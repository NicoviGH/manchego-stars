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
--            claims = {claim ids}, route = 1|2 }. Bot.STYLES lists the sampled aggressions; "greedy" is not
--          sampled -- it is the clear scenarios' old bot and ignores `sight` except reach and
--          the objective.
--   sight: { danger(x, y) -> how many enemies reach (x, y), the game's danger zone;
--            forecast(unit, target, x, y, slot) -> { hit, dmg, crit, hits, takenHit, takenDmg,
--              takenCrit, takenHits, killsTarget, diesWorst };
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
--              the BOARD SIGNATURE (every unit's id, tile, HP and held item with its uses)
--              plus the exchange (attacker, target, strike tile, weapon slot). FE8's forecast
--              reads more than the pair: support bonuses from allies in range, and the held
--              weapon. So a hit is only ever the same board asked again (a re-decide after a
--              cancelled input); any action that moves, hurts or spends a weapon misses.
--              Reach and worst case are per call only. }
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
--   careful: no diesWorst, and the worst case < the unit's current HP
--   even:    no diesWorst, and no SINGLE enemy's worst case >= the unit's current HP
--   bold:    no diesWorst (the exchange alone)
--   greedy:  nothing
-- None of these was chosen by a survival rate (ADR 0368).
--
-- Who acts: the lord seizes when it can reach the seize tile (the chapter ends there, so no
-- enemy phase follows and no gate applies); else the unit with an allowed sure kill; else the
-- unit whose own tile has the largest worst case (more reaching enemies breaks a tie); else
-- slot order. Greedy keeps the old order: seize, then slot order.
--
-- What it does: attack when an allowed attack exists -- a sure kill first, then the likeliest
-- kill, then the most expected damage, then the boss, then the lowest HP -- else march toward
-- the objective (its tile, the boss, or the nearest enemy) over allowed tiles. With none
-- allowed, or nothing to march to (survive), it ends where the worst case is smallest, its own
-- tile first on a tie.
--
-- The throne: a unit that cannot Seize never ends on the seize tile, nor on or beside it
-- (needsToStepOff) -- to wait or to attack -- unless its target stands ON the seize tile (the
-- boss on the throne is struck from its approach). A body there blocks a single-approach
-- throne for the lord.
--
-- ── Between chapters (ADR 0368): pure rules over plain tables the caller reads from memory ──
-- roster entry (a unit, slot order): { id, charId, level, forced = bool|nil,
--   ranks = {[weaponType] = rank number}, items = {{ id, type = weaponType|nil, rank,
--   promotes = bool|nil }...} }. `promotes` is set by the caller only on a seal that promotes
--   THIS unit; the bot never knows which seal fits which class.
-- stock entry: { item, price, type = weaponType|nil, rank, kind = "vulnerary"|nil }; the caller
--   says which stock item is the Vulnerary, so no item id lives here.
-- Bot.prep(roster, cap, style) -> { deploy = {charIds}, give = {} }: forced units (slot order),
--   then style.deploy (listed order; a charId not in the roster is skipped, a repeat counts
--   once), then the highest level (ties by slot order), up to `cap`. Forced units all go even
--   when they alone exceed the cap. No transfer rule is decided yet, so `give` is always empty.
-- Bot.shop(gold, stock, party) -> {{ item, qty }...}: party is the deployed roster entries, in
--   deploy order. One Vulnerary (the cheapest) per unit first, then for each unit and each
--   weapon type it has a rank in (type names in order) it holds none of, the cheapest stock
--   weapon of that type at or under its rank. A purchase gold cannot cover is skipped and the
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

local function isSureKill(f) return f.killsTarget and f.hit >= SURE_HIT end

-- Everything on the board a forecast can depend on, as one string: each unit's id, tile, HP
-- and held item (items[1], FE8's equipped slot) with its uses. Built once per decide call.
function M.boardSignature(board)
    local parts = {}
    for _, u in ipairs(board.units) do
        local held = u.items and u.items[1]
        parts[#parts + 1] = table.concat({ u.id, u.x, u.y, u.hp,
            held and held.id or "-", held and held.uses or "-" }, ":")
    end
    return table.concat(parts, ";")
end

-- One decide call's view: the board split by role, and memos so a forecast or a reach the
-- caller pays for (an emulator round trip, in the ROM) is asked for once per call.
local function context(board, sight)
    local cache = sight.cache or {}
    cache.forecasts = cache.forecasts or {}
    local ctx = { sight = sight, actors = {}, enemies = {}, standing = {},
                  forecasts = cache.forecasts, reaches = {}, worsts = {}, fields = {},
                  signature = M.boardSignature(board) }
    local o = sight.objective
    if o and o.kind == "seize" and o.tile then ctx.seizeTile = o.tile end
    for _, u in ipairs(board.units) do
        if u.onField then
            ctx.standing[tileKey(u.x, u.y)] = u
            if u.faction == "blue" and not u.acted then ctx.actors[#ctx.actors + 1] = u end
            if u.faction == "red" then ctx.enemies[#ctx.enemies + 1] = u end
        end
    end
    table.sort(ctx.actors, function(a, b) return a.slot < b.slot end)
    return ctx
end

local function forecast(ctx, u, e, x, y)
    local k = table.concat({ ctx.signature, u.id, e.id, x, y, "held" }, ",")
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
-- seize tile for a unit that cannot Seize there.
local function endTiles(ctx, u)
    local s = ctx.seizeTile
    local barred = s and not canSeize(ctx, u)
    local out = {}
    for _, t in ipairs(reachOf(ctx, u)) do
        local there = ctx.standing[tileKey(t.x, t.y)]
        if (not there or there == u) and not (barred and t.x == s.x and t.y == s.y) then
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
                local f = forecast(ctx, u, e, x, y)
                local dmg = 0
                if (f.takenHit or 0) > 0 then
                    local crit = (f.takenCrit or 0) > 0 and CRIT_MULTIPLIER or 1
                    dmg = f.takenDmg * f.takenHits * crit
                end
                w.sum, w.max = w.sum + dmg, math.max(w.max, dmg)
            end
        end
    end
    ctx.worsts[k] = w
    return w
end

-- Whether a style lets `u` end its move on (x, y), `spared` left out of the worst case. An
-- attack whose forecast says diesWorst is refused before any gate is asked (every style but
-- greedy). bold's gate never weighs the enemy phase, so it asks for no forecast to do so.
local GATES = {
    careful = function(ctx, u, x, y, spared) return worstCase(ctx, u, x, y, spared).sum < u.hp end,
    even = function(ctx, u, x, y, spared) return worstCase(ctx, u, x, y, spared).max < u.hp end,
    bold = function() return true end,
}

local function action(u, tile, act, target)
    return { unit = u.charId, unitId = u.id, move = { x = tile.x, y = tile.y }, act = act,
             target = target and target.charId, targetId = target and target.id, weapon = nil }
end

-- True if attack candidate c beats b: sure kill, kill chance, expected damage, boss, low HP.
local function betterAttack(c, b)
    if c.sure ~= b.sure then return c.sure end
    if c.killChance ~= b.killChance then return c.killChance > b.killChance end
    if c.expected ~= b.expected then return c.expected > b.expected end
    if c.target.isBoss ~= b.target.isBoss then return c.target.isBoss end
    return c.target.hp < b.target.hp
end

local function bestAttack(ctx, u, gate)
    if not u.minRange then return nil end
    local best
    for _, e in ipairs(ctx.enemies) do
        for _, t in ipairs(strikeTiles(ctx, u, e)) do
            if inRange(t.x, t.y, e.x, e.y, u.minRange, u.maxRange) then
                local f = forecast(ctx, u, e, t.x, t.y)
                local sure = isSureKill(f)
                if not f.diesWorst and gate(ctx, u, t.x, t.y, sure and e or nil) then
                    local c = { tile = t, target = e, sure = sure,
                                killChance = f.killsTarget and f.hit or 0,
                                expected = f.dmg * f.hits * f.hit }
                    if not best or betterAttack(c, best) then best = c end
                end
            end
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

local function march(ctx, u, gate, objective)
    local tiles, allowed = waitTiles(ctx, u), {}
    for _, t in ipairs(tiles) do
        if gate(ctx, u, t.x, t.y, nil) then allowed[#allowed + 1] = t end
    end
    local goal = goalFor(ctx, u, objective)
    if #allowed == 0 or not goal then
        -- nowhere is safe enough, or nothing to march to: end where the worst case is
        -- smallest, the unit's own tile first on a tie (holding costs nothing)
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
    local tiles = endTiles(ctx, u)
    local targets = {}
    for _, e in ipairs(ctx.enemies) do
        targets[#targets + 1] = { x = e.x, y = e.y, hp = e.hp, is_boss = e.isBoss, unit = e }
    end
    local pick = u.minRange and M.pickTarget(tiles, targets,
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
    local ctx = context(board, sight)
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
    -- the most threatened: the largest worst case where it stands, then the most enemies
    local u, most, count = ctx.actors[1], 0, 0
    for _, c in ipairs(ctx.actors) do
        local w, d = worstCase(ctx, c, c.x, c.y, nil).sum, sight.danger(c.x, c.y)
        if w > most or (w == most and d > count) then u, most, count = c, w, d end
    end
    local a = attacks[u]
    if a then return action(u, a.tile, "attack", a.target) end
    return action(u, march(ctx, u, gate, objective), "wait")
end

-- ── Between chapters ───────────────────────────────────────────────────────────

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
    local forced = #deploy
    for _, charId in ipairs(style.deploy or {}) do
        for _, u in ipairs(roster) do
            if u.charId == charId and #deploy < math.max(cap, forced) then take(u) break end
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

function M.shop(gold, stock, party)
    local bought, order = {}, {}
    local function buy(s)
        if not s or s.price > gold then return end
        gold = gold - s.price
        if not bought[s.item] then bought[s.item] = 0; order[#order + 1] = s.item end
        bought[s.item] = bought[s.item] + 1
    end
    local vuln = cheapest(stock, function(s) return s.kind == "vulnerary" end)
    for _ in ipairs(party) do buy(vuln) end
    for _, u in ipairs(party) do
        local types = {}
        for t in pairs(u.ranks) do types[#types + 1] = t end
        table.sort(types)
        for _, t in ipairs(types) do
            local holds = false
            for _, it in ipairs(u.items) do
                if it.type == t then holds = true end
            end
            if not holds then
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
        error("bot.lua: route " .. tostring(r) .. " is not an index into " .. #options .. " options")
    end
    return r
end

return M
