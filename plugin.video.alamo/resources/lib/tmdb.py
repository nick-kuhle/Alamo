# -*- coding: utf-8 -*-
"""TMDB client - everything the browsing UI shows comes from here.

Only metadata. No streams, no links.
"""
import requests

from . import kodi
from . import cache

BASE = 'https://api.themoviedb.org/3'
IMG = 'https://image.tmdb.org/t/p'

POSTER = IMG + '/w500'
POSTER_HQ = IMG + '/w780'
BACKDROP = IMG + '/w1280'
BACKDROP_HQ = IMG + '/original'
STILL = IMG + '/w300'
LOGO = IMG + '/w500'

# A public, rate limited fallback key so the add-on works out of the box.
# Users can paste their own key in the settings.
DEFAULT_KEY = ''

TTL_SHORT = 6 * 3600
TTL_LONG = 7 * cache.DAY

SESSION = requests.Session()
SESSION.headers.update({'Accept': 'application/json',
                        'User-Agent': 'Alamo/%s' % kodi.ADDON_VERSION})


class TMDBError(Exception):
    pass


def api_key():
    return kodi.setting('tmdb_key', DEFAULT_KEY).strip()


def language():
    return kodi.setting('tmdb_language', 'en-US') or 'en-US'


def has_key():
    return bool(api_key())


def verify_key(key):
    """Return (ok, message) for a candidate API key."""
    key = (key or '').strip()
    if not key:
        return False, 'No key entered'
    if len(key) < 20 or ' ' in key:
        return False, ('That does not look like a v3 API key (32 hex '
                       'characters). Use the "API Key (v3 auth)" value, not '
                       'the long read access token.')
    try:
        response = SESSION.get('%s/configuration' % BASE,
                               params={'api_key': key}, timeout=20)
    except Exception as exc:
        return False, 'Could not reach TMDB: %s' % exc
    if response.status_code == 200:
        return True, 'Key accepted'
    if response.status_code == 401:
        return False, 'TMDB rejected that key (401)'
    return False, 'TMDB returned HTTP %s' % response.status_code


def _get(path, **params):
    key = api_key()
    if not key:
        raise TMDBError('missing-key')
    params.setdefault('language', language())
    params['api_key'] = key
    url = '%s/%s' % (BASE, path.lstrip('/'))
    try:
        response = SESSION.get(url, params=params, timeout=20)
        if response.status_code == 401:
            raise TMDBError('bad-key')
        response.raise_for_status()
        return response.json()
    except TMDBError:
        raise
    except Exception as exc:
        kodi.error('tmdb request failed %s: %s' % (path, exc))
        return {}


def get(path, ttl=TTL_SHORT, **params):
    hit = cache.get('tmdb', path, sorted(params.items()), language())
    if hit is not None:
        return hit
    data = _get(path, **params)
    if data:
        cache.put(data, ttl, 'tmdb', path, sorted(params.items()), language())
    return data


# --------------------------------------------------------------------------
# normalisation
# --------------------------------------------------------------------------

def _img(base, path):
    return (base + path) if path else ''


def normalise(item, media_type=None):
    """Turn a raw TMDB item into the flat dict the UI works with."""
    mtype = media_type or item.get('media_type') or (
        'tv' if item.get('first_air_date') or item.get('name') else 'movie')
    title = item.get('title') or item.get('name') or ''
    date = item.get('release_date') or item.get('first_air_date') or ''
    return {
        'id': item.get('id'),
        'type': mtype,
        'title': title,
        'original_title': item.get('original_title') or item.get('original_name') or title,
        'year': date[:4] if date else '',
        'premiered': date,
        'plot': item.get('overview') or '',
        'rating': round(float(item.get('vote_average') or 0), 1),
        'votes': item.get('vote_count') or 0,
        'poster': _img(POSTER_HQ, item.get('poster_path')),
        'thumb': _img(POSTER, item.get('poster_path')),
        'fanart': _img(BACKDROP_HQ, item.get('backdrop_path')),
        'backdrop': _img(BACKDROP, item.get('backdrop_path')),
        'genres': item.get('genre_ids') or
                  [g.get('name') for g in item.get('genres', [])],
    }


def normalise_list(payload, media_type=None):
    results = payload.get('results') or []
    items = [normalise(i, media_type) for i in results]
    return [i for i in items if i['title'] and i['thumb']]


def page_info(payload):
    return {'page': payload.get('page', 1),
            'total_pages': min(payload.get('total_pages', 1) or 1, 500)}


# --------------------------------------------------------------------------
# rows / catalogues
# --------------------------------------------------------------------------

MOVIE_ROWS = [
    ('trending', 'Trending Now', 'trending/movie/week', {}),
    ('popular', 'Popular', 'movie/popular', {}),
    ('now_playing', 'In Theatres', 'movie/now_playing', {}),
    ('top_rated', 'Top Rated', 'movie/top_rated', {}),
    ('upcoming', 'Coming Soon', 'movie/upcoming', {}),
]

TV_ROWS = [
    ('trending', 'Trending Now', 'trending/tv/week', {}),
    ('airing_today', 'On Today', 'tv/airing_today', {}),
    ('popular', 'Popular', 'tv/popular', {}),
    ('top_rated', 'Top Rated', 'tv/top_rated', {}),
    ('on_the_air', 'Currently Airing', 'tv/on_the_air', {}),
]

