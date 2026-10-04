"""Milestone B step 3: the test-chapter sandbox -- the whole cast on a Ch1 map.
"""
import json
import os
import sys

from inject.boot import _lord_select_event_seq, LORDSEL_EXPLAINER_MSG
from inject.cast import (
    _chapter_unit, class_enum_for, CLASS_LOADOUT, deploy_class_for, load_unit, PORTRAIT_MAP,
    RAW_PID_BATTLE_ANIMS)
from inject.chapter_ids import CH01_LORDSEL_BG, CH05_CLASS_IDS, CH05_ITEM_IDS
from inject.decomp import _replace_brace_block, REPO
from inject.paths import CH1_EVENTINFO_H, CH1_EVENTSCRIPT_H, CH1_UDEFS_H
from inject.reskins import enemy_class_reskins


# Centered, spread-out formation on the Ch1 map (a 4x2 grid, 2-tile gaps), clear of the
# houses (13,6)/(10,4) and seize (2,2). Pulled in from the old bottom-right cluster so the
# cast reads spaced out toward the middle for the look-test. Roster fills in order.
TEST_SPAWN_POSITIONS = [(5, 4), (7, 4), (9, 4), (11, 4),
                        (5, 6), (7, 6), (9, 6), (11, 6),
                        (13, 5), (13, 7), (13, 3),   # 9th-11th: recruits Trex + Baxby + Lupin
                        (3, 5), (3, 7)]              # 12th-13th: ch05's Basil + Sahnar. Left-hand
                        # column mirroring the (13,*) one, and clear of the seize tile at (2,2).

# The TESTCH sandbox doubles as the SINGLE battle-anim test bench: it deploys one hostile of
# every enemy_class_reskins slot as a foe (a row south of the cast), so `recordenemy` can bait
# any reskinned class into a counter and capture its anim -- the enemy analogue of `recordanim`
# for the PC cast (no chapter-specific setup, all animations tested from one New Game). Iron
# loadout by the reskin's BASE weapon type so the foe can actually attack/counter (anims are
# weapon-keyed); a ranged option too, to exercise the thrown/ranged modes.
CLASS_RESKIN_FOE_WEAPON = {
    'CLASS_BRIGAND':   ['ITEM_AXE_IRON', 'ITEM_AXE_HANDAXE'],
    'CLASS_FIGHTER':   ['ITEM_AXE_IRON', 'ITEM_AXE_HANDAXE'],
    'CLASS_MERCENARY': ['ITEM_SWORD_IRON'],
    'CLASS_SOLDIER':   ['ITEM_LANCE_IRON', 'ITEM_LANCE_JAVELIN'],
    # A BOW class benches fine -- it just cannot be baited from an adjacent tile, because a bow
    # has no range-1 attack to counter with. `recordenemy` now picks a bait whose reach overlaps
    # the foe's and stands at that distance, so an archer answers at range 2 exactly as RBG does
    # (Nicolas, 2026-08-20). This entry was missing on the theory that archers could not be
    # benched at all, which was the picker's limitation wearing a class's name.
    'CLASS_ARCHER':    ['ITEM_BOW_IRON'],
}
# The TESTCH sandbox's bench row. A tile at x=16 is not a tile at all on a 15-wide map, and
# it shipped as one anyway: the strip was extended a slot at a time as creatures joined, and
# `_next_sandbox_tile`'s guard only catches running OUT of tiles, never a tile that does not
# EXIST. The seventh creature (the white moose, once Ravisin took the sixth) deployed off the
# map edge and `recordenemy` failed walking the cursor to a column the map has not got.
# Spacing 2 is kept -- adjacent foes let the bait counter the wrong one -- so the strip starts
# at 2 rather than running past 14.
# The TESTCH bench: one seat per DISTINCT creature sprite, spacing 2 so `recordenemy` can always
# find a bait tile adjacent to ONLY its target (decisions.md -> "The TESTCH bench is bounded by
# SMS VRAM, not by its tile row").
#
# SECOND ROW ADDED 2026-08-20 (#25): ch05's four skeleton reskins took the roster from 7 to 10 and
# the single row at y=9 held exactly 7 on a 15-wide map. That doc already named the fix -- "a
# second row lifts it immediately" -- so this is the lift, not a redesign.
#
# y=1, and the row is chosen by ELIMINATION rather than by feel. `TEST_SPAWN_POSITIONS` puts the
# player formation on y=3..7, so every row in that band is spoken for; y=9 is the first bench row
# and a second row beside it would put two foes within one bait tile of each other. That leaves
# 0, 1 and 2, and y=1 keeps a clear row on both sides -- bait tiles at y=0 and y=2 are free, and
# nothing is adjacent to the party.
#
# (An earlier cut of this put the row at y=6, which shares a row with four player spawns and
# missed them only because those sit on ODD x while the bench uses EVEN. One added seat would
# have stacked a foe on a party member, and `assert_sandbox_bench_fits` checks map bounds only.
# `test_the_bench_never_seats_a_foe_on_a_player` now makes that collision a build failure.)
#
# The real ceiling is still SMS VRAM (64 slots, two counters growing toward each other), and ten
# 16x16 creatures are nowhere near it; `recordunitlist` FAILs if the counters ever cross.
SANDBOX_FOE_POSITIONS = [(2, 9), (4, 9), (6, 9), (8, 9), (10, 9), (12, 9), (14, 9),
                         (2, 1), (4, 1), (6, 1), (8, 1), (10, 1), (12, 1), (14, 1)]


