-- botrun.lua -- the bot plays ONE chapter of the running ROM (#510 step 9, PR D).
--
-- Its own chunk, reached the way cases.lua is: harness.lua's `bot` scenario builds an `api`
-- table and calls Botrun.run(api). Nothing here touches emu, SYM or a harness global, so
-- test_botrun.lua drives it with a fake api and no emulator.
--
-- The loop: at the start of each player phase, build a fresh sight (sight.lua, one per phase)
-- and hash the board; then ask Bot.decide for one action at a time and perform it, until it
-- returns nil; then end the phase and ride the enemy phase out. The run ends:
--   won      the chapter advanced (api.won)
--   lost     the game-over screen came up (api.lost), or the enemy phase reached it
--   stuck    a player phase began on a board already seen this run: each on-field unit's id,
--            tile and HP, plus the objective's turns left (so holding a Defense map is not
--            circling). The bot decides from the board alone, so a repeat is a loop.
--   crashed  an action or an enemy phase the harness could not drive (a controller fault,
--            or an enemy phase that never returned control -- its own frame budget)
-- There is no turn cap: a repeated board is the only "no progress" rule (the amendment).
--
-- api (harness.lua builds it; test_botrun.lua fakes it):
--   info = { game, rom_hash, chapter, mode, seed }    what the record names the run by
--   style = Bot.STYLES-shaped table, claims = resolved claims (bot.lua's Claims)
--   seed(s)            seed the game's RNG (Sight.seed)
--   board()            Board.read
--   sight()            a fresh Sight.new for this phase
--   act(action)        perform Bot.decide's action: true; "noseize" when the menu offered no
--                      Seize (a crash: the game's CanUnitSeize had allowed it); false on a
--                      controller fault
--   endPhase()         "player" | "gameover" | "ended" | nil, and the deaths it saw:
--                      { { id, charId, faction, killer } } (id = Board's unit index byte,
--                      killer = the other fighter's charId)
--   won(), lost()      the chapter advanced / the game-over screen is up
--   frames()           emulated frames so far, every frame sight's sandbox ran included
--   emit(line)         print one line to stdout
--   log(s)
-- Botrun.run(api) -> ok, why, record. It emits the record as ONE stdout line, `BOTRUN <json>`.

local M = {}

local function here()
    local src = debug.getinfo(1, "S").source
    return (src:sub(1, 1) == "@" and src:sub(2):match("(.*/)")) or "./"
end
local Bot = dofile(here() .. "bot.lua")
local Json = dofile(here() .. "json.lua")

M.PREFIX = "BOTRUN "

-- The board at a player phase's start, as one string: who stands where with what HP, and the
-- objective's turns left.
function M.boardHash(board, objective)
    local parts = {}
    for _, u in ipairs(board.units) do
        if u.onField then parts[#parts + 1] = string.format("%d@%d,%d:%d", u.id, u.x, u.y, u.hp) end
    end
    table.sort(parts)
    parts[#parts + 1] = "left=" .. tostring(objective and objective.turnsLeft or "-")
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
    local style = Bot.applyClaims(api.claims or {}, api.style)
    local unplayed = Bot.unplayed(api.claims or {})
    local skipped = {}
    for _, id in ipairs(unplayed) do skipped[id] = true end
    local played = {}
    for _, c in ipairs(api.claims or {}) do
        if not skipped[c.id] then played[#played + 1] = c.id end
    end
    local rec = { game = api.info.game, rom_hash = api.info.rom_hash, chapter = api.info.chapter,
                  mode = api.info.mode, seed = api.info.seed, style = api.style,
                  claims_played = played, claims_unplayed = unplayed, deaths = {}, kills = {},
                  deployed = {}, bot_faults = {} }
    local startFrame = api.frames()
    api.seed(api.info.seed)
    local seen, turn = {}, 0

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
        api.emit(M.PREFIX .. Json.encode(rec))
        api.log(string.format("botrun: %s on turn %d (%s)", outcome, turn, why))
        return outcome == "won" or outcome == "lost" or outcome == "stuck", why, rec
    end

    while true do
        if api.won() then return finish("won", "the chapter advanced") end
        if api.lost() then return finish("lost", "game over") end
        local board = api.board()
        turn = board.turn
        if #rec.deployed == 0 then
            for _, u in ipairs(board.units) do
                if u.faction == "blue" and u.onField then rec.deployed[#rec.deployed + 1] = u.charId end
            end
        end
        local sight = api.sight()
        local h = M.boardHash(board, sight.objective)
        if seen[h] then return finish("stuck", "a player phase began on a board seen before") end
        seen[h] = true
        while true do
            local action = Bot.decide(board, sight, style)
            if not action then break end
            local done = api.act(action)
            if done == false then
                return finish("crashed", "the harness could not perform " .. action.act)
            end
            local after = api.board()
            local actor = byId(after)[action.unitId]
            if done == "noseize" then
                -- The bot only seizes with a unit the game's CanUnitSeize allows, on the tile its
                -- location event names: a menu without Seize there is the two disagreeing.
                return finish("crashed", "CanUnitSeize allowed it, but the menu offered no Seize")
            elseif actor and actor.onField and not actor.acted and after.turn == turn
                and after.phase == "blue" and not api.won() then
                -- The bot decides from the board, so an action that leaves its unit able to act
                -- would be asked for again, forever.
                return finish("crashed", "the action left its unit able to act")
            end
            record(fallen(board, after, action), "player")
            board = after
            if api.won() then return finish("won", "the chapter advanced") end
            if api.lost() then return finish("lost", "game over") end
            if board.phase ~= "blue" or board.turn ~= turn then break end
        end
        local before = api.board()
        local phase, deaths = api.endPhase()
        record(deaths or {}, "enemy")
        if phase == "gameover" then return finish("lost", "game over in the enemy phase") end
        if phase == "ended" then
            if api.won() then return finish("won", "the chapter advanced in the enemy phase") end
            return finish("lost", "the chapter ended without advancing")
        end
        if phase ~= "player" then
            return finish("crashed", "the enemy phase never returned control")
        end
        -- A unit seen on the field before the phase and dead after it, that the watcher missed.
        local counted = {}
        for _, d in ipairs(deaths or {}) do counted[d.id] = true end
        for _, d in ipairs(fallen(before, api.board(), nil)) do
            if not counted[d.id] then record({ d }, "enemy") end
        end
    end
end

return M
