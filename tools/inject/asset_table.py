"""The asset table's 8-BIT CEILING (#26): which slots a chapter may reclaim and claim.
"""
import json
import os
import sys

from inject.decomp import DECOMP, vanilla_decomp_text


#
# Every id that reaches gChapterDataAssetTable is a u8 FIELD of `struct ROMChapterData`:
# the eight `map.*Id`s and `mapEventDataId` (chapterdata.h; chapterdata.c/bmmap.c/bmio.c are
# the only readers, and all nine go through those fields). So index 255 is the last one the
# engine can address, and an entry appended past it is written, linked, shipped -- and
# unreachable. The compiler says so in the one place it can: `chapter_settings.h:993: warning:
# large integer implicitly truncated to unsigned type`, which is `-Werror` and is how ch06
# found this. Nothing else would have: the ROM would have built and drawn another chapter's map.
#
# Vanilla ships 236 entries and our campaign had appended 19 by ch05 -- 255 exactly, the last
# addressable slot. ch06 registers four more (its own tileset's three pieces plus its layout)
# and the prologue's layout follows, so the very next chapter was always going to be the one
# that hit this.
ASSET_TABLE_CEILING = 256

# Slots 0..25 of `gChapterDataAssetTable`'s CONSUMER -- the vanilla chapter table -- are
# treated as untouchable, and everything they reference is reserved. Our nine chapters host on
# slots 1..9 (`inject/hosts.py`), so 26 is a wide margin rather than a fitted bound, and it
# still leaves 118 reclaimable entries -- more than ch07, ch08 and any tileset they bring could
# spend several times over.
ASSET_TABLE_RESERVED_SLOTS = 26

# The nine u8 fields of a vanilla chapter entry that index the asset table.
_ASSET_ID_FIELDS = ('obj1Id', 'obj2Id', 'paletteId', 'tileConfigId', 'mainLayerId',
                    'objAnimId', 'paletteAnimId', 'changeLayerId')


def _chapter_asset_ids(chapter):
    """Every asset-table index one vanilla chapter entry references."""
    cmap = chapter.get('map') or {}
    ids = set(cmap[f] for f in _ASSET_ID_FIELDS if isinstance(cmap.get(f), int))
    if isinstance(chapter.get('mapEventDataId'), int):
        ids.add(chapter['mapEventDataId'])
    return ids


def reclaimable_asset_slots():
    """Asset-table indices no chapter this campaign can ever load references.

    Derived from VANILLA's chapter table at HEAD, never from the built tree, so the answer does
    not depend on how far through a build we are.

    The argument is the one the whole campaign already runs on: our ROM has no world map and its
    chapter chain runs ch00 -> ch08 on slots 1..9, so a vanilla chapter at slot 26 or beyond
    cannot be reached, and the assets only IT names are dead weight we may spend. That is the
    same reasoning that lets us strip a host slot's event lists, squat its dead message block and
    repurpose its unreferenced scripts -- and the reason there is no cheaper answer here is that
    NOTHING in vanilla's own table is unreferenced: an earlier read of this found 60 free
    entries by looking only at `map.*`, and every one of them turned out to be a
    ChapterEventGroup reached through `mapEventDataId`.

    An index reserved by an early slot is never offered, even if a late slot also uses it.
    """
    vanilla = json.loads(vanilla_decomp_text('src/data/chapter_settings.json'))
    chapters = vanilla['chapters']
    reserved, later = set(), set()
    for index, chapter in enumerate(chapters):
        into = reserved if index < ASSET_TABLE_RESERVED_SLOTS else later
        into |= _chapter_asset_ids(chapter)
    return sorted(later - reserved)


def _asm_table_words(lines, table_label, path):
    """(index of the label's line, [line indices of its consecutive `.word` entries])."""
    start = next((i for i, ln in enumerate(lines)
                  if ln.lstrip().startswith(table_label + ':')), None)
    if start is None:
        sys.exit('ERROR: table %r not found in %s' % (table_label, path))
    rows = []
    for i in range(start + 1, len(lines)):
        s = lines[i].strip()
        if s.startswith('.word'):
            rows.append(i)
        elif s and not s.startswith('@'):
            break
    if not rows:
        sys.exit('ERROR: no .word entries under %r' % table_label)
    return start, rows


