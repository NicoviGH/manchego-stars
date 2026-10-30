-- Tests for procmemo.lua -- the proc pool read once per frame (#531), over a fake emulator,
-- so no mGBA. Run: lua tools/playtest/test_procmemo.lua
local here = (arg[0]:match("(.*/)")) or "./"
local ProcMemo = dofile(here .. "procmemo.lua")

local tests, fails = 0, 0
local function check(got, want, msg)
    tests = tests + 1
    if got ~= want then
        fails = fails + 1
        print(string.format("FAIL: %s\n  got  %s\n  want %s", msg, tostring(got), tostring(want)))
    end
end

local BASE, STRIDE, COUNT = 0x02026A70, 0x6C, 64
local A, B, C = 0x08A00000, 0x08A00100, 0x08A00200

-- A fake `emu`: word memory, a frame counter the test advances, and a count of every read32
-- so "one scan per frame" is measured rather than assumed.
local function fakeEmu()
    local mem, e = {}, { frame = 0, reads = 0, keys = 0 }
    function e:read32(a) self.reads = self.reads + 1; return mem[a] or 0 end
    function e:read8(a) self.reads = self.reads + 1; return (mem[a] or 0) & 0xFF end
    function e:write32(a, v) mem[a] = v end
    function e:currentFrame() return self.frame end
    function e:addKey(k) self.keys = self.keys | k end
    function e:clearKey(k) self.keys = self.keys & ~k end
    function e:loadStateFile(_) for k in pairs(mem) do mem[k] = nil end; return true end
    e.label = "not a method"
    -- mGBA's memory domains: objects reached THROUGH emu, with their own read/write methods.
    local wram = {}
    function wram:read32(a) e.reads = e.reads + 1; return mem[a] or 0 end
    function wram:write32(a, v) mem[a] = v end
    e.memory = { wram = wram }
    return e, mem
end
local function slot(i) return BASE + i * STRIDE end
local function setup()
    local real, mem = fakeEmu()
    local env = { emu = real }
    local procs = ProcMemo.install(env, { base = BASE, stride = STRIDE, count = COUNT })
    return procs, env, real, mem
end
-- procs.pool is the pool it was installed over (anyMenuProc bounds its parent walk by it).
do
    local procs = setup()
    check(procs.pool.base, BASE, "pool.base is the installed base")
    check(procs.pool.stride * procs.pool.count, STRIDE * COUNT, "pool spans stride * count")
end
-- The naive scan findProc used to be: the memo must agree with it on every pool.
local function naive(mem, script)
    for i = 0, COUNT - 1 do if (mem[slot(i)] or 0) == script then return slot(i) end end
    return nil
end

-- install swaps the guard in and hands back the real emulator.
do
    local procs, env, real = setup()
    check(procs.raw, real, "install exposes the real emulator for raw reads")
    check(env.emu ~= real, true, "install replaces env.emu with the write guard")
    check(env.emu.label, "not a method", "a non-method field reads straight through")
end

-- The answers are the naive scan's: first (lowest) slot wins, absent is nil.
do
    local procs, _, _, mem = setup()
    mem[slot(3)] = A; mem[slot(7)] = B; mem[slot(9)] = A
    check(procs.find(A), naive(mem, A), "a proc in two slots answers the lowest, as the scan did")
    check(procs.find(A), slot(3), "... which is slot 3")
    check(procs.find(B), slot(7), "a single proc answers its slot")
    check(procs.find(C), nil, "a script with no proc answers nil")
    check(procs.find(0), naive(mem, 0), "script 0 answers the first empty slot, as the scan did")
    local live = procs.live()
    check(#live, 3, "live() lists every non-empty slot")
    check(live[1].slot, 3, "in slot order")
    check(live[2].slot, 7, "in slot order (2)")
    check(live[3].addr, slot(9), "with its address")
    check(live[3].script, A, "and its script")
    -- The caller owns what live() returns: mutating it cannot change the next caller's view.
    live[1].addr = 0; table.remove(live, 2); live[#live + 1] = { slot = 99 }
    local again = procs.live()
    check(#again, 3, "a caller mutating its list does not change the next live()")
    check(again[1].addr, slot(3), "nor an entry in it")
end

-- An unexported symbol reads as nil; looking it up must fail loudly, not answer "no proc".
do
    local procs = setup()
    local ok, err = pcall(procs.find, nil)
    check(ok, false, "find(nil) is an error")
    check(tostring(err):match("gen_symbols") ~= nil, true, "naming the export list to fix")
end

-- One scan per frame: the second and later finds in a frame read nothing.
do
    local procs, env, real, mem = setup()
    mem[slot(5)] = A
    procs.find(A)
    check(real.reads, COUNT, "the first find of a frame scans the pool once")
    for _ = 1, 30 do procs.find(B); procs.find(A); procs.live() end
    check(real.reads, COUNT, "every later find in the same frame is free")
    -- Reads THROUGH THE GUARD do not drop the memo: they cannot start or end a proc. Each
    -- costs its own one read, and the find after them costs nothing.
    local reads = real.reads
    env.emu:read32(slot(5)); env.emu:read8(slot(5)); env.emu:currentFrame()
    env.emu.memory.wram:read32(slot(5))
    check(real.reads, reads + 3, "guarded reads forward, one read each")
    check(procs.find(A), slot(5), "and the memo still answers")
    check(real.reads, reads + 3, "with no rescan after reads through the guard")
end

-- A new frame rescans: a proc the game started since the last frame is seen.
do
    local procs, _, real, mem = setup()
    check(procs.find(A), nil, "frame 0: no proc")
    mem[slot(2)] = A          -- the game ran a frame and started it
    check(procs.find(A), nil, "still frame 0: the memo answers frame 0's pool")
    real.frame = 1
    check(procs.find(A), slot(2), "frame 1: the new proc is found")
    mem[slot(2)] = 0          -- and ended it on the next
    real.frame = 2
    check(procs.find(A), nil, "frame 2: the ended proc is gone")
end

-- Review focus: a harness WRITE in the middle of a frame drops the memo. Every non-read call
-- through env.emu counts -- a poke into the pool, a poke anywhere, a key, a state load -- so
-- the next read is a fresh scan of the same frame, never the pre-write answer.
do
    local procs, env, real, mem = setup()
    check(procs.find(A), nil, "before the poke: no proc")
    env.emu:write32(slot(4), A)
    check(mem[slot(4)], A, "the guard forwards the write to the real emulator")
    check(procs.find(A), slot(4), "same frame, after a pool poke: the proc is seen")
    env.emu:write32(slot(4), 0)
    check(procs.find(A), nil, "same frame, after the slot is cleared: it is gone")
    mem[slot(6)] = B           -- as if the game had already started it this frame
    env.emu:write32(0x0202BCF0, 1)   -- a poke that is NOT into the pool (an event flag)
    check(procs.find(B), slot(6), "any write drops the memo, not only one into the pool")
    mem[slot(6)] = 0
    env.emu:addKey(1)
    check(real.keys, 1, "the guard forwards a key press")
    check(procs.find(B), nil, "a key press drops the memo")
    mem[slot(8)] = C
    env.emu:clearKey(1)
    check(procs.find(C), slot(8), "a key release drops the memo")
    env.emu:loadStateFile("x.ss")   -- the whole pool changes without the frame moving
    check(procs.find(C), nil, "a state load drops the memo")
    -- A write through an object REACHED through the guard (a memory domain) counts too.
    mem[slot(10)] = 0
    check(procs.find(A), nil, "before the domain poke: A is not live")
    env.emu.memory.wram:write32(slot(10), A)
    check(mem[slot(10)], A, "the domain write reaches memory")
    check(procs.find(A), slot(10), "same frame, after a domain write: the memo was dropped")
    local reads = real.reads
    check(env.emu:read32(slot(8)), 0, "a read through the guard forwards")
    procs.find(C)
    check(real.reads, reads + 1, "and does not drop the memo")
    check(env.emu:currentFrame(), real.frame, "currentFrame forwards")
end

-- stamp() is the memo's key: it moves with the frame and with every non-read call, and with
-- nothing else (controllerState keeps a classification under it).
do
    local procs, env, real = setup()
    local f0, w0 = procs.stamp()
    env.emu:read32(slot(1))
    procs.find(A)
    local f1, w1 = procs.stamp()
    check(f1 == f0 and w1 == w0, true, "stamp: reads leave it unchanged")
    env.emu:write32(slot(1), A)
    local _, w2 = procs.stamp()
    check(w2 ~= w1, true, "stamp: a write moves it")
    real.frame = real.frame + 1
    local f3 = procs.stamp()
    check(f3 ~= f1, true, "stamp: a new frame moves it")
end

-- harness.lua writes nothing through PROCS.raw: the write counter sees only calls through the
-- guard, and both the proc memo and controllerState's per-frame state are kept under
-- PROCS.stamp(). Whether a call is a read is isRead's answer, the guard's own (ADR 0366).
do
    local f = assert(io.open(here .. "harness.lua"))
    local harness = f:read("a")
    f:close()
    -- every `raw:name(` whose `raw` is a whole name (PROCS.raw, a local, any other alias)
    local calls, writes = 0, {}
    for before, name in harness:gmatch("(.)raw:([%w_]+)%(") do
        if not before:match("[%w_]") then
            calls = calls + 1
            if not ProcMemo.isRead(name) then writes[#writes + 1] = name end
        end
    end
    check(calls > 0, true, "harness: the hot reads bind to PROCS.raw")
    check(table.concat(writes, ","), "", "harness: no non-read call through the raw emulator")
end

-- If anything replaces the guard (mGBA re-binding the global, or a script), writes would
-- bypass it and the memo could go stale silently. It must fail loudly instead.
do
    local procs, env, real = setup()
    env.emu = real
    local ok, err = pcall(procs.find, A)
    check(ok, false, "a replaced guard is an error, not a stale answer")
    check(tostring(err):match("write guard") ~= nil, true, "and the error says why")
end

print(string.format("%d tests, %d failures", tests, fails))
if fails > 0 then os.exit(1) end
