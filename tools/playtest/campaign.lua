-- campaign.lua -- the bot plays chapter to chapter (#510 step 9, PR E).
--
-- Its own chunk, reached the way botrun.lua is: harness.lua's `campaign` scenario builds an
-- `api` table and calls Campaign.run(api). Nothing here touches emu, SYM or a harness global,
-- so test_campaign.lua drives it with a fake api and no emulator.
--
-- The loop, per chapter: ride the game to the chapter's start (arrive: the scenes, the world
-- map's walk to its next story node, the route split), save a state there, then attempt it.
-- An attempt draws a style never tried at this chapter start (drawStyle), picks the team
-- (Bot.team, over what the map asks: api.needs, read once per chapter start since every attempt
-- starts from the same state), buys at the shops the world map has open (Bot.shop, through the
-- game's own shop screen), spends seals (Bot.promote), and plays the chapter (botrun.lua). A
-- clean clear (the record's `clean`: won, no blue or green unit lost, every owed recruit
-- joined, every village and chest taken) moves on and its team is CARRIED into the next
-- chapter's pick; anything else loads the chapter-start state back and attempts again, at most
-- MAX_ATTEMPTS times (the retry cap, ADR 0399). The team follows from the claims a style
-- follows (a carry claim's units); once every style has been tried they are drawn again, each
-- one only if it was not yet played with what is remembered now (a style and a memory already
-- played replay that try exactly); with none left the chapter stops. The game's RNG is never re-seeded on a restart: FE8 seeds it once at
-- power-on and a suspend save stores it, so a restart differs from the last only by the bot's
-- style, its memory, and the game's RNG following from that different play (the amendment, #510).
-- A retry remembers what earlier failed attempts at this start showed on screen, from attempt 2
-- on: the turns a reinforcement arrived (botrun's `arrivals_seen`, ADR 0386) as one more list
-- in style.arrivals, where a reinforcements claim's turns go; and (ADR 0399) style.memory =
-- { enemies }: every red unit a board showed out of fog and every killer a fight showed
-- (botrun's `enemies_seen`), by slot, character and class (Board.memoryKey). A death is
-- remembered through its killer: where our units stood is the play's, not the game's. Never a
-- dice result.
-- One attempt alone (api.only = k, montecarlo.py's pool, #510 step 9 PR F): the k-th style
-- this chapter start would draw is played, and nothing else. Every attempt loads the same
-- start state, the game's RNG in it; the style draws restart at each chapter start (api.seed)
-- and never read a result; and the start carries the team the campaign carried in (api.save,
-- arrive). So attempt k plays the style and team it would after k - 1 failures, but it is an
-- independent attempt, not the campaign's k-th try: it has no memory (the workers side by side
-- share no results, ADR 0386), and it ends at the style count, where the loop draws the styles
-- again with memory (ADR 0399). Attempt 1, every measured cell (ADR 0385), is the same either
-- way. It saves no state (the workers share the start's files) and moves on to no chapter.
-- A campaign stops when:
--   done        the game has no next chapter (arrive says "end")
--   played      api.only: its attempt was played (whatever the record says)
--   no_style    api.only: this chapter start has fewer than k styles
--   infeasible  Manchego Stars: a chapter used MAX_ATTEMPTS without a clean clear: no later
--               chapter is reached by a clean run, so none is played
--   bot_fault   the same on vanilla, which strong players clear clean: the bot is what failed,
--               never the chapter (#510 step 9 design, decision 2). The chapter line's failures
--               carry what spoiled each attempt and its trace
--   crashed     an attempt crashed (botrun's outcome), or the harness could not do a step
--               between chapters. A crash is the harness failing, never the bot: it is never
--               retried, so it cannot hide behind a restart.
--
-- api (harness.lua builds it; test_campaign.lua fakes it):
--   Bot, Json             bot.lua and json.lua
--   info = { game, rom_hash, mode, seed, campaign, route }: route = which branch of a route
--                         split (vanilla's Ch8) the campaign takes, a SETTING, never drawn (#510
--                         plan comment, "Lords"); a split with none set raises in Bot.route
--   random()              a float in [0, 1): the campaign's own draws (styles)
--   seed(chapter)         restart random()'s draws for this chapter start, from (seed, chapter)
--   arrive(route)         ride the game to the next chapter's start; at a route split the
--                         harness calls route(options) -> index. Returns { chapter = n,
--                         carried = {charIds}|nil (a resumed start: the team carried in),
--                         carriedUnknown = true|nil (a start saved before records kept it) } |
--                         "end" | nil, why
--   save(chapter, carried) write the chapter-start state, what the game gave (party, gold,
--                         items) and the carried team (charIds; nil = unknown, left out of the
--                         record); true | nil, why
--   load(chapter)         load that state back; true | nil, why
--   roster()              bot.lua's roster entries: every unit the player could field this
--                         chapter, in slot order, each with its classId
--   teamGroups()          groups, maxima: class id (string) -> team group, and each group's
--                         most fielded (team_groups.py)
--   needs(roster)         { demands, answers, strength } for Bot.team, read at the prep screen
--   cap()                 the prep screen's deploy cap, or nil when the chapter has no prep
--                         screen (the game fields its own list; nothing is picked)
--   deploy(charIds)       pick exactly these on the prep screen; true | nil, why
--   gold(), stock()       the party's gold; the stock of every shop the world map has open
--                         at this point (bot.lua's stock entries; {} when none)
--   buy(purchase)         one Bot.shop entry, through the shop screen; true | nil, why
--   promote(entry)        spend the seal the game accepts for this roster entry; true | nil, why
--   claims(chapter)       that chapter's resolved claims (bot.lua's Claims)
--   play(style, claims, attempt) -> botrun's record (it emits its own BOTRUN line)
--   only                  OPTIONAL: the one attempt to play (see above)
--   startOnly             OPTIONAL: a chapter index; the campaign stops once that chapter's start
--                         state is saved, unplayed (montecarlo.py `starts`: a cell loads only it)
--   diag                  OPTIONAL, with only: that attempt is a diagnostic replay (botrun.lua's
--                         api.diag). Its one DIAG line is all it writes: no CAMPAIGN line, so
--                         no endpoint is recorded, and it hands no record back
--   emit(line), log(s)
-- Campaign.run(api) -> ok, why, chapters. Each chapter emits ONE stdout line,
-- `CAMPAIGN <json>`, and the campaign a last one with `chapter = nil`.

local M = {}

M.PREFIX = "CAMPAIGN "
-- the retry cap a chapter start (Nicolas, 2026-11-10; ADR 0399): late chapters need many
-- restarts, and memory makes a repeated style play differently, so styles are drawn again once
-- every one has been tried
M.MAX_ATTEMPTS = 12

local function pick(random, list) return list[math.floor(random() * #list) + 1] end

-- A style for one attempt, never one already tried since `tried` was last emptied: the aggression
-- uniform over Bot.STYLES, each claim the bot can play followed with p = 0.5, the campaign's
-- route. A claim Bot.unplayed names plays the same followed or not, so it is no part of a style
-- (vanilla Ch5: four such claims made 48 styles that played as 3). `tried` is the keys drawn so
-- far. Returns the style and the claims followed, or nil when every style has been tried (the
-- loop then empties `tried` and draws again, skipping a try already played; one attempt alone
-- says no_style).
local function styleKey(aggression, ids) return aggression .. "|" .. table.concat(ids, ",") end

function M.drawStyle(Bot, random, claims, route, tried)
    local unplayed, playable = {}, {}
    for _, id in ipairs(Bot.unplayed(claims)) do unplayed[id] = true end
    for _, c in ipairs(claims) do
        if not unplayed[c.id] then playable[#playable + 1] = c end
    end
    claims = playable
    local total, n = #Bot.STYLES.aggression * 2 ^ #claims, 0
    for _ in pairs(tried) do n = n + 1 end
    if n >= total then return nil end
    while true do
        local followed, ids = {}, {}
        for _, c in ipairs(claims) do
            if random() < 0.5 then
                followed[#followed + 1] = c
                ids[#ids + 1] = c.id
            end
        end
        local aggression = pick(random, Bot.STYLES.aggression)
        local key = styleKey(aggression, ids)
        if not tried[key] then
            tried[key] = true
            return { aggression = aggression, claims = ids, route = route }, followed
        end
    end
end

local function byCharId(roster)
    local out = {}
    for _, u in ipairs(roster) do out[u.charId] = u end
    return out
end

-- Between the chapter's start and its first move: the team, the shops, the seals. `need` is
-- the chapter's api.needs (nil without a prep screen); `carried` the last cleared team. Returns
-- the team ({ deploy, reasons }; deploy = the units fielded) or nil, why when the harness could
-- not do a step.
local function between(api, style, followed, need, carried)
    local Bot = api.Bot
    local roster = api.roster()
    local cap, cwhy = api.cap()
    if cwhy then return nil, "cap: " .. cwhy end
    local team = { deploy = {}, reasons = {} }
    local party = {}
    if cap then
        local groups, maxima = api.teamGroups()
        for _, u in ipairs(roster) do u.group = groups[tostring(u.classId)] end
        team = Bot.team({ roster = roster, cap = cap, maxima = maxima, demands = need.demands,
                          answers = need.answers, strength = need.strength, carried = carried,
                          style = Bot.applyClaims(followed, { deploy = {} }) })
        local said = {}
        for _, u in ipairs(roster) do
            local r = team.reasons[u.charId]
            said[#said + 1] = string.format("0x%02X %s%s%s=%s", u.charId, tostring(u.group),
                u.forced and " forced" or "", carried[u.charId] and " carried" or "",
                r and r.why or "benched")
        end
        api.log("campaign: team (cap " .. cap .. "): " .. table.concat(said, ", "))
        local ok, why = api.deploy(team.deploy)
        if not ok then return nil, "deploy: " .. tostring(why) end
        local by = byCharId(roster)
        for _, charId in ipairs(team.deploy) do party[#party + 1] = by[charId] end
    else
        party = roster
        for _, u in ipairs(roster) do team.deploy[#team.deploy + 1] = u.charId end
    end
    for _, p in ipairs(Bot.shop(api.gold(), api.stock(), party)) do
        local ok, why = api.buy(p)
        if not ok then return nil, "buy: " .. tostring(why) end
    end
    -- Re-read after the shop: a seal bought or moved changes what each unit holds.
    local now = byCharId(api.roster())
    local fielded = {}
    for _, u in ipairs(party) do fielded[#fielded + 1] = now[u.charId] or u end
    for _, u in ipairs(Bot.promoteOrder(fielded)) do
        if Bot.promote(u, u.items) then
            local ok, why = api.promote(u)
            if not ok then return nil, "promote: " .. tostring(why) end
        end
    end
    return team
end

function M.run(api)
    local Bot, Json, info = api.Bot, api.Json, api.info
    local route = info.route
    local chapters = {}
    local function line(t)
        if api.diag then return end   -- a diagnostic writes only its DIAG line (botrun.lua)
        t.campaign, t.game, t.rom_hash, t.mode, t.seed =
            info.campaign, info.game, info.rom_hash, info.mode, info.seed
        api.emit(M.PREFIX .. Json.encode(t))
    end
    local function stop(outcome, why)
        line({ outcome = outcome, why = why, route = route, chapters = #chapters })
        api.log(string.format("campaign: %s after %d chapters (%s)", outcome, #chapters,
            tostring(why)))
        return outcome == "done" or outcome == "played" or outcome == "no_style", why, chapters
    end

    -- a chapter with no clean clear left to try: on vanilla the bot's fault, on
    -- Manchego Stars infeasible
    local function noClean(entry, tried)
        local fault = info.game == "vanilla"
        entry.outcome = fault and "bot_fault" or "infeasible"
        line(entry)
        return entry.outcome, string.format("chapter %d: no clean clear in " .. tried .. "%s",
            entry.chapter, entry.attempts, fault and ", a bot fault" or "")
    end

    local function play()
        local carried = {}
        while true do
            local at, why = api.arrive(function(options)
                return Bot.route(options, { route = route })
            end)
            if at == "end" then return "done", "the game has no next chapter" end
            if not at then return "crashed", "arrive: " .. tostring(why) end
            local ch = at.chapter
            api.seed(ch)
            if at.carried then
                carried = {}
                for _, charId in ipairs(at.carried) do carried[charId] = true end
            end
            if not api.only then
                -- a team the start's record never kept stays unknown when it is saved again
                local list
                if not at.carriedUnknown then
                    list = {}
                    for charId in pairs(carried) do list[#list + 1] = charId end
                    table.sort(list)
                end
                local ok, swhy = api.save(ch, list)
                if not ok then return "crashed", "save: " .. tostring(swhy) end
                if api.startOnly == ch then
                    return "done", string.format("chapter %d's start is saved", ch)
                end
            end
            local claims = api.claims(ch) or {}
            local entry = { chapter = ch, attempts = 0, failures = {},
                            carried_unknown = at.carriedUnknown or nil }
            chapters[#chapters + 1] = entry
            local cap, cwhy = api.cap()
            if cwhy then return "crashed", string.format("chapter %d: cap: %s", ch, cwhy) end
            local need = cap and api.needs(api.roster()) or nil
            entry.demands = need and need.demands or nil
            local tried, remembered, known = {}, {}, {}
            -- a retry's memory of the enemy (ADR 0399): style.memory
            local memory, memoryKeys = { enemies = {} }, {}
            -- a unit whose class was not read cannot be told from another in its slot (its key
            -- would match nothing, and grow the memory with nothing learned): not kept
            local function rememberEnemy(id, charId, classId)
                local k = Bot.memoryKey(id, charId, classId)
                if classId ~= nil and not memoryKeys[k] then
                    memoryKeys[k] = true
                    memory.enemies[#memory.enemies + 1] = { id = id, charId = charId,
                                                            classId = classId }
                end
            end
            -- the tries made, by style and what was remembered then: the start state restores
            -- the game's RNG, so the same style with the same memory replays that try move for
            -- move, and is never spent again. Both lists only grow, so their sizes say which
            local played = {}
            local function tryKey(style)
                return styleKey(style.aggression, style.claims) .. "#" .. #memory.enemies .. "/"
                    .. #remembered
            end
            -- from a draw on, the first style not yet played with this memory (nil: none left)
            local function unplayed(style, followed)
                while style and played[tryKey(style)] do
                    style, followed = M.drawStyle(Bot, api.random, claims, route, tried)
                end
                return style, followed
            end
            while true do
                local style, followed = M.drawStyle(Bot, api.random, claims, route, tried)
                -- one attempt alone: the styles before it are drawn, never played
                while style and api.only and entry.attempts + 1 < api.only do
                    entry.attempts = entry.attempts + 1
                    style, followed = M.drawStyle(Bot, api.random, claims, route, tried)
                end
                if not style and api.only then
                    entry.outcome = "no_style"
                    line(entry)
                    return "no_style", string.format("chapter %d has %d styles, not %d", ch,
                        entry.attempts, api.only)
                end
                style, followed = unplayed(style, followed)
                if not style then
                    -- every style tried: draw them again, each one not yet played with what is
                    -- remembered now (ADR 0399); none left, and a retry could only replay a try
                    tried = {}
                    style, followed = unplayed(M.drawStyle(Bot, api.random, claims, route, tried))
                    if not style then
                        return noClean(entry, "%d attempts, every style played with what it remembers")
                    end
                end
                played[tryKey(style)] = true
                entry.attempts = entry.attempts + 1
                local team, bwhy = between(api, style, followed, need, carried)
                if not team then
                    entry.outcome = "crashed"
                    line(entry)
                    return "crashed", string.format("chapter %d attempt %d: %s", ch,
                        entry.attempts, bwhy)
                end
                -- a retry's memory (ADR 0386): the turns earlier failures here saw a
                -- reinforcement arrive on screen, read where a reinforcements claim's are
                -- (style.arrivals); attempt 1, and any attempt alone, has none
                if #remembered > 0 then style.arrivals = { table.move(remembered, 1, #remembered, 1, {}) } end
                -- and every enemy they showed (ADR 0399), from attempt 2
                if #memory.enemies > 0 then
                    local copy = {}   -- each attempt its own copy
                    for i, e in ipairs(memory.enemies) do
                        copy[i] = { id = e.id, charId = e.charId, classId = e.classId }
                    end
                    style.memory = { enemies = copy }
                end
                local rec = api.play(style, followed, entry.attempts)
                if api.diag then
                    return "played", string.format("chapter %d attempt %d: diagnostic replayed", ch,
                        entry.attempts)
                end
                if api.only then
                    entry.outcome, entry.turns = rec.outcome, rec.turns
                    line(entry)
                    return "played", string.format("chapter %d attempt %d: %s", ch,
                        entry.attempts, tostring(rec.outcome))
                end
                if rec.clean == true then
                    entry.outcome, entry.turns = "cleared", rec.turns
                    entry.team = { deploy = team.deploy, reasons = {} }
                    for _, charId in ipairs(team.deploy) do
                        local r = team.reasons[charId] or { why = "fielded" }
                        r.charId = charId
                        entry.team.reasons[#entry.team.reasons + 1] = r
                    end
                    carried = {}
                    for _, charId in ipairs(team.deploy) do carried[charId] = true end
                    break
                end
                entry.failures[#entry.failures + 1] = { attempt = entry.attempts, style = style,
                    team = team.deploy, outcome = rec.outcome, deaths = rec.deaths,
                    clear = rec.clear, trace = rec.trace }
                if rec.outcome == "crashed" then
                    entry.outcome = "crashed"
                    line(entry)
                    return "crashed", string.format("chapter %d attempt %d crashed", ch,
                        entry.attempts)
                end
                for _, a in ipairs(rec.arrivals_seen or {}) do
                    if not known[a.turn] then
                        known[a.turn] = true
                        remembered[#remembered + 1] = a.turn
                    end
                end
                table.sort(remembered)
                for _, e in ipairs(rec.enemies_seen or {}) do
                    rememberEnemy(e.id, e.charId, e.classId)
                end
                if entry.attempts >= M.MAX_ATTEMPTS then return noClean(entry, "%d attempts") end
                local lok, lwhy = api.load(ch)
                if not lok then
                    entry.outcome = "crashed"
                    line(entry)
                    return "crashed", "load: " .. tostring(lwhy)
                end
            end
            line(entry)
        end
    end

    local ok, outcome, why = pcall(play)
    if not ok then return stop("crashed", "Lua error: " .. tostring(outcome)) end
    return stop(outcome, why)
end

return M
