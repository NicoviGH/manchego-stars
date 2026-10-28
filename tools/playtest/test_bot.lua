-- Tests for bot.lua -- the pure policy (no emulator): the greedy core the clear scenarios
-- drive, then Bot.decide's styles over hand-built boards and a fake `sight`.
-- Run: lua tools/playtest/test_bot.lua
local here = (arg[0]:match("(.*/)")) or "./"
local B = dofile(here .. "bot.lua")
local Planner = dofile(here .. "planner.lua")
local Sight = dofile(here .. "sight.lua")
local Board = dofile(here .. "board.lua")

local tests, fails = 0, 0
local function check(got, want, msg)
    tests = tests + 1
    if got ~= want then
        fails = fails + 1
        print(string.format("FAIL: %s\n  got  %s\n  want %s", msg, tostring(got), tostring(want)))
    end
end

-- ── greedy: the old clear-bot core, every case ported unchanged ──────────────────

-- reachable tiles the unit could move to (incl its own); enemies have x,y,hp,is_boss.
local function tiles(...)
    local r = {}
    for _, t in ipairs({ ... }) do r[#r + 1] = { x = t[1], y = t[2] } end
    return r
end

-- No enemy within range of any reachable tile -> nil (nothing to attack).
do
    local reach = tiles({ 0, 0 }, { 1, 0 }, { 2, 0 })
    local enemies = { { x = 8, y = 8, hp = 20, is_boss = false } }
    check(B.pickTarget(reach, enemies, { range = 1 }), nil, "no enemy in range -> nil")
end

-- One enemy orthogonally adjacent to a reachable tile -> that enemy, from that tile.
do
    local reach = tiles({ 5, 5 }, { 5, 6 })
    local enemies = { { x = 5, y = 7, hp = 20, is_boss = false } }  -- adjacent to (5,6)
    local pick = B.pickTarget(reach, enemies, { range = 1 })
    check(pick ~= nil, true, "adjacent enemy is attackable")
    check(pick and pick.target.x, 5, "picks the enemy")
    check(pick and pick.tile.x, 5, "attack tile x")
    check(pick and pick.tile.y, 6, "attack tile is the adjacent reachable tile")
end

-- The boss is preferred over a non-boss when both are attackable.
do
    local reach = tiles({ 3, 3 }, { 3, 4 }, { 6, 6 })
    local enemies = {
        { x = 3, y = 5, hp = 10, is_boss = false },  -- adjacent to (3,4)
        { x = 6, y = 7, hp = 40, is_boss = true },   -- adjacent to (6,6)
    }
    local pick = B.pickTarget(reach, enemies, { range = 1 })
    check(pick and pick.target.is_boss, true, "boss preferred over non-boss")
end

-- Among non-boss targets, the lowest-HP one wins (likeliest kill).
do
    local reach = tiles({ 0, 1 }, { 2, 1 })
    local enemies = {
        { x = 0, y = 2, hp = 18, is_boss = false },  -- adjacent to (0,1)
        { x = 2, y = 2, hp = 5, is_boss = false },   -- adjacent to (2,1)
    }
    local pick = B.pickTarget(reach, enemies, { range = 1 })
    check(pick and pick.target.hp, 5, "lowest-hp non-boss preferred")
end

-- Range 2 (e.g. a hand axe): an enemy two tiles from a reachable tile is attackable.
do
    local reach = tiles({ 4, 4 })
    local enemies = { { x = 4, y = 6, hp = 20, is_boss = false } }  -- distance 2 from (4,4)
    check(B.pickTarget(reach, enemies, { range = 1 }), nil, "range 1 can't reach distance 2")
    local pick = B.pickTarget(reach, enemies, { range = 2 })
    check(pick ~= nil, true, "range 2 reaches distance 2")
end

-- A BOW (min_range 2): an ADJACENT enemy is NOT attackable -- striking from range 1 leaves
-- no Attack command, so pickTarget must skip the adjacent tile (#65 recordrbgtest bug).
do
    local adjacent = tiles({ 4, 5 })  -- distance 1 from the foe at (4,6)
    local enemies = { { x = 4, y = 6, hp = 20, is_boss = false } }
    check(B.pickTarget(adjacent, enemies, { range = 2, min_range = 2 }), nil,
          "bow (min_range 2) won't pick an adjacent tile it can't fire from")
    -- but a true range-2 tile IS picked, and an adjacent one is left out of a mixed reach.
    local mixed = tiles({ 4, 5 }, { 4, 4 })  -- (4,5)=dist 1, (4,4)=dist 2
    local pick = B.pickTarget(mixed, enemies, { range = 2, min_range = 2 })
    check(pick ~= nil and pick.tile.x == 4 and pick.tile.y == 4, true,
          "bow strikes from the range-2 tile (4,4), not the adjacent (4,5)")
end

-- ── pickMove (#60 last-mile breach) ─────────────────────────────────────────────

local P = dofile(here .. "pathing.lua")

-- Best field tile wins; Manhattan tiebreak on a plateau.
do
    local field = { [0] = { [0] = 4, [1] = 3, [2] = 3 } }   -- fd row y=0
    local reach = tiles({ 0, 0 }, { 1, 0 }, { 2, 0 })
    local mv = B.pickMove(reach, { field = field, cur = { x = 0, y = 0 },
                                   goal = { x = 9, y = 0 } })
    check(mv.x, 2, "plateau tiebreak: same fd -> nearer the goal by Manhattan")
end

-- Blocked tiles (claimed by a friendly this phase) are skipped.
do
    local field = { [0] = { [0] = 4, [1] = 3, [2] = 2 } }
    local reach = tiles({ 0, 0 }, { 1, 0 }, { 2, 0 })
    local blocked = { [B.tileKey(2, 0)] = true }
    local mv = B.pickMove(reach, { field = field, cur = { x = 0, y = 0 },
                                   goal = { x = 9, y = 0 }, blocked = blocked })
    check(mv.x, 1, "blocked best tile -> next-best field tile")
end

-- Chokepoint jam: nothing reachable improves the current fd -> push at the
-- nearest CORK enemy. The cork sits OFF the goal axis so this answer differs
-- from the plain field+Manhattan pick -- deleting the fallback fails this test.
do
    local field = { [0] = { [0] = 8, [1] = 8, [2] = 8 },
                    [1] = { [0] = 8, [1] = 8, [2] = 8 } }   -- a plateau, no progress
    local reach = tiles({ 0, 0 }, { 1, 0 }, { 2, 0 })
    local mv = B.pickMove(reach, { field = field, cur = { x = 2, y = 0 },
                                   goal = { x = 9, y = 0 },
                                   enemies = { { x = 0, y = 1, hp = 20 } } })  -- cork, fd 8
    check(mv.x .. "," .. mv.y, "0,0", "jammed march -> tile nearest the off-axis cork")
end

-- A straggler BEHIND the advance (farther from the boss than we are) never
-- triggers the fallback: the follower whose best tile is claimed holds the
-- line instead of marching backward (the oscillation bug).
do
    local field = { [0] = { [0] = 10, [1] = 9, [2] = 8, [3] = 7 } }
    local reach = tiles({ 1, 0 }, { 2, 0 }, { 3, 0 })
    local blocked = { [B.tileKey(3, 0)] = true }             -- leader claimed the front
    local mv = B.pickMove(reach, { field = field, cur = { x = 2, y = 0 },
                                   goal = { x = 9, y = 0 }, blocked = blocked,
                                   enemies = { { x = 0, y = 0, hp = 20 } } })  -- fd 10 > cur 8
    check(mv.x, 2, "straggler behind never pulls the follower backward")
end

-- Field-less tiles fall back to Manhattan-toward-goal (off-field never beats on-field).
do
    local field = { [0] = { [1] = 5 } }
    local reach = tiles({ 0, 0 }, { 1, 0 })
    local mv = B.pickMove(reach, { field = field, cur = { x = 0, y = 0 },
                                   goal = { x = 9, y = 0 } })
    check(mv.x, 1, "on-field tile beats field-less tile")
end

-- ── Simulated march over the REPORTED ch01 jam geometry (issue #60, 2026-06-25) ──
-- Boss at (21,7) on the gate, walls at (20,7)/(22,7), open approach (21,8)/(21,6);
-- escort at (20,10); two units start at (14,8)/(13,8) with move 5. The old bot sat
-- at fd 8 for 3 turns; the new decision must keep strictly closing until a unit
-- stands in attack range of the boss or has engaged the escort.
do
    local W, H = 25, 16
    local wall = { [B.tileKey(20, 7)] = true, [B.tileKey(22, 7)] = true,
                   [B.tileKey(20, 6)] = true, [B.tileKey(22, 6)] = true,
                   [B.tileKey(20, 5)] = true, [B.tileKey(21, 5)] = true,
                   [B.tileKey(22, 5)] = true }
    local function passable(x, y) return not wall[B.tileKey(x, y)] end
    local boss = { x = 21, y = 7 }
    local field = P.distanceField(W, H, passable, boss)
    local units = { { x = 14, y = 8 }, { x = 13, y = 8 } }
    local enemies = { { x = 20, y = 10, hp = 20, is_boss = false },
                      { x = boss.x, y = boss.y, hp = 30, is_boss = true } }
    local MOVE = 5
    local function reachFor(u, blocked)
        local r = {}
        for dy = -MOVE, MOVE do
            for dx = -MOVE, MOVE do
                local x, y = u.x + dx, u.y + dy
                if Board.distance(0, 0, dx, dy) <= MOVE and x >= 0 and y >= 0
                    and x < W and y < H and passable(x, y)
                    and not blocked[B.tileKey(x, y)] then
                    r[#r + 1] = { x = x, y = y }
                end
            end
        end
        r[#r + 1] = { x = u.x, y = u.y }
        return r
    end
    local engaged = false
    for turn = 1, 6 do
        local claimed = {}
        for _, u in ipairs(units) do
            local blocked = {}
            for k in pairs(claimed) do blocked[k] = true end
            for _, o in ipairs(units) do
                if o ~= u then blocked[B.tileKey(o.x, o.y)] = true end
            end
            local reach = reachFor(u, blocked)
            local atk = B.pickTarget(reach, enemies, { range = 1 })
            if atk then engaged = true break end
            local mv = B.pickMove(reach, { field = field, cur = u,
                                           goal = boss, blocked = blocked,
                                           enemies = enemies })
            if mv then u.x, u.y = mv.x, mv.y end
            claimed[B.tileKey(u.x, u.y)] = true
        end
        if engaged then break end
    end
    check(engaged, true, "walled-camp march: a unit reaches attack range within 6 turns")
end
-- gridHostileInReach (#204): the clear-bot must decide from the ENGINE'S tile->unit grid, not
-- from the unit array. A red the grid does not know about is not attackable, and pressing the
-- command menu's row 0 anyway lands on Item.
do
    -- gridAt over a sparse {["x,y"] = byte} table; nil off-map.
    local function gridOf(t)
        return function(x, y)
            if x < 0 or x > 14 or y < 0 or y > 14 then return nil end
            return t[x .. "," .. y] or 0
        end
    end

    check(B.gridHostileInReach(gridOf({ ["6,5"] = 0x81 }), 5, 5, 1, 1), true,
        "hostile adjacent ON THE GRID -> attackable")

    -- The #204 regression: the unit array says an enemy is at (6,5), but it stands in fog so
    -- RefreshUnitsOnBmMap never wrote it to gBmMapUnit. There is no Attack row.
    check(B.gridHostileInReach(gridOf({}), 5, 5, 1, 1), false,
        "enemy absent from the grid (fogged) -> NOT attackable")

    check(B.gridHostileInReach(gridOf({ ["6,5"] = 0x01 }), 5, 5, 1, 1), false,
        "a BLUE id on the grid is not a hostile")
    check(B.gridHostileInReach(gridOf({ ["6,5"] = 0x41 }), 5, 5, 1, 1), false,
        "a GREEN id on the grid is not a hostile")

    -- A bow cannot fire at an adjacent foe: min range 2.
    check(B.gridHostileInReach(gridOf({ ["6,5"] = 0x81 }), 5, 5, 2, 2), false,
        "bow: hostile at range 1 is out of [2,2]")
    check(B.gridHostileInReach(gridOf({ ["7,5"] = 0x81 }), 5, 5, 2, 2), true,
        "bow: hostile at range 2 is attackable")

    -- Diagonals count as range 2 (Manhattan), and the map edge must not throw.
    check(B.gridHostileInReach(gridOf({ ["1,1"] = 0x81 }), 0, 0, 1, 2), true,
        "diagonal hostile is at Manhattan 2")
    check(B.gridHostileInReach(gridOf({}), 0, 0, 1, 2), false,
        "off-map probes at the corner are safe")
end

-- Stall progress (#510 step 9). Distance is measured from the units that can still be the
-- one to finish: once the boss is dead the field points at the seize tile, and a unit that
-- the game says cannot Seize is excluded, so the lord's march is what counts.
do
    -- field[y][x] = steps to the target; a 1-row map, target at x = 9.
    local field = { [0] = {} }
    for x = 0, 9 do field[0][x] = 9 - x end
    local function u(slot, x) return { slot = slot, x = x, y = 0, onField = true } end
    local excluded = { [2] = true }   -- slot 2: CanUnitSeize says no
    check(B.seizeDistance({ u(1, 3), u(2, 8) }, field, excluded), 6,
        "the excluded unit beside the tile does not mask the lord's distance")
    check(B.seizeDistance({ u(1, 3), { slot = 3, x = -1, y = -1, onField = false } }, field, {}), 6,
        "an off-field unit has no distance")
    check(B.seizeDistance({ u(2, 8) }, field, excluded), math.huge,
        "nobody left who could seize -> no distance")
    check(B.seizeDistance({ u(1, 3) }, nil, {}), math.huge, "no field -> no distance")

    -- boss dead, the lord marching: its seize distance falls -> progress
    local last = { dist = 6, enemies = 0 }
    check(B.madeProgress(last, { dist = 3, enemies = 0 }), true,
        "boss dead + seize distance falling = progress")
    -- boss dead, nobody closer, no fewer enemies -> no progress
    check(B.madeProgress(last, { dist = 6, enemies = 0 }), false,
        "boss dead + distance unchanged + enemy count unchanged = no progress")
    check(B.madeProgress({ dist = math.huge, enemies = 3 },
                         { dist = math.huge, enemies = 2 }), true,
        "a kill is progress even with no distance")
    check(B.madeProgress({ dist = 4, enemies = 2 }, { dist = 5, enemies = 2 }), false,
        "moving away with no kill is not progress")
    -- the target changed (the boss died): the old best belonged to another
    -- question, so the change counts, and a farther first reading is not a stall
    check(B.madeProgress({ dist = 4, enemies = 0, key = "boss" },
                         { dist = 10, enemies = 0, key = "seize" }),
        true, "a new target is progress, not a stall against the old best")
    check(B.madeProgress({ dist = 10, enemies = 0, key = "seize" },
                         { dist = 10, enemies = 0, key = "seize" }),
        false, "same target, same distance, same enemies = no progress")
end

-- stepOffTile: a unit that cannot Seize clears the throne's approach. From its reachable tiles,
-- the one FARTHEST from the seize tile, never on or beside it; ties go to the shorter move.
do
    local seize = { x = 5, y = 5 }
    local reach = tiles({ 5, 4 }, { 4, 4 }, { 5, 2 }, { 3, 5 }, { 5, 1 })
    local t = B.stepOffTile(reach, { x = 5, y = 4 }, seize)
    check(t and t.x, 5, "steps to the farthest reachable tile (x)")
    check(t and t.y, 1, "steps to the farthest reachable tile (y)")
    check(B.stepOffTile(tiles({ 5, 4 }, { 4, 5 }), { x = 5, y = 4 }, seize), nil,
        "only tiles beside the throne reachable -> nil (no move that helps)")
    -- tie on distance from the throne: the shorter move wins
    local tie = B.stepOffTile(tiles({ 5, 8 }, { 8, 5 }), { x = 6, y = 8 }, seize)
    check(tie and tie.x, 5, "tie on throne distance -> the nearer tile")
    check(B.needsToStepOff({ x = 5, y = 4 }, seize), true, "beside the throne -> step off")
    check(B.needsToStepOff({ x = 5, y = 5 }, seize), true, "on the throne -> step off")
    check(B.needsToStepOff({ x = 5, y = 3 }, seize), false, "two away -> stay")
end

-- ── Bot.decide (#510 step 9): one action per call, over Board.read's shape ──────────

-- A board unit as Board.read returns it (only the fields the policy reads). `id` is the
-- unit's own index byte: blue 0x01.., red 0x81.., unique across factions.
local function unit(o)
    return {
        id = o.id, slot = o.slot or 0, faction = o.faction or "blue", charId = o.charId or o.id,
        x = o.x, y = o.y, hp = o.hp or 20, maxhp = o.maxhp or o.hp or 20,
        onMap = true, onField = o.onField ~= false, dead = false, acted = o.acted or false,
        minRange = o.minRange == nil and 1 or o.minRange or nil,
        maxRange = o.maxRange == nil and 1 or o.maxRange or nil,
        isBoss = o.isBoss or false, classId = o.classId,
    }
end
local function blue(id, slot, x, y, o)
    o = o or {}; o.id, o.slot, o.x, o.y = id, slot, x, y; return unit(o)
end
local function red(id, x, y, o)
    o = o or {}; o.id, o.slot, o.x, o.y, o.faction = id, id - 0x81, x, y, "red"; return unit(o)
end
local function boardOf(...)
    return { turn = 1, phase = "blue", map = { w = 15, h = 10 }, units = { ... } }
end

-- A fake sight. danger["x,y"] = count; reach[id] = tile list; fc[uid][tid]["x,y"] = one entry
-- holding both reads of that exchange -- our attack (hit, dmg, counter*...) and the enemy's
-- strike (taken*) -- which sight.attack and sight.strike each return (a missing entry is a
-- harmless exchange: nothing dealt, nothing taken).
local QUIET = { hit = 0, dmg = 0, crit = 0, hits = 0, counters = false, counterHit = 0,
                counterDmg = 0, counterCrit = 0, counterHits = 0, takenHit = 0, takenDmg = 0,
                takenCrit = 0, takenHits = 0, killsTarget = false }
local function sightOf(o)
    local attacks, strikes = 0, 0
    local function entry(u, t, x, y)
        local byT = (o.fc or {})[u.id]
        local byTile = byT and byT[t.id]
        return (byTile and byTile[x .. "," .. y]) or QUIET
    end
    local s = {
        objective = o.objective or { kind = "rout" },
        field = o.field,
        cache = o.cache,
        terrain = o.terrain,
        -- The game's equipped-weapon reach, modelled by the board unit's own range.
        range = function(u) return u.minRange and { min = u.minRange, max = u.maxRange } or nil end,
        -- The game's CanUnitSeize, modelled by the objective's lord (anyone, when none is named).
        canSeize = function(u)
            local lord = (o.objective or {}).lord
            return lord == nil or u.charId == lord
        end,
        danger = function(x, y) return (o.danger or {})[x .. "," .. y] or 0 end,
        reach = function(u) return (o.reach or {})[u.id] or { { x = u.x, y = u.y } } end,
        -- The game's one-enemy danger zone, modelled here by its reach and held weapon's range.
        threat = function(e)
            local tiles = (o.reach or {})[e.id] or { { x = e.x, y = e.y } }
            return function(x, y)
                if not e.minRange then return 0 end
                local n = 0
                for _, t in ipairs(tiles) do
                    local d = Board.distance(t.x, t.y, x, y)
                    if d >= e.minRange and d <= e.maxRange then n = n + 1 end
                end
                return n
            end
        end,
        attack = function(u, t, x, y)
            attacks = attacks + 1
            return entry(u, t, x, y)
        end,
        strike = function(u, t, x, y)
            strikes = strikes + 1
            return entry(u, t, x, y)
        end,
    }
    -- The game reads PR E added (each optional, as in sight.lua's callers): obstacles, doors,
    -- staves/heals/mend, the Talk check, key holders, and fog.
    for _, k in ipairs({ "obstacles", "doors", "unseen" }) do
        if o[k] then s[k] = function() return o[k] end end
    end
    if o.staves then s.staves = function(u) return o.staves[u.id] or {} end end
    if o.heals then s.heals = function(u, x, y) return (o.heals[u.id] or {})[x .. "," .. y] or {} end end
    if o.mend then s.mend = function(u) return o.mend[u.id] end end
    if o.talk then s.canTalk = function(u, t) return (o.talk[u.id] or {})[t.id] == true end end
    if o.keys then s.holdsKey = function(u) return o.keys[u.id] == true end end
    if o.openers then s.opensDoor = function(u) return o.openers[u.id] == true end end
    if o.hidden then s.visible = function(x, y) return not o.hidden[x .. "," .. y] end end
    -- villages and chests: the open tiles, and the unit menu's check per unit and tile
    if o.explorable then
        s.explorable = function() return o.explorable end
        s.canExplore = function(u, x, y, kind)
            return ((o.canExplore or {})[u.id] or {})[x .. "," .. y] == kind
        end
    end
    s.hitChance = Sight.hitChance
    if o.enemyPhase then s.enemyPhase = o.enemyPhase end
    s.attacks = function() return attacks end
    s.strikes = function() return strikes end
    s.calls = function() return attacks + strikes end
    return s
end
local function fc(o)
    local f = {}
    for k, v in pairs(QUIET) do f[k] = v end
    for k, v in pairs(o) do f[k] = v end
    return f
end
local function style(aggression) return { aggression = aggression, deploy = {}, claims = {} } end
local function at(a) return a and a.move and (a.move.x .. "," .. a.move.y) end

-- test_careful_never_ends_on_a_tile_where_worst_case_kills: A (hp 20) can kill E1 only from
-- (2,0), and E2 reaches (2,0) for 12 x 2 = 24 >= 20. Careful refuses the kill and ends safe;
-- bold, gated by the exchange alone, takes it.
do
    local A = blue(0x01, 0, 0, 0, { hp = 20 })
    local E1 = red(0x81, 3, 0, { hp = 5 })
    local E2 = red(0x82, 2, 3)
    local board = boardOf(A, E1, E2)
    local sight = sightOf {
        danger = { ["2,0"] = 1 },
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }, { 2, 0 }),
                  [0x82] = tiles({ 2, 3 }, { 2, 1 }) },
        fc = { [0x01] = {
            [0x81] = { ["2,0"] = fc { hit = 100, dmg = 9, hits = 1, killsTarget = true } },
            [0x82] = { ["2,0"] = fc { takenHit = 70, takenDmg = 12, takenHits = 2 } },
        } },
    }
    local careful = B.decide(board, sight, style("careful"))
    check(careful and careful.act, "wait", "careful: the lethal end tile refuses the kill")
    check(careful and careful.move.x ~= 2, true, "careful: ends off the tile E2 reaches")
    local bold = B.decide(board, sight, style("bold"))
    check(bold and bold.act, "attack", "bold: takes the kill the exchange allows")
    check(bold and bold.target, 0x81, "bold: the target is E1")
    check(at(bold), "2,0", "bold: strikes from (2,0)")
end

-- A unit that cannot Seize, boxed in ON the seize tile, still has its own tile: it waits there
-- rather than finding no tile at all.
do
    local L = blue(0x01, 0, 0, 0, { charId = 0x0F, acted = true })
    local O = blue(0x02, 1, 4, 4, { minRange = false, maxRange = false })
    local sight = sightOf {
        objective = { kind = "seize", tile = { x = 4, y = 4 }, lord = 0x0F },
        reach = { [0x02] = tiles({ 4, 4 }) },
    }
    for _, aggr in ipairs({ "careful", "even", "bold", "greedy" }) do
        local ok, a = pcall(B.decide, boardOf(L, O, red(0x81, 9, 9)), sight, style(aggr))
        check(ok, true, aggr .. ": a boxed-in non-lord on the throne does not crash")
        check(ok and at(a), "4,4", aggr .. ": it waits where it stands")
    end
end

-- The attack's own counter comes off HP before the enemy phase is weighed: A (hp 20) takes a
-- 15 counter striking E1, then the enemy phase (E2's 10, E1's 15 again). Without the counter
-- careful read 25 against 20; even read 15 < 20 and struck. 15 off the HP refuses both.
do
    local A = blue(0x01, 0, 0, 0, { hp = 20 })
    local E1 = red(0x81, 3, 0, { hp = 30 })
    local E2 = red(0x82, 2, 3)
    local board = boardOf(A, E1, E2)
    local function sightWith(counter)
        return sightOf {
            danger = { ["2,0"] = 1 },
            reach = { [0x01] = tiles({ 0, 0 }, { 2, 0 }), [0x82] = tiles({ 2, 1 }) },
            fc = { [0x01] = {
                [0x81] = { ["2,0"] = fc { hit = 80, dmg = 5, hits = 1, counters = true,
                                          counterHit = 90, counterDmg = counter, counterHits = 1,
                                          takenHit = 90, takenDmg = counter, takenHits = 1 } },
                [0x82] = { ["2,0"] = fc { takenHit = 70, takenDmg = 10, takenHits = 1 } },
            } },
        }
    end
    check(B.decide(board, sightWith(15), style("careful")).act, "wait",
        "careful: counter 15 + enemy phase 10 >= 20 refuses the strike")
    check(B.decide(board, sightWith(15), style("even")).act, "wait",
        "even: 10 < 20 - 15 fails too")
    -- An enemy that cannot answer this attack (out of its weapon's range) takes nothing off
    -- first: no counter*, and its taken* -- its own strike on its phase -- is weighed there.
    local unanswered = sightWith(15)
    local quiet = unanswered.attack
    unanswered.attack = function(...)
        local f = quiet(...)
        if f.dmg > 0 then
            local g = {}
            for k, v in pairs(f) do g[k] = v end
            g.counters, g.counterHit, g.counterDmg, g.counterHits = false, 0, 0, 0
            return g
        end
        return f
    end
    check(B.decide(board, unanswered, style("even")).act, "attack",
        "even: no counter, and no single enemy's 10 or 15 reaches 20")
    -- The enemy phase reads E1's OWN strike (taken*), not its counter: a 3 counter, but on its
    -- phase E1's AI picks a weapon that deals 15. 3 + (10 + 15) = 28 >= 20 refuses; reading
    -- the counter for both would have said 3 + (10 + 3) = 16 and struck.
    local s2 = sightOf {
        danger = { ["2,0"] = 1 },
        reach = { [0x01] = tiles({ 0, 0 }, { 2, 0 }), [0x82] = tiles({ 2, 1 }) },
        fc = { [0x01] = {
            [0x81] = { ["2,0"] = fc { hit = 80, dmg = 5, hits = 1, counters = true,
                                      counterHit = 90, counterDmg = 3, counterHits = 1,
                                      takenHit = 90, takenDmg = 15, takenHits = 1 } },
            [0x82] = { ["2,0"] = fc { takenHit = 70, takenDmg = 10, takenHits = 1 } },
        } },
    }
    check(B.decide(board, s2, style("careful")).act, "wait",
        "careful weighs the enemy's next-phase strike, not its counter")
    -- E1 survives the strike and swings again on the enemy phase: 3 + (10 + 3) = 16 < 20
    check(B.decide(board, sightWith(3), style("careful")).act, "attack",
        "a 3 counter leaves room for the enemy phase: the strike is allowed")
    -- a sure first-blow kill takes no counter
    local weak = red(0x81, 3, 0, { hp = 5 })
    local s = sightOf {
        danger = { ["2,0"] = 1 },
        reach = { [0x01] = tiles({ 0, 0 }, { 2, 0 }), [0x82] = tiles({ 2, 1 }) },
        fc = { [0x01] = {
            [0x81] = { ["2,0"] = fc { hit = 100, dmg = 9, hits = 1, killsTarget = true,
                                      counters = true, counterHit = 90, counterDmg = 15,
                                      counterHits = 1, takenHit = 90, takenDmg = 15,
                                      takenHits = 1 } },
            [0x82] = { ["2,0"] = fc { takenHit = 70, takenDmg = 10, takenHits = 1 } },
        } },
    }
    check(B.decide(boardOf(A, weak, E2), s, style("careful")).act, "attack",
        "a sure kill on the first blow is never countered")
end

-- The kill chance counts every blow the kill needs: a doubling 70% that needs both (49%)
-- loses to a single 60% blow.
do
    local A = blue(0x01, 0, 0, 0)
    local E1 = red(0x81, 1, 0, { hp = 10 })
    local E2 = red(0x82, 0, 1, { hp = 10 })
    local s = sightOf {
        fc = { [0x01] = {
            [0x81] = { ["0,0"] = fc { hit = 70, dmg = 5, hits = 2, killsTarget = true } },
            [0x82] = { ["0,0"] = fc { hit = 60, dmg = 10, hits = 1, killsTarget = true } },
        } },
    }
    check(B.decide(boardOf(A, E1, E2), s, style("careful")).target, 0x82,
        "60% in one blow beats 70% needed twice")
    -- 4% once and 20% twice are the SAME chance: the tie goes on to expected damage (E2's)
    s = sightOf {
        fc = { [0x01] = {
            [0x81] = { ["0,0"] = fc { hit = 20, dmg = 5, hits = 2, killsTarget = true } },
            [0x82] = { ["0,0"] = fc { hit = 4, dmg = 60, hits = 1, killsTarget = true } },
        } },
    }
    check(B.decide(boardOf(A, E1, E2), s, style("careful")).target, 0x82,
        "equal kill chances tie exactly; expected damage (60 x 4 > 5 x 2 x 20) decides")
    -- a kill only a crit lands (10 HP at 2 a blow, 2 blows) ranks as no kill chance at all
    s = sightOf {
        fc = { [0x01] = {
            [0x81] = { ["0,0"] = fc { hit = 90, dmg = 2, hits = 2, killsTarget = true } },
            [0x82] = { ["0,0"] = fc { hit = 30, dmg = 10, hits = 1, killsTarget = true } },
        } },
    }
    check(B.decide(boardOf(A, E1, E2), s, style("careful")).target, 0x82,
        "a crit-only kill (5 blows needed) loses to a 30% plain kill")
end

-- even weighs each enemy on its own: two enemies at 12 each (24 together) kill A only
-- together, so careful refuses the tile and even takes it.
do
    local A = blue(0x01, 0, 0, 0, { hp = 20 })
    local E1 = red(0x81, 3, 0, { hp = 5 })
    local E2 = red(0x82, 2, 3)
    local E3 = red(0x83, 2, 5)
    local board = boardOf(A, E1, E2, E3)
    local sight = sightOf {
        danger = { ["2,0"] = 2 },
        reach = { [0x01] = tiles({ 0, 0 }, { 2, 0 }), [0x82] = tiles({ 2, 1 }),
                  [0x83] = tiles({ 3, 1 }) },  -- (3,1) is 2 from (2,0): needs E3 at range 2
        fc = { [0x01] = {
            [0x81] = { ["2,0"] = fc { hit = 100, dmg = 9, hits = 1, killsTarget = true } },
            [0x82] = { ["2,0"] = fc { takenHit = 70, takenDmg = 12, takenHits = 1 } },
            [0x83] = { ["2,0"] = fc { takenHit = 70, takenDmg = 12, takenHits = 1 } },
        } },
    }
    board.units[4].maxRange = 2
    check(B.decide(board, sight, style("careful")).act, "wait", "careful: 12 + 12 >= 20 refuses")
    check(B.decide(board, sight, style("even")).act, "attack", "even: no single enemy kills")
    -- a crit chance triples the worst case: one enemy at 7 with crit 1 is 21 >= 20
    sight = sightOf {
        danger = { ["2,0"] = 1 },
        reach = { [0x01] = tiles({ 0, 0 }, { 2, 0 }), [0x82] = tiles({ 2, 1 }) },
        fc = { [0x01] = {
            [0x81] = { ["2,0"] = fc { hit = 100, dmg = 9, hits = 1, killsTarget = true } },
            [0x82] = { ["2,0"] = fc { takenHit = 70, takenDmg = 7, takenHits = 1, takenCrit = 1 } },
        } },
    }
    board = boardOf(A, E1, E2)
    check(B.decide(board, sight, style("even")).act, "wait", "worst case counts the crit (7 x 3)")
    -- an enemy that cannot hit (takenHit 0) adds nothing
    sight = sightOf {
        danger = { ["2,0"] = 1 },
        reach = { [0x01] = tiles({ 0, 0 }, { 2, 0 }), [0x82] = tiles({ 2, 1 }) },
        fc = { [0x01] = {
            [0x81] = { ["2,0"] = fc { hit = 100, dmg = 9, hits = 1, killsTarget = true } },
            [0x82] = { ["2,0"] = fc { takenHit = 0, takenDmg = 30, takenHits = 2 } },
        } },
    }
    check(B.decide(board, sight, style("careful")).act, "attack", "a 0% hit is no threat")
end

-- A sure kill's target does not counter in the enemy phase; a kill that may miss still might.
do
    local A = blue(0x01, 0, 0, 0, { hp = 20 })
    local E1 = red(0x81, 3, 0, { hp = 5 })
    local board = boardOf(A, E1)
    local function sightWith(hit)
        return sightOf {
            danger = { ["2,0"] = 1 },
            reach = { [0x01] = tiles({ 0, 0 }, { 2, 0 }), [0x81] = tiles({ 3, 0 }) },
            fc = { [0x01] = { [0x81] = { ["2,0"] = fc { hit = hit, dmg = 9, hits = 1,
                killsTarget = true, takenHit = 80, takenDmg = 11, takenHits = 2 } } } },
        }
    end
    check(B.decide(board, sightWith(100), style("careful")).act, "attack",
        "careful: a sure kill removes its target from the worst case")
    check(B.decide(board, sightWith(90), style("careful")).act, "wait",
        "careful: a 90% kill leaves the target's 22 in the worst case")
end

-- test_takes_a_sure_kill_first: a killsTarget at hit 100 beats any chip, both between units
-- (B acts before A, who is earlier in slot order) and within one unit's options.
do
    local A = blue(0x01, 0, 0, 0)
    local Bu = blue(0x02, 1, 6, 0)
    local E1 = red(0x81, 1, 0, { hp = 30 })
    local E2 = red(0x82, 7, 0, { hp = 4 })
    local E3 = red(0x83, 6, 1, { hp = 30 })
    local board = boardOf(A, Bu, E1, E2, E3)
    local sight = sightOf {
        reach = { [0x01] = tiles({ 0, 0 }), [0x02] = tiles({ 6, 0 }) },
        fc = {
            [0x01] = { [0x81] = { ["0,0"] = fc { hit = 95, dmg = 14, hits = 2 } } },
            [0x02] = { [0x82] = { ["6,0"] = fc { hit = 100, dmg = 4, hits = 1,
                                                 killsTarget = true } },
                       [0x83] = { ["6,0"] = fc { hit = 95, dmg = 15, hits = 2 } } },
        },
    }
    for _, aggr in ipairs({ "careful", "even", "bold" }) do
        local a = B.decide(board, sight, style(aggr))
        check(a and a.unit, 0x02, aggr .. ": the unit with the sure kill acts first")
        check(a and a.target, 0x82, aggr .. ": the sure kill beats a bigger chip")
    end
    -- a kill that may miss is not sure: slot order again, and the bigger expected damage
    sight = sightOf {
        reach = { [0x01] = tiles({ 0, 0 }), [0x02] = tiles({ 6, 0 }) },
        fc = {
            [0x01] = { [0x81] = { ["0,0"] = fc { hit = 95, dmg = 14, hits = 2 } } },
            [0x02] = { [0x82] = { ["6,0"] = fc { hit = 80, dmg = 4, hits = 1,
                                                 killsTarget = true } } },
        },
    }
    check(B.decide(board, sight, style("careful")).unit, 0x01, "an 80% kill is not a sure kill")
end

-- test_never_attacks_when_the_counter_kills: a counter whose worst case reaches the unit's HP
-- refuses the attack in every style but greedy, which never reads one.
do
    local A = blue(0x01, 0, 0, 0)
    local E1 = red(0x81, 1, 0, { hp = 30 })
    local board = boardOf(A, E1)
    local sight = sightOf {
        reach = { [0x01] = tiles({ 0, 0 }, { 0, 1 }) },
        fc = { [0x01] = { [0x81] = {
            ["0,0"] = fc { hit = 90, dmg = 10, hits = 1, counters = true, counterHit = 50,
                           counterDmg = 20, counterHits = 1 } } } },
    }
    for _, aggr in ipairs({ "careful", "even", "bold" }) do
        check(B.decide(board, sight, style(aggr)).act, "wait", aggr .. ": a lethal counter refuses")
    end
    local fresh = sightOf {
        reach = { [0x01] = tiles({ 0, 0 }, { 0, 1 }) },
        fc = { [0x01] = { [0x81] = {
            ["0,0"] = fc { hit = 90, dmg = 10, hits = 1, counters = true, counterHit = 50,
                           counterDmg = 20, counterHits = 1 } } } },
    }
    -- A SURE kill on the first blow draws no counter (the attacker strikes first), however lethal
    -- the counter would be: every style takes it.
    local weak = red(0x81, 1, 0, { hp = 8 })
    local sure = sightOf {
        reach = { [0x01] = tiles({ 0, 0 }, { 0, 1 }) },
        fc = { [0x01] = { [0x81] = {
            ["0,0"] = fc { hit = 100, dmg = 10, hits = 1, killsTarget = true, counters = true,
                           counterHit = 50, counterCrit = 30, counterDmg = 20,
                           counterHits = 1 } } } },
    }
    for _, aggr in ipairs({ "careful", "even", "bold" }) do
        check(B.decide(boardOf(A, weak), sure, style(aggr)).act, "attack",
            aggr .. ": a sure first-blow kill is never refused for its counter")
    end
    local g = B.decide(board, fresh, style("greedy"))
    check(g.act, "attack", "greedy attacks whatever the forecast says")
    check(fresh.calls(), 0, "greedy reads no forecast")
end

-- test_objective_seize: the lord with the seize tile in reach and danger 0 there seizes,
-- ahead of a sure kill; a unit that is not the lord never does.
do
    local L = blue(0x01, 0, 2, 2, { charId = 0x0F })
    local O = blue(0x02, 1, 4, 3)
    local E1 = red(0x81, 9, 9, { hp = 3 })
    local Bo = red(0x82, 4, 5, { hp = 3 })
    local board = boardOf(L, O, E1, Bo)
    local sight = sightOf {
        objective = { kind = "seize", tile = { x = 4, y = 4 }, lord = 0x0F },
        reach = { [0x01] = tiles({ 2, 2 }, { 3, 3 }, { 4, 4 }),
                  [0x02] = tiles({ 4, 3 }, { 4, 4 }) },
        fc = { [0x02] = { [0x82] = { ["4,4"] = fc { hit = 100, dmg = 9, hits = 1,
                                                    killsTarget = true } } } },
    }
    for _, aggr in ipairs({ "careful", "even", "bold", "greedy" }) do
        local a = B.decide(board, sight, style(aggr))
        check(a and a.act, "seize", aggr .. ": the lord seizes")
        check(a and a.unit, 0x0F, aggr .. ": it is the lord who seizes")
        check(at(a), "4,4", aggr .. ": on the seize tile")
    end
    -- the lord has acted; the other unit's only kill is from the throne. It does not seize,
    -- and it does not end on the throne either -- not to attack, not to wait.
    local Ld = blue(0x01, 0, 2, 2, { charId = 0x0F, acted = true })
    sight = sightOf {
        objective = { kind = "seize", tile = { x = 4, y = 4 }, lord = 0x0F },
        reach = { [0x02] = tiles({ 4, 4 }, { 4, 3 }, { 4, 1 }) },
        fc = { [0x02] = { [0x82] = { ["4,4"] = fc { hit = 100, dmg = 9, hits = 1,
                                                    killsTarget = true } } } },
    }
    for _, aggr in ipairs({ "careful", "bold", "greedy" }) do
        local a = B.decide(boardOf(Ld, O, E1, Bo), sight, style(aggr))
        check(a.act ~= "seize", true, aggr .. ": a non-lord does not seize")
        check(at(a), "4,1", aggr .. ": a non-lord ends off the throne and out of its approach")
    end
    -- the seize tile in reach and in lethal danger: the lord still seizes (no enemy phase follows)
    sight = sightOf {
        objective = { kind = "seize", tile = { x = 4, y = 4 }, lord = 0x0F },
        danger = { ["4,4"] = 3 },
        reach = { [0x01] = tiles({ 2, 2 }, { 4, 4 }), [0x82] = tiles({ 4, 5 }) },
        fc = { [0x01] = { [0x82] = { ["4,4"] = fc { takenHit = 90, takenDmg = 30, takenHits = 2,
                                                    takenCrit = 10 } } } },
    }
    local a = B.decide(board, sight, style("careful"))
    check(a.act, "seize", "careful seizes even where the worst case is lethal")
    -- Who may Seize is the game's answer (CanUnitSeize): when it allows nobody here, nobody
    -- tries, and the unit within reach of the throne keeps off its approach.
    sight = sightOf {
        objective = { kind = "seize", tile = { x = 4, y = 4 } },
        reach = { [0x01] = tiles({ 2, 2 }), [0x02] = tiles({ 4, 3 }, { 4, 4 }, { 4, 1 }) },
    }
    sight.canSeize = function() return false end
    a = B.decide(boardOf(Ld, O, E1, Bo), sight, style("careful"))
    check(a.act ~= "seize" and at(a), "4,1", "the game allows no Seize: off the throne's approach")
end

-- A unit that cannot Seize strikes from the throne's approach only at a target ON the throne.
do
    local Ld = blue(0x01, 0, 0, 0, { charId = 0x0F, acted = true })
    local O = blue(0x02, 1, 5, 1)
    local seizeAt = { kind = "seize", tile = { x = 4, y = 4 }, lord = 0x0F }
    -- (a) X at (5,3) is reachable from (4,3), beside the throne, and from (6,3): (6,3) it is
    local X = red(0x81, 5, 3, { hp = 30 })
    local chip = fc { hit = 80, dmg = 5, hits = 1 }
    local sight = sightOf {
        objective = seizeAt,
        reach = { [0x02] = tiles({ 4, 3 }, { 6, 3 }) },
        fc = { [0x02] = { [0x81] = { ["4,3"] = chip, ["6,3"] = chip } } },
    }
    for _, aggr in ipairs({ "careful", "greedy" }) do
        local a = B.decide(boardOf(Ld, O, X), sight, style(aggr))
        check(a.act, "attack", aggr .. ": (a) attacks X")
        check(at(a), "6,3", aggr .. ": (a) from the tile out of the throne's approach")
    end
    -- (b) the boss ON the throne: struck from its approach
    local Bo = red(0x82, 4, 4, { hp = 30, isBoss = true })
    sight = sightOf {
        objective = seizeAt,
        reach = { [0x02] = tiles({ 4, 3 }, { 5, 1 }) },
        fc = { [0x02] = { [0x82] = { ["4,3"] = chip } } },
    }
    for _, aggr in ipairs({ "careful", "greedy" }) do
        local a = B.decide(boardOf(Ld, O, Bo), sight, style(aggr))
        check(a.act, "attack", aggr .. ": (b) attacks the boss on the throne")
        check(at(a), "4,3", aggr .. ": (b) from the approach")
    end
end

-- The most threatened unit acts before the rest; with no threat, slot order.
do
    local A = blue(0x01, 0, 0, 0)
    local Bu = blue(0x02, 1, 5, 5)
    local E = red(0x81, 9, 5)
    local board = boardOf(A, Bu, E)
    local sight = sightOf {
        danger = { ["5,5"] = 2 },
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x02] = tiles({ 5, 5 }, { 4, 5 }),
                  [0x81] = tiles({ 6, 5 }) },
        fc = { [0x02] = { [0x81] = { ["5,5"] = fc { takenHit = 60, takenDmg = 15,
                                                    takenHits = 2 } } } },
    }
    local a = B.decide(board, sight, style("careful"))
    check(a.unit, 0x02, "the threatened unit acts first")
    check(at(a), "4,5", "and steps out of reach")
    check(B.decide(boardOf(A, Bu, E), sightOf {}, style("careful")).unit, 0x01,
        "no threat anywhere: slot order")
end

-- Threat is the worst case, not the head count: one lethal enemy outranks two that chip.
do
    local A = blue(0x01, 0, 0, 0, { hp = 20 })
    local Bu = blue(0x02, 1, 9, 9, { hp = 20 })
    local C1, C2 = red(0x81, 0, 2), red(0x82, 2, 0)
    local L1 = red(0x83, 9, 7)
    local sight = sightOf {
        danger = { ["0,0"] = 2, ["9,9"] = 1 },
        reach = { [0x81] = tiles({ 0, 1 }), [0x82] = tiles({ 1, 0 }), [0x83] = tiles({ 9, 8 }) },
        fc = {
            [0x01] = { [0x81] = { ["0,0"] = fc { takenHit = 50, takenDmg = 3, takenHits = 1 } },
                       [0x82] = { ["0,0"] = fc { takenHit = 50, takenDmg = 3, takenHits = 1 } } },
            [0x02] = { [0x83] = { ["9,9"] = fc { takenHit = 80, takenDmg = 12, takenHits = 2 } } },
        },
    }
    check(B.decide(boardOf(A, Bu, C1, C2, L1), sight, style("careful")).unit, 0x02,
        "the unit facing one lethal enemy acts before the one facing two chips")
end

-- sight.field routes the march around a wall; without it the march is Manhattan.
do
    local P = dofile(here .. "pathing.lua")
    -- a wall at x = 2 for y = 0..1; the way past it is y = 2
    local wall = { ["2,0"] = true, ["2,1"] = true }
    local function passable(x, y) return not wall[x .. "," .. y] end
    local A = blue(0x01, 0, 0, 1)
    local E = red(0x81, 4, 1)
    local reach = { [0x01] = tiles({ 1, 0 }, { 1, 2 }) }  -- both 4 from E by Manhattan
    local asked
    local withField = sightOf { reach = reach, field = function(goal)
        asked = goal; return P.distanceField(6, 4, passable, goal) end }
    local a = B.decide(boardOf(A, E), withField, style("careful"))
    check(at(a), "1,2", "the field's march takes the way around the wall")
    check(asked and asked.x == 4 and asked.y == 1, true, "the field is asked for the bot's goal")
    check(at(B.decide(boardOf(A, E), sightOf { reach = reach }, style("careful"))), "1,0",
        "no field: Manhattan (first of the tied tiles)")
    check(at(B.decide(boardOf(A, E), withField, style("greedy"))), "1,2",
        "greedy marches over the field too")
end

-- sight.cache keeps attacks and strikes across decide calls. An attack is keyed on what the
-- simulation reads (the fighters, their tiles, units within support range); a strike on the
-- whole board, since the enemy AI's pick can change with any unit anywhere.
do
    local A = blue(0x01, 0, 0, 0)
    local Bu = blue(0x02, 1, 5, 0)
    local E = red(0x81, 1, 0, { hp = 30 })
    local o = {
        cache = {},
        danger = { ["0,0"] = 1, ["5,0"] = 0 },
        reach = { [0x01] = tiles({ 0, 0 }), [0x02] = tiles({ 5, 0 }), [0x81] = tiles({ 1, 0 }) },
        fc = { [0x01] = { [0x81] = { ["0,0"] = fc { hit = 80, dmg = 5, hits = 1 } } } },
    }
    local sight = sightOf(o)
    local function counts() return sight.attacks() .. "/" .. sight.strikes() end
    B.decide(boardOf(A, Bu, E), sight, style("careful"))
    check(counts(), "1/1", "one attack and one strike for the one pair and tile")
    B.decide(boardOf(A, Bu, E), sight, style("careful"))
    check(counts(), "1/1", "the second call reads both from the cache")
    local hurt = red(0x81, 1, 0, { hp = 25 })
    B.decide(boardOf(A, Bu, hurt), sight, style("careful"))
    check(counts(), "2/2", "a changed HP is a new attack and a new strike")
    local far = blue(0x02, 1, 6, 0)
    B.decide(boardOf(A, far, hurt), sight, style("careful"))
    check(counts(), "2/3",
        "an ally moving out of support range: the attack stands, the strike does not")
    local moved = blue(0x02, 1, 0, 2)
    B.decide(boardOf(A, moved, hurt), sight, style("careful"))
    check(counts(), "3/4", "an ally moving into support range: both asked again")
    -- a level-up mid-phase changes the unit's stats: a new attack
    local leveled = blue(0x01, 0, 0, 0)
    A.level, leveled.level = 1, 2
    B.decide(boardOf(A, moved, hurt), sight, style("careful"))
    local was = sight.attacks()
    B.decide(boardOf(leveled, moved, hurt), sight, style("careful"))
    check(sight.attacks(), was + 1, "a level-up is a new attack")
    local spent = blue(0x01, 0, 0, 0)
    A.items, spent.items = { { id = 1, uses = 40 } }, { { id = 1, uses = 39 } }
    B.decide(boardOf(A, moved, hurt), sight, style("careful"))
    local before = sight.attacks()
    B.decide(boardOf(spent, moved, hurt), sight, style("careful"))
    check(sight.attacks(), before + 1, "a spent weapon use is a new attack")
    local bare = sightOf { danger = o.danger, reach = o.reach, fc = o.fc }
    B.decide(boardOf(A, Bu, E), bare, style("careful"))
    B.decide(boardOf(A, Bu, E), bare, style("careful"))
    check(bare.attacks(), 2, "without a cache each call asks for itself")
end

-- Every unit has acted (or is off the field): nil, the phase is over.
do
    local board = boardOf(blue(0x01, 0, 0, 0, { acted = true }),
                          blue(0x02, 1, 1, 0, { onField = false }), red(0x81, 5, 5))
    check(B.decide(board, sightOf {}, style("careful")), nil, "nobody left to act -> nil")
end

-- A unit never ends on a tile another unit stands on, even when sight's reach lists it.
do
    local A = blue(0x01, 0, 0, 0)
    local Bu = blue(0x02, 1, 1, 0, { acted = true })
    local E = red(0x81, 2, 1)
    local sight = sightOf { reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) } }
    local a = B.decide(boardOf(A, Bu, E), sight, style("bold"))
    check(at(a), "0,0", "the ally's tile is not an end tile")
end

-- greedy through decide: the same pick pickTarget makes (boss first), from the same tile.
do
    local A = blue(0x01, 0, 3, 3)
    local E1 = red(0x81, 3, 5, { hp = 10 })
    local E2 = red(0x82, 6, 7, { hp = 40, isBoss = true })
    local sight = sightOf { reach = { [0x01] = tiles({ 3, 3 }, { 3, 4 }, { 6, 6 }) } }
    local a = B.decide(boardOf(A, E1, E2), sight, style("greedy"))
    check(a.act, "attack", "greedy decide attacks")
    check(a.target, 0x82, "greedy decide: boss first, as pickTarget")
    check(at(a), "6,6", "greedy decide: from pickTarget's tile")
    local ok = pcall(B.decide, boardOf(A, E1), sight, style("reckless"))
    check(ok, false, "an unknown aggression is an error, not a silent default")
end

-- survive: nothing to march to, so the unit holds -- on its own tile while that is allowed,
-- else on the tile where the worst case is smallest.
do
    local A = blue(0x01, 0, 2, 2, { hp = 20 })
    local E = red(0x81, 9, 2)
    local function sightWith(danger)
        return sightOf {
            objective = { kind = "survive", turnsLeft = 3 },
            danger = danger,
            reach = { [0x01] = tiles({ 1, 2 }, { 2, 2 }, { 3, 2 }), [0x81] = tiles({ 4, 2 }) },
            fc = { [0x01] = { [0x81] = {
                ["3,2"] = fc { takenHit = 60, takenDmg = 10, takenHits = 2 },
                ["2,2"] = fc { takenHit = 60, takenDmg = 10, takenHits = 2 } } } },
        }
    end
    E.maxRange = 2
    check(at(B.decide(boardOf(A, E), sightWith({}), style("careful"))), "2,2",
        "survive, own tile safe: holds")
    check(at(B.decide(boardOf(A, E), sightWith({ ["2,2"] = 1, ["3,2"] = 1 }), style("careful"))),
        "1,2", "survive, own tile in reach: steps to the safest tile")
end

-- ── claims: what a Strategy claim makes the bot do (#510 step 9 C3) ──────────────
-- Claims arrive RESOLVED by the runner: unit = {charIds}, vs = {classIds} | "boss" | "all",
-- tile = a terrain id, turns = {arrival turns}. Each test goes through decide and shows the
-- claim changes the pick against the same board without it.

local function csv(list) return table.concat(list, ",") end
local CLS_A, CLS_B = 0x10, 0x20   -- two enemy classes; ids only, no class is named here
local function claimed(aggression, ...)
    return B.applyClaims({ ... }, style(aggression))
end

-- test_carry_deploys_and_attacks_the_named_class: A and C can both hit E; with no claim A
-- acts (slot order, nobody threatened). Carry C vs E's class: C is deployed and acts on E.
do
    local A = blue(0x01, 0, 0, 0)
    local C = blue(0x02, 1, 4, 0)
    local E = red(0x81, 2, 0, { hp = 30, classId = CLS_A })
    local sight = sightOf {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x02] = tiles({ 4, 0 }, { 3, 0 }) },
        fc = { [0x01] = { [0x81] = { ["1,0"] = fc { hit = 80, dmg = 5, hits = 1 } } },
               [0x02] = { [0x81] = { ["3,0"] = fc { hit = 80, dmg = 5, hits = 1 } } } },
    }
    local board = boardOf(A, C, E)
    check(B.decide(board, sight, style("careful")).unit, 0x01, "no claim: A acts first")
    local base = style("careful")
    base.deploy = { 0x02 }
    local carry = { id = "c1", kind = "carry", unit = { 0x02, 0x03 }, vs = { CLS_A } }
    local st = B.CLAIM_BEHAVIOURS.carry(carry, base)
    check(csv(st.deploy), "2,3", "carry: its units lead deploy, a repeat once")
    check(csv(base.deploy), "2", "carry: the style it was given is not edited")
    local a = B.decide(board, sight, st)
    check(a and a.unit, 0x02, "carry: C acts first on the named class")
    check(a and a.target, 0x81, "carry: C's target is E")
    check(at(a), "3,0", "carry: from C's strike tile")
    -- a carry against another class leaves the pick alone
    local other = B.CLAIM_BEHAVIOURS.carry({ id = "c2", kind = "carry", unit = { 0x02 },
                                             vs = { CLS_B } }, style("careful"))
    check(B.decide(board, sight, other).unit, 0x01, "carry vs another class: A acts")
end

-- test_answer_targets_the_named_class_first: A out-damages on E2, so with no claim it hits
-- E2; answering E1's class it hits E1.
do
    local A = blue(0x01, 0, 0, 0)
    local E1 = red(0x81, 1, 0, { hp = 30, classId = CLS_A })
    local E2 = red(0x82, 0, 1, { hp = 30, classId = CLS_B })
    local sight = sightOf {
        fc = { [0x01] = { [0x81] = { ["0,0"] = fc { hit = 80, dmg = 3, hits = 1 } },
                          [0x82] = { ["0,0"] = fc { hit = 80, dmg = 10, hits = 1 } } } },
    }
    local board = boardOf(A, E1, E2)
    check(B.decide(board, sight, style("careful")).target, 0x82, "no claim: the bigger hit")
    local st = claimed("careful", { id = "a1", kind = "answer", unit = { 0x01 }, vs = { CLS_A } })
    check(B.decide(board, sight, st).target, 0x81, "answer: the named class first")
    st = claimed("careful", { id = "a2", kind = "answer", unit = { 0x05 }, vs = { CLS_A } })
    check(B.decide(board, sight, st).target, 0x82, "answer for another unit: unchanged")
    -- "boss" and "all" resolve against the board, not a class
    E1.isBoss = true
    st = claimed("careful", { id = "a3", kind = "answer", unit = { 0x01 }, vs = "boss" })
    check(B.decide(board, sight, st).target, 0x81, "answer vs boss: the boss first")
end

-- test_wall_ends_on_the_approach_and_others_hold_behind: on survive W would hold on its own
-- tile; walling E's class it steps to the tile E reaches, when careful allows it there.
do
    local W = blue(0x01, 0, 0, 0, { hp = 20 })
    local O = blue(0x02, 1, 0, 2)
    local E = red(0x81, 6, 0, { classId = CLS_A })
    local function sightWith(taken, objective)
        return sightOf {
            objective = objective,
            danger = { ["3,0"] = 1 },
            reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }, { 2, 0 }, { 3, 0 }),
                      [0x02] = tiles({ 0, 2 }, { 2, 2 }, { 6, 2 }),
                      [0x81] = tiles({ 6, 0 }, { 5, 0 }, { 4, 0 }) },
            fc = { [0x01] = { [0x81] = { ["3,0"] = fc { takenHit = 70, takenDmg = taken,
                                                         takenHits = 1 } } } },
        }
    end
    local survive = { kind = "survive", turnsLeft = 3 }
    local board = boardOf(W, O, E)
    local wall = { id = "w1", kind = "wall", unit = { 0x01 }, vs = { CLS_A } }
    local st = claimed("careful", wall)
    check(at(B.decide(board, sightWith(5, survive), style("careful"))), "0,0",
        "no claim: W holds on survive")
    local a = B.decide(board, sightWith(5, survive), st)
    check(a and a.unit, 0x01, "wall: the wall acts first")
    check(at(a), "3,0", "wall: ends on the tile E reaches")
    check(at(B.decide(board, sightWith(25, survive), st)), "0,0",
        "wall: no safe approach -> the normal pick (a wall that dies is not a wall)")
    -- O, after the wall stood at (3,0): on rout it would march to (6,2), nearer E than W
    local moved = boardOf(blue(0x01, 0, 3, 0, { acted = true }), O, E)
    local rout = { kind = "rout" }
    check(at(B.decide(moved, sightWith(5, rout), style("careful"))), "6,2",
        "no claim: O marches past the wall's line")
    check(at(B.decide(moved, sightWith(5, rout), st)), "2,2",
        "wall: O holds behind it")
    -- a wall that can strike the walled enemy does, ahead of the slot order
    local first = blue(0x02, 0, 0, 5)
    local W2 = blue(0x01, 1, 5, 4)
    local E2 = red(0x81, 5, 5, { classId = CLS_A })
    local strike = sightOf {
        reach = { [0x02] = tiles({ 0, 5 }, { 4, 5 }), [0x01] = tiles({ 5, 4 }) },
        fc = { [0x02] = { [0x81] = { ["4,5"] = fc { hit = 80, dmg = 5, hits = 1 } } },
               [0x01] = { [0x81] = { ["5,4"] = fc { hit = 80, dmg = 5, hits = 1 } } } },
    }
    check(B.decide(boardOf(first, W2, E2), strike, style("careful")).unit, 0x02,
        "no claim: slot order strikes")
    local a2 = B.decide(boardOf(first, W2, E2), strike, st)
    check(a2 and a2.unit == 0x01 and a2.act == "attack", true, "wall: strikes the walled enemy")
end

-- test_terrain_prefers_the_named_tile: the boss reaches both (1,0) and (2,0); a march to
-- (2,0) holds on (1,0), the named terrain, against it.
do
    local A = blue(0x01, 0, 0, 0)
    local E = red(0x81, 9, 0, { isBoss = true, maxRange = 2 })
    local FORT = 0x1E
    local function sightWith(terrain, bossReach)
        return sightOf { reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }, { 2, 0 }),
                                   [0x81] = bossReach or tiles({ 9, 0 }, { 3, 0 }) },
                         terrain = terrain }
    end
    local map = function(x, y) return (x == 1 and y == 0) and FORT or 1 end
    local board = boardOf(A, E)
    check(at(B.decide(board, sightWith(map), style("careful"))), "2,0", "no claim: marches on")
    local st = claimed("careful", { id = "t1", kind = "terrain", tile = FORT, vs = "boss" })
    check(at(B.decide(board, sightWith(map), st)), "1,0", "terrain: ends on the named tile")
    check(at(B.decide(board, sightWith(nil), st)), "2,0",
        "terrain without sight.terrain: a no-op")
    check(at(B.decide(board, sightWith(map, tiles({ 9, 0 })), st)), "2,0",
        "terrain: a fort out of every named enemy's reach holds nothing, the march goes on")
    st = claimed("careful", { id = "t2", kind = "terrain", tile = FORT, vs = { CLS_B } })
    check(at(B.decide(board, sightWith(map), st)), "2,0",
        "terrain vs a class not on the map: a no-op")
