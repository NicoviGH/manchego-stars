"""campaign_env.py: where a campaign ends, and ours' twin shops (#510 step 9 PR E)."""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import campaign_env as ce  # noqa: E402
import campaign_chapters  # noqa: E402
import difficulty  # noqa: E402
import inject.hosts  # noqa: E402


class VanillaIndex(unittest.TestCase):
    def test_chain_reads_the_decomp_enum(self):
        # Ch5x is CHAPTER_L_5X = 5, so Ch5 onward sits one past its number.
        got = [ce.vanilla_index(r) for r in difficulty.VANILLA_CHAIN]
        self.assertEqual(got, [0, 1, 2, 3, 4, 6, 7, 8, 9])

    def test_vanilla_ends_after_either_routes_last_chapter(self):
        env = ce.vanilla_env()
        self.assertEqual(env['last'], [0x16, 0x23])
        self.assertEqual(env['route'], 1, 'Eirika unless the campaign says otherwise')
        self.assertEqual(ce.vanilla_env(2)['route'], 2)

    def test_both_games_carry_the_team_caps(self):
        self.assertEqual(ce.vanilla_env()['maxima']['armour'], 1)
        self.assertEqual(ce.vanilla_env()['groups'][str(0x05)], 'mounted')


class LeadRow(unittest.TestCase):
    def test_a_pc_is_its_menu_row(self):
        lords = [u for u, *_ in ce.inject.cast._classed_cast(campaign_chapters.CAMPAIGN,
                                                              available_at=1)[0]]
        self.assertEqual(ce.lead_row(lords[-1]), len(lords) - 1)

    def test_a_unit_not_offered_raises(self):
        with self.assertRaises(ValueError):
            ce.lead_row('lupin')


class Ours(unittest.TestCase):
    def written(self):
        written = {int(c['chapter_number']) for c in campaign_chapters.load_all()
                   if c.get('status') != 'planned'}
        return {h.number: h.host_index for h in inject.hosts.hosted_chapters()
                if h.number in written}

    def test_shops_are_the_twins_records_and_it_ends_at_the_last_written(self):
        hosts = self.written()
        with tempfile.TemporaryDirectory() as store:
            for number in hosts:
                twin = ce.vanilla_index(difficulty.VANILLA_CHAIN[number])
                with open(os.path.join(store, '%d.json' % twin), 'w') as f:
                    json.dump({'shops': [twin, 100 + twin]}, f)
            env = ce.ours_env(store)
        self.assertEqual(env['last'], [hosts[max(hosts)]])
        for number, host in hosts.items():
            twin = ce.vanilla_index(difficulty.VANILLA_CHAIN[number])
            self.assertEqual(env['shops'][str(host)], [twin, 100 + twin])

    def test_a_missing_twin_record_raises(self):
        with tempfile.TemporaryDirectory() as store:
            with self.assertRaises(FileNotFoundError):
                ce.ours_env(store)


class Claims(unittest.TestCase):
    def test_every_twin_claim_resolves_on_both_routes(self):
        for route in (1, 2):
            claims = ce.vanilla_env(route)['claims']
            for chapter, listed in claims.items():
                for c in listed:
                    for field in ('unit', 'by'):
                        self.assertTrue(all(isinstance(i, int) for i in c.get(field, [])),
                                        '%s: %r' % (chapter, c))

    def test_twin_ch3_is_played_not_parked(self):
        ch3 = ce.vanilla_env(1)['claims'][str(ce.vanilla_index('FE8 Ch3'))]
        recruit = [c for c in ch3 if c['kind'] == 'recruit'][0]
        enum = ce.character_pid
        self.assertEqual((recruit['unit'], recruit['by']),
                         ([enum('CHARACTER_COLM')], [enum('CHARACTER_NEIMI')]))
        self.assertNotIn('unmodelled', {c['kind'] for c in ch3})

    def test_routes_split_after_ch8(self):
        enum = ce._chapter_enum()
        self.assertEqual(ce.twin_index('FE8 Ch9', 1), enum['CHAPTER_E_9'])
        self.assertIsNone(ce.twin_index('FE8 Ch9', 2), "Eirika's own Ch9 is not Ephraim's")
        self.assertEqual(ce.twin_index('FE8 Ch9 Ephraim', 2), enum['CHAPTER_I_9'])
        self.assertEqual(ce.twin_index('FE8 Ch15', 2), enum['CHAPTER_I_15'], 'shared from 15')
        self.assertEqual(ce.twin_index('FE8 Final 2', 1), enum['CHAPTER_E_21X'])
        self.assertEqual(ce.twin_index('FE8 Ch5x', 1), enum['CHAPTER_L_5X'])

    def test_every_written_chapter_resolves_and_reskins_join_their_base(self):
        import strategy
        for chap in campaign_chapters.load_all():
            if chap.get('status') != 'planned':
                for i, c in enumerate(strategy.our_claims(chap)):
                    ce.resolve(c, 'x#%d' % i, 'ours', chap)
        values = ce.class_ids.vanilla_class_values()
        ours = ce.class_ids_of('brigand', 'ours')
        self.assertIn(values['CLASS_BRIGAND'], ours)
        self.assertGreater(len(ours), 1, 'the kobold reskins play as Brigands (ADR 0362)')
        self.assertEqual(ce.class_ids_of('brigand', 'vanilla'), [values['CLASS_BRIGAND']])

    def test_a_name_that_resolves_to_nothing_raises(self):
        with self.assertRaises(ValueError):
            ce.resolve({'kind': 'priority', 'vs': 'no-such-class'}, 'x#0', 'vanilla')
        with self.assertRaises(ValueError):
            ce.resolve({'kind': 'recruit', 'unit': 'nobody'}, 'x#0', 'ours')

    def test_reinforcements_go_unresolved_not_dropped(self):
        self.assertEqual(ce.resolve({'kind': 'reinforcements'}, 'x#0', 'vanilla')['kind'],
                         'unresolved')


class Resume(unittest.TestCase):
    def run_main(self, argv):
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ce.main(argv)
        return json.loads(out.getvalue())

    def test_from_resumes_the_named_campaign(self):
        env = self.run_main(['vanilla', '--id', 'probe', '--from', '2'])
        self.assertEqual((env['id'], env['from']), ('probe', 2))
        self.assertNotIn('from', self.run_main(['vanilla']))

    def test_from_without_an_id_is_refused(self):
        with self.assertRaises(SystemExit):
            ce.main(['vanilla', '--from', '2'])


if __name__ == '__main__':
    unittest.main()
