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
--      to kill our unit, HP healed, a recruit, ground gained toward the goal -- less each moved
--      unit's standing exposure: its chance to die and the HP it loses if every enemy that
--      reaches its tile strikes it (an enemy the plan kills does not; the HP is the plan's).
--      Without it the beam ranked only what a unit does, and every plan it kept was the
--      exposed one: the judge then had nothing safe to pick (ch03, 2026-10-27).
--   3. Judge: the best FINAL complete plans each meet the enemy phase the game's own AI would
--      play against them (sight.enemyPhase), which replaces the exposure estimate: they pay
--      for each unit's chance to die there, its expected damage, and a fog risk for a fragile
--      unit left beside ground it cannot see.
--   4. The best plan's first act is returned, and the plan with it: botrun plays the plan's
--      next act after each one unless M.surprise finds the board off what the plan expected
--      (a miss, a kill, a death, a newly seen enemy), and only then plans again. Judging is
--      most of a plan's cost, and an act that went as expected leaves the plan as good as it
--      was.
-- Honesty: outcomes are odds (Sight.hitChance: FE8's two-roll hit; crits one roll), never the
-- game's next random numbers; an enemy the player cannot see is in no plan (Bot.candidates and
-- sight.enemyPhase skip it); the enemy's choices are the game's own AI.
-- Styles are weights (M.WEIGHTS): how much a unit's death costs against progress.
--
-- api: Planner.plan(Bot, board, sight, style) -> the first act of the best plan (bot.lua's
-- action shape) or nil when no unit can act, and the plan's record { score, acts, expect,
-- enemies, judged }. Planner.surprise(plan, k, before, after, visible) -> why the board after
-- its k-th act calls for a new plan, or nil to play act k + 1.

local M = {}

M.BEAM = 6         -- partial plans kept at each depth
M.PER_UNIT = 4     -- a unit's best acts, by their own score, that the beam tries (and its
                   -- hold and retreat, always: the way out survives the cut)
M.FINAL = 4        -- complete plans judged against the enemy phase
M.FOG_REACH = 6    -- unseen ground this close to a unit may hide what can strike it
M.BOSS_WORTH = 5   -- damage on a Defeat Boss map's boss, per point, against any other's

-- death: one unit's death; taken: per HP short at the phase's end; dealt: per HP; kill: per enemy removed; progress: per step
-- of the march field; heal: per HP restored; recruit: a unit talked over; breach: a way
-- opened; win: a Seize; fog: a fragile unit beside the unseen.
M.WEIGHTS = {
    careful = { death = 1000, taken = 2, dealt = 1, kill = 30, progress = 2, heal = 1.5,
                recruit = 200, breach = 25, win = 100000, fog = 40 },
    even = { death = 300, taken = 1, dealt = 1, kill = 30, progress = 3, heal = 1,
             recruit = 200, breach = 25, win = 100000, fog = 15 },
    bold = { death = 60, taken = 0.5, dealt = 1, kill = 40, progress = 4, heal = 0.5,
             recruit = 200, breach = 25, win = 100000, fog = 0 },
}

local CRIT = 3     -- bmbattle.c: damage x3 on a critical hit