def sandbox_map_size(campaign):
    """(w, h) of the map the TESTCH sandbox actually runs on -- READ, not remembered.

    It is NOT vanilla chapter 1's map: `inject_winter_tileset` repoints the test chapter at
    our own `ChTestSnowMap`. They are the same 15x10 today, so a hardcoded constant is right
    by accident -- and the bench is now exactly 7 of 7 full, which makes widening that
    snowfield the obvious next move. A constant would then reject legitimate tiles."""
    with open(os.path.join(REPO, 'campaigns', campaign, 'maps',
                           'ch-test-snowfield.json'), encoding='utf-8') as f:
        m = json.load(f)
    return m['width'], m['height']


def assert_sandbox_bench_fits(campaign):
    """Every bench tile is on the sandbox map. Called from the injector that stages them."""
    w, h = sandbox_map_size(campaign)
    for x, y in SANDBOX_FOE_POSITIONS:
        if not (0 <= x < w and 0 <= y < h):
            sys.exit('ERROR: sandbox bench tile (%d,%d) is outside the %dx%d sandbox map '
                     '(campaigns/%s/maps/ch-test-snowfield.json) -- a foe staged there '
                     'cannot be reached, and recordenemy fails walking to it'
                     % (x, y, w, h, campaign))


def _next_sandbox_tile(tiles, who):
    """The next free sandbox foe tile, or a loud failure. The bench is a fixed strip of
    tiles; running out silently would stack two foes and make `recordenemy` bait the wrong
    one, which is the failure the whole per-pid selection exists to prevent."""
    try:
        return next(tiles)
    except StopIteration:
        sys.exit('ERROR: sandbox foe bench is full (%d tiles) -- %s has nowhere to stand; '
                 'add a tile to SANDBOX_FOE_POSITIONS' % (len(SANDBOX_FOE_POSITIONS), who))


