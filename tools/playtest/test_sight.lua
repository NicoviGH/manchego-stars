-- Tests for sight.lua's pure parts (#510 step 9 PR D): the sandbox over a fake CPU, our attack
-- and the enemy's strike as read off their simulations, turns left and the turn-event scan.
-- What the ROM's own functions return is proven by the `sightprobe` scenario, not here.
-- Run: lua tools/playtest/test_sight.lua
local here = (arg[0]:match("(.*/)")) or "./"
local Sight = dofile(here .. "sight.lua")
local Board = dofile(here .. "board.lua")
local fakeMem = dofile(here .. "fakemem.lua")
-- sight.lua's own text, for the tests that read a call's place off the source
local sightSrc
do
    local f = assert(io.open(here .. "sight.lua"))
    sightSrc = f:read("a")
    f:close()
end

local tests, fails = 0, 0
local function check(got, want, msg)
    tests = tests + 1
    if got ~= want then
        fails = fails + 1
        print(string.format("FAIL: %s\n  got  %s\n  want %s", msg, tostring(got), tostring(want)))
    end
end

-- A CPU whose "game function" at 0x08001000 returns r0 + r1 after `cost` frames (to the
-- loop lr names), and at 0x08002000 never returns.
local function fakeCpu(cost)
    local regs = { sp = 0x03007D00, cpsr = 0x1F, pc = 0x1F8, lr = 0 }
    for i = 0, 12 do regs["r" .. i] = 0 end
    local ram, loads, ran = {}, 0, 0
    local cpu = {}
    function cpu.read(r) return regs[r] end
    function cpu.write(r, v) regs[r] = v end
    function cpu.read32(a) return ram[a] or 0 end
    function cpu.write16(a, v) ram[a] = v end
    function cpu.write32(a, v) ram[a] = v end
    function cpu.save() return { pc = regs.pc, sp = regs.sp, marker = ram.marker } end
    function cpu.load(st)
        loads = loads + 1
        regs.pc, regs.sp, ram.marker = st.pc, st.sp, st.marker
    end
    function cpu.frames(done, max)
        for _ = 1, max do
            ran = ran + 1
            if regs.pc == 0x08001000 and ran >= cost then
                regs.r0 = regs.r0 + regs.r1
                local loop = regs.lr & ~1
                regs.pc = loop + 4   -- bx lr, then the pipeline reads ahead
                -- the halt loop's str: the marker (its literal at +10) set to its own address
                local marker = ram[loop + Sight.HALT_MARKER]
                if ram[loop] == Sight.HALT_LOOP[1] and marker then ram[marker] = marker end
            end
            if done() then return true end
        end
        return false
    end
    cpu.live = function(done, max) return cpu.frames(done, max) end
    return cpu, function() return loads, ram end
end

-- mGBA's pc write refills the pipeline: a pc written in the BIOS reads one instruction ahead
-- (measured at the halt loop, ARM: +4). `keep` lists the pcs the test sets as they read.
local function refills(cpu, keep)
    local write = cpu.write
    function cpu.write(r, v)
        if r == "pc" and v < 0x08000000 and not (keep or {})[v] then v = v + 4 end
        write(r, v)
    end
end

-- test_roll_chance_counts_every_draw: Roll1RN and Roll2RN's odds over every 16-bit NextRN
-- (rng.c). NextRN_100 = NextRN() * 100 / 0x10000 gives 0 to 656 of the 65536 values, so a 1%
-- roll passes 656/65536 of the time; Roll2RN lands on the published 2RN table to 0.1% (a
-- displayed 70 lands 82.3% of the time, a 30 only 18.3%).
do
    local function near(got, want) return math.abs(got - want) < 0.0005 end
    check(Sight.rollChance(2, 0), 0, "2RN: 0 never")
    check(Sight.rollChance(2, 100), 1, "2RN: 100 always")
    check(Sight.rollChance(2, 0xFFFF), 1, "2RN: a u16 past 100 always")
    check(near(Sight.rollChance(2, 50), 0.505), true, "2RN: 50 lands 50.5%")
    check(near(Sight.rollChance(2, 70), 0.823), true, "2RN: 70 lands 82.3%")
    check(near(Sight.rollChance(2, 30), 0.183), true, "2RN: 30 lands 18.3%")
    check(Sight.rollChance(1, 1), 656 / 0x10000, "1RN: a 1% roll is the 656 draws that give 0")
    check(Sight.rollChance(1, 0), 0, "1RN: 0 never")
end

