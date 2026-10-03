"""Chapter 1 (#21): its injector and everything only it reads.
"""
import os
import subprocess
import sys

from PIL import Image

import fe8_talk_font
from inject.boot import _lord_select_event_seq, LORDSEL_EXPLAINER_MSG
from inject.cast import _classed_cast, CLASS_LOADOUT, GUEST_PORTRAIT_MAP, load_unit, PORTRAIT_MAP
from inject.chapter_ids import (
    CH01_BOSS_SLOT, CH01_GOAL_STATUS_MSG, CH01_GOAL_WINDOW_MSG, CH01_LORDSEL_BG,
    PROLOGUE_HLIN_SLOT, PROLOGUE_SCRAMSAX_SLOT)
from inject.decomp import (
    _replace_brace_block, DECOMP, FOUNDING_EXP_FLAG, git_env, LORDSEL_FLAG_BASE, REPO)
from inject.chapter_frame import write_event_group
from inject.hosting import _load_chapter_yaml, _retarget_host_chapter
from inject.hosts import CH01_EVENT_GROUP, CH01_HOST_INDEX, CH02_HOST_INDEX
from inject.maps import _register_chapter_map
from inject.message_alloc import appended_message_id
from inject.paths import CH2_EVENTINFO_H, CH2_EVENTSCRIPT_H, EVENTS_UDEFS_C, TEXTS_TXT
from inject.scenes import (
    _emit_scene_beats, _make_fid, _prepend_defeat_quote, _scenic_beat_calls, _split_event_beats,
    _stage_beat, _write_chapter_title_card)
from inject.text import (
    _fe_dialogue_text, _fid_tag, _script_to_message, _wrap_fe_lines, DEV_PLACEHOLDER_MSG,
    display_name, goal_window_body, name_message_body, set_message_body, vanilla_name_text_id)
from inject.units import (
    _ally_unit_entry, _deploy_cap_entries, _enemy_unit_entry, enemy_ai_initialiser)


CH01_LAYOUT = ('Ch01IronTrailMap', 'ch01-the-iron-trail')  # (asset label, maps/ stem)
CH01_CHAPTER_YAML = 'ch01-the-iron-trail.yaml'
                             # armor-knight boss bases -- the chief is a Breguet mirror
# Where the cast stands when the join-LOAD runs (pre-prep; PREP hides everyone and
# redeploys the picked 4 onto the YAML deploy_slots, so these only need to be legal
# tiles): a 5x2 block on the west trail mouth around the deploy zone.
CH01_JOIN_POSITIONS = [(c, r) for r in (8, 9) for c in range(1, 6)]


CH01_ITEM_IDS = {'iron-lance': 'ITEM_LANCE_IRON', 'iron-axe': 'ITEM_AXE_IRON'}
# ch01's grunts are goblins: they ride the CLONED goblin classes, whose own class entries
# carry the Fire Imp map sprite (SMSId) and the goblin AnimConf. Name the SLOT here, the way
# every other chapter does (ch05: 'soldier' -> CLASS_SOL_SKELEBERDIER) -- resolving a skin
# from the vanilla base at build time is what shipped ch01 as ch05's skeletons (#347).
# armor-knight is reskinned by nobody, so the chief stays a vanilla Knight.
CH01_CLASS_IDS = {'soldier': 'CLASS_BLST_REGULAR_EMPTY',
                  'fighter': 'CLASS_BLST_LONG_EMPTY',
                  'armor-knight': 'CLASS_ARMOR_KNIGHT'}
LORDSEL_CONFIRM_MSGS = (0x959, 0x95A, 0x95B, 0x95C, 0x95D, 0x95E, 0x95F,
                        0x962, 0x963, 0x964)  # same dead pool, one per candidate
LORDSEL_PITCH_MSGS = (0x967, 0x968, 0x969, 0x96A, 0x96B, 0x96C, 0x96D,
                      0x96E, 0x96F, 0x970)  # one per candidate (cast capped at 10)
LORDSEL_HEADER_MSG = 0x971   # "Choose your lead" prep-screen header (#46); same dead pool
# The one-time "(a) explain" box (feedback #4): drawn once before the pick loop. Locked
# gist (decisions.md / #46): the chosen hero is the must-survive lead for the whole
# campaign. Faithful to the gist; final wording is Nicolas's render-review call.
LORDSEL_EXPLAINER_TEXT = (
    "One of you must lead the company. Your chosen hero carries the whole "
    "campaign -- if they fall in battle, the war is lost. Choose well."
)
# Beat 1 (#21) "The Northlook" scenic opening: a location card + one message per
# beat (A-E), all riding dead vanilla Ch1-tutorial slot-2 message ids (the prologue
# host strips Ch1's tutorial event lists, so these never display in our ROM).
CH01_BEAT1_CARD_MSG = 0x945
CH01_BEAT1_MSGS = (0x940, 0x941, 0x942, 0x943, 0x944)  # A,B,C,D,E (0x945 = card)
# ch01 ending "The Rolling Cheddar" (#21): a "Bryn Shander" location card + one message
# per beat (A-F), on the dead slot-2 pool (see Beat 1). RESOLVED (#125, 2026-07-05):
# 0x949/0x94A/0x94B/0x94C are ALSO TEXTSHOWn by the tutorial-mode trade demo compiled
# into src/bmtrade.c (EventScr_TradeTut_SelectItem etc.), which nothing patches -- but
# that demo is gated on CheckTradeTutorial() -> CheckFlag(0x87), and flag 0x87 has
# exactly one setter in the whole decomp: ENUT(0x87) inside
# EventScr_Ch1Tut_TradeSelectGalliamEnd (events/ch1-tutorials.h), part of vanilla's
# REAL Ch1 slot (Ch1Events, data_8B363C.s) -- a separate ROM asset from PrologueEvents,
# which is the only slot our chapter progression ever loads (New Game redirects to
# PROLOGUE_HOST_INDEX; see _redirect_new_game). Vanilla Ch1 never loads in our build, so
# flag 0x87 can never be set, CheckTradeTutorial() always returns false, and the trade
# demo (and this msg-id collision) is provably unreachable -- no emulator repro needed.
CH01_ENDING_CARD_MSG = 0x94C
# AB,C,D,E1,E2(narration),E2b(Marty/Baxby),F. 0x93D is a dead vanilla Ch1-tutorial
# slot-2 id (weapon-triangle blurb, stripped by the prologue host) reused for the
# faceless "Marty leans in..." narration that #58 split into its own opaque box.
CH01_ENDING_MSGS = (0x946, 0x947, 0x948, 0x949, 0x93D, 0x94A, 0x94B)
CH01_BODY_MSG = 0x956    # the dismembered sled-driver (dead vanilla Ch2 slot-2 scene id)
CH01_TAUNT_MSG = 0x960   # Izobai's turn-1 boss taunt (no vanilla event-script ref at all)
# Wolfram's turn-1 line on the healing forts + gate, after the taunt (#21). Vanilla teaches the same
# thing in Ch1 (EventScr_Ch1Tut_GuideTerrainHeal), but only in tutorial mode; ADR 0104 keeps tutorial
# mode off Normal, so ours is party dialogue and plays on every difficulty.
CH01_TERRAIN_HEAL_MSG = appended_message_id('ch01', 'terrain-heal-warning')
# Guide "Fortresses & Castle Gates" (MSG_0627). Vanilla's beat ends on ENUT(0xCE); without SOME Guide
# flag set, IsGuideLocked() hides the Guide command from the map menu entirely.
CH01_GUIDE_FORTS_FLAG = 0xCE
DEV_PLACEHOLDER_SPEAKER = 'prof-rbg'   # RBG, the company's over-engineer (Moulder slot)
DEV_PLACEHOLDER_LINE = (
    "Ah -- mind the edge there, friends! That's as far as we've built the world. "
    "The rest is still curing down in the cellar -- you can't rush a good wheel, you "
    "know. Thank you kindly for playtesting! Hold your whey... there's a great deal "
    "more adventure left to age. Come back when it's ripe."
)


def _term_pad(body):
    """FE8 Huffman terminator-parity (see [[manchego_stars_text_terminator_parity]]):
    the utf8 message packer (textprocess.py) pairs printable bytes two-at-a-time, so a
    printable run with an ODD length makes its last char swallow the FOLLOWING byte --
    and when that byte is the 0x00 terminator the decoder runs past [X] into the next
    message (garbage + bleed-through). Pad with a [.] before [X] so the odd char eats the
    pad instead. The parity that matters is the FINAL run (the printables after the last
    control code), NOT the whole message: a multi-line body whose earlier [LF] runs are
    odd can sum to an even total yet still have an odd final run (Pinky: 16+19+13=48 even,
    final run 13 odd). No-op when the final run is already even."""
    if not body.endswith('[X]'):
        return body
    inner = body[:-3]                       # strip the [X] terminator
    last_close = inner.rfind(']')           # final run = text after the last control tag
    final_run = (inner[last_close + 1:] if last_close != -1 else inner).replace('\n', '')
    if len(final_run) % 2:
        body = inner + '[.][X]'
    return body


