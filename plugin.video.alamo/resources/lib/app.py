# -*- coding: utf-8 -*-
"""Section controller: decides which window opens next."""
from . import kodi
from . import tmdb
from . import store
from .providers import registry
from .ui import windows


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
    window = cls(cls.xml, kodi.ADDON_PATH, windows.SKIN, windows.RES, **kwargs)
    window.doModal()
    following = getattr(window, 'next_window', None)
    del window
    return following


def _tile(title, thumb='', plot='', open_callback=None, badge=''):
    return {'type': 'category', 'title': title, 'thumb': thumb, 'poster': thumb,
            'fanart': thumb, 'plot': plot, 'open': open_callback, 'badge': badge}


def _row_art(media_type, row_id):
    """Use the top item's artwork as the tile image - cheap and gorgeous."""
    try:
        items, _ = tmdb.row(media_type, row_id)
        return items[0]['backdrop'] or items[0]['thumb'] if items else ''
    except Exception:
        return ''


def _genre_art(media_type, genre_id):
    try:
        items, _ = tmdb.genre(media_type, genre_id)
        return items[0]['backdrop'] or items[0]['thumb'] if items else ''
    except Exception:
        return ''


# --------------------------------------------------------------------------
# sections
# --------------------------------------------------------------------------

def open_grid(title, loader, section):
    return _open(windows.GridWindow, title=title, loader=loader, section=section)


def catalogue(media_type):
    """Movies / TV landing page: big tiles for each row and each genre."""
    section = 'movies' if media_type == 'movie' else 'tv'
    label = 'Movies' if media_type == 'movie' else 'TV Shows'
    if not tmdb.has_key():
        kodi.ok('Add your free TMDB API key in Settings to browse %s.' % label)
        return 'settings'
    rows = tmdb.MOVIE_ROWS if media_type == 'movie' else tmdb.TV_ROWS
    genres = tmdb.MOVIE_GENRES if media_type == 'movie' else tmdb.TV_GENRES

    tiles = []
    for row_id, row_label, _path, _extra in rows:
        tiles.append(_tile(
            row_label, _row_art(media_type, row_id), '',
            (lambda rid=row_id, rlabel=row_label: open_grid(
                rlabel, lambda page, r=rid: tmdb.row(media_type, r, page),
                section))))
    for genre_id, genre_label in genres:
        tiles.append(_tile(
            genre_label, _genre_art(media_type, genre_id), '',
            (lambda gid=genre_id, glabel=genre_label: open_grid(
                glabel, lambda page, g=gid: tmdb.genre(media_type, g, page),
                section))))
    return _open(CategoryGrid, title=label, loader=_static(tiles),
                 section=section)


def sports():
    catalog = registry.sports_catalog()
    if not catalog:
        kodi.ok('No sports providers yet.\n\nPoint the built-in playlist '
                'provider at an M3U or JSON guide in Settings, or install an '
                'Alamo provider add-on.')
        return 'settings'
    tiles = []
    for category in catalog:
        tiles.append(_tile(
            category.get('title') or category['id'],
            category.get('thumb') or kodi.media('sports_tile.png'), '',
            (lambda cid=category['id'], ctitle=category.get('title', ''):
             open_grid(ctitle or 'Sports',
                       _static(_events(cid)), 'sports'))))
    return _open(CategoryGrid, title='Sports', loader=_static(tiles),
                 section='sports')


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


def search(query=None):
    query = query or kodi.keyboard('Search The Alamo')
    if not query:
        return None
    store.add_search(query)

    def loader(page):
        movies, minfo = tmdb.search('movie', query, page)
        shows, tinfo = tmdb.search('tv', query, page)
        merged = sorted(movies + shows,
                        key=lambda i: -(i.get('votes') or 0))
        return merged, {'page': page,
                        'total_pages': max(minfo.get('total_pages', 1),
                                           tinfo.get('total_pages', 1))}

    return open_grid('Search: %s' % query, loader, 'search')


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
    'search': search,
    'mylist': mylist,
}


def run(start='home'):
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
            following = SECTIONS[current]()
            current = following or 'home'
        else:
            current = None
