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
--                  may Talk it over); its takers are those talkers.
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
-- `closes`: sight.closings(k, style.waves) -- the enemy phase after which a looter has it.
--
-- Goals.worth(goal, W) -> points: gold x W.gold, plus W.death for a recruit (a unit), and for
-- the objective's way there one W.death shared over the army (`share`): no style walks into a
-- death for it, and each unit is pulled forward as the old flat ground term pulled it (careful:
-- ~111 a unit of nine, a turn closer ~9 against the old 8). The win itself is the planner's W.win.
--
-- Goals.chance(goal, pos, gamma, turnsTo) -> 0..1: pos[unit id] = { x, y, acted, alive (0..1) },
-- the board a plan leaves. t = turnsTo(u, tile, pos), its turns there (sight's: cost / MOV, not
-- rounded); one that has acted takes it a turn later. The chance is gamma ^ (max(t, 1) - 1 +
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
-- a reward is unknown when a goal it needs is. A goal no unit can reach this turn (a unit in
-- the way) stays feasible: only a closure loses it. One with no chance at all is no goal of
-- the bot's: the game lets no player unit use it (a chest with no key in the army and none on
-- an enemy that drops it), none has a way
-- there (sight.turnsTo reads the terrain, through a breach), or a looter takes it first. Kept,
-- it would close with every win and so forbid the win for good. A reward needing one of those
-- can never be had, and is no row either.
-- Goals.forfeited(ledger, goals, closes) -> the sorted ids of the feasible rows a plan loses
-- for good (FR-011's forfeits), `closes` what the plan does in the judged phase, each a chance
-- over its judged branches: { win (the chapter ends), took = { [goal id] = true }, lost =
-- { [recruit unit id] = chance it dies } }. Counted conservatively (FR-014): a goal is lost
-- when it is lost in any branch with p > 0, so any chance at all is the whole goal. A win
-- closes every goal the plan does not take; a recruit's death closes its Talk; a looter's
-- closing after this phase (`closes` 1) closes a tile the plan does not take; a reward closes
-- with any goal it needs. A unit whose death ends the game closes nothing here: its risk is
-- admission's, within the style's cap, and counted again as a forfeit the plan whose lord is
-- at 0% would beat every plan that puts it in danger (Nicolas, 2026-11-02: ADR 0384).

local M = {}

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

-- The villages and chests still open, each with its worth in gold and when it closes:
-- { { id, kind, x, y, tile, gold, closes } }. Goals.list's, and Bot.candidates' exploring ranks who
-- is sent where by it.
function M.openTiles(sight, style, ctx)
    local cost = sight.itemCost or function() return 0 end
    local explored = ctx.explored or {}
    local closings = sight.closings and sight.closings(nil, style.waves) or {}
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

function M.list(board, sight, style, ctx)
    local goals, blues, byId = {}, {}, {}
    -- a sight without a read (test_bot's fakes) has no goal that needs it
    local cost = sight.itemCost or function() return 0 end
    for _, u in ipairs(board.units) do
        byId[u.id] = u
        if u.faction == "blue" and u.onField and not u.dead then blues[#blues + 1] = u end
    end
    local function takers(ok)
        local out = {}
        for _, u in ipairs(blues) do
            if ok(u) then out[#out + 1] = u end
        end
        return out
    end
    for _, g in ipairs(M.openTiles(sight, style, ctx)) do
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
    for id, talkers in pairs(ctx.recruitTalkers or {}) do
        local t = byId[id]
        if t then
            local gold = 0
            for _, it in ipairs(t.items or {}) do gold = gold + cost(it.id) end
            local us = {}
            for _, uid in ipairs(talkers) do
                if byId[uid] then us[#us + 1] = byId[uid] end
            end
            goals[#goals + 1] = { id = "recruit:" .. id, kind = "recruit", unitId = id,
                                  tile = { x = t.x, y = t.y }, gold = gold, takerUnits = us }
        end
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

function M.ledger(goals, sight, style, ctx, chances)
    local reads = sight.canExplore ~= nil and sight.closings ~= nil
    local rows, byId = {}, {}
    for _, g in ipairs(goals) do
        if g.kind ~= "objective" and (chances[g.id] or 0) > M.DUST then
            local known = g.kind == "recruit" or reads
            local row = { id = g.id, kind = g.kind, status = known and "feasible" or "unknown",
                          closes_on = g.closes }
            rows[#rows + 1], byId[g.id] = row, row
        end
    end
    for i, r in ipairs(style.rewards or {}) do
        if not voided(r, ctx.lost) then
            local ids, status, lost = {}, "feasible", false
            for _, g in ipairs(goals) do
                if g.kind ~= "objective" and needs(r, g) then
                    ids[#ids + 1] = g.id
                    lost = lost or not byId[g.id]
                    if byId[g.id] and byId[g.id].status == "unknown" then status = "unknown" end
                end
            end
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
    for _, g in ipairs(goals) do
        if g.kind ~= "objective" and not took[g.id] then
            shut[g.id] = wins
                or (g.kind == "recruit" and (lost[g.unitId] or 0) > M.DUST)
                or (g.kind ~= "recruit" and g.closes ~= nil and g.closes <= 1)
        end
    end
    local out = {}
    for _, r in ipairs(ledger) do
        local gone = shut[r.id]
        for _, id in ipairs(r.needs or {}) do gone = gone or shut[id] end
        if r.status == "feasible" and gone then out[#out + 1] = r.id end
    end
    table.sort(out)
    return out
end

function M.worth(goal, W)
    local v = goal.gold * W.gold
    if goal.kind == "recruit" then v = v + W.death end
    if goal.kind == "objective" then v = v + W.death * goal.share end
    return v
end

function M.chance(goal, pos, gamma, turnsTo)
    local options = {}
    for _, u in ipairs(goal.takerUnits) do
        local p = pos[u.id]
        if p and (p.alive or 1) > 0 then
            local t = turnsTo(u, goal.tile, p)
            if t then
                local late = p.acted and 1 or 0
                if not goal.closes or goal.closes >= math.max(math.ceil(t), 1) + late then
                    options[#options + 1] = { c = gamma ^ (math.max(t, 1) - 1 + late),
                                              alive = p.alive or 1 }
                end
            end
        end
    end
    table.sort(options, function(a, b) return a.c > b.c end)
    local out, none = 0, 1
    for _, o in ipairs(options) do
        out = out + none * o.alive * o.c
        none = none * (1 - o.alive)
    end
    return out
end

return M
