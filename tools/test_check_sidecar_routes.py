"""Regression tests for check_map_sidecar_routes_agree -- #373.

Three places answer "which sidecar JSON belongs to this chapter", by three different routes:

  * the GATE derives it from the chapter YAML's `map.file` (`check._chapter_sidecar`);
  * the BUILD gets its stem from the `CHxx_LAYOUT` constants and never reads `map.file` at all;
  * the PREVIEW takes `basename(map.file)` against `map_placement_preview`'s own campaign root.

They agree today. Nothing made them agree. If they drifted, `check_documented_tileset` would
either skip in silence (looking for a sidecar at a path that does not exist) or -- worse --
assert that the YAML agrees with a sidecar the cartridge never loads. That is the
"documentation nothing reads" failure #371 closed for the tileset FIELD, reappearing one level
up in how the file is LOCATED.

**The guard checks that they agree rather than making one of them authoritative**, and #371's
own history is the argument for it: the first attempt at that bug picked the wrong winner (the
YAML) and would have shipped a preview of a tileset the game never loads. Right answers for a
wrong reason are only visible if something compares the two.

What these tests hold, beyond the happy path:

  * the COVERED SET is assertable. A guard that quietly compares nothing also passes, and this
    repo has shipped exactly that (`_tile_change_injectors_seen` exists for the same reason).
  * a chapter whose map is painted but not yet HOSTED is a legitimate skip, not a failure --
    ch06 lived in that state from #331 until #364, and a guard that reds the build during a
    normal authoring window gets bypassed.
  * an injector the guard cannot attribute to a chapter is REPORTED, not skipped, because from
    outside those two are the same silence.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check

BUILD_SRC = open(os.path.join(check.REPO, 'tools', 'build_campaign.py'),
                 encoding='utf-8').read()
PREVIEW_SRC = open(os.path.join(check.REPO, 'tools', 'map_placement_preview.py'),
                   encoding='utf-8').read()
HOSTED = ['prologue', 'ch01', 'ch02', 'ch03', 'ch04', 'ch05', 'ch06']


def _rows(text=None, chapters=None, preview=None, hosted=None):
    return check._sidecar_routes(
        BUILD_SRC if text is None else text,
        PREVIEW_SRC if preview is None else preview,
        list(check._chapters()) if chapters is None else chapters,
        HOSTED if hosted is None else hosted)


def _violations(**kw):
    return check._sidecar_route_violations(_rows(**kw))


def _chapters_with(short_prefix, mutate):
    """The live chapter set with one chapter's dict replaced by `mutate(d)`."""
    out = []
    for rel, d in check._chapters():
        if str(d.get('id', '')).startswith(short_prefix):
            d = mutate(d)
        out.append((rel, d))
    return out


class TheThreeRoutesAgree(unittest.TestCase):

    def test_the_live_tree_agrees_for_every_chapter(self):
        fail = []
        check.check_map_sidecar_routes_agree(fail)
        self.assertEqual(fail, [])

    def test_every_hosted_chapter_is_actually_compared_on_all_three_routes(self):
        """A guard that compares nothing passes too, so the covered set is asserted."""
        compared = [r['short'] for r in _rows() if len(r['routes']) == 3]
        self.assertEqual(compared, ['ch00', 'ch01', 'ch02', 'ch03', 'ch04', 'ch05', 'ch06'])

    def test_a_build_registering_another_chapters_layout_is_caught(self):
        """The divergence itself: the build loads one map, the gate grades another."""
        doctored = BUILD_SRC.replace(
            '_register_chapter_map(maps_dir, CH02_LAYOUT',
            '_register_chapter_map(maps_dir, CH04_LAYOUT')
        self.assertNotEqual(doctored, BUILD_SRC)
        bad = _violations(text=doctored)
        self.assertTrue(bad)
        self.assertIn('ch02', bad[0])
        self.assertIn('ch04-lonelywood-forest.json', bad[0])

    def test_a_yaml_map_file_that_drifts_from_the_registered_layout_is_caught(self):
        """The same divergence from the other side -- someone renames `map.file`."""
        chapters = _chapters_with(
            'ch05', lambda d: dict(d, map=dict(d['map'], file='maps/ch05-renamed-by-hand.mar')))
        bad = _violations(chapters=chapters)
        self.assertTrue(bad)
        self.assertIn('ch05', bad[0])

    def test_a_nested_map_file_the_preview_flattens_is_caught(self):
        """`terrain_grid` resolves the stem from `basename(map.file)`, so a `map.file` with a
        subdirectory in it silently loses the directory -- the third route drifting while the
        other two still agree with each other."""
        chapters = _chapters_with(
            'ch03',
            lambda d: dict(d, map=dict(d['map'], file='maps/caves/ch03-the-termalaine-mine.mar')))
        bad = _violations(chapters=chapters)
        self.assertTrue(bad)
        self.assertIn('ch03', bad[0])
        self.assertIn('preview', bad[0])

    def test_a_painted_but_unhosted_chapter_is_skipped_with_a_reason(self):
        """ch06 was in exactly this state from #331 to #364. A guard that reds the build
        through a normal authoring window is a guard that gets bypassed."""
        doctored = BUILD_SRC.replace(
            '_register_chapter_map(maps_dir, CH06_LAYOUT',
            '_register_nothing(maps_dir, CH06_LAYOUT')
        self.assertNotEqual(doctored, BUILD_SRC)
        # ...and ch06 is not on the hosted list while it is in that state.
        hosted = [h for h in HOSTED if h != 'ch06']
        self.assertEqual(_violations(text=doctored, hosted=hosted), [])
        row = [r for r in _rows(text=doctored, hosted=hosted) if r['short'] == 'ch06'][0]
        self.assertIn('no injector', ' '.join(r for _, r in row['problems']) or row['note'])

    def test_an_injector_the_guard_cannot_attribute_is_reported_not_skipped(self):
        """From outside, "this guard skipped it" and "there was nothing to check" look the
        same. A registration it cannot name has to say so."""
        doctored = BUILD_SRC.replace('def inject_ch04(', 'def inject_ch04_stage_two(', 1)
        bad = _violations(text=doctored)
        self.assertTrue(bad)
        self.assertTrue(any('inject_ch04_stage_two' in b for b in bad), bad)

    def test_a_layout_constant_the_build_does_not_define_is_reported(self):
        doctored = BUILD_SRC.replace(
            '_register_chapter_map(maps_dir, CH01_LAYOUT',
            '_register_chapter_map(maps_dir, CHZZ_LAYOUT')
        bad = _violations(text=doctored)
        self.assertTrue(bad)
        self.assertTrue(any('CHZZ_LAYOUT' in b for b in bad), bad)

    def test_the_guard_is_registered_in_the_drift_gate(self):
        self.assertIn(check.check_map_sidecar_routes_agree, check.CHECKS)


