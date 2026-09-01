# -*- coding: utf-8 -*-
"""Headless smoke tests. Run: python3 tests/test_smoke.py"""
import os
import re
import sys
import shutil
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kodistubs  # noqa: E402

kodistubs.install()

from resources.lib import cache, store, player, tmdb, router  # noqa: E402
from resources.lib.providers import base, registry  # noqa: E402
from resources.lib.providers import playlist_provider  # noqa: E402


class TestCache(unittest.TestCase):
    def test_roundtrip(self):
        cache.put({'a': 1}, 60, 'unit', 'k')
        self.assertEqual(cache.get('unit', 'k'), {'a': 1})

    def test_expiry(self):
        cache.put('x', -1, 'unit', 'expired')
        self.assertIsNone(cache.get('unit', 'expired'))


class TestStore(unittest.TestCase):
    def test_mylist_toggle(self):
        item = {'id': 1, 'type': 'movie', 'title': 'A'}
        self.assertTrue(store.toggle_mylist(item))
        self.assertTrue(store.in_mylist('movie', 1))
        self.assertFalse(store.toggle_mylist(item))
        self.assertFalse(store.in_mylist('movie', 1))

    def test_progress(self):
        store.clear_progress()
        store.note_play({'id': 5, 'type': 'movie', 'title': 'B'})
        self.assertEqual(len(store.progress()), 1)


class TestRanking(unittest.TestCase):
    def test_quality_guess(self):
        self.assertEqual(player.guess_quality('Movie.2160p.WEB'), '4K')
        self.assertEqual(player.guess_quality('Movie.1080p'), '1080p')
        self.assertEqual(player.guess_quality('Movie.HDCAM'), 'CAM')

    def test_sorting_and_filtering(self):
        sources = [
            base.Source(url='a', name='m 720p', size=1),
            base.Source(url='b', name='m 1080p', size=8),
            base.Source(url='c', name='m HDCAM'),
            base.Source(url='d', name='m 2160p', size=30),
        ]
        for source in sources:
            source['quality'] = player.guess_quality(source['name'])
        ranked = player.prepare(sources)
        # default cap is 1080p, so the 4K release and the CAM are dropped
        self.assertEqual([s['url'] for s in ranked], ['b', 'a'])
        kodistubs.SETTINGS['max_quality'] = '4K'
        kodistubs.SETTINGS['allow_cam'] = 'true'
        ranked = player.prepare(sources)
        self.assertEqual([s['url'] for s in ranked], ['d', 'b', 'a', 'c'])
        kodistubs.SETTINGS['max_quality'] = '1080p'
        kodistubs.SETTINGS['allow_cam'] = 'false'


class TestPlaylistProvider(unittest.TestCase):
    def setUp(self):
        self.provider = playlist_provider.PlaylistProvider()

    def test_m3u(self):
        m3u = ('#EXTM3U\n'
               '#EXTINF:-1 tvg-logo="http://x/l.png" group-title="NFL",Red Zone\n'
               'http://x/rz.m3u8\n'
               '#EXTINF:-1 group-title="NBA",League Pass\n'
               'http://x/lp.m3u8\n')
        categories, events = self.provider._parse_m3u(m3u)
        self.assertEqual(sorted(c['id'] for c in categories), ['nba', 'nfl'])
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]['url'], 'http://x/rz.m3u8')
        self.assertTrue(events[0]['live'])

    def test_json_guide(self):
        guide = ('{"categories":[{"id":"ufc","title":"UFC"}],'
                 '"events":[{"id":"1","category":"ufc","title":"UFC 320",'
                 '"url":"http://x/u.m3u8","live":true}]}')
        categories, events = self.provider._parse_json(guide)
        self.assertEqual(categories[0]['id'], 'ufc')
        self.assertEqual(events[0]['title'], 'UFC 320')
        self.assertEqual(self.provider.sports_sources(events[0])[0]['url'],
                         'http://x/u.m3u8')


