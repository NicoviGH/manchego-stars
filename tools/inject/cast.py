"""Who is who: the cast's class and portrait bindings and the unit loader.

`class_enum_for`, `PORTRAIT_MAP` and `GUEST_PORTRAIT_MAP` bind a campaign character to the vanilla
class, slot and face it borrows; the raw-pid tables do the same for bodies with no slot.
"""
import os
import re
import sys

from PIL import Image

from yaml_loader import yaml_load
from inject.chapter_ids import (
    CH01_BOSS_SLOT, CH02_BOSS_SLOT, CH02_MINIBOSS_SLOT, CH04_MOOSE_PID, CH05_BOSS_PID,
    CH05_CHAPTER_YAML, CH05_MOOSE_NAME_MSG, CH05_MOOSE_PID, CH06_BOAT_NAME_MSGS, CH06_BOAT_PIDS,
    CH06_MESSIE_PID,
    PROLOGUE_SEPHEK_SLOT)
from inject.class_ids import DEFAULT_CAMPAIGN, vanilla_class_enum, vanilla_class_enums
from inject.decomp import fe_item_enum, REPO
from inject.hosting import _load_chapter_yaml, recruit_chapter_number
from inject.text import display_name


# Palette index 0 of an FE8 bust is the transparent key. Our busts keep whatever colour their
# source put there (green, magenta, sage; the game never draws it) and mark index 0 transparent
# in the file (tools/test_bust_key.py). Named because _vendor_mug_to_bust has to WRITE a key:
# a community mug arrives keyed on whatever green its artist used, and ours is magenta.
PORTRAIT_TRANSPARENT_RGB = (255, 0, 255)



# The ENEMY-side counterpart of BASE_DONOR: our enemy id -> the vanilla CHARACTER_ slot it is
# actually deployed on. Nothing patches these slots (they are not in PORTRAIT_MAP), so the built
# ROM adds the slot's OWN personal line on top of the class base, exactly as FE8 does for its own
# bosses -- Halvar fights as a Brigand *plus* Bazba's HP+5/Def+2/..., because he IS Bazba's slot.
#
# It exists so the difficulty tool can measure what actually fights (#284). Reading these units
# off naked class base understated ch02's boss by 3x -- 1.2 rounds against a bar of 3.6 -- and
# opened a balance issue against content that was never wrong. The slot names are NOT repeated
# here: each entry points at the one constant the injector already builds the unit from, so the
# two cannot drift apart. A boss on a RAW pid (ch03's grell, ch05's Ravisin) has no entry -- its
# CharacterData gap is all zeros, so it is a genuine naked class base until a `personal:` line is
# authored in its chapter YAML *and* registered in RAW_PID_PERSONAL_SOURCES to reach the ROM.
#
# Riding a vanilla slot is NOT sufficient on its own -- the slot must also survive the build
# unpatched. The prologue's guests do not: inject_prologue REWRITES their personal bases (Hlin
# and Scramsax onto their twins' lines, Sephek to zero), so Sephek is genuinely naked despite
# deploying on O'Neill's slot, and belongs here no more than a raw pid does.
# PROLOGUE_REWRITTEN_GUEST_SLOTS is the authoritative list of that exclusion and the two are
# asserted disjoint.
ENEMY_BASE_SLOT = {
    'goblin-chief':  'CHARACTER_%s' % CH01_BOSS_SLOT,
    'raider-captain': 'CHARACTER_%s' % CH02_BOSS_SLOT,
    'raider-bruiser': 'CHARACTER_%s' % CH02_MINIBOSS_SLOT,
    # ch06's merfolk elder RIDES NOVALA (2026-08-29). Her chapter's parity_reference IS
    # FE8 Ch6, so the boss the bar measures against and the slot she deploys on are the
    # same character -- she inherits his real line (HP 28 / Mag 10 / Def 5) instead of
    # needing an invented `personal:` block and a RAW_PID_PERSONAL_SOURCES route. Both
    # sides of the comparison then read the same article.
    'nerra': 'CHARACTER_NOVALA',
    # ch07's Speaker rides MURRAY: FE8 Ch7 is his chapter's parity_reference, and Murray is the
    # boss it fields on the same door (ADR 0332's face slot is Murray too). He fights as a
    # Fighter, not Murray's Cavalier, so his YAML line REPLACES Murray's on the slot
    # (raw_pids.SLOT_PERSONAL_SOURCES, ADR 0343).
    'dorbulgruf': 'CHARACTER_MURRAY',
}


