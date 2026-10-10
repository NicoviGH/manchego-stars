"""The prologue (#20): its injector and everything only it reads.
"""
import json
import os
import re
import sys

from inject.asset_table import _asm_table_word_index
from inject.chapter_frame import write_settings_row, write_event_group
from inject.hosting import _load_chapter_yaml, GOAL_TEMPLATE, map_writes
from inject.chapter_ids import PROLOGUE_HLIN_SLOT, PROLOGUE_SCRAMSAX_SLOT, PROLOGUE_SEPHEK_SLOT
from inject.decomp import _find_brace_block, _replace_brace_block, fe_item_enum, REPO
from inject.hosts import PROLOGUE_CHAPTER_INDEX, PROLOGUE_EVENT_GROUP, PROLOGUE_HOST_INDEX
from inject.maps import _register_chapter_map
from inject.montage import inject_opening_montage, inject_world_tour
from inject.paths import (
    ASSET_TABLE_S, CH1_EVENTINFO_H, CH1_EVENTSCRIPT_H, CH1_UDEFS_H, CHAPTER_SETTINGS_JSON, CHARACTERS_C,
    GAMECONTROL_C, TEXTS_TXT)
from inject.scenes import (
    _prepend_battle_quote, _prepend_defeat_quote, _write_chapter_title_card, battle_quote_body,
    battle_quote_pair, defeat_quote_row)
from inject.stats import _set_field, _set_gender, donor_growths_and_ranks, guest_personal_line
from inject.text import (
    _fid_tag, _script_to_message, display_name, name_message_body, set_message_body,
    vanilla_name_text_id)
from inject.units import enemy_ai_initialiser


# The guest slots whose personal bases inject_prologue rewrites: Hlin and Scramsax onto their
# `twin:`'s vanilla line (Eirika's, Seth's), Sephek to zero, a bare class base. Named because it
# is the exception to ENEMY_BASE_SLOT: a unit on one of these slots does NOT inherit the vanilla
# character's line, however much the deployment looks like it should.
PROLOGUE_REWRITTEN_GUEST_SLOTS = (PROLOGUE_HLIN_SLOT, PROLOGUE_SCRAMSAX_SLOT, PROLOGUE_SEPHEK_SLOT)
PROLOGUE_LAYOUT = ('Ch00PrologueMap', 'ch00-prologue')  # (asset label, maps/ source stem)
PROLOGUE_CHAPTER_YAML = 'ch00-prologue-a-dagger-of-ice.yaml'
# The consumables a ch00 guest may carry. WEAPON_ITEM_ENUM is weapons-only (#53 seam rule).
_GUEST_CONSUMABLES = {'vulnerary': 'ITEM_VULNERARY'}


def guest_items_for(unit):
    """A guest's `.items` initialiser body, from its YAML inventory in order."""
    return ', '.join(_GUEST_CONSUMABLES[i['id']] if i['id'] in _GUEST_CONSUMABLES
                     else fe_item_enum(i) for i in unit.get('inventory') or ())


# Stand up the designed ch00 ("A Dagger of Ice") as the New Game target: register its
# winter layout onto chapter 0, rewrite the prologue rosters to Scramsax+Hlin vs
# Sephek+guards, strip the vanilla Eirika/Seth/Valter cutscene down to a deploy +
# DefeatBoss, name the three guests, and flag Hlin's death as game over. Runs AFTER
# inject_winter_tileset (reuses its registered snow tileset assets). Replaces
# inject_test_chapter as main()'s in-engine entry. Structural unit data (class/level/
# position/items/ai) tracks campaigns/.../chapters/ch00-prologue-a-dagger-of-ice.yaml;
# names are read from that YAML so they live in one place.

def _load_prologue_chapter(campaign):
    return _load_chapter_yaml(campaign, PROLOGUE_CHAPTER_YAML)


