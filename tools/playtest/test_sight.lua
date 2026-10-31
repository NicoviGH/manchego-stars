-- Tests for sight.lua's pure parts (#510 step 9 PR D): the sandbox over a fake CPU, our attack
-- and the enemy's strike as read off their simulations, turns left and the turn-event scan.
-- What the ROM's own functions return is proven by the `sightprobe` scenario, not here.
-- Run: lua tools/playtest/test_sight.lua
local here = (arg[0]:match("(.*/)")) or "./"
local Sight = dofile(here .. "sight.lua")
local Board = dofile(here .. "board.lua")

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
    return cpu, function() return loads, ram end
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
    check(at[S.BattleRoll1RN] == nil and at[S.BattleRoll2RN] == nil, true,
          "played: the breakpoints are cleared")
end

-- test_talks_reads_each_entry_the_walk_hands_its_checks: the game's walk hands two talk
-- entries to its checks (one plain, one with an asm condition); CheckForCharacterEvents keeps
-- the available one, the walk was asked for a pair no entry names, and the breakpoints go.
do
    local bytes, holds, at = {}, {}, {}
    local function u8(a) return bytes[a] or 0 end
    local function u32(a) return u8(a) | u8(a + 1) << 8 | u8(a + 2) << 16 | u8(a + 3) << 24 end
    local function w8(a, v) bytes[a] = v & 0xFF end
    local function w32(a, v) for i = 0, 3 do w8(a + i, v >> (8 * i)) end end
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

-- Every equip in sight.lua goes through Sight.equip: a sandbox read that called
-- EquipUnitItemSlot itself would leak the reordered bag into the next judged plan again
-- (the test above proves only the helper). Read off the source: the strike and the enemy
-- phase each equip through it, and the game call appears in Sight.equip alone.
do
    local f = assert(io.open(here .. "sight.lua"))
    local src = f:read("a")
    f:close()
    local _, direct = src:gsub("S%.EquipUnitItemSlot", "")
    check(direct, 1, "equip: EquipUnitItemSlot is called from Sight.equip alone")
    for _, name in ipairs({ "s.strike", "s.enemyPhase" }) do
        local at = src:find("function " .. name .. "(", 1, true)
        local body = at and src:sub(at, (src:find("\n    function ", at + 1) or #src))
        check(body ~= nil and body:find("M.equip(api, call, S, ", 1, true) ~= nil, true,
              "equip: " .. name .. " equips through Sight.equip")
    end
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
    local write = cpu.write
    function cpu.write(r, v)
        if r == "pc" and v < 0x08000000 then v = v + 4 end   -- the refill, at the BIOS loop
        write(r, v)
    end
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

print(string.format("%d tests, %d failures", tests, fails))
if fails > 0 then os.exit(1) end
