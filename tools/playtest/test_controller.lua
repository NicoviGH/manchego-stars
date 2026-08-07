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
-- The Pick Units deploy screen. Its legal moves are exactly the bounds ProcPrepUnit_Idle
-- enforces on a TWO-COLUMN list (prep_unitselect.c): LEFT only from an odd index, RIGHT only
-- from an even one that is not the last, and UP/DOWN by two. A scenario that pressed RIGHT or
-- DOWN off the end of that grid moved nothing and then acted on whoever it was still sitting
-- on -- which is how a bench/deploy walk can pick the wrong unit and stay green (#238).
local pickUnits = {
    procs = proc("prep_units", "prep_units_input"),
    prep_units = { cursor = 0, settled = true, deployed = 1, count = 8 },
}
classify(pickUnits, "prep_pick_units", "Pick Units screen")
a = action(pickUnits, "pick_right")
check(a and a.key, "RIGHT", "an even index can cross to the second column")
check(action(pickUnits, "pick_left"), nil, "...but the first column has nothing to its left")
check(action(pickUnits, "pick_previous"), nil, "and the top row has nothing above it")
a = action(pickUnits, "pick_next")
check(a and a.key, "DOWN", "the row below is two indices on")
a = action(pickUnits, "toggle_deploy")
check(a and a.key, "A", "A benches or deploys whoever the cursor holds")
a = action(pickUnits, "fight")
check(a and a.key, "START", "START launches once at least one unit is deployed")

local lastPick = {
    procs = proc("prep_units", "prep_units_input"),
    prep_units = { cursor = 7, settled = true, deployed = 4, count = 8 },
}
check(action(lastPick, "pick_right"), nil, "the last entry has nothing to its right")
check(action(lastPick, "pick_next"), nil, "...and nothing below it")
a = action(lastPick, "pick_left")
check(a and a.key, "LEFT", "but an odd index can always step back a column")

local emptyPick = {
    procs = proc("prep_units", "prep_units_input"),
    prep_units = { cursor = 0, settled = true, deployed = 0, count = 8 },
}
check(action(emptyPick, "fight"), nil, "START does not launch with an empty field")

-- The whole key handler is gated on list_num_pre == list_num_cur: while the list scrolls to a
-- new row FE8 reads no keys at all, so a press sent then is lost outright.
local scrollingPick = {
    procs = proc("prep_units", "prep_units_input"),
    prep_units = { cursor = 4, settled = false, deployed = 2, count = 8 },
}
classify(scrollingPick, "transition", "a scrolling deploy list takes no input")
check(action(scrollingPick, "toggle_deploy"), nil, "and offers none")

-- The in-map convoy, opened by the unit menu's Supply command. Only ever entered to look and
-- leave, so B is the whole contract -- but it has to be a NAMED state, because two blind B's
-- into an unclassified screen cannot tell "the convoy closed" from "the second B also
-- cancelled the unit's move".
local supply = {
    procs = { supply_screen = { idle = "supply_input" }, player_phase = { idle = "player_main_idle" } },
}
classify(supply, "supply_screen", "the map convoy outranks the map underneath it")
a = action(supply, "close_supply")
check(a and a.key, "B", "B leaves the convoy (PrepItemSupply_Loop_GiveTakeKeyHandler)")
check(action(supply, "cursor_down"), nil, "and the map cursor is not offered while it is up")

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

-- The rest of gUnitActionMenuItems that our scenarios actually drive (menu_def.c). Each was
-- being reached by pressing A on an assumed ROW -- "Door (row 0)", "Chest (row 0)", "Item
-- (row 0, no weapon)" -- which is only true while the command's neighbours happen to be
-- unavailable. Naming them makes the row an observation instead of an assumption (#238).
local fieldMenu = {
    procs = proc("menu", "menu_input"),
    menu = {
        current = 0,
        items = {
            { slot = 0, override_id = 0x5D, availability = 1 },  -- Chest
            { slot = 1, override_id = 0x5E, availability = 1 },  -- Door
            { slot = 2, override_id = 0x67, availability = 1 },  -- Item
            { slot = 3, override_id = 0x69, availability = 1 },  -- Supply
            { slot = 4, override_id = 0x6B, availability = 1 },  -- Wait
        },
    },
}
classify(fieldMenu, "unit_command_menu", "Chest/Door/Item/Supply are unit commands")
a = action(fieldMenu, "open_chest")
check(a and a.target, 0, "Chest resolves from semantic id 0x5D")
check(a and a.key, "A", "the highlighted command carries its key")
a = action(fieldMenu, "open_door")
check(a and a.target, 1, "Door resolves from semantic id 0x5E")
check(a and a.key, nil, "a command that is not highlighted must be selected first")
a = action(fieldMenu, "open_items")
check(a and a.target, 2, "Item resolves from semantic id 0x67")
a = action(fieldMenu, "open_supply")
check(a and a.target, 3, "Supply resolves from semantic id 0x69")

-- Availability is read, never assumed. This pins a DELIBERATELY conservative choice rather
-- than an engine behaviour: addMenuCommand filters on enabledMenuItems, so a MENU_DISABLED row
-- is never offered as a command -- even though Menu_OnIdle would in fact fire its onSelected
-- (it never consults availability; see the inventory list below, which relies on exactly that).
-- No unit command actually greys today: DoorCommandUsability and its neighbours return only
-- MENU_ENABLED or MENU_NOTSHOWN, and a NOTSHOWN row is not built at all (uimenu.c). So this
-- guards the day one of them starts greying, and the fixture is synthetic on purpose.
local shutMenu = {
    procs = proc("menu", "menu_input"),
    menu = {
        current = 0,
        items = {
            { slot = 0, override_id = 0x5E, availability = 2 },  -- Door, greyed out
            { slot = 1, override_id = 0x6B, availability = 1 },
        },
    },
}
check(action(shutMenu, "open_door"), nil, "a disabled Door is not a legal action")

-- The inventory list a unit's Item command opens (gItemSelectMenuItems, override 0x43-0x47).
-- It needs its own state because MENU_DISABLED means something different here than it does
-- on a command menu: ItemSelectMenu_Usability greys any item the unit cannot USE -- a weapon,
-- a healing item at full HP -- but Menu_OnIdle's A path calls onSelected WITHOUT consulting
-- availability, and ItemSelectMenu_Effect opens the Use/Equip/Trade/Discard submenu
-- unconditionally. A greyed row is still a live row. Reading it as a command menu instead
-- reported "unsupported standard menu has no recognized semantic commands" the moment every
-- item happened to be unusable, which is Hlin's whole inventory at ch00 turn 1 (#238).
local itemList = {
    procs = proc("menu", "menu_input"),
    menu = {
        current = 1,
        on_b = "0x0802291C",
        items = {
            { slot = 0, override_id = 0x43, availability = 2, on_selected = "0x080234E4" },
            { slot = 1, override_id = 0x44, availability = 2, on_selected = "0x080234E4" },
        },
    },
}
classify(itemList, "item_list", "an inventory of unusable items is still an inventory")
a = action(itemList, "select_item")
check(a and a.target, 1, "the inventory commits the HIGHLIGHTED row, never an assumed one")
check(a and a.key, "A", "a greyed row is selectable -- grey means unusable, not unreachable")
check(action(itemList, "menu_next") ~= nil, true, "and the list can be walked to another row")
a = action(itemList, "cancel_menu")
check(a and a.key, "B", "B backs out of the inventory")

-- FE8's "your inventory is full -- which item goes to the convoy" chooser
-- (gSendToConvoyMenuItems, override 0x2A-0x2F; raised by ConvoyMenuProc_StarMenu whenever a
-- unit is handed an item with no free slot). It is a MenuProc with no semantic command on it,
-- so it fell through to generic_menu -- and a driver waiting for a scene to finish would sit
-- behind it forever, because nothing advances until it is answered. The ch02 ending's third
-- charm-gift raises exactly this, which is why clear_ch02's blind A-mash was load-bearing:
-- the run's "3/3 charms delivered" verdict depended on a stray press resolving a prompt the
-- scenario never knew was there (#238).
local sendToConvoy = {
    procs = { menu = { idle = "menu_input" }, std_event = { idle = "event_engine" } },
    menu = {
        current = 0,
        items = {
            { slot = 0, override_id = 0x2A, availability = 1, on_selected = "0x08022BEC" },
            { slot = 1, override_id = 0x2B, availability = 1, on_selected = "0x08022BEC" },
            { slot = 5, override_id = 0x2F, availability = 1, on_selected = "0x08022C40" },
        },
    },
}
classify(sendToConvoy, "send_to_convoy", "the inventory-full convoy chooser is its own state")

-- ConvoyMenuProc_StarMenu has TWO arms off one call site: gSendToConvoyMenuItems (0x2A-0x2F)
-- when the convoy has room, gConvoyMenuItems (0x24-0x29) when it is FULL. Both block the same
-- way, so classifying only the first leaves the identical hang one branch over -- and it would
-- not even trip the stall watch, which arms on UNCLASSIFIED transitions and this would read as
-- a tidy generic_menu.
local convoyFull = {
    procs = { menu = { idle = "menu_input" }, std_event = { idle = "event_engine" } },
    menu = {
        current = 0,
        items = {
            { slot = 0, override_id = 0x24, availability = 1, on_selected = "0x08022B00" },
            { slot = 5, override_id = 0x29, availability = 1, on_selected = "0x08022B40" },
        },
    },
}
classify(convoyFull, "send_to_convoy", "...and so is the convoy-FULL arm of the same call site")
a = action(convoyFull, "send_item")
check(a and a.key, "A", "which blocks the chapter identically and so is answered identically")
a = action(sendToConvoy, "send_item")
check(a and a.key, "A", "A sends the highlighted item to the convoy")
check(a and a.target, 0, "...the HIGHLIGHTED one, not an assumed row")
check(action(sendToConvoy, "menu_next") ~= nil, true, "and another slot can be chosen first")

local usableItems = {
    procs = proc("menu", "menu_input"),
    menu = {
        current = 0,
        items = { { slot = 0, override_id = 0x43, availability = 1, on_selected = "0x080234E4" } },
    },
}
classify(usableItems, "item_list", "...and so is an inventory of usable ones")

-- The map-menu Character screen (ProcScr_UnitListScreen_Field). It is not a MenuProc at all
-- -- it owns the whole screen and runs its own key handler -- so before it was named, a
-- scenario walking the roster pressed DOWN into a state the controller could not see, and
-- the player_phase rule underneath was calling the same frames `player_map_idle` (#238).
local unitList = {
    procs = { player_phase = { idle = "player_main_idle" },
              unit_list = { idle = "unit_list_input" } },
    unit_list = { row = 0, screen_row = 0, page = 0, count = 9, scrolling = false },
}
classify(unitList, "unit_list_screen", "the Character screen outranks the map underneath it")
check(action(unitList, "list_next") ~= nil, true, "the roster can be walked forward")
check(action(unitList, "cursor_down"), nil, "and the map cursor is NOT offered while it is up")
a = action(unitList, "close_list")
check(a and a.key, "B", "B leaves the Character screen (sub_809144C)")

-- The walk is bounded at BOTH ends, from the same field sub_809144C bounds against. UP at
-- row 0 is not a no-op: it sets unk_29 = 3, which routes sub_8091AEC into sub_80917D8, the
-- sort-column mode -- a persistent input state the observer reports as `scrolling`, i.e. as a
-- transition offering nothing. Advertising UP there hands the driver an action that walks it
-- into a screen it has no enumerated way out of, and it burns its budget until the stall
-- watch fires on a wait the controller itself caused.
check(action(unitList, "list_previous"), nil, "UP at row 0 is NOT offered -- it opens sort mode")
local midList = {
    procs = { unit_list = { idle = "unit_list_input" } },
    unit_list = { row = 4, screen_row = 4, page = 0, count = 9, scrolling = false },
}
a = action(midList, "list_previous")
check(a and a.key, "UP", "...but it is offered anywhere the row can actually move up")
local lastList = {
    procs = { unit_list = { idle = "unit_list_input" } },
    unit_list = { row = 8, screen_row = 5, page = 0, count = 9, scrolling = false },
}
check(action(lastList, "list_next"), nil,
    "and DOWN is not offered on the last entry (unk_30 < count-1 is the engine's own bound)")

-- unk_29 != 0 is the page/row scroll animating, and its key handler does not run then. FE8
-- DROPS input in that window, so calling it an input state is how a press goes missing.
local scrollingList = {
    procs = { unit_list = { idle = "unit_list_input" } },
    unit_list = { row = 3, screen_row = 1, page = 0, count = 9, scrolling = true },
}
classify(scrollingList, "transition", "a scrolling Character screen takes no input")
check(action(scrollingList, "list_next"), nil, "and offers none")

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

-- Yes/No choice (cgtext.c gProcScr_YesNoChoice). The lord-select prompt "Will Braulo lead
-- the party?" rides this, and nothing classified it -- so ch01 parked on it for the whole
-- of #232 while the event engine stayed live and read as a passive transition (#236 found
-- it by name). currentChoice is TALK_CHOICE_YES/NO; A commits whichever is highlighted.
local yesHighlighted = {
    procs = proc("yes_no", "yes_no_input"),
    choice = { current = "yes" },
}
classify(yesHighlighted, "yes_no_choice", "yes/no prompt in its key handler")
local yes = action(yesHighlighted, "answer_yes")
check(yes and yes.key, "A", "A commits the highlighted Yes")
local no = action(yesHighlighted, "answer_no")
check(no ~= nil, true, "No is legal, but not by pressing A")
check(no and no.key, nil, "No must be selected before it can be committed")
check(action(yesHighlighted, "select_no").key, "RIGHT", "RIGHT moves the choice to No")
check(action(yesHighlighted, "cancel_choice").key, "B", "B cancels the prompt")

local noHighlighted = {
    procs = proc("yes_no", "yes_no_input"),
    choice = { current = "no" },
}
check(action(noHighlighted, "answer_no").key, "A", "A commits the highlighted No")
check(action(noHighlighted, "answer_yes").key, nil, "Yes is not committable while No is up")
check(action(noHighlighted, "select_yes").key, "LEFT", "LEFT moves the choice back to Yes")

-- The prompt animating in offers nothing, and says so by name.
classify({ procs = proc("yes_no", "yes_no_fade"), choice = { current = "yes" } }, "transition",
    "a yes/no prompt outside its key handler is passive")
check(action({ procs = proc("yes_no", "yes_no_fade") }, "answer_yes"), nil,
    "a passive yes/no prompt exposes no answer")

-- A live event engine must not mask the prompt: the yes/no rule is evaluated first.
classify({
    procs = { std_event = { idle = "event_engine" }, yes_no = { idle = "yes_no_input" } },
    choice = { current = "yes" },
}, "yes_no_choice", "the yes/no prompt outranks the passive event engine")

-- RULE ORDER IS THE LOAD-BEARING PROPERTY of the table, and only one pairing was pinned.
-- The dangerous one is talk_wait + yes_no: `dialogue_wait` says "press A", the choice
-- handler CONSUMES that A, and the prompt is answered by accident with the run green --
-- exactly #232, restored silently. The specific state outranks the general one.
classify({
    procs = { talk_wait = { idle = "talk_wait_input" }, yes_no = { idle = "yes_no_input" } },
    choice = { current = "yes" },
}, "yes_no_choice", "the yes/no prompt outranks a waiting text box")
check(action({
    procs = { talk_wait = { idle = "talk_wait_input" }, yes_no = { idle = "yes_no_input" } },
    choice = { current = "yes" },
}, "advance_dialogue"), nil, "a live choice withdraws the blind dialogue A")

classify({
    procs = { std_event = { idle = "event_engine" }, menu = { idle = "menu_input" } },
    menu = { current = 0, items = {
        { slot = 0, override_id = 0x7F, availability = 1, on_selected = 0x0800B1C0 } } },
}, "generic_menu", "an open menu outranks the passive event engine")

classify({
    procs = { std_event = { idle = "event_engine" }, map_fade = { idle = "map_fade_loop" } },
}, "transition", "map_fade and std_event agree it is a transition")
check(C.explain({
    procs = { std_event = { idle = "event_engine" }, map_fade = { idle = "map_fade_loop" } },
}).matched, "map_fade", "the named fade owns the transition, not the catch-all passive rule")

-- explain(): the same verdict, plus WHY. Every #232 defect but one was an input wait
-- nothing had a name for; each read as a passive `transition` and cost a full
-- build-and-run cycle to identify. An unclassified wait has to say what it rejected.
local function reasonFor(explanation, rule)
    for _, entry in ipairs(explanation.considered) do
        if entry.rule == rule then return entry.reason end
    end
    return nil
end

local dialogue = C.explain({ procs = proc("talk_wait", "talk_wait_input") })
check(dialogue.state, "dialogue_wait", "explain agrees with classify on a match")
check(dialogue.matched, "dialogue_wait", "explain names the rule that matched")
check(dialogue.error, nil, "a matched explanation carries no error")

-- The ch01 acceptance case: a live event engine and nothing else, which classify calls
-- `transition`. The explanation must name the proc that made it one, and show that the
-- dialogue-wait rule was considered and why it was rejected.
local scene = C.explain({
    procs = { std_event = { idle = "event_engine", addr = 0x02024F00 } },
    world = { chapter = 2, turn = 0, faction = 0 },
})
check(scene.state, "transition", "a live event engine still classifies as transition")
check(scene.matched, "passive_proc", "explain names which rule produced the transition")
check(scene.detail:find("std_event", 1, true) ~= nil, true,
    "the transition detail names the live proc responsible")
check(reasonFor(scene, "dialogue_wait"):find("talk_wait", 1, true) ~= nil, true,
    "dialogue_wait rejection names the proc it looked for")
check(reasonFor(scene, "menu"):find("absent", 1, true) ~= nil, true,
    "menu rejection says the proc is absent")
check(scene.unclassified_wait, true,
    "a transition with no live input proc is flagged as an unclassified wait")
check(#scene.live_procs, 1, "explain lists the live procs it saw")
check(scene.live_procs[1].name, "std_event", "live proc entries carry their name")
check(scene.live_procs[1].idle, "event_engine", "live proc entries carry their idle callback")

-- A proc that IS live but in the wrong callback must say so -- "absent" and "present but
-- not in its input callback" are different bugs and cost different fixes.
local fadingMenu = C.explain({ procs = proc("menu", "menu_fade_in"), menu = { current = 0, items = {} } })
check(fadingMenu.state, "transition", "a menu outside its input callback is a transition")
check(fadingMenu.matched, "menu", "the menu rule owns that transition")
check(fadingMenu.detail:find("menu_fade_in", 1, true) ~= nil, true,
    "the detail names the callback the menu is actually sitting in")
check(fadingMenu.unclassified_wait, false,
    "a transition a rule explained is not an unclassified wait")

-- A hard error explains itself the same way classify does.
local broken = C.explain({ error = "malformed live menu", procs = proc("menu", "menu_input") })
check(broken.state, nil, "explain fails closed on a malformed observation")
check(broken.error, "malformed live menu", "explain preserves the observer rejection")

-- The other two rules that flag an unclassified wait. Both feed the stall detector, and
-- only passive_proc was covered -- so a change that stopped flagging either would have
-- disarmed the failure oracle on those states silently (#241).
local bootGap = C.explain({ procs = proc("game_control", "game_control_root") })
check(bootGap.matched, "boot_proc", "an unnamed boot owner is the boot_proc rule's transition")
check(bootGap.unclassified_wait, true, "and it is flagged as an unclassified wait")

local strangePhase = C.explain({ procs = proc("player_phase", "player_unknown_idle") })
check(strangePhase.matched, "player_phase", "an unknown player_phase callback stays with its rule")
check(strangePhase.unclassified_wait, true, "and is flagged -- it is a wait with no name yet")
check(strangePhase.detail:find("player_unknown_idle", 1, true) ~= nil, true,
    "the detail names the callback nobody has classified")

-- ---------------------------------------------------------------- stall detection
-- The failure ORACLE: it is what turns "the run ended" into "the run ended HERE, waiting
-- on this". It lived in harness.lua, which cannot be loaded outside mGBA, so the most
-- flake-prone component in the playtest stack had no tests at all (#241).
local function rawProc(fields)
    return {
        slot = fields.slot or 3, script = fields.script or 0x085A7EF4,
        scr_cur = fields.scr_cur or 0x085A7F00, idle = fields.idle or 0x08007CA0,
        lock = fields.lock or 1, sleep = fields.sleep or 0,
    }
end

local sceneObs = {
    procs = { std_event = { idle = "event_engine" } },
    raw_procs = { rawProc({}) },
}

local function feed(watch, observation, times)
    local fired = nil
    for _ = 1, times do fired = watch(observation, C.classify(observation)) end
    return fired
end

local watch = C.stallWatch(3)
check(feed(watch, sceneObs, 2), nil, "an unclassified wait under the hold is not a stall")
check(feed(watch, sceneObs, 1) ~= nil, true, "an unclassified wait held long enough is a stall")
check(C.stallWatch(3)(sceneObs, "player_map_idle"), nil, "a classified STATE never arms the watch")

-- The PROC_REPEAT blindness this was written for: every long-running FE8 proc
-- (ProcScr_StdEventEngine, TalkWaitForInput, BMXFADE, YesNoChoice) is PROC_REPEAT, so
-- scrCur/idleCb/lockCnt are constant for a whole scene. A proc counting DOWN a timed
-- wait is progress, and the old signature could not see it.
local sleeping = C.stallWatch(3)
check(feed(sleeping, sceneObs, 2), nil, "two identical samples")
check(sleeping({ procs = sceneObs.procs, raw_procs = { rawProc({ sleep = 30 }) } },
    "transition"), nil, "a proc counting down its sleep resets the hold")

local growing = C.stallWatch(3)
check(feed(growing, sceneObs, 2), nil, "two identical samples")
check(growing({ procs = sceneObs.procs,
    raw_procs = { rawProc({}), rawProc({ slot = 4 }) } }, "transition"), nil,
    "a proc entering the pool resets the hold")

local shrinking = C.stallWatch(2)
check(shrinking({ procs = sceneObs.procs, raw_procs = { rawProc({}), rawProc({ slot = 4 }) } },
    "transition"), nil, "first sample of a two-proc pool")
check(shrinking(sceneObs, "transition"), nil, "a proc LEAVING the pool resets the hold too")

-- A named transition is a state we can wait out; arming on it trades a silent hang for a
-- noisy false FAIL, which is worse.
local fade = { procs = proc("map_fade", "map_fade_loop"), raw_procs = { rawProc({}) } }
check(feed(C.stallWatch(2), fade, 6), nil, "a CLASSIFIED transition (map_fade) never arms")

local leaving = C.stallWatch(2)
check(feed(leaving, sceneObs, 1), nil, "one sample")
check(leaving({ procs = proc("talk_wait", "talk_wait_input") }, "dialogue_wait"), nil,
    "leaving the transition state resets the hold")
check(feed(leaving, sceneObs, 1), nil, "and the count starts over rather than firing early")

local fired = feed(C.stallWatch(2), sceneObs, 2)
check(fired ~= nil and fired.state, "transition", "the stall carries the explanation with it")
check(fired ~= nil and fired.unclassified_wait, true,
    "and that explanation is the one that says nothing has a name for this")

-- Fallthrough: no rule matched at all.
local unknown = C.explain({ procs = { mystery = { idle = "mystery_idle" } } })
check(unknown.state, nil, "an unrecognised proc set fails closed")
check(type(unknown.error), "string", "the fallthrough explains itself")
check(#unknown.considered > 5, true, "the fallthrough reports every rule it rejected")

if fails > 0 then
    print(string.format("\n%d/%d FAILED", fails, tests))
    os.exit(1)
else
    print(string.format("ok -- %d assertions", tests))
end
