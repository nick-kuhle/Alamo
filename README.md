# The Alamo

A Kodi 21+ video add-on with exactly three things in it: **Sports, TV and Movies**.
Inspired by The Crew's structure, but stripped down to a fraction of the code and
wrapped in a custom, poster-first interface that behaves like Netflix or YouTube
rather than a wall of Kodi menu text.

```
alamo/
├── plugin.video.alamo/              the add-on
│   ├── addon.xml
│   ├── alamo.py                     entry point
│   └── resources/
│       ├── lib/
│       │   ├── kodi.py              tiny Kodi API wrapper
│       │   ├── cache.py             sqlite cache
│       │   ├── tmdb.py              all metadata (movies + TV)
│       │   ├── store.py             My List / Continue Watching
│       │   ├── player.py            ranking, ResolveURL, playback
│       │   ├── router.py            plugin:// routes for widgets
│       │   ├── app.py               section controller
│       │   ├── providers/           the pluggable source layer
│       │   │   ├── base.py          Provider / Source / SportsEvent API
│       │   │   ├── registry.py      discovery + parallel querying
│       │   │   └── playlist_provider.py   built-in M3U / JSON provider
│       │   └── ui/                  custom windows + list items
│       ├── skins/Default/1080i/     the four custom windows
│       ├── settings.xml
│       └── media/                   icon, fanart, nav icons
├── script.alamo.provider.example/   provider add-on template
├── tools/                           skin, media and repo generators
├── tests/                           headless tests (no Kodi needed)
└── docs/ui-preview.html             browser mockup of the interface
```

## The three sections

| Section | Where the browsing comes from | Where playback comes from |
|---|---|---|
| **Movies** | TMDB: Trending, Popular, In Theatres, Top Rated, Coming Soon + 16 genres | providers with the `movie` capability |
| **TV** | TMDB: Trending, On Today, Popular, Top Rated, Airing + 10 genres, full season/episode browsing | providers with the `episode` capability |
| **Sports** | league/category tiles from any provider with the `sports` capability (the built-in one reads your own M3U or JSON guide) | the same providers |

## The UI

Four custom windows, all generated from `tools/build_skin.py`:

* `alamo-home.xml` – hero backdrop bound to the focused tile + up to five horizontal poster rows (Continue Watching, Live & On Now, Trending Movies, Trending TV, Popular).
* `alamo-grid.xml` – the poster wall used by every browse, genre, search and sports list, with infinite scroll (the next TMDB page loads when you get within 12 tiles of the end).
* `alamo-detail.xml` – full-bleed fanart, clearlogo, Play / Trailer / My List, season rail + episode panel for TV, "More Like This" for movies.
* `alamo-sources.xml` – live "3/5 providers · 12 streams" progress while providers are queried in parallel, then a ranked list.

Text is deliberately minimal: tiles show artwork only, and the title/plot appear
in the hero panel for whatever is focused. Open `docs/ui-preview.html` in a
browser to see the layout without installing anything.

## Sources: nothing is built in

The Alamo ships with **no scrapers**. Everything playable arrives through a
provider, and the only provider included reads a playlist *you* configure.
See [docs/PROVIDERS.md](docs/PROVIDERS.md) for the API — a provider is one Python
file with a `get_provider()` function.

Resolution order for a chosen source: the provider's own `resolve()` → direct
playback if the link is direct → ResolveURL (optional dependency).

> **New to Kodi add-ons?** Start with
> **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)** — a step-by-step runbook
> covering the Kodi mental model, TMDB key, installing, the edit/reload loop,
> reading logs and publishing a repository.

## Install

**From the repository (recommended for end users)**

```bash
python3 tools/build_repo.py     # edit REPO_URL at the top first
```

Published at <https://nick-kuhle.github.io/Alamo/>. In Kodi: *Settings → File manager → Add
source →* your URL → *Add-ons → Install from zip →* `repository.alamo` →
*Install from repository → The Alamo Repository → Video add-ons → The Alamo*.

**Straight from a zip**

Install `dist/plugin.video.alamo/plugin.video.alamo-1.0.0.zip` with
*Install from zip file*.

## First run

1. Get a free TMDB v3 API key at themoviedb.org → Settings → API.
2. The Alamo → *Settings → General → TMDB API key*.
3. For Sports, put an M3U or JSON guide URL in *Settings → Providers*.
4. Optional: install `script.module.resolveurl` so hoster links resolve.

## Development

```bash
./tools/release.sh 1.0.2 "What changed"   # bump, test, build, tag, push - CI publishes
python3 tools/make_media.py     # regenerate every texture and icon
python3 tools/build_skin.py     # regenerate the four window XMLs
python3 tests/test_smoke.py     # 14 headless tests, Kodi stubbed out
python3 tools/build_repo.py     # package zips + repository
```

`tests/kodistubs.py` fakes `xbmc`, `xbmcgui`, `xbmcaddon`, `xbmcplugin` and
`xbmcvfs`, so the metadata, cache, ranking, provider and routing code can be run
and tested on a desktop. The window classes themselves can only be exercised
inside Kodi.

## Widgets and favourites

Skins can point straight at content:

```
plugin://plugin.video.alamo/?action=list&kind=trending_movies
plugin://plugin.video.alamo/?action=list&kind=on_today
plugin://plugin.video.alamo/?action=list&kind=mylist
plugin://plugin.video.alamo/?action=sports        (opens the custom UI)
```

## Legal

The Alamo is a browser and a player. It contains no content, no links and no
scrapers. What your providers return is your responsibility.
