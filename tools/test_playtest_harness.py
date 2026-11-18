#!/usr/bin/env python3
"""Regression coverage for state-driven playtest scenario wiring."""
import os
import sys
import re
import unittest


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARNESS = os.path.join(REPO, 'tools/playtest/harness.lua')


def _read_harness():
    with open(HARNESS, encoding='utf-8') as source:
        return source.read()


def _block(harness, start_marker, end_marker):
    start = harness.index(start_marker)
    return harness[start:harness.index(end_marker, start + len(start_marker))]


class TestHarnessLoads(unittest.TestCase):
    def test_harness_lua_compiles(self):
        # #232, caught by Nicolas watching the run: harness.lua is ONE Lua chunk, and its
        # main function has Lua's 200-local cap. A few new top-level constants
        # pushed it over and the whole file stopped loading -- every scenario dies at once,
        # and nothing in a source-text assertion notices. Compile it for real.
        import shutil
        import subprocess
        lua = shutil.which('lua') or shutil.which('luac')
        if not lua:
            self.skipTest('no lua interpreter (brew install lua)')
        probe = ('local f, err = loadfile(%r); if not f then io.stderr:write(err) '
                 'os.exit(1) end' % HARNESS)
        done = subprocess.run([lua, '-e', probe], capture_output=True)
        self.assertEqual(done.returncode, 0,
                         'harness.lua does not load: %s' % done.stderr.decode())


    def test_harness_reads_no_stray_global(self):
        # PR #628: moving the convoy's helpers into a `do` block left the Item command's use
        # (api.use) calling `slotOf` and `count` as globals, nil at run time. The chunk still
        # compiled and every unit test passed; the first scout lap to use a seal crashed.
        # Every global harness.lua reads must be the emulator's, a run setting (PLAYTEST_*)
        # or Lua's own.
        import shutil
        import subprocess
        luac = shutil.which('luac')
        if not luac:
            self.skipTest('no luac (brew install lua)')
        listing = subprocess.run([luac, '-l', '-l', '-p', HARNESS],
                                 capture_output=True, text=True, check=True).stdout
        read = set(re.findall(r'GETTABUP\s.*_ENV "(\w+)"', listing))
        self.assertTrue(read, 'the luac listing format changed: no global read found')
        known = {'emu', 'callbacks', 'SYM', 'CAMPAIGN', 'C', 'PROCSCR',
                 '_G', 'assert', 'coroutine', 'dofile', 'error', 'io', 'ipairs', 'math',
                 'next', 'os', 'pairs', 'pcall', 'require', 'select', 'setmetatable',
                 'string', 'table', 'tonumber', 'tostring', 'type', 'utf8', 'xpcall'}
        stray = sorted(n for n in read if n not in known and not n.startswith('PLAYTEST_'))
        self.assertEqual(stray, [], 'harness.lua reads these as globals (nil at run time '
                                    'unless the emulator or the run defines them)')


class TestChooseAttackContract(unittest.TestCase):
    """#232. chooseAttack is the shared attack path -- every combat scenario in the
    campaign routes through it -- so both of its waits have to hold in every mode the
    scenarios actually run in."""

    def test_confirm_target_postcondition_is_not_battle_animation_only(self):
        # gProc_ekrBattle (observed as procs.battle) is the battle ANIMATION proc. Any
        # scenario that called pokeFastConfig() runs map combat, where it never spawns
        # -- so a postcondition of `after.procs.battle ~= nil` alone can never hold and
        # the attack fails despite having resolved (ch04packmath/ch04snag/clear_ch04).
        # The commit is INSPECT.commitTarget's, shared by the Attack and Staff paths.
        harness = _read_harness()
        self.assertIn('return INSPECT.commitTarget(actorAddr, stopWhen, "attack")',
                      _block(harness, 'local function chooseAttack(', '-- March a unit toward'))
        body = _block(harness, 'INSPECT.commitTarget = function(', 'INSPECT.awaitActed = ')
        self.assertIn('confirm_target', body)
        commit = body[body.index('"confirm_target"'):]
        commit = commit[:commit.index('end,')]
        self.assertIn('procs.battle', commit,
                      'the animated path should still be accepted as proof of commit')
        self.assertIn('target_selection', commit,
                      'map-combat scenarios need the mode-agnostic proof too: the '
                      'target selector closing')

    def test_combat_wait_budget_fits_an_unskipped_animation(self):
        # #220 retired waitFor's 50-frame A cadence, which had been advancing the
        # in-battle quote text. The ch00 boss animation then measured 1238 frames against
        # a 1200 budget, so every ch00/ch01 combat scenario timed out on a fight it had
        # already won. The budget must clear the measurement with real margin, because
        # vanilla's worst cases (crit, double, level-up, promotion) are much longer.
        harness = _read_harness()
        self.assertIn('combatFrames = ', harness)
        budget = int(harness.split('combatFrames = ')[1].split(',')[0])
        self.assertGreaterEqual(budget, 2400,
                                'a budget this close to the measured 1238 will flake on '
                                'any longer combat')
        self.assertIn('end, TUNE.combatFrames, true)', harness,
                      'the combat wait must use the named budget, not a literal')

    def test_win_ch00_gives_the_combat_wait_a_chapter_ending_escape(self):
        # chooseAttack waits for the actor to be greyed out (US_UNSELECTABLE). Killing
        # Sephek fires DefeatBoss on the spot, so the chapter tears the unit down and it
        # never greys -- the win succeeds and the wait times out anyway. chooseAttack
        # takes a stopWhen for exactly this; winCh00 has to pass one.
        body = _block(_read_harness(), 'local function winCh00()', '\nlocal function ')
        call = body[body.index('chooseAttack('):]
        call = call[:call.index('\n')]
        self.assertIn('function()', call,
                      'winCh00 must pass chooseAttack a stopWhen: the boss kill ends the '
                      'chapter, so the actor never becomes US_UNSELECTABLE')


