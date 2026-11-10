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

    -- a sight with no read of who may use a tile, or when it closes
    local blind = fakeSight({ open = open })
    blind.closings = nil
    local g2 = Goals.list(board, blind, {}, ctx)
    local l2 = Goals.ledger(g2, blind, {}, ctx, chancesOf(g2, blind))
    check(row(l2, "visit:4,0").status, "unknown", "ledger: no closings read, unknown")
    check(row(l2, "recruit:144").status, "feasible", "ledger: a recruit needs no tile read")
    check(ids(Goals.forfeited(l2, g2, { win = 1 })), "recruit:144",
          "forfeits: an unknown goal is neither kept nor lost")
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

print(string.format("%d tests, %d failures", tests, fails))
if fails > 0 then os.exit(1) end
