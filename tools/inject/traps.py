"""Traps (#302): every hosted chapter's `.traps`, written from its declaration.
"""
import glob
import os
import re
import sys

from inject.decomp import DECOMP, vanilla_decomp_text
from inject.hosting import _load_chapter_yaml, chapter_yaml_for
from inject.paths import TRAPDATA_C


# Our trap-type token -> the decomp enum. The list is exactly what `LoadTrapData`
# (bmtrap.c:245) has a working case for, which is NOT the same as the bmtrick.h enum:
#   * TRAP_OBSTACLE / TRAP_TORCHLIGHT / TRAP_LIGHT_RUNE have no case at all -- declaring
#     one builds green and places nothing.
#   * TRAP_LIGHTARROW falls THROUGH into AddGorgonEggTrap: its `break` sits behind
#     `#if BUGFIX`, and BUGFIX is defined nowhere in the submodule. A light arrow would
#     also hatch an undeclared gorgon egg at the same tile.
# So the whitelist is what the ENGINE does, not what the enum names. Adding a row means
# reading LoadTrapData first, because every failure here is silent at runtime.
TRAP_TYPES = {
    'ballista':   'TRAP_BALLISTA',
    'firetile':   'TRAP_FIRETILE',
    'gas':        'TRAP_GAS',
    'mine':       'TRAP_MINE',
    'gorgon-egg': 'TRAP_GORGON_EGG',
}
TRAP_MAX_COORD = 255      # the u8 range of the ROM field. NOT a map-bounds check: the map
                          # is not loaded here, so a coordinate can be legal-but-off-map and
                          # this will not catch it. Say "byte range", never "off the map".
TRAP_MAX_COUNT = 64       # sTrapPool is TRAP_MAX_COUNT wide (bmtrick.h:6) and AddTrap
                          # (bmtrick.c:113) scans it for a free slot with NO bound


def chapter_traps(chap):
    """A chapter's DECLARED traps, validated, as a list of row dicts (#302).

    `.traps` is a ChapterEventGroup field, so a hosted chapter inherits whatever its donor
    group carries unless the build writes it -- the same silent-inheritance shape as the
    goal text ids (#207), the battle grounds and the difficulty numbers. It was one chapter
    from biting: ch06 fills `Ch7EventData`, and vanilla Ch7 carries two ballistae at (17,8)
    and (2,10), which would have appeared on our map having been chosen by nobody.

    Declaring nothing is a valid declaration and means NO traps -- the build writes
    TRAP_NONE either way, so inheritance is impossible by construction."""
    rows = chap.get('traps') or []
    if len(rows) > TRAP_MAX_COUNT:
        sys.exit('ERROR: chapter %s declares %d traps -- the engine has %d slots and AddTrap '
                 'scans for a free one WITHOUT a bound, so the surplus walks past the pool'
                 % (chap.get('id', '?'), len(rows), TRAP_MAX_COUNT))
    out = []
    for row in rows:
        token = row.get('type')
        if token not in TRAP_TYPES:
            sys.exit('ERROR: chapter %s declares trap type %r -- placeable types are %s '
                     '(the list is what LoadTrapData has a working case for, not the enum)'
                     % (chap.get('id', '?'), token, ', '.join(sorted(TRAP_TYPES))))
        for axis in ('x', 'y'):
            value = row.get(axis)
            if not isinstance(value, int) or isinstance(value, bool) \
                    or not 0 <= value <= TRAP_MAX_COORD:
                sys.exit('ERROR: chapter %s trap %s has %s=%r -- must be an integer 0..%d '
                         '(the ROM field is a u8; map bounds are NOT checked here)'
                         % (chap.get('id', '?'), token, axis, value, TRAP_MAX_COORD))
        for field in ('count', 'turn'):
            value = row.get(field, 0)
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 255:
                sys.exit('ERROR: chapter %s trap %s has %s=%r -- must be an integer 0..255 '
                         '(it is emitted into a u8 array and would truncate)'
                         % (chap.get('id', '?'), token, field, value))
        item = row.get('item')
        if token == 'ballista' and not item:
            sys.exit('ERROR: chapter %s declares a ballista with no `item` -- AddBallista '
                     'reads it as the AMMUNITION, and 0 means zero uses, so the ballista '
                     'exists and can never fire' % chap.get('id', '?'))
        out.append({'type': TRAP_TYPES[token], 'x': row['x'], 'y': row['y'],
                    'item': item or 0, 'count': int(row.get('count', 0)),
                    'turn': int(row.get('turn', 0))})
    return out


