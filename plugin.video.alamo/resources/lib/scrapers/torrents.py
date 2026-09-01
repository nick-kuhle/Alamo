# -*- coding: utf-8 -*-
"""Torrent, magnet and pack infrastructure.

The Alamo ships no torrent scrapers. This module exists so that anyone who
writes one has the hard parts already solved, because these are exactly the
parts every scraper in every Kodi add-on re-implements slightly differently
and slightly wrong.

What The Crew does, and what is fixed here
------------------------------------------
*Info hashes.* The Crew builds magnets with a bare
``magnet:?xt=urn:btih:{hash}&dn={name}`` and never normalises the hash. Real
indexers hand back base32 hashes, mixed case, and hashes already wrapped in a
magnet URI. Feed those to a debrid service unchanged and you get three cache
misses for one torrent. :func:`info_hash` accepts all of those forms and
:func:`normalise_hash` returns one canonical lowercase hex form.

*Deduplication.* The Crew dedupes by URL, so the same torrent found on four
indexers is offered to the user four times. :func:`dedupe` merges by info hash
and keeps the best-evidenced copy, summing seeders across indexers.

*Packs.* The Crew has ``filter_season_pack`` / ``filter_show_pack`` and
``pick_best_pack_file`` spread across a 1144-line utility module. Here pack
detection and file selection are one small, tested surface.

*Seeders.* Treated as an int everywhere, when indexers return ``''``, ``'-'``
and ``'1,234'``.
"""
import re
import base64
import binascii
import urllib.parse

from .base import Scraper
from ..providers import parsing

#: Public trackers appended to generated magnets. A magnet with no trackers is
#: useless to a client that is not DHT-only, and debrid services accept them.
DEFAULT_TRACKERS = (
    'udp://tracker.opentrackr.org:1337/announce',
    'udp://open.demonii.com:1337/announce',
    'udp://tracker.torrent.eu.org:451/announce',
    'udp://exodus.desync.com:6969/announce',
)

_HEX40 = re.compile(r'\b([a-fA-F0-9]{40})\b')
_BASE32 = re.compile(r'\b([a-zA-Z2-7]{32})\b')

VIDEO_EXT = ('.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv', '.ts', '.m2ts',
             '.mpg', '.mpeg', '.webm', '.ogv', '.flv', '.divx')

#: files inside a pack that are never the episode you asked for
PACK_JUNK = ('sample', 'trailer', 'extra', 'featurette', 'behind', 'bonus',
             'deleted', 'subs/', 'subpack', 'proof', 'screens')


# ---------------------------------------------------------------------------
# info hashes
# ---------------------------------------------------------------------------

def normalise_hash(value):
    """Return a canonical lowercase 40-char hex info hash, or ''.

    Accepts hex (any case) and base32, which is what a surprising number of
    indexers actually emit.
    """
    if not value:
        return ''
    value = str(value).strip()
    if _HEX40.fullmatch(value):
        return value.lower()
    if len(value) == 32 and _BASE32.fullmatch(value):
        try:
            raw = base64.b32decode(value.upper())
            return binascii.hexlify(raw).decode('ascii').lower()
        except Exception:
            return ''
    return ''


def info_hash(value):
    """Pull an info hash out of a magnet URI, a bare hash, or a URL."""
    if not value:
        return ''
    value = str(value).strip()

    direct = normalise_hash(value)
    if direct:
        return direct

    if value.lower().startswith('magnet:'):
        query = urllib.parse.urlparse(value).query
        for xt in urllib.parse.parse_qs(query).get('xt', []):
            if 'btih' in xt.lower():
                found = normalise_hash(xt.rsplit(':', 1)[-1])
                if found:
                    return found

    for pattern in (_HEX40, _BASE32):
        match = pattern.search(value)
        if match:
            found = normalise_hash(match.group(1))
            if found:
                return found
    return ''


def magnet(value, name='', trackers=DEFAULT_TRACKERS):
    """Build a magnet URI from a hash or an existing magnet.

    Idempotent: passing a magnet back in returns a normalised magnet rather
    than nesting garbage.
    """
    digest = info_hash(value)
    if not digest:
        return ''
    uri = 'magnet:?xt=urn:btih:%s' % digest
    if name:
        uri += '&dn=%s' % urllib.parse.quote_plus(str(name))
    for tracker in trackers or ():
        uri += '&tr=%s' % urllib.parse.quote_plus(tracker)
    return uri


def seeders(value):
    """Indexers report seeders as '', '-', 'n/a', '1,234' and 1234."""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return max(0, int(value))
    text = re.sub(r'[^\d]', '', str(value))
    return int(text) if text else 0


# ---------------------------------------------------------------------------
# dedupe
# ---------------------------------------------------------------------------

_QUALITY_ORDER = {'4K': 0, '1080p': 1, '720p': 2, 'SD': 3, 'CAM': 4}


def dedupe(sources):
    """Merge sources that are the same torrent found on different indexers.

    Keeps the entry with the best quality, then the largest known size, and
    sums seeders across indexers because that is genuinely more information
    than any single indexer had. Sources with no hash are passed through
    untouched but still deduped on exact URL.
    """
    by_hash = {}
    by_url = {}
    out = []

    for source in sources:
        digest = source.get('hash') or info_hash(source.get('url', ''))
        if not digest:
            url = source.get('url', '')
            if url and url in by_url:
                continue
            if url:
                by_url[url] = source
            out.append(source)
            continue

        source['hash'] = digest
        existing = by_hash.get(digest)
        if existing is None:
            by_hash[digest] = source
            out.append(source)
            continue

        existing['seeders'] = seeders(existing.get('seeders')) + \
            seeders(source.get('seeders'))
        better = (
            _QUALITY_ORDER.get(source.get('quality'), 5),
            -float(source.get('size') or 0),
        ) < (
            _QUALITY_ORDER.get(existing.get('quality'), 5),
            -float(existing.get('size') or 0),
        )
        if better:
            keep_seeders = existing['seeders']
            existing.clear()
            existing.update(source)
            existing['seeders'] = keep_seeders
    return out


