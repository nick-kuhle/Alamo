# -*- coding: utf-8 -*-
"""Section controller: decides which window opens next.

Navigation is *nested*: opening Movies from Home puts the Movies window on top
of Home rather than closing it. That matters visually - if we closed first,
Kodi's own home screen would be on screen for as long as the next section takes
to load. Nested means an Alamo window is always the thing you are looking at,
and the new window paints its own loading screen from the first frame.
"""
import threading

from . import kodi
from . import tmdb
from . import store
from .providers import registry
from .ui import windows

#: how many Alamo windows are currently stacked
_DEPTH = [0]


def depth():
    return _DEPTH[0]


def _static(items):
    def loader(page):
        return (items, {'page': 1, 'total_pages': 1}) if page == 1 else ([], {})
    return loader


class CategoryGrid(windows.GridWindow):
    """A wall of category tiles (Trending, Genres, Leagues...)."""

    def onClick(self, control_id):
        if control_id == windows.GRID:
            position = self.getControl(windows.GRID).getSelectedPosition()
            if 0 <= position < len(self.entries):
                entry = self.entries[position]
                target = entry.get('open')
                if callable(target):
                    target()
                    return
            return
        windows.GridWindow.onClick(self, control_id)


def _open(cls, **kwargs):
    _DEPTH[0] += 1
    try:
        window = cls(cls.xml, kodi.ADDON_PATH, windows.SKIN, windows.RES, **kwargs)
        window.doModal()
        following = getattr(window, 'next_window', None)
        del window
        return following
    finally:
        _DEPTH[0] -= 1


def _tile(title, thumb='', plot='', open_callback=None, badge='', fanart=''):
    return {'type': 'category', 'title': title, 'thumb': thumb, 'poster': thumb,
            'fanart': fanart or thumb, 'plot': plot, 'open': open_callback,
            'badge': badge}


def _parallel(jobs, workers=8):
    """Run ``jobs`` (list of no-arg callables) concurrently, keeping order."""
    results = [None] * len(jobs)
    lock = threading.Semaphore(workers)

    def run(index, job):
        with lock:
            try:
                results[index] = job()
            except Exception as exc:
                kodi.error('tile art failed: %s' % exc)
                results[index] = ''

    threads = [threading.Thread(target=run, args=(i, j))
               for i, j in enumerate(jobs)]
    for thread in threads:
        thread.daemon = True
        thread.start()
    for thread in threads:
        thread.join(20)
    return results


def _row_art(media_type, row_id):
    """Use the top item's poster as the tile image - portrait, so it fills the
    same 2:3 frame as every other tile instead of being stretched."""
    try:
        items, _ = tmdb.row(media_type, row_id)
        return (items[0]['poster'] or items[0]['thumb']) if items else ''
    except Exception:
        return ''


def _genre_art(media_type, genre_id):
    try:
        items, _ = tmdb.genre(media_type, genre_id)
        return (items[0]['poster'] or items[0]['thumb']) if items else ''
    except Exception:
        return ''


# --------------------------------------------------------------------------
# sections
# --------------------------------------------------------------------------

def open_grid(title, loader, section, search_type='', search_label=''):
    return _open(windows.GridWindow, title=title, loader=loader,
                 section=section, search_type=search_type,
                 search_label=search_label)


def catalogue(media_type):
    """Movies / TV landing page: big tiles for each row and each genre."""
    section = 'movies' if media_type == 'movie' else 'tv'
    label = 'Movies' if media_type == 'movie' else 'TV Shows'
    if not tmdb.has_key():
        from . import router
        if not router.ask_tmdb_key(prompt_first=True):
            return None

    rows = tmdb.MOVIE_ROWS if media_type == 'movie' else tmdb.TV_ROWS
    genres = tmdb.MOVIE_GENRES if media_type == 'movie' else tmdb.TV_GENRES

    def loader(page):
        """Built on the window's worker thread, so the loading screen shows
        immediately instead of the UI stalling before the window even opens."""
        if page != 1:
            return [], {}
        jobs = [(lambda r=row_id: _row_art(media_type, r)) for row_id, _l, _p, _e in rows]
        jobs += [(lambda g=gid: _genre_art(media_type, g)) for gid, _l in genres]
        art = _parallel(jobs)

        tiles = [_tile('Search %s' % label, kodi.media('search_tile.png'), '',
                       (lambda: search(media_type)))]
        for index, (row_id, row_label, _path, _extra) in enumerate(rows):
            tiles.append(_tile(
                row_label, art[index], '',
                (lambda rid=row_id, rlabel=row_label: open_grid(
                    rlabel, lambda page_, r=rid: tmdb.row(media_type, r, page_),
                    section, media_type, 'Search %s' % label))))
        for index, (genre_id, genre_label) in enumerate(genres):
            tiles.append(_tile(
                genre_label, art[len(rows) + index], '',
                (lambda gid=genre_id, glabel=genre_label: open_grid(
                    glabel, lambda page_, g=gid: tmdb.genre(media_type, g, page_),
                    section, media_type, 'Search %s' % label))))
        return tiles, {'page': 1, 'total_pages': 1}

    return _open(CategoryGrid, title=label, loader=loader, section=section,
                 search_type=media_type, search_label='Search %s' % label)


