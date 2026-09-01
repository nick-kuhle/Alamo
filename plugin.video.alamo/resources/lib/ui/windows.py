# -*- coding: utf-8 -*-
"""The custom windows - this is where The Alamo stops looking like Kodi."""
import threading

import xbmc
import xbmcgui

from .. import kodi
from .. import tmdb
from .. import store
from .. import player
from ..providers import registry
from . import listitems

SKIN = 'Default'
RES = '1080i'

# control ids -------------------------------------------------------------
NAV = 90
HERO_ROWS = [101, 102, 103, 104, 105]
GRID = 50
SEASONS = 40
EPISODES = 41
RECOMMENDED = 42
SEARCH_BTN = 61
BTN_PLAY = 31
BTN_TRAILER = 32
BTN_MYLIST = 33
SOURCES = 50

# Search lives at the top of each section now, not in the rail: you almost
# always want to search *within* Movies, TV or Sports.
NAV_ITEMS = [
    ('home', 'Home'),
    ('movies', 'Movies'),
    ('tv', 'TV'),
    ('sports', 'Sports'),
    ('mylist', 'My List'),
    ('settings', 'Settings'),
]

ACTION_BACK = (9, 10, 92, 216, 247, 257, 275, 61467, 61448)


def _thread(func, *args, **kwargs):
    thread = threading.Thread(target=func, args=args, kwargs=kwargs)
    thread.daemon = True
    thread.start()
    return thread


class BaseWindow(xbmcgui.WindowXML):
    xml = 'alamo-home.xml'

    def __init__(self, *args, **kwargs):
        super(BaseWindow, self).__init__(*args, **kwargs)
        self.next_window = None

    # -- helpers ----------------------------------------------------------
    def prop(self, key, value=''):
        self.setProperty(key, value if value is not None else '')

    def busy(self, on=True, text=''):
        if on:
            self.prop('LoadingText', text or getattr(self, 'title', '') or '')
        self.prop('Loading', 'true' if on else '')

    def fill(self, control_id, items):
        try:
            control = self.getControl(control_id)
        except Exception:
            return None
        control.reset()
        if items:
            control.addItems(items)
        return control

    def build_nav(self, active=''):
        # so "did my update actually install?" is answerable at a glance
        self.prop('Version', kodi.ADDON_VERSION)
        items = [listitems.menu_item(label, kodi.media('nav_%s.png' % key),
                                     key) for key, label in NAV_ITEMS]
        control = self.fill(NAV, items)
        if control:
            for index, (key, _label) in enumerate(NAV_ITEMS):
                if key == active:
                    control.selectItem(index)
                    break
        self.prop('Section', active.title())

    # -- events -----------------------------------------------------------
    def onAction(self, action):
        if action.getId() in ACTION_BACK:
            self.close()

    def onClick(self, control_id):
        if control_id == NAV:
            item = self.getControl(NAV).getSelectedItem()
            if item:
                self.navigate(item.getProperty('action'))

    #: how deep we let nested windows stack before unwinding instead
    MAX_DEPTH = 6

    def navigate(self, action):
        """Open the next section *on top of* this window.

        Closing first and opening after would show Kodi's own UI for as long as
        the next section takes to load. Opening nested means an Alamo window is
        on screen the entire time - the new one paints its loading screen
        immediately and fills in behind it.
        """
        if not action or action == getattr(self, 'section', None):
            return
        if action == 'settings':
            kodi.open_settings()
            return
        from .. import app
        if app.depth() >= self.MAX_DEPTH:
            # too deep - fall back to unwinding to the root and going from there
            self.next_window = action
            self.close()
            return
        app.open_section(action)


