-- fakeline.lua -- a retry's memory for the unit tests, in the shape timeline.lua reads (#765):
-- { attempts = { timeline, ... } }. One attempt per call of M.attempt; each sighting becomes one
-- of the timeline's `units`, so a test states what an earlier attempt saw, not how it is stored.
--   enemies   { { id, charId, classId, arrival } }: reds seen (sight.remember's list)
--   arrivals  { { charId, classId, x, y, turn, boardTurn, by, timed, gone } }: units the screen
--             showed arrive (boardTurn defaults to turn); `gone` = { how, boardTurn, x, y }
--   closings  { { x, y, phase, closer, closerClass, closerKey } }
-- Pure; the tests' own, never a run's.
local Board = dofile(PLAYTEST_DIR and (PLAYTEST_DIR .. "/board.lua")
    or ((debug.getinfo(1, "S").source:match("^@(.*/)") or "./") .. "board.lua"))

local M = {}

-- One failed attempt's timeline.
function M.attempt(o)
    local units, slot = {}, 0x100
    for _, e in ipairs(o.enemies or {}) do
        units[#units + 1] = { key = Board.memoryKey(e.id, e.charId, e.classId, e.arrival),
                              id = e.id, charId = e.charId, classId = e.classId, faction = "red",
                              arrival = e.arrival, track = {} }
    end
    for _, a in ipairs(o.arrivals or {}) do
        slot = slot + 1
        local bt = a.boardTurn or a.turn
        units[#units + 1] = { key = Board.memoryKey(a.id or slot, a.charId, a.classId, bt),
                              id = a.id or slot, charId = a.charId, classId = a.classId,
                              faction = a.faction or "red", arrival = bt,
                              appeared = { turn = a.turn, boardTurn = bt, x = a.x, y = a.y,
                                           by = a.by, timed = a.timed },
                              track = {}, gone = a.gone }
    end
    return { units = units, deaths = o.deaths or {}, closings = o.closings or {}, items = {} }
end

-- A memory of one attempt per argument, oldest first.
function M.memory(...)
    local out = { attempts = {} }
    for _, o in ipairs({ ... }) do out.attempts[#out.attempts + 1] = M.attempt(o) end
    return out
end

return M
