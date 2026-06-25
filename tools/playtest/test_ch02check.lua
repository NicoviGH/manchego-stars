-- Tests for ch02check.lua -- the pure charm-delivery check (no emulator).
-- Run: lua tools/playtest/test_ch02check.lua
local here = (arg[0]:match("(.*/)")) or "./"
local C = dofile(here .. "ch02check.lua")

local tests, fails = 0, 0
local function check(got, want, msg)
    tests = tests + 1
    if got ~= want then
        fails = fails + 1
        print(string.format("FAIL: %s\n  got  %s\n  want %s", msg, tostring(got), tostring(want)))
    end
end

-- The 3 chwinga charms (real decomp item ids): Red Gem 0x76, Elixir 0x6D, Pure Water 0x6E.
local CHARMS = { 0x76, 0x6D, 0x6E }

-- No charms anywhere in the collected items -> empty result.
do
    local got = C.deliveredCharms({ 0x01, 0x02, 0x03 }, CHARMS)
    check(#got, 0, "no charms present -> none delivered")
end

-- A single charm in the item list is reported.
do
    local got = C.deliveredCharms({ 0x01, 0x76, 0x02 }, CHARMS)
    check(#got, 1, "one charm present -> one delivered")
    check(got[1], 0x76, "the present charm id is reported")
end

-- All three charms present (e.g. all chwinga survived) -> all three reported.
do
    local got = C.deliveredCharms({ 0x76, 0x6D, 0x6E, 0x01 }, CHARMS)
    check(#got, 3, "all three charms present -> three delivered")
end

-- A charm appearing twice (leader inventory AND convoy) is reported once, not double-counted.
do
    local got = C.deliveredCharms({ 0x76, 0x76, 0x01 }, CHARMS)
    check(#got, 1, "duplicate charm id reported once")
    check(got[1], 0x76, "the de-duplicated charm id is correct")
end

-- An empty 0x00 item slot is ignored (FE8 packs empty inventory slots as 0x00).
do
    local got = C.deliveredCharms({ 0x00, 0x00, 0x6D, 0x00 }, CHARMS)
    check(#got, 1, "empty 0x00 slots ignored, charm still found")
    check(got[1], 0x6D, "charm found amid empty slots")
end

if fails > 0 then
    print(string.format("\n%d/%d FAILED", fails, tests)); os.exit(1)
else
    print(string.format("ok -- %d assertions", tests))
end
