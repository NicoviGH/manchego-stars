#!/usr/bin/env python3
"""Tests for tools/inject/asset_table.py.

Run:  python3 tools/test_inject_asset_table.py
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inject.namespace import stubbed
import inject.asset_table
import inject.decomp
from inject import source as injector  # the injector's source, every file of it (#389)


class AssetTableCeiling(unittest.TestCase):
    """gChapterDataAssetTable is addressed by NINE u8 fields of struct ROMChapterData, so 255 is
    the last index the engine can reach (decisions.md -> "The asset table is addressed by a u8").

    ch06 is the chapter that hit it: vanilla's 236 entries plus ch00-ch05's 19 appends is 255
    exactly, and ch06 registers four more. The ONLY thing that caught it was agbcc's `-Werror`
    on an implicit truncation in generated code -- so these are the gates that catch the next
    one before the compiler has to.
    """

    TABLE = 'gChapterDataAssetTable'
    # Every u8 field of a vanilla chapter entry that indexes the table. Spelled out here rather
    # than imported, so a silent edit to the module's own tuple fails this test instead of
    # travelling through it -- a PARTIAL list is the specific mistake that made the first read
    # of this problem report 60 free slots that were all ChapterEventGroups.
    INDEX_FIELDS = ('obj1Id', 'obj2Id', 'paletteId', 'tileConfigId', 'mainLayerId',
                    'objAnimId', 'paletteAnimId', 'changeLayerId')

    def _vanilla_table(self):
        return inject.decomp.vanilla_decomp_text('data/data_8B363C.s')

    def test_every_index_field_the_engine_reads_is_counted(self):
        self.assertEqual(set(inject.asset_table._ASSET_ID_FIELDS), set(self.INDEX_FIELDS))

    def test_vanilla_has_no_unreferenced_entry_at_all(self):
        """The reason reclaiming from never-loaded chapters is the only answer: there is no
        free list to find. Counting only `map.*` says otherwise, and says it convincingly."""
        vanilla = json.loads(inject.decomp.vanilla_decomp_text('src/data/chapter_settings.json'))
        used = set()
        for chapter in vanilla['chapters']:
            used |= inject.asset_table._chapter_asset_ids(chapter)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'asset_table.s')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self._vanilla_table())
            with open(path, encoding='utf-8') as f:
                lines = f.read().splitlines(keepends=True)
            _start, rows = inject.asset_table._asm_table_words(lines, self.TABLE, path)
        self.assertEqual([i for i in range(len(rows)) if i not in used], [])

    def test_the_reclaim_pool_never_offers_a_reserved_slot(self):
        vanilla = json.loads(inject.decomp.vanilla_decomp_text('src/data/chapter_settings.json'))
        reserved = set()
        for chapter in vanilla['chapters'][:inject.asset_table.ASSET_TABLE_RESERVED_SLOTS]:
            reserved |= inject.asset_table._chapter_asset_ids(chapter)
        pool = set(inject.asset_table.reclaimable_asset_slots())
        self.assertTrue(pool, 'the pool is empty -- every new chapter asset would fail')
        self.assertEqual(pool & reserved, set())

    def test_our_own_host_slots_are_inside_the_reserve(self):
        """The reserve is stated as a slot COUNT, so it has to actually cover where we host."""
        from inject import hosts
        for chapter in hosts.hosted_chapters():
            self.assertLess(chapter.host_index, inject.asset_table.ASSET_TABLE_RESERVED_SLOTS, chapter.name)

    def _claim(self, count, table=None):
        vanilla = self._vanilla_table()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'data_8B363C.s')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(table if table is not None else vanilla)
            got = inject.asset_table._claim_asm_table_words(
                path, self.TABLE, ['MS_TestAsset%d' % i for i in range(count)],
                vanilla_source=vanilla)
            with open(path, encoding='utf-8') as f:
                return got, f.read()

    def test_it_appends_while_the_index_is_still_addressable(self):
        got, written = self._claim(3)
        self.assertEqual(got, [236, 237, 238])
        self.assertNotIn('reclaimed', written)

    def test_it_reclaims_once_the_ceiling_is_reached_and_never_exceeds_it(self):
        # 20 more than vanilla's 236: the first 20 fit (236..255), the rest must be reclaimed.
        got, written = self._claim(24)
        self.assertEqual(got[:20], list(range(236, 256)))
        self.assertTrue(all(i < inject.asset_table.ASSET_TABLE_CEILING for i in got), got)
        self.assertEqual(len(set(got)), len(got), 'a slot was handed out twice')
        self.assertEqual(written.count('/* reclaimed:'), 4)
        # ...and the reclaimed ones are pool slots, not arbitrary ones.
        for index in got[20:]:
            self.assertIn(index, inject.asset_table.reclaimable_asset_slots())

    def test_a_full_table_fails_loudly_rather_than_truncating(self):
        with stubbed('reclaimable_asset_slots', lambda: []):
            with self.assertRaises(SystemExit) as caught:
                self._claim(21)
        self.assertIn('is full', str(caught.exception))

    def test_a_reclaimed_slot_is_still_findable_by_name(self):
        """_asm_table_word_index is how a later injector finds a tileset piece, and a reclaimed
        entry carries a trailing comment. Matching the raw line would find every APPENDED asset
        and miss exactly the reclaimed ones."""
        vanilla = self._vanilla_table()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'data_8B363C.s')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(vanilla)
            got = inject.asset_table._claim_asm_table_words(
                path, self.TABLE, ['MS_A%d' % i for i in range(22)], vanilla_source=vanilla)
            self.assertEqual(inject.asset_table._asm_table_word_index(path, self.TABLE, 'MS_A21'), got[21])


if __name__ == '__main__':
    unittest.main()
