-- Tests for liveness.lua -- the pure stability classifier (no emulator).
-- Run: lua tools/playtest/test_liveness.lua
local here = (arg[0]:match("(.*/)")) or "./"
local L = dofile(here .. "liveness.lua")

local tests, fails = 0, 0
local function check(got, want, msg)
    tests = tests + 1
    if got ~= want then
        fails = fails + 1
        print(string.format("FAIL: %s\n  got  %s\n  want %s", msg, tostring(got), tostring(want)))
    end
end

-- A snapshot: frame, turn, faction, hpsum, procfp, chapter_advanced, gameover.
local function snap(frame, turn, faction, hpsum, procfp, win, over)
    return { frame = frame, turn = turn, faction = faction, hpsum = hpsum,
             procfp = procfp, chapter_advanced = win or false, gameover = over or false }
end
local cfg = { softlock_frames = 600 }

-- A clean win (chapter advanced) is TERMINAL_WIN.
do
    local s = { snap(0, 1, 0, 100, 1), snap(100, 1, 0x80, 90, 2, true, false) }
    check(L.classify(s, cfg).state, "TERMINAL_WIN", "chapter advanced -> TERMINAL_WIN")
end

-- A clean loss (game over active) is TERMINAL_LOSS.
do
    local s = { snap(0, 1, 0, 100, 1), snap(100, 3, 0x80, 0, 7, false, true) }
    check(L.classify(s, cfg).state, "TERMINAL_LOSS", "game over -> TERMINAL_LOSS")
end

-- Frozen state across >= softlock_frames is SOFTLOCK.
do
    local s = {}
    for i = 0, 10 do s[#s + 1] = snap(i * 100, 2, 0x80, 50, 5) end  -- spans 1000 frames, no change
    check(L.classify(s, cfg).state, "SOFTLOCK", "no change for >= softlock_frames -> SOFTLOCK")
end

-- Idle but turns still cycling (fingerprint changes) is LIVE, even over a long span.
do
    local s = {}
    for i = 0, 10 do s[#s + 1] = snap(i * 100, 2 + i, (i % 2) * 0x80, 50, 5) end
    check(L.classify(s, cfg).state, "LIVE", "cycling turns -> LIVE (no false SOFTLOCK)")
end

-- Frozen, but for less than softlock_frames -> not yet SOFTLOCK (LIVE).
do
    local s = { snap(0, 2, 0x80, 50, 5), snap(300, 2, 0x80, 50, 5) }  -- 300 < 600
    check(L.classify(s, cfg).state, "LIVE", "short freeze (< window) -> LIVE")
end

-- A terminal verdict wins even if the state looks frozen.
do
    local s = {}
    for i = 0, 10 do s[#s + 1] = snap(i * 100, 2, 0x80, 50, 5) end
    s[#s].chapter_advanced = true
    check(L.classify(s, cfg).state, "TERMINAL_WIN", "terminal takes precedence over SOFTLOCK")
end

if fails > 0 then
    print(string.format("\n%d/%d FAILED", fails, tests)); os.exit(1)
else
    print(string.format("ok -- %d assertions", tests))
end
