# -*- coding: utf-8 -*-
"""Base class for The Alamo's built-in, hand-written site scrapers.

Why this exists alongside ``providers/``
----------------------------------------
``providers/``  = pluggable things the *user* installs or drops in, plus the
                  JSON site-config engine.
``scrapers/``   = site scrapers we hand-write and ship inside the add-on.

This is the same split The Crew uses (its ``scrapers/`` package inside
``script.module.thecrew``), with three deliberate improvements:

1. **Metadata is declared, never guessed.** The Crew classifies a scraper by
   regex-grepping its own source code for ``'source': 'torrent'`` and
   ``'debridonly': True``. Here every scraper states ``KIND``, ``PRIORITY``,
   ``CAPABILITIES`` and ``ATTRIBUTION`` as class attributes. No heuristics.

2. **Title matching lives in one place.** In The Crew each scraper re-implements
   its own title check, so a fix to one never reaches the other 36. Here
   :meth:`Scraper.accepts` is inherited by every scraper, so the containment /
   extra-word / junk rules that live testing forced on us apply everywhere.

3. **Failure is data, not a silent except.** Every scan records rows in
   :mod:`resources.lib.scrapers` so the user can see which site was slow,
   which returned nothing, and which raised.
"""
import re
import time

from .. import kodi
from ..providers import parsing
from ..providers.base import Source

# Words that mean "this is not the feature film you searched for".
# Learned the hard way: searching The Kid (1921) on a real archive returns
# four featurettes and an unrelated film before the actual movie.
JUNK_WORDS = (
    'trailer', 'teaser', 'featurette', 'interview', 'commentary', 'sample',
    'behind the scenes', 'making of', 'deleted scene', 'blooper', 'outtake',
    'end credits', 'opening credits', 'promo', 'preview', 'clip', 'excerpt',
    'restoration demo', 'comparison', 'review', 'reaction', 'scenes',
)

_JUNK_RE = re.compile('|'.join(re.escape(w) for w in JUNK_WORDS), re.I)


def is_junk(*texts):
    """True when any supplied text looks like an extra rather than the film."""
    for text in texts:
        if text and _JUNK_RE.search(text):
            return True
    return False


def quality_for(width=0, height=0, name='', default='SD'):
    """Resolution first, filename hints only as a fallback.

    Never trust a title that claims 1080p; archives routinely label a 640x360
    derivative as ``_1080p``. Real pixel dimensions win when we have them.
    """
    try:
        height = int(height or 0)
        width = int(width or 0)
    except (TypeError, ValueError):
        height = width = 0
    # some sources only report width
    if not height and width:
        height = int(width * 9 / 16.0)
    if height:
        if height >= 2000:
            return '4K'
        if height >= 900:
            return '1080p'
        if height >= 650:
            return '720p'
        return 'SD'
    if name:
        found = parsing.quality(name)
        if found and found != 'SD':
            return found
    return default


