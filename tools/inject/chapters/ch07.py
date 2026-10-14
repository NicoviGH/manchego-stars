"""Chapter 7 (#27): its injector and everything only it reads.
"""
import os
import sys

from inject.cast import CLASS_LOADOUT, _classed_cast, ENEMY_BASE_SLOT
from inject.chapter_frame import write_event_group
from inject.chapter_ids import CH07_CHAPTER_YAML, CH07_GOAL_STATUS_MSG, CH07_GOAL_WINDOW_MSG
from inject.class_ids import ChapterClassIds
from inject.decomp import _replace_brace_block, REPO, ITEM_ENUM
from inject.hosting import _load_chapter_yaml, _retarget_host_chapter
from inject.hosts import CH07_EVENT_GROUP, CH07_HOST_INDEX
from inject.maps import _register_chapter_map
from inject.paths import CH07_EVENTINFO_H, CH07_EVENTSCRIPT_H, TEXTS_TXT
from inject.scenes import chapter_boss, write_frame_texts
from inject.text import dev_placeholder_scene, write_nameplate
from inject.units import _ally_unit_entry, declare_unit_table, _deploy_cap_entries, enemy_rows
from inject.villages import chapter_location_events


CH07_BEGINNING_SCRIPT = 'EventScr_Ch8_BeginningScene'
CH07_ENDING_SCRIPT = 'EventScr_Ch8_EndingScene'
CH07_PREP_SCRIPT = 'EventScr_08591FD8'           # the shared CLEAN/PREP/CLEAN script (cf. ch06)

CH07_ALLY_TABLE = 'MS_Ch07DeployCap'             # the never-LOADed PREP cap template
CH07_BOOT_SEED_TABLE = 'MS_Ch07BootSeed'         # --ch07-boot only: an armed party from a cold start
CH07_LINE_TABLE = 'MS_Ch07Line'                  # vanilla Ch7's 19, re-dressed as Bremen's militia

CH07_LAYOUT = ('Ch07BremenMap', 'ch07-blood-in-bremen')   # (asset label, maps/ stem)
# The goal donor is slot 8 ITSELF: vanilla Ch7's own Seize template, on the slot we host, which
# nothing before inject_ch07 writes. Its window text is replaced by ours below either way.
CH07_GOAL_DONOR = CH07_HOST_INDEX
CH07_SEIZE_TEXT = 'Seize hall'                   # vanilla's "Seize gate", for the Town Hall door

# Dorbulgruf rides Murray, vanilla Ch7's boss on the same door (ENEMY_BASE_SLOT). Everyone else
# shares the slot's autolevelled generic, as vanilla Ch7 does.
CH07_BOSS_PID = ENEMY_BASE_SLOT['dorbulgruf']
CH07_GENERIC_PID = '0x80'

CH07_CLASS_IDS = ChapterClassIds('ch07')

# Vanilla Ch7's two talk-only houses keep vanilla's own scripts (MSG 0xA06 / 0xA07), still in
# slot 7's eventscript, until the dialogue pass gives them Bremen's lines. In the YAML's order:
# the west house (1,15), then the south-east one (17,21).
CH07_HOUSE_SCRIPTS = ('EventScr_089F2E6C', 'EventScr_089F2E94')
# Two of vanilla's archers LOAD on the hall door and walk out to their posts (REDA_088B6E68/70).
CH07_HALL_DOOR = (9, 4)
CH07_HALL_ARCHERS = (('bremen-archer', 1), ('bremen-archer', 2))


def ch07_reda_symbol(enemy_id, index):
    return 'MS_Ch07HallDoor_%s_%d' % (enemy_id.replace('-', '_'), index)


def ch07_enemy_pid(enemy, _index=0):
    """The boss on Murray's slot; the rest on the generic, as vanilla Ch7."""
    return CH07_BOSS_PID if enemy.get('is_boss') else CH07_GENERIC_PID


