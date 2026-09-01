# -*- coding: utf-8 -*-
"""Discovery and scan reporting for built-in hand-written scrapers.

Two things this does that The Crew's equivalent does not:

**Discovery reads declared metadata.** The Crew globs ``scrapers/*.py`` and
then regex-greps each file's *source text* to decide whether it is a torrent
or debrid scraper. That silently misclassifies any scraper whose style differs.
Here we import the module and read class attributes.

**Every scan is recorded.** ``last_report()`` returns one row per scraper with
its source count, elapsed time and error, which the UI shows in Diagnostics.
When a site dies you can see which one, instead of just getting fewer results.
"""
import os
import pkgutil
import importlib
import threading

from .. import kodi
from .base import Scraper  # noqa: F401  (re-export for scraper modules)

_CACHE = {'scrapers': None}
_REPORT = {'rows': [], 'started': 0.0, 'elapsed': 0.0}
_LOCK = threading.Lock()

#: modules that are infrastructure, not scrapers
_SKIP = frozenset({'base', '__init__'})


def _package_dir():
    return os.path.dirname(os.path.abspath(__file__))


def discover(refresh=False):
    """Import every scraper module and instantiate what it declares."""
    if _CACHE['scrapers'] is not None and not refresh:
        return _CACHE['scrapers']

    found = []
    for _finder, name, ispkg in pkgutil.iter_modules([_package_dir()]):
        if ispkg or name in _SKIP or name.startswith('_'):
            continue
        try:
            module = importlib.import_module('.' + name, __name__)
        except Exception as exc:
            kodi.error('scraper %s failed to import: %s' % (name, exc))
            continue

        instance = None
        if hasattr(module, 'get_scraper'):
            try:
                instance = module.get_scraper()
            except Exception as exc:
                kodi.error('get_scraper() failed in %s: %s' % (name, exc))
                continue
        else:
            # fall back to the first Scraper subclass defined in the module
            for attr in vars(module).values():
                if (isinstance(attr, type) and issubclass(attr, Scraper)
                        and attr is not Scraper
                        and attr.__module__ == module.__name__):
                    try:
                        instance = attr()
                    except Exception as exc:
                        kodi.error('%s could not be built: %s' % (attr, exc))
                    break

        if instance is None:
            continue
        if not instance.ID:
            kodi.error('scraper in %s has no ID, skipping' % name)
            continue
        found.append(instance)

    found.sort(key=lambda s: (s.PRIORITY, s.NAME))
    _CACHE['scrapers'] = found
    kodi.log('discovered %d built-in scraper(s): %s'
             % (len(found), ', '.join(s.ID for s in found)))
    return found


def enabled(capability=None):
    """Discovered scrapers minus the ones the user switched off."""
    import json
    try:
        off = set(json.loads(kodi.setting('disabled_providers', '[]') or '[]'))
    except ValueError:
        off = set()
    items = [s for s in discover() if s.ID not in off]
    if capability:
        items = [s for s in items if capability in s.CAPABILITIES]
    return items


def find(scraper_id):
    for scraper in discover():
        if scraper.ID == scraper_id:
            return scraper
    return None


# ---------------------------------------------------------------------------
# scan reporting
# ---------------------------------------------------------------------------

def begin_report():
    import time
    with _LOCK:
        _REPORT['rows'] = []
        _REPORT['started'] = time.time()
        _REPORT['elapsed'] = 0.0


def record(scraper_id, name, count, elapsed, error=''):
    import time
    with _LOCK:
        _REPORT['rows'].append({
            'id': scraper_id, 'name': name, 'count': count,
            'elapsed': round(elapsed, 2), 'error': str(error or ''),
        })
        if _REPORT['started']:
            _REPORT['elapsed'] = round(time.time() - _REPORT['started'], 2)


def last_report():
    """Rows sorted worst-first so problems surface at the top."""
    with _LOCK:
        rows = list(_REPORT['rows'])
        total = _REPORT['elapsed']
    rows.sort(key=lambda r: (not r['error'], r['count'], -r['elapsed']))
    return {'rows': rows, 'elapsed': total,
            'sources': sum(r['count'] for r in rows)}
