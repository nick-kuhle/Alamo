# The Alamo — Getting Started (a Kodi add-on, explained for a dev who's new to Kodi)

You know how to code; you just haven't shipped a Kodi add-on before. This walks
through the whole loop: mental model → TMDB key → get it running on your machine
→ edit/reload cycle → reading logs → publishing a repo so other people can
install it with one click.

Estimated time to "it's running on my TV": **about 30 minutes**.

---

## 0. The mental model (5 minutes that save you an hour)

A few things about Kodi that are unlike normal app dev:

**An add-on is just a folder with an `addon.xml`.** No compiler, no build step,
no bundler. Kodi scans its `addons/` directory at start-up, reads each
`addon.xml`, and that's the install. A "zip install" is literally Kodi
unzipping a folder into that directory.

**A "video plugin" is a script that runs and exits.** Every time the user opens
your add-on, Kodi launches Python, runs your entry point (`alamo.py`) with
`sys.argv = [plugin_url, handle, query_string]`, and expects you to either build
a list of items or resolve something to play. Then the process ends. There's no
long-running app object — that's why state lives in settings/JSON files rather
than in memory.

**Two ways to draw a screen.** The normal way is `xbmcplugin.addDirectoryItem(...)`
— you hand Kodi items and the *user's skin* decides how they look (that's the
generic Kodi list look). The other way is a **custom window**: you ship your own
XML layout and Kodi renders exactly that. The Alamo uses the second one — that's
what makes it look like Netflix instead of like Kodi. It costs more code, and
the trade-off is that you own the layout (`resources/skins/Default/1080i/*.xml`).

**Kodi versions have names.** Kodi 19 = Matrix, 20 = Nexus, 21 = Omega, 22 =
Piers. Add-ons declare compatibility via `<import addon="xbmc.python" version="3.0.1"/>`
in `addon.xml`. We target **Omega (21) and newer**.

**Three folders you'll live in** (see §3 for exact paths per OS):
- `addons/` — where add-ons are installed
- `userdata/addon_data/plugin.video.alamo/` — our settings, cache DB, My List, drop-in providers
- `kodi.log` — the log, your only real debugger at first

**One rule that trips everyone up:** Python modules are cached by the running
Kodi process. After editing code, *restarting Kodi* is the reliable way to see
changes. Yes, really. (§5 has the faster loop.)

---

## 1. Get a TMDB API key (2 minutes, free)

The Alamo gets every movie/TV poster, title, plot and season list from TMDB.
Without a key, Movies and TV are empty (Sports still works — it comes from your
providers).

1. Sign up at <https://www.themoviedb.org/signup> and verify the email.
2. Go to <https://www.themoviedb.org/settings/api>.
3. Click **Request an API Key** → **Developer** → accept the terms.
4. Fill the form. It's fine to be honest and boring:
   - Type of use: **Personal / Educational**
   - Application name: `The Alamo`, URL: your GitHub repo URL (or `http://localhost`)
   - Summary: "Personal Kodi add-on for browsing movie and TV metadata."
   Approval is instant.
5. Copy the **API Key (v3 auth)** — a 32-character hex string. That's the one we
   want (*not* the long "Read Access Token" JWT).

Keep it out of the repo. It goes into the add-on's settings at runtime.

---

## 2. Install Kodi 21 Omega (or 22)

Grab it from <https://kodi.tv/download>. Develop on your desktop (macOS,
Windows or Linux) — much faster than deploying to a TV box each time. A Fire
Stick / Shield / Pi is where you test *at the end*.

Then turn on two things inside Kodi:

- **Settings → System → Add-ons → Unknown sources → On.** Required for
  installing anything that isn't from the official repo. Accept the warning.
- **Settings → System → Logging → Enable debug logging → On.** Do this now; the
  first time something goes wrong you'll want it already on. (It also puts an
  FPS/debug overlay on screen — you can turn just the overlay off with
  *Enable debug logging* on and *Show FPS* off in some skins; the overlay is
  harmless.)

---

## 3. Where Kodi keeps its stuff

`<KODI_HOME>` is:

