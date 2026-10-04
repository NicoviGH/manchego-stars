#!/usr/bin/env python3
"""gen_symbols' generated campaign tables: what harness.lua and the chapter chunks used to
hand-copy from the injector's constants."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'playtest'))
import gen_symbols  # noqa: E402


class LuaLiteral(unittest.TestCase):
    def test_shapes(self):
        self.assertEqual('0x1D', gen_symbols.lua_literal(0x1D))
        self.assertEqual('{ 0xCA, 0xC9 }', gen_symbols.lua_literal([0xCA, 0xC9]))
        self.assertEqual('{\n    [0xB0] = true,\n}', gen_symbols.lua_literal({0xB0: True}))
        self.assertEqual('{\n    ["prof-rbg"] = 0x05,\n}', gen_symbols.lua_literal({'prof-rbg': 5}))

    def test_refuses_what_lua_would_misread(self):
        for bad in (False, 'x', 1.5, None):
            with self.assertRaises(TypeError):
                gen_symbols.lua_literal(bad)


class CampaignIds(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ids = gen_symbols.campaign_ids()

    def test_a_cast_pid_is_its_slot_not_its_stat_donor(self):
        # The trap the harness's CAST comments warned about three times: Lupin's stats come
        # from Kyle (0x11), but he IS Duessel (0x1D); Baxby is Forde, Basil Artur, Sahnar Marisa.
        cast = self.ids['CAST']
        self.assertEqual((0x1D, 0x10, 0x13, 0x16),
                         (cast['lupin'], cast['baxby'], cast['basil'], cast['sahnar']))
        self.assertEqual(cast['prof-rbg'], cast['rbg'])

    def test_the_charms_are_the_yaml_gifts_of_the_chwinga_on_the_field(self):
        # Glimmerfrost lives in a hut, so the field pays two charms, not three.
        self.assertEqual([0xCA, 0xC9], self.ids['CH02_CHWINGA_PIDS'])
        self.assertEqual([0x28, 0x6D], self.ids['CH02_CHARMS'])   # Hand Axe, Elixir

    def test_hosts_follow_the_host_slots(self):
        self.assertEqual({'ch%02d' % n: n + 1 for n in range(1, 7)}, self.ids['HOST'])

    @unittest.skipUnless(shutil.which('lua'), 'no lua interpreter (brew install lua)')
    def test_the_rendered_table_is_lua_the_harness_can_read(self):
        with tempfile.NamedTemporaryFile('w', suffix='.lua', delete=False) as f:
            f.write('CAMPAIGN = %s\n' % gen_symbols.lua_literal(self.ids))
        try:
            out = subprocess.run(
                ['lua', '-e', 'dofile(%r); print(CAMPAIGN.CAST.lupin, CAMPAIGN.HOST.ch06, '
                              'CAMPAIGN.CH04_PACK_PIDS[0xB4])' % f.name],
                capture_output=True, text=True, check=True).stdout.split()
        finally:
            os.remove(f.name)
        self.assertEqual(['29', '7', 'true'], out)


if __name__ == '__main__':
    unittest.main()
