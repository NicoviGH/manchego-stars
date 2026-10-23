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
--   units = { { id, slot, faction, charId, classId, x, y, onMap, hp, maxhp, level, state,
--               dead, acted, items = { {id, uses}... }, minRange, maxRange, isBoss,
--               addr, pow, def }... } }
-- `slot` is the 0-based index into the faction's array; `id` is the unit's own index byte
-- (struct Unit +0x0B: blue 0x01.., green 0x41.., red 0x81..), unique across factions.
-- `addr`, `pow`, `def` are carried for harness.lua's unitAt callers.
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
Board.US_UNSELECTABLE = 1 << 1  -- "has acted this phase" (include/bmunit.h)
Board.US_DEAD = 1 << 2          -- include/bmunit.h
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
local PHASE = { [0x00] = "blue", [0x40] = "green", [0x80] = "red" }

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

-- One array slot as a unit table, or nil when the slot is empty (no character pointer).
-- `faction` is derived from `base` when it is one of the three arrays.
function Board.unitAt(mem, SYM, base, slot)
    local a = base + slot * Board.UNIT_SIZE
    local chptr = mem.u32(a)
    if chptr == 0 then return nil end
    local clptr = mem.u32(a + 0x04)
    local state = mem.u32(a + 0x0C)
    -- xPos/yPos are s8, and FE8 parks a unit that is NOT on the map at -1. Read unsigned,
    -- that unit reported x=255 and the clear-bot drove the cursor at (255,8) (#335).
    local x, y = mem.s8(a + 0x10), mem.s8(a + 0x11)
    local items = {}
    for k = 0, ITEM_COUNT - 1 do
        local raw = mem.u16(a + 0x1E + k * 2)
        if (raw & 0xFF) ~= 0 then items[#items + 1] = { id = raw & 0xFF, uses = raw >> 8 } end
    end
    local mn, mx = Board.attackRange(mem, SYM, a)
    return {
        addr = a, slot = slot, faction = factionOf(SYM, base),
        id = mem.u8(a + 0x0B),
        charId = mem.u8(chptr + 0x04),
        classId = clptr ~= 0 and mem.u8(clptr + 0x04) or nil,
        x = x, y = y, onMap = x >= 0 and y >= 0,
        hp = mem.u8(a + 0x13), maxhp = mem.u8(a + 0x12),
        -- +08 level, +12 maxHP, +14 pow, +17 def: the difficulty shift re-projects these, so
        -- they are what a mode probe reads.
        level = mem.u8(a + 0x08), pow = mem.u8(a + 0x14), def = mem.u8(a + 0x17),
        state = state,
        dead = (state & Board.US_DEAD) ~= 0,
        acted = (state & Board.US_UNSELECTABLE) ~= 0,
        items = items, minRange = mn, maxRange = mx,
        isBoss = Board.isBoss(mem, a),
    }
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
    return {
        turn = mem.u16(SYM.gPlaySt + 0x10),
        phase = PHASE[mem.u8(SYM.gPlaySt + 0x0F)],
        map = { w = mem.u16(SYM.gBmMapSize), h = mem.u16(SYM.gBmMapSize + 2) },
        units = units,
    }
end

-- Is a live unit of any faction standing on (x, y)? A lean scan (pointer, state, x, y per
-- slot) rather than Board.read, because callers ask it once per tile of a movement range.
-- Not gBmMapUnit: under fog the engine leaves a hidden red unit OFF that map
-- (bmmap.c RefreshUnitsOnBmMap), and a destination picker must still not walk into it.
function Board.occupied(mem, SYM, x, y)
    for _, f in ipairs(Board.FACTIONS) do
        local base = SYM[f.sym]
        for slot = 0, f.count - 1 do
            local a = base + slot * Board.UNIT_SIZE
            if mem.u32(a) ~= 0 and mem.s8(a + 0x10) == x and mem.s8(a + 0x11) == y
                and (mem.u32(a + 0x0C) & Board.US_DEAD) == 0 then
                return true
            end
        end
    end
    return false
end

-- The first unit of `faction` with `charId`, or nil. Generics SHARE a charId: use `slot`.
function Board.unit(board, faction, charId)
    for _, u in ipairs(board.units) do
        if u.faction == faction and u.charId == charId then return u end
    end
    return nil
end

-- `faction`'s units that are not dead, in array order. Off-map units are included: being
-- alive and being on the map are separate questions, and `onMap` answers the second.
function Board.live(board, faction)
    local out = {}
    for _, u in ipairs(board.units) do
        if u.faction == faction and not u.dead then out[#out + 1] = u end
    end
    return out
end

-- The reader with its memory and symbols bound, for harness.lua: one top-level local there
-- instead of one per helper (the chunk sits near Lua's 200-local ceiling, #327).
function Board.bind(mem, SYM)
    return {
        read = function() return Board.read(mem, SYM) end,
        unitAt = function(base, slot) return Board.unitAt(mem, SYM, base, slot) end,
        attackRange = function(addr) return Board.attackRange(mem, SYM, addr) end,
        isBoss = function(addr) return Board.isBoss(mem, addr) end,
        occupied = function(x, y) return Board.occupied(mem, SYM, x, y) end,
        unit = Board.unit, live = Board.live,
        UNIT_SIZE = Board.UNIT_SIZE, US_DEAD = Board.US_DEAD,
        ITEMDATA_STRIDE = Board.ITEMDATA_STRIDE,
    }
end

return Board