# The same question asked about ATTRIBUTES rather than stats: our enemy id -> the vanilla
# CHARACTER_ slot whose `.attributes` the deployed unit carries. It is a superset of
# ENEMY_BASE_SLOT, because zeroing a slot's personal STAT line (inject_prologue's guests) does
# not clear its CA_BOSS bit -- Sephek's DefeatBoss fires precisely because he keeps ONEILL's.
# Read this, never ENEMY_BASE_SLOT, for "does the engine treat this body as a boss": the exp
# economy pays a 40-point kill bonus off CA_BOSS (exp_curve.py), and the stat table answers a
# different question.
ENEMY_CHARACTER_SLOT = dict(
    ENEMY_BASE_SLOT, **{'sephek-kaltro': 'CHARACTER_%s' % PROLOGUE_SEPHEK_SLOT})


def _slot_table(key, campaign=DEFAULT_CAMPAIGN):
    """One of campaign.yaml's slot tables, in the order it is written (the injector walks it in
    that order, so the order is part of the build)."""
    with open(os.path.join(REPO, 'campaigns', campaign, 'campaign.yaml'), encoding='utf-8') as f:
        return dict(yaml_load(f)[key])


# our cast bust -> the vanilla portrait slot whose graphic files we overwrite; it is also the
# general character-slot key (names, class/stats/growths/gender, death quotes, map sprites).
# The table itself, with why each slot was chosen, is campaign.yaml `cast_slots` (#486).
PORTRAIT_MAP = _slot_table('cast_slots')
# guests and bosses with a bust -> the vanilla portrait slot their face overwrites;
# campaign.yaml `guest_slots`.
GUEST_PORTRAIT_MAP = _slot_table('guest_slots')


def _bust_dir(campaign):
    return os.path.join(REPO, 'campaigns', campaign, 'portraits')


def _name_only_donors():
    """Guest units whose donor slot lends a NAME and nothing else -- never dressed.

    A raw-pid row with `portrait_id` None has no bust by design (its donor has no portraitId to
    give). Dressing its slot anyway would be driven purely by a PNG happening to sit in
    portraits/, which is how the moose would have picked up the full-body Wyrdeer sheet that was
    explicitly retired (Nicolas, 2026-08-15) -- an asset on disk is not a decision to ship it.
    """
    return {unit_id for _pid, (unit_id, _slot, portrait_id, _name)
            in RAW_PID_PORTRAITS.items() if portrait_id is None}


def dressed_guest_slots(campaign):
    """Portrait slots of guests whose bust PNG exists (and so get dressed)."""
    name_only = _name_only_donors()
    return [slot for unit, slot in GUEST_PORTRAIT_MAP.items()
            if unit not in name_only
            and os.path.isfile(os.path.join(_bust_dir(campaign), unit + '.png'))]


# Each cast member wears a vanilla character's slot (PORTRAIT_MAP). We overwrite that
# vanilla character's NAME message in texts/texts.txt with our unit's display name, so
# the recompressed gMsgTable carries it. The vanilla name's message index is the
# slot character's `.nameTextId` -- read it from the decomp, never hardcode (the data
# is the source of truth). Names live in YAML; the C/text we emit is just data.

def load_unit(campaign, unit_id):
    """Load a cast member's YAML from pcs/ or npcs/."""
    base = os.path.join(REPO, 'campaigns', campaign)
    for sub in ('pcs', 'npcs'):
        path = os.path.join(base, sub, unit_id + '.yaml')
        if os.path.isfile(path):
            with open(path, encoding='utf-8') as f:
                return yaml_load(f)
    sys.exit('ERROR: no YAML for unit %r under %s/{pcs,npcs}' % (unit_id, base))


def class_enum_for(unit):
    """A cast member's CLASS_ enum. `fe_stats.class` is a vanilla class TOKEN ('armor-knight'),
    the one vocabulary enemies use too (docs/decisions.md Class Mapping: stock vanilla classes),
    resolved the same way and refused if vanilla has no such class."""
    raw = unit.get('fe_stats', {}).get('class')
    if not raw:
        return None
    enum = vanilla_class_enum(raw)
    if enum not in vanilla_class_enums():
        sys.exit('ERROR: unit %r class %r is not a vanilla class token' % (unit.get('id'), raw))
    return enum


