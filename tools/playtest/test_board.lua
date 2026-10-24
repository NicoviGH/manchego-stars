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
    check(Board.find(mem, SYM, "red", 0x81).slot, 30, "find scans the faction's whole array")
    check(Board.find(mem, SYM, "blue", 0x81), nil, "find reads only the faction it names")
    check(#Board.leanList(mem, SYM, "red"), 6, "leanList returns every occupied slot")
    local seen, last = 0, nil
    for slot, u in Board.each(mem, SYM, "red") do
        seen = seen + 1; last = slot
        check(u.slot, slot, "each yields (slot, unit)")
    end
    check(seen, 6, "each visits every occupied slot, past slot 23")
    check(last, 41, "each runs to the decomp bound")
    local visited = 0
    for slot in Board.each(mem, SYM, "red") do
        visited = visited + 1
        if slot == 0 then putUnit(m, SYM.gUnitArrayRed, 5, { charId = 0x90, x = 6, y = 6 }) end
    end
    check(visited, 7, "each reads lazily: a unit placed mid-loop is seen")
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

-- Seize (#510 step 9): FE8's CanUnitSeize, as our engine patches it (0005, bmdifficulty.c):
-- the unit's character is LordSelect_GetPid() -- the first gLordSelectCandidates[i] whose
-- permanent flag 0xF0 + i is set, else candidate 0.
do
    local m = fakeMem()
    local CANDS = 0x08909624
    local pids = { 0x01, 0x03, 0x02 }
    for i, pid in ipairs(pids) do m.w16(CANDS + (i - 1) * 2, pid) end
    m.w16(CANDS + #pids * 2, 0xFFFF)
    local sym = setmetatable({ gLordSelectCandidates = CANDS }, { __index = SYM })
    local mem = { u8 = m.u8, s8 = m.s8, u16 = m.u16, u32 = m.u32 }
    local set = {}
    local function flag(f) return set[f] == true end
    check(Board.lordPid(mem, sym, flag), 0x01, "no pick recorded -> the first candidate")
    set[0xF0 + 1] = true
    check(Board.lordPid(mem, sym, flag), 0x03, "flag 0xF1 set -> candidate 1")
    check(Board.lordPid(mem, SYM, flag), nil, "no candidate table symbol -> unknown")

    local lord = { slot = 0, charId = 0x03 }
    local other = { slot = 1, charId = 0x02 }
    check(Board.canSeize(lord, 0x03, {}), true, "the chosen lead can seize")
    check(Board.canSeize(other, 0x03, {}), false,
        "a non-lord cannot -- known up front, before it ever walks to the throne")
    check(Board.canSeize(other, nil, {}), true, "lord unknown -> not ruled out yet")
    check(Board.canSeize(other, nil, { [1] = true }), false, "lord unknown -> the memo rules it out")
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

-- Placing a unit (#531 audit 4): bounds come from the map size passed in, and an off-map tile is
-- refused with nothing touched. 17x16 is ch03's map, where the old literal 24/15 accepted x=20.
do
    local mem2, grid = {}, {}
    local io = {
        rs8 = function(a) local v = mem2[a] or 0; return v >= 0x80 and v - 0x100 or v end,
        write8 = function(a, v) mem2[a] = v end,
        grid = function(x, y) return grid[y * 100 + x] or 0 end,
        setGrid = function(x, y, v) grid[y * 100 + x] = v end,
    }
    local A = 0x1000
    mem2[A + 0x10], mem2[A + 0x11] = 3, 4
    grid[4 * 100 + 3] = 0x41
    local ok, why = Board.place(io, A, 20, 5, 17, 16)
    check(ok, false, "place on x=20 of a 17-wide map is refused")
    check(why ~= nil and why:find("(20,5)", 1, true) ~= nil, true, "the refusal names the tile")
    check(mem2[A + 0x10], 3, "a refused place leaves the position")
    check(grid[4 * 100 + 3], 0x41, "a refused place leaves the old tile occupied")
    check(Board.place(io, A, 5, 16, 17, 16), false, "y == height is off the map")
    check(Board.place(io, A, -1, 0, 17, 16), false, "negative x is off the map")
    check(Board.place(io, A, 16, 15, 17, 16), true, "the far corner is on the map")
    check(mem2[A + 0x10], 16, "x written")
    check(grid[15 * 100 + 16], 0x41, "the old tile's id moved to the new tile")
    check(grid[4 * 100 + 3], 0, "the old tile was vacated")
    check(Board.place(io, A, 2, 2, 17, 16, { grid = 7, vacate = false }), true, "explicit grid id")
    check(grid[2 * 100 + 2], 7, "o.grid is what the new tile holds")
    check(grid[15 * 100 + 16], 0x41, "o.vacate == false leaves the old tile")
    -- A unit parked off the map (-1,-1) has no old tile to vacate.
    mem2[A + 0x10], mem2[A + 0x11] = 0xFF, 0xFF
    check(Board.place(io, A, 1, 1, 17, 16), true, "an off-map unit can be placed")
    check(grid[1 * 100 + 1], 0, "an off-map unit carries no grid id")
    -- o.tracked: the teleports' refusal. A unit whose old tile reads 0 (or that is off the map)
    -- is refused with nothing touched, instead of writing 0 under it and reporting success.
    mem2[A + 0x10], mem2[A + 0x11] = 0xFF, 0xFF
    local tok, twhy = Board.place(io, A, 6, 6, 17, 16, { tracked = true })
    check(tok, false, "tracked: an off-map unit has no grid id to carry, so it is refused")
    check(twhy ~= nil and twhy:find("not tracked", 1, true) ~= nil, true, "tracked: the refusal says why")
    check(mem2[A + 0x10], 0xFF, "tracked: a refused place leaves the position")
    mem2[A + 0x10], mem2[A + 0x11] = 1, 1          -- on the map, but its tile reads 0
    check(Board.place(io, A, 6, 6, 17, 16, { tracked = true }), false, "tracked: an untracked tile is refused")
    check(mem2[A + 0x10], 1, "tracked: nothing written on refusal")
    grid[1 * 100 + 1] = 0x42
    check(Board.place(io, A, 6, 6, 17, 16, { tracked = true }), true, "tracked: a tracked unit moves")
    check(grid[6 * 100 + 6], 0x42, "tracked: its id moved with it")
    check(grid[1 * 100 + 1], 0, "tracked: the old tile was vacated")
    -- freeBeside honours the bounds and the occupancy grid, in order.
    grid[0 * 100 + 1] = 5
    local fx, fy = Board.freeBeside(io, 0, 0, { { -1, 0 }, { 1, 0 }, { 0, 1 } }, 17, 16)
    check(fx .. "," .. fy, "0,1", "off-map and occupied neighbours are skipped")
    check(Board.freeBeside(io, 16, 0, { { 1, 0 } }, 17, 16), nil, "a neighbour past the width is none")
end

print(string.format("%d tests, %d failures", tests, fails))
if fails > 0 then os.exit(1) end
