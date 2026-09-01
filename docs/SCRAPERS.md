# Scrapers and sources

The Alamo separates **finding** links from **playing** them:

```
TMDB item ─► providers (parallel, isolated) ─► Source list
                                                   │
                                        rank ──────┤ quality cap, debrid,
                                                   │ direct, size, priority
                                                   ▼
                            provider.resolve() ─► direct? ─► ResolveURL ─► play
```

Three ways to add sources, easiest first.

---

## 1. A site config (no code)

Drop a JSON file into
`userdata/addon_data/plugin.video.alamo/providers/sites/`.
*Settings → Providers → Where do site configs go?* prints the exact path and
lists what loaded.

```json
{
  "id": "example",
  "name": "Example Site",
  "base": "https://example.com",
  "search_url": "https://example.com/?s={query}",
  "result_pattern": "<h2 class=\"post\"><a href=\"(?P<url>[^\"]+)\">(?P<title>[^<]+)</a>",
  "link_pattern": "<iframe[^>]+src=\"(?P<url>[^\"]+)\"",
  "movie_query": "{title} {year}",
  "episode_query": "{show} S{season:02d}E{episode:02d}",
  "capabilities": ["movie", "episode"],
  "require_resolvable": true,
  "cache_hours": 6,
  "priority": 50,
  "headers": {"Referer": "https://example.com/"}
}
```

| Key | Required | Notes |
|---|---|---|
| `id`, `name` | ✅ | `id` must be unique |
| `search_url` | ✅ | `{query}` url-encoded, `{query_plus}`, `{query_dash}` also available |
| `result_pattern` | ✅ | regex with named groups `url` and `title` |
| `link_pattern` | ❌ | regex with named group `url`. Omit it and every outbound link on the page is harvested |
| `movie_query` / `episode_query` | ❌ | `{title} {year} {show} {season} {episode}` |
| `capabilities` | ❌ | defaults to `["movie", "episode"]` |
| `require_resolvable` | ❌ | drop links ResolveURL can't play (default true) |
| `priority` | ❌ | lower sorts first on ties |

Patterns are Python regexes compiled with `re.I | re.S`. Relative hrefs are
resolved against `base`.

**The engine does the rest:** the release name from `title` is matched against
the requested movie/episode, quality/codec/audio/size are parsed out of it,
links are deduplicated, unsupported hosts are dropped, results are cached.

---

## 2. A Python provider (full control)

Subclass `HosterScraper` and implement two hooks. Put the file in
`.../providers/` or ship it as a `script.alamo.provider.*` add-on.

```python
from resources.lib.providers.scraper_base import HosterScraper

class MySite(HosterScraper):
    id = 'mysite'
    name = 'My Site'
    base_url = 'https://mysite.example'
    capabilities = ('movie', 'episode')

    def search(self, query, item, media_type):
        """-> [(release_name, page_url), ...]"""
        body = self.fetch('%s/search?q=%s' % (self.base_url, query))
        return re.findall(r'<a href="([^"]+)" class="r">([^<]+)</a>', body)

    def links(self, page_url, page_body, item):
        """-> [(name, hoster_url), ...]   empty name = reuse the release name"""
        return [('', url) for url in self.harvest(page_body)]

def get_provider():
    return MySite()
```

Useful inherited pieces:

| Member | Does |
|---|---|
| `self.fetch(url, **kw)` | cached GET with retries, UA, referer, bot-wall detection |
| `self.harvest(body)` | every plausible outbound video link, minus assets and social junk |
| `self.query_for(item, type)` | `"Heat 1995"` / `"Severance S02E03"` |
| `self.accepts(name, item, type)` | title/year/episode matching — override to loosen |
| `page_ttl`, `max_pages`, `require_resolvable` | knobs |

For something that isn't page scraping at all (a JSON API, a debrid cloud, a
local folder), subclass `Provider` directly and return `Source` objects — see
`archive_provider.py`.

---

## 3. What ships in the box

| Provider | Type | Content |
|---|---|---|
| **Internet Archive** (`archive_org`) | JSON API, direct MP4s | Public domain and freely licensed film — silent era, noir, classic sci-fi. Real, legal, and works with zero configuration |
| **My Playlist** (`playlist`) | M3U / JSON | Sports. Points at *your* playlist |

The Archive provider is the reference implementation: it does a real search,
filters out extras and same-titled home movies, reads pixel dimensions to get
quality right (Archive identifiers routinely claim 1080p for a 640×360 file),
and returns direct links needing no resolver.

---

## Matching, and why it's fussy

`providers/parsing.py` is the brain. It uses **containment**, not overlap:
`The.Batman.2022.1080p.WEB-DL.DDP5.1.x265` shares only a third of its tokens
with `The Batman`, but it *contains* all of the title — which is the question
that matters.

A movie release must clear three gates:

1. **Containment ≥ 0.8** — nearly all title words present
2. **≤ 2 extra title words** — `Batman Begins` is not `The Batman`
3. **Year within ±1** — `The.Batman.1966` is not the 2022 film

Episodes must match `SxxEyy` / `2x07` / `Season 2 Episode 7` exactly, and the
text before the marker must contain the show title.

Also handles: accents (`Amélie` → `amelie`), `&` → `and`, apostrophes, and a
noise list so `1080p`, `HEVC`, `RARBG` etc. never count as title words.

---

## Quality, ranking, playback

`parsing.describe(name)` returns `(quality, info, size)`:

- **quality** `4K` / `1080p` / `720p` / `SD` / `CAM`
- **info** source, codec, audio, HDR — `WEB-DL • HEVC • DDP5.1 • HDR`
- **size** GB, parsed from text or supplied by the provider

Sorting: quality (capped by *Maximum quality*) → debrid → direct → size →
provider priority. *Autoplay best stream* plays the top one; otherwise the
sources window lists them.

Relevant settings under **Providers**:

| Setting | Default |
|---|---|
| Internet Archive | on |
| Hide links ResolveURL cannot play | on |
| Stop after this many sources | 60 |
| Provider timeout | 45s |

---

## Debugging

```bash
tail -f ~/.kodi/temp/kodi.log | grep -i alamo
```

Each scraper logs `mysite: 12 sources for Heat 1995`. Failures are logged with
the provider id and never break the scan — one broken provider can't take the
others down.

Test parsing without Kodi:

```python
from resources.lib.providers import parsing
parsing.matches_movie('The.Batman.2022.1080p.WEB-DL', 'The Batman', '2022')  # True
parsing.describe('Dune.2024.2160p.WEB-DL.DDP5.1.Atmos.HDR.HEVC')
# ('4K', 'WEB-DL • HEVC • Atmos • HDR', 0.0)
```

`python3 tests/test_smoke.py` covers parsing, the scraper flow end to end
against a fake site, config scrapers and the Archive provider.

---

## A note on what you point this at

The engine is deliberately source-agnostic and ships with nothing pointed at
anyone's site. What you add in `sites/` is your call and your responsibility —
The Alamo hosts nothing, bundles no links, and has no scrapers targeting
copyrighted content built in.

---

# Built-in scrapers (hand-written)

Alongside the JSON site-config engine, Alamo ships **hand-written Python
scrapers** in `resources/lib/scrapers/`. This is the same approach The Crew
takes, with its structural weaknesses removed.

## Writing one

Drop a file in `resources/lib/scrapers/`. Discovery is automatic.

```python
from .base import Scraper, quality_for

class MySite(Scraper):
    ID          = 'mysite'
    NAME        = 'My Site'
    KIND        = 'free'        # free | debrid | torrent
    PRIORITY    = 30            # lower runs and sorts first
    CAPABILITIES = ('movie', 'episode')
    TIMEOUT     = 20
    ATTRIBUTION = 'My Site - public domain'

    def movie(self, item):
        data = self.get_json(API % item['title'])
        for hit in data['results']:
            if not self.accepts(hit['title'], item):
                continue
            yield self.source(hit['url'], hit['title'],
                              quality=quality_for(hit['w'], hit['h']),
                              size=hit['bytes'] / 1024.0 ** 3)

def get_scraper():
    return MySite()
```

`item` has `title`, `year`, and for episodes `show`, `season`, `episode`.
Return or yield `Source` objects. **Raising is fine** — the bridge isolates the
failure and records it in the scan report.

## What you get for free

| Inherited | What it does |
|---|---|
| `accepts(title, item)` | The full title gate — junk words, containment, leading/trailing word rules, year tolerance |
| `source(...)` | Builds a `Source` with your identity attached |
| `rank(sources)` | Quality then size, trimmed to `MAX_RESULTS` |
| `get` / `get_json` | Pooled sessions, retries, UA rotation, bot-wall detection, caching |
| error isolation | One dead site never kills a scan |

## Three ways this differs from The Crew

**1. Metadata is declared, not grepped.** The Crew's `provider_settings_sync.py`
decides whether a scraper is torrent or debrid by regex-searching the scraper's
own source code for `'source': 'torrent'` and `'debridonly': True`. Any scraper
written in a different style is silently misclassified. Here `KIND`, `PRIORITY`
and `CAPABILITIES` are class attributes, and a test asserts every scraper
declares them.

**2. Title matching lives in one place.** In The Crew each of the 37 scrapers
implements its own title check, so fixing one fixes one. `Scraper.accepts()` is
inherited by all of ours. Every rule in it was forced on us by a real API
response:

- **junk words** — searching *The Kid (1921)* returns four featurettes first
- **containment ≥ 0.8, asymmetric** — a release name is far longer than a
  title, so symmetric overlap scores `The.Batman.2022.1080p.WEB-DL` against
  `The Batman` at 0.33 and rejects the correct result
- **leading words ≤ 1** — drops *The Wolf and The Kid* and
  *Beulah Bains In The Kid* when you searched for *The Kid*
- **trailing words ≤ 3, brackets stripped** — keeps
  *Nosferatu (1922, English titles 1947)*, drops
  *Night of the Living Dead - Ten Minutes to Three*, which is a clip

**3. Failures are visible.** Every scan records per-scraper counts, timings and
errors. See them in *Settings > Sources > Last source scan*. When a site dies
you learn which one, instead of just getting fewer results.

## Never trust a filename for quality

Use `quality_for(width, height, name)`. Archives routinely serve a 640x360
derivative from an item called `Night.Of.The.Living.Dead_1080p`. Pixel
dimensions win; the filename is only a fallback.

## Shipped scrapers

| Scraper | Source | Notes |
|---|---|---|
| `wikimedia` | Wikimedia Commons | Public-domain features as direct webm/mp4. Verified live: *His Girl Friday* returns a 4K/5 GB source |
| `loc` | Library of Congress | National Screening Room + site-wide film search. Direct MP4, real pixel height and duration in the search response |
| `archive` | Internet Archive | Provider-style; predates this layer |
