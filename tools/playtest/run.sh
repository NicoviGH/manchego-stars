#!/usr/bin/env bash
# Run ONE automated playtest scenario in mGBA, fully scripted.
#
# A `kind: verdict` scenario runs HEADLESS (no window) under tools/emulator/mgba-headless --
# it asserts on memory and needs no pixels. `record` and `diagnostic` scenarios run HEADED,
# because their output IS the picture. PT_HEADED=1 forces headed; see #308.
#
#   tools/playtest/run.sh <scenario> [--keep-open]
#
# For a GROUP of scenarios use the matrix runner instead -- it builds each ROM
# configuration at most once and prints a verdict table:
#
#   make matrix                 # the merge gate
#   make matrix SUITE=ch04      # every ch04 scenario, one build
#   tools/playtest/matrix.py run --scenarios ch04moose,ch04snag
#
# WHAT A SCENARIO NEEDS -- its ROM configuration (`make` flag), its PT_HOST_CHAPTER,
# its checkpoint, and its fps/vsync/deadline -- is declared in tools/playtest/matrix.yaml
# and resolved here. So `run.sh ch04moose` sets PT_HOST_CHAPTER=5 by itself, and refuses
# outright if the tree holds a ROM that cannot host it. Setting PT_HOST_CHAPTER or PT_FPS
# by hand still overrides the manifest. The per-scenario notes below say what each one
# PROVES; the flags they mention are documentation, not something you have to type.
#
# Logic scenarios (assert PASS/FAIL):  win | gameover | retreat | ch01win | titlecard
#   also: ch01 (entry asserts) | ch01lord | lordfloor | goodberry | clearprobe
#   controller_turn -- #220 controller contract: no-prep boot -> move -> semantic Wait ->
#                      semantic End Phase -> verified enemy-phase return
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
#   smoke_ch03           -- stability net on ch03 (#23; PT_HOST_CHAPTER=4, needs CH03BOOT=1):
#                           boot -> idle-drive, catching a crash/soft-lock on load or in the cutscenes
#   clear_ch03           -- rout ch03 via real combat (#23; PT_HOST_CHAPTER=4, CH03BOOT=1): the grell's
#                           death raises EVFLAG_DEFEAT_BOSS -> assert the DefeatBoss win + ending fired
#   smoke_ch04           -- stability net on ch04 (#24; PT_HOST_CHAPTER=5, needs CH04BOOT=1)
#   clear_ch04           -- rout ch04 (DefeatAll) and film the NO-LUPIN fallback ending (#204;
#                           PT_HOST_CHAPTER=5, CH04BOOT=1): Pinky reads the trail, Meesmickle
#                           takes the dread. Lifts the fog onto the unit GRID first -- see
#                           liftFogOntoTheGrid in harness.lua for why zeroing vision is not enough
#   clear_ch04_parley    -- the same rout, but Marty parleys FIRST, so the ending's CHECK_EVENTID
#                           branches to the AUTHORED Lupin scene instead (same ROM/host)
#   ch04packmath         -- the Stage 5 balance question: kill 2 of the 5 generic wolves, THEN
#                           parley, and count the green allies. Answers whether LOAD1 brings the
#                           full five-wolf table back regardless of who died (it does)
#   attackprobe          -- diagnostic: why a clear-bot's blind Attack press lands on the wrong
#                           command row. Dumps vision range, every red's grid id + fog byte, the
#                           5x5 gBmMapUnit window, and photographs the open menu. Any hosted map
#   recordch04open       -- the two-BG Lonelywood opening in motion (#24; PT_HOST_CHAPTER=5, CH04BOOT=1)
#   recordch04reveal     -- the turn-2 wolf-pack reveal cutscene in motion (same ROM/host)
#   recordch04parley     -- Marty's Talk on the wolf pack + the green swap, in motion
#   ch04moose            -- the moose sighting is PLAYER-only: assert it skips the enemy phase
#                           and still fires when the party walks into the clearing (same ROM/host)
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
#   recordchain   -- the ch02 -> ch03 CHAIN (#23): routs ch02 at top speed off ch02start, fires the win,
#                    then records the ch02 ending -> MNC2(0x4) -> ch03 opening -> PREP (frames "chain").
#                      tools/playtest/run.sh recordchain
#                      tools/playtest/make_gif.py recordchain chain --name ch02-ch03-chain --open
#   recordprep    -- the Preparations + Pick Units deploy screen (frames "prep")
#   recordrbg     -- RBG's custom battle anim ("rbg"); loads the rbgch01 checkpoint
#   recordanim    -- ANY cast member's battle anim on a `make TESTCH=1` ROM: New Game boots
#                    STRAIGHT into the Ch1 sandbox (whole cast + foes pre-deployed), so
#                    boot->fire ~30s, no prologue grind / lord-select / save-state. Pick the
#                    unit with PT_CHAR=<id> (default prof-rbg): braulo marty meesmickle wolfram
#                    prof-rbg rootis sclorbo pinky lupin baxby basil sahnar. Frames tagged <id>:
#                      PT_CHAR=braulo tools/playtest/run.sh recordanim
#                      tools/playtest/make_gif.py recordanim braulo --name braulo-anim --open
#                    A staff-only unit (sclorbo) FAILs cleanly: no attack = no combat anim.
#                    Build TESTCH=1 first. (recordrbgtest is the back-compat alias for RBG.)
#   recordravisin -- Ravisin's live enemy status-screen portrait on the real ch05 map
#                    (needs CH05BOOT=1; proves raw pid 0xB8 -> dressed Riev portrait binding).
#   recordunitlist -- the map-menu "Unit" screen (Character list) on a `make TESTCH=1` ROM (#218):
#                    boots straight into the Ch1 sandbox with the whole cast deployed, opens the
#                    list semantically off gMapMenuItems[0] (overrideId 0x6E), shoots every page,
#                    and dumps the SMS geometry + the shared 0x40-slot VRAM budget before/after.
#                    FAILs if the two UseUnitSprite counters cross (later sprites overwrite earlier).
#                      tools/playtest/run.sh recordunitlist
#                      tools/playtest/make_gif.py recordunitlist unitlist --name unit-list
#   recordenemy   -- the ENEMY analogue of recordanim on the SAME TESTCH sandbox (#90): a
#                    reskinned enemy CLASS's battle anim, or a named RAW-PID creature's (#25).
#                    The sandbox deploys one hostile of each enemy_class_reskins slot plus one
#                    of each RAW_PID_BATTLE_ANIMS unit under its OWN pid; a harmless player
#                    baits the chosen foe into a counter-attack. Pick with
#                    PT_CHAR=<name|classid> (default kobold-grunt):
#                    kobold-grunt kobold-blade kobold-brute white-moose ravisin.
#                    Build TESTCH=1 first, e.g.:
#                      PT_CHAR=kobold-grunt tools/playtest/run.sh recordenemy
#                      tools/playtest/make_gif.py recordenemy kobold-grunt --name kobold-anim
#                      PT_CHAR=white-moose  tools/playtest/run.sh recordenemy
#                      PT_CHAR=ravisin      tools/playtest/run.sh recordenemy
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