class Scraper(object):
    """Subclass this, set the metadata, implement :meth:`movie`.

    Minimum viable scraper::

        class MySite(Scraper):
            ID = 'mysite'
            NAME = 'My Site'
            CAPABILITIES = ('movie',)

            def movie(self, item):
                for hit in self.get_json(URL % item['title'])['results']:
                    if not self.accepts(hit['title'], item):
                        continue
                    yield self.source(hit['file'], hit['title'], direct=True)

    Return (or yield) :class:`Source` objects. Raising is fine — the registry
    isolates each scraper and records the error in the scan report.
    """

    # --- declared metadata (never inferred) --------------------------------
    ID = ''
    NAME = ''
    #: free | debrid | torrent — drives grouping and the debrid-only filter
    KIND = 'free'
    #: lower runs and sorts first
    PRIORITY = 50
    CAPABILITIES = ('movie',)
    #: seconds this scraper may take before the scan moves on without it
    TIMEOUT = 20
    LANGUAGE = 'en'
    #: shown in the UI; required for sources with a licence or credit
    ATTRIBUTION = ''
    #: set False for scrapers that should ship switched off
    DEFAULT_ENABLED = True
    #: how many sources one scraper may contribute to a single scan
    MAX_RESULTS = 12

    # --- HTTP ---------------------------------------------------------------
    HEADERS = None

    def __init__(self):
        self.log_prefix = '[%s]' % (self.ID or self.__class__.__name__)

    def _net(self):
        from ..providers import net
        return net

    def get(self, url, **kwargs):
        kwargs.setdefault('headers', self.HEADERS)
        return self._net().get(url, **kwargs)

    def get_json(self, url, **kwargs):
        kwargs.setdefault('headers', self.HEADERS)
        return self._net().get_json(url, **kwargs)

    # --- helpers every scraper inherits -------------------------------------
    def source(self, url, name, quality=None, size=0.0, direct=True,
               info='', **extra):
        """Build a :class:`Source` with this scraper's identity filled in."""
        return Source(
            url=url,
            name=name,
            quality=quality or parsing.quality(name),
            size=float(size or 0.0),
            direct=direct,
            info=info,
            language=self.LANGUAGE,
            provider=self.ID,
            provider_name=self.NAME,
            **extra)

    def accepts(self, found_title, item, media_type='movie'):
        """Shared title gate. One fix here fixes every scraper.

        Rules, all of them earned from real API responses:

        * junk words (trailer, featurette, end credits...) are rejected
        * containment >= 0.8 — asymmetric, because a release name is much
          longer than a title and symmetric overlap dilutes to nothing
        * many extra words are only tolerated when the found title *starts
          with* the wanted one, so "Nosferatu, eine Symphonie des Grauens"
          is kept while "Beulah Bains In The Kid" is dropped
        """
        if not found_title:
            return False
        if is_junk(found_title):
            return False
        wanted = item.get('title') or ''
        if not wanted:
            return False
        if media_type == 'episode':
            return parsing.matches_episode(
                found_title, wanted, item.get('season'), item.get('episode'))

        if parsing.containment(found_title, wanted) < 0.8:
            return False

        # Bracketed text is version metadata, not part of the title:
        # "Nosferatu (1922, English titles 1947)" is the film;
        # "Night of the Living Dead - Ten Minutes to Three" is a clip.
        bare = re.sub(r'[\(\[\{][^)\]\}]*[\)\]\}]', ' ', found_title)
        found_tokens = parsing.normalise(bare).split()
        wanted_tokens = parsing.normalise(wanted).split()

        start = self._phrase_index(found_tokens, wanted_tokens)
        if start is None:
            # title present only as scattered words, not as a phrase
            if parsing.extra_words(found_title, wanted) > 2:
                return False
        else:
            # "Beulah Bains In The Kid" / "The Wolf and The Kid" - the wanted
            # title is buried mid-sentence, so this is a different work.
            if start > 1:
                return False
            trailing = len(found_tokens) - (start + len(wanted_tokens))
            if trailing > 3:
                return False
        year = item.get('year')
        if year:
            found_years = parsing.years(found_title)
            if found_years and not any(abs(int(y) - int(year)) <= 1
                                       for y in found_years):
                return False
        return True

    @staticmethod
    def _phrase_index(haystack, needle):
        """Index where ``needle`` appears as a contiguous run, else None."""
        if not needle or len(needle) > len(haystack):
            return None
        for i in range(len(haystack) - len(needle) + 1):
            if haystack[i:i + len(needle)] == needle:
                return i
        return None

    def rank(self, sources):
        """Best first: quality, then size. Trimmed to ``MAX_RESULTS``."""
        order = {'4K': 0, '1080p': 1, '720p': 2, 'SD': 3, 'CAM': 4}
        ranked = sorted(
            sources,
            key=lambda s: (order.get(s.get('quality'), 5), -float(s.get('size') or 0)))
        return ranked[:self.MAX_RESULTS]

    # --- the contract -------------------------------------------------------
    def movie(self, item):
        return []

    def episode(self, item):
        return []

    def ping(self):
        return True

    # --- called by the registry --------------------------------------------
    def run(self, capability, item):
        """Execute one capability and return ranked sources plus timing."""
        started = time.time()
        handler = getattr(self, capability, None)
        if handler is None:
            return [], 0.0
        found = list(handler(item) or [])
        elapsed = time.time() - started
        kodi.log('%s %s -> %d source(s) in %.2fs'
                 % (self.log_prefix, capability, len(found), elapsed))
        return self.rank(found), elapsed

    def __repr__(self):
        return '<Scraper %s>' % (self.ID or self.__class__.__name__)