# ---------------------------------------------------------------------------
# packs
# ---------------------------------------------------------------------------

#: Release names are dot-, underscore- or space-separated, interchangeably.
#: Using \s here is the classic bug: "Complete.Series" never matches.
_SEP = r'[\s._\-]'

_SEASON_PACK_RES = (
    re.compile(r'\bs(?P<s>\d{1,2})%s*(?:-|to|thru)%s*s?(?P<e>\d{1,2})\b'
               % (_SEP, _SEP), re.I),
    re.compile(r'\bseasons?%s*(?P<s>\d{1,2})%s*(?:-|to|thru)%s*(?P<e>\d{1,2})\b'
               % (_SEP, _SEP, _SEP), re.I),
    re.compile(r'\b(?:complete|full)%s+series\b' % _SEP, re.I),
    re.compile(r'\bseries%s+(?P<only3>\d{1,2})\b(?!%s*e\d)' % (_SEP, _SEP), re.I),
    re.compile(r'\bseasons?%s*(?P<only>\d{1,2})\b(?!%s*e\d)' % (_SEP, _SEP), re.I),
    re.compile(r'\bs(?P<only2>\d{1,2})\b(?!%s*e\d)' % _SEP, re.I),
)


def is_pack(name, season=None):
    """True when a release looks like a season or series pack.

    A pack is only useful if it plausibly *contains* the season we want, so
    when ``season`` is given we check the range rather than accepting any pack.
    """
    if not name:
        return False
    lowered = name.lower()
    if re.search(r's\d{1,2}[\s._-]*e\d{1,3}', lowered):
        return False          # a single episode, not a pack

    for pattern in _SEASON_PACK_RES:
        match = pattern.search(lowered)
        if not match:
            continue
        groups = match.groupdict()
        if season is None:
            return True
        want = int(season)
        if groups.get('s') and groups.get('e'):
            return int(groups['s']) <= want <= int(groups['e'])
        only = (groups.get('only') or groups.get('only2')
                or groups.get('only3'))
        if only:
            return int(only) == want
        return True           # "complete series"
    return False


def pick_file(files, season=None, episode=None, path_key='path',
              size_key='bytes'):
    """Choose the right file inside a pack.

    ``files`` is a list of dicts as debrid services return them. Returns the
    chosen dict, or None. Selection order:

    1. drop non-video and obvious junk (samples, extras, subs)
    2. when season/episode are given, require an exact SxxEyy style match
    3. otherwise take the largest remaining file
    """
    candidates = []
    for entry in files or []:
        path = str(entry.get(path_key) or '')
        lowered = path.lower()
        if not lowered.endswith(VIDEO_EXT):
            continue
        if any(junk in lowered for junk in PACK_JUNK):
            continue
        candidates.append(entry)

    if not candidates:
        return None

    if season is not None and episode is not None:
        matched = [e for e in candidates
                   if parsing.matches_episode_marker(
                       str(e.get(path_key) or ''), season, episode)]
        if not matched:
            return None
        candidates = matched

    return max(candidates, key=lambda e: float(e.get(size_key) or 0))


# ---------------------------------------------------------------------------
# the scraper base
# ---------------------------------------------------------------------------

class TorrentScraper(Scraper):
    """Base for indexer scrapers. Sets the torrent defaults and adds helpers.

    Subclasses implement :meth:`movie` / :meth:`episode` exactly as with
    :class:`~resources.lib.scrapers.base.Scraper`, but build results with
    :meth:`torrent_source`, which normalises the hash, builds a proper magnet
    and records seeders and pack status.
    """

    KIND = 'torrent'
    #: torrents are not directly playable; a debrid service must resolve them
    DEBRID_ONLY = True
    #: sources below this are dropped. 0 disables the check.
    MIN_SEEDERS = 1
    MAX_RESULTS = 20

    def torrent_source(self, name, url_or_hash, size=0.0, seeds=0,
                       season=None, episode=None, info=''):
        """Build a torrent :class:`Source`, or None if it fails the gates."""
        digest = info_hash(url_or_hash)
        count = seeders(seeds)
        if self.MIN_SEEDERS and count < self.MIN_SEEDERS and digest:
            return None

        url = magnet(digest, name) if digest else url_or_hash
        if not url:
            return None

        pack = is_pack(name, season)
        bits = [b for b in (info, '%d seeders' % count if count else '',
                            'PACK' if pack else '') if b]

        source = self.source(
            url, name,
            quality=parsing.quality(name),
            size=float(size or 0.0),
            direct=False,
            info=' | '.join(bits))
        source['hash'] = digest
        source['seeders'] = count
        source['pack'] = pack
        source['debrid_only'] = self.DEBRID_ONLY
        if season is not None:
            source['season'] = season
        if episode is not None:
            source['episode'] = episode
        return source

    def rank(self, sources):
        """Dedupe by hash first, then quality, size and seeders."""
        merged = dedupe([s for s in sources if s])
        order = _QUALITY_ORDER
        merged.sort(key=lambda s: (order.get(s.get('quality'), 5),
                                   -float(s.get('size') or 0),
                                   -seeders(s.get('seeders'))))
        return merged[:self.MAX_RESULTS]
