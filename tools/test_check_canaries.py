#!/usr/bin/env python3
"""Every registered check proves it can FAIL (#407).

A guard that passes by checking nothing is this repo's most repeated bug: #405's camera
check read a key no layout carries and never found a map; #401's walk skipped every `MS_*`
scene; the fingerprint's first cut passed in 1.1s by doing nothing (ADRs 0287, 0296). Each
was caught by a reviewer, one at a time. This makes "watched failing" structural.

Every entry in `check.CHECKS` has a CANARY here: the REAL check, run against the real tree
with ONE input doctored into a known-bad state, which must produce a named failure. The
doctoring happens at the read -- `open()` returns a changed text for one path -- so the
canary exercises the whole guard, input wiring included, which is exactly where #405's bug
lived. A helper fed a bad string would have passed that canary.

A check whose input is not a file read (a subprocess, a git probe, a manifest object) is
doctored at the narrowest seam that still leaves its logic running: its path global, its git
probe, its allowlist. Where even that is impossible, it goes in UNCANARIED with the reason,
and a reason is a claim a reviewer can challenge.

`check.check_every_gate_has_a_canary` reads the two registries below by AST (the lean CI job
cannot import this file's dependencies), so a new check without a canary fails the build.

Run:  python3 tools/test_check_canaries.py
"""
import builtins
import contextlib
import io
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check                                                         # noqa: E402
from inject import hosts                                             # noqa: E402
from inject import source                                            # noqa: E402

REPO = check.REPO
CHAPTERS = 'campaigns/rime-of-the-frostmaiden/chapters/'
CH01 = CHAPTERS + 'ch01-the-iron-trail.yaml'
CH02 = CHAPTERS + 'ch02-cold-welcome.yaml'
CH06 = CHAPTERS + 'ch06-the-maer-monster.yaml'
BC = 'tools/build_campaign.py'
HARNESS = 'tools/playtest/harness.lua'
# A guarded tool (tools/**, not a test, not the injector) to plant a bad line in.
TOOL = 'tools/map_donor.py'
HAS_DECOMP = os.path.isdir(os.path.join(REPO, 'fireemblem8u', 'src'))
HAS_LUA = shutil.which('lua') is not None


def _clear_read_caches():
    """`inject.source` memoises by mtime, and a doctored read changes no mtime."""
    for fn in (source._read, source._parse, source._lines, source._code_text,
               source._definitions):
        fn.cache_clear()
    hosts._literal_cache.clear()


@contextlib.contextmanager
def doctored(edits):
    """Serve `edits[rel](real_text)` for every READ of that repo path, and nothing else.

    Asserts on exit, OUTSIDE the check, that every target was read and actually changed. A
    miss is recorded rather than raised inside `open()`: several checks swallow a read error
    (`_chapters()` skips a file it cannot parse), so an error raised there would come back as
    "the check stayed silent" -- blaming a working check for a canary whose anchor moved.
    And "was read" is half the proof: a check that never opens the file it is supposed to
    guard is exactly the vacuous pass this file exists to catch."""
    targets = {os.path.realpath(os.path.join(REPO, rel)): fn for rel, fn in edits.items()}
    served, unchanged = set(), set()
    real_open = builtins.open

    def fake_open(file, mode='r', *args, **kwargs):
        if (isinstance(file, (str, os.PathLike)) and not set(mode) & set('wax+')
                and os.path.realpath(os.fspath(file)) in targets):
            path = os.path.realpath(os.fspath(file))
            with real_open(file, 'r', encoding='utf-8') as fh:
                text = fh.read()
            new = targets[path](text)
            (unchanged if new == text else served).add(path)
            return io.BytesIO(new.encode('utf-8')) if 'b' in mode else io.StringIO(new)
        return real_open(file, mode, *args, **kwargs)

    _clear_read_caches()
    try:
        with mock.patch.object(builtins, 'open', fake_open), \
                mock.patch.object(io, 'open', fake_open):
            yield
    finally:
        _clear_read_caches()
    moved = sorted(os.path.relpath(p, REPO) for p in unchanged - served)
    unread = sorted(os.path.relpath(p, REPO) for p in set(targets) - served - unchanged)
    if moved:
        raise AssertionError('canary doctoring changed nothing in %s -- the anchor it edits has '
                             'moved; fix the canary, the check is not at fault' % moved)
    if unread:
        raise AssertionError('the check never READ %s, the input this canary doctors -- either '
                             'the canary targets the wrong file or the check stopped reading '
                             'its own input' % unread)


