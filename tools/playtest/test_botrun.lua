-- Tests for botrun.lua -- the bot playing one chapter (#510 step 9 PR D), over a fake game:
-- a board table the fake api moves and strikes on, so no emulator.
-- Run: lua tools/playtest/test_botrun.lua
local here = (arg[0]:match("(.*/)")) or "./"
local Botrun = dofile(here .. "botrun.lua")
local Json = dofile(here .. "json.lua")

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
                if math.abs(x - u.x) + math.abs(y - u.y) <= r then out[#out + 1] = { x = x, y = y } end
            end
        end
        return out
    end
    g.api = {
        info = { game = "fake", rom_hash = "abc", chapter = 1, mode = "normal", seed = 7 },
        style = { aggression = o.aggression or "careful", deploy = {}, claims = {} },
        claims = o.claims,
        seed = function(s) g.seeded = s end,
        board = copy,
        sight = function()
            return {
                cache = {},
                objective = { kind = o.kind or "rout", turnsLeft = g.turnsLeft },
                danger = function() return 0 end,
                reach = function(u) return within(u, u.faction == "blue" and (o.move or 3) or 0) end,
                forecast = function(u, e)
                    local dmg = o.hit or 5
                    return { hit = 100, dmg = dmg, crit = 0, hits = 1, takenHit = 0, takenDmg = 0,
                             takenCrit = 0, takenHits = 0, counters = false,
                             killsTarget = dmg >= e.hp, diesWorst = false }
                end,
            }
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
        log = function() end,
    }
    return g
end

local function recordOf(g)
    local line = g.emitted[#g.emitted]
    check(line and line:sub(1, #Botrun.PREFIX), Botrun.PREFIX, "one BOTRUN line is emitted")
    return Json.decode(line:sub(#Botrun.PREFIX + 1))
end

-- test_two_turn_rout_ends_won: A strikes E for 5 a turn; E has 10 HP.
do
    local g = fakeGame { units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x81, 0, "red", 1, 0, 10) } }
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
        units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x81, 0, "red", 9, 9, 10) } }
    local ok = Botrun.run(g.api)
    check(ok, true, "stuck is a finished run, not a crash")
    local r = recordOf(g)
    check(r.outcome, "stuck", "a repeated board ends the run")
    check(r.turns, 2, "at the first repeat")
end

-- test_survive_map_waiting_is_not_stuck: the same board, but the turns left fall each phase.
do
    local g = fakeGame { move = 0, kind = "survive", turnsLeft = 3,
        units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x81, 0, "red", 9, 9, 10) } }
    Botrun.run(g.api)
    local r = recordOf(g)
    check(r.outcome, "won", "holding until the turns run out wins")
    check(r.turns, 3, "after three phases")
end

-- An action the harness cannot perform is a crash, never a hang.
do
    local g = fakeGame { units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x81, 0, "red", 1, 0, 10) } }
    g.api.act = function() return false end
    local ok = Botrun.run(g.api)
    check(ok, false, "a controller fault is not a finished run")
    check(recordOf(g).outcome, "crashed", "it is recorded as crashed")
end

-- An action that leaves its unit able to act would be asked for again forever.
do
    local g = fakeGame { units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x81, 0, "red", 1, 0, 10) } }
    g.api.act = function() return true end
    Botrun.run(g.api)
    check(recordOf(g).outcome, "crashed", "a no-op action ends the run")
end

-- An enemy phase that never hands control back is a crash.
do
    local g = fakeGame { move = 0,
        units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x81, 0, "red", 9, 9, 10) } }
    g.api.endPhase = function() return nil, {} end
    Botrun.run(g.api)
    check(recordOf(g).outcome, "crashed", "a wedged enemy phase is recorded as crashed")
end

-- A claim kind the bot has no behaviour for is reported, never dropped.
do
    local g = fakeGame { claims = { { id = "t1", kind = "threat" } },
        units = { unit(0x01, 0, "blue", 0, 0, 20), unit(0x81, 0, "red", 1, 0, 10) } }
    Botrun.run(g.api)
    local r = recordOf(g)
    check(r.claims_unplayed[1], "t1", "the unplayed claim is in the record")
    check(#r.claims_played, 0, "and not among the played")
end

print(string.format("%d tests, %d failures", tests, fails))
if fails > 0 then os.exit(1) end
