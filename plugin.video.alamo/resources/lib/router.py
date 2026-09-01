# -*- coding: utf-8 -*-
"""Plugin URL routing.

Opening the add-on normally launches the custom UI. The plugin:// routes exist
so skins, widgets and favourites can point at The Alamo directly.
"""
import sys

try:
    from urllib.parse import parse_qsl, urlencode
except ImportError:  # pragma: no cover
    from urlparse import parse_qsl
    from urllib import urlencode

import xbmcgui
import xbmcplugin

from . import kodi
from . import tmdb
from . import cache
from . import store
from . import player
from .ui import listitems


def url(**params):
    return 'plugin://%s/?%s' % (kodi.ADDON_ID, urlencode(params))


def _end(handle, content='videos', succeeded=True):
    if content:
        xbmcplugin.setContent(handle, content)
    xbmcplugin.endOfDirectory(handle, succeeded=succeeded, cacheToDisc=False)


def _dir_items(handle, entries):
    for entry in entries:
        item = listitems.media_item(entry)
        item.setLabel(entry.get('title', ''))
        if entry.get('type') in ('movie', 'episode', 'sports'):
            item.setProperty('IsPlayable', 'true')
            target = url(action='play', type=entry.get('type'),
                         id=entry.get('id'), season=entry.get('season') or '',
                         episode=entry.get('episode') or '',
                         stream=entry.get('url') or '',
                         provider=entry.get('provider') or '',
                         title=entry.get('title') or '')
            xbmcplugin.addDirectoryItem(handle, target, item, False)
        else:
            target = url(action='list', kind='%s_details' % entry.get('type'),
                         id=entry.get('id'))
            xbmcplugin.addDirectoryItem(handle, target, item, True)


WIDGETS = {
    'trending_movies': lambda page: tmdb.row('movie', 'trending', page),
    'popular_movies': lambda page: tmdb.row('movie', 'popular', page),
    'top_rated_movies': lambda page: tmdb.row('movie', 'top_rated', page),
    'in_theatres': lambda page: tmdb.row('movie', 'now_playing', page),
    'trending_tv': lambda page: tmdb.row('tv', 'trending', page),
    'popular_tv': lambda page: tmdb.row('tv', 'popular', page),
    'on_today': lambda page: tmdb.row('tv', 'airing_today', page),
}


def _widget(handle, kind, page):
    if kind == 'mylist':
        entries = store.mylist()
    elif kind == 'continue':
        entries = store.progress()
    else:
        loader = WIDGETS.get(kind)
        if not loader:
            _end(handle, succeeded=False)
            return
        entries, info = loader(page)
        _dir_items(handle, entries)
        if info.get('page', 1) < info.get('total_pages', 1):
            item = xbmcgui.ListItem(label='Next page')
            xbmcplugin.addDirectoryItem(
                handle, url(action='list', kind=kind, page=page + 1), item, True)
        _end(handle)
        return
    _dir_items(handle, entries)
    _end(handle)


def _play(params, handle):
    """Playable route used by widgets, favourites and the custom UI fallback."""
    from .ui import windows
    media_type = params.get('type', 'movie')
    if media_type == 'sports':
        item = {'type': 'sports', 'id': params.get('id', ''),
                'title': params.get('title', ''), 'url': params.get('stream', ''),
                'provider': params.get('provider', '')}
        if item['url']:
            source = {'url': item['url'], 'direct': True,
                      'provider': item['provider'], 'name': item['title']}
            if player.play(source, item, handle=handle):
                store.note_play(item)
            return
        windows.play_item(item)
        return

    tmdb_id = params.get('id')
    if media_type == 'episode':
        show = tmdb.details('tv', tmdb_id)
        episodes = tmdb.season(tmdb_id, params.get('season', 1), show)
        wanted = str(params.get('episode', '1'))
        item = next((e for e in episodes if str(e['episode']) == wanted), None)
        if not item:
            kodi.notify('Episode not found')
            xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
            return
    else:
        item = tmdb.details('movie', tmdb_id)
    windows.play_item(item)
    xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())


def ask_tmdb_key(prompt_first=False):
    """Ask for a TMDB key with the on-screen keyboard, verify it, save it.

    This is the fallback path: it works even if the settings dialog is
    unavailable, and it validates the key against TMDB before saving.
    """
    if prompt_first:
        if not kodi.yesno('The Alamo needs a free TMDB API key to show Movies '
                          'and TV.\n\nGet one at themoviedb.org (Settings > '
                          'API > API Key v3 auth).\n\nEnter it now?'):
            return False
    key = kodi.keyboard('TMDB API key (v3 auth)', kodi.setting('tmdb_key', ''))
    if not key:
        return False
    ok, message = tmdb.verify_key(key)
    if ok:
        kodi.set_setting('tmdb_key', key)
        cache.clear()
        kodi.notify('TMDB key saved')
        return True
    kodi.ok('%s\n\nNothing was saved.' % message, 'TMDB key not accepted')
    return False


def dispatch(argv):
    handle = int(argv[1]) if len(argv) > 1 and argv[1].lstrip('-').isdigit() else -1
    params = dict(parse_qsl(argv[2][1:])) if len(argv) > 2 else {}
    action = params.get('action', '')
    kodi.log('dispatch %s %s' % (action or 'home', params))

    if action == 'play':
        _play(params, handle)
        return

    if action == 'list':
        _widget(handle, params.get('kind', ''), int(params.get('page', 1) or 1))
        return

    if action == 'set_tmdb':
        ask_tmdb_key()
        return

    if action == 'clear_cache':
        cache.clear()
        kodi.notify('Cache cleared')
        return

    if action == 'clear_progress':
        store.clear_progress()
        kodi.notify('Continue Watching cleared')
        return

    if action == 'sites_folder':
        from .providers import config_scraper
        folder = config_scraper.sites_dir()
        found = config_scraper.load_configs()
        kodi.ok('Drop one JSON file per site into:\n\n%s\n\nLoaded right '
                'now: %s\n\nFormat: docs/SCRAPERS.md'
                % (folder, ', '.join(p.id for p in found) or 'none'),
                'Site configs')
        return

    if action == 'providers':
        from .providers import registry
        found = registry.all_providers(refresh=True)
        if not found:
            kodi.ok('No providers installed.\n\nDrop a provider .py in\n%s\n'
                    'or install a script.alamo.provider.* add-on.'
                    % registry.providers_dir())
        else:
            kodi.ok('\n'.join('%s  (%s)  -  %s' %
                              (p.name, p.version, ', '.join(p.capabilities))
                              for p in found), 'Installed providers')
        return

    # anything else = open the custom UI
    from . import app
    if handle > 0:
        xbmcplugin.endOfDirectory(handle, succeeded=False, updateListing=False,
                                  cacheToDisc=False)
    app.run(action or 'home')
