-- Tests for goals.lua (#510 step 9): the goals still open, their worth and their chance from a
-- board, over a fake sight. What the game's own reads return is the ROM runs' to prove.
-- Run: lua tools/playtest/test_goals.lua
local here = (arg[0]:match("(.*/)")) or "./"
local Goals = dofile(here .. "goals.lua")
local Fakeline = dofile(here .. "fakeline.lua")

local tests, fails = 0, 0
local function check(got, want, msg)
    tests = tests + 1
    local ok = got == want
    if type(got) == "number" and type(want) == "number" then ok = math.abs(got - want) < 1e-9 end
    if not ok then
        fails = fails + 1
        print(string.format("FAIL: %s\n  got  %s\n  want %s", msg, tostring(got), tostring(want)))
    end
end

local G = 0.85

-- A fake sight: turns = Manhattan distance / mov (mov 4), not rounded, as sight.turnsTo;
-- prices by id.
local function fakeSight(o)
    o = o or {}
    local s = {}
    function s.turnsTo(u, tile, from)
        from = from or u
        local d = math.abs(from.x - tile.x) + math.abs(from.y - tile.y)
        if o.cutOff and o.cutOff[u.id] then return nil end
        return d / 4
    end
    function s.itemCost(id) return (o.prices or {})[id] or 0 end
    function s.explorable() return o.open or {} end
    function s.canExplore(u) return not (o.noVisit and o.noVisit[u.id]) end
    function s.closings() return o.closings or {} end
    function s.canSeize(u) return u.id == 1 end
    s.objective = o.objective or { kind = "rout" }
    return s
end

local function blue(id, x, y, extra)
    local u = { id = id, charId = id, x = x, y = y, faction = "blue", onField = true, items = {} }
    for k, v in pairs(extra or {}) do u[k] = v end
    return u
end

local function find(goals, id)
    for _, g in ipairs(goals) do if g.id == id then return g end end
end

-- the board as a plan leaves it: every taker where it stands, not yet acted
local function before(goals)
    local pos = {}
    for _, g in ipairs(goals) do
        for _, u in ipairs(g.takerUnits) do pos[u.id] = { x = u.x, y = u.y, acted = false, alive = 1 } end
    end
    return pos
end

-- TestChanceDiscountsByTurns: one taker 2 turns away (8 tiles, mov 4), unacted -> 0.85^1. After
-- it has acted from the same tile, a turn later: 0.85^2.
do
    local sight = fakeSight({ open = { { x = 8, y = 0, kind = "visit" } },
                              prices = { [0x0E] = 500 } })
    local board = { units = { blue(1, 0, 0) }, turn = 1 }
    local goals = Goals.list(board, sight, { villageGifts = { items = { 0x0E }, gold = {} } }, {})
    local g = find(goals, "visit:8,0")
    check(g ~= nil, true, "list: the open village is a goal")
    check(Goals.chance(g, { [1] = { x = 0, y = 0, acted = false, alive = 1 } }, G, sight.turnsTo),
        G ^ 1, "chance: two turns away, unacted")
    check(Goals.chance(g, { [1] = { x = 0, y = 0, acted = true, alive = 1 } }, G, sight.turnsTo),
        G ^ 2, "chance: two turns away, acted")
    check(Goals.chance(g, { [1] = { x = 7, y = 0, acted = true, alive = 1 } }, G, sight.turnsTo),
        G ^ 1, "chance: in reach but acted: next turn")
    check(Goals.chance(g, { [1] = { x = 8, y = 0, acted = true, alive = 1 } }, G, sight.turnsTo),
        G ^ 1, "chance: standing on it, acted: next turn too (taking it now is worth a turn)")
end

-- #711: a chest's taker is worth p.opens, the chance it lives and keeps an opener (planner.lua
-- reads it per way of the phase), not p.alive: a village's taker is unaffected by it. The taker
-- 2 turns away, unacted: 0.85^1 times that chance.
do
    local sight = fakeSight({ open = { { x = 8, y = 0, kind = "chest" },
                                       { x = 7, y = 1, kind = "visit" } },
                              prices = { [0x0E] = 500 } })
    local board = { units = { blue(1, 0, 0) }, turn = 1 }
    local goals = Goals.list(board, sight, { villageGifts = { items = { 0x0E }, gold = {} } }, {})
    local chest, village = find(goals, "chest:8,0"), find(goals, "visit:7,1")
    local pos = { [1] = { x = 0, y = 0, acted = false, alive = 0.9, opens = 0.4 } }
    check(chest ~= nil and village ~= nil, true, "opens: a chest and a village are goals")
    check(math.abs(Goals.chance(chest, pos, G, sight.turnsTo) - 0.4 * G) < 1e-9, true,
          "opens: a chest's taker counts at the chance it lives and keeps a key")
    check(math.abs(Goals.chance(village, pos, G, sight.turnsTo) - 0.9 * G) < 1e-9, true,
          "opens: a village's taker counts at the chance it lives")
    pos[1].opens = nil
    check(math.abs(Goals.chance(chest, pos, G, sight.turnsTo) - 0.9 * G) < 1e-9, true,
          "opens: with no theft read, a chest's taker counts at the chance it lives")
end

-- TestChanceZeroWhenClosedFirst: the taker arrives on player phase 3; a looter closes it after
-- enemy phase 2 -> 0. Closing after phase 3 leaves it.
do
    local tile = { x = 12, y = 0, kind = "visit" }
    local board = { units = { blue(1, 0, 0) }, turn = 1 }
    local pos = { [1] = { x = 0, y = 0, acted = false, alive = 1 } }
    local s1 = fakeSight({ open = { tile }, closings = { ["12,0"] = 2 } })
    local g = find(Goals.list(board, s1, {}, {}), "visit:12,0")
    check(g.closes, 2, "list: the goal carries its closing phase")
    check(Goals.chance(g, pos, G, s1.turnsTo), 0, "chance: closed before we arrive")
    local s2 = fakeSight({ open = { tile }, closings = { ["12,0"] = 3 } })
    g = find(Goals.list(board, s2, {}, {}), "visit:12,0")
    check(Goals.chance(g, pos, G, s2.turnsTo), G ^ 2, "chance: we arrive on the phase it closes after")
