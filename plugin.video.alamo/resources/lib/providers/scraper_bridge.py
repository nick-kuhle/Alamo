# -*- coding: utf-8 -*-
"""Adapts a built-in :class:`Scraper` to the :class:`Provider` interface.

Keeping the two APIs separate is deliberate: scrapers are a thin
"search a site, return sources" contract with no Kodi knowledge, while
providers are the richer pluggable surface (sports catalogues, resolve hooks,
ping). The bridge means a hand-written scraper needs none of that ceremony but
still shows up everywhere providers do — settings toggles, the source list,
diagnostics — with no special-casing in the rest of the add-on.
"""
from .. import kodi
from .base import Provider
from .. import scrapers as scraper_registry


class ScraperProvider(Provider):
    """One built-in scraper, wearing the Provider interface."""

    def __init__(self, scraper):
        self.scraper = scraper
        self.id = scraper.ID
        self.name = scraper.NAME
        self.priority = scraper.PRIORITY
        self.capabilities = tuple(scraper.CAPABILITIES)
        self.kind = scraper.KIND
        self.attribution = scraper.ATTRIBUTION
        self.builtin = True

    def _run(self, capability, item):
        import time
        started = time.time()
        try:
            sources, elapsed = self.scraper.run(capability, item)
            scraper_registry.record(self.id, self.name, len(sources), elapsed)
            return sources
        except Exception as exc:
            kodi.error('scraper %s raised: %s' % (self.id, exc))
            scraper_registry.record(self.id, self.name, 0,
                                    time.time() - started, exc)
            return []

    def movie(self, item):
        return self._run('movie', item)

    def episode(self, item):
        return self._run('episode', item)

    def ping(self):
        try:
            return bool(self.scraper.ping())
        except Exception:
            return False

    def __repr__(self):
        return '<ScraperProvider %s>' % self.id


def bridged():
    """Every enabled built-in scraper, as providers."""
    out = []
    for scraper in scraper_registry.enabled():
        try:
            out.append(ScraperProvider(scraper))
        except Exception as exc:
            kodi.error('could not bridge scraper %s: %s' % (scraper, exc))
    return out