class TestAwaitControllerState(unittest.TestCase):
    def test_dialogue_is_advanced_while_waiting_not_treated_as_a_fault(self):
        # #232. FE8 interleaves text with play (turn events, village lines, post-combat
        # quotes), so a wait for player_map_idle routinely passes through dialogue_wait.
        # Bailing there failed every ch01 flow on its first line of text. dialogue_wait is
        # a classified state with a legal guarded action, so advancing it is the #220
        # contract -- unlike the 50-frame blind cadence #220 removed.
        body = _block(_read_harness(), 'local function awaitControllerState(',
                      '\n-- Select unit at')
        self.assertIn('dialogue_wait', body)
        self.assertIn('INSPECT.advanceDialogue(', body)   # the guarded "advance_dialogue" press
        self.assertIn('want ~= "dialogue_wait"', body,
                      'a caller that explicitly waits FOR dialogue must still get it')
        self.assertIn('fail:unexpected-state:', body,
                      'every other unexpected state must still fail closed')

    def test_an_unwanted_screen_is_backed_out_of_and_the_recovery_is_traced(self):
        # #232, Nicolas's call: one screen the driver cannot commit used to cost the whole
        # remaining run. Backing out keeps the suite moving -- but it must be a legal
        # enumerated cancel, it must be TRACED, and the allowance must be small, or it
        # becomes the blanket rescue that hid five defects behind the old blind cadence.
        body = _block(_read_harness(), 'local function awaitControllerState(',
                      '\n-- Select unit at')
        self.assertIn('cancel_target', body)
        self.assertIn('cancel_menu', body)
        self.assertIn('TUNE.stuckRecoveries', body, 'recovery must be bounded')
        self.assertIn('"recovered"', body, 'every recovery must land in the trace')
        self.assertIn('fail:unexpected-state:', body,
                      'a screen that outlives the allowance must still fail closed')

    def test_the_budget_counts_stall_not_wall_clock(self):
        # #232/#335. A wait for the map to become playable spans whole cutscenes AND whole
        # enemy phases, and no fixed budget fits every one -- the ch01 opening outran 300
        # frames, and so did clear_ch02's ~2100-frame turn 1 -- each logging a fault on a
        # chapter the scenario went on to clear. What counts as the engine working is
        # Controller.engineIsWorking's to decide, because there it is tested against
        # observations instead of asserted as a substring here; the budget must consult it
        # rather than re-deciding inline. A genuinely wedged engine still fails closed here
        # rather than at run.sh's wall-clock deadline.
        body = _block(_read_harness(), 'local function awaitControllerState(',
                      '\n-- Select unit at')
        self.assertIn('Controller.engineIsWorking(last)', body,
                      'the stall budget must consult the tested predicate')
        self.assertIn('idle = idle + 1', body, 'and only count frames it rejects')
        self.assertIn('STALL_CEILING', body, 'the wait must still terminate on its own')
        self.assertIn('fail:state-timeout', body)

    def test_a_scene_prompt_between_chapters_is_answered_and_logged(self):
        # The Eirika lap from vanilla's prologue (2026-11-15) crashed after E_16: the scene at
        # chapter index 71 asks a yes/no question no pick came before, and the arrival loop
        # answered only a pick's confirmation. The prompt takes its highlighted answer under the
        # controller's own name for it (a bare A is an illegal input), and the question is
        # logged: the last three messages decoded before a choice proc opened (its labels can
        # decode first: E_16's first prompt logged 0x843 "Yes").
        body = _block(_read_harness(), 'local stalled = INSPECT.watch("arrive")',
                      'unsupported state between chapters')
        pick = body.index('elseif state == "yes_no_choice" and menuPicked ~= nil then')
        scene = body.index('elseif state == "yes_no_choice" then', pick)
        before, tail = body[:pick], body[scene:]
        self.assertRegex(before, r'if not \(obs\.procs\.yes_no or obs\.procs\.talk_choice\) then'
                                 r'[\s\S]*?INSPECT\.activeMsg\(\)[\s\S]*?INSPECT\.msgLine\(\)')
        answer = tail.index('guardedInput')
        self.assertRegex(before, r'table\.insert\(asked,\s*1,')
        self.assertRegex(tail[:answer], r'for _, m in ipairs\(asked\)')
        self.assertRegex(tail[:answer], r'if not current then return nil,')
        self.assertRegex(tail, r'guardedInput\(\s*"answer_"\s*\.\.\s*current\s*,\s*"A"')

    def test_a_full_bag_between_chapters_is_answered_by_the_bots_chooser(self):
        # After E_19 (2026-11-16) a scene gave an item to a unit with a full bag, and the
        # arrival loop stopped: "unsupported state between chapters: send_to_convoy". It asks
        # the same chooser the map does (INSPECT.answerWait -> INSPECT.onFullBag).
        harness = _read_harness()
        body = _block(harness, 'local stalled = INSPECT.watch("arrive")',
                      'unsupported state between chapters')
        bag = body.index('elseif state == "send_to_convoy" then')
        # before the generic fallback, so it is reached
        self.assertLess(bag, body.index('elseif state ~= "player_map_idle" then'))
        branch = body[bag:body.index('elseif state ~= "player_map_idle" then')]
        self.assertIn('INSPECT.answerWait(state)', branch)
        # its answer is marked read: the next chapter's record never claims it (PR #635 review)
        self.assertRegex(branch, r'INSPECT\.bagLog\.seen\s*=\s*#INSPECT\.bagLog')
        # the campaign installs the chooser itself, before any attempt's botApi
        camp = _block(harness, 'INSPECT.campaignApi = function(game)', 'local seed = ')
        self.assertIn('INSPECT.onFullBag = INSPECT.answerFullBag', camp)

    def test_every_yes_no_prompt_closes_by_one_predicate(self):
        # PR #632 review: the "prompt has closed" predicate had six hand-rolled copies.
        harness = _read_harness()
        self.assertEqual(harness.count('~= "yes_no_choice"'), 1, 'INSPECT.promptClosed owns it')
        self.assertIn('INSPECT.promptClosed = function(after)', harness)

    def test_an_act_is_done_only_once_the_map_is_idle_past_canto(self):
        # The act sets US_UNSELECTABLE before TryMakeCantoUnit clears it and hands a Canto unit
        # its second move (playerphase.c). awaitActed read the bit in that window after a
        # Rescue (vanilla E_19, 2026-11-16), the bot replanned, and the next unit's input met
        # the Canto move. The bit counts only with the map idle again.
        harness = _read_harness()
        body = _block(harness, 'INSPECT.awaitActed = function(', '\n    local done = ')
        # the bit the read names is one the bound board carries (an unbound name reads nil)
        self.assertIn('INSPECT.greyed = function(addr) return (ru32(addr + 0x0C) & BOARD.US_UNSELECTABLE)',
                      harness)
        with open(os.path.join(REPO, 'tools/playtest/board.lua'), encoding='utf-8') as fh:
            self.assertRegex(fh.read(), r'US_UNSELECTABLE = Board\.US_UNSELECTABLE')
        self.assertRegex(body, r'INSPECT\.greyed\(actorAddr\)\s+and\s+'
                               r'controllerState\(\)\s*==\s*"player_map_idle"')

    def test_the_win_fired_by_the_last_kill_leaves_no_turn_to_end(self):
        # #335. A clear-bot that kills the final enemy can fire the DefeatAll win right there,
        # and the ending then plays INSIDE the old chapter slot -- so `chapter() ~= start` is
        # still false while the map is already gone. Ending the turn at that point makes
        # endTurn wait for a player_map_idle this chapter will never show again, and it walks
        # into the post-chapter save prompt and the next chapter's title card and fails the run
        # on them. The precondition endTurn actually needs is the one that must be checked.
        harness = _read_harness()
        body = _block(harness, 'local function endTurn(', '\n-- End turn, then ride out')
        self.assertIn('alreadyWon', body, 'callers firing a win must be able to say so')
        self.assertIn('waitFor', body,
                      'and it must settle -- FE8 is mid-transition right after the last kill')
        self.assertIn('~= "player_map_idle"', body,
                      'the decision must rest on the player actually having the map back')
        # Both clear-and-chain scenarios must go through it; a second hand-rolled copy is how
        # one of them silently keeps the bug.
        self.assertNotIn('if routed and not advanced() then endTurn()', harness,
                         'no scenario may end the turn on the chapter-number guard alone')
        self.assertEqual(harness.count('endTurn(nil, advanced)'), 1,
                         'clear_ch02 must pass the win predicate')

    def test_a_chapter_ending_mid_phase_is_an_exit_not_a_wedge(self):
        # #335. A DefeatAll win fires the ending from INSIDE the enemy phase, and from there
        # FE8 goes to the post-chapter save prompt and the next chapter -- no player phase is
        # ever coming back. runEnemyPhase waited for one anyway, spent its whole budget and
        # reported a phase timeout on a chapter clear_ch04_parley had cleared and chained out
        # of. Raising the cap only made it fail slower; the loop has to recognise the exit.
        body = _block(_read_harness(), 'local function runEnemyPhase(', '\n-- Detecting an on-screen')
        self.assertIn('startedIn', body, 'the phase must remember which chapter it began in')
        self.assertIn('"ended"', body, 'and report a chapter that finished under it')
        self.assertIn('fail:phase-timeout', body, 'a genuinely wedged phase must still fail')
        # The fault is what a verdict trips over, so the normal exit must come FIRST.
        self.assertLess(body.index('"ended"'), body.index('fail:phase-timeout'),
                        'the chapter-ended exit must precede the timeout trace')

    def test_the_enemy_phase_cap_outlives_a_phase_that_contains_a_scene(self):
        # #335, the other half of the same failure. ch04's parley phase plays a cutscene and
        # then the chapter ending inside the enemy phase: it was still running, chapter
        # unchanged, 3,768 frames in, and the chapter did not flip until past 9,800. So the
        # chapter-ended exit above can only fire if the cap outlives the scene -- with a flat
        # 3,600 the loop died first and the exit never got the chance. Both are needed.
        harness = _read_harness()
        body = _block(harness, 'local function runEnemyPhase(', '\n-- Detecting an on-screen')
        self.assertIn('TUNE.enemyPhaseFrames', body,
                      'the cap must be a named tunable, not a literal in the loop head')
        m = re.search(r'enemyPhaseFrames = (\d+)', harness)
        self.assertIsNotNone(m, 'TUNE.enemyPhaseFrames must be defined')
        self.assertGreater(int(m.group(1)), 9800,
                           'it must outlive the longest scene-bearing phase measured')

    def test_a_unit_off_the_map_is_not_a_tile_at_x_255(self):
        # #335. struct Unit's xPos/yPos are s8 (bmunit.h), and FE8 parks a unit that is not on
        # the map at xPos -1. unitAt read them with ru8, so such a unit reported x=255: the
        # clear-bot took it for a real position, drove the cursor at (255,8) on a 25-wide map,
        # and failed clear_ch01 with an illegal input it could never satisfy. ch02 showed the
        # same number in "teleportToFiringTile: (255,9)", which only survived because that one
        # site happened to bail. Read the field the width the struct declares, and keep an
        # off-map unit out of the lists that drive the cursor. The read lives in board.lua,
        # the one board reader (#510 step 9); harness unitAt only delegates to it.
        harness = _read_harness()
        body = _block(harness, 'local function unitAt(', '\nlocal function blue')
        self.assertIn('BOARD.leanAt(base, i)', body, 'unitAt delegates to board.lua')
        with open(os.path.join(REPO, 'tools/playtest/board.lua'), encoding='utf-8') as fh:
            board = _block(fh.read(), 'function Board.leanAt(', '\nend\n')
        self.assertIn('mem.s8(a + 0x10)', board, 'xPos is s8')
        self.assertIn('mem.s8(a + 0x11)', board, 'yPos is s8')
        self.assertNotIn('mem.u8(a + 0x10)', board, 'the unsigned read is the bug')
        live = _block(harness, 'local function liveEnemies(', '\n\n')
        self.assertIn('onField', live, 'a target list must not offer an off-map unit (onField implies onMap)')

    def test_no_guard_still_compares_a_units_x_against_255(self):
        # The other half of the same change, and the one that was missed. Switching unitAt to
        # rs8 silently RETIRED every `u.x ~= 0xFF` guard in the file: rs8 cannot return 255,
        # so each one became vacuously true (and the two `== 0xFF` forms vacuously false).
        # That is worse than the crash it replaced -- deployment counters counted units that
        # were not on the map, partyDeployed() returned true on a unit that had not been
        # placed (the exact false positive its own comment says it exists to prevent), and
        # the off-map lord and Baxby checks could never fire again. A guard that stops
        # guarding fails silently, so pin the encoding rather than the call sites.
        harness = _read_harness()
        self.assertNotIn('.x == 0xFF', harness,
                         'an off-map test must read .onMap; rs8 never returns 255')
        self.assertNotIn('.x ~= 0xFF', harness,
                         'an off-map test must read .onMap; rs8 never returns 255')

    def test_an_off_map_destination_is_refused_by_name(self):
        # #335. The #220/#238 controller contract governs INPUTS -- it enumerates legal actions
        # and verifies postconditions -- but it cannot vet the DESTINATION a caller asks for.
        # Handed (-1,8), cursorTo walked the cursor to the wall at x=0 and then reported
        # "cursor_left is not legal", which is true and useless: the defect is the target, and
        # the bot read it off a unit that was not on the map. A target outside the map is
        # refused up front, named, so the trace points at the caller instead of a wall.
        harness = _read_harness()
        body = _block(harness, 'local function cursorTo(', '\nlocal function waitFor')
        self.assertIn('mapSize()', body, 'the target must be checked against the real map')
        self.assertIn('off-map', body, 'and refused by name')
        self.assertIn('traceFailure', body, 'failing closed, in the trace')

    def test_a_destination_the_unit_cannot_reach_is_not_a_controller_fault(self):
        # #335. Once ch01's boss dies, the clear loop offers the seize tile to every remaining
        # unit in turn. The ones that cannot reach it drove the cursor there anyway and pressed
        # A, and FE8 -- correctly -- offers no confirm on an unreachable tile, so each attempt
        # logged `confirm_move: fail:not-legal`. That sticky fault failed a run that went on to
        # WIN by turn 9. "This unit cannot get there" is an answer, not a defect: check the
        # movement map after selecting and back out cleanly, leaving no fault behind.
        harness = _read_harness()
        body = _block(harness, 'local function moveUnit(', '\nlocal function chooseWait')
        self.assertIn('reachCost(tx, ty)', body,
                      'the destination must be checked against the live movement map')
        self.assertIn('cancel_selection', body, 'and the selection backed out cleanly')
        self.assertNotIn('traceFailure', body, 'an out-of-range destination is not a fault')

    def test_engine_is_working_recognises_the_phases_that_are_not_stalls(self):
        # The predicate is unit-tested in tools/playtest/test_controller.lua; this pins that
        # it keeps covering the two cases that produced real controller faults, so deleting
        # either arm cannot pass by moving the constant somewhere else.
        src = open(os.path.join(REPO, 'tools/playtest/controller.lua'), encoding='utf-8').read()
        body = _block(src, 'function M.engineIsWorking(', '\nfunction M.formatTrace')
        self.assertIn('std_event', body, 'event-engine progress must be recognised (#232)')
        self.assertIn('FACTION_PLAYER', body, 'a phase the player does not control (#335)')


