-- board.lua -- the ONE reader of FE8's board state (#510 step 9).
--
-- Before this file the board had three shapes: harness.lua's unitAt, the clear scenario's
-- enemy tables (fed to the greedy core, now in bot.lua) and llmExportBoard (fed to
-- llm_player.py), each with its own scan bounds and its own copy of the item/boss reads. The
-- bots built on top of it need one answer to "what is on the map", so it is read here, once,
-- into plain tables.
--
-- Pure: memory comes in as `mem = { u8, s8, u16, u32 }` (address -> value), so
-- test_board.lua runs it over a table-backed fake with no emulator. Addresses come from SYM.
--
-- Board.read(mem, SYM) -> {
--   turn, phase = "blue"|"green"|"red", map = { w, h },
--   units = { { id, slot, faction, charId, classId, x, y, onMap, onField, hp, maxhp, level,
--               state, dead, acted, items = { {id, uses}... }, minRange, maxRange, isBoss,
--               addr, pow, def }... } }
-- `slot` is the 0-based index into the faction's array; `id` is the unit's own index byte
-- (struct Unit +0x0B: blue 0x01.., green 0x41.., red 0x81..), unique across factions.
-- `onMap` = a real tile (FE8 parks an off-map unit at -1); `onField` = onMap AND not hidden,
-- rescued or undeployed AND not dead -- a body that stands on its tile and can be fought.
--
-- Two read widths, on purpose. Board.read / Board.unitAt are the FULL read (items, weapon
-- reach, boss attribute): a snapshot a decision is made from. Board.leanAt and the scans built
-- on it read only position/hp/state, because harness.lua calls them from per-frame waits and
-- per-tile loops, where the full read multiplied by every frame is what made tooling slow.
--
-- Offsets, from the decomp headers:
--   include/bmunit.h struct Unit (0x48 bytes): +00 pCharacterData, +04 pClassData,
--     +08 s8 level, +0B s8 index, +0C u32 state, +10/+11 s8 xPos/yPos, +12 maxHP, +13 curHP,
--     +14 pow, +17 def, +1E u16 items[5] (low byte id, high byte uses)
--   CharacterData +04 number, +28 attributes; ClassData +04 number
--   include/bmitem.h struct ItemData (stride 0x24): +08 attributes, +19 encodedRange
--   include/types.h struct PlaySt: +0F faction (0x00/0x40/0x80), +10 u16 turn
--   include/bmmap.h gBmMapSize: struct Vec2 { s16 x, y }

local Board = {}

Board.UNIT_SIZE = 0x48
-- Unit state bits, include/bmunit.h.
Board.US_HIDDEN = 1 << 0
Board.US_UNSELECTABLE = 1 << 1  -- "has acted this phase"
Board.US_DEAD = 1 << 2
Board.US_NOT_DEPLOYED = 1 << 3
Board.US_RESCUED = 1 << 5
local OFF_FIELD = Board.US_HIDDEN | Board.US_NOT_DEPLOYED | Board.US_RESCUED | Board.US_DEAD
Board.CA_BOSS = 1 << 15         -- include/bmunit.h, a CHARACTER attribute here
Board.ITEMDATA_STRIDE = 0x24
local IA_WEAPON = 1 << 0
local ITEM_COUNT = 5

-- Array bounds are the DECOMP's (bmunit.h: blue[62] / red[50] / green[20]), never the
-- roster of the day: `blue` once searched 8 for as long as the cast WAS 8, and missed a
-- deployed unit the day the cast grew. The arrays are contiguous, so a bound past these
-- reads the next faction's units as this one's.
Board.FACTIONS = {
    { name = "blue", sym = "gUnitArrayBlue", count = 62 },
    { name = "red", sym = "gUnitArrayRed", count = 50 },
    { name = "green", sym = "gUnitArrayGreen", count = 20 },
}
local BY_NAME = {}
for _, f in ipairs(Board.FACTIONS) do BY_NAME[f.name] = f end
local PHASE = { [0x00] = "blue", [0x40] = "green", [0x80] = "red" }

