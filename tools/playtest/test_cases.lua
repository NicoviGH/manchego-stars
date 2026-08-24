-- Tests for cases.lua -- the declarative playtest case driver (#314, no emulator).
-- The driver is pure with respect to the game: everything it touches arrives on the `api`
-- table, so a fake api is a complete test double.
-- Run: lua tools/playtest/test_cases.lua
local here = (arg[0]:match("(.*/)")) or "./"
local C = dofile(here .. "cases.lua")

local tests, fails = 0, 0
local function check(got, want, msg)
    tests = tests + 1
    if got ~= want then
        fails = fails + 1
        print(string.format("FAIL: %s\n  got  %s\n  want %s", msg, tostring(got), tostring(want)))
    end
end
local function contains(hay, needle, msg)
    tests = tests + 1
    if not tostring(hay):find(needle, 1, true) then
        fails = fails + 1
        print(string.format("FAIL: %s\n  %q does not contain %q", msg, tostring(hay), needle))
    end
end

-- A fake api. `script` decides what each visit does: it returns ok, why, spoke and may add
-- items to the party, exactly as visitVillage does against the real engine.
local function fakeApi(opts)
    opts = opts or {}
    local items = {}
    for _, id in ipairs(opts.items or {}) do items[#items + 1] = id end
    local a = {verdict = nil, reason = nil, log = {}, visits = {}, booted = false, settled = 0}
    a.bootToMap = function() a.booted = true; return opts.boot ~= false end
    a.fastConfig = function() a.fast = true end
    a.settle = function() a.settled = a.settled + 1; return opts.settle ~= false end
    a.collectedItems = function() return items end
    a.eventFlag = function(id) return (opts.flags or {})[id] == true end
    a.log = function(s) a.log[#a.log + 1] = s end
    a.shot = function() end
    a.result = function(v, why) a.verdict, a.reason = v, why; return v end
    a.visitVillage = function(x, y)
        a.visits[#a.visits + 1] = {x = x, y = y}
        local step = (opts.visits or {})[#a.visits] or {}
        if step.gives then items[#items + 1] = step.gives end
        return step.ok ~= false, step.why or "refused", step.spoke ~= false
    end
    return a
end

-- The happy path: ch05village's shape end to end.
do
    local api = fakeApi({visits = {{gives = 0x60}}})
    local case = {name = "ch05village", given = {"on_map"},
                  ["when"] = {{visit = {x = 12, y = 19}}},
                  ["then"] = {{gained_item = 0x60}}}
    C.run(case, api)
    check(api.verdict, "PASS", "a satisfied case PASSes")
    check(api.booted, true, "`on_map` boots to the map")
    check(api.fast, true, "`on_map` pokes fast text")
    check(#api.visits, 1, "one visit step ran")
    check(api.visits[1].x, 12, "the visit used the declared x")
    check(api.visits[1].y, 19, "the visit used the declared y")
end

-- The item never arrives: the case must FAIL, and say which item.
do
    local api = fakeApi({visits = {{}}})       -- visit succeeds, hands over nothing
    C.run({name = "ch05village", given = {"on_map"}, ["when"] = {{visit = {x = 12, y = 19}}},
           ["then"] = {{gained_item = 0x60}}}, api)
    check(api.verdict, "FAIL", "an unmet gained_item FAILs")
    contains(api.reason, "0x60", "the reason names the item that never arrived")
end

-- An item the party ALREADY held does not count: the assertion is that the case GAINED it.
-- Without this, ch05village would pass on a chapter whose reliquary hands over nothing at
-- all, so long as anyone in the party happened to be carrying a Dracoshield.
do
    local api = fakeApi({items = {0x60}, visits = {{}}})
    C.run({name = "ch05village", given = {"on_map"}, ["when"] = {{visit = {x = 12, y = 19}}},
           ["then"] = {{gained_item = 0x60}}}, api)
    check(api.verdict, "FAIL", "an item held BEFORE the case does not satisfy gained_item")
end

-- A second copy of an item the party already held DOES count.
do
    local api = fakeApi({items = {0x60}, visits = {{gives = 0x60}}})
    C.run({name = "ch05village", given = {"on_map"}, ["when"] = {{visit = {x = 12, y = 19}}},
           ["then"] = {{gained_item = 0x60}}}, api)
    check(api.verdict, "PASS", "gained_item counts copies, not presence")
end

-- ch05reliquaries: four visits, four items, and `spoke` covering all of them.
do
    local api = fakeApi({visits = {{gives = 0x70}, {gives = 0x5D}, {gives = 0x0E}, {gives = 0x60}}})
    C.run({name = "ch05reliquaries", given = {"on_map"},
           ["when"] = {{visit = {x = 5, y = 1}}, {visit = {x = 5, y = 6}},
                       {visit = {x = 12, y = 10}}, {visit = {x = 12, y = 19}}},
           ["then"] = {{gained_item = 0x70}, {gained_item = 0x5D}, {gained_item = 0x0E},
                       {gained_item = 0x60}, {spoke = true}}}, api)
    check(api.verdict, "PASS", "all four reliquaries satisfied")
    check(#api.visits, 4, "four visit steps ran")
    -- 5, not 4: `on_map` settles once after the boot, and each visit settles again
    -- before it moves. That is exactly what the hand-written ch05reliquaries does.
    check(api.settled, 5, "the map settles after the boot and before every visit")
end

-- A door that pays out in SILENCE fails `spoke`, and the reason names which one.
do
    local api = fakeApi({visits = {{gives = 0x70}, {gives = 0x5D, spoke = false},
                                   {gives = 0x0E}, {gives = 0x60}}})
    C.run({name = "ch05reliquaries", given = {"on_map"},
           ["when"] = {{visit = {x = 5, y = 1}}, {visit = {x = 5, y = 6}},
                       {visit = {x = 12, y = 10}}, {visit = {x = 12, y = 19}}},
           ["then"] = {{gained_item = 0x70}, {spoke = true}}}, api)
    check(api.verdict, "FAIL", "a silent payout FAILs")
    contains(api.reason, "(5,6)", "the reason names the silent door's tile")
end

-- Boot failure is a FAIL with a reason about the BOOT, not a confusing assertion error.
do
    local api = fakeApi({boot = false})
    C.run({name = "ch05village", given = {"on_map"}, ["when"] = {{visit = {x = 1, y = 1}}},
           ["then"] = {{gained_item = 0x60}}}, api)
    check(api.verdict, "FAIL", "a failed boot FAILs")
    contains(api.reason, "never reached", "the reason blames the boot")
    check(#api.visits, 0, "no step runs after a failed boot")
end

-- An unknown step or assertion is an ERROR, never a skip. A case that silently ignored a
-- word it did not know would report coverage it does not have -- the same failure class as
-- a case with no steps passing vacuously.
do
    local api = fakeApi({})
    C.run({name = "x", given = {"on_map"}, ["when"] = {{teleport = {x = 1}}},
           ["then"] = {{gained_item = 1}}}, api)
    check(api.verdict, "ERROR", "an unknown step is an ERROR")
    contains(api.reason, "teleport", "the reason names the unknown step")
end
do
    local api = fakeApi({visits = {{gives = 1}}})
    C.run({name = "x", given = {"on_map"}, ["when"] = {{visit = {x = 1, y = 1}}},
           ["then"] = {{unit_is_purple = true}}}, api)
    check(api.verdict, "ERROR", "an unknown assertion is an ERROR")
    contains(api.reason, "unit_is_purple", "the reason names the unknown assertion")
end
do
    local api = fakeApi({})
    C.run({name = "x", given = {"levitate"}, ["when"] = {}, ["then"] = {}}, api)
    check(api.verdict, "ERROR", "an unknown given is an ERROR")
end

-- A case with no assertions cannot PASS. Vacuous green is worse than red: it reports
-- coverage that does not exist.
do
    local api = fakeApi({visits = {{gives = 1}}})
    C.run({name = "x", given = {"on_map"}, ["when"] = {{visit = {x = 1, y = 1}}},
           ["then"] = {}}, api)
    check(api.verdict, "ERROR", "a case asserting nothing is an ERROR, not a PASS")
end

-- event_flag, for the save-all payout shape (ch05crest's half that is declarable).
do
    local api = fakeApi({visits = {{gives = 1}}, flags = {[12] = true}})
    C.run({name = "x", given = {"on_map"}, ["when"] = {{visit = {x = 5, y = 1}}},
           ["then"] = {{event_flag = 12}}}, api)
    check(api.verdict, "PASS", "a set event flag satisfies event_flag")
    api = fakeApi({visits = {{gives = 1}}, flags = {}})
    C.run({name = "x", given = {"on_map"}, ["when"] = {{visit = {x = 5, y = 1}}},
           ["then"] = {{event_flag = 12}}}, api)
    check(api.verdict, "FAIL", "an unset event flag FAILs")
end

-- The map failing to return to player control before a visit is its own reason.
do
    local api = fakeApi({settle = false})
    C.run({name = "x", given = {"on_map"}, ["when"] = {{visit = {x = 5, y = 1}}},
           ["then"] = {{gained_item = 1}}}, api)
    check(api.verdict, "FAIL", "a map that never settles FAILs")
    contains(api.reason, "player control", "the reason blames the settle, not the visit")
end

print(string.format("%d checks, %d failures", tests, fails))
os.exit(fails == 0 and 0 or 1)