class TestPlaytestHarness(unittest.TestCase):
    def test_recorder_terminal_observes_dialogue_before_advancing_it(self):
        # #260's visual proof records whether its four-box warning was actually seen.
        # If recordCutscene advances the wait first and calls doneFn second, the callback
        # can never observe dialogue_wait and the scenario times out after a good scene.
        harness = _read_harness()
        body = _block(harness, 'local function recordCutscene(o)',
                      '\nlocal function tileOccupied')
        loop = body[body.index('while fr < maxFrames do'):]
        observe = loop.index('if doneFn() then reached = true break end')
        advance = loop.index('if autoAdvanceDialogue and controllerState() == "dialogue_wait" then')
        self.assertLess(observe, advance,
                        'the terminal callback must see a dialogue wait before the recorder '
                        'consumes it')

    def test_ch05recruit_advances_and_counts_the_new_eruption_boxes(self):
        harness = _read_harness()
        body = _block(harness, 'scenarios.ch05recruit = function(opts)',
                      '\n-- ch05lupinbenched')
        self.assertIn('eruptionBoxes', body,
                      'the recruit gate would hang before Sahnar LOADs if it never advances '
                      'Ravisin\'s newly visible warning')
        # The eruption's OWN talkUntil: it advances only on an observed dialogue_wait, stops
        # on turn 2 AND all four boxes, and counts each box as it comes up. Any other
        # talkUntil in the body (there are several) must not satisfy this.
        self.assertIn('INSPECT.talkUntil(function() return turn() >= 2 and eruptionBoxes >= 4 end',
                      body)
        self.assertIn('onBox = function() eruptionBoxes = eruptionBoxes + 1 end', body)
        self.assertIn('controllerState() == "dialogue_wait"',
                      _block(harness, 'function INSPECT.talkUntil(', '\nend\n'))
        self.assertIn('"advance_dialogue"', _block(harness, 'function INSPECT.advanceDialogue(', '\n\n'))
        self.assertIn('eruption warning showed %d boxes', body,
                      'the gate must distinguish the locked four-box scene from merely '
                      'reaching turn 2')

    def test_goodberry_finds_its_row_by_item_id_not_by_bag_position(self):
        """One DOWN was the Goodberry until #430 gave Hlin a Killer Axe first; from then on it
        highlighted the Hand Axe (#531 item 10, the instrumented run's item dump)."""
        body = _block(_read_harness(), 'scenarios.goodberry = function()', '\nend\n')
        self.assertIn('local GOODBERRY = 0x6C', body)
        self.assertIn('down and "menu_next" or "menu_previous"', body)
        self.assertIn('if list.current ~= row then', body)

    def test_the_observed_menu_is_the_unlocked_one_when_a_submenu_sits_above_its_parent(self):
        """A submenu locks its parent and can take a HIGHER pool slot; the lowest-slot menu
        was then the locked parent and the controller read 'transition' while the submenu
        was up (goodberry's instrumented run: parent slot 7 locked, submenu slot 16)."""
        body = _block(_read_harness(), 'local function anyMenuProc()', '\nend\n')
        self.assertIn('if not lowest or ru8(lowest + 0x28) == 0 then return lowest end', body)
        self.assertIn('ru8(p.addr + 0x28) == 0 then', body)
        self.assertIn('off % pool.stride ~= 0', body, 'the walk stays inside the proc pool')
        self.assertIn('if up == lowest then return p.addr end', body,
                      'only a DESCENDANT of the locked menu may stand in for it')

    def test_ch05recruit_names_the_message_id_it_saw_not_just_the_box_count(self):
        """The Talk recruit's two arms both recruit Sahnar and both run 21 boxes (#25), so
        every other assertion in this gate passes on either one. `sActiveMsg` is the only
        witness that separates them, and it has to be SAMPLED WHILE A BOX IS UP -- menus and
        unit names decode through the same buffer the moment the scene ends."""
        harness = _read_harness()
        body = _block(harness, 'scenarios.ch05recruit = function(opts)',
                      '\n-- ch05lupinbenched')
        self.assertIn('INSPECT.activeMsg()', body)
        self.assertIn('playedMsg = playedMsg or INSPECT.activeMsg()', body,
                      'the id must be latched on the FIRST box, not read after the scene')
        self.assertIn('if playedMsg ~= ARM then', body,
                      'sampling the arm without asserting it is a gate that cannot fail')

    def test_the_two_owed_check_alive_states_each_name_their_expected_arm(self):
        """benched -> the wolf's arm (0x9E8); killed -> the no-Lupin arm (0x9D1). The pair IS
        the proof #25 still owed, and getting either expectation backwards would make the run
        certify the bug it exists to catch."""
        harness = _read_harness()
        for scenario, state, arm in (('ch05lupinbenched', 'benched', '0x9E8'),
                                     ('ch05lupinkilled', 'killed', '0x9D1')):
            body = _block(harness, 'scenarios.%s = function()' % scenario, '\nend')
            self.assertIn('lupin = "%s"' % state, body)
            self.assertIn('arm = %s' % arm, body)

    def test_ch05arena_proves_the_loaded_winter_palette_and_skeleton_face(self):
        harness = _read_harness()
        body = _block(harness, 'scenarios.ch05arena = function()', '\nend')
        self.assertIn('SYM.gFaces', body)
        self.assertIn('ru16(face + 0x3E) == 0x4B', body,
                      'the live Arena face proc must carry the chapter-selected Glen FID')
        for word, what in (('0x779B', 'the overcast sky'), ('0x3127', 'the blue awning')):
            self.assertIn(word, body, '%s must be proven to have arrived' % what)
        for word, what in (('0x3F19', 'sandstone'), ('0x194B', 'stone shadow'),
                           ('0x4B9D', 'bright stone')):
            self.assertIn(word, body,
                          'the welcome screen keeps its warm masonry -- vanilla %s must be '
                          'proven UNCHANGED, or a wash-out passes' % what)
        self.assertIn('shot("ch05arena-welcome")', body,
                      'the asserted presentation must still be captured for visual review')
        self.assertIn('pokeAnimsOn()', body,
                      'the Arena proof must leave full battle animations on for review')
        self.assertIn('shootCombatFrames("ch05arena-combat")', body,
                      'the accepted wager must capture the real in-combat presentation')
        for word, what in (('0x7FFF', 'the snow floor'), ('0x45A9', 'the blue banner')):
            self.assertIn(word, body, '%s must be proven to have arrived' % what)
        # The regression this feature actually shipped: a cold ramp across all 64 words per
        # phase passed every data check and lost the coliseum. Anchors that only prove the new
        # colours arrived would have passed it too.
        for word, what in (('0x473D', 'crowd gold'), ('0x4AD8', 'upper stone'),
                           ('0x292A', 'pillar grey')):
            self.assertIn(word, body,
                          'vanilla %s must be proven UNCHANGED, or a wash-out passes' % what)
        self.assertIn('VANILLA', body,
                      'the preserved anchors must be labelled as such in the failure text')
        self.assertIn('Arena combat BG %s (bank %d idx %d)', body)
        self.assertLess(body.index('combatPaletteAnchors'),
                        body.index('shootCombatFrames("ch05arena-combat")'),
                        'the palette must be observed while combat is live, before the recorder '
                        'returns to the Arena UI')
        self.assertIn('generated its opponent', body,
                      'presentation proof may not replace the real wager/opponent proof')

        # gProcScr_ArenaUiMain runs TWO blocking dialogue pages between the accepted wager
        # and the fight (ArenaUi_InstructionsDialogue 0x8D5, ArenaUi_GoodLuckDialogue 0x8D3).
        # A single press on a fat budget reaches combat anyway -- through guardedInput's
        # lost-input re-press -- so the scenario passed by ACCIDENT for as long as it did
        # (#269). Counting the pages is what turns arriving at combat into proof, and #255
        # caches passes, so a silent regression here would be frozen rather than noticed.
        self.assertIn('arenaPages ~= 2', body,
                      'the Arena flow must assert its two-page anatomy, not merely arrive '
                      'at combat -- one press reaches the fight by lost-input retry (#269)')
        self.assertIn('ARENA TRAIL', body,
                      'a failure here must carry its own state trail, or diagnosing it costs '
                      'a second emulator run')
        self.assertNotIn(', 1800) then', body,
                         'the 1800-frame single-press budget is what made the accidental pass '
                         'possible; each page now presses on its own postcondition')

        with open(os.path.join(REPO, 'tools/playtest/gen_symbols.py'), encoding='utf-8') as f:
            symbols = f.read()
        self.assertIn("'gFaces'", symbols)

    def test_ch04snag_accepts_the_native_fallen_snag_crossing(self):
        harness = _read_harness()
        body = _block(harness, 'scenarios.ch04snag = function()', '\n-- clear_ch04 / clear_ch04_parley')
        self.assertIn('local T_CROSSING = 0x34', body,
                      'the painted center metatile uses TERRAIN_BRIDGE_SNAG; the playtest '
                      'must not retain the old generic-bridge workaround')

