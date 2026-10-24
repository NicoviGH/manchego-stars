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
    local a = {verdict = nil, reason = nil, logged = {}, visits = {}, booted = false, settled = 0}
    a.bootToMap = function() a.booted = true; return opts.boot ~= false end
    a.fastConfig = function() a.fast = true end
    a.settle = function() a.settled = a.settled + 1; return opts.settle ~= false end
    a.collectedItems = function() return items end
    a.eventFlag = function(id) return (opts.flags or {})[id] == true end
    a.log = function(s) a.logged[#a.logged + 1] = s end
    a.shot = function() end
    a.result = function(v, why) a.verdict, a.reason = v, why; return v end
    a.visitVillage = function(x, y)
        a.visits[#a.visits + 1] = {x = x, y = y}
        local step = (opts.visits or {})[#a.visits] or {}
        if step.gives then items[#items + 1] = step.gives end
        return step.ok ~= false, step.why or "refused", step.spoke ~= false
    end
    -- `talk` sites share the visit script, so a mixed case counts its steps in one sequence.
    a.talkFrom = function(x, y)
        local r = {a.visitVillage(x, y)}
        a.visits[#a.visits].talk = true
        return table.unpack(r)
    end
    -- `shop` opens the tile's Armory/Vendor and reports what it stocks.
    a.shopAt = function(x, y, kind)
        a.visits[#a.visits + 1] = {x = x, y = y, shop = kind}
        local step = (opts.shops or {})[#a.visits] or {}
        return step.ok ~= false, step.why or "refused", step.stock or {}
    end
    -- `help`: the pid on a tile, what the build gives it, and what R on its name decoded.
    a.pidAt = function(x, y) return (opts.pids or {})[x .. "," .. y] end
    a.helpFor = function(pid) return (opts.help or {})[pid] end
    a.helpAt = function(x, y, want)
        a.visits[#a.visits + 1] = {x = x, y = y, help = want}
        if opts.helpRead == false then return false, "help never opened" end
        return true, opts.helpRead
    end
    -- `idle`/`raided`: enemy phase n returns `opts.phaseResults[n]` ("player" by default), then
    -- every "x,y" in `opts.raze[n]` is RUINS and every id in `opts.loot[n]` reached the party.
    -- An unlisted tile is a village.
    local terrain = {}
    for k, v in pairs(opts.terrain or {}) do terrain[k] = v end
    a.phases, a.held = 0, 0
    a.enemyPhase = function()
        a.phases = a.phases + 1
        for _, key in ipairs((opts.raze or {})[a.phases] or {}) do terrain[key] = 0x25 end
        for _, id in ipairs((opts.loot or {})[a.phases] or {}) do items[#items + 1] = id end
        return (opts.phaseResults or {})[a.phases] or "player"
    end
    a.holdParty = function() a.held = a.held + 1 end
    a.turn = function() return a.phases + 1 end
    a.terrainAt = function(x, y) return terrain[x .. "," .. y] or 0x03 end
    a.village = function(id) return (opts.villages or {})[id] end
    a.showTile = function(x, y) a.shown = x .. "," .. y end
    return a
end

-- `help`: R on a generic's name reads the help text its pid is given (#493).
do
    local raider = {msg = 0xD5F, line1 = "Raiders who prey on Ten-Towns"}
    local opts = {pids = {["3,4"] = 0x95}, help = {[0x95] = raider}, helpRead = raider}
    local api = fakeApi(opts)
    C.run({name = "ch02generichelp", given = {"on_map"}, ["when"] = {{help = {x = 3, y = 4}}}}, api)
    check(api.verdict, "PASS", "help reading the pid's own text PASSes")
    check(api.visits[1].help, 0xD5F, "the step waits for the pid's own message")

    opts.helpRead = {msg = 0x2A9, line1 = "The army of Grado, the largest"}
    api = fakeApi(opts)
    C.run({name = "ch02generichelp", given = {"on_map"}, ["when"] = {{help = {x = 3, y = 4}}}}, api)
    check(api.verdict, "FAIL", "a donor's vanilla line FAILs")
    contains(api.reason, "The army of Grado", "the failure quotes what help read")

    api = fakeApi({pids = {["3,4"] = 0x80}, help = {}, helpRead = raider})
    C.run({name = "ch02generichelp", given = {"on_map"}, ["when"] = {{help = {x = 3, y = 4}}}}, api)
    check(api.verdict, "FAIL", "a pid the build gives no help text FAILs")
    contains(api.reason, "pid 0x80", "the failure names the pid")
end

-- `shop`: ch02's Armory, the stock read off the shop that opened.
do
    local stock = {0x02, 0x01, 0x15, 0x14, 0x1F}
    local api = fakeApi({shops = {{stock = stock}}})
    C.run({name = "ch02armory", given = {"on_map"},
           ["when"] = {{shop = {x = 5, y = 7, kind = "armory", stocks = stock}}}}, api)
    check(api.verdict, "PASS", "a shop with the declared stock PASSes")
    check(api.visits[1].shop, "armory", "the shop step opens the declared kind")

    api = fakeApi({shops = {{stock = {0x01, 0x02}}}})
    C.run({name = "ch02armory", given = {"on_map"},
           ["when"] = {{shop = {x = 5, y = 7, kind = "armory", stocks = stock}}}}, api)
    check(api.verdict, "FAIL", "a shop wired to the wrong list FAILs")
    contains(api.reason, "stocks [0x01, 0x02]", "the failure names the stock it found")

    api = fakeApi({shops = {{ok = false, why = "live command menu did not expose armory"}}})
    C.run({name = "ch02armory", given = {"on_map"},
           ["when"] = {{shop = {x = 5, y = 7, kind = "armory", stocks = stock}}}}, api)
    check(api.verdict, "FAIL", "a tile with no Armory command FAILs")
    contains(api.reason, "did not expose armory", "the failure says the command was missing")
end

-- `idle` + `raided`: ch02raid's shape. Two huts watched, the second falls on phase 3.
local HUTS = {south = {x = 1, y = 12, flag = 9, gift = 0x6E}, east = {x = 12, y = 3, flag = 10}}
local function raid(opts, idle, watched)
    opts.villages = opts.villages or HUTS
    local api = fakeApi(opts)
    C.run({name = "ch02raid", given = {"on_map"},
           ["when"] = {{idle = idle or {phases = 12, hold = true, ["until"] = "raided"}}},
           ["then"] = {{raided = watched or {"south", "east"}}}}, api)
    return api
end
do
    local api = raid({raze = {[3] = {"12,3"}}})
    check(api.verdict, "PASS", "a watched site that falls PASSes")
    check(api.phases, 3, "`until: raided` stops at the phase the site fell")
    check(api.held, 3, "`hold` refills the party before every phase")
    check(api.shown, "12,3", "the camera goes to the site that fell")
    contains(table.concat(api.logged, "\n"), "east fell", "the log names the site that fell")

    api = raid({}, {phases = 4})
    check(api.verdict, "FAIL", "a raid where nothing falls FAILs")
    check(api.phases, 4, "without `until` every phase is spent")
    check(api.held, 0, "an unheld idle never touches the party")
    contains(api.reason, "still stands", "the failure says every site stood")

    api = raid({raze = {[2] = {"1,12"}}, loot = {[2] = {0x6E}}})
    check(api.verdict, "FAIL", "a sacked site whose gift still arrived FAILs")
    contains(api.reason, "0x6E reached the party", "the failure names the gift")

    api = raid({raze = {[2] = {"1,12"}}, flags = {[9] = true}})
    check(api.verdict, "FAIL", "a sacked site whose event id is set FAILs")
    contains(api.reason, "event id 9 is set", "the failure names the flag")

    api = raid({terrain = {["1,12"] = 0x25}})
    check(api.verdict, "FAIL", "a watched site that is not a village before the raid FAILs")
    contains(api.reason, "not a village", "the failure says nothing could raid it")
    check(api.phases, 0, "and no phase is spent finding that out")

    api = raid({}, nil, {"south", "west"})
    check(api.verdict, "FAIL", "a site CAMPAIGN.VILLAGES does not carry FAILs")
    contains(api.reason, "\"west\"", "the failure names the id")

    api = raid({phaseResults = {[2] = "gameover"}})
    check(api.verdict, "FAIL", "a party that dies while idling FAILs")
    contains(api.reason, "even while held", "the failure says it was held")

    api = fakeApi({})
    C.run({name = "x", given = {"on_map"},
           ["when"] = {{idle = {phases = 2, ["until"] = "raided"}}}, ["then"] = {{spoke = true}}},
          api)
    check(api.verdict, "FAIL", "`until: raided` with no `raided` assertion FAILs")
    check(api.phases, 0, "before spending a phase")
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

-- `talk` is the same site step through talkFrom: ch06boarding's shape, one paying hull and one
-- whose line is the reward.
do
    local api = fakeApi({visits = {{gives = 0x6F}, {}}})
    C.run({name = "ch06boarding", given = {"on_map"},
           ["when"] = {{talk = {x = 17, y = 13, gains = 0x6F}}, {talk = {x = 4, y = 18}}},
           ["then"] = {{spoke = true}}}, api)
    check(api.verdict, "PASS", "a boarding case PASSes")
    check(api.visits[1].talk, true, "a `talk` step opens its site through talkFrom")
    check(api.visits[2].y, 18, "the second talk used its declared y")
end
do
    local api = fakeApi({visits = {{why = "the command menu offered no Talk", ok = false}}})
    C.run({name = "ch06boarding", given = {"on_map"},
           ["when"] = {{talk = {x = 17, y = 13, gains = 0x6F}}}}, api)
    check(api.verdict, "FAIL", "a missing Talk command FAILs the case")
    contains(api.reason, "no Talk", "the reason says the Talk was missing")
end
do
    local api = fakeApi({visits = {{}}})
    C.run({name = "ch06boarding", given = {"on_map"},
           ["when"] = {{talk = {x = 17, y = 13, gains = 0x6F}}}}, api)
    check(api.verdict, "FAIL", "a talk that pays nothing FAILs its own gains")
    contains(api.reason, "0x6F", "the reason names the missing gift")
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

-- A door that hands over ANOTHER door's gift must FAIL. This is the whole reason the gift
-- rides the step: the gifts are per-tile on purpose, so "some item arrived" is not the
-- assertion. Rotating the four gifts passed under a whole-case `gained_item` list -- every
-- id still arrived, just from the wrong door -- which is the defect ch05reliquaries was
-- written to catch in the first place.
do
    local api = fakeApi({visits = {{gives = 0x5D}, {gives = 0x0E}, {gives = 0x60}, {gives = 0x70}}})
    C.run({name = "ch05reliquaries", given = {"on_map"},
           ["when"] = {{visit = {x = 5, y = 1, gains = 0x70}},
                       {visit = {x = 5, y = 6, gains = 0x5D}},
                       {visit = {x = 12, y = 10, gains = 0x0E}},
                       {visit = {x = 12, y = 19, gains = 0x60}}},
           ["then"] = {{spoke = true}}}, api)
    check(api.verdict, "FAIL", "four doors handing over each other's gifts FAILs")
    contains(api.reason, "(5,1)", "the reason names the FIRST door that gave the wrong gift")
    contains(api.reason, "0x70", "the reason names the gift that door owed")
end

-- The matching happy path: each door gives its own.
do
    local api = fakeApi({visits = {{gives = 0x70}, {gives = 0x5D}, {gives = 0x0E}, {gives = 0x60}}})
    C.run({name = "ch05reliquaries", given = {"on_map"},
           ["when"] = {{visit = {x = 5, y = 1, gains = 0x70}},
                       {visit = {x = 5, y = 6, gains = 0x5D}},
                       {visit = {x = 12, y = 10, gains = 0x0E}},
                       {visit = {x = 12, y = 19, gains = 0x60}}},
           ["then"] = {{spoke = true}}}, api)
    check(api.verdict, "PASS", "each door handing over its own gift PASSes")
end

-- A step-borne assertion COUNTS as an assertion: a case with `gains` and no `then` is not
-- the vacuous case the ERROR is for.
do
    local api = fakeApi({visits = {{gives = 0x60}}})
    C.run({name = "ch05village", given = {"on_map"},
           ["when"] = {{visit = {x = 12, y = 19, gains = 0x60}}}, ["then"] = {}}, api)
    check(api.verdict, "PASS", "a `gains` step is an assertion, so `then` may be empty")
end

-- ...but a case with neither still cannot pass.
do
    local api = fakeApi({visits = {{gives = 0x60}}})
    C.run({name = "x", given = {"on_map"}, ["when"] = {{visit = {x = 1, y = 1}}},
           ["then"] = {}}, api)
    check(api.verdict, "ERROR", "no `then` and no step assertion is still an ERROR")
end

-- A malformed entry is an ERROR with a readable reason, not an uncaught Lua error inside
-- pairs(). `- spoke` instead of `- spoke: true` is the typo this catches.
do
    local api = fakeApi({visits = {{gives = 1}}})
    C.run({name = "x", given = {"on_map"}, ["when"] = {{visit = {x = 1, y = 1, gains = 1}}},
           ["then"] = {"spoke"}}, api)
    check(api.verdict, "ERROR", "a bare string in `then` is an ERROR verdict, not a crash")
    contains(api.reason, "single-key mapping", "the reason explains the shape it wanted")
end

-- A `visit` whose argument is not a coordinate table fails cleanly too.
do
    local api = fakeApi({})
    C.run({name = "x", given = {"on_map"}, ["when"] = {{visit = "south"}},
           ["then"] = {{spoke = true}}}, api)
    check(api.verdict, "FAIL", "a non-table visit argument FAILs rather than crashing")
end

print(string.format("%d checks, %d failures", tests, fails))
os.exit(fails == 0 and 0 or 1)