end

-- test_reinforcements_hold_the_turn_before: arrival on turn 3 holds the march on turn 2. The
-- turn is the board's (Board.read's), the one source for it.
do
    local A = blue(0x01, 0, 0, 0)
    local E = red(0x81, 9, 0)
    local sight = sightOf { reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }, { 2, 0 }) } }
    local function boardAt(turn)
        local b = boardOf(A, E)
        b.turn = turn
        return b
    end
    local st = claimed("careful", { id = "r1", kind = "reinforcements", turns = { 3, 7 } })
    check(at(B.decide(boardAt(2), sight, style("careful"))), "2,0", "no claim: marches")
    check(at(B.decide(boardAt(2), sight, st)), "0,0", "reinforcements: holds the turn before")
    check(at(B.decide(boardAt(6), sight, st)), "0,0", "reinforcements: before each arrival")
    check(at(B.decide(boardAt(3), sight, st)), "2,0", "reinforcements: marches on arrival")
    local ok, err = pcall(B.decide, boardAt(nil), sight, st)
    check(ok, false, "reinforcements without board.turn raise")
    check(tostring(err):find("a reinforcements claim needs board.turn", 1, true) ~= nil, true,
        "the error says what is missing")
end

-- test_unmodelled_is_reported_not_dropped: every claim with no behaviour comes back by id.
do
    local claims = {
        { id = "k1", kind = "carry", unit = { 0x01 }, vs = "all" },
        { id = "k2", kind = "threat", vs = { CLS_A } },
        { id = "k3", kind = "kits", topic = "villages" },
        { id = "k4", kind = "unmodelled", topic = "healing", step = "out" },
        { id = "k5", kind = "mystery" },
    }
    check(csv(B.unplayed(claims)), "k2,k3,k4,k5", "unplayed: threat, kits, unmodelled, unknown")
    check(B.CLAIM_BEHAVIOURS.threat, nil, "threat has no behaviour")