| OS | Path |
|---|---|
| **Windows** | `%APPDATA%\Kodi\` (paste that into Explorer) |
| **macOS** | `~/Library/Application Support/Kodi/` |
| **Linux** | `~/.kodi/` |
| **Android / Fire TV** | `/sdcard/Android/data/org.xbmc.kodi/files/.kodi/` |
| **LibreELEC** | `/storage/.kodi/` |

Inside it:

```
<KODI_HOME>/
├── addons/                                    installed add-ons (one folder each)
│   └── plugin.video.alamo/
├── userdata/
│   ├── addon_data/plugin.video.alamo/         our data:
│   │   ├── settings.xml                       (TMDB key, playlist URL, ...)
│   │   ├── alamo_cache.db                     TMDB response cache
│   │   ├── mylist.json  progress.json
│   │   └── providers/                         drop-in provider .py files
│   └── Database/Addons33.db                   Kodi's add-on registry (don't touch)
└── kodi.log                                   the log (macOS: ~/Library/Logs/kodi.log)
```

---

## 4. Install The Alamo (two ways — pick one)

### Way A — install the zip (what a normal user does; do this once to sanity-check)

The zip is already built at:

```
alamo/dist/plugin.video.alamo/plugin.video.alamo-1.0.0.zip
```

In Kodi: **Add-ons → the box icon (top-left) → Install from zip file** →
navigate to that file → OK. Wait for the "Add-on installed" toast.

It will warn about missing dependencies only if something's absent —
`script.module.requests` ships with Kodi, and **ResolveURL is optional** (§8).

Find it under **Add-ons → Video add-ons → The Alamo**.

### Way B — symlink your working copy (what you'll actually develop with)

Instead of re-zipping after every edit, point Kodi's `addons/` folder at your
git checkout:

```bash
# macOS
ln -s ~/code/alamo/plugin.video.alamo \
      ~/Library/Application\ Support/Kodi/addons/plugin.video.alamo

# Linux
ln -s ~/code/alamo/plugin.video.alamo ~/.kodi/addons/plugin.video.alamo
```

```powershell
# Windows (PowerShell as Administrator)
New-Item -ItemType SymbolicLink `
  -Path "$env:APPDATA\Kodi\addons\plugin.video.alamo" `
  -Target "C:\code\alamo\plugin.video.alamo"
```

Restart Kodi. It picks the folder up as a normal add-on, and now editing a file
in your editor *is* editing the installed add-on.

> If Kodi doesn't see it: the folder name must exactly equal the `id` in
> `addon.xml` (`plugin.video.alamo`), and `addon.xml` must be at its top level.

---

## 5. First run + the edit/reload loop

**Paste your TMDB key:** Add-ons → Video add-ons → *right-click* (or `C` / long-press)
on **The Alamo** → **Settings** → *General* → **TMDB API key**. Paste, OK.

Now open it. You should get the dark poster wall: rail on the left, hero at the
top, Trending Movies / Trending TV rows. Sports will say it needs a provider —
that's expected (§7).

**The loop:**

| You changed | What to do |
|---|---|
| Python in `resources/lib/` | Exit to the Kodi home screen and re-open the add-on. If behaviour looks stale, restart Kodi (module cache). |
| Window XML in `resources/skins/` | Regenerate with `python3 tools/build_skin.py`, then **restart Kodi**. |
| Textures/icons in `resources/media/` or `skins/Default/media/` | `python3 tools/make_media.py`, then restart Kodi (textures are cached hard). |
| `addon.xml` or `resources/settings.xml` | Restart Kodi. |

Two big speed-ups:

1. **Run Kodi from a terminal** so the log streams to stdout:
   `/Applications/Kodi.app/Contents/MacOS/Kodi` (macOS) or just `kodi` (Linux).
2. **Tail the log in a second window:**
   ```bash
   tail -f ~/Library/Logs/kodi.log | grep -i alamo     # macOS
   tail -f ~/.kodi/temp/kodi.log   | grep -i alamo     # Linux
   ```
   Every line we log is prefixed `[plugin.video.alamo]`. A Python traceback in
   your add-on shows up in that log — that's your stack trace.

Optional but nice: enable **Kodi's web interface** (Settings → Services →
Control → Allow remote control via HTTP) and you can restart/refresh from the
command line instead of the couch.

---

## 6. Run the tests without Kodi

You don't need Kodi to exercise most of the code — `tests/kodistubs.py` fakes
the `xbmc*` modules:

```bash
cd alamo
python3 tests/test_smoke.py        # 14 tests: cache, ranking, providers, routing
python3 -m compileall -q plugin.video.alamo && echo "syntax ok"
python3 tools/build_skin.py        # regenerate window XML
python3 tools/make_media.py        # regenerate textures/icons
python3 tools/build_repo.py        # package zips + repository into dist/
```

What the stubs *can't* test: the window classes and actual playback. Those need
real Kodi.

---

## 7. Give Sports something to show

The Alamo deliberately ships with no sources. The built-in provider reads a
playlist you point it at. To prove the pipeline end-to-end, make a file
`~/alamo-test.json`:

```json
{
  "categories": [
    {"id": "demo", "title": "Demo Channels", "thumb": ""}
  ],
  "events": [
    {"id": "1", "category": "demo", "title": "Big Buck Bunny (test stream)",
     "live": true,
     "url": "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"}
  ]
}
```

Add-on **Settings → Providers → Playlist URL or file** → `/Users/you/alamo-test.json`
(a local path works; so does an `http(s)://` URL, and so does a plain `.m3u8`
IPTV playlist where `group-title` becomes the league tile).