def _prologue_roster_blocks(chap, by_id, slots, classes, guest_items):
    """The prologue's two `UnitDefinition` initialisers, driven by the ch00 YAML.

    redaCount=0 places units statically at xPosition/yPosition (like inject_test_chapter);
    the boss rides the ONEILL slot (CA_BOSS marks it a boss for autolevel/UI -- the
    DefeatBoss EVENT flag comes from the flagged defeat quote, not from CA_BOSS). AI is
    BORROWED from each unit's vanilla donor and no longer written here (#335); Sephek
    carries an `ai_override:` in the YAML because O'Neill's DoNothing depends on a tutorial
    event-script we do not run.

    Levels, positions (0-indexed x,y), the guard head-count and the enemy weapons are read
    from the YAML. They used to be literals here under a comment that claimed otherwise,
    and because every literal happened to match what the YAML said, nothing looked wrong --
    a rebalance authored in the chapter file simply would not have shipped. #255's
    invalidation probe is what exposed it: bumping the boss's `level:` changed no injected
    byte, and two full ROM builds came out byte-identical. Keep this sourced.

    Guest INVENTORIES come from the YAML too (`guest_items_for`): weapons through
    WEAPON_ITEM_ENUM, and Hlin's Vulnerary through this module's own consumable map, because
    WEAPON_ITEM_ENUM is weapons-only by the #53 seam rule.

    slots       -- (hlin, scramsax, sephek) vanilla CHARACTER_ slot names
    classes     -- (hlin, scramsax) CLASS_ enums
    guest_items -- (hlin, scramsax) `.items` initialiser bodies
    """
    hlin_slot, scram_slot, sephek_slot = slots
    hlin_class, scram_class = classes
    hlin_items, scram_items = guest_items
    hlin, scram = by_id['hlin-trollbane'], by_id['scramsax']
    sephek, guard = by_id['sephek-kaltro'], by_id['caravan-guard']

    ally = (
        '{\n'
        '    {\n'
        '        .charIndex = CHARACTER_%(hlin_slot)s, /* Hlin -- frail must-survive lead */\n'
        '        .classIndex = %(hlin_class)s,\n'
        '        .leaderCharIndex = CHARACTER_%(hlin_slot)s,\n'
        '        .allegiance = FACTION_ID_BLUE,\n'
        '        .level = %(hlin_level)d,\n'
        '        .xPosition = %(hlin_x)d,\n'
        '        .yPosition = %(hlin_y)d,\n'
        '        .redaCount = 0,\n'
        '        .items = { %(hlin_items)s },\n'
        '    },\n'
        '    {\n'
        '        .charIndex = CHARACTER_%(scram_slot)s, /* Scramsax -- strong veteran (our Jeigan) */\n'
        '        .classIndex = %(scram_class)s,\n'
        '        .leaderCharIndex = CHARACTER_%(hlin_slot)s,\n'
        '        .allegiance = FACTION_ID_BLUE,\n'
        '        .level = %(scram_level)d,\n'
        '        .xPosition = %(scram_x)d,\n'
        '        .yPosition = %(scram_y)d,\n'
        '        .redaCount = 0,\n'
        '        .items = { %(scram_items)s },\n'
        '    },\n'
        '    { 0 },\n'
        '}' % {'hlin_slot': hlin_slot, 'hlin_class': hlin_class, 'hlin_items': hlin_items,
               'hlin_level': hlin['level'],
               'hlin_x': hlin['position'][0], 'hlin_y': hlin['position'][1],
               'scram_slot': scram_slot, 'scram_class': scram_class,
               'scram_items': scram_items, 'scram_level': scram['level'],
               'scram_x': scram['position'][0], 'scram_y': scram['position'][1]})

    # The guards ride two spare non-cast character slots. `count`/`positions` decide how
    # many are emitted and where; a disagreement between them would silently ship a roster
    # nobody authored, so it fails the build instead.
    guard_slots = (0x80, 0x82)
    import difficulty
    guard_class = difficulty._enemy_class_enum(guard['class'])
    if len(guard['positions']) != guard['count']:
        sys.exit('ERROR: ch00 caravan-guard has count=%d but %d position(s)'
                 % (guard['count'], len(guard['positions'])))
    if guard['count'] > len(guard_slots):
        sys.exit('ERROR: ch00 caravan-guard count=%d exceeds the %d spare character slot(s); '
                 'add one to guard_slots in _prologue_roster_blocks'
                 % (guard['count'], len(guard_slots)))
    guards = ''.join(
        '    {\n'
        '        .charIndex = 0x%02x, /* Torg\'s caravan guard */\n'
        '        .classIndex = %s,\n'
        '        .allegiance = FACTION_ID_RED,\n'
        '        .level = %d,\n'
        '        .xPosition = %d,\n'
        '        .yPosition = %d,\n'
        '        .redaCount = 0,\n'
        '        .items = { %s },\n'
        '        .ai = %s,\n'
        '    },\n' % (slot, guard_class, guard['level'], pos[0], pos[1],
                      fe_item_enum(guard['inventory'][0]),
                      enemy_ai_initialiser(chap, guard, index))
        for index, (slot, pos) in enumerate(zip(guard_slots, guard['positions'])))

    enemy = (
        '{\n'
        '    {\n'
        '        .charIndex = CHARACTER_%s, /* Sephek -- boss; escapes in the ending */\n'
        '        .classIndex = CLASS_MYRMIDON,\n'
        '        .allegiance = FACTION_ID_RED,\n'
        '        .level = %d,\n'
        '        .xPosition = %d,\n'
        '        .yPosition = %d,\n'
        '        .redaCount = 0,\n'
        '        .items = { %s },\n'
        '        .ai = %s,\n'
        '    },\n'
        '%s'
        '    { 0 },\n'
        '}' % (sephek_slot, sephek['level'], sephek['position'][0], sephek['position'][1],
               fe_item_enum(sephek['inventory'][0]),
               enemy_ai_initialiser(chap, sephek), guards))
    return ally, enemy


