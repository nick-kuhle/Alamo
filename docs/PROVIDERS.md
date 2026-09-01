# Writing a provider for The Alamo

A provider is a Python module with one required function:

```python
def get_provider():
    return MyProvider()
```

## Where providers live

| Location | Use it for |
|---|---|
| `userdata/addon_data/plugin.video.alamo/providers/<name>.py` | quick, personal providers - just drop the file in |
| a Kodi add-on with id `script.alamo.provider.<name>`, containing `provider.py` (or `lib/provider.py`) | shareable/installable providers, with their own settings |

Both are discovered at start-up. `Settings → Providers → Show installed
providers` lists what The Alamo found.

## The class

```python
from resources.lib.providers.base import Provider, Source, SportsEvent

class MyProvider(Provider):
    id = 'myprovider'            # unique, short
    name = 'My Provider'         # shown next to each source
    version = '1.0.0'
    priority = 50                # lower wins ties
    capabilities = ('movie', 'episode', 'sports')

    def movie(self, item):       # item = TMDB movie dict
        return [Source(url='https://host/x', name='Title 1080p WEB',
                       quality='1080p', size=4.2)]

    def episode(self, item):     # item has season/episode/show_title
        return []

    # sports -----------------------------------------------------------
    def sports_categories(self):
        return [{'id': 'nfl', 'title': 'NFL', 'thumb': 'https://...'}]

    def sports_events(self, category_id):
        return [SportsEvent(id='1', title='Chiefs @ Bills', league='nfl',
                            live=True, url='https://host/stream.m3u8',
                            thumb='https://...')]

    def sports_sources(self, event):
        return [Source(url=event['url'], quality='HD', direct=True)]

    # optional ---------------------------------------------------------
    def resolve(self, source):
        """Return a final url, or None to let ResolveURL handle it."""
        return None

    def ping(self):
        """Return False to hide the provider until it is configured."""
        return True
```

Declare only the capabilities you implement — The Alamo only calls capable
providers, and it calls them all in parallel with a timeout
(`Settings → General → Provider timeout`).

## What `item` contains

**Movies**

```python
{'id': 693134, 'type': 'movie', 'title': 'Dune: Part Two', 'year': '2024',
 'original_title': ..., 'imdb': 'tt15239678', 'premiered': '2024-02-27',
 'plot': ..., 'rating': 8.2, 'genres': ['Science Fiction', 'Adventure'],
 'runtime': 167, 'poster': ..., 'fanart': ...}
```

**Episodes**

```python
{'id': 1399, 'type': 'episode', 'show_title': 'Game of Thrones',
 'title': 'Winter Is Coming', 'season': 1, 'episode': 1, 'year': '2011',
 'premiered': '2011-04-17', 'imdb': 'tt0944947', 'tvdb': 121361, ...}
```

Use `imdb`/`tvdb` when your backend is keyed on them, otherwise
`title` + `year` (+ `season`/`episode`).

## The `Source` fields

| Field | Meaning |
|---|---|
| `url` | direct stream, or a hoster page ResolveURL understands |
| `name` | release name shown in the list |
| `quality` | `4K`, `1080p`, `720p`, `SD`, `CAM` (guessed from `name` when omitted) |
| `size` | size in GB, float, used for sorting |
| `direct` | `True` when the url can be handed to the player as-is |
| `debrid` | name of the service if it is already resolved (sorted higher) |
| `headers` | dict of HTTP headers required for playback |
| `info` | free-text tags, e.g. `HEVC · 10bit · 5.1` |

Ranking is: quality (capped by the user's max-quality setting) → debrid →
direct → size → provider priority. With *Autoplay best stream* on, the top
source plays immediately; otherwise the user picks from the sources window.

## Sports without a provider

The built-in **playlist provider** covers most cases without any code. Point
`Settings → Providers → Playlist URL` at either an M3U:

```
#EXTM3U
#EXTINF:-1 tvg-logo="https://x/nfl.png" group-title="NFL",Red Zone
https://host/redzone.m3u8
```

or an Alamo JSON guide:

```json
{
  "categories": [{"id": "nfl", "title": "NFL", "thumb": "https://x/nfl.png"}],
  "events": [
    {"id": "1", "category": "nfl", "title": "Chiefs @ Bills",
     "start": "2026-09-07T20:20:00Z", "live": true,
     "thumb": "https://x/game.jpg", "url": "https://host/game.m3u8"}
  ]
}
```

`group-title` becomes the league tile, `tvg-logo` becomes its artwork, and the
playlist is re-read on the interval set in settings.

## Debugging

* `Settings → Providers → Show installed providers` — confirms discovery.
* Kodi log lines are prefixed `[plugin.video.alamo]`; loader failures are logged
  with the file path and exception.
* An exception inside a provider never breaks a scan — it is logged and the
  other providers still return.