class HomeWindow(BaseWindow):
    xml = 'alamo-home.xml'

    section = 'home'

    def onInit(self):
        self.prop('Heading', 'The Alamo')
        self.build_nav('home')
        self.busy(True, 'Loading The Alamo')
        _thread(self._load)

    def _rows(self):
        rows = []
        recent = store.progress()
        if recent:
            rows.append(('Continue Watching', recent))
        if tmdb.has_key():
            trending_movies, _ = tmdb.row('movie', 'trending')
            trending_tv, _ = tmdb.row('tv', 'trending')
        else:
            trending_movies = trending_tv = []
        live = []
        for event in registry.sports_events('')[:24]:
            live.append({'id': event.get('id'), 'type': 'sports',
                         'title': event.get('title'),
                         'thumb': event.get('thumb') or kodi.media('sports_tile.png'),
                         'fanart': event.get('fanart', ''),
                         'plot': event.get('plot', ''),
                         'live': event.get('live'),
                         'league': event.get('league', ''),
                         'start': event.get('start', ''),
                         'url': event.get('url', ''),
                         'provider': event.get('provider', '')})
        if live:
            rows.append(('Live & On Now', live))
        if trending_movies:
            rows.append(('Trending Movies', trending_movies))
        if trending_tv:
            rows.append(('Trending TV', trending_tv))
        if tmdb.has_key():
            popular, _ = tmdb.row('movie', 'popular')
            if popular:
                rows.append(('Popular on The Alamo', popular))
        return rows[:len(HERO_ROWS)]

    def _load(self):
        rows = self._rows()
        self._data = {}
        for index, control_id in enumerate(HERO_ROWS):
            if index < len(rows):
                title, entries = rows[index]
                self.prop('Row%dTitle' % (index + 1), title)
                self.fill(control_id,
                          [listitems.media_item(e) for e in entries])
                self._data[control_id] = entries
            else:
                self.prop('Row%dTitle' % (index + 1), '')
                self.fill(control_id, [])
                self._data[control_id] = []
        self.busy(False)
        if not tmdb.has_key():
            self.prop('Empty', 'Add a free TMDB API key in Settings to '
                               'unlock Movies and TV')
        try:
            for control_id in HERO_ROWS:
                if self._data.get(control_id):
                    self.setFocusId(control_id)
                    break
        except Exception:
            pass

    def onClick(self, control_id):
        if control_id in HERO_ROWS:
            entries = getattr(self, '_data', {}).get(control_id) or []
            control = self.getControl(control_id)
            position = control.getSelectedPosition()
            if 0 <= position < len(entries):
                open_item(entries[position])
            return
        BaseWindow.onClick(self, control_id)


class GridWindow(BaseWindow):
    """A wall of posters - used for every browse, genre and search result."""

    xml = 'alamo-grid.xml'

    def __init__(self, *args, **kwargs):
        super(GridWindow, self).__init__(*args, **kwargs)
        self.title = kwargs.get('title', '')
        self.loader = kwargs.get('loader')     # callable(page) -> (items, info)
        self.section = kwargs.get('section', '')
        self.search_type = kwargs.get('search_type', '')   # movie / tv / sports
        self.search_label = kwargs.get('search_label', '')
        self.entries = []
        self.page = 1
        self.total_pages = 1
        self.loading = False

    def onInit(self):
        self.prop('Heading', self.title)
        self.prop('SearchLabel', self.search_label)
        self.build_nav(self.section)
        self.busy(True, 'Loading %s' % self.title)
        _thread(self._load, 1)

    def _load(self, page):
        if self.loading:
            return
        self.loading = True
        try:
            items, info = self.loader(page)
        except Exception as exc:
            kodi.error('grid load failed: %s' % exc)
            items, info = [], {}
        if page == 1:
            self.entries = []
        self.entries += items
        self.page = info.get('page', page)
        self.total_pages = info.get('total_pages', 1)
        control = self.fill(GRID, [listitems.media_item(e) for e in self.entries])
        self.prop('Count', str(len(self.entries)))
        self.prop('Empty', '' if self.entries else 'Nothing found')
        self.busy(False)
        self.loading = False
        if page == 1 and control and self.entries:
            try:
                self.setFocusId(GRID)
            except Exception:
                pass

    def _maybe_more(self):
        if self.loading or self.page >= self.total_pages:
            return
        try:
            position = self.getControl(GRID).getSelectedPosition()
        except Exception:
            return
        if position >= len(self.entries) - 12:
            _thread(self._load, self.page + 1)

    def onAction(self, action):
        BaseWindow.onAction(self, action)
        self._maybe_more()

    def onClick(self, control_id):
        if control_id == GRID:
            position = self.getControl(GRID).getSelectedPosition()
            if 0 <= position < len(self.entries):
                open_item(self.entries[position])
            return
        if control_id == SEARCH_BTN:
            self.do_search()
            return
        BaseWindow.onClick(self, control_id)

    def do_search(self):
        if not self.search_type:
            return
        from .. import app
        app.search(self.search_type)


