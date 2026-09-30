"""SMS id allocation (#227): reclaim dead vanilla standing-map-sprite rows before appending.
"""
import glob
import os
import re
import sys

from yaml_loader import yaml_load
from inject.cast import class_enum_for, deploy_class_for, load_unit, PORTRAIT_MAP
from inject.decomp import _table_close_line, DECOMP, REPO, vanilla_decomp_text
from inject.paths import UNIT_ICON_WAIT_C
from inject.warm import PATCHED_DECOMP_FILES


CUSTOM_SMS_BASE = 107


# FE8 draws map sprites by class (GetUnitSMSId -> pClassData->SMSId). To give each
# cast member a distinct overworld sprite without touching stock classes or vanilla
# enemies, we add a custom SMS slot per cast member (ids CUSTOM_SMS_BASE+) and a
# per-CHARACTER override in GetUnitSMSId. Colours come from the bespoke cast OBJ
# palette (map_sprites/cast_palette.png -> gCastMapPalette via _inject_cast_palette;
# the shared player blue bank stays untouched) -- a map sprite still can't carry its
# OWN palette, they all share the cast bank. Cold-open guests render through the
# vanilla unit_icon_pal_player.agbpal.


# Vanilla assigns map sprites per CLASS -- 107 wait rows serve 127 classes, because classes
# share (every Cavalier draws row 4). We assign per CHARACTER, so each custom cast member
# needs its own row. That is the design. What was NOT the design is that CUSTOM_SMS_BASE
# only ever APPENDED, leaving ~71 rows for classes this campaign can never field sitting
# unused below it while we ran into the engine's 127-id ceiling (#225).
#
# So: allocate into those dead rows first, append only when they run out.
#
# The trap is that "no class points at it" is NOT the same as "unreferenced".
# src/bmudisp.c RenderUnitSprites draws map OBJECTS by literal SMS id, no class involved:
#   0x5B/0x5C/0x5D -- ballista trap sprites, picked by trap->extra 0x35/0x36/0x37
#   0x66           -- trap type 0xD
# A class-only scan calls all four free, and reusing one renders a cast member on any map
# with a ballista. They are reserved, and a test re-derives this set from HEAD so a decomp
# bump cannot leave the reservation stale.
SMS_RESERVED_IDS = frozenset({0x5B, 0x5C, 0x5D, 0x66})


def _vanilla_class_table():
    """{CLASS_X: {'sms': id, 'promotion': CLASS_Y or None}} from the VANILLA class data.
    Read from HEAD: the working tree's data_classes.c carries our own injected clones."""
    out = {}
    for name, body in re.findall(r'\[(CLASS_\w+) - 1\] = \{(.*?)\n    \},',
                                 vanilla_decomp_text('src/data_classes.c'), re.S):
        sms = re.search(r'\.SMSId\s*=\s*(0x[0-9A-Fa-f]+|\d+)', body)
        if not sms:
            continue
        promo = re.search(r'\.promotion\s*=\s*(CLASS_\w+)', body)
        out[name] = {'sms': int(sms.group(1), 0),
                     'promotion': promo.group(1) if promo else None}
    return out


def sms_rows_for_classes(class_names):
    """The wait rows a set of vanilla classes draws from."""
    table = _vanilla_class_table()
    return {table[c]['sms'] for c in class_names if c in table}


def _promotion_branches():
    """{CLASS_X: [both promotion targets]} from FE8's BRANCHING promotion table,
    `gPromoJidLut[][2]` in src/classchg-data.c.

    ClassData.promotion holds only ONE target and is NOT the whole story: FE8 lets the
    player pick either branch (Myrmidon -> Assassin OR Swordmaster, Priest -> Bishop OR
    Sage, Thief -> Assassin OR Rogue). Following `.promotion` alone under-counts what a
    character can become, which would let us reuse the row of a class a PC can promote
    into -- and then that promotion renders as somebody else (Nicolas, 2026-08-05: the
    player should be able to class into any appropriate class, not only the one we
    prescribe)."""
    text = vanilla_decomp_text('src/classchg-data.c')
    text = text[text.index('gPromoJidLut'):]
    text = text[:text.index('};')]
    return {src: re.findall(r'CLASS_\w+', targets)
            for src, targets in re.findall(r'\[(CLASS_\w+)\]\s*=\s*\{([^}]*)\}', text)}