class TestRegistry(unittest.TestCase):
    def test_collect_runs_in_parallel(self):
        class Fake(base.Provider):
            id, name, capabilities = 'fake', 'Fake', ('movie',)

            def movie(self, item):
                return [base.Source(url='http://x/1', name='fake 1080p')]

        registry._CACHE['providers'] = [Fake()]
        found = registry.collect('movie', {'title': 'X'})
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['provider'], 'fake')

    def test_broken_provider_is_survived(self):
        class Broken(base.Provider):
            id, name, capabilities = 'broken', 'Broken', ('movie',)

            def movie(self, item):
                raise ValueError('boom')

        registry._CACHE['providers'] = [Broken()]
        self.assertEqual(registry.collect('movie', {}), [])


class TestTMDBNormalise(unittest.TestCase):
    def test_movie(self):
        raw = {'id': 1, 'title': 'Heat', 'release_date': '1995-12-15',
               'overview': 'plot', 'vote_average': 8.3,
               'poster_path': '/p.jpg', 'backdrop_path': '/b.jpg'}
        item = tmdb.normalise(raw, 'movie')
        self.assertEqual(item['year'], '1995')
        self.assertEqual(item['rating'], 8.3)
        self.assertTrue(item['poster'].endswith('/p.jpg'))

    def test_tv_detection(self):
        item = tmdb.normalise({'id': 2, 'name': 'Show',
                               'first_air_date': '2020-01-01'})
        self.assertEqual(item['type'], 'tv')


class TestRouter(unittest.TestCase):
    def test_url(self):
        built = router.url(action='play', type='movie', id=42)
        self.assertIn('plugin://plugin.video.alamo/?', built)
        self.assertIn('action=play', built)

    def test_dispatch_clear_cache(self):
        router.dispatch(['plugin://plugin.video.alamo/', '1',
                         '?action=clear_cache'])


class TestBuiltinScrapers(unittest.TestCase):
    """The hand-written scraper layer. No network: gates and metadata only."""

    def setUp(self):
        from resources.lib import scrapers
        self.scrapers = scrapers
        self.found = scrapers.discover(refresh=True)

    def test_discovers_the_shipped_scrapers(self):
        ids = {s.ID for s in self.found}
        self.assertIn('wikimedia', ids)
        self.assertIn('loc', ids)

    def test_metadata_is_declared_not_guessed(self):
        """The Crew infers kind by grepping source text; we require it stated."""
        for scraper in self.found:
            self.assertTrue(scraper.ID, '%s has no ID' % scraper)
            self.assertTrue(scraper.NAME, '%s has no NAME' % scraper)
            self.assertIn(scraper.KIND, ('free', 'debrid', 'torrent'))
            self.assertTrue(scraper.CAPABILITIES)
            self.assertIsInstance(scraper.PRIORITY, int)

    def test_ids_are_unique(self):
        ids = [s.ID for s in self.found]
        self.assertEqual(len(ids), len(set(ids)))

    def test_shared_title_gate(self):
        """Every case here came from a real API response that fooled us."""
        from resources.lib.scrapers.base import Scraper
        gate = Scraper()
        item = lambda t, y: {'title': t, 'year': y}
        keep = [
            ('Night of the Living Dead (1968)', 'Night of the Living Dead', 1968),
            ('Night of the Living Dead (1968 film)', 'Night of the Living Dead', 1968),
            ('Nosferatu (1922, English titles 1947)', 'Nosferatu', 1922),
            ('The Kid (1921)', 'The Kid', 1921),
        ]
        drop = [
            # a clip, not the feature
            ('Night of the Living Dead - Ten Minutes to Three', 'Night of the Living Dead', 1968),
            ('The Kid scenes', 'The Kid', 1921),
            # different films that merely contain the wanted title
            ('The Wolf and The Kid (1921)', 'The Kid', 1921),
            ('Beulah Bains In The Kid', 'The Kid', 1921),
            # junk words
            ('Night Of The Living Dead (1968) - trailer', 'Night of the Living Dead', 1968),
        ]
        for title, wanted, year in keep:
            self.assertTrue(gate.accepts(title, item(wanted, year)),
                            'should keep %r' % title)
        for title, wanted, year in drop:
            self.assertFalse(gate.accepts(title, item(wanted, year)),
                             'should drop %r' % title)

    def test_resolution_beats_a_lying_filename(self):
        """Archives label 640x360 derivatives as _1080p. Pixels win."""
        from resources.lib.scrapers.base import quality_for
        self.assertEqual(quality_for(640, 360, 'Movie_1080p'), 'SD')
        self.assertEqual(quality_for(1920, 1080, 'whatever'), '1080p')
        self.assertEqual(quality_for(3840, 2160, ''), '4K')
        self.assertEqual(quality_for(0, 0, 'Movie.720p.WEB'), '720p')
        self.assertEqual(quality_for(0, 0, 'no hints here'), 'SD')

    def test_junk_detection(self):
        from resources.lib.scrapers.base import is_junk
        self.assertTrue(is_junk('The Kid - featurette'))
        self.assertTrue(is_junk('ok title', 'x_trailer.mp4'))
        self.assertFalse(is_junk('Night of the Living Dead'))

    def test_scan_report_records_and_sorts_failures_first(self):
        self.scrapers.begin_report()
        self.scrapers.record('a', 'Alpha', 5, 1.0)
        self.scrapers.record('b', 'Beta', 0, 0.2, 'boom')
        report = self.scrapers.last_report()
        self.assertEqual(report['sources'], 5)
        self.assertEqual(report['rows'][0]['id'], 'b')

    def test_bridge_exposes_scrapers_as_providers(self):
        from resources.lib.providers import scraper_bridge
        bridged = scraper_bridge.bridged()
        self.assertTrue(bridged)
        for provider in bridged:
            self.assertTrue(provider.id)
            self.assertTrue(hasattr(provider, 'movie'))
            self.assertTrue(provider.builtin)

    def test_a_raising_scraper_is_isolated_and_recorded(self):
        from resources.lib.providers import scraper_bridge
        from resources.lib.scrapers.base import Scraper

        class Exploding(Scraper):
            ID, NAME = 'boom', 'Exploding'

            def movie(self, item):
                raise RuntimeError('site is down')

        self.scrapers.begin_report()
        provider = scraper_bridge.ScraperProvider(Exploding())
        self.assertEqual(provider.movie({'title': 'x'}), [])
        rows = self.scrapers.last_report()['rows']
        self.assertTrue(any(r['error'] for r in rows))


