-- Tests for clearbot.lua -- the pure target-selection core (no emulator).
-- Run: lua tools/playtest/test_clearbot.lua
local here = (arg[0]:match("(.*/)")) or "./"
local C = dofile(here .. "clearbot.lua")

local tests, fails = 0, 0
local function check(got, want, msg)
    tests = tests + 1
    if got ~= want then
        fails = fails + 1
        print(string.format("FAIL: %s\n  got  %s\n  want %s", msg, tostring(got), tostring(want)))
    end
end

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
    check(C.pickTarget(reach, enemies, { range = 1 }), nil, "no enemy in range -> nil")
end

-- One enemy orthogonally adjacent to a reachable tile -> that enemy, from that tile.
do
    local reach = tiles({ 5, 5 }, { 5, 6 })
    local enemies = { { x = 5, y = 7, hp = 20, is_boss = false } }  -- adjacent to (5,6)
    local pick = C.pickTarget(reach, enemies, { range = 1 })
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
    local pick = C.pickTarget(reach, enemies, { range = 1 })
    check(pick and pick.target.is_boss, true, "boss preferred over non-boss")
end

-- Among non-boss targets, the lowest-HP one wins (likeliest kill).
do
    local reach = tiles({ 0, 1 }, { 2, 1 })
    local enemies = {
        { x = 0, y = 2, hp = 18, is_boss = false },  -- adjacent to (0,1)
        { x = 2, y = 2, hp = 5, is_boss = false },   -- adjacent to (2,1)
    }
    local pick = C.pickTarget(reach, enemies, { range = 1 })
    check(pick and pick.target.hp, 5, "lowest-hp non-boss preferred")
end

-- Range 2 (e.g. a hand axe): an enemy two tiles from a reachable tile is attackable.
do
    local reach = tiles({ 4, 4 })
    local enemies = { { x = 4, y = 6, hp = 20, is_boss = false } }  -- distance 2 from (4,4)
    check(C.pickTarget(reach, enemies, { range = 1 }), nil, "range 1 can't reach distance 2")
    local pick = C.pickTarget(reach, enemies, { range = 2 })
    check(pick ~= nil, true, "range 2 reaches distance 2")
end

