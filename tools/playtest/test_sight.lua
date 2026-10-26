-- Tests for sight.lua's pure parts (#510 step 9 PR D): the sandbox over a fake CPU, the
-- forecast assembled from two simulated sides, and the enemy's strike tile. What the ROM's
-- own functions return is proven by the `sightprobe` scenario, not here.
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
    function cpu.load(st) loads = loads + 1; regs.pc, regs.sp, ram.marker = st.pc, st.sp, st.marker end
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
    -- The fifth argument rides the stack, as the ARM calling convention puts it.
    local cpu = fakeCpu(1)
    local wrote = {}
    cpu.write32 = function(a, v) wrote[#wrote + 1] = { a, v } end
    Sight.machine(cpu)(function(call) return call(0x08001000, { 1, 2, 3, 4, -1 }) end)
    check(#wrote, 1, "one stack argument written")
    check(wrote[1][2], 0xFFFFFFFF, "BU_ISLOT_AUTO (-1) as a 32-bit word")
end

-- assemble: the four shapes an exchange takes.
local hitter = { hit = 80, crit = 5, dmg = 6, hits = 2, armed = true }
do
    local ours = { hit = 70, crit = 0, dmg = 5, hits = 1, armed = true, counter = hitter }
    local f = Sight.assemble(ours, nil, 20, 5)
    check(f.counters, true, "in range, armed: the enemy counters")
    check(f.takenDmg, 6, "taken is the counter")
    check(f.takenHits, 2, "with its blows")
    check(f.killsTarget, true, "5 x 1 kills a 5 HP enemy")
    check(f.diesWorst, true, "6 x 2, x3 on its 5% crit = 36 >= 20 HP")
end

do
    local ours = { hit = 70, crit = 0, dmg = 5, hits = 1, armed = true, counter = hitter }
    local f = Sight.assemble(ours, nil, 37, 9)
    check(f.diesWorst, false, "36 worst case against 37 HP survives")
    check(f.killsTarget, false, "5 x 1 does not kill 9")
end

do
    local ours = { hit = 70, crit = 0, dmg = 5, hits = 1, armed = true,
                   counter = { hit = 0, crit = 0, dmg = 0, hits = 0, armed = false } }
    local f = Sight.assemble(ours, hitter, 10, 30)
    check(f.counters, false, "an unarmed answer is no counter")
    check(f.takenDmg, 6, "taken is the enemy's own strike on its phase")
    check(f.diesWorst, false, "and the exchange alone cannot kill us")
end

do
    local f = Sight.assemble(nil, hitter, 10, 30)
    check(f.hit, 0, "out of range: no attack of ours")
    check(f.killsTarget, false, "so no kill")
    check(f.counters, false, "and no counter")
    check(f.takenHit, 80, "the enemy's strike is still read")
end

do
    local f = Sight.assemble(nil, nil, 10, 30)
    check(f.takenHit, 0, "an enemy with no weapon reach strikes nothing")
end

-- aiPick: FE8's AI weapon choice -- the best score, a tie to the later slot, skips left out.
do
    local p = Sight.aiPick({ { slot = 0, score = 40 }, { slot = 1, score = 90 }, { slot = 2, score = 60 } })
    check(p.slot, 1, "the best-scoring slot")
    p = Sight.aiPick({ { slot = 0, score = 50 }, { slot = 1, score = 50 } })
    check(p.slot, 1, "a tie goes to the later slot, as cp_battle.c's >= does")
    p = Sight.aiPick({ { slot = 0, skip = true }, { slot = 1, score = 0 } })
    check(p.slot, 1, "a skipped slot never wins, even over a zero score")
    check(Sight.aiPick({ { slot = 0, skip = true } }), nil, "no usable weapon, no strike")
    check(Sight.aiPick({}), nil, "an empty hand, no strike")
end

-- The AI's scratch struct fits between the forecast proc and the return loop.
check(Sight.SCRATCH_SIZE <= 0x70, true, "scratch ends before the loop at +0x80 (scratch at +0x10)")

-- strikeTile: a tile at the enemy's own range, inside the map.
do
    local x, y = Sight.strikeTile(0, 0, 1, 10, 10)
    check(x .. "," .. y, "1,0", "the corner's first in-map tile at range 1")
    x, y = Sight.strikeTile(5, 5, 2, 10, 10)
    check(x .. "," .. y, "5,3", "range 2 from the middle")
    check(Sight.strikeTile(5, 5, nil, 10, 10), nil, "no weapon reach, no tile")
    check(Sight.strikeTile(0, 0, 3, 2, 2), nil, "no tile at that range inside a 2x2 map")
end

print(string.format("%d tests, %d failures", tests, fails))
if fails > 0 then os.exit(1) end