local function onFieldState(state, x, y)
    return x >= 0 and y >= 0 and (state & OFF_FIELD) == 0
end

-- Attack reach from the item in items[0] -- FE8 keeps the equipped weapon there -- as
-- (minRange, maxRange), or nil for a staff / non-weapon (IA_WEAPON unset) or empty hand.
function Board.attackRange(mem, SYM, addr)
    local item = mem.u16(addr + 0x1E) & 0xFF
    if item == 0 then return nil end
    local data = SYM.gItemData + item * Board.ITEMDATA_STRIDE
    if (mem.u32(data + 0x08) & IA_WEAPON) == 0 then return nil end
    local er = mem.u8(data + 0x19)
    return er >> 4, er & 0xF
end

-- The unit's CHARACTER carries CA_BOSS (named bosses). The class attribute is not read:
-- the clear-bot has always meant "this chapter's named boss", not "a boss-class unit".
function Board.isBoss(mem, addr)
    local chptr = mem.u32(addr)
    if chptr == 0 then return false end
    return (mem.u32(chptr + 0x28) & Board.CA_BOSS) ~= 0
end

local function factionOf(SYM, base)
    for _, f in ipairs(Board.FACTIONS) do
        if SYM[f.sym] == base then return f.name end
    end
    return nil
end

