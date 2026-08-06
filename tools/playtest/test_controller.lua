-- Tests for controller.lua -- pure FE8 state classification + legal actions (no emulator).
-- Run: lua tools/playtest/test_controller.lua
local here = (arg[0]:match("(.*/)")) or "./"
local C = dofile(here .. "controller.lua")

local tests, fails = 0, 0
local function check(got, want, msg)
    tests = tests + 1
    if got ~= want then
        fails = fails + 1
        print(string.format("FAIL: %s\n  got  %s\n  want %s", msg, tostring(got), tostring(want)))
    end
end

local function proc(name, idle)
    return { [name] = { idle = idle } }
end

local function classify(observation, want, msg)
    local got, why = C.classify(observation)
    check(got, want, msg)
    if want ~= nil then check(why, nil, msg .. " has no rejection") end
end

local function action(observation, intention)
    local actions, why = C.legalActions(observation)
    if not actions then return nil, why end
    return C.findAction(actions, intention), why
end

-- Boot/input states are identified by the live proc script AND current idle callback.
classify({ procs = proc("game_early_start", "health_safety_wait") }, "health_safety_wait",
    "health/safety button wait")
classify({ procs = proc("title", "title_idle") }, "title_idle", "title idle")
classify({ procs = proc("save_menu", "save_menu_input") }, "save_menu_input", "save/New Game input")
classify({ procs = proc("save_menu", "save_slot_input") }, "save_slot_input", "New Game save-slot input")
classify({ procs = proc("difficulty", "difficulty_input") }, "difficulty_input", "difficulty input")
classify({ procs = proc("chapter_intro", "chapter_intro_input") }, "chapter_intro_input",
    "chapter intro input")

-- The same proc in a non-input callback is passive transition state, not permission to press.
classify({ procs = {}, world = { chapter = 0, turn = 0 } }, "transition",
    "empty proc pool before FE8 startup is an input-free transition")
check(action({ procs = {}, world = { chapter = 0, turn = 0 } }, "continue"), nil,
    "emulator startup exposes no input")
classify({ procs = proc("game_early_start", "health_safety_fade") }, "transition",
    "health/safety fade is passive")
classify({ procs = proc("game_control", "game_control_root") }, "transition",
    "root GameControl with no input child is a passive boot gap")
check(action({ procs = proc("game_early_start", "health_safety_fade") }, "continue"), nil,
    "passive transition exposes no continue input")

-- Dialogue A is legal only for the exact TalkWaitForInput proc/callback.
classify({ procs = proc("talk_wait", "talk_wait_input") }, "dialogue_wait", "dialogue input wait")
local a = action({ procs = proc("talk_wait", "talk_wait_input") }, "advance_dialogue")
check(a and a.key, "A", "dialogue wait exposes A")
check(action({ procs = proc("std_event", "event_engine") }, "advance_dialogue"), nil,
    "generic event proc does not expose dialogue A")
check(action({ procs = proc("save_menu", "save_slot_input") }, "select_save_slot").key, "A",
    "save slot is confirmed only at its exact input callback")

-- Preparations are read from the live ProcPrepMenu structure. Fight is the main-menu START
-- callback, not Check Map/B and not a row selected by name or position.
local prepMain = {
    procs = {
        at_menu = { idle = "at_menu_idle" },
        prep_menu = { idle = "prep_menu_input" },
    },
    prep = {
        current = 1,
        on_b = "prep_main_check_map",
        on_start = "prep_main_fight",
        items = {
            { slot = 0, index = 0, effect = "prep_pick_units", color = 0 },
            { slot = 1, index = 1, effect = "prep_items", color = 0 },
            { slot = 2, index = 7, effect = "prep_check_map", color = 0 },
        },
    },
}
classify(prepMain, "prep_main", "preparations main menu")
a = action(prepMain, "fight")
check(a and a.key, "START", "Fight uses live main-menu START callback")
check(a and a.source, "prep.on_start", "Fight records semantic callback source")
a = action(prepMain, "pick_units")
check(a and a.target, 0, "Pick Units comes from live prep command index")
check(action(prepMain, "check_map"), nil, "Check Map is not a controller exit action")
local prepHelp = {
    procs = prepMain.procs,
    prep = {
        current = prepMain.prep.current, items = prepMain.prep.items,
        on_b = prepMain.prep.on_b, on_start = prepMain.prep.on_start,
        help_open = true,
    },
}
classify(prepHelp, "transition", "preparations help mode is passive")
check(action(prepHelp, "fight"), nil, "preparations help mode exposes no Fight input")

