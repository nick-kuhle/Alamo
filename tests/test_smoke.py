# -*- coding: utf-8 -*-
"""Headless smoke tests. Run: python3 tests/test_smoke.py"""
import os
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


def tearDownModule():
    shutil.rmtree(kodistubs.PROFILE, ignore_errors=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