class TestDifficultyGateDefault(unittest.TestCase):
    """The playtest gate grades NORMAL unless a scenario asks otherwise (#303 follow-up).

    FE8's difficulty menu initialises to option 0 (Tutorial) and the harness only ever
    pressed A, so every verdict this project produced before #303 graded the EASIEST mode
    while reading as general. Normal is what ships to most players and what
    `difficulty.py` grades by default, so it is what the gate must run.

    Pinned at the source, because the default is a module-level constant evaluated at load
    and there is no way to observe it without booting mGBA.
    """

    def _harness(self):
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, 'playtest', 'harness.lua'), encoding='utf-8') as fh:
            return fh.read()

    def _mode_table(self, src):
        """The one mode->menu-index table, parsed. FE8's menu order is fixed:
        option 0 Tutorial, 1 Normal, 2 Difficult (SaveMenuWriteNewGame, savemenu.c:522)."""
        m = re.search(r'difficultyIndex\s*=\s*\{(.*?)\}', src, re.S)
        self.assertIsNotNone(m, 'harness.lua must expose one named mode->index table')
        return {k: int(v) for k, v in re.findall(r'(\w+)\s*=\s*(\d+)', m.group(1))}

    def test_the_menu_indices_match_fe8s_own_order(self):
        # Pins the MAPPING, not the spelling. Swapping tutorial/normal here would make the
        # gate confirm Tutorial while calling it Normal -- the exact regression this PR
        # exists to prevent, and a string-only assertion sails straight past it.
        self.assertEqual(self._mode_table(self._harness()),
                         {'tutorial': 0, 'normal': 1, 'difficult': 2})

    def test_the_default_mode_resolves_to_normal(self):
        src = self._harness()
        m = re.search(r'PLAYTEST_DIFFICULTY\s*or\s*"(\w+)"', src)
        self.assertIsNotNone(m, 'harness.lua must name its fallback mode')
        self.assertEqual(m.group(1), 'normal')
        self.assertEqual(self._mode_table(src)[m.group(1)], 1,
                         'the fallback must resolve to menu option 1 (Normal)')

    def test_run_sh_and_the_harness_agree_on_the_default(self):
        # run.sh owns the default; harness.lua's fallback only fires for entry points that
        # bypass it. They must not be able to disagree about what "unset" means.
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, 'playtest', 'run.sh'), encoding='utf-8') as fh:
            run = fh.read()
        m = re.search(r'PT_DIFFICULTY:-(\w+)', run)
        self.assertIsNotNone(m, 'run.sh must default PT_DIFFICULTY')
        self.assertEqual(m.group(1), 'normal')

    def test_the_checkpoint_stamp_includes_the_mode(self):
        # A save state carries the difficulty it was minted in. Keying checkpoints on the
        # ROM hash alone reloads a Tutorial state under a Normal label, and this change
        # alters no ROM bytes -- so the hash cannot notice.
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, 'playtest', 'run.sh'), encoding='utf-8') as fh:
            run = fh.read()
        self.assertIn('CHECKPOINT_STAMP', run,
                      'checkpoint validity must include the difficulty mode, not just ROMHASH')



