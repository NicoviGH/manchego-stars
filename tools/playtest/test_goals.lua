-- Tests for goals.lua (#510 step 9): the goals still open, their worth and their chance from a
-- board, over a fake sight. What the game's own reads return is the ROM runs' to prove.
-- Run: lua tools/playtest/test_goals.lua
local here = (arg[0]:match("(.*/)")) or "./"
local Goals = dofile(here .. "goals.lua")

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

-- A fake sight: turns = Manhattan distance / mov, rounded up (mov 4); prices by id.
local function fakeSight(o)
    o = o or {}
    local s = {}
    function s.turnsTo(u, tile, from)
        from = from or u
        local d = math.abs(from.x - tile.x) + math.abs(from.y - tile.y)
        if o.cutOff and o.cutOff[u.id] then return nil end
        return math.ceil(d / 4)
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

-- TestChanceDiscountsByTurns: one taker 2 turns away (8 tiles, mov 4), unacted -> it arrives on
-- this turn's player phase 2 -> 0.85^1. After it has acted from the same tile, phase 3: 0.85^2.
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
        G ^ 1, "chance: beside it, acted: next phase")
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

-- TestObjectiveGoals: a Seize map's way there is a goal its Seizers take; a Defeat Boss map's
-- is the boss's tile, every unit a taker; Survive and Rout have none.
do
    local board = { units = { blue(1, 0, 0), blue(2, 1, 0),
                              { id = 0x81, charId = 0x40, x = 9, y = 9, faction = "red",
                                onField = true, isBoss = true, items = {} } }, turn = 1 }
    local seize = Goals.list(board, fakeSight({ objective = { kind = "seize", tile = { x = 6, y = 6 } } }), {}, {})
    local g = find(seize, "objective")
    check(g ~= nil and #g.takerUnits, 1, "objective: Seize, taken by who can Seize")
    check(Goals.worth(g, { gold = 0.04, death = 1000 }), 1000, "objective: worth one death")
    local boss = Goals.list(board, fakeSight({ objective = { kind = "boss" } }), {}, {})
    g = find(boss, "objective")
    check(g.tile.x .. "," .. g.tile.y, "9,9", "objective: the boss's tile")
    check(#g.takerUnits, 2, "objective: every unit goes at the boss")
    check(find(Goals.list(board, fakeSight({ objective = { kind = "survive" } }), {}, {}),
        "objective"), nil, "objective: Survive has no way there")
    check(find(Goals.list(board, fakeSight({ objective = { kind = "rout" } }), {}, {}),
        "objective"), nil, "objective: Rout has none")
end

print(string.format("%d tests, %d failures", tests, fails))
if fails > 0 then os.exit(1) end