def deploy_class_for(unit):
    """The class enum a unit is DEPLOYED as (its `defaultClass` + UnitDef `classIndex`).

    Every cast member deploys as their plain vanilla class. Custom battle anims no longer
    need a clone class: they ride the per-character `_u25` table (#65 M-B, see
    inject_battle_anims + the _patch_banim_character_unique engine hook)."""
    return class_enum_for(unit)


# First in-engine confirmation that names + portraits + classes + stats land together.
# We keep vanilla Ch1's MAP but strip its scripting to a bare sandbox: the original
# beginning scene choreographs specific vanilla units (scripted Breguet fight, forced
# moves, MoveUnitS2ToLeader) and was deleting our cast mid-cutscene -> instant lord-
# death game over. Instead we:
#   * rewrite the player roster (UnitDef_Event_Ch1Ally) to our classed cast,
#   * replace the beginning scene with a minimal "load the cast, hand over control",
#   * empty every per-chapter event list (turn/character/location/misc/tutorial) so
#     nothing references removed units or fires a win/lose condition,
#   * cut the boot attract reel + redirect prologue->Ch1 so a fresh boot lands on the
#     title and New Game drops straight onto the map (dev loop).
# Result: New Game -> Ch1 map with the 8 cast, no cutscene, no game over -- a
# combat-ready sandbox (the vanilla foes stay, reskinned; no objective -- reset when
# done; battle-anim capture fires on them). Each cast unit rides its
# PORTRAIT_MAP slot's CHARACTER_ id, so its injected name/portrait/class/stats show.
# redaCount=0 places a unit statically at xPosition/yPosition (eventscr.c sub_800F8A8).
# All edits are restorable build artifacts (PATCHED_DECOMP_FILES). Authored chapters
# (real maps/events/objectives from YAML) supersede this whole step.

def unit_items(campaign, unit_id):
    """The ITEM_ enums a cast member fields, in slot order: its unit file's `inventory:`.

    One home for the kit (#486): every roster that LOADs the unit -- its join, a boot party
    seed, a bench -- reads it here. Promotion-gated (`unlock:`) and story-only entries are
    design notes, not items the ROM fields, so they are skipped."""
    unit = load_unit(campaign, unit_id)
    items = [fe_item_enum(i) for i in unit.get('inventory') or ()
             if not i.get('unlock') and not i.get('story_only')]
    if not items:
        sys.exit('ERROR: %s has no fieldable inventory: (its unit file is the kit\'s home)'
                 % unit_id)
    return items


def classed_cast(campaign):
    """Cast (PORTRAIT_MAP order) that carry an FE class; name-only units are skipped.

    The 4th tuple slot is a legacy None -- SMS ids are NOT assigned here. They used to be
    (CUSTOM_SMS_BASE + position, for every classed member whether or not its sprite was
    authored), which meant a classed member without art still burned an id while emitting
    no wait row, shifting every later row off the id naming it. Ids are now claimed by the
    pass that writes the matching row (claim_sms_id), so the two cannot drift (#227)."""
    out = []
    for unit_id, slot in PORTRAIT_MAP.items():
        unit = load_unit(campaign, unit_id)
        unit.setdefault('id', unit_id)
        if class_enum_for(unit) is None:
            continue
        out.append((unit_id, slot, class_enum_for(unit), None))
    return out