RUN_SH = os.path.join(REPO, 'tools/playtest/run.sh')


class TestUnitStateBits(unittest.TestCase):
    def test_board_lua_state_bits_are_the_decomps(self):
        # board.lua owns the unit state bits; sight.lua sets them to steer FE8's own code
        # (US_HIDDEN keeps a unit out of the AI's target loop, US_UNDER_A_ROOF out of the danger
        # zone's). A wrong bit is silent: `1 << 30` for the roof made threat(e) every enemy's
        # danger zone. So each `Board.US_* = 1 << N` is read against include/bmunit.h, and a bit
        # written any other way fails rather than going unchecked.
        sys.path.insert(0, os.path.join(REPO, 'tools'))
        from inject.decomp import enum_values, vanilla_decomp_text
        decomp = enum_values(vanilla_decomp_text('include/bmunit.h'), 'US_')
        with open(os.path.join(REPO, 'tools/playtest/board.lua'), encoding='utf-8') as fh:
            text = fh.read()
        named = re.findall(r'^Board\.(US_\w+)\s*=', text, re.M)
        bits = dict(re.findall(r'^Board\.(US_\w+) = 1 << (\d+)\b', text, re.M))
        self.assertIn('US_UNDER_A_ROOF', named, 'board.lua names no US_UNDER_A_ROOF')
        self.assertEqual(sorted(named), sorted(bits),
                         'a Board.US_* bit not written as `1 << N` goes unchecked')
        for name, shift in bits.items():
            self.assertEqual(1 << int(shift), decomp.get(name), name)