class TestTorrentInfrastructure(unittest.TestCase):
    """Alamo ships no torrent scrapers; this is the toolkit for writing one."""

    HEX = 'C9E15763F722F23E98A29DECDFAE341B98D53056'
    LOW = HEX.lower()

    def setUp(self):
        from resources.lib.scrapers import torrents
        self.t = torrents

    def test_info_hash_accepts_every_form_indexers_emit(self):
        self.assertEqual(self.t.info_hash(self.HEX), self.LOW)
        self.assertEqual(self.t.info_hash(self.LOW), self.LOW)
        self.assertEqual(self.t.info_hash('ZHQVOY7XELZD5GFCTXWN7LRUDOMNKMCW'),
                         self.LOW)   # base32
        self.assertEqual(
            self.t.info_hash('magnet:?xt=urn:btih:%s&dn=X' % self.HEX), self.LOW)
        self.assertEqual(self.t.info_hash('https://x/t/%s/n' % self.LOW), self.LOW)
        self.assertEqual(self.t.info_hash('not a hash'), '')

    def test_magnet_is_idempotent_and_has_trackers(self):
        uri = self.t.magnet(self.HEX, 'My Movie')
        self.assertIn('btih:' + self.LOW, uri)
        self.assertIn('dn=My+Movie', uri)
        self.assertIn('tr=', uri)
        self.assertEqual(self.t.info_hash(self.t.magnet(uri)), self.LOW)

    def test_seeders_survives_indexer_junk(self):
        got = [self.t.seeders(v)
               for v in ('', '-', 'n/a', '1,234', 42, None, '12 seeds')]
        self.assertEqual(got, [0, 0, 0, 1234, 42, 0, 12])

    def test_dedupe_merges_by_hash_and_sums_seeders(self):
        rows = [
            {'url': self.t.magnet(self.HEX), 'quality': '720p', 'size': 1.0,
             'seeders': 10},
            {'url': self.t.magnet(self.HEX), 'quality': '1080p', 'size': 8.0,
             'seeders': 5},
            {'url': 'https://other/x', 'quality': 'SD', 'size': 0.5},
        ]
        merged = self.t.dedupe(rows)
        self.assertEqual(len(merged), 2)
        best = [r for r in merged if r.get('hash') == self.LOW][0]
        self.assertEqual(best['quality'], '1080p')   # better copy won
        self.assertEqual(best['seeders'], 15)        # evidence combined

    def test_pack_detection_handles_dot_separated_names(self):
        """The classic bug: \\s+ never matches "Complete.Series"."""
        cases = [
            ('Show.S02.1080p.WEB-DL', 2, True),
            ('Show.S02.1080p.WEB-DL', 3, False),
            ('Show.S01-S05.COMPLETE', 3, True),
            ('Show.Complete.Series.1080p', 9, True),
            ('Show.Seasons.1.to.4', 2, True),
            ('Show.Seasons.1.to.4', 7, False),
            ('Show Season 3 1080p', 3, True),
            ('Show.S02E07.1080p', 2, False),      # single episode
        ]
        for name, season, expected in cases:
            self.assertEqual(self.t.is_pack(name, season), expected, name)

    def test_pick_file_out_of_a_pack(self):
        files = [
            {'path': 'Show/Sample/sample.mkv', 'bytes': 9e6},
            {'path': 'Show/Show.S02E07.1080p.mkv', 'bytes': 2.1e9},
            {'path': 'Show/Show.S02E08.1080p.mkv', 'bytes': 2.2e9},
            {'path': 'Show/Subs/eng.srt', 'bytes': 1e5},
        ]
        self.assertIn('S02E07', self.t.pick_file(files, 2, 7)['path'])
        self.assertIsNone(self.t.pick_file(files, 2, 99))
        self.assertIn('S02E08', self.t.pick_file(files)['path'])

    def test_torrent_scraper_builds_a_gated_source(self):
        from resources.lib.scrapers.torrents import TorrentScraper

        class Indexer(TorrentScraper):
            ID, NAME = 'idx', 'Indexer'
            MIN_SEEDERS = 5

        idx = Indexer()
        good = idx.torrent_source('Movie.2024.1080p.WEB-DL', self.HEX,
                                  size=6.2, seeds=40)
        self.assertEqual(good['hash'], self.LOW)
        self.assertEqual(good['quality'], '1080p')
        self.assertFalse(good['direct'])
        self.assertTrue(good['debrid_only'])
        self.assertIn('40 seeders', good['info'])
        # below MIN_SEEDERS
        self.assertIsNone(idx.torrent_source('X.1080p', self.HEX, seeds=1))