def _sandbox_foe_roster(campaign):
    """A UnitDefinition[] body deploying one hostile of each enemy_class_reskins slot, so the
    TESTCH sandbox is the single battle-anim bench (`recordenemy` baits any of them). Generic
    autolevel monsters (charIndex 0x80), FACTION_ID_RED, HOLD ai so they stay put to be baited,
    iron loadout by the reskin's BASE weapon type. A reskin whose base has no mapped weapon is
    skipped (never a foe)."""
    entries = []
    # ONE cursor over the tiles, advanced only when a row is actually emitted. `zip` here used
    # to burn a tile on every weapon-less reskin it skipped, so the raw-pid loop below (which
    # indexed by len(entries)) could hand a later creature a tile the zip had already spent.
    # Harmless only while the skipped reskin is LAST; one more reskin after it stacks two foes
    # on a tile, and a seventh raises IndexError.
    assert_sandbox_bench_fits(campaign)
    tiles = iter(SANDBOX_FOE_POSITIONS)
    for rk in enemy_class_reskins(campaign):
        weapon = CLASS_RESKIN_FOE_WEAPON.get(rk['base'])
        if not weapon:
            continue
        x, y = _next_sandbox_tile(tiles, rk['slot'])
        entries.append(
            '    {\n'
            '        .charIndex = 0x80,\n'                 # generic autolevel monster slot
            '        .classIndex = %s,\n'                  # the reskin's clone class (its sprite+anim)
            '        .leaderCharIndex = 0x80,\n'
            '        .autolevel = 1,\n'
            '        .allegiance = FACTION_ID_RED,\n'
            '        .level = 3,\n'
            '        .xPosition = %d,\n'
            '        .yPosition = %d,\n'
            '        .redaCount = 0,\n'
            '        .items = { %s },\n'
            '        .ai = {0x3, 0x3, 0x9, 0x20},\n'       # attack in place, never move -> baitable
            '    },' % (rk['slot'], x, y, ', '.join(weapon)))
    # Named RAW-PID creatures bench here too, and they must be deployed under their OWN pid.
    # A class-level reskin animates off its class, so the generic 0x80 monster charIndex above
    # is fine for it; a raw-pid creature's anim binds per-CHARACTER through `_u25`, so the same
    # row under 0x80 would deploy a plain Gwyllgi playing the STOCK HOUND -- a bench that
    # proves the opposite of what it was run for. No autolevel: these are named units whose
    # level is the chapter's.
    for uid, (chapter_yaml, pid) in sorted(RAW_PID_BATTLE_ANIMS.items()):
        unit = _chapter_unit(campaign, chapter_yaml, uid)
        if not unit.get('battle_anim'):
            continue
        x, y = _next_sandbox_tile(tiles, uid)
        items = [CH05_ITEM_IDS[i['fe_base']] for i in unit.get('inventory') or []]
        entries.append(
            '    {\n'
            '        .charIndex = %s,\n'
            '        .classIndex = %s,\n'
            '        .leaderCharIndex = %s,\n'
            '        .allegiance = FACTION_ID_RED,\n'
            '        .level = %d,\n'
            '        .xPosition = %d,\n'
            '        .yPosition = %d,\n'
            '        .redaCount = 0,\n'
            '        .items = { %s },\n'
            '        .ai = {0x3, 0x3, 0x9, 0x20},\n'       # attack in place, never move -> baitable
            '    },' % (pid, CH05_CLASS_IDS.for_entry(unit), pid,
                        int(unit.get('level', 1)), x, y, ', '.join(items)))
    return '{\n' + '\n'.join(entries) + '\n    { 0 },\n}'


