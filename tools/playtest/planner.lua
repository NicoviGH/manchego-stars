-- planner.lua -- the bot plans each player phase (#510 step 9; the plan comment's "The
-- planner"). Its own chunk, pure: no emu, SYM or harness global, so test_bot.lua drives it
-- with a fake sight.
-- How a decision here is written (ADR 0396): an ordering of the game's outcomes, never a ban,
-- except one the game itself makes; a new rule passes that record's five tests first.
--
-- One call plans the phase from the board as it stands (botrun calls it again after every act:
-- a receding horizon, so a miss, a kill or a newly seen enemy is planned around at once):
--   1. Propose: Bot.candidates -- per unit its attacks, breach, Talks, Rescues and Drops, heal,
--      Vulnerary, march, hold, retreat, Seize, each read from the game, each with its end
--      tile's exposure.
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
--      expected damage. A unit left beside ground it cannot see also meets one strike from the
--      strongest enemy seen so far, stood at the fog's edge: its own rank key, not its chance
--      to die (M.outranks' `fog`).
--      The plans are then ranked, not summed (ADR 0384): one whose protected units (every
--      blue, and any unit whose death ends the game) each die at no more than the style's cap
--      (M.CAPS) outranks any that does not. With none under it, the one least likely to end
--      the game is played, then the least over the cap, and it is labelled. Under the cap,
--      the plan that forfeits fewer goals for good (the completion ledger, goals.lua), then
--      the likelier win, then the more turns gained toward each unit's goal, then the judged
--      score.
--      More are judged beside them: on a Defeat Boss map the assault (every unit that
--      reaches the boss strikes it, heaviest first -- a combination the beam's per-unit cut
--      never tries), the advance (each unit's act that gains the most ground toward its goal,
--      which the beam's judged score can cut while the rank puts it first), and on a stalled
--      board (opts.stalled) each unit's best act that
--      changes the board, of which the best is played: a careful player that has stopped
--      making progress takes the least it must.
--      The enemy phase is played every way it can go where a counter may kill a striker
--      (its tile freed for the next), and once per way each uncertain kill can go, up to
--      BRANCH of them (an enemy the average keeps may die, one it removes may live). Last, the
--      best plan is mended: each unit it may lose tries its other acts (a green one, the acts
--      of the player units that could save it; a recruit, the acts of the units it strikes), the
--      rest of the plan kept, and those are judged too. At an irreversible transition (M.triggers:
--      a door opened or a wall struck, a first step into a seen boss's reach) the best M.FINAL
--      plans each meet a second enemy phase, our units holding between (sight.nextPhase): all of
--      them or none, within M.LOOK_DECISION calls a decision and opts.budget.attempt left of
--      M.LOOK_ATTEMPT, else skipped and tagged. Each protected unit's death chance becomes
--      that of dying in either phase, and those plans are ranked again among themselves.
--   4. The best plan's first act is returned, and the plan with it: botrun plays the plan's
--      next act after each one unless M.surprise finds the board off what the plan expected
--      (a miss, a kill, a death, a newly seen enemy), and only then plans again. Judging is
--      most of a plan's cost, and an act that went as expected leaves the plan as good as it
--      was.
-- Honesty: outcomes are odds (each exchange played by the game every way its rolls can go,
-- sight.lua's `played`; several composed by sight.odds), never the game's next random numbers; an enemy the player cannot see is in no plan (Bot.candidates and
-- sight.enemyPhase skip it); the enemy's choices are the game's own AI.
-- Styles are a risk cap each (M.CAPS), and weights (M.WEIGHTS) that order the beam and the plans
-- under the cap: how much a unit's death costs against progress.
--
-- api: Planner.plan(Bot, board, sight, style, opts) -> the first act of the best plan
-- (bot.lua's action shape) or nil when no unit can act, and the plan's record { score, acts
-- (an attack act carries `die`: its counter's chance to kill the attacker),
-- expect, enemies, judged, predict (each blue and green unit's phase; `green` marks one, `fog`
-- the fog read's chance to kill a blue one, on the played plan only (Bot.fogRead); and
-- `strikers` the ids of the enemies that strike it in the judged phase, sorted; and each
-- recruit our counter may kill: `recruit` marks one, `die` that chance, `struck` the ids of
-- player units it strikes, sorted), kind = "beam"|"assault"|"advance"|"unstall"|"mend"|"rest",
-- considered = every plan judged, best first: { judged, acts (its key list, M.keysOf), kind, rank,
-- seizes, extended (it met the lookahead's second phase), played (the one played), rejected (why
-- not: "over_cap", "outranked", "stalled"), weights (its judged phase's likeliest ways' chances) },
-- rank = what plans are compared by (M.outranks): { admitted,
-- forfeits (how many ledger goals it closes for good), complete (its chance to end the
-- chapter), progress (the turns it cuts from each unit's way to its goal, summed), behind
-- (whole turns short of the most progress judged), green_die (allied greens' summed death
-- chance), value (the judged score), game_over (the chance a unit whose death ends the game
-- dies), max_exceed, sum_exceed, max_die, sum_die, hp_left, fog (the fog read's summed
-- chance to kill, where the chapter goes on), key }, forfeited = the ids it
-- closes, ledger = Goals.ledger's rows as the plan leaves them (what it forfeits `closed`),
-- seizeJudged / seizeAdmitted = whether any plan judged took the Seize, and one within the
-- cap, stuck = Bot.candidates' record of the goals units are blocked from, fallback =
-- "FALLBACK_SACRIFICE" when no plan was under the cap, protected = each protected unit's
-- { id, charId, die, branches = { { p, die } } per way the judged phase went, cap, second (the
-- lookahead's second phase's chance, when extended; `die` then counts both) }, lookahead =
-- { trigger = the kinds M.triggers found | nil, extended, skipped, calls, deep }, audit = the
-- failure audit's (FR-020): { offered_n = how many acts Bot.candidates offered, mend_rounds =
-- { before, now } (whether a plan judged without the mend's later rounds was under the cap,
-- and whether the played one is: #510 PR A), visibility =
-- { seen, fogged } (the red units on the field), budget = { exhausted (the lookahead skipped),
-- averaged } }, branched
-- = the uncertain kills its judged phase played both ways, averaged = the ones past BRANCH left
-- to the average, opts = { stalled = bool, sent, explored (both Bot.candidates') } | nil,
-- explore = every Visit and Chest offered: { id, charId, x, y, kind, die (its standing chance
-- to die), played, judgedDie (the judged phase's, when played) }, goals = the recruit, village
-- or chest each unit was sent to: { id, x, y }, goalWorth = what it does to each open goal
-- (goals.lua): { id, kind, gold, worth, before, after (its chance after the judged phase),
-- closes },
-- winFell = the judged phase's chance our counter ends the chapter, talks = the charIds any
-- unit was offered a Talk to, sorted, seizable = whether any unit was offered the Seize,
-- seizes = whether this plan takes it }, and what the call cost, over every plan it judged (a
-- call that finds no plan judged some too): { phases (the enemy phases judged), averaged (the
-- uncertain kills left to the average past BRANCH), look = { decisions, triggered, extended,
-- skipped_budget, calls, cpu_s } (the lookahead's; absent when no unit can act) }.
-- opts.budget = { decision, attempt } (optional): the lookahead calls this decision may spend.
-- opts.seen = unit slot -> charId, every red a board showed out of fog this attempt (optional,
-- botrun's): the fog rule's strongest enemy is one of these; without it, one in sight.
-- opts.rest = the act keys (M.key) of the plan in hand not yet played (optional; botrun's on a
-- replan): judged as one more plan, kind "rest", its acts as this board still offers them.
-- opts.diag = "deep" (a diagnostic replay's, FR-019): every decision's finalists meet the
-- lookahead's second phase, no trigger or budget asked. A forced plan is botrun's (its acts
-- may be ones no candidate offered: M.unkey reads its keys); "full_info" is sight.fullInfo
-- around the call, with opts.offer = { cands, ctx } (Bot.candidates on the fogged board, read
-- before it): the acts the fogged game allows, judged with every enemy seen.
-- Planner.surprise(plan, k, before, after, legal)
-- -> why the board after its k-th act calls for a new plan, or nil to play act k + 1. legal
-- (optional) = sight.legal: the game no longer offering the next act ends the plan.

local M = {}

-- goals.lua, beside this file: the goals still open and their chance from a board
local Goals = dofile((debug.getinfo(1, "S").source:match("^@(.*/)") or "./") .. "goals.lua")
-- board.lua, as bot.lua loads it: Board.endTile, where an act leaves its unit (a Canto move)
local Board = dofile(PLAYTEST_DIR and (PLAYTEST_DIR .. "/board.lua")
    or ((debug.getinfo(1, "S").source:match("^@(.*/)") or "./") .. "board.lua"))
local endTile = Board.endTile

M.BEAM = 6         -- partial plans kept at each depth
M.PER_UNIT = 4     -- a unit's best acts, by their own score, that the beam tries (and its
                   -- hold and retreat, always: the way out survives the cut)
M.FINAL = 4        -- complete plans judged against the enemy phase
M.MEND_ROUNDS = 3  -- the mend's rounds; past the first, only while no plan is under the cap
-- the uncertain kills the judge plays both ways (2^n enemy phases), so a protected unit's death
-- chance is a sum over the ways the phase can go, never read off an average that keeps a
-- likely kill gone (FR-009). Even an enemy that reaches no one is played both ways: its death
-- can free a tile for one that does (test_planner_plays_an_uncertain_kill_both_ways). This
-- many at most, so a board of uncertain kills cannot cost thousands of phases a plan: past
-- it, the most uncertain are branched and the plan records how many it left to the average
-- (`averaged`). ADR 0384 has the cost.
M.BRANCH = 8
M.AUDIT_WAYS = 4  -- the judged phase's ways whose chances a plan's audit record keeps
M.BOSS_WORTH = 5   -- damage on a Defeat Boss map's boss, per point, against any other's

-- death: one unit's death; taken: per HP short at the phase's end; dealt: per HP; kill: per
-- enemy removed; heal: per HP restored; breach: a way opened; win: the game lost, for a unit
-- whose death ends it (a lord's); gold: points per gold
-- a goal is worth (goals.lua: under careful no item outweighs a life, under bold a good one
-- does). What each further turn to a goal leaves of its chance is goals.lua's GAMMA.
-- Ground toward a goal, a Visit, a Talk recruit and the win itself: the goals' term (goalTerm
-- below), the change a plan makes to each open goal's worth x chance. The win completes every
-- unit's way to the objective (one death's worth in all) and closes every other goal: a later
-- win is the same win, so it waits while what it would close is worth more than the waiting.
M.WEIGHTS = {
    careful = { death = 1000, taken = 2, dealt = 1, kill = 30, heal = 1.5, breach = 25,
                win = 100000, gold = 0.04 },
    even = { death = 300, taken = 1, dealt = 1, kill = 30, heal = 1, breach = 25,
             win = 100000, gold = 0.08 },
    bold = { death = 60, taken = 0.5, dealt = 1, kill = 40, heal = 0.5, breach = 25,
             win = 100000, gold = 0.15 },
}

-- The most predicted death chance a style accepts for any protected unit in a plan (ADR 0384,
-- FR-010): fixed, never drawn, so a pinned run reproduces exactly. A plan over it never
-- outranks one under it, whatever it gains: a weight can be outbid, a cap cannot.
M.CAPS = { careful = 0.01, even = 0.05, bold = 0.15 }

-- Whether death chance `d` is within `cap`: a sum of branch products can land a few ulps over a
-- chance that is at the cap, and that is not an excess.
M.DUST = Goals.DUST
-- the lookahead's budget (FR-018): extra judged calls (sight.nextPhase, one a finalist) per
-- decision and per attempt. 128 an attempt, not 32: 32 ran out before the boss fight on
-- Manchego Stars ch03 and two vanilla starts, so the decisive turns were judged one phase deep
-- (#570)
M.LOOK_DECISION = 8
M.LOOK_ATTEMPT = 128
-- the look's enemy phases (#510 W1, a trade's: the next one, our turn, the one after)
M.LOOK_DEPTH = 2
function M.admits(d, cap) return d <= cap + M.DUST end

-- Whether complete plan rank `a` ranks before `b` (ADR 0384, FR-011 to FR-013). Admission
-- first. Over the cap, the smaller chance of a game over first: a lord's death is no risk
-- among others, it ends the chapter (Nicolas, 2026-11-01); then the smallest largest excess,
-- then summed excess, then largest death chance. Each of those is read on the next enemy
-- phase first (`first_*`) and on both phases only to break its ties: the lookahead's second
-- phase has our units stand still another round, and over Manchego Stars ch03's pilots its readings
-- came true 0 of 8 times where the next phase's were about right, so ranking by both let a
-- unit be sent to an 82% death to dodge another's second-phase 90% (ADR 0389, amended
-- 2026-11-08; careful seed 3010 turn 18, replayed). Then the admitted order: fewer goals forfeited
-- (the completion ledger's), the likelier win, more progress. Allied greens' summed death
-- chance breaks ties among the plans within a turn of the most progress judged (FR-012: only
-- there, and never ahead of a forfeit or the win): `behind`, the whole turns a plan's progress
-- is short of the best's, comes first, then the greens. Measured from the best rather than
-- between each two plans, it is an order a sort can keep: "within a turn of each other" is
-- not one (0, 0.8 and 1.6 would each tie their neighbour). `behind` is set by M.plan once
-- every plan is judged (M.rebase). Then the progress itself, then `value`, the judged score:
-- what a plan deals, kills, heals and loses in HP (Nicolas, 2026-11-02: without it a unit
-- within the cap never chips an enemy it cannot kill this turn, as the counter's HP is all
-- the rank would see). The score after the progress, so a unit chips, heals or kills only
-- from as forward a tile as its march: the advisory panel's decision, on Nicolas's
-- instruction (ADR 0384's amendment of 2026-11-02, research record 0024, which has the
-- numbers; why the reverse order lost more units is open, #565). Then the fog (#510 PR A step
-- 4): the summed chance the fog's strike kills a unit, on the ways the plan does not end the
-- chapter (Bot.fogRead), less first. A tie-breaker only: inside the cap it froze the bot on
-- Ch6, and ranked right after admission it held the army back from the fog until the Bael
-- reached the Civilians (#510 comments 6780781911, 6781704202); a first attempt cannot know
-- what the fog hides, a retry can (PR B). Last the largest death chance, the summed one, more
-- HP left, and the acts as a stable key.
local ADMITTED = { { "forfeits", 1 }, { "complete", -1 }, { "behind", 1 },
                   { "green_die", 1 }, { "progress", -1 }, { "value", -1 } }
function M.outranks(a, b)
    if a.admitted ~= b.admitted then return a.admitted end
    local order = { { "fog", 1 }, { "max_die", 1 }, { "sum_die", 1 }, { "hp_left", -1 },
                    { "key", 1 } }
    local lead = {}
    if not a.admitted then
        lead = { { "first_game_over", 1 }, { "first_max_exceed", 1 }, { "first_sum_exceed", 1 },
                 { "game_over", 1 }, { "max_exceed", 1 }, { "sum_exceed", 1 }, { "max_die", 1 } }
    end
    for _, o in ipairs(ADMITTED) do lead[#lead + 1] = o end
    for i = #lead, 1, -1 do table.insert(order, 1, lead[i]) end
    -- `behind` says nothing until M.rebase has set it over the plans compared: one rank with it
    -- and one without is a plan compared outside that set
    if (a.behind == nil) ~= (b.behind == nil) then
        error("planner.lua: a rank compared before M.rebase set how far behind it is")
    end
    for _, o in ipairs(order) do
        local x, y = a[o[1]], b[o[1]]
        -- a chance summed in another order differs by float dust, which is no difference
        local differ = x ~= y
        if type(x) == "number" and type(y) == "number" then differ = math.abs(x - y) > M.DUST end
        if differ then
            if o[2] > 0 then return x < y end
            return x > y
        end
    end
    return false
end

-- Sets each rank's `behind` (M.outranks) from the most progress among the ranks `ok` allows
-- (all when nil: a plan that may not be played is no measure), and returns the index of the
-- best of those.
function M.rebase(ranks, ok)
    local top
    for i, r in ipairs(ranks) do
        if (not ok or ok(i)) and (not top or r.progress > top) then top = r.progress end
    end
    top = top or 0
    local best
    for _, r in ipairs(ranks) do r.behind = math.floor(top - r.progress + M.DUST) end
    for i, r in ipairs(ranks) do
        if (not ok or ok(i)) and (not best or M.outranks(r, ranks[best])) then best = i end
    end
    return best
end

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
            -- its goal is one unit (W.death); what its death costs beyond that (the chapter,
            -- when it ends the game: loss())
            v = v - (loss(W, st, e.charId) - W.death) * kill
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
            fx.die = die
            v = v - loss(W, st, act.unit) * die
            fx.hp = math.max(1, act.unitHp - math.floor(taken + 0.5))
            -- the judge chains it with the enemy phase's strikes, so a counter that lands is
            -- not averaged away
            fx.counter = { f.counterDist }
            -- the exchange's pairs (what it deals, what its counter takes) as the game plays
            -- them, for the judge to play the enemy phase on the HP each pair leaves (T100b)
            if f.joint then fx.exchange = { target = e.id, joint = f.joint } end
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
    elseif act.act == "rescue" then
        -- the target is carried (bmunit.c UnitRescue): off the map, never the AI's target, and
        -- dropped alive if its carrier dies (DropRescueOnDeath). What that saves it is the
        -- judged phase's to read; a carried recruit's Talk waits on a Drop (goalTerm)
        fx.carry = { id = act.targetId, by = act.unitId }
    elseif act.act == "drop" then
        -- the carried unit is set down on act.dropAt (bmunit.c UnitDrop)
        fx.drop = { id = act.targetId, x = act.dropAt.x, y = act.dropAt.y }
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
        if fx.wall.hp <= 0 then fx.opened = at end
    elseif act.obstacle or act.act == "door" then
        v = v + W.breach
        if act.door then fx.opened = act.door.x .. "," .. act.door.y end
    elseif act.act == "seize" then
        fx.win = 1   -- the win, scored as the boss's death is (goalTerm)
    end
    return v, fx
end

local function key(act)
    local k = string.format("%d>%s@%d,%d>%s", act.unitId, act.act, act.move.x, act.move.y,
        tostring(act.targetId or (act.obstacle and (act.obstacle.x .. "," .. act.obstacle.y))))
    -- a Drop is told apart by where it sets the unit down, a Canto move by where it ends
    if act.dropAt then k = k .. "/" .. act.dropAt.x .. "," .. act.dropAt.y end
    if act.canto then k = k .. "~" .. act.canto.x .. "," .. act.canto.y end
    return k
end

-- a plan's acts as keys, in order: what tells two plans apart
local function keysOf(st)
    local out = {}
    for _, x in ipairs(st.acts) do out[#out + 1] = key(x) end
    return out
end

-- key(act)'s inverse: the act's identity { unitId, act, move, targetId | obstacle, dropAt, canto } read back,
-- for a forced replay's act no candidate offered (botrun). It raises on a string no key gave.
local function unkey(k)
    local id, act, x, y, tgt = k:match("^(%-?%d+)>([%w_]+)@(%-?%d+),(%-?%d+)>(.*)$")
    if not id then error("planner.lua: not an act key: " .. k) end
    local a = { unitId = tonumber(id), act = act, move = { x = tonumber(x), y = tonumber(y) } }
    local rest, dx, dy = tgt:match("^(.-)~(%-?%d+),(%-?%d+)$")
    if rest then
        tgt, a.canto = rest, { x = tonumber(dx), y = tonumber(dy) }
    end
    rest, dx, dy = tgt:match("^(.-)/(%-?%d+),(%-?%d+)$")
    if rest then
        tgt, a.dropAt = rest, { x = tonumber(dx), y = tonumber(dy) }
    end
    local ox, oy = tgt:match("^(%-?%d+),(%-?%d+)$")
    if ox then
        a.obstacle = { x = tonumber(ox), y = tonumber(oy) }
    elseif tgt ~= "nil" then
        a.targetId = tonumber(tgt) or error("planner.lua: not an act key: " .. k)
    end
    return a
end

-- One act's identity and a plan's, for the diagnostics too: a forced replay, its DIAG line and
-- the audit name a plan by this list (botrun, montecarlo.py), never by a second spelling
M.key, M.keysOf, M.unkey = key, keysOf, unkey

-- whether a plan takes the Seize
local function seizesIn(st)
    for _, x in ipairs(st.acts) do
        if x.act == "seize" then return true end
    end
    return false
end

-- An enemy phase outcome's strikes, by the unit struck: the blows it takes (takenDist each).
local function blowsOn(strikes)
    local out = {}
    for _, s in ipairs(strikes) do
        out[s.target] = out[s.target] or {}
        table.insert(out[s.target], s.takenDist)
    end
    return out
end

local function copy(t)
    local out = {}
    for k, v in pairs(t) do out[k] = v end
    return out
end

-- What makes a decision irreversible enough to look a second enemy phase ahead (FR-017), over
-- the finalists `fin` (complete plans: acts with unitId, move, act): a door opened or a wall
-- struck ("breach"); a unit stepping into a boss's reach from outside it ("boss": its
-- end tile under sight.threat, its start tile not). No arrival trigger: the second phase
-- cannot place the wave yet, so it would learn nothing about it (ADR 0389, Nicolas
-- 2026-11-03). `enemies` are the ones in sight and those a retry remembers (Bot.candidates'
-- ctx.threats, ADR 0399): a remembered boss in fog is a boss whose reach a unit steps into.
-- -> the kinds, sorted, or nil.
function M.triggers(fin, byId, enemies, sight)
    local hit = {}
    local bosses = {}
    for _, e in ipairs(enemies or {}) do
        if e.isBoss and sight.threat then bosses[#bosses + 1] = sight.threat(e) end
    end
    for _, st in ipairs(fin) do
        for _, a in ipairs(st.acts) do
            if a.act == "door" or a.obstacle then hit.breach = true end
            local u = byId[a.unitId]
            for _, reach in ipairs(u and bosses or {}) do
                local at = endTile(a)
                if reach(at.x, at.y) > 0 and reach(u.x, u.y) == 0 then hit.boss = true end
            end
        end
    end
    local out = {}
    for k in pairs(hit) do out[#out + 1] = k end
    table.sort(out)
    return #out > 0 and out or nil
end

function M.plan(Bot, board, sight, style, opts)
    local W = M.WEIGHTS[style.aggression]
    if not W then error("planner.lua: no weights for style " .. tostring(style.aggression)) end
    local cap = M.CAPS[style.aggression]
    if not cap then error("planner.lua: no risk cap for style " .. tostring(style.aggression)) end
    local odds = sight.odds
    -- opts.offer: the acts read on another board (a full-information replay's: the fogged
    -- one, whose game is the one that plays them), judged on this one -- with this board's
    -- enemies, so the trigger, the assault and the record see one the fog hid there
    local offer = opts and opts.offer
    local cands, ctx
    if offer then
        local enemies, threats = Bot.enemiesOf(board, sight)
        cands, ctx = offer.cands, setmetatable({ enemies = enemies, threats = threats },
                                               { __index = offer.ctx })
    else
        cands, ctx = Bot.candidates(board, sight, style, opts)
    end
    if #cands == 0 then return nil, nil, { phases = 0, averaged = 0 } end
    local byId = {}
    for _, u in ipairs(board.units) do byId[u.id] = u end
    local objective = sight.objective and sight.objective.kind
    local gameOver = Bot.gameOver(sight)
    local start = { score = 0, base = 0, acts = {}, expect = {}, used = {}, tiles = {},
                    gone = {}, enemyHp = {}, hp = {}, took = {}, recruitHit = {}, win = 0,
                    fought = {}, healed = {},
                    walls = {}, opened = {}, objective = objective, recruits = ctx.recruits or {},
                    gameOver = gameOver, kill = {}, carry = {} }
    -- who carries whom as the plan leaves it: [carried id] = { by = carrier id } while carried,
    -- { x, y } once dropped (score's fx.carry, fx.drop); the board's carries to start
    for _, u in ipairs(board.units) do
        if u.carriedBy and not u.dead then start.carry[u.id] = { by = u.carriedBy } end
    end

    -- Whether `id` ends an earlier act of the plan off the tile it stands on now. The game
    -- was asked which heals reach whom with every unit where it stands (sight.heals), so a
    -- heal on a unit the plan has moved has no answer behind it: the Staff command may not
    -- be there at all (ch03, 2026-10-27).
    local function moved(st, id)
        local u = byId[id]
        for _, x in ipairs(st.acts) do
            if x.unitId == id then
                local at = endTile(x)
                return not u or at.x ~= u.x or at.y ~= u.y
            end
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
            if p then
                local at = endTile(a)
                p.x, p.y, p.acted = at.x, at.y, true
            end
        end
        return pos
    end
    -- a goal's chance on the board a plan leaves. A carried recruit is talked to only once set
    -- down (TalkCommandUsability lists units on the map), so its goal is at its carrier's tile
    -- and a turn later (GAMMA) while carried; at the drop tile once dropped
    local function chanceOf(st, g, pos)
        local c = g.kind == "recruit" and (st.carry or {})[g.unitId]
        if not c then return Goals.chance(g, pos, Goals.GAMMA, turnsTo) end
        local at, late = c, 1
        if c.by then
            at, late = pos[c.by] or byId[c.by] or g.tile, Goals.GAMMA
        end
        local moved = {}
        for k, v in pairs(g) do moved[k] = v end
        moved.tile = { x = at.x, y = at.y }
        return Goals.chance(moved, pos, Goals.GAMMA, turnsTo) * late
    end
    local before = {}
    do
        local pos = positions(start)
        for _, g in ipairs(goals) do before[g.id] = chanceOf(start, g, pos) end
    end
    -- the completion ledger (FR-014): what is still to get at this decision, for the rank's
    -- forfeits and botrun's seize skips
    local ledger = Goals.ledger(goals, sight, style, ctx, before)
    -- each unit's assigned goal as the decision starts (FR-016): the recruit, village or chest
    -- it was sent to, else its way to the objective, and its turns there now. Progress is what a
    -- plan cuts from those turns, the game's own (sight.turnsTo, through a breach when cut off)
    local assigned, goalOf = {}, {}
    for _, u in ipairs(ctx.blues) do
        local tile = (ctx.exploreGoal or {})[u.id] or (ctx.objectiveTile and ctx.objectiveTile(u))
        local t = tile and turnsTo(u, tile)
        if t then
            assigned[#assigned + 1] = { u = u, tile = tile, turns = t }
            goalOf[u.id] = assigned[#assigned]
        end
    end
    local function progress(st)
        local pos, out = positions(st), 0
        for _, a in ipairs(assigned) do
            local t = turnsTo(a.u, a.tile, pos[a.u.id])
            if t then out = out + (a.turns - t) end
        end
        return out
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
    -- the red units the plan leaves standing, as the game counts them for a Rout
    -- (sight.redCount: CountRedUnits -- the fogged, carried and hidden ones too), less the ones
    -- the plan removes: a Rout is won only when none is left, not when the last one in sight
    -- dies. A sight without the read (test_bot's fakes) counts as CountRedUnits does: every
    -- red not dead, on the field or not.
    local function redsLeft(st)
        local n = sight.redCount and sight.redCount()
        if not n then
            n = 0
            for _, u in ipairs(board.units) do
                if u.faction == "red" and not u.dead then n = n + 1 end
            end
        end
        -- a Talk takes a green recruit off too (fx.gone); the game's count holds only reds
        for id in pairs(st.gone) do
            if byId[id] and byId[id].faction == "red" then n = n - 1 end
        end
        return n
    end
    -- the chance a plan ends the chapter: a Seize or the boss's death (score's fx.win), or on
    -- a Rout map every red unit gone
    local function winChance(st)
        if objective ~= "rout" then return st.win end
        return redsLeft(st) == 0 and 1 or 0
    end
    -- `alive` (the judge's): each unit's chance to live the phase; `felled`: each recruit's
    -- chance our counter killed it; `fell`: the chance a player counter ended the chapter in
    -- the phase (the boss, or a Rout's last enemy, striking and dying: vanilla Ch5 attempt 8's
    -- boss died so on turn 5 with (5,1) still open); `rows` (optional) gets each goal's { id,
    -- kind, gold, worth, before, after }, the plan record's goalWorth
    local function winOf(st, fell) return 1 - (1 - winChance(st)) * (1 - (fell or 0)) end
    local function goalTerm(st, alive, felled, rows, fell)
        local pos, v = positions(st, alive), 0
        local pWin = winOf(st, fell)
        for _, g in ipairs(goals) do
            local c
            if st.took[g.id] then
                c = 1
            elseif g.kind == "objective" then
                c = pWin + (1 - pWin) * Goals.chance(g, pos, Goals.GAMMA, turnsTo)
            else
                c = chanceOf(st, g, pos) * (1 - pWin)
                if g.kind == "recruit" then
                    c = c * (1 - (st.recruitHit[g.unitId] or 0))
                        * (1 - (felled and felled[g.unitId] or 0))
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
    local talks, seizable = {}, false   -- every Talk and Seize the candidates offered
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
            -- the counter's chance to kill the attacker, for the record (botrun's `predicted`
            -- on a player-phase death): every attack act passes through here, mends included
            if a.act == "attack" then a.die = fx.die or 0 end
            if a.act == "talk" and a.target then talks[a.target] = true end
            if a.act == "seize" then seizable = true end
            local gone = fx.gone and { [fx.gone] = true } or {}
            -- what the act alone does to the goals: a march toward one earns nothing of its own,
            -- and ranked without this it was cut from the menu (vanilla Ch2: Eirika's walk to
            -- Ross never reached the beam, and Ross died on turn 4)
            local alone = { acts = { a }, took = fx.took and { [fx.took] = true } or {},
                            recruitHit = fx.recruitHit and { [fx.recruitHit.id] = fx.recruitHit.p } or {},
                            win = fx.win or 0, gone = gone }
            scored[#scored + 1] = { a = a, v = v - risk(a, fx.hp, gone) + goalTerm(alone) }
            a.own = scored[#scored].v   -- the advance's tie-break
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
                    or x.a.why == "hold" or x.a.why == "retreat"
                    -- what a Rescue or Drop saves or opens is the judged phase's to read, and
                    -- its own score never sees the phase
                    or x.a.act == "rescue" or x.a.act == "drop" then
                menu[#menu + 1] = x.a
            end
        end
        menus[#menus + 1] = { unit = c.unit, acts = menu }
    end

    -- `st` with `a` (unit `uid`'s act) added, the board the plan leaves updated; nil when the
    -- act cannot follow the plan (its tile taken, its target gone, a heal on a moved unit or
    -- on no one hurt)
    local function extend(st, a, uid)
        -- the tile it ends on (a Canto move's), which the plan then holds; the act's own tile
        -- must be free too, when it moves on from it
        local at = endTile(a)
        local tile = at.x .. "," .. at.y
        if st.used[uid] or st.tiles[tile] or st.tiles[a.move.x .. "," .. a.move.y]
                or (a.targetId and st.gone[a.targetId])
                or (a.act == "staff" and moved(st, a.targetId))
                -- an ally's tile, until the plan has moved that ally off it
                or (a.vacate and not st.used[a.vacate])
                -- a Rescue of a unit already carried; a Drop of one this unit does not carry,
                -- or onto a tile the plan has filled
                or (a.act == "rescue" and st.carry[a.targetId])
                or (a.act == "drop" and (not st.carry[a.targetId]
                    or st.carry[a.targetId].by ~= uid
                    or st.tiles[a.dropAt.x .. "," .. a.dropAt.y])) then
            return nil
        end
        local v, fx = score(a, st, W, style, odds)
        if fx.blocked then return nil end
        local n = { base = st.base + v, acts = copy(st.acts), expect = copy(st.expect),
                    used = copy(st.used), tiles = copy(st.tiles), gone = copy(st.gone),
                    enemyHp = copy(st.enemyHp), hp = copy(st.hp), took = copy(st.took),
                    recruitHit = copy(st.recruitHit), win = st.win, bossWant = st.bossWant,
                    fought = copy(st.fought), healed = copy(st.healed), walls = copy(st.walls),
                    opened = copy(st.opened), objective = objective, recruits = st.recruits, gameOver = st.gameOver,
                    kill = copy(st.kill), carry = copy(st.carry) }
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
        -- the counter it drew, as one record: its blows (a chain), the chance it kills, and
        -- the exchange's pairs when the game gave them
        if fx.counter then
            n.fought[uid] = { back = fx.counter, die = fx.die, exchange = fx.exchange }
        end
        if fx.took then n.took[fx.took] = true end
        if fx.recruitHit then
            n.recruitHit[fx.recruitHit.id] = math.max(n.recruitHit[fx.recruitHit.id] or 0,
                                                     fx.recruitHit.p)
        end
        if fx.win then n.win = math.max(n.win, fx.win) end
        if fx.wall then n.walls[fx.wall.at] = fx.wall.hp end
        if fx.opened then n.opened[fx.opened] = true end
        if fx.carry then n.carry[fx.carry.id] = { by = fx.carry.by } end
        if fx.drop then
            n.carry[fx.drop.id] = { x = fx.drop.x, y = fx.drop.y }
            n.tiles[fx.drop.x .. "," .. fx.drop.y] = true
        end
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

    -- The board plan `st` leaves, as sight stages a phase (enemyPhase, look): each player unit
    -- on its end tile at the HP the plan leaves it (its attack's weapon equipped), the reds'
    -- HP, the doors opened, the carries, and gone = each enemy the plan's blows together kill
    -- at even odds or better. -> that phase table, and kills = { [id] = { p, mean } }: each
    -- struck enemy's composed chance to die and its mean damage, at its own HP
    local function phaseOf(st)
        local planned, at = {}, {}
        for _, a in ipairs(st.acts) do at[a.unitId] = a end
        for _, u in ipairs(ctx.blues) do
            local a = at[u.id]
            local at = a and endTile(a)
            planned[#planned + 1] = { unit = u, x = at and at.x or u.x, y = at and at.y or u.y,
                                      hp = st.hp[u.id] or u.hp,
                                      slot = a and a.act == "attack" and a.slot or nil }
        end
        local reds = {}
        for id, hp in pairs(st.enemyHp) do reds[id] = math.max(1, math.floor(hp + 0.5)) end
        -- the plan's blows on it together, at its own HP: each blow alone was scored at the
        -- HP the earlier ones leave on average, which can call a sure kill short. Gone or
        -- standing by that composed chance (the damage is capped at its HP, so the dead
        -- share is hp * p)
        local gone, kills = copy(st.gone), {}
        for id, blows in pairs(st.kill) do
            local p, mean = odds(blows, byId[id].hp)
            gone[id] = p >= 0.5 or nil
            kills[id] = { p = p, mean = mean }
        end
        return { blues = planned, gone = gone, reds = reds, opened = st.opened, carry = st.carry },
            kills
    end
    -- opts.unjudged (the look's turn between, #510 W1): the beam's best plan, every unit it
    -- does not move holding, unjudged, as the phase table it leaves (phaseOf), .win its chance
    -- to end the chapter. No enemy phase is judged, no plan mended, no record made.
    if opts and opts.unjudged then
        local st = complete(beam[1])
        local ph = phaseOf(st)
        ph.win = winChance(st)
        return ph
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

    -- The advance (FR-016): each unit in turn takes the act that gains it the most turns toward
    -- its goal, of those whose standing chance to die is within the cap (the better by its own
    -- score on a tie: a Visit before a wait on the same tile). The beam orders partial plans by
    -- the judged score, where a House worth a few points never pays for the steps away from the
    -- gate, so no plan it kept had the lord walk there (Manchego Stars ch01: four plans judged,
    -- each with him waiting, and the run stuck); the rank puts progress first, but picks only among
    -- the plans judged. nil when no unit gains ground, or when the beam already has this plan.
    local function advance(have)
        local st, moved = start, false
        -- each unit's acts that gain ground, the most first: one a tile still taken refuses
        -- (extend) gives way to the next. A unit refused every one is tried again once the
        -- others have moved: the tile it wants may be one they vacate
        local waiting = {}
        for _, c in ipairs(cands) do
            local goal, ranked = goalOf[c.unit.id], {}
            for _, a in ipairs(goal and c.acts or {}) do
                local t = turnsTo(c.unit, goal.tile, endTile(a))
                if t and goal.turns - t > M.DUST
                    and M.admits((exposed(a, a.unitHp, {}, odds)), cap) then
                    ranked[#ranked + 1] = { a = a, g = goal.turns - t }
                end
            end
            table.sort(ranked, function(x, y)
                if math.abs(x.g - y.g) > M.DUST then return x.g > y.g end
                if (x.a.own or 0) ~= (y.a.own or 0) then return (x.a.own or 0) > (y.a.own or 0) end
                return key(x.a) < key(y.a)
            end)
            if #ranked > 0 then waiting[#waiting + 1] = { uid = c.unit.id, ranked = ranked } end
        end
        repeat
            local placed, left = false, {}
            for _, w in ipairs(waiting) do
                local n
                for _, r in ipairs(w.ranked) do
                    n = extend(st, r.a, w.uid)
                    if n then break end
                end
                if n then st, moved, placed = n, true, true else left[#left + 1] = w end
            end
            waiting = left
        until not placed or #waiting == 0
        if not moved then return nil end
        st = complete(st)
        if have[table.concat(keysOf(st), " ")] then return nil end
        return st
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
    -- The fog read (Bot.fogRead, #510 PR A step 4): each unit's chance to die to one strike
    -- from the strongest enemy seen so far, stood at the fog's edge. It never enters the cap,
    -- which reads the enemies in sight only (priced inside it, it froze the bot on Ch6: #510
    -- comment 6780781911); it breaks ties after everything else the rank reads (M.outranks'
    -- `fog`) and orders the best plan's acts (below).
    local fogDie = (offer and Bot.fogRead(board, sight, opts and opts.seen) or ctx.fogRead()).die
    -- what this call costs, over every plan it judges: the enemy phases judged, and the
    -- uncertain kills left to the average past BRANCH (never silent)
    local cost = { phases = 0, averaged = 0,
                   look = { decisions = 1, triggered = 0, extended = 0, skipped_budget = 0,
                            calls = 0, cpu_s = 0 } }
    -- a green unit lost spoils the clear as a player unit lost does (botrun's clean clear: vanilla
    -- Ch2's Ross, a Talk recruit, killed on turn 2 in every style while only blue deaths were
    -- paid), so the phase's strikes on one are paid at the same price. No plan moves one: it
    -- meets the phase where it stands
    local greens = {}
    -- A carried green is one too (board's carriedBy): carried it meets no strike, and a plan
    -- that drops it meets the phase on its drop tile
    for _, u in ipairs(board.units) do
        if u.faction == "green" and not u.dead and (u.onField or u.carriedBy) then
            greens[#greens + 1] = u
        end
    end
    -- the rank's admission (FR-009 to FR-011) from each protected unit's death chance against
    -- the cap: set once the phase is judged, and again when the lookahead adds a second phase
    -- The first call is the next phase's alone, and its numbers are kept (`first_*`, a
    -- protected unit's `first`): over the cap they rank ahead of the two-phase ones
    -- (M.outranks), which the lookahead's call overwrites.
    local function admit(st)
        local rank = st.rank
        local firstCall = rank.first_game_over == nil
        if firstCall then rank.first_game_over = rank.game_over end
        rank.admitted, rank.max_exceed, rank.sum_exceed, rank.max_die, rank.sum_die =
            true, 0, 0, 0, 0
        for _, pr in ipairs(st.protected) do
            if firstCall then pr.first = pr.die end
            local over = M.admits(pr.die, cap) and 0 or pr.die - cap
            rank.admitted = rank.admitted and over == 0
            rank.max_exceed = math.max(rank.max_exceed, over)
            rank.sum_exceed = rank.sum_exceed + over
            rank.max_die = math.max(rank.max_die, pr.die)
            rank.sum_die = rank.sum_die + pr.die
        end
        if firstCall then rank.first_max_exceed, rank.first_sum_exceed = rank.max_exceed, rank.sum_exceed end
    end
    -- One enemy phase outcome's strikes on `units` ({ id, charId, hp, maxhp?, back?, fought?,
    -- heal? }): per id { d (its chance to die), t (HP taken), sh (HP short at the end, when
    -- maxhp is given), n (strikes) }, and the chance no unit whose death ends the game dies. A
    -- unit with `back` (our counter's blows on it, from the plan's attack, left to the average)
    -- plays each way the counter goes: on `fought`, the HP it struck at, a counter that kills
    -- it is score()'s death and never the phase's; one that leaves it standing leaves it on
    -- that HP plus `heal`, what the plan heals it by after, and the phase strikes it there
    -- (PR #585 re-review: a heal after the counter is no heal for a unit the counter killed).
    local function struckIn(strikes, units)
        local onUnit, res, none = blowsOn(strikes), {}, 1
        for _, u in ipairs(units) do
            local phase = onUnit[u.id] or {}
            local d, t = odds(phase, u.hp)
            local sh = u.maxhp and (u.maxhp - u.hp) + t
            if u.back then
                d, sh = 0, 0
                for b, pb in pairs(u.back[1]) do
                    if pb > 0 and b >= u.fought then
                        sh = sh + pb * u.maxhp
                    elseif pb > 0 then
                        local left = math.min(u.maxhp, u.fought - b + u.heal)
                        local pd, pt = odds(phase, left)
                        d = d + pb * pd
                        sh = sh + pb * ((u.maxhp - left) + pt)
                    end
                end
            end
            res[u.id] = { d = d, t = t, sh = sh, n = #phase }
            if gameOver[u.charId] then none = none * (1 - d) end
        end
        return res, none
    end
    -- What the phases a look played after the judged one (sight.look's result `r`) do to
    -- `hit`, the units the judged phase may strike (st.phase.hit): each one's chance to die in
    -- any of them, the HP each loses, and the chance a unit whose death ends the game dies in
    -- one. A unit is struck in a phase at the HP it began it with, and only if it lives then.
    -- The last phase is read over every way it went; one before it (r.phases past the first,
    -- the judged one's own) along its expected way.
    local function lookDeaths(r, hit)
        local function inPhase(hp, outcomes)
            local live = {}
            for _, u in ipairs(hit) do
                local h = hp and hp[u.id] or 0
                if h > 0 then live[#live + 1] = { id = u.id, charId = u.charId, hp = h } end
            end
            local die, lost, over = {}, {}, 0
            for _, o in ipairs(outcomes) do
                local res, none = struckIn(o.strikes, live)
                for _, u in ipairs(live) do
                    die[u.id] = (die[u.id] or 0) + o.p * res[u.id].d
                    lost[u.id] = (lost[u.id] or 0) + o.p * res[u.id].t
                end
                over = over + o.p * (1 - none)
            end
            return die, lost, over
        end
        local die, lost, over = {}, {}, 0
        if not r.ended then
            die, lost, over = inPhase(r.hp, r.outcomes or { { p = 1, strikes = r } })
        end
        -- the phases between, folded in only where a look has them: a two-phase look's
        -- numbers stay the lookahead's own to the last bit
        for k = 2, #(r.phases or {}) do
            local ph = r.phases[k]
            local d, l, o = inPhase(ph.hp, { { p = 1, strikes = ph.strikes } })
            for id, x in pairs(d) do die[id] = 1 - (1 - (die[id] or 0)) * (1 - x) end
            for id, x in pairs(l) do lost[id] = (lost[id] or 0) + x end
            over = 1 - (1 - over) * (1 - o)
        end
        return die, lost, over
    end
    local function judge(st)
        local phase, kills = phaseOf(st)
        local planned, reds = phase.blues, phase.reds
        -- each uncertain kill, and each counter that can leave its attacker on more than one
        -- HP, played every way it goes: the average (an enemy gone at a kill >= 0.5, else
        -- standing at its mean HP; our attacker on its mean HP after the counter) hides the
        -- way the rolls go otherwise. Vanilla Ch5 turn 5: Eirika's attack killed an enemy the
        -- plan kept standing, and Joshua's AI turned on her. Manchego Stars ch03 (T100b): Wolfram's
        -- attack missed, the counter left him on 3 HP, and the AI that had passed him by at
        -- his mean HP killed him. A unit whose blow is the only one on its target plays the
        -- exchange's own pairs (sight's `joint`), so a counter is played only where our blow
        -- did not kill first; any other counter is played on its own spread. The most uncertain
        -- are played first, BRANCH of them at most; one that would take the ways past
        -- 2^BRANCH keeps the average and a narrower one after it is still played. Each left to
        -- the average is counted (`averaged`) so it is never silent.
        local dims, gone = {}, phase.gone
        local only = {}   -- target id -> the unit whose blow is the plan's only one on it
        for uid, x in pairs(st.fought) do
            if x.exchange and #(st.kill[x.exchange.target] or {}) == 1 then
                only[x.exchange.target] = uid
            end
        end
        local joined = {}
        for id, k in pairs(kills) do
            -- each uncertain kill played both ways (phaseOf composed it); `left`, the HP it
            -- keeps when it lives
            local hp = byId[id].hp
            local p, mean = k.p, k.mean
            local uid = only[id]
            if p > 0 and p < 1 and uid then
                local pairsOf, list = {}, {}
                for _, l in ipairs(st.fought[uid].exchange.joint) do
                    local dead = l.dealt >= hp
                    local k = (dead and "d" or "l") .. ":" .. l.back
                    if not pairsOf[k] then
                        pairsOf[k] = { p = 0, dead = dead, back = l.back, uid = uid, sum = 0 }
                        list[#list + 1] = pairsOf[k]
                    end
                    pairsOf[k].p = pairsOf[k].p + l.p
                    if not dead then pairsOf[k].sum = pairsOf[k].sum + l.p * (hp - l.dealt) end
                end
                for _, w in ipairs(list) do
                    if not w.dead then w.left = w.sum / w.p end
                end
                dims[#dims + 1] = { id = id, key = "k" .. id, ways = list }
                joined[uid] = true
            elseif p > 0 and p < 1 then
                dims[#dims + 1] = { id = id, key = "k" .. id, ways = {
                    { p = p, dead = true },
                    { p = 1 - p, dead = false, left = hp - (mean - hp * p) / (1 - p) } } }
            end
        end
        for uid, x in pairs(st.fought) do
            if not joined[uid] then
                local list = {}
                for b, p in pairs(x.back[1]) do
                    if p > 0 then list[#list + 1] = { p = p, back = b, uid = uid } end
                end
                table.sort(list, function(x, y) return x.back < y.back end)
                if #list > 1 then dims[#dims + 1] = { id = uid, key = "c" .. uid, ways = list } end
            end
        end
        for _, d in ipairs(dims) do
            local top = 0
            for _, w in ipairs(d.ways) do top = math.max(top, w.p) end
            d.unsure = 1 - top
        end
        table.sort(dims, function(x, y)
            if x.unsure ~= y.unsure then return x.unsure > y.unsure end
            return x.key < y.key
        end)
        -- the phase as the average leaves it: what the lookahead plays on (nextPhase)
        st.phase = phase
        local ways = { { p = 1, gone = gone, reds = reds, hp = {}, dead = {} } }
        st.branched = 0
        for _, d in ipairs(dims) do
            if st.branched >= M.BRANCH then break end
            -- a dim too wide for the ways left keeps the average; a narrower one after it is
            -- still played
            if #ways * #d.ways <= 2 ^ M.BRANCH then
                local nxt = {}
                for _, w in ipairs(ways) do
                    for _, o in ipairs(d.ways) do
                        local n = { p = w.p * o.p, gone = w.gone, reds = w.reds, hp = w.hp,
                                    dead = w.dead }
                        if o.dead ~= nil then
                            n.gone = copy(w.gone)
                            n.gone[d.id] = o.dead or nil
                            if not o.dead then
                                n.reds = copy(w.reds)
                                n.reds[d.id] = math.max(1, math.floor(o.left + 0.5))
                            end
                        end
                        if o.uid then
                            -- the HP the counter leaves, on the HP the unit fought at (score's
                            -- act.unitHp, the board's): a counter that kills it there kills it,
                            -- whatever the plan heals it by after; a unit that lives gets the
                            -- heal (struckIn's `heal`), never past its max
                            local u = byId[o.uid]
                            if u.hp - o.back <= 0 then
                                n.dead = copy(w.dead)
                                n.dead[o.uid] = true
                            else
                                n.hp = copy(w.hp)
                                n.hp[o.uid] = math.min(u.maxhp or math.huge,
                                                       u.hp - o.back + (st.healed[o.uid] or 0))
                            end
                        end
                        nxt[#nxt + 1] = n
                    end
                end
                ways = nxt
                st.branched = st.branched + 1
            end
        end
        st.averaged = #dims - st.branched
        cost.averaged = cost.averaged + st.averaged
        -- `list`'s units as way `w` leaves them: one its counter killed gone (that death is
        -- score()'s, never the phase's), one it played the counter on at the HP it left, with
        -- field `clear` dropped (what that HP already holds); `idOf` reads a unit's id
        local function inWay(list, w, idOf, clear)
            local out = {}
            for _, x in ipairs(list) do
                local id = idOf(x)
                if not w.dead[id] then
                    if w.hp[id] then
                        local q = copy(x)
                        q.hp = w.hp[id]
                        if clear then q[clear] = nil end
                        out[#out + 1] = q
                    else
                        out[#out + 1] = x
                    end
                end
            end
            return out
        end
        local function bluesIn(w) return inWay(planned, w, function(p) return p.unit.id end) end
        local strikes, outcomes, top, total = {}, {}, nil, 0
        for i, w in ipairs(ways) do
            if sight.enemyPhase then cost.phases = cost.phases + 1 end
            local s = sight.enemyPhase and sight.enemyPhase({ blues = bluesIn(w), gone = w.gone,
                                                              reds = w.reds,
                                                              opened = st.opened,
                                                              carry = st.carry }) or {}
            for _, o in ipairs(s.outcomes or { { p = 1, strikes = s } }) do
                outcomes[#outcomes + 1] = { p = w.p * o.p, strikes = o.strikes, way = i }
                total = total + w.p * o.p
            end
            if not top or w.p > top then strikes, top = s, w.p end
        end
        -- mutually exclusive branches, their chances normalized to sum to 1 (FR-009)
        local wayP = {}
        for _, o in ipairs(outcomes) do
            if total ~= 1 then o.p = total > 0 and o.p / total or 0 end
            wayP[o.way] = (wayP[o.way] or 0) + o.p
        end
        -- the audit's branch weights (FR-020): the likeliest AUDIT_WAYS ways' chances, rounded
        st.weights = {}
        for i = 1, #ways do st.weights[i] = wayP[i] or 0 end
        table.sort(st.weights, function(x, y) return x > y end)
        for i = #st.weights, M.AUDIT_WAYS + 1, -1 do st.weights[i] = nil end
        for i, p in ipairs(st.weights) do st.weights[i] = math.floor(p * 1e4 + 0.5) / 1e4 end
        -- each unit's chance to die, HP lost and the strikes on it, over every way the phase went
        local judged = st.base
        local die, taken, short, struck = {}, {}, {}, {}
        local byWay = {}   -- per unit, per way: its share of the death chance there
        -- the chance the game ends in the phase: per outcome, any unit whose death ends it
        -- dies there; deaths in one outcome may come together, never across outcomes
        local overAll = 0
        -- per unit, player and green, the enemies that strike it in any outcome
        local strikers = {}
        for _, g in ipairs(greens) do strikers[g.id] = {} end
        for _, p in ipairs(planned) do strikers[p.unit.id] = {} end
        -- per recruit, its chance our counter kills it (the phase's own `felled`) and the units
        -- on the player's side it strikes, whose other acts may save it (vanilla Ch5: Joshua,
        -- killed by Seth's counter on turn 3, the planner paying nothing for it)
        local felled, struckBy, fell, winStruck = {}, {}, 0, {}
        -- the units the phase may strike: the player's as the plan leaves them (its counter
        -- chained), then the greens where they stand; kept for the lookahead's second phase
        local hit = {}
        for _, p in ipairs(planned) do
            local id = p.unit.id
            local fought = st.fought[id]
            hit[#hit + 1] = { id = id, charId = p.unit.charId, hp = p.hp,
                              maxhp = p.unit.maxhp or p.hp, back = fought and fought.back,
                              fought = p.unit.hp, heal = st.healed[id] or 0 }
        end
        for _, g in ipairs(greens) do hit[#hit + 1] = { id = g.id, charId = g.charId, hp = g.hp } end
        st.phase.hit = hit
        -- per way: a counter it plays struck on the HP it left (no chain: the counter is
        -- already in that HP), a unit the counter killed out of the phase
        local hitOf = {}
        for i, w in ipairs(ways) do
            hitOf[i] = inWay(hit, w, function(u) return u.id end, "back")
        end
        for _, o in ipairs(outcomes) do
            local res, none = struckIn(o.strikes, hitOf[o.way])   -- none: no game-over unit dies
            for _, u in ipairs(hitOf[o.way]) do
                local id, r = u.id, res[u.id]
                die[id] = (die[id] or 0) + o.p * r.d
                byWay[id] = byWay[id] or {}
                byWay[id][o.way] = (byWay[id][o.way] or 0) + o.p * r.d
                taken[id] = (taken[id] or 0) + o.p * r.t
                if r.sh then short[id] = (short[id] or 0) + o.p * r.sh end
                struck[id] = math.max(struck[id] or 0, r.n)
            end
            overAll = overAll + o.p * (1 - none)
            -- the strikers our counters fell (felled): the boss, or a Rout's last enemy, is the win
            local left = objective == "rout" and redsLeft(st) or 0
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
                if strikers[s.target] and s.enemy then strikers[s.target][s.enemy] = true end
                if st.recruits[s.enemy] then
                    felled[s.enemy] = (felled[s.enemy] or 0) + o.p * (s.felled or 0)
                    struckBy[s.enemy] = struckBy[s.enemy] or {}
                    struckBy[s.enemy][s.target] = true
                end
            end
        end
        -- the fog's strike, after the phase: on the HP the phase is expected to leave. Its own
        -- number, never the unit's chance to die (the cap's). Read here, not when the rank
        -- first reaches it: M.outranks runs inside table.sort, and a sandbox call there yields
        -- across a C call (every scout-ch6 run crashed so, review of #598)
        st.fogBy, st.fogSum = {}, 0
        for _, p in ipairs(planned) do
            local f = fogDie(p.unit, p.x, p.y, p.hp - (taken[p.unit.id] or 0))
            if f > 0 then st.fogBy[p.unit.id], st.fogSum = f, st.fogSum + f end
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
            local by = {}
            for e in pairs(strikers[id]) do by[#by + 1] = e end
            table.sort(by)
            st.predict[#st.predict + 1] = { id = id, charId = p.unit.charId, x = p.x,
                                            y = p.y, hp = p.hp, die = die[id], taken = taken[id],
                                            strikes = struck[id], strikers = by }
            -- the HP the phase leaves it short: the plan's own deficit, then the enemy's
            judged = judged - loss(W, st, p.unit.charId) * die[id] - W.taken * short[id]
        end
        -- the goals, as the phase leaves them: who lives to take each, and each recruit our
        -- counter may have felled (its goal lost)
        local alive = {}
        for _, p in ipairs(planned) do alive[p.unit.id] = 1 - (die[p.unit.id] or 0) end
        st.goalWorth = {}
        judged = judged + goalTerm(st, alive, felled, st.goalWorth, fell)
        st.winFell, st.winStruck = fell, winStruck
        st.judged = judged
        st.strikes = strikes
        -- the protected units (FR-009): every blue, and any unit whose death ends the game; an
        -- allied green is not one. Each one's death chance, summed over the branches, against
        -- the style's cap, and the rank the plan is compared by
        st.keys = keysOf(st)
        -- what the plan forfeits for good (the ledger's goals it closes in any judged branch),
        -- how likely it ends the chapter, and the turns it gains toward each unit's goal
        local lost = {}
        for id, p in pairs(st.recruitHit) do lost[id] = p end
        for id, p in pairs(felled) do lost[id] = (lost[id] or 0) + p end
        for _, g in ipairs(greens) do
            if st.recruits[g.id] then lost[g.id] = (lost[g.id] or 0) + (die[g.id] or 0) end
        end
        st.forfeited = Goals.forfeited(ledger, goals, { win = winOf(st, fell), took = st.took,
                                                       lost = lost })
        local gain = progress(st)
        local greenDie = 0
        for _, g in ipairs(greens) do
            -- a game-over green is admission's, not here. A recruit's death is a forfeit too, and
            -- counted here as well: the forfeit is yes/no (any chance past Goals.DUST), so
            -- without its chance every plan that risks the recruit at all ties, and one that
            -- lowers it ranks no higher (vanilla Ch2's Ross, 37% in every turn-1 plan, #510).
            -- The forfeit ranks first, so this only breaks ties among plans that forfeit alike
            if not gameOver[g.charId] then
                greenDie = greenDie + (die[g.id] or 0)
            end
        end
        local won = winOf(st, fell)
        local rank = { admitted = true, forfeits = #st.forfeited, complete = won,
                       progress = gain, green_die = greenDie, value = judged, game_over = 0,
                       max_exceed = 0, sum_exceed = 0, max_die = 0, sum_die = 0, hp_left = 0,
                       key = table.concat(st.keys, " ") }
        -- `fog`, on the ways the plan does not end the chapter
        rank.fog = st.fogSum * (1 - won)
        st.protected = {}
        -- a unit's death in the plan: its counter's (score's fx.die, the chance the exchange
        -- kills it) and the phase's after it. The cap reads both: a counter that can kill is
        -- offered (Bot.candidates, `priced`), so it is the cap's to judge (ADR 0396). Where a
        -- way played the counter, its death is that way's; else it is spread over the ways.
        local played = {}
        for _, w in ipairs(ways) do
            for id in pairs(w.dead) do played[id] = true end
            for id in pairs(w.hp) do played[id] = true end
        end
        local function protect(u, hp)
            local o = st.fought[u.id] and st.fought[u.id].die or 0
            local d, branches = (die[u.id] or 0) + o, {}
            for i = 1, #ways do
                local p = wayP[i] or 0
                if p > 0 then
                    local mine = (byWay[u.id] or {})[i] or 0
                    if played[u.id] then
                        if ways[i].dead[u.id] then mine = mine + p end
                    else
                        mine = mine + o * p
                    end
                    branches[#branches + 1] = { p = p, die = mine / p }
                end
            end
            if gameOver[u.charId] and o > 0 then overAll = 1 - (1 - overAll) * (1 - o) end
            st.protected[#st.protected + 1] = { id = u.id, charId = u.charId, die = d,
                                                branches = branches, cap = cap }
            rank.hp_left = rank.hp_left + (hp - (taken[u.id] or 0))
        end
        for _, p in ipairs(planned) do protect(p.unit, p.hp) end
        for _, g in ipairs(greens) do
            if gameOver[g.charId] then protect(g, g.hp) end
        end
        rank.game_over = overAll
        st.rank = rank
        admit(st)
    end

    -- the plans judged: the beam's best, the assault, and on a stalled board (opts.stalled:
    -- botrun saw this board before and no turn event can change it) each unit's best act that
    -- changes the board, the rest holding -- and there only a plan that changes it is played
    local stalled = opts and opts.stalled
    local finals = {}
    for i = 1, math.min(M.FINAL, #beam) do finals[#finals + 1] = { st = beam[i], kind = "beam" } end
    local a = assault()
    if a then finals[#finals + 1] = { st = a, kind = "assault" } end
    local have = {}
    for _, f in ipairs(finals) do have[table.concat(keysOf(f.st), " ")] = true end
    local adv = advance(have)
    if adv then finals[#finals + 1] = { st = adv, kind = "advance" } end
    -- the rest of the plan in hand (opts.rest, botrun's on a replan): its acts as this board
    -- still offers them, in order, kept where they still fit as the mend keeps a plan, the
    -- units it leaves holding. The beam keeps only what scores well act by act, so a replan
    -- could lose a plan already found and judge only worse ones (vanilla Ch6 seed 1001 turn 4:
    -- a counter hit Eirika, the replan judged 4 plans, every one 30.8% or more to end the
    -- game; the rest of the plan in hand, replayed on that board, lost no lord).
    local rest = opts and opts.rest
    if rest and #rest > 0 then
        local byKey = {}
        for _, c in ipairs(cands) do
            for _, x in ipairs(c.acts) do byKey[key(x)] = { a = x, uid = c.unit.id } end
        end
        local st, kept = start, 0
        for _, k in ipairs(rest) do
            local o = byKey[k]
            local n = o and extend(st, o.a, o.uid)
            if n then st, kept = n, kept + 1 end
        end
        if kept > 0 then
            st = complete(st)
            local k = table.concat(keysOf(st), " ")
            if not have[k] then
                have[k] = true
                finals[#finals + 1] = { st = st, kind = "rest" }
            end
        end
    end
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
    -- every plan judged, for the run's trace: its acts, its score and where it came from; and
    -- the plans themselves, with whether a stalled board lets each be played
    local considered, judgedPlans, playable = {}, {}, {}
    local function pick()
        local ranks = {}
        for i, j in ipairs(judgedPlans) do ranks[i] = j.st.rank end
        local i = M.rebase(ranks, function(k) return judgedPlans[k].ok end)
        best = i and judgedPlans[i].st
    end
    local function consider(st, kind)
        judge(st)
        st.kind = kind
        local c = { judged = st.judged, acts = st.keys, kind = kind, rank = st.rank,
                    seizes = seizesIn(st) or nil, weights = st.weights }
        considered[#considered + 1] = c
        judgedPlans[#judgedPlans + 1] = { st = st, ok = not stalled or changes(st) }
        playable[c] = judgedPlans[#judgedPlans].ok
    end
    for _, f in ipairs(finals) do consider(f.st, f.kind) end
    pick()   -- the plan the mend starts from; once more after the mends
    -- the best plan judged, mended where the judge finds it may lose someone: each such unit,
    -- the likeliest to die first, tries every other act of its menu, the rest of the plan kept
    -- where it still fits. The beam ranks acts by their own score, so a plan where one unit
    -- steps elsewhere for its own sake can lose to that unit's best act in every slot (ch02
    -- turn 5: the four plans judged all left Marty to two Brigands). A green unit has no menu:
    -- it tries instead the player acts that could save it, one ending beside it (a block) or
    -- striking an enemy that strikes it. A recruit our counter may kill tries the acts of the
    -- units it strikes.
    -- With no plan under the cap the mend goes again from the plan it found, up to
    -- M.MEND_ROUNDS rounds, so more than one unit may change (#510 PR A): one round changed one
    -- unit, and two units each over the cap where they stood stayed a fallback.
    for round = 1, M.MEND_ROUNDS do
        if not best or (round > 1 and best.rank.admitted) then break end
        local base, menuOf, risky = best, {}, {}
        for _, m in ipairs(menus) do
            local mine = {}
            for _, a in ipairs(m.acts) do mine[#mine + 1] = { uid = m.unit.id, a = a } end
            menuOf[m.unit.id] = mine
        end
        local function tries(p)
            if p.recruit then
                -- a recruit has no player menu: the units it strikes try theirs (out of its
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
        -- a player unit whose counter may end the chapter (the boss striking it and dying)
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
                    st = complete(st)
                    -- a later round: new with #510 PR A
                    st.newer = round > 1 or base.newer or nil
                    consider(st, "mend")
                end
            end
        end
        pick()
        if best == base then break end   -- no mend outranked the plan it started from
    end
    -- The lookahead (FR-017, FR-018): at an irreversible transition, the finalists (the best
    -- M.FINAL plans judged, by rank) each meet a second enemy phase, our units holding between
    -- (sight.nextPhase; the hold is the R-8 spike's intervening turn). All of them or none: the
    -- calls it needs, one a finalist, within the decision's and the attempt's budget, else the
    -- original horizon, tagged `skipped`. A protected unit's death chance becomes that of dying
    -- in either phase, its branch-local first phase's kept, and the finalists are ranked again.
    local look = { calls = 0 }
    if best and sight.nextPhase then
        local idx = {}
        for i, j in ipairs(judgedPlans) do
            if j.ok then idx[#idx + 1] = i end
        end
        table.sort(idx, function(x, y)
            return M.outranks(judgedPlans[x].st.rank, judgedPlans[y].st.rank)
        end)
        local fin = {}
        for i = 1, math.min(M.FINAL, #idx) do fin[i] = judgedPlans[idx[i]].st end
        look.trigger = M.triggers(fin, byId, ctx.threats, sight)
        -- the deep diagnostic (FR-019): this same second phase on every decision, whatever
        -- the board and the budget, so a replay can ask whether one more cycle saw the death
        local deep = opts and opts.diag == "deep"
        look.deep = deep or nil
        if look.trigger or deep then
            if look.trigger then cost.look.triggered = 1 end
            local budget = opts and opts.budget or {}
            local room = deep and math.huge or math.min(budget.decision or M.LOOK_DECISION,
                                                        budget.attempt or M.LOOK_ATTEMPT)
            if #fin > room then
                look.skipped = true
                cost.look.skipped_budget = 1
            else
                local clock = os.clock()
                for _, st in ipairs(fin) do
                    local r = sight.nextPhase({ blues = st.phase.blues, gone = st.phase.gone,
                                                reds = st.phase.reds, opened = st.phase.opened,
                                                carry = st.phase.carry })
                    look.calls = look.calls + 1
                    local second, lost, over = lookDeaths(r, st.phase.hit)
                    -- each unit's death in either phase, and what the rank reads of it: the
                    -- protected units' admission, the greens' summed death, the HP left, and
                    -- the judged score's price for each death and for the HP lost. Only the
                    -- rank (and `protected`) take the second phase: `judged` and `predict` stay
                    -- the next phase's, which botrun grades against the phase that follows
                    local rank, first = st.rank, {}
                    for _, p in ipairs(st.predict) do first[p.id] = p end
                    local protected = {}
                    for _, pr in ipairs(st.protected) do
                        protected[pr.id] = true
                        pr.second = second[pr.id] or 0
                        pr.die = 1 - (1 - pr.die) * (1 - pr.second)
                        rank.hp_left = rank.hp_left - (lost[pr.id] or 0)
                    end
                    for _, u in ipairs(st.phase.hit) do
                        local f = first[u.id]
                        local was = f and f.die or 0
                        local more = (1 - was) * (second[u.id] or 0)
                        rank.value = rank.value - loss(W, st, u.charId) * more
                        if u.maxhp then rank.value = rank.value - W.taken * (lost[u.id] or 0) end
                        if f and f.green and not protected[u.id] then
                            rank.green_die = rank.green_die + more
                        end
                    end
                    rank.game_over = 1 - (1 - rank.game_over) * (1 - over)
                    admit(st)
                    st.extended = true
                end
                cost.look.cpu_s = os.clock() - clock
                cost.look.extended = 1
                look.extended = true
                -- every rank's `behind` from the one best progress, as pick() sets it, then
                -- the best of the finalists alone: a plan outside them lost to each on the
                -- first phase, and was never asked the second
                local ranks = {}
                for i, j in ipairs(judgedPlans) do ranks[i] = j.st.rank end
                M.rebase(ranks, function(k) return judgedPlans[k].ok end)
                best = fin[1]
                for _, st in ipairs(fin) do
                    if M.outranks(st.rank, best.rank) then best = st end
                end
                for _, c in ipairs(considered) do
                    for _, st in ipairs(fin) do
                        if c.rank == st.rank then c.extended = true end
                    end
                end
            end
            cost.look.calls = look.calls
        end
    end
    if not best or #best.acts == 0 then return nil, nil, cost end
    best.lookahead = look
    -- The look, in shadow (#510 W1, comment 6786548233): on a retry, while an enemy an earlier
    -- attempt saw kill one of our units or a green is on the field (sight.watching), the best plan's
    -- board is played M.LOOK_DEPTH enemy phases forward, our turn between each two the beam's
    -- own best plan, unjudged (opts.unjudged). Recorded on the plan (best.look), never ranked:
    -- play is PR B's until a shadow run proves the look. It costs at most opts.look.room
    -- AiDecideMain calls (botrun's allowance: a quarter of the attempt's others so far), the
    -- cost guessed before it runs by the last look's (opts.look.last), else the depth times
    -- the enemies on the field; one the room cannot pay is not run, and says so (`skipped`).
    local watching = sight.look and sight.watching and sight.watching() or {}
    if #watching > 0 then
        local depth = M.LOOK_DEPTH
        local rec = { asked = true, depth = depth, watched = {} }
        for i, e in ipairs(watching) do rec.watched[i] = e.id end
        local reds = 0
        for _, u in ipairs(board.units) do
            if u.faction == "red" and u.onField and not u.dead then reds = reds + 1 end
        end
        local lo = opts and opts.look or {}
        rec.estimate = lo.last or depth * reds
        if rec.estimate > (lo.room or 0) then
            rec.skipped = true
        else
            local calls0, clock, between = sight.aiCalls(), os.clock(), 0
            local r = sight.look({ blues = best.phase.blues, gone = best.phase.gone,
                                   reds = best.phase.reds, opened = best.phase.opened,
                                   carry = best.phase.carry }, depth, function(b)
                local c0 = sight.aiCalls()
                local ph = M.plan(Bot, b, sight, style, { unjudged = true, seen = opts and opts.seen })
                between = between + sight.aiCalls() - c0
                return ph
            end)
            -- each unit's chance to die in any looked phase: the judged one's, then the look's
            local later = lookDeaths(r, best.phase.hit)
            local first = {}
            for _, p in ipairs(best.predict or {}) do first[p.id] = p.die end
            rec.die = {}
            for _, u in ipairs(best.phase.hit) do
                local d = 1 - (1 - (first[u.id] or 0)) * (1 - (later[u.id] or 0))
                rec.die[tostring(u.id)] = math.floor(d * 1e4 + 0.5) / 1e4
            end
            rec.run, rec.ended = true, r.ended
            rec.calls = sight.aiCalls() - calls0
            rec.between_calls = between
            rec.cpu_s = os.clock() - clock
        end
        best.look = rec
    end
    -- best first; after a lookahead the finalists before the rest, whose ranks were never asked
    -- the second phase (the played plan heads the list either way)
    table.sort(considered, function(x, y)
        if look.extended and (x.extended == true) ~= (y.extended == true) then
            return x.extended == true
        end
        return M.outranks(x.rank, y.rank)
    end)
    best.considered = considered
    -- why each plan judged was not played (FR-020), for the failure audit: the played one
    -- nothing; else a stalled board's plan that changes nothing, one over the cap, or one the
    -- rank put below the played one. A plan the beam or a menu cut was never complete, so it
    -- is in no list: the audit finds it missing from `considered` while its acts are offered
    for _, c in ipairs(considered) do
        if c.rank == best.rank then
            c.played = true
        elseif not playable[c] then
            c.rejected = "stalled"
        else
            c.rejected = c.rank.admitted and "outranked" or "over_cap"
        end
    end
    local offeredN, seen, fogged = 0, 0, 0
    for _, c in ipairs(cands) do offeredN = offeredN + #c.acts end
    for _, u in ipairs(board.units) do
        if u.faction == "red" and u.onField and not u.dead then
            if u.fogged then fogged = fogged + 1 else seen = seen + 1 end
        end
    end
    -- mend_rounds (#510 PR A): whether a plan the planner judged before the mend's later rounds
    -- (st.newer) was under the cap, beside whether the played one is
    local oldUnder = false
    for _, j in ipairs(judgedPlans) do
        if j.ok and not j.st.newer and j.st.rank.admitted then oldUnder = true end
    end
    best.audit = { offered_n = offeredN, visibility = { seen = seen, fogged = fogged },
                   budget = { exhausted = look.skipped == true, averaged = best.averaged or 0 },
                   mend_rounds = { before = oldUnder, now = best.rank.admitted == true } }
    -- no plan under the cap: the least likely to end the game, then the least over it, is
    -- played, and says so (FR-011, ADR 0384 amended)
    best.fallback = not best.rank.admitted and "FALLBACK_SACRIFICE" or nil
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
    -- the enemies the plan was made against: in sight, and those a retry remembers (ctx.threats,
    -- ADR 0399), so a death by a remembered one is never graded `fog` (botrun.grade)
    best.enemies = {}
    for _, e in ipairs(ctx.threats) do best.enemies[e.id] = true end
    best.talks = {}
    for c in pairs(talks) do best.talks[#best.talks + 1] = c end
    table.sort(best.talks)
    best.seizable = seizable
    -- whether the plan takes the Seize offered, whether any plan judged took it, and whether
    -- one did within the cap: a skip is a fault only when a legal Seize under the cap was there
    -- to take (FR-015, botrun's seize skips)
    best.seizes, best.seizeJudged, best.seizeAdmitted = seizesIn(best), false, false
    best.stuck = ctx.stuck   -- the goals units are blocked from (Bot.candidates' opts.stuck)
    for _, c in ipairs(considered) do
        if c.seizes then
            best.seizeJudged = true
            best.seizeAdmitted = best.seizeAdmitted or c.rank.admitted
        end
    end
    -- the ledger as this plan leaves it: what it forfeits is closed
    local shut = {}
    for _, id in ipairs(best.forfeited) do shut[id] = true end
    best.ledger = {}
    for _, r in ipairs(ledger) do
        best.ledger[#best.ledger + 1] = { id = r.id, kind = r.kind, closes_on = r.closes_on,
                                          needs = r.needs,
                                          status = shut[r.id] and "closed" or r.status }
    end
    -- Sturdy first, fragile last (#510 PR A's fog rule): the acts of units the fog's strike
    -- threatens (predict's `fog`) are played after the others', the most threatened last, so a
    -- unit that shows what the fog hid moves before them and botrun's replan (M.surprise: a
    -- newly seen enemy) plans them around it. Kept only when the plan rebuilt in that order
    -- expects every act to end as judged (extend's expect: HP, a kill, the target's HP).
    local fogBy, any = best.fogBy or {}, false
    for _, p in ipairs(best.predict or {}) do
        if fogBy[p.id] then p.fog, any = fogBy[p.id], true end
    end
    if any then
        local order = {}
        for i, a in ipairs(best.acts) do order[i] = { a = a, i = i, f = fogBy[a.unitId] or 0 } end
        table.sort(order, function(x, y)
            if x.f ~= y.f then return x.f < y.f end
            return x.i < y.i
        end)
        local st = start
        for _, o in ipairs(order) do
            st = st and extend(st, o.a, o.a.unitId)
        end
        local was, same = {}, st ~= nil
        for i, a in ipairs(best.acts) do was[key(a)] = best.expect[i] end
        for i, a in ipairs(st and st.acts or {}) do
            local x, y = was[key(a)], st.expect[i]
            if not x or x.hp ~= y.hp or x.gone ~= y.gone or x.targetHp ~= y.targetHp then
                same = false
            end
        end
        if same then
            best.acts, best.expect = st.acts, st.expect
            -- the key list in place: the considered record's `acts` is this same table, and a
            -- replay reads the plan in the order it is played
            local keys = keysOf(best)
            for i = 1, #keys do best.keys[i] = keys[i] end
            -- and the rank's key: every comparison is done, so it only names the plan again
            best.rank.key = table.concat(best.keys, " ")
        end
    end
    return best.acts[1], best, cost
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
    local at = endTile(a)
    if actor and (actor.x ~= at.x or actor.y ~= at.y) then return "the move ended short" end
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