def sports():
    def loader(page):
        if page != 1:
            return [], {}
        catalog = registry.sports_catalog()
        tiles = [_tile('Search Sports', kodi.media('search_tile.png'), '',
                       (lambda: search('sports')))]
        for category in catalog:
            tiles.append(_tile(
                category.get('title') or category['id'],
                category.get('thumb') or kodi.media('sports_tile.png'), '',
                (lambda cid=category['id'], ctitle=category.get('title', ''):
                 open_grid(ctitle or 'Sports', _static(_events(cid)), 'sports',
                           'sports', 'Search Sports'))))
        return tiles, {'page': 1, 'total_pages': 1}

    if not registry.for_capability('sports'):
        kodi.ok('No sports providers yet.\n\nPoint the built-in playlist '
                'provider at an M3U or JSON guide in Settings, or install an '
                'Alamo provider add-on.')
        return 'settings'
    return _open(CategoryGrid, title='Sports', loader=loader, section='sports',
                 search_type='sports', search_label='Search Sports')


def _events(category_id):
    entries = []
    for event in registry.sports_events(category_id):
        entries.append({
            'id': event.get('id'), 'type': 'sports',
            'title': event.get('title', ''),
            'thumb': event.get('thumb') or kodi.media('sports_tile.png'),
            'poster': event.get('thumb') or kodi.media('sports_tile.png'),
            'fanart': event.get('fanart', ''),
            'plot': event.get('plot', ''),
            'live': event.get('live'), 'start': event.get('start', ''),
            'league': event.get('league', ''), 'url': event.get('url', ''),
            'provider': event.get('provider', ''),
        })
    return entries


def search(what='all', query=None):
    """Search within a section. ``what`` is movie, tv, sports or all."""
    names = {'movie': 'Movies', 'tv': 'TV', 'sports': 'Sports', 'all': 'The Alamo'}
    query = query or kodi.keyboard('Search %s' % names.get(what, 'The Alamo'))
    if not query:
        return None
    store.add_search(query)
    section = {'movie': 'movies', 'tv': 'tv', 'sports': 'sports'}.get(what, 'home')

    if what == 'sports':
        needle = query.lower()
        hits = [e for e in _events('') if needle in (e['title'] or '').lower()
                or needle in (e.get('league') or '').lower()]
        return open_grid('Sports: %s' % query, _static(hits), 'sports',
                         'sports', 'Search Sports')

    def loader(page):
        if what in ('movie', 'tv'):
            items, info = tmdb.search(what, query, page)
            return items, info
        movies, minfo = tmdb.search('movie', query, page)
        shows, tinfo = tmdb.search('tv', query, page)
        merged = sorted(movies + shows, key=lambda i: -(i.get('votes') or 0))
        return merged, {'page': page,
                        'total_pages': max(minfo.get('total_pages', 1),
                                           tinfo.get('total_pages', 1))}

    return open_grid('%s: %s' % (names.get(what, 'Search'), query), loader,
                     section, what if what in ('movie', 'tv') else '',
                     'Search %s' % names.get(what, ''))


def mylist():
    items = store.mylist()
    if not items:
        kodi.notify('My List is empty - press C on any poster to add')
        return None
    return open_grid('My List', _static(items), 'mylist')


# --------------------------------------------------------------------------
# main loop
# --------------------------------------------------------------------------

SECTIONS = {
    'movies': lambda: catalogue('movie'),
    'tv': lambda: catalogue('tv'),
    'sports': sports,
    'search': lambda: search('all'),
    'mylist': mylist,
}


def open_section(name):
    """Open a section nested on top of whatever is currently showing."""
    handler = SECTIONS.get(name)
    if not handler:
        return None
    return handler()


def run(start='home'):
    # First run: no key means empty Movies/TV, so offer the keyboard straight
    # away rather than sending people hunting through the settings dialog.
    if not tmdb.has_key() and not kodi.setting_bool('tmdb_prompted', False):
        kodi.set_setting('tmdb_prompted', 'true')
        from . import router
        router.ask_tmdb_key(prompt_first=True)

    current = start
    guard = 0
    while current and guard < 100:
        guard += 1
        if current == 'home':
            current = _open(windows.HomeWindow)
        elif current == 'settings':
            kodi.open_settings()
            current = 'home'
        elif current in SECTIONS:
            current = open_section(current) or None
        else:
            current = None
