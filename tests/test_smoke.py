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
        import xml.etree.ElementTree as ET  # noqa: F401
        actions = [s.get('action') or '' for s in self.tree.iter('setting')
                   if s.get('type') == 'action']
        self.assertTrue(actions)
        for action in actions:
            self.assertIn('plugin://plugin.video.alamo/?action=', action)
            name = action.split('action=')[1].rstrip(')')
            self.assertIn(name, ('set_tmdb', 'providers', 'clear_cache',
                                 'clear_progress'))


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


def tearDownModule():
    shutil.rmtree(kodistubs.PROFILE, ignore_errors=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
