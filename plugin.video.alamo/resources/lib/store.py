# -*- coding: utf-8 -*-
"""My List, Continue Watching and search history - a small JSON store."""
import os
import json
import time
import threading

from . import kodi

_LOCK = threading.Lock()
_FILES = {'mylist': 'mylist.json', 'progress': 'progress.json',
          'searches': 'searches.json'}


def _path(name):
    return os.path.join(kodi.ensure_profile(), _FILES[name])


def _read(name, default):
    try:
        with open(_path(name), 'r') as handle:
            return json.load(handle)
    except Exception:
        return default


def _write(name, data):
    with _LOCK:
        try:
            with open(_path(name), 'w') as handle:
                json.dump(data, handle)
        except Exception as exc:
            kodi.error('store write failed (%s): %s' % (name, exc))
    return data


# -- my list ---------------------------------------------------------------

def mylist():
    return _read('mylist', [])


def in_mylist(media_type, tmdb_id):
    return any(i['type'] == media_type and str(i['id']) == str(tmdb_id)
               for i in mylist())


def toggle_mylist(item):
    items = mylist()
    key = (item['type'], str(item['id']))
    remaining = [i for i in items
                 if (i['type'], str(i['id'])) != key]
    if len(remaining) != len(items):
        _write('mylist', remaining)
        return False
    slim = {k: item.get(k) for k in
            ('id', 'type', 'title', 'year', 'thumb', 'poster', 'fanart',
             'plot', 'rating')}
    slim['added'] = time.time()
    _write('mylist', [slim] + remaining)
    return True


# -- continue watching -----------------------------------------------------

def progress():
    return _read('progress', [])


def note_play(item):
    """Remember what was just started so Home can show Continue Watching."""
    items = [i for i in progress()
             if not (i['type'] == item['type'] and str(i['id']) == str(item['id'])
                     and i.get('season') == item.get('season')
                     and i.get('episode') == item.get('episode'))]
    slim = {k: item.get(k) for k in
            ('id', 'type', 'title', 'year', 'thumb', 'poster', 'fanart',
             'plot', 'season', 'episode', 'show_title')}
    slim['played'] = time.time()
    return _write('progress', ([slim] + items)[:40])


def clear_progress():
    return _write('progress', [])


# -- searches --------------------------------------------------------------

def searches():
    return _read('searches', [])


def add_search(query):
    items = [q for q in searches() if q.lower() != query.lower()]
    return _write('searches', ([query] + items)[:25])


def clear_searches():
    return _write('searches', [])
