#!/usr/bin/env bash
# Soak the stability fuzzer (#49) across MANY seeds and aggregate the verdicts.
#
#   tools/playtest/fuzz_sweep.sh [N] [scenario]
#       N         how many seeds to run, 1..N            (default 8)
#       scenario  fuzz | fuzz_ch01                        (default fuzz)
#   PT_SEEDS="1 7 9 …" tools/playtest/fuzz_sweep.sh   -- run an explicit seed set instead
#
# A single fuzz run only explores ONE random path; this runs a set and FAILS (exit 1) if any
# seed soft-locks/crashes, printing each seed's verdict + the reproduce command for any FAIL.
# This is a LOCAL pre-release soak, not a CI gate: CI builds against a mock ROM and has no
# mGBA, so it can't run in-emulator scenarios at all (see .github/workflows/checks.yml).
# It is SLOW by design -- each seed is a full New Game -> chapter -> frame-budget soak
# (~minutes of wall time at 240fps). Kick it off deliberately before cutting a player build.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
N="${1:-8}"
SCENARIO="${2:-fuzz}"

if [ -n "${PT_SEEDS:-}" ]; then
    read -r -a SEEDS <<< "$PT_SEEDS"
else
    SEEDS=()
    for s in $(seq 1 "$N"); do SEEDS+=("$s"); done
fi

echo "== fuzz sweep: scenario '$SCENARIO', ${#SEEDS[@]} seed(s): ${SEEDS[*]} =="
fails=()
for s in "${SEEDS[@]}"; do
    echo "----- seed $s -----"
    if PT_SEED="$s" "$HERE/run.sh" "$SCENARIO" >"/tmp/fuzz-sweep-seed-$s.log" 2>&1; then
        grep "RESULT:" "/tmp/fuzz-sweep-seed-$s.log" | tail -1 || echo "  (PASS, no RESULT line?)"
    else
        grep "RESULT:" "/tmp/fuzz-sweep-seed-$s.log" | tail -1 || echo "  (FAIL, no RESULT line -- see /tmp/fuzz-sweep-seed-$s.log)"
        fails+=("$s")
    fi
done

echo "========================================"
if [ "${#fails[@]}" -eq 0 ]; then
    echo "SWEEP PASS -- all ${#SEEDS[@]} seed(s) clean"
    exit 0
else
    echo "SWEEP FAIL -- ${#fails[@]}/${#SEEDS[@]} seed(s) failed: ${fails[*]}"
    echo "reproduce a failing seed: PT_SEED=<seed> tools/playtest/run.sh $SCENARIO"
    exit 1
fi
