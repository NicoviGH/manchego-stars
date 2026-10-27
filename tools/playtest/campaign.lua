-- campaign.lua -- the bot plays chapter to chapter (#510 step 9, PR E).
--
-- Its own chunk, reached the way botrun.lua is: harness.lua's `campaign` scenario builds an
-- `api` table and calls Campaign.run(api). Nothing here touches emu, SYM or a harness global,
-- so test_campaign.lua drives it with a fake api and no emulator.
--
-- The loop, per chapter: ride the game to the chapter's start (arrive: the scenes, the world
-- map's walk to its next story node, the route split), save a state there, then attempt it.
-- An attempt draws a NEW style, picks the deploy (Bot.prep), buys at the shops the world map
-- has open (Bot.shop, through the game's own shop screen), spends seals (Bot.promote), and
-- plays the chapter (botrun.lua). A clear with everyone alive moves on; anything else loads the
-- chapter-start state back and attempts again, at most MAX_ATTEMPTS times. The RNG is never
-- re-seeded on a restart: FE8 seeds it once at power-on and a suspend save stores it, so a
-- restart differs from the last only by the bot's new style and the game's RNG follows from
-- that different play (the amendment, #510).
-- A campaign stops when:
--   done        the game has no next chapter (arrive says "end")
--   infeasible  a chapter used MAX_ATTEMPTS without a clean clear: no later chapter is reached
--               by a clean run, so none is played
--   crashed     an attempt crashed (botrun's outcome), or the harness could not do a step
--               between chapters. A crash is the harness failing, never the bot: it is never
--               retried, so it cannot hide behind a restart.
--
-- api (harness.lua builds it; test_campaign.lua fakes it):
--   Bot, Json             bot.lua and json.lua
--   info = { game, rom_hash, mode, seed, campaign }
--   random()              a float in [0, 1): the campaign's own draws (route, styles)
--   arrive(route)         ride the game to the next chapter's start; at a route split the
--                         harness calls route(options) -> index. Returns { chapter = n } |
--                         "end" | nil, why
--   save(chapter)         write the chapter-start state and what the game gave (party, gold,
--                         items); true | nil, why
--   load(chapter)         load that state back; true | nil, why
--   roster()              bot.lua's roster entries: every unit the player could field this
--                         chapter, in slot order
--   cap()                 the prep screen's deploy cap, or nil when the chapter has no prep
--                         screen (the game fields its own list; nothing is picked)
--   deploy(charIds)       pick exactly these on the prep screen; true | nil, why
--   gold(), stock()       the party's gold; the stock of every shop the world map has open
--                         at this point (bot.lua's stock entries; {} when none)
--   buy(purchase)         one Bot.shop entry, through the shop screen; true | nil, why
--   promote(entry)        spend the seal the game accepts for this roster entry; true | nil, why
--   claims(chapter)       that chapter's resolved claims (bot.lua's Claims)
--   play(style, claims, attempt) -> botrun's record (it emits its own BOTRUN line)
--   emit(line), log(s)
-- Campaign.run(api) -> ok, why, chapters. Each chapter emits ONE stdout line,
-- `CAMPAIGN <json>`, and the campaign a last one with `chapter = nil`.

local M = {}

M.PREFIX = "CAMPAIGN "
M.MAX_ATTEMPTS = 300

local function pick(random, list) return list[math.floor(random() * #list) + 1] end

-- A style for one attempt: the aggression uniform over Bot.STYLES; the deploy a uniform shuffle
-- of the roster's non-forced units (Bot.prep cuts it at the cap, after the forced ones); each
-- claim followed with p = 0.5; the campaign's route. Returns the style and the claims followed.
function M.drawStyle(Bot, random, roster, claims, route)
    local deploy = {}
    for _, u in ipairs(roster) do
        if not u.forced then deploy[#deploy + 1] = u.charId end
    end
    for i = #deploy, 2, -1 do
        local j = math.floor(random() * i) + 1
        deploy[i], deploy[j] = deploy[j], deploy[i]
    end
    local followed, ids = {}, {}
    for _, c in ipairs(claims) do
        if random() < 0.5 then
            followed[#followed + 1] = c
            ids[#ids + 1] = c.id
        end
    end
    return { aggression = pick(random, Bot.STYLES.aggression), deploy = deploy, claims = ids,
             route = route }, followed
end

local function byCharId(roster)
    local out = {}
    for _, u in ipairs(roster) do out[u.charId] = u end
    return out
end

-- Between the chapter's start and its first move: the deploy, the shops, the seals. nil, why
-- when the harness could not do a step.
local function between(api, style)
    local Bot = api.Bot
    local roster, cap = api.roster(), api.cap()
    local party = roster
    if cap then
        local plan = Bot.prep(roster, cap, style)
        local ok, why = api.deploy(plan.deploy)
        if not ok then return nil, "deploy: " .. tostring(why) end
        local by = byCharId(roster)
        party = {}
        for _, charId in ipairs(plan.deploy) do party[#party + 1] = by[charId] end
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
    return true
end

function M.run(api)
    local Bot, Json, info = api.Bot, api.Json, api.info
    local route = pick(api.random, Bot.STYLES.route)
    local chapters = {}
    local function line(t)
        t.campaign, t.game, t.rom_hash, t.mode, t.seed =
            info.campaign, info.game, info.rom_hash, info.mode, info.seed
        api.emit(M.PREFIX .. Json.encode(t))
    end
    local function stop(outcome, why)
        line({ outcome = outcome, why = why, route = route, chapters = #chapters })
        api.log(string.format("campaign: %s after %d chapters (%s)", outcome, #chapters,
            tostring(why)))
        return outcome == "done", why, chapters
    end

    local function play()
        while true do
            local at, why = api.arrive(function(options)
                return Bot.route(options, { route = route })
            end)
            if at == "end" then return "done", "the game has no next chapter" end
            if not at then return "crashed", "arrive: " .. tostring(why) end
            local ch = at.chapter
            local ok, swhy = api.save(ch)
            if not ok then return "crashed", "save: " .. tostring(swhy) end
            local claims = api.claims(ch) or {}
            local entry = { chapter = ch, attempts = 0, failures = {} }
            chapters[#chapters + 1] = entry
            while true do
                entry.attempts = entry.attempts + 1
                local style, followed = M.drawStyle(Bot, api.random, api.roster(), claims, route)
                local bok, bwhy = between(api, style)
                if not bok then
                    entry.outcome = "crashed"
                    line(entry)
                    return "crashed", string.format("chapter %d attempt %d: %s", ch,
                        entry.attempts, bwhy)
                end
                local rec = api.play(style, followed, entry.attempts)
                if rec.outcome == "won" and rec.all_alive then
                    entry.outcome, entry.turns = "cleared", rec.turns
                    break
                end
                entry.failures[#entry.failures + 1] = { attempt = entry.attempts, style = style,
                    outcome = rec.outcome, deaths = rec.deaths }
                if rec.outcome == "crashed" then
                    entry.outcome = "crashed"
                    line(entry)
                    return "crashed", string.format("chapter %d attempt %d crashed", ch,
                        entry.attempts)
                end
                if entry.attempts >= M.MAX_ATTEMPTS then
                    entry.outcome = "infeasible"
                    line(entry)
                    return "infeasible", string.format("chapter %d: no clean clear in %d attempts",
                        ch, entry.attempts)
                end
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