end

-- TestChanceTakesTheFastestLiveTaker: takers 1 and 3 turns off. Both alive -> the fast one's;
-- the fast one dead -> the slow one's; the fast one half alive -> the expected best.
do
    local tile = { x = 12, y = 0, kind = "visit" }
    local sight = fakeSight({ open = { tile } })
    local board = { units = { blue(1, 8, 0), blue(2, 0, 0) }, turn = 1 }
    local g = find(Goals.list(board, sight, {}, {}), "visit:12,0")
    local function pos(a1)
        return { [1] = { x = 8, y = 0, acted = false, alive = a1 },
                 [2] = { x = 0, y = 0, acted = false, alive = 1 } }
    end
    check(Goals.chance(g, pos(1), G, sight.turnsTo), 1, "chance: the fastest live taker")
    check(Goals.chance(g, pos(0), G, sight.turnsTo), G ^ 2, "chance: the fastest is dead")
    check(Goals.chance(g, pos(0.5), G, sight.turnsTo), 0.5 * 1 + 0.5 * G ^ 2,
        "chance: the expected best over who lives")
end

-- TestUnusableTakerIsNoTaker: a unit the game refuses Visit, or cut off, takes nothing; a goal
-- with no taker has chance 0.
do
    local tile = { x = 4, y = 0, kind = "visit" }
    local sight = fakeSight({ open = { tile }, noVisit = { [1] = true }, cutOff = { [2] = true } })
    local board = { units = { blue(1, 0, 0), blue(2, 0, 1) }, turn = 1 }
    local g = find(Goals.list(board, sight, {}, {}), "visit:4,0")
    check(#g.takerUnits, 1, "list: the game's Visit check leaves only the able unit")
    check(Goals.chance(g, before({ g }), G, sight.turnsTo), 0, "chance: no way there, no chance")
end

-- TestRewardSharesAcrossNeeds: a 10000-gold reward needing every village shares evenly over the
-- four open ones (2500 each, on top of each village's own); one already lost kills it.
do
    local open = { { x = 1, y = 0, kind = "visit" }, { x = 2, y = 0, kind = "visit" },
                   { x = 3, y = 0, kind = "visit" }, { x = 4, y = 0, kind = "visit" },
                   { x = 5, y = 0, kind = "chest" } }
    local sight = fakeSight({ open = open, prices = { [0x68] = 10000, [0x0E] = 500 } })
    local board = { units = { blue(1, 0, 0) }, turn = 1 }
    local style = { rewards = { { item = 0x68, needs = "villages" } },
                    villageGifts = { items = { 0x0E }, gold = {} } }
    local goals = Goals.list(board, sight, style, {})
    check(find(goals, "visit:1,0").gold, 500 + 2500, "reward: a village's share")
    check(find(goals, "chest:5,0").gold, 500, "reward: a chest is not in its needs")
    goals = Goals.list(board, sight, style, { lost = { ["9,9"] = "visit" } })
    check(find(goals, "visit:1,0").gold, 500, "reward: a village already lost voids it")
    -- tiles: only those named
    style.rewards = { { item = 0x68, needs = { { 1, 0 }, { 2, 0 } } } }
    goals = Goals.list(board, sight, style, {})
    check(find(goals, "visit:1,0").gold, 500 + 5000, "reward: named tiles share it")
    check(find(goals, "visit:3,0").gold, 500, "reward: an unnamed tile does not")
end

-- TestVillagePriorIsTheMeanGift: the mean of every gift's GetItemCost, gold at face value.
do
    local sight = fakeSight({ open = { { x = 1, y = 0, kind = "visit" } },
                              prices = { [1] = 300, [2] = 900 } })
    local goals = Goals.list({ units = { blue(1, 0, 0) }, turn = 1 }, sight,
        { villageGifts = { items = { 1, 2 }, gold = { 3000 } } }, {})
    check(find(goals, "visit:1,0").gold, (300 + 900 + 3000) / 3, "prior: the mean gift")
end

-- TestRecruitWorthIsADeathPlusItems: a recruit is worth its items' prices in gold, and the
-- planner adds one death on top (Goals.worth).
do
    local sight = fakeSight({ prices = { [0x09] = 1200 } })
    local joshua = { id = 0x90, charId = 0x20, x = 4, y = 0, faction = "red", onField = true,
                     items = { { id = 0x09, uses = 30 } } }
    local board = { units = { blue(1, 0, 0), joshua }, turn = 1 }
    local goals = Goals.list(board, sight, {}, { recruitTalkers = { [0x90] = { 1 } } })
    local g = find(goals, "recruit:144")
    check(g.gold, 1200, "recruit: its items")
    check(Goals.worth(g, { gold = 0.04, death = 1000 }), 1000 + 1200 * 0.04,
        "worth: a recruit is one death plus its items")
    check(Goals.worth(find(Goals.list(board, fakeSight({ open = { { x = 1, y = 0, kind = "visit" } } }),
        { villageGifts = { items = {}, gold = { 1000 } } }, {}), "visit:1,0"),
        { gold = 0.04, death = 1000 }), 40, "worth: gold at the style's rate")
end

-- TestRecruitClosesWhereTheGameRemovesIt (#699): sight.closings answers "unit:<id>" -> the enemy
-- phase the game's AI escapes with a recruit it was asked to watch. The goal carries it: a Talk
-- that arrives (two turns off here) after it has chance 0, one the plan leaves unmade in the phase it leaves is
-- forfeit, and the recruit's id reaches sight as the watch set.
do
    local joshua = { id = 0x90, charId = 0x20, x = 8, y = 0, faction = "red", onField = true,
                     items = {} }
    local board = { units = { blue(1, 0, 0), joshua }, turn = 1 }
    local pos = { [1] = { x = 0, y = 0, acted = false, alive = 1 } }
    local watched
    local sight = fakeSight({ closings = { ["unit:144"] = 1 } })
    function sight.closings(_, _, watch)
        watched = watch
        return { ["unit:144"] = 1 }, {}
    end
    local goals = Goals.list(board, sight, {}, { recruitTalkers = { [0x90] = { 1 } } })
    local g = find(goals, "recruit:144")
    check(watched and watched[0x90], true, "recruit closes: the field's recruits are watched")
    check(g.closes, 1, "recruit closes: the phase the game removes it")
    check(Goals.chance(g, pos, G, sight.turnsTo), 0, "recruit closes: a Talk after it is no Talk")
    local ledger = Goals.ledger(goals, sight, {}, { recruitTalkers = { [0x90] = { 1 } } },
                                { [g.id] = 1 })
    check(table.concat(Goals.forfeited(ledger, goals, {}), " "), "recruit:144",
        "recruit closes: removed in this enemy phase and not talked to, it is forfeit")
    check(#Goals.forfeited(ledger, goals, { took = { [g.id] = true } }), 0,
        "recruit closes: a plan that talks to it this phase loses nothing")
    sight.closings = function() return { ["unit:144"] = 2 } end
    g = find(Goals.list(board, sight, {}, { recruitTalkers = { [0x90] = { 1 } } }), "recruit:144")
    check(Goals.chance(g, pos, G, sight.turnsTo) > 0, true, "recruit closes: still reachable before it goes")
end

-- TestRecruitIsMetWhereTheGameMovesIt (#699): the talker is 8 tiles (2 turns) from the recruit's
-- tile now, and the recruit walks east 4 a phase, leaving after phase 3. Priced at his current
-- tile it is reachable (turn 2) but he is gone from it by then; only the tile he stands on at the
-- phase it arrives in counts: (8,0) now, (12,0) after phase 1, (16,0) after phase 2.
do
    local joshua = { id = 0x90, charId = 0x20, x = 8, y = 0, faction = "red", onField = true,
                     items = {} }
    local board = { units = { blue(1, 0, 0), joshua }, turn = 1 }
    local pos = { [1] = { x = 0, y = 0, acted = false, alive = 1 } }
    local sight = fakeSight()
    -- gone after phase 3: the path holds phases 1 and 2 (sight.carryPaths leaves the escape out)
    local path = { { x = 12, y = 0 }, { x = 16, y = 0 } }
    function sight.closings() return { ["unit:144"] = 3 }, { [0x90] = path } end
    local ctx = { recruitTalkers = { [0x90] = { 1 } } }
    local g = find(Goals.list(board, sight, {}, ctx), "recruit:144")
    check(g.path, path, "recruit path: the goal carries the projected tiles")
    check(Goals.chance(g, pos, G, sight.turnsTo), 0,
        "recruit path: a talker 2 turns behind a recruit moving 1 turn a phase never meets him")
    pos[1].x = 2   -- 1.5 turns from (8,0), 2.5 from (12,0), 3.5 from (16,0): always a phase late
    check(Goals.chance(g, pos, G, sight.turnsTo), 0, "recruit path: still behind him")
    pos[1].x = 8   -- on his tile now: meets him in phase 1
    check(Goals.chance(g, pos, G, sight.turnsTo), 1, "recruit path: beside him now")
    pos[1] = { x = 12, y = 0, acted = false, alive = 1 }   -- ahead of him: waits at (16,0), phase 3
    check(Goals.chance(g, pos, G, sight.turnsTo) > 0, true, "recruit path: ahead, it meets him on his way")
    g.path = nil
    pos[1] = { x = 0, y = 0, acted = false, alive = 1 }
    check(Goals.chance(g, pos, G, sight.turnsTo) > 0, true,
        "recruit path: without a path, the current tile is the price")
end

-- test_a_recruit_path_runs_on_where_the_last_attempt_saw_him_walk (#766's stage job, vanilla
-- Ch14's Rennac): the forecast plays one enemy phase of his walk, and he leaves after phase 4.
-- The last attempt saw him walk east from his appearance; this attempt he appeared on turn 3,
-- and it is turn 5, so phases 2 and 3 are where he stood 4 and 5 turns after he appeared. A
-- talker ahead of him meets him only in phase 3: on the forecast alone he is past its end, and
-- the goal reads no chance.
do
    local rennac = { id = 0x90, charId = 0x20, classId = 4, x = 8, y = 0, faction = "red",
                     onField = true, items = {} }
    local board = { units = { blue(1, 24, 0), rennac }, turn = 5 }
    local sight = fakeSight()
    function sight.closings() return { ["unit:144"] = 4 }, { [0x90] = { { x = 12, y = 0 } } } end
    local track = { { turn = 3, phase = "player", x = 6, y = 0 }, { turn = 4, phase = "enemy", x = 8, y = 0 },
                    { turn = 5, phase = "enemy", x = 12, y = 0 }, { turn = 6, phase = "enemy", x = 16, y = 0 },
                    { turn = 7, phase = "enemy", x = 20, y = 0 } }
    local memory = { attempts = { { units = { { key = "r", charId = 0x20, classId = 4, faction = "red",
                                                  arrival = 3, track = track } } } } }
    local ctx = { recruitTalkers = { [0x90] = { 1 } }, turn = 5,
                  appeared = function(c, k) return c == 0x20 and k == 4 and 3 or nil end }
    local g = find(Goals.list(board, sight, { memory = memory }, ctx), "recruit:144")
    local p = g.path or {}
    check(#p .. " " .. p[1].x .. " " .. (p[2] or {}).x .. " " .. (p[3] or {}).x, "3 12 16 20",
          "remembered route: the forecast's phase, then where he walked, up to his removal")
    local pos = { [1] = { x = 24, y = 0, acted = false, alive = 1 } }
    check(Goals.chance(g, pos, G, sight.turnsTo) > 0, true, "remembered route: met in phase 3")
    local m = Goals.meetings(g, board.units[1], pos[1], G, sight.turnsTo)[1]
    check(m and m.tile.x .. "," .. m.tile.y .. " " .. m.f, "16,0 3", "remembered route: the meeting tile and phase")
    g = find(Goals.list(board, sight, {}, ctx), "recruit:144")
    check(Goals.chance(g, pos, G, sight.turnsTo), 0, "no memory: past the forecast he is never met")
end

-- test_meetings_price_each_meeting_on_its_wait (PR #777 review): Goals.meetings' chance is a gamma
-- per turn until the Talk, the trip's and the wait's. His walk is (4,0), then (8,0), and he stays
-- there (no removal). A (at (0,0), 4 tiles a turn) meets him on (4,0) in phase 2 after one turn
-- there and a wait of one, on (8,0) in phase 3 on arrival; past the walk's end it meets him
-- whenever it arrives, waiting from that phase. B, 8 turns from his last tile, meets him only
-- past the walk's end, on its arrival: never at a phase before it gets there (the wait was -4
-- and the chance above 1). A goal with no path is met where it stands.
do
    local goal = { tile = { x = 0, y = 4 }, path = { { x = 4, y = 0 }, { x = 8, y = 0 } } }
    local A, B = { id = 1 }, { id = 2 }
    local function turnsTo(u, tile)
        if u.id == 2 then return (tile.x == 8 and tile.y == 0) and 8 or nil end
        return (math.abs(tile.x) + math.abs(tile.y)) / 4
    end
    local function list(u, g)
        local parts = {}
        for _, m in ipairs(Goals.meetings(g or goal, u, { x = 0, y = 0 }, G, turnsTo)) do
            parts[#parts + 1] = m.tile.x .. "," .. m.tile.y .. "@" .. m.f .. "/" .. m.turns
                .. "=" .. string.format("%.4f", m.c)
        end
        return table.concat(parts, " ")
    end
    check(list(A), "0,4@1/1=1.0000 4,0@2/1=0.8500 8,0@3/2=0.7225 8,0@4/2=0.6141",
          "meetings: a gamma per turn until the Talk, the trip's and the wait's")
    check(list(B), "8,0@8/8=" .. string.format("%.4f", G ^ 7),
          "meetings: past the walk's end, met on arrival, never before it")
    check(list(A, { tile = { x = 8, y = 0 } }), "8,0@2/2=0.8500", "meetings: no path, met where it stands")
end

-- TestRecruitOnALockedTileIsMet (#710, vanilla Ch14's Rennac): his path runs over a chest the
-- taker holds no key for. A Talk is beside the recruit, so his tile's lock is no way's cost: the
-- goal asks turnsTo to leave it out (`beside`), for the path and for the stationary price. A
-- chest goal keeps the lock.
do
    local rennac = { id = 0x90, charId = 0x20, x = 8, y = 0, faction = "red", onField = true,
                     items = {} }
    local board = { units = { blue(1, 0, 0), rennac }, turn = 1 }
    local pos = { [1] = { x = 4, y = 0, acted = false, alive = 1 } }
    local sight = fakeSight()
    local path = { { x = 12, y = 0 }, { x = 16, y = 0 } }
    function sight.closings() return { ["unit:144"] = 3 }, { [0x90] = path } end
    local g = find(Goals.list(board, sight, {}, { recruitTalkers = { [0x90] = { 1 } } }), "recruit:144")
    local locked = { ["12,0"] = true, ["16,0"] = true, ["8,0"] = true }
    local function turnsTo(u, tile, from, beside)
        if locked[tile.x .. "," .. tile.y] and not beside then return nil end
        return sight.turnsTo(u, tile, from)
    end
    check(Goals.chance(g, pos, G, turnsTo) > 0, true, "recruit on a chest: his path is met")
    g.path = nil
    check(Goals.chance(g, pos, G, turnsTo) > 0, true, "recruit on a chest: his own tile is met")
    g.kind = "chest"
    check(Goals.chance(g, pos, G, turnsTo), 0, "a chest goal keeps its lock")
end

-- TestObjectiveGoals: each unit's way to the objective (ctx.objectiveTile) is its own goal,
-- worth one death shared over the army; none where it has no tile (Survive).
do
    local board = { units = { blue(1, 0, 0), blue(2, 1, 0) }, turn = 1 }
    local tiles = { [1] = { x = 6, y = 6 }, [2] = { x = 9, y = 9 } }
    local goals = Goals.list(board, fakeSight(), {}, { objectiveTile = function(u) return tiles[u.id] end })
    local g = find(goals, "objective:1")
    check(g.tile.x .. "," .. g.tile.y, "6,6", "objective: the unit's own way there")
    check(#g.takerUnits == 1 and g.takerUnits[1].id, 1, "objective: the unit is its one taker")
    check(Goals.worth(g, { gold = 0.04, death = 1000 }), 500, "objective: one death over the army")
    check(find(Goals.list(board, fakeSight(), {}, { objectiveTile = function() return nil end }),
        "objective:1"), nil, "objective: none without a tile (Survive)")
end

-- TestEveryStepCounts: a step that leaves the whole turns the same still raises the chance.
do
    local board = { units = { blue(1, 0, 0) }, turn = 1 }
    local g = find(Goals.list(board, fakeSight(), {}, { objectiveTile = function() return { x = 20, y = 0 } end }),
        "objective:1")
    local t = fakeSight().turnsTo
    local far = Goals.chance(g, { [1] = { x = 0, y = 0, acted = true, alive = 1 } }, G, t)
    local near = Goals.chance(g, { [1] = { x = 1, y = 0, acted = true, alive = 1 } }, G, t)
    check(near > far, true, "chance: one step nearer is worth something")
end

-- TestHouseIsNotAVillage: a House (flag 0) is worth the House prior and no 'villages' reward
-- is shared onto it (vanilla Ch1's two Houses held Seth and Eirika for nine turns).
do
    local open = { { x = 1, y = 0, kind = "visit" }, { x = 2, y = 0, kind = "visit", house = true } }
    local sight = fakeSight({ open = open, prices = { [0x68] = 10000 } })
    local style = { rewards = { { item = 0x68, needs = "villages" } },
                    villageGifts = { items = {}, gold = { 1000 } },
                    houseGifts = { items = {}, gold = { 0, 0, 100 } } }
    local goals = Goals.list({ units = { blue(1, 0, 0) }, turn = 1 }, sight, style, {})
    check(find(goals, "visit:1,0").gold, 1000 + 10000, "house: the village takes the whole reward")
    check(find(goals, "visit:2,0").gold, 100 / 3, "house: the House prior, no reward share")
end

-- TestLedger (FR-014, plan T045): the completion ledger at a decision, and what a plan forfeits.
local function ids(list) return table.concat(list, " ") end
local function row(ledger, id)
    for _, r in ipairs(ledger) do if r.id == id then return r end end
end
local function rowIds(ledger)
    local out = {}
    for _, r in ipairs(ledger) do out[#out + 1] = r.id end
    return ids(out)
end
local function chancesOf(goals, sight)
    local out = {}
    for _, g in ipairs(goals) do out[g.id] = Goals.chance(g, before(goals), G, sight.turnsTo) end
    return out
end
do
    local open = { { x = 4, y = 0, kind = "visit" }, { x = 14, y = 9, kind = "visit" },
                   { x = 9, y = 9, kind = "visit" }, { x = 12, y = 0, kind = "visit" },
                   { x = 2, y = 0, kind = "chest" } }
    local joshua = { id = 0x90, charId = 0x20, x = 6, y = 0, faction = "red", onField = true,
                     items = {} }
    -- (14,9) is turns away for unit 1; only unit 2 may use (9,9), and it has no way there
    -- (cut off); a looter takes (12,0) after phase 2, a turn before anyone gets there; no
    -- unit holds what opens the chest
    local sight = fakeSight({ open = open, cutOff = { [2] = true },
                              closings = { ["4,0"] = 1, ["12,0"] = 2 } })
    function sight.canExplore(u, x, y, kind)
        return kind ~= "chest" and not (x == 9 and u.id == 1)
    end
    local board = { units = { blue(1, 0, 0), blue(2, 0, 1), joshua }, turn = 1 }
    local style = { rewards = { { item = 0x68, needs = { { 4, 0 } } },
                                { item = 0x69, needs = { { 4, 0 }, { 9, 9 } } } } }
    local ctx = { recruitTalkers = { [0x90] = { 1 } },
                  objectiveTile = function() return { x = 20, y = 0 } end }
    local goals = Goals.list(board, sight, style, ctx)
    local ledger = Goals.ledger(goals, sight, style, ctx, chancesOf(goals, sight))
    check(rowIds(ledger), "recruit:144 visit:14,9 visit:4,0 reward:1",
          "ledger: the goals still open, then rewards")
    check(row(ledger, "visit:14,9").status, "feasible",
          "ledger: a goal no taker can reach this turn stays feasible")
    check(row(ledger, "visit:9,9"), nil, "ledger: a goal no taker has any way to is no goal")
    check(row(ledger, "visit:12,0"), nil, "ledger: nor one a looter takes before we arrive")
    check(row(ledger, "chest:2,0"), nil, "ledger: a chest no unit of ours may open is no goal")
    check(row(ledger, "reward:2"), nil, "ledger: a reward needing a goal we cannot get is none")
    check(row(ledger, "objective:1"), nil, "ledger: the ways to the objective are the win's")
    check(row(ledger, "visit:4,0").closes_on, 1, "ledger: when a looter closes it")
    check(ids(row(ledger, "reward:1").needs), "visit:4,0", "ledger: what a reward needs")

    check(ids(Goals.forfeited(ledger, goals, { win = 0, took = { ["visit:4,0"] = true } })), "",
          "forfeits: taking the closing tile loses nothing")
    check(ids(Goals.forfeited(ledger, goals, { win = 0 })), "reward:1 visit:4,0",
          "forfeits: a tile the looter closes after this phase, and the reward needing it")
    check(ids(Goals.forfeited(ledger, goals, { win = 0.004, took = { ["visit:4,0"] = true } })),
          "recruit:144 visit:14,9", "forfeits: any chance of the win closes every goal not taken")
    check(ids(Goals.forfeited(ledger, goals, { win = 1e-12, took = { ["visit:4,0"] = true } })),
          "", "forfeits: a win chance of float dust is none")
    check(ids(Goals.forfeited(ledger, goals, { win = 0, took = { ["visit:4,0"] = true },
                                               lost = { [0x90] = 0.01 } })),
          "recruit:144", "forfeits: a recruit killed in any branch with p > 0 is lost")

    -- #714, ADR 0450: a plan that leaves a DATED goal out of reach by its deadline, from a chance
    -- of at least `gone` before it, counts it (visit:14,9 as a dated goal, a looter after phase 3)
    local took = { ["visit:4,0"] = true }
    local dated, undated = {}, {}
    for k, g in ipairs(goals) do
        dated[k], undated[k] = g, g
        if g.id == "visit:14,9" then
            dated[k] = setmetatable({ closes = 3 }, { __index = g })
        end
    end
    local function reachOf(b, a) return { ["visit:14,9"] = { before = b, after = a } } end
    local function lostBy(gs, b, a)
        return ids(Goals.forfeited(ledger, gs, { win = 0, took = took, gone = 0.5,
                                                 reach = reachOf(b, a) }))
    end
    check(lostBy(dated, 0.6, 0), "visit:14,9", "forfeits: a dated goal out of reach by its deadline")
    check(lostBy(dated, 0.3, 0), "", "forfeits: one that was never likelier than not loses nothing")
    check(lostBy(dated, 0.9, 0.2), "", "forfeits: a chance left above none is not lost")
    check(lostBy(undated, 0.6, 0), "", "forfeits: a goal with no deadline is never lost this way")
    check(not pcall(Goals.forfeited, ledger, dated, { win = 0, reach = reachOf(0.6, 0) }), true,
          "forfeits: reach without gone is an error, not a silent no-op")

    -- a sight with no read of who may use a tile, or when it closes
    local blind = fakeSight({ open = open })
    blind.closings = nil
    local g2 = Goals.list(board, blind, {}, ctx)
    local l2 = Goals.ledger(g2, blind, {}, ctx, chancesOf(g2, blind))
    check(row(l2, "visit:4,0").status, "unknown", "ledger: no closings read, unknown")
    check(row(l2, "recruit:144").status, "feasible", "ledger: a recruit needs no tile read")
    check(ids(Goals.forfeited(l2, g2, { win = 1 })), "recruit:144",
          "forfeits: an unknown goal is neither kept nor lost")

    -- ctx.quietGoals (#510 call 3, ADR 0403): a goal no unit has neared for a while is a stalled
    -- ROW. The win no longer forfeits it; a reward needing it is stalled too; unknown wins
    local quiet = { recruitTalkers = ctx.recruitTalkers, objectiveTile = ctx.objectiveTile,
                    quietGoals = { ["visit:4,0"] = true, ["visit:14,9"] = true } }
    local l3 = Goals.ledger(goals, sight, style, quiet, chancesOf(goals, sight))
    check(row(l3, "visit:4,0").status, "stalled", "ledger: a quiet goal's row is stalled")
    check(row(l3, "visit:14,9").status, "stalled", "ledger: each quiet goal's row")
    check(row(l3, "recruit:144").status, "feasible", "ledger: a goal not quiet stays feasible")
    check(row(l3, "reward:1").status, "stalled", "ledger: a reward needing a stalled goal is stalled")
    check(ids(Goals.forfeited(l3, goals, { win = 1 })), "recruit:144",
          "forfeits: the win no longer closes a stalled row (nor the reward needing it)")
    check(ids(Goals.forfeited(l3, goals, { win = 0 })), "",
          "forfeits: a stalled row is not counted even when a looter closes the tile")
    local qb = { recruitTalkers = ctx.recruitTalkers, objectiveTile = ctx.objectiveTile,
                 quietGoals = { ["visit:4,0"] = true } }
    local l4 = Goals.ledger(g2, blind, style, qb, chancesOf(g2, blind))
    check(row(l4, "visit:4,0").status, "unknown", "ledger: an unknown row stays unknown")
end

-- TestKeyOnAnEnemyMakesTheChestAGoal: no player unit holds a Chest Key, but an enemy whose
-- fall gives one stands (sight.keySources), so the chest is a goal and its taker is the unit
-- without the key; with no such enemy it is none (vanilla Ch5x: both chests were never a goal).
do
    local sight = fakeSight({ open = { { x = 2, y = 0, kind = "chest" } } })
    function sight.canExplore() return false end
    function sight.locked() return "chest" end
    local holder = { id = 0x81, x = 3, y = 0, faction = "red", onField = true, items = {} }
    local sources = { holder }
    function sight.keySources() return sources end
    local board = { units = { blue(1, 0, 0), holder }, turn = 1 }
    local goals = Goals.list(board, sight, {}, {})
    local g = find(goals, "chest:2,0")
    check(g and #g.takerUnits, 1, "keys: a chest whose key an enemy drops has a taker")
    sources = {}
    g = find(Goals.list(board, sight, {}, {}), "chest:2,0")
    check(g and #g.takerUnits, 0, "keys: no key on the board, no taker")
end

-- TestTeammateKeyMakesTheChestAGoal (#688, ADR 0479): no enemy drops a key and the unit holds
-- none, but teammate 2's bag holds one that opens the chest for it (sight.bagKey). Only once 2's
-- own trip to the chest stalled (ctx.tried) is the key spare: then a Trade hands it over and the
-- unit is the chest's taker. Before that, and for a door's lock, the key is no one else's way.
do
    local sight = fakeSight({ open = { { x = 2, y = 0, kind = "chest" } } })
    function sight.canExplore() return false end
    function sight.locked() return "chest" end
    function sight.keySources() return {} end
    function sight.isChestLock(lock) return lock == "chest" end
    local key = { id = 0x69, uses = 1, slot = 0 }
    function sight.bagKey(u, m, lock)
        return u.id == 1 and m.id == 2 and lock == "chest" and key or nil
    end
    local board = { units = { blue(1, 0, 0), blue(2, 5, 5) }, turn = 1 }
    local stalled = { tried = { ["chest:2,0"] = { [2] = true } } }
    local g = find(Goals.list(board, sight, {}, stalled), "chest:2,0")
    check(g and #g.takerUnits, 1, "teammate key: a stalled holder's key makes the chest a taker's")
    g = find(Goals.list(board, sight, {}, {}), "chest:2,0")
    check(g and #g.takerUnits, 0, "teammate key: a holder not yet stalled keeps its key")
    local u, m, tile = board.units[1], board.units[2], { x = 2, y = 0 }
    check(Goals.spareKey(sight, stalled, u, m, "chest", tile), key, "spareKey: the stalled holder's key")
    check(Goals.spareKey(sight, stalled, u, m, "door", tile), nil, "spareKey: never a door's")
    check(Goals.spareKey(sight, stalled, m, m, "chest", tile), nil, "spareKey: never the unit's own")
end

-- TestPendingRecruitGoal (#683, ADR 0436): a recruit not on the board yet that ctx.pendingRecruits
-- names is a goal at its remembered tile, taken by the talkers; none for one nobody may Talk.
do
    local board = { units = { blue(1, 0, 0) }, turn = 1 }
    local pending = { ["arrival:14"] = { id = "arrival:14", charId = 14, x = 8, y = 4 } }
    local goals = Goals.list(board, fakeSight(), {}, { recruitTalkers = { ["arrival:14"] = { 1 } },
                                                       pendingRecruits = pending })
    local g = find(goals, "recruit:arrival:14")
    check(g and g.tile.x .. "," .. g.tile.y, "8,4", "pending recruit: a goal at its remembered tile")
    check(g and g.takerUnits[1] and g.takerUnits[1].id, 1, "pending recruit: its talker takes it")
    check(find(Goals.list(board, fakeSight(), {}, { recruitTalkers = {} }), "recruit:arrival:14"), nil,
          "no talker, no goal")
    -- a pending recruit cannot close before its turn: a quiet count never stalls its row (ADR 0403's
    -- stall rule, exempted by ADR 0436), where a board recruit's row stalls as any goal's does
    local ctx = { recruitTalkers = { ["arrival:14"] = { 1 } }, pendingRecruits = pending,
                  quietGoals = { ["recruit:arrival:14"] = true } }
    local sight = fakeSight()
    local goals2 = Goals.list(board, sight, {}, ctx)
    local rows = Goals.ledger(goals2, sight, {}, ctx, { ["recruit:arrival:14"] = 1 })
    check(rows[1] and rows[1].id .. " " .. rows[1].status, "recruit:arrival:14 feasible",
          "pending recruit: quiet readings do not stall it")
    ctx.pendingRecruits = nil
    ctx.recruitTalkers = { ["arrival:14"] = { 1 } }
    local listed = { { id = "recruit:arrival:14", kind = "recruit", unitId = "arrival:14",
                       tile = { x = 8, y = 4 }, takerUnits = {} } }
    rows = Goals.ledger(listed, sight, {}, ctx, { ["recruit:arrival:14"] = 1 })
    check(rows[1] and rows[1].status, "stalled", "a recruit that is not pending stalls on quiet readings")
end

-- A scripted removal (#724): a turn event's DISA of a recruit on turn 12, read on turn 8, closes
-- the goal after enemy phase 4; the AI's earlier escape stays, a removal in the past is none.
do
    local board = { units = { blue(1, 0, 0), { id = 0x85, charId = 0x12, x = 5, y = 5, faction = "green",
                                              onField = true, items = {} } }, turn = 8 }
    local function closes(removals, closings)
        local sight = fakeSight({ closings = closings })
        sight.scriptedUnits = function() return { arrivals = {}, removals = removals } end
        local g = find(Goals.list(board, sight, {}, { recruitTalkers = { [0x85] = { 1 } }, owedRecruits = { [0x12] = true } }), "recruit:133")
        return g and g.closes
    end
    check(closes({ [0x12] = 12 }, nil), 4, "scripted removal: turn 12 read on turn 8 closes after phase 4")
    check(closes({ [0x12] = 12 }, { ["unit:133"] = 2 }), 2, "scripted removal: the AI's earlier escape wins")
    check(closes({ [0x12] = 7 }, nil), nil, "scripted removal: one in the past is none")
    check(closes({}, nil), nil, "scripted removal: none read")
    -- the path is cut to the deadline less one, and sight's own answer is left as it was
    local own = { [0x85] = { [1] = { x = 1, y = 1 }, [2] = { x = 2, y = 2 }, [3] = { x = 3, y = 3 },
                             [4] = { x = 4, y = 4 }, [5] = { x = 5, y = 5 } } }
    local sight = fakeSight({})
    sight.scriptedUnits = function() return { arrivals = {}, removals = { [0x12] = 11 } } end
    function sight.closings() return {}, own end
    local g = find(Goals.list(board, sight, {}, { recruitTalkers = { [0x85] = { 1 } }, owedRecruits = { [0x12] = true } }), "recruit:133")
    check(g.closes, 3, "scripted removal: turn 11 read on turn 8")
    check(g.path[2] ~= nil and g.path[3], nil, "scripted removal: the path stops at deadline less one")
    check(own[0x85][5].x, 5, "scripted removal: sight's own path is not edited")
    -- nobody to watch: the scripts are not asked
    local asked = false
    sight.scriptedUnits = function() asked = true return { arrivals = {}, removals = {} } end
    Goals.list(board, sight, {}, { recruitTalkers = {}, owedRecruits = { [0x12] = true } })
    check(asked, false, "scripted removal: no recruit, no scan")
    -- a talk offered to a unit nobody owes (a two-way talk) asks for no scan either
    Goals.list(board, sight, {}, { recruitTalkers = { [0x85] = { 1 } }, owedRecruits = {} })
    Goals.list(board, sight, {}, { recruitTalkers = { [0x85] = { 1 } } })
    check(asked, false, "scripted removal: a watched unit nobody owes is no scan")
    local owedOnly = find(Goals.list(board, sight, {}, { recruitTalkers = { [0x85] = { 1 } },
                                                          owedRecruits = { [0x99] = true } }), "recruit:133")
    check(owedOnly and owedOnly.closes, nil, "scripted removal: another recruit's owed does not close this one")
end

-- #741, #765: what a retry remembers it lost is a deadline like the game's own. A tile an earlier
-- attempt lost in enemy phase 10 (Timeline.deadlines), read on turn 8, closes after phase 3
-- (this turn's is 1); a later simulated date gives way, an earlier one stays, one past is none.
-- A recruit that left the map from turn 12 is a removal as a script's is.
do
    local board = { units = { blue(1, 0, 0) }, turn = 8 }
    local open = { { x = 4, y = 4, kind = "visit" } }
    local function lost(phase) return Fakeline.memory({ closings = { { x = 4, y = 4, phase = phase } } }) end
    local function closes(memory, simulated, appeared)
        local sight = fakeSight({ open = open, closings = simulated })
        local g = find(Goals.list(board, sight, { memory = memory }, { turn = 8, appeared = appeared }),
                       "visit:4,4")
        return g and g.closes
    end
    check(closes(lost(10), nil), 3, "remembered: enemy phase 10 read on turn 8")
    check(closes(lost(10), { ["4,4"] = 5 }), 3, "remembered: the earlier wins over the simulated")
    check(closes(lost(10), { ["4,4"] = 2 }), 2, "remembered: an earlier simulated stays")
    check(closes(lost(7), nil), nil, "remembered: a phase past closes nothing")
    check(closes(Fakeline.memory({ closings = { { x = 4, y = 4, phase = 12 } } },
                                 { closings = { { x = 4, y = 4, phase = 10 } } }), nil), 3,
          "remembered: the earliest over the attempts")
    local ok = pcall(Goals.list, board, fakeSight({ open = open }), { memory = lost(10) }, {})
    check(ok, false, "remembered: no ctx.turn raises")
    -- #765: a looter our door loaded (Ch14's) razed the tile 3 phases after it appeared. This
    -- attempt it appeared on turn 6: the tile goes in enemy phase 9, after phase 2 read on turn
    -- 8. Before it has appeared, the memory dates nothing (ADR 0464 dropped the loss for good)
    local door = Fakeline.memory({
        arrivals = { { charId = 0x80, classId = 63, x = 1, y = 1, turn = 2,
                       by = { act = "door", x = 2, y = 2 } } },
        closings = { { x = 4, y = 4, phase = 5, closer = 0x80, closerClass = 63,
                       closerKey = "a:128:63:2" } } })
    check(closes(door, nil, function(c, k) return c == 0x80 and k == 63 and 6 or nil end), 2,
          "brought: dated from its appearance this attempt")
    check(closes(door, nil, function() return nil end), nil, "brought: not appeared yet, no date")
    local rb = { units = { blue(1, 0, 0), { id = 0x85, charId = 0x12, x = 5, y = 5, faction = "green",
                                           onField = true, items = {} } }, turn = 8 }
    local sight = fakeSight({})
    sight.scriptedUnits = function() return { arrivals = {}, removals = {} } end
    local function departs(memory, appeared)
        local g = find(Goals.list(rb, sight, { memory = memory },
                                  { turn = 8, recruitTalkers = { [0x85] = { 1 } }, appeared = appeared,
                                    owedRecruits = { [0x12] = true } }), "recruit:133")
        return g and g.closes
    end
    check(departs(Fakeline.memory({ arrivals = { { charId = 0x12, classId = 5, x = 5, y = 5, turn = 3,
                                                  gone = { how = "left", boardTurn = 12 } } } })), 4,
          "remembered departure: turn 12 read on turn 8, as a script's removal")
    -- #765: Ch14's Rennac, loaded by our door on turn 2, gone from turn 11 (9 turns on). This
    -- attempt he appeared on turn 4: gone from turn 13, 5 turns after turn 8
    local rennac = Fakeline.memory({ arrivals = { { charId = 0x12, classId = 5, x = 5, y = 5, turn = 2,
        by = { act = "door", x = 2, y = 2 }, gone = { how = "left", boardTurn = 11 } } } })
    check(departs(rennac, function(c) return c == 0x12 and 4 or nil end), 5,
          "brought departure: dated from his appearance this attempt")
    check(departs(rennac, function() return nil end), nil, "brought departure: not appeared, no date")
end

-- #741 review: a pending recruit an act loads (`by`) has no turn to pass, so a quiet count of it
-- stalls its row as any goal's (else an act this attempt never makes holds the win for good); a
-- timed pending one still waits for its turn.
do
    local function status(p)
        local g = { id = "recruit:arrival:28", kind = "recruit", unitId = "arrival:28" }
        local rows = Goals.ledger({ g }, fakeSight({}), {},
            { pendingRecruits = { ["arrival:28"] = p }, quietGoals = { [g.id] = true } },
            { [g.id] = 0.5 })
        return rows[1] and rows[1].status
    end
    check(status({ charId = 28 }), "feasible", "pending, timed: a quiet count is no stall")
    check(status({ charId = 28, by = { act = "door", x = 22, y = 17 } }), "stalled",
          "pending, loaded by an act: a quiet count stalls it")
end

-- #741 review: a sight with no simulated closings still has the remembered ones.
do
    local sight = fakeSight({ open = { { x = 4, y = 4, kind = "visit" } } })
    sight.closings = nil
    local out = Goals.closings(sight, { memory = Fakeline.memory({ closings = { { x = 4, y = 4, phase = 10 } } }) },
                               { turn = 8 })
    check(out["4,4"], 3, "remembered closing kept without sight.closings")
end

-- An on-field recruit the game's AI takes out of unreachable ground (#724: Ch13's Cormag at (2,13) in
-- the peaks, no tile beside him reachable): his replayed path to a tile a talker reaches is a chance,
-- the control whose path never leaves the peaks stays 0 and so holds no win.
do
    local function chance(path)
        local goal = { id = "recruit:9", kind = "recruit", tile = { x = 2, y = 13 }, path = path,
                       takerUnits = { { id = 1 } } }
        local turnsTo = function(_, tile)   -- the peaks (rows 12 and down): no way beside them
            if tile.y >= 12 then return nil end
            return 1.5
        end
        return Goals.chance(goal, { [1] = { x = 7, y = 5, acted = false, alive = 1 } }, G, turnsTo)
    end
    check(chance({ [1] = { x = 2, y = 13 }, [2] = { x = 2, y = 6 } }) > 0, true,
          "on-field recruit: the AI takes him to a tile a talker reaches")
    check(chance({ [1] = { x = 2, y = 13 }, [2] = { x = 2, y = 13 } }), 0,
          "on-field recruit: one that never leaves the peaks is no chance")
end

-- released: a goal an unstaged release loses (#766): a recruit by the character memory saw its
-- door's units walk off with, a tile goal by the tile they closed; a recruit's own tile is no
-- tile loss
do
    local stakes = { { gone = { [0x1C] = true }, tiles = { ["22,5"] = true } } }
    check(Goals.released({ kind = "recruit", charId = 0x1C, tile = { x = 22, y = 12 } }, stakes), true,
          "released: the recruit who left, by character")
    check(Goals.released({ kind = "recruit", charId = 0x1D, tile = { x = 22, y = 5 } }, stakes), false,
          "released: another recruit, though on a closed tile")
    check(Goals.released({ kind = "chest", tile = { x = 22, y = 5 } }, stakes), true,
          "released: the tile its units closed")
    check(Goals.released({ kind = "chest", tile = { x = 22, y = 3 } }, stakes), false,
          "released: another tile")
    check(Goals.released({ kind = "chest", tile = { x = 22, y = 5 } }, nil), false,
          "released: no release made, nothing lost")
end

print(string.format("%d tests, %d failures", tests, fails))
if fails > 0 then os.exit(1) end