ensure_headed_app() {
    [ -x "$APP" ] && return 0
    echo "mGBA dev build missing; downloading nightly..."
    curl -fsSL -o /tmp/mgba-nightly.dmg "https://s3.amazonaws.com/mgba/mGBA-build-latest-macos.dmg"
    VOL=$(hdiutil attach /tmp/mgba-nightly.dmg -nobrowse | awk -F'\t' '/\/Volumes\//{print $NF}')
    mkdir -p "$REPO/tools/emulator"
    cp -R "$VOL/mGBA.app" "$REPO/tools/emulator/mGBA-dev.app"
    hdiutil detach "$VOL" -quiet
}
[ -f "$ROM" ] || { echo "ROM not built; run make first" >&2; exit 2; }

# What this scenario needs -- ROM configuration, host chapter, checkpoint, fps/vsync/
# deadline -- comes from tools/playtest/matrix.yaml, which is the single source of that
# table (see matrix.py). run.sh owns "run ONE scenario in mGBA" and nothing else.
MX_RESOLVED="$(python3 "$HERE/matrix.py" resolve "$SCENARIO")" || {
    echo "run.sh: '$SCENARIO' has no row in tools/playtest/matrix.yaml" >&2; exit 2; }
eval "$MX_RESOLVED"

# Which mGBA runs a given invocation, decided by the manifest's `headless` field (#308).
#
# A headless scenario asserts on MEMORY -- INSPECT.units, activeMsg, flags -- and needs no
# pixels, so it runs with no window and stops costing Nicolas's attention. `record` and
# `diagnostic` scenarios, and the two verdict scenarios that also drop frames, declare
# `headless: false` and keep the Qt frontend, because their output IS the picture.
#
# TWO things mgba-headless cannot do, because it attaches no video renderer:
#   * emu:screenshot() null-derefs inside PNGWritePixels -- harness.lua skips it.
#   * emu:saveStateFile() returns false and writes an all-zeros file (measured: 397312
#     bytes of zeros). Every saveState() call site discards that return, so a CHECKPOINT
#     BUILDER run headless would mint a dead state, PASS on its own assertions, and get
#     its .romhash stamped VALID -- poisoning the checkpoint permanently.
# So the engine is chosen PER INVOCATION, not once: run_mgba takes it as an argument and
# the checkpoint builder below always passes `headed`.
HEADLESS_APP="$REPO/tools/emulator/mgba-headless"
HEADED_APP="$APP"
SCENARIO_HEADLESS=0
if [ -n "${MX_HEADLESS:-}" ] && [ "${PT_HEADED:-0}" = "0" ]; then
    if [ -x "$HEADLESS_APP" ]; then
        SCENARIO_HEADLESS=1
    else
        # Do NOT silently fall back to headed. Which engine ran is not in the verdict-cache
        # key, so a silent fallback would let a headed PASS be served for a headless run and
        # vice versa -- the exact collision the key exists to prevent. Refuse in 0s instead.
        echo "run.sh: '$SCENARIO' is declared headless but $HEADLESS_APP is not built." >&2
        echo "        Build it once:  tools/build_mgba_headless.sh   (~10 min)" >&2
        echo "        Or force the Qt frontend for this run:  PT_HEADED=1 tools/playtest/run.sh $SCENARIO" >&2
        exit 2
    fi
