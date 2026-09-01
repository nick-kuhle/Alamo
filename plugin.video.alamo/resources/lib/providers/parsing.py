# -*- coding: utf-8 -*-
"""Release-name parsing and title matching.

This is the part that decides whether "The.Batman.2022.1080p.WEB-DL.DDP5.1.x265"
is actually the movie you asked for - and it is where most scrapers get things
subtly wrong.
"""
import re
import unicodedata

QUALITY_PATTERNS = (
    ('4K', r'\b(2160p|4k|uhd|ultrahd)\b'),
    ('1080p', r'\b(1080p|1080i|fullhd|fhd)\b'),
    ('720p', r'\b(720p|hd\b|hdrip)\b'),
    ('CAM', r'\b(cam|camrip|hdcam|ts|telesync|tc|telecine|hdts|dvdscr|scr)\b'),
)

CODEC_PATTERNS = (
    ('HEVC', r'\b(hevc|x265|h\.?265)\b'),
    ('AVC', r'\b(avc|x264|h\.?264)\b'),
    ('AV1', r'\bav1\b'),
    ('XviD', r'\b(xvid|divx)\b'),
)

AUDIO_PATTERNS = (
    ('Atmos', r'\batmos\b'),
    ('TrueHD', r'\btruehd\b'),
    ('DTS-HD', r'\bdts[\.\- ]?hd\b'),
    ('DTS', r'\bdts\b'),
    ('DDP5.1', r'\b(ddp|eac3|e\-?ac3)[\.\- ]?5\.?1\b'),
    ('DD5.1', r'\b(dd|ac3)[\.\- ]?5\.?1\b'),
    ('AAC', r'\baac\b'),
)

EXTRA_PATTERNS = (
    ('HDR10+', r'\bhdr10\+\b'),
    ('HDR', r'\bhdr\b'),
    ('DV', r'\b(dolby[\.\- ]?vision|\bdv\b)\b'),
    ('10bit', r'\b10.?bit\b'),
    ('REMUX', r'\bremux\b'),
    ('IMAX', r'\bimax\b'),
    ('SDR', r'\bsdr\b'),
)

SOURCE_PATTERNS = (
    ('BluRay', r'\b(blu[\.\- ]?ray|bdrip|brrip|bd25|bd50)\b'),
    ('WEB-DL', r'\b(web[\.\- ]?dl|webdl)\b'),
    ('WEBRip', r'\b(web[\.\- ]?rip|webrip|web)\b'),
    ('HDTV', r'\bhdtv\b'),
    ('DVDRip', r'\bdvd[\.\- ]?rip\b'),
)

SIZE_RE = re.compile(r'(\d+(?:[.,]\d+)?)\s*(gb|gib|mb|mib)\b', re.I)

EPISODE_RES = (
    re.compile(r's(?P<season>\d{1,2})[\. _-]?e(?P<episode>\d{1,3})', re.I),
    re.compile(r'(?P<season>\d{1,2})x(?P<episode>\d{1,3})'),
    re.compile(r'season[\. _-]?(?P<season>\d{1,2})[\. _-]?episode[\. _-]?'
               r'(?P<episode>\d{1,3})', re.I),
)

YEAR_RE = re.compile(r'(?:19|20)\d{2}')
JUNK_RE = re.compile(r'[\[\](){}]|\b(www\.\S+|proper|repack|internal|limited|'
                     r'extended|unrated|remastered|directors?\.?cut)\b', re.I)


def strip_accents(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text or '')
                   if not unicodedata.combining(c))


def normalise(title):
    """Lowercase, de-accented, punctuation-free form used for comparisons."""
    text = strip_accents(title or '').lower()
    text = text.replace('&', ' and ')
    text = re.sub(r"['’`]", '', text)
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return ' '.join(text.split())


def quality(name):
    text = (name or '').lower()
    for label, pattern in QUALITY_PATTERNS:
        if re.search(pattern, text):
            return label
    return 'SD'


def _tags(name, patterns):
    text = (name or '').lower()
    return [label for label, pattern in patterns if re.search(pattern, text)]


def info_tags(name):
    """Human readable extras: codec, audio, HDR, source."""
    tags = []
    tags += _tags(name, SOURCE_PATTERNS)[:1]
    tags += _tags(name, CODEC_PATTERNS)[:1]
    tags += _tags(name, AUDIO_PATTERNS)[:1]
    tags += _tags(name, EXTRA_PATTERNS)
    seen, out = set(), []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            out.append(tag)
    return out


