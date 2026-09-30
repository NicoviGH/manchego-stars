#!/usr/bin/env python3
"""Tests for tools/inject/platforms.py.

Run:  python3 tools/test_inject_platforms.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.chapters.ch05
import inject.decomp
import inject.hosts
import inject.maps
import inject.platforms
import inject.terrain


class BattlePlatformTerrain(unittest.TestCase):
    """Terrain category -> snow ground, and the OFF-BY-ONE that hid inside it (#65).

    `GetBanimTerrainGround` ends `return ret - 1`, so a terrain array holds
    **table index + 1**, never the index. The cave path always knew that (it writes 21 for
    `siroyuka1` at index 20); the snow path wrote raw indices, so every snow chapter had been
    standing one platform BELOW the one named for it since #65 -- open ground landed on
    `mizuiumi1`, a vanilla LAKE, and the chapters that asked for rough got the drift. Nothing
    caught it because the drift is plausible snow and nobody read the ground.

    So these assert the CONVENTION, in the direction that fails loudly if it is dropped again:
    the value is one MORE than the index, and never equal to it.
    """
    BASE = 115   # PLATFORM_BASE_INDEX in the shipped table: drift 115, rough 116, ice 117

    def test_a_ground_value_is_one_more_than_its_table_index(self):
        self.assertEqual(21, inject.platforms._ground_value(20))   # siroyuka1, the case vanilla proves
        self.assertEqual(5, inject.platforms._ground_value(4))     # gake1

    def test_road_gets_the_snow_path_on_both_tilesets(self):
        """TERRAIN_ROAD has its own slot in the 66-entry array -- vanilla's own tables use it
        (slot 6 puts `michi1` there, which is what ch05 was standing on). Ours had been
        collapsing it into "everything else"; it now names the vendored snowy path, and it does
        so on BOTH tilesets, because a road is a road whether the open ground beside it reads
        as drift or as rock."""
        path = inject.platforms._ground_value(self.BASE + 3)       # -> table[118] = ms_snowpath
        self.assertEqual(path, inject.platforms._terrain_snow_ground('ROAD', self.BASE, False))
        self.assertEqual(path, inject.platforms._terrain_snow_ground('ROAD', self.BASE, True))
        # ...and it is NOT what open ground gets, or the assignment bought nothing.
        self.assertNotEqual(path, inject.platforms._terrain_snow_ground('PLAINS', self.BASE, False))

    def test_open_ground_is_snowdrift_on_the_open_tileset(self):
        drift = inject.platforms._ground_value(self.BASE)          # -> table[115] = ms_snowdrift
        self.assertEqual(drift, inject.platforms._terrain_snow_ground('PLAINS', self.BASE, False))
        self.assertNotEqual(self.BASE, drift, 'a raw index selects the row BELOW the one meant')

    def test_open_ground_becomes_rough_on_the_rough_tileset(self):
        rough = inject.platforms._ground_value(self.BASE + 1)      # -> table[116] = ms_snowrough
        self.assertEqual(rough, inject.platforms._terrain_snow_ground('PLAINS', self.BASE, True))

    def test_rough_terrain_is_always_uneven(self):
        rough = inject.platforms._ground_value(self.BASE + 1)
        for t in ('MOUNTAIN', 'PEAK', 'CLIFF', 'VALLEY'):
            self.assertEqual(rough, inject.platforms._terrain_snow_ground(t, self.BASE, False))
            self.assertEqual(rough, inject.platforms._terrain_snow_ground(t, self.BASE, True))

    def test_water_terrain_is_always_ice(self):
        ice = inject.platforms._ground_value(self.BASE + 2)
        for t in ('LAKE', 'SEA', 'RIVER', 'WATER', 'GLACIER'):
            self.assertEqual(ice, inject.platforms._terrain_snow_ground(t, self.BASE, False))
            self.assertEqual(ice, inject.platforms._terrain_snow_ground(t, self.BASE, True))  # even on rough

    def test_every_snow_ground_names_one_of_OUR_platforms(self):
        """The assertion that would have caught it: resolve each value the way the ENGINE does
        (subtract one, index the table) and require the row to be one we appended."""
        ours = {inject.platforms.PLATFORM_BASE_INDEX + n: 'ms_' + sym
                for n, (_stem, sym, _tint) in enumerate(inject.platforms.BATTLE_PLATFORMS)}
        for rough_open in (False, True):
            for terrain in ('PLAINS', 'ROAD', 'MOUNTAIN', 'CLIFF', 'LAKE', 'RIVER'):
                value = inject.platforms._terrain_snow_ground(terrain, inject.platforms.PLATFORM_BASE_INDEX, rough_open)
                self.assertIn(value - 1, ours,
                              '%s -> value %d selects table[%d], which is not one of ours'
                              % (terrain, value, value - 1))


class EveryHostedChapterPicksItsGround(unittest.TestCase):
    """A hosted chapter that never names a battleTileSet keeps its HOST SLOT's vanilla one,
    and vanilla's slots are not our world (#65 / #25).

    That is not a theoretical gap -- it shipped. ch05's slot 6 carries vanilla Ch6's
    `battleTileSet = 6`, whose table sends TERRAIN_ROAD to `michi1` and TERRAIN_PLAINS to
    `heichi1`; ch05's map is 53% road, so every fight in a snowbound elven tomb was standing
    on a green verge and a dirt track. ch02's slot 3 (vanilla 5) had the same defect, unseen.
    Silence is what made both invisible, so the registry is REQUIRED to be total: a new
    chapter has to state its ground, not inherit somebody else's.
    """
    OURS = {0x00, 0x15, 0x16}   # snow-open (Default), snow-rough (Tileset15), cave (Tileset16)

    def test_every_hosted_chapter_names_its_ground(self):
        missing = [c.name for c in inject.hosts.hosted_chapters()
                   if c.host_index not in inject.platforms.CHAPTER_BATTLE_TILESETS]
        self.assertEqual([], missing,
                         'these chapters would silently inherit vanilla platforms: %s' % missing)

    def test_no_chapter_is_left_on_a_vanilla_ground(self):
        for host_index, tileset in inject.platforms.CHAPTER_BATTLE_TILESETS.items():
            self.assertIn(tileset, self.OURS,
                          'chapter slot %d is pointed at a ground we do not own' % host_index)

    def test_the_snowbound_chapters_stand_on_snow(self):
        """The two that were wrong, pinned by the values they were wrong about."""
        self.assertEqual(0x15, inject.platforms.CHAPTER_BATTLE_TILESETS[inject.hosts.CH05_HOST_INDEX])
        self.assertEqual(0x15, inject.platforms.CHAPTER_BATTLE_TILESETS[inject.hosts.CH02_HOST_INDEX])
        self.assertEqual(0x16, inject.platforms.CHAPTER_BATTLE_TILESETS[inject.hosts.CH03_HOST_INDEX])   # the mine

    def test_ch05_fights_mostly_on_its_ROAD_and_that_is_where_the_path_ground_goes(self):
        """Which ground matters here is a fact about the map, not a taste: ch05 is more than
        half TERRAIN_ROAD, so the road slot decides how most of the chapter looks in combat.
        Resolved the way the engine resolves it (value - 1), so it cannot pass on the row below
        the one it names -- see _ground_value."""
        maps = os.path.join(inject.decomp.REPO, 'campaigns', 'rime-of-the-frostmaiden', 'maps')
        _w, _h, grid = inject.terrain._map_terrain_grid(maps, inject.chapters.ch05.CH05_LAYOUT[1])
        ids = inject.maps.terrain_ids()
        tiles = [t for row in grid for t in row]
        road = sum(1 for t in tiles if t == ids['TERRAIN_ROAD'])
        self.assertGreater(road, len(tiles) // 2, 'ch05 is a paved map; if that changes, revisit')
        for rough_open in (False, True):
            value = inject.platforms._terrain_snow_ground('ROAD', inject.platforms.PLATFORM_BASE_INDEX, rough_open)
            self.assertEqual('ms_snowpath',
                             'ms_' + inject.platforms.BATTLE_PLATFORMS[value - 1 - inject.platforms.PLATFORM_BASE_INDEX][1])


if __name__ == '__main__':
    unittest.main()
