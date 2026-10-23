-- Tests for board.lua -- the one board reader (#510 step 9), over a table-backed fake
-- memory, so no emulator. Run: lua tools/playtest/test_board.lua
local here = (arg[0]:match("(.*/)")) or "./"
local Board = dofile(here .. "board.lua")

local tests, fails = 0, 0
local function check(got, want, msg)
    tests = tests + 1
    if got ~= want then
        fails = fails + 1
        print(string.format("FAIL: %s\n  got  %s\n  want %s", msg, tostring(got), tostring(want)))
    end
end

-- The real layout: the three unit arrays are contiguous (blue[62] then red[50] then
-- green[20]), which is what makes a wrong bound read the NEXT faction's units.
local SYM = {
    gPlaySt = 0x0202BCF0,
    gUnitArrayBlue = 0x0202BE4C,
    gUnitArrayRed = 0x0202BE4C + 62 * 0x48,
    gUnitArrayGreen = 0x0202BE4C + (62 + 50) * 0x48,
    gItemData = 0x08840B20,
    gBmMapSize = 0x0202E4D4,
}

local function fakeMem()
    local bytes = {}
    local m = {}
    function m.u8(a) return bytes[a] or 0 end
    function m.s8(a) local v = m.u8(a); return v >= 0x80 and v - 0x100 or v end
    function m.u16(a) return m.u8(a) | (m.u8(a + 1) << 8) end
    function m.u32(a) return m.u16(a) | (m.u16(a + 2) << 16) end
    function m.w8(a, v) bytes[a] = v & 0xFF end
    function m.w16(a, v) m.w8(a, v); m.w8(a + 1, v >> 8) end
    function m.w32(a, v) m.w16(a, v); m.w16(a + 2, v >> 16) end
    return m
end

local CHAR_BASE, CLASS_BASE = 0x08800000, 0x08810000
local IA_WEAPON = 0x1
-- item ids used below: 1 = iron sword (1-1), 2 = bow (2-2), 3 = heal staff (no IA_WEAPON)
local function defineItems(m)
    local function item(id, attrs, minR, maxR)
        local d = SYM.gItemData + id * 0x24
        m.w32(d + 0x08, attrs)
        m.w8(d + 0x19, (minR << 4) | maxR)
    end
    item(1, IA_WEAPON, 1, 1)
    item(2, IA_WEAPON, 2, 2)
    item(3, 0x4, 1, 1)
end

-- Put a unit in `faction`'s array at `slot`. o: charId, classId, x, y, hp, maxhp, level,
-- state, items = {{id,uses}...}, charAttrs.
local function putUnit(m, base, slot, o)
    local a = base + slot * 0x48
    local ch = CHAR_BASE + (o.charId or 1) * 0x34
    local cl = CLASS_BASE + (o.classId or 1) * 0x54
    m.w8(ch + 0x04, o.charId or 1)
    m.w32(ch + 0x28, o.charAttrs or 0)
    m.w8(cl + 0x04, o.classId or 1)
    m.w32(a + 0x00, ch)
    m.w32(a + 0x04, cl)
    m.w8(a + 0x08, o.level or 1)
    m.w8(a + 0x0B, o.index or 0)
    m.w32(a + 0x0C, o.state or 0)
    m.w8(a + 0x10, o.x or 0)
    m.w8(a + 0x11, o.y or 0)
    m.w8(a + 0x12, o.maxhp or 20)
    m.w8(a + 0x13, o.hp or 20)
    for k, it in ipairs(o.items or {}) do m.w16(a + 0x1E + (k - 1) * 2, it[1] | (it[2] << 8)) end
end

local function board(setup)
    local m = fakeMem()
    defineItems(m)
    m.w8(SYM.gPlaySt + 0x0F, 0x80)
    m.w16(SYM.gPlaySt + 0x10, 3)
    m.w16(SYM.gBmMapSize, 25)
    m.w16(SYM.gBmMapSize + 2, 16)
    setup(m)
    return Board.read({ u8 = m.u8, s8 = m.s8, u16 = m.u16, u32 = m.u32 }, SYM)
end

-- A blue unit parked off the map (FE8 writes x = -1) reads onMap = false, x = -1.
do
    local b = board(function(m)
        putUnit(m, SYM.gUnitArrayBlue, 0, { charId = 5, x = -1, y = -1, items = { { 1, 40 } } })
    end)
    local u = Board.unit(b, "blue", 5)
    check(u ~= nil, true, "off-map blue unit is still on the board")
    check(u and u.onMap, false, "x = -1 reads onMap = false")
    check(u and u.x, -1, "x reads signed")
end

-- A red unit whose character carries CA_BOSS reads isBoss = true; a generic does not.
do
    local b = board(function(m)
        putUnit(m, SYM.gUnitArrayRed, 0, { charId = 0x6A, charAttrs = 0x8000, x = 4, y = 4 })
        putUnit(m, SYM.gUnitArrayRed, 1, { charId = 0x80, x = 5, y = 4 })
    end)
    check(Board.unit(b, "red", 0x6A).isBoss, true, "CA_BOSS character reads isBoss")
    check(Board.unit(b, "red", 0x80).isBoss, false, "generic reads not isBoss")
    check(Board.unit(b, "red", 0x6A).faction, "red", "faction from the array")
    check(Board.unit(b, "red", 0x80).slot, 1, "slot is the 0-based array index")
end

-- A staff-only unit has no attack reach; a bow reads 2-2; a sword 1-1.
do
    local b = board(function(m)
        putUnit(m, SYM.gUnitArrayBlue, 0, { charId = 1, items = { { 3, 30 } } })
        putUnit(m, SYM.gUnitArrayBlue, 1, { charId = 2, items = { { 2, 45 }, { 3, 1 } } })
        putUnit(m, SYM.gUnitArrayBlue, 2, { charId = 3, items = { { 1, 46 } } })
    end)
    check(Board.unit(b, "blue", 1).minRange, nil, "staff-only minRange nil")
    check(Board.unit(b, "blue", 1).maxRange, nil, "staff-only maxRange nil")
    check(Board.unit(b, "blue", 2).minRange, 2, "bow minRange")
    check(Board.unit(b, "blue", 2).maxRange, 2, "bow maxRange")
    check(Board.unit(b, "blue", 3).maxRange, 1, "sword maxRange")
    local items = Board.unit(b, "blue", 2).items
    check(#items, 2, "items lists only the held slots")
    check(items[1].id, 2, "item id")
    check(items[1].uses, 45, "item uses")
    check(items[2].id, 3, "second item id")
end

-- A dead unit (US_DEAD) is on the board but excluded by Board.live; acted reads state bit 1.
do
    local b = board(function(m)
        putUnit(m, SYM.gUnitArrayRed, 0, { charId = 0x80, state = 0x4, hp = 0 })
        putUnit(m, SYM.gUnitArrayRed, 1, { charId = 0x81, x = 2, y = 2 })
        putUnit(m, SYM.gUnitArrayBlue, 0, { charId = 1, state = 0x2 })
    end)
    check(Board.unit(b, "red", 0x80).dead, true, "US_DEAD reads dead")
    local live = Board.live(b, "red")
    check(#live, 1, "Board.live drops the dead unit")
    check(live[1].charId, 0x81, "Board.live keeps the living one")
    check(Board.unit(b, "blue", 1).acted, true, "US_UNSELECTABLE reads acted")
    check(Board.unit(b, "red", 0x81).acted, false, "fresh unit has not acted")
end

-- Bounds are the decomp's: blue slot 61 is blue; what sits past it is red slot 0, read once,
-- as red. Green is read too.
do
    local b = board(function(m)
        putUnit(m, SYM.gUnitArrayBlue, 61, { charId = 9 })
        putUnit(m, SYM.gUnitArrayRed, 0, { charId = 0x90 })
        putUnit(m, SYM.gUnitArrayRed, 49, { charId = 0x91 })
        putUnit(m, SYM.gUnitArrayGreen, 19, { charId = 0x30, classId = 7, level = 4 })
    end)
    check(Board.unit(b, "blue", 9).slot, 61, "blue[61] is read")
    check(Board.unit(b, "blue", 0x90), nil, "red[0] is not blue[62]")
    check(Board.unit(b, "red", 0x91).slot, 49, "red[49] is read")
    check(Board.unit(b, "green", 0x30).classId, 7, "green[19] read with its class id")
    check(Board.unit(b, "green", 0x30).level, 4, "level")
    check(#b.units, 4, "each unit appears once")
end

-- Board.occupied sees every slot the decomp has (#531: red 24-49 were invisible), and a
-- dead unit's tile is free.
do
    local m = fakeMem()
    putUnit(m, SYM.gUnitArrayRed, 30, { charId = 0x80, x = 7, y = 3 })
    putUnit(m, SYM.gUnitArrayBlue, 40, { charId = 2, x = 1, y = 1 })
    putUnit(m, SYM.gUnitArrayGreen, 2, { charId = 0x40, x = 4, y = 4, state = 0x4 })
    local mem = { u8 = m.u8, s8 = m.s8, u16 = m.u16, u32 = m.u32 }
    check(Board.occupied(mem, SYM, 7, 3), true, "red slot 30 occupies its tile")
    check(Board.occupied(mem, SYM, 1, 1), true, "blue slot 40 occupies its tile")
    check(Board.occupied(mem, SYM, 4, 4), false, "a dead unit's tile is free")
    check(Board.occupied(mem, SYM, 7, 4), false, "an empty tile is free")
end

-- onField: on a tile AND not hidden, rescued, undeployed or dead -- each excluded on its own.
do
    local b = board(function(m)
        putUnit(m, SYM.gUnitArrayBlue, 0, { charId = 1, x = 2, y = 2 })
        putUnit(m, SYM.gUnitArrayBlue, 1, { charId = 2, x = 2, y = 3, state = 0x20 })  -- rescued
        putUnit(m, SYM.gUnitArrayBlue, 2, { charId = 3, x = 2, y = 4, state = 0x01 })  -- hidden
        putUnit(m, SYM.gUnitArrayBlue, 3, { charId = 4, x = 2, y = 5, state = 0x08 })  -- undeployed
        putUnit(m, SYM.gUnitArrayBlue, 4, { charId = 5, x = -1, y = -1 })              -- off map
        putUnit(m, SYM.gUnitArrayBlue, 5, { charId = 6, x = 2, y = 6, state = 0x02 })  -- acted
    end)
    check(Board.unit(b, "blue", 1).onField, true, "a plain unit on a tile is on the field")
    check(Board.unit(b, "blue", 2).onField, false, "US_RESCUED is off the field")
    check(Board.unit(b, "blue", 3).onField, false, "US_HIDDEN is off the field")
    check(Board.unit(b, "blue", 4).onField, false, "US_NOT_DEPLOYED is off the field")
    check(Board.unit(b, "blue", 5).onField, false, "x = -1 is off the field")
    check(Board.unit(b, "blue", 6).onField, true, "having acted does not leave the field")
end

-- The lean read: position/hp/state, and NOT the item/boss reads (which it must never touch).
do
    local m = fakeMem()
    defineItems(m)
    putUnit(m, SYM.gUnitArrayRed, 3, { charId = 0x6A, charAttrs = 0x8000, x = 4, y = 5,
        hp = 7, maxhp = 18, items = { { 1, 40 } } })
    local reads = 0
    local function counted(f) return function(a) reads = reads + 1; return f(a) end end
    local mem = { u8 = counted(m.u8), s8 = counted(m.s8), u16 = counted(m.u16), u32 = counted(m.u32) }
    local u = Board.leanAt(mem, SYM, SYM.gUnitArrayRed, 3)
    check(u.charId, 0x6A, "lean charId")
    check(u.x, 4, "lean x")
    check(u.hp, 7, "lean hp")
    check(u.maxhp, 18, "lean maxhp")
    check(u.faction, "red", "lean faction")
    check(u.slot, 3, "lean slot")
    check(u.onField, true, "lean onField")
    check(u.isBoss, nil, "lean does not read the boss attribute")
    check(u.minRange, nil, "lean does not read the weapon")
    check(reads, 10, "lean read is ten memory reads")
    reads = 0
    local full = Board.unitAt(mem, SYM, SYM.gUnitArrayRed, 3)
    check(full.isBoss, true, "full read has the boss attribute")
    check(full.maxRange, 1, "full read has the weapon reach")
    check(reads > 10, true, "the full read costs more than the lean one")
end

-- Lean scans over the decomp bounds: findIn, liveCount, liveBoss, leanList.
do
    local m = fakeMem()
    putUnit(m, SYM.gUnitArrayRed, 0, { charId = 0x80, x = 1, y = 1 })
    putUnit(m, SYM.gUnitArrayRed, 30, { charId = 0x81, x = 2, y = 1 })
    putUnit(m, SYM.gUnitArrayRed, 31, { charId = 0x82, x = 3, y = 1, state = 0x4 })  -- dead
    putUnit(m, SYM.gUnitArrayRed, 32, { charId = 0x83, x = 4, y = 1, state = 0x20 }) -- rescued
    putUnit(m, SYM.gUnitArrayRed, 40, { charId = 0x6A, charAttrs = 0x8000, x = 9, y = 9 })
    putUnit(m, SYM.gUnitArrayRed, 41, { charId = 0x6B, charAttrs = 0x8000, x = -1, y = -1 })
    local mem = { u8 = m.u8, s8 = m.s8, u16 = m.u16, u32 = m.u32 }
    check(Board.liveCount(mem, SYM, "red"), 3, "liveCount: on-field reds at any slot")
    check(Board.liveCount(mem, SYM, "blue"), 0, "liveCount: no blues")
    local boss = Board.liveBoss(mem, SYM)
    check(boss and boss.slot, 40, "liveBoss: the on-field CA_BOSS unit, past slot 23")
    check(Board.findIn(mem, SYM, SYM.gUnitArrayRed, 50, 0x81).slot, 30, "findIn finds slot 30")
    check(Board.findIn(mem, SYM, SYM.gUnitArrayRed, 24, 0x81), nil, "findIn honours its count")
    check(#Board.leanList(mem, SYM, "red"), 6, "leanList returns every occupied slot")
    check(Board.occupied(mem, SYM, 4, 1), false, "a rescued unit does not occupy its old tile")
end

-- inPhase: the player phase of the recorded turn only -- not another faction's phase, and not
-- a LATER player phase (the guard that stops the clear loop ending a fresh turn unacted).
do
    check(Board.inPhase({ phase = "blue", turn = 3 }, 3), true, "same turn, player phase")
    check(Board.inPhase({ phase = "red", turn = 3 }, 3), false, "enemy phase of the same turn")
    check(Board.inPhase({ phase = "blue", turn = 4 }, 3), false, "the NEXT player phase")
    local b = board(function(m) putUnit(m, SYM.gUnitArrayBlue, 7, { charId = 9 }) end)
    check(Board.inPhase(b, 3), false, "a board read in the red phase is not our phase")
    check(Board.at(b, "blue", 7).charId, 9, "Board.at looks up by slot")
end

-- Header: turn, phase, map size.
do
    local b = board(function() end)
    check(b.turn, 3, "turn")
    check(b.phase, "red", "phase from PlaySt faction 0x80")
    check(b.map.w, 25, "map width")
    check(b.map.h, 16, "map height")
    check(#b.units, 0, "empty arrays read no units")
end

print(string.format("%d tests, %d failures", tests, fails))
if fails > 0 then os.exit(1) end