def size_gb(text):
    """Pull a size out of free text, in GB."""
    match = SIZE_RE.search(text or '')
    if not match:
        return 0.0
    value = float(match.group(1).replace(',', '.'))
    unit = match.group(2).lower()
    if unit.startswith('m'):
        value /= 1024.0
    return round(value, 2)


def episode_numbers(name):
    """Return (season, episode) found in a release name, or (None, None)."""
    for pattern in EPISODE_RES:
        match = pattern.search(name or '')
        if match:
            return int(match.group('season')), int(match.group('episode'))
    return None, None


def years(name):
    return [int(y) for y in YEAR_RE.findall(name or '')]


def clean_release(name):
    """Strip site junk so titles compare sensibly."""
    text = JUNK_RE.sub(' ', name or '')
    return ' '.join(text.split())


#: tokens that describe the file, not the film - ignored when comparing titles
NOISE = set((
    '1080p 1080i 720p 480p 2160p 4k uhd hd fhd sd cam camrip hdcam ts telesync '
    'tc telecine hdts dvdscr scr bluray blu ray bdrip brrip webrip web dl webdl '
    'hdtv dvdrip dvd rip remux imax hdr hdr10 dv sdr 10bit 8bit hevc x265 h265 '
    'avc x264 h264 av1 xvid divx aac ac3 dd dd5 ddp eac3 dts truehd atmos 51 '
    '71 20 multi dual audio subs esub proper repack internal limited extended '
    'unrated remastered directors cut yify yts rarbg galaxyrg mkv mp4 avi'
).split())


def similarity(left, right):
    """Symmetric 0..1 token overlap - for comparing two *titles*."""
    a, b = set(normalise(left).split()), set(normalise(right).split())
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a | b))


def containment(release, title):
    """How much of ``title`` appears in ``release`` (0..1).

    Asymmetric on purpose: "The.Batman.2022.1080p.WEB-DL.DDP5.1.x265" shares
    only a third of its tokens with "The Batman", but it contains *all* of the
    title - which is the question that actually matters.
    """
    wanted = set(normalise(title).split())
    if not wanted:
        return 0.0
    found = set(normalise(release).split())
    return len(wanted & found) / float(len(wanted))


def title_head(release):
    """The part of a release name before the year / quality noise starts."""
    text = clean_release(release)
    match = YEAR_RE.search(text)
    if match and match.start() > 0:
        text = text[:match.start()]
    tokens = []
    for token in normalise(text).split():
        if token in NOISE:
            break
        tokens.append(token)
    return ' '.join(tokens)


def extra_words(release, title):
    """Words in the release's title portion that the real title does not have."""
    head = set(title_head(release).split())
    wanted = set(normalise(title).split())
    return len(head - wanted - NOISE)


def matches_movie(release, title, year, aliases=None, tolerance=1):
    """Does this release name plausibly belong to this movie?

    Three gates: the title must be (almost) fully present, the release must not
    introduce extra title words ("Batman Begins" is not "The Batman"), and any
    year in the name must be close to the real one.
    """
    release_clean = clean_release(release)
    candidates = [c for c in ([title] + list(aliases or [])) if c]
    if not candidates:
        return False
    if max(containment(release_clean, c) for c in candidates) < 0.8:
        return False
    if min(extra_words(release_clean, c) for c in candidates) > 2:
        return False
    found = years(release_clean)
    if year and found:
        if not any(abs(int(year) - y) <= tolerance for y in found):
            return False
    return True


def matches_episode(release, show_title, season, episode, aliases=None):
    """Does this release name belong to this exact episode?"""
    found_season, found_episode = episode_numbers(release)
    if found_season is None:
        return False
    if int(found_season) != int(season) or int(found_episode) != int(episode):
        return False
    # the title part is whatever precedes the SxxEyy marker
    head = re.split(r's\d{1,2}[\. _-]?e\d{1,3}|\d{1,2}x\d{1,3}|season',
                    release, flags=re.I)[0]
    candidates = [c for c in ([show_title] + list(aliases or [])) if c]
    if not candidates:
        return False
    return max(containment(head, c) for c in candidates) >= 0.8


def describe(name, size_text=''):
    """Return (quality, info string, size) for a release name."""
    return (quality(name),
            ' \u2022 '.join(info_tags(name)),
            size_gb(size_text or name))
