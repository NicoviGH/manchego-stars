-- Tests for timeline.lua (#765, ADR 0467): an attempt's visible timeline read off its trace, and
-- what a retry reads from it. The recorded games under fixtures/ are three filed traces cut to
-- the events the timeline reads (jq, in the fixtures' README).
-- Run: lua tools/playtest/test_timeline.lua
local here = (arg[0]:match("(.*/)")) or "./"
local Timeline = dofile(here .. "timeline.lua")
local Fakeline = dofile(here .. "fakeline.lua")
local Json = dofile(here .. "json.lua")

local tests, fails = 0, 0
local function check(got, want, msg)
    tests = tests + 1
    if got ~= want then
        fails = fails + 1
        print(string.format("FAIL: %s\n  got  %s\n  want %s", msg, tostring(got), tostring(want)))
    end
end

local function recorded(name)
    local evs = {}
    for line in io.lines(here .. "fixtures/timeline-" .. name .. ".jsonl") do
        evs[#evs + 1] = Json.decode(line)
    end
    return Timeline.of(evs)
end

local function unitOf(tl, charId, classId)
    for _, u in ipairs(tl.units) do
        if u.charId == charId and (not classId or u.classId == classId) then return u end
    end
end

local function closingAt(tl, x, y)
    for _, c in ipairs(tl.closings) do
        if c.x == x and c.y == y then return c end
    end
end

-- ---- the recorder, on synthetic events ----

local function phase(turn, ph, units) return { t = "phase", turn = turn, phase = ph, units = units } end
local function u(id, charId, classId, faction, x, y, hp, fogged)
    return { id = id, charId = charId, classId = classId, faction = faction, x = x, y = y, hp = hp,
             fogged = fogged }
end

-- A red seen, one only in fog, a green recruited, a red that left, and our unit killed by a red
-- that moved to strike: what each became, and the killer's tile.
do
    local tl = Timeline.of({
        phase(1, "player", { u(1, 1, 2, "blue", 0, 0, 20), u(0x81, 0x50, 9, "red", 5, 5, 18),
                             u(0x82, 0x51, 9, "red", 9, 9, 18, true),
                             u(0x40, 0x12, 4, "green", 3, 3, 15),
                             u(0x83, 0x52, 9, "red", 7, 7, 18) }),
        phase(1, "enemy", { u(1, 1, 2, "blue", 0, 0, 20), u(0x81, 0x50, 9, "red", 5, 5, 18),
                            u(0x82, 0x51, 9, "red", 9, 9, 18, true),
                            u(0x40, 0x12, 4, "blue", 3, 3, 15),
                            u(0x83, 0x52, 9, "red", 7, 8, 18) }),
        { t = "act", turn = 1, phase = "enemy", id = 0x81, to = { x = 1, y = 0 }, fell = {} },
        { t = "fell", turn = 1, phase = "enemy",
          fell = { { id = 1, charId = 1, faction = "blue", killer = 0x50, killerId = 0x81 } } },
        phase(2, "player", { u(0x81, 0x50, 9, "red", 1, 0, 18),
                             u(0x82, 0x51, 9, "red", 9, 9, 18, true),
                             u(0x40, 0x12, 4, "blue", 3, 3, 15) }),
        { t = "end", turn = 2, record = { deaths = { { id = 1, charId = 1, faction = "blue",
            killer = 0x50, killerId = 0x81, killerClass = 9, turn = 1, phase = "enemy",
            predicted = 0.1 } } } },
    })
    local seen = unitOf(tl, 0x50)
    check(seen and seen.key, "129:80:9", "a start unit keyed by slot, character and class")
    check(seen and #seen.track, 2, "its track: where it stood, and where it moved")
    check(unitOf(tl, 0x51), nil, "one only ever in fog is not kept")
    local green = unitOf(tl, 0x12)
    check(green and green.gone and green.gone.how, "turned", "a recruit is no departure")
    check(green and green.gone and green.gone.side, "blue", "and says its new side")
    local left = unitOf(tl, 0x52)
    check(left and left.gone and left.gone.how .. " t" .. left.gone.boardTurn .. " "
          .. left.gone.x .. "," .. left.gone.y, "left t2 7,8",
          "an unkilled red gone: left, from its last tile, the first player turn it was gone on")
    check(left and #left.track, 2, "a track point only where it moved")
    local d = tl.deaths[1]
    check(d and d.x .. "," .. d.y .. " by " .. d.killerKey, "0,0 by 129:80:9",
          "our death: its tile and its killer's key")
    check(d and d.killerTile and d.killerTile.x .. "," .. d.killerTile.y, "1,0",
          "the killer struck from where its act ended")
    check(d and d.predicted, 0.1, "and the read our plan gave it")
end

-- A killer seen only in a fight (fog) is kept: a fight is on screen.
do
    local tl = Timeline.of({
        phase(1, "player", { u(1, 1, 2, "blue", 0, 0, 20), u(0x81, 0x50, 9, "red", 5, 5, 18, true) }),
        { t = "fell", turn = 1, phase = "enemy",
          fell = { { id = 1, charId = 1, faction = "blue", killer = 0x50, killerId = 0x81 } } },
        phase(2, "player", { u(0x81, 0x50, 9, "red", 1, 0, 18, true) }),
        { t = "end", record = { deaths = { { id = 1, charId = 1, faction = "blue", killer = 0x50,
            killerId = 0x81, killerClass = 9, turn = 1, phase = "enemy" } } } },
    })
    check(unitOf(tl, 0x50) ~= nil, true, "a fogged killer is remembered")
    check(#unitOf(tl, 0x50).track, 0, "with no track point from the fog")
end

-- ---- the recorded games ----

-- Ch14 s4003 attempt 1 (x741c): Rennac (charId 28) comes through the door our act opened on turn
-- 2, loots two chests, and is gone from turn 11, 9 turns after he appeared (#741, #764).
do
    local tl = recorded("ch14-x741c-a1")
    local r = unitOf(tl, 28)
    check(r and r.appeared and r.appeared.by and r.appeared.by.act, "door", "Rennac: our door brought him")
    check(r and r.appeared.boardTurn, 2, "Rennac: on turn 2")
    check(r and r.gone and r.gone.how, "left", "Rennac: he left the map")
    check(r and r.gone.boardTurn - r.appeared.boardTurn, 9, "Rennac: 9 turns after he appeared")
    check(closingAt(tl, 22, 5) and closingAt(tl, 22, 5).closerKey, r and r.key,
          "Rennac's chest: closed by him")
    -- a retry dates his departure from his appearance in its own attempt (ADR 0464 dropped it)
    local mem = { attempts = { tl } }
    check(Timeline.deadlines(mem, function(c) return c == 28 and 5 or nil end).gone[28], 14,
          "Rennac in a retry: gone 9 turns after he appears there")
    check(Timeline.deadlines(mem, function() return nil end).gone[28], nil,
          "Rennac not appeared yet: no date")
    -- the hold: the turns a turn event brought units on (2 has some beside the door's), never
    -- the door's own or the unit no turn event loads
    check(table.concat(Timeline.holdTurns(mem), ","), "2,5,6", "the hold: the timed arrivals' turns")
    check(#tl.deaths, 1, "the one death of the attempt")
    check(tl.deaths[1].killerKey ~= nil, true, "its killer is a unit the timeline kept")
    -- a timeline is what the record stores: it must encode, and stay small
    local size = #Json.encode(tl)
    check(size < 32 * 1024, true, "Ch14's timeline is under 32 KB (" .. size .. ")")
end

-- Ch10 s4002 attempt 1, two games (x741d, fx730a): each village's raze phase, from a unit there
-- at the start and from one that arrived on turn 2.
do
    local a = recorded("ch10-x741d-a1")
    local c = closingAt(a, 11, 15)
    check(c and c.phase, 5, "x741d: (11,15) razed in enemy phase 5")
    check(c and c.closerKey, "152:167:66", "by the unit there from the start")
    local b = recorded("ch10-fx730a-a1")
    c = closingAt(b, 1, 11)
    check(c and c.phase, 5, "fx730a: (1,11) razed in enemy phase 5")
    check(c and c.closerKey, "a:167:66:2", "by a turn-2 arrival")
    local dl = Timeline.deadlines({ attempts = { a, b } }, nil).tiles
    check(dl["11,15"] .. " " .. dl["1,11"], "5 5", "a retry of both knows both villages' dates")
end

-- ---- the readers ----

-- the hold: a turn's arrivals only, each turn once, sorted; never one the play brought
do
    local mem = Fakeline.memory(
        { arrivals = { { charId = 0x82, classId = 1, turn = 6 },
                       { charId = 0x1C, classId = 2, turn = 2, by = { act = "door", x = 1, y = 1 } },
                       { charId = 0x80, classId = 3, turn = 3, timed = false } } },
        { arrivals = { { charId = 0x83, classId = 1, turn = 4 }, { charId = 0x84, classId = 1, turn = 6 } } })
    check(table.concat(Timeline.holdTurns(mem), ","), "4,6", "hold: 4 and 6, not the door's or the room's")
    check(#Timeline.holdTurns(nil), 0, "no memory: no hold")
end

-- arrivals: each character's latest sighting, with how it came
do
    local mem = Fakeline.memory(
        { arrivals = { { charId = 0x82, classId = 1, x = 9, y = 9, turn = 4 } } },
        { arrivals = { { charId = 0x82, classId = 1, x = 7, y = 2, turn = 5 },
                       { charId = 0x1C, classId = 2, x = 22, y = 12, turn = 2,
                         by = { act = "door", x = 22, y = 18 } } } })
    local got = {}
    for _, a in ipairs(Timeline.arrivals(mem)) do
        got[#got + 1] = string.format("%X@%d,%d t%d%s", a.charId, a.x, a.y, a.turn, a.by and " " .. a.by.act or "")
    end
    check(table.concat(got, " "), "82@7,2 t5 1C@22,12 t2 door", "arrivals: the latest wins, the act kept")
end

-- enemies: the union, each key once, an arrival apart from the same slot's start unit; a red
-- whose class was not read is not kept (its key would match nothing)
do
    local mem = Fakeline.memory(
        { enemies = { { id = 0x81, charId = 0x50, classId = 1 }, { id = 0x82, charId = 0x51, classId = 1 },
                      { id = 0x83, charId = 0x53 } } },
        { enemies = { { id = 0x81, charId = 0x50, classId = 1 }, { id = 0x81, charId = 0x52, classId = 1 },
                      { id = 0x93, charId = 0x50, classId = 1, arrival = 7 } } })
    local ids = {}
    for _, e in ipairs(Timeline.enemies(mem)) do
        ids[#ids + 1] = string.format("%x:%x:%s", e.id, e.charId, tostring(e.arrival))
    end
    check(table.concat(ids, ","), "81:50:nil,82:51:nil,81:52:nil,93:50:7", "enemies: the union, once each")
end

-- deadlines: the earliest over the attempts; a loss by a unit the play brought is dated from its
-- appearance in this attempt; a unit killed is no departure
do
    local looter = "a:128:63:3"
    local mem = Fakeline.memory(
        { closings = { { x = 11, y = 15, phase = 9 } },
          arrivals = { { charId = 0x12, classId = 4, turn = 2, gone = { how = "left", boardTurn = 8 } },
                       { charId = 0x13, classId = 4, turn = 2, gone = { how = "killed", boardTurn = 5 } } } },
        { closings = { { x = 11, y = 15, phase = 4 }, { x = 22, y = 5, phase = 6, closerKey = looter } },
          arrivals = { { charId = 0x80, classId = 63, turn = 3, timed = false },
                       { charId = 0x12, classId = 4, turn = 2, gone = { how = "left", boardTurn = 6 } } } })
    local dl = Timeline.deadlines(mem, function(c, k) return c == 0x80 and k == 63 and 5 or nil end)
    check(dl.tiles["11,15"], 4, "the earliest closing over both")
    check(dl.tiles["22,5"], 8, "a brought looter's: 3 phases after its appearance, here on turn 5")
    check(dl.gone[0x12], 6, "the earliest departure")
    check(dl.gone[0x13], nil, "a unit killed is the play's, no departure")
    check(Timeline.deadlines(mem, nil).tiles["22,5"], nil, "a brought looter not seen yet dates nothing")
end

-- routes: counted from appearance; threats: every death with its attempt
do
    local tl = Fakeline.attempt({ arrivals = { { charId = 0x80, classId = 5, turn = 3 } },
                                  deaths = { { charId = 1, killerKey = "a:128:5:3" } } })
    tl.units[1].track = { { turn = 3, phase = "player", x = 1, y = 1, hp = 20 },
                          { turn = 4, phase = "enemy", x = 2, y = 1, hp = 20 } }
    local mem = { attempts = { tl } }
    local r = Timeline.routes(mem)[tl.units[1].key]
    check(r and #r.steps .. " " .. r.steps[1].after .. " " .. r.steps[2].after, "2 0 2",
          "a route counts the turns since it appeared")
    local t = Timeline.threats(mem)
    check(#t .. " " .. t[1].killerKey .. " a" .. t[1].attempt, "1 a:128:5:3 a1", "threats: the death and its attempt")
end

-- routeOf: a character's walk by its charId and class, the latest attempt that showed it (#766's
-- stage job reads where a recruit walks, not which slot he had)
do
    local a1 = Fakeline.attempt({ arrivals = { { charId = 0x80, classId = 5, turn = 3 } } })
    a1.units[1].track = { { turn = 3, phase = "player", x = 1, y = 1, hp = 20 } }
    local a2 = Fakeline.attempt({ arrivals = { { charId = 0x80, classId = 5, turn = 4 } } })
    a2.units[1].track = { { turn = 4, phase = "player", x = 2, y = 2, hp = 20 },
                          { turn = 5, phase = "enemy", x = 3, y = 2, hp = 20 } }
    local mem = { attempts = { a1, a2 } }
    local r = Timeline.routeOf(mem, 0x80, 5)
    check(r and #r .. " " .. r[2].after .. " " .. r[2].x, "2 2 3", "routeOf: the latest attempt's walk")
    check(Timeline.routeOf(mem, 0x80, 6), nil, "routeOf: another class is another unit")
    check(Timeline.routeOf(nil, 0x80, 5), nil, "routeOf: no memory, no route")
end

-- releases: an act by our army that brought reds, its front (its own turn's reds, foes only) and what
-- the units it brought lost (#766: vanilla Ch14's (22,17) door brings four Fighters and Rennac,
-- who loots two chests and leaves)
do
    local door = { act = "door", x = 22, y = 17 }
    local mem = Fakeline.memory(
        { arrivals = { { charId = 0x80, classId = 9, x = 22, y = 16, turn = 4, by = door, timed = false },
                       { charId = 0x80, classId = 63, x = 21, y = 14, turn = 4, by = door, timed = false },
                       { charId = 0x1C, classId = 51, x = 22, y = 12, turn = 4, by = door, timed = false,
                         gone = { how = "left", boardTurn = 12 } },
                       { charId = 0x80, classId = 19, x = 22, y = 7, turn = 5, by = door, timed = false },
                       { charId = 0x80, classId = 5, x = 7, y = 18, turn = 5, timed = true } },
          closings = { { x = 22, y = 5, phase = 5, closerKey = "a:28:51:4" },
                       { x = 11, y = 15, phase = 6 } } })
    local r = Timeline.releases(mem)
    check(#r, 1, "releases: one act brought reds (a timed arrival is no release)")
    local fr = {}
    for _, u in ipairs(r[1] and r[1].front or {}) do fr[#fr + 1] = u.x .. "," .. u.y end
    table.sort(fr)
    check(r[1] and r[1].act .. " " .. r[1].x .. "," .. r[1].y, "door 22,17", "releases: the act and its tile")
    check(table.concat(fr, " "), "21,14 22,16", "releases: its own turn's foes; not the recruit who left, nor a later arrival")
    check(r[1] and r[1].gone[0x1C], true, "releases: the unit it brought that left")
    check(r[1] and r[1].tiles["22,5"], true, "releases: the tile its unit closed")
    check(r[1] and r[1].tiles["11,15"], nil, "releases: not a tile someone else closed")
    check(#Timeline.releases(nil), 0, "releases: no memory, none")
end

print(string.format("%d tests, %d failures", tests, fails))
if fails > 0 then os.exit(1) end
