# -*- coding: utf-8 -*-
"""Internet Archive provider - real, legal, direct links.

The Archive's moving image collection holds a large amount of public domain and
freely licensed film. It has a proper JSON API, serves direct MP4s, and is happy
to be queried - which makes it the perfect thing to prove the whole pipeline
end to end without pointing at anybody's warez site.

It is also a genuinely useful source: silent era, film noir, classic sci-fi,
government and educational film, and a lot of pre-1930 features.
"""
from . import net
from . import parsing
from .. import kodi
from .base import Provider, Source

SEARCH = 'https://archive.org/advancedsearch.php'
METADATA = 'https://archive.org/metadata/%s'
DOWNLOAD = 'https://archive.org/download/%s/%s'

#: archive format name -> quality guess when the file carries no dimensions.
#: The originals (h.264 MPEG4 / Matroska / MPEG4) are the good copies; the
#: plain 'h.264' and '512Kb' entries are downscaled web derivatives.
VIDEO_FORMATS = {
    'h.264 MPEG4': '1080p',
    'MPEG4': '1080p',
    'HiRes MPEG4': '1080p',
    'Matroska': '1080p',
    'WebM': '720p',
    'h.264 IA': '720p',
    'h.264': 'SD',
    '512Kb MPEG4': 'SD',
    'Ogg Video': 'SD',
    'MPEG2': 'SD',
    'DivX': 'SD',
}

PLAYABLE_EXT = ('.mp4', '.m4v', '.mkv', '.webm', '.ogv', '.m2ts', '.mpg',
                '.mpeg', '.avi')

#: the Archive is full of extras filed under the film's own title
JUNK_WORDS = ('trailer', 'featurette', 'interview', 'commentary', 'sample',
              'excerpt', 'clip', 'behind the scenes', 'making of', 'outtake',
              'promo', 'teaser', 'restoration demo', 'soundtrack')


def _is_junk(text, wanted_title):
    low = (text or '').lower()
    wanted = (wanted_title or '').lower()
    return any(word in low and word not in wanted for word in JUNK_WORDS)

TTL = 12 * 3600


def _quality(entry, fmt, name):
    """Trust real pixel dimensions first, then the filename, then the format.

    Archive identifiers lie constantly - an item called "..._1080p" routinely
    holds a 640x360 derivative.
    """
    def _int(key):
        try:
            return int(entry.get(key) or 0)
        except Exception:
            return 0

    height, width = _int('height'), _int('width')
    if height or width:
        if height >= 1700 or width >= 3000:
            return '4K'
        if height >= 900 or width >= 1700:
            return '1080p'
        if height >= 650 or width >= 1200:
            return '720p'
        return 'SD'
    guess = parsing.quality(name)
    if guess != 'SD':
        return guess
    return VIDEO_FORMATS.get(fmt, 'SD')


class ArchiveProvider(Provider):
    id = 'archive_org'
    name = 'Internet Archive'
    version = '1.0.0'
    priority = 30
    capabilities = ('movie',)

    def ping(self):
        return kodi.setting_bool('provider_archive', True)

    # ------------------------------------------------------------------
    def _search(self, title, year):
        query = 'title:("%s") AND mediatype:(movies)' % title.replace('"', '')
        if year:
            query += ' AND date:[%s-01-01 TO %s-12-31]' % (int(year) - 1,
                                                           int(year) + 1)
        payload = net.get_json(SEARCH, params={
            'q': query,
            'fl[]': ['identifier', 'title', 'year', 'downloads'],
            'rows': 12, 'page': 1, 'output': 'json',
            'sort[]': 'downloads desc',
        }, ttl=TTL)
        return ((payload.get('response') or {}).get('docs') or [])

    def _files(self, identifier):
        payload = net.get_json(METADATA % identifier, ttl=TTL)
        return payload.get('files') or []

    def movie(self, item):
        title = item.get('title') or ''
        year = item.get('year') or ''
        if not title:
            return []

        sources = []
        for doc in self._search(title, year):
            identifier = doc.get('identifier')
            found_title = doc.get('title') or ''
            if isinstance(found_title, list):
                found_title = found_title[0] if found_title else ''
            # the Archive holds a lot of same-named home movies and trailers.
            # containment, not overlap: "Nosferatu (1922)" contains "Nosferatu"
            if parsing.containment(found_title, title) < 0.8:
                continue
            # "Nosferatu, eine Symphonie des Grauens" is fine (starts with the
            # title); "Beulah Bains In The Kid" is a different film entirely
            starts_with_title = parsing.normalise(found_title).startswith(
                parsing.normalise(title))
            if not starts_with_title and parsing.extra_words(found_title, title) > 2:
                continue
            if _is_junk(found_title, title):
                continue

            for entry in self._files(identifier):
                fmt = entry.get('format') or ''
                name = entry.get('name') or ''
                if fmt not in VIDEO_FORMATS:
                    continue
                if not name.lower().endswith(PLAYABLE_EXT):
                    continue
                if _is_junk(name, title):
                    continue
                try:
                    size = round(int(entry.get('size') or 0) / float(1024 ** 3), 2)
                except Exception:
                    size = 0.0
                sources.append(Source(
                    url=DOWNLOAD % (identifier, net.requests.utils.quote(name)),
                    name='%s [%s]' % (found_title, fmt),
                    quality=_quality(entry, fmt, name),
                    info='Internet Archive \u2022 public domain \u2022 %s' % fmt,
                    size=size,
                    direct=True,
                    language='en',
                ))
            if len(sources) >= 24:
                break

        order = {'4K': 0, '1080p': 1, '720p': 2, 'SD': 3}
        sources.sort(key=lambda s: (order.get(s['quality'], 3), -s['size']))
        kodi.log('archive_org: %d sources for %s' % (len(sources), title))
        return sources[:12]


def get_provider():
    return ArchiveProvider()
