-- Tests for jobs.lua (#766, R2 of #764): who does which job over several turns.
-- Run: lua tools/playtest/test_jobs.lua
local here = (arg[0]:match("(.*/)")) or "./"
local Jobs = dofile(here .. "jobs.lua")

local tests, fails = 0, 0
local function check(got, want, msg)
    tests = tests + 1
    if got ~= want then
        fails = fails + 1
        print(string.format("FAIL: %s\n  got  %s\n  want %s", msg, tostring(got), tostring(want)))
    end
end

local GAMMA = 0.85

-- A straight road: a unit at x walks `mov` tiles a turn. A job at tile x closes after enemy
-- phase `closes` (it must be had by player phase `closes`). The value is worth x GAMMA^(turns-1),
-- none past the deadline: Goals.chance's shape for one taker.
local function road(units)
    local byId = {}
    for _, u in ipairs(units) do byId[u.id] = u end
    return function(u, j, from)
        local x0, late = from and from.x or u.x, from and from.late or 0
        local turns = late + math.max(math.ceil(math.abs(j.tile.x - x0) / u.mov), 1)
        if j.closes and turns > j.closes then return nil end
        return j.worth * GAMMA ^ (turns - 1), turns
    end
end

local function jobOf(out, id) return out[id] and out[id][1] and out[id][1].id or "-" end

-- test_the_greedy_pairing_loses_a_village: Vanessa (fast, at 0) can make either village in
-- time; Gilliam (slow, at 0) makes only the near rich one. Greedy gives Vanessa the rich one
-- (her worth there is highest) and the far one is lost. The assignment sends Vanessa far and
-- Gilliam near: both had.
do
    local A = { id = 1, slot = 1, x = 0, mov = 8 }   -- the flier
    local B = { id = 2, slot = 2, x = 0, mov = 4 }   -- the knight
    local near = { id = "near", tile = { x = 8 }, worth = 1000, closes = 3 }
    local far = { id = "far", tile = { x = 16 }, worth = 800, closes = 2 }
    local out, total = Jobs.assign({ A, B }, { near, far }, road({ A, B }))
    check(jobOf(out, 1), "far", "assignment: the flier takes the village only it reaches in time")
    check(jobOf(out, 2), "near", "assignment: the knight takes the near one")
    check(total > 1000, true, "assignment: both villages are had")
end

-- test_a_unit_chains_two_jobs: one unit, two villages on its way, both open long enough: it is
-- given both, the nearer (urgent) first, the second counted from the first's tile.
do
    local A = { id = 1, slot = 1, x = 0, mov = 5 }
    local a = { id = "a", tile = { x = 5 }, worth = 500, closes = 2 }
    local b = { id = "b", tile = { x = 10 }, worth = 500, closes = 4 }
    local out = Jobs.assign({ A }, { a, b }, road({ A }))
    check(out[1] and #out[1], 2, "chain: one unit gets both jobs")
    check(jobOf(out, 1), "a", "chain: the urgent job first")
    check(out[1] and out[1][2] and out[1][2].id, "b", "chain: the later job second")
end

-- test_a_job_no_one_makes_is_dropped: a village that closes before anyone can get there is
-- given to no one (it is not chased), and the unit takes what it can still have.
do
    local A = { id = 1, slot = 1, x = 0, mov = 4 }
    local lost = { id = "lost", tile = { x = 20 }, worth = 5000, closes = 2 }
    local open = { id = "open", tile = { x = 4 }, worth = 100 }
    local out = Jobs.assign({ A }, { lost, open }, road({ A }))
    check(jobOf(out, 1), "open", "dropped: the unreachable rich job is not chased")
end

-- test_a_tie_goes_to_the_fewest_turns: two equal villages, two equal units at either end: each
-- takes the one beside it, not the one across.
do
    local A = { id = 1, slot = 1, x = 0, mov = 4 }
    local B = { id = 2, slot = 2, x = 20, mov = 4 }
    local w = { id = "w", tile = { x = 2 }, worth = 100 }
    local e = { id = "e", tile = { x = 18 }, worth = 100 }
    local out = Jobs.assign({ A, B }, { w, e }, road({ A, B }), { chain = 1 })
    check(jobOf(out, 1), "w", "tie: the west unit takes the west village")
    check(jobOf(out, 2), "e", "tie: the east unit takes the east village")
end

-- test_takers_limit_who_may_take_a_job: a Talk only one unit may make goes to it, even when
-- another is nearer.
do
    local A = { id = 1, slot = 1, x = 0, mov = 5 }
    local B = { id = 2, slot = 2, x = 10, mov = 5 }
    local talk = { id = "talk", tile = { x = 10 }, worth = 300 }
    local out = Jobs.assign({ A, B }, { talk }, road({ A, B }), {
        takers = function() return { A } end })
    check(jobOf(out, 1), "talk", "takers: the one talker is sent")
    check(jobOf(out, 2), "-", "takers: the nearer non-talker is not")
end

-- test_a_fixed_job_is_kept: B was sent to `w` last decision. A is nearer now, but B keeps it,
-- and A is left the rest.
do
    local A = { id = 1, slot = 1, x = 2, mov = 4 }
    local B = { id = 2, slot = 2, x = 8, mov = 4 }
    local w = { id = "w", tile = { x = 1 }, worth = 100 }
    local out = Jobs.assign({ A, B }, { w }, road({ A, B }), { fixed = { [2] = "w" } })
    check(jobOf(out, 2), "w", "fixed: the sent unit keeps its job")
    check(jobOf(out, 1), "-", "fixed: the nearer unit is not given it")
end

-- test_budget: with a budget of 1 node the search stops at once and still returns an
-- assignment (all jobs left), never an error.
do
    local A = { id = 1, slot = 1, x = 0, mov = 4 }
    local w = { id = "w", tile = { x = 1 }, worth = 100 }
    local out, total = Jobs.assign({ A }, { w }, road({ A }), { budget = 1 })
    check(type(out), "table", "budget: an assignment comes back")
    check(total >= 0, true, "budget: its worth is a number")
end

print(string.format("%d tests, %d failures", tests, fails))
if fails > 0 then os.exit(1) end
