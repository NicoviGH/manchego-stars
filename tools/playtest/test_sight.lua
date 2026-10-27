-- Tests for sight.lua's pure parts (#510 step 9 PR D): the sandbox over a fake CPU, our attack
-- and the enemy's strike as read off their simulations, turns left and the turn-event scan.
-- What the ROM's own functions return is proven by the `sightprobe` scenario, not here.
-- Run: lua tools/playtest/test_sight.lua
local here = (arg[0]:match("(.*/)")) or "./"
local Sight = dofile(here .. "sight.lua")

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
                regs.pc = (regs.lr & ~1) + 4   -- bx lr, then the pipeline reads ahead
            end
            if done() then return true end
        end
        return false
    end
    return cpu, function() return loads, ram end
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
    for r, v in pairs(before) do check(cpu.read(r), v, "register " .. r .. " is put back") end
end

do
    local cpu, seen = fakeCpu(3)
    local loop
    local got = Sight.machine(cpu)(function(call)
        local _, ram = seen(); ram.marker = "dirty"
        local r = call(0x08001001, { 2, 40 })
        loop = cpu.read("lr") & ~1
        return r
    end)
    check(got, 42, "a sandboxed call returns the function's r0")
    local loads, ram = seen()
    check(ram[loop], 0xE7FE, "lr names a Thumb `b .` written into scratch RAM")
    check(loop > cpu.read("sp"), false, "the loop sits above the call's stack, under the caller's")
    check(loads, 1, "the state is loaded back once")
    check(ram.marker, nil, "what the call wrote is gone after the sandbox")
    check(cpu.read("pc"), 0x1F8, "the CPU is back where the frame left it")
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
    local wrote = {}
    cpu.write32 = function(a, v) wrote[#wrote + 1] = { a, v } end
    Sight.machine(cpu)(function(call) return call(0x08001000, { 1, 2, 3, 4, -1 }) end)
    check(#wrote, 1, "one stack argument written")
    check(wrote[1][2], 0xFFFFFFFF, "BU_ISLOT_AUTO (-1) as a 32-bit word")
end

-- attackOf / strikeOf: our attack (with the enemy's counter) and the enemy's own strike are
-- separate reads.
local hitter = { hit = 80, crit = 5, dmg = 6, hits = 2, armed = true }
do
    local f = Sight.attackOf({ hit = 70, crit = 0, dmg = 5, hits = 1, armed = true,
                               counter = hitter }, 5)
    check(f.counters, true, "armed: the enemy counters")
    check(f.counterDmg, 6, "the counter's damage")
    check(f.counterHits, 2, "with its blows")
    check(f.counterCrit, 5, "and its crit")
    check(f.killsTarget, true, "5 x 1 kills a 5 HP enemy")
end

do
    local f = Sight.attackOf({ hit = 70, crit = 0, dmg = 5, hits = 1, armed = true,
                               counter = { hit = 0, crit = 0, dmg = 0, hits = 0,
                                           armed = false } }, 9)
    check(f.counters, false, "an unarmed answer is no counter")
    check(f.counterDmg, 0, "so no counter damage")
    check(f.killsTarget, false, "5 x 1 does not kill 9")
end

do
    local t = Sight.strikeOf({ hit = 60, crit = 0, dmg = 9, hits = 1, armed = true, slot = 1,
                               tile = { x = 4, y = 4 } })
    check(t.takenDmg, 9, "the AI's strike")
    check(t.takenSlot, 1, "with the slot it chose")
    check(t.takenTile.x .. "," .. t.takenTile.y, "4,4", "and the tile")
    local none = Sight.strikeOf(nil)
    check(none.takenHit, 0, "an enemy whose AI does not strike us strikes nothing")
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

-- side: the forecast window marks only the ACTOR's Monster Stone 0xFF (damage and crit); a
-- target's is read as it is.
do
    local bytes = {}
    local mem = {
        u16 = function(a) return bytes[a] or 0 end,
        s8 = function(a) local v = bytes[a] or 0; return v >= 0x80 and v - 0x100 or v end,
    }
    local A, T, P = 0x100, 0x200, 0x300
    bytes[A + 0x48] = 0xB5        -- weapon: the Monster Stone (uses 0)
    bytes[A + 0x5A], bytes[T + 0x5C] = 12, 4
    bytes[A + 0x64], bytes[A + 0x6A] = 70, 0
    bytes[P + 0x50] = 1
    local actor = Sight.side(mem, A, T, P, 0x50, true)
    check(actor.dmg .. "/" .. actor.crit, "255/255",
        "the actor's Monster Stone: 0xFF damage and crit")
    local target = Sight.side(mem, A, T, P, 0x50, false)
    check(target.dmg .. "/" .. target.crit, "8/0", "the same stone on the target's side: as it is")
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

-- answerOf: kills in one round AND outlives the counter at its worst; strength = expected damage.
do
    local a = { hit = 80, dmg = 6, hits = 2, killsTarget = true, counterDmg = 5, counterHits = 2 }
    local ok, strength = Sight.answerOf(a, 11)
    check(ok, true, "answerOf: kills, and 10 counter damage < 11 HP")
    check(strength, 9.6, "answerOf: strength = 6 x 2 x 80%")
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

print(string.format("%d tests, %d failures", tests, fails))
if fails > 0 then os.exit(1) end
