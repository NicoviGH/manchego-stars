"""Chapter 2 (#22): its injector and everything only it reads.
"""
import os
import sys

from PIL import Image

import fe8_talk_font
import portrait_tool
from inject.cast import (
    _bust_dir, _classed_cast, class_enum_for, CLASS_LOADOUT, deploy_class_for, load_unit,
    PORTRAIT_MAP)
from inject.chapter_ids import (
    CH02_BOSS_SLOT, CH02_CHWINGA, CH02_CHWINGA_PORTRAIT_SLOT, CH02_CHWINGA_SPRITE_SRC,
    CH02_GOAL_STATUS_MSG, CH02_GOAL_WINDOW_MSG, CH02_MINIBOSS_SLOT, CH02_OPENING_BG,
    CH02_TURN1_MSGS, CH02_VILLAGE_SLOTS)
from inject.decomp import _replace_brace_block, REPO
from inject.hosting import _load_chapter_yaml, _retarget_host_chapter, recruit_chapter_number
from inject.hosts import CH02_EVENT_GROUP, CH02_HOST_INDEX, CH03_HOST_INDEX
from inject.maps import (
    _drawn_block, _inject_tile_changes, _map_changes_tileset, _register_chapter_map,
    _snowy_metatile_for)
from inject.paths import (
    CH3_EVENTINFO_H, CH3_EVENTSCRIPT_H, EVENTS_UDEFS_C, PORTRAIT_DIR, TEXTS_TXT)
from inject.recruit import ON_MAP_RECRUIT_VIA
from inject.scenes import (
    _emit_scene_beats, _make_fid, _prepend_defeat_quote, _scenic_beat_calls, _split_event_beats,
    _stage_beat, _write_chapter_title_card)
from inject.text import (
    _fid_tag, _script_to_message, display_name, goal_window_body, name_message_body,
    set_message_body, vanilla_name_text_id)
from inject.units import (
    _ally_unit_entry, _deploy_cap_entries, _enemy_unit_entry, enemy_ai_initialiser)
from inject.villages import (
    DEFAULT_VILLAGE_SPEAKER, location_events, village_boxes, village_reward_item, village_script)


CH02_LAYOUT = ('Ch02ColdWelcomeMap', 'ch02-cold-welcome')  # (asset label, maps/ stem)
CH02_CHAPTER_YAML = 'ch02-cold-welcome.yaml'
# Off-map recruit join-LOAD (#23): Baxby (won over in the ch01-ending cutscene) enters the
# saved party HERE, his first prep roster. A free vanilla-Ch3-region UnitDef symbol (externed,
# unused by our ch02 flow); LOAD1'd blue before the PREP CALL -> Pick Units lists him. The join
# tile is a walkable NW deploy slot (PREP hides everyone and re-picks, so the tile only needs
# to be valid + collision-free at LOAD time -- clear of the chwinga/raiders).
CH02_RECRUIT_JOIN_SYMBOL = 'UnitDef_088B476C'
CH02_RECRUIT_JOIN_POS = (2, 4)
# Vellynne Harpell (recurring Brotherhood NPC) has no map unit in ch02; her CUTSCENE FACE
# rides FID_Ismaire -- a regal vanilla woman absent from our ch00-08 chapters, collision-free.
# Her custom bust (#19) is OPTIONAL: this is a flagged placeholder until that art lands.
CH02_VELLYNNE_SLOT = 'ISMAIRE'
CH02_FISHER_FID = '[FID_VillagerOldMan]'   # the brittle Targos fisher -- generic villager mug
CH02_ENDING_BG = 'BG_MS_TARGOS_WINTER'     # Targos at nightfall -- vendored snow-town (inject_backgrounds)
# Enemy AI byte vectors + class/item maps (FE8-valid, mirrored from ch01's proven set).
CH02_CLASS_IDS = {'brigand': 'CLASS_BRIGAND', 'archer': 'CLASS_ARCHER',
                  'pegasus_knight': 'CLASS_PEGASUS_KNIGHT',
                  # the chwinga chassis: Mov 5 like Garcia, staff at D so they heal EACH
                  # OTHER (a staff cannot target its own carrier -- cp_staff.c), and it
                  # wears Sclorbo's greenified anim. They were Mov-7 fliers, which gave
                  # the units that need rescuing the best escape in the chapter.
                  'priest': 'CLASS_PRIEST'}
CH02_ITEM_IDS = {'iron-axe': 'ITEM_AXE_IRON', 'steel-axe': 'ITEM_AXE_STEEL',
                 'iron-bow': 'ITEM_BOW_IRON', 'vulnerary': 'ITEM_VULNERARY',
                 'slim-lance': 'ITEM_LANCE_SLIM', 'hand-axe': 'ITEM_AXE_HANDAXE',
                 'red-gem': 'ITEM_REDGEM', 'elixir': 'ITEM_ELIXIR', 'pure-water': 'ITEM_PUREWATER',
                 'heal-staff': 'ITEM_STAFF_HEAL'}
CH02_GENERIC_PID = '0x8e'    # vanilla slot-3 generic-minion charIndex (autolevelled trash)
CH02_VILLAGE_CHWINGA = 'chwinga-glimmer'
# Dead vanilla Ch3 scripts (slot 3 is ch02's host and inject_ch02 blanks its event lists).
# 0xAC0/0xAC1 are the first two ids of ch02's block -- it had none until the pool widened.

