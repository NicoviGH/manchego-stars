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

-- A fake game. o.chapters = { { id, outcomes = { "won"|"lost"|"dead"|"stuck"|"crashed"... },
-- options = n (a route split before it), needs = Bot.team's demands/answers/strength } };
-- "dead" is a win with a death. o.route = the campaign's route setting.
local function fakeGame(o)
    local g = { at = 0, saved = {}, loads = 0, deployed = {}, bought = {}, promoted = {},
                plays = {}, emitted = {}, seeds = {}, routeAsked = nil, attempt = 0 }
    g.api = {
        Bot = Bot, Json = Json,
        info = { game = "fake", rom_hash = "abc", mode = "normal", seed = 7, campaign = "c1",
                 route = o.route },
        random = o.random or cycle({ 0.1, 0.6, 0.3, 0.9, 0.5 }),
        arrive = function(route)
            g.at = g.at + 1
            local ch = o.chapters[g.at]
            if not ch then return "end" end
            if ch.options then g.routeAsked = route({ "a", "b" }) end
            if ch.arriveFails then return nil, "the world map never handed over" end
            g.attempt = 0
            return { chapter = ch.id }
        end,
        save = function(ch) g.saved[#g.saved + 1] = ch; return true end,
        load = function() g.loads = g.loads + 1; return true end,
        roster = roster,
        cap = function() return o.cap end,
        teamGroups = function()
            return { ["2"] = "lord", ["5"] = "mounted", ["38"] = "healer" }, { mounted = 3 }
        end,
        needs = function()
            g.needsAsked = (g.needsAsked or 0) + 1
            return o.chapters[g.at].needs or { demands = {}, answers = {}, strength = {} }
        end,
        deploy = function(ids) g.deployed[#g.deployed + 1] = ids; return true end,
        gold = function() return o.gold or 0 end,
        stock = function() return o.stock or {} end,
        buy = function(p) g.bought[#g.bought + 1] = p; return true end,
        promote = function(u) g.promoted[#g.promoted + 1] = u.charId; return true end,
        claims = function() return o.claims or {} end,
        play = function(style, claims, attempt)
            local ch = o.chapters[g.at]
            g.attempt = g.attempt + 1
            local out = (ch.outcomes or {})[g.attempt] or "won"
            g.plays[#g.plays + 1] = { chapter = ch.id, style = style, claims = claims,
                                      attempt = attempt }
            local deaths = {}
            if out == "dead" or out == "lost" then
                deaths = { { charId = 0x02, turn = 3, killer = 0x40, phase = "enemy" } }
            end
            return { outcome = out == "dead" and "won" or out, all_alive = out == "won",
                     turns = 4, deaths = deaths }
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

local function test_between_deploys_shops_promotes()
    local stock = { { item = 0x6C, price = 300, kind = "vulnerary" },
                    { item = 0x10, price = 500, type = "sword" } }
    local needs = { demands = { { id = "sustain", need = 1 } },
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
    local who = {}
    for _, p in ipairs(g.bought) do who[#who + 1] = string.format("%d:%d", p.unit, p.item) end
    check(table.concat(who, ","), "1:108,3:108", "the shop buys for the deployed units only")
    check(table.concat(g.promoted, ","), "3", "a fielded unit holding a seal it accepts is promoted")
    local ls = lines(g)
    check(ls[1].team.reasons[2].why, "covers", "the record says why each unit was fielded")
    check(ls[1].demands[1].id, "sustain", "and what the map asked")
end
test_between_deploys_shops_promotes()

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
    local ch1 = { demands = { { id = "d1", need = 1 } }, answers = { [0x04] = { d1 = true } },
                  strength = {} }
    local ch2 = { demands = { { id = "d2", need = 1 } },
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

print(string.format("%s -- %d assertions", fails == 0 and "ok" or (fails .. " FAILED"), tests))
os.exit(fails == 0 and 0 or 1)
