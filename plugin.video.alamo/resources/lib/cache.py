# -*- coding: utf-8 -*-
"""Tiny sqlite backed cache used for TMDB responses and provider results."""
import os
import time
import json
import hashlib
import sqlite3
import threading

from . import kodi

_LOCK = threading.Lock()
_DB = None

DAY = 60 * 60 * 24


def _db():
    global _DB
    if _DB is None:
        kodi.ensure_profile()
        path = os.path.join(kodi.PROFILE_PATH, 'alamo_cache.db')
        _DB = sqlite3.connect(path, timeout=20, check_same_thread=False)
        _DB.execute('CREATE TABLE IF NOT EXISTS cache '
                    '(key TEXT PRIMARY KEY, value TEXT, expires REAL)')
        _DB.commit()
    return _DB


def _key(namespace, *parts):
    raw = namespace + '|' + '|'.join(repr(p) for p in parts)
    return hashlib.md5(raw.encode('utf-8')).hexdigest()


def get(namespace, *parts):
    key = _key(namespace, *parts)
    try:
        with _LOCK:
            row = _db().execute(
                'SELECT value, expires FROM cache WHERE key = ?', (key,)
            ).fetchone()
    except Exception as exc:
        kodi.error('cache get failed: %s' % exc)
        return None
    if not row:
        return None
    if row[1] < time.time():
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


def put(value, ttl, namespace, *parts):
    key = _key(namespace, *parts)
    try:
        with _LOCK:
            _db().execute(
                'INSERT OR REPLACE INTO cache (key, value, expires) VALUES (?,?,?)',
                (key, json.dumps(value), time.time() + ttl))
            _db().commit()
    except Exception as exc:
        kodi.error('cache put failed: %s' % exc)
    return value


def cached(ttl, namespace, func, *args, **kwargs):
    """Return cached value for func(*args) or compute + store it."""
    hit = get(namespace, *args)
    if hit is not None:
        return hit
    value = func(*args, **kwargs)
    if value:
        put(value, ttl, namespace, *args)
    return value


def clear():
    try:
        with _LOCK:
            _db().execute('DELETE FROM cache')
            _db().commit()
        return True
    except Exception as exc:
        kodi.error('cache clear failed: %s' % exc)
        return False