end

-- A claim missing what its behaviour needs raises, naming the claim; it is never skipped.
do
    local bad = {
        { id = "m1", kind = "carry", vs = { CLS_A } },
        { id = "m2", kind = "answer", unit = { 0x01 } },
        { id = "m3", kind = "wall", unit = {}, vs = "boss" },
        { id = "m4", kind = "terrain", vs = "all" },
        { id = "m5", kind = "reinforcements" },
        { id = "m6", kind = "answer", unit = { 0x01 }, vs = "fighter" },
        { id = "m7", kind = "carry", unit = { "some-name" }, vs = { CLS_A } },
        { id = "m8", kind = "wall", unit = { 0x01 }, vs = { "fighter" } },
        { id = "m9", kind = "reinforcements", turns = { "3" } },
        { id = "m10", kind = "terrain", tile = "fort", vs = "all" },
    }
    for _, c in ipairs(bad) do
        local ok, err = pcall(B.CLAIM_BEHAVIOURS[c.kind], c, style("careful"))
        check(ok, false, c.id .. ": a malformed claim raises")
        check(tostring(err):find(c.id, 1, true) ~= nil, true, c.id .. ": the error names it")
    end
end

-- A claim with no string id or kind raises before dispatch: it could be neither played nor
-- reported.
do
    for _, c in ipairs({ { kind = "carry", unit = { 1 }, vs = "all" }, { id = "n2" },
                         { id = 7, kind = "kits" } }) do
        local ok, err = pcall(B.applyClaims, { c }, style("careful"))
        check(ok, false, "applyClaims: a claim without a string id and kind raises")
        check(tostring(err):find("needs a string id and kind", 1, true) ~= nil, true,
            "applyClaims: the error says so")
        check(pcall(B.unplayed, { c }), false, "unplayed: the same claim raises")
    end
