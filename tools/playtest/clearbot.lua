-- clearbot.lua -- pure target-selection for the greedy clear-bot (#60, no emulator).
--
-- The decision core, split from the emulator driving so it is unit-tested without mGBA
-- (tools/playtest/test_clearbot.lua). The clear scenario reads real reachability + enemy
-- state into plain tables and asks pickTarget what to hit; it owns the actual moving/
-- attacking. Boss-ness is passed in as data (is_boss), computed by the scenario from the
-- CA_BOSS character attribute -- so this stays a pure function over positions/hp.
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

local function tileKey(x, y) return x .. "," .. y end

-- pickMove(reachable, opts) -> {x,y} | nil -- the march decision when nothing is
-- attackable this turn (#60 last-mile breach). Pure, like pickTarget: the scenario
-- reads reachability/field/positions and owns the actual moving.
--   opts.field:   BFS distance field to the boss (pathing.lua); nil-tolerant
--   opts.cur:     the unit's current {x,y}
--   opts.goal:    the boss {x,y} (Manhattan fallback where the field has no value)
--   opts.blocked: set (keyed "x,y") of tiles claimed by OTHER friendly units this
--                 phase, so two marchers stop fighting over the same chokepoint tile
--   opts.enemies: live enemies -- straggler pressure when the boss path is jammed
-- Decision: the unblocked reachable tile with the lowest field distance, Manhattan
-- tiebroken (keeps momentum on field plateaus). If the best tile does NOT improve
-- on the unit's current field distance -- the walled-camp jam: a chokepoint or a
-- friendly/enemy cork means no reachable tile gets nearer the boss -- push toward
-- the nearest live enemy instead (kill the cork, unjam next turn).
function M.pickMove(reachable, opts)
    opts = opts or {}
    local field, cur, goal = opts.field, opts.cur, opts.goal
    local blocked = opts.blocked or {}
    local enemies = opts.enemies or {}
    local function fd(x, y) return field and field[y] and field[y][x] end
    local best, bestScore
    for _, t in ipairs(reachable) do
        if not blocked[tileKey(t.x, t.y)] then
            local m = goal and manhattan(t.x, t.y, goal.x, goal.y) or 0
            local f = fd(t.x, t.y)
            local score = (f or (1000 + m)) * 1000 + m
            if not bestScore or score < bestScore then best, bestScore = t, score end
        end
    end
    if not best then return nil end
    local curFd = cur and fd(cur.x, cur.y)
    local bestFd = fd(best.x, best.y)
    if curFd and bestFd and bestFd >= curFd and #enemies > 0 then
        local eb, ebs
        for _, t in ipairs(reachable) do
            if not blocked[tileKey(t.x, t.y)] then
                local near = math.huge
                for _, e in ipairs(enemies) do
                    near = math.min(near, manhattan(t.x, t.y, e.x, e.y))
                end
                if not ebs or near < ebs then eb, ebs = t, near end
            end
        end
        if eb then return eb end
    end
    return best
end

M.tileKey = tileKey

return M