MOVIE_GENRES = [
    (28, 'Action'), (12, 'Adventure'), (16, 'Animation'), (35, 'Comedy'),
    (80, 'Crime'), (99, 'Documentary'), (18, 'Drama'), (10751, 'Family'),
    (14, 'Fantasy'), (27, 'Horror'), (9648, 'Mystery'), (10749, 'Romance'),
    (878, 'Sci-Fi'), (53, 'Thriller'), (10752, 'War'), (37, 'Western'),
]

TV_GENRES = [
    (10759, 'Action & Adventure'), (16, 'Animation'), (35, 'Comedy'),
    (80, 'Crime'), (99, 'Documentary'), (18, 'Drama'), (10751, 'Family'),
    (9648, 'Mystery'), (10765, 'Sci-Fi & Fantasy'), (10768, 'War & Politics'),
]


def row(media_type, row_id, page=1):
    rows = MOVIE_ROWS if media_type == 'movie' else TV_ROWS
    for rid, _label, path, extra in rows:
        if rid == row_id:
            payload = get(path, page=page, **extra)
            return normalise_list(payload, media_type), page_info(payload)
    return [], {'page': 1, 'total_pages': 1}


def discover(media_type, page=1, **params):
    payload = get('discover/%s' % media_type, page=page,
                  sort_by=params.pop('sort_by', 'popularity.desc'), **params)
    return normalise_list(payload, media_type), page_info(payload)


def genre(media_type, genre_id, page=1):
    return discover(media_type, page=page, with_genres=genre_id,
                    **{'vote_count.gte': 50})


def search(media_type, query, page=1):
    payload = get('search/%s' % media_type, ttl=TTL_SHORT, query=query,
                  page=page, include_adult='false')
    return normalise_list(payload, media_type), page_info(payload)


def details(media_type, tmdb_id):
    data = get('%s/%s' % (media_type, tmdb_id), ttl=TTL_LONG,
               append_to_response='credits,external_ids,images,videos,'
                                  'recommendations,content_ratings,release_dates',
               include_image_language='%s,en,null' % language()[:2])
    if not data:
        return {}
    item = normalise(data, media_type)
    item['genres'] = [g['name'] for g in data.get('genres', [])]
    item['tagline'] = data.get('tagline') or ''
    item['runtime'] = data.get('runtime') or (
        (data.get('episode_run_time') or [0])[0])
    item['status'] = data.get('status') or ''
    item['imdb'] = (data.get('imdb_id') or
                    (data.get('external_ids') or {}).get('imdb_id') or '')
    item['tvdb'] = (data.get('external_ids') or {}).get('tvdb_id') or ''
    item['studio'] = ', '.join(
        c['name'] for c in (data.get('production_companies') or [])[:2])
    item['country'] = ', '.join(
        c.get('iso_3166_1', '') for c in (data.get('production_countries') or [])[:2])
    credits_ = data.get('credits') or {}
    item['cast'] = [{
        'name': c.get('name'),
        'role': c.get('character'),
        'thumbnail': _img(POSTER, c.get('profile_path')),
    } for c in (credits_.get('cast') or [])[:20]]
    item['director'] = ', '.join(
        c['name'] for c in (credits_.get('crew') or [])
        if c.get('job') == 'Director')[:120]
    item['seasons'] = [{
        'season': s.get('season_number'),
        'title': s.get('name'),
        'episodes': s.get('episode_count'),
        'plot': s.get('overview') or '',
        'poster': _img(POSTER_HQ, s.get('poster_path')) or item['poster'],
        'premiered': s.get('air_date') or '',
    } for s in (data.get('seasons') or []) if s.get('season_number') is not None
        and s.get('episode_count')]
    logos = ((data.get('images') or {}).get('logos') or [])
    item['clearlogo'] = _img(LOGO, logos[0]['file_path']) if logos else ''
    item['recommendations'] = normalise_list(
        data.get('recommendations') or {}, media_type)
    trailers = [v for v in ((data.get('videos') or {}).get('results') or [])
                if v.get('site') == 'YouTube' and v.get('type') == 'Trailer']
    item['trailer'] = ('plugin://plugin.video.youtube/play/?video_id=%s'
                       % trailers[0]['key']) if trailers else ''
    return item


def season(tmdb_id, season_number, show=None):
    data = get('tv/%s/season/%s' % (tmdb_id, season_number), ttl=TTL_SHORT)
    show = show or {}
    episodes = []
    for ep in data.get('episodes') or []:
        episodes.append({
            'type': 'episode',
            'id': tmdb_id,
            'show_title': show.get('title', ''),
            'title': ep.get('name') or 'Episode %s' % ep.get('episode_number'),
            'season': ep.get('season_number'),
            'episode': ep.get('episode_number'),
            'plot': ep.get('overview') or '',
            'premiered': ep.get('air_date') or '',
            'year': show.get('year', ''),
            'rating': round(float(ep.get('vote_average') or 0), 1),
            'thumb': _img(BACKDROP, ep.get('still_path')) or show.get('backdrop', ''),
            'poster': show.get('poster', ''),
            'fanart': show.get('fanart', ''),
            'imdb': show.get('imdb', ''),
            'tvdb': show.get('tvdb', ''),
        })
    return episodes