end

-- test_answer_beats_a_sure_kill: A has a sure kill on E2, and a chip on E1; answering E1's
-- class it takes the chip.
do
    local A = blue(0x01, 0, 0, 0)
    local E1 = red(0x81, 1, 0, { hp = 30, classId = CLS_A })
    local E2 = red(0x82, 0, 1, { hp = 4, classId = CLS_B })
    local sight = sightOf {
        fc = { [0x01] = { [0x81] = { ["0,0"] = fc { hit = 80, dmg = 3, hits = 1 } },
                          [0x82] = { ["0,0"] = fc { hit = 100, dmg = 9, hits = 1,
                                                    killsTarget = true } } } },
    }
    local board = boardOf(A, E1, E2)
    check(B.decide(board, sight, style("careful")).target, 0x82, "no claim: the sure kill")
    local st = claimed("careful", { id = "a4", kind = "answer", unit = { 0x01 }, vs = { CLS_A } })
    check(B.decide(board, sight, st).target, 0x81, "answer: the named class above a sure kill")
end

-- Greedy ignores claims in decide: the clear-bot's pick, claim or no claim.
do
    local A = blue(0x01, 0, 0, 0)
    local E1 = red(0x81, 1, 0, { hp = 30, classId = CLS_A })
    local E2 = red(0x82, 0, 1, { hp = 5, classId = CLS_B })
    local board = boardOf(A, E1, E2)
    local st = claimed("greedy", { id = "g1", kind = "answer", unit = { 0x01 }, vs = { CLS_A } })
    check(B.decide(board, sightOf {}, st).target, 0x82, "greedy: lowest HP, the claim ignored")
