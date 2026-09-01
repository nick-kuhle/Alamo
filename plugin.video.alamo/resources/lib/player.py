# -*- coding: utf-8 -*-
"""Source ranking + ResolveURL integration + playback."""
import re

import xbmc
import xbmcgui
import xbmcplugin

from . import kodi

QUALITY_ORDER = {'4K': 0, '1080p': 1, '720p': 2, 'SD': 3, 'CAM': 4}
QUALITY_PATTERNS = [
    ('4K', r'(2160p|4k|uhd)'),
    ('1080p', r'(1080p|1080i|fhd)'),
    ('720p', r'(720p|hd\b)'),
    ('CAM', r'(\bcam\b|camrip|hdcam|ts\b|telesync)'),
]


def guess_quality(name):
    text = (name or '').lower()
    for label, pattern in QUALITY_PATTERNS:
        if re.search(pattern, text):
            return label
    return 'SD'


def max_quality_filter(sources):
    """Drop anything above/below the user's quality preferences."""
    cap = kodi.setting('max_quality', '1080p')
    allow_cam = kodi.setting_bool('allow_cam', False)
    cap_rank = QUALITY_ORDER.get(cap, 1)
    out = []
    for source in sources:
        quality = source.get('quality') or guess_quality(source.get('name'))
        source['quality'] = quality
        if quality == 'CAM' and not allow_cam:
            continue
        if QUALITY_ORDER.get(quality, 3) < cap_rank:
            continue
        out.append(source)
    return out


def sort_sources(sources):
    def key(source):
        return (
            QUALITY_ORDER.get(source.get('quality', 'SD'), 3),
            0 if source.get('debrid') else 1,
            0 if source.get('direct') else 1,
            -float(source.get('size') or 0),
            source.get('provider', ''),
        )
    return sorted(sources, key=key)


def prepare(sources):
    return sort_sources(max_quality_filter(sources))


# --------------------------------------------------------------------------
# resolving
# --------------------------------------------------------------------------

def _resolveurl():
    try:
        import resolveurl
        return resolveurl
    except ImportError:
        return None


def resolvable(url):
    module = _resolveurl()
    if not module:
        return False
    try:
        return bool(module.HostedMediaFile(url=url).valid_url())
    except Exception:
        return False


def resolve(source):
    """Turn a source into a final playable url (or '' on failure)."""
    url = source.get('url') or ''
    if not url:
        return ''

    provider_id = source.get('provider')
    if provider_id:
        from .providers import registry
        provider = registry.find(provider_id)
        if provider:
            try:
                custom = provider.resolve(source)
                if custom:
                    return custom
            except Exception as exc:
                kodi.error('provider resolve failed: %s' % exc)

    if source.get('direct') or url.startswith(('plugin://', 'rtmp', 'udp')):
        return url

    module = _resolveurl()
    if not module:
        kodi.notify('ResolveURL is not installed')
        return url
    try:
        media = module.HostedMediaFile(url=url)
        if media.valid_url():
            return module.resolve(url) or ''
    except Exception as exc:
        kodi.error('resolveurl failed: %s' % exc)
    return url


# --------------------------------------------------------------------------
# playback
# --------------------------------------------------------------------------

def build_listitem(source, meta):
    meta = meta or {}
    item = xbmcgui.ListItem(path=source.get('resolved') or source.get('url'),
                            label=meta.get('title', ''))
    art = {'thumb': meta.get('thumb', ''), 'poster': meta.get('poster', ''),
           'fanart': meta.get('fanart', ''), 'icon': meta.get('thumb', '')}
    item.setArt({k: v for k, v in art.items() if v})
    try:
        info = item.getVideoInfoTag()
        info.setTitle(meta.get('title', ''))
        info.setPlot(meta.get('plot', ''))
        if meta.get('year'):
            info.setYear(int(meta['year']))
        if meta.get('type') == 'episode':
            info.setSeason(int(meta.get('season') or 0))
            info.setEpisode(int(meta.get('episode') or 0))
            info.setTvShowTitle(meta.get('show_title', ''))
            info.setMediaType('episode')
        elif meta.get('type') == 'movie':
            info.setMediaType('movie')
    except Exception:
        pass
    headers = source.get('headers') or {}
    if headers:
        item.setProperty('inputstream.adaptive.stream_headers',
                         '&'.join('%s=%s' % kv for kv in headers.items()))
    url = source.get('resolved') or source.get('url') or ''
    if url.endswith('.m3u8') or '.m3u8?' in url:
        item.setMimeType('application/vnd.apple.mpegurl')
        item.setProperty('inputstream', 'inputstream.adaptive')
        item.setProperty('inputstream.adaptive.manifest_type', 'hls')
        item.setContentLookup(False)
    elif '.mpd' in url:
        item.setMimeType('application/dash+xml')
        item.setProperty('inputstream', 'inputstream.adaptive')
        item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
        item.setContentLookup(False)
    return item


def play(source, meta, handle=None):
    """Resolve and start playback. Returns True when something was played."""
    resolved = resolve(source)
    if not resolved:
        kodi.notify('Could not resolve that link')
        return False
    source['resolved'] = resolved
    item = build_listitem(source, meta)
    handle = kodi.HANDLE if handle is None else handle
    if handle and handle > 0:
        xbmcplugin.setResolvedUrl(handle, True, item)
    else:
        xbmc.Player().play(resolved, item)
    return True