class TestAliases(unittest.TestCase):
    """Alternate titles, without which non-English releases are invisible."""

    def setUp(self):
        from resources.lib.scrapers.base import Scraper
        self.gate = Scraper()

    def test_alias_matches_when_primary_title_does_not(self):
        item = {'title': 'Amelie', 'year': 2001,
                'aliases': ["Le Fabuleux Destin d'Amelie Poulain"]}
        self.assertTrue(self.gate.accepts(
            "Le Fabuleux Destin d'Amelie Poulain (2001)", item))

    def test_no_aliases_still_works(self):
        self.assertTrue(self.gate.accepts(
            'Nosferatu (1922)', {'title': 'Nosferatu', 'year': 1922}))

    def test_alias_does_not_open_the_gate_to_anything(self):
        item = {'title': 'The Kid', 'year': 1921, 'aliases': ['Le Gosse']}
        self.assertFalse(self.gate.accepts('The Wolf and The Kid (1921)', item))


class TestCircuitBreaker(unittest.TestCase):
    """The Crew needs a maintainer to hand-set defunct=True and ship."""

    def setUp(self):
        from resources.lib import scrapers
        self.s = scrapers
        scrapers.reset_health()

    def tearDown(self):
        self.s.reset_health()

    def test_trips_only_after_repeated_failure(self):
        for _ in range(self.s.TRIP_AFTER - 1):
            self.s.record('x', 'X', 0, 0.1, 'down')
            self.assertFalse(self.s.is_tripped('x'))
        self.s.record('x', 'X', 0, 0.1, 'down')
        self.assertTrue(self.s.is_tripped('x'))

    def test_success_resets(self):
        self.s.record('x', 'X', 0, 0.1, 'down')
        self.s.record('x', 'X', 3, 0.1)
        self.assertFalse(self.s.is_tripped('x'))

    def test_cooldown_expiry_allows_one_probe(self):
        import time
        for _ in range(self.s.TRIP_AFTER):
            self.s.record('x', 'X', 0, 0.1, 'down')
        self.assertTrue(self.s.is_tripped('x'))
        self.s.health()['x']['tripped_at'] = time.time() - self.s.COOLDOWN - 1
        self.assertFalse(self.s.is_tripped('x'))

    def test_tripped_scrapers_are_excluded_from_scans(self):
        found = self.s.discover()
        if not found:
            return
        target = found[0].ID
        for _ in range(self.s.TRIP_AFTER):
            self.s.record(target, target, 0, 0.1, 'down')
        self.assertNotIn(target, [s.ID for s in self.s.enabled()])