def inject_prologue(campaign, verbose=True, montage=False):
    """Wire the designed Prologue (#20) onto chapter 0 as the New Game target."""
    maps_dir = os.path.join(REPO, 'campaigns', campaign, 'maps')
    # Cold-open guests ride non-PORTRAIT_MAP vanilla slots (PROLOGUE_*_SLOT). Classes mirror
    # the ch00 YAML: a strong promoted "Jeigan" (Scramsax/Hero) + the frail must-survive lead
    # (Hlin/Fighter, UNPROMOTED -- the frailty is the point) -- the vanilla Prologue
    # Seth+Eirika dynamic. (Difficulty lives in the
    # roster levels/items below + the guest stat patch in step 4b.)
    hlin_slot, scram_slot, sephek_slot = (
        PROLOGUE_HLIN_SLOT, PROLOGUE_SCRAMSAX_SLOT, PROLOGUE_SEPHEK_SLOT)
    # Structural data the build emits comes from the ch00 YAML (single source of truth).
    chap = _load_prologue_chapter(campaign)
    by_id = {u['id']: u for u in chap['player_units'] + chap['enemy_units']}
    # Hlin = frail must-survive lead -> UNPROMOTED Fighter (frail like vanilla Eirika next to a
    # promoted unit; a custom FEMALE Fighter map sprite makes her read as a woman -- see
    # inject_map_sprites). Scramsax = dominant promoted "Jeigan" (Hero, the Seth
    # analog) -> a real Steel Sword so he can carry the map. Items: the ch00 YAML inventories.
    hlin_class, scram_class = 'CLASS_FIGHTER', 'CLASS_HERO'
    hlin_items = guest_items_for(by_id['hlin-trollbane'])
    scram_items = guest_items_for(by_id['scramsax'])

    # 1. Register the prologue layout (.mar + .json -> Makefile mar_to_map -> .bin -> .lz) and
    #    point the HOST chapter (Ch1) at it + the winter tileset. We host the prologue in the
    #    Ch1 chapter + event group, NOT the vanilla prologue slot (0): the prologue slot's
    #    event group (asset[7]) garbles the gameplay HUD/terrain display when loaded with our
    #    stripped chapter (garbage band, bad string-pointer loads), while a normal chapter's
    #    group (Ch1Events, asset[10]) loads cleanly -- proven by inject_test_chapter. New Game
    #    redirects 0 -> 1 (step 6). The prologue slot is left vanilla and never loaded.
    obj_idx, pal_idx, cfg_idx, layout_idx = _register_chapter_map(
        maps_dir, PROLOGUE_LAYOUT, 'Manchego Stars prologue layout (#20)')
    with open(CHAPTER_SETTINGS_JSON, encoding='utf-8') as f:
        settings = json.load(f)
    # The goal banner/objective display is chapter data, not events -- the host (vanilla
    # Ch1) says "Seize gate". Copy the vanilla Prologue's defeat_boss goal block, text ids too.
    goal = settings['chapters'][PROLOGUE_CHAPTER_INDEX]['goal']
    writes = dict(map_writes((obj_idx, pal_idx, cfg_idx, layout_idx)))
    writes.update(('goal.' + f, goal[f]) for f in GOAL_TEMPLATE)
    writes['goal.windowTextId'] = goal['windowTextId']
    writes['goal.statusObjectiveTextId'] = goal['statusObjectiveTextId']
    # The slot's own group: the prologue keeps Ch1Events rather than retargeting, and says so.
    writes['mapEventDataId'] = _asm_table_word_index(
        ASSET_TABLE_S, 'gChapterDataAssetTable', PROLOGUE_EVENT_GROUP)
    # fadeToBlack=1: the intro ends on black, not a map fade-in (see _retarget_host_chapter) --
    # our opening is a BG cutscene (the BeginningScene BACGs), so the vanilla map fade-in would
    # FLASH the map first. Slot 1 shipped with fadeToBlack=0; set it so the prologue matches.
    writes['fadeToBlack'] = 1
    host = write_settings_row('prologue', PROLOGUE_HOST_INDEX, writes)
    # The New Game save-slot select draws the VANILLA prologue slot's title-card
    # IMAGE ("Prologue: The Fall of Renais") -- it reads chapter 0's chapTitleId,
    # not the host's. Point slot 0 at the host's card (recomposed in step 4a);
    # slot 0 is never loaded as a chapter, so only this menu metadata matters.
    with open(CHAPTER_SETTINGS_JSON, encoding='utf-8') as f:
        settings = json.load(f)
    settings['chapters'][PROLOGUE_CHAPTER_INDEX]['chapTitleId'] = host['chapTitleId']
    with open(CHAPTER_SETTINGS_JSON, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)

    # 2. Rewrite the two prologue rosters from the ch00 YAML (_prologue_roster_blocks).
    ally, enemy = _prologue_roster_blocks(
        chap, by_id, (hlin_slot, scram_slot, sephek_slot), (hlin_class, scram_class),
        (hlin_items, scram_items))
    with open(CH1_UDEFS_H, encoding='utf-8') as f:
        udefs = f.read()
    udefs = _replace_brace_block(udefs, 'UnitDef_Event_Ch1Ally[] =', ally, CH1_UDEFS_H)
    udefs = _replace_brace_block(udefs, 'UnitDef_Event_Ch1Enemy[] =', enemy, CH1_UDEFS_H)
    with open(CH1_UDEFS_H, 'w', encoding='utf-8') as f:
        f.write(udefs)

    # 3. Strip the Ch1 cutscene scripting (like inject_test_chapter, which renders cleanly):
    #    the frame writes every list but Misc empty (#412), then the beginning scene is replaced
    #    with a bare deploy of both rosters. The Misc list keeps the win/lose
    #    machinery in the vanilla Prologue's shape (prologue-eventinfo.h): DefeatBoss = AFEV
    #    on EVFLAG_DEFEAT_BOSS, which Sephek's FLAGGED DEFEAT QUOTE sets on his death
    #    (step 5; CA_BOSS alone sets nothing) -> runs the ending scene; CauseGameOverIfLordDies = AFEV on
    #    EVFLAG_GAMEOVER, which Hlin's flagged defeat quote sets (step 5).
    write_event_group(
        'prologue', CH1_EVENTINFO_H, PROLOGUE_EVENT_GROUP,
        lists={'miscBasedEvents': '{\n    DefeatBoss(EventScr_Ch1_EndingScene)\n'
                                  '    CauseGameOverIfLordDies\n'
                                  '    END_MAIN\n}'},
        roster='UnitDef_Event_Ch1Ally',
        scenes=('EventScr_Ch1_BeginningScene', 'EventScr_Ch1_EndingScene'))

    with open(CH1_EVENTSCRIPT_H, encoding='utf-8') as f:
        script = f.read()
    # The chapter-start auto-cursor (ProcFun_ResetCursorPosition) now centers the camera +
    # cursor on the first player unit even when the lord rides a non-LORD slot (engine fix in
    # _patch_player_start_cursor_guard). Begin scene = the ch00 YAML's locked chapter_start
    # script, staged vanilla-Prologue-style: deploy the allies, brown-box location card
    # ("The Eastway", msg 0x664 -- step 4c), the opening dialogue ON the map (msg 0x90D;
    # vanilla 0x910's convention -- FE8 ships no snow background, and a green BG_PLAIN_*
    # reads wrong in a two-year winter, so the snowy map IS the backdrop), THEN deploy the
    # enemies -- Sephek "steps out" exactly when his interrupt lands in the text -- and
    # flash him to mark the boss before handing over control. The music is ducked under the
    # allies' talk and turns to Shadow of the Enemy as he steps out, vanilla's O'Neill cue
    # (EventScr_Prologue_ONeillSpawn; ADR 0336).
    begin = ('{\n    LOAD1(1, UnitDef_Event_Ch1Ally)\n    ENUN\n'
             '    BROWNBOXTEXT(0x664, 8, 8)\n'
             '    STAL(30)\n'
             '    FlashCursor(CHARACTER_%s, 60)\n'
             '    MUSI\n'
             '    Text(0x90D)\n'
             '    MUNO\n'
             '    LOAD1(1, UnitDef_Event_Ch1Enemy)\n    ENUN\n'
             '    FlashCursor(CHARACTER_%s, 60)\n'
             '    MUSC(SONG_SHADOW_OF_THE_ENEMY) /* as vanilla\'s O\'Neill steps out (ADR 0336) */\n'
             '    Text(0x90E)\n'
             '    NoFade\n    ENDA\n}' % (hlin_slot, sephek_slot))
    script = _replace_brace_block(
        script, 'EventScr_Ch1_BeginningScene[] =', begin, CH1_EVENTSCRIPT_H)
    # DefeatBoss ending = the YAML's locked chapter_end script (msg 0x918), vanilla
    # Prologue EndingScene shape minus its worldmap/supply ENUT flags: victory sting,
    # dialogue ON the map (over the spot where Sephek vanished -- same no-snow-BG
    # rationale as the opening), fade to black (the locked script ends on
    # fade_to_black -- no location-card tease, decided 2026-06-10), then advance.
    ending = ('{\n    MUSC(SONG_VICTORY)\n'
              '    Text(0x918)\n    FADI(16)\n'
              '    MNC2(0x2)\n    ENDA\n}')
    script = _replace_brace_block(
        script, 'EventScr_Ch1_EndingScene[] =', ending, CH1_EVENTSCRIPT_H)
    with open(CH1_EVENTSCRIPT_H, 'w', encoding='utf-8') as f:
        f.write(script)

    # 4. Names (read from the chapter YAML so they live in one place; fe_name handles
    #    FE8's 12-char buffer -- see [[manchego-stars-fe-name-truncation]]). chap/by_id
    #    were loaded at the top of the function.
    name_slots = [(PROLOGUE_HLIN_SLOT, 'hlin-trollbane'),
                  (PROLOGUE_SCRAMSAX_SLOT, 'scramsax'),
                  (PROLOGUE_SEPHEK_SLOT, 'sephek-kaltro')]
    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    for slot, uid in name_slots:
        unit = by_id[uid]
        unit.setdefault('id', uid)
        set_message_body(lines, vanilla_name_text_id(slot),
                         name_message_body(display_name(unit)))
    # 4a. Chapter title, both places FE8 keeps it: the intro/status banner is a 4bpp
    #     IMAGE (chap_title_data[chapTitleId], not text) -- recompose it from vanilla
    #     glyphs in the YAML's title (gen_chapter_title) and overwrite the host slot's
    #     card; the save-select/status TEXT rides chapTitleTextId. Stale .4bpp/.lz
    #     intermediates are removed so make re-converts the new PNG.
    set_message_body(lines, host['chapTitleTextId'],
                     name_message_body(chap['title']))
    # The New Game save-slot select shows the VANILLA prologue slot's title text
    # ("Prologue: <title>" with the prefix screen-composed) -- it reads chapter 0,
    # not the host, so retitle that slot's text too.
    set_message_body(lines,
                     settings['chapters'][PROLOGUE_CHAPTER_INDEX]['chapTitleTextId'],
                     name_message_body(chap['title']))
    # The copied goal block still points its Status-screen objective at vanilla's
    # "Defeat O'Neill" -- rewrite it as "Defeat <boss fe_name>" (vanilla keeps this
    # short; the YAML's full objective.description is for docs/banners).
    set_message_body(lines, host['goal']['statusObjectiveTextId'],
                     name_message_body('Defeat ' + display_name(by_id['sephek-kaltro'])))
    # Was an inline copy of _write_chapter_title_card, carrying the same delete-and-hope bug
    # (#245): make does not re-derive a deleted .4bpp.lz, so the prologue's card either broke
    # the build or silently never landed. One helper now, which owns the conversion.
    _write_chapter_title_card(host, 'Prologue: ' + chap['title'])

    # 4c. Dialogue (ch00 dialogue pass, 2026-06-10): message bodies are GENERATED from
    #     the chapter YAML's locked `script:` blocks + quote fields -- the YAML stays
    #     the single source of truth. Overwritten ids are vanilla messages that can
    #     never display in our ROM (the prologue slot is never loaded; vanilla Ch1's
    #     scenes are stripped): 0x664 "Renais Castle" location card, 0x90D prologue
    #     opening, 0x914 boss mid-fight line, 0x918 prologue ending. The three quote
    #     msgs (0x936/0x917/0xC25) are the ids the gDefeatTalkList entries in step 5
    #     already reference. Staging mirrors vanilla: protectors left, lead right in
    #     the ending (0x918's Seth/Eirika layout); boss MidRight (0x910's O'Neill).
    fid = {s: _fid_tag(s) for s in (hlin_slot, scram_slot, sephek_slot)}
    # On-map bubbles want vanilla 0x911's Mid pair: with Hlin on plain [OpenLeft],
    # Sephek's MidRight turns AFTER a left turn rendered as empty bubbles (2026-06-10
    # scenes capture); [OpenMidLeft] <-> [OpenMidRight] round-trips are the shape
    # vanilla actually ships on-map.
    opening_staging = {'hlin': ('[OpenMidLeft]', fid[hlin_slot]),
                       'scramsax': ('[OpenFarLeft]', fid[scram_slot]),
                       'sephek': ('[OpenMidRight]', fid[sephek_slot])}
    ending_staging = {'scramsax': ('[OpenMidLeft]', fid[scram_slot]),
                      'hlin': ('[OpenMidRight]', fid[hlin_slot])}
    events = {e['trigger']: e for e in chap.get('events', [])}
    opening_script = events['chapter_start']['script']
    card = next(v for e in opening_script for k, v in e.items()
                if k == 'location_card')
    set_message_body(lines, 0x664, name_message_body(card))
    # The opening splits at Sephek's interrupt into TWO messages (0x90D briefing /
    # 0x90E confrontation), mirroring vanilla's own boss reveal (0x910 is its own
    # message, boss face loaded at message START). A right-side face lazy-loaded
    # MID-message gets empty/offscreen bubbles for its later multi-page turns
    # (2026-06-10 scenes capture) -- vanilla never ships that shape. The event
    # script deploys the enemies between the two, so Sephek's unit appears on the
    # map exactly when he finishes Hlin's sentence.
    i_reveal = next(i for i, e in enumerate(opening_script) if 'sephek' in e)
    set_message_body(lines, 0x90D, _script_to_message(
        opening_script[:i_reveal], opening_staging))
    set_message_body(lines, 0x90E, _script_to_message(
        opening_script[i_reveal:], opening_staging))
    set_message_body(lines, 0x914, _script_to_message(
        events['boss_battle']['script'], opening_staging))
    set_message_body(lines, 0x918, _script_to_message(
        events['chapter_end']['script'], ending_staging))
    set_message_body(lines, 0x936, battle_quote_body(
        'sephek', [by_id['sephek-kaltro']['death_quote']], opening_staging['sephek']))
    set_message_body(lines, 0x917, battle_quote_body(
        'hlin', [by_id['hlin-trollbane']['death_quote']], ending_staging['hlin']))
    # A defeat quote rides the 143px battle bubble like the two above; at the talk window's
    # 203px its first line ran 193px, off the bubble.
    set_message_body(lines, 0xC25, battle_quote_body(
        'scramsax', [by_id['scramsax']['defeat_quote']], ending_staging['scramsax']))

    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    # 4b. Give the guest slots a consistent character identity for their deployed class --
    #     just like patch_character_data does for the cast. Guests aren't in PORTRAIT_MAP, so
    #     we align defaultClass + baseLevel + affinity, write the personal base stats (each
    #     guest's `twin:` line, so Hlin fights as Eirika and Scramsax as Seth whatever their
    #     class; Sephek's are zeroed, a bare class base), and copy growths + weapon ranks from a
    #     class-matched vanilla donor so each guest levels like a real FE unit of its class and
    #     can wield its items.
    #     (Mirrors patch_character_data; keeps the cast and guests on equal footing.)
    _axe = ('PIRATE', 'WARRIOR', 'FIGHTER', 'BRIGAND', 'BERSERKER')
    _hlin_donor = 'CHARACTER_GARCIA' if any(c in hlin_class for c in _axe) else 'CHARACTER_GERIK'
    _scram_donor = 'CHARACTER_GARCIA' if any(c in scram_class for c in _axe) else 'CHARACTER_GERIK'
    # (slot, class, level, donor, female, line) -- female None means "leave attributes alone"
    # (the boss keeps CA_BOSS; _set_gender would clobber it). baseLevel comes from the same
    # YAML field the roster block does: these are two encodings of one number, and a literal
    # here would drift out of step with the roster the moment the chapter is rebalanced.
    # `line` is the personal layer, from guest_personal_line, which difficulty also reads.
    hlin, scram = by_id['hlin-trollbane'], by_id['scramsax']
    guest_patch = [(PROLOGUE_HLIN_SLOT, hlin_class, hlin['level'], _hlin_donor, True,
                    guest_personal_line(hlin, hlin_class)),
                   (PROLOGUE_SCRAMSAX_SLOT, scram_class, scram['level'], _scram_donor, False,
                    guest_personal_line(scram, scram_class)),
                   (PROLOGUE_SEPHEK_SLOT, 'CLASS_MYRMIDON', by_id['sephek-kaltro']['level'],
                    'CHARACTER_JOSHUA', None, {})]
    # The rewrite below is what disqualifies these slots from ENEMY_BASE_SLOT (a unit here does
    # NOT inherit the vanilla character's personal line). Keep the two statements of that in step.
    assert tuple(g[0] for g in guest_patch) == PROLOGUE_REWRITTEN_GUEST_SLOTS, \
        'guest_patch and PROLOGUE_REWRITTEN_GUEST_SLOTS disagree about which slots get rewritten'
    with open(CHARACTERS_C, encoding='utf-8') as f:
        chars = f.read()
    for slot, cls, level, donor, female, line in guest_patch:
        growths, ranks = donor_growths_and_ranks(chars, donor)  # donors are unpatched slots
        marker = '[CHARACTER_%s - 1]' % slot
        s, e = _find_brace_block(chars, marker, CHARACTERS_C)
        block = chars[s:e]
        block = _set_field(block, 'defaultClass', cls, CHARACTERS_C, marker)
        block = _set_field(block, 'affinity', 'UNIT_AFFIN_ANIMA', CHARACTERS_C, marker)
        block = _set_field(block, 'baseLevel', level, CHARACTERS_C, marker)
        if female is not None:
            block = _set_gender(block, female)
        for bf in ('baseHP', 'basePow', 'baseSkl', 'baseSpd', 'baseDef',
                   'baseRes', 'baseLck', 'baseCon'):
            block = _set_field(block, bf, line.get(bf, 0), CHARACTERS_C, marker)
        for gf, gv in growths.items():
            block = _set_field(block, gf, gv, CHARACTERS_C, marker)
        block, n = re.subn(r'(\.baseRanks\s*=\s*)\{.*?\}',
                           lambda m: m.group(1) + ranks, block, count=1, flags=re.DOTALL)
        if n == 0:
            sys.exit('ERROR: .baseRanks not found for %s' % marker)
        chars = chars[:s] + block + chars[e:]
    with open(CHARACTERS_C, 'w', encoding='utf-8') as f:
        f.write(chars)

    # 5. All three chapter outcomes ride gDefeatTalkList (vanilla's mechanism -- the flags
    #    on defeat quotes are what set the event flags the Misc AFEVs watch; CA_BOSS alone
    #    sets nothing):
    #    - Sephek: .flag = EVFLAG_DEFEAT_BOSS, exactly like every vanilla boss's entry
    #      (O'Neill/Breguet/...). Without it the DefeatBoss AFEV never fires -- O'Neill's
    #      own entry is keyed to CHAPTER_L_PROLOGUE, not our host slot (caught by the
    #      automated win playtest, 2026-06-09).
    #    - Hlin: .flag = EVFLAG_GAMEOVER (lord-death = game over, decided 2026-06-09;
    #      YAML NOTE 3); CauseGameOverIfLordDies (step 3) fires on it -- vanilla's
    #      Eirika/Duessel mechanism.
    #    - Scramsax: FLAG-LESS quote (vanilla Seth precedent): quote plays, battle
    #      continues, framed as a retreat -- he's alive for Ch1.
    #    msg bodies are written from the chapter YAML in step 4c; #42 generalizes the lord.
    # The prologue is hosted on chapter slot 1, hence CHAPTER_L_1.
    quotes = [
        defeat_quote_row('CHARACTER_%s' % sephek_slot, 'CHAPTER_L_1',
                         'Sephek -- boss kill sets the DefeatBoss flag', msg=0x936,
                         flag='EVFLAG_DEFEAT_BOSS'),
        defeat_quote_row('CHARACTER_%s' % hlin_slot, 'CHAPTER_L_1',
                         'Hlin -- lord-death = game over', msg=0x917, flag='EVFLAG_GAMEOVER'),
        defeat_quote_row('CHARACTER_%s' % scram_slot, 'CHAPTER_L_1',
                         'Scramsax -- retreat quote only, NO game over', msg=0xC25)]
    #    The entries must land at the HEAD of the list: GetDefeatTalkEntry (eventinfo.c)
    #    returns the FIRST match, and vanilla gives every playable slot a generic
    #    chapter=0xFF death quote further down -- NATASHA's/KYLE's would shadow our
    #    flagged entries (quote plays, flag never set, no game over; caught by the
    #    automated gameover playtest, 2026-06-09). Vanilla orders the table the same
    #    way: chapter-keyed boss entries first, generic quotes after. (And never append
    #    after the {.pid = -1} terminator: the scan stops there -- that one was a real,
    #    silent bug too.)
    # 5b. Sephek's mid-fight frost line (slot 4) = a first-engagement boss battle
    #     quote on gBattleTalkList -- FE8's native "mid-fight boss line" mechanism
    #     (vanilla wires O'Neill's 0x916 with this exact two-entry pattern: one for
    #     the player engaging the boss, one for the boss engaging the player; the
    #     EVFLAG_BATTLE_QUOTES flag makes it play exactly once). Same head-insertion
    #     rule as the defeat quotes: GetBattleTalkEntry returns the first match.
    #     battle_quote_pair() owns both rows and why there are two of them.
    _prepend_defeat_quote('\n'.join(quotes))
    _prepend_battle_quote(battle_quote_pair(
        'CHARACTER_%s' % sephek_slot, 'CHAPTER_L_1', 0x914,
        'Sephek mid-fight frost line (step 4c)'))

    # 6. Opening montage (#43): when MONTAGE=1, re-render the intro-monologue slides as our
    #    lore crawl + the world-map tour. The boot cut + New-Game redirect themselves (so the
    #    prologue loads through host chapter slot 1, dodging the prologue slot's special-cased
    #    HUD/terrain handling) are the single owner _configure_boot()'s job, called once from
    #    main() -- MONTAGE=1 there keeps the intro monologue for these slides to replace.
    if montage:
        print('opening montage (#43):')
        inject_opening_montage(campaign, verbose=verbose)
        inject_world_tour(campaign, verbose=verbose)

    # 7. Don't start in tutorial mode. New Game sets PLAY_FLAG_TUTORIAL (gamecontrol.c
    #    sub_8009C5C), which drives the vanilla guide/tutorial system; our beginning scene
    #    is a plain deploy with none of that setup, so clear the flag.
    with open(GAMECONTROL_C, encoding='utf-8') as f:
        gc = f.read()
    gc, n = re.subn(r'[ \t]*gPlaySt\.chapterStateBits \|= PLAY_FLAG_TUTORIAL;\n',
                    '', gc, count=1)
    if n == 0:
        sys.exit('ERROR: PLAY_FLAG_TUTORIAL set not found in %s' % GAMECONTROL_C)
    with open(GAMECONTROL_C, 'w', encoding='utf-8') as f:
        f.write(gc)

    if verbose:
        print('  prologue map (obj1=%d pal=%d cfg=%d layout=%d) hosted on chapter %d '
              '(Ch1 group); New Game redirects %d -> %d'
              % (obj_idx, pal_idx, cfg_idx, layout_idx, PROLOGUE_HOST_INDEX,
                 PROLOGUE_CHAPTER_INDEX, PROLOGUE_HOST_INDEX))
        print('  units: Hlin(%s)+Scramsax(%s) vs Sephek(%s)+2 guards'
              % (hlin_slot, scram_slot, sephek_slot))