def _campaign_seed_classes(campaign):
    """Every vanilla class this campaign can put on screen, BEFORE promotions.

    Deliberately over-broad -- it scans raw `CLASS_*` tokens out of all campaign YAML and
    out of the event headers we author (which is where a world map names its units, #29) --
    because a missed class means a reused row and a unit rendering as somebody else. A
    false positive only costs us one reclaimable row."""
    seed = set()
    base = os.path.join(REPO, 'campaigns', campaign)
    sources = glob.glob(os.path.join(base, '**', '*.yaml'), recursive=True)
    sources += [os.path.join(DECOMP, p) for p in PATCHED_DECOMP_FILES
                if p.startswith('src/events/')]
    for path in sources:
        try:
            with open(path, encoding='utf-8') as f:
                seed |= set(re.findall(r'CLASS_[A-Z0-9_]+', f.read()))
        except (OSError, UnicodeDecodeError):
            continue
    for unit_id in PORTRAIT_MAP:
        unit = load_unit(campaign, unit_id)
        unit.setdefault('id', unit_id)
        for enum in (class_enum_for(unit), deploy_class_for(unit)):
            if enum:
                seed.add(enum)
    # Art donors are named by SHEET, not by CLASS_ enum (art.map_sprite.base: 'Cyclops'),
    # so the token scan above misses them. Naming a vanilla class as a donor is a decent
    # signal we might also field it, and reserving costs one row.
    seed |= {'CLASS_' + name.upper() for name in _declared_donor_bases(campaign)}
    return seed | SMS_RESERVED_CLASSES


# Classes no PC holds yet but a future recruit plausibly could. Reserved by hand because
# nothing in the data can infer "we might write this character later" (#227):
#   BARD/DANCER  -- the cast already includes a bard in D&D terms
#   MANAKETE*    -- Rime of the Frostmaiden has a white dragon (Arveiaturace), so keep the
#                   WHOLE dragon family (the three are separate classes). CLASS_MANAKETE is
#                   also the only class pointing at the shared `Blank` fallback row, so
#                   reusing it would put a cast sprite on the fallback sprite
SMS_RESERVED_CLASSES = frozenset({
    'CLASS_BARD', 'CLASS_DANCER',
    'CLASS_MANAKETE', 'CLASS_MANAKETE_2', 'CLASS_MANAKETE_MYRRH',
})


def _declared_donor_bases(campaign):
    """Every `art.map_sprite.base` a campaign unit declares (vanilla sheet/class names)."""
    out = set()
    for path in glob.glob(os.path.join(REPO, 'campaigns', campaign, '**', '*.yaml'),
                          recursive=True):
        try:
            with open(path, encoding='utf-8') as f:
                data = yaml_load(f)
        except Exception:
            continue

        def walk(node):
            if isinstance(node, dict):
                ms = node.get('map_sprite')
                if isinstance(ms, dict) and isinstance(ms.get('base'), str):
                    out.add(ms['base'])
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
        walk(data)
    return out


def sms_reachable_rows(campaign):
    """Wait rows this campaign must not reuse.

    CONSERVATIVE BY DECISION (Nicolas, 2026-08-05). The seed is not just the classes our
    YAML names today -- it is **every class in FE8's promotion tree**, i.e. anything a
    player unit could ever hold or become, whether or not this campaign fields it yet.

    Why not just today's roster: the roster is not final. Chapters and recruits are still
    being written, so a row that looks dead now can belong to a class a future PC holds --
    and "we have characters we haven't recruited yet, so your list is by definition
    incomplete" is not a bug that computation can fix. Reserving the whole player tree
    costs ~30 reclaimable rows and removes the dependency on the roster being finished.
    What is left over is genuinely un-playable: story-unique Magvel classes, the Demon
    King, spent-ballista variants, Phantom, and civilians.
    """
    table = _vanilla_class_table()
    branches = _promotion_branches()
    player_tree = set(branches) | {t for v in branches.values() for t in v}
    closure = {c for c in (_campaign_seed_classes(campaign) | player_tree) if c in table}
    frontier = set(closure)
    while frontier:
        nxt = set()
        for c in frontier:
            # BOTH branches of gPromoJidLut, plus ClassData.promotion as a belt-and-braces
            # fallback for anything the LUT does not list.
            nxt |= {t for t in branches.get(c, []) if t in table}
            if table[c]['promotion'] in table:
                nxt.add(table[c]['promotion'])
        nxt -= closure
        closure |= nxt
        frontier = nxt
    return {table[c]['sms'] for c in closure}


