-- controller.lua -- pure FE8 playtest state classification and legal actions.
--
-- The mGBA-facing observer/driver lives in harness.lua. It converts decomp memory into
-- the plain observation tables consumed here, asks for legal intentions, executes one
-- guarded key, and verifies the resulting observation. Keeping this module pure makes
-- the controller contract testable without an emulator.

local M = {}

local MENU_ENABLED = 1
local MENU_WEAPON_FIRST = 0x49
local MENU_WEAPON_LAST = 0x4D
local MENU_SEIZE = 0x4E
local MENU_ATTACK = 0x4F
local MENU_BALLISTA_ATTACK = 0x50
local MENU_TALK = 0x5A
local MENU_VISIT = 0x5C
local MENU_CHEST = 0x5D
local MENU_DOOR = 0x5E
local MENU_ITEM = 0x67
local MENU_SUPPLY = 0x69
local MENU_WAIT = 0x6B
local MENU_UNIT_LIST = 0x6E
local MENU_STATUS = 0x6F
local MENU_END_PHASE = 0x78

local function proc(observation, name)
    return observation.procs and observation.procs[name] or nil
end

local function idleIs(observation, name, idle)
    local p = proc(observation, name)
    return p ~= nil and p.idle == idle
end

local function enabledMenuItems(observation)
    local out = {}
    if not observation.menu or type(observation.menu.items) ~= "table" then return out end
    for _, item in ipairs(observation.menu.items) do
        if item.availability == MENU_ENABLED then out[#out + 1] = item end
    end
    return out
end

local function menuKinds(observation)
    local unit, map, weapon = false, false, false
    for _, item in ipairs(enabledMenuItems(observation)) do
        if item.override_id >= MENU_WEAPON_FIRST and item.override_id <= MENU_WEAPON_LAST then
            weapon = true
        end
        if item.override_id == MENU_SEIZE or item.override_id == MENU_ATTACK
            or item.override_id == MENU_BALLISTA_ATTACK
            or item.override_id == MENU_TALK or item.override_id == MENU_CHEST
            or item.override_id == MENU_DOOR or item.override_id == MENU_ITEM
            or item.override_id == MENU_SUPPLY or item.override_id == MENU_WAIT then unit = true end
        if item.override_id == MENU_END_PHASE then map = true end
    end
    return unit, map, weapon
end

-- ---------------------------------------------------------------- classification rules
-- Ordered rules, evaluated top to bottom. One rule list serves both classify() (the
-- verdict) and explain() (the verdict PLUS what every earlier rule rejected and why),
-- so the two can never drift apart. #232 spent a full build-and-run cycle per hypothesis
-- because a `transition` verdict said nothing about what had been considered.
--
-- A rule returns exactly one of:
--   matched(state, detail, unclassified)  this is the state; detail says how we know
--   rejected(reason)                      not this state, and why -- the diagnostic payload
--   unsupported(why)                      fail closed; the observation makes no sense
--
-- `unclassified` marks a transition matched purely on a proc EXISTING, without
-- recognizing what it is currently waiting in. Those are the ones that hide an input
-- wait nothing can advance -- ch01's Northlook scene is exactly this shape.
local function matched(state, detail, unclassified)
    return { state = state, detail = detail, unclassified = unclassified or false }
end
local function rejected(reason) return { reject = reason } end
local function unsupported(why) return { error = why } end

local function idleOf(observation, name)
    local p = proc(observation, name)
    return p and p.idle or nil
end

-- "absent" and "live but in another callback" are different bugs with different fixes,
-- so the rejection has to distinguish them by name.
local function missIs(observation, name, wanted)
    local idle = idleOf(observation, name)
    if idle == nil then return name .. " proc absent" end
    return string.format("%s idle=%s, not %s", name, tostring(idle), wanted)
end

-- The boot/menu states that are identified by one proc sitting in one exact callback.
local SIMPLE_INPUT_RULES = {
    { rule = "health_safety_wait", proc = "game_early_start", idle = "health_safety_wait" },
    { rule = "title_idle", proc = "title", idle = "title_idle" },
    { rule = "save_menu_input", proc = "save_menu", idle = "save_menu_input" },
    { rule = "save_slot_input", proc = "save_menu", idle = "save_slot_input" },
    { rule = "difficulty_input", proc = "difficulty", idle = "difficulty_input" },
    { rule = "chapter_intro_input", proc = "chapter_intro", idle = "chapter_intro_input" },
}

-- Procs that make the game passive without ever offering an input. A match here means
-- "something is running and we have no name for what it wants" -- the blind spot.
local PASSIVE_PROCS = { "talk_wait", "std_event", "battle_forecast", "battle" }
local BOOT_PROCS = {
    "game_control", "game_early_start", "title", "save_menu", "difficulty", "chapter_intro",
    "talk_wait", "std_event", "map_fade", "battle_forecast", "battle", "at_menu", "sally",
}

local function anyLive(observation, names)
    for _, name in ipairs(names) do
        if proc(observation, name) then
            return string.format("%s live (idle=%s)", name, tostring(idleOf(observation, name)))
        end
    end
    return nil
end

local RULES = {
    {
        name = "observation",
        check = function(observation)
            if observation.error then return unsupported(observation.error) end
            return rejected("the observer reported no malformed structure")
        end,
    },
    {
        name = "pre_boot",
        check = function(observation)
            if observation.world and observation.world.chapter == 0 and observation.world.turn == 0
                and next(observation.procs or {}) == nil then
                return matched("transition", "empty proc pool before FE8 startup")
            end
            return rejected("the proc pool is not empty, or the game is past startup")
        end,
    },
    {
        -- Ordered ABOVE `dialogue_wait` and the passive rules on purpose, and that order is
        -- pinned by tests. The prompt runs INSIDE a live event scene, so `std_event` would
        -- swallow it as a transition -- which is how ch01's lord-select prompt stayed
        -- invisible through #232. `dialogue_wait` is the subtler version of the same trap:
        -- it would answer "press A", the choice's key handler would CONSUME that A, and the
        -- prompt would be answered by accident with the run still green (#241 review).
        -- General rule for this table: the more SPECIFIC state outranks the more general
        -- one -- a live YesNoChoice in its key handler owns the A button, whatever else is
        -- on screen.
        name = "yes_no_choice",
        check = function(observation)
            if not proc(observation, "yes_no") then return rejected("yes_no proc absent") end
            if not idleIs(observation, "yes_no", "yes_no_input") then
                return matched("transition", string.format("yes_no idle=%s, not its key handler",
                    tostring(idleOf(observation, "yes_no"))))
            end
            if not observation.choice then
                return matched("transition", "yes_no live with no observed choice")
            end
            return matched("yes_no_choice", "yes_no in its key handler")
        end,
    },
    {
        name = "dialogue_wait",
        check = function(observation)
            if idleIs(observation, "talk_wait", "talk_wait_input") then
                return matched("dialogue_wait", "talk_wait in talk_wait_input")
            end
            return rejected(missIs(observation, "talk_wait", "talk_wait_input"))
        end,
    },
    {
        name = "target_selection",
        check = function(observation)
            if not proc(observation, "target_selection") then
                return rejected("target_selection proc absent")
            end
            if not idleIs(observation, "target_selection", "target_selection_input") then
                return matched("transition", string.format("target_selection idle=%s, not its input loop",
                    tostring(idleOf(observation, "target_selection"))))
            end
            if not observation.target then
                return matched("transition", "target_selection live with no observed target")
            end
            if observation.target.frozen then
                return matched("transition", "target_selection is frozen")
            end
            if observation.target.kind ~= "attack" and observation.target.kind ~= "talk" then
                return unsupported("unsupported target selection kind")
            end
            return matched("target_selection", "target_selection in its input loop")
        end,
    },
    {
        name = "menu",
        check = function(observation)
            local menuProc = proc(observation, "menu")
            if not menuProc then return rejected("menu proc absent") end
            if not idleIs(observation, "menu", "menu_input") then
                return matched("transition", string.format("menu idle=%s, not menu_input",
                    tostring(menuProc.idle)))
            end
            for _, flag in ipairs({ "locked", "frozen", "ending", "doomed" }) do
                if menuProc[flag] then
                    return matched("transition", "menu is " .. flag)
                end
            end
            if not observation.menu then
                return matched("transition", "menu proc live with no observed menu structure")
            end
            local unit, map, weapon = menuKinds(observation)
            if weapon and (unit or map) then
                return unsupported("ambiguous standard menu mixes weapon and command items")
            end
            if unit and map then
                return unsupported("ambiguous standard menu contains unit and map commands")
            end
            if weapon then return matched("weapon_menu", "menu offers weapon items") end
            if unit then return matched("unit_command_menu", "menu offers unit commands") end
            if map then return matched("map_command_menu", "menu offers map commands") end
            local enabled = enabledMenuItems(observation)
            local callbacks = #enabled > 0
            for _, item in ipairs(enabled) do
                if not item.on_selected then callbacks = false break end
            end
            if callbacks then return matched("generic_menu", "every enabled item has a callback") end
            return unsupported("unsupported standard menu has no recognized semantic commands")
        end,
    },
    {
        -- Ordered ABOVE player_phase, and that order is load-bearing. The Character screen is
        -- opened from the map menu DURING the player phase, so gProcScr_PlayerPhase is still
        -- in the pool underneath it -- and the player_phase rule would answer
        -- `player_map_idle`, advertising cursor moves for a map nothing can reach. It is not
        -- a MenuProc either, so the menu rule never sees it: this is a whole screen with its
        -- own key handler, and until it was named a scenario walking the roster was pressing
        -- DOWN into a state the controller had no word for (#238).
        name = "unit_list",
        check = function(observation)
            if not proc(observation, "unit_list") then return rejected("unit_list proc absent") end
            if not idleIs(observation, "unit_list", "unit_list_input") then
                return matched("transition", string.format("unit_list idle=%s, not its key handler",
                    tostring(idleOf(observation, "unit_list"))))
            end
            if not observation.unit_list then
                return matched("transition", "unit_list live with no observed list structure")
            end
            -- unk_29 selects which branch sub_8091AEC runs: 0 is the key handler, 1 and 2 are
            -- the row/page scroll animating. FE8 reads no D-pad in that window, so a press
            -- sent then is simply LOST -- the exact shape of failure #232 spent sessions on.
            if observation.unit_list.scrolling then
                return matched("transition", "the unit list is mid-scroll")
            end
            return matched("unit_list_screen", "unit_list in its key handler")
        end,
    },
    {
        name = "prep_units",
        check = function(observation)
            if not proc(observation, "prep_units") then return rejected("prep_units proc absent") end
            if idleIs(observation, "prep_units", "prep_units_input") then
                return matched("prep_pick_units", "prep_units in its input loop")
            end
            return matched("transition", string.format("prep_units idle=%s, not prep_units_input",
                tostring(idleOf(observation, "prep_units"))))
        end,
    },
    {
        name = "prep_menu",
        check = function(observation)
            if not proc(observation, "prep_menu") then return rejected("prep_menu proc absent") end
            if not idleIs(observation, "prep_menu", "prep_menu_input") then
                return matched("transition", string.format("prep_menu idle=%s, not prep_menu_input",
                    tostring(idleOf(observation, "prep_menu"))))
            end
            if not observation.prep then
                return matched("transition", "prep_menu live with no observed prep structure")
            end
            if observation.prep.help_open then return matched("transition", "prep help window is open") end
            if proc(observation, "at_menu") then return matched("prep_main", "at_menu owns the prep list") end
            if proc(observation, "sally") then return matched("prep_map_menu", "sally owns the prep list") end
            return unsupported("preparations menu has no recognized owner")
        end,
    },
    {
        name = "simple_input",
        check = function(observation)
            -- Two rules watch save_menu (New Game vs the between-chapters prompt), so the
            -- same "absent" reason would otherwise be reported twice.
            local misses, seen = {}, {}
            for _, spec in ipairs(SIMPLE_INPUT_RULES) do
                if idleIs(observation, spec.proc, spec.idle) then
                    return matched(spec.rule, spec.proc .. " in " .. spec.idle)
                end
                local miss = missIs(observation, spec.proc, spec.idle)
                if not seen[miss] then
                    seen[miss] = true
                    misses[#misses + 1] = miss
                end
            end
            return rejected(table.concat(misses, "; "))
        end,
    },
    {
        name = "map_fade",
        check = function(observation)
            if proc(observation, "map_fade") then
                return matched("transition", "map_fade is animating")
            end
            return rejected("map_fade proc absent")
        end,
    },
    {
        name = "passive_proc",
        check = function(observation)
            local live = anyLive(observation, PASSIVE_PROCS)
            if live then return matched("transition", live, true) end
            return rejected("no passive proc live (" .. table.concat(PASSIVE_PROCS, ", ") .. ")")
        end,
    },
    {
        name = "player_phase",
        check = function(observation)
            if not proc(observation, "player_phase") then return rejected("player_phase proc absent") end
            if idleIs(observation, "player_phase", "player_main_idle") then
                return matched("player_map_idle", "player_phase in player_main_idle")
            end
            if idleIs(observation, "player_phase", "player_range_idle") then
                return matched("unit_selected", "player_phase in player_range_idle")
            end
            if idleIs(observation, "player_phase", "player_move_wait") then
                return matched("unit_moving", "player_phase in player_move_wait")
            end
            return matched("transition", string.format("player_phase idle=%s is not a known callback",
                tostring(idleOf(observation, "player_phase"))), true)
        end,
    },
    {
        name = "boot_proc",
        check = function(observation)
            local live = anyLive(observation, BOOT_PROCS)
            if live then return matched("transition", live, true) end
            return rejected("no boot-owner proc live")
        end,
    },
}

local function evaluate(observation)
    local considered = {}
    for _, rule in ipairs(RULES) do
        local verdict = rule.check(observation)
        if verdict.state then
            return verdict.state, nil, considered, rule.name, verdict.detail, verdict.unclassified
        end
        if verdict.error then
            return nil, verdict.error, considered, rule.name, nil, false
        end
        considered[#considered + 1] = { rule = rule.name, reason = verdict.reject }
    end
    return nil, "unsupported FE8 state", considered, nil, nil, false
end

function M.classify(observation)
    local state, why = evaluate(observation or {})
    return state, why
end

-- The same verdict, with the reasoning attached. Pure, so the emulator is never needed
-- to answer "why did this read as a transition" (#236).
function M.explain(observation)
    observation = observation or {}
    local state, why, considered, rule, detail, unclassified = evaluate(observation)
    local live = {}
    for name, p in pairs(observation.procs or {}) do
        live[#live + 1] = { name = name, idle = p.idle, addr = p.addr }
    end
    table.sort(live, function(a, b) return a.name < b.name end)
    return {
        state = state,
        error = why,
        matched = rule,
        detail = detail,
        considered = considered,
        live_procs = live,
        unclassified_wait = state == "transition" and unclassified or false,
    }
end

-- The liveness proxy behind the stall detector. Every long-running FE8 proc is
-- PROC_REPEAT -- ProcScr_StdEventEngine (event.c), gProcScr_TalkWaitForInput (scene.c),
-- sProcScr_BMXFADE (bmxfade.c), gProcScr_YesNoChoice (cgtext.c) -- so scrCur/idleCb/
-- lockCnt are constant for an ENTIRE scene and cannot show progress inside a callback.
-- What the signature can see is churn: a proc entering or leaving the pool, and a
-- sleepTime counting down (a timed wait IS progress, and excluding it made a proc mid-STAL
-- look frozen -- INSPECT.snapshot's own `frozen` field already compared it, so the feature
-- held two different definitions of "not moving"). #241.
function M.procSignature(observation)
    local raw = (observation or {}).raw_procs or {}
    local parts = { tostring(#raw) }
    for _, p in ipairs(raw) do
        parts[#parts + 1] = string.format("%d:%08X:%08X:%08X:%d:%d",
            p.slot, p.script, p.scr_cur, p.idle, p.lock, p.sleep or 0)
    end
    return table.concat(parts, ",")
end

-- A `transition` the classifier has no NAME for, holding a byte-identical proc pool, is
-- not a slow scene -- it is an input wait nothing will ever send. #232's ch01 burned a
-- 12000-iteration loop and then reported a timeout that named nothing.
--
-- Returns a per-loop closure: call it with each observation and its state, and act on the
-- first non-nil return (the explanation, ready to snapshot). Pure and unit-tested here;
-- the harness only wraps it with logging, because this is now the thing that decides FAIL
-- for a whole suite and it lived where nothing could test it (#241).
--
-- `samples` counts CALLS, not frames. The harness drives one call per frame on the
-- transition path, which is what makes TUNE.stallFrames read as frames -- add a wait to
-- that branch and the tunable stops meaning what it says.
function M.stallWatch(samples)
    local signature, held = nil, 0
    return function(observation, state)
        if state ~= "transition" then signature, held = nil, 0 return nil end
        local now = M.procSignature(observation)
        if now ~= signature then signature, held = now, 1 return nil end
        held = held + 1
        if held < samples then return nil end
        -- explain() sorts the live-proc list, so it is called ONCE per hold rather than on
        -- every frame of a 36000-iteration loop.
        local explanation = M.explain(observation)
        signature, held = nil, 0
        -- Only an UNCLASSIFIED transition can stall this way. A named one (a map fade, a
        -- menu animating in) is a state we can already wait out, and arming on those would
        -- trade a silent hang for a noisy false positive.
        if not explanation.unclassified_wait then return nil end
        return explanation
    end
end

local function add(actions, intention, key, source, target)
    actions[#actions + 1] = {
        intention = intention,
        key = key,
        source = source,
        target = target,
    }
end

local function prepEnabled(item)
    return item.effect ~= nil and ((item.color or 0) & 1) == 0
end

local function addMenuCommand(actions, observation, id, intention)
    for _, item in ipairs(enabledMenuItems(observation)) do
        if item.override_id == id then
            add(actions, intention, observation.menu.current == item.slot and "A" or nil,
                string.format("menu.override_id=0x%02X", id), item.slot)
        end
    end
end

local function addCursorActions(actions, cursor)
    if not cursor then return end
    if cursor.x and cursor.x > 0 then add(actions, "cursor_left", "LEFT", "map.bounds") end
    if cursor.y and cursor.y > 0 then add(actions, "cursor_up", "UP", "map.bounds") end
    if cursor.width and cursor.x and cursor.x + 1 < cursor.width then
        add(actions, "cursor_right", "RIGHT", "map.bounds")
    end
    if cursor.height and cursor.y and cursor.y + 1 < cursor.height then
        add(actions, "cursor_down", "DOWN", "map.bounds")
    end
end

local function addMenuNavigation(actions, observation)
    if observation.menu and #observation.menu.items > 1 then
        add(actions, "menu_previous", "UP", "menu.current")
        add(actions, "menu_next", "DOWN", "menu.current")
    end
    if observation.menu and observation.menu.on_b then
        add(actions, "cancel_menu", "B", "menu.on_b=" .. observation.menu.on_b)
    end
end

function M.legalActions(observation)
    local state, why = M.classify(observation)
    if not state then return nil, why end
    local actions = {}

    if state == "health_safety_wait" then
        add(actions, "continue", "A", "game_early_start.health_safety_wait")
    elseif state == "title_idle" then
        add(actions, "new_game", "START", "title.title_idle")
    elseif state == "save_menu_input" then
        add(actions, "new_game", "A", "save_menu.save_menu_input")
    elseif state == "save_slot_input" then
        add(actions, "select_save_slot", "A", "save_menu.save_slot_input")
    elseif state == "difficulty_input" then
        add(actions, "confirm_difficulty", "A", "difficulty.difficulty_input")
    elseif state == "chapter_intro_input" then
        add(actions, "continue_chapter_intro", "A", "chapter_intro.chapter_intro_input")
    elseif state == "dialogue_wait" then
        add(actions, "advance_dialogue", "A", "talk_wait.talk_wait_input")
    elseif state == "yes_no_choice" then
        -- A commits whatever is highlighted (YesNoChoice_Loop_KeyHandler, cgtext.c), so
        -- only the highlighted answer carries a key; the other is legal but must be
        -- selected first. Same contract as a menu command that needs navigating to.
        local current = observation.choice.current
        add(actions, "answer_yes", current == "yes" and "A" or nil, "choice.current")
        add(actions, "answer_no", current == "no" and "A" or nil, "choice.current")
        if current == "no" then add(actions, "select_yes", "LEFT", "choice.current=no") end
        if current == "yes" then add(actions, "select_no", "RIGHT", "choice.current=yes") end
        add(actions, "cancel_choice", "B", "yes_no.cancel")
    elseif state == "prep_main" then
        if observation.prep.on_start == "prep_main_fight" then
            add(actions, "fight", "START", "prep.on_start")
        end
        for _, item in ipairs(observation.prep.items or {}) do
            if prepEnabled(item) and item.index == 0 and item.effect == "prep_pick_units" then
                add(actions, "pick_units", observation.prep.current == item.slot and "A" or nil,
                    "prep.command.index=0", item.slot)
            end
        end
    elseif state == "unit_list_screen" then
        -- sub_809144C (unitlistscreen.c): DOWN/UP walk the roster, LEFT/RIGHT change page, A
        -- opens the highlighted unit's stat screen, B leaves. The roster index it moves is
        -- unk_30 -- NOT the on-screen row, which clamps while the list scrolls under it, so a
        -- driver that watched the row would stop believing it had reached the end of a list
        -- it was still halfway down.
        add(actions, "list_next", "DOWN", "unit_list.row")
        add(actions, "list_previous", "UP", "unit_list.row")
        add(actions, "select_list_entry", "A", "unit_list.row")
        add(actions, "close_list", "B", "unit_list.on_b")
    elseif state == "unit_command_menu" then
        addMenuNavigation(actions, observation)
        addMenuCommand(actions, observation, MENU_SEIZE, "seize")
        addMenuCommand(actions, observation, MENU_ATTACK, "attack")
        addMenuCommand(actions, observation, MENU_BALLISTA_ATTACK, "attack")
        addMenuCommand(actions, observation, MENU_TALK, "talk")
        addMenuCommand(actions, observation, MENU_VISIT, "visit")
        -- The map-interaction and inventory commands. Each of these used to be reached by
        -- pressing A on a row the scenario ASSUMED was top ("Door (row 0)"), which holds only
        -- while the command's neighbours happen to be unavailable -- give the unit a talkable
        -- ally or a chest on the same tile and the blind press fires the wrong command and
        -- the run stays green (#238).
        addMenuCommand(actions, observation, MENU_CHEST, "open_chest")
        addMenuCommand(actions, observation, MENU_DOOR, "open_door")
        addMenuCommand(actions, observation, MENU_ITEM, "open_items")
        addMenuCommand(actions, observation, MENU_SUPPLY, "open_supply")
        addMenuCommand(actions, observation, MENU_WAIT, "wait")
    elseif state == "map_command_menu" then
        addMenuNavigation(actions, observation)
        addMenuCommand(actions, observation, MENU_UNIT_LIST, "unit_list")
        addMenuCommand(actions, observation, MENU_STATUS, "status")
        addMenuCommand(actions, observation, MENU_END_PHASE, "end_phase")
    elseif state == "weapon_menu" then
        addMenuNavigation(actions, observation)
        for _, item in ipairs(enabledMenuItems(observation)) do
            if item.override_id >= MENU_WEAPON_FIRST and item.override_id <= MENU_WEAPON_LAST then
                add(actions, "select_weapon", observation.menu.current == item.slot and "A" or nil,
                    string.format("menu.override_id=0x%02X", item.override_id), item.slot)
            end
        end
    elseif state == "generic_menu" then
        addMenuNavigation(actions, observation)
        for _, item in ipairs(enabledMenuItems(observation)) do
            if observation.menu.current == item.slot then
                add(actions, "select_current_menu_item", "A",
                    "menu.on_selected=" .. item.on_selected, item.slot)
            end
        end
    elseif state == "target_selection" then
        add(actions, "confirm_target", "A", "target.currentTarget", observation.target.uid)
        -- B backs out of target selection to the command menu. Enumerating it is what
        -- lets a driver RECOVER from a selector it cannot commit instead of wedging
        -- there for the rest of the run (#232).
        add(actions, "cancel_target", "B", "target.selection")
    elseif state == "player_map_idle" then
        addCursorActions(actions, observation.cursor)
        if observation.cursor then
            if observation.cursor.unit_select_kind == "no_unit"
                or observation.cursor.unit_select_kind == "turn_ended" then
                add(actions, "open_map_menu", "A", "map.cursor.no_unit_or_turn_ended")
            elseif observation.cursor.unit_select_kind == "control" then
                add(actions, "select_unit", "A", "map.cursor.blue_unit")
            elseif observation.cursor.unit_select_kind == "no_control" then
                add(actions, "inspect_unit", "A", "map.cursor.no_control_unit")
            end
        end
    elseif state == "unit_selected" then
        addCursorActions(actions, observation.cursor)
        if observation.cursor and observation.cursor.reachable and observation.cursor.unit == 0 then
            add(actions, "confirm_move", "A", "movement.reachable_and_unoccupied")
        end
        add(actions, "cancel_selection", "B", "player_phase.range_idle")
    end

    return actions
end

function M.findAction(actions, intention)
    for _, candidate in ipairs(actions or {}) do
        if candidate.intention == intention then return candidate end
    end
    return nil
end

local function jsonString(value)
    return '"' .. tostring(value):gsub('[%z\1-\31\\"]', function(c)
        local escapes = { ['"'] = '\\"', ['\\'] = '\\\\', ['\b'] = '\\b', ['\f'] = '\\f',
            ['\n'] = '\\n', ['\r'] = '\\r', ['\t'] = '\\t' }
        return escapes[c] or string.format("\\u%04x", string.byte(c))
    end) .. '"'
end

local function jsonEncode(value)
    local kind = type(value)
    if kind == "nil" then return "null" end
    if kind == "boolean" or kind == "number" then return tostring(value) end
    if kind ~= "table" then return jsonString(value) end
    local count, array = 0, true
    for key in pairs(value) do
        count = count + 1
        if type(key) ~= "number" or key < 1 or key % 1 ~= 0 then array = false end
    end
    if array then
        for i = 1, count do if value[i] == nil then array = false break end end
    end
    local out = {}
    if array then
        for i = 1, count do out[#out + 1] = jsonEncode(value[i]) end
        return "[" .. table.concat(out, ",") .. "]"
    end
    local keys = {}
    for key in pairs(value) do keys[#keys + 1] = tostring(key) end
    table.sort(keys)
    for _, key in ipairs(keys) do out[#out + 1] = jsonString(key) .. ":" .. jsonEncode(value[key]) end
    return "{" .. table.concat(out, ",") .. "}"
end

-- Deterministic (sorted-key) JSON. The trace format and the #236 inspector snapshot are
-- the same wire format, so they share one encoder -- two would drift.
M.encode = jsonEncode

function M.formatTrace(record)
    return jsonEncode({
        event = "transition",
        state = record.state,
        legal = record.legal,
        action = record.intention,
        input = record.input,
        expected = record.expected,
        result = record.result,
        before = record.before,
        after = record.after,
    })
end

M.MENU_ATTACK = MENU_ATTACK
M.MENU_SEIZE = MENU_SEIZE
M.MENU_BALLISTA_ATTACK = MENU_BALLISTA_ATTACK
M.MENU_TALK = MENU_TALK
M.MENU_VISIT = MENU_VISIT
M.MENU_WAIT = MENU_WAIT
M.MENU_STATUS = MENU_STATUS
M.MENU_END_PHASE = MENU_END_PHASE

return M
