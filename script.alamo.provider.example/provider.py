# -*- coding: utf-8 -*-
"""Example Alamo provider add-on.

Copy this folder, rename it to script.alamo.provider.<yours>, edit addon.xml
and this file. The Alamo will pick it up automatically on the next start.

This example returns links from a JSON index that you host yourself, e.g.::

    {
      "movies": {"tt0111161": [{"name": "Shawshank 1080p", "url": "https://..."}]},
      "episodes": {"tt0944947|1|1": [{"name": "GoT S01E01", "url": "https://..."}]}
    }

Nothing is scraped: you decide what the index contains.
"""
import json

import requests
import xbmcaddon

try:
    from resources.lib.providers.base import Provider, Source
except ImportError:  # running inside The Alamo's loader
    Provider = object
    Source = dict

ADDON = xbmcaddon.Addon()


class ExampleProvider(Provider):
    id = 'example_index'
    name = 'Example JSON index'
    version = '1.0.1'
    priority = 40
    capabilities = ('movie', 'episode')

    def _index(self):
        url = ADDON.getSetting('index_url').strip()
        if not url:
            return {}
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            return response.json()
        except Exception:
            return {}

    def _sources(self, entries):
        out = []
        for entry in entries or []:
            out.append(Source(url=entry.get('url', ''),
                              name=entry.get('name', ''),
                              quality=entry.get('quality', ''),
                              size=float(entry.get('size') or 0),
                              direct=bool(entry.get('direct'))))
        return [s for s in out if s.get('url')]

    def movie(self, item):
        key = item.get('imdb') or str(item.get('id'))
        return self._sources((self._index().get('movies') or {}).get(key))

    def episode(self, item):
        key = '%s|%s|%s' % (item.get('imdb') or item.get('id'),
                            item.get('season'), item.get('episode'))
        return self._sources((self._index().get('episodes') or {}).get(key))


def get_provider():
    return ExampleProvider()
