# -*- coding: utf-8 -*-
"""Library of Congress — National Screening Room and other moving-image sets.

The LoC JSON API is unusually generous: a single search response already
carries the direct MP4 URL, the pixel height, the duration and a poster, so
one request per query is enough. Everything is public domain or free to view.

API: https://www.loc.gov/collections/national-screening-room/?q=...&fo=json
"""
import urllib.parse

from .base import Scraper, quality_for, is_junk

BASE = 'https://www.loc.gov'
#: verified live. 'silent-films' looks plausible and 404s - do not re-add it.
COLLECTIONS = (
    'collections/national-screening-room',
    'film-and-videos',          # site-wide, catches items outside the NSR
)
PAGE_SIZE = 25


class LibraryOfCongress(Scraper):
    ID = 'loc'
    NAME = 'Library of Congress'
    KIND = 'free'
    PRIORITY = 25
    CAPABILITIES = ('movie',)
    TIMEOUT = 25
    ATTRIBUTION = 'Library of Congress - public domain'
    HEADERS = {
        'User-Agent': 'TheAlamo-Kodi/1.0 (https://github.com/nick-kuhle/Alamo)',
        'Accept': 'application/json',
    }

    def _search(self, collection, query):
        params = {'q': query, 'fo': 'json', 'c': str(PAGE_SIZE), 'at': 'results'}
        url = '%s/%s/?%s' % (BASE, collection, urllib.parse.urlencode(params))
        data = self.get_json(url)
        if not isinstance(data, dict):
            return []
        return data.get('results') or []

    def movie(self, item):
        title = item.get('title') or ''
        if not title:
            return []

        found = []
        seen = set()
        for collection in COLLECTIONS:
            try:
                results = self._search(collection, title)
            except Exception as exc:                      # one dead collection
                self._log_skip(collection, exc)           # must not kill the rest
                continue

            for result in results:
                name = result.get('title') or ''
                if is_junk(name):
                    continue
                if not self.accepts(name, item):
                    continue

                for resource in result.get('resources') or []:
                    url = resource.get('video') or ''
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    duration = resource.get('duration') or 0
                    found.append(self.source(
                        url,
                        name,
                        quality=quality_for(resource.get('width'),
                                            resource.get('height'), name),
                        size=0.0,
                        direct=True,
                        info=self._info(duration, result.get('date'))))
        return found

    def _log_skip(self, collection, exc):
        from .. import kodi
        kodi.log('%s collection %s unavailable: %s'
                 % (self.log_prefix, collection, exc))

    @staticmethod
    def _info(duration, date):
        bits = []
        if duration:
            try:
                bits.append('%d min' % max(1, int(duration) // 60))
            except (TypeError, ValueError):
                pass
        if date:
            bits.append(str(date))
        bits.append('Public domain')
        return ' - '.join(bits)


def get_scraper():
    return LibraryOfCongress()
