-- procmemo.lua -- the proc pool, read once per frame (#531).
--
-- Every observation asks "is proc X live?" about thirty times, and each ask used to be a
-- 64-slot scan of sProcArray: ~2,000 emulator reads per observation, several observations
-- per frame. This reads the pool's script words ONCE and answers every later ask from that
-- map until the pool can have changed.
--
-- WHEN THE POOL CAN CHANGE, and why the memo is keyed the way it is. The harness runs inside
-- mGBA's frame callback, so the GBA CPU does not execute between two harness reads: a key
-- press, or a poke that will start an event, changes nothing in the pool until the next
-- frame -- and the next frame is a new key. What CAN change the pool inside one callback is
-- the harness itself: a write into the pool, or a state load, which swaps all of memory
-- without the frame moving. Rather than enumerate which writes those are (and trust every
-- future one to be enumerated), the key is (frame, writes): `install` puts a guard in place
-- of the global `emu`, and EVERY call through it that is not a read bumps the write count --
-- writes, key presses, state loads, resets, and the same calls on any object reached through
-- it (`emu.memory.<domain>:write32`). ADR 0366. Conservative on purpose: a dropped memo costs
-- one 64-read rescan, a stale one costs a wrong verdict.
--
-- Pure over an injected env: test_procmemo.lua runs it against a fake emulator.
local ProcMemo = {}

-- Calls that only READ the emulator. Everything else counts as a write.
local function isRead(name)
    return name == "currentFrame" or name:sub(1, 4) == "read" or name:sub(1, 3) == "get"
end

-- A proxy for `obj` that forwards every method call to it, counting each non-read call as a
-- write via bump(). A member that is itself an object -- `emu.memory` and its domains, whose
-- handles have their own write8/write32 -- is guarded the same way, recursively: a write that
-- reached memory through a member the guard handed out unwrapped would never be counted, and
-- the memo would answer from before it. Plain values (numbers, strings) read straight through.
local function guardOf(obj, bump)
    return setmetatable({}, { __index = function(t, name)
        local member = obj[name]
        local kind = type(member)
        local forward
        if kind == "function" then
            if isRead(name) then
                forward = function(_, ...) return member(obj, ...) end
            else
                forward = function(_, ...) bump(); return member(obj, ...) end
            end
        elseif kind == "table" or kind == "userdata" then
            forward = guardOf(member, bump)
        else
            return member
        end
        rawset(t, name, forward)
        return forward
    end })
end

-- Replace env.emu with the write guard and return the proc map over the REAL emulator:
--   procs.raw         the real emulator (hot read paths bind to it, skipping the guard)
--   procs.pool        the `pool` it was installed over ({ base, stride, count }), so a caller
--                     can tell a proc address from any other word
--   procs.find(s)     the address of the lowest slot whose script is s, or nil (s == 0
--                     answers the first free slot, as the plain scan did; s == nil is an
--                     error: it is an unexported symbol, not an absent proc)
--   procs.live()      a NEW list of { slot, addr, script } for every non-empty slot, in slot
--                     order, on every call: the caller owns it, so mutating it cannot corrupt
--                     what the next caller in the same frame is told
-- `pool` is { base, stride, count }: SYM.sProcArray, sizeof(struct Proc), the pool size.
function ProcMemo.install(env, pool)
    local real = env.emu
    assert(real ~= nil, "procmemo.install: no emulator bound to env.emu yet")
    local writes = 0
    local guard = guardOf(real, function() writes = writes + 1 end)
    env.emu = guard

    -- scripts[i] is slot i's script word; byScript answers find(). live() is built from
    -- scripts on demand, so a frame that only asks find() never builds it.
    local keyFrame, keyWrites, byScript, scripts
    local function refresh()
        -- A write that bypassed the guard could leave the memo stale with nothing to show for
        -- it, so a replaced guard is an error here, not a quiet wrong answer.
        if rawget(env, "emu") ~= guard then
            error("procmemo: env.emu is no longer the write guard -- writes would bypass it and "
                .. "the proc map could answer from before them", 3)
        end
        local frame = real:currentFrame()
        if frame == keyFrame and writes == keyWrites then return end
        keyFrame, keyWrites = frame, writes
        byScript, scripts = {}, {}
        for i = 0, pool.count - 1 do
            local addr = pool.base + i * pool.stride
            local script = real:read32(addr)
            scripts[i] = script
            if byScript[script] == nil then byScript[script] = addr end
        end
    end
    return {
        raw = real,
        pool = pool,
        find = function(script)
            -- A symbol gen_symbols.py does not export reads as nil, and looking for nil finds
            -- nothing, which looks exactly like "the proc never started" (ch02armory, #493).
            if script == nil then
                error("PROCS.find: nil proc script -- add the symbol to gen_symbols.py's "
                    .. "export list", 2)
            end
            refresh()
            return byScript[script]
        end,
        live = function()
            refresh()
            local out = {}
            for i = 0, pool.count - 1 do
                local script = scripts[i]
                if script ~= 0 then
                    out[#out + 1] = { slot = i, addr = pool.base + i * pool.stride, script = script }
                end
            end
            return out
        end,
    }
end

return ProcMemo