local prepView = {
    procs = {
        sally = { idle = "sally_idle" },
        prep_menu = { idle = "prep_menu_input" },
    },
    prep = {
        current = 0,
        on_b = "prep_map_back",
        on_start = "prep_map_fight",
        items = {
            { slot = 0, index = 1, effect = "prep_view_map", color = 0 },
            { slot = 1, index = 2, effect = "prep_formation", color = 0 },
        },
    },
}
classify(prepView, "prep_map_menu", "View Map preparations menu is distinct")
check(action(prepView, "fight"), nil, "controller never exits prep through View Map")
classify({ procs = proc("prep_units", "prep_units_input") }, "prep_pick_units", "Pick Units screen")

-- Standard menus expose semantic command IDs and enabled availability, never guessed rows.
local unitMenu = {
    procs = proc("menu", "menu_input"),
    menu = {
        current = 1,
        on_b = "0x0804F000",
        items = {
            { slot = 3, override_id = 0x4F, availability = 1 },
            { slot = 4, override_id = 0x4E, availability = 1 },
            { slot = 0, override_id = 0x5A, availability = 1 },
            { slot = 1, override_id = 0x6B, availability = 1 },
            { slot = 2, override_id = 0x5C, availability = 1 },
        },
    },
}
classify(unitMenu, "unit_command_menu", "unit command menu")
a = action(unitMenu, "talk")
check(a and a.target, 0, "Talk resolves from semantic id 0x5A")
a = action(unitMenu, "wait")
check(a and a.target, 1, "Wait resolves from semantic id 0x6B")
a = action(unitMenu, "visit")
check(a and a.target, 2, "Visit resolves from semantic id 0x5C")
a = action(unitMenu, "attack")
check(a and a.target, 3, "Attack resolves from semantic id 0x4F")
a = action(unitMenu, "seize")
check(a and a.target, 4, "Seize resolves from semantic id 0x4E")
a = action(unitMenu, "cancel_menu")
check(a and a.key, "B", "standard menu cancellation comes from its live B callback")
check(a and a.source, "menu.on_b=0x0804F000", "menu cancel records the live callback")

local lockedMenu = {
    procs = { menu = { idle = "menu_input", locked = true, frozen = false } },
    menu = unitMenu.menu,
}
classify(lockedMenu, "transition", "locked standard menu is passive")
check(action(lockedMenu, "wait"), nil, "locked standard menu exposes no command input")
local frozenMenu = {
    procs = { menu = { idle = "menu_input", locked = false, frozen = true } },
    menu = unitMenu.menu,
}
classify(frozenMenu, "transition", "frozen standard menu is passive")
check(action(frozenMenu, "wait"), nil, "frozen standard menu exposes no command input")
local endingMenu = {
    procs = { menu = { idle = "menu_input", locked = false, frozen = false, ending = true } },
    menu = unitMenu.menu,
}
classify(endingMenu, "transition", "ending standard menu is passive")
check(action(endingMenu, "wait"), nil, "ending standard menu exposes no command input")
local doomedMenu = {
    procs = { menu = { idle = "menu_input", locked = false, frozen = false, doomed = true } },
    menu = unitMenu.menu,
}
classify(doomedMenu, "transition", "doomed standard menu is passive")
check(action(doomedMenu, "wait"), nil, "doomed standard menu exposes no command input")

local disabledTalk = {
    procs = proc("menu", "menu_input"),
    menu = { current = 0, items = { { slot = 0, override_id = 0x5A, availability = 2 } } },
}
check(action(disabledTalk, "talk"), nil, "disabled Talk is not legal")

local callbackMenu = {
    procs = proc("menu", "menu_input"),
    menu = { current = 1, items = {
        { slot = 0, override_id = 0, availability = 1, on_selected = "0x08123456" },
        { slot = 1, override_id = 1, availability = 1, on_selected = "0x08123456" },
    } },
}
classify(callbackMenu, "generic_menu", "unknown standard menu is supported through live callbacks")
a = action(callbackMenu, "select_current_menu_item")
check(a and a.key, "A", "generic menu exposes only its current live callback")
check(a and a.target, 1, "generic selection records the current item slot")
check(a and a.source, "menu.on_selected=0x08123456", "generic selection records callback identity")
local callbacklessMenu = {
    procs = proc("menu", "menu_input"),
    menu = { current = 0, items = { { slot = 0, override_id = 0, availability = 1 } } },
}
local callbacklessState = C.classify(callbacklessMenu)
check(callbacklessState, nil, "callbackless unknown menu still fails closed")
classify({ procs = proc("menu", "menu_input") }, "transition",
    "menu Proc without an actionable live item snapshot is passive")

