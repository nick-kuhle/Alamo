# -*- coding: utf-8 -*-
"""Built-in provider: user supplied playlist.

The Alamo ships with exactly one provider and it scrapes nothing. It reads a
playlist that *you* point it at in the settings - either

* an M3U / M3U8 playlist (``#EXTINF`` entries, ``group-title`` becomes the
  category, ``tvg-logo`` becomes the artwork), or
* an Alamo JSON guide::

    {
      "categories": [
        {"id": "nfl", "title": "NFL", "thumb": "https://..."}
      ],
      "events": [
        {"id": "1", "category": "nfl", "title": "Chiefs @ Bills",
         "start": "2026-09-07T20:20:00Z", "live": true,
         "thumb": "https://...", "url": "https://.../stream.m3u8"}
      ]
    }

Perfect for your own IPTV subscription, a local network stream, or the free
official channels a lot of leagues publish.
"""
import re
import time
import datetime

import requests

from .. import kodi
from .. import cache
from .base import Provider, Source, SportsEvent

EXTINF = re.compile(r'#EXTINF:(?P<dur>-?\d+)(?P<attrs>[^,]*),(?P<title>.*)')
ATTR = re.compile(r'([\w-]+)="([^"]*)"')


def _slug(text):
    return re.sub(r'[^a-z0-9]+', '-', (text or '').lower()).strip('-') or 'other'


class PlaylistProvider(Provider):
    id = 'playlist'
    name = 'My Playlist'
    version = '1.0.0'
    priority = 10
    capabilities = ('sports',)

    # -- fetching ---------------------------------------------------------
    @property
    def url(self):
        return kodi.setting('playlist_url', '').strip()

    def ping(self):
        return bool(self.url)

    def _download(self):
        url = self.url
        if not url:
            return ''
        hit = cache.get('playlist', url)
        if hit is not None:
            return hit
        try:
            if url.startswith(('http://', 'https://')):
                response = requests.get(url, timeout=25)
                response.raise_for_status()
                text = response.text
            else:
                with open(url, 'r', encoding='utf-8', errors='ignore') as handle:
                    text = handle.read()
        except Exception as exc:
            kodi.error('playlist download failed: %s' % exc)
            return ''
        ttl = max(kodi.setting_int('playlist_refresh', 30), 1) * 60
        cache.put(text, ttl, 'playlist', url)
        return text

    def _parse(self):
        text = self._download()
        if not text:
            return [], []
        stripped = text.lstrip()
        if stripped.startswith('{'):
            return self._parse_json(stripped)
        return self._parse_m3u(text)

    def _parse_json(self, text):
        import json
        try:
            data = json.loads(text)
        except Exception as exc:
            kodi.error('bad json guide: %s' % exc)
            return [], []
        categories = data.get('categories') or []
        events = []
        for raw in data.get('events') or []:
            events.append(SportsEvent(
                id=str(raw.get('id') or raw.get('title')),
                title=raw.get('title', ''),
                league=raw.get('category', ''),
                start=raw.get('start', ''),
                thumb=raw.get('thumb', ''),
                fanart=raw.get('fanart', ''),
                plot=raw.get('plot', ''),
                live=bool(raw.get('live')),
                url=raw.get('url', ''),
            ))
        if not categories:
            seen = {}
            for event in events:
                seen.setdefault(event['league'], {
                    'id': event['league'], 'title': event['league'].title(),
                    'thumb': event['thumb']})
            categories = list(seen.values())
        return categories, events

    def _parse_m3u(self, text):
        categories, events = {}, []
        pending = None
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith('#EXTINF'):
                match = EXTINF.match(line)
                if not match:
                    continue
                attrs = dict(ATTR.findall(match.group('attrs')))
                pending = {
                    'title': match.group('title').strip(),
                    'group': attrs.get('group-title', 'Channels'),
                    'logo': attrs.get('tvg-logo', ''),
                }
            elif line.startswith('#'):
                continue
            elif pending:
                group_id = _slug(pending['group'])
                categories.setdefault(group_id, {
                    'id': group_id, 'title': pending['group'],
                    'thumb': pending['logo']})
                events.append(SportsEvent(
                    id='%s|%s' % (group_id, pending['title']),
                    title=pending['title'], league=group_id,
                    thumb=pending['logo'], live=True, url=line))
                pending = None
        return list(categories.values()), events

    # -- provider api -----------------------------------------------------
    def sports_categories(self):
        categories, _events = self._parse()
        return categories

    def sports_events(self, category_id):
        _categories, events = self._parse()
        return [e for e in events if e['league'] == category_id or not category_id]

    def sports_sources(self, event):
        if not event.get('url'):
            return []
        return [Source(url=event['url'], name=event.get('title', 'Stream'),
                       quality='HD', direct=True, info='playlist')]


def get_provider():
    return PlaylistProvider()