class TestHealStaves(unittest.TestCase):
    def test_sight_lua_heal_staves_are_the_ones_doitemuse_heals_with(self):
        # sight.staves offers a staff as a heal; the harness then plays gSelectInfo_Heal's
        # target selection. GetUnitItemHealAmount adds power for every staff, so it let a
        # Barrier through and the game opened gSelectInfo_Barrier (vanilla E_16, a crash). The
        # set is the case labels DoItemUse (bmitemuse.c) sends to DoUseHealStaff.
        sys.path.insert(0, os.path.join(REPO, 'tools'))
        from inject.decomp import enum_values, vanilla_decomp_text
        items = enum_values(vanilla_decomp_text('include/constants/items.h'), 'ITEM_')
        src = vanilla_decomp_text('src/bmitemuse.c')
        body = src[src.index('void DoItemUse('):]
        body = body[:body.index('\n}\n')]
        heal = set()
        for labels, call in re.findall(r'((?:\s*case \w+:)+)\s*(\w+)\(', body):
            if call == 'DoUseHealStaff':
                heal |= {items[n] for n in re.findall(r'case (\w+):', labels)}
        self.assertEqual(len(heal), 4, 'Heal, Mend, Recover, Physic')
        with open(os.path.join(REPO, 'tools/playtest/sight.lua'), encoding='utf-8') as fh:
            m = re.search(r'^M\.HEAL_STAVES = \{([^}]*)\}', fh.read(), re.M)
        self.assertIsNotNone(m, 'sight.lua names M.HEAL_STAVES in one table')
        lua = {int(v, 16) for v in re.findall(r'\[(0x[0-9A-Fa-f]+)\] = true', m.group(1))}
        self.assertEqual(lua, heal)

    def test_the_sustain_demand_is_answered_by_a_heal_staff(self):
        # The team's `sustain` demand took any staff CanUnitUseStaff allows, so a Barrier
        # fielded as the party's healer (PR #631 review). It asks s.staves, the one owner of
        # what a heal staff is.
        with open(os.path.join(REPO, 'tools/playtest/sight.lua'), encoding='utf-8') as fh:
            text = fh.read()
        body = _block(text, 'elseif d.kind == "sustain" then', 'elseif d.kind == "village"')
        self.assertIn('#s.staves(u) > 0', body)
        self.assertNotIn('CanUnitUseStaff', body)


