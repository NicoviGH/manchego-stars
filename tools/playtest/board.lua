-- board.lua -- the ONE reader of FE8's board state (#510 step 9).
--
-- Before this file the board had three shapes: harness.lua's unitAt, the clear scenario's
-- enemy tables (fed to clearbot.lua) and llmExportBoard (fed to llm_player.py), each with its
-- own scan bounds and its own copy of the item/boss reads. The bots built on top of it need
-- one answer to "what is on the map", so it is read here, once, into plain tables.
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
-- of live lookup by character id (harness findUnit/blue/red); Board.unit is its snapshot twin.
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

-- The reader with its memory and symbols bound, for harness.lua: one top-level local there
-- instead of one per helper.
function Board.bind(mem, SYM)
    return {
        read = function() return Board.read(mem, SYM) end,
        header = function() return Board.header(mem, SYM) end,
        unitAt = function(base, slot) return Board.unitAt(mem, SYM, base, slot) end,
        leanAt = function(base, slot) return Board.leanAt(mem, SYM, base, slot) end,
        leanList = function(faction) return Board.leanList(mem, SYM, faction) end,
        liveCount = function(faction) return Board.liveCount(mem, SYM, faction) end,
        liveBoss = function() return Board.liveBoss(mem, SYM) end,
        findIn = function(base, count, charId) return Board.findIn(mem, SYM, base, count, charId) end,
        attackRange = function(addr) return Board.attackRange(mem, SYM, addr) end,
        isBoss = function(addr) return Board.isBoss(mem, addr) end,
        occupied = function(x, y) return Board.occupied(mem, SYM, x, y) end,
        lordPid = function(flagSet) return Board.lordPid(mem, SYM, flagSet) end,
        canSeize = Board.canSeize,
        unit = Board.unit, at = Board.at, live = Board.live, inPhase = Board.inPhase,
        UNIT_SIZE = Board.UNIT_SIZE, US_DEAD = Board.US_DEAD,
        ITEMDATA_STRIDE = Board.ITEMDATA_STRIDE,
    }
end

return Board
