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
--   info = { game, rom_hash, chapter, mode, seed, campaign, attempt }  what the record names
--                      the run by; campaign and attempt only when campaign.lua plays it
--   style = Bot.STYLES-shaped table, claims = resolved claims (bot.lua's Claims)
--   seed(s)            seed the game's RNG (Sight.seed)
--   board()            Board.read
--   sight()            Sight.new, called once
--   act(action)        perform Bot.decide's action: true; "noseize" when the menu offered no
--                      Seize; false on a controller fault
--   endPhase()         "player" | "gameover" | "ended" | nil, and the deaths it saw:
--                      { { id, charId, faction, killer } } (id = Board's unit index byte,
--                      killer = the other fighter's charId)
--   won(), lost()      the chapter advanced / the game-over screen is up
--   frames()           emulated frames so far, every frame sight's sandbox ran included
--   costs()            OPTIONAL: { cpu_s, sandbox_calls, save_s, load_s, run_s } so far; the
--                      record carries what the run itself spent
--   emit(line)         print one line to stdout
--   log(s)
-- Botrun.run(api) -> ok, why, record. It emits the record as ONE stdout line, `BOTRUN <json>`.

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

-- Units on the field before and gone after, with the fighter that downed them. A player-phase
-- action has one fight: the actor and its target are each other's killer.
local function fallen(before, after, action)
    local now, out = byId(after), {}
    for _, u in ipairs(before.units) do
        local n = now[u.id]
        if u.onField and not u.dead and (n == nil or n.dead) then
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
                  deployed = {}, bot_faults = {} }
    local startFrame = api.frames()
    local startCosts = api.costs and api.costs() or {}
    local turn = 0

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
        rec.outcome, rec.turns = outcome, turn
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
        api.emit(M.PREFIX .. Json.encode(rec))
        api.log(string.format("botrun: %s on turn %d (%s)", outcome, turn, why))
        return outcome == "won" or outcome == "lost" or outcome == "stuck", why, rec
    end

    local function play()
        api.seed(api.info.seed)
        local sight = api.sight()
        local seen, waitUntil = {}, nil
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
            while true do
                -- one decision's reads in one save/load (sight.batch), when the sight batches
                local function decide() return Bot.decide(board, sight, style) end
                local action
                if sight.batch then action = sight.batch(decide) else action = decide() end
                if not action then break end
                local done = api.act(action)
                if done == false then
                    return "crashed", "the harness could not perform " .. action.act
                end
                local after = api.board()
                sight.refresh()
                local actor = byId(after)[action.unitId]
                record(fallen(board, after, action), "player")
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
            local phase, deaths = api.endPhase()
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