def sms_free_rows(campaign):
    """Vanilla wait rows this campaign can safely reuse: unreachable by any class it can
    field (after promotions) and not rendered by literal id. Recomputed every build -- if a
    later chapter fields a Wyvern Rider, that row stops being free here rather than silently
    rendering a PC as a wyvern."""
    vanilla_rows = len(re.findall(r'UNIT_ICON_SIZE',
                                  vanilla_decomp_text('src/unit_icon_wait_data.c')))
    return (set(range(vanilla_rows)) - sms_reachable_rows(campaign)) - set(SMS_RESERVED_IDS)


def allocate_sms_ids(campaign, count, verbose=False):
    """`count` SMS ids: reclaimed vanilla rows first (ascending), then appended ids past the
    end of the table. Appending stays subject to the engine ceiling (#225)."""
    free = sorted(sms_free_rows(campaign))[:count]
    ids = list(free)
    limit = sms_id_max()
    nxt = CUSTOM_SMS_BASE
    while len(ids) < count:
        if nxt > limit:
            sys.exit('ERROR: out of SMS ids -- %d requested, %d reclaimable vanilla rows + '
                     'ids %d..%d appended is all the engine can address (#225/#227).'
                     % (count, len(free), CUSTOM_SMS_BASE, limit))
        ids.append(nxt)
        nxt += 1
    if verbose and free:
        sheets = re.findall(r'unit_icon_wait_(\w+?)_sheet',
                            vanilla_decomp_text('src/unit_icon_wait_data.c'))
        print('  reclaiming %d dead vanilla SMS row(s): %s'
              % (len(free), ', '.join('%d (was %s)' % (i, sheets[i]) for i in free[:8])
                 + (' ...' if len(free) > 8 else '')))
    return ids


# The build's live SMS id pool. Module state because the two injectors that spend it --
# inject_map_sprites and inject_enemy_class_reskins -- are separate top-level passes called
# in sequence from main(), with no shared context object to thread it through. Reset once
# per build, before the first pass, so a re-run in the same process cannot double-spend.
_SMS_POOL = None


def sms_alloc_reset(campaign, verbose=False):
    """Open a fresh SMS id pool for one build: every reclaimable vanilla row (ascending),
    then the appended ids. Call once, before any sprite pass."""
    global _SMS_POOL
    free = sorted(sms_free_rows(campaign))
    _SMS_POOL = {'free': list(free), 'next_append': CUSTOM_SMS_BASE, 'reclaimed': []}
    if verbose:
        print('  SMS id pool: %d reclaimable vanilla row(s) + ids %d..%d'
              % (len(free), CUSTOM_SMS_BASE, sms_id_max()))


def claim_sms_id():
    """The next SMS id: a reclaimed dead vanilla row while any remain, else an appended id.
    Claimed ONLY by a pass that is about to write the matching wait row, which is what keeps
    ids and row indices in lockstep (allocating for a unit that never gets a row would shift
    every later row off the id naming it)."""
    if _SMS_POOL is None:
        sys.exit('ERROR: SMS id claimed before sms_alloc_reset() -- the pool is per-build')
    if _SMS_POOL['free']:
        sms = _SMS_POOL['free'].pop(0)
        _SMS_POOL['reclaimed'].append(sms)
        return sms
    sms = _SMS_POOL['next_append']
    if sms > sms_id_max():
        sys.exit('ERROR: out of SMS ids -- every reclaimable vanilla row is spent and the '
                 'append range %d..%d is full. FE8 masks ids with 0x%X, so there is no id '
                 '%d (#225/#227).' % (CUSTOM_SMS_BASE, sms_id_max(), sms_id_max(), sms))
    _SMS_POOL['next_append'] = sms + 1
    return sms


def sms_alloc_report():
    """What this build reclaimed and what is left, so reuse is legible in the build log
    instead of invisible -- and so running low is visible BEFORE the build that runs out."""
    if not _SMS_POOL:
        return
    got = _SMS_POOL['reclaimed']
    if got:
        sheets = re.findall(r'unit_icon_wait_(\w+?)_sheet',
                            vanilla_decomp_text('src/unit_icon_wait_data.c'))
        shown = ', '.join('%d (was %s)' % (i, sheets[i]) for i in got[:6])
        print('  reclaimed %d dead vanilla SMS row(s): %s%s'
              % (len(got), shown, ' ...' if len(got) > 6 else ''))
    left = len(_SMS_POOL['free']) + max(0, sms_id_max() + 1 - _SMS_POOL['next_append'])
    print('  SMS ids left: %d (%d reclaimable row(s) + %d appendable)%s'
          % (left, len(_SMS_POOL['free']), max(0, sms_id_max() + 1 - _SMS_POOL['next_append']),
             '  <-- NEARLY FULL' if left <= SMS_ID_LOW_WATER else ''))