def inject_test_chapter(campaign, verbose=True, lord_boot=False):
    """Rewrite Ch1's ally roster to our classed cast and disable Ch1 tutorials."""
    # Build the cast roster in PORTRAIT_MAP order, skipping name-only units (no class).
    units = []
    for unit_id, slot in PORTRAIT_MAP.items():
        unit = load_unit(campaign, unit_id)
        unit.setdefault('id', unit_id)
        class_enum = class_enum_for(unit)
        if class_enum is None:
            continue
        if class_enum not in CLASS_LOADOUT:
            sys.exit('ERROR: no test loadout for %s (unit %s)' % (class_enum, unit_id))
        units.append((unit_id, slot, class_enum, unit))
    if len(units) > len(TEST_SPAWN_POSITIONS):
        sys.exit('ERROR: %d classed cast > %d test spawn positions'
                 % (len(units), len(TEST_SPAWN_POSITIONS)))

    leader = 'CHARACTER_%s' % units[0][1].upper()  # the lord slot anchors the roster
    entries = []
    for (unit_id, slot, class_enum, unit), (x, y) in zip(units, TEST_SPAWN_POSITIONS):
        items = ', '.join(CLASS_LOADOUT[class_enum])
        entries.append(
            '    {\n'
            '        .charIndex = CHARACTER_%s,\n'
            '        .classIndex = %s,\n'
            '        .leaderCharIndex = %s,\n'
            '        .allegiance = FACTION_ID_BLUE,\n'
            '        .level = %d,\n'
            '        .xPosition = %d,\n'
            '        .yPosition = %d,\n'
            '        .redaCount = 0,\n'
            '        .items = { %s },\n'
            '    },' % (slot.upper(), deploy_class_for(unit), leader,
                        int(unit.get('fe_stats', {}).get('level', 1)),
                        x, y, items))
    roster = '{\n' + '\n'.join(entries) + '\n    { 0 },\n}'

    with open(CH1_UDEFS_H, encoding='utf-8') as f:
        udefs = f.read()
    udefs = _replace_brace_block(
        udefs, 'UnitDef_Event_Ch1Ally[] =', roster, CH1_UDEFS_H)
    # Make the sandbox the single battle-anim bench: replace the Ch1 foe roster with one
    # hostile of every enemy_class_reskins slot (the begin scene already LOAD1s this symbol),
    # so `recordenemy` can capture any reskinned class's anim without a chapter-specific setup.
    foes = _sandbox_foe_roster(campaign)
    udefs = _replace_brace_block(
        udefs, 'UnitDef_Event_Ch1Enemy[] =', foes, CH1_UDEFS_H)
    with open(CH1_UDEFS_H, 'w', encoding='utf-8') as f:
        f.write(udefs)

    # Empty every per-chapter event list so nothing references the removed cutscene
    # units or triggers a win/lose condition. Each is an EventListScr[] terminated by
    # END_MAIN; the tutorial list is a pointer array terminated by NULL.
    with open(CH1_EVENTINFO_H, encoding='utf-8') as f:
        info = f.read()
    for name in ('EventListScr_Ch1_Turn', 'EventListScr_Ch1_Character',
                 'EventListScr_Ch1_Location', 'EventListScr_Ch1_Misc'):
        info = _replace_brace_block(info, name + '[] =', '{\n    END_MAIN\n}',
                                    CH1_EVENTINFO_H)
    info = _replace_brace_block(
        info, 'EventListScr_Ch1_Tutorial[] =', '{\n    NULL\n}', CH1_EVENTINFO_H)
    with open(CH1_EVENTINFO_H, 'w', encoding='utf-8') as f:
        f.write(info)

    # Minimal beginning scene: deploy the cast and hand over control. (Vanilla's scene
    # ran a scripted fight + forced moves that wiped our units.) LOAD1 deploys the
    # chapter's player UnitDefinition; ENUN waits for the placement; ENDA ends.
    with open(CH1_EVENTSCRIPT_H, encoding='utf-8') as f:
        script = f.read()
    if lord_boot:
        # DEBUG fast-boot (#46): a pure off-map scene that mirrors the REAL ch1 lord-select
        # sequence (the SHARED _lord_select_event_seq -- explainer + re-pick loop) over the
        # scenic BG, minus only the post-Yes map build (no deploy: the menu reads
        # CharacterData, not loaded units). Verifies the explainer + "Will N lead?" confirm
        # in-engine, not just the menu. Compile-time-only iteration on the screen.
        minimal_begin = ('{\n'
                         + _lord_select_event_seq(CH01_LORDSEL_BG, LORDSEL_EXPLAINER_MSG)
                         + '    FADI(16)\n'
                           '    ENDA\n'
                           '}')
    else:
        minimal_begin = ('{\n'
                         '    LOAD1(1, UnitDef_Event_Ch1Enemy)\n'   # keep the vanilla foes (reskinned) so the sandbox is combat-ready
                         '    ENUN\n'
                         '    LOAD1(1, UnitDef_Event_Ch1Ally)\n'
                         '    ENUN\n'
                         '    ENDA\n'
                         '}')
    script = _replace_brace_block(
        script, 'EventScr_Ch1_BeginningScene[] =', minimal_begin, CH1_EVENTSCRIPT_H)
    with open(CH1_EVENTSCRIPT_H, 'w', encoding='utf-8') as f:
        f.write(script)

    # The boot cut + New-Game redirect (so a fresh boot lands on the title and New Game drops
    # straight onto this sandbox chapter) are the single owner _configure_boot()'s job, called
    # once from main() -- not re-decided here.
    if verbose:
        for unit_id, slot, class_enum, _ in units:
            print('  %-10s -> Ch1 ally (%s as %s)'
                  % (unit_id, slot, class_enum.replace('CLASS_', '')))
        foe_classes = [rk['slot'].replace('CLASS_', '') for rk in enemy_class_reskins(campaign)
                       if rk['base'] in CLASS_RESKIN_FOE_WEAPON]
        print('  sandbox foes (recordenemy bench): %s' % ', '.join(foe_classes))
        print('  Ch1 stripped to sandbox; boot attract + Magvel intro cut; '
              'New Game boots into Ch1')