-- test_played_splits_every_roll_that_can_go_both_ways: a fake battle -- our blow (2RN 50),
-- its crit (1RN 10) only when it lands, a crit-free counter (1RN 0) that cannot pass, and the
-- counter's own blow (2RN 100) that cannot miss -- is run once per outcome, each roll forced
-- through r1, and the breakpoints are cleared after.
do
    local regs, holds, at = { r0 = 0, r1 = 0 }, {}, {}
    local cpu = {
        read = function(r) return regs[r] end,
        write = function(r, v) regs[r] = v end,
        breakpoint = function(addr, fn) holds[#holds + 1] = addr; at[addr] = fn; return #holds end,
        unbreak = function(id) at[holds[id]] = nil end,
    }
    local S = { BattleRoll1RN = 0x0802B000, BattleRoll2RN = 0x0802B100 }
    local function roll(addr, threshold)
        regs.r0, regs.r1 = threshold, 0
        at[addr]()
        return regs.r1 == 1
    end
    local dealt, back, runs = 0, 0, 0
    local function battle()
        runs = runs + 1
        dealt, back = 0, 0
        if roll(S.BattleRoll2RN, 50) then
            dealt = roll(S.BattleRoll1RN, 10) and 15 or 5
        end
        roll(S.BattleRoll1RN, 0)
        if roll(S.BattleRoll2RN, 100) then back = 3 end
    end
    local called = {}
    local leaves = Sight.played(cpu, function(addr, args)
        called[#called + 1] = string.format("%X:%s", addr, table.concat(args, ","))
        battle()
    end, { 0x0802C001, { 1, 2 } }, S, function() return dealt, back end)
    check(called[1], "802C001:1,2", "played: the simulation is called with its own arguments")
    check(runs, 3, "played: one run per outcome (crit, hit, miss)")
    local d, b = Sight.exchangeOf(leaves)
    local hit, crit = Sight.rollChance(2, 50), Sight.rollChance(1, 10)
    check(math.abs(d[15] - hit * crit) < 1e-12, true, "played: the crit's chance")
    check(math.abs(d[5] - hit * (1 - crit)) < 1e-12, true, "played: the plain hit's")
    check(math.abs(d[0] - (1 - hit)) < 1e-12, true, "played: the miss's")
    check(math.abs(b[3] - 1) < 1e-12, true, "played: the sure counter in every outcome")
    local _, _, joint = Sight.exchangeOf(leaves)
    local pairsSeen = {}
    for _, x in ipairs(joint) do pairsSeen[#pairsSeen + 1] = x.dealt .. ":" .. x.back end
    check(table.concat(pairsSeen, " "), "0:3 5:3 15:3", "played: the joint pairs, dealt then back")
    check(math.abs(joint[1].p - (1 - hit)) < 1e-12, true, "played: a pair's chance is its leaf's")
    check(at[S.BattleRoll1RN] == nil and at[S.BattleRoll2RN] == nil, true,
          "played: the breakpoints are cleared")
end

-- test_talks_reads_each_entry_the_walk_hands_its_checks: the game's walk hands two talk
-- entries to its checks (one plain, one with an asm condition); CheckForCharacterEvents keeps
-- the available one, the walk was asked for a pair no entry names, and the breakpoints go.
do
    local holds, at = {}, {}
    local m = fakeMem()
    local u8, u32, w8, w32 = m.u8, m.u32, m.w8, m.w32
    local INFO, LIST, GROUP = 0x03000000, 0x08100000, 0x08200000
    w32(GROUP + 4, LIST)
    w8(LIST + 0x08, 0x01); w8(LIST + 0x09, 0x0E)        -- Eirika -> Ross
    w8(LIST + 0x18, 0x00); w8(LIST + 0x19, 0x0A)        -- anyone -> Garcia, asm-gated
    local S = { GetChapterEventDataPointer = 1, SearchAvailableEvent = 2, EvCheck03_CHAR = 3,
                EvCheck04_CHARASM = 4, CheckForCharacterEvents = 5 }
    local asked
    local api = {
        SYM = S, mem = { u8 = u8, u32 = u32 }, write8 = w8, write32 = w32,
        chapter = function() return 2 end,
        cpu = { breakpoint = function(addr, fn) holds[#holds + 1] = addr; at[addr] = fn; return #holds end,
                unbreak = function(id) at[holds[id]] = nil end },
    }
    local function sandbox(fn)
        return fn(function(addr, args)
            if addr == S.GetChapterEventDataPointer then return GROUP end
            if addr == S.SearchAvailableEvent then
                asked = { u8(INFO + 0x1A), u8(INFO + 0x1B) }
                at[S.EvCheck03_CHAR]()
                w32(INFO, LIST + 0x10); at[S.EvCheck04_CHARASM]()
                return 0
            end
            if addr == S.CheckForCharacterEvents then return args[2] == 0x0E and 1 or 0 end
        end, INFO)
    end
    local talks = Sight.talks(api, sandbox)
    check(#talks, 1, "talks: only the available one is kept")
    check(talks[1] and talks[1].a, 0x01, "talks: its pidA")
    check(talks[1] and talks[1].b, 0x0E, "talks: its pidB")
    check(asked and asked[1] == 0xFF and asked[2] == 0xFF, true, "talks: the walk matches no entry")
    check(at[S.EvCheck03_CHAR] == nil and at[S.EvCheck04_CHARASM] == nil, true,
          "talks: the breakpoints are cleared")
end

-- test_odds_compose_exchanges: two 50/50 exchanges of 6 on a 10 HP unit kill a quarter of the
-- time; the damage is capped at the HP; worst and least read a distribution's ends.
do
    local half = { [0] = 0.5, [6] = 0.5 }
    local dead, mean = Sight.odds({ half, half }, 10)
    check(dead, 0.25, "odds: both must land")
    check(mean, 0.5 * 6 + 0.25 * 10, "odds: the mean, 12 capped at the 10 HP")
    check(Sight.odds({ { [4] = 1 } }, 10), 0, "odds: one sure 4 does not kill 10")
    check(Sight.worst(half), 6, "worst: the largest damage with a chance")
    check(Sight.worst({ [0] = 1, [9] = 0 }), 0, "worst: a damage with no chance is not counted")
    check(Sight.least(half), 0, "least: the smallest")
end

-- test_batch_is_one_round_trip_and_reads_do_not_leak: three reads inside one batch load the
-- state once; each read's journaled writes are undone when it returns, so the next sees the
-- byte as it was; the result of each call still comes back.
do
    local cpu, seen = fakeCpu(1)
    local bytes = { [0x100] = 7 }
    local outer = { cpu = cpu, mem = { u8 = function(a) return bytes[a] or 0 end,
                                       u16 = function(a) return bytes[a] or 0 end,
                                       u32 = function(a) return bytes[a] or 0 end },
                    write8 = function(a, v) bytes[a] = v end,
                    write16 = function(a, v) bytes[a] = v end,
                    write32 = function(a, v) bytes[a] = v end }
    local sandbox, api = Sight.batching(outer)
    local before = { bytes[0x100] }

    local sums = sandbox(function()
        local out = {}
        for i = 1, 3 do
            out[i] = sandbox(function(call)
                before[#before + 1] = bytes[0x100]
                api.write8(0x100, 99)
                return call(0x08001000, { i, 10 })
            end)
        end
        return out
    end)
    check(select(1, seen()), 1, "batch: one load for three reads")
    check(table.concat(sums, ","), "11,12,13", "batch: each read's answer")
    check(table.concat(before, ","), "7,7,7,7", "batch: no read sees another's write")
    check(bytes[0x100], 7, "batch: the write is undone")
    -- an unbatched read is its own round trip, as before
    sandbox(function(call) return call(0x08001000, { 1, 1 }) end)
    check(select(1, seen()), 2, "unbatched: its own load")
end

-- open(): whether a sandbox is open, nested ones included, journal or no journal -- a game
-- call's own writes are never journaled, so Sight.new keeps no units() read made while it is.
do
    local cpu = fakeCpu(1)
    local mem = { u8 = function() return 0 end, u16 = function() return 0 end,
                  u32 = function() return 0 end }
    local nop = function() end
    local sandbox, _, open = Sight.batching({ cpu = cpu, mem = mem, write8 = nop,
                                              write16 = nop, write32 = nop })
    check(open(), false, "open: no sandbox yet")
    sandbox(function(call)
        check(open(), true, "open: inside a sandbox")
        sandbox(function() call(0x08001000, { 1, 1 }) end)
        check(open(), true, "open: still, after a nested call returns with nothing journaled")
    end)
    check(open(), false, "open: closed after the outermost returns")
end

-- test_open_map_does_not_leak_into_the_next_read: the plan's door at (2,1) is opened on the
-- judged phase's board (Sight.openMap: the change's tile and its terrain), and the next judged
-- plan in the same batch finds it shut. TriggerMapChanges' own writes were journaled by no one,
-- so one plan's open door stood open in every later plan's phase (PR #596 review).
do
    local cpu = fakeCpu(1)
    local bytes = {}
    local outer = { cpu = cpu, mem = { u8 = function(a) return bytes[a] or 0 end,
                                       u16 = function(a) return bytes[a] or 0 end,
                                       u32 = function(a) return bytes[a] or 0 end },
                    write8 = function(a, v) bytes[a] = v end,
                    write16 = function(a, v) bytes[a] = v end,
                    write32 = function(a, v) bytes[a] = v end }
    local sandbox, api = Sight.batching(outer)
    local S = { GetMapChangeIdAt = 1, GetMapChange = 2, gTilesetTerrainLookup = 0x10,
                gBmMapBaseTiles = 0x20, gBmMapTerrain = 0x30 }
    -- row pointers (one row each for y = 0..1), the lookup table, the change: 1x1 at (2,1)
    bytes[0x20], bytes[0x30], bytes[0x10] = 0x100, 0x200, 0x400
    bytes[0x104], bytes[0x204] = 0x140, 0x240     -- row 1 of each grid
    bytes[0x140 + 4], bytes[0x240 + 2] = 0x50, 0x1E  -- the door's tile and TERRAIN_DOOR
    bytes[0x400 + (0x88 >> 2)] = 0x01               -- the open tile's terrain: plains
    local mc = 0x500
    bytes[mc + 1], bytes[mc + 2], bytes[mc + 3], bytes[mc + 4], bytes[mc + 8] = 2, 1, 1, 1, 0x600
    bytes[0x600] = 0x88
    local function call(fn, args)
        if fn == S.GetMapChangeIdAt then
            return (args[1] == 2 and args[2] == 1) and 3 or 0xFFFFFFFF
        end
        check(args[1], 3, "openMap: asks for the change at the tile")
        return mc
    end
    local seen = {}
    sandbox(function()
        sandbox(function()
            Sight.openMap(api, call, S, 2, 1)
            seen[1] = bytes[0x242] .. "/" .. bytes[0x144]
        end)
        sandbox(function() seen[2] = bytes[0x242] .. "/" .. bytes[0x144] end)
        sandbox(function()
            Sight.openMap(api, call, S, 5, 0)
            seen[3] = bytes[0x242]
        end)
    end)
    check(seen[1], "1/136", "openMap: the door's terrain and tile are the change's")
    check(seen[2], "30/80", "openMap: the next plan finds the door shut")
    check(seen[3], 30, "openMap: a tile with no change changes nothing")
end

-- test_map_change_tiles_are_the_rectangles_drawn_tiles: the change at (2,1) is 2x2 at (2,1);
-- the game writes only its non-zero tiles (ApplyMapChangesById), so (3,2), a 0, is not one.
-- A tile with no change has none (nil).
do
    local bytes = {}
    local mem = { u8 = function(a) return bytes[a] or 0 end,
                  u16 = function(a) return bytes[a] or 0 end,
                  u32 = function(a) return bytes[a] or 0 end }
    local S = { GetMapChangeIdAt = 1, GetMapChange = 2, gTilesetTerrainLookup = 0x10 }
    local mc = 0x500
    bytes[mc + 1], bytes[mc + 2], bytes[mc + 3], bytes[mc + 4], bytes[mc + 8] = 2, 1, 2, 2, 0x600
    bytes[0x600], bytes[0x602], bytes[0x604], bytes[0x606] = 0x88, 0x8C, 0x90, 0
    local function call(fn, args)
        if fn == S.GetMapChangeIdAt then
            return (args[1] == 2 and args[2] == 1) and 3 or 0xFFFFFFFF
        end
        return args[1] == 3 and mc or 0
    end
    local got = {}
    for _, t in ipairs(Sight.mapChangeTiles(mem, call, S, 2, 1) or {}) do
        got[#got + 1] = t.x .. "," .. t.y .. "=" .. t.tile
    end
    check(table.concat(got, " "), "2,1=136 3,1=140 2,2=144", "change: the drawn tiles, row by row")
    check(Sight.mapChangeTiles(mem, call, S, 5, 0), nil, "change: none at a tile without one")
end

-- test_map_change_ground_is_only_what_the_unit_can_walk: with a unit's movement costs (the
-- s8 table GetUnitMovementCost returns, -1 = no way), only the change's tiles it can walk are
-- ground, each with its cost: a wall the change draws is not (#612 review).
do
    local bytes = {}
    local mem = { u8 = function(a) return bytes[a] or 0 end,
                  s8 = function(a) local v = bytes[a] or 0 return v >= 0x80 and v - 0x100 or v end,
                  u16 = function(a) return bytes[a] or 0 end,
                  u32 = function(a) return bytes[a] or 0 end }
    local S = { GetMapChangeIdAt = 1, GetMapChange = 2, gTilesetTerrainLookup = 0x10 }
    local mc, costs = 0x500, 0x700
    bytes[0x10] = 0x400
    bytes[mc + 1], bytes[mc + 2], bytes[mc + 3], bytes[mc + 4], bytes[mc + 8] = 2, 1, 3, 1, 0x600
    bytes[0x600], bytes[0x602], bytes[0x604] = 0x88, 0x8C, 0x90
    bytes[0x400 + (0x88 >> 2)], bytes[0x400 + (0x8C >> 2)], bytes[0x400 + (0x90 >> 2)] = 1, 2, 3
    bytes[costs + 1], bytes[costs + 2], bytes[costs + 3] = 1, 0xFF, 2
    local function call(fn, args)
        if fn == S.GetMapChangeIdAt then return 3 end
        return mc
    end
    local got = {}
    for _, t in ipairs(Sight.mapChangeTiles(mem, call, S, 2, 1, costs)) do
        got[#got + 1] = t.x .. "," .. t.y .. "/" .. t.terrain .. "/" .. t.cost
    end
    check(table.concat(got, " "), "2,1/1/1 4,1/3/2", "ground: the wall is left out, costs kept")
    check(#Sight.mapChangeTiles(mem, call, S, 2, 1), 3, "ground: no costs, every drawn tile")
end

-- test_equip_does_not_leak_into_the_next_read: EquipUnitItemSlot (bmitem.c) moves the item to
-- the front of the bag, a write the game makes and no journal sees. Two judged plans in one
-- batch: the first equips slot 2, and the second must find the bag as it was, its slot 0 still
-- the first item (vanilla Ch5: Seth's Iron Sword left in front, Joshua's death to his Silver
-- Lance judged impossible).
do
    local cpu = fakeCpu(1)
    local bytes = {}
    local outer = { cpu = cpu, mem = { u8 = function(a) return bytes[a] or 0 end,
                                       u16 = function(a) return bytes[a] or 0 end,
                                       u32 = function(a) return bytes[a] or 0 end },
                    write8 = function(a, v) bytes[a] = v end,
                    write16 = function(a, v) bytes[a] = v end,
                    write32 = function(a, v) bytes[a] = v end, Board = Board }
    local sandbox, api = Sight.batching(outer)
    local S, u = { EquipUnitItemSlot = 0x08016C34 }, { addr = 0x200 }
    local function bag()
        local out = {}
        for k = 0, Board.ITEM_COUNT - 1 do out[#out + 1] = bytes[u.addr + Board.UNIT_ITEMS + k * 2] or 0 end
        return table.concat(out, ",")
    end
    for k, item in ipairs({ 23, 108, 1 }) do bytes[u.addr + Board.UNIT_ITEMS + (k - 1) * 2] = item end
    -- the game's own EquipUnitItemSlot, written straight to memory as the game writes it
    local function call(fn, args)
        check(fn, S.EquipUnitItemSlot, "equip: calls EquipUnitItemSlot")
        local base = args[1] + Board.UNIT_ITEMS
        local item = bytes[base + args[2] * 2]
        for i = args[2], 1, -1 do bytes[base + i * 2] = bytes[base + (i - 1) * 2] end
        bytes[base] = item
    end
    local seen = {}
    sandbox(function()
        sandbox(function()
            Sight.equip(api, call, S, u, 2)
            seen[1] = bag()
        end)
        sandbox(function() seen[2] = bag() end)
    end)
    check(seen[1], "1,23,108,0,0", "equip: slot 2 is moved to the front")
    check(seen[2], "23,108,1,0,0", "equip: the next read finds the bag as it was")
    Sight.equip(api, function() error("equip: slot 0 is already in hand") end, S, u, 0)
    -- keep16 makes no write itself (a real one drops harness memos); the sandbox still puts
    -- the halfword back
    local writes, real = 0, outer.write16
    outer.write16 = function(a, v) writes = writes + 1; real(a, v) end
    local at = u.addr + Board.UNIT_ITEMS
    sandbox(function()
        sandbox(function()
            api.keep16(at, 1)
            check(writes, 0, "keep16: no write made")
            bytes[at] = 99
        end)
    end)
    check(bytes[at], 23, "keep16: put back when the sandbox returns")
end

-- test_a_self_heal_is_no_staff (ADR 0421): Sight.selfHeals lists the heals a unit uses on itself.
-- A Heal staff its holder cannot use (CanUnitUseStaff 0: no rank, silenced) is no such heal, so
-- the wear does not take it for one; the Vulnerary behind it is.
do
    local S = { GetUnitItemHealAmount = 1, CanUnitUseStaff = 2 }
    local staff, vul = 0x6C, 0x6E
    local B = { staffRange = function(item) return (item & 0xFF) == staff and 1 or nil end }
    local function call(fn, args)
        if fn == S.GetUnitItemHealAmount then return 10 end
        if fn == S.CanUnitUseStaff then return 0 end
        error("selfHeals: asked " .. tostring(fn))
    end
    local u = { addr = 0x200, items = { { id = staff, uses = 20 }, { id = vul, uses = 3 } } }
    local got = Sight.selfHeals(B, call, S, u)
    check(#got, 1, "selfHeals: the staff its holder cannot use is no self-heal")
    check(got[1] and got[1].slot, 1, "selfHeals: the Vulnerary, slot 1")
    check(got[1] and got[1].amount, 10, "selfHeals: its amount")
    u.items = { { id = staff, uses = 20 } }
    check(#Sight.selfHeals(B, call, S, u), 0, "selfHeals: a staff alone heals its holder never")
end

-- test_a_barrier_is_no_heal_staff: Sight.healStaves lists the staves a unit heals one ally with.
-- GetUnitItemHealAmount adds its holder's power for any staff (bmitem.c), so a Barrier read 5
-- here and was offered as a heal; the game then opened its own target selection and the run
-- crashed (vanilla E_16, PR #631). A Heal its holder cannot use is none; a Physic's reach of 0 is
-- its holder's Mag/2.
do
    local S = { GetUnitItemHealAmount = 1, CanUnitUseStaff = 2, GetUnitMagBy2Range = 3,
                BattleInitItemEffect = 4, GetBattleUnitStaffExp = 5, gBattleActor = 0x10 }
    local barrier, heal, physic = 0x59, 0x4B, 0x4E
    local B = { staffRange = function(item) return (item & 0xFF) == physic and 0 or 1 end }
    local usable = { [barrier] = true, [physic] = true }
    local function call(fn, args)
        if fn == S.GetUnitItemHealAmount then return ((args[2] & 0xFF) == barrier) and 5 or 15 end
        if fn == S.CanUnitUseStaff then return usable[args[2] & 0xFF] and 1 or 0 end
        if fn == S.GetUnitMagBy2Range then return 4 end
        if fn == S.BattleInitItemEffect then return 0 end
        if fn == S.GetBattleUnitStaffExp then return 11 end
        error("healStaves: asked " .. tostring(fn))
    end
    local u = { addr = 0x200, items = { { id = barrier, uses = 15 }, { id = heal, uses = 30 },
                                         { id = physic, uses = 15 } } }
    local got = Sight.healStaves(B, call, S, u)
    check(#got, 1, "healStaves: the Barrier and the unusable Heal are no heal staves")
    check(got[1] and got[1].slot, 2, "healStaves: the Physic, slot 2")
    check(got[1] and got[1].amount, 15, "healStaves: its amount")
    check(got[1] and got[1].range, 4, "healStaves: its reach, Mag/2")
    check(got[1] and got[1].exp, 11, "healStaves: its experience")
end

-- test_holding_puts_the_bag_back: s.holding lists the unit's items then the ones it is handed
-- (the first empty slots), and the bag is byte-identical after it, whether fn returns or
-- errors; a bag with an item past a gap (which the board read would not list) raises.
do
    local m = fakeMem()
    local outer = { cpu = fakeCpu(1), mem = m, write8 = m.w8, write16 = m.w16, write32 = m.w32,
                    Board = Board, SYM = {}, map = function() return 1, 1 end }
    local sandbox, api = Sight.batching(outer)
    local s = { batch = sandbox }
    function s.holding(u, values, fn) return Sight.holding(api, sandbox, u, values, fn) end
    local addr = 0x02030400
    local function bag()
        local out = {}
        for k = 0, Board.ITEM_COUNT - 1 do out[#out + 1] = m.u16(addr + Board.UNIT_ITEMS + k * 2) end
        return table.concat(out, ",")
    end
    m.w16(addr + Board.UNIT_ITEMS, 0x2301)
    local u = { addr = addr, items = { { id = 0x01, uses = 0x23 } } }
    local seen
    -- a nested read, as every real one is (the outermost sandbox is the emulator's own state)
    s.batch(function()
        local got = s.holding(u, { 0x1410, 0x0A20 }, function(copy)
            seen = bag()
            return #copy.items .. ":" .. copy.items[3].id .. "x" .. copy.items[3].uses
        end)
        check(got, "3:32x10", "holding: the copy lists every item handed")
        check(seen, "8961,5136,2592,0,0", "holding: the game's bag holds them after the unit's own")
        check(bag(), "8961,0,0,0,0", "holding: the bag is as it was on return")
        local ok = pcall(s.holding, u, { 0x1410 }, function() error("fn fails") end)
        check(ok, false, "holding: an error in fn passes through")
        check(bag(), "8961,0,0,0,0", "holding: and the bag is as it was after it")
        check(pcall(s.holding, u, { 1, 2, 3, 4, 5 }, function() end), false, "holding: no room raises")
        -- an item past a gap: the packed read lists one, the game holds two
        m.w16(addr + Board.UNIT_ITEMS + 4, 0x0505)
        local packed, why = pcall(s.holding, u, { 0x1410 }, function() end)
        check(packed, false, "holding: a bag with a gap raises")
        check(tostring(why):find("not packed", 1, true) ~= nil, true, "holding: and says why")
        check(bag(), "8961,0,1285,0,0", "holding: the refused bag is untouched")
    end)
end

-- keepAi, on byte-true memory (aiFlags is one byte of a halfword whose other byte is the unit's
-- index): what the game's AI writes on unit structs while one decides is put back -- every
-- unit's aiFlags and AI block, not the decider's alone. A looter the closings replay played
-- past its last village read as no looter for the rest of the batch (#510).
do
    local cpu = fakeCpu(1)
    local m, reads = fakeMem(), 0
    local u8, w8, plain16 = m.u8, m.w8, m.u16
    m.u16 = function(a) reads = reads + 1; return plain16(a) end
    local outer = { cpu = cpu, mem = m, write8 = w8, write16 = m.w16, write32 = m.w32,
                    Board = Board }
    local FLAGS, BLOCK, LAST = Sight.UNIT_AI_FLAGS, Sight.UNIT_AI_CONFIG,
        Sight.UNIT_AI_CONFIG + Sight.UNIT_AI_WORDS * 2 - 1
    local e, other = { addr = 0x02030000 }, { addr = 0x02030100 }
    local byId = { [3] = e, [9] = other }
    -- the game's own writes, straight to memory: every AI byte of both units set to `v`
    local function gameWrites(v)
        for _, o in pairs(byId) do
            w8(o.addr + FLAGS, v)
            for at = o.addr + BLOCK, o.addr + LAST do w8(at, v) end
        end
    end
    local function ai(o)
        local out = { u8(o.addr + FLAGS), u8(o.addr + FLAGS + 1) }
        for at = o.addr + BLOCK, o.addr + LAST do out[#out + 1] = u8(at) end
        return table.concat(out, ",")
    end
    gameWrites(4)
    w8(e.addr + FLAGS + 1, 3); w8(other.addr + FLAGS + 1, 9)   -- their indexes
    local first, inner
    local function sandboxed(sandbox, api)
        sandbox(function()
            sandbox(function()
                Sight.keepAi(api, byId)
                local kept = reads
                Sight.keepAi(api, byId)
                check(reads, kept, "keepAi: a second keep in one sandbox reads nothing")
                gameWrites(7)
                -- a sandbox inside puts back what IT found, the first decision's writes
                sandbox(function()
                    Sight.keepAi(api, byId)
                    check(reads > kept, true, "keepAi: a nested sandbox keeps afresh")
                    gameWrites(8)
                end)
                inner = ai(e) .. " " .. ai(other)
            end)
            first = ai(e) .. " " .. ai(other)
        end)
    end
    sandboxed(Sight.batching(outer))
    check(inner, "7,3,7,7,7,7,7,7,7,7 7,9,7,7,7,7,7,7,7,7",
        "keepAi: a nested sandbox puts back the bytes as it found them")
    check(first, "4,3,4,4,4,4,4,4,4,4 4,9,4,4,4,4,4,4,4,4",
        "keepAi: every unit's aiFlags and AI block are put back, the index untouched")

    -- the guard (PT_LEAKGUARD): a word a nested sandbox leaves changed is logged once, with
    -- a count, and put back so play goes on as if kept; every leaking word is logged, not the
    -- first alone. Writes all kept log nothing. Sight.keepAi is that keep.
    local function guarded()
        return { { e.addr, Board.UNIT_SIZE, "unit struct" }, { other.addr, Board.UNIT_SIZE, "unit struct" } }
    end
    local log = {}
    local sandbox, api = Sight.batching(outer, guarded, log)
    local after
    sandbox(function()
        for k = 1, 2 do
            sandbox(function() w8(other.addr + BLOCK + 2, 1); w8(e.addr + 2, k == 1 and 0x55 or 0x77) end)
        end
        after = m.u8(other.addr + BLOCK + 2) .. "," .. m.u8(e.addr + 2)
    end)
    check(#log, 2, "guard: both leaking words are logged, each once")
    check(after, "4,0", "guard: each leaking word is put back as the sandbox found it")
    local line = Sight.leakLine(log[2])
    check(line:find(("sandbox leak: the unit struct at 0x%08X, word +0x40"):format(other.addr),
              1, true) ~= nil and line:find("(2 times)", 1, true) ~= nil, true,
          "guard: the line names the struct, the word and how often: " .. line)
    line = Sight.leakLine(log[1])
    check(line:find("is 0x00550000 or 0x00770000", 1, true) ~= nil, true,
          "guard: a word leaked to two values says both: " .. line)
    -- small values (a flag word leaked to 1, then 2) are values, never list slots
    local small = {}
    for _, v in ipairs({ 1, 2, 1 }) do
        Sight.logLeak(small, { name = "unit struct", addr = 0x02030000, off = 4, was = 0, now = v })
    end
    local ok2, said = pcall(Sight.leakLine, small[1])
    check(ok2 and said:find("is 0x00000001 or 0x00000002 after", 1, true) ~= nil
          and said:find("(3 times)", 1, true) ~= nil, true,
          "guard: a word leaked to 1, then 2, says both and counts three: " .. tostring(said))
    log = {}
    sandbox, api = Sight.batching(outer, guarded, log)
    sandboxed(sandbox, api)
    check(#log, 0, "guard: writes that keepAi held log nothing")
end

-- refresh: the game's map refresh rewrites a red's fog bits for the board it runs on (a
-- judged plan's), and the next plan must find them as they were (vanilla Ch6: an enemy one
-- plan revealed stayed seen for the rest of the batch). The fake call is bmmap.c's write.
do
    local m = fakeMem()
    local outer = { cpu = fakeCpu(1), mem = m, write8 = m.w8, write16 = m.w16,
                    write32 = m.w32, Board = Board }
    local S, STATE = { RefreshEntityBmMaps = 0x0801A2D8 }, 0x0C
    local red = { addr = 0x02030200 }
    m.w32(red.addr + STATE, Board.US_BIT9 | 0x00010000)
    local function call(fn)
        check(fn, S.RefreshEntityBmMaps, "refresh: calls RefreshEntityBmMaps")
        m.w32(red.addr + STATE, (m.u32(red.addr + STATE) & ~Board.US_BIT9) | 0x100)
    end
    local TRAPS = 0x0203A614
    local log = {}
    local sandbox, api = Sight.batching(outer, function()
        return { { red.addr, Board.UNIT_SIZE, "unit struct" },
                 { TRAPS, Sight.TRAP_MAX * Sight.TRAP_SIZE, "trap pool" } }
    end, log)
    local seen = {}
    local ok, why = pcall(sandbox, function()
        sandbox(function()
            Sight.refresh(api, call, S, { [130] = red })
            seen[1] = m.u32(red.addr + STATE)
        end)
        seen[2] = m.u32(red.addr + STATE)
    end)
    check(ok and #log == 0, true, "refresh: the guard finds nothing left changed: " .. tostring(why))
    check(seen[1], 0x00010100, "refresh: the plan's own read sees the enemy revealed")
    check(seen[2], Board.US_BIT9 | 0x00010000, "refresh: the next plan finds it in fog again")

    -- keepRide: a ballista's rider that decides to strike with its own weapon steps off it
    -- (bmarch.c TryRemoveUnitFromBallista, written here as the game writes it); the next plan
    -- finds it riding, the ballista ridden and on its tile. A unit on foot keeps nothing.
    local RIDE, trap = Sight.UNIT_BALLISTA, TRAPS + 2 * Sight.TRAP_SIZE
    local S2 = { sTrapPool = TRAPS }
    m.w32(red.addr + STATE, Sight.US_IN_BALLISTA)
    m.w8(red.addr + RIDE, 2); m.w8(red.addr + RIDE + 1, 5)        -- its trap; movBonus
    m.w8(trap, 7); m.w8(trap + 1, 3); m.w8(trap + 5, 1); m.w8(trap + 6, 4)   -- tile, ridden, uses
    m.w32(red.addr + Sight.UNIT_SPRITE, 0x0203A0A8)
    local function ride()
        return table.concat({ m.u32(red.addr + STATE), m.u8(red.addr + RIDE), m.u8(trap),
                              m.u8(trap + 1), m.u8(trap + 5), m.u8(trap + 6),
                              m.u32(red.addr + Sight.UNIT_SPRITE) }, ",")
    end
    local riding = ride()
    local function stepsOff()
        m.w32(red.addr + STATE, 0)
        m.w8(red.addr + RIDE, 0)
        m.w8(trap, 9); m.w8(trap + 1, 9); m.w8(trap + 5, 0)
        m.w32(red.addr + Sight.UNIT_SPRITE, 0)        -- RefreshUnitSprites, the unit hidden
    end
    ok, why = pcall(sandbox, function()
        sandbox(function()
            Sight.keepFog(api, { red })
            Sight.keepRide(api, S2, red, { red })
            stepsOff()
            seen[3] = ride()
        end)
        seen[4] = ride()
    end)
    check(ok and #log == 0, true, "keepRide: the guard finds nothing left changed: " .. tostring(why))
    check(seen[3], "0,0,9,9,0,4,0", "keepRide: the plan's own read sees the rider on foot")
    check(seen[4], riding, "keepRide: the next plan finds it riding, the ballista where it was")
    sandbox(function()
        sandbox(function()
            Sight.keepFog(api, { red })
            m.w8(trap + 5, 0)
        end)
    end)
    check(#log == 1 and Sight.leakLine(log[1]):find("sandbox leak: the trap pool at", 1, true)
          ~= nil and m.u8(trap + 5), 1, "guard: a trap a nested sandbox leaves changed is "
          .. "logged and put back")
    m.w32(red.addr + STATE, 0)
    local kept = 0
    Sight.keepRide({ mem = m, keep16 = function() kept = kept + 1 end }, S2, red, { red })
    check(kept, 0, "keepRide: a unit on foot keeps nothing")
end

-- aiPhaseStart: a simulated enemy phase starts as the game's does (cp_phase.c AiPhaseInit). The
-- player phase leaves gAiState as the last enemy phase ended it, or as the save found it on
-- turn 1, and gPlaySt.faction blue: the judged phase must find the game's phase-start values,
-- have the two setup functions run on them with the faction red, and hand everything back.
do
    local m = fakeMem()
    local outer = { cpu = fakeCpu(1), mem = m, write8 = m.w8, write16 = m.w16,
                    write32 = m.w32, Board = Board, chapter = function() return 5 end }
    local AI, PLAY, TABLE = 0x0203AA04, 0x0202BCF0, 0x080D8178
    local S = { gAiState = AI, gPlaySt = PLAY, gAiItemConfigTable = TABLE,
                UpdateAllPhaseHealingAIStatus = 0x0803E640, SetupUnitInventoryAIFlags = 0x0803C064 }
    local blue, red = { addr = 0x02030000 }, { addr = 0x02030200 }
    local FLAGS, COUNTER = Sight.UNIT_AI_FLAGS, Sight.UNIT_AI_CONFIG + 6
    m.w8(PLAY + 0x0F, Sight.PHASES[1])                            -- the player's phase; chapter 5
    m.w32(TABLE + 5 * 4, 0x80000003)
    m.w8(AI + 0x78, 2); m.w8(AI + 0x7B, 4); m.w8(AI + 0x7E, 3)    -- orderState, BERSERKED, unk7E
    m.w32(AI + 0x80, 0xDEAD); m.w8(AI + 0x84, 1); m.w8(AI + 0x85, 9)
    for k = 0, 7 do m.w8(AI + 0x86 + k, 0x10 + k) end
    m.w8(AI + 0x8E, 0x77)                                         -- the byte past cmd_result
    m.w8(blue.addr + FLAGS, 0x02); m.w8(blue.addr + COUNTER, 1); m.w8(red.addr + FLAGS, 0)
    local function state()
        local out = { m.u8(PLAY + 0x0F), m.u8(AI + 0x78), m.u8(AI + 0x7B), m.u8(AI + 0x7E),
                      m.u32(AI + 0x80), m.u8(AI + 0x84), m.u8(AI + 0x85) }
        for k = 0, 8 do out[#out + 1] = m.u8(AI + 0x86 + k) end
        for _, v in ipairs({ m.u8(blue.addr + FLAGS), m.u8(blue.addr + COUNTER),
                             m.u8(red.addr + FLAGS) }) do out[#out + 1] = v end
        return table.concat(out, ",")
    end
    local stale, atCall, ran, setsUp = state(), nil, {}, true
    -- the game's writes when the two setup functions are in the list (`setsUp`): the red's
    -- heal flag, the best blue Mov, a blue's flags and ally count
    local function call(list)
        atCall = atCall or state()
        for _, c in ipairs(list) do ran[#ran + 1] = c[1] end
        if not setsUp then return 17 end
        m.w8(red.addr + FLAGS, 1)
        m.w8(AI + 0x85, 7)
        m.w8(blue.addr + FLAGS, 0x42); m.w8(blue.addr + COUNTER, 3)
        return 17
    end
    local log = {}
    local sandbox, api = Sight.batching(outer, function()
        return { { blue.addr, Board.UNIT_SIZE, "unit struct" },
                 { red.addr, Board.UNIT_SIZE, "unit struct" } }
    end, log)
    local inside, r0
    local ok, why = pcall(sandbox, function()
        sandbox(function()
            -- the caller's own next call rides in the phase start's list
            r0 = Sight.aiPhaseStart(api, call, S, { blue, red }, { { 0x08039AE8, {} } })
            inside = state()
        end)
    end)
    check(ok, true, "aiPhaseStart: runs: " .. tostring(why))
    check(atCall, table.concat({ Sight.PHASES[3], 0, 1, 0xFF, 0x80000003, 0, 0,
                                 0, 0, 0, 0, 0, 0, 0, 0, 0x77, 0x02, 1, 0 }, ","),
          "aiPhaseStart: the setup runs on AiPhaseInit's values, the faction red")
    check(#ran == 3 and ran[1] == S.UpdateAllPhaseHealingAIStatus
          and ran[2] == S.SetupUnitInventoryAIFlags and ran[3] == 0x08039AE8 and r0, 17,
          "aiPhaseStart: the heal statuses, then the inventory flags, as AiPhaseInit calls "
          .. "them, then the caller's call in the same list -> its r0")
    check(inside, table.concat({ Sight.PHASES[3], 0, 1, 0xFF, 0x80000003, 0, 7,
                                 0, 0, 0, 0, 0, 0, 0, 0, 0x77, 0x42, 3, 1 }, ","),
          "aiPhaseStart: the phase reads what the setup wrote")
    check(state(), stale, "aiPhaseStart: the next read finds the player phase's state again")
    check(#log, 0, "aiPhaseStart: the guard finds no unit struct left changed")

    -- `known`: a later start on the same board writes back what the two calls left (the
    -- best Mov, every unit's aiFlags) and calls neither; the caller's call still runs
    local known, again
    ran = {}
    ok, why = pcall(sandbox, function()
        sandbox(function()
            Sight.aiPhaseStart(api, call, S, { blue, red }, { { 0x08039AE8, {} } })
            known = Sight.phaseStarted(m, S, { blue, red })
        end)
        ran, setsUp = {}, false
        sandbox(function()
            Sight.aiPhaseStart(api, call, S, { blue, red }, { { 0x08039AE8, {} } }, known)
            again = state()
        end)
    end)
    check(ok, true, "aiPhaseStart: a known start runs: " .. tostring(why))
    check(#ran == 1 and ran[1], 0x08039AE8, "aiPhaseStart: a known start calls neither setup function")
    -- as `inside`, but for ai_counter (the blue's stays 1: nothing reads it there)
    check(again, table.concat({ Sight.PHASES[3], 0, 1, 0xFF, 0x80000003, 0, 7,
                                0, 0, 0, 0, 0, 0, 0, 0, 0x77, 0x42, 1, 1 }, ","),
          "aiPhaseStart: a known start leaves the best Mov and the flags the calls did")
    check(state() == stale and #log, 0, "aiPhaseStart: a known start is handed back too")

    -- phaseKey: a kept start is kept by every unit's HP and state word, so a board staged
    -- otherwise (a plan's HP, a unit hidden) finds none; where a unit stands is not in it
    local key = Sight.phaseKey(m, { blue, red })
    check(Sight.phaseKey(m, { [9] = red, [3] = blue }), key, "phaseKey: the units' order is not in it")
    m.w8(blue.addr + 0x10, 7)
    check(Sight.phaseKey(m, { blue, red }), key, "phaseKey: where a unit stands is not in it")
    m.w8(red.addr + 0x13, 12)
    check(Sight.phaseKey(m, { blue, red }) ~= key, true, "phaseKey: an HP staged is another board")
    m.w8(red.addr + 0x13, 0)
    m.w32(blue.addr + 0x0C, Board.US_HIDDEN)
    check(Sight.phaseKey(m, { blue, red }) ~= key, true, "phaseKey: a unit hidden is another board")
    check(Sight.phaseKey(m, { blue }) ~= key, true, "phaseKey: another set of units is another board")
    m.w32(blue.addr + 0x0C, 0)
end

-- decisionCalls: one decision's calls, in cp_decide.c's order. The heal flags are read again
-- first only when an enemy's HP was written since (`stale`), as the game does after every act;
-- no list is longer than the stub holds, and a split decision's setup has room for the phase
-- start's two calls ahead of it.
do
    local S = { RefreshEntityBmMaps = 1, AiUpdateNoMoveFlag = 2, AiInitDangerMap = 3,
                AiClearDecision = 4, AiDecideMain = 5, UpdateAllPhaseHealingAIStatus = 6 }
    local function names(list)
        local out = {}
        for i, c in ipairs(list or {}) do out[i] = c[1] end
        return table.concat(out, ",")
    end
    local one, none = Sight.decisionCalls(S, 0x02030200, false, false)
    check(names(one) .. "|" .. tostring(none), "1,2,3,4,5|nil", "decisionCalls: one list, the setup then the decision")
    check(one[2][2][1], 0x02030200, "decisionCalls: AiUpdateNoMoveFlag is handed the unit")
    local stale = Sight.decisionCalls(S, 0, true, false)
    check(names(stale), "6,1,2,3,4,5", "decisionCalls: a stale heal flag is read again first")
    check(#stale <= Sight.LIST_MAX, true, "decisionCalls: the longest list fits the stub")
    local setup, decide = Sight.decisionCalls(S, 0, false, true)
    check(names(setup) .. "|" .. names(decide), "1,2,3|4,5", "decisionCalls: split, the caller acts between")
    check(#setup + 2 <= Sight.LIST_MAX, true, "decisionCalls: a phase start's two calls fit ahead of a split setup")
    setup, decide = Sight.decisionCalls(S, 0, true, true)
    check(names(setup) .. "|" .. names(decide), "6,1,2,3|4,5", "decisionCalls: split and stale")
end

-- battleWord: a played exchange is kept by its two battle units less where they stand and less
-- aiFlags and ai_counter, which the phase start rewrites and no battle reads; every other
-- byte of their words (the level, ai2, its script counter) and of the unit stays.
do
    check(Sight.battleWord(0x44, 0x5A07FF03), 0x5A00FF03, "battleWord: ai_counter is left out")
    check(Sight.battleWord(0x08, 0x0341630A), 0x0300630A, "battleWord: aiFlags is left out, the "
          .. "level, the exp and the unit's index kept")
    check(Sight.battleWord(0x10, 0x12340A0B), 0x12340000, "battleWord: where the unit stands is left out")
    check(Sight.battleWord(0x40, 0x5A07FF03), 0x5A07FF03, "battleWord: every other word is whole")
    local src = sightSrc
    check(src:find("parts[#parts + 1] = M.battleWord(at, mem.u32(bu + at))", 1, true) ~= nil, true,
          "battleWord: the played exchanges' key is built from it")
end

-- Every simulated enemy phase starts through it (the test above proves only the helper): read
-- off the source, aiOrder starts the phase in the list that builds its order, aiDecide starts
-- one when told to (`starts`: the strike) and otherwise refuses a faction not red, and nothing
-- else calls it. Every aiOrder call hands it the units.
do
    local src = sightSrc
    local _, starts = src:gsub("M%.aiPhaseStart%(api, call, S, all,", "")
    check(starts, 2, "aiPhaseStart: aiOrder and aiDecide are its two callers")
    local function bodyOf(name)
        local at = src:find(name, 1, true)
        return at and src:sub(at, src:find("\n    end\n", at, true)) or ""
    end
    check(bodyOf("local function aiOrder(call, all)")
              :find("local n = M%.aiPhaseStart%(api, call, S, all,%s*{ { S%.BuildAiUnitList, {} } }%)") ~= nil,
          true, "aiPhaseStart: aiOrder builds the order in the phase start's own list")
    local decide = bodyOf("local function aiDecide(call, proc, e, all, before, starts)")
    local started = decide:find("M%.aiPhaseStart%(api, call, S, all, setup, known%)")
    local guard = decide:find("assert%(mem%.u8%(S%.gPlaySt %+ PLAY_FACTION%) == M%.PHASES%[3%]")
    local stale = decide:find("M%.decisionCalls%(S, e%.addr, healStale,")
    check(started ~= nil and guard ~= nil and stale ~= nil and started < guard and guard < stale, true,
          "aiPhaseStart: a decision starts its phase, or is inside a red one and is told "
          .. "whether an enemy's HP was written since the heal flags were read")
    check(decide:find("local key = M%.phaseKey%(mem, all%)%s+local known = seen%.phaseStart%[key%]") ~= nil
          and decide:find("seen%.phaseStart%[key%] = known or M%.phaseStarted%(mem, S, all%)") ~= nil,
          true, "aiPhaseStart: a strike's start is kept by the HPs and states it was read on")
    -- an HP written inside a simulated phase goes through wound(), which marks the heal flags
    -- stale for the deciding side: the staging's two writes come before the phase's order,
    -- and the fourth is a planned heal's (an ally read as wounded, no phase simulated). The
    -- experience count's two writes are to the simulation's battle units, no unit's (M.expOf).
    -- wound()'s callers: a strike's target, the lookahead's striker, the army reply's killer
    local _, all = src:gsub("api%.write8%([^\n,]- %+ UNIT_HP,", "")
    local at = src:find("function M.expOf(", 1, true)
    local count = at and src:sub(at, src:find("\nend\n", at, true)) or ""
    local _, onBattle = count:gsub("api%.write8%([^\n,]- %+ UNIT_HP,", "")
    local writes = all - onBattle
    check(onBattle, 2, "aiPhaseStart: the experience count writes the battle units' HP twice")
    local _, wounds = src:gsub("\n%s+wound%(", "")
    check(writes == 4 and wounds == 3
          and src:find("api%.write8%(addr %+ UNIT_HP, hp%)%s+if decides then healStale = true end") ~= nil,
          true, "aiPhaseStart: a phase's own HP writes are wound()'s, the heal flags stale after")
    check(bodyOf("function s.strike("):find("function%(%) onlyTarget%(u, all%) end,%s*true%)") ~= nil,
          true, "aiPhaseStart: the strike's decision starts its phase")
    -- the definition's own parameter list counts as one
    local calls, withUnits = 0, 0
    for args in src:gmatch("[^%w]aiOrder(%b())") do
        calls = calls + 1
        if args == "(call, all)" or args == "(call, byId)" then withUnits = withUnits + 1 end
    end
    check(calls > 1 and calls == withUnits, true,
          ("aiPhaseStart: each of aiOrder's %d mentions hands it the units (%d do)"):format(calls, withUnits))
end

-- Every enemy decision keeps the AI bytes first (the tests above prove only the helpers): read
-- off the source, aiDecide calls Sight.keepAi before its first write, nothing else does, and
-- every call of aiDecide hands it the board's units. And every map refresh in a sandbox keeps
-- the fog bits: RefreshEntityBmMaps is called from Sight.refresh, from fullInfo (the outermost
-- sandbox, whose load undoes it) and in aiDecide's call list, after its keepFog.
do
    local src = sightSrc
    local _, refreshes = src:gsub("\n[^\n-]*S%.RefreshEntityBmMaps", "")
    check(refreshes, 3, "refresh: RefreshEntityBmMaps is called from refresh, fullInfo and "
          .. "a decision's calls (decisionCalls, aiDecide's) alone")
    for _, name in ipairs({ "function M.refresh(", "function M.fullInfo(",
                            "function M.decisionCalls(" }) do
        local at = src:find(name, 1, true)
        local body = at and src:sub(at, src:find("\nend\n", at, true) or #src)
        check(body ~= nil and body:find("S.RefreshEntityBmMaps", 1, true) ~= nil, true,
              "refresh: " .. name .. " holds one of the three calls")
    end
    local at = src:find("local function aiDecide(call, proc, e, all, before, starts)", 1, true)
    local body = at and src:sub(at, src:find("\n    end\n", at, true))
    local keep = body and body:find("M.keepAi(api, all)", 1, true)
    local write = body and body:find("api.write", 1, true)
    check(keep ~= nil and write ~= nil and keep < write, true,
          "keepAi: aiDecide keeps the AI bytes before its first write")
    local fog = body and body:find("M.keepFog(api, all)", 1, true)
    check(fog ~= nil and fog < write, true,
          "refresh: aiDecide keeps the fog bits before its first write")
    local ride = body and body:find("M.keepRide(api, S, e, all)", 1, true)
    check(ride ~= nil and ride < write, true,
          "keepRide: aiDecide keeps the rider's ballista before its first write")
    local _, keeps = src:gsub("\n +M%.keepAi%(", "")
    -- aiPhaseStart's own keep comes before its call: its test above runs under the guard
    check(keeps, 2, "keepAi: aiDecide and aiPhaseStart are its two callers")
    local calls, withUnits = 0, 0
    for args in src:gmatch("[^%w]aiDecide(%b())") do
        if not args:find("^%(e%)") and not args:find("before, starts%)$") then
            calls = calls + 1
            local units = args:match("^%(call, proc, e, (%w+)[,)]")
            if units == "all" or units == "byId" then withUnits = withUnits + 1 end
        end
    end
    check(calls > 0 and calls == withUnits, true,
          ("keepAi: each of aiDecide's %d calls hands it the units (%d do)"):format(calls, withUnits))
end

-- Every equip in sight.lua goes through Sight.equip: a sandbox read that called
-- EquipUnitItemSlot itself would leak the reordered bag into the next judged plan again
-- (the test above proves only the helper). Read off the source: the strike and the enemy
-- phases' staging each equip through it, both phases stage through that, and the game call
-- appears in Sight.equip alone.
do
    local src = sightSrc
    local _, direct = src:gsub("S%.EquipUnitItemSlot", "")
    check(direct, 1, "equip: EquipUnitItemSlot is called from Sight.equip alone")
    for _, name in ipairs({ "s.enemyPhase", "s.nextPhase" }) do
        local at = src:find("function " .. name .. "(", 1, true)
        local body = at and src:sub(at, (src:find("\n    function ", at + 1) or #src))
        check(body ~= nil and body:find("stagePhase(call, plan)", 1, true) ~= nil, true,
              "equip: " .. name .. " stages through stagePhase")
    end
    for _, name in ipairs({ "s.strike", "stagePhase" }) do
        local at = src:find("function " .. name .. "(", 1, true)
        local body = at and src:sub(at, (src:find("\n    function ", at + 1) or #src))
        check(body ~= nil and body:find("M.equip(api, call, S, ", 1, true) ~= nil, true,
              "equip: " .. name .. " equips through Sight.equip")
    end
end

-- Sight.knows (ADR 0399): a red unit is remembered by slot and character (Board.memoryKey); a
-- slot another character holds now is not; no memory, none. And every read the fog alone would
-- hide a unit from asks it: both judged phases' decides, the danger maps (the remembered tile
-- lifted out of the fog), and keySources.
do
    local keys = { [Board.memoryKey(0x81, 0x80, 0x0A)] = true }
    check(Sight.knows(Board, keys, { id = 0x81, charId = 0x80, classId = 0x0A }), true,
          "knows: slot, character and class")
    check(Sight.knows(Board, keys, { id = 0x81, charId = 0x51, classId = 0x0A }), false,
          "knows: another character in the slot")
    check(Sight.knows(Board, keys, { id = 0x81, charId = 0x80, classId = 0x0B }), false,
          "knows: another generic soldier (one character id, another class) in the slot")
    check(Sight.knows(Board, nil, { id = 0x81, charId = 0x80, classId = 0x0A }), false, "knows: no memory")
    -- the emulator hands sight Board.bind's table, not board.lua itself (harness api.Board)
    local bound = Board.bind({}, {})
    check(Sight.knows(bound, keys, { id = 0x81, charId = 0x80, classId = 0x0A }), true,
          "knows: the bound Board keys it too")
    -- playsAsSeen: in sight always; in fog only when remembered
    local FOG = Board.US_BIT9
    check(Sight.playsAsSeen(bound, 0, false), true, "playsAsSeen: in sight")
    check(Sight.playsAsSeen(bound, FOG | 1, false), false, "playsAsSeen: in fog, not remembered")
    check(Sight.playsAsSeen(bound, FOG, true), true, "playsAsSeen: in fog, remembered")
    -- and the emulator-bound reads that the fog alone would hide a unit from all ask it (the
    -- sandboxed game calls cannot run here; the campaign rerun is their proof, ADR 0399)
    local src = sightSrc
    local _, asks = src:gsub("M%.playsAsSeen%(Board, [^\n]-, s%.knows%(e%)%)", "")
    check(asks, 3, "playsAsSeen: decides, closings' looters and keySources ask it")
    local _, lifts = src:gsub("liftRemembered%(%)\n%s+call%(S%.GenerateDangerZoneRange", "")
    check(lifts, 3, "knows: danger, threat and the army's reply lift the remembered out of the fog")
    local _, fogTests = src:gsub("& Board%.US_BIT9%)", "")
    check(fogTests, 1, "the fog bit is read in playsAsSeen alone")
end

-- The call-list stub's last word is a hand-encoded Thumb `b loop`: decoded, it must land on the
-- return loop, wherever LIST_STUB_AT puts the stub (the fake CPU never runs the stub, so the
-- call is let fail and the words it wrote are read).
do
    local cpu, seen = fakeCpu(1)
    pcall(Sight.machine(cpu), function(call) return call({ { 0x08001000, { 1, 2 } } }) end)
    local _, ram = seen()
    local loop = Sight.top(0x03007D00) + Sight.LOOP_AT
    local stub = loop + Sight.LIST_STUB_AT
    check(ram[stub], Sight.LIST_STUB[1], "list: the stub was written at LIST_STUB_AT")
    local at = stub + (#Sight.LIST_STUB - 2) * 2   -- the `b loop`, before the `bx r5` veneer
    local h = ram[at]
    check(h & 0xF800, 0xE000, "list: the stub's last word is a Thumb B")
    local imm = h & 0x7FF
    if imm >= 0x400 then imm = imm - 0x800 end
    check(at + 4 + imm * 2, loop, "list: the stub branches back to the loop")
end

-- keptRead: a read made with no sandbox open is kept and answers every later ask; one made
-- inside a sandbox is returned but never kept (it may see the sandbox's own writes).
do
    local reads, isOpen = 0, false
    local function read() reads = reads + 1; return "board" .. reads end
    local function open() return isOpen end
    local cache = {}
    isOpen = true
    check(Sight.keptRead(cache, "units", read, open), "board1", "keptRead: inside a sandbox, read")
    check(cache.units, nil, "keptRead: and not kept")
    isOpen = false
    check(Sight.keptRead(cache, "units", read, open), "board2", "keptRead: outside, a fresh read")
    isOpen = true
    check(Sight.keptRead(cache, "units", read, open), "board2", "keptRead: kept, even inside one")
    check(reads, 2, "keptRead: no third read")
end

-- withBreaks: a breakpoint that cannot be set still clears the ones set before it, and raises.
do
    local set, cleared = {}, {}
    local cpu = {
        breakpoint = function(addr)
            if #set == 1 then error("no debugger") end
            set[#set + 1] = addr
            return #set
        end,
        unbreak = function(id) cleared[#cleared + 1] = id end,
    }
    local ok = pcall(Sight.withBreaks, cpu, { { 0x10, print }, { 0x20, print } }, function() end)
    check(ok, false, "withBreaks: a breakpoint that fails raises")
    check(#cleared == 1 and cleared[1] == 1, true, "withBreaks: and the one set first is cleared")
end

-- A KEPT call (PR E): what it wrote stays, the registers come back as they were, pc through a
-- write that lands one instruction ahead (mGBA's pipeline refill, measured).
do
    local cpu, seen = fakeCpu(2)
    refills(cpu)
    local before = {}
    for _, r in ipairs({ "r0", "r4", "sp", "lr", "pc", "cpsr" }) do before[r] = cpu.read(r) end
    local got = Sight.machine(cpu, true)(function(call)
        local _, ram = seen(); ram.marker = "kept"
        return call(0x08001001, { 2, 40 })
    end)
    check(got, 42, "a kept call returns the function's r0")
    local loads, ram = seen()
    check(loads, 0, "a kept call loads no state")
    check(ram.marker, "kept", "and what it wrote stays")
    check(ram[Sight.REG_IE], nil, "a kept call leaves REG_IE alone")
    for r, v in pairs(before) do check(cpu.read(r), v, "register " .. r .. " is put back") end
end

-- A kept call waits for the CPU to rest between frames (#620): a frame that ended inside the
-- game's VBlank work (pc 0x2E8) is run on until pc reads the BIOS's halt, and the registers
-- put back are the resting ones; a CPU that never rests fails loudly.
do
    local cpu, seen = fakeCpu(2)
    cpu.write("pc", 0x2E8)
    local frames, waited = cpu.frames, 0
    function cpu.live(done, max)
        if cpu.read("pc") == 0x2E8 then
            for _ = 1, max do
                waited = waited + 1
                if waited == 3 then cpu.write("pc", Sight.REST_PC) end
                if done() then return true end
            end
            return false
        end
        return frames(done, max)
    end
    refills(cpu, { [0x2E8] = true, [Sight.REST_PC] = true })
    local got = Sight.machine(cpu, true)(function(call) return call(0x08001001, { 2, 40 }) end)
    check(got, 42, "rest: the kept call runs once the CPU rests")
    check(waited, 3, "rest: after the frames it took to rest")
    check(cpu.read("pc"), Sight.REST_PC, "rest: and the game resumes from its rest, not mid-frame")
    local busy = fakeCpu(2)
    busy.write("pc", 0x2E8)
    local ok, err = pcall(Sight.machine(busy, true), function(call) return call(0x08001001, { 1, 1 }) end)
    check(ok, false, "rest: a CPU that never rests stops the kept call")
    check(tostring(err):find("never rested", 1, true) ~= nil, true, "rest: and says why")
    -- a kept call's frames are real ones (cpu.live), never the sight's counted cpu.frames
    local real = fakeCpu(2)
    refills(real)
    local sightFrames = real.frames
    real.live = function(done, max) return sightFrames(done, max) end
    real.frames = function() error("a kept call stepped the sight's frames") end
    check(Sight.machine(real, true)(function(call) return call(0x08001001, { 1, 2 }) end), 3,
          "rest: a kept call runs on real frames")
    -- a sandboxed call loads its state back: it needs no rest
    local sandboxed = fakeCpu(2)
    sandboxed.write("pc", 0x2E8)
    check(Sight.machine(sandboxed)(function(call) return call(0x08001001, { 2, 3 }) end), 5,
          "rest: a sandboxed call runs where the frame ended")
end

do
    local cpu, seen = fakeCpu(3)
    local loop
    select(2, seen())[Sight.REG_IE] = 0x2001
    local got = Sight.machine(cpu)(function(call)
        local _, ram = seen(); ram.marker = "dirty"
        local r = call(0x08001001, { 2, 40 })
        loop = cpu.read("lr") & ~1
        return r
    end)
    check(got, 42, "a sandboxed call returns the function's r0")
    local loads, ram = seen()
    local top = Sight.top(0x03007D00)
    check(loop, top + Sight.LOOP_AT, "lr names the loop's place above the call's stack")
    for i, h in ipairs(Sight.HALT_LOOP) do
        check(ram[loop + (i - 1) * 2], h, "the halt loop's word " .. i .. " is written")
    end
    check(ram[loop + Sight.HALT_MARKER], top + Sight.MARKER_AT,
          "its first literal is the marker's address")
    check(ram[loop + Sight.HALT_IE], Sight.REG_IE, "its second is REG_IE, which the loop clears")
    check(ram[Sight.REG_IE], 0x2001, "the call starts with the game's IE written back")
    check(loop > cpu.read("sp"), false, "the loop sits above the call's stack, under the caller's")
    check(loads, 1, "the state is loaded back once")
    check(ram.marker, nil, "what the call wrote is gone after the sandbox")
    check(cpu.read("pc"), 0x1F8, "the CPU is back where the frame left it")
end

do
    -- Returned into the halt: the CPU sits in the BIOS's Halt, outside the loop, and the loop's
    -- str has set the marker. The call is seen as returned through the marker alone.
    local cpu = fakeCpu(2)
    local frames = cpu.frames
    function cpu.frames(done, max)
        local loop
        return frames(function()
            local pc = cpu.read("pc")
            if pc ~= 0x08001000 and pc < 0x08000000 and pc > 0x03000000 then
                loop = pc - 4
                local marker = cpu.read32(loop + Sight.HALT_MARKER)
                cpu.write32(marker, marker)
                cpu.write("pc", 0x0000016C)
            end
            return done()
        end, max)
    end
    local got = Sight.machine(cpu)(function(call) return call(0x08001001, { 2, 40 }) end)
    check(got, 42, "a call halted in the BIOS is seen as returned through its marker")
end

do
    local cpu, seen = fakeCpu(1)
    local ok, err = pcall(Sight.machine(cpu), function(call) return call(0x08002000, {}) end)
    check(ok, false, "a call that never returns raises")
    check(tostring(err):find("did not return", 1, true) ~= nil, true, "naming the call")
    check((seen()), 1, "and the state is still loaded back")
end

do
    -- A raise anywhere after the save -- the mode switch included -- still loads the state back.
    local cpu, seen = fakeCpu(1)
    local read = cpu.read
    cpu.read = function(r) if r == "sp" then error("banked sp unreadable") end return read(r) end
    local ok = pcall(Sight.machine(cpu), function(call) return call(0x08001000, {}) end)
    check(ok, false, "a raise in the mode switch is raised")
    check((seen()), 1, "and the state is still loaded back")
end

do
    -- The fifth argument rides the stack, as the ARM calling convention puts it.
    local cpu = fakeCpu(1)
    local wrote, write32 = {}, cpu.write32
    cpu.write32 = function(a, v) wrote[#wrote + 1] = { a, v }; write32(a, v) end
    Sight.machine(cpu)(function(call) return call(0x08001000, { 1, 2, 3, 4, -1 }) end)
    local top, stack = Sight.top(0x03007D00), {}
    for _, w in ipairs(wrote) do
        if w[1] >= top and w[1] < top + Sight.SCRATCH_AT then stack[#stack + 1] = w end
    end
    check(#stack, 1, "one stack argument written")
    check(stack[1][1], top, "at the call's sp")
    check(stack[1][2], 0xFFFFFFFF, "BU_ISLOT_AUTO (-1) as a 32-bit word")
end

-- attackOf / strikeOf: our attack (with the enemy's counter) and the enemy's own strike are
-- separate reads; what each does is its played distributions.
local hitter = { hit = 80, crit = 5, dmg = 6, hits = 2, armed = true }
do
    -- 70%: the target (5 HP) dies, or lives to counter for 6 or a critical 18
    local f = Sight.attackOf({ hit = 70, crit = 0, dmg = 5, hits = 1, armed = true,
                               counter = hitter, killsTarget = true,
                               dealt = { [5] = 0.7, [0] = 0.3 },
                               back = { [0] = 0.75, [6] = 0.2, [18] = 0.05 } }, 5, 20)
    check(f.counters, true, "armed: the enemy counters")
    check(f.counterDmg, 6, "the counter's damage, as the window shows it")
    check(f.counterHits, 2, "with its blows")
    check(f.counterCrit, 5, "and its crit")
    check(f.killsTarget, true, "the game's own simulation kills it")
    check(f.kill, 0.7, "kill: the outcomes that take its 5 HP")
    check(f.sure, false, "not sure: it can miss")
    check(f.expected, 3.5, "expected: the mean damage dealt")
    check(f.counterWorst, 18, "counterWorst: a critical counter")
    check(f.die, 0, "die: nothing takes our 20")
end

do
    local f = Sight.attackOf({ hit = 70, crit = 0, dmg = 5, hits = 1, armed = true,
                               counter = { hit = 0, crit = 0, dmg = 0, hits = 0,
                                           armed = false }, killsTarget = false,
                               dealt = { [5] = 1 }, back = { [0] = 1 } }, 9, 20)
    check(f.counters, false, "an unarmed answer is no counter")
    check(f.counterDmg, 0, "so no counter damage")
    check(f.killsTarget, false, "5 does not kill 9")
    check(f.counterWorst, 0, "and nothing comes back")
    check(f.sure, false, "a sure 5 on 9 is no sure kill")
    local a = Sight.attackOf({ hit = 100, crit = 0, dmg = 9, hits = 1, armed = true,
                               counter = hitter, killsTarget = true, dealt = { [9] = 1 },
                               back = { [0] = 1 } }, 9, 20)
    check(a.sure, true, "every outcome takes 9 of 9: a sure kill")
    check(Sight.answerOf(a, 20), true, "a sure kill that takes nothing back answers")
end

do
    local t = Sight.strikeOf({ hit = 60, crit = 0, dmg = 9, hits = 1, armed = true, slot = 1,
                               tile = { x = 4, y = 4 }, dealt = { [0] = 0.4, [9] = 0.6 },
                               back = { [0] = 1 } })
    check(t.takenDmg, 9, "the AI's strike")
    check(t.takenWorst, 9, "the most it takes")
    check(t.takenDist[9], 0.6, "as the game plays it")
    check(t.takenSlot, 1, "with the slot it chose")
    check(t.takenTile.x .. "," .. t.takenTile.y, "4,4", "and the tile")
    local none = Sight.strikeOf(nil)
    check(none.takenHit, 0, "an enemy whose AI does not strike us strikes nothing")
    check(none.takenWorst, 0, "and takes nothing")
    check(none.takenSlot, nil, "and chose no slot")
end

-- turnsLeft: the goal window's last turn is End - 1 (player_interface.c), so End - turn are left.
check(Sight.turnsLeft(11, 1), 10, "turn 1 of a map whose goal window says 10 turns")
check(Sight.turnsLeft(11, 10), 1, "the last turn: one left")

-- firstNewEvent: a script available now (a repeating event) is no change.
do
    local now = { [0xA] = true }
    check(Sight.firstNewEvent(now, { { turn = 4, scripts = { [0xA] = true } },
                                     { turn = 5, scripts = { [0xA] = true, [0xB] = true } } }), 5,
        "the first turn offering a new script")
    check(Sight.firstNewEvent(now, { { turn = 4, scripts = { [0xA] = true } } }), nil,
        "only the repeating event ahead: no change")
end

-- side: the forecast window's numbers, read off the battle units and the proc.
do
    local bytes = {}
    local mem = {
        u16 = function(a) return bytes[a] or 0 end,
        s8 = function(a) local v = bytes[a] or 0; return v >= 0x80 and v - 0x100 or v end,
    }
    local A, T, P = 0x100, 0x200, 0x300
    bytes[A + 0x48] = 0x01
    bytes[A + 0x5A], bytes[T + 0x5C] = 12, 4
    bytes[A + 0x64], bytes[A + 0x6A] = 70, 3
    bytes[P + 0x50] = 2
    local side = Sight.side(mem, A, T, P, 0x50)
    check(string.format("%d/%d/%d/%d/%s", side.hit, side.dmg, side.crit, side.hits,
        tostring(side.armed)), "70/8/3/2/true", "side: the window's hit, damage, crit, blows")
end

-- eventOrder: the check runs at a player phase's start, so this turn's green and red phases are
-- still ahead, before every phase of the turns after it.
do
    local o = Sight.eventOrder(4)
    check(o[1].turn .. ":" .. o[1].phase, "4:64", "first: this turn's green phase")
    check(o[2].turn .. ":" .. o[2].phase, "4:128", "then this turn's red phase")
    check(o[3].turn .. ":" .. o[3].phase, "5:0", "then the next turn's player phase")
    check(o[#o].turn, Sight.LAST_EVENT_TURN, "out to the last turn an event can name")
end

-- The sandbox puts the CPU in System mode BEFORE it reads sp: sp is banked.
do
    local cpu = fakeCpu(1)
    local order = {}
    local read, write = cpu.read, cpu.write
    cpu.read = function(r) order[#order + 1] = "r:" .. r; return read(r) end
    cpu.write = function(r, v) order[#order + 1] = "w:" .. r; return write(r, v) end
    Sight.machine(cpu)(function(call) return call(0x08001000, { 1, 2 }) end)
    local cpsrAt, spAt
    for i, o in ipairs(order) do
        if o == "w:cpsr" and not cpsrAt then cpsrAt = i end
        if o == "r:sp" and cpsrAt and i > cpsrAt and not spAt then spAt = i end
    end
    check(cpsrAt ~= nil and spAt ~= nil, true, "sp is read after cpsr is switched")
end

-- The scratch the forecast proc and EventInfo share fits below the return loop.
check(Sight.SCRATCH_SIZE <= 0x70, true, "scratch ends before the loop at +0x80 (scratch at +0x10)")

-- answerOf: the game's simulation kills AND no outcome's counter kills us; strength = expected.
do
    local a = { killsTarget = true, counterWorst = 10, expected = 9.6 }
    local ok, strength = Sight.answerOf(a, 11)
    check(ok, true, "answerOf: kills, and the worst counter (10) < 11 HP")
    check(strength, 9.6, "answerOf: strength = the expected damage")
    check((Sight.answerOf(a, 10)), false, "answerOf: a counter that can kill is no answer")
    a.killsTarget = false
    check((Sight.answerOf(a, 99)), false, "answerOf: no kill this round is no answer")
end

-- demandsOf: one per red class (need = its count, rep = the first), villages each, chests and
-- doors once, fog only with fog, sustain always; blue and off-field units ask nothing.
do
    local units = {
        { faction = "red", onField = true, classId = 9, id = 0x81 },
        { faction = "red", onField = true, classId = 7, id = 0x82 },
        { faction = "red", onField = true, classId = 9, id = 0x83 },
        { faction = "red", onField = false, classId = 5, id = 0x84 },
        { faction = "blue", onField = true, classId = 9, id = 0x01 },
    }
    local cmds = { { x = 1, y = 2, cmd = Sight.TILE_COMMAND_CHEST },
                   { x = 3, y = 4, cmd = Sight.TILE_COMMAND_CHEST },
                   { x = 5, y = 6, cmd = Sight.TILE_COMMAND_VISIT },
                   { x = 7, y = 8, cmd = Sight.TILE_COMMAND_SEIZE } }
    local ids = {}
    local d = Sight.demandsOf(units, cmds, 0)
    for _, x in ipairs(d) do ids[#ids + 1] = x.id .. "/" .. x.need end
    check(table.concat(ids, " "), "enemy:9/2 enemy:7/1 chests/1 village:5,6/1 sustain/1",
        "demandsOf: classes, chests once, the village, sustain; no fog, no Seize demand")
    check(d[1].rep.id, 0x81, "demandsOf: the class's first unit stands for it")
    d = Sight.demandsOf({}, { { x = 0, y = 0, cmd = Sight.TILE_COMMAND_DOOR } }, 3)
    ids = {}
    for _, x in ipairs(d) do ids[#ids + 1] = x.id end
    check(table.concat(ids, " "), "doors fog sustain", "demandsOf: doors, fog when the range is set")
end

-- loots: an AI script loots when it holds AI_CMD_PILLAGE (0x10) before its first GOTO
-- (cp_script.h; the scripts loop back with a GOTO, so a scan past it reads the next script).
do
    local ram = {}
    local mem = { u32 = function(a) return ram[a] or 0 end, u8 = function(a) return ram[a] or 0 end }
    -- gpAi1Table at 0x100 holds the table's address 0x200; ai1 0 -> script 0x300, ai1 1 -> 0x400
    ram[0x100], ram[0x200], ram[0x204] = 0x200, 0x300, 0x400
    ram[0x300], ram[0x310], ram[0x320] = 0x05, 0x10, 0x03           -- action, PILLAGE, GOTO
    ram[0x400], ram[0x410], ram[0x420] = 0x05, 0x03, 0x10           -- action, GOTO, (another's)
    check(Sight.loots(mem, 0x100, 0), true, "loots: PILLAGE before the GOTO")
    check(Sight.loots(mem, 0x100, 1), false, "loots: nothing past the script's GOTO counts")
end

-- opensChests: AiGetChestUnlockItemSlot's rule -- a Chest Key, or a Lockpick on a CA_STEAL
-- class, and never with a full bag.
do
    check(Sight.opensChests({ { id = 0x69 } }, 0, Board.ITEM_COUNT), true, "opensChests: a Chest Key")
    check(Sight.opensChests({ { id = 0x6B } }, 0, Board.ITEM_COUNT), false, "opensChests: a Lockpick, no CA_STEAL")
    check(Sight.opensChests({ { id = 0x6B } }, 4, Board.ITEM_COUNT), true, "opensChests: a Lockpick on a thief")
    check(Sight.opensChests({ { id = 1 }, { id = 2 }, { id = 3 }, { id = 4 }, { id = 0x69 } }, 0, Board.ITEM_COUNT),
        false, "opensChests: a full bag takes no loot")
end

-- waveCloses: a wave loaded on turn T first moves that turn's enemy phase; from turn `now` the
-- enemy phases are numbered 1, 2, ... so it closes at (T - now) + its turns.
do
    check(Sight.waveCloses(8, 4, 2), 6, "waveCloses: turn 8, two moves, seen from turn 4")
    check(Sight.waveCloses(8, 4, nil), nil, "waveCloses: a tile it never reaches")
end

-- closingsKey: a looter killed, moved or hurt, a tile taken, or other waves is a new read; the
-- same board is the same key whatever order the units come in.
do
    local open = { ["1,2"] = {}, ["5,6"] = {} }
    local a, b = { id = 0x81, x = 3, y = 3, hp = 20 }, { id = 0x82, x = 9, y = 9, hp = 20 }
    local key = Sight.closingsKey(3, 8, nil, { a, b }, open)
    check(Sight.closingsKey(3, 8, nil, { b, a }, open), key, "closingsKey: order-free")
    check(Sight.closingsKey(3, 8, nil, { a }, open) ~= key, true, "closingsKey: a looter gone")
    check(Sight.closingsKey(3, 8, nil, { a, { id = 0x82, x = 8, y = 9, hp = 20 } }, open) ~= key,
        true, "closingsKey: a looter moved")
    check(Sight.closingsKey(3, 8, nil, { a, b }, { ["1,2"] = {} }) ~= key, true,
        "closingsKey: a tile taken")
    local wave = { { turn = 8, units = { { class = 9, x = 13, y = 0 } } } }
    check(Sight.closingsKey(3, 8, wave, { a, b }, open) ~= key, true, "closingsKey: the waves")
    check(Sight.closingsKey(3, 8, { { turn = 8, units = { { class = 9, x = 14, y = 1 } } } },
        { a, b }, open) ~= Sight.closingsKey(3, 8, wave, { a, b }, open), true,
        "closingsKey: a wave's units, not only how many waves")
    check(Sight.closingsKey(3, 8, nil, { a, b }, open, { { x = 4, y = 4 } }) ~= key, true,
        "closingsKey: one of ours blocking")
end

-- sackedTerrain: a taken chest is emptied, a taken village closed; neither is on the AI's loot
-- lists (cp_utility.c: VILLAGE_REGULAR 0x03, CHURCH, RUINS_VILLAGE 0x37, CHEST_FULL 0x21).
do
    check(Sight.sackedTerrain({ kind = "chest" }), 0x20, "sackedTerrain: an emptied chest")
    check(Sight.sackedTerrain({ kind = "visit" }), 0x04, "sackedTerrain: a closed village")
end

-- test_full_info_reveals_inside_one_call_only (T071, R-7): Sight.fullInfo runs `fn` with fog
-- off -- the vision byte written 0 through the journaled api, then the game's own
-- RefreshEntityBmMaps, which clears a seen unit's US_BIT9 (bmmap.c RefreshUnitsOnBmMap) --
-- and hands it the board read there. Its writes are the vision byte alone, so no RNG seed and
-- no arrival is touched (an arrival is a unit not loaded yet: no write loads it); the game's
-- own writes are undone by the outermost load; the sight's caches are swapped for the call and
-- put back; and it refuses to run inside an open sandbox, whose load would come too late.
do
    local cpu = fakeCpu(1)
    local VISION, UNIT, SEED, ARRIVAL = 0x300 + 0x0D, 0x400, 0x500, 0x600
    local bytes = { [VISION] = 3, [UNIT] = Board.US_BIT9, [SEED] = 0x1234, [ARRIVAL] = 0 }
    -- the emulator's state round trip: RAM is saved and loaded with the registers
    local save0, load0 = cpu.save, cpu.load
    function cpu.save()
        local st, ram = save0(), {}
        for k, v in pairs(bytes) do ram[k] = v end
        st.ram = ram
        return st
    end
    function cpu.load(st)
        load0(st)
        for k in pairs(bytes) do bytes[k] = nil end
        for k, v in pairs(st.ram) do bytes[k] = v end
    end
    -- the game's RefreshEntityBmMaps: with no fog, the unit's US_BIT9 cleared (a game write)
    local frames0, refreshes = cpu.frames, 0
    function cpu.frames(done, max)
        if cpu.read("pc") == 0x08001000 then
            refreshes = refreshes + 1
            if bytes[VISION] == 0 then bytes[UNIT] = bytes[UNIT] & ~Board.US_BIT9 end
        end
        return frames0(done, max)
    end
    local writes = {}
    local function writer(a, v) writes[#writes + 1] = a; bytes[a] = v end
    local function byte(a) return bytes[a] or 0 end
    local mem = { u8 = byte, u16 = byte, u32 = byte }
    local outer = { cpu = cpu, mem = mem, write8 = writer, write16 = writer, write32 = writer,
                    board = function()
                        local fogged = (bytes[UNIT] & Board.US_BIT9) ~= 0
                        return { units = { { id = 0x81, fogged = fogged } } }
                    end }
    local sandbox, api, open = Sight.batching(outer)
    local S = { gPlaySt = 0x300, RefreshEntityBmMaps = 0x08001000 }
    local caches = { "fogged answers" }
    local function isolate()
        local kept = caches[1]
        caches[1] = "fresh"
        return function() caches[1] = kept end
    end
    local inside = {}
    local got = Sight.fullInfo(sandbox, open, api, S, isolate, function(board)
        inside.fogged = board.units[1].fogged
        inside.vision, inside.seed, inside.arrival = bytes[VISION], bytes[SEED], bytes[ARRIVAL]
        inside.cache = caches[1]
        inside.writes = #writes
        return "plan"
    end)
    check(got, "plan", "fullInfo: fn's result comes back")
    check(inside.fogged, false, "fullInfo: the hidden unit is seen inside the call")
    check(inside.vision, 0, "fullInfo: fog off inside")
    check(refreshes, 1, "fullInfo: the game's RefreshEntityBmMaps rebuilt the maps once")
    check(inside.writes, 1, "fullInfo: its one write is the vision byte")
    check(writes[1], VISION, "fullInfo: ...at gPlaySt + 0x0D")
    check(inside.seed .. "/" .. inside.arrival, 0x1234 .. "/0", "fullInfo: no RNG seed, no arrival")
    check(inside.cache, "fresh", "fullInfo: the sight's caches swapped for the call")
    check(caches[1], "fogged answers", "fullInfo: and put back after it")
    check(bytes[VISION], 3, "fullInfo: the vision range restored")
    check((bytes[UNIT] & Board.US_BIT9) ~= 0, true, "fullInfo: the game's own write undone")
    check(outer.board().units[1].fogged, true,
          "fullInfo: outside the call, the unit is hidden again")
    -- an error inside still puts the caches back
    local ok = pcall(Sight.fullInfo, sandbox, open, api, S, isolate, function() error("boom") end)
    check(ok, false, "fullInfo: fn's error is raised")
    check(caches[1] .. "/" .. bytes[VISION], "fogged answers/3",
          "fullInfo: restored after an error")
    -- inside an open sandbox the game's writes would outlive the call: refused
    local refused = sandbox(function()
        return not pcall(Sight.fullInfo, sandbox, open, api, S, isolate, function() end)
    end)
    check(refused, true, "fullInfo: refused inside an open sandbox")
end

-- canExplore's memo is keyed on the tile's terrain: a chest another side opened (full ->
-- empty) is asked again, never answered from the kept yes
check(Sight.exploreKey("chest", 6, 3, Sight.TERRAIN_CHEST_FULL)
      ~= Sight.exploreKey("chest", 6, 3, Sight.TERRAIN_CHEST_EMPTY), true,
      "an opened chest is a new canExplore question")
check(Sight.exploreKey("chest", 6, 3, 0x21), Sight.exploreKey("chest", 6, 3, 0x21),
      "the same tile and terrain is the same question")

-- NextRN is rng.c's, word for word: the draws below were worked by hand from rng.c for the
-- state InitRN(0) writes (initTable[0..2], no extra draws since 0 % 23 == 0). The first:
-- (0x924E << 11) + (0xA36E >> 5) = 0x751B in 16 bits, s2 = 0xB784 * 2 + 1 (s1's top bit) =
-- 0x6F09, and 0x751B ^ 0x6F09 = 0x1A12.
do
    local w = { 0xA36E, 0x924E, 0xB784 }
    local got = {}
    for i = 1, 4 do got[i] = string.format("%04X", Sight.nextRN(w)) end
    check(table.concat(got, " "), "1A12 544D D47E 5A87", "NextRN: rng.c's first four draws")
    check(string.format("%04X %04X %04X", w[1], w[2], w[3]), "5A87 D47E 544D",
          "NextRN: the state shifts one word")
end

-- advance(api, n) = n single steps written back; 0 draws write nothing
do
    local mem = { [0x100] = 0xA36E, [0x102] = 0x924E, [0x104] = 0xB784 }
    local writes = 0
    local api = { SYM = { gRNSeeds = 0x100 },
                  mem = { u16 = function(a) return mem[a] end },
                  write16 = function(a, v) writes = writes + 1; mem[a] = v end }
    check(table.concat(Sight.dice(api), ","), "41838,37454,46980", "dice reads the three words")
    Sight.advance(api, 0)
    check(writes, 0, "advance(0) writes nothing")
    check(mem[0x100], 0xA36E, "advance(0) leaves the state")
    Sight.advance(api, 3)
    check(string.format("%04X %04X %04X", mem[0x100], mem[0x102], mem[0x104]), "D47E 544D 1A12",
          "advance(3) is three single steps")
    Sight.advance(api, 1)
    check(string.format("%04X", mem[0x100]), "5A87", "advance(1) after advance(3) is the fourth draw")
end

-- Sight.phaseWays (ADR 0411): a striker the counter may kill splits the phase, the second way
-- with its tile freed, only while the rarer side is at least the floor of the whole phase.
-- Split at every such striker, a phase of 20 of them is 2^20 ways: vanilla Ch15 (Eirika)'s
-- first decision never came back from such a phase.
do
    local function sandbox(fn) return fn() end
    -- n strikers, each felled with chance q(k); `asked` counts the decisions played
    local function phase(n, q, floor, mass0)
        local asked, freed = 0, {}
        local outcomes, averaged = Sight.phaseWays(n, function(k, done)
            asked = asked + 1
            local now = {}
            for i, t in ipairs(done) do now[i] = t end
            local t = { enemy = k, felled = q(k) }
            now[#now + 1] = t
            return t, now, function() freed[#freed + 1] = k end
        end, sandbox, floor, mass0)
        return outcomes, averaged, asked, freed
    end
    local function total(outcomes)
        local p = 0
        for _, o in ipairs(outcomes) do p = p + o.p end
        return math.floor(p * 1e9 + 0.5) / 1e9
    end
    -- two uncertain strikers: both ways of each, as before
    local out, averaged, asked = phase(2, function() return 0.5 end)
    check(#out, 4, "ways: two even counter kills are four ways")
    check(averaged, 0, "ways: none left unsplit")
    check(asked, 3, "ways: the second striker decides once a way of the first")
    check(total(out), 1, "ways: their chances sum to 1")
    -- twenty of them: bounded by the floor, every way still at least that likely
    out, averaged, asked = phase(20, function() return 0.5 end)
    check(#out <= 1 / Sight.SPLIT_FLOOR, true,
          "ways: 20 even counter kills stay within 1 / floor ways (" .. #out .. ")")
    check(asked <= 20 / Sight.SPLIT_FLOOR, true,
          "ways: and within that many decisions a striker (" .. asked .. ")")
    check(averaged > 0, true, "ways: the kills left unsplit are counted")
    check(total(out), 1, "ways: the bounded phase's chances still sum to 1")
    local least = 1
    for _, o in ipairs(out) do least = math.min(least, o.p) end
    check(least >= Sight.SPLIT_FLOOR, true, "ways: no way played is rarer than the floor")
    -- a sure kill is no split: one way, the tile freed, nothing to count
    local freed
    out, averaged, asked, freed = phase(3, function() return 1 end)
    check(#out, 1, "ways: a sure counter kill is one way")
    check(#freed, 3, "ways: each sure kill frees its tile")
    check(averaged, 0, "ways: a sure kill is not an uncertain one left unsplit")
    -- below the floor the phase goes the likelier way: the striker stands on a rare kill,
    -- is gone on a likely one
    out, averaged, asked, freed = phase(1, function() return 0.004 end)
    check(#out .. "/" .. #freed .. "/" .. averaged, "1/0/1", "ways: a rare kill keeps the striker")
    out, averaged, asked, freed = phase(1, function() return 0.996 end)
    check(#out .. "/" .. #freed .. "/" .. averaged, "1/1/1", "ways: a near-sure kill frees the tile")
    -- the floor is of the whole judged plan (ADR 0415): a phase that is one way of the plan's
    -- uncertain kills (mass0) splits only while the rarer side is that floor of the PLAN
    out, averaged = phase(1, function() return 0.1 end)
    check(#out .. "/" .. averaged, "2/0", "ways: a 10% kill splits a phase that is the whole plan")
    out, averaged = phase(1, function() return 0.1 end, nil, 0.1)
    check(#out .. "/" .. averaged, "1/1", "ways: and stays unsplit in a way a tenth of the plan")
    -- an enemy that does not strike splits nothing
    out = Sight.phaseWays(3, function() return nil end, sandbox)
    check(#out == 1 and #out[1].strikes == 0, true, "ways: no strike, one way")
end

-- Sight.watched: the watch is asked before every game call's frames, and what it raises ends
-- the call before it runs (botrun's decision budget, ADR 0411); set(nil) asks no more.
do
    local ran, asked = 0, 0
    local cpu, set = Sight.watched({ frames = function() ran = ran + 1; return true end,
                                     read = function() return 7 end })
    check(cpu.frames(), true, "watched: no watch, the call runs")
    check(cpu.read(), 7, "watched: the rest of the cpu is the cpu's")
    set(function() asked = asked + 1; if asked > 1 then error({ timeout = true }, 0) end end)
    cpu.frames()
    local ok, err = pcall(cpu.frames)
    check(ok, false, "watched: the watch's error ends the call")
    check(type(err) == "table" and err.timeout, true, "watched: its error value comes through")
    check(ran, 2, "watched: the refused call ran no frame")
    set(nil)
    check(cpu.frames(), true, "watched: unset, the call runs again")
end

-- M.expOf (ADR 0414): the game's GetBattleUnitExpGain called three times on the simulation's
-- battle units, the actor alive, each call after nonZeroDamage (+7C) and the target's curHP
-- (+13) are set to its case: none (0, alive), hit (1, alive), kill (1, 0 HP).
do
    local S = { gBattleActor = 0x0203A4EC, gBattleTarget = 0x0203A56C,
                GetBattleUnitExpGain = 0x0802B900 }
    local mem = {}
    local api = { write8 = function(a, v) mem[a] = v end }
    local seen = {}
    local function call(addr, args)
        check(addr, S.GetBattleUnitExpGain, "expOf: calls the game's count")
        check(args[1] == S.gBattleActor and args[2] == S.gBattleTarget, true,
              "expOf: on the simulation's actor and target")
        local damaged, hp = mem[S.gBattleActor + 0x7C], mem[S.gBattleTarget + 0x13]
        seen[#seen + 1] = damaged .. "/" .. hp .. "/" .. mem[S.gBattleActor + 0x13]
        return damaged == 0 and 1 or hp == 0 and 40 or 12
    end
    local x = Sight.expOf(api, call, S, "actor")
    check(table.concat(seen, " "), "0/1/1 1/1/1 1/0/1", "expOf: each case's fields, the actor alive")
    check(x.none == 1 and x.hit == 12 and x.kill == 40, true, "expOf: each case's count")
    -- the struck side (our unit's counter): the same three cases with the two units swapped
    seen, mem = {}, {}
    local swapped = function(addr, args)
        check(args[1] == S.gBattleTarget and args[2] == S.gBattleActor, true,
              "expOf: the struck side counts itself against the striker")
        local damaged, hp = mem[S.gBattleTarget + 0x7C], mem[S.gBattleActor + 0x13]
        seen[#seen + 1] = damaged .. "/" .. hp .. "/" .. mem[S.gBattleTarget + 0x13]
        return damaged == 0 and 1 or hp == 0 and 40 or 12
    end
    x = Sight.expOf(api, swapped, S, "target")
    check(table.concat(seen, " "), "0/1/1 1/1/1 1/0/1", "expOf: the struck side's fields, it alive")
end

-- M.known (ADR 0414): a key first read by an enemy's strike (no count) gets its count from the
-- first teaching read, before nothing is played again; a later non-teaching read keeps it; the
-- count runs before the play on a miss.
do
    local memo, order = {}, {}
    local function count() order[#order + 1] = "count"; return { none = 1, hit = 5, kill = 9 } end
    local function play() order[#order + 1] = "play"; return { "d", "b", "j" } end
    local k = Sight.known(memo, "k", false, count, play)
    check(k[4], nil, "known: a strike's read has no count")
    k = Sight.known(memo, "k", true, count, play)
    check(k[4] and k[4].kill, 9, "known: the first teaching read fills it in")
    check(table.concat(order, ","), "play,count", "known: played once, counted once")
    Sight.known(memo, "k", false, count, play)
    check(memo.k[4] and memo.k[4].kill, 9, "known: a non-teaching read keeps it")
    order = {}
    Sight.known(memo, "m", true, count, play)
    check(table.concat(order, ","), "count,play", "known: on a miss the count comes first")
end

-- M.staffExp (ADR 0414): the Staff command's setup for the unit and slot, then the game's count
-- on the battle unit it set up.
do
    local S = { BattleInitItemEffect = 0x0802C000, GetBattleUnitStaffExp = 0x0802C100,
                gBattleActor = 0x0203A4EC }
    local calls = {}
    local function call(addr, args)
        calls[#calls + 1] = string.format("%X(%s)", addr, table.concat(args, ","))
        return addr == S.GetBattleUnitStaffExp and 11 or 0
    end
    check(Sight.staffExp(call, S, 0x0202BE4C, 2), 11, "staffExp: the game's count")
    check(table.concat(calls, " "), string.format("%X(%d,2) %X(%d)", S.BattleInitItemEffect,
          0x0202BE4C, S.GetBattleUnitStaffExp, S.gBattleActor), "staffExp: set up, then counted")
end

-- M.strikeAt / M.strikeOf (ADR 0414): a judged strike keeps its exchange's ways and its
-- target's count, and the HPs and level they were read at.
do
    local side = { armed = true, hit = 70, dmg = 5, crit = 0, hits = 1, dealt = { [0] = 0.3, [5] = 0.7 },
                   back = { [0] = 0.5, [10] = 0.5 }, joint = { { p = 1, dealt = 5, back = 10 } },
                   exp = { none = 1, hit = 10, kill = 30 }, slot = 0, tile = { x = 1, y = 0 } }
    local t = Sight.strikeAt(side, 0x81, 0x01, 10, 20, 7)
    check(t.joint == side.joint and t.taught == side.exp, true, "strikeAt: the ways and the count")
    check(t.enemy .. " " .. t.target .. " " .. t.strikerHp .. " " .. t.targetHp .. " " .. t.targetLevel,
          "129 1 10 20 7", "strikeAt: who, the HPs and the level read at")
    check(t.felled, 0.5, "strikeAt: our counter's chance to fell the striker")
    local none = Sight.strikeOf(nil)
    check(none.joint == nil and none.taught == nil, true, "strikeOf: no strike, no ways or count")
end

-- M.known keeps one side's count: a key read for the other side is an error, never a count.
do
    local memo = {}
    local function count() return { none = 1, hit = 2, kill = 3 } end
    local function play() return {} end
    Sight.known(memo, "k", "actor", count, play)
    check(memo.k.side, "actor", "known: the entry keeps the side counted")
    check(pcall(Sight.known, memo, "k", "target", count, play), false,
          "known: the other side's read of that key raises")
end

-- The counter's count is read only in the judged phase (ADR 0414), read off the source: the
-- strike's exchange teaches only while `learning`, which only s.enemyPhase sets true, and
-- nextPhase and s.strike set false, each through learningAs (which puts the flag back); the
-- judged strike takes its level from the board unit.
do
    local src = sightSrc
    check(src:find('exchange(call, proc, sim, learning and target < 0x40 and "target" or nil)', 1, true) ~= nil,
          true, "learning: a strike on a player unit counts only while learning")
    local _, sets = src:gsub("learning = [%a]+", "")
    check(sets, 3, "learning: set only by its declaration and learningAs (set, put back)")
    local function bodyOf(name)
        local at = src:find(name, 1, true)
        return at and src:sub(at, src:find("\n    end\n", at, true)) or ""
    end
    check(bodyOf("function s.enemyPhase(plan)"):find("learningAs(true,", 1, true) ~= nil, true,
          "learning: the judged phase counts")
    check(bodyOf("function s.nextPhase(plan, reply)"):find("learningAs(false,", 1, true) ~= nil, true,
          "learning: the lookahead's phase does not")
    check(bodyOf("function s.strike(u, e, x, y, slot, from)"):find("learningAs(false,", 1, true) ~= nil,
          true, "learning: a single strike's forecast does not")
    local call = src:find("local t = M.strikeAt(side, id, target,", 1, true)
    check(call ~= nil and src:find("byId[target] and byId[target].level)", call, true) ~= nil, true,
          "strikeAt: the judged strike's level is the board unit's")
end

-- M.known: an entry a non-teaching read made takes the side of the first teaching read.
do
    local memo = {}
    local function count() return { none = 1, hit = 2, kill = 3 } end
    Sight.known(memo, "k", nil, count, function() return {} end)
    check(memo.k.side, nil, "known: a non-teaching entry has no side")
    Sight.known(memo, "k", "target", count, function() return {} end)
    check(memo.k.side .. " " .. memo.k[4].kill, "target 3", "known: the first teaching read sets it")
end

-- A ballista's rider (#510, vanilla Ch10 on Eirika's route): Innes (charId 11) joined riding an
-- emptied ballista, the bot planned his Silver Bow from (7,23), and the game showed him no
-- Attack there (AttackCommandUsability hides it from a rider). weapons() lists nothing for a
-- rider and his bow on foot; riderTiles() drops the tiles CanMoveActiveUnitTo refuses him (a
-- ballista's), keeps his own, and asks an ally's tile with the ally lifted off the map.
do
    local m = fakeMem()
    local S = { CanUnitUseWeaponNow = 1, CanMoveActiveUnitTo = 2, gActiveUnit = 0x100,
                gActiveUnitMoveOrigin = 0x110, gBmMapUnit = 0x200 }
    local ROWS = 0x300                      -- gBmMapUnit -> row pointers -> 32-wide rows
    m.w32(S.gBmMapUnit, ROWS)
    for y = 0, 31 do m.w32(ROWS + y * 4, 0x1000 + y * 32) end
    local api = { SYM = S, mem = m, write8 = m.w8, write16 = m.w16, write32 = m.w32,
                  Board = { itemRange = function() return 2, 3 end } }
    local BOW = 0x2F
    local innes = { addr = 0x4000, x = 2, y = 22, items = { { id = BOW, uses = 5 } },
                    state = Sight.US_IN_BALLISTA }
    local function sandbox(fn)
        return fn(function(fnAddr) return fnAddr == S.CanUnitUseWeaponNow and 1 or 0 end)
    end
    check(#Sight.weapons(api, innes, sandbox), 0, "weapons: a ballista's rider is listed none")
    local onFoot = { addr = innes.addr, x = 2, y = 22, items = innes.items, state = 0 }
    local w = Sight.weapons(api, onFoot, sandbox)
    check(#w == 1 and w[1].slot == 0 and w[1].max == 3, true, "weapons: on foot, his bow")

    -- (4,23) is the ballista's: refused while gBmMapUnit is clear there; (6,22) is an ally's
    m.w8(0x1000 + 22 * 32 + 6, 0x15)
    local asked = {}
    local function call(fnAddr, args)
        if fnAddr ~= S.CanMoveActiveUnitTo then return 0 end
        local x, y = args[1], args[2]
        asked[#asked + 1] = string.format("%d,%d:%d", x, y, m.u8(0x1000 + y * 32 + x))
        if m.u8(0x1000 + y * 32 + x) ~= 0 then return 0 end
        return (x == 4 and y == 23) and 0 or 1
    end
    local tiles = { { x = 2, y = 22 }, { x = 4, y = 23 }, { x = 7, y = 23 },
                    { x = 6, y = 22, by = 0x15 } }
    local function keys(list)
        local out = {}
        for _, t in ipairs(list) do out[#out + 1] = t.x .. "," .. t.y end
        return table.concat(out, " ")
    end
    check(keys(Sight.riderTiles(api, call, innes, tiles)), "2,22 7,23 6,22",
          "riderTiles: a rider ends on no other ballista's tile")
    check(table.concat(asked, " "), "4,23:0 7,23:0 6,22:0",
          "riderTiles: his own tile is never asked, an ally's is asked with it lifted")
    check(m.u8(0x1000 + 22 * 32 + 6), 0x15, "riderTiles: the ally is put back on the map")
    check(m.u32(S.gActiveUnit) .. " " .. m.u16(S.gActiveUnitMoveOrigin) .. ","
          .. m.u16(S.gActiveUnitMoveOrigin + 2), "16384 2,22",
          "riderTiles: asked as the active unit, setting out from his tile")
    check(keys(Sight.riderTiles(api, call, onFoot, tiles)), "2,22 4,23 7,23 6,22",
          "riderTiles: a unit on foot keeps every tile")
    -- a Canto move sets out from the act's tile: that one is kept unasked and is the origin
    asked = {}
    check(keys(Sight.riderTiles(api, call, innes, { { x = 7, y = 23 }, { x = 4, y = 23 } },
                                { x = 7, y = 23 })), "7,23",
          "riderTiles: a Canto rider keeps its set-out tile and ends on no ballista's")
    check(table.concat(asked, " ") .. " " .. m.u16(S.gActiveUnitMoveOrigin) .. ","
          .. m.u16(S.gActiveUnitMoveOrigin + 2), "4,23:0 7,23",
          "riderTiles: a Canto rider is asked setting out from the act's tile")

    -- the wiring: every reader of a move's tiles filters a rider's, and the answers' memo
    -- keys whether the unit rides (a rider's empty weapons are never served on foot)
    local function bodyOf(src, head)
        local at = src:find(head, 1, true)
        return at and src:sub(at, src:find("\n    end\n", at, true)) or ""
    end
    check(bodyOf(sightSrc, "    function s.reach(u, friends)")
              :find("M.riderTiles(api, call, u, movementTiles(u, u.x, u.y, friends))", 1, true)
          ~= nil, true, "riderTiles: s.reach filters the rider's tiles")
    check(bodyOf(sightSrc, "    function s.cantoTiles(u, a)")
              :find("M.riderTiles(api, call, u, movementTiles(u, x, y), { x = x, y = y })", 1,
                    true) ~= nil, true, "riderTiles: s.cantoTiles filters the rider's tiles")
    check(bodyOf(sightSrc, "    local function ownKey(kind, u, hp)")
              :find("M.riding(u.state)", 1, true) ~= nil, true,
          "weapons: the answers' memo keys whether the unit rides")
    local hf = assert(io.open(here .. "harness.lua"))
    local harnessSrc = hf:read("a")
    hf:close()
    local march = harnessSrc:find("local function marchToward(u, tx, ty, maxx, maxy)", 1, true)
    local marchBody = march and harnessSrc:sub(march, harnessSrc:find("\nend\n", march, true))
        or ""
    check(marchBody:find("INSPECT.Sight.riderTiles(api, call, rider, tiles)", 1, true) ~= nil,
          true, "riderTiles: harness marchToward filters the rider's tiles")
    -- M.riding is the one rider test: no other reads the bit off a state word
    local _, copies = sightSrc:gsub("& M%.US_IN_BALLISTA", "")
    check(copies, 1, "riding: sight.lua reads US_IN_BALLISTA in M.riding alone")
end

-- convoyKey (#510, Supply mid-map): the convoy's first item that lets the unit open a door, as
-- the Supply screen's Take would hand it; none with a full bag, a convoy that is not the
-- game's, or no such item. legal asks it again for the key the act names.
do
    local convoy, fault = {}, nil
    local Bd = { ITEM_COUNT = 5, convoyItems = function() return convoy end,
                 convoyFault = function() return fault end }
    local opens = function(id) return id == 0x6A end
    local u = { items = { {}, {} } }
    convoy = { { id = 0x14, uses = 30 }, { id = 0x6A, uses = 1 } }
    local k = Sight.convoyKey(Bd, nil, {}, u, opens)
    check(k and (k.id .. "x" .. k.uses), "106x1", "convoyKey: the first item that opens a door")
    check(Sight.convoyKey(Bd, nil, {}, { items = { {}, {}, {}, {}, {} } }, opens), nil,
          "convoyKey: none into a full bag")
    fault = "a garbage slot"
    check(Sight.convoyKey(Bd, nil, {}, u, opens), nil, "convoyKey: none from a convoy not the game's")
    fault, convoy = nil, { { id = 0x14, uses = 30 } }
    check(Sight.convoyKey(Bd, nil, {}, u, opens), nil, "convoyKey: none with no key in it")
    local at = sightSrc:find('elseif a.act == "supply" then', 1, true)
    local branch = at and sightSrc:sub(at, sightSrc:find("elseif", at + 10, true)) or ""
    check(branch:find("key.id == a.item", 1, true) ~= nil and branch:find("key.uses == a.uses", 1, true) ~= nil,
          true, "legal: a Take is legal only while the key it names is the convoy's")
end

-- replyKills / safest: the army's reply between the lookahead's two enemy phases (#510 comment
-- 6906859807). A kill at even odds or better is made, the likeliest first, one act a unit, one
-- death an enemy and one unit a tile; a unit that kills nothing steps to the tile the fewest
-- enemies reach, staying put on a tie, then the nearest.
do
    local function opt(unit, enemy, x, y, p) return { unit = unit, enemy = enemy, tile = { x = x, y = y }, p = p } end
    local function keys(ks)
        local out = {}
        for _, k in ipairs(ks) do out[#out + 1] = k.unit .. ">" .. k.enemy .. "@" .. k.tile.x .. "," .. k.tile.y end
        return table.concat(out, " ")
    end
    check(keys(Sight.replyKills({ opt(1, 0x81, 2, 2, 0.49) })), "",
          "replyKills: under even odds no kill is made")
    check(keys(Sight.replyKills({ opt(1, 0x81, 2, 2, 0.5) })), "1>129@2,2",
          "replyKills: even odds kill")
    -- unit 1 kills 0x81 surer than unit 2 does, so 2 takes 0x82
    check(keys(Sight.replyKills({ opt(2, 0x81, 3, 3, 0.7), opt(1, 0x81, 2, 2, 0.9),
                                  opt(2, 0x82, 4, 4, 0.6) })), "1>129@2,2 2>130@4,4",
          "replyKills: the likeliest first, one death an enemy")
    -- unit 1's surest kill uses it up: its second is not made
    check(keys(Sight.replyKills({ opt(1, 0x81, 2, 2, 0.9), opt(1, 0x82, 2, 3, 0.8) })), "1>129@2,2",
          "replyKills: one act a unit")
    -- both want (2,2): the first keeps it, the second kills from another tile
    check(keys(Sight.replyKills({ opt(1, 0x81, 2, 2, 0.9), opt(2, 0x82, 2, 2, 0.8),
                                  opt(2, 0x82, 5, 5, 0.7) })), "1>129@2,2 2>130@5,5",
          "replyKills: one unit a tile")

    local d = { ["1,1"] = 2, ["2,1"] = 0, ["3,1"] = 0, ["1,2"] = 1 }
    local function danger(x, y) return d[x .. "," .. y] or 9 end
    local tiles = { { x = 1, y = 1 }, { x = 3, y = 1 }, { x = 2, y = 1 }, { x = 1, y = 2 } }
    local t = Sight.safest(tiles, danger, { x = 1, y = 1 })
    check(t.x .. "," .. t.y, "2,1", "safest: the fewest enemies, the nearest of the tied")
    d["1,1"] = 0
    t = Sight.safest(tiles, danger, { x = 1, y = 1 })
    check(t.x .. "," .. t.y, "1,1", "safest: its own tile when no tile is safer")
    check(Sight.safest({}, danger, { x = 1, y = 1 }), nil, "safest: no tile, no step")
    -- the reply is read only beside the hold: nextPhase plays it only when asked
    local at = sightSrc:find("function s.nextPhase(plan, reply)", 1, true)
    local body = at and sightSrc:sub(at, sightSrc:find("\n    end\n", at, true)) or ""
    check(body:find("reply and armyReply(", 1, true) ~= nil, true,
          "nextPhase: the army's reply only when asked")
end

print(string.format("%d tests, %d failures", tests, fails))
if fails > 0 then os.exit(1) end
