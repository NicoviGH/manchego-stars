-- botrun.lua -- the bot plays ONE chapter of the running ROM (#510 step 9, PR D).
--
-- Its own chunk, reached the way cases.lua is: harness.lua's `bot` scenario builds an `api`
-- table and calls Botrun.run(api). Nothing here touches emu, SYM or a harness global, so
-- test_botrun.lua drives it with a fake api and no emulator.
--
-- The loop: one sight for the run (sight.lua), refreshed whenever the board may have changed
-- -- after every action -- and given a fresh phase (newPhase: its caches too) at each player
-- phase. At a phase's start the board is hashed; then
-- Bot.decide is asked for one action at a time until it returns nil; then the phase ends and the
-- enemy phase is ridden out. The run ends:
--   won      the chapter advanced (api.won)
--   lost     the game-over screen came up (api.lost), or the enemy phase reached it
--   stuck    a player phase began on a board already seen this run, and nothing ahead can
--            change it -- for the planner, a board that comes round again AFTER the planner was
--            made to change it once (its first repeat: opts.stalled, counted in the record's
--            `board_repeats`): the hash holds every on-field unit's id, tile and HP, the
--            objective's turns left, and the turns until the next arrival a reinforcements claim cites --
--            everything Bot.decide reads -- and the game's own turn-event check
--            (sight.nextTurnEvent) finds no event still to fire. A repeat with an event ahead
--            waits for that turn.
--   crashed  anything the run could not do: an action or enemy phase the harness could not
--            drive, an action that left its unit able to act, a Seize the menu refused though
--            the game's CanUnitSeize allowed it, or any Lua error (a sight call that never
--            returned, a policy fault). The record is still emitted.
-- There is no turn cap: a board that cannot change any more is the only "no progress" rule.
--
-- api (harness.lua builds it; test_botrun.lua fakes it):
--   Bot, Json          bot.lua and json.lua, loaded by the caller
--   Planner            OPTIONAL: planner.lua; when given it plays every style but greedy, and
--                      a plan's acts are played in turn until Planner.surprise calls for a new
--                      one (the record's `plans`: made, and acts played from a kept one)
--   info = { game, rom_hash, chapter, mode, seed, campaign, attempt, instrument }  what the
--                      record names; instrument = the bot hash and suite version (PT_INSTRUMENT)
--                      the run by; campaign and attempt only when campaign.lua plays it
--   style = Bot.STYLES-shaped table, claims = resolved claims (bot.lua's Claims)
--   villageGifts, houseGifts  OPTIONAL: { items, gold }, what every vanilla village and House
--                      gives (campaign_env): the worth of one whose gift is unknown (goals.lua)
--   recruits()         OPTIONAL: the charIds the chapter's talks would bring over, read from
--                      the game at the first look (Sight talks: each talk the game would run,
--                      its pidB); absent, the recruits part is "unchecked" and `clean` is
--                      never true
--   party()            with recruits: the charIds in the game's party now, the game's own
--                      MakePrepUnitList (IsUnitInCurrentRoster), run in the sandbox
--   seed(s)            seed the game's RNG (Sight.seed)
--   board()            Board.read
--   sight()            Sight.new, called once
--   act(action)        perform Bot.decide's or the planner's action (a Visit or Chest
--                      included): true; "noseize" when the menu offered no
--                      Seize; false on a controller fault
--   endPhase()         "player" | "gameover" | "ended" | nil, the deaths it saw:
--                      { { id, charId, faction, killer } } (id = Board's unit index byte,
--                      killer = the other fighter's charId), and OPTIONALLY each act of the
--                      phase in order: { { id, charId, from = {x, y}, to = {x, y}, hp,
--                      act (Board.ACTIONS' name), targetId, tile (a pillaged village or chest),
--                      battles = { Board.battle... } } }
--   killed()           each unit the game killed since the last call (Board.fate, what
--                      UnitKill writes): { { id, charId, faction, killer|nil, turn|nil,
--                      phase|nil (when it fell: "player" | "enemy") } }, and each
--                      unit the watch could not read as { fault, id, charId, faction }. The
--                      only word on a blue or green loss: a unit gone from the field without
--                      one was unloaded by a script (a chapter's ending), or escaped, never
--                      killed
--   battle()           OPTIONAL: Board.battle, the last real battle as the game rolled it
--   bag()              OPTIONAL: each full-inventory answer since the last call: { charId,
--                      item (the new one), sent (the item that went: to the convoy, or
--                      discarded when `discard`), discard, why } (Bot.fullBag's); the record's
--                      `bag` and a `bag` trace event each
--   trace(event)       OPTIONAL: keep one event of the run's TRACE (below); an api that
--                      keeps it in a file names the file in info.trace, and so in the record
--   won(), lost()      the chapter advanced / the game-over screen is up
--   frames()           emulated frames so far, every frame sight's sandbox ran included
--   costs()            OPTIONAL: { cpu_s, sandbox_calls, save_s, load_s, run_s } so far; the
--                      record carries what the run itself spent
--   emit(line)         print one line to stdout
--   log(s)
-- Botrun.run(api) -> ok, why, record. It emits the record as ONE stdout line, `BOTRUN <json>`.
--
-- The TRACE (#510 step 9 F3, Nicolas 2026-10-27: "I want to be able to understand everything
-- about how it went"): one event per api.trace call, each with `t` its kind and `turn`:
--   start   the run's info, style and claims
--   phase   a phase's start (`phase` "player"|"enemy"): every on-field unit's id, charId,
--           faction, tile, HP and item ids
--   plan    a decision: the act chosen, and from the planner its judged score, the other plans
--           judged (`considered`), what it expects of the enemy phase (`predict`), every Visit
--           and Chest offered (`explore`), the tile each unit was sent to (`goals`), what the
--           plan does to each open goal (`worth`: id, kind, gold, worth, before, after), and whether a kept plan's act was played or a
--           surprise (`replan`, why) forced a new one
--   act     one act, either side: unit, from, to, the act and its target, the game's own
--           battle records (Board.battle: the forecast's numbers, every blow) and who fell
--   event   a change on the board no act names: a unit arriving, a recruit, items gained/lost
--   bag     a full inventory answered: the new item, the one that went, why
--   drop    the game gave one of ours a fallen unit's item: from, to (charIds), item
--   end     the BOTRUN record, last
-- Every number in it is read from the game; nothing is re-derived.

local M = {}

M.PREFIX = "BOTRUN "

-- What Bot.decide reads at a player phase's start, as one string: who stands where with what
-- HP, the objective's turns left, and the turns until the next claimed arrival.
function M.boardHash(Bot, board, objective, arrivals)
    local parts = {}
    for _, u in ipairs(board.units) do
        if u.onField then parts[#parts + 1] = string.format("%d@%d,%d:%d", u.id, u.x, u.y, u.hp) end
    end
    table.sort(parts)
    parts[#parts + 1] = "left=" .. tostring(objective and objective.turnsLeft or "-")
    parts[#parts + 1] = "arrive=" .. tostring(Bot.nextArrival(arrivals, board.turn) or "-")
    return table.concat(parts, ";")
end

local function byId(board)
    local out = {}
    for _, u in ipairs(board.units) do out[u.id] = u end
    return out
end

-- A phase's units, for the trace.
function M.snapshot(board)
    local out = {}
    for _, u in ipairs(board.units) do
        if u.onField then
            local items = {}
            for _, it in ipairs(u.items or {}) do items[#items + 1] = it.id end
            out[#out + 1] = { id = u.id, charId = u.charId, classId = u.classId,
                              faction = u.faction, x = u.x, y = u.y, hp = u.hp, items = items,
                              isBoss = u.isBoss or nil }
        end
    end
    return out
end

local function itemCounts(u)
    local n = {}
    for _, it in ipairs(u.items or {}) do n[it.id] = (n[it.id] or 0) + 1 end
    return n
end

-- What changed between two boards that no act names: a unit on the field now that was not
-- (an arrival, or a recruit when its character was on another side), and a blue unit's items.
function M.events(before, after)
    local was, side = {}, {}
    for _, u in ipairs(before.units) do
        was[u.id] = u
        if u.onField then side[u.charId .. "/" .. u.faction] = true end
    end
    local out = {}
    for _, u in ipairs(after.units) do
        local b = was[u.id]
        if u.onField and not (b and b.onField) then
            local from
            for _, f in ipairs({ "blue", "green", "red" }) do
                if f ~= u.faction and side[u.charId .. "/" .. f] then from = f end
            end
            out[#out + 1] = { kind = from and "recruit" or "arrive", id = u.id, charId = u.charId,
                              faction = u.faction, from = from, x = u.x, y = u.y }
        elseif u.faction == "blue" and b and b.onField and u.onField then
            local nb, na, gained, lost = itemCounts(b), itemCounts(u), {}, {}
            for id, c in pairs(na) do
                for _ = 1, c - (nb[id] or 0) do gained[#gained + 1] = id end
            end
            for id, c in pairs(nb) do
                for _ = 1, c - (na[id] or 0) do lost[#lost + 1] = id end
            end
            if #gained + #lost > 0 then
                table.sort(gained); table.sort(lost)
                out[#out + 1] = { kind = "items", id = u.id, charId = u.charId, gained = gained,
                                  lost = lost }
            end
        end
    end
    return out
end

local function actOf(a)
    return { unit = a.unit, act = a.act, x = a.move.x, y = a.move.y, target = a.target,
             why = a.why }
end

-- Units on the field before and gone after, with the fighter that downed them. A player-phase
-- action has one fight: the actor and its target are each other's killer. A unit that left its
-- side for ours (a Talk recruit: the game moves it to a blue slot) did not fall.
local function fallen(before, after, action)
    local now, out, blue = byId(after), {}, {}
    for _, u in ipairs(after.units) do
        if u.faction == "blue" and u.onField then blue[u.charId] = true end
    end
    for _, u in ipairs(before.units) do
        local n = now[u.id]
        local joined = u.faction ~= "blue" and blue[u.charId]
        if u.onField and not u.dead and (n == nil or n.dead) and not joined then
            local killer, killerId
            if action and u.id == action.unitId then
                killer, killerId = action.target, action.targetId
            end
            if action and u.id == action.targetId then
                killer, killerId = action.unit, action.unitId
            end
            out[#out + 1] = { id = u.id, charId = u.charId, faction = u.faction, killer = killer,
                              killerId = killerId,
                              ours = action ~= nil and u.id == action.targetId }
        end
    end
    return out
end

-- Every village and chest the run saw open, and what became of it (#510 step 9): the record of
-- how the planner's goals (goals.lua) played out.
--   open(list, turn, usable)  one read of sight.explorable(); a tile gone from it that we did
--                      not visit was closed by someone else (a pillage, an event). usable(t):
--                      whether a unit could use it now (the game's own check)
--   offered(list)      a plan's `explore`: each offer's standing chance to die
--   visited(a, turn)   our Visit or Chest act was played
--   failed(a, turn)    it was tried and the harness could not drive it (a full inventory's
--                      send-or-discard menu): the run ends there as a crash
--   summary()          per tile, in the order first seen: { x, y, kind, status = "visited" |
--                      "failed" | "closed" | "skipped" (offered, never played) | "unreached"
--                      (never offered), by, tried (the unit that failed), turn, offers, die =
--                      the lowest chance it was offered at }
--   explored()         the "x,y" tiles we visited or opened (Bot.candidates offers them no more)
--   leftOpen()         bot faults: each tile never explored that a unit could still use at the
--                      last read, { kind = "left_open", x, y, tile, offers }. ch03's chest behind
--                      a door went unopened in every attempt, silently, as "unreached"
--   closedBy(x, y, charId, loot)  an act of another side's unit named the tile (a pick:
--                      a pillage, or a thief's chest), and the item it gained doing so
--   dropped(d)         the game gave one of ours a fallen unit's item (api.drops: its own
--                      BATTLE_HandleItemDrop), d = { from, to, item }
--   fell(charId)       a unit of another side fell to one of ours
--   joined(party)      the game's party at the end, by charId: a chest whose thief is in it
--                      came to us with the thief (vanilla Ch3's Colm; Nicolas, 2026-10-30)
--   dropMissed()       the drop watch's faults: each chest a thief emptied whose thief then
--                      fell to one of ours with no drop of that item caught. popup.c marks the
--                      thief US_DROP_ITEM, so the game gave it: the watch missed it.
--                      { kind = "drop_missed", x, y, thief, item }; the record's
--                      `watch_faults` adds the death watch's, { kind = "death_unread", why,
--                      charId, faction, turn, phase }
--   missing()          the clean clear's rewards part: each tile not taken, { x, y, kind,
--                      why = its status, closed_by }. Taken = visited, or a chest whose
--                      thief the game then made drop that chest's item to one of ours
--                      (popup.c sets US_DROP_ITEM on the thief), or whose thief joined us
function M.exploreLog()
    local log, tiles, order = {}, {}, {}
    local drops, felled = {}, {}
    local function key(x, y) return x .. "," .. y end
    function log.open(list, turn, usable)
        local now = {}
        for _, t in ipairs(list) do
            local k = key(t.x, t.y)
            now[k] = true
            if not tiles[k] then
                tiles[k] = { x = t.x, y = t.y, kind = t.kind, offers = 0 }
                order[#order + 1] = k
            end
            tiles[k].usable = usable ~= nil and usable(t) or false
        end
        for _, k in ipairs(order) do
            local e = tiles[k]
            if not now[k] and not e.by and not e.closed then e.closed = turn end
        end
    end
    function log.offered(list)
        for _, o in ipairs(list or {}) do
            local e = tiles[key(o.x, o.y)]
            if e then
                e.offers = e.offers + 1
                if not e.die or o.die < e.die then e.die = o.die end
            end
        end
    end
    function log.visited(a, turn)
        local e = tiles[key(a.move.x, a.move.y)]
        if e then e.by, e.turn = a.unit, turn end
    end
    function log.failed(a, turn)
        local e = tiles[key(a.move.x, a.move.y)]
        if e then e.failed, e.turn = a.unit, turn end
    end
    function log.explored()
        local out = {}
        for k, e in pairs(tiles) do
            if e.by then out[k] = true end
        end
        return out
    end
    -- the "x,y" tiles closed before we took them (a pillage, an event), each to its kind: a
    -- reward that needs one is lost (goals.lua)
    function log.lost()
        local out = {}
        for k, e in pairs(tiles) do
            if not e.by and (e.closed or e.closedBy) then out[k] = e.kind end
        end
        return out
    end
    function log.leftOpen()
        local out = {}
        for _, k in ipairs(order) do
            local e = tiles[k]
            if e.usable and not (e.by or e.failed or e.closed) then
                out[#out + 1] = { kind = "left_open", x = e.x, y = e.y, tile = e.kind,
                                  offers = e.offers }
            end
        end
        return out
    end
    function log.closedBy(x, y, charId, loot)
        local e = tiles[key(x, y)]
        if e and not e.by then e.closedBy, e.loot = charId, loot end
    end
    function log.dropped(d) drops[#drops + 1] = d end
    function log.fell(charId) felled[charId] = true end
    local party = {}
    function log.joined(p) party = p end
    local function wonBack(e)
        if e.kind ~= "chest" or not e.closedBy or not e.loot then return false end
        if party[e.closedBy] then return true end
        for _, d in ipairs(drops) do
            if d.from == e.closedBy and d.item == e.loot then return true end
        end
        return false
    end
    function log.dropMissed()
        local out = {}
        for _, k in ipairs(order) do
            local e = tiles[k]
            if e.kind == "chest" and e.loot and felled[e.closedBy] and not wonBack(e) then
                out[#out + 1] = { kind = "drop_missed", x = e.x, y = e.y, thief = e.closedBy,
                                  item = e.loot }
            end
        end
        return out
    end
    function log.missing()
        local out = {}
        for _, s in ipairs(log.summary()) do
            if s.status ~= "visited" and not s.won_back then
                out[#out + 1] = { x = s.x, y = s.y, kind = s.kind, why = s.status,
                                  closed_by = s.closed_by }
            end
        end
        return out
    end
    function log.summary()
        local out = {}
        for _, k in ipairs(order) do
            local e = tiles[k]
            -- a chest a thief opened can stay in GetAvailableTileEventCommand's list (its
            -- terrain is emptied, its flag left): the act names it closed
            local status = (e.by and "visited") or (e.failed and "failed")
                or ((e.closed or e.closedBy) and "closed")
                or (e.offers > 0 and "skipped") or "unreached"
            out[#out + 1] = { x = e.x, y = e.y, kind = e.kind, status = status, by = e.by,
                              turn = e.turn or e.closed, offers = e.offers, die = e.die,
                              tried = e.failed, closed_by = e.closedBy,
                              won_back = wonBack(e) or nil }
        end
        return out
    end
    return log
end

-- A death's primary cause, in precedence order (#510 step 9, FR-005): the plan took a risk
-- above its style's cap; the killer arrived after the plan was made; the killer was on the
-- field but hidden from the plan; the plan saw the chance and lost the roll; anything else.
-- The one list montecarlo.py reads these names from.
M.CAUSES = { "over_cap", "reinforcement", "fog", "rng_tail", "other" }
-- What "other" was, by family: the plan's own reads failed it (a sandbox fault), or it read
-- the board right and could not see this death coming (a blindspot).
M.DETAILS = {
    missing_prediction = "sandbox_fault",    -- no committing plan, or none for this unit
    forecast_desync = "sandbox_fault",       -- the plan played this very strike and saw no death
    zero_multi_attacker = "blindspot",       -- several strikers the plan judged, at zero together
    unrevealed_killer = "blindspot",         -- a seen enemy the judged phase never sent at it
    player_phase_counter = "blindspot",      -- a counter the forecast said would not come
    noncombat = "blindspot",                 -- no fighter: an event or a phase-start tick
}

-- A missed reward's reason, from the explore log's status (exploreLog.summary): offered to a
-- unit and never taken; never offered; closed by another side first (a pillage, a thief); or
-- tried and the harness could not drive it (the run crashed there).
M.REWARD_REASONS = { skipped = "skipped", unreached = "unreachable", closed = "closed",
                     failed = "failed" }

-- d: a graded death ({ predicted, over_cap, flags, killer }); why: what the committing plan
-- judged of it ({ struck: its killer among the judged strikers, strikers: how many,
-- counters: the attack expected a counter }) -> cause, detail (nil unless "other").
function M.cause(d, why)
    local f = d.flags
    if d.over_cap then return "over_cap" end
    if f.reinforcement then return "reinforcement" end
    if f.fog then return "fog" end
    -- no fighter (an event's SET_HP, a phase-start poison tick): no plan's combat odds were
    -- about it, so it is neither the roll the plan lost nor a plan that failed to read
    if not d.killer and not d.killerId then return "other", "noncombat" end
    -- a zero is never a tail: it is a death the plan did not see (FR-005)
    if d.predicted and d.predicted > 0 then return "rng_tail" end
    local detail
    if d.predicted == nil then detail = "missing_prediction"
    elseif f.player_phase then detail = why.counters and "forecast_desync" or "player_phase_counter"
    elseif not why.struck then detail = "unrevealed_killer"
    elseif (why.strikers or 0) > 1 then detail = "zero_multi_attacker"
    else detail = "forecast_desync" end
    return "other", detail
end

-- Grade blue or green death `d` (its id, charId, faction, killer, killerId, phase) against
-- the plan that committed to the board it happened on (FR-003, FR-004): for a player-phase
-- death, the plan whose `action` struck (its counter's `die`); for an enemy-phase one, the
-- phase's last plan (its `predict`). `plan.snapshot` is the board when that plan was made,
-- `cap` the style's risk cap (nil until the planner has one), `gameOver` the charIds whose
-- death ends the game, `diedAt` (optional) each unit index of another side to the decision count
-- it fell at: one that fell at or after the plan's (`plan.ref`) is no killer from the snapshot,
-- its slot free for an arrival of the same generic charId. Unknown is nil, never zero: a death
-- with no plan behind it has no prediction, and so no over-cap, reinforcement or fog flag.
function M.grade(d, plan, action, cap, gameOver, board, diedAt)
    local playerPhase = d.phase == "player"
    local snap, known = {}, plan and plan.snapshot ~= nil
    for _, u in ipairs(plan and plan.snapshot or {}) do
        local at = diedAt and diedAt[u.id]
        if not (at and at >= plan.ref) then snap[u.id] = u end
    end
    local judged
    if playerPhase then
        if action and action.unitId == d.id then d.predicted = action.die end
    else
        for _, p in ipairs(plan and plan.predict or {}) do
            if p.id == d.id then judged = p; d.predicted = p.die end
        end
    end
    -- the killer: by unit index when the watch read one, and by charId -- FE8 reloads a freed
    -- slot, so an arrival can hold the index of a unit the snapshot saw die
    local function isKiller(u)
        return u.faction == "red" and (not d.killerId or u.id == d.killerId)
            and (not d.killer or u.charId == d.killer) and (d.killerId or d.killer) and true
    end
    local killers = {}
    for _, u in pairs(snap) do
        if isKiller(u) then killers[#killers + 1] = u end
    end
    local boss = false
    for _, u in ipairs(killers) do boss = boss or u.isBoss == true end
    for _, u in ipairs(board and board.units or {}) do
        if isKiller(u) and u.isBoss then boss = true end
    end
    local hidden = #killers > 0
    for _, u in ipairs(killers) do
        if plan.enemies and plan.enemies[u.id] then hidden = false end
    end
    local fought = (d.killer or d.killerId) and true or false
    d.flags = { player_phase = playerPhase, boss = boss }
    if known then
        d.flags.reinforcement = fought and #killers == 0
        d.flags.fog = hidden
    end
    d.cap = cap
    if d.predicted ~= nil and cap ~= nil then d.over_cap = d.predicted > cap end
    local struck, strikers = false, 0
    for _, id in ipairs(judged and judged.strikers or {}) do
        strikers = strikers + 1
        for _, u in ipairs(killers) do
            if u.id == id then struck = true end
        end
    end
    d.cause, d.detail = M.cause(d, { struck = struck, strikers = strikers,
                                     counters = action and action.f and action.f.counters })
    d.family = d.detail and M.DETAILS[d.detail]
    d.plan_ref = plan and plan.ref
    if d.faction == "green" then
        d.escort = false
        for _, c in ipairs(gameOver or {}) do
            if c == d.charId then d.escort = true end
        end
    end
    return d
end

function M.run(api)
    local Bot, Json = api.Bot, api.Json
    local style = Bot.applyClaims(api.claims or {}, api.style)
    style.villageGifts, style.houseGifts = api.villageGifts, api.houseGifts
    local unplayed = Bot.unplayed(api.claims or {})
    local skipped = {}
    for _, id in ipairs(unplayed) do skipped[id] = true end
    local played = {}
    for _, c in ipairs(api.claims or {}) do
        if not skipped[c.id] then played[#played + 1] = c.id end
    end
    local rec = { game = api.info.game, rom_hash = api.info.rom_hash, chapter = api.info.chapter,
                  mode = api.info.mode, seed = api.info.seed, campaign = api.info.campaign,
                  attempt = api.info.attempt, style = api.style,
                  claims_played = played, claims_unplayed = unplayed, deaths = {}, kills = {},
                  deployed = {}, bot_faults = {}, watch_faults = {}, thefts = {},
                  plans = { made = 0, kept = 0 }, bag = {}, board_repeats = 0,
                  seize_skips = {}, stall_events = {}, anomalies = {} }
    local explore = M.exploreLog()
    -- what the graded record reads (FR-003..007): the charIds whose death ends the game
    -- (sight.objective.gameOver), every charId of another side that fell, every charId a
    -- Talk was offered to, and the turn each green unit was first seen at a phase's start
    local gameOver, felled, talked, greenSeen = {}, {}, {}, {}
    -- per unit index of another side, the decision count when it fell: a slot the game freed
    -- after a plan's snapshot and reloaded with an arrival is not the snapshot's unit
    local diedAt = {}
    -- whether the planner plays: only its plans record the Talks and rewards it was offered
    local planned = api.Planner ~= nil and style.aggression ~= "greedy"
    -- each with its turn: montecarlo.py's keep_trace gives it the story command (`narrate`)
    -- once the trace is filed where it will stay
    local function anomaly(a) rec.anomalies[#rec.anomalies + 1] = a end
    -- whether this turn moved the chapter on: a lord moved, a kill, a Visit, Talk or Chest
    -- (FR-007's stall is three player phases in a row without one)
    local progressed, idle = false, 0
    -- the clean clear's recruits part, read from the game's party (api.party: the game's own
    -- MakePrepUnitList, i.e. IsUnitInCurrentRoster), never from the unit arrays: owed =
    -- api.recruits() less the party at the first read; joined = owed and in the party at the
    -- run's end. Vanilla's endings leave an unrecruited one as a blue entry the roster test
    -- keeps out (EventScr_StrictLoadUniqueAlly: SET_HP 0 sets US_DEAD)
    local owed = nil
    local startFrame = api.frames()
    local startCosts = api.costs and api.costs() or {}
    local turn = 0
    local function trace(ev)
        if api.trace then
            ev.turn = ev.turn or turn
            api.trace(ev)
        end
    end
    -- each full-bag answer the harness gave, and each drop the game gave one of ours, since
    -- the last look (api.bag, api.drops)
    local function bagged()
        for _, b in ipairs(api.bag and api.bag() or {}) do
            b.turn = turn
            rec.bag[#rec.bag + 1] = b
            trace({ t = "bag", charId = b.charId, item = b.item, sent = b.sent,
                    discard = b.discard, why = b.why })
        end
        for _, d in ipairs(api.drops and api.drops() or {}) do
            explore.dropped(d)
            trace({ t = "drop", from = d.from, to = d.to, item = d.item })
        end
        for _, t in ipairs(api.thefts and api.thefts() or {}) do
            t.turn = turn
            rec.thefts[#rec.thefts + 1] = t
            trace({ t = "theft", thief = t.thief, from = t.from, item = t.item, rank = t.rank,
                    spoils = t.spoils })
        end
    end
    local lastBoard
    local function changes(after)
        if api.recruits and not owed then
            local party = {}
            for _, c in ipairs(api.party()) do party[c] = true end
            owed = {}
            for _, c in ipairs(api.recruits()) do
                if not party[c] then owed[#owed + 1] = c end
            end
        end
        if lastBoard then
            for _, e in ipairs(M.events(lastBoard, after)) do
                e.t = "event"
                trace(e)
            end
        end
        lastBoard = after
    end

    -- A blue or green unit lost spoils the clear (design 11: vanilla Ch6's Orion's Bolt is
    -- given only if its three green villagers live), so both are deaths; a red one is a kill.
    -- A blue or green death is one the game ran UnitKill on (api.killed); `list`, the board's
    -- falls, gives the red kills and a killer where the watch saw no fight. A slot the watch
    -- could not read is a watch fault, never a guess.
    -- Each blue or green death is graded against the plan that committed to its board (plan,
    -- and for a player-phase death the action that struck: M.grade).
    local deathFaults = {}
    local function record(list, phase, plan, action)
        local seen = {}
        for _, d in ipairs(list) do seen[d.id] = d end
        for _, k in ipairs(api.killed()) do
            if k.fault then
                deathFaults[#deathFaults + 1] = { kind = "death_unread", why = k.fault,
                                                  charId = k.charId, faction = k.faction,
                                                  turn = turn, phase = phase }
            elseif k.faction == "blue" or k.faction == "green" then
                local d = seen[k.id] or {}
                local g = M.grade({ id = k.id, charId = k.charId, faction = k.faction,
                                    turn = k.turn or turn, killer = k.killer or d.killer,
                                    killerId = k.killerId or d.killerId,
                                    phase = k.phase or phase }, plan, action, nil, gameOver,
                                  lastBoard, diedAt)
                rec.deaths[#rec.deaths + 1] = g
                if g.faction == "green" and greenSeen[g.id] == g.turn then
                    -- a green lost on the turn it was first seen: the plan had one player
                    -- phase to save it
                    anomaly({ kind = "same_turn_green", turn = g.turn, charId = g.charId })
                elseif g.faction == "green" and not greenSeen[g.id] then
                    -- one no player phase ever saw: no plan could have saved it
                    anomaly({ kind = "unseen_green", turn = g.turn, charId = g.charId })
                end
            else
                felled[k.charId], diedAt[k.id] = true, rec.plans.made
                -- a kill is progress when the player phase made it (FR-007's stall counts
                -- player phases), never an enemy walking onto a counter
                progressed = progressed or (k.phase or phase) == "player"
            end
        end
        for _, d in ipairs(list) do
            if d.faction ~= "blue" and d.faction ~= "green" then
                felled[d.charId], diedAt[d.id] = true, diedAt[d.id] or rec.plans.made
                progressed = progressed or phase == "player"
            end
        end
        -- a red one gone with the fighter that downed it: that fighter's kill
        for _, d in ipairs(list) do
            if d.faction == "red" and d.killer then
                local k = tostring(d.killer)
                rec.kills[k] = (rec.kills[k] or 0) + 1
                if d.ours then explore.fell(d.charId) end
            end
        end
    end
    local function finish(outcome, why, fault)
        rec.outcome, rec.turns, rec.why = outcome, turn, why
        rec.frames = api.frames() - startFrame
        if api.costs then
            -- what the run spent: each figure the difference since it started
            local now = api.costs()
            rec.costs = {}
            for k, v in pairs(now) do
                if type(v) == "table" then
                    rec.costs[k] = {}
                    for n, c in pairs(v) do rec.costs[k][n] = c - ((startCosts[k] or {})[n] or 0) end
                else
                    rec.costs[k] = v - (startCosts[k] or 0)
                end
            end
        end
        local party = {}
        local ok, list = pcall(api.party or function() return {} end)
        for _, c in ipairs(ok and list or {}) do party[c] = true end
        explore.joined(party)
        rec.explore = explore.summary()
        local missing = "unchecked"
        if owed then
            rec.recruits = { owed = owed, joined = {} }
            missing = {}
            for _, c in ipairs(owed) do
                local list = party[c] and rec.recruits.joined or missing
                list[#list + 1] = c
            end
        end
        -- a theft spoils the clear only above the stat boosters (ADR 0379); the rest are kept
        -- in rec.thefts
        local stolen = {}
        for _, t in ipairs(rec.thefts) do
            if t.spoils then stolen[#stolen + 1] = t end
        end
        rec.clear = { won = outcome == "won", lost = rec.deaths, recruits_missing = missing,
                      rewards_missing = explore.missing(), stolen = stolen }
        local held = rec.clear.won and #rec.deaths == 0 and #rec.clear.rewards_missing == 0
            and #stolen == 0
        if not held or (owed and #missing > 0) then rec.clean = false
        elseif owed then rec.clean = true end
        -- The graded outcomes (FR-006, FR-007), beside the clean clear. `clean` is derived
        -- from them and descriptive only: no decision reads it (FR-008).
        rec.greens = { escort_deaths = {}, allied_deaths = {} }
        -- a recruit that joined and then fell is out of the party too: its death is a player
        -- death, and its reason says so (vanilla Ch5 attempt 1: Joshua, turn 9)
        local fellOurs = {}
        for _, d in ipairs(rec.deaths) do
            if d.faction == "blue" then
                fellOurs[d.charId] = true
                rec.first_death_turn = math.min(rec.first_death_turn or d.turn, d.turn)
            else
                local list = d.escort and rec.greens.escort_deaths or rec.greens.allied_deaths
                list[#list + 1] = d.charId
            end
        end
        if owed then
            rec.missed_recruits = {}
            for _, c in ipairs(missing) do
                rec.missed_recruits[#rec.missed_recruits + 1] = { charId = c,
                    reason = (fellOurs[c] and "died_after_joining")
                        or (felled[c] and "killed_before_talk")
                        or (talked[c] and "talk_skipped")
                        or (planned and "not_reached") or "unknown" }
            end
        end
        rec.missed_rewards = {}
        for _, t in ipairs(rec.clear.rewards_missing) do
            -- M.REWARD_REASONS. Only the planner counts offers (its plans' `explore`), so a run
            -- without one cannot tell skipped from unreachable
            rec.missed_rewards[#rec.missed_rewards + 1] = { x = t.x, y = t.y, kind = t.kind,
                reason = planned and M.REWARD_REASONS[t.why] or "unknown",
                closed_by = t.closed_by }
        end
        if outcome == "won" then rec.turns_to_win = turn end
        if outcome == "stuck" then anomaly({ kind = "stall_abort", turn = turn }) end
        -- a win put off with nothing left the win would close (a justified skip waits for a goal)
        for _, k in ipairs(outcome == "won" and rec.seize_skips or {}) do
            if not k.justified then
                anomaly({ kind = "seize_delay", turn = k.turn, delay = turn - k.turn })
                break
            end
        end
        if outcome == "won" then
            for _, f in ipairs(explore.leftOpen()) do rec.bot_faults[#rec.bot_faults + 1] = f end
        end
        rec.watch_faults = explore.dropMissed()
        for _, f in ipairs(deathFaults) do rec.watch_faults[#rec.watch_faults + 1] = f end
        -- Whether the environment held (#510 step 9 plan, T009): a crash, a timeout or a
        -- misread board makes the record unreadable, never death-free. Outcome-dependent when
        -- play had begun (a unit was deployed): which runs fail then can follow what happened
        -- in them, so dropping them could bias the rest. A bot fault (a tile left open) is
        -- the bot's own play, measured, not the environment's.
        fault = fault or (outcome == "crashed" and "crash")
            or (#rec.watch_faults > 0 and "watch") or nil
        rec.env_status = fault and { fault = fault, outcome_dependent = #rec.deployed > 0 }
            or "clean"
        rec.instrument = api.info.instrument   -- the bot and suite version (montecarlo.py)
        rec.trace = api.info.trace   -- the trace's file, when the api keeps one
        trace({ t = "end", record = rec })
        api.emit(M.PREFIX .. Json.encode(rec))
        api.log(string.format("botrun: %s on turn %d (%s)", outcome, turn, why))
        return outcome == "won" or outcome == "lost" or outcome == "stuck", why, rec
    end

    local function play()
        api.seed(api.info.seed)
        local sight = api.sight()
        -- the units whose death ends the game, as the game says (sight.objective.gameOver)
        trace({ t = "start", info = api.info, style = api.style, claims_played = played,
                claims_unplayed = unplayed,
                game_over = sight.objective and sight.objective.gameOver })
        gameOver = sight.objective and sight.objective.gameOver or {}
        local lords = {}
        for _, c in ipairs(gameOver) do lords[c] = true end
        local seen, waitUntil = {}, nil
        -- the plan that committed to the enemy phase: this phase's last (FR-003)
        local commit
        -- each red unit's tile at every phase start, for a bait loop; the turn of the last
        -- seize skip recorded (one a turn)
        local tiles, baited, skipTurn = {}, {}, nil
        -- the tiles units were sent to explore: they outlive the turn's last, empty plan (no
        -- unit left to act returns none), so the next turn keeps the same senders
        local sent
        -- the plan being played this phase: its next act's index, and the board before the
        -- last act it played (Planner.surprise compares the two)
        local playing, nextAct, before
        while true do
            if api.won() then return "won", "the chapter advanced" end
            if api.lost() then return "lost", "game over" end
            local board = api.board()
            turn = board.turn
            sight.newPhase()
            if #rec.deployed == 0 then
                for _, u in ipairs(board.units) do
                    if u.faction == "blue" and u.onField then
                        rec.deployed[#rec.deployed + 1] = u.charId
                    end
                end
            end
            local h = M.boardHash(Bot, board, sight.objective, style.arrivals)
            local stalled = false
            if seen[h] and not (waitUntil and turn < waitUntil) then
                waitUntil = sight.nextTurnEvent(turn)
                if not waitUntil then
                    -- the first repeat is a stall: the planner must change the board (its
                    -- opts.stalled); a board that comes round again after that is stuck
                    if seen[h] == "stalled" or not planned then
                        for _, l in ipairs(Bot.explain(board, sight, style)) do api.log("stuck: " .. l) end
                        return "stuck", "a player phase began on a board seen before, and no turn "
                            .. "event is left to change it"
                    end
                    stalled = true
                    rec.board_repeats = rec.board_repeats + 1
                    api.log(string.format("botrun: board repeats on turn %d; the plan must change it",
                        turn))
                else
                    api.log(string.format("botrun: board repeats on turn %d; a turn event is due on "
                        .. "turn %d", turn, waitUntil))
                end
            end
            seen[h] = stalled and "stalled" or seen[h] or true
            changes(board)
            commit = nil
            for _, u in ipairs(board.units) do
                if u.onField and u.faction == "green" then
                    greenSeen[u.id] = greenSeen[u.id] or turn
                elseif u.onField and u.faction == "red" and not baited[u.id] then
                    -- an enemy drawn back and forth between two tiles for four turns
                    local t = tiles[u.id] or {}
                    t[#t + 1] = u.x .. "," .. u.y
                    tiles[u.id] = t
                    local n = #t
                    if n >= 4 and t[n] == t[n - 2] and t[n - 1] == t[n - 3]
                        and t[n] ~= t[n - 1] then
                        baited[u.id] = true
                        anomaly({ kind = "bait_loop", turn = turn, charId = u.charId, id = u.id })
                    end
                end
            end
            if sight.explorable then
                -- whether any unit could use each tile now: every unit can act at phase start
                explore.open(sight.explorable(), turn, function(t)
                    for _, u in ipairs(board.units) do
                        if u.faction == "blue" and u.onField
                            and sight.canExplore(u, t.x, t.y, t.kind) then return true end
                    end
                    return false
                end)
            end
            trace({ t = "phase", phase = "player", units = M.snapshot(board) })
            playing = nil
            while true do
                -- one decision's reads in one save/load (sight.batch), when the sight batches
                -- the planner plays every style but greedy, the old clear bot (bot.lua)
                local function decide()
                    if planned then
                        local why
                        if playing then
                            why = api.Planner.surprise(playing, nextAct - 1, before, board,
                                sight.legal)
                            if not why then
                                local a = playing.acts[nextAct]
                                nextAct = nextAct + 1
                                rec.plans.kept = rec.plans.kept + 1
                                trace({ t = "plan", kept = true, choice = actOf(a) })
                                api.log(string.format("plan: keep 0x%02X %s @%d,%d", a.unit, a.act,
                                    a.move.x, a.move.y))
                                return a
                            end
                            api.log("plan: replan, " .. why)
                        end
                        local replan = playing and why
                        local a, plan = api.Planner.plan(Bot, board, sight, style,
                                                         { stalled = stalled, sent = sent,
                                                           explored = explore.explored(),
                                                           lost = explore.lost() })
                        stalled = false   -- one changed act is the change; the rest plans freely
                        rec.plans.made = rec.plans.made + 1
                        if plan then
                            sent = plan.goals
                            -- the board this plan committed to, and its decision index (a
                            -- death's plan_ref)
                            plan.ref, plan.snapshot = rec.plans.made, M.snapshot(board)
                            commit = plan
                            for _, c in ipairs(plan.talks or {}) do talked[c] = true end
                            if plan.seizable and not plan.seizes and skipTurn ~= turn then
                                -- the win was on offer and the plan did something else: only
                                -- a goal the win would close justifies it
                                skipTurn = turn
                                local ledger = {}
                                for _, g in ipairs(plan.goalWorth or {}) do
                                    if g.kind ~= "objective" and (g.before or 0) > 0 then
                                        ledger[#ledger + 1] = g.id
                                    end
                                end
                                local justified = #ledger > 0
                                rec.seize_skips[#rec.seize_skips + 1] = { turn = turn,
                                    ledger = ledger, justified = justified,
                                    reason = justified and "goals the win would close are open"
                                        or "nothing left the win would close" }
                                if not justified then
                                    rec.stall_events[#rec.stall_events + 1] = { turn = turn,
                                        kind = "unjustified_seize_skip" }
                                end
                            end
                        end
                        explore.offered(plan and plan.explore)
                        trace({ t = "plan", choice = a and actOf(a), replan = replan,
                                ref = plan and plan.ref,
                                judged = plan and plan.judged, kind = plan and plan.kind,
                                considered = plan and plan.considered,
                                predict = plan and plan.predict,
                                explore = plan and plan.explore, goals = plan and plan.goals,
                                worth = plan and plan.goalWorth,
                                win_fell = plan and plan.winFell })
                        playing, nextAct = a and plan, 2
                        if plan and a then
                            local said = {}
                            for _, x in ipairs(plan.strikes or {}) do
                                said[#said + 1] = string.format("%X>%X", x.enemy, x.target)
                            end
                            api.log(string.format("plan: 0x%02X %s @%d,%d judged %.0f of %d; strikes %s",
                                a.unit, a.act, a.move.x, a.move.y, plan.judged or 0, #(plan.acts or {}),
                                table.concat(said, " ")))
                        end
                        return a
                    end
                    local a = Bot.decide(board, sight, style)
                    trace({ t = "plan", choice = a and actOf(a), policy = style.aggression })
                    return a
                end
                local action
                if sight.batch then action = sight.batch(decide) else action = decide() end
                if not action then break end
                local done, why = api.act(action)
                bagged()
                if done == false and (action.act == "visit" or action.act == "chest") then
                    explore.failed(action, turn)
                end
                if done == false then
                    record({}, "player", playing, action)   -- the deaths the act caused first
                    return "crashed", "the harness could not perform " .. action.act
                        .. (why and (": " .. why) or "")
                end
                if action.act == "visit" or action.act == "chest" then
                    explore.visited(action, turn)
                end
                if action.act == "visit" or action.act == "chest" or action.act == "talk" then
                    progressed = true
                end
                local battle = action.act == "attack" and api.battle and api.battle() or nil
                local after = api.board()
                sight.refresh()
                before = board
                local actor = byId(after)[action.unitId]
                local from = byId(board)[action.unitId]
                local fell = fallen(board, after, action)
                if lords[action.unit] and from
                    and (from.x ~= action.move.x or from.y ~= action.move.y) then
                    progressed = true
                end
                record(fell, "player", playing, action)
                trace({ t = "act", phase = "player", unit = action.unit, id = action.unitId,
                        from = from and { x = from.x, y = from.y }, to = action.move,
                        act = action.act, target = action.target, battles = { battle },
                        fell = fell })
                changes(after)
                if done == "noseize" then
                    -- The bot seizes only with a unit the game's CanUnitSeize allows, on the tile
                    -- its location event names: a menu without Seize there is the two disagreeing.
                    return "crashed", "CanUnitSeize allowed it, but the menu offered no Seize"
                elseif actor and actor.onField and not actor.acted and after.turn == turn
                    and after.phase == "blue" and not api.won() then
                    -- The bot decides from the board, so an action that leaves its unit able to
                    -- act would be asked for again, forever.
                    return "crashed", "the action left its unit able to act"
                end
                board = after
                if api.won() then return "won", "the chapter advanced" end
                if api.lost() then return "lost", "game over" end
                if board.phase ~= "blue" or board.turn ~= turn then break end
            end
            local before = api.board()
            -- what the last plan expected of this enemy phase, beside what it did
            for _, p in ipairs(commit and commit.predict or {}) do
                if p.strikes > 0 then
                    api.log(string.format("plan: 0x%02X @%d,%d hp %d: %d strikes, die %.2f, taken %.1f",
                        p.charId, p.x, p.y, p.hp, p.strikes, p.die, p.taken))
                end
            end
            changes(before)
            trace({ t = "phase", phase = "enemy", units = M.snapshot(before) })
            local phase, deaths, acts = api.endPhase()
            bagged()
            local was, now = byId(before), byId(api.board())
            for _, a in ipairs(acts or {}) do
                if a.tile then
                    -- the item the unit gained by it: a thief's chest, which it drops if it falls
                    local b, n, loot = was[a.id], now[a.id], nil
                    if b and n then
                        local had = itemCounts(b)
                        for id, c in pairs(itemCounts(n)) do
                            if c > (had[id] or 0) then loot = id end
                        end
                    end
                    explore.closedBy(a.tile.x, a.tile.y, a.charId, loot)
                end
                trace({ t = "act", phase = "enemy", unit = a.charId, id = a.id, from = a.from,
                        to = a.to, hp = a.hp, act = a.act, targetId = a.targetId, tile = a.tile,
                        battles = a.battles })
            end
            trace({ t = "fell", phase = "enemy", fell = deaths or {} })
            for _, d in ipairs(deaths or {}) do
                api.log(string.format("plan: died 0x%02X to 0x%02X", d.charId or 0, d.killer or 0))
            end
            -- the watcher's falls and any it missed, read before any return so a lost run
            -- carries every death; record keeps the blue and green ones the game killed
            local all, counted = {}, {}
            for _, d in ipairs(deaths or {}) do all[#all + 1] = d; counted[d.id] = true end
            for _, d in ipairs(fallen(before, api.board(), nil)) do
                if not counted[d.id] then all[#all + 1] = d end
            end
            record(all, "enemy", commit, nil)
            if phase == "gameover" then return "lost", "game over in the enemy phase" end
            if phase == "ended" then
                if api.won() then return "won", "the chapter advanced in the enemy phase" end
                return "lost", "the chapter ended without advancing"
            end
            if phase ~= "player" then
                return "crashed", "the enemy phase never returned control", "timeout"
            end
            idle = progressed and 0 or idle + 1
            if idle > 0 and idle % 3 == 0 then
                rec.stall_events[#rec.stall_events + 1] = { turn = turn, kind = "idle_3" }
            end
            progressed = false
        end
    end

    local ok, outcome, why, fault = pcall(play)
    if not ok then return finish("crashed", "Lua error: " .. tostring(outcome)) end
    return finish(outcome, why, fault)
end

return M
