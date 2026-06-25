-- Tests for pathing.lua -- the pure BFS distance field for the clear-bot march (#60, no emulator).
-- Run: lua tools/playtest/test_pathing.lua
local here = (arg[0]:match("(.*/)")) or "./"
local P = dofile(here .. "pathing.lua")

local tests, fails = 0, 0
local function check(got, want, msg)
    tests = tests + 1
    if got ~= want then
        fails = fails + 1
        print(string.format("FAIL: %s\n  got  %s\n  want %s", msg, tostring(got), tostring(want)))
    end
end

-- Build (w, h, isPassable) from ASCII rows: '#' is a wall, anything else is passable. Row 0
-- is the first string; tiles are 0-indexed in both axes (matching the game's tile coords).
local function grid(rows)
    local h, w = #rows, #rows[1]
    local function isPassable(x, y)
        if x < 0 or y < 0 or x >= w or y >= h then return false end
        return rows[y + 1]:sub(x + 1, x + 1) ~= "#"
    end
    return w, h, isPassable
end

-- Open grid: distances equal Manhattan distance from the goal.
do
    local w, h, pass = grid({ "...", "...", "..." })
    local d = P.distanceField(w, h, pass, { x = 0, y = 0 })
    check(d[0][0], 0, "goal tile is distance 0")
    check(d[0][1], 1, "one tile right of goal is 1")
    check(d[1][0], 1, "one tile below goal is 1")
    check(d[2][2], 4, "far corner of an open 3x3 is Manhattan 4")
end

-- A wall forces a detour, so the path distance exceeds the Manhattan distance.
do
    -- goal at (0,1); column x=1 is walled at rows 0 and 1 (open at row 2):
    --   .#.
    --   G#.
    --   ...
    local w, h, pass = grid({ ".#.", "G#.", "..." })
    local d = P.distanceField(w, h, pass, { x = 0, y = 1 })
    -- (2,1) is Manhattan 2 away but the wall forces (0,1)->(0,2)->(1,2)->(2,2)->(2,1) = 4
    check(d[1][2], 4, "tile behind a wall is reached via the detour (4, not Manhattan 2)")
end

-- A goal walled off on all sides: only the goal itself has a distance; the rest is unreachable.
do
    --   ###
    --   #G#
    --   ###
    local w, h, pass = grid({ "###", "#G#", "###" })
    local d = P.distanceField(w, h, pass, { x = 1, y = 1 })
    check(d[1][1], 0, "isolated goal is still distance 0")
    check(d[0][1] == nil, true, "a walled tile adjacent to the goal is unreachable (nil)")
end

-- An impassable region beyond the wall is left nil (infinity), not a finite distance.
do
    --   G.#x   (x at (3,0) is cut off by the wall column x=2 across all rows)
    --   ..#.
    --   ..#.
    local w, h, pass = grid({ "G.#.", "..#.", "..#." })
    local d = P.distanceField(w, h, pass, { x = 0, y = 0 })
    check(d[0][1], 1, "reachable side is filled")
    check(d[0][3] == nil, true, "tile across an unbroken wall is unreachable (nil)")
end

if fails > 0 then
    print(string.format("\n%d/%d FAILED", fails, tests)); os.exit(1)
else
    print(string.format("ok -- %d assertions", tests))
end