def _vendor_mug_to_bust(path, recolor=None):
    """A 128x112 FE-Repo mug sheet -> the 96x80 indexed bust portrait_tool.generate() wants.

    The community sheets are one main frame at top-left plus speaking/blink frames; we take the
    main frame only (our busts are static -- decisions.md, Art & Audio). The background key is
    read from the CORNER PIXEL rather than hardcoded, because it is not one colour across the
    repo: Glaceo's set keys on (123,162,115) and Eden/L95's on (160,200,152), and hardcoding
    either silently leaves a green box behind the other artist's faces.

    `recolor` maps source RGB -> replacement, applied before indexing, for pulling two mugs that
    share a body apart (see CH05_VISIT_FACES).

    FE8 portraits are 16 colours INCLUDING the transparent key, so index 0 is forced to magenta
    and the rest follow. A mug that does not fit is a hard error, not a silent quantize: dithering
    a pixel-art bust to fit would wreck the flats it is drawn in.
    """
    im = Image.open(path).convert('RGB').crop((0, 0, 96, 80))
    key = im.getpixel((0, 0))
    px = im.load()
    for y in range(80):
        for x in range(96):
            colour = px[x, y]
            if colour == key:
                px[x, y] = PORTRAIT_TRANSPARENT_RGB
            elif recolor and colour in recolor:
                px[x, y] = recolor[colour]
    colours = [c for _, c in im.getcolors(1 << 16)]
    if len(colours) > 16:
        sys.exit('ERROR: %s needs %d colours; an FE8 portrait holds 16 including the '
                 'transparent key.' % (os.path.basename(path), len(colours)))
    palette = ([PORTRAIT_TRANSPARENT_RGB]
               + [c for c in colours if c != PORTRAIT_TRANSPARENT_RGB])
    bust = Image.new('P', (96, 80))
    bust.putpalette([v for c in palette for v in c] + [0] * (768 - 3 * len(palette)))
    index = {c: i for i, c in enumerate(palette)}
    bust.putdata([index[px[x, y]] for y in range(80) for x in range(96)])
    return bust


def _chapter_unit(campaign, chapter_yaml, unit_id):
    """A named unit's block from a chapter YAML, from whichever roster holds it."""
    chapter = _load_chapter_yaml(campaign, chapter_yaml)
    for roster in ('enemy_units', 'neutral_units', 'ally_units'):
        for unit in chapter.get(roster) or []:
            if unit.get('id') == unit_id:
                return unit
    sys.exit('ERROR: %s declares no unit %r' % (chapter_yaml, unit_id))


def _classed_cast(campaign, available_at=None):
    """The classed cast in PORTRAIT_MAP order: (unit_id, slot, class_enum,
    deploy_class_enum, level) per unit, plus a parallel display-name list.
    Units with no class mapping (non-combat NPCs) are skipped.

    available_at=N (a chapter_number) returns only the cast ON THE FIELD at chapter N =
    the founding party (no `recruit:` block) + every recruit whose recruit chapter is
    BEFORE N (they joined in a prior chapter, so they ride the prep/deploy roster). A unit
    recruited IN chapter N is NOT here -- it enters mid-chapter via inject_recruits (green
    placement + a CUSA join), not the prep roster. available_at=None returns the full cast
    (recruits included), which still drives name/class/stat patching, map sprites and death
    quotes regardless of chapter."""
    cast, names = [], []
    for unit_id, slot in PORTRAIT_MAP.items():
        unit = load_unit(campaign, unit_id)
        unit.setdefault('id', unit_id)
        class_enum = class_enum_for(unit)
        if class_enum is None:
            continue
        if available_at is not None:
            rc = recruit_chapter_number(campaign, unit)
            if rc is not None and rc >= available_at:
                continue   # not yet recruited (or joins THIS chapter mid-map)
        cast.append((unit_id, slot, class_enum, deploy_class_for(unit),
                     int(unit.get('fe_stats', {}).get('level', 1))))
        names.append(display_name(unit))
    if not cast:
        sys.exit('ERROR: no classed cast -- every PORTRAIT_MAP unit is missing a '
                 'class mapping (check the pcs/*.yaml fe_stats blocks)')
    return cast, names


def char_symbol(slot):
    """The CHARACTER_ enum for a vanilla character slot name (the unit's on-map pid/FID
    symbol). A cast PC rides its PORTRAIT_MAP slot, so its map identity is CHARACTER_<slot>."""
    return 'CHARACTER_%s' % slot.upper()
