#!/usr/bin/env bash
# One-command builds of the two flavours of the ROM (#37/#43).
#
#   tools/build.sh test      fast dev build: straight-to-map boot, NO opener.
#                            Boot cut applied; New Game drops onto the map.
#   tools/build.sh dist      distribution build: WITH the #43 opening montage
#                            (Frostmaiden lore crawl + Ten Towns map tour), then
#                            stamps a dated copy into dist/.
#
# WHY a wrapper: `make` ALWAYS re-runs build_campaign.py, adding --montage ONLY
# when MONTAGE=1 is set. So `build_campaign.py --montage` followed by a PLAIN
# `make` silently re-runs the generator WITHOUT --montage and clobbers the
# montage back out -> a byte-identical no-opener ROM. The montage flavour MUST
# be built as a single `make MONTAGE=1`; this script is the supported way to do
# it (and to not have to remember the flag).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
CAMPAIGN="${CAMPAIGN:-rime-of-the-frostmaiden}"

MODE="${1:-}"
case "$MODE" in
    test|dist) ;;
    *) echo "usage: tools/build.sh test|dist" >&2; exit 2 ;;
esac

# The decomp ships Linux-only `#!/bin/python3` shebangs in fireemblem8u/scripts;
# setup-toolchain.sh rewrites them for macOS, but ANY `git checkout` inside the
# submodule (e.g. restore_vanilla_sources, a manual reset) reverts them and the
# next build dies on `bad interpreter`. Re-apply the fix here -- idempotent.
if [ "$(uname)" = "Darwin" ]; then
    while IFS= read -r f; do
        sed -i '' '1s|^#!/bin/python3|#!/usr/bin/env python3|' "$f"
    done < <(grep -rl '^#!/bin/python3' fireemblem8u/scripts 2>/dev/null || true)
fi

if [ "$MODE" = "test" ]; then
    echo ">> test build (no montage)"
    make CAMPAIGN="$CAMPAIGN"
    echo ">> built fireemblem8u/fireemblem8.gba (test: straight-to-map boot)"
    exit 0
fi

echo ">> dist build (MONTAGE=1: with the #43 opening montage)"
make CAMPAIGN="$CAMPAIGN" MONTAGE=1

# Versioned dist stamp (see docs/decisions.md §Distribution & Scope -> Versioning).
# Scheme: v0.<chapters-playable>.<patch>, staying 0.x until the full MVP ships as v1.0.
# "Alpha" remains the title-screen/README label for the whole 0.x phase; the FILE is versioned.
VERSION="$(tr -d ' \t\n\r' < VERSION)"
OUT="dist/ManchegoStars-v${VERSION}-$(date +%Y-%m-%d).gba"
mkdir -p dist
cp fireemblem8u/fireemblem8.gba "$OUT"
echo ">> stamped $OUT"
echo "   md5: $(md5 -q "$OUT" 2>/dev/null || md5sum "$OUT" | cut -d' ' -f1)"
echo "   (a montage ROM's md5 MUST differ from the no-opener 142971e3 build)"
echo ">> to ship: git tag v${VERSION} && git push --tags"