class DetailWindow(BaseWindow):
    xml = 'alamo-detail.xml'

    def __init__(self, *args, **kwargs):
        super(DetailWindow, self).__init__(*args, **kwargs)
        self.entry = kwargs.get('entry') or {}
        self.item = {}
        self.episodes = []
        self.season_index = 0

    def onInit(self):
        entry = self.entry
        self.prop('Title', entry.get('title', ''))
        self.prop('Poster', entry.get('poster') or entry.get('thumb', ''))
        self.prop('Fanart', entry.get('fanart') or entry.get('backdrop', ''))
        self.prop('Plot', entry.get('plot', ''))
        self.prop('IsTV', 'true' if entry.get('type') == 'tv' else '')
        self.busy(True, entry.get('title', ''))
        _thread(self._load)

    def _load(self):
        item = tmdb.details(self.entry.get('type', 'movie'), self.entry.get('id'))
        if not item:
            item = dict(self.entry)
        self.item = item
        self.prop('Title', item.get('title', ''))
        self.prop('Tagline', item.get('tagline', ''))
        self.prop('Plot', item.get('plot', ''))
        self.prop('Poster', item.get('poster', ''))
        self.prop('Fanart', item.get('fanart', ''))
        self.prop('Clearlogo', item.get('clearlogo', ''))
        self.prop('Rating', str(item.get('rating') or ''))
        self.prop('Year', str(item.get('year') or ''))
        self.prop('Genres', ' \u2022 '.join(item.get('genres') or [])[:60])
        runtime = item.get('runtime') or 0
        self.prop('Runtime', ('%dh %02dm' % (runtime // 60, runtime % 60))
                  if runtime else '')
        self.prop('Cast', ', '.join(c['name'] for c in (item.get('cast') or [])[:5]))
        self.prop('InMyList', 'true' if store.in_mylist(
            item.get('type'), item.get('id')) else '')
        self.prop('HasTrailer', 'true' if item.get('trailer') else '')

        if item.get('type') == 'tv':
            seasons = item.get('seasons') or []
            self.fill(SEASONS, [listitems.media_item({
                'title': s['title'], 'thumb': s['poster'], 'plot': s['plot'],
                'year': (s.get('premiered') or '')[:4], 'type': 'season',
                'id': s['season']}) for s in seasons])
            if seasons:
                _thread(self._load_season, seasons[0]['season'])
        self.fill(RECOMMENDED, [listitems.media_item(e)
                                for e in (item.get('recommendations') or [])[:20]])
        self.busy(False)

    def _load_season(self, season_number):
        self.busy(True)
        self.episodes = tmdb.season(self.item.get('id'), season_number, self.item)
        self.fill(EPISODES, [listitems.episode_item(e) for e in self.episodes])
        self.prop('SeasonTitle', 'Season %s' % season_number)
        self.busy(False)

    # -- actions ----------------------------------------------------------
    def onClick(self, control_id):
        if control_id == BTN_PLAY:
            self._play(self.item)
        elif control_id == BTN_TRAILER and self.item.get('trailer'):
            xbmc.Player().play(self.item['trailer'])
        elif control_id == BTN_MYLIST:
            added = store.toggle_mylist(self.item)
            self.prop('InMyList', 'true' if added else '')
            kodi.notify('Added to My List' if added else 'Removed from My List')
        elif control_id == SEASONS:
            seasons = self.item.get('seasons') or []
            position = self.getControl(SEASONS).getSelectedPosition()
            if 0 <= position < len(seasons):
                _thread(self._load_season, seasons[position]['season'])
        elif control_id == EPISODES:
            position = self.getControl(EPISODES).getSelectedPosition()
            if 0 <= position < len(self.episodes):
                self._play(self.episodes[position])
        elif control_id == RECOMMENDED:
            position = self.getControl(RECOMMENDED).getSelectedPosition()
            recommendations = self.item.get('recommendations') or []
            if 0 <= position < len(recommendations):
                self.entry = recommendations[position]
                self.onInit()
        else:
            BaseWindow.onClick(self, control_id)

    def _play(self, item):
        if item.get('type') == 'tv':
            if self.episodes:
                item = self.episodes[0]
            else:
                kodi.notify('Pick an episode')
                return
        play_item(item)


class SourcesDialog(xbmcgui.WindowXMLDialog):
    """Scrapes providers with a live progress line, then lists what it found."""

    xml = 'alamo-sources.xml'

    def __init__(self, *args, **kwargs):
        super(SourcesDialog, self).__init__(*args, **kwargs)
        self.item = kwargs.get('item') or {}
        self.capability = kwargs.get('capability', 'movie')
        self.sources = []
        self.chosen = None
        self.cancelled = False

    def onInit(self):
        self.setProperty('Title', self.item.get('title', ''))
        self.setProperty('Scanning', 'true')
        self.setProperty('Status', 'Looking for streams...')
        _thread(self._scrape)

    def _progress(self, done, total, name, found):
        self.setProperty('Status', '%s/%s providers  -  %s streams  -  %s'
                         % (done, total, found, name))

    def _scrape(self):
        raw = registry.collect(self.capability, self.item,
                               on_progress=self._progress)
        if self.cancelled:
            return
        self.sources = player.prepare(raw)
        items = [listitems.source_item(s, i) for i, s in enumerate(self.sources)]
        try:
            control = self.getControl(SOURCES)
            control.reset()
            if items:
                control.addItems(items)
        except Exception as exc:
            kodi.error('sources fill failed: %s' % exc)
        self.setProperty('Scanning', '')
        self.setProperty('Status', '%d streams found' % len(self.sources)
                         if self.sources else 'No streams found')
        self.setProperty('Empty', '' if self.sources else 'true')
        if self.sources:
            try:
                self.setFocusId(SOURCES)
            except Exception:
                pass
            if kodi.setting_bool('autoplay', True):
                self.chosen = self.sources[0]
                self.close()

    def onAction(self, action):
        if action.getId() in ACTION_BACK:
            self.cancelled = True
            self.close()

    def onClick(self, control_id):
        if control_id == SOURCES:
            position = self.getControl(SOURCES).getSelectedPosition()
            if 0 <= position < len(self.sources):
                self.chosen = self.sources[position]
                self.close()


# --------------------------------------------------------------------------
# window plumbing
# --------------------------------------------------------------------------

def _open(cls, **kwargs):
    window = cls(cls.xml, kodi.ADDON_PATH, SKIN, RES, **kwargs)
    window.doModal()
    following = getattr(window, 'next_window', None)
    del window
    return following


def open_item(entry):
    """Poster clicked - sports plays straight away, movies/TV open details."""
    if entry.get('type') == 'sports':
        play_item(entry)
    elif entry.get('type') == 'episode':
        play_item(entry)
    else:
        _open(DetailWindow, entry=entry)


def play_item(item):
    capability = {'movie': 'movie', 'episode': 'episode',
                  'sports': 'sports'}.get(item.get('type'), 'movie')
    if not registry.for_capability(capability):
        kodi.ok('No %s providers are installed yet.\n\nThe Alamo does not '
                'include any sources of its own - add a provider add-on, or '
                'point the built-in playlist provider at your own playlist '
                'in Settings.' % capability)
        return
    dialog = SourcesDialog(SourcesDialog.xml, kodi.ADDON_PATH, SKIN, RES,
                           item=item, capability=capability)
    dialog.doModal()
    chosen = dialog.chosen
    del dialog
    if not chosen:
        return
    if player.play(chosen, item, handle=-1):
        store.note_play(item)