class TestAddonXML(unittest.TestCase):
    """An unsatisfiable dependency makes Kodi refuse updates *silently*."""

    PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'plugin.video.alamo', 'addon.xml')

    def setUp(self):
        import xml.etree.ElementTree as ET
        self.root = ET.parse(self.PATH).getroot()

    def test_only_dependencies_kodi_actually_ships(self):
        allowed = {'xbmc.python', 'script.module.requests'}
        declared = {i.get('addon') for i in self.root.iter('import')}
        self.assertTrue(declared <= allowed,
                        'undeclarable dependency: %s' % (declared - allowed))

    def test_resolveurl_is_not_declared(self):
        """It is imported lazily; declaring a version blocks updates for
        anyone running an older ResolveURL."""
        declared = {i.get('addon') for i in self.root.iter('import')}
        self.assertNotIn('script.module.resolveurl', declared)
        lib = os.path.join(os.path.dirname(self.PATH), 'resources', 'lib')
        found = False
        for root, _dirs, files in os.walk(lib):
            for name in files:
                if not name.endswith('.py'):
                    continue
                with open(os.path.join(root, name)) as handle:
                    body = handle.read()
                if 'import resolveurl' in body:
                    found = True
                    self.assertIn('ImportError', body,
                                  '%s imports resolveurl without a guard' % name)
        self.assertTrue(found)

    def test_requests_version_is_conservative(self):
        for item in self.root.iter('import'):
            if item.get('addon') == 'script.module.requests':
                major, minor = [int(p) for p in item.get('version').split('.')[:2]]
                self.assertLessEqual((major, minor), (2, 27))


class TestSettingsXML(unittest.TestCase):
    """The settings dialog is invisible from here, so validate it statically."""

    PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'plugin.video.alamo', 'resources', 'settings.xml')

    def setUp(self):
        import xml.etree.ElementTree as ET
        self.tree = ET.parse(self.PATH)

    def test_parses(self):
        self.assertEqual(self.tree.getroot().tag, 'settings')

    def test_every_setting_id_used_in_code_exists(self):
        declared = {s.get('id') for s in self.tree.iter('setting')}
        lib = os.path.join(os.path.dirname(self.PATH), 'lib')
        used = set()
        pattern = re.compile(r"setting(?:_bool|_int)?\(\s*'([a-z0-9_]+)'")
        for root, _dirs, files in os.walk(lib):
            for name in files:
                if name.endswith('.py'):
                    with open(os.path.join(root, name)) as handle:
                        used |= set(pattern.findall(handle.read()))
        missing = used - declared
        self.assertFalse(missing, 'settings.xml is missing: %s' % missing)

    def test_no_invalid_level_elements(self):
        # <level> only accepts 0-3; 4 makes Kodi reject the file
        for level in self.tree.iter('level'):
            self.assertIn(level.text, ('0', '1', '2', '3'))

    def test_action_settings_point_at_real_routes(self):
        """Every settings button must hit a route router.dispatch handles."""
        router_py = os.path.join(os.path.dirname(self.PATH), 'lib', 'router.py')
        with open(router_py) as handle:
            routes = set(re.findall(r"action == '([a-z_]+)'", handle.read()))
        self.assertTrue(routes)
        actions = [s.get('action') or '' for s in self.tree.iter('setting')
                   if s.get('type') == 'action']
        self.assertTrue(actions)
        for action in actions:
            self.assertIn('plugin://plugin.video.alamo/?action=', action)
            name = action.split('action=')[1].rstrip(')')
            self.assertIn(name, routes,
                          '%s has no handler in router.dispatch' % name)


