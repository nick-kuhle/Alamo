# -*- coding: utf-8 -*-
"""Config-driven scraper: add a site with a JSON file, no Python required.

Drop files into ``userdata/addon_data/plugin.video.alamo/providers/sites/``:

    {
      "id": "example",
      "name": "Example",
      "base": "https://example.com",
      "search_url": "https://example.com/?s={query}",
      "result_pattern": "<a href=\\"(?P<url>[^\\"]+)\\"[^>]*>(?P<title>[^<]+)</a>",
      "link_pattern": "<iframe[^>]+src=\\"(?P<url>[^\\"]+)\\"",
      "movie_query": "{title} {year}",
      "episode_query": "{show} S{season:02d}E{episode:02d}",
      "capabilities": ["movie", "episode"],
      "require_resolvable": true,
      "headers": {"Referer": "https://example.com/"},
      "priority": 50
    }

Only ``id``, ``name``, ``search_url`` and ``result_pattern`` are required. Leave
``link_pattern`` out and every outbound link on the page is harvested, which is
usually enough. Named groups ``url`` and ``title`` are what the patterns must
capture.
"""
import os
import re
import glob
import json

from .. import kodi
from . import net
from .scraper_base import HosterScraper

REQUIRED = ('id', 'name', 'search_url', 'result_pattern')


def sites_dir():
    path = os.path.join(kodi.ensure_profile(), 'providers', 'sites')
    if not os.path.isdir(path):
        os.makedirs(path)
        with open(os.path.join(path, 'README.txt'), 'w') as handle:
            handle.write(
                'Drop one JSON file per site here - see docs/SCRAPERS.md.\n'
                'Required keys: id, name, search_url, result_pattern.\n'
                'The patterns are Python regexes with named groups '
                '(?P<url>...) and (?P<title>...).\n')
    return path


class ConfigScraper(HosterScraper):
    """A HosterScraper whose behaviour comes from a dict rather than code."""

    def __init__(self, config):
        self.config = config
        self.id = config['id']
        self.name = config['name']
        self.version = str(config.get('version', '1.0.0'))
        self.priority = int(config.get('priority', 50))
        self.capabilities = tuple(config.get('capabilities',
                                             ('movie', 'episode')))
        self.base_url = config.get('base', '')
        self.require_resolvable = bool(config.get('require_resolvable', True))
        self.page_ttl = int(config.get('cache_hours', 6)) * 3600
        self.headers = config.get('headers') or {}
        self._result_re = re.compile(config['result_pattern'],
                                     re.I | re.S)
        link_pattern = config.get('link_pattern')
        self._link_re = re.compile(link_pattern, re.I | re.S) if link_pattern else None

    # -- query building ---------------------------------------------------
    def query_for(self, item, media_type):
        if media_type == 'episode':
            template = self.config.get('episode_query',
                                       '{show} S{season:02d}E{episode:02d}')
            return template.format(
                show=item.get('show_title') or item.get('title') or '',
                title=item.get('title') or '',
                season=int(item.get('season') or 0),
                episode=int(item.get('episode') or 0),
                year=item.get('year') or '')
        template = self.config.get('movie_query', '{title} {year}')
        return template.format(title=item.get('title') or '',
                               year=item.get('year') or '').strip()

    # -- the two hooks ----------------------------------------------------
    def search(self, query, item, media_type):
        url = self.config['search_url'].format(
            query=net.requests.utils.quote(query),
            query_plus=query.replace(' ', '+'),
            query_dash=query.replace(' ', '-'))
        body = self.fetch(url, headers=self.headers)
        if not body:
            return []
        results = []
        for match in self._result_re.finditer(body):
            data = match.groupdict()
            link = net.absolute(self.base_url or url, data.get('url', ''))
            title = re.sub(r'<[^>]+>', ' ', data.get('title', '') or '')
            results.append((' '.join(title.split()), link))
        return results

    def links(self, page_url, page_body, item):
        if not self._link_re:
            return [('', url) for url in self.harvest(page_body)]
        found = []
        for match in self._link_re.finditer(page_body):
            data = match.groupdict()
            url = net.absolute(self.base_url or page_url, data.get('url', ''))
            found.append((data.get('title') or '', url))
        return found


def load_configs():
    """Every valid site config on disk, as ConfigScraper instances."""
    scrapers = []
    for path in sorted(glob.glob(os.path.join(sites_dir(), '*.json'))):
        try:
            with open(path, 'r') as handle:
                config = json.load(handle)
        except Exception as exc:
            kodi.error('bad site config %s: %s' % (path, exc))
            continue
        missing = [key for key in REQUIRED if not config.get(key)]
        if missing:
            kodi.error('site config %s is missing %s'
                       % (os.path.basename(path), ', '.join(missing)))
            continue
        try:
            scrapers.append(ConfigScraper(config))
        except re.error as exc:
            kodi.error('site config %s has a bad regex: %s'
                       % (os.path.basename(path), exc))
        except Exception as exc:
            kodi.error('site config %s failed to load: %s'
                       % (os.path.basename(path), exc))
    return scrapers