-- A BOW (min_range 2): an ADJACENT enemy is NOT attackable -- striking from range 1 leaves
-- no Attack command, so pickTarget must skip the adjacent tile (#65 recordrbgtest bug).
do
    local adjacent = tiles({ 4, 5 })  -- distance 1 from the foe at (4,6)
    local enemies = { { x = 4, y = 6, hp = 20, is_boss = false } }
    check(C.pickTarget(adjacent, enemies, { range = 2, min_range = 2 }), nil,
          "bow (min_range 2) won't pick an adjacent tile it can't fire from")
    -- but a true range-2 tile IS picked, and an adjacent one is left out of a mixed reach.
    local mixed = tiles({ 4, 5 }, { 4, 4 })  -- (4,5)=dist 1, (4,4)=dist 2
    local pick = C.pickTarget(mixed, enemies, { range = 2, min_range = 2 })
    check(pick ~= nil and pick.tile.x == 4 and pick.tile.y == 4, true,
          "bow strikes from the range-2 tile (4,4), not the adjacent (4,5)")
end

-- ── pickMove (#60 last-mile breach) ─────────────────────────────────────────────

local P = dofile(here .. "pathing.lua")

-- Best field tile wins; Manhattan tiebreak on a plateau.
do
    local field = { [0] = { [0] = 4, [1] = 3, [2] = 3 } }   -- fd row y=0
    local reach = tiles({ 0, 0 }, { 1, 0 }, { 2, 0 })
    local mv = C.pickMove(reach, { field = field, cur = { x = 0, y = 0 },
                                   goal = { x = 9, y = 0 } })
    check(mv.x, 2, "plateau tiebreak: same fd -> nearer the goal by Manhattan")
end

-- Blocked tiles (claimed by a friendly this phase) are skipped.
do
    local field = { [0] = { [0] = 4, [1] = 3, [2] = 2 } }
    local reach = tiles({ 0, 0 }, { 1, 0 }, { 2, 0 })
    local blocked = { [C.tileKey(2, 0)] = true }
    local mv = C.pickMove(reach, { field = field, cur = { x = 0, y = 0 },
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
    local mv = C.pickMove(reach, { field = field, cur = { x = 2, y = 0 },
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
    local blocked = { [C.tileKey(3, 0)] = true }             -- leader claimed the front
    local mv = C.pickMove(reach, { field = field, cur = { x = 2, y = 0 },
                                   goal = { x = 9, y = 0 }, blocked = blocked,
                                   enemies = { { x = 0, y = 0, hp = 20 } } })  -- fd 10 > cur 8
    check(mv.x, 2, "straggler behind never pulls the follower backward")
end

-- Field-less tiles fall back to Manhattan-toward-goal (off-field never beats on-field).
do
    local field = { [0] = { [1] = 5 } }
    local reach = tiles({ 0, 0 }, { 1, 0 })
    local mv = C.pickMove(reach, { field = field, cur = { x = 0, y = 0 },
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
    local wall = { [C.tileKey(20, 7)] = true, [C.tileKey(22, 7)] = true,
                   [C.tileKey(20, 6)] = true, [C.tileKey(22, 6)] = true,
                   [C.tileKey(20, 5)] = true, [C.tileKey(21, 5)] = true,
                   [C.tileKey(22, 5)] = true }
    local function passable(x, y) return not wall[C.tileKey(x, y)] end
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
                    and not blocked[C.tileKey(x, y)] then
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
                if o ~= u then blocked[C.tileKey(o.x, o.y)] = true end
            end
            local reach = reachFor(u, blocked)
            local atk = C.pickTarget(reach, enemies, { range = 1 })
            if atk then engaged = true break end
            local mv = C.pickMove(reach, { field = field, cur = u,
                                           goal = boss, blocked = blocked,
                                           enemies = enemies })
            if mv then u.x, u.y = mv.x, mv.y end
            claimed[C.tileKey(u.x, u.y)] = true
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

    check(C.gridHostileInReach(gridOf({ ["6,5"] = 0x81 }), 5, 5, 1, 1), true,
        "hostile adjacent ON THE GRID -> attackable")

    -- The #204 regression: the unit array says an enemy is at (6,5), but it stands in fog so
    -- RefreshUnitsOnBmMap never wrote it to gBmMapUnit. There is no Attack row.
    check(C.gridHostileInReach(gridOf({}), 5, 5, 1, 1), false,
        "enemy absent from the grid (fogged) -> NOT attackable")

    check(C.gridHostileInReach(gridOf({ ["6,5"] = 0x01 }), 5, 5, 1, 1), false,
        "a BLUE id on the grid is not a hostile")
    check(C.gridHostileInReach(gridOf({ ["6,5"] = 0x41 }), 5, 5, 1, 1), false,
        "a GREEN id on the grid is not a hostile")

    -- A bow cannot fire at an adjacent foe: min range 2.
    check(C.gridHostileInReach(gridOf({ ["6,5"] = 0x81 }), 5, 5, 2, 2), false,
        "bow: hostile at range 1 is out of [2,2]")
    check(C.gridHostileInReach(gridOf({ ["7,5"] = 0x81 }), 5, 5, 2, 2), true,
        "bow: hostile at range 2 is attackable")

    -- Diagonals count as range 2 (Manhattan), and the map edge must not throw.
    check(C.gridHostileInReach(gridOf({ ["1,1"] = 0x81 }), 0, 0, 1, 2), true,
        "diagonal hostile is at Manhattan 2")
    check(C.gridHostileInReach(gridOf({}), 0, 0, 1, 2), false,
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
    check(C.seizeDistance({ u(1, 3), u(2, 8) }, field, ruledOut), 6,
        "the ruled-out unit beside the tile does not mask the lord's distance")
    check(C.seizeDistance({ u(1, 3), { slot = 3, x = -1, y = -1, onField = false } }, field, {}), 6,
        "an off-field unit has no distance")
    check(C.seizeDistance({ u(2, 8) }, field, ruledOut), math.huge,
        "nobody left who could seize -> no distance")
    check(C.seizeDistance({ u(1, 3) }, nil, {}), math.huge, "no field -> no distance")

    -- boss dead, the lord marching: its seize distance falls -> progress
    local last = { dist = 6, enemies = 0 }
    check(C.madeProgress(last, { dist = 3, enemies = 0 }), true,
        "boss dead + seize distance falling = progress")
    -- boss dead, nobody closer, no fewer enemies -> no progress
    check(C.madeProgress(last, { dist = 6, enemies = 0 }), false,
        "boss dead + distance unchanged + enemy count unchanged = no progress")
    check(C.madeProgress({ dist = math.huge, enemies = 3 }, { dist = math.huge, enemies = 2 }), true,
        "a kill is progress even with no distance")
    check(C.madeProgress({ dist = 4, enemies = 2 }, { dist = 5, enemies = 2 }), false,
        "moving away with no kill is not progress")
    -- the target changed (boss died / a unit ruled out): the old best belonged to another
    -- question, so the change counts, and a farther first reading is not a stall
    check(C.madeProgress({ dist = 4, enemies = 0, key = "boss" }, { dist = 10, enemies = 0, key = "seize:1" }),
        true, "a new target is progress, not a stall against the old best")
    check(C.madeProgress({ dist = 10, enemies = 0, key = "seize:1" }, { dist = 10, enemies = 0, key = "seize:1" }),
        false, "same target, same distance, same enemies = no progress")
end

-- stepOffTile: a unit that cannot Seize clears the throne's approach. From its reachable tiles,
-- the one FARTHEST from the seize tile, never on or beside it; ties go to the shorter move.
do
    local seize = { x = 5, y = 5 }
    local reach = tiles({ 5, 4 }, { 4, 4 }, { 5, 2 }, { 3, 5 }, { 5, 1 })
    local t = C.stepOffTile(reach, { x = 5, y = 4 }, seize)
    check(t and t.x, 5, "steps to the farthest reachable tile (x)")
    check(t and t.y, 1, "steps to the farthest reachable tile (y)")
    check(C.stepOffTile(tiles({ 5, 4 }, { 4, 5 }), { x = 5, y = 4 }, seize), nil,
        "only tiles beside the throne reachable -> nil (no move that helps)")
    -- tie on distance from the throne: the shorter move wins
    local tie = C.stepOffTile(tiles({ 5, 8 }, { 8, 5 }), { x = 6, y = 8 }, seize)
    check(tie and tie.x, 5, "tie on throne distance -> the nearer tile")
    check(C.needsToStepOff({ x = 5, y = 4 }, seize), true, "beside the throne -> step off")
    check(C.needsToStepOff({ x = 5, y = 5 }, seize), true, "on the throne -> step off")
    check(C.needsToStepOff({ x = 5, y = 3 }, seize), false, "two away -> stay")
end

if fails > 0 then
    print(string.format("\n%d/%d FAILED", fails, tests)); os.exit(1)
else
    print(string.format("ok -- %d assertions", tests))
end