class TestTMDBKeyValidation(unittest.TestCase):
    def test_rejects_obvious_rubbish(self):
        ok, message = tmdb.verify_key('')
        self.assertFalse(ok)
        ok, message = tmdb.verify_key('not a key')
        self.assertFalse(ok)
        self.assertIn('v3', message)


class TestNavigationWiring(unittest.TestCase):
    """Guard the frontend contracts that are easy to break and hard to see."""

    def test_search_is_not_in_the_rail(self):
        from resources.lib.ui import windows
        keys = [k for k, _label in windows.NAV_ITEMS]
        self.assertNotIn('search', keys)
        for expected in ('home', 'movies', 'tv', 'sports', 'mylist', 'settings'):
            self.assertIn(expected, keys)

    def test_every_section_is_openable(self):
        from resources.lib import app
        for name in ('movies', 'tv', 'sports', 'search', 'mylist'):
            self.assertIn(name, app.SECTIONS)

    def test_depth_tracking_starts_at_zero(self):
        from resources.lib import app
        self.assertEqual(app.depth(), 0)

    def test_parallel_helper_keeps_order(self):
        from resources.lib import app
        jobs = [(lambda v=i: v * 2) for i in range(12)]
        self.assertEqual(app._parallel(jobs), [i * 2 for i in range(12)])


class TestSkinXML(unittest.TestCase):
    SKIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'plugin.video.alamo', 'resources', 'skins', 'Default')

    def _read(self, name):
        with open(os.path.join(self.SKIN, '1080i', name)) as handle:
            return handle.read()

    def test_all_windows_parse(self):
        import xml.etree.ElementTree as ET
        import glob
        files = glob.glob(os.path.join(self.SKIN, '1080i', '*.xml'))
        self.assertEqual(len(files), 4)
        for path in files:
            ET.parse(path)

    def test_every_texture_referenced_exists(self):
        import re
        import glob
        media = os.path.join(self.SKIN, 'media')
        available = set(os.listdir(media))
        for path in glob.glob(os.path.join(self.SKIN, '1080i', '*.xml')):
            with open(path) as handle:
                body = handle.read()
            for texture in re.findall(r'<texture[^>]*>([^<$][^<]*)</texture>', body):
                self.assertIn(texture.strip(), available,
                              '%s references missing texture %s'
                              % (os.path.basename(path), texture))

    def test_rounded_corners_on_every_tile(self):
        for name in ('alamo-home.xml', 'alamo-grid.xml'):
            self.assertIn('corner_mask.png', self._read(name))

    def test_focus_ring_is_scoped_to_the_focused_row(self):
        home = self._read('alamo-home.xml')
        # every row: ring/title shown only while that row has focus, and its
        # selected tile is dimmed like the others while it does not
        for cid in (101, 102, 103, 104, 105):
            self.assertIn('<visible>Control.HasFocus(%d)</visible>' % cid, home)
            self.assertIn('<visible>!Control.HasFocus(%d)</visible>' % cid, home)
        grid = self._read('alamo-grid.xml')
        self.assertIn('<visible>Control.HasFocus(50)</visible>', grid)

    def test_loading_screen_present_in_every_browse_window(self):
        for name in ('alamo-home.xml', 'alamo-grid.xml', 'alamo-detail.xml'):
            self.assertIn('Window.Property(LoadingText)', self._read(name))

    def test_grid_has_a_search_button(self):
        grid = self._read('alamo-grid.xml')
        self.assertIn('id="61"', grid)
        self.assertIn('Window.Property(SearchLabel)', grid)