def dev_placeholder_message():
    """The RBG dev-placeholder message body (one speaker, scenic wrap)."""
    slot = PORTRAIT_MAP[DEV_PLACEHOLDER_SPEAKER]
    return _script_to_message(
        [{DEV_PLACEHOLDER_SPEAKER: DEV_PLACEHOLDER_LINE}],
        {DEV_PLACEHOLDER_SPEAKER: ('[OpenMidLeft]', _fid_tag(slot))})


def founding_exp_table(campaign, cast):
    """gFoundingExpGrants[] as C (#430 step 4, ADR 0320): what the prologue's twin pays each
    founding career (`exp_curve.founding_grant`), as { pid, exp } byte pairs, 0-terminated.
    Engine patch 0015 hands it over once, at ch01's prep Fight!, and the model banks the same
    numbers, so the exp guard and the cartridge read one source. `cast` is [(uid, slot)]."""
    import exp_curve
    grant = exp_curve.founding_grant(campaign)
    founding = [(uid, slot) for uid, slot in cast if uid in grant]
    if {uid for uid, _ in founding} != set(grant):
        sys.exit('ERROR: founding grant names %s, but ch01 fields %s'
                 % (sorted(grant), sorted(uid for uid, _ in founding)))
    return '\n'.join(
        ['', '/* Founding exp (#430 step 4, build-generated from exp_curve.founding_grant):',
         '   { pid, exp } pairs, 0-terminated. FoundingExp_ApplyOnce raises each level-1',
         '   unit to its grant once, at the first prep Fight! (flag 0x%X). */' % FOUNDING_EXP_FLAG,
         'CONST_DATA u8 gFoundingExpGrants[] = {'] +
        ['    CHARACTER_%s, %d, /* %s */' % (slot.upper(), grant[uid], uid)
         for uid, slot in founding] +
        ['    0,', '};', ''])


def lord_floor_rows(campaign, uids, ch='ch01', target=3.5):
    """Per-lord survivability-floor deltas (#45 3b): one (uid, hp, def, res) tuple per uid,
    in input order, = difficulty.lord_floor_delta vs chapter `ch`'s enemies @`target` bulk-
    durability. The engine adds the CHOSEN lord's row to its stats ONCE at chapter start
    (#45 3c), so it must stay parallel to the gLordSelectCandidates[] it is indexed against.

    Local-imports difficulty: difficulty imports this module, so a top-level import would
    cycle (HANDOFF gotcha)."""
    import difficulty
    _, _, line, bosses, _, _ = difficulty.load_field(campaign, ch)
    threat = line + bosses
    rows = []
    for uid in uids:
        f = difficulty.lord_floor_delta(
            difficulty.player_combatant(campaign, uid), threat, target=target)
        rows.append((uid, f.hp, f.df, f.res))
    return rows


def lord_select_pitches(campaign, uids):
    """Per-candidate lord-select blurbs (#46): one (uid, pitch) tuple per uid, in input
    order, read off each cast member's hand-authored `lord_pitch:` YAML. The build emits
    these as sLordSelectPitchMsg[] (eventscript TU), PARALLEL to gLordSelectCandidates[] --
    LordSelect_DrawCard draws candidate i's pitch as the cursor lands on it. Hard-fails if any candidate lacks
    a pitch: a blank card would ship silently (the "no silent gaps" lock, Nicolas
    2026-06-20)."""
    rows = []
    for uid in uids:
        pitch = load_unit(campaign, uid).get('lord_pitch')
        if not pitch:
            sys.exit('ERROR: lord-select candidate %r has no lord_pitch (#46): every '
                     'candidate needs a qualitative blurb -- no silent gaps.' % uid)
        rows.append((uid, pitch))
    return rows


def ch01_turn1_taunt_script(heal_beat):
    """Izobai's taunt, Wolfram's terrain-heal line, then vanilla GuideTerrainHeal's tail (#21).

    Vanilla's tail flashes the healing tiles and sets the Guide flag. The camera opens on the
    first tile (Izobai's gate) so the flashes land on screen; ch05's arena beat does the same."""
    tiles = heal_beat['flash_tiles']
    flashes = ''.join('    CURSOR_FLASHING(%d, %d)\n' % tuple(t) for t in tiles)
    return ('{\n'
            '    TEXTSHOW(0x%X) /* Izobai turn-1 taunt */\n'
            '    TEXTEND\n'
            '    REMA\n'
            '    TEXTSHOW(0x%X) /* Wolfram: the mounds and the gate heal them */\n'
            '    TEXTEND\n'
            '    REMA\n'
            '    CAMERA(%d, %d)\n'
            '%s'
            '    STAL(60)\n'
            '    CURE\n'
            '    ENUT(0x%X) /* Guide: Fortresses & Castle Gates */\n'
            '    EVBIT_T(7)\n'
            '    ENDA\n}'
            % (CH01_TAUNT_MSG, CH01_TERRAIN_HEAL_MSG, tiles[0][0], tiles[0][1], flashes,
               CH01_GUIDE_FORTS_FLAG))