def inject_ch07(campaign, boot=False, verbose=True):
    """Host Ch7 "Blood in Bremen" (#27) on slot 8: vanilla Ch7's own layout retiled to Bremen
    (ADR 0341), vanilla Ch7's own nineteen as the town's militia, the real PREP deploy on
    vanilla's ten start tiles, its two ballistae (the YAML's `traps:`) and Seize(9,4).

    Scenes are the next pass: the beginning is LOMA + the line + PREP, and the ending parks
    on the dev placeholder until ch08 hosts.
    """
    maps_dir = os.path.join(REPO, 'campaigns', campaign, 'maps')
    chap = _load_chapter_yaml(campaign, CH07_CHAPTER_YAML)

    # 1. Map: snowy-bern is registered by inject_winter_tileset; point slot 8 at the layout
    #    and keep its own Seize goal.
    indices = _register_chapter_map(maps_dir, CH07_LAYOUT,
                                    'Manchego Stars ch07 Bremen layout (#27)')
    obj_idx, pal_idx, cfg_idx, layout_idx = indices
    host = _retarget_host_chapter(
        CH07_HOST_INDEX, CH07_GOAL_DONOR, 'seize',
        'ERROR: slot %d goal is not vanilla Ch7\'s Seize template' % CH07_GOAL_DONOR,
        indices, chap['chapter_number'], CH07_EVENT_GROUP,
        (CH07_GOAL_WINDOW_MSG, CH07_GOAL_STATUS_MSG))

    # 2. Rosters: the never-LOADed cap template PREP reads, the boot seed, and the line.
    cast, _ = _classed_cast(campaign, available_at=chap['chapter_number'])
    for uid, _slot, ce, _dce, _level in cast:
        if ce not in CLASS_LOADOUT:
            sys.exit('ERROR: no loadout for %s (ch07 field roster %s)' % (ce, uid))
    leader = 'CHARACTER_%s' % cast[0][1].upper()
    cap_rows = _deploy_cap_entries(chap, cast, leader, 'ch07')
    declare_unit_table(CH07_ALLY_TABLE, cap_rows,
                       'ch07 PREP deploy-cap template (never LOADed; the CAP is the parity)')
    slots = chap['deployment']['deploy_slots']
    seed_rows = [_ally_unit_entry(leader, slot, dce, level, x, y,
                                  ', '.join(CLASS_LOADOUT[ce]),
                                  ' /* %s -- ch07 boot party seed (armed; PREP re-picks) */' % uid)
                 for (uid, slot, ce, dce, level), (x, y) in zip(cast, slots)]
    declare_unit_table(CH07_BOOT_SEED_TABLE, seed_rows,
                       'ch07 --ch07-boot armed party seed (cold-start PREP fodder)')
    spawns = {key: CH07_HALL_DOOR for key in CH07_HALL_ARCHERS}
    line_rows = enemy_rows(chap, CH07_CLASS_IDS, ITEM_ENUM, ch07_enemy_pid, spawns=spawns,
                           reda_symbol=ch07_reda_symbol)
    by_id = {e['id']: e for e in chap['enemy_units']}
    redas = [(ch07_reda_symbol(eid, i),) + tuple(by_id[eid]['positions'][i])
             for eid, i in CH07_HALL_ARCHERS]
    declare_unit_table(CH07_LINE_TABLE, line_rows,
                       'ch07 turn-1 line: vanilla Ch7\'s nineteen as Bremen\'s militia, two '
                       'archers walking out of the hall', redas=redas)

    # 3. The event group. Every list not named is written empty.
    write_event_group('ch07', CH07_EVENTINFO_H, CH07_EVENT_GROUP, lists={
        'locationBasedEvents': chapter_location_events(chap, {}, house_scripts=CH07_HOUSE_SCRIPTS,
                                                       seize=True),
        'miscBasedEvents': '{\n    CauseGameOverIfLordDies\n    END_MAIN\n}',
    }, roster=CH07_ALLY_TABLE, scenes=(CH07_BEGINNING_SCRIPT, CH07_ENDING_SCRIPT))

    # 4. Scenes. No FADU before the prep CALL: the shared prep prologue fades to black itself.
    with open(CH07_EVENTSCRIPT_H, encoding='utf-8') as f:
        script = f.read()
    seed_load = ('    LOAD1(0x1, %s) /* --ch07-boot: found an armed party */\n'
                 '    ENUN\n' % CH07_BOOT_SEED_TABLE) if boot else ''
    beginning = ('{\n'
                 '    SVAL(EVT_SLOT_B, 0x0) /* map camera origin for the reload */\n'
                 '    LOMA(0x%X) /* RestartBattleMap -- build the ch07 map fresh */\n'
                 % CH07_HOST_INDEX
                 + '    LOAD1(0x1, %s) /* vanilla Ch7\'s nineteen */\n'
                   '    ENUN\n' % CH07_LINE_TABLE
                 + seed_load
                 + '    CALL(%s) /* preparations: pick %d; lord force-deployed */\n'
                 % (CH07_PREP_SCRIPT, chap['deployment']['deploy_limit'])
                 + '    ENUT(8)\n    EVBIT_T(7)\n    ENDA\n}')
    script = _replace_brace_block(script, CH07_BEGINNING_SCRIPT + '[] =', beginning,
                                  CH07_EVENTSCRIPT_H)
    script = _replace_brace_block(
        script, CH07_ENDING_SCRIPT + '[] =',
        '{\n    FADI(16) /* the hall is taken */\n' + dev_placeholder_scene() + '    ENDA\n}',
        CH07_EVENTSCRIPT_H)
    with open(CH07_EVENTSCRIPT_H, 'w', encoding='utf-8') as f:
        f.write(script)

    # 5. Texts: title, goal pair, card, and Murray's nameplate (Dorbulgruf rides his slot).
    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    write_frame_texts(lines, host, chap, CH07_SEIZE_TEXT, CH07_SEIZE_TEXT)
    write_nameplate(lines, CH07_BOSS_PID.replace('CHARACTER_', ''), chapter_boss(chap))
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    if verbose:
        sx, sy = chap['objective']['seize_tile']
        print('  ch07 map (obj1=%d pal=%d cfg=%d layout=%d) hosted on chapter %d; Seize(%d,%d) '
              'WIN wired, PREP deploy cap %d%s + %d line'
              % (obj_idx, pal_idx, cfg_idx, layout_idx, CH07_HOST_INDEX, sx, sy, len(cap_rows),
                 ' (boot-seeded party)' if boot else '', len(line_rows)))
