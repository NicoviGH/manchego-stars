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
--                  takers = our units the game lets use it (sight.canExplore).
--   recruit        each unit ctx.recruitTalkers names (Bot.candidates: the units of ours that
--                  may Talk it over); its takers are those talkers.
--   objective      each unit's own way to the objective (ctx.objectiveTile: the Seize tile,
--                  the boss, or on Rout the nearest enemy -- where its march heads), the unit
--                  its one taker. None on Survive, whose way there is holding.
-- goal = { id, kind, tile = {x, y}, gold, takerUnits = { unit }, closes = enemy phase | nil }.
-- `gold` (Goals.worth makes it points):
--   a village or chest: the mean gift over every vanilla village (style.villageGifts: items
--     at sight.itemCost, the game's own GetItemCost; gold at face value) -- a new player does
--     not know what one holds;
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
-- rounded); one that has acted starts a turn later. The chance is gamma ^ (t + late - 1), at
-- most 1: each turn further is another enemy phase where something can go wrong, and every
-- step counts, the last one into reach too (a talker one step from its recruit's side was
-- indifferent between that tile and one farther off but still in reach). A goal closed before
-- the phase the taker really arrives on (closes < ceil(t) + late, at least phase 1) is 0 for
-- it. Over the takers, the expected best as each lives (alive), the best first.

local M = {}

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
    if reward.needs == "villages" then return g.kind == "visit" end
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
    local explored, closings = ctx.explored or {}, sight.closings and
        sight.closings(nil, style.waves) or {}
    local worth = prior(cost, style.villageGifts)
    for _, t in ipairs(sight.explorable and sight.explorable() or {}) do
        local k = key(t.x, t.y)
        if not explored[k] then
            goals[#goals + 1] = {
                id = t.kind .. ":" .. k, kind = t.kind, tile = { x = t.x, y = t.y }, gold = worth,
                closes = closings[k],
                takerUnits = takers(function(u)
                    return sight.canExplore and sight.canExplore(u, t.x, t.y, t.kind)
                end),
            }
        end
    end
    -- a reward's item, shared over the open goals it needs
    for _, r in ipairs(style.rewards or {}) do
        if not voided(r, ctx.lost) then
            local share = {}
            for _, g in ipairs(goals) do
                if needs(r, g) then share[#share + 1] = g end
            end
            for _, g in ipairs(share) do g.gold = g.gold + cost(r.item) / #share end
        end
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
                    options[#options + 1] = { c = gamma ^ math.max(t + late - 1, 0),
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