# One event id per hut. It records the visit, disarms that hut's raider hook (Village() puts
# the same eid on the destruction LOCA), and -- for the south hut -- answers whether
# Glimmerfrost was reached in time to hand over her charm. ch02 sets no other event flag, so
# 9 and 10 are free (checked: no ENUT/CHECK_EVENTID anywhere in its host).
# The mug each hut's RESIDENT wears. A chwinga inhabitant brings her own -- see
# CH02_CHWINGA_PORTRAIT_SLOT, which dresses MANSEL's slot with the green bust, so
# Glimmerfrost speaks (wordlessly) with her own face rather than a villager stand-in.
# Three distinct villager mugs across the chapter: these two plus the ending's fisher.
CH02_VILLAGE_FLAGS = {
    'targos-hut-south': 'EVFLAG_TMP(9)',
    'targos-hut-east':  'EVFLAG_TMP(10)',
}
# The 3x2 ruins block in snowy-bern: metatiles 929-931 over 961-963 (one row apart), the
# picture the tileset artist drew to fit together. VERIFIED by _drawn_block on every build,
# so a renumbered tileset fails loudly instead of tiling one corner across the footprint.
CH02_RUIN_ORIGIN = 929


def ch02_map_changes(chap, maps_dir):
    """ch02's tile flips: a Targos hut SACKED, and a hut visited.

    Same anatomy as ch05's reliquaries, and the same two correctness arguments.

    ORDER: ruins (3x2) first, then the 1x1 doors. GetMapChangeIdAt keeps the LAST region
    covering a tile (bmtrick.c), and the 3x2 overlaps its own door -- doors-first would make
    VISITING a hut collapse it.

    FOOTPRINT: AiPillageAction looks the change up at (x, y - 1), the tile above the door where
    Village()'s destruction LOCA sits, so a change on the door alone is never found and a
    sacked hut would keep standing and keep its gift.

    RUINS_REGULAR is the lost state, not RUINS_VILLAGE: FE8 reads both "can a unit Visit here"
    (CanUnitVisit) and "is this worth pillaging" (gTerrainList_LootableVillages) off the
    TERRAIN, and RUINS_VILLAGE sits in BOTH lists -- a hut ruined into it would be lootable
    again next turn.
    """
    tileset = _map_changes_tileset(maps_dir, CH02_LAYOUT)
    villages = chap.get('villages', [])
    changes = [(x - 1, y - 1, 3, 2,
                _drawn_block(tileset, CH02_RUIN_ORIGIN, (3, 2), 'TERRAIN_RUINS_REGULAR',
                             '%s sacked' % v['id']),
                '%s sacked -- raided before the party reached it' % v['id'])
               for v in villages for x, y in [v['tile']]]
    changes += [(v['tile'][0], v['tile'][1], 1, 1,
                 [_snowy_metatile_for(tileset, 'TERRAIN_VILLAGE_CLOSED')],
                 '%s visited' % v['id'])
                for v in villages]
    return changes


def ch02_location_events(chap):
    """ch02's Location list: the two Targos huts. Empty until 2026-08-30, which is why the
    map drew huts that backed nothing and why six pillaging raiders had nowhere to go but
    the protected chwinga."""
    return location_events(chap.get('villages', []),
                           {vid: slot[0] for vid, slot in CH02_VILLAGE_SLOTS.items()},
                           flags=CH02_VILLAGE_FLAGS)
# blue glow ramp -> spirit-green, keyed by SOURCE RGB (robust to palette reordering); the
# same ramp as the map sprite. Everything else (fur collar, tan robe, red tassels) untouched.
CH02_CHWINGA_GLOW_RECOLOR = {
    (96, 211, 219): (150, 230, 160), (113, 188, 214): (140, 205, 150),
    (81, 165, 185): (100, 185, 120), (63, 141, 165): (78, 155, 95),
    (57, 117, 138): (58, 120, 78),
}
# Cutscene message ids -- the dead vanilla Ch3 scene/talk/turn texts our host overwrites
# (referenced ONLY by ch3-eventscript.h scenes we replace; 0x993/0x994 are LIVE battle
# quotes in data_battlequotes.c and are deliberately NOT in this pool -- see decisions.md
# "Ch2 hosting"). Opening (Vellynne): card + 3 beats. Turn-1 archer tutorial: 2. Rear bark:
# 1. Ending (Targos): card + 4 beats. Boss death quote: 1.
CH02_OPENING_CARD_MSG = 0x98b
CH02_OPENING_MSGS = (0x98c, 0x98e, 0x98d)     # A (Vellynne/RBG), B (Meesmickle/Braulo), C (chwinga: Sclorbo's kin + Marty)
CH02_BARK_MSG = 0x990                         # Wolfram's turn-3 rear-ambush bark (over map)
CH02_ENDING_CARD_MSG = 0x995
CH02_ENDING_MSGS = (0x996, 0x997, 0x998, 0x999)  # A fisher, B Rootis, C narration(#58), D RBG
CH02_BOSS_DEATH_MSG = 0x99a                   # Halvar's death quote (gDefeatTalkList, slot 3)


def ch02_chwinga_identities(chap):
    """{id: {name, fe_name, ...}} for every chwinga the chapter names, wherever it stands.

    Two are green units and one is a village inhabitant, and BOTH need a face and a name --
    Glimmerfrost speaks in her hut. Merging here rather than reading green_allies means
    moving a chwinga between the field and a village stays a YAML edit.
    """
    out = {g['id']: g for g in chap.get('deployment', {}).get('green_allies', [])}
    for village in chap.get('villages', []):
        who = village.get('inhabitant')
        if isinstance(who, dict):
            out.setdefault(who['id'], who)
    return out


