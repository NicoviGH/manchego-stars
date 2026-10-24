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
        # A string, quoted and escaped so Lua reads back exactly these characters (casthelp's
        # expected help-text lines carry apostrophes; a quote or backslash must survive too).
        self.assertEqual('"a \\"b\\" c\\\\"', gen_symbols.lua_literal('a "b" c\\'))

    def test_refuses_what_lua_would_misread(self):
        for bad in (False, 1.5, None):
            with self.assertRaises(TypeError):
                gen_symbols.lua_literal(bad)



class StaticEwram(unittest.TestCase):
    """A file-static array is found through the linker map, and refused when its object's
    section holds anything else (#495: sTrapPool, for the cracked-wall verdict)."""

    MAP = (' src/bmtrick.o(ewram_data)\n'
           ' ewram_data     0x0203a614      0x208 src/bmtrick.o\n')

    def test_the_section_start_is_the_array(self):
        self.assertEqual({'sTrapPool': 0x0203A614}, gen_symbols.static_ewram_symbols(self.MAP))

    def test_a_section_of_another_size_is_refused(self):
        with self.assertRaises(KeyError):
            gen_symbols.static_ewram_symbols(self.MAP.replace('0x208', '0x210'))

    def test_a_missing_object_is_refused(self):
        with self.assertRaises(KeyError):
            gen_symbols.static_ewram_symbols(self.MAP.replace('bmtrick', 'bmtrap'))

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
        self.assertEqual([0x6C, 0x6C], self.ids['CH02_CHARMS'])   # a Vulnerary each (#495)

    def test_villages_carry_the_yaml_tile_the_injector_flag_and_the_gift(self):
        # Glimmerfrost's hut pays her Pure Water on EVFLAG_TMP(9); the east hut pays its line
        # alone, so it carries no gift and a raid there cannot be judged on one.
        villages = self.ids['VILLAGES']
        self.assertEqual({'x': 1, 'y': 12, 'flag': 9, 'gift': 0x6E}, villages['targos-hut-south'])
        self.assertEqual({'x': 12, 'y': 3, 'flag': 10}, villages['targos-hut-east'])
        self.assertEqual({'x': 12, 'y': 19, 'flag': 10, 'gift': 0x60}, villages['reliquary-south'])

    def test_every_declared_raid_names_a_site_the_export_carries(self):
        # declared.py checks an id against the chapter's `villages:`, but only a village whose
        # injector arms an event id is exported; a raid on any other would ERROR at run time.
        import declared
        for _short, case in declared.cases():
            for entry in case.get('then') or ():
                for site in (entry.get('raided') or ()) if isinstance(entry, dict) else ():
                    self.assertIn(site, self.ids['VILLAGES'],
                                  '%s raids %s, which no CHNN_VILLAGE_FLAGS arms'
                                  % (case['name'], site))

    def test_hosts_follow_the_host_slots(self):
        # Every hosted chapter, so a film can name the slot a chain lands on; from ch01 on each
        # chapter N sits on slot N + 1.
        from inject import hosts
        hosted = [c.name for c in hosts.hosted_chapters() if c.name != 'prologue']
        self.assertIn('ch07', hosted)
        self.assertEqual({name: int(name[2:]) + 1 for name in hosted}, self.ids['HOST'])

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
