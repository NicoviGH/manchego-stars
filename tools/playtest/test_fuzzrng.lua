-- Tests for fuzzrng.lua -- the pure seeded PRNG + weighted input policy (no emulator).
-- Run: lua tools/playtest/test_fuzzrng.lua
--
-- The contract this locks: a given seed yields an IDENTICAL sequence on any host Lua
-- (CI's lua AND mGBA's embedded Lua), so a crash seed replays exactly. That is the whole
-- point of a fuzzer -- a non-reproducible crash is just noise.
local here = (arg[0]:match("(.*/)")) or "./"
local F = dofile(here .. "fuzzrng.lua")

local tests, fails = 0, 0
local function check(got, want, msg)
    tests = tests + 1
    if got ~= want then
        fails = fails + 1
        print(string.format("FAIL: %s\n  got  %s\n  want %s", msg, tostring(got), tostring(want)))
    end
end

-- Reproducibility: same seed -> identical raw sequence.
do
    local a, b = F.new(12345), F.new(12345)
    local same = true
    for _ = 1, 50 do
        if a:next() ~= b:next() then same = false end
    end
    check(same, true, "same seed -> identical next() sequence")
end

-- Determinism is host-independent: pin the exact first values for a known seed so a Lua
-- version bump that changes integer/bit semantics is caught here, not in a silent replay miss.
do
    local g = F.new(1)
    check(g:next(), (1 * 1664525 + 1013904223) & 0xFFFFFFFF, "first value matches the documented LCG")
    check(type(g:next()), "number", "second value is a number")
end

-- Different seeds diverge (a fuzzer that ignored its seed would be useless).
do
    local a, b = F.new(1), F.new(2)
    check(a:next() ~= b:next(), true, "different seeds -> different first value")
end

-- next() stays in the unsigned 32-bit range (masked), so % total below is well-defined.
do
    local g = F.new(99)
    local ok = true
    for _ = 1, 200 do
        local v = g:next()
        if v < 0 or v > 0xFFFFFFFF then ok = false end
    end
    check(ok, true, "next() stays within [0, 2^32)")
end

-- weightedPick returns one of the given entries (key-agnostic: entries are opaque tables).
do
    local g = F.new(7)
    local entries = { { key = "A", weight = 3 }, { key = "B", weight = 1 } }
    local ok = true
    for _ = 1, 200 do
        local e = F.weightedPick(g, entries)
        if e ~= entries[1] and e ~= entries[2] then ok = false end
    end
    check(ok, true, "weightedPick always returns a provided entry")
end

-- A weight-0 entry is NEVER chosen (so the driver can disable a key by zeroing it).
do
    local g = F.new(3)
    local entries = { { key = "A", weight = 1 }, { key = "NEVER", weight = 0 } }
    local sawNever = false
    for _ = 1, 500 do
        if F.weightedPick(g, entries).key == "NEVER" then sawNever = true end
    end
    check(sawNever, false, "weight-0 entry is never picked")
end

-- A single forced entry is always returned (degenerate distribution).
do
    local g = F.new(42)
    local only = { { key = "ONLY", weight = 5 } }
    check(F.weightedPick(g, only).key, "ONLY", "single entry is always chosen")
end

-- weightedPick is itself reproducible: same seed -> same pick sequence.
do
    local entries = { { key = "A", weight = 2 }, { key = "B", weight = 2 }, { key = "C", weight = 1 } }
    local a, b = F.new(2026), F.new(2026)
    local same = true
    for _ = 1, 100 do
        if F.weightedPick(a, entries).key ~= F.weightedPick(b, entries).key then same = false end
    end
    check(same, true, "same seed -> identical weightedPick sequence")
end

if fails > 0 then
    print(string.format("\n%d/%d FAILED", fails, tests)); os.exit(1)
else
    print(string.format("ok -- %d assertions", tests))
end
