#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Packages The Alamo into installable zips plus a Kodi repository.

Run:  python3 tools/build_repo.py
Output in dist/:
    plugin.video.alamo/plugin.video.alamo-<ver>.zip
    script.alamo.provider.example/...zip
    repository.alamo/repository.alamo-<ver>.zip
    addons.xml, addons.xml.md5
Host dist/ on GitHub Pages and point Kodi's file manager at that URL.
"""
import os
import re
import shutil
import hashlib
import zipfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
DIST = os.path.join(ROOT, 'dist')

REPO_ID = 'repository.alamo'
REPO_VERSION = '1.0.0'
REPO_URL = 'https://nick-kuhle.github.io/Alamo/'

ADDONS = ['plugin.video.alamo', 'script.alamo.provider.example']
EXCLUDE = re.compile(r'(__pycache__|\.pyc$|\.DS_Store|\.testprofile)')


def clean():
    shutil.rmtree(DIST, ignore_errors=True)
    os.makedirs(DIST)


def zip_addon(addon_id, source_dir, version):
    target_dir = os.path.join(DIST, addon_id)
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, '%s-%s.zip' % (addon_id, version))
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if not EXCLUDE.search(d)]
            for name in files:
                full = os.path.join(root, name)
                if EXCLUDE.search(full):
                    continue
                rel = os.path.relpath(full, os.path.dirname(source_dir))
                archive.write(full, os.path.join(addon_id, *rel.split(os.sep)[1:]))
    for extra in ('icon.png', 'fanart.jpg'):
        candidate = os.path.join(source_dir, 'resources', 'media', extra)
        if os.path.exists(candidate):
            shutil.copy(candidate, os.path.join(target_dir, extra))
    changelog = os.path.join(source_dir, 'changelog.txt')
    if os.path.exists(changelog):
        shutil.copy(changelog, target_dir)
    print('packed', os.path.relpath(path, ROOT))
    return path


def repo_addon_xml():
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<addon id="{rid}" name="The Alamo Repository" version="{ver}" provider-name="Alamo Team">
    <extension point="xbmc.addon.repository" name="The Alamo Repository">
        <dir>
            <info compressed="false">{url}addons.xml</info>
            <checksum>{url}addons.xml.md5</checksum>
            <datadir zip="true">{url}</datadir>
        </dir>
    </extension>
    <extension point="xbmc.addon.metadata">
        <summary lang="en_GB">Install and update The Alamo</summary>
        <description lang="en_GB">Repository for The Alamo video add-on and its source providers.</description>
        <platform>all</platform>
        <license>GPL-3.0-or-later</license>
    </extension>
</addon>
'''.format(rid=REPO_ID, ver=REPO_VERSION, url=REPO_URL)


def build_repo_addon():
    staging = os.path.join(DIST, '_staging', REPO_ID)
    os.makedirs(staging, exist_ok=True)
    with open(os.path.join(staging, 'addon.xml'), 'w') as handle:
        handle.write(repo_addon_xml())
    icon = os.path.join(ROOT, 'plugin.video.alamo', 'resources', 'media', 'icon.png')
    if os.path.exists(icon):
        os.makedirs(os.path.join(staging, 'resources', 'media'), exist_ok=True)
        shutil.copy(icon, os.path.join(staging, 'resources', 'media', 'icon.png'))
    zip_addon(REPO_ID, staging, REPO_VERSION)
    return staging


def main():
    clean()
    roots = []
    for addon_id in ADDONS:
        source = os.path.join(ROOT, addon_id)
        tree = ET.parse(os.path.join(source, 'addon.xml'))
        version = tree.getroot().get('version')
        zip_addon(addon_id, source, version)
        roots.append(tree.getroot())

    staging = build_repo_addon()
    roots.append(ET.parse(os.path.join(staging, 'addon.xml')).getroot())

    addons = ET.Element('addons')
    for root in roots:
        addons.append(root)
    xml = ET.tostring(addons, encoding='unicode')
    xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + xml
    with open(os.path.join(DIST, 'addons.xml'), 'w') as handle:
        handle.write(xml)
    digest = hashlib.md5(xml.encode('utf-8')).hexdigest()
    with open(os.path.join(DIST, 'addons.xml.md5'), 'w') as handle:
        handle.write(digest)
    shutil.rmtree(os.path.join(DIST, '_staging'), ignore_errors=True)
    print('addons.xml md5', digest)
    print('\ndist/ is ready - upload it to', REPO_URL)


if __name__ == '__main__':
    main()