class _Captured(io.StringIO):
    """stdout as a check sees it; compileall asks for `.encoding` when it reports."""
    encoding = 'utf-8'


def run(check_fn, **kwargs):
    """(fail list, printed output) of one real check."""
    fail, out = [], _Captured()
    with contextlib.redirect_stdout(out):
        check_fn(fail, **kwargs)
    return fail, out.getvalue()


def sub1(pattern, repl, flags=re.M):
    """A doctoring that rewrites the FIRST match of `pattern`."""
    return lambda text: re.sub(pattern, repl, text, count=1, flags=flags)


def append(tail):
    return lambda text: text + tail


def _tmp_tree(files):
    tmp = tempfile.mkdtemp()
    for rel, body in files.items():
        path = os.path.join(tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(body)
    return tmp


# ── the canaries: each returns (fail, printed) from the REAL check, doctored ─────────────

def c_skip_claims():
    with doctored({'tools/test_check_chapter_schema.py':
                   sub1(r'def test_personal_line_routes_gate_passes\(', 'def test_renamed_away(')}):
        return run(check.check_skip_claims_name_a_live_test)


def c_python_compiles():
    tmp = _tmp_tree({'tools/broken.py': 'def (:\n'})
    try:
        with mock.patch.object(check, 'REPO', tmp):
            return run(check.check_python_compiles)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def c_tests_pass():
    import run_tests
    with mock.patch.object(run_tests, 'run',
                           lambda *a, **k: [('tools/test_canary.py', 'FAILED (failures=1)')]):
        return run(check.check_tests_pass)


def c_lua_chunks_load():
    tmp = _tmp_tree({'canary_broken.lua': 'local x = (\n'})
    try:
        with mock.patch.object(check, 'LUA_CHUNKS', (os.path.join(tmp, 'canary_broken.lua'),)):
            return run(check.check_lua_chunks_load)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def c_harness_local_ratchet():
    with doctored({HARNESS: lambda t: 'local canary_extra_local = 1\n' + t}):
        return run(check.check_harness_local_ratchet)


def c_lua_local_headroom():
    tmp = _tmp_tree({'full.lua': ''.join('local v%d = %d\n' % (i, i) for i in range(200))})
    try:
        return run(check.check_lua_local_headroom, paths=[os.path.join(tmp, 'full.lua')])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def c_hosted_chapters_declared():
    with doctored({BC: append('\n\ndef inject_ch42(campaign):\n    pass\n')}):
        return run(check.check_hosted_chapters_declared)


def c_yaml_parses():
    with doctored({CH01: append('\ncanary: [unclosed\n')}):
        return run(check.check_yaml_parses)


def c_chapter_status():
    with doctored({CH01: sub1(r'^status:.*$', 'status: someday')}):
        return run(check.check_chapter_status)


def c_personal_line_routes():
    import build_campaign as bc
    uid = sorted(uid for _yaml, uid in bc.RAW_PID_PERSONAL_SOURCES.values())[0]
    edits = {}
    for rel in sorted(f for f in os.listdir(os.path.join(REPO, CHAPTERS)) if f.endswith('.yaml')):
        with open(os.path.join(REPO, CHAPTERS, rel), encoding='utf-8') as f:
            if re.search(r'id:\s*%s\b' % re.escape(uid), f.read()):
                edits[CHAPTERS + rel] = sub1(r'(id:\s*)%s\b' % re.escape(uid),
                                             r'\g<1>%s-canary' % uid)
    with doctored(edits):
        return run(check.check_personal_line_injection_routes)


def c_deployment_schema():
    with doctored({CH01: append('\ndeploy_limit: 5\n')}):
        return run(check.check_chapter_deployment_schema)


def c_cached_steps():
    # A boot-flag reader hoisted above the cached battle-anim step.
    with doctored({BC: sub1(r'^def main\(\):\n', 'def main():\n    inject_canary(args.test_chapter)\n')}):
        return run(check.check_cached_steps_are_config_invariant)


def c_tile_changes():
    with doctored({BC: append('\n\ndef inject_ch42(campaign):\n'
                              '    _inject_tile_changes(campaign)\n'
                              '    _retarget_host_chapter(campaign)\n')}):
        return run(check.check_tile_changes_outlive_the_retarget)


def c_injection_order():
    with doctored({BC: sub1(r'^def main\(\):\n', 'def main():\n    inject_ch05(campaign)\n')}):
        return run(check.check_injection_order)


def c_one_reader():
    with doctored({TOOL: append("\nX = open(os.path.join(REPO, 'tools', 'build_campaign.py'))\n")}):
        return run(check.check_injector_source_has_one_reader)


def c_recordenemy():
    with doctored({HARNESS: lambda t: re.sub(r'(\["[\w-]+"\]\s*=\s*)0x[0-9a-fA-F]+',
                                             r'\g<1>0xFFFF', t)}):
        return run(check.check_recordenemy_knows_every_raw_pid)


def c_gate_window():
    sys.path.insert(0, os.path.join(REPO, 'tools', 'playtest'))
    import matrix as mx
    # Every gate scenario boots a slot outside the window -- what a stale gate looks like.
    with mock.patch.object(mx, '_boot_slot', lambda *a, **k: 99):
        return run(check.check_gate_chapter_window)


def c_chapter_lua_facts():
    with doctored({'tools/playtest/ch06.lua': sub1(r'\bx\s*=\s*\d+', 'x = 63')}):
        return run(check.check_chapter_lua_facts)


def c_documented_tileset():
    with doctored({CH01: sub1(r'^(\s+tileset:\s*)\S+', r'\g<1>canary-tileset')}):
        return run(check.check_documented_tileset)


def c_sidecar_routes():
    with doctored({'tools/map_placement_preview.py':
                   sub1(r"^(MAPS\s*=\s*os\.path\.join\(CAMPAIGN,\s*')[^']+'", r"\g<1>canary-maps'")}):
        return run(check.check_map_sidecar_routes_agree)


def c_rescue_targets():
    with doctored({CH06: sub1(r'^rescue_pursuers:\n(- id: .*\n)+', 'rescue_pursuers: []\n')}):
        return run(check.check_rescue_targets)


def c_rescue_fuse_forecast():
    with doctored({CH06: sub1(r'^(rescue_boats:\n- id: boat-east\n)', r'\g<1>  declared_fuse: 99\n')}):
        return run(check.check_rescue_fuse_forecast)


def c_decomp_git_env():
    with doctored({TOOL: append("\nsubprocess.run(['git', '-C', DECOMP, 'status'])\n")}):
        return run(check.check_decomp_git_calls_strip_the_env)


def c_shadowed_definitions():
    with doctored({TOOL: append('\n\ndef our_layout_labels():\n    pass\n')}):
        return run(check.check_no_shadowed_definitions)


def c_rom_configs():
    matrix = open(os.path.join(REPO, 'tools/playtest/matrix.yaml'), encoding='utf-8').read()
    block = re.search(r'^rom_configs:\n(.*?)(?=^\S|\Z)', matrix, re.S | re.M).group(1)
    env = sorted(set(re.findall(r'^\s+([A-Z][A-Z0-9_]*):\s', block, re.M)))[0]
    with doctored({'Makefile': lambda t: t.replace('$(%s)' % env, '$(CANARY)')}):
        return run(check.check_rom_configs_reach_the_build)


def c_playtest_matrix():
    with doctored({HARNESS: sub1(r'^(scenarios\.smoke = )', r'scenarios.canary_unlisted = function() end\n\g<1>')}):
        return run(check.check_playtest_matrix)


def c_verdict_guarded():
    with mock.patch.object(check, 'BLIND_PRESS_ALLOWED', set()):
        return run(check.check_verdict_scenarios_are_guarded)


def c_declared_cases():
    with doctored({CH02: sub1(r'visit: \{x: 1, y: 12', 'visit: {x: 2, y: 12')}):
        return run(check.check_declared_cases)


def c_symbol_addresses():
    with doctored({'tools/playtest/controller.lua': append('\nlocal canary = 0x02001234\n')}):
        return run(check.check_no_hardcoded_symbol_addresses)


def c_tool_refs():
    with doctored({TOOL: append('\n# see tools/canary_nonexistent.py\n')}):
        return run(check.check_tool_refs_exist)


def c_one_tileset_default():
    import map_tileset_tool
    with doctored({TOOL: append("\nX = {}.get('tileset', %r)\n" % map_tileset_tool.DEFAULT_TILESET)}):
        return run(check.check_one_tileset_default)


def c_no_chapter_list():
    with doctored({'campaigns/rime-of-the-frostmaiden/campaign.yaml': append('\nchapters: []\n')}):
        return run(check.check_campaign_declares_no_chapter_list)


def c_dead_concepts():
    with doctored({TOOL: append('\n# generated by build-campaign.ts\n')}):
        return run(check.check_no_dead_concepts)


def c_generated_indexes():
    with doctored({'docs/CHAPTERS.md': append('\ncanary hand edit\n')}):
        return run(check.check_generated_indexes_fresh)


def c_engine_guards():
    with doctored({'tools/inject/engine_hooks.py':
                   sub1(r'def _patch_terrain_name_guard\(', 'def _patch_terrain_name_guard_gone(')}):
        return run(check.check_engine_guards_present)


def c_purple_bank():
    def drop_first(text):
        start = text.index('PURPLE_BANK_BLANKERS = (')
        head, tail = text[:start], text[start:]
        return head + re.sub(r'^(\s*\()(\w+)_C,', r'\g<1>\g<2>_CANARY_C,', tail, count=1,
                             flags=re.M)
    with doctored({BC: drop_first}):
        return run(check.check_purple_bank_blankers_known)


def c_engine_agnostic():
    name = sorted(check._campaign_character_ids())[0]
    with doctored({'tools/inject/engine_hooks.py': append('\n# %s\n' % name)}):
        return run(check.check_engine_campaign_agnostic)


def c_save_layout():
    name = sorted(check.PINNED_SAVE_LAYOUT)[0]
    with doctored({'fireemblem8u/include/bmsave.h':
                   lambda t: re.sub(r'\b%s\b' % re.escape(name), name + '_CANARY', t)}):
        return run(check.check_save_layout_stable)


def c_every_test_runs():
    with doctored({'tools/test_map_donor.py':
                   append('\n\nclass CanaryAfterMain(unittest.TestCase):\n'
                          '    def test_never_runs(self):\n        pass\n')}):
        return run(check.check_every_test_actually_runs)


def c_wrap_widths():
    # A character count where a pixel budget belongs: what shipped in ch05's moose beat.
    with doctored({TOOL: append('\n_wrap_fe_lines("canary text", width=29)\n')}):
        return run(check.check_wrap_widths_are_pixels)


def c_vanilla_reads():
    with doctored({TOOL: append("\nX = open('fireemblem8u/src/uiarena.c')\n")}):
        return run(check.check_vanilla_reads_come_from_head)


def c_message_literals():
    with doctored({BC: append('\n\ndef canary_helper():\n'
                              '    set_message_body(0x9FF, 0x9FF, "canary")\n')}):
        return run(check.check_message_literals_are_registered)


def c_handoff_only_on_main():
    answers = {('rev-parse', '--abbrev-ref', 'HEAD'): 'feat/canary',
               ('rev-parse', '--verify', '--quiet', 'origin/main'): 'abc123',
               ('merge-base', 'HEAD', 'origin/main'): 'abc123',
               ('diff', '--cached', '--name-only'): check.HANDOFF_FILE}
    with mock.patch.dict(os.environ, {'GITHUB_HEAD_REF': '', 'GITHUB_BASE_REF': ''}), \
            mock.patch.object(check, '_git', lambda args: answers.get(tuple(args), '')):
        return run(check.check_handoff_only_on_main)


def c_lane_ownership():
    with mock.patch.object(check, '_current_lane', lambda: 'pipeline'), \
            mock.patch.object(check, '_changed_files', lambda *a: [CH01]):
        return run(check.check_lane_ownership)


def c_every_gate_registered():
    def check_canary_unregistered(fail):
        pass
    check_canary_unregistered.__module__ = check.__name__
    with mock.patch.dict(check.__dict__, {'check_canary_unregistered': check_canary_unregistered}):
        return run(check.check_every_gate_is_registered)


def c_workflow_filters():
    with doctored({'.github/workflows/build.yml':
                   sub1(r'(paths-ignore:\n)', r"\g<1>      - 'canary-only-on-push.md'\n")}):
        return run(check.check_build_workflow_filters_agree)


def c_decision_records():
    with doctored({'docs/decisions/0297-the-injector-is-every-file-of-it-and-has-one-source-reader.md':
                   sub1(r'^id: 297$', 'id: 296')}):
        return run(check.check_decision_records_wellformed)


def c_decision_citations():
    with doctored({TOOL: append('\n# see decisions.md -> "A canary record title that resolves nowhere at all"\n')}):
        return run(check.check_decision_citations_resolve)


def c_every_gate_has_a_canary():
    # This very file, read as the guard reads it, with one registration struck out.
    with doctored({'tools/test_check_canaries.py':
                   sub1(r"^    'check_build_workflow_filters_agree': \(.*\n", '')}):
        return run(check.check_every_gate_has_a_canary)


# check name -> (canary, a substring its failure (or advisory print) must contain, needs)
# `needs` names what the canary requires to run at all; without it the test SKIPS and says so.
CANARIES = {
    'check_skip_claims_name_a_live_test': (c_skip_claims, 'test_personal_line_routes_gate_passes', None),
    'check_python_compiles': (c_python_compiles, 'does not compile', None),
    'check_tests_pass': (c_tests_pass, 'unit tests fail', 'decomp'),
    'check_lua_chunks_load': (c_lua_chunks_load, 'canary_broken.lua', 'lua'),
    'check_harness_local_ratchet': (c_harness_local_ratchet, 'up from the ratcheted', None),
    'check_lua_local_headroom': (c_lua_local_headroom, 'full.lua', 'lua'),
    'check_hosted_chapters_declared': (c_hosted_chapters_declared, 'inject_ch42', None),
    'check_yaml_parses': (c_yaml_parses, 'YAML does not parse', None),
    'check_chapter_status': (c_chapter_status, 'someday', None),
    'check_personal_line_injection_routes': (c_personal_line_routes, 'no chapter fields', 'decomp'),
    'check_chapter_deployment_schema': (c_deployment_schema, 'deploy_limit', None),
    'check_cached_steps_are_config_invariant': (c_cached_steps, 'injection cache', None),
    'check_tile_changes_outlive_the_retarget': (c_tile_changes, 'inject_ch42', None),
    'check_injection_order': (c_injection_order, 'must run before', None),
    'check_injector_source_has_one_reader': (c_one_reader, 'map_donor.py', None),
    'check_recordenemy_knows_every_raw_pid': (c_recordenemy, 'pid 0xFFFF', None),
    'check_gate_chapter_window': (c_gate_window, 'host slot 99', None),
    'check_chapter_lua_facts': (c_chapter_lua_facts, '(63,12)', None),
    'check_documented_tileset': (c_documented_tileset, 'canary-tileset', 'decomp'),
    'check_map_sidecar_routes_agree': (c_sidecar_routes, 'disagree', None),
    'check_rescue_targets': (c_rescue_targets, 'neither a declared pursuer', 'decomp'),
    'check_rescue_fuse_forecast': (c_rescue_fuse_forecast, 'declared_fuse 99', 'decomp'),
    'check_decomp_git_calls_strip_the_env': (c_decomp_git_env, 'map_donor.py', None),
    'check_no_shadowed_definitions': (c_shadowed_definitions, 'our_layout_labels', None),
    'check_rom_configs_reach_the_build': (c_rom_configs, 'Makefile', None),
    'check_playtest_matrix': (c_playtest_matrix, 'canary_unlisted', None),
    'check_verdict_scenarios_are_guarded': (c_verdict_guarded, 'press', None),
    'check_declared_cases': (c_declared_cases, 'visit', None),
    'check_no_hardcoded_symbol_addresses': (c_symbol_addresses, '0x02001234', None),
    'check_tool_refs_exist': (c_tool_refs, 'canary_nonexistent', None),
    'check_one_tileset_default': (c_one_tileset_default, 'map_donor.py', None),
    'check_campaign_declares_no_chapter_list': (c_no_chapter_list, 'campaign.yaml', None),
    'check_no_dead_concepts': (c_dead_concepts, 'build-campaign', None),
    'check_generated_indexes_fresh': (c_generated_indexes, 'CHAPTERS.md', None),
    'check_engine_guards_present': (c_engine_guards, '_patch_terrain_name_guard', None),
    'check_purple_bank_blankers_known': (c_purple_bank, 'PURPLE_BANK_BLANKERS', 'decomp'),
    'check_engine_campaign_agnostic': (c_engine_agnostic, 'engine_hooks.py', None),
    'check_save_layout_stable': (c_save_layout, 'not found', 'decomp'),
    'check_every_test_actually_runs': (c_every_test_runs, 'CanaryAfterMain', None),
    'check_wrap_widths_are_pixels': (c_wrap_widths, 'map_donor.py', None),
    'check_vanilla_reads_come_from_head': (c_vanilla_reads, 'uiarena', None),
    'check_message_literals_are_registered': (c_message_literals, 'BARE LITERAL', None),
    'check_handoff_only_on_main': (c_handoff_only_on_main, 'staged for commit', None),
    'check_lane_ownership': (c_lane_ownership, CH01, None),
    'check_every_gate_is_registered': (c_every_gate_registered, 'check_canary_unregistered', None),
    'check_build_workflow_filters_agree': (c_workflow_filters, 'canary-only-on-push', None),
    'check_decision_records_wellformed': (c_decision_records, 'declares id 296', None),
    'check_decision_citations_resolve': (c_decision_citations, 'canary record title', None),
    'check_every_gate_has_a_canary': (c_every_gate_has_a_canary, 'check_build_workflow_filters_agree has no canary', None),
}

# check name -> why it cannot carry a canary. Empty is the goal; every entry is a claim.
UNCANARIED = {}

NEEDS = {'decomp': (HAS_DECOMP, 'fireemblem8u submodule not checked out'),
         'lua': (HAS_LUA, 'no lua on PATH')}


# The canaries are 49 real check runs, ~41s in one process. `run_tests.py` runs FILES in
# parallel, so they are dealt across SHARDS files -- this one and test_check_canaries_shard*.py
# -- or this file alone would set the pre-commit hook's wall time (45s -> 63s, measured).
SHARDS = 3


def shard(k):
    """Every k-th canary (by name), so each shard file runs a third of them."""
    return sorted(CANARIES)[k::SHARDS]


class CanariesFire(unittest.TestCase):
    """One subTest per check: the doctored run must report the named failure."""
    SHARD = 0

    def test_every_canary_in_this_shard_fires(self):
        for name in shard(self.SHARD):
            canary, expect, needs = CANARIES[name]
            with self.subTest(check=name):
                if needs and not NEEDS[needs][0]:
                    self.skipTest('%s: %s' % (name, NEEDS[needs][1]))
                fail, printed = canary()
                said = '\n'.join(fail) + '\n' + printed
                self.assertTrue(fail or printed.strip(),
                                '%s stayed SILENT against its canary -- it cannot fail' % name)
                self.assertIn(expect, said,
                              '%s reported something, but not the planted fault:\n%s'
                              % (name, said[:2000]))


class TheHarnessBlamesTheRightThing(unittest.TestCase):
    """A canary that cannot plant its fault must say so -- not report the check as silent."""

    def test_a_moved_anchor_is_reported_as_the_canary_s_fault(self):
        # check_chapter_status reads chapters through _chapters(), which SWALLOWS a read error.
        with self.assertRaisesRegex(AssertionError, 'anchor it edits has moved'):
            with doctored({CH01: sub1(r'^no-such-anchor$', 'x')}):
                run(check.check_chapter_status)

    def test_a_check_that_never_reads_the_doctored_file_is_reported(self):
        with self.assertRaisesRegex(AssertionError, 'never READ'):
            with doctored({'docs/CLASSES.md': append('x')}):
                run(check.check_chapter_status)


class TheRegistryIsComplete(unittest.TestCase):

    def test_every_canary_lands_in_exactly_one_shard_file(self):
        dealt = [n for k in range(SHARDS) for n in shard(k)]
        self.assertEqual(sorted(CANARIES), sorted(dealt))
        here = os.path.dirname(os.path.abspath(__file__))
        for k in range(1, SHARDS):
            path = os.path.join(here, 'test_check_canaries_shard%d.py' % k)
            self.assertTrue(os.path.isfile(path), 'shard %d has no file, so it never runs' % k)
            with open(path, encoding='utf-8') as f:
                self.assertIn('SHARD = %d' % k, f.read())

    def test_every_registered_check_has_a_canary_or_a_reason(self):
        names = {c.__name__ for c in check.CHECKS}
        missing = names - set(CANARIES) - set(UNCANARIED)
        self.assertEqual(set(), missing)

    def test_nothing_is_registered_twice_or_for_a_check_that_does_not_exist(self):
        names = {c.__name__ for c in check.CHECKS}
        self.assertEqual(set(), set(CANARIES) & set(UNCANARIED))
        self.assertEqual(set(), (set(CANARIES) | set(UNCANARIED)) - names)


if __name__ == '__main__':
    unittest.main()
