-- sight.lua -- what the bot SEES, read from the game itself (#510 step 9, PR D).
--
-- bot.lua decides from a `sight` table and re-creates nothing; this file builds that table
-- from the running ROM. Every answer comes out of FE8's own code: the danger zone is
-- GenerateDangerZoneRange's gBmMapRange, a unit's reach is GenerateUnitMovementMap's
-- gBmMapMovement, a forecast is BattleGenerateSimulation + InitBattleForecastBattleStats (the
-- forecast window's own two calls), the seize tile is GetAvailableTileEventCommand and the
-- objective is the chapter data's goal window. No FE8 rule is written here.
--
-- HOW THE GAME'S CODE IS RUN. Sight.machine(cpu) is a sandbox: it saves the emulator's state,
-- points the CPU at a game function (args in r0-r3 and on the stack, IRQs masked, lr at a
-- two-byte `b .` it writes into scratch RAM), lets the emulator run frames until the CPU sits
-- in that loop, reads what the caller asks for, and loads the state back -- registers, RAM and
-- RNG exactly as they were. It never single-steps: a call long enough to cross the end of a
-- frame (ch01's danger zone) deadlocks mGBA's emu:step() inside its frame callback, so the
-- call runs as ordinary emulation, between frames. Driving the forecast WINDOW instead cannot
-- answer the enemy phase: FE8 zeroes the weapon of a target outside its range
-- (SetBattleUnitWeapon, BattleInitTargetCanCounter), so the window never shows an enemy's
-- strike on a tile it is not already beside. Here the enemy is the ACTOR, struck from its own
-- range, which is what it does on its phase (ADR 0369).
--
-- ── Sight.new(api) -> sight (bot.lua's contract) ────────────────────────────────────────────
-- api: { mem = { u8, s8, u16, s16, u32 }, write8, write16, write32, SYM, cpu (Sight.machine's),
--        map = function() -> w, h, chapter = function() -> index, turn = function() -> n,
--        board = Board.read }
-- The sight is for ONE player phase: build a new one after the enemy phase. Its danger grid
-- and objective are read once, at the first question.
--   danger(x, y)             gBmMapRange after GenerateDangerZoneRange(FALSE), fog and roofs as
--                            the game shows them: 0 when no enemy reaches (x, y), else its
--                            COVERAGE -- GenerateUnitCompleteAttackRange adds 1 for every tile
--                            an enemy could strike it from, so it is not an enemy count.
--   reach(unit)              tiles with gBmMapMovement < 120 after GenerateUnitMovementMap,
--                            less those another unit stands on (gBmMapUnit). Either faction.
--   forecast(u, e, x, y, slot) our unit `u` from (x, y) against enemy `e` where it stands:
--     hit, dmg, crit, hits    our side, as the forecast window shows it (dmg = battleAttack -
--                             the target's battleDefense, floored at 0; hits = hitCountA).
--     counter*                `e`'s COUNTER to that attack (counterHit, counterDmg, counterCrit,
--                             counterHits), with the weapon it holds, as FE8's counters are;
--     counters                false (and counter* 0) when (x, y) is out of our range of `e` or
--                             `e` cannot answer at that range.
--     taken*                  `e`'s own strike on `u` standing on (x, y), on its phase: FE8's AI
--                             routine for one target run as the game runs it (aiStrike, below)
--                             -- it picks the weapon AND the tile together, from where `e` can
--                             really move -- then simulated. All 0 when `e` cannot strike `u`
--                             there this turn.
--     takenSlot, takenTile    the slot and tile the AI chose (nil when it cannot strike).
--     takenCandidates         every slot the AI weighed: { slot, score, x, y } or { slot, skip }.
--     killsTarget             dmg x hits >= e's HP, from our side of an attack in range.
--     diesWorst               `e` counters and the counter's worst case (x3 on any crit) >= u's HP.
--   threat(e) -> function(x, y) -> coverage: ONE enemy's danger zone, every weapon it can use --
--                            the calls GenerateDangerZoneRange makes per unit, for `e` alone.
--                            Read once per enemy per sight.
--   objective                { kind, tile, turnsLeft } -- see objective().
--   canSeize(unit)           the game's CanUnitSeize for that unit.
--   range(unit)              { min, max } of the weapon FE8 has equipped, or nil (none).
--   field(goal)              dist[y][x] = the movement cost from `goal` to (x, y), FE8's
--                            GenerateExtendedMovementMap with fieldUnit()'s costs (nil = unreached).
--   terrain(x, y)            gBmMapTerrain[y][x].
--   cache                    {} for the phase (bot.lua keeps its forecasts there).
-- Sight.seed(api, s)         InitRN(s): the game's own seeding, written into gRNSeeds.

local M = {}

local function here()
    local src = debug.getinfo(1, "S").source
    return (src:sub(1, 1) == "@" and src:sub(2):match("(.*/)")) or "./"
end
local Board = dofile(here() .. "board.lua")

M.FRAME_BUDGET = 600         -- frames one call may run; a full map's danger zone takes a few
M.MOVE_LIMIT = 120           -- include/bmmap.h: a movement-map cost at or above it is unreachable
M.UNREACHED = 0xFF           -- GenerateMovementMap fills its map with -1 before it floods
M.ISLOT_AUTO = -1            -- include/bmbattle.h BU_ISLOT_AUTO
M.TILE_COMMAND_SEIZE = 0x11  -- include/eventinfo.h
-- include/types.h goal window types, chapter data +0x8C (goalWindowDataType); +0x8D is
-- goalWindowEndTurnNumber, the last turn a Defense map must be held.
M.GOALS = { [0] = "seize", [1] = "rout", [2] = "survive", [3] = "boss", [4] = "special" }
M.CHAPTER_GOAL, M.CHAPTER_GOAL_TURN = 0x8C, 0x8D

-- struct BattleUnit (include/bmbattle.h) and BattleForecastProc (include/bksel.h) offsets.
local BU = { weapon = 0x48, attack = 0x5A, defense = 0x5C, hit = 0x64, crit = 0x6A }
local PROC_HITS_A, PROC_HITS_B, PROC_SIZE = 0x50, 0x51, 0x54
-- struct AiCombatSimulationSt (include/cp_common.h): xMove, yMove, targetId, u16 itemSlot +4,
-- u32 score +8. It sits in scratch after the forecast proc.
local ST, ST_SLOT, ST_SCORE = PROC_SIZE + 4, 0x04, 0x08
M.SCRATCH_SIZE = ST + 0x0C
M.ITEM_SLOTS, M.UNIT_ITEMS = 5, 0x1E   -- bmunit.h UNIT_ITEM_COUNT; struct Unit +1E u16 items[5]
M.ITEM_NIGHTMARE = 0xA6                -- constants/items.h
local UNIT_X, UNIT_Y = 0x10, 0x11
local CRIT_MULTIPLIER = 3   -- bmbattle.c BattleGenerateHitAttributes

local REGS = { "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9", "r10", "r11",
               "r12", "sp", "lr", "pc", "cpsr" }

-- Sight.machine(cpu) -> sandbox(fn): cpu = { read(reg), write(reg, v), write16(addr, v),
-- write32(addr, v), save() -> state, load(state), frames(done, max) -> bool (run emulated frames
-- until done() or `max` have passed) }. sandbox(fn) runs fn(call, scratch) between a save and a
-- load and returns what fn returns; call(addr, args) runs one game function and returns its r0.
-- `scratch` is SCRATCH_SIZE free bytes for the caller.
-- Above the call's stack sit `scratch` and the return loop; the load puts back whatever was there.
local THUMB_B_SELF = 0xE7FE
function M.machine(cpu)
    return function(fn)
        local state = cpu.save()
        local saved = {}
        for _, r in ipairs(REGS) do saved[r] = cpu.read(r) end
        local top = (saved.sp - 0x100) & ~7
        local scratch, loop = top + 0x10, top + 0x80   -- SCRATCH_SIZE fits between them
        local function returned()
            local pc = cpu.read("pc")
            return pc >= loop and pc <= loop + 8
        end
        local function call(addr, args)
            local sp = top
            for i, a in ipairs(args) do
                if i <= 4 then cpu.write("r" .. (i - 1), a & 0xFFFFFFFF)
                else cpu.write32(sp + (i - 5) * 4, a & 0xFFFFFFFF) end
            end
            cpu.write16(loop, THUMB_B_SELF)
            cpu.write("sp", sp)
            cpu.write("lr", loop | 1)
            -- System mode, Thumb, IRQs masked: no interrupt handler runs inside the call, and
            -- the CPU spins in the loop once it returns.
            cpu.write("cpsr", (saved.cpsr & ~0xFF) | 0x1F | 0x20 | 0x80)
            cpu.write("pc", addr & ~1)
            if not cpu.frames(returned, M.FRAME_BUDGET) then
                error(string.format("sight: call 0x%08X did not return in %d frames (pc 0x%08X)",
                    addr, M.FRAME_BUDGET, cpu.read("pc")))
            end
            return cpu.read("r0")
        end
        local ok, a, b = pcall(fn, call, scratch)
        cpu.load(state)
        if not ok then error(a, 0) end
        return a, b
    end
end

local function s16(v) return v >= 0x8000 and v - 0x10000 or v end
local function manhattan(ax, ay, bx, by) return math.abs(ax - bx) + math.abs(ay - by) end

-- One side of a simulated exchange, as the forecast window reads it: hit, crit, damage against
-- the other side's defence, and how many blows (the proc's hit count for that side).
function M.side(mem, me, other, proc, hitsAt)
    local dmg = s16(mem.u16(me + BU.attack)) - s16(mem.u16(other + BU.defense))
    return { hit = s16(mem.u16(me + BU.hit)), crit = s16(mem.u16(me + BU.crit)),
             dmg = dmg > 0 and dmg or 0, hits = mem.s8(proc + hitsAt),
             armed = mem.u16(me + BU.weapon) ~= 0 }
end

-- The AI's weapon for one target, FE8's own way (cp_battle.c AiAttemptOffensiveAction): each
-- item slot in order, stopping at an empty one; Nightmare skipped -- compared as the WHOLE item
-- word, uses byte included, exactly as the game does, so only a used-up one is ever skipped;
-- a weapon CanUnitUseWeapon rejects, or one AiReachesByBirdsEyeDistance rules out, skipped;
-- each left scored by AiSimulateBestBattleAgainstTarget (which picks its tile; no tile = skip),
-- the best kept and a tie going to the later slot (`>=`). `slots` is
-- { {slot, score, x, y}|{slot, skip=true} } in slot order; returns the chosen entry or nil.
-- Pure, so test_sight.lua pins the order and the tie.
function M.aiPick(slots)
    local best
    for _, c in ipairs(slots) do
        if not c.skip and (best == nil or c.score >= best.score) then best = c end
    end
    return best
end

-- A forecast from what the simulations read: `ours` from our attack (nil when (x, y) is out of
-- our range of the enemy), with `ours.counter` the enemy's answer to it; `theirs` the enemy's
-- own strike on its phase (nil when it cannot strike us there). Pure, so test_sight.lua builds
-- every case.
function M.assemble(ours, theirs, uHp, eHp)
    local c = ours and ours.counter
    local counters = c ~= nil and c.armed
    local t = theirs
    local f = { hit = 0, dmg = 0, crit = 0, hits = 0, counters = counters,
                counterHit = counters and c.hit or 0, counterDmg = counters and c.dmg or 0,
                counterCrit = counters and c.crit or 0, counterHits = counters and c.hits or 0,
                takenHit = t and t.armed and t.hit or 0, takenDmg = t and t.dmg or 0,
                takenCrit = t and t.crit or 0, takenHits = t and t.hits or 0,
                takenSlot = t and t.slot or nil, takenTile = t and t.tile or nil,
                takenCandidates = t and t.candidates or nil }
    if ours then
        f.hit, f.dmg, f.crit, f.hits = ours.hit, ours.dmg, ours.crit, ours.hits
    end
    f.killsTarget = ours ~= nil and f.hits > 0 and f.dmg * f.hits >= eHp
    local worst = f.counterDmg * f.counterHits * (f.counterCrit > 0 and CRIT_MULTIPLIER or 1)
    f.diesWorst = counters and f.counterHit > 0 and worst >= uHp or false
    return f
end

-- The chapter's objective from its goal window. A Seize map's tile is the one location event
-- whose command is Seize; a Defense map counts its turns left from the goal's last turn.
function M.objective(api, sandbox)
    local S = api.SYM
    local w, h = api.map()
    return sandbox(function(call)
        local data = call(S.GetROMChapterStruct, { api.chapter() })
        local kind = M.GOALS[api.mem.u8(data + M.CHAPTER_GOAL)]
        local o = { kind = kind or "special" }
        if kind == "survive" then
            o.turnsLeft = api.mem.u8(data + M.CHAPTER_GOAL_TURN) - api.turn() + 1
        elseif kind == "seize" then
            for y = 0, h - 1 do
                for x = 0, w - 1 do
                    if call(S.GetAvailableTileEventCommand, { x, y }) == M.TILE_COMMAND_SEIZE then
                        o.tile = { x = x, y = y }
                    end
                end
            end
        end
        return o
    end)
end

local function cell(mem, base, x, y) return mem.u32(mem.u32(base) + y * 4) + x end
local function grid(mem, base, x, y) return mem.u8(cell(mem, base, x, y)) end
local function readGrid(mem, base, w, h)
    local g = {}
    for y = 0, h - 1 do
        g[y] = {}
        for x = 0, w - 1 do g[y][x] = grid(mem, base, x, y) end
    end
    return g
end

function M.new(api)
    local mem, S = api.mem, api.SYM
    local sandbox = M.machine(api.cpu)
    local w, h = api.map()
    local s = { cache = {} }
    local dangerGrid, threats, fields = nil, {}, {}

    function s.danger(x, y)
        if not dangerGrid then
            dangerGrid = sandbox(function(call)
                call(S.GenerateDangerZoneRange, { 0 })
                return readGrid(mem, S.gBmMapRange, w, h)
            end)
        end
        return dangerGrid[y] and dangerGrid[y][x] or 0
    end

    -- GenerateDangerZoneRange's body (bmidoten.c) for one unit: its movement map, itself lifted
    -- off gBmMapUnit, the magic seal map for a magic user, then its complete attack range.
    function s.threat(e)
        if not threats[e.id] then
            threats[e.id] = sandbox(function(call)
                call(S.BmMapFill, { mem.u32(S.gBmMapRange), 0 })
                call(S.GenerateUnitMovementMap, { e.addr })
                api.write8(cell(mem, S.gBmMapUnit, e.x, e.y), 0)
                if call(S.UnitHasMagicRank, { e.addr }) ~= 0 then
                    call(S.BmMapFill, { mem.u32(S.gBmMapOther), 0 })
                    call(S.GenerateMagicSealMap, { 1 })
                end
                call(S.SetWorkingBmMap, { mem.u32(S.gBmMapRange) })
                call(S.GenerateUnitCompleteAttackRange, { e.addr })
                return readGrid(mem, S.gBmMapRange, w, h)
            end)
        end
        local g = threats[e.id]
        return function(x, y) return g[y] and g[y][x] or 0 end
    end

    function s.reach(u)
        return sandbox(function(call)
            call(S.GenerateUnitMovementMap, { u.addr })
            local out = {}
            for y = 0, h - 1 do
                for x = 0, w - 1 do
                    if grid(mem, S.gBmMapMovement, x, y) < M.MOVE_LIMIT
                        and ((x == u.x and y == u.y) or grid(mem, S.gBmMapUnit, x, y) == 0) then
                        out[#out + 1] = { x = x, y = y }
                    end
                end
            end
            return out
        end)
    end

    -- Inside a sandbox: FE8's AI choosing how `e` strikes `u` on (x, y), run as
    -- AiAttemptOffensiveAction runs it for one target (cp_battle.c): `u` is moved onto (x, y) on
    -- the unit grid as well as in its struct, so movement and blocking see it there; `e` becomes
    -- the active unit; its movement map, magic seal map and working map are set up as the AI
    -- sets them; then each slot is filtered and scored as the AI scores it.
    local function aiStrike(call, st, u, e, x, y)
        if mem.u8(cell(mem, S.gBmMapUnit, u.x, u.y)) == u.id then
            api.write8(cell(mem, S.gBmMapUnit, u.x, u.y), 0)
        end
        api.write8(cell(mem, S.gBmMapUnit, x, y), u.id)
        api.write8(u.addr + UNIT_X, x)
        api.write8(u.addr + UNIT_Y, y)
        api.write32(S.gActiveUnit, e.addr)
        api.write8(S.gActiveUnitId, e.id)
        call(S.GenerateUnitMovementMap, { e.addr })
        if call(S.UnitHasMagicRank, { e.addr }) ~= 0 then call(S.GenerateMagicSealMap, { -1 }) end
        call(S.SetWorkingBmMap, { mem.u32(S.gBmMapRange) })
        local slots = {}
        for i = 0, M.ITEM_SLOTS - 1 do
            local item = mem.u16(e.addr + M.UNIT_ITEMS + i * 2)
            if item == 0 then break end
            local c = { slot = i, skip = true }
            if item ~= M.ITEM_NIGHTMARE and call(S.CanUnitUseWeapon, { e.addr, item }) ~= 0
                and call(S.AiReachesByBirdsEyeDistance, { e.addr, u.addr, item }) ~= 0 then
                call(S.AiFillReversedAttackRangeMap, { u.addr, item })
                api.write8(st + 2, u.id)
                api.write16(st + ST_SLOT, i)
                api.write32(st + ST_SCORE, 0)
                if call(S.AiSimulateBestBattleAgainstTarget, { st }) ~= 0 then
                    c.skip, c.score = false, mem.u32(st + ST_SCORE)
                    c.x, c.y = mem.u8(st), mem.u8(st + 1)
                end
            end
            slots[#slots + 1] = c
        end
        return M.aiPick(slots), slots
    end

    -- Our unit's reach: the weapon FE8 has equipped (GetUnitEquippedWeapon -- the first one
    -- CanUnitUseWeapon accepts, which BU_ISLOT_AUTO strikes with), and that item's range.
    -- { min, max } or false when it has none. Per unit, once.
    local ranges = {}
    function s.range(u)
        if ranges[u.id] == nil then
            local item = sandbox(function(call) return call(S.GetUnitEquippedWeapon, { u.addr }) end)
            local mn, mx = Board.itemRange(mem, S, item)
            ranges[u.id] = mn and { min = mn, max = mx } or false
        end
        return ranges[u.id] or nil
    end

    function s.forecast(u, e, x, y, slot)
        local r = s.range(u)
        local d = manhattan(x, y, e.x, e.y)
        local inRange = r and d >= r.min and d <= r.max
        local ours, theirs = sandbox(function(call, proc)
            local a, t
            if inRange then
                call(S.BattleGenerateSimulation, { u.addr, e.addr, x, y, slot or M.ISLOT_AUTO })
                call(S.InitBattleForecastBattleStats, { proc })
                a = M.side(mem, S.gBattleActor, S.gBattleTarget, proc, PROC_HITS_A)
                a.counter = M.side(mem, S.gBattleTarget, S.gBattleActor, proc, PROC_HITS_B)
            end
            local pick, slots = aiStrike(call, proc + ST, u, e, x, y)
            if pick then
                call(S.BattleGenerateSimulation, { e.addr, u.addr, pick.x, pick.y, pick.slot })
                call(S.InitBattleForecastBattleStats, { proc })
                t = M.side(mem, S.gBattleActor, S.gBattleTarget, proc, PROC_HITS_A)
                t.slot, t.tile, t.candidates = pick.slot, { x = pick.x, y = pick.y }, slots
            else
                t = { armed = false, candidates = slots }   -- no strike, but what was weighed
            end
            return a, t
        end)
        return M.assemble(ours, theirs, u.hp, e.hp)
    end

    function s.terrain(x, y) return grid(mem, S.gBmMapTerrain, x, y) end

    -- The game's own Seize check (bmdifficulty.c CanUnitSeize, which the Seize command's
    -- usability calls; engine patch 0005 makes it the chosen lead in our build). Per unit, once.
    local seizers = {}
    function s.canSeize(u)
        if seizers[u.id] == nil then
            seizers[u.id] = sandbox(function(call) return call(S.CanUnitSeize, { u.addr }) ~= 0 end)
        end
        return seizers[u.id]
    end

    -- Whose movement costs a march field uses: the first deployed unit that can Seize, else the
    -- first deployed unit (slot order).
    function s.fieldUnit()
        local first
        for _, u in ipairs(api.board().units) do
            if u.faction == "blue" and u.onField then
                if s.canSeize(u) then return u end
                first = first or u
            end
        end
        return first
    end

    -- FE8's own march distance: GenerateExtendedMovementMap from the goal, out to
    -- MAP_MOVEMENT_EXTENDED, with the lord's (else the first deployed unit's) movement costs --
    -- the map its AI heads for a far target over (cp_0803E2F4.c). Units do not block it, as they
    -- do not block the AI's. A field is a march heading; each unit's real reach is reach()'s.
    function s.field(goal)
        local k = goal.x .. "," .. goal.y
        if fields[k] == nil then
            local unit = s.fieldUnit()
            fields[k] = unit and sandbox(function(call)
                local costs = call(S.GetUnitMovementCost, { unit.addr })
                call(S.GenerateExtendedMovementMap, { goal.x, goal.y, costs })
                local dist = {}
                for y = 0, h - 1 do
                    dist[y] = {}
                    for x = 0, w - 1 do
                        local v = grid(mem, S.gBmMapMovement, x, y)
                        if v ~= M.UNREACHED then dist[y][x] = v end
                    end
                end
                return dist
            end) or false
        end
        return fields[k] or nil
    end

    s.objective = M.objective(api, sandbox)
    return s
end

-- InitRN(seed) run in the sandbox, its three seeds then written into the live game: the run's
-- whole RNG stream is the game's own function of `seed`.
function M.seed(api, seed)
    local S = api.SYM
    local words = M.machine(api.cpu)(function(call)
        call(S.InitRN, { seed })
        return { api.mem.u16(S.gRNSeeds), api.mem.u16(S.gRNSeeds + 2), api.mem.u16(S.gRNSeeds + 4) }
    end)
    for i, v in ipairs(words) do
        api.write8(S.gRNSeeds + (i - 1) * 2, v & 0xFF)
        api.write8(S.gRNSeeds + (i - 1) * 2 + 1, v >> 8)
    end
    return words
end

return M
