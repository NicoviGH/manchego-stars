-- planner.lua -- the bot plans each player phase (#510 step 9; the plan comment's "The
-- planner"). Its own chunk, pure: no emu, SYM or harness global, so test_bot.lua drives it
-- with a fake sight.
--
-- One call plans the phase from the board as it stands (botrun calls it again after every act:
-- a receding horizon, so a miss, a kill or a newly seen enemy is planned around at once):
--   1. Propose: Bot.candidates -- per unit its attacks, breach, Talks, heal, Vulnerary, march,
--      hold, retreat, Seize, each read from the game, each with its end tile's exposure.
--   2. Search: a beam over which unit acts next and how. A partial plan is scored by expected
--      values from the game's forecasts: damage dealt, the chance to kill, the counter's chance
--      to kill our unit, HP healed, and what the plan does to every goal still open (goals.lua:
--      each one's worth x chance, the ground toward it, a Visit or Talk taking it, an attack
--      on a recruit losing it, the win closing the rest) -- less each moved unit's standing
--      exposure: its chance to die and the
--      HP it loses if every enemy that reaches its tile strikes it (an enemy the plan kills
--      does not; the HP is the plan's).
--      Without it the beam ranked only what a unit does, and every plan it kept was the
--      exposed one: the judge then had nothing safe to pick (ch03, 2026-10-27).
--   3. Judge: the best FINAL complete plans each meet the enemy phase the game's own AI would
--      play against them (sight.enemyPhase), which replaces the exposure estimate: they pay
--      for each unit's chance to die there (a green one's too: it spoils the clear; a recruit
--      our counter fells loses its goal; a unit whose death ends the game costs the chapter), its
--      expected damage, and a fog risk for a fragile unit left beside ground it cannot see.
--      Two more are judged beside them: on a Defeat Boss map the assault (every unit that
--      reaches the boss strikes it, heaviest first -- a combination the beam's per-unit cut
--      never tries), and on a stalled board (opts.stalled) each unit's best act that
--      changes the board, of which the best is played: a careful player that has stopped
--      making progress takes the least it must.
--      The enemy phase is played every way it can go where a counter may kill a striker
--      (its tile freed for the next), and once per way the plan's BRANCH most uncertain kills
--      can go (an enemy the average keeps may die, one it removes may live). Last, the best
--      plan is mended: each unit it may lose tries its other acts (a green one, the acts of
--      ours that could save it; a recruit, the acts of the units it strikes), the rest of the
--      plan kept, and those are judged too.
--   4. The best plan's first act is returned, and the plan with it: botrun plays the plan's
--      next act after each one unless M.surprise finds the board off what the plan expected
--      (a miss, a kill, a death, a newly seen enemy), and only then plans again. Judging is
--      most of a plan's cost, and an act that went as expected leaves the plan as good as it
--      was.
-- Honesty: outcomes are odds (each exchange played by the game every way its rolls can go,
-- sight.lua's `played`; several composed by sight.odds), never the game's next random numbers; an enemy the player cannot see is in no plan (Bot.candidates and
-- sight.enemyPhase skip it); the enemy's choices are the game's own AI.
-- Styles are weights (M.WEIGHTS): how much a unit's death costs against progress.
--
-- api: Planner.plan(Bot, board, sight, style, opts) -> the first act of the best plan
-- (bot.lua's action shape) or nil when no unit can act, and the plan's record { score, acts,
-- expect, enemies, judged, predict (each blue and green unit's phase; `green` marks one, and
-- `strikers` the ids of the enemies that strike it in the judged phase, sorted; and each
-- recruit our counter may kill: `recruit` marks one, `die` that chance, `struck` the ids of
-- ours it strikes, sorted), kind =
-- "beam"|"assault"|"unstall"|"mend", considered = every plan judged, best first: { judged,
-- acts, kind }, opts = { stalled = bool, sent, explored (both Bot.candidates') } | nil,
-- explore = every Visit and Chest offered: { id, charId, x, y, kind, die (its standing chance
-- to die), played, judgedDie (the judged phase's, when played) }, goals = the recruit, village
-- or chest each unit was sent to: { id, x, y }, goalWorth = what it does to each open goal
-- (goals.lua): { id, kind, gold, worth, before, after (its chance after the judged phase),
-- closes },
-- winFell = the judged phase's chance our counter ends the chapter }.
-- Planner.surprise(plan, k, before, after, legal)
-- -> why the board after its k-th act calls for a new plan, or nil to play act k + 1. legal
-- (optional) = sight.legal: the game no longer offering the next act ends the plan.

local M = {}

-- goals.lua, beside this file: the goals still open and their chance from a board
local Goals = dofile((debug.getinfo(1, "S").source:match("^@(.*/)") or "./") .. "goals.lua")

M.BEAM = 6         -- partial plans kept at each depth
M.PER_UNIT = 4     -- a unit's best acts, by their own score, that the beam tries (and its
                   -- hold and retreat, always: the way out survives the cut)
M.FINAL = 4        -- complete plans judged against the enemy phase
M.BRANCH = 2       -- a plan's uncertain kills the judge plays both ways (2^BRANCH enemy phases)
M.FOG_REACH = 6    -- unseen ground this close to a unit may hide what can strike it
M.BOSS_WORTH = 5   -- damage on a Defeat Boss map's boss, per point, against any other's

-- death: one unit's death; taken: per HP short at the phase's end; dealt: per HP; kill: per
-- enemy removed; heal: per HP restored; breach: a way opened; win: the game lost, for a unit
-- whose death ends it (a lord's); fog: a fragile unit beside the unseen; gold: points per gold
-- a goal is worth (goals.lua: under careful no item outweighs a life, under bold a good one
-- does). What each further turn to a goal leaves of its chance is goals.lua's GAMMA.
-- Ground toward a goal, a Visit, a Talk recruit and the win itself: the goals' term (goalTerm
-- below), the change a plan makes to each open goal's worth x chance. The win completes every
-- unit's way to the objective (one death's worth in all) and closes every other goal: a later
-- win is the same win, so it waits while what it would close is worth more than the waiting.
M.WEIGHTS = {
    careful = { death = 1000, taken = 2, dealt = 1, kill = 30, heal = 1.5, breach = 25,
                win = 100000, fog = 40, gold = 0.04 },
    even = { death = 300, taken = 1, dealt = 1, kill = 30, heal = 1, breach = 25,
             win = 100000, fog = 15, gold = 0.08 },
    bold = { death = 60, taken = 0.5, dealt = 1, kill = 40, heal = 0.5, breach = 25,
             win = 100000, fog = 0, gold = 0.15 },
}

-- `act`'s standing exposure for a unit at `hp`, the enemies in `gone` left out: the chance
-- it dies and the HP it loses if each enemy that reaches its tile strikes it.
local function exposed(act, hp, gone, odds)
    local strikes = {}
    for _, s in ipairs(act.exposure or {}) do
        if not gone[s.id] then strikes[#strikes + 1] = s.dist end
    end
    if #strikes == 0 then return 0, 0 end
    return odds(strikes, hp)
end

-- What losing unit `charId` costs: the chapter, for one whose death ends the game (its death
-- sets EVFLAG_GAMEOVER, a lord's: sight.objective.gameOver), else one unit's death.
local function loss(W, st, charId)
    return st.gameOver[charId] and W.win or W.death
end

-- An act's own score, given the partial plan `st` before it (enemy HP already taken, enemies
-- already counted gone). Returns the score and the act's effects on the plan.
local function score(act, st, W, style, odds)
    local fx = { hp = act.unitHp, gone = nil, enemyHp = nil }
    local v = 0
    if act.act == "attack" and act.f then
        local f, e = act.f, act.targetUnit
        -- the game played the exchange at the target's own HP; at the lower HP an earlier act
        -- of the plan leaves it, its damage is read capped there (the plan's HP is an average:
        -- design decision 5)
        local hp = st.enemyHp[e.id] or e.hp
        local kill, dealt = odds({ f.dealt }, hp)
        if st.recruits[e.id] then
            -- a recruit is talked over, not worn down: its damage earns nothing, and its death
            -- is its goal lost (the goals' term reads fx.recruitHit)
            fx.recruitHit = { id = e.id, p = kill }
        else
            -- the objective's boss: every point of its HP is a step to the win, as far as the
            -- win is wanted now (st.bossWant: 1 with nothing else left to get, near 0 with a
            -- rich goal open -- vanilla Ch5 attempt 8: a chip on the boss, credited five times,
            -- crit it dead with three villages open)
            local want = st.bossWant or 1
            local target = (e.isBoss and st.objective == "boss") and 1 + (M.BOSS_WORTH - 1) * want or 1
            local worth = (e.isBoss and 1 + 4 * want or 1) + (act.first and 1 or 0)
            v = v + W.dealt * dealt * target + W.kill * kill * worth
        end
        if f.counters then
            -- the counter's risk is its chance to kill (a target dead before it answers takes
            -- nothing: the game's play of the exchange); the HP it takes is paid once, at the
            -- end, after any heal the plan gives back (the judge's deficit)
            local die, taken = odds({ f.counterDist }, act.unitHp)
            v = v - loss(W, st, act.unit) * die
            fx.hp = math.max(1, act.unitHp - math.floor(taken + 0.5))
            -- the judge chains it with the enemy phase's strikes, so a counter that lands is
            -- not averaged away
            fx.counter = { f.counterDist }
        end
        fx.enemyHp = { id = e.id, hp = hp - dealt }
        -- what the blow does, for the judge to play the kill both ways (its odds composed with
        -- the plan's other blows on the target, at the target's own HP)
        fx.kill = { id = e.id, dist = f.dealt }
        if kill >= 0.5 then fx.gone = e.id end
        -- the boss's death is the win: its worth is the goals' (goalTerm), what it completes
        -- less what it closes, never a sum of its own, or no goal could ever wait for it
        if e.isBoss and st.objective == "boss" then fx.win = kill end
    elseif act.act == "talk" then
        -- the recruit joins us: it is off the enemy side, for the plan's later acts and for the
        -- judged phase, as a kill is; its goal is taken (the goals' term)
        fx.gone = act.targetId
        fx.took = "recruit:" .. act.targetId
    elseif act.act == "visit" or act.act == "chest" then
        -- the goal is taken; what it is worth against the risk there is the goals' term
        -- against the unit's exposure, by style
        fx.took = act.act .. ":" .. act.move.x .. "," .. act.move.y
    elseif act.act == "staff" and act.amount then
        -- a planned heal: what the target is short by now in the plan, up to the staff's amount.
        -- This is AddUnitHp's clamp to GetUnitMaxHp (sight.maxHps), applied here because the HP
        -- is the plan's, which no game state holds
        local t = act.targetUnit
        local hp = st.hp[t.id] or t.hp
        local gain = math.min(act.amount, (t.maxhp or hp) - hp)
        v = v + W.heal * gain
        fx.heals = { id = t.id, hp = hp + gain }
        -- the game offers Staff only on someone hurt: a heal before the blow is no act
        fx.blocked = gain <= 0
    elseif act.act == "item" and act.amount then
        -- a Vulnerary on the unit itself: what it is short by now in the plan (a heal earlier
        -- in it counts). FE8 refuses one at full HP (CanUnitUseHealItem), so then it is no act
        local hp = st.hp[act.unitId] or act.unitHp
        local gain = math.min(act.amount, act.unitMaxHp - hp)
        v = v + W.heal * gain
        fx.hp = hp + gain
        fx.heals = { id = act.unitId, hp = hp + gain }
        fx.blocked = gain <= 0
    elseif act.act == "staff" or act.act == "item" then
        v = v + W.heal * (act.gain or 0)
    elseif act.obstacle and act.obstacle.blow then
        -- a wall takes what the game's forecast of the strike deals (sight.strikeWall); one
        -- the plan has already broken is no act -- a second strike planned on it was a crash
        local at = act.obstacle.x .. "," .. act.obstacle.y
        local hp = st.walls[at] or act.obstacle.hp
        v = v + W.breach
        fx.wall = { at = at, hp = hp - act.obstacle.blow.dealt }
        fx.blocked = hp <= 0
    elseif act.obstacle or act.act == "door" then
        v = v + W.breach
    elseif act.act == "seize" then
        fx.win = 1   -- the win, scored as the boss's death is (goalTerm)
    end
    return v, fx
end

local function key(act)
    return string.format("%d>%s@%d,%d>%s", act.unitId, act.act, act.move.x, act.move.y,
        tostring(act.targetId or (act.obstacle and (act.obstacle.x .. "," .. act.obstacle.y))))
end

local function copy(t)
    local out = {}
    for k, v in pairs(t) do out[k] = v end
    return out
end

function M.plan(Bot, board, sight, style, opts)
    local W = M.WEIGHTS[style.aggression]
    if not W then error("planner.lua: no weights for style " .. tostring(style.aggression)) end
    local odds = sight.odds
    local cands, ctx = Bot.candidates(board, sight, style, opts)
    if #cands == 0 then return nil end
    local byId = {}
    for _, u in ipairs(board.units) do byId[u.id] = u end
    local objective = sight.objective and sight.objective.kind
    local gameOver = {}
    for _, c in ipairs(sight.objective and sight.objective.gameOver or {}) do gameOver[c] = true end
    local start = { score = 0, base = 0, acts = {}, expect = {}, used = {}, tiles = {},
                    gone = {}, enemyHp = {}, hp = {}, took = {}, recruitHit = {}, win = 0,
                    counter = {}, healed = {},
                    walls = {}, objective = objective, recruits = ctx.recruits or {},
                    gameOver = gameOver, kill = {} }

    -- Whether `id` ends an earlier act of the plan off the tile it stands on now. The game
    -- was asked which heals reach whom with every unit where it stands (sight.heals), so a
    -- heal on a unit the plan has moved has no answer behind it: the Staff command may not
    -- be there at all (ch03, 2026-10-27).
    local function moved(st, id)
        local u = byId[id]
        for _, x in ipairs(st.acts) do
            if x.unitId == id then return not u or x.move.x ~= u.x or x.move.y ~= u.y end
        end
        return false
    end

    -- The goals still open (goals.lua), and each one's chance on the board as it stands, every
    -- unit yet to act where it is: a plan earns what it changes of worth x chance. A march at
    -- full speed keeps a goal's chance, holding back loses a turn of it, a Visit or a Talk
    -- takes it; the win closes every other goal still open, so it costs what they were worth.
    local goals = Goals.list(board, sight, style, ctx)
    -- the goals' turns: the game's own, through the breach when a door or wall cuts a unit off
    local turnsTo = ctx.turnsTo
    local function positions(st, alive)
        local pos = {}
        for _, u in ipairs(ctx.blues) do
            pos[u.id] = { x = u.x, y = u.y, acted = u.acted, alive = alive and alive[u.id] or 1 }
        end
        for _, a in ipairs(st.acts) do
            local p = pos[a.unitId]
            if p then p.x, p.y, p.acted = a.move.x, a.move.y, true end
        end
        return pos
    end
    local before = {}
    do
        local pos = positions(start)
        for _, g in ipairs(goals) do before[g.id] = Goals.chance(g, pos, Goals.GAMMA, turnsTo) end
    end
    -- how much the win is wanted now: its worth now (one death x (1 - GAMMA), goalTerm's)
    -- against that and everything else still open, worth x chance (score's boss credit)
    do
        local open = 0
        for _, g in ipairs(goals) do
            if g.kind ~= "objective" then open = open + Goals.worth(g, W) * before[g.id] end
        end
        local now = W.death * (1 - Goals.GAMMA)
        start.bossWant = now / (now + open)
    end
    -- the chance a plan ends the chapter: a Seize or the boss's death (score's fx.win), or on
    -- a Rout map every enemy in sight gone
    local function winChance(st)
        if objective ~= "rout" then return st.win end
        if #ctx.enemies == 0 then return 0 end
        for _, e in ipairs(ctx.enemies) do
            if not st.gone[e.id] then return 0 end
        end
        return 1
    end
    -- `alive` (the judge's): each unit's chance to live the phase; `felled`: each recruit's
    -- chance our counter killed it; `fell`: the chance a counter of ours ended the chapter in
    -- the phase (the boss, or a Rout's last enemy, striking and dying: vanilla Ch5 attempt 8's
    -- boss died so on turn 5 with (5,1) still open); `rows` (optional) gets each goal's { id,
    -- kind, gold, worth, before, after }, the plan record's goalWorth
    local function goalTerm(st, alive, felled, rows, fell)
        local pos, v = positions(st, alive), 0
        local pWin = 1 - (1 - winChance(st)) * (1 - (fell or 0))
        for _, g in ipairs(goals) do
            local c
            if st.took[g.id] then
                c = 1
            elseif g.kind == "objective" then
                c = pWin + (1 - pWin) * Goals.chance(g, pos, Goals.GAMMA, turnsTo)
            else
                c = Goals.chance(g, pos, Goals.GAMMA, turnsTo) * (1 - pWin)
                if g.kind == "recruit" then
                    c = c * (1 - (st.recruitHit[g.unitId] or 0))
                        * (1 - (felled and felled[g.unitId] or 0))
                        * (alive and alive[g.unitId] or 1)
                end
            end
            v = v + Goals.worth(g, W) * (c - before[g.id])
            if rows then
                rows[#rows + 1] = { id = g.id, kind = g.kind, gold = g.gold,
                                    worth = Goals.worth(g, W), before = before[g.id], after = c,
                                    closes = g.closes }
            end
        end
        -- the win now rather than a turn later: one death's worth x (1 - GAMMA). With nothing
        -- left to get, a unit beside the boss whose way there is already sure would otherwise
        -- gain nothing by the kill and could idle there; it is less than any open goal's worth
        v = v + W.death * pWin * (1 - Goals.GAMMA)
        if rows then
            rows[#rows + 1] = { id = "win", kind = "win", gold = 0, worth = W.death,
                                before = Goals.GAMMA, after = pWin + (1 - pWin) * Goals.GAMMA }
        end
        return v
    end

    -- the beam's exposure term, memoised: the same act, HP and kills recur across the beam
    local risks = {}
    local function risk(a, hp, gone)
        local ids = {}
        for _, s in ipairs(a.exposure or {}) do
            if gone[s.id] then ids[#ids + 1] = s.id end
        end
        local k = key(a) .. "#" .. hp .. "#" .. table.concat(ids, ",")
        local r = risks[k]
        if not r then
            local die, taken = exposed(a, hp, gone, odds)
            r = loss(W, start, a.unit) * die + W.taken * taken
            risks[k] = r
        end
        return r
    end

    -- each unit's acts, its own best first (its score with what it does to the goals),
    -- PER_UNIT of them; every Visit and Chest offered,
    -- with its standing chance to die, for the run's trace (the rule's experiment)
    local menus, offered = {}, {}
    for _, c in ipairs(cands) do
        local scored = {}
        for _, a in ipairs(c.acts) do
            a.unitHp, a.unitMaxHp = c.unit.hp, c.unit.maxhp or c.unit.hp
            a.targetUnit = a.targetId and byId[a.targetId]
            if a.act == "visit" or a.act == "chest" then
                offered[#offered + 1] = { id = a.unitId, charId = a.unit, x = a.move.x,
                                          y = a.move.y, kind = a.act,
                                          die = (exposed(a, a.unitHp, {}, odds)) }
            end
            local v, fx = score(a, start, W, style, odds)
            local gone = fx.gone and { [fx.gone] = true } or {}
            -- what the act alone does to the goals: a march toward one earns nothing of its own,
            -- and ranked without this it was cut from the menu (vanilla Ch2: Eirika's walk to
            -- Ross never reached the beam, and Ross died on turn 4)
            local alone = { acts = { a }, took = fx.took and { [fx.took] = true } or {},
                            recruitHit = fx.recruitHit and { [fx.recruitHit.id] = fx.recruitHit.p } or {},
                            win = fx.win or 0, gone = gone }
            scored[#scored + 1] = { a = a, v = v - risk(a, fx.hp, gone) + goalTerm(alone) }
        end
        table.sort(scored, function(x, y)
            if x.v ~= y.v then return x.v > y.v end
            return key(x.a) < key(y.a)
        end)
        -- the PER_UNIT best by their own score, and every planned heal: a heal is worth
        -- nothing until a blow earlier in the plan gives it someone to restore
        local menu = {}
        for i, x in ipairs(scored) do
            if i <= M.PER_UNIT or (x.a.act == "staff" and x.a.amount)
                    or x.a.why == "hold" or x.a.why == "retreat" then
                menu[#menu + 1] = x.a
            end
        end
        menus[#menus + 1] = { unit = c.unit, acts = menu }
    end

    -- `st` with `a` (unit `uid`'s act) added, the board the plan leaves updated; nil when the
    -- act cannot follow the plan (its tile taken, its target gone, a heal on a moved unit or
    -- on no one hurt)
    local function extend(st, a, uid)
        local tile = a.move.x .. "," .. a.move.y
        if st.used[uid] or st.tiles[tile] or (a.targetId and st.gone[a.targetId])
                or (a.act == "staff" and moved(st, a.targetId))
                -- an ally's tile, until the plan has moved that ally off it
                or (a.vacate and not st.used[a.vacate]) then
            return nil
        end
        local v, fx = score(a, st, W, style, odds)
        if fx.blocked then return nil end
        local n = { base = st.base + v, acts = copy(st.acts), expect = copy(st.expect),
                    used = copy(st.used), tiles = copy(st.tiles), gone = copy(st.gone),
                    enemyHp = copy(st.enemyHp), hp = copy(st.hp), took = copy(st.took),
                    recruitHit = copy(st.recruitHit), win = st.win, bossWant = st.bossWant,
                    counter = copy(st.counter), healed = copy(st.healed), walls = copy(st.walls),
                    objective = objective, recruits = st.recruits, gameOver = st.gameOver,
                    kill = copy(st.kill) }
        n.acts[#n.acts + 1] = a
        -- what the board should show after it (M.surprise): a Talk or a kill takes its target
        -- off the enemy side (score's fx.gone)
        n.expect[#n.acts] = { hp = fx.hp, gone = fx.gone,
                              targetHp = fx.enemyHp and fx.enemyHp.hp, heals = fx.heals }
        n.used[uid], n.tiles[tile] = true, true
        n.hp[uid] = fx.hp
        if fx.gone then n.gone[fx.gone] = true end
        if fx.enemyHp then n.enemyHp[fx.enemyHp.id] = fx.enemyHp.hp end
        if fx.kill then
            local blows = copy(n.kill[fx.kill.id] or {})
            blows[#blows + 1] = fx.kill.dist
            n.kill[fx.kill.id] = blows
        end
        if fx.heals then
            n.healed[fx.heals.id] = (n.healed[fx.heals.id] or 0)
                + fx.heals.hp - (st.hp[fx.heals.id] or (byId[fx.heals.id] or {}).hp or fx.heals.hp)
            n.hp[fx.heals.id] = fx.heals.hp
        end
        if fx.counter then n.counter[uid] = fx.counter end
        if fx.took then n.took[fx.took] = true end
        if fx.recruitHit then
            n.recruitHit[fx.recruitHit.id] = math.max(n.recruitHit[fx.recruitHit.id] or 0,
                                                     fx.recruitHit.p)
        end
        if fx.win then n.win = math.max(n.win, fx.win) end
        if fx.wall then n.walls[fx.wall.at] = fx.wall.hp end
        -- every moved unit's exposure, again: a later kill or heal in the plan changes an
        -- earlier unit's
        n.score = n.base + goalTerm(n)
        for _, x in ipairs(n.acts) do
            n.score = n.score - risk(x, n.hp[x.unitId] or x.unitHp, n.gone)
        end
        return n
    end

    -- the beam: every depth, each plan extended by one more unit's act
    local beam = { start }
    for _ = 1, #menus do
        local nxt, seenSig = {}, {}
        for _, st in ipairs(beam) do
            for _, m in ipairs(menus) do
                for _, a in ipairs(m.acts) do
                    local n = extend(st, a, m.unit.id)
                    if n then
                        -- in order: a heal after a blow is not the heal before it
                        local sig = {}
                        for _, x in ipairs(n.acts) do sig[#sig + 1] = key(x) end
                        sig = table.concat(sig, "|")
                        if not seenSig[sig] then
                            seenSig[sig] = true
                            nxt[#nxt + 1] = n
                        end
                    end
                end
            end
        end
        if #nxt == 0 then break end
        table.sort(nxt, function(x, y)
            if x.score ~= y.score then return x.score > y.score end
            return key(x.acts[1]) < key(y.acts[1])
        end)
        -- the same acts in another order end on the same board: only the best order is kept,
        -- or the permutations of one plan fill the beam (ch02 turn 5: all four plans judged
        -- were one plan, and the only one left Marty to two Brigands)
        beam = {}
        local seenSet = {}
        for _, n in ipairs(nxt) do
            if #beam == M.BEAM then break end
            local set = {}
            for _, x in ipairs(n.acts) do set[#set + 1] = key(x) end
            table.sort(set)
            set = table.concat(set, "|")
            if not seenSet[set] then
                seenSet[set] = true
                beam[#beam + 1] = n
            end
        end
    end

    -- `st` with every unit it does not move holding: its safest hold tile still free
    local function complete(st)
        for _, c in ipairs(cands) do
            if not st.used[c.unit.id] then
                for _, a in ipairs(c.acts) do
                    local n = a.why == "hold" and extend(st, a, c.unit.id)
                    if n then st = n break end
                end
            end
        end
        return st
    end

    -- The assault (Nicolas, 2026-10-28): on a Defeat Boss map, every unit that can strike the
    -- boss this phase does, the heaviest expected blow first, until the plan counts it dead.
    -- One unit's strike alone rarely beats holding -- the counter, then the boss's own phase
    -- -- so the beam cuts it, and the combination is never tried; this plan is that
    -- combination, and the judge weighs it like any other. While too few units reach the boss
    -- it judges badly, and holding out of reach wins: the rounds of no combat while backup
    -- arrives.
    local function assault()
        local boss
        for _, e in ipairs(ctx.enemies) do
            if e.isBoss then boss = e end
        end
        if objective ~= "boss" or not boss then return nil end
        local strikers = {}
        for _, c in ipairs(cands) do
            local opts = {}
            for _, a in ipairs(c.acts) do
                if a.act == "attack" and a.targetId == boss.id and a.f then
                    local _, dealt = odds({ a.f.dealt }, boss.hp)
                    opts[#opts + 1] = { a = a, dealt = dealt }
                end
            end
            table.sort(opts, function(x, y)
                if x.dealt ~= y.dealt then return x.dealt > y.dealt end
                return key(x.a) < key(y.a)
            end)
            if #opts > 0 then strikers[#strikers + 1] = { uid = c.unit.id, opts = opts } end
        end
        if #strikers < 2 then return nil end   -- one striker is a plan the beam already has
        table.sort(strikers, function(x, y)
            if x.opts[1].dealt ~= y.opts[1].dealt then return x.opts[1].dealt > y.opts[1].dealt end
            return x.uid < y.uid
        end)
        -- each tile's takers; a striker takes, of its heaviest blows, the tile the fewest of
        -- those after it could use -- a 1-2 range unit leaves the boss's side to the melee
        local takers = {}
        for i, sk in ipairs(strikers) do
            for _, o in ipairs(sk.opts) do
                local t = o.a.move.x .. "," .. o.a.move.y
                takers[t] = takers[t] or {}
                takers[t][i] = true
            end
        end
        local function contention(t, after)
            local n = 0
            for j in pairs(takers[t]) do
                if j > after then n = n + 1 end
            end
            return n
        end
        for i, sk in ipairs(strikers) do
            local c = {}
            for _, o in ipairs(sk.opts) do c[o] = contention(o.a.move.x .. "," .. o.a.move.y, i) end
            table.sort(sk.opts, function(x, y)
                if x.dealt ~= y.dealt then return x.dealt > y.dealt end
                if c[x] ~= c[y] then return c[x] < c[y] end
                return key(x.a) < key(y.a)
            end)
        end
        local st = start
        for _, sk in ipairs(strikers) do
            if st.gone[boss.id] then break end
            for _, o in ipairs(sk.opts) do
                local n = extend(st, o.a, sk.uid)
                if n then st = n break end
            end
        end
        return complete(st)
    end

    -- whether a plan changes the board: any act but a wait on the unit's own tile
    local function changes(st)
        for _, a in ipairs(st.acts) do
            local u = byId[a.unitId]
            if a.act ~= "wait" or not u or a.move.x ~= u.x or a.move.y ~= u.y then return true end
        end
        return false
    end

    -- judge one complete plan against the enemy phase the AI would play
    local unseen = sight.unseen and sight.unseen() or {}
    -- a green unit lost spoils the clear as one of ours does (botrun's clean clear: vanilla
    -- Ch2's Ross, a Talk recruit, killed on turn 2 in every style while only blue deaths were
    -- paid), so the phase's strikes on one are paid at the same price. No plan moves one: it
    -- meets the phase where it stands
    local greens = {}
    for _, u in ipairs(ctx.onField) do
        if u.faction == "green" and not u.dead then greens[#greens + 1] = u end
    end
    local function judge(st)
        local planned, at = {}, {}
        for _, a in ipairs(st.acts) do at[a.unitId] = a end
        for _, u in ipairs(ctx.blues) do
            local a = at[u.id]
            planned[#planned + 1] = { unit = u, x = a and a.move.x or u.x, y = a and a.move.y or u.y,
                                      hp = st.hp[u.id] or u.hp,
                                      slot = a and a.act == "attack" and a.slot or nil }
        end
        local reds = {}
        for id, hp in pairs(st.enemyHp) do reds[id] = math.max(1, math.floor(hp + 0.5)) end
        -- the plan's BRANCH most uncertain kills, each played both ways: the average (an enemy
        -- gone at a kill >= 0.5, else standing at its mean HP) hides the way the rolls go
        -- otherwise (vanilla Ch5 turn 5: Eirika's attack killed an enemy the plan kept
        -- standing, and Joshua's AI turned on her). The rest keep the average.
        local open, gone = {}, copy(st.gone)
        for id, blows in pairs(st.kill) do
            -- the plan's blows on it together, at its own HP: each blow alone was scored at the
            -- HP the earlier ones leave on average, which can call a sure kill short. Gone or
            -- standing by that composed chance; `left`, the HP it keeps when it lives (the
            -- damage is capped at its HP, so the dead share is hp * p)
            local hp = byId[id].hp
            local p, mean = odds(blows, hp)
            gone[id] = p >= 0.5 or nil
            if p > 0 and p < 1 then
                open[#open + 1] = { id = id, p = p, left = hp - (mean - hp * p) / (1 - p) }
            end
        end
        table.sort(open, function(x, y)
            local dx, dy = math.abs(x.p - 0.5), math.abs(y.p - 0.5)
            if dx ~= dy then return dx < dy end
            return x.id < y.id
        end)
        local ways = { { p = 1, gone = gone, reds = reds } }
        for i = 1, math.min(M.BRANCH, #open) do
            local k, nxt = open[i], {}
            for _, w in ipairs(ways) do
                local dead, lives = copy(w.gone), copy(w.gone)
                dead[k.id], lives[k.id] = true, nil
                local hp = copy(w.reds)
                hp[k.id] = math.max(1, math.floor(k.left + 0.5))
                nxt[#nxt + 1] = { p = w.p * k.p, gone = dead, reds = w.reds }
                nxt[#nxt + 1] = { p = w.p * (1 - k.p), gone = lives, reds = hp }
            end
            ways = nxt
        end
        local strikes, outcomes, top = {}, {}, nil
        for _, w in ipairs(ways) do
            local s = sight.enemyPhase and sight.enemyPhase({ blues = planned, gone = w.gone,
                                                              reds = w.reds }) or {}
            for _, o in ipairs(s.outcomes or { { p = 1, strikes = s } }) do
                outcomes[#outcomes + 1] = { p = w.p * o.p, strikes = o.strikes }
            end
            if not top or w.p > top then strikes, top = s, w.p end
        end
        -- each unit's chance to die, HP lost and the strikes on it, over every way the phase went
        local judged = st.base
        local die, taken, short, struck = {}, {}, {}, {}
        local strikers = {}   -- per green unit, the enemies that strike it in any outcome
        for _, g in ipairs(greens) do strikers[g.id] = {} end
        -- per recruit, its chance our counter kills it (the phase's own `felled`) and the units
        -- of ours it strikes, whose other acts may save it (vanilla Ch5: Joshua, killed by
        -- Seth's counter on turn 3, the planner paying nothing for it)
        local felled, struckBy, fell, winStruck = {}, {}, 0, {}
        for _, o in ipairs(outcomes) do
            local onUnit = {}
            for _, s in ipairs(o.strikes) do
                onUnit[s.target] = onUnit[s.target] or {}
                table.insert(onUnit[s.target], s.takenDist)
            end
            for _, p in ipairs(planned) do
                local id = p.unit.id
                local phase = onUnit[id] or {}
                local d, t = odds(phase, p.hp)
                local back = st.counter[id]
                local sh = ((p.unit.maxhp or p.hp) - p.hp) + t
                if back then
                    -- the counter and the phase as one chain on the HP the unit had (and any
                    -- heal the plan gives it): the phase's share of the death is the chain's
                    -- less the counter's own, which score() already paid
                    local chain = {}
                    for _, x in ipairs(back) do chain[#chain + 1] = x end
                    for _, x in ipairs(phase) do chain[#chain + 1] = x end
                    local hp0 = p.unit.hp + (st.healed[id] or 0)
                    local all, lost = odds(chain, hp0)
                    d = math.max(0, all - (odds(back, hp0)))
                    sh = ((p.unit.maxhp or p.hp) - hp0) + lost
                end
                die[id] = (die[id] or 0) + o.p * d
                taken[id] = (taken[id] or 0) + o.p * t
                short[id] = (short[id] or 0) + o.p * sh
                struck[id] = math.max(struck[id] or 0, #phase)
            end
            for _, g in ipairs(greens) do
                local phase = onUnit[g.id] or {}
                local d, t = odds(phase, g.hp)
                die[g.id] = (die[g.id] or 0) + o.p * d
                taken[g.id] = (taken[g.id] or 0) + o.p * t
                struck[g.id] = math.max(struck[g.id] or 0, #phase)
            end
            -- the strikers our counters fell (felled): the boss, or a Rout's last enemy, is the win
            local left = 0
            if objective == "rout" then
                for _, e in ipairs(ctx.enemies) do
                    if not st.gone[e.id] then left = left + 1 end
                end
            end
            local lives = 1
            for _, s in ipairs(o.strikes) do
                local e = byId[s.enemy]
                if e and ((objective == "boss" and e.isBoss) or (objective == "rout" and left == 1)) then
                    lives = lives * (1 - (s.felled or 0))
                    if (s.felled or 0) > 0 then winStruck[s.target] = true end
                end
            end
            fell = fell + o.p * (1 - lives)
            for _, s in ipairs(o.strikes) do
                if strikers[s.target] then strikers[s.target][s.enemy] = true end
                if st.recruits[s.enemy] then
                    felled[s.enemy] = (felled[s.enemy] or 0) + o.p * (s.felled or 0)
                    struckBy[s.enemy] = struckBy[s.enemy] or {}
                    struckBy[s.enemy][s.target] = true
                end
            end
        end
        st.predict = {}
        for _, g in ipairs(greens) do
            judged = judged - loss(W, st, g.charId) * die[g.id]
            local by = {}   -- a list: the record is logged as JSON, whose keys are strings
            for id in pairs(strikers[g.id]) do by[#by + 1] = id end
            table.sort(by)
            st.predict[#st.predict + 1] = { id = g.id, charId = g.charId, x = g.x, y = g.y,
                                            hp = g.hp, die = die[g.id], taken = taken[g.id],
                                            strikes = struck[g.id], strikers = by,
                                            green = true }
        end
        local fallen = {}   -- in id order: the judged sum and the trace are the same every run
        for id, d in pairs(felled) do
            if d > 0 then fallen[#fallen + 1] = id end
        end
        table.sort(fallen)
        for _, id in ipairs(fallen) do
            local d, r, hit = felled[id], byId[id], {}
            for t in pairs(struckBy[id]) do hit[#hit + 1] = t end
            table.sort(hit)
            st.predict[#st.predict + 1] = { id = id, charId = r.charId, x = r.x, y = r.y,
                                            hp = st.enemyHp[id] or r.hp, die = d, taken = 0,
                                            strikes = 0, struck = hit, recruit = true }
        end
        for _, p in ipairs(planned) do
            local id = p.unit.id
            st.predict[#st.predict + 1] = { id = id, charId = p.unit.charId, x = p.x,
                                            y = p.y, hp = p.hp, die = die[id], taken = taken[id],
                                            strikes = struck[id] }
            -- the HP the phase leaves it short: the plan's own deficit, then the enemy's
            judged = judged - loss(W, st, p.unit.charId) * die[id] - W.taken * short[id]
            if W.fog > 0 then
                for _, t in ipairs(unseen) do
                    if math.abs(t.x - p.x) + math.abs(t.y - p.y) <= M.FOG_REACH then
                        judged = judged - W.fog * 10 / math.max(p.hp, 1)
                        break
                    end
                end
            end
        end
        -- the goals, as the phase leaves them: who lives to take each, and each recruit our
        -- counter may have felled (its goal lost)
        local alive = {}
        for _, p in ipairs(planned) do alive[p.unit.id] = 1 - (die[p.unit.id] or 0) end
        -- a green recruit the enemy may kill loses its goal as well (vanilla Ch2: Ross, at 0.37
        -- to die, was a 22-point risk to bold, and with him went Garcia, whom only he talks over)
        for _, g in ipairs(greens) do alive[g.id] = 1 - (die[g.id] or 0) end
        st.goalWorth = {}
        judged = judged + goalTerm(st, alive, felled, st.goalWorth, fell)
        st.winFell, st.winStruck = fell, winStruck
        st.judged = judged
        st.strikes = strikes
    end

    -- the plans judged: the beam's best, the assault, and on a stalled board (opts.stalled:
    -- botrun saw this board before and no turn event can change it) each unit's best act that
    -- changes the board, the rest holding -- and there only a plan that changes it is played
    local stalled = opts and opts.stalled
    local finals = {}
    for i = 1, math.min(M.FINAL, #beam) do finals[#finals + 1] = { st = beam[i], kind = "beam" } end
    local a = assault()
    if a then finals[#finals + 1] = { st = a, kind = "assault" } end
    if stalled then
        for _, c in ipairs(cands) do
            local pick
            for _, x in ipairs(c.acts) do
                if x.act ~= "wait" or x.move.x ~= c.unit.x or x.move.y ~= c.unit.y then
                    local n = extend(start, x, c.unit.id)
                    if n and (not pick or n.score > pick.score) then pick = n end
                end
            end
            if pick then finals[#finals + 1] = { st = complete(pick), kind = "unstall" } end
        end
    end
    local best
    -- every plan judged, for the run's trace: its acts, its score and where it came from
    local considered = {}
    local function consider(st, kind)
        judge(st)
        st.kind = kind
        local keys = {}
        for _, x in ipairs(st.acts) do keys[#keys + 1] = key(x) end
        considered[#considered + 1] = { judged = st.judged, acts = keys, kind = kind }
        if (not stalled or changes(st)) and (not best or st.judged > best.judged) then best = st end
    end
    for _, f in ipairs(finals) do consider(f.st, f.kind) end
    -- the best plan judged, mended where the judge finds it may lose someone: each such unit,
    -- the likeliest to die first, tries every other act of its menu, the rest of the plan kept
    -- where it still fits. The beam ranks acts by their own score, so a plan where one unit
    -- steps elsewhere for its own sake can lose to that unit's best act in every slot (ch02
    -- turn 5: the four plans judged all left Marty to two Brigands). A green unit has no menu:
    -- it tries instead the acts of ours that could save it, one ending beside it (a block) or
    -- striking an enemy that strikes it. A recruit our counter may kill tries the acts of the
    -- units it strikes.
    if best then
        local base, menuOf, risky = best, {}, {}
        for _, m in ipairs(menus) do
            local mine = {}
            for _, a in ipairs(m.acts) do mine[#mine + 1] = { uid = m.unit.id, a = a } end
            menuOf[m.unit.id] = mine
        end
        local function tries(p)
            if p.recruit then
                -- a recruit has no menu of ours: the units it strikes try theirs (out of its
                -- reach, or holding no weapon that answers it)
                local out = {}
                for _, id in ipairs(p.struck) do
                    for _, t in ipairs(menuOf[id] or {}) do out[#out + 1] = t end
                end
                return out
            end
            if not p.green then return menuOf[p.id] or {} end
            local striker, out = {}, {}
            for _, id in ipairs(p.strikers) do striker[id] = true end
            for _, m in ipairs(menus) do
                for _, a in ipairs(m.acts) do
                    if Bot.distance(a.move.x, a.move.y, p.x, p.y) == 1
                        or (a.act == "attack" and a.targetId and striker[a.targetId]) then
                        out[#out + 1] = { uid = m.unit.id, a = a }
                    end
                end
            end
            return out
        end
        for _, p in ipairs(base.predict) do
            if p.die > 0 then risky[#risky + 1] = p end
        end
        -- a unit of ours whose counter may end the chapter (the boss striking it and dying)
        -- tries its other acts too: the beam cannot see that counter, so every plan it kept
        -- had Seth strike the boss and stand beside it (vanilla Ch5 attempt 8, turn 5)
        local struckIds = {}
        for id in pairs(base.winStruck or {}) do struckIds[#struckIds + 1] = id end
        table.sort(struckIds)
        for _, id in ipairs(struckIds) do
            if menuOf[id] then risky[#risky + 1] = { id = id, die = base.winFell } end
        end
        table.sort(risky, function(x, y)
            if x.die ~= y.die then return x.die > y.die end
            return x.id < y.id
        end)
        -- each act tried once: two greens side by side, or a blue at risk beside a green, offer
        -- the same one again, and each try plays a whole enemy phase
        local mine, tried = {}, {}
        for _, a in ipairs(base.acts) do mine[a.unitId] = key(a) end
        for _, p in ipairs(risky) do
            for _, t in ipairs(tries(p)) do
                local k = key(t.a)
                local st = k ~= mine[t.uid] and not tried[k] and extend(start, t.a, t.uid)
                tried[k] = true
                if st then
                    for _, x in ipairs(base.acts) do
                        if x.unitId ~= t.uid then st = extend(st, x, x.unitId) or st end
                    end
                    consider(complete(st), "mend")
                end
            end
        end
    end
    if not best or #best.acts == 0 then return nil end
    table.sort(considered, function(x, y) return x.judged > y.judged end)
    best.considered = considered
    -- the rule's record: each Visit or Chest offered, and whether the plan played it credited
    -- (its standing chance 0 and the judged phase's 0 too)
    for _, o in ipairs(offered) do
        for _, a in ipairs(best.acts) do
            if a.unitId == o.id and a.act == o.kind and a.move.x == o.x and a.move.y == o.y then
                o.played = true
                for _, p in ipairs(best.predict) do
                    if p.id == o.id then o.judgedDie = p.die end
                end
            end
        end
    end
    best.explore = offered
    -- the recruit, village or chest each unit was sent to (Bot.candidates' exploring), by unit id
    best.goals = {}
    for id, t in pairs(ctx.exploreGoal or {}) do
        best.goals[#best.goals + 1] = { id = id, x = t.x, y = t.y }
    end
    table.sort(best.goals, function(a, b) return a.id < b.id end)
    best.enemies = {}
    for _, e in ipairs(ctx.enemies) do best.enemies[e.id] = true end
    return best.acts[1], best
end

-- Why the board `after` the plan's k-th act (played from `before`) is off what the plan
-- expected, so the rest of it was planned for a board that is not there; nil when act k + 1
-- may be played as planned. An enemy the game hides in fog (`fogged`, US_BIT9) is not in sight;
-- `legal(act, unit)` is sight.legal, the game's own word on whether the next act is offered.
-- Taking LESS from a counter, or dealing more without a kill, is no surprise: the plan
-- reckoned with worse.
function M.surprise(plan, k, before, after, legal)
    local a, x, nxt = plan.acts[k], plan.expect[k], plan.acts[k + 1]
    if not (a and x and nxt) then return "the plan is played out" end
    local now = {}
    for _, u in ipairs(after.units) do
        if u.onField and not u.dead then now[u.id] = u end
    end
    for _, u in ipairs(before.units) do
        if u.faction == "blue" and u.onField and not u.dead and not now[u.id] then
            return "a unit of ours fell"
        end
    end
    local actor = now[a.unitId]
    if actor and (actor.x ~= a.move.x or actor.y ~= a.move.y) then return "the move ended short" end
    if actor and x.hp and actor.hp < x.hp then return "the counter took more than expected" end
    -- the enemy side: the plan's enemies, less every kill and Talk it expected by now
    local gone = {}
    for i = 1, k do
        if plan.expect[i].gone then gone[plan.expect[i].gone] = true end
    end
    for _, u in pairs(now) do
        if u.faction == "red" and not plan.enemies[u.id] and not u.fogged then
            return "an enemy came into sight"
        end
    end
    for id in pairs(plan.enemies) do
        local e = now[id]
        local alive = e ~= nil and e.faction == "red"
        if gone[id] and alive then return "the kill missed" end
        if not gone[id] and not alive then return "an unexpected kill" end
    end
    local t = a.act == "attack" and now[a.targetId]
    if t and x.targetHp and t.hp > x.targetHp + 0.5 then return "a blow missed" end
    local h = x.heals and now[x.heals.id]
    if h and h.hp < x.heals.hp then return "the heal fell short" end
    -- the next act must still be there to play, and the game must still offer it: a kept act
    -- is played on the game's word, never the plan's (a wall an earlier blow broke, a door
    -- already opened, a heal whose counter missed: each crashed a run when it was not asked)
    local u = now[nxt.unitId]
    if not u or u.acted then return "the next unit cannot act" end
    return legal and legal(nxt, u) or nil
end

return M