-- One strike's blows: { hit chance, crit chance, damage } each, `hits` of them.
function M.blows(hitRate, dmg, hits, critRate, hitChance)
    local out = {}
    local p, c = hitChance(hitRate or 0), math.max(0, math.min(100, critRate or 0)) / 100
    for _ = 1, hits or 0 do out[#out + 1] = { p = p, c = c, dmg = dmg or 0 } end
    return out
end

-- The damage a list of blows deals, as a distribution { [damage] = probability }, capped at
-- `cap` (the target's HP: past it, it is dead and the rest does not matter).
function M.damage(blows, cap)
    local dist = { [0] = 1 }
    for _, b in ipairs(blows) do
        local nxt = {}
        local function add(d, p)
            if p > 0 then
                d = math.min(d, cap)
                nxt[d] = (nxt[d] or 0) + p
            end
        end
        for d, p in pairs(dist) do
            if d >= cap then
                add(d, p)
            else
                add(d, p * (1 - b.p))
                add(d + b.dmg, p * b.p * (1 - b.c))
                add(d + b.dmg * CRIT, p * b.p * b.c)
            end
        end
        dist = nxt
    end
    return dist
end

-- P(the blows deal at least `hp`), and the expected damage (capped at `hp`).
function M.odds(blows, hp)
    local dead, mean = 0, 0
    for d, p in pairs(M.damage(blows, hp)) do
        if d >= hp then dead = dead + p end
        mean = mean + d * p
    end
    return dead, mean
end

-- `act`'s standing exposure for a unit at `hp`, the enemies in `gone` left out: the chance
-- it dies and the HP it loses if each enemy that reaches its tile strikes it.
local function exposed(act, hp, gone, hitChance)
    local blows = {}
    for _, s in ipairs(act.exposure or {}) do
        if not gone[s.id] then
            for _, b in ipairs(M.blows(s.hit, s.dmg, s.hits, s.crit, hitChance)) do
                blows[#blows + 1] = b
            end
        end
    end
    if #blows == 0 then return 0, 0 end
    return M.odds(blows, hp)
end

-- An act's own score, given the partial plan `st` before it (enemy HP already taken, enemies
-- already counted gone). Returns the score and the act's effects on the plan.
local function score(act, st, W, style, hitChance)
    local fx = { hp = act.unitHp, gone = nil, enemyHp = nil }
    local v = W.progress * (act.progress or 0)
    if act.act == "attack" and act.f then
        local f, e = act.f, act.targetUnit
        local hp = st.enemyHp[e.id] or e.hp
        local ours = M.blows(f.hit, f.dmg, f.hits, f.crit, hitChance)
        local kill, dealt = M.odds(ours, hp)
        -- the objective's boss: every point of its HP is a step to the win
        local target = (e.isBoss and st.objective == "boss") and M.BOSS_WORTH or 1
        local worth = (e.isBoss and 5 or 1) + (act.first and 1 or 0)
        v = v + W.dealt * dealt * target + W.kill * kill * worth
        if f.counters then
            -- the counter's risk is its chance to kill; the HP it takes is paid once, at the
            -- end, after any heal the plan gives back (the judge's deficit)
            local back = M.blows(f.counterHit, f.counterDmg, f.counterHits, f.counterCrit, hitChance)
            local die, taken = M.odds(back, act.unitHp)
            v = v - (1 - kill) * W.death * die
            fx.hp = math.max(1, act.unitHp - math.floor((1 - kill) * taken + 0.5))
        end
        fx.enemyHp = { id = e.id, hp = hp - dealt }
        if kill >= 0.5 then fx.gone = e.id end
        if e.isBoss and kill >= 0.5 and st.objective == "boss" then v = v + W.win * kill end
    elseif act.act == "talk" then
        v = v + W.recruit
    elseif act.act == "staff" and act.amount then
        -- a planned heal: what the target is short by now in the plan, up to the staff's amount
        local t = act.targetUnit
        local hp = st.hp[t.id] or t.hp
        local gain = math.min(act.amount, (t.maxhp or hp) - hp)
        v = v + W.heal * gain
        fx.heals = { id = t.id, hp = hp + gain }
        -- the game offers Staff only on someone hurt: a heal before the blow is no act
        fx.blocked = gain <= 0
    elseif act.act == "staff" or act.act == "item" then
        v = v + W.heal * (act.gain or 0)
    elseif act.obstacle or act.act == "door" then
        v = v + W.breach
    elseif act.act == "seize" then
        v = v + W.win
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

function M.plan(Bot, board, sight, style)
    local W = M.WEIGHTS[style.aggression]
    if not W then error("planner.lua: no weights for style " .. tostring(style.aggression)) end
    local hitChance = sight.hitChance
    local cands, ctx = Bot.candidates(board, sight, style)
    if #cands == 0 then return nil end
    local byId = {}
    for _, u in ipairs(board.units) do byId[u.id] = u end
    local objective = sight.objective and sight.objective.kind
    local start = { score = 0, base = 0, acts = {}, expect = {}, used = {}, tiles = {},
                    gone = {}, enemyHp = {}, hp = {}, objective = objective }

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
            local die, taken = exposed(a, hp, gone, hitChance)
            r = W.death * die + W.taken * taken
            risks[k] = r
        end
        return r
    end

    -- each unit's acts, its own best first, PER_UNIT of them
    local menus = {}
    for _, c in ipairs(cands) do
        local scored = {}
        for _, a in ipairs(c.acts) do
            a.unitHp = c.unit.hp
            a.targetUnit = a.targetId and byId[a.targetId]
            local v, fx = score(a, start, W, style, hitChance)
            scored[#scored + 1] = { a = a, v = v - risk(a, fx.hp, fx.gone and { [fx.gone] = true } or {}) }
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

    -- the beam: every depth, each plan extended by one more unit's act
    local beam = { start }
    for _ = 1, #menus do
        local nxt, seenSig = {}, {}
        for _, st in ipairs(beam) do
            for _, m in ipairs(menus) do
                if not st.used[m.unit.id] then
                    for _, a in ipairs(m.acts) do
                        local tile = a.move.x .. "," .. a.move.y
                        local blocked = st.tiles[tile]
                            or (a.targetId and st.gone[a.targetId])
                            or (a.act == "staff" and moved(st, a.targetId))
                        if not blocked then
                            local v, fx = score(a, st, W, style, hitChance)
                            if fx.blocked then goto skip end
                            local n = { base = st.base + v, acts = copy(st.acts),
                                        expect = copy(st.expect),
                                        used = copy(st.used), tiles = copy(st.tiles),
                                        gone = copy(st.gone), enemyHp = copy(st.enemyHp),
                                        hp = copy(st.hp), objective = objective }
                            n.acts[#n.acts + 1] = a
                            -- what the board should show after it (M.surprise): a Talk takes
                            -- its target off the enemy side as a kill does
                            n.expect[#n.acts] = { hp = fx.hp, gone = fx.gone
                                                      or (a.act == "talk" and a.targetId or nil),
                                                  targetHp = fx.enemyHp and fx.enemyHp.hp,
                                                  heals = fx.heals }
                            n.used[m.unit.id], n.tiles[tile] = true, true
                            n.hp[m.unit.id] = fx.hp
                            if fx.gone then n.gone[fx.gone] = true end
                            if fx.enemyHp then n.enemyHp[fx.enemyHp.id] = fx.enemyHp.hp end
                            if fx.heals then n.hp[fx.heals.id] = fx.heals.hp end
                            -- every moved unit's exposure, again: a later kill or heal in
                            -- the plan changes an earlier unit's
                            n.score = n.base
                            for _, x in ipairs(n.acts) do
                                n.score = n.score - risk(x, n.hp[x.unitId] or x.unitHp, n.gone)
                            end
                            -- in order: a heal after a blow is not the heal before it
                            local sig = {}
                            for _, x in ipairs(n.acts) do sig[#sig + 1] = key(x) end
                            sig = table.concat(sig, "|")
                            if not seenSig[sig] then
                                seenSig[sig] = true
                                nxt[#nxt + 1] = n
                            end
                            ::skip::
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
        beam = {}
        for i = 1, math.min(M.BEAM, #nxt) do beam[i] = nxt[i] end
    end

    -- judge the best complete plans against the enemy phase the AI would play
    local unseen = sight.unseen and sight.unseen() or {}
    local best
    for i = 1, math.min(M.FINAL, #beam) do
        local st = beam[i]
        local planned, at = {}, {}
        for _, a in ipairs(st.acts) do at[a.unitId] = a end
        for _, u in ipairs(ctx.blues) do
            local a = at[u.id]
            planned[#planned + 1] = { unit = u, x = a and a.move.x or u.x, y = a and a.move.y or u.y,
                                      hp = st.hp[u.id] or u.hp }
        end
        local strikes = sight.enemyPhase and sight.enemyPhase({ blues = planned, gone = st.gone })
            or {}
        local onUnit = {}
        for _, s in ipairs(strikes) do
            onUnit[s.target] = onUnit[s.target] or {}
            for _, b in ipairs(M.blows(s.takenHit, s.takenDmg, s.takenHits, s.takenCrit, hitChance)) do
                table.insert(onUnit[s.target], b)
            end
        end
        local judged = st.base
        st.predict = {}
        for _, p in ipairs(planned) do
            local die, taken = M.odds(onUnit[p.unit.id] or {}, p.hp)
            st.predict[#st.predict + 1] = { id = p.unit.id, charId = p.unit.charId, x = p.x,
                                            y = p.y, hp = p.hp, die = die, taken = taken,
                                            blows = #(onUnit[p.unit.id] or {}) }
            -- the HP the phase leaves it short: the plan's own deficit, then the enemy's
            local short = ((p.unit.maxhp or p.hp) - p.hp) + taken
            judged = judged - W.death * die - W.taken * short
            if W.fog > 0 then
                for _, t in ipairs(unseen) do
                    if math.abs(t.x - p.x) + math.abs(t.y - p.y) <= M.FOG_REACH then
                        judged = judged - W.fog * 10 / math.max(p.hp, 1)
                        break
                    end
                end
            end
        end
        st.judged = judged
        st.strikes = strikes
        if not best or judged > best.judged then best = st end
    end
    if not best or #best.acts == 0 then return nil end
    best.enemies = {}
    for _, e in ipairs(ctx.enemies) do best.enemies[e.id] = true end
    return best.acts[1], best
end

-- Why the board `after` the plan's k-th act (played from `before`) is off what the plan
-- expected, so the rest of it was planned for a board that is not there; nil when act k + 1
-- may be played as planned. `visible(x, y)` is the player's sight after the act (fog).
-- Taking LESS from a counter, or dealing more without a kill, is no surprise: the plan
-- reckoned with worse.
function M.surprise(plan, k, before, after, visible)
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
        if u.faction == "red" and not plan.enemies[u.id] and (not visible or visible(u.x, u.y)) then
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
    -- the next act must still be there to play
    local u = now[nxt.unitId]
    if not u or u.acted then return "the next unit cannot act" end
    if nxt.targetId and not now[nxt.targetId] then return "the next target is gone" end
    -- the game offers Staff only on someone hurt: a counter that missed leaves none
    local t2 = nxt.act == "staff" and nxt.targetId and now[nxt.targetId]
    if t2 and t2.hp >= (t2.maxhp or t2.hp) then return "the heal's target is not hurt" end
    return nil
end

return M
