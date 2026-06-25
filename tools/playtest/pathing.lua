-- pathing.lua -- pure BFS distance field for the clear-bot's march-to-boss (#60), kept free of
-- any emulator dependency so it unit-tests without a ROM (cf. clearbot.lua / ch02check.lua). The
-- harness reads terrain into a passability predicate; this turns it into a path-distance field so
-- a unit can route AROUND walls/peaks toward a held boss instead of greedily minimizing Manhattan
-- distance (which strands a unit against an obstacle).
local M = {}

-- distanceField(w, h, isPassable, goal) -> dist
--   isPassable(x, y) -> bool  (false out of bounds)
--   goal = { x =, y = }
--   dist[y][x] = number of 4-connected steps over passable tiles from goal to (x,y); the goal
--   tile is 0 (it is the source even if a unit stands on it); unreachable/impassable tiles are
--   absent (nil), which callers treat as +infinity.
function M.distanceField(w, h, isPassable, goal)
    local dist = {}
    for y = 0, h - 1 do dist[y] = {} end
    dist[goal.y][goal.x] = 0
    local queue = { { goal.x, goal.y } }
    local head = 1
    local dirs = { { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } }
    while head <= #queue do
        local cx, cy = queue[head][1], queue[head][2]
        head = head + 1
        local nd = dist[cy][cx] + 1
        for _, d in ipairs(dirs) do
            local nx, ny = cx + d[1], cy + d[2]
            if nx >= 0 and ny >= 0 and nx < w and ny < h
                and isPassable(nx, ny) and dist[ny][nx] == nil then
                dist[ny][nx] = nd
                queue[#queue + 1] = { nx, ny }
            end
        end
    end
    return dist
end

return M