fi
[ "$SCENARIO_HEADLESS" = "1" ] || ensure_headed_app

# The most expensive failure in this repo is a scenario that FAILs because the tree
# holds the wrong ROM (a CH04BOOT=1 build cannot reach ch02's map). Refuse in 0s
# instead of timing out in 7 minutes. MX_SKIP_ROM_CHECK=1 opts out.
if [ -z "${MX_SKIP_ROM_CHECK:-}" ]; then
    python3 "$HERE/matrix.py" check-rom "$SCENARIO" || exit 2
fi

# ...and the SECOND way the ROM is wrong: right FLAGS, STALE CODE. run.sh launches whatever is
# on disk -- only matrix.py builds -- so editing build_campaign.py and reaching straight for
# run.sh re-runs the PREVIOUS binary and every observation from it is about the old build.
# Cost the session two runs and two rounds of Nicolas's attention on 2026-08-15 ("sounded like
# the same rumble", "nothing changed in that last run"): both were true, because nothing HAD
# changed. check-rom cannot see this -- the flags matched exactly.
if [ -z "${MX_SKIP_ROM_CHECK:-}" ]; then
    _stale=$(find "$REPO/tools/build_campaign.py" "$REPO/campaigns" \
                  -newer "$ROM" -type f 2>/dev/null | head -3)
    if [ -n "$_stale" ]; then
        echo "run.sh: the ROM is OLDER than campaign sources -- you would be testing the" >&2
        echo "        previous build. Newer than $ROM:" >&2
        echo "$_stale" | sed 's/^/          /' >&2
        echo "        Rebuild first, e.g.  make CAMPAIGN=<c> [FLAGS] fireemblem8.gba -j8" >&2
        echo "        (or run it through matrix.py, which builds). MX_SKIP_ROM_CHECK=1 opts out." >&2
        exit 2
    fi
fi

