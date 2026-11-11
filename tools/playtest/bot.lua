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
--          the clear scenarios' old bot and ignores `sight` except reach, range and the
--          objective, and every claim field but `deploy`.
--   sight: every answer FE8's own code gives (sight.lua's contract; ADR 0369) --
--          { danger(x, y) -> the game's danger zone at (x, y): 0 when no enemy reaches it,
--              else gBmMapRange's coverage (1 per tile an enemy could strike it from);
--            threat(enemy) -> function(x, y) -> n, the game's danger zone of that ONE enemy:
--              0 = it cannot strike (x, y) this turn;
--            attack(unit, target, x, y, slot) -> sight.lua's (Sight.attackOf): the window's
--              numbers, and as the game plays it: kill, die, sure, expected, counterWorst,
--              dealt, counterDist, joint (the two together: { { p, dealt, back } }; a fake
--              may leave it out) | nil (out of range);
--            strike(unit, enemy, x, y) -> sight.lua's (Sight.strikeOf): the enemy's own strike
--              on `unit` standing on (x, y), on its phase, as its AI makes it and the game
--              plays it: takenDist, takenWorst; nothing taken when it does not strike there;
--            reach(unit) -> {{x,y}...}, the tiles the unit can move to this phase;
--            range(unit) -> { min, max }|nil, the reach of the weapon FE8 has equipped;
--            canSeize(unit) -> bool, the game's CanUnitSeize;
--            objective = { kind = "rout"|"boss"|"seize"|"survive"|"special",
--                          tile = {x,y}|nil, turnsLeft = n|nil, boss = charId|nil } (a
--                          Defense map is "survive"; `boss` marks that red unit isBoss on the
--                          board, beside CA_BOSS);
--            field(goal) -> dist|nil, OPTIONAL: dist[y][x] = the distance from `goal` to
--              (x, y), lower nearer (nil = unreached); FE8's own march map. A function of the
--              goal because the bot chooses the goal (the boss, the nearest enemy). Without it
--              the march falls back to Manhattan, which strands a unit against a wall (#60).
--            cache = {}|nil, OPTIONAL: a table the caller keeps for ONE player phase (an
--              AI a turn event rewrote between phases is in no key). Attacks are kept in it
--              keyed by what FE8's simulation reads -- both fighters (id, HP, level, every item
--              and its uses), both tiles, and every other unit within support range (3,
--              bmreliance.h) of either; strikes keyed by the exchange AND the whole board,
--              because the AI's pick of weapon and tile can be changed by any unit anywhere.
--              Reach and worst case are per call only.
--            terrain(x, y) -> FE8 terrain id, OPTIONAL: only a terrain claim reads it; without
--              it that claim is a no-op.
--            explorable() -> {{x, y, kind = "visit"|"chest"}...}, canExplore(unit, x, y, kind)
--              -> bool, OPTIONAL (sight.lua's): the open villages and chests, and the unit
--              menu's own check; without them nothing is explored.
--            locked(unit, x, y) -> terrain|nil, keySources(unit, terrain) -> {enemy}, OPTIONAL
--              (sight.lua's): a chest or door the unit holds no key for, and the enemies
--              whose fall gives it one; without them no way runs through a key. }
--   Returns ONE action, for the unit that should act next, or nil when no unit can act (the
--   caller ends the phase): { unit = charId, unitId = id, move = {x,y},
--   act = "attack"|"wait"|"seize", target = charId|nil, targetId = id|nil, slot = n|nil }.
--   `unitId`/`targetId` are Board's index byte: generics share a charId, the id is unique.
--   `slot` is the item an attack strikes with (one of sight.weapons), a heal's staff or a used
--   item; nil = the first the Weapon Select menu lists.
--   "talk" and "staff" are acts the claim behaviours add; "visit", "chest", "rescue" and
--   "drop" (a Drop's `dropAt` is the tile it sets the carried unit on) only the planner's
--   proposals (Bot.candidates) make. `canto` (optional, the proposals'): the tile a Canto
--   unit moves on to after the act (cantoMoves); the unit ends there (Board.endTile).
--
-- Worst case on an end tile = the sum, over every enemy that reaches it, of the most that
-- enemy's strike can take as the game plays it (takenWorst). An enemy "reaches" the
-- tile when sight.threat(enemy) covers it; danger(x, y) = 0 skips the walk. The target of a
-- SURE kill (every way the attack goes kills it) is left out: it is dead before the enemy
-- phase. An attack's own counter is its worst case too (counterWorst: nothing when the enemy
-- cannot answer or is dead before it can, as the game plays the exchange). An attack
-- whose counter alone can kill the unit is refused by every style but greedy (a known break of
-- ADR 0396: a ban the game does not make, so the planner's cap never sees that risk); then:
--   careful: the worst case < the unit's HP after that counter
--   even:    no SINGLE enemy's worst case >= that same HP
--   bold:    nothing more (the exchange alone)
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
--   carry {unit, vs}:   its units go AHEAD of style.deploy (deduped; Bot.team fills its cap in
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
--                       Its `waves` (who arrives where: campaign_env) go to style.waves, which
--                       the goals read for when a looter reaches a village (sight.closings).
--   reward {item, needs}: an end-of-chapter reward the game gives when every goal `needs`
--                       names is taken (villages, chests or tiles): style.rewards, which the
--                       goals share out over those goals.
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
-- Every game rule here is the GAME's answer, read by the caller and handed in: the bot weighs
-- no rank, level or class (ADR 0369).
-- roster entry (a unit, slot order): { id, charId, level, forced = bool|nil,
--   canUse = {[item] = true}, items = {{ id, type = weaponType|nil, kind = "vulnerary"|nil,
--   promotes = bool|nil }...} }. `canUse` is the game's CanUnitUseWeapon for this unit over the
--   stock; `promotes` is the game's own promotion-item check for THIS unit (class and level),
--   set on a seal it would accept.
-- stock entry: { item, price = {[charId] = n}, type = weaponType|nil, kind = "vulnerary"|nil };
--   price is the game's for each buyer (GetItemPurchasePrice reads the unit: a Silver Card
--   halves it). The caller says which stock item is the Vulnerary, so no item id lives here.
-- Bot.team(t) -> { deploy = {charIds}, reasons = {[charId] = reason}, give = {} }: whom the
--   prep screen fields (#510 plan comment, "Party selection"). t = { roster, cap,
--   maxima = {[group] = n}, demands = {{ id, need }...}, answers = {[charId] = {[demandId] =
--   true}}, strength = {[charId] = {[demandId] = n}}, carried = {[charId] = true}, style }. Each roster entry carries `group`, the
--   caller's read of team_groups.py (the bot weighs no class); a unit without one raises.
--   A demand is what the map asks (an enemy class, chests, fog...), `need` how many answerers
--   cover it; `answers` and `strength` are measured by the caller in the game. In order:
--   forced units (slot order, past every ceiling); then style.deploy, a followed claim's units;
--   then, while a demand still needs answerers, the unit answering the most of them (ties: a
--   carried unit, then the earlier joiner = slot order); then fill: the highest strength on
--   the biggest demand (largest need, first listed), same ties. Everything after the forced units
--   obeys `maxima`: a full group benches the later joiner, even if a slot stays empty.
--   reason = { why = "forced"|"claim"|"covers"|"fill", demands = {ids} (covers),
--   carried = bool }. No transfer rule is decided yet, so `give` is always empty.
-- Bot.shop(gold, stock, party) -> {{ unit = charId, item }...}, one entry per purchase in the
--   order made, each naming the unit it is for (FE8's shop screen buys into the inventory of
--   the unit that opened it, bmshop.c StartShopScreen). party is the deployed roster entries,
--   in deploy order. One Vulnerary (the cheapest) per unit holding none first, then for each
--   unit and each weapon type among the stock it can use (type names in order) it holds none
--   of, the cheapest stock weapon of that type it can use. A purchase gold cannot cover is
--   skipped and the later ones are still tried.
-- Bot.promote(unit, items) -> bool: a seal the game says promotes this unit is held.
-- Bot.promoteOrder(units) -> units, highest level first (ties by slot order): the order a
--   caller spends seals in.
-- Bot.route(options, style) -> style.route, validated as an index into options.
-- Bot.fullBag(held, new, convoyFull) -> slot, why: a unit given an item with no room (FE8's
--   chooser, convoymenu.c) sends one item to the convoy -- or discards it when the convoy is
--   full (convoyFull) -- and this is which (Nicolas, 2026-10-28): 0 = the new item, else the
--   index into `held`. Each item is the game's facts about it for this unit: { id, kind =
--   "weapon" (a staff included) | "heal" | "key" | "passive" | "money" | "other", type,
--   rank, maxRange, effective (its effectiveness list, compared by identity), usable, uses }.
--   The new item stays only when it is wanted: a healing item when the unit carries none, a
--   key, or a weapon it can use that it lacks the type of, that adds range or bonus damage its
--   others of the type lack, or that outranks one of them that does neither. Then what leaves
--   is, in order, money, a seal or booster, a weapon the unit cannot use (the lowest rank), a
--   spare healing item (the fewest uses), the weapon the new one beats; a discard takes only
--   the beaten weapon, the spare heal or the unusable weapon. Nothing to leave, or a new item
--   not wanted, and the new item goes.
--
-- ── The greedy core (the clear scenarios drive these directly) ─────────────────────────────
-- pickTarget(reachable, enemies, prefs) -> { target = <enemy>, tile = {x,y}, slot } | nil
--   reachable: list of {x,y} tiles the unit can move to this turn (its own tile included)
--   enemies:   list of {x,y,hp,is_boss}
--   prefs.weapons:   the unit's weapons, { slot, min, max } (sight.weapons; Board.weaponFor
--                    says which strikes a tile). A bow's min is 2: it CANNOT hit an adjacent
--                    foe, so its strike tile sits min..max away, not 1..max.
--   prefs.tilesFor:  optional function(enemy) -> tiles, the strike tiles for THAT enemy in
--                    place of `reachable` (decide's throne rule); absent = `reachable`.
--   Returns the best attackable enemy, the reachable tile to strike from and the weapon's
--   slot, or nil if no weapon strikes an enemy from any reachable tile. Preference: the boss
--   first, then the lowest-HP enemy (likeliest kill).

local M = {}

-- goals.lua, beside this file: what each open village or chest is worth, and its chance
local Goals = dofile((debug.getinfo(1, "S").source:match("^@(.*/)") or "./") .. "goals.lua")

-- board.lua is pure too. In a run the wrapper's PLAYTEST_DIR names this directory (run.sh);
-- under plain `lua` (test_bot.lua) it is read off this chunk's own path.
local Board = dofile(PLAYTEST_DIR and (PLAYTEST_DIR .. "/board.lua")
    or ((debug.getinfo(1, "S").source:match("^@(.*/)") or "./") .. "board.lua"))

local manhattan = Board.distance   -- FE8's RECT_DISTANCE

-- A reachable tile from which one of `weapons` strikes `e` (so a bow, min 2, won't pick an
-- adjacent tile it can't fire from), and that weapon; nil when none does.
local function attackTileFor(reachable, e, weapons)
    for _, t in ipairs(reachable) do
        local w = Board.weaponFor(weapons, t.x, t.y, e.x, e.y)
        if w then return t, w end
    end
    return nil
end

-- True if candidate c is a better target than the current best b.
local function preferred(c, b)
    if c.is_boss ~= b.is_boss then return c.is_boss end      -- boss beats non-boss
    return (c.hp or math.huge) < (b.hp or math.huge)         -- else lowest HP
end

function M.pickTarget(reachable, enemies, prefs)
    local best, bestTile, bestWeapon
    for _, e in ipairs(enemies) do
        local from = prefs.tilesFor and prefs.tilesFor(e) or reachable
        local tile, w = attackTileFor(from, e, prefs.weapons)
        if tile and (not best or preferred(e, best)) then
            best, bestTile, bestWeapon = e, tile, w
        end
    end
    if best then return { target = best, tile = bestTile, slot = bestWeapon.slot } end
    return nil
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
M.distance = manhattan   -- the planner's too (which player unit could save a green unit)

-- The stall watchdog's distance (#510 step 9): the nearest field distance to the target among
-- the units that could still be the one to finish -- on the field, and not excluded.
--   units:    {slot, x, y, onField} tables
--   field:    field[y][x] = distance to the target (the boss, or once it is dead the seize
--             tile), or nil
--   excluded: [slot] = true for a unit the game says cannot Seize (CanUnitSeize). Without it
--             a non-lord parked beside the throne pins the minimum while the lord's march --
--             the only progress left -- goes unseen.
-- Returns math.huge when nobody qualifies or there is no field.
function M.seizeDistance(units, field, excluded)
    local best = math.huge
    if not field then return best end
    for _, u in ipairs(units) do
        if u.onField and not (excluded and excluded[u.slot]) then
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
-- measured to (the boss, or the seize tile once it is dead): when it changes the old best
-- distance belonged to another question, and the
-- change is itself progress. Without that, a non-lord's distance to the boss (4) stood as the
-- bar the lord's march to the throne (10, then 5) had to beat, and clear_ch01 read two turns
-- of marching as a stall.
function M.madeProgress(last, now)
    if last.key ~= now.key then return true end
    return now.dist < last.dist or now.enemies < last.enemies
end

-- ── Bot.decide ─────────────────────────────────────────────────────────────────────────────

-- The axes a run's style is sampled on: aggression, a closed set, and the claims a run follows
-- (the runner's list). The team is not an axis: Bot.team picks it from the map and the claims.
-- The route is not one either: a campaign SETTING (#510 plan comment, "Lords").
M.HOLDS = 3        -- hold tiles offered per unit (candidates), safest first

M.STYLES = {
    aggression = { "careful", "even", "bold" },
    claims = {},   -- Strategy claim ids the run follows
}

-- bmreliance.h SUPPORT_BONUSES_MAX_DISTANCE, by RECT_DISTANCE. Copied because it is compiled
-- in as an immediate, with no symbol to read. It only bounds attackKey, a memo key: a unit
-- further away cannot move the simulation's support bonus (bmreliance.c). The link arena's
-- unlimited range (BM_FLAG_LINKARENA) never applies in a campaign.
local SUPPORT_RANGE = 3


-- The chance the attack kills, as a whole number of billionths: equal chances must compare
-- equal, and a sum of float products differs in its last bit with the order it was added in.
local function killChance(f) return math.floor(f.kill * 1e9 + 0.5) end

-- A unit as an attack or strike reads it within a phase: id, HP, level (a level-up mid-phase
-- changes its stats) and every item with its uses (which one is equipped is the game's call:
-- GetUnitEquippedWeapon, the first usable, not a fixed slot).
local function unitKey(u)
    local parts = { u.id, u.hp, u.level or "-" }
    for _, it in ipairs(u.items or {}) do parts[#parts + 1] = it.id .. "x" .. it.uses end
    return table.concat(parts, ":")
end

-- One decide call's view: the board split by role, and memos so an attack, a strike or a reach
-- the caller pays for (an emulator round trip, in the ROM) is asked for once.
-- The enemies a player knows of on `board`: every red on the field the game does not hide in
-- fog (US_BIT9, board.lua), the Defeat Boss map's boss marked as the game names it
-- (sight.objective.boss), CA_BOSS or not. The planner asks it again for a board it judges on
-- that is not the one its acts were read on (a full-information replay's, opts.offer).
-- -> those in sight, and the threats: those plus every fogged one a retry remembers
-- (sight.knows, ADR 0399), which can strike a tile but not be targeted (bmtarget.c refuses a
-- unit on a fogged tile), so only the danger reads take them (exposure).
function M.enemiesOf(board, sight)
    local o, out, threats = sight.objective, {}, {}
    for _, u in ipairs(board.units) do
        if o and o.boss and u.faction == "red" and u.charId == o.boss then u.isBoss = true end
        if u.onField and u.faction == "red" then
            if not u.fogged then out[#out + 1] = u end
            if Board.playsAsSeen(u.fogged, u.fogged and sight.knows and sight.knows(u)) then
                threats[#threats + 1] = u
            end
        end
    end
    return out, threats
end

-- One unit across a chapter start's attempts (Board's, ADR 0399): campaign.lua holds Bot only
M.memoryKey = Board.memoryKey

M.FOG_REACH = 6    -- unseen ground this close to a unit may hide what can strike it

-- The fog read (#510 PR A, plan comment 6779357154 step 4): ground the fog hides may hide what
-- strikes a unit beside it, and the judged phase plays only the enemies in sight. A unit on
-- (x, y) within FOG_REACH of an unseen tile meets one strike from the strongest enemy seen so
-- far, stood on the nearest unseen tile no other unit stands on (sight.strike's `from`: the
-- game's AI choosing from there, the unit its one target; a tile another hidden unit holds would
-- put two units on one cell of the map, while the enemy's own tile is where it stands). Seen so far is `seen` (unit slot -> charId, botrun's: every red a
-- board showed out of fog this attempt), else the enemies in sight; of each class and kit the
-- highest level is asked. -> { die(u, x, y, hp): the chance that strike kills `u` at `hp`, 0
-- with no free unseen tile in reach or no enemy seen; unseen: every tile the fog hides }. Its
-- strikes are memoised for the decision.
function M.fogRead(board, sight, seen)
    local unseen = sight.unseen and sight.unseen() or {}
    local reps, kits, memo = {}, {}, {}
    if #unseen > 0 and sight.strike then
        for _, u in ipairs(board.units) do
            local ok = u.faction == "red" and u.onField and not u.dead
            if ok then
                if seen then ok = seen[u.id] == u.charId else ok = not u.fogged end
            end
            local kit
            if ok then
                local ids = {}   -- board.lua's items: { id, uses }
                for _, it in ipairs(u.items or {}) do ids[#ids + 1] = it.id end
                kit = tostring(u.classId) .. ":" .. table.concat(ids, ",")
            end
            local had = kit and kits[kit]
            if kit and not had then
                kits[kit] = #reps + 1
                reps[#reps + 1] = u
            elseif had and (u.level or 0) > (reps[had].level or 0) then
                reps[had] = u
            end
        end
    end
    -- the unit on each tile, hidden ones too (board.lua reads every unit's tile)
    local held = {}
    for _, u in ipairs(board.units) do
        if u.onField and not u.dead then held[tileKey(u.x, u.y)] = u.id end
    end
    local odds = sight.odds or function() return 0 end
    local function die(u, x, y, hp)
        if #reps == 0 or hp <= 0 then return 0 end
        local worst = 0
        for _, e in ipairs(reps) do
            -- the nearest unseen tile in reach that no unit but `e` itself holds
            local edge, near
            for _, t in ipairs(unseen) do
                local d = manhattan(t.x, t.y, x, y)
                local by = held[tileKey(t.x, t.y)]
                if d <= M.FOG_REACH and (not by or by == e.id) and (not near or d < near) then
                    edge, near = t, d
                end
            end
            if edge then
                local k = u.id .. "@" .. x .. "," .. y .. "/" .. e.id
                local f = memo[k]
                if not f then
                    f = sight.strike(u, e, x, y, nil, edge)
                    memo[k] = f
                end
                worst = math.max(worst, (odds({ f.takenDist }, hp)))
            end
        end
        return worst
    end
    return { die = die, unseen = unseen }
end

local function context(board, sight)
    local cache = sight.cache or {}
    cache.attacks, cache.strikes = cache.attacks or {}, cache.strikes or {}
    local ctx = { sight = sight, actors = {}, enemies = {}, blues = {}, standing = {},
                  onField = {}, attacks = cache.attacks, strikes = cache.strikes, reaches = {},
                  worsts = {}, exposures = {}, options = {}, priced = {}, breaches = {}, keyed = {}, talks = {},
                  talkTiles = {}, openers = {}, rescueTiles = {}, carried = {} }
    local o = sight.objective
    if o and o.kind == "seize" and o.tile then ctx.seizeTile = o.tile end
    -- the map the phase memos are kept on (sight.mapKey): a door or wall the phase opened
    ctx.mapKey = sight.mapKey and sight.mapKey() or "-"
    ctx.enemies, ctx.threats = M.enemiesOf(board, sight)
    -- the fog read (M.fogRead), built when first asked: ctx.seen is M.candidates' opts.seen
    local fog
    ctx.fogRead = function()
        fog = fog or M.fogRead(board, sight, ctx.seen)
        return fog
    end
    for _, u in ipairs(board.units) do
        -- a carried unit (Rescue): off the field, at its carrier's tile, by its id
        if u.carriedBy and not u.dead then ctx.carried[u.id] = u end
        if u.onField then
            ctx.onField[#ctx.onField + 1] = u
            ctx.standing[tileKey(u.x, u.y)] = u
            if u.faction == "blue" then ctx.blues[#ctx.blues + 1] = u end
            if u.faction == "blue" and not u.acted then ctx.actors[#ctx.actors + 1] = u end
        end
    end
    table.sort(ctx.actors, function(a, b) return a.slot < b.slot end)
    -- the max HP a heal fills to, as the game reads it (the board's maxhp is the raw stat)
    if sight.maxHps then sight.maxHps(ctx.blues) end
    return ctx
end

-- An attack's key: what FE8's simulation reads for it -- both fighters (unitKey), our tile, the
-- enemy's tile, the map (ctx.mapKey: the phase memo outlives a door the phase opens), and every
-- other unit within support range of either fighter (support bonuses move with them). An
-- action elsewhere leaves it standing.
local function attackKey(ctx, u, e, x, y, slot)
    local parts = { unitKey(u), slot or "-", x, y, unitKey(e), e.x, e.y, ctx.mapKey, "near" }
    for _, o in ipairs(ctx.onField) do
        if o ~= u and o ~= e and (manhattan(o.x, o.y, x, y) <= SUPPORT_RANGE
                or manhattan(o.x, o.y, e.x, e.y) <= SUPPORT_RANGE) then
            parts[#parts + 1] = o.id .. "@" .. tileKey(o.x, o.y)
        end
    end
    return table.concat(parts, ";")
end

-- A strike's key: the exchange and the WHOLE board, its map too (ctx.mapKey). The strike is the enemy AI's own pick of
-- weapon and tile (sight.lua), and any unit anywhere can block or open its path.
local function strikeKey(ctx, u, e, x, y, slot)
    local parts = { unitKey(u), x, y, slot or "-", unitKey(e), e.x, e.y, ctx.mapKey, "board" }
    for _, o in ipairs(ctx.onField) do
        parts[#parts + 1] = unitKey(o) .. "@" .. tileKey(o.x, o.y)
    end
    return table.concat(parts, ";")
end

local function remembered(memo, k, ask)
    local v = memo[k]
    if v == nil then
        v = ask() or false
        memo[k] = v
    end
    return v or nil
end

-- Our attack from (x, y) on `e` with the weapon in item `slot` (nil when it does not reach),
-- and `e`'s own strike on `u` there, `u` holding the weapon in `slot` (nil: as it is) after
-- striking with it.
local function attack(ctx, u, e, x, y, slot)
    return remembered(ctx.attacks, attackKey(ctx, u, e, x, y, slot),
        function() return ctx.sight.attack(u, e, x, y, slot) end)
end
local function strike(ctx, u, e, x, y, slot)
    return remembered(ctx.strikes, strikeKey(ctx, u, e, x, y, slot),
        function() return ctx.sight.strike(u, e, x, y, slot) end)
end

-- sight.reach, with the unit's own tile always in it (attacking or waiting where it stands),
-- and the tiles our own units stand on (FE8's movement map passes through them; endTiles).
local function reachOf(ctx, u)
    local r = ctx.reaches[u.id]
    if r then return r end
    r = {}
    local own = false
    for _, t in ipairs(ctx.sight.reach(u, true) or {}) do
        r[#r + 1] = t
        if t.x == u.x and t.y == u.y then own = true end
    end
    if not own then r[#r + 1] = { x = u.x, y = u.y } end
    ctx.reaches[u.id] = r
    return r
end

local function canSeize(ctx, u) return ctx.sight.canSeize(u) end

local function reaches(ctx, e, x, y) return ctx.sight.threat(e)(x, y) > 0 end

-- The charIds whose death ends the game, as a set (charId -> true): the game's own list,
-- sight.objective.gameOver (a lord's death quote sets EVFLAG_GAMEOVER). The planner and botrun
-- both read it from here.
function M.gameOver(sight)
    local set = {}
    for _, c in ipairs(sight.objective and sight.objective.gameOver or {}) do set[c] = true end
    return set
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

-- The tiles `u` can end on: its reach, less every tile another unit stands on, and less the
-- seize tile for a unit that cannot Seize there -- unless it already stands on it: its own
-- tile is always left, so a unit boxed in on the throne still has somewhere to wait.
-- A tile an ally who has yet to act stands on is left in: the plan may move that ally first
-- (vacated, below; the planner holds the act until it has), unless ctx.freeOnly is set
-- (candidates' second march and retreat). Manchego Stars ch03: the corner's safe tiles held our
-- lightest hitters, and Braulo, the heaviest, never reached the boss.
local function vacated(ctx, u, x, y)
    local there = ctx.standing[tileKey(x, y)]
    if there and there ~= u and there.faction == "blue" and not there.acted then return there end
    return nil
end

local function endTiles(ctx, u)
    local s = ctx.seizeTile
    local barred = s and not canSeize(ctx, u)
    local out = {}
    for _, t in ipairs(reachOf(ctx, u)) do
        local there = ctx.standing[tileKey(t.x, t.y)]
        local own = t.x == u.x and t.y == u.y
        if (not there or there == u or (not ctx.freeOnly and vacated(ctx, u, t.x, t.y)))
            and (own or not (barred and t.x == s.x and t.y == s.y)) then
            out[#out + 1] = t
        end
    end
    return out
end

-- Where `u` may Wait: its end tiles, and for a unit that cannot Seize none on or beside the
-- seize tile (needsToStepOff) while any other is left -- it aims at the throne, it does not
-- stand in the lord's way to it.
-- An avoid claim on `u` keeps it off every tile an enemy its `vs` names reaches, while any
-- other is left -- and not on a stalled board (ctx.stalled), where a careful player that has
-- stopped making progress takes the least it must (vanilla Ch5: Natasha dead, every unit
-- kept out of Joshua's reach between them and the boss, the same board for ten turns).
local function outOfReach(ctx, u, tiles)
    if ctx.stalled then return tiles end
    local vs = {}
    for _, c in ipairs(ctx.style.avoids or {}) do
        if listed(c.units, u.charId) then vs[#vs + 1] = c.vs end
    end
    if #vs == 0 then return tiles end
    local clear = {}
    for _, t in ipairs(tiles) do
        local safe = true
        for _, v in ipairs(vs) do
            if nearestReaching(ctx, v, t.x, t.y) then safe = false end
        end
        if safe then clear[#clear + 1] = t end
    end
    return #clear > 0 and clear or tiles
end

local function waitTiles(ctx, u)
    local tiles, s = outOfReach(ctx, u, endTiles(ctx, u)), ctx.seizeTile
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

-- sight.field for `goal` (sight keeps it for the board); nil when the caller has none.
local function fieldFor(ctx, goal)
    if not (goal and ctx.sight.field) then return nil end
    return ctx.sight.field(goal)
end

-- The style's claim entries in `field` that name `u` (a carry, answer or wall's units).
local function claimsOn(ctx, field, u)
    local out = {}
    for _, c in ipairs(ctx.style[field] or {}) do
        if listed(c.units, u.charId) then out[#out + 1] = c end
    end
    return out
end

-- What can strike `u` next enemy phase if it ends on (x, y): per enemy seen or remembered
-- (ctx.threats) that reaches
-- the tile, that enemy (`by`) and its own strike there (sight.strike: the AI's weapon), `u`
-- holding the weapon in `slot` when it struck with that one.
local function exposure(ctx, u, x, y, slot)
    local k = u.id .. "@" .. tileKey(x, y) .. "/" .. (slot or "-")
    local list = ctx.exposures[k]
    if list then return list end
    list = {}
    if ctx.sight.danger(x, y) > 0 then
        for _, e in ipairs(ctx.threats) do
            if reaches(ctx, e, x, y) then
                list[#list + 1] = { by = e, f = strike(ctx, u, e, x, y, slot) }
            end
        end
    end
    ctx.exposures[k] = list
    return list
end

-- The enemy phase's worst case for `u` ending on (x, y): {sum, max} of each reaching enemy's
-- damage, `spared` (a sure kill's target) left out.
local function worstCase(ctx, u, x, y, spared)
    local k = u.id .. "@" .. tileKey(x, y) .. "-" .. (spared and spared.id or "")
    local w = ctx.worsts[k]
    if w then return w end
    w = { sum = 0, max = 0 }
    for _, s in ipairs(exposure(ctx, u, x, y)) do
        if s.by ~= spared then
            local dmg = s.f.takenWorst
            w.sum, w.max = w.sum + dmg, math.max(w.max, dmg)
        end
    end
    ctx.worsts[k] = w
    return w
end

-- Of `tiles`, the one with the smallest worst case, the unit's own tile first on a tie (holding
-- costs nothing).
-- `tiles`, safest first: the lowest worst case, its own tile first on a tie, then board order.
local function bySafety(ctx, u, tiles)
    local out = {}
    for i, t in ipairs(tiles) do
        out[i] = { t = t, i = i, sum = worstCase(ctx, u, t.x, t.y, nil).sum,
                   own = t.x == u.x and t.y == u.y }
    end
    table.sort(out, function(a, b)
        if a.sum ~= b.sum then return a.sum < b.sum end
        if a.own ~= b.own then return a.own end
        return a.i < b.i
    end)
    for i, o in ipairs(out) do out[i] = o.t end
    return out
end

local function safest(ctx, u, tiles) return bySafety(ctx, u, tiles)[1] end

-- Whether a style lets `u` end its move on (x, y), `spared` left out of the worst case and
-- `spent` (the attack's own counter, f.counterWorst) already off its HP. An attack whose
-- counter alone can kill is refused before any gate is asked (every style but greedy; a known
-- break of ADR 0396).
-- bold's gate never weighs the enemy phase, so it asks for no strike to do so.
local GATES = {
    careful = function(ctx, u, x, y, spared, spent)
        return worstCase(ctx, u, x, y, spared).sum < u.hp - (spent or 0)
    end,
    even = function(ctx, u, x, y, spared, spent)
        return worstCase(ctx, u, x, y, spared).max < u.hp - (spent or 0)
    end,
    bold = function() return true end,
}

local function action(u, tile, act, target, slot)
    return { unit = u.charId, unitId = u.id, move = { x = tile.x, y = tile.y }, act = act,
             target = target and target.charId, targetId = target and target.id, slot = slot }
end

-- An attack option's act: its tile, target and weapon.
local function strikeAct(u, c) return action(u, c.tile, "attack", c.target, c.slot) end

-- True if attack candidate c beats b: a priority target, an answered class, sure kill, kill
-- chance, expected damage, boss, low HP.
local function betterAttack(c, b)
    if c.first ~= b.first then return c.first end
    if c.answered ~= b.answered then return c.answered end
    if c.sure ~= b.sure then return c.sure end
    if c.killChance ~= b.killChance then return c.killChance > b.killChance end
    if c.expected ~= b.expected then return c.expected > b.expected end
    if c.target.isBoss ~= b.target.isBoss then return c.target.isBoss end
    return c.target.hp < b.target.hp
end

-- A priority claim's enemy, or under a keys claim one the game says holds a key or lockpick
-- (sight.holdsKey): struck before the rest.
local function isPriority(ctx, e)
    for _, c in ipairs(ctx.style.priorities or {}) do
        if matchesVs(c.vs, e) then return true end
    end
    if ctx.style.keys and ctx.sight.holdsKey then
        if ctx.keyed[e.id] == nil then ctx.keyed[e.id] = ctx.sight.holdsKey(e) end
        return ctx.keyed[e.id]
    end
    return false
end

-- Under a heal claim against `e`: the most HP a healer that has not acted can give `u` after
-- it strikes from `t` -- a staff the healer holds (sight.staves), a tile of its reach beside
-- `t` (the adjacent staves; a Physic's reach is not counted). 0 otherwise.
local function healCredit(ctx, u, e, t)
    local claimed = false
    for _, c in ipairs(ctx.style.heals or {}) do
        if matchesVs(c.vs, e) then claimed = true end
    end
    if not (claimed and ctx.sight.staves) then return 0 end
    local best = 0
    for _, h in ipairs(ctx.actors) do
        if h ~= u then
            for _, st in ipairs(ctx.sight.staves(h)) do
                if st.amount > best then
                    for _, r in ipairs(endTiles(ctx, h)) do
                        if manhattan(r.x, r.y, t.x, t.y) == 1 then best = st.amount break end
                    end
                end
            end
        end
    end
    return best
end

-- Every attack the gate allows `u` this call, worked out once (decide's pass and a claim's
-- filtered pass read the same list). `priced` (the planner's proposals): an attack whose
-- counter can kill is offered, its death chance (the forecast's `die`) judged against the
-- cap like any other (ADR 0396: only the game forbids). Without it, decide's own refusal of
-- every attack whose counter's worst case reaches the unit's HP (ADR 0368's gates).
local function attackOptions(ctx, u, gate, priced)
    local store = priced and ctx.priced or ctx.options
    local opts = store[u]
    if opts then return opts end
    opts = {}
    local answers = claimsOn(ctx, "answers", u)
    local weapons = ctx.sight.weapons(u)
    for _, e in ipairs(ctx.enemies) do
        local answered = false
        for _, c in ipairs(answers) do
            if matchesVs(c.vs, e) then answered = true end
        end
        local first = isPriority(ctx, e)
        for _, t in ipairs(strikeTiles(ctx, u, e)) do
            for _, w in ipairs(weapons) do
                local f = Board.weaponFor(weapons, t.x, t.y, e.x, e.y, w.slot)
                    and attack(ctx, u, e, t.x, t.y, w.slot)
                local sure = f and f.sure
                local spent = f and f.counterWorst
                -- what the counter leaves before the enemy phase, a heal claim's heal counted
                local left = f and math.max(u.hp - (u.maxhp or u.hp),
                                            spent - healCredit(ctx, u, e, t))
                if f and (priced or spent < u.hp) and gate(ctx, u, t.x, t.y, sure and e or nil, left) then
                    opts[#opts + 1] = { tile = t, target = e, slot = w.slot, sure = sure,
                                        answered = answered, first = first, f = f,
                                        spent = spent, killChance = killChance(f),
                                        expected = f.expected }
                end
            end
        end
    end
    store[u] = opts
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

-- Where the march heads: the recruit, village or chest the unit is sent to (exploring, below),
-- else its way to the objective (objectiveTile); nil = hold.
-- objectiveTile: the objective's tile, the boss, or the nearest enemy; nil on a Survive map.
-- With no enemy in sight (fog), the nearest tile the party cannot see: a player knows no more
-- than the fog shows, so it pushes the fog back. Only the enemies in sight are aimed at: a boss
-- the fog hides is no goal (Bot.enemiesOf), so on a fogged Defeat Boss map each unit marches on
-- its nearest enemy in sight (#510 W1, Ch6 4001 attempt 2).
-- ctx.aimBoss (Bot.candidates' opts.aim = "boss": the look's boss alternative, #510 W1, shadow
-- only) makes a boss in fog that a retry remembers (ctx.threats, sight.knows) the goal too.
-- objectiveGoal is the same choice with where it came from, for Bot.explain: the tile, then
-- "objective" (the objective's own tile), "unseen", "boss" or "enemy", and the enemy's id.
local objectiveTile
local function objectiveGoal(ctx, u, objective)
    local kind = objective and objective.kind
    if objective and objective.tile then return objective.tile, "objective" end
    if kind == "survive" then return nil end
    if kind == "boss" and ctx.aimBoss then
        for _, e in ipairs(ctx.threats) do
            if e.isBoss then return e, "boss", e.id end
        end
    end
    if #ctx.enemies == 0 and ctx.sight.unseen then
        local best, bestD
        for _, t in ipairs(ctx.fogRead().unseen) do
            local d = manhattan(u.x, u.y, t.x, t.y)
            if not bestD or d < bestD then best, bestD = t, d end
        end
        return best, best and "unseen"
    end
    local best, bestD
    for _, e in ipairs(ctx.enemies) do
        local d = manhattan(u.x, u.y, e.x, e.y)
        if kind == "boss" and e.isBoss then return e, "boss", e.id end
        if not bestD or d < bestD then best, bestD = e, d end
    end
    return best, best and "enemy", best and best.id
end
local function goalFor(ctx, u, objective)
    local explore = ctx.exploreGoal and ctx.exploreGoal[u.id]
    if explore then return explore end
    return objectiveTile(ctx, u, objective)
end
objectiveTile = function(ctx, u, objective) return (objectiveGoal(ctx, u, objective)) end

-- The obstacle that opens `u`'s way to `goal` when no walk reaches it: sight.field(goal) is
-- known and leaves u's tile unreached. Of the obstacles the Attack command can strike
-- (sight.obstacles), one beside a tile the goal's field reaches, and whose own field reaches u,
-- the nearest u by that field. nil when u is not cut off, or nothing opens the way. A door is
-- one when u can open it, now or with a key it can take on the way (doorOpens).
local SIDES = { { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } }

-- `u` holds a key or lockpick for doors (sight.opens, the Door command's own check).
local function opener(ctx, u)
    if ctx.openers[u.id] == nil then
        ctx.openers[u.id] = ctx.sight.opensDoor ~= nil and ctx.sight.opensDoor(u) or false
    end
    return ctx.openers[u.id]
end

-- A unit and a goal tile as one key, "unit id>x,y": breachFor's cache, and M.candidates'
-- record of the goals units are blocked from.
local function goalKey(id, t) return id .. ">" .. tileKey(t.x, t.y) end

-- What `u` lacks to use the tile (x, y): the chest's or door's terrain when the game says it
-- holds nothing that opens it (sight.locked), else nil.
local function lockAt(ctx, u, x, y)
    return ctx.sight.locked and ctx.sight.locked(u, x, y) or nil
end

-- A key on the way (#510, vanilla Ch5x: two chests in a room behind a door, both keys on
-- enemies). `seeking` = the locks a way is fetching a key for, so a key behind its own lock is
-- no way. A key taken on the way opens the one lock it was fetched for (`keyed`: the tile's
-- own), never a second: a Door Key or Chest Key is one use (FE8's item data).
local function withLock(set, lock)
    local out = { [lock] = true }
    for k in pairs(set or {}) do out[k] = true end
    return out
end
local function lockSig(set)
    local out = {}
    for k in pairs(set or {}) do out[#out + 1] = tostring(k) end
    table.sort(out)
    return table.concat(out, ",")
end

-- The enemies whose fall gives `u` what opens `lock` (sight.keySources), read once a decision.
local function keySources(ctx, u, lock)
    if not ctx.sight.keySources then return {} end
    ctx.keySrc = ctx.keySrc or {}
    local k = u.id .. ":" .. tostring(lock)
    if ctx.keySrc[k] == nil then ctx.keySrc[k] = ctx.sight.keySources(u, lock) end
    return ctx.keySrc[k]
end

local keyWay

-- Whether `u` can open the door `d`: it holds a key, or it has a way to an enemy whose fall
-- gives it one and from there to the door (keyWay). A key no one can reach opens nothing, so a
-- wall the unit can strike is still its way through.
local function doorOpens(ctx, u, d, seeking)
    local lock = lockAt(ctx, u, d.x, d.y)
    if not lock then return true end
    return keyWay(ctx, u, d, u, lock, seeking) ~= nil
end

local function breachFor(ctx, u, goal, seeking)
    if not (goal and ctx.sight.obstacles) then return nil end
    local k = goalKey(u.id, goal) .. "|" .. lockSig(seeking)
    local b = ctx.breaches[k]
    if b ~= nil then return b or nil end
    -- one still being worked out reads as none: a door's key way can ask for this same breach
    -- again (the key's holder cut off from the door), and that way would never end
    b, ctx.breaches[k] = false, false
    local field = fieldFor(ctx, goal)
    if field and not (field[u.y] and field[u.y][u.x]) then
        -- a unit that can open a door takes it first: opening costs one act, a wall its HP
        local doors = {}
        for _, d in ipairs(ctx.sight.doors and ctx.sight.doors() or {}) do
            if opener(ctx, u) or (ctx.sight.locked and doorOpens(ctx, u, d, seeking)) then
                doors[#doors + 1] = { x = d.x, y = d.y, door = true }
            end
        end
        local lists = { ctx.sight.obstacles() }
        if #doors > 0 then table.insert(lists, 1, doors) end
        for _, list in ipairs(lists) do
            local bestD
            for _, o in ipairs(list) do
                local opens = false
                for _, d in ipairs(SIDES) do
                    local y = field[o.y + d[2]]
                    if y and y[o.x + d[1]] then opens = true end
                end
                local of = opens and fieldFor(ctx, o)
                local d = of and of[u.y] and of[u.y][u.x]
                if d and (not bestD or d < bestD) then b, bestD = o, d end
            end
            if b then break end
        end
    end
    ctx.breaches[k] = b
    return b or nil
end

-- The turns `u` needs from `from` (default: where it stands) to `tile`, the goals' read
-- (goals.lua's turnsTo): sight.turnsTo on its own costs, else, cut off by a door or a wall,
-- through the obstacle that opens the way (breachFor) as the march goes -- its moves to the
-- obstacle, one step through, the field beyond. Without the breach, vanilla Ch3's throne (behind
-- walls) was unreachable for every unit, so nothing pulled the army and a run took 22 turns.
-- A chest or door `u` has no key for is reached by way of the enemy whose fall gives it one
-- (keyWay): the walk to that enemy, then on from its tile with the key (`keyed`). Memoised
-- for the decision (ctx.keyTurns): the goals ask it per goal, taker and partial plan.
local function turnsFor(ctx, u, tile, from, seeking, keyed)
    from = from or u
    ctx.keyTurns = ctx.keyTurns or {}
    local mk = u.id .. "@" .. from.x .. "," .. from.y .. ">" .. tile.x .. "," .. tile.y .. "|"
        .. lockSig(seeking) .. (keyed and "+" or "")
    local hit = ctx.keyTurns[mk]
    if hit ~= nil then return hit or nil end
    local s, n = ctx.sight, nil
    local lock = not keyed and lockAt(ctx, u, tile.x, tile.y)
    if lock then
        n = select(2, keyWay(ctx, u, tile, from, lock, seeking))
    else
        n = s.turnsTo and s.turnsTo(u, tile, from)
        local b = not n and s.turnsTo and breachFor(ctx, u, tile, seeking)
        local toB = b and (b.door and turnsFor(ctx, u, b, from, seeking) or s.turnsTo(u, b, from))
        local field = toB and fieldFor(ctx, tile)
        local beyond
        for _, side in ipairs(field and SIDES or {}) do
            local row = field[b.y + side[2]]
            local v = row and row[b.x + side[1]]
            if v and (not beyond or v < beyond) then beyond = v end
        end
        if beyond then n = toB + (1 + beyond) / s.mov(u) end
    end
    ctx.keyTurns[mk] = n or false
    return n
end

-- The enemy whose fall gives `u` what opens `lock` at `tile` (keySources), the one on the
-- fewest turns there and on (turnsFor), and those turns; nil when none has a way.
keyWay = function(ctx, u, tile, from, lock, seeking)
    if seeking and seeking[lock] then return nil end
    local fetching, best, bestN = withLock(seeking, lock), nil, nil
    for _, e in ipairs(keySources(ctx, u, lock)) do
        local a = turnsFor(ctx, u, e, from, fetching)
        local b = a and turnsFor(ctx, u, tile, e, seeking, true)
        if b and (not bestN or a + b < bestN) then best, bestN = e, a + b end
    end
    return best, bestN
end

-- Where `u` marches for `tile`: the enemy holding the key it lacks (keyWay), else the obstacle
-- that opens the way (breachFor), else the tile; a door it has no key for, through its key.
-- turnsFor in moves, as marchLength counts a march (cost, not turns); nil = no way
local function movesFor(ctx, u, tile)
    local n = turnsFor(ctx, u, tile)
    return n and n * ctx.sight.mov(u)
end

local function stepFor(ctx, u, tile, seeking)
    local lock = tile and lockAt(ctx, u, tile.x, tile.y)
    if lock then
        local e = keyWay(ctx, u, tile, u, lock, seeking)
        return e and stepFor(ctx, u, e, withLock(seeking, lock)) or tile
    end
    local b = breachFor(ctx, u, tile, seeking)
    if b and b.door and lockAt(ctx, u, b.x, b.y) then return stepFor(ctx, u, b, seeking) end
    return b or tile
end

-- Where `u` marches: its goal, or what opens the way to it (stepFor).
local function marchGoal(ctx, u, objective)
    return stepFor(ctx, u, goalFor(ctx, u, objective))
end

-- A cut-off unit's strike on its breach, from the wait tile the gate allows nearest it; nil
-- when it has no weapon or no such tile is in range this turn.
local function breach(ctx, u, gate, objective)
    -- the obstacle the march is stepping to (stepFor): a locked door's way may be a wall in
    -- front of its key's holder, and that wall is the one to strike now
    local b = stepFor(ctx, u, goalFor(ctx, u, objective))
    if not (b and (b.door or (b.hp ~= nil and b.id == nil))) then return nil end
    -- a door opens where the Door command offers it (sight.offers); a wall is struck by a
    -- weapon that reaches it
    local weapons = not b.door and ctx.sight.weapons(u)
    if not (b.door or #weapons > 0) then return nil end
    local tiles = waitTiles(ctx, u)
    if b.door then tiles = ctx.sight.offers(u, tiles, "door", b) end
    for _, t in ipairs(tiles) do
        local can = b.door or Board.weaponFor(weapons, t.x, t.y, b.x, b.y)
        if can and gate(ctx, u, t.x, t.y, nil) then
            if b.door then
                -- the door it opens: the judged enemy phase plays with it open (planner.lua)
                local a = action(u, t, "door", nil)
                a.door = { x = b.x, y = b.y }
                return a
            end
            local a = action(u, t, "attack", nil, can.slot)
            -- its HP and the strike's blow (the game's forecast): the planner tracks the wall
            a.obstacle = { x = b.x, y = b.y, hp = b.hp, blow = ctx.sight.strikeWall
                           and ctx.sight.strikeWall(u, b, t.x, t.y, can.slot) }
            return a
        end
    end
    return nil
end

-- Whether the game lets `u` Talk to `t` (sight.canTalk), asked once per pair per decide.
local function talks(ctx, u, t)
    local k = u.id .. ">" .. t.id
    if ctx.talks[k] == nil then
        ctx.talks[k] = ctx.sight.canTalk ~= nil and ctx.sight.canTalk(u, t) or false
    end
    return ctx.talks[k]
end

-- The Rescues `u` may make: of each green unit on the field (an ally, bmphase.c
-- AreUnitsAllied), from each wait tile beside it the gate allows where the game's Rescue
-- command lists it (sight.offers: RescueUsability, CanUnitRescue's Aid against Con). Which one,
-- if any, is the planner's: what it saves is the judged phase's to read (ADR 0396). A blue
-- unit is not offered as a target: one carried cannot act, and the guides' Rescue is of a
-- green in danger (vanilla Ch2's Ross; docs/research/0014).
local function rescues(ctx, u, gate)
    local out = {}
    if not ctx.sight.offers or u.carrying then return out end
    for _, t in ipairs(ctx.onField) do
        if t.faction == "green" and not t.fogged then
            local k = u.id .. ">" .. t.id
            if not ctx.rescueTiles[k] then
                local beside = {}
                for _, tile in ipairs(waitTiles(ctx, u)) do
                    if manhattan(tile.x, tile.y, t.x, t.y) == 1 then beside[#beside + 1] = tile end
                end
                ctx.rescueTiles[k] = #beside > 0 and ctx.sight.offers(u, beside, "rescue", t) or {}
            end
            for _, tile in ipairs(ctx.rescueTiles[k]) do
                if gate(ctx, u, tile.x, tile.y, nil) then out[#out + 1] = action(u, tile, "rescue", t) end
            end
        end
    end
    return out
end

-- The Drops `u` may make of the unit it carries (board's `carrying`): from its own tile and
-- from each wait tile beside a unit that may Talk it over (recruitsOf: a carried recruit is
-- talked to once set down), onto each tile the game's drop list holds (sight.drops). Which is
-- the planner's to rank.
local function drops(ctx, u, gate)
    local out = {}
    local t = u.carrying and ctx.carried[u.carrying]
    if not t or not ctx.sight.drops then return out end
    local near, from = {}, {}
    for _, id in ipairs(ctx.recruitTalkers and ctx.recruitTalkers[t.id] or {}) do
        for _, b in ipairs(ctx.blues) do
            if b.id == id and b ~= u then near[#near + 1] = b end
        end
    end
    for _, tile in ipairs(waitTiles(ctx, u)) do
        local keep = tile.x == u.x and tile.y == u.y
        for _, b in ipairs(near) do
            if manhattan(tile.x, tile.y, b.x, b.y) <= 2 then keep = true end
        end
        if keep and gate(ctx, u, tile.x, tile.y, nil) then from[#from + 1] = tile end
    end
    for _, d in ipairs(#from > 0 and ctx.sight.drops(u, from) or {}) do
        for _, at in ipairs(d.drops) do
            local a = action(u, d, "drop", t)
            a.dropAt = { x = at.x, y = at.y }
            out[#out + 1] = a
        end
    end
    return out
end

-- A Talk from a wait tile the gate allows where the Talk command offers `t` (sight.offers);
-- nil when `u` cannot reach one. The tiles are asked once per pair per decide.
local function talkFrom(ctx, u, t, gate)
    if not talks(ctx, u, t) then return nil end
    local k = u.id .. ">" .. t.id
    ctx.talkTiles[k] = ctx.talkTiles[k] or ctx.sight.offers(u, waitTiles(ctx, u), "talk", t)
    for _, tile in ipairs(ctx.talkTiles[k]) do
        if gate(ctx, u, tile.x, tile.y, nil) then return action(u, tile, "talk", t) end
    end
    return nil
end

-- The march from `u` to `t` by the game's field from `t`, through the breach where the field
-- has no way (breachFor); nil = no way at all.
local function marchLength(ctx, u, t)
    local field = fieldFor(ctx, t)
    local d = field and field[u.y] and field[u.y][u.x]
    if field and not d then
        -- the way through the breach: the path to it, one step through, the path beyond
        local b = breachFor(ctx, u, t)
        if b and b.door and lockAt(ctx, u, b.x, b.y) then
            -- its key first, as turnsFor counts the way (keyWay)
            return movesFor(ctx, u, t)
        end
        local of = b and fieldFor(ctx, b)
        local toB, beyond = of and of[u.y] and of[u.y][u.x], nil
        for _, side in ipairs(b and SIDES or {}) do
            local row = field[b.y + side[2]]
            local v = row and row[b.x + side[1]]
            if v and (not beyond or v < beyond) then beyond = v end
        end
        d = toB and beyond and toB + 1 + beyond
    end
    return d
end

-- Whether `u` may Talk `t` over: the game's own check (talks), for a unit not on our side
-- and not hidden by the fog (a player knows no more than the fog shows).
local function mayTalkOver(ctx, u, t)
    return t.faction ~= "blue" and not t.fogged and talks(ctx, u, t)
end

-- The units able to act that could go and Talk `t` over (mayTalkOver, and `by` names them,
-- when given) with a way to it, in slot order: { { u, d = the march } }.
local function talkersOf(ctx, t, by)
    local out = {}
    for _, u in ipairs(ctx.actors) do
        if (not by or listed(by, u.charId)) and mayTalkOver(ctx, u, t) then
            local d = marchLength(ctx, u, t)
            if d then out[#out + 1] = { u = u, d = d } end
        end
    end
    return out
end

-- The units a player unit may Talk over (mayTalkOver), by id: a recruit lost to any blow spoils
-- the clear (botrun's recruits_missing), as a green unit's death does. Every blue counts, one
-- that has acted too: it Talks next turn, so its recruit is no less one after a replan.
-- -> out[id] = true, and talkers[id] = the player units' ids that may Talk it over (goals.lua's
-- takers).
local function recruitsOf(ctx)
    local out, talkers = {}, {}
    -- a carried recruit too (ctx.carried): a Drop sets it down to be talked to
    local units = {}
    for _, t in ipairs(ctx.onField) do units[#units + 1] = t end
    local carried = {}
    for id in pairs(ctx.carried or {}) do carried[#carried + 1] = id end
    table.sort(carried)
    for _, id in ipairs(carried) do units[#units + 1] = ctx.carried[id] end
    for _, t in ipairs(units) do
        for _, u in ipairs(ctx.blues) do
            if mayTalkOver(ctx, u, t) then
                out[t.id] = true
                talkers[t.id] = talkers[t.id] or {}
                table.insert(talkers[t.id], u.id)
            end
        end
    end
    return out, talkers
end

-- A recruit claim, before anything else: a talker it names (any the game lets, when it names
-- none) talks the recruit over when it can reach it, else the nearest such talker (by the
-- field from the recruit) marches on it.
local function recruitFirst(ctx, gate)
    for _, c in ipairs(ctx.style.recruits or {}) do
        for _, t in ipairs(ctx.onField) do
            if t.faction ~= "blue" and listed(c.units, t.charId) then
                -- the Talk is the game's own check (talkFrom), the field's way or not: the field
                -- is one class's costs, not the talker's; only the march needs a way
                for _, u in ipairs(ctx.actors) do
                    if not c.by or listed(c.by, u.charId) then
                        local a = talkFrom(ctx, u, t, gate)
                        if a then return a end
                    end
                end
                local near, nearD
                for _, p in ipairs(talkersOf(ctx, t, c.by)) do
                    if not nearD or p.d < nearD then near, nearD = p.u, p.d end
                end
                if near then
                    local field = fieldFor(ctx, t)
                    local allowed = {}
                    for _, tile in ipairs(waitTiles(ctx, near)) do
                        if gate(ctx, near, tile.x, tile.y, nil) then allowed[#allowed + 1] = tile end
                    end
                    local tile = #allowed > 0 and M.pickMove(allowed, { cur = near, goal = t,
                                                                        field = field })
                    return action(near, tile or { x = near.x, y = near.y }, "wait")
                end
            end
        end
    end
    return nil
end

-- A habit, no claim needed: any Talk the game offers to a unit not on our side is taken.
local function talkHabit(ctx, gate)
    for _, u in ipairs(ctx.actors) do
        for _, t in ipairs(ctx.onField) do
            if t.faction ~= "blue" then
                local a = talkFrom(ctx, u, t, gate)
                if a then return a end
            end
        end
    end
    return nil
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

-- The turns from `turn` to the next arrival `arrivals` (a style's reinforcements claims) cites,
-- or nil when none is left. botrun hashes it too: it is part of what decide reads.
function M.nextArrival(arrivals, turn)
    local best
    for _, turns in ipairs(arrivals or {}) do
        for _, t in ipairs(turns) do
            if t > turn and (not best or t < best) then best = t end
        end
    end
    return best and best - turn or nil
end

-- A reinforcements claim: the turn before any cited arrival, the march holds. The turn is
-- board.turn (decide has checked it is there).
local function holding(ctx) return M.nextArrival(ctx.style.arrivals, ctx.turn) == 1 end

local function march(ctx, u, gate, objective)
    local tiles, allowed = behindWalls(ctx, u, waitTiles(ctx, u)), {}
    for _, t in ipairs(tiles) do
        if gate(ctx, u, t.x, t.y, nil) then allowed[#allowed + 1] = t end
    end
    allowed = onTerrain(ctx, allowed)
    local goal = nil
    if not holding(ctx) then goal = marchGoal(ctx, u, objective) end
    if #allowed == 0 or not goal then
        -- nowhere is safe enough, or nothing to march to (or a hold): end where the worst
        -- case is smallest, the unit's own tile first on a tie (holding costs nothing)
        return safest(ctx, u, #allowed > 0 and allowed or tiles)
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
                    if a then return strikeAct(u, a) end
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

-- A healer's staff, once the fighters have acted: of the heals the game offers (sight.heals) from wait
-- tiles the gate allows, the one restoring the most HP -- the ally's missing HP up to the
-- staff's amount -- then the most wounded ally, then the safest tile. Slot order picks among
-- healers. nil when no ally is wounded or no healer reaches one.
local function staffHeal(ctx, gate, only)
    local missing, any = {}, false
    for _, b in ipairs(ctx.blues) do
        if b.maxhp and b.hp < b.maxhp then missing[b.id], any = b.maxhp - b.hp, true end
    end
    if not (any and ctx.sight.heals) then return nil end
    local best
    for _, u in ipairs(only and { only } or ctx.actors) do
        if #ctx.sight.staves(u) > 0 then
            for _, t in ipairs(waitTiles(ctx, u)) do
                if gate(ctx, u, t.x, t.y, nil) then
                    for _, h in ipairs(ctx.sight.heals(u, t.x, t.y)) do
                        for _, id in ipairs(h.targets) do
                            local gain = math.min(missing[id] or 0, h.amount)
                            local c = { u = u, tile = t, slot = h.slot, id = id, gain = gain,
                                        amount = h.amount,
                                        left = -(missing[id] or 0),
                                        worst = worstCase(ctx, u, t.x, t.y, nil).sum }
                            if gain > 0 and (not best or c.gain > best.gain
                                    or (c.gain == best.gain and (c.left < best.left
                                        or (c.left == best.left and c.worst < best.worst)))) then
                                best = c
                            end
                        end
                    end
                end
            end
        end
        if best then break end
    end
    if not best then return nil end
    local a = action(best.u, best.tile, "staff", nil)
    -- the amount too: the planner reads what the target is short by when the heal lands
    a.slot, a.targetId, a.gain, a.amount = best.slot, best.id, best.gain, best.amount
    for _, b in ipairs(ctx.blues) do
        if b.id == best.id then a.target = b.charId end
    end
    return a
end

-- A unit with no attack its style allows heals itself (sight.mend: a Vulnerary) on the safest
-- tile the gate allows, when it is down at least the item's whole amount -- no HP of it is
-- wasted. nil otherwise.
local function mend(ctx, u, gate)
    if not (ctx.sight.mend and u.maxhp) then return nil end
    local m = ctx.sight.mend(u)
    if not (m and u.maxhp - u.hp >= m.amount) then return nil end
    local allowed = {}
    for _, t in ipairs(waitTiles(ctx, u)) do
        if gate(ctx, u, t.x, t.y, nil) then allowed[#allowed + 1] = t end
    end
    local tile = safest(ctx, u, #allowed > 0 and allowed or waitTiles(ctx, u))
    local a = action(u, tile, "item", nil)
    a.slot, a.gain, a.amount = m.slot, math.min(u.maxhp - u.hp, m.amount), m.amount
    return a
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
    local pick = M.pickTarget(nil, targets, { weapons = ctx.sight.weapons(u),
        tilesFor = function(t) return strikeTiles(ctx, u, t.unit) end })
    if pick then return action(u, pick.tile, "attack", pick.target.unit, pick.slot) end
    local b = breach(ctx, u, function() return true end, objective)
    if b then return b end
    local goal = marchGoal(ctx, u, objective)
    local tile = M.pickMove(waitTiles(ctx, u), { cur = u, goal = goal,
                                                 field = fieldFor(ctx, goal), enemies = targets })
    return action(u, tile, "wait")
end

-- An experiment's benched unit (style.bench: a playthrough without it, botrun's api.bench)
-- only waits where it stands, and is still in the enemy's reach there: its wait, else nil.
-- Every way the bot acts reads it, the planner's candidates and decide alike, so a benched
-- run never plays the unit (PR #585 review: decide, the greedy style's and the planner's
-- fallback, played it).
local function benchedWait(ctx, u)
    if ctx.style and ctx.style.bench and listed(ctx.style.bench, u.charId) then
        return action(u, u, "wait")
    end
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
    for _, u in ipairs(ctx.actors) do
        local held = benchedWait(ctx, u)
        if held then return held end
    end
    local objective = sight.objective
    local s = seize(ctx)
    if s then return s end
    if not gate then return greedy(ctx, objective) end
    local recruit = recruitFirst(ctx, gate)
    if recruit then return recruit end

    local attacks = {}
    for _, u in ipairs(ctx.actors) do
        local a = bestAttack(ctx, u, gate)
        attacks[u] = a
        if a and a.sure then return strikeAct(u, a) end
    end
    local talk = talkHabit(ctx, gate)
    if talk then return talk end
    local claimed = claimedMove(ctx, gate)
    if claimed then return claimed end
    -- Healers act after the fighters, as a player heals after the attacks: the staff then
    -- covers what this phase's counters cost, before the enemy phase.
    local fighters = {}
    for _, c in ipairs(ctx.actors) do
        if not (sight.staves and #sight.staves(c) > 0) then fighters[#fighters + 1] = c end
    end
    if #fighters == 0 then
        local healed = staffHeal(ctx, gate)
        if healed then return healed end
    end
    -- the most threatened: the largest worst case where it stands, then the most coverage
    local pool = #fighters > 0 and fighters or ctx.actors
    local u, most, count = pool[1], 0, 0
    for _, c in ipairs(pool) do
        local w, d = worstCase(ctx, c, c.x, c.y, nil).sum, sight.danger(c.x, c.y)
        if w > most or (w == most and d > count) then u, most, count = c, w, d end
    end
    local a = attacks[u]
    if a then return strikeAct(u, a) end
    return mend(ctx, u, gate) or breach(ctx, u, gate, objective)
        or action(u, march(ctx, u, gate, objective), "wait")
end

-- Exploring (#510 step 9; Nicolas: a new player does not know the rewards, so it visits
-- every village and opens every chest it can): each village or chest still open
-- (sight.explorable) sends one unit the game lets use it (sight.canExplore) marching to it, the
-- nearest by the game's own field from the tile; each tile one unit, each unit one tile, the
-- nearest pair first. A Talk recruit comes before them all, paired with its talkers the same way.
-- ctx.exploreGoal[unit id] = the tile, which goalFor reads.
-- `sent` (the last plan's goals, { {id, x, y} }) is kept first: a unit sent to a tile keeps it
-- while the tile is open and the unit can still reach and use it, acted this turn or not.
-- Re-picking each decision handed ch02's (12,3) between two units, and no one reached it.
-- The game's check is a menu's, asked only of a unit that can act: an acted unit keeps its
-- tile on the path alone (asked anyway, ch02's turn-7 "no" was cached into turn 8).
-- A unit cut off from the tile is sent when breachFor finds the door or wall that opens the
-- way (the march then opens it, as for any goal): ch03's (6,12) chest sits behind a door,
-- and pairing only the units a path reached left it unopened in every attempt.
-- The villages and chests still worth a trip: what the game offers (sight.explorable) less
-- the tiles this run has already explored (ctx.explored), each with its worth and when it
-- closes (Goals.openTiles). A House keeps its Visit for good (eventinfo House(0, ...)):
-- vanilla Ch1's two held Seth and Eirika for nine turns.
local function openTiles(ctx) return Goals.openTiles(ctx.sight, ctx.style, ctx) end

-- What sending `u` to open tile `t` is worth: its gold x the chance `u` gets there (Goals.chance:
-- its own turns, none once a looter closes it first), and that chance. A unit cut off from it
-- goes through the breach (turnsFor).
local function sendWorth(ctx, u, t)
    local goal = { tile = { x = t.x, y = t.y }, closes = t.closes, takerUnits = { u } }
    local pos = { [u.id] = { x = u.x, y = u.y, acted = u.acted, alive = 1 } }
    local c = Goals.chance(goal, pos, Goals.GAMMA, ctx.turnsTo)
    return t.gold * c, c
end

local function exploring(ctx, sent, barred, guard)
    -- ctx.goalWhy[unit id]: why it was sent (Bot.explain): "guard" (the walker's), "recruit",
    -- or the open tile's kind
    ctx.exploreGoal, ctx.goalWhy = {}, {}
    barred = barred or {}
    local taken = {}
    -- `guard` (the look's walker, #510 W1; only the shadow look passes it): { {id, x, y} },
    -- a unit sent to the tile a watched enemy strikes from, before anything else. What it
    -- does there is the beam's choice.
    for _, g in ipairs(guard or {}) do
        for _, u in ipairs(ctx.blues) do
            if u.id == g.id and not ctx.exploreGoal[u.id] then
                taken[tileKey(g.x, g.y)], ctx.exploreGoal[u.id] = true, { x = g.x, y = g.y }
                ctx.goalWhy[u.id] = "guard"
            end
        end
    end
    local function reaches(u, t)
        if u.acted or ctx.sight.canExplore(u, t.x, t.y, t.kind) then return marchLength(ctx, u, t) end
        -- a chest it has no key for: by way of the enemy whose fall gives it one (turnsFor)
        return lockAt(ctx, u, t.x, t.y) and movesFor(ctx, u, t) or nil
    end
    -- each goal one unit, each unit one goal, the nearest pair first; `key` names a goal,
    -- `why` says what it is
    local function assign(pairs_, key, why)
        table.sort(pairs_, function(a, b)
            if (a.v or 0) ~= (b.v or 0) then return (a.v or 0) > (b.v or 0) end
            if a.d ~= b.d then return a.d < b.d end
            if a.u.slot ~= b.u.slot then return a.u.slot < b.u.slot end
            if a.t.y ~= b.t.y then return a.t.y < b.t.y end
            return a.t.x < b.t.x
        end)
        for _, p in ipairs(pairs_) do
            local k = key(p.t)
            if not taken[k] and not ctx.exploreGoal[p.u.id]
                and not barred[goalKey(p.u.id, p.t)] then
                taken[k], ctx.exploreGoal[p.u.id] = true, { x = p.t.x, y = p.t.y }
                ctx.goalWhy[p.u.id] = why(p.t)
            end
        end
    end
    -- A Talk recruit before any village: a unit that could Talk it over (talkersOf) marches on
    -- it, or the planner credits the Talk only once a talker happens into reach (vanilla Ch2:
    -- Ross, killed on turn 2 while Eirika marched on the brigands). A recruit the style claims
    -- goes to the claim's talker only, as recruitFirst marches it.
    local talkPairs = {}
    for _, t in ipairs(ctx.onField) do
        -- unclaimed: any talker; claimed: the first claim with a talker that can go, as
        -- recruitFirst falls through its claims in order
        local claims, talkers = claimsOn(ctx, "recruits", t), nil
        if #claims == 0 then talkers = talkersOf(ctx, t, nil) end
        for _, c in ipairs(claims) do
            talkers = talkersOf(ctx, t, c.by)
            if #talkers > 0 then break end
        end
        for _, p in ipairs(talkers) do
            talkPairs[#talkPairs + 1] = { t = t, u = p.u, d = p.d }
        end
    end
    assign(talkPairs, function(t) return "talk>" .. t.id end, function() return "recruit" end)
    if not ctx.sight.explorable then return end
    local pairs_ = {}
    local open, blues = {}, {}
    for _, t in ipairs(openTiles(ctx)) do open[tileKey(t.x, t.y)] = t end
    for _, u in ipairs(ctx.blues) do blues[u.id] = u end
    for _, g in ipairs(sent or {}) do
        local t, u = open[tileKey(g.x, g.y)], blues[g.id]
        if t and u and not taken[tileKey(t.x, t.y)] and not ctx.exploreGoal[u.id]
            and not barred[goalKey(u.id, t)]
            and reaches(u, t) and select(2, sendWorth(ctx, u, t)) > 0 then
            taken[tileKey(t.x, t.y)], ctx.exploreGoal[u.id] = true, { x = t.x, y = t.y }
            ctx.goalWhy[u.id] = t.kind
        end
    end
    -- each pair by what the trip is worth, the best first (a fast unit wins a race a nearer
    -- slow one would lose), the nearer on a tie
    for _, t in ipairs(openTiles(ctx)) do
        for _, u in ipairs(ctx.actors) do
            local d = reaches(u, t)
            if d then
                local v, c = sendWorth(ctx, u, t)
                if c > 0 then pairs_[#pairs_ + 1] = { t = t, u = u, d = d, v = v } end
            end
        end
    end
    assign(pairs_, function(t) return tileKey(t.x, t.y) end, function(t) return t.kind end)
end

-- Bot.explain's record as log lines (botrun's `stuck` log): the objective, the boss and its fog
-- state, and per unit its goal and why; montecarlo.py story prints the plans' records.
function M.explainLines(rec)
    local function at(t) return t and tileKey(t.x, t.y) or "-" end
    local o, b = rec.objective or {}, rec.boss
    local lines = { string.format("objective %s tile %s, turn %s", tostring(o.kind), at(o.tile),
                                  tostring(rec.turn)) }
    if b then
        lines[#lines + 1] = string.format("  boss id %d char 0x%02X @%s hp %d%s", b.id, b.charId,
            at(b), b.hp, b.fogged and (b.known and " in fog, remembered" or " in fog") or "")
    end
    for _, r in ipairs(rec.units) do
        lines[#lines + 1] = string.format("  unit %d char 0x%02X @%s: goal %s (%s%s)", r.id,
            r.charId, at(r), at(r.goal), tostring(r.source), r.by and (" " .. r.by) or "")
    end
    return lines
end

-- Why each unit goes where it goes (#510 W1; Nicolas, 2026-11-11: the probe that explained Ch6,
-- kept). -> { turn, objective = { kind, tile }, boss = the Defeat Boss map's boss as the board
-- has it: { id, charId, x, y, hp, fogged (the game hides it), known (a retry remembers it,
-- sight.knows) } | nil, units = per blue unit on the field { id, charId, x, y, hp, acted,
-- goal = its march's tile, source = why that tile: "guard" (the look's walker sent it),
-- "recruit", a village or chest's kind, "objective" (the objective's own tile), "boss",
-- "enemy" (its nearest in sight), "unseen" (the fog's nearest tile), nil for none; by = the
-- enemy's id for "boss" and "enemy" } }.
-- `view` (the planner's, for a plan's record): { ctx = Bot.candidates' ctx, acts = the plan's,
-- progress = unit id -> the turns the plan cuts from its way to its goal, forward = fn(unit)
-- -> its forward steps (acts nearer its goal) offered, and those within the style's cap }; each
-- unit then also says its act, why and end tile (`to`), `progress`, `offered`, `admitted`.
-- With no view (a run that ends `stuck`, botrun's log), `lines` adds what decide weighs per
-- blue unit: its wait tiles and how many the style's gate allows, the march goal, the obstacle
-- that opens the way to it when it is cut off, and the field distance from the goal (where it
-- stands, the best wait tile, the best allowed one), and per enemy it can strike, the tiles in
-- range, how many the gate allows, and the best (largest-margin) exchange: our hit/damage and
-- its counter against our HP.
function M.explain(board, sight, style, view)
    local ctx = view and view.ctx or context(board, sight)
    if not view then ctx.style, ctx.turn = style, board.turn end
    local o = sight.objective or {}
    local rec = { turn = board.turn, units = {},
                  objective = { kind = o.kind, tile = o.tile and { x = o.tile.x, y = o.tile.y } } }
    for _, u in ipairs(board.units) do
        if o.boss and u.faction == "red" and u.charId == o.boss and u.onField and not u.dead then
            rec.boss = { id = u.id, charId = u.charId, x = u.x, y = u.y, hp = u.hp,
                         fogged = u.fogged == true,
                         known = (u.fogged and sight.knows and sight.knows(u)) == true }
        end
    end
    local acts = {}
    for _, a in ipairs(view and view.acts or {}) do acts[a.unitId] = a end
    for _, u in ipairs(ctx.blues) do
        local goal, source, by
        if ctx.exploreGoal and ctx.exploreGoal[u.id] then
            goal, source = ctx.exploreGoal[u.id], ctx.goalWhy and ctx.goalWhy[u.id]
        else
            goal, source, by = objectiveGoal(ctx, u, o)
        end
        local r = { id = u.id, charId = u.charId, x = u.x, y = u.y, hp = u.hp,
                    acted = u.acted and true or nil, source = source, by = by,
                    goal = goal and { x = goal.x, y = goal.y } }
        local a = acts[u.id]
        if a then
            local t = Board.endTile(a)
            r.act, r.why, r.to = a.act, a.why, { x = t.x, y = t.y }
        end
        if view then
            r.progress = view.progress[u.id]
            r.offered, r.admitted = view.forward(u)
        end
        rec.units[#rec.units + 1] = r
    end
    if view then return rec end
    rec.lines = M.explainLines(rec)
    local gate = GATES[style.aggression] or GATES.bold
    local function at(t) return t and tileKey(t.x, t.y) or "-" end
    local lines = rec.lines
    for _, e in ipairs(ctx.enemies) do
        lines[#lines + 1] = string.format("  red id %d char 0x%02X class 0x%02X @%s hp %d%s",
            e.id, e.charId, e.classId or 0, at(e), e.hp, e.isBoss and " BOSS" or "")
    end
    for _, u in ipairs(ctx.blues) do
        local tiles, allowed = waitTiles(ctx, u), {}
        for _, t in ipairs(tiles) do
            if gate(ctx, u, t.x, t.y, nil) then allowed[#allowed + 1] = t end
        end
        local goal = goalFor(ctx, u, o)
        local field = fieldFor(ctx, goal)
        local function fd(t) return field and field[t.y] and field[t.y][t.x] end
        local function nearest(list)
            local best
            for _, t in ipairs(list) do
                local d = fd(t)
                if d and (not best or d < best) then best = d end
            end
            return best
        end
        lines[#lines + 1] = string.format(
            "  blue char 0x%02X @%s hp %d%s: wait %d allowed %d, goal %s, breach %s, field here "
            .. "%s best wait %s best allowed %s, worst here %d", u.charId, at(u), u.hp,
            u.acted and " acted" or "", #tiles, #allowed, at(goal), at(breachFor(ctx, u, goal)),
            tostring(fd(u)),
            tostring(nearest(tiles)), tostring(nearest(allowed)),
            worstCase(ctx, u, u.x, u.y, nil).sum)
        local weapons = ctx.sight.weapons(u)
        for _, e in ipairs(ctx.enemies) do
            local n, pass, best = 0, 0, nil
            for _, t in ipairs(strikeTiles(ctx, u, e)) do
                for _, w in ipairs(weapons) do
                    local f = attack(ctx, u, e, t.x, t.y, w.slot)
                    if f then
                        n = n + 1
                        local spent = f.counterWorst
                        if spent < u.hp and gate(ctx, u, t.x, t.y, f.sure and e or nil,
                                                 spent) then
                            pass = pass + 1
                        end
                        if not best or u.hp - spent > best.margin then
                            best = { margin = u.hp - spent, f = f, spent = spent, t = t }
                        end
                    end
                end
            end
            if n > 0 then
                local f = best.f
                lines[#lines + 1] = string.format(
                    "    vs 0x%02X: %d tiles, %d allowed; best @%s hit %d dmg %dx%d, counter "
                    .. "worst %d of hp %d", e.charId, n, pass, at(best.t), f.hit, f.dmg, f.hits,
                    best.spent, u.hp)
            end
        end
    end
    return rec
end

-- Canto (playerphase.c TryMakeCantoUnit): per act in `acts` after which the game hands `u` a
-- second move (sight.cantoTiles: a Canto unit's Rescue, Drop, Visit, Chest or Talk with Mov
-- left), variants that move on (`canto`, the tile): the M.HOLDS safest tiles the game's map
-- offers from the act's tile and the one that gains the most ground (`gain`, the march's),
-- the safest of those on a tie. Staying is the plain act. Which is played is the planner's:
-- the judged phase reads what each leaves (ADR 0396). Nicolas (#510): Canto is a decision,
-- not a rule that always flies back.
local function cantoMoves(ctx, u, acts, gain)
    local out = {}
    if not ctx.sight.cantoTiles then return out end
    local s = ctx.seizeTile
    local barred = s and not canSeize(ctx, u)
    for _, a in ipairs(acts) do
        -- the act's own tile is in the set an avoid claim is asked about, then left out:
        -- staying is the plain act, so where it is clear, no move into reach is offered
        -- (outOfReach gives every tile back only when none is clear)
        local tiles = { { x = a.move.x, y = a.move.y } }
        for _, t in ipairs(ctx.sight.cantoTiles(u, a)) do
            if not (t.x == a.move.x and t.y == a.move.y)
                    and not (barred and t.x == s.x and t.y == s.y) then
                tiles[#tiles + 1] = t
            end
        end
        -- an avoid claim holds here as on every end tile (outOfReach, waitTiles' first rule):
        -- the second move is a move like the first
        local moves = {}
        for _, t in ipairs(#tiles > 1 and outOfReach(ctx, u, tiles) or {}) do
            if not (t.x == a.move.x and t.y == a.move.y) then moves[#moves + 1] = t end
        end
        local ranked = bySafety(ctx, u, moves)
        local pick = {}
        for i = 1, math.min(M.HOLDS, #ranked) do pick[#pick + 1] = ranked[i] end
        local front, fg
        for _, t in ipairs(ranked) do
            local g = gain(t.x, t.y)
            if g > 0 and (not fg or g > fg) then front, fg = t, g end
        end
        if front then pick[#pick + 1] = front end
        for _, t in ipairs(pick) do
            local v = {}
            for k, x in pairs(a) do v[k] = x end
            v.canto = { x = t.x, y = t.y }
            out[#out + 1] = v
        end
    end
    return out
end

-- `acts` of `u`, each told the ally its act's tile asks to move (`vacate`) and what can strike
-- it where it ends (Board.endTile: a Canto move's tile) next phase (`exposure`, each enemy's own
-- strike: the planner's odds).
local function exposed(ctx, u, acts)
    for _, a in ipairs(acts) do
        local friend = vacated(ctx, u, a.move.x, a.move.y)
        a.vacate = friend and friend.id
        a.exposure = {}
        local held = a.act == "attack" and a.slot or nil
        local at = Board.endTile(a)
        for _, s in ipairs(exposure(ctx, u, at.x, at.y, held)) do
            a.exposure[#a.exposure + 1] = { id = s.by.id, dist = s.f.takenDist }
        end
    end
    return acts
end

-- One unit's acts this phase, from the view `ctx` holds (M.candidates' doc below says what
-- each is).
local function proposeOne(ctx, u)
    local held = benchedWait(ctx, u)
    if held then
        held.why = "hold"
        return { unit = u, acts = exposed(ctx, u, { held }) }
    end
    local sight, objective = ctx.sight, ctx.sight.objective
    local open = function() return true end
    local acts, seen = {}, {}
    local function add(a, why)
        if not a then return end
        local k = a.act .. "@" .. a.move.x .. "," .. a.move.y .. ">" .. tostring(a.targetId)
            .. (a.obstacle and (a.obstacle.x .. "," .. a.obstacle.y) or "")
            .. (a.dropAt and ("/" .. a.dropAt.x .. "," .. a.dropAt.y) or "")
            .. (a.canto and ("~" .. a.canto.x .. "," .. a.canto.y) or "")
        if seen[k] then return end
        seen[k] = true
        a.why = why
        acts[#acts + 1] = a
    end
    local s = ctx.seizeTile
    if s and canSeize(ctx, u) then
        for _, t in ipairs(endTiles(ctx, u)) do
            if t.x == s.x and t.y == s.y then add(action(u, t, "seize"), "seize") end
        end
    end
    -- per enemy, three strikes: the best, the least exposed to the enemy phase (`safe`), and
    -- the least likely to die by its own counter (`guard`, exposure breaking its ties). These
    -- attacks are `priced` (a counter that can kill is offered, ADR 0396), so either risk can
    -- be the one that matters; the planner weighs both, and ranking one strike by both would
    -- drop the other's best (PR #585 review and re-review).
    local best, safe, guard = {}, {}, {}
    for _, c in ipairs(attackOptions(ctx, u, open, true)) do
        local e = c.target
        if not best[e] or betterAttack(c, best[e]) then best[e] = c end
        c.worst = worstCase(ctx, u, c.tile.x, c.tile.y, c.sure and e or nil).sum
        if not safe[e] or c.worst < safe[e].worst then safe[e] = c end
        local g = guard[e]
        if not g or c.f.die < g.f.die or (c.f.die == g.f.die and c.worst < g.worst) then
            guard[e] = c
        end
    end
    local function offer(c)
        local a = strikeAct(u, c)
        a.f, a.spent, a.first = c.f, c.spent, c.first
        add(a, "attack")
    end
    for _, e in ipairs(ctx.enemies) do      -- board order: a plan never depends on `pairs`
        for _, list in ipairs({ best, safe, guard }) do
            if list[e] then offer(list[e]) end
        end
    end
    -- the boss from every tile: the planner's assault seats several strikers around it,
    -- and two tiles per unit gave them all the same one (Manchego Stars ch03's corner Mogall: three
    -- of six strikers dropped, the rest of its tiles empty)
    for _, c in ipairs(attackOptions(ctx, u, open, true)) do
        if c.target.isBoss then offer(c) end
    end
    add(breach(ctx, u, open, objective), "breach")
    for _, t in ipairs(ctx.onField) do
        if t.faction ~= "blue" then add(talkFrom(ctx, u, t, open), "talk") end
    end
    for _, a in ipairs(rescues(ctx, u, open)) do add(a, "rescue") end
    for _, a in ipairs(drops(ctx, u, open)) do add(a, "drop") end
    add(staffHeal(ctx, open, u), "heal")
    -- a heal the plan may need after its blows land: per ally the game would let `u`
    -- heal were it hurt, from the safest tile that reaches it
    if ctx.sight.heals and ctx.sight.staves and #ctx.sight.staves(u) > 0 then
        local others, best = {}, {}
        for _, b in ipairs(ctx.blues) do
            if b ~= u then others[#others + 1] = b end
        end
        for _, t in ipairs(waitTiles(ctx, u)) do
            local w = worstCase(ctx, u, t.x, t.y, nil).sum
            for _, h in ipairs(ctx.sight.heals(u, t.x, t.y, others)) do
                for _, id in ipairs(h.targets) do
                    if not best[id] or w < best[id].w then
                        best[id] = { w = w, tile = t, slot = h.slot, amount = h.amount }
                    end
                end
            end
        end
        for _, b in ipairs(others) do
            local c = best[b.id]
            if c then
                local a = action(u, c.tile, "staff", b)
                a.slot, a.amount = c.slot, c.amount
                add(a, "heal")
            end
        end
    end
    add(mend(ctx, u, open), "mend")
    -- a village or chest the game lets `u` use, from the tile itself (whether it is worth
    -- the trip is the planner's: its worth against the unit's risk there, goals.lua)
    if ctx.sight.explorable then
        local ends = {}
        for _, t in ipairs(endTiles(ctx, u)) do ends[tileKey(t.x, t.y)] = true end
        for _, t in ipairs(openTiles(ctx)) do
            if ends[tileKey(t.x, t.y)] and ctx.sight.canExplore(u, t.x, t.y, t.kind) then
                add(action(u, t, t.kind), "explore")
            end
        end
    end
    -- the march over every tile, and over free tiles only: a tile an ally may vacate is
    -- an extra way forward, never the only one (vanilla Ch3: Eirika held behind the army
    -- for five turns, the throne open, every forward tile an ally's who stayed put)
    add(action(u, march(ctx, u, open, objective), "wait"), "march")
    ctx.freeOnly = true
    add(action(u, march(ctx, u, open, objective), "wait"), "march")
    ctx.freeOnly = nil
    local holds = bySafety(ctx, u, waitTiles(ctx, u))
    add(holds[1] and action(u, holds[1], "wait"), "hold")
    -- progress: how much nearer its march goal (the game's field to it) each act ends it
    local goal = marchGoal(ctx, u, objective)
    local field = fieldFor(ctx, goal)
    local function fd(x, y)
        if field then return field[y] and field[y][x] end
        return goal and manhattan(x, y, goal.x, goal.y)
    end
    local here = fd(u.x, u.y)
    local function gain(x, y)
        local there = fd(x, y)
        return (here and there) and (here - there) or 0
    end
    -- the retreat: the safest tile that still gains ground, the most ground on a tie, so a
    -- unit has a way forward that is not the march's exposed front
    local function retreatOver(tiles)
        local retreat, rw, rg
        for _, t in ipairs(tiles) do
            local g = gain(t.x, t.y)
            if g > 0 then
                local w = worstCase(ctx, u, t.x, t.y, nil).sum
                if not rw or w < rw or (w == rw and g > rg) then retreat, rw, rg = t, w, g end
            end
        end
        return retreat
    end
    local retreat = retreatOver(waitTiles(ctx, u))
    if retreat then add(action(u, retreat, "wait"), "retreat") end
    ctx.freeOnly = true
    retreat = retreatOver(waitTiles(ctx, u))
    ctx.freeOnly = nil
    if retreat then add(action(u, retreat, "wait"), "retreat") end
    -- the next safest holds too: another unit the plan moves first may take the safest,
    -- and with one hold the unit had only exposed tiles left (Manchego Stars ch03: Braulo, at 16
    -- HP, parked beside the Mogall at an 81% chance to die while a safe tile stood free)
    for i = 2, math.min(M.HOLDS, #holds) do add(action(u, holds[i], "wait"), "hold") end
    for _, a in ipairs(cantoMoves(ctx, u, acts, gain)) do add(a, a.why) end
    return { unit = u, acts = exposed(ctx, u, acts) }
end

-- Every unit's acts (proposeOne). Given the last proposal `last` and the goals it was made for
-- (`was`, ctx.exploreGoal then), only the units whose goal has changed since are proposed again.
local function propose(ctx, last, was)
    local out, kept = {}, {}
    for _, c in ipairs(last or {}) do
        local a, b = was[c.unit.id], ctx.exploreGoal[c.unit.id]
        if (a == nil) == (b == nil) and (not a or (a.x == b.x and a.y == b.y)) then
            kept[c.unit.id] = c
        end
    end
    for _, u in ipairs(ctx.actors) do out[#out + 1] = kept[u.id] or proposeOne(ctx, u) end
    return out
end

-- Whether `u` can get nearer goal tile `g` this turn by the game's turns (ctx.turnsTo) or take
-- it: it stands on it, a tile it may end on is nearer, or, with a recruit standing on `g` (a
-- tile no player unit ends on), it may end beside it, where a Talk is made. A unit with no tile
-- but its own is boxed in, and counts as able: no other goal would get it anywhere either. The
-- turns are the terrain's alone, so what stops a unit with moves is a unit in its way.
local function stepsToward(ctx, u, g)
    local now = ctx.turnsTo(u, g)
    if now and now <= Goals.DUST then return true end
    local there = ctx.standing[tileKey(g.x, g.y)]
    -- a recruit (recruitsOf: one a player unit may Talk over), not any unit: an enemy holding
    -- a village is no goal reached by standing beside it
    local recruit = there and ctx.recruits[there.id]
    local boxed = true
    for _, t in ipairs(endTiles(ctx, u)) do
        if recruit and manhattan(t.x, t.y, g.x, g.y) == 1 then return true end
        if t.x ~= u.x or t.y ~= u.y then
            boxed = false
            local n = now and ctx.turnsTo(u, g, t)
            if n and n < now - Goals.DUST then return true end
        end
    end
    return boxed
end

-- The planner's proposals (#510 step 9, the planner): per unit still able to act, the acts the
-- rules above would consider, with no style gate -- the planner weighs the risk itself. Per
-- target, the attack betterAttack ranks first and the one from the safest tile; a breach,
-- every Talk the game offers, each Rescue of a green unit and each Drop of the unit it carries
-- the game offers (rescues, drops), its best heal, a Vulnerary, a Visit or Chest on each open tile
-- it reaches (sight.canExplore), the march (to its exploring tile when it was sent to one), the
-- hold, the retreat and a Seize. Each act carries `why`, its `progress` and its end tile's `exposure` (each enemy
-- that can strike it there next phase); an attack its forecast (`f`) and counter worst case
-- (`spent`).
-- opts (botrun's memory of the run, nil for none): `sent`, the last plan's goals, the tiles
-- units were already sent to (exploring keeps them); `explored`, the "x,y" tiles this run
-- has visited or opened (never offered again); `lost`, the "x,y" tiles closed before we took
-- them ("x,y" -> kind; a reward needing one is gone); `stalled`, the board repeats (an avoid
-- claim gives way); `stuck`, the last call's ctx.stuck ("unit id>x,y" -> { id, x, y, since }:
-- each goal a unit was found with no step toward, and the turn it was first found so); `guard`,
-- the look's walker's units sent to a strike's tile (exploring); `aim` = "boss", the look's boss
-- alternative: a remembered boss in fog is a march goal (objectiveGoal).
-- -> { { unit, acts } }, ctx (the planner scores with the same view; ctx.recruits, recruitsOf's
-- ids, are the units a player blow must not kill; ctx.recruitTalkers who may Talk each over).
function M.candidates(board, sight, style, opts)
    local ctx = context(board, sight)
    ctx.style, ctx.turn = style, board.turn
    ctx.explored = opts and opts.explored or {}
    ctx.seen = opts and opts.seen
    ctx.lost = opts and opts.lost or {}
    ctx.stalled = opts and opts.stalled
    ctx.aimBoss = opts and opts.aim == "boss" or nil
    -- memoised for the decision (turnsFor's ctx.keyTurns): the planner asks it per goal, taker
    -- and partial plan, and a unit cut off goes through breachFor and the field again each time
    ctx.keyTurns = {}
    ctx.turnsTo = function(u, tile, from) return turnsFor(ctx, u, tile, from) end
    ctx.recruits, ctx.recruitTalkers = recruitsOf(ctx)
    -- each unit's way to the objective, for the goals (goals.lua)
    ctx.objectiveTile = function(u) return objectiveTile(ctx, u, sight.objective) end
    -- A unit sent where it has had no step nearer since an earlier turn is sent again,
    -- elsewhere or to the objective (FR-016): a goal it cannot step toward would hold it in
    -- place for good. One turn blocked is only a unit in the way, so it holds that turn: re-
    -- sending at once handed a tile between units (ch02's (12,3), which `sent` was made to
    -- stop). opts.stuck (botrun's memory, the last plan's `stuck`) holds each blocked goal and
    -- the turn it was first found blocked; each is tested again here, and kept while it still
    -- is, so a bar lifts once the way opens. ctx.stuck is the record to carry on.
    local turn, byId = board.turn or 0, {}
    for _, u in ipairs(ctx.blues) do byId[u.id] = u end
    local actor = {}
    for _, u in ipairs(ctx.actors) do actor[u.id] = true end
    ctx.stuck = {}
    for k, e in pairs(opts and opts.stuck or {}) do
        local u = byId[e.id]
        -- a unit that has acted keeps its record until it can move again
        if u and (not actor[u.id] or not stepsToward(ctx, u, e)) then ctx.stuck[k] = e end
    end
    local barred, out = {}, nil
    for _ = 0, #ctx.actors do
        for k, e in pairs(ctx.stuck) do
            if e.since < turn then barred[k] = true end
        end
        local before = ctx.exploreGoal
        exploring(ctx, opts and opts.sent, barred, opts and opts.guard)
        out = propose(ctx, out, before)
        local more = false
        for _, c in ipairs(out) do
            local g = ctx.exploreGoal[c.unit.id]
            local k = g and goalKey(c.unit.id, g)
            if g and not stepsToward(ctx, c.unit, g) then
                ctx.stuck[k] = ctx.stuck[k] or { id = c.unit.id, x = g.x, y = g.y, since = turn }
                more = more or (ctx.stuck[k].since < turn and not barred[k])
            end
        end
        if not more then break end
    end
    return out, ctx
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
    -- the carried units go AHEAD of any other claim's: Bot.team takes style.deploy in list
    -- order, so appended they were cut whenever an earlier list already filled the cap
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
        local out = withEntry(style, "arrivals", needIds(claim, "turns", "{arrival turns}"))
        -- the waves themselves (campaign_env: who arrives where), for the goals' closings
        out.waves = copyList(style.waves)
        for _, w in ipairs(claim.waves or {}) do out.waves[#out.waves + 1] = w end
        return out
    end,
    -- an end-of-chapter reward (the game gives `item` when every goal `needs` names is taken)
    reward = function(claim, style)
        if not isInteger(claim.item) then malformed(claim, "needs item = an item id") end
        if claim.needs ~= "villages" and claim.needs ~= "chests" and type(claim.needs) ~= "table" then
            malformed(claim, "needs needs = villages | chests | { {x, y} }")
        end
        return withEntry(style, "rewards", { item = claim.item, needs = claim.needs })
    end,
    recruit = function(claim, style)
        local by = claim.by ~= nil and needIds(claim, "by", "{charIds}") or nil
        return withEntry(style, "recruits", { units = needIds(claim, "unit", "{charIds}"),
                                              by = by })
    end,
    keys = function(_claim, style)
        local out = {}
        for k, v in pairs(style) do out[k] = v end
        out.keys = true
        return out
    end,
    heal = function(claim, style) return withEntry(style, "heals", { vs = needVs(claim) }) end,
    avoid = byUnit("avoids"),
    priority = function(claim, style)
        return withEntry(style, "priorities", { vs = needVs(claim) })
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

function M.team(t)
    local roster, cap, maxima = t.roster, t.cap, t.maxima
    local deploy, reasons, taken, count = {}, {}, {}, {}
    for _, u in ipairs(roster) do
        if u.group == nil then
            error(string.format("bot.lua: unit 0x%02X has no team group", u.charId), 2)
        end
    end
    local function fits(u)
        return not taken[u.charId] and #deploy < cap
            and (maxima[u.group] == nil or (count[u.group] or 0) < maxima[u.group])
    end
    local function take(u, reason)
        taken[u.charId] = true
        count[u.group] = (count[u.group] or 0) + 1
        deploy[#deploy + 1] = u.charId
        reason.carried = t.carried[u.charId] == true
        reasons[u.charId] = reason
    end
    local left = {}
    for _, d in ipairs(t.demands) do left[d.id] = d.need end
    local function answers(u, id)
        return (t.answers[u.charId] or {})[id] == true
    end
    local function settle(u)
        for _, d in ipairs(t.demands) do
            if answers(u, d.id) and left[d.id] > 0 then left[d.id] = left[d.id] - 1 end
        end
    end
    -- the best unit by `key` (higher wins), ties to a carried unit, then slot order
    local function best(key)
        local top, topKey
        for _, u in ipairs(roster) do
            if fits(u) then
                local k = key(u)
                if k > 0 and (not top or k > topKey
                        or (k == topKey and t.carried[u.charId] and not t.carried[top.charId])) then
                    top, topKey = u, k
                end
            end
        end
        return top
    end

    for _, u in ipairs(roster) do
        if u.forced and not taken[u.charId] then
            take(u, { why = "forced" })
            settle(u)
        end
    end
    for _, charId in ipairs(t.style.deploy or {}) do
        for _, u in ipairs(roster) do
            if u.charId == charId and fits(u) then
                take(u, { why = "claim" })
                settle(u)
                break
            end
        end
    end
    while true do
        local u = best(function(c)
            local n = 0
            for _, d in ipairs(t.demands) do
                if left[d.id] > 0 and answers(c, d.id) then n = n + 1 end
            end
            return n
        end)
        if not u then break end
        local covered = {}
        for _, d in ipairs(t.demands) do
            if left[d.id] > 0 and answers(u, d.id) then covered[#covered + 1] = d.id end
        end
        take(u, { why = "covers", demands = covered })
        settle(u)
    end
    local biggest
    for _, d in ipairs(t.demands) do
        if not biggest or d.need > biggest.need then biggest = d end
    end
    while true do
        local u = best(function(c)
            -- every unit fills; its strength on the biggest demand ranks it
            return 1 + (biggest and ((t.strength or {})[c.charId] or {})[biggest.id] or 0)
        end)
        if not u then break end
        take(u, { why = "fill" })
    end
    return { deploy = deploy, reasons = reasons, give = {} }
end

-- the cheapest stock entry `want` accepts, at `u`'s prices
local function cheapest(stock, u, want)
    local best
    for _, s in ipairs(stock) do
        if want(s) and (not best or s.price[u.charId] < best.price[u.charId]) then best = s end
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
    local out = {}
    local function buy(u, s)
        if not s or s.price[u.charId] > gold then return end
        gold = gold - s.price[u.charId]
        out[#out + 1] = { unit = u.charId, item = s.item }
    end
    for _, u in ipairs(party) do
        if not holdsAny(u, function(it) return it.kind == "vulnerary" end) then
            buy(u, cheapest(stock, u, function(s) return s.kind == "vulnerary" end))
        end
    end
    for _, u in ipairs(party) do
        local usable = function(s) return s.type ~= nil and (u.canUse or {})[s.item] end
        local types, seen = {}, {}
        for _, s in ipairs(stock) do
            if usable(s) and not seen[s.type] then
                seen[s.type] = true
                types[#types + 1] = s.type
            end
        end
        table.sort(types)
        for _, t in ipairs(types) do
            if not holdsAny(u, function(it) return it.type == t end) then
                buy(u, cheapest(stock, u, function(s) return usable(s) and s.type == t end))
            end
        end
    end
    return out
end

function M.promote(unit, items)
    for _, it in ipairs(items) do
        if it.promotes then return true end
    end
    return false
end

function M.promoteOrder(units) return byLevel(units) end

-- A weapon's own reach and bonus damage, against the unit's other weapons of its type: what a
-- higher rank cannot replace (a Javelin's range, an Armorslayer's effectiveness).
local function special(w, others)
    local reach, kinds = 0, {}
    for _, o in ipairs(others) do
        if o ~= w then
            reach = math.max(reach, o.maxRange or 1)
            if o.effective then kinds[o.effective] = true end
        end
    end
    return (w.maxRange or 1) > reach or (w.effective ~= nil and not kinds[w.effective])
end

function M.fullBag(held, new, convoyFull)
    local function usableOfType(t)
        local out = {}
        for _, it in ipairs(held) do
            if it.kind == "weapon" and it.usable and it.type == t then out[#out + 1] = it end
        end
        return out
    end
    local heals = {}
    for _, it in ipairs(held) do
        if it.kind == "heal" then heals[#heals + 1] = it end
    end
    -- is the new item wanted, and which carried weapon it beats (nil: it beats none)
    local wanted, beaten = false, nil
    if new.kind == "heal" then
        wanted = #heals == 0
    elseif new.kind == "key" then
        wanted = true
    elseif new.kind == "weapon" and new.usable then
        local same = usableOfType(new.type)
        local with = { new }
        for _, w in ipairs(same) do with[#with + 1] = w end
        if #same == 0 or special(new, with) then
            wanted = true
        else
            for _, w in ipairs(same) do
                if not special(w, with) and (w.rank or 0) < (new.rank or 0)
                        and (not beaten or (w.rank or 0) < (beaten.rank or 0)) then
                    beaten = w
                end
            end
            wanted = beaten ~= nil
        end
    end
    if not wanted then return 0, "the new item is not needed in hand" end
    -- what may leave, in order
    local function first(test)
        for i, it in ipairs(held) do
            if test(it) then return i end
        end
        return nil
    end
    local spareHeal
    if #heals > 1 then
        for i, it in ipairs(held) do
            if it.kind == "heal" and (not spareHeal or (it.uses or 0) < (held[spareHeal].uses or 0)) then
                spareHeal = i
            end
        end
    end
    local unusable
    for i, it in ipairs(held) do
        if it.kind == "weapon" and not it.usable
                and (not unusable or (it.rank or 0) < (held[unusable].rank or 0)) then
            unusable = i
        end
    end
    local beatenAt = beaten and first(function(it) return it == beaten end)
    local order
    if convoyFull then
        -- a discard: duplicates and low tiers go; money, keys and the rest never do
        order = { { beatenAt, "a weapon it beats" }, { spareHeal, "a spare healing item" },
                  { unusable, "a weapon the unit cannot use" } }
    else
        order = { { first(function(it) return it.kind == "money" end), "money" },
                  { first(function(it) return it.kind == "other" end), "a seal or booster" },
                  { unusable, "a weapon the unit cannot use" },
                  { spareHeal, "a spare healing item" }, { beatenAt, "a weapon it beats" } }
    end
    for _, o in ipairs(order) do
        if o[1] then return o[1], o[2] end
    end
    return 0, "everything carried is needed"
end

function M.route(options, style)
    local r = style.route
    if type(r) ~= "number" or r < 1 or r > #options or r % 1 ~= 0 then
        error("bot.lua: route " .. tostring(r) .. " is not an index into " .. #options
            .. " options")
    end
    return r
end

return M
