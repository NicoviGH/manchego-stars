-- Tests for botrun.lua -- the bot playing one chapter (#510 step 9 PR D), over a fake game:
-- a board table the fake api moves and strikes on, so no emulator.
-- Run: lua tools/playtest/test_botrun.lua
local here = (arg[0]:match("(.*/)")) or "./"
local Botrun = dofile(here .. "botrun.lua")
local Json = dofile(here .. "json.lua")
local Bot = dofile(here .. "bot.lua")
local Board = dofile(here .. "board.lua")

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
        recruits = o.recruits,
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
                range = function(u) return { min = u.minRange, max = u.maxRange } end,
                canSeize = function() return true end,
                reach = function(u)
                    return within(u, u.faction == "blue" and (o.move or 3) or 0)
                end,
                attack = function(u, e)
                    local dmg = o.hit or 5
                    return { hit = 100, dmg = dmg, crit = 0, hits = 1, counters = false,
                             counterHit = 0, counterDmg = 0, counterCrit = 0, counterHits = 0,
                             killsTarget = dmg >= e.hp }
                end,
                strike = function()
                    return { takenHit = 0, takenDmg = 0, takenCrit = 0, takenHits = 0 }
                end,
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

-- test_explore_log: what became of each village and chest the run saw open -- ours, someone
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
                if u.faction == "blue" and u.acted then return nil end
            end
            if board.turn > 1 then return nil end
            local acts = { { unit = 0x01, unitId = 0x01, act = "wait", move = { x = 1, y = 0 } },
                           { unit = 0x02, unitId = 0x02, act = "wait", move = { x = 1, y = 5 } } }
            return acts[1], { acts = acts, expect = { { hp = 20 }, { hp = 20 } },
                              enemies = { [0x81] = true } }
        end,
    }
    Botrun.run(g.api)
    local r = recordOf(g)
    check(r.plans.kept, 1, "C's wait is played from A's plan")
    check(asked, r.plans.made, "every plan asked for is counted")
    check(asked, 4, "turn 1: the plan and the played-out ask; turn 2: one ask; turn 3 repeats "
          .. "turn 2's board: one stalled ask; turn 4 repeats it again: stuck")
    check(r.stalls, 1, "the first repeat is a stall, not stuck")
    check(g.stalledAsk, 4, "the stalled ask is told it is stalled")
    check(r.outcome, "stuck", "a board that comes round again after a stall is stuck")
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
    Botrun.run(g.api)
    return recordOf(g), g
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

-- test_a_razed_village_is_missing_at_once: a brigand's pick act names the village, and the
-- game stops offering it.
do
    local tiles = { { x = 9, y = 8, kind = "visit" } }
    local r = judged { explorable = tiles, enemy = function(g, find)
        if #tiles == 0 then return {} end
        table.remove(tiles, 1)
        return {}, { { id = 0x81, charId = 0x81, act = "pick", tile = { x = 9, y = 8 } } }
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
-- when blue, the drop reaches A through the full-bag menu (api.bag).
local function thiefGame(killer)
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
                table.remove(tiles, 1)
                t.items = { { id = 0x6C, uses = 1 } }
                return {}, { { id = 0x82, charId = 0x82, act = "pick", tile = { x = 9, y = 8 } } }
            elseif phase == 2 then
                t.hp, t.dead, t.onField = 0, true, false
                dropped = killer == 0x01
                return { { id = 0x82, charId = 0x82, faction = "red", killer = killer } }
            end
            return {}
        end }
    g.api.bag = function()
        if dropped then
            dropped = false
            return { { charId = 0x01, item = 0x6C, sent = 0x6C, discard = false, why = "full" } }
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
end

-- test_a_chest_thief_killed_by_green_is_lost
do
    local r = thiefGame(0x41)
    local m = r.clear.rewards_missing[1]
    check(m and m.closed_by, 0x82, "green kill: the chest is missing, closed by the thief")
    check(r.clean, false, "green kill: not clean")
end

-- test_no_recruit_list_leaves_clean_unjudged
do
    local g = fakeGame { units = rout() }
    Botrun.run(g.api)
    local r = recordOf(g)
    check(r.clear.recruits_missing, "unchecked", "no list: unchecked")
    check(r.clean, nil, "no list: not judged")
end

print(string.format("%d tests, %d failures", tests, fails))
if fails > 0 then os.exit(1) end
