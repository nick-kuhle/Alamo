#!/usr/bin/env bash
# Ship a release: bump -> test -> build -> commit -> tag -> push.
#
#   ./tools/release.sh 1.0.2 "Fix the sources dialog"
#
# CI then republishes gh-pages, so the source, the zips, addons.xml and the
# GitHub Release all move together. Nothing is ever half-shipped.
set -euo pipefail

VERSION="${1:-}"
MESSAGE="${2:-Release v${VERSION}}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ADDON_XML="$ROOT/plugin.video.alamo/addon.xml"

if [[ -z "$VERSION" ]]; then
  echo "usage: $0 <version> [message]     e.g. $0 1.0.2 \"Fix sources dialog\"" >&2
  exit 1
fi
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "version must look like 1.0.2" >&2
  exit 1
fi

cd "$ROOT"

CURRENT=$(python3 -c "import xml.etree.ElementTree as ET;print(ET.parse('$ADDON_XML').getroot().get('version'))")
echo "==> $CURRENT -> $VERSION"

if git rev-parse "v$VERSION" >/dev/null 2>&1; then
  echo "tag v$VERSION already exists" >&2
  exit 1
fi

# 1. bump the plugin (the repository add-on follows it automatically)
python3 - "$VERSION" <<'PY'
import re, sys
version = sys.argv[1]
path = 'plugin.video.alamo/addon.xml'
text = open(path).read()
text = re.sub(r'(<addon[^>]*?\sversion=")[^"]+(")', r'\g<1>%s\g<2>' % version,
              text, count=1)
open(path, 'w').write(text)
print('bumped', path)
PY

# 2. changelog
{
  echo ""
  echo "v$VERSION"
  echo "- $MESSAGE"
} >> changelog.txt
cp changelog.txt plugin.video.alamo/changelog.txt

# 3. regenerate everything that is generated, then test
python3 tools/build_skin.py >/dev/null
python3 tests/test_smoke.py
python3 tools/build_repo.py

# 4. commit, tag, push
git add -A
git commit -m "v$VERSION - $MESSAGE"
git tag -a "v$VERSION" -m "The Alamo v$VERSION"
git push origin main
git push origin "v$VERSION"

cat <<EOF

==> v$VERSION pushed.
    CI: https://github.com/nick-kuhle/Alamo/actions
    Live in a minute or two at https://nick-kuhle.github.io/Alamo/addons.xml

    In Kodi: Add-ons -> right-click The Alamo Repository -> Check for updates,
    then Add-ons -> right-click The Alamo -> Update (or Information -> Update).
EOF
