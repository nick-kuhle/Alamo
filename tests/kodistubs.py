# -*- coding: utf-8 -*-
"""Minimal Kodi API stubs so the add-on can be exercised outside Kodi."""
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON_DIR = os.path.join(ROOT, 'plugin.video.alamo')
PROFILE = os.path.join(ROOT, '.testprofile')

SETTINGS = {'tmdb_key': '', 'tmdb_language': 'en-US', 'autoplay': 'true',
            'max_quality': '1080p', 'allow_cam': 'false', 'scrape_timeout': '10',
            'playlist_url': '', 'playlist_refresh': '30',
            'disabled_providers': '[]'}

LOGDEBUG = 0
LOGERROR = 4


def install():
    os.makedirs(PROFILE, exist_ok=True)

    xbmc = types.ModuleType('xbmc')
    xbmc.LOGDEBUG, xbmc.LOGINFO, xbmc.LOGWARNING, xbmc.LOGERROR = 0, 1, 2, 4
    xbmc.log = lambda msg, level=0: None
    xbmc.executebuiltin = lambda cmd: None
    xbmc.executeJSONRPC = lambda payload: '{"result":{"addons":[]}}'
    xbmc.sleep = lambda ms: None

    class Player(object):
        played = []

        def play(self, url, item=None):
            Player.played.append(url)
    xbmc.Player = Player

    class Keyboard(object):
        def __init__(self, default='', heading=''):
            self.text = default

        def doModal(self):
            pass

        def isConfirmed(self):
            return False

        def getText(self):
            return self.text
    xbmc.Keyboard = Keyboard

    xbmcvfs = types.ModuleType('xbmcvfs')
    xbmcvfs.translatePath = lambda path: path

    xbmcaddon = types.ModuleType('xbmcaddon')

    class Addon(object):
        def __init__(self, *args):
            pass

        def getAddonInfo(self, key):
            return {'id': 'plugin.video.alamo', 'name': 'The Alamo',
                    'version': '1.0.0', 'path': ADDON_DIR,
                    'profile': PROFILE}.get(key, '')

        def getSetting(self, key):
            return SETTINGS.get(key, '')

        def setSetting(self, key, value):
            SETTINGS[key] = value

        def getLocalizedString(self, sid):
            return ''

        def openSettings(self):
            pass
    xbmcaddon.Addon = Addon

    xbmcgui = types.ModuleType('xbmcgui')

    class ListItem(object):
        def __init__(self, label='', label2='', path=''):
            self._label, self._path, self._props, self._art = label, path, {}, {}

        def setLabel(self, label):
            self._label = label

        def getLabel(self):
            return self._label

        def setArt(self, art):
            self._art.update(art)

        def setProperties(self, props):
            self._props.update({k: str(v) for k, v in props.items()})

        def setProperty(self, key, value):
            self._props[key] = str(value)

        def getProperty(self, key):
            return self._props.get(key, '')

        def setMimeType(self, value):
            pass

        def setContentLookup(self, value):
            pass

        def getVideoInfoTag(self):
            raise RuntimeError('no infotag in stub')
    xbmcgui.ListItem = ListItem

    class _Window(object):
        def __init__(self, *args, **kwargs):
            self.props = {}

        def setProperty(self, key, value):
            self.props[key] = value

        def getProperty(self, key):
            return self.props.get(key, '')

        def getControl(self, cid):
            raise RuntimeError('no controls in stub')

        def setFocusId(self, cid):
            pass

        def doModal(self):
            pass

        def close(self):
            pass
    xbmcgui.WindowXML = _Window
    xbmcgui.WindowXMLDialog = _Window

    class Dialog(object):
        def notification(self, *args, **kwargs):
            pass

        def ok(self, *args):
            return True

        def yesno(self, *args):
            return False
    xbmcgui.Dialog = Dialog

    xbmcplugin = types.ModuleType('xbmcplugin')
    xbmcplugin.addDirectoryItem = lambda *a, **k: True
    xbmcplugin.endOfDirectory = lambda *a, **k: None
    xbmcplugin.setContent = lambda *a, **k: None
    xbmcplugin.setResolvedUrl = lambda *a, **k: None

    for module in (xbmc, xbmcgui, xbmcaddon, xbmcplugin, xbmcvfs):
        sys.modules[module.__name__] = module

    if ADDON_DIR not in sys.path:
        sys.path.insert(0, ADDON_DIR)
