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