end

-- ── between chapters: prep, shop, promote, route ────────────────────────────────

local function unitOf(id, charId, level, extra)
    local u = { id = id, charId = charId, level = level, canUse = {}, items = {} }
    for k, v in pairs(extra or {}) do u[k] = v end
    return u
end

-- test_carry_survives_a_full_deploy: the sampled deploy fills the cap; the carried unit is
-- still fielded, because carry puts it first.
local function test_carry_survives_a_full_deploy()
    local roster = { unitOf(1, 0x01, 9), unitOf(2, 0x02, 1), unitOf(3, 0x03, 8) }
    local sampled = style("careful")
    sampled.deploy = { 0x01, 0x03 }
    local st = B.CLAIM_BEHAVIOURS.carry({ id = "c3", kind = "carry", unit = { 0x02 },
                                          vs = "all" }, sampled)
    check(csv(st.deploy), "2,1,3", "carry: carried first, then the sampled list")
    for _, u in ipairs(roster) do u.group = "magic" end
    check(csv(B.team({ roster = roster, cap = 2, maxima = {}, demands = {}, answers = {},
                       carried = {}, style = st }).deploy), "2,1",
        "team: a full claim list keeps the carry")
end
test_carry_survives_a_full_deploy()

-- Bot.team: forced, then a followed claim's units, then the demands, then fill. g = the group.
local function teamUnit(id, charId, group, extra)
    return unitOf(id, charId, 1, (function()
        local e = { group = group }
        for k, v in pairs(extra or {}) do e[k] = v end
        return e
    end)())
end
local function team(t)
    t.maxima = t.maxima or {}
    t.demands = t.demands or {}
    t.answers = t.answers or {}
    t.carried = t.carried or {}
    t.style = t.style or { deploy = {} }
    return B.team(t)
end

