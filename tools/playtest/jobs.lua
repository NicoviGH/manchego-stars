-- jobs.lua: who does which job, over several turns (#766, R2 of the bot redesign #764). Pure: no
-- emulator, no game read; the caller hands it each job's worth and each unit's way to it.
--
-- A person sends units so that every goal is had before it closes, not the best goal first and
-- then whatever is left: vanilla Ch10's fliers took the (11,15) village, and nobody was timed
-- for (1,11) (#764's witness). The greedy pairing (each pair by its worth, the best first) gives
-- the one unit that can make two goals the richer one, and the other goal is lost although a
-- slower unit could have made the richer one in time. This module asks which ASSIGNMENT gets
-- the most worth: every unit a chain of jobs (the first is where it marches now; the next starts
-- where the first ends, its turns counted on), urgent jobs first in a chain.
--
-- The worth of a job taken is the caller's `value(u, job, from)`: its worth x the chance the
-- unit gets there in time (goals.lua's Goals.chance: GAMMA a turn, none past the job's
-- deadline), from `from` (nil: where the unit stands; else the tile the chain's last job ends on,
-- and the turns spent on the way, `late`). No new weight (Nicolas, 2026-11-24, #764): the
-- worth is the style's own (Goals.worth), its loss the style's death weight.
--
-- ADR 0396 holds: a job ranks, the game alone forbids. A unit given no job marches on the
-- objective as before.

local M = {}

-- How many jobs one unit is given in a row. Two: the second is what keeps a unit that can make
-- two goals from being counted for one goal only, while a chain of three asks the field for
-- turns from tiles the unit will reach five or more turns from now, a read the enemy's moves
-- by then make little better than a guess (the forecast's own horizon is 8 enemy phases,
-- sight.lua CLOSE_HORIZON).
M.CHAIN = 2

-- The most search nodes one assignment may visit: the search is exact under it (a bound prunes
-- a branch only when it cannot beat the best found), and past it the best found so far stands
-- (test_jobs's `budget` case pins that).
M.BUDGET = 50000

-- Values closer than this are a tie (sums of float products differ in their last bits with the
-- order they are added in); a tie goes to the assignment that has more jobs done, then to the one
-- whose `cost`s (value's third answer) sum least.
local EPS = 1e-9

-- Jobs in the order a chain takes them: the one that closes first, then the richer, then by id
-- (a job with no deadline closes last).
local function urgency(a, b)
    local ca, cb = a.closes or math.huge, b.closes or math.huge
    if ca ~= cb then return ca < cb end
    if (a.worth or 0) ~= (b.worth or 0) then return (a.worth or 0) > (b.worth or 0) end
    return tostring(a.id) < tostring(b.id)
end

-- assign(units, jobs, value, opts) -> { [unit id] = { job, job2? } }, the total worth.
--   units  { { id, slot } }: those that may be given a job, in the order a tie goes to
--   jobs   { { id, worth, closes } }: `worth` bounds what the job can add (its value at chance
--          1); `closes` orders a chain (urgent first); anything else rides along untouched
--   value  value(u, job, from) -> v, turns, cost: the job's worth to `u` x its chance, the turn
--          it gets there on (counted from now, `from.late` included: the next job's `late`), and
--          what a tie between equal worths is settled by, the fewer the better (default: turns;
--          a march's length is finer); nil: u cannot do it in time. A worth of 0 is still a job
--          (a village whose gift the style has no prior for: a new player visits it anyway).
--          `from` is nil for u's first job, { x, y, late } for the next one. Asked once per
--          (unit, job, from): the search reaches one chain's end by many orders
--   opts   { takers = function(job) -> the units that may take it (default: all), chain (default
--          M.CHAIN), budget (default M.BUDGET) }
function M.assign(units, jobs, value, opts)
    opts = opts or {}
    local chain, budget = opts.chain or M.CHAIN, opts.budget or M.BUDGET
    local asked = {}
    local raw = value
    value = function(u, j, from)
        local k = u.id .. "|" .. tostring(j.id) .. "|"
            .. (from and (tostring(from.x) .. "," .. tostring(from.y) .. "," .. from.late) or "-")
        local r = asked[k]
        if not r then
            r = table.pack(raw(u, j, from))
            asked[k] = r
        end
        return r[1], r[2], r[3]
    end
    local order = {}
    for _, j in ipairs(jobs) do order[#order + 1] = j end
    table.sort(order, urgency)
    -- each job's takers, the best first job first (its value from where it stands, then slot):
    -- a search the budget cuts short keeps its first dive, and that dive is then the greedy
    -- pairing's, never a worse one by slot order
    local takers = {}
    for i, j in ipairs(order) do
        local list = {}
        for _, u in ipairs(opts.takers and opts.takers(j) or units) do list[#list + 1] = u end
        local first = {}
        for _, u in ipairs(list) do first[u.id] = value(u, j, nil) or -math.huge end
        table.sort(list, function(a, b)
            if first[a.id] ~= first[b.id] then return first[a.id] > first[b.id] end
            return (a.slot or 0) < (b.slot or 0)
        end)
        takers[i] = list
    end
    -- what the jobs from i on could add at most: each its own worth
    local rest = { [#order + 1] = 0 }
    for i = #order, 1, -1 do rest[i] = rest[i + 1] + math.max(order[i].worth or 0, 0) end

    local chains, ends = {}, {}   -- unit id -> its jobs so far; -> { x, y, late } its chain's end
    local cur, curTurns, curN = 0, 0, 0
    local best, bestTurns, bestN, bestChains = -1, math.huge, -1, {}
    local nodes = 0

    local function better(v, t)
        if v > best + EPS then return true end
        if v < best - EPS then return false end
        if curN ~= bestN then return curN > bestN end
        return t < bestTurns
    end
    local function keep()
        best, bestTurns, bestN, bestChains = cur, curTurns, curN, {}
        for id, c in pairs(chains) do
            local copy = {}
            for k, j in ipairs(c) do copy[k] = j end
            bestChains[id] = copy
        end
    end
    local function give(u, j, v, t, cost)
        chains[u.id] = chains[u.id] or {}
        table.insert(chains[u.id], j)
        local was = ends[u.id]
        ends[u.id] = { x = j.tile and j.tile.x, y = j.tile and j.tile.y, late = t }
        cur, curTurns, curN = cur + v, curTurns + (cost or t), curN + 1
        return was
    end
    local function take(u, was, v, t, cost)
        table.remove(chains[u.id])
        if #chains[u.id] == 0 then chains[u.id] = nil end
        ends[u.id] = was
        cur, curTurns, curN = cur - v, curTurns - (cost or t), curN - 1
    end

    local function search(i)
        nodes = nodes + 1
        if i > #order then
            if better(cur, curTurns) then keep() end
            return
        end
        -- no way to beat the best from here: every job left at its full worth falls short
        if cur + rest[i] < best - EPS then return end
        local j = order[i]
        for _, u in ipairs(takers[i]) do
            if nodes > budget then break end
            local c = chains[u.id]
            if not c or #c < chain then
                local v, t, cost = value(u, j, ends[u.id])
                if v then
                    local was = give(u, j, v, t, cost)
                    search(i + 1)
                    take(u, was, v, t, cost)
                end
            end
        end

        -- the job left to no one
        if nodes <= budget or best < 0 then search(i + 1) end
    end
    search(1)
    return bestChains, math.max(best, 0)
end

return M
