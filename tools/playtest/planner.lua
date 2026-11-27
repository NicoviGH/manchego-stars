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
--      A plan that opens a door, breaks a wall or kills an enemy gives its later units the acts
--      from the tiles that change adds to their reach, read on the board it leaves (menusFor,
--      sight.changed; ADR 0431): the doorway, the room behind it and a dead enemy's tile are
--      tiles the board's own listing never had.
--   3. Judge: the best FINAL complete plans each meet the enemy phase the game's own AI would
--      play against them (sight.enemyPhase), which replaces the exposure estimate: they pay
--      for each unit's chance to die there (a green one's when it spoils the clear, M.greenPaid;
--      a recruit our counter fells loses its goal; a unit whose death ends the game costs the
--      chapter), its
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
--      which the beam's judged score can cut while the rank puts it first), the Seize when
--      the game offers it (the rest holding: the beam must not hide the win from the rank),
--      each ledger goal's offered Talk, Visit or chest no plan above holds, the plans without
--      the Seize while a goal is feasible and every plan above seizes (ADR 0405), and on a
--      stalled board (opts.stalled) each unit's best act that changes the board, of which the
--      best is played: a careful player that has stopped making progress takes the least it
--      must.
--      The enemy phase is played both ways where a counter may kill a striker (its tile
--      freed for the next), while the rarer way is at least sight's SPLIT_FLOOR of the phase
--      (ADR 0411), and once per way each uncertain kill can go, up to
--      BRANCH of them (an enemy the likeliest way keeps may die, one it removes may live), a way
--      splitting only while that kill's rarer side is at least the same floor of the whole
--      plan, and each phase told its way's share so its splits are bounded alike (ADR 0415).
--      Last, the
--      best plan is mended: each unit it may lose tries its other acts (a green one, the acts
--      of the player units that could save it; a recruit, the acts of the units it strikes), the
--      rest of the plan kept, and those are judged too. At an irreversible transition (M.triggers:
--      a door opened or a wall struck, a first step into a seen boss's reach) the best M.FINAL
--      plans each meet a second enemy phase, our army's reply played between
--      (sight.nextPhase): all of them or none, within M.LOOK_DECISION calls a decision and
--      opts.budget.attempt left of M.LOOK_ATTEMPT, else skipped and tagged. Each protected
--      unit's death chance becomes that of dying in either phase, and those plans are ranked
--      again among themselves.
--      Apart from that, a unit a plan's judged phase strikes, that no heal of the army's can
--      reach before the phase after, is read on M.WEAR enemy phases with its HP carried (the
--      wear, ADR 0421), within its own budget of M.WEAR_DECISION and M.WEAR_ATTEMPT calls.
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
-- player units it strikes, sorted),
-- kind = "beam"|"assault"|"bait"|"advance"|"seize"|"goal"|"lone"|"noseize"|"unstall"|"mend"|"rest"|"heal"|"spare",
-- considered = every plan judged, best first: { judged, acts (its key list, M.keysOf), kind, rank,
-- seizes, extended (it met the lookahead's second phase), lookWin (that phase's win, below),
-- played (the one played), rejected (why
-- not: "over_cap", "outranked", "stalled", "idle"), weights (its judged phase's likeliest ways'
-- chances) },
-- rank = what plans are compared by (M.outranks): { admitted, idle (opts.idle only: 1 for a plan
-- that does not advance the level, 0 for one that does; ADR 0439),
-- forfeits (how many ledger goals it closes for good, every owed recruit with no feasible row it
-- risks, and every spoiling theft: Goals.forfeited, ADR 0475), complete (its chance to end the
-- chapter), progress (the turns it cuts from each unit's way to its goal, summed), behind
-- (whole turns short of the most progress judged), green_die (allied greens' summed death
-- chance), value (the judged score), game_over (the chance a unit whose death ends the game
-- dies), max_exceed, sum_exceed, max_die, sum_die, hp_left, fog (the fog read's summed
-- chance to kill, where the chapter goes on), key }, forfeited = the ids it
-- closes (a row's, "owed:<unit id>" or "stolen:<unit id>"), ledger = Goals.ledger's rows as the plan leaves them (what it forfeits `closed`),
-- seizeJudged / seizeAdmitted = whether any plan judged took the Seize, and one within the
-- cap, stuck = Bot.candidates' record of the goals units are blocked from, fallback =
-- "FALLBACK_SACRIFICE" when no plan was under the cap, protected = each protected unit's
-- { id, charId, die, counter (the part of `die` that is the counters to the plan's own acts),
-- branches = { { p, die } } per way the judged phase went, cap, second (the
-- lookahead's second phase's chance, when extended; `die` then counts both, but for a unit the
-- wear read, whose `die` is the wear's reading of the later phases alone), capDie (when
-- extended: `die` as it stood before the second phase, the next phase and the wear, which
-- admission and the idle rule read: ADR 0470), wear (what the
-- phases after the next add for a unit no heal of the army's reaches, and `phases` how many were
-- read: ADR 0421, M.WEAR; `die` counts it) }, lookahead =
-- { trigger = the kinds M.triggers found | nil, extended, skipped, calls, deep, wear (the wear's
-- calls, ADR 0421), wear_skipped (its plans past the budget) }, audit = the
-- failure audit's (FR-020): { offered_n = how many acts Bot.candidates offered, mend_rounds =
-- { before, now } (whether a plan judged without the mend's later rounds was under the cap,
-- and whether the played one is: #510 PR A), visibility =
-- { seen, fogged } (the red units on the field), budget = { exhausted (the lookahead skipped),
-- averaged } }, branched
-- = the uncertain kills its judged phase played both ways, averaged = the ones past BRANCH left
-- to the likeliest way, opts = { stalled = bool, idle (botrun's quiet reached M.GOAL_QUIET), lows
-- (botrun's least turns read per goal id this attempt: the idle rule's march exemption, #698), sent,
-- tried, explored (all Bot.candidates'), quietGoals = the ledger ids
-- no unit has neared for M.GOAL_QUIET readings (botrun's rule 1, ADR 0403) } | nil,
-- explore = every Visit and Chest offered: { id, charId, x, y, kind, die (its standing chance
-- to die), played, judgedDie (the judged phase's, when played) }, goals = the recruit, village
-- or chest each unit was sent to: { id, x, y }, goalWorth = what it does to each open goal
-- (goals.lua): { id, kind, gold, worth, before, after (its chance after the judged phase),
-- closes },
-- nearest = the progress record's near half (botrun's rec.progress), sorted by id: { id, turns }
-- for "objective" (its nearest unit's turns) and each feasible or stalled visit, chest or
-- recruit row of the ledger (its best taker's turns), in ctx.turnsTo turns,
-- winFell = the judged phase's chance our counter ends the chapter, lookWin = the lookahead's
-- second phase's win (#641, M.secondRead's `won`) when it read one: { won, gain (what it adds to
-- the rank's value, never to `judged`), worth (goalWorth's rows with it) }, talks = the charIds any
-- unit was offered a Talk to, sorted, seizable = whether any unit was offered the Seize,
-- gentle = the recruit-sparing acts the board's menus offered, read before the PER_UNIT cut ({ unit,
-- act, slot, x, y, target }; #730),
-- seizes = whether this plan takes it }, and what the call cost, over every plan it judged (a
-- call that finds no plan judged some too): { phases (the enemy phases judged), averaged (the
-- uncertain kills left to the likeliest way past BRANCH), unsplit (the counter kills those phases
-- left unsplit below sight's SPLIT_FLOOR, summed over them), unjoined (the most Talked recruits
-- any judged phase found no blue slot for: taken off, no death read, ADR 0471; a most, not a
-- sum, so one missing slot reads as one however many ways and phases met it), area_positional
-- and area_truncated (the CHAI_AT commands, #727, and the walks the budget cut short in the Misc
-- scripts the plans' waits ran, which the judged phase did not play: M.areaWake), floored (the ways of the plan's
-- uncertain kills left unsplit below that floor of the plan, ADR 0415), look = { decisions, triggered,
-- extended, skipped_budget, calls, cpu_s, wear, wear_cpu_s, wear_skipped } (the lookahead's and
-- the wear's; absent when no unit can act) }.
-- opts.at = {} (optional; botrun's): written as the call goes, { stage ("propose", "search",
-- "judge <kind>", "lookahead"), judged (the plans judged so far), phases }: what a decision
-- cut short by its frame budget was doing (botrun's M.DECISION_FRAMES).
-- opts.budget = { decision, attempt, wear } (optional): the lookahead calls this decision may
-- spend, and the wear's calls left this attempt.
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
                   -- or the best still forfeits a theft ("stolen:<id>", ADR 0475)
-- the uncertain kills the judge plays both ways (2^n enemy phases), so a protected unit's death
-- chance is a sum over the ways the phase can go, never read off an average that keeps a
-- likely kill gone (FR-009). Even an enemy that reaches no one is played both ways: its death
-- can free a tile for one that does (test_planner_plays_an_uncertain_kill_both_ways). This
-- many at most, so a board of uncertain kills cannot cost thousands of phases a plan: past
-- it, the most uncertain are branched and the plan records how many it left to the likeliest way
-- (`averaged`). ADR 0384 has the cost.
M.BRANCH = 8
M.AUDIT_WAYS = 4  -- the judged phase's ways whose chances a plan's audit record keeps
M.BOSS_WORTH = 5   -- damage on a Defeat Boss map's boss, per point, against any other's

-- On a Seize map, the enemy standing on the seize tile (sight.objective.tile): the game offers
-- the Seize to no one while it holds the tile, so its death is the win's one step, as a Defeat
-- Boss map's boss's is (vanilla I_14, campaign 4006's Ephraim lap, 2026-11-15: Vigarde, charId
-- 0x6B, on the throne; twelve attempts never struck him together and stalled). The assault
-- strikes it; its HP is weighed as any enemy's (BOSS_WORTH stays the Defeat Boss map's). Its
-- id, or nil. Pure.
function M.throne(objective, enemies)
    local tile = objective and objective.kind == "seize" and objective.tile
    if not tile then return nil end
    for _, e in ipairs(enemies) do
        if e.x == tile.x and e.y == tile.y then return e.id end
    end
    return nil
end

-- death: one unit's death; taken: per HP short at the phase's end; dealt: per HP; kill: per
-- enemy removed; heal: per HP restored; breach: a door opened or the convoy's key taken (a
-- wall strike is worth its turns, #655); win: the game lost, for a unit
-- whose death ends it (a lord's); exp: per experience point our unit's attack teaches it, the
-- game's own count (a full level is 100: about one kill), so the blow that trains the unit
-- that needs it most ranks first among blows of the same risk and progress; gold: points per gold
-- a goal is worth (goals.lua: under careful no item outweighs a life, under bold a good one
-- does). What each further turn to a goal leaves of its chance is goals.lua's GAMMA.
-- Ground toward a goal, a Visit, a Talk recruit and the win itself: the goals' term (goalTerm
-- below), the change a plan makes to each open goal's worth x chance. The win completes every
-- unit's way to the objective (one death's worth in all) and closes every other goal: a later
-- win is the same win, so it waits while what it would close is worth more than the waiting.
M.WEIGHTS = {
    careful = { death = 1000, taken = 2, dealt = 1, kill = 30, heal = 1.5, breach = 25,
                win = 100000, gold = 0.04, exp = 0.3 },
    even = { death = 300, taken = 1, dealt = 1, kill = 30, heal = 1, breach = 25,
             win = 100000, gold = 0.08, exp = 0.3 },
    bold = { death = 60, taken = 0.5, dealt = 1, kill = 40, heal = 0.5, breach = 25,
             win = 100000, gold = 0.15, exp = 0.3 },
}

-- The most predicted death chance a style accepts for any protected unit in a plan (ADR 0384,
-- FR-010): fixed, never drawn, so a pinned run reproduces exactly. A plan over it never
-- outranks one under it, whatever it gains: a weight can be outbid, a cap cannot.
M.CAPS = { careful = 0.01, even = 0.05, bold = 0.15 }

-- Whether death chance `d` is within `cap`: a sum of branch products can land a few ulps over a
-- chance that is at the cap, and that is not an excess.
M.DUST = Goals.DUST
-- the chance at which a kill or a win counts as done: `score` counts a target gone at a kill of
-- this much, the judge a composed kill, the assault a lone strike's, and the rank a plan's win
-- (M.outranks). One line, so what the planner calls "gone" and what it ranks as "won" agree
M.GONE = 0.5
-- the chance at which a win, a kill or a counter's kill counts as advancing the level under the
-- idle rule (ADR 0439, #744): a bait with a 0.0003 win chance is no bait. Ch21's all-wait plan
-- with one unit in reach read as "baiting" and outranked every under-cap march, and cost charId 2
-- a 0.93 death three times. Nicolas's call (2026-11-23): 0.05, the value replayed; the caps run
-- 0.01 to 0.15. A weight, his to move.
M.ADVANCE_MIN = 0.05
-- the lookahead's budget (FR-018): extra judged calls (sight.nextPhase, one a finalist) per
-- decision and per attempt. 128 an attempt, not 32: 32 ran out before the boss fight on
-- Manchego Stars ch03 and two vanilla starts, so the decisive turns were judged one phase deep
-- (#570)
M.LOOK_DECISION = 8
M.LOOK_ATTEMPT = 128
-- the wear (ADR 0421): the most enemy phases a unit's HP is carried over while no heal of the
-- army's can reach it. 3, the least that read Colm's Ch9 death (27 HP outlives two hits of 12:
-- runs wg2x23 and wg3x23, #510). Its own budget of sight.nextPhase calls, beside the
-- lookahead's: a decision and an attempt. The most seen were 57 and 122 (vanilla Ch11,
-- lap3e/11, run wn11), so neither cut any of the 31 games behind the ADR
M.WEAR = 3
M.WEAR_DECISION = 64
M.WEAR_ATTEMPT = 256
-- Whether a plan's `took` ids hold a goal (a visit, chest or talk). A convoy use is no goal: the
-- plan only moves an item. Pure.
function M.tookGoal(took)
    for id in pairs(took) do
        if id:sub(1, 7) ~= "convoy:" then return true end
    end
    return false
end
function M.admits(d, cap) return d <= cap + M.DUST end

-- Whether complete plan rank `a` ranks before `b` (ADR 0384, FR-011 to FR-013). Admission
-- first, which reads the next enemy phase and the wear, never the lookahead's second phase
-- (ADR 0470). Over the cap, the smaller chance of a game over first: a lord's death is no risk
-- among others, it ends the chapter (Nicolas, 2026-11-01); then, once the bot's own stall
-- reading has fired (opts.idle, ADR 0439), a plan that advances the level before an idle one
-- (`idle`: a hold, or a march over the cap; an under-cap march is not idle, ADR 0458); then
-- the smallest largest excess,
-- then summed excess, then largest death chance. Each of those is read on the next enemy
-- phase first (`first_*`) and on both phases only to break its ties: the lookahead's second
-- phase has our units stand still another round, and over Manchego Stars ch03's pilots its readings
-- came true 0 of 8 times where the next phase's were about right, so ranking by both let a
-- unit be sent to an 82% death to dodge another's second-phase 90% (ADR 0389, amended
-- 2026-11-08; careful seed 3010 turn 18, replayed). Then the admitted order: fewer goals forfeited
-- (the completion ledger's), the likelier win (only one likelier than not: M.GONE), more
-- progress. Allied greens' summed death chance breaks ties among the plans within a turn of
-- the most progress judged (FR-012: only there, and never ahead of a forfeit or the win): `behind`, the whole turns a plan's progress
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
-- Whether readings `near` (goal id -> turns) set a new low against `best` (the army's best so
-- far, same ids; Goals.nearer, botrun's own test): some goal strictly nearer than ever. A goal
-- `best` has no reading for (no way to it on the board the plan starts from) sets none (#698).
function M.setsLow(near, best)
    for id, t in pairs(near) do
        if Goals.nearer(t, best[id]) then return true end
    end
    return false
end

function M.outranks(a, b)
    if a.admitted ~= b.admitted then return a.admitted end
    local order = { { "fog", 1 }, { "max_die", 1 }, { "sum_die", 1 }, { "hp_left", -1 },
                    { "key", 1 } }
    local lead = {}
    if not a.admitted then
        lead = { { "first_game_over", 1 }, { "idle", 1 }, { "first_max_exceed", 1 },
                 { "first_sum_exceed", 1 },
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
        -- the win ranks first only where it is likelier than not (M.GONE, the line `score` counts
        -- a target gone at). Below it the chance still counts, through `value` (goalTerm's
        -- objective worth and its win term): a 0.09% chance outranked plans worth 340 more in
        -- `value` and cost Ch17 seed 2 its Eirika (#641, ADR 0425)
        if o[1] == "complete" then
            if x < M.GONE then x = 0 end
            if y < M.GONE then y = 0 end
        end
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

-- the one owner is Board.sortedKeys (board.lua): bot.lua walks sets in the same order
local sortedKeys = Board.sortedKeys
M.sortedKeys = sortedKeys

-- What losing unit `charId` costs: the chapter, for one whose death ends the game (its death
-- sets EVFLAG_GAMEOVER, a lord's: sight.objective.gameOver), else one unit's death.
local function loss(W, st, charId)
    return st.gameOver[charId] and W.win or W.death
end

-- Whether a green's death is paid in a plan's value (#788, ADR 0482): when it spoils the clean
-- clear, i.e. it ends the game (an escort, paid W.win), it is an owed recruit (ADR 0381: vanilla
-- Ch2's Ross), or the chapter's ending tests its life (`gated`, botrun's api.gated: a reward it
-- may gate). `gated` nil (unread) pays every green, ADR 0376's rule. Any other green's death
-- costs nothing, in the value or the rank's green_die tie-break (ADR 0384): its death is still
-- predicted, and reported.
function M.greenPaid(st, g, gated)
    return gated == nil or st.gameOver[g.charId] or st.recruits[g.id] or st.loose[g.id]
        or gated[g.charId] or false
end

-- The ledger goal an act takes (Goals' ids): a Talk its recruit, a Visit or a chest its tile;
-- nil for any other act.
local function takes(act)
    if act.act == "talk" then return "recruit:" .. act.targetId end
    if act.act == "visit" or act.act == "chest" then
        return act.act .. ":" .. act.move.x .. "," .. act.move.y
    end
    return nil
end

-- The experience an exchange teaches our unit, over its ways (`ways`: exchangeOf's joint,
-- { p, dealt, back }): `x` is the game's count for our blows dealing nothing, dealing damage and
-- killing (sight.lua expOf), `hp` the HP the other side is at, `unitHp` our unit's. A way that kills
-- our unit teaches nothing (GetBattleUnitExpGain: its HP is 0). `struck`: the exchange is an
-- enemy's strike on our unit, so our blows are its `back` (our counter) and its `dealt` is
-- what we lose; else it is our attack, the other way round. ADR 0414.
local function taught(x, ways, hp, unitHp, struck)
    if not x then return 0 end
    local sum = 0
    for _, w in ipairs(ways or {}) do
        local ours, lost = w.dealt, w.back
        if struck then ours, lost = w.back, w.dealt end
        if lost < unitHp then
            sum = sum + w.p * (ours >= hp and x.kill or ours > 0 and x.hit or x.none)
        end
    end
    return sum
end

-- The HP `e` stands on once its own phase begins, after the plan leaves it on `hp` and the tile
-- gives it `heal` HP (sight.terrainHeal, via the plan's memo `st.healOf`): the game heals a unit
-- on a heal tile at the start of its faction's phase, before any enemy acts
-- (MakeTerrainHealTargetList, bmtarget.c:587-608; AddUnitHp holds it to max HP). The enemy
-- stands on its tile through our phase, so its tile now is the one that heals it (#709). No heal
-- leaves `hp` as it is; the cap is the unit's max HP (GetUnitMaxHp, bot.lua's context) and never
-- below the HP it stands on now, so a unit over its max is not credited a wound by the clamp. A
-- unit left at 0 HP gains nothing. `hp` here is ONE HP (a survivor's): `survivorDealt` is the
-- one owner of the survivors' share of an expectation that mixes a kill.
function M.healed(heal, e, hp)
    if heal == 0 or hp <= 0 then return hp end
    return Board.addHp(hp, heal, math.max(e.maxhp or hp, e.hp))
end

-- The surviving branch's mean damage of `dealt` on `hp`, a mean over the kill branch too (a kill
-- deals the HP it had), given its chance `kill` < 1; held to [0, hp]: a survivor was left above 0,
-- so more than hp is a rounding of `dealt`, never a bigger wound. The one read of it, for the
-- heal (M.outlasting) and the idle rule's wound (advances(), #744).
function M.survivorDealt(hp, dealt, kill)
    return math.min(hp, math.max(0, (dealt - kill * hp) / (1 - kill)))
end

-- What a blow of `dealt` on `hp` earns once the heal is counted (`kill`: its chance to kill). The
-- kill branch earns what it always did (the dead heal nothing: `dealt` there is the HP it had),
-- the surviving branch only the wound that outlasts the heal, healed(hp) - healed(hp - its mean
-- damage); the whole `dealt` where nothing heals.
function M.outlasting(heal, e, hp, dealt, kill)
    kill = kill or 0
    if heal == 0 or kill >= 1 or hp - dealt <= 0 then return dealt end
    if kill == 0 then return M.healed(heal, e, hp) - M.healed(heal, e, hp - dealt) end
    local survived = M.survivorDealt(hp, dealt, kill)
    return kill * hp + (1 - kill) * (M.healed(heal, e, hp) - M.healed(heal, e, hp - survived))
end

-- An act's own score, given the partial plan `st` before it (enemy HP already taken, enemies
-- already counted gone). Returns the score and the act's effects on the plan.
local function score(act, st, W, style, odds, likeliest)
    -- the HP the plan has left its unit so far: a heal earlier in the plan stays (from the start
    -- board's, a staff heal before its target's wait was undone; ADR 0408). An attack's own HP
    -- is set below, on the HP it fought at (the counter's ways add the plan's heals back)
    local fx = { hp = st.hp[act.unitId] or act.unitHp, gone = nil, enemyHp = nil }
    local v = 0
    if act.act == "attack" and act.f then
        local f, e = act.f, act.targetUnit
        -- the game played the exchange at the target's own HP; at the lower HP an earlier act
        -- of the plan leaves it, its damage is read capped there (the plan's HP is an average:
        -- design decision 5)
        local hp = st.enemyHp[e.id] or e.hp
        local kill, dealt = odds({ f.dealt }, hp)
        -- an owed unit no one may Talk yet keeps every credit of a red; only its death is priced
        if st.loose[e.id] then fx.recruitHit = { id = e.id, p = kill } end
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
            local winning = st.objective == "boss" and M.isWinBoss(e, st.winBoss)
            local target = winning and 1 + (M.BOSS_WORTH - 1) * want or 1
            local worth = (e.isBoss and 1 + 4 * want or 1) + (act.first and 1 or 0)
            -- only the wound that outlasts the tile's heal: a fort heals it back at the start
            -- of the enemy's phase (#709, M.outlasting); the plan's own HP is the unhealed one
            local earned = M.outlasting(st.healOf(e), e, hp, dealt, kill)
            v = v + W.dealt * earned * target + W.kill * kill * worth
                -- at the HP the plan leaves the target: a kill an earlier blow of the plan
                -- set up is this unit's, so the plan's chip and finish train the finisher
                + W.exp * taught(f.exp, f.joint, hp, act.unitHp)
        end
        if f.counters then
            -- the counter's risk is its chance to kill (a target dead before it answers takes
            -- nothing: the game's play of the exchange); the HP it takes, its likeliest loss, is
            -- paid once, at the end, after any heal the plan gives back (the judge's deficit)
            local die = odds({ f.counterDist }, act.unitHp)
            fx.die = die
            v = v - loss(W, st, act.unit) * die
            -- the HP the board is left at: the likeliest the counter leaves it alive at (ADR
            -- 0463), never the mean, an HP the game cannot produce. A heal after it is worth only
            -- what that HP lacks: none for a counter that most likely misses
            fx.hp = likeliest({ f.counterDist }, act.unitHp)
            -- the judge chains it with the enemy phase's strikes, so a counter that lands is
            -- not averaged away
            fx.counter = { f.counterDist }
            -- the exchange's pairs (what it deals, what its counter takes) as the game plays
            -- them, for the judge to play the enemy phase on the HP each pair leaves (T100b)
            if f.joint then fx.exchange = { target = e.id, joint = f.joint } end
        end
        fx.enemyHp = { id = e.id, hp = hp - dealt }
        -- the weapon uses the exchange spends at the HP the plan leaves the target (#644
        -- review): a blow its sooner death cuts off spends none. The attacker's, for the judged
        -- phase to arm it with, and the counter's off the enemy's weapon (its slot as the
        -- board's)
        fx.wear = { slot = f.wearSlot, uses = M.wearAt(f.wearAt, hp) }
        if f.counterSlot then
            fx.redWear = { id = e.id, slot = f.counterSlot, uses = M.wearAt(f.counterWearAt, hp) }
        end
        -- what the blow does, for the judge to play the kill both ways (its odds composed with
        -- the plan's other blows on the target, at the target's own HP)
        fx.kill = { id = e.id, dist = f.dealt }
        if kill >= M.GONE then fx.gone = e.id end
        -- the boss's death is the win: its worth is the goals' (goalTerm), what it completes
        -- less what it closes, never a sum of its own, or no goal could ever wait for it
        if st.objective == "boss" and M.isWinBoss(e, st.winBoss) then fx.win = kill end
    elseif act.act == "talk" then
        -- the recruit joins us: it is off the enemy side, for the plan's later acts and for the
        -- judged phase, as a kill is; its goal is taken (the goals' term)
        fx.gone = act.targetId
        fx.took = takes(act)
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
        fx.took = takes(act)
    elseif act.act == "staff" and act.amount then
        -- a planned heal: what the target is short by now in the plan, up to the staff's amount.
        -- This is AddUnitHp's clamp to GetUnitMaxHp (sight.maxHps), applied here because the HP
        -- is the plan's, which no game state holds
        local t = act.targetUnit
        local hp = st.hp[t.id] or t.hp
        -- the staff's amount the clamp leaves: what the target is short by, up to the amount
        local gain = Board.addHp(hp, act.amount, t.maxhp or hp) - hp
        -- and the experience the staff teaches the healer (the game's count, sight.staffExp)
        v = v + W.heal * gain + (gain > 0 and W.exp * (act.exp or 0) or 0)
        fx.heals = { id = t.id, hp = hp + gain }
        -- the game offers Staff only on someone hurt: a heal before the blow is no act
        fx.blocked = gain <= 0
    elseif act.act == "item" and act.amount then
        -- a Vulnerary on the unit itself: what it is short by now in the plan (a heal earlier
        -- in it counts). FE8 refuses one at full HP (CanUnitUseHealItem), so then it is no act.
        -- The HP it would restore past max is thrown away with a use, and costs what a restored
        -- HP earns: it is offered at any HP below max (bot.lua mend), and a use spent for a
        -- point or two is a use gone (ADR 0408 has the break-even)
        local hp = st.hp[act.unitId] or act.unitHp
        local gain = math.min(act.amount, act.unitMaxHp - hp)
        v = v + W.heal * (gain - (act.amount - math.max(gain, 0)))
        fx.hp = hp + gain
        fx.heals = { id = act.unitId, hp = hp + gain }
        fx.blocked = gain <= 0
    elseif act.act == "staff" or act.act == "item" then
        v = v + W.heal * (act.gain or 0)
    elseif act.obstacle and act.obstacle.blow then
        -- a wall takes what the game's forecast of the strike deals (sight.strikeWall); one
        -- the plan has already broken is no act -- a second strike planned on it was a crash
        -- its HP is its trap's (`at`, bot.lua wallKey: a two-tile wall's tiles share one; the
        -- tile struck on an act built without one), and its fall opens the tile struck
        local tile = act.obstacle.x .. "," .. act.obstacle.y
        local at = act.obstacle.at or tile
        local hp = st.walls[at] or act.obstacle.hp
        -- no flat `breach` worth (#655, Nicolas 2026-11-18): the HP it takes off is worth the
        -- turns it takes off every way through the wall (the goals' read, turnsOn); a flat
        -- reward on top counted the same thing twice
        fx.wall = { at = at, hp = hp - act.obstacle.blow.dealt }
        -- the uses the strike spends (#644 review): every blow on a wall lands, and a blow
        -- thrown once the wall is broken is never thrown, at the HP the plan leaves the wall
        -- (the forecast was played at its own: sight.strikeWall's wearAt)
        fx.wear = { slot = act.obstacle.blow.wearSlot, uses = M.wearAt(act.obstacle.blow.wearAt, hp) }
        fx.blocked = hp <= 0
        if fx.wall.hp <= 0 then fx.opened = tile end
    elseif act.act == "supply" then
        -- the convoy's door key taken when no one fielded can open the door on the way
        -- (bot.lua supplyKey): the act that opens the way, as a door's opening or a wall's
        -- strike is. The convoy holds that one key: a second Take of it in the plan is no act
        v = v + W.breach
        fx.took = "convoy:" .. act.item .. "x" .. act.uses
        fx.blocked = st.took[fx.took] == true
    elseif act.act == "trade" then
        -- a teammate's key handed over by Trade (bot.lua trades, #688): the act that opens the
        -- way, as the convoy's Take is. The holder holds that one key: a second Trade of it in
        -- the plan is no act. A hand-off out of a thief's reach (act.handoff, ADR 0483) opens
        -- no way: what it is worth is the theft the judged phase no longer plays
        if not act.handoff then v = v + W.breach end
        fx.took = "trade:" .. (act.gives and act.unitId or act.targetId) .. ":" .. act.item .. "x" .. act.uses
        fx.blocked = st.took[fx.took] == true
    elseif act.obstacle or act.act == "door" then
        -- a door keeps `breach` (#658). So does a wall strike with no forecast of its blow: the
        -- goals then cost the wall by the walk alone (bot.lua strikersOf), so the turns can
        -- never price it, and only the unit whose own way it is was offered it (breach)
        v = v + W.breach
        if act.door then fx.opened = act.door.x .. "," .. act.door.y end
    elseif act.act == "seize" then
        fx.win = 1   -- the win, scored as the boss's death is (goalTerm)
    end
    return v, fx
end

local function key(act)
    -- a Take's target is the lock its key is for ("lock" .. terrain, #699): a chest's Take told
    -- from a door's (no terrain), so a replay takes the chest key the plan took
    local k = string.format("%d>%s@%d,%d>%s", act.unitId, act.act, act.move.x, act.move.y,
        tostring(act.targetId or (act.obstacle and (act.obstacle.x .. "," .. act.obstacle.y))
                 or (act.terrain and "lock" .. tostring(act.terrain))))
    -- a Drop is told apart by where it sets the unit down, a Canto move by where it ends
    if act.dropAt then k = k .. "/" .. act.dropAt.x .. "," .. act.dropAt.y end
    if act.canto then k = k .. "~" .. act.canto.x .. "," .. act.canto.y end
    -- the same strike with another of the unit's weapons (#642): its slot
    if act.slotKey then k = k .. "#" .. tostring(act.slot) end
    return k
end

-- a plan's acts as keys, in order: what tells two plans apart
local function keysOf(st)
    local out = {}
    for _, x in ipairs(st.acts) do out[#out + 1] = key(x) end
    return out
end

-- key(act)'s inverse: the act's identity { unitId, act, move, targetId | obstacle, dropAt, canto,
-- slot (a spare's: slotKey), terrain (a chest Take's) } read back, for a forced replay's act no
-- candidate offered
-- (botrun). It raises on a string no key gave.
local function unkey(k)
    local id, act, x, y, tgt = k:match("^(%-?%d+)>([%w_]+)@(%-?%d+),(%-?%d+)>(.*)$")
    if not id then error("planner.lua: not an act key: " .. k) end
    local a = { unitId = tonumber(id), act = act, move = { x = tonumber(x), y = tonumber(y) } }
    -- a strike with another of the unit's weapons (#642): key's last suffix, so read first
    local rest, slot = tgt:match("^(.-)#(%d+)$")
    if rest then tgt, a.slot, a.slotKey = rest, tonumber(slot), true end
    local dx, dy
    rest, dx, dy = tgt:match("^(.-)~(%-?%d+),(%-?%d+)$")
    if rest then
        tgt, a.canto = rest, { x = tonumber(dx), y = tonumber(dy) }
    end
    rest, dx, dy = tgt:match("^(.-)/(%-?%d+),(%-?%d+)$")
    if rest then
        tgt, a.dropAt = rest, { x = tonumber(dx), y = tonumber(dy) }
    end
    local ox, oy = tgt:match("^(%-?%d+),(%-?%d+)$")
    local lock = tgt:match("^lock(.+)$")
    if lock then
        a.terrain = tonumber(lock) or lock
    elseif ox then
        a.obstacle = { x = tonumber(ox), y = tonumber(oy) }
    elseif tgt ~= "nil" then
        a.targetId = tonumber(tgt) or error("planner.lua: not an act key: " .. k)
    end
    return a
end

-- Every act the candidates `cands` (Bot.candidates') offer, by its key: { a, uid } each, the
-- first offer of a key kept. A strike's spares (#642, Bot's `spares`) are offered too, each by
-- its own key: a plan that played one names it so, and a replan's rest (opts.rest) or a forced
-- replay (botrun) that looked only at the acts lost its strike or raised on its key.
local function offeredByKey(cands)
    local out = {}
    local function put(a, uid)
        local k = key(a)
        if not out[k] then out[k] = { a = a, uid = uid } end
    end
    for _, c in ipairs(cands) do
        for _, x in ipairs(c.acts) do
            put(x, c.unit.id)
            for _, b in ipairs(x.spares or {}) do put(b, c.unit.id) end
        end
    end
    return out
end

-- One act's identity and a plan's, for the diagnostics too: a forced replay, its DIAG line and
-- the audit name a plan by this list (botrun, montecarlo.py), never by a second spelling
M.key, M.keysOf, M.unkey, M.offeredByKey = key, keysOf, unkey, offeredByKey

-- whether a plan takes the Seize
local function seizesIn(st)
    for _, x in ipairs(st.acts) do
        if x.act == "seize" then return true end
    end
    return false
end

-- An enemy phase outcome's strikes, by the unit struck: the blows it takes (takenDist each).
-- A berserk strike's striker (t.berserk, sight's: the player's berserked unit in the berserk
-- phase, #660) takes its target's counter (counterDist) as a blow too: a player unit's death.
local function blowsOn(strikes)
    local out = {}
    for _, s in ipairs(strikes) do
        out[s.target] = out[s.target] or {}
        table.insert(out[s.target], s.takenDist)
        if s.berserk and s.counterDist then
            out[s.enemy] = out[s.enemy] or {}
            table.insert(out[s.enemy], s.counterDist)
        end
    end
    return out
end

local copy = Board.copy

-- The weapon uses an exchange spends when its target stands on `hp` (#644 review): `at` =
-- { [HP the target had lost when the blow came] = expected uses } (sight's wearAt, M.wornBy over
-- the game's played ways). The ways were played at the target's own HP; an earlier blow of the
-- plan leaves it on less, its death comes sooner, and a blow thrown once it had lost `hp` or
-- more is never thrown. Nothing when the exchange gives no count. Pure.
function M.wearAt(at, hp)
    local n = 0
    for lost, uses in pairs(at or {}) do
        if lost < hp then n = n + uses end
    end
    return n
end

-- The waits a way of a judged plan makes (sight's M.areaWake): `blues` = the way's blues, of
-- which each that acts waits; and each acting unit in `dead` (its counter killed it): the game
-- runs the Misc events after the action whether or not the actor lived (playerphase.c:98-99,
-- cp_perform.c:85-86), and a dead actor is in no board list. `planned` = the plan's entries
-- ({ unit, x, y, acted, order }); a unit whose act was not played is `unacted` (acted false) and
-- waits nowhere. Pure.
function M.waitsIn(planned, dead, blues)
    local out = {}
    for _, p in ipairs(planned) do
        if p.acted and dead[p.unit.id] then out[#out + 1] = p end
    end
    for _, p in ipairs(blues) do
        if p.acted then out[#out + 1] = p end
    end
    return out
end

-- A finalist's staged board for sight.nextPhase: its first phase as the judge played it.
function M.staged(st)
    local ph = st.phase
    return { blues = ph.blues, waits = ph.waits, gone = ph.gone, reds = ph.reds, redWear = ph.redWear,
             joined = ph.joined, opened = ph.opened, carry = ph.carry, trades = ph.trades }
end

-- The items a plan's Trades move, for the sandbox's bags (sight's stagePhase, ADR 0483): each
-- Trade act as { holder, taker, item, uses, back } (bot.lua tradeAct: the actor takes from its
-- target, or gives to it with `gives`). Pure.
function M.tradesIn(acts)
    local out = {}
    for _, a in ipairs(acts) do
        if a.act == "trade" then
            local holder, taker = a.targetId, a.unitId
            if a.gives then holder, taker = a.unitId, a.targetId end
            out[#out + 1] = { holder = holder, taker = taker, item = a.item, uses = a.uses,
                              back = a.back }
        end
    end
    return out
end

-- The chance either of two independent events happens: 1 - (1 - a)(1 - b). The one fold of
-- chances: the plan's win and its counters' (winOf), a later phase's win and deaths (the
-- lookahead's), a protected unit's deaths over the plan's (overAll).
function M.either(a, b) return 1 - (1 - a) * (1 - b) end

-- Whether enemy `e` is the unit whose death is the "boss" win: the one `bossId`
-- (sight.objective.boss) names, else any CA_BOSS unit (a Defeat Boss goal whose boss has no row).
-- A second CA_BOSS on a map is no win: its death ends nothing. Pure.
function M.isWinBoss(e, bossId)
    return e.isBoss == true and (bossId == nil or e.charId == bossId)
end

-- The kind of win the planner prices for `objective` (sight.objective): "boss" when the boss's
-- death ends the chapter -- a Defeat Boss goal, or any other goal window beside a Misc
-- DefeatBoss event (vanilla Ch13: a Survive window, `DefeatBoss(EndingScene)`; sight.objective.boss
-- names that boss) -- else the goal's own kind. The one owner of "this boss's death is the win"
-- (#721), with M.isWinBoss. Known gap: a Rout stays a Rout (one kind is priced), so a Rout map
-- whose boss's death ends it early is priced as a plain kill.
function M.winKind(objective)
    if objective == nil then return nil end
    if objective.kind ~= "rout" and (objective.kind == "boss" or objective.boss) then return "boss" end
    return objective.kind
end

-- Whether the death of enemy `id` ends the chapter, on a board with `left` red units (a Rout's
-- count, the plan's: sight.redCount less the plan's kills), `byId` the board's units:
-- -> ends(id, gone), `gone` (optional) the ids dead since that count. The boss on a Defeat Boss
-- map; on a Rout map the last red unit standing. Not a Seize map's throne holder: its death
-- opens the Seize and ends nothing (ADR 0405: the Seize is the win). The judge's `fell` and
-- the lookahead's second phase (M.secondRead's `won`) read it alike. Pure.
function M.endsIn(objective, left, byId, bossId)
    return function(id, gone)
        local e = byId[id]
        -- a red unit only: the player's berserked unit strikes in a phase too (#660)
        if e == nil or e.faction ~= "red" or (gone and gone[id]) then return false end
        if objective == "boss" then return M.isWinBoss(e, bossId) end
        if objective ~= "rout" then return false end
        local n = left
        for g in pairs(gone or {}) do
            if byId[g] and byId[g].faction == "red" then n = n - 1 end
        end
        return n == 1
    end
end

-- The chance a counter in `strikes` (an enemy phase's, sight's: enemy, target, felled) fells an
-- enemy `ends(id, gone)` names, each counter weighted by the chance its unit is there to make
-- it (`alive[target]`, 1 when not given) -> that chance, and the targets whose counter can.
-- The judge's `fell` and the second phase's (M.secondRead) both. Pure.
function M.fellBy(strikes, ends, gone, alive)
    local stands, by = 1, {}
    for _, s in ipairs(strikes) do
        if ends(s.enemy, gone) then
            local p = (s.felled or 0) * (alive and alive[s.target] or 1)
            stands = stands * (1 - p)
            if p > 0 then by[#by + 1] = s.target end
        end
    end
    return 1 - stands, by
end

-- What a lookahead's second phase `r` (sight.nextPhase's) reads of the units the first phase
-- may strike (`hit`), each alive at its start at the HP r.hp gives it -> second (each one's
-- death chance in it), lost (its HP lost in it, and to a counter in the army's reply), over
-- (the chance any unit not in `worn` dies, as struckIn's `none` reads it: the game over's
-- share), won (the chance the chapter ends there, M.endsIn's `ends` naming the enemy: killed
-- by the army's reply, or felled by our counter to its own strike in the second phase). The
-- enemies the first phase's counters removed (r.fell) and the reply's kills, each taken as
-- made as nextPhase takes them, are gone before the next is read (a Rout's last enemy). A kill
-- or a counter counts only as far as its unit lives the first phase (`alive`, the judge's:
-- nextPhase plays that phase along its expected way, so a unit it leaves standing may still
-- die there). `struckIn` is the judge's; `worn` the units the wear read (ADR 0421), whose
-- later phases are its reading. Pure given struckIn and ends.
function M.secondRead(r, hit, struckIn, worn, ends, alive)
    worn = worn or {}
    ends = ends or function() return false end
    local live, unworn = {}, {}
    for _, u in ipairs(hit) do
        local hp = r.hp and r.hp[u.id] or 0
        if hp > 0 then
            live[#live + 1] = { id = u.id, charId = u.charId, hp = hp }
            if not worn[u.id] then unworn[#unworn + 1] = live[#live] end
        end
    end
    local gone = {}
    for _, id in ipairs(r.fell or {}) do gone[id] = true end
    local second, lost, over = {}, {}, 0
    -- the counter each killer took in the army's reply (sight.nextPhase's .reply): HP the
    -- plan loses between the phases, as the first phase's strikes are. A kill there of the
    -- enemy whose death ends the chapter is the win at the kill's chance (#641: Morva, charId
    -- 0x41, wounded by a bait's counters, dies to the next turn's blow)
    local won = 0
    for _, k in ipairs((r.reply or {}).kills or {}) do
        lost[k.unit] = (lost[k.unit] or 0) + (k.lost or 0)
        if ends(k.enemy, gone) then
            won = M.either(won, (k.p or 0) * (alive and alive[k.unit] or 1))
        end
        gone[k.enemy] = true
    end
    local fell = 0
    for _, o in ipairs(r.outcomes or { { p = 1, strikes = r } }) do
        local res, none = struckIn(o.strikes, live)
        for _, u in ipairs(live) do
            second[u.id] = (second[u.id] or 0) + o.p * res[u.id].d
            lost[u.id] = (lost[u.id] or 0) + o.p * res[u.id].t
        end
        if #unworn < #live then none = select(2, struckIn(o.strikes, unworn)) end
        over = over + o.p * (1 - none)
        fell = fell + o.p * M.fellBy(o.strikes, ends, gone, alive)
    end
    return second, lost, over, M.either(won, fell)
end

-- What makes a decision irreversible enough to look a second enemy phase ahead (FR-017), over
-- the finalists `fin` (complete plans: acts with unitId, move, act): a door opened or a wall
-- struck ("breach"); a unit stepping into a boss's reach from outside it ("boss": its
-- end tile under sight.threat, its start tile not); a finalist with the assault's bait in it
-- ("bait", #641: its worth is the next turn's kill, which only the second phase reads, and
-- reads as a win only where that kill ends the chapter (endsIn: not a Seize map's holder); vanilla
-- E_20's Ephraim, charId 0x0F, baited Morva from inside her danger zone, so no "boss" fired and
-- the bait ranked on progress alone). No arrival trigger: the second phase
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
            if a.why == "bait" then hit.bait = true end
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
    -- the greens whose death spoils the clear besides an escort and a recruit (botrun's read of
    -- the ending, #788): M.greenPaid's `gated`, one read for every place a green is charged
    local gated = opts and opts.gated
    local W = M.WEIGHTS[style.aggression]
    if not W then error("planner.lua: no weights for style " .. tostring(style.aggression)) end
    local cap = M.CAPS[style.aggression]
    if not cap then error("planner.lua: no risk cap for style " .. tostring(style.aggression)) end
    local odds = sight.odds
    -- the HP a unit keeps at its likeliest surviving outcome (ADR 0463); 1 when none is left
    -- alive (a sure death: the plan's `gone` or the counter's `die` carries it)
    local function likeliest(dists, hp) return sight.likeliestLeft(dists, hp) or 1 end
    -- sight's split floor, one bound for the whole judged plan (ADR 0415)
    local floor = assert(sight.splitFloor, "planner.lua: the sight gives no splitFloor")
    -- opts.offer: the acts read on another board (a full-information replay's: the fogged
    -- one, whose game is the one that plays them), judged on this one -- with this board's
    -- enemies, so the trigger, the assault and the record see one the fog hid there
    local offer = opts and opts.offer
    -- opts.at (botrun's, optional): where this call is, kept as it goes for the record of a
    -- decision cut short (botrun's M.DECISION_FRAMES): { stage, judged, phases }
    -- (a call without it writes nothing: the planner is called thousands of times a run)
    local now = opts and opts.at
    if now then now.stage, now.judged, now.phases = "propose", 0, 0 end
    local cands, ctx
    if offer then
        local enemies, threats = Bot.enemiesOf(board, sight)
        cands, ctx = offer.cands, setmetatable({ enemies = enemies, threats = threats },
                                               { __index = offer.ctx })
    else
        cands, ctx = Bot.candidates(board, sight, style, opts)
    end
    if #cands == 0 then return nil, nil, { phases = 0, averaged = 0, unsplit = 0, floored = 0,
                                      unjoined = 0, area_positional = 0, area_truncated = 0 } end
    if now then now.stage = "search" end
    local byId = {}
    for _, u in ipairs(board.units) do byId[u.id] = u end
    local objective = M.winKind(sight.objective)
    local winBoss = sight.objective and sight.objective.boss
    local gameOver = Bot.gameOver(sight)
    -- the HP a heal tile gives each enemy at its own phase's start (sight.terrainHeal), read once
    -- an enemy for the whole search: its tile and max HP do not move through our phase. Required:
    -- a sight without it would hide the bug (#709).
    local healMemo = {}
    local function healOf(e)
        local h = healMemo[e.id]
        if h == nil then h = sight.terrainHeal(e); healMemo[e.id] = h end
        return h
    end
    local start = { score = 0, base = 0, acts = {}, expect = {}, used = {}, tiles = {},
                    gone = {}, enemyHp = {}, hp = {}, took = {}, recruitHit = {}, win = 0,
                    fought = {}, healed = {}, healOf = healOf,
                    walls = {}, opened = {}, objective = objective, winBoss = winBoss,
                    recruits = ctx.recruits or {}, loose = ctx.looseRecruits or {},
                    gameOver = gameOver, kill = {}, carry = {}, wear = {}, redWear = {} }
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
    -- the goals' turns: the game's own, through a door or wall where that is the shorter way
    local turnsTo = ctx.turnsTo
    -- the same read on the board plan `st` leaves, its units at `pos` (positions): a wall it
    -- struck has the HP the plan leaves it (st.walls), and each unit that can strike a wall
    -- stands where the plan puts it, so a strike, or a striker brought into reach, is worth the
    -- turns it takes off every way through that wall, and a striker led away costs them (#655;
    -- bot.lua's ctx.turnsOn)
    local function turnsOn(st, pos)
        return ctx.turnsOn and ctx.turnsOn(st.walls, pos) or turnsTo
    end
    local function positions(st, alive)
        local pos = {}
        for _, u in ipairs(ctx.blues) do
            pos[u.id] = { x = u.x, y = u.y, acted = u.acted, alive = alive and alive[u.id] or 1,
                        opens = st.opens and st.opens[u.id] }
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
    local function chanceOf(st, g, pos, read)
        -- the looter that closes the tile dies in the plan: the tile stays open (ADR 0483;
        -- vanilla Ch16's east thief looted (20,5) while no strike on it was worth anything)
        if g.closer and st.gone[g.closer] then
            -- one open copy per goal, shared by every plan that kills its looter
            if not g.kept then
                g.kept = copy(g)
                g.kept.closes = nil
            end
            g = g.kept
        end
        local c = g.kind == "recruit" and (st.carry or {})[g.unitId]
        read = read or turnsOn(st, pos)
        if not c then return Goals.chance(g, pos, Goals.GAMMA, read) end
        local at, late = c, 1
        if c.by then
            at, late = pos[c.by] or byId[c.by] or g.tile, Goals.GAMMA
        end
        local moved = copy(g)
        moved.tile = { x = at.x, y = at.y }
        return Goals.chance(moved, pos, Goals.GAMMA, read) * late
    end
    local before = {}
    do
        local pos = positions(start)
        for _, g in ipairs(goals) do before[g.id] = chanceOf(start, g, pos) end
    end
    -- the completion ledger (FR-014): what is still to get at this decision, for the rank's
    -- forfeits and botrun's seize skips
    local ledger = Goals.ledger(goals, sight, style, ctx, before)
    -- the chance of each dated, feasible ledger goal (the only rows `forfeited` reads this for) on
    -- the board a plan leaves, by reaching it alone: no unit's survival, no win, no opener's
    -- chance (a chest opener's death or theft is the cap's and the theft price's, ADR 0384, 0442;
    -- p.opens = nil), so a 0 here is the goal out of reach by its deadline (ADR 0450)
    -- -> { [goal id] = { before, after } }, `before` the decision's. Empty (no read at all) when the
    -- ledger has no such row.
    local dated = {}
    do
        local feasible = {}
        for _, r in ipairs(ledger) do
            if r.status == "feasible" then feasible[r.id] = true end
        end
        for _, g in ipairs(goals) do
            if g.closes ~= nil and g.kind ~= "objective" and feasible[g.id] then
                dated[#dated + 1] = g
            end
        end
    end
    local function reached(st)
        local out = {}
        if #dated == 0 then return out end
        local pos = positions(st)
        for _, p in pairs(pos) do p.opens = nil end
        local read = turnsOn(st, pos)
        for _, g in ipairs(dated) do
            if not st.took[g.id] then
                out[g.id] = { before = before[g.id], after = chanceOf(st, g, pos, read) }
            end
        end
        return out
    end
    -- the progress signal's near half (#510 fwd1 item C; botrun's rules read it): how near the objective's
    -- nearest unit is, and each still-feasible or stalled ledger goal's best taker, in turns (a
    -- stalled row stays read: a new low there makes it feasible again, ADR 0403). Goals.chance
    -- asked turnsTo for these very (unit, tile, from, beside) above (a unit's own tile is the
    -- start position, so the memo key matches turnsTo(u, tile)): no new path search. `beside`
    -- is the goal's own (Goals.beside), so the read and the chance never disagree on a recruit.
    -- `nearOn(read, pos)` takes the same readings with `read` from `pos` (a plan's end board,
    -- turnsOn's read): the idle rule's march exemption asks it whether a plan sets a new low
    -- (admit(), #698). -> goal id -> turns
    local goalById = {}
    for _, g in ipairs(goals) do goalById[g.id] = g end
    local function nearOn(read, pos)
        local function least(g)
            local n
            for _, u in ipairs(g.takerUnits) do
                local t = read(u, g.tile, pos and pos[u.id], Goals.beside(g.kind))
                if t and (not n or t < n) then n = t end
            end
            return n
        end
        local out = {}
        for _, g in ipairs(goals) do
            if g.kind == "objective" then
                local t = least(g)
                if t and (not out.objective or t < out.objective) then out.objective = t end
            end
        end
        for _, r in ipairs(ledger) do
            local g = (r.status == "feasible" or r.status == "stalled") and goalById[r.id]
            if g and g.tile and (r.kind == "visit" or r.kind == "chest" or r.kind == "recruit") then
                out[r.id] = least(g)
            end
        end
        return out
    end
    local nearest, nearNow = {}, nearOn(turnsTo)
    for id, t in pairs(nearNow) do nearest[#nearest + 1] = { id = id, turns = t } end
    table.sort(nearest, function(x, y) return x.id < y.id end)
    -- the army's best so far per goal: the least of botrun's lows (opts.lows, every earlier
    -- phase's reading this attempt) and this board's; a goal no earlier phase read is measured
    -- against this board alone. A plan marches only below it (#698)
    local bestNear = {}
    for id, t in pairs(nearNow) do
        bestNear[id] = Goals.lowest(opts and opts.lows and opts.lows[id], t)
    end
    -- each unit's assigned goal as the decision starts (FR-016): the recruit, village or chest
    -- it was sent to, else its way to the objective, and its turns there now. Progress is what a
    -- plan cuts from those turns, the game's own (sight.turnsTo, or through a door or wall)
    local assigned, goalOf = {}, {}
    local chestAt = {}   -- "x,y" of every chest goal: a march there needs an opener (below)
    for _, g in ipairs(goals) do
        if g.kind == "chest" and g.tile then chestAt[g.tile.x .. "," .. g.tile.y] = true end
    end
    for _, u in ipairs(ctx.blues) do
        local tile = (ctx.exploreGoal or {})[u.id] or (ctx.objectiveTile and ctx.objectiveTile(u))
        -- the tile's kind (a Talk assignment, Bot.candidates' exploring) says whether every read
        -- of it below is beside it
        local beside = tile and ctx.beside and ctx.beside(tile) or false
        local t = tile and turnsTo(u, tile, nil, beside)
        if t then
            assigned[#assigned + 1] = { u = u, tile = tile, turns = t, beside = beside,
                                        chest = chestAt[tile.x .. "," .. tile.y] }
            goalOf[u.id] = assigned[#assigned]
        end
    end
    -- Not nearOn: progress sums what each unit cuts from its OWN assigned way (a unit's march
    -- counts though another is nearer the same goal), nearOn takes each goal's least over its
    -- takers. The rank scores the first, the idle rule's new low reads the second (#698).
    -- A march to a chest counts in the ways the phase leaves its unit an opener (st.opens: the
    -- chance it lives and keeps one, set for a unit a thief robs of its last; ADR 0483): ranked
    -- before the score, a march that hands the thief the key outranked the stay that kept it
    -- (vanilla Ch16 s4005, replay l764a, turn 12: Eirika's stay was a turn behind)
    local function progress(st)
        local pos, out = positions(st), 0
        local read = turnsOn(st, pos)
        for _, a in ipairs(assigned) do
            local t = read(a.u, a.tile, pos[a.u.id], a.beside)
            local keep = a.chest and st.opens and st.opens[a.u.id] or 1
            if t then out = out + (a.turns - t) * keep end
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
    -- Whether `id`'s death is the plan's win (#730 fix 2, ADR 0452): the Defeat-boss boss, or a
    -- Rout's last red (no other red left after the plan's kills). The one reading of "this unit's
    -- death ends the chapter" a loose recruit's forfeit is released by; an unrelated win (a
    -- Seize, another boss) does not release it.
    local function winByDeath(st, id)
        local e = byId[id]
        if not e or e.faction ~= "red" then return false end
        if objective == "boss" then return M.isWinBoss(e, winBoss) end
        if objective == "rout" then return redsLeft(st) - (st.gone[id] and 0 or 1) <= 0 end
        return false
    end
    -- `alive` (the judge's): each unit's chance to live the phase; `felled`: each recruit's
    -- chance our counter killed it; `fell`: the chance a player counter ended the chapter in
    -- the phase (the boss, or a Rout's last enemy, striking and dying: vanilla Ch5 attempt 8's
    -- boss died so on turn 5 with (5,1) still open); `rows` (optional) gets each goal's { id,
    -- kind, gold, worth, before, after }, the plan record's goalWorth
    local function winOf(st, fell) return M.either(winChance(st), fell or 0) end
    -- M.endsIn on the board plan `st` leaves (a Rout's count less the plan's kills)
    local function endsIn(st)
        return M.endsIn(objective, objective == "rout" and redsLeft(st) or 0, byId, winBoss)
    end
    -- Whether a plan advances the level (ADR 0439): it may kill a red unit (our blows, or our
    -- counters in the judged phase: a bait counts), takes a goal (a visit, chest, talk or
    -- rescue), may end the chapter, or wounds a unit the win needs (the boss of a Defeat-boss
    -- chapter, any red of a Rout). A kill, counter-kill or win chance counts only above
    -- M.ADVANCE_MIN (ADR 0458, #744). A march nearer a goal does not advance: nearing is what
    -- the stall reading found idle (an under-cap march that sets a new low is still no idle
    -- plan: admit(), ADRs 0458 and 0476), and a blow that deals nothing wounds nothing. `counters`: each red
    -- enemy's chance our counters kill it in the judged phase. A wound counts only as far as it
    -- outlasts the tile's heal (M.healed, #709): a boss on a fort regains it before it acts.
    -- -> advances, woundOnly: `woundOnly` when a wound that outlasts the heal is all it has. A
    -- kill chance on any red is a return of its own, ahead of the wound read, so a plan whose
    -- wound is all it has has no kill chance this phase (#709: admit() asks it only under the cap).
    -- The lookahead's second-phase kills are not read here: they come from sight.nextPhase, a
    -- search made for finalists after this judge, and advances() runs for every plan.
    -- a chance above M.ADVANCE_MIN, past the ulps a composed chance lands over it (M.admits)
    local function material(p) return not M.admits(p, M.ADVANCE_MIN) end
    local function advances(st, fell, counters)
        if M.tookGoal(st.took) or next(st.carry) or material(winOf(st, fell)) then
            return true, false
        end
        for _, p in pairs(counters) do
            if material(p) then return true, false end
        end
        local kills = {}
        for id, blows in pairs(st.kill) do
            kills[id] = (odds(blows, byId[id].hp))
            if not st.recruits[id] and material(kills[id]) then return true, false end
        end
        for id, hp in pairs(st.enemyHp) do
            local e = byId[id]
            local needed = e and not st.recruits[id]
                and (objective == "rout" or (objective == "boss" and M.isWinBoss(e, winBoss)))
            if needed then
                -- the survivor's HP: the plan's `hp` is a mean over the kill branch too, and a
                -- kill chance up to ADVANCE_MIN did not return above, so its share is no wound
                -- either (#744: a 4% crit, else a miss, would read as a wound on the boss). Exact
                -- for one blow; a chain of blows composes its mean blow by blow and its kill
                -- whole, so there it is near, not exact. `k` < 1: a sure kill returned above
                local k = kills[id] or 0
                local left = e.hp - M.survivorDealt(e.hp, e.hp - hp, k)
                if e.hp - M.healed(healOf(e), e, left) > M.DUST then return true, true end
            end
        end
        return false, false
    end
    -- A goal's chance after the plan's blows on its recruit: our attack's (recruitHit) and our counter's
    -- (felled), each a chance the recruit is gone. The one combination a talker recruit's goal
    -- and a loose recruit's death both use (#730 fix 2, ADR 0452).
    local function sparedOf(st, felled, id, c)
        return c * (1 - (st.recruitHit[id] or 0)) * (1 - (felled and felled[id] or 0))
    end
    local function goalTerm(st, alive, felled, rows, fell)
        local pos, v = positions(st, alive), 0
        local read = turnsOn(st, pos)
        local pWin = winOf(st, fell)
        for _, g in ipairs(goals) do
            local c
            if st.took[g.id] then
                c = 1
            elseif g.kind == "objective" then
                c = pWin + (1 - pWin) * Goals.chance(g, pos, Goals.GAMMA, read)
            else
                c = chanceOf(st, g, pos, read) * (1 - pWin)
                if g.kind == "recruit" then
                    c = sparedOf(st, felled, g.unitId, c)
                end
            end
            v = v + Goals.worth(g, W) * (c - before[g.id])
            if rows then
                rows[#rows + 1] = { id = g.id, kind = g.kind, gold = g.gold,
                                    worth = Goals.worth(g, W), before = before[g.id], after = c,
                                    closes = g.closes }
            end
        end
        -- an owed recruit no one may Talk yet has no goal, but its death costs what a talker
        -- recruit's does: a death's worth of the chance it is gone, by the same combination. Its
        -- reach is whole (1: nothing to reach, no one can Talk it yet), so the chance it stays is
        -- the win's discount and the blows' (#730 fix 2, ADR 0452). Paid by the judged phase and
        -- the lookahead only (`rows`): a menu's or the beam's partial score that pre-pays it
        -- prunes the plan the rank would pick (a kill that is the one admitted plan; #722's
        -- lesson). The rank orders by what the game forbids, and its forfeit already counts it
        for _, id in ipairs(rows and sortedKeys(st.loose) or {}) do
            v = v + W.death * (sparedOf(st, felled, id, 1 - pWin) - 1)
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
        -- a re-listed act (menusFor) is read on its own map: the same act there is another risk
        local k = key(a) .. "#" .. hp .. "#" .. table.concat(ids, ",") .. "#" .. (a.map or "")
        local r = risks[k]
        if not r then
            local die, taken = exposed(a, hp, gone, odds)
            r = loss(W, start, a.unit) * die + W.taken * taken
            risks[k] = r
        end
        return r
    end

    -- what score reads of an act beside the act itself: its unit's HP and cap, its target
    local function annotate(a, u)
        a.unitHp, a.unitMaxHp = u.hp, u.maxhp or u.hp
        a.targetUnit = a.targetId and byId[a.targetId]
    end
    -- a strike's spare (#642) annotated as the menus annotate every offered act, with its
    -- counter's chance to kill (`die`, the record's): read only once a plan takes it (the spare
    -- step, a replan's rest), since most never are. Any other act is annotated already.
    local function readied(b)
        if not b.unitHp then
            annotate(b, byId[b.unitId])
            b.die = select(2, score(b, start, W, style, odds, likeliest)).die or 0
        end
        return b
    end

    -- each unit's acts, its own best first (its score with what it does to the goals),
    -- PER_UNIT of them; every Visit and Chest offered,
    -- with its standing chance to die, for the run's trace (the rule's experiment).
    -- menusOf(list, opens): the menus of Bot.candidates' `list`. `opens` (the acts a plan's
    -- changes add, menusFor's): the tiles the changes freed ("x,y" -> true), every act ending on
    -- one kept past the cut as an aside is: what standing in a doorway or a dead guard's gap is
    -- worth is the unit it shields, which only the judged phase reads (#661). The board's own menus (no `opens`) also record
    -- every Visit, Chest, Talk and Seize offered.
    local offered, talks, seizable = {}, {}, false   -- every Talk and Seize the candidates offered
    local gentle = {}   -- every recruit-sparing act the board's menus offered, before the cut (best.gentle)
    local function menusOf(list, opens)
        local out = {}
        for _, c in ipairs(list) do
            local scored = {}
            for _, a in ipairs(c.acts) do
                annotate(a, c.unit)
                if not opens and (a.act == "visit" or a.act == "chest") then
                    offered[#offered + 1] = { id = a.unitId, charId = a.unit, x = a.move.x,
                                              y = a.move.y, kind = a.act,
                                              die = (exposed(a, a.unitHp, {}, odds)) }
                end
                local v, fx = score(a, start, W, style, odds, likeliest)
                -- the counter's chance to kill the attacker, for the record (botrun's `predicted`
                -- on a player-phase death): every attack act passes through here, mends included
                if a.act == "attack" then a.die = fx.die or 0 end
                if not opens and a.act == "talk" and a.target then talks[a.target] = true end
                if not opens and a.act == "seize" then seizable = true end
                if not opens and a.why == "gentle" then
                    gentle[#gentle + 1] = { unit = a.unitId, act = a.act, slot = a.slot,
                                            x = a.move.x, y = a.move.y, target = a.targetId }
                end
                local gone = fx.gone and { [fx.gone] = true } or {}
                -- what the act alone does to the goals: a march toward one earns nothing of its
                -- own, and ranked without this it was cut from the menu (vanilla Ch2: Eirika's
                -- walk to Ross never reached the beam, and Ross died on turn 4)
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
                local e = endTile(x.a)
                if i <= M.PER_UNIT or (x.a.act == "staff" and x.a.amount)
                        or x.a.why == "hold" or x.a.why == "retreat" or x.a.why == "careful"
                        -- the wait or attack that spares a recruit (Bot.candidates' "gentle",
                        -- #730): its own score never sees the forfeit it avoids, only the
                        -- judged phase
                        or x.a.why == "gentle"
                        -- what a Rescue or Drop saves or opens is the judged phase's to read, and
                        -- its own score never sees the phase; a step aside's is the teammate's
                        -- act it frees the tile for (Bot.candidates' aside), which its own score
                        -- never sees either
                        or x.a.act == "rescue" or x.a.act == "drop" or x.a.why == "aside"
                        or (opens and opens[e.x .. "," .. e.y]) then
                    menu[#menu + 1] = x.a
                end
            end
            out[#out + 1] = { unit = c.unit, acts = menu }
        end
        return out
    end
    local menus = menusOf(cands)

    -- The menus a plan's later units choose from on the board it leaves (#661, #670). Each
    -- unit's acts were listed once, on the board before anyone acts; a plan that opens a door
    -- or breaks a wall (st.opened), or kills an enemy (st.gone), frees tiles no act was listed
    -- on: in vanilla Ch8 (seed 4002) 101 plans opened (20,7) and none had a unit step into the
    -- doorway or strike past it, and no plan in ~1,300 ever moved a unit onto a tile an earlier
    -- act's kill freed. So each unit keeps its board menu, and gains the acts from the tiles the
    -- plan's changes add to its reach: read on the board with every change applied
    -- (sight.changed), and listed over those tiles alone (Bot.candidates' opts.only and
    -- opts.tiles). Only a unit whose board reach comes beside a changed tile is read at all: a
    -- freed tile is entered from one beside it. A unit's other acts keep their board exposure;
    -- the judged phase plays the changed board (ADR 0431, the cost). The read is on the board
    -- the plan's changes leave, the units it moved still on their board tiles. Once per set of
    -- changes (extend's `changeKey`) this decision;
    -- extend keeps a used unit or a taken tile out. Each added act carries its board (`map`),
    -- so the exposure memo tells it apart, and the changes it needs (`needs`), which extend
    -- holds a plan to: a mend, heal swap or assault rebuilds a plan with one act swapped. An
    -- offered replay (opts.offer) reads its acts on the fogged board, which it cannot do on the
    -- changed one (botrun's DIAG `relisted` says so), and a sight without the read (test fakes)
    -- has none: both keep the board's menus.
    local relisted = {}
    -- The enemies a plan's changes count dead: the reds of its `gone` (a Talk's recruit is one
    -- too, red until it joins); the board's units are looked up here for both menusFor and
    -- extend's key.
    -- the recruits a plan's acts Talk over, as a set: each joins the player on its tile
    -- (#766), off the enemy side (fx.gone) but never dead, and its tile never freed
    local function talkedIn(acts)
        local out = {}
        for _, a in ipairs(acts) do
            if a.act == "talk" then out[a.targetId] = true end
        end
        return out
    end
    local function deadReds(gone, acts)
        local out, talked = {}, talkedIn(acts)
        for id in pairs(gone) do
            if byId[id] and byId[id].faction == "red" and not talked[id] then out[id] = true end
        end
        return out
    end
    -- A plan's change set as one key: its doors and walls, then its dead reds; nil for none.
    -- extend keeps it (`changeKey`) as it adds either, so menusFor never rebuilds it per state.
    local function changeKeyOf(opened, gone, acts)
        local dead = deadReds(gone, acts)
        if next(opened) == nil and next(dead) == nil then return nil end
        return table.concat(sortedKeys(opened), ";") .. "|" .. table.concat(sortedKeys(dead), ";")
    end
    local function menusFor(st)
        if offer or not sight.changed or not st.changeKey then return menus end
        local mk = st.changeKey
        if relisted[mk] then return relisted[mk] end
        local gone = deadReds(st.gone, st.acts)
        -- the changed tiles: each door's or wall's whole change where the sight says
        -- (sight.mapChange: a gate two tiles deep), else its own tile; each dead enemy's
        -- `terrainAfter`: the terrain each tile of a door's or wall's change takes (the roof
        -- read, Board.unroofed: a dead enemy's tile is no map change)
        local changed, terrainAfter = {}, {}
        for k in pairs(st.opened) do
            changed[k] = true
            local x, y = k:match("^(%d+),(%d+)$")
            for _, t in ipairs(sight.mapChange and sight.mapChange(tonumber(x), tonumber(y)) or {}) do
                changed[t.x .. "," .. t.y] = true
                terrainAfter[t.x .. "," .. t.y] = t.terrain
            end
        end
        for id in pairs(gone) do changed[byId[id].x .. "," .. byId[id].y] = true end
        -- each unit's board reach, and whether it comes beside a changed tile
        local shut, near = {}, {}
        for _, m in ipairs(menus) do
            local u = m.unit
            local set = { [u.x .. "," .. u.y] = true }
            for _, t in ipairs((ctx.reaches or {})[u.id] or {}) do set[t.x .. "," .. t.y] = true end
            shut[u.id] = set
            for k in pairs(set) do
                local x, y = k:match("^(%d+),(%d+)$")
                x, y = tonumber(x), tonumber(y)
                if changed[k] or changed[(x + 1) .. "," .. y] or changed[(x - 1) .. "," .. y]
                        or changed[x .. "," .. (y + 1)] or changed[x .. "," .. (y - 1)] then
                    near[#near + 1] = u
                    break
                end
            end
        end
        local list = {}
        if #near > 0 then
            -- the board the read is on: the dead gone. The units the plan already moved stay on
            -- their board tiles (ADR 0431: an ally never blocks a march, extend rejects a tile
            -- the plan filled, and the judged phase stages every moved unit where the plan puts
            -- it, so the stale tiles only order a unit's new acts for the PER_UNIT cut)
            -- A unit hidden under a roof the plan's change removes is on the field on that board
            -- (TriggerMapChange's UpdateRoofedUnits: Board.unroofed, as sight.unroof applies it):
            -- the units a door's room holds are targets for the acts past it (#766: vanilla
            -- Ch14's (22,17) door; the one try that recruited Rennac struck the squad it revealed
            -- on the door's own turn)
            local b = {}
            for k, v in pairs(board) do b[k] = v end
            b.units = {}
            for _, u in ipairs(board.units) do
                if not gone[u.id] then
                    local out = u.onMap and Board.unroofed(u.state, terrainAfter[u.x .. "," .. u.y])
                    if out then
                        u = copy(u)
                        u.state, u.onField = out, Board.onFieldState(out, u.x, u.y)
                    end
                    b.units[#b.units + 1] = u
                end
            end
            -- what each act of this read needs of the plan: all of its changes
            local needs = { opened = copy(st.opened), gone = gone }
            list = sight.changed({ opened = st.opened, gone = gone }, function()
                local only, tiles, any = {}, {}, false
                for _, u in ipairs(near) do
                    for _, t in ipairs(sight.reach(u, true) or {}) do
                        local k = t.x .. "," .. t.y
                        if not shut[u.id][k] then
                            tiles[u.id] = tiles[u.id] or {}
                            tiles[u.id][k], only[u.id], any = true, true, true
                        end
                    end
                end
                if not any then return {} end
                local o = {}
                for k, v in pairs(opts or {}) do o[k] = v end
                o.only, o.tiles = only, tiles
                o.talks = ctx.talks   -- the board's Talk memo (Bot.candidates)
                local out = Bot.candidates(b, sight, style, o)
                -- an act whose own tile is a new one (a Vulnerary in place is the board's); it
                -- and its spares carry the board they were read on (`map`, the exposure memo's)
                -- and what they need of the plan (`needs`, extend's)
                for _, c in ipairs(out) do
                    local kept = {}
                    for _, a in ipairs(c.acts) do
                        if tiles[c.unit.id][a.move.x .. "," .. a.move.y] then
                            a.map, a.needs = mk, needs
                            for _, sp in ipairs(a.spares or {}) do sp.map, sp.needs = mk, needs end
                            kept[#kept + 1] = a
                        end
                    end
                    c.acts = kept
                end
                return out
            end)
        end
        local added = {}
        for _, m in ipairs(menusOf(list, changed)) do added[m.unit.id] = m.acts end
        local out = {}
        for _, m in ipairs(menus) do
            local more = added[m.unit.id]
            if more and #more > 0 then
                local acts = {}
                for i, a in ipairs(m.acts) do acts[i] = a end
                for _, a in ipairs(more) do acts[#acts + 1] = a end
                out[#out + 1] = { unit = m.unit, acts = acts }
            else
                out[#out + 1] = m
            end
        end
        relisted[mk] = out
        return out
    end

    -- `st` with `a` (unit `uid`'s act) added, the board the plan leaves updated; nil when the
    -- act cannot follow the plan (its tile taken, its target gone, a heal on a moved unit or
    -- on no one hurt)
    -- Whether the plan holds every change a re-listed act (menusFor) was read on: its doors and
    -- walls open, its enemies dead. A mend, heal swap or assault rebuilds a plan with one act
    -- swapped; a doorway act whose door was swapped out must not follow.
    local function holds(st, needs)
        for k in pairs(needs.opened) do
            if not st.opened[k] then return false end
        end
        for id in pairs(needs.gone) do
            if not st.gone[id] then return false end
        end
        return true
    end

    -- An act on an ally's tile (its `vacate`) brings that ally's move off it, as a player moves
    -- the ally first: its best act by its own score (a.own) that ends on neither tile the act
    -- needs. Without it the act waited for some other part of the plan to move the ally first,
    -- and nothing did: vanilla Ch14 s4003 (#766, `r766f`), Colm and Innes were offered the
    -- (17,2) door from (18,1) and (17,1) for nine turns, the allies who stood there held, no
    -- plan judged held the door, and the board repeated until the run was cut. One step deep:
    -- the ally's own move is not given an ally's in turn.
    local candById
    -- each unit's candidates by its id (stepAside's ally, the heal swap's unit), built once
    local function candOf(id)
        if not candById then
            candById = {}
            for _, c in ipairs(cands) do candById[c.unit.id] = c end
        end
        return candById[id]
    end
    local function stepAside(st, a, extendFn)
        local c = candOf(a.vacate)
        if not c then return nil end
        local need, at = a.move.x .. "," .. a.move.y, endTile(a)
        local order = {}
        for _, b in ipairs(c.acts) do
            local e = endTile(b)
            local tile = e.x .. "," .. e.y
            if tile ~= need and tile ~= at.x .. "," .. at.y
                    and b.move.x .. "," .. b.move.y ~= need then
                order[#order + 1] = b
            end
        end
        table.sort(order, function(x, y)
            if (x.own or 0) ~= (y.own or 0) then return (x.own or 0) > (y.own or 0) end
            return key(x) < key(y)
        end)
        for _, b in ipairs(order) do
            local n = extendFn(st, b, a.vacate, true)   -- one step deep
            if n then return n end
        end
        return nil
    end

    -- `exact`: the act alone, never the ally's step aside: a replay of acts a plan already
    -- holds (complete, rebuild, the mends, the kept rest, the fog reorder) puts back the moves it
    -- had, and an aside there would silently swap an ally's own act for another
    local extend
    extend = function(st, a, uid, exact)
        if a.vacate and not st.used[a.vacate] and not exact and not st.used[uid] then
            st = stepAside(st, a, extend) or st
        end
        -- the tile it ends on (a Canto move's), which the plan then holds; the act's own tile
        -- must be free too, when it moves on from it
        local at = endTile(a)
        local tile = at.x .. "," .. at.y
        if st.used[uid] or st.tiles[tile] or st.tiles[a.move.x .. "," .. a.move.y]
                or (a.targetId and st.gone[a.targetId])
                or (a.needs and not holds(st, a.needs))
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
        local v, fx = score(a, st, W, style, odds, likeliest)
        if fx.blocked then return nil end
        local n = { base = st.base + v, acts = copy(st.acts), expect = copy(st.expect),
                    used = copy(st.used), tiles = copy(st.tiles), gone = copy(st.gone),
                    enemyHp = copy(st.enemyHp), hp = copy(st.hp), took = copy(st.took),
                    recruitHit = copy(st.recruitHit), win = st.win, bossWant = st.bossWant,
                    fought = copy(st.fought), healed = copy(st.healed), walls = copy(st.walls),
                    opened = copy(st.opened), objective = objective, winBoss = winBoss,
                    recruits = st.recruits, loose = st.loose,
                    gameOver = st.gameOver,
                    kill = copy(st.kill), carry = copy(st.carry), wear = copy(st.wear),
                    redWear = copy(st.redWear), changeKey = st.changeKey, healOf = st.healOf }
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
        if fx.wear then n.wear[uid] = fx.wear end
        if fx.redWear and fx.redWear.uses > 0 then
            local slots = copy(n.redWear[fx.redWear.id] or {})
            slots[fx.redWear.slot] = (slots[fx.redWear.slot] or 0) + fx.redWear.uses
            n.redWear[fx.redWear.id] = slots
        end
        if fx.opened then n.opened[fx.opened] = true end
        -- the change set's key, kept as either grows (menusFor's memo reads it)
        if fx.opened or fx.gone then n.changeKey = changeKeyOf(n.opened, n.gone, n.acts) end
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
            local menusNow, placed = menusFor(st), true
            for _, m in ipairs(menusNow) do placed = placed and st.used[m.unit.id] == true end
            -- a plan whose every unit is placed already (an ally's step aside placed two in one
            -- depth, ADR 0469) goes on as it is: it would extend to nothing at the last depth
            -- and lose its place to plans one act behind it
            if placed then
                local sig = {}
                for _, x in ipairs(st.acts) do sig[#sig + 1] = key(x) end
                sig = table.concat(sig, "|")
                if not seenSig[sig] then seenSig[sig] = true; nxt[#nxt + 1] = st end
            end
            for _, m in ipairs(placed and {} or menusNow) do
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
                    local n = a.why == "hold" and extend(st, a, c.unit.id, true)
                    if n then st = n break end
                end
            end
        end
        return st
    end

    -- `st` with `acts` added in order, each where it still fits, as the mend keeps the rest of a
    -- plan. `choose(x, st)` (optional) returns false to leave x out, or an act to try in x's
    -- place first, x itself when that one no longer fits.
    local function rebuild(st, acts, choose)
        for _, x in ipairs(acts) do
            local y = choose and choose(x, st)
            if y ~= false then
                st = (y and extend(st, y, y.unitId, true)) or extend(st, x, x.unitId, true) or st
            end
        end
        return st
    end

    -- The assault (Nicolas, 2026-10-28): on a Defeat Boss map, every unit that can strike the
    -- boss this phase does, the heaviest expected blow first, until the plan counts it dead. On
    -- a Seize map, the enemy holding the seize tile (M.throne) is that boss.
    -- One unit's strike alone rarely beats holding -- the counter, then the boss's own phase
    -- -- so the beam cuts it, and the combination is never tried; this plan is that
    -- combination, and the judge weighs it like any other. While too few units reach the boss
    -- it judges badly, and holding out of reach wins: the rounds of no combat while backup
    -- arrives.
    -- Only a striker that deals damage is seated (#641): a blow that cannot hurt the boss buys
    -- its counter and nothing else (vanilla E_20: three javelins and hand axes on Morva, charId
    -- 0x41, each a whole death in every plan). When the strikers do not count the boss dead
    -- this phase, the bait is judged beside it: the heaviest striker waits, holding that
    -- strike's weapon, on the first of its strike tiles (heaviest first) the boss is read to
    -- strike and its counter to hurt (Bot.baitAt), the rest holding, so the boss's own strike
    -- meets the counter and the next turn finishes it (the lookahead's win, M.secondRead). It is
    -- one more plan for the rank: no ban and no weight beyond its outcomes (ADR 0396). The boss
    -- is the enemy whose death ends the chapter (M.endsIn), or the throne's holder.
    -- -> the assault (nil with fewer than two strikers: one is a plan the beam has), the bait
    -- (nil when the strike counts the boss dead, or no tile offers it)
    local function assault()
        local boss
        local throne, ends = M.throne(sight.objective, ctx.enemies), endsIn(start)
        for _, e in ipairs(ctx.enemies) do
            if ends(e.id) or e.id == throne then boss = e end
        end
        if not boss then return nil end
        local strikers = {}
        for _, c in ipairs(cands) do
            local opts = {}
            for _, a in ipairs(c.acts) do
                if a.act == "attack" and a.targetId == boss.id and a.f then
                    local kill, dealt = odds({ a.f.dealt }, boss.hp)
                    if dealt > M.DUST then opts[#opts + 1] = { a = a, dealt = dealt, kill = kill } end
                end
            end
            table.sort(opts, function(x, y)
                if x.dealt ~= y.dealt then return x.dealt > y.dealt end
                return key(x.a) < key(y.a)
            end)
            if #opts > 0 then strikers[#strikers + 1] = { uid = c.unit.id, opts = opts } end
        end
        if #strikers == 0 then return nil end
        table.sort(strikers, function(x, y)
            if x.opts[1].dealt ~= y.opts[1].dealt then return x.opts[1].dealt > y.opts[1].dealt end
            return x.uid < y.uid
        end)
        local plan, dead
        if #strikers == 1 then
            -- no assault to build: whether the lone strike counts the boss dead is its own
            -- kill chance, as extend reads it (score's fx.gone)
            for _, o in ipairs(strikers[1].opts) do dead = dead or o.kill >= M.GONE end
        else
            -- each tile's takers; a striker takes, of its heaviest blows, the tile the fewest
            -- of those after it could use -- a 1-2 range unit leaves the boss's side to the melee
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
            plan, dead = complete(st), st.gone[boss.id]
        end
        local bait
        local heavy = strikers[1]
        local u = byId[heavy.uid]
        for _, o in ipairs((not dead and u and Bot.baitAt) and heavy.opts or {}) do
            local w = Bot.baitAt(ctx, u, boss, o.a.move, o.a.slot)
            if w then
                w.why = "bait"
                annotate(w, u)
                bait = extend(start, w, u.id)
                if bait then break end
            end
        end
        return plan, bait
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
                local t = turnsTo(c.unit, goal.tile, endTile(a), goal.beside)
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
    -- uncertain kills left to the likeliest way past BRANCH (never silent)
    local cost = { phases = 0, averaged = 0, unsplit = 0, floored = 0, unjoined = 0,
                   area_positional = 0, area_truncated = 0,
                   look = { decisions = 1, triggered = 0, extended = 0, skipped_budget = 0,
                            calls = 0, cpu_s = 0, wear = 0, wear_cpu_s = 0, wear_skipped = 0 } }
    -- a green unit's death is paid at a player unit's price (ADR 0381: vanilla Ch2's Ross, a
    -- Talk recruit, killed on turn 2 in every style while only blue deaths were paid), though
    -- only an escort or a green the ending tests spoils the clean clear (#788). No plan moves
    -- one: it meets the phase where it stands
    local greens = {}
    -- A carried green is one too (board's carriedBy): carried it meets no strike, and a plan
    -- that drops it meets the phase on its drop tile
    for _, u in ipairs(board.units) do
        if u.faction == "green" and not u.dead and (u.onField or u.carriedBy) then
            greens[#greens + 1] = u
        end
    end
    -- the rank's admission (FR-009 to FR-011) from each protected unit's death chance against
    -- the cap: set once the phase is judged, again after the wear and the idle rule, and when
    -- the lookahead adds a second phase, which changes the rank's numbers but not admission
    -- (ADR 0470). The first call is the next phase's alone, and its numbers are kept (`first_*`,
    -- a protected unit's `first`): over the cap they rank ahead of the two-phase ones
    -- (M.outranks), which the lookahead's call overwrites.
    -- Whether healer `q` (a plan's entry: unit, x, y), from where the plan leaves it, can stand
    -- within one of its staves' reach of `p`'s tile next turn: a tile 1 to that reach away
    -- (Manhattan, as the game's staff range), on the map, that its own MOV gets it to.
    -- sight.turnsTo with the healer's tile as its `tile` (GenerateExtendedMovementMap: the costs
    -- out from it, units not blocking, as for the AI), read at each tile. Memoised for the
    -- decision per healer, its tile and the tile healed.
    local healReach = {}
    local function healsNext(q, p)
        local k = q.unit.id .. "@" .. q.x .. "," .. q.y .. ">" .. p.x .. "," .. p.y
        if healReach[k] == nil then
            local r, ok = 0, false
            for _, sv in ipairs(sight.staves and sight.staves(q.unit) or {}) do
                r = math.max(r, sv.range or 1)
            end
            local healer, map = { x = q.x, y = q.y }, board.map
            for dx = -r, r do
                local span = r - math.abs(dx)
                for dy = -span, span do
                    local x, y = p.x + dx, p.y + dy
                    if not ok and (dx ~= 0 or dy ~= 0) and x >= 0 and y >= 0
                        and x < map.w and y < map.h then
                        local t = sight.turnsTo(q.unit, healer, { x = x, y = y })
                        ok = t ~= nil and t <= 1 + M.DUST
                    end
                end
            end
            healReach[k] = ok
        end
        return healReach[k]
    end
    -- Whether a plan not advancing the level is inadmissible (ADR 0439): opts.idle, the bot's own
    -- stall reading (botrun's GOAL_QUIET), and at least one plan judged that advances. With none,
    -- every plan ties on `idle`, so it stays off. Set by pick(), which re-admits every plan judged
    -- when it moves.
    local idleOn = false
    -- Whether a plan advances the level for the idle rule: under the death-risk cap any
    -- advance counts; over it, a wound that only outlasts the heal does not (#709, ADR 0441: a
    -- seven-unit assault netting 1 HP on a fort boss, max_die 0.999, outranked every hold). Read
    -- off the cap's own excess (`st.capExceed`), which admit() sets before this is asked.
    local function advancing(st)
        return st.advances and (not st.woundOnly or st.capExceed == 0)
    end
    -- The cap reads the next enemy phase and the wear (ADR 0421), never the lookahead's second
    -- phase (ADR 0470): `pr.capDie`, each protected unit's death chance as it stood before the
    -- lookahead raised `pr.die` (pr.die itself before then). The both-phase excesses below only
    -- break ties (M.outranks): over 300 stored runs the second phase's readings of 0.05 or more
    -- summed to 345 deaths where 54 units died, and admitting by them marked plans safe on the
    -- next phase as over the cap.
    -- the goals' readings on the board plan `st` leaves (nearOn), read once per plan
    local function nearOf(st)
        if not st.nearRead then
            local pos = positions(st)
            st.nearRead = nearOn(turnsOn(st, pos), pos)
        end
        return st.nearRead
    end
    local function admit(st)
        local rank = st.rank
        local firstCall = rank.first_game_over == nil
        if firstCall then rank.first_game_over = rank.game_over end
        rank.admitted, rank.max_exceed, rank.sum_exceed, rank.max_die, rank.sum_die =
            true, 0, 0, 0, 0
        local capExceed = 0
        for _, pr in ipairs(st.protected) do
            if firstCall then pr.first = pr.die end
            local over = M.admits(pr.die, cap) and 0 or pr.die - cap
            local capDie = pr.capDie or pr.die
            local capOver = M.admits(capDie, cap) and 0 or capDie - cap
            capExceed = math.max(capExceed, capOver)
            rank.admitted = rank.admitted and capOver == 0
            rank.max_exceed = math.max(rank.max_exceed, over)
            rank.sum_exceed = rank.sum_exceed + over
            rank.max_die = math.max(rank.max_die, pr.die)
            rank.sum_die = rank.sum_die + pr.die
        end
        if firstCall then rank.first_max_exceed, rank.first_sum_exceed = rank.max_exceed, rank.sum_exceed end
        st.capExceed = capExceed
        -- a plan that does not advance is no plan once the stall reading fired (ADR 0439); one
        -- under the cap that brings a goal nearer than the army has ever had it is not idle
        -- (#744, #698): the cap already keeps it safe, and idling it handed the turn to a
        -- 0.93-death bait. Against the best so far, not this board: a shuffle always nears
        -- something, and read against this turn it played the all-wait plan over every boss
        -- wound for 30 turns (Ch15, Ch21). `idleOn` still turns on only for a real advance
        -- (pick()), so a march never switches the rule on.
        local idle = idleOn and not advancing(st)
            and not (capExceed == 0 and M.setsLow(nearOf(st), bestNear))
        rank.idle = idle and 1 or 0
        rank.admitted = rank.admitted and rank.idle ~= 1
    end
    -- One enemy phase outcome's strikes on `units` ({ id, charId, hp, maxhp?, back?, fought?,
    -- heal? }): per id { d (its chance to die), t (HP taken), sh (HP short at the end, when
    -- maxhp is given), n (strikes) }, and the chance no unit whose death ends the game dies. A
    -- unit with `back` (our counter's blows on it, from the plan's attack, left to the likeliest
    -- way)
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
    local function judge(st)
        local planned, at, nth = {}, {}, {}
        for i, a in ipairs(st.acts) do at[a.unitId], nth[a.unitId] = a, i end
        for _, u in ipairs(ctx.blues) do
            local a = at[u.id]
            local at = a and endTile(a)
            local attacks = a and a.act == "attack"
            -- wear: the weapon uses its act is expected to spend off the item in bag slot
            -- wearSlot, at the HP the plan leaves its target (score's fx.wear), so the phase
            -- reads it with what is left (#644)
            local w = st.wear[u.id]
            planned[#planned + 1] = { unit = u, x = at and at.x or u.x, y = at and at.y or u.y,
                                      hp = st.hp[u.id] or u.hp,
                                      -- a unit the plan acts ends its action there, the nth
                                      -- act: the game runs the chapter's Misc events after it
                                      -- (#712, waitsIn)
                                      acted = a ~= nil, order = nth[u.id],
                                      -- a strike's weapon, or a wait's held one (a bait's,
                                      -- a gentle wait's or strike's): the one its counter answers with
                                      slot = (attacks or (a and a.act == "wait")) and a.slot or nil,
                                      wearSlot = w and w.slot, wear = w and w.uses }
        end
        local reds = {}
        -- each uncertain kill, and each counter that can leave its attacker on more than one HP,
        -- played every way it goes: one way alone (an enemy gone at a kill >= M.GONE, else standing
        -- at its likeliest HP; our attacker at its likeliest HP after the counter) hides the way
        -- the rolls go otherwise. Vanilla Ch5 turn 5: Eirika's attack killed an enemy the plan kept
        -- standing, and Joshua's AI turned on her. Manchego Stars ch03 (T100b): Wolfram's attack
        -- missed, the counter left him on 3 HP, and the AI that had passed him by at his mean HP
        -- (before ADR 0463) killed him. A unit whose blow is the only one on its target plays the
        -- exchange's own pairs (sight's `joint`), so a counter is played only where our blow did
        -- not kill first; any other counter is played on its own spread. The most uncertain are
        -- played first, BRANCH of them at most; one that would take the ways past 2^BRANCH keeps
        -- its likeliest HP and a narrower one after it is still played. Each left unsplit is
        -- counted (`averaged`) so it is never silent.
        local dims, gone = {}, copy(st.gone)
        local only = {}   -- target id -> the unit whose blow is the plan's only one on it
        for uid, x in pairs(st.fought) do
            if x.exchange and #(st.kill[x.exchange.target] or {}) == 1 then
                only[x.exchange.target] = uid
            end
        end
        local jointDone = {}   -- the units whose own exchange's joint a dim above plays
        for id, blows in pairs(st.kill) do
            -- the plan's blows on it together, at its own HP: each blow alone was scored at the
            -- HP the earlier ones leave on average, which can call a sure kill short. Gone or
            -- standing by that composed chance. The board the phase meets holds it at the
            -- likeliest HP all the blows leave it alive at (`reds`, ADR 0463), never the mean
            -- st.enemyHp scores by; a way that lives keeps the same (`left`)
            local hp = byId[id].hp
            local p = odds(blows, hp)
            reds[id] = likeliest(blows, hp)
            gone[id] = p >= M.GONE or nil
            local uid = only[id]
            if p > 0 and p < 1 and uid then
                local list = sight.jointAt(st.fought[uid].exchange.joint, hp)
                for _, w in ipairs(list) do w.uid = uid end
                dims[#dims + 1] = { id = id, key = "k" .. id, ways = list }
                jointDone[uid] = true
            elseif p > 0 and p < 1 then
                dims[#dims + 1] = { id = id, key = "k" .. id, ways = {
                    { p = p, dead = true },
                    { p = 1 - p, dead = false, left = reds[id] } } }
            end
        end
        for uid, x in pairs(st.fought) do
            if not jointDone[uid] then
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
        -- the phase as the likeliest way leaves it: what the lookahead plays on (nextPhase)
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
        -- The blues as way `w` leaves them. A re-listed act (menusFor) needs enemies dead; where
        -- a kill missed in this way (w.gone lacks one the act needs), that act is not played:
        -- M.surprise replans before the next act, so its unit still stands on its board tile,
        -- not the planned one, which may be the living enemy's own (the phase's standOn would
        -- take the enemy's cell). That unit has no counter to play either (`unacted`); its
        -- `hit` entry (below) keeps the HP the planned act left it, a pessimism ADR 0431 names.
        -- A unit whose act comes after one not played, and ends on that unit's board tile, could
        -- move there only once the other had left: it stays put too (else two blues share a tile
        -- and the phase's standOn overwrites one). The plan's order, one pass, so a chain follows.
        local function bluesIn(w)
            local back, held = {}, {}
            for _, a in ipairs(st.acts) do
                local lost = false
                for id in pairs(a.needs and a.needs.gone or {}) do
                    lost = lost or not w.gone[id]
                end
                local e = endTile(a)
                if lost or held[e.x .. "," .. e.y] then
                    local u = byId[a.unitId]
                    back[a.unitId], held[u.x .. "," .. u.y] = true, true
                end
            end
            local list = planned
            for i, p in ipairs(planned) do
                if back[p.unit.id] then
                    if list == planned then list = copy(planned) end
                    list[i] = { unit = p.unit, x = p.unit.x, y = p.unit.y, hp = p.unit.hp,
                                unacted = true, acted = false }
                end
            end
            return inWay(list, w, function(p) return not p.unacted and p.unit.id or nil end)
        end
        local blues0 = bluesIn({ gone = gone, dead = {}, hp = {} })
        -- the recruits the plan Talks over join the player on their tiles (#766): the judged
        -- phase stands each as a blue unit (sight's plan.joined), where the reds may strike it,
        -- so its death is read as a player unit's (`ours` below), never left out with the gone
        local joined = talkedIn(st.acts)
        local trades = M.tradesIn(st.acts)
        st.phase = { blues = blues0, waits = M.waitsIn(planned, {}, blues0), gone = gone, reds = reds,
                     redWear = st.redWear, joined = joined,
                     opened = st.opened, carry = st.carry, trades = trades }
        local ways = { { p = 1, gone = gone, reds = reds, hp = {}, dead = {} } }
        st.branched, st.floored = 0, 0
        for _, d in ipairs(dims) do
            if st.branched >= M.BRANCH then break end
            -- a dim too wide for the ways left keeps the likeliest way; a narrower one after it is
            -- still played
            if #ways * #d.ways <= 2 ^ M.BRANCH then
                local nxt, split = {}, false
                for _, w in ipairs(ways) do
                    -- a way splits on this kill only while the chance off its likeliest side is at
                    -- least sight's floor of the whole plan (ADR 0415); below it the way keeps its
                    -- likeliest side, as a dim past BRANCH does. A counter's dim of three or more
                    -- ways may still leave one of its ways rarer than the floor: the bound is on
                    -- the chance off the likeliest, and BRANCH bounds the ways
                    if w.p * d.unsure < floor then
                        nxt[#nxt + 1] = w
                        st.floored = st.floored + 1
                    else
                        split = true
                        for _, o in ipairs(d.ways) do
                            local n = { p = w.p * o.p, gone = w.gone, reds = w.reds, hp = w.hp,
                                        dead = w.dead }
                            if o.dead ~= nil then
                                n.gone = copy(w.gone)
                                n.gone[d.id] = o.dead or nil
                                if not o.dead then
                                    n.reds = copy(w.reds)
                                    n.reds[d.id] = o.left
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
                                    n.hp[o.uid] = Board.addHp(u.hp - o.back, st.healed[o.uid] or 0, u.maxhp)
                                end
                            end
                            nxt[#nxt + 1] = n
                        end
                    end
                end
                ways = nxt
                -- a kill every way floored was split nowhere: it is left to the likeliest way
                if split then st.branched = st.branched + 1 end
            end
        end
        st.averaged = #dims - st.branched
        local strikes, outcomes, top, total = {}, {}, nil, 0
        -- a plan that takes the Seize ends the chapter there: the game plays no enemy phase
        -- after it, so none is judged (ADR 0405). Read against one, the Seize was over the cap
        -- for a death that could not happen (vanilla Ch8, run goal8b, campaign 4001 turn 19: the
        -- thief's 63.5%, far from the throne; he died and the win came a turn later). A counter
        -- to a blow struck before the Seize is still the cap's (st.fought, below).
        local phase = not seizesIn(st) and sight.enemyPhase
        -- the counter kills the phases left unsplit (sight's `unsplit`, M.phaseWays): counted
        -- apart from `averaged`, which stays the plan's own uncertain kills past BRANCH
        local unsplit = 0
        local ours = {}   -- [recruit id] = its blue id in the phase (sight's .joined)
        local unjoined = 0   -- the recruits no blue slot was free for (sight's .unjoined)
        for i, w in ipairs(ways) do
            if phase then cost.phases = cost.phases + 1 end
            if now then now.phases = cost.phases end
            local blues = bluesIn(w)
            local s = phase and phase({ blues = blues, waits = M.waitsIn(planned, w.dead, blues), gone = w.gone,
                                        reds = w.reds, joined = joined,
                                        redWear = st.redWear, mass = w.p,
                                        opened = st.opened, carry = st.carry,
                                        trades = trades }) or {}
            unsplit = unsplit + (s.unsplit or 0)
            unjoined = math.max(unjoined, s.unjoined or 0)
            cost.area_positional = cost.area_positional + (s.areaPositional or 0)
            cost.area_truncated = cost.area_truncated + (s.areaTruncated or 0)
            for _, o in ipairs(s.outcomes or { { p = 1, strikes = s } }) do
                outcomes[#outcomes + 1] = { p = w.p * o.p, strikes = o.strikes, way = i }
                total = total + w.p * o.p
            end
            if not top or w.p > top then strikes, top = s, w.p end
            -- each joined recruit's blue id, the one the phase's strikes on it carry: the
            -- game's free slot, alike in every way
            for id, blue in pairs(s.joined or {}) do ours[id] = blue end
        end
        cost.averaged = cost.averaged + st.averaged
        cost.unsplit = cost.unsplit + unsplit
        cost.unjoined = math.max(cost.unjoined, unjoined)
        cost.floored = cost.floored + st.floored
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
        -- a green the plan Talks over is a player unit in this phase (`recruited` below), its
        -- green id gone from the board: it is read once, as a player unit
        local greens = greens
        if next(ours) then
            local kept = {}
            for _, g in ipairs(greens) do
                if not ours[g.id] then kept[#kept + 1] = g end
            end
            greens = kept
        end
        for _, g in ipairs(greens) do strikers[g.id] = {} end
        for _, p in ipairs(planned) do strikers[p.unit.id] = {} end
        -- the recruits the plan Talks over, each as the phase stands it: a player unit, under
        -- its blue id, at the HP it has, with its own charId
        local recruited = {}
        for _, id in ipairs(sortedKeys(ours)) do
            local r = byId[id]
            recruited[#recruited + 1] = { id = ours[id], charId = r.charId, x = r.x, y = r.y,
                                          hp = st.enemyHp[id] or r.hp, from = id }
            strikers[ours[id]] = {}
        end
        -- per recruit, its chance our counter kills it (the phase's own `felled`) and the units
        -- on the player's side it strikes, whose other acts may save it (vanilla Ch5: Joshua,
        -- killed by Seth's counter on turn 3, the planner paying nothing for it)
        local felled, struckBy, fell, winStruck = {}, {}, 0, {}
        local countered = {}   -- per red enemy, the chance our counters kill it in the phase
        local learnt = 0   -- the experience our counters are expected to earn in the phase
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
        for _, r in ipairs(recruited) do
            hit[#hit + 1] = { id = r.id, charId = r.charId, hp = r.hp }
        end
        st.phase.hit = hit
        -- per way: a counter it plays struck on the HP it left (no chain: the counter is
        -- already in that HP), a unit the counter killed out of the phase
        local hitOf = {}
        for i, w in ipairs(ways) do
            hitOf[i] = inWay(hit, w, function(u) return u.id end, "back")
        end
        -- The wear (ADR 0421): whether a heal of the army's can reach a unit of the plan
        -- before the enemy phase after the next. None can when it holds none of its own
        -- (sight.salve) and no staff of the army's gets within its reach next turn (healsNext).
        -- Its HP then carries from phase to phase.
        local plannedBy, unhealed = {}, {}
        for _, p in ipairs(planned) do plannedBy[p.unit.id] = p end
        -- -> the enemy phases the unit meets before a heal of the army's can reach it: 1 when one
        -- reaches it next turn, M.WEAR at most
        local function carries(id)
            if unhealed[id] ~= nil then return unhealed[id] end
            local p, n = plannedBy[id], 1
            if p ~= nil and sight.salve ~= nil and sight.turnsTo ~= nil and not sight.salve(p.unit) then
                n = M.WEAR
                for _, q in ipairs(planned) do
                    if q ~= p and healsNext(q, p) then
                        n = 1
                        break
                    end
                end
            end
            unhealed[id] = n
            return n
        end
        local ends = endsIn(st)
        -- The key a thief takes in the phase (#711): per unit a thief robs of its last chest
        -- opener in some outcome, the chance it lives AND keeps one, summed per outcome (the
        -- game's own AI decided the theft, sight's pilfer; a plan that moves the holder out of
        -- reach, or kills the thief, reads none). A chest it would have opened is worth that
        -- much of what it was, and a way where the thief also kills the holder counts once.
        -- A theft of an item the game ranks above the stat boosters (th.spoils) by a thief that
        -- keeps it (not th.drops: its death gives it back, and clean is the end state) costs the
        -- clean clear whatever else it takes: a forfeit of its own (`spoiled`, robbed id -> its
        -- thieves' ids, kept as st.thieves for the mend, ADR 0475). A holder robbed of its last
        -- opener in a way past DUST is the mend's too (`locked`, kept as st.lockThieves): the
        -- beam never sees the chests it loses (vanilla Ch16 s4005, R5: Eirika's Chest Key).
        -- What either case takes (`stolen`, robbed id -> the item ids, kept as st.stolen) is
        -- what the mend's hand-off moves out of reach (Bot.handoffsFor)
        local robbed, keeps, spoiled, locked, stolen = {}, {}, {}, {}, {}
        local function took(th)
            stolen[th.target] = stolen[th.target] or {}
            if th.item then stolen[th.target][th.item] = true end
        end
        for _, o in ipairs(outcomes) do
            local res, none = struckIn(o.strikes, hitOf[o.way])   -- none: no game-over unit dies
            local robbedHere = {}
            for _, th in ipairs(o.strikes.thefts or {}) do
                if th.lock then robbedHere[th.target], robbed[th.target] = true, true end
                if th.lock and o.p > M.DUST then
                    locked[th.target] = locked[th.target] or {}
                    locked[th.target][th.thief] = true
                    took(th)
                end
                -- a holder the same way surely kills loses the item with its life: that way's
                -- death is the plan's cost, not a theft as well
                local dies = res[th.target] and res[th.target].d >= 1 - M.DUST
                if th.spoils and not th.drops and not dies and o.p > M.DUST then
                    spoiled[th.target] = spoiled[th.target] or {}
                    spoiled[th.target][th.thief] = true
                    took(th)
                end
            end
            for _, u in ipairs(hitOf[o.way]) do
                local id, r = u.id, res[u.id]
                if not robbedHere[id] then keeps[id] = (keeps[id] or 0) + o.p * (1 - r.d) end
                die[id] = (die[id] or 0) + o.p * r.d
                byWay[id] = byWay[id] or {}
                byWay[id][o.way] = (byWay[id][o.way] or 0) + o.p * r.d
                taken[id] = (taken[id] or 0) + o.p * r.t
                if r.sh then short[id] = (short[id] or 0) + o.p * r.sh end
                struck[id] = math.max(struck[id] or 0, r.n)
            end
            overAll = overAll + o.p * (1 - none)
            -- the strikers our counters fell (felled): the boss, or a Rout's last enemy, is the win
            local p, by = M.fellBy(o.strikes, ends)
            for _, t in ipairs(by) do winStruck[t] = true end
            fell = fell + o.p * p
            -- what our units' counters learn in this way of the phase: each strike's own
            -- exchange, played at the HPs the phase had left when it came (ADR 0414)
            for _, s in ipairs(o.strikes) do
                if s.taught and s.targetHp then
                    learnt = learnt + o.p * taught(s.taught, s.joint, s.strikerHp, s.targetHp, true)
                end
            end
            for _, s in ipairs(o.strikes) do
                local striker = s.enemy and byId[s.enemy]
                if striker and striker.faction == "red" and not st.recruits[s.enemy] then
                    countered[s.enemy] = (countered[s.enemy] or 0) + o.p * (s.felled or 0)
                end
                if strikers[s.target] and s.enemy then strikers[s.target][s.enemy] = true end
                -- a berserk strike's striker is struck by its target's counter (blowsOn)
                if s.berserk and strikers[s.enemy] then
                    strikers[s.enemy][s.target] = true
                end
                if st.recruits[s.enemy] or st.loose[s.enemy] then
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
        -- the fog read of unit `u` on (x, y) at `hp`, paid into the plan's sum
        local function addFog(u, x, y, hp)
            local f = fogDie(u, x, y, hp)
            if f > 0 then st.fogBy[u.id], st.fogSum = f, st.fogSum + f end
        end
        for _, p in ipairs(planned) do addFog(p.unit, p.x, p.y, p.hp - (taken[p.unit.id] or 0)) end
        -- a green meets the fog where the plan leaves it (#713): a green whose death spoils the
        -- clear is paid as a player unit's (below, M.greenPaid), so its fog read is summed with
        -- theirs; any other green's is not (#788). A carried one meets none
        for _, g in ipairs(greens) do
            local c = (st.carry or {})[g.id]
            local gx, gy = g.x, g.y
            if c and c.x then gx, gy = c.x, c.y end
            if M.greenPaid(st, g, gated) and not (c and c.by) and (g.onField or (c and c.x)) then
                addFog(g, gx, gy, g.hp - (taken[g.id] or 0))
            end
        end
        -- A joined recruit meets no fog read: the fog's strike (Bot.fogRead, sight.strike) is
        -- read on the real board, where she is still red and no red strikes her, and her blue
        -- unit lives only inside the judged phase. The fog is a tie-breaker (M.outranks); her
        -- death in the phase is read in full above
        st.predict = {}
        for _, g in ipairs(greens) do
            if M.greenPaid(st, g, gated) then
                judged = judged - loss(W, st, g.charId) * die[g.id]
            end
            local by = sortedKeys(strikers[g.id])   -- a list: the record is logged as JSON
            st.predict[#st.predict + 1] = { id = g.id, charId = g.charId, x = g.x, y = g.y,
                                            hp = g.hp, die = die[g.id], taken = taken[g.id],
                                            strikes = struck[g.id], strikers = by,
                                            green = true }
        end
        -- in id order: the judged sum and the trace are the same every run
        for _, id in ipairs(sortedKeys(felled)) do
            if felled[id] > 0 then
                local r = byId[id]
                st.predict[#st.predict + 1] = { id = id, charId = r.charId, x = r.x, y = r.y,
                                                hp = st.enemyHp[id] or r.hp, die = felled[id],
                                                taken = 0, strikes = 0,
                                                struck = sortedKeys(struckBy[id]), recruit = true }
            end
        end
        -- a joined recruit is a player unit: its death is paid as one's (`joined`: its red id)
        for _, r in ipairs(recruited) do
            judged = judged - loss(W, st, r.charId) * (die[r.id] or 0)
            st.predict[#st.predict + 1] = { id = r.id, charId = r.charId, x = r.x, y = r.y,
                                            hp = r.hp, die = die[r.id], taken = taken[r.id],
                                            strikes = struck[r.id],
                                            strikers = sortedKeys(strikers[r.id]), joined = r.from }
        end
        for _, p in ipairs(planned) do
            local id = p.unit.id
            local by = sortedKeys(strikers[id])
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
        st.opens = {}
        for id in pairs(robbed) do st.opens[id] = keeps[id] or 0 end
        st.goalWorth = {}
        st.goalNow = goalTerm(st, alive, felled, st.goalWorth, fell)
        st.alive, st.felled = alive, felled   -- for the lookahead's later win (goalTerm again)
        judged = judged + st.goalNow + W.exp * learnt
        st.winFell, st.winStruck = fell, winStruck
        st.advances, st.woundOnly = advances(st, fell, countered)
        -- each way the phase went and its units' HP there, for the wear's later phases
        st.outcomes, st.hitOf = outcomes, hitOf
        -- the units the phase strikes that no heal of the army's reaches after it, in id order
        st.worn, st.wearFor = {}, {}
        for _, p in ipairs(planned) do
            if (struck[p.unit.id] or 0) > 0 and carries(p.unit.id) > 1 then
                st.worn[#st.worn + 1] = p.unit.id
                st.wearFor[p.unit.id] = carries(p.unit.id)
            end
        end
        -- what the plan's strikes spend of their weapons, and its hires, at the gold's points
        -- (#642, Bot's useCharge): the uses each spends at the HP the plan leaves its target
        -- (st.wear, the game's played ways), charged here, on the judged plan, and never on an
        -- act's own score, so the beam builds the plan a dear weapon's kill makes safe and the
        -- cap reads it first
        st.priced = 0
        for _, a in ipairs(st.acts) do
            local w = st.wear[a.unitId]
            st.priced = st.priced + W.gold * (a.useCharge or 0) * (w and w.uses or 0)
            -- a paid Talk's hire (#766, Bot's hirePrice): the gold the paid-recruit script takes
            st.priced = st.priced + W.gold * (a.hirePrice or 0)
        end
        judged = judged - st.priced
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
        -- every owed recruit on the field whose death is not the win: a loose one, or one a
        -- blue may Talk (its feasible row counts it once; without one, its death still costs
        -- the clean clear, ADR 0475)
        local owed = {}
        for _, set in ipairs({ st.loose, st.recruits }) do
            for id in pairs(set) do
                if byId[id] and not winByDeath(st, id) then owed[id] = true end
            end
        end
        st.thieves, st.lockThieves, st.stolen = spoiled, locked, stolen
        -- each door the plan opens that memory says brings reds, before the strikers its front
        -- needs stand ready (Bot's releasesOf): what that door's units lost before is lost again
        -- (#766: vanilla Ch14's (22,17) door, Rennac and the two chests he loots)
        local released = {}
        for _, r in ipairs(ctx.releases or {}) do
            if not r.staged and st.opened[r.key] then released[#released + 1] = r.stake end
        end
        st.forfeited = Goals.forfeited(ledger, goals, { win = winOf(st, fell), took = st.took,
                                                       lost = lost, owed = owed,
                                                       stolen = spoiled, reach = reached(st),
                                                       gone = M.GONE, released = released })
        local gain = progress(st)
        local greenDie = 0
        for _, g in ipairs(greens) do
            -- a game-over green is admission's, not here. A recruit's death is a forfeit too, and
            -- counted here as well: the forfeit is yes/no (any chance past Goals.DUST), so
            -- without its chance every plan that risks the recruit at all ties, and one that
            -- lowers it ranks no higher (vanilla Ch2's Ross, 37% in every turn-1 plan, #510).
            -- The forfeit ranks first, so this only breaks ties among plans that forfeit alike
            if not gameOver[g.charId] and M.greenPaid(st, g, gated) then
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
            if gameOver[u.charId] and o > 0 then overAll = M.either(overAll, o) end
            -- `counter`: the part of `die` that is the plan's own acts' counters, resolved by the
            -- enemy phase; botrun grades a later death given the unit lived through it (#737)
            st.protected[#st.protected + 1] = { id = u.id, charId = u.charId, die = d,
                                                counter = o, branches = branches, cap = cap }
            rank.hp_left = rank.hp_left + (hp - (taken[u.id] or 0))
        end
        for _, p in ipairs(planned) do protect(p.unit, p.hp) end
        for _, g in ipairs(greens) do
            if gameOver[g.charId] then protect(g, g.hp) end
        end
        -- a recruit the plan Talks over is a player unit in the phase: protected, under the cap,
        -- as any blue (#766: vanilla Ch10's Amelia was Talked over by plans that read her no
        -- death; the replan just after read 0.65 to 0.95, and she died)
        for _, r in ipairs(recruited) do protect(r, r.hp) end
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
    local a, bait = assault()
    if a then finals[#finals + 1] = { st = a, kind = "assault" } end
    local have = {}
    for _, f in ipairs(finals) do have[table.concat(keysOf(f.st), " ")] = true end
    -- one more plan for the rank to judge: `st` completed (every unit it leaves holding), as
    -- `kind`, unless a plan with the same acts is there already or no unit took an act
    local function offer(st, kind)
        st = complete(st)
        local k = table.concat(keysOf(st), " ")
        if st == start or have[k] then return end
        have[k] = true
        finals[#finals + 1] = { st = st, kind = kind }
    end
    if bait then offer(bait, "bait") end
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
        local byKey = offeredByKey(cands)
        local st, kept = start, 0
        for _, k in ipairs(rest) do
            local o = byKey[k]
            if o then readied(o.a) end   -- a spare is read only once a plan takes it
            local n = o and extend(st, o.a, o.uid, true)
            if n then st, kept = n, kept + 1 end
        end
        if kept > 0 then offer(st, "rest") end
    end
    -- the Seize, whenever the game offers it, the rest holding (#510 fwd1 item C, ADR 0403): the
    -- beam keeps what scores well act by act and can cut the one plan the rank puts first once
    -- the goals' rows are stalled (vanilla Ch8, run fwd1c2, campaign 4004 attempt 10: the Seize
    -- offered for 11 player phases, the four beam plans judged all waits over the cap, and the
    -- win taken only when the lord was the last unit left to act; another attempt never took
    -- it). Whether to take it is the rank's call (forfeits first); the beam only decides what
    -- the rank gets to see. So when every other judged plan is over the cap and the Seize plan
    -- is admitted, the Seize is played even though it forfeits a feasible goal: a win under the
    -- cap beats a plan that risks a death (M.outranks: admitted first)
    for _, c in ipairs(cands) do
        for _, x in ipairs(c.acts) do
            local n = x.act == "seize" and extend(start, x, c.unit.id)
            if n then offer(n, "seize") end
        end
    end
    -- each goal's act the game offers (#510 fwd1 item D, ADR 0405): the Seize's step above, for
    -- a Talk, a chest and a Visit. The beam decides which plans the rank judges, and cut the
    -- one act that takes an open goal (vanilla Ch9, campaign 4006 turn 11: the lord's Talk to
    -- the recruit offered and in none of the 8 plans judged; she left the map that enemy
    -- phase). So a ledger goal whose act is offered and in no plan above gets one: the act (the
    -- best by its own score, where more than one unit or tile offers it), then the first plan's
    -- other acts where they still fit, as the mend keeps a plan. Every row counts, whatever its
    -- status: the ledger lists what is still to get, and the game offering the act is the
    -- proof it can be taken now. Beside it, the act alone, every other unit holding (`lone`,
    -- #510 item E1). An ordering only: the rank decides.
    local open = {}
    for _, r in ipairs(ledger) do open[r.id] = true end
    do
        local held, bestFor, ids = {}, {}, {}
        for _, f in ipairs(finals) do
            for id in pairs(f.st.took) do held[id] = true end
        end
        for _, c in ipairs(cands) do
            for _, x in ipairs(c.acts) do
                local id = takes(x)
                if id and open[id] and not held[id] then
                    local b = bestFor[id]
                    if not b then ids[#ids + 1] = id end
                    if not b or (x.own or 0) > (b.a.own or 0)
                            or ((x.own or 0) == (b.a.own or 0) and key(x) < key(b.a)) then
                        bestFor[id] = { a = x, uid = c.unit.id }
                    end
                end
            end
        end
        table.sort(ids)
        local first = finals[1] and finals[1].st
        for _, id in ipairs(ids) do
            local b = bestFor[id]
            local alone = extend(start, b.a, b.uid)
            if alone then
                local st = rebuild(alone, first and first.acts or {}, function(x)
                    if x.unitId == b.uid then return false end
                end)
                offer(st, "goal")
                -- and alone, every other unit holding (#510 item E1): the first plan's other
                -- acts can put the act over the cap by themselves (vanilla Ch9, campaign 4006
                -- turn 11: the Talk plan read 87.2%, all of it another unit's attack across
                -- the map; the Talk alone read 30.8%). offer() drops it when it is the same plan.
                offer(alone, "lone")
            end
        end
    end
    -- and its mirror: while a ledger goal is feasible, plans that do not take the Seize.
    -- Every plan judged took it (vanilla Ch8, campaign 4001 turn 16: all 6, forfeiting two chests
    -- the thief had neared every turn), so the rank's first key had nothing to choose between.
    -- Two are built: the first plan with its Seize left out, that unit holding; and every unit
    -- holding, since the first plan's other acts can put the wait over the cap by themselves
    -- (the same start, turn 17: its attack by unit 16 read 63%, and the Seize was played with
    -- the chests still feasible). A stalled row asks for none: it no longer holds the win
    -- (ADR 0403).
    do
        local feasible, every = false, #finals > 0
        for _, r in ipairs(ledger) do feasible = feasible or r.status == "feasible" end
        for _, f in ipairs(finals) do every = every and seizesIn(f.st) end
        for _, acts in ipairs(feasible and every and { finals[1].st.acts, {} } or {}) do
            offer(rebuild(start, acts, function(x)
                if x.act == "seize" then return false end
            end), "noseize")
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
        local was = idleOn
        idleOn = false
        for _, j in ipairs(judgedPlans) do
            if opts and opts.idle and j.ok and advancing(j.st) then idleOn = true end
        end
        if idleOn ~= was then
            for _, j in ipairs(judgedPlans) do admit(j.st) end
        end
        local ranks = {}
        for i, j in ipairs(judgedPlans) do ranks[i] = j.st.rank end
        local i = M.rebase(ranks, function(k) return judgedPlans[k].ok end)
        best = i and judgedPlans[i].st
    end
    -- what the beam knew of a plan before the judge, for the trace (#510, the cheap screen's
    -- offline test): its acts' summed score, and over its acts' standing exposure (exposed: the
    -- enemies that reach the tile) at the plan's final kills and HP, the likeliest death and the
    -- summed chance. The beam scored each act at the kills and HP when it was added, so an
    -- early act here can read lower than it scored: the judge's view, which a screen must match.
    local function screen(st)
        local most, sum = 0, 0
        for _, a in ipairs(st.acts) do
            local die = (exposed(a, st.hp[a.unitId] or a.unitHp, st.gone, odds))
            if die > most then most = die end
            sum = sum + die
        end
        local function r4(x) return math.floor(x * 1e4 + 0.5) / 1e4 end
        return { base = r4(st.base), max_die = r4(most), sum_die = r4(sum) }
    end
    -- The wear (ADR 0421): a unit the judged phase strikes that no heal of the army's reaches
    -- before the phase after it (judge's st.worn) is read on M.WEAR enemy phases, its HP
    -- carried from each into the next. The second is played by the game's AI after our army's
    -- reply (sight.nextPhase); each one past it is taken as the second again. Its
    -- chance to die is that of dying in any of them: each way the next phase went (judge's
    -- st.outcomes, on that way's HP: st.hitOf), the same ways its own death is read over, then
    -- the later phases' strikes on what is left. A unit whose death ends the game adds its
    -- later death to the game over, as the lookahead's second phase does.
    -- Only such a unit takes the later phases here: for any other the turn between can
    -- restore it, and the hold is no reading (ADR 0389's amendment of 2026-11-08). One
    -- sight.nextPhase call a plan, within its own budget beside the lookahead's: M.WEAR_DECISION
    -- a decision and opts.budget.wear left of M.WEAR_ATTEMPT. A plan past it keeps the one-phase
    -- reading and is counted (`wear_skipped`): botrun records a wear_budget anomaly.
    -- The mend does not try such a unit's other acts for the wear alone: tried, it lost
    -- vanilla Ch5x's two chests and its clean clear (runs wr5 and wn5, #510).
    -- Every second phase, the wear's and the lookahead's, is read after our army's reply
    -- (sight.nextPhase's `reply`; ADR 0389's amendment of 2026-11-17). opts.reply = "hold"
    -- (PT_REPLY=hold) reads it with our units holding instead, the control it replaced
    local replyOn = not (opts and opts.reply == "hold")
    local wearCalls, wearCpu, wearSkipped = 0, 0, 0
    local wearRoom = math.min(M.WEAR_DECISION, (opts and opts.budget or {}).wear or M.WEAR_ATTEMPT)
    local function wear(st)
        if not (sight.nextPhase and st.worn and #st.worn > 0) or seizesIn(st) then return end
        if wearCalls >= wearRoom then
            wearSkipped = wearSkipped + 1
            return
        end
        local clock = os.clock()
        local r = sight.nextPhase(M.staged(st), replyOn)
        wearCalls = wearCalls + 1
        cost.area_positional = cost.area_positional + (r.areaPositional or 0)
        cost.area_truncated = cost.area_truncated + (r.areaTruncated or 0)
        cost.unjoined = math.max(cost.unjoined, r.unjoined or 0)
        -- the lookahead's second phase for this plan is this same call: kept for it
        st.wearNext = r
        local worn = {}
        for _, id in ipairs(st.worn) do worn[id] = true end
        st.wornRead = worn
        local seconds = r.outcomes or { { p = 1, strikes = r } }
        -- per unit, its death in the next phase (one) and in all M.WEAR (all3), each way's
        local one, all3 = {}, {}
        for _, o1 in ipairs(st.outcomes) do
            local units = {}
            for _, u in ipairs(st.hitOf[o1.way]) do
                if worn[u.id] then units[#units + 1] = u end
            end
            local first = #units > 0 and struckIn(o1.strikes, units)
            for _, u in ipairs(units) do
                one[u.id] = (one[u.id] or 0) + o1.p * first[u.id].d
                for _, o2 in ipairs(seconds) do
                    -- the phases past the second: the second's strikes on it again, each only
                    -- while its striker has outlived our counters before it
                    local all = {}
                    for _, s in ipairs(o1.strikes) do all[#all + 1] = s end
                    for _, s in ipairs(o2.strikes) do
                        if s.target == u.id then
                            all[#all + 1] = s
                            local live, left = 1 - (s.felled or 0), 1
                            for _ = 3, st.wearFor[u.id] do
                                left = left * live
                                local later = { [0] = 1 - left }
                                for d, p in pairs(s.takenDist) do later[d] = (later[d] or 0) + p * left end
                                all[#all + 1] = { target = u.id, takenDist = later }
                            end
                        end
                    end
                    all3[u.id] = (all3[u.id] or 0) + o1.p * o2.p * struckIn(all, { u })[u.id].d
                end
            end
        end
        local any, lives = false, 1
        for _, pr in ipairs(st.protected) do
            local more = math.max(0, (all3[pr.id] or 0) - (one[pr.id] or 0))
            if more > M.DUST then
                pr.wear, pr.phases = more, st.wearFor[pr.id]
                pr.die, any = math.min(1, pr.die + more), true
                -- `more` is the chance it lives through the next phase and dies after; the game
                -- over already holds the next phase's, so it takes the later death given that
                -- one lived (#629 re-review: unconditioned, a lord's game over read below its death)
                local lived = 1 - (one[pr.id] or 0)
                if gameOver[pr.charId] then
                    lives = lives * (lived > M.DUST and math.max(0, 1 - more / lived) or 1)
                end
            end
        end
        st.rank.game_over = 1 - (1 - st.rank.game_over) * lives
        -- admission again, the next phase's own numbers kept (`first_*`): over the cap the
        -- next phase still ranks first (ADR 0389's amendment). `predict` stays the next
        -- phase's: botrun grades each phase against the plan made just before it
        if any then admit(st) end
        wearCpu = wearCpu + (os.clock() - clock)
    end
    local function consider(st, kind)
        if now then now.stage, now.judged = "judge " .. kind, #considered end
        local before, phases = screen(st), cost.phases
        judge(st)
        wear(st)
        st.outcomes, st.hitOf = nil, nil   -- the wear's alone: not kept on every judged plan
        st.kind = kind
        before.phases = cost.phases - phases   -- the enemy phases this plan's judge played
        local c = { judged = st.judged, acts = st.keys, kind = kind, rank = st.rank,
                    seizes = seizesIn(st) or nil, weights = st.weights, screen = before }
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
    -- With no plan under the cap, or the best still robbed (below), the mend goes again from the plan it found, up to
    -- M.MEND_ROUNDS rounds, so more than one unit may change (#510 PR A): one round changed one
    -- unit, and two units each over the cap where they stood stayed a fallback.
    -- whether the plan forfeits a theft the mend can try to undo ("stolen:<id>"): a round that
    -- took the plan under the cap with the robbed unit left beside its thief is not the last
    -- (vanilla Ch16, replay i730g: Eirika's mend took the plan under the cap with Colm still
    -- robbed, and his own mend, tried from the over-cap base, stayed over it)
    -- (or robs a holder of its last chest opener, st.lockThieves: the same mend, ADR 0483)
    local function robbed(st)
        for _, f in ipairs(st.forfeited or {}) do
            if f:match("^stolen:") then return true end
        end
        return next(st.lockThieves or {}) ~= nil
    end
    -- (a robbed plan whose round changed nothing still stops: `best == base` below)
    for round = 1, M.MEND_ROUNDS do
        if not best or (round > 1 and best.rank.admitted and not robbed(best)) then break end
        local base, menuOf, risky = best, {}, {}
        -- the menus on the board the plan being mended leaves (menusFor): a unit at risk may
        -- try a doorway or a freed tile its plan's door or kill opens; extend's `needs` check
        -- drops such an act once the rebuild no longer holds that change
        local baseMenus = menusFor(base)
        for _, m in ipairs(baseMenus) do
            local mine = {}
            for _, a in ipairs(m.acts) do mine[#mine + 1] = { uid = m.unit.id, a = a } end
            menuOf[m.unit.id] = mine
        end
        -- the menu entries of the units `ids`, in order
        local function entriesOf(ids)
            local out = {}
            for _, id in ipairs(ids) do
                for _, t in ipairs(menuOf[id] or {}) do out[#out + 1] = t end
            end
            return out
        end
        local function tries(p)
            if p.recruit then
                -- a recruit has no player menu: the units it strikes try theirs (out of its
                -- reach, or waiting or striking holding a weapon whose counter spares it:
                -- the "gentle" acts, #730)
                return entriesOf(p.struck)
            end
            if p.joined then
                -- a recruit the plan Talks over has no act of its own in it: the talker's
                -- other acts are its way out, the Talk not made this turn (vanilla Ch10 s4005:
                -- every plan judged Talked Amelia into the reds' reach at 0.94, and she died).
                -- Its other Talks over her stay in: the talker's Canto tile after the Talk can
                -- be what shields her (s4005 a2, turn 10: the mend's swap to a Talk with Canto
                -- to (4,21) was the one plan under the cap)
                local talkers = {}
                for _, a in ipairs(base.acts) do
                    if a.act == "talk" and a.targetId == p.joined then
                        talkers[#talkers + 1] = a.unitId
                    end
                end
                return entriesOf(talkers)
            end
            if p.thieves then
                -- a robbed unit: its own other acts (out of the thief's reach), then the Trades
                -- that hand its item to a teammate (Bot.handoffsFor, ADR 0483: its worth is the
                -- theft the judged phase no longer plays, so only here, where a theft is read),
                -- then every unit's strike on a thief that robs it (dead, it steals nothing):
                -- vanilla Ch16, replay i730h, turn 14: Colm cornered at (19,1), every tile of
                -- his robbed
                local out = {}
                for _, t in ipairs(menuOf[p.id] or {}) do out[#out + 1] = t end
                local u = Bot.handoffsFor and byId[p.id]
                for _, a in ipairs(u and Bot.handoffsFor(ctx, u, (base.stolen or {})[p.id]) or {}) do
                    annotate(a, byId[a.unitId])
                    out[#out + 1] = { uid = a.unitId, a = a }
                end
                for _, m in ipairs(baseMenus) do
                    if m.unit.id ~= p.id then
                        for _, a in ipairs(m.acts) do
                            if a.act == "attack" and a.targetId and p.thieves[a.targetId] then
                                out[#out + 1] = { uid = m.unit.id, a = a }
                            end
                        end
                    end
                end
                return out
            end
            if not p.green then return menuOf[p.id] or {} end
            local striker, out = {}, {}
            for _, id in ipairs(p.strikers) do striker[id] = true end
            for _, m in ipairs(baseMenus) do
                for _, a in ipairs(m.acts) do
                    if Bot.distance(a.move.x, a.move.y, p.x, p.y) == 1
                        or (a.act == "attack" and a.targetId and striker[a.targetId]) then
                        out[#out + 1] = { uid = m.unit.id, a = a }
                    end
                end
            end
            return out
        end
        -- a green whose death spoils nothing is no reason to mend (#788, M.greenPaid)
        for _, p in ipairs(base.predict) do
            if p.die > 0 and not (p.green and not M.greenPaid(base, p, gated)) then
                risky[#risky + 1] = p
            end
        end
        -- a unit a spoiling theft robs in the plan ("stolen:<id>", Goals.forfeited) tries its
        -- other acts too, first: the forfeit ranks before any death, and the beam ranked its acts
        -- by their own score, which never sees the theft (vanilla Ch16, replay i730b: every plan
        -- judged kept Colm and the Knight Crest beside the thief, ADR 0475)
        for _, f in ipairs(base.forfeited or {}) do
            local id = tonumber(f:match("^stolen:(%d+)$"))
            if id then
                risky[#risky + 1] = { id = id, die = math.huge,
                                      thieves = (base.thieves or {})[id] or {} }
            end
        end
        -- a holder a thief robs of its last chest opener the same way, after the spoiled ones
        -- and before any death (its chests are lost in the ways it is robbed in, ADR 0483); a
        -- unit both spoiled and locked is tried once (`tried` below)
        for _, id in ipairs(sortedKeys(base.lockThieves or {})) do
            risky[#risky + 1] = { id = id, die = 2, thieves = base.lockThieves[id] }
        end
        -- a player unit whose counter may end the chapter (the boss striking it and dying)
        -- tries its other acts too: the beam cannot see that counter, so every plan it kept
        -- had Seth strike the boss and stand beside it (vanilla Ch5 attempt 8, turn 5)
        for _, id in ipairs(sortedKeys(base.winStruck or {})) do
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
        local function leave(uid)
            return function(x)
                if x.unitId == uid then return false end
            end
        end
        for _, p in ipairs(risky) do
            for _, t in ipairs(tries(p)) do
                local k = key(t.a)
                local st
                if k ~= mine[t.uid] and not tried[k] then
                    if t.a.needs then
                        -- a re-listed act goes in right after the act that completes the
                        -- changes it needs, the rest of the plan after it (another unit may
                        -- take its tile otherwise); last only if it does not fit there
                        local cur, put = start, false
                        for _, x in ipairs(base.acts) do
                            cur = rebuild(cur, { x }, leave(t.uid))
                            if not put and holds(cur, t.a.needs) then
                                local n = extend(cur, t.a, t.uid, true)
                                if n then cur, put = n, true end
                            end
                        end
                        st = put and cur or extend(cur, t.a, t.uid, true)
                    else
                        st = extend(start, t.a, t.uid, true)
                        st = st and rebuild(st, base.acts, leave(t.uid))
                    end
                end
                tried[k] = true
                if st then
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
    -- The heal swap (ADR 0408): the best plan with each hurt unit it leaves waiting given its own
    -- heal (a Vulnerary) on the tile the plan gives it, judged as one more plan, kind "heal".
    -- The beam keeps the acts that score best on their own (a march first) and the mend tries
    -- other acts only for a unit at risk, so neither judges the heal of a unit held out of
    -- reach. A heal is swapped in where the plan gains by it as the judge reads it, on the
    -- plan's HP so far: its own score (W.heal for each HP restored, the same for each thrown
    -- away) and the deficit it closes (W.taken for each HP restored, the judge's `short`). The
    -- rank decides between the plans.
    if best and Bot.mendAt then
        local st = rebuild(start, best.acts, function(x, now)
            local u = x.act == "wait" and candOf(x.unitId) and candOf(x.unitId).unit or nil
            local h = u and Bot.mendAt(ctx, u, x.move) or nil
            if not h then return nil end
            h.why = "mend"
            -- the board and changes the wait it replaces was read on (menusFor)
            h.map, h.needs = x.map, x.needs
            annotate(h, u)
            local gain = math.min(h.amount, h.unitMaxHp - (now.hp[h.unitId] or h.unitHp))
            return score(h, now, W, style, odds, likeliest) + W.taken * gain > 0 and h or nil
        end)
        st = complete(st)
        -- no heal fitted (none scored, or each lost its tile): no new plan to judge
        if table.concat(keysOf(st), " ") ~= table.concat(keysOf(best), " ") then
            consider(st, "heal")
            pick()
        end
    end
    -- The spare (#642): the best plan with each strike's cheaper weapon in its place (Bot's
    -- `spares`: the same target from the same tile), judged as one more plan, kind "spare";
    -- with two or more such strikes, also all of them swapped at once. The beam never sees a
    -- weapon's price, so this is where a Steel Lance's same kill outranks a Siegmund's: the
    -- price is in each judged plan's value, below the cap and the plan's progress.
    if best then
        -- each swap alone; then, with two or more strikes that have spares, each one's cheapest
        -- spare (the least useCost; slot order on a tie) all at once. With one such strike that
        -- plan is one of the swaps already, and judging it again would waste an enemy phase.
        local swaps, all, swapped = {}, {}, 0
        for i, a in ipairs(best.acts) do
            for _, b in ipairs(a.spares or {}) do
                swaps[#swaps + 1] = { [i] = readied(b) }
                if not all[i] then swapped = swapped + 1 end
                if not all[i] or (b.useCost or 0) < (all[i].useCost or 0) then all[i] = b end
            end
        end
        if swapped > 1 then swaps[#swaps + 1] = all end
        local was = table.concat(keysOf(best), " ")
        for _, sw in ipairs(swaps) do
            local i = 0
            local st = complete(rebuild(start, best.acts, function()
                i = i + 1
                return sw[i]
            end))
            if table.concat(keysOf(st), " ") ~= was then consider(st, "spare") end
        end
        if #swaps > 0 then pick() end
    end
    -- The lookahead (FR-017, FR-018): at an irreversible transition, the finalists (the best
    -- M.FINAL plans judged, by rank) each meet a second enemy phase, our army's reply played
    -- between (sight.nextPhase; it replaced the R-8 spike's hold). All of them or none: the
    -- calls it needs, one a finalist, within the decision's and the attempt's budget, else the
    -- original horizon, tagged `skipped`. A protected unit's death chance becomes that of dying
    -- in either phase, its branch-local first phase's kept, and the finalists are ranked again.
    local look = { calls = 0 }
    if now then now.stage, now.judged = "lookahead", #considered end
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
            -- a finalist that takes the Seize meets no second phase, as it met no first: the
            -- chapter is over (ADR 0405). It costs no call and stays a finalist, ranked again
            -- beside the others
            local asks = 0
            for _, st in ipairs(fin) do
                if not seizesIn(st) and not st.wearNext then asks = asks + 1 end
            end
            if asks > room then
                look.skipped = true
                cost.look.skipped_budget = 1
            else
                local clock = os.clock()
                for _, st in ipairs(fin) do
                    local r = {}
                    if st.wearNext then
                        r = st.wearNext   -- the wear asked this same phase (ADR 0421): no call
                    elseif not seizesIn(st) then
                        r = sight.nextPhase(M.staged(st), replyOn)
                        look.calls = look.calls + 1
                        cost.area_positional = cost.area_positional + (r.areaPositional or 0)
                        cost.area_truncated = cost.area_truncated + (r.areaTruncated or 0)
                        cost.unjoined = math.max(cost.unjoined, r.unjoined or 0)
                    end
                    -- the units the wear read (ADR 0421): their later phases are its reading,
                    -- the same second phase on each way's HP and the third, already in their
                    -- death and the game over
                    local wornRead = st.wornRead or {}
                    local second, lost, over, won = M.secondRead(r, st.phase.hit, struckIn,
                                                                 wornRead, endsIn(st), st.alive)
                    -- what the army's reply played there (sight.nextPhase's .reply): the
                    -- played plan's goes in its trace, so a death read safe can be checked
                    -- against the turn the read assumed
                    st.replied = r.reply
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
                        -- the cap's reading stays the one before this phase (ADR 0470)
                        pr.capDie = pr.capDie or pr.die
                        if not wornRead[pr.id] then pr.die = M.either(pr.die, pr.second) end
                        rank.hp_left = rank.hp_left - (lost[pr.id] or 0)
                    end
                    for _, u in ipairs(st.phase.hit) do
                        local f = first[u.id]
                        local was = f and f.die or 0
                        local more = (1 - was) * (second[u.id] or 0)
                        -- a green is paid here as in the first phase: only when its death
                        -- spoils the clear (M.greenPaid, #788), in the value and the tie-break
                        local paid = not (f and f.green) or M.greenPaid(st, u, gated)
                        if paid then
                            rank.value = rank.value - loss(W, st, u.charId) * more
                        end
                        if u.maxhp then rank.value = rank.value - W.taken * (lost[u.id] or 0) end
                        if f and f.green and not protected[u.id] and paid then
                            rank.green_die = rank.green_die + more
                        end
                    end
                    rank.game_over = M.either(rank.game_over, over)
                    -- the win the second phase reads (#641): a turn later, so worth GAMMA of
                    -- the first phase's, through the goals' own term (goalTerm) on the
                    -- chance the first phase leaves the chapter open. Without it a bait whose
                    -- counters only wound the boss is worth its HP lost and nothing more.
                    -- `judged` and `goalWorth` stay the first phase's (they add up: botrun
                    -- grades them on the phase that follows); the record keeps this one apart
                    -- (`lookWin`), its rows and what it adds to the rank's value
                    if won > M.DUST then
                        local rows = {}
                        local later = goalTerm(st, st.alive, st.felled, rows,
                                               M.either(st.winFell, Goals.GAMMA * won))
                        rank.value = rank.value + later - st.goalNow
                        st.lookWin = { won = won, gain = later - st.goalNow, worth = rows }
                    end
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
                look.reply = best.replied
                for _, c in ipairs(considered) do
                    for _, st in ipairs(fin) do
                        if c.rank == st.rank then c.extended, c.lookWin = true, st.lookWin end
                    end
                end
            end
            cost.look.calls = look.calls
        end
    end
    -- the wear's calls, time and plans past its budget, beside the lookahead's and outside its
    -- budget (FR-018's is for the irreversible transitions: spent here, the boss fight went unread)
    look.wear = wearCalls > 0 and wearCalls or nil
    look.wear_skipped = wearSkipped > 0 and wearSkipped or nil
    cost.look.wear, cost.look.wear_cpu_s, cost.look.wear_skipped = wearCalls, wearCpu, wearSkipped
    if not best or #best.acts == 0 then return nil, nil, cost end
    best.lookahead = look
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
            c.rejected = c.rank.admitted and "outranked"
                or c.rank.idle == 1 and "idle" or "over_cap"
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
    -- (a plan inadmissible only for being idle, a hold the game-over plans lost to, is no sacrifice)
    best.fallback = (not best.rank.admitted and best.rank.max_exceed > 0)
        and "FALLBACK_SACRIFICE" or nil
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
        best.goals[#best.goals + 1] = { id = id, x = t.x, y = t.y, stage = t.stage }
    end
    table.sort(best.goals, function(a, b) return a.id < b.id end)
    -- each door memory says brings reds (Bot's releasesOf, #766): how many strikers its front
    -- needs, how many stand ready, whether a recruit it took has a talker ready, and whether a
    -- plan that opens it forfeits its stake; a thief the calendar brings is one too (`arrival`,
    -- its board turn, and `due`, whether its stage job is on: ADR 0483)
    best.releases = {}
    for _, r in ipairs(ctx.releases or {}) do
        best.releases[#best.releases + 1] = { x = r.x, y = r.y, need = r.need, ready = r.ready,
                                              talkReady = r.talkReady, staged = r.staged,
                                              arrival = r.arrival, due = r.due }
    end
    -- every job the strategy layer priced this decision (bot.lua notePrice), and which unit's
    -- chain took it (`chosen`: its place in the chain, ctx.jobs)
    local chosen = {}
    for uid, c in pairs(ctx.jobs or {}) do
        for i, j in ipairs(c) do chosen[Bot.jobKey(uid, j.t.id, j.t.x, j.t.y)] = i end
    end
    best.jobs = {}
    for _, p in pairs(ctx.jobPrices or {}) do
        local row = copy(p)
        row.chosen = chosen[Bot.jobKey(p.id, p.goal, p.x, p.y)]
        best.jobs[#best.jobs + 1] = row
    end
    table.sort(best.jobs, function(a, b)
        if a.id ~= b.id then return a.id < b.id end
        if a.x ~= b.x then return a.x < b.x end
        return a.y < b.y
    end)
    -- the enemies the plan was made against: in sight, and those a retry remembers (ctx.threats,
    -- ADR 0399), so a death by a remembered one is never graded `fog` (botrun.grade)
    best.enemies = {}
    for _, e in ipairs(ctx.threats) do best.enemies[e.id] = true end
    best.talks = {}
    for c in pairs(talks) do best.talks[#best.talks + 1] = c end
    table.sort(best.talks)
    best.seizable = seizable
    best.gentle = gentle
    -- whether the plan takes the Seize offered, whether any plan judged took it, and whether
    -- one did within the cap: a skip is a fault only when a legal Seize under the cap was there
    -- to take (FR-015, botrun's seize skips)
    best.seizes, best.seizeJudged, best.seizeAdmitted = seizesIn(best), false, false
    best.tried = ctx.tried   -- the units each stalled goal was given to (Bot.candidates' opts.tried)
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
    best.nearest = nearest   -- the near half of botrun's progress record
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
            st = st and extend(st, o.a, o.a.unitId, true)
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