local function test_team_forced_past_the_ceiling_claims_under_it()
    local roster = { teamUnit(1, 0x01, "armour", { forced = true }), teamUnit(2, 0x02, "armour"),
                     teamUnit(3, 0x03, "armour", { forced = true }), teamUnit(4, 0x04, "magic") }
    local p = team({ roster = roster, cap = 4, maxima = { armour = 1 },
                     style = { deploy = { 0x02, 0x04 } } })
    check(csv(p.deploy), "1,3,4", "forced both (past armour 1); claim's armour 2 capped; magic in")
    check(p.reasons[0x01].why, "forced", "reason: forced")
    check(p.reasons[0x04].why, "claim", "reason: a followed claim")
    check(#p.give, 0, "no transfer rule decided: give is empty")
end
test_team_forced_past_the_ceiling_claims_under_it()

local function test_team_covers_the_most_demand_first()
    local roster = { teamUnit(1, 0x01, "magic"), teamUnit(2, 0x02, "thief"),
                     teamUnit(3, 0x03, "healer") }
    local demands = { { id = "chests", need = 1 }, { id = "fog", need = 1 },
                      { id = "sustain", need = 1 } }
    local answers = { [0x01] = { fog = true }, [0x02] = { chests = true, fog = true },
                      [0x03] = { sustain = true } }
    local p = team({ roster = roster, cap = 2, demands = demands, answers = answers })
    check(csv(p.deploy), "2,3", "thief covers two, then the healer covers what is left")
    check(table.concat(p.reasons[0x02].demands, ","), "chests,fog", "reason names the demands")
end
test_team_covers_the_most_demand_first()

local function test_team_ties_carried_then_earlier_joiner()
    local roster = { teamUnit(1, 0x01, "magic"), teamUnit(2, 0x02, "magic"),
                     teamUnit(3, 0x03, "magic") }
    local demands = { { id = "sustain", need = 1 } }
    local answers = { [0x01] = { sustain = true }, [0x02] = { sustain = true }, [0x03] = { sustain = true } }
    local p = team({ roster = roster, cap = 1, demands = demands, answers = answers,
                     carried = { [0x03] = true } })
    check(csv(p.deploy), "3", "equal cover: the carried unit")
    check(p.reasons[0x03].carried, true, "reason says it won as carried")
    p = team({ roster = roster, cap = 1, demands = demands, answers = answers })
    check(csv(p.deploy), "1", "equal cover, none carried: the earlier joiner (slot order)")
end
test_team_ties_carried_then_earlier_joiner()

local function test_team_carried_never_beats_an_uncovered_demand()
    local roster = { teamUnit(1, 0x01, "magic"), teamUnit(2, 0x02, "thief") }
    local p = team({ roster = roster, cap = 1, demands = { { id = "chests", need = 1 } },
                     answers = { [0x02] = { chests = true } }, carried = { [0x01] = true } })
    check(csv(p.deploy), "2", "a carried unit covering nothing loses to the chest opener")
end
test_team_carried_never_beats_an_uncovered_demand()

local function test_team_a_full_group_benches_the_later_joiner()
    local roster = { teamUnit(1, 0x01, "flier"), teamUnit(2, 0x02, "flier"),
                     teamUnit(3, 0x03, "flier") }
    local demands = { { id = "villages", need = 3 } }
    local answers = { [0x01] = { villages = true }, [0x02] = { villages = true },
                      [0x03] = { villages = true } }
    local p = team({ roster = roster, cap = 3, maxima = { flier = 2 }, demands = demands,
                     answers = answers })
    check(csv(p.deploy), "1,2", "flier 2: the third flier stays benched, its slot stays empty")
end
test_team_a_full_group_benches_the_later_joiner()

local function test_team_an_enemy_class_needs_an_answer_each()
    local roster = { teamUnit(1, 0x01, "axe"), teamUnit(2, 0x02, "axe"),
                     teamUnit(3, 0x03, "magic"), teamUnit(4, 0x04, "sword") }
    local demands = { { id = "enemy:9", need = 2 }, { id = "sustain", need = 1 } }
    local answers = { [0x01] = { ["enemy:9"] = true }, [0x02] = { ["enemy:9"] = true },
                      [0x04] = { ["enemy:9"] = true } }
    local p = team({ roster = roster, cap = 2, demands = demands, answers = answers })
    check(csv(p.deploy), "1,2", "two enemies of the class: two answerers")
end
test_team_an_enemy_class_needs_an_answer_each()

local function test_team_fill_is_the_best_answer_to_the_biggest_class()
    local roster = { teamUnit(1, 0x01, "magic"), teamUnit(2, 0x02, "axe"),
                     teamUnit(3, 0x03, "sword"), teamUnit(4, 0x04, "sword") }
    local demands = { { id = "enemy:9", need = 1 }, { id = "enemy:7", need = 1 } }
    local answers = { [0x01] = { ["enemy:9"] = true }, [0x02] = { ["enemy:7"] = true },
                      [0x03] = { ["enemy:9"] = true }, [0x04] = { ["enemy:9"] = true } }
    local strength = { [0x03] = { ["enemy:9"] = 2 }, [0x04] = { ["enemy:9"] = 5 } }
    local p = team({ roster = roster, cap = 4, demands = demands, answers = answers,
                     strength = strength })
    check(csv(p.deploy), "1,2,4,3", "covered by the first answerers, then fill: highest strength first")
    check(p.reasons[0x04].why, "fill", "reason: fill")
end
test_team_fill_is_the_best_answer_to_the_biggest_class()

local function test_team_ungrouped_class_raises_and_absent_carried_is_ignored()
    local ok = pcall(team, { roster = { unitOf(1, 0x01, 1) }, cap = 1 })
    check(ok, false, "a unit with no group raises: there is no default group")
    local p = team({ roster = { teamUnit(1, 0x01, "magic") }, cap = 3,
                     carried = { [0x09] = true } })
    check(csv(p.deploy), "1", "a carried unit no longer on the roster (dead, departed) drops out")
end
test_team_ungrouped_class_raises_and_absent_carried_is_ignored()

local function test_shop_stops_at_gold()
    local stock = {
        { item = 0x6C, price = 300, kind = "vulnerary" },
        { item = 0x10, price = 500, type = "sword" },
        { item = 0x11, price = 400, type = "sword" },
        { item = 0x12, price = 900, type = "sword" },
        { item = 0x20, price = 700, type = "lance" },
        { item = 0x21, price = 100, type = "axe" },
    }
    -- canUse is the game's CanUnitUseWeapon: A can wield the two cheaper swords, not 0x12.
    local A = unitOf(1, 0x01, 1, { canUse = { [0x10] = true, [0x11] = true } })
    local Bu = unitOf(2, 0x02, 1, { canUse = { [0x20] = true } })
    local function flat(r)
        local t = {}
        for _, e in ipairs(r) do t[#t + 1] = e.unit .. ":" .. e.item end
        return csv(t)
    end
    check(flat(B.shop(10000, stock, { A, Bu })), "1:108,2:108,1:17,2:32",
        "vulneraries per unit first, then the cheapest usable weapon each lacks, each for its unit")
    check(flat(B.shop(700, stock, { A, Bu })), "1:108,2:108",
        "gold runs out after the vulneraries: 100 left buys no 400+ sword")
    local Cu0 = unitOf(3, 0x03, 1, { canUse = { [0x21] = true, [0x10] = true, [0x11] = true } })
    check(flat(B.shop(1000, stock, { Bu, Cu0 })), "2:108,3:108,3:33",
        "skip then continue: the lance (700) is skipped at 400 gold, "
            .. "the axe (100) after it is bought")
    A.items = { { id = 0x10, type = "sword", rank = 1 } }
    check(flat(B.shop(10000, stock, { A, Bu })), "1:108,2:108,2:32", "a unit holding its type buys none")
    local Cu = unitOf(3, 0x03, 1, { canUse = { [0x21] = true, [0x10] = true, [0x11] = true } })
    check(flat(B.shop(800, stock, { Cu })), "3:108,3:33,3:17",
        "skip-and-continue: exact fit, gold 800 buys vuln 300, axe 100, sword 400 in order")
    check(flat(B.shop(450, stock, { Cu })), "3:108,3:33",
        "the sword (400) is skipped at 50 gold, the buying stops there")
    A.items = { { id = 0x10, type = "sword", rank = 1 }, { id = 0x6C, kind = "vulnerary" } }
    check(flat(B.shop(10000, stock, { A, Bu })), "2:108,2:32",
        "a unit already holding a Vulnerary buys none")
    check(flat(B.shop(0, stock, { A })), "", "no gold, nothing")
    check(flat(B.shop(10000, { stock[2] }, { A })), "",
        "no Vulnerary in stock and sword held: nothing")
    local NoUse = unitOf(4, 0x04, 1, { canUse = {} })
    check(flat(B.shop(10000, { stock[4] }, { NoUse })), "",
        "a weapon the game says the unit cannot use is never bought")
end
test_shop_stops_at_gold()

local function test_promote_reads_the_games_answer()
    -- `promotes` is the game's own check (class and level): the bot adds no rule of its own.
    check(B.promote(unitOf(1, 1, 10), { { id = 0x82, promotes = true } }), true,
        "a seal the game accepts promotes")
    check(B.promote(unitOf(1, 1, 15), {}), false, "no seal, no promotion")
    check(B.promote(unitOf(1, 1, 15), { { id = 0x82, promotes = false } }), false,
        "a seal that does not promote this unit is not one")
    local o = B.promoteOrder({ unitOf(1, 0x01, 8), unitOf(2, 0x02, 12), unitOf(3, 0x03, 12),
                               unitOf(4, 0x04, 15) })
    local ids = {}
    for _, u in ipairs(o) do ids[#ids + 1] = u.id end
    check(csv(ids), "4,2,3,1", "promote order: highest level first, ties by slot")
end
test_promote_reads_the_games_answer()

local function test_route_follows_style()
    local opts = { "a", "b", "c" }
    check(B.route(opts, { route = 1 }), 1, "route 1")
    check(B.route(opts, { route = 2 }), 2, "route 2")
    check(pcall(B.route, opts, { route = 4 }), false, "out-of-range route raises")
    check(pcall(B.route, opts, {}), false, "missing route raises")
end
test_route_follows_style()

-- ── a full bag: which item goes to the convoy (Nicolas, 2026-10-28) ─────────────────────
do
    local function lance(rank, o)
        o = o or {}
        return { kind = "weapon", type = "lance", rank = rank, maxRange = o.maxRange or 1,
                 effective = o.effective, usable = o.usable ~= false }
    end
    local function heal(uses) return { kind = "heal", uses = uses or 3 } end
    local key, gem = { kind = "key" }, { kind = "money" }
    local bow = { kind = "weapon", type = "bow", rank = 1, maxRange = 2, usable = false }
    local F = B.fullBag
    -- money, healing and an unusable weapon go first, the new item kept
    check(F({ lance(1), heal(), key, gem, lance(2) }, lance(4)), 4, "bag: a gem leaves for a better lance")
    check(F({ lance(1), heal(), key, bow, lance(2) }, heal()), 0, "bag: a second heal is not needed")
    check(F({ lance(1), key, bow, lance(2), lance(3) }, heal()), 3, "bag: an unusable bow leaves for the first heal")
    check(F({ lance(1), heal(1), heal(3), key, lance(2) }, key), 2, "bag: the emptier spare heal leaves for a key")
    -- a weapon: a higher rank beats the lowest plain one of its type
    check(F({ lance(1), heal(), key, lance(2), lance(3) }, lance(4)), 1, "bag: Silver beats Iron")
    check(F({ lance(2), heal(), key, lance(2), lance(3) }, lance(2)), 0, "bag: an equal rank is a duplicate")
    -- a Javelin's range is not beaten by rank, and a Javelin is wanted for its range
    check(F({ lance(1, { maxRange = 2 }), heal(), key, lance(3), lance(3) }, lance(4)), 4,
          "bag: Silver replaces a Steel, the Javelin stays")
    check(F({ lance(1, { maxRange = 2 }), heal(), key, lance(3, { effective = "armour" }), heal() },
            lance(4)), 0, "bag: the only ranged lance is never the one replaced")
    check(F({ lance(1), heal(), key, gem, lance(3) }, lance(1, { maxRange = 2 })), 4,
          "bag: a lance that adds range is wanted")
    check(F({ lance(1), heal(), key, gem, lance(3) }, lance(2, { effective = "armour" })), 4,
          "bag: a lance that adds bonus damage is wanted")
    -- all five needed: the new item goes (Nicolas: three weapons, a Vulnerary and a key)
    check(F({ lance(1), lance(2), lance(3, { maxRange = 2 }), heal(), key }, lance(1)), 0,
          "bag: everything carried is needed")
    -- a weapon the unit cannot use, money, a seal: not needed in hand
    check(F({ lance(1), heal(), key, gem, lance(2) }, { kind = "weapon", type = "bow", rank = 4,
              usable = false }), 0, "bag: a bow for a lance user goes to the convoy")
    check(F({ lance(1), heal(), key, gem, lance(2) }, { kind = "money" }), 0, "bag: money goes")
    check(F({ lance(1), heal(), key, gem, lance(2) }, { kind = "other" }), 0, "bag: a seal goes")
    -- the convoy full: a discard takes duplicates and low tiers, never money
    check(F({ lance(1), heal(), key, gem, lance(2) }, lance(4), true), 1, "bag: discard the beaten lance")
    check(F({ heal(1), heal(), key, gem, lance(2) }, key, true), 1, "bag: discard a spare heal")
    check(F({ lance(1), heal(), key, gem, lance(2, { maxRange = 2 }) }, heal(), true), 0,
          "bag: no duplicate to discard, the new item goes")
end

-- ── PR E: breaching, doors, healing, Talk, keys, avoid, fog ────────────────────────────

-- A field per goal tile: fields["x,y"] = { "x,y" = dist }.
local function fieldsOf(fields)
    return function(g)
        local f = fields[g.x .. "," .. g.y]
        if not f then return nil end
        local out = {}
        for k, d in pairs(f) do
            local x, y = k:match("(%d+),(%d+)")
            x, y = tonumber(x), tonumber(y)
            out[y] = out[y] or {}
            out[y][x] = d
        end
        return out
    end
end
local BOSS_SIDE = { ["3,0"] = 1, ["4,0"] = 0 }
local FROM_WALL = { ["0,0"] = 2, ["1,0"] = 1, ["2,0"] = 0, ["3,0"] = 1, ["4,0"] = 2 }

-- test_breach_strikes_the_wall_that_cuts_off_the_goal: the boss's field never reaches A, the
-- wall at (2,0) sits beside it, so A strikes the wall from (1,0); without the wall it marches.
do
    local A = blue(0x01, 0, 0, 0)
    local E = red(0x81, 4, 0, { isBoss = true, minRange = false })
    local sight = sightOf {
        objective = { kind = "boss" }, reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        field = fieldsOf { ["4,0"] = BOSS_SIDE, ["2,0"] = FROM_WALL },
        obstacles = { { x = 2, y = 0, hp = 20 } },
    }
    local a = B.decide(boardOf(A, E), sight, style("careful"))
    check(a and a.act, "attack", "breach: the cut-off unit attacks")
    check(a and a.obstacle and (a.obstacle.x .. "," .. a.obstacle.y), "2,0", "breach: the wall")
    check(at(a), "1,0", "breach: from beside it")
end

-- test_a_key_holder_opens_the_door_before_a_wall: the same cut, a door at (2,0) as well as a
-- wall: the opener uses Door; a unit with no key still strikes the wall.
do
    local A = blue(0x01, 0, 0, 0)
    local E = red(0x81, 4, 0, { isBoss = true, minRange = false })
    local o = {
        objective = { kind = "boss" }, reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        field = fieldsOf { ["4,0"] = BOSS_SIDE, ["2,0"] = FROM_WALL },
        obstacles = { { x = 2, y = 0, hp = 20 } }, doors = { { x = 2, y = 0 } },
        openers = { [0x01] = true },
    }
    check(B.decide(boardOf(A, E), sightOf(o), style("careful")).act, "door", "door: opener")
    o.openers = {}
    check(B.decide(boardOf(A, E), sightOf(o), style("careful")).act, "attack",
          "door: no key, the wall")
end

-- test_healers_act_after_the_fighters: H heals A only once A has acted; until then A moves.
do
    local A = blue(0x01, 0, 0, 0, { hp = 10, maxhp = 20, minRange = false })
    local H = blue(0x02, 1, 1, 0, { minRange = false })
    local o = {
        staves = { [0x02] = { { slot = 0, amount = 10 } } },
        heals = { [0x02] = { ["1,0"] = { { slot = 0, amount = 10, targets = { 0x01 } } } } },
        reach = { [0x02] = tiles({ 1, 0 }) },
    }
    local a = B.decide(boardOf(A, H), sightOf(o), style("careful"))
    check(a and a.unit, 0x01, "heal: the fighter acts first")
    A.acted = true
    a = B.decide(boardOf(A, H), sightOf(o), style("careful"))
    check(a and a.act, "staff", "heal: then the healer heals")
    check(a and a.targetId, 0x01, "heal: the wounded ally")
    check(a and a.slot, 0, "heal: with its staff's slot")
end

-- test_mend_uses_a_vulnerary_when_down_its_whole_amount: no attack, 15 HP down, a 10-HP
-- Vulnerary in slot 1: used. Only 5 down: kept.
do
    local A = blue(0x01, 0, 0, 0, { hp = 5, maxhp = 20 })
    local o = { mend = { [0x01] = { slot = 1, amount = 10 } } }
    local a = B.decide(boardOf(A), sightOf(o), style("careful"))
    check(a and a.act, "item", "mend: a wounded unit with nothing to strike uses it")
    check(a and a.slot, 1, "mend: that slot")
    A.hp = 15
    check(B.decide(boardOf(A), sightOf(o), style("careful")).act, "wait", "mend: not for 5 HP")
end

-- test_recruit_claim_talks_first_and_marches_when_out_of_reach: green T talkable by A.
do
    local A = blue(0x01, 0, 0, 0)
    local T = blue(0x30, 5, 3, 0, { faction = "green" })
    local E = red(0x81, 9, 9, { hp = 1 })
    local o = { reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }, { 2, 0 }) },
                talk = { [0x01] = { [0x30] = true } } }
    local st = claimed("careful", { id = "r1", kind = "recruit", unit = { 0x30 } })
    local a = B.decide(boardOf(A, T, E), sightOf(o), st)
    check(a and a.act, "talk", "recruit: talks")
    check(a and a.targetId, 0x30, "recruit: to the recruit")
    check(at(a), "2,0", "recruit: from beside it")
    -- no claim: the habit still takes the offered Talk
    check(B.decide(boardOf(A, T, E), sightOf(o), style("careful")).act, "talk", "talk habit")
    -- out of reach: the claim marches the talker on the recruit
    o.reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) }
    a = B.decide(boardOf(A, T, E), sightOf(o), st)
    check(a and a.act, "wait", "recruit: marches when it cannot reach")
    check(at(a), "1,0", "recruit: toward the recruit")
