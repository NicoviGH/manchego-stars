-- cases.lua -- the driver for DECLARED playtest cases (#314).
--
-- A chapter YAML declares what its scenarios prove; `tools/playtest/declared.py` emits one
-- case as a Lua table and this runs it. The vocabulary is deliberately small: it covers the
-- shape 15 of the harness's scenarios already share (boot -> settle -> drive -> read
-- memory), and anything outside it stays hand-written Lua behind the chapter's `lua:` key.
-- Code is the exception you NAME, not the default you copy.
--
-- WHY THIS IS ITS OWN CHUNK. Lua allows 200 locals per chunk and `harness.lua` is one chunk
-- whose slots are shared (`check_lua_local_headroom` measures what is left, so no number is
-- written here). A chapter costs ~6-7 of them, so chapters would crowd the harness out. A
-- chapter's Lua lives in its own chunk with its own budget; see decisions.md -> "A chapter costs local slots".
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

-- `arg.gains` is an item id this site must hand over. It rides the STEP because the gift is
-- per-tile: a whole-case "these ids arrived" list passes on four doors swapping each other's
-- gifts, which is exactly the defect ch05reliquaries exists to catch. It is still not
-- positional -- the assertion lives INSIDE the step it belongs to, so inserting a site cannot
-- re-target another site's assertion.
--
-- A SITE is anything the party walks up to and is paid for: a village door (`visit`, the unit
-- stands ON x,y) or a unit it Talks to (`talk`, the unit stands on x,y and Talks its neighbour
-- -- ch06's boarding pass, from a hull's door). Same step, same assertions; only the api call
-- that opens the site differs.
local function siteStep(verb, open)
    return function(api, arg, state)
        if type(arg) ~= "table" or type(arg.x) ~= "number" or type(arg.y) ~= "number" then
            return false, string.format("a `%s` step needs a table with numeric x and y", verb)
        end
        -- Settle FIRST. A site event's tail (give-item, MapChange, EVBIT_T, ENDA) is still
        -- running when the item lands, and walking to the next site while std_event holds the
        -- controller is an illegal input that dies as "cursor could not reach" -- which reads
        -- like a map problem and is an impatience problem.
        if not api.settle(true) then
            return false, string.format(
                "the map never returned to player control before (%d,%d)", arg.x, arg.y)
        end
        local before = M.tally(api.collectedItems())
        local ok, why, spoke = api[open](arg.x, arg.y)
        if not ok then
            return false, string.format("(%d,%d): %s", arg.x, arg.y, tostring(why))
        end
        api.shot(verb)
        state.visits = state.visits + 1
        if arg.gains ~= nil then
            state.asserted = state.asserted + 1
            local after = M.tally(api.collectedItems())
            if (after[arg.gains] or 0) <= (before[arg.gains] or 0) then
                return false, string.format(
                    "%s at (%d,%d) did not hand over item 0x%02X -- this site's OWN gift. "
                    .. "Another site's gift arriving instead still fails here, on purpose",
                    verb, arg.x, arg.y, arg.gains)
            end
        end
        if not spoke then
            state.silent[#state.silent + 1] = string.format("(%d,%d)", arg.x, arg.y)
        end
        return true
    end
end

M.WHEN.visit = siteStep("visit", "visitVillage")

-- `shop: {x, y, kind, stocks}`: a unit stands on the tile, takes the Armory or Vendor command,
-- and the shop that opens must stock exactly `stocks`, in order (item ids). A shop is part of
-- the map (ADR 0345), so this proves a chapter inherited its donor's shop for real: a missing
-- command, a shop that never opens, and a shop wired to the wrong list each fail here.
M.WHEN.shop = function(api, arg, state)
    if type(arg) ~= "table" or type(arg.x) ~= "number" or type(arg.y) ~= "number"
        or (arg.kind ~= "armory" and arg.kind ~= "vendor") or type(arg.stocks) ~= "table" then
        return false, "a `shop` step needs numeric x, y, kind: armory|vendor and a stocks list"
    end
    if not api.settle(true) then
        return false, string.format("the map never returned to player control before (%d,%d)",
            arg.x, arg.y)
    end
    local ok, why, stock = api.shopAt(arg.x, arg.y, arg.kind)
    if not ok then
        return false, string.format("%s at (%d,%d): %s", arg.kind, arg.x, arg.y, tostring(why))
    end
    state.visits = state.visits + 1
    state.asserted = state.asserted + 1
    local function hex(list)
        local out = {}
        for i, id in ipairs(list or {}) do out[i] = string.format("0x%02X", id) end
        return table.concat(out, ", ")
    end
    if hex(stock) ~= hex(arg.stocks) then
        return false, string.format("%s at (%d,%d) stocks [%s], not [%s]",
            arg.kind, arg.x, arg.y, hex(stock), hex(arg.stocks))
    end
    return true
end
M.WHEN.talk = siteStep("talk", "talkFrom")

-- `help: {x, y}`: R on the name of the unit standing on x,y must read the help text its pid is
-- GIVEN (the build's own table, `api.helpFor`), so the words are never copied into the YAML.
-- A unit that still reads its donor slot's vanilla line -- "The army of Grado" under a goblin,
-- #493 -- fails here, and so does a pid the build gives no help text at all.
M.WHEN.help = function(api, arg, state)
    if type(arg) ~= "table" or type(arg.x) ~= "number" or type(arg.y) ~= "number" then
        return false, "a `help` step needs numeric x, y"
    end
    if not api.settle(true) then
        return false, string.format("the map never returned to player control before (%d,%d)",
            arg.x, arg.y)
    end
    local pid = api.pidAt(arg.x, arg.y)
    local want = pid and api.helpFor(pid)
    if not want then
        return false, string.format("(%d,%d) holds %s, which the build gives no help text",
            arg.x, arg.y, pid and string.format("pid 0x%02X", pid) or "no unit")
    end
    local ok, got = api.helpAt(arg.x, arg.y, want.msg)
    if not ok then return false, string.format("help at (%d,%d): %s", arg.x, arg.y, got) end
    state.asserted = state.asserted + 1
    if got.msg ~= want.msg or got.line1 ~= want.line1 then
        return false, string.format("help at (%d,%d) reads MSG_%03X %q, want MSG_%03X %q",
            arg.x, arg.y, got.msg, got.line1, want.msg, want.line1)
    end
    return true
end

-- `idle: {phases, hold, until}`: give the turns back. End the player phase and ride out the
-- enemy's, `phases` times, never acting -- how a case hands a site to the raiders. `hold: true`
-- refills every blue unit to full HP before each phase, because a party deployed across the raid's
-- path is routed by an honest idle before the question is answered (ch02raid's first run died
-- on turn 11), and whether the party SURVIVES is a balance question for `make difficulty` and
-- the human pass, not for a wiring test. `until: raided` stops at the first phase after which
-- a site the case's `raided` assertion watches has fallen; without it every phase is spent.
M.WHEN.idle = function(api, arg, state)
    if type(arg) ~= "table" or type(arg.phases) ~= "number" or arg.phases < 1 then
        return false, "an `idle` step needs a positive numeric `phases`"
    end
    if arg.hold ~= nil and type(arg.hold) ~= "boolean" then
        return false, string.format("`idle`'s `hold` is true or false, not %q", tostring(arg.hold))
    end
    local stop = arg["until"]
    if stop ~= nil and stop ~= "raided" then
        return false, string.format("`idle` can stop only `until: raided`, not %q", tostring(stop))
    end
    if stop == "raided" and #state.raidSites == 0 then
        return false, "`idle` waits `until: raided`, but the case declares no `raided` assertion"
    end
    for p = 1, arg.phases do
        if arg.hold then api.holdParty() end
        local phase = api.enemyPhase()
        if phase == nil then
            return false, string.format("the enemy phase never returned (idle phase %d)", p)
        end
        if phase == "gameover" then
            api.shot("idle-gameover")
            return false, string.format("the party died on turn %d%s", api.turn(),
                arg.hold and " even while held" or "")
        end
        if phase == "ended" then
            return false, string.format("the chapter ended during idle phase %d", p)
        end
        state.idled = state.idled + 1
        if stop == "raided" and M.fallen(api, state)[1] then return true end
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
        return false, "these sites paid out in SILENCE (no text box): "
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

-- `raided: [village id, ...]`: a raider SACKED one of these sites. At least one must have
-- fallen, and every one that did must have cost its gift and left its event id unset. Which
-- one falls is a real design answer (ch02's band took the east hut, not the south one the
-- first draft presumed), so the case names every site it accepts and the log says which.
--
-- The verdict is the TERRAIN, because terrain is what FE8 itself reads: CanUnitVisit
-- (bmmenu.c) and gTerrainList_LootableVillages (cp_utility.c) both decide from it, so a site
-- that has become RUINS is one the player cannot enter and a second raider will not revisit.
-- The event id staying UNSET is the other half: TILE_COMMAND_20 changes the tile and sets
-- nothing (eventinfo.c), which is why a sacked site cannot count toward a save-all payout.
-- The sites are resolved and checked to be villages right after `given` (M.watchRaids), so
-- a site that never stood fails as that rather than as "nothing fell".
M.THEN.raided = function(api, _ids, state)
    local fell = M.fallen(api, state)
    if not fell[1] then
        api.shot("raided-unraided")
        local standing = {}
        for _, site in ipairs(state.raidSites) do
            standing[#standing + 1] = string.format("%s 0x%02X", site.name,
                api.terrainAt(site.x, site.y))
        end
        return false, string.format(
            "%d enemy phase(s) and every watched site still stands (%s) -- no raider reached "
            .. "one, so the raid the chapter declares does not exist", state.idled,
            table.concat(standing, ", "))
    end
    -- Camera on the site before the shot: the verdict is a terrain byte, and a terrain byte has
    -- been right while the tiles it names drew wrong. The frame shows the ruin replaced it.
    api.showTile(fell[1].x, fell[1].y)
    api.shot("raided")
    local now = M.tally(api.collectedItems())
    for _, site in ipairs(fell) do
        api.log(string.format("raided: %s fell by turn %d", site.name, api.turn()))
        local before = state.itemsAtStart[site.gift or -1] or 0
        if site.gift and (now[site.gift] or 0) > before then
            return false, string.format(
                "%s was sacked but its gift 0x%02X reached the party anyway (%d -> %d) -- a "
                .. "lost site must cost its gift", site.name, site.gift, before, now[site.gift])
        end
        if api.eventFlag(site.flag) then
            return false, string.format(
                "%s was RAIDED but its event id %d is set -- a sacked site would still pay out",
                site.name, site.flag)
        end
    end
    return true
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

-- FE8's own terrain ids (terrains.h), not any chapter's: a raid turns a VILLAGE into RUINS.
M.VILLAGE, M.RUINS = 0x03, 0x25

-- Resolve the case's `raided` sites once the map is up, and refuse a site that is not a
-- village now: nothing can raid it and nothing can visit it, so "it never fell" would blame
-- the raiders for a tile the chapter never built. "Up" is `on_map`'s settle, the same
-- event wait (INSPECT.settle "event", 6000) the hand-written raids opened with.
-- Returns ok, verdict, why: a malformed list or an unknown id is the AUTHOR's error (ERROR,
-- like an unknown step); a site that is not a village is the CHAPTER's (FAIL).
function M.watchRaids(case, api, state)
    for _, entry in ipairs(case["then"] or {}) do
        local key, ids = M.pair(entry)
        if key == "raided" then
            if type(ids) ~= "table" or #ids == 0 then
                return false, "ERROR", "`raided` takes a list of village ids"
            end
            for _, id in ipairs(ids) do
                local site = api.village(id)
                if not site then
                    return false, "ERROR", string.format("`raided` names %q, which CAMPAIGN.VILLAGES "
                        .. "does not carry", tostring(id))
                end
                local terrain = api.terrainAt(site.x, site.y)
                if terrain ~= M.VILLAGE then
                    return false, "FAIL", string.format(
                        "%s (%d,%d) is terrain 0x%02X before the raid, not a village -- nothing "
                        .. "can raid it and nothing can visit it", id, site.x, site.y, terrain)
                end
                state.raidSites[#state.raidSites + 1] = {name = id, x = site.x, y = site.y,
                                                         flag = site.flag, gift = site.gift}
            end
        end
    end
    return true
end

-- The watched sites that are RUINS now, in the order the case named them.
function M.fallen(api, state)
    local out = {}
    for _, site in ipairs(state.raidSites) do
        if api.terrainAt(site.x, site.y) == M.RUINS then out[#out + 1] = site end
    end
    return out
end

function M.run(case, api)
    local state = {visits = 0, silent = {}, itemsAtStart = {}, asserted = 0, raidSites = {},
                   idled = 0}
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
    local watching, verdict, why = M.watchRaids(case, api, state)
    if not watching then
        return api.result(verdict, string.format("%s: %s", name, why))
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