def inject_ch01(campaign, verbose=True, boot=False):
    """Wire Ch1 "The Iron Trail" (#21) onto chapter slot 2 (ch00's MNC2(0x2) target).

    Field parity (decisions.md 2026-06-10): the deploy cap IS the ally UnitDefinition
    table -- GetChapterAllyUnitCount (eventscr3.c) counts its entries and the prep
    flow (SortPlayerUnitsForPrepScreen, prepscreen.c) clamps deployment to that
    count, force-deployed units first. The prep screen itself opens via the PREP
    event command (0x3E), reached through the shared CALL(EventScr_08591FD8)
    (eventscr.c:4283) exactly like every vanilla prep chapter (Ch4+). The
    hasPrepScreen field in chapter_settings.json is dead ("left over from FE7",
    chapterdata.h:37) -- the event call is the only gate.

    MUST run before inject_prologue: it copies vanilla slot 1's goal block (the
    Seize display template) which inject_prologue overwrites with the prologue's
    defeat_boss goal.
    """
    maps_dir = os.path.join(REPO, 'campaigns', campaign, 'maps')
    chap = _load_chapter_yaml(campaign, CH01_CHAPTER_YAML)

    # 0. Beat 1 (#21): the Northlook opening, consumed from the chapter YAML's locked
    #    chapter_start `script:` and staged below (step 4) as a scenic off-map scene
    #    (BACG bg_Fireplace) at the head of EventScr_Ch2_BeginningScene. The script
    #    splits on `beat_break` sentinels into 5 messages (A-E); each rides one `Text()`
    #    whose trailing REMA clears all faces (eventscr.c sub_800E640) -> a fresh 4-face
    #    budget per beat. TWO SIDES: the quest-givers stand on the RIGHT (Hlin mid-right,
    #    Scramsax far-right, Hruna right) and the party on the LEFT. The roll-call rotates
    #    one PC at a time through the mid-left spotlight (eviction); monologue beats PRELOAD
    #    a few PCs as silent listeners on the left so Hlin/RBG address a populated room
    #    instead of empty air, and the haggle puts Hruna across from RBG. Hlin's final
    #    "who leads?" line stays in the scene (end of beat E, at the Northlook); the
    #    lord-select menu then plays over its own scenic BG (not the battle map).
    b1_card, b1_beats = _split_event_beats(chap, 'chapter_start', 'ch01 Beat 1',
                                           CH01_BEAT1_MSGS)

    b1_guests = {'hlin': _fid_tag(PROLOGUE_HLIN_SLOT),
                 'scramsax': _fid_tag(PROLOGUE_SCRAMSAX_SLOT),
                 'hruna': _fid_tag('VILLAGER_WOMAN')}
    b1_fid = _make_fid(b1_guests, 'ch01 Beat 1 unknown speaker')
    # Podium geometry (gTalkFaceHPosLut, scene.c, px = x*8; faces are 96px = 12 tiles):
    # FarLeft 24 | MidLeft 48 | Left 72 | Right 168 | MidRight 192 | FarRight 216.
    # Two faces only avoid overlap when >=96px apart, so the clean "two-shot" is
    # MidLeft <-> MidRight (144px). Speakers therefore default to the mid-left podium
    # and Hlin anchors mid-right; everyone rotating through one inner podium keeps the
    # stage to two non-overlapping faces (Nicolas, 2026-06-16: Hlin/Scramsax & the
    # 3-stack were too crowded). Silent listeners fill the OUTER podiums where a touch
    # of overlap reads as "a couple standing together."
    b1_home = {'hlin': '[OpenMidRight]'}
    # per-beat silent listeners (podium -> face), and per-beat speaker-podium overrides
    b1_preload = [
        [],                                                            # A: Scramsax<->Hlin two-shot
        [('[OpenMidRight]', b1_fid('hlin'))],                          # B: Hlin watches the roll-call
        [('[OpenLeft]', b1_fid('wolfram'))],                           # C: Wolfram listens (Braulo speaks here now)
        [],                                                            # D: Hruna<->Hlin two-shot
        [('[OpenMidRight]', b1_fid('hruna'))],                         # E: Hruna across from RBG
    ]
    # beat B: Pinky peeks out far-left beside his father (RBG speaks from mid-left) -- they
    # read as a pair (Nicolas, 2026-06-16: keep). Beat B now ENDS on that pair: Braulo's
    # "name the job" line moved to the head of beat C (YAML), so the beat's REMA clears the
    # RBG+Pinky pair before Braulo speaks. Otherwise Pinky lingered far-left BEHIND Braulo:
    # he sits on a different podium than the one Braulo's mid-left load would evict, so
    # nothing cleared him (Nicolas's friends, 2026-06-17). In beat C Braulo speaks from his
    # crowd spot (FarLeft) and stays as a silent listener through Hlin's story.
    b1_overrides = [None, {'pinky': '[OpenFarLeft]'},
                    {'braulo': '[OpenFarLeft]'}, None, None]

    # 0b. Ending "The Rolling Cheddar" (#21): the locked chapter_end `script:`, consumed
    #     the same way as Beat 1 -- a "Bryn Shander" location card + one message per beat
    #     (A-F), each rendered with the scenic full-screen wrap and staged below; each
    #     rides its own Text()/REMA in EventScr_Ch2_EndingScene (step 4) so the 4-face
    #     budget resets per beat. Duvessa (the host, Speaker of Bryn Shander) anchors the
    #     mid-right podium throughout; the party speaks from mid-left, with the other beat
    #     speaker(s) staged as clean two-shots opposite her (cf. Beat 1 podium geometry).
    end_card, end_beats = _split_event_beats(chap, 'chapter_end', 'ch01 ending',
                                             CH01_ENDING_MSGS)

    # narration = faceless stage-business box (no portrait); the fallback covers
    # the duvessa/hruna/baxby cutscene faces (GUEST_PORTRAIT_MAP).
    end_fid = _make_fid({'narration': None}, 'ch01 ending unknown speaker',
                        fallback=GUEST_PORTRAIT_MAP)
    # Duvessa hosts from mid-right (like Hlin in Beat 1); everyone else defaults mid-left.
    # Per-beat overrides put the OTHER speaker opposite her for a clean two-shot: Hruna
    # (C) and Meesmickle (D) take mid-right; in E, Baxby takes mid-right -- evicting
    # Duvessa's face there (a [ClearFace] step-out) as she gestures to the market and the
    # bird steps forward. Marty stays mid-left across E.
    end_home = {'duvessa': '[OpenMidRight]'}
    # NO silent-listener preloads: a preloaded face fades out and back in at every beat's
    # REMA boundary it straddles -- exactly the Marty/Duvessa "flashing during dialogue"
    # Nicolas flagged 2026-06-17. Each beat now shows ONLY its actual speakers, and the
    # scene is split so no character spans a REMA: consecutive same-speaker beats are
    # merged (A+B = one continuous Duvessa beat), and the REMA fades land only between
    # genuinely different casts (read as scene transitions, not flashes). In E2 the right
    # podium starts EMPTY so Baxby fades in fresh for his answer (Duvessa was cleared at
    # the E1->E2 boundary, never swapped on the same podium).
    end_preload = [[], [], [], [], [], [], []]
    # AB, C, D, E1, E2(narration -- faceless, override unused), E2b(Baxby fades in
    # mid-right opposite Marty), F.
    end_overrides = [None, {'hruna': '[OpenMidRight]'},
                     {'meesmickle': '[OpenMidRight]'}, None, None,
                     {'baxby': '[OpenMidRight]'}, None]

    # 1. Map: register the painted layout and point slot 2 at it + the winter tileset
    #    (same flow as inject_prologue step 1). Goal display = vanilla Ch1's own Seize
    #    template (windowDataType "seize"), copied from slot 1 while it is still vanilla.
    indices = _register_chapter_map(maps_dir, CH01_LAYOUT,
                                    'Manchego Stars ch01 layout (#21)')
    obj_idx, pal_idx, cfg_idx, layout_idx = indices
    host = _retarget_host_chapter(
        CH01_HOST_INDEX, 1, 'seize',
        'ERROR: slot 1 goal is not the vanilla Seize template -- '
        'inject_ch01 must run BEFORE inject_prologue',
        indices, chap['chapter_number'], CH01_EVENT_GROUP,
        (CH01_GOAL_WINDOW_MSG, CH01_GOAL_STATUS_MSG))

    # 2. Rosters (events_udefs.c). Four tables, all reusing vanilla Ch2 symbols so no
    #    extern surgery is needed (scripts/eventinfo already declare them):
    #    - UnitDef_Event_Ch2Ally: the 4-slot deploy template = THE CAP. Never LOADed;
    #      the prep flow reads its entry count (cap) and positions (deploy tiles).
    #    - UnitDef_088B440C: the cast join-LOAD (whole roster enters the party at the
    #      Northlook; the engine benches everyone past the cap).
    #    - UnitDef_088B4344: the 7 initial goblins. UnitDef_088B44AC: the 3 west
    #      reinforcements (turn 3).
    # cast_names is parallel to cast: lord-select menu/confirm display names (#42).
    # available_at=1: the founding party on the field at ch01 -- later recruits (Baxby ch01
    # via market -> ch02 prep; Trex ch03) are not in the ch01 join-LOAD / lord-select / world map.
    cast, cast_names = _classed_cast(campaign, available_at=chap['chapter_number'])
    for unit_id, _, class_enum, _, _ in cast:
        if class_enum not in CLASS_LOADOUT:
            sys.exit('ERROR: no loadout for %s (unit %s)' % (class_enum, unit_id))
    if len(cast) > len(LORDSEL_CONFIRM_MSGS):
        sys.exit('ERROR: %d lord candidates > %d reserved confirm text ids'
                 % (len(cast), len(LORDSEL_CONFIRM_MSGS)))
    if len(cast) > len(CH01_JOIN_POSITIONS):
        sys.exit('ERROR: %d classed cast > %d ch01 join positions'
                 % (len(cast), len(CH01_JOIN_POSITIONS)))
    leader = 'CHARACTER_%s' % cast[0][1].upper()

    # classIndex rides the DEPLOY class (dce) -- which today equals the real vanilla class
    # (ce) for EVERY unit: the #65 clone-class approach is retired (custom anims ride the
    # per-character _u25 path; see deploy_class_for). The split survives only as a seam.
    join = [_ally_unit_entry(leader, slot, dce, lv, x, y,
                             ', '.join(CLASS_LOADOUT[ce]), ' /* %s */' % uid)
            for (uid, slot, ce, dce, lv), (x, y) in zip(cast, CH01_JOIN_POSITIONS)]
    deploy = _deploy_cap_entries(chap, cast, leader, 'ch01')

    by_eid = {e['id']: e for e in chap['enemy_units']}
    spear, axe = by_eid['goblin-spear'], by_eid['goblin-axe']
    chief, reinf = by_eid['goblin-chief'], by_eid['goblin-reinforcements']

    enemies = []
    for index, (x, y) in enumerate(spear['positions']):
        enemies.append(_enemy_unit_entry(
            '0x80', CH01_CLASS_IDS[spear['class']], spear['level'], True, x, y,
            CH01_ITEM_IDS[spear['inventory'][0]['id']],
            enemy_ai_initialiser(chap, spear, index),
            ' /* goblin spear -- camp approach */'))
    for index, (x, y) in enumerate(axe['positions']):
        enemies.append(_enemy_unit_entry(
            '0x80', CH01_CLASS_IDS[axe['class']], axe['level'], True, x, y,
            CH01_ITEM_IDS[axe['inventory'][0]['id']],
            enemy_ai_initialiser(chap, axe, index),
            ' /* goblin raider -- mid-trail pursuer */'))
    cx, cy = chief['position']
    # The iron-ingots MacGuffin stays narrative (no FE8 item exists for it yet);
    # recovery is told in the ending scene. The chief mirrors Breguet 1:1: his slot's
    # vanilla boss bases, no autolevel, lv4, his own borrowed AI, ON the seize tile.
    enemies.append(_enemy_unit_entry(
        'CHARACTER_%s' % CH01_BOSS_SLOT, CH01_CLASS_IDS[chief['class']],
        chief['level'], False, cx, cy,
        CH01_ITEM_IDS[chief['inventory'][0]['id']], enemy_ai_initialiser(chap, chief),
        ' /* goblin chief -- boss, holds the seize tile */'))
    reinforce = []
    for index, (cls, (x, y)) in enumerate(zip(reinf['composition'], reinf['positions'])):
        reinforce.append(_enemy_unit_entry(
            '0x80', CH01_CLASS_IDS[cls], reinf['level'], True, x, y,
            CH01_ITEM_IDS[reinf['inventory_by_class'][cls][0]],
            enemy_ai_initialiser(chap, reinf, index), ' /* west reinforcement, turn %d */'
            % reinf['spawn_turn']))

    with open(EVENTS_UDEFS_C, encoding='utf-8') as f:
        udefs = f.read()
    for marker, entries in (
            ('UnitDef_Event_Ch2Ally[] =', deploy),
            ('UnitDef_088B440C[] =', join),
            ('UnitDef_088B4344[] =', enemies),
            ('UnitDef_088B44AC[] =', reinforce)):
        block = '{\n' + '\n'.join(entries) + '\n    { 0 },\n}'
        udefs = _replace_brace_block(udefs, marker, block, EVENTS_UDEFS_C)
    # Lord-select candidate pids (#42), menu order = classed cast order; the engine
    # recovers the chosen pid by scanning permanent flags LORDSEL_FLAG_BASE + i
    # (LordSelect_GetPid, eventinfo.c).
    udefs += '\n'.join(
        ['', '/* Lord-select candidate pids (#42, build-generated): menu order =',
         '   classed cast order; chosen pid = flag scan (LordSelect_GetPid). */',
         'CONST_DATA u16 gLordSelectCandidates[] = {'] +
        ['    CHARACTER_%s, /* %s */' % (slot.upper(), uid)
         for uid, slot, _, _, _ in cast] +
        ['    0xFFFF,', '};', ''])
    # (The per-candidate pitch + "Choose your lead" header msg ids live in the eventscript
    #  TU as sLordSelectPitchMsg[] / an inlined header, drawn directly by LordSelect_DrawCard
    #  -- no global table is needed.)
    # Lord survivability floors (#45 3b): per-candidate { +maxHP, +Def, +Res }, PARALLEL to
    # gLordSelectCandidates above (same menu order). Computed @target 3.5 bulk-durability vs
    # Ch1 enemies -- the shamans' frail floor; the armor tanks score 0. The engine adds the
    # chosen lord's triple to its unit ONCE at chapter start, flag-gated (#45 3c).
    floor_rows = lord_floor_rows(campaign, [uid for uid, _, _, _, _ in cast])
    udefs += '\n'.join(
        ['', '/* Lord survivability floors (#45 3b, build-generated): per-candidate',
         '   { +maxHP, +Def, +Res } at base level, parallel to gLordSelectCandidates above.',
         "   The engine adds the chosen lord's triple to maxHP/curHP/def/res ONCE at chapter",
         '   start, gated by a permanent flag (#45 3c) -- bakes in, then fades as it levels. */',
         'CONST_DATA s8 gLordFloorDeltas[] = {'] +
        ['    %d, %d, %d, /* %s */' % (hp, df, res, uid)
         for uid, hp, df, res in floor_rows] +
        ['};', ''])
    udefs += founding_exp_table(campaign, [(uid, slot) for uid, slot, _, _, _ in cast])
    with open(EVENTS_UDEFS_C, 'w', encoding='utf-8') as f:
        f.write(udefs)

    # 3. Event lists (ch2-eventinfo.h). Turn: the west wave on turn 3 (vanilla's own
    #    reinforcement idiom: FACTION_ID_BLUE = appear at the start of the player
    #    phase, act on the following enemy phase -- cf. ch9a). Location: the two
    #    vanilla-Ch1-parity hint houses + Seize on the chief's tile (the Seize macro
    #    raises EVFLAG_WIN -> ending scene). Turn: the road-sign+body narration at
    #    battle start (turn 1, #5) + Izobai's taunt + reinforcements. Misc:
    #    CauseGameOverIfLordDies (fires on EVFLAG_GAMEOVER, raised by the UnitKill
    #    hook when the chosen lead falls -- _inject_lord_select_engine, #42).
    sx, sy = chap['objective']['seize_tile']
    houses = [e for e in chap['events'] if e.get('type') == 'house']
    # The road-sign + body narration (#5): fires at BATTLE START as a turn-1 event (not a
    # tile step), so the party always reads it. Presence-checked here; wired as the first
    # turn-1 TURN entry below (its script body is EventScr_Ch2_Talk_EirikaRoss, step 4).
    next(e for e in chap['events'] if e.get('trigger') == 'battle_start')
    heal_beat = next(e for e in chap['events']
                     if e.get('trigger') == 'turn_start' and e.get('turn') == 1)
    write_event_group('ch01', CH2_EVENTINFO_H, CH01_EVENT_GROUP, lists={
        'turnBasedEvents':
            '{\n    TURN(0x0, EventScr_Ch2_Talk_EirikaRoss, 1, 0, FACTION_ID_BLUE)'
            ' /* #5: roadsign + body, read at battle start (was a [8,8] tile trigger) */\n'
            '    TURN(0x0, EventScr_Ch2_Turn2Player, 1, 0, FACTION_ID_BLUE)'
            ' /* Izobai turn-1 taunt */\n'
            '    TURN(0x0, EventScr_Ch2_Turn1Player, %d, 0, FACTION_ID_BLUE)'
            ' /* west reinforcements */\n'
            '    END_MAIN\n}' % reinf['spawn_turn'],
        'locationBasedEvents':
            '{\n    House(0x0, EventScr_Ch2_Village1, %d, %d)\n'
            '    House(0x0, EventScr_Ch2_Village2, %d, %d)\n'
            '    Seize(%d, %d)\n    END_MAIN\n}'
            % (houses[0]['tile'][0], houses[0]['tile'][1],
               houses[1]['tile'][0], houses[1]['tile'][1], sx, sy),
        'miscBasedEvents': '{\n    CauseGameOverIfLordDies\n    END_MAIN\n}',
    }, roster='UnitDef_Event_Ch2Ally',
        scenes=('EventScr_Ch2_BeginningScene', 'EventScr_Ch2_EndingScene'))

    # 4. Scenes (ch2-eventscript.h), mechanical pass -- real dialogue lands in the
    #    dialogue pass (LAST, per the slice plan). Beginning = vanilla prep-chapter
    #    shape (cf. Ch4): the ch00 guests leave the party (DISA = ClearUnit -- Orson's
    #    own departure idiom), enemies deploy, the cast joins, then the shared prep
    #    call. PREP hides all units, runs Pick Units (cap 4), and redeploys the picks
    #    onto the ally-template tiles.
    # 4a. Lord-select menu (#42), prepended so the scene below can ASMC it. Pure
    #     route-split clone: same draw callback, same menu flow, same confirm idiom
    #     (Command stores the confirm text id in EVT_SLOT_C; the scene SADDs it
    #     into slot 2, TEXTSHOW(0xffff) shows it, and the [Yes] answer comes back
    #     in EVT_SLOT_C -- 1 = yes, anything else re-opens the menu).
    items = []
    for i, ((uid, slot, _, _, _), name) in enumerate(zip(cast, cast_names)):
        items.append(
            '    {\n'
            '        .name = (const char *)0x8205958, /* vanilla dummy (rodata is discarded) */\n'
            '        .nameMsgId = 0x%X, /* %s rides this vanilla name slot */\n'
            '        .overrideId = %d,\n'
            '        .color = TEXT_COLOR_SYSTEM_WHITE,\n'
            '        .isAvailable = MenuAlwaysEnabled,\n'
            '        .onDraw = MenuCommand_DrawRouteSplit,\n'
            '        .onSelected = Command_SelectLord,\n'
            '        .onSwitchIn = LordSelect_DrawCard, /* #46: live candidate card */\n'
            '    },' % (vanilla_name_text_id(slot), uid, i))
    menu_code = (
        '/* ==== Lord select (#42/#46, build-generated): "choose your lead" screen ====\n'
        '   A stock candidate menu (route-split flow: pick -> confirm text in EVT_SLOT_C)\n'
        '   COMPOSED with a live info card (Nicolas 2026-06-25 layout, supersedes the\n'
        '   prep_unitselect clone). The names list rides the LEFT column; as the cursor\n'
        '   lands on candidate i the menu engine fires onSwitchIn (uimenu.c), which draws\n'
        '   that candidate\'s FULL 80x72 bust on the RIGHT (PutFace80x72 -> BG tilemap, so\n'
        '   it layers over the scenic BACG with no OBJ-vs-BG priority fight) + the\n'
        '   qualitative PITCH (#46) below it, in DrawUiFrame panels. The pick is stored as\n'
        '   permanent flag 0x%X + item index and read back by LordSelect_GetPid\n'
        '   (eventinfo.c). One confirm + one pitch text per candidate (dead vanilla\n'
        '   Ch1-tutorial slot-2 message ids). Coords are render-tunable. */\n'
        '\n'
        '#include "uimenu.h"\n'
        '#include "hardware.h"\n'
        '#include "uiutils.h"\n'
        '#include "bmlib.h"\n'
        '#include "bmunit.h"\n'
        '#include "face.h"\n'
        '#include "fontgrp.h"\n'
        '\n'
        'extern const u16 gLordSelectCandidates[]; /* events_udefs.c */\n'
        '\n'
        'static CONST_DATA u16 sLordSelectConfirmMsg[] = { %s };\n'
        '/* #46: qualitative blurb per candidate, PARALLEL to gLordSelectCandidates. */\n'
        'static CONST_DATA u16 sLordSelectPitchMsg[] = { %s };\n'
        '\n'
        '/* #46 card (Nicolas 2026-06-25 layout): names MENU on the LEFT; as the cursor\n'
        '   lands on candidate i, draw their FULL 80x72 bust on the RIGHT (PutFace80x72 ->\n'
        '   BG tilemap, over the scenic BACG) + the qualitative PITCH wrapped BELOW it.\n'
        '   The 8-item menu exhausts the shared system-font tile pool (each glyph is 2\n'
        '   tiles tall), so the pitch gets its OWN font in free BG VRAM (tile 0x140 =\n'
        '   VRAM 0x2800 (0x140<<5), in the gap between the menu pool -- which spills just\n'
        '   past the system font at 0x80 -- and the bust at 0x200) -- no clash with the\n'
        '   menu name tiles, full manual control of the box. */\n'
        'extern void InitTextFont(struct Font * font, void * vram, int chr, int palid);\n'
        '\n'
        'int LordSelect_DrawCard(struct MenuProc* menu, struct MenuItemProc* menu_item)\n'
        '{\n'
        '    const struct CharacterData* cd =\n'
        '        GetCharacterData(gLordSelectCandidates[menu_item->itemNumber]);\n'
        '    const char* s = GetStringFromIndex(sLordSelectPitchMsg[menu_item->itemNumber]);\n'
        '    struct Font pitchFont;\n'
        '    char buf[40];\n'
        '    char* o = buf;\n'
        '    int line = 0;\n'
        '\n'
        '    /* full bust, RIGHT, top-aligned at row 4 (rows 4..0xC): on a 20-row screen\n'
        '       under a 4-row title, this is the only fit that leaves 3 pitch lines\n'
        '       (rows 0xD/0xF/0x11) clear of the box bottom border at row 0x13. Clear the\n'
        '       BG0 block first (reveals the blue panel on BG1), then redraw. */\n'
        '    TileMap_FillRect(TILEMAP_LOCATED(gBG0TilemapBuffer, 0xE, 4), 15, 9, 0);\n'
        '    PutFace80x72(menu, TILEMAP_LOCATED(gBG0TilemapBuffer, 0x11, 4),\n'
        '                 cd->portraitId, 0x200, 0xD);\n'
        '\n'
        '    /* pitch BELOW the bust, in its OWN font/VRAM (tile 0x140), so it never\n'
        '       collides with the menu name tiles. [LF]-delimited lines, two tile-rows\n'
        '       apart (FE8 text is 16px tall); control bytes (the [.] parity pad) skipped.\n'
        '       Restore the system font afterwards so the menu keeps drawing. */\n'
        '    InitTextFont(&pitchFont, (void*)(0x06000000 + 0x2800), 0x140, 0);\n'
        '    /* Scrub the WHOLE pitch tile band (3 lines x 15 cols x 2 rows = 90 tiles)\n'
        '       before drawing: a shorter line over a previous candidate\'s longer one left\n'
        '       its tail glyphs in VRAM (per-line ClearText alone did not catch it). */\n'
        '    CpuFastFill16(0, (void*)(0x06000000 + 0x2800), 90 * 0x20);\n'
        '    TileMap_FillRect(TILEMAP_LOCATED(gBG0TilemapBuffer, 0xE, 0xD), 15, 6, 0);\n'
        '    for (;; s++) {\n'
        '        if (*s == 0x01 || *s == 0x00) {\n'
        '            *o = 0;\n'
        '            /* PutDrawText(NULL,...) InitTexts a throwaway Text from the ACTIVE\n'
        '               font (pitchFont) -- so the line\'s tiles allocate fresh from tile\n'
        '               0x140, chr_counter advancing per line so lines do not overlap. */\n'
        '            if (line < 3 && o != buf)\n'
        '                PutDrawText((struct Text*)0,\n'
        '                            TILEMAP_LOCATED(gBG0TilemapBuffer, 0xE, 0xD + 2 * line),\n'
        '                            TEXT_COLOR_SYSTEM_WHITE, 0, 15, buf);\n'
        '            if (*s == 0x00)\n'
        '                break;\n'
        '            line++;\n'
        '            o = buf;\n'
        '        } else if ((u8)*s >= 0x20 && o < buf + sizeof(buf) - 1) {\n'
        '            *o++ = *s; /* bounded: a pathologically long unwrapped line truncates,\n'
        '                          never smashes the stack (lines wrap at 20, buf is 40) */\n'
        '        }\n'
        '    }\n'
        '    SetTextFont(0); /* restore the system font for the menu */\n'
        '    InitSystemTextFont();\n'
        '\n'
        '    BG_EnableSyncByMask(BG0_SYNC_BIT | BG1_SYNC_BIT);\n'
        '    return 0;\n'
        '}\n'
        '\n'
        'u8 Command_SelectLord(struct MenuProc* menu, struct MenuItemProc* menu_item)\n'
        '{\n'
        '    int i;\n'
        '\n'
        '    /* re-picks (confirm answered "No") must not leave a stale flag */\n'
        '    for (i = 0; gLordSelectCandidates[i] != 0xFFFF; i++) {\n'
        '        ClearFlag(0x%X + i);\n'
        '    }\n'
        '\n'
        '    SetFlag(0x%X + menu_item->itemNumber);\n'
        '    SetEventSlotC(sLordSelectConfirmMsg[menu_item->itemNumber]);\n'
        '\n'
        '    return MENU_ACT_CLEAR | MENU_ACT_SND6A | MENU_ACT_END | MENU_ACT_SKIPCURSOR;\n'
        '}\n'
        '\n'
        'CONST_DATA struct MenuItemDef MenuItemDef_LordSelect[] = {\n'
        '%s\n'
        '    { 0 }\n'
        '};\n'
        '\n'
        'CONST_DATA struct MenuDef MenuDef_LordSelect = {\n'
        '    .rect = {1, 0, 9, 0}, /* names MENU on the LEFT (left-to-right reading) */\n'
        '    .style = 1,\n'
        '    .menuItems = MenuItemDef_LordSelect,\n'
        '};\n'
        '\n'
        'void CallLordSelectMenu(ProcPtr proc)\n'
        '{\n'
        '    ClearBg0Bg1();\n'
        '    /* BG2 OFF: the menu plays over a scenic BACG on BG3 (#21), not the battle\n'
        '       map -- leaving BG2 enabled would show the (disabled) map layer behind. */\n'
        '    SetDispEnable(1, 1, 0, 1, 1);\n'
        '    SetTextFont(0);\n'
        '    InitSystemTextFont();\n'
        '    LoadUiFrameGraphics();\n'
        '\n'
        '    /* title across the TOP: opaque frame box on the menu back BG (BG1, where the\n'
        '       UI-frame gfx is loaded), text on the front BG (BG0). */\n'
        '    DrawUiFrame(gBG1TilemapBuffer, 0xA, 0, 0x13, 4, 0, 1);\n'
        '    PutStringCentered(TILEMAP_LOCATED(gBG0TilemapBuffer, 0xB, 1),\n'
        '                      TEXT_COLOR_SYSTEM_WHITE, 0xE, GetStringFromIndex(0x%X));\n'
        '\n'
        '    /* opaque panel backing the BUST + pitch (BG1). Right edge (0xD+0x10=0x1D)\n'
        '       lines up with the title box right edge (0xA+0x13=0x1D), per Nicolas. Tall\n'
        '       enough (rows 4..0x14) for the 9-row bust AND 3 pitch lines below it. */\n'
        '    DrawUiFrame(gBG1TilemapBuffer, 0xD, 4, 0x10, 0x10, 0, 1);\n'
        '\n'
        '    /* (blurb text handles are InitText\'d in LordSelect_DrawCard, parked above\n'
        '       the menu names that StartMenu allocates below.) */\n'
        '    StartMenu(&MenuDef_LordSelect, proc);\n'
        '}\n'
        '\n'
        % (LORDSEL_FLAG_BASE,
           ', '.join('0x%X' % m for m in LORDSEL_CONFIRM_MSGS[:len(cast)]),
           ', '.join('0x%X' % m for m in LORDSEL_PITCH_MSGS[:len(cast)]),
           LORDSEL_FLAG_BASE, LORDSEL_FLAG_BASE, '\n'.join(items),
           LORDSEL_HEADER_MSG))
    with open(CH2_EVENTSCRIPT_H, encoding='utf-8') as f:
        script = f.read()
    script = menu_code + script
    # Declare CallLordSelectMenu in eventcall.h so eventscript files included BEFORE
    # ch2-eventscript.h (e.g. the ch1 sandbox, debug fast-boot) can ASMC it.
    eventcall_h = os.path.join(DECOMP, 'include', 'eventcall.h')
    with open(eventcall_h, encoding='utf-8') as f:
        ec = f.read()
    anchor = 'void CallRouteSplitMenu(ProcPtr proc);\n'
    if anchor in ec and 'CallLordSelectMenu' not in ec:
        ec = ec.replace(
            anchor, anchor + 'void CallLordSelectMenu(ProcPtr proc); /* lord select (#46) */\n', 1)
        with open(eventcall_h, 'w', encoding='utf-8') as f:
            f.write(ec)
    beat1_labels = ['A -- Hlin & Scramsax in from the cold',
                    'B -- the roll-call (PCs one at a time + RBG/Pinky, Hlin watching)',
                    "C -- Hlin's story: the endless winter",
                    "D -- the test: Hruna's iron job",
                    'E -- the price; Braulo commits; Hlin asks who leads']
    beat1_text_calls = _scenic_beat_calls(CH01_BEAT1_MSGS, b1_beats, beat1_labels)
    beat1_scene = (
        '    /* Beat 1 (#21): the Northlook -- scenic off-map scene over bg_Fireplace.\n'
        '       Built from the chapter YAML; faces are budget-managed (the 4-slot fix\n'
        '       in _script_to_message) and staged as clean two-shots (speakers rotate\n'
        '       through the mid-left/mid-right inner podiums; silent listeners fill the\n'
        '       outer ones so no one talks to an empty room). The brown-box card\n'
        '       auto-dismisses (blocks ~100 frames then fades). Beat E ends on Hlin\'s\n'
        '       "who leads?" -- still at the Northlook. */\n'
        '    REMOVEPORTRAITS\n'
        '    BACG(BG_FIREPLACE)\n'
        '    FADU(16) /* chapter loads come up black; reveal the tavern BG */\n'
        '    BROWNBOXTEXT(0x%X, 8, 8) /* "The Northlook" location card */\n'
        % CH01_BEAT1_CARD_MSG
        + beat1_text_calls +
        '    FADI(16) /* fade the Northlook out */\n')
    if boot:
        # --ch01-boot (#353): the fast boot is a MAP load-test, so it drops everything that
        # stands between New Game and the trail -- the Northlook beats, lord select (#42) and
        # Preparations. Same shape as --ch03/04/05-boot ("cutscenes stripped"), and the reason
        # this branch has to exist at all: ch01 is the only hosted chapter whose opening runs a
        # MENU, and a controller that meets an unrecognised menu cannot reach the map (measured
        # 2026-09-02 -- mapshot on the first cut died on the 8-item lord-select with
        # "fail:nil ... never reached the map"). The company LOAD is ch01's own, so the boot
        # still founds the party exactly as the canonical chapter does -- no seed table.
        boot_scene = (
            '{\n'
            '    EVBIT_MODIFY(0x0)\n'
            '    SVAL(EVT_SLOT_B, 0x0) /* map camera origin for the reload */\n'
            '    LOMA(0x%X) /* RestartBattleMap -- build the trail map fresh */\n'
            '    DISA(CHARACTER_NATASHA) /* Hlin stays in Bryn Shander (ch00 guest) */\n'
            '    DISA(CHARACTER_KYLE)    /* Scramsax departs (ch00 guest) */\n'
            '    LOAD1(0x1, UnitDef_088B4344) /* goblins */\n'
            '    ENUN\n'
            '    LOAD1(0x1, UnitDef_088B440C) /* the company signs on at the Northlook */\n'
            '    ENUN\n'
            '    FADU(16) /* chapter loads come up black; reveal the trail */\n'
            '    ENUT(8)\n'
            '    EVBIT_T(7)\n'
            '    ENDA\n}' % (CH01_HOST_INDEX,))
        script = _replace_brace_block(script, 'EventScr_Ch2_BeginningScene[] =', boot_scene,
                                      CH2_EVENTSCRIPT_H)
    else:
        script = _replace_brace_block(
        script, 'EventScr_Ch2_BeginningScene[] =',
        '{\n'
        + beat1_scene +
        '    /* Lord select (#42) on its OWN scenic BG -- a "choose your leader" screen,\n'
        '       NOT the battle map (Nicolas, 2026-06-16). The menu window draws on BG0/1\n'
        '       over the BACG on BG3; CallLordSelectMenu keeps BG2 (map) off. The explainer\n'
        '       + re-pick loop is the SHARED _lord_select_event_seq (also the lord-fast\n'
        '       debug boot); here we append the post-Yes map build. */\n'
        + _lord_select_event_seq(CH01_LORDSEL_BG, LORDSEL_EXPLAINER_MSG)
        + '    EVBIT_MODIFY(0x0)\n'
        '    /* leader chosen: fade the scenic BG out, build the battle map, deploy. */\n'
        '    FADI(16)\n'
        '    SVAL(EVT_SLOT_B, 0x0) /* map camera origin for the reload */\n'
        '    LOMA(0x%X) /* RestartBattleMap -- builds the trail map fresh (cf. ch13a) */\n'
        '    DISA(CHARACTER_NATASHA) /* Hlin stays in Bryn Shander (ch00 guest) */\n'
        '    DISA(CHARACTER_KYLE)    /* Scramsax departs (ch00 guest) */\n'
        '    LOAD1(0x1, UnitDef_088B4344) /* goblins */\n'
        '    ENUN\n'
        '    LOAD1(0x1, UnitDef_088B440C) /* the company signs on at the Northlook */\n'
        '    ENUN\n'
        # NO FADU here: the shared prep prologue (EventScr_08591F64) fades to black itself before
        # drawing Preparations, so revealing the freshly-LOMA'd map first only FLASHES it for a
        # beat before prep blanks it. Vanilla prep chapters go straight into CALL(prep). Stay black.
        '    CALL(EventScr_08591FD8) /* preparations (PREP, event cmd 0x3E) */\n'
        '    ENUT(8)\n'
        '    EVBIT_T(7)\n'
        '    ENDA\n}' % (CH01_HOST_INDEX,),
        CH2_EVENTSCRIPT_H)
    script = _replace_brace_block(
        script, 'EventScr_Ch2_Turn1Player[] =',
        '{\n    SVAL(EVT_SLOT_2, UnitDef_088B44AC)\n'
        '    CALL(EventScr_LoadReinforce)\n'
        '    EVBIT_T(7)\n    ENDA\n}', CH2_EVENTSCRIPT_H)
    # Izobai's turn-1 taunt rides the spare vanilla Turn2Player slot (externed in
    # eventcall.h; fired at turn 1 by the Turn list above), shown over the map. Wolfram's
    # terrain-heal line follows, then vanilla's GuideTerrainHeal tail: flash the healing
    # tiles, unlock the Guide entry (#21).
    script = _replace_brace_block(script, 'EventScr_Ch2_Turn2Player[] =',
                                  ch01_turn1_taunt_script(heal_beat), CH2_EVENTSCRIPT_H)
    script = _replace_brace_block(
        script, 'EventScr_Ch2_Village1[] =',
        '{\n    IGNORE_KEYS(0)\n    HouseEvent(0x93B, 0x0)\n}', CH2_EVENTSCRIPT_H)
    script = _replace_brace_block(
        script, 'EventScr_Ch2_Village2[] =',
        '{\n    IGNORE_KEYS(0)\n    HouseEvent(0x93C, 0x0)\n}', CH2_EVENTSCRIPT_H)
    # The trailhead sign + the body are faceless narration shown OVER the battle map at
    # BATTLE START (wired as the first turn-1 TURN entry above, #5 Nicolas 2026-06-17 --
    # was a [8,8] tile trigger; now the party always reads it). SOLOTEXTBOXSTART renders
    # them in an opaque, bordered box (gProcScr_BoxDialogue, helpbox.c) instead of the
    # default translucent map talk window -- readable over the snow ("roadsign hard to
    # read"). EVT_SLOT_B = 0x00FF00FF feeds x=y=0xFF into sub_800E31C, so the box
    # auto-centers (dialogue-box config flag 0x100). One SOLOTEXTBOXSTART per page since
    # REMA tears the talk down between them.
    script = _replace_brace_block(
        script, 'EventScr_Ch2_Talk_EirikaRoss[] =',
        '{\n    SVAL(EVT_SLOT_B, 0xFF00FF) /* x=y=0xFF -> auto-center the solo box */\n'
        '    SOLOTEXTBOXSTART\n'
        '    TEXTSHOW(0x955) /* road sign + gouged warning */\n    TEXTEND\n    REMA\n'
        '    SOLOTEXTBOXSTART\n'
        '    TEXTSHOW(0x%X) /* the smashed sled + the body, just past the sign */\n'
        '    TEXTEND\n    REMA\n'
        '    EVBIT_T(7)\n    ENDA\n}' % CH01_BODY_MSG, CH2_EVENTSCRIPT_H)
    # ch01 ending "The Rolling Cheddar" (#21): scenic in-town scene, same machinery as
    # Beat 1's BeginningScene -- a "Bryn Shander" brown-box card + one Text() per beat
    # (A-F), each Text()'s trailing REMA clearing faces (fresh 4-face budget). The locked
    # bodies + staging are built in step 0b/step 6. The scene plays over BG_MS_BRYN_SHANDER_WINTER,
    # a vendored winter CG (#21). The 2026-06-17 call to keep vanilla's green BG_NORMAL_VILLAGE was
    # about PALETTE-swapping it, which just washed it out; the vendored-BG pipeline built for ch02
    # (bg_to_fe8.py -> inject_backgrounds) makes a real snowbound town available instead.
    # The ending MNC2s into ch02 "Cold Welcome" (hosted on chapter slot 3 by
    # inject_ch02; see the generated EventScr_Ch2_EndingScene below). Before ch02 landed
    # it parked on the dev placeholder instead.
    end_text_calls = _scenic_beat_calls(
        CH01_ENDING_MSGS, end_beats,
        ['A+B -- Duvessa thanks them, commissions them, grants the sled, points west',
         'C -- Wolfram asks Hruna for the iron to armor the sled',
         'D -- RBG over-engineers it; names it the Rolling Cheddar',
         'E1 -- Duvessa points to the axe-beak at the market',
         'E2 -- "Marty leans in..." faceless narration (opaque solo box, #58)',
         'E2b -- Marty wins over Baxby the axe-beak (first recruit)',
         'F -- "Targos is expecting weather. Better hurry."'])
    script = _replace_brace_block(
        script, 'EventScr_Ch2_EndingScene[] =',
        '{\n    MUSC(SONG_VICTORY)\n'
        '    REMOVEPORTRAITS\n'
        '    BACG(BG_MS_BRYN_SHANDER_WINTER) /* Bryn Shander -- vendored winter CG (#21) */\n'
        '    FADU(16) /* chapter ending comes up black; reveal the town BG */\n'
        '    BROWNBOXTEXT(0x%X, 8, 8) /* "Bryn Shander" location card */\n'
        % CH01_ENDING_CARD_MSG
        + end_text_calls +
        '    FADI(16) /* fade the town out */\n'
        '    MNC2(0x%X) /* -> ch02 "Cold Welcome", hosted on chapter slot 3 (inject_ch02) */\n'
        '    ENDA\n}' % CH02_HOST_INDEX,
        CH2_EVENTSCRIPT_H)
    with open(CH2_EVENTSCRIPT_H, 'w', encoding='utf-8') as f:
        f.write(script)

    # 5. The chief's defeat quote: head of gDefeatTalkList (same shadowing rule as the
    #    prologue entries). No flag -- the win is the Seize, not the boss kill.
    quote = ('    {\n'
             '        .pid     = CHARACTER_%s, /* goblin chief death quote (ch01) */\n'
             '        .route   = CHAPTER_MODE_ANY,\n'
             '        .chapter = CHAPTER_L_2, /* ch01 is hosted on chapter slot 2 */\n'
             '        .msg     = 0x0961, /* body rewritten from the chapter YAML */\n'
             '    },' % CH01_BOSS_SLOT)
    _prepend_defeat_quote(quote)

    # 6. Texts. Overwritten ids are vanilla slot-2 messages our build can never show
    #    (the vanilla Ch2 scenes are gone) plus vanilla Ch1's own house hints, which
    #    only the Ch1 location list referenced -- and our prologue host stripped it.
    #    House/sign/ending bodies are functional placeholders for the playtests; the
    #    dialogue pass owns the real words.
    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    set_message_body(lines, vanilla_name_text_id(CH01_BOSS_SLOT),
                     name_message_body(display_name(chief)))
    set_message_body(lines, host['chapTitleTextId'],
                     name_message_body(chap['title']))
    set_message_body(lines, host['goal']['statusObjectiveTextId'],
                     name_message_body('Seize camp'))
    set_message_body(lines, host['goal']['windowTextId'],
                     goal_window_body('Seize camp'))
    chief.setdefault('id', 'goblin-chief')
    # Izobai (boss, her custom bust on the Breguet slot): turn-1 taunt + death quote,
    # both from the chapter YAML (lore/izobai.md voice). She/her throughout.
    izobai_face = {'izobai': ('[OpenMidRight]', _fid_tag(CH01_BOSS_SLOT))}
    set_message_body(lines, CH01_TAUNT_MSG, _script_to_message(
        [{'izobai': chief['taunt']}], izobai_face, width=fe8_talk_font.BATTLE_QUOTE_BUDGET_PX))
    heal_fid = _make_fid({}, 'ch01 terrain-heal unknown speaker')
    set_message_body(lines, CH01_TERRAIN_HEAL_MSG, _script_to_message(
        heal_beat['script'], _stage_beat(heal_beat['script'], heal_fid, {})))
    set_message_body(lines, 0x961, _script_to_message(
        [{'izobai': chief['death_quote']}], izobai_face, width=fe8_talk_font.BATTLE_QUOTE_BUDGET_PX))
    # Hint houses -- vanilla Ch1's own two house quotes (0x93B/0x93C) reskinned with the
    # goblin nouns (dialogue pass, 2026-06-17). Two different villager faces, like vanilla.
    set_message_body(lines, 0x93B, _script_to_message([{'villager': (
        "The rumors are true, aren't they? Goblins have taken the old waystation. "
        "Looks like they've dug into the mounds, too. Smart work -- the mounds provide "
        "defense and heal wounds to boot. They must be vicious, to have taken it. "
        'Watch yourself.'
    )}], {'villager': ('[OpenMidLeft]', '[FID_VillagerMan3]')}))
    set_message_body(lines, 0x93C, _script_to_message([{'villager': (
        'That goblin warlord, Izobai, was wearing the finest scrap-plate I have seen. '
        'It looked like it could turn aside almost any blade you swing at it. I know '
        "my armor, though. I'll wager a good blast of magic could get right through it."
    )}], {'villager': ('[OpenMidLeft]', '[FID_VillagerMan4]')}))
    # Trailhead (msg 0x955) = the sign + gouged warning; the body (CH01_BODY_MSG) follows
    # in the same trigger -- faceless narration, hand-wrapped at the on-map width.
    set_message_body(lines, 0x955, _term_pad(
                     'BRYN SHANDER -- 2 MILES.[LF]\nBelow it, freshly gouged:[A][LF]\n'
                     '-- KEEP WALKING --[X]'))
    set_message_body(lines, CH01_BODY_MSG, _term_pad(
                     'Just past the sign, a sled[LF]\nlies smashed in the snow.[A][LF]\n'
                     'Its driver lies beside it --[LF]\na dwarf, in pieces.[A][LF]\n'
                     'The iron is gone. Goblin[LF]\ntracks lead up the trail.[X]'))
    # ch01 ending "The Rolling Cheddar" (#21): the locked chapter_end script -> a "Bryn
    # Shander" card + one message per beat (A-F), rendered at the scenic full-screen wrap
    # with the staging built in step 0b (Duvessa hosts mid-right; two-shots opposite).
    # Each beat rides its own Text()/REMA (step 4), so the 4-face budget resets per beat.
    # (0x954, the old placeholder "ingots recovered" body, is repurposed as the dev
    # placeholder line -- DEV_PLACEHOLDER_MSG; the ingot recovery is told in beat A.)
    set_message_body(lines, DEV_PLACEHOLDER_MSG, dev_placeholder_message())
    set_message_body(lines, CH01_ENDING_CARD_MSG, name_message_body(end_card))
    _emit_scene_beats(lines, CH01_ENDING_MSGS, end_beats, end_fid, end_home,
                      end_overrides, end_preload)
    # Beat 1 (#21): the Northlook opening. Card + one message per beat (A-E), rendered
    # from the chapter YAML's locked script with the scenic full-screen wrap width and
    # the per-beat two-sided staging + silent listeners built in step 0. Each beat rides
    # its own Text()/REMA, so the 4-face budget resets per beat.
    set_message_body(lines, CH01_BEAT1_CARD_MSG, name_message_body(b1_card))
    _emit_scene_beats(lines, CH01_BEAT1_MSGS, b1_beats, b1_fid, b1_home,
                      b1_overrides, b1_preload)
    # Lord select (#42): Hlin's "who leads?" already lands in beat E (at the Northlook),
    # so the menu opens directly over its scenic BG -- no separate prompt. Per-candidate
    # confirm texts keep the vanilla route-split shape (cf. MSG_C14/C17/C18) incl. the
    # odd-printable-count [.] parity pad.
    for i, name in enumerate(cast_names):
        q = 'Will %s lead the party?' % name
        set_message_body(lines, LORDSEL_CONFIRM_MSGS[i], '%s%s[LF]\n[Yes][X]'
                         % (q, '[.]' if len(q) % 2 else ''))
    # Lord-select candidate pitches (#46): drawn IN-MENU by LordSelect_DrawCard, which
    # splits the decoded body on [LF] and renders each line through its own dedicated font
    # (no [A] paging -- the pitch is one static 3-line panel below the bust). _term_pad
    # guards the terminator parity (final-run rule). Build hard-fails on a missing pitch
    # (lord_select_pitches).
    for i, (uid, pitch) in enumerate(lord_select_pitches(campaign,
                                                         [u for u, *_ in cast])):
        # CHARACTERS, not pixels: this is the card panel, not the talk window -- a fixed
        # 20-column box drawn by LordSelect_DrawCard through its own font, so the talk
        # font's glyph widths do not describe it. `measure` says so at the call site.
        body = '[LF]'.join(_wrap_fe_lines(_fe_dialogue_text(pitch), width=20,
                                          measure=len))
        set_message_body(lines, LORDSEL_PITCH_MSGS[i], _term_pad(body + '[X]'))
    # The one-time explainer box (#46 (a)) rides the normal tutorial text box, so it uses
    # the talk decoder: [A] page breaks every two lines + the standard [.] parity pad.
    # TUTORIALTEXTBOXSTART, not the talk bubble: Event1B_TEXTSHOW routes it through the same
    # helpbox proc as the solo box, whose width clamps at 0xC0.
    expl = _wrap_fe_lines(_fe_dialogue_text(LORDSEL_EXPLAINER_TEXT),
                          fe8_talk_font.SOLO_BOX_BUDGET_PX)
    expl_body = ''.join(
        ln + ('' if j == len(expl) - 1
              else '[A]' if (j + 1) % 2 == 0 else '[LF]')
        for j, ln in enumerate(expl))
    set_message_body(lines, LORDSEL_EXPLAINER_MSG, _term_pad(expl_body + '[X]'))
    # Lord-select screen title (#46): "Choose your lead", drawn by the generated
    # CallLordSelectMenu title box (the prep screen's own "Pick N Units Left" is untouched).
    set_message_body(lines, LORDSEL_HEADER_MSG, _term_pad('Choose your lead[X]'))
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    # 6a. Title card image (the intro/status banner is a 4bpp image, not text).
    _write_chapter_title_card(host, 'Ch.1: ' + chap['title'])

    if verbose:
        print('  ch01 map (obj1=%d pal=%d cfg=%d layout=%d) hosted on chapter %d; '
              'deploy cap %d + PREP (vanilla Ch4+ idiom)'
              % (obj_idx, pal_idx, cfg_idx, layout_idx, CH01_HOST_INDEX, len(deploy)))
        print('  rosters: %d cast join, %d goblins + chief on (%d,%d) [Seize], '
              '%d west reinforcements turn %d'
              % (len(cast), len(enemies) - 1, cx, cy, len(reinforce),
                 reinf['spawn_turn']))