Open **Sports** → *Demo Channels* → the item plays. That confirms: provider
discovery → source collection → ranking → playback all work.

For Movies/TV playback you need a provider with `movie`/`episode` capability —
`script.alamo.provider.example/` is a working template, and `docs/PROVIDERS.md`
is the full API. That layer is intentionally yours to fill.

---

## 8. ResolveURL (optional)

If your providers return hoster *pages* rather than direct streams, install
`script.module.resolveurl` (it lives in third-party repos such as Gujal's). The
Alamo imports it lazily — if it's absent, direct links still play and hoster
links just get handed to the player as-is. Nothing crashes.

---

## 9. Put it in your repo

Create the empty repo on GitHub (no README/licence — we have files already),
then:

```bash
cd ~/code/alamo               # wherever you put the project
git init -b main
git add .
git commit -m "The Alamo v1.0.0 - Kodi add-on: Sports, TV, Movies"
git remote add origin git@github.com:nick-kuhle/Alamo.git
git push -u origin main
```

`.gitignore` already excludes `dist/`, `__pycache__/`, `.testprofile/` and the
`reference/` folder (that's The Crew's source, kept for research — **don't
publish it**).

Suggested layout on GitHub, which is also how most Kodi projects do it:

- `main` — the source (what you just pushed)
- `gh-pages` — the built repository (`dist/`), served as a static site

---

## 10. Publish an installable Kodi repository

This is what turns "here's a zip" into "add this source URL and get updates
forever". A Kodi repository is nothing but three static files on a web server:
`addons.xml`, `addons.xml.md5`, and the add-on zips in per-add-on folders.
`tools/build_repo.py` generates all of it.

1. Edit the top of `tools/build_repo.py`:
   ```python
   REPO_URL = 'https://nick-kuhle.github.io/Alamo/'      # trailing slash matters
   ```
2. Build and publish:
   ```bash
   python3 tools/build_repo.py
   git checkout --orphan gh-pages
   git rm -rf .          # clear the branch
   cp -r dist/* .
   touch .nojekyll       # stops GitHub Pages hiding files
   git add . && git commit -m "Publish repo 1.0.0"
   git push -u origin gh-pages
   ```
3. GitHub → repo **Settings → Pages** → Source: *Deploy from a branch* →
   Branch: `gh-pages` / `(root)` → Save. Wait a minute, then confirm
   `https://nick-kuhle.github.io/Alamo/addons.xml` loads in a browser.

Install path for you and anyone else, on any device:

1. **Settings → File manager → Add source → \<None\>** → type
   `https://nick-kuhle.github.io/Alamo/` → name it `alamo` → OK.
2. **Add-ons → Install from zip file → alamo → repository.alamo-1.0.0.zip**.
3. **Add-ons → Install from repository → The Alamo Repository → Video add-ons → The Alamo → Install.**

From then on, bumping `version` in `addon.xml`, re-running `build_repo.py` and
pushing `gh-pages` makes Kodi offer the update automatically.

### Shipping an update, in full

One command does the lot:

```bash
./tools/release.sh 1.0.2 "Fix the sources dialog"
```

It bumps `addon.xml`, appends to `changelog.txt`, regenerates the skin, runs the
tests, rebuilds `dist/`, commits, tags `v1.0.2` and pushes. CI takes it from
there: republishes `gh-pages`, cuts a GitHub Release with the zips attached, and
then **verifies the live `addons.xml` actually reports the new version** before
going green.

**Everything moves together, by design:**

| Artefact | Version | Kept in sync by |
|---|---|---|
| `plugin.video.alamo` zip | 1.0.2 | `addon.xml` (the source of truth) |
| `repository.alamo` zip | 1.0.2 | `build_repo.py` reads the plugin's version |
| `addons.xml` + `.md5` | 1.0.2 | rebuilt every run |
| `gh-pages` | 1.0.2 | CI publishes on **every push to main**, not just tags |
| GitHub Release | 1.0.2 | CI, on `v*` tags |

CI also warns if you push without bumping the version — republishing different
bytes under a version Kodi has already cached is the classic way to make an
update silently not arrive.

### Making Kodi actually notice an update

Kodi caches repository metadata and only auto-checks periodically, so after a
release:

1. **Add-ons → right-click *The Alamo Repository* → Check for updates**
   (this refreshes `addons.xml` — do this one first)
2. **Add-ons → right-click *The Alamo* → Update**, or *Information → Update →*
   pick the version
3. Still stuck? **Settings → System → Add-ons → Manage dependencies** shows real
   versions, and a Kodi restart clears the in-memory repo cache. As a last
   resort, install the new zip directly from
   `https://nick-kuhle.github.io/Alamo/plugin.video.alamo/`.

---

## 11. When something breaks

| Symptom | Cause / fix |
|---|---|
| Add-on doesn't appear after install | Folder name ≠ `addon.xml` id, or unknown sources is off. Check `kodi.log` for `Unable to load addon`. |
| "Dependencies not met" | A `<requires>` entry can't be found. Everything we require except ResolveURL ships with Kodi; if you added a dependency, it must exist in an installed repo. |
| Blank/black custom window | An XML error. Kodi logs `Unable to load window XML` with the filename. Re-run `python3 tools/build_skin.py` and check the log. |
| Missing textures (invisible buttons) | Texture filenames in the XML resolve against `resources/skins/Default/media/`. Re-run `make_media.py`, restart Kodi (texture cache). |
| Movies/TV empty | TMDB key missing/wrong. Log shows `tmdb request failed` or `bad-key`. |
| Nothing plays | No provider with that capability. Settings → Providers → *Show installed providers*. |
| Changes don't take effect | Restart Kodi. Then delete `__pycache__` in the add-on folder if you're really suspicious. |

Reading the log is the whole game: search for `plugin.video.alamo`, and for
`Traceback` right after it.

---

## 12. Your checklist

- [ ] TMDB v3 API key in hand
- [ ] Kodi 21+ installed, unknown sources on, debug logging on
- [ ] Add-on symlinked into `addons/` (dev) or zip installed (sanity check)
- [ ] TMDB key pasted into add-on settings; Movies/TV rows populate
- [ ] Test playlist configured; a Sports item plays end to end
- [ ] `python3 tests/test_smoke.py` green
- [ ] Fresh GitHub repo created, `main` pushed
- [ ] `REPO_URL` set, `dist/` published to `gh-pages`, source URL installs cleanly

When those are all ticked, the next real work is the provider layer
(`docs/PROVIDERS.md`) — that's the part only you can decide the shape of.
