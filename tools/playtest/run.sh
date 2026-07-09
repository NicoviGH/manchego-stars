#!/usr/bin/env bash
# Run an automated playtest scenario in mGBA (headed, but fully scripted).
#
#   tools/playtest/run.sh <scenario> [--keep-open]
#
# Logic scenarios (assert PASS/FAIL):  win | gameover | retreat | ch01win | titlecard
#   also: ch01 (entry asserts) | ch01lord | lordfloor | goodberry | clearprobe
#   (harness.lua's `scenarios` table is the authoritative full list)
#   ch02   -- ch2 (#22) ENTRY assertions off the ch02start checkpoint: 3 green chwinga on the
#             field, party at the deploy cap, the archer (fliers-vs-bows debut) + boss present.
#   ch02baxby -- (#23 recruit-persist) prove Baxby (the ch01-ending cutscene recruit) persists into
#             ch02: in the prep roster AND deployable + fighting on the ch02 map (force-deploy + strike).
# Stability scenarios (PASS/FAIL liveness over a run):
#   smoke | smoke_ch01   -- idle the party; catch crashes/soft-locks (#49)
#   smoke_ch02           -- the same net on ch02 (loads ch02start; catches a cutscene soft-lock)
#   clear | clear_ch01   -- greedy clear-bot plays to a win (#60)
#   clear_ch02           -- rout ch02 (DefeatAll) keeping the chwinga alive, then verify all 3
#                           chwinga charm-gifts (CHECK_ALIVE -> GIVEITEMTO) reach leader/convoy (#22)
#   fuzz  | fuzz_ch01    -- SEEDED random-input soak (#49); set PT_SEED=N (default 1) to
#                           pick the seed; a FAIL prints the seed so PT_SEED=N replays it
#   llm                  -- LLM-player commander on the prologue (#63): the harness
#                           handshakes with an EXTERNAL sidecar over PT_LLM_DIR (default
#                           /tmp/playtest-llm-handshake). Start the sidecar first:
#                             python3 tools/playtest/llm_player.py serve \
#                                 --dir /tmp/playtest-llm-handshake \
#                                 --transcript tools/playtest/transcripts/prologue.json
#                           (prologue.json is MINTED by the first --record run; until then
#                           replay mode has nothing to serve -- see transcripts/README.md.)
#                           Replay-only by default (zero LLM cost); add --record + env
#                           knobs (PT_PROVIDER=openai for a free local Ollama model,
#                           PT_MODEL, PT_BASE_URL) to record a fresh transcript. When
#                           the run ends this script touches <dir>/stop: the sidecar
#                           drains, saves its transcript, and exits on its own.
# Recording scenarios (drop motion frames for a review GIF):
#   recordscene   -- GENERIC cutscene recorder: records ANY dialogue cutscene, no new Lua.
#                    Env: PT_STATE=<checkpoint> PT_TAG=<frametag> PT_UNTIL=prep|title|chapter
#                    [PT_SPEED=normal|fast] [PT_MAXFRAMES=6000] [PT_PRESSEVERY=60] [PT_SHOTEVERY=4]
#                      PT_STATE=ch02intro PT_TAG=intro PT_UNTIL=prep tools/playtest/run.sh recordscene
#                    ONE loop (recordCutscene in harness.lua) does the work. recordending and
#                    recordch02intro are named PRESETS over it (a checkpoint + fixed params).
#                    The rest are NOT cutscene recorders and stay separate: recordopening /
#                    recordch01 replay a lead-in instead of loading a checkpoint; scenes /
#                    record / recordch01trail / recordch02map / recordch02combat drive gameplay
#                    (boot, unit moves, combat) -- different tools, not duplication.
#   recordending  -- the ch01 "Rolling Cheddar" outro cutscene (frames tagged "end"); preset over recordscene
#   recordprep    -- the Preparations + Pick Units deploy screen (frames "prep")
#   recordrbg     -- RBG's custom battle anim ("rbg"); loads the rbgch01 checkpoint
#   recordanim    -- ANY cast member's battle anim on a `make TESTCH=1` ROM: New Game boots
#                    STRAIGHT into the Ch1 sandbox (whole cast + foes pre-deployed), so
#                    boot->fire ~30s, no prologue grind / lord-select / save-state. Pick the
#                    unit with PT_CHAR=<id> (default prof-rbg): braulo marty meesmickle wolfram
#                    prof-rbg rootis sclorbo pinky. Frames are tagged <id>, so:
#                      PT_CHAR=braulo tools/playtest/run.sh recordanim
#                      tools/playtest/make_gif.py recordanim braulo --name braulo-anim --open
#                    A staff-only unit (sclorbo) FAILs cleanly: no attack = no combat anim.
#                    Build TESTCH=1 first. (recordrbgtest is the back-compat alias for RBG.)
#   recordch01trail / recordlord / recordlordfast / recordch01 / recordopening /
#   record / scenes / scenesch01 / bootobserve -- other scenes (no checkpoint: these
#   replay their full lead-in at 60fps, so they are the slowest captures)
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

