# -*- coding: utf-8 -*-
"""HTTP layer shared by every scraper.

Retries, timeouts, a believable user agent, gzip, cookie reuse and a response
cache - the boring things that make scraping stable instead of flaky.
"""
import time
import random
import threading

import requests
from requests.adapters import HTTPAdapter

from .. import kodi
from .. import cache

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 '
    '(KHTML, like Gecko) Version/17.4 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
]

DEFAULT_TIMEOUT = 15
_LOCAL = threading.local()

#: pages that are really "you are being blocked"
BLOCK_MARKERS = ('cf-browser-verification', 'Just a moment...',
                 'DDoS protection by', 'Checking your browser before',
                 'Attention Required! | Cloudflare')


class Blocked(Exception):
    """The site answered, but with a bot wall rather than content."""


def session():
    """One pooled session per thread - scrapers run concurrently."""
    existing = getattr(_LOCAL, 'session', None)
    if existing is not None:
        return existing
    new = requests.Session()
    adapter = HTTPAdapter(pool_connections=8, pool_maxsize=16, max_retries=0)
    new.mount('http://', adapter)
    new.mount('https://', adapter)
    new.headers.update({
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
    })
    _LOCAL.session = new
    return new


def get(url, params=None, headers=None, timeout=DEFAULT_TIMEOUT, retries=2,
        referer=None, allow_redirects=True, ttl=0):
    """GET a page. Returns the body as text, or '' on failure.

    ``ttl`` > 0 caches the body, which keeps repeat scrapes of the same title
    (very common while browsing) off the network entirely.
    """
    if ttl:
        hit = cache.get('http', url, params, ttl)
        if hit is not None:
            return hit

    request_headers = dict(headers or {})
    if referer:
        request_headers['Referer'] = referer

    last_error = None
    for attempt in range(retries + 1):
        try:
            response = session().get(url, params=params, headers=request_headers,
                                     timeout=timeout,
                                     allow_redirects=allow_redirects)
            if response.status_code in (403, 429, 503):
                raise Blocked('HTTP %s' % response.status_code)
            response.raise_for_status()
            body = response.text
            if any(marker in body[:4000] for marker in BLOCK_MARKERS):
                raise Blocked('bot wall')
            if ttl:
                cache.put(body, ttl, 'http', url, params, ttl)
            return body
        except Blocked as exc:
            kodi.log('blocked by %s (%s)' % (url, exc))
            return ''
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.4 * (attempt + 1))
    kodi.log('GET failed %s: %s' % (url, last_error))
    return ''


def get_json(url, params=None, headers=None, timeout=DEFAULT_TIMEOUT, ttl=0):
    if ttl:
        hit = cache.get('http_json', url, params, ttl)
        if hit is not None:
            return hit
    try:
        response = session().get(url, params=params, headers=headers or {},
                                 timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        kodi.log('GET json failed %s: %s' % (url, exc))
        return {}
    if ttl and data:
        cache.put(data, ttl, 'http_json', url, params, ttl)
    return data


def head_size(url, timeout=8):
    """Content length in GB, 0 when unknown. Used for ranking."""
    try:
        response = session().head(url, timeout=timeout, allow_redirects=True)
        length = int(response.headers.get('Content-Length') or 0)
        return round(length / float(1024 ** 3), 2) if length else 0.0
    except Exception:
        return 0.0


def absolute(base, link):
    """Turn a possibly relative href into an absolute url."""
    if not link:
        return ''
    if link.startswith(('http://', 'https://')):
        return link
    if link.startswith('//'):
        return 'https:' + link
    if link.startswith('/'):
        return base.rstrip('/') + link
    return base.rstrip('/') + '/' + link