class TheGuardCannotGoBlind(unittest.TestCase):
    """Every way this guard could pass while comparing nothing.

    Review of #378 found two of these live: the registration pattern hard-coded the
    caller's local name, so renaming it degraded every chapter to the intentional
    "painted but not hosted" skip and the gate returned zero violations over zero
    chapters; and a registration whose parsed chapter id matched no YAML reported that
    same false note. The hosted-chapter registry (`inject.hosts`, stdlib-only and
    already trusted by `check_hosted_chapters_declared`) is the floor that makes both
    loud: a HOSTED chapter owes all three routes.
    """

    def test_a_renamed_local_in_the_build_cannot_silently_empty_the_gate(self):
        """The pattern reads the LAYOUT argument, not the caller's variable name."""
        doctored = BUILD_SRC.replace('_register_chapter_map(maps_dir, ',
                                     '_register_chapter_map(map_root, ')
        self.assertNotEqual(doctored, BUILD_SRC)
        self.assertEqual(_violations(text=doctored), [])

    def test_a_pattern_that_matches_nothing_at_all_is_reported(self):
        """And if the call shape changes past recognising, the gate says so rather than
        comparing zero chapters and passing."""
        doctored = BUILD_SRC.replace('_register_chapter_map(', '_register_map_v2(')
        bad = _violations(text=doctored)
        self.assertTrue(bad)
        self.assertTrue(any('no chapter map registration' in b for b in bad), bad)

    def test_a_hosted_chapter_whose_id_stopped_matching_is_reported(self):
        """Renaming ch06's `id:` dropped its registration and reported the false note
        "painted but not hosted yet" -- the exact silence this guard refuses."""
        chapters = _chapters_with('ch06', lambda d: dict(d, id='ch6-the-maer-monster'))
        bad = _violations(chapters=chapters)
        self.assertTrue(bad)
        self.assertTrue(any('ch06' in b for b in bad), bad)

    def test_a_hosted_chapter_that_loses_its_map_block_is_reported(self):
        """One route left is not agreement -- and no other gate demands a `map:` block."""
        chapters = _chapters_with('ch04', lambda d: {k: v for k, v in d.items() if k != 'map'})
        bad = _violations(chapters=chapters)
        self.assertTrue(bad)
        self.assertTrue(any('ch04' in b for b in bad), bad)

    def test_a_preview_root_the_guard_cannot_read_is_reported(self):
        """The preview route exists to catch its hardcoded campaign root, so failing to
        find that root must not quietly drop the route."""
        doctored = PREVIEW_SRC.replace("CAMPAIGN = os.path.join(ROOT, 'campaigns/rime-of-the-frostmaiden')",
                                       "CAMPAIGN = _campaign_root()")
        self.assertNotEqual(doctored, PREVIEW_SRC)
        bad = _violations(preview=doctored)
        self.assertTrue(bad)
        self.assertTrue(any('preview' in b for b in bad), bad)


if __name__ == '__main__':
    unittest.main()
