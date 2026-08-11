#!/usr/bin/env python3
"""Regression coverage for state-driven playtest scenario wiring."""
import os
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
        # #232. A wait for the map to become playable spans whole cutscenes, and no fixed
        # budget fits every one -- the ch01 opening outran 300 frames and logged a fault
        # on a chapter the scenario went on to clear. So the event engine running must not
        # burn the budget, while a genuinely wedged engine still fails closed here rather
        # than at run.sh's wall-clock deadline.
        body = _block(_read_harness(), 'local function awaitControllerState(',
                      '\n-- Select unit at')
        self.assertIn('std_event', body, 'event-engine progress must be recognised')
        self.assertIn('STALL_CEILING', body, 'the wait must still terminate on its own')
        self.assertIn('fail:state-timeout', body)


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
        body = _block(harness, 'scenarios.ch05recruit = function()',
                      '\n-- Park an unexhausted blue unit')
        self.assertIn('eruptionBoxes', body,
                      'the recruit gate would hang before Sahnar LOADs if it never advances '
                      'Ravisin\'s newly visible warning')
        self.assertIn('dialogue_wait', body)
        self.assertIn('advance_dialogue', body)
        self.assertIn('eruption warning showed %d boxes', body,
                      'the gate must distinguish the locked four-box scene from merely '
                      'reaching turn 2')

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

        matrix = os.path.join(REPO, 'tools/playtest/matrix.yaml')
        with open(matrix, encoding='utf-8') as source:
            registry = source.read()
        self.assertIn('  recordch05ravisindeath:\n'
                      '    rom: ch05boot\n'
                      '    host_chapter: 6\n'
                      '    kind: record\n', registry)

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


if __name__ == '__main__':
    unittest.main()