def _write_wait_row(sms_id, row):
    """Put `row` at index `sms_id` of unit_icon_wait_table[].

    A reclaimed id REPLACES the vanilla row living there; an appended id extends the table
    and must land at exactly the index it names. Asserting that equality here is what makes
    an id/row desync impossible rather than merely unlikely."""
    with open(UNIT_ICON_WAIT_C, encoding='utf-8') as f:
        lines = f.read().splitlines(keepends=True)
    di, ci = _table_close_line(lines, 'unit_icon_wait_table[]')
    body = [i for i in range(di + 1, ci) if lines[i].lstrip().startswith('{')]
    if sms_id < len(body):
        lines[body[sms_id]] = row + '\n'
    else:
        if sms_id != len(body):
            sys.exit('ERROR: SMS row for id %d would land at index %d -- ids and wait-table '
                     'row indices have desynced (#227)' % (sms_id, len(body)))
        if sms_id > sms_id_max():
            sys.exit('ERROR: SMS id %d is past the engine ceiling of %d (#225)'
                     % (sms_id, sms_id_max()))
        if '},' not in lines[ci - 1] and '}' in lines[ci - 1]:
            lines[ci - 1] = re.sub(r'\}(\s*)(/[/*][^\n]*)?\n$', r'},\1\2\n',
                                   lines[ci - 1], count=1)
        lines[ci:ci] = [row + '\n']
    with open(UNIT_ICON_WAIT_C, 'w', encoding='utf-8') as f:
        f.write(''.join(lines))


def _wait_table_len():
    """Count rows currently in unit_icon_wait_table[] -> the next free SMS id (rows are
    0-indexed by SMS id). Read AFTER inject_map_sprites so the cast rows are included."""
    with open(UNIT_ICON_WAIT_C, encoding='utf-8') as f:
        lines = f.read().splitlines()
    di, ci = _table_close_line(lines, 'unit_icon_wait_table[]')
    return sum(1 for i in range(di + 1, ci) if lines[i].lstrip().startswith('{'))


# How close to the ceiling we let a build get before saying so out loud. Two is the number
# that matters today: ch05's Basil + Sahnar are the last two ids (#225).
SMS_ID_LOW_WATER = 4
_SMS_MASK_BITS = None


def _sms_id_mask_bits():
    """Bit width of the mask the ENGINE applies to every SMS id, read from the decomp:

        src/bmudisp.c:  #define GetInfo(id) (unit_icon_wait_table[(id) & ((1<<7)-1)])

    Read from HEAD, never the working tree -- our injections are build artifacts. Grounding
    the ceiling in the engine that enforces it means a decomp bump moves the guard with it
    instead of leaving a stale literal behind."""
    global _SMS_MASK_BITS
    if _SMS_MASK_BITS is None:
        m = re.search(r'#define\s+GetInfo\(id\)\s*\(unit_icon_wait_table\[\(id\)\s*&\s*'
                      r'\(\(1\s*<<\s*(\d+)\)\s*-\s*1\)\]\)',
                      vanilla_decomp_text('src/bmudisp.c'))
        if not m:
            sys.exit('ERROR: the GetInfo SMS-id mask is not in its expected form in '
                     'src/bmudisp.c -- re-derive the custom SMS id ceiling before building '
                     '(#225), an id past the mask silently renders a VANILLA sprite')
        _SMS_MASK_BITS = int(m.group(1))
    return _SMS_MASK_BITS


def sms_id_max():
    """Highest SMS id the engine can look up without wrapping (127 today)."""
    return (1 << _sms_id_mask_bits()) - 1


def _wait_row_label(row):
    """The unit a generated wait row names, for an error message. Rows carry a trailing
    `// <id> <label>` / `/* <id> <label> */` comment written by the pass that emitted them."""
    m = re.search(r'(?://|/\*)\s*\d+\s+([^*\n]+?)\s*(?:\*/)?$', row.strip())
    return m.group(1).strip() if m else row.strip()
