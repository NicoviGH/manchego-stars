-- Tests for botrun.lua -- the bot playing one chapter (#510 step 9 PR D), over a fake game:
-- a board table the fake api moves and strikes on, so no emulator.
-- Run: lua tools/playtest/test_botrun.lua
local here = (arg[0]:match("(.*/)")) or "./"
local Botrun = dofile(here .. "botrun.lua")
local Json = dofile(here .. "json.lua")
local Bot = dofile(here .. "bot.lua")
local Board = dofile(here .. "board.lua")
local Sight = dofile(here .. "sight.lua")

local tests, fails = 0, 0
local function check(got, want, msg)
    tests = tests + 1
    if got ~= want then
        fails = fails + 1
        print(string.format("FAIL: %s\n  got  %s\n  want %s", msg, tostring(got), tostring(want)))
    end
end

local function unit(id, slot, faction, x, y, hp)
    return { id = id, slot = slot, faction = faction, charId = id, x = x, y = y, hp = hp,
             maxhp = hp, onMap = true, onField = true, dead = false, acted = false,
             minRange = 1, maxRange = 1, isBoss = false }
end

-- A fake game. `units` is mutated in place; act moves the actor and, on an attack, takes
-- `hit` off the target. endPhase runs `enemy(game)` (the enemy phase's effect), clears
-- acted and advances the turn. Won when no red is left; lost when `game.over` is set.
local function fakeGame(o)
    local g = { turn = 1, units = o.units, emitted = {}, frame = 0, seeded = nil,
                turnsLeft = o.turnsLeft }
    local function find(id)
        for _, u in ipairs(g.units) do if u.id == id then return u end end
    end
    local function reds()
        local n = 0
        for _, u in ipairs(g.units) do if u.faction == "red" and not u.dead then n = n + 1 end end
        return n
    end
    local function copy()
        local units = {}
        for i, u in ipairs(g.units) do
            local c = {}
            for k, v in pairs(u) do c[k] = v end
            units[i] = c
        end
        return { turn = g.turn, phase = "blue", map = { w = 10, h = 10 }, units = units }
    end
    local function within(u, r)
        local out = {}
        for y = 0, 9 do
            for x = 0, 9 do
                if Board.distance(x, y, u.x, u.y) <= r then out[#out + 1] = { x = x, y = y } end
            end
        end
        return out
    end
    g.api = {
        Bot = Bot, Json = Json,
        info = { game = "fake", rom_hash = "abc", chapter = 1, mode = "normal", seed = 7 },
        style = { aggression = o.aggression or "careful", deploy = {}, claims = {} },
        claims = o.claims,
        recruits = o.recruits and function() return o.recruits end,
        -- the game's party (IsUnitInCurrentRoster, through MakePrepUnitList): o.party(g) when
        -- a case decides it, else every blue unit not dead
        party = function()
            if o.party then return o.party(g) end
            local out = {}
            for _, u in ipairs(g.units) do
                if u.faction == "blue" and not u.dead then out[#out + 1] = u.charId end
            end
            return out
        end,
        seed = function(s) g.seeded = s end,
        board = copy,
        sight = function()
            g.sights = (g.sights or 0) + 1
            local s = {
                cache = {},
                objective = { kind = o.kind or "rout" },
                danger = function() return 0 end,
                threat = function() return function() return 0 end end,
                weapons = function(u) return { { slot = 0, min = u.minRange, max = u.maxRange } } end,
                canSeize = function() return true end,
                reach = function(u)
                    return within(u, u.faction == "blue" and (o.move or 3) or 0)
                end,
                -- one sure blow of o.hit and no counter, as the game would play it
                attack = function(u, e)
                    local dmg = o.hit or 5
                    return Sight.attackOf({ hit = 100, dmg = dmg, crit = 0, hits = 1,
                                            counter = { armed = false, hits = 0 },
                                            killsTarget = dmg >= e.hp,
                                            dealt = { [math.min(dmg, e.hp)] = 1 },
                                            back = { [0] = 1 } }, e.hp, u.hp)
                end,
                strike = function() return Sight.strikeOf(nil) end,
                odds = Sight.odds,
                nextTurnEvent = function(turn)
                    g.eventAsks = (g.eventAsks or 0) + 1
                    return o.eventTurn and o.eventTurn > turn and o.eventTurn or nil
                end,
            }
            if o.explorable then
                s.explorable = function() return o.explorable end
                s.canExplore = function() return true end
            end
            s.refresh = function()
                g.refreshes = (g.refreshes or 0) + 1
                s.objective.turnsLeft = g.turnsLeft
            end
            s.newPhase = function()
                g.phases = (g.phases or 0) + 1
                s.refresh()
                s.cache = {}
            end
            return s
        end,
        act = function(a)
            local u = find(a.unitId)
            u.x, u.y, u.acted = a.move.x, a.move.y, true
            if a.act == "attack" then
                local e = find(a.targetId)
                e.hp = e.hp - (o.hit or 5)
                if e.hp <= 0 then e.hp, e.dead, e.onField = 0, true, false end
            end
            return true
        end,
        endPhase = function()
            local deaths, acts = {}, nil
            if o.enemy then deaths, acts = o.enemy(g, find) end
            deaths = deaths or {}
            for _, u in ipairs(g.units) do u.acted = false end
            g.turn = g.turn + 1
            if g.turnsLeft then g.turnsLeft = g.turnsLeft - 1 end
            if g.over then return "gameover", deaths, acts end
            return "player", deaths, acts
        end,
        won = function()
            if g.turnsLeft then return g.turnsLeft <= 0 end
            return reds() == 0
        end,
        lost = function() return g.over == true end,
        -- the game's kills: every unit the fake has marked dead since the last call (UnitKill
        -- marks the unit; a unit only taken off the field was unloaded, not killed)
        killed = function()
            local out = {}
            g.reported = g.reported or {}
            for _, u in ipairs(g.units) do
                if u.dead and not g.reported[u.id] then
                    g.reported[u.id] = true
                    out[#out + 1] = { id = u.id, charId = u.charId, faction = u.faction }
                end
            end
            return out
        end,
        frames = function() g.frame = g.frame + 100; return g.frame end,
        emit = function(line) g.emitted[#g.emitted + 1] = line end,
        log = function(l)
            g.logs = g.logs or {}
            g.logs[#g.logs + 1] = l
        end,
    }
    return g
end

-- The two-unit rout most cases play: A beside an enemy it kills in two blows.
local function rout()
    return { unit(0x01, 0, "blue", 0, 0, 20), unit(0x81, 0, "red", 1, 0, 10) }
end

-- A and an enemy out of each other's reach for good: nothing either does changes the board.
local function standoff()
    return { unit(0x01, 0, "blue", 0, 0, 20), unit(0x81, 0, "red", 9, 9, 10) }
end

local function recordOf(g)
    local line = g.emitted[#g.emitted]
    check(line and line:sub(1, #Botrun.PREFIX), Botrun.PREFIX, "one BOTRUN line is emitted")
    return Json.decode(line:sub(#Botrun.PREFIX + 1))
end

-- test_explore_log: what became of each village and chest the run saw open -- the player's, someone
-- else's (a pillage), offered and never played (with the lowest chance it was offered at),
-- never offered.
do
    local log = Botrun.exploreLog()
    log.open({ { x = 1, y = 1, kind = "visit" }, { x = 2, y = 2, kind = "visit" },
               { x = 3, y = 3, kind = "chest" }, { x = 4, y = 4, kind = "chest" } }, 1)
    log.offered({ { x = 1, y = 1, die = 0 }, { x = 3, y = 3, die = 0.4 } })
    log.offered({ { x = 3, y = 3, die = 0.1 } })
    log.visited({ unit = 0x01, move = { x = 1, y = 1 } }, 1)
    log.open({ { x = 3, y = 3, kind = "chest" }, { x = 4, y = 4, kind = "chest" } }, 2)
    local by = {}
    for _, e in ipairs(log.summary()) do by[e.x] = e end
    check(by[1].status, "visited", "explore log: ours")
    check(by[1].by, 0x01, "explore log: by whom")
    check(by[2].status, "closed", "explore log: gone, not by us")
    check(by[2].turn, 2, "explore log: when it was seen gone")
    check(by[3].status, "skipped", "explore log: offered, never played")
    check(by[3].offers, 2, "explore log: how often")
    check(by[3].die, 0.1, "explore log: the lowest chance it was offered at")
    check(by[4].status, "unreached", "explore log: never offered")
    local done = log.explored()
    check(done["1,1"], true, "explore log: ours is explored")
    check(done["3,3"], nil, "explore log: an offer alone is not")
    log.failed({ unit = 0x1C, move = { x = 4, y = 4 } }, 3)
    by = {}
    for _, e in ipairs(log.summary()) do by[e.x] = e end
    check(by[4].status, "failed", "explore log: tried, and the harness could not drive it")
    check(by[4].tried, 0x1C, "explore log: by whom")
end

-- test_explore_left_open: a tile still open at the last player phase that a unit could use
-- (the game's own check, read then) and that was never explored is a bot fault; one nobody
-- could use any more (a chest with no opener left, a village destroyed) is not.
do
    local log = Botrun.exploreLog()
    local tiles = { { x = 3, y = 3, kind = "chest" }, { x = 4, y = 4, kind = "chest" },
                    { x = 5, y = 5, kind = "visit" } }
    log.open(tiles, 1, function(t) return true end)
    log.offered({ { x = 3, y = 3, die = 0.4 } })
    log.visited({ unit = 0x01, move = { x = 5, y = 5 } }, 1)
    log.open(tiles, 2, function(t) return t.x == 3 end)
    local left = log.leftOpen()
    check(#left, 1, "left open: only the tile a unit could still use")
    check(left[1] and (left[1].x .. "," .. left[1].y), "3,3", "left open: which")
    check(left[1] and left[1].kind, "left_open", "left open: the fault's kind")
    check(left[1] and left[1].tile, "chest", "left open: the tile's kind")
    check(left[1] and left[1].offers, 1, "left open: how often it was offered")
end

-- test_a_won_run_records_left_open_tiles: the rout is won in two blows while a village the
-- unit could visit stands far off; the record's bot_faults names it.
do
    local g = fakeGame { units = rout(), explorable = { { x = 9, y = 9, kind = "visit" } } }
    Botrun.run(g.api)
    local r = recordOf(g)
    check(r.outcome, "won", "left open: the run is won")
    local f = r.bot_faults and r.bot_faults[1]
    check(f and f.kind, "left_open", "left open: a bot fault")
    check(f and (f.x .. "," .. f.y), "9,9", "left open: the village")
end

-- test_full_bag_answers_are_recorded: the harness's full-bag answers land in the record with
-- the turn they came on.
do
    local g = fakeGame { units = rout() }
    local given = { { charId = 1, item = 0x6C, sent = 0x6C, discard = false, why = "w" } }
    g.api.bag = function() local b = given; given = {}; return b end
    Botrun.run(g.api)
    local r = recordOf(g)
    check(#r.bag, 1, "bag: one answer recorded")
    check(r.bag[1].sent, 0x6C, "bag: what went")
    check(r.bag[1].turn, 1, "bag: on its turn")
end

-- test_two_turn_rout_ends_won: A strikes E for 5 a turn; E has 10 HP.
do
    local g = fakeGame { units = rout() }
    local ok, why = Botrun.run(g.api)
    check(ok, true, "a won run is a finished run")
    local r = recordOf(g)
    check(r.outcome, "won", "the rout is won")
    check(r.turns, 2, "on turn 2")
    check(r.clean, nil, "with no owed list the clear is not judged")
    check(r.kills["1"], 1, "A's kill is counted")
    check(r.deployed[1], 1, "A was deployed")
    check(r.seed, 7, "the seed is recorded")
    check(g.seeded, 7, "and handed to the game")
    check(r.frames > 0, true, "frames are reported")
end

-- test_leader_death_ends_lost: the enemy phase kills A and the game-over screen comes up.
do
    local g = fakeGame {
        hit = 1,
        units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x81, 0, "red", 5, 5, 30) },
        enemy = function(g, find)
            local a = find(0x01)
            a.hp, a.dead, a.onField = 0, true, false
            g.over = true
            return { { id = 0x01, charId = 0x01, faction = "blue", killer = 0x81 } }
        end,
    }
    Botrun.run(g.api)
    local r = recordOf(g)
    check(r.outcome, "lost", "game over is a loss")
    check(#r.deaths, 1, "the death is recorded")
    check(r.deaths[1].charId, 1, "it is A's")
    check(r.deaths[1].killer, 0x81, "with its killer")
    check(r.deaths[1].phase, "enemy", "in the enemy phase")
    check(r.deaths[1].turn, 1, "on turn 1")
    check(r.clean, false, "nobody calls that clean")
end

-- test_repeated_board_is_stuck: the enemy is out of every reach and the bot cannot move
-- (reach 0), so turn 2 begins on turn 1's board.
do
    local g = fakeGame { move = 0,
        units = standoff() }
    local ok = Botrun.run(g.api)
    check(ok, true, "stuck is a finished run, not a crash")
    local r = recordOf(g)
    check(r.outcome, "stuck", "a repeated board ends the run")
    check(r.turns, 2, "at the first repeat")
    local said = {}
    for _, l in ipairs(g.logs) do
        if l:find("^stuck: ") then said[#said + 1] = l end
    end
    check(#said > 0 and said[1]:find("objective rout", 1, true) ~= nil, true,
          "a stuck run logs why the bot held, objective first")
    local blue = false
    for _, l in ipairs(said) do
        if l:find("blue char", 1, true) and l:find("wait 1 allowed 1", 1, true) then blue = true end
    end
    check(blue, true, "each blue unit's wait tiles and what the gate allows")
end

-- test_survive_map_waiting_is_not_stuck: the same board, but the turns left fall each phase.
do
    local g = fakeGame { move = 0, kind = "survive", turnsLeft = 3,
        units = standoff() }
    Botrun.run(g.api)
    local r = recordOf(g)
    check(r.outcome, "won", "holding until the turns run out wins")
    check(r.turns, 3, "after three phases")
end

-- An action the harness cannot perform is a crash, never a hang.
do
    local g = fakeGame { units = rout() }
    g.api.act = function() return false end
    local ok = Botrun.run(g.api)
    check(ok, false, "a controller fault is not a finished run")
    check(recordOf(g).outcome, "crashed", "it is recorded as crashed")
end

-- A move the game halted on a unit the fog hid (FE8's ambush: api.act says "trapped") is no
-- crash: the unit's turn is over one step short, the trace says where it stopped, and the run
-- plays on.
do
    local g = fakeGame { units = rout() }
    local act, trapped = g.api.act, 0
    g.api.act = function(a)
        if trapped == 0 then
            trapped = trapped + 1
            for _, u in ipairs(g.units) do
                if u.id == a.unitId then u.acted = true end
            end
            return "trapped"
        end
        return act(a)
    end
    local events = {}
    g.api.trace = function(ev) events[#events + 1] = ev end
    Botrun.run(g.api)
    check(trapped, 1, "trapped: one move was halted")
    check(recordOf(g).outcome ~= "crashed", true, "trapped: the run is no crash")
    local said
    for _, e in ipairs(events) do
        if e.t == "act" and e.trapped then said = e end
    end
    check(said ~= nil, true, "trapped: the trace marks the act")
    check(said and said.to and said.from and said.to.x == said.from.x and said.to.y == said.from.y,
          true, "trapped: and says it ended where the unit stopped, not where it was sent")
end

-- An action that leaves its unit able to act would be asked for again forever.
do
    local g = fakeGame { units = rout() }
    g.api.act = function() return true end
    Botrun.run(g.api)
    check(recordOf(g).outcome, "crashed", "a no-op action ends the run")
end

-- An enemy phase that never hands control back is a crash.
do
    local g = fakeGame { move = 0,
        units = standoff() }
    g.api.endPhase = function() return nil, {} end
    Botrun.run(g.api)
    check(recordOf(g).outcome, "crashed", "a wedged enemy phase is recorded as crashed")
end

-- test_the_record_says_whether_its_environment_held (#510 step 9 plan, T008): `env_status` is
-- "clean", or the fault that makes the record unreadable and whether it came after play began
-- (outcome_dependent: dropping such a run could bias what the rest say); `instrument` is the
-- bot and suite version the harness ran it under.
do
    local g = fakeGame { units = rout() }
    g.api.info.instrument = "0123456789ab+v1"
    Botrun.run(g.api)
    local r = recordOf(g)
    check(r.env_status, "clean", "a won run on a sound harness: clean")
    check(r.instrument, "0123456789ab+v1", "the record names its instrument")
end
do
    local g = fakeGame { units = rout() }
    g.api.act = function() return false end
    Botrun.run(g.api)
    local e = recordOf(g).env_status
    check(type(e) == "table" and e.fault, "crash", "a controller fault: a crash")
    check(type(e) == "table" and e.outcome_dependent, true, "after play began: outcome-dependent")
end
do
    local g = fakeGame { units = rout() }
    g.api.sight = function() error("sight: the symbol table is stale") end
    Botrun.run(g.api)
    local e = recordOf(g).env_status
    check(type(e) == "table" and e.fault, "crash", "a crash before the first board: a crash")
    check(type(e) == "table" and e.outcome_dependent, false, "before play: not outcome-dependent")
end
do
    local g = fakeGame { move = 0, units = standoff() }
    g.api.endPhase = function() return nil, {} end
    Botrun.run(g.api)
    local e = recordOf(g).env_status
    check(type(e) == "table" and e.fault, "timeout", "an enemy phase that never returns: a timeout")
    check(type(e) == "table" and e.outcome_dependent, true, "a timeout in play: outcome-dependent")
end
-- A claim kind the bot has no behaviour for is reported, never dropped.
do
    local g = fakeGame { claims = { { id = "t1", kind = "threat" } }, units = rout() }
    Botrun.run(g.api)
    local r = recordOf(g)
    check(r.claims_unplayed[1], "t1", "the unplayed claim is in the record")
    check(#r.claims_played, 0, "and not among the played")
end

-- One sight for the run, refreshed at every phase and after every action.
do
    local g = fakeGame { units = rout() }
    Botrun.run(g.api)
    check(g.sights, 1, "the sight is built once per run")
    check(g.phases, 2, "given a fresh phase (and cache) at each of the two player phases")
    check(g.refreshes >= 4, true, "and refreshed after each action too")
end

-- A Lua error anywhere in the run -- a sight call that never returned -- is a crash, and the
-- record is still emitted.
do
    local g = fakeGame { units = rout() }
    local sight = g.api.sight
    g.api.sight = function()
        local s = sight()
        s.attack = function() error("sight: call 0x08001000 did not return in 600 frames") end
        return s
    end
    local ok = Botrun.run(g.api)
    check(ok, false, "a Lua error is not a finished run")
    local r = recordOf(g)
    check(r.outcome, "crashed", "it is recorded as crashed")
end

-- A repeated board with a turn event still to fire waits for it instead of ending stuck.
do
    local g = fakeGame { move = 0, eventTurn = 4,
        units = standoff() }
    Botrun.run(g.api)
    local r = recordOf(g)
    check(r.outcome, "stuck", "still stuck once the event's turn has passed with nothing changed")
    -- a turn event fires at the phase change, so turn 4's board already shows what it did
    check(r.turns, 4, "but only once turn 4's event has had its turn, not at the first repeat (2)")
    check(g.eventAsks, 2, "the game's turn-event check is asked at the repeat and after the event")
end

-- A claimed reinforcement arrival is part of what decide reads: the turns to it change the hash.
do
    check(Bot.nextArrival({ { 3, 6 }, { 5 } }, 2), 1, "turn 3 is the next arrival after turn 2")
    check(Bot.nextArrival({ { 3 } }, 3), nil, "none left after the last")
    local turn2 = Botrun.boardHash(Bot, { turn = 2, units = {} }, nil, { { 5 } })
    local turn3 = Botrun.boardHash(Bot, { turn = 3, units = {} }, nil, { { 5 } })
    check(turn2 ~= turn3, true, "the same board, a turn nearer an arrival, hashes differently")
end

-- An enemy phase that ends the game still carries the deaths the watcher missed.
do
    local g = fakeGame {
        hit = 1,
        units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x02, 1, "blue", 1, 1, 20),
                  unit(0x81, 0, "red", 5, 5, 30) },
        enemy = function(g, find)
            for _, id in ipairs({ 0x01, 0x02 }) do
                local a = find(id)
                a.hp, a.dead, a.onField = 0, true, false
            end
            g.over = true
            return { { id = 0x01, charId = 0x01, faction = "blue", killer = 0x81 } }
        end,
    }
    Botrun.run(g.api)
    local r = recordOf(g)
    check(r.outcome, "lost", "game over is a loss")
    check(#r.deaths, 2, "the watched death and the one it missed are both recorded")
end

-- test_a_kept_plan_is_played_without_replanning: the planner plans A's and C's waits at
-- once; A's goes as expected, so C's is played from the same plan, and only the played-out
-- plan asks for a new one (which finds no one left to act).
do
    local Planner = dofile(here .. "planner.lua")
    local g = fakeGame { units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x02, 1, "blue", 0, 5, 20),
                                   unit(0x81, 0, "red", 9, 9, 10) } }
    local asked = 0
    g.api.Planner = {
        surprise = Planner.surprise,
        plan = function(_, board, _, _, opts)
            asked = asked + 1
            if opts and opts.stalled then g.stalledAsk = asked end
            for _, u in ipairs(board.units) do
                if u.faction == "blue" and u.acted then
                    return nil, nil, { phases = 3, averaged = 0 }
                end
            end
            if board.turn > 1 then return nil, nil, { phases = 3, averaged = 1 } end
            local acts = { { unit = 0x01, unitId = 0x01, act = "wait", move = { x = 1, y = 0 } },
                           { unit = 0x02, unitId = 0x02, act = "wait", move = { x = 1, y = 5 } } }
            return acts[1], { acts = acts, expect = { { hp = 20 }, { hp = 20 } },
                              enemies = { [0x81] = true } }, { phases = 3, averaged = 1 }
        end,
    }
    Botrun.run(g.api)
    local r = recordOf(g)
    check(r.plans.kept, 1, "C's wait is played from A's plan")
    check(r.plans.phases, 12, "the judged enemy phases of every call, a nil plan's too, summed")
    -- the stub's calls: turn 1's plan (1) and its played-out ask (0), turn 2's (1), turn 3's
    -- stalled ask (1)
    check(r.plans.averaged, 3, "the uncertain kills past the bound in every plan judged, "
          .. "a nil call's too, summed: never silent")
    check(asked, r.plans.made, "every plan asked for is counted")
    check(asked, 4, "turn 1: the plan and the played-out ask; turn 2: one ask; turn 3 repeats "
          .. "turn 2's board: one stalled ask; turn 4 repeats it again: stuck")
    check(r.board_repeats, 1, "the first repeat is a board repeat, not stuck (R-9)")
    check(r.stalls, nil, "the old name is gone")
    check(r.anomalies[1] and r.anomalies[1].kind, "stall_abort", "stuck is a stall abort")
    check(g.stalledAsk, 4, "the stalled ask is told it is stalled")
    check(r.outcome, "stuck", "a board that comes round again after a stall is stuck")
end

-- test_a_replan_is_handed_the_rest_of_the_plan: the planner plans A's, B's and C's waits; the
-- board is off after A's (a surprise), so the next ask carries B's and C's keys, in order, for
-- the planner to judge again (opts.rest). A fresh ask, one no plan was playing for, has none.
do
    local Planner = dofile(here .. "planner.lua")
    local g = fakeGame { units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x02, 1, "blue", 0, 5, 20),
                                   unit(0x03, 2, "blue", 0, 7, 20),
                                   unit(0x81, 0, "red", 9, 9, 10) } }
    local rests = {}
    g.api.Planner = {
        key = Planner.key,
        surprise = function(_, k) return k == 1 and "a blow missed" or nil end,
        plan = function(_, board, _, _, opts)
            rests[#rests + 1] = opts and opts.rest and table.concat(opts.rest, " ") or "none"
            if #rests > 1 or board.turn > 1 then return nil, nil, { phases = 0, averaged = 0 } end
            local acts = { { unit = 0x01, unitId = 0x01, act = "wait", move = { x = 1, y = 0 } },
                           { unit = 0x02, unitId = 0x02, act = "wait", move = { x = 1, y = 5 } },
                           { unit = 0x03, unitId = 0x03, act = "wait", move = { x = 1, y = 7 } } }
            return acts[1], { acts = acts, expect = { { hp = 20 }, { hp = 20 }, { hp = 20 } },
                              enemies = { [0x81] = true } }, { phases = 0, averaged = 0 }
        end,
    }
    Botrun.run(g.api)
    check(rests[1], "none", "rest: a fresh plan is handed no plan in hand")
    check(rests[2], "2>wait@1,5>nil 3>wait@1,7>nil",
          "rest: the replan is handed the acts not yet played, in order")
end

-- test_trace_tells_the_run: every act with the game's battle record, both phases, an arrival,
-- and the BOTRUN record last.
do
    local g = fakeGame {
        units = rout(),
        enemy = function(g)
            if g.turn == 1 then
                g.units[#g.units + 1] = unit(0x82, 1, "red", 9, 9, 10)   -- arrives in its phase
            end
            return {}
        end,
    }
    local evs, battle = {}, { actor = { charId = 1 }, target = { charId = 0x81 },
                              hits = { { by = "actor", dmg = 5 } } }
    g.api.trace = function(ev) evs[#evs + 1] = Json.decode(Json.encode(ev)) end
    g.api.battle = function() return battle end
    local endPhase = g.api.endPhase
    g.api.endPhase = function()
        local phase, deaths = endPhase()
        return phase, deaths, { { id = 0x81, charId = 0x81, from = { x = 1, y = 0 },
                                  to = { x = 1, y = 0 }, hp = 5, battles = {} } }
    end
    Botrun.run(g.api)
    local kinds = {}
    for _, e in ipairs(evs) do kinds[#kinds + 1] = e.t end
    kinds = table.concat(kinds, ",")
    check(evs[1].t, "start", "the trace opens with the run's info")
    check(evs[1].info.seed, 7, "which names the seed")
    check(evs[#evs].t, "end", "and closes with the record")
    check(evs[#evs].record.outcome, "won", "the record, whole")
    local acts, strikes, enemyActs, arrive, phases = 0, 0, 0, nil, 0
    for _, e in ipairs(evs) do
        if e.t == "act" and e.phase == "player" then
            acts = acts + 1
            if acts == 1 then
                check(e.from.x .. "," .. e.from.y, "0,0", "an act names where it moved from")
            end
            if e.act == "attack" then
                strikes = strikes + 1
                check(e.battles[1] and e.battles[1].hits[1].dmg, 5, "a strike carries the game's battle")
            else
                check(#e.battles, 0, "a move carries none")
            end
        end
        if e.t == "act" and e.phase == "enemy" then enemyActs = enemyActs + 1 end
        if e.t == "event" and e.kind == "arrive" then arrive = e end
        if e.t == "phase" then phases = phases + 1 end
        check(e.turn ~= nil, true, "every event names its turn: " .. e.t)
    end
    check(strikes >= 2, true, "both strikes on the first enemy are traced")
    check(enemyActs >= 1, true, "the enemy phase's acts are traced")
    check(arrive and arrive.id, 0x82, "the arrival is an event")
    check(phases >= 3, true, "each phase opens with a snapshot")
    check(kinds:find("plan", 1, true) ~= nil, true, "decisions are traced")
end

-- test_arrivals_seen_lists_only_what_the_screen_showed (ADR 0386, T060): a reinforcement's
-- arrival turn and tile are in the record only when it came up on screen; one under fog is not.
do
    local g = fakeGame {
        units = rout(),
        enemy = function(g)
            if g.turn == 1 then
                g.units[#g.units + 1] = unit(0x82, 1, "red", 9, 9, 10)
                local hid = unit(0x83, 2, "red", 9, 8, 10)
                hid.fogged = true
                g.units[#g.units + 1] = hid
                g.units[#g.units + 1] = unit(0x84, 3, "red", 8, 8, 10)
            end
            return {}
        end,
    }
    -- 0x84 lands in enemy phase 1 and acts there
    local endPhase = g.api.endPhase
    g.api.endPhase = function()
        local phase, deaths = endPhase()
        local acts = {}
        if g.turn == 2 then acts = { { id = 0x84, charId = 0x84, battles = {} } } end
        return phase, deaths, acts
    end
    Botrun.run(g.api)
    local r = recordOf(g)
    check(#r.arrivals_seen, 2, "two arrivals were on screen, the fogged one is not listed")
    local a, b = r.arrivals_seen[1] or {}, r.arrivals_seen[2] or {}
    if a.charId == 0x84 then a, b = b, a end
    check(a.charId, 0x82, "the seen arrival")
    check(a.turn, 2, "the player phase whose board first showed it")
    check(a.x .. "," .. a.y, "9,9", "and its tile")
    check(b.turn, 1, "one that acted in the enemy phase it landed in: that phase's turn")
end

-- test_enemies_seen_lists_every_red_out_of_fog (ADR 0399): what a retry may remember of the
-- enemy -- every red unit a board showed out of fog, once, by slot and character; a fogged one
-- is not listed until a board shows it.
do
    local g = fakeGame {
        units = rout(),
        enemy = function(g)
            if g.turn == 1 then
                local hid = unit(0x83, 2, "red", 9, 8, 10)
                hid.fogged = true
                g.units[#g.units + 1] = hid
            end
            return {}
        end,
    }
    Botrun.run(g.api)
    local r = recordOf(g)
    local seen, red = {}, 0
    for _, e in ipairs(r.enemies_seen) do seen[Bot.memoryKey(e.id, e.charId, e.classId)] = (seen[Bot.memoryKey(e.id, e.charId, e.classId)] or 0) + 1 end
    for _, u in ipairs(rout()) do
        if u.faction == "red" then
            red = red + 1
            check(seen[Bot.memoryKey(u.id, u.charId, u.classId)], 1, "a red in sight is listed once")
        end
    end
    check(red > 0, true, "the board has reds in sight")
    check(seen[Bot.memoryKey(0x83, 2)], nil, "one only ever fogged is not")
end

-- test_a_retry_starts_from_its_memory (ADR 0399): style.memory reaches the attempt's sight
-- (remember: what plays as seen); it is not handed back as seen this attempt (campaign.lua keeps
-- the union) nor given to the fog read's enemies seen; attempt 1 (no memory) tells nothing.
do
    local function played(memory)
        local g = fakeGame { units = rout() }
        g.api.style.memory = memory
        local told = "never"
        local make = g.api.sight
        g.api.sight = function()
            local s = make()
            s.remember = function(enemies) told = enemies end
            return s
        end
        Botrun.run(g.api)
        local r = recordOf(g)
        local keys = {}
        for _, e in ipairs(r.enemies_seen) do keys[Bot.memoryKey(e.id, e.charId, e.classId)] = true end
        return told, keys
    end
    local mem = { enemies = { { id = 0x9A, charId = 0x77 } } }
    local told, keys = played(mem)
    check(told, mem.enemies, "memory: the sight is told what plays as seen")
    check(keys[Bot.memoryKey(0x9A, 0x77)], nil, "memory: a remembered red never shown is not seen")
    told, keys = played(nil)
    check(told, nil, "attempt 1: the sight is told nothing")
    check(keys[Bot.memoryKey(0x9A, 0x77)], nil, "attempt 1: nothing remembered")
end

-- test_a_killer_that_arrived_in_the_phase_has_its_class (review of #599): a reinforcement loads
-- in the enemy phase, in fog, and kills A. The board before the phase does not hold it, so its
-- class is read from the board after the deaths, and it is among the enemies seen.
do
    local g = fakeGame { units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x02, 1, "blue", 0, 2, 20),
                                   unit(0x81, 0, "red", 9, 9, 10) },
                         enemy = function(g, find)
                             if g.turn == 1 and not g.came then
                                 g.came = true
                                 local W = unit(0x85, 4, "red", 1, 0, 10)
                                 W.classId, W.fogged = 0x22, true
                                 g.units[#g.units + 1] = W
                                 local u = find(0x01)
                                 u.hp, u.dead, u.onField = 0, true, false
                             end
                             return {}
                         end }
    g.api.killed = function()
        if g.turn ~= 2 or g.told then return {} end
        g.told = true
        return { { id = 0x01, charId = 0x01, faction = "blue", killer = 0x85, killerId = 0x85,
                   phase = "enemy" } }
    end
    Botrun.run(g.api)
    local r = recordOf(g)
    local d = r.deaths[1]
    check(d and d.killerClass, 0x22, "arrival: the killer's class, from the board after the phase")
    local shown = false
    for _, e in ipairs(r.enemies_seen) do
        if e.id == 0x85 and e.classId == 0x22 then shown = true end
    end
    check(shown, true, "arrival: the killer in fog is among the enemies seen (the fight showed it)")
end

-- test_enemies_seen_keep_a_reused_slot (ADR 0399): a red seen, then killed, and a reinforcement
-- later loaded into its slot: both are among the enemies seen (kept by slot, character and
-- class), so a retry remembers the first, alive again at the start.
do
    local g = fakeGame {
        units = rout(),
        enemy = function(g, find)
            if g.turn == 1 then
                for _, u in ipairs(g.units) do
                    if u.faction == "red" then
                        g.slot, g.char = u.id, u.charId
                        u.hp, u.dead, u.onField = 0, true, false
                        break
                    end
                end
                local n = unit(g.slot, 9, "red", 9, 8, 10)
                n.charId, n.classId = g.char, 0x33
                g.units[#g.units + 1] = n
            end
            return {}
        end,
    }
    Botrun.run(g.api)
    local r, n = recordOf(g), 0
    for _, e in ipairs(r.enemies_seen) do
        if e.id == g.slot then n = n + 1 end
    end
    check(n, 2, "reused slot: the unit killed and the arrival are both seen")
end

-- Botrun.events: a recruit is a unit whose character was on another side; items are diffed.
do
    local b = { units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x41, 0, "green", 3, 3, 15) } }
    b.units[1].items = { { id = 1 }, { id = 0x6C } }
    local a = { units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x02, 1, "blue", 3, 3, 15) } }
    a.units[1].items = { { id = 1 }, { id = 5 } }
    a.units[2].charId = 0x41
    b.units[2].onField = true
    local ev = Botrun.events(b, a)
    local by = {}
    for _, e in ipairs(ev) do by[e.kind] = e end
    check(by.recruit and by.recruit.from, "green", "the green unit came over")
    check(by.items and by.items.gained[1], 5, "an item gained")
    check(by.items and by.items.lost[1], 0x6C, "an item gone")
end

-- test_a_talk_recruit_is_no_kill: the green unit Talked to leaves its slot for a blue one.
do
    local g = fakeGame { units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x41, 0, "green", 1, 0, 15),
                                   unit(0x81, 0, "red", 9, 9, 10) } }
    g.units[2].charId = 0x30
    -- the first act also recruits the green unit, as a Talk does: its slot empties, a blue one
    -- fills with the same character
    local act, talked = g.api.act, false
    g.api.act = function(a)
        if not talked then
            talked = true
            table.remove(g.units, 2)                  -- the game clears the green slot
            local r = unit(0x02, 1, "blue", 1, 0, 15)
            r.charId, r.acted = 0x30, true
            g.units[#g.units + 1] = r
        end
        return act(a)
    end
    local evs = {}
    g.api.trace = function(ev) evs[#evs + 1] = ev end
    Botrun.run(g.api)
    local r = recordOf(g)
    check(r.kills["1"] == nil or r.kills["1"] == 1, true, "the recruit is not A's kill")
    local joined
    for _, e in ipairs(evs) do
        if e.t == "event" and e.kind == "recruit" then joined = e end
        if e.t == "act" then
            for _, f in ipairs(e.fell or {}) do
                check(f.charId ~= 0x30, true, "the recruit did not fall")
            end
        end
    end
    check(joined and joined.from, "green", "it joined from green")
end

-- The four-part clean clear (#510 step 9 design, part A): won, no blue or green unit lost,
-- every owed recruit joined, every village and chest taken, each read off the game.

-- the rout, judged: nothing owed, nothing to explore
local function judged(o)
    o.units = o.units or rout()
    o.recruits = o.recruits or {}
    local g = fakeGame(o)
    for k, v in pairs(o.api or {}) do g.api[k] = v end
    Botrun.run(g.api)
    return recordOf(g), g
end

-- test_a_theft_above_the_boosters_spoils_the_clear (ADR 0379): every theft is recorded; one
-- the game ranks above ITEM_BOOSTER_SKL (api.thefts: spoils) spoils it, one below does not.
do
    local function robbed(spoils)
        local told = false
        return judged { api = { thefts = function()
            if told then return {} end
            told = true
            return { { thief = 0x85, from = 0x01, item = spoils and 0x89 or 0x6C,
                       rank = spoils and 9 or 40, spoils = spoils } }
        end } }
    end
    local r = robbed(true)
    check(#r.thefts, 1, "theft: recorded")
    check(r.clear.stolen[1] and r.clear.stolen[1].item, 0x89, "theft: a Master Seal is stolen")
    check(r.clean, false, "theft: above the boosters, not clean")
    r = robbed(false)
    check(#r.thefts, 1, "theft: a Vulnerary recorded")
    check(#r.clear.stolen, 0, "theft: a Vulnerary spoils nothing")
    check(r.clean, true, "theft: below the boosters, still clean")
end

-- test_a_clean_rout_is_clean: the four parts hold.
do
    local r = judged {}
    check(r.clean, true, "clean: a won rout with nothing owed")
    check(r.clear.won, true, "clean: won")
    check(#r.clear.lost, 0, "clean: nobody lost")
    check(#r.clear.recruits_missing, 0, "clean: no recruit missing")
    check(#r.clear.rewards_missing, 0, "clean: no reward missing")
end

-- test_a_green_death_spoils_the_clear: a green ally falls in the enemy phase (design 11).
do
    local units = rout()
    units[#units + 1] = unit(0x41, 0, "green", 5, 5, 10)
    local r = judged { units = units, enemy = function(g, find)
        local v = find(0x41)
        if v.dead then return {} end
        v.hp, v.dead, v.onField = 0, true, false
        return { { id = 0x41, charId = 0x41, faction = "green", killer = 0x81 } }
    end }
    check(r.outcome, "won", "green death: the chapter is still won")
    check(r.deaths[1] and r.deaths[1].faction, "green", "green death: recorded, with its side")
    check(r.clean, false, "green death: not clean")
end

-- test_a_green_unit_a_script_unloads_is_not_lost: the chapter's ending clears its green units
-- (vanilla Ch6's villagers, Ch2's Garcia): gone from the field, but the game killed nobody.
do
    local units = rout()
    units[#units + 1] = unit(0x41, 0, "green", 5, 5, 10)
    local r = judged { units = units, enemy = function(g)
        -- ClearUnit empties the slot: the board read no longer has the unit at all
        for i, u in ipairs(g.units) do
            if u.id == 0x41 then table.remove(g.units, i) break end
        end
        return {}
    end }
    check(r.outcome, "won", "unloaded green: the chapter is won")
    check(#r.deaths, 0, "unloaded green: no death recorded")
    check(r.clean, true, "unloaded green: still clean")
end

-- test_a_slot_the_death_watch_could_not_read_is_a_watch_fault: freed and reloaded within a
-- frame, the slot no longer says whether its unit died: a watch fault, never a guess.
do
    local base
    local r = judged { api = { killed = function()
        local out = base or { { fault = "replaced", id = 0x41, charId = 0x41, faction = "green" } }
        base = {}
        return out
    end } }
    check(#r.deaths, 0, "unread slot: no death guessed")
    check(r.watch_faults[1] and r.watch_faults[1].kind, "death_unread", "unread slot: a watch fault")
    -- T008: a record that misread the board is not a clean environment's
    local e = r.env_status
    check(type(e) == "table" and e.fault, "watch", "unread slot: env_status names the watch")
    check(type(e) == "table" and e.outcome_dependent, true, "unread slot: outcome-dependent")
end

-- test_a_failed_act_still_records_its_deaths: the act killed a player unit, then the harness
-- failed: the run crashes with the death recorded.
do
    local g = fakeGame { units = rout() }
    g.api.act = function(a)
        g.units[1].hp, g.units[1].dead, g.units[1].onField = 0, true, false
        return false, "a menu never opened"
    end
    Botrun.run(g.api)
    local r = recordOf(g)
    check(r.outcome, "crashed", "failed act: crashed")
    check(#r.deaths, 1, "failed act: the death it caused is recorded")
end

-- test_a_recruit_never_seen_is_missing: owed X, X never comes on the field.
do
    local r = judged { recruits = { 0x30 } }
    check(r.recruits.owed[1], 0x30, "never seen: owed")
    check(r.clear.recruits_missing[1], 0x30, "never seen: missing")
    check(r.clean, false, "never seen: not clean")
end

-- test_a_recruit_already_blue_is_not_owed: X is in the party at the start, even undeployed
-- (Amelia in Eirika's Ch13 when Ch9 recruited her).
do
    local units = rout()
    local x = unit(0x05, 4, "blue", -1, -1, 18)
    x.charId, x.onMap, x.onField = 0x30, false, false
    units[#units + 1] = x
    local r = judged { units = units, recruits = { 0x30 } }
    check(#r.recruits.owed, 0, "already blue: not owed")
    check(r.clean, true, "already blue: clean")
end

-- test_a_talked_recruit_joins: the green unit turns blue on the first act.
do
    local g = fakeGame { recruits = { 0x30 },
        units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x41, 0, "green", 1, 0, 15),
                  unit(0x81, 0, "red", 1, 1, 10) } }
    g.units[2].charId = 0x30
    local act, talked = g.api.act, false
    g.api.act = function(a)
        if not talked then
            talked = true
            table.remove(g.units, 2)
            local r = unit(0x02, 1, "blue", 1, 0, 15)
            r.charId, r.acted = 0x30, true
            g.units[#g.units + 1] = r
        end
        return act(a)
    end
    Botrun.run(g.api)
    local r = recordOf(g)
    check(r.recruits.joined[1], 0x30, "talked: joined")
    check(r.clean, true, "talked: clean")
end

-- test_joined_is_the_games_party_not_the_unit_array: vanilla Ch5's ending runs
-- EventScr_StrictLoadUniqueAlly on an unrecruited Joshua, leaving a blue entry the game's own
-- roster test (IsUnitInCurrentRoster: US_DEAD, US_BIT16, a class attribute) keeps out of the
-- party. Here the entry is blue and not flagged dead, and the game's party still leaves it
-- out: the party decides, never the array.
do
    local g = fakeGame { recruits = { 0x30 },
        units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x81, 0, "red", 1, 0, 10) },
        party = function(g) return { 0x01 } end }
    local act = g.api.act
    g.api.act = function(a)
        local ok = act(a)
        if a.act == "attack" then
            local j = unit(0x05, 4, "blue", -1, -1, 24)
            j.charId, j.onMap, j.onField = 0x30, false, false
            g.units[#g.units + 1] = j
        end
        return ok
    end
    Botrun.run(g.api)
    local r = recordOf(g)
    check(#r.recruits.joined, 0, "out of the party: not joined")
    check(r.clear.recruits_missing[1], 0x30, "out of the party: missing")
    check(r.clean, false, "out of the party: not clean")
end

-- test_owed_is_read_from_the_games_party_at_the_start: a blue entry for X exists at the start
-- but the game's party leaves it out (a unit the game marked dead in an earlier chapter): X is
-- owed, and never joins.
do
    local units = rout()
    local x = unit(0x05, 4, "blue", -1, -1, 18)
    x.charId, x.onMap, x.onField = 0x30, false, false
    units[#units + 1] = x
    local r = judged { units = units, recruits = { 0x30 }, party = function() return { 0x01 } end }
    check(r.recruits.owed[1], 0x30, "not in the party at the start: owed")
    check(r.clean, false, "not in the party at the start: not clean")
end

-- test_a_razed_village_is_missing_at_once: a brigand's pillage act names the village's own
-- tile (the one the explore log keys, not the row above where the game runs the event), and
-- the game stops offering it.
do
    local tiles = { { x = 9, y = 8, kind = "visit" } }
    local r = judged { explorable = tiles, enemy = function(g, find)
        if #tiles == 0 then return {} end
        table.remove(tiles, 1)
        return {}, { { id = 0x81, charId = 0x81, act = "pillage", tile = { x = 9, y = 8 } } }
    end }
    local m = r.clear.rewards_missing[1]
    check(m and m.why, "closed", "razed: missing, closed")
    check(m and m.closed_by, 0x81, "razed: by the brigand")
    check(r.clean, false, "razed: not clean")
end

-- test_a_skipped_village_is_missing: still open at the end, never visited.
do
    local r = judged { explorable = { { x = 9, y = 9, kind = "visit" } } }
    local m = r.clear.rewards_missing[1]
    check(m and m.kind, "visit", "skipped: the village is missing")
    check(r.clean, false, "skipped: not clean")
end

-- A thief (0x82, far off) opens the chest at 9,8 in the first enemy phase and gains item 0x6C;
-- A meanwhile fights the red at 1,0. `killer` kills the thief in the second enemy phase and,
-- when blue, the game drops the chest's item to A (api.drops: its BATTLE_HandleItemDrop),
-- unless `missed` (the drop watch failing to catch it).
local function thiefGame(killer, missed, stays, joins)
    local units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x81, 0, "red", 1, 0, 30),
                    unit(0x82, 1, "red", 9, 9, 10), unit(0x41, 0, "green", 8, 9, 10) }
    for _, u in ipairs(units) do u.items = {} end
    local tiles = { { x = 9, y = 8, kind = "chest" } }
    local phase, dropped = 0, false
    local g = fakeGame { units = units, recruits = {}, hit = 10, explorable = tiles,
        enemy = function(g, find)
            phase = phase + 1
            local t = find(0x82)
            if phase == 1 then
                if not stays then table.remove(tiles, 1) end
                t.items = { { id = 0x6C, uses = 1 } }
                return {}, { { id = 0x82, charId = 0x82, act = "pick", tile = { x = 9, y = 8 } } }
            elseif phase == 2 and joins then
                t.faction = "blue"   -- recruited, the chest's item in its bag
                return {}
            elseif phase == 2 then
                t.hp, t.dead, t.onField = 0, true, false
                dropped = killer == 0x01 and not missed
                return { { id = 0x82, charId = 0x82, faction = "red", killer = killer,
                           ours = killer == 0x01 } }
            end
            return {}
        end }
    g.api.drops = function()
        if dropped then
            dropped = false
            return { { from = 0x82, to = 0x01, item = 0x6C } }
        end
        return {}
    end
    Botrun.run(g.api)
    return recordOf(g)
end

-- test_a_chest_won_back_from_its_thief_is_taken
do
    local r = thiefGame(0x01)
    check(#r.clear.rewards_missing, 0, "won back: the chest is taken")
    check(r.explore[1] and r.explore[1].won_back, true, "won back: said so")
    check(r.clean, true, "won back: clean")
    check(#r.watch_faults, 0, "won back: the drop was caught")
end

-- test_a_thief_opened_chest_still_listed_is_closed: AiPillageAction empties the chest's terrain
-- and leaves its event flag, so the game's list still names it (vanilla Ch3, Colm, 2026-10-30)
do
    local r = thiefGame(0x41, false, true)
    check(r.explore[1] and r.explore[1].status, "closed", "still listed: closed by the thief")
    check(r.explore[1] and r.explore[1].closed_by, 0x82, "still listed: by the thief")
end

-- test_a_thief_felled_by_ours_with_no_drop_caught_is_a_watch_fault: the game gave the drop
-- (popup.c marks the thief US_DROP_ITEM), so a miss is the watch's
do
    local r = thiefGame(0x01, true)
    local f = r.watch_faults[1]
    check(f and f.kind, "drop_missed", "missed drop: a watch fault")
    check(f and f.thief, 0x82, "missed drop: the thief")
    check(f and f.item, 0x6C, "missed drop: the chest's item")
end

-- test_a_chest_thief_killed_by_green_is_lost
do
    local r = thiefGame(0x41)
    local m = r.clear.rewards_missing[1]
    check(m and m.closed_by, 0x82, "green kill: the chest is missing, closed by the thief")
    check(r.clean, false, "green kill: not clean")
    check(#r.watch_faults, 0, "green kill: no drop was owed to us")
end

-- test_a_chest_whose_thief_joins_us_is_taken (ADR 0376 amended, Nicolas 2026-10-30: vanilla
-- Ch3's Colm opens two chests and is recruited holding them)
do
    local r = thiefGame(nil, false, false, true)
    check(#r.clear.rewards_missing, 0, "joined: the chest is taken")
    check(r.explore[1] and r.explore[1].won_back, true, "joined: said so")
    check(r.clean, true, "joined: clean")
end

-- test_no_recruit_list_leaves_clean_unjudged
do
    local g = fakeGame { units = rout() }
    Botrun.run(g.api)
    local r = recordOf(g)
    check(r.clear.recruits_missing, "unchecked", "no list: unchecked")
    check(r.clean, nil, "no list: not judged")
end

-- The graded record (#510 step 9, US1). A death graded against the plan that committed to
-- its board: M.grade, then the run-level outcomes.

-- a plan as botrun keeps it: made on a board (its snapshot), predicting each unit's phase
local function committed(o)
    return { ref = o.ref or 3, enemies = o.enemies or { [0x81] = true },
             snapshot = o.snapshot or { { id = 0x01, charId = 0x01, faction = "blue" },
                                        { id = 0x81, charId = 0x81, faction = "red" } },
             predict = o.predict or { { id = 0x01, die = 0.04, strikers = { 0x81 } } } }
end
local function death(o)
    local d = { id = 0x01, charId = 0x01, faction = "blue", turn = 2, killer = 0x81,
                killerId = 0x81, phase = "enemy" }
    for k, v in pairs(o or {}) do d[k] = v end
    return d
end

-- test_grade_takes_the_committing_plans_prediction (FR-003)
do
    local d = Botrun.grade(death(), committed {}, nil, nil, {})
    check(d.predicted, 0.04, "enemy phase: the last player-phase plan's predict")
    check(d.plan_ref, 3, "enemy phase: which plan")
    check(d.cause, "rng_tail", "a positive prediction under no cap is a tail")
    check(d.over_cap, nil, "no cap given: over_cap is null")
    local act = { unitId = 0x01, die = 0.3, f = { counters = true } }
    d = Botrun.grade(death { phase = "player" }, committed {}, act, nil, {})
    check(d.predicted, 0.3, "player phase: the attack's own counter chance")
    check(d.flags.player_phase, true, "player phase: flagged")
    local admits = dofile(here .. "planner.lua").admits
    d = Botrun.grade(death(), nil, nil, 0.05, {}, nil, nil, admits)
    check(d.predicted, nil, "no plan: no prediction")
    check(d.over_cap, nil, "no plan: over_cap is null, never false")
    check(d.flags.reinforcement, nil, "no plan: reinforcement unknown")
    check(d.cause .. "/" .. tostring(d.detail), "other/missing_prediction",
          "no plan: never counted as zero risk")
    check(d.family, "sandbox_fault", "missing prediction: a sandbox fault")
    d = Botrun.grade(death(), committed { predict = {} }, nil, nil, {})
    check(d.predicted, nil, "a plan with no read for the unit: null")
end

-- test_grade_flags_are_independent (FR-004)
do
    -- the killer was not on the board the plan was made on: an arrival
    local d = Botrun.grade(death { killer = 0x90, killerId = 0x90 }, committed {}, nil, nil, {})
    check(d.flags.reinforcement, true, "reinforcement: killer absent from the snapshot")
    check(d.flags.fog, false, "reinforcement: not fog")
    -- on the board but not among the enemies the plan saw
    d = Botrun.grade(death(), committed { enemies = {} }, nil, nil, {})
    check(d.flags.fog, true, "fog: killer absent from the plan's enemies")
    check(d.flags.reinforcement, false, "fog: not an arrival")
    -- the boss flag, as the board says
    local snap = { { id = 0x01, charId = 0x01, faction = "blue" },
                   { id = 0x81, charId = 0x81, faction = "red", isBoss = true } }
    d = Botrun.grade(death(), committed { snapshot = snap }, nil, nil, {})
    check(d.flags.boss, true, "boss: the killer's isBoss")
    check(d.flags.fog or d.flags.reinforcement, false, "boss alone")
    -- by charId, when the watch read no index: a generic shares its charId with others
    snap = { { id = 0x81, charId = 0x50, faction = "red" }, { id = 0x82, charId = 0x50, faction = "red" } }
    d = Botrun.grade(death { killer = 0x50, killerId = false }, committed { snapshot = snap,
        enemies = { [0x82] = true } }, nil, nil, {})
    check(d.flags.fog, false, "by charId: one of them was seen")
    check(d.flags.player_phase, false, "enemy phase")
end

-- test_cause_precedence (FR-005)
do
    local all = { over_cap = true, predicted = 0.3, killer = 0x81,
                  flags = { reinforcement = true, fog = true, boss = true, player_phase = true } }
    check(Botrun.cause(all, {}), "over_cap", "over_cap first")
    all.over_cap = false
    check(Botrun.cause(all, {}), "reinforcement", "then reinforcement")
    all.flags.reinforcement = false
    check(Botrun.cause(all, {}), "fog", "then fog")
    all.flags.fog = false
    check(Botrun.cause(all, {}), "rng_tail", "then a positive prediction under the cap")
    local zero = { predicted = 0, killer = 0x81, flags = {} }
    local c, detail = Botrun.cause(zero, { struck = true, strikers = 1 })
    check(c .. "/" .. detail, "other/forecast_desync", "zero, its lone judged striker killed it")
    check(Botrun.DETAILS[detail], "sandbox_fault", "a desync is a sandbox fault")
    c, detail = Botrun.cause(zero, { struck = true, strikers = 2 })
    check(detail, "zero_multi_attacker", "zero, among several judged strikers")
    check(Botrun.DETAILS[detail], "blindspot", "a blindspot")
    c, detail = Botrun.cause(zero, { struck = false, strikers = 1 })
    check(detail, "unrevealed_killer", "zero, a killer the judged phase never sent")
    c, detail = Botrun.cause({ predicted = 0, flags = {} }, {})
    check(detail, "noncombat", "zero, no fighter")
    c, detail = Botrun.cause({ predicted = 0, killer = 0x81, flags = { player_phase = true } },
                             { counters = false })
    check(detail, "player_phase_counter", "a counter the forecast did not expect")
    c, detail = Botrun.cause({ predicted = 0, killer = 0x81, flags = { player_phase = true } },
                             { counters = true })
    check(detail, "forecast_desync", "a counter expected at zero that killed")
    for _, name in ipairs(Botrun.CAUSES) do
        check(type(name), "string", "the cause list is names")
    end
end

-- test_graded_outcomes (FR-006, FR-008): two allied greens die; the owed
-- recruit 0x30 was killed, 0x31 never reached; a village was never offered; the run is won.
do
    local units = rout()
    units[#units + 1] = unit(0x41, 0, "green", 5, 5, 10)
    units[#units + 1] = unit(0x42, 1, "green", 6, 6, 10)
    units[#units + 1] = unit(0x30, 2, "red", 9, 0, 1)
    -- 0x32 is owed, and on our side and dead by the run's end: it joined and fell
    units[#units + 1] = unit(0x32, 3, "blue", 0, 9, 10)
    local g = fakeGame { units = units, recruits = { 0x30, 0x31, 0x32 },
                         party = function(g)
                             local out = {}
                             for _, u in ipairs(g.units) do
                                 if u.faction == "blue" and not u.dead and u.charId ~= 0x32
                                     or (u.charId == 0x32 and g.turn > 1 and not u.dead) then
                                     out[#out + 1] = u.charId
                                 end
                             end
                             return out
                         end,
                         explorable = { { x = 9, y = 9, kind = "visit" } },
                         enemy = function(g, find)
                             if g.turn ~= 1 then return {} end
                             for _, id in ipairs({ 0x41, 0x42, 0x30, 0x32 }) do
                                 local v = find(id)
                                 v.hp, v.dead, v.onField = 0, true, false
                             end
                             return {}
                         end }
    Botrun.run(g.api)
    local r = recordOf(g)
    check(r.outcome, "won", "graded: a win with misses stays won (AS 2)")
    check(r.clean, false, "graded: and not clean")
    check(r.turns_to_win, r.turns, "graded: turns to win")
    -- an escort (a green the game ends on) cannot fall in a won run: its death is the loss,
    -- test_a_protected_green_unit_felled_ends_the_run_lost
    check(r.greens.allied_deaths[1], 0x41, "graded: an allied green")
    check(r.greens.allied_deaths[2], 0x42, "graded: and the other")
    check(r.first_death_turn, 1, "graded: the joined recruit's death is a player death")
    local why = {}
    for _, m in ipairs(r.missed_recruits) do why[m.charId] = m.reason end
    check(why[0x30], "killed_before_talk", "graded: a recruit killed first")
    check(why[0x31], "unknown", "graded: greedy records no Talk offers, so it cannot say")
    check(why[0x32], "died_after_joining", "graded: one that joined and fell")
    local m = r.missed_rewards[1]
    check(m and m.kind, "visit", "graded: the missed reward's kind")
    check(m and m.reason, "unknown", "graded: greedy counts no offers, so it cannot say")
    local same = 0
    for _, a in ipairs(r.anomalies) do
        if a.kind == "same_turn_green" then same = same + 1 end
    end
    check(same, 2, "graded: greens lost on the turn first seen")
end

-- test_first_death_turn_and_a_lost_run_has_no_turns_to_win
do
    local g = fakeGame {
        hit = 1,
        units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x81, 0, "red", 5, 5, 30) },
        enemy = function(g, find)
            if g.turn == 2 then
                local a = find(0x01)
                a.hp, a.dead, a.onField = 0, true, false
                g.over = true
            end
            return {}
        end,
    }
    Botrun.run(g.api)
    local r = recordOf(g)
    check(r.first_death_turn, 2, "first death turn")
    check(r.turns_to_win, nil, "a loss has no turns to win")
    check(r.deaths[1].cause, "other", "greedy: no plan behind it")
    check(r.deaths[1].detail, "noncombat", "no fighter: noncombat, not a sandbox fault")
    check(r.deaths[1].over_cap, nil,
          "greedy has no cap: the over-cap check has not run (null, not false)")
end

-- test_seize_skips_and_stalls (FR-007, FR-015, plan T049): a planner offered the Seize keeps
-- waiting. With a goal of its ledger still feasible the skip is justified and no stall; with
-- nothing left and a Seize under the cap judged, each skip is a stall. Every Seize plan over
-- the cap justifies it; none judged at all does not. Three turns with no lord move, kill,
-- visit, talk or chest are an idle_3 stall.
do
    local function seizer(ledger, seize)
        seize = seize or { judged = true, admitted = true }
        local g = fakeGame { units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x81, 0, "red", 9, 9, 10) },
                             turnsLeft = 5 }
        g.api.info.trace = "trace.jsonl"
        local sight = g.api.sight
        g.api.sight = function()
            local s = sight()
            s.objective.gameOver = { 0x01 }
            return s
        end
        local n = 0
        g.api.Planner = {
            surprise = function() return "the plan is played out" end,
            plan = function(_, board)
                for _, u in ipairs(board.units) do
                    if u.faction == "blue" and u.acted then return nil end
                end
                n = n + 1
                local a = { unit = 0x01, unitId = 0x01, act = "wait",
                            move = { x = 0, y = n % 2 } }   -- back and forth: a lord moving
                return a, { acts = { a }, expect = { { hp = 20 } }, enemies = { [0x81] = true },
                            seizable = true, ledger = ledger, seizeJudged = seize.judged,
                            seizeAdmitted = seize.admitted }
            end,
        }
        Botrun.run(g.api)
        return recordOf(g)
    end
    local r = seizer({ { id = "visit:3,3", kind = "visit", status = "feasible" },
                       { id = "chest:4,4", kind = "chest", status = "unknown" } })
    check(#r.seize_skips, 5, "seize skips: one a turn")
    check(r.seize_skips[1].turn, 1, "seize skips: the turn")
    check(table.concat(r.seize_skips[1].ledger, " "), "visit:3,3",
          "seize skips: the ledger's feasible goals (an unknown one justifies nothing)")
    check(r.seize_skips[1].justified, true, "seize skips: an open village justifies it")
    check(#r.stall_events, 0, "a justified skip alone is not a stall")
    check(r.turns_to_win, 5, "turns to win, on a winner")
    check(#r.anomalies, 0, "a win put off only for open goals is no seize delay")
    check(seizer({}, { judged = true, admitted = false }).seize_skips[1].justified, true,
          "seize skips: every Seize over the cap justifies it")
    local lost = seizer({}, { judged = false, admitted = false }).seize_skips[1]
    check(tostring(lost.justified) .. " " .. lost.reason, "false no plan with the Seize was judged",
          "seize skips: a Seize no plan judged is a fault")
    r = seizer({ { id = "visit:3,3", kind = "visit", status = "closed" } })
    check(r.seize_skips[1].justified, false, "nothing the win would close: unjustified")
    check(r.stall_events[1] and r.stall_events[1].kind, "unjustified_seize_skip",
          "an unjustified skip is a stall")
    check(r.anomalies[1] and r.anomalies[1].kind, "seize_delay", "an unjustified skip delays")
    check(r.anomalies[1] and r.anomalies[1].turn, 1, "from the first unjustified skip")
    check(r.anomalies[1] and r.anomalies[1].delay, 4, "by how many turns")

    -- idle: a lord holding still with nothing to do for three player phases
    local g = fakeGame { units = standoff(), turnsLeft = 4 }
    local sight = g.api.sight
    g.api.sight = function()
        local s = sight()
        s.objective.gameOver = { 0x01 }
        return s
    end
    g.api.Planner = {
        surprise = function() return "the plan is played out" end,
        plan = function(_, board)
            for _, u in ipairs(board.units) do
                if u.faction == "blue" and u.acted then return nil end
            end
            local a = { unit = 0x01, unitId = 0x01, act = "wait", move = { x = 0, y = 0 } }
            return a, { acts = { a }, expect = { { hp = 20 } }, enemies = { [0x81] = true } }
        end,
    }
    g.eventTurn = 99
    Botrun.run(g.api)
    local r2 = recordOf(g)
    local idle = {}
    for _, e in ipairs(r2.stall_events) do
        if e.kind == "idle_3" then idle[#idle + 1] = e.turn end
    end
    check(table.concat(idle, ","), "3", "idle_3: on the third idle turn (four turns played)")
end

-- test_review_fixes (PR #559's review): no fighter is noncombat even with a positive
-- prediction; a reloaded slot is an arrival; a green no phase saw is unseen_green, not
-- same-turn; an idle stretch is a stall every third phase; an enemy-phase kill is no progress.
do
    local d = Botrun.grade(death { killer = false, killerId = false }, committed {}, nil, nil, {})
    check(d.cause .. "/" .. tostring(d.detail), "other/noncombat",
          "no fighter: noncombat before the tail, though the plan predicted 4%")
    -- slot 0x81 held 0x81 when the plan was made; an arrival 0x90 reloaded it
    d = Botrun.grade(death { killer = 0x90, killerId = 0x81 }, committed {}, nil, nil, {})
    check(d.flags.reinforcement, true, "a reloaded slot: matched by index and charId")
    -- the same, with a generic of the same charId: the snapshot's 0x81 fell at decision 3 or
    -- later (diedAt), so the killer in its slot arrived after the plan
    d = Botrun.grade(death(), committed {}, nil, nil, {}, nil, { [0x81] = 3 })
    check(d.flags.reinforcement, true, "a reloaded slot, same charId: the snapshot's unit fell")
    d = Botrun.grade(death(), committed {}, nil, nil, {}, nil, { [0x81] = 2 })
    check(d.flags.reinforcement, false, "a slot freed before the plan: the snapshot's unit is the killer")

    -- a green that arrives in the enemy phase and dies on a later enemy phase before any
    -- player phase saw it; and an idle stretch of six turns where the enemy dies on a counter
    local g = fakeGame { units = standoff(), turnsLeft = 7, enemy = function(g, find)
        if g.turn == 2 then g.units[#g.units + 1] = unit(0x43, 5, "green", 5, 5, 10) end
        return {}
    end }
    local endPhase = g.api.endPhase
    g.api.endPhase = function()
        local phase, deaths, acts = endPhase()
        return phase, deaths, acts
    end
    local killed = g.api.killed
    g.api.killed = function()
        local out = killed()
        if g.turn == 3 and not g.greenDone then
            g.greenDone = true
            out[#out + 1] = { id = 0x43, charId = 0x43, faction = "green", turn = 2, phase = "enemy" }
        end
        if g.turn == 4 and not g.redDone then
            g.redDone = true
            out[#out + 1] = { id = 0x99, charId = 0x99, faction = "red", phase = "enemy" }
        end
        return out
    end
    Botrun.run(g.api)
    local r = recordOf(g)
    local kinds, idle = {}, {}
    for _, a in ipairs(r.anomalies) do kinds[#kinds + 1] = a.kind end
    check(table.concat(kinds, ","):find("unseen_green") ~= nil, true, "a green never seen: unseen_green")
    check(table.concat(kinds, ","):find("same_turn_green"), nil, "and not same_turn_green")
    for _, e in ipairs(r.stall_events) do
        if e.kind == "idle_3" then idle[#idle + 1] = e.turn end
    end
    check(table.concat(idle, ","), "3,6", "idle_3: every third idle phase; an enemy-phase kill is no progress")
end

-- test_a_killer_that_dies_later_in_the_phase_is_still_the_killer: in one enemy phase X kills
-- A, then dies on B's counter. The game lists the deaths in that order, so A's grade still
-- finds X on the plan's board: no reinforcement.
do
    local X = unit(0x81, 0, "red", 0, 1, 10)
    X.classId = 0x0E
    local g = fakeGame { units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x02, 1, "blue", 0, 2, 20), X },
                         enemy = function(g, find)
                             for _, id in ipairs({ 0x01, 0x81 }) do
                                 local u = find(id)
                                 u.hp, u.dead, u.onField = 0, true, false
                             end
                             return {}
                         end }
    g.api.killed = function()
        if g.turn ~= 2 or g.told then return {} end
        g.told = true
        return { { id = 0x01, charId = 0x01, faction = "blue", killer = 0x81, killerId = 0x81,
                   phase = "enemy" },
                 { id = 0x81, charId = 0x81, faction = "red", killer = 0x02, killerId = 0x02,
                   phase = "enemy" } }
    end
    g.api.Planner = {
        surprise = function() return "the plan is played out" end,
        plan = function(_, board)
            for _, u in ipairs(board.units) do
                if u.faction == "blue" and u.acted then return nil end
            end
            local a = { unit = 0x02, unitId = 0x02, act = "wait", move = { x = 0, y = 2 } }
            return a, { acts = { a }, expect = { { hp = 20 } }, enemies = { [0x81] = true },
                        predict = { { id = 0x01, charId = 0x01, x = 0, y = 0, hp = 20, die = 0.3,
                                      taken = 6, strikes = 1, strikers = { 0x81 } } } }
        end,
    }
    Botrun.run(g.api)
    local r = recordOf(g)
    local d = r.deaths[1]
    check(d and d.flags.reinforcement, false, "same phase: the killer fell after its kill")
    check(d and d.cause, "rng_tail", "same phase: the plan's 30% was the roll")
    -- the killer's class, read from the board before the death (it fell on the counter, so the
    -- board after has none): what a retry keys it by, ADR 0399; and the fight showed it
    check(d and d.killerClass, 0x0E, "same phase: the killer's class is recorded")
    local shown = false
    for _, e in ipairs(r.enemies_seen) do
        if e.id == 0x81 and e.classId == 0x0E then shown = true end
    end
    check(shown, true, "same phase: the killer is among the enemies seen")
end

-- test_the_planner_is_told_every_enemy_seen (#510 PR A, the fog rule): opts.seen holds every
-- red a board showed out of fog this attempt, slot -> charId, and never one only ever fogged.
do
    local g = fakeGame { units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x81, 0, "red", 5, 5, 10),
                                   unit(0x82, 1, "red", 9, 9, 10) } }
    for _, u in ipairs(g.units) do
        if u.id == 0x82 then u.fogged = true end
    end
    local got
    g.api.Planner = {
        surprise = function() return "the plan is played out" end,
        plan = function(_, board, _, _, opts)
            got = got or opts.seen
            for _, u in ipairs(board.units) do
                if u.faction == "blue" and u.acted then return nil end
            end
            local a = { unit = 0x01, unitId = 0x01, act = "wait", move = { x = 0, y = 0 } }
            return a, { acts = { a }, expect = { { hp = 20 } }, enemies = { [0x81] = true } }
        end,
    }
    Botrun.run(g.api)
    check(got and got[0x81], 0x81, "seen: a red in sight, by slot, its charId")
    check(got and got[0x82], nil, "seen: not one only ever fogged")
    -- nor one a retry remembers (ADR 0399): the fog read's enemies seen are this attempt's alone,
    -- so a remembered unit is not also its stand-in for what the fog may hide
    local g2 = fakeGame { units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x82, 1, "red", 9, 9, 10) } }
    g2.units[2].fogged = true
    g2.api.style.memory = { enemies = { { id = 0x82, charId = 0x82, classId = 1 } } }
    got = nil
    g2.api.Planner = g.api.Planner
    Botrun.run(g2.api)
    check(got and got[0x82], nil, "seen: not one only remembered")
end

-- test_enemy_phase_death_graded_by_its_mover (#510 PR A): a unit's enemy-phase death is
-- graded by the plan that moved it, not by a later replan that found it over the cap; a unit
-- no plan moved this turn falls back to the phase's last plan.
do
    local function run(moveFirst)
        local g = fakeGame { units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x02, 1, "blue", 0, 2, 20),
                                       unit(0x03, 2, "blue", 0, 3, 20), unit(0x81, 0, "red", 0, 1, 10) },
                             enemy = function(g, find)
                                 local u = find(0x01)
                                 u.hp, u.dead, u.onField = 0, true, false
                                 g.killNow = true
                                 return {}
                             end }
        g.api.killed = function()
            if not g.killNow or g.told then return {} end
            g.told = true
            return { { id = 0x01, charId = 0x01, faction = "blue", killer = 0x81, killerId = 0x81,
                       phase = "enemy" } }
        end
        g.api.Planner = {
            surprise = function() return "the plan is played out" end,
            plan = function(_, board)
                local left, n = {}, 0
                for _, u in ipairs(board.units) do
                    if u.faction == "blue" and u.onField and not u.acted then left[u.id], n = u, n + 1 end
                end
                local id = (moveFirst and left[0x01]) and 0x01 or (left[0x02] and 0x02)
                    or (left[0x03] and 0x03) or nil
                if not id then return nil end
                -- the first plan read 0x01 at 30%; every replan after it, at 90%
                local die = n == 3 and 0.3 or 0.9
                local a = { unit = id, unitId = id, act = "wait", move = { x = left[id].x, y = left[id].y } }
                return a, { acts = { a }, expect = { { hp = 20 } }, enemies = { [0x81] = true },
                            predict = { { id = 0x01, charId = 0x01, x = 0, y = 0, hp = 20, die = die,
                                          taken = 6, strikes = 1, strikers = { 0x81 } } } }
            end,
        }
        Botrun.run(g.api)
        return recordOf(g).deaths[1]
    end
    local d = run(true)
    check(d and d.predicted, 0.3, "moved by the first plan: its 30%, not the replan's 90%")
    check(d and d.plan_ref, 1, "and its plan_ref is the mover's (the first plan made)")
    d = run(false)
    check(d and d.predicted, 0.9, "moved by no plan: the phase's last plan")
end

-- test_only_a_protected_death_has_a_cap (FR-009): the cap is on blue units and on units whose
-- death ends the game; an allied green's death is graded with no cap, so never over it.
do
    local green = death { faction = "green", charId = 0x41, id = 0x41 }
    local admits = dofile(here .. "planner.lua").admits
    local d = Botrun.grade(green, committed { predict = { { id = 0x41, die = 0.3,
                                                            strikers = { 0x81 } } } },
                           nil, 0.01, { [0x01] = true }, nil, nil, admits)
    check(d.cap, nil, "an allied green has no cap")
    check(d.over_cap, nil, "and so no over-cap verdict")
    local vip = death { faction = "green", charId = 0x41, id = 0x41 }
    d = Botrun.grade(vip, committed {}, nil, 0.01, { [0x41] = true }, nil, nil, admits)
    check(d.cap, 0.01, "a game-over green has its style's cap")
    d = Botrun.grade(death(), committed {}, nil, 0.01, {}, nil, nil, admits)
    check(d.cap, 0.01, "a blue has its style's cap")
    -- a cap with no test to apply it is a fault, never a death left ungraded (FR-010)
    local ok, err = pcall(Botrun.grade, death(), committed {}, nil, 0.01, {})
    check(ok, false, "a cap without admits raises")
    check(tostring(err):find("admits", 1, true) ~= nil, true, "and says why")
    -- graded by the planner's own admission: a sum a few ulps over the cap is at it
    local Planner = dofile(here .. "planner.lua")
    d = Botrun.grade(death(), committed { predict = { { id = 0x01, die = 0.05 + 1e-15,
                                                        strikers = { 0x81 } } } },
                     nil, 0.05, {}, nil, nil, Planner.admits)
    check(d.over_cap, false, "dust: graded as the planner admitted it")
end

-- test_a_fallback_plan_and_its_death_are_graded_against_the_cap (#510 step 9 PR-C, FR-011):
-- the planner's careful cap (1%) reaches the death's grade, a 30% prediction is over it, and
-- a committed FALLBACK_SACRIFICE plan is an anomaly on its turn.
do
    local g = fakeGame { units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x02, 1, "blue", 0, 5, 20),
                                   unit(0x81, 0, "red", 0, 1, 10) },
                         enemy = function(g, find)
                             local u = find(0x01)
                             u.hp, u.dead, u.onField = 0, true, false
                             g.over = true
                             return {}
                         end }
    g.api.killed = function()
        if g.told then return {} end
        g.told = true
        return { { id = 0x01, charId = 0x01, faction = "blue", killer = 0x81, killerId = 0x81,
                   phase = "enemy" } }
    end
    g.api.Planner = {
        CAPS = { careful = 0.01 },
        admits = dofile(here .. "planner.lua").admits,
        surprise = function() return "the plan is played out" end,
        plan = function(_, board)
            -- each blue yet to act gets its own plan: two plans over the cap on turn 1
            local u
            for _, x in ipairs(board.units) do
                if x.faction == "blue" and not x.acted and not u then u = x end
            end
            if not u then return nil end
            local a = { unit = u.id, unitId = u.id, act = "wait", move = { x = u.x, y = u.y } }
            return a, { acts = { a }, expect = { { hp = 20 } }, enemies = { [0x81] = true },
                        fallback = "FALLBACK_SACRIFICE",
                        rank = { admitted = false, max_die = u.id == 0x01 and 0.3 or 0.2,
                                 max_exceed = 0.29 },
                        predict = { { id = 0x01, charId = 0x01, x = 0, y = 0, hp = 20, die = 0.3,
                                      taken = 20, strikes = 1, strikers = { 0x81 } } } }
        end,
    }
    Botrun.run(g.api)
    local r = recordOf(g)
    local d = r.deaths[1]
    check(d and d.cap, 0.01, "cap: the style's cap reaches the grade")
    check(d and d.over_cap, true, "cap: 30% is over careful's 1%")
    check(d and d.cause, "over_cap", "cap: so the cause is over_cap")
    local fb
    for _, x in ipairs(r.anomalies) do
        if x.kind == "fallback_sacrifice" then fb = x end
    end
    check(fb and fb.turn, 1, "fallback: an anomaly on the turn it was committed")
    check(fb and fb.max_die, 0.3, "fallback: with the largest death chance it accepted")
    local n = 0
    for _, x in ipairs(r.anomalies) do
        if x.kind == "fallback_sacrifice" then n = n + 1 end
    end
    check(n, 1, "fallback: one anomaly a turn, however often it replans")
    check(fb and fb.plans, 2, "fallback: counting the plans made over the cap that turn")
end

-- test_missed_reasons_under_the_planner: offered and never taken is skipped; closed by another
-- side before any offer is closed; never offered is never_offered; a Talk never offered is
-- not_reached.
do
    local tiles = { { x = 9, y = 0, kind = "visit" }, { x = 0, y = 9, kind = "visit" },
                    { x = 5, y = 5, kind = "chest" } }
    local open = { tiles[1], tiles[2], tiles[3] }
    local g = fakeGame { units = standoff(), turnsLeft = 3, recruits = { 0x31 },
                         explorable = open,
                         enemy = function(g)
                             if g.turn == 1 then table.remove(open, 3) end   -- pillaged
                             return {}
                         end }
    g.api.Planner = {
        surprise = function() return "the plan is played out" end,
        plan = function(_, board)
            for _, u in ipairs(board.units) do
                if u.faction == "blue" and u.acted then return nil end
            end
            local a = { unit = 0x01, unitId = 0x01, act = "wait", move = { x = 0, y = 0 } }
            return a, { acts = { a }, expect = { { hp = 20 } }, enemies = { [0x81] = true },
                        explore = { { x = 9, y = 0, die = 0 } } }
        end,
    }
    Botrun.run(g.api)
    local r = recordOf(g)
    local why = {}
    for _, m in ipairs(r.missed_rewards) do why[m.x .. "," .. m.y] = m.reason end
    check(why["9,0"], "skipped", "reasons: offered, never taken")
    check(why["5,5"], "closed", "reasons: closed by another side before any offer")
    check(why["0,9"], "never_offered", "reasons: never offered")
    check(r.missed_recruits[1] and r.missed_recruits[1].reason, "not_reached",
          "reasons: a Talk never offered")
end

-- test_a_bait_loop: an enemy drawn between two tiles for four turns is an anomaly, once.
do
    local g = fakeGame { units = standoff(), turnsLeft = 7, enemy = function(g, find)
        local e = find(0x81)
        e.x = e.x == 9 and 8 or 9
        return {}
    end }
    Botrun.run(g.api)
    local r = recordOf(g)
    local n = 0
    for _, a in ipairs(r.anomalies) do
        if a.kind == "bait_loop" then n = n + 1; check(a.turn, 4, "bait loop: on the fourth turn") end
    end
    check(n, 1, "bait loop: once")
end

-- test_the_record_sums_the_lookahead (T064, FR-018): each decision's lookahead cost is summed
-- into rec.lookahead, and the planner is told the attempt's calls left (Planner.LOOK_ATTEMPT
-- less those spent).
do
    local Planner = dofile(here .. "planner.lua")
    local g = fakeGame { units = rout() }
    local left = {}
    g.api.Planner = {
        surprise = Planner.surprise, LOOK_ATTEMPT = Planner.LOOK_ATTEMPT,
        plan = function(_, board, _, _, opts)
            left[#left + 1] = opts.budget.attempt
            local look = { decisions = 1, triggered = 1, extended = 1, skipped_budget = 0,
                           calls = 3, cpu_s = 0.5 }
            for _, u in ipairs(board.units) do
                if u.faction == "blue" and u.acted then return nil, nil, { look = look } end
            end
            local acts = { { unit = 0x01, unitId = 0x01, act = "attack", target = 0x81,
                             targetId = 0x81, move = { x = 0, y = 0 } } }
            return acts[1], { acts = acts, expect = { { hp = 20 } }, enemies = { [0x81] = true },
                              lookahead = { trigger = { "boss" }, extended = true, calls = 3 } },
                { look = look }
        end,
    }
    local traced
    g.api.trace = function(ev)
        if ev.t == "plan" and ev.lookahead then traced = ev.lookahead end
    end
    Botrun.run(g.api)
    local r = recordOf(g)
    check(traced and traced.trigger[1], "boss", "the plan's trace says what triggered it")
    local n = #left
    check(n >= 2, true, "more than one decision")
    check(r.lookahead.decisions, n, "every decision counted")
    check(r.lookahead.calls, 3 * n, "their calls summed")
    check(r.lookahead.cpu_s, 0.5 * n, "and their CPU")
    check(left[1], Planner.LOOK_ATTEMPT, "the first is told the whole attempt budget")
    check(left[2], Planner.LOOK_ATTEMPT - 3, "the next what the first left")
end

-- test_an_exhausted_lookahead_is_an_anomaly (#570): a decision the attempt's budget left one
-- phase deep is visible in the record -- one lookahead_budget anomaly an attempt, on the first
-- such turn, counting every decision skipped -- not only as a sum in rec.lookahead.
do
    local Planner = dofile(here .. "planner.lua")
    local g = fakeGame { units = rout() }
    g.api.Planner = {
        surprise = Planner.surprise, LOOK_ATTEMPT = 0,
        plan = function(_, board)
            local look = { decisions = 1, triggered = 1, extended = 0, skipped_budget = 1,
                           calls = 0, cpu_s = 0 }
            for _, u in ipairs(board.units) do
                if u.faction == "blue" and u.acted then return nil, nil, { look = look } end
            end
            local acts = { { unit = 0x01, unitId = 0x01, act = "attack", target = 0x81,
                             targetId = 0x81, move = { x = 0, y = 0 } } }
            return acts[1], { acts = acts, expect = { { hp = 20 } }, enemies = { [0x81] = true },
                              lookahead = { trigger = { "boss" }, skipped = true, calls = 0 } },
                { look = look }
        end,
    }
    Botrun.run(g.api)
    local r = recordOf(g)
    local seen = {}
    for _, a in ipairs(r.anomalies) do
        if a.kind == "lookahead_budget" then seen[#seen + 1] = a end
    end
    check(r.lookahead.skipped_budget > 1, true, "more than one decision skipped")
    check(#seen, 1, "one lookahead_budget anomaly an attempt")
    check(seen[1] and seen[1].skipped, r.lookahead.skipped_budget, "counting every skip")
    check(seen[1] and seen[1].turn ~= nil, true, "on the turn it first ran out")
end

-- The diagnostic replay (#510 step 9 PR F, T072/T074, FR-019): the attempt played again from
-- the same start, matched against its original trace up to the pinned decision `ref`, then
-- the diagnostic's plan played there. A in the rout attacks from (0,0) and the enemy phase
-- kills a unit standing on (0,0) on turn 1; the forced wait on (0,1) avoids that.
local Planner = dofile(here .. "planner.lua")
local function deadly(g, find)
    local a = find(0x01)
    if g.turn == 1 and a and not a.dead and a.x == 0 and a.y == 0 then
        a.hp, a.dead, a.onField = 0, true, false
        return { { id = 0x01, charId = 0x01, faction = "blue", killer = 0x81 } }
    end
    return {}
end
-- the planner the original run played: A attacks from where it stands; nothing once A acted
local function attacker(seen)
    return {
        surprise = Planner.surprise, key = Planner.key, keysOf = Planner.keysOf,
        unkey = Planner.unkey,
        plan = function(_, board, _, _, opts)
            if seen then seen[#seen + 1] = opts and opts.diag or "baseline" end
            for _, u in ipairs(board.units) do
                if u.id == 0x01 and u.onField and not u.acted then
                    local acts = { { unit = 0x01, unitId = 0x01, act = "attack", target = 0x81,
                                     targetId = 0x81, move = { x = 0, y = 0 } } }
                    return acts[1], { acts = acts, expect = { { hp = 20 } },
                                      enemies = { [0x81] = true } }, { phases = 1, averaged = 0 }
                end
            end
            return nil, nil, { phases = 0, averaged = 0 }
        end,
    }
end
local function original()
    local g = fakeGame { units = rout(), enemy = deadly }
    local evs = {}
    g.api.Planner = attacker()
    g.api.trace = function(ev) evs[#evs + 1] = Json.decode(Json.encode(ev)) end
    Botrun.run(g.api)
    return evs
end
local function replay(diag, seen, tweak)
    local g = fakeGame { units = rout(), enemy = deadly }
    g.api.Planner = attacker(seen)
    g.api.diag = diag
    if tweak then tweak(g) end
    local ok, why, rec = Botrun.run(g.api)
    local diags, botruns = {}, 0
    for _, l in ipairs(g.emitted) do
        if l:sub(1, #Botrun.DIAG_PREFIX) == Botrun.DIAG_PREFIX then
            diags[#diags + 1] = Json.decode(l:sub(#Botrun.DIAG_PREFIX + 1))
        elseif l:sub(1, #Botrun.PREFIX) == Botrun.PREFIX then
            botruns = botruns + 1
        end
    end
    return diags, botruns, rec, g, ok, why
end
local failure = { charId = 0x01, turn = 1 }
local run = { game = "fake", chapter = 1, seed = 7, attempt = 1 }

-- test_a_diagnostic_writes_only_its_DIAG_line: no BOTRUN record, no record handed back (the
-- retry memory and the campaign's endpoint read it), one DIAG line
do
    local evs = original()
    local diags, botruns, rec = replay({ ref = 1, mode = "force", force = { "1>wait@0,1>nil" },
                                        failure = failure, run = run, original = evs })
    check(botruns, 0, "a diagnostic emits no BOTRUN record")
    check(rec, nil, "and hands no record back: no retry memory, no endpoint, no label")
    check(#diags, 1, "one DIAG line")
    local d = diags[1] or {}
    check(d.matched, true, "the replay matched the original trace up to the pinned decision")
    check(d.mode, "force", "the mode is named")
    check(d.ref, 1, "and the pinned decision")
    check(d.run and d.run.seed, 7, "and the original attempt's identity")
    check(d.baseline and d.baseline[1], "1>attack@0,0>129", "the baseline is the planner's plan")
    check(d.chosen and d.chosen[1], "1>wait@0,1>nil", "the forced plan was played")
    check(d.differs, true, "and it differs from the baseline")
    check(d.avoided, true, "standing off (0,0) avoids the turn-1 death")
    check(d.failure and d.failure.turn, 1, "the failure tested is named")
end

-- test_a_replay_that_leaves_its_original_is_unmatched: the original's turn-1 snapshot says A
-- had other HP, so the replay is not the same attempt: matched is false, said, never a witness
do
    local evs = original()
    for _, e in ipairs(evs) do
        if e.t == "phase" then e.units[1].hp = 19; break end
    end
    local seen = {}
    local diags, botruns = replay({ ref = 1, mode = "force", force = { "1>wait@0,1>nil" },
                                    failure = failure, run = run, original = evs }, seen)
    check(botruns, 0, "an unmatched diagnostic writes no record either")
    check(diags[1] and diags[1].matched, false, "a replay off its original is unmatched")
    check(diags[1] and diags[1].avoided, false, "and witnesses nothing")
    -- it stops at the first difference: the turn-1 snapshot, before any decision is asked for
    check(#seen, 0, "a replay that left its original plays on no further")
    check(diags[1] and diags[1].why:match("^unmatched") ~= nil, true, "and says why it stopped")
end

-- test_chosen_is_what_was_played: a forced plan whose second key has no unit to play it
-- (unit 3 is not on the field) is broken there; `chosen` holds only the act played
do
    local diags = replay({ ref = 1, mode = "force", force = { "1>wait@0,1>nil", "3>wait@4,4>nil" },
                           failure = failure, run = run, original = original() })
    local d = diags[1] or {}
    check(d.chosen and #d.chosen, 1, "chosen holds the acts played, not the forced list")
    check(d.chosen and d.chosen[1], "1>wait@0,1>nil", "the first forced act was played")
    check(d.broken, "3>wait@4,4>nil", "the key that could not be played is named")
end

-- test_a_forced_act_with_no_unit_witnesses_nothing: the replay stops at the pin, nothing was
-- played, so nothing was avoided
do
    local diags = replay({ ref = 1, mode = "force", force = { "3>wait@4,4>nil" },
                           failure = failure, run = run, original = original() })
    local d = diags[1] or {}
    check(d.avoided, false, "a forced plan never played avoids nothing")
    check(d.chosen and #d.chosen, 0, "and played nothing")
    check(d.broken, "3>wait@4,4>nil", "its key is named")
end

-- test_a_kept_act_builds_no_planner_memory: the memory a plan call reads (the lookahead budget
-- left: Planner.LOOK_ATTEMPT) is read only when the planner is asked, never for a kept act
do
    local g = fakeGame { units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x02, 1, "blue", 0, 5, 20),
                                   unit(0x81, 0, "red", 9, 9, 10) } }
    local reads, asked = 0, 0
    local P = { surprise = Planner.surprise, key = Planner.key, keysOf = Planner.keysOf }
    P.plan = function(_, board)
        asked = asked + 1
        for _, u in ipairs(board.units) do
            if u.faction == "blue" and u.acted then return nil, nil, {} end
        end
        if board.turn > 1 then return nil, nil, {} end
        local acts = { { unit = 0x01, unitId = 0x01, act = "wait", move = { x = 1, y = 0 } },
                       { unit = 0x02, unitId = 0x02, act = "wait", move = { x = 1, y = 5 } } }
        return acts[1], { acts = acts, expect = { { hp = 20 }, { hp = 20 } },
                          enemies = { [0x81] = true } }, {}
    end
    g.api.Planner = setmetatable(P, { __index = function(_, k)
        if k == "LOOK_ATTEMPT" then reads = reads + 1; return 0 end
    end })
    Botrun.run(g.api)
    local r = recordOf(g)
    check(r.plans.kept, 1, "one act was kept")
    check(reads, asked, "the planner's memory is built once per plan asked for, never for a kept act")
end

-- test_a_pinned_decision_never_reached_is_unmatched
do
    local diags = replay({ ref = 99, mode = "deep", failure = failure, run = run,
                           original = original() })
    check(#diags, 1, "a replay that never reaches its decision still says so")
    check(diags[1] and diags[1].matched, false, "unmatched")
end

-- test_deep_and_full_info_plan_from_the_same_decision: deep asks the planner with opts.diag;
-- full_info asks it inside sight.fullInfo, never inside a batch; each beside the baseline
do
    local seen = {}
    local diags = replay({ ref = 1, mode = "deep", failure = failure, run = run,
                           original = original() }, seen)
    check(table.concat(seen, ","):match("^baseline,deep") ~= nil, true,
          "the baseline, then the deep plan, at the same decision")
    check(diags[1] and diags[1].differs, false, "the same plan both ways does not differ")
    -- the pinned plan, played out, is no plan cut short (vanilla Ch6's live full_info replay
    -- crashed here, 2026-11-07)
    check(diags[1] and diags[1].outcome, "diag", "a played-out pinned plan replans cleanly")
    check(diags[1] and diags[1].broken, nil, "and is not broken")
    check(diags[1] and diags[1].avoided, false, "and does not avoid the death")
    local full, inBatch = 0, false
    local offeredOn, fullOffer
    seen = {}
    replay({ ref = 1, mode = "full_info", failure = failure, run = run, original = original() },
        seen, function(g)
            local sight = g.api.sight
            g.api.sight = function()
                local s = sight()
                local batching = false
                s.batch = function(fn)
                    batching = true
                    local out = table.pack(fn())
                    batching = false
                    return table.unpack(out, 1, out.n)
                end
                s.fullInfo = function(fn)
                    full = full + 1
                    inBatch = inBatch or batching
                    local b = g.api.board()
                    b.revealed = true   -- the fog-off board
                    return fn(b)
                end
                return s
            end
            -- which board the acts were offered on, and what the full_info plan was given
            local Bot0 = g.api.Bot
            g.api.Bot = setmetatable({ candidates = function(board, ...)
                offeredOn = offeredOn or {}
                offeredOn[#offeredOn + 1] = board.revealed and "revealed" or "fogged"
                return Bot0.candidates(board, ...)
            end }, { __index = Bot0 })
            local plan = g.api.Planner.plan
            g.api.Planner.plan = function(B, board, sgt, st, opts)
                if board.revealed then fullOffer = opts and opts.offer end
                return plan(B, board, sgt, st, opts)
            end
        end)
    check(full, 1, "full_info plans once inside sight.fullInfo")
    -- knowledge, not powers: the acts are the ones the fogged game allows; only the judging
    -- sees every enemy
    check(fullOffer ~= nil and fullOffer.cands ~= nil, true,
          "the full_info plan is given the acts offered on the fogged board")
    check(offeredOn and table.concat(offeredOn, ","), "fogged", "offered on the fogged board only")
    check(inBatch, false, "never inside a batch")
end

-- test_a_death_moved_onto_another_unit_is_not_avoided: the forced wait saves A, but the enemy
-- phase kills B instead; the failure's unit lives, yet nothing was avoided (ours-ch03 seed
-- 1002's force replay, 2026-11-07: unit 3 lived and unit 5 fell to the same boss)
do
    local function trade(g, find)
        local a, b = find(0x01), find(0x02)
        if g.turn ~= 1 then return {} end
        local v = (a.x == 0 and a.y == 0) and a or b
        v.hp, v.dead, v.onField = 0, true, false
        return { { id = v.id, charId = v.charId, faction = "blue", killer = 0x81 } }
    end
    local function units()
        local u = rout()
        u[#u + 1] = unit(0x02, 1, "blue", 5, 5, 20)
        return u
    end
    local g0 = fakeGame { units = units(), enemy = trade }
    local evs = {}
    g0.api.Planner = attacker()
    g0.api.trace = function(ev) evs[#evs + 1] = Json.decode(Json.encode(ev)) end
    Botrun.run(g0.api)
    local g = fakeGame { units = units(), enemy = trade }
    g.api.Planner = attacker()
    g.api.diag = { ref = 1, mode = "force", force = { "1>wait@0,1>nil" }, failure = failure,
                   run = run, original = evs }
    Botrun.run(g.api)
    local d = Json.decode(g.emitted[#g.emitted]:sub(#Botrun.DIAG_PREFIX + 1))
    check(d.matched, true, "the trade replay matched")
    check(d.traded and d.traded[1], 0x02, "B, lost in A's place, is named")
    check(d.avoided, false, "a death moved onto another unit is not avoided")
end

-- test_the_pinned_state_is_checked_by_loading_it_back: the state kept at the pinned decision,
-- loaded back, holds the board that decision read; one that does not is said
do
    local kept
    local function keeper(g, wrong)
        g.api.pinned = function(ref)
            kept = g.api.board()
            return "pinned-r" .. ref .. ".ss"
        end
        g.api.reload = function(file)
            check(file, "pinned-r1.ss", "the file the pin kept is the one loaded back")
            if wrong then kept.units[1].hp = 1 end
            return kept
        end
    end
    local diags = replay({ ref = 1, mode = "deep", failure = failure, run = run,
                           original = original() }, nil, function(g) keeper(g) end)
    check(diags[1] and diags[1].pinned_board, true, "the kept state holds the pinned board")
    diags = replay({ ref = 1, mode = "deep", failure = failure, run = run,
                     original = original() }, nil, function(g) keeper(g, true) end)
    check(diags[1] and diags[1].pinned_board, false, "a kept state off the pinned board is said")
end

-- test_a_pinned_check_reports_the_board_and_plays_nothing (PR-G T084): a suite snapshot's state,
-- loaded in a fresh emulator, reports the board it holds -- and the pin keeps the board its
-- decision read beside the state, for the check to be compared with
do
    local pinnedWith
    local diags = replay({ ref = 1, mode = "deep", failure = failure, run = run,
                           original = original() }, nil, function(g)
        g.api.pinned = function(ref, board) pinnedWith = board; return "pinned-r1.ss" end
    end)
    check(#diags, 1, "the replay still emits its DIAG line")
    check(pinnedWith and #pinnedWith > 0, true, "the pin is handed the decision's board")
    local g = fakeGame { units = rout() }
    local loaded
    g.api.check_pinned = "snap.ss"
    g.api.reload = function(file) loaded = file; return g.api.board() end
    local ok, why, rec = Botrun.run(g.api)
    check(loaded, "snap.ss", "the snapshot's own state is the one loaded")
    check(ok, false, "a pinned check is no run")
    check(rec, nil, "and hands no record back")
    check(#g.emitted, 1, "one line only: no BOTRUN record, no DIAG line")
    local line = g.emitted[1] or ""
    check(line:sub(1, #Botrun.PINNED_PREFIX), Botrun.PINNED_PREFIX, "the line is a PINNED line")
    local p = Json.decode(line:sub(#Botrun.PINNED_PREFIX + 1))
    check(p.file, "snap.ss", "naming the state")
    check(Json.encode(p.board), Json.encode(Botrun.snapshot(g.api.board())),
          "and carrying the board it holds, as the pin kept it")
    check(why ~= nil, true, "with why")
end

-- test_a_plan_event_carries_the_plans_audit (FR-020): what the planner offered, saw and spent
-- is in the trace, for `montecarlo.py audit` to read
do
    local g = fakeGame { units = rout() }
    local evs = {}
    local P = attacker()
    local plan = P.plan
    P.plan = function(...)
        local a, p, c = plan(...)
        if p then p.audit = { offered_n = 1, budget = { exhausted = false } } end
        return a, p, c
    end
    g.api.Planner = P
    g.api.trace = function(ev) evs[#evs + 1] = Json.decode(Json.encode(ev)) end
    Botrun.run(g.api)
    local audit
    for _, e in ipairs(evs) do
        if e.t == "plan" and e.ref == 1 then audit = e.audit end
    end
    check(audit and audit.offered_n, 1, "the plan event carries plan.audit")
end

-- test_a_lord_felled_by_our_own_act_is_a_loss (fwd1 A): the game runs its game-over event only
-- after the death quote, so the screen is not up when the act returns; the lord's death is the
-- game's word already.
do
    local function lordDies(done)
        local g = fakeGame { hit = 1, units = { unit(0x01, 0, "blue", 0, 0, 20),
                                                unit(0x81, 0, "red", 5, 5, 30) } }
        local sight = g.api.sight
        g.api.sight = function()
            local s = sight()
            s.objective.gameOver = { 0x01 }
            return s
        end
        local act, calls = g.api.act, 0
        g.api.act = function(a)
            calls = calls + 1
            if calls > 3 then error("the run played on after its lord fell") end
            act(a)
            local l = g.units[1]
            l.hp, l.dead, l.onField = 0, true, false
            return done
        end
        g.api.endPhase = function() error("the run ended its phase after its lord fell") end
        Botrun.run(g.api)
        return recordOf(g)
    end
    local r = lordDies(true)
    check(r.outcome, "lost", "a lord felled in the player phase: lost")
    check(r.why, "game over in the player phase", "a lord felled in the player phase: why")
    check(r.deaths[1] and r.deaths[1].phase, "player", "a lord felled in the player phase: the death")
    r = lordDies(false)
    check(r.outcome, "lost", "a lord felled by an act the harness lost track of: still lost")
end

-- test_a_recruit_a_script_removed_left_the_map (fwd1 A): the game's kills are api.killed()'s; a
-- red unit gone from the field without one was unloaded or escaped, and did not fall.
do
    local units = rout()
    units[#units + 1] = unit(0x30, 2, "red", 9, 0, 1)
    units[#units + 1] = unit(0x33, 3, "red", 9, 1, 1)
    local r = judged { units = units, recruits = { 0x30, 0x33 },
                       enemy = function(g, find)
                           if g.turn ~= 1 then return {} end
                           for i, u in ipairs(g.units) do             -- a script took it away
                               if u.id == 0x30 then table.remove(g.units, i); break end
                           end
                           local k = find(0x33)                       -- the game killed this one     
                           k.hp, k.dead, k.onField = 0, true, false
                           return {}
                       end }
    local why = {}
    for _, m in ipairs(r.missed_recruits) do why[m.charId] = m.reason end
    check(why[0x30], "left_map", "a recruit a script removed: left the map")
    check(why[0x33], "killed_before_talk", "a recruit the game killed: killed before the Talk")
    check(r.clean, false, "a recruit that left: the clear is not clean")
    -- a slot the watch could not read neither fell nor left
    units = rout()
    units[#units + 1] = unit(0x30, 2, "red", 9, 0, 1)
    local gone, told = false, false
    r = judged { units = units, recruits = { 0x30 },
                 enemy = function(g)
                     if g.turn ~= 1 then return {} end
                     table.remove(g.units, 3)
                     gone = true
                     return {}
                 end,
                 api = { killed = function()
                     if not gone or told then return {} end
                     told = true
                     return { { fault = "replaced", id = 0x30, charId = 0x30, faction = "red" } }
                 end } }
    check(r.missed_recruits[1].reason, "unknown", "a recruit the watch could not read: no guess")
    check(r.watch_faults[1] and r.watch_faults[1].why, "replaced", "and the fault is recorded")
end

-- test_a_slot_freed_without_a_kill_is_free_for_an_arrival (re-review of fwd1 A): a red unit
-- leaves the field unkilled after a plan's snapshot, an arrival loads into its slot under the
-- same generic charId and kills the unit that plan moved. The killer is no unit the plan saw.
do
    local g = fakeGame { units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x02, 1, "blue", 0, 2, 20),
                                   unit(0x81, 0, "red", 9, 9, 10) },
                         turnsLeft = 2,
                         enemy = function(g, find)
                             if g.turn == 1 then
                                 g.units[#g.units + 1] = unit(0x81, 4, "red", 1, 0, 10)
                                 local u = find(0x01)
                                 u.hp, u.dead, u.onField = 0, true, false
                             end
                             return {}
                         end }
    g.api.Planner = {
        -- one plan a player phase: kept until every blue unit has acted
        surprise = function()
            for _, u in ipairs(g.units) do
                if u.faction == "blue" and not u.acted and not u.dead then return nil end
            end
            return "the plan is played out"
        end,
        plan = function(_, board)
            local acts = {}
            for _, u in ipairs(board.units) do
                if u.faction == "blue" and not u.acted and not u.dead then
                    acts[#acts + 1] = { unit = u.charId, unitId = u.id, act = "wait",
                                        move = { x = u.x, y = u.y } }
                end
            end
            if not acts[1] then return nil end
            return acts[1], { acts = acts, expect = { { hp = 20 }, { hp = 20 } },
                              enemies = { [0x81] = true } }
        end,
    }
    local act = g.api.act
    g.api.act = function(a)
        if a.unitId == 0x02 then   -- while our second unit acts, a script takes the red away
            for i, u in ipairs(g.units) do
                if u.id == 0x81 then table.remove(g.units, i); break end
            end
        end
        return act(a)
    end
    g.api.killed = function()
        if g.turn ~= 2 or g.told then return {} end
        g.told = true
        return { { id = 0x01, charId = 0x01, faction = "blue", killer = 0x81, killerId = 0x81,
                   phase = "enemy" } }
    end
    Botrun.run(g.api)
    local d = recordOf(g).deaths[1]
    check(d and d.flags.reinforcement, true, "a freed slot: its arrival is no unit the plan saw")
end

-- test_a_protected_green_unit_felled_ends_the_run_lost (fwd1 A): the game's set of units it
-- ends on (Bot.gameOver) holds units of any side, and an enemy-phase kill of one is a loss even if
-- the phase came back to the player before the game-over screen.
do
    local units = standoff()
    units[#units + 1] = unit(0x41, 0, "green", 5, 5, 10)
    local g = fakeGame { units = units, turnsLeft = 5,
                         enemy = function(g, find)
                             local v = find(0x41)
                             v.hp, v.dead, v.onField = 0, true, false
                             return { { id = 0x41, charId = 0x41, faction = "green", killer = 0x81 } }
                         end }
    local sight = g.api.sight
    g.api.sight = function()
        local s = sight()
        s.objective.gameOver = { 0x41 }
        return s
    end
    Botrun.run(g.api)
    local r = recordOf(g)
    check(r.outcome, "lost", "a protected green felled: lost")
    check(r.why, "game over in the enemy phase", "a protected green felled: in the enemy phase")
    check(r.turns, 1, "a protected green felled: on the turn it fell")
    check(r.greens.escort_deaths[1], 0x41, "a protected green felled: the escort, as the game says")
end

-- test_the_record_counts_player_phases_and_hashes_the_acts (fwd1 A): two attempts that played
-- the same acts in the same order carry the same acts_hash, so a replay shows in the record.
do
    local function play(hit)
        local g = fakeGame { hit = hit, units = rout() }
        Botrun.run(g.api)
        return recordOf(g)
    end
    local a, b, c = play(5), play(5), play(10)
    check(a.team, nil, "the team pick: none without a campaign's prep screen")
    local g = fakeGame { units = rout() }
    g.api.info.team = { cap = 2, units = { { charId = 1, why = "forced" } } }
    Botrun.run(g.api)
    check(recordOf(g).team.units[1].why, "forced", "the team pick: the record carries it")
    check(a.player_phases, 2, "player phases: one per player phase played")
    check(c.player_phases, 1, "player phases: a one-phase win")
    check(type(a.acts_hash), "string", "acts hash: recorded")
    check(a.acts_hash, b.acts_hash, "acts hash: the same acts, the same hash")
    check(a.acts_hash ~= c.acts_hash, true, "acts hash: fewer acts, another hash")
    check(Botrun.actsHash(nil, { unit = 1, act = "wait", move = { x = 1, y = 2 } })
          ~= Botrun.actsHash(nil, { unit = 1, act = "wait", move = { x = 2, y = 1 } }), true,
          "acts hash: the tile counts")
    local function strike(id)
        return Botrun.actsHash(nil, { unit = 1, act = "attack", move = { x = 1, y = 2 },
                                      target = 0x81, targetId = id })
    end
    check(strike(0x90) ~= strike(0x91), true, "acts hash: two enemies of one charId are two targets")
end

print(string.format("%d tests, %d failures", tests, fails))
if fails > 0 then os.exit(1) end
