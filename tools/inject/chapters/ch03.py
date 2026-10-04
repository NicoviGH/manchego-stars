"""Chapter 3 (#23): its injector and everything only it reads.
"""
import json
import os
import struct
import sys

import fe8_talk_font
from inject.cast import _classed_cast, char_symbol, CLASS_LOADOUT, GUEST_PORTRAIT_MAP
from inject.chapter_ids import (
    CH03_BOSS_PID, CH03_BRUTE_MINIBOSS_PID, CH03_CHAPTER_YAML, CH03_ENDING_CARD_MSG,
    CH03_ENDING_MSGS, CH03_GOAL_STATUS_MSG, CH03_GOAL_WINDOW_MSG, CH03_MIDMAP_MSGS,
    CH03_OPENING_CARD_MSG, CH03_OPENING_MSGS, CH03_TREX_ENTRANCE_MSG, CH03_TREX_TALK_MSG)
from inject.decomp import _replace_brace_block, REPO
from inject.chapter_frame import write_event_group
from inject.class_ids import ChapterClassIds
from inject.hosting import _load_chapter_yaml, _retarget_host_chapter
from inject.hosts import CH03_EVENT_GROUP, CH03_HOST_INDEX
from inject.maps import (
    _inject_tile_changes, _layout_sidecar, _register_chapter_map, _register_tileset)
from inject.paths import CH4_EVENTINFO_H, CH4_EVENTSCRIPT_H, EVENTS_UDEFS_C, TEXTS_TXT
from inject.recruit import on_map_talk_recruits, talk_recruit_wiring
from inject.scenes import (
    _emit_scene_beats, _make_fid, _prepend_defeat_quote, _scenic_beat_calls, _split_event_beats,
    _stage_beat, _write_chapter_title_card, flag_defeat_quote)
from inject.text import (
    _fid_tag, _script_to_message, dev_placeholder_scene, name_message_body, SCRIPT_DIRECTIVES,
    set_message_body)
from inject.units import (
    _ally_unit_entry, _deploy_cap_entries, _enemy_unit_entry, enemy_ai_initialiser)


def _beat_is_faceless(beat, fid):
    """True if a scenic beat has NO on-screen face -- every speaker resolves faceless (fid k is None).
    A superset of _beat_is_narration (which keys on the literal 'narration' speaker): also catches a
    named-but-portraitless speaker (e.g. the ch03 kobold-brute, no mug art). Such a beat CANNOT ride
    a map talk bubble on-map -- PutTalkBubble anchors to a speaking unit, and an AFEV event script has
    none, so the bubble renders off the tilemap -- it must use the opaque AUTO-CENTERED box
    (SOLOTEXTBOXSTART), which needs no anchor. (Over a BG the full-screen window sidesteps this, which
    is why the opening/ending don't hit it; the mid-map RBG-execution beat, on-map, does.)"""
    keys = [next(iter(e)) for e in beat
            if next(iter(e)) not in SCRIPT_DIRECTIVES]
    return bool(keys) and all(fid(k) is None for k in keys)


def talk_recruiters(campaign, chapter_number):
    """The candidate RECRUITERS for an on-map talk recruit in chapter N = every core party
    member on the blue field roster (cast_available_at(N) = _classed_cast(available_at=N)),
    as CHARACTER_ symbols. "Talker = ANY core party member" (Nicolas, 2026-07-08: the only
    thief must be non-missable, and a static CHAR can't name the CHOSEN lord) -> one CHAR
    entry per candidate, all -> the shared recruit script."""
    cast, _ = _classed_cast(campaign, available_at=chapter_number)
    return [char_symbol(slot) for _, slot, *_ in cast]


def midmap_afev(guard_flag, script, watch_flag):
    """A Misc AFEV that runs `script` once when `watch_flag` is set (the miniboss's flagged
    death), guarded by `guard_flag` (EvCheck01_AFEV's ent-flag, set after the entry fires) so it
    does not re-trigger every subsequent turn. The vanilla mid-map death-scene idiom (cf. ch1
    AFEV(EVFLAG_TMP(7), EventScr_Ch1_Misc_DefeatBoss, EVFLAG_DEFEAT_BOSS)). guard_flag must
    differ from watch_flag."""
    return 'AFEV(%s, %s, %s)' % (guard_flag, script, watch_flag)
CH03_LAYOUT = ('Ch03TermalaineMineMap', 'ch03-the-termalaine-mine')  # (asset label, maps/ stem)
CH03_TILESET = 'cave-interior'   # stem 'Cave' (TILESET_STEMS); first chapter to use it -> self-registers
CH03_GOAL_DONOR = 6              # vanilla slot 6 = defeat_boss goal template (untouched by our injectors)
                                # a clean slate -- no vanilla boss name/face/defeat-quote leaks, and our
                                # flagged gDefeatTalkList entry (CHAPTER_L_4) uniquely keys the DefeatBoss win to it.
CH03_GENERIC_PID = '0xaa'       # vanilla slot-4 generic-minion charIndex (autolevelled trash)
# DefeatBoss ending script: repurpose the vanilla Ch4 ending EventScr_089F19F8 (defined in ch4-eventscript.h,
# already extern-referenced by the vanilla Ch4 Misc's DefeatAll -> visible to ch4-eventinfo.h's Misc list).
CH03_ENDING_SCRIPT = 'EventScr_089F19F8'
# The kobolds are campaign.yaml's kobold reskins, which `dress` ch03's brigand and mercenary --
# and `brigand-brute`, the steel brute's `deploy_class`: a Brigand for parity that deploys on
# the Lizardzerker sprite. Grell = vanilla Mogall; archer/thief stay vanilla.
CH03_CLASS_IDS = ChapterClassIds('ch03')
CH03_ITEM_IDS = {'iron-axe': 'ITEM_AXE_IRON', 'hand-axe': 'ITEM_AXE_HANDAXE',
                 'steel-axe': 'ITEM_AXE_STEEL', 'iron-sword': 'ITEM_SWORD_IRON',
                 'iron-lance': 'ITEM_LANCE_IRON', 'javelin': 'ITEM_LANCE_JAVELIN',
                 'iron-bow': 'ITEM_BOW_IRON', 'evil-eye': 'ITEM_MONSTER_EVILEYE',
                 'red-gem': 'ITEM_REDGEM',
                 'pure-water': 'ITEM_PUREWATER', 'antitoxin': 'ITEM_ANTITOXIN',
                 'door-key': 'ITEM_DOORKEY', 'chest-key': 'ITEM_CHESTKEY'}
