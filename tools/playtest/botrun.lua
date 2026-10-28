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
--            change it: the hash holds every on-field unit's id, tile and HP, the objective's
--            turns left, and the turns until the next arrival a reinforcements claim cites --
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
--   info = { game, rom_hash, chapter, mode, seed, campaign, attempt }  what the record names
--                      the run by; campaign and attempt only when campaign.lua plays it
--   style = Bot.STYLES-shaped table, claims = resolved claims (bot.lua's Claims)
--   seed(s)            seed the game's RNG (Sight.seed)
--   board()            Board.read
--   sight()            Sight.new, called once
--   act(action)        perform Bot.decide's action: true; "noseize" when the menu offered no
--                      Seize; false on a controller fault
--   endPhase()         "player" | "gameover" | "ended" | nil, the deaths it saw:
--                      { { id, charId, faction, killer } } (id = Board's unit index byte,
--                      killer = the other fighter's charId), and OPTIONALLY each act of the
--                      phase in order: { { id, charId, from = {x, y}, to = {x, y}, hp,
--                      act (Board.ACTIONS' name), targetId, tile (a pillaged village or chest),
--                      battles = { Board.battle... } } }
--   battle()           OPTIONAL: Board.battle, the last real battle as the game rolled it
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
--           judged (`considered`), what it expects of the enemy phase (`predict`), and whether a
--           kept plan's act was played or a surprise (`replan`, why) forced a new one
--   act     one act, either side: unit, from, to, the act and its target, the game's own
--           battle records (Board.battle: the forecast's numbers, every blow) and who fell
--   event   a change on the board no act names: a unit arriving, a recruit, items gained/lost
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
                              faction = u.faction, x = u.x, y = u.y, hp = u.hp, items = items }
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
            local killer
            if action and u.id == action.unitId then killer = action.target end
            if action and u.id == action.targetId then killer = action.unit end
            out[#out + 1] = { id = u.id, charId = u.charId, faction = u.faction, killer = killer }
        end
    end
    return out
end

function M.run(api)
    local Bot, Json = api.Bot, api.Json
    local style = Bot.applyClaims(api.claims or {}, api.style)
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
                  deployed = {}, bot_faults = {}, plans = { made = 0, kept = 0 } }
    local startFrame = api.frames()
    local startCosts = api.costs and api.costs() or {}
    local turn = 0
    local function trace(ev)
        if api.trace then
            ev.turn = ev.turn or turn
            api.trace(ev)
        end
    end
    local lastBoard
    local function changes(after)
        if lastBoard then
            for _, e in ipairs(M.events(lastBoard, after)) do
                e.t = "event"
                trace(e)
            end
        end
        lastBoard = after
    end

    local function record(list, phase)
        for _, d in ipairs(list) do
            if d.faction == "blue" then
                rec.deaths[#rec.deaths + 1] = { charId = d.charId, turn = turn, killer = d.killer,
                                                phase = phase }
            elseif d.killer then
                local k = tostring(d.killer)
                rec.kills[k] = (rec.kills[k] or 0) + 1
            end
        end
    end
    local function finish(outcome, why)
        rec.outcome, rec.turns, rec.why = outcome, turn, why
        rec.all_alive = outcome == "won" and #rec.deaths == 0
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
        rec.trace = api.info.trace   -- the trace's file, when the api keeps one
        trace({ t = "end", record = rec })
        api.emit(M.PREFIX .. Json.encode(rec))
        api.log(string.format("botrun: %s on turn %d (%s)", outcome, turn, why))
        return outcome == "won" or outcome == "lost" or outcome == "stuck", why, rec
    end

    local function play()
        api.seed(api.info.seed)
        trace({ t = "start", info = api.info, style = api.style, claims_played = played,
                claims_unplayed = unplayed })
        local sight = api.sight()
        local seen, waitUntil = {}, nil
        local lastPlan
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
            if seen[h] and not (waitUntil and turn < waitUntil) then
                waitUntil = sight.nextTurnEvent(turn)
                if not waitUntil then
                    for _, l in ipairs(Bot.explain(board, sight, style)) do api.log("stuck: " .. l) end
                    return "stuck", "a player phase began on a board seen before, and no turn "
                        .. "event is left to change it"
                end
                api.log(string.format("botrun: board repeats on turn %d; a turn event is due on "
                    .. "turn %d", turn, waitUntil))
            end
            seen[h] = true
            changes(board)
            trace({ t = "phase", phase = "player", units = M.snapshot(board) })
            playing = nil
            while true do
                -- one decision's reads in one save/load (sight.batch), when the sight batches
                -- the planner plays every style but greedy, the old clear bot (bot.lua)
                local function decide()
                    if api.Planner and style.aggression ~= "greedy" then
                        local why
                        if playing then
                            why = api.Planner.surprise(playing, nextAct - 1, before, board,
                                                             sight.visible)
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
                        local a, plan = api.Planner.plan(Bot, board, sight, style)
                        lastPlan = plan
                        rec.plans.made = rec.plans.made + 1
                        trace({ t = "plan", choice = a and actOf(a), replan = replan,
                                judged = plan and plan.judged, considered = plan and plan.considered,
                                predict = plan and plan.predict })
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
                local done = api.act(action)
                if done == false then
                    return "crashed", "the harness could not perform " .. action.act
                end
                local battle = action.act == "attack" and api.battle and api.battle() or nil
                local after = api.board()
                sight.refresh()
                before = board
                local actor = byId(after)[action.unitId]
                local from = byId(board)[action.unitId]
                local fell = fallen(board, after, action)
                record(fell, "player")
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
            for _, p in ipairs(lastPlan and lastPlan.predict or {}) do
                if p.blows > 0 then
                    api.log(string.format("plan: 0x%02X @%d,%d hp %d: %d blows, die %.2f, taken %.1f",
                        p.charId, p.x, p.y, p.hp, p.blows, p.die, p.taken))
                end
            end
            changes(before)
            trace({ t = "phase", phase = "enemy", units = M.snapshot(before) })
            local phase, deaths, acts = api.endPhase()
            for _, a in ipairs(acts or {}) do
                trace({ t = "act", phase = "enemy", unit = a.charId, id = a.id, from = a.from,
                        to = a.to, hp = a.hp, act = a.act, targetId = a.targetId, tile = a.tile,
                        battles = a.battles })
            end
            trace({ t = "fell", phase = "enemy", fell = deaths or {} })
            for _, d in ipairs(deaths or {}) do
                api.log(string.format("plan: died 0x%02X to 0x%02X", d.charId or 0, d.killer or 0))
            end
            record(deaths or {}, "enemy")
            -- A unit seen on the field before the phase and dead after it, that the watcher
            -- missed -- read before any return, so a lost run carries every death.
            local counted = {}
            for _, d in ipairs(deaths or {}) do counted[d.id] = true end
            for _, d in ipairs(fallen(before, api.board(), nil)) do
                if not counted[d.id] then record({ d }, "enemy") end
            end
            if phase == "gameover" then return "lost", "game over in the enemy phase" end
            if phase == "ended" then
                if api.won() then return "won", "the chapter advanced in the enemy phase" end
                return "lost", "the chapter ended without advancing"
            end
            if phase ~= "player" then return "crashed", "the enemy phase never returned control" end
        end
    end

    local ok, outcome, why = pcall(play)
    if not ok then return finish("crashed", "Lua error: " .. tostring(outcome)) end
    return finish(outcome, why)
end

return M
