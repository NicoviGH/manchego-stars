-- bot.lua -- the bot's policy, PURE (#510 step 9; the greedy clear-bot core since #60).
--
-- No emulator: every input is a plain table, so tools/playtest/test_bot.lua runs it with a
-- fake `sight`. The bot plays the game and re-creates none of it: whether a tile is in danger,
-- what a fight does and what the chapter asks for are read from the game's memory by the
-- caller and handed in as `sight`. This file only chooses.
--
-- ── Bot.decide(board, sight, style, opts) -> action | nil ──────────────────────────────────
--   board: Board.read's shape (board.lua). Blue units on the field that have not acted are the
--          ones that can act; on-field reds are the enemies.
--   opts (optional): { unpaid = { ["<talker charId>><target charId>"] = true } }, the Talks
--          this attempt that recruited no one (botrun's, #679), offered no more; and, for
--          Bot.candidates, pending = { { charId, x, y, turn } }: owed recruits an earlier attempt
--          saw arrive (botrun's pendingRecruits, ADR 0436).
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
--              bmreliance.h) of either; strikes keyed by the exchange, every unit that is not
--              red and the reds the enemy's strike can read (strikeScope: range + 3 of the
--              tile, MOV + 1 of the enemy, a blue's flood; the whole board for a staff, a
--              ballista or a script that reads reds).
--              Reach and worst case are per call only.
--            itemReach(unit) -> the widest max range of a weapon item in its bag, and
--              readsReds(unit) -> bool (a staff, a ballista or a script that reads reds anywhere),
--              OPTIONAL: both keep the strike memo narrow; without either it keys the whole board.
--              strikeCheck = {}|nil: PT_STRIKECHECK's log (a memo hit is also read and a read
--              that differs is appended as a line).
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
--   "talk" and "staff" are acts the claim behaviours add; "visit", "chest", "rescue",
--   "drop" (a Drop's `dropAt` is the tile it sets the carried unit on) and "supply" (the
--   convoy's door key taken, `item`/`uses`, then Wait: supplyKey) only the planner's
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
--   canUse = {[item] = true}, items = {{ id, uses, kind, type = weaponType|"staff"|nil,
--   usable, vulnerary = true|nil, maxUses, use = "seal"|"booster"|nil, promotes = bool|nil,
--   gains = bool|nil }...} }: each item is the game's facts about it for THIS unit (harness.lua
--   unitItemFacts). `canUse` is the game's can-use (a weapon's CanUnitUseWeapon, a staff's
--   CanUnitUseStaff) for this unit over the stock; `use` says the item is a seal or a booster
--   (the game's own Use switch); `promotes` is the game's promotion-item check for THIS unit
--   (class and level), asked only of a seal, and `gains` its stat-gain check, only of a
--   booster (ADR 0418).
-- stock entry: { item, price = {[charId] = n}, type = weaponType|"staff"|nil, vulnerary = true|nil };
--   price is the game's for each buyer (GetItemPurchasePrice reads the unit: a Silver Card
--   halves it). The caller says which stock item is the Vulnerary, so no item id lives here.
-- Bot.team(t) -> { deploy = {charIds}, reasons = {[charId] = reason}, give = {} }: whom the
--   prep screen fields (#510 plan comment, "Party selection"). t = { roster, cap,
--   maxima = {[group] = n}, demands = {{ id, kind, need, locks }...}, answers = {[charId] =
--   {[demandId] = true}}, strength = {[charId] = {[demandId] = n}}, carried = {[charId] = true},
--   style }. Each roster entry carries `group`, the
--   caller's read of team_groups.py (the bot weighs no class); a unit without one raises.
--   A demand is what the map asks (an enemy class, chests, fog...), `kind` sight.demandsOf's
--   name for what it is ("enemy" for an enemy class; a demand without one raises), `need` how
--   many answerers cover it (`locks`, a chests or doors demand's: the tiles a key may still be
--   needed for, is read by Bot.supply's takeKeys alone, never by Bot.team); `answers` and
--   `strength` are measured by the caller in the game.
--   In order: forced units (slot order, past every ceiling); then style.deploy, a followed
--   claim's units; then, while a demand still needs answerers, the scarcest one first (ADR
--   0402): the open demand the fewest units still fitting can answer (ties: a demand of
--   another kind before an enemy class, which the rest of the party still fights; then the
--   first listed) gets, of those units, the one answering the most open demands (ties: a
--   carried unit, then the earlier joiner = slot order). A demand nobody fitting answers is
--   passed over. Then fill: the highest strength on the biggest demand (largest need, first
--   listed), same ties. Everything after the forced units obeys `maxima`: a full group benches
--   the later joiner, even if a slot stays empty.
--   reason = { why = "forced"|"claim"|"covers"|"fill", demands = {ids} (covers),
--   carried = bool }. No transfer rule is decided yet, so `give` is always empty.
-- Bot.shop(gold, stock, party) -> {{ unit = charId, item }...}, one entry per purchase in the
--   order made, each naming the unit it is for (FE8's shop screen buys into the inventory of
--   the unit that opened it, bmshop.c StartShopScreen). party is the deployed roster entries,
--   in roster order (the order Bot.arms reads them in). One Vulnerary (the cheapest) per unit
--   holding none first, then for each
--   unit and each weapon or staff type among the stock it can use (type names in order) in
--   which it holds no USABLE item with uses left (a held weapon the game says it cannot use, or
--   a tome with 0 uses, counts as none), the cheapest stock item of that type it can use. A
--   purchase gold cannot cover, or a full bag has no room for, is skipped and the later ones are
--   still tried; a unit with nothing usable in hand keeps a slot free of a Vulnerary for its arms.
-- Bot.armed(unit) -> bool: it holds a weapon or staff it can use, with uses left.
-- Bot.arms(gold, stock, roster, convoy) -> { [charId] = { { id, uses }... } }: the weapons
--   and staves the convoy, then the shop, would give each unit that is not armed, in their
--   order, the convoy and the purse shared (none: nothing in reach arms it, its bag is full, or
--   the units before it took it). The pick reads such a unit as holding them (harness.lua
--   api.needs), so a unit the supply or the shop can arm ranks as armed, by the game's own
--   numbers, not as the unarmed unit it is now.
-- Bot.supply(party, convoy, benched) -> acts: before the shop, what the roster (benched units
--   too) gives the convoy because it cannot use it this chapter, and the weapons the fielded
--   units take from it. Bot.uses(party, convoy, style) -> acts: after the shop, the
--   seals and boosters they take and use; style.sealAt is the level a seal is used at (#639).
--   Their docstrings have the rules.
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

-- json.lua, beside this file: the strike memo's guard compares and prints two reads with it
local Json = dofile((debug.getinfo(1, "S").source:match("^@(.*/)") or "./") .. "json.lua")

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
-- unit on a fogged tile): the danger reads take them (exposure), and on a Defeat Boss map the
-- march's goal when one is the boss (objectiveTile, ADR 0401).
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
-- The gold one use of a weapon the game gives no price costs a plan over the cheapest weapon
-- that makes the same strike (#642): a Sacred Twin, Excalibur, the legendaries (ItemData
-- costPerUse 0). PT_USEPRICE overrides it ("off": no price and no spares, the bot before
-- #642). 300: one use stays under one death's weight in every style (ADR 0423).
M.RARE_USE = 300

-- What one use of a strike's weapon costs a plan over the cheapest weapon the unit makes the
-- same strike with (#642, ADR 0423), in gold. `price` is the weapon's own price per use
-- (sight.usePrice; nil: the game gives it none), `least` and `most` the lowest and highest of
-- the priced ones there (nil: none is priced), `rare` M.RARE_USE or its knob. A weapon with no
-- price is always the dearest: it costs `rare` a use over the dearest shop weapon there, so
-- over any one spare it costs `rare` at least, whatever that spare's shop price. Priced at a
-- flat `rare`, a shop weapon dearer per use than `rare` (a Spear 600, Eclipse 800:
-- data_items.c) made the legendary the cheaper weapon, and it rode as that one's spare.
-- Between shop weapons the charge is the difference in price; with no priced weapon there,
-- nothing (the price never decides whether to strike).
function M.useCharge(price, least, most, rare)
    if price == nil then return most and most + rare - least or 0 end
    return price - least
end

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
-- A sight's odds (sight.odds), or none where a sight carries no odds (a test's bare board).
local function oddsOf(sight) return sight.odds or function() return 0 end end

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
    local odds = oddsOf(sight)
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
    local ctx = { sight = sight, map = board.map, actors = {}, enemies = {}, blues = {}, standing = {},
                  onField = {}, attacks = cache.attacks, strikes = cache.strikes, reaches = {},
                  worsts = {}, exposures = {}, options = {}, priced = {}, breaches = {}, keyed = {}, talks = {},
                  talkTiles = {}, openers = {}, scopes = {}, floods = {}, rescueTiles = {}, carried = {} }
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
            if u.faction == "blue" and not u.acted and not u.held then
                ctx.actors[#ctx.actors + 1] = u
            end
        end
    end
    table.sort(ctx.actors, function(a, b) return a.slot < b.slot end)
    -- the max HP a heal fills to, as the game reads it (the board's maxhp is the raw stat): for
    -- every unit on the field, the enemy a terrain heal fills too (planner's M.healed)
    if sight.maxHps then sight.maxHps(ctx.onField) end
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

-- Which reds can change an enemy's strike, as strikeKey keeps them (#671, ADR 0431). The strike is
-- the AI's whole decision for `e` against our unit `u` on a tile (sight.strike), and the game
-- reads a red three ways there:
--  * A tile in `e`'s movement and within its weapon's range of the struck tile is a candidate
--    unless a unit stands on it, and its score counts the units within 3 of it
--    (cp_battle.c AiSimulateBestBattleAgainstTarget, AiGetFriendZoneCombatPositionScoreComponent
--    via AiGetCombatPositionScore). So a red within range + 3 of the struck tile.
--  * The score also takes the danger map (gBmMapOther / 8, filled for every decision by
--    AiInitDangerMap, cp_decide.c, no config gate) from AiFillDangerMap (cp_0803E2F4.c): the
--    movement flood and weapon reach of each unit that is not `e`'s ally (a blue or a green;
--    GenerateMovementMap, bmidoten.c, stops at a unit of the other side, so a red blocks it;
--    a hidden unit is not on the unit map, RefreshUnitsOnBmMap, bmmap.c). The weapon it takes
--    is the strongest seen so far by ANY unit (its `item` is never reset), so the reach used
--    here is the widest of every non-red unit's. A red changes a candidate tile's danger only
--    if it is within mov(b) of such a unit b, and b's flood plus reach can reach a tile within
--    range of the struck tile: mov(b) + reach + range(e) >= its distance to that tile.
--  * Before the script, `e` heals or escapes (DecideHealOrEscape: the nearest heal point reads
--    the allies on tiles in its movement), and a script action may steal from a tile beside a
--    target: allies within its movement, so a red within mov(e) + 1 of `e`.
-- A red beyond all three cannot change the strike. `e` reads reds elsewhere through a staff, a
-- ballista, or an AI script that decides on one (sight.readsReds), and its range is unknown
-- with no weapon: those key the whole board (`false`). The range is sight.itemReach's, every
-- weapon item in the bag, not `sight.weapons` (a seal on the tile drops a magic weapon there,
-- which the game's candidate loop still counts).
local STRIKE_ZONE = 3
local function strikeScope(ctx, e)
    local scope = ctx.scopes[e.id]
    if scope ~= nil then return scope end
    local s = ctx.sight
    scope = false
    if s.itemReach and s.readsReds then
        local range = s.itemReach(e)
        if range > 0 and not s.readsReds(e) then
            scope = { range = range, near = s.mov(e) + 1 }
        end
    end
    ctx.scopes[e.id] = scope
    return scope
end

-- The widest weapon reach of any unit that is not red: what AiFillDangerMap takes for each.
-- ctx.onField holds every unit the game's loop counts: it skips US_HIDDEN, US_DEAD,
-- US_NOT_DEPLOYED and US_BIT16 (cp_0803E2F4.c AiFillDangerMap), onField drops US_HIDDEN,
-- US_NOT_DEPLOYED, US_RESCUED and US_DEAD (board.lua OFF_FIELD), and a rescue sets US_HIDDEN
-- with US_RESCUED and a drop clears both (bmunit.c UnitRescue, UnitDrop). So the
-- key's units are the game's or more, never fewer.
local function dangerReach(ctx)
    local far = ctx.dangerFar
    if far then return far end
    far = 0
    for _, o in ipairs(ctx.onField) do
        if o.faction ~= "red" then far = math.max(far, ctx.sight.itemReach(o)) end
    end
    ctx.dangerFar = far
    return far
end

-- A strike's key: the exchange, the map (ctx.mapKey), every unit that is not red, and the reds
-- the enemy's strike can read (strikeScope); `e` itself is always in it.
local function strikeKey(ctx, u, e, x, y, slot)
    local parts = { unitKey(u), x, y, slot or "-", unitKey(e), e.x, e.y, ctx.mapKey, "board" }
    local scope = strikeScope(ctx, e)
    local flooders
    if scope then
        -- the non-red units whose danger can reach this strike's tiles, with their flood's radius:
        -- the same for every strike on this tile at this range, so read once per board (ctx)
        local fk = scope.range .. ":" .. tileKey(x, y)
        flooders = ctx.floods[fk]
        if not flooders then
            flooders = {}
            local reach = dangerReach(ctx) + scope.range
            for _, o in ipairs(ctx.onField) do
                if o.faction ~= "red" then
                    local mov = ctx.sight.mov(o)
                    if mov + reach >= manhattan(o.x, o.y, x, y) then
                        flooders[#flooders + 1] = { o = o, mov = mov }
                    end
                end
            end
            ctx.floods[fk] = flooders
        end
    end
    for _, o in ipairs(ctx.onField) do
        local keep = o.faction ~= "red" or o == e or not scope
            or manhattan(o.x, o.y, x, y) <= scope.range + STRIKE_ZONE
            or manhattan(o.x, o.y, e.x, e.y) <= scope.near
        if not keep then
            for _, f in ipairs(flooders) do
                if manhattan(o.x, o.y, f.o.x, f.o.y) <= f.mov then keep = true; break end
            end
        end
        if keep then parts[#parts + 1] = unitKey(o) .. "@" .. tileKey(o.x, o.y) end
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
    local ask = function() return ctx.sight.strike(u, e, x, y, slot) end
    local k = strikeKey(ctx, u, e, x, y, slot)
    -- PT_STRIKECHECK=1 only (sight.strikeCheck is the run's log, nil otherwise): a memo hit
    -- also runs the strike on this board, as the whole-board key did, and a read that differs
    -- is logged and replaced by the fresh one, so it is logged once
    local log, kept = ctx.sight.strikeCheck, ctx.strikes[k]
    if log and kept ~= nil then
        local fresh = ask()
        if not Json.same(kept or nil, fresh) then
            -- the fields that differ: a read is numbers and tables, with number keys Json.encode refuses
            local fields, all = {}, {}
            for f in pairs(kept or {}) do all[f] = true end
            for f in pairs(fresh or {}) do all[f] = true end
            for f in pairs(all) do
                if not Json.same((kept or {})[f], (fresh or {})[f]) then fields[#fields + 1] = tostring(f) end
            end
            table.sort(fields)
            log[#log + 1] = ("strike memo: enemy %s striking %s at %d,%d (slot %s) read differently "
                .. "from the memo and on this board (%s): strikeKey left out a unit the AI reads "
                .. "(bot.lua strikeScope)"):format(tostring(e.id), tostring(u.id), x, y,
                tostring(slot), #fields > 0 and table.concat(fields, ",") or "one read is nil")
            ctx.strikes[k] = fresh or false
        end
        return fresh
    end
    return remembered(ctx.strikes, k, ask)
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
    -- a re-listing's unit (M.candidates' opts.tiles): only the tiles the plan's changes opened
    -- to it, so every act built over its reach is one its board menu could not hold
    local only = ctx.tiles and ctx.tiles[u.id]
    if only then
        local kept = {}
        for _, t in ipairs(r) do
            if only[tileKey(t.x, t.y)] then kept[#kept + 1] = t end
        end
        r = kept
    end
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

-- `tiles`, safest first: the lowest worst case, the unit's own tile first on a tie (holding
-- costs nothing), then the most ground by `gain(x, y)` when given (a step aside's), then board
-- order. safest is its first.
local function bySafety(ctx, u, tiles, gain)
    local out = {}
    for i, t in ipairs(tiles) do
        out[i] = { t = t, i = i, sum = worstCase(ctx, u, t.x, t.y, nil).sum,
                   own = t.x == u.x and t.y == u.y, g = gain and gain(t.x, t.y) or 0 }
    end
    table.sort(out, function(a, b)
        if a.sum ~= b.sum then return a.sum < b.sum end
        if a.own ~= b.own then return a.own end
        if a.g ~= b.g then return a.g > b.g end
        return a.i < b.i
    end)
    for i, o in ipairs(out) do out[i] = o.t end
    return out
end

local function safest(ctx, u, tiles) return bySafety(ctx, u, tiles)[1] end

-- The tiles of `tiles` the gate lets `u` end on (no target: a wait, a march's step, a heal's)
local function gated(ctx, u, tiles, gate)
    local out = {}
    for _, t in ipairs(tiles) do
        if gate(ctx, u, t.x, t.y, nil) then out[#out + 1] = t end
    end
    return out
end

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
-- The win condition says what the march is for: on a Defeat Boss map it is the boss once the
-- party knows where it stands -- in sight, or in fog and remembered by a retry (ctx.threats,
-- ADR 0399) -- and on a Rout map the nearest enemy in sight. A retry that marched on its
-- nearest remembered enemy instead reached vanilla Ch6's boss turns late (ADR 0401). A
-- remembered boss is aimed at where it stands now, as every remembered unit is read (ADR 0399).
-- With no enemy in sight (fog) and no boss known, the nearest tile the party cannot see: a
-- player knows no more than the fog shows, so it pushes the fog back.
local objectiveTile
local function goalFor(ctx, u, objective)
    local explore = ctx.exploreGoal and ctx.exploreGoal[u.id]
    if explore then return explore end
    return objectiveTile(ctx, u, objective)
end
objectiveTile = function(ctx, u, objective)
    local kind = objective and objective.kind
    if objective and objective.tile then return objective.tile end
    if kind == "survive" then return nil end
    if kind == "boss" then
        -- the unit the objective names, whose death ends the chapter (sight.objective.boss):
        -- another CA_BOSS unit the party knows of is no goal beside it. With none named, the
        -- first CA_BOSS unit known.
        for _, e in ipairs(ctx.threats) do
            if e.isBoss and (not objective.boss or e.charId == objective.boss) then return e end
        end
    end
    if #ctx.enemies == 0 and ctx.sight.unseen then
        local best, bestD
        for _, t in ipairs(ctx.fogRead().unseen) do
            local d = manhattan(u.x, u.y, t.x, t.y)
            if not bestD or d < bestD then best, bestD = t, d end
        end
        return best
    end
    local best, bestD
    for _, e in ipairs(ctx.enemies) do
        local d = manhattan(u.x, u.y, e.x, e.y)
        if not bestD or d < bestD then best, bestD = e, d end
    end
    return best
end

-- The obstacle that opens `u`'s way to `goal` when no walk reaches it: sight.field(goal) is
-- known and leaves u's tile unreached. Of the obstacles the Attack command can strike
-- (sight.obstacles), one whose opening opens onto ground the goal's field reaches
-- (stepsThrough): first one whose own field reaches u, the nearest u by that field; else one u
-- has turns to through others (turnsFor, which asks this again for that obstacle), the fewest
-- -- a way through two doors in a row is still a way, as a player opens them one after
-- another (vanilla Ch14 (Eirika): three doors to the throne). nil when u is not cut off, or
-- nothing opens the way. A door is one when u can open it, now or with a key it can take on
-- the way (doorOpens).
local SIDES = { { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } }

-- The ground opening the door or wall `o` opens, "x,y" -> the cost to walk onto it: its map
-- change's tiles the march walks (sight.mapChange) -- the game opens the change's whole
-- rectangle (ApplyMapChangesById), so a gate two doors deep, or a door onto a roofed room,
-- opens with its first tile (vanilla Ch9 (Ephraim): a 2x2 gate) -- and o's own tile, which a
-- door opened or a wall broken always leaves to walk, even where the change draws none.
local function opensTiles(ctx, o)
    local out = { [tileKey(o.x, o.y)] = 1 }
    for _, t in ipairs(ctx.sight.mapChange and ctx.sight.mapChange(o.x, o.y) or {}) do
        out[tileKey(t.x, t.y)] = t.cost or 1
    end
    return out
end

-- The steps from the obstacle `o` onto the goal's ground (`field`, the goal's), the fewest over
-- the ground opening it opens (opensTiles): from o to a tile of it, walked over that ground
-- alone (a change's shut tiles are walked round), one step off it onto a tile the field
-- reaches, and that tile's own way on. nil = what o opens touches none of the goal's ground,
-- so o is no way to it.
local function stepsThrough(ctx, field, o)
    local ground = opensTiles(ctx, o)
    -- the walk over the opened ground from o: a few tiles, so the cheapest open tile each pass
    local dist, done = { [tileKey(o.x, o.y)] = 0 }, {}
    while true do
        local k, best
        for key, d in pairs(dist) do
            if not done[key] and (not best or d < best) then k, best = key, d end
        end
        if not k then break end
        done[k] = true
        local x, y = k:match("(-?%d+),(-?%d+)")
        for _, side in ipairs(SIDES) do
            local nk = tileKey(tonumber(x) + side[1], tonumber(y) + side[2])
            local c = ground[nk]
            if c and (not dist[nk] or best + c < dist[nk]) then dist[nk] = best + c end
        end
    end
    local best
    for k, d in pairs(dist) do
        local x, y = k:match("(-?%d+),(-?%d+)")
        for _, side in ipairs(SIDES) do
            local row = field[tonumber(y) + side[2]]
            local v = row and row[tonumber(x) + side[1]]
            v = v and d + 1 + v
            if v and (not best or v < best) then best = v end
        end
    end
    return best
end

-- The goal's field distance at (x, y): the walk from there, nil when cut off or no field.
local function walkFrom(ctx, goal, x, y)
    local field = fieldFor(ctx, goal)
    return field and field[y] and field[y][x]
end

-- `u` is cut off from `goal`: its field is known and leaves u's tile unreached (breachFor's
-- case). With no field known, nothing says a way is cut.
local function cutOff(ctx, goal, u)
    return fieldFor(ctx, goal) ~= nil and walkFrom(ctx, goal, u.x, u.y) == nil
end

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
-- no way. A key taken on the way opens the one lock it was fetched for (`unlocked`: the tile's
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

-- The chest lock at (x, y) `u` holds nothing to open (lockAt), never a door's: a door's convoy
-- key is supplyKey's own way (lockedOnWay), and doorOpens must not count it.
local function chestLockAt(ctx, u, x, y)
    local lock = lockAt(ctx, u, x, y)
    return lock and ctx.sight.isChestLock and ctx.sight.isChestLock(lock) and lock or nil
end

-- The wait tiles where the game's Supply command is enabled for `u` (sight.offers), read once a
-- decision: where a key can be taken from the convoy this turn.
local function supplyTiles(ctx, u)
    ctx.supplyAt = ctx.supplyAt or {}
    if ctx.supplyAt[u.id] == nil then
        ctx.supplyAt[u.id] = ctx.sight.offers and ctx.sight.offers(u, waitTiles(ctx, u), "supply")
            or {}
    end
    return ctx.supplyAt[u.id]
end

-- The key the convoy holds for the chest at `tile` that `u` could take now (sight.convoyKey:
-- a free bag slot, a key its class or character may use) and a wait tile where Supply is
-- offered this turn (supplyTiles: the take is this turn's act, so a unit that cannot reach one
-- would arrive at the chest with no key), or nil. Vanilla Ch21's two chests
-- (ch21a-eventinfo.h) have no key in the army, only in the convoy: with no taker the goals
-- dropped them and 134 of 135 recorded attempts missed one (#699).
local function convoyChestKey(ctx, u, tile)
    local lock = chestLockAt(ctx, u, tile.x, tile.y)
    if not (lock and ctx.sight.convoyKey) or #supplyTiles(ctx, u) == 0 then return nil end
    return ctx.sight.convoyKey(u, lock)
end

local keyWay, turnsFor, turnsOn, strikersNear

-- The goal kind of a recruit a Talk is made to (goals.lua's), carried on the goal tiles the march
-- reads (Goals.beside).
local RECRUIT = "recruit"

-- Whether `tile` (a goal tile the march reads: an assigned goal's, carrying its kind, or the
-- nearest enemy's unit table, which is a recruit's when recruitsOf lists it) is met beside it.
-- The one answer for every read of a goal tile (Goals.beside).
local function besideGoal(ctx, tile)
    local recruit = tile and tile.id and ctx.recruits and ctx.recruits[tile.id]
    return Goals.beside(tile and tile.kind or recruit and RECRUIT)
end

-- Whether `from` is a start whose `acted` is `u`'s own, so its turns begin next turn: `u` or a
-- copy of it by id, or a planner position (no id). Not another unit's table (a key source
-- standing in as `from`): its acted flag is not `u`'s. By id, not table identity, so a copy of
-- the unit reads as the unit and the memo keys (turnsFor's, obstacleTurns') agree (#710).
local function startsLate(u, from)
    return (from.id == nil or from.id == u.id) and from.acted and true or false
end

-- Whether `u` can open the door `d`: it holds a key, or it has a way to an enemy whose fall
-- gives it one and from there to the door (keyWay). A key no one can reach opens nothing, so a
-- wall the unit can strike is still its way through.
local function doorOpens(ctx, u, d, seeking)
    local lock = lockAt(ctx, u, d.x, d.y)
    if not lock then return true end
    return keyWay(ctx, u, d, u, lock, seeking) ~= nil
end

local function obstacleKey(o) return (o.door and "door " or "wall ") .. tileKey(o.x, o.y) end
local obstacleTurns

-- The living teammates of `u` who open doors themselves (opener): a door one of them opens
-- opens its whole map change for every unit (ApplyMapChangesById), so it is a way for `u`
-- too, escorting its opener (escortTurns). Only those who hold the means: one fetching a key
-- from an enemy is that key's way, and asking it here would ask `u`'s way back. An opener's
-- own way never asks this (no door is locked to it), so the read cannot cycle. `chests`: the
-- teammates who open chests instead (sight.opensChest; supplyKey's test that the chest is
-- already someone's).
local function doorMates(ctx, u, chests)
    local out = {}
    for _, m in ipairs(ctx.blues or {}) do
        local opens = chests and ctx.sight.opensChest and ctx.sight.opensChest(m)
            or not chests and opener(ctx, m)
        if m.id ~= u.id and not m.dead and opens then out[#out + 1] = m end
    end
    return out
end

-- The teammates of `u` (doorMates) that have a way to the door `d`, through what they open on
-- the way, with their turns there: soonest first, slot order on a tie. A key holder cut off
-- from the door opens nothing, so it is not listed.
local function matesTo(ctx, u, d)
    local out = {}
    for _, m in ipairs(doorMates(ctx, u)) do
        local n = obstacleTurns(ctx, m, m)[obstacleKey(d)]
        if n then out[#out + 1] = { m = m, n = n } end
    end
    table.sort(out, function(a, b)
        if a.n ~= b.n then return a.n < b.n end
        return (a.m.slot or 0) < (b.m.slot or 0)
    end)
    return out
end

-- The soonest turns a teammate of `u` (doorMates) needs to the door `d`, through what it opens
-- on its way; nil when none has a way there (a key holder cut off from it opens nothing).
local function mateTurns(ctx, u, d)
    local first = matesTo(ctx, u, d)[1]
    return first and first.n
end

-- The doors `u` can open, then the walls (sight.obstacles): what may open a way, in the order
-- a unit takes them -- opening a door costs one act, a wall the turns its strikers need to
-- break it (obstacleTurns' fallTurn, #655). A door is one when u can
-- open it, now or with a key it can take on the way (doorOpens), or a teammate can (doorMates).
local function openables(ctx, u, seeking)
    local doors = {}
    for _, d in ipairs(ctx.sight.doors and ctx.sight.doors() or {}) do
        local door = { x = d.x, y = d.y, door = true }
        if opener(ctx, u) or (ctx.sight.locked and (doorOpens(ctx, u, d, seeking)
                                                    or mateTurns(ctx, u, door) ~= nil)) then
            doors[#doors + 1] = door
        end
    end
    local lists = { ctx.sight.obstacles() }
    if #doors > 0 then table.insert(lists, 1, doors) end
    return lists
end

-- `u`'s turns from `from` to the door `d` it holds no key for, opened by a teammate
-- (doorMates): the later of its own walk to the door and the soonest opener's turns there --
-- it gains no ground running ahead of the one who opens it, so the army arrives with its
-- opener (vanilla Ch10 on Eirika's route: the only key holder walked to the door alone while
-- every other unit read no way, and died there). nil with no opener who has a way to it.
local function escortTurns(ctx, u, d, from)
    local walk = ctx.sight.turnsTo and ctx.sight.turnsTo(u, d, from)
    local soonest = walk and mateTurns(ctx, u, d)
    return soonest and math.max(walk, soonest) or nil
end

-- The steps from the obstacle `o` onto `goal`'s ground (stepsThrough over the goal's field),
-- kept for the decision: every way read asks it per obstacle pair, per unit and start.
local function stepsOnto(ctx, goal, field, o)
    ctx.onto = ctx.onto or {}
    local k = tileKey(goal.x, goal.y) .. ">" .. obstacleKey(o)
    if ctx.onto[k] == nil then ctx.onto[k] = stepsThrough(ctx, field, o) or false end
    return ctx.onto[k] or nil
end

-- A wall's HP as this read sees it: the plan's (ctx.wallHp, set by ctx.turnsTo from the
-- planner's st.walls) or the board's (sight.obstacles). Every strike lowers it, so every way
-- through the wall reads shorter after one (#655).
-- The key of a wall's HP: its trap's tile (sight.obstacles' `trap`), which a two-tile wall's
-- tiles share, so a strike on either takes HP off both; its own tile where the sight gives none.
local function wallKey(o) return o.trap or tileKey(o.x, o.y) end

local function wallHp(ctx, o)
    local hp = ctx.wallHp and ctx.wallHp[wallKey(o)]
    return hp or o.hp
end

-- What one strike of `m` takes off the wall `o`, the game's forecast (sight.strikeWall) from the
-- first tile on the map its weapon reaches the wall from and its blow takes something there
-- (the four beside it, then two away for a bow); nil when there is none.
local WALL_SIDES = { { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 }, { 2, 0 }, { -2, 0 }, { 0, 2 }, { 0, -2 } }
local function wallBlow(ctx, m, o)
    local weapons = ctx.sight.weapons(m)
    for _, d in ipairs(WALL_SIDES) do
        local x, y = o.x + d[1], o.y + d[2]
        local map = ctx.map or { w = math.huge, h = math.huge }
        local w = Board.inMap(x, y, map.w, map.h) and Board.weaponFor(weapons, x, y, o.x, o.y)
        local blow = w and ctx.sight.strikeWall(m, o, x, y, w.slot)
        if blow and blow.dealt > 0 then return blow.dealt end
    end
    return nil
end

-- The units that can break the wall `o` (#655): each living blue whose blow takes something
-- off it (wallBlow), with that blow and its weapons (every plan's read asks them). Read once
-- a decision; nil with no forecast of a blow (a sight with no strikeWall): the wall is then
-- costed by the walk alone.
local function strikersOf(ctx, o)
    local s = ctx.sight
    if not (s.strikeWall and s.weapons) then return nil end
    ctx.strikers = ctx.strikers or {}
    local k = tileKey(o.x, o.y)
    if ctx.strikers[k] then return ctx.strikers[k] end
    local out = {}
    for _, m in ipairs(ctx.blues or {}) do
        local dmg = not m.dead and wallBlow(ctx, m, o)
        if dmg then out[#out + 1] = { unit = m, dmg = dmg, weapons = ctx.sight.weapons(m) } end
    end
    ctx.strikers[k] = out
    return out
end

-- The turn a striker `m` (a strikersOf entry) first strikes the wall `o` on this read: only
-- where the read stands it (`p`, default the plan's tile, ctx.wallPos, else the board's) on a tile its
-- weapon reaches the wall from: this turn, or the next once it has acted. nil anywhere else
-- (Nicolas, 2026-11-18): counted from its walk there, every unit that could reach the wall was
-- a striker, so vanilla Ch8's wall always fell on turn 2 while the army marched past it to the
-- throne, and no strike was ever worth making (#655). A striker the plan brings to the wall is
-- counted; one that only could come is not. Second: its chance to be alive to strike (`alive`,
-- the planner's positions after the judged enemy phase; 1 on the board), which its blows are
-- counted at: a striker the plan leaves to die at the wall does not break it.
local function firstStrike(ctx, m, o, p)
    p = p or ctx.wallPos and ctx.wallPos[m.unit.id] or m.unit
    if not Board.weaponFor(m.weapons, p.x, p.y, o.x, o.y) then return nil end
    return p.acted and 2 or 1, p.alive or 1
end

-- The turn the wall `o` falls on this read (#655): every striker (strikersOf) the read stands
-- at the wall strikes once a turn from its first (firstStrike), its blow counted at its chance
-- to be alive, `u` from its arrival `n` on this read; the wall falls on the first turn the
-- blows summed by then reach its HP (wallHp). `late` 1 reads from a tile `u`
-- has already acted from: the read's turns start next turn. -> priced, turn: priced false with
-- no forecast (strikersOf nil); turn nil when no one can break it, else in the read's turns (0
-- for a wall the plan has broken).
local function fallTurn(ctx, o, u, n, late)
    local list = strikersOf(ctx, o)
    if not list then return false end
    local hp = wallHp(ctx, o)
    if hp <= 0 then return true, 0 end
    local starts = {}
    for _, m in ipairs(list) do
        -- u's own chance to live is the goals' (Goals.chance's `alive`), not counted again here
        local first, alive = nil, 1
        if m.unit.id == u.id then
            first = math.max(1, math.ceil(n - Goals.DUST)) + late
        else
            first, alive = firstStrike(ctx, m, o)
        end
        local dmg = m.dmg * (alive or 0)
        if first and dmg > 0 then starts[#starts + 1] = { first = first, dmg = dmg } end
    end
    if #starts == 0 then return true, nil end
    table.sort(starts, function(a, b) return a.first < b.first end)
    -- turn by turn at the summed rate, counted a span at a time between strikers' first turns:
    -- a striker counted at a small chance to live deals a small blow, and a 50-HP wall would
    -- take thousands of turns of the loop one at a time (#659 re-review)
    local i, rate, dealt, turn = 1, 0, 0, starts[1].first
    while true do
        while starts[i] and starts[i].first <= turn do rate, i = rate + starts[i].dmg, i + 1 end
        local need = math.max(1, math.ceil((hp - dealt) / rate - Goals.DUST))
        local nextAt = starts[i] and starts[i].first
        if not nextAt or turn + need - 1 < nextAt then return true, turn + need - 1 - late end
        dealt, turn = dealt + rate * (nextAt - turn), nextAt
    end
end

-- The turns `u` needs from `from` to each obstacle it may open (openables), by obstacleKey:
-- the walk there (sight.turnsTo), a door it has no key for through its key (keyWay), and on
-- from any obstacle it reaches through the ground opening that one opens (stepsThrough), the
-- fewest -- the turns through any number of doors and walls, opened one after another as a
-- player opens them (vanilla Ch14 (Eirika): three doors to the throne). A wall is passed when
-- it falls (#655): the later of `u`'s own arrival and the turn u and the strikers the read
-- stands at it would have broken it at its HP now (fallTurn), as a door locked to `u` is
-- passed with its opener (escortTurns) -- running ahead of the strikers gains nothing, and a
-- wall no one there can break is no way. Charged the walk alone, a 50-HP wall only a 9-damage thief could reach read
-- as open (vanilla Ch8, #655). One shortest-path read (Dijkstra) per unit, start and keys
-- sought, and the plan's wall HP (ctx.wallSig), kept for the decision. Asked per obstacle by
-- recursion instead, X's way asked Y's and Y's asked X's: a guard cut the cycle, its answer
-- was wrong for every later question, and dropping such answers ran a row of doors in time
-- doubling with each door (#612 review). One asked again while it is being worked out (a key's
-- way back to a door of the same read) reads as none. Second: the obstacle each one's fewest
-- turns came through (the chain's step before it; none for one reached on its own), which
-- stepFor follows so the march walks the way these turns count. Third: the obstacles read.
obstacleTurns = function(ctx, u, from, seeking)
    ctx.ways = ctx.ways or {}
    local late = startsLate(u, from) and 1 or 0
    local k = u.id .. "@" .. from.x .. "," .. from.y .. (late == 1 and "!" or "") .. "|"
        .. lockSig(seeking) .. "|" .. (ctx.wallSig or "")
    if ctx.ways[k] then return ctx.ways[k][1], ctx.ways[k][2], ctx.ways[k][3] end
    ctx.ways[k] = { {}, {}, {} }
    local s, all, turns, prev, done = ctx.sight, {}, {}, {}, {}
    for _, list in ipairs(openables(ctx, u, seeking)) do
        for _, o in ipairs(list) do all[#all + 1] = o end
    end
    -- `u` at a wall on turn n is through it when it falls; a door costs the arrival
    local function past(o, n)
        if not n or o.door then return n end
        local priced, fall = fallTurn(ctx, o, u, n, late)
        if not priced then return n end
        return fall and math.max(n, fall) or nil
    end
    for _, o in ipairs(all) do
        local lock = o.door and lockAt(ctx, u, o.x, o.y)
        local n
        if lock then
            n = select(2, keyWay(ctx, u, o, from, lock, seeking))
            -- `lock` is only a door's here: its key's way or its opener's, the sooner
            local e = escortTurns(ctx, u, o, from)
            if e and (not n or e < n) then n = e end
        else
            n = past(o, s.turnsTo and s.turnsTo(u, o, from))
        end
        turns[obstacleKey(o)] = n
    end
    while true do
        local p, best
        for _, o in ipairs(all) do
            local n = turns[obstacleKey(o)]
            if n and not done[obstacleKey(o)] and (not best or n < best) then p, best = o, n end
        end
        if not p then break end
        done[obstacleKey(p)] = true
        for _, o in ipairs(all) do
            -- a door locked to u opens only with its key: no way round that
            local field = not done[obstacleKey(o)] and not (o.door and lockAt(ctx, u, o.x, o.y))
                and fieldFor(ctx, o)
            local steps = field and stepsOnto(ctx, o, field, p)
            local n = steps and past(o, best + steps / s.mov(u))
            if n and (not turns[obstacleKey(o)] or n < turns[obstacleKey(o)]) then
                turns[obstacleKey(o)], prev[obstacleKey(o)] = n, p
            end
        end
    end
    ctx.ways[k] = { turns, prev, all }
    return turns, prev, all
end

-- `u`'s cheapest way from `from` to `tile` through an obstacle (#655): of the obstacles it may
-- open (obstacleTurns), the one whose turns there (through any before it) and steps on to the
-- tile's ground (stepsOnto) are the fewest -> { o, turns }, nil when none opens onto it. Every
-- way through an obstacle is read, a cut-off unit's or not: the chain is one measure beside
-- the walk round (turnsFor), so a wall the army breaks soon is the shorter way where it is.
local function viaObstacle(ctx, u, tile, from, seeking)
    if not (tile and ctx.sight.obstacles and ctx.sight.turnsTo) then return nil end
    local field = fieldFor(ctx, tile)
    if not field then return nil end
    local turns, _, all = obstacleTurns(ctx, u, from, seeking)
    local best
    for _, o in ipairs(all) do
        local t = not (o.x == tile.x and o.y == tile.y) and turns[obstacleKey(o)]
        local steps = t and stepsOnto(ctx, tile, field, o)
        local n = steps and t + steps / ctx.sight.mov(u)
        if n and (not best or n < best.turns) then best = { o = o, turns = n } end
    end
    return best
end

-- The obstacle `u` goes through last on its way to `goal` (viaObstacle), when that way takes
-- fewer turns than its walk (sight.turnsTo) -- nil when the walk is as short, or there is no
-- way through. Was: only for a unit cut off from the goal, and the obstacle nearest it, so a
-- unit with any walk round never weighed a wall (#655). Kept for the decision (ctx.breaches);
-- one still being worked out reads as none: a door's key way can ask for this same breach
-- again (the key's holder cut off from the door), and that way would never end.
local function breachFor(ctx, u, goal, seeking)
    if not (goal and ctx.sight.obstacles) then return nil end
    local k = goalKey(u.id, goal) .. "|" .. lockSig(seeking) .. "|" .. (ctx.wallSig or "")
    local b = ctx.breaches[k]
    if b ~= nil then return b or nil end
    ctx.breaches[k] = false
    local via = viaObstacle(ctx, u, goal, u, seeking)
    local walk = via and ctx.sight.turnsTo(u, goal, u)
    b = via and (not walk or via.turns < walk) and via.o or false
    ctx.breaches[k] = b
    return b or nil
end

-- The turns `u` needs from `from` (default: where it stands) to `tile`, the goals' read
-- (goals.lua's turnsTo): the fewer of sight.turnsTo on its own costs and the way through the
-- obstacles that open onto it (viaObstacle) -- its turns to the last obstacle (through any
-- before it, each wall when the army breaks it: obstacleTurns), the steps through what it
-- opens, the field beyond. Without the way through, vanilla Ch3's throne (behind walls) was
-- unreachable for every unit, so nothing pulled the army and a run took 22 turns. A chest or
-- door `u` has no key for is reached by way of the enemy whose fall gives it one (keyWay): the
-- walk to that enemy, then on from its tile with the key. Memoised for the decision
-- (ctx.keyTurns): the goals ask it per goal, taker and partial plan.
-- `unlocked`: the lock on `tile` is left out of the read, for either of two reasons: the key is
-- in hand (keyWay's second leg, the convoy way's walk with the key: it opens the one lock it was
-- fetched for) or a Talk is made beside the tile, never on it (Goals.beside, ctx.turnsTo's 4th
-- argument). Both read the walk alone, so they share a memo entry.
turnsFor = function(ctx, u, tile, from, seeking, unlocked)
    from = from or u
    ctx.keyTurns = ctx.keyTurns or {}
    local late = startsLate(u, from) and "!" or ""
    local mk = u.id .. "@" .. from.x .. "," .. from.y .. late .. ">" .. tile.x .. "," .. tile.y
        .. "|" .. lockSig(seeking) .. (unlocked and "+" or "") .. "|" .. (ctx.wallSig or "")
    local hit = ctx.keyTurns[mk]
    if hit ~= nil then return hit or nil end
    local s, n = ctx.sight, nil
    local lock = not unlocked and lockAt(ctx, u, tile.x, tile.y)
    if lock then
        n = select(2, keyWay(ctx, u, tile, from, lock, seeking))
        -- a chest key in the convoy is a way too (#699): taken with Supply (supplyKey), after
        -- which the chest is the walk alone, so the walk with the key is its turns
        -- only from where `u` stands: the take is this turn's act. By coordinates, not table
        -- identity: a planner position is never `u`, and the memo key above reads coordinates, so
        -- identical arguments must read alike (#710). `acted` is deliberately not read here, as
        -- `from == u` did not: the way is offered whether or not `u` has acted, and the walk
        -- below reads its own late start (viaObstacle, its own memo key)
        if from.x == u.x and from.y == u.y and convoyChestKey(ctx, u, tile) then
            local c = turnsFor(ctx, u, tile, from, seeking, true)
            if c and (not n or c < n) then n = c end
        end
    else
        n = s.turnsTo and s.turnsTo(u, tile, from)
        local via = viaObstacle(ctx, u, tile, from, seeking)
        if via and (not n or via.turns < n) then n = via.turns end
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
    local n = turnsFor(ctx, u, tile, nil, nil, besideGoal(ctx, tile))
    return n and n * ctx.sight.mov(u)
end

-- The obstacles on `u`'s cheapest way to `tile` (breachFor), first to last: the last one,
-- then each one's step before it (obstacleTurns' second read). Empty when the walk is as short.
local function chainTo(ctx, u, tile, seeking)
    local b = breachFor(ctx, u, tile, seeking)
    if not b then return {} end
    local prev, out = select(2, obstacleTurns(ctx, u, u, seeking)), { b }
    while prev[obstacleKey(out[1])] do table.insert(out, 1, prev[obstacleKey(out[1])]) end
    return out
end

-- Where `u` steps for `tile`: the first obstacle on the way turnsFor counts (chainTo), so
-- the march and the goals read one measure (#655: the march walked round while the turns
-- counted the wall); a door u has no key for, through its key.
local function stepFor(ctx, u, tile, seeking)
    -- a recruit's tile has no lock to fetch a key for: the Talk is beside it (Goals.beside, #710)
    local lock = tile and not besideGoal(ctx, tile) and lockAt(ctx, u, tile.x, tile.y)
    if lock then
        local e = keyWay(ctx, u, tile, u, lock, seeking)
        return e and stepFor(ctx, u, e, withLock(seeking, lock)) or tile
    end
    local first = chainTo(ctx, u, tile, seeking)[1]
    if not first then return tile end
    -- a door u has no key for is reached through its key (or with its opener: then the door)
    if first.door and lockAt(ctx, u, first.x, first.y) then return stepFor(ctx, u, first, seeking) end
    return first
end

-- Where `u` marches: its goal, or what opens the way to it (stepFor).
local function marchGoal(ctx, u, objective)
    return stepFor(ctx, u, goalFor(ctx, u, objective))
end

-- `u`'s act on the obstacle `b` (a door it opens, a wall it strikes), from the first wait tile
-- the gate allows where the game offers it; nil when it has no weapon or no such tile is in
-- range this turn.
local function openAct(ctx, u, b, gate)
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
            -- its HP and the strike's blow (the game's forecast): the planner tracks the wall. A
            -- tile the forecast says takes nothing is no strike: the next is tried (#659
            -- re-review: a strike with no blow read earned the flat `breach` of an unforecast one)
            local blow = ctx.sight.strikeWall and ctx.sight.strikeWall(u, b, t.x, t.y, can.slot)
            if blow and blow.dealt > 0 or not ctx.sight.strikeWall then
                local a = action(u, t, "attack", nil, can.slot)
                a.obstacle = { x = b.x, y = b.y, hp = b.hp, at = wallKey(b), blow = blow }
                return a
            end
        end
    end
    return nil
end

local function isWall(b) return b ~= nil and not b.door and b.hp ~= nil and b.id == nil end

-- A unit's act on the obstacle its own march steps to (stepFor): a locked door's way may be a
-- wall in front of its key's holder, and that wall is the one to strike now.
local function breach(ctx, u, gate, objective)
    local b = stepFor(ctx, u, goalFor(ctx, u, objective))
    if not (b and (b.door or isWall(b))) then return nil end
    return openAct(ctx, u, b, gate)
end

-- The walls whose fall would shorten some unit's way to its goal, in board order, read once a
-- decision (#655): each on the cheapest way (chainTo, the way turnsFor counts), and each the
-- unit could pass sooner than that way if it stood open (its walk there, sight.turnsTo, and the
-- steps on to the goal's ground, stepsOnto). A strike on one is offered to every unit that can
-- hurt it (proposeOne), not only to the unit whose way it is: the strike lowers the wall's HP,
-- and the goals' turns through it (fallTurn) are how the judge prices it. The cheapest way
-- alone never named vanilla Ch8's wall: priced with no striker at it, the thief's 9 a blow
-- made the door round the cheaper way, and with no strike offered no striker ever came.
-- Each way is read to its goal and to each obstacle on it (chainTo) (#663): a goal behind a
-- door has a field that stops at the door (a door is no ground to walk), so a wall that
-- opens onto the door's side was never on a way to the goal. Vanilla Ch8's west chests sit
-- behind the (1,5) door; the cracked wall at (4,8) opens onto that door's room, and the thief
-- walked the south route round to it for 9 turns, never striking or waiting for a strike.
local function wallsOnWays(ctx, objective)
    if ctx.wallWays then return ctx.wallWays end
    local out, seen, s = {}, {}, ctx.sight
    local function put(o)
        if isWall(o) and not seen[tileKey(o.x, o.y)] then
            seen[tileKey(o.x, o.y)] = true
            out[#out + 1] = o
        end
    end
    -- the walls that would bring `h` to `to` sooner than its way there now, stood open
    local function shorter(h, to)
        local field = s.turnsTo and fieldFor(ctx, to)
        local now = field and turnsFor(ctx, h, to)
        for _, o in ipairs(field and s.obstacles and s.obstacles() or {}) do
            local walk = isWall(o) and not seen[tileKey(o.x, o.y)] and s.turnsTo(h, o, h)
            local steps = walk and stepsOnto(ctx, to, field, o)
            if steps and (not now or walk + steps / s.mov(h) < now - Goals.DUST) then put(o) end
        end
    end
    for _, h in ipairs(ctx.blues) do
        local goal = not h.dead and goalFor(ctx, h, objective)
        local chain = goal and chainTo(ctx, h, goal) or {}
        for _, o in ipairs(chain) do put(o) end
        if goal then shorter(h, goal) end
        for _, o in ipairs(chain) do shorter(h, o) end
    end
    ctx.wallWays = out
    return out
end

-- `u`'s strikes on the walls on the army's ways (wallsOnWays) that its blow hurts: it is one
-- of the wall's strikers (strikersOf, the game's forecast read once a decision). None where
-- the sight forecasts no blow: such a strike is worth no turns to anyone (a wall is then
-- costed by the walk), so only the unit whose own way it is strikes it (breach).
local function wallStrikes(ctx, u, gate, objective)
    local out = {}
    for _, w in ipairs(wallsOnWays(ctx, objective)) do
        for _, m in ipairs(strikersOf(ctx, w) or {}) do
            local a = m.unit.id == u.id and openAct(ctx, u, w, gate)
            if a then out[#out + 1] = a end
        end
    end
    return out
end

-- A door locked to `u` on its way to `goal`: `u` is cut off from it (cutOff), walks to the
-- door, and the door's opening opens onto ground the goal's field reaches (stepsThrough, as
-- breachFor reads an obstacle). nil when there is none.
local function lockedOnWay(ctx, u, goal)
    if not (goal and ctx.sight.doors and cutOff(ctx, goal, u)) then return nil end
    local field = fieldFor(ctx, goal)
    for _, d in ipairs(ctx.sight.doors()) do
        if lockAt(ctx, u, d.x, d.y) and walkFrom(ctx, d, u.x, u.y)
                and stepsThrough(ctx, field, d) then
            return d
        end
    end
    return nil
end

-- A Take `a` (a "supply" act) with the item it takes filled in: the convoy's key for `u` now
-- (sight.convoyKey), for the door or, with `a.terrain`, the chest lock it is taken for, or nil
-- with none. An act's key does not carry the item, so a Take built from a key (botrun's forced
-- act) is filled here too; the terrain is in the key (Planner.key), so a chest's Take replays
-- as one.
function M.takeItem(sight, u, a)
    local key = sight.convoyKey and sight.convoyKey(u, a.terrain)
    if not key then return nil end
    a.item, a.uses = key.id, key.uses
    return a
end

-- The convoy's key, taken with the Supply command (#510, vanilla Ch10 on Eirika's route: the
-- one key holder died, the dropped key sat in the convoy, and every unit read no way to the
-- throne). Offered for a door locked to `u` on its way to its goal (lockedOnWay) when no fielded
-- unit opens doors (with one, the door is already every unit's way: doorMates); and, for the
-- chest `u` is sent to (#699: vanilla Ch21's two chests, no key in the army), when no fielded
-- unit opens chests (with one, the chest is that unit's). Either way the convoy must hold what
-- lets `u` open it (sight.convoyKey): from the safest wait tile the gate allows where the
-- game's Supply command is enabled (the lord's, or beside the lord). The game would let it act
-- on after the Take (SupplyCommandEffect returns to the unit menu); the act ends with a Wait,
-- the one act the plan models after it.
local function supplyKey(ctx, u, gate, objective)
    local s = ctx.sight
    if not (s.convoyKey and s.offers and s.locked) then return nil end
    local goal = goalFor(ctx, u, objective)
    local terrain
    if opener(ctx, u) or #doorMates(ctx, u) > 0 or not lockedOnWay(ctx, u, goal) then
        terrain = goal and not besideGoal(ctx, goal) and chestLockAt(ctx, u, goal.x, goal.y)
        if not terrain or #doorMates(ctx, u, true) > 0 then return nil end
    end
    local best = safest(ctx, u, gated(ctx, u, supplyTiles(ctx, u), gate))
    if not best then return nil end
    local a = action(u, best, "supply", nil)
    a.terrain = terrain
    return M.takeItem(s, u, a)
end

-- Whether the game lets `u` Talk to `t` (sight.canTalk), asked once per pair per decide.
local function talks(ctx, u, t)
    -- a Talk that recruited no one this attempt is not offered again: the game re-arms a paid
    -- recruit the party cannot pay (common-events.h EventScr_9EEB00, ENUF), and its check knows
    -- no gold, so the same Talk would spend the talker's act every turn (#679; botrun's unpaid)
    if ctx.unpaid and ctx.unpaid[u.charId .. ">" .. t.charId] then return false end
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

-- The march from `u` to `t` by the game's field from `t`, or the way through an obstacle where
-- that is shorter (breachFor), counted as turnsFor counts it (movesFor); nil = no way at all.
-- Both are movement cost: the field's is the march's cost grid, movesFor's is u's own grid
-- (sight.turnsTo is cost / MOV), so units are ranked on one count. A wall's wait is in the
-- second because that march is that long: running ahead of the wall's fall gains nothing.
local function marchLength(ctx, u, t)
    if breachFor(ctx, u, t) then return movesFor(ctx, u, t) end
    return walkFrom(ctx, t, u.x, u.y)
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
            local d = marchLength(ctx, u, { x = t.x, y = t.y, kind = RECRUIT })
            if d then out[#out + 1] = { u = u, d = d } end
        end
    end
    return out
end

-- The tile a talker can walk to that is nearest (x, y): where a pending recruit is met. Where it
-- arrived may be a tile no talker can walk to (a wyvern rider lands over a cliff: ch13's
-- Cormag). One march field per talker, from where it stands (sight.march, memoised by the sight
-- per class and tile for the board), then the nearest tile of it; ties go to the first in
-- reading order, so the choice is the same every read.
local function meetingTile(ctx, talkers, x, y)
    local best, bestD
    if not ctx.map then error("meetingTile: the board has no map (board.map)", 0) end
    for _, u in ipairs(talkers) do
        local field = ctx.sight.march(u, { x = u.x, y = u.y })
        for ty = 0, ctx.map.h - 1 do
            for tx = 0, ctx.map.w - 1 do
                local d = manhattan(tx, ty, x, y)
                if (not bestD or d < bestD) and field[ty] and field[ty][tx] then
                    best, bestD = { x = tx, y = ty }, d
                end
            end
        end
    end
    return best
end

-- The units a player unit may Talk over (mayTalkOver), by id: a recruit lost to any blow spoils
-- the clear (botrun's recruits_missing), as a green unit's death does. Every blue counts, one
-- that has acted too: it Talks next turn, so its recruit is no less one after a replan.
-- Then those a retry saw arrive and that are not on the board yet (ctx.pending: botrun's
-- pendingRecruits, ADR 0436): an owed recruit not on it counts as one at the tile it arrived on,
-- under the id "arrival:<charId>", from the turn it is read on until the first player turn it
-- stood on the board (boardTurn: T+1 after an enemy-phase arrival of turn T, T itself for a
-- start-of-turn one; a record without it reads turn + 1): a unit not there by then is not coming
-- this attempt, and its goal is none after. Its talkers are the units the game's own check (mayTalkOver) lets
-- Talk its charId -- that check reads the two charIds and the event flags, never the unit. The
-- goal is the tile a talker can reach nearest to where it arrived (meetingTile), none when no
-- talker reaches anywhere.
-- -> out[id] = true, talkers[id] = the player units' ids that may Talk it over (goals.lua's
-- takers), and pending[id] = { id, charId, x, y } for the arrivals.
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
    local pending, here = {}, {}
    for _, t in ipairs(ctx.onField) do here[t.charId] = true end
    for id, t in pairs(ctx.carried or {}) do here[t.charId] = true end
    for _, p in ipairs(ctx.pending or {}) do
        if not here[p.charId] and (ctx.turn or 0) < (p.boardTurn or p.turn + 1) then
            local t = { id = "arrival:" .. p.charId, charId = p.charId, faction = "red", x = p.x,
                        y = p.y }
            local by = {}
            for _, u in ipairs(ctx.blues) do
                if mayTalkOver(ctx, u, t) then by[#by + 1] = u end
            end
            local at = #by > 0 and meetingTile(ctx, by, p.x, p.y)
            if at then
                t.x, t.y = at.x, at.y
                out[t.id], pending[t.id], talkers[t.id] = true, t, {}
                for _, u in ipairs(by) do table.insert(talkers[t.id], u.id) end
            end
        end
    end
    return out, talkers, pending
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
    local tiles = behindWalls(ctx, u, waitTiles(ctx, u))
    local allowed = onTerrain(ctx, gated(ctx, u, tiles, gate))
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

-- A heal act's staff, from the game's heal read (`h`: sight.heals' entry, or a candidate that
-- copied it): its slot, the HP it restores (the planner reads what the target is short by when
-- it lands) and the experience it teaches the healer (sight.staffExp: the planner's score).
local function healWith(a, h)
    a.slot, a.amount, a.exp = h.slot, h.amount, h.exp
end

-- A healer's staff, once the fighters have acted: of the heals the game offers (sight.heals) from wait
-- tiles the gate allows, the one restoring the most HP -- the ally's missing HP up to the
-- staff's amount -- then the most wounded ally, then the safest tile. Slot order picks among
-- healers. nil when no ally is wounded or no healer reaches one.
local function staffHeal(ctx, gate, only)
    local missing, hurt = {}, 0
    for _, b in ipairs(ctx.blues) do
        if b.maxhp and b.hp < b.maxhp then missing[b.id], hurt = b.maxhp - b.hp, hurt + 1 end
    end
    if not (hurt > 0 and ctx.sight.heals) then return nil end
    local best
    for _, u in ipairs(only and { only } or ctx.actors) do
        -- a shortcut only: sight.heals reads the game's list, which never holds the healer
        -- (Sight.asActive), so a healer wounded alone is skipped without asking it
        if hurt > (missing[u.id] and 1 or 0) and #ctx.sight.staves(u) > 0 then
            for _, t in ipairs(waitTiles(ctx, u)) do
                if gate(ctx, u, t.x, t.y, nil) then
                    for _, h in ipairs(ctx.sight.heals(u, t.x, t.y)) do
                        for _, id in ipairs(h.targets) do
                            local gain = math.min(missing[id] or 0, h.amount)
                            local c = { u = u, tile = t, slot = h.slot, id = id, gain = gain,
                                        amount = h.amount, exp = h.exp,
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
    a.targetId, a.gain = best.id, best.gain
    healWith(a, best)
    for _, b in ipairs(ctx.blues) do
        if b.id == best.id then a.target = b.charId end
    end
    return a
end

-- A unit's own heal (sight.mend: a Vulnerary) as the game allows it, at any HP below max
-- (CanUnitUseItem): { slot, amount }, or nil.
local function ownHeal(ctx, u)
    if not (ctx.sight.mend and u.maxhp and u.maxhp > u.hp) then return nil end
    return ctx.sight.mend(u)
end

-- `acts` of `u`, each told the ally its act's tile asks to move (`vacate`) and what can strike
-- it where it ends (Board.endTile: a Canto move's tile) next phase (`exposure`, each enemy's own
-- strike: the planner's odds).
local function exposed(ctx, u, acts)
    for _, a in ipairs(acts) do
        local friend = vacated(ctx, u, a.move.x, a.move.y)
        a.vacate = friend and friend.id
        a.exposure = {}
        -- a strike's weapon, or the one a bait's wait holds (M.baitAt)
        local held = (a.act == "attack" or a.act == "wait") and a.slot or nil
        local at = Board.endTile(a)
        for _, s in ipairs(exposure(ctx, u, at.x, at.y, held)) do
            a.exposure[#a.exposure + 1] = { id = s.by.id, dist = s.f.takenDist }
        end
        -- a strike's spares (#642) too: what strikes the unit next phase depends on the weapon
        -- it holds, and a spare is played in its strike's place
        if a.spares then exposed(ctx, u, a.spares) end
    end
    return acts
end

-- That heal's "item" act on `tile`.
local function healAct(u, m, tile)
    local a = action(u, tile, "item", nil)
    a.slot, a.gain, a.amount = m.slot, math.min(u.maxhp - u.hp, m.amount), m.amount
    return a
end

-- The planner's offer of a unit's own heal (`m`, ownHeal's, when the caller has read it), on
-- the safest tile the gate allows. Offered whenever the game allows it; the planner prices the
-- HP it throws away (ADR 0408). nil when there is none.
local function mend(ctx, u, gate, m)
    m = m or ownHeal(ctx, u)
    if not m then return nil end
    local allowed = gated(ctx, u, waitTiles(ctx, u), gate)
    -- no tile at all only for a re-listing's unit (M.candidates' opts.tiles)
    local tile = safest(ctx, u, #allowed > 0 and allowed or waitTiles(ctx, u))
    return tile and healAct(u, m, tile) or nil
end

-- One act `a` of `u` the planner builds itself (the heal swap's, the bait's), told its tile's
-- ally and its exposure as every offered act is (exposed): without the `vacate`, the swap's
-- heal took Kyle's (charId 0x11) tile before he left it, and the harness could not end the
-- move there (vanilla E_19, 2026-11-16: "could not perform item").
local function offeredAt(ctx, u, a) return exposed(ctx, u, { a })[1] end

-- The planner's heal swap: unit `u`'s own heal on `tile` (ctx: M.candidates' second value).
function M.mendAt(ctx, u, tile)
    local m = ownHeal(ctx, u)
    return m and offeredAt(ctx, u, healAct(u, m, tile)) or nil
end

-- The planner's bait (#641): `u`'s wait on `tile` holding the weapon in bag slot `slot` (the
-- act's `slot`, its key's too: the harness equips it before the Wait, and the judged phase arms
-- the unit with it), where the boss `boss` reaches it (its exposure there, with that weapon
-- held; whether the AI picks `u` over another target is the judged phase's read) and the
-- counter takes HP off it. nil when it is not: a tile `u` may not strike the boss from
-- (strikeTiles: the throne's rule and the avoid claims, as the strike itself), one the boss
-- does not reach, or a counter that cannot hurt it (a range-2 tile against a
-- range-1 boss). No march or hold offers a strike tile (vanilla E_20: Ephraim, charId 0x0F,
-- never offered 11,12 to wait on), and no style gate is asked: the strikes it stands for are
-- offered ungated (`priced`, ADR 0396) and the cap judges the plan.
function M.baitAt(ctx, u, boss, tile, slot)
    local may = false
    for _, t in ipairs(strikeTiles(ctx, u, boss)) do
        if t.x == tile.x and t.y == tile.y then may = true end
    end
    if not may then return nil end
    for _, s in ipairs(exposure(ctx, u, tile.x, tile.y, slot)) do
        if s.by.id == boss.id and s.f and s.f.counterDist then
            local _, back = oddsOf(ctx.sight)({ s.f.counterDist }, boss.hp)
            if back > Goals.DUST then
                -- slot 0 holds the weapon the unit fights with already (the game equips the
                -- first usable one, GetUnitEquippedWeapon; the strike proves it usable): a plain
                -- Wait. Another is equipped first, and is the act's identity (its key)
                local a = action(u, tile, "wait")
                if slot and slot > 0 then a.slot, a.slotKey = slot, true end
                return offeredAt(ctx, u, a)
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

function M.decide(board, sight, style, opts)
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
    ctx.unpaid = opts and opts.unpaid
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
    -- decide, which judges no plan, heals only when no HP of the item is thrown away
    local m = ownHeal(ctx, u)
    local healed = m and u.maxhp - u.hp >= m.amount and mend(ctx, u, gate, m) or nil
    return healed or breach(ctx, u, gate, objective)
        or action(u, march(ctx, u, gate, objective), "wait")
end

-- Why decide holds, as log lines, for a run that ends `stuck`: the objective, every enemy, and
-- per blue unit what decide weighs -- its wait tiles and how many the style's gate allows, the
-- march goal, the obstacle that opens the way to it when it is cut off, and the field distance
-- from the goal (where it stands, the best wait tile, the best allowed one), and per enemy it can strike, the tiles in range, how many the gate allows, and
-- the best (largest-margin) exchange: our hit/damage and its counter against our HP.
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

-- Whether the goal tile `t` is barred for unit `id` (the goals units are blocked from).
local function isBarred(barred, id, t) return barred[goalKey(id, t)] end

-- The door a taker's trip waits on gets its opener (#699: vanilla Ch21's two chests sit behind
-- doors, a Door Key and a Chest Key in the convoy, taken at prep by two units: the chest's taker
-- waited for an opener (escortTurns) whose goal was the boss, so no unit ever went to a door and
-- no chest was reached). For each unit sent to a tile whose first obstacle is a door locked to
-- it, the teammate that opens doors (doorMates) with the fewest turns to that door (matesTo; it
-- gets there first, so the taker's wait is shortest) and no goal of its own is sent to the door
-- itself (unless the goal is barred for it, as assign reads), which breach() opens from where
-- the Door command offers it. Once open the door is no
-- obstacle, and the taker walks on alone. One opener a door, however many units wait on it.
local function sendOpeners(ctx, barred)
    local sentTo, lords = {}, M.gameOver(ctx.sight)
    for _, u in ipairs(ctx.blues) do
        local g = ctx.exploreGoal[u.id]
        local first = g and not g.door and chainTo(ctx, u, g)[1]
        if first and first.door and lockAt(ctx, u, first.x, first.y)
            and not sentTo[tileKey(first.x, first.y)] then
            for _, c in ipairs(matesTo(ctx, u, first)) do
                -- never one whose loss ends the game, nor the seizer (its goal is the seize
                -- tile): a lord pulled to a door leaves the objective
                local free = not (ctx.exploreGoal[c.m.id] or lords[c.m.charId]
                    or ctx.seizeTile and canSeize(ctx, c.m))
                if free and not isBarred(barred, c.m.id, first) then
                    ctx.exploreGoal[c.m.id] = { x = first.x, y = first.y, door = true }
                    sentTo[tileKey(first.x, first.y)] = true
                    break
                end
            end
        end
    end
end

local function exploring(ctx, sent, barred, triedIn)
    ctx.exploreGoal = {}
    ctx.tried = {}
    barred = barred or {}
    local taken = {}
    -- Whether `u` uses `t` on its own: the game's menu check, never asked of a unit that has acted
    -- (an acted unit keeps its tile on the path alone). Not Goals.list's takerUnits (any unit
    -- that opens it, or that an enemy's key would let), nor botrun's reading of a goal's takers:
    -- those ask who could ever take the goal, this who needs no one's key now.
    local function ownOpener(u, t)
        return u.acted or ctx.sight.canExplore(u, t.x, t.y, t.kind)
    end
    local function reaches(u, t)
        if ownOpener(u, t) then return marchLength(ctx, u, t) end
        -- a chest it has no key for: by way of the enemy whose fall gives it one (turnsFor)
        return lockAt(ctx, u, t.x, t.y) and movesFor(ctx, u, t) or nil
    end
    -- each goal one unit, each unit one goal, the nearest pair first; `key` names a goal
    -- the goal's `kind` rides on the unit's goal tile (Goals.beside: every read of a recruit's
    -- tile leaves its lock out)
    local function assign(pairs_, key, kind)
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
                and not isBarred(barred, p.u.id, p.t) then
                taken[k], ctx.exploreGoal[p.u.id] = true, { x = p.t.x, y = p.t.y, kind = kind }
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
    assign(talkPairs, function(t) return "talk>" .. t.id end, RECRUIT)
    if not ctx.sight.explorable then return end
    local open, blues = {}, {}
    for _, t in ipairs(openTiles(ctx)) do open[tileKey(t.x, t.y)] = t end
    for _, u in ipairs(ctx.blues) do blues[u.id] = u end
    -- A keyless unit is one that reaches a chest only by way of the key an enemy drops (#719:
    -- vanilla Ch16, Colm freed by a thief's opening of his chest waited twenty turns at (14,4)
    -- while Eirika and Seth held the two chests he opens, through a Druid's key).
    -- Whether a free unit (no goal, not spent on a tile already) opens `t` itself and gets
    -- there; the one found is spent, so two keyless pairs and one opener drop one pair, not both
    -- (both dropped could swap chests and walk back: the handoff the sticky keep prevents).
    local spent = {}
    local function openerFree(t, but)
        for _, w in ipairs(ctx.actors) do
            if w ~= but and not spent[w.id] and not ctx.exploreGoal[w.id]
                and not isBarred(barred, w.id, t) and ownOpener(w, t) and reaches(w, t)
                and select(2, sendWorth(ctx, w, t)) > 0 then
                spent[w.id] = true
                return true
            end
        end
        return false
    end
    -- The sent pairs, openers' first: a keyless pair is dropped while a free opener stands to
    -- take the chest, and so is a pair of a unit that can act whose goal the ledger marks
    -- stalled (quietGoals: no unit has neared it over GOAL_QUIET waiting player phases, and the
    -- sticky keep is what held it there; a village stalls like a chest, nothing about it makes
    -- standing still fine). An acted unit keeps its tile, as it always did. Both are paired fresh
    -- below, and the unit a stalled pair dropped comes last for that goal (`dropped`): a stalled
    -- goal handed back to the same unit would stall on.
    -- `tried[goal id]` = the units a stalled goal was already given to (triedIn, last decision's,
    -- carried like `sent`; kept only while the goal stays quiet): a unit is dropped from a
    -- stalled goal once per quiet spell, so the goal does not swap between two units for ever
    -- (goalQuiet counts the goal, not the pair, and its nearest reading is a min over all takers)
    local quiet, tried = ctx.quietGoals or {}, ctx.tried
    local function triedOn(id)
        if not tried[id] then
            tried[id] = {}
            for k in pairs(triedIn and triedIn[id] or {}) do tried[id][k] = true end
        end
        return tried[id]
    end
    for id in pairs(triedIn or {}) do
        if quiet[id] then triedOn(id) end
    end
    for _, keyless in ipairs({ false, true }) do
        for _, g in ipairs(sent or {}) do
            local t, u = open[tileKey(g.x, g.y)], blues[g.id]
            if t and u and not taken[tileKey(t.x, t.y)] and not ctx.exploreGoal[u.id]
                and ownOpener(u, t) ~= keyless and not isBarred(barred, u.id, t) then
                if not u.acted and quiet[t.id] and not triedOn(t.id)[u.id] then
                    triedOn(t.id)[u.id] = true
                elseif reaches(u, t) and select(2, sendWorth(ctx, u, t)) > 0
                    and not (keyless and openerFree(t, u)) then
                    taken[tileKey(t.x, t.y)], ctx.exploreGoal[u.id] = true, { x = t.x, y = t.y }
                end
            end
        end
    end
    -- each pair by what the trip is worth, the best first (a fast unit wins a race a nearer
    -- slow one would lose), the nearer on a tie; the units that open the tile themselves
    -- first, then the keyless ones take what is left (a chest only an enemy's key opens for
    -- them goes to an opener, but two chests still go to two units while one opener is
    -- free for one: ch23's win took its chests in parallel that way), and last the unit a
    -- stalled pair just dropped, when no other is left to take its goal
    local byOpen = { {}, {}, {} }
    for _, t in ipairs(openTiles(ctx)) do
        for _, u in ipairs(ctx.actors) do
            local d = reaches(u, t)
            if d then
                local v, c = sendWorth(ctx, u, t)
                if c > 0 then
                    local list = quiet[t.id] and triedOn(t.id)[u.id] and byOpen[3]
                        or byOpen[ownOpener(u, t) and 1 or 2]
                    list[#list + 1] = { t = t, u = u, d = d, v = v }
                end
            end
        end
    end
    for _, list in ipairs(byOpen) do assign(list, function(t) return tileKey(t.x, t.y) end) end
    -- a unit now holding a stalled goal has had its turn with it: the next decision keeps it
    for uid, g in pairs(ctx.exploreGoal) do
        local t = open[tileKey(g.x, g.y)]
        if t and not g.door and quiet[t.id] then triedOn(t.id)[uid] = true end
    end
    sendOpeners(ctx, barred)
end

function M.explain(board, sight, style)
    local ctx = context(board, sight)
    ctx.style, ctx.turn = style, board.turn
    local gate = GATES[style.aggression] or GATES.bold
    local o = sight.objective or {}
    local function at(t) return t and tileKey(t.x, t.y) or "-" end
    local lines = { string.format("objective %s tile %s, turn %s", tostring(o.kind), at(o.tile),
                                  tostring(board.turn)) }
    for _, e in ipairs(ctx.enemies) do
        lines[#lines + 1] = string.format("  red id %d char 0x%02X class 0x%02X @%s hp %d%s",
            e.id, e.charId, e.classId or 0, at(e), e.hp, e.isBoss and " BOSS" or "")
    end
    for _, u in ipairs(ctx.blues) do
        local tiles = waitTiles(ctx, u)
        local allowed = gated(ctx, u, tiles, gate)
        local goal = goalFor(ctx, u, o)
        local function fd(t) return walkFrom(ctx, goal, t.x, t.y) end
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
    return lines
end

-- `a` moved on to tile `t` after it (a Canto variant): a copy, its spares (#642) moving on
-- with it, so a spare stays the same strike with another weapon, canto and all
local function cantoOf(a, t)
    local v = {}
    for k, x in pairs(a) do v[k] = x end
    v.canto = { x = t.x, y = t.y }
    if a.spares then
        v.spares = {}
        for i, b in ipairs(a.spares) do v.spares[i] = cantoOf(b, t) end
    end
    return v
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
        for _, t in ipairs(pick) do out[#out + 1] = cantoOf(a, t) end
    end
    return out
end

-- progress: how much nearer its march goal (the game's field to it) `u` ends on (x, y), as
-- gain(x, y); 0 where either end has no way to the goal.
local function groundFor(ctx, u, objective)
    local goal = marchGoal(ctx, u, objective)
    local function fd(x, y)
        if fieldFor(ctx, goal) then return walkFrom(ctx, goal, x, y) end
        return goal and manhattan(x, y, goal.x, goal.y)
    end
    local here = fd(u.x, u.y)
    return function(x, y)
        local there = fd(x, y)
        return (here and there) and (here - there) or 0
    end
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
    -- the unit's weapons that make each strike, by target and tile (#642): a strike is
    -- priced over the cheapest of them (M.useCharge), and carries the cheaper ones as spares.
    -- One list of options: the boss's tiles below read the same, and each option keeps its
    -- price and charge (`at`, `price`, `charge`) for every strike made of it.
    local options = attackOptions(ctx, u, open, true)
    local others = {}
    for _, c in ipairs(options) do
        local e = c.target
        if ctx.priceUse then
            local it = u.items and u.items[c.slot + 1]
            c.at, c.price = e.id .. "@" .. c.tile.x .. "," .. c.tile.y, it and ctx.sight.usePrice(it.id)
            others[c.at] = others[c.at] or {}
            table.insert(others[c.at], c)
        end
        if not best[e] or betterAttack(c, best[e]) then best[e] = c end
        c.worst = worstCase(ctx, u, c.tile.x, c.tile.y, c.sure and e or nil).sum
        if not safe[e] or c.worst < safe[e].worst then safe[e] = c end
        local g = guard[e]
        if not g or c.f.die < g.f.die or (c.f.die == g.f.die and c.worst < g.worst) then
            guard[e] = c
        end
    end
    for _, here in pairs(others) do   -- each group alone: no order between groups matters
        local least, most
        for _, o in ipairs(here) do
            if o.price then
                least, most = math.min(least or o.price, o.price), math.max(most or o.price, o.price)
            end
        end
        for _, o in ipairs(here) do o.charge = M.useCharge(o.price, least, most, ctx.priceUse) end
    end
    -- option `c`'s strike: its act, and what it spends of its weapon over the cheapest weapon
    -- that makes the same strike (#642), in gold: its charge per use (useCharge), and useCost,
    -- the uses the game's played ways spend at the target's own HP (sight's `wear`, ADR 0423's
    -- 2026-11-18 note) at that charge. The judge charges the uses at the HP the plan leaves the
    -- target (Planner's st.wear); useCost orders the spares. A unit with no cheaper weapon there
    -- pays nothing, so the price chooses the weapon and never whether to strike (a Manakete's
    -- Divinestone is its only weapon: Ch17, #642 comment).
    local function strike(c)
        local a = strikeAct(u, c)
        a.f, a.spent, a.first = c.f, c.spent, c.first
        if c.charge then a.useCharge, a.useCost = c.charge, (c.f.wear or 0) * c.charge end
        return a
    end
    -- The strike keeps the weapon expected damage picked (betterAttack), as with the price off:
    -- the beam never sees the price (an act it cuts on its own score is never judged, and a
    -- Twin's kill that keeps a unit alive was cut that way: #642's shadow runs). Each cheaper
    -- weapon that makes the same strike rides along as a `spare`: the planner judges the plan
    -- with it in this one's place (Planner's spare step), where the cap and the judge read what
    -- the swap costs beside what it saves.
    local function offer(c)
        local a = strike(c)
        for _, o in ipairs(c.charge and others[c.at] or {}) do
            if o.charge < c.charge then
                local b = strike(o)
                -- another weapon, another act: its slot tells the key apart (Planner.key)
                b.slotKey, b.why = true, "attack"
                a.spares = a.spares or {}
                a.spares[#a.spares + 1] = b
            end
        end
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
    for _, c in ipairs(options) do
        if c.target.isBoss then offer(c) end
    end
    add(breach(ctx, u, open, objective), "breach")
    for _, a in ipairs(wallStrikes(ctx, u, open, objective)) do add(a, "breach") end
    add(supplyKey(ctx, u, open, objective), "supply")
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
                        best[id] = { w = w, tile = t, slot = h.slot, amount = h.amount, exp = h.exp }
                    end
                end
            end
        end
        for _, b in ipairs(others) do
            local c = best[b.id]
            if c then
                local a = action(u, c.tile, "staff", b)
                healWith(a, c)
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
    -- (no tile at all only for a re-listing's unit, M.candidates' opts.tiles: its new tiles
    -- may all be allies')
    local function marched()
        local t = march(ctx, u, open, objective)
        add(t and action(u, t, "wait"), "march")
    end
    marched()
    ctx.freeOnly = true
    marched()
    ctx.freeOnly = nil
    local holds = bySafety(ctx, u, waitTiles(ctx, u))
    add(holds[1] and action(u, holds[1], "wait"), "hold")
    local gain = groundFor(ctx, u, objective)
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

-- `c` (a unit's proposal, propose's) with the step aside offered to `c.unit`: of the tiles
-- it may wait on that no unit stands on, less its own, the safest, the most ground toward its
-- march goal on a tie, then board order (bySafety). `c` itself when an act of its already
-- ends there, for a benched unit (its claim holds it), or with no such tile.
local function aside(ctx, c)
    local u = c.unit
    if benchedWait(ctx, u) then return c end
    ctx.freeOnly = true
    local tiles = waitTiles(ctx, u)
    ctx.freeOnly = nil
    local others = {}
    for _, t in ipairs(tiles) do
        if t.x ~= u.x or t.y ~= u.y then others[#others + 1] = t end
    end
    local best = bySafety(ctx, u, others, groundFor(ctx, u, ctx.sight.objective))[1]
    if not best then return c end
    for _, a in ipairs(c.acts) do
        if a.act == "wait" and a.move.x == best.x and a.move.y == best.y then return c end
    end
    local a = action(u, best, "wait")
    a.why = "aside"
    local acts = {}
    for i, x in ipairs(c.acts) do acts[i] = x end
    acts[#acts + 1] = exposed(ctx, u, { a })[1]
    -- `base` is the proposal without the aside: propose keeps that one for a unit whose goal
    -- has not changed, so the next pass asks again who needs its tile
    return { unit = u, acts = acts, base = c }
end

-- Every unit's acts (proposeOne). Given the last proposal `last` and the goals it was made for
-- (`was`, ctx.exploreGoal then), only the units whose goal has changed since are proposed again.
local function propose(ctx, last, was)
    local out, kept = {}, {}
    for _, c in ipairs(last or {}) do
        local a, b = was[c.unit.id], ctx.exploreGoal[c.unit.id]
        if (a == nil) == (b == nil) and (not a or (a.x == b.x and a.y == b.y)) then
            kept[c.unit.id] = c.base or c
        end
    end
    for _, u in ipairs(ctx.actors) do out[#out + 1] = kept[u.id] or proposeOne(ctx, u) end
    -- a unit whose tile a teammate's offered act asks for (its `vacate`) is offered a tile no one
    -- stands on: its march and holds may all end on its own tile or other allies', and allies
    -- asked in a loop leave no order of moves that frees the tile (vanilla Ch8: Joshua on the
    -- one tile beside the door, Garcia and Ross on the two he was offered)
    local asked = {}
    for _, c in ipairs(out) do
        for _, a in ipairs(c.acts) do
            if a.vacate then asked[a.vacate] = true end
        end
    end
    for i, c in ipairs(out) do
        if asked[c.unit.id] then out[i] = aside(ctx, c) end
    end
    return out
end

-- ctx.turnsTo on a board a plan leaves (#655): `walls` ("x,y" -> HP, the planner's st.walls)
-- the wall HP it leaves, `pos` (id -> { x, y, acted }, the planner's positions) where it puts
-- each unit. Only the walls it struck and the strikers it stands at a wall, or takes from one
-- (firstStrike against the board's), change a way, so only they key the read (ctx.wallSig, in
-- every memo): a plan that does neither reads, and memoises, as the board as it stands.
-- -> a turnsTo.
turnsOn = function(ctx, walls, pos)
    local keys = {}
    for k, hp in pairs(walls or {}) do keys[#keys + 1] = k .. "=" .. hp end
    for _, o in ipairs(pos and ctx.sight.obstacles and ctx.sight.obstacles() or {}) do
        for _, m in ipairs(isWall(o) and strikersOf(ctx, o) or {}) do
            local p = pos[m.unit.id]
            local f, alive = nil, nil
            if p then f, alive = firstStrike(ctx, m, o, p) end
            -- the board's own, kept on the entry: every plan's read compares with it
            if m.board == nil then m.board = { firstStrike(ctx, m, o, m.unit) } end
            if p and (f ~= m.board[1] or alive ~= m.board[2]) then
                keys[#keys + 1] = m.unit.id .. ">" .. tileKey(o.x, o.y) .. "=" .. tostring(f)
                    .. "@" .. tostring(alive)
            end
        end
    end
    if #keys == 0 then return ctx.turnsTo end
    table.sort(keys)
    local sig = table.concat(keys, ";")
    return function(u, tile, from, beside)
        ctx.wallHp, ctx.wallPos, ctx.wallSig = walls, pos, sig
        -- cleared whatever happens: an error left inside it would key every later read as this
        -- plan's board
        local ok, n = pcall(turnsFor, ctx, u, tile, from, nil, beside)
        ctx.wallHp, ctx.wallPos, ctx.wallSig = nil, nil, nil
        if not ok then error(n, 0) end
        return n
    end
end

-- Whether `u`'s way to `g` can shorten this turn by a strike on a wall on it (#655): a way
-- through a wall is passed when the wall falls (fallTurn), so a unit waiting on the fall has
-- no step nearer of its own, and is held only while some unit able to act (u too) can strike
-- that wall this turn and the strike shortens u's way: for each striker (strikersOf) of each
-- wall on the way (chainTo), each tile it may end on that its weapon reaches the wall from,
-- and the read (turnsOn) with its blow taken off and it standing there, against `now`,
-- u's turns on the board as it stands. No one able to strike it this turn, the goal is barred
-- like any other: a wall's fall is never assumed.
strikersNear = function(ctx, u, g, now)
    for _, w in ipairs(chainTo(ctx, u, g)) do
        local hp = isWall(w) and wallHp(ctx, w)
        for _, m in ipairs(hp and strikersOf(ctx, w) or {}) do
            local a = m.unit
            if not a.acted and not a.held then
                local weapons = ctx.sight.weapons(a)
                for _, t in ipairs(endTiles(ctx, a)) do
                    if Board.weaponFor(weapons, t.x, t.y, w.x, w.y) then
                        local p = { x = t.x, y = t.y, acted = true }
                        local read = turnsOn(ctx, { [wallKey(w)] = math.max(0, hp - m.dmg) },
                                             { [a.id] = p })
                        local n = read(u, g, a.id == u.id and p or nil)
                        if n and n < now - Goals.DUST then return true end
                    end
                end
            end
        end
    end
    return false
end

-- Whether `u` can get nearer goal tile `g` this turn by the game's turns (ctx.turnsTo) or take
-- it: it stands on it, a tile it may end on is nearer, or, with a recruit standing on `g` (a
-- tile no player unit ends on), it may end beside it, where a Talk is made. A unit with no tile
-- but its own is boxed in, and counts as able: no other goal would get it anywhere either. The
-- turns are the terrain's alone, so what stops a unit with moves is a unit in its way. A unit
-- whose way waits on a wall's fall is able while a strike on it can come this turn
-- (strikersNear, #655): vanilla Ch8's thief, waiting at the wall, read as stuck and its chests
-- were dropped.
local function stepsToward(ctx, u, g)
    local there = ctx.standing[tileKey(g.x, g.y)]
    -- a recruit (recruitsOf: one a player unit may Talk over), not any unit: an enemy holding
    -- a village is no goal reached by standing beside it
    local recruit = there and ctx.recruits[there.id]
    local beside = besideGoal(ctx, g)
    local now = ctx.turnsTo(u, g, nil, beside)
    if now and now <= Goals.DUST then return true end
    local boxed = true
    for _, t in ipairs(endTiles(ctx, u)) do
        if recruit and manhattan(t.x, t.y, g.x, g.y) == 1 then return true end
        if t.x ~= u.x or t.y ~= u.y then
            boxed = false
            local n = now and ctx.turnsTo(u, g, t, beside)
            if n and n < now - Goals.DUST then return true end
        end
    end
    return boxed or (now ~= nil and strikersNear(ctx, u, g, now))
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
-- claim gives way); `quietGoals`, the ledger goal ids no unit has neared over GOAL_QUIET waiting player
-- phases (goals.lua's ledger marks their rows stalled); `stuck`, the last call's ctx.stuck ("unit id>x,y" -> { id, x, y, since }:
-- each goal a unit was found with no step toward, and the turn it was first found so); `only`
-- ({ [unit id] = true }) and `tiles` ({ [unit id] = { ["x,y"] = true } }), the planner's
-- re-listing (#661, #670): only those units' acts are listed, each over those tiles of its
-- reach alone, every other unit standing as it is.
-- -> { { unit, acts } }, ctx (the planner scores with the same view; ctx.recruits, recruitsOf's
-- ids, are the units a player blow must not kill; ctx.recruitTalkers who may Talk each over).
function M.candidates(board, sight, style, opts)
    local ctx = context(board, sight)
    ctx.style, ctx.turn = style, board.turn
    -- the board's Talk memo (#671): a re-list's read asks the same pairs again (recruitsOf, 224
    -- CheckForCharacterEvents per change key), and a pair's answer is keyed by its two units (ids
    -- are stable within the chapter) and depends on charIds and the event flags, which no door or
    -- kill moves. A dead enemy is out of the re-list's board, so its pairs are never asked,
    -- whatever the memo holds
    if opts and opts.talks then ctx.talks = opts.talks end
    ctx.unpaid = opts and opts.unpaid
    if opts and opts.only then
        local kept = {}
        for _, u in ipairs(ctx.actors) do
            if opts.only[u.id] then kept[#kept + 1] = u end
        end
        ctx.actors = kept
    end
    ctx.tiles = opts and opts.tiles
    ctx.explored = opts and opts.explored or {}
    ctx.seen = opts and opts.seen
    ctx.lost = opts and opts.lost or {}
    ctx.stalled = opts and opts.stalled
    -- the weapon-use price (#642): the gold a use of an unpriced weapon costs, or nil (off:
    -- PT_USEPRICE=off, or a sight that cannot price an item)
    local knob = opts and opts.usePrice
    if knob ~= "off" and sight.usePrice then ctx.priceUse = tonumber(knob) or M.RARE_USE end
    ctx.quietGoals = opts and opts.quietGoals or {}
    -- memoised for the decision (turnsFor's ctx.keyTurns, obstacleTurns' ctx.ways): the planner
    -- asks it per goal, taker and partial plan, and a unit cut off goes through breachFor and
    -- the field again each time
    ctx.keyTurns, ctx.ways = {}, {}
    -- `beside`: the tile's lock is left out (a Talk is beside a recruit, not on his tile)
    ctx.turnsTo = function(u, tile, from, beside)
        return turnsFor(ctx, u, tile, from, nil, beside)
    end
    ctx.beside = function(tile) return besideGoal(ctx, tile) end
    ctx.turnsOn = function(walls, pos) return turnsOn(ctx, walls, pos) end
    ctx.pending = opts and opts.pending
    ctx.recruits, ctx.recruitTalkers, ctx.pendingRecruits = recruitsOf(ctx)
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
        exploring(ctx, opts and opts.sent, barred, opts and opts.tried)
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
    local out = Board.copy(style)
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
        local out = Board.copy(style)
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
    for _, d in ipairs(t.demands) do
        -- the covering's tie-break reads it: without one an enemy class would pass for another kind
        if d.kind == nil then error("bot.lua: demand " .. tostring(d.id) .. " has no kind", 2) end
        left[d.id] = d.need
    end
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
        -- the scarcest open demand: counting "the most demands answered" alone benched the one
        -- unit that could open a chest behind fighters answering three enemy classes each
        local scarce, fewest
        for _, d in ipairs(t.demands) do
            local n = 0
            if left[d.id] > 0 then
                for _, c in ipairs(roster) do
                    if fits(c) and answers(c, d.id) then n = n + 1 end
                end
            end
            -- equally scarce: a demand of another kind (a chest, a door, a village, the fog,
            -- the healing) goes unanswered without its unit, an enemy class is still fought
            -- by the rest of the party
            if n > 0 and (not fewest or n < fewest
                    or (n == fewest and scarce.kind == "enemy" and d.kind ~= "enemy")) then
                scarce, fewest = d, n
            end
        end
        local u = scarce and best(function(c)
            if not answers(c, scarce.id) then return 0 end
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

-- A weapon or staff the game says the unit can use (its rank, its class), and the one test of
-- "can use" (Bot.fullBag's weighing and the shop's arming both ask it); not a rank it forbids.
-- A weapon is the game's own flag (IA_WEAPON or IA_STAFF, kind "weapon"), not a named type: a
-- Dragonstone or a Ballista's type (bmitem.h ITYPE_DRAGN, ITYPE_BLLST) has no shop type name,
-- and its holder is still armed.
local function canUseWeapon(it)
    return it.kind == "weapon" and it.usable == true
end

-- A weapon the game says the unit cannot use: the matching "unusable".
local function cannotUseWeapon(it)
    return it.kind == "weapon" and it.usable ~= true
end

-- A weapon or staff the unit can use now: the game's can-use and uses left (a broken tome, or
-- a lance its rank forbids, arms nobody).
local function usableWeapon(it)
    return canUseWeapon(it) and (it.uses or 0) > 0
end

function M.armed(u)
    return holdsAny(u, usableWeapon)
end

-- The units not armed and the armed (armed(u)), each in party order: the one split the shop
-- and the convoy both serve the unarmed first by.
local function splitArmed(party, armed)
    local unarmed, out = {}, {}
    for _, u in ipairs(party) do table.insert(armed(u) and out or unarmed, u) end
    return unarmed, out
end

-- A weapon's full uses (ItemData maxUses): the harness reads it for every stock, convoy and bag
-- weapon (INSPECT.itemFacts); one without it raises, so a missing read never passes as "holds
-- none".
local function fullUses(x)
    return x.maxUses or error(string.format("item 0x%X has no maxUses", x.item or x.id or -1))
end

-- How many uses short of the type `t` the unit holding `items` is (> 0: short, so a spare is
-- wanted), when the weapons on offer of the type start at `offered` full uses: one full weapon
-- (the fewest full uses among those on offer and the ones it holds) times M.SPARE, less the
-- uses its usable weapons of the type hold together. A spare comes before the last weapon
-- breaks, not after (Nicolas, 2026-11-15: rule B of #510 comment 6896261936); a unit holding
-- nothing of the type is short, as before. The one test of "short of a type": lackedTypes (the
-- shop, the convoy, Bot.arms) and Bot.fullBag (a weapon arriving in a full bag) both ask it.
-- M.SPARE is half a weapon (Nicolas, 2026-11-15, to be tuned if it costs): at one whole, a unit
-- that had spent one use (an Elfire at 29 of 30) bought a spare at every chapter start.
M.SPARE = 0.5
local function shortfall(items, t, offered)
    local held, need = 0, offered
    for _, it in ipairs(items) do
        if it.type == t and usableWeapon(it) then
            held = held + it.uses
            need = math.min(need, it.maxUses or need)
        end
    end
    return need * M.SPARE - held
end

-- The weapon or staff types among `list` (stock entries or convoy items) the unit can use
-- (usable(x): the game's can-use for it), in name order, that it is short of (shortfall), and
-- by how many uses each: one owner for what the shop buys and the convoy gives, one item of
-- each.
local function lackedTypes(u, list, usable)
    local types, full = {}, {}
    for _, x in ipairs(list) do
        if x.type ~= nil and usable(x) then
            if not full[x.type] then types[#types + 1] = x.type end
            full[x.type] = math.min(full[x.type] or math.huge, fullUses(x))
        end
    end
    table.sort(types)
    local out, gap = {}, {}
    for _, t in ipairs(types) do
        local short = shortfall(u.items or {}, t, full[t])
        if short > 0 then
            out[#out + 1] = t
            gap[t] = short
        end
    end
    return out, gap
end

-- What the shop would buy for one unit, in order: a Vulnerary when it holds none, then for each
-- weapon or staff type among the stock it can use that it is short of (lackedTypes, type names
-- in order), the cheapest stock item of that type it can use. Bag room and gold are the
-- caller's.
local function wants(u, stock)
    local out = {}
    if not holdsAny(u, function(it) return it.vulnerary end) then
        local s = cheapest(stock, u, function(s) return s.vulnerary end)
        if s then out[#out + 1] = s end
    end
    local usable = function(s) return (u.canUse or {})[s.item] end
    for _, t in ipairs(lackedTypes(u, stock, usable)) do
        out[#out + 1] = cheapest(stock, u, function(s) return usable(s) and s.type == t end)
    end
    return out
end

-- The shop's spend order, the one owner (Bot.arms asks it too, so the two cannot drift): bag
-- room is FE8's five slots (Board.ITEM_COUNT), spent by every purchase in order; a unit with no
-- usable weapon or staff keeps one slot free of a Vulnerary for what arms it.
function M.shop(gold, stock, party)
    local out, room = {}, {}
    for _, u in ipairs(party) do room[u.charId] = Board.ITEM_COUNT - #u.items end
    local function buy(u, s)
        if room[u.charId] <= 0 or s.price[u.charId] > gold then return end
        gold = gold - s.price[u.charId]
        room[u.charId] = room[u.charId] - 1
        out[#out + 1] = { unit = u.charId, item = s.item, vulnerary = s.vulnerary }
    end
    -- Vulneraries first, then weapons, within one group of units.
    local function spend(group)
        local list = {}
        for _, u in ipairs(group) do list[u.charId] = wants(u, stock) end
        for _, u in ipairs(group) do
            local w = list[u.charId]
            if w[1] and w[1].vulnerary then
                local arms = not M.armed(u) and w[2] ~= nil
                if room[u.charId] > (arms and 1 or 0) then buy(u, w[1]) end
            end
        end
        for _, u in ipairs(group) do
            for _, s in ipairs(list[u.charId]) do
                if not s.vulnerary then buy(u, s) end
            end
        end
    end
    -- The unarmed are paid for before the armed, so no armed unit's Vulnerary takes the gold
    -- that arms a fielded unit, and Bot.arms (this loop over the roster's unarmed) is the
    -- shop's own prefix.
    local unarmed, armed = splitArmed(party, M.armed)
    spend(unarmed)
    spend(armed)
    return out
end

-- ── the convoy gives back (#510 comment 6872948037; the party plan's PR 2) ─────────────────
-- Every "can this unit use it" is the game's own answer, handed in per unit as an item's
-- `for[charId] = { usable, promotes, gains }` (harness.lua api.convoy: CanUnitUseWeapon /
-- CanUnitUseStaff, CanUnitUsePromotionItem, CanUnitUseStatGainItem). A bag item's top-level
-- usable / promotes / gains are its holder's.

-- the item as `charId` would hold it: its facts for that unit on top
local function forUnit(it, charId) return (it["for"] or {})[charId] or {} end

local function asHeld(it, charId)
    local h, f = Board.copy(it), forUnit(it, charId)
    h.usable, h.promotes, h.gains = f.usable, f.promotes, f.gains
    return h
end

-- The supply's working copy: each unit's bag (the fielded, and for Bot.supply the benched)
-- and the convoy, and the acts that changed them, in order. `swap` lets a full bag give first
-- what Bot.fullBag would send (it needs every held item's kind: api.convoy's read, not the
-- roster's).
local function ledger(party, convoy, swap, benched)
    local L = { acts = {}, bags = {}, pool = {} }
    for _, u in ipairs(party) do L.bags[u.charId] = copyList(u.items) end
    for _, u in ipairs(benched or {}) do L.bags[u.charId] = copyList(u.items) end
    L.pool = copyList(convoy)
    -- false when the convoy is full (api.give would refuse it): the item stays in the bag
    function L.give(charId, i, why)
        if #L.pool >= Board.CONVOY_ITEM_COUNT then return false end
        local it = table.remove(L.bags[charId], i)
        L.pool[#L.pool + 1] = it
        L.acts[#L.acts + 1] = { act = "give", unit = charId, item = it.id, uses = it.uses, why = why }
        return true
    end
    -- the convoy's i-th item into the unit's bag; false when there is no room for it
    -- `kind`: what the bag holds it as when the convoy's read has none (a key is "other" there,
    -- and Bot.fullBag keeps a key it is handed: "key")
    function L.take(charId, i, why, kind)
        local it, bag = L.pool[i], L.bags[charId]
        local h = asHeld(it, charId)
        h.kind = kind or h.kind
        if #bag >= Board.ITEM_COUNT then
            if not swap then return false end
            local slot, swhy = M.fullBag(bag, h, false)
            if slot == 0 then return false end
            if not L.give(charId, slot, "room: " .. swhy) then return false end
            -- the given item is appended after i: i still names the item taken
        end
        table.remove(L.pool, i)
        bag[#bag + 1] = h
        L.acts[#L.acts + 1] = { act = "take", unit = charId, item = it.id, uses = it.uses, why = why }
        return true
    end
    function L.armed(charId) return holdsAny({ items = L.bags[charId] }, usableWeapon) end
    return L
end

-- The unarmed first, then the armed (the shop's own order, splitArmed), each in party order.
local function unarmedFirst(party, armed)
    local a, b = splitArmed(party, armed)
    for _, u in ipairs(b) do a[#a + 1] = u end
    return a
end

-- The convoy's weapons and staves: for each type lackedTypes names (the shop's own test), the
-- convoy's best of that type for the unit: one whose uses end the shortage first (else the
-- shop would buy another after it), then the highest rank, then the most uses, then the first.
-- Not the shop's cheapest, on purpose: a stored item costs nothing, so the best one is taken.
local function takeWeapons(L, party)
    for _, u in ipairs(unarmedFirst(party, function(v) return L.armed(v.charId) end)) do
        local function usable(it)
            return it.kind == "weapon" and forUnit(it, u.charId).usable and (it.uses or 0) > 0
        end
        local types, gap = lackedTypes({ items = L.bags[u.charId] }, L.pool, usable)
        for _, t in ipairs(types) do
            local best
            local function key(it)
                return it.uses >= gap[t] and 1 or 0, it.rank or 0, it.uses
            end
            local function beats(a, b)
                local a1, a2, a3 = key(a)
                local b1, b2, b3 = key(b)
                if a1 ~= b1 then return a1 > b1 end
                if a2 ~= b2 then return a2 > b2 end
                return a3 > b3
            end
            for i, it in ipairs(L.pool) do
                if it.type == t and usable(it) and (not best or beats(it, L.pool[best])) then
                    best = i
                end
            end
            L.take(u.charId, best, "a usable " .. t)
        end
    end
end

-- The keys a chapter's chests and doors need (#699: vanilla Ch21's two chests, a Chest Key in
-- the convoy and nobody holding one -- 134 of 135 recorded attempts missed a chest). A `demands`
-- entry of kind chests or doors wants one use per lock tile it counts (`locks`: the tiles a key
-- may still be needed for, #711; a Chest Key opens one chest, vanilla Ch21 has two), less the
-- uses the fielded bags already open. An item the game says opens the kind for its holder
-- (`for[charId].opens`: GetUnitKeyItemSlotForTerrain, so a Lockpick counts only for a thief; no
-- id lives here) has `uses` of them, and one Lockpick's uses are spent once across the kinds: the
-- narrowest opener is counted first, so a Chest Key answers chests before a Lockpick is. What is
-- still wanted is taken from the convoy, one item per pass, by the unit with the most free slots
-- then (ties to party order): the take costs it nothing, and a full bag gives first what
-- Bot.fullBag would send, so the next in order is tried when that gives nothing up.
local function takeKeys(L, party, demands)
    local spare = {}   -- a held item -> its uses not yet counted against a lock
    local function left(it)
        if spare[it] == nil then spare[it] = it.uses or 1 end
        return spare[it]
    end
    local function spend(it, want)
        local n = math.min(left(it), want)
        spare[it] = spare[it] - n
        return want - n
    end
    for _, d in ipairs(demands or {}) do
        if d.kind == "chests" or d.kind == "doors" then
            local function opens(u, it) return (forUnit(it, u.charId).opens or {})[d.kind] end
            local want, held = d.locks or d.need or 1, {}
            for _, u in ipairs(party) do
                for _, it in ipairs(L.bags[u.charId]) do
                    if opens(u, it) then
                        local kinds = 0
                        for _, yes in pairs(forUnit(it, u.charId).opens) do
                            if yes then kinds = kinds + 1 end
                        end
                        held[#held + 1] = { it = it, kinds = kinds, i = #held }
                    end
                end
            end
            table.sort(held, function(a, b)
                if a.kinds ~= b.kinds then return a.kinds < b.kinds end
                return a.i < b.i
            end)
            for _, h in ipairs(held) do want = spend(h.it, want) end
            local order = {}
            for i, u in ipairs(party) do
                order[#order + 1] = { u = u, i = i }
            end
            -- a pass takes one item for the unit with the most free slots; the next pass counts
            -- the slot the take used, so a second key goes to the next unit with room
            while want > 0 do
                table.sort(order, function(a, b)
                    local fa, fb = Board.ITEM_COUNT - #L.bags[a.u.charId],
                                   Board.ITEM_COUNT - #L.bags[b.u.charId]
                    if fa ~= fb then return fa > fb end
                    return a.i < b.i
                end)
                local took = false
                for _, o in ipairs(order) do
                    for i, it in ipairs(L.pool) do
                        local why = "the " .. d.kind .. " key"
                        if opens(o.u, it) and L.take(o.u.charId, i, why, "key") then
                            local bag = L.bags[o.u.charId]
                            want, took = spend(bag[#bag], want), true
                            break
                        end
                    end
                    if took then break end
                end
                if not took then break end
            end
        end
    end
end

-- Why a unit gives an item to the convoy before the shop, or nil when it keeps it: what it
-- cannot use this chapter (rule A of #510 comment 6896261936). A weapon or staff the game says
-- it cannot use (cannotUseWeapon, Bot.fullBag's own test); a seal or booster (the item's `use`)
-- the game says it cannot use now; and a benched unit's every seal and booster, since only a
-- fielded unit uses one (api.use is the map's Item command). From the convoy the existing
-- rules hand each to a fielded unit that can use it (takeWeapons, Bot.uses), now or later.
local function cannotUseNow(it, fielded)
    if it.kind == "weapon" then
        return cannotUseWeapon(it) and "a weapon it cannot use" or nil
    elseif it.use then
        if not fielded then return "a " .. it.use .. " a benched unit cannot use" end
        if not (it.promotes or it.gains) then return "a " .. it.use .. " it cannot use" end
    end
    return nil
end

-- Why a unit gives back the key it holds: the chapter's demands (api.needs') name no lock it
-- opens (#699: takeKeys took it for an earlier chapter's chests, and a key left in the bag costs
-- a slot for good). `opens` is the game's read for the holder (api.convoy's `for`); nil without
-- demands (no prep screen: nothing is known), for a non-key, or for a key a demand names.
local function unneededKey(it, charId, demands)
    local opens = demands and it.kind == "key" and forUnit(it, charId).opens
    if not opens then return nil end
    for _, d in ipairs(demands) do
        if opens[d.kind] then return nil end
    end
    return "a key no lock of this chapter needs"
end

-- Bot.supply(party, convoy, benched) -> acts, before the shop: what the roster gives the convoy
-- and what the fielded units take from it (the party plan's PR 2; comment 6872948037's rules,
-- widened by comment 6896261936's rule A). party = the fielded units in roster order, benched =
-- the roster's other units, each item with the game's facts and its kind (api.convoy's read);
-- convoy = its items, each with `for` over every roster unit.
--   1. Every roster unit gives what it cannot use this chapter (cannotUseNow), and a key no
--      demand of the chapter names (unneededKey).
--   2. Weapons and staves from the convoy, the unarmed first (takeWeapons), so the shop buys
--      only what storage cannot give.
--   3. The key a chapter's chests or doors need when no fielded unit holds one (takeKeys;
--      `demands` = api.needs', nil without a prep screen).
-- A full bag gives first what Bot.fullBag would send. acts = { act = "give" | "take" | "use",
-- unit = charId, item = id, uses, seal = true (a use that promotes) | nil, why }.
function M.supply(party, convoy, benched, demands)
    local L = ledger(party, convoy, true, benched)
    local function giveBack(list, fielded)
        for _, u in ipairs(list or {}) do
            -- from the last slot down, so a give (which packs the bag) never moves an item not
            -- yet looked at
            for i = #L.bags[u.charId], 1, -1 do
                local it = L.bags[u.charId][i]
                local why = cannotUseNow(it, fielded) or unneededKey(it, u.charId, demands)
                if why then L.give(u.charId, i, why) end   -- false: the convoy is full
            end
        end
    end
    giveBack(party, true)
    giveBack(benched, false)
    takeWeapons(L, party)
    takeKeys(L, party, demands)
    return L.acts
end

-- Bot.uses(party, convoy, style) -> acts, after the shop (the same shapes as Bot.supply's): the
-- seals and boosters the fielded units use, each taken from the convoy first when not in the bag.
--   3. A seal for each fielded unit the game says one promotes, the highest level first (ties
--      by party order). One use a unit a chapter, since each costs the unit its first turn
--      (api.use is the Item command); what a promotion opens (a stat whose cap rose) is asked
--      of the game again at the next chapter's start, from the unit's new class. A unit below
--      style.sealAt (nil: none, so the game's own L10 floor) is skipped and its seal stays in
--      the bag or convoy (#639: the L10-or-L20 promotion comparison; cannotUseNow keeps a
--      seal the game says promotes the holder, so nothing sells or gives it away meanwhile).
--   4. A booster for each fielded unit left that the game says gains from one: the units the
--      game forces onto the map first (the lord), then the lowest level (ties by party order).
-- Its own first, else the convoy's (a full bag gives first what Bot.fullBag would send).
function M.uses(party, convoy, style)
    local L = ledger(party, convoy, true)
    local sealAt = style and style.sealAt or 0   -- 0: the game's own L10 floor decides
    local used = {}
    local function useOne(u, fact, why)
        if used[u.charId] then return end
        for _, it in ipairs(L.bags[u.charId]) do
            if it[fact] then
                used[u.charId] = true
                L.acts[#L.acts + 1] = { act = "use", unit = u.charId, item = it.id, uses = it.uses,
                                        seal = fact == "promotes" or nil, why = why }
                return
            end
        end
        for i, it in ipairs(L.pool) do
            if forUnit(it, u.charId)[fact] then
                if L.take(u.charId, i, why) then return useOne(u, fact, why) end
                return
            end
        end
    end
    for _, u in ipairs(byLevel(party)) do
        if u.level >= sealAt then useOne(u, "promotes", "promotes it") end
    end
    local order = {}
    for i, u in ipairs(party) do order[i] = { u = u, i = i } end
    table.sort(order, function(x, y)
        if (x.u.forced or false) ~= (y.u.forced or false) then return x.u.forced == true end
        if x.u.level ~= y.u.level then return x.u.level < y.u.level end
        return x.i < y.i
    end)
    for _, o in ipairs(order) do useOne(o.u, "gains", "raises a stat") end
    return L.acts
end

-- Bot.arms(gold, stock, roster, convoy) -> { [charId] = { { id, uses }... } }: every weapon or
-- staff that would arm each unit that is not armed (M.armed): the convoy's first (takeWeapons,
-- Bot.supply's own step, uses as stored), then the shop's (uses nil: as the shop makes it),
-- in the order they are taken and bought. It is those two loops run over the unarmed with the
-- one convoy, the one purse and each unit's bag room, so what it says is what the supply and
-- the shop do; none for a unit nothing in reach arms, a full bag, or a purse or a convoy the
-- units before it spent. Both serve the unarmed before the armed, and the fielded unarmed are
-- a subset of these in the same order (between() serves the fielded in roster order, as this
-- reads the roster). Fewer units before a unit take from a type and spend from the purse, so
-- what is left for it is never less: a unit `arms` arms is armed, though not always with the
-- same item (an earlier fielded unit may take the one `arms` gave it, leaving another of its
-- type). The real supply may arm one more: a full bag gives first there, which needs every
-- item's kind, not the roster's read. The pick asks the game how such a unit fights holding
-- those items.
function M.arms(gold, stock, roster, convoy)
    local unarmed, out = {}, {}
    for _, u in ipairs(roster) do
        if not M.armed(u) then unarmed[#unarmed + 1] = u end
    end
    local L = ledger(unarmed, convoy or {}, false)
    takeWeapons(L, unarmed)
    for _, a in ipairs(L.acts) do
        out[a.unit] = out[a.unit] or {}
        table.insert(out[a.unit], { id = a.item, uses = a.uses })
    end
    local after = {}
    for i, u in ipairs(unarmed) do
        after[i] = Board.copy(u)
        after[i].items = L.bags[u.charId]
    end
    for _, p in ipairs(M.shop(gold, stock, after)) do
        if not p.vulnerary then
            out[p.unit] = out[p.unit] or {}
            table.insert(out[p.unit], { id = p.item })
        end
    end
    return out
end

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
            if canUseWeapon(it) and it.type == t then out[#out + 1] = it end
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
    elseif new.kind ~= "weapon" and (new.promotes or new.gains) then
        wanted = true   -- a seal or booster its holder can use: Bot.supply uses it
    elseif canUseWeapon(new) then
        local same = usableOfType(new.type)
        local with = { new }
        for _, w in ipairs(same) do with[#with + 1] = w end
        -- short of the type (the shop's and the convoy's own test, rule B), or it adds reach
        -- or bonus damage
        if shortfall(held, new.type, fullUses(new)) > 0 or special(new, with) then
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
        if cannotUseWeapon(it)
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
                  { first(function(it)
                      return it.use ~= nil and not (it.promotes or it.gains)
                  end), "a seal or booster it cannot use" },
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