def inject_northlook_bitey(verbose=True):
    """Mount 'Ol Bitey -- the Northlook's stuffed-fish trophy -- over the hearth (#21
    Beat 1 set dressing; Scramsax name-drops him in beat A). A custom edit to the vanilla
    bg_Fireplace convo background: restore the vanilla PNG first (idempotent across
    builds), paint a small cold-water fish using ONLY existing palette colours (so each
    8x8 tile stays within its 4bpp 16-colour bank), and drop the converted intermediates
    so `make` re-derives them. Centered on the hearth (fire centre x=135); the cool
    blue-purple tones read as a frozen-lake trophy and survive the tile conversion."""
    from PIL import ImageDraw
    bg = os.path.join(DECOMP, 'graphics', 'bg', 'bg_Fireplace.png')
    subprocess.run(['git', '-C', DECOMP, 'checkout', '--', 'graphics/bg/bg_Fireplace.png'], env=git_env(),
                   check=True)
    im = Image.open(bg)
    pal = im.getpalette()
    # FE8 convo backgrounds are 4bpp: each 8x8 tile may only reference ONE 16-colour
    # sub-palette. The mantle tiles where Bitey hangs all use sub-palette BLOCK 5
    # (indices 80..95, the warm-stone tones) -- so the fish MUST be painted with block-5
    # indices, or the tile conversion can't fit its colours and garbles it to a black
    # blob (the old cool-blue fish drew from another block -> the in-game blob Nicolas
    # flagged). So a dark *smoked-fish* trophy in stone tones, reading against the light
    # tan wall by VALUE + a crisp black outline. Stamp explicit indices (not an RGB
    # lookup, which could resolve to the same colour in the wrong block).
    OUTL, BODY, BELLY, FIN, EYE = 80, 89, 82, 84, 92  # block-5 indices (see palette)
    cmap = {}
    def c(idx):
        rgb = tuple(pal[idx * 3:idx * 3 + 3])
        cmap[rgb] = idx
        return rgb + (255,)
    ov = Image.new('RGBA', (34, 15), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.ellipse([5, 3, 26, 11], fill=c(BODY), outline=c(OUTL))     # body
    d.arc([6, 6, 25, 12], 20, 160, fill=c(BELLY))               # belly sheen
    d.polygon([(12, 3), (20, 3), (16, 0)], fill=c(FIN))         # dorsal fin
    d.polygon([(25, 7), (33, 1), (30, 7), (33, 13)], fill=c(FIN), outline=c(OUTL))  # forked tail
    d.polygon([(12, 8), (16, 8), (12, 13)], fill=c(FIN))        # pectoral fin
    d.line([(5, 7), (1, 7)], fill=c(OUTL))                      # open mouth
    d.ellipse([7, 5, 10, 8], fill=c(EYE), outline=c(OUTL))      # eye socket (light, reads)
    d.point((8, 6), fill=c(OUTL))                               # pupil
    op, ovp = im.load(), ov.load()
    ox, oy = 118, 89                                             # centered over the hearth
    for y in range(15):
        for x in range(34):
            r, g, b, a = ovp[x, y]
            if a > 0:
                op[ox + x, oy + y] = cmap[(r, g, b)]
    im.save(bg)
    for ext in ('.feimg2.bin', '.feimg2.bin.lz', '.fetsa2.bin', '.gbapal'):
        stale = bg[:-4] + ext
        if os.path.exists(stale):
            os.remove(stale)
    if verbose:
        print("  'Ol Bitey mounted over the Northlook hearth (bg_Fireplace, #21)")
