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
REPO_URL = 'https://nick-kuhle.github.io/Alamo/'


def addon_version(addon_id):
    tree = ET.parse(os.path.join(ROOT, addon_id, 'addon.xml'))
    return tree.getroot().get('version')


# The repository add-on is versioned in lockstep with the plugin, so a release
# always moves the plugin zip, the repository zip and addons.xml together.
REPO_VERSION = addon_version('plugin.video.alamo')

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
    # a stable, version-less copy so documentation links never go stale
    shutil.copy(path, os.path.join(target_dir, '%s.zip' % addon_id))
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


LANDING = '''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>The Alamo - Kodi repository</title>
<style>
body{{background:#07070b;color:#f4f4f6;font-family:-apple-system,Helvetica,Arial,sans-serif;
     max-width:760px;margin:0 auto;padding:56px 24px;line-height:1.65}}
h1{{font-size:34px;letter-spacing:1px;margin:0 0 4px}} h1 span{{color:#e8b44a}}
p.sub{{color:#9a9aa6;margin-top:0}}
code{{background:#14141c;padding:2px 7px;border-radius:4px;color:#e8b44a}}
a{{color:#e8b44a}}
.box{{background:#0d0d14;border:1px solid #22222c;border-radius:10px;padding:20px 24px;margin:26px 0}}
ul.files{{list-style:none;padding:0}} ul.files li{{padding:3px 0}}
</style></head><body>
<h1>THE <span>ALAMO</span></h1>
<p class="sub">A Kodi 21+ video add-on. Sports, TV and Movies - nothing else.</p>
<div class="box"><b>Source URL for Kodi</b><br><code>{url}</code></div>
<ol>
<li>Kodi &rarr; <b>Settings &rarr; System &rarr; Add-ons</b> &rarr; turn on <b>Unknown sources</b>.</li>
<li><b>Settings &rarr; File manager &rarr; Add source</b> &rarr; paste the URL above &rarr; name it <code>alamo</code>.</li>
<li><b>Add-ons &rarr; Install from zip file &rarr; alamo &rarr; repository.alamo &rarr; repository.alamo-{repo_ver}.zip</b>.</li>
<li><b>Add-ons &rarr; Install from repository &rarr; The Alamo Repository &rarr; Video add-ons &rarr; The Alamo</b>.</li>
</ol>
<p>Direct downloads (if you would rather skip the repository):</p>
<ul class="files">{links}</ul>
<p>The Alamo hosts no content and contains no scrapers. Playable links come only
from provider plug-ins you install yourself.</p>
</body></html>
'''


def write_indexes():
    """Kodi browses HTTP sources by parsing <a href> links, and GitHub Pages
    does not generate directory listings - so we write our own everywhere."""
    downloads = []
    for entry in sorted(os.listdir(DIST)):
        folder = os.path.join(DIST, entry)
        if not os.path.isdir(folder):
            continue
        rows = []
        for name in sorted(os.listdir(folder)):
            rows.append('<li><a href="%s">%s</a></li>' % (name, name))
            if name.endswith('.zip'):
                downloads.append('<li><a href="%s/%s">%s</a></li>'
                                 % (entry, name, name))
        with open(os.path.join(folder, 'index.html'), 'w') as handle:
            handle.write('<html><head><meta charset="utf-8"><title>%s</title>'
                         '</head><body><h1>%s</h1><ul>%s</ul></body></html>\n'
                         % (entry, entry, ''.join(rows)))

    # the root needs links to every subfolder AND every loose file, or Kodi's
    # file manager shows an empty source
    root_rows = []
    for entry in sorted(os.listdir(DIST)):
        if entry == 'index.html':
            continue
        suffix = '/' if os.path.isdir(os.path.join(DIST, entry)) else ''
        root_rows.append('<li><a href="%s%s">%s%s</a></li>'
                         % (entry, suffix, entry, suffix))
    landing = LANDING.format(url=REPO_URL, repo_ver=REPO_VERSION,
                             links=''.join(downloads))
    landing = landing.replace('</body>',
                              '<hr style="border-color:#22222c;margin:32px 0">'
                              '<ul class="files">%s</ul></body>'
                              % ''.join(root_rows))
    with open(os.path.join(DIST, 'index.html'), 'w') as handle:
        handle.write(landing)
    with open(os.path.join(DIST, '.nojekyll'), 'w') as handle:
        handle.write('')
    print('wrote index.html for the root and every add-on folder')


def check_versions():
    """Everything ships together: refuse to build a mixed-version repository."""
    versions = {a: addon_version(a) for a in ADDONS}
    versions[REPO_ID] = REPO_VERSION
    if len(set(versions.values())) != 1:
        raise SystemExit('version mismatch, bump them together: %s' % versions)
    print('all add-ons at version', REPO_VERSION)


def main():
    check_versions()
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
    write_indexes()
    print('addons.xml md5', digest)
    print('\ndist/ is ready - upload it to', REPO_URL)


if __name__ == '__main__':
    main()
