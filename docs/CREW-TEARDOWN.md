# How The Crew's source engine works, and where Alamo diverges

A structural read of `script.module.thecrew` (the reference copy in
`/home/user/reference`, never published), and the reasoning behind each place
Alamo does it differently. No site-specific logic is reproduced here — this is
about plumbing.

## Their shape

```
script.module.thecrew/lib/resources/lib/
  scrapers/
    base.py            316 lines   BaseScraper: sources(), check_title(), _request()
    torrent_base.py    435 lines   magnets, sizes, seeders, pack filtering
    <37 site modules>            one per indexer/hoster
  modules/
    sources.py        6232 lines   the aggregator: threads, debrid, filter, sort, UI
    source_utils.py   1144 lines   quality, sizes, aliases, packs, host validation
    client.py          943 lines   HTTP + cfscrape
    cache.py          1412 lines   sqlite caching
    debrid*.py         6 modules   RD / Premiumize / AllDebrid / TorBox
```

The entry point every scraper implements:

```python
def sources(self, data, hostDict, hostprDict):
```

`data` is the media dict (title, year, imdb, season, episode, **aliases**).
`hostDict` / `hostprDict` are ResolveURL's lists of supported free and premium
hosts, computed **once** by the aggregator and injected, so 37 scrapers don't
each rebuild them. That injection is a genuinely good idea and Alamo does the
same thing lazily in `scraper_base._ResolveURL`.

### The flow

1. `sources.py` builds `hostDict`/`hostprDict` and the media dict, including
   alternate titles from Trakt/TMDB.
2. Every enabled scraper is dispatched onto a thread pool.
3. Each scraper searches its site, filters by `check_title(...)`, and appends
   dicts to `self._sources_list`.
4. The aggregator filters (quality ceiling, size limits, debrid-only, host
   validity), sorts, and renders.
5. On play, torrents go to a debrid service; hoster links go to ResolveURL.

The source dict is the contract, and it is a good one:

```python
{'provider','source','quality','language','url','info','direct',
 'debridonly','name','seeders','hash','size','season','episode'}
```

Alamo's `Source` is deliberately close to this. Interoperability with the
mental model most Kodi scraper authors already have is worth more than a
prettier schema.

---

## Six things they get right

1. **Injected host dictionaries.** Compute the ResolveURL whitelist once.
2. **A source dict, not a class hierarchy.** Trivially serialisable, cacheable.
3. **`debridonly` as a first-class flag.** A magnet is not playable; the schema
   says so rather than failing at playback.
4. **Aliases threaded through every title check.** Without them, every
   non-English release is invisible.
5. **Pack awareness.** A season pack is a legitimate source *if* you can pick
   the right file out of it.
6. **Per-scraper error isolation.** One dead site never kills a scan.

## Six things they get wrong, and what Alamo does instead

### 1. Metadata inferred by grepping source code

`provider_settings_sync.py` decides whether a scraper is torrent, debrid or
free by regex-searching **the scraper's own Python source text**:

```python
if re.search(r"['\"]source['\"]\s*:\s*['\"]torrent['\"]", source):
    return 'torrent'
if re.search(r"['\"]debridonly['\"]\s*:\s*True", source):
    return 'debrid'
```

Write a scraper that builds its dict differently — via a helper, or with
`debridonly=True` as a kwarg — and it is silently misfiled, which puts its
on/off toggle in the wrong settings category.

**Alamo:** `KIND`, `PRIORITY`, `CAPABILITIES` are declared class attributes,
and `test_metadata_is_declared_not_guessed` fails the build if a scraper omits
them.

### 2. Title matching duplicated 37 times

`BaseScraper.check_title()` exists, but scrapers also call
`source_utils.check_title()`, `_matches_release()`, `_matches_search_result()`
and hand-rolled comparisons. Fixing a matching bug fixes one call site.

**Alamo:** one inherited `Scraper.accepts()`. Every rule in it was forced by a
real API response, and each is pinned by a test:

| Rule | Why |
|---|---|
| junk words | *The Kid (1921)* returns four featurettes before the film |
| containment ≥ 0.8, **asymmetric** | symmetric overlap scores `The.Batman.2022.1080p.WEB-DL` vs `The Batman` at 0.33 and rejects the right answer |
| leading words ≤ 1 | drops *The Wolf and The Kid*, *Beulah Bains In The Kid* |
| trailing words ≤ 3, brackets stripped | keeps *Nosferatu (1922, English titles 1947)*, drops *Night of the Living Dead - Ten Minutes to Three* |
| aliases | *Le Fabuleux Destin d'Amelie Poulain* matches a search for *Amelie* |

### 3. Dead sites cost you forever

A site that dies stays in the rotation until a maintainer hand-sets
`defunct=True` and ships a release. Until then every user pays that site's full
timeout on every scan.

**Alamo:** a circuit breaker. Three consecutive failures trips a scraper; it is
skipped for 30 minutes, then gets one probe to recover. State persists in
`scraper_health.json`. No release required, no maintainer in the loop.

### 4. The timeout is per-thread, not per-scan

This pattern appears in The Crew and appeared in Alamo until v1.0.6:

```python
for thread in threads:
    thread.join(timeout)
```

Joining *each* thread with the *full* timeout means N slow scrapers stall for
N × timeout. Twelve providers at 45 s is **nine minutes**.

**Alamo:** one shared deadline for the whole scan. The user asked to wait 45
seconds, so 45 seconds is the budget.

### 5. Deduplication by URL

The same torrent found on four indexers is four rows in the list, and four
separate cache lookups against your debrid service.

**Alamo:** `torrents.dedupe()` merges on **info hash**, keeps the
best-evidenced copy, and *sums seeders across indexers* — which is real
information no single indexer had.

### 6. Info hashes taken at face value

`_build_magnet()` does `f'magnet:?xt=urn:btih:{info_hash}'` with no
normalisation. Indexers emit base32, mixed case, and hashes already inside a
magnet URI. Those are three cache misses for one torrent.

**Alamo:** `torrents.info_hash()` accepts hex, base32, magnet URIs and hashes
embedded in URLs, and always returns one canonical lowercase hex form.
`magnet()` is idempotent and appends trackers.

---

## The toolkit Alamo gives a scraper author

Alamo ships **no** torrent or hoster scrapers. It ships the parts that are
tedious and easy to get wrong, so a new scraper is mostly site logic.

```python
from .torrents import TorrentScraper

class MyIndexer(TorrentScraper):
    ID, NAME = 'myindexer', 'My Indexer'
    MIN_SEEDERS = 5

    def movie(self, item):
        for row in self.get_json(API % item['title'])['results']:
            if not self.accepts(row['name'], item):
                continue
            yield self.torrent_source(row['name'], row['hash'],
                                      size=row['gb'], seeds=row['seeders'])
```

Everything below is inherited:

| Concern | Provided by |
|---|---|
| hash normalisation, magnet building | `info_hash()`, `magnet()` |
| seeder parsing (`''`, `'-'`, `'1,234'`) | `seeders()` |
| dedupe across indexers | `dedupe()` |
| season/series pack detection | `is_pack()` |
| choosing the file inside a pack | `pick_file()` |
| title matching incl. aliases | `Scraper.accepts()` |
| HTTP pooling, retries, UA rotation, bot walls | `net.py` |
| ranking, capping | `rank()` |
| error isolation, breaker, diagnostics | the bridge and registry |

`pick_file()` deserves a note: inside a pack the show title is frequently
absent from the filename, so only the `SxxEyy` marker can be trusted. It drops
non-video files and junk (`sample`, `extras`, `subs/`), requires an exact
episode marker when season and episode are supplied, and otherwise takes the
largest remaining file.

## Still missing

Honest list of what The Crew has that Alamo does not:

- **Debrid account integration.** `torrents.py` produces correctly formed
  magnets and the `debrid_only` flag, but nothing resolves them yet. This is
  the next substantial piece of infrastructure.
- **Cached-availability checks.** The Crew queries a debrid service before
  showing a source, so uncached torrents can be hidden or de-prioritised.
- **Cloudflare bypass.** They bundle `cfscrape`. Alamo detects a bot wall and
  reports it rather than fighting it.
- **Progressive results.** The Crew streams sources into the UI as they
  arrive; Alamo waits for the scan to finish.
