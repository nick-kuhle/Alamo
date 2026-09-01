# -*- coding: utf-8 -*-
"""Wikimedia Commons — public-domain and freely licensed films.

Commons hosts complete public-domain features (Night of the Living Dead,
Nosferatu, His Girl Friday...) as direct .webm/.ogv/.mp4 files served from
upload.wikimedia.org. No login, no rate limit worth worrying about, and the
files are direct-playable so Kodi needs no resolver.

API: https://commons.wikimedia.org/w/api.php  (action=query, generator=search)
"""
import urllib.parse

from .base import Scraper, quality_for, is_junk

API = 'https://commons.wikimedia.org/w/api.php'

# Commons search returns a lot of unrelated footage for short titles; we ask
# for more than we need and let the shared title gate do the filtering.
SEARCH_LIMIT = 30

PLAYABLE_MIME = ('video/webm', 'video/ogg', 'video/mp4', 'video/quicktime',
                 'application/ogg')


class WikimediaCommons(Scraper):
    ID = 'wikimedia'
    NAME = 'Wikimedia Commons'
    KIND = 'free'
    PRIORITY = 20
    CAPABILITIES = ('movie',)
    TIMEOUT = 20
    ATTRIBUTION = 'Wikimedia Commons - public domain / CC'
    # Commons requires a descriptive UA or it will start returning 403s.
    HEADERS = {
        'User-Agent': 'TheAlamo-Kodi/1.0 (https://github.com/nick-kuhle/Alamo)',
        'Accept': 'application/json',
    }

    def _search(self, query):
        params = {
            'action': 'query',
            'format': 'json',
            'formatversion': '2',
            'generator': 'search',
            'gsrsearch': 'filetype:video %s' % query,
            'gsrnamespace': '6',          # File:
            'gsrlimit': str(SEARCH_LIMIT),
            'prop': 'imageinfo',
            'iiprop': 'url|size|mime|dimensions',
        }
        data = self.get_json('%s?%s' % (API, urllib.parse.urlencode(params)))
        if not isinstance(data, dict):
            return []
        return (data.get('query') or {}).get('pages') or []

    def movie(self, item):
        title = item.get('title') or ''
        if not title:
            return []
        query = title
        if item.get('year'):
            # year in the query improves ranking but must not be mandatory,
            # since most Commons filenames omit it
            query = '%s %s' % (title, item['year'])

        found = []
        seen = set()
        for page in self._search(query) or self._search(title):
            name = (page.get('title') or '').replace('File:', '')
            info = (page.get('imageinfo') or [{}])[0]
            url = info.get('url') or ''
            mime = (info.get('mime') or '').lower()

            if not url or url in seen:
                continue
            if mime and not any(mime.startswith(m) for m in PLAYABLE_MIME):
                continue
            # filename AND page title both get the junk check
            if is_junk(name, url):
                continue
            if not self.accepts(name, item):
                continue

            seen.add(url)
            size = float(info.get('size') or 0) / (1024.0 ** 3)
            found.append(self.source(
                url,
                self._clean(name),
                quality=quality_for(info.get('width'), info.get('height'), name),
                size=size,
                direct=True,
                info='Public domain'))
        return found

    @staticmethod
    def _clean(name):
        for ext in ('.webm', '.ogv', '.ogg', '.mp4', '.mov'):
            if name.lower().endswith(ext):
                name = name[:-len(ext)]
        return name.replace('_', ' ').strip()


def get_scraper():
    return WikimediaCommons()