# LLM-player handshake dir (#63): fresh req/resp files per run -- a stale resp-1.json
# from the last run would satisfy the first poll instantly with old orders.
LLM_DIR="${PT_LLM_DIR:-/tmp/playtest-llm-handshake}"
if [ "$SCENARIO" = "llm" ]; then
    mkdir -p "$LLM_DIR"
    rm -f "$LLM_DIR"/req-*.json "$LLM_DIR"/resp-*.json "$LLM_DIR"/*.tmp "$LLM_DIR/stop"
fi

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
PLAYTEST_SEED = "${PT_SEED:-1}"
PLAYTEST_CHAR = "${PT_CHAR:-}"
PLAYTEST_HOST_CHAPTER = ${PT_HOST_CHAPTER:-1}
PLAYTEST_LLMDIR = "$LLM_DIR"
PLAYTEST_STATE = "${PT_STATE:-}"
PLAYTEST_TAG = "${PT_TAG:-}"
PLAYTEST_UNTIL = "${PT_UNTIL:-}"
PLAYTEST_SPEED = "${PT_SPEED:-}"
PLAYTEST_MAXFRAMES = "${PT_MAXFRAMES:-}"
PLAYTEST_PRESSEVERY = "${PT_PRESSEVERY:-}"
PLAYTEST_SHOTEVERY = "${PT_SHOTEVERY:-}"
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
    recordending) BUILDER=ckpt_seize;     CKPT=seize ;;
    recordprep)   BUILDER=ckpt_prep;      CKPT=prep ;;
    recordsupply) BUILDER=ckpt_lordpinky; CKPT=lordpinky ;;
    recordrescue) BUILDER=ckpt_prep;      CKPT=prep ;;
    recordtrade)  BUILDER=ckpt_prep;      CKPT=prep ;;
    recordfix)    BUILDER=ckpt_prep;      CKPT=prep ;;
    recordrbg)    BUILDER=ckpt_rbgch01;   CKPT=rbgch01 ;;
    # ch02 (#22) scenarios LOAD the ch02start state (the real ch00->ch01->ch02 chain, paid once).
    ch02|smoke_ch02|clear_ch02|ch02baxby|recordch02map|recordch02combat|recordch02ending) BUILDER=ckpt_ch02start; CKPT=ch02start ;;
    # recordch02intro needs its OWN checkpoint (ckpt_ch02intro, harness.lua) saved just BEFORE the
    # ch02 opening plays -- ckpt_ch02start is captured at turn 1, after the opening is already over.
    recordch02intro) BUILDER=ckpt_ch02intro; CKPT=ch02intro ;;
    # recordscene (generic cutscene recorder): PT_STATE names the checkpoint; its builder is
    # ckpt_<PT_STATE> by convention (matches every ckpt_* above). e.g. PT_STATE=ch02intro.
    recordscene) CKPT="${PT_STATE:?recordscene needs PT_STATE=<checkpoint> (e.g. PT_STATE=ch02intro)}"; BUILDER="ckpt_${PT_STATE}" ;;
esac
if [ -n "$BUILDER" ]; then
    if [ ! -f "$STATE_DIR/$CKPT.ss" ] || [ "$(cat "$STATE_DIR/$CKPT.romhash" 2>/dev/null || true)" != "$ROMHASH" ]; then
        echo "== checkpoint '$CKPT' missing/stale -> building at top speed (240fps) =="
        run_mgba "$BUILDER" 240 0 900   # ch02start plays the whole ch00->ch01->ch02 chain
        case "$VERDICT" in
            *PASS*) echo "$ROMHASH" > "$STATE_DIR/$CKPT.romhash" ;;
            *) echo "checkpoint build FAILED -- aborting"; exit 1 ;;
        esac
    else
        echo "== checkpoint '$CKPT' valid for rom $ROMHASH -> loading =="
    fi
fi

# Main run: record* at 60fps (faithful motion); everything else at 240fps (top speed).
# The checkpoint-backed record* scenarios (table above) skip the grind; the rest replay
# their full lead-in and simply have to fit the record deadline.
FPS=240; VSYNC=0; DEADLINE_S=420
case "$SCENARIO" in record*) FPS=60; VSYNC=1; DEADLINE_S=300 ;; esac
# smoke_* / fuzz_* / clear_ch02 play a full chapter (lead-in + a long soak) -> longer
# wall. recordch02ending routs the whole band, so it needs the same headroom. llm waits
# wall-clock on the sidecar EVERY turn (18 turns x 90s handshake budget), and a --record run
# against a slow local model legitimately uses it -- so its deadline covers the harness's own
# worst case instead of killing a healthy run.
case "$SCENARIO" in smoke*|fuzz*|clear_ch02|recordch02ending) DEADLINE_S=600 ;; llm) DEADLINE_S=2100 ;; esac
# PT_FPS overrides the rate. 60fps+videoSync is only needed to capture smooth cutscene
# FADES; verification captures of static text/boxes (sign, death quote) read fine at top
# speed, so `PT_FPS=240 ... recordfix` runs ~4x faster.
if [ -n "${PT_FPS:-}" ]; then FPS="$PT_FPS"; [ "$PT_FPS" -ge 240 ] && VSYNC=0; fi
run_mgba "$SCENARIO" "$FPS" "$VSYNC" "$DEADLINE_S"
# Tell the sidecar the run is over: serve() drains any pending request, saves its
# transcript (record mode), and exits -- without this it polls forever and a recorded
# transcript would only be saved by a clean Ctrl-C.
if [ "$SCENARIO" = "llm" ]; then touch "$LLM_DIR/stop"; fi
case "$VERDICT" in *PASS*) exit 0 ;; *) exit 1 ;; esac