python3 "$HERE/gen_symbols.py"
# Clear a leftover emulator from an interrupted run of THIS scenario -- it would still hold
# the ROM this one is about to boot. Scoped to the scenario's own /tmp dir, NEVER `pkill -i
# mgba`: since #310 the matrix runs four scenarios at a time, and a blanket kill here meant
# every newly dispatched scenario SIGKILLed the siblings already running. Three of them died
# that way in one gate (ch01, ch04moose, ch04packmath), each at the exact second the pool
# started the next scenario, and each reported `mGBA exited early` as though the ROM were
# broken.
pkill -9 -f "/tmp/playtest-(ckpt_)?$SCENARIO/" 2>/dev/null || true
ROMHASH=$(shasum "$ROM" | cut -c1-12)

# Did the last run_mgba PASS? Classify in ONE place. This was four copies of a glob, and
# when the glob was wrong it was wrong four times -- including on the exit-code line, where a
# FAIL could have exited 0. Match the whole `RESULT: ...` line, never the bare word: VERDICT
# carries the failure REASON too, and a guard message that merely CONTAINED the word made a
# FAIL classify as a pass (#308).
verdict_passed() { case "$VERDICT" in *"RESULT: PASS"*) return 0 ;; *) return 1 ;; esac; }

# run_mgba <scenario> <fps> <vsync> <deadline_s> [headless|headed] [budget_fps]
#   -> echoes log, sets global VERDICT. The engine is an ARGUMENT because a checkpoint
#      builder must stay headed even when the scenario that needs it is headless.
run_mgba() {
    local scen=$1 fps=$2 vsync=$3 deadline=$4 mode=${5:-headed} budget_fps=${6:-$2}
    local app hl=0
    if [ "$mode" = "headless" ]; then app="$HEADLESS_APP"; hl=1; else app="$HEADED_APP"; ensure_headed_app; fi
    # Say which engine ran, every time. Which binary served an invocation decides whether
    # screenshots and saveStateFile work at all, and it was previously invisible -- the
    # checkpoint builder silently inheriting the headless engine is exactly the bug this
    # line makes impossible to miss (#308).
    echo "engine: $mode ($(basename "$app"))"
    local out="/tmp/playtest-$scen" log
    log="$out/playtest.log"
    rm -rf "$out" && mkdir -p "$out"
    # A DECLARED case (#314) has no function in harness.lua: its chapter YAML declares what
    # it proves and declared.py emits it here, fresh, for every run. Generated into the run
    # directory rather than committed -- a generated file in the tree is a second copy of the
    # chapter YAML, and a second copy can be stale.
    local case=""
    if python3 "$HERE/declared.py" emit "$scen" > "$out/case.lua" 2>"$out/case.err"; then
        case="$out/case.lua"
        echo "case: declared (from the chapter YAML)"
    else
        rm -f "$out/case.lua"
    fi
    local wrapper="$out/wrapper.lua"
    cat > "$wrapper" <<EOF
PLAYTEST_DIR = "$HERE"
PLAYTEST_SCENARIO = "$scen"
PLAYTEST_LOG = "$log"
PLAYTEST_SHOTDIR = "$out"
PLAYTEST_STATEDIR = "$STATE_DIR"
PLAYTEST_SEED = "${PT_SEED:-1}"
PLAYTEST_CHAR = "${PT_CHAR:-}"
PLAYTEST_ROUNDS = ${PT_ROUNDS:-1}
PLAYTEST_HOST_CHAPTER = ${PT_HOST_CHAPTER:-${MX_HOST_CHAPTER:-1}}
PLAYTEST_CHECKPOINT = "${CKPT:-}"
PLAYTEST_DIFFICULTY = "${PT_DIFFICULTY:-normal}"
PLAYTEST_LLMDIR = "$LLM_DIR"
PLAYTEST_STATE = "${PT_STATE:-}"
PLAYTEST_TAG = "${PT_TAG:-}"
PLAYTEST_UNTIL = "${PT_UNTIL:-}"
PLAYTEST_SPEED = "${PT_SPEED:-}"
PLAYTEST_MAXFRAMES = "${PT_MAXFRAMES:-}"
PLAYTEST_PRESSEVERY = "${PT_PRESSEVERY:-}"
PLAYTEST_SHOTEVERY = "${PT_SHOTEVERY:-}"
PLAYTEST_HEADLESS = "$hl"
PLAYTEST_CASE = "$case"
dofile("$HERE/harness.lua")
EOF
    rm -f "$REPO/fireemblem8u/fireemblem8.sav"   # fresh save: New Game is the default path
    # Muted by DEFAULT and deliberately: a scenario is watched, often many times, and at
    # 240fps the audio is a screech. `PT_SOUND=1` unmutes for the runs where the SOUND is the
    # thing under review (ch05's moose bellow was the first, 2026-08-15) -- and it pins
    # audioSync on with it, because sound played against a free-running video clock stutters.
    local mute=1 async=0
    if [ -n "${PT_SOUND:-}" ] && [ "${PT_SOUND}" != "0" ]; then mute=0; async=1; fi
    # -l 0: mgba-headless logs every BIOS SWI and DMA otherwise -- 5.4MB in 6s, which is
    # ~1GB over a 600s scenario, all of it captured into mgba-stdout.log and none of it read.
    "$app" --script "$wrapper" -l 0 \
        -C mute=$mute -C fpsTarget="$fps" -C audioSync=$async -C videoSync="$vsync" \
        "$ROM" >"$out/mgba-stdout.log" 2>&1 &
    local pid=$!
    echo "running '$scen' (pid $pid, ${fps}fps); polling $log"
    # The work is FRAME-bound; the deadline used to be WALL-clock, and that mismatch is what
    # made SUITE=all report false failures (#345). Four long scenarios sharing the machine ran
    # at ~15fps against a 240fps target -- 16x slower -- so scenarios that pass solo in 25-70s
    # blew 300-600s wall deadlines and were tabled as FAIL. Nothing had failed; the clock was
    # measuring the MACHINE'S LOAD, not the scenario.
    #
    # So the declared `deadline` is read as what it always meant -- how much WORK a scenario may
    # do -- expressed in frames at its own target rate. Contention then makes a run take longer
    # in wall time and changes nothing about its verdict. Two things still kill a run, and both
    # are real faults rather than symptoms of a busy laptop:
    #
    #   OVERRUN  the scenario did more frames than its budget: it is genuinely not finishing.
    #   STALL    the frame counter stopped moving: mGBA is wedged, so no budget would ever be
    #            reached and waiting for one is waiting forever.
    #
    # PT_MAX_WALL_S remains as a last-resort net for a pathology neither of those describes.
    # The budget is sized on the DECLARED rate, never on PT_FPS. PT_FPS=60 to watch a run at
    # real speed must not quarter its work allowance and OVERRUN a scenario that passes by
    # default (#358 review).
    #
    # ...and it floors at that rate rather than fixing it there, because the emulator OUTRUNS
    # its target: titlecard measures 877fps against a 240 target. A flat deadline*target would
    # be ~3.6x STINGIER than the wall deadline it replaces, and `llm` -- whose own comment says
    # "at 240fps a frame budget would be 4x too impatient" -- would start failing. Taking the
    # best rate the run has actually achieved reproduces the old allowance on an idle machine,
    # while contention can only make the budget LARGER, never smaller. The bad direction is
    # the one that cannot happen.
    local stall=${PT_STALL_S:-1800}
    local max_wall=${PT_MAX_WALL_S:-7200}
    local started=$SECONDS
    local last_frame=0 last_progress=$SECONDS frame=0
    VERDICT=""
    while :; do
        if [ -f "$log" ] && grep -q "RESULT:" "$log"; then VERDICT=$(grep "RESULT:" "$log" | tail -1); break; fi
        if ! kill -0 "$pid" 2>/dev/null; then VERDICT="RESULT: ERROR -- mGBA exited early"; break; fi
        # Every harness line is stamped [fNNNNN], so progress is free to read. Only the tail is
        # scanned: these logs reach hundreds of MB and re-reading one every 3s is its own load.
        # `|| true`: before the first stamped line exists grep exits 1, and under
        # `set -euo pipefail` that killed run.sh outright -- silently, after the "running"
        # banner, with the scenario still passing in its own log. No frames yet is a NORMAL
        # early state, not an error.
        frame=$(tail -c 200000 "$log" 2>/dev/null | grep -oE '\[f[0-9]+\]' | tail -1 | tr -dc '0-9' || true)
        # 10# forces base 10: the stamps are zero-padded ([f005267]) and bash reads a
        # leading-zero number in $(( )) as OCTAL, which silently mis-scaled the throughput
        # line (3425 read as 3425o = 1813, reported as 302fps instead of 570).
        frame=$((10#${frame:-0}))
        if [ "$frame" -gt "$last_frame" ]; then last_frame=$frame; last_progress=$SECONDS; fi
        local ran=$((SECONDS - started)); [ "$ran" -gt 0 ] || ran=1
        local rate=$((last_frame / ran))
        [ "$rate" -gt "$budget_fps" ] || rate=$budget_fps
        local budget=$((deadline * rate))
        if [ "$frame" -gt "$budget" ]; then
            VERDICT="RESULT: ERROR -- OVERRAN its frame budget (${frame} > ${budget} frames, i.e. ${deadline}s of work at ${rate}fps)"
            break
        fi
        if [ $((SECONDS - last_progress)) -ge "$stall" ]; then
            VERDICT="RESULT: ERROR -- STALLED: no frame progress for ${stall}s (stuck at frame ${last_frame})"
            break
        fi
        if [ $((SECONDS - started)) -ge "$max_wall" ]; then
            VERDICT="RESULT: ERROR -- exceeded PT_MAX_WALL_S=${max_wall}s at frame ${last_frame}"
            break
        fi
        sleep 3
    done
    # Throughput, always -- a contended run is now legible instead of a mystery (#345). A number
    # far under the target is the signal that the machine, not the change, is what is slow.
    # Re-read the final frame: the poll interval means the loop's last sample is up to 3s
    # stale, and on a short scenario that is most of the run.
    local final
    final=$(tail -c 200000 "$log" 2>/dev/null | grep -oE '\[f[0-9]+\]' | tail -1 | tr -dc '0-9' || true)
    final=$((10#${final:-0}))
    [ "$final" -gt "$last_frame" ] && last_frame=$final
    local elapsed=$((SECONDS - started)); [ "$elapsed" -gt 0 ] || elapsed=1
    echo "throughput: ${last_frame} frames in ${elapsed}s = $((last_frame / elapsed))fps (target ${fps}fps)"
    if [ "$KEEP_OPEN" != "--keep-open" ]; then kill "$pid" 2>/dev/null || true; fi
    echo "----------------------------------------"
    cat "$log" 2>/dev/null || echo "(no log produced)"
    echo "----------------------------------------"
    echo "$VERDICT"
    # A failing run renders its OWN diagnosis. The snapshot was already in the log as
    # JSON, but reading it meant knowing to run inspect_state.py by hand -- and the point
    # of #236 was that the next question after a FAIL should be "which proc do I classify",
    # not "which hypothesis do I rebuild" (#241).
    if ! verdict_passed; then
        if grep -q '"event":"inspect"\|"event": "inspect"' "$log" 2>/dev/null; then
            echo "---------------- inspector ----------------"
            python3 "$HERE/inspect_state.py" render "$log" || true
        fi
    fi
    echo "artifacts: $out"
}

# Checkpoint dependency: a scenario may load a save state built fast by a ckpt_* scenario.
# Build it (240fps) if the state is missing or was made for a different ROM. The
# scenario -> checkpoint map lives in matrix.yaml; recordscene is the one dynamic case,
# where PT_STATE names the checkpoint and its builder is ckpt_<PT_STATE> by convention.
BUILDER="$MX_CHECKPOINT_BUILDER"; CKPT="$MX_CHECKPOINT"
if [ -n "$MX_CHECKPOINT_DYNAMIC" ]; then
    CKPT="${PT_STATE:?$SCENARIO needs PT_STATE=<checkpoint> (e.g. PT_STATE=ch02intro)}"
    BUILDER="ckpt_${PT_STATE}"
fi
# A save state carries the difficulty it was MINTED in (it is in gPlaySt), so checkpoint
# validity is (rom, mode) -- not rom alone. Keying on the hash reloaded a Tutorial state
# under a Normal label, and a difficulty change alters no ROM bytes, so the hash could
# never notice. Existing single-hash stamps mismatch and re-mint once, which is correct.
CHECKPOINT_STAMP="$ROMHASH:${PT_DIFFICULTY:-normal}"
if [ -n "$BUILDER" ]; then
    if [ ! -f "$STATE_DIR/$CKPT.ss" ] || [ "$(cat "$STATE_DIR/$CKPT.romhash" 2>/dev/null || true)" != "$CHECKPOINT_STAMP" ]; then
        echo "== checkpoint '$CKPT' missing/stale for $CHECKPOINT_STAMP -> building at top speed (240fps) =="
        # Note what the state file looked like BEFORE the build. Most builder failures never
        # reach saveState() at all (the builder gives up, the deadline expires, mGBA exits
        # early), so they write nothing -- and a rebuild triggered only by a STAMP change
        # (PT_DIFFICULTY=difficult, say) would otherwise delete the perfectly good state
        # belonging to the previous stamp and force a full re-mint when you switch back.
        _ss_before=$(stat -f%m "$STATE_DIR/$CKPT.ss" 2>/dev/null || echo none)
        run_mgba "$BUILDER" 240 0 "$MX_CHECKPOINT_DEADLINE" headed 240  # HEADED always: saveStateFile is
        # broken under mgba-headless (see the engine-selection note above). ch02start
        # replays the whole ch00->ch01->ch02 chain.
        if verdict_passed; then
            echo "$CHECKPOINT_STAMP" > "$STATE_DIR/$CKPT.romhash"
        else
            _ss_after=$(stat -f%m "$STATE_DIR/$CKPT.ss" 2>/dev/null || echo none)
            if [ "$_ss_after" != "$_ss_before" ]; then
                # THIS run wrote it and then failed, so what is on disk is partial or dead
                # (mgba-headless writes 397312 bytes of zeros). Without its .romhash the next
                # run rebuilds anyway, but a file that size reads as a real checkpoint to
                # whoever looks next, and that is how a dead one gets trusted.
                echo "removing the partial '$CKPT' state this run wrote"
                rm -f "$STATE_DIR/$CKPT.ss"
            fi
            # Evict the scenario's stored green before leaving. `exit 1` here skips the
            # eviction at the bottom of this file, so a direct `run.sh ch02` whose checkpoint
            # build failed would leave a stale PASS that the next `make matrix` serves without
            # running anything -- while the same failure UNDER matrix.py does evict. The two
            # paths have to agree.
            rm -rf "$REPO/.matrix-verdictcache/$SCENARIO-"* 2>/dev/null || true
            echo "checkpoint build FAILED -- aborting"; exit 1
        fi
    else
        echo "== checkpoint '$CKPT' valid for $CHECKPOINT_STAMP -> loading =="
    fi
fi

# Rate + deadline also come from matrix.yaml (record* film at 60fps for faithful motion;
# everything else runs at top speed; soaks and routs get a longer wall).
FPS="$MX_FPS"; VSYNC="$MX_VSYNC"; DEADLINE_S="$MX_DEADLINE"
# PT_FPS overrides the rate. 60fps+videoSync is only needed to capture smooth cutscene
# FADES; verification captures of static text/boxes (sign, death quote) read fine at top
# speed, so `PT_FPS=240 ... recordfix` runs ~4x faster.
if [ -n "${PT_FPS:-}" ]; then FPS="$PT_FPS"; [ "$PT_FPS" -ge 240 ] && VSYNC=0; fi
run_mgba "$SCENARIO" "$FPS" "$VSYNC" "$DEADLINE_S" \
    "$([ "$SCENARIO_HEADLESS" = "1" ] && echo headless || echo headed)" "$MX_FPS"
# Tell the sidecar the run is over: serve() drains any pending request, saves its
# transcript (record mode), and exits -- without this it polls forever and a recorded
# transcript would only be saved by a clean Ctrl-C.
if [ "$SCENARIO" = "llm" ]; then touch "$LLM_DIR/stop"; fi
# A red always wins over a stored green (#255). The matrix evicts its own cache slot when
# it sees a failure, but a scenario run DIRECTLY -- which is how debugging happens -- never
# passes through it, and the next `make matrix` would go on reporting the stale PASS for a
# scenario that is red right now. Nothing else here reads the cache; this only invalidates.
verdict_passed || rm -rf "$REPO/.matrix-verdictcache/$SCENARIO-"* 2>/dev/null || true
verdict_passed && exit 0 || exit 1
