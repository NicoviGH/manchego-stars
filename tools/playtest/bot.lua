-- bot.lua -- the bot's policy, PURE (#510 step 9; the greedy clear-bot core since #60).
--
-- No emulator: every input is a plain table, so tools/playtest/test_bot.lua runs it with a
-- fake `sight`. The bot plays the game and re-creates none of it: whether a tile is in danger,
-- what a fight does and what the chapter asks for are read from the game's memory by the
-- caller and handed in as `sight`. This file only chooses.
--
-- ── Bot.decide(board, sight, style) -> action | nil ────────────────────────────────────────
--   board: Board.read's shape (board.lua). Blue units on the field that have not acted are the
--          ones that can act; on-field reds are the enemies.
--   style: { aggression = "careful"|"even"|"bold"|"greedy", deploy = {charIds},
--            claims = {claim ids}, route = 1|2 }, plus the fields the claim behaviours add
--          (Claims, below). Bot.STYLES lists the sampled axes; "greedy" is not sampled -- it is
--          the clear scenarios' old bot and ignores `sight` except reach and the objective, and
--          every claim field but `deploy`.
--   sight: { danger(x, y) -> the game's danger zone at (x, y): 0 when no enemy reaches it,
--              else gBmMapRange's coverage (1 per tile an enemy could strike it from);
--            forecast(unit, target, x, y, slot) -> { hit, dmg, crit, hits, takenHit, takenDmg,
--              takenCrit, takenHits, counters, killsTarget, diesWorst }; taken* is what
--              `target` does to `unit` on (x, y) -- its counter when it can answer this
--              attack, else its own strike on its phase -- and counters == false says the
--              attack has no counter (nil reads as one; sight.lua's contract);
--            reach(unit) -> {{x,y}...}, the tiles the unit can move to this phase;
--            objective = { kind = "rout"|"boss"|"seize"|"defend"|"escape"|"survive",
--                          tile = {x,y}|nil, turnsLeft = n|nil, lord = charId|nil,
--                          ruledOut = {[slot] = true}|nil };
--            field(goal) -> dist|nil, OPTIONAL: pathing.distanceField's shape (dist[y][x] =
--              steps to `goal` over the map's passable tiles), built by the caller from the
--              game's terrain. A function of the goal because the bot chooses the goal (the
--              boss, the nearest enemy). Without it the march falls back to Manhattan, which
--              strands a unit against a wall (#60).
--            cache = {}|nil, OPTIONAL: a table the caller keeps for ONE player phase and
--              replaces at the next. Forecasts are kept in it across decide calls, keyed by
--              what FE8's forecast reads for that exchange: both fighters (id, HP, held item
--              and its uses), the strike tile, the enemy's tile, and every other unit within
--              support range (3, bmreliance.h) of either fighter. An action elsewhere on the
--              board leaves the entry standing. Reach and worst case are per call only.
--            terrain(x, y) -> FE8 terrain id, OPTIONAL: read from the game's map by the caller.
--              Only a terrain claim reads it; without it that claim is a no-op. }
--          Who may Seize is board.lua's Board.canSeize(unit, lord, ruledOut): `lord` is
--          Board.lordPid; without it, anyone not in the ruledOut memo may try.
--   Returns ONE action, for the unit that should act next, or nil when no unit can act (the
--   caller ends the phase): { unit = charId, unitId = id, move = {x,y},
--   act = "attack"|"wait"|"seize", target = charId|nil, targetId = id|nil, weapon = nil }.
--   `unitId`/`targetId` are Board's index byte: generics share a charId, the id is unique.
--   `weapon` is nil = the weapon the unit holds; the board knows the reach of that one only.
--   "talk", "visit" and "staff" are acts the claim behaviours add; nothing here emits them.
--
-- ONE forecast direction. `sight.forecast` is always OUR unit's attack on `target` from (x, y).
-- For the enemy phase the bot reads the taken* fields of the forecast our unit would get
-- against each threatening enemy -- forecast(ourUnit, enemy, x, y, nil) -- as what that enemy
-- does to us there. There is no enemy-side call.
--
-- Worst case on an end tile = the sum, over every enemy that reaches it, of that enemy's
-- takenDmg x takenHits, x3 when takenCrit > 0 (FE8 triples a crit: bmbattle.c
-- BattleGenerateHitAttributes); an enemy with takenHit 0 adds nothing. An enemy "reaches" the
-- tile when some tile of sight.reach(enemy) is within its weapon range of it; danger(x, y) = 0
-- skips the walk. The target of a SURE kill (killsTarget at hit >= 100) is left out: it is dead
-- before the enemy phase. Each style gates an action on it:
--   careful: no diesWorst, and the worst case < the unit's HP after its own attack's
--            worst-case counter (none for a sure kill on the first blow)
--   even:    no diesWorst, and no SINGLE enemy's worst case >= that same HP
--   bold:    no diesWorst (the exchange alone)
--   greedy:  nothing
-- None of these was chosen by a survival rate (ADR 0368).
--
-- Who acts: the lord seizes when it can reach the seize tile (the chapter ends there, so no
-- enemy phase follows and no gate applies); else the unit with an allowed sure kill; else a
-- claimed unit's move (a carry's attack, then a wall's attack or approach); else the unit
-- whose own tile has the largest worst case (more danger-zone coverage breaks a tie); else slot
-- order. Greedy keeps the old order: seize, then slot order.
--
-- What it does: attack when an allowed attack exists -- an answered class first, then a sure
-- kill, then the likeliest kill (the hit rate once per blow it needs), then the most expected
-- damage, then the boss, then the lowest HP -- else march toward the objective (its tile, the
-- boss, or the nearest enemy) over allowed tiles. With none allowed, or nothing to march to
-- (survive, or a reinforcements hold), it ends where the worst case is smallest, its own tile
-- first on a tie.
--
-- ── Claims: Bot.CLAIM_BEHAVIOURS[kind](claim, style) -> a NEW style (the given one is kept) ──
-- A claim reaches the bot RESOLVED by the runner, which reads the Strategy YAML (the kinds are
-- tools/strategy.py's): { id, kind, unit = {charIds}, vs = {classIds}|"boss"|"all",
-- tile = terrain id, turns = {arrival turns} }, each kind with the fields it uses. The bot
-- maps no name: every unit, class and turn must be an integer, and a claim missing a field
-- its kind needs, or holding a name, raises naming its id (one with no string id or kind
-- raises before dispatch).
--   carry {unit, vs}:   its units go AHEAD of style.deploy (deduped; Bot.prep fills its cap in
--                       that order, so a full sampled list never cuts them) and, ahead of
--                       the most-threatened rule, attack an enemy `vs` names when one can.
--   answer {unit, vs}:  those units rank an enemy `vs` names above every other target.
--   wall {unit, vs}:    ahead of the most-threatened rule a wall attacks an enemy `vs` names,
--                       else ends on its approach -- the allowed wait tile nearest that enemy
--                       among those it reaches -- else takes the normal pick. Every other unit
--                       marches only to tiles no nearer that enemy than the nearest wall (when
--                       any is left); its attacks are not held.
--   terrain {tile, vs}: the march keeps to allowed tiles of that terrain that an enemy `vs`
--                       names reaches, when any is in reach -- it holds the tile AGAINST them;
--                       a unit out of their reach marches on. Needs sight.terrain.
--   reinforcements {turns}: on the turn before any of `turns` the march holds (the no-goal
--                       rule above); attacks are still made. Reads board.turn (Board.read's),
--                       and decide raises when it is missing.
-- Bot.applyClaims(claims, style) folds them in order. Bot.unplayed(claims) -> the ids of every
-- claim whose kind has no behaviour (threat, kits, unmodelled, an unknown kind), so a run
-- reports what it did not play instead of dropping it.
--
-- The throne: a unit that cannot Seize never ends on the seize tile, nor on or beside it
-- (needsToStepOff) -- to wait or to attack -- unless its target stands ON the seize tile (the
-- boss on the throne is struck from its approach). A body there blocks a single-approach
-- throne for the lord.
--
-- ── Between chapters (ADR 0368): pure rules over plain tables the caller reads from memory ──
-- roster entry (a unit, slot order): { id, charId, level, forced = bool|nil,
--   ranks = {[weaponType] = rank number}, items = {{ id, type = weaponType|nil, rank,
--   kind = "vulnerary"|nil, promotes = bool|nil }...} }. `promotes` is set by the caller only
--   on a seal that promotes THIS unit; the bot never knows which seal fits which class.
-- stock entry: { item, price, type = weaponType|nil, rank, kind = "vulnerary"|nil }; the caller
--   says which stock item is the Vulnerary, so no item id lives here.
-- Bot.prep(roster, cap, style) -> { deploy = {charIds}, give = {} }: forced units (slot order),
--   then style.deploy (listed order; a charId not in the roster is skipped, a repeat counts
--   once), then the highest level (ties by slot order), up to `cap`. Forced units all go even
--   when they alone exceed the cap. No transfer rule is decided yet, so `give` is always empty.
-- Bot.shop(gold, stock, party) -> {{ item, qty }...}: party is the deployed roster entries, in
--   deploy order. One Vulnerary (the cheapest) per unit holding none first, then for each unit
--   and each weapon type it has a rank in (type names in order) it holds none of, the cheapest
--   stock weapon of that type at or under its rank. A purchase gold cannot cover is skipped and the
--   later ones are still tried.
-- Bot.promote(unit, items) -> bool: level 10 or above and a promoting seal held.
-- Bot.promoteOrder(units) -> units, highest level first (ties by slot order): the order a
--   caller spends seals in.
-- Bot.route(options, style) -> style.route, validated as an index into options.
--
-- ── The greedy core (the clear scenarios drive these directly) ─────────────────────────────
-- pickTarget(reachable, enemies, prefs) -> { target = <enemy>, tile = {x,y} } | nil
--   reachable: list of {x,y} tiles the unit can move to this turn (its own tile included)
--   enemies:   list of {x,y,hp,is_boss}
--   prefs.range:     weapon MAX reach in tiles (1 = melee adjacency; 2 = e.g. a hand axe)
--   prefs.min_range: weapon MIN reach (default 1); 2 for a bow, which CANNOT hit an adjacent
--                    foe -- striking from range 1 leaves no Attack command, so the strike
--                    tile must sit at min_range..range, not 1..range.
--   prefs.tilesFor:  optional function(enemy) -> tiles, the strike tiles for THAT enemy in
--                    place of `reachable` (decide's throne rule); absent = `reachable`.
--   Returns the best attackable enemy + the reachable tile to strike from, or nil if no
--   enemy sits within [min_range, range] of any reachable tile. Preference: the boss first,
--   then the lowest-HP enemy (likeliest kill).

local M = {}

-- board.lua is pure too. In a run the wrapper's PLAYTEST_DIR names this directory (run.sh);
-- under plain `lua` (test_bot.lua) it is read off this chunk's own path.
local Board = dofile(PLAYTEST_DIR and (PLAYTEST_DIR .. "/board.lua")
    or ((debug.getinfo(1, "S").source:match("^@(.*/)") or "./") .. "board.lua"))

local function manhattan(ax, ay, bx, by)
    return math.abs(ax - bx) + math.abs(ay - by)
end

local function inRange(ax, ay, bx, by, minRange, maxRange)
    local d = manhattan(ax, ay, bx, by)
    return d >= minRange and d <= maxRange
end

-- A reachable tile from which `e` is within [minRange, range] (so a bow, minRange 2, won't
-- pick an adjacent tile it can't fire from), or nil.
local function attackTileFor(reachable, e, range, minRange)
    for _, t in ipairs(reachable) do
        if inRange(t.x, t.y, e.x, e.y, minRange, range) then return t end
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
        local from = prefs and prefs.tilesFor and prefs.tilesFor(e) or reachable
        local tile = attackTileFor(from, e, range, minRange)
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

-- ── Bot.decide ─────────────────────────────────────────────────────────────────────────────

-- The axes a run's style is sampled on. aggression is a closed set; deploy and claims are
-- lists the runner fills per run, empty until it does.
M.STYLES = {
    aggression = { "careful", "even", "bold" },
    deploy = {},   -- charIds the runner chooses to field
    claims = {},   -- Strategy claim ids the run follows
    route = { 1, 2 },   -- which of a chapter's two routes (1-based) the run takes
}

local CRIT_MULTIPLIER = 3   -- bmbattle.c: gBattleStats.damage * 3 on a critical hit
local SURE_HIT = 100

local SUPPORT_RANGE = 3     -- bmreliance.h SUPPORT_BONUSES_MAX_DISTANCE, RECT_DISTANCE (Manhattan)

local function isSureKill(f) return f.killsTarget and f.hit >= SURE_HIT end

-- An exchange's worst case for our unit: the taken side's damage x hits, x3 on a crit.
local function takenWorst(f)
    if (f.takenHit or 0) <= 0 then return 0 end
    local crit = (f.takenCrit or 0) > 0 and CRIT_MULTIPLIER or 1
    return f.takenDmg * f.takenHits * crit
end

-- The chance that the attack kills: the hit rate once per blow the kill needs, crits not
-- counted. A doubling attack that needs both blows is hit^2, not hit. Kept as an exact integer
-- over a fixed 100^MAX_BLOWS (hit^n x 100^(MAX_BLOWS-n)), so equal chances compare equal: as a
-- float, 4% once and 20% twice differed in the last bit and the tie went to whichever rounded up.
local MAX_BLOWS = 4     -- a brave weapon doubling: 2 rounds x 2 strikes
local function killChance(f, e)
    if not f.killsTarget or f.dmg <= 0 then return 0 end
    local need = (e.hp + f.dmg - 1) // f.dmg
    -- more blows than any exchange lands: the forecast's kill needs a crit, which is not counted
    if need > MAX_BLOWS then return 0 end
    local chance = 1
    for i = 1, MAX_BLOWS do chance = chance * (i <= need and f.hit or 100) end
    return chance
end

local function unitKey(u)
    local held = u.items and u.items[1]          -- items[1] is FE8's equipped slot
    return table.concat({ u.id, u.hp, held and held.id or "-", held and held.uses or "-" }, ":")
end

-- One decide call's view: the board split by role, and memos so a forecast or a reach the
-- caller pays for (an emulator round trip, in the ROM) is asked for once per call.
local function context(board, sight)
    local cache = sight.cache or {}
    cache.forecasts = cache.forecasts or {}
    local ctx = { sight = sight, actors = {}, enemies = {}, blues = {}, standing = {},
                  onField = {}, forecasts = cache.forecasts, reaches = {}, worsts = {},
                  fields = {}, options = {} }
    local o = sight.objective
    if o and o.kind == "seize" and o.tile then ctx.seizeTile = o.tile end
    for _, u in ipairs(board.units) do
        if u.onField then
            ctx.onField[#ctx.onField + 1] = u
            ctx.standing[tileKey(u.x, u.y)] = u
            if u.faction == "blue" then ctx.blues[#ctx.blues + 1] = u end
            if u.faction == "blue" and not u.acted then ctx.actors[#ctx.actors + 1] = u end
            if u.faction == "red" then ctx.enemies[#ctx.enemies + 1] = u end
        end
    end
    table.sort(ctx.actors, function(a, b) return a.slot < b.slot end)
    return ctx
end

-- A forecast's key: what FE8's forecast reads for this exchange -- both fighters (id, HP, held
-- item and its uses), the strike tile, the enemy's tile, and every other unit within support
-- range of either fighter (support bonuses move with them). An action elsewhere on the board
-- leaves it standing, so a phase's cache keeps paying across decide calls.
local function forecastKey(ctx, u, e, x, y)
    local parts = { unitKey(u), x, y, unitKey(e), e.x, e.y, "held" }
    for _, o in ipairs(ctx.onField) do
        if o ~= u and o ~= e and (manhattan(o.x, o.y, x, y) <= SUPPORT_RANGE
                or manhattan(o.x, o.y, e.x, e.y) <= SUPPORT_RANGE) then
            parts[#parts + 1] = o.id .. "@" .. tileKey(o.x, o.y)
        end
    end
    return table.concat(parts, ";")
end

local function forecast(ctx, u, e, x, y)
    local k = forecastKey(ctx, u, e, x, y)
    local f = ctx.forecasts[k]
    if not f then
        f = ctx.sight.forecast(u, e, x, y, nil)
        ctx.forecasts[k] = f
    end
    return f
end

-- sight.reach, with the unit's own tile always in it (attacking or waiting where it stands).
local function reachOf(ctx, u)
    local r = ctx.reaches[u.id]
    if r then return r end
    r = {}
    local own = false
    for _, t in ipairs(ctx.sight.reach(u) or {}) do
        r[#r + 1] = t
        if t.x == u.x and t.y == u.y then own = true end
    end
    if not own then r[#r + 1] = { x = u.x, y = u.y } end
    ctx.reaches[u.id] = r
    return r
end

local function canSeize(ctx, u)
    local o = ctx.sight.objective
    return Board.canSeize(u, o.lord, o.ruledOut)
end

-- The tiles `u` can end on: its reach, less every tile another unit stands on, and less the
-- seize tile for a unit that cannot Seize there -- unless it already stands on it: its own
-- tile is always left, so a unit boxed in on the throne still has somewhere to wait.
local function endTiles(ctx, u)
    local s = ctx.seizeTile
    local barred = s and not canSeize(ctx, u)
    local out = {}
    for _, t in ipairs(reachOf(ctx, u)) do
        local there = ctx.standing[tileKey(t.x, t.y)]
        local own = t.x == u.x and t.y == u.y
        if (not there or there == u) and (own or not (barred and t.x == s.x and t.y == s.y)) then
            out[#out + 1] = t
        end
    end
    return out
end

-- Where `u` may Wait: its end tiles, and for a unit that cannot Seize none on or beside the
-- seize tile (needsToStepOff) while any other is left -- it aims at the throne, it does not
-- stand in the lord's way to it.
local function waitTiles(ctx, u)
    local tiles, s = endTiles(ctx, u), ctx.seizeTile
    if not s or canSeize(ctx, u) then return tiles end
    local clear = {}
    for _, t in ipairs(tiles) do
        if not M.needsToStepOff(t, s) then clear[#clear + 1] = t end
    end
    return #clear > 0 and clear or tiles
end

-- The tiles `u` may strike `e` from: anywhere it may end when `e` stands on the seize tile
-- (the boss on the throne is reached from its approach), else only where it may wait.
local function strikeTiles(ctx, u, e)
    local s = ctx.seizeTile
    if s and e.x == s.x and e.y == s.y then return endTiles(ctx, u) end
    return waitTiles(ctx, u)
end

-- sight.field for `goal`, asked once per goal per call; nil when the caller has none.
local function fieldFor(ctx, goal)
    if not (goal and ctx.sight.field) then return nil end
    local k = tileKey(goal.x, goal.y)
    if ctx.fields[k] == nil then ctx.fields[k] = ctx.sight.field(goal) or false end
    return ctx.fields[k] or nil
end

local function reaches(ctx, e, x, y)
    if not e.minRange then return false end
    for _, r in ipairs(reachOf(ctx, e)) do
        if inRange(r.x, r.y, x, y, e.minRange, e.maxRange) then return true end
    end
    return false
end

local function listed(list, v)
    for _, x in ipairs(list) do
        if x == v then return true end
    end
    return false
end

-- A resolved claim's `vs` against an enemy on the board.
local function matchesVs(vs, e)
    if vs == "all" then return true end
    if vs == "boss" then return e.isBoss end
    return listed(vs, e.classId)
end

-- The nearest enemy `vs` names that reaches (x, y), and its distance; nil when none does.
-- A wall's approach and a terrain claim's hold are both "a tile those enemies reach".
local function nearestReaching(ctx, vs, x, y)
    local best, bestD
    for _, e in ipairs(ctx.enemies) do
        local d = manhattan(x, y, e.x, e.y)
        if matchesVs(vs, e) and (not bestD or d < bestD) and reaches(ctx, e, x, y) then
            best, bestD = e, d
        end
    end
    return best, bestD
end

-- The style's claim entries in `field` that name `u` (a carry, answer or wall's units).
local function claimsOn(ctx, field, u)
    local out = {}
    for _, c in ipairs(ctx.style[field] or {}) do
        if listed(c.units, u.charId) then out[#out + 1] = c end
    end
    return out
end

-- The enemy phase's worst case for `u` ending on (x, y): {sum, max} of each reaching enemy's
-- damage, `spared` (a sure kill's target) left out.
local function worstCase(ctx, u, x, y, spared)
    local k = u.id .. "@" .. tileKey(x, y) .. "-" .. (spared and spared.id or "")
    local w = ctx.worsts[k]
    if w then return w end
    w = { sum = 0, max = 0 }
    if ctx.sight.danger(x, y) > 0 then
        for _, e in ipairs(ctx.enemies) do
            if e ~= spared and reaches(ctx, e, x, y) then
                local dmg = takenWorst(forecast(ctx, u, e, x, y))
                w.sum, w.max = w.sum + dmg, math.max(w.max, dmg)
            end
        end
    end
    ctx.worsts[k] = w
    return w
end

-- What our own attack's counter can take before the enemy phase: its worst case, nothing when
-- the target cannot answer this attack (counters == false) or the first blow is a sure kill
-- (the target is dead before it can answer).
local function counterWorst(f, e)
    if f.counters == false then return 0 end
    if f.hit >= SURE_HIT and f.dmg >= e.hp then return 0 end
    return takenWorst(f)
end

-- Whether a style lets `u` end its move on (x, y), `spared` left out of the worst case and
-- `spent` (the attack's own counter, counterWorst) already off its HP. An attack whose
-- forecast says diesWorst is refused before any gate is asked (every style but greedy).
-- bold's gate never weighs the enemy phase, so it asks for no forecast to do so.
local GATES = {
    careful = function(ctx, u, x, y, spared, spent)
        return worstCase(ctx, u, x, y, spared).sum < u.hp - (spent or 0)
    end,
    even = function(ctx, u, x, y, spared, spent)
        return worstCase(ctx, u, x, y, spared).max < u.hp - (spent or 0)
    end,
    bold = function() return true end,
}

local function action(u, tile, act, target)
    return { unit = u.charId, unitId = u.id, move = { x = tile.x, y = tile.y }, act = act,
             target = target and target.charId, targetId = target and target.id, weapon = nil }
end

-- True if attack candidate c beats b: an answered class, sure kill, kill chance, expected
-- damage, boss, low HP.
local function betterAttack(c, b)
    if c.answered ~= b.answered then return c.answered end
    if c.sure ~= b.sure then return c.sure end
    if c.killChance ~= b.killChance then return c.killChance > b.killChance end
    if c.expected ~= b.expected then return c.expected > b.expected end
    if c.target.isBoss ~= b.target.isBoss then return c.target.isBoss end
    return c.target.hp < b.target.hp
end

-- Every attack the gate allows `u` this call, worked out once (decide's pass and a claim's
-- filtered pass read the same list).
local function attackOptions(ctx, u, gate)
    local opts = ctx.options[u]
    if opts then return opts end
    opts = {}
    local answers = claimsOn(ctx, "answers", u)
    for _, e in ipairs(u.minRange and ctx.enemies or {}) do
        local answered = false
        for _, c in ipairs(answers) do
            if matchesVs(c.vs, e) then answered = true end
        end
        for _, t in ipairs(strikeTiles(ctx, u, e)) do
            if inRange(t.x, t.y, e.x, e.y, u.minRange, u.maxRange) then
                local f = forecast(ctx, u, e, t.x, t.y)
                local sure = isSureKill(f)
                if not f.diesWorst and gate(ctx, u, t.x, t.y, sure and e or nil,
                                            counterWorst(f, e)) then
                    opts[#opts + 1] = { tile = t, target = e, sure = sure, answered = answered,
                                        killChance = killChance(f, e),
                                        expected = f.dmg * f.hits * f.hit }
                end
            end
        end
    end
    ctx.options[u] = opts
    return opts
end

-- `only`, a resolved `vs`, limits the targets to that enemy (a carry's or a wall's).
local function bestAttack(ctx, u, gate, only)
    local best
    for _, c in ipairs(attackOptions(ctx, u, gate)) do
        if (not only or matchesVs(only, c.target)) and (not best or betterAttack(c, best)) then
            best = c
        end
    end
    return best
end

-- Where the march heads: the objective's tile, the boss, or the nearest enemy; nil = hold.
local function goalFor(ctx, u, objective)
    local kind = objective and objective.kind
    if objective and objective.tile then return objective.tile end
    if kind == "survive" then return nil end
    local best, bestD
    for _, e in ipairs(ctx.enemies) do
        local d = manhattan(u.x, u.y, e.x, e.y)
        if kind == "boss" and e.isBoss then return e end
        if not bestD or d < bestD then best, bestD = e, d end
    end
    return best
end

-- A wall's line: of `tiles`, those no nearer any walled enemy than the nearest of that claim's
-- walls on the field. A unit that is itself one of the claim's walls is not held by it. When
-- no tile is behind the line the unit is not held (it is already past it).
local function behindWalls(ctx, u, tiles)
    local kept = tiles
    for _, c in ipairs(ctx.style.walls or {}) do
        if not listed(c.units, u.charId) then
            for _, e in ipairs(ctx.enemies) do
                local line
                for _, w in ipairs(matchesVs(c.vs, e) and ctx.blues or {}) do
                    local d = manhattan(w.x, w.y, e.x, e.y)
                    if listed(c.units, w.charId) and (not line or d < line) then line = d end
                end
                if line then
                    local behind = {}
                    for _, t in ipairs(kept) do
                        if manhattan(t.x, t.y, e.x, e.y) >= line then behind[#behind + 1] = t end
                    end
                    kept = behind
                end
            end
        end
    end
    return #kept > 0 and kept or tiles
end

-- A terrain claim holds that tile AGAINST its enemies: of the allowed `tiles`, those of the
-- first claimed terrain that an enemy `vs` names reaches; all of them when there are none, so
-- a unit out of those enemies' reach marches on. Without sight.terrain this is a no-op: the
-- bot never guesses a tile's terrain.
local function onTerrain(ctx, tiles)
    local terrainAt = ctx.sight.terrain
    if not terrainAt then return tiles end
    for _, c in ipairs(ctx.style.terrains or {}) do
        local on = {}
        for _, t in ipairs(tiles) do
            if terrainAt(t.x, t.y) == c.tile and nearestReaching(ctx, c.vs, t.x, t.y) then
                on[#on + 1] = t
            end
        end
        if #on > 0 then return on end
    end
    return tiles
end

-- A reinforcements claim: the turn before any cited arrival, the march holds. The turn is
-- board.turn (decide has checked it is there).
local function holding(ctx)
    for _, turns in ipairs(ctx.style.arrivals or {}) do
        for _, t in ipairs(turns) do
            if ctx.turn == t - 1 then return true end
        end
    end
    return false
end

local function march(ctx, u, gate, objective)
    local tiles, allowed = behindWalls(ctx, u, waitTiles(ctx, u)), {}
    for _, t in ipairs(tiles) do
        if gate(ctx, u, t.x, t.y, nil) then allowed[#allowed + 1] = t end
    end
    allowed = onTerrain(ctx, allowed)
    local goal = nil
    if not holding(ctx) then goal = goalFor(ctx, u, objective) end
    if #allowed == 0 or not goal then
        -- nowhere is safe enough, or nothing to march to (or a hold): end where the worst
        -- case is smallest, the unit's own tile first on a tie (holding costs nothing)
        local pool = #allowed > 0 and allowed or tiles
        local best, bestSum = nil, nil
        for _, t in ipairs(pool) do
            local s = worstCase(ctx, u, t.x, t.y, nil).sum
            local own = t.x == u.x and t.y == u.y
            if not bestSum or s < bestSum or (s == bestSum and own) then best, bestSum = t, s end
        end
        return best
    end
    -- no enemies passed: pickMove's cork fallback pushes at a foe when the march is jammed,
    -- and over tiles the style allowed that push is the greedy bot's charge, not this one's
    return M.pickMove(allowed, { cur = u, goal = goal, field = fieldFor(ctx, goal) })
end

-- A wall's approach: of the wait tiles the gate allows, one a walled enemy reaches, the
-- nearest that enemy; nil when there is none (then the wall takes the normal pick).
local function approach(ctx, u, gate, vs)
    local best, bestD
    for _, t in ipairs(waitTiles(ctx, u)) do
        if gate(ctx, u, t.x, t.y, nil) then
            local e, d = nearestReaching(ctx, vs, t.x, t.y)
            if e and (not bestD or d < bestD) then best, bestD = t, d end
        end
    end
    return best
end

-- The claimed units' move, before the most-threatened rule: a carry's units attack the
-- carried enemy, then a wall's attack the walled enemy or stand on its approach. Claim order,
-- then slot order; nil when no claimed unit has such a move.
local function claimedMove(ctx, gate)
    for _, field in ipairs({ "carries", "walls" }) do
        for _, c in ipairs(ctx.style[field] or {}) do
            for _, u in ipairs(ctx.actors) do
                if listed(c.units, u.charId) then
                    local a = bestAttack(ctx, u, gate, c.vs)
                    if a then return action(u, a.tile, "attack", a.target) end
                    local t = field == "walls" and approach(ctx, u, gate, c.vs)
                    if t then return action(u, t, "wait") end
                end
            end
        end
    end
    return nil
end

local function seize(ctx)
    local s = ctx.seizeTile
    if not s then return nil end
    for _, u in ipairs(ctx.actors) do
        if canSeize(ctx, u) then
            for _, t in ipairs(endTiles(ctx, u)) do
                if t.x == s.x and t.y == s.y then return action(u, t, "seize") end
            end
        end
    end
    return nil
end

-- The old clear-bot through decide: the first unit in slot order, pickTarget's pick, else
-- pickMove toward the goal over sight.field when there is one. With no field pickMove's cork
-- rule sends it at the nearest enemy, which is the charge the greedy bot has always made.
local function greedy(ctx, objective)
    local u = ctx.actors[1]
    local targets = {}
    for _, e in ipairs(ctx.enemies) do
        targets[#targets + 1] = { x = e.x, y = e.y, hp = e.hp, is_boss = e.isBoss, unit = e }
    end
    -- tilesFor gives the strike tiles per target, so no shared reach is passed
    local pick = u.minRange and M.pickTarget(nil, targets,
        { range = u.maxRange, min_range = u.minRange,
          tilesFor = function(t) return strikeTiles(ctx, u, t.unit) end })
    if pick then return action(u, pick.tile, "attack", pick.target.unit) end
    local goal = goalFor(ctx, u, objective)
    local tile = M.pickMove(waitTiles(ctx, u), { cur = u, goal = goal,
                                                 field = fieldFor(ctx, goal), enemies = targets })
    return action(u, tile, "wait")
end

function M.decide(board, sight, style)
    local aggression = style and style.aggression
    local gate = GATES[aggression]
    if not gate and aggression ~= "greedy" then
        error("bot.lua: unknown aggression " .. tostring(aggression))
    end
    local arrivals = style.arrivals
    if arrivals and #arrivals > 0 and board.turn == nil then
        error("bot.lua: a reinforcements claim needs board.turn")
    end
    local ctx = context(board, sight)
    ctx.style, ctx.turn = style, board.turn
    if #ctx.actors == 0 then return nil end
    local objective = sight.objective
    local s = seize(ctx)
    if s then return s end
    if not gate then return greedy(ctx, objective) end

    local attacks = {}
    for _, u in ipairs(ctx.actors) do
        local a = bestAttack(ctx, u, gate)
        attacks[u] = a
        if a and a.sure then return action(u, a.tile, "attack", a.target) end
    end
    local claimed = claimedMove(ctx, gate)
    if claimed then return claimed end
    -- the most threatened: the largest worst case where it stands, then the most coverage
    local u, most, count = ctx.actors[1], 0, 0
    for _, c in ipairs(ctx.actors) do
        local w, d = worstCase(ctx, c, c.x, c.y, nil).sum, sight.danger(c.x, c.y)
        if w > most or (w == most and d > count) then u, most, count = c, w, d end
    end
    local a = attacks[u]
    if a then return action(u, a.tile, "attack", a.target) end
    return action(u, march(ctx, u, gate, objective), "wait")
end

-- ── Claims ───────────────────────────────────────────────────────────────────────────────

local function malformed(claim, what)
    error("bot.lua: claim " .. tostring(claim.id) .. " (" .. tostring(claim.kind) .. ") "
        .. what, 3)
end

local function isInteger(v) return type(v) == "number" and v % 1 == 0 end

-- A claim reaches the bot resolved: every unit, class and turn is an integer id. A name left
-- in (unit = {"some-name"}, turns = {"3"}) would never match anything, silently.
local function needIds(claim, field, what)
    local v = claim[field]
    local ok = type(v) == "table" and #v > 0
    for _, x in ipairs(ok and v or {}) do
        if not isInteger(x) then ok = false end
    end
    if not ok then malformed(claim, "needs " .. field .. " = " .. what) end
    return v
end

local function needVs(claim)
    local vs = claim.vs
    if vs == "boss" or vs == "all" then return vs end
    return needIds(claim, "vs", '{classIds}, "boss" or "all"')
end

-- Before any dispatch: a claim with no id could not be reported, one with no kind not played.
local function needClaim(claim)
    if type(claim.id) ~= "string" or type(claim.kind) ~= "string" then
        error("bot.lua: a claim needs a string id and kind (got id " .. tostring(claim.id)
            .. ", kind " .. tostring(claim.kind) .. ")", 3)
    end
    return claim
end

local function copyList(list)
    local out = {}
    for i, v in ipairs(list or {}) do out[i] = v end
    return out
end

-- A copy of `style` with `entry` appended to its list `field`; the given style is not edited
-- (the runner samples one style and may apply claims to it more than once).
local function withEntry(style, field, entry)
    local out = {}
    for k, v in pairs(style) do out[k] = v end
    out[field] = copyList(style[field])
    out[field][#out[field] + 1] = entry
    return out
end

local function byUnit(field)
    return function(claim, style)
        return withEntry(style, field, { units = needIds(claim, "unit", "{charIds}"),
                                         vs = needVs(claim) })
    end
end

M.CLAIM_BEHAVIOURS = {
    -- the carried units go AHEAD of the sampled deploy: Bot.prep fills the cap in list order,
    -- so appended they were cut whenever the sampled list already filled it
    carry = function(claim, style)
        local out = byUnit("carries")(claim, style)
        local deploy = copyList(claim.unit)
        for _, c in ipairs(style.deploy or {}) do
            if not listed(deploy, c) then deploy[#deploy + 1] = c end
        end
        out.deploy = deploy
        return out
    end,
    answer = byUnit("answers"),
    wall = byUnit("walls"),
    terrain = function(claim, style)
        if not isInteger(claim.tile) then malformed(claim, "needs tile = a terrain id") end
        return withEntry(style, "terrains", { tile = claim.tile, vs = needVs(claim) })
    end,
    reinforcements = function(claim, style)
        return withEntry(style, "arrivals", needIds(claim, "turns", "{arrival turns}"))
    end,
}

function M.applyClaims(claims, style)
    for _, c in ipairs(claims) do
        local behaviour = M.CLAIM_BEHAVIOURS[needClaim(c).kind]
        if behaviour then style = behaviour(c, style) end
    end
    return style
end

function M.unplayed(claims)
    local ids = {}
    for _, c in ipairs(claims) do
        if not M.CLAIM_BEHAVIOURS[needClaim(c).kind] then ids[#ids + 1] = c.id end
    end
    return ids
end

-- ── Between chapters ─────────────────────────────────────────────────────────────────────

local PROMOTE_LEVEL = 10   -- FE8: a unit may use a promotion item from level 10

-- Slot order is roster order; table.sort is not stable, so order carries its index.
local function byLevel(units)
    local order = {}
    for i, u in ipairs(units) do order[i] = { u = u, i = i } end
    table.sort(order, function(a, b)
        if a.u.level ~= b.u.level then return a.u.level > b.u.level end
        return a.i < b.i
    end)
    local out = {}
    for i, o in ipairs(order) do out[i] = o.u end
    return out
end

function M.prep(roster, cap, style)
    local deploy, taken = {}, {}
    local function take(u)
        if taken[u] then return end
        taken[u] = true
        deploy[#deploy + 1] = u.charId
    end
    for _, u in ipairs(roster) do
        if u.forced then take(u) end
    end
    for _, charId in ipairs(style.deploy or {}) do
        for _, u in ipairs(roster) do
            if u.charId == charId and #deploy < cap then take(u) break end
        end
    end
    for _, u in ipairs(byLevel(roster)) do
        if #deploy >= cap then break end
        take(u)
    end
    return { deploy = deploy, give = {} }
end

local function cheapest(stock, want)
    local best
    for _, s in ipairs(stock) do
        if want(s) and (not best or s.price < best.price) then best = s end
    end
    return best
end

local function holdsAny(u, want)
    for _, it in ipairs(u.items) do
        if want(it) then return true end
    end
    return false
end

function M.shop(gold, stock, party)
    local bought, order = {}, {}
    local function buy(s)
        if not s or s.price > gold then return end
        gold = gold - s.price
        if not bought[s.item] then bought[s.item] = 0; order[#order + 1] = s.item end
        bought[s.item] = bought[s.item] + 1
    end
    local vuln = cheapest(stock, function(s) return s.kind == "vulnerary" end)
    for _, u in ipairs(party) do
        if not holdsAny(u, function(it) return it.kind == "vulnerary" end) then buy(vuln) end
    end
    for _, u in ipairs(party) do
        local types = {}
        for t in pairs(u.ranks) do types[#types + 1] = t end
        table.sort(types)
        for _, t in ipairs(types) do
            if not holdsAny(u, function(it) return it.type == t end) then
                buy(cheapest(stock, function(s)
                    return s.type == t and s.rank <= u.ranks[t]
                end))
            end
        end
    end
    local out = {}
    for _, item in ipairs(order) do out[#out + 1] = { item = item, qty = bought[item] } end
    return out
end

function M.promote(unit, items)
    if unit.level < PROMOTE_LEVEL then return false end
    for _, it in ipairs(items) do
        if it.promotes then return true end
    end
    return false
end

function M.promoteOrder(units) return byLevel(units) end

function M.route(options, style)
    local r = style.route
    if type(r) ~= "number" or r < 1 or r > #options or r % 1 ~= 0 then
        error("bot.lua: route " .. tostring(r) .. " is not an index into " .. #options
            .. " options")
    end
    return r
end

return M