local mapMenu = {
    procs = proc("menu", "menu_input"),
    menu = {
        current = 0,
        items = {
            { slot = 0, override_id = 0x6F, availability = 1 },
            { slot = 4, override_id = 0x78, availability = 1 },
        },
    },
}
classify(mapMenu, "map_command_menu", "map command menu")
a = action(mapMenu, "end_phase")
check(a and a.target, 4, "End Phase resolves from semantic id 0x78")
a = action(mapMenu, "status")
check(a and a.target, 0, "Status resolves from semantic id 0x6F")

-- Attack sub-states remain semantic: live weapon items and the live SelectTargetProc.
local weaponMenu = {
    procs = proc("menu", "menu_input"),
    menu = {
        current = 1,
        items = {
            { slot = 0, override_id = 0x49, availability = 2 },
            { slot = 1, override_id = 0x4A, availability = 1 },
        },
    },
}
classify(weaponMenu, "weapon_menu", "weapon menu is identified by its semantic slot ids")
a = action(weaponMenu, "select_weapon")
check(a and a.key, "A", "selected enabled weapon is confirmable")
check(a and a.target, 1, "weapon selection records the live item slot")

local attackTarget = {
    procs = proc("target_selection", "target_selection_input"),
    target = { kind = "attack", x = 7, y = 5, uid = 0x81, frozen = false },
}
classify(attackTarget, "target_selection", "live attack target selector")
a = action(attackTarget, "confirm_target")
check(a and a.key, "A", "live unfrozen target can be confirmed")
check(a and a.target, 0x81, "target confirmation records the live unit id")
-- #232: a selector we cannot commit must be escapable, or a driver wedges in it for the
-- rest of the run. B backs out to the command menu; enumerating it is what makes the
-- recovery a legal observed action rather than a guessed key.
a = action(attackTarget, "cancel_target")
check(a and a.key, "B", "a live target selector can be backed out of")

local frozenTarget = {
    procs = proc("target_selection", "target_selection_input"),
    target = { kind = "talk", x = 7, y = 5, uid = 0x41, frozen = true },
}
classify(frozenTarget, "transition", "frozen target selector is passive")
check(action(frozenTarget, "confirm_target"), nil, "frozen target exposes no input")
check(action(frozenTarget, "cancel_target"), nil, "a frozen selector exposes no escape either")

-- The battle forecast is display-only. TargetSelection_Loop owns confirmation; the
-- forecast's callbacks must be observed as passive transitions and never expose a
-- guessed second A press.
classify({ procs = proc("battle_forecast", "battle_forecast_display") }, "transition",
    "battle forecast display is passive")
check(action({ procs = proc("battle_forecast", "battle_forecast_display") }, "confirm_target"), nil,
    "battle forecast exposes no duplicate target confirmation")

-- PlayerPhase's live callback distinguishes idle map, range selection, and movement.
classify({ procs = proc("player_phase", "player_main_idle") }, "player_map_idle", "player map idle")
classify({ procs = proc("player_phase", "player_range_idle") }, "unit_selected", "unit selected")
classify({ procs = proc("player_phase", "player_move_wait") }, "unit_moving", "unit movement")
classify({ procs = {
    player_phase = { idle = "player_main_idle" },
    map_fade = { idle = "map_fade" },
} }, "transition", "map fade suppresses otherwise-idle player input")
classify({ procs = {
    player_phase = { idle = "player_main_idle" },
    std_event = { idle = "event_engine" },
} }, "transition", "event engine suppresses otherwise-idle player input")
check(action({ procs = {
    player_phase = { idle = "player_main_idle" },
    map_fade = { idle = "map_fade" },
}, cursor = { unit = 1, unit_faction = "blue", unit_selectable = true } }, "select_unit"), nil,
    "map fade exposes no unit selection")
