-- Tests for bot.lua -- the pure policy (no emulator): the greedy core the clear scenarios
-- drive, then Bot.decide's styles over hand-built boards and a fake `sight`.
-- Run: lua tools/playtest/test_bot.lua
local here = (arg[0]:match("(.*/)")) or "./"
local B = dofile(here .. "bot.lua")

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
                if math.abs(dx) + math.abs(dy) <= MOVE and x >= 0 and y >= 0
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
-- stood on that tile without a legal Seize is ruled out, so the lord's march is what counts.
do
    -- field[y][x] = steps to the target; a 1-row map, target at x = 9.
    local field = { [0] = {} }
    for x = 0, 9 do field[0][x] = 9 - x end
    local function u(slot, x) return { slot = slot, x = x, y = 0, onField = true } end
    local ruledOut = { [2] = true }   -- slot 2 stood on the seize tile: no Seize for it
    check(B.seizeDistance({ u(1, 3), u(2, 8) }, field, ruledOut), 6,
        "the ruled-out unit beside the tile does not mask the lord's distance")
    check(B.seizeDistance({ u(1, 3), { slot = 3, x = -1, y = -1, onField = false } }, field, {}), 6,
        "an off-field unit has no distance")
    check(B.seizeDistance({ u(2, 8) }, field, ruledOut), math.huge,
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
    -- the target changed (boss died / a unit ruled out): the old best belonged to another
    -- question, so the change counts, and a farther first reading is not a stall
    check(B.madeProgress({ dist = 4, enemies = 0, key = "boss" },
                         { dist = 10, enemies = 0, key = "seize:1" }),
        true, "a new target is progress, not a stall against the old best")
    check(B.madeProgress({ dist = 10, enemies = 0, key = "seize:1" },
                         { dist = 10, enemies = 0, key = "seize:1" }),
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

-- A fake sight. danger["x,y"] = count; reach[id] = tile list; fc[uid][tid]["x,y"] = forecast
-- (a missing entry is a harmless exchange: nothing dealt, nothing taken).
local QUIET = { hit = 0, dmg = 0, crit = 0, hits = 0, counters = false, counterHit = 0,
                counterDmg = 0, counterCrit = 0, counterHits = 0, takenHit = 0, takenDmg = 0,
                takenCrit = 0, takenHits = 0, killsTarget = false, diesWorst = false }
local function sightOf(o)
    local calls = 0
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
                    local d = math.abs(t.x - x) + math.abs(t.y - y)
                    if d >= e.minRange and d <= e.maxRange then n = n + 1 end
                end
                return n
            end
        end,
        forecast = function(u, t, x, y, slot)
            calls = calls + 1
            local byT = (o.fc or {})[u.id]
            local byTile = byT and byT[t.id]
            return (byTile and byTile[x .. "," .. y]) or QUIET
        end,
    }
    s.calls = function() return calls end
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
    local quiet = unanswered.forecast
    unanswered.forecast = function(...)
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

-- test_never_attacks_when_forecast_says_dies: diesWorst refuses the attack in every style
-- but greedy, which never reads a forecast.
do
    local A = blue(0x01, 0, 0, 0)
    local E1 = red(0x81, 1, 0, { hp = 30 })
    local board = boardOf(A, E1)
    local sight = sightOf {
        reach = { [0x01] = tiles({ 0, 0 }, { 0, 1 }) },
        fc = { [0x01] = { [0x81] = {
            ["0,0"] = fc { hit = 90, dmg = 10, hits = 1, diesWorst = true } } } },
    }
    for _, aggr in ipairs({ "careful", "even", "bold" }) do
        check(B.decide(board, sight, style(aggr)).act, "wait", aggr .. ": diesWorst refuses")
    end
    local fresh = sightOf {
        reach = { [0x01] = tiles({ 0, 0 }, { 0, 1 }) },
        fc = { [0x01] = { [0x81] = {
            ["0,0"] = fc { hit = 90, dmg = 10, hits = 1, diesWorst = true } } } },
    }
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

-- sight.cache carries forecasts across decide calls in one phase: once per pair and tile.
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
    B.decide(boardOf(A, Bu, E), sight, style("careful"))
    local first = sight.calls()
    B.decide(boardOf(A, Bu, E), sight, style("careful"))
    check(first, 1, "one forecast for the one pair and tile")
    check(sight.calls(), 1, "the second call reads it from the cache")
    -- the enemy's HP changed (it was hit): a different exchange, asked again
    local hurt = red(0x81, 1, 0, { hp = 25 })
    B.decide(boardOf(A, Bu, hurt), sight, style("careful"))
    check(sight.calls(), 2, "a changed HP is a new forecast")
    -- ANY unit moving, however far from the fighters, is a new board: the enemy's strike is
    -- its AI's pick, and a unit anywhere can block or open its path
    local far = blue(0x02, 1, 6, 0)
    B.decide(boardOf(A, far, hurt), sight, style("careful"))
    check(sight.calls(), 3, "a far ally that moved is a new forecast")
    local moved = blue(0x02, 1, 0, 2)
    B.decide(boardOf(A, moved, hurt), sight, style("careful"))
    check(sight.calls(), 4, "and so is one that moved near")
    -- and a spent weapon use too
    local spent = blue(0x01, 0, 0, 0)
    A.items, spent.items = { { id = 1, uses = 40 } }, { { id = 1, uses = 39 } }
    B.decide(boardOf(A, moved, hurt), sight, style("careful"))
    local before = sight.calls()
    B.decide(boardOf(spent, moved, hurt), sight, style("careful"))
    check(sight.calls(), before + 1, "a spent weapon use is a new forecast")
    -- no cache: every call asks again
    local bare = sightOf { danger = o.danger, reach = o.reach, fc = o.fc }
    B.decide(boardOf(A, Bu, E), bare, style("careful"))
    B.decide(boardOf(A, Bu, E), bare, style("careful"))
    check(bare.calls(), 2, "without a cache each call asks for itself")
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
    check(csv(B.prep(roster, 2, st).deploy), "2,1", "prep: a full sampled list keeps the carry")
end
test_carry_survives_a_full_deploy()

local function test_prep_forced_first()
    local roster = { unitOf(1, 0x01, 3), unitOf(2, 0x02, 9), unitOf(3, 0x03, 5, { forced = true }),
                     unitOf(4, 0x04, 7), unitOf(5, 0x05, 7), unitOf(6, 0x06, 1, { forced = true }) }
    local p = B.prep(roster, 4, { deploy = {} })
    check(csv(p.deploy), "3,6,2,4", "forced (slot order), then highest level, ties by slot")
    check(#p.give, 0, "no transfer rule decided: give is empty")
    p = B.prep(roster, 4, { deploy = { 0x01, 0x99, 0x01, 0x03 } })
    check(csv(p.deploy), "3,6,1,2",
        "style.deploy next; unknown charId skipped, duplicate not doubled")
    p = B.prep(roster, 5, { deploy = { 0x04 } })
    check(csv(p.deploy), "3,6,4,2,5", "cap 5: forced, style, then level")
    p = B.prep(roster, 1, { deploy = { 0x04 } })
    check(csv(p.deploy), "3,6", "forced alone exceed the cap: all forced still go, nothing else")
    p = B.prep(roster, 10, { deploy = {} })
    check(#p.deploy, 6, "cap above the roster: everyone")
end
test_prep_forced_first()

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
        for _, e in ipairs(r) do t[#t + 1] = e.item .. "x" .. e.qty end
        return csv(t)
    end
    check(flat(B.shop(10000, stock, { A, Bu })), "108x2,17x1,32x1",
        "vulneraries per unit first, then the cheapest usable weapon each lacks")
    check(flat(B.shop(700, stock, { A, Bu })), "108x2",
        "gold runs out after the vulneraries: 100 left buys no 400+ sword")
    local Cu0 = unitOf(3, 0x03, 1, { canUse = { [0x21] = true, [0x10] = true, [0x11] = true } })
    check(flat(B.shop(1000, stock, { Bu, Cu0 })), "108x2,33x1",
        "skip then continue: the lance (700) is skipped at 400 gold, "
            .. "the axe (100) after it is bought")
    A.items = { { id = 0x10, type = "sword", rank = 1 } }
    check(flat(B.shop(10000, stock, { A, Bu })), "108x2,32x1", "a unit holding its type buys none")
    local Cu = unitOf(3, 0x03, 1, { canUse = { [0x21] = true, [0x10] = true, [0x11] = true } })
    check(flat(B.shop(800, stock, { Cu })), "108x1,33x1,17x1",
        "skip-and-continue: exact fit, gold 800 buys vuln 300, axe 100, sword 400 in order")
    check(flat(B.shop(450, stock, { Cu })), "108x1,33x1",
        "the sword (400) is skipped at 50 gold, the buying stops there")
    A.items = { { id = 0x10, type = "sword", rank = 1 }, { id = 0x6C, kind = "vulnerary" } }
    check(flat(B.shop(10000, stock, { A, Bu })), "108x1,32x1",
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
    check(#B.STYLES.route, 2, "route is a sampled axis, two options")
end
test_route_follows_style()

if fails > 0 then
    print(string.format("\n%d/%d FAILED", fails, tests)); os.exit(1)
else
    print(string.format("ok -- %d assertions", tests))
end