def inject_ch02_chwinga_faces(campaign, verbose=True):
    """Dress the 3 green chwinga (CH02_CHWINGA) with Sclorbo's bust recoloured green + their
    fe_names. The bust is build-derived from sclorbo.png -- the blue glow ramp hue-shifted to
    spirit-green, the same swap as the map sprite -- so the single source stays Sclorbo's
    portrait (no committed derived asset). Each chwinga's vanilla portrait slot is collision-
    free; names come from the ch02 YAML (deployment.green_allies fe_name)."""
    bust_path = os.path.join(_bust_dir(campaign), CH02_CHWINGA_SPRITE_SRC + '.png')
    if not os.path.isfile(bust_path):
        if verbose:
            print('  (no %s bust yet; chwinga keep vanilla faces/names)' % CH02_CHWINGA_SPRITE_SRC)
        return
    # 1. recolour Sclorbo's bust: blue glow ramp -> spirit-green (by source RGB).
    im = Image.open(bust_path).convert('P')
    pal = list(im.getpalette()[:48])
    for i in range(16):
        rgb = tuple(pal[i * 3:i * 3 + 3])
        if rgb in CH02_CHWINGA_GLOW_RECOLOR:
            pal[i * 3:i * 3 + 3] = list(CH02_CHWINGA_GLOW_RECOLOR[rgb])
    chwinga_bust = im.copy()
    chwinga_bust.putpalette(pal)
    tileset, mouth, chibi, pal_bytes = portrait_tool.generate(chwinga_bust, static_portrait=True)

    # 2. dress each chwinga's collision-free portrait slot with the one shared green bust.
    for vanilla in CH02_CHWINGA_PORTRAIT_SLOT.values():
        base = os.path.join(PORTRAIT_DIR, 'portrait_' + vanilla)
        tileset.save(base + '_tileset.png')
        mouth.save(base + '_mouth.png')
        chibi.save(base + '_chibi.png')
        with open(base + '_palette.agbpal', 'wb') as f:
            f.write(pal_bytes)

    # 3. name each chwinga slot from the ch02 YAML fe_name (Mote / Rime / Glimmer).
    chap = _load_chapter_yaml(campaign, CH02_CHAPTER_YAML)
    by_id = ch02_chwinga_identities(chap)
    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    for uid, slot in CH02_CHWINGA:
        set_message_body(lines, vanilla_name_text_id(slot),
                         name_message_body(display_name(by_id[uid])))
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    if verbose:
        names = ', '.join(display_name(by_id[uid]) for uid, _ in CH02_CHWINGA)
        print('  chwinga faces -> %s (shared green bust + names: %s)'
              % (', '.join(CH02_CHWINGA_PORTRAIT_SLOT.values()), names))


def offmap_join_recruits(campaign, chapter_number):
    """Cast members that FIRST enter the persistent party OFF the map at `chapter_number`:
    recruits whose recruit chapter is the one immediately before (so cast_available_at first
    lists them now) and whose join method is off-map (recruit.via not in ON_MAP_RECRUIT_VIA).
    Returns [(unit_id, slot, class_enum, deploy_class_enum, level)], PORTRAIT_MAP order.

    Each such unit needs a beginning-scene LOAD1 so it enters the saved roster -- the prep
    availability filter only sizes the deploy cap; it never LOADs anyone. Keyed to the
    immediately-preceding chapter (contiguous hosted chapters, our MVP) so a unit is joined
    exactly once, the first chapter it rides the prep roster (no re-LOAD -> no duplicate)."""
    out = []
    for unit_id, slot in PORTRAIT_MAP.items():
        unit = load_unit(campaign, unit_id)
        unit.setdefault('id', unit_id)
        class_enum = class_enum_for(unit)
        if class_enum is None:
            continue
        rc = recruit_chapter_number(campaign, unit)
        if rc is None or rc != chapter_number - 1:
            continue   # not a recruit, or not newly available at THIS chapter
        via = (unit.get('recruit') or {}).get('via')
        if via in ON_MAP_RECRUIT_VIA:
            continue   # on-map talk recruit -- self-joins via CUSA, persists naturally
        out.append((unit_id, slot, class_enum, deploy_class_for(unit),
                    int(unit.get('fe_stats', {}).get('level', 1))))
    return out


