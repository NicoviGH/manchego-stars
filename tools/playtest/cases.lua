-- cases.lua -- the driver for DECLARED playtest cases (#314).
--
-- A chapter YAML declares what its scenarios prove; `tools/playtest/declared.py` emits one
-- case as a Lua table and this runs it. The vocabulary is deliberately small: it covers the
-- shape 15 of the harness's scenarios already share (boot -> settle -> drive -> read
-- memory), and anything outside it stays hand-written Lua behind the chapter's `lua:` key.
-- Code is the exception you NAME, not the default you copy.
--
-- WHY THIS IS ITS OWN CHUNK. Lua allows 200 locals per chunk and `harness.lua` is one chunk
-- sitting at that ceiling with 2 slots left (`check_lua_local_headroom` measures it). Of its
-- 198 top-level locals, 32 are chapter- or cast-scoped, so a chapter costs ~6-7 -- which
-- means the harness runs out during ch06, not at ch18. A chapter's Lua lives in its own
-- chunk with its own budget now; see decisions.md -> "A chapter costs local slots".
--
-- The driver never touches `emu`, `SYM` or any harness global: everything the game can do
-- arrives on the `api` table. That is what lets `test_cases.lua` be a complete test double,
-- and it is the interface the placement test asks for -- cases.lua talks over it and never
-- reaches into the harness's cabinet.
--
-- WHERE AN ASSERTION LIVES. An assertion about ONE STEP rides that step (`visit: {x, y,
-- gains}`); `then` holds only assertions about the WHOLE case (`spoke`, `event_flag`).
-- Neither is paired positionally, and both are needed. A whole-case list alone passes on
-- four doors handing over each other's gifts; a `then` list paired against `when` by INDEX
-- means inserting a step silently re-targets every assertion after it.
local M = {}

-- ---------------------------------------------------------------- given
-- Preconditions. `on_map` is the four-line preamble 15 scenarios open with, named once.
M.GIVEN = {}

M.GIVEN.on_map = function(api, state)
    if not api.bootToMap() then
        return false, "never reached the map"
    end
    api.fastConfig()
    -- The WEAK settle: player faction, no menu, no std_event. Deliberately not the idle
    -- one -- that is what every hand-written preamble waits on after a boot, and demanding
    -- `player_map_idle` here would be a stricter precondition than any of them proved.
    if not api.settle(false) then
        return false, "booted, but the map never returned to player control"
    end
    state.itemsAtStart = M.tally(api.collectedItems())
    return true
end

-- ---------------------------------------------------------------- when
-- Steps. Each returns ok, why.
M.WHEN = {}

