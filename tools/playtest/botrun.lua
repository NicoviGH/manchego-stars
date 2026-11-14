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
--   lost     the game-over screen came up (api.lost), or the enemy phase reached it, or our
--            own act felled a unit whose death ends the game (M.LOST_IN_PLAYER_PHASE): the
--            game's game-over event waits for the death quote and the act to end, so its
--            screen is not up when the act returns
--   stuck    a player phase began on a board already seen this run, and nothing ahead can
--            change it -- for the planner, a board that comes round again AFTER the planner was
--            made to change it once (its first repeat: opts.stalled, counted in the record's
--            `board_repeats`): the hash holds every on-field unit's id, tile and HP, the
--            objective's turns left, and the turns until the next arrival a reinforcements claim cites --
--            everything Bot.decide reads -- and the game's own turn-event check
--            (sight.nextTurnEvent) finds no event still to fire. A repeat with an event ahead
--            waits for that turn. Also `stuck`: M.QUIET_BOUND player phases in a row with no progress
--            (an event, or a new low in turns-to-goal: see the progress state in M.run), once the
--            same turn-event check finds nothing to wait for and no Survive turns are counting down
--            (#510 fwd1 item C, ADR 0403).
--   crashed  anything the run could not do: an action or enemy phase the harness could not
--            drive, an action that left its unit able to act, a Seize the menu refused though
--            the game's CanUnitSeize allowed it, or any Lua error (a sight call that never
--            returned, a policy fault), or a sandbox leak the guard logged (api.leaks: the
--            record's `leaks`, its `why` saying what the game ended as). The record is still
--            emitted.
--   timeout  one decision ran more than M.DECISION_FRAMES frames of game code in its
--            simulations (sight.watch asks before each game call): the record's `timeout` =
--            { turn, frames, limit, stage, plans_judged, phases } (the last three the
--            planner's opts.at: where it was). No game result; the record is still emitted.
-- There is no turn cap. The "no progress" rules are the two `stuck` ones: a board that cannot
-- change any more, and M.QUIET_BOUND player phases that gained nothing.
--
-- api (harness.lua builds it; test_botrun.lua fakes it):
--   Bot, Json          bot.lua and json.lua, loaded by the caller
--   Planner            OPTIONAL: planner.lua; when given it plays every style but greedy, and
--                      a plan's acts are played in turn until Planner.surprise calls for a new
--                      one (the record's `plans`: made, acts played from a kept one, the enemy
--                      phases they judged, and the uncertain kills they left to the average past
--                      Planner.BRANCH: every plan judged, not only the ones played)
--   info = { game, rom_hash, chapter, mode, seed, campaign, attempt, team, dice_advanced,
--                      instrument }  what the record names; instrument = the bot hash and suite
--                      version (PT_INSTRUMENT) the run by; campaign, attempt and dice_advanced
--                      (the RNG draws the attempt was advanced, ADR 0404) only when campaign.lua
--                      plays it
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
--   leaks()            OPTIONAL: the sandbox leaks logged since the last ask, as lines, the log
--                      emptied (PT_LEAKGUARD; sight.lua M.leaks): any fails the attempt
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
--                      only word on a loss or a kill, of any faction: a unit gone from the
--                      field without one was unloaded by a script (a chapter's ending, a
--                      recruit a turn event takes away), or escaped, never killed
--   battle()           OPTIONAL: Board.battle, the last real battle as the game rolled it
--   bag()              OPTIONAL: each full-inventory answer since the last call: { charId,
--                      item (the new one), sent (the item that went: to the convoy, or
--                      discarded when `discard`), discard, why } (Bot.fullBag's); the record's
--                      `bag` and a `bag` trace event each
--   dice()             OPTIONAL: the game's RNG words { s0, s1, s2 } (Sight.dice): the record's
--                      `dice_start` and each `progress` trace line's `rn` (the words at the
--                      start of that player phase)
--   trace(event)       OPTIONAL: keep one event of the run's TRACE (below); an api that
--                      keeps it in a file names the file in info.trace, and so in the record
--   won(), lost()      the chapter advanced / the game-over screen is up
--   frames()           emulated frames so far, every frame sight's sandbox ran included
--   costs()            OPTIONAL: { cpu_s, sandbox_calls, save_s, load_s, run_s } so far; the
--                      record carries what the run itself spent
--   emit(line)         print one line to stdout
--   log(s)
--   diag               OPTIONAL: a diagnostic replay (FR-019, below): { ref, mode = "force" |
--                      "full_info" | "deep", force = { Planner.key... } (force only), failure =
--                      { charId, turn }, run = { game, chapter, seed, attempt } (the original
--                      attempt's), original = the original attempt's trace events, decoded }
--   pinned(ref, board) OPTIONAL, with diag: keep the game's state at the pinned decision (a
--                      board fixture: botrun's own memory is not in it) and the board that
--                      decision read (M.snapshot) beside it; returns the state's file
--   reload(file)       OPTIONAL, with pinned: load that file back and read the board there;
--                      the DIAG line's `pinned_board` says whether it is the pinned board
--   check_pinned       OPTIONAL: a kept decision state (a suite snapshot, PR-G T084). The run
--                      loads it through reload, emits ONE `PINNED <json>` line, { file, board },
--                      and plays nothing: no record, no DIAG line
-- Botrun.run(api) -> ok, why, record. It emits the record as ONE stdout line, `BOTRUN <json>`.
--
-- A DIAGNOSTIC REPLAY (#510 step 9 PR F, T074): the attempt is played again from the same start
-- with the same seed, style and budgets, which reproduces it: 156 of 156 reruns in the stores
-- traced identically (2026-11-07). Lua seeds its string hash per process, so a `pairs` over
-- string keys that picks a winner would break that; nothing is assumed, then: every phase
-- snapshot, act and choice up to decision `ref` is compared with the original trace's, and a
-- replay that leaves it is `matched = false`, never a witness. At `ref` the planner's own plan
-- (the baseline) and the diagnostic's are made from the same board with the same budget left
-- (only the baseline's lookahead is charged, as the original was): `force` plays the given
-- keys in order (an act Bot.candidates never offered is built from its key: missing_action's
-- witness), `deep` asks the planner with opts.diag = "deep", `full_info` asks it inside
-- sight.fullInfo, never inside a batch, over the acts the fogged board offers (it knows more,
-- it may do no more). A replay that leaves its original stops there; one that reaches its pin
-- plays on to the end of the failure's turn and stops. It never writes what production reads:
-- no BOTRUN line, no record handed back (the retry memory and campaign.lua's endpoint read
-- it), only ONE `DIAG <json>` line:
-- { run, ref, mode, matched, baseline, planned (the diagnostic's plan), chosen (its acts
-- actually played), broken (its first act not played), differs, failure, avoided (the
-- diagnostic's plan played whole, the failure's unit alive at the end of its turn, and no other
-- blue or green unit lost in its place: `traded`), outcome, why, unoffered (forced keys never
-- offered), pinned_board, trace }.
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
--   drop    the game gave a player unit a fallen unit's item: from, to (charIds), item
--   progress  a player phase's progress, in the planner's styles only (#510 fwd1 item C, ADR
--           0403). Two rules read it: `quiet` ends the attempt `stuck` (rule 2) and a goal's own
--           readings stall its ledger row (rule 1, `quietGoals`). `events` (the kinds this
--           player phase made: kill, visit,
--           chest, talk, door, wall, seize), `near` (the goal ids at a new low in turns-to-goal at
--           the next phase's first plan; "objective" or a ledger row's id), `quiet` (the player
--           phases in a row without either, this one included). The record's `progress` sums
--           it: { quiet_max, quiet_last, events_quiet_max (events only), phases }
--   end     the BOTRUN record, last
-- Every number in it is read from the game; nothing is re-derived.

local M = {}

M.PREFIX = "BOTRUN "
M.DIAG_PREFIX = "DIAG "
M.PINNED_PREFIX = "PINNED "

-- Deep equality of two decoded JSON values (the replay's events against the original trace's)
local function same(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return a == b end
    for k, v in pairs(a) do
        if not same(v, b[k]) then return false end
    end
    for k in pairs(b) do
        if a[k] == nil then return false end
    end
    return true
end

-- What a replay must reproduce of its original trace before the pinned decision `ref`: every
-- phase snapshot, every act, and every decision's choice (its other fields are the planner's
-- working, which a newer planner may add to without changing the play). Returns the watch:
-- see(ev) for each event the replay traces; at(choice) at the pinned decision: whether the
-- replay matched so far, every original event before it seen, and the baseline chose what the
-- original did there; why, the first difference.
function M.matcher(original, ref, Json)
    local function shape(ev)
        if ev.t == "plan" then
            return { t = ev.t, turn = ev.turn, choice = ev.choice, kept = ev.kept, ref = ev.ref }
        end
        return ev
    end
    local want, pinned = {}, nil
    for _, ev in ipairs(original or {}) do
        if ev.t == "plan" and ev.ref == ref then pinned = ev; break end
        if ev.t == "phase" or ev.t == "act" or ev.t == "plan" then want[#want + 1] = shape(ev) end
    end
    local w = { seen = 0 }
    function w.see(ev)
        if w.done or w.why or not (ev.t == "phase" or ev.t == "act" or ev.t == "plan") then return end
        w.seen = w.seen + 1
        local got, exp = Json.decode(Json.encode(shape(ev))), want[w.seen]
        if not exp then
            w.why = string.format("event %d (%s) is past the original's decision %d", w.seen,
                ev.t, ref)
        elseif not same(got, exp) then
            w.why = string.format("event %d (%s, turn %s) differs from the original's", w.seen,
                ev.t, tostring(ev.turn))
        end
    end
    function w.at(choice)
        if not w.why and not pinned then
            w.why = "the original trace has no decision " .. tostring(ref)
        elseif not w.why and w.seen ~= #want then
            w.why = string.format("the replay reached decision %d after %d events, the original "
                .. "after %d", ref, w.seen, #want)
        elseif not w.why and not same(Json.decode(Json.encode({ c = choice })).c, pinned.choice) then
            w.why = "the baseline's choice at the pinned decision differs from the original's"
        end
        w.done = true   -- past the pin the replay is meant to differ
        return not w.why
    end
    return w
end

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
             why = a.why, canto = a.canto }
end

-- Units on the field before and gone after, with the fighter that downed them. A player-phase
-- action has one fight: the actor and its target are each other's killer. A unit that left its
-- side for the player's (a Talk recruit: the game moves it to a blue slot) did not fall.
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
--   dropped(d)         the game gave a player unit a fallen unit's item (api.drops: its own
--                      BATTLE_HandleItemDrop), d = { from, to, item }
--   fell(charId)       a unit of another side fell to a player unit
--   joined(party)      the game's party at the end, by charId: a chest whose thief is in it
--                      came to us with the thief (vanilla Ch3's Colm; Nicolas, 2026-10-30)
--   dropMissed()       the drop watch's faults: each chest a thief emptied whose thief then
--                      fell to a player unit with no drop of that item caught. popup.c marks the
--                      thief US_DROP_ITEM, so the game gave it: the watch missed it.
--                      { kind = "drop_missed", x, y, thief, item }; the record's
--                      `watch_faults` adds the death watch's, { kind = "death_unread", why,
--                      charId, faction, turn, phase }
--   missing()          the clean clear's rewards part: each tile not taken, { x, y, kind,
--                      why = its status, closed_by }. Taken = visited, or a chest whose
--                      thief the game then made drop that chest's item to a player unit
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
-- `stalled` is set by `finish`, not by the log: the tile's goal row was a stalled ROW (goals.lua:
-- no unit neared it over M.GOAL_QUIET waiting player phases) in the last plan made, so the win did not wait
-- for it (ADR 0403). It overrides the log's word for that tile. A missed recruit's reason is
-- `stalled` the same way (its `recruit:` row), after left_map and before talk_skipped.
M.REWARD_REASONS = { skipped = "skipped", unreached = "never_offered", closed = "closed",
                     failed = "failed" }

M.LOST_IN_PLAYER_PHASE = "game over in the player phase"

-- Player phases in a row with no progress that end an attempt `stuck` (#510 fwd1 item C, ADR
-- 0403). Every kept vanilla win outside the old Ch8 waits has at most 15 such phases (#510
-- comment 6828202335); the 13 wins of the resumed Ch8 run have at most 2 under the full
-- definition, while its stuck attempts ran 8 to 1,206. 16 spares every kept win and ends a wait
-- within one more phase. Nicolas left the number to Fable (2026-11-12).
M.QUIET_BOUND = 16

-- The frames of game code one decision may run in the planner's simulations before the attempt
-- ends `timeout` (the record's `timeout`: the turn, the frames, the planner's stage; ADR 0411).
-- Vanilla Ch15 (Eirika)'s first decision ran 8.4 million with no plan and was stopped by hand
-- after an hour. The kept records hold no decision's own frames (from now: plans.slowest); the
-- most any attempt averaged a decision is 152,790 (vanilla Ch4, campaign 4003: 3,055,800 over
-- 20 plans). Nicolas set 4,000,000 (2026-11-14) because no kept record could have met it: the
-- largest whole attempt is 3,545,061 frames. 1,500,000 was sized from per-attempt averages, and
-- Ch15 already held a 1,220,020-frame decision (tag ch15b). plans.slowest will give real
-- per-decision numbers to tighten it.
M.DECISION_FRAMES = 4000000

-- Readings in a row without a new low of its own after which a ledger goal's row is stalled (the
-- win stops waiting for it). FR-007's stall is three player phases in a row without a move that
-- changes the chapter, and #510 call 3 (comment 6810567866) asked for the same three here.
M.GOAL_QUIET = 3

-- A run's player acts as one number, folded act by act (FNV-1a, 32 bits): who, what, where,
-- on whom (the target's unit slot too: generic enemies share a charId). Equal on two attempts of one start means the same game was played twice. `h` is the
-- hash so far (nil at the start) -> the hash with `a` added.
function M.actsHash(h, a)
    h = h or 0x811C9DC5
    local s = string.format("%s:%s:%d,%d:%s/%s;", tostring(a.unit), tostring(a.act), a.move.x,
                            a.move.y, tostring(a.target), tostring(a.targetId))
    for i = 1, #s do h = ((h ~ s:byte(i)) * 0x01000193) & 0xFFFFFFFF end
    return h
end

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
-- death, the plan whose `action` struck (its counter's `die`); for an enemy-phase one, the plan
-- that last moved the unit, else the phase's last (its `predict`; the caller picks, record).
-- `plan.snapshot` is the board when that plan was made,
-- `cap` the style's risk cap (nil for greedy, which plays no plan; kept only on a protected
-- unit's death), `lords` the set (charId -> true) of the units whose death ends the game,
-- `admits` the planner's own test of a chance against the cap (Planner.admits: required
-- whenever `cap` is given), `diedAt` (optional) each unit index of another side to the
-- decision count it fell at: one that fell at or after the plan's (`plan.ref`) is no killer
-- from the snapshot, its slot free for an arrival of the same generic charId. Unknown is nil,
-- never zero: a death with no plan behind it has no prediction, and so no over-cap,
-- reinforcement or fog flag.
function M.grade(d, plan, action, cap, lords, board, diedAt, admits)
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
    -- the cap is on the protected units only (FR-009): blue, or one whose death ends the game
    local endsGame = (lords or {})[d.charId] == true
    if d.faction == "blue" or endsGame then d.cap = cap end
    if cap ~= nil and not admits then
        -- a cap with no test to apply it would leave every death ungraded, never a fault
        error("botrun.grade: a cap with no admits (Planner.admits) to grade it by")
    end
    if d.predicted ~= nil and d.cap ~= nil then d.over_cap = not admits(d.predicted, d.cap) end
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
    if d.faction == "green" then d.escort = endsGame end
    return d
end

function M.run(api)
    local Bot, Json = api.Bot, api.Json
    if api.check_pinned then
        local board = M.snapshot(api.reload(api.check_pinned))
        api.emit(M.PINNED_PREFIX .. Json.encode({ file = api.check_pinned, board = board }))
        return false, "pinned state read", nil
    end
    local style = Bot.applyClaims(api.claims or {}, api.style)
    style.villageGifts, style.houseGifts = api.villageGifts, api.houseGifts
    style.bench = api.bench
    local unplayed = Bot.unplayed(api.claims or {})
    local skipped = {}
    for _, id in ipairs(unplayed) do skipped[id] = true end
    local played = {}
    for _, c in ipairs(api.claims or {}) do
        if not skipped[c.id] then played[#played + 1] = c.id end
    end
    local rec = { game = api.info.game, rom_hash = api.info.rom_hash, chapter = api.info.chapter,
                  mode = api.info.mode, seed = api.info.seed, campaign = api.info.campaign,
                  attempt = api.info.attempt, team = api.info.team, style = api.style,
                  dice_advanced = api.info.dice_advanced,
                  bench = api.bench,
                  claims_played = played, claims_unplayed = unplayed, deaths = {}, kills = {},
                  deployed = {}, bot_faults = {}, watch_faults = {}, thefts = {},
                  -- unsplit: the counter kills the judged phases left unsplit (sight's
                  -- M.phaseWays); slowest: the decision that ran the most frames, and its
                  -- turn (what M.DECISION_FRAMES is sized from)
                  plans = { made = 0, kept = 0, phases = 0, averaged = 0, unsplit = 0,
                            slowest = { frames = 0 } }, bag = {},
                  board_repeats = 0, arrivals_seen = {}, enemies_seen = {},
                  -- the planner's lookahead, summed over the attempt (FR-018): decisions
                  -- planned, triggered, extended, skipped for budget, its calls and CPU
                  lookahead = { decisions = 0, triggered = 0, extended = 0, skipped_budget = 0,
                                calls = 0, cpu_s = 0 },
                  seize_skips = {}, stall_events = {}, anomalies = {} }
    local explore = M.exploreLog()
    -- a diagnostic replay (diag): the watch on its original trace; `pin`, the pinned decision's
    -- baseline and chosen keys once it is reached; `halt`, why the replay stops early
    local diag = api.diag
    local watch = diag and M.matcher(diag.original, diag.ref, Json)
    local pin, halt
    -- the lookahead's calls left this attempt (Planner.LOOK_ATTEMPT, FR-018)
    local function lookLeft()
        return (api.Planner and api.Planner.LOOK_ATTEMPT or 0) - rec.lookahead.calls
    end
    -- the attempt's lookahead_budget anomaly, once one is recorded: a decision the attempt's
    -- budget left one phase deep shows in the record, not only in the sum (#570: 32 calls ran
    -- out before ours-ch03's boss fight, and only `skipped_budget` said so)
    local lookOut
    -- what the graded record reads (FR-003..007): the charIds whose death ends the game
    -- (sight.objective.gameOver), every charId of another side that fell, every charId a
    -- Talk was offered to, and the turn each green unit was first seen at a phase's start
    local lords, felled, talked, greenSeen = {}, {}, {}, {}
    -- leftMap: the red units gone from the field that the game did not kill (charId -> true);
    -- lordFell: the game killed a unit whose death ends it (Bot.gameOver). The game-over event
    -- runs only once the death quote and the act are over, so its screen is not up yet
    local leftMap, lordFell = {}, false
    -- per unit index of another side, the decision count when it fell: a slot the game freed
    -- after a plan's snapshot and reloaded with an arrival is not the snapshot's unit
    local diedAt = {}
    -- whether the planner plays: only its plans record the Talks and rewards it was offered
    local planned = api.Planner ~= nil and style.aggression ~= "greedy"
    -- the style's risk cap, which every death is graded against (the planner raises on a
    -- style without one; greedy plays no plan, and so has none)
    local cap = planned and api.Planner.CAPS and api.Planner.CAPS[style.aggression] or nil
    local admits = planned and api.Planner.admits or nil   -- the planner's own test of the cap
    -- each with its turn: montecarlo.py's keep_trace gives it the story command (`narrate`)
    -- once the trace is filed where it will stay
    local function anomaly(a) rec.anomalies[#rec.anomalies + 1] = a end
    -- whether this turn moved the chapter on: a lord moved, a kill, a Visit, Talk or Chest
    -- (FR-007's stall is three player phases in a row without one)
    local progressed, idle = false, 0
    -- the progress signal (#510 fwd1 item C, ADR 0403): per player phase, whether it made
    -- progress under one definition -- an event (a kill made in the player phase, a Visit, Talk,
    -- Chest, door opened, wall broken, or the Seize) or a new low in turns-to-goal (planner's
    -- `nearest`: the objective's nearest unit, or a feasible ledger goal's best taker, strictly
    -- nearer than at any earlier reading of this attempt). Recorded in `rec.progress` and the
    -- trace's `progress` lines. Two rules read it: `quiet` ends the attempt `stuck` at
    -- M.QUIET_BOUND (the top of a player phase, below), and each goal's own run of readings
    -- without a new low (`goalQuiet`) makes its ledger row stalled at M.GOAL_QUIET (memo()'s
    -- quietGoals). `quiet` is never reset by those rules: the record is the plain count. FR-007's
    -- `progressed`/`idle` above stays as it is, and `idle_3` still counts the lord's moves: it is
    -- not this signal (what a stall event means is a separate call). Known limit: a phase's near
    -- half is read at the NEXT player phase's first fresh plan, so it also holds what the enemy
    -- phase did (on a Rout chapter the objective is the nearest enemy, and an enemy walking in is
    -- a new low); the trace's `near` names the ids, so a reader tells "objective" from the rest.
    local lows, quiet, eventsQuiet = {}, 0, 0   -- goal id -> least turns read; the phases in a row
    local curPhase, prevPhase                   -- { turn, events = set, read }; prev awaits its reading
    local goalQuiet = {}                        -- goal id -> readings in a row without a new low of its own
    local goalReads = {}                        -- goal id -> its last M.GOAL_QUIET readings (turns)
    -- stalled rows of the last plan's ledger: "x,y" (a village or chest) or "recruit:<charId>"
    local stalledRows = {}
    local wallHp = {}                           -- "x,y" -> the wall's HP as the forecasts left it
    if planned then
        rec.progress = { quiet_max = 0, quiet_last = 0, events_quiet_max = 0, phases = 0 }
    end
    -- the clean clear's recruits part, read from the game's party (api.party: the game's own
    -- MakePrepUnitList, i.e. IsUnitInCurrentRoster), never from the unit arrays: owed =
    -- api.recruits() less the party at the first read; joined = owed and in the party at the
    -- run's end. Vanilla's endings leave an unrecruited one as a blue entry the roster test
    -- keeps out (EventScr_StrictLoadUniqueAlly: SET_HP 0 sets US_DEAD)
    local owed = nil
    local startFrame = api.frames()
    local startCosts = api.costs and api.costs() or {}
    local turn = 0
    local deciding   -- the decision being made: { turn, at (the planner's opts.at) }
    local playerPhases, playerActs = 0, nil   -- rec.player_phases, rec.acts_hash
    local function trace(ev)
        ev.turn = ev.turn or turn
        if watch then
            watch.see(ev)
            -- a replay that left its original stops at once: nothing past it is the same attempt
            if watch.why and not pin then halt = halt or ("unmatched: " .. watch.why) end
        end
        if api.trace then api.trace(ev) end
    end
    local function markEvent(kind)
        if planned and curPhase then curPhase.events[kind] = true end
    end
    -- a phase's progress, once its near half is known (`near`: the ids at a new low)
    local function closePhase(ph, near)
        local events = {}
        for k in pairs(ph.events) do events[#events + 1] = k end
        table.sort(events)
        table.sort(near)
        quiet = (#events > 0 or #near > 0) and 0 or quiet + 1
        eventsQuiet = #events > 0 and 0 or eventsQuiet + 1
        local p = rec.progress
        p.quiet_max = math.max(p.quiet_max, quiet)
        p.events_quiet_max = math.max(p.events_quiet_max, eventsQuiet)
        p.phases = p.phases + 1
        trace({ t = "progress", turn = ph.turn, events = events, near = near, quiet = quiet,
                rn = ph.rn })
    end
    -- the first fresh plan of a player phase reads the goals' turns: a new low closes the phase
    -- before it, the first reading of an id sets its low and is not progress
    local function readNearest(plan)
        if not (planned and curPhase and not curPhase.read and plan and plan.nearest) then return end
        curPhase.read = true
        local near, here = {}, {}
        for _, n in ipairs(plan.nearest) do
            local low = lows[n.id]
            if low and n.turns < low - 1e-9 then near[#near + 1] = n.id end
            lows[n.id] = low and math.min(low, n.turns) or n.turns
        end
        -- whether the phase before this reading was a wait: no event in it and no new low
        -- anywhere. A goal's run grows only over waits: an army that is fighting has not given
        -- a goal up (vanilla Ch4, suite seed 1001: the village at (1,11) drifted from 0.43 to
        -- 1.43 turns over four phases of kills, was stalled, and the win was taken a turn before
        -- the unit sent back would have visited it)
        local waited = prevPhase ~= nil and next(prevPhase.events) == nil and #near == 0
        for _, n in ipairs(plan.nearest) do
            -- a ledger goal's own run: 0 on its first reading, or when it is strictly below
            -- EVERY one of its last M.GOAL_QUIET readings, else one more after a wait and
            -- unchanged after a phase that made progress. Not the all-time low:
            -- a taker that walked away and is walking back would count as quiet until it passed
            -- its old best (a chest missed while a unit walked to it). Against the window, a
            -- shuffle between two or three tiles (period <= M.GOAL_QUIET) can never beat it, and
            -- a longer wander that does only keeps the row feasible (the old behaviour, still
            -- ended by M.QUIET_BOUND). An id missing from this reading closed or lost its way,
            -- and starts again if it returns
            if n.id ~= "objective" then
                here[n.id] = true
                local win = goalReads[n.id]
                local neared = true   -- an empty window (the first reading) is run 0
                for _, r in ipairs(win or {}) do
                    if not (n.turns < r - 1e-9) then neared = false; break end
                end
                if win == nil then win = {}; goalReads[n.id] = win end
                win[#win + 1] = n.turns
                if #win > M.GOAL_QUIET then table.remove(win, 1) end
                goalQuiet[n.id] = neared and 0 or (goalQuiet[n.id] or 0) + (waited and 1 or 0)
            end
        end
        for id in pairs(goalQuiet) do
            if not here[id] then goalQuiet[id], goalReads[id] = nil, nil end
        end
        if prevPhase then closePhase(prevPhase, near); prevPhase = nil end
    end
    -- each full-bag answer the harness gave, and each drop the game gave a player unit, since
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
    local lastBoard, actedIn
    -- every red unit a board showed out of fog this attempt, slot -> charId: the planner's
    -- strongest enemy seen so far, for its fog rule (Planner.plan's opts.seen, #510 PR A): the
    -- slot's current unit. What a retry may remember (rec.enemies_seen, ADR 0399) is every unit a
    -- board showed, kept by its whole key (Board.memoryKey): a unit killed and a reinforcement
    -- later loaded into its slot are both remembered
    local seenReds, enemiesSeen = {}, {}
    local function sawEnemy(id, charId, classId)
        enemiesSeen[Bot.memoryKey(id, charId, classId)] = { id = id, charId = charId,
                                                               classId = classId }
    end
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
            local now = byId(after)
            for _, e in ipairs(M.events(lastBoard, after)) do
                e.t = "event"
                trace(e)
                -- what a retry may remember (ADR 0386): a reinforcement's turn and tile, only
                -- as the screen showed it -- one that arrived under fog was never seen arrive.
                -- Its turn as a guide claim cites one: the player phase it arrives on, or the
                -- enemy phase's own turn when it acted there (one that landed then and did not
                -- act reads as the next turn's)
                if e.kind == "arrive" and e.faction == "red" and not now[e.id].fogged then
                    local inPhase = actedIn and actedIn.ids[e.id] and actedIn.turn
                    rec.arrivals_seen[#rec.arrivals_seen + 1] = { turn = inPhase or after.turn or turn,
                                                                  x = e.x, y = e.y,
                                                                  charId = e.charId }
                end
            end
        end
        for _, u in ipairs(after.units or {}) do
            if u.faction == "red" and u.onField and not u.dead and not u.fogged then
                seenReds[u.id] = u.charId
                sawEnemy(u.id, u.charId, u.classId)
            end
        end
        lastBoard, actedIn = after, nil
    end

    -- A blue or green unit lost spoils the clear (design 11: vanilla Ch6's Orion's Bolt is
    -- given only if its three green villagers live), so both are deaths; a red one is a kill.
    -- A death or a kill is one the game ran UnitKill on (api.killed); `list`, the board's
    -- falls, gives a killer where the watch saw no fight, and the red units that left the
    -- field unkilled (`leftMap`). A slot the watch
    -- could not read is a watch fault, never a guess.
    -- Each blue or green death is graded against the plan that committed to its board (plan,
    -- and for a player-phase death the action that struck: M.grade). An enemy-phase death is
    -- graded by the plan that last moved its unit this turn (`movers`, unit slot -> plan): what
    -- that plan knew when it put the unit there, not what a later replan found (#510 PR A); a
    -- unit no plan moved (a green, one carried) falls back to `plan`, the phase's last.
    local deathFaults = {}
    -- `now` (optional): the board read after the deaths, where a killer that arrived during the
    -- phase stands (lastBoard, from before it, does not hold one)
    local function record(list, phase, plan, action, movers, now)
        -- killed: the unit slots the game killed in this record; unread: those the watch
        -- could not read, which neither fell nor left as far as anyone can say
        local seen, killed, unread = {}, {}, {}
        for _, d in ipairs(list) do seen[d.id] = d end
        for _, k in ipairs(api.killed()) do
            if k.fault then
                unread[k.id] = true
                deathFaults[#deathFaults + 1] = { kind = "death_unread", why = k.fault,
                                                  charId = k.charId, faction = k.faction,
                                                  turn = turn, phase = phase }
            elseif k.faction == "blue" or k.faction == "green" then
                local d = seen[k.id] or {}
                local g = M.grade({ id = k.id, charId = k.charId, faction = k.faction,
                                    turn = k.turn or turn, killer = k.killer or d.killer,
                                    killerId = k.killerId or d.killerId,
                                    phase = k.phase or phase },
                                  movers and movers[k.id] or plan, action, cap, lords,
                                  lastBoard, diedAt, admits)
                -- the killer's class: with its slot and character, what a retry remembers it by
                -- (Board.memoryKey, ADR 0399). The board after the deaths first (an arrival that
                -- struck in this phase), then the one before (a killer that fell on the counter)
                for _, b in ipairs(g.killerId and { now or {}, lastBoard or {} } or {}) do
                    for _, u in ipairs(not g.killerClass and b.units or {}) do
                        if u.id == g.killerId and u.charId == g.killer and u.faction == "red" then
                            g.killerClass = u.classId
                        end
                    end
                end
                -- a fight is on screen, fog or not: the killer is an enemy seen
                if g.killerClass then sawEnemy(g.killerId, g.killer, g.killerClass) end
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
                felled[k.charId], diedAt[k.id], killed[k.id] = true, rec.plans.made, true
                -- a kill is progress when the player phase made it (FR-007's stall counts
                -- player phases), never an enemy walking onto a counter
                progressed = progressed or (k.phase or phase) == "player"
                if (k.phase or phase) == "player" then markEvent("kill") end
            end
            -- of any side: a chapter can end on a green unit's death
            if not k.fault and lords[k.charId] then lordFell = true end
        end
        for _, d in ipairs(list) do
            if d.faction ~= "blue" and d.faction ~= "green" then
                -- gone from the field and not killed: a script unloaded it or it escaped
                -- (Board.fate), as for a blue or green one. It did not fall
                -- its slot is free either way: an arrival loaded there is another unit
                diedAt[d.id] = diedAt[d.id] or rec.plans.made
                if killed[d.id] then
                    progressed = progressed or phase == "player"
                    if phase == "player" then markEvent("kill") end
                elseif not unread[d.id] then
                    leftMap[d.charId] = true
                end
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
        -- the phases still open: the one waiting for its near half has none to read now (no
        -- later plan), then the last played; the trace's `end` comes after
        if planned then
            if prevPhase then closePhase(prevPhase, {}) end
            if curPhase then closePhase(curPhase, {}) end
            prevPhase, curPhase = nil, nil
            rec.progress.quiet_last = quiet
        end
        -- the game's turn counter stops at 999 and two attempts of one start can be one game:
        -- the player phases played, and the acts played in them, in order (M.actsHash)
        rec.player_phases, rec.acts_hash = playerPhases, string.format("%08x", playerActs or 0)
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
                        or (leftMap[c] and "left_map")
                        or (outcome == "won" and planned and stalledRows["recruit:" .. c] and "stalled")
                        or (talked[c] and "talk_skipped")
                        or (planned and "not_reached") or "unknown" }
            end
        end
        rec.missed_rewards = {}
        for _, t in ipairs(rec.clear.rewards_missing) do
            -- M.REWARD_REASONS. Only the planner counts offers (its plans' `explore`), so a run
            -- without one cannot tell skipped from never offered
            local reason = planned and M.REWARD_REASONS[t.why] or "unknown"
            if outcome == "won" and planned and stalledRows[t.x .. "," .. t.y] then
                reason = "stalled"
            end
            rec.missed_rewards[#rec.missed_rewards + 1] = { x = t.x, y = t.y, kind = t.kind,
                reason = reason, closed_by = t.closed_by }
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
        -- PT_LEAKGUARD: every leak of the attempt, finish's own reads above included, its game
        -- played on with each word put back. The record keeps what the game did (its deaths,
        -- missed rewards); only its outcome says the run cannot be trusted, and a fault play()
        -- named is kept.
        local leaks = api.leaks and api.leaks() or {}
        if #leaks > 0 then
            rec.leaks = leaks
            why = ("%d sandbox leak(s) (the record's leaks); the game ended %s: %s")
                :format(#leaks, tostring(outcome), tostring(why))
            outcome = "crashed"
            rec.outcome, rec.why = outcome, why
        end
        fault = fault or (outcome == "crashed" and "crash") or (outcome == "timeout" and "timeout")
            or (#rec.watch_faults > 0 and "watch") or nil
        rec.env_status = fault and { fault = fault, outcome_dependent = #rec.deployed > 0 }
            or "clean"
        rec.instrument = api.info.instrument   -- the bot and suite version (montecarlo.py)
        rec.trace = api.info.trace   -- the trace's file, when the api keeps one
        trace({ t = "end", record = rec })
        if diag then
            -- the replay's one line: never the record, which production reads
            -- avoided: the failure's unit alive at the end of its turn, and no other blue or
            -- green unit lost in its place from the pinned turn on (`traded`): a plan that
            -- moves the death onto someone else avoided nothing
            local died, traded = false, {}
            for _, d in ipairs(rec.deaths) do
                if d.turn <= diag.failure.turn then
                    if d.charId == diag.failure.charId then
                        died = true
                    elseif pin and d.turn >= pin.turn then
                        traded[#traded + 1] = d.charId
                    end
                end
            end
            local matched = pin ~= nil and pin.matched
            -- the kept state, loaded back, must hold the board the pinned decision read (a
            -- fixture that does not is said, never used)
            local pinnedBoard
            if pin and pin.file and api.reload then
                local ok, b = pcall(api.reload, pin.file)
                pinnedBoard = ok and same(Json.decode(Json.encode(M.snapshot(b))),
                                          Json.decode(Json.encode(pin.board))) or false
            end
            api.emit(M.DIAG_PREFIX .. Json.encode({ run = diag.run, ref = diag.ref, mode = diag.mode,
                matched = matched, baseline = pin and pin.baseline or {},
                chosen = pin and pin.chosen or {}, planned = pin and pin.planned or {},
                differs = pin and pin.differs or false,
                failure = diag.failure,
                avoided = matched and #pin.chosen > 0 and not pin.broken and not died
                    and #traded == 0 and outcome ~= "crashed" or false,
                traded = traded,
                unoffered = pin and pin.unoffered or {}, broken = pin and pin.broken,
                pinned_board = pinnedBoard,
                outcome = outcome, why = why, trace = api.info.trace }))
            api.log(string.format("botrun: diagnostic %s at decision %d: %s (%s)", diag.mode,
                diag.ref, outcome, why))
            return false, why, nil
        end
        -- every red a board or a fight showed: campaign.lua's memory for the next retry
        for _, e in pairs(enemiesSeen) do rec.enemies_seen[#rec.enemies_seen + 1] = e end
        table.sort(rec.enemies_seen, function(a, b)
            return Bot.memoryKey(a.id, a.charId, a.classId) < Bot.memoryKey(b.id, b.charId, b.classId)
        end)
        api.emit(M.PREFIX .. Json.encode(rec))
        api.log(string.format("botrun: %s on turn %d (%s)", outcome, turn, why))
        return outcome == "won" or outcome == "lost" or outcome == "stuck", why, rec
    end

    local function play()
        api.seed(api.info.seed)
        rec.dice_start = api.dice and api.dice() or nil   -- right after the campaign's advance
        local sight = api.sight()
        -- a retry's memory (ADR 0399): what earlier attempts at this start showed plays as seen
        if sight.remember then sight.remember(style.memory and style.memory.enemies) end
        -- the units whose death ends the game, as the game says (sight.objective.gameOver)
        trace({ t = "start", info = api.info, style = api.style, bench = api.bench,
                claims_played = played,
                claims_unplayed = unplayed,
                game_over = sight.objective and sight.objective.gameOver })
        lords = Bot.gameOver(sight)
        local seen, waitUntil = {}, nil
        -- the plan that committed to the enemy phase: this phase's last (FR-003)
        local commit
        -- the plan that last moved each blue unit this turn (unit slot -> plan): an enemy-phase
        -- death's grader (record)
        local movers = {}
        -- each red unit's tile at every phase start, for a bait loop; the turn of the last
        -- seize skip recorded (one a turn)
        local tiles, baited, skipTurn = {}, {}, nil
        local fallback   -- this turn's fallback_sacrifice anomaly, once one is recorded
        -- the tiles units were sent to explore: they outlive the turn's last, empty plan (no
        -- unit left to act returns none), so the next turn keeps the same senders; and the
        -- goals units were found blocked from, since which turn (Bot.candidates' opts.stuck)
        local sent, stuck
        -- the plan being played this phase: its next act's index, and the board before the
        -- last act it played (Planner.surprise compares the two)
        local playing, nextAct, before
        -- the diagnostic's pinned decision is the next plan made (diag.ref is its plan.ref)
        local function pinNow() return diag and not pin and rec.plans.made + 1 == diag.ref end
        local function batched(fn)
            if sight.batch then return sight.batch(fn) end
            return fn()
        end
        -- a forced key as an act on this board: the one Bot.candidates offers with that key,
        -- else built from the key (an act never offered, kept in pin.unoffered); nil when its
        -- unit cannot act any more
        local function forcedAct(board, k, opts)
            for _, c in ipairs(Bot.candidates(board, sight, style, opts)) do
                for _, a in ipairs(c.acts) do
                    if api.Planner.key(a) == k then return a end
                end
            end
            local a = api.Planner.unkey(k)
            local byIdNow = byId(board)
            local u = byIdNow[a.unitId]
            if not (u and u.faction == "blue" and u.onField and not u.acted) then return nil end
            pin.unoffered[#pin.unoffered + 1] = k
            a.unit = u.charId
            if a.targetId then a.target = byIdNow[a.targetId] and byIdNow[a.targetId].charId end
            return a
        end
        -- The pinned decision: the baseline, then the diagnostic's plan from the same board and
        -- budget; the baseline's cost is the one charged (the original paid it here)
        local function pinDecision(board, opts)
            local P = api.Planner
            local a, plan, cost = batched(function() return P.plan(Bot, board, sight, style, opts) end)
            pin = { baseline = plan and P.keysOf(plan) or {}, unoffered = {}, chosen = {},
                    turn = turn }
            pin.matched = watch.at(a and actOf(a))
            pin.board = M.snapshot(board)
            if api.pinned then pin.file = api.pinned(diag.ref, pin.board) end
            if not pin.matched then
                halt = "unmatched: " .. watch.why
                return nil, nil, cost
            end
            local dopts = {}
            for k, v in pairs(opts) do dopts[k] = v end
            local da, dplan
            if diag.mode == "deep" then
                dopts.diag = "deep"
                da, dplan = batched(function() return P.plan(Bot, board, sight, style, dopts) end)
            elseif diag.mode == "full_info" then
                -- knowledge, not powers: the acts are the ones the fogged game allows (offered on
                -- this board, in its own sandbox: fullInfo refuses to run inside one); only the
                -- judging sees every enemy
                local cands, ctx = batched(function() return Bot.candidates(board, sight, style, dopts) end)
                dopts.offer = { cands = cands, ctx = ctx }
                da, dplan = sight.fullInfo(function(b) return P.plan(Bot, b, sight, style, dopts) end)
            elseif diag.mode == "force" then
                da = batched(function() return forcedAct(board, diag.force[1], opts) end)
                if not da then
                    pin.broken = diag.force[1]
                    halt = "the forced act " .. diag.force[1] .. " has no unit to play it"
                    return nil, nil, cost
                end
                dplan = { acts = { da }, forced = true, goals = plan and plan.goals,
                          stuck = plan and plan.stuck }
            else
                error("botrun: no diagnostic mode " .. tostring(diag.mode))
            end
            -- `planned` is the diagnostic's plan; `chosen` grows by each of its acts actually
            -- played, and `broken` names the first that was not (pinPlayed)
            pin.planned = diag.mode == "force" and diag.force or (dplan and P.keysOf(dplan) or {})
            pin.differs = not same(pin.planned, pin.baseline)
            pin.plan = dplan
            if da then pin.chosen[1] = P.key(da) end
            return da, dplan, cost
        end
        while true do
            if api.won() then return "won", "the chapter advanced" end
            if api.lost() then return "lost", "game over" end
            local board = api.board()
            turn = board.turn
            if halt then return "diag", halt end
            if pin and turn > diag.failure.turn then return "diag", "the failure's turn is over" end
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
            -- A wait that gains nothing ends (#510 fwd1 item C, ADR 0403): M.QUIET_BOUND player
            -- phases in a row with no progress, with the same two guards as the board repeat
            -- above -- a turn event still to fire may change the board, and a Survive chapter's
            -- wait IS the play (the objective counts turns down). `quiet` lags one phase (a
            -- phase closes at the next one's first plan), which only delays the end by a phase.
            -- It is not reset while a guard holds, and nothing else reads it here: the check
            -- fires only on this line, so the record stays the plain count.
            -- Not in a diagnostic replay (diag): it plays a kept run to its pinned decision and
            -- must reach it, and the bound only ends a run, so a kept run from before the bound
            -- (16+ quiet phases ahead of its pin) would otherwise end `stuck` short of the
            -- witness. Rule 1 stays on: it changes the plans, and a replay of a run made WITH it
            -- must make the same plans to match its trace (a mismatch is `matched = false`).
            if planned and not diag and quiet >= M.QUIET_BOUND and not sight.nextTurnEvent(turn)
                and not (sight.objective and sight.objective.turnsLeft) then
                for _, l in ipairs(Bot.explain(board, sight, style)) do api.log("stuck: " .. l) end
                return "stuck", string.format("no progress in %d player phases in a row, and no "
                    .. "turn event is left to change that", quiet)
            end
            seen[h] = stalled and "stalled" or seen[h] or true
            changes(board)
            commit, movers = nil, {}
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
            playerPhases = playerPhases + 1
            playing = nil
            if planned then
                -- the phase before it never got a reading (no plan made in this one yet): it
                -- closes on its events alone, then it is the one awaiting this phase's reading
                if prevPhase then closePhase(prevPhase, {}) end
                -- `rn`: the dice this phase starts on, before the bot's first act (nil without
                -- api.dice); a `progress` line is no part of what a replay must match
                prevPhase, curPhase = curPhase, { turn = turn, events = {},
                                                  rn = api.dice and api.dice() or nil }
            end
            while true do
                if halt then return "diag", halt end
                -- one decision's reads in one save/load (sight.batch), when the sight batches
                -- the planner plays every style but greedy, the old clear bot (bot.lua)
                local function decide()
                    if planned then
                        local why
                        -- what a plan call reads of the run: built only when one is asked for
                        local function memo()
                            -- the ledger goals no unit has neared for M.GOAL_QUIET readings: the
                            -- plan's ledger marks their rows stalled (goals.lua). Read before the
                            -- plan, which is why botrun keeps the run of readings
                            local quietGoals = {}
                            for id, n in pairs(goalQuiet) do
                                if n >= M.GOAL_QUIET then quietGoals[id] = true end
                            end
                            return { stalled = stalled, sent = sent, stuck = stuck,
                                     explored = explore.explored(), lost = explore.lost(),
                                     budget = { attempt = lookLeft() }, seen = seenReds,
                                     quietGoals = quietGoals }
                        end
                        if playing and playing.forced then
                            -- a forced plan plays its keys in turn, each read on this board
                            local k = diag.force[nextAct]
                            local a = k and forcedAct(board, k, memo())
                            if a then
                                nextAct = nextAct + 1
                                pin.chosen[#pin.chosen + 1] = k
                                trace({ t = "plan", kept = true, forced = true, choice = actOf(a) })
                                return a
                            end
                            if k then pin.broken = k end
                            playing = nil
                        end
                        if playing then
                            why = api.Planner.surprise(playing, nextAct - 1, before, board,
                                sight.legal)
                            if not why then
                                local a = playing.acts[nextAct]
                                if pin and playing == pin.plan then
                                    pin.chosen[#pin.chosen + 1] = api.Planner.key(a)
                                end
                                nextAct = nextAct + 1
                                rec.plans.kept = rec.plans.kept + 1
                                trace({ t = "plan", kept = true, choice = actOf(a) })
                                api.log(string.format("plan: keep 0x%02X %s @%d,%d", a.unit, a.act,
                                    a.move.x, a.move.y))
                                return a
                            end
                            api.log("plan: replan, " .. why)
                            local cut = pin and playing == pin.plan and playing.acts[nextAct]
                            if cut and not pin.broken then
                                -- the diagnostic's plan was cut short: what it did not play
                                pin.broken = api.Planner.key(cut)
                            end
                        end
                        local replan = playing and why
                        local opts = memo()
                        opts.at = deciding.at   -- where the planner is, for a timeout's record
                        if replan then
                            -- the plan in hand, from the act it did not play: judged again on
                            -- this board beside the new ones (Planner.plan's opts.rest)
                            opts.rest = {}
                            for i = nextAct, #playing.acts do
                                opts.rest[#opts.rest + 1] = api.Planner.key(playing.acts[i])
                            end
                        end
                        local a, plan, cost
                        if pinNow() then
                            a, plan, cost = pinDecision(board, opts)
                        else
                            a, plan, cost = api.Planner.plan(Bot, board, sight, style, opts)
                        end
                        stalled = false   -- one changed act is the change; the rest plans freely
                        rec.plans.made = rec.plans.made + 1
                        cost = cost or {}
                        rec.plans.phases = rec.plans.phases + (cost.phases or 0)
                        rec.plans.averaged = rec.plans.averaged + (cost.averaged or 0)
                        rec.plans.unsplit = rec.plans.unsplit + (cost.unsplit or 0)
                        for k, v in pairs(cost.look or {}) do
                            rec.lookahead[k] = rec.lookahead[k] + v
                        end
                        if (cost.look or {}).skipped_budget == 1 then
                            if lookOut then
                                lookOut.skipped = lookOut.skipped + 1
                            else
                                lookOut = { kind = "lookahead_budget", turn = turn, skipped = 1 }
                                anomaly(lookOut)
                            end
                        end
                        if plan then
                            sent, stuck = plan.goals, plan.stuck
                            -- the tiles whose goal row this plan's ledger left stalled: a win
                            -- that leaves one of them missing says so (`finish`)
                            stalledRows = {}
                            local charOf = {}   -- a recruit row's id carries the unit id; the record keys charIds
                            for _, u in ipairs(board.units) do charOf[u.id] = u.charId end
                            for _, g in ipairs(plan.ledger or {}) do
                                if g.status == "stalled" then
                                    local at = (g.kind == "visit" or g.kind == "chest")
                                        and g.id:match("^%a+:(%-?%d+,%-?%d+)$")
                                    if at then
                                        stalledRows[at] = true
                                    else
                                        -- a recruit row carries its unit only in its id
                                        -- (goals.lua: "recruit:<unit id>"); the planner copies
                                        -- no unitId onto a ledger row
                                        local c = g.kind == "recruit"
                                            and charOf[tonumber(g.id:match("^recruit:(%d+)$"))]
                                        if c then stalledRows["recruit:" .. c] = true end
                                    end
                                end
                            end
                            -- the board this plan committed to, and its decision index (a
                            -- death's plan_ref)
                            plan.ref, plan.snapshot = rec.plans.made, M.snapshot(board)
                            commit = plan
                            if plan.fallback then
                                -- every plan was over the cap: the least likely to end the
                                -- game, then the least over it, was played.
                                -- One anomaly a turn, however often the turn replans: `plans`
                                -- counts them, `max_die` the most any of them accepted
                                local die = plan.rank and plan.rank.max_die or 0
                                if fallback and fallback.turn == turn then
                                    fallback.plans = fallback.plans + 1
                                    fallback.max_die = math.max(fallback.max_die, die)
                                else
                                    fallback = { kind = "fallback_sacrifice", turn = turn,
                                                 plans = 1, max_die = die }
                                    anomaly(fallback)
                                end
                            end
                            for _, c in ipairs(plan.talks or {}) do talked[c] = true end
                            if plan.seizable and not plan.seizes and skipTurn ~= turn then
                                -- the win was on offer and the plan did something else (FR-015):
                                -- justified while a goal of the ledger is still to get, or when
                                -- every plan that took the Seize was over the cap. A fault when a
                                -- Seize under the cap was judged and nothing was left, or when no
                                -- plan with it was judged at all (the beam lost it)
                                skipTurn = turn
                                local ledger = {}
                                for _, g in ipairs(plan.ledger or {}) do
                                    if g.status == "feasible" then ledger[#ledger + 1] = g.id end
                                end
                                local reason
                                if #ledger > 0 then
                                    reason = "goals the win would close are open"
                                elseif plan.seizeJudged and not plan.seizeAdmitted then
                                    reason = "every plan with the Seize was over the cap"
                                elseif plan.seizeJudged then
                                    reason = "nothing left the win would close"
                                else
                                    reason = "no plan with the Seize was judged"
                                end
                                local justified = #ledger > 0
                                    or (plan.seizeJudged and not plan.seizeAdmitted) or false
                                rec.seize_skips[#rec.seize_skips + 1] = { turn = turn,
                                    ledger = ledger, justified = justified, reason = reason }
                                if not justified then
                                    rec.stall_events[#rec.stall_events + 1] = { turn = turn,
                                        kind = "unjustified_seize_skip" }
                                end
                            end
                        end
                        explore.offered(plan and plan.explore)
                        readNearest(plan)
                        trace({ t = "plan", choice = a and actOf(a), replan = replan,
                                ref = plan and plan.ref, audit = plan and plan.audit,
                                judged = plan and plan.judged, kind = plan and plan.kind,
                                rank = plan and plan.rank, fallback = plan and plan.fallback,
                                protected = plan and plan.protected,
                                considered = plan and plan.considered,
                                predict = plan and plan.predict,
                                explore = plan and plan.explore, goals = plan and plan.goals,
                                worth = plan and plan.goalWorth,
                                ledger = plan and plan.ledger,
                                nearest = plan and plan.nearest,
                                lookahead = plan and plan.lookahead,
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
                -- the pinned decision is not batched: full_info's sandbox must be the outermost
                -- the decision's frame budget (M.DECISION_FRAMES): asked before every game call
                -- it makes, so one that runs away ends the attempt as `timeout`
                local from = api.frames()
                deciding = { turn = turn, at = {} }
                if sight.watch then
                    sight.watch(function()
                        local spent = api.frames() - from
                        if spent > M.DECISION_FRAMES then
                            error({ timeout = true, frames = spent }, 0)
                        end
                    end)
                end
                -- the watch comes off however the decision ends: a timeout (or any error)
                -- left on the sight would police the next game call outside any decision
                local ran, got = pcall(function()
                    if sight.batch and not pinNow() then return sight.batch(decide) end
                    return decide()
                end)
                if sight.watch then sight.watch(nil) end
                if not ran then
                    -- the outer handler reads where the decision was; it is cleared here
                    if type(got) == "table" then got.deciding = deciding end
                    deciding = nil
                    error(got, 0)
                end
                action = got
                local spent = api.frames() - from
                if spent > rec.plans.slowest.frames then
                    rec.plans.slowest = { frames = spent, turn = turn }
                end
                deciding = nil
                if halt then return "diag", halt end
                if not action then break end
                local done, why = api.act(action)
                bagged()
                if done == false and (action.act == "visit" or action.act == "chest") then
                    explore.failed(action, turn)
                end
                if done == false then
                    record({}, "player", playing, action)   -- the deaths the act caused first
                    if lordFell or api.lost() then return "lost", M.LOST_IN_PLAYER_PHASE end
                    return "crashed", "the harness could not perform " .. action.act
                        .. (why and (": " .. why) or "")
                end
                -- "trapped": the game halted the move on a unit the fog hid (FE8's ambush,
                -- harness api.act); the unit's turn is over where it stopped, its act not made
                local trapped = done == "trapped"
                if playing then movers[action.unitId] = playing end
                if not trapped and (action.act == "visit" or action.act == "chest") then
                    explore.visited(action, turn)
                end
                if not trapped and (action.act == "visit" or action.act == "chest"
                        or action.act == "talk" or action.act == "rescue" or action.act == "drop") then
                    progressed = true
                end
                if not trapped then
                    if action.act == "visit" or action.act == "chest" or action.act == "talk"
                        or action.act == "door" or action.act == "seize" then
                        markEvent(action.act)
                    elseif action.act == "attack" and action.obstacle
                        and action.obstacle.blow and action.obstacle.blow.dealt
                        and action.obstacle.hp then
                        -- a wall is broken when the forecasts, summed, take its HP
                        local at = action.obstacle.x .. "," .. action.obstacle.y
                        wallHp[at] = (wallHp[at] or action.obstacle.hp) - action.obstacle.blow.dealt
                        if wallHp[at] <= 0 then markEvent("wall") end
                    end
                end
                local battle = not trapped and action.act == "attack" and api.battle and api.battle() or nil
                local after = api.board()
                sight.refresh()
                before = board
                local actor = byId(after)[action.unitId]
                local from = byId(board)[action.unitId]
                local fell = fallen(board, after, action)
                local to = trapped and actor or action.move
                if lords[action.unit] and from and (from.x ~= to.x or from.y ~= to.y) then
                    progressed = true
                end
                record(fell, "player", playing, action, nil, after)
                trace({ t = "act", phase = "player", unit = action.unit, id = action.unitId,
                        from = from and { x = from.x, y = from.y },
                        to = trapped and actor and { x = actor.x, y = actor.y } or action.move,
                        canto = action.canto, act = action.act, target = action.target, battles = { battle },
                        fell = fell, trapped = trapped or nil })
                changes(after)
                playerActs = M.actsHash(playerActs, action)
                -- before any complaint about the act: an act that felled our lord is a loss,
                -- however it left the board
                if lordFell or (api.lost() and not api.won()) then
                    return "lost", M.LOST_IN_PLAYER_PHASE
                end
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
                if board.phase ~= "blue" or board.turn ~= turn then break end
            end
            if halt then return "diag", halt end
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
            -- who acted in it: an arrival among them landed in this enemy phase, not the next
            -- player phase the board is read on (arrivals_seen's turn)
            actedIn = { turn = turn, ids = {} }
            for _, a in ipairs(acts or {}) do actedIn.ids[a.id] = true end
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
            local now = api.board()
            for _, d in ipairs(fallen(before, now, nil)) do
                if not counted[d.id] then all[#all + 1] = d end
            end
            record(all, "enemy", commit, nil, movers, now)
            -- lordFell: the game killed a unit it ends on, whatever the phase came back as
            if phase == "gameover" or lordFell then
                return "lost", "game over in the enemy phase"
            end
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
    if not ok and type(outcome) == "table" and outcome.timeout then
        -- the watch's (above): where the decision was when its budget ran out
        local at = outcome.deciding
        rec.timeout = { turn = at.turn, frames = outcome.frames, limit = M.DECISION_FRAMES,
                        stage = at.at and at.at.stage,
                        plans_judged = at.at and at.at.judged,
                        phases = at.at and at.at.phases }
        return finish("timeout", string.format(
            "the decision on turn %d ran %d frames of game code, over the %d a decision may (%s)",
            at.turn, outcome.frames, M.DECISION_FRAMES,
            at.at and at.at.stage or "no planner stage"))
    end
    if not ok then return finish("crashed", "Lua error: " .. tostring(outcome)) end
    return finish(outcome, why, fault)
end

return M
