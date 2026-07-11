-- ch02check.lua -- pure helpers for the ch02 structural load-test (#22), kept free of any
-- emulator dependency so they unit-test without a ROM (cf. clearbot.lua). The harness reads
-- the bytes (leader inventory + convoy) and hands this module a flat list of item ids.
local M = {}

-- Given a flat list of collected item ids and the set of charm item ids to look for, return
-- the charm ids that are present -- de-duplicated and in charmIds order (deterministic), with
-- empty 0x00 slots ignored. Used to verify the per-chwinga charm-gifts (Hand Axe / Elixir /
-- Pure Water) actually landed in the leader's inventory or the convoy after the ending scene.
-- (Mote's gift was vanilla Ch2's Red Gem; the ch02<->ch03 reward swap moved it to a ch03 chest, #23.)
function M.deliveredCharms(items, charmIds)
    local present = {}
    for _, id in ipairs(items) do
        if id ~= 0 then present[id] = true end
    end
    local out = {}
    for _, charm in ipairs(charmIds) do
        if present[charm] then out[#out + 1] = charm end
    end
    return out
end

return M