end

-- test_keys_and_priority_rank_their_target_first: A deals more to E1, but E2 holds a key
-- (keys claim) or is a priority claim's class.
do
    local A = blue(0x01, 0, 0, 0)
    local E1 = red(0x81, 1, 0, { hp = 30, classId = CLS_A })
    local E2 = red(0x82, 0, 1, { hp = 30, classId = CLS_B })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }) }, keys = { [0x82] = true },
        fc = { [0x01] = { [0x81] = { ["0,0"] = fc { hit = 90, dmg = 9, hits = 1 } },
                          [0x82] = { ["0,0"] = fc { hit = 90, dmg = 3, hits = 1 } } } },
    }
    local board = boardOf(A, E1, E2)
    check(B.decide(board, sightOf(o), style("careful")).targetId, 0x81, "no claim: the bigger hit")
    check(B.decide(board, sightOf(o), claimed("careful", { id = "k", kind = "keys" })).targetId,
          0x82, "keys: the key holder first")
    check(B.decide(board, sightOf(o), claimed("careful", { id = "p", kind = "priority",
                                                         vs = { CLS_B } })).targetId,
          0x82, "priority: the named class first")
end

-- test_avoid_keeps_the_unit_out_of_reach: P marches right; (2,0) is in the archer's reach.
do
    local P = blue(0x01, 0, 0, 0, { minRange = false })
    local X = red(0x81, 4, 0, { classId = CLS_A, minRange = 2, maxRange = 2 })
    local o = { reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }, { 2, 0 }) } }
    check(at(B.decide(boardOf(P, X), sightOf(o), style("bold"))), "2,0", "no claim: as far as it goes")
    local st = claimed("bold", { id = "v", kind = "avoid", unit = { 0x01 }, vs = { CLS_A } })
    check(at(B.decide(boardOf(P, X), sightOf(o), st)), "1,0", "avoid: short of the reach")
end

-- test_heal_claim_counts_the_heal_before_the_enemy_phase: careful A (20 HP) on the boss:
-- counter 12 + the boss's strike 10 kills; a healer beside the attack tile gives 10 back.
do
    local A = blue(0x01, 0, 0, 0)
    local H = blue(0x02, 1, 0, 1, { minRange = false })
    local E = red(0x81, 2, 0, { isBoss = true, hp = 40 })
    local o = {
        objective = { kind = "boss" }, danger = { ["1,0"] = 1 },
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x02] = tiles({ 0, 1 }, { 1, 1 }) },
        staves = { [0x02] = { { slot = 0, amount = 10 } } },
        fc = { [0x01] = { [0x81] = { ["1,0"] = fc { hit = 80, dmg = 5, hits = 1, counters = true,
                                                    counterHit = 80, counterDmg = 12,
                                                    counterHits = 1, takenHit = 80,
                                                    takenDmg = 10, takenHits = 1 } } } },
    }
    local a = B.decide(boardOf(A, H, E), sightOf(o), style("careful"))
    check(a and a.act ~= "attack", true, "no claim: careful refuses the boss")
    a = B.decide(boardOf(A, H, E), sightOf(o),
                 claimed("careful", { id = "h", kind = "heal", vs = "boss" }))
    check(a and a.act, "attack", "heal claim: the heal is counted")
end

-- test_fog_hides_targets_and_marches_on_the_unseen: E stands in fog: no attack on it, and
-- the march heads for the nearest unseen tile, not for E.
do
    local A = blue(0x01, 0, 0, 0)
    local E = red(0x81, 1, 0, { hp = 1 })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 0, 1 }) }, hidden = { ["1,0"] = true },
        unseen = { { x = 0, y = 3 } },
        fc = { [0x01] = { [0x81] = { ["0,0"] = fc { hit = 100, dmg = 9, hits = 1,
                                                    killsTarget = true } } } },
    }
    local a = B.decide(boardOf(A, E), sightOf(o), style("bold"))
    check(a and a.act, "wait", "fog: no target it cannot see")
    check(at(a), "0,1", "fog: toward the unseen, not the hidden enemy")
end

-- ── The planner ─────────────────────────────────────────────────────────────────────────

-- test_planner_odds: one sure blow of 10 kills 10 HP; two coin-flip blows of 6 kill 10 HP a
-- quarter of the time; a crit triples.
do
    local sure = { { p = 1, c = 0, dmg = 10 } }
    check(Planner.odds(sure, 10), 1, "odds: a sure blow kills")
    local flip = { { p = 0.5, c = 0, dmg = 6 }, { p = 0.5, c = 0, dmg = 6 } }
    check(Planner.odds(flip, 10), 0.25, "odds: both must land")
    check(Planner.odds({ { p = 1, c = 1, dmg = 4 } }, 10), 1, "odds: a crit triples")
end

-- test_planner_takes_the_sure_kill: E1 dies to A's blow, E2 only takes a chip.
do
    local A = blue(0x01, 0, 0, 0)
    local E1 = red(0x81, 1, 0, { hp = 5 })
    local E2 = red(0x82, 0, 1, { hp = 30 })
    local sight = sightOf {
        reach = { [0x01] = tiles({ 0, 0 }) },
        fc = { [0x01] = { [0x81] = { ["0,0"] = fc { hit = 100, dmg = 9, hits = 1, killsTarget = true } },
                          [0x82] = { ["0,0"] = fc { hit = 100, dmg = 9, hits = 1 } } } },
    }
    local a = Planner.plan(B, boardOf(A, E1, E2), sight, style("careful"))
    check(a and a.targetId, 0x81, "planner: the kill")
end

-- test_planner_weighs_the_enemy_phase: marching to (1,0) gains 20 steps of the field, but the
-- AI would strike A there for its whole HP. careful holds; bold takes the ground.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local X = red(0x81, 9, 9, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        field = function() return { [0] = { [0] = 40, [1] = 20 } } end,
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.x == 1 then
                    return { { target = b.unit.id, takenHit = 100, takenDmg = 25, takenHits = 1,
                               takenCrit = 0 } }
                end
            end
            return {}
        end,
    }
    check(at(Planner.plan(B, boardOf(A, X), sightOf(o), style("careful"))), "0,0",
          "planner: careful holds out of the strike")
    check(at(Planner.plan(B, boardOf(A, X), sightOf(o), style("bold"))), "1,0",
          "planner: bold takes the ground")
end

-- test_planner_heals_between_attacks: the grell pattern. A's attack draws a 12 counter and the
-- enemy phase strikes 10 more: 22 of A's 20. H's heal after the attack (+10) keeps A alive,
-- so careful attacks and heals; without H it does not attack. A strikes from where it
-- stands: the heals the game lists were read with it there.
do
    local A = blue(0x01, 0, 1, 0)
    local H = blue(0x02, 1, 0, 1, { minRange = false })
    local E = red(0x81, 2, 0, { isBoss = true, hp = 40 })
    local o = {
        objective = { kind = "boss" },
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x02] = tiles({ 0, 1 }, { 1, 1 }) },
        staves = { [0x02] = { { slot = 0, amount = 10 } } },
        heals = { [0x02] = { ["1,1"] = { { slot = 0, amount = 10, targets = { 0x01 } } } } },
        fc = { [0x01] = { [0x81] = { ["1,0"] = fc { hit = 100, dmg = 5, hits = 1, counters = true,
                                                    counterHit = 100, counterDmg = 12,
                                                    counterHits = 1 } } } },
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.unit.id == 0x01 and b.x == 1 then
                    return { { target = 0x01, takenHit = 100, takenDmg = 10, takenHits = 1,
                               takenCrit = 0 } }
                end
            end
            return {}
        end,
    }
    local st = style("careful")
    local first, plan = Planner.plan(B, boardOf(A, H, E), sightOf(o), st)
    local acts = {}
    for _, a in ipairs(plan and plan.acts or {}) do acts[#acts + 1] = a.act end
    check(table.concat(acts, ","), "attack,staff", "planner: attack, then heal the attacker")
    check(first and first.act, "attack", "planner: the attack first")
    -- no healer: the counter and the strike together kill A, so careful does not attack
    local alone = Planner.plan(B, boardOf(A, E), sightOf(o), st)
    check(alone and alone.act ~= "attack", true, "planner: no heal, no attack")
    -- A starting at (0,0) must move to strike: the heal was read with A at (0,0), so it is
    -- no heal for A at (1,0), and careful does not attack
    local _, moved = Planner.plan(B, boardOf(blue(0x01, 0, 0, 0), H, E), sightOf(o), st)
    local heals = 0
    for _, a in ipairs(moved and moved.acts or {}) do
        if a.act == "staff" then heals = heals + 1 end
    end
    check(heals, 0, "planner: no heal on a unit the plan has moved")
end

-- test_planner_prices_standing_exposure: the march to (1,0) gains 20 steps but X reaches it
-- for 25 of A's 20; (0,1) gains 10 and nothing reaches it. Only the beam's top plan is
-- judged (FINAL = 1), so the pick is the beam's own: its exposure term keeps the retreat
-- first, where before it ranked the march first and the judge had nothing safe to choose.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local X = red(0x81, 3, 0)
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }, { 0, 1 }), [0x81] = tiles({ 2, 0 }) },
        field = function() return { [0] = { [0] = 40, [1] = 20 }, [1] = { [0] = 30 } } end,
        danger = { ["1,0"] = 1 },
        fc = { [0x01] = { [0x81] = { ["1,0"] = fc { takenHit = 100, takenDmg = 25, takenHits = 1 } } } },
    }
    local final = Planner.FINAL
    Planner.FINAL = 1
    local a = Planner.plan(B, boardOf(A, X), sightOf(o), style("careful"))
    Planner.FINAL = final
    check(at(a), "0,1", "planner: careful takes the safe ground")
    check(a and a.why, "retreat", "planner: it is the retreat")
end

-- test_planner_exposure_spares_the_killed: A's sure kill removes X, the only enemy that
-- reaches (2,2), so B's march there costs nothing -- whichever unit the beam moves first.
do
    local A = blue(0x01, 0, 0, 0)
    local Bu = blue(0x02, 1, 0, 2, { minRange = false })
    local X = red(0x81, 1, 0, { hp = 5 })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }), [0x02] = tiles({ 0, 2 }, { 2, 2 }),
                  [0x81] = tiles({ 1, 0 }, { 2, 1 }) },
        field = function() return { [0] = { [0] = 50 }, [2] = { [0] = 40, [2] = 20 } } end,
        danger = { ["2,2"] = 1 },
        fc = { [0x01] = { [0x81] = { ["0,0"] = fc { hit = 100, dmg = 9, hits = 1, killsTarget = true } } },
               [0x02] = { [0x81] = { ["2,2"] = fc { takenHit = 100, takenDmg = 25, takenHits = 1 } } } },
    }
    local _, plan = Planner.plan(B, boardOf(A, Bu, X), sightOf(o), style("careful"))
    local moved
    for _, a in ipairs(plan and plan.acts or {}) do
        if a.unitId == 0x02 then moved = at(a) end
    end
    check(moved, "2,2", "planner: a killed enemy threatens no one")
end

