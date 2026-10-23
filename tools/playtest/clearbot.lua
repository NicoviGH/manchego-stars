-- clearbot.lua -- pure target-selection for the greedy clear-bot (#60, no emulator).
--
-- The decision core, split from the emulator driving so it is unit-tested without mGBA
-- (tools/playtest/test_clearbot.lua). The clear scenario reads real reachability, and the
-- enemy state from board.lua's Board.read (the one board reader), into plain tables and asks
-- pickTarget what to hit; it owns the actual moving/attacking. Boss-ness is passed in as data
-- (is_boss, board.lua's isBoss: the CA_BOSS character attribute) -- so this stays a pure
-- function over positions/hp.
--
-- pickTarget(reachable, enemies, prefs) -> { target = <enemy>, tile = {x,y} } | nil
--   reachable: list of {x,y} tiles the unit can move to this turn (its own tile included)
--   enemies:   list of {x,y,hp,is_boss}
--   prefs.range:     weapon MAX reach in tiles (1 = melee adjacency; 2 = e.g. a hand axe)
--   prefs.min_range: weapon MIN reach (default 1); 2 for a bow, which CANNOT hit an adjacent
--                    foe -- striking from range 1 leaves no Attack command, so the strike
--                    tile must sit at min_range..range, not 1..range.
--   Returns the best attackable enemy + the reachable tile to strike from, or nil if no
--   enemy sits within [min_range, range] of any reachable tile. Preference: the boss first,
--   then the lowest-HP enemy (likeliest kill).

local M = {}

local function manhattan(ax, ay, bx, by)
    return math.abs(ax - bx) + math.abs(ay - by)
end

-- A reachable tile from which `e` is within [minRange, range] (so a bow, minRange 2, won't
-- pick an adjacent tile it can't fire from), or nil.
local function attackTileFor(reachable, e, range, minRange)
    for _, t in ipairs(reachable) do
        local d = manhattan(t.x, t.y, e.x, e.y)
        if d >= minRange and d <= range then return t end
    end
    return nil
end

-- True if candidate c is a better target than the current best b.
local function preferred(c, b)
    if c.is_boss ~= b.is_boss then return c.is_boss end      -- boss beats non-boss
    return (c.hp or math.huge) < (b.hp or math.huge)         -- else lowest HP
end

function M.pickTarget(reachable, enemies, prefs)
    local range = (prefs and prefs.range) or 1
    local minRange = (prefs and prefs.min_range) or 1
    local best, bestTile
    for _, e in ipairs(enemies) do
        local tile = attackTileFor(reachable, e, range, minRange)
        if tile and (not best or preferred(e, best)) then
            best, bestTile = e, tile
        end
    end
    if best then return { target = best, tile = bestTile } end
    return nil
end

-- FE8 writes the UNIT INDEX into gBmMapUnit (bmmap.c RefreshUnitsOnBmMap): 1..0x7F for blue and
-- green, FACTION_RED + 1 (0x81) and up for red/purple. So a grid byte above FACTION_RED is a
-- hostile standing on that tile.
local FACTION_RED = 0x80

-- True when the engine's tile->unit GRID holds a hostile within [minRange, maxRange] of (x,y) --
-- i.e. when the engine would offer an Attack row to a unit standing there. `gridAt(x, y)` returns
-- the grid byte, or nil off-map.
--
-- Deliberately the grid and NOT the unit array (#204): RefreshUnitsOnBmMap SKIPS a red standing in
-- fog, writing it to gBmMapHidden instead, so the unit array can report ten live enemies while
-- gBmMapUnit holds none of them. A clear-bot that trusts the array then teleports "adjacent" to a
-- foe the engine cannot see, gets a command menu with no Attack row, and its blind row-0 press
-- opens ITEM -- Using a vulnerary at full HP, forever, with the enemy count never moving.
function M.gridHostileInReach(gridAt, x, y, minRange, maxRange)
    for dx = -maxRange, maxRange do
        local slack = maxRange - math.abs(dx)
        for dy = -slack, slack do
            local d = math.abs(dx) + math.abs(dy)
            if d >= minRange then
                local id = gridAt(x + dx, y + dy)
                if id and id > FACTION_RED then return true end
            end
        end
    end
    return false
end

local function tileKey(x, y) return x .. "," .. y end

-- Off-field sentinel: a tile the BFS never reached must score worse than ANY real
-- field distance. Real distances are bounded by map area (FE8 maps are < 65536
-- tiles); Manhattan by map perimeter -- both far under this.
local OFFFIELD = 1000000

-- pickMove(reachable, opts) -> {x,y} | nil -- the march decision when nothing is
-- attackable this turn (#60 last-mile breach). Pure, like pickTarget: the scenario
-- reads reachability/field/positions and owns the actual moving.
--   opts.field:   BFS distance field to the boss (pathing.lua); nil-tolerant
--   opts.cur:     the unit's current {x,y}
--   opts.goal:    the boss {x,y} (Manhattan fallback where the field has no value)
--   opts.blocked: set (keyed "x,y") of tiles claimed by OTHER friendly units this
--                 phase, so two marchers stop fighting over the same chokepoint tile
--   opts.enemies: live enemies -- cork pressure when the boss path is jammed
-- Decision: the unblocked reachable tile with the lowest field distance, Manhattan
-- tiebroken (keeps momentum on field plateaus). If that does NOT improve on the
-- unit's current field distance -- the walled-camp jam -- push toward the nearest
-- CORK enemy: one at least as boss-near as we are (fd(e) <= curFd). Stragglers
-- BEHIND the advance never trigger the fallback, so a follower whose best tile is
-- merely claimed by its leader holds the line instead of marching backward; among
-- equally-cork-near tiles the boss-nearest wins (no oscillation).
function M.pickMove(reachable, opts)
    opts = opts or {}
    local field, cur, goal = opts.field, opts.cur, opts.goal
    local blocked = opts.blocked or {}
    local enemies = opts.enemies or {}
    local function fd(x, y) return field and field[y] and field[y][x] end
    local function score(t)
        local m = goal and manhattan(t.x, t.y, goal.x, goal.y) or 0
        return (fd(t.x, t.y) or (OFFFIELD + m)) * 1000 + m
    end
    local best, bestScore
    for _, t in ipairs(reachable) do
        if not blocked[tileKey(t.x, t.y)] then
            local s = score(t)
            if not bestScore or s < bestScore then best, bestScore = t, s end
        end
    end
    if not best then return nil end
    -- a nil fd (unit/tile off the field, e.g. terrain-disconnected from the boss)
    -- counts as maximally far, so a fully-disconnected unit still gets the cork
    -- fallback rather than silently Manhattan-pressing against a wall
    local curFd = (cur and fd(cur.x, cur.y)) or OFFFIELD
    local bestFd = fd(best.x, best.y) or OFFFIELD
    if bestFd >= curFd and #enemies > 0 then
        local corks = {}
        for _, e in ipairs(enemies) do
            local efd = fd(e.x, e.y) or OFFFIELD
            if efd <= curFd then corks[#corks + 1] = e end
        end
        local eb, ebs
        for _, t in ipairs(reachable) do
            if not blocked[tileKey(t.x, t.y)] then
                local near = math.huge
                for _, e in ipairs(corks) do
                    near = math.min(near, manhattan(t.x, t.y, e.x, e.y))
                end
                if near < math.huge then
                    local s = near * (OFFFIELD * 1000) + score(t)
                    if not ebs or s < ebs then eb, ebs = t, s end
                end
            end
        end
        if eb then return eb end
    end
    return best
end

M.tileKey = tileKey

-- The stall watchdog's distance (#510 step 9): the nearest field distance to the target among
-- the units that could still be the one to finish -- on the field, and not ruled out.
--   units:    {slot, x, y, onField} tables
--   field:    field[y][x] = path steps to the target (the boss, or once it is dead the seize
--             tile), or nil
--   ruledOut: [slot] = true for a unit that stood on the seize tile with no legal Seize. It is
--             not the lord, and without this a non-lord parked beside the throne pins the
--             minimum while the lord's march -- the only progress left -- goes unseen.
-- Returns math.huge when nobody qualifies or there is no field.
function M.seizeDistance(units, field, ruledOut)
    local best = math.huge
    if not field then return best end
    for _, u in ipairs(units) do
        if u.onField and not (ruledOut and ruledOut[u.slot]) then
            local d = field[u.y] and field[u.y][u.x]
            if d and d < best then best = d end
        end
    end
    return best
end

-- A unit that has shown it cannot Seize (it stood on the tile; no Seize command) must not park
-- on or beside the throne: on a single-approach throne that body blocks the lord forever.
function M.needsToStepOff(cur, seize)
    return manhattan(cur.x, cur.y, seize.x, seize.y) <= 1
end

-- Where such a unit should Wait: of its reachable tiles, the one FARTHEST from the seize tile
-- (out of the approach, not merely off the tile), never on or beside it; ties go to the
-- shorter move. nil when every reachable tile is on or beside the throne.
function M.stepOffTile(reachable, cur, seize)
    local best, bestFar, bestMove
    for _, t in ipairs(reachable) do
        local far = manhattan(t.x, t.y, seize.x, seize.y)
        if far >= 2 then
            local move = manhattan(t.x, t.y, cur.x, cur.y)
            if not best or far > bestFar or (far == bestFar and move < bestMove) then
                best, bestFar, bestMove = t, far, move
            end
        end
    end
    return best
end

-- Did a turn make progress? Nearer the target, or fewer enemies. `last` holds the best
-- {dist, enemies, key} seen so far, `now` this turn's. `key` names WHAT the distance is
-- measured to and from (the target, and who is still a candidate): when it changes -- the boss
-- died, a unit was ruled out -- the old best distance belonged to another question, and the
-- change is itself progress. Without that, a non-lord's distance to the boss (4) stood as the
-- bar the lord's march to the throne (10, then 5) had to beat, and clear_ch01 read two turns
-- of marching as a stall.
function M.madeProgress(last, now)
    if last.key ~= now.key then return true end
    return now.dist < last.dist or now.enemies < last.enemies
end

return M