# The FF5 navy chest metatile in the cave-interior tileset (retile.py): closed 17 / open 29.
# gBmMapBaseTiles stores metatile<<2 (compile_layout: .mar = metatile<<5, mar_to_map >>3, so
# the loaded tile = metatile<<2), so the open-chest tile a MapChange writes is 29<<2 (#23).
CH03_CHEST_CLOSED_TILE = 17
CH03_CHEST_OPEN_TILE = 29
# Left-entrance floor tiles (verified walkable on the painted .mar, clear of enemy tiles) --
# the party deploys here statically (fast-boot; the real PREP flow lands with deploy_slots + cutscenes).
# 9 tiles = the ch03 field roster (cast_available_at(3) = the 8 founding party + Baxby, the
# ch01 recruit). Trex is NOT here -- he is a Colm-style TALK recruit placed GREEN on the map
# (CH03_TREX_GREEN_POS), joining via CUSA when a party member talks to him (that CHAR talk +
# its line ride the ch03 event/cutscene pass, #23 item 4). cast_available_at gives him ch04+ prep.
CH03_TREX_GREEN_POS = (2, 4)    # Colm's tile: our map is a 1:1 17x16 retile of vanilla Ch3 (Borgo),
                                # where green Colm walks to (2,4) on the upper-left ledge (spawns 0,5)
                                # -- UnitDef_088B4718/REDA_088B456C. Trex mirrors the recruit, so he
                                # stands green on the same ledge the party naturally reaches to Talk.
# Two free vanilla Ch4 UnitDef tables (defined in events_udefs.c, referenced nowhere but
# themselves -> safe to repurpose, like the enemy table 088B4A80): one holds Trex GREEN
# (always LOADed, the on-map talk-recruit); the other is the DEBUG-BOOT party seed (the
# armed field roster, LOADed ONLY on --ch03-boot to found a party from nothing so PREP has
# something to pick -- exactly ch01's founding-chapter shape). The real chain (item 3) omits
# the seed: the party persists from ch02, and PREP reads the never-LOADed cap template.
CH03_TREX_GREEN_SYMBOL = 'UnitDef_088B49CC'
CH03_BOOT_SEED_SYMBOL = 'UnitDef_088B47E4'
CH03_PREP_SCRIPT = 'EventScr_08591FD8'   # shared Preparations call (event cmd 0x3E), cf. ch01/ch02
# Trex talk-recruit wiring (#23 item 2) -- the vanilla Colm/Neimi pattern. Repurpose dead
# vanilla Ch4 symbols the host frees: EventScr_089F199C is the Ch4 Turn-2 green script (its
# only referrer was EventListScr_Ch4_Turn, emptied by the host) -> the shared recruit script;
# 0x9A5 is a dead Ch4 opening-cutscene line (referenced only by the replaced BeginningScene,
# like the boss-death 0x9A3) -> the talk body; EVFLAG_TMP(9) is vanilla ch3 Colm's own CHAR
# talk flag, unused in our minimal host.
CH03_TREX_TALK_SCRIPT = 'EventScr_089F199C'
CH03_TREX_TALK_FLAG = 'EVFLAG_TMP(9)'
# ch03 cutscene beats (#23 Cutscenes) ride the dead vanilla Ch4 cutscene-message block
# 0x9A3..0x9B9 -- every id there is referenced ONLY by the Ch4 event scripts that inject_ch03
# replaces (git-verified against the pristine ch4-eventscript.h) -> dead in our build. 0x9A3
# (boss death) + 0x9A5 (talk) are already claimed above. BG: reuse the ch02 Targos-winter slot
# for the Termalaine street (Nicolas 2026-07-04: vanilla-style BG reuse, no new slot; the
# mid-map beats play ON-MAP, no BG). The midmap RBG-execution beat uses 0x9AF..0x9B1 + 0x9B4
# (0x9B2/0x9B3 are the opening's Pinky-scout beats).
CH03_OPENING_TOWN_BG = 'BG_MS_TARGOS_WINTER'      # beats A-B: the Termalaine street (crier, bounty, Wolfram)
CH03_OPENING_MINE_BG = 'BG_MS_TERMALAINE_MINE'    # beats C-E: inside the mine (sign, Pinky's scout) -- swaps in after Wolfram's "we're going in"
CH03_ENDING_BG = 'BG_MS_TARGOS_WINTER'
CH03_TREX_ENTRANCE_SCRIPT = 'EventScr_089F1B38'  # dead Ch4 Village script (its list ref is dropped by the host) -> Trex's light turn-1 entrance beat
                                   # 0xb7 (0xB0..0xB9 are all UNNAMED gaps in gCharacterData, a
                                   # designated-init array -> zero name/face/quote, no vanilla leak).
                                   # Distinct from the shared generic 0xaa so its flagged death quote
                                   # keys the midmap trigger to the Brute ALONE (first-match pid scan).
CH03_BRUTE_DEFEAT_FLAG = 'EVFLAG_TMP(10)'  # set by the Brute's silent gDefeatTalkList entry on death
CH03_MIDMAP_GUARD_FLAG = 'EVFLAG_TMP(11)'  # AFEV ent-flag: guards the one-shot (set after the beat fires)
CH03_MIDMAP_SCRIPT = 'EventScr_089F1BD8'   # dead vanilla Ch4 script (defined-only; its list ref dropped by the host)
CH03_CRIER_FID = '[FID_VillagerYoungBoy]'   # the boy crying the bounty on his crate (book p.95; generic mug)


