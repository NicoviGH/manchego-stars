-- goals.lua -- what is still left to get in a chapter, what each thing is worth and the chance
-- of getting it from a board (#510 step 9; the design: #510 comment 6534885686). Its own chunk,
-- pure: no emu, SYM or harness global; the game is read through `sight`.
--
-- The planner scored one phase, so nothing in it knew a village three turns off was worth the
-- walk, or that a boss kill closes every goal still open (vanilla Ch5 attempt 8: Gilliam sent
-- to (5,1) on turn 1, held four turns of eight, and the boss died with him three turns short).
-- A plan is now also worth what it does to the goals' chances (planner.lua).
--
-- Goals.list(board, sight, style, ctx) -> { goal }, the goals still open:
--   visit / chest  each tile sight.explorable() still offers that this run has not taken;
--                  takers = our units the game lets use it (sight.canExplore), and for a
--                  chest the units with no key for it while an enemy whose fall gives them
--                  one stands (sight.locked, sight.keySources): its turns run by way of that
--                  enemy (Bot's turnsTo).
--   recruit        each unit ctx.recruitTalkers names (Bot.candidates: the player units that
--                  may Talk it over); its takers are those talkers. A recruit a retry saw
--                  arrive and that is not on the board yet (ctx.pendingRecruits, ADR 0436) is
--                  one too, at the tile it arrived on; one an act loaded (`by`, ADR 0464)
--                  stalls on a quiet count, as any goal (M.ledger).
--   objective      each unit's own way to the objective (ctx.objectiveTile: the Seize tile,
--                  the boss, or on Rout the nearest enemy -- where its march heads), the unit
--                  its one taker. None on Survive, whose way there is holding.
-- goal = { id, kind, tile = {x, y}, gold, takerUnits = { unit }, closes = enemy phase | nil }.
-- `gold` (Goals.worth makes it points):
--   a village or chest: the mean gift over every vanilla village (style.villageGifts: items
--     at sight.itemCost, the game's own GetItemCost; gold at face value) -- a new player does
--     not know what one holds; a House (sight.explorable's `house`) the mean over every vanilla
--     House (style.houseGifts: most only talk, worth 0), and no 'villages' reward needs one;
--   a recruit: its items' sight.itemCost;
--   a reward (style.rewards, a guide's claim): its item's itemCost shared evenly over the open
--     goals its `needs` names, none of it once one of them is lost (ctx.lost).
-- `closes`: sight.closings(k, style.waves) -- the enemy phase after which a looter has it (or a
-- retry remembers one did, Timeline.deadlines), or
-- the game's AI escapes with the recruit (Goals.closings), or a turn event removes it (Goals.scriptedCloses,
-- #724).
--
-- Goals.worth(goal, W) -> points: gold x W.gold, plus W.death for a recruit (a unit), and for
-- the objective's way there one W.death shared over the army (`share`): no style walks into a
-- death for it, and each unit is pulled forward as the old flat ground term pulled it (careful:
-- ~111 a unit of nine, a turn closer ~9 against the old 8). The win itself is the planner's W.win.
--
-- Goals.chance(goal, pos, gamma, turnsTo) -> 0..1, and the turn the likeliest taker arrives on
-- (nil: none can): pos[unit id] = { x, y, acted, alive (0..1), late (turns a chain of jobs spends
-- first, jobs.lua) },
-- the board a plan leaves. t = turnsTo(u, tile, pos, beside), its turns there (sight's: cost /
-- MOV, not rounded; `beside` = M.beside(goal.kind), the tile's lock left out); one that has
-- acted takes it a turn later. The chance is gamma ^ (max(t, 1) - 1 +
-- late): each turn further is another enemy phase where something can go wrong, and every
-- step beyond reach counts. Within reach it is 1 for a unit that has not acted and gamma for
-- one that has, standing on the goal too: taking it now is worth a turn over waiting there.
-- A goal closed before the phase the taker really arrives on (closes < ceil(t) + late, at
-- least phase 1) is 0 for it. Over the takers, the expected best as each lives (alive), the
-- best first.
--
-- Goals.ledger(goals, sight, style, ctx, chances) -> { row }, the completion ledger (FR-014):
-- at the decision, every goal of Goals.list's still to get (the objective's ways there are the
-- win's, not goals of their own), and each declared reward still to be had (style.rewards).
-- chances[goal id] is its chance from the decision's board (Goals.chance).
-- row = { id, kind (visit, chest, recruit, reward), status, closes_on, needs (a reward's: the
-- ids of the goals it needs) }. status: `feasible`; `unknown` for a village or chest when the
-- sight has no read of who may use it or when it closes (sight.canExplore, sight.closings);
-- `stalled` for a goal whose id is in ctx.quietGoals (no unit has neared it over GOAL_QUIET waiting player
-- phases, botrun's reading; #510 call 3, amending FR-015): a stalled ROW no longer holds the
-- win, since forfeited counts feasible rows only, but the goal stays a goal units may walk to,
-- and one new low makes its row feasible again. A reward is unknown when a goal it needs is,
-- else stalled when one is. (`stalled` also names a repeated board, ctx.stalled: not this.) A goal no unit can reach this turn (a unit in
-- the way) stays feasible: only a closure loses it. One with no chance at all is no goal of
-- the bot's: the game lets no player unit use it (a chest with no key in the army and none on
-- an enemy that drops it), none has a way
-- there (sight.turnsTo reads the terrain, through a breach), or a looter takes it first. Kept,
-- it would close with every win and so forbid the win for good. A reward needing one of those
-- can never be had, and is no row either.
-- Goals.forfeited(ledger, goals, closes) -> the sorted ids of the feasible rows a plan loses
-- for good (FR-011's forfeits), "owed:<unit id>" for each owed recruit with no feasible row
-- whose death it risks, and "stolen:<unit id>" for each unit a spoiling theft robs: what the
-- record's clean clear loses (ADR 0475). `closes` is what the plan does in the judged phase,
-- each a chance over its judged branches: { win (the chapter ends), took = { [goal id] = true },
-- lost = { [recruit unit id] = chance it dies }, owed = { [unit id] = true } (every owed recruit
-- on the field whose death is not the win), stolen = { [unit id] = true } (robbed of an item the
-- game ranks above the stat boosters in some branch), reach = { [goal id] = { before, after } },
-- gone }.
-- Counted conservatively (FR-014): a goal is lost when it is lost in any branch with p > 0, so
-- any chance at all is the whole goal. A win
-- closes every goal the plan does not take; a recruit's death closes its Talk; a looter's
-- closing after this phase (`closes` 1) closes a tile the plan does not take; a reward closes
-- with any goal it needs. So does a plan that leaves a DATED goal (g.closes set) out of reach by
-- its deadline: `reach[id]` is the goal's chance read from reaching it alone (Goals.chance on
-- the board before the plan, `before`, and the board it leaves, `after`: no survival or win
-- weight, which are the cap's and the win's own counts), and the goal counts when `before` was
-- at least `gone` (the planner's M.GONE) and `after` is none. That 0.5 floor is a deliberate
-- exception to "any chance at all is the whole goal": this reading comes from the chance model,
-- not the game's rules, so a goal that was never likelier than not is not marked lost by it
-- (#714, ADR 0450). `reach` and `gone` come together. A unit whose death ends the game closes
-- nothing here: its risk is
-- admission's, within the style's cap, and counted again as a forfeit the plan whose lord is
-- at 0% would beat every plan that puts it in danger (Nicolas, 2026-11-02: ADR 0384).

local M = {}

-- timeline.lua, beside this file: what a retry remembers losing, and when (#765)
local Timeline = dofile(PLAYTEST_DIR and (PLAYTEST_DIR .. "/timeline.lua")
    or ((debug.getinfo(1, "S").source:match("^@(.*/)") or "./") .. "timeline.lua"))

-- What each turn further from a goal leaves of its chance: another enemy phase where something
-- can go wrong (Claude's starting value, #510 comment 6534885686; tuned on the runs).
M.GAMMA = 0.85

local function key(x, y) return x .. "," .. y end

local function mean(xs)
    if #xs == 0 then return 0 end
    local s = 0
    for _, x in ipairs(xs) do s = s + x end
    return s / #xs
end

-- the worth of a village or chest whose gift is unknown: the mean vanilla gift
local function prior(cost, gifts)
    if not gifts then return 0 end
    local xs = {}
    for _, id in ipairs(gifts.items or {}) do xs[#xs + 1] = cost(id) end
    for _, g in ipairs(gifts.gold or {}) do xs[#xs + 1] = g end
    return mean(xs)
end

local function needs(reward, g)
    if reward.needs == "villages" then return g.kind == "visit" and not g.house end
    if reward.needs == "chests" then return g.kind == "chest" end
    for _, t in ipairs(reward.needs) do
        if t[1] == g.tile.x and t[2] == g.tile.y then return true end
    end
    return false
end

-- a lost tile (ctx.lost: "x,y" -> kind) that a reward needs voids it
local function voided(reward, lost)
    for k, kind in pairs(lost or {}) do
        local x, y = k:match("^(%-?%d+),(%-?%d+)$")
        if needs(reward, { kind = kind, tile = { x = tonumber(x), y = tonumber(y) } }) then
            return true
        end
    end
    return false
end

-- sight.closings for this board: when a looter has each open tile and, for each recruit on the
-- field (ctx.recruitTalkers), "unit:<id>" -> the enemy phase the game's own AI escapes with it
-- (#699); and the paths of those recruits, { [unit id] = { [enemy phase] = tile } }.
-- Then what a retry remembers (Timeline.deadlines' tiles, #765: the earliest enemy phase an
-- earlier attempt lost each tile in, a looter the play brought dated from its appearance in this
-- attempt, ctx.appeared) for a tile still open: the earlier of the two, as M.scriptedCloses
-- takes the earlier removal. ctx.turn is the board's turn; a remembered phase already past
-- closes nothing (this attempt's play kept the tile so far).
function M.closings(sight, style, ctx)
    local out, paths = {}, {}
    if sight.closings then
        local watch = {}
        for id in pairs(ctx.recruitTalkers or {}) do watch[id] = true end
        -- style.waves: no caller sets it since the guide's claims stopped playing (ADR 0464); it
        -- is the slot #569's remembered waves would fill
        out, paths = sight.closings(nil, style.waves, watch)
    end
    -- a sight with no simulated closings still has the remembered ones
    local lost = Timeline.deadlines(style.memory, ctx.appeared).tiles
    if next(lost) then
        assert(ctx.turn, "Goals.closings: a remembered closing needs ctx.turn")
        local copy = {}   -- sight keeps its answer for the board
        for k, v in pairs(out) do copy[k] = v end
        for k, phase in pairs(lost) do
            -- enemy phase 1 is this turn's
            local at = phase - ctx.turn + 1
            if at >= 1 and at < (copy[k] or math.huge) then copy[k] = at end
        end
        out = copy
    end
    return out, paths or {}
end

-- The scripted removals (#724) folded into M.closings' answer for this board: a turn event's DISA
-- or KILL (sight.scriptedUnits) closes the recruit the enemy phase before its boardTurn, so
-- "unit:<id>" is boardTurn - board.turn when that is sooner than the AI's escape, and the
-- recruit's path (as long as its deadline less one, the closings contract) is cut to match. An
-- ESTIMATE: the script's guards (CHECK_ALIVE, CHECK_ALLEGIANCE) are not evaluated; for a recruit
-- not yet joined the removal holds, and a removal whose turn is past is none. `board` names each
-- recruit's charId (a pending one is ctx.pendingRecruits'); ctx.owedRecruits (a set of charIds)
-- names the ones owed, and empty or nil asks for no scan. Returns new tables: sight keeps its
-- answers for the board. A departure a retry remembers (Timeline.deadlines' `gone`, #765: the
-- first player turn the unit was off the map, one the play brought dated from its appearance in
-- this attempt, ctx.appeared) is a removal too, the earlier of the two.
function M.scriptedCloses(sight, ctx, board, out, paths, memory)
    assert(board.turn, "Goals.scriptedCloses: the board has no turn")
    -- only an owed recruit (ctx.owedRecruits, a set of charIds: botrun's) can be removed from a
    -- goal: recruitTalkers also holds any talk offered, and a scan for those would be asked again
    -- by every plan's sandbox
    local watch, owed = ctx.recruitTalkers or {}, ctx.owedRecruits or {}
    if not sight.scriptedUnits or next(watch) == nil or next(owed) == nil then return out, paths end
    local gone = sight.scriptedUnits().removals
    local left = Timeline.deadlines(memory, ctx.appeared).gone
    if next(left) then
        local merged = {}
        for c, t in pairs(gone) do merged[c] = t end
        for c, t in pairs(left) do merged[c] = math.min(merged[c] or t, t) end
        gone = merged
    end
    local byId = {}
    for _, u in ipairs(board.units) do byId[u.id] = u end
    local outCopy, pathCopy = nil, nil
    for id in pairs(watch) do
        local u = byId[id] or (ctx.pendingRecruits or {})[id]
        local at = u and owed[u.charId] and gone[u.charId] and gone[u.charId] - board.turn
        if at and at >= 1 and at < (out["unit:" .. id] or math.huge) then
            if not outCopy then
                outCopy, pathCopy = {}, {}
                for k, v in pairs(out) do outCopy[k] = v end
                for k, v in pairs(paths) do pathCopy[k] = v end
            end
            outCopy["unit:" .. id] = at
            if pathCopy[id] then
                local cut = {}
                for phase, tile in pairs(pathCopy[id]) do
                    if phase < at then cut[phase] = tile end
                end
                pathCopy[id] = cut
            end
        end
    end
    return outCopy or out, pathCopy or paths
end

-- The villages and chests still open, each with its worth in gold and when it closes:
-- { { id, kind, x, y, tile, gold, closes } }. Goals.list's, and Bot.candidates' exploring ranks who
-- is sent where by it.
function M.openTiles(sight, style, ctx, closings)
    local cost = sight.itemCost or function() return 0 end
    local explored = ctx.explored or {}
    closings = closings or M.closings(sight, style, ctx)
    local worth, house, out = prior(cost, style.villageGifts), prior(cost, style.houseGifts), {}
    for _, t in ipairs(sight.explorable and sight.explorable() or {}) do
        local k = key(t.x, t.y)
        if not explored[k] then
            out[#out + 1] = { id = t.kind .. ":" .. k, kind = t.kind, x = t.x, y = t.y,
                              tile = { x = t.x, y = t.y }, house = t.house,
                              gold = t.house and house or worth, closes = closings[k] }
        end
    end
    -- a reward's item, shared over the open goals it needs
    for _, r in ipairs(style.rewards or {}) do
        if not voided(r, ctx.lost) then
            local share = {}
            for _, g in ipairs(out) do
                if needs(r, g) then share[#share + 1] = g end
            end
            for _, g in ipairs(share) do g.gold = g.gold + cost(r.item) / #share end
        end
    end
    return out
end

-- A recruit's path (sight.closings' second answer: where he stands after each enemy phase, as
-- far as the forecast plays) run on with where an earlier attempt saw him walk (Timeline.routeOf,
-- #766's stage job: Ch14's Rennac leaves 9 turns after he appears, past the forecast's 8
-- phases). Phase k is player turn ctx.turn + k, so it reads the route `ctx.turn + k - from`
-- turns after he came: `from` is his appearance in this attempt (ctx.appeared) for a unit that
-- arrived, turn 0 for one there at the start. Up to his removal (closes - 1, the path's own
-- contract), or with none known to the route's end. The forecast's phases stand: the board as
-- it is outranks another play's memory. A turn before the route's first step reads the tile
-- before it (a phase the fog hid). A unit that came in the earlier attempt but not yet in this
-- one, or that no attempt saw walk, keeps the forecast.
local function runOn(path, closes, t, memory, ctx)
    local route, arrival = nil, nil
    if memory and t.charId then route, arrival = Timeline.routeOf(memory, t.charId, t.classId) end
    local from = route and (arrival == nil and 0 or ctx.appeared and ctx.appeared(t.charId, t.classId))
    if not (from and ctx.turn) then return path end
    path = path or {}
    local last = closes and closes - 1 or route[#route].after - (ctx.turn - from)
    if last <= #path then return path end
    local out = {}
    for k, v in ipairs(path) do out[k] = v end
    for k = #path + 1, last do
        local at = out[k - 1] or { x = t.x, y = t.y }
        for _, st in ipairs(route) do
            if st.after <= ctx.turn + k - from then at = { x = st.x, y = st.y } end
        end
        out[k] = at
    end
    return out
end

-- Each recruit a unit may Talk over (ctx.recruitTalkers, a pending one ctx.pendingRecruits'),
-- as a goal: worth the gold he carries, taken by his talkers, closing when he is removed, met on
-- his path (runOn). `byId` holds the board's units by id.
local function recruitGoals(byId, closings, paths, cost, style, ctx)
    local out = {}
    for id, talkers in pairs(ctx.recruitTalkers or {}) do
        local t = byId[id] or (ctx.pendingRecruits or {})[id]
        if t then
            local gold = 0
            for _, it in ipairs(t.items or {}) do gold = gold + cost(it.id) end
            local us = {}
            for _, uid in ipairs(talkers) do
                if byId[uid] then us[#us + 1] = byId[uid] end
            end
            out[#out + 1] = { id = "recruit:" .. id, kind = "recruit", unitId = id,
                              tile = { x = t.x, y = t.y }, gold = gold, takerUnits = us,
                              closes = closings["unit:" .. id],
                              path = runOn(paths[id], closings["unit:" .. id], t, style.memory, ctx) }
        end
    end
    return out
end

-- This board's closings and recruit paths (M.closings, then M.scriptedCloses), and its units by
-- id: the one read M.list and M.recruits share, kept on ctx for the board it was read on (the
-- Talk jobs read it once per exploring pass, and the planner's M.list again on the same board).
local function boardRead(board, sight, style, ctx)
    local r = ctx.goalRead
    if r and r.board == board then return r end
    local byId = {}
    for _, u in ipairs(board.units) do byId[u.id] = u end
    local open, walks = M.closings(sight, style, ctx)
    local closings, paths = M.scriptedCloses(sight, ctx, board, open, walks, style.memory)
    r = { board = board, byId = byId, closings = closings, paths = paths }
    ctx.goalRead = r
    return r
end

-- a sight without a read (test_bot's fakes) has no goal that needs it
local function costOf(sight) return sight.itemCost or function() return 0 end end

-- The recruit goals alone (recruitGoals), by the recruit's unit id: the Talk jobs' read
-- (bot.lua's exploring, #766), the same goals M.list prices. New tables each call: a caller may
-- set its own takers on one.
function M.recruits(board, sight, style, ctx)
    local r = boardRead(board, sight, style, ctx)
    local out = {}
    for _, g in ipairs(recruitGoals(r.byId, r.closings, r.paths, costOf(sight), style, ctx)) do
        out[g.unitId] = g
    end
    return out
end

function M.list(board, sight, style, ctx)
    local goals, blues = {}, {}
    local r = boardRead(board, sight, style, ctx)
    for _, u in ipairs(board.units) do
        if u.faction == "blue" and u.onField and not u.dead then blues[#blues + 1] = u end
    end
    local function takers(ok)
        local out = {}
        for _, u in ipairs(blues) do
            if ok(u) then out[#out + 1] = u end
        end
        return out
    end
    for _, g in ipairs(M.openTiles(sight, style, ctx, r.closings)) do
        g.takerUnits = takers(function(u)
            if sight.canExplore and sight.canExplore(u, g.tile.x, g.tile.y, g.kind) then
                return true
            end
            -- a chest whose key an enemy drops (sight.keySources): its turns run by way of
            -- that enemy (Bot's turnsTo), so its chance says whether that way is worth it
            local lock = g.kind == "chest" and sight.locked and sight.locked(u, g.tile.x, g.tile.y)
            return lock and sight.keySources ~= nil and #sight.keySources(u, lock) > 0 or false
        end)
        goals[#goals + 1] = g
    end
    for _, g in ipairs(recruitGoals(r.byId, r.closings, r.paths, costOf(sight), style, ctx)) do
        goals[#goals + 1] = g
    end
    for _, u in ipairs(ctx.objectiveTile and blues or {}) do
        local t = ctx.objectiveTile(u)
        if t then
            goals[#goals + 1] = { id = "objective:" .. u.id, kind = "objective",
                                  tile = { x = t.x, y = t.y }, gold = 0, share = 1 / #blues,
                                  takerUnits = { u } }
        end
    end
    table.sort(goals, function(a, b) return a.id < b.id end)
    return goals
end

-- a chance this small is none: sums of branch products leave float dust (planner.lua's DUST)
M.DUST = 1e-9

-- The one reading of "a new low" in turns to a goal, which botrun's progress count and the
-- planner's idle rule both take (#698): `t` strictly below `low`, past float dust; no low yet
-- is no new low. `lowest` folds a reading into the low it is compared with.
function M.nearer(t, low) return low ~= nil and t < low - M.DUST end
function M.lowest(low, t) return low and math.min(low, t) or t end

function M.ledger(goals, sight, style, ctx, chances)
    local reads = sight.canExplore ~= nil and sight.closings ~= nil
    local rows, byId = {}, {}
    for _, g in ipairs(goals) do
        if g.kind ~= "objective" and (chances[g.id] or 0) > M.DUST then
            local known = g.kind == "recruit" or reads
            local status = known and "feasible" or "unknown"
            -- a pending recruit (ctx.pendingRecruits, ADR 0436) cannot close before its turn, so
            -- no quiet count of it is a stall: it holds the win until it is there or its turn is
            -- past. One an act loads (`by`, ADR 0464) has no turn to pass: if no unit nears it, it
            -- stalls as any goal does, or an act this attempt never makes would hold the win
            local pending = g.kind == "recruit" and (ctx.pendingRecruits or {})[g.unitId]
            local waits = pending and not pending.by
            if known and not waits and (ctx.quietGoals or {})[g.id] then status = "stalled" end
            local row = { id = g.id, kind = g.kind, status = status, closes_on = g.closes }
            rows[#rows + 1], byId[g.id] = row, row
        end
    end
    for i, r in ipairs(style.rewards or {}) do
        if not voided(r, ctx.lost) then
            local ids, status, lost = {}, "feasible", false
            local quiet = false
            for _, g in ipairs(goals) do
                if g.kind ~= "objective" and needs(r, g) then
                    ids[#ids + 1] = g.id
                    lost = lost or not byId[g.id]
                    if byId[g.id] and byId[g.id].status == "unknown" then status = "unknown" end
                    if byId[g.id] and byId[g.id].status == "stalled" then quiet = true end
                end
            end
            if quiet and status == "feasible" then status = "stalled" end
            -- none of what it needs left open: taken already, so the game gives it, nothing to get
            if #ids > 0 and not lost then
                rows[#rows + 1] = { id = "reward:" .. i, kind = "reward", status = status,
                                    needs = ids }
            end
        end
    end
    return rows
end

function M.forfeited(ledger, goals, closes)
    local took, lost, shut = closes.took or {}, closes.lost or {}, {}
    local wins = (closes.win or 0) > M.DUST
    assert((closes.reach == nil) == (closes.gone == nil), "forfeited: reach and gone come together")
    local reach = closes.reach or {}
    for _, g in ipairs(goals) do
        if g.kind ~= "objective" and not took[g.id] then
            shut[g.id] = wins
                or (g.kind == "recruit" and (lost[g.unitId] or 0) > M.DUST)
                or (g.closes ~= nil and g.closes <= 1)
                or (g.closes ~= nil and reach[g.id] ~= nil and reach[g.id].before >= closes.gone
                    and reach[g.id].after <= M.DUST)
        end
    end
    local out = {}
    for _, r in ipairs(ledger) do
        local gone = shut[r.id]
        for _, id in ipairs(r.needs or {}) do gone = gone or shut[id] end
        if r.status == "feasible" and gone then out[#out + 1] = r.id end
    end
    -- What the record's clean clear loses whatever the ledger says (ADR 0475, #730, #711): an
    -- owed recruit's death (closes.owed, a set of unit ids: every owed recruit on the field, one
    -- no player unit may Talk yet included, less the ones whose death is the win itself: the
    -- Defeat-boss boss, a Rout's last red, which the planner leaves out). Its feasible row counts
    -- it above, once; one with no feasible row (none may Talk it yet, ADR 0452; its Talk has no
    -- chance this turn; its row stalled) is "owed:<unit id>". Its death only: a win does not
    -- close it (an unrelated one, a Seize, does not release it either), or a row nobody can take
    -- would hold the Seize for good. And a theft the game ranks as spoiling (closes.stolen, a
    -- set of the robbed units' ids: sight.pilfer's `spoils`) is "stolen:<unit id>".
    local counted = {}
    for _, r in ipairs(ledger) do
        if r.kind == "recruit" and r.status == "feasible" then counted[r.id] = true end
    end
    for id in pairs(closes.owed or {}) do
        if not counted["recruit:" .. id] and (lost[id] or 0) > M.DUST then
            out[#out + 1] = "owed:" .. id
        end
    end
    for id in pairs(closes.stolen or {}) do out[#out + 1] = "stolen:" .. id end
    table.sort(out)
    return out
end

-- Whether a goal of this kind is met beside its tile, not on it (the one owner of the answer:
-- chance, the planner's nearest and advance reads, the march's talk assignment). A Talk is made
-- from a tile beside the recruit, so a lock on the tile he stands on (vanilla Ch14's Rennac walks
-- over two unopened chests) is no cost of meeting him (#710).
local BESIDE = { recruit = true }
function M.beside(kind) return BESIDE[kind] or false end

function M.worth(goal, W)
    local v = goal.gold * W.gold
    if goal.kind == "recruit" then v = v + W.death end
    if goal.kind == "objective" then v = v + W.death * goal.share end
    return v
end

-- The turns a taker needs to meet a recruit the game's AI moves (goal.path, sight.closings'
-- second answer: the tile it stands on after each enemy phase, one fewer than goal.closes), or
-- nil: the earliest player phase f, up to the one it is removed after (goal.closes), in which
-- the taker can be at the tile the recruit stands on then (the current tile in phase 1,
-- path[f - 1] after) within f turns, by the same turnsTo the stationary price uses: to the
-- recruit's own tile. Past the path's last phase, with no removal, it stays where it ended.
-- `beside` (M.beside) asks turnsTo to leave the lock on his tile out: priced through the chests
-- Rennac walks over, every partial plan read his chance as 0 (#710).
-- Second and third answers: the tile he is met on and its phase.
-- `each(t, tile, f)` for each phase in turn whose meeting the taker makes, until it answers
-- true: meet's first, M.meetings' every one.
-- A trip of `t` turns (turnsTo's) begun `late` turns from now: the player phase it arrives in
-- (1: this one) and its chance, a gamma per turn on the way. The one clock every Talk and goal
-- price reads (meetEach, arrive, M.meetings, M.chance).
local function trip(t, late, gamma)
    return math.max(math.ceil(t), 1) + late, gamma and gamma ^ (math.max(t, 1) - 1 + late)
end

local function meetEach(goal, u, p, late, turnsTo, beside, each)
    local path = goal.path
    for f = 1, goal.closes or math.huge do
        local beyond = f - 1 > #path
        if beyond and goal.closes then return end
        local tile = f == 1 and goal.tile or path[math.min(f - 1, #path)] or goal.tile
        local t = turnsTo(u, tile, p, beside)
        if t and (beyond or trip(t, late) <= f) and each(t, tile, f) then return end
        if beyond then return end
    end
end

local function meet(goal, u, p, late, turnsTo, beside)
    local mt, mtile, mf
    meetEach(goal, u, p, late, turnsTo, beside, function(t, tile, f)
        mt, mtile, mf = t, tile, f
        return true
    end)
    return mt, mtile, mf
end

-- When taker `u` (at `p`, M.chance's position, `late` turns spent first) gets to `goal`: its
-- turns (turnsTo's), the tile it gets the goal on and the player phase from now (1: this one),
-- or nil when it cannot before the goal closes. A recruit the game moves is met on his way
-- (meet); any other goal stands where it is. The one read M.chance and M.meetings share.
local function arrive(goal, u, p, late, turnsTo)
    local beside = M.beside(goal.kind)
    -- the deadline is in the meeting's phase (meet), so no closes test after it
    if goal.path and #goal.path > 0 then return meet(goal, u, p, late, turnsTo, beside) end
    local t = turnsTo(u, goal.tile, p, beside)
    local f = t and trip(t, late)
    if not f or goal.closes and goal.closes < f then return nil end
    return t, goal.tile, f
end

-- Every meeting taker `u` (at `p`, M.chance's position) can make with a recruit on his way
-- (#766: the job is "get him", worth its best meeting, not its first: vanilla Ch14's Rennac is
-- met first in the corridor the enemy holds, and later, safely, at the map's edge):
-- { { tile, f (its player phase from now), c (its chance: M.chance's for a lone taker, one gamma
-- more for each turn it waits there for him), turns (the turn it gets there on) } }, soonest first.
-- A goal with no path is met where it is.
function M.meetings(goal, u, p, gamma, turnsTo)
    local late = (p.late or 0) + (p.acted and 1 or 0)
    local out = {}
    -- every turn until the Talk costs a gamma: the trip's (as M.chance), then the wait there
    -- for him, so a later meeting is never worth more for being nearer
    -- A meeting past the walk's end (meetEach's `beyond`, no removal) is made whenever the taker
    -- arrives, later than that phase too: it is met on its arrival, and no wait is negative (PR
    -- #777 review: a talker 8 turns off read a meeting at phase 4 at gamma^-4, above every
    -- nearer one)
    local function add(t, tile, f)
        local turns, c = trip(t, late, gamma)
        f = math.max(f, turns)
        out[#out + 1] = { tile = tile, f = f, turns = turns, c = c * gamma ^ (f - turns) }
    end
    if goal.path and #goal.path > 0 then
        meetEach(goal, u, p, late, turnsTo, M.beside(goal.kind), function(t, tile, f) add(t, tile, f) end)
    else
        local t, tile, f = arrive(goal, u, p, late, turnsTo)
        if t then add(t, tile, f) end
    end
    return out
end

function M.chance(goal, pos, gamma, turnsTo)
    local options = {}
    for _, u in ipairs(goal.takerUnits) do
        local p = pos[u.id]
        -- a chest's taker lives to open it AND keeps the key that opens it: p.opens is that one
        -- chance, read per way of the phase (planner.lua, #711: a thief's steal of its last
        -- opener), where p.alive x (1 - robbed) would count a way that kills the holder twice
        local alive = p and (goal.kind == "chest" and p.opens or p.alive or 1)
        if p and alive > 0 then
            -- p.late: the turns a chain of jobs already spends before this one (jobs.lua), so
            -- its deadline and GAMMA count from now, not from the chain's last tile
            local late = (p.late or 0) + (p.acted and 1 or 0)
            local t = arrive(goal, u, p, late, turnsTo)
            if t then
                local turns, c = trip(t, late, gamma)
                options[#options + 1] = { c = c, alive = alive, turns = turns }
            end
        end
    end
    table.sort(options, function(a, b) return a.c > b.c end)
    local out, none = 0, 1
    for _, o in ipairs(options) do
        out = out + none * o.alive * o.c
        none = none * (1 - o.alive)
    end
    -- and the turns the likeliest taker arrives on, counted from now (a chain's next job,
    -- jobs.lua, starts from there)
    return out, options[1] and options[1].turns
end

return M
