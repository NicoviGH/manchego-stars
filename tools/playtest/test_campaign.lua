-- Tests for campaign.lua -- the bot playing chapter to chapter (#510 step 9 PR E), over a fake
-- game: a list of chapters, each with a scripted list of attempt outcomes, so no emulator.
-- Run: lua tools/playtest/test_campaign.lua
local here = (arg[0]:match("(.*/)")) or "./"
local Campaign = dofile(here .. "campaign.lua")
local Json = dofile(here .. "json.lua")
local Bot = dofile(here .. "bot.lua")

local tests, fails = 0, 0
local function check(got, want, msg)
    tests = tests + 1
    if got ~= want then
        fails = fails + 1
        print(string.format("FAIL: %s\n  got  %s\n  want %s", msg, tostring(got), tostring(want)))
    end
end

-- A deterministic random(): cycles through `seq`.
local function cycle(seq)
    local i = 0
    return function()
        i = i % #seq + 1
        return seq[i]
    end
end

local function roster()
    return {
        { id = 1, charId = 0x01, classId = 2, level = 5, forced = true, canUse = {}, items = {} },
        { id = 2, charId = 0x02, classId = 5, level = 3, canUse = { [0x10] = true }, items = {} },
        { id = 3, charId = 0x03, classId = 0x26, level = 9, canUse = {}, items = {} },
        { id = 4, charId = 0x04, classId = 5, level = 1, canUse = {}, items = {} },
    }
end

-- A fake game. o.chapters = { { id, outcomes = { "won"|"lost"|"dead"|"stuck"|"crashed"|"timeout"... },
-- options = n (a route split before it), needs = Bot.team's demands/answers/strength } };
-- "dead" is a win with a death, "spoiled" a win with a recruit missed. o.route = the
-- campaign's route setting, o.game the game (default "fake"). ch.seen = { [attempt] =
-- arrivals_seen } (the record's reinforcements seen on screen, ADR 0386).
local function fakeGame(o)
    local g = { at = 0, saved = {}, loads = 0, deployed = {}, bought = {}, promoted = {},
                plays = {}, emitted = {}, seeds = {}, routeAsked = nil, attempt = 0, dice = {} }
    g.api = {
        Bot = Bot, Json = Json,
        info = { game = o.game or "fake", rom_hash = "abc", mode = "normal", seed = 7, campaign = "c1",
                 route = o.route },
        random = o.random or cycle({ 0.1, 0.6, 0.3, 0.9, 0.5 }),
        arrive = function(route)
            g.at = g.at + 1
            local ch = o.chapters[g.at]
            if not ch then return "end" end
            if ch.options then g.routeAsked = route({ "a", "b" }) end
            if ch.arriveFails then return nil, "the world map never handed over" end
            g.attempt = 0
            return { chapter = ch.id, carried = ch.carried, carriedUnknown = ch.carriedUnknown }
        end,
        seed = function(ch) g.seeds[#g.seeds + 1] = ch; if o.seed then o.seed(ch) end end,
        snapshot = function()
            return o.snapshot or { gold = o.gold or 0, party = {}, convoy = {}, shops = {} }
        end,
        save = function(ch, record)
            g.saved[#g.saved + 1] = ch
            g.carriedSaved = g.carriedSaved or {}
            g.carriedSaved[ch] = record.carried
            g.records = g.records or {}
            g.records[ch] = record
            return true
        end,
        load = function() g.loads = g.loads + 1; return true end,
        roster = roster,
        cap = function() return o.cap end,
        teamGroups = function()
            return { ["2"] = "lord", ["5"] = "mounted", ["38"] = "healer" }, { mounted = 3 }
        end,
        needs = function(_, arms)
            g.needsAsked = (g.needsAsked or 0) + 1
            g.arms = arms
            return o.chapters[g.at].needs or { demands = {}, answers = {}, strength = {} }
        end,
        deploy = function(ids) g.deployed[#g.deployed + 1] = ids; return true end,
        gold = function() return o.gold or 0 end,
        stock = function() return o.stock or {} end,
        buy = function(p) g.bought[#g.bought + 1] = p; return true end,
        promote = function(u) g.promoted[#g.promoted + 1] = u.charId; return true end,
        claims = function() return o.claims or {} end,
        -- harness.lua's advanceDice: the draws advanced, handed back for the record
        advanceDice = function(n) g.dice[#g.dice + 1] = n; return n end,
        play = function(style, claims, attempt, pick, dice)
            local ch = o.chapters[g.at]
            g.attempt = g.attempt + 1
            local out = (ch.outcomes or {})[g.attempt] or "won"
            g.plays[#g.plays + 1] = { chapter = ch.id, style = style, claims = claims,
                                      attempt = attempt, pick = pick, dice = dice }
            local deaths = {}
            if out == "dead" or out == "lost" then
                deaths = { { id = 2, charId = 0x02, faction = "blue", turn = 3, killer = 0x40,
                             killerId = 0x90, killerClass = 0x0C, phase = "enemy" } }
            end
            local won = out == "won" or out == "dead" or out == "spoiled"
            return { outcome = won and "won" or out, clean = out == "won", turns = 4,
                     deaths = deaths, trace = "t" .. g.attempt,
                     arrivals_seen = (ch.seen or {})[g.attempt] or {},
                     enemies_seen = (ch.enemies or {})[g.attempt] or {},
                     clear = { won = won, lost = deaths,
                               recruits_missing = out == "spoiled" and { 0x30 } or {},
                               rewards_missing = {} } }
        end,
        emit = function(line) g.emitted[#g.emitted + 1] = line end,
        log = function() end,
    }
    return g
end

local function lines(g)
    local out = {}
    for _, l in ipairs(g.emitted) do
        out[#out + 1] = Json.decode(l:sub(#Campaign.PREFIX + 1))
    end
    return out
end

local function test_restart_redraws_style_not_seed()
    local g = fakeGame({ chapters = { { id = 3, outcomes = { "lost", "dead", "won" } } } })
    local ok = Campaign.run(g.api)
    check(ok, true, "the campaign ends done")
    check(#g.plays, 3, "three attempts")
    check(g.loads, 2, "each failed attempt loads the chapter-start state back")
    for _, p in ipairs(g.plays) do
        check(g.api.info.seed, 7, "the seed is never redrawn")
        check(p.chapter, 3, "every attempt is the same chapter")
    end
    local same = Json.encode(g.plays[1].style) == Json.encode(g.plays[2].style)
        and Json.encode(g.plays[2].style) == Json.encode(g.plays[3].style)
    check(same, false, "a restart draws a new style")
end
test_restart_redraws_style_not_seed()

-- api.startOnly = n (montecarlo.py `starts`, T100e): the campaign stops once chapter n's start
-- state is saved, never playing it, since a cell only loads that start.
local function test_a_starts_campaign_stops_at_its_last_start()
    local g = fakeGame({ chapters = { { id = 1, outcomes = { "won" } },
                                      { id = 2, outcomes = { "won" } } } })
    g.api.startOnly = 2
    local ok, why = Campaign.run(g.api)
    check(ok, true, "stopping at the last start is a finished run")
    check(#g.saved, 2, "both starts are saved")
    check(#g.plays, 1, "the last chapter is never played")
    check(why, "chapter 2's start is saved", "and it says where it stopped")
end
test_a_starts_campaign_stops_at_its_last_start()

-- api.only = k plays the style the loop plays at attempt k after k - 1 failures, and only
-- it: no state saved, no chapter after it, and a k past the styles there are says so.
local function test_one_attempt_alone_is_the_loops_kth()
    local seq = fakeGame({ chapters = { { id = 3, outcomes = { "lost", "dead", "won" } } } })
    Campaign.run(seq.api)
    local alone = fakeGame({ chapters = { { id = 3 }, { id = 4 } } })
    alone.api.only = 3
    local ok, why = Campaign.run(alone.api)
    check(ok, true, "one attempt played is a finished run")
    check(#alone.plays, 1, "only the one attempt is played")
    -- the loop's attempt 3 also carries its memory (ADR 0399); the style drawn is the same
    local drawn = {}
    for k, v in pairs(seq.plays[3].style) do
        if k ~= "memory" and k ~= "arrivals" then drawn[k] = v end
    end
    check(Json.encode(alone.plays[1].style), Json.encode(drawn),
          "attempt 3 alone plays the loop's third style")
    check(alone.plays[1].attempt, 3, "and is numbered 3")
    check(#alone.saved, 0, "it writes no chapter-start state")
    check(why, "chapter 3 attempt 3: won", "and stops after it")
    local none = fakeGame({ chapters = { { id = 3 } } })
    none.api.only = 99
    local nok, nwhy = Campaign.run(none.api)
    check(nok, true, "a k past every style is an answer, not a crash")
    check(#none.plays, 0, "nothing is played")
    check(nwhy:match("has %d+ styles, not 99") ~= nil, true, "it says how many there are")
end
test_one_attempt_alone_is_the_loops_kth()

-- A diagnostic replay of attempt k (botrun.lua's api.diag, #510 step 9 PR F): its DIAG line is
-- all it writes. botrun hands no record back, and the campaign writes no CAMPAIGN line, so no
-- endpoint is recorded.
local function test_a_diagnostic_attempt_writes_no_campaign_line()
    local g = fakeGame({ chapters = { { id = 3 }, { id = 4 } } })
    g.api.only, g.api.diag = 1, { ref = 1, mode = "deep" }
    local play = g.api.play
    g.api.play = function(...) play(...); return nil end
    local ok, why = Campaign.run(g.api)
    check(ok, true, "a diagnostic attempt played is a finished run")
    check(#g.plays, 1, "the one attempt is played")
    check(#lines(g), 0, "no CAMPAIGN line is written")
    check(why, "chapter 3 attempt 1: diagnostic replayed", "and it says what it did")
end
test_a_diagnostic_attempt_writes_no_campaign_line()

local function test_attempts_recorded()
    local g = fakeGame({ chapters = { { id = 3, outcomes = { "lost", "stuck", "won" } },
                                      { id = 4, outcomes = { "won" } } } })
    Campaign.run(g.api)
    local ls = lines(g)
    check(#ls, 3, "one line per chapter and one for the campaign")
    check(ls[1].chapter, 3, "the first chapter's line")
    check(ls[1].attempts, 3, "attempts counted")
    check(ls[1].outcome, "cleared", "cleared on the third")
    check(#ls[1].failures, 2, "both failed attempts recorded")
    check(ls[1].failures[1].outcome, "lost", "the first failure's outcome")
    check(ls[1].failures[1].deaths[1].charId, 0x02, "with its deaths")
    check(ls[1].failures[2].outcome, "stuck", "a stuck run is a failed attempt, restarted")
    check(type(ls[1].failures[1].style.aggression), "string", "with its style")
    check(ls[2].attempts, 1, "the next chapter cleared on its first")
    check(ls[3].outcome, "done", "the campaign line")
    check(ls[3].chapters, 2, "names how many chapters it played")
    check(ls[3].campaign, "c1", "every line names the campaign")
end
test_attempts_recorded()

local function test_state_written_per_chapter_start()
    local g = fakeGame({ chapters = { { id = 1 }, { id = 2, outcomes = { "lost" } }, { id = 3 } } })
    Campaign.run(g.api)
    check(table.concat(g.saved, ","), "1,2,3", "one state per chapter start, never per attempt")
end
test_state_written_per_chapter_start()

local function test_route_is_the_campaign_setting()
    local g = fakeGame({ route = 2, chapters = { { id = 1 }, { id = 2, options = 2 } } })
    Campaign.run(g.api)
    check(g.routeAsked, 2, "the split takes the campaign's route setting")
    for _, p in ipairs(g.plays) do check(p.style.route, 2, "every attempt's style carries it") end
    g = fakeGame({ chapters = { { id = 1 }, { id = 2, options = 2 } } })
    local ok, why = Campaign.run(g.api)
    check(ok, false, "a split with no route set stops the campaign: the route is never drawn")
    check(why:find("route") ~= nil, true, "naming the route")
end
test_route_is_the_campaign_setting()

local function test_crash_is_never_retried()
    local g = fakeGame({ chapters = { { id = 1, outcomes = { "crashed", "won" } }, { id = 2 } } })
    local ok, why = Campaign.run(g.api)
    check(ok, false, "a crash stops the campaign")
    check(#g.plays, 1, "and is not retried")
    check(g.loads, 0, "no restart")
    check(why:find("crashed") ~= nil, true, "the reason says so")
    local ls = lines(g)
    check(ls[#ls].outcome, "crashed", "the campaign line says crashed")
end
test_crash_is_never_retried()

-- A decision over its frame budget (botrun's `timeout`, ADR 0411) stops the campaign as a crash
-- does, under its own name: a retry would meet the same board and spend the same budget.
local function test_timeout_is_never_retried()
    local g = fakeGame({ chapters = { { id = 1, outcomes = { "timeout", "won" } }, { id = 2 } } })
    local ok, why = Campaign.run(g.api)
    check(ok, false, "a timeout stops the campaign")
    check(#g.plays, 1, "and is not retried")
    check(g.loads, 0, "no restart")
    local ls = lines(g)
    check(ls[#ls].outcome, "timeout", "the campaign line says timeout")
    check(ls[#ls - 1].outcome, "timeout", "and so does the chapter's")
    check(why:find("attempt 1") ~= nil, true, "the reason names the attempt")
end
test_timeout_is_never_retried()

local function test_arrive_failure_is_a_crash()
    local g = fakeGame({ chapters = { { id = 1, arriveFails = true } } })
    local ok, why = Campaign.run(g.api)
    check(ok, false, "a world map the harness cannot ride stops the campaign")
    check(why:find("never handed over") ~= nil, true, "with the harness's reason")
end
test_arrive_failure_is_a_crash()

local function test_infeasible_after_max_attempts()
    local saved = Campaign.MAX_ATTEMPTS
    Campaign.MAX_ATTEMPTS = 4
    -- One claim: 3 aggressions x 2 = 6 styles, so the allowance (4) is what stops it.
    local g = fakeGame({ claims = { { id = "a", kind = "carry", unit = { 1 }, vs = "all" } },
                         chapters = { { id = 5, outcomes = { "lost", "lost", "lost", "lost",
                                                              "won" } }, { id = 6 } } })
    local ok, why = Campaign.run(g.api)
    Campaign.MAX_ATTEMPTS = saved
    check(ok, false, "no clean clear in the allowance stops the campaign")
    check(#g.plays, 4, "exactly the allowance is spent")
    check(why:find("chapter 5") ~= nil, true, "naming the chapter")
    local ls = lines(g)
    check(ls[1].outcome, "infeasible", "the chapter line says infeasible")
    check(#ls[1].failures, 4, "every attempt's failure is kept")
    check(ls[2].outcome, "infeasible", "and so does the campaign line")
end
test_infeasible_after_max_attempts()

-- the scout lap (api.scout, #510 comment 6872554917): a vanilla chapter with no clean clear is
-- carried on past from its first win with no player unit lost, and from M.SCOUT_PATIENCE on,
-- from any win; the chapter line says scouted, every line says scout, and the dead are not
-- carried
local function test_the_scout_lap_carries_on_past_an_unclean_chapter()
    local g = fakeGame({ game = "vanilla", chapters = {
        { id = 5, outcomes = { "lost", "spoiled" } },
        { id = 6, outcomes = { "dead", "dead", "lost", "dead" } }, { id = 7 } } })
    g.api.scout = true
    local ok = Campaign.run(g.api)
    local ls = lines(g)
    check(ok, true, "scout: the lap reaches the game's end")
    check(ls[1].outcome .. " " .. ls[1].attempts, "scouted 2",
          "scout: a win with a recruit missed and no death is carried on from")
    check(ls[2].outcome .. " " .. ls[2].attempts, "scouted 4",
          "scout: a win with a death only from the patience on")
    check(ls[2].deaths[1].charId, 0x02, "scout: the line keeps who died")
    check(g.carriedSaved[7] and table.concat(g.carriedSaved[7], ","), "1,3,4",
          "scout: the dead are not carried")
    check(ls[3].outcome, "cleared", "scout: a clean chapter is still cleared")
    for _, l in ipairs(ls) do check(l.scout, true, "scout: every line says scout") end
    -- without the flag the same game stops at the first chapter, as before
    local plain = fakeGame({ game = "vanilla", chapters = {
        { id = 5, outcomes = { "lost", "spoiled", "lost", "lost", "lost", "lost", "lost",
                               "lost", "lost", "lost", "lost", "lost" } }, { id = 6 } } })
    check(Campaign.run(plain.api), false, "no scout: no clean clear stops the campaign")
    check(lines(plain)[1].scout, nil, "no scout: no line says scout")
end
test_the_scout_lap_carries_on_past_an_unclean_chapter()

-- a cap lowered under the patience (`resume --scout --attempts 2`): the last attempt's win is
-- taken, death or not, rather than the lap stopping at the chapter it exists to pass
local function test_the_scout_patience_never_outlasts_a_lowered_cap()
    local g = fakeGame({ game = "vanilla", chapters = { { id = 5, outcomes = { "dead", "dead" } },
                                                        { id = 6 } } })
    g.api.scout, g.api.attempts = true, 2
    check(Campaign.run(g.api), true, "scout, cap 2: the lap goes on")
    check(lines(g)[1].outcome .. " " .. lines(g)[1].attempts, "scouted 2",
          "scout, cap 2: a win with a death on the last attempt is taken")
end
test_the_scout_patience_never_outlasts_a_lowered_cap()

-- test_a_won_attempt_that_spoiled_a_part_is_retried: attempt 1 is won with a recruit missed,
-- attempt 2 is clean; the failure keeps what spoiled it and the attempt's trace.
local function test_a_won_attempt_that_spoiled_a_part_is_retried()
    local g = fakeGame({ chapters = { { id = 3, outcomes = { "spoiled", "won" } } } })
    Campaign.run(g.api)
    local ls = lines(g)
    check(ls[1].outcome, "cleared", "spoiled: cleared on the retry")
    check(ls[1].attempts, 2, "spoiled: at attempt 2")
    local f = ls[1].failures[1]
    check(f and f.clear.recruits_missing[1], 0x30, "spoiled: the failure says what was missed")
    check(f and f.trace, "t1", "spoiled: and names its trace")
end
test_a_won_attempt_that_spoiled_a_part_is_retried()

-- vanilla is beaten clean by strong players, so no clean clear there is the bot's fault
-- (#510 step 9 design, decision 2); Manchego Stars keeps "infeasible"
local function noCleanClear(game)
    local saved = Campaign.MAX_ATTEMPTS
    Campaign.MAX_ATTEMPTS = 2
    local g = fakeGame({ game = game, chapters = { { id = 5, outcomes = { "spoiled", "dead" } },
                                                   { id = 6 } } })
    local ok, why = Campaign.run(g.api)
    Campaign.MAX_ATTEMPTS = saved
    return ok, why, lines(g)
end

local function test_vanilla_without_a_clean_clear_is_a_bot_fault()
    local ok, why, ls = noCleanClear("vanilla")
    check(ok, false, "bot fault: the campaign stops")
    check(ls[1].outcome, "bot_fault", "bot fault: the chapter line")
    check(ls[2].outcome, "bot_fault", "bot fault: the campaign line")
    check(why:find("bot fault", 1, true) ~= nil, true, "bot fault: said in the why")
end
test_vanilla_without_a_clean_clear_is_a_bot_fault()

local function test_ours_without_a_clean_clear_is_infeasible()
    local _, _, ls = noCleanClear("ours")
    check(ls[1].outcome, "infeasible", "ours: infeasible")
end
test_ours_without_a_clean_clear_is_infeasible()

local function test_between_deploys_shops_promotes()
    -- priced per buyer, as the harness does (every roster unit pays the same here)
    local stock = { { item = 0x6C, price = { 300, 300, 300, 300 }, vulnerary = true },
                    { item = 0x10, price = { 500, 500, 500, 500 }, type = "sword" } }
    local needs = { demands = { { id = "sustain", kind = "sustain", need = 1 } },
                    answers = { [0x03] = { sustain = true } }, strength = {} }
    local g = fakeGame({ cap = 2, gold = 10000, stock = stock, random = cycle({ 0.1 }),
                         chapters = { { id = 1, needs = needs } } })
    -- Unit 3 holds a seal the game accepts; the roster re-read after the shop still has it.
    local base = g.api.roster
    g.api.roster = function()
        local r = base()
        r[3].items = { { id = 0x88, promotes = true } }
        return r
    end
    Campaign.run(g.api)
    local d = g.deployed[1]
    check(table.concat(d, ","), "1,3", "forced first, then the unit answering the map's demand")
    check(g.needsAsked, 1, "the needs are read once per chapter start")
    check(g.arms and g.arms[2], 0x10, "the pick is told which item arms the unarmed unit it could field")
    check(g.arms and g.arms[3], nil, "and nothing for a unit no stock item arms")
    local who = {}
    for _, p in ipairs(g.bought) do who[#who + 1] = string.format("%d:%d", p.unit, p.item) end
    check(table.concat(who, ","), "1:108,3:108", "the shop buys for the deployed units only")
    check(table.concat(g.promoted, ","), "3", "a fielded unit holding a seal it accepts is promoted")
    local ls = lines(g)
    check(#ls[1].buys, 2, "the chapter's record lists what the shop bought")
    check(ls[1].buys[1].unit .. ":" .. ls[1].buys[1].item, "1:108", "each buy names its unit and item")
    check(ls[1].team.reasons[2].why, "covers", "the record says why each unit was fielded")
    check(ls[1].demands[1].id, "sustain", "and what the map asked")
    -- the whole pick goes to the attempt's record (fwd1 A): the benched too, and what each
    -- unit answers, which only the worker's log said
    local pick = g.plays[1].pick
    check(pick and pick.cap, 2, "the pick: the cap")
    check(pick and pick.demands[1].id, "sustain", "the pick: what the map asked")
    local by = {}
    for _, u in ipairs(pick and pick.units or {}) do by[u.charId] = u end
    check(by[3] and by[3].why, "covers", "the pick: why a unit was fielded")
    check(by[3] and table.concat(by[3].answers, ","), "sustain", "the pick: what it answers")
    check(by[3] and table.concat(by[3].covers, ","), "sustain", "the pick: what it covered")
    check(by[2] and by[2].why, "benched", "the pick: a unit left out is in it")
    check(by[2] and #by[2].answers, 0, "the pick: and answers nothing")
    check(pick and #pick.uncovered, 0, "the pick: every demand with an answerer has one fielded")
end
test_between_deploys_shops_promotes()

-- The chapter-start record keeps each item's uses left and the convoy (#510 party plan, PR 1):
-- a later start can tell a broken tome from a fresh one, and what the convoy holds.
local function test_the_saved_start_lists_uses_and_the_convoy()
    local snap = { gold = 900,
                   party = { { charId = 2, classId = 5, level = 3,
                               items = { { id = 0x4D, uses = 0 }, { id = 0x6C, uses = 3 } } } },
                   convoy = { { id = 0x82, uses = 1 }, { id = 0x10, uses = 40 } },
                   shops = { "armory" } }
    local g = fakeGame({ game = "vanilla", snapshot = snap, chapters = { { id = 9 } } })
    Campaign.run(g.api)
    local r = g.records[9]
    check(r.game .. r.chapter .. r.gold, "vanilla9900", "the record names the game, chapter and gold")
    check(r.party[1].items[1].id .. "x" .. r.party[1].items[1].uses, "77x0",
          "a unit's item carries its uses left")
    check(#r.convoy, 2, "the convoy's items are listed")
    check(r.convoy[2].id .. "x" .. r.convoy[2].uses, "16x40", "each with its uses")
    check(r.shops[1], "armory", "the open shops stay")
end
test_the_saved_start_lists_uses_and_the_convoy()

-- ADR 0402's rule passes a demand of another kind when an enemy class has fewer answerers: no
-- kept pick has shown it, so the record names the demand the day one does.
local function test_the_pick_names_a_demand_left_without_its_unit()
    local needs = { demands = { { id = "enemy:9", kind = "enemy", need = 1 },
                                { id = "chests", kind = "chests", need = 1 },
                                { id = "doors", kind = "doors", need = 1 } },
                    answers = { [0x02] = { ["enemy:9"] = true }, [0x03] = { chests = true },
                                [0x04] = { chests = true } }, strength = {} }
    local g = fakeGame({ cap = 2, chapters = { { id = 1, needs = needs } } })
    Campaign.run(g.api)
    check(table.concat(g.deployed[1], ","), "1,2", "the class's one answerer takes the last slot")
    check(table.concat(g.plays[1].pick.uncovered, ","), "chests",
          "the chests have two answerers, both benched; doors nobody answers are not listed")
end
test_the_pick_names_a_demand_left_without_its_unit()

local function test_no_prep_screen_picks_nothing()
    local g = fakeGame({ chapters = { { id = 1 } } })
    Campaign.run(g.api)
    check(#g.deployed, 0, "no cap, no prep screen: nothing is picked")
end
test_no_prep_screen_picks_nothing()

local function test_claims_followed_are_passed()
    local claims = { { id = "a", kind = "carry", unit = { 1 }, vs = "all" },
                     { id = "b", kind = "carry", unit = { 2 }, vs = "all" } }
    local g = fakeGame({ claims = claims, random = cycle({ 0.1, 0.9, 0.2, 0.7 }),
                         chapters = { { id = 1 } } })
    Campaign.run(g.api)
    local p = g.plays[1]
    local ids = {}
    for _, c in ipairs(p.claims) do ids[#ids + 1] = c.id end
    check(table.concat(ids, ","), table.concat(p.style.claims, ","),
        "the claims played are exactly the ones the style names")
end
test_claims_followed_are_passed()

local function test_draw_style_never_repeats_and_runs_out()

-- A claim the bot has no behaviour for (Bot.unplayed) plays the same followed or not, so it is
-- no part of a style: vanilla Ch5's four claims (arena, recruit, reinforcements, villages) made
-- 3 x 2^4 = 48 styles that played as 3 games, and the campaign gave up after replaying them.
local function test_unplayed_claims_are_no_part_of_a_style()
    local claims = { { id = "u", kind = "unmodelled", topic = "arena" },
                     { id = "k", kind = "kits", topic = "villages" },
                     { id = "c", kind = "carry", unit = { 1 }, vs = "all" } }
    local tried, n = {}, 0
    math.randomseed(7)
    while n <= 48 and Campaign.drawStyle(Bot, math.random, claims, 1, tried) do n = n + 1 end
    check(n, 6, "three aggressions x the one playable claim followed or not")
    for key in pairs(tried) do
        check(key:match("|(.*)"):find("[uk]") == nil, true, "no unplayed claim in a style: " .. key)
    end
end
test_unplayed_claims_are_no_part_of_a_style()
    local tried, keys = {}, {}
    for _ = 1, 3 do
        local style = Campaign.drawStyle(Bot, cycle({ 0.0, 0.0, 0.5, 0.99 }), {}, 1, tried)
        keys[#keys + 1] = style.aggression
    end
    table.sort(keys)
    check(table.concat(keys, ","), "bold,careful,even", "three draws, three different styles")
    check(Campaign.drawStyle(Bot, cycle({ 0.0 }), {}, 1, tried), nil, "every style tried: nil")
end
test_draw_style_never_repeats_and_runs_out()

local function test_cleared_team_is_carried()
    -- Units 2 and 4 both answer chapter 2's demand; 4 is carried from chapter 1, so it wins
    -- over the earlier joiner.
    local ch1 = { demands = { { id = "d1", kind = "fog", need = 1 } }, answers = { [0x04] = { d1 = true } },
                  strength = {} }
    local ch2 = { demands = { { id = "d2", kind = "fog", need = 1 } },
                  answers = { [0x02] = { d2 = true }, [0x04] = { d2 = true } }, strength = {} }
    local g = fakeGame({ cap = 2, chapters = { { id = 1, needs = ch1 }, { id = 2, needs = ch2 } } })
    Campaign.run(g.api)
    check(table.concat(g.deployed[1], ","), "1,4", "chapter 1 fields its answerer")
    check(table.concat(g.deployed[2], ","), "1,4", "chapter 2 keeps it: carried wins the tie")
end
test_cleared_team_is_carried()

local function test_ungrouped_class_stops_the_campaign()
    local g = fakeGame({ cap = 2, chapters = { { id = 1 } } })
    local base = g.api.roster
    g.api.roster = function()
        local r = base()
        r[2].classId = 0x7E
        return r
    end
    local ok, why = Campaign.run(g.api)
    check(ok, false, "a class with no team group stops the campaign")
    check(why:find("no team group") ~= nil, true, "and says so")
end
test_ungrouped_class_stops_the_campaign()

-- A prep screen whose Pick Units never opens is a crash, never a chapter without prep: the
-- bot must not field the whole roster and shop on the prep screen.
local function test_cap_failure_is_a_crash()
    local g = fakeGame({ cap = 2, chapters = { { id = 1 } } })
    g.api.cap = function() return nil, "Pick Units did not open" end
    local ok, why = Campaign.run(g.api)
    check(ok, false, "a cap failure stops the campaign")
    check(why:find("Pick Units did not open") ~= nil, true, "and says why")
    check(#g.plays, 0, "nothing is played on a prep screen it could not read")
end
test_cap_failure_is_a_crash()

-- A run resumed at chapter 2 (the pool, or --from) plays it as the whole campaign did: the
-- draws restart from (seed, chapter), and the start's record hands back the carried team.
local function test_resume_plays_as_the_campaign()
    local function seeded()
        local at = 0
        local values = { 0.1, 0.6, 0.3, 0.9, 0.5, 0.7 }
        return function() at = at + 1; return values[(at - 1) % #values + 1] end,
               function(ch) at = ch end
    end
    local ch1 = { demands = { { id = "d1", kind = "fog", need = 1 } }, answers = { [0x04] = { d1 = true } },
                  strength = {} }
    local ch2 = { demands = { { id = "d2", kind = "fog", need = 1 } },
                  answers = { [0x02] = { d2 = true }, [0x04] = { d2 = true } }, strength = {} }
    local r1, s1 = seeded()
    local full = fakeGame({ cap = 2, random = r1, seed = s1, chapters = {
        { id = 1, needs = ch1, outcomes = { "lost", "won" } }, { id = 2, needs = ch2 } } })
    Campaign.run(full.api)
    check(table.concat(full.seeds, ","), "1,2", "the draws restart at each chapter start")
    check(table.concat(full.carriedSaved[2], ","), "1,4", "chapter 2's start saves the team carried in")
    local r2, s2 = seeded()
    local resumed = fakeGame({ cap = 2, random = r2, seed = s2, chapters = {
        { id = 2, needs = ch2, carried = full.carriedSaved[2] } } })
    Campaign.run(resumed.api)
    check(Json.encode(resumed.plays[1].style), Json.encode(full.plays[3].style),
          "the resumed chapter 2 draws the campaign's style")
    check(table.concat(resumed.deployed[1], ","), table.concat(full.deployed[3], ","),
          "and picks the campaign's team: the carried unit wins the tie")
end
test_resume_plays_as_the_campaign()

-- A start saved before records kept the carried team resumes with none, and its chapter line
-- says so: that pick may not be the campaign's.
local function test_resume_without_a_carried_team_says_so()
    local g = fakeGame({ cap = 2, chapters = { { id = 3, carried = {}, carriedUnknown = true } } })
    Campaign.run(g.api)
    check(lines(g)[1].carried_unknown, true, "the chapter line marks the team unknown")
    check(#g.plays, 1, "and the chapter is played")
    check(g.saved[1], 3, "the start is saved again")
    check(g.carriedSaved[3], nil, "with its team still unknown, so the next resume says so too")
end
test_resume_without_a_carried_team_says_so()

-- A retry remembers the arrivals it saw (ADR 0386, T061): attempt k >= 2 is given, in
-- style.arrivals, the turns of every earlier failed attempt's arrivals_seen at this start;
-- attempt 1 none; one attempt alone (api.only) none either: the pool's workers share no results.
local function test_a_retry_remembers_the_arrivals_it_saw()
    local seen = { [1] = { { turn = 4, x = 9, y = 9, charId = 0x82 } },
                   [2] = { { turn = 4, x = 8, y = 9, charId = 0x83 },
                           { turn = 6, x = 9, y = 0, charId = 0x84 } } }
    local g = fakeGame { chapters = { { id = 1, outcomes = { "lost", "dead", "won" }, seen = seen } } }
    Campaign.run(g.api)
    check(#g.plays, 3, "three attempts")
    check(g.plays[1].style.arrivals, nil, "attempt 1 remembers nothing")
    check(table.concat(g.plays[2].style.arrivals[1], ","), "4", "attempt 2: attempt 1's arrival turn")
    check(#g.plays[2].style.arrivals, 1, "as one list, beside any claim's")
    check(table.concat(g.plays[3].style.arrivals[1], ","), "4,6",
          "attempt 3: the union over both failures, each turn once, in order")
    local keys = {}
    for k in pairs(g.plays[3].style) do keys[#keys + 1] = k end
    table.sort(keys)
    check(table.concat(keys, ","), "aggression,arrivals,claims",
          "the arrival turns; no enemy was shown, so no memory (ADR 0399)")
    local alone = fakeGame { chapters = { { id = 1, seen = seen } } }
    alone.api.only = 1
    Campaign.run(alone.api)
    check(alone.plays[1].style.arrivals, nil, "a measured cell (api.only = 1) is untouched")
    local third = fakeGame { chapters = { { id = 1, seen = seen } } }
    third.api.only = 3
    Campaign.run(third.api)
    check(third.plays[1].style.arrivals, nil, "a pool attempt k has no earlier result to remember")
end
test_a_retry_remembers_the_arrivals_it_saw()

-- A retry remembers what earlier attempts showed on screen (ADR 0399): every enemy a board
-- showed out of fog (enemies_seen) and every killer a death showed, each once by slot and
-- character; attempt 1 and an attempt alone (api.only) remember nothing.
local function test_a_retry_remembers_the_enemies_it_saw()
    local enemies = { [1] = { { id = 0x81, charId = 0x50, classId = 1 }, { id = 0x82, charId = 0x51, classId = 1 } },
                      [2] = { { id = 0x81, charId = 0x50, classId = 1 }, { id = 0x81, charId = 0x52, classId = 1 } } }
    local g = fakeGame { chapters = { { id = 1, outcomes = { "lost", "dead", "won" },
                                        enemies = enemies } } }
    Campaign.run(g.api)
    check(g.plays[1].style.memory, nil, "attempt 1 remembers nothing")
    local m2 = g.plays[2].style.memory
    local ids = {}
    for _, e in ipairs(m2.enemies) do ids[#ids + 1] = string.format("%x:%x:%x", e.id, e.charId, e.classId) end
    check(table.concat(ids, ","), "81:50:1,82:51:1",
          "attempt 2: attempt 1's enemies seen (a killer is among them: botrun's enemies_seen)")
    check(m2.deaths, nil, "a death is remembered through its killer alone")
    local m3 = g.plays[3].style.memory
    ids = {}
    for _, e in ipairs(m3.enemies) do ids[#ids + 1] = string.format("%x:%x", e.id, e.charId) end
    check(table.concat(ids, ","), "81:50,82:51,81:52",
          "attempt 3: the union, each enemy once; a slot another unit took is another enemy")
    m2.enemies[1] = nil
    check(#g.plays[3].style.memory.enemies, 3, "each attempt gets its own copy")
    -- a unit whose class was not read is not kept: its key would match nothing
    local noClass = fakeGame { chapters = { { id = 1, outcomes = { "lost", "won" },
                                              enemies = { [1] = { { id = 0x81, charId = 0x50 } } } } } }
    Campaign.run(noClass.api)
    check(noClass.plays[2].style.memory, nil, "a unit with no class read is not remembered")
    local alone = fakeGame { chapters = { { id = 1, enemies = enemies } } }
    alone.api.only = 2
    Campaign.run(alone.api)
    check(alone.plays[1].style.memory, nil, "a pool attempt has no earlier result to remember")
end
test_a_retry_remembers_the_enemies_it_saw()

-- The retry cap (ADR 0399): every style tried, the styles are drawn again, up to MAX_ATTEMPTS
-- attempts a chapter start, while what is remembered keeps growing; then the chapter stops.
local function test_styles_are_drawn_again_up_to_the_cap()
    check(Campaign.MAX_ATTEMPTS, 12, "the cap is 12 a chapter start (Nicolas, 2026-11-10)")
    local outcomes, enemies = {}, {}
    for i = 1, 12 do
        outcomes[i] = "lost"
        enemies[i] = { { id = 0x80 + i, charId = 0x50, classId = 1 } }   -- something new each try
    end
    local g = fakeGame({ game = "vanilla", chapters = { { id = 5, outcomes = outcomes, enemies = enemies } } })
    local ok, why = Campaign.run(g.api)
    check(ok, false, "no clean clear in the cap stops the campaign")
    check(#g.plays, 12, "all 12 attempts are played, past the 3 styles (no claims)")
    check(why:find("12 attempts") ~= nil, true, "and it says the cap stopped it")
    local seen = {}
    for i = 1, 3 do seen[g.plays[i].style.aggression] = true end
    local n = 0
    for _ in pairs(seen) do n = n + 1 end
    check(n, 3, "every style is tried before one is drawn again")
    check(lines(g)[1].outcome, "bot_fault", "a vanilla chapter so stopped is a bot fault")
end
test_styles_are_drawn_again_up_to_the_cap()

-- Retries get different dice (ADR 0404): the loop advances the game's RNG (k - 1) * DICE_STRIDE
-- draws before attempt k's play, and hands the count to play for the record. Attempt 1 advances
-- none: every measured cell plays as it always did.
local function test_attempt_k_advances_the_dice_by_k_minus_1_strides()
    check(Campaign.DICE_STRIDE > 150, true, "the stride is more than a turn draws (one draw is absorbed)")
    local g = fakeGame({ chapters = { { id = 3, outcomes = { "lost", "lost", "lost", "won" } } } })
    Campaign.run(g.api)
    local st = Campaign.DICE_STRIDE
    check(table.concat(g.dice, ","), table.concat({ 0, st, 2 * st, 3 * st }, ","), "the advance is 0 for attempt 1 and (k - 1) strides after")
    for k, p in ipairs(g.plays) do
        check(p.dice, (k - 1) * Campaign.DICE_STRIDE, "attempt " .. k .. "'s play is told its dice")
    end
    local saved = Campaign.DICE_STRIDE
    Campaign.DICE_STRIDE = 5
    local h = fakeGame({ chapters = { { id = 3, outcomes = { "lost", "won" } } } })
    Campaign.run(h.api)
    Campaign.DICE_STRIDE = saved
    check(table.concat(h.dice, ","), "0,5", "the stride scales the advance")
end
test_attempt_k_advances_the_dice_by_k_minus_1_strides()

-- one attempt alone burns what the campaign's k-th try would; a diagnostic replay of it too
local function test_one_attempt_alone_advances_as_attempt_k()
    local alone = fakeGame({ chapters = { { id = 3 } } })
    alone.api.only = 3
    Campaign.run(alone.api)
    check(table.concat(alone.dice, ","), tostring(2 * Campaign.DICE_STRIDE), "attempt 3 alone advances two strides")
    check(alone.plays[1].dice, 2 * Campaign.DICE_STRIDE, "and its play is told")
    local first = fakeGame({ chapters = { { id = 3 } } })
    first.api.only = 1
    Campaign.run(first.api)
    check(table.concat(first.dice, ","), "0", "attempt 1 alone advances none")
    -- a replay burns what its original's record says (the diag line's dice_advanced), whatever
    -- its attempt number: the record's count, and 0 for a record from before ADR 0404 (the diag
    -- line of a pinned check is `{}`: harness.lua)
    local replay = fakeGame({ chapters = { { id = 3 } } })
    replay.api.only, replay.api.diag = 2, { ref = 1, mode = "deep", dice_advanced = 7 }
    Campaign.run(replay.api)
    check(table.concat(replay.dice, ","), "7", "a diagnostic replay of attempt 2 burns its record's dice")
    check(replay.plays[1].dice, 7, "and its play is told")
    local old = fakeGame({ chapters = { { id = 3 } } })
    old.api.only, old.api.diag = 3, { ref = 1, mode = "deep" }
    Campaign.run(old.api)
    check(table.concat(old.dice, ","), "0", "an old attempt-3 record (no dice_advanced) replays none")
    local pinned = fakeGame({ chapters = { { id = 3 } } })
    pinned.api.only, pinned.api.diag = 3, {}
    Campaign.run(pinned.api)
    check(table.concat(pinned.dice, ","), "0", "a pinned check (diag = {}) burns none")
end
test_one_attempt_alone_advances_as_attempt_k()

-- With different dice a style played again is a new try, so the chapter no longer stops when
-- every style has been played: it goes on to the cap (here 3 styles, one memory, 12 attempts).
local function test_a_chapter_runs_to_the_cap_past_every_style()
    local outcomes = {}
    for i = 1, 12 do outcomes[i] = "lost" end
    local g = fakeGame({ game = "vanilla", chapters = { { id = 5, outcomes = outcomes,
        enemies = { [1] = { { id = 0x90, charId = 0x40, classId = 0x0C } } } } } })
    local ok, why = Campaign.run(g.api)
    check(ok, false, "the chapter stops")
    check(#g.plays, 12, "all 12 attempts are played, memory or no new memory")
    check(why:find("12 attempts") ~= nil, true, "and the cap says so")
    check(lines(g)[1].outcome, "bot_fault", "a bot fault on vanilla")
end
test_a_chapter_runs_to_the_cap_past_every_style()

-- api.attempts bounds the retries in place of MAX_ATTEMPTS (montecarlo.py `resume --attempts`)
local function test_api_attempts_bounds_the_retries()
    local outcomes = {}
    for i = 1, 12 do outcomes[i] = "lost" end
    local g = fakeGame({ game = "vanilla", chapters = { { id = 5, outcomes = outcomes } } })
    g.api.attempts = 3
    local ok, why = Campaign.run(g.api)
    check(ok, false, "no clean clear in the bound stops the campaign")
    check(#g.plays, 3, "exactly 3 attempts are played")
    check(why, "chapter 5: no clean clear in 3 attempts, the cap lowered from 12",
          "it says 3 attempts and the lowered cap")
    -- a lowered cap is its own outcome, never the chapter's or the bot's verdict
    check(lines(g)[1].outcome, "capped", "the chapter line says capped, not bot_fault")
    check(lines(g)[2].outcome, "capped", "and so does the campaign line")
    local ours = fakeGame({ game = "ours", chapters = { { id = 5, outcomes = outcomes } } })
    ours.api.attempts = 2
    Campaign.run(ours.api)
    check(lines(ours)[1].outcome, "capped", "Manchego Stars: capped, not infeasible")
    local full = fakeGame({ game = "vanilla", chapters = { { id = 5, outcomes = outcomes } } })
    full.api.attempts = Campaign.MAX_ATTEMPTS
    Campaign.run(full.api)
    check(lines(full)[1].outcome, "bot_fault", "a bound equal to the cap is the cap: bot_fault")
    for _, bad in ipairs({ 0, -1, Campaign.MAX_ATTEMPTS + 1, 2.5 }) do
        local b = fakeGame({ chapters = { { id = 5 } } })
        b.api.attempts = bad
        local bok, err = pcall(Campaign.run, b.api)
        check(bok, false, "attempts " .. bad .. " is refused")
        check(tostring(err):find("attempts is " .. tostring(bad) .. ", and a chapter start gets 1 to 12", 1, true) ~= nil,
              true, "and the error names the value and the cap: " .. tostring(err))
    end
    local one = fakeGame({ game = "vanilla", chapters = { { id = 5, outcomes = outcomes } } })
    one.api.attempts = 1
    Campaign.run(one.api)
    check(#one.plays, 1, "a bound of 1 plays one attempt")
    local clear = fakeGame({ chapters = { { id = 5, outcomes = { "lost", "won" } }, { id = 6 } } })
    clear.api.attempts = 3
    check(Campaign.run(clear.api), true, "a clean clear inside the bound goes on")
end
test_api_attempts_bounds_the_retries()

print(string.format("%s -- %d assertions", fails == 0 and "ok" or (fails .. " FAILED"), tests))
os.exit(fails == 0 and 0 or 1)
