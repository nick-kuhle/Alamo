# -*- coding: utf-8 -*-
"""Discovers, loads and queries providers."""
import os
import sys
import glob
import json
import importlib.util
import threading

import xbmcvfs

from .. import kodi
from .base import Provider, Source, SportsEvent  # noqa: F401  (re-export)

ADDON_PREFIX = 'script.alamo.provider.'

_CACHE = {'providers': None}


def providers_dir():
    path = os.path.join(kodi.ensure_profile(), 'providers')
    if not os.path.isdir(path):
        os.makedirs(path)
        readme = os.path.join(path, 'README.txt')
        with open(readme, 'w') as handle:
            handle.write(
                'Drop provider .py files here.\n'
                'Each file must define get_provider() returning a Provider '
                'instance. See the Alamo documentation for the API.\n')
    return path


def _load_module(path, name):
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    except Exception as exc:
        kodi.error('failed loading provider %s: %s' % (path, exc))
        return None


def _from_module(module):
    if not module or not hasattr(module, 'get_provider'):
        return None
    try:
        provider = module.get_provider()
    except Exception as exc:
        kodi.error('get_provider() failed in %s: %s' % (module, exc))
        return None
    return provider if isinstance(provider, Provider) else None


def _addon_providers():
    found = []
    result = kodi.jsonrpc('Addons.GetAddons', type='xbmc.python.module',
                          enabled=True, properties=['path', 'name', 'version'])
    addons = (result.get('result') or {}).get('addons') or []
    result2 = kodi.jsonrpc('Addons.GetAddons', type='xbmc.python.script',
                           enabled=True, properties=['path', 'name', 'version'])
    addons += (result2.get('result') or {}).get('addons') or []
    for addon in addons:
        addon_id = addon.get('addonid', '')
        if not addon_id.startswith(ADDON_PREFIX):
            continue
        path = xbmcvfs.translatePath(addon.get('path', ''))
        for candidate in (os.path.join(path, 'provider.py'),
                          os.path.join(path, 'lib', 'provider.py')):
            if os.path.isfile(candidate):
                provider = _from_module(
                    _load_module(candidate, 'alamo_p_' + addon_id.replace('.', '_')))
                if provider:
                    found.append(provider)
                break
    return found


def _file_providers():
    found = []
    for path in sorted(glob.glob(os.path.join(providers_dir(), '*.py'))):
        name = os.path.splitext(os.path.basename(path))[0]
        if name.startswith('_'):
            continue
        provider = _from_module(_load_module(path, 'alamo_f_' + name))
        if provider:
            found.append(provider)
    return found


def _builtin_providers():
    from . import playlist_provider
    found = []
    provider = playlist_provider.get_provider()
    if provider and provider.ping():
        found.append(provider)
    return found


def all_providers(refresh=False):
    if _CACHE['providers'] is None or refresh:
        providers = _builtin_providers() + _file_providers() + _addon_providers()
        disabled = set(json.loads(kodi.setting('disabled_providers', '[]') or '[]'))
        providers = [p for p in providers if p.id not in disabled]
        providers.sort(key=lambda p: (p.priority, p.name))
        _CACHE['providers'] = providers
        kodi.log('loaded %d providers: %s'
                 % (len(providers), ', '.join(p.id for p in providers)))
    return _CACHE['providers']


def for_capability(capability):
    return [p for p in all_providers() if capability in p.capabilities]


def find(provider_id):
    for provider in all_providers():
        if provider.id == provider_id:
            return provider
    return None


# --------------------------------------------------------------------------
# parallel source collection
# --------------------------------------------------------------------------

def collect(capability, item, timeout=None, on_progress=None):
    """Query every capable provider in parallel and return merged sources."""
    timeout = timeout or kodi.setting_int('scrape_timeout', 45)
    providers = for_capability(capability)
    results = []
    lock = threading.Lock()
    done = {'count': 0}

    def worker(provider):
        found = []
        try:
            if capability == 'movie':
                found = provider.movie(item) or []
            elif capability == 'episode':
                found = provider.episode(item) or []
            elif capability == 'sports':
                found = provider.sports_sources(item) or []
        except Exception as exc:
            kodi.error('provider %s failed: %s' % (provider.id, exc))
        for source in found:
            source['provider'] = provider.id
            source.setdefault('provider_name', provider.name)
        with lock:
            results.extend(found)
            done['count'] += 1
            if on_progress:
                on_progress(done['count'], len(providers), provider.name,
                            len(results))

    threads = [threading.Thread(target=worker, args=(p,)) for p in providers]
    for thread in threads:
        thread.daemon = True
        thread.start()
    for thread in threads:
        thread.join(timeout)
    return results


def sports_catalog():
    """Merged sports categories from all sports capable providers."""
    rows = {}
    for provider in for_capability('sports'):
        try:
            for category in provider.sports_categories() or []:
                key = category.get('id')
                if not key:
                    continue
                entry = rows.setdefault(key, dict(category, providers=[]))
                entry['providers'].append(provider.id)
        except Exception as exc:
            kodi.error('sports categories failed for %s: %s' % (provider.id, exc))
    return list(rows.values())


def sports_events(category_id):
    events = []
    for provider in for_capability('sports'):
        try:
            for event in provider.sports_events(category_id) or []:
                event['provider'] = provider.id
                events.append(event)
        except Exception as exc:
            kodi.error('sports events failed for %s: %s' % (provider.id, exc))
    events.sort(key=lambda e: (not e.get('live'), e.get('start') or '',
                               e.get('title') or ''))
    return events
