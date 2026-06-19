-- fuzzrng.lua -- pure seeded PRNG + weighted input policy for the stability fuzzer (#49).
--
-- NO emulator calls and NO host math.random: a self-contained linear congruential
-- generator so a given seed yields an IDENTICAL sequence on any Lua >= 5.3 (the CI `lua`
-- AND mGBA's embedded interpreter, both of which have 64-bit integers + bitwise ops --
-- harness.lua already relies on `&`). That host-independence is the contract a fuzzer
-- lives or dies by: a crash found at PT_SEED=N must replay exactly at PT_SEED=N. Unit
-- tested without an emulator in test_fuzzrng.lua.
--
--   new(seed)               -> generator with :next()
--   gen:next()              -> next pseudo-random integer in [0, 2^32), advancing state
--   weightedPick(gen, list) -> one entry of `list`, chosen with probability weight/sum.
--       Entries are opaque tables carrying a numeric `weight` (default 1); the driver puts
--       whatever it likes alongside it ({ key = K.A, hold = 3, weight = 5 }). A weight of 0
--       disables an entry, so the driver can mute a key without restructuring the table.

local M = {}

local MASK = 0xFFFFFFFF
-- Numerical Recipes LCG constants. a*state (<= 1664525 * 2^32 ~= 2^52.6) stays well within
-- 63-bit signed range before the mask, so the arithmetic never overflows on a 64-bit int Lua.
local A, C = 1664525, 1013904223

function M.new(seed)
    local state = (seed or 0) & MASK
    local gen = {}
    function gen:next()
        state = (A * state + C) & MASK
        return state
    end
    return gen
end

function M.weightedPick(gen, entries)
    local total = 0
    for _, e in ipairs(entries) do total = total + (e.weight or 1) end
    local r = gen:next() % total
    local acc = 0
    for _, e in ipairs(entries) do
        acc = acc + (e.weight or 1)
        if r < acc then return e end
    end
    return entries[#entries]   -- unreachable unless total mismatches; safe fallback
end

return M