class TestAiActionIds(unittest.TestCase):
    def test_board_lua_ai_actions_are_the_decomps(self):
        # board.lua names the AI's action ids it reads off gAiDecision (Board.fate tells an
        # escape from a death by AI_ACTION_ESCAPE); a wrong id would read an escape as a kill.
        sys.path.insert(0, os.path.join(REPO, 'tools'))
        from inject.decomp import enum_values, vanilla_decomp_text
        decomp = enum_values(vanilla_decomp_text('include/cp_common.h'), 'AI_ACTION_')
        with open(os.path.join(REPO, 'tools/playtest/board.lua'), encoding='utf-8') as fh:
            text = fh.read()
        m = re.search(r'^(Board\.AI_ACTION_\w+(?:, Board\.AI_ACTION_\w+)*) =\s*([\d, ]+)$', text, re.M)
        self.assertIsNotNone(m, 'board.lua names its AI_ACTION_* ids in one assignment')
        names = [n.strip()[len('Board.'):] for n in m.group(1).split(',')]
        values = [int(v) for v in m.group(2).split(',')]
        self.assertEqual(len(names), len(values))
        for name, value in zip(names, values):
            self.assertEqual(value, decomp.get(name), name)


class TestPillageNamesTheVillage(unittest.TestCase):
    def test_a_pillage_act_names_the_tile_the_explore_log_keys(self):
        # botrun's explore log keys a village on the tile sight.explorable lists, the one a Visit
        # stands on; AiPillageAction's gAiDecision is that same tile and its event runs one row
        # above (cp_perform.c). The enemy-act watch named the row above, so `closedBy` matched
        # nothing and a razed village carried no `closed_by` (fwd1, vanilla Ch9's (11,15)).
        sys.path.insert(0, os.path.join(REPO, 'tools'))
        from inject.decomp import vanilla_decomp_text
        decomp = vanilla_decomp_text('src/cp_perform.c')
        body = decomp[decomp.index('AiPillageAction('):]
        body = body[:body.index('\n}')]
        self.assertIn('int y = gAiDecision.yMove;', body, 'the decision is the village tile')
        self.assertRegex(body, r'y2 = y - 1;\s*StartAvailableTileEvent\(\(s8\)x, y2\)',
                         'and the event runs one row above it')
        with open(os.path.join(REPO, 'tools/playtest/harness.lua'), encoding='utf-8') as fh:
            text = fh.read()
        m = re.search(r'cur\.act, cur\.tile = "pillage", (\{[^}]*\})', text)
        self.assertIsNotNone(m, 'the enemy-act watch names a pillaged tile')
        self.assertEqual(m.group(1), '{ x = cur.dest.x, y = cur.dest.y }')