-- LEAN: one array slot's position/hp/state, or nil when the slot is empty (no character
-- pointer). `faction` is derived from `base` when it is one of the three arrays.
function Board.leanAt(mem, SYM, base, slot)
    local a = base + slot * Board.UNIT_SIZE
    local chptr = mem.u32(a)
    if chptr == 0 then return nil end
    local state = mem.u32(a + 0x0C)
    -- xPos/yPos are s8, and FE8 parks a unit that is NOT on the map at -1. Read unsigned,
    -- that unit reported x=255 and the clear-bot drove the cursor at (255,8) (#335).
    local x, y = mem.s8(a + 0x10), mem.s8(a + 0x11)
    return {
        addr = a, slot = slot, faction = factionOf(SYM, base),
        charId = mem.u8(chptr + 0x04),
        x = x, y = y, onMap = x >= 0 and y >= 0, onField = onFieldState(state, x, y),
        hp = mem.u8(a + 0x13), maxhp = mem.u8(a + 0x12),
        -- +08 level, +12 maxHP, +14 pow, +17 def: the difficulty shift re-projects these, so
        -- they are what a mode probe reads.
        level = mem.u8(a + 0x08), pow = mem.u8(a + 0x14), def = mem.u8(a + 0x17),
        state = state,
        dead = (state & Board.US_DEAD) ~= 0,
        acted = (state & Board.US_UNSELECTABLE) ~= 0,
    }
end

-- FULL: the lean read plus index, class, items, weapon reach and boss attribute.
function Board.unitAt(mem, SYM, base, slot)
    local u = Board.leanAt(mem, SYM, base, slot)
    if not u then return nil end
    local a = u.addr
    local clptr = mem.u32(a + 0x04)
    local items = {}
    for k = 0, ITEM_COUNT - 1 do
        local raw = mem.u16(a + 0x1E + k * 2)
        if (raw & 0xFF) ~= 0 then items[#items + 1] = { id = raw & 0xFF, uses = raw >> 8 } end
    end
    u.id = mem.u8(a + 0x0B)
    u.classId = clptr ~= 0 and mem.u8(clptr + 0x04) or nil
    u.items = items
    u.minRange, u.maxRange = Board.attackRange(mem, SYM, a)
    u.isBoss = Board.isBoss(mem, a)
    return u
end

function Board.header(mem, SYM)
    return { turn = mem.u16(SYM.gPlaySt + 0x10), phase = PHASE[mem.u8(SYM.gPlaySt + 0x0F)] }
end

function Board.read(mem, SYM)
    local units = {}
    for _, f in ipairs(Board.FACTIONS) do
        local base = SYM[f.sym]
        for slot = 0, f.count - 1 do
            local u = Board.unitAt(mem, SYM, base, slot)
            if u then units[#units + 1] = u end
        end
    end
    local board = Board.header(mem, SYM)
    board.map = { w = mem.u16(SYM.gBmMapSize), h = mem.u16(SYM.gBmMapSize + 2) }
    board.units = units
    return board
end

-- Is the player phase of turn `phaseTurn` still the one running? False once FE8 has moved on
-- -- to another faction's phase, or to a LATER player phase. A bare "player map is idle" cannot
-- tell turn N's player phase from turn N+1's, and acting on that confusion ends a fresh turn
-- with nobody moved. `header` is Board.header's (or a board's) {turn, phase}.
function Board.inPhase(header, phaseTurn)
    return header.phase == "blue" and header.turn == phaseTurn
end

-- Every occupied slot of `faction`, LEAN, in array order (dead ones included: filter).
function Board.leanList(mem, SYM, faction)
    local f, out = BY_NAME[faction], {}
    local base = SYM[f.sym]
    for slot = 0, f.count - 1 do
        local u = Board.leanAt(mem, SYM, base, slot)
        if u then out[#out + 1] = u end
    end
    return out
end

-- Iterator over `faction`'s occupied slots at the decomp bound: `for slot, u in Board.each(...)`.
-- LEAN and LAZY -- each unit is read when the loop reaches it, not up front -- so a scenario
-- that kills or moves units as it goes sees the live board on the next turn of the loop, as
-- the `for i = 0, N do unitAt(base, i)` it replaces did. Empty slots are skipped.
function Board.each(mem, SYM, faction)
    local f = BY_NAME[faction]
    local base, slot = SYM[f.sym], -1
    return function()
        while true do
            slot = slot + 1
            if slot >= f.count then return nil end
            local u = Board.leanAt(mem, SYM, base, slot)
            if u then return slot, u end
        end
    end
end

-- How many of `faction`'s units are on the field (alive, on a tile, not hidden/rescued/
-- undeployed). Leaner than leanAt: a per-frame stop condition calls it.
function Board.liveCount(mem, SYM, faction)
    local f, n = BY_NAME[faction], 0
    local base = SYM[f.sym]
    for slot = 0, f.count - 1 do
        local a = base + slot * Board.UNIT_SIZE
        if mem.u32(a) ~= 0
            and onFieldState(mem.u32(a + 0x0C), mem.s8(a + 0x10), mem.s8(a + 0x11)) then
            n = n + 1
        end
    end
    return n
end

-- The first on-field red unit whose character carries CA_BOSS, LEAN, or nil.
function Board.liveBoss(mem, SYM)
    local base = SYM.gUnitArrayRed
    for slot = 0, BY_NAME.red.count - 1 do
        local a = base + slot * Board.UNIT_SIZE
        -- On-field first: it is three reads, the boss attribute two more through a pointer.
        if mem.u32(a) ~= 0
            and onFieldState(mem.u32(a + 0x0C), mem.s8(a + 0x10), mem.s8(a + 0x11))
            and Board.isBoss(mem, a) then
            return Board.leanAt(mem, SYM, base, slot)
        end
    end
    return nil
end

-- Is an on-field unit of any faction standing on (x, y)? Callers ask once per tile of a
-- movement range, so it reads pointer, x, y and state only.
-- Not gBmMapUnit: under fog the engine leaves a hidden red unit OFF that map
-- (bmmap.c RefreshUnitsOnBmMap), and a destination picker must still not walk into it.
function Board.occupied(mem, SYM, x, y)
    for _, f in ipairs(Board.FACTIONS) do
        local base = SYM[f.sym]
        for slot = 0, f.count - 1 do
            local a = base + slot * Board.UNIT_SIZE
            if mem.u32(a) ~= 0 and mem.s8(a + 0x10) == x and mem.s8(a + 0x11) == y
                and onFieldState(mem.u32(a + 0x0C), x, y) then
                return true
            end
        end
    end
    return false
end

-- The first unit with `charId` in the `count` slots from `base`, LEAN, or nil. The one owner
-- of live lookup by character id (harness blue/red via Board.find); Board.unit is its snapshot twin.
function Board.findIn(mem, SYM, base, count, charId)
    for slot = 0, count - 1 do
        local a = base + slot * Board.UNIT_SIZE
        local chptr = mem.u32(a)
        if chptr ~= 0 and mem.u8(chptr + 0x04) == charId then
            return Board.leanAt(mem, SYM, base, slot)
        end
    end
    return nil
end

-- The first unit of `faction` with `charId`, over that faction's whole decomp array, LEAN, or
-- nil. A literal count at the call site is how a scan stopped at slot 19 or 23 (#531 audit 13).
function Board.find(mem, SYM, faction, charId)
    local f = BY_NAME[faction]
    return Board.findIn(mem, SYM, SYM[f.sym], f.count, charId)
end

-- Who can Seize. FE8's Seize command is usable only when CanUnitSeize(unit) holds
-- (bmmenu.c UnitActionMenu_CanSeize), and our engine patch 0005 rewrites that test to
-- `unit->pCharacterData->number == LordSelect_GetPid()` (bmdifficulty.c). LordSelect_GetPid
-- (eventinfo.c, same patch) returns the first gLordSelectCandidates[i] -- a u16 table ended by
-- 0xFFFF -- whose permanent flag LORDSEL_FLAG_BASE + i is set, else candidate 0. This mirrors
-- that read. `flagSet(flag)` is the caller's event-flag test (harness eventFlag), so the flag
-- encoding keeps one owner. nil when the build has no candidate table: then the caller can only
-- learn who cannot Seize by trying (Board.canSeize's ruledOut memo).
Board.LORDSEL_FLAG_BASE = 0xF0   -- tools/inject/decomp.py LORDSEL_FLAG_BASE (pinned by a test)
local MAX_LORD_CANDIDATES = 64   -- a bound for a corrupt table, far above any cast
function Board.lordPid(mem, SYM, flagSet)
    local base = SYM.gLordSelectCandidates
    if not base then return nil end
    for i = 0, MAX_LORD_CANDIDATES - 1 do
        local pid = mem.u16(base + i * 2)
        if pid == 0xFFFF then break end
        if flagSet(Board.LORDSEL_FLAG_BASE + i) then return pid end
    end
    return mem.u16(base)
end

-- Can `unit` Seize? Decided up front from the lord's pid when it is known; otherwise only the
-- memo of units that stood on the tile without a Seize command (ruledOut[slot]) says no.
function Board.canSeize(unit, lordPid, ruledOut)
    if lordPid then return unit.charId == lordPid end
    return not (ruledOut and ruledOut[unit.slot])
end

-- Snapshot lookups over a Board.read result.
-- The first unit of `faction` with `charId`, or nil. Generics SHARE a charId: use Board.at.
function Board.unit(board, faction, charId)
    for _, u in ipairs(board.units) do
        if u.faction == faction and u.charId == charId then return u end
    end
    return nil
end

function Board.at(board, faction, slot)
    for _, u in ipairs(board.units) do
        if u.faction == faction and u.slot == slot then return u end
    end
    return nil
end

-- `faction`'s units that are not dead, in array order. Off-field units are included: being
-- alive and standing on the field are separate questions, and `onField` answers the second.
function Board.live(board, faction)
    local out = {}
    for _, u in ipairs(board.units) do
        if u.faction == faction and not u.dead then out[#out + 1] = u end
    end
    return out
end

-- ---- placing a unit (#531 audit 4) ----------------------------------------------------
-- Pure over `io = { rs8(a), write8(a, v), grid(x, y), setGrid(x, y, v) }` so test_board.lua runs
-- it with no emulator. The map's size comes in as an ARGUMENT, read live by the caller: six
-- copies of this dance carried the literal `tx <= 24 and ty <= 15` from a bigger chapter, and
-- on ch03's 17x16 map an off-map tile reads gBmMapUnit's zero border as "empty" and was
-- accepted.
function Board.inMap(x, y, w, h)
    return x >= 0 and x < w and y >= 0 and y < h
end

-- Stand the unit at `addr` on (x, y) and keep the tile->unit grid in step: vacate its old tile,
-- write the new position, occupy the new tile. Returns true, or false + the reason when (x, y)
-- is off the map (nothing is touched then). `o.grid` overrides the id written to the new tile
-- (default: the id read live from the unit's old tile, which preserves faction bits);
-- `o.vacate == false` skips clearing the old tile (a unit that was never on the grid).
-- `o.tracked` also refuses, touching nothing, when the id to write is 0: the default read finds
-- the old tile empty in the grid (or the unit off the map), so the move would leave the new tile
-- reading "empty" and the engine unable to select the unit there. The teleports always refused
-- that case; a site that places a unit the grid does not hold yet leaves it off.
function Board.place(io, addr, x, y, w, h, o)
    o = o or {}
    if not Board.inMap(x, y, w, h) then
        return false, string.format("tile (%d,%d) is off the %dx%d map", x, y, w, h)
    end
    local ox, oy = io.rs8(addr + 0x10), io.rs8(addr + 0x11)
    local was = Board.inMap(ox, oy, w, h)
    local grid = o.grid
    if grid == nil then grid = was and io.grid(ox, oy) or 0 end
    if o.tracked and grid == 0 then
        return false, string.format("the unit at (%d,%d) is not tracked in the grid", ox, oy)
    end
    if o.vacate ~= false and was then io.setGrid(ox, oy, 0) end
    io.write8(addr + 0x10, x); io.write8(addr + 0x11, y)
    io.setGrid(x, y, grid)
    return true
end

-- The first tile beside (ax, ay), taken in `order` (a list of { dx, dy }), that is on the map and
-- empty in the grid and passes `ok(x, y)` when given. Returns x, y or nil.
function Board.freeBeside(io, ax, ay, order, w, h, ok)
    for _, d in ipairs(order) do
        local tx, ty = ax + d[1], ay + d[2]
        if Board.inMap(tx, ty, w, h) and io.grid(tx, ty) == 0 and (not ok or ok(tx, ty)) then
            return tx, ty
        end
    end
    return nil
end

-- The reader with its memory and symbols bound, for harness.lua: one top-level local there
-- instead of one per helper.
function Board.bind(mem, SYM)
    return {
        read = function() return Board.read(mem, SYM) end,
        header = function() return Board.header(mem, SYM) end,
        unitAt = function(base, slot) return Board.unitAt(mem, SYM, base, slot) end,
        leanAt = function(base, slot) return Board.leanAt(mem, SYM, base, slot) end,
        each = function(faction) return Board.each(mem, SYM, faction) end,
        leanList = function(faction) return Board.leanList(mem, SYM, faction) end,
        liveCount = function(faction) return Board.liveCount(mem, SYM, faction) end,
        liveBoss = function() return Board.liveBoss(mem, SYM) end,
        findIn = function(base, count, charId) return Board.findIn(mem, SYM, base, count, charId) end,
        find = function(faction, charId) return Board.find(mem, SYM, faction, charId) end,
        attackRange = function(addr) return Board.attackRange(mem, SYM, addr) end,
        isBoss = function(addr) return Board.isBoss(mem, addr) end,
        occupied = function(x, y) return Board.occupied(mem, SYM, x, y) end,
        lordPid = function(flagSet) return Board.lordPid(mem, SYM, flagSet) end,
        canSeize = Board.canSeize,
        inMap = Board.inMap, place = Board.place, freeBeside = Board.freeBeside,
        unit = Board.unit, at = Board.at, live = Board.live, inPhase = Board.inPhase,
        UNIT_SIZE = Board.UNIT_SIZE, US_DEAD = Board.US_DEAD,
        ITEMDATA_STRIDE = Board.ITEMDATA_STRIDE,
    }
end

return Board