class TestReleaseParsing(unittest.TestCase):
    def setUp(self):
        from resources.lib.providers import parsing
        self.parsing = parsing

    def test_quality(self):
        cases = {
            'The.Batman.2022.2160p.UHD.BluRay.x265': '4K',
            'Heat.1995.1080p.BluRay.DDP5.1.x264': '1080p',
            'Arrival.2016.720p.WEBRip': '720p',
            'Dune.Part.Two.2024.HDCAM.x264': 'CAM',
            'Some.Old.Movie.DVDRip.XviD': 'SD',
        }
        for name, expected in cases.items():
            self.assertEqual(self.parsing.quality(name), expected, name)

    def test_info_tags(self):
        tags = self.parsing.info_tags(
            'Dune.Part.Two.2024.2160p.WEB-DL.DDP5.1.Atmos.HDR.HEVC-GROUP')
        self.assertIn('WEB-DL', tags)
        self.assertIn('HEVC', tags)
        self.assertIn('HDR', tags)

    def test_size(self):
        self.assertEqual(self.parsing.size_gb('4.32 GB'), 4.32)
        self.assertEqual(self.parsing.size_gb('700 MB'), 0.68)
        self.assertEqual(self.parsing.size_gb('no size here'), 0.0)

    def test_episode_numbers(self):
        for name in ('Show.S02E07.1080p', 'Show 2x07 720p',
                     'Show.Season.2.Episode.7'):
            self.assertEqual(self.parsing.episode_numbers(name), (2, 7), name)

    def test_movie_matching(self):
        match = self.parsing.matches_movie
        self.assertTrue(match('The.Batman.2022.1080p.WEB-DL', 'The Batman', '2022'))
        self.assertTrue(match('Heat.1995.BluRay.1080p', 'Heat', '1995'))
        # right title, very wrong year
        self.assertFalse(match('The.Batman.1966.DVDRip', 'The Batman', '2022'))
        # completely different film
        self.assertFalse(match('Batman.Begins.2005.1080p', 'The Batman', '2022'))

    def test_episode_matching(self):
        match = self.parsing.matches_episode
        self.assertTrue(match('Severance.S02E03.1080p.WEB', 'Severance', 2, 3))
        self.assertFalse(match('Severance.S02E04.1080p.WEB', 'Severance', 2, 3))
        self.assertFalse(match('The.Bear.S02E03.1080p', 'Severance', 2, 3))

    def test_accents_and_punctuation(self):
        self.assertEqual(self.parsing.normalise("Amélie's Café & Bar"),
                         'amelies cafe and bar')


class TestScraperEngine(unittest.TestCase):
    def setUp(self):
        from resources.lib.providers import scraper_base
        self.scraper_base = scraper_base

    def test_harvest_skips_junk_and_assets(self):
        class Dummy(self.scraper_base.HosterScraper):
            id = 'dummy'
            base_url = 'https://mysite.test'

        body = '''
          <a href="https://mysite.test/internal">internal</a>
          <img src="https://cdn.test/poster.jpg">
          <a href="https://facebook.com/share">fb</a>
          <iframe src="https://goodhost.test/embed/abc123"></iframe>
          <a href="https://otherhost.test/v/xyz">mirror</a>
          <script src="https://cdn.test/app.js"></script>
        '''
        found = Dummy().harvest(body)
        self.assertIn('https://goodhost.test/embed/abc123', found)
        self.assertIn('https://otherhost.test/v/xyz', found)
        self.assertNotIn('https://mysite.test/internal', found)
        self.assertNotIn('https://facebook.com/share', found)
        self.assertFalse([u for u in found if u.endswith(('.jpg', '.js'))])

    def test_host_of(self):
        self.assertEqual(self.scraper_base.host_of('https://www.Host.TEST/a/b'),
                         'host.test')

    def test_query_building(self):
        class Dummy(self.scraper_base.HosterScraper):
            id = 'dummy'
        dummy = Dummy()
        self.assertEqual(
            dummy.query_for({'title': 'Heat', 'year': '1995'}, 'movie'),
            'Heat 1995')
        self.assertEqual(
            dummy.query_for({'show_title': 'Severance', 'season': 2,
                             'episode': 3}, 'episode'),
            'Severance S02E03')

    def test_end_to_end_against_a_fake_site(self):
        """Full flow: search -> page -> links -> filtered, parsed sources."""
        pages = {
            'https://fake.test/search?q=Heat+1995': (
                '<a class="r" href="/movie/heat-1995">Heat 1995 1080p BluRay</a>'
                '<a class="r" href="/movie/heat-2015">Heat 2015 720p</a>'),
            'https://fake.test/movie/heat-1995':
                '<iframe src="https://hoster.test/e/abc"></iframe>'
                '<a href="https://mirror.test/v/def">mirror</a>',
        }

        class Fake(self.scraper_base.HosterScraper):
            id = 'fake'
            base_url = 'https://fake.test'
            require_resolvable = False

            def fetch(self, url, **kwargs):
                return pages.get(url, '')

            def search(self, query, item, media_type):
                body = self.fetch('https://fake.test/search?q=%s'
                                  % query.replace(' ', '+'))
                import re as _re
                return [(t, 'https://fake.test' + u) for u, t in
                        _re.findall(r'href="([^"]+)">([^<]+)<', body)]

        sources = Fake()._collect({'title': 'Heat', 'year': '1995'}, 'movie')
        urls = sorted(s['url'] for s in sources)
        self.assertEqual(urls, ['https://hoster.test/e/abc',
                                'https://mirror.test/v/def'])
        self.assertEqual(sources[0]['quality'], '1080p')
        self.assertIn('BluRay', sources[0]['info'])
        self.assertFalse(sources[0]['direct'])