def trap_data_body(traps):
    """Render trap rows as the decomp's own TrapData array body, TRAP_NONE-terminated.

    Row shape is copied from vanilla's tables verbatim (6 bytes: type, xPos, yPos, subt,
    cnt, turn) rather than from `struct Trap`, which is the RAM layout and orders its
    fields differently."""
    lines = ['    /* type */ %s, /* xPos */ %s, /* yPos */ %s, /* subt */ %s, '
             '/* cnt */ %d, /* turn */ %d,'
             % (t['type'], t['x'], t['y'], t['item'], t['count'], t['turn'])
             for t in traps]
    return '\n'.join(lines + ['    /* type */ TRAP_NONE'])


def _chapter_trap_symbol(event_group):
    """The TrapData symbol a ChapterEventGroup's `.traps` points at."""
    for path in glob.glob(os.path.join(DECOMP, 'src', 'events', '*-eventinfo.h')):
        with open(path, encoding='utf-8') as f:
            text = f.read()
        match = re.search(re.escape(event_group) + r'\s*=\s*\{(.*?)\n\};', text, re.S)
        if match:
            field = re.search(r'\.traps\s*=\s*(\w+)', match.group(1))
            return field.group(1) if field else None
    return None


def _vanilla_trap_kinds(symbol):
    """The trap types vanilla's table for `symbol` carries (TRAP_NONE excluded)."""
    text = vanilla_decomp_text('src/events_trapdata.c')
    match = re.search(re.escape(symbol) + r'\[\]\s*=\s*\{(.*?)\};', text, re.S)
    if not match:
        return []
    return sorted(set(re.findall(r'\b(TRAP_[A-Z_0-9]+)\b', match.group(1))) - {'TRAP_NONE'})


def inherited_traps_undeclared(campaign):
    """Hosted chapters whose DONOR group carries traps the chapter declares nothing about.

    Writing the declaration already makes inheritance impossible, so this is not a safety
    net -- it is a prompt. A donor carrying real traps means a real decision is being made
    silently (keep vanilla's ballistae, or clear the field), and the build should stop and
    ask rather than pick one. ch06 on `Ch7EventData` is the founding case."""
    from inject.hosts import hosted_chapters
    stranded = []
    for chapter in hosted_chapters():
        chap = _load_chapter_yaml(campaign, chapter_yaml_for(chapter.name))
        if chap.get('traps') is not None:
            continue
        symbol = _chapter_trap_symbol(chapter.event_group)
        if symbol and _vanilla_trap_kinds(symbol):
            stranded.append(chapter.name)
    return sorted(stranded)


def chapter_trap_tables(campaign):
    """{TrapData symbol: rendered body} for every hosted chapter."""
    from inject.hosts import hosted_chapters
    out = {}
    for chapter in hosted_chapters():
        chap = _load_chapter_yaml(campaign, chapter_yaml_for(chapter.name))
        symbol = _chapter_trap_symbol(chapter.event_group)
        if symbol is None:
            sys.exit('ERROR: %s fills %s, which declares no `.traps` field -- the trap table '
                     'cannot be written and the chapter would inherit silently'
                     % (chapter.name, chapter.event_group))
        if symbol in out:
            sys.exit('ERROR: %s and another chapter both resolve to %s -- keying the write by '
                     'SYMBOL would silently drop one chapter\'s declaration'
                     % (chapter.name, symbol))
        out[symbol] = trap_data_body(chapter_traps(chap))
    return out


def apply_chapter_traps(campaign, verbose=False):
    """Write every hosted chapter's DECLARED trap table into events_trapdata.c."""
    stranded = inherited_traps_undeclared(campaign)
    if stranded:
        sys.exit('ERROR: %s fill donor groups that carry TRAPS, and declare no `traps:` '
                 'block -- keeping another chapter\'s ballistae at another chapter\'s '
                 'coordinates is a decision, not a default. Declare `traps: []` to clear '
                 'them or list the ones you want.' % ', '.join(stranded))
    with open(TRAPDATA_C, encoding='utf-8') as f:
        text = f.read()
    for symbol, body in sorted(chapter_trap_tables(campaign).items()):
        pattern = re.compile(re.escape(symbol) + r'(\[\]\s*=\s*\{)(.*?)(\n\};)', re.S)
        if not pattern.search(text):
            sys.exit('ERROR: %s not found in %s' % (symbol, TRAPDATA_C))
        text = pattern.sub(lambda m: symbol + m.group(1) + '\n' + body + m.group(3), text, 1)
    with open(TRAPDATA_C, 'w', encoding='utf-8') as f:
        f.write(text)
    if verbose:
        print('  traps: %s' % ', '.join(
            '%s=%d' % (s, b.count('/* xPos */')) for s, b in sorted(
                chapter_trap_tables(campaign).items())))