def _read_map_metatile(maps_dir, stem, x, y):
    """Return the metatile index painted at (x, y) on a compiled .mar layout. compile_layout
    stores each cell as metatile<<5 with no header (map_tileset_tool), row-major over the
    width from the paired .json -- so reading the door's OPEN tile off the map itself tracks
    any re-retile (no hand-copied tile numbers to drift)."""
    with open(_layout_sidecar(maps_dir, stem), encoding='utf-8') as f:
        w = json.load(f)['width']
    with open(os.path.join(maps_dir, stem + '.mar'), 'rb') as f:
        mar = f.read()
    return struct.unpack_from('<H', mar, (y * w + x) * 2)[0] >> 5


def _inject_ch03_tile_changes(chap, maps_dir, host_index):
    """Author the ch03 chest + door tile-changes + point slot `host_index` at them (#23).

    Emits MS_Ch03MapChanges (chests then doors -- see _ch03_tile_changes_asm), registers it as
    a fresh gChapterDataAssetTable word, and sets the host slot's map.changeLayerId to that index
    (GetChapterMapChangesPointer -> gChapterDataAssetTable[changeLayerId], chapterdata.c). Each
    door's open tile is read off the painted map (the metatile directly below the door cell)."""
    changes = [(c['position'][0], c['position'][1], 1, 1, [CH03_CHEST_OPEN_TILE],
                'chest %d -> %d on loot' % (CH03_CHEST_CLOSED_TILE, CH03_CHEST_OPEN_TILE))
               for c in chap.get('chests', [])]
    # An opened door becomes the passable tile directly BELOW it (Nicolas 2026-07-11), read off
    # the painted map so a re-retile cannot leave a hand-copied tile number behind.
    changes += [(d['position'][0], d['position'][1], 1, 1,
                 [_read_map_metatile(maps_dir, CH03_LAYOUT[1],
                                     d['position'][0], d['position'][1] + 1)],
                 'door opens to the floor below')
                for d in chap.get('doors', [])]
    return _inject_tile_changes('MS_Ch03MapChanges', changes, host_index)