def inject_ch02(campaign, verbose=True):
    """Wire Ch2 "Cold Welcome" (#22) onto chapter slot 3 (ch01's MNC2(0x3) target).

    Simpler than inject_ch01: the founding party PERSISTS from ch01 (no cast re-LOAD, no
    lord-select menu) -- only the ch01 cutscene recruit Baxby gets an explicit off-map
    join-LOAD here (step 2a-bis), his first prep roster. The win is DefeatAll (no Seize). The slot-3 host goal is
    swapped to vanilla slot-4's defeat_all template, the vanilla Ch3 Seize(14,1) is
    dropped (so engine CountRedUnits() drives the rout win), and the ch01-chosen lord
    is auto-force-deployed by the flag-driven IsCharacterForceDeployed_ hook
    (_inject_lord_select_engine) -- no per-chapter wiring beyond the
    CauseGameOverIfLordDies that already sits in EventListScr_Ch3_Misc.

    The protect layer is three GREEN chwinga (pegasus chassis, vanilla Colm table
    088B4718 repurposed) on distinct NPC slots; each surviving chwinga gifts a charm
    (Red Gem / Elixir / Pure Water) at the ending scene via CHECK_ALIVE -> GIVEITEMTO
    (per-unit soft-fail, no game over). Enemies are vanilla Ch2's exact mix, reflavored
    chardalyn berserkers. Reinforcements move to the empty table 088B4758 (088B4718 is
    now the chwinga).

    DEFERRED checkpoints (flagged, not in this pass): the DIALOGUE REGROUND -- the locked
    cutscene text still frames the dropped sled + "snow wolves" and lacks a chwinga intro
    beat (Nicolas co-write via the dialogue-pass skill; wired as placeholder meanwhile);
    the chwinga art (map sprite + portrait + name-text over DARA/KLIMT/MANSEL, #38/#39);
    Vellynne's cutscene bust (#19, placeholder vanilla face here); the chardalyn map-sprite
    reskin (vanilla brigand sprite for now); and the in-game load-test.
    """
    maps_dir = os.path.join(REPO, 'campaigns', campaign, 'maps')
    chap = _load_chapter_yaml(campaign, CH02_CHAPTER_YAML)

    # 0. Cutscene beat splits, consumed from the locked chapter YAML (cf. inject_ch01).
    op_card, op_beats = _split_event_beats(chap, 'chapter_start', 'ch02 opening',
                                           CH02_OPENING_MSGS, card_required=False)
    end_card, end_beats = _split_event_beats(chap, 'chapter_end', 'ch02 ending',
                                             CH02_ENDING_MSGS, card_required=False)
    bark = next(e for e in chap['events']
                if e.get('trigger') == 'turn_start' and e.get('turn') == 3)['script']
    tutorial = next(e for e in chap['events']
                    if e.get('trigger') == 'turn_start' and e.get('turn') == 1)['script']
    if len(tutorial) != len(CH02_TURN1_MSGS):
        sys.exit('ERROR: ch02 turn-1 tutorial has %d lines; expected %d '
                 '(zip would silently drop the extra)' % (len(tutorial), len(CH02_TURN1_MSGS)))

    cut_special = {
        'narration': None,                         # faceless stage-business box (#58)
        'halvar': _fid_tag(CH02_BOSS_SLOT),        # the raider captain, on the Bazba slot
        'vellynne': _fid_tag(CH02_VELLYNNE_SLOT),  # recurring NPC: placeholder face (#19)
        'targos-fisher': CH02_FISHER_FID,          # generic villager mug
    }

    cut_fid = _make_fid(cut_special, 'ch02 unknown cutscene speaker')

    # Vellynne anchors mid-right (the quest-giver, cf. Hlin/Duvessa); everyone else
    # speaks from mid-left. The ending beats are single-speaker each, so mid-left is
    # enough (no two-shots, no preloads -> no REMA face-flashing, cf. inject_ch01).
    op_home = {'vellynne': '[OpenMidRight]'}

    # 1. Map: register the painted layout, point slot 3 at it + the winter tileset, and
    #    swap the host goal to vanilla slot-4's defeat_all template (cf. inject_ch01 step 1).
    indices = _register_chapter_map(maps_dir, CH02_LAYOUT,
                                    'Manchego Stars ch02 layout (#22)')
    obj_idx, pal_idx, cfg_idx, layout_idx = indices
    host = _retarget_host_chapter(
        CH02_HOST_INDEX, 4, 'defeat_all',
        'ERROR: slot 4 goal is not the vanilla defeat_all template '
        '(needed as the ch02 DefeatAll donor)',
        indices, chap['chapter_number'], CH02_EVENT_GROUP,
        (CH02_GOAL_WINDOW_MSG, CH02_GOAL_STATUS_MSG))
    # AFTER the retarget, which zeroes map.changeLayerId (as ch03/ch04/ch05 do). Ordering this
    # the other way emitted MS_Ch02MapChanges, registered it, and then left slot 3 pointing at
    # gChapterDataAssetTable[0] -- so no hut could be sacked or closed, and a raider stood on a
    # village for twelve turns doing nothing (#335). check.py pins the order for every chapter.
    _inject_tile_changes('MS_Ch02MapChanges', ch02_map_changes(chap, maps_dir),
                         CH02_HOST_INDEX)

    # 2. Rosters (events_udefs.c). Four tables, reusing vanilla Ch3 symbols (already
    #    declared in eventcall.h, so no extern surgery):
    #    - UnitDef_Event_Ch3Ally: the 5-slot deploy template = THE CAP. Never LOADed;
    #      the prep flow reads its entry count (cap) + positions (deploy tiles). The
    #      founding party itself persists from ch01 (no join-LOAD) -- but a cutscene recruit
    #      (Baxby) was never a unit, so he needs an explicit join-LOAD (UnitDef_088B476C, 2a-bis).
    #    - UnitDef_088B463C: the RED raider band (Beginning-scene LOAD1) -- vanilla Ch2's
    #      exact mix, reflavored chardalyn berserkers. 0x8e = generic autolevelled trash;
    #      Grukk rides the vanilla Bone slot, Halvar the Bazba slot.
    #    - UnitDef_088B4718: the 3 GREEN chwinga (LOAD1 at chapter start, green from .allegiance;
    #      was vanilla Colm's green table). Distinct NPC slots so CHECK_ALIVE tracks each.
    #    - UnitDef_088B4758: the turn-3 RED reinforcement pair (the empty vanilla table;
    #      088B4718 is now the chwinga). Vanilla 088B4470 mix = one L2 + one L3 brigand.
    # available_at=2: the party on the field at ch02 -- founding party + Baxby (recruited
    # ch01 at the market); Trex (ch03) is not yet in. Data-driven from each unit's recruit.chapter.
    # NB this only SIZES the deploy cap; the founding party persists from ch01 but Baxby (a
    # cutscene recruit) is put in the saved roster by the off-map join-LOAD below (2a-bis, #23).
    cast, _ = _classed_cast(campaign, available_at=chap['chapter_number'])
    leader = 'CHARACTER_%s' % cast[0][1].upper()
    deploy = _deploy_cap_entries(chap, cast, leader, 'ch02')

    # 2a-bis. Off-map recruit join-LOAD: the party persists from ch01 (already in the save),
    #     but a cutscene recruit was never a unit -- so LOAD him in HERE, his first prep
    #     roster, or the deploy cap sizes a slot nothing fills (#23). For ch02 that is Baxby
    #     (ch01 ending cutscene; recruit.via = market = off-map). Each rides its CLASS_LOADOUT
    #     kit, blue, on a walkable NW tile (PREP re-picks positions). Empty for a chapter with
    #     no newly-available off-map recruit (then no LOAD1 is emitted -- see step 4).
    join_recruits = offmap_join_recruits(campaign, chap['chapter_number'])
    for uid, _s, ce, _d, _l in join_recruits:
        if ce not in CLASS_LOADOUT:
            sys.exit('ERROR: no loadout for %s (ch02 join recruit %s)' % (ce, uid))
    jx, jy = CH02_RECRUIT_JOIN_POS
    recruit_join = [_ally_unit_entry(leader, slot, dce, lv, jx, jy,
                                     ', '.join(CLASS_LOADOUT[ce]),
                                     ' /* %s -- off-map recruit joins the party (#23) */' % uid)
                    for uid, slot, ce, dce, lv in join_recruits]

    by_eid = {e['id']: e for e in chap['enemy_units']}
    raider = by_eid['chardalyn-raider']            # 2x L3 generic brigand (vanilla #1 + #5)
    scavenger = by_eid['chardalyn-scavenger']      # 1x L3, the vulnerary dropper (vanilla #4)
    skirmisher = by_eid['chardalyn-skirmisher']    # 1x L2 generic brigand (vanilla #6)
    archer = by_eid['frost-archer']                # 1x L1 archer (vanilla #2)
    grukk, halvar = by_eid['raider-bruiser'], by_eid['raider-captain']
    reinf = chap['reinforcements'][0]
    brig, arch = CH02_CLASS_IDS['brigand'], CH02_CLASS_IDS['archer']
    axe, steel, bow, vuln, lance = (CH02_ITEM_IDS['iron-axe'], CH02_ITEM_IDS['steel-axe'],
                                    CH02_ITEM_IDS['iron-bow'], CH02_ITEM_IDS['vulnerary'],
                                    CH02_ITEM_IDS['slim-lance'])

    # 2a. RED raider band (088B463C) -- vanilla Ch2 parity, reflavored chardalyn berserkers.
    enemies = []
    for index, (x, y) in enumerate(raider['positions']):
        enemies.append(_enemy_unit_entry(
            CH02_GENERIC_PID, brig, raider['level'], True, x, y,
            axe, enemy_ai_initialiser(chap, raider, index),
            ' /* chardalyn berserker */'))
    for index, (x, y) in enumerate(scavenger['positions']):
        enemies.append(_enemy_unit_entry(
            CH02_GENERIC_PID, brig, scavenger['level'], True, x, y,
            '%s, %s' % (axe, vuln), enemy_ai_initialiser(chap, scavenger, index),
            ' /* chardalyn scavenger -- drops the vulnerary */',
            itemdrop=True))
    for index, (x, y) in enumerate(skirmisher['positions']):
        enemies.append(_enemy_unit_entry(
            CH02_GENERIC_PID, brig, skirmisher['level'], True, x, y,
            axe, enemy_ai_initialiser(chap, skirmisher, index),
            ' /* chardalyn skirmisher (L2) */'))
    for index, (x, y) in enumerate(archer['positions']):
        enemies.append(_enemy_unit_entry(
            CH02_GENERIC_PID, arch, archer['level'], True, x, y,
            bow, enemy_ai_initialiser(chap, archer, index),
            ' /* chardalyn hunter -- vanilla\'s lone archer, charges on turn 2 */'))
    gx, gy = grukk['position']
    enemies.append(_enemy_unit_entry(
        'CHARACTER_%s' % CH02_MINIBOSS_SLOT, brig, grukk['level'],
        False, gx, gy, axe, enemy_ai_initialiser(chap, grukk),
        ' /* Grukk the Bruiser -- miniboss, fixed bases (Bone slot) */'))
    hx, hy = halvar['position']
    enemies.append(_enemy_unit_entry(
        'CHARACTER_%s' % CH02_BOSS_SLOT, brig, halvar['level'],
        True, hx, hy, steel, enemy_ai_initialiser(chap, halvar),
        ' /* Halvar the Raider Captain -- boss, steel axe (Bazba slot) */'))

    # 2b. GREEN chwinga (088B4718) -- the protect layer; class + level + positions +
    #     per-survivor gift come from the YAML deployment.green_allies (id order
    #     matches CH02_CHWINGA). autolevel leans on the class curve (bases = tuning
    #     checkpoint).
    chwinga_by_id = {g['id']: g for g in chap['deployment']['green_allies']}
    # The charm-gift is authored in the YAML (green_allies[].gift) -- the single source of truth
    # for the ch02<->ch03 reward swap. Validate every gift resolves + the id sets agree, so a YAML
    # edit that adds/renames a gift fails loudly here instead of silently shipping the wrong item.
    slot_by_uid = dict(CH02_CHWINGA)
    village_chwinga = {v['inhabitant']['id'] for v in chap.get('villages', [])
                       if isinstance(v.get('inhabitant'), dict)}
    for uid, _slot in CH02_CHWINGA:
        g = chwinga_by_id.get(uid)
        if g is None:
            # Not on the field is fine -- but only if a village claims her, or a chwinga can
            # vanish from the chapter entirely and still be credited a charm at the ending.
            if uid in village_chwinga:
                continue
            sys.exit('ERROR: ch02 chwinga %s is neither in deployment.green_allies nor named '
                     'as a village inhabitant -- it would exist only as a charm nobody can '
                     'earn' % uid)
        if 'gift' not in g:
            sys.exit('ERROR: ch02 chwinga %s has no gift' % uid)
        if g['gift'] not in CH02_ITEM_IDS:
            sys.exit('ERROR: ch02 chwinga %s gift %r not in CH02_ITEM_IDS' % (uid, g['gift']))
    # The green table is what DEPLOYS, read from the YAML rather than from CH02_CHWINGA:
    # Glimmerfrost is a village inhabitant, not a unit. Inventory is per-chwinga now (the
    # frail one carries Ross's Vulnerary alongside its Heal staff), and the AI comes from
    # the same donor machinery as everything else (#335).
    chwinga = [_ally_unit_entry(None, slot_by_uid[g['id']],
                                CH02_CLASS_IDS[g['class']], g['level'],
                                g['position'][0], g['position'][1],
                                ', '.join(CH02_ITEM_IDS[i] for i in g['inventory']),
                                ' /* chwinga %s (gift: %s) */' % (g['id'], g['gift']),
                                allegiance='GREEN', autolevel=True,
                                ai=enemy_ai_initialiser(chap, g))
               for g in chap['deployment']['green_allies']]

    # 2c. RED reinforcements (088B4758) -- vanilla 088B4470 mix: one L2 + one L3, turn 3.
    reinforce = [_enemy_unit_entry(CH02_GENERIC_PID, brig, lv, True, x, y, axe,
                                   enemy_ai_initialiser(chap, reinf, index),
                                   ' /* rear raider L%d, turn %d */'
                                   % (lv, reinf['trigger_turn']))
                 for index, ((x, y), lv)
                 in enumerate(zip(reinf['positions'], reinf['levels']))]

    with open(EVENTS_UDEFS_C, encoding='utf-8') as f:
        udefs = f.read()
    tables = [('UnitDef_Event_Ch3Ally[] =', deploy),
              ('UnitDef_088B463C[] =', enemies),
              ('UnitDef_088B4718[] =', chwinga),
              ('UnitDef_088B4758[] =', reinforce)]
    if recruit_join:  # only overwrite the free join table when a recruit actually joins here
        tables.append(('%s[] =' % CH02_RECRUIT_JOIN_SYMBOL, recruit_join))
    for marker, entries in tables:
        block = '{\n' + '\n'.join(entries) + '\n    { 0 },\n}'
        udefs = _replace_brace_block(udefs, marker, block, EVENTS_UDEFS_C)
    with open(EVENTS_UDEFS_C, 'w', encoding='utf-8') as f:
        f.write(udefs)

    # 3. Event lists (ch3-eventinfo.h). Turn: the rear raiders on turn 3 (FACTION_ID_BLUE
    #    appear-at-player-phase idiom, cf. inject_ch01). Character/Location cleared: no
    #    talks, and DROP the vanilla Seize(14,1) + chests/doors so DefeatAll (CountRedUnits)
    #    is the only win path. Misc keeps its vanilla CauseGameOverIfLordDies untouched.
    with open(CH3_EVENTINFO_H, encoding='utf-8') as f:
        info = f.read()
    info = _replace_brace_block(
        info, 'EventListScr_Ch3_Turn[] =',
        '{\n    TURN(0x0, EventScr_Ch3_Turn2Player, 1, 0, FACTION_ID_BLUE)'
        ' /* turn-1 fliers-vs-bows: RBG warns flier Pinky off the archer */\n'
        '    TURN(0x0, EventScr_Ch3_Turn1Npc, %d, 0, FACTION_ID_BLUE)'
        ' /* turn-%d rear raiders + Wolfram bark */\n    END_MAIN\n}'
        % (reinf['trigger_turn'], reinf['trigger_turn']), CH3_EVENTINFO_H)
    info = _replace_brace_block(
        info, 'EventListScr_Ch3_Character[] =', '{\n    END_MAIN\n}', CH3_EVENTINFO_H)
    info = _replace_brace_block(
        info, 'EventListScr_Ch3_Location[] =', ch02_location_events(chap), CH3_EVENTINFO_H)
    with open(CH3_EVENTINFO_H, 'w', encoding='utf-8') as f:
        f.write(info)

    # 4. Scenes (ch3-eventscript.h). Beginning: Vellynne's opening over a scenic BACG,
    #    then LOMA rebuilds the battle map fresh (the BACG clobbered it, cf. inject_ch01),
    #    the raiders LOAD, and the shared prep call runs Pick Units (cap 5, lord
    #    force-deployed). Turn1Npc: the turn-3 reinforcement LOAD + Wolfram's bark over the
    #    map. Ending: the Targos discovery, then the dev placeholder (ch03 not hosted yet).
    op_text_calls = _scenic_beat_calls(
        CH02_OPENING_MSGS, op_beats,
        ['A -- Vellynne stops them; RBG haggles the orb job',
         'B -- Meesmickle & Braulo react to the corpse-sled',
         'C -- Sclorbo meets his chwinga kin; Marty offers a Chagaccino'])
    tut_text_calls = _scenic_beat_calls(
        CH02_TURN1_MSGS, [[ln] for ln in tutorial],
        ['RBG warns flier Pinky off the archer (fliers-vs-bows debut)',
         'Pinky takes it to heart',
         "Halvar sends the band at the huts (vanilla MSG_957 verbatim)",
         'Halvar: cut down anyone in the way',
         'Halvar takes the far hut himself'])
    end_text_calls = _scenic_beat_calls(
        CH02_ENDING_MSGS, end_beats,
        ['A -- the Targos fisher warns them off the frozen body',
         'B -- Rootis clocks the dagger-of-ice kill (Sephek breadcrumb)',
         'C -- nightfall narration over the camp (#58 opaque box)',
         'D -- RBG sets the road north (lets the Bremen bounty keep)'])
    # Off-map recruit join-LOAD line: emitted only when a cutscene/market recruit becomes
    # available this chapter (Baxby, ch02) -> he enters the persistent party right before PREP,
    # so Pick Units lists him. Empty (no LOAD1) for a chapter with no such recruit.
    recruit_load = (
        '    LOAD1(0x1, %s) /* off-map recruit joins the persistent party (#23) */\n'
        % CH02_RECRUIT_JOIN_SYMBOL if recruit_join else '')
    with open(CH3_EVENTSCRIPT_H, encoding='utf-8') as f:
        script = f.read()
    script = _replace_brace_block(
        script, 'EventScr_Ch3_BeginningScene[] =',
        '{\n'
        '    MUSC(SONG_TENSION)\n'
        '    REMOVEPORTRAITS\n'
        '    BACG(%s) /* Bryn Shander west gate (placeholder BG; #22 polish) */\n'
        '    FADU(16)\n'
        '    BROWNBOXTEXT(0x%X, 8, 8) /* "Bryn Shander -- West Gate" card */\n'
        % (CH02_OPENING_BG, CH02_OPENING_CARD_MSG)
        + op_text_calls +
        ('    FADI(16) /* fade the scenic BG out */\n'
         '    SVAL(EVT_SLOT_B, 0x0) /* map camera origin */\n'
         '    LOMA(0x%X) /* RestartBattleMap -- build the ch02 map fresh (cf. inject_ch01) */\n'
         '    LOAD1(0x1, UnitDef_088B463C) /* the RED raider band */\n'
         '    LOAD1(0x1, UnitDef_088B4718) /* the 3 GREEN chwinga (protect layer) */\n'
         % CH02_HOST_INDEX)
        + recruit_load +
        '    ENUN\n'
        # NO FADU here: the prep prologue (EventScr_08591F64) fades to black before drawing
        # Preparations, so revealing the map first only FLASHES it. Stay black into CALL(prep).
        '    CALL(EventScr_08591FD8) /* preparations (PREP, event cmd 0x3E) -- cap 5 */\n'
        '    ENUT(8)\n'
        '    EVBIT_T(7)\n'
        '    ENDA\n}', CH3_EVENTSCRIPT_H)
    script = _replace_brace_block(
        script, 'EventScr_Ch3_Turn1Npc[] =',
        '{\n    SVAL(EVT_SLOT_2, UnitDef_088B4758)\n'
        '    CALL(EventScr_LoadReinforce)\n'
        '    TEXTSHOW(0x%X) /* Wolfram: hold the rear (rear-ambush bark) */\n'
        '    TEXTEND\n    REMA\n'
        '    EVBIT_T(7)\n    ENDA\n}' % CH02_BARK_MSG, CH3_EVENTSCRIPT_H)
    # Turn-1 fliers-vs-bows tutorial (repurposes the dead vanilla Ch3 Turn2Player scene):
    # RBG warns flier Pinky off the Chardalyn Hunter -- the in-voice heads-up vanilla owes
    # via the Vanessa rescue. Portrait talk over the map; no BACG (would clobber the map).
    script = _replace_brace_block(
        script, 'EventScr_Ch3_Turn2Player[] =',
        '{\n' + tut_text_calls +
        '    REMA\n'
        '    EVBIT_T(7)\n    ENDA\n}', CH3_EVENTSCRIPT_H)

    # The two Targos huts (2026-08-30). Vanilla's own village shape (village_script, shared
    # with ch04/ch05): one box over the village BG, then the reward into the visitor's hands.
    # The south hut IS Glimmerfrost -- she hands her charm over when the party reaches her, so
    # her Pure Water is delivered here rather than at the ending like the two on the field.
    for village in chap.get('villages', []):
        symbol, msg, _fid, bg = CH02_VILLAGE_SLOTS[village['id']]
        script = _replace_brace_block(
            script, symbol + '[] =',
            village_script(msg, village_reward_item(village, CH02_ITEM_IDS), bg),
            CH3_EVENTSCRIPT_H)
    # Per-chwinga charm-gift: read each chwinga's survival (CHECK_ALIVE writes EVT_SLOT_C)
    # while the battle units are still loaded, BEQ past the give if it fell, else drop the
    # charm into the leader's inventory (overflow -> convoy). This is the chapter's
    # per-unit soft-fail signature beat (cf. vanilla survival idiom, ch10b ending).
    # Per-survivor charms, for the chwinga ON THE FIELD. Glimmerfrost's is not here: she
    # lives in the south hut and hands hers over when the party reaches her, the way a
    # vanilla village pays on visit. Losing her to a raider and losing a chwinga on the
    # field are the same soft-fail; they are simply collected in different places.
    slot_by_uid = dict(CH02_CHWINGA)
    chwinga_gifts = ''.join(
        '    SVAL(EVT_SLOT_3, %s) /* %s charm */\n'
        '    CHECK_ALIVE(CHARACTER_%s)\n'
        '    BEQ(0x%X, EVT_SLOT_C, EVT_SLOT_0) /* fell -> forfeit its own charm */\n'
        '    GIVEITEMTO(CHAR_EVT_PLAYER_LEADER)\n'
        'LABEL(0x%X)\n'
        % (CH02_ITEM_IDS[g['gift']], g['id'], slot_by_uid[g['id']].upper(),
           0x30 + i, 0x30 + i)
        for i, g in enumerate(chap['deployment']['green_allies']))
    script = _replace_brace_block(
        script, 'EventScr_Ch3_EndingScene[] =',
        '{\n    MUSC(SONG_VICTORY)\n'
        + chwinga_gifts +               # per-survivor charm-gifts (read while units are loaded)
        '    REMOVEPORTRAITS\n'
        '    BACG(%s) /* Targos square (placeholder BG; #22 polish) */\n'
        '    FADU(16)\n'
        '    BROWNBOXTEXT(0x%X, 8, 8) /* "Targos" card */\n'
        % (CH02_ENDING_BG, CH02_ENDING_CARD_MSG)
        + end_text_calls +
        '    FADI(16) /* fade the town out */\n'
        '    MNC2(0x%X) /* -> ch03 "The Termalaine Mine", hosted on chapter slot 4 (inject_ch03) */\n'
        '    ENDA\n}' % CH03_HOST_INDEX, CH3_EVENTSCRIPT_H)
    with open(CH3_EVENTSCRIPT_H, 'w', encoding='utf-8') as f:
        f.write(script)

    # 5. Halvar's defeat quote -> head of gDefeatTalkList (same shadowing rule as ch01:
    #    a head entry wins the first-match scan, shadowing any vanilla Bazba entry).
    quote = ('    {\n'
             '        .pid     = CHARACTER_%s, /* Halvar death quote (ch02) */\n'
             '        .route   = CHAPTER_MODE_ANY,\n'
             '        .chapter = CHAPTER_L_3, /* ch02 is hosted on chapter slot 3 */\n'
             '        .msg     = 0x%X,\n'
             '    },' % (CH02_BOSS_SLOT, CH02_BOSS_DEATH_MSG))
    _prepend_defeat_quote(quote)

    # 6. Texts. Overwritten ids are dead vanilla Ch3 scene/talk/turn messages (the vanilla
    #    Ch3 scenes are gone); 0x993/0x994 are LIVE battle quotes and are NOT in the pool.
    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    set_message_body(lines, host['chapTitleTextId'], name_message_body(chap['title']))
    # The two Targos hut visits. One `visit_text` entry per BOX (ch04's lesson: a flowed
    # scalar reflows at the pixel budget and buttons mid-sentence), each over BG_NORMAL_VILLAGE.
    # Glimmerfrost speaks with the green chwinga bust; the east hut takes a villager mug.
    for village in chap.get('villages', []):
        _symbol, msg, fid, _bg = CH02_VILLAGE_SLOTS[village['id']]
        # Two voices in the south hut: the resident carries vanilla's alarm, and the chwinga
        # sheltering under his table hands the token over. She takes the OPPOSITE side of the
        # screen so the hand-off reads as two people, which is what vanilla's own multi-speaker
        # village (MSG_969: villager, Eirika, Selena) does.
        speakers = {DEFAULT_VILLAGE_SPEAKER: ('[OpenMidLeft]', fid)}
        guest = village.get('inhabitant')
        if isinstance(guest, dict):
            speakers[guest['id']] = (
                '[OpenMidRight]',
                '[FID_%s]' % CH02_CHWINGA_PORTRAIT_SLOT[dict(CH02_CHWINGA)[guest['id']]])
        set_message_body(lines, msg, _script_to_message(
            [{who: line} for who, line in village_boxes(village)], speakers))
    # Boss/miniboss ride vanilla slots (Bazba/Bone) -- rename their name plates to ours,
    # or the vanilla "Bazba"/"Bone" leaks on the unit window + death quote (cf. inject_ch01,
    # which renames its Breguet boss slot). display_name uses the YAML fe_name (<=12).
    set_message_body(lines, vanilla_name_text_id(CH02_BOSS_SLOT),
                     name_message_body(display_name(halvar)))
    set_message_body(lines, vanilla_name_text_id(CH02_MINIBOSS_SLOT),
                     name_message_body(display_name(grukk)))
    # VANILLA'S OWN WORDING, restored 2026-07-31 (Nicolas: "it should never have been altered
    # in the first place"). FE8 never prints "rout" as an objective -- its whole objective
    # vocabulary is Defeat enemy / Defeat boss / Defeat all monsters / Seize gate / Seize throne
    # / Survive, and the game's only uses of the word are "Route +/-" on the world map and
    # "en route" in prose. "Rout" is FE *community* vocabulary, and importing it also overran a
    # window vanilla had sized for its own words.
    set_message_body(lines, host['goal']['statusObjectiveTextId'],
                     name_message_body('Defeat all monsters'))
    set_message_body(lines, host['goal']['windowTextId'],
                     goal_window_body('Defeat enemy'))
    set_message_body(lines, CH02_OPENING_CARD_MSG, name_message_body(op_card))
    _emit_scene_beats(lines, CH02_OPENING_MSGS, op_beats, cut_fid, op_home)
    # The turn-1 scene: one portrait box per line -- RBG, Pinky, then Halvar's three-box bark.
    for msg_id, ln in zip(CH02_TURN1_MSGS, tutorial):
        set_message_body(lines, msg_id, _script_to_message(
            [ln], _stage_beat([ln], cut_fid, op_home)))
    # Wolfram's rear-ambush bark, shown over the map (29-tile bubble wrap via
    # _wrap_fe_lines; the current YAML lines fit unwrapped).
    set_message_body(lines, CH02_BARK_MSG, _script_to_message(
        bark, {'wolfram': ('[OpenMidLeft]', _fid_tag(PORTRAIT_MAP['wolfram'].upper()))}))
    set_message_body(lines, CH02_ENDING_CARD_MSG, name_message_body(end_card))
    _emit_scene_beats(lines, CH02_ENDING_MSGS, end_beats, cut_fid, {})
    set_message_body(lines, CH02_BOSS_DEATH_MSG, _script_to_message(
        [{'halvar': halvar['death_quote']}],
        {'halvar': ('[OpenMidRight]', _fid_tag(CH02_BOSS_SLOT))}, width=fe8_talk_font.BATTLE_QUOTE_BUDGET_PX))
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    # 6a. Title card image (the intro/status banner is a 4bpp image, not text) -- "Ch.2:
    #     <title>" composed from vanilla glyphs (gen_chapter_title reads the source cards
    #     from HEAD, so inject_ch01 overwriting chap_title_2.png first doesn't disturb the
    #     "Ch.2:" cut).
    _write_chapter_title_card(host, 'Ch.2: ' + chap['title'])

    if verbose:
        print('  ch02 map (obj1=%d pal=%d cfg=%d layout=%d) hosted on chapter %d; '
              'DefeatAll, deploy cap %d + PREP (lord auto-force-deployed)'
              % (obj_idx, pal_idx, cfg_idx, layout_idx, CH02_HOST_INDEX, len(deploy)))
        joined = ', '.join(uid for uid, *_ in join_recruits) or 'none'
        print('  rosters: party persists + off-map recruit join-LOAD [%s], %d chardalyn '
              'raiders (Grukk@%s Halvar@%s) + %d rear raiders turn %d; %d GREEN chwinga '
              '(per-survivor charm-gifts)'
              % (joined, len(enemies), (gx, gy), (hx, hy), len(reinforce),
                 reinf['trigger_turn'], len(chwinga)))