# Scripted units carrying custom map art that no CAST pass can see: they stand on a map wearing
# our own sprite without being cast members, so `classed_cast` never looks at them.
# Row = (campaign asset id, the raw charIds that wear it, donor base for the wait-row GEOMETRY).
#
# THE CHARIDS ARE A TUPLE, AND THAT IS THE FIX FOR A REAL BUG (Nicolas spotted it 2026-08-14).
# One asset can be worn by SEVERAL pids, because a pid is per-chapter: the white moose is ch04's
# green scripted neutral at 0xce AND ch05's red miniboss at 0xb9. The registry held 0xce alone,
# so ch05's moose fell through `GetUnitSMSId` to CLASS_GWYLLGI's stock hound on the enemy palette
# -- a red dog standing in for the chapter's cornered elk, with the Wyrdeer sheets committed and
# ch05's own YAML claiming they had shipped. Exactly the failure `_inject_scripted_neutral_sprites`
# was written to end, one chapter over, and invisible for the same reason: nothing tried and
# failed, nothing tried at all.
#
# The sheets and the SMS slot are claimed ONCE per asset; only the two override tables gain a row
# per pid. Reading the tables out of the POST-INJECTION tree is what proves it -- HEAD has neither.
SCRIPTED_NEUTRAL_SPRITES = (
    ('white-moose', (CH04_MOOSE_PID, CH05_MOOSE_PID), 'Gwyllgi'),
    # Ravisin (#25). Not a neutral -- she is ch05's BOSS -- but she is here for the reason
    # this table exists: a raw pid wearing our own art, which `classed_cast` never sees. Her
    # bust, name and stats are already bound the same explicit way off the ch05 YAML.
    # The CAST palette is right for her on the table's own test: she never changes faction
    # (hostile from spawn, never recruited, never converted -- her death ends the chapter),
    # so nothing is lost by leaving the faction ramp, and it is what lets her map sprite hold
    # the exact black robe / near-white skin / auburn hair her battle anim was hand-edited to.
    # The donor is only ever read for FRAME SIZE (16x16). The wait row's first field is
    # `pattern`, which the decomp calls unused and this injector writes as 0 -- and it is NOT
    # a frame count: Eirika Lord carries 0, the Druid 2, the Bonewalker 3, and all three
    # sheets are 16x48. Frame count comes from the sheet HEIGHT, and the engine reads exactly
    # three (ApplyUnitSpriteImage16x16 loops i < 3), which map_sprite_tool now enforces.
    ('ravisin', (CH05_BOSS_PID,), 'Druid'),
    # Messie (#26): ch06's cutscene actor, the whole plesiosaur in one 32x32 cell. The cast
    # palette for the moose's reason -- he never changes faction. Gwyllgi is the 32x32 GEOMETRY
    # donor (wait-row size, glide MU dimensions), so the scene must load him as CLASS_GWYLLGI.
    # The top-hat sheet (messie-mayor.png) is ch07's and is wired there.
    ('messie', (CH06_MESSIE_PID,), 'Gwyllgi'),
)
# Raw CharacterData identity binding. Riev contributes collision-free name/portrait slots:
# MSG_246 is retitled Ravisin and portrait id 0x48 is dressed from ravisin.png.
RAW_PID_PORTRAITS = {
    CH05_BOSS_PID: ('ravisin', GUEST_PORTRAIT_MAP['ravisin'], 0x48, 'Ravisin'),
    # The moose spends NO donor: its name is an APPENDED message id we own, and its portrait id
    # is None (no bust). Same rule the kobolds settled for classes in #90 -- append your own
    # rather than burn a scarce vanilla slot, so Morva stays free for the Chardalyn Dragon.
    CH05_MOOSE_PID: ('white-moose', CH05_MOOSE_NAME_MSG, None, 'White Moose'),
    # ch06's two marooned boats, on the same name-only shape as the moose: an appended message
    # id of our own and no portraitId, because a fishing boat has no bust and never speaks. The
    # `fe_name` they are named for is the chapter YAML's ("Fishing Boat", 12 chars against the
    # buffer's 12); without a row here both hulls read "Monster" on the unit window, on a map
    # whose whole point is that the monster is not the thing you are looking at.
    CH06_BOAT_PIDS['boat-east']: ('boat-east', CH06_BOAT_NAME_MSGS['boat-east'], None,
                                  'Fishing Boat'),
    CH06_BOAT_PIDS['boat-west']: ('boat-west', CH06_BOAT_NAME_MSGS['boat-west'], None,
                                  'Fishing Boat'),
    # Messie rides Syrene for both name and face, as Ravisin rides Riev: his no-hat bust is
    # dressed onto Syrene's slot (GUEST_PORTRAIT_MAP), so his unit points at that portraitId.
    CH06_MESSIE_PID: ('messie', GUEST_PORTRAIT_MAP['messie'], 0x2B, 'Messie'),
}


RAW_PID_BATTLE_ANIMS = {
    'white-moose': (CH05_CHAPTER_YAML, CH05_MOOSE_PID),
    'ravisin': (CH05_CHAPTER_YAML, CH05_BOSS_PID),
}
