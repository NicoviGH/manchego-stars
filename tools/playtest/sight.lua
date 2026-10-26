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
-- api: { mem = { u8, s8, u16, s16, u32 }, write8, write32, SYM, cpu (Sight.machine's),
--        map = function() -> w, h, chapter = function() -> index, turn = function() -> n,
--        lordPid = function() -> charId|nil, fieldUnit = function() -> board unit|nil (the
--        lord, else the first deployed unit), distanceField = pathing.lua's }
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
--     taken*                  what `e` does to `u` on (x, y). When (x, y) is in our weapon's
--                             range of `e` and `e` can answer, its COUNTER in this exchange;
--                             otherwise `e` as the ACTOR, striking `u` placed on (x, y) from a
--                             tile at its own weapon's minimum range (that tile's terrain only
--                             moves `e`'s avoid and defence, which no taken field reads).
--     counters                `e` answers this attack (false when out of range of it, or it
--                             cannot counter): the attack's own counter is then nothing.
--     killsTarget             dmg x hits >= e's HP, from our side of an attack in range.
--     diesWorst               `e` counters and its worst case (x3 on any crit) >= u's HP.
--   objective                { kind, tile, turnsLeft, lord, ruledOut } -- see objective().
--   field(goal)              BFS steps to `goal` (pathing.lua) over tiles the lord's movement
--                            cost table can enter (GetUnitMovementCost, -1 = impassable).
--   terrain(x, y)            gBmMapTerrain[y][x].
--   cache                    {} for the phase (bot.lua keeps its forecasts there).
-- Sight.seed(api, s)         InitRN(s): the game's own seeding, written into gRNSeeds.

local M = {}

M.FRAME_BUDGET = 600         -- frames one call may run; a full map's danger zone takes a few
M.MOVE_LIMIT = 120           -- include/bmmap.h: a movement-map cost at or above it is unreachable
M.ISLOT_AUTO = -1            -- include/bmbattle.h BU_ISLOT_AUTO
M.TILE_COMMAND_SEIZE = 0x11  -- include/eventinfo.h
-- include/types.h goal window types, chapter data +0x8C (goalWindowDataType); +0x8D is
-- goalWindowEndTurnNumber, the last turn a Defense map must be held.
M.GOALS = { [0] = "seize", [1] = "rout", [2] = "survive", [3] = "boss", [4] = "special" }
M.CHAPTER_GOAL, M.CHAPTER_GOAL_TURN = 0x8C, 0x8D

-- struct BattleUnit (include/bmbattle.h) and BattleForecastProc (include/bksel.h) offsets.
local BU = { weapon = 0x48, attack = 0x5A, defense = 0x5C, hit = 0x64, crit = 0x6A }
local PROC_HITS_A, PROC_HITS_B, PROC_SIZE = 0x50, 0x51, 0x54
local UNIT_X, UNIT_Y = 0x10, 0x11
local CRIT_MULTIPLIER = 3   -- bmbattle.c BattleGenerateHitAttributes

local REGS = { "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9", "r10", "r11",
               "r12", "sp", "lr", "pc", "cpsr" }

-- Sight.machine(cpu) -> sandbox(fn): cpu = { read(reg), write(reg, v), write16(addr, v),
-- write32(addr, v), save() -> state, load(state), frames(done, max) -> bool (run emulated frames
-- until done() or `max` have passed) }. sandbox(fn) runs fn(call, scratch) between a save and a
-- load and returns what fn returns; call(addr, args) runs one game function and returns its r0.
-- Above the call's stack sit `scratch` (PROC_SIZE free bytes for the caller) and the return
-- loop; the load puts back whatever was there.
local THUMB_B_SELF = 0xE7FE
function M.machine(cpu)
    return function(fn)
        local state = cpu.save()
        local saved = {}
        for _, r in ipairs(REGS) do saved[r] = cpu.read(r) end
        local top = (saved.sp - 0x100) & ~7
        local scratch, loop = top + 0x10, top + 0x80
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

-- A tile `d` from (x, y) inside the map, for the enemy to strike from. Its terrain moves only
-- the striker's own avoid and defence, so any one will do; nil when none fits (d = 0).
function M.strikeTile(x, y, d, w, h)
    if not d or d < 1 then return nil end
    for _, o in ipairs({ { 0, -d }, { d, 0 }, { 0, d }, { -d, 0 } }) do
        local sx, sy = x + o[1], y + o[2]
        if sx >= 0 and sy >= 0 and sx < w and sy < h then return sx, sy end
    end
    return nil
end

-- A forecast from the two sides read off the simulations: `ours` from our attack (nil when
-- (x, y) is out of our range of the enemy), `theirs` from the enemy's own strike (nil when
-- the counter already answered it). Pure, so test_sight.lua builds every case.
function M.assemble(ours, theirs, uHp, eHp)
    local counters = ours ~= nil and ours.counter ~= nil and ours.counter.armed
    local t = counters and ours.counter or theirs
    local f = { hit = 0, dmg = 0, crit = 0, hits = 0, counters = counters,
                takenHit = t and t.armed and t.hit or 0, takenDmg = t and t.dmg or 0,
                takenCrit = t and t.crit or 0, takenHits = t and t.hits or 0 }
    if ours then
        f.hit, f.dmg, f.crit, f.hits = ours.hit, ours.dmg, ours.crit, ours.hits
    end
    f.killsTarget = ours ~= nil and f.hits > 0 and f.dmg * f.hits >= eHp
    local worst = f.takenDmg * f.takenHits * (f.takenCrit > 0 and CRIT_MULTIPLIER or 1)
    f.diesWorst = counters and f.takenHit > 0 and worst >= uHp or false
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
        local o = { kind = kind or "special", lord = api.lordPid(), ruledOut = {} }
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

local function grid(mem, base, x, y) return mem.u8(mem.u32(mem.u32(base) + y * 4) + x) end

function M.new(api)
    local mem, S = api.mem, api.SYM
    local sandbox = M.machine(api.cpu)
    local w, h = api.map()
    local s = { cache = {} }
    local dangerGrid, fields, costs = nil, {}, nil

    function s.danger(x, y)
        if not dangerGrid then
            dangerGrid = sandbox(function(call)
                call(S.GenerateDangerZoneRange, { 0 })
                local g = {}
                for yy = 0, h - 1 do
                    g[yy] = {}
                    for xx = 0, w - 1 do g[yy][xx] = grid(mem, S.gBmMapRange, xx, yy) end
                end
                return g
            end)
        end
        return dangerGrid[y] and dangerGrid[y][x] or 0
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

    function s.forecast(u, e, x, y, slot)
        local inRange = u.minRange and manhattan(x, y, e.x, e.y) >= u.minRange
            and manhattan(x, y, e.x, e.y) <= u.maxRange
        local ours, theirs = sandbox(function(call, proc)
            local a, t
            if inRange then
                call(S.BattleGenerateSimulation, { u.addr, e.addr, x, y, slot or M.ISLOT_AUTO })
                call(S.InitBattleForecastBattleStats, { proc })
                a = M.side(mem, S.gBattleActor, S.gBattleTarget, proc, PROC_HITS_A)
                a.counter = M.side(mem, S.gBattleTarget, S.gBattleActor, proc, PROC_HITS_B)
                if a.counter.armed then return a, nil end
            end
            local sx, sy = M.strikeTile(x, y, e.minRange, w, h)
            if sx then
                api.write8(u.addr + UNIT_X, x)
                api.write8(u.addr + UNIT_Y, y)
                call(S.BattleGenerateSimulation, { e.addr, u.addr, sx, sy, M.ISLOT_AUTO })
                call(S.InitBattleForecastBattleStats, { proc })
                t = M.side(mem, S.gBattleActor, S.gBattleTarget, proc, PROC_HITS_A)
            end
            return a, t
        end)
        return M.assemble(ours, theirs, u.hp, e.hp)
    end

    function s.terrain(x, y) return grid(mem, S.gBmMapTerrain, x, y) end

    -- The lord's (else the first deployed unit's) movement costs, read once: a field is a
    -- march heading, and each unit's real reach still comes from reach().
    function s.field(goal)
        local k = goal.x .. "," .. goal.y
        if fields[k] then return fields[k] end
        if not costs then
            local unit = api.fieldUnit()
            costs = {}
            if unit then
                sandbox(function(call)
                    local table_ = call(S.GetUnitMovementCost, { unit.addr })
                    for t = 0, 0xFF do costs[t] = mem.s8(table_ + t) end
                end)
            end
        end
        local function passable(x, y)
            if x < 0 or y < 0 or x >= w or y >= h then return false end
            local c = costs[s.terrain(x, y)]
            return c ~= nil and c >= 0
        end
        fields[k] = api.distanceField(w, h, passable, goal)
        return fields[k]
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
