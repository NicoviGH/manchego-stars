#!/usr/bin/env bash
# Run an automated playtest scenario in mGBA (headed, but fully scripted).
#
#   tools/playtest/run.sh <scenario> [--keep-open]
#
# Logic scenarios (assert PASS/FAIL):  win | gameover | retreat | ch01win | titlecard
# Recording scenarios (drop motion frames for a review GIF):
#   recordending  -- the ch01 "Rolling Cheddar" outro cutscene (frames tagged "end")
#   recordprep    -- the Preparations + Pick Units deploy screen (frames "prep")
#   recordch01trail / recordlord / recordch01 / record / scenes -- other scenes
#
# CHECKPOINTS (fast playtest, viewable spot-check): record scenarios load a save state
# built ONCE at top speed (240fps) by a ckpt_* scenario, then replay JUST that section
# at 60fps so the motion is faithful and watchable. run.sh does this automatically --
# it builds the checkpoint (if missing or stale for this ROM build) then runs the record
# scenario. States live in tools/playtest/states/ (gitignored, ROM-hash-stamped). So the
# slow full playthrough is paid once per build; later spot-checks load the state instantly.
#
# To turn recorded frames into a GIF and show Nicolas (he can't see inline renders):
#   tools/playtest/make_gif.py <scenario> <tag> --name <basename> --open
#   e.g. tools/playtest/make_gif.py recordending end --name ch01-ending --fps 15 --open
#
# Requires the mGBA 0.11+ nightly (has --script); auto-downloads it into
# tools/emulator/mGBA-dev.app on first run. Results land in /tmp/playtest-<scenario>/.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
APP="$REPO/tools/emulator/mGBA-dev.app/Contents/MacOS/mGBA"
ROM="$REPO/fireemblem8u/fireemblem8.gba"
SCENARIO="${1:?usage: run.sh <scenario>  (see header: win|ch01win|recordending|recordprep|...)}"
KEEP_OPEN="${2:-}"
STATE_DIR="$HERE/states"
mkdir -p "$STATE_DIR"

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
pkill -9 -i mgba 2>/dev/null || true
ROMHASH=$(shasum "$ROM" | cut -c1-12)

# run_mgba <scenario> <fps> <vsync> <deadline_s>  -> echoes log, sets global VERDICT.
run_mgba() {
    local scen=$1 fps=$2 vsync=$3 deadline=$4
    local out="/tmp/playtest-$scen" log
    log="$out/playtest.log"
    rm -rf "$out" && mkdir -p "$out"
    local wrapper="$out/wrapper.lua"
    cat > "$wrapper" <<EOF
PLAYTEST_DIR = "$HERE"
PLAYTEST_SCENARIO = "$scen"
PLAYTEST_LOG = "$log"
PLAYTEST_SHOTDIR = "$out"
PLAYTEST_STATEDIR = "$STATE_DIR"
dofile("$HERE/harness.lua")
EOF
    rm -f "$REPO/fireemblem8u/fireemblem8.sav"   # fresh save: New Game is the default path
    "$APP" --script "$wrapper" \
        -C mute=1 -C fpsTarget="$fps" -C audioSync=0 -C videoSync="$vsync" \
        "$ROM" >"$out/mgba-stdout.log" 2>&1 &
    local pid=$!
    echo "running '$scen' (pid $pid, ${fps}fps); polling $log"
    local end=$((SECONDS + deadline))
    VERDICT=""
    while [ $SECONDS -lt $end ]; do
        if [ -f "$log" ] && grep -q "RESULT:" "$log"; then VERDICT=$(grep "RESULT:" "$log" | tail -1); break; fi
        if ! kill -0 "$pid" 2>/dev/null; then VERDICT="RESULT: ERROR -- mGBA exited early"; break; fi
        sleep 3
    done
    [ -n "$VERDICT" ] || VERDICT="RESULT: ERROR -- timed out after ${deadline}s"
    if [ "$KEEP_OPEN" != "--keep-open" ]; then kill "$pid" 2>/dev/null || true; fi
    echo "----------------------------------------"
    cat "$log" 2>/dev/null || echo "(no log produced)"
    echo "----------------------------------------"
    echo "$VERDICT"
    echo "artifacts: $out"
}

# Checkpoint dependency: a record scenario loads a save state built fast by a ckpt_*
# scenario. Build it (240fps) if the state is missing or was made for a different ROM.
BUILDER=""; CKPT=""
case "$SCENARIO" in
    recordending) BUILDER=ckpt_seize; CKPT=seize ;;
    recordprep)   BUILDER=ckpt_prep;  CKPT=prep ;;
esac
if [ -n "$BUILDER" ]; then
    if [ ! -f "$STATE_DIR/$CKPT.ss" ] || [ "$(cat "$STATE_DIR/$CKPT.romhash" 2>/dev/null || true)" != "$ROMHASH" ]; then
        echo "== checkpoint '$CKPT' missing/stale -> building at top speed (240fps) =="
        run_mgba "$BUILDER" 240 0 600
        case "$VERDICT" in
            *PASS*) echo "$ROMHASH" > "$STATE_DIR/$CKPT.romhash" ;;
            *) echo "checkpoint build FAILED -- aborting"; exit 1 ;;
        esac
    else
        echo "== checkpoint '$CKPT' valid for rom $ROMHASH -> loading =="
    fi
fi

# Main run: record* at 60fps (faithful motion); everything else at 240fps (top speed).
# record* now LOADS a checkpoint (no grind), so its deadline is short.
FPS=240; VSYNC=0; DEADLINE_S=420
case "$SCENARIO" in record*) FPS=60; VSYNC=1; DEADLINE_S=300 ;; esac
run_mgba "$SCENARIO" "$FPS" "$VSYNC" "$DEADLINE_S"
case "$VERDICT" in *PASS*) exit 0 ;; *) exit 1 ;; esac