class TestItemAfterUse(unittest.TestCase):
    def test_board_lua_item_after_use_is_the_games(self):
        # Board.itemAfterUse copies bmitem.c GetItemAfterUse (#644: a game call a use cost the
        # bot ~3% CPU). PR #645 review: prove the copy is the game's. The game's own function,
        # compiled on the host from the decomp's source with GetItemAttributes reading
        # data_items.c's attributes, and the copy, reading the same attributes off an ItemData
        # table laid out as Board.itemData reads it, are run on every item at the use counts
        # that tell them apart (none, one, a few, its full uses, 0xFF) and must agree.
        import shutil
        import subprocess
        import tempfile
        cc, lua = shutil.which('cc'), shutil.which('lua')
        if not (cc and lua):
            self.skipTest('needs a host C compiler and lua')
        sys.path.insert(0, os.path.join(REPO, 'tools'))
        from inject.decomp import enum_values, vanilla_decomp_text
        ia = enum_values(vanilla_decomp_text('include/bmitem.h'), 'IA_')
        ids = enum_values(vanilla_decomp_text('include/constants/items.h'), 'ITEM_')
        src = vanilla_decomp_text('src/bmitem.c')
        fn = src[src.index('u16 GetItemAfterUse(int item) {'):]
        fn = fn[:fn.index('\n}\n') + 3]
        items = {}
        for name, body in re.findall(r'\[(ITEM_\w+)\] = \{(.*?)\n\t\}',
                                     vanilla_decomp_text('src/data_items.c'), re.S):
            m = re.search(r'\.attributes = ([^,]+),', body)
            attrs = 0
            for flag in (m.group(1).split('|') if m else []):
                attrs |= ia[flag.strip()]
            uses = re.search(r'\.maxUses = (\d+),', body)
            items[ids[name]] = (attrs, int(uses.group(1)) if uses else 0)
        self.assertGreater(len(items), 100, 'data_items.c read')
        self.assertTrue(any(a & ia['IA_UNBREAKABLE'] for a, _ in items.values()),
                        'the table holds unbreakable items, the case the copy tells apart')
        cases = sorted({(i, u) for i, (_, full) in items.items()
                        for u in (0, 1, 2, 3, full, 0xFF)})
        with tempfile.TemporaryDirectory() as tmp:
            c = os.path.join(tmp, 'after.c')
            with open(c, 'w', encoding='utf-8') as fh:
                fh.write('#include <stdio.h>\ntypedef unsigned short u16;\n')
                fh.write('#define IA_UNBREAKABLE %d\n' % ia['IA_UNBREAKABLE'])
                fh.write('static const unsigned attrs[256] = {%s};\n' % ', '.join(
                    str(items.get(i, (0, 0))[0]) for i in range(256)))
                fh.write('static int GetItemAttributes(int item) { return attrs[item & 0xFF]; }\n')
                fh.write(fn)
                fh.write('int main(void) { int i, u; while (scanf("%d %d", &i, &u) == 2) '
                         'printf("%d\\n", GetItemAfterUse(i | (u << 8))); return 0; }\n')
            exe = os.path.join(tmp, 'after')
            subprocess.run([cc, '-o', exe, c], check=True, capture_output=True)
            stdin = ''.join('%d %d\n' % k for k in cases)
            game = subprocess.run([exe], input=stdin, capture_output=True, text=True,
                                  check=True).stdout.split()
        probe = ('local Board = dofile(%r) '
                 'local attrs = {%s} '
                 'local SYM = { gItemData = 0x10000 } '
                 'local mem = { u32 = function(a) return attrs[(a - 0x10000 - 8) // '
                 'Board.ITEMDATA_STRIDE] or 0 end, u8 = function() return 0 end } '
                 'for i, u in io.read("a"):gmatch("(%%d+) (%%d+)") do '
                 'print(Board.itemAfterUse(mem, SYM, tonumber(i) | (tonumber(u) << 8))) end'
                 % (os.path.join(REPO, 'tools/playtest/board.lua'),
                    ', '.join('[%d] = %d' % (i, a) for i, (a, _) in items.items())))
        ours = subprocess.run([lua, '-e', probe], input=stdin, capture_output=True, text=True,
                              check=True).stdout.split()
        self.assertEqual(len(game), len(cases))
        diverged = [(k, g, o) for k, g, o in zip(cases, game, ours) if g != o]
        self.assertEqual(diverged, [], '(item, uses), the game, the copy')


class TestFullBagItems(unittest.TestCase):
    def test_bag_item_ids_are_the_decomps(self):
        # INSPECT.BAG names each key and passive item it lists (Bot.fullBag's kinds); a wrong id
        # would silently file a key as money and send it to the convoy. Each `[0xNN] = "ITEM_X"`
        # is read against include/constants/items.h.
        sys.path.insert(0, os.path.join(REPO, 'tools'))
        from inject.decomp import enum_values, vanilla_decomp_text
        items = enum_values(vanilla_decomp_text('include/constants/items.h'), 'ITEM_')
        with open(os.path.join(REPO, 'tools/playtest/harness.lua'), encoding='utf-8') as fh:
            text = fh.read()
        block = text[text.index('INSPECT.BAG = {'):]
        block = block[:block.index('\n}\n')]
        pairs = re.findall(r'\[0x([0-9A-Fa-f]+)\] = "(ITEM_\w+)"', block)
        self.assertEqual(len(pairs), 4, 'INSPECT.BAG lists the four passive items')
        for value, name in pairs:
            self.assertEqual(int(value, 16), items.get(name), name)


class TestNoBlanketEmulatorKill(unittest.TestCase):
    """Scenarios run FOUR AT A TIME by default since #310, so anything run.sh kills by name
    kills its siblings."""

    def source(self):
        with open(RUN_SH, encoding='utf-8') as fh:
            return fh.read()

    def test_run_sh_never_kills_every_mgba(self):
        """`pkill -9 -i mgba` at startup SIGKILLed three scenarios in one gate run: each was
        executing while the pool dispatched the next, and the newcomer killed it. The kill has
        to name THIS scenario's process, never the program."""
        for line in self.source().splitlines():
            stripped = line.strip()
            if stripped.startswith('#') or 'pkill' not in stripped:
                continue
            self.assertNotRegex(
                stripped, r'pkill[^|]*\s-i\s',
                'run.sh kills mGBA by NAME, which reaches other scenarios: %s' % stripped)
            self.assertIn('playtest-', stripped,
                          'a kill in run.sh must be scoped to one scenario: %s' % stripped)

    def test_the_leftover_kill_is_still_there(self):
        """Scoped, not deleted: a leftover emulator from an interrupted run of the SAME
        scenario still has to be cleared, or it holds the ROM the next run wants."""
        self.assertIn('pkill', self.source())


if __name__ == '__main__':
    unittest.main()
