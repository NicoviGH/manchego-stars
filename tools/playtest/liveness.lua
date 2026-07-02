-- liveness.lua -- pure stability classifier for the playtest smoke net (#49).
--
-- NO emulator calls: a function over a series of state snapshots, so it is unit-tested
-- without mGBA (tools/playtest/test_liveness.lua). The smoke driver (smokeDrive in
-- harness.lua) samples real memory into snapshots and asks classify() what to do each cycle.
--
-- A snapshot is a table:
--   frame             monotonic emulated-frame counter at sample time
--   turn, faction     PlaySt turn / phase-faction (the game advancing)
--   hpsum             sum of curHP over both unit arrays (global progress signal)
--   procfp            small fingerprint of which known procs are active
--   chapter_advanced  true once the host chapter index has moved past the start (= win)
--   gameover          true while the game-over proc is active (= loss)
--
-- classify(snapshots, cfg) -> { state = <STATE>, why = <string> }
--   STATE: "LIVE" | "TERMINAL_WIN" | "TERMINAL_LOSS" | "NUDGE" | "SOFTLOCK"
--   cfg.nudge_frames (optional): a shorter stall => NUDGE, the fuzzer's unstick signal
--     ("mash B to back out of a benign menu"), not yet a failure. Omit it (as the smoke
--     driver does) and NUDGE is never returned -- the verdict is unchanged.
--   cfg.softlock_frames: frames with no change in {turn,faction,hpsum,procfp} => SOFTLOCK.
--
-- There is deliberately no budget/HANG state: exhausting the in-game turn budget while
-- still LIVE is the driver's call (smokeDrive PASSes it -- an idle party usually can't
-- force a terminal), and a wedged emulator is caught by run.sh's wall-clock deadline --
-- both outside this pure verdict.

local M = {}

local function key_unchanged(a, b)
    return a.turn == b.turn and a.faction == b.faction
        and a.hpsum == b.hpsum and a.procfp == b.procfp
end

function M.classify(snapshots, cfg)
    local latest = snapshots[#snapshots]
    if latest.chapter_advanced then
        return { state = "TERMINAL_WIN", why = "host chapter advanced past start" }
    end
    if latest.gameover then
        return { state = "TERMINAL_LOSS", why = "game-over proc active" }
    end
    -- Frames since the last observed change in the game-state key. If we never saw a change
    -- in the buffered history, measure from the oldest snapshot we have.
    local last_change_frame = snapshots[1].frame
    for i = #snapshots - 1, 1, -1 do
        if not key_unchanged(snapshots[i], latest) then
            last_change_frame = snapshots[i].frame
            break
        end
    end
    local stuck = latest.frame - last_change_frame
    if stuck >= cfg.softlock_frames then
        return { state = "SOFTLOCK",
                 why = string.format("no state change for %d frames", stuck) }
    end
    if cfg.nudge_frames and stuck >= cfg.nudge_frames then
        return { state = "NUDGE",
                 why = string.format("stalled %d frames; try to unstick", stuck) }
    end
    return { state = "LIVE", why = "state still advancing" }
end

return M