def inject_ch03(campaign, boot=False, verbose=True):
    """Host for Ch3 "The Termalaine Mine" (#23) on chapter slot 4: register the cave-interior
    tileset + the painted layout, wire the real PREP deploy of the classed party + the 10
    vanilla-Ch3-parity enemies (reflavored kobolds / grell / svirfneblin) at their vanilla
    tiles, strip cutscenes, and leave a walkable, playable map.

    Deploy = the vanilla prep-chapter idiom (cf. inject_ch01/inject_ch02): a never-LOADed
    deploy-cap template (UnitDef_Event_Ch4Ally, sized to cast_available_at(3) over the YAML
    deploy_slots) + a Preparations CALL that fields the roster (the lord force-deployed).
    The real ch02->ch03 chain calls this with boot=False: ch02's ending MNC2(0x4) lands here
    and the party that PERSISTS from ch02 feeds PREP (main() hosts ch03 in every non-boot build).
    `boot` (the --ch03-boot debug path, New Game straight to slot 4) instead LOADs an ARMED party
    seed so PREP has a party to pick from from a COLD New Game -- a standalone-playtest crutch only.

    The DefeatBoss(grell) WIN is wired: Misc DefeatBoss AFEV + the grell's flagged (EVFLAG_DEFEAT_BOSS)
    defeat quote + a minimal ending script (victory -> dev-placeholder landing until ch04 hosts).
    Trex's TALK RECRUIT (#23 item 2) stands GREEN in its own table; ANY core party member Talks
    to him -> the shared recruit script CUSA-flips him BLUE (the Colm/Neimi pattern -- one CHAR entry
    per field candidate). The OPENING (chapter_start, over the Targos-winter BG), Trex's light
    turn-1 ENTRANCE (Colm pattern, on-map), and the ENDING (chapter_end, over the BG -> the
    dev-placeholder landing) cutscenes are wired here, as is the mid-map RBG-EXECUTION beat: the
    Icewind Brute rides a unique miniboss pid + a silent flagged defeat quote, and a Misc AFEV fires
    the on-map execution cutscene once on its death (the mirror of the boss WIN). DEFERRED (follow-up
    passes): chests/doors; title-card art; enemy/boss art; ch03's own ending still parks on the
    dev-placeholder until ch04 hosts (then it MNC2s onward like this chapter's ch02->ch03 chain)."""
    maps_dir = os.path.join(REPO, 'campaigns', campaign, 'maps')
    chap = _load_chapter_yaml(campaign, CH03_CHAPTER_YAML)

    # 0. Cutscene beat splits, from the locked chapter YAML (cf. inject_ch01/ch02). The
    #    opening + ending play over the reused Targos-winter BG; trex_entrance is a LIGHT
    #    on-map turn-1 beat (Colm's pattern). The midmap RBG-execution beat is a follow-up.
    op_card, op_beats = _split_event_beats(chap, 'chapter_start', 'ch03 opening', CH03_OPENING_MSGS)
    end_card, end_beats = _split_event_beats(chap, 'chapter_end', 'ch03 ending', CH03_ENDING_MSGS)
    trex_entr = next(e for e in chap['events'] if e.get('trigger') == 'trex_entrance')['script']
    # Midmap RBG-execution beat: on-map (no BG, no card), 3 beats (A/B/C) over 0x9AF..0x9B1.
    _mid_card, mid_beats = _split_event_beats(chap, 'midmap', 'ch03 midmap', CH03_MIDMAP_MSGS,
                                              card_required=False)
    # Speaker -> face: cast via PORTRAIT_MAP; narration faceless (opaque #58 box); the boy-crier
    # rides a generic villager mug (his line names Speaker Masthew -- book p.93, Oarus Masthew).
    # The kobold-brute now has a custom mug on the Caellach guest slot -> it resolves through the
    # GUEST_PORTRAIT_MAP fallback (checked after cast), so its midmap snarl is a FACED bubble.
    cut_special = {'narration': None, 'boy-crier': CH03_CRIER_FID}
    cut_fid = _make_fid(cut_special, 'ch03 unknown cutscene speaker', fallback=GUEST_PORTRAIT_MAP)
    # RBG anchors mid-right through the opening (the leader who answers): the beat-A crier
    # two-shot + the beat-C Pinky/RBG flyover two-hander stage cleanly without face-flashing.
    # The midmap Brute also anchors mid-right (facing Pinky at mid-left) -- its A-beat preload +
    # its A3 snarl land on the same podium; it never shares a beat with RBG, so no collision.
    op_home = {'prof-rbg': '[OpenMidRight]', 'kobold-brute': '[OpenMidRight]'}

    # 1. Map: register the cave-interior tileset (first chapter to use it) + the painted
    #    layout, point slot 4 at them, and borrow slot 6's defeat_boss goal banner.
    _register_tileset(campaign, CH03_TILESET, 'Cave',
                      'Manchego Stars cave-interior tileset (#23/#40)')
    indices = _register_chapter_map(maps_dir, CH03_LAYOUT, 'Manchego Stars ch03 layout (#23)')
    obj_idx, pal_idx, cfg_idx, layout_idx = indices
    host = _retarget_host_chapter(
        CH03_HOST_INDEX, CH03_GOAL_DONOR, 'defeat_boss',
        'ERROR: slot %d goal is not the vanilla defeat_boss template (ch03 DefeatBoss donor)'
        % CH03_GOAL_DONOR, indices, chap['chapter_number'], CH03_EVENT_GROUP,
        (CH03_GOAL_WINDOW_MSG, CH03_GOAL_STATUS_MSG))

    # 2. Rosters (events_udefs.c, vanilla Ch4 symbols):
    #    - UnitDef_Event_Ch4Ally: the deploy-cap TEMPLATE = THE CAP. NEVER LOADed; PREP reads
    #      its entry count (cap = cast_available_at(3), the 8 founding party + Baxby) and its
    #      YAML deploy_slots tiles, then redeploys the picks (cf. ch01/ch02 _deploy_cap_entries).
    #    - UnitDef_088B47E4 (boot only): the ARMED party seed -- the same field roster with real
    #      CLASS_LOADOUT kit, LOADed on --ch03-boot so PREP has a party to pick (ch03 has no
    #      prior chapter to found one yet). The real chain (item 3) omits it: the party persists.
    #    - UnitDef_088B49CC: Trex, GREEN in the galleries -- the vanilla Colm pattern (he stands
    #      unrecruited until a party member Talks to him -> CUSA join). Its own table so PREP's
    #      cap template stays the pure blue roster.
    #    - UnitDef_088B4A80: the 10 enemies (vanilla Ch3 parity) -- grell on the vanilla ch4
    #      boss slot, the kobolds/svirfneblin on the generic autolevelled slot.
    cast, _ = _classed_cast(campaign, available_at=chap['chapter_number'])
    for uid, _s, ce, _d, _l in cast:
        if ce not in CLASS_LOADOUT:
            sys.exit('ERROR: no loadout for %s (ch03 field roster %s)' % (ce, uid))
    leader = 'CHARACTER_%s' % cast[0][1].upper()
    cap_rows = _deploy_cap_entries(chap, cast, leader, 'ch03')
    ally = '{\n' + '\n'.join(cap_rows) + '\n    { 0 },\n}'
    # Boot party seed: the field roster armed from CLASS_LOADOUT, on the deploy_slots tiles
    # (PREP hides + re-picks them, so the tiles only need to be legal). Built regardless; only
    # LOADed when boot (step 4). classIndex rides the deploy class (dce == the vanilla class).
    slots = chap['deployment']['deploy_slots']
    seed_rows = [_ally_unit_entry(leader, slot, dce, lv, x, y, ', '.join(CLASS_LOADOUT[ce]),
                                  ' /* %s -- boot party seed (armed; PREP re-picks) */' % uid)
                 for (uid, slot, ce, dce, lv), (x, y) in zip(cast, slots)]
    seed = '{\n' + '\n'.join(seed_rows) + '\n    { 0 },\n}'
    # Trex: the chapter's on-map recruit, placed GREEN (Colm-style) at the galleries. He is a
    # classed cast member (full cast, not available_at(3)); pull his slot/class from the roster.
    (trex_uid, tslot, _, tdce, tlv), = on_map_talk_recruits(campaign, chap['chapter_number'])
    tx, ty = CH03_TREX_GREEN_POS
    trex_green = '{\n' + _ally_unit_entry(
        leader, tslot, tdce, tlv, tx, ty, '0',
        ' /* trex -- green talk-recruit (Colm-style; CUSA on talk, #23 item 2) */',
        allegiance='GREEN') + '\n    { 0 },\n}'
    # Trex talk-recruit (#23 item 2): the shared talk-recruit wiring (talk_recruit_wiring, reused
    # by ch04/ch05). Recruiter set = ANY core party member (the ch03 field roster) -> ONE CHAR
    # entry each, all pointing at the shared recruit script (CUSA flips green Trex blue). FE8's
    # multi-recruiter idiom (cf. vanilla ch14a Rennac). No pre_script: Trex is a plain green recruit.
    trex_char = char_symbol(tslot)
    char_events, trex_talk_script = talk_recruit_wiring(
        talk_recruiters(campaign, chap['chapter_number']), trex_char,
        CH03_TREX_TALK_FLAG, CH03_TREX_TALK_SCRIPT, CH03_TREX_TALK_MSG)

    enemies = []
    for e in chap['enemy_units']:
        cls = CH03_CLASS_IDS.for_entry(e)
        items = ', '.join(CH03_ITEM_IDS[i['id']] for i in e.get('inventory', []))
        drop = e.get('item_drop')
        if drop:
            items = '%s, %s' % (items, CH03_ITEM_IDS[drop]) if items else CH03_ITEM_IDS[drop]
        # The boss (grell) + the mid-map miniboss (Brute) each ride a UNIQUE raw pid so their
        # flagged gDefeatTalkList entries key their death events (WIN / midmap AFEV) to them
        # alone; every other enemy shares the generic autolevelled-trash pid.
        char = (CH03_BOSS_PID if e.get('is_boss')
                else CH03_BRUTE_MINIBOSS_PID if e.get('is_miniboss')
                else CH03_GENERIC_PID)
        for index, (x, y) in enumerate(e['positions']):
            enemies.append(_enemy_unit_entry(
                char, cls, e['level'], bool(e.get('autolevel')), x, y, items,
                enemy_ai_initialiser(chap, e, index),
                ' /* %s */' % e['id'], itemdrop=bool(drop)))
    enemy = '{\n' + '\n'.join(enemies) + '\n    { 0 },\n}'

    with open(EVENTS_UDEFS_C, encoding='utf-8') as f:
        udefs = f.read()
    udefs = _replace_brace_block(udefs, 'UnitDef_Event_Ch4Ally[] =', ally, EVENTS_UDEFS_C)
    udefs = _replace_brace_block(udefs, '%s[] =' % CH03_BOOT_SEED_SYMBOL, seed, EVENTS_UDEFS_C)
    udefs = _replace_brace_block(udefs, '%s[] =' % CH03_TREX_GREEN_SYMBOL, trex_green, EVENTS_UDEFS_C)
    udefs = _replace_brace_block(udefs, 'UnitDef_088B4A80[] =', enemy, EVENTS_UDEFS_C)
    with open(EVENTS_UDEFS_C, 'w', encoding='utf-8') as f:
        f.write(udefs)

    # 3. Strip cutscenes (cf. inject_test_chapter): empty the Ch4 event lists, wire the win/lose
    #    machinery into Misc (DefeatBoss on the grell's death + lord-death game-over), and make the
    #    beginning scene deploy the enemies + green Trex then run Preparations. DefeatBoss = AFEV on EVFLAG_DEFEAT_BOSS,
    #    which the grell's FLAGGED defeat quote sets on its death (step 5) -> runs the ending script;
    #    CauseGameOverIfLordDies = AFEV on EVFLAG_GAMEOVER (the lord's flagged quote / lord-select hook).
    # Turn list: Trex's light entrance beat fires on turn 1 (player phase), the vanilla Colm
    # turn-1 green-NPC idiom (cf. inject_ch02's turn-1 tutorial TURN).
    turn_events = ('{\n    TURN(0x0, %s, 1, 0, FACTION_ID_BLUE)'
                   ' /* turn-1: Trex\'s light entrance (Colm pattern) */\n    END_MAIN\n}'
                   % CH03_TREX_ENTRANCE_SCRIPT)
    # Location = the mine chests + doors (#23). Each Chest(item, x, y) makes its tile openable
    # (IsThereClosedChestAt reads this list) and gives the item; each Door_(x, y) makes its tile a
    # thief/key door (TILE_COMMAND_DOOR, script=1 -> CallTileChangeEvent). The paired
    # MS_Ch03MapChanges entry (step 6b) flips the chest 17->29 on loot / the door to the floor tile
    # below it on open. Coords + items from the YAML (vanilla Ch3 Borgo 1:1; (8,3) = the Tourmaline,
    # the ch02<->ch03 swap).
    loc_events = '{\n' + ''.join(
        '    Chest(%s, %d, %d) /* %s */\n'
        % (CH03_ITEM_IDS[c['contents'][0]['id']], c['position'][0], c['position'][1],
           c['contents'][0]['id'])
        for c in chap['chests']) + ''.join(
        '    Door_(%d, %d)\n' % (d['position'][0], d['position'][1])
        for d in chap.get('doors', [])) + '    END_MAIN\n}'
    # Misc = the win/lose machinery + the mid-map RBG-execution AFEV. DefeatBoss(ending) fires on
    # the grell's death (EVFLAG_DEFEAT_BOSS); the midmap AFEV fires ONCE on the Brute's death (its
    # flagged quote sets CH03_BRUTE_DEFEAT_FLAG), guarded by CH03_MIDMAP_GUARD_FLAG so it doesn't
    # re-run each turn -- the vanilla mid-map death-scene idiom (cf. ch1's tmp-flag AFEV).
    misc_events = ('{\n    DefeatBoss(%s)\n    %s /* midmap: RBG executes the beaten Brute (#23) */\n'
                   '    CauseGameOverIfLordDies\n    END_MAIN\n}'
                   % (CH03_ENDING_SCRIPT,
                      midmap_afev(CH03_MIDMAP_GUARD_FLAG, CH03_MIDMAP_SCRIPT,
                                  CH03_BRUTE_DEFEAT_FLAG)))
    # Character events = the Trex talk-recruit (#23 item 2): the CHAR-per-candidate list.
    write_event_group('ch03', CH4_EVENTINFO_H, CH03_EVENT_GROUP, lists={
        'turnBasedEvents': turn_events,
        'characterBasedEvents': char_events,
        'locationBasedEvents': loc_events,
        'miscBasedEvents': misc_events,
    }, roster='UnitDef_Event_Ch4Ally', scenes=('EventScr_Ch4_BeginningScene', CH03_ENDING_SCRIPT))

    # 3b. Tile-changes: pair each Chest()/Door_() location event above with a MapChange -- flips the
    #     FF5 navy chest 17->29 on loot, and each door to the floor tile below it on open (must run
    #     AFTER _retarget_host_chapter zeroed the slot's changeLayerId in step 1).
    _inject_ch03_tile_changes(chap, maps_dir, CH03_HOST_INDEX)

    with open(CH4_EVENTSCRIPT_H, encoding='utf-8') as f:
        script = f.read()
    # Beginning scene = the vanilla prep-chapter shape (cf. inject_ch01/ch02) with a TWO-BG
    # opening (Nicolas 2026-07-09 staging): beats A-B play over the Termalaine STREET (crier +
    # bounty, then Wolfram's "we're going in"); on that line the BG CUTS to the mine interior --
    # empty, no portraits -- for the KOBOLDS ONLY sign, then Pinky scouts (he fades OUT into the
    # dark, an over-long tension pause holds on the empty cave, then he fades back in white-faced).
    # Then LOMA rebuilds the battle map fresh, the enemies + green Trex LOAD, and CALL Preparations
    # (PREP reads the never-LOADed cap template UnitDef_Event_Ch4Ally). --ch03-boot additionally
    # LOADs the armed party seed first, so PREP has a party from a cold New Game.
    labels = ['A -- the boy crier bawls the bounty; RBG takes the job (public mask up)',
              'B -- Wolfram scents the tourmaline seam; "We\'re going in"',
              'C -- the KOBOLDS ONLY sign (faceless #58 opaque box, empty cave)',
              'D -- Pinky scouts ahead (he fades out into the dark after this)',
              'E -- Pinky drops back white-faced; the grell looked at him']
    # Split the beat calls around the BG cut: A-B over the town, C-E inside the mine.
    town_calls = _scenic_beat_calls(CH03_OPENING_MSGS[:2], op_beats[:2], labels[:2])
    sign_call = _scenic_beat_calls(CH03_OPENING_MSGS[2:3], op_beats[2:3], labels[2:3])   # SOLOTEXTBOXSTART sign
    return_call = _scenic_beat_calls(CH03_OPENING_MSGS[4:5], op_beats[4:5], labels[4:5])  # Pinky returns
    # Beat D (Pinky scouts) is RAW TEXTSTART/SHOW/END -- NOT the Text() macro, whose trailing
    # REMA fades ALL portraits (why RBG used to vanish for the pause). No REMA here: RBG's face
    # persists (Pinky's own portrait fades at the beat's end via a trailing [ClearFace] in the
    # message body -- see CH03_OPENING_TRAILINGS). The over-long STAL(90) then holds on RBG alone
    # (he watches the dark; Nicolas 2026-07-10). Beat E's Text() re-opens with TEXTSTART, which
    # equals the still-active TEXTSTART type -> Event1A_TEXTSTART skips its face-clear, so RBG
    # carries through un-reloaded (TalkLoadFace early-returns on the occupied slot -- no reflicker)
    # while Pinky fades back in white-faced. Its trailing REMA then clears both into the FADI.
    scout_raw = ('    TEXTSTART\n'
                 '    TEXTSHOW(0x%X) /* %s */\n'
                 '    TEXTEND\n' % (CH03_OPENING_MSGS[3], labels[3]))
    seed_load = ('    LOAD1(0x1, %s) /* boot: found an armed party so PREP can pick (--ch03-boot) */\n'
                 '    ENUN\n' % CH03_BOOT_SEED_SYMBOL) if boot else ''
    begin = ('{\n'
             '    MUSC(SONG_TENSION)\n'
             '    REMOVEPORTRAITS\n'
             '    BACG(%s) /* Termalaine street (town BG) */\n'
             '    FADU(16)\n'
             '    BROWNBOXTEXT(0x%X, 8, 8) /* "Termalaine" location card */\n'
             % (CH03_OPENING_TOWN_BG, CH03_OPENING_CARD_MSG)
             + town_calls +
             '    REMA /* clear the town portraits before the cut */\n'
             '    FADI(16) /* fade the street out */\n'
             # BACG (EventShowTextBgDirect) only DECOMPRESSES a new BG when activeTextType is
             # REMOVEPORTRAITS/_1A22 (eventscr.c:1316) -- every other mode returns EVC_ERROR and
             # loads nothing. The town Text() beats above expand to TEXTSTART, which left
             # activeTextType == TEXTSTART, so a bare 2nd BACG was a no-op (stale town BG stayed
             # in VRAM). Re-arm the load mode first -- the vanilla multi-BG idiom (ch17a: every
             # BACG rides a REMOVEPORTRAITS-mode scene). Faded to black, so no visible pop.
             '    REMOVEPORTRAITS /* re-arm BACG BG-load mode (Text() beats reset it to TEXTSTART) */\n'
             '    BACG(%s) /* CUT to the mine interior -- empty, no PCs */\n'
             '    FADU(16)\n'
             % CH03_OPENING_MINE_BG
             + sign_call            # the KOBOLDS ONLY sign over the empty cave (#58 opaque box)
             + scout_raw +          # Pinky scouts: "I'll look ahead" / RBG / "Straight back!" (RAW, no REMA)
             '    STAL(90) /* over-long tension pause -- Pinky winged off, RBG holds at the mouth */\n'
             + return_call +        # Pinky fades back in, white-faced: "it looked at me" / RBG "Form up"
             '    FADI(16) /* fade the mine cutscene out */\n'
             '    SVAL(EVT_SLOT_B, 0x0) /* map camera origin for the reload */\n'
             '    LOMA(0x%X) /* RestartBattleMap -- build the ch03 map fresh (cf. inject_ch02) */\n'
             % CH03_HOST_INDEX
             + '    LOAD1(0x1, UnitDef_088B4A80) /* the vanilla-Ch3-parity enemies */\n    ENUN\n'
             + seed_load +
             '    LOAD1(0x1, %s) /* Trex -- green talk-recruit (Colm-style) */\n    ENUN\n'
             # NO FADU here: the shared prep prologue (EventScr_08591F64) fades to black itself
             # before drawing Preparations, so revealing the freshly-LOMA'd battle map first only
             # FLASHES it for a beat before prep blanks it again. Vanilla prep chapters (ch10a/ch13a)
             # go straight from the cutscene into CALL(prep) -- the map is first shown after Fight!,
             # never before prep. Stay black (the cutscene FADI above) straight into prep.
             '    CALL(%s) /* preparations (PREP, event cmd 0x3E) -- cap 9, lord force-deployed */\n'
             '    ENUT(8)\n'
             '    EVBIT_T(7)\n'
             '    ENDA\n}' % (CH03_TREX_GREEN_SYMBOL, CH03_PREP_SCRIPT))
    script = _replace_brace_block(script, 'EventScr_Ch4_BeginningScene[] =', begin, CH4_EVENTSCRIPT_H)
    # DefeatBoss ending (the script the Misc AFEV runs on the grell's death): victory sting ->
    # fade the mine out -> the ENDING cutscene over the reused Targos-winter BG (RBG takes the
    # bounty; Trex negotiates his warren into the town, which frees him to leave with the party;
    # Meesmickle's deadpan button) -> the dev-placeholder landing (RBG-by-the-campfire, then back
    # to title). ch04 isn't hosted yet, so the LANDING parks on the placeholder exactly as ch02's
    # ending does; the chaining pass (#23) swaps that dev landing for MNC2 -> ch04.
    end_text_calls = _scenic_beat_calls(
        CH03_ENDING_MSGS, end_beats,
        ['A -- RBG collects the Masthew bounty; the gems a "gratuity"',
         'B -- Trex negotiates his kobolds into the town, then asks to join the party',
         'C -- Meesmickle deadpan button (his one line of the chapter)'])
    ending = ('{\n    MUSC(SONG_VICTORY)\n'
              '    FADI(16) /* fade the mine out */\n'
              '    REMOVEPORTRAITS\n'
              '    BACG(%s) /* Termalaine square (reused Targos-winter BG) */\n'
              '    FADU(16)\n'
              '    BROWNBOXTEXT(0x%X, 8, 8) /* "Termalaine" location card */\n'
              % (CH03_ENDING_BG, CH03_ENDING_CARD_MSG)
              + end_text_calls +
              '    FADI(16) /* fade the square out into the dev-placeholder landing */\n'
              + dev_placeholder_scene() +
              '    ENDA\n}')
    script = _replace_brace_block(script, CH03_ENDING_SCRIPT + '[] =', ending, CH4_EVENTSCRIPT_H)
    # Trex's LIGHT entrance beat (Colm's turn-1 green-NPC pattern): a dead Ch4 Village script,
    # rewritten to show Pinky's telegraph ("He waved at me!") + RBG's warm "little dragon" over
    # the map. Fired by the turn-1 TURN entry (step 3). All of Trex's substance rides the TALK.
    script = _replace_brace_block(
        script, CH03_TREX_ENTRANCE_SCRIPT + '[] =',
        '{\n    TEXTSHOW(0x%X) /* Trex entrance: Pinky telegraph + RBG "little dragon" */\n'
        '    TEXTEND\n    REMA\n    EVBIT_T(7)\n    ENDA\n}' % CH03_TREX_ENTRANCE_MSG,
        CH4_EVENTSCRIPT_H)
    # Trex talk-recruit script (#23 item 2): repurpose the dead Ch4 Turn-2 green script symbol
    # -> show Trex's migrated talk line then CUSA green Trex to blue. Every CHAR entry (step 3)
    # points here, so ANY core party member's talk runs it (the vanilla Colm/Neimi shape).
    script = _replace_brace_block(script, CH03_TREX_TALK_SCRIPT + '[] =',
                                  trex_talk_script, CH4_EVENTSCRIPT_H)
    # Midmap RBG-execution beat (#23 item 1): the Misc AFEV runs this on the Brute's death. Plays
    # ON-MAP (no BACG -- the chapter continues on the same battle map). Each beat renders by whether
    # it has a face (_beat_is_faceless): FACED beats ride a map talk bubble via Text() (TEXTSTART..REMA
    # -- its trailing REMA clears the beat's faces, so none bleed into the next; a bare TEXTSHOW without
    # it left Pinky up under Wolfram). A speaker with no mug would ride the opaque AUTO-CENTERED box
    # (SOLOTEXTBOXSTART) -- a map bubble anchors to a speaking unit and an AFEV has none, so a faceless
    # bubble renders off the tilemap. All four midmap speakers now have mugs (the Brute got one on the
    # Caellach slot), so all four are faced bubbles here. EVBIT_T(7) marks the map event done.
    mid_labels = ['A -- Pinky reaches out to the beaten Brute (faced)',
                  'A2 -- ACTION: the Brute lunges at Pinky; claws ring off metal (faceless box)',
                  'A3 -- the Brute\'s shock: "you not soft?!" (faced mug)',
                  'B -- RBG levels the Fonduedler: "Say cheese." (faced)',
                  'B2 -- ACTION: the shot; the Brute drops dead (faceless box)',
                  'B3 -- Pinky "you saved me!" / RBG "always, my boy" (faced two-hander)',
                  'C -- Wolfram\'s oblivious ore gag deflates the moment (faced)']
    mid_calls = ''
    for msg, beat, lbl in zip(CH03_MIDMAP_MSGS, mid_beats, mid_labels):
        if _beat_is_faceless(beat, cut_fid):
            mid_calls += ('    SVAL(EVT_SLOT_B, 0xFF00FF) /* auto-center the opaque solo box (#58) */\n'
                          '    SOLOTEXTBOXSTART\n    TEXTSHOW(0x%X) /* %s */\n    TEXTEND\n    REMA\n'
                          % (msg, lbl))
        else:
            mid_calls += '    Text(0x%X) /* %s */\n' % (msg, lbl)
    script = _replace_brace_block(
        script, CH03_MIDMAP_SCRIPT + '[] =',
        '{\n' + mid_calls + '    EVBIT_T(7)\n    ENDA\n}', CH4_EVENTSCRIPT_H)
    with open(CH4_EVENTSCRIPT_H, 'w', encoding='utf-8') as f:
        f.write(script)

    # 4. Texts: chapter title (status/prep banner). The grell's death quote was CUT (Nicolas): it
    #    has no portrait, so the faceless line rendered boxless + unreadable -- the DefeatBoss win now
    #    fires silently off the grell's flagged gDefeatTalkList entry (step 5, .msg = 0).
    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    set_message_body(lines, host['chapTitleTextId'], name_message_body(chap['title']))
    # The borrowed slot-6 defeat_boss goal block still points its Status-screen objective at
    # vanilla's "Defeat Saar" -- rewrite it as "Defeat <boss fe_name>" (the prologue precedent;
    # the goal WINDOW banner is a static "Defeat boss" by goal type, so only this text leaks).
    ch03_boss = next(e for e in chap['enemy_units'] if e.get('is_boss'))
    set_message_body(lines, host['goal']['statusObjectiveTextId'],
                     name_message_body('Defeat ' + (ch03_boss.get('fe_name') or ch03_boss['name'])))
    # Trex talk-recruit body (#23 item 2): his migrated pitch (chapter YAML talk_recruit event,
    # single source of truth), faced on the Rennac slot. One speaker -> one [OpenX] block with
    # page breaks; the recruit script (EventScr_089F199C) TEXTSHOWs it before the CUSA.
    talk = next(e for e in chap['events'] if e.get('trigger') == 'talk_recruit')['script']
    set_message_body(lines, CH03_TREX_TALK_MSG, _script_to_message(
        talk, {trex_uid: ('[OpenMidRight]', _fid_tag(tslot))}))
    # Cutscene beats (#23 Cutscenes): the opening + ending scenic beats over the Targos-winter BG
    # (location card + one message per beat, staged via _emit_scene_beats) and Trex's light on-map
    # entrance line (map-bubble wrap 29). Speakers resolve through cut_fid (cast busts + the crier
    # mug + faceless narration). RBG anchors mid-right in the opening + entrance (op_home).
    set_message_body(lines, CH03_OPENING_CARD_MSG, name_message_body(op_card))
    # Beat D (Pinky scouts, index 3) fades ONLY Pinky at its end so RBG holds through the STAL(90)
    # pause (Nicolas 2026-07-10). Pinky sits at the _stage_beat default podium ([OpenMidLeft] --
    # op_home anchors only prof-rbg, to [OpenMidRight]); the trailing [ClearFace] there fades his
    # portrait out, RBG's untouched. Pairs with scout_raw (no trailing REMA) in the event script.
    op_trailings = [None, None, None, '[OpenMidLeft][ClearFace]', None]
    _emit_scene_beats(lines, CH03_OPENING_MSGS, op_beats, cut_fid, op_home,
                      trailings=op_trailings)
    set_message_body(lines, CH03_ENDING_CARD_MSG, name_message_body(end_card))
    _emit_scene_beats(lines, CH03_ENDING_MSGS, end_beats, cut_fid, {})
    # Midmap RBG-execution beats (on-map, no card): faced beats wrap at the talk bubble's budget; the two
    # faceless ACTION boxes take SOLO_BOX_BUDGET_PX, the auto-centered opaque box's own clamp.
    # Beat A (Pinky's opening)
    # PRELOADS the Brute's mug as a silent listener at mid-right, so the player sees WHO Pinky is
    # talking to before it lunges (the Brute otherwise only appeared when it snarled in A3 -- Nicolas
    # 2026-07-11). The Brute + RBG both anchor mid-right via op_home (never on screen together; each
    # beat's REMA clears faces); Pinky/party default mid-left.
    brute_face = cut_fid('kobold-brute')   # [FID_Caellach] -- the Brute's mug slot
    mid_preloads = [[('[OpenMidRight]', brute_face)]] + [None] * (len(mid_beats) - 1)
    for msg, beat, preload in zip(CH03_MIDMAP_MSGS, mid_beats, mid_preloads):
        # TWO RENDERERS, TWO UNITS, and the pair is deliberate. A FACED beat rides the talk
        # window, whose real constraint is pixels (fe8_talk_font). A FACELESS one rides the
        # auto-centered SOLOTEXTBOXSTART box (helpbox.c) -- a different proc with less room,
        # which nobody has measured in pixels, so it keeps the character width it was authored
        # against and says so with `measure=len`. Converting it on the talk window's evidence
        # would be extending a measurement past what it measured.
        kw = ({'width': fe8_talk_font.SOLO_BOX_BUDGET_PX}
              if _beat_is_faceless(beat, cut_fid) else {})
        set_message_body(lines, msg, _script_to_message(
            beat, _stage_beat(beat, cut_fid, op_home), preload=preload, **kw))
    set_message_body(lines, CH03_TREX_ENTRANCE_MSG, _script_to_message(
        trex_entr, _stage_beat(trex_entr, cut_fid, op_home)))
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    # 4a. Title card image (the intro/status banner is a 4bpp image, not text) -- "Ch.3:
    #     <title>" composed from vanilla glyphs, overwriting the host slot's vanilla card
    #     (chapTitleId 4 = the "Ch.4: Ancient Horrors" card). gen_chapter_title reads the
    #     source cards from HEAD, so overwriting chap_title_4.png here doesn't disturb any cut.
    _write_chapter_title_card(host, 'Ch.3: ' + chap['title'])

    # 5. The grell's flagged gDefeatTalkList entry keys the DefeatBoss win to its raw pid (first-match
    #    scan wins; no vanilla 0xb7 entry to shadow). .flag = EVFLAG_DEFEAT_BOSS is what fires the win.
    #    .msg = 0: NO death quote (the grell has no portrait, so the faceless line rendered boxless +
    #    unreadable; Nicolas cut it). The engine still sets the flag -- DisplayDefeatTalkForPid only
    #    shows the quote `if (ent->msg != 0)` but SetPidDefeatedFlag runs regardless (eventinfo.c:595).
    #    The Brute miniboss rides the SAME silent-quote idiom: its flagged death sets the tmp flag
    #    CH03_BRUTE_DEFEAT_FLAG that the mid-map RBG-execution AFEV watches (step 3). Different pids
    #    -> both entries coexist at the head; the first-match pid scan keys each to its own unit.
    _prepend_defeat_quote(flag_defeat_quote(
        CH03_BOSS_PID, 'CHAPTER_L_4', 'EVFLAG_DEFEAT_BOSS',
        'grell (ch03 boss): silent defeat -> DefeatBoss WIN flag'))
    _prepend_defeat_quote(flag_defeat_quote(
        CH03_BRUTE_MINIBOSS_PID, 'CHAPTER_L_4', CH03_BRUTE_DEFEAT_FLAG,
        'Icewind Brute (ch03 miniboss): silent defeat -> mid-map RBG-execution AFEV'))

    if verbose:
        print('  ch03 map (obj1=%d pal=%d cfg=%d layout=%d) hosted on chapter %d; defeat_boss goal + '
              'DefeatBoss(grell) WIN wired, PREP deploy cap %d%s + %d enemies (grell@14,1); opening/entrance/midmap/ending cutscenes wired'
              % (obj_idx, pal_idx, cfg_idx, layout_idx, CH03_HOST_INDEX, len(cap_rows),
                 ' (boot-seeded party)' if boot else '', len(enemies)))
