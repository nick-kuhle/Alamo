# -*- coding: utf-8 -*-
"""Small wrapper around the Kodi API so the rest of the code stays clean."""
import sys
import os
import json

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_VERSION = ADDON.getAddonInfo('version')
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))
PROFILE_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
MEDIA_PATH = os.path.join(ADDON_PATH, 'resources', 'media')

HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else -1


def ensure_profile():
    if not os.path.isdir(PROFILE_PATH):
        os.makedirs(PROFILE_PATH)
    return PROFILE_PATH


def media(name):
    return os.path.join(MEDIA_PATH, name)


def setting(key, default=''):
    try:
        value = ADDON.getSetting(key)
    except Exception:
        return default
    return value if value not in (None, '') else default


def setting_bool(key, default=False):
    value = setting(key, '')
    if value == '':
        return default
    return value.lower() == 'true'


def setting_int(key, default=0):
    try:
        return int(float(setting(key, default)))
    except Exception:
        return default


def set_setting(key, value):
    try:
        ADDON.setSetting(key, str(value))
    except Exception:
        pass


def open_settings():
    ADDON.openSettings()


def localize(string_id, fallback=''):
    try:
        text = ADDON.getLocalizedString(string_id)
    except Exception:
        text = ''
    return text or fallback


def log(message, level=xbmc.LOGDEBUG):
    xbmc.log('[%s] %s' % (ADDON_ID, message), level)


def error(message):
    log(message, xbmc.LOGERROR)


def notify(message, heading=None, icon=None, time=4000):
    xbmcgui.Dialog().notification(heading or ADDON_NAME, message,
                                  icon or media('icon.png'), time)


def ok(message, heading=None):
    xbmcgui.Dialog().ok(heading or ADDON_NAME, message)


def yesno(message, heading=None):
    return xbmcgui.Dialog().yesno(heading or ADDON_NAME, message)


def keyboard(heading, default=''):
    kb = xbmc.Keyboard(default, heading)
    kb.doModal()
    if kb.isConfirmed():
        return kb.getText().strip()
    return ''


def busy(on=True):
    xbmc.executebuiltin('ActivateWindow(busydialognocancel)' if on
                        else 'Dialog.Close(busydialognocancel)')


def execute(command):
    xbmc.executebuiltin(command)


def jsonrpc(method, **params):
    payload = {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}
    try:
        return json.loads(xbmc.executeJSONRPC(json.dumps(payload)))
    except Exception as exc:
        error('jsonrpc failed: %s' % exc)
        return {}
