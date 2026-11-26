-- timeline.lua: what a failed attempt showed on screen, and everything a retry reads from it
-- (#765, R1 of the bot redesign #764; ADR 0467). Pure: no emulator, no game read.
--
-- A person on their second try remembers what they saw: who came, when and after what; where each
-- enemy walked; who killed whom from where; which village went when; who left the map. This module
-- is the one owner of that memory. It reads it off an attempt's TRACE (botrun.lua's header: the
-- `phase` snapshots, `act`s, `fell`s, `event`s, `drop`s, `theft`s and the `end` record), so a
-- recorded game reads exactly as a live one: botrun feeds its own trace() into a recorder, and a
-- test feeds a filed trace.
--
-- Fog is respected (ADR 0386): a unit is kept only once a snapshot showed it out of fog, a fight
-- showed it (it killed one of our units) or the record says the screen showed it arrive; a track
-- point is kept only where it stood in sight. A snapshot with no `fogged` field (traces filed
-- before #765) reads as all in sight.
--
-- The timeline (Timeline.of(events), or recorder().result()), lists only, since the record is
-- JSON:
--   units     every red or green unit seen: { key (Board.memoryKey), id, charId, classId,
--             faction, arrival (its first board turn, nil for one there at the start),
--             appeared = { turn, boardTurn, x, y, by, timed } (an arrival the screen showed:
--             botrun's arrivals_seen), track = { { turn, phase, x, y, hp } } (each in-sight
--             snapshot where its tile or HP changed), gone = { how = "killed"|"left"|"turned", boardTurn
--             (the first player turn it was gone on), x, y, killer, side (a recruit's new side) } }
--   deaths    each blue or green death: { charId, faction, classId, hp (its last HP seen), x, y,
--             turn, phase, killer, killerClass, killerKey, killerTile, predicted (the read our
--             plan gave it, botrun's grade) }
--   closings  each village or chest another side closed: { x, y, phase (the enemy phase's turn),
--             closer, closerClass, closerKey }
--   items     what the screen showed change hands: { kind = "theft"|"drop", turn, ... }
--
-- A retry's memory is the failed attempts' timelines, oldest first: style.memory = { attempts }.
-- Its readers are below (M.enemies, M.arrivals, M.holdTurns, M.deadlines, M.routes, M.routeOf,
-- M.threats);
-- nothing else keeps a copy of what an earlier attempt saw.

local Board = dofile(PLAYTEST_DIR and (PLAYTEST_DIR .. "/board.lua")
    or ((debug.getinfo(1, "S").source:match("^@(.*/)") or "./") .. "board.lua"))

local M = {}

-- The first player turn a unit stands (or is gone) on, from the phase that first shows it: a
-- player phase is that turn; an enemy phase, the next. The one owner of the rule for a phase
-- named by its turn: botrun's leftMap reads it too (its boardTurnOf reads a board, whose arrival
-- may have acted in the phase: the same rule, with that case first).
function M.boardTurnOf(turn, phase)
    return phase == "player" and turn or turn + 1
end
local boardTurnOf = M.boardTurnOf

local function tileKey(x, y) return x .. "," .. y end

-- A recorder: feed(ev) takes each trace event in order, result() returns the timeline.
function M.recorder()
    local open = {}        -- slot id -> the segment of the unit in it now
    local segs = {}        -- every segment, in the order it opened
    local killed = {}      -- slot id -> { killer, killerId, turn, phase }, since the last snapshot
    local lastTile = {}    -- slot id -> { x, y, hp, classId }: blue or green, for a death's tile
    local killerAt = {}    -- victim slot id -> the killer's tile, from the act that felled it
    local items = {}
    local arrivedAt = {}   -- slot id -> the tile its latest `arrive` event named
    local record
    local first = true

    local function segOf(u, turn, phase)
        local at = arrivedAt[u.id]
        local s = { id = u.id, charId = u.charId, classId = u.classId, faction = u.faction,
                    start = first and 0 or boardTurnOf(turn, phase), track = {}, seen = false,
                    at = at and at.charId == u.charId and at or nil }
        arrivedAt[u.id] = nil
        segs[#segs + 1] = s
        open[u.id] = s
        return s
    end

    local actedTo = {}     -- slot id -> where its act this phase ended (reset each snapshot)

    -- the units a kill or a departure took off the field. A blue or green victim's killer struck
    -- from where its act this phase ended, or, when it did not act (it countered our attack),
    -- from where the last snapshot had it
    local function fell(list)
        for _, d in ipairs(list or {}) do
            killed[d.id] = { killer = d.killer, killerId = d.killerId, turn = d.turn,
                             phase = d.phase }
            if (d.faction == "blue" or d.faction == "green") and d.killerId then
                local s = open[d.killerId]
                killerAt[d.id] = actedTo[d.killerId]
                    or (s and s.last and { x = s.last.x, y = s.last.y }) or nil
            end
        end
    end

    local function snapshot(ev)
        local now = {}
        for _, u in ipairs(ev.units or {}) do
            now[u.id] = u
            if u.faction == "blue" or u.faction == "green" then
                lastTile[u.id] = { x = u.x, y = u.y, hp = u.hp, classId = u.classId }
            end
        end
        -- a slot gone, or holding another unit: its segment ends here
        for id, s in pairs(open) do
            local u = now[id]
            if not u or u.charId ~= s.charId or u.faction ~= s.faction then
                local k = killed[id]
                local last = s.last or {}
                -- the same character on another side: a recruit (or a turncoat), not a loss
                local how = (u and u.charId == s.charId and "turned") or (k and "killed") or "left"
                s.gone = { how = how, boardTurn = boardTurnOf(ev.turn, ev.phase),
                           x = last.x, y = last.y, killer = k and k.killer or nil,
                           side = how == "turned" and u.faction or nil }
                open[id] = nil
            end
        end
        for _, u in ipairs(ev.units or {}) do
            if u.faction ~= "blue" then
                local s = open[u.id] or segOf(u, ev.turn, ev.phase)
                -- the same unit read as another class (a promotion) keeps its segment
                s.classId = u.classId
                local last = s.last
                s.last = { x = u.x, y = u.y, hp = u.hp }
                if not u.fogged then
                    s.seen = true
                    local t = s.track[#s.track]
                    if not t or t.x ~= u.x or t.y ~= u.y or t.hp ~= u.hp or not last then
                        s.track[#s.track + 1] = { turn = ev.turn, phase = ev.phase, x = u.x,
                                                  y = u.y, hp = u.hp }
                    end
                end
            end
        end
        killed, actedTo = {}, {}
        first = false
    end

    local function act(ev)
        if ev.id and ev.to then actedTo[ev.id] = { x = ev.to.x, y = ev.to.y } end
        fell(ev.fell)
    end

    local self = {}
    function self.feed(ev)
        local t = ev.t
        if t == "phase" then snapshot(ev)
        elseif t == "act" then act(ev)
        elseif t == "fell" then fell(ev.fell)
        elseif t == "event" and ev.kind == "arrive" then
            arrivedAt[ev.id] = { charId = ev.charId, x = ev.x, y = ev.y }
        elseif t == "theft" then
            items[#items + 1] = { kind = "theft", turn = ev.turn, thief = ev.thief, from = ev.from,
                                  item = ev.item }
        elseif t == "drop" then
            items[#items + 1] = { kind = "drop", turn = ev.turn, from = ev.from, to = ev.to,
                                  item = ev.item }
        elseif t == "end" then record = ev.record
        end
    end

    function self.result()
        local rec = record or {}
        -- what the screen showed arrive (botrun's arrivals_seen), by character and tile
        local shown = {}
        for _, a in ipairs(rec.arrivals_seen or {}) do
            shown[#shown + 1] = a
        end
        -- the slot stamps botrun remembered each red by (enemies_seen): the key a retry's
        -- sight.knows matches. A trace filed before #765 has none; its arrival is the snapshot's
        local stamps = {}
        for _, e in ipairs(rec.enemies_seen or {}) do
            local k = e.id .. ":" .. tostring(e.charId) .. ":" .. tostring(e.classId)
            stamps[k] = stamps[k] or {}
            table.insert(stamps[k], e.arrival or 0)
        end
        local killers = {}
        for _, d in ipairs(rec.deaths or {}) do
            if d.killerId then killers[d.killerId .. ":" .. tostring(d.killer)] = true end
        end
        local units, byKey, bySlot = {}, {}, {}
        for _, s in ipairs(segs) do
            local appeared
            if s.start > 0 then
                -- the record's sighting of this arrival: on the tile its `arrive` event named
                -- when the trace has one, else the same character and class that turn
                local pick
                for i, a in ipairs(shown) do
                    local same = a.charId == s.charId and (a.classId == nil or a.classId == s.classId)
                        and math.abs((a.boardTurn or a.turn) - s.start) <= 1
                    if same and s.at and a.x == s.at.x and a.y == s.at.y then pick = i; break end
                    if same and not pick then pick = i end
                end
                local a = pick and table.remove(shown, pick)
                if a then
                    appeared = { turn = a.turn, boardTurn = a.boardTurn, x = a.x, y = a.y,
                                 by = a.by, timed = a.timed }
                end
            end
            local arrival = s.start > 0 and (appeared and appeared.boardTurn or s.start) or nil
            local st = stamps[s.id .. ":" .. tostring(s.charId) .. ":" .. tostring(s.classId)]
            if st and s.faction == "red" then
                -- the stamp nearest the segment's start: a slot refilled by the same character
                -- and class holds one stamp per arrival
                local best
                for _, a in ipairs(st) do
                    if not best or math.abs(a - s.start) < math.abs(best - s.start) then best = a end
                end
                arrival = best > 0 and best or nil
            end
            local seen = s.seen or appeared ~= nil or killers[s.id .. ":" .. tostring(s.charId)]
            if seen then
                local u = { key = Board.memoryKey(s.id, s.charId, s.classId, arrival), id = s.id,
                            charId = s.charId, classId = s.classId, faction = s.faction,
                            arrival = arrival, appeared = appeared, track = s.track,
                            gone = s.gone }
                units[#units + 1] = u
                byKey[u.key] = u
                bySlot[s.id] = bySlot[s.id] or {}
                table.insert(bySlot[s.id], u)
            end
        end
        -- the unit in slot `id` that was `charId` at board turn `turn`
        local function unitAt(id, charId, turn)
            local best
            for _, u in ipairs(bySlot[id] or {}) do
                if u.charId == charId and (u.arrival or 0) <= turn then best = u end
            end
            return best
        end
        local deaths = {}
        for _, d in ipairs(rec.deaths or {}) do
            if d.faction == "blue" or d.faction == "green" then
                local at = lastTile[d.id] or {}
                local k = d.killerId and unitAt(d.killerId, d.killer, boardTurnOf(d.turn, d.phase))
                deaths[#deaths + 1] = { charId = d.charId, faction = d.faction, classId = at.classId,
                                        hp = at.hp, x = at.x, y = at.y, turn = d.turn,
                                        phase = d.phase, killer = d.killer,
                                        killerClass = d.killerClass, killerKey = k and k.key or nil,
                                        killerTile = killerAt[d.id], predicted = d.predicted }
            end
        end
        local closings = {}
        for _, e in ipairs(rec.explore or {}) do
            if e.status == "closed" and e.closed_phase then
                local closer
                for _, u in ipairs(units) do
                    if u.charId == e.closed_by and (not e.closer_class or u.classId == e.closer_class)
                        and (u.arrival or 0) <= e.closed_phase + 1
                        and (not u.gone or u.gone.boardTurn > e.closed_phase) then
                        closer = u
                    end
                end
                closings[#closings + 1] = { x = e.x, y = e.y, phase = e.closed_phase,
                                            closer = e.closed_by, closerClass = e.closer_class,
                                            closerKey = closer and closer.key or nil }
            end
        end
        return { units = units, deaths = deaths, closings = closings, items = items }
    end
    return self
end

-- The timeline of a whole list of trace events.
function M.of(events)
    local r = M.recorder()
    for _, ev in ipairs(events) do r.feed(ev) end
    return r.result()
end

-- ---- readers: what a retry knows, from style.memory = { attempts = { timeline, ... } } ----

local function attempts(memory)
    return memory and memory.attempts or {}
end

-- A reader's answer, kept per memory table: a retry's memory never changes during its attempt,
-- and the hold is read at every decision (weak keys: a finished attempt's memory is dropped).
-- Every caller gets the same tables: a reader's answer is READ-ONLY (no caller edits one; a
-- caller that must, copies it first).
local cache = setmetatable({}, { __mode = "k" })
local compute = {}   -- each cached reader's own work, by name
local function memo(name, memory, fn)
    if not memory then return fn(memory) end
    local c = cache[memory]
    if not c then c = {}; cache[memory] = c end
    if c[name] == nil then c[name] = fn(memory) end
    return c[name]
end

-- Whether unit `u`'s arrival was brought by the play (our door, chest or visit: `by`; or a unit
-- the game did not time to a turn: timed == false), so it is dated from its appearance, never
-- by the calendar (ADR 0464's distinction, kept).
local function brought(u)
    local a = u and u.appeared
    return a ~= nil and (a.by ~= nil or a.timed == false)
end

-- Every red unit the earlier attempts showed, once each by its key: sight.remember's list
-- { id, charId, classId, arrival } (ADR 0399, 0449).
function M.enemies(memory) return memo("enemies", memory, compute.enemies) end
function compute.enemies(memory)
    local out, had = {}, {}
    for _, tl in ipairs(attempts(memory)) do
        for _, u in ipairs(tl.units or {}) do
            if u.faction == "red" and u.classId ~= nil and not had[u.key] then
                had[u.key] = true
                out[#out + 1] = { id = u.id, charId = u.charId, classId = u.classId,
                                  arrival = u.arrival }
            end
        end
    end
    return out
end

-- Each character the screen showed arrive, its latest attempt's sighting (ADR 0436): botrun's
-- pending recruits. { turn, boardTurn, x, y, charId, classId, by, timed }.
function M.arrivals(memory) return memo("arrivals", memory, compute.arrivals) end
function compute.arrivals(memory)
    local out, at = {}, {}
    for _, tl in ipairs(attempts(memory)) do
        for _, u in ipairs(tl.units or {}) do
            local a = u.appeared
            if a then
                local e = { turn = a.turn, boardTurn = a.boardTurn, x = a.x, y = a.y,
                            charId = u.charId, classId = u.classId, by = a.by, timed = a.timed }
                if at[u.charId] then out[at[u.charId]] = e
                else out[#out + 1] = e; at[u.charId] = #out end
            end
        end
    end
    return out
end

-- The turns the earlier attempts saw a turn's reinforcement arrive (the march's hold, ADR 0386),
-- sorted, once each; never one the play brought (#741).
function M.holdTurns(memory) return memo("holdTurns", memory, compute.holdTurns) end
function compute.holdTurns(memory)
    local out, had = {}, {}
    for _, tl in ipairs(attempts(memory)) do
        for _, u in ipairs(tl.units or {}) do
            local a = u.appeared
            if a and not brought(u) and not had[a.turn] then
                had[a.turn] = true
                out[#out + 1] = a.turn
            end
        end
    end
    table.sort(out)
    return out
end

-- When this attempt loses what earlier ones lost, as early as any lost it:
--   tiles = { ["x,y"] = the enemy phase's turn a looter or an event closed it }
--   gone  = { [charId] = the first player turn that unit was off the map, unkilled }
-- A loss by a unit the game timed is dated by the calendar. One by a unit the play brought
-- (Ch14's Rennac, whom our door loads, loots and leaves) is dated by the turns after it appeared,
-- and counts once it has appeared in this attempt: `appeared(charId, classId)` -> this attempt's
-- first board turn for that unit, or nil (botrun's stamps). A death is the play's, never kept.
-- Every loss the attempts remember, once per memory: { kind = "tile"|"gone", k ("x,y" or a
-- charId), t (its turn), from (the unit's own appearance when the play brought it: { charId,
-- classId, boardTurn }) }.
local function losses(memory)
    local out = {}
    for _, tl in ipairs(attempts(memory)) do
        local byKey = {}
        for _, u in ipairs(tl.units or {}) do byKey[u.key] = u end
        local function from(u)
            if not brought(u) then return nil end
            return { charId = u.charId, classId = u.classId, boardTurn = u.appeared.boardTurn }
        end
        for _, c in ipairs(tl.closings or {}) do
            out[#out + 1] = { kind = "tile", k = tileKey(c.x, c.y), t = c.phase,
                              from = from(byKey[c.closerKey]) }
        end
        for _, u in ipairs(tl.units or {}) do
            if u.gone and u.gone.how == "left" then
                out[#out + 1] = { kind = "gone", k = u.charId, t = u.gone.boardTurn, from = from(u) }
            end
        end
    end
    return out
end

function M.deadlines(memory, appeared)
    local out = { tile = {}, gone = {} }
    for _, l in ipairs(memo("losses", memory, losses)) do
        local t = l.t
        if l.from then
            local now = appeared and appeared(l.from.charId, l.from.classId)
            t = now and now + (t - l.from.boardTurn) or nil
        end
        local into = out[l.kind]
        if t and (not into[l.k] or t < into[l.k]) then into[l.k] = t end
    end
    return { tiles = out.tile, gone = out.gone }
end

-- Where each unit walked, counted from its appearance (0 = its first board turn), from the latest
-- attempt that showed it: { [key] = { charId, classId, steps = { { after, phase, x, y } } } }.
function M.routes(memory) return memo("routes", memory, compute.routes) end
function compute.routes(memory)
    local out = {}
    for _, tl in ipairs(attempts(memory)) do
        for _, u in ipairs(tl.units or {}) do
            local from = u.arrival or 0
            local steps = {}
            for _, p in ipairs(u.track or {}) do
                steps[#steps + 1] = { after = boardTurnOf(p.turn, p.phase) - from, phase = p.phase,
                                      x = p.x, y = p.y }
            end
            out[u.key] = { charId = u.charId, classId = u.classId, steps = steps }
        end
    end
    return out
end

-- A character's walk (M.routes' steps) by its charId and class, from the latest attempt that
-- showed it walk, or nil: a unit's slot id is not the same over attempts, its character is
-- (#766's stage job: where a recruit walks after he appears). Second answer: the first board
-- turn it arrived on that attempt, the one its steps count from; nil for a unit there at the
-- start (its steps count from turn 0).
function M.routeOf(memory, charId, classId)
    local out, arrival
    for _, tl in ipairs(attempts(memory)) do
        for _, u in ipairs(tl.units or {}) do
            local r = u.charId == charId and u.classId == classId and M.routes(memory)[u.key]
            if r and #r.steps > 0 then out, arrival = r.steps, u.arrival end
        end
    end
    return out, arrival
end

-- Each act by our army that brought reds, by the act and its tile (an arrival's `by`, botrun's
-- triggerOf): what a person who opened that door before knows. Vanilla Ch14's (22,17) door
-- brings four Fighters and Rennac into the corridor he leaves by (#766); the one try that got
-- him had three strikers at the door when it opened.
--   { act, x, y,
--     front = { { charId, classId, x, y } }: the foes it brought on the first board turn it
--             brought any (the act's own), a foe being a red that neither left the map nor
--             turned (a recruit is a goal, not a foe), from the latest attempt that made the act
--     tiles = { ["x,y"] = true }: tiles a unit it brought closed (looted, opened) in any attempt
--     gone  = { [charId] = true }: units it brought that left the map, unkilled, in any attempt }
-- In act-tile order. A death is the play's (as deadlines' reads it): no loss.
function M.releases(memory) return memo("releases", memory, compute.releases) end
function compute.releases(memory)
    local byAct, order = {}, {}
    for _, tl in ipairs(attempts(memory)) do
        local byKey, mine = {}, {}
        for _, u in ipairs(tl.units or {}) do
            byKey[u.key] = u
            local by = u.appeared and u.appeared.by
            if by and u.faction == "red" then
                local k = by.act .. ":" .. tileKey(by.x, by.y)
                local r = byAct[k]
                if not r then
                    r = { act = by.act, x = by.x, y = by.y, front = {}, tiles = {}, gone = {} }
                    byAct[k], order[#order + 1] = r, k
                end
                mine[k] = mine[k] or { r = r, units = {} }
                table.insert(mine[k].units, u)
                if u.gone and u.gone.how == "left" then r.gone[u.charId] = true end
            end
        end
        for _, c in ipairs(tl.closings or {}) do
            local u = c.closerKey and byKey[c.closerKey]
            local by = u and u.appeared and u.appeared.by
            local r = by and byAct[by.act .. ":" .. tileKey(by.x, by.y)]
            if r then r.tiles[tileKey(c.x, c.y)] = true end
        end
        -- this attempt made the act: its own turn's reds are the front (the latest attempt's)
        for _, m in pairs(mine) do
            local function foe(u)
                return not (u.gone and (u.gone.how == "left" or u.gone.how == "turned"))
            end
            local first
            for _, u in ipairs(m.units) do
                local t = u.appeared.boardTurn
                if foe(u) and (not first or t < first) then first = t end
            end
            local front = {}
            for _, u in ipairs(m.units) do
                if u.appeared.boardTurn == first and foe(u) then
                    front[#front + 1] = { charId = u.charId, classId = u.classId,
                                          x = u.appeared.x, y = u.appeared.y }
                end
            end
            m.r.front = front
        end
    end
    table.sort(order)
    local out = {}
    for _, k in ipairs(order) do out[#out + 1] = byAct[k] end
    return out
end

-- Who killed whom, from where, on which turn, over every earlier attempt, oldest first: each
-- death as M.recorder's `deaths` has it, with its `attempt`.
function M.threats(memory) return memo("threats", memory, compute.threats) end
function compute.threats(memory)
    local out = {}
    for i, tl in ipairs(attempts(memory)) do
        for _, d in ipairs(tl.deaths or {}) do
            local e = {}
            for k, v in pairs(d) do e[k] = v end
            e.attempt = i
            out[#out + 1] = e
        end
    end
    return out
end

return M