-- `arg.gains` is an item id this door must hand over. It rides the STEP because the gift is
-- per-tile: a whole-case "these ids arrived" list passes on four doors swapping each other's
-- gifts, which is exactly the defect ch05reliquaries exists to catch. It is still not
-- positional -- the assertion lives INSIDE the step it belongs to, so inserting a door cannot
-- re-target another door's assertion.
M.WHEN.visit = function(api, arg, state)
    if type(arg) ~= "table" or type(arg.x) ~= "number" or type(arg.y) ~= "number" then
        return false, "a `visit` step needs a table with numeric x and y"
    end
    -- Settle FIRST. A location event's tail (give-item, MapChange, EVBIT_T, ENDA) is still
    -- running when the item lands, and walking to the next door while std_event holds the
    -- controller is an illegal input that dies as "cursor could not reach" -- which reads
    -- like a map problem and is an impatience problem.
    if not api.settle(true) then
        return false, string.format(
            "the map never returned to player control before (%d,%d)", arg.x, arg.y)
    end
    local before = M.tally(api.collectedItems())
    local ok, why, spoke = api.visitVillage(arg.x, arg.y)
    if not ok then
        return false, string.format("(%d,%d): %s", arg.x, arg.y, tostring(why))
    end
    api.shot("visit")
    state.visits = state.visits + 1
    if arg.gains ~= nil then
        state.asserted = state.asserted + 1
        local after = M.tally(api.collectedItems())
        if (after[arg.gains] or 0) <= (before[arg.gains] or 0) then
            return false, string.format(
                "(%d,%d) was visited but did not hand over item 0x%02X -- this door's OWN "
                .. "gift. Another door's gift arriving instead still fails here, on purpose",
                arg.x, arg.y, arg.gains)
        end
    end
    if not spoke then
        state.silent[#state.silent + 1] = string.format("(%d,%d)", arg.x, arg.y)
    end
    return true
end

-- ---------------------------------------------------------------- then
-- Assertions. Each returns ok, why.
M.THEN = {}

-- The party GAINED this item during the case -- counted, not merely present. A presence
-- check would pass on a reliquary that hands over nothing whenever anyone in the party
-- already happens to be carrying one.
M.THEN.gained_item = function(api, id, state)
    local now = M.tally(api.collectedItems())
    local before, after = state.itemsAtStart[id] or 0, now[id] or 0
    if after > before then
        return true
    end
    return false, string.format(
        "item 0x%02X never arrived (%d in the party before, %d after) -- the site was "
        .. "visited, the give-item tail did not run", id, before, after)
end

-- Every visit raised a text box. A wired-but-empty message would hand its gift over in
-- silence and every item assertion would still pass.
M.THEN.spoke = function(api, want, state)
    if want == false then
        return true
    end
    if #state.silent > 0 then
        return false, "these visits paid out in SILENCE (no text box): "
            .. table.concat(state.silent, ", ")
    end
    return true
end

M.THEN.event_flag = function(api, id, state)
    if api.eventFlag(id) then
        return true
    end
    return false, string.format(
        "event id %d never set -- the location's Village macro is still on flag 0, so "
        .. "nothing can count it toward a save-all payout", id)
end

-- ---------------------------------------------------------------- driver

function M.tally(list)
    local n = {}
    for _, id in ipairs(list or {}) do n[id] = (n[id] or 0) + 1 end
    return n
end

-- One-key table -> key, value. A `when`/`then` entry is a single-pair mapping in YAML.
function M.pair(entry)
    if type(entry) ~= "table" then
        return nil, nil, string.format(
            "is %s, not a single-key mapping (write `- spoke: true`, not `- spoke`)",
            type(entry))
    end
    local k, v
    for key, value in pairs(entry) do
        if k ~= nil then return nil, nil, "entry declares more than one key" end
        k, v = key, value
    end
    if k == nil then return nil, nil, "empty entry" end
    return k, v
end

function M.run(case, api)
    local state = {visits = 0, silent = {}, itemsAtStart = {}, asserted = 0}
    local name = case.name or "?"

    for _, want in ipairs(case.given or {}) do
        local fn = M.GIVEN[want]
        if not fn then
            return api.result("ERROR", string.format(
                "%s: unknown `given` %q -- the vocabulary is in cases.lua", name, tostring(want)))
        end
        local ok, why = fn(api, state)
        if not ok then
            return api.result("FAIL", string.format("%s: %s", name, why))
        end
    end

    for i, entry in ipairs(case["when"] or {}) do
        local key, arg, err = M.pair(entry)
        if err then
            return api.result("ERROR", string.format("%s: step %d: %s", name, i, err))
        end
        local fn = M.WHEN[key]
        if not fn then
            return api.result("ERROR", string.format(
                "%s: unknown step %q -- the vocabulary is in cases.lua, and a case outside "
                .. "it belongs behind the chapter's `lua:` key", name, key))
        end
        local ok, why = fn(api, arg, state)
        if not ok then
            return api.result("FAIL", string.format("%s: %s", name, why))
        end
    end

    -- A case that asserts nothing must not report green. It would be counted as coverage by
    -- `make chapter`, by the chapter suite and by the gate, and it proves nothing at all.
    local asserts = case["then"] or {}
    if #asserts == 0 and state.asserted == 0 then
        return api.result("ERROR", string.format(
            "%s: asserts nothing -- no `then` entry and no step carrying its own assertion, "
            .. "so a PASS would mean nothing", name))
    end

    local proved = {}
    for i, entry in ipairs(asserts) do
        local key, arg, err = M.pair(entry)
        if err then
            return api.result("ERROR", string.format("%s: assertion %d: %s", name, i, err))
        end
        local fn = M.THEN[key]
        if not fn then
            return api.result("ERROR", string.format(
                "%s: unknown assertion %q -- the vocabulary is in cases.lua", name, key))
        end
        local ok, why = fn(api, arg, state)
        if not ok then
            return api.result("FAIL", string.format("%s: %s", name, why))
        end
        proved[#proved + 1] = key
    end

    return api.result("PASS", string.format("%s: %s (%d assertion(s) over %d visit(s))",
        name, case.proves or "declared case", #proved + state.asserted, state.visits))
end

return M
