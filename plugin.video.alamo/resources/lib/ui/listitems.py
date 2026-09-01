# -*- coding: utf-8 -*-
"""Turn Alamo dicts into pretty ListItems (poster first, text second)."""
import xbmcgui

from .. import kodi

BADGE = {'movie': 'Film', 'tv': 'Series', 'episode': 'Episode',
         'sports': 'Live'}


def _stars(rating):
    try:
        rating = float(rating or 0)
    except Exception:
        rating = 0
    return ('%0.1f' % rating) if rating else ''


def media_item(entry, focus_label=True):
    """A poster tile. Label is used for the hero panel, not drawn on the tile."""
    title = entry.get('title') or ''
    item = xbmcgui.ListItem(label=title if focus_label else '')
    thumb = entry.get('thumb') or entry.get('poster') or ''
    item.setArt({
        'thumb': thumb,
        'poster': entry.get('poster') or thumb,
        'fanart': entry.get('fanart') or entry.get('backdrop') or '',
        'icon': thumb,
    })
    item.setProperties({
        'id': str(entry.get('id', '')),
        'type': entry.get('type', ''),
        'title': title,
        'year': str(entry.get('year') or ''),
        'plot': entry.get('plot') or '',
        'rating': _stars(entry.get('rating')),
        'badge': BADGE.get(entry.get('type', ''), ''),
        'backdrop': entry.get('backdrop') or entry.get('fanart') or '',
        'clearlogo': entry.get('clearlogo') or '',
        'season': str(entry.get('season') or ''),
        'episode': str(entry.get('episode') or ''),
        'show_title': entry.get('show_title') or '',
        'live': 'true' if entry.get('live') else '',
        'start': entry.get('start') or '',
        'league': entry.get('league') or '',
        'url': entry.get('url') or '',
        'provider': entry.get('provider') or '',
    })
    return item


def episode_item(entry):
    item = media_item(entry)
    label = '%s. %s' % (entry.get('episode'), entry.get('title'))
    item.setLabel(label)
    item.setProperty('subtitle', entry.get('premiered') or '')
    return item


def menu_item(label, icon='', action='', badge=''):
    item = xbmcgui.ListItem(label=label)
    if icon:
        item.setArt({'icon': icon, 'thumb': icon})
    item.setProperties({'action': action, 'title': label, 'badge': badge})
    return item


def source_item(source, index):
    quality = source.get('quality', 'SD')
    name = source.get('name') or source.get('url', '')
    item = xbmcgui.ListItem(label=name)
    size = source.get('size') or 0
    item.setProperties({
        'index': str(index),
        'quality': quality,
        'provider': source.get('provider_name') or source.get('provider', ''),
        'size': ('%.2f GB' % size) if size else '',
        'info': source.get('info', ''),
        'debrid': source.get('debrid', ''),
        'direct': 'true' if source.get('direct') else '',
    })
    return item
