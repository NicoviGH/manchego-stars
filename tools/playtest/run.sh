#!/usr/bin/env bash
# Run an automated ch00 playtest scenario in mGBA (headed, but fully scripted).
#
#   tools/playtest/run.sh win|gameover|retreat [--keep-open]
#
# Requires the mGBA 0.11+ nightly (has --script); auto-downloads it into
# tools/emulator/mGBA-dev.app on first run. Results land in
# /tmp/playtest-<scenario>/ (log + milestone screenshots); exit code 0 = PASS.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
APP="$REPO/tools/emulator/mGBA-dev.app/Contents/MacOS/mGBA"
ROM="$REPO/fireemblem8u/fireemblem8.gba"
SCENARIO="${1:?usage: run.sh win|gameover|retreat}"
KEEP_OPEN="${2:-}"

OUT="/tmp/playtest-$SCENARIO"
LOG="$OUT/playtest.log"
rm -rf "$OUT" && mkdir -p "$OUT"

if [ ! -x "$APP" ]; then
    echo "mGBA dev build missing; downloading nightly..."
    curl -fsSL -o /tmp/mgba-nightly.dmg "https://s3.amazonaws.com/mgba/mGBA-build-latest-macos.dmg"
    VOL=$(hdiutil attach /tmp/mgba-nightly.dmg -nobrowse | awk -F'\t' '/\/Volumes\//{print $NF}')
    mkdir -p "$REPO/tools/emulator"
    cp -R "$VOL/mGBA.app" "$REPO/tools/emulator/mGBA-dev.app"
    hdiutil detach "$VOL" -quiet
fi
[ -f "$ROM" ] || { echo "ROM not built; run make first" >&2; exit 2; }

python3 "$HERE/gen_symbols.py"

# Wrapper sets the harness globals (mGBA --script takes no arguments).
WRAPPER="$OUT/wrapper.lua"
cat > "$WRAPPER" <<EOF
PLAYTEST_DIR = "$HERE"
PLAYTEST_SCENARIO = "$SCENARIO"
PLAYTEST_LOG = "$LOG"
PLAYTEST_SHOTDIR = "$OUT"
dofile("$HERE/harness.lua")
EOF

pkill -9 -i mgba 2>/dev/null || true
rm -f "$REPO/fireemblem8u/fireemblem8.sav"   # fresh save: New Game is the default path

"$APP" --script "$WRAPPER" \
    -C mute=1 -C fpsTarget=240 -C audioSync=0 -C videoSync=0 \
    "$ROM" >"$OUT/mgba-stdout.log" 2>&1 &
MGBA_PID=$!

echo "running scenario '$SCENARIO' (mGBA pid $MGBA_PID); polling $LOG"
DEADLINE=$((SECONDS + 420))
VERDICT=""
while [ $SECONDS -lt $DEADLINE ]; do
    if [ -f "$LOG" ] && grep -q "RESULT:" "$LOG"; then
        VERDICT=$(grep "RESULT:" "$LOG" | tail -1)
        break
    fi
    if ! kill -0 "$MGBA_PID" 2>/dev/null; then
        VERDICT="RESULT: ERROR -- mGBA exited early"
        break
    fi
    sleep 3
done
[ -n "$VERDICT" ] || VERDICT="RESULT: ERROR -- timed out after 420s"

if [ "$KEEP_OPEN" != "--keep-open" ]; then
    kill "$MGBA_PID" 2>/dev/null || true
fi

echo "----------------------------------------"
cat "$LOG" 2>/dev/null || echo "(no log produced)"
echo "----------------------------------------"
echo "$VERDICT"
echo "artifacts: $OUT"
case "$VERDICT" in *PASS*) exit 0 ;; *) exit 1 ;; esac
