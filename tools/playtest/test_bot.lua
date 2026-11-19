-- Tests for bot.lua -- the pure policy (no emulator): the greedy core the clear scenarios
-- drive, then Bot.decide's styles over hand-built boards and a fake `sight`.
-- Run: lua tools/playtest/test_bot.lua
--
-- Writing a planner test here:
-- - A test that passes only on a tie-break proves nothing. Assert the judged gap (from
--   `plan.considered`) or the goal's chance after the plan (`goalAfter`), and check that it fails
--   with the fix stashed.
-- - In these fakes a single-unit army's way to the objective is worth a whole death: give the
--   objective its own direction, or it swamps the trade under test.
local here = (arg[0]:match("(.*/)")) or "./"
local B = dofile(here .. "bot.lua")
local Planner = dofile(here .. "planner.lua")
local Sight = dofile(here .. "sight.lua")
local Board = dofile(here .. "board.lua")
local Json = dofile(here .. "json.lua")

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
    check(B.pickTarget(reach, enemies, { weapons = { { slot = 0, min = 1, max = 1 } } }), nil, "no enemy in range -> nil")
end

-- One enemy orthogonally adjacent to a reachable tile -> that enemy, from that tile.
do
    local reach = tiles({ 5, 5 }, { 5, 6 })
    local enemies = { { x = 5, y = 7, hp = 20, is_boss = false } }  -- adjacent to (5,6)
    local pick = B.pickTarget(reach, enemies, { weapons = { { slot = 0, min = 1, max = 1 } } })
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
    local pick = B.pickTarget(reach, enemies, { weapons = { { slot = 0, min = 1, max = 1 } } })
    check(pick and pick.target.is_boss, true, "boss preferred over non-boss")
end

-- Among non-boss targets, the lowest-HP one wins (likeliest kill).
do
    local reach = tiles({ 0, 1 }, { 2, 1 })
    local enemies = {
        { x = 0, y = 2, hp = 18, is_boss = false },  -- adjacent to (0,1)
        { x = 2, y = 2, hp = 5, is_boss = false },   -- adjacent to (2,1)
    }
    local pick = B.pickTarget(reach, enemies, { weapons = { { slot = 0, min = 1, max = 1 } } })
    check(pick and pick.target.hp, 5, "lowest-hp non-boss preferred")
end

-- Range 2 (e.g. a hand axe): an enemy two tiles from a reachable tile is attackable.
do
    local reach = tiles({ 4, 4 })
    local enemies = { { x = 4, y = 6, hp = 20, is_boss = false } }  -- distance 2 from (4,4)
    check(B.pickTarget(reach, enemies, { weapons = { { slot = 0, min = 1, max = 1 } } }), nil, "range 1 can't reach distance 2")
    local pick = B.pickTarget(reach, enemies, { weapons = { { slot = 0, min = 1, max = 2 } } })
    check(pick ~= nil, true, "range 2 reaches distance 2")
end

-- A BOW (min 2): an ADJACENT enemy is NOT attackable -- striking from range 1 leaves
-- no Attack command, so pickTarget must skip the adjacent tile (#65 recordrbgtest bug).
do
    local adjacent = tiles({ 4, 5 })  -- distance 1 from the foe at (4,6)
    local enemies = { { x = 4, y = 6, hp = 20, is_boss = false } }
    check(B.pickTarget(adjacent, enemies, { weapons = { { slot = 0, min = 2, max = 2 } } }), nil,
          "bow (min 2) won't pick an adjacent tile it can't fire from")
    -- but a true range-2 tile IS picked, and an adjacent one is left out of a mixed reach.
    local mixed = tiles({ 4, 5 }, { 4, 4 })  -- (4,5)=dist 1, (4,4)=dist 2
    local pick = B.pickTarget(mixed, enemies, { weapons = { { slot = 0, min = 2, max = 2 } } })
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
            local atk = B.pickTarget(reach, enemies, { weapons = { { slot = 0, min = 1, max = 1 } } })
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
        fogged = o.fogged or false, held = o.held,
        minRange = o.minRange == nil and 1 or o.minRange or nil,
        maxRange = o.maxRange == nil and 1 or o.maxRange or nil,
        isBoss = o.isBoss or false, classId = o.classId, weapons = o.weapons, level = o.level,
        items = o.items,   -- { { id, uses } }: what a weapon use costs is read by its id (#642)
        mov = o.mov,   -- the fake sight's MOV (turnsTo, mov); 5 when unset
        carrying = o.carrying, carriedBy = o.carriedBy,   -- a Rescue pair (board.lua)
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
-- The fake game's play of a strike's blows, for the fixtures' window numbers (the ROM's own
-- play is sight.lua's `played`, proven in the ROM): each lands at its hit through FE8's two
-- rolls and crits at its crit, tripled. `live` = the chance the striker is still standing
-- for them (a counter's blows, after our attack may have killed).
local function blowsOf(hit, dmg, hits, crit, live)
    local p = Sight.rollChance(2, hit or 0) * (live or 1)
    local c = math.max(0, math.min(100, crit or 0)) / 100
    local out = {}
    for _ = 1, hits or 0 do
        local one = { [0] = 1 - p }
        one[dmg or 0] = (one[dmg or 0] or 0) + p * (1 - c)
        one[(dmg or 0) * 3] = (one[(dmg or 0) * 3] or 0) + p * c
        out[#out + 1] = one
    end
    return out
end
-- A fixture's attack, as sight.attack returns it once the fake game has played it.
local function attackPlayed(f, uHp, tHp)
    local dealt = Sight.damage(blowsOf(f.hit, f.dmg, f.hits, f.crit), tHp)
    local kill = Sight.odds({ dealt }, tHp)
    local back = f.counters and Sight.damage(blowsOf(f.counterHit, f.counterDmg, f.counterHits,
                                                     f.counterCrit, 1 - kill), uHp)
        or { [0] = 1 }
    -- the exchange's pairs: our blows, then the counter only where they left the target
    -- standing (the fixtures' one-blow exchanges are played in that order)
    local leaves = {}
    local whole = f.counters and Sight.damage(blowsOf(f.counterHit, f.counterDmg, f.counterHits,
                                                      f.counterCrit), uHp) or { [0] = 1 }
    for d, pd in pairs(dealt) do
        if d >= tHp then
            leaves[#leaves + 1] = { p = pd, dealt = d, back = 0 }
        else
            for b, pb in pairs(whole) do leaves[#leaves + 1] = { p = pd * pb, dealt = d, back = b } end
        end
    end
    local _, _, joint = Sight.exchangeOf(leaves)
    -- the weapon uses our blows spend (the ROM's are sight's M.worn / M.wornBy): each blow
    -- thrown while the target stands, a use if it lands (every blow for a weapon that spends on
    -- a miss), by the HP the target had lost when it came
    local blows, wearAt, wear = blowsOf(f.hit, f.dmg, f.hits, f.crit), {}, 0
    local spend = f.spendsMiss and 1 or Sight.rollChance(2, f.hit or 0)
    for i = 1, #blows do
        local before = {}
        for j = 1, i - 1 do before[j] = blows[j] end
        for lost, q in pairs(Sight.damage(before, tHp)) do
            if lost < tHp and q > 0 then
                wearAt[lost] = (wearAt[lost] or 0) + q * spend
                wear = wear + q * spend
            end
        end
    end
    -- the counter's (a fixture with a counterSlot): its blows after the attacker's, each
    -- thrown while the target stands, a use if it lands
    local counterAt, counterWear = {}, 0
    if f.counters and f.counterSlot then
        local spent = (f.counterHits or 0) * Sight.rollChance(2, f.counterHit or 0)
        for lost, q in pairs(dealt) do
            if lost < tHp and q > 0 then
                counterAt[lost] = (counterAt[lost] or 0) + q * spent
                counterWear = counterWear + q * spent
            end
        end
    end
    return Sight.attackOf({ hit = f.hit, dmg = f.dmg, crit = f.crit, hits = f.hits,
                            spendsMiss = f.spendsMiss, wear = wear, wearAt = wearAt,
                            wearSlot = f.wearSlot,
                            counter = { armed = f.counters, hit = f.counterHit,
                                        dmg = f.counterDmg, crit = f.counterCrit,
                                        hits = f.counterHits, wear = counterWear,
                                        wearAt = counterAt, wearSlot = f.counterSlot },
                            killsTarget = f.killsTarget, dealt = dealt, back = back,
                            joint = joint, exp = f.exp }, tHp, uHp)
end
-- A fixture's enemy strike (sight.strike's, or one of sight.enemyPhase's), played on a unit
-- at `hp`; one already carrying takenDist is left as it is.
local function strikePlayed(t, hp)
    if t.takenDist then return t end
    local out = {}
    for k, v in pairs(t) do out[k] = v end
    out.takenDist = Sight.damage(blowsOf(t.takenHit, t.takenDmg, t.takenHits, t.takenCrit),
                                 hp or math.huge)
    out.takenWorst = Sight.worst(out.takenDist)
    out.counterDist = Sight.damage(blowsOf(t.counterHit, t.counterDmg, t.counterHits,
                                           t.counterCrit), t.strikerHp or math.huge)
    -- the chance the target's counter kills the striker, as sight.enemyPhase plays it; a
    -- fixture may give its own
    if out.felled == nil and t.strikerHp then
        out.felled = (Sight.odds({ out.counterDist }, t.strikerHp))
    end
    return out
end
local function sightOf(o)
    local attacks, strikes = 0, 0
    -- a forecast per tile, or per tile and weapon ("x,y/slot") where a test tells them apart
    local function entry(u, t, x, y, slot)
        local byT = (o.fc or {})[u.id]
        local byTile = byT and byT[t.id]
        return (byTile and (byTile[x .. "," .. y .. "/" .. tostring(slot)]
                            or byTile[x .. "," .. y])) or QUIET
    end
    -- The game's Weapon Select list, modelled by the unit's `weapons` or its one range.
    local function weapons(u)
        return u.weapons or (u.minRange and { { slot = 0, min = u.minRange, max = u.maxRange } })
            or {}
    end
    local s = {
        objective = o.objective or { kind = "rout" },
        field = o.field,
        -- The game's march cost to a goal over MOV (sight.turnsTo, not rounded): the test's
        -- field when it gives one, else Manhattan; MOV 5 unless the unit says.
        turnsTo = function(u, tile, from)
            from = from or u
            local f = o.field and o.field(tile)
            local d = f and f[from.y] and f[from.y][from.x]
            if f and not d then return nil end
            return (d or Board.distance(from.x, from.y, tile.x, tile.y)) / (u.mov or 5)
        end,
        mov = function(u) return u.mov or 5 end,
        cache = o.cache,
        terrain = o.terrain,
        weapons = weapons,
        -- The game's price per use (sight.usePrice; nil: no price), when the test prices uses
        usePrice = o.usePrice,
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
        attack = function(u, t, x, y, slot)
            local w = Board.weaponFor(weapons(u), x, y, t.x, t.y, slot)
            if not w then return nil end
            attacks = attacks + 1
            return attackPlayed(entry(u, t, x, y, w.slot), u.hp, t.hp)
        end,
        strike = function(u, t, x, y, slot)
            strikes = strikes + 1
            return strikePlayed(entry(u, t, x, y, slot), u.hp)
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
    -- who holds a heal of its own, whatever its HP (sight.salve); a fixture that names none
    -- has no read, and the planner reads no wear
    if o.salve then s.salve = function(u) return o.salve[u.id] == true end end
    -- the fog read's strike (sight.strike with `from`, the fog's edge): o.fogStrike(u, e, x, y,
    -- fx, fy) answers it; a strike with no `from` is the fake's own
    if o.fogStrike then
        local own = s.strike
        s.strike = function(u, e, x, y, slot, from)
            if from then return o.fogStrike(u, e, x, y, from.x, from.y) end
            return own and own(u, e, x, y, slot)
        end
    end
    if o.maxHp then
        s.maxHps = function(units)
            for _, u in ipairs(units) do u.maxhp = o.maxHp[u.id] or u.maxhp end
        end
    end
    if o.talk then s.canTalk = function(u, t) return (o.talk[u.id] or {})[t.id] == true end end
    -- the map as the phase changes it (sight.mapKey), read live so a test can open a door
    s.mapKey = function() return o.mapKey or "-" end
    -- fn() on the board a plan leaves (sight.changed, #661, #670): o.change(change) gives the
    -- fixture's fields as that board has them (a reach through the door or the dead enemy's
    -- tile, the door gone), each put back after; every change read is kept in `changes`
    if o.change then
        s.changed = function(change, fn)
            local was = {}
            for k, v in pairs(o.change(change)) do was[k] = { v = o[k] }; o[k] = v end
            local out = table.pack(fn())
            for k, w in pairs(was) do o[k] = w.v end
            s.changes = s.changes or {}
            s.changes[#s.changes + 1] = change
            return table.unpack(out, 1, out.n)
        end
    end
    if o.keys then s.holdsKey = function(u) return o.keys[u.id] == true end end
    -- a retry's memory (sight.knows, ADR 0399): the red unit ids it remembers
    if o.known then s.knows = function(u) return o.known[u.id] == true end end
    if o.openers then s.opensDoor = function(u) return o.openers[u.id] == true end end
    -- the tiles a door's or wall's map change opens ("x,y" -> { { x, y } }; sight.mapChange)
    if o.changes then s.mapChange = function(x, y) return o.changes[x .. "," .. y] end end
    -- what each unit holds no key for ("x,y" -> the lock), and who drops one (lock -> enemies)
    if o.locked then
        s.locked = function(u, x, y) return (o.locked[u.id] or {})[x .. "," .. y] end
        s.keySources = function(_, lock) return (o.keySources or {})[lock] or {} end
    end
    -- the unit menu's check: Door lists a door beside an opener (TryAddClosedDoorToTargetList),
    -- Talk a talkable unit beside the talker (MakeTalkTargetList), Rescue a unit o.rescue lets
    -- `u` carry beside it (MakeRescueTargetList)
    s.offers = function(u, tiles, act, target)
        local may = act == "door" and (o.openers or {})[u.id] == true
            or act == "talk" and s.canTalk ~= nil and s.canTalk(u, target)
            or act == "rescue" and ((o.rescue or {})[u.id] or {})[target.id] == true
        local out = {}
        for _, t in ipairs(tiles) do
            -- Supply (SupplyUsability) has no target: the tiles o.supplyAt holds ("x,y")
            if act == "supply" then
                if (o.supplyAt or {})[t.x .. "," .. t.y] then out[#out + 1] = t end
            elseif may and Board.distance(t.x, t.y, target.x, target.y) == 1 then
                out[#out + 1] = t
            end
        end
        return out
    end
    -- the convoy's door key for each unit (sight.convoyKey): { id, uses }
    if o.convoyKey then s.convoyKey = function(u) return o.convoyKey[u.id] end end
    -- the Drop list (MakeDropTargetList): from each tile, its neighbours o.dropOn holds ("x,y")
    if o.dropOn then
        s.drops = function(_, tiles)
            local out = {}
            for _, t in ipairs(tiles) do
                local at = {}
                for _, d in ipairs({ { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } }) do
                    local x, y = t.x + d[1], t.y + d[2]
                    if o.dropOn[x .. "," .. y] then at[#at + 1] = { x = x, y = y } end
                end
                if #at > 0 then out[#out + 1] = { x = t.x, y = t.y, drops = at } end
            end
            return out
        end
    end
    -- when a looter takes each open tile (sight.closings: "x,y" -> the enemy phase); the game
    -- always has the read where it has villages and chests (none: no looter)
    if o.closings or o.explorable then s.closings = function() return o.closings or {} end end
    -- villages and chests: the open tiles, and the unit menu's check per unit and tile
    if o.explorable then
        s.explorable = function() return o.explorable end
        s.canExplore = function(u, x, y, kind)
            return ((o.canExplore or {})[u.id] or {})[x .. "," .. y] == kind
        end
    end
    s.odds = Sight.odds
    s.splitFloor = Sight.SPLIT_FLOOR
    -- each strike played on its target at the HP the plan gives it; the lookahead's second
    -- phase (o.nextPhase, sight.nextPhase) also says each unit's HP when it begins, the plan's
    -- unless the fixture gives its own
    local function phaseOf(fn)
        return function(plan)
            local hp = {}
            for _, b in ipairs(plan.blues) do hp[b.unit.id] = b.hp end
            local out = fn(plan)
            out.hp = out.hp or hp
            local played = {}
            local function play(t)
                played[t] = played[t] or strikePlayed(t, t.targetHp or hp[t.target])
                return played[t]
            end
            for i, t in ipairs(out) do out[i] = play(t) end
            -- every way the phase went, as sight.enemyPhase gives them: their chances sum to 1
            local sum = 0
            for _, oc in ipairs(out.outcomes or {}) do
                for i, t in ipairs(oc.strikes) do oc.strikes[i] = play(t) end
                sum = sum + oc.p
            end
            if out.outcomes and math.abs(sum - 1) > 1e-9 then
                error("test fixture: enemyPhase outcomes' chances sum to " .. sum .. ", not 1")
            end
            return out
        end
    end
    if o.enemyPhase then s.enemyPhase = phaseOf(o.enemyPhase) end
    if o.nextPhase then
        local next, replied = phaseOf(o.nextPhase), phaseOf(o.replyPhase or o.nextPhase)
        -- `reply`: the second phase after the army's reply, o.replyPhase's (o.nextPhase's when
        -- none); every call is in `asked`, the reply's counted in `replied` too
        s.nextPhase = function(plan, reply)
            s.asked = s.asked or {}
            s.asked[#s.asked + 1] = plan
            if reply then
                s.replied = (s.replied or 0) + 1
                return replied(plan)
            end
            return next(plan)
        end
    end
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
-- a style whose villages and chests are worth `gold` each (goals.lua's prior: the mean gift)
-- the chance a plan leaves goal `id` (its record's goalWorth `after`), nil when it has none
local function goalAfter(plan, id)
    for _, g in ipairs(plan and plan.goalWorth or {}) do
        if g.id == id then return g.after end
    end
end
local function gifted(aggression, gold)
    local st = style(aggression)
    st.villageGifts = { items = {}, gold = { gold } }
    return st
end
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
            g.counterDist, g.counterWorst, g.die = { [0] = 1 }, 0, 0
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
    -- the same 50% kill on both: the tie goes on to expected damage, E2's 12 HP against E1's 10
    local E2b = red(0x82, 0, 1, { hp = 12 })
    s = sightOf {
        fc = { [0x01] = {
            [0x81] = { ["0,0"] = fc { hit = 50, dmg = 10, hits = 1, killsTarget = true } },
            [0x82] = { ["0,0"] = fc { hit = 50, dmg = 12, hits = 1, killsTarget = true } },
        } },
    }
    check(B.decide(boardOf(A, E1, E2b), s, style("careful")).target, 0x82,
        "equal kill chances tie exactly; expected damage (12 x 50% > 10 x 50%) decides")
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

-- Every weapon the Weapon Select menu lists is asked (sight.weapons), not the equipped one
-- alone (audit 9): a sword (1) and a javelin (1-2) in the bag, the javelin strikes an enemy two
-- tiles off; where both reach, the act's slot is the weapon whose forecast wins.
do
    local A = blue(0x01, 0, 0, 0, { weapons = { { slot = 0, min = 1, max = 1 },
                                                { slot = 1, min = 1, max = 2 } } })
    local kills = fc { hit = 100, dmg = 10, hits = 1, killsTarget = true }
    local far = red(0x81, 0, 2, { hp = 10 })
    local sight = sightOf { reach = { [0x01] = tiles({ 0, 0 }) },
                            fc = { [0x01] = { [0x81] = { ["0,0"] = kills } } } }
    local a = B.decide(boardOf(A, far), sight, style("careful"))
    check(a.act .. "/" .. tostring(a.slot), "attack/1", "the javelin strikes from two tiles")
    local near = red(0x81, 0, 1, { hp = 10 })
    local both = sightOf { reach = { [0x01] = tiles({ 0, 0 }) },
                           fc = { [0x01] = { [0x81] = {
                               ["0,0/0"] = kills,
                               ["0,0/1"] = fc { hit = 100, dmg = 3, hits = 1 } } } } }
    a = B.decide(boardOf(A, near), both, style("careful"))
    check(a.act .. "/" .. tostring(a.slot), "attack/0", "where both reach, the weapon that kills")
    local swordOnly = blue(0x01, 0, 0, 0)
    check(B.decide(boardOf(swordOnly, far), sight, style("careful")).act, "wait",
          "a sword alone does not reach two tiles")
end

-- #642: a plan pays for the weapon uses it spends. Two weapons make the same sure kill: the
-- plan strikes with the one whose use costs less (a Steel Lance at its own 16 gold, not a
-- Siegmund, which the game gives no price); with the price off (PT_USEPRICE=off) it keeps the
-- one expected damage picked. Where only the dear weapon kills, the kill is still worth it.
do
    local SIEGMUND, STEEL = 0x92, 0x16
    local A = blue(0x01, 0, 0, 0, { weapons = { { slot = 0, min = 1, max = 1 },
                                                { slot = 1, min = 1, max = 1 } },
                                    items = { { id = SIEGMUND, uses = 20 },
                                              { id = STEEL, uses = 30 } } })
    local E = red(0x81, 0, 1, { hp = 20 })
    local function priced(steel)
        return { reach = { [0x01] = tiles({ 0, 0 }) },
                 usePrice = function(id) return id == STEEL and 16 or nil end,
                 fc = { [0x01] = { [0x81] = {
                     ["0,0/0"] = fc { hit = 100, dmg = 30, hits = 1, killsTarget = true },
                     ["0,0/1"] = steel } } } }
    end
    local same = priced(fc { hit = 100, dmg = 30, hits = 1, killsTarget = true })
    local a = Planner.plan(B, boardOf(A, E), sightOf(same), style("careful"))
    check(a and a.act .. "/" .. tostring(a.slot), "attack/1", "the same kill: the cheaper use")
    a = Planner.plan(B, boardOf(A, E), sightOf(same), style("careful"), { usePrice = "off" })
    check(a and a.act .. "/" .. tostring(a.slot), "attack/0", "price off: expected damage's pick")
    local weak = priced(fc { hit = 100, dmg = 10, hits = 1 })
    a = Planner.plan(B, boardOf(A, E), sightOf(weak), style("careful"))
    check(a and a.act .. "/" .. tostring(a.slot), "attack/0", "only the dear weapon kills: it strikes")
    -- a unit whose only weapon has no price pays nothing for it: the price picks the weapon,
    -- never whether to strike (a chip the planner takes at no price is taken at any)
    local M = blue(0x01, 0, 0, 0, { weapons = { { slot = 0, min = 1, max = 1 } },
                                    items = { { id = SIEGMUND, uses = 20 } } })
    local chip = { reach = { [0x01] = tiles({ 0, 0 }) },
                   usePrice = function(id) return id == STEEL and 16 or nil end,
                   fc = { [0x01] = { [0x81] = { ["0,0/0"] = fc { hit = 100, dmg = 5, hits = 1 } } } } }
    local free = Planner.plan(B, boardOf(M, E), sightOf(chip), style("careful"), { usePrice = "off" })
    a = Planner.plan(B, boardOf(M, E), sightOf(chip), style("careful"), { usePrice = "100000" })
    check(a and a.act, free and free.act, "one weapon: the price does not stop its strike")
    check(a and a.act, "attack", "and the chip is struck")
end

-- #644 review (PR #645, finding 8): a second attacker's wear follows the HP the plan leaves
-- its target. E has 10 HP; A's blow takes 6 for sure, B's two blows 4 each. Played at E's own
-- 10 HP, B throws both blows (2 uses); after A's blow E stands on 4, B's first blow kills it and
-- the second is never thrown: 1 use, as the game spends it. The plan's attacks both strike E;
-- whichever comes second spends what the HP the first leaves allows.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false, weapons = { { slot = 0, min = 1, max = 1 } } })
    local Bu = blue(0x02, 1, 2, 1, { minRange = false, weapons = { { slot = 0, min = 1, max = 1 } } })
    local E = red(0x81, 1, 1, { hp = 10, minRange = false })
    local staged
    local o = {
        reach = { [0x01] = tiles({ 0, 1 }), [0x02] = tiles({ 2, 1 }) },
        fc = { [0x01] = { [0x81] = { ["0,1"] = fc { hit = 100, dmg = 6, hits = 1, wearSlot = 0 } } },
               [0x02] = { [0x81] = { ["2,1"] = fc { hit = 100, dmg = 4, hits = 2, wearSlot = 0 } } } },
        enemyPhase = function(plan)
            staged = staged or plan
            return {}
        end,
    }
    local _, plan = Planner.plan(B, boardOf(A, Bu, E), sightOf(o), style("careful"))
    local order = {}
    for _, a in ipairs(plan and plan.acts or {}) do
        if a.act == "attack" then order[#order + 1] = a.unitId end
    end
    check(#order, 2, "#644 wear: both strike E")
    local wear = {}
    for _, b in ipairs(staged and staged.blues or {}) do wear[b.unit.id] = b.wear end
    -- first A (6, then B's first 4 kills: B 1 use) or first B (both its blows: 2; A's lands: 1)
    check((wear[0x01] or 0) .. ":" .. (wear[0x02] or 0),
          order[1] == 0x01 and "1:1" or "1:2",
          "#644 wear: the second attacker spends only the blows the HP left allows")
    check(Planner.wearAt({ [0] = 1, [4] = 1 }, 10), 2, "wearAt: both blows at the target's own HP")
    check(Planner.wearAt({ [0] = 1, [4] = 1 }, 4), 1, "wearAt: the second blow cut off at 4 HP")
end

-- #644 review (PR #645, finding 7): an enemy's weapon worn by countering our planned attack.
-- A's chip leaves E standing and E's counter throws a javelin from its bag slot 1, a use a
-- landed blow: the judged phase is told (plan.redWear) so E strikes with what it has left.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false, weapons = { { slot = 0, min = 1, max = 1 } } })
    local E = red(0x81, 0, 1, { hp = 20, minRange = false })
    local staged
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }) },
        fc = { [0x01] = { [0x81] = { ["0,0"] = fc { hit = 100, dmg = 5, hits = 1, wearSlot = 0,
                                                     counters = true, counterHit = 100,
                                                     counterDmg = 1, counterHits = 1,
                                                     counterSlot = 1 } } } },
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.slot then staged = plan end
            end
            return {}
        end,
    }
    local a = Planner.plan(B, boardOf(A, E), sightOf(o), style("bold"))
    check(a and a.act, "attack", "#644 counter wear: A chips E")
    local slots = staged and staged.redWear and staged.redWear[0x81] or {}
    check(slots[1], 1, "#644 counter wear: E's counter spent one use of its slot-1 weapon")
end

-- #642's shadow runs: the price never reaches the beam. A's Siegmund kill on E is the only
-- act that keeps C alive (E kills C in its phase); A's four waits outscore that strike once
-- its price is taken off its own score, so a beam that saw the price cut the kill before the
-- judge read C's death, and every plan judged lost C. Priced on the judged plan, the kill is
-- judged, alone under the cap, and played whatever its price.
do
    local SIEGMUND, STEEL = 0x92, 0x16
    local A = blue(0x01, 0, 0, 0, { minRange = false,
                                    weapons = { { slot = 0, min = 1, max = 1 },
                                                { slot = 1, min = 1, max = 1 } },
                                    items = { { id = SIEGMUND, uses = 20 },
                                              { id = STEEL, uses = 30 } } })
    local C = blue(0x02, 1, 3, 3, { minRange = false, hp = 10 })
    local E = red(0x81, 1, 0, { hp = 20, minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 0, 1 }, { 0, 2 }, { 0, 3 }, { 0, 4 }),
                  [0x02] = tiles({ 3, 3 }) },
        usePrice = function(id) return id == STEEL and 16 or nil end,
        fc = { [0x01] = { [0x81] = {
            ["0,0/0"] = fc { hit = 100, dmg = 30, hits = 1, killsTarget = true },
            ["0,0/1"] = fc { hit = 100, dmg = 10, hits = 1 } } } },
        enemyPhase = function(plan)
            if (plan.gone or {})[0x81] then return {} end
            return { { enemy = 0x81, target = 0x02, takenHit = 100, takenDmg = 99,
                       takenHits = 1, takenCrit = 0, targetHp = 10 } }
        end,
    }
    local a, plan = Planner.plan(B, boardOf(A, C, E), sightOf(o), style("careful"),
                                 { usePrice = "100000" })
    check(a and a.act .. "/" .. tostring(a.slot), "attack/0",
          "#642: the dear kill that saves a life is judged and struck, at any price")
    check(plan and plan.rank and plan.rank.admitted, true, "#642: and its plan is under the cap")
end

-- #642 review (PR #643): the spares. A carries a Siegmund (no price), a Spear (600 a use, dearer
-- than M.RARE_USE) and an Iron Lance (8 a use); all three make the same sure kill of E.
do
    local SIEGMUND, SPEAR, IRON = 0x92, 0x1A, 0x14
    local prices = { [SPEAR] = 600, [IRON] = 8 }
    local function bag(id)
        return blue(id, id - 1, 0, id - 1, { minRange = false,
            weapons = { { slot = 0, min = 1, max = 1 }, { slot = 1, min = 1, max = 1 },
                        { slot = 2, min = 1, max = 1 } },
            items = { { id = SIEGMUND, uses = 20 }, { id = SPEAR, uses = 15 },
                      { id = IRON, uses = 45 } } })
    end
    local kill = fc { hit = 100, dmg = 30, hits = 1, killsTarget = true }
    local function sightFor(units, extra)
        local o = { reach = {}, fc = {}, usePrice = function(id) return prices[id] end }
        for _, u in ipairs(units) do
            o.reach[u.id] = tiles({ 0, u.y })
            o.fc[u.id] = { [0x80 + u.id] = { ["0,0/0"] = kill, ["0,0/1"] = kill, ["0,0/2"] = kill,
                                              ["0," .. u.y .. "/0"] = kill,
                                              ["0," .. u.y .. "/1"] = kill,
                                              ["0," .. u.y .. "/2"] = kill } }
        end
        for k, v in pairs(extra or {}) do o[k] = v end
        return sightOf(o)
    end
    local A = bag(0x01)
    local E = red(0x81, 1, 0, { hp = 20, minRange = false })

    -- the charge: a weapon with no price is the dearest whatever a shop weapon costs per use
    check(B.useCharge(nil, 600, 600, 300), 300, "useCharge: no price, over a 600-gold spare: RARE_USE")
    check(B.useCharge(nil, 8, 600, 300), 892, "useCharge: no price: RARE_USE over the dearest spare")
    check(B.useCharge(600, 8, 600, 300), 592, "useCharge: two shop weapons: the difference")
    check(B.useCharge(nil, nil, nil, 300), 0, "useCharge: no priced weapon there: nothing")
    -- (finding 3) the Spear costs more a use than RARE_USE, yet the Siegmund is still the dear one
    local two = blue(0x01, 0, 0, 0, { minRange = false,
        weapons = { { slot = 0, min = 1, max = 1 }, { slot = 1, min = 1, max = 1 } },
        items = { { id = SIEGMUND, uses = 20 }, { id = SPEAR, uses = 15 } } })
    local a = Planner.plan(B, boardOf(two, E), sightFor({ two }), style("careful"))
    check(a and a.act .. "/" .. tostring(a.slot), "attack/1",
          "#642: a 600-gold Spear's use is spent before a Siegmund's")

    -- (finding 9) one strike with two spares: each judged once, no third "all swapped" plan;
    -- the cheapest (the Iron Lance) is played
    local plan
    a, plan = Planner.plan(B, boardOf(A, E), sightFor({ A }), style("careful"))
    local spares = 0
    for _, c in ipairs(plan and plan.considered or {}) do
        if c.kind == "spare" then spares = spares + 1 end
    end
    check(spares, 2, "#642: one strike's two spares are two plans, judged once each")
    check(a and a.act .. "/" .. tostring(a.slot), "attack/2", "#642: the cheapest spare strikes")
    -- (finding 9) two strikes with spares: the all-swapped plan takes each one's CHEAPEST spare
    local A2 = bag(0x02)
    local E2 = red(0x82, 1, 1, { hp = 20, minRange = false })
    local _, both = Planner.plan(B, boardOf(A, A2, E, E2), sightFor({ A, A2 }), style("careful"))
    local slots = {}
    for _, x in ipairs(both and both.acts or {}) do
        if x.act == "attack" then slots[#slots + 1] = x.unitId .. "/" .. tostring(x.slot) end
    end
    table.sort(slots)
    check(table.concat(slots, " "), "1/2 2/2", "#642: all swapped, each to its cheapest spare")

    -- (findings 1, 10) a spare is offered under its own key, and that key reads back its slot
    local cands = B.candidates(boardOf(A, E), sightFor({ A }), style("careful"))
    local byKey = Planner.offeredByKey(cands)
    check(byKey["1>attack@0,0>129#2"] and byKey["1>attack@0,0>129#2"].a.slot, 2,
          "#642: a spare is found by its own key")
    local back = Planner.unkey("1>attack@0,0>129~3,4#2")
    check(back.slot .. "/" .. tostring(back.slotKey) .. "/" .. back.canto.x .. "," .. back.targetId,
          "2/true/3,129", "#642: unkey reads a spare's slot back")
    -- (finding 6) a spare is told its exposure, as every offered act is
    local exposedSpares, spareCount = 0, 0
    for _, c in ipairs(cands) do
        for _, x in ipairs(c.acts) do
            for _, b in ipairs(x.spares or {}) do
                spareCount = spareCount + 1
                if type(b.exposure) == "table" then exposedSpares = exposedSpares + 1 end
            end
        end
    end
    check(spareCount > 0 and exposedSpares, spareCount, "#642: every spare's exposure is read")

    -- (finding 2) a replan's rest keeps a strike that played a spare
    local _, rested = Planner.plan(B, boardOf(A, E), sightFor({ A }), style("careful"),
                                   { rest = { "1>attack@0,0>129#2" } })
    local restKept
    for _, c in ipairs(rested and rested.considered or {}) do
        if c.kind == "rest" then restKept = c.acts[1] end
    end
    check(restKept, "1>attack@0,0>129#2", "#642: the rest of the plan keeps its spare's strike")

    -- (finding 5) a Canto strike's spares move on to the same tile
    local s = sightFor({ A })
    s.cantoTiles = function(_, x)
        if x.act ~= "attack" then return {} end
        return tiles({ 0, 0 }, { 0, 1 })
    end
    local cantoed, matched = 0, 0
    for _, c in ipairs(B.candidates(boardOf(A, E), s, style("bold"))) do
        for _, x in ipairs(c.acts) do
            if x.canto and x.spares then
                for _, b in ipairs(x.spares) do
                    cantoed = cantoed + 1
                    if b.canto and b.canto.x == x.canto.x and b.canto.y == x.canto.y then
                        matched = matched + 1
                    end
                end
            end
        end
    end
    check(cantoed > 0 and matched, cantoed, "#642: a Canto strike's spares move on with it")
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
    -- a door opened or a wall broken mid-phase (sight.mapKey): the enemy's path, so both again
    o.mapKey = "closed"
    B.decide(boardOf(A, moved, hurt), sight, style("careful"))
    local a0, s0 = sight.attacks(), sight.strikes()
    o.mapKey = "opened"
    B.decide(boardOf(A, moved, hurt), sight, style("careful"))
    check(sight.attacks() .. "/" .. sight.strikes(), (a0 + 1) .. "/" .. (s0 + 1),
          "a map the phase changed is a new attack and a new strike")
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

-- A reward claim lands in style.rewards and is played; a reinforcements claim's waves land
-- in style.waves beside its turns in style.arrivals.
do
    local wave = { turn = 8, units = { { class = 9, x = 13, y = 0, ai1 = 0, ai2 = 4, items = {} } } }
    local st = claimed("careful", { id = "r1", kind = "reward", item = 0x68, needs = "villages" },
        { id = "w1", kind = "reinforcements", turns = { 2, 8 }, waves = { wave } })
    check(#st.rewards, 1, "reward: style.rewards holds it")
    check(st.rewards[1].item, 0x68, "reward: its item")
    check(st.rewards[1].needs, "villages", "reward: its needs")
    check(#B.unplayed({ { id = "r1", kind = "reward", item = 0x68, needs = "villages" } }), 0,
        "reward: played")
    check(st.waves[1].turn, 8, "reinforcements: style.waves holds its waves")
    check(st.arrivals[1][2], 8, "reinforcements: style.arrivals keeps its turns")
    local ok = pcall(B.CLAIM_BEHAVIOURS.reward, { id = "r2", kind = "reward", needs = "villages" },
        style("careful"))
    check(ok, false, "reward without an item raises")
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
    -- a case that does not turn on the kind takes it from the id, as sight.demandsOf names them
    for _, d in ipairs(t.demands) do d.kind = d.kind or d.id:match("^%a+") end
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

-- fwd1 B: a demand few can answer is covered before the ones many can. Three fighters answer
-- three enemy classes each and the thief answers two demands, so "the most demands" alone
-- benched the only unit that can open a chest (vanilla Ch8, 30 of 68 parties).
local function test_team_covers_the_scarcest_demand_first()
    local roster = { teamUnit(1, 0x01, "foot"), teamUnit(2, 0x02, "foot"),
                     teamUnit(3, 0x03, "foot"), teamUnit(4, 0x04, "thief") }
    local demands = { { id = "enemy:1", need = 9 }, { id = "enemy:2", need = 9 },
                      { id = "enemy:3", need = 9 }, { id = "chests", need = 1 } }
    local fighter = { ["enemy:1"] = true, ["enemy:2"] = true, ["enemy:3"] = true }
    local answers = { [0x01] = fighter, [0x02] = fighter, [0x03] = fighter,
                      [0x04] = { chests = true, ["enemy:1"] = true } }
    local p = team({ roster = roster, cap = 2, demands = demands, answers = answers })
    check(csv(p.deploy), "4,1", "the chest's one answerer first, then the fighter covering most")
    check(table.concat(p.reasons[0x04].demands, ","), "enemy:1,chests", "and it covers all it answers")
    -- a Door Key's holder settles the doors the same way
    answers[0x04] = { doors = true }
    demands[4] = { id = "doors", need = 1 }
    p = team({ roster = roster, cap = 1, demands = demands, answers = answers })
    check(csv(p.deploy), "4", "one slot: the door's one answerer")
    -- among a scarce demand's answerers, the one covering the most open demands
    answers = { [0x01] = { chests = true }, [0x02] = { chests = true, fog = true },
                [0x03] = { fog = true } }
    demands = { { id = "chests", need = 1 }, { id = "fog", need = 1 } }
    p = team({ roster = roster, cap = 1, demands = demands, answers = answers })
    check(csv(p.deploy), "2", "two can open the chest: the one who also answers the fog")
    -- equally scarce, an enemy class waits: one fighter alone answers enemy:3, one thief alone
    -- the chest, and there is one slot (vanilla Ch8, campaign 4001: claims left three slots
    -- and three such classes were listed before the chest)
    demands = { { id = "enemy:3", kind = "enemy", need = 2 }, { id = "chests", kind = "chests", need = 1 } }
    answers = { [0x01] = { ["enemy:3"] = true }, [0x04] = { chests = true } }
    p = team({ roster = roster, cap = 1, demands = demands, answers = answers })
    check(csv(p.deploy), "4", "equally scarce: the chest before the enemy class")
    -- a demand nobody who fits can answer is passed over, never a stop
    answers = { [0x01] = { chests = true }, [0x02] = { chests = true, fog = true },
                [0x03] = { fog = true } }
    demands = { { id = "sustain", need = 1 }, { id = "fog", need = 1 } }
    p = team({ roster = roster, cap = 1, demands = demands, answers = answers })
    check(csv(p.deploy), "2", "an unanswerable demand does not end the covering")
end
test_team_covers_the_scarcest_demand_first()

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
    check(csv(p.deploy), "2,1,4,3",
          "covered scarcest first (one unit answers enemy:7), then fill: highest strength first")
    check(p.reasons[0x04].why, "fill", "reason: fill")
end
test_team_fill_is_the_best_answer_to_the_biggest_class()

local function test_team_ungrouped_class_raises_and_absent_carried_is_ignored()
    local ok = pcall(team, { roster = { unitOf(1, 0x01, 1) }, cap = 1 })
    check(ok, false, "a unit with no group raises: there is no default group")
    -- past the helper, which names a kind from the id: the tie-break reads the kind
    local err
    ok, err = pcall(B.team, { roster = { teamUnit(1, 0x01, "magic") }, cap = 1, maxima = {},
                              demands = { { id = "enemy:1", need = 1 } }, answers = {},
                              carried = {}, style = { deploy = {} } })
    check(ok, false, "a demand with no kind raises")
    check(tostring(err):match("enemy:1 has no kind") ~= nil, true, "and the error names it")
    local p = team({ roster = { teamUnit(1, 0x01, "magic") }, cap = 3,
                     carried = { [0x09] = true } })
    check(csv(p.deploy), "1", "a carried unit no longer on the roster (dead, departed) drops out")
end
test_team_ungrouped_class_raises_and_absent_carried_is_ignored()

-- A stock price every buyer pays (the game prices per buyer: GetItemPurchasePrice).
local function anyone(n) return setmetatable({}, { __index = function() return n end }) end

local function test_shop_stops_at_gold()
    local stock = {
        { item = 0x6C, price = anyone(300), vulnerary = true },
        { item = 0x10, price = anyone(500), type = "sword", maxUses = 46 },
        { item = 0x11, price = anyone(400), type = "sword", maxUses = 30 },
        { item = 0x12, price = anyone(900), type = "sword", maxUses = 20 },
        { item = 0x20, price = anyone(700), type = "lance", maxUses = 45 },
        { item = 0x21, price = anyone(100), type = "axe", maxUses = 45 },
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
    A.items = { { kind = "weapon", id = 0x10, type = "sword", rank = 1, usable = true, uses = 46 } }
    check(flat(B.shop(10000, stock, { A, Bu })), "2:108,2:32,1:108", "a unit holding its type buys none")
    local Cu = unitOf(3, 0x03, 1, { canUse = { [0x21] = true, [0x10] = true, [0x11] = true } })
    check(flat(B.shop(800, stock, { Cu })), "3:108,3:33,3:17",
        "skip-and-continue: exact fit, gold 800 buys vuln 300, axe 100, sword 400 in order")
    check(flat(B.shop(450, stock, { Cu })), "3:108,3:33",
        "the sword (400) is skipped at 50 gold, the buying stops there")
    A.items = { { kind = "weapon", id = 0x10, type = "sword", rank = 1, usable = true, uses = 46 }, { id = 0x6C, kind = "heal", vulnerary = true, uses = 3 } }
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

-- test_arms_is_the_shops_spend_order: Bot.arms is M.shop's own loop over the unarmed, so it
-- cannot say armed what the shop cannot pay for, nor read a unit holding one item when the shop
-- buys two. Fails on an arms that prices each unit against the whole purse and keeps the first
-- item it finds.
-- the item ids of a Bot.arms list
local function idsOf(list)
    local out = {}
    for i, it in ipairs(list) do out[i] = it.id end
    return out
end

local function test_arms_is_the_shops_spend_order()
    local sword = { item = 0x10, price = anyone(400), type = "sword", maxUses = 46 }
    local staff = { item = 0x4B, price = anyone(600), type = "staff", maxUses = 30 }
    local function lacking(id, canUse)
        return unitOf(id, id, 1, { canUse = canUse })
    end
    -- 600 gold, four units each lacking a 400 gold sword: the shop arms the first only
    local roster = {}
    for id = 1, 4 do roster[id] = lacking(id, { [0x10] = true }) end
    local bought = B.arms(600, { sword }, roster)
    local n = 0
    for _ in pairs(bought) do n = n + 1 end
    check(n, 1, "arms: 600 gold arms one of four units")
    check(type(bought[1]) == "table" and bought[1][1].id, 0x10, "arms: the first unit, with the sword")
    check(bought[1][1].uses, nil, "arms: a bought item's uses are the shop's (MakeNewItem)")
    local shop = B.shop(600, { sword }, roster)
    check(#shop, 1, "arms: the shop buys exactly that")
    check(shop[1].unit, 1, "arms: for the unit arms names")
    -- a unit that uses a staff and a sword is read holding both, as the shop buys both
    local both = B.arms(10000, { sword, staff }, { lacking(5, { [0x10] = true, [0x4B] = true }) })
    check(type(both[5]) == "table" and csv(idsOf(both[5])), "75,16", "arms: a staff user who wields a sword holds both (types in order)")
    local one = B.arms(10000, { sword, staff }, { lacking(6, { [0x10] = true }) })[6]
    check(type(one) == "table" and csv(idsOf(one)), "16",
          "arms: only what the unit can use")
    -- an armed unit's Vulnerary never takes the gold that arms an unarmed one: the unarmed
    -- are paid for first (500 gold: the 400 sword, not the 300 Vulnerary)
    local vulnerary = { item = 0x6C, price = anyone(300), vulnerary = true }
    local armedOne = unitOf(7, 7, 1, { canUse = { [0x10] = true }, items = {
        { kind = "weapon", id = 0x10, type = "sword", usable = true, uses = 46 } } })
    local bare = lacking(8, { [0x10] = true })
    bare.items = { { id = 0x6C, kind = "heal", vulnerary = true, uses = 3 } }
    local paid = B.shop(500, { vulnerary, sword }, { armedOne, bare })
    check(#paid == 1 and paid[1].unit .. ":" .. paid[1].item, "8:16",
          "shop: the unarmed unit's sword before the armed unit's Vulnerary")
    check(csv(idsOf(B.arms(500, { vulnerary, sword }, { armedOne, bare })[8])), "16",
          "and arms says so")
    -- a held weapon with no shop type (the Divinestone, ITYPE_DRAGN) still arms its holder
    local dragon = unitOf(9, 9, 1, { items = {
        { kind = "weapon", id = 0xAA, usable = true, uses = 20 } } })
    check(B.armed(dragon), true, "a usable weapon with no shop type arms its holder")
end
test_arms_is_the_shops_spend_order()

-- The shop arms a unit by the game's own facts (can-use, uses left), staves and tomes included
-- (#510 party plan, PR 1). Each case fails on the shop that buys only a weapon type the unit
-- "holds none of".
local function test_shop_arms_by_usable_items_with_uses_left()

    local stock = {
        { item = 0x6C, price = anyone(300), vulnerary = true },
        { item = 0x4B, price = anyone(600), type = "staff", maxUses = 30 },
        { item = 0x4D, price = anyone(900), type = "anima", maxUses = 40 },
        { item = 0x20, price = anyone(400), type = "lance", maxUses = 45 },
    }
    local function flat(r)
        local t = {}
        for _, e in ipairs(r) do t[#t + 1] = e.unit .. ":" .. e.item end
        return csv(t)
    end
    local vuln = { id = 0x6C, kind = "heal", vulnerary = true, uses = 3 }
    -- a healer with no staff buys one
    local healer = unitOf(1, 0x01, 1, { canUse = { [0x4B] = true }, items = { vuln } })
    check(flat(B.shop(10000, stock, { healer })), "1:75", "a healer with no staff buys one")
    check(B.armed(healer), false, "a healer with no staff is not armed")
    check(csv(idsOf(B.arms(10000, stock, { healer })[0x01])), "75", "the pick is told what arms it")
    healer.items[#healer.items + 1] = { kind = "weapon", id = 0x4B, type = "staff", usable = true, uses = 30 }
    check(flat(B.shop(10000, stock, { healer })), "", "a healer with a full staff buys none")
    check(B.armed(healer), true, "a healer with a staff is armed")
    check(B.arms(10000, stock, { healer })[0x01], nil, "an armed unit needs nothing")
    -- a unit whose only tome has 0 uses buys one
    local mage = unitOf(2, 0x02, 1, { canUse = { [0x4D] = true }, items = { vuln,
        { kind = "weapon", id = 0x4D, type = "anima", usable = true, uses = 0 } } })
    check(flat(B.shop(10000, stock, { mage })), "2:77", "a tome with 0 uses is replaced")
    mage.items[2].uses = 40
    check(flat(B.shop(10000, stock, { mage })), "", "a full tome buys no spare")
    -- a held weapon the unit cannot use does not count
    local knight = unitOf(3, 0x03, 1, { canUse = { [0x20] = true }, items = { vuln,
        { kind = "weapon", id = 0x21, type = "lance", usable = false, uses = 30 } } })
    check(B.armed(knight), false, "a lance the game says it cannot use is not armed")
    check(flat(B.shop(10000, stock, { knight })), "3:32", "and a lance it can use is bought")
    -- a full bag buys nothing
    local full = unitOf(4, 0x04, 1, { canUse = { [0x20] = true }, items = {
        { id = 1, kind = "other" }, { id = 2, kind = "other" }, { id = 3, kind = "other" },
        { id = 4, kind = "other" }, { id = 5, kind = "other" } } })
    check(flat(B.shop(10000, stock, { full })), "", "a full bag buys nothing")
    check(B.arms(10000, stock, { full })[0x04], nil, "and cannot be armed")
    -- one free slot goes to the arms, not the Vulnerary
    local one = unitOf(5, 0x05, 1, { canUse = { [0x20] = true }, items = {
        { id = 1, kind = "other" }, { id = 2, kind = "other" }, { id = 3, kind = "other" },
        { id = 4, kind = "other" } } })
    check(flat(B.shop(10000, stock, { one })), "5:32", "the last slot arms the unit")
    -- gold decides: no gold, no arms
    check(B.arms(100, stock, { knight })[0x03], nil, "a unit the gold cannot arm is not armed")
end
test_shop_arms_by_usable_items_with_uses_left()

-- test_shop_budgets_at_the_buyers_price: a Silver Card halves A's prices only, so 450 gold buys
-- B's Vulnerary (300) and A's (150); priced at B's 300 for both, A's would not fit.
local function test_shop_budgets_at_the_buyers_price()
    local stock = { { item = 0x6C, price = { [0x01] = 150, [0x02] = 300 }, vulnerary = true } }
    local t = {}
    for _, e in ipairs(B.shop(450, stock, { unitOf(2, 0x02, 1), unitOf(1, 0x01, 1) })) do
        t[#t + 1] = e.unit .. ":" .. e.item
    end
    check(csv(t), "2:108,1:108", "each buyer pays its own price: 300 + 150 fit in 450")
end
test_shop_budgets_at_the_buyers_price()

-- ── the convoy gives back (the party plan's PR 2; #510 comment 6872948037) ──────────────
do
    local function lance(uses) return { kind = "weapon", id = 0x14, type = "lance", rank = 1,
                                        usable = true, uses = uses or 40 } end
    -- an item with the game's per-unit facts (api.convoy's `for`); `own` = its holder's
    local function item(id, facts, own)
        local it = { id = id, kind = "other", uses = 1, ["for"] = facts }
        for k, v in pairs(own or {}) do it[k] = v end
        return it
    end
    local function acts(list)
        local out = {}
        for _, a in ipairs(list) do
            out[#out + 1] = string.format("%s %d:%X", a.act, a.unit, a.item)
        end
        return table.concat(out, ", ")
    end
    local function armedUnit(charId, level, extra)
        local u = unitOf(charId, charId, level, extra)
        u.items = u.items[1] and u.items or { lance() }
        return u
    end

    -- 3. a convoy seal goes to the highest-level unit the game says it promotes; one nobody
    -- can use stays (fails on main: no Bot.uses, and the old promote read only the own bag)
    local crest = item(0x65, { [1] = { promotes = true }, [2] = { promotes = true } })
    check(acts(B.uses({ armedUnit(1, 10), armedUnit(2, 12) }, { crest })), "take 2:65, use 2:65",
        "uses: the convoy's seal to the highest level the game accepts")
    check(acts(B.uses({ armedUnit(1, 10) }, { item(0x65, { [1] = {} }) })), "",
        "uses: a seal the game says promotes nobody stays")
    local own = armedUnit(3, 10, { items = { lance(), item(0x64, nil, { promotes = true }) } })
    check(acts(B.uses({ own }, { item(0x64, { [3] = { promotes = true } }) })), "use 3:64",
        "uses: its own seal first, nothing taken")
    check(B.uses({ own }, {})[1].seal, true, "uses: a seal's use says so (api.use checks the class)")
    check(B.uses({ armedUnit(8, 3, { items = { lance(), item(0x5B, nil, { gains = true }) } }) },
        {})[1].seal, nil, "uses: a booster's does not")
    -- one use a unit a chapter, the seal before the booster
    local both = armedUnit(4, 10, { items = { lance(), item(0x64, nil, { promotes = true }),
                                              item(0x5C, nil, { gains = true }) } })
    check(acts(B.uses({ both }, {})), "use 4:64", "uses: one use a unit, the seal first")

    -- #639: style.sealAt is the level a promotion item is used at (nil: 10, the game's floor).
    -- A L12 unit's own seal and a convoy's seal are both used at 10 and neither at 20; a L20
    -- unit uses one at 20. The seal is kept where it is: no take from the convoy, and Bot.supply
    -- (which runs before the shop and never reads the style) does not give the bag's seal away,
    -- since the game says it promotes the holder.
    local ownSeal = armedUnit(6, 12, { items = { lance(), item(0x64, nil, { promotes = true, use = "seal" }) } })
    local convoySeal = item(0x65, { [7] = { promotes = true } })
    -- nil is "no floor of ours": the game's own L10 check decides. The suites' fake units sit
    -- under L10 with seals the fake game says promote them, so a literal 10 would skip them.
    check(acts(B.uses({ ownSeal }, {})), "use 6:64", "sealAt nil: a L12 unit uses its seal")
    check(acts(B.uses({ ownSeal }, {}, { sealAt = 10 })), "use 6:64", "sealAt 10: a L12 unit uses its seal")
    check(acts(B.uses({ ownSeal }, {}, { sealAt = 20 })), "", "sealAt 20: a L12 unit keeps its seal")
    check(acts(B.uses({ armedUnit(7, 12) }, { convoySeal })), "take 7:65, use 7:65",
        "sealAt nil: the convoy's seal goes to a L12 unit")
    check(acts(B.uses({ armedUnit(7, 12) }, { convoySeal }, { sealAt = 20 })), "",
        "sealAt 20: the convoy's seal stays in the convoy")
    check(acts(B.uses({ armedUnit(7, 20) }, { convoySeal }, { sealAt = 20 })), "take 7:65, use 7:65",
        "sealAt 20: a L20 unit takes and uses it")
    check(acts(B.uses({ armedUnit(7, 19), armedUnit(8, 20) },
            { item(0x65, { [7] = { promotes = true }, [8] = { promotes = true } }) }, { sealAt = 20 })),
        "take 8:65, use 8:65", "sealAt 20: only the L20 unit of two promotes")
    check(acts(B.supply({ ownSeal }, {})), "", "sealAt 20: supply keeps a seal that promotes its holder")
    check(acts(B.supply({ ownSeal }, { convoySeal })), "",
        "sealAt 20: supply neither gives the bag's seal away nor takes a seal from the convoy")

    -- 4. a booster: the forced unit first, then the lowest level; nobody when the game says no
    -- stat gains
    local lord = armedUnit(1, 5, { forced = true })
    local low = armedUnit(2, 2)
    local robe = function(f) return item(0x5B, f) end
    check(acts(B.uses({ low, lord }, { robe({ [1] = { gains = true }, [2] = { gains = true } }) })),
        "take 1:5B, use 1:5B", "uses: a booster to the unit the game forces onto the map")
    check(acts(B.uses({ low, lord, armedUnit(3, 9) },
            { robe({ [2] = { gains = true }, [3] = { gains = true } }) })),
        "take 2:5B, use 2:5B", "uses: then the lowest level")
    check(acts(B.uses({ low, lord }, { robe({ [1] = {}, [2] = {} }) })), "",
        "uses: no gain, no booster (CanUnitUseStatGainItem says no at a cap)")

    -- a full bag gives first what Bot.fullBag sends (money), then takes and uses
    local fullU = armedUnit(5, 10, { items = { lance(), lance(30), { kind = "heal", uses = 3 },
                                              { kind = "key", id = 0x69, uses = 1 },
                                              { kind = "money", id = 0xBC, uses = 1 } } })
    check(acts(B.uses({ fullU }, { item(0x65, { [5] = { promotes = true } }) })),
        "give 5:BC, take 5:65, use 5:65", "uses: a full bag gives its gem first")

    -- 1. a seal its holder cannot use goes back, whether another roster unit can use it today
    -- (the ring) or nobody yet (the bolt: every user under level 10)
    local ring = item(0x68, { [1] = {}, [9] = { promotes = true } }, { use = "seal" })
    local bolt = item(0x67, { [1] = {}, [9] = {} }, { use = "seal" })
    local holder = armedUnit(1, 4, { items = { lance(), ring, bolt } })
    check(acts(B.supply({ holder }, {})), "give 1:67, give 1:68",
        "supply: a seal its holder cannot use goes to the convoy, used by anyone today or not")

    -- a full convoy (Board.CONVOY_ITEM_COUNT) takes no give: the ring stays in the bag, and a
    -- full bag that would have to give to make room takes nothing (api.give would refuse both)
    local full = {}
    for k = 1, Board.CONVOY_ITEM_COUNT do full[k] = item(0x6C, {}) end
    check(acts(B.supply({ armedUnit(1, 4, { items = { lance(), ring } }) }, full)), "",
        "supply: a full convoy takes no give")
    local packed = armedUnit(5, 10, { items = { lance(), lance(30), { kind = "heal", uses = 3 },
                                               { kind = "key", id = 0x69, uses = 1 },
                                               { kind = "money", id = 0xBC, uses = 1 } } })
    full[Board.CONVOY_ITEM_COUNT] = item(0x65, { [5] = { promotes = true } })
    check(acts(B.uses({ packed }, full)), "", "uses: a full bag cannot make room in a full convoy")

    -- 2. convoy weapons: the unarmed first, the best of the type it can use, uses left
    local function tome(id, rank, uses, users, maxUses)
        local f = {}
        for _, c in ipairs(users) do f[c] = { usable = true } end
        return { id = id, kind = "weapon", type = "anima", rank = rank, uses = uses,
                 maxUses = maxUses or 40, ["for"] = f }
    end
    local swordsman = armedUnit(6, 8)   -- armed with a lance; can use anima, holds none
    local mage = unitOf(7, 7, 10)       -- nothing in hand (its tome broke)
    local convoy = { tome(0x38, 1, 40, { 6, 7 }), tome(0x39, 2, 30, { 6, 7 }, 30), tome(0x3A, 3, 0, { 6, 7 }) }
    check(acts(B.supply({ swordsman, mage }, convoy)), "take 7:39, take 6:38",
        "supply: the unarmed mage first takes the best tome with uses left, then the armed unit")
    check(acts(B.supply({ mage }, { tome(0x38, 1, 40, { 6 }) })), "",
        "supply: a tome the game says the unit cannot use is never taken")

    -- Bot.arms reads the convoy before the shop: the tome comes from storage, so the shop buys
    -- none of that type
    local fire = { item = 0x38, price = anyone(560), type = "anima", maxUses = 40 }
    local m2 = unitOf(7, 7, 10, { canUse = { [0x38] = true } })
    local got = B.arms(10000, { fire }, { m2 }, { tome(0x39, 2, 30, { 7 }, 30) })[7]
    check(type(got) == "table" and #got == 1 and got[1].id == 0x39 and got[1].uses, 30,
        "arms: the convoy's Elfire at its own uses, and nothing bought")
    check(type(B.arms(10000, { fire }, { m2 })[7]) == "table"
        and B.arms(10000, { fire }, { m2 })[7][1].id, 0x38, "arms: no convoy, the shop's Fire")

    -- Rule A (#510 comment 6896261936): what a unit cannot use this chapter goes to the
    -- convoy. Each case fails on the supply that gave only a seal or booster some roster unit
    -- could use today, and read no benched bag.
    local axe = { kind = "weapon", id = 0x1F, type = "axe", rank = 1, usable = false, uses = 45,
                  maxUses = 45 }
    local vuln = { kind = "heal", id = 0x6C, uses = 3, vulnerary = true }
    local keeper = armedUnit(2, 7, { items = { lance(), axe, vuln,
        item(0x65, nil, { use = "seal", promotes = true }) } })
    check(acts(B.supply({ keeper }, {})), "give 2:1F",
        "supply: a weapon its holder cannot use goes back; a usable seal and a Vulnerary stay")
    local energy = item(0x5C, { [3] = { gains = true } }, { use = "booster", gains = true })
    local bench = armedUnit(9, 5, { items = { lance(), energy, vuln, axe,
        item(0x68, nil, { use = "seal", promotes = true }) } })
    check(acts(B.supply({}, {}, { bench })), "give 9:68, give 9:1F, give 9:5C",
        "supply: a benched unit gives its seals and boosters, usable or not, and what it "
            .. "cannot wield; it keeps its lance and Vulnerary")
    check(acts(B.supply({ keeper }, full, { bench })), "",
        "supply: a full convoy takes no give from the benched either")

    -- Rule B: a unit is short of a type below one full weapon of it, so a spare comes before
    -- the last one breaks. Fails on the lackedTypes that asked only "holds none with uses left".
    local function bow(uses, maxUses, users)
        local f = {}
        for _, c in ipairs(users or {}) do f[c] = { usable = true } end
        return { kind = "weapon", id = 0x2D, type = "bow", rank = 3, uses = uses,
                 maxUses = maxUses, usable = true, ["for"] = f }
    end
    local sniper = unitOf(11, 11, 12, { items = { bow(4, 20) } })
    check(acts(B.supply({ sniper }, { bow(45, 45, { 11 }) })), "take 11:2D",
        "supply: a bow with 4 of 20 uses left takes the convoy's bow")
    -- the convoy's bow that ends the shortage beats a higher-rank one that does not (else the
    -- shop buys another after it; review of #624)
    local worn = bow(2, 20, { 11 })
    local iron = bow(45, 45, { 11 })
    iron.id, iron.rank = 0x2C, 1
    check(acts(B.supply({ sniper }, { worn, iron })), "take 11:2C",
        "supply: a 4-use Silver Bow takes the full Iron Bow, not a 2-use Silver Bow")
    sniper.items = { bow(20, 20) }
    check(acts(B.supply({ sniper }, { bow(45, 45, { 11 }) })), "",
        "supply: a full Silver Bow takes no spare (the smallest full weapon held counts)")
    local ironSword = { item = 0x01, price = anyone(460), type = "sword", maxUses = 46 }
    local lord = unitOf(12, 12, 7, { canUse = { [0x01] = true }, items = {
        { kind = "weapon", id = 0x09, type = "sword", rank = 1, usable = true, uses = 4,
          maxUses = 40 }, vuln } })
    local bought = B.shop(10000, { ironSword }, { lord })
    check(#bought == 1 and bought[1].item, 0x01, "shop: a Rapier with 4 of 40 uses buys an Iron Sword")
    lord.items[1].uses = 40
    check(#B.shop(10000, { ironSword }, { lord }), 0, "shop: a full Rapier buys none")
    -- the line is half a weapon (Nicolas, 2026-11-15): 20 of 40 is not short, 19 is
    lord.items[1].uses = 20
    check(#B.shop(10000, { ironSword }, { lord }), 0, "shop: a Rapier at half its uses buys none")
    lord.items[1].uses = 19
    check(#B.shop(10000, { ironSword }, { lord }), 1, "shop: a Rapier under half buys a sword")
    check(B.armed(sniper) and B.armed(lord), true, "rule B does not change who is armed")
    lord.canUse[0x02] = true
    local ok, err = pcall(B.shop, 10000, { { item = 0x02, price = anyone(1), type = "sword" } },
                          { lord })
    check(not ok and tostring(err):find("has no maxUses", 1, true) ~= nil, true,
        "shop: a stock weapon without its full uses raises, never reads as 'holds none'")
end

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
                 effective = o.effective, usable = o.usable ~= false, uses = o.uses or 30,
                 maxUses = 30 }
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
    -- short of the type is the shop's own test (rule B): a lance at 4 of 30 uses wants a new
    -- one of the same rank, and the gem makes room (review of #624: fullBag asked "holds none")
    check(F({ lance(1, { uses = 4 }), heal(), key, gem, heal() }, lance(1)), 4,
          "bag: a lance near breaking takes a full one of its rank")
    check(F({ lance(1), heal(), key, gem, heal() }, lance(1)), 0,
          "bag: a full lance takes no duplicate")
    check(F({ lance(1), heal(), key, gem, lance(2) }, { kind = "other", use = "seal" }), 0,
          "bag: a seal goes")
    -- a seal or booster its holder can use is kept in hand (Bot.uses spends it): wanted when
    -- new, and never the one that leaves (fails on main: "a seal or booster" leaves second)
    check(F({ lance(1), heal(), key, gem, lance(2) }, { kind = "other", use = "seal", promotes = true }), 4,
          "bag: a seal its holder can use stays, the gem goes")
    check(F({ lance(1), heal(), key, { kind = "other", use = "booster", gains = true }, lance(2) },
            lance(4)), 1,
          "bag: a usable booster is kept, the beaten lance goes")
    check(F({ lance(1), heal(), key, { kind = "other", use = "seal" }, lance(2) }, lance(4)), 4,
          "bag: a seal it cannot use still goes first")
    -- #639: at sealAt 20 a seal is held for many chapters, so a held seal the game says
    -- promotes its holder is never what leaves, convoy full or not: the new key goes instead
    -- (0) and a beaten lance leaves before it
    local held = { lance(1, { maxRange = 2 }), { kind = "other", use = "seal", promotes = true }, heal(),
                   lance(3, { effective = "armour" }), lance(3) }
    check(F(held, key), 0, "bag: a held seal that promotes stays, the new key goes (convoy not full)")
    check(F(held, key, true), 0, "bag: a held seal that promotes stays, the new key goes (convoy full)")
    local withBeaten = { lance(1), { kind = "other", use = "seal", promotes = true }, heal(), key, lance(2) }
    check(F(withBeaten, lance(4)), 1, "bag: the beaten lance leaves, not the held seal (convoy not full)")
    check(F(withBeaten, lance(4), true), 1, "bag: the beaten lance leaves, not the held seal (convoy full)")
    -- an item that is neither a seal nor a booster (Pure Water) is never sent as one; the
    -- beaten lance goes instead (review of #626: the test asked only `kind == "other"`)
    check(F({ lance(1), heal(), key, { kind = "other", id = 0x6E }, lance(2) }, lance(4)), 1,
          "bag: Pure Water is not sent as a seal")
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

-- test_the_judged_phase_plays_with_the_door_open: A opens the door at (2,0); the enemy phase
-- judging that plan is staged with the door open (plan.opened), so the enemies behind it can
-- reach A. Vanilla Ch3: Colm opened (6,9), the phase was judged with it shut, and the Brigand
-- behind it killed him at a predicted 0%.
do
    local A = blue(0x01, 0, 0, 0)
    local E = red(0x81, 4, 0, { isBoss = true, minRange = false })
    local seen = {}
    local o = {
        objective = { kind = "boss" }, reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        field = fieldsOf { ["4,0"] = BOSS_SIDE, ["2,0"] = FROM_WALL },
        obstacles = {}, doors = { { x = 2, y = 0 } }, openers = { [0x01] = true },
        enemyPhase = function(plan)
            for k in pairs(plan.opened or {}) do seen[k] = true end
            return {}
        end,
    }
    local a = Planner.plan(B, boardOf(A, E), sightOf(o), style("careful"))
    check(a and a.act, "door", "opened: the plan opens the door")
    check(seen["2,0"], true, "opened: its enemy phase is judged with the door open")
end

-- test_a_plan_steps_through_the_door_it_opens (#661): K, beside the door at (2,0), holds the
-- key; the boss E stands behind it at (3,0). D, at (1,1), can reach the doorway only once it is
-- open. A plan that opens the door and leaves the doorway empty lets E strike K dead; one where
-- D steps into the doorway after the door (holding it, or striking E from it) has E strike D,
-- who stands it. Each unit's acts were
-- listed once, on the shut map, so no plan ever had D in the doorway (vanilla Ch8, seed 4002:
-- 101 plans opened (20,7), none with an act on or past it, every one over the cap). The units a
-- plan has not used and whose reach the door changes (D, not F) gain the acts from their new
-- tiles, read on the map it leaves (sight.changed).
do
    local K = blue(0x01, 0, 1, 0)
    local D = blue(0x02, 1, 1, 1)
    local F = blue(0x03, 2, 0, 2)
    local E = red(0x81, 3, 0, { isBoss = true })
    -- D's reach holds K's tile (sight.reach with friends: an ally's tile is passed through)
    local shut = { [0x01] = tiles({ 1, 0 }, { 0, 0 }), [0x02] = tiles({ 1, 1 }, { 0, 1 }, { 1, 0 }),
                   [0x03] = tiles({ 0, 2 }) }
    local open = { [0x01] = shut[0x01], [0x02] = tiles({ 1, 1 }, { 0, 1 }, { 1, 0 }, { 2, 0 }),
                   [0x03] = shut[0x03] }
    local o = {
        objective = { kind = "boss" }, reach = shut,
        field = fieldsOf { ["3,0"] = { ["3,0"] = 0 },
                           ["2,0"] = { ["0,0"] = 2, ["1,0"] = 1, ["2,0"] = 0, ["3,0"] = 1,
                                       ["0,1"] = 3, ["1,1"] = 2 } },
        obstacles = {}, doors = { { x = 2, y = 0 } }, openers = { [0x01] = true },
        change = function(c)
            if c.opened["2,0"] then return { reach = open, doors = {}, mapKey = "open" } end
            return {}
        end,
        enemyPhase = function(plan)
            if not (plan.opened or {})["2,0"] then return {} end
            for _, b in ipairs(plan.blues) do
                if b.x == 2 and b.y == 0 then
                    return { { enemy = 0x81, target = b.unit.id, takenHit = 100, takenDmg = 3,
                               takenHits = 1, strikerHp = 20 } }
                end
            end
            return { { enemy = 0x81, target = 0x01, takenHit = 100, takenDmg = 99,
                       takenHits = 1, strikerHp = 20 } }
        end,
    }
    local sight = sightOf(o)
    local _, plan = Planner.plan(B, boardOf(K, D, F, E), sight, style("careful"))
    local order = {}
    for _, a in ipairs(plan and plan.acts or {}) do
        order[#order + 1] = a.unitId .. ">" .. a.act .. "@" .. at(a)
    end
    order = table.concat(order, " ")
    -- D in the doorway: holding it, or striking E from it
    local door, block = order:find("1>door@1,0", 1, true), order:find("2>%a+@2,0")
    check(door ~= nil and block ~= nil and door < block, true,
          "relist: K opens the door, then D acts from the doorway (" .. order .. ")")
    check(#(sight.changes or {}), 1, "relist: one re-listing for the one door, however many plans open it")
    -- F's reach is the same with the door open: it keeps its board menu (the cost, ADR 0431)
    local fAct, dAct
    for _, a in ipairs(plan and plan.acts or {}) do
        if a.unitId == 0x03 then fAct = a end
        if a.unitId == 0x02 then dAct = a end
    end
    check(fAct ~= nil and fAct.map == nil and dAct ~= nil and dAct.map ~= nil, true,
          "relist: only D, whose reach the door changes, gains acts")
end

-- test_a_relisted_unit_with_only_an_allys_tile_does_not_crash: a re-listing (opts.tiles) can
-- leave a unit only a tile an ally stands on (its reach passes through allies); its march then
-- has no tile, and building an act on none crashed vanilla Ch8 (relist661c, turn 16)
do
    local A = blue(0x01, 0, 0, 0)
    local C = blue(0x02, 1, 1, 0)
    local E = red(0x81, 4, 0)
    local sight = sightOf({ reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) } })
    local ok, cands = pcall(B.candidates, boardOf(A, C, E), sight, style("careful"),
                            { only = { [0x01] = true }, tiles = { [0x01] = { ["1,0"] = true } } })
    local off = true
    for _, c in ipairs(ok and cands or {}) do
        for _, a in ipairs(c.acts) do off = off and a.move.x == 1 and a.move.y == 0 end
    end
    check(ok and off, true, "relist: a unit left only an ally's tile lists acts on it alone ("
          .. tostring(ok and "" or cands) .. ")")
    -- and none at all (every tile it reached filtered out), on a boss map with a staff, a
    -- Vulnerary and a village to read
    local H = blue(0x03, 2, 0, 1)
    local boss = red(0x82, 6, 0, { isBoss = true })
    local s2 = sightOf({ objective = { kind = "boss" }, reach = { [0x01] = tiles({ 0, 0 }),
                         [0x03] = tiles({ 0, 1 }) }, staves = { [0x03] = { { slot = 0 } } },
                         heals = { [0x03] = {} }, mend = { [0x01] = { slot = 1, amount = 10 } },
                         explorable = { { x = 0, y = 0, kind = "visit" } }, closings = {} })
    local A2 = blue(0x01, 0, 0, 0, { hp = 10, maxhp = 20 })
    local ok2, err2 = pcall(B.candidates, boardOf(A2, C, H, E, boss), s2, style("careful"),
                            { only = { [0x01] = true, [0x03] = true },
                              tiles = { [0x01] = {}, [0x03] = {} } })
    check(ok2, true, "relist: a unit left no tile lists without a crash (" .. tostring(ok2 or err2) .. ")")
end

-- test_a_plan_steps_onto_the_tile_its_kill_frees (#670): E1 holds the one tile, (1,0), between
-- D at (0,0) and the boss E2 at (3,0). K, at (1,1), kills E1 for sure. D reaches (2,0), beside
-- the boss, only through E1's tile, so only once the kill is in the plan. Each unit's acts were
-- listed on the board before anyone acts, where E1 stands: no plan in ~1,300 (4 traces) moved
-- a unit onto a tile an earlier act's kill freed. The plan's kills change the board as a door
-- does (sight.changed's gone).
do
    local K = blue(0x01, 0, 1, 1)
    local D = blue(0x02, 1, 0, 0)
    local E1 = red(0x81, 1, 0)
    local E2 = red(0x82, 3, 0, { isBoss = true, minRange = false })
    local o = {
        objective = { kind = "boss" },
        reach = { [0x01] = tiles({ 1, 1 }), [0x02] = tiles({ 0, 0 }, { 0, 1 }) },
        fc = { [0x01] = { [0x81] = { ["1,1"] = fc { hit = 100, dmg = 99, hits = 1 } } },
               [0x02] = { [0x82] = { ["2,0"] = fc { hit = 100, dmg = 8, hits = 1 } } } },
        change = function(c)
            if c.gone[0x81] then
                return { reach = { [0x01] = tiles({ 1, 1 }),
                                   [0x02] = tiles({ 0, 0 }, { 0, 1 }, { 1, 0 }, { 2, 0 }) } }
            end
            return {}
        end,
        enemyPhase = function() return {} end,
    }
    local sight = sightOf(o)
    local _, plan = Planner.plan(B, boardOf(K, D, E1, E2), sight, style("careful"))
    local order = {}
    for _, a in ipairs(plan and plan.acts or {}) do
        order[#order + 1] = a.unitId .. ">" .. a.act .. "@" .. at(a)
    end
    order = table.concat(order, " ")
    local kill, step = order:find("1>attack@1,1", 1, true), order:find("2>attack@2,0", 1, true)
    check(kill ~= nil and step ~= nil and kill < step, true,
          "relist: K kills E1, then D strikes the boss through its tile (" .. order .. ")")
end

-- test_a_key_no_one_can_reach_opens_nothing: the same cut, A holds no key, and the one Door
-- Key is on D, inside behind the door it opens. That door is no way, so A still strikes the
-- wall (PR #596 review: the door was listed whenever any holder stood, and A marched to a door
-- it could never open).
do
    local A = blue(0x01, 0, 0, 0)
    local E = red(0x81, 4, 0, { isBoss = true, minRange = false })
    local D = red(0x82, 3, 1, { minRange = false })
    local o = {
        objective = { kind = "boss" }, reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        field = fieldsOf { ["4,0"] = BOSS_SIDE, ["2,0"] = FROM_WALL, ["3,1"] = { ["3,1"] = 0 } },
        obstacles = { { x = 2, y = 0, hp = 20 } }, doors = { { x = 2, y = 0 } },
        locked = { [0x01] = { ["2,0"] = "door" } }, keySources = { door = { D } },
    }
    check(B.decide(boardOf(A, E, D), sightOf(o), style("careful")).act, "attack",
          "keys: a Door Key no one can reach leaves the wall the way")
    -- D reachable only through the wall: the door's way runs through it, so the wall is struck
    D.y = 0
    o.field = fieldsOf { ["4,0"] = BOSS_SIDE, ["2,0"] = FROM_WALL,
                         ["3,0"] = { ["3,0"] = 0, ["4,0"] = 1 } }
    check(B.decide(boardOf(A, E, D), sightOf(o), style("careful")).act, "attack",
          "keys: the key's way through the wall strikes the wall")
end

-- test_a_door_no_one_can_walk_to_ends: A is cut off from the boss by the wall at (2,0); a
-- locked door stands at (6,0) that neither A nor the Door Key's holder K can walk to. Asking
-- whether that door opens asked for the same breach again without end (a stack overflow, PR
-- #596 re-review); A strikes the wall.
do
    local A = blue(0x01, 0, 0, 0)
    local E = red(0x81, 4, 0, { isBoss = true, minRange = false })
    local K = red(0x82, 0, 5, { minRange = false })
    local o = {
        objective = { kind = "boss" }, reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        field = fieldsOf { ["4,0"] = BOSS_SIDE, ["2,0"] = FROM_WALL,
                           ["0,5"] = { ["0,5"] = 0, ["0,0"] = 5 }, ["6,0"] = { ["6,0"] = 0 } },
        obstacles = { { x = 2, y = 0, hp = 20 } }, doors = { { x = 6, y = 0 } },
        locked = { [0x01] = { ["6,0"] = "door" } }, keySources = { door = { K } },
    }
    local ok, a = pcall(B.decide, boardOf(A, E, K), sightOf(o), style("careful"))
    check(ok and a and a.act, "attack", "keys: an unreachable door's question ends; the wall")
end

-- test_a_plan_strikes_a_wall_only_while_it_stands: A and C are both cut off by the wall at
-- (2,0). A blow that breaks it leaves C nothing to strike, so the plan holds one strike, not
-- two (vanilla Ch3 planned two, and the second crashed); a wall one blow leaves standing is
-- struck by both. The blow is the game's forecast (sight.strikeWall).
do
    local A = blue(0x01, 0, 0, 0)
    local C = blue(0x02, 1, 0, 1)
    local E = red(0x81, 4, 0, { isBoss = true, minRange = false })
    local function strikes(blowDmg)
        local o = {
            objective = { kind = "boss" },
            reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x02] = tiles({ 0, 1 }, { 1, 1 }, { 2, 1 }) },
            field = fieldsOf { ["4,0"] = BOSS_SIDE,
                               ["2,0"] = { ["0,0"] = 2, ["1,0"] = 1, ["2,0"] = 0, ["3,0"] = 1,
                                           ["4,0"] = 2, ["0,1"] = 3, ["1,1"] = 2, ["2,1"] = 1 } },
            obstacles = { { x = 2, y = 0, hp = 10 } },
        }
        local sight = sightOf(o)
        sight.strikeWall = function() return { dealt = blowDmg } end
        local _, plan = Planner.plan(B, boardOf(A, C, E), sight, style("careful"))
        local n = 0
        for _, a in ipairs(plan and plan.acts or {}) do
            if a.obstacle then n = n + 1 end
        end
        return n
    end
    check(strikes(10), 1, "wall: a blow that breaks it is the only strike planned")
    check(strikes(4), 2, "wall: a wall the first blow leaves standing is struck again")
    -- #644 review (finding 10): a wall strike spends its weapon's uses as any blow does
    -- (BattleApplyUnitUpdates writes the actor's weapon back), so the judged phase arms the
    -- striker with what the strike leaves: the forecast's wear (sight.strikeWall's M.worn)
    local o = {
        objective = { kind = "boss" },
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x02] = tiles({ 0, 1 }, { 1, 1 }, { 2, 1 }) },
        field = fieldsOf { ["4,0"] = BOSS_SIDE,
                           ["2,0"] = { ["0,0"] = 2, ["1,0"] = 1, ["2,0"] = 0, ["3,0"] = 1,
                                       ["4,0"] = 2, ["0,1"] = 3, ["1,1"] = 2, ["2,1"] = 1 } },
        obstacles = { { x = 2, y = 0, hp = 10 } },
    }
    -- each judged plan's wall striker (the one blue it stages with an act's wear): every
    -- plan here strikes the wall with one unit or the other
    local worn = {}
    o.enemyPhase = function(plan)
        for _, b in ipairs(plan.blues) do
            if b.wearSlot or b.wear then worn[tostring(b.wearSlot) .. ":" .. tostring(b.wear)] = true end
        end
        return {}
    end
    local sight = sightOf(o)
    sight.strikeWall = function() return { dealt = 10, wear = 2, wearSlot = 1, wearAt = { [0] = 2 } } end
    Planner.plan(B, boardOf(A, C, E), sight, style("careful"))
    local seen = {}
    for k in pairs(worn) do seen[#seen + 1] = k end
    worn = table.concat(seen, ",")
    check(worn, "1:2", "wall: the striker's weapon is staged less the uses the strike spends")

    -- PR #645 re-review (5): a second striker on a wall spends what the HP the first leaves
    -- allows. The forecast (at the wall's own 10 HP) is two blows of 4, a use each; the first
    -- striker spends 2 and leaves 2 HP, so the second's first blow breaks it: 1 use.
    local pairsSeen = {}
    o.enemyPhase = function(plan)
        local uses = {}
        for _, b in ipairs(plan.blues) do
            if b.wear then uses[#uses + 1] = b.wear end
        end
        table.sort(uses)
        if #uses == 2 then pairsSeen[table.concat(uses, ",")] = true end
        return {}
    end
    sight = sightOf(o)
    sight.strikeWall = function()
        return { dealt = 8, wear = 2, wearSlot = 0, wearAt = { [0] = 1, [4] = 1 } }
    end
    Planner.plan(B, boardOf(A, C, E), sight, style("careful"))
    local seenPairs = {}
    for k in pairs(pairsSeen) do seenPairs[#seenPairs + 1] = k end
    table.sort(seenPairs)
    check(table.concat(seenPairs, " "), "1,2",
          "wall: the second striker's blow after the wall breaks is never thrown")
end

-- #655: a wall costs what the strikers at it need to break it. The boss E at (4,0) is A's
-- goal; the wall at (2,0) has the boss's side behind it. Each blue's blow on the wall is the
-- game's forecast (sight.strikeWall), here by unit; MOV 5, so a field step is 0.2 turns.
local WALL_WAY = { ["0,0"] = 2, ["1,0"] = 1, ["2,0"] = 0, ["3,0"] = 1, ["4,0"] = 2, ["0,1"] = 3,
                   ["1,1"] = 2, ["2,1"] = 1, ["3,1"] = 2 }
-- the boss's field with a long walk round to A's side: 20 steps from (0,0), (0,1) the way round
WALL_WAY["2,5"] = 30   -- far from the wall: 6 turns at MOV 5
local LONG_WAY = { ["4,0"] = 0, ["3,0"] = 1, ["0,0"] = 20, ["0,1"] = 19, ["1,0"] = 21,
                   ["1,1"] = 20, ["2,1"] = 21 }
local function wallSight(goalField, hp, blows, reach)
    local s = sightOf {
        objective = { kind = "boss" }, reach = reach or {},
        field = fieldsOf { ["4,0"] = goalField, ["2,0"] = WALL_WAY },
        obstacles = { { x = 2, y = 0, hp = hp } },
    }
    s.strikeWall = function(u) return { dealt = blows[u.id] or 0 } end
    return s
end
local function near(got, want) return got ~= nil and math.abs(got - want) < 1e-9 end

-- test_a_wall_costs_the_turns_its_strikers_need: A, cut off, strikes 5 a turn on its own: a
-- 20-HP wall falls on turn 4, so the boss is 4 + 0.4 turns away (the walk alone said 0.8); at
-- 10 HP on turn 2; with C beside the wall striking 20, on turn 1. Fails on the walk-only cost.
do
    local A = blue(0x01, 0, 0, 0)
    local C = blue(0x02, 1, 2, 1)
    local E = red(0x81, 4, 0, { isBoss = true, minRange = false })
    local goal = { x = 4, y = 0 }
    local function turns(hp, units, blows)
        local _, ctx = B.candidates(boardOf(table.unpack(units)),
                                    wallSight(BOSS_SIDE, hp, blows), style("careful"))
        return ctx.turnsTo(A, goal)
    end
    check(near(turns(20, { A, E }, { [0x01] = 5 }), 4.4), true, "wall cost: a lone 5-damage striker, 20 HP")
    check(near(turns(10, { A, E }, { [0x01] = 5 }), 2.4), true, "wall cost: falls with the wall's HP")
    check(near(turns(20, { A, C, E }, { [0x01] = 5, [0x02] = 20 }), 1.4), true,
          "wall cost: falls with a striker in reach")
    check(turns(20, { A, E }, {}), nil, "wall cost: a wall no one can hurt is no way")
    -- C two steps off at (3,1), on no tile its weapon reaches the wall from: a striker only
    -- once a plan stands it there (Nicolas, 2026-11-18); counted from its walk, the wall fell
    -- on turn 1 and no strike was ever worth making (vanilla Ch8's)
    check(near(turns(20, { A, blue(0x02, 1, 3, 1), E }, { [0x01] = 5, [0x02] = 20 }), 4.4), true,
          "wall cost: a striker that could come but stands off is not counted")
end

-- test_the_march_takes_the_wall_the_army_breaks_soon: the boss also has a long walk round (20
-- steps, 4 turns). A's own 2-damage blow on the 20-HP wall needs 10 turns, so A walks round
-- (its march to (0,1)); with C beside the wall striking 20 it falls this turn, the way through
-- is 1.4 turns, and A's march steps to the wall's side (1,0): turnsFor and the march read one
-- way. The second half fails on the walk-only cost (the walk round always won); the first is
-- the guard that a weak striker does not take the wall.
do
    local A = blue(0x01, 0, 0, 0)
    local C = blue(0x02, 1, 2, 1)
    local E = red(0x81, 4, 0, { isBoss = true, minRange = false })
    local goal = { x = 4, y = 0 }
    local reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }, { 0, 1 }), [0x02] = tiles({ 2, 1 }) }
    local function read(units, blows)
        local cands, ctx = B.candidates(boardOf(table.unpack(units)),
                                        wallSight(LONG_WAY, 20, blows, reach), style("careful"))
        local marchTo
        for _, c in ipairs(cands) do
            for _, a in ipairs(c.unit.id == 0x01 and c.acts or {}) do
                if a.why == "march" and not marchTo then marchTo = at(a) end
            end
        end
        return ctx.turnsTo(A, goal), marchTo
    end
    local t, m = read({ A, E }, { [0x01] = 2 })
    check(near(t, 4), true, "wall way: a lone weak striker's way is the walk round")
    check(m, "0,1", "wall way: so it marches round")
    t, m = read({ A, C, E }, { [0x01] = 2, [0x02] = 20 })
    check(near(t, 1.4), true, "wall way: a strong striker beside it makes the wall the way")
    check(m, "1,0", "wall way: and the march steps to the wall")
end

-- test_a_strike_is_offered_to_a_unit_whose_way_it_is_not: C stands on the boss's side (its own
-- way is the walk); the wall is on A's way. C, whose blow hurts the wall, is offered the strike,
-- and the board it leaves (the wall broken: the planner's st.walls) takes turns off A's way.
-- Fails where only the unit whose own march goal is the wall was offered one.
do
    local A = blue(0x01, 0, 0, 0)
    local C = blue(0x02, 1, 3, 0)
    local E = red(0x81, 4, 0, { isBoss = true, minRange = false })
    local reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x02] = tiles({ 3, 0 }) }
    local cands, ctx = B.candidates(boardOf(A, C, E),
                                    wallSight(BOSS_SIDE, 20, { [0x02] = 20 }, reach), style("careful"))
    local struck
    for _, c in ipairs(cands) do
        for _, a in ipairs(c.unit.id == 0x02 and c.acts or {}) do
            if a.obstacle then struck = a.obstacle.x .. "," .. a.obstacle.y end
        end
    end
    check(struck, "2,0", "wall strike: offered to a unit whose own way it is not")
    local before = ctx.turnsTo(A, { x = 4, y = 0 })
    local after = ctx.turnsOn and ctx.turnsOn({ ["2,0"] = 0 })(A, { x = 4, y = 0 })
    check(near(before, 1.4) and near(after, 0.8), true,
          "wall strike: the wall it breaks takes turns off the goal-holder's way")
end

-- test_a_strike_is_offered_on_a_wall_off_the_cheapest_way (#655): A's way to the boss is the
-- walk round (4 turns): its own 2 a blow on the 20-HP wall needs 10 turns, and C (20 a blow),
-- at (3,1), stands on no tile it strikes the wall from. Open, the wall would be 0.8 turns, so C,
-- who can reach (2,1) beside it, is offered the strike, and the board it leaves takes A's way
-- to 0.8. Fails where a strike was offered only on the cheapest way, priced with no striker at
-- the wall: no one ever came (vanilla Ch8's wall, the thief's door round the cheaper way).
do
    local A = blue(0x01, 0, 0, 0)
    local C = blue(0x02, 1, 3, 1)
    local E = red(0x81, 4, 0, { isBoss = true, minRange = false })
    local reach = { [0x01] = tiles({ 0, 0 }, { 0, 1 }), [0x02] = tiles({ 3, 1 }, { 2, 1 }) }
    -- C on the boss's side, two steps from it: its own way is the walk, never the wall
    local field = { ["3,1"] = 2 }
    for k, v in pairs(LONG_WAY) do field[k] = field[k] or v end
    local cands, ctx = B.candidates(boardOf(A, C, E),
                                    wallSight(field, 20, { [0x01] = 2, [0x02] = 20 }, reach),
                                    style("careful"))
    local struck
    for _, c in ipairs(cands) do
        for _, a in ipairs(c.unit.id == 0x02 and c.acts or {}) do
            if a.obstacle then struck = a.move.x .. "," .. a.move.y .. ">" .. a.obstacle.x .. "," .. a.obstacle.y end
        end
    end
    check(struck, "2,1>2,0", "wall strike: offered on a wall whose fall would shorten a way")
    local now = ctx.turnsTo(A, { x = 4, y = 0 })
    local after = ctx.turnsOn({ ["2,0"] = 0 }, { [0x02] = { x = 2, y = 1, acted = true } })(A, { x = 4, y = 0 })
    check(near(now, 4) and near(after, 0.8), true, "wall strike: and the board it leaves takes the wall")
end

-- test_a_wall_falls_with_the_strikers_where_the_plan_puts_them (#655, Nicolas 2026-11-18): C
-- (20 a blow) is a striker only from where a plan stands it. Far off at (2,5), the wall falls
-- by A's own 5 a turn (turn 4: 4.4 turns to the boss); a plan that brings C beside it (acted:
-- it strikes next turn) breaks it on turn 2 (2.4). C beside the wall makes it turn 1 (1.4),
-- and a plan that leads C away puts A back on its own (4.4). Fails where the strikers were
-- counted from the board as it stands.
do
    local A = blue(0x01, 0, 0, 0)
    local E = red(0x81, 4, 0, { isBoss = true, minRange = false })
    local goal = { x = 4, y = 0 }
    local function read(cx, cy, pos)
        local C = blue(0x02, 1, cx, cy)
        local _, ctx = B.candidates(boardOf(A, C, E),
                                    wallSight(BOSS_SIDE, 20, { [0x01] = 5, [0x02] = 20 }), style("careful"))
        return ctx.turnsTo(A, goal), ctx.turnsOn and ctx.turnsOn(nil, pos)(A, goal)
    end
    local now, brought = read(2, 5, { [0x02] = { x = 2, y = 1, acted = true } })
    check(near(now, 4.4) and near(brought, 2.4), true,
          "wall plan: a striker the plan brings into reach breaks it sooner")
    local stays, led = read(2, 1, { [0x02] = { x = 2, y = 5, acted = true } })
    check(near(stays, 1.4) and near(led, 4.4), true,
          "wall plan: a striker the plan leads away costs the way its blows")
    -- the judged enemy phase kills C there (positions' alive 0): its blows count for nothing
    -- (#659 review: a plan leaving a striker to die at the wall read the wall as falling)
    local _, dies = read(2, 5, { [0x02] = { x = 2, y = 1, acted = true, alive = 0 } })
    check(near(dies, 4.4), true, "wall plan: a striker the plan leaves to die at the wall does not break it")
end

-- #659 review. (1) A two-tile wall's tiles share their trap's HP (sight.obstacles' `trap`): a
-- strike on the trap's tile is read through the other tile too, and its strike act carries
-- that key (`at`) for the planner's st.walls. (2) A striker whose first side tile's forecast
-- takes nothing is tried from the next: here C's blow from (3,0) is 0 and from (1,0) is 20.
-- (3) With no forecast of a blow, no strike is offered to a unit whose own way it is not.
-- (4) A read on a plan's board that errors leaves no plan state behind.
do
    local A = blue(0x01, 0, 0, 0)
    local E = red(0x81, 4, 0, { isBoss = true, minRange = false })
    local goal = { x = 4, y = 0 }
    -- (1): the way's tile (2,0) belongs to the trap at (2,9)
    local C = blue(0x02, 1, 3, 0)
    local reach = { [0x01] = tiles({ 0, 0 }), [0x02] = tiles({ 3, 0 }) }
    local s = wallSight(BOSS_SIDE, 20, { [0x01] = 5, [0x02] = 20 }, reach)
    s.obstacles = function() return { { x = 2, y = 0, hp = 20, trap = "2,9" } } end
    local cands, ctx = B.candidates(boardOf(A, C, E), s, style("careful"))
    check(near(ctx.turnsOn({ ["2,9"] = 0 })(A, goal), 0.8), true,
          "two-tile wall: a strike on its trap's tile opens the other tile's way")
    local at
    for _, c in ipairs(cands) do
        for _, a in ipairs(c.unit.id == 0x02 and c.acts or {}) do
            if a.obstacle then at = a.obstacle.at end
        end
    end
    check(at, "2,9", "two-tile wall: the strike carries its trap's key")
    -- (2)
    C = blue(0x02, 1, 2, 1)
    s = wallSight(BOSS_SIDE, 20, {})
    s.strikeWall = function(u, o, x, y)
        if u.id == 0x01 then return { dealt = 5 } end
        return { dealt = (x == 3 and y == 0) and 0 or 20 }
    end
    _, ctx = B.candidates(boardOf(A, C, E), s, style("careful"))
    check(near(ctx.turnsTo(A, goal), 1.4), true,
          "wall blow: a side whose forecast takes nothing is not the striker's last try")
    -- and no strike is offered from such a side: C, reaching (3,0) and (1,0), strikes from (1,0)
    C = blue(0x02, 1, 3, 0)
    local s2 = wallSight(BOSS_SIDE, 20, {}, { [0x01] = tiles({ 0, 0 }), [0x02] = tiles({ 3, 0 }, { 1, 0 }) })
    s2.strikeWall = s.strikeWall
    cands = B.candidates(boardOf(A, C, E), s2, style("careful"))
    local from
    for _, c in ipairs(cands) do
        for _, a in ipairs(c.unit.id == 0x02 and c.acts or {}) do
            if a.obstacle then from = from or (a.move.x .. "," .. a.move.y) end
        end
    end
    check(from, "1,0", "wall strike: never from a tile whose forecast takes nothing")
    -- (3)
    C = blue(0x02, 1, 3, 1)
    local field = { ["3,1"] = 2 }
    for k, v in pairs(LONG_WAY) do field[k] = field[k] or v end
    s = wallSight(field, 20, {}, { [0x01] = tiles({ 0, 0 }, { 0, 1 }), [0x02] = tiles({ 3, 1 }, { 2, 1 }) })
    s.strikeWall = nil
    cands = B.candidates(boardOf(A, C, E), s, style("careful"))
    local offered = false
    for _, c in ipairs(cands) do
        for _, a in ipairs(c.unit.id == 0x02 and c.acts or {}) do
            if a.obstacle then offered = true end
        end
    end
    check(offered, false, "wall strike: none offered off the striker's own way with no forecast")
    -- (4)
    C = blue(0x02, 1, 2, 5)
    s = wallSight(BOSS_SIDE, 20, { [0x01] = 5, [0x02] = 20 })
    local turnsTo = s.turnsTo
    _, ctx = B.candidates(boardOf(A, C, E), s, style("careful"))
    s.turnsTo = function() error("boom") end
    local ok = pcall(ctx.turnsOn({ ["2,0"] = 3 }), A, { x = 4, y = 1 })
    s.turnsTo = turnsTo
    check(not ok and ctx.wallSig == nil and ctx.wallHp == nil, true,
          "plan read: an error leaves no plan's walls behind")
end

-- test_a_wall_strike_earns_only_the_turns_it_takes_off (#655, Nicolas 2026-11-18: no flat
-- `breach` for a wall): C's 1-damage blow on a 50-HP wall that only C can hurt takes about a
-- turn off A's 50-turn way, worth next to nothing, so the best plan with C's strike is judged
-- no better than the best without it beyond that (main paid every strike 25 flat).
do
    local A = blue(0x01, 0, 0, 0)
    local C = blue(0x02, 1, 3, 1)
    local E = red(0x81, 4, 0, { isBoss = true, minRange = false })
    local reach = { [0x01] = tiles({ 0, 0 }), [0x02] = tiles({ 3, 1 }, { 3, 0 }) }
    local sight = wallSight(BOSS_SIDE, 50, { [0x02] = 1 }, reach)
    local _, plan = Planner.plan(B, boardOf(A, C, E), sight, style("careful"))
    local with, without
    for _, c in ipairs(plan and plan.considered or {}) do
        local struck = false
        for _, k in ipairs(c.acts or {}) do
            if k:match("^2>attack") then struck = true end
        end
        local v = c.rank and c.rank.value
        if v and struck and (not with or v > with) then with = v end
        if v and not struck and (not without or v > without) then without = v end
    end
    check(with ~= nil and without ~= nil and with - without < 1, true,
          "wall strike: no flat worth, only the turns it takes off a way")
end

-- test_a_unit_waiting_on_the_wall_is_not_stuck (#655): A, sent to the chest at (4,0), waits
-- beside the wall at (2,0) with no tile nearer. Its own 5-damage blow on the 20-HP wall
-- shortens its way this turn, so the goal is not recorded as blocked (main recorded it either
-- way: vanilla Ch8's thief waiting at the wall lost its chests to this rule). A unit that cannot hurt
-- the wall, with the one striker (C, 20 a blow) beside it already acted, has no strike to wait
-- on this turn: its goal is recorded, to be tested again next turn, when C can strike.
do
    local A = blue(0x01, 0, 1, 0)
    local E = red(0x81, 0, 9, { minRange = false })
    local function blocked(blows, c)
        local s = sightOf {
            reach = { [0x01] = tiles({ 1, 0 }, { 0, 0 }), [0x02] = tiles({ c.x, c.y }) },
            field = fieldsOf { ["4,0"] = BOSS_SIDE, ["2,0"] = WALL_WAY },
            obstacles = { { x = 2, y = 0, hp = 20 } },
            explorable = { { x = 4, y = 0, kind = "chest" } },
            canExplore = { [0x01] = { ["4,0"] = "chest" } },
        }
        s.strikeWall = function(u) return { dealt = blows[u.id] or 0 } end
        local _, ctx = B.candidates(boardOf(A, c, E), s, style("careful"),
                                    { sent = { { id = 0x01, x = 4, y = 0 } } })
        return ctx.exploreGoal[0x01] ~= nil, ctx.stuck["1>4,0"] ~= nil
    end
    local sent, rec = blocked({ [0x01] = 5 }, blue(0x02, 1, 2, 5))
    check(sent and not rec, true, "stuck rule: its own blow on the wall keeps the goal open")
    sent, rec = blocked({ [0x02] = 20 }, blue(0x02, 1, 2, 1, { acted = true }))
    check(sent and rec, true, "stuck rule: with no strike to make this turn, the goal is recorded")
end

-- test_the_assault_seats_every_striker: the boss E sits in the corner (0,0); (1,0) is the one
-- tile beside it both A and C reach. R, the heavier, strikes from 1 or 2 away and also
-- reaches (1,1); M strikes only from beside it. The assault seats R on (1,1) and M on (1,0):
-- both strike. Offering each unit two tiles and seating the heaviest first on its first
-- left M nothing (Manchego Stars ch03: three of six strikers dropped).
do
    local R = blue(0x01, 0, 3, 0, { maxRange = 2 })
    local M = blue(0x02, 1, 3, 1)
    local E = red(0x81, 0, 0, { isBoss = true, hp = 30, minRange = false })
    local hit = function(dmg) return fc { hit = 100, dmg = dmg, hits = 1 } end
    local o = {
        objective = { kind = "boss" },
        reach = { [0x01] = tiles({ 3, 0 }, { 1, 0 }, { 1, 1 }), [0x02] = tiles({ 3, 1 }, { 1, 0 }) },
        fc = { [0x01] = { [0x81] = { ["1,0"] = hit(10), ["1,1"] = hit(10) } },
               [0x02] = { [0x81] = { ["1,0"] = hit(5) } } },
    }
    local _, plan = Planner.plan(B, boardOf(R, M, E), sightOf(o), style("careful"))
    local seated
    for _, c in ipairs(plan and plan.considered or {}) do
        if c.kind == "assault" then seated = table.concat(c.acts, " ") end
    end
    check(seated and seated:find("1>attack@1,1") ~= nil and seated:find("2>attack@1,0") ~= nil, true,
          "assault: R strikes from 2 away, leaving M the tile beside the boss")
end

-- test_a_plan_moves_an_ally_off_the_tile_another_needs: B stands on (1,0), the one tile that
-- brings A nearer the enemy; B can step on to (2,0). The plan moves B first, then A onto B's
-- old tile -- never A first, which the game would refuse (Manchego Stars ch03: Braulo queued behind
-- the light hitters on the corner's safe tiles, and never reached the boss).
do
    local A = blue(0x01, 0, 0, 0)
    local F = blue(0x02, 1, 1, 0)
    local E = red(0x81, 6, 0, { minRange = false })
    local far = { ["0,0"] = 6, ["1,0"] = 5, ["2,0"] = 4, ["3,0"] = 3 }
    local o = { reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x02] = tiles({ 1, 0 }, { 2, 0 }) },
                field = fieldsOf { ["6,0"] = far } }
    local _, plan = Planner.plan(B, boardOf(A, F, E), sightOf(o), style("careful"))
    local order = {}
    for _, a in ipairs(plan and plan.acts or {}) do order[#order + 1] = a.unitId .. "@" .. at(a) end
    check(table.concat(order, " "), "2@2,0 1@1,0", "vacate: B steps on, then A takes its tile")
end

-- test_a_unit_still_advances_when_the_ally_ahead_stays: F holds (2,0), A's nearest tile to
-- the goal, and has nowhere else to go; A's safest holds are its own tile and two behind it.
-- A still advances to the free (1,0): a tile an ally
-- may vacate is an extra way forward, never the only one (vanilla Ch3: Eirika held at (13,8)
-- behind the army for five turns, the throne open).
do
    local A = blue(0x01, 0, 0, 0)
    local F = blue(0x02, 1, 2, 0)
    local E = red(0x81, 6, 0, { minRange = false })
    local o = { reach = { [0x01] = tiles({ 0, 0 }, { 0, 1 }, { 0, 2 }, { 1, 0 }, { 2, 0 }),
                          [0x02] = tiles({ 2, 0 }) },
                field = fieldsOf { ["6,0"] = { ["0,0"] = 6, ["0,1"] = 7, ["0,2"] = 8, ["1,0"] = 5,
                                               ["2,0"] = 4 } } }
    local _, plan = Planner.plan(B, boardOf(A, F, E), sightOf(o), style("careful"))
    local where = {}
    for _, a in ipairs(plan and plan.acts or {}) do where[a.unitId] = at(a) end
    check(where[0x01], "1,0", "vacate: with the ally ahead staying, A takes the free tile")
end

-- test_a_unit_whose_safest_tile_is_taken_holds_on_the_next: X reaches (0,0) for 25 of A's 20;
-- (0,1) and (0,2) are safe, (0,1) the safest by board order. C marches onto (0,1). A must
-- still end safe, on (0,2) -- with one hold it was left the exposed (0,0) (Manchego Stars ch03:
-- Braulo beside the Mogall at 81% to die while a safe tile stood free).
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local C = blue(0x02, 1, 1, 1, { minRange = false })
    local X = red(0x81, 3, 0)
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 0, 1 }, { 0, 2 }), [0x02] = tiles({ 1, 1 }, { 0, 1 }),
                  [0x81] = tiles({ 1, 0 }) },
        field = function() return { [0] = { [0] = 5 }, [1] = { [0] = 5, [1] = 9 }, [2] = { [0] = 5 } } end,
        danger = { ["0,0"] = 1 },
        fc = { [0x01] = { [0x81] = { ["0,0"] = fc { takenHit = 100, takenDmg = 25, takenHits = 1 } } } },
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.x == 0 and b.y == 0 then
                    return { { enemy = 0x81, target = b.unit.id, takenHit = 100, takenDmg = 25,
                               takenHits = 1, takenCrit = 0 } }
                end
            end
            return {}
        end,
    }
    local _, plan = Planner.plan(B, boardOf(A, C, X), sightOf(o), style("careful"))
    local where = {}
    for _, a in ipairs(plan and plan.acts or {}) do where[a.unitId] = at(a) end
    check(where[0x02], "0,1", "holds: C takes the ground it marches for")
    check(where[0x01], "0,2", "holds: A holds on its next safe tile, not the exposed one")
end

-- test_a_unit_on_the_tile_a_teammate_needs_is_offered_a_free_one: the door at (2,0) opens
-- only from (1,0), where J, who holds no key, stands. J's other tiles are C's and D's, whose
-- own only other tile is J's: a loop no order of moves breaks, and J's free tile (0,2) comes
-- after its holds. J is offered that free tile because K's Door asks J's tile, so the plan
-- moves J off and K opens the door. Vanilla Ch8 (lap3e, seed 4006): Joshua held the one tile
-- beside the door for 17 turns, Garcia and Ross on the two tiles he was offered.
do
    local K = blue(0x01, 0, 0, 1)
    local J = blue(0x02, 1, 1, 0)
    local C = blue(0x03, 2, 0, 0)
    local D = blue(0x04, 3, 1, 1)
    local E = red(0x81, 4, 0, { isBoss = true, minRange = false })
    local o = {
        objective = { kind = "boss" },
        reach = { [0x01] = tiles({ 0, 1 }, { 1, 0 }),
                  [0x02] = tiles({ 1, 0 }, { 0, 0 }, { 1, 1 }, { 0, 2 }),
                  [0x03] = tiles({ 0, 0 }, { 1, 0 }), [0x04] = tiles({ 1, 1 }, { 1, 0 }) },
        field = fieldsOf { ["4,0"] = BOSS_SIDE,
                           ["2,0"] = { ["0,0"] = 2, ["1,0"] = 1, ["2,0"] = 0, ["3,0"] = 1,
                                       ["4,0"] = 2, ["0,1"] = 3, ["1,1"] = 2, ["0,2"] = 4 } },
        obstacles = {}, doors = { { x = 2, y = 0 } }, openers = { [0x01] = true },
    }
    local _, plan = Planner.plan(B, boardOf(K, J, C, D, E), sightOf(o), style("careful"))
    local order = {}
    for _, a in ipairs(plan and plan.acts or {}) do
        order[#order + 1] = a.unitId .. ">" .. a.act .. "@" .. at(a)
    end
    order = table.concat(order, " ")
    local aside, door = order:find("2>wait@0,2", 1, true), order:find("1>door@1,0", 1, true)
    check(aside ~= nil and door ~= nil and aside < door, true,
          "aside: J steps to its free tile, then K opens the door (" .. order .. ")")

    -- J's offered asides (Bot.candidates), on the same board with `edit` applied to it
    local function asidesOf(edit, st)
        local p = { reach = {}, field = o.field, objective = o.objective, obstacles = {},
                    doors = o.doors, openers = o.openers }
        for id, r in pairs(o.reach) do p.reach[id] = r end
        if edit then edit(p) end
        local cands = B.candidates(boardOf(K, J, C, D, E), sightOf(p), st or style("careful"))
        local out = {}
        for _, c in ipairs(cands) do
            for _, a in ipairs(c.unit.id == 0x02 and c.acts or {}) do
                if a.why == "aside" then out[#out + 1] = at(a) end
            end
        end
        return table.concat(out, " ")
    end
    check(asidesOf(), "0,2", "aside: J is offered its one free tile, once")
    local benched = style("careful")
    benched.bench = { J.charId }
    check(asidesOf(nil, benched), "", "aside: none for a benched unit")
    check(asidesOf(function(p) p.reach[0x02] = tiles({ 1, 0 }, { 0, 2 }, { 0, 0 }, { 1, 1 }) end),
          "", "aside: none when the free tile is already one of J's waits")
    check(asidesOf(function(p) p.reach[0x02] = tiles({ 1, 0 }, { 0, 0 }, { 1, 1 }) end), "",
          "aside: none when J has no free tile")
    check(asidesOf(function(p)
        p.reach[0x01], p.reach[0x03], p.reach[0x04] = tiles({ 0, 1 }), tiles({ 0, 0 }), tiles({ 1, 1 })
    end), "", "aside: none when no teammate's act asks for J's tile")
end

-- test_a_visited_tile_is_not_offered_again: a House (eventinfo House(0, ...), flag 0) keeps
-- its Visit for good, so the game offers it every turn. Once we have visited it, it is no one's
-- goal and no Visit is proposed there: vanilla Ch1's two houses held Seth and Eirika on them
-- for nine turns, every style stuck.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local E = red(0x81, 0, 9, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        explorable = { { x = 1, y = 0, kind = "visit" } },
        canExplore = { [0x01] = { ["1,0"] = "visit" } },
    }
    local function visits(opts)
        local n = 0
        for _, c in ipairs(B.candidates(boardOf(A, E), sightOf(o), style("careful"), opts)) do
            for _, a in ipairs(c.acts) do
                if a.act == "visit" then n = n + 1 end
            end
        end
        return n
    end
    check(visits(nil), 1, "visited: an unvisited house is offered")
    check(visits({ explored = { ["1,0"] = true } }), 0, "visited: not offered again")
end

-- test_exploring_opens_the_door_to_a_chest: the chest at (4,0) sits behind the door at (2,0),
-- so no path reaches A. A can open both, so it is sent to the chest and its first act is the
-- Door. Pairing only units the path reached left ch03's (6,12) chest, behind the door at
-- (6,10), unopened in every attempt of every style, with Trex able to open both.
do
    local A = blue(0x01, 0, 0, 0)
    local E = red(0x81, 0, 9, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        field = fieldsOf { ["4,0"] = BOSS_SIDE, ["2,0"] = FROM_WALL },
        doors = { { x = 2, y = 0 } }, obstacles = {}, openers = { [0x01] = true },
        explorable = { { x = 4, y = 0, kind = "chest" } },
        canExplore = { [0x01] = { ["4,0"] = "chest" } },
    }
    local function doorFor(cands)
        for _, c in ipairs(cands) do
            for _, a in ipairs(c.acts) do
                if a.act == "door" then return at(a) end
            end
        end
    end
    check(doorFor(B.candidates(boardOf(A, E), sightOf(o), style("careful"))), "1,0",
          "exploring: a cut-off unit that can open the way is sent, and opens the door")
    o.openers = {}
    check(doorFor(B.candidates(boardOf(A, E), sightOf(o), style("careful"))), nil,
          "exploring: nothing opens the way, nobody is sent")
end

-- test_goal_turns_go_through_the_breach: the same chest, behind the door. The game's own turns
-- (sight.turnsTo) find no way; the goals' read goes through the door A can open, so the chest
-- has a chance and the walk to it is worth something (vanilla Ch3: the throne behind walls was
-- unreachable for every unit, and the army sat for 22 turns).
do
    local A = blue(0x01, 0, 0, 0)
    local E = red(0x81, 0, 9, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        field = fieldsOf { ["4,0"] = BOSS_SIDE, ["2,0"] = FROM_WALL },
        doors = { { x = 2, y = 0 } }, obstacles = {}, openers = { [0x01] = true },
        explorable = { { x = 4, y = 0, kind = "chest" } },
        canExplore = { [0x01] = { ["4,0"] = "chest" } },
    }
    local sight = sightOf(o)
    check(sight.turnsTo(A, { x = 4, y = 0 }), nil, "breach: the game's turns find no way")
    local _, ctx = B.candidates(boardOf(A, E), sight, style("careful"))
    local t = ctx.turnsTo(A, { x = 4, y = 0 })
    check(t ~= nil and t > 0, true, "breach: the goals' turns go through the door")
end

-- The way through doors (#510, the scout lap): A at (0,0) holds a key, the boss stands at the
-- far end of the row, and `o` builds the doors between. What A does first and its turns there.
local function doorWay(goalX, o)
    local A = blue(0x01, 0, 0, 0)
    local E = red(0x81, goalX, 0, { isBoss = true, minRange = false })
    o.objective, o.reach = { kind = "boss" }, { [0x01] = tiles({ 0, 0 }, { 1, 0 }) }
    o.obstacles, o.openers = {}, { [0x01] = true }
    local a = B.decide(boardOf(A, E), sightOf(o), style("careful"))
    local _, ctx = B.candidates(boardOf(A, E), sightOf(o), style("careful"))
    return a, ctx.turnsTo(A, { x = goalX, y = 0 })
end
local function near(t, want) return t ~= nil and math.abs(t - want) < 1e-9 end

-- test_a_door_a_teammate_opens_is_a_way_for_every_unit (#510, vanilla Ch10 on Eirika's route):
-- the boss stands behind the locked door at (2,0). A holds no key and no enemy drops one; K
-- holds one. A's way runs through the door K opens, at the later of A's own walk there and
-- K's: the army walks with its opener instead of reading no way and holding while the opener
-- walks alone. With no living opener the door is no way.
do
    local A = blue(0x01, 0, 0, 0)
    local K = blue(0x02, 1, 0, 1)
    local E = red(0x81, 4, 0, { isBoss = true, minRange = false })
    local function wayOf(kFar, opener)
        local toDoor = { ["0,0"] = 2, ["1,0"] = 1, ["2,0"] = 0, ["3,0"] = 1, ["4,0"] = 2,
                         ["0,1"] = kFar }
        local o = {
            objective = { kind = "boss" },
            reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x02] = tiles({ 0, 1 }) },
            field = fieldsOf { ["4,0"] = BOSS_SIDE, ["2,0"] = toDoor },
            obstacles = {}, doors = { { x = 2, y = 0 } },
            openers = { [0x02] = opener }, locked = { [0x01] = { ["2,0"] = "door" } },
        }
        local _, ctx = B.candidates(boardOf(A, K, E), sightOf(o), style("careful"))
        return ctx.turnsTo(A, { x = 4, y = 0 }), ctx.turnsTo(K, { x = 4, y = 0 })
    end
    -- K 8 moves from the door, A 2: A arrives with K, so their turns to the boss are K's
    local a, k = wayOf(8, true)
    check(a ~= nil and near(a, k), true, "escort: the door its teammate opens is A's way, at K's turns")
    -- K 1 move from the door: A's own walk is the later, so A's turns exceed K's
    a, k = wayOf(1, true)
    check(a ~= nil and k ~= nil and a > k + 1e-9, true, "escort: A's own walk when it is the later")
    check(wayOf(8, false), nil, "escort: with no one to open it, the locked door is no way")
    -- an enemy far off drops a Door Key too (8 turns there, 8 back): the opener's way is the
    -- sooner, so A's turns are still K's (review of PR #628: the key's way was taken whenever
    -- there was one)
    local D = red(0x82, 0, 9, { minRange = false })
    local o = {
        objective = { kind = "boss" },
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x02] = tiles({ 0, 1 }) },
        field = fieldsOf { ["4,0"] = BOSS_SIDE,
                           ["2,0"] = { ["0,0"] = 2, ["1,0"] = 1, ["2,0"] = 0, ["0,1"] = 8,
                                       ["0,9"] = 40 },
                           ["0,9"] = { ["0,0"] = 40, ["0,9"] = 0 } },
        obstacles = {}, doors = { { x = 2, y = 0 } }, openers = { [0x02] = true },
        locked = { [0x01] = { ["2,0"] = "door" } }, keySources = { door = { D } },
    }
    local _, ctx = B.candidates(boardOf(A, K, E, D), sightOf(o), style("careful"))
    local ka, kk = ctx.turnsTo(A, { x = 4, y = 0 }), ctx.turnsTo(K, { x = 4, y = 0 })
    check(ka ~= nil and near(ka, kk), true,
          "escort: the opener's way when it is sooner than a key's (" .. tostring(ka) .. ")")
end

-- test_the_convoys_door_key_is_taken_when_no_one_can_open_the_door (#510, vanilla Ch10 on
-- Eirika's route: the one key holder died, the key the enemy dropped sat in the convoy, and
-- the army stalled): A holds no key, the door at (2,0) is locked to it, no fielded unit opens
-- doors, and the convoy holds a Door Key. A is offered Supply from the tile the game enables
-- it on, carrying the item; not when a teammate opens doors (the door is already its way),
-- nor with no key in the convoy.
do
    local A = blue(0x01, 0, 0, 0)
    local K = blue(0x02, 1, 0, 1)
    local E = red(0x81, 4, 0, { isBoss = true, minRange = false })
    local function supplies(o, ...)
        o.objective, o.reach = { kind = "boss" }, { [0x01] = tiles({ 0, 0 }, { 1, 0 }) }
        o.field = fieldsOf { ["4,0"] = BOSS_SIDE, ["2,0"] = FROM_WALL }
        o.obstacles, o.doors = {}, { { x = 2, y = 0 } }
        o.locked, o.supplyAt = { [0x01] = { ["2,0"] = "door" } }, { ["1,0"] = true }
        local props = B.candidates(boardOf(...), sightOf(o), style("careful"))
        for _, p in ipairs(props) do
            if p.unit.id == 0x01 then
                for _, a in ipairs(p.acts) do
                    if a.act == "supply" then return a end
                end
            end
        end
        return nil
    end
    local key = { [0x01] = { id = 0x6A, uses = 1 } }
    local a = supplies({ convoyKey = key }, A, E)
    check(a and (a.move.x .. "," .. a.move.y .. " " .. a.item .. "x" .. a.uses), "1,0 106x1",
          "supply: the convoy's Door Key, from the tile Supply is offered on")
    check(supplies({ convoyKey = key, openers = { [0x02] = true } }, A, K, E), nil,
          "supply: not while a teammate opens the door")
    check(supplies({ convoyKey = {} }, A, E), nil, "supply: not with no key in the convoy")
    -- a Take rebuilt from its key (botrun's forced act) names no item: takeItem fills it in
    local taken = B.takeItem(sightOf({ convoyKey = key }), A, { act = "supply" })
    check(taken and (taken.item .. "x" .. taken.uses), "106x1",
          "takeItem: a Take built from its key takes the convoy's key for the unit now")
    check(B.takeItem(sightOf({ convoyKey = {} }), A, { act = "supply" }), nil,
          "takeItem: no Take with no key in the convoy")
    -- the plan credits it as the act that opens the way (the breach weight), over a wait
    local o = { convoyKey = key, objective = { kind = "boss" },
                reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
                field = fieldsOf { ["4,0"] = BOSS_SIDE, ["2,0"] = FROM_WALL },
                obstacles = {}, doors = { { x = 2, y = 0 } },
                locked = { [0x01] = { ["2,0"] = "door" } }, supplyAt = { ["1,0"] = true } }
    local p, plan = Planner.plan(B, boardOf(A, E), sightOf(o), style("careful"))
    check(p and p.act, "supply", "supply: the plan takes the key rather than wait")
    -- by its worth, not by a tie: it is valued above the wait on the same tile
    local took, waited
    for _, c in ipairs(plan and plan.considered or {}) do
        local k = table.concat(c.acts, " ")
        if k == "1>supply@1,0>nil" then took = c.rank.value end
        if k == "1>wait@1,0>nil" then waited = c.rank.value end
    end
    check(took ~= nil and waited ~= nil and took > waited, true,
          "supply: valued above the wait on its tile (" .. tostring(took) .. " vs "
          .. tostring(waited) .. ")")
end

-- test_a_door_no_teammate_can_reach_is_no_way (review of PR #628): A is cut off by the wall
-- at (2,0), which is also a door locked to A; K holds a key but has no way to that door. The
-- door is no way for A, so A still strikes the wall (listing it for any key holder at all sent
-- A at a door no one could open).
do
    local A = blue(0x01, 0, 0, 0)
    local K = blue(0x02, 1, 0, 5)
    local E = red(0x81, 4, 0, { isBoss = true, minRange = false })
    local o = {
        objective = { kind = "boss" }, reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        field = fieldsOf { ["4,0"] = BOSS_SIDE, ["2,0"] = FROM_WALL },
        obstacles = { { x = 2, y = 0, hp = 20 } }, doors = { { x = 2, y = 0 } },
        openers = { [0x02] = true }, locked = { [0x01] = { ["2,0"] = "door" } },
    }
    local p = B.candidates(boardOf(A, K, E), sightOf(o), style("careful"))
    local struck = false
    for _, c in ipairs(p) do
        if c.unit.id == 0x01 then
            for _, a in ipairs(c.acts) do
                if a.act == "attack" and a.obstacle then struck = true end
            end
        end
    end
    check(struck, true, "escort: a door no teammate can reach leaves the wall A's way")
end

-- test_supply_only_for_a_door_on_the_way_and_one_take_a_plan (review of PR #628): a locked door
-- that is not on A's way (A walks to the boss) offers no Supply; and with the key's Take
-- offered to two units, no plan takes the one key twice.
do
    local A = blue(0x01, 0, 0, 0)
    local C = blue(0x02, 1, 0, 1)
    local E = red(0x81, 4, 0, { isBoss = true, minRange = false })
    local key = { [0x01] = { id = 0x6A, uses = 1 }, [0x02] = { id = 0x6A, uses = 1 } }
    local walkable = {
        objective = { kind = "boss" }, reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        field = fieldsOf { ["4,0"] = FROM_WALL, ["2,5"] = { ["0,0"] = 7, ["2,5"] = 0 } },
        obstacles = {}, doors = { { x = 2, y = 5 } }, convoyKey = key,
        locked = { [0x01] = { ["2,5"] = "door" } }, supplyAt = { ["1,0"] = true },
    }
    local offered = false
    for _, c in ipairs(B.candidates(boardOf(A, E), sightOf(walkable), style("careful"))) do
        for _, a in ipairs(c.acts) do if a.act == "supply" then offered = true end end
    end
    check(offered, false, "supply: not for a door off the unit's way")
    local o = {
        convoyKey = key, objective = { kind = "boss" },
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x02] = tiles({ 0, 1 }, { 1, 1 }) },
        field = fieldsOf { ["4,0"] = BOSS_SIDE, ["2,0"] = { ["0,0"] = 2, ["1,0"] = 1, ["2,0"] = 0,
                                                             ["0,1"] = 3, ["1,1"] = 2 } },
        obstacles = {}, doors = { { x = 2, y = 0 } },
        locked = { [0x01] = { ["2,0"] = "door" }, [0x02] = { ["2,0"] = "door" } },
        supplyAt = { ["1,0"] = true, ["1,1"] = true },
    }
    local _, plan = Planner.plan(B, boardOf(A, C, E), sightOf(o), style("careful"))
    local both, any = false, false
    for _, c in ipairs(plan and plan.considered or {}) do
        local k = table.concat(c.acts, " ")
        local _, n = k:gsub(">supply@", "")
        if n > 0 then any = true end
        if n > 1 then both = true end
    end
    check(any and not both, true, "supply: a plan takes the convoy's one key once")
end

-- test_a_gate_two_doors_deep_opens_as_one: the doors at (2,0) and (3,0) are one map change
-- (the game opens its whole rectangle, ApplyMapChangesById). (3,0) touches the boss's side but
-- A cannot walk to it; (2,0) is A's but touches only the other door. Read one tile at a time
-- neither opened the way, and vanilla Ch9 (Ephraim)'s army held in its corner for 12 attempts.
-- Turns: 2 moves to (2,0), 1 through the gate, 1 out, 1 to the boss = 5 / MOV 5.
do
    local gate = { { x = 2, y = 0 }, { x = 3, y = 0 } }
    local a, t = doorWay(5, {
        field = fieldsOf { ["5,0"] = { ["4,0"] = 1, ["5,0"] = 0 },
                           ["2,0"] = { ["0,0"] = 2, ["1,0"] = 1, ["2,0"] = 0 },
                           ["3,0"] = { ["3,0"] = 0, ["4,0"] = 1, ["5,0"] = 2 } },
        doors = gate, changes = { ["2,0"] = gate, ["3,0"] = gate },
    })
    check(a and a.act, "door", "gate: the cut-off unit opens the gate")
    check(a and a.door and (a.door.x .. "," .. a.door.y), "2,0", "gate: the door it can reach")
    check(near(t, 1.0), true, "gate: the turns run through both tiles of the gate")
end

-- test_a_way_runs_through_two_doors: doors at (2,0) and (5,0), the boss at (7,0). Only (5,0)
-- touches the boss's side, and A reaches it only through (2,0); the way is both, in order.
-- Turns: 2 to (2,0), 3 on to (5,0), 2 on to the boss = 7 / 5.
do
    local a, t = doorWay(7, {
        field = fieldsOf { ["7,0"] = { ["6,0"] = 1, ["7,0"] = 0 },
                           ["5,0"] = { ["3,0"] = 2, ["4,0"] = 1, ["5,0"] = 0, ["6,0"] = 1, ["7,0"] = 2 },
                           ["2,0"] = { ["0,0"] = 2, ["1,0"] = 1, ["2,0"] = 0, ["3,0"] = 1, ["4,0"] = 2 } },
        doors = { { x = 2, y = 0 }, { x = 5, y = 0 } },
    })
    check(a and a.door and (a.door.x .. "," .. a.door.y), "2,0", "two doors: the first one first")
    check(near(t, 1.4), true, "two doors: the turns count both")
end

-- test_a_door_onto_a_roofed_room: the door at (2,0) opens onto a room the game draws as roof
-- (no walk) until the door's change uncovers it, (3,0) and (4,0); the door at (5,0) is the far
-- wall's, the boss at (7,0) beyond (vanilla Ch14 (Eirika): (17,19), its 4x6 change, then
-- (10,14)). Turns: 2 to (2,0), 3 across the room to (5,0), 2 on = 7 / 5.
do
    local a, t = doorWay(7, {
        field = fieldsOf { ["7,0"] = { ["6,0"] = 1, ["7,0"] = 0 },
                           ["5,0"] = { ["5,0"] = 0, ["6,0"] = 1, ["7,0"] = 2 },
                           ["2,0"] = { ["0,0"] = 2, ["1,0"] = 1, ["2,0"] = 0 } },
        doors = { { x = 2, y = 0 }, { x = 5, y = 0 } },
        changes = { ["2,0"] = { { x = 2, y = 0 }, { x = 3, y = 0 }, { x = 4, y = 0 } } },
    })
    check(a and a.door and (a.door.x .. "," .. a.door.y), "2,0", "roof: the room's door first")
    check(near(t, 1.4), true, "roof: the turns cross the room the door uncovers")
end

-- test_an_empty_change_still_opens_the_door: a change with no tile to walk (sight.mapChange
-- returns none) still leaves the door's own tile open; read as "opens nothing", the door was
-- no way at all (#612 review).
do
    local a, t = doorWay(4, {
        field = fieldsOf { ["4,0"] = BOSS_SIDE, ["2,0"] = FROM_WALL },
        doors = { { x = 2, y = 0 } }, changes = { ["2,0"] = {} },
    })
    check(a and a.door and (a.door.x .. "," .. a.door.y), "2,0", "empty change: the door opens")
    check(near(t, 0.8), true, "empty change: the way runs through the door's own tile")
end

-- test_the_crossing_is_walked_round_what_the_change_leaves_shut: the door at (2,0) opens
-- (2,1) (3,1) (4,1) (4,0) but not (3,0), so its far side (4,0) is four steps on, not two as
-- the crow flies (#612 review). Turns: 2 to the door, 4 across, 1 off, 1 on = 8 / 5.
do
    local _, t = doorWay(6, {
        field = fieldsOf { ["6,0"] = { ["5,0"] = 1, ["6,0"] = 0 },
                           ["2,0"] = { ["0,0"] = 2, ["1,0"] = 1, ["2,0"] = 0 } },
        doors = { { x = 2, y = 0 } },
        changes = { ["2,0"] = { { x = 2, y = 0 }, { x = 2, y = 1 }, { x = 3, y = 1 },
                                { x = 4, y = 1 }, { x = 4, y = 0 } } },
    })
    check(near(t, 1.6), true, "crossing: the steps go round the shut tile")
end

-- test_a_way_cut_short_by_its_own_question_is_not_kept: a row of rooms, A at (0,0): door W
-- (2,0), Z (4,0), X (6,0), then the boss's room (7,0)-(8,0), whose far door Y (9,0) leads on.
-- Asking for the boss asks X's way, which asks Y's (Y touches X's ground), which asks X's again
-- while X is still being worked out: Y reads "no way" then. Kept, that answer said Y was cut
-- off for the rest of the decision, though A reaches it by W, Z and X (#612 review).
do
    local A = blue(0x01, 0, 0, 0)
    local E = red(0x81, 8, 0, { isBoss = true, minRange = false })
    local o = {
        objective = { kind = "boss" }, reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        obstacles = {}, openers = { [0x01] = true },
        field = fieldsOf { ["8,0"] = { ["7,0"] = 1, ["8,0"] = 0 },
                           ["6,0"] = { ["5,0"] = 1, ["6,0"] = 0, ["7,0"] = 1, ["8,0"] = 2 },
                           ["9,0"] = { ["7,0"] = 2, ["8,0"] = 1, ["9,0"] = 0, ["10,0"] = 1 },
                           ["4,0"] = { ["3,0"] = 1, ["4,0"] = 0, ["5,0"] = 1 },
                           ["2,0"] = { ["0,0"] = 2, ["1,0"] = 1, ["2,0"] = 0, ["3,0"] = 1 } },
        doors = { { x = 6, y = 0 }, { x = 9, y = 0 }, { x = 4, y = 0 }, { x = 2, y = 0 } },
    }
    -- asked first: the decision's own questions (the march on the boss) forgotten
    local _, fresh = B.candidates(boardOf(A, E), sightOf(o), style("careful"))
    fresh.breaches, fresh.keyTurns, fresh.ways = {}, {}, {}
    local want = fresh.turnsTo(A, { x = 9, y = 0 })
    check(want ~= nil, true, "cut: asked first, Y has a way")
    local _, ctx = B.candidates(boardOf(A, E), sightOf(o), style("careful"))
    check(ctx.turnsTo(A, { x = 8, y = 0 }) ~= nil, true, "cut: the boss has a way")
    check(ctx.turnsTo(A, { x = 9, y = 0 }), want, "cut: Y's way, asked after, is the same")
end

-- test_a_read_that_hits_a_cut_answer_is_cut_too: A at (0,0) walks to door W; W opens onto
-- Z's ground, Z onto X's, X onto the boss's. Y and X open onto each other's ground; V opens
-- onto X's, and only Y onto V's. Asking for the boss works out X, which asks Y (cut short:
-- X is open, so "no way"), then V, whose one way is Y: it finds Y's cut answer in the memo.
-- Read as a plain "no way" and kept, V was cut off for the rest of the decision, though A
-- reaches it by W, Z, X and Y (#612 re-review). The fields are drawn as the test needs them:
-- a door is beside another's ground where one of its sides is in that field.
do
    local A = blue(0x01, 0, 0, 0)
    local E = red(0x81, 8, 0, { isBoss = true, minRange = false })
    local o = {
        objective = { kind = "boss" }, reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        obstacles = {}, openers = { [0x01] = true },
        field = fieldsOf { ["8,0"] = { ["7,0"] = 1, ["8,0"] = 0 },
                           ["6,0"] = { ["6,0"] = 0, ["5,0"] = 1, ["7,0"] = 1, ["6,1"] = 1,
                                       ["9,5"] = 1, ["9,1"] = 1 },
                           ["9,2"] = { ["9,2"] = 0, ["6,1"] = 1 },
                           ["9,4"] = { ["9,4"] = 0, ["9,3"] = 1 },
                           ["4,0"] = { ["3,0"] = 1, ["4,0"] = 0, ["5,0"] = 1 },
                           ["2,0"] = { ["0,0"] = 2, ["1,0"] = 1, ["2,0"] = 0, ["3,0"] = 1 } },
        doors = { { x = 6, y = 0 }, { x = 9, y = 2 }, { x = 9, y = 4 }, { x = 4, y = 0 },
                  { x = 2, y = 0 } },
    }
    -- asked first: the decision's own questions (the march on the boss) forgotten
    local _, fresh = B.candidates(boardOf(A, E), sightOf(o), style("careful"))
    fresh.breaches, fresh.keyTurns, fresh.ways = {}, {}, {}
    local want = fresh.turnsTo(A, { x = 9, y = 4 })
    check(want ~= nil, true, "cut hit: asked first, V has a way")
    local _, ctx = B.candidates(boardOf(A, E), sightOf(o), style("careful"))
    check(ctx.turnsTo(A, { x = 8, y = 0 }) ~= nil, true, "cut hit: the boss has a way")
    check(ctx.turnsTo(A, { x = 9, y = 4 }), want, "cut hit: V's way, asked after, is the same")
end

-- test_a_row_of_doors_is_read_in_few_steps: eight doors in a row, the boss beyond the last,
-- the doors listed far first; each door touches the next one's room and the last one's. Asked
-- per door by recursion, each way asked the next one's, which asked back: the reads doubled
-- with each door, and one turn of vanilla Ch14 (Eirika) took 14 minutes (#612 review). The
-- game's turns are read about once a door.
do
    local N = 8
    local A = blue(0x01, 0, 0, 0)
    local E = red(0x81, 2 * N + 1, 0, { isBoss = true, minRange = false })
    local fields, doors = { [(2 * N + 1) .. ",0"] = { [(2 * N + 1) .. ",0"] = 0 } }, {}
    for i = N, 1, -1 do
        local x = 2 * i
        fields[x .. ",0"] = { [(x - 1) .. ",0"] = 1, [x .. ",0"] = 0, [(x + 1) .. ",0"] = 1 }
        doors[#doors + 1] = { x = x, y = 0 }
    end
    fields["2,0"]["0,0"] = 2
    local sight = sightOf {
        objective = { kind = "boss" }, reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        obstacles = {}, openers = { [0x01] = true }, field = fieldsOf(fields), doors = doors,
    }
    local calls, read = 0, sight.turnsTo
    sight.turnsTo = function(...) calls = calls + 1 return read(...) end
    local _, ctx = B.candidates(boardOf(A, E), sight, style("careful"))
    check(near(ctx.turnsTo(A, { x = 2 * N + 1, y = 0 }), (2 + 2 * (N - 1) + 1) / 5), true,
          "row: the way runs through all eight doors")
    check(calls <= 4 * N, true, "row: the game's turns read " .. calls .. " times")
end

-- test_goal_turns_go_through_the_keys_enemies_drop: the chest at (4,0) sits in a room behind
-- the door at (2,0), A holds no key, and both keys are drops: C, in the room at (3,0), drops a
-- Chest Key, D, outside at (1,1), a Door Key. The way runs A -> D (0.4), D -> the door (0.4),
-- one step in (0.2), the chest from C's tile (0.2). Vanilla Ch5x: no way through a key, so both
-- chests were no goal and every attempt missed them.
do
    local A = blue(0x01, 0, 0, 0)
    local C = red(0x81, 3, 0, { minRange = false })
    local D = red(0x82, 1, 1, { minRange = false })
    local door = { ["0,0"] = 2, ["1,0"] = 1, ["2,0"] = 0, ["3,0"] = 1, ["4,0"] = 2, ["1,1"] = 2 }
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        field = fieldsOf { ["4,0"] = BOSS_SIDE, ["2,0"] = door,
                           ["3,0"] = { ["3,0"] = 0, ["4,0"] = 1 },
                           ["1,1"] = { ["0,0"] = 2, ["1,0"] = 1, ["1,1"] = 0 } },
        doors = { { x = 2, y = 0 } }, obstacles = {},
        locked = { [0x01] = { ["4,0"] = "chest", ["2,0"] = "door" } },
        keySources = { chest = { C }, door = { D } },
    }
    local _, ctx = B.candidates(boardOf(A, C, D), sightOf(o), style("careful"))
    local t = ctx.turnsTo(A, { x = 4, y = 0 })
    check(t ~= nil and math.abs(t - 1.2) < 1e-9, true,
          "keys: the turns run through the Door Key, the door and the Chest Key")
    o.keySources = { chest = { C } }
    _, ctx = B.candidates(boardOf(A, C, D), sightOf(o), style("careful"))
    check(ctx.turnsTo(A, { x = 4, y = 0 }), nil, "keys: no Door Key to take, no way in")
    o.keySources = { door = { D } }
    _, ctx = B.candidates(boardOf(A, C, D), sightOf(o), style("careful"))
    check(ctx.turnsTo(A, { x = 4, y = 0 }), nil, "keys: no Chest Key to take, no way to the chest")
end

-- test_goal_turns_are_read_once_per_decision: the planner asks the same unit, tile and start
-- again and again (every goal, every partial plan); the game's read runs once (PR #553 review).
do
    local A = blue(0x01, 0, 0, 0)
    local E = red(0x81, 0, 9, { minRange = false })
    local sight = sightOf({ reach = { [0x01] = tiles({ 0, 0 }) } })
    local calls, read = 0, sight.turnsTo
    sight.turnsTo = function(...) calls = calls + 1 return read(...) end
    local _, ctx = B.candidates(boardOf(A, E), sight, style("careful"))
    calls = 0
    for _ = 1, 3 do ctx.turnsTo(A, { x = 4, y = 0 }, { x = 1, y = 0 }) end
    check(calls, 1, "turns: one game read for the same unit, tile and start")
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

-- test_mend_reads_the_games_max_hp: A's maxHP stat is 20 and it has 12 (8 down), but its
-- weapon adds 5 HP, so GetUnitMaxHp (sight.maxHps) is 25: 13 down, and the 10-HP Vulnerary
-- is used.
do
    local A = blue(0x01, 0, 0, 0, { hp = 12, maxhp = 20 })
    local o = { mend = { [0x01] = { slot = 1, amount = 10 } }, maxHp = { [0x01] = 25 } }
    local a = B.decide(boardOf(A), sightOf(o), style("careful"))
    check(a and a.act, "item", "mend: the cap is the game's max HP, not the raw stat")
end

-- test_planner_is_offered_a_vulnerary_below_max_hp (ADR 0408): A is 9 down with a 10-HP
-- Vulnerary. The game lets it heal at any HP below max, so the planner's menu holds the heal;
-- decide, which judges no plan, keeps to the whole amount.
do
    local A = blue(0x01, 0, 0, 0, { hp = 9, maxhp = 18 })
    local o = { mend = { [0x01] = { slot = 1, amount = 10 } } }
    local cands = B.candidates(boardOf(A), sightOf(o), style("careful"))
    local item
    for _, c in ipairs(cands) do
        for _, a in ipairs(c.acts) do
            if a.act == "item" then item = a end
        end
    end
    check(item and item.slot, 1, "offer: 9 down, the planner is offered the Vulnerary")
    check(B.decide(boardOf(A), sightOf(o), style("careful")).act, "wait",
          "offer: decide still waits for the whole amount")
    A.hp = 18
    cands = B.candidates(boardOf(A), sightOf(o), style("careful"))
    local any = false
    for _, c in ipairs(cands) do
        for _, a in ipairs(c.acts) do any = any or a.act == "item" end
    end
    check(any, false, "offer: none at full HP")
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
    -- beside it but the game's Talk command does not list it (silenced, say): no Talk
    local mute = sightOf(o)
    mute.offers = function() return {} end
    check(B.decide(boardOf(A, T, E), mute, style("careful")).act ~= "talk", true,
          "talk: only where the Talk command lists the target")
    -- out of reach: the claim marches the talker on the recruit
    o.reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) }
    a = B.decide(boardOf(A, T, E), sightOf(o), st)
    check(a and a.act, "wait", "recruit: marches when it cannot reach")
    check(at(a), "1,0", "recruit: toward the recruit")
end

-- test_recruit_claim_marches_only_where_a_player_could: the claim's talker A is out of reach of
-- its recruit. It is not marched on one the fog hides, nor on one it has no way to; it goes on
-- toward the enemy (east) instead of west to the recruit.
do
    local A = blue(0x01, 0, 4, 0, { minRange = false })
    local E = red(0x81, 9, 0, { hp = 1 })
    local function open(goal, cut)
        local f = {}
        for y = 0, 9 do
            f[y] = {}
            for x = 0, 14 do f[y][x] = math.abs(x - goal.x) + math.abs(y - goal.y) end
        end
        if cut then f[0][4] = nil end
        return f
    end
    local reach = { [0x01] = tiles({ 4, 0 }, { 3, 0 }, { 5, 0 }) }
    local st = claimed("careful", { id = "r1", kind = "recruit", unit = { 0x31 } })
    local R = red(0x82, 0, 0, { charId = 0x31, fogged = true })
    local a = B.decide(boardOf(A, R, E), sightOf({ reach = reach, field = open,
                                                   talk = { [0x01] = { [0x82] = true } } }), st)
    check(at(a) ~= "3,0", true, "recruit: no march on one the fog hides")
    local T = blue(0x30, 5, 0, 0, { faction = "green", charId = 0x31 })
    a = B.decide(boardOf(A, T, E), sightOf({ reach = reach,
        field = function(goal) return open(goal, goal.x == 0) end,
        talk = { [0x01] = { [0x30] = true } } }), st)
    check(at(a) ~= "3,0", true, "recruit: no march on one it has no way to")
end

-- test_recruit_claim_talks_where_the_game_offers_it: the claim names C. The field (one
-- class's costs) has no way from C to T, but the game offers C's Talk from (1,0) this turn. The
-- Talk is the game's own check, so C talks -- not A, whom the plain talk habit (slot order)
-- would pick; only the march, when no Talk is offered, needs a way.
do
    local A = blue(0x01, 0, 0, 1)
    local C = blue(0x02, 1, 2, 0)
    local T = blue(0x30, 5, 0, 0, { faction = "green" })
    local st = claimed("careful", { id = "r1", kind = "recruit", unit = { 0x30 } })
    st.recruits[1].by = { 0x02 }
    local a = B.decide(boardOf(A, C, T), sightOf({
        reach = { [0x01] = tiles({ 0, 1 }), [0x02] = tiles({ 2, 0 }, { 1, 0 }) },
        field = function() return { [0] = {}, [1] = { [0] = 1 } } end,
        talk = { [0x01] = { [0x30] = true }, [0x02] = { [0x30] = true } } }), st)
    check(a and a.act .. ">" .. a.unitId, "talk>2", "recruit: the claim's talker talks, way or not")
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
    -- on a stalled board the claim gives way: a careful player that has stopped making
    -- progress takes the least it must (vanilla Ch5: Natasha dead, every unit kept out of
    -- Joshua's reach between them and the boss, the same board for ten turns)
    local function tilesOf(opts)
        local out = {}
        for _, c in ipairs(B.candidates(boardOf(P, X), sightOf(o), st, opts)) do
            for _, a in ipairs(c.acts) do out[at(a)] = true end
        end
        return out
    end
    check(tostring(tilesOf(nil)["2,0"]) .. " " .. tostring(tilesOf({ stalled = true })["2,0"]),
          "nil true", "avoid: lifted on a stalled board")
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
    local E = red(0x81, 1, 0, { hp = 1, fogged = true })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 0, 1 }) },
        unseen = { { x = 0, y = 3 } },
        fc = { [0x01] = { [0x81] = { ["0,0"] = fc { hit = 100, dmg = 9, hits = 1,
                                                    killsTarget = true } } } },
    }
    local a = B.decide(boardOf(A, E), sightOf(o), style("bold"))
    check(a and a.act, "wait", "fog: no target it cannot see")
    check(at(a), "0,1", "fog: toward the unseen, not the hidden enemy")
end

-- ── The planner ─────────────────────────────────────────────────────────────────────────

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

-- The experience a fixture's attack teaches (sight's exp: the game's GetBattleUnitExpGain for
-- blows that deal nothing, deal damage, kill). A unit that cannot gain levels counts 0 for all.
local function taught(none, hit, kill) return { none = none, hit = hit, kill = kill } end
local CAPPED = taught(0, 0, 0)

-- test_planner_trains_the_unit_the_kill_teaches_more (#510 party plan, PR 3): A and C each kill
-- E for sure. A cannot gain levels (CAPPED), C learns 40 from the kill: C takes it. A's plan is
-- valued as it was before experience counted: what a unit cannot learn adds nothing.
local function sureKills(expA, expC)
    local A = blue(0x01, 0, 0, 0)
    local C = blue(0x02, 1, 2, 0)
    local E = red(0x81, 1, 0, { hp = 5 })
    return boardOf(A, C, E), sightOf {
        reach = { [0x01] = tiles({ 0, 0 }), [0x02] = tiles({ 2, 0 }) },
        fc = { [0x01] = { [0x81] = { ["0,0"] = fc { hit = 100, dmg = 9, hits = 1,
                                                    killsTarget = true, exp = expA } } },
               [0x02] = { [0x81] = { ["2,0"] = fc { hit = 100, dmg = 9, hits = 1,
                                                    killsTarget = true, exp = expC } } } },
    }
end
-- the unit whose attack the chosen plan holds (its first, by act order)
local function attacker(rec)
    local id = rec and rec.rank and (" " .. rec.rank.key):match(" (%d+)>attack@")
    return id and tonumber(id)
end
local function valueOf(rec, unitId)
    local best
    for _, c in ipairs(rec and rec.considered or {}) do
        if (" " .. c.rank.key):find(" " .. unitId .. ">attack@") then
            best = math.max(best or -math.huge, c.rank.value)
        end
    end
    return best
end
do
    local board, sight = sureKills(CAPPED, taught(1, 20, 40))
    local _, rec = Planner.plan(B, board, sight, style("careful"))
    check(attacker(rec), 2, "experience: the kill goes to the unit it teaches")
    local b1, s1 = sureKills(CAPPED, nil)
    local _, capped = Planner.plan(B, b1, s1, style("careful"))
    local b0, s0 = sureKills(nil, nil)
    local _, before = Planner.plan(B, b0, s0, style("careful"))
    check(valueOf(capped, 1) ~= nil and valueOf(capped, 1) == valueOf(before, 1), true,
          "experience: a unit that cannot gain levels adds nothing")
end

-- test_planner_lets_the_kill_fall_to_the_unit_it_teaches (#510 party plan, PR 3): E has 10 HP;
-- A's and C's blows take 5 each, for sure, so neither kills alone. A learns 40 from the kill, C
-- 10: C chips first and A finishes, the kill read at the HP C's blow leaves E. (Without the
-- experience the two orders tie, and the key puts A's blow first.)
do
    local A = blue(0x01, 0, 0, 0)
    local C = blue(0x02, 1, 2, 0)
    local E = red(0x81, 1, 0, { hp = 10 })
    local sight = sightOf {
        reach = { [0x01] = tiles({ 0, 0 }), [0x02] = tiles({ 2, 0 }) },
        fc = { [0x01] = { [0x81] = { ["0,0"] = fc { hit = 100, dmg = 5, hits = 1,
                                                    exp = taught(1, 20, 40) } } },
               [0x02] = { [0x81] = { ["2,0"] = fc { hit = 100, dmg = 5, hits = 1,
                                                    exp = taught(1, 5, 10) } } } },
    }
    local _, rec = Planner.plan(B, boardOf(A, C, E), sight, style("careful"))
    check(rec and rec.rank.key, "2>attack@2,0>129 1>attack@0,0>129",
          "experience: C's chip first, so A finishes")
end

-- test_experience_never_buys_a_plan_over_the_cap (#510 party plan, PR 3; a guard, true before
-- experience counted too): C learns 40 from the kill, but its blow can miss and E's counter
-- then kills it, past careful's 1%. A's sure kill teaches nothing, and A takes it.
do
    local A = blue(0x01, 0, 0, 0)
    local C = blue(0x02, 1, 2, 0, { hp = 10 })
    local E = red(0x81, 1, 0, { hp = 5 })
    local sight = sightOf {
        reach = { [0x01] = tiles({ 0, 0 }), [0x02] = tiles({ 2, 0 }) },
        fc = { [0x01] = { [0x81] = { ["0,0"] = fc { hit = 100, dmg = 9, hits = 1,
                                                    killsTarget = true, exp = CAPPED } } },
               [0x02] = { [0x81] = { ["2,0"] = fc { hit = 80, dmg = 9, hits = 1,
                                                    killsTarget = true, counters = true,
                                                    counterHit = 100, counterDmg = 20,
                                                    counterHits = 1, exp = taught(1, 20, 40) } } } },
    }
    local _, rec = Planner.plan(B, boardOf(A, C, E), sight, style("careful"))
    check(attacker(rec), 1, "experience: the cap holds")
end

-- test_planner_stands_where_the_counter_teaches (#510 party plan, PR 3): at (1,0) E strikes A
-- and misses, and A's counter kills it, which teaches A 30 (the game's count, the strike's
-- `taught`); at (0,1), as far from E and F, nothing reaches A. F keeps E from being the Rout's
-- last enemy. Without the experience the two tiles tie, and the key holds A at (0,1).
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local E = red(0x81, 5, 5, { hp = 10, minRange = false })
    local F = red(0x82, 9, 9, { minRange = false })
    local sight = sightOf {
        reach = { [0x01] = tiles({ 0, 1 }, { 1, 0 }) },
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.unit.id == 0x01 and b.x == 1 then
                    return { { target = 0x01, enemy = 0x81, takenHit = 0, takenDmg = 0,
                               takenHits = 1, takenCrit = 0, counterHit = 100, counterDmg = 10,
                               counterHits = 1, strikerHp = 10, targetHp = 20,
                               joint = { { p = 1, dealt = 0, back = 10 } },
                               taught = taught(1, 10, 30) } }
                end
            end
            return {}
        end,
    }
    local _, rec = Planner.plan(B, boardOf(A, E, F), sight, style("careful"))
    check(rec and rec.rank.key, "1>wait@1,0>nil", "experience: A stands where its counter learns")
end

-- test_planner_heals_with_the_healer_the_staff_teaches (#510 party plan, PR 3): A is 10 HP
-- down; H and K each reach it with a 10-HP heal. H cannot gain levels, K learns 15 from the
-- staff (the game's count, sight.staffExp): K heals.
do
    local A = blue(0x01, 0, 0, 0, { hp = 10, maxhp = 20, minRange = false, acted = true })
    local H = blue(0x02, 1, 1, 0, { minRange = false })
    local K = blue(0x03, 2, 0, 1, { minRange = false })
    local sight = sightOf {
        reach = { [0x02] = tiles({ 1, 0 }), [0x03] = tiles({ 0, 1 }) },
        staves = { [0x02] = { { slot = 0, amount = 10, exp = 0 } },
                   [0x03] = { { slot = 0, amount = 10, exp = 15 } } },
        heals = { [0x02] = { ["1,0"] = { { slot = 0, amount = 10, targets = { 0x01 }, exp = 0 } } },
                  [0x03] = { ["0,1"] = { { slot = 0, amount = 10, targets = { 0x01 }, exp = 15 } } } },
    }
    local _, rec = Planner.plan(B, boardOf(A, H, K), sight, style("careful"))
    check(rec and rec.rank.key and rec.rank.key:find("3>staff@0,1>1", 1, true) ~= nil, true,
          "experience: the healer the staff teaches heals: " .. tostring(rec and rec.rank.key))
end

-- test_both_heal_proposals_carry_the_staffs_experience (ADR 0414): the heal for a wounded ally
-- (staffHeal) and the one for an ally the plan's blows may wound (the full-HP proposal) each
-- carry the staff's count, through healWith.
do
    local function heals(hp)
        local A = blue(0x01, 0, 0, 0, { hp = hp, maxhp = 20, minRange = false })
        local H = blue(0x02, 1, 1, 0, { minRange = false })
        local o = {
            staves = { [0x02] = { { slot = 0, amount = 10, exp = 15 } } },
            heals = { [0x02] = { ["1,0"] = { { slot = 0, amount = 10, targets = { 0x01 }, exp = 15 } } } },
            reach = { [0x02] = tiles({ 1, 0 }) },
        }
        local out = {}
        for _, c in ipairs(B.candidates(boardOf(A, H), sightOf(o), style("careful"))) do
            for _, a in ipairs(c.acts) do
                if a.act == "staff" then out[#out + 1] = tostring(a.exp) end
            end
        end
        return table.concat(out, ",")
    end
    check(heals(10):find("15", 1, true) ~= nil and not heals(10):find("nil", 1, true), true,
          "heal: the wounded ally's heal carries the staff's count: " .. heals(10))
    check(heals(20) ~= "" and not heals(20):find("nil", 1, true), true,
          "heal: the heal the plan may need carries it too: " .. heals(20))
end

-- test_the_enemy_phase_is_played_on_each_way_the_counter_goes (T100b, Manchego Stars ch03 turn 11):
-- A (12 HP) strikes E (9 HP): a hit kills it, a miss lets E's counter take 9. F's AI strikes A
-- only when A is on 4 HP or less, and its blow kills him there. On A's mean HP after the
-- counter, F passes him by and the attack reads safe; on the 3 HP the miss-and-counter leaves,
-- F kills him. Careful's cap is 1%: it holds rather than strike, and the plan says why.
local function counterWays()
    local A = blue(0x01, 0, 0, 0, { hp = 12, maxhp = 12 })
    local E = red(0x81, 1, 0, { hp = 9 })
    local F = red(0x82, 5, 5, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }) },
        fc = { [0x01] = { [0x81] = { ["0,0"] = fc { hit = 60, dmg = 12, hits = 1, counters = true,
                                                   counterHit = 100, counterDmg = 9,
                                                   counterHits = 1 } } } },
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.unit.id == 0x01 and b.hp <= 4 then
                    return { { target = 0x01, enemy = 0x82, takenHit = 100, takenDmg = 4,
                               takenHits = 1, takenCrit = 0 } }
                end
            end
            return {}
        end,
    }
    return boardOf(A, E, F), sightOf(o)
end
do
    local board, sight = counterWays()
    local a, rec = Planner.plan(B, board, sight, style("careful"))
    check(a and a.act, "wait", "counter ways: careful does not strike into the miss-and-counter death")
    local risk
    for _, c in ipairs(rec and rec.considered or {}) do
        if c.rank.key:find(">attack@") then risk = c.rank.max_die end
    end
    local miss = 1 - Sight.rollChance(2, 60)
    check(risk and math.abs(risk - miss) < 1e-9, true,
          "counter ways: the attack reads the miss's chance, the way the counter kills by F")
end

-- test_a_counter_that_kills_is_not_undone_by_a_later_heal (PR #585 review): A (12 HP)
-- strikes E (9 HP); a miss lets E's 12-damage counter kill A, then H's staff gives A 10. The
-- heal comes after the death: the way the counter kills plays the phase without A, never with
-- A standing on what the heal gives back.
do
    local A = blue(0x01, 0, 0, 0, { hp = 12, maxhp = 12 })
    local H = blue(0x02, 1, 0, 1, { minRange = false })
    local E = red(0x81, 1, 0, { hp = 9 })
    local seen = {}
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }), [0x02] = tiles({ 0, 1 }) },
        staves = { [0x02] = { { slot = 0, amount = 10 } } },
        heals = { [0x02] = { ["0,1"] = { { slot = 0, amount = 10, targets = { 0x01 } } } } },
        fc = { [0x01] = { [0x81] = { ["0,0"] = fc { hit = 60, dmg = 12, hits = 1, counters = true,
                                                   counterHit = 100, counterDmg = 12,
                                                   counterHits = 1 } } } },
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.unit.id == 0x01 then seen[#seen + 1] = b.hp end
            end
            return {}
        end,
    }
    local _, plan = Planner.plan(B, boardOf(A, H, E), sightOf(o), style("bold"))
    local healed
    for _, c in ipairs(plan and plan.considered or {}) do
        local k = table.concat(c.acts, " ")
        if k:find("1>attack@") and k:find("2>staff@") then healed = true end
    end
    check(healed, true, "heal after a counter death: the attack-then-heal plan is judged")
    local low = 12
    for _, hp in ipairs(seen) do low = math.min(low, hp) end
    check(low, 12,
          "heal after a counter death: A never stands on the heal the counter's death denies")
end
-- the same with the counter left to the average (BRANCH = 0, PR #585 re-review): the phase
-- strikes A for 6 wherever A stands. Only a miss lets the counter kill A, and that death is
-- the counter's; the phase strikes only an A the counter left standing, healed, and kills
-- none. A's death in the attack-then-heal plan is the miss's chance once, never the phase's
-- again on an HP the heal gave a dead unit.
do
    local A = blue(0x01, 0, 0, 0, { hp = 12, maxhp = 12 })
    local H = blue(0x02, 1, 0, 1, { minRange = false })
    local E = red(0x81, 1, 0, { hp = 9 })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }), [0x02] = tiles({ 0, 1 }) },
        staves = { [0x02] = { { slot = 0, amount = 10 } } },
        heals = { [0x02] = { ["0,1"] = { { slot = 0, amount = 10, targets = { 0x01 } } } } },
        fc = { [0x01] = { [0x81] = { ["0,0"] = fc { hit = 60, dmg = 12, hits = 1, counters = true,
                                                   counterHit = 100, counterDmg = 12,
                                                   counterHits = 1 } } } },
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.unit.id == 0x01 then
                    return { { target = 0x01, takenHit = 100, takenDmg = 6, takenHits = 1,
                               takenCrit = 0 } }
                end
            end
            return {}
        end,
    }
    local saved = Planner.BRANCH
    Planner.BRANCH = 0
    local ok, a, plan = pcall(Planner.plan, B, boardOf(A, H, E), sightOf(o), style("bold"))
    Planner.BRANCH = saved
    check(ok, true, "averaged counter: the plan is made" .. (ok and "" or (": " .. tostring(a))))
    local die
    for _, c in ipairs(plan and plan.considered or {}) do
        local k = table.concat(c.acts, " ")
        if k:find("1>attack@") and k:find("2>staff@") then die = c.rank.max_die end
    end
    local miss = 1 - Sight.rollChance(2, 60)
    check(die and math.abs(die - miss) < 1e-9, true,
          "averaged counter: A dies on the miss alone (" .. tostring(die) .. " vs " .. miss .. ")")
end

-- test_planner_weighs_the_enemy_phase: marching to (1,0) gains 20 steps of the field toward a
-- village worth 1000 gold, but the AI would strike A there for `dmg` of its 20 HP. A blow that
-- cannot kill is under every cap, and progress comes before HP left (FR-011): every style takes
-- the ground. A sure death there is over every cap: no style buys it.
local function weighsThePhase(dmg)
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    -- X stands where (1,0) is no nearer: the objective's way there pulls neither way
    local X = red(0x81, 0, 9, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        field = function(t)
            return t.x == 9 and t.y == 0 and { [0] = { [0] = 40, [1] = 20 } } or nil
        end,
        explorable = { { x = 9, y = 0, kind = "visit" } },
        canExplore = { [0x01] = { ["9,0"] = "visit" } },
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.x == 1 then
                    return { { target = b.unit.id, takenHit = 100, takenDmg = dmg, takenHits = 1,
                               takenCrit = 0 } }
                end
            end
            return {}
        end,
    }
    return boardOf(A, X), sightOf(o)
end
do
    local board, sight = weighsThePhase(10)
    check(at(Planner.plan(B, board, sight, gifted("careful", 1000))), "1,0",
          "planner: careful takes the ground under a blow that cannot kill")
    board, sight = weighsThePhase(10)
    check(at(Planner.plan(B, board, sight, gifted("bold", 1000))), "1,0",
          "planner: bold takes the ground")
    board, sight = weighsThePhase(20)
    check(at(Planner.plan(B, board, sight, gifted("bold", 1000))), "0,0",
          "planner: no style walks into a sure death for ground")
end

-- test_a_struck_weapon_is_held_next_phase: the game equips the weapon a unit struck with
-- (EquipUnitItemSlot), so it counters with it: A's javelin (slot 1) strikes E from two tiles,
-- and the act's exposure and the plan's enemy phase are judged with A holding it.
do
    local A = blue(0x01, 0, 0, 0, { weapons = { { slot = 0, min = 1, max = 1 },
                                                { slot = 1, min = 1, max = 2 } } })
    local E = red(0x81, 0, 2, { hp = 30, minRange = 1, maxRange = 1 })
    local judged = {}
    local o = { reach = { [0x01] = tiles({ 0, 0 }), [0x81] = tiles({ 0, 2 }, { 0, 1 }) },
                danger = { ["0,0"] = 1 },
                fc = { [0x01] = { [0x81] = { ["0,0"] = fc { hit = 100, dmg = 3, hits = 1 } } } },
                enemyPhase = function(plan)
                    for _, b in ipairs(plan.blues) do judged[#judged + 1] = tostring(b.slot) end
                    return {}
                end }
    local sight = sightOf(o)
    local asked, strike = {}, sight.strike
    sight.strike = function(u, e, x, y, slot)
        asked[tostring(slot)] = true
        return strike(u, e, x, y, slot)
    end
    local att
    for _, c in ipairs(B.candidates(boardOf(A, E), sight, style("careful"))) do
        for _, a in ipairs(c.acts) do if a.act == "attack" then att = a end end
    end
    check(att and att.slot, 1, "held: the javelin strikes")
    check(asked["1"], true, "held: the act's exposure holds the javelin")
    local a = Planner.plan(B, boardOf(A, E), sight, style("bold"))
    check(a and a.act, "attack", "held: the plan strikes")
    check(table.concat(judged, ","):find("1") ~= nil, true,
          "held: the plan's enemy phase holds the javelin")
end

-- test_planner_mends_a_plan_that_loses_a_unit: A's Vulnerary at (1,0) is its best act by its
-- own score, and the beam (BEAM = 1) keeps only that; the enemy phase kills A there. The
-- mend tries A's other acts and finds the hold at (0,0), where nothing strikes it.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false, hp = 10, maxhp = 20 })
    local X = red(0x81, 9, 9, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        field = function() return { [0] = { [0] = 40, [1] = 20 } } end,
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.x == 1 then
                    return { { target = b.unit.id, takenHit = 100, takenDmg = 99, takenHits = 1,
                               takenCrit = 0 } }
                end
            end
            return {}
        end,
    }
    local beam = Planner.BEAM
    Planner.BEAM = 1
    local a, plan = Planner.plan(B, boardOf(A, X), sightOf(o), style("careful"))
    Planner.BEAM = beam
    check(at(a) .. " " .. tostring(plan and plan.kind), "0,0 mend",
          "planner: the mend keeps A out of the strike")
end

-- test_planner_prices_a_heal_thrown_away (ADR 0408): A has a 10-HP Vulnerary and nothing can
-- reach it. Each HP the heal throws away costs W.heal; each it restores earns W.heal and
-- closes W.taken of the judge's deficit: used past W.heal * 10 / (2 * W.heal + W.taken) of its 10.
do
    local X = red(0x81, 9, 9, { minRange = false })
    local o = { reach = { [0x01] = tiles({ 0, 0 }) },
                mend = { [0x01] = { slot = 1, amount = 10 } } }
    -- careful (1.5, 2): past 3 of 10; even (1, 1): past 10/3, so 3 down is kept there
    for _, c in ipairs({ { 17, "wait", "careful" }, { 16, "wait", "careful" },
                         { 14, "item", "careful" }, { 12, "item", "careful" },
                         { 15, "wait", "even" }, { 14, "item", "even" } }) do
        local A = blue(0x01, 0, 0, 0, { minRange = false, hp = c[1], maxhp = 18 })
        local a = Planner.plan(B, boardOf(A, X), sightOf(o), style(c[3]))
        check(a and a.act, c[2], "price: " .. (18 - c[1]) .. " HP down, " .. c[3])
    end
end

-- test_planner_swaps_a_held_units_wait_for_its_heal (ADR 0408): A is 12 down with a 10-HP
-- Vulnerary and nothing can reach it. Its march to (1,0) scores best on its own, so the beam
-- (BEAM = 1) keeps only that and no plan it builds heals A; no unit is at risk, so the mend
-- tries nothing. The heal swap judges the plan with A's Vulnerary on (1,0), and the rank
-- plays it. On the deep diagnostic that plan is a finalist like any other and meets the
-- lookahead's second phase.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false, hp = 6, maxhp = 18 })
    local X = red(0x81, 9, 9, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        field = function() return { [0] = { [0] = 40, [1] = 20 } } end,
        mend = { [0x01] = { slot = 1, amount = 10 } },
    }
    local beam = Planner.BEAM
    Planner.BEAM = 1
    local ok, a, plan = pcall(Planner.plan, B, boardOf(A, X), sightOf(o), style("careful"))
    local deep, dplan
    if ok then
        o.nextPhase = function() return {} end
        ok, deep, dplan = pcall(Planner.plan, B, boardOf(A, X), sightOf(o), style("careful"),
                                { diag = "deep" })
    end
    Planner.BEAM = beam
    if not ok then error(a or deep) end
    check((a and a.act) .. " " .. at(a) .. " " .. tostring(plan and plan.kind), "item 1,0 heal",
          "swap: A heals on the tile its march gives it")
    local extended
    for _, c in ipairs(dplan and dplan.considered or {}) do
        if c.kind == "heal" then extended = c.extended end
    end
    check(tostring(deep and deep.act) .. " " .. tostring(extended), "item true",
          "swap: the heal plan meets the lookahead as a finalist")
end

-- test_the_swapped_heal_names_the_ally_on_its_tile (ADR 0408, 0422): the heal swap asks
-- Bot.mendAt for A's Vulnerary on (1,0), where K, yet to act, stands. The act names K to vacate,
-- as every offered act on an ally's tile does, so the planner holds it until K has moved; without
-- it the swap healed A on K's tile first and the harness could not end the move there (vanilla
-- E_19, 2026-11-16).
do
    local A = blue(0x01, 0, 0, 0, { minRange = false, hp = 6, maxhp = 18 })
    local K = blue(0x02, 1, 1, 0, { minRange = false })
    local X = red(0x81, 9, 9, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x02] = tiles({ 1, 0 }, { 2, 0 }) },
        mend = { [0x01] = { slot = 1, amount = 10 } },
    }
    local _, ctx = B.candidates(boardOf(A, K, X), sightOf(o), style("careful"))
    local h = B.mendAt(ctx, A, { x = 1, y = 0 })
    check(h and h.act, "item", "swapped heal: A's Vulnerary")
    check(h and h.vacate, K.id, "swapped heal: K, on its tile, is named to vacate")
    check(h and type(h.exposure), "table", "swapped heal: its exposure is read")
end

-- test_planner_swap_reads_the_plans_hp (ADR 0408): A is 12 down with a 4-HP Vulnerary; H heals
-- it 11 with its staff. With BEAM = 1 the beam's best is the staff, then A's wait 1 short: on
-- the plan's HP its Vulnerary would restore 1 and throw 3 away, below the break-even. The swap
-- reads that same HP, swaps nothing, and judges no "heal" plan; read off the start board (12
-- down, all 4 restored) it would swap the Vulnerary in on top of the staff.
do
    local H = blue(0x01, 0, 0, 1, { minRange = false })
    local A = blue(0x02, 1, 0, 0, { hp = 8, maxhp = 20, minRange = false })
    local X = red(0x81, 9, 9)
    local o = {
        reach = { [0x02] = tiles({ 0, 0 }), [0x01] = tiles({ 0, 1 }) },
        mend = { [0x02] = { slot = 1, amount = 4 } },
        staves = { [0x01] = { { slot = 0, amount = 11 } } },
        heals = { [0x01] = { ["0,1"] = { { slot = 0, amount = 11, targets = { 0x02 } } } } },
    }
    local beam = Planner.BEAM
    Planner.BEAM = 1
    local ok, _, plan = pcall(Planner.plan, B, boardOf(H, A, X), sightOf(o), style("careful"))
    Planner.BEAM = beam
    if not ok then error(_) end
    local beamBest, heal = nil, 0
    for _, c in ipairs(plan and plan.considered or {}) do
        if c.kind == "beam" and not beamBest then beamBest = table.concat(c.acts, " ") end
        if c.kind == "heal" then heal = heal + 1 end
    end
    check(beamBest, "1>staff@0,1>2 2>wait@0,0>nil", "swap HP: the beam's best is staff, then A waits")
    check(heal, 0, "swap HP: no heal plan for the 1 HP the staff left")
end

-- test_planner_keeps_a_staff_heal_through_its_targets_act (ADR 0408): A is 12 down; H, first in
-- the plan (the lower id), heals it 11 with its staff, then A waits. The plan leaves A at 19:
-- each act starts from the HP the plan has given its unit. From the start board's HP, A's wait
-- set it back to 8 and the heal counted for nothing in the judged phase.
do
    local H = blue(0x01, 0, 0, 1, { minRange = false })
    local A = blue(0x02, 1, 0, 0, { hp = 8, maxhp = 20, minRange = false })
    local X = red(0x81, 9, 9)
    local o = {
        reach = { [0x02] = tiles({ 0, 0 }), [0x01] = tiles({ 0, 1 }) },
        staves = { [0x01] = { { slot = 0, amount = 11 } } },
        heals = { [0x01] = { ["0,1"] = { { slot = 0, amount = 11, targets = { 0x02 } } } } },
    }
    local _, plan = Planner.plan(B, boardOf(H, A, X), sightOf(o), style("careful"))
    local acts, hp = {}, nil
    for _, a in ipairs(plan and plan.acts or {}) do acts[#acts + 1] = a.act .. a.unitId end
    for _, p in ipairs(plan and plan.predict or {}) do
        if p.id == 0x02 then hp = p.hp end
    end
    check(table.concat(acts, " ") .. " " .. tostring(hp), "staff1 wait2 19",
          "plan HP: the staff's heal stays through A's wait")
end

-- test_planner_beam_keeps_one_order: two units, two tiles each, nothing to fight. The beam
-- reaches each pair of tiles in both orders; the plans judged are each a different board.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local C = blue(0x02, 1, 0, 2, { minRange = false })
    local X = red(0x81, 9, 9, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x02] = tiles({ 0, 2 }, { 1, 2 }) },
        field = function() return { [0] = { [0] = 40, [1] = 20 }, [2] = { [0] = 40, [1] = 20 } } end,
    }
    local _, plan = Planner.plan(B, boardOf(A, C, X), sightOf(o), style("careful"))
    local seen, twice = {}, false
    for _, c in ipairs(plan and plan.considered or {}) do
        local set = {}
        for _, k in ipairs(c.acts) do set[#set + 1] = k end
        table.sort(set)
        set = table.concat(set, "|")
        if seen[set] then twice = true end
        seen[set] = true
    end
    check(plan ~= nil and #plan.considered > 1 and not twice, true,
          "planner: no plan judged twice in another order")
end

-- test_planner_judges_every_way_the_phase_goes: at (1,0) X strikes A for nothing, and A's
-- counter may kill X (sight.enemyPhase plays the phase both ways, as likely as the counter's
-- played chance). If it does, Y takes X's tile and kills A. The judge pays A's death in that
-- outcome only: die = that outcome's chance, not 0 and not 1 (2RN 10, under bold's cap).
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local X = red(0x81, 9, 9, { minRange = false })
    -- a red far off that never strikes: X falling is not the Rout's last kill, which would
    -- close the village and pay the win (sightOf's strikes carry the counter's `felled`)
    local Z = red(0x83, 15, 15, { minRange = false })
    local q = Sight.rollChance(2, 10)
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        field = function() return { [0] = { [0] = 40, [1] = 5 } } end,
        -- a village beside (1,0), worth bold's stand there
        explorable = { { x = 9, y = 0, kind = "visit" } },
        canExplore = { [0x01] = { ["9,0"] = "visit" } },
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.x == 1 then
                    local x = { enemy = 0x81, target = b.unit.id, takenHit = 0, takenDmg = 0,
                                takenHits = 1, takenCrit = 0, counterHit = 10, counterDmg = 20,
                                counterHits = 1, counterCrit = 0, strikerHp = 10,
                                targetHp = b.hp }
                    local y = { enemy = 0x82, target = b.unit.id, takenHit = 100, takenDmg = 99,
                                takenHits = 1, takenCrit = 0 }
                    local out = { x }
                    out.outcomes = { { p = 1 - q, strikes = { x } }, { p = q, strikes = { x, y } } }
                    return out
                end
            end
            return {}
        end,
    }
    local _, plan = Planner.plan(B, boardOf(A, X, Z), sightOf(o), gifted("bold", 10000))
    local die
    for _, p in ipairs(plan and plan.predict or {}) do
        if p.id == 0x01 and p.x == 1 then die = p.die end
    end
    check(die ~= nil and math.abs(die - q) < 1e-9, true,
          "planner: A dies only in the outcome where X falls")
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

-- test_planner_no_vulnerary_after_a_full_heal: A is 15 down with a 10-HP Vulnerary; H's staff
-- heals 20. Once H has healed A, A is full and FE8 refuses the Vulnerary (CanUnitUseHealItem:
-- HP == max), so no plan uses it after the heal. ch02 turn 9 played exactly that and crashed:
-- the Vulnerary act's gain was read off the start board.
do
    local A = blue(0x01, 0, 0, 0, { hp = 5, maxhp = 20, minRange = false })
    local H = blue(0x02, 1, 0, 1, { minRange = false })
    local X = red(0x81, 9, 9)
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }), [0x02] = tiles({ 0, 1 }) },
        mend = { [0x01] = { slot = 1, amount = 10 } },
        staves = { [0x02] = { { slot = 0, amount = 20 } } },
        heals = { [0x02] = { ["0,1"] = { { slot = 0, amount = 20, targets = { 0x01 } } } } },
    }
    local _, plan = Planner.plan(B, boardOf(A, H, X), sightOf(o), style("careful"))
    local bad = 0
    for _, c in ipairs(plan and plan.considered or {}) do
        local healed = false
        for _, k in ipairs(c.acts) do
            if k:match("^2>staff@.*>1$") then healed = true end
            if healed and k:match("^1>item@") then bad = bad + 1 end
        end
    end
    check(bad, 0, "planner: no Vulnerary on a unit the plan has healed full")
    local acts = {}
    for _, a in ipairs(plan and plan.acts or {}) do acts[#acts + 1] = a.act end
    check(table.concat(acts, ","):find("staff") ~= nil, true, "planner: the staff heal is played")
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

-- test_planner_traces_the_screen (#510, the cheap screen's offline test): every plan judged
-- carries what the beam knew before the judge -- its acts' summed score, the likeliest death
-- and the summed chance over its acts' standing exposure at the plan's final kills and HP --
-- and the enemy phases its judge played. X strikes B on (2,2) for 25 of 20 at 100% and A on
-- (0,1) at 50%; A's sure kill from (0,0) takes X out of every exposure.
do
    local A = blue(0x01, 0, 0, 0)
    local Bu = blue(0x02, 1, 0, 2, { minRange = false })
    local X = red(0x81, 1, 0, { hp = 5 })
    -- Y, far off, keeps the map from being won by X's death (the win makes every move moot)
    local Y = red(0x82, 9, 9, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 0, 1 }), [0x02] = tiles({ 0, 2 }, { 2, 2 }),
                  [0x81] = tiles({ 1, 0 }, { 2, 1 }, { 1, 1 }) },
        field = function() return { [0] = { [0] = 50, [1] = 45 }, [2] = { [0] = 40, [2] = 20 } } end,
        danger = { ["2,2"] = 1, ["0,1"] = 1 },
        fc = { [0x01] = { [0x81] = { ["0,0"] = fc { hit = 100, dmg = 9, hits = 1, killsTarget = true },
                                     ["0,1"] = fc { takenHit = 50, takenDmg = 25, takenHits = 1 } } },
               [0x02] = { [0x81] = { ["2,2"] = fc { takenHit = 100, takenDmg = 25, takenHits = 1 } } } },
        enemyPhase = function() return {} end,
    }
    local final = Planner.FINAL
    Planner.FINAL = 8
    local _, plan = Planner.plan(B, boardOf(A, Bu, X, Y), sightOf(o), style("bold"))
    Planner.FINAL = final
    local by = {}
    for _, c in ipairs(plan and plan.considered or {}) do by[table.concat(c.acts, " ")] = c.screen or {} end
    local function line(acts)
        local sc = by[acts]
        return sc and string.format("%s %s %s %s", sc.base, sc.max_die, sc.sum_die, sc.phases) or "not judged"
    end
    check(line("1>attack@0,0>129 2>wait@2,2>nil"), "45.0 0.0 0.0 1", "screen: the kill takes X out of B's exposure")
    check(line("1>wait@0,0>nil 2>wait@2,2>nil"), "0.0 1.0 1.0 1", "screen: B alone in X's reach")
    check(line("1>wait@0,1>nil 2>wait@2,2>nil"), "0.0 1.0 1.505 1", "screen: two in reach, the likeliest and the sum")
    check(line("1>wait@0,0>nil 2>wait@0,2>nil"), "0.0 0.0 0.0 1", "screen: none in reach")
end

-- test_planner_floors_the_plans_ways (ADR 0415): a way of the plan's uncertain kills splits only
-- while the chance off its likeliest side is at least sight's floor of the whole plan, and each
-- enemy phase is told its way's share of the plan (sight bounds its own splits by it). A strikes
-- X from (0,0) for a kill at `hit`%; Y, far off, keeps the map from being won by X's death.
do
    local function judge(hit)
        local A = blue(0x01, 0, 0, 0)
        local X = red(0x81, 1, 0, { hp = 5 })
        local Y = red(0x82, 9, 9, { minRange = false })
        local masses = {}
        local o = {
            reach = { [0x01] = tiles({ 0, 0 }) },
            field = function() return { [0] = { [0] = 50 } } end,
            fc = { [0x01] = { [0x81] = { ["0,0"] = fc { hit = hit, dmg = 9, hits = 1, killsTarget = true } } } },
            enemyPhase = function(plan)
                -- the attack plan's phases only: its board holds X (the one that waits does not)
                if plan.reds[0x81] then masses[#masses + 1] = plan.mass end
                return {}
            end,
        }
        local _, plan, cost = Planner.plan(B, boardOf(A, X, Y), sightOf(o), style("bold"))
        local sc
        for _, c in ipairs(plan and plan.considered or {}) do
            if table.concat(c.acts, " ") == "1>attack@0,0>129" then sc = c.screen end
        end
        table.sort(masses)
        for i, m in ipairs(masses) do masses[i] = string.format("%.3f", m) end
        return sc and sc.phases, cost and cost.floored, masses, cost and cost.averaged
    end
    local phases, floored, masses, averaged = judge(50)
    check(averaged, 0, "floor: a kill split is not averaged")
    check(phases, 2, "floor: an even kill splits the plan into two phases")
    check(floored, 0, "floor: and leaves no way unsplit")
    -- (the game's two-dice hit: 50 shown is 49.5% true)
    check(table.concat(masses, " "), "0.495 0.505", "floor: each phase is told its way's share")
    phases, floored, masses, averaged = judge(99)
    check(averaged, 1, "floor: a kill no way split is left to the average")
    check(phases, 1, "floor: a 1% miss is under the floor, one phase on the average")
    check(floored, 1, "floor: the way left unsplit is counted")
    check(table.concat(masses, " "), "1.000", "floor: that phase is the whole plan")
end

-- test_planner_exposure_spares_the_killed: A's sure kill removes X, the only enemy that
-- reaches (2,2), so B's march there costs nothing -- whichever unit the beam moves first.
do
    local A = blue(0x01, 0, 0, 0)
    local Bu = blue(0x02, 1, 0, 2, { minRange = false })
    local X = red(0x81, 1, 0, { hp = 5 })
    -- Y, far off, keeps the map from being won by X's death (the win makes every move moot)
    local Y = red(0x82, 9, 9, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }), [0x02] = tiles({ 0, 2 }, { 2, 2 }),
                  [0x81] = tiles({ 1, 0 }, { 2, 1 }) },
        field = function() return { [0] = { [0] = 50 }, [2] = { [0] = 40, [2] = 20 } } end,
        danger = { ["2,2"] = 1 },
        fc = { [0x01] = { [0x81] = { ["0,0"] = fc { hit = 100, dmg = 9, hits = 1, killsTarget = true } } },
               [0x02] = { [0x81] = { ["2,2"] = fc { takenHit = 100, takenDmg = 25, takenHits = 1 } } } },
    }
    local _, plan = Planner.plan(B, boardOf(A, Bu, X, Y), sightOf(o), style("careful"))
    local moved
    for _, a in ipairs(plan and plan.acts or {}) do
        if a.unitId == 0x02 then moved = at(a) end
    end
    check(moved, "2,2", "planner: a killed enemy threatens no one")
end

-- test_planner_visits_a_safe_village: nothing reaches the village at (1,0), worth 500 gold, so
-- careful takes it; the offer is in the plan's record, played, at no chance to die.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local X = red(0x81, 9, 9, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }, { 0, 1 }) },
        explorable = { { x = 1, y = 0, kind = "visit" } },
        canExplore = { [0x01] = { ["1,0"] = "visit" } },
    }
    local a, plan = Planner.plan(B, boardOf(A, X), sightOf(o), gifted("careful", 500))
    check(a and a.act, "visit", "explore: a safe village is visited")
    check(at(a), "1,0", "explore: from its own tile")
    local e = plan and plan.explore and plan.explore[1]
    check(e and e.die, 0, "explore: offered at no chance to die")
    check(e and e.played, true, "explore: the offer was played")
    -- a unit the game refuses (a Phantom, a Silenced unit) is offered nothing
    o.canExplore = {}
    local b = Planner.plan(B, boardOf(A, X), sightOf(o), gifted("careful", 500))
    check(b and b.act ~= "visit", true, "explore: only where the game's menu allows it")
end

-- test_planner_weighs_a_risky_chest: X reaches the chest and kills A there for sure. A chest of
-- 500 gold is left under every style (bold's 75 points against its 60 a death, and the chest
-- lost with A); the offer is recorded with its chance to die, unplayed.
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
        local a, plan = Planner.plan(B, boardOf(A, X), sightOf(o), gifted(aggression, 500))
        check(a and a.act ~= "chest", true, "explore: no deadly chest, " .. aggression)
        local e = plan and plan.explore and plan.explore[1]
        check(e and e.die > 0, true, "explore: the offer carries its chance to die, " .. aggression)
        check(e and e.played, nil, "explore: unplayed, " .. aggression)
    end
end

-- test_planner_prices_a_small_risk: the enemy phase the AI plays strikes A at the village with
-- a small chance to kill (2RN 10: 2.1%). Careful leaves it at 500 gold and at 100000 too: the
-- chance is over careful's 1% cap, and no gold buys risk over the cap (ADR 0384).
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
    local die = Sight.rollChance(2, 10)
    check(die > 0 and die < 0.1, true, "explore: the strike's chance to kill is small")
    check(at(Planner.plan(B, boardOf(A, X), sightOf(o), gifted("careful", 500))), "0,0",
          "explore: careful leaves a small village to a small risk")
    check(at(Planner.plan(B, boardOf(A, X), sightOf(o), gifted("careful", 100000))), "0,0",
          "explore: careful leaves a rich one too: the risk is over its cap")
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

    -- test_exploring_sends_the_faster_in_a_race: a looter closes (8,0) after enemy phase 2. A
    -- (MOV 4, 2 turns: phase 2 unacted) and a slow B (MOV 1, 3 tiles: 3 turns, too late) can
    -- both use it; nearer by the field, B was the old pick. A is sent: B would get nothing.
    do
        local A2 = blue(0x01, 0, 0, 0, { minRange = false, mov = 4 })
        local B2 = blue(0x02, 1, 5, 0, { minRange = false, mov = 1 })
        local race = {}
        for k, v in pairs(o) do race[k] = v end
        race.closings = { ["8,0"] = 2 }
        local _, ctx = B.candidates(boardOf(A2, B2, X), sightOf(race), style("careful"))
        check(ctx.exploreGoal[0x01] and ctx.exploreGoal[0x01].x, 8,
              "exploring: the unit that gets there in time is sent")
        check(ctx.exploreGoal[0x02], nil, "exploring: the one too slow for the race is not")
    end

    -- test_threats_are_the_seen_and_the_remembered (ADR 0399): enemiesOf's first list is the
    -- reds in sight (what can be targeted); its second adds every fogged red sight.knows, which
    -- can strike; a fogged one not remembered is in neither. Attempt 1 (no knows) adds none.
    do
        local hid = red(0x82, 3, 3, { fogged = true, charId = 0x50 })
        local other = red(0x83, 4, 4, { fogged = true, charId = 0x51 })
        local function ids(list)
            local out = {}
            for _, u in ipairs(list) do out[#out + 1] = string.format("%x", u.id) end
            return table.concat(out, ",")
        end
        local seen, threats = B.enemiesOf(boardOf(A, X, hid, other), sightOf({ known = { [0x82] = true } }))
        check(ids(seen), string.format("%x", X.id), "enemiesOf: in sight only")
        check(ids(threats), string.format("%x,82", X.id), "enemiesOf: the threats add the remembered")
        local _, plain = B.enemiesOf(boardOf(A, X, hid, other), sightOf({}))
        check(ids(plain), string.format("%x", X.id), "enemiesOf: no memory, no fogged threat")
    end

    -- test_exploring_keeps_the_sent_unit: A was sent last decision. B is nearer now, but A
    -- keeps the village while it can still use it, and B marches on the enemy. (Re-picking
    -- per decision left ch02's (12,3) handed between two units and never reached.)
    local function sentMarches(sent, ...)
        local out = {}
        for _, c in ipairs(B.candidates(boardOf(...), sightOf(o), style("careful"), { sent = sent })) do
            for _, a in ipairs(c.acts) do
                if a.why == "march" then out[c.unit.id] = at(a) end
            end
        end
        return out
    end
    local sentA = { { id = 0x01, x = 8, y = 0 } }
    marches = sentMarches(sentA, A, Bu, X)
    check(marches[0x01], "1,0", "exploring: the sent unit keeps its village")
    check(marches[0x02], "5,1", "exploring: the nearer unit is not re-sent to it")
    -- A has acted this turn: it still holds the village, so B is not sent there instead
    local acted = blue(0x01, 0, 0, 0, { minRange = false, acted = true })
    marches = sentMarches(sentA, acted, Bu, X)
    check(marches[0x02], "5,1", "exploring: an acted sent unit still holds its village")
    -- the game's check is never asked of a unit that has acted (it is a menu check, and its
    -- answer is cached by the unit's facts: ch02's turn-7 "no" outlived the turn)
    local asked = {}
    local can = o.canExplore
    local s = sightOf(o)
    local inner = s.canExplore
    s.canExplore = function(u, ...) asked[#asked + 1] = u.id; return inner(u, ...) end
    B.candidates(boardOf(acted, Bu, X), s, style("careful"), { sent = sentA })
    local askedA = 0
    for _, id in ipairs(asked) do
        if id == 0x01 then askedA = askedA + 1 end
    end
    check(#asked > 0, true, "exploring: the game's check is asked of the unit that can act")
    check(askedA, 0, "exploring: the game's check is not asked of an acted unit")
    o.canExplore = can
    -- A can no longer use it (the game's check says no): it is released to the nearest
    o.canExplore[0x01] = {}
    marches = sentMarches(sentA, A, Bu, X)
    check(marches[0x02], "6,0", "exploring: a sent unit that cannot use the tile releases it")
    o.canExplore[0x01] = { ["8,0"] = "visit" }
    -- the village is gone (visited, or pillaged): nobody is sent to it
    o.explorable = {}
    marches = sentMarches(sentA, A, Bu, X)
    check(marches[0x01], "0,1", "exploring: a closed tile releases its unit")
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
    -- a Seize map whose seize tile the boss holds (vanilla I_14's Vigarde): the game offers no
    -- Seize past him, so his death is the win's step and the assault is the same
    o.objective = { kind = "seize", tile = { x = 1, y = 1 } }
    Planner.BEAM = 2
    local _, held = Planner.plan(B, boardOf(blue(0x01, 0, 0, 0), blue(0x02, 1, 0, 2), plain),
                                 sightOf(o), style("careful"))
    Planner.BEAM = beam
    check(held and held.kind, "assault", "assault: the enemy holding the seize tile")
    check(Planner.throne(o.objective, { { id = 0x81, x = 1, y = 1 } }), 0x81,
          "throne: the enemy on the seize tile")
    check(Planner.throne(o.objective, { { id = 0x81, x = 2, y = 1 } }), nil,
          "throne: none off it")
    check(Planner.throne({ kind = "boss" }, { { id = 0x81, x = 1, y = 1 } }), nil,
          "throne: none on a map with no seize tile")
    o.objective = { kind = "boss" }
end

-- test_planner_assault_baits (#641, vanilla E_20's Morva, charId 0x41): a Guard Tile boss X
-- (62 HP) strikes from its tile at range 1-2 for 36, its counter the same, at the unit in
-- range it can kill first (the game's AI prefers a kill); one tile beside it. E (51 HP) deals
-- 30 twice at 81% from there: 60, short of the kill, and E at 15 HP meets X's own strike. A, C
-- and D (30 HP) reach it from range 2 and deal 0. The assault seats none of them (a
-- blow that cannot hurt X buys its counter and nothing else); with E alone short of the kill,
-- the bait is judged: E waits on the tile, X strikes and meets E's counter, and the army's
-- reply finishes it at 81% (the lookahead's win). The bait is played, everyone else out of
-- X's range. Then: a second striker F (10 at 50%) makes an assault, which seats E and F and
-- none of A, C, D; E's heavy weapon in bag slot 2 (slot 0's deals 5) is the one the bait holds,
-- in the act and in the judged phase; and against a range-1 X, the bait waits on the tile X
-- strikes, not on E's heavier range-2 tile, where X never answers it.
do
    -- opt: { second = F joins, slots = E's weapons in slots 0 and 2, range1 = X strikes at 1 }
    local function scene(opt)
        local far = opt.range1 and 1 or 2
        local function near(x, y) local d = Board.distance(x, y, 5, 2) return d >= 1 and d <= far end
        local E = blue(0x01, 0, 5, 6, { hp = 51, weapons = opt.slots and {
            { slot = 0, min = 1, max = 1 }, { slot = 2, min = 1, max = 1 } }
            or opt.range1 and { { slot = 0, min = 1, max = 2 } } or nil })
        local units = { E,
            blue(0x02, 1, 2, 6, { hp = 30, minRange = 1, maxRange = 2 }),
            blue(0x03, 2, 8, 6, { hp = 30, minRange = 1, maxRange = 2 }),
            blue(0x04, 3, 5, 9, { hp = 30, minRange = 1, maxRange = 2 }),
            red(0x81, 5, 2, { isBoss = true, hp = 62, minRange = 1, maxRange = far }) }
        if opt.second then units[#units + 1] = blue(0x05, 4, 2, 2, { hp = 51 }) end
        local heavy = fc { hit = 81, dmg = 30, hits = 2, counters = true, counterHit = 100,
                           counterDmg = 36, counterHits = 1, takenHit = 100, takenDmg = 36,
                           takenHits = 1, takenCrit = 2 }
        local naught = fc { hit = 81, dmg = 0, hits = 1, counters = true, counterHit = 100,
                            counterDmg = 36, counterHits = 1, takenHit = 100, takenDmg = 36,
                            takenHits = 1 }
        local armed = {}   -- E's weapon slot in each judged phase where E waits beside X
        -- X's strike on the unit in its range with the least HP (one it kills, before E), E's
        -- counter 30 twice at 81%
        -- with weapons in slots 0 and 2, E counters for 30 only with slot 2's
        local function heavyArmed(plan)
            for _, x in ipairs(plan.blues) do
                if x.unit.id == 0x01 then return not opt.slots or x.slot == 2 end
            end
            return false
        end
        local function strikes(plan)
            for _, x in ipairs(plan.blues) do
                if x.unit.id == 0x01 and x.x == 5 and x.y == 3 and not (plan.reds or {})[0x81] then
                    armed[#armed + 1] = x.slot or "none"
                end
            end
            if plan.gone[0x81] then return {} end
            local b
            for _, x in ipairs(plan.blues) do
                if near(x.x, x.y) and (not b or x.hp < b.hp) then b = x end
            end
            if not b then return {} end
            local e = b.unit.id == 0x01
            return { { enemy = 0x81, target = b.unit.id, takenHit = 100, takenDmg = 36,
                       takenHits = 1, takenCrit = e and 2 or 0, counterHit = 81,
                       counterDmg = e and (heavyArmed(plan) and 30 or 5) or 0,
                       counterHits = e and 2 or 1,
                       counterCrit = 0, strikerHp = (plan.reds or {})[0x81] or 62 } }
        end
        local fcE = { ["5,3"] = heavy }
        if opt.slots then
            fcE = { ["5,3/2"] = heavy, ["5,3/0"] = fc { hit = 81, dmg = 5, hits = 1, counters = true,
                    counterHit = 100, counterDmg = 36, counterHits = 1, takenHit = 100,
                    takenDmg = 36, takenHits = 1, takenCrit = 2 } }
        end
        if opt.range1 then
            -- from range 2 E deals more (51 to 48.6, no counter, still short of 62), and X
            -- (range 1) never strikes it there
            fcE["5,4"] = fc { hit = 85, dmg = 30, hits = 2, counters = false, takenHit = 100,
                              takenDmg = 36, takenHits = 1 }
        end
        local o = {
            objective = { kind = "boss" },
            reach = { [0x01] = tiles({ 5, 6 }, { 5, 3 }, { 4, 6 }, opt.range1 and { 5, 4 } or nil),
                      [0x02] = tiles({ 2, 6 }, { 4, 3 }, { 1, 6 }),
                      [0x03] = tiles({ 8, 6 }, { 6, 3 }, { 9, 6 }),
                      [0x04] = tiles({ 5, 9 }, { 5, 4 }, { 4, 9 }),
                      [0x05] = tiles({ 2, 2 }, { 4, 2 }),
                      [0x81] = tiles({ 5, 2 }) },
            danger = { ["5,3"] = 1, ["4,3"] = 1, ["6,3"] = 1, ["5,4"] = 1, ["4,2"] = 1 },
            fc = { [0x01] = { [0x81] = fcE }, [0x02] = { [0x81] = { ["4,3"] = naught } },
                   [0x03] = { [0x81] = { ["6,3"] = naught } }, [0x04] = { [0x81] = { ["5,4"] = naught } },
                   [0x05] = { [0x81] = { ["4,2"] = fc { hit = 50, dmg = 10, hits = 1, counters = true,
                       counterHit = 100, counterDmg = 36, counterHits = 1, takenHit = 100,
                       takenDmg = 36, takenHits = 1 } } } },
            enemyPhase = strikes,
            -- the reply: E, beside a wounded X, kills it at 81%; the second phase is X's (or none)
            nextPhase = function(plan)
                local out = strikes(plan)
                for _, b in ipairs(plan.blues) do
                    if b.unit.id == 0x01 and b.x == 5 and b.y == 3 and heavyArmed(plan) then
                        out = {}
                        out.reply = { kills = { { unit = 0x01, enemy = 0x81, x = 5, y = 3,
                                                  p = 0.81, lost = 0 } }, steps = {} }
                    end
                end
                return out
            end,
        }
        local a, plan = Planner.plan(B, boardOf(table.unpack(units)), sightOf(o), style("even"))
        return a, plan, near, armed
    end
    local function seatedIn(plan)
        local seated = {}
        for _, c in ipairs(plan and plan.considered or {}) do
            if c.kind == "assault" then
                for _, k in ipairs(c.acts) do
                    if k:match("attack") then seated[#seated + 1] = k:match("^(%d+)>") end
                end
            end
        end
        table.sort(seated)
        return table.concat(seated, " ")
    end
    local a, plan, near = scene({})
    check(seatedIn(plan), "", "bait: E alone deals damage, so there is no assault")
    check(plan and plan.kind, "bait", "bait: the bait is the plan played")
    check(a and a.unitId == 0x01 and a.act .. "@" .. at(a), "wait@5,3",
          "bait: E waits on the tile beside the boss")
    for _, x in ipairs(plan and plan.acts or {}) do
        if x.unitId ~= 0x01 then
            check(near(x.move.x, x.move.y), false,
                  "bait: unit " .. x.unitId .. " waits out of the boss's range")
        end
    end
    -- the reply's kill is the win a turn later, as far as E lives the first phase (its 2% crit
    -- death): the objective's chance rises by GAMMA of it
    local won = plan and plan.lookWin and plan.lookWin.won
    check(won and math.abs(won - 0.81 * 0.98) < 1e-9, true,
          "bait: the lookahead reads the reply's kill as the win, as far as E lives")
    check(table.concat(plan and plan.lookahead.trigger or {}, " "), "bait boss",
          "bait: a plan with the bait meets the second phase")
    local win
    for _, r in ipairs(plan and plan.lookWin and plan.lookWin.worth or {}) do
        if r.kind == "win" then win = r end
    end
    local g = dofile(here .. "goals.lua").GAMMA
    check(win and math.abs(win.after - (g * won + (1 - g * won) * g)) < 1e-9, true,
          "bait: the win's row is the first phase's, with GAMMA of the later kill")
    -- the record's goalWorth stays the first phase's: its win row has no later kill in it
    local first
    for _, r in ipairs(plan and plan.goalWorth or {}) do
        if r.kind == "win" then first = r end
    end
    check(first and math.abs(first.after - g) < 1e-9, true,
          "bait: goalWorth is the first phase's, as `judged` is")
    -- a second striker that hurts X: the assault seats E and F, never a 0-damage unit
    local _, two = scene({ second = true })
    check(seatedIn(two), "1 5", "bait: the assault seats the two strikers that hurt X, and only them")
    -- E's heavy weapon is in slot 2: the bait holds it, in the act and in the judged phase
    local held, sp, _, armed = scene({ slots = true })
    check(sp and sp.kind == "bait" and held and held.act .. "#" .. tostring(held.slot), "wait#2",
          "bait: E waits holding the weapon in slot 2")
    local two2 = false
    for _, s in ipairs(armed) do two2 = two2 or s == 2 end
    check(two2, true, "bait: the judged phase arms E with slot 2")
    -- a range-1 X: the bait waits where X strikes it, not on the heavier range-2 tile
    local _, rp = scene({ range1 = true })
    local baitAt
    for _, c in ipairs(rp and rp.considered or {}) do
        if c.kind == "bait" then baitAt = c.acts[1] end
    end
    check(baitAt, "1>wait@5,3>nil", "bait: against a range-1 boss, the tile it strikes")
end

-- test_a_remembered_boss_is_the_march_goal (#510, ADR 0401; vanilla Ch6 retries): on a Defeat
-- Boss map the boss is the march goal once the party knows where it stands -- in sight, or
-- in fog and remembered by a retry (sight.knows, ADR 0399) -- and it is the unit the objective
-- names, not another CA_BOSS unit. A boss in fog no attempt showed, or one off the field, is no
-- goal (the march heads for the nearest enemy in sight), and on a Rout map a remembered CA_BOSS
-- unit changes nothing: the win condition says what the march is for.
do
    -- X in sight at (3,0); Y the named boss at (9,0); D another CA_BOSS unit at (6,0), ahead of
    -- Y on the board, so "the first CA_BOSS unit" is D
    local function goal(objective, y, known, decoy)
        local A, X = blue(0x01, 0, 0, 0), red(0x81, 3, 0)
        y.charId, y.isBoss = 0x40, true
        local Y = red(0x82, 9, 0, y)
        local D = decoy and red(0x83, 6, 0, { charId = 0x41, isBoss = true, fogged = true })
        local board = decoy and boardOf(A, X, D, Y) or boardOf(A, X, Y)
        local _, ctx = B.candidates(board,
                                    sightOf({ objective = objective, known = known }),
                                    style("careful"))
        local t = ctx.objectiveTile(A)
        return t and (t.x .. "," .. t.y)
    end
    local boss, both = { kind = "boss", boss = 0x40 }, { [0x82] = true, [0x83] = true }
    check(goal(boss, {}), "9,0", "boss goal: a boss in sight")
    check(goal(boss, { fogged = true }, { [0x82] = true }), "9,0",
          "boss goal: a boss in fog a retry remembers")
    check(goal(boss, { fogged = true }), "3,0", "boss goal: none for a boss no attempt showed")
    check(goal(boss, { fogged = true }, both, true), "9,0",
          "boss goal: the boss the objective names, past a nearer remembered CA_BOSS unit")
    check(goal(boss, { fogged = true }, { [0x83] = true }, true), "3,0",
          "boss goal: a remembered CA_BOSS unit the objective does not name is none")
    check(goal({ kind = "boss" }, { fogged = true }, both, true), "6,0",
          "boss goal: with none named, the first CA_BOSS unit known")
    check(goal(boss, { fogged = true, onField = false }, { [0x82] = true }), "3,0",
          "boss goal: none for a boss off the field")
    check(goal({ kind = "rout" }, { fogged = true }, { [0x82] = true }), "3,0",
          "boss goal: a Rout map marches on its nearest enemy in sight")
    -- and the unit walks there: with no enemy in sight the fog would pull A to the unseen tile
    -- at (0,3); the remembered boss at (5,0) pulls it to (1,0)
    local A = blue(0x01, 0, 0, 0)
    local E = red(0x82, 5, 0, { charId = 0x40, isBoss = true, fogged = true })
    local o = { objective = boss, known = { [0x82] = true },
                reach = { [0x01] = tiles({ 0, 0 }, { 0, 1 }, { 1, 0 }) },
                unseen = { { x = 0, y = 3 } } }
    check(at(B.decide(boardOf(A, E), sightOf(o), style("bold"))), "1,0",
          "boss goal: the march steps toward the remembered boss, not the unseen")
    o.known = nil
    check(at(B.decide(boardOf(A, E), sightOf(o), style("bold"))), "0,1",
          "boss goal: with no memory it pushes the fog back")
end

-- test_an_attack_whose_counter_can_kill_is_offered (ADR 0396's known break, the counter
-- refusal; Manchego Stars ch03 even, turn 15: Rootis, 10 HP, beside a boss on 2 HP whose counter
-- hits for 11, and his blow, first, wins the chapter 98 times in 100 -- never offered, so never
-- judged). A cannot get out of the boss's reach, and holding is a sure death; its blow kills the
-- boss nine times in ten, and only a miss lets the 30-damage counter kill it. The attack is
-- offered, its death chance is the counter's, and it is played over the sure death.
do
    local A = blue(0x01, 0, 0, 0, { hp = 20 })
    local X = red(0x81, 1, 1, { isBoss = true, hp = 10 })
    local o = {
        objective = { kind = "boss" },
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x81] = tiles({ 1, 1 }) },
        danger = { ["0,0"] = 1, ["1,0"] = 1 },
        fc = { [0x01] = { [0x81] = { ["1,0"] = fc { hit = 90, dmg = 12, hits = 1, counters = true,
                                                   counterHit = 100, counterDmg = 30,
                                                   counterHits = 1, takenHit = 100,
                                                   takenDmg = 30, takenHits = 1 } } } },
        enemyPhase = function(plan)
            if plan.gone[0x81] then return {} end
            local out = {}
            for _, b in ipairs(plan.blues) do
                out[#out + 1] = { target = b.unit.id, takenHit = 100, takenDmg = 30,
                                  takenHits = 1, takenCrit = 0 }
            end
            return out
        end,
    }
    local a, plan = Planner.plan(B, boardOf(A, X), sightOf(o), style("careful"))
    local blow
    for _, c in ipairs(plan and plan.considered or {}) do
        if c.rank.key:find(">attack@1,0>") then blow = c.rank.max_die end
    end
    check(blow and math.abs(blow - (1 - Sight.rollChance(2, 90))) < 1e-9, true,
          "counter refusal lifted: the blow is judged, at the counter's chance to kill")
    check(a and a.act, "attack", "counter refusal lifted: the blow is played over a sure death")
end

-- test_the_strike_whose_counter_cannot_kill_is_offered (PR #585 review): from (0,0) A's blow
-- kills E 80 times in 100 and E's counter kills A on a miss; from (1,1) A kills 40 times in 100
-- and E cannot counter. Neither tile is in an enemy phase's reach, so the old "safest" (least
-- exposed) tied and kept the first, the strike whose counter kills: (1,1) was never offered.
do
    local A = blue(0x01, 0, 0, 0, { hp = 20 })
    local E = red(0x81, 1, 0, { hp = 10 })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 1 }) },
        fc = { [0x01] = { [0x81] = {
            ["0,0"] = fc { hit = 80, dmg = 12, hits = 1, counters = true, counterHit = 100,
                           counterDmg = 30, counterHits = 1 },
            ["1,1"] = fc { hit = 40, dmg = 12, hits = 1 } } } },
    }
    local on = {}
    for _, c in ipairs(B.candidates(boardOf(A, E), sightOf(o), style("careful"))) do
        for _, a in ipairs(c.acts) do
            if a.act == "attack" then on[a.move.x .. "," .. a.move.y] = true end
        end
    end
    check(on["0,0"], true, "safest strike: the likelier kill is offered")
    check(on["1,1"], true, "safest strike: the strike whose counter cannot kill is offered too")
end
-- and the least exposed strike is still offered beside it (PR #585 re-review): from (0,0) the
-- best kill; from (1,1) no counter can kill but the enemy phase reaches it; from (2,0) a
-- counter can kill on a miss, and no enemy phase reaches it. All three are offered.
do
    local A = blue(0x01, 0, 0, 0, { hp = 20 })
    local E = red(0x81, 1, 0, { hp = 10 })
    local F = red(0x82, 5, 5)
    local o = {
        -- F strikes (0,0) from (-1,0) and (1,1) from (1,2); (2,0) is out of its reach
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 1 }, { 2, 0 }),
                  [0x82] = tiles({ -1, 0 }, { 1, 2 }) },
        danger = { ["0,0"] = 1, ["1,1"] = 1 },
        fc = { [0x01] = {
            [0x81] = {
                ["0,0"] = fc { hit = 90, dmg = 12, hits = 1, counters = true, counterHit = 100,
                               counterDmg = 30, counterHits = 1 },
                ["1,1"] = fc { hit = 40, dmg = 12, hits = 1 },
                ["2,0"] = fc { hit = 50, dmg = 12, hits = 1, counters = true, counterHit = 100,
                               counterDmg = 30, counterHits = 1 } },
            [0x82] = {
                ["0,0"] = fc { takenHit = 100, takenDmg = 15, takenHits = 1 },
                ["1,1"] = fc { takenHit = 100, takenDmg = 15, takenHits = 1 } } } },
    }
    local on = {}
    for _, c in ipairs(B.candidates(boardOf(A, E, F), sightOf(o), style("careful"))) do
        for _, a in ipairs(c.acts) do
            if a.act == "attack" then on[a.move.x .. "," .. a.move.y] = true end
        end
    end
    check(on["0,0"] and on["1,1"] and on["2,0"], true,
          "safest strike: the best, the counter-safe and the least exposed are all offered")
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

-- test_planner_records_the_counters_death_chance (#510 step 9, T012): A (20 HP) strikes X for
-- 20 without killing it, and X's counter (30, 15) answers. The attack act the plan plays
-- carries `die`, sight.odds on its counterDist at A's HP: zero here, as for every attack the
-- planner is offered, since Bot.candidates refuses one whose counter alone can kill. A
-- player-phase death after it is then a death the plan did not see (botrun's M.cause). The
-- judged phase names the striker of each player unit (`strikers`), not only of greens.
do
    local A = blue(0x01, 0, 0, 0, { hp = 20 })
    local X = red(0x81, 2, 0, { hp = 40 })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        fc = { [0x01] = { [0x81] = { ["1,0"] = fc { hit = 100, dmg = 20, hits = 1, counters = true,
                                                    counterHit = 30, counterDmg = 15,
                                                    counterHits = 1 } } } },
        enemyPhase = function(plan)
            local out = {}
            for _, b in ipairs(plan.blues) do
                out[#out + 1] = { target = b.unit.id, enemy = 0x81, takenHit = 0, takenDmg = 0,
                                  takenHits = 1, takenCrit = 0 }
            end
            return out
        end,
    }
    local a, plan = Planner.plan(B, boardOf(A, X), sightOf(o), style("bold"))
    check(a and a.act, "attack", "die: the plan strikes X")
    local want = a and a.f and (Sight.odds({ a.f.counterDist }, 20))
    check(a and a.die, want, "die: the counter's chance, from sight.odds on counterDist")
    check(want, 0, "die: a counter that cannot kill")
    check(plan and plan.acts[1].die, want, "die: kept in the plan record's acts")
    check(plan and plan.seizable, false, "no Seize offered")
    check(plan and plan.seizes, false, "and none taken")
    local mine
    for _, p in ipairs(plan and plan.predict or {}) do
        if p.id == 0x01 then mine = p end
    end
    check(mine and mine.strikers and mine.strikers[1], 0x81, "a blue unit's judged strikers")
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
    local fogged = after(A { acted = true }, C(), red(0x81, 2, 0, { hp = 10 }), red(0x82, 5, 5, { fogged = true }))
    check(S(plan(), 1, before, fogged), nil, "surprise: an enemy still in fog is no news")
    check(S(plan(), 1, before, after(A { acted = true }, C { acted = true }, red(0x81, 2, 0, { hp = 10 }))),
          "the next unit cannot act", "surprise: the next act is gone")
    check(S(plan(), 2, before, before), "the plan is played out", "surprise: nothing left to play")
    -- C's act is played on the game's word: sight.legal is asked of it, with C's live record
    -- (vanilla Ch3: a wall an earlier blow broke, a heal whose counter missed, each crashed)
    local played = after(A { acted = true }, C(), red(0x81, 2, 0, { hp = 10 }))
    local asked
    local function refuses(act, u) asked = { act = act, u = u }; return "the game offers no attack" end
    check(S(plan(), 1, before, played, refuses), "the game offers no attack",
          "surprise: the game no longer offers the next act")
    check(asked.act.unitId == 0x02 and asked.u.id == 0x02, true,
          "surprise: the game is asked about the next act, for its unit as it stands now")
    check(S(plan(), 1, before, played, nil, function() return nil end), nil,
          "surprise: the game still offers it, play on")
end

-- test_planner_pays_a_green_units_death (FR-012): X kills green G next phase unless A stands
-- on (1,0), which costs A ground toward its goal (`block`: (1,0)'s field, 20 at (0,0), MOV 5).
-- An allied green breaks ties only among plans within a turn of the most progress: at 0.8 of a
-- turn A blocks, and the plan predicts G's phase with it there; at four turns A keeps the
-- ground and G is lost.
local function greenBlock(block)
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local G = blue(0x30, 5, 3, 3, { faction = "green", hp = 10, minRange = false })
    local X = red(0x81, 9, 9, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        field = function() return { [0] = { [0] = 20, [1] = block } } end,
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.x == 1 then return {} end
            end
            return { { enemy = 0x81, target = 0x30, takenHit = 100, takenDmg = 99,
                       takenHits = 1, takenCrit = 0, targetHp = 10 } }
        end,
    }
    local a, plan = Planner.plan(B, boardOf(A, G, X), sightOf(o), style("careful"))
    local g
    for _, p in ipairs(plan and plan.predict or {}) do
        if p.id == 0x30 then g = p end
    end
    return at(a), g and g.green and g.die
end
do
    local a, die = greenBlock(24)
    check(a, "1,0", "planner: careful blocks for a green unit within a turn of progress")
    check(die, 0, "planner: the green unit's phase is predicted")
    a, die = greenBlock(40)
    check(a, "0,0", "planner: a green unit is no reason to lose four turns of progress")
    check(die, 1, "planner: and its death is predicted")
end

-- test_planner_mends_a_plan_that_loses_a_green_unit: A's march to (0,1) is its best act by its
-- own score, and the beam (BEAM = 1) keeps only that; X then kills green G. G has no menu of
-- its own, so the mend tries the player acts that could save it -- one ending beside it, or
-- striking one that strikes it -- and finds A's block at (1,0).
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local G = blue(0x30, 5, 2, 0, { faction = "green", hp = 10, minRange = false })
    local X = red(0x81, 9, 9, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }, { 0, 1 }) },
        -- the march gains 2 steps: within a turn, where a green's survival breaks the tie
        field = function()
            return { [0] = { [0] = 40, [1] = 40, [2] = 40 }, [1] = { [0] = 38 } }
        end,
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.x == 1 and b.y == 0 then return {} end
            end
            return { { enemy = 0x81, target = 0x30, takenHit = 100, takenDmg = 99,
                       takenHits = 1, takenCrit = 0, targetHp = 10 } }
        end,
    }
    local beam = Planner.BEAM
    Planner.BEAM = 1
    local a, plan = Planner.plan(B, boardOf(A, G, X), sightOf(o), style("careful"))
    Planner.BEAM = beam
    check(at(a) .. " " .. tostring(plan and plan.kind), "1,0 mend",
          "planner: the mend blocks for a green unit")
end

-- test_planner_mend_tries_each_act_once: greens G1 and G2 both stand beside (1,0), and only
-- A's block there saves them. Both are at risk and both offer it; it is judged once.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local G1 = blue(0x30, 5, 2, 0, { faction = "green", hp = 10, minRange = false })
    local G2 = blue(0x31, 6, 1, 1, { faction = "green", hp = 10, minRange = false })
    local X = red(0x81, 9, 9, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }, { 0, 2 }) },
        field = function()
            return { [0] = { [0] = 40, [1] = 40 }, [2] = { [0] = 38 } }
        end,
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.x == 1 and b.y == 0 then return {} end
            end
            return { { enemy = 0x81, target = 0x30, takenHit = 100, takenDmg = 99, takenHits = 1,
                       takenCrit = 0, targetHp = 10 },
                     { enemy = 0x81, target = 0x31, takenHit = 100, takenDmg = 99, takenHits = 1,
                       takenCrit = 0, targetHp = 10 } }
        end,
    }
    local beam = Planner.BEAM
    Planner.BEAM = 1
    local a, plan = Planner.plan(B, boardOf(A, G1, G2, X), sightOf(o), style("careful"))
    Planner.BEAM = beam
    local blocks = 0
    for _, c in ipairs(plan and plan.considered or {}) do
        if c.kind == "mend" and table.concat(c.acts, " "):find("@1,0") then blocks = blocks + 1 end
    end
    check(at(a), "1,0", "planner: the mend blocks for both")
    check(blocks, 1, "planner: the block is judged once")
end

-- test_planner_records_a_green_units_strikers: nothing saves G from X. The prediction names X
-- as its striker, and encodes: botrun logs the plan's record as JSON (string keys only).
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local G = blue(0x30, 5, 2, 0, { faction = "green", hp = 10, minRange = false })
    local X = red(0x81, 9, 9, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }) },
        enemyPhase = function()
            return { { enemy = 0x81, target = 0x30, takenHit = 100, takenDmg = 99,
                       takenHits = 1, takenCrit = 0, targetHp = 10 } }
        end,
    }
    local _, plan = Planner.plan(B, boardOf(A, G, X), sightOf(o), style("careful"))
    local g
    for _, p in ipairs(plan and plan.predict or {}) do
        if p.id == 0x30 then g = p end
    end
    check(g and table.concat(g.strikers, ","), tostring(0x81), "planner: the green's striker")
    check(pcall(Json.encode, plan and plan.predict), true, "planner: the predictions encode")
end

-- test_planner_pays_a_recruit_our_counter_kills: R (red) is a recruit, since the game lets A
-- Talk to it, but stands out of A's reach this turn. It strikes A at (0,0) and A's counter
-- kills it; at (1,0) A is out of its reach, which costs ground toward a village worth 10000
-- gold. A recruit killed is its goal lost for good (vanilla Ch5's Joshua, killed by Seth's
-- counter): a forfeit, which comes before progress (FR-011), so every style gives up the
-- ground. Where A has nowhere else to stand, the plan records R's chance to fall.
local function counterKillsRecruit(only)
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local R = red(0x81, 9, 9, { minRange = false })
    -- Y is the objective's nearest enemy, where (0,0) and (1,0) are about as near: the
    -- objective pulls neither way
    local Y = red(0x82, 0, 9, { minRange = false })
    local o = {
        reach = { [0x01] = only and tiles({ 0, 0 }) or tiles({ 0, 0 }, { 1, 0 }) },
        talk = { [0x01] = { [0x81] = true } },
        field = function(t)
            return (t.x ~= 0 or t.y ~= 9) and { [0] = { [0] = 20, [1] = 40 } } or nil
        end,
        explorable = { { x = 5, y = 0, kind = "visit" } },
        canExplore = { [0x01] = { ["5,0"] = "visit" } },
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.x == 1 then return {} end
            end
            return { { enemy = 0x81, target = 0x01, takenHit = 0, takenDmg = 0, takenHits = 1,
                       takenCrit = 0, targetHp = 20, felled = 1 } }
        end,
    }
    return boardOf(A, R, Y), o
end
do
    local board, o = counterKillsRecruit()
    local a = Planner.plan(B, board, sightOf(o), gifted("careful", 10000))
    check(at(a), "1,0", "planner: careful keeps out of a recruit's reach when its counter kills it")
    board, o = counterKillsRecruit()
    check(at(Planner.plan(B, board, sightOf(o), gifted("bold", 10000))), "1,0",
          "planner: bold too: a recruit's death is a forfeit, whatever the ground")
    board, o = counterKillsRecruit(true)
    local b, plan = Planner.plan(B, board, sightOf(o), gifted("bold", 10000))
    local r
    for _, p in ipairs(plan and plan.predict or {}) do
        if p.recruit then r = p end
    end
    check(at(b) .. " " .. tostring(r and r.id) .. " " .. tostring(r and r.die) .. " "
          .. tostring(r and table.concat(r.struck, ",")), "0,0 129 1 1",
          "planner: the recruit's chance to fall to A is recorded")
    check(plan and table.concat(plan.forfeited or {}, ","), "recruit:129",
          "planner: and the plan forfeits it")
    check(pcall(Json.encode, plan and plan.predict), true, "planner: a recruit's record encodes")
end

-- test_planner_mends_a_plan_that_kills_a_recruit: as above with BEAM = 1, so the beam keeps only
-- A's march to (0,0). R strikes A there and dies; R has no player menu, so the mend tries the
-- acts of the unit it strikes, A, and finds (1,0).
do
    local board, o = counterKillsRecruit()
    local beam = Planner.BEAM
    Planner.BEAM = 1
    local a, plan = Planner.plan(B, board, sightOf(o), style("careful"))
    Planner.BEAM = beam
    check(at(a) .. " " .. tostring(plan and plan.kind), "1,0 mend",
          "planner: the mend keeps A out of the recruit's reach")
end

-- test_planner_never_credits_killing_a_recruit: A can kill R from (1,0); C, far off, is the one
-- the game lets Talk to R, so R is a recruit. Its kill is paid as a death, not credited, so
-- careful does not attack it.
do
    local A = blue(0x01, 0, 0, 0)
    local C = blue(0x02, 1, 0, 5, { minRange = false })
    local R = red(0x81, 2, 0, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x02] = tiles({ 0, 5 }) },
        talk = { [0x02] = { [0x81] = true } },
        fc = { [0x01] = { [0x81] = { ["1,0"] = fc { hit = 100, dmg = 99, hits = 1,
                                                     killsTarget = true } } } },
        enemyPhase = function() return {} end,
    }
    local _, plan = Planner.plan(B, boardOf(A, C, R), sightOf(o), style("careful"))
    local attacks = false
    for _, x in ipairs(plan and plan.acts or {}) do
        attacks = attacks or (x.act == "attack" and x.targetId == 0x81)
    end
    check(attacks, false, "planner: no plan kills a recruit")
    -- C has acted (a replan after its move): R is still its recruit next turn
    C.acted = true
    _, plan = Planner.plan(B, boardOf(A, C, R), sightOf(o), style("careful"))
    attacks = false
    for _, x in ipairs(plan and plan.acts or {}) do
        attacks = attacks or (x.act == "attack" and x.targetId == 0x81)
    end
    check(attacks, false, "planner: a recruit whose talker has acted is still one")
end

-- test_planner_judges_a_talk_with_the_recruit_off_the_enemy_side: A Talks R over from (1,0). R
-- joins us, so the judged phase has no strike from it: the phase is played with R gone, and A's
-- predicted chance to die there is nothing.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local R = red(0x81, 2, 0, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        talk = { [0x01] = { [0x81] = true } },
        enemyPhase = function(plan)
            if (plan.gone or {})[0x81] then return {} end
            return { { enemy = 0x81, target = 0x01, takenHit = 100, takenDmg = 99, takenHits = 1,
                       takenCrit = 0, targetHp = 20 } }
        end,
    }
    local a, plan = Planner.plan(B, boardOf(A, R), sightOf(o), style("careful"))
    local die
    for _, p in ipairs(plan and plan.predict or {}) do
        if p.id == 0x01 then die = p.die end
    end
    check(tostring(a and a.act) .. " " .. tostring(die), "talk 0",
          "planner: a talked-over recruit does not strike in the judged phase")
end

-- test_planner_protects_a_game_over_unit: L's death quote ends the game
-- (sight.objective.gameOver). Where L stands, X strikes it at even odds; at (1,0) L takes X's
-- strike off C, who then dies for sure. Both plans are over careful's cap. A game over is not
-- one more risk: it ends the chapter (Nicolas, 2026-11-01, ADR 0384), so the fallback with the
-- smaller chance of it comes first, whatever the excess: L moves.
do
    local L = blue(0x01, 0, 0, 0, { minRange = false })
    local C = blue(0x02, 1, 0, 5, { minRange = false })
    local X = red(0x81, 9, 9, { minRange = false })
    local o = {
        objective = { kind = "rout", gameOver = { 0x01 } },
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x02] = tiles({ 0, 5 }) },
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.unit.id == 0x01 and b.x == 1 then
                    return { { enemy = 0x81, target = 0x02, takenHit = 100, takenDmg = 99,
                               takenHits = 1, takenCrit = 0, targetHp = 20 } }
                end
            end
            return { { enemy = 0x81, target = 0x01, takenHit = 50, takenDmg = 99, takenHits = 1,
                       takenCrit = 0, targetHp = 20 } }
        end,
    }
    local a, plan = Planner.plan(B, boardOf(L, C, X), sightOf(o), style("careful"))
    local moved
    for _, x in ipairs(plan and plan.acts or {}) do
        if x.unitId == 0x01 then moved = at(x) end
    end
    check(moved, "1,0", "planner: over the cap, the smaller chance of a game over first")
    check(plan and plan.fallback, "FALLBACK_SACRIFICE", "planner: and labelled")
end

-- test_planner_plays_an_uncertain_kill_both_ways: L can attack E from (1,0), killing it 40%
-- of the time. Standing, E holds J off; dead, it frees J to strike L there for sure, and L's
-- death ends the game. The average keeps E standing (kill < 0.5), so only the branch where the
-- kill lands shows the risk (vanilla Ch5 turn 5: Eirika's kill turned Joshua on her). L waits.
do
    local L = blue(0x01, 0, 0, 0)
    local E = red(0x81, 2, 0, { minRange = false, hp = 10 })
    local J = red(0x82, 9, 9, { minRange = false })
    local o = {
        objective = { kind = "rout", gameOver = { 0x01 } },
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        fc = { [0x01] = { [0x81] = { ["1,0"] = fc { hit = 40, dmg = 10, hits = 1 } } } },
        enemyPhase = function(plan)
            local atOne = false
            for _, b in ipairs(plan.blues) do
                if b.unit.id == 0x01 and b.x == 1 then atOne = true end
            end
            if atOne and (plan.gone or {})[0x81] then
                return { { enemy = 0x82, target = 0x01, takenHit = 100, takenDmg = 99,
                           takenHits = 1, takenCrit = 0, targetHp = 20 } }
            end
            return {}
        end,
    }
    local _, plan = Planner.plan(B, boardOf(L, E, J), sightOf(o), style("careful"))
    local attacks = false
    for _, x in ipairs(plan and plan.acts or {}) do attacks = attacks or x.act == "attack" end
    check(attacks, false, "planner: a kill that may free a striker on the lord is played both ways")
end

-- test_planner_composes_a_targets_blows_before_branching: A and C each hit E (20 HP) for 10 at
-- 50%. Together they kill it a quarter of the time (both land), and when it lives it keeps
-- 13 HP on average ((0 x 1/4 + 10 x 1/2) / (3/4) taken). Read one blow at a time, at the HP
-- the first leaves on average (15), neither kills and the judge never plays E dead.
do
    local A = blue(0x01, 0, 0, 0)
    local C = blue(0x02, 1, 2, 1)
    local E = red(0x81, 1, 1, { minRange = false, hp = 20 })
    local blow = fc { hit = 50, dmg = 10, hits = 1 }
    local seen = {}
    local o = {
        reach = { [0x01] = tiles({ 1, 0 }), [0x02] = tiles({ 1, 2 }) },
        fc = { [0x01] = { [0x81] = { ["1,0"] = blow } }, [0x02] = { [0x81] = { ["1,2"] = blow } } },
        enemyPhase = function(plan)
            local both = 0
            for _, b in ipairs(plan.blues) do
                if b.slot then both = both + 1 end
            end
            if both == 2 then
                seen[(plan.gone or {})[0x81] and "dead" or tostring((plan.reds or {})[0x81])] = true
            end
            return {}
        end,
    }
    Planner.plan(B, boardOf(A, C, E), sightOf(o), style("bold"))
    check(tostring(seen.dead) .. " " .. tostring(seen["13"]), "true true",
          "planner: two blows on one target are played dead and alive at 13 HP")
end

-- test_planner_prices_a_game_over_greens_death_as_the_chapter: as the green test above, in
-- bold, which pays one death (60) less than the ground toward a village of 10000 gold the
-- block costs. When G's death ends the game (an escort: sight.objective.gameOver names it),
-- its death is the chapter, and A blocks.
do
    local function play(gameOver)
        local A = blue(0x01, 0, 0, 0, { minRange = false })
        local G = blue(0x30, 5, 3, 3, { faction = "green", hp = 10, minRange = false })
        local X = red(0x81, 0, 9, { minRange = false })
        local o = {
            objective = { kind = "rout", gameOver = gameOver },
            -- (0,1) is the march toward the village, (1,0) the block
            reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }, { 0, 1 }) },
            field = function(t)
                return t.x == 5 and t.y == 0
                    and { [0] = { [0] = 20, [1] = 40 }, [1] = { [0] = 15 } } or nil
            end,
            explorable = { { x = 5, y = 0, kind = "visit" } },
            canExplore = { [0x01] = { ["5,0"] = "visit" } },
            enemyPhase = function(plan)
                for _, b in ipairs(plan.blues) do
                    if b.x == 1 then return {} end
                end
                return { { enemy = 0x81, target = 0x30, takenHit = 100, takenDmg = 99,
                           takenHits = 1, takenCrit = 0, targetHp = 10 } }
            end,
        }
        local a, plan = Planner.plan(B, boardOf(A, G, X), sightOf(o), gifted("bold", 10000))
        return at(a), plan
    end
    check(play({}) .. " " .. play({ 0x30 }), "0,1 1,0",
          "planner: a green whose death ends the game costs the chapter")
    -- (FR-012, plan T046) it is protected, so the cap keeps it, and its death forfeits no goal:
    -- a game over is admission's to weigh, not the ledger's (Nicolas, 2026-11-02)
    local _, plan = play({ 0x30 })
    local open
    for _, c in ipairs(plan and plan.considered or {}) do
        if table.concat(c.acts, " "):find("@0,0") then open = c.rank end
    end
    check(open and tostring(open.admitted) .. " " .. open.forfeits, "false 0",
          "planner: a game-over green's death is over the cap, and no forfeit")
end

-- The seize board the rank tests below share. It sets only the gate at (10,0), no enemy phase
-- and, given `mover`, that unit's march: reach to (0,0), (1,0) and (2,0). Each is set only
-- where `o` leaves it unset; forecasts, staves and heals are the test's to give. `o` is
-- copied, never written.
local function seizeSight(o, mover)
    local s = {}
    for k, v in pairs(o) do s[k] = v end
    s.objective = s.objective or { kind = "seize", tile = { x = 10, y = 0 } }
    s.enemyPhase = s.enemyPhase or function() return {} end
    if mover then s.reach = s.reach or { [mover] = tiles({ 0, 0 }, { 1, 0 }, { 2, 0 }) } end
    return sightOf(s)
end

-- test_a_march_beats_a_chip_a_step_back (ADR 0384's panel amendment, research record 0024): A
-- can strike X for 20 of its 40 HP from (1,0), a step toward the gate, or march two steps to
-- (2,0). Both are within a turn of the most progress, and progress comes before the judged
-- score: the march. (Under the order this replaced, the test expected the strike.)
do
    local A = blue(0x01, 0, 0, 0)
    local X = red(0x81, 1, 1, { hp = 40, minRange = false })
    local sight = seizeSight({
        fc = { [0x01] = { [0x81] = { ["1,0"] = fc { hit = 100, dmg = 20, hits = 1 } } } },
    }, 0x01)
    local a = Planner.plan(B, boardOf(A, X), sight, style("bold"))
    check(a and a.act .. "@" .. at(a), "wait@2,0", "rank: the march beats the chip a step back")
end

-- test_a_march_beats_a_heal_a_step_back (ADR 0384's panel amendment): a heal is the judged
-- score too, so the order holds for it. H can heal W from (1,0), or march to (2,0): it marches.
do
    local H = blue(0x02, 0, 0, 0, { minRange = false })
    local W = blue(0x03, 1, 1, 1, { hp = 5, maxhp = 30, minRange = false, acted = true })
    local sight = seizeSight({
        staves = { [0x02] = { { slot = 0, amount = 10 } } },
        heals = { [0x02] = { ["1,0"] = { { slot = 0, amount = 10, targets = { 0x03 } } } } },
    }, 0x02)
    local a = Planner.plan(B, boardOf(H, W), sight, style("careful"))
    check(a and a.act .. "@" .. at(a), "wait@2,0", "rank: the march beats the heal a step back")
end

-- test_a_march_beats_a_kill_a_step_back (ADR 0384's panel amendment): a kill is the judged score
-- too. A can kill X (20 HP, a sure 20) from (1,0), or march to (2,0): it marches.
do
    local A = blue(0x01, 0, 0, 0)
    local X = red(0x81, 1, 1, { hp = 20, minRange = false })
    local sight = seizeSight({
        fc = { [0x01] = { [0x81] = { ["1,0"] = fc { hit = 100, dmg = 20, hits = 1 } } } },
    }, 0x01)
    local a = Planner.plan(B, boardOf(A, X), sight, style("careful"))
    check(a and a.act .. "@" .. at(a), "wait@2,0", "rank: the march beats the kill a step back")
end

-- test_the_chip_is_kept_from_the_forward_tile (ADR 0384's panel amendment): A can strike X for
-- 20 of its 40 HP from (2,0), its march's tile, and take a 5 back, or wait there. Progress
-- ties, so the judged score decides: the chip. Without it the wait would win, as neither can
-- die (the death chances tie) and the wait keeps more HP (the tie after them).
do
    local A = blue(0x01, 0, 0, 0)
    local X = red(0x81, 2, 1, { hp = 40, minRange = false })
    local sight = seizeSight({
        fc = { [0x01] = { [0x81] = { ["2,0"] = fc { hit = 100, dmg = 20, hits = 1, counters = true,
                                                    counterHit = 100, counterDmg = 5,
                                                    counterHits = 1 } } } },
    }, 0x01)
    local a = Planner.plan(B, boardOf(A, X), sight, style("careful"))
    check(a and a.act .. "@" .. at(a), "attack@2,0", "rank: the chip from the march's tile")
end

-- test_rebase_measures_turns_behind_the_best (FR-012): progress 1.6, 0.8 and 0 are 0, 0 and 1
-- whole turns behind the best, and the best of those `ok` allows is returned.
do
    local ranks = {}
    for i, p in ipairs({ 0, 0.8, 1.6 }) do
        ranks[i] = { admitted = true, forfeits = 0, complete = 0, green_die = 0, progress = p,
                     value = 0, game_over = 0, max_exceed = 0, sum_exceed = 0, max_die = 0,
                     sum_die = 0, hp_left = 0, key = tostring(i) }
    end
    local best = Planner.rebase(ranks)
    check(ranks[1].behind .. ranks[2].behind .. ranks[3].behind .. " " .. best, "100 3",
          "rebase: whole turns behind the most progress, and the best")
    check(Planner.rebase(ranks, function(i) return i ~= 3 end), 2, "rebase: the best allowed")
    check(ranks[1].behind .. ranks[2].behind, "00",
          "rebase: a plan that may not be played is no measure of progress")
end

-- test_the_advance_gives_way_on_a_shared_tile (FR-016): U1 and U2 both gain the most ground at
-- (3,0); U1, first, takes it, and U2's advance falls to its next tile forward, (2,1), not to
-- a hold. U2 is slow (MOV 2), so (3,0) is worth more turns to it: the beam's one plan gives it
-- U2, and only the advance has U1 there and U2 at (2,1).
do
    local U1 = blue(0x01, 0, 0, 0, { minRange = false })
    local U2 = blue(0x02, 1, 1, 1, { minRange = false, mov = 2 })
    local Z = red(0x83, 14, 9, { minRange = false })
    local sight = seizeSight({
        reach = { [0x01] = tiles({ 0, 0 }, { 3, 0 }), [0x02] = tiles({ 1, 1 }, { 3, 0 }, { 2, 1 }) },
    })
    local beam = Planner.BEAM
    Planner.BEAM = 1
    local _, plan = Planner.plan(B, boardOf(U1, U2, Z), sight, style("bold"))
    Planner.BEAM = beam
    local adv
    for _, c in ipairs(plan and plan.considered or {}) do
        if c.kind == "advance" then adv = table.concat(c.acts, " ") end
    end
    check(adv, "1>wait@3,0>nil 2>wait@2,1>nil", "advance: the second unit takes its next tile")
end

-- test_with_none_under_the_cap_the_mend_changes_more_than_one_unit (#510 PR A): X kills A
-- unless A stands at (1,0) and B unless B stands at (1,4). Every plan the beam and the advance
-- build has both at home; one mend saves one of them; only a second round, from
-- the mended plan, saves both, and that plan is under the cap.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local Bu = blue(0x02, 1, 0, 4, { minRange = false })
    local X = red(0x81, 0, 9, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x02] = tiles({ 0, 4 }, { 1, 4 }) },
        enemyPhase = function(plan)
            local out = {}
            for _, b in ipairs(plan.blues) do
                if b.x ~= 1 then
                    out[#out + 1] = { target = b.unit.id, takenHit = 80, takenDmg = 99,
                                      takenHits = 1, takenCrit = 0 }
                end
            end
            return out
        end,
    }
    local beam = Planner.BEAM
    Planner.BEAM = 1
    local a, plan = Planner.plan(B, boardOf(A, Bu, X), sightOf(o), style("careful"))
    Planner.BEAM = beam
    local acts = {}
    for _, x in ipairs(plan and plan.acts or {}) do acts[#acts + 1] = x.unitId .. "@" .. at(x) end
    table.sort(acts)
    check(table.concat(acts, " "), "1@1,0 2@1,4", "mend rounds: both units moved to safety")
    check(plan and plan.fallback, nil, "mend rounds: under the cap, no fallback")
    local sb = plan and plan.audit and plan.audit.mend_rounds or {}
    check(tostring(sb.before) .. " " .. tostring(sb.now), "false true",
          "mend rounds: the audit says the planner before had none under the cap")
end

-- test_fog_ranks_and_does_not_gate (#510 PR A step 4, as reworked: comment 6780781911): a
-- unit ending beside unseen ground meets one strike from the strongest enemy seen so far, stood
-- on the nearest unseen tile (sight.fogStrike). Here that strike kills A half the time from
-- (0,0), three tiles from the fog; (0,9) is out of FOG_REACH. The strike is its own rank key
-- (`fog`), never A's chance to die: the plan beside the fog is still under the cap, and careful
-- walks away from the fog only because the fog key ranks it after (0,9). An enemy never seen
-- (opts.seen) is no one's strongest.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local X = red(0x81, 9, 9, { minRange = false })
    local Y = red(0x82, 9, 8, { minRange = false, fogged = true })
    local asked = {}
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 0, 9 }) },
        unseen = { { x = 3, y = 0 }, { x = 14, y = 0 } },
        fogStrike = function(u, e, x, y, fx, fy)
            asked[#asked + 1] = string.format("%X@%d,%d<%d,%d", e.id, x, y, fx, fy)
            return { takenDist = { [0] = 0.5, [99] = 0.5 } }
        end,
        enemyPhase = function() return {} end,
    }
    local a, plan = Planner.plan(B, boardOf(A, X, Y), sightOf(o), style("careful"),
                                 { seen = { [0x81] = 0x81 } })
    check(at(a), "0,9", "fog: careful steps away from the unseen")
    local rank
    for _, c in ipairs(plan and plan.considered or {}) do
        if c.acts[1] == "1>wait@0,0>nil" then rank = c.rank end
    end
    check(rank and rawget(rank, "fog"), 0.5,
          "fog: beside it, the strike's chance to kill is the fog key, read before any sort")
    check(rank and rank.max_die, 0, "fog: not the unit's chance to die")
    check(rank and rank.admitted, true, "fog: the cap reads the enemies in sight only")
    local others = {}
    for _, q in ipairs(asked) do
        if not q:find("^81@") then others[#others + 1] = q end
    end
    check(#asked > 0 and #others, 0, "fog: only the enemy seen so far is asked")
    check(asked[1] and asked[1]:match("<(.*)$"), "3,0", "fog: from the nearest unseen tile")
end

-- test_the_fog_key_breaks_ties_only (#510 PR A step 4, Nicolas 2026-11-10): the fog read
-- orders plans only after everything else the rank reads (goals, the win, progress, value),
-- under the cap and over it.
do
    local function r(t)
        local base = { admitted = true, forfeits = 0, complete = 0, behind = 0, green_die = 0,
                       progress = 0, value = 0, game_over = 0, first_game_over = 0,
                       max_exceed = 0, sum_exceed = 0, first_max_exceed = 0,
                       first_sum_exceed = 0, max_die = 0, sum_die = 0, hp_left = 0, fog = 0,
                       key = "a" }
        for k, v in pairs(t) do base[k] = v end
        return base
    end
    check(Planner.outranks(r { fog = 0.3, progress = 5, key = "b" }, r { fog = 0.1, progress = 0 }),
          true, "fog key: more progress outranks less fog")
    check(Planner.outranks(r { fog = 0.3, value = 5, key = "b" }, r { fog = 0.1 }), true,
          "fog key: after the value")
    check(Planner.outranks(r { fog = 0.1, key = "b" }, r { fog = 0.3 }), true,
          "fog key: alike otherwise, less fog first")
    check(Planner.outranks(r { admitted = false, fog = 0.9, first_max_exceed = 0.1,
                               max_exceed = 0.1 },
                           r { admitted = false, fog = 0, first_max_exceed = 0.2,
                               max_exceed = 0.2, key = "b" }), true,
          "fog key: over the cap, after the seen excess")
end

-- test_under_fog_the_threatened_move_last (#510 PR A's fog rule): A ends beside the fog and
-- its strike may kill it; U ends far from it. U's act is played first, so what U shows of the
-- fog is seen before A moves (botrun replans on a newly seen enemy).
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local U = blue(0x02, 1, 0, 9, { minRange = false })
    local X = red(0x81, 14, 9, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 0, 1 }), [0x02] = tiles({ 0, 9 }, { 1, 9 }) },
        unseen = { { x = 2, y = 0 } },
        fogStrike = function(u) return { takenDist = { [0] = 0.99, [99] = 0.01 } } end,
        enemyPhase = function() return {} end,
    }
    local a, plan = Planner.plan(B, boardOf(A, U, X), sightOf(o), style("bold"))
    check(a and a.unitId, 0x02, "fog order: the unit far from the fog acts first")
    check(plan and plan.acts[#plan.acts].unitId, 0x01, "fog order: the threatened one last")
    local played
    for _, c in ipairs(plan and plan.considered or {}) do
        if c.played then played = c.acts end
    end
    check(played and played[#played] and played[#played]:match("^(%d+)>"), "1",
          "fog order: the record's keys are in the order played")
    check(plan and plan.rank.key, table.concat(played or {}, " "),
          "fog order: the rank's key names the plan as played")
end

-- test_the_fog_read_asks_a_free_tile_and_the_highest_level (#510 PR A, review of #598): the
-- strike comes from the nearest unseen tile no unit holds (a hidden unit's tile would put two
-- units on one cell), and of two seen enemies with one class and kit the higher level is asked.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local X = red(0x81, 9, 9, { minRange = false, level = 3 })
    local Y = red(0x82, 9, 8, { minRange = false, level = 9 })
    local H = red(0x83, 2, 0, { minRange = false, fogged = true, classId = 99 })
    local asked = {}
    local s = sightOf({
        unseen = { { x = 2, y = 0 }, { x = 3, y = 0 } },
        fogStrike = function(u, e, x, y, fx, fy)
            asked[#asked + 1] = string.format("%X<%d,%d", e.id, fx, fy)
            return { takenDist = { [0] = 1 } }
        end,
    })
    B.fogRead(boardOf(A, X, Y, H), s, { [0x81] = 0x81, [0x82] = 0x82 }).die(A, 0, 0, 20)
    check(table.concat(asked, " "), "82<3,0", "fog read: the free tile, the higher level")
    -- the seen enemy itself hidden on the nearest unseen tile: asked from its own tile
    asked = {}
    local Z = red(0x84, 2, 0, { minRange = false, fogged = true, level = 20, classId = 5 })
    B.fogRead(boardOf(A, X, Z), s, { [0x81] = 0x81, [0x84] = 0x84 }).die(A, 0, 0, 20)
    table.sort(asked)
    check(table.concat(asked, " "), "81<3,0 84<2,0", "fog read: an enemy's own tile is free to it")
end

-- test_a_replan_judges_the_rest_of_the_plan_in_hand: on a replan botrun hands the planner the
-- acts of the plan in hand not yet played (opts.rest). The beam (one plan wide) and the advance
-- never build U2 holding at (1,1) with U1 marching to (3,0); handed those acts, the planner
-- judges that plan too, kind "rest". An act this board no longer offers is dropped and its
-- unit holds; a rest the other plans already hold is not judged twice. (Vanilla Ch6 seed 1001
-- turn 4: the replan after a counter judged 4 plans, every one 30.8% or more to end the game,
-- and the rest of the plan in hand, replayed, lost no lord.)
do
    local U1 = blue(0x01, 0, 0, 0, { minRange = false })
    local U2 = blue(0x02, 1, 1, 1, { minRange = false, mov = 2 })
    local Z = red(0x83, 14, 9, { minRange = false })
    local sight = seizeSight({
        reach = { [0x01] = tiles({ 0, 0 }, { 3, 0 }), [0x02] = tiles({ 1, 1 }, { 3, 0 }, { 2, 1 }) },
    })
    local function judged(rest)
        local beam = Planner.BEAM
        Planner.BEAM = 1
        local _, plan = Planner.plan(B, boardOf(U1, U2, Z), sight, style("bold"), { rest = rest })
        Planner.BEAM = beam
        local out = {}
        for _, c in ipairs(plan and plan.considered or {}) do
            out[#out + 1] = c.kind .. ": " .. table.concat(c.acts, " ")
        end
        table.sort(out)
        return table.concat(out, " | ")
    end
    local plain = judged(nil)
    check(plain:find("1>wait@3,0>nil 2>wait@1,1>nil", 1, true)
          or plain:find("2>wait@1,1>nil 1>wait@3,0>nil", 1, true), nil,
          "rest: no other plan holds U2 at (1,1) with U1 marching")
    check(judged({ "2>wait@1,1>nil", "1>wait@3,0>nil" }),
          plain .. " | rest: 2>wait@1,1>nil 1>wait@3,0>nil",
          "rest: the plan in hand is judged too, in its order")
    check(judged({ "1>wait@5,5>nil", "2>wait@1,1>nil" }),
          plain .. " | rest: 2>wait@1,1>nil 1>wait@0,0>nil",
          "rest: an act no longer offered is dropped, and its unit holds")
    check(judged({ "2>wait@3,0>nil", "1>wait@0,0>nil" }), plain,
          "rest: a plan already judged is not judged twice")
end

-- test_a_visit_comes_before_the_win (SC-002, plan T047): the lord can Seize now, or Visit a
-- village in reach first. The Seize would close the village: one forfeit, which the Visit
-- does not have, so the Visit is played and the Seize waits.
do
    local L = blue(0x01, 0, 4, 3, { charId = 0x0F, minRange = false })
    local Z = red(0x83, 14, 14, { minRange = false })
    local o = {
        objective = { kind = "seize", tile = { x = 4, y = 4 }, lord = 0x0F },
        reach = { [0x01] = tiles({ 4, 3 }, { 4, 4 }, { 4, 2 }) },
        -- the game's field to the village, which sends the lord there (exploring)
        field = function(t)
            return t.x == 4 and t.y == 2
                and { [2] = { [4] = 0 }, [3] = { [4] = 1 }, [4] = { [4] = 2 } } or nil
        end,
        explorable = { { x = 4, y = 2, kind = "visit" } },
        canExplore = { [0x01] = { ["4,2"] = "visit" } },
        enemyPhase = function() return {} end,
    }
    local a, plan = Planner.plan(B, boardOf(L, Z), sightOf(o), gifted("bold", 100))
    check(a and a.act, "visit", "visit before win: the Visit is played")
    local seize
    for _, c in ipairs(plan and plan.considered or {}) do
        if c.seizes then seize = c.rank end
    end
    check(seize and seize.forfeits .. " " .. seize.complete, "1 1",
          "visit before win: the Seize forfeits the village")
    check(plan and plan.seizable and plan.seizeAdmitted and not plan.seizes, true,
          "visit before win: a Seize under the cap was judged and not played")
    check(plan and plan.ledger[1] and plan.ledger[1].id .. " " .. plan.ledger[1].status,
          "visit:4,2 feasible", "visit before win: the ledger the plan leaves")
end

-- test_a_stalled_goal_does_not_hold_the_win (#510 fwd1 item C, call 3, ADR 0403): the same board
-- as the visit above, but botrun reports the village's id in opts.quietGoals (no unit neared it
-- for a while). Its row is stalled, the Seize forfeits nothing, and it is played; the plan's
-- ledger and its `nearest` still name the village.
do
    local L = blue(0x01, 0, 4, 3, { charId = 0x0F, minRange = false })
    local Z = red(0x83, 14, 14, { minRange = false })
    local o = {
        objective = { kind = "seize", tile = { x = 4, y = 4 }, lord = 0x0F },
        reach = { [0x01] = tiles({ 4, 3 }, { 4, 4 }, { 4, 2 }) },
        field = function(t)
            return t.x == 4 and t.y == 2
                and { [2] = { [4] = 0 }, [3] = { [4] = 1 }, [4] = { [4] = 2 } } or nil
        end,
        explorable = { { x = 4, y = 2, kind = "visit" } },
        canExplore = { [0x01] = { ["4,2"] = "visit" } },
        enemyPhase = function() return {} end,
    }
    local a, plan = Planner.plan(B, boardOf(L, Z), sightOf(o), gifted("bold", 100),
                                 { quietGoals = { ["visit:4,2"] = true } })
    check(a and a.act, "seize", "stalled goal: the Seize is played")
    check(plan and plan.ledger[1] and plan.ledger[1].id .. " " .. plan.ledger[1].status,
          "visit:4,2 stalled", "stalled goal: the ledger names a stalled row")
    check(plan and plan.nearest[2] and plan.nearest[2].id, "visit:4,2",
          "stalled goal: its turns are still read (a new low makes it feasible again)")
    -- none of the beam's plans is judged (FINAL = 0: the beam kept no Seize, as on vanilla Ch8):
    -- the Seize is judged all the same, and the rank plays it
    local final = Planner.FINAL
    Planner.FINAL = 0
    local a1, p1 = Planner.plan(B, boardOf(L, Z), sightOf(o), gifted("bold", 100),
                                { quietGoals = { ["visit:4,2"] = true } })
    Planner.FINAL = final
    local kind
    for _, c in ipairs(p1 and p1.considered or {}) do
        if c.seizes then kind = c.kind end
    end
    check((a1 and a1.act) .. " " .. tostring(kind), "seize seize",
          "stalled goal: the Seize is judged though the beam cut it")
end

-- test_the_seize_is_played_when_every_other_plan_is_over_the_cap (#510 fwd1 item C, ADR 0403):
-- the board of the visit above, but the enemy phase kills the lord on every tile except the
-- objective's (the Seize ends the chapter before it strikes). The Seize forfeits the open
-- village, yet it is the only admitted plan, and admission outranks forfeits: it is played.
do
    local L = blue(0x01, 0, 4, 3, { charId = 0x0F, minRange = false })
    local Z = red(0x83, 14, 14, { minRange = false })
    local o = {
        objective = { kind = "seize", tile = { x = 4, y = 4 }, lord = 0x0F },
        reach = { [0x01] = tiles({ 4, 3 }, { 4, 4 }, { 4, 2 }) },
        field = function(t)
            return t.x == 4 and t.y == 2
                and { [2] = { [4] = 0 }, [3] = { [4] = 1 }, [4] = { [4] = 2 } } or nil
        end,
        explorable = { { x = 4, y = 2, kind = "visit" } },
        canExplore = { [0x01] = { ["4,2"] = "visit" } },
        enemyPhase = function(plan)
            local b = plan.blues[1]
            if b.x == 4 and b.y == 4 then return {} end
            return { { target = b.unit.id, takenHit = 80, takenDmg = 99, takenHits = 1,
                       takenCrit = 0 } }
        end,
    }
    local a, plan = Planner.plan(B, boardOf(L, Z), sightOf(o), gifted("careful", 100))
    local seize
    for _, c in ipairs(plan and plan.considered or {}) do
        if c.seizes then seize = c.rank end
    end
    check(a and a.act, "seize", "seize over the cap: the Seize is played")
    check(seize and seize.forfeits .. " " .. tostring(seize.admitted), "1 true",
          "seize over the cap: it forfeits the open village and is admitted")
    local other
    for _, c in ipairs(plan and plan.considered or {}) do
        if not c.seizes and c.rank.admitted then other = true end
    end
    check(other, nil, "seize over the cap: no other judged plan is under the cap")
end

-- test_no_enemy_phase_is_judged_after_the_seize (#510 fwd1 item D, ADR 0405): the lord can
-- Seize, and the enemy phase would kill T wherever it stands. The Seize ends the chapter
-- before that phase (vanilla Ch8, run goal8b, campaign 4001 turn 19: the Seize plan read the
-- thief's 63.5% and was over the cap, the thief died and the win came a turn later). So the
-- plan that seizes is under the cap and played.
do
    local L = blue(0x01, 0, 4, 3, { charId = 0x0F, minRange = false })
    local T = blue(0x02, 1, 0, 9, { minRange = false })
    local Z = red(0x83, 14, 14, { minRange = false })
    local o = {
        objective = { kind = "seize", tile = { x = 4, y = 4 }, lord = 0x0F },
        reach = { [0x01] = tiles({ 4, 3 }, { 4, 4 }) },
        enemyPhase = function(plan)
            local out = {}
            for _, b in ipairs(plan.blues) do
                if b.unit.id == 0x02 then
                    out[#out + 1] = { target = 0x02, takenHit = 80, takenDmg = 99, takenHits = 1,
                                      takenCrit = 0 }
                end
            end
            return out
        end,
    }
    local a, plan = Planner.plan(B, boardOf(L, T, Z), sightOf(o), style("careful"))
    check((a and a.act) .. " " .. tostring(plan and plan.rank.admitted), "seize true",
          "seize: no enemy phase is judged after it")
    -- nor a second one: on the deep diagnostic every finalist meets the lookahead's phase,
    -- which kills T too. The plan that seizes is never asked it and keeps its rank
    o.nextPhase = o.enemyPhase
    local sight = sightOf(o)
    a, plan = Planner.plan(B, boardOf(L, T, Z), sight, style("careful"), { diag = "deep" })
    check((a and a.act) .. " " .. tostring(plan and plan.rank.admitted) .. " "
          .. tostring(plan and plan.rank.max_die) .. " " .. tostring(#(sight.asked or {}) > 0),
          "seize true 0 true", "seize: nor is the lookahead's second phase")
end

-- test_the_rank_sees_an_offered_goal_act (#510 fwd1 item D's planner item, ADR 0405): U can
-- take a goal at or from (4,2), a step away from the gate, and none of the beam's plans is
-- judged (FINAL = 0: the beam cut the act, as it cut the Talk on vanilla Ch9 turn 11). A plan
-- with the act is judged all the same, its other acts the first plan's (V's march). With the
-- beam's plans judged and the act in one of them, no second plan is built for it. A stalled
-- row gets its plan too, and of two units offered one goal the plan has the better by its own
-- score.
do
    -- the goal plans judged on the shared board, as key lists, and how many. `o` is the
    -- sight's options, `final` Planner.FINAL for the call (nil: the beam's plans are judged
    -- and U is alone, so the beam keeps each of its three acts), `more` the units besides U.
    local function judged(want, o, final, st, opts, ...)
        local U = blue(0x01, 0, 4, 3, { minRange = false })
        local Z = red(0x83, 14, 14, { minRange = false })
        o.objective = { kind = "seize", tile = { x = 4, y = 9 } }
        o.reach = o.reach or { [0x01] = tiles({ 4, 3 }, { 4, 4 }, { 4, 2 }),
                               [0x02] = tiles({ 0, 0 }, { 0, 1 }) }
        o.enemyPhase = function() return {} end
        local was = Planner.FINAL
        Planner.FINAL = final or was
        local _, plan = Planner.plan(B, boardOf(U, Z, ...), sightOf(o), st or style("bold"), opts)
        Planner.FINAL = was
        local goal, n = nil, 0
        for _, c in ipairs(plan and plan.considered or {}) do
            if c.kind == want then goal, n = table.concat(c.acts, " "), n + 1 end
        end
        return goal, n
    end
    local function V() return blue(0x02, 1, 0, 0, { minRange = false }) end
    for _, kind in ipairs({ "visit", "chest" }) do
        local function o()
            return { explorable = { { x = 4, y = 2, kind = kind } },
                     canExplore = { [0x01] = { ["4,2"] = kind } } }
        end
        check(judged("goal", o(), 0, nil, nil, V()), "1>" .. kind .. "@4,2>nil 2>wait@0,1>nil",
              "goal act: the " .. kind .. " the beam cut is judged, the rest the first plan's")
        check(select(2, judged("goal", o())), 0,
              "goal act: a " .. kind .. " a judged plan already holds gets no second plan")
        -- item E1 (#510): the act is judged with every other unit holding too, since the first
        -- plan's other acts can put it over the cap by themselves (vanilla Ch9, campaign 4006
        -- turn 11: the Talk plan at 87.2% was another unit's attack across the map)
        check(select(2, judged("lone", o(), 0)), 0,
              "goal act alone: no lone plan when the goal plan is already the act alone")
        check(judged("lone", o(), 0, nil, nil, V()), "1>" .. kind .. "@4,2>nil 2>wait@0,0>nil",
              "goal act alone: the " .. kind .. " is judged with every other unit holding")
        check(judged("goal", o(), 0, nil, { quietGoals = { [kind .. ":4,2"] = true } }, V()),
              "1>" .. kind .. "@4,2>nil 2>wait@0,1>nil",
              "goal act: a stalled " .. kind .. " the game offers is judged too")
    end
    -- a Talk to the recruit T, from beside it
    check(judged("goal", { talk = { [0x01] = { [0x30] = true } } }, 0,
                 claimed("bold", { id = "r1", kind = "recruit", unit = { 0x30 } }), nil, V(),
                 blue(0x30, 5, 4, 1, { faction = "green", minRange = false })),
          "1>talk@4,2>48 2>wait@0,1>nil", "goal act: the Talk the beam cut is judged")
    -- U and W are both offered the village. U's Visit is a step back from the gate and W's is
    -- not, so W's scores better by its own score: one plan is built, not one a unit, with W's
    local two = { explorable = { { x = 4, y = 2, kind = "visit" } },
                  canExplore = { [0x01] = { ["4,2"] = "visit" }, [0x03] = { ["4,2"] = "visit" } },
                  reach = { [0x01] = tiles({ 4, 3 }, { 4, 4 }, { 4, 2 }),
                            [0x03] = tiles({ 3, 3 }, { 4, 2 }) } }
    local goal, n = judged("goal", two, 0, nil, nil, blue(0x03, 2, 3, 3, { minRange = false }))
    check(tostring(goal and goal:match("^%d+>visit@4,2")) .. " " .. n, "3>visit@4,2 1",
          "goal act: two units offered one goal, one plan, the better act's")
    -- and the other way round: W two steps back from the gate, U one, so U's is the better
    two.reach = { [0x01] = tiles({ 4, 3 }, { 4, 2 }), [0x03] = tiles({ 4, 4 }, { 4, 2 }) }
    goal, n = judged("goal", two, 0, nil, nil, blue(0x03, 2, 4, 4, { minRange = false }))
    check(tostring(goal and goal:match("^%d+>visit@4,2")) .. " " .. n, "1>visit@4,2 1",
          "goal act: the better act's, whichever unit has it")
end

-- test_plans_without_the_seize_while_a_goal_is_feasible (#510 fwd1 item D, ADR 0405): the
-- lord can Seize, and the thief T is two turns from a chest only it opens. Every plan judged
-- seizes (BEAM = 1, as all 6 did on vanilla Ch8, campaign 4001 turn 16), each forfeiting the
-- chest. Plans without the Seize are judged too, and the rank plays one: no forfeit. With the
-- chest's row stalled (opts.quietGoals) no such plan is built and the Seize is played. Where
-- the first plan's other act is over the cap (T's march into X's strike), the plan with every
-- unit holding is the one under it, and is played.
do
    local function run(opts, enemyPhase)
        local L = blue(0x01, 0, 4, 3, { charId = 0x0F, minRange = false })
        local T = blue(0x02, 1, 0, 9, { minRange = false })
        local Z = red(0x83, 14, 14, { minRange = false })
        local o = {
            objective = { kind = "seize", tile = { x = 4, y = 4 }, lord = 0x0F },
            reach = { [0x01] = tiles({ 4, 3 }, { 4, 4 }), [0x02] = tiles({ 0, 9 }, { 5, 9 }) },
            explorable = { { x = 10, y = 9, kind = "chest" } },
            canExplore = { [0x02] = { ["10,9"] = "chest" } },
            enemyPhase = enemyPhase or function() return {} end,
        }
        local beam = Planner.BEAM
        Planner.BEAM = 1
        local a, plan = Planner.plan(B, boardOf(L, T, Z), sightOf(o), gifted("careful", 100),
                                     opts)
        Planner.BEAM = beam
        local kinds = {}
        for _, c in ipairs(plan and plan.considered or {}) do
            kinds[#kinds + 1] = c.kind .. (c.seizes and "+seize" or "") .. ":" .. c.rank.forfeits
        end
        table.sort(kinds)
        return table.concat(kinds, " "), plan
    end
    local kinds, plan = run()
    check(kinds:find("noseize:0", 1, true) ~= nil, true,
          "no seize: a plan without the Seize is judged")
    check(plan and plan.seizes, false, "no seize: and played, the chest still to get")
    check(plan and #plan.forfeited, 0, "no seize: it forfeits nothing")
    kinds, plan = run({ quietGoals = { ["chest:10,9"] = true } })
    check(kinds:find("noseize", 1, true), nil, "no seize: a stalled chest asks for no such plan")
    check(plan and plan.seizes, true, "no seize: and the Seize is played")
    -- T is struck dead at (5,9), where the first plan marches it; at home it is safe
    kinds, plan = run(nil, function(p)
        for _, b in ipairs(p.blues) do
            if b.x == 5 and b.y == 9 then
                return { { target = b.unit.id, takenHit = 80, takenDmg = 99, takenHits = 1,
                           takenCrit = 0 } }
            end
        end
        return {}
    end)
    local acts = {}
    for _, x in ipairs(plan and plan.acts or {}) do acts[#acts + 1] = Planner.key(x) end
    table.sort(acts)
    check(table.concat(acts, " ") .. " " .. tostring(plan and plan.kind),
          "1>wait@4,3>nil 2>wait@0,9>nil noseize", "no seize: every unit holding is played")
end

-- test_the_plan_names_how_near_each_goal_is (#510 fwd1 item C, the progress record's near half):
-- `nearest` holds the objective's nearest unit and each feasible visit row's best taker, in
-- turns, sorted by id; a reward row has no tile and gives no entry.
do
    local L = blue(0x01, 0, 4, 3, { charId = 0x0F, minRange = false })
    local M = blue(0x02, 1, 4, 4, { minRange = false })
    local Z = red(0x83, 14, 14, { minRange = false })
    local o = {
        objective = { kind = "seize", tile = { x = 4, y = 4 }, lord = 0x0F },
        reach = { [0x01] = tiles({ 4, 3 }), [0x02] = tiles({ 4, 4 }) },
        field = function(t)
            return t.x == 4 and t.y == 2
                and { [2] = { [4] = 0 }, [3] = { [4] = 1 }, [4] = { [4] = 2 } } or nil
        end,
        explorable = { { x = 4, y = 2, kind = "visit" } },
        canExplore = { [0x01] = { ["4,2"] = "visit" }, [0x02] = { ["4,2"] = "visit" } },
        enemyPhase = function() return {} end,
    }
    local st = gifted("bold", 100)
    st.rewards = { { item = 0x68, needs = "villages" } }
    local _, plan = Planner.plan(B, boardOf(L, M, Z), sightOf(o), st)
    local rows = {}
    for _, r in ipairs(plan and plan.ledger or {}) do rows[#rows + 1] = r.id end
    check(table.concat(rows, " "), "visit:4,2 reward:1", "nearest: the ledger holds a visit and a reward row")
    local near = {}
    for _, n in ipairs(plan and plan.nearest or {}) do near[#near + 1] = n.id .. "=" .. n.turns end
    check(table.concat(near, " "), "objective=0.0 visit:4,2=0.2",
          "nearest: the objective's nearest unit (M, on the tile; not the lord's 0.2), the visit's best taker (0.2, not M's 0.4), no reward")
end

-- test_the_win_is_not_deferred_for_a_green (FR-012, plan T034): the lord can Seize, and X
-- kills green G unless the lord blocks instead. A green's survival is a tie-break after the
-- win: the Seize is played.
do
    local L = blue(0x01, 0, 4, 3, { charId = 0x0F, minRange = false })
    local G = blue(0x30, 5, 5, 3, { faction = "green", hp = 10, minRange = false })
    local X = red(0x81, 14, 14, { minRange = false })
    local o = {
        objective = { kind = "seize", tile = { x = 4, y = 4 }, lord = 0x0F },
        reach = { [0x01] = tiles({ 4, 3 }, { 4, 4 }, { 5, 4 }) },
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.x == 5 and b.y == 4 then return {} end
            end
            return { { enemy = 0x81, target = 0x30, takenHit = 100, takenDmg = 99,
                       takenHits = 1, takenCrit = 0, targetHp = 10 } }
        end,
    }
    local a = Planner.plan(B, boardOf(L, G, X), sightOf(o), style("careful"))
    check(a and a.act, "seize", "a green never defers the Seize")
end

-- test_planner_reads_a_second_blow_at_the_hp_the_first_leaves: A and C each hit E (20 HP)
-- for 12, sure. The plan reads C's blow at the 8 HP A's leaves, so it kills, and the plan
-- expects E gone after it. Read at E's full HP, neither blow kills.
do
    local A = blue(0x01, 0, 0, 0)
    local C = blue(0x02, 1, 2, 1)
    local E = red(0x81, 1, 1, { minRange = false, hp = 20 })
    local blow = fc { hit = 100, dmg = 12, hits = 1 }
    local o = {
        reach = { [0x01] = tiles({ 1, 0 }), [0x02] = tiles({ 1, 2 }) },
        fc = { [0x01] = { [0x81] = { ["1,0"] = blow } }, [0x02] = { [0x81] = { ["1,2"] = blow } } },
        enemyPhase = function() return {} end,
    }
    local _, plan = Planner.plan(B, boardOf(A, C, E), sightOf(o), style("bold"))
    local blows, last = 0, nil
    for k, x in ipairs(plan and plan.acts or {}) do
        if x.act == "attack" then blows, last = blows + 1, plan.expect[k] end
    end
    check(blows .. " " .. tostring(last and last.gone), "2 " .. 0x81,
          "planner: the second blow is read at the HP the first leaves")
end

-- test_a_talker_is_sent_to_its_recruit: T (green) is far off and A is the only unit the game
-- lets Talk to it. A is sent to T's tile, not to the nearest enemy, and marches on it.
do
    local A = blue(0x01, 0, 4, 0, { minRange = false })
    local C = blue(0x02, 1, 4, 1, { minRange = false })
    local T = blue(0x30, 5, 0, 0, { faction = "green" })
    local E = red(0x81, 9, 0)
    local o = {
        reach = { [0x01] = tiles({ 4, 0 }, { 3, 0 }, { 5, 0 }),
                  [0x02] = tiles({ 4, 1 }) },
        talk = { [0x01] = { [0x30] = true } },
        field = function(goal)
            local f = {}
            for y = 0, 9 do
                f[y] = {}
                for x = 0, 14 do f[y][x] = math.abs(x - goal.x) + math.abs(y - goal.y) end
            end
            return f
        end,
    }
    local _, plan = Planner.plan(B, boardOf(A, C, T, E), sightOf(o), style("careful"))
    local sent, moved
    for _, g in ipairs(plan and plan.goals or {}) do
        if g.id == 0x01 then sent = g.x .. "," .. g.y end
    end
    for _, a in ipairs(plan and plan.acts or {}) do
        if a.unitId == 0x01 then moved = at(a) end
    end
    check(sent, "0,0", "talker: sent to its recruit")
    -- the plan leaves T's Talk for next turn, sure (GAMMA^1): within one move of T every tile
    -- gives that, and nothing in the model makes a nearer one surer (goals.lua)
    local after = goalAfter(plan, "recruit:" .. 0x30)
    check(after, 0.85, "talker: its recruit is Talked over next turn")
end

-- The goals a careful plan sends units to, "x,y" by unit id. `o.field` defaults to open ground
-- (the manhattan distance from the goal); `blocked[id]` cuts that unit off from every goal.
local function talkGoals(board, o, st, blocked)
    o.field = o.field or function(goal)
        local f = {}
        for y = 0, 9 do
            f[y] = {}
            for x = 0, 14 do f[y][x] = math.abs(x - goal.x) + math.abs(y - goal.y) end
        end
        for _, u in ipairs(board.units) do
            if blocked and blocked[u.id] then f[u.y][u.x] = nil end
        end
        return f
    end
    local _, plan = Planner.plan(B, board, sightOf(o), st or style("careful"))
    local out = {}
    for _, g in ipairs(plan and plan.goals or {}) do out[g.id] = g.x .. "," .. g.y end
    return out
end

-- test_a_claimed_talker_keeps_its_menu: the style claims R (red, far off) for N, a healer with
-- a hurt ally beside it. The claim sends N to R (the march on it), and N keeps the heal and its
-- hold tiles: the recruit's goal worth (goals.lua) pulls it there, and the planner prices the
-- turn a hold costs against the death a march risks. A menu cut to the march alone left no safe
-- plan to judge (vanilla Ch5: Natasha sent into a 0.56 chance to die on turn 3, Joshua lost).
-- So claimed and unclaimed menus are alike here; which talker a claim sends is
-- test_a_claimed_recruit_is_sent_its_claimed_talker's, and no way at all
-- test_no_talker_is_sent_where_it_has_no_way's.
do
    local N = blue(0x0D, 0, 4, 0, { minRange = false })
    local C = blue(0x02, 1, 4, 1, { minRange = false, hp = 5, maxhp = 20 })
    local R = red(0x81, 0, 0, { minRange = false })
    local o = {
        reach = { [0x0D] = tiles({ 4, 0 }, { 3, 0 }, { 5, 0 }), [0x02] = tiles({ 4, 1 }) },
        talk = { [0x0D] = { [0x81] = true } },
        staves = { [0x0D] = { { slot = 0 } } },
        heals = { [0x0D] = { ["4,0"] = { { slot = 0, amount = 10, targets = { 0x02 } } },
                             ["5,0"] = { { slot = 0, amount = 10, targets = { 0x02 } } } } },
        field = function(goal)
            local f = {}
            for y = 0, 9 do
                f[y] = {}
                for x = 0, 14 do f[y][x] = math.abs(x - goal.x) + math.abs(y - goal.y) end
            end
            return f
        end,
    }
    local function whys(st)
        local out = {}
        for _, c in ipairs(B.candidates(boardOf(N, C, R), sightOf(o), st)) do
            if c.unit.id == 0x0D then
                for _, a in ipairs(c.acts) do out[a.why] = true end
            end
        end
        return out
    end
    local free = whys(style("careful"))
    check(tostring(free.heal) .. " " .. tostring(free.hold) .. " " .. tostring(free.march),
          "true true true", "talker: unclaimed, it marches on R and may heal or hold")
    local st = B.applyClaims({ { id = "c", kind = "recruit", unit = { 0x81 }, by = { 0x0D } } },
                             style("careful"))
    local claimed = whys(st)
    check(tostring(claimed.heal) .. " " .. tostring(claimed.hold) .. " " .. tostring(claimed.march),
          "true true true", "talker: claimed, it marches on its recruit and keeps heal and hold")
end

-- test_no_talker_is_sent_into_the_fog: a red the game lets A Talk to, hidden in fog. A player
-- knows no more than the fog shows (goalFor), so A is not sent to its tile.
do
    local A = blue(0x01, 0, 4, 0, { minRange = false })
    local R = red(0x81, 0, 0, { fogged = true })
    local g = talkGoals(boardOf(A, R), { reach = { [0x01] = tiles({ 4, 0 }) },
                                         talk = { [0x01] = { [0x81] = true } } })
    check(g[0x01] ~= "0,0", true, "talker: not sent to a recruit in fog")
end

-- test_no_talker_is_sent_where_it_has_no_way: A may Talk to T, but the field from T has no way
-- to A (and no wall or door to breach). A is not sent to stand idle facing it.
do
    local A = blue(0x01, 0, 4, 0, { minRange = false })
    local T = blue(0x30, 5, 0, 0, { faction = "green" })
    local g = talkGoals(boardOf(A, T), { reach = { [0x01] = tiles({ 4, 0 }) },
                                         talk = { [0x01] = { [0x30] = true } } }, nil,
                        { [0x01] = true })
    check(g[0x01], nil, "talker: not sent to a recruit it has no way to")
end

-- test_each_recruit_gets_its_own_talker: A and C may each Talk to T1 and T2, and A is the
-- nearer to both. Each recruit gets one talker and each talker one recruit, nearest pair first:
-- A takes T1 (distance 1), C is left T2.
do
    local A = blue(0x01, 0, 4, 0, { minRange = false })
    local C = blue(0x02, 1, 8, 0, { minRange = false })
    local T1 = blue(0x30, 5, 3, 0, { faction = "green" })
    local T2 = blue(0x31, 6, 4, 4, { faction = "green" })
    local g = talkGoals(boardOf(A, C, T1, T2), {
        reach = { [0x01] = tiles({ 4, 0 }), [0x02] = tiles({ 8, 0 }) },
        talk = { [0x01] = { [0x30] = true, [0x31] = true },
                 [0x02] = { [0x30] = true, [0x31] = true } } })
    check(g[0x01], "3,0", "talker: the nearest pair is sent first")
    check(g[0x02], "4,4", "talker: the second recruit gets the free talker")
end

-- test_a_claimed_recruit_is_sent_its_claimed_talker: the style claims T for C (`by`), and A is
-- the nearer unit able to Talk to it. Only C is sent; A is left to its own goal.
do
    local A = blue(0x01, 0, 1, 0, { minRange = false })
    local C = blue(0x02, 1, 8, 0, { minRange = false })
    local T = blue(0x30, 5, 0, 0, { faction = "green" })
    local st = style("careful")
    st.recruits = { { units = { 0x30 }, by = { 0x02 } } }
    local g = talkGoals(boardOf(A, C, T), {
        reach = { [0x01] = tiles({ 1, 0 }), [0x02] = tiles({ 8, 0 }) },
        talk = { [0x01] = { [0x30] = true }, [0x02] = { [0x30] = true } } }, st)
    check(g[0x02], "0,0", "talker: the claim's talker is sent")
    check(g[0x01] ~= "0,0", true, "talker: a nearer unit the claim does not name is not")
end

-- test_a_recruit_falls_through_its_claims: two claims name T; the first's talker C has acted,
-- so, as recruitFirst falls through to the second, A (the second's) is sent.
do
    local A = blue(0x01, 0, 8, 0, { minRange = false })
    local C = blue(0x02, 1, 1, 0, { minRange = false, acted = true })
    local T = blue(0x30, 5, 0, 0, { faction = "green" })
    local st = style("careful")
    st.recruits = { { units = { 0x30 }, by = { 0x02 } }, { units = { 0x30 }, by = { 0x01 } } }
    local g = talkGoals(boardOf(A, C, T), {
        reach = { [0x01] = tiles({ 8, 0 }) },
        talk = { [0x01] = { [0x30] = true }, [0x02] = { [0x30] = true } } }, st)
    check(g[0x01], "0,0", "talker: the next claim's talker when the first's cannot go")
end


-- ── The goals (#510 step 9: what is still left to get) ──────────────────────────────────────

-- A beside the boss with a sure kill; a village 6 tiles off (1.2 turns at MOV 5) that only A
-- can take, worth 10000 gold (careful: 400 points). `o` changes per case.
local function bossAndVillage(o)
    local A = blue(0x01, 0, 1, 0)
    local E = red(0x81, 2, 0, { hp = 5, isBoss = true })
    local x = {
        objective = { kind = "boss" },
        reach = { [0x01] = tiles({ 1, 0 }, { 1, 1 }, { 1, 4 }) },
        fc = { [0x01] = { [0x81] = { ["1,0"] = fc { hit = 100, dmg = 9, hits = 1, killsTarget = true } } } },
        explorable = { { x = 1, y = 6, kind = "visit" } },
        canExplore = { [0x01] = { ["1,6"] = "visit" } },
        enemyPhase = function() return {} end,
    }
    for k, v in pairs(o or {}) do x[k] = v end
    return boardOf(A, E), sightOf(x)
end

-- test_boss_kill_waits_for_a_reachable_village: the kill would end the chapter and close the
-- village; a later win is the same win, so careful does not kill. A village worth more than A's
-- way to the boss (a whole death's worth, A being the army) is walked on.
do
    -- 30000 gold (careful: 1200 points) outweighs the kill's own credit and the win now
    -- (~205 + 150); a 10000-gold village is about level with them under careful
    local board, sight = bossAndVillage()
    local a = Planner.plan(B, board, sight, gifted("careful", 30000))
    check(a and a.act ~= "attack", true, "goals: the boss kill waits for a village in reach")
    -- the game's field to the village, which sends A to it (exploring): A's progress is then
    -- toward the village, not the boss
    board, sight = bossAndVillage({ field = function(t)
        return t.x == 1 and t.y == 6 and { [0] = { [1] = 6 }, [1] = { [1] = 5 }, [4] = { [1] = 2 } }
            or nil
    end })
    local _, vplan = Planner.plan(B, board, sight, gifted("careful", 100000))
    local after = goalAfter(vplan, "visit:1,6")
    check(after, 0.85, "goals: A ends where it Visits the rich village next turn")
end

-- test_boss_kill_taken_when_the_village_cannot_be_had: a looter closes it after this phase,
-- before A could get there; or the game lets no player unit Visit it. Then the win costs
-- nothing it could still get, and is taken.
do
    local board, sight = bossAndVillage({ closings = { ["1,6"] = 1 } })
    check((Planner.plan(B, board, sight, gifted("careful", 10000)) or {}).act, "attack",
          "goals: the boss dies when the village closes first")
    board, sight = bossAndVillage({ canExplore = {} })
    check((Planner.plan(B, board, sight, gifted("careful", 10000)) or {}).act, "attack",
          "goals: a village no one may take holds nothing back")
end

-- test_rout_last_kill_and_seize_are_the_win: on a Rout map the last enemy's death is the win
-- and waits for the village as the boss's does; with another enemy left it is only a kill.
-- A Seize waits the same way, and is taken with no village open.
do
    local A = blue(0x01, 0, 1, 0)
    local E = red(0x81, 2, 0, { hp = 5 })
    local o = {
        objective = { kind = "rout" },
        reach = { [0x01] = tiles({ 1, 0 }, { 1, 1 }, { 1, 4 }) },
        fc = { [0x01] = { [0x81] = { ["1,0"] = fc { hit = 100, dmg = 9, hits = 1, killsTarget = true } } } },
        explorable = { { x = 1, y = 6, kind = "visit" } },
        canExplore = { [0x01] = { ["1,6"] = "visit" } },
        enemyPhase = function() return {} end,
    }
    local a = Planner.plan(B, boardOf(A, E), sightOf(o), gifted("careful", 10000))
    check(a and a.act ~= "attack", true, "goals: a Rout's last kill waits for the village")
    local F = red(0x82, 14, 14, { minRange = false })
    a = Planner.plan(B, boardOf(A, E, F), sightOf(o), gifted("careful", 10000))
    check(a and a.act, "attack", "goals: a kill that leaves an enemy is no win, and is taken")
    local L = blue(0x01, 0, 4, 3, { charId = 0x0F, minRange = false })
    local Z = red(0x83, 14, 14, { minRange = false })
    local seize = {
        objective = { kind = "seize", tile = { x = 4, y = 4 }, lord = 0x0F },
        reach = { [0x01] = tiles({ 4, 3 }, { 4, 4 }, { 4, 2 }) },
        explorable = { { x = 4, y = 0, kind = "visit" } },
        canExplore = { [0x01] = { ["4,0"] = "visit" } },
        enemyPhase = function() return {} end,
    }
    a = Planner.plan(B, boardOf(L, Z), sightOf(seize), gifted("careful", 10000))
    check(a and a.act ~= "seize", true, "goals: the Seize waits for the village")
    seize.explorable, seize.canExplore = {}, {}
    a = Planner.plan(B, boardOf(L, Z), sightOf(seize), gifted("careful", 10000))
    check(a and a.act, "seize", "goals: with nothing left, the Seize")
end

-- test_survive_holds_as_before: a Survive map has no way there: with nothing to get, the
-- safest hold, its own tile on a tie.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local X = red(0x81, 9, 9, { minRange = false })
    local o = { objective = { kind = "survive" }, reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
                enemyPhase = function() return {} end }
    check(at(Planner.plan(B, boardOf(A, X), sightOf(o), style("careful"))), "0,0",
          "goals: Survive holds where it stands")
end

-- test_a_goal_closing_now_is_taken_first: two villages A can each Visit now; a looter takes
-- (2,0) after this phase and (0,1) never. A takes (2,0): the other keeps its chance.
do
    local A = blue(0x01, 0, 1, 0, { minRange = false })
    local X = red(0x81, 14, 14, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 1, 0 }, { 2, 0 }, { 0, 1 }) },
        explorable = { { x = 2, y = 0, kind = "visit" }, { x = 0, y = 1, kind = "visit" } },
        canExplore = { [0x01] = { ["2,0"] = "visit", ["0,1"] = "visit" } },
        closings = { ["2,0"] = 1 },
        enemyPhase = function() return {} end,
    }
    local a = Planner.plan(B, boardOf(A, X), sightOf(o), gifted("careful", 1000))
    check(a and a.act .. "@" .. at(a), "visit@2,0", "goals: the closing village first")
end


-- test_a_counter_that_kills_the_boss_is_the_win: at (1,0) the boss strikes A and A's counter
-- kills it in the enemy phase -- the chapter ends there, closing the village. Careful keeps A
-- at (1,1), out of the boss's reach, while the village is open (vanilla Ch5 attempt 8: the
-- boss fell so on turn 5, (5,1) unvisited).
do
    local A = blue(0x01, 0, 1, 2, { minRange = false })
    local E = red(0x81, 2, 0, { hp = 5, isBoss = true, minRange = false })
    local Z = red(0x82, 14, 14, { minRange = false })
    local o = {
        objective = { kind = "boss" },
        reach = { [0x01] = tiles({ 1, 2 }, { 1, 0 }, { 1, 1 }) },
        explorable = { { x = 1, y = 6, kind = "visit" } },
        canExplore = { [0x01] = { ["1,6"] = "visit" } },
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.x == 1 and b.y == 0 then
                    return { { enemy = 0x81, target = b.unit.id, takenHit = 0, takenDmg = 0,
                               takenHits = 1, takenCrit = 0, targetHp = b.hp, felled = 1 } }
                end
            end
            return {}
        end,
    }
    local a = Planner.plan(B, boardOf(A, E, Z), sightOf(o), gifted("careful", 10000))
    check(at(a) ~= "1,0", true, "goals: no stand where our counter would end the chapter")
end


-- test_mend_moves_a_unit_whose_counter_ends_the_chapter: A's chip on the boss (no kill) tops
-- the beam (the boss's damage counts five times), and in the enemy phase the boss strikes A
-- and A's counter kills it, closing a rich village. The beam cannot see that counter; the
-- mend tries A's other acts, and A does not stay beside the boss.
do
    local A = blue(0x01, 0, 1, 0)
    local E = red(0x81, 2, 0, { hp = 30, isBoss = true })
    local Z = red(0x82, 14, 14, { minRange = false })
    local o = {
        objective = { kind = "boss" },
        reach = { [0x01] = tiles({ 1, 0 }, { 1, 1 }, { 1, 4 }) },
        fc = { [0x01] = { [0x81] = { ["1,0"] = fc { hit = 100, dmg = 9, hits = 1 } } } },
        explorable = { { x = 1, y = 6, kind = "visit" } },
        canExplore = { [0x01] = { ["1,6"] = "visit" } },
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.x == 1 and b.y == 0 then
                    return { { enemy = 0x81, target = b.unit.id, takenHit = 0, takenDmg = 0,
                               takenHits = 1, takenCrit = 0, targetHp = b.hp, felled = 1 } }
                end
            end
            return {}
        end,
    }
    local final = Planner.FINAL
    Planner.FINAL = 1
    local a = Planner.plan(B, boardOf(A, E, Z), sightOf(o), gifted("careful", 30000))
    Planner.FINAL = final
    check(at(a) ~= "1,0", true, "goals: the mend keeps A from the counter that ends the chapter")
end


-- test_no_boss_chip_while_a_goal_is_open: A can chip the boss (9 of its 25 HP; a 5% crit
-- kills it) or not, a village worth 25000 gold open (careful: 1000 points). The chip is a step
-- to a win not wanted yet (st.bossWant ~0.13): credited ~25 with the win's own share, against
-- the crit's 5% of the village (~41), it is left; credited five times over (~61), it was
-- taken. With no village, the chip.
do
    local function play(village)
        local A = blue(0x01, 0, 1, 0)
        local E = red(0x81, 2, 0, { hp = 25, isBoss = true, minRange = false })
        local Z = red(0x82, 14, 14, { minRange = false })
        local o = {
            objective = { kind = "boss" },
            reach = { [0x01] = tiles({ 1, 0 }, { 1, 1 }, { 1, 4 }) },
            fc = { [0x01] = { [0x81] = { ["1,0"] = fc { hit = 100, dmg = 9, hits = 1, crit = 5 } } } },
            explorable = village and { { x = 1, y = 6, kind = "visit" } } or {},
            canExplore = { [0x01] = village and { ["1,6"] = "visit" } or {} },
            enemyPhase = function() return {} end,
        }
        return Planner.plan(B, boardOf(A, E, Z), sightOf(o), gifted("careful", 25000))
    end
    check((play(true) or {}).act ~= "attack", true, "goals: no chip on the boss while a goal is open")
    check((play(false) or {}).act, "attack", "goals: with nothing left, the chip")
end


-- test_a_green_recruits_death_is_a_forfeit (FR-012, FR-014): as the game-over green test, in
-- bold. An allied green is no reason to lose four turns toward the village, so A keeps the
-- ground; but when G is a recruit A may Talk over, its death is that goal lost for good, a
-- forfeit, and A blocks at every village worth.
local function greenRecruitPlay(gold, talk)
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local G = blue(0x30, 5, 3, 3, { faction = "green", hp = 10, minRange = false })
    local X = red(0x81, 0, 9, { minRange = false })
    local o = {
        objective = { kind = "rout" },
        -- (0,1) is the march toward the village, (1,0) the block
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }, { 0, 1 }) },
        talk = talk and { [0x01] = { [0x30] = true } } or nil,
        field = function(t)
            return t.x == 5 and t.y == 0
                and { [0] = { [0] = 20, [1] = 40 }, [1] = { [0] = 15 } } or nil
        end,
        explorable = { { x = 5, y = 0, kind = "visit" } },
        canExplore = { [0x01] = { ["5,0"] = "visit" } },
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.x == 1 then return {} end
            end
            return { { enemy = 0x81, target = 0x30, takenHit = 100, takenDmg = 99,
                       takenHits = 1, takenCrit = 0, targetHp = 10 } }
        end,
    }
    local a, plan = Planner.plan(B, boardOf(A, G, X), sightOf(o), gifted("bold", gold))
    return at(a), plan
end
for _, gold in ipairs({ 1500, 3000 }) do
    check(greenRecruitPlay(gold, true), "1,0",
          "goals: a green recruit's death is a forfeit, at " .. gold)
    check(greenRecruitPlay(gold, false), "0,1", "goals: an allied green's is not, at " .. gold)
end
-- and a recruit's death is the forfeit, and its chance is in the allied greens' share too: the
-- forfeit is yes/no, so the share is what tells a plan risking it less from one risking it more
do
    local function marchRank(talk)
        local _, plan = greenRecruitPlay(1500, talk)
        for _, c in ipairs(plan and plan.considered or {}) do
            if table.concat(c.acts, " ") == "1>wait@0,1>nil" then return c.rank end
        end
    end
    local r, g = marchRank(true), marchRank(false)
    check(r and r.forfeits == 1 and r.green_die, 1, "goals: a recruit's death, the forfeit and its share")
    check(g and g.forfeits == 0 and g.green_die, 1, "goals: an allied green's, its share only")
end

-- test_a_rescue_saves_a_green_the_phase_would_kill (vanilla Ch2's Ross, #510): X kills G
-- where it stands unless G is carried (the game's AI skips a rescued unit, cp_battle.c). A may
-- Rescue G from (2,0), beside it, or wait there. The judged phase is asked with the plan's
-- carry, and the plan that carries G ranks first (green_die). Without Rescue, both plans
-- lose G.
local function rescuePlay(canRescue)
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local G = blue(0x30, 5, 3, 0, { faction = "green", hp = 5, minRange = false })
    local X = red(0x81, 9, 0, { minRange = false })
    local asked
    local o = {
        objective = { kind = "rout" },
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }, { 2, 0 }) },
        rescue = canRescue and { [0x01] = { [0x30] = true } } or nil,
        enemyPhase = function(plan)
            asked = asked or plan.carry
            if plan.carry and plan.carry[0x30] and plan.carry[0x30].by == 0x01 then return {} end
            return { { enemy = 0x81, target = 0x30, takenHit = 100, takenDmg = 99,
                       takenHits = 1, takenCrit = 0, targetHp = 5 } }
        end,
    }
    local a, plan = Planner.plan(B, boardOf(A, G, X), sightOf(o), style("bold"))
    return a, plan, asked
end
do
    local a, plan = rescuePlay(true)
    check(a and a.act .. ">" .. tostring(a.targetId) .. "@" .. at(a), "rescue>48@2,0",
          "rescue: A carries G out of the phase that kills it")
    local g
    for _, p in ipairs(plan and plan.predict or {}) do
        if p.id == 0x30 then g = p.die end
    end
    check(g, 0, "rescue: the carried green meets no strike")
    local b = rescuePlay(false)
    check(b and b.act ~= "rescue", true, "rescue: none where the game offers none")
end

-- test_a_carried_recruit_is_dropped_beside_its_talker: A carries G, a recruit E may Talk over
-- once G is set down (TalkCommandUsability lists units on the map). Carried, G's goal waits a
-- turn at A's tile (goalTerm); dropped beside E it does not, so A drops G there. The key
-- carries the drop tile, and reads back.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false, carrying = 0x30 })
    local E = blue(0x02, 1, 5, 0, { minRange = false })
    local G = blue(0x30, 5, 0, 0, { faction = "green", hp = 5, onField = false, carriedBy = 0x01 })
    local X = red(0x81, 14, 9, { minRange = false })
    local o = {
        objective = { kind = "rout" },
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }, { 2, 0 }, { 3, 0 }),
                  [0x02] = tiles({ 5, 0 }) },
        talk = { [0x02] = { [0x30] = true } },
        dropOn = { ["4,0"] = true, ["1,0"] = true, ["0,1"] = true },
        enemyPhase = function() return {} end,
    }
    local _, plan = Planner.plan(B, boardOf(A, E, G, X), sightOf(o), style("bold"))
    local drop
    for _, x in ipairs(plan and plan.acts or {}) do
        if x.act == "drop" then drop = x end
    end
    check(drop and (drop.move.x .. "," .. drop.move.y .. "/" .. drop.dropAt.x .. ","
                    .. drop.dropAt.y), "3,0/4,0", "drop: G set down beside its talker")
    local k = drop and Planner.key(drop)
    check(k, "1>drop@3,0>48/4,0", "drop: the key names the drop tile")
    local back = k and Planner.unkey(k)
    check(back and back.dropAt and (back.dropAt.x .. "," .. back.dropAt.y), "4,0",
          "drop: the key reads back")
end


-- test_a_canto_unit_moves_on_after_its_rescue (vanilla Ch2's Vanessa, #510): A, a Canto unit,
-- may Rescue G from (2,0), beside it. X kills G where it stands unless G is carried, and kills A
-- if A ends on (2,0). The game offers A a second move from (2,0) (sight.cantoTiles); the plan
-- rescues and moves on, so no one dies, and the judged phase is asked with A where it ends.
-- Without Canto every plan loses one of them. The key names the Canto tile and reads back.
local function cantoPlay(canto)
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local G = blue(0x30, 5, 3, 0, { faction = "green", hp = 5, minRange = false })
    local X = red(0x81, 9, 0, { minRange = false })
    local o = {
        objective = { kind = "rout" },
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }, { 2, 0 }) },
        rescue = { [0x01] = { [0x30] = true } },
        enemyPhase = function(plan)
            local ends
            for _, b in ipairs(plan.blues) do
                if b.unit.id == 0x01 then ends = b.x .. "," .. b.y end
            end
            local carried = plan.carry and plan.carry[0x30] and plan.carry[0x30].by == 0x01
            if not carried then
                return { { enemy = 0x81, target = 0x30, takenHit = 100, takenDmg = 99,
                           takenHits = 1, takenCrit = 0, targetHp = 5 } }
            end
            if ends == "2,0" then
                return { { enemy = 0x81, target = 0x01, takenHit = 100, takenDmg = 99,
                           takenHits = 1, takenCrit = 0, targetHp = A.hp } }
            end
            return {}
        end,
    }
    local s = sightOf(o)
    if canto then
        s.cantoTiles = function(_, a)
            if a.act ~= "rescue" then return {} end
            return tiles({ 2, 0 }, { 1, 0 }, { 0, 0 })
        end
    end
    return Planner.plan(B, boardOf(A, G, X), s, style("bold"))
end
do
    local function deaths(plan)
        local n = 0
        for _, p in ipairs(plan and plan.predict or {}) do
            if (p.die or 0) > 0 then n = n + 1 end
        end
        return n
    end
    local a, plan = cantoPlay(true)
    check(a and a.act .. "@" .. at(a) .. "~" .. tostring(a.canto and (a.canto.x .. "," .. a.canto.y)),
          "rescue@2,0~1,0", "canto: A rescues G and moves on")
    check(deaths(plan), 0, "canto: no one dies when A moves on")
    local _, still = cantoPlay(false)
    check(deaths(still) > 0, true, "canto: without it, a plan loses one")
    local k = a and Planner.key(a)
    check(k, "1>rescue@2,0>48~1,0", "canto: the key names the Canto tile")
    local back = k and Planner.unkey(k)
    check(back and back.canto and (back.canto.x .. "," .. back.canto.y) .. "/" .. back.targetId,
          "1,0/48", "canto: the key reads back")
    local d = Planner.unkey("1>drop@3,0>48/4,0~2,0")
    check(d.dropAt.x .. "," .. d.dropAt.y .. "~" .. d.canto.x .. "," .. d.canto.y, "4,0~2,0",
          "canto: a Drop's key reads back with both tiles")
end

-- test_an_avoid_claim_holds_on_a_canto_tile: P, a Canto unit, may Rescue G from (1,0) and move
-- on to (0,0) or (2,0). (2,0) is in the archer's reach and an avoid claim keeps P out of it,
-- so no Canto move ends there; (0,0) is still offered.
do
    local P = blue(0x01, 0, 0, 0, { minRange = false })
    local G = blue(0x30, 5, 1, 1, { faction = "green", hp = 5, minRange = false })
    local X = red(0x81, 4, 0, { classId = CLS_A, minRange = 2, maxRange = 2 })
    local o = { reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
                rescue = { [0x01] = { [0x30] = true } } }
    local s = sightOf(o)
    s.cantoTiles = function(_, a)
        if a.act ~= "rescue" then return {} end
        return tiles({ 1, 0 }, { 0, 0 }, { 2, 0 })
    end
    local function cantos(st)
        local out = {}
        for _, c in ipairs(B.candidates(boardOf(P, G, X), s, st)) do
            for _, a in ipairs(c.acts) do
                if a.canto then out[#out + 1] = a.canto.x .. "," .. a.canto.y end
            end
        end
        table.sort(out)
        return table.concat(out, " ")
    end
    check(cantos(style("bold")), "0,0 2,0", "canto: with no claim, both tiles")
    local st = claimed("bold", { id = "v", kind = "avoid", unit = { 0x01 }, vs = { CLS_A } })
    check(cantos(st), "0,0", "canto: an avoid claim keeps the second move out of reach")
    -- every move in reach, the act's tile clear: staying keeps the claim, so no move is offered
    s.cantoTiles = function(_, a)
        if a.act ~= "rescue" then return {} end
        return tiles({ 1, 0 }, { 2, 0 })
    end
    check(cantos(st), "", "canto: no move into reach when staying is clear")
end

-- test_surprise_reads_the_canto_tile: a unit that moved on to its Canto tile ended its move as
-- planned; one still on the act's tile ended short.
do
    local a = { unitId = 0x01, unit = 0x01, act = "visit", move = { x = 2, y = 0 },
                canto = { x = 0, y = 0 } }
    local plan = { acts = { a, { unitId = 0x02, act = "wait", move = { x = 5, y = 0 } } },
                   expect = { { hp = 20 } }, enemies = {} }
    local function board(x)
        return { units = { blue(0x01, 0, x, 0, { hp = 20 }), blue(0x02, 1, 5, 0) } }
    end
    check(Planner.surprise(plan, 1, board(0), board(0)), nil, "canto: the Canto tile is the plan's end")
    check(Planner.surprise(plan, 1, board(0), board(2)), "the move ended short",
          "canto: stopping on the act's tile is short")
end

-- test_a_march_toward_a_goal_survives_the_menu_cut: A has four small attacks (each worth a
-- point of damage) and a march to (2,0) toward T, a recruit only A can Talk over, worth one
-- death, east like the throne; (2,0) costs 2 HP of exposure to X. Ranked by its own score the march (-4) fell under
-- the attacks and was cut before the beam; ranked with what it does to T's goal, it is played.
do
    local A = blue(0x01, 0, 0, 0)
    local T = blue(0x30, 5, 9, 0, { faction = "green", minRange = false })
    local E = {}
    for i, t in ipairs({ { 0, 1 }, { 1, 1 }, { 3, 1 }, { 4, 1 } }) do
        E[i] = red(0x80 + i, t[1], t[2], { hp = 30, minRange = false })
    end
    local X = red(0x85, 3, 0)
    local hit = fc { hit = 100, dmg = 1, hits = 1 }
    local o = {
        -- a Seize map whose throne lies east too, and A no lord: the way there pulls with T
        objective = { kind = "seize", tile = { x = 9, y = 1 }, lord = 0x0F },
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }, { 2, 0 }), [0x85] = tiles({ 3, 0 }) },
        talk = { [0x01] = { [0x30] = true } },
        danger = { ["2,0"] = 1 },
        fc = { [0x01] = { [0x81] = { ["0,0"] = hit }, [0x82] = { ["1,0"] = hit },
                          [0x85] = { ["2,0"] = fc { takenHit = 100, takenDmg = 2, takenHits = 1 } } } },
        enemyPhase = function() return {} end,
    }
    local _, plan = Planner.plan(B, boardOf(A, T, E[1], E[2], E[3], E[4], X), sightOf(o),
                                 style("careful"))
    local moved
    for _, a in ipairs(plan and plan.acts or {}) do
        if a.unitId == 0x01 then moved = at(a) end
    end
    check(moved, "2,0", "goals: the march toward a recruit survives the menu cut")
end


-- test_a_visit_now_beats_waiting_on_the_village: A stands one step from a village worth 1000
-- gold and nothing threatens it. Visiting now takes it; standing on it without the Visit leaves
-- it for next turn, one turn of GAMMA (6 points under careful). Before PR #553's review both
-- read chance 1 and judged the same: the visit won on the tie-break alone.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local X = red(0x81, 14, 14, { minRange = false })
    local o = {
        objective = { kind = "survive" },
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        explorable = { { x = 1, y = 0, kind = "visit" } },
        canExplore = { [0x01] = { ["1,0"] = "visit" } },
        enemyPhase = function() return {} end,
    }
    local a, plan = Planner.plan(B, boardOf(A, X), sightOf(o), gifted("careful", 1000))
    local judged = {}
    for _, x in ipairs(plan and plan.considered or {}) do judged[x.acts[1]] = x.judged end
    check(a and a.act, "visit", "goals: a village in reach is visited, not waited on")
    check((judged["1>visit@1,0>nil"] or -1e9) > (judged["1>wait@1,0>nil"] or 1e9), true,
          "goals: the visit judges above waiting on the village")
end

-- test_rout_under_fog_is_not_won_by_the_last_seen_kill: A can kill E, the only enemy in sight;
-- F stands in the fog. Killing E wins nothing, so a village A could take now is not closed by
-- it: careful visits rather than strike (PR #553 review).
do
    local A = blue(0x01, 0, 1, 0)
    local E = red(0x81, 2, 0, { hp = 5 })
    local F = red(0x82, 14, 14, { minRange = false, fogged = true })
    local o = {
        objective = { kind = "rout" },
        reach = { [0x01] = tiles({ 1, 0 }, { 1, 1 }) },
        fc = { [0x01] = { [0x81] = { ["1,0"] = fc { hit = 100, dmg = 9, hits = 1, killsTarget = true } } } },
        explorable = { { x = 1, y = 1, kind = "visit" } },
        canExplore = { [0x01] = { ["1,1"] = "visit" } },
        enemyPhase = function() return {} end,
    }
    local _, plan = Planner.plan(B, boardOf(A, E, F), sightOf(o), gifted("careful", 1000))
    local win = goalAfter(plan, "win")
    check(win, 0.85, "goals: a kill with an enemy in the fog is no win (the win stays a turn off)")
end

-- The game's own count (CountRedUnits) decides: a red carried by another is in no board read,
-- yet the Rout goes on while it lives.
do
    local A = blue(0x01, 0, 1, 0)
    local E = red(0x81, 2, 0, { hp = 5 })
    local o = {
        objective = { kind = "rout" },
        reach = { [0x01] = tiles({ 1, 0 }, { 1, 1 }) },
        fc = { [0x01] = { [0x81] = { ["1,0"] = fc { hit = 100, dmg = 9, hits = 1, killsTarget = true } } } },
        explorable = { { x = 1, y = 1, kind = "visit" } },
        canExplore = { [0x01] = { ["1,1"] = "visit" } },
        enemyPhase = function() return {} end,
    }
    local sight = sightOf(o)
    sight.redCount = function() return 2 end   -- E, and a red E carries
    local _, plan = Planner.plan(B, boardOf(A, E), sight, gifted("careful", 1000))
    local win = goalAfter(plan, "win")
    check(win, 0.85, "goals: the game's red count, not the board's, decides a Rout's win")
end

-- test_hitting_a_game_over_recruit_costs_the_chapter: R (red) is a recruit A may Talk over,
-- and its death ends the game (sight.objective.gameOver names it). A's attack on it may kill
-- it: even bold, which prices a death at 60, judges that strike as the chapter (PR #553 review).
do
    local A = blue(0x01, 0, 1, 0)
    local R = red(0x81, 2, 0, { hp = 10, charId = 0x50 })
    local Z = red(0x82, 14, 14, { minRange = false })
    local o = {
        objective = { kind = "rout", gameOver = { 0x50 } },
        reach = { [0x01] = tiles({ 1, 0 }, { 1, 1 }) },
        talk = { [0x01] = { [0x81] = true } },
        fc = { [0x01] = { [0x81] = { ["1,0"] = fc { hit = 60, dmg = 10, hits = 1, killsTarget = true } } } },
        enemyPhase = function() return {} end,
    }
    local a, plan = Planner.plan(B, boardOf(A, R, Z), sightOf(o), style("bold"))
    check(a and a.act ~= "attack", true, "goals: bold does not strike a game-over recruit")
    -- the strike as the judge priced it: the chapter at its 60% kill, not one death's 60
    local judged
    for _, x in ipairs(plan and plan.considered or {}) do
        for _, k in ipairs(x.acts) do
            if k:find(">attack@1,0>129", 1, true) then judged = x.judged end
        end
    end
    check(judged ~= nil and judged < -10000, true,
          "goals: a strike that may kill a game-over recruit is judged as the chapter")
end


-- test_rout_counts_reds_only: on a Rout map, a Talk takes a green recruit off the board too
-- (gone), but only reds count: talking T over while E stands is no win. And the count, as
-- the game's, takes a red off the field (carried) as standing (PR #553 re-review).
do
    local A = blue(0x01, 0, 1, 0)
    local T = blue(0x30, 5, 0, 0, { faction = "green", minRange = false })
    local E = red(0x81, 9, 9, { minRange = false })
    local o = {
        objective = { kind = "rout" },
        reach = { [0x01] = tiles({ 1, 0 }) },
        talk = { [0x01] = { [0x30] = true } },
        enemyPhase = function() return {} end,
    }
    local _, plan = Planner.plan(B, boardOf(A, T, E), sightOf(o), style("careful"))
    local win = goalAfter(plan, "win")
    check(win, 0.85, "rout: a Talk on a green is no win while a red stands")
    local H = red(0x82, 9, 8, { minRange = false, onField = false })
    local x = { objective = { kind = "rout" }, reach = { [0x01] = tiles({ 1, 0 }) },
                enemyPhase = function() return {} end }
    _, plan = Planner.plan(B, boardOf(A, H), sightOf(x), style("careful"))
    win = goalAfter(plan, "win")
    check(win, 0.85, "rout: the fallback count keeps a red off the field standing")
end

-- ── Risk admission and ranking (#510 step 9 PR-C: FR-009 to FR-013, ADR 0384) ──────

-- test_caps_are_fixed_per_style (FR-010): careful 1%, even 5%, bold 15%, and a style with no
-- cap is an error, never a silent default.
do
    check(Planner.CAPS.careful, 0.01, "caps: careful 1%")
    check(Planner.CAPS.even, 0.05, "caps: even 5%")
    check(Planner.CAPS.bold, 0.15, "caps: bold 15%")
    local saved = Planner.CAPS.even
    Planner.CAPS.even = nil
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local X = red(0x81, 9, 9, { minRange = false })
    local ok, err = pcall(Planner.plan, B, boardOf(A, X), sightOf {}, style("even"))
    Planner.CAPS.even = saved
    check(ok, false, "caps: a style with no cap raises")
    check(tostring(err):find("no risk cap", 1, true) ~= nil, true, "caps: and says why")
end

-- test_protected_are_blues_and_game_over_units (FR-009): the blue units and every unit whose
-- death ends the game are protected, each with its style's cap; an ordinary allied green is not.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local G = blue(0x30, 5, 3, 3, { faction = "green", minRange = false })
    local V = blue(0x31, 6, 5, 5, { faction = "green", minRange = false, charId = 0x40 })
    local X = red(0x81, 9, 9, { minRange = false })
    local o = { objective = { kind = "rout", gameOver = { 0x01, 0x40 } },
                enemyPhase = function() return {} end }
    local _, plan = Planner.plan(B, boardOf(A, G, V, X), sightOf(o), style("even"))
    local ids, caps = {}, {}
    for _, p in ipairs(plan and plan.protected or {}) do
        ids[#ids + 1] = string.format("%02X", p.id); caps[#caps + 1] = p.cap
    end
    check(table.concat(ids, ","), "01,31", "protected: the blue and the game-over green, not G")
    check(caps[1] == 0.05 and caps[2] == 0.05, true, "protected: each carries the style's cap")
end

-- Three blues, each beside an enemy it kills at 2RN 60 (one blow of 10 on 10 HP). An enemy
-- left standing kills its blue in the enemy phase; holding leaves it standing for sure.
local function threeOpenKills(hits)
    local units, reach, fcs, pair = {}, {}, {}, {}
    for k = 1, 3 do
        local a, e = k, 0x80 + k
        units[#units + 1] = blue(a, k - 1, 0, 2 * k)
        units[#units + 1] = red(e, 1, 2 * k, { hp = 10 })
        reach[a] = tiles({ 0, 2 * k })
        fcs[a] = { [e] = { ["0," .. (2 * k)] = fc { hit = hits and hits[k] or 60, dmg = 10,
                                                     hits = 1 } } }
        pair[e] = a
    end
    local o = {
        reach = reach, fc = fcs,
        enemyPhase = function(plan)
            local out = {}
            for e, a in pairs(pair) do
                if not plan.gone[e] then
                    out[#out + 1] = { enemy = e, target = a, takenHit = 100, takenDmg = 99,
                                      takenHits = 1, takenCrit = 0 }
                end
            end
            table.sort(out, function(x, y) return x.enemy < y.enemy end)
            return out
        end,
    }
    return units, o
end

-- test_death_is_summed_over_branches (FR-009): every uncertain kill is played both ways. The
-- average keeps a 68% kill gone, so a judge that branched only two kills saw no death for the
-- third blue; its enemy lives 32% of the time, and then it kills.
do
    local units, o = threeOpenKills()
    local _, plan = Planner.plan(B, boardOf(table.unpack(units)), sightOf(o), style("bold"))
    local live = 1 - Sight.rollChance(2, 60)
    local attacks = 0
    for _, a in ipairs(plan and plan.acts or {}) do
        if a.act == "attack" then attacks = attacks + 1 end
    end
    check(attacks, 3, "branches: every blue strikes its enemy")
    for _, p in ipairs(plan and plan.predict or {}) do
        check(math.abs(p.die - live) < 1e-9, true,
              string.format("branches: 0x%02X dies only where its enemy lives", p.id))
    end
    -- every judged plan played 2^3 phases at most; the call's third value counts them all
    local _, _, cost = Planner.plan(B, boardOf(table.unpack(units)), sightOf(o), style("bold"))
    check(cost and cost.phases >= 8, true, "branches: the phases are counted")
    check(cost and cost.averaged, 0, "branches: none left to the average")
    check(plan and plan.branched, 3, "branches: each uncertain kill is branched")
    check(plan and plan.averaged, 0, "branches: none left to the average, in the plan")
end

-- The counter kills a judged phase left unsplit (sight's `unsplit`, ADR 0411) are summed into the
-- call's cost apart from `averaged`, which stays the plan's own uncertain kills past BRANCH;
-- and opts.at says where the call is as it goes (what a decision cut short was doing).
do
    local units, o = threeOpenKills({ 90, 50, 70 })
    local phase = o.enemyPhase
    -- the same call with no unsplit kills: what `averaged` is without them
    local _, _, plain = Planner.plan(B, boardOf(table.unpack(units)), sightOf(o), style("bold"))
    local at, during = {}, nil
    o.enemyPhase = function(plan)
        during = during or (at.stage .. "/" .. at.phases)
        local out = phase(plan)
        out.unsplit = 2
        return out
    end
    local _, _, cost = Planner.plan(B, boardOf(table.unpack(units)), sightOf(o), style("bold"),
                                    { at = at })
    check(cost.unsplit, 2 * cost.phases, "unsplit: each phase's count is summed into the cost")
    check(cost.averaged, plain.averaged, "unsplit: and is no part of `averaged`")
    check(during ~= nil and during:match("^judge %a+/1$") ~= nil, true,
          "at: the first judged phase reads its stage and count (" .. tostring(during) .. ")")
    check(at.stage, "lookahead", "at: the call ends in its last stage")
    check(at.phases, cost.phases, "at: every phase was counted as it was played")
    check(at.judged > 0, true, "at: and the plans judged")
end

-- test_branching_past_its_bound_plays_the_most_uncertain (PR #560 re-review): the kills land
-- at 2RN 90, 50 and 70. With BRANCH = 1 only the 50% one is played both ways, the others keep
-- the average (gone), and the call counts each kill left over in every plan it judged.
do
    local units, o = threeOpenKills({ 90, 50, 70 })
    local both = {}   -- per enemy, the states the phases judging the three attacks saw it in
    local phase = o.enemyPhase
    o.enemyPhase = function(plan)
        local slots = 0
        for _, b in ipairs(plan.blues) do
            if b.slot then slots = slots + 1 end
        end
        for e = 0x81, slots == 3 and 0x83 or 0x80 do
            both[e] = both[e] or {}
            both[e][plan.gone[e] and "dead" or "alive"] = true
        end
        return phase(plan)
    end
    local saved = Planner.BRANCH
    Planner.BRANCH = 1
    local ok, a, plan, cost = pcall(Planner.plan, B, boardOf(table.unpack(units)), sightOf(o),
                                    style("bold"))
    Planner.BRANCH = saved
    check(ok, true, "bound: the plan is made" .. (ok and "" or (": " .. tostring(a))))
    check(plan and plan.branched, 1, "bound: one kill branched")
    check(plan and plan.averaged, 2, "bound: two left to the average")
    check(both[0x82] and both[0x82].dead and both[0x82].alive, true,
          "bound: the 50% kill both ways")
    check(both[0x81] and both[0x81].alive, nil, "bound: the 90% kill keeps the average")
    check(cost and cost.averaged >= 2, true, "bound: the call counts what every plan averaged")
    local three = plan and plan.protected and plan.protected[3]
    local sum = 0
    for _, b in ipairs(three and three.branches or {}) do sum = sum + b.p end
    check(math.abs(sum - 1) < 1e-9, true, "branches: the record's weights are normalized")
end

-- test_a_dim_too_wide_does_not_stop_the_narrower_ones (PR #585 review): A's exchange with E1
-- (a 2RN-40 kill, a four-blow counter) goes six ways and is the most uncertain; C's 50% kill on
-- E2 goes two. With BRANCH = 2 (four ways at most) A's six keep the average, and C's kill,
-- which fits, is still played both ways.
do
    local A = blue(0x01, 0, 0, 0, { hp = 20, maxhp = 20 })
    local C = blue(0x02, 1, 0, 5, { hp = 20, maxhp = 20 })
    local E1 = red(0x81, 1, 0, { hp = 9 })
    local E2 = red(0x82, 1, 5, { hp = 9 })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }), [0x02] = tiles({ 0, 5 }) },
        fc = { [0x01] = { [0x81] = { ["0,0"] = fc { hit = 40, dmg = 12, hits = 1, counters = true,
                                                   counterHit = 50, counterDmg = 1,
                                                   counterHits = 4 } } },
               [0x02] = { [0x82] = { ["0,5"] = fc { hit = 50, dmg = 12, hits = 1 } } } },
        enemyPhase = function() return {} end,
    }
    local saved = Planner.BRANCH
    Planner.BRANCH = 2
    local ok, a, plan = pcall(Planner.plan, B, boardOf(A, C, E1, E2), sightOf(o), style("bold"))
    Planner.BRANCH = saved
    check(ok, true, "wide dim: the plan is made" .. (ok and "" or (": " .. tostring(a))))
    local attacks = 0
    for _, x in ipairs(plan and plan.acts or {}) do
        if x.act == "attack" then attacks = attacks + 1 end
    end
    check(attacks, 2, "wide dim: both strike")
    check(plan and plan.branched, 1, "wide dim: the narrower kill is still branched")
    check(plan and plan.averaged, 1, "wide dim: only the wide exchange keeps the average")
end

-- test_a_game_over_is_counted_per_branch (PR #561 review): two lords, and X kills one or the
-- other, each half the time. Each alone dies at 50%, but a game over comes in every branch:
-- its chance is 1, never the 75% the two chances multiplied as if apart would give.
do
    local L1 = blue(0x01, 0, 0, 0, { minRange = false })
    local L2 = blue(0x02, 1, 0, 4, { minRange = false })
    local X = red(0x81, 9, 9, { minRange = false })
    local kill = function(t) return { enemy = 0x81, target = t, takenHit = 100, takenDmg = 99,
                                      takenHits = 1, takenCrit = 0, targetHp = 20 } end
    local o = {
        objective = { kind = "rout", gameOver = { 0x01, 0x02 } },
        enemyPhase = function()
            local a, b = kill(0x01), kill(0x02)
            local out = { a }
            out.outcomes = { { p = 0.5, strikes = { a } }, { p = 0.5, strikes = { b } } }
            return out
        end,
    }
    local _, plan = Planner.plan(B, boardOf(L1, L2, X), sightOf(o), style("careful"))
    local g = plan and plan.rank and plan.rank.game_over
    check(g and math.abs(g - 1) < 1e-9, true, "game over: summed per branch, 1 not 0.75")
end

-- test_game_over_units_are_the_games_word: the set of charIds whose death ends the game, as
-- sight.objective.gameOver lists them, the one place the planner and botrun read it from.
do
    local set = B.gameOver({ objective = { gameOver = { 0x01, 0x0F } } })
    check(set[0x01] and set[0x0F] and not set[0x02], true, "game over set: the listed charIds")
    check(next(B.gameOver({})), nil, "game over set: none without an objective")
end

-- test_admission_forgives_float_dust (PR #560 review): a death chance a few ulps over the cap
-- is at the cap, not over it.
do
    check(Planner.admits(0.05 + 1e-15, 0.05), true, "dust: at the cap")
    check(Planner.admits(0.0501, 0.05), false, "dust: a real excess is over")
end

-- test_within_cap_outranks_any_gold (FR-011, AS 1): the village's strike kills at 2RN 10
-- (2.1%). Careful (1%) leaves it at any gold; even (5%) takes it.
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
    check(at(Planner.plan(B, boardOf(A, X), sightOf(o), gifted("careful", 10000000))), "0,0",
          "admission: careful leaves a 2% village at any gold")
    local a, plan = Planner.plan(B, boardOf(A, X), sightOf(o), gifted("even", 500))
    check(at(a), "1,0", "admission: even takes it under its 5%")
    check(plan and plan.rank and plan.rank.admitted, true, "admission: the plan is admitted")
    check(plan and plan.fallback, nil, "admission: no fallback label")
end

-- test_every_plan_over_the_cap_is_a_labelled_fallback (FR-011, AS 2): X kills A wherever it
-- stands, at 2RN 80 on (0,0) and 2RN 30 on (1,0). A is no game-over unit, so careful takes the
-- smaller excess and says so.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local X = red(0x81, 9, 9, { minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        enemyPhase = function(plan)
            local b = plan.blues[1]
            return { { target = b.unit.id, takenHit = b.x == 1 and 30 or 80, takenDmg = 99,
                       takenHits = 1, takenCrit = 0 } }
        end,
    }
    local a, plan = Planner.plan(B, boardOf(A, X), sightOf(o), style("careful"))
    check(at(a), "1,0", "fallback: the smallest excess")
    check(plan and plan.fallback, "FALLBACK_SACRIFICE", "fallback: labelled")
    check(plan and plan.rank and plan.rank.admitted, false, "fallback: not admitted")
    local r = plan and plan.rank or {}
    check(math.abs((r.max_exceed or 0) - (Sight.rollChance(2, 30) - 0.01)) < 1e-9, true,
          "fallback: its excess is the death chance over the cap")
end

-- test_rank_order (FR-011 to FR-013, plan T034): the comparator, on rank tuples. Admission
-- first; among violators the chance of a game over, the largest excess, the summed excess,
-- then the largest death chance; then the admitted order: fewer forfeits, the likelier win,
-- the whole turns behind the most progress, allied greens' summed death chance, the judged
-- score, the progress itself (Nicolas, 2026-11-02); last the largest death chance, the summed
-- one, more HP left, then the plan's stable key.
do
    local function r(o)
        local t = { admitted = true, forfeits = 0, complete = 0, behind = 0, green_die = 0,
                    progress = 0, game_over = 0, max_exceed = 0, sum_exceed = 0, max_die = 0,
                    sum_die = 0, hp_left = 20, value = 0, key = "a" }
        for k, v in pairs(o) do t[k] = v end
        return t
    end
    local before = Planner.outranks
    check(before(r { max_die = 0.009, value = -50 }, r { admitted = false, value = 9e9 }), true,
          "rank: admitted beats over-cap at any value")
    -- ADR 0384, amended 2026-11-02: the comparator puts admission ahead of game_over (FR-011).
    check(before(r { game_over = 0.15, max_die = 0.15 },
                 r { admitted = false, game_over = 0, max_exceed = 0.01 }), true,
          "rank: a lord at the cap is admitted ahead of a safe lord with another unit over it")
    check(before(r { admitted = false, game_over = 0, max_exceed = 0.99 },
                 r { admitted = false, game_over = 0.02, max_exceed = 0.01 }), true,
          "rank: violators by the chance of a game over first, whatever the excess")
    check(before(r { admitted = false, game_over = 0.1 + 0.2, max_exceed = 0.2 },
                 r { admitted = false, game_over = 0.3, max_exceed = 0.9 }), true,
          "rank: a chance's float dust is no difference (0.1 + 0.2 is 0.3)")
    check(before(r { admitted = false, max_exceed = 0.1, sum_exceed = 0.3 },
                 r { admitted = false, max_exceed = 0.2, sum_exceed = 0.2 }), true,
          "rank: then by the largest excess")
    check(before(r { admitted = false, max_exceed = 0.1, sum_exceed = 0.1 },
                 r { admitted = false, max_exceed = 0.1, sum_exceed = 0.2 }), true,
          "rank: then by the summed excess")
    check(before(r { admitted = false, max_exceed = 0.1, sum_exceed = 0.1, max_die = 0.2 },
                 r { admitted = false, max_exceed = 0.1, sum_exceed = 0.1, max_die = 0.3 }), true,
          "rank: then by the largest death chance")
    local tied = { admitted = false, max_exceed = 0.1, sum_exceed = 0.1, max_die = 0.2 }
    tied.value = 5
    local more = r(tied)
    tied.value = 1
    check(before(more, r(tied)), true, "rank: then the admitted order")
    check(before(r { value = 2, max_die = 0.009 }, r { value = 1 }), true,
          "rank: among the admitted, the admitted order before the death chance")
    check(before(r { forfeits = 0, complete = 0 }, r { forfeits = 1, complete = 1 }), true,
          "rank: fewer forfeits before the win (a village open outranks the Seize)")
    check(before(r { complete = 1, behind = 3 }, r { complete = 0 }), true,
          "rank: the win before progress")
    check(before(r { behind = 0, progress = 0.2, green_die = 1 },
                 r { behind = 1, progress = -1, green_die = 0 }), true,
          "rank: a green is no tie-break a whole turn behind")
    check(before(r { progress = 0.2, green_die = 0 }, r { progress = 0.9, green_die = 1 }), true,
          "rank: within the turn, the green's survival before the progress")
    check(before(r { progress = 0.9, value = 0 }, r { progress = 0.2, value = 500 }), true,
          "rank: within the turn, the progress before the judged score")
    check(before(r { progress = 0.9, value = 500 }, r { progress = 0.9, value = 0 }), true,
          "rank: the judged score breaks a progress tie")
    check(before(r { progress = 0.9 - 1e-12, value = 500 }, r { progress = 0.9, value = 0 }), true,
          "rank: the judged score breaks a progress tie within float dust")
    check(before(r { progress = 0.9, value = 0 }, r { progress = 0.9 - 1e-12, value = 0 }), false,
          "rank: then progress, float dust no difference")
    check(before(r { progress = 0.9 }, r { progress = 0.2 }), true, "rank: then progress")
    check(before(r { value = 500, max_die = 0.009 }, r { value = 0 }), true,
          "rank: the judged score before the death chance")
    -- #641: a win chance under M.GONE is no lead, the judged score decides; one at it still is
    check(before(r { complete = 0.0009, value = 0 }, r { complete = 0, value = 340 }), false,
          "rank: a 0.09% win chance does not outrank a plan worth more")
    check(before(r { complete = 0, value = 340 }, r { complete = 0.0009, value = 0 }), true,
          "rank: the plan worth more outranks a 0.09% win chance")
    check(before(r { complete = Planner.GONE, value = 0 }, r { complete = 0.4, value = 340 }),
          true, "rank: a win at M.GONE outranks a plan worth more")
    check(before(r { complete = 0.9 }, r { complete = 0.6 }), true,
          "rank: above M.GONE the likelier win first")
    check(before(r { complete = 0.3 }, r { complete = 0.1 + 0.2 }), false,
          "rank: a win chance's float dust is no difference")
    local ok = pcall(before, r {}, { admitted = true })
    check(ok, false, "rank: a rank compared before M.rebase raises")
    check(before(r { max_die = 0.001 }, r { max_die = 0.002 }), true, "rank: ties, largest death")
    check(before(r { sum_die = 0.001 }, r { sum_die = 0.002 }), true, "rank: ties, summed death")
    check(before(r { hp_left = 21 }, r { hp_left = 20 }), true, "rank: ties, more HP left")
    check(before(r { key = "a" }, r { key = "b" }), true, "rank: ties, the stable key")
    check(before(r {}, r {}), false, "rank: a plan does not outrank its equal")
end

-- The ch01 stall's shape (FR-016, plan T048), no chapter named: every enemy gone, the lord L
-- (the only unit that may Seize) sent to a village a turn up (his whole move) while the gate is far east.
-- `reach` is L's move this turn; the field is open ground (Manhattan) to whichever goal.
local function lordSentAway(reach, extra)
    local L = blue(0x01, 0, 12, 7, { charId = 0x0F, minRange = false })
    local units = { L }
    for _, u in ipairs(extra or {}) do units[#units + 1] = u end
    local o = {
        objective = { kind = "seize", tile = { x = 21, y = 7 }, lord = 0x0F },
        reach = { [0x01] = reach },
        field = function(goal)
            local f = {}
            for y = 0, 9 do
                f[y] = {}
                for x = 0, 22 do f[y][x] = math.abs(x - goal.x) + math.abs(y - goal.y) end
            end
            return f
        end,
        explorable = { { x = 12, y = 0, kind = "visit" } },
        canExplore = { [0x01] = { ["12,0"] = "visit" }, [0x02] = { ["12,0"] = "visit" } },
        enemyPhase = function() return {} end,
    }
    return units, o
end

-- test_a_step_toward_the_goal_beats_holding (AS 3): the House is worth a few points and the
-- gate the lord's whole way to the win, so by the judged score each step north cost more of
-- the gate than it gained of the House: here he walked east, off the goal he was sent to, and
-- in Manchego Stars ch01, with no tile east on his menu, he held until the run stopped (attempts 1
-- and 3). By the rank's progress, the step toward his goal comes first.
do
    local units, o = lordSentAway(tiles({ 12, 7 }, { 12, 2 }, { 15, 7 }))
    local board = boardOf(table.unpack(units))
    local a, plan = Planner.plan(B, board, sightOf(o), gifted("careful", 100))
    check(at(a), "12,2", "progress: the lord steps toward the House, not holding")
    check(plan and plan.goals[1] and plan.goals[1].x .. "," .. plan.goals[1].y, "12,0",
          "progress: he is sent to the House")
    check(plan and math.abs(plan.rank.progress - 1) < 1e-9, true,
          "progress: five steps nearer, a whole turn (MOV 5)")
    -- the beam keeps one plan, the judged score's (east, toward the gate): only the advance,
    -- judged beside it, has the step north
    local beam = Planner.BEAM
    Planner.BEAM = 1
    units, o = lordSentAway(tiles({ 12, 7 }, { 12, 2 }, { 15, 7 }))
    a, plan = Planner.plan(B, boardOf(table.unpack(units)), sightOf(o), gifted("careful", 100))
    Planner.BEAM = beam
    check(at(a) .. " " .. tostring(plan and plan.kind), "12,2 advance",
          "progress: the advance is judged where the beam cut the step")
end

-- test_no_progressing_step_reassigns_the_goal (FR-016): L, sent to the House, has moves but
-- none nearer it (a unit in its way north, say). One turn so is a unit in the way: L keeps
-- the House and the turn is recorded. Blocked since an earlier turn, the House goes to M,
-- whose step north is nearer, and L's way is the objective's. Once L can step north again, the
-- record lifts.
do
    local M = blue(0x02, 1, 10, 7, { minRange = false })
    local units, o = lordSentAway(tiles({ 12, 7 }, { 13, 8 }, { 14, 7 }), { M })
    o.reach[0x02] = tiles({ 10, 7 }, { 10, 6 })
    local sent = { { id = 0x01, x = 12, y = 0 } }
    local _, ctx = B.candidates(boardOf(table.unpack(units)), sightOf(o), style("careful"),
                                { sent = sent })
    check(ctx.exploreGoal[0x01] and ctx.exploreGoal[0x01].y, 0,
          "reassign: one blocked turn keeps the goal")
    local rec = ctx.stuck["1>12,0"]
    check(rec and rec.since, 1, "reassign: the blocked turn is recorded")
    local board = boardOf(table.unpack(units))
    board.turn = 2
    _, ctx = B.candidates(board, sightOf(o), style("careful"), { sent = sent, stuck = ctx.stuck })
    check(ctx.exploreGoal[0x01], nil, "reassign: blocked since an earlier turn, L is sent again")
    check(ctx.exploreGoal[0x02] and ctx.exploreGoal[0x02].x .. "," .. ctx.exploreGoal[0x02].y,
          "12,0", "reassign: the House goes to the unit that can step toward it")
    local held = ctx.stuck
    units, o = lordSentAway(tiles({ 12, 7 }, { 12, 2 }), { M })
    o.reach[0x02] = tiles({ 10, 7 }, { 10, 6 })
    board = boardOf(table.unpack(units))
    board.turn = 3
    _, ctx = B.candidates(board, sightOf(o), style("careful"), { sent = sent, stuck = held })
    check(ctx.stuck["1>12,0"], nil, "reassign: the way open again, the record lifts")
    -- boxed in (no act off its own tile), L keeps its goal: no other gets it anywhere
    units, o = lordSentAway(tiles({ 12, 7 }))
    _, ctx = B.candidates(boardOf(table.unpack(units)), sightOf(o), style("careful"),
                          { sent = { { id = 0x01, x = 12, y = 0 } } })
    check(ctx.exploreGoal[0x01] and ctx.exploreGoal[0x01].y, 0,
          "reassign: a boxed-in unit keeps it")
end

-- test_a_block_on_a_recruit_lifts_beside_it (FR-016): A was found blocked from recruit T on an
-- earlier turn. T's tile is one no player unit ends on, so no tile is ever nearer it than the
-- tiles beside it: A, beside T now, has none nearer. It can end beside T, where the Talk is
-- made, so the record lifts and A is still sent to T.
do
    local A = blue(0x01, 0, 4, 0, { minRange = false })
    local T = blue(0x30, 5, 5, 0, { faction = "green", minRange = false })
    local o = {
        reach = { [0x01] = tiles({ 4, 0 }, { 3, 0 }) },
        talk = { [0x01] = { [0x30] = true } },
        field = function(goal)
            local f = {}
            for y = 0, 9 do
                f[y] = {}
                for x = 0, 14 do f[y][x] = math.abs(x - goal.x) + math.abs(y - goal.y) end
            end
            return f
        end,
    }
    local board = boardOf(A, T)
    board.turn = 3
    local _, ctx = B.candidates(board, sightOf(o), style("careful"),
                                { stuck = { ["1>5,0"] = { id = 0x01, x = 5, y = 0, since = 1 } } })
    check(ctx.stuck["1>5,0"], nil, "reassign: a unit that can end beside its recruit is not blocked")
    check(ctx.exploreGoal[0x01] and ctx.exploreGoal[0x01].x, 5, "reassign: and it is sent to it")
    -- an enemy that is no recruit, standing on a village A was sent to: beside it is not there
    local V = red(0x81, 5, 0, { minRange = false })
    o.talk, o.explorable = nil, { { x = 5, y = 0, kind = "visit" } }
    o.canExplore = { [0x01] = { ["5,0"] = "visit" } }
    board = boardOf(A, V)
    board.turn = 3
    _, ctx = B.candidates(board, sightOf(o), gifted("careful", 1000),
                          { sent = { { id = 0x01, x = 5, y = 0 } },
                            stuck = { ["1>5,0"] = { id = 0x01, x = 5, y = 0, since = 1 } } })
    check(ctx.stuck["1>5,0"] ~= nil and ctx.exploreGoal[0x01] == nil, true,
          "reassign: an enemy on the goal keeps the block, and the goal goes")
end

-- test_after_a_visit_the_march_returns_to_the_objective (FR-016): the House taken (explored),
-- the lord sent there last turn marches on the gate.
do
    local units, o = lordSentAway(tiles({ 12, 7 }, { 12, 2 }, { 15, 7 }))
    local cands, ctx = B.candidates(boardOf(table.unpack(units)), sightOf(o), style("careful"),
                                    { sent = { { id = 0x01, x = 12, y = 0 } },
                                      explored = { ["12,0"] = true } })
    check(ctx.exploreGoal[0x01], nil, "after a visit: no longer sent")
    local march
    for _, a in ipairs(cands[1].acts) do
        if a.why == "march" then march = at(a) end
    end
    check(march, "15,7", "after a visit: the march heads for the gate")
end

-- test_candidate_order_is_frozen (FR-013): the order Bot.candidates proposes acts in, for a
-- fixed board, is pinned. It orders the beam, never the complete plans: a change to it is a
-- change to the instrument, so it fails here first.
do
    local units, o = threeOpenKills()
    local cands = B.candidates(boardOf(table.unpack(units)), sightOf(o), style("careful"))
    local out = {}
    for _, c in ipairs(cands) do
        for _, a in ipairs(c.acts) do
            out[#out + 1] = string.format("%d:%s@%d,%d>%s", c.unit.id, a.act, a.move.x, a.move.y,
                                          tostring(a.targetId))
        end
    end
    check(table.concat(out, " "), "1:attack@0,2>129 1:wait@0,2>nil 2:attack@0,4>130 "
          .. "2:wait@0,4>nil 3:attack@0,6>131 3:wait@0,6>nil", "candidates: the frozen order")
end

-- ── The lookahead (PR-E: FR-017, FR-018) ──────────────────────────────────────────────────

-- test_lookahead_triggers (T057): a door opened or a wall struck, and a step into the reach of a
-- boss in sight or remembered, from outside it; nothing else (no arrival trigger: ADR 0389).
do
    local A = blue(0x01, 0, 0, 0)
    local K = red(0x81, 5, 0, { isBoss = true, minRange = 1, maxRange = 1 })
    local byId = { [0x01] = A, [0x81] = K }
    local sight = sightOf({ reach = { [0x81] = tiles({ 5, 0 }) } })
    local function plan(...) return { acts = { ... } } end
    local function act(x, kind, extra)
        local a = { unitId = 0x01, move = { x = x, y = 0 }, act = kind or "wait" }
        for k, v in pairs(extra or {}) do a[k] = v end
        return a
    end
    local function why(fin, enemies)
        local t = Planner.triggers(fin, byId, enemies or {}, sight)
        return t and table.concat(t, ",") or "none"
    end
    check(why({ plan(act(1)) }), "none", "lookahead: a plain move is no transition")
    check(why({ plan(act(1)), plan(act(1, "door")) }), "breach",
          "lookahead: one finalist's door is the decision's trigger")
    check(why({ plan(act(1, "attack", { obstacle = { x = 2, y = 0 } })) }), "breach",
          "lookahead: a wall struck is a breach")
    check(why({ plan(act(4)) }, { K }), "boss", "lookahead: the first step into the boss's reach")
    A.x = 4
    check(why({ plan(act(4)) }, { K }), "none", "lookahead: already in its reach is no first entry")
    A.x = 0
    -- which bosses count is the caller's list (ctx.threats: in sight, or remembered, ADR 0399);
    -- a fogged boss given is one a retry remembers, so it triggers
    K.fogged = true
    check(why({ plan(act(4)) }, { K }), "boss", "lookahead: a remembered boss in fog is a boss")
    K.fogged = nil
end

-- A at (0,0) is pulled to (1,0) toward a village; the next enemy phase leaves (1,0) alone, the
-- one after it kills a unit there for sure (o.nextPhase). `boss`: a boss stands at (2,0), so
-- (1,0) is a first step into its reach -- the lookahead's trigger. `replyPhase`: the second
-- phase with the army's reply played between (sightOf's), the hold's when nil.
local function looksAhead(boss, replyPhase)
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local X = red(0x81, 0, 9, { minRange = false })
    local K = boss and red(0x82, 2, 9, { isBoss = true, minRange = 1, maxRange = 1 })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x82] = tiles({ 1, 1 }) },
        field = function(t)
            return t.x == 9 and t.y == 0 and { [0] = { [0] = 40, [1] = 20 } } or nil
        end,
        explorable = { { x = 9, y = 0, kind = "visit" } },
        canExplore = { [0x01] = { ["9,0"] = "visit" } },
        enemyPhase = function() return {} end,
        nextPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.x == 1 then
                    return { { target = b.unit.id, takenHit = 100, takenDmg = 99, takenHits = 1,
                               takenCrit = 0 } }
                end
            end
            return {}
        end,
        replyPhase = replyPhase,
    }
    return boardOf(A, X, K), sightOf(o), gifted("careful", 1000)
end

-- test_lookahead_triggers_on_a_remembered_boss (ADR 0399): a boss in fog that a retry remembers
-- (sight.knows) is a boss whose reach a step enters, so the lookahead is triggered as for one in
-- sight; one the fog hides and no attempt showed triggers nothing.
do
    local function fogged(remembered)
        local board, sight, st = looksAhead(true)
        for _, u in ipairs(board.units) do
            if u.id == 0x82 then u.fogged = true end
        end
        if remembered then sight.knows = function(u) return u.id == 0x82 end end
        return board, sight, st
    end
    local board, sight, st = fogged(true)
    local a, plan = Planner.plan(B, board, sight, st)
    check(at(a), "0,0", "remembered boss: the second phase's sure death keeps A back")
    check(plan.lookahead.extended, true, "remembered boss: the step into its reach triggers the lookahead")
    board, sight, st = fogged(false)
    check(at(Planner.plan(B, board, sight, st)), "1,0", "unseen boss: no trigger, the march goes")
end

-- test_lookahead_extends_all_finalists_or_none (T058, AS 1 and AS 2): with room, every
-- finalist meets the second phase, one call each, and the death it finds feeds the rank; with
-- too little, none does, the plan keeps the first phase's horizon and says it was skipped.
do
    local board, sight, st = looksAhead(nil)
    check(at(Planner.plan(B, board, sight, st)), "1,0", "lookahead: no trigger, the march goes")
    check(sight.asked, nil, "lookahead: no trigger asks no second phase")

    board, sight, st = looksAhead(true)
    local a, plan, cost = Planner.plan(B, board, sight, st)
    check(at(a), "0,0", "lookahead: the second phase's sure death keeps A back")
    local fin = 0
    for _, c in ipairs(plan.considered) do
        if c.extended then fin = fin + 1 end
    end
    check(#sight.asked, fin, "lookahead: one call a finalist")
    check(fin >= 2, true, "lookahead: every finalist was extended, not only the triggering one")
    check(plan.lookahead.calls, fin, "lookahead: the plan counts its calls")
    check(plan.lookahead.extended, true, "lookahead: and says it extended")
    check(cost.look.calls, fin, "lookahead: the call's cost counts them too")
    check(cost.look.triggered + cost.look.extended, 2, "lookahead: triggered and extended")
    local over = false
    for _, c in ipairs(plan.considered) do
        if c.extended and not c.rank.admitted then over = true end
    end
    check(over, true, "lookahead: the finalist at (1,0) dies in the second phase, over the cap")
    -- the HP it loses there leaves the rank too, and the judged score pays the death; the
    -- trace's `judged` stays the next phase's alone
    local hold, march
    for _, c in ipairs(plan.considered) do
        if c.extended and c.rank.admitted then hold = hold or c end
        if c.extended and not c.rank.admitted then march = march or c end
    end
    check(march.rank.hp_left < hold.rank.hp_left, true, "lookahead: the second phase's HP lost")
    check(march.rank.value < march.judged, true, "lookahead: the value pays the second death")
    check(hold.rank.value, hold.judged, "lookahead: a safe hold pays nothing more")
    check(plan.protected[1].second, 0, "lookahead: holding at (0,0) is safe in the second phase")

    board, sight, st = looksAhead(true)
    a, plan, cost = Planner.plan(B, board, sight, st, { budget = { attempt = 1 } })
    check(at(a), "1,0", "lookahead: an exhausted budget keeps the original horizon")
    check(sight.asked, nil, "lookahead: and asks no finalist")
    check(plan.lookahead.skipped, true, "lookahead: tagged skipped")
    check(cost.look.skipped_budget, 1, "lookahead: counted as skipped")
    board, sight, st = looksAhead(true)
    a, plan = Planner.plan(B, board, sight, st, { budget = { decision = 1 } })
    check(plan.lookahead.skipped, true, "lookahead: a decision budget below the finalists skips")
    check(Planner.LOOK_DECISION .. "/" .. Planner.LOOK_ATTEMPT, "8/128",
          "lookahead: 8 calls a decision, 128 an attempt (FR-018, #570)")
    -- the most a tuning game wanted (ours-ch03 seed 1002: 19 triggered decisions, each its
    -- finalists' calls) leaves the next decision room to extend: at 32 the boss fight was
    -- judged one phase deep (#570)
    board, sight, st = looksAhead(true)
    a, plan = Planner.plan(B, board, sight, st,
                           { budget = { attempt = Planner.LOOK_ATTEMPT - 19 * Planner.FINAL } })
    check(plan.lookahead.extended, true, "lookahead: room left after ours-ch03's 19 triggers")
end

-- test_the_second_phase_reads_the_army_s_reply (ADR 0389's amendment of 2026-11-17): every
-- second phase is asked with the army's reply (sight.nextPhase's `reply`); opts.reply = "hold"
-- (PT_REPLY=hold) asks the hold instead. Here the hold's second phase kills A at (1,0) and the
-- reply's spares it: the march goes, and the hold keeps A back.
do
    local played = { kills = {}, steps = { { unit = 0x01, x = 0, y = 0 } } }
    local board, sight, st = looksAhead(true, function() return { reply = played } end)
    local a, plan = Planner.plan(B, board, sight, st)
    check(at(a), "1,0", "reply: the reply's second phase spares the march, so it goes")
    check(plan.lookahead.reply, played, "reply: what it played is in the played plan's trace")
    check(sight.replied, #sight.asked, "reply: every second phase is the reply's")
    check(plan.lookahead.calls, #sight.asked, "reply: one call a finalist, as the hold's")
    board, sight, st = looksAhead(true, function() return {} end)
    a = Planner.plan(B, board, sight, st, { reply = "hold" })
    check(at(a), "0,0", "reply: PT_REPLY=hold reads the hold, which keeps A back")
    check(sight.replied, nil, "reply: and never asks the reply")
end

-- test_second_read_prices_the_reply_s_counter (PR 637 review): a kill in the army's reply costs
-- the killer the counter's HP between the phases; Planner.secondRead counts it in `lost`, as the
-- second phase's own strikes, so a plan whose reply bleeds a unit ranks below one that does not.
do
    local struck = function(_, live)
        local res = {}
        for _, u in ipairs(live) do res[u.id] = { d = 0, t = 3 } end
        return res, 1
    end
    local r = { hp = { [0x01] = 13 },
                reply = { kills = { { unit = 0x01, enemy = 0x81, lost = 7 } } } }
    local second, lost, over = Planner.secondRead(r, { { id = 0x01, charId = 1 } }, struck)
    check(lost[0x01], 10, "secondRead: the reply's counter (7) and the second phase's strikes (3)")
    check(second[0x01] .. "/" .. over, "0/0", "secondRead: no death read from the counter alone")
    -- #641: the win the second phase reads, for the enemy `ends` names only: killed by the
    -- reply at its chance, or felled by our counter to its own strike in the second phase
    local function boss(id) return id == 0x81 end
    r.reply.kills[1].p = 0.81
    check(select(4, Planner.secondRead(r, { { id = 0x01, charId = 1 } }, struck)), 0,
          "secondRead: no win when no enemy's death ends the chapter")
    check(select(4, Planner.secondRead(r, { { id = 0x01, charId = 1 } }, struck, nil, boss)),
          0.81, "secondRead: the reply's kill of the boss is the win at its chance")
    -- the killer lives the first phase 90% of the time: its kill counts that far (review of
    -- PR #646)
    local won = select(4, Planner.secondRead(r, { { id = 0x01, charId = 1 } }, struck, nil, boss,
                                             { [0x01] = 0.9 }))
    check(math.abs(won - 0.729) < 1e-9, true,
          "secondRead: the reply's kill counts as far as its killer lives the first phase")
    local felled = { hp = { [0x01] = 13 },
                     outcomes = { { p = 0.5, strikes = { { enemy = 0x81, target = 0x01,
                                                           felled = 0.6 } } },
                                  { p = 0.5, strikes = { { enemy = 0x82, target = 0x01,
                                                           felled = 1 } } } } }
    won = select(4, Planner.secondRead(felled, { { id = 0x01, charId = 1 } }, struck, nil, boss))
    check(math.abs(won - 0.3) < 1e-9, true,
          "secondRead: the boss felled by our counter in the second phase, over its ways")
    -- a Rout with two reds left: the first phase's counter removed 0x82 (r.fell), so 0x81 is
    -- the last, and our counter felling it in the second phase ends the map
    local byId = { [0x81] = { id = 0x81, faction = "red" }, [0x82] = { id = 0x82, faction = "red" } }
    local rout = Planner.endsIn("rout", 2, byId)
    check(rout(0x81), false, "endsIn: a Rout's enemy is not its last while another stands")
    check(rout(0x81, { [0x82] = true }), true, "endsIn: it is once the other is gone")
    local last = { hp = { [0x01] = 13 }, fell = { 0x82 },
                   outcomes = { { p = 1, strikes = { { enemy = 0x81, target = 0x01, felled = 0.5 } } } } }
    won = select(4, Planner.secondRead(last, { { id = 0x01, charId = 1 } }, struck, nil, rout))
    check(math.abs(won - 0.5) < 1e-9, true,
          "secondRead: a Rout's last enemy, the first phase's kill counted gone")
    -- a Seize map: the throne's holder's death opens the Seize and ends nothing (ADR 0405)
    check(Planner.endsIn("seize", 0, { [0x81] = { id = 0x81, isBoss = true } })(0x81), false,
          "endsIn: on a Seize map no death ends the chapter")
    check(Planner.endsIn("boss", 0, { [0x81] = { id = 0x81, isBoss = true } })(0x81), true,
          "endsIn: a Defeat Boss map's boss")
    check(math.abs(Planner.either(0.5, 0.2) - 0.6) < 1e-9, true, "either: 1 - (1 - a)(1 - b)")
end

-- test_over_the_cap_this_phase_comes_first (#510 T100b, Manchego Stars ch03 careful seed 3010 turn
-- 18, replayed): every plan is over the cap. The march to (1,0) may die in the next enemy phase
-- (70% shown); the hold at (0,0) is safe there, and dies only in the lookahead's second phase,
-- which has it stand still for another round (the guess the records found far too high: 0 of
-- 8 such readings came true). Over the cap the next phase's own chances rank first, the second
-- phase's only break their ties: the hold is played. Before, the larger two-phase number
-- decided, and the march (the smaller) was played and died.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local X = red(0x81, 0, 9, { minRange = false })
    local K = red(0x82, 2, 9, { isBoss = true, minRange = 1, maxRange = 1 })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x82] = tiles({ 1, 1 }) },
        field = function(t)
            return t.x == 9 and t.y == 0 and { [0] = { [0] = 40, [1] = 20 } } or nil
        end,
        explorable = { { x = 9, y = 0, kind = "visit" } },
        canExplore = { [0x01] = { ["9,0"] = "visit" } },
        enemyPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.x == 1 then
                    return { { enemy = 0x82, target = b.unit.id, takenHit = 70, takenDmg = 99,
                               takenHits = 1, takenCrit = 0 } }
                end
            end
            return {}
        end,
        nextPhase = function(plan)
            for _, b in ipairs(plan.blues) do
                if b.x == 0 then
                    return { { enemy = 0x82, target = b.unit.id, takenHit = 100, takenDmg = 99,
                               takenHits = 1, takenCrit = 0 } }
                end
            end
            return {}
        end,
    }
    local a, plan = Planner.plan(B, boardOf(A, X, K), sightOf(o), gifted("careful", 1000))
    check(plan.lookahead.extended, true, "over the cap: the boss trigger asked the second phase")
    local hold, march
    for _, c in ipairs(plan.considered) do
        if c.extended and c.acts[1]:match("@0,0>") then hold = hold or c end
        if c.extended and c.acts[1]:match("@1,0>") then march = march or c end
    end
    check(hold ~= nil and march ~= nil, true, "over the cap: both the hold and the march judged")
    check(hold.rank.admitted or march.rank.admitted, false, "over the cap: neither is admitted")
    -- the gap the order turns on, both ways: the two-phase numbers favour the march, the next
    -- phase's favour the hold
    check(march.rank.max_die < hold.rank.max_die - 0.1, true,
          "over the cap: the march's two-phase chance is the smaller")
    check(hold.rank.first_max_exceed, 0, "over the cap: the hold is safe in the next phase")
    check(march.rank.first_max_exceed > 0.3, true, "over the cap: the march is not")
    check(at(a), "0,0", "over the cap: the next phase's chance ranks first, the hold is played")
    check(plan.protected[1].first, 0, "over the cap: the record keeps the next phase's chance")
    check(plan.protected[1].die > 0.99, true, "over the cap: and the two-phase one")
end

-- test_a_benched_unit_only_waits (#510, the benched-twin experiment): a unit the style
-- benches (style.bench, PT_BENCH) is offered one act, a wait on its own tile, and the plan
-- leaves it there; unbenched, the same unit marches.
do
    local board, sight, st = looksAhead(nil)
    local function actsOf(cands)
        local out = {}
        for _, c in ipairs(cands) do
            for _, a in ipairs(c.acts) do out[#out + 1] = a.act .. "@" .. a.move.x .. "," .. a.move.y end
        end
        return out
    end
    check(#actsOf(B.candidates(board, sight, st)) > 1, true, "bench: unbenched, A has acts")
    check(at(Planner.plan(B, board, sight, st)), "1,0", "bench: unbenched, A marches")
    board, sight, st = looksAhead(nil)
    st.bench = { 0x01 }
    check(table.concat(actsOf(B.candidates(board, sight, st)), " "), "wait@0,0",
          "bench: a benched unit is offered only a wait where it stands")
    check(at(Planner.plan(B, board, sight, st)), "0,0", "bench: and the plan leaves it there")
    -- decide (the greedy style's, and the planner's fallback) holds it too (PR #585 review)
    -- (A beside an enemy its blow surely kills: unbenched, decide strikes it)
    local function decided(aggression, bench)
        local A = blue(0x01, 0, 0, 0)
        local E = red(0x81, 1, 0, { hp = 5 })
        local s = sightOf({ reach = { [0x01] = tiles({ 0, 0 }) },
                            fc = { [0x01] = { [0x81] = { ["0,0"] = fc { hit = 100, dmg = 12,
                                                                       hits = 1 } } } } })
        local sty = style(aggression)
        sty.bench = bench
        local a = B.decide(boardOf(A, E), s, sty)
        return a and (a.act .. "@" .. a.move.x .. "," .. a.move.y)
    end
    for _, aggression in ipairs({ "greedy", "careful" }) do
        check(decided(aggression, nil), "attack@0,0",
              "bench: unbenched, " .. aggression .. "'s decide strikes")
        check(decided(aggression, { 0x01 }), "wait@0,0",
              "bench: benched, " .. aggression .. "'s decide holds A where it stands")
    end
end

-- test_lookahead_sees_only_the_board (T059): the second phase is asked on the staged board
-- alone -- our units, the enemies gone, the enemies' HP and the weapon uses their counters
-- spent (#644), the doors and walls it opens, the units it carries (Rescue) -- and
-- nothing about a turn to come:
-- an arrival is a trigger, never a unit placed on it.
do
    local board, sight, st = looksAhead(true)
    Planner.plan(B, board, sight, st)
    local keys = {}
    for k in pairs(sight.asked[1]) do keys[#keys + 1] = k end
    table.sort(keys)
    check(table.concat(keys, ","), "blues,carry,gone,opened,redWear,reds", "lookahead: the staged board, nothing more")
end

-- test_a_remembered_enemy_is_planned_against (ADR 0399): a fogged red the retry remembers
-- (sight.knows) is in the exposure a candidate is judged by, and among the enemies the plan was
-- made against, so a death by it is never graded `fog`. Attempt 1 (no memory): neither.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local X = red(0x81, 0, 9, { minRange = false })
    local F = red(0x83, 2, 0, { fogged = true, charId = 0x50 })
    local o = { reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x83] = tiles({ 2, 0 }, { 1, 0 }, { 0, 0 }) },
                danger = { ["0,0"] = 1, ["1,0"] = 1 }, enemyPhase = function() return {} end }
    -- whose strike on A the candidates' exposure asks for (sight.strike, without `from`)
    local function strikers(sight)
        local asked, strike = {}, sight.strike
        sight.strike = function(u, e, x, y, slot, from)
            if not from and u.id == A.id then asked[e.id] = true end
            return strike(u, e, x, y, slot, from)
        end
        B.candidates(boardOf(A, X, F), sight, style("careful"))
        return asked[0x83] and tostring(0x83) or ""
    end
    o.known = { [0x83] = true }
    check(strikers(sightOf(o)), tostring(0x83), "remembered: its strike is in the exposure")
    local _, plan = Planner.plan(B, boardOf(A, X, F), sightOf(o), style("careful"))
    check(plan.enemies[0x83], true, "remembered: the plan was made against it")
    o.known = nil
    check(strikers(sightOf(o)), "", "no memory: the fogged red strikes nothing")
    local _, plain = Planner.plan(B, boardOf(A, X, F), sightOf(o), style("careful"))
    check(plain.enemies[0x83], nil, "no memory: the fogged red is not among the plan's enemies")
end

-- test_lookahead_counts_a_green_and_ranks_the_list_once (review of #568): an allied green the
-- second phase kills is paid in the rank's green_die and value, not only the protected units;
-- and the played plan heads `considered`, the finalists before the plans never asked the second
-- phase, every `behind` measured from the one best progress.
do
    local A = blue(0x01, 0, 0, 0, { minRange = false })
    local G = blue(0x30, 5, 3, 3, { faction = "green", hp = 10, minRange = false })
    local X = red(0x81, 9, 9, { minRange = false })
    local K = red(0x82, 2, 9, { isBoss = true, minRange = 1, maxRange = 1 })
    local o = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x82] = tiles({ 1, 1 }) },
        field = function(t)
            return t.x == 9 and t.y == 0 and { [0] = { [0] = 40, [1] = 20 } } or nil
        end,
        explorable = { { x = 9, y = 0, kind = "visit" } },
        canExplore = { [0x01] = { ["9,0"] = "visit" } },
        enemyPhase = function() return {} end,
        nextPhase = function(plan)
            local hp = { [0x30] = 10 }
            for _, b in ipairs(plan.blues) do hp[b.unit.id] = b.hp end
            return { { enemy = 0x81, target = 0x30, takenHit = 100, takenDmg = 99, takenHits = 1,
                       takenCrit = 0, targetHp = 10 }, hp = hp }
        end,
    }
    local a, plan = Planner.plan(B, boardOf(A, G, X, K), sightOf(o), gifted("careful", 1000))
    check(plan.lookahead.extended, true, "lookahead: extended")
    for _, c in ipairs(plan.considered) do
        if c.extended then
            check(c.rank.green_die > 0.99, true, "lookahead: the green's second-phase death is paid")
        end
    end
    check(plan.considered[1].acts[1], plan.rank.key:match("^%S+"),
          "lookahead: the played plan heads the list")
    local seenPlain = false
    for _, c in ipairs(plan.considered) do
        if not c.extended then seenPlain = true end
        if c.extended and seenPlain then
            check(false, true, "lookahead: a finalist sorted below a plan never extended")
        end
        check(c.rank.behind ~= nil, true, "lookahead: every rank is rebased")
    end
end

-- test_plan_record_carries_the_audit_fields (T076, FR-020): how many acts were offered; each
-- plan judged says why it was not played (the played one: nothing, and `played`) and the
-- chances of the ways its phase went; the enemies seen and fogged; and whether the lookahead's
-- budget ran out.
do
    local board, sight, st = looksAhead(true)
    board.units[#board.units + 1] = red(0x83, 9, 5, { fogged = true, minRange = false })
    local _, plan = Planner.plan(B, board, sight, st)
    local cands = B.candidates(board, sight, st)
    local n = 0
    for _, c in ipairs(cands) do n = n + #c.acts end
    check(plan.audit.offered_n, n, "audit: how many acts were offered (the count, not the keys)")
    check(plan.audit.offered, nil, "audit: no key list in every plan event (review #18)")
    check(plan.audit.visibility.seen .. "/" .. plan.audit.visibility.fogged, "2/1",
          "audit: the red units seen and fogged")
    check(plan.audit.budget.exhausted, false, "audit: the lookahead had room")
    check(plan.audit.budget.averaged, 0, "audit: no uncertain kill left to the average")
    local why = {}
    for i, c in ipairs(plan.considered) do
        if i == 1 then
            check(c.played, true, "audit: the played plan heads the list, marked")
            check(c.rejected, nil, "audit: and is rejected for nothing")
            check(table.concat(c.acts, " "), table.concat(Planner.keysOf(plan), " "),
                  "audit: its key list is the plan's")
        else
            check(c.played, nil, "audit: only one plan played")
            why[c.rejected] = true
            check(c.rejected == (c.rank.admitted and "outranked" or "over_cap"), true,
                  "audit: a plan over the cap is over_cap, one under it outranked")
        end
        check(#c.weights >= 1 and math.abs(c.weights[1] - 1) < 1e-9, true,
              "audit: one way, all the weight")
    end
    check(why.over_cap, true, "audit: the march the second phase kills is over_cap")
    -- no transition, no second phase: both plans within the cap, the hold ranked below
    board, sight, st = looksAhead(nil)
    _, plan = Planner.plan(B, board, sight, st)
    check(plan.considered[2] and plan.considered[2].rejected, "outranked",
          "audit: a plan within the cap the rank put below is outranked")

    board, sight, st = looksAhead(true)
    _, plan = Planner.plan(B, board, sight, st, { budget = { attempt = 1 } })
    check(plan.audit.budget.exhausted, true, "audit: a skipped lookahead is an exhausted budget")
end

-- test_deep_diagnostic_adds_one_cycle (FR-019): opts.diag = "deep" sends every finalist to the
-- lookahead's second phase -- the same machinery, no trigger and no budget asked -- and the
-- plan says so; without it the same board asks nothing.
do
    local board, sight, st = looksAhead(nil)
    local a, plan = Planner.plan(B, board, sight, st, { diag = "deep", budget = { attempt = 0 } })
    check(sight.asked ~= nil and #sight.asked >= 2, true,
          "deep: every finalist meets a second phase")
    check(plan.lookahead.deep and plan.lookahead.extended, true, "deep: tagged and extended")
    check(plan.lookahead.trigger, nil, "deep: no transition was found, none is claimed")
    check(at(a), "0,0", "deep: the second phase's death keeps A back")
    board, sight, st = looksAhead(nil)
    _, plan = Planner.plan(B, board, sight, st)
    check(sight.asked == nil and plan.lookahead.deep == nil, true, "deep: off by default")
end

-- test_unkey_inverts_key (review #8): Planner.unkey reads back every act kind's key -- a unit
-- target, a wall, none, a negative tile -- as the act's identity, and keys back to the same
-- string, so botrun's forced replay has one spelling of a key, the planner's.
do
    local acts = {
        { unitId = 1, act = "attack", move = { x = 3, y = 4 }, targetId = 0x81 },
        { unitId = 1, act = "attack", move = { x = 3, y = 4 }, obstacle = { x = 5, y = 6 } },
        { unitId = 2, act = "wait", move = { x = 0, y = 0 } },
        { unitId = 2, act = "talk", move = { x = 1, y = 0 }, targetId = 0x40 },
        { unitId = 3, act = "staff", move = { x = 2, y = 2 }, targetId = 2 },
        { unitId = 3, act = "item", move = { x = 2, y = 2 } },
        { unitId = 4, act = "seize", move = { x = 9, y = 1 } },
        { unitId = 4, act = "visit", move = { x = 7, y = 3 } },
        { unitId = 4, act = "chest", move = { x = 7, y = 3 } },
        { unitId = 4, act = "door", move = { x = 7, y = 3 } },
        { unitId = 5, act = "wait", move = { x = -1, y = 12 } },
    }
    for _, a in ipairs(acts) do
        local k = Planner.key(a)
        local b = Planner.unkey(k)
        check(Planner.key(b), k, "unkey: " .. k .. " keys back to itself")
        check(b.unitId .. b.act .. b.move.x .. "," .. b.move.y, a.unitId .. a.act .. a.move.x
              .. "," .. a.move.y, "unkey: " .. k .. " unit, act and tile")
        check(b.targetId, a.targetId, "unkey: " .. k .. " target")
        check(b.obstacle and (b.obstacle.x .. "," .. b.obstacle.y),
              a.obstacle and (a.obstacle.x .. "," .. a.obstacle.y), "unkey: " .. k .. " wall")
    end
    check(pcall(Planner.unkey, "not a key"), false, "unkey: a string that is no key raises")
end

-- test_offer_plans_the_fogged_acts_judged_in_full (review #3): opts.offer = Bot.candidates'
-- (cands, ctx) read on the fogged board. A full-information replay judges on the board with
-- the fog off, but plays on the fogged game, which offers no attack on an enemy it hides: the
-- plan takes its acts from the offer and never reads them again.
do
    local A = blue(0x01, 0, 0, 0)
    local X = red(0x81, 1, 0, { hp = 5 })
    local o = { fc = { [0x01] = { [0x81] = { ["0,0"] = fc({ hit = 100, dmg = 10, hits = 1,
                                                              killsTarget = true }) } } },
                enemyPhase = function() return {} end }
    local st = style("careful")
    -- with the fog off, the attack is offered and played
    local a = Planner.plan(B, boardOf(A, X), sightOf(o), st)
    check(a and a.act, "attack", "offer: the seen enemy is attacked")
    -- the offer read with X hidden, the plan made on the board with it seen
    local fogged = boardOf(blue(0x01, 0, 0, 0), red(0x81, 1, 0, { hp = 5, fogged = true }))
    local sight = sightOf(o)
    local cands, ctx = B.candidates(fogged, sight, st)
    local n = 0
    for _, c in ipairs(cands) do n = n + #c.acts end
    local plan
    a, plan = Planner.plan(B, boardOf(A, X), sight, st, { offer = { cands = cands, ctx = ctx } })
    check(a and a.act ~= "attack", true, "offer: no attack on the enemy the fogged game hides")
    check(plan.audit.offered_n, n, "offer: the plan's acts are the offer's")
end

-- test_offer_judges_every_enemy_seen (re-review A): the offer brings the fogged board's acts
-- only; the enemies the judging knows are the fog-off board's. A boss the fog hides when the
-- acts are read still makes the step into its reach a lookahead trigger, and the second
-- phase's death keeps A back, as it does with the boss seen all along.
do
    local board, sight, st = looksAhead(true)
    local fogged = { turn = board.turn, phase = board.phase, map = board.map, units = {} }
    for i, u in ipairs(board.units) do
        local c = {}
        for k, v in pairs(u) do c[k] = v end
        c.fogged = c.id == 0x82
        fogged.units[i] = c
    end
    local cands, ctx = B.candidates(fogged, sight, st)
    local a, plan = Planner.plan(B, board, sight, st, { offer = { cands = cands, ctx = ctx } })
    check(plan.lookahead.trigger and plan.lookahead.trigger[1], "boss",
          "offer: the boss the fog hid is seen by the trigger")
    check(at(a), "0,0", "offer: and its second phase keeps A back")
    check(plan.enemies[0x82], true, "offer: the plan's enemies hold the boss")
end

-- a unit the game will not let the player select (asleep or berserked, playerphase.c) is never
-- an actor: the scout lap's Ch14 (2026-11-14) planned a berserked Cormag's attack, and the
-- harness's move failed. It still stands on the board (an enemy may strike it).
do
    local held = blue(0x01, 0, 2, 2, { held = true })
    local free = blue(0x02, 1, 4, 4)
    local cands = B.candidates(boardOf(held, free, red(0x81, 9, 9)), sightOf({}), style("careful"))
    local ids = {}
    for _, c in ipairs(cands) do ids[#ids + 1] = c.unit.id end
    check(table.concat(ids, ","), "2", "held: an asleep or berserked unit is offered no act")
end

-- A (27 HP unless given) at (0,0) is pulled to (1,0) toward a village. An enemy strikes
-- whoever stands on (1,0) for 12, every blow landing, in the next enemy phase and in the one
-- after it. `o` adds to the sight: who holds a heal of its own, and who a staff.
-- one blow of 12 on A where it stands on (1,0), in the enemy's reach
local function strikes12(plan)
    for _, b in ipairs(plan.blues) do
        if b.x == 1 and b.unit.id == 0x01 then
            return { { target = b.unit.id, takenHit = 100, takenDmg = 12, takenHits = 1,
                       takenCrit = 0 } }
        end
    end
    return {}
end
local function wears(hp, o, ...)
    local A = blue(0x01, 0, 0, 0, { hp = hp or 27, minRange = false })
    local X = red(0x81, 0, 9, { minRange = false })
    local strikes = strikes12
    local so = {
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }) },
        field = function(t)
            return t.x == 9 and t.y == 0 and { [0] = { [0] = 40, [1] = 20 } } or nil
        end,
        explorable = { { x = 9, y = 0, kind = "visit" } },
        canExplore = { [0x01] = { ["9,0"] = "visit" } },
        enemyPhase = strikes, nextPhase = strikes, salve = {},
    }
    for k, v in pairs(o or {}) do so[k] = v end
    return boardOf(A, X, ...), sightOf(so), gifted("careful", 1000)
end

-- test_a_struck_unit_no_heal_reaches_is_judged_on_three_phases (ADR 0421): one blow of
-- 12 a phase never kills 27 HP in the phase the cap reads, so the march into reach read 0 and
-- was played; with no heal of the army's able to reach the unit its HP carries, and the third blow
-- kills. The cap reads the three phases (the second played by sight.nextPhase, the third taken
-- as the second again), and the unit stays out of reach.
do
    local board, sight, st = wears()
    local a, plan, cost = Planner.plan(B, board, sight, st)
    check(at(a), "0,0", "wear: three blows of 12 on 27 HP, no heal in reach: A stays out")
    local march
    for _, c in ipairs(plan.considered) do
        if c.acts[1] == "1>wait@1,0>nil" then march = c end
    end
    check(march ~= nil and march.rank.admitted, false, "wear: the march into reach is over the cap")
    check(march and march.rank.max_die, 1, "wear: the third blow's sure death")
    check(march and march.rank.first_max_exceed, 0, "wear: the next phase's own reading is kept")
    check(cost.look.wear > 0, true, "wear: its second phases are counted")
    check(cost.look.calls, 0, "wear: outside the lookahead's budget")
    check(plan.lookahead.calls, 0, "wear: the plan's lookahead made no call")

    -- 40 HP outlasts three blows: no death in them, the march goes
    board, sight, st = wears(40)
    check(at(Planner.plan(B, board, sight, st)), "1,0", "wear: 40 HP outlasts three blows of 12")

    -- a heal of its own: its HP does not carry, the next phase alone is read
    board, sight, st = wears(27, { salve = { [0x01] = true } })
    a, plan, cost = Planner.plan(B, board, sight, st)
    check(at(a), "1,0", "wear: a unit holding its own heal is read on the next phase")
    check(cost.look.wear, 0, "wear: no second phase asked for it")

    -- a staff of the army's one turn away: the same
    local H = blue(0x02, 1, 0, 1, { minRange = false })
    board, sight, st = wears(27, { staves = { [0x02] = { { slot = 0, amount = 10 } } },
                                   reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }),
                                             [0x02] = tiles({ 0, 1 }) } }, H)
    check(at(Planner.plan(B, board, sight, st)), "1,0", "wear: a staff within a turn, the march goes")

    -- that staff too far to reach it next turn (MOV 5, 13 tiles off): A stays out again
    H = blue(0x02, 1, 14, 0, { minRange = false })
    board, sight, st = wears(27, { staves = { [0x02] = { { slot = 0, amount = 10 } } },
                                   reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }),
                                             [0x02] = tiles({ 14, 0 }) } }, H)
    check(at(Planner.plan(B, board, sight, st)), "0,0", "wear: a staff two turns off is no heal in reach")

    -- a staff's own reach (#629 review): from (8,0) on MOV 5 the healer gets to (3,0), two
    -- tiles from A on (1,0). A reach of 1 is no heal next turn; a staff reach of 3 is
    H = blue(0x02, 1, 8, 0, { minRange = false })
    local function physic(range)
        return wears(27, { staves = { [0x02] = { { slot = 0, amount = 10, range = range } } },
                           reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }),
                                     [0x02] = tiles({ 8, 0 }) } }, H)
    end
    check(at(Planner.plan(B, physic(1))), "0,0", "wear: a reach of 1, seven tiles off, no heal")
    check(at(Planner.plan(B, physic(3))), "1,0", "wear: a reach of 3 heals from two tiles off")

    -- the healer's move is read out from its own tile (#629 re-review): the costs out from (8,0)
    -- reach (2,0) in one turn, the costs back from (2,0) would take three. The march goes
    H = blue(0x02, 1, 8, 0, { minRange = false })
    board, sight, st = wears(27, {
        staves = { [0x02] = { { slot = 0, amount = 10, range = 1 } } },
        reach = { [0x01] = tiles({ 0, 0 }, { 1, 0 }), [0x02] = tiles({ 8, 0 }) },
        field = function(t)
            if t.x == 8 and t.y == 0 then return { [0] = { [2] = 5 } } end   -- out from the healer
            if t.x == 2 and t.y == 0 then return { [0] = { [8] = 15 } } end   -- back from (2,0)
            if t.x == 9 and t.y == 0 then return { [0] = { [0] = 40, [1] = 20 } } end
            return nil
        end }, H)
    check(at(Planner.plan(B, board, sight, st)), "1,0", "wear: the healer's own way out, one turn")

    -- its own budget spent (the attempt's left, opts.budget.wear): the plan keeps the one-phase
    -- reading, the march goes, and every plan left unread is counted for botrun's wear_budget
    board, sight, st = wears()
    a, plan, cost = Planner.plan(B, board, sight, st, { budget = { wear = 0 } })
    check(at(a), "1,0", "wear: no call left, the next phase alone is read")
    check(cost.look.wear, 0, "wear: no call past the budget")
    check(cost.look.wear_skipped > 0, true, "wear: the plans left unread are counted")
    check(plan.lookahead.wear_skipped, cost.look.wear_skipped, "wear: and recorded on the plan")
    -- the decision's own cap holds whatever the attempt has left
    local was = Planner.WEAR_DECISION
    Planner.WEAR_DECISION = 0
    board, sight, st = wears()
    a, plan, cost = Planner.plan(B, board, sight, st, { budget = { wear = 1000 } })
    Planner.WEAR_DECISION = was
    check(at(a), "1,0", "wear: the decision's cap spent, the next phase alone is read")
    check(cost.look.wear_skipped > 0, true, "wear: counted the same")

    -- each way the next phase goes, on that way's HP (#629 review): the blow lands in half the
    -- ways only, the likeliest way's strikes are none. Where it lands, two more kill (27 - 36);
    -- where it does not, two leave 3 HP. Read off the likeliest way's strikes, the wear saw 27
    -- HP met by two blows and nothing; each way's, it reads a half chance and A stays out
    local function halfway(plan)
        local blow = strikes12(plan)
        if #blow == 0 then return {} end
        return { outcomes = { { p = 0.5, strikes = blow }, { p = 0.5, strikes = {} } } }
    end
    board, sight, st = wears(27, { enemyPhase = halfway })
    a, plan = Planner.plan(B, board, sight, st)
    check(at(a), "0,0", "wear: a blow in half the ways, then two more: A stays out")
    for _, c in ipairs(plan.considered) do
        if c.acts[1] == "1>wait@1,0>nil" then march = c end
    end
    check(march and math.abs(march.rank.max_die - 0.5) < 1e-9, true, "wear: the half chance, each way read")

    -- a unit whose death ends the game: its later death is the game over's too (#629 review),
    -- which ranks over-cap plans first
    board, sight, st = wears(27, { objective = { kind = "rout", gameOver = { 0x01 } } })
    a, plan = Planner.plan(B, board, sight, st)
    for _, c in ipairs(plan.considered) do
        if c.acts[1] == "1>wait@1,0>nil" then march = c end
    end
    check(march and march.rank.first_game_over, 0, "wear: the next phase ends no game")
    check(march and march.rank.game_over, 1, "wear: the third blow ends it")

    -- the next phase already may end it (#629 re-review): a 30 blow in 3 ways of 10 kills A
    -- there, a 12 in the rest wears it to death by the third. The game over is the lord's whole
    -- death, the later one taken given it lived (unconditioned it read 1 - 0.7 x 0.3 = 0.79)
    local function heavy(plan)
        local blow = strikes12(plan)
        if #blow == 0 then return {} end
        local big = {}
        for k, v in pairs(blow[1]) do big[k] = v end
        big.takenDmg = 30
        return { outcomes = { { p = 0.3, strikes = { big } }, { p = 0.7, strikes = blow } } }
    end
    board, sight, st = wears(27, { enemyPhase = heavy,
                                   objective = { kind = "rout", gameOver = { 0x01 } } })
    a, plan = Planner.plan(B, board, sight, st)
    for _, c in ipairs(plan.considered) do
        if c.acts[1] == "1>wait@1,0>nil" then march = c end
    end
    check(march and math.abs(march.rank.first_game_over - 0.3) < 1e-9, true, "wear: the next phase's 0.3")
    check(march and math.abs(march.rank.game_over - march.rank.max_die) < 1e-9, true,
          "wear: the game over is the lord's whole death")

    -- the lookahead on a worn plan (#629 review): it reuses the wear's second phase, no second
    -- call, and the worn unit's death stays the wear's reading of it
    board, sight, st = wears()
    local calls, next = 0, sight.nextPhase
    sight.nextPhase = function(...) calls = calls + 1 return next(...) end
    a, plan, cost = Planner.plan(B, board, sight, st, { diag = "deep" })
    check(calls, cost.look.wear + cost.look.calls, "wear: every second phase counted once")
    for _, c in ipairs(plan.considered) do
        if c.acts[1] == "1>wait@1,0>nil" then march = c end
    end
    check(march and march.extended, true, "wear: the march was a finalist the lookahead read")
    check(march and march.rank.max_die, 1, "wear: its death the wear's three phases")
    -- the finalists it read, less the worn ones (A on (1,0), its wear read): each one call
    local read, worn = 0, 0
    for _, c in ipairs(plan.considered) do
        if c.extended then
            read = read + 1
            if c.rank.max_die == 1 then worn = worn + 1 end
        end
    end
    check(worn > 0, true, "wear: a worn finalist was read")
    check(cost.look.calls, read - worn, "wear: a worn finalist costs the lookahead no call")

    -- one reading of the worn unit's later phases, the wear's (#629 review): the lookahead adds
    -- neither its own second phase to the unit's death nor to the game over. Its own reading
    -- starts A on the 10 HP the game's played phase left (r.hp), which the second blow kills
    local function tenLeft(plan)
        local out = strikes12(plan)
        out.hp = { [0x01] = 10 }
        return out
    end
    board, sight, st = wears(27, { enemyPhase = halfway, nextPhase = tenLeft,
                                   objective = { kind = "rout", gameOver = { 0x01 } } })
    a, plan = Planner.plan(B, board, sight, st, { diag = "deep" })
    for _, c in ipairs(plan.considered) do
        if c.acts[1] == "1>wait@1,0>nil" then march = c end
    end
    check(march and march.extended, true, "wear: the lord's march read by the lookahead")
    check(march and math.abs(march.rank.max_die - 0.5) < 1e-9, true, "wear: its death the wear's half")
    check(march and math.abs(march.rank.game_over - 0.5) < 1e-9, true, "wear: and the game over's")
end

if fails > 0 then
    print(string.format("\n%d/%d FAILED", fails, tests)); os.exit(1)
else
    print(string.format("ok -- %d assertions", tests))
end
