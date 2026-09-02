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
        # main function sits near Lua's 200-local ceiling. A few new top-level constants
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


class TestChooseAttackContract(unittest.TestCase):
    """#232. chooseAttack is the shared attack path -- every combat scenario in the
    campaign routes through it -- so both of its waits have to hold in every mode the
    scenarios actually run in."""

    def test_confirm_target_postcondition_is_not_battle_animation_only(self):
        # gProc_ekrBattle (observed as procs.battle) is the battle ANIMATION proc. Any
        # scenario that called pokeFastConfig() runs map combat, where it never spawns
        # -- so a postcondition of `after.procs.battle ~= nil` alone can never hold and
        # the attack fails despite having resolved (ch04packmath/ch04snag/clear_ch04).
        body = _block(_read_harness(), 'local function chooseAttack(',
                      '-- March a unit toward')
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
        self.assertIn('advance_dialogue', body)
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
        self.assertEqual(harness.count('endTurn(nil, advanced)'), 2,
                         'clear_ch02 and recordchain must both pass the win predicate')

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
        # off-map unit out of the lists that drive the cursor.
        harness = _read_harness()
        body = _block(harness, 'local function unitAt(', '\nlocal function findUnit')
        self.assertIn('rs8(a + 0x10)', body, 'xPos is s8')
        self.assertIn('rs8(a + 0x11)', body, 'yPos is s8')
        self.assertNotIn('ru8(a + 0x10)', body, 'the unsigned read is the bug')
        live = _block(harness, 'local function liveEnemies(', '\n\n')
        self.assertIn('onMap', live, 'a target list must not offer an off-map unit')

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
        self.assertIn('dialogue_wait', body)
        self.assertIn('advance_dialogue', body)
        self.assertIn('eruption warning showed %d boxes', body,
                      'the gate must distinguish the locked four-box scene from merely '
                      'reaching turn 2')

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

    def test_recordch05eruption_records_only_the_turn_two_scene(self):
        harness = _read_harness()
        self.assertIn('scenarios.recordch05eruption = function()', harness)
        body = _block(harness, 'scenarios.recordch05eruption = function()',
                      '\n-- Park an unexhausted blue unit')
        self.assertIn('endTurn()', body)
        self.assertIn('recordCutscene({', body)
        self.assertIn('turn() >= 2', body)
        self.assertIn('not procActive(SYM.ProcScr_StdEventEngine)', body)

    def test_recordch05ravisindeath_records_one_real_boss_death_box(self):
        harness = _read_harness()
        self.assertIn('scenarios.recordch05ravisindeath = function()', harness)
        body = _block(harness, 'scenarios.recordch05ravisindeath = function()',
                      '\n-- ch04cottage')
        self.assertIn('bootToMap()', body)
        self.assertIn('pokeFrail(boss)', body)
        self.assertIn('chooseAttack(', body)
        self.assertIn('recordCutscene({', body)
        self.assertIn('shotEvery = 1', body,
                      'per-frame capture must preserve the death box before advancing it')
        self.assertIn('controllerState() == "dialogue_wait"', body)
        self.assertIn('eventFlag(2)', body,
                      'the recorder must preserve the DefeatBoss flag as its terminal proof')
        self.assertIn('boxes == 1', body,
                      'the focused proof must require exactly the one locked death box')

        # The row is DERIVED from ch05's chapter YAML now (#314), so this asserts the
        # resolved row rather than matrix.yaml's text: it checks the value the runner
        # actually uses, and it keeps holding wherever the declaration lives.
        sys.path.insert(0, os.path.join(REPO, 'tools', 'playtest'))
        import matrix as mx
        row = mx.Manifest.load().resolve('recordch05ravisindeath')
        self.assertEqual((row.rom, row.host_chapter, row.kind), ('ch05boot', 6, 'record'))

    def test_ch04snag_accepts_the_native_fallen_snag_crossing(self):
        harness = _read_harness()
        body = _block(harness, 'scenarios.ch04snag = function()', '\n-- attackprobe')
        self.assertIn('local T_CROSSING = 0x34', body,
                      'the painted center metatile uses TERRAIN_BRIDGE_SNAG; the playtest '
                      'must not retain the old generic-bridge workaround')

    def test_moose_recorder_wires_fast_setup_to_guaranteed_cleanup(self):
        with open(HARNESS, encoding='utf-8') as source:
            harness = source.read()

        start = harness.index('scenarios.recordch04moose = function()')
        end = harness.index('\n-- ch04moose:', start)
        recorder = harness[start:end]

        fast = recorder.index('pokeFastConfig()')
        boot = recorder.index('bootToMap()')
        march = recorder.index('marchPartyToward(')
        self.assertLess(fast, boot)
        self.assertLess(boot, march)
        self.assertIn('return false, "never reached the ch04 map"', recorder)
        self.assertIn('return false, "party never triggered the moose sighting"', recorder)
        self.assertIn('afterPre = pokeNormalConfig', recorder)


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