local emptyMap = {
    procs = proc("player_phase", "player_main_idle"),
    cursor = { x = 3, y = 4, unit = 0, unit_select_kind = "no_unit", width = 10, height = 8 },
}
check(action(emptyMap, "open_map_menu").key, "A", "A on a live empty tile opens the map menu")
check(action(emptyMap, "cursor_left").key, "LEFT", "map cursor can move left inside bounds")
check(action(emptyMap, "cursor_up").key, "UP", "map cursor can move up inside bounds")
local unitMap = {
    procs = proc("player_phase", "player_main_idle"),
    cursor = { x = 0, y = 0, unit = 1, unit_faction = "blue", unit_select_kind = "control",
        width = 10, height = 8 },
}
check(action(unitMap, "select_unit").key, "A", "A selects a live blue unit")
check(action(unitMap, "open_map_menu"), nil, "occupied tile does not expose map-menu A")
check(action(unitMap, "cursor_left"), nil, "cursor cannot move left past map edge")
local exhaustedUnitMap = {
    procs = proc("player_phase", "player_main_idle"),
    cursor = { x = 2, y = 2, unit = 3, unit_faction = "blue", unit_select_kind = "turn_ended",
        width = 10, height = 8 },
}
check(action(exhaustedUnitMap, "select_unit"), nil, "exhausted blue unit is not selectable")
check(action(exhaustedUnitMap, "open_map_menu").key, "A",
    "A on an exhausted blue unit follows FE8 and opens the map menu")
local noControlUnitMap = {
    procs = proc("player_phase", "player_main_idle"),
    cursor = { x = 2, y = 2, unit = 0x81, unit_faction = "red", unit_select_kind = "no_control",
        width = 10, height = 8 },
}
check(action(noControlUnitMap, "inspect_unit").key, "A",
    "A on a no-control unit exposes FE8's inspection action")
local selected = {
    procs = proc("player_phase", "player_range_idle"),
    cursor = { x = 2, y = 2, unit = 0, width = 10, height = 8, reachable = true },
}
check(action(selected, "confirm_move").key, "A", "reachable selected tile exposes move confirm")
check(action(selected, "cancel_selection").key, "B", "selected unit exposes cancel")
local selectedOccupied = {
    procs = proc("player_phase", "player_range_idle"),
    cursor = { x = 2, y = 2, unit = 0x41, width = 10, height = 8, reachable = true },
}
check(action(selectedOccupied, "confirm_move"), nil,
    "reachable-looking occupied tile does not expose move confirm")

-- When a semantic command is not selected yet, navigation itself is an enumerated legal action.
a = action(unitMenu, "talk")
check(a.key, nil, "off-cursor semantic command cannot be confirmed yet")
check(action(unitMenu, "menu_previous").key, "UP", "unit menu exposes guarded previous-row input")
check(action(unitMenu, "menu_next").key, "DOWN", "unit menu exposes guarded next-row input")

-- Known battle/event activity is passive. Ambiguous menus and unknown snapshots fail closed.
classify({ procs = proc("battle", "battle_loop") }, "transition", "battle transition")
local mixedMenu = {
    procs = proc("menu", "menu_input"),
    menu = { current = 0, items = {
        { slot = 0, override_id = 0x6B, availability = 1 },
        { slot = 1, override_id = 0x78, availability = 1 },
    } },
}
local got, why = C.classify(mixedMenu)
check(got, nil, "ambiguous unit/map menu fails closed")
check(type(why) == "string", true, "ambiguous menu explains rejection")
got, why = C.classify({ procs = {} })
check(got, nil, "unknown snapshot fails closed")
check(type(why) == "string", true, "unknown snapshot explains rejection")
got, why = C.classify({ error = "malformed live menu", procs = proc("menu", "menu_input") })
check(got, nil, "malformed observation fails closed")
check(why, "malformed live menu", "observer rejection is preserved")

-- Trace lines are structured and carry the full state/action/postcondition transition.
local trace = C.formatTrace({
    state = "unit_command_menu",
    legal = { "talk", "wait" },
    intention = "wait",
    input = "A",
    expected = "player_map_idle",
    result = "pass",
    before = { state = "unit_command_menu", menu = { current = 1 } },
    after = { state = "player_map_idle", cursor = { x = 2, y = 3 } },
})
for _, field in ipairs({ '"event":"transition"', '"state":"unit_command_menu"',
                         '"legal":["talk","wait"]', '"action":"wait"', '"input":"A"',
                         '"expected":"player_map_idle"', '"result":"pass"',
                         '"before":{', '"after":{' }) do
    check(trace:find(field, 1, true) ~= nil, true, "trace includes " .. field)
end

if fails > 0 then
    print(string.format("\n%d/%d FAILED", fails, tests))
    os.exit(1)
else
    print(string.format("ok -- %d assertions", tests))
end
