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
            or item.override_id == MENU_TALK or item.override_id == MENU_WAIT then unit = true end
        if item.override_id == MENU_END_PHASE then map = true end
    end
    return unit, map, weapon
end

function M.classify(observation)
    observation = observation or {}
    if observation.error then return nil, observation.error end

    if observation.world and observation.world.chapter == 0 and observation.world.turn == 0
        and next(observation.procs or {}) == nil then
        return "transition"
    end

    if idleIs(observation, "talk_wait", "talk_wait_input") then
        return "dialogue_wait"
    end

    if proc(observation, "target_selection") then
        if not idleIs(observation, "target_selection", "target_selection_input")
            or not observation.target or observation.target.frozen then
            return "transition"
        end
        if observation.target.kind ~= "attack" and observation.target.kind ~= "talk" then
            return nil, "unsupported target selection kind"
        end
        return "target_selection"
    end

    if proc(observation, "menu") then
        local menuProc = proc(observation, "menu")
        if not idleIs(observation, "menu", "menu_input") or menuProc.locked or menuProc.frozen
            or menuProc.ending or menuProc.doomed or not observation.menu then
            return "transition"
        end
        local unit, map, weapon = menuKinds(observation)
        if weapon and (unit or map) then return nil, "ambiguous standard menu mixes weapon and command items" end
        if unit and map then return nil, "ambiguous standard menu contains unit and map commands" end
        if weapon then return "weapon_menu" end
        if unit then return "unit_command_menu" end
        if map then return "map_command_menu" end
        local enabled = enabledMenuItems(observation)
        local callbacks = #enabled > 0
        for _, item in ipairs(enabled) do
            if not item.on_selected then callbacks = false break end
        end
        if callbacks then return "generic_menu" end
        return nil, "unsupported standard menu has no recognized semantic commands"
    end

    if proc(observation, "prep_units") then
        if idleIs(observation, "prep_units", "prep_units_input") then return "prep_pick_units" end
        return "transition"
    end

    if proc(observation, "prep_menu") then
        if not idleIs(observation, "prep_menu", "prep_menu_input") or not observation.prep then
            return "transition"
        end
        if observation.prep.help_open then return "transition" end
        if proc(observation, "at_menu") then return "prep_main" end
        if proc(observation, "sally") then return "prep_map_menu" end
        return nil, "preparations menu has no recognized owner"
    end

    if idleIs(observation, "game_early_start", "health_safety_wait") then
        return "health_safety_wait"
    end
    if idleIs(observation, "title", "title_idle") then return "title_idle" end
    if idleIs(observation, "save_menu", "save_menu_input") then return "save_menu_input" end
    if idleIs(observation, "save_menu", "save_slot_input") then return "save_slot_input" end
    if idleIs(observation, "difficulty", "difficulty_input") then return "difficulty_input" end
    if idleIs(observation, "chapter_intro", "chapter_intro_input") then return "chapter_intro_input" end

    if proc(observation, "map_fade") then return "transition" end

    for _, name in ipairs({ "talk_wait", "std_event", "battle_forecast", "battle" }) do
        if proc(observation, name) then return "transition" end
    end

    if proc(observation, "player_phase") then
        if idleIs(observation, "player_phase", "player_main_idle") then return "player_map_idle" end
        if idleIs(observation, "player_phase", "player_range_idle") then return "unit_selected" end
        if idleIs(observation, "player_phase", "player_move_wait") then return "unit_moving" end
        return "transition"
    end

    for _, name in ipairs({
        "game_control", "game_early_start", "title", "save_menu", "difficulty", "chapter_intro",
        "talk_wait", "std_event", "map_fade", "battle_forecast", "battle", "at_menu", "sally",
    }) do
        if proc(observation, name) then return "transition" end
    end

    return nil, "unsupported FE8 state"
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
    elseif state == "unit_command_menu" then
        addMenuNavigation(actions, observation)
        addMenuCommand(actions, observation, MENU_SEIZE, "seize")
        addMenuCommand(actions, observation, MENU_ATTACK, "attack")
        addMenuCommand(actions, observation, MENU_BALLISTA_ATTACK, "attack")
        addMenuCommand(actions, observation, MENU_TALK, "talk")
        addMenuCommand(actions, observation, MENU_VISIT, "visit")
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
