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
            local deaths = o.enemy and o.enemy(g, find) or {}
            for _, u in ipairs(g.units) do u.acted = false end
            g.turn = g.turn + 1
            if g.turnsLeft then g.turnsLeft = g.turnsLeft - 1 end
            if g.over then return "gameover", deaths end
            return "player", deaths
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

-- test_two_turn_rout_ends_won: A strikes E for 5 a turn; E has 10 HP.
do
    local g = fakeGame { units = rout() }
    local ok, why = Botrun.run(g.api)
    check(ok, true, "a won run is a finished run")
    local r = recordOf(g)
    check(r.outcome, "won", "the rout is won")
    check(r.turns, 2, "on turn 2")
    check(r.all_alive, true, "with everyone alive")
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
    check(r.all_alive, false, "nobody calls that all alive")
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
        plan = function(_, board)
            asked = asked + 1
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
    check(asked, 3, "turn 1: the plan and the played-out ask; turn 2: one ask, then stuck")
end

print(string.format("%d tests, %d failures", tests, fails))
if fails > 0 then os.exit(1) end
