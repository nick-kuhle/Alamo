# -*- coding: utf-8 -*-
"""Base class for hoster-link scrapers.

A scraper subclass only has to answer two questions:

* given a movie or episode, which pages should I look at?  (``search``)
* given one of those pages, which hoster links are on it? (``links``)

Everything else - matching, quality/size parsing, deduplication, dropping
hosters ResolveURL cannot play, error isolation - happens here.
"""
import re

from .. import kodi
from .. import cache
from . import net
from . import parsing
from .base import Provider, Source

#: links that are never a video
JUNK_HOSTS = ('google.com/recaptcha', 'facebook.com', 'twitter.com', 'x.com',
              'pinterest.', 'reddit.com', 'imdb.com', 'themoviedb.org',
              'youtube.com/channel', 'discord.', 'telegram.', 'paypal.',
              't.me/', 'archive.org/details')

URL_RE = re.compile(r'https?://[^\s"\'<>\\]+', re.I)


def host_of(url):
    match = re.match(r'https?://(?:www\.)?([^/:]+)', url or '', re.I)
    return match.group(1).lower() if match else ''


class _ResolveURL(object):
    """Lazy, optional ResolveURL access with a memoised host whitelist."""

    def __init__(self):
        self._module = None
        self._checked = False
        self._valid = {}

    @property
    def module(self):
        if not self._checked:
            self._checked = True
            try:
                import resolveurl
                self._module = resolveurl
            except ImportError:
                kodi.log('ResolveURL not installed - hoster links cannot be '
                         'validated or resolved')
        return self._module

    def playable(self, url):
        """True when ResolveURL claims it can handle this link.

        With ResolveURL absent we do not throw links away - we just cannot
        promise anything, so everything is kept.
        """
        if not self.module:
            return True
        host = host_of(url)
        if host in self._valid:
            return self._valid[host]
        try:
            ok = bool(self.module.HostedMediaFile(url=url).valid_url())
        except Exception:
            ok = False
        self._valid[host] = ok
        return ok


RESOLVER = _ResolveURL()


class HosterScraper(Provider):
    """Scrapes pages for direct hoster links."""

    id = 'hoster'
    name = 'Hoster scraper'
    version = '1.0.0'
    capabilities = ('movie', 'episode')

    #: site root, used to resolve relative links
    base_url = ''
    #: cache page bodies for this long
    page_ttl = 6 * 3600
    #: give up on one site after this many result pages
    max_pages = 1
    #: skip links whose host ResolveURL does not support (user overridable)
    require_resolvable = True

    @property
    def _resolvable_only(self):
        return self.require_resolvable and kodi.setting_bool(
            'require_resolvable', True)

    # ---------------------------------------------------------------- hooks
    def search(self, query, item, media_type):
        """Return candidate page urls: ``[(title, url), ...]``."""
        raise NotImplementedError

    def links(self, page_url, page_body, item):
        """Return ``[(name, url), ...]`` hoster links found on a page.

        An empty name means "use the release name from the search result",
        which is almost always the more informative of the two.
        """
        return [('', url) for url in self.harvest(page_body)]

    # ------------------------------------------------------------- helpers
    def fetch(self, url, **kwargs):
        kwargs.setdefault('ttl', self.page_ttl)
        kwargs.setdefault('referer', self.base_url or None)
        return net.get(url, **kwargs)

    def harvest(self, body):
        """Every plausible outbound video link on a page."""
        found, seen = [], set()
        for url in URL_RE.findall(body or ''):
            url = url.rstrip('.,);\'"')
            if url in seen:
                continue
            seen.add(url)
            low = url.lower()
            if any(junk in low for junk in JUNK_HOSTS):
                continue
            if self.base_url and host_of(url) == host_of(self.base_url):
                continue
            if low.endswith(('.jpg', '.jpeg', '.png', '.gif', '.css', '.js',
                             '.svg', '.woff', '.woff2', '.ico')):
                continue
            found.append(url)
        return found

    def query_for(self, item, media_type):
        title = item.get('show_title') or item.get('title') or ''
        if media_type == 'episode':
            return '%s S%02dE%02d' % (title, int(item.get('season') or 0),
                                      int(item.get('episode') or 0))
        year = item.get('year')
        return '%s %s' % (title, year) if year else title

    def accepts(self, release_name, item, media_type):
        """Filter a candidate against the thing the user actually asked for."""
        if media_type == 'episode':
            return parsing.matches_episode(
                release_name, item.get('show_title') or item.get('title'),
                item.get('season'), item.get('episode'))
        return parsing.matches_movie(release_name, item.get('title'),
                                     item.get('year'))

    # ---------------------------------------------------------------- flow
    def _collect(self, item, media_type):
        query = self.query_for(item, media_type)
        try:
            candidates = self.search(query, item, media_type) or []
        except Exception as exc:
            kodi.error('%s search failed: %s' % (self.id, exc))
            return []

        sources, seen_urls = [], set()
        for title, page_url in candidates[:20]:
            if not self.accepts(title or '', item, media_type):
                continue
            body = self.fetch(page_url)
            if not body:
                continue
            try:
                links = self.links(page_url, body, item) or []
            except Exception as exc:
                kodi.error('%s links failed on %s: %s' % (self.id, page_url, exc))
                continue
            for name, url in links:
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                if self._resolvable_only and not RESOLVER.playable(url):
                    continue
                release = name or title or ''
                quality, info, size = parsing.describe(release)
                sources.append(Source(
                    url=url,
                    name=parsing.clean_release(release) or host_of(url),
                    quality=quality,
                    info=' \u2022 '.join(x for x in (info, host_of(url)) if x),
                    size=size,
                    direct=False,
                    hoster=host_of(url),
                ))
        kodi.log('%s: %d sources for %s' % (self.id, len(sources), query))
        return sources

    def movie(self, item):
        return cache.cached(self.page_ttl, 'scrape_%s_movie' % self.id,
                            lambda i: self._collect(i, 'movie'),
                            {'id': item.get('id'), 'title': item.get('title'),
                             'year': item.get('year')}) or []

    def episode(self, item):
        key = {'id': item.get('id'), 'season': item.get('season'),
               'episode': item.get('episode')}
        return cache.cached(self.page_ttl, 'scrape_%s_episode' % self.id,
                            lambda i: self._collect(item, 'episode'), key) or []

    def resolve(self, source):
        """Let The Alamo's normal ResolveURL path handle it."""
        return None
