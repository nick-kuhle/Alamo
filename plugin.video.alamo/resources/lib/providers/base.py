# -*- coding: utf-8 -*-
"""Provider API for The Alamo.

The Alamo itself never scrapes anything. Everything playable comes from a
*provider*: a small Python module that returns a list of ``Source`` objects
for a movie, an episode, or a sports event.

A provider can live in two places:

1. ``userdata/addon_data/plugin.video.alamo/providers/<name>.py`` (drop-in file)
2. any installed Kodi add-on whose id starts with ``script.alamo.provider.``
   (the registry imports ``<addon>/provider.py``)

In both cases the module must expose::

    def get_provider():
        return MyProvider()

and the class should subclass :class:`Provider`.
"""


class Source(dict):
    """One playable candidate.

    Fields
    ------
    url       : link to play, or a hoster page ResolveURL understands
    provider  : provider id (filled in automatically)
    name      : release / stream name shown to the user
    quality   : one of 4K, 1080p, 720p, SD, CAM
    info      : extra tags, e.g. "HEVC - 10bit - 5.1"
    size      : size in GB (float, 0 if unknown)
    direct    : True when ``url`` can be handed straight to the player
    debrid    : name of the debrid service if the link is already resolved
    language  : ISO language code, default 'en'
    headers   : optional dict of HTTP headers required for playback
    """

    DEFAULTS = {
        'url': '', 'provider': '', 'name': '', 'quality': 'SD', 'info': '',
        'size': 0.0, 'direct': False, 'debrid': '', 'language': 'en',
        'headers': None,
    }

    def __init__(self, **kwargs):
        data = dict(self.DEFAULTS)
        data.update(kwargs)
        super(Source, self).__init__(**data)

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)


class SportsEvent(dict):
    """One sports item: a live event, a replay or a 24/7 channel."""

    DEFAULTS = {
        'id': '', 'title': '', 'league': '', 'start': '', 'thumb': '',
        'fanart': '', 'plot': '', 'live': False, 'url': '', 'provider': '',
    }

    def __init__(self, **kwargs):
        data = dict(self.DEFAULTS)
        data.update(kwargs)
        super(SportsEvent, self).__init__(**data)


class Provider(object):
    """Base class every provider should extend."""

    #: unique short id, e.g. 'myplaylist'
    id = 'unnamed'
    #: pretty name shown in settings and next to sources
    name = 'Unnamed provider'
    version = '1.0.0'
    #: lower sorts first when two sources look equally good
    priority = 50
    #: what this provider can do: any of 'movie', 'episode', 'sports'
    capabilities = ()

    # -- lookups ----------------------------------------------------------
    def movie(self, item):
        """Return a list of :class:`Source` for a movie dict from tmdb."""
        return []

    def episode(self, item):
        """Return a list of :class:`Source` for an episode dict."""
        return []

    def sports_categories(self):
        """Return a list of ``{'id':.., 'title':.., 'thumb':..}`` rows."""
        return []

    def sports_events(self, category_id):
        """Return a list of :class:`SportsEvent` for a category."""
        return []

    def sports_sources(self, event):
        """Return a list of :class:`Source` for a sports event."""
        if event.get('url'):
            return [Source(url=event['url'], name=event.get('title', ''),
                           quality='HD', direct=False)]
        return []

    # -- optional ---------------------------------------------------------
    def resolve(self, source):
        """Optionally turn a source into a final playable url.

        Return ``None`` to let The Alamo hand the link to ResolveURL.
        """
        return None

    def ping(self):
        """Return True when the provider is configured and usable."""
        return True

    def __repr__(self):
        return '<Provider %s %s>' % (self.id, self.version)