class TestConfigScraper(unittest.TestCase):
    def test_builds_from_json_and_scrapes(self):
        from resources.lib.providers import config_scraper
        config = {
            'id': 'jsonsite', 'name': 'JSON Site',
            'base': 'https://json.test',
            'search_url': 'https://json.test/?s={query}',
            'result_pattern': r'<h2><a href="(?P<url>[^"]+)">(?P<title>[^<]+)</a>',
            'link_pattern': r'<source src="(?P<url>[^"]+)"',
            'capabilities': ['movie'],
        }
        scraper = config_scraper.ConfigScraper(config)
        self.assertEqual(scraper.id, 'jsonsite')
        self.assertEqual(scraper.capabilities, ('movie',))
        self.assertEqual(
            scraper.query_for({'title': 'Heat', 'year': '1995'}, 'movie'),
            'Heat 1995')

        pages = {
            'https://json.test/?s=Heat%201995':
                '<h2><a href="/w/heat">Heat 1995 1080p WEB</a></h2>',
            'https://json.test/w/heat':
                '<source src="https://cdn.host.test/heat.mp4">',
        }
        scraper.fetch = lambda url, **kw: pages.get(url, '')
        scraper.require_resolvable = False
        sources = scraper._collect({'title': 'Heat', 'year': '1995'}, 'movie')
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]['url'], 'https://cdn.host.test/heat.mp4')

    def test_rejects_incomplete_config(self):
        from resources.lib.providers import config_scraper
        self.assertEqual(
            [k for k in config_scraper.REQUIRED
             if k not in {'id': 1, 'name': 2}],
            ['search_url', 'result_pattern'])


class TestArchiveProvider(unittest.TestCase):
    def test_filters_mismatched_titles(self):
        from resources.lib.providers import archive_provider
        provider = archive_provider.ArchiveProvider()
        provider._search = lambda title, year: [
            {'identifier': 'right', 'title': 'Night of the Living Dead'},
            {'identifier': 'wrong', 'title': 'Family Holiday Home Movie'},
        ]
        provider._files = lambda identifier: [
            {'format': 'h.264', 'name': '%s.mp4' % identifier,
             'size': '1073741824', 'width': '1920'},
            {'format': 'Thumbnail', 'name': 'thumb.jpg'},
        ]
        sources = provider.movie({'title': 'Night of the Living Dead',
                                  'year': '1968'})
        self.assertEqual(len(sources), 1)
        self.assertIn('right.mp4', sources[0]['url'])
        self.assertEqual(sources[0]['quality'], '1080p')
        self.assertTrue(sources[0]['direct'])


def tearDownModule():
    shutil.rmtree(kodistubs.PROFILE, ignore_errors=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
