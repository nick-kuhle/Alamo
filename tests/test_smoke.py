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