-- test_planner_visits_a_safe_village: nothing reaches the village at (1,0), so careful takes
-- it over a step of ground; the offer is in the plan's record, played, at no chance to die.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local X = red(0x81, 9, 9, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }, { 0, 1 }) },
        explorable = { { x = 1, y = 0, kind = "visit" } },
        canExplore = { [0x01] = { ["1,0"] = "visit" } },
    }
    local a, plan = Planner.plan(B, boardOf(A, X), sightOf(o), style("careful"))
    check(a and a.act, "visit", "explore: a safe village is visited")
    check(at(a), "1,0", "explore: from its own tile")
    local e = plan and plan.explore and plan.explore[1]
    check(e and e.die, 0, "explore: offered at no chance to die")
    check(e and e.played, true, "explore: the offer was played")
    -- a unit the game refuses (a Phantom, a Silenced unit) is offered nothing
    o.canExplore = {}
    local b = Planner.plan(B, boardOf(A, X), sightOf(o), style("careful"))
    check(b and b.act ~= "visit", true, "explore: only where the game's menu allows it")
end

-- test_planner_skips_a_risky_village: X reaches the village and can kill A there, so the
-- visit earns nothing -- under every style, bold included -- and the offer is recorded with
-- its chance to die, unplayed.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local X = red(0x81, 3, 0)
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x81] = tiles({ 2, 0 }) },
        danger = { ["1,0"] = 1 },
        fc = { [0x01] = { [0x81] = { ["1,0"] = fc { takenHit = 100, takenDmg = 25, takenHits = 1 } } } },
        explorable = { { x = 1, y = 0, kind = "chest" } },
        canExplore = { [0x01] = { ["1,0"] = "chest" } },
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.x == 1 then
                    return { { target = b.unit.id, takenHit = 100, takenDmg = 25, takenHits = 1,
                               takenCrit = 0 } }
                end
            end
            return {}
        end,
    }
    for _, aggression in ipairs({ "careful", "bold" }) do
        local a, plan = Planner.plan(B, boardOf(A, X), sightOf(o), style(aggression))
        check(a and a.act ~= "chest", true, "explore: no risky chest, " .. aggression)
        local e = plan and plan.explore and plan.explore[1]
        check(e and e.die > 0, true, "explore: the offer carries its chance to die, " .. aggression)
        check(e and e.played, nil, "explore: unplayed, " .. aggression)
    end
end

-- test_planner_beam_withholds_the_credit: X reaches the chest with a small chance to kill A,
-- and only the beam's top plan is judged (FINAL = 1), against no enemy phase. Credited, the
-- chest would top the beam; the beam's own check leaves it uncredited, so A holds.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local X = red(0x81, 3, 0)
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x81] = tiles({ 2, 0 }) },
        danger = { ["1,0"] = 1 },
        fc = { [0x01] = { [0x81] = { ["1,0"] = fc { takenHit = 10, takenDmg = 25, takenHits = 1 } } } },
        explorable = { { x = 1, y = 0, kind = "chest" } },
        canExplore = { [0x01] = { ["1,0"] = "chest" } },
    }
    local final = Planner.FINAL
    Planner.FINAL = 1
    local a = Planner.plan(B, boardOf(A, X), sightOf(o), style("careful"))
    Planner.FINAL = final
    check(at(a), "0,0", "explore: the beam credits no chest at a chance to die")
end

-- test_planner_judge_takes_the_credit_back: nothing the beam sees reaches the village, but the
-- enemy phase the AI plays strikes A there with a small chance to kill. Credited, the visit
-- would outweigh that chance; the judge takes the credit back, so careful stays put.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local X = red(0x81, 9, 9, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        explorable = { { x = 1, y = 0, kind = "visit" } },
        canExplore = { [0x01] = { ["1,0"] = "visit" } },
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.x == 1 then
                    return { { target = b.unit.id, takenHit = 10, takenDmg = 25, takenHits = 1,
                               takenCrit = 0 } }
                end
            end
            return {}
        end,
    }
    local die = Planner.odds(Planner.blows(10, 25, 1, 0, Sight.hitChance), 20)
    check(die > 0 and Planner.WEIGHTS.careful.death * die < Planner.WEIGHTS.careful.recruit, true,
          "explore: the strike's chance is small enough that a credit would buy it")
    local a = Planner.plan(B, boardOf(A, X), sightOf(o), style("careful"))
    check(at(a), "0,0", "explore: the judged phase's chance withdraws the credit")
end

-- test_exploring_sends_the_nearest: the village at (8,0) is nearer B by the game's field, so
-- B marches to it and A marches on the enemy.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local Bu = blue(0x02, 1, 5, 0, { minRange = false })
    local X = red(0x81, 0, 9, { minRange = false })
    local function manhattanField(goal)
        local f = {}
        for y = 0, 9 do
            f[y] = {}
            for x = 0, 14 do f[y][x] = math.abs(x - goal.x) + math.abs(y - goal.y) end
        end
        return f
    end
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }, { 0, 1 }),
                  [0x02] = tiles({ 5, 0 }, { 6, 0 }, { 5, 1 }) },
        field = manhattanField,
        explorable = { { x = 8, y = 0, kind = "visit" } },
        canExplore = { [0x01] = { ["8,0"] = "visit" }, [0x02] = { ["8,0"] = "visit" } },
    }
    local marches = {}
    for _, c in ipairs(B.candidates(boardOf(A, Bu, X), sightOf(o), style("careful"))) do
        for _, a in ipairs(c.acts) do
            if a.why == "march" then marches[c.unit.id] = at(a) end
        end
    end
    check(marches[0x02], "6,0", "exploring: the nearer unit marches to the village")
    check(marches[0x01], "0,1", "exploring: the other marches on the enemy")
end

-- test_planner_assault: the boss X has 20 HP. A's and C's blows (12 each, sure) kill it
-- together; either alone leaves it alive to strike that unit in its phase for its whole HP.
-- The beam reads each strike tile as deadly (X reaches it) and keeps two plans a depth
-- (BEAM = 2): holding outranks either blow alone, so it never holds both. Only the assault
-- plan is the combination, and it is played.
do
    local A = blue(0x01, 0, 0, 0)
    local C = blue(0x02, 1, 0, 2)
    local X = red(0x81, 1, 1, { isBoss = true, hp = 20 })
    local blow = fc { hit = 100, dmg = 12, hits = 1, counters = true, counterHit = 100,
                      counterDmg = 5, counterHits = 1, takenHit = 100, takenDmg = 30,
                      takenHits = 1 }
    local o = {
        objective = { kind = "boss" },
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }, { 0, 1 }), [0x02] = tiles({ 0, 2 }, { 1, 2 }),
                  [0x81] = tiles({ 1, 1 }) },
        danger = { ["1,0"] = 1, ["1,2"] = 1 },
        fc = { [0x01] = { [0x81] = { ["1,0"] = blow } }, [0x02] = { [0x81] = { ["1,2"] = blow } } },
        enemyPhase = function(plan)
            if plan.gone[0x81] then return {} end
            local out = {}
            for _, b in ipairs(plan.blues) do
                if math.abs(b.x - 1) + math.abs(b.y - 1) == 1 then
                    out[#out + 1] = { target = b.unit.id, takenHit = 100, takenDmg = 30,
                                      takenHits = 1, takenCrit = 0 }
                end
            end
            return out
        end,
    }
    local beam = Planner.BEAM
    Planner.BEAM = 2
    local a, plan = Planner.plan(B, boardOf(A, C, X), sightOf(o), style("careful"))
    Planner.BEAM = beam
    check(plan and plan.kind, "assault", "assault: the combination is the plan played")
    check(a and a.act, "attack", "assault: it opens with a blow")
    local blows = 0
    for _, x in ipairs(plan and plan.acts or {}) do
        if x.act == "attack" then blows = blows + 1 end
    end
    check(blows, 2, "assault: both strike the boss")
    -- a boss on a cloned generic row has no CA_BOSS: the objective names it (its death quote
    -- raises the goal's flag), and the assault is the same
    local plain = red(0x81, 1, 1, { hp = 20 })
    o.objective = { kind = "boss", boss = 0x81 }
    Planner.BEAM = 2
    local _, named = Planner.plan(B, boardOf(blue(0x01, 0, 0, 0), blue(0x02, 1, 0, 2), plain),
                                  sightOf(o), style("careful"))
    Planner.BEAM = beam
    check(named and named.kind, "assault", "assault: the boss the objective names")
    o.objective = { kind = "boss" }
    -- one unit alone: no assault, and careful does not strike
    local alone, aplan = Planner.plan(B, boardOf(A, X), sightOf(o), style("careful"))
    check(aplan and aplan.kind, "beam", "assault: none with one striker")
    check(alone and alone.act ~= "attack", true, "assault: a lone strike is not made")
end

-- test_planner_chains_the_counter: A (30 HP) strikes the boss for 20; the boss's counter (66,
-- 15) and its own strike next phase (sure, 15) kill A whenever the counter lands. Averaging
-- the counter leaves A at 18, out of the phase's reach to kill: the chain does not.
do
    local A = blue(0x01, 0, 0, 0, { hp = 30 })
    local X = red(0x81, 2, 0, { isBoss = true, hp = 40 })
    local o = {
        objective = { kind = "boss" },
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        fc = { [0x01] = { [0x81] = { ["1,0"] = fc { hit = 100, dmg = 20, hits = 1, counters = true,
                                                    counterHit = 66, counterDmg = 15,
                                                    counterHits = 1 } } } },
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.x == 1 then
                    return { { target = b.unit.id, takenHit = 100, takenDmg = 15, takenHits = 1,
                               takenCrit = 0 } }
                end
            end
            return {}
        end,
    }
    local a = Planner.plan(B, boardOf(A, X), sightOf(o), style("careful"))
    check(a and a.act ~= "attack", true, "chain: no strike whose landed counter leaves A to die")
end

-- test_planner_unstalls: A holding at (0,0) is the best plan, but botrun has seen this board
-- before (opts.stalled): the plan played must change it, and the least it can is the step to
-- (1,0) that X reaches with a small chance to kill.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local X = red(0x81, 3, 0)
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x81] = tiles({ 2, 0 }) },
        danger = { ["1,0"] = 1 },
        fc = { [0x01] = { [0x81] = { ["1,0"] = fc { takenHit = 10, takenDmg = 25, takenHits = 1 } } } },
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.x == 1 then
                    return { { target = b.unit.id, takenHit = 10, takenDmg = 25, takenHits = 1,
                               takenCrit = 0 } }
                end
            end
            return {}
        end,
    }
    check(at(Planner.plan(B, boardOf(A, X), sightOf(o), style("careful"))), "0,0",
          "unstall: careful holds")
    local a = Planner.plan(B, boardOf(A, X), sightOf(o), style("careful"), { stalled = true })
    check(at(a), "1,0", "unstall: a stalled board is changed, by the least risky change")
end

-- test_planner_surprise: A attacks X from (1,0) expecting X at 10 HP and itself at 20; C
-- moves next. The plan plays on only while the board is what it expected.
do
    local function plan(o)
        o = o or {}
        return { acts = { { unitId = 0x01, act = "attack", targetId = 0x81, move = { x = 1, y = 0 } },
                          { unitId = 0x02, act = "wait", move = { x = 0, y = 2 } } },
                 expect = { { hp = 20, gone = o.gone, targetHp = 10 } },
                 enemies = { [0x81] = true } }
    end
    local function A(o) return blue(0x01, 0, 1, 0, o) end
    local function C(o) return blue(0x02, 1, 0, 1, o) end
    local before = boardOf(blue(0x01, 0, 0, 0), C(), red(0x81, 2, 0, { hp = 20 }))
    local function after(...) return boardOf(...) end
    local S = Planner.surprise
    check(S(plan(), 1, before, after(A { acted = true }, C(), red(0x81, 2, 0, { hp = 10 }))), nil,
          "surprise: as expected, play on")
    check(S(plan(), 1, before, after(A { acted = true }, C(), red(0x81, 2, 0, { hp = 4 }))), nil,
          "surprise: more dealt than expected is no surprise")
    check(S(plan(), 1, before, after(A { acted = true }, C(), red(0x81, 2, 0, { hp = 20 }))),
          "a blow missed", "surprise: a miss")
    check(S(plan(), 1, before, after(A { acted = true, hp = 12 }, C(), red(0x81, 2, 0, { hp = 10 }))),
          "the counter took more than expected", "surprise: a heavier counter")
    check(S(plan(), 1, before, after(C(), red(0x81, 2, 0, { hp = 10 }))), "a unit of ours fell",
          "surprise: a death")
    check(S(plan(), 1, before, after(A { acted = true }, C())), "an unexpected kill",
          "surprise: a kill the plan did not count on")
    check(S(plan { gone = 0x81 }, 1, before, after(A { acted = true }, C(), red(0x81, 2, 0, { hp = 3 }))),
          "the kill missed", "surprise: an expected kill that did not land")
    local seen = after(A { acted = true }, C(), red(0x81, 2, 0, { hp = 10 }), red(0x82, 5, 5))
    check(S(plan(), 1, before, seen), "an enemy came into sight", "surprise: a new enemy")
    check(S(plan(), 1, before, seen, function(x, y) return not (x == 5 and y == 5) end), nil,
          "surprise: an enemy still in fog is no news")
    check(S(plan(), 1, before, after(A { acted = true }, C { acted = true }, red(0x81, 2, 0, { hp = 10 }))),
          "the next unit cannot act", "surprise: the next act is gone")
    check(S(plan(), 2, before, before), "the plan is played out", "surprise: nothing left to play")
    -- C means to heal A, but the counter missed: A is whole and the game offers no Staff
    local healing = plan()
    healing.acts[2] = { unitId = 0x02, act = "staff", targetId = 0x01, move = { x = 0, y = 1 } }
    check(S(healing, 1, before, after(A { acted = true }, C(), red(0x81, 2, 0, { hp = 10 }))),
          "the heal's target is not hurt", "surprise: nothing to heal")
    check(S(healing, 1, before, after(A { acted = true, hp = 25, maxhp = 30 }, C(),
                                      red(0x81, 2, 0, { hp = 10 }))), nil,
          "surprise: a hurt target is healed as planned")
end

if fails > 0 then
    print(string.format("\n%d/%d FAILED", fails, tests)); os.exit(1)
else
    print(string.format("ok -- %d assertions", tests))
end