def _claim_asm_table_words(path, table_label, words, vanilla_source=None):
    """Give each of `words` an ADDRESSABLE index in the asm array `table_label:`.

    Appends while the next index is still below `ASSET_TABLE_CEILING`, and otherwise RECLAIMS a
    slot from `reclaimable_asset_slots()` -- overwriting the vanilla entry in place. Returns the
    indices, in the order the words were given.

    Appending first is deliberate: it keeps every id ch00-ch05 already build with exactly where
    it was, so this change's blast radius is the assets that could not fit at all. A reclaimed
    slot is recognised as still-free by comparing it against HEAD -- the decomp is restored from
    HEAD every build, so an entry that no longer matches vanilla is one THIS build already
    claimed. That needs no bookkeeping of its own and cannot go stale.

    `vanilla_source` overrides the committed text this compares against. It exists so the tests
    can drive the ceiling against a throwaway copy: `path` is otherwise resolved back to the
    submodule through DECOMP, and pointing DECOMP at a temp directory just breaks `git show`.
    """
    with open(path, encoding='utf-8') as f:
        lines = f.read().splitlines(keepends=True)
    _start, rows = _asm_table_words(lines, table_label, path)
    if vanilla_source is None:
        vanilla_source = vanilla_decomp_text(os.path.relpath(path, DECOMP))
    vanilla = vanilla_source.splitlines()
    _vstart, vrows = _asm_table_words(
        [ln + '\n' for ln in vanilla], table_label, path)

    def word_at(index):
        return lines[rows[index]].strip()[len('.word'):].strip()

    def vanilla_word_at(index):
        return vanilla[vrows[index]].strip()[len('.word'):].strip()

    pool = [i for i in reclaimable_asset_slots()
            if i < len(rows) and word_at(i) == vanilla_word_at(i)]
    claimed, appended = [], []
    for word in words:
        index = len(rows) + len(appended)
        if index < ASSET_TABLE_CEILING:
            appended.append(word)
            claimed.append(index)
            continue
        if not pool:
            sys.exit(
                'ERROR: %s is full -- %d entries, ceiling %d, and no reclaimable slot is left '
                'for %r. Every id into this table is a u8 field of struct ROMChapterData, so '
                'there is no room to grow it; widen ASSET_TABLE_RESERVED_SLOTS only if the '
                'campaign really will never load those vanilla chapters.'
                % (table_label, len(rows), ASSET_TABLE_CEILING, word))
        index = pool.pop(0)
        lines[rows[index]] = '\t.word %s /* reclaimed: vanilla %s */\n' % (
            word, vanilla_word_at(index))
        claimed.append(index)
    if appended:
        lines[rows[-1] + 1:rows[-1] + 1] = ['\t.word %s\n' % w for w in appended]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(''.join(lines))
    return claimed



def _asm_table_word_index(path, table_label, word_label):
    """0-based index of `.word <word_label>` within the asm array `table_label:`. Used
    to look up an asset registered by an earlier injector (e.g. the winter tileset).

    The trailing `/* reclaimed: ... */` a reclaimed slot carries is stripped before the
    comparison: a slot claimed past the table's 8-bit ceiling says whose vanilla entry it took,
    and matching the raw line would find the appended assets and miss exactly the reclaimed
    ones -- which are the entries the newest chapter is made of."""
    with open(path, encoding='utf-8') as f:
        lines = f.read().splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.lstrip().startswith(table_label + ':')), None)
    if start is None:
        sys.exit('ERROR: table %r not found in %s' % (table_label, path))
    idx = 0
    for i in range(start + 1, len(lines)):
        s = lines[i].strip()
        if s.startswith('.word'):
            if s.split(None, 1)[1].split('/*')[0].strip() == word_label:
                return idx
            idx += 1
        elif s and not s.startswith('@'):
            break
    sys.exit('ERROR: .word %r not found under %r in %s' % (word_label, table_label, path))
