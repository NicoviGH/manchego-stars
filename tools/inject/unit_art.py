"""What a unit LOOKS like in the game -- its bust and its map sprite -- answered once (#491).

Until #491 the answer lived in thirteen places. A bust came from `cast_slots`, `guest_slots`,
the ch02 chwinga recolour, the ch05 reliquary mugs or the Arena attendant config; a map sprite
from the cast pass, the prologue-guest list, the scripted-neutral table, the ch02 chwinga special
case or `enemy_class_reskins` -- each pass choosing its own members and its own palette rule. No
function said "this is what unit X looks like in chapter N", so every reader that was not the
build rebuilt the answer and missed a path: the wiki drew Ravisin and the white moose in their
stock class sprites, and the build itself once shipped the moose as a red hound.

This module is the registry. The injector passes keep their EMISSION (each writes a different
ROM table, and the order they claim SMS ids in is part of the build), but they take their
members from here; the wiki asks the same questions per unit and draws the answer through the
same remap. The tables it reads stay where they are defined -- this is their one interpreter.

A map sprite's palette is one of three rules, which is the whole of what the passes disagreed on:
  'cast'    the sheet is drawn in the bespoke cast bank (cast_palette.png), whatever the faction
            -- cast members, and scripted neutrals/bosses who never change faction;
  'faction' the sheet is already in a vanilla class's standard role layout, so the faction ramp
            tints it -- the prologue guests;
  'remap'   the sheet is remapped onto its donor class's role layout at build time, then the
            faction ramp tints it -- enemy class reskins, the ch02 chwinga, faction-tinted cast.
"""
import collections
import functools
import os
import tempfile

from PIL import Image

import map_sprite_tool
import portrait_tool
from inject.arena import _vendor_mug_to_arena_bust, arena_presentation_config
from inject.cast import (_bust_dir, _vendor_mug_to_bust, classed_cast, dressed_guest_slots,
                         GUEST_PORTRAIT_MAP, load_unit, PORTRAIT_MAP, SCRIPTED_NEUTRAL_SPRITES)
from inject.chapter_ids import (CH02_CHWINGA, CH02_CHWINGA_GLOW_RECOLOR,
                                CH02_CHWINGA_PORTRAIT_SLOT, CH02_CHWINGA_SPRITE_SRC,
                                CH05_VISIT_FACES, PROLOGUE_GUEST_SPRITES)
from inject.decomp import REPO
from inject.paths import PORTRAIT_DIR

# Cast who change faction on the map (Trex: green until recruited), so they cannot wear the
# fixed cast bank -- their sheet is remapped onto the donor's role layout and tinted instead.
FACTION_TINTED_CAST = frozenset({'trex'})

Sprite = collections.namedtuple('Sprite', 'uid kind cls wearers sheet walk donor frame palette')
Sprite.__doc__ = """One map-sprite asset as the game wears it.
    uid      the art's id (its map_sprites/<uid>.png stem)
    kind     'cast' | 'guest' | 'neutral' | 'chwinga' | 'reskin' | 'class'
    cls      the CLASS_ enum the wearer deploys as (None where the pass keys on charIds)
    wearers  CHARACTER_ slot names or raw charIds that wear it (reskins: the class slot)
    sheet    the idle sheet on disk (a vanilla wait sheet for kind 'class')
    walk     a committed <uid>_mu.png, or None (the build synthesizes a glide)
    donor    the vanilla class NAME whose wait geometry (and role layout, for 'remap') it uses
    frame    an explicit (w, h) idle frame, or None to take the donor's
    palette  'cast' | 'faction' | 'remap' (module docstring)"""

Bust = collections.namedtuple('Bust', 'uid kind slot image')
Bust.__doc__ = """One bust the build dresses: `image()` is the 96x80 indexed bust (or the 48x48
    counter portrait for the Arena), `slot` the vanilla portrait slot it overwrites."""


def _asset_dir(campaign):
    return os.path.join(REPO, 'campaigns', campaign, 'map_sprites')


def _walk(campaign, uid):
    path = os.path.join(_asset_dir(campaign), uid + '_mu.png')
    return path if os.path.isfile(path) else None


def _unit_donor(campaign, uid):
    try:
        return load_unit(campaign, uid)['art']['map_sprite']['base']
    except (KeyError, TypeError):
        raise SystemExit('ERROR: %s has map_sprites/%s.png but no art.map_sprite.base in its '
                         'YAML (needed to read the SMS size from the decomp)' % (uid, uid))


# ── map sprites ────────────────────────────────────────────────────────────────

def cast_sprites(campaign):
    """Cast members with an idle sheet, in PORTRAIT_MAP order (the order their SMS ids are
    claimed in)."""
    out = []
    for uid, slot, cls, _ in classed_cast(campaign):
        sheet = os.path.join(_asset_dir(campaign), uid + '.png')
        if os.path.isfile(sheet):
            out.append(Sprite(uid, 'cast', cls, (slot,), sheet, _walk(campaign, uid),
                              _unit_donor(campaign, uid), None,
                              'remap' if uid in FACTION_TINTED_CAST else 'cast'))
    return out


def guest_sprites(campaign):
    """Cold-open guests: standard player palette, base named in PROLOGUE_GUEST_SPRITES (they
    have no pcs/npcs YAML)."""
    out = []
    for uid, slot, cls, base in PROLOGUE_GUEST_SPRITES:
        sheet = os.path.join(_asset_dir(campaign), uid + '.png')
        if os.path.isfile(sheet):
            out.append(Sprite(uid, 'guest', cls, (slot,), sheet, _walk(campaign, uid), base,
                              None, 'faction'))
    return out


def neutral_sprites(campaign):
    """Raw-pid units wearing our art on the cast bank (the white moose, Ravisin, Messie)."""
    out = []
    for uid, char_ids, donor in SCRIPTED_NEUTRAL_SPRITES:
        sheet = os.path.join(_asset_dir(campaign), uid + '.png')
        if os.path.isfile(sheet):
            out.append(Sprite(uid, 'neutral', None, tuple(char_ids), sheet,
                              _walk(campaign, uid), donor, None, 'cast'))
    return out


def chwinga_sprite(campaign):
    """ch02's green chwinga: Sclorbo's sheet, remapped and tinted green, on three NPC slots."""
    sheet = os.path.join(_asset_dir(campaign), CH02_CHWINGA_SPRITE_SRC + '.png')
    if not os.path.isfile(sheet):
        return None
    return Sprite(CH02_CHWINGA_SPRITE_SRC, 'chwinga', None,
                  tuple(slot for _, slot in CH02_CHWINGA), sheet, None,
                  _unit_donor(campaign, CH02_CHWINGA_SPRITE_SRC), None, 'remap')


def reskin_sprites(campaign):
    """{(chapter, token): Sprite} for every enemy class reskin that dresses a chapter."""
    from inject.reskins import enemy_class_reskins, _class_field, _wait_symbol_at
    out = {}
    for rk in enemy_class_reskins(campaign):
        _sym, donor = _wait_symbol_at(_class_field(rk['base'], 'SMSId'))
        frame = (tuple(int(v) for v in str(rk['frame']).lower().split('x'))
                 if rk.get('frame') else None)
        sprite = Sprite(rk['sprite'], 'reskin', rk['slot'], (rk['slot'],),
                        os.path.join(_asset_dir(campaign), rk['sprite'] + '.png'),
                        os.path.join(_asset_dir(campaign), rk['sprite'] + '_mu.png'),
                        donor, frame, 'remap')
        for chapter, tokens in (rk.get('dresses') or {}).items():
            for token in tokens:
                out[(chapter, token)] = sprite
    return out


@functools.lru_cache(maxsize=None)
def _by_uid(campaign):
    out = {}
    for s in cast_sprites(campaign) + guest_sprites(campaign) + neutral_sprites(campaign):
        out[s.uid] = s
    chwinga = chwinga_sprite(campaign)
    if chwinga:
        for uid, _slot in CH02_CHWINGA:
            out[uid] = chwinga
    return out


def unit_sprite(campaign, chapter, uid=None, token=None):
    """The Sprite a unit wears in `chapter`: its own art by id, else its class's reskin there,
    else None (the stock class sprite, which `class_sprite` draws)."""
    own = _by_uid(campaign).get(uid)
    if own:
        return own
    if token:
        return _reskins(campaign).get((chapter, token))
    return None


@functools.lru_cache(maxsize=None)
def _reskins(campaign):
    return reskin_sprites(campaign)


# ── busts ──────────────────────────────────────────────────────────────────────

def _file_bust(path):
    return lambda: Image.open(path)


def chwinga_bust(campaign):
    """Sclorbo's bust with the blue glow ramp shifted to spirit-green (the map sprite's swap)."""
    im = Image.open(os.path.join(_bust_dir(campaign), CH02_CHWINGA_SPRITE_SRC + '.png')).convert('P')
    pal = list(im.getpalette()[:48])
    for i in range(16):
        rgb = tuple(pal[i * 3:i * 3 + 3])
        if rgb in CH02_CHWINGA_GLOW_RECOLOR:
            pal[i * 3:i * 3 + 3] = list(CH02_CHWINGA_GLOW_RECOLOR[rgb])
    out = im.copy()
    out.putpalette(pal)
    return out


def busts(campaign, kinds=None):
    """Every bust the build dresses, by kind: 'cast', 'guest', 'chwinga', 'visit', 'arena'.
    Conditioned on the asset existing, exactly as each pass was: a slot we do not dress keeps
    its vanilla face."""
    bust_dir = _bust_dir(campaign)
    out = []
    for uid, slot in PORTRAIT_MAP.items():
        out.append(Bust(uid, 'cast', slot, _file_bust(os.path.join(bust_dir, uid + '.png'))))
    dressed = set(dressed_guest_slots(campaign))
    for uid, slot in GUEST_PORTRAIT_MAP.items():
        if slot in dressed:
            out.append(Bust(uid, 'guest', slot, _file_bust(os.path.join(bust_dir, uid + '.png'))))
    if os.path.isfile(os.path.join(bust_dir, CH02_CHWINGA_SPRITE_SRC + '.png')):
        for uid, npc_slot in CH02_CHWINGA:
            out.append(Bust(uid, 'chwinga', CH02_CHWINGA_PORTRAIT_SLOT[npc_slot],
                            lambda: chwinga_bust(campaign)))
    vendor = os.path.join(bust_dir, 'vendor')
    for vid, (mug, slot, recolor) in sorted(CH05_VISIT_FACES.items()):
        path = os.path.join(vendor, mug)
        if os.path.isfile(path):
            out.append(Bust(vid, 'visit', slot,
                            lambda path=path, recolor=recolor: _vendor_mug_to_bust(path, recolor)))
    for host, override in sorted(arena_presentation_config(campaign)['chapters'].items()):
        out.append(Bust('arena-%s' % host, 'arena', override['face_slot'],
                        lambda p=override['portrait_path']: _vendor_mug_to_arena_bust(p)))
    return [b for b in out if kinds is None or b.kind in kinds]


def unit_bust(campaign, uid):
    """The bust a unit shows, as an image, or None: what the build dresses for it."""
    for b in busts(campaign, kinds=('cast', 'guest', 'chwinga')):
        if b.uid == uid:
            path = os.path.join(_bust_dir(campaign), uid + '.png')
            if b.kind != 'chwinga' and not os.path.isfile(path):
                return None
            return b.image()
    return None


def dress_slot(slot, bust):
    """Overwrite one vanilla portrait slot with a bust: the four files every bust pass writes.
    Custom busts are static (no mouth flap, no blink) -- see portrait_tool.generate."""
    tileset, mouth, chibi, pal_bytes = portrait_tool.generate(bust, static_portrait=True)
    base = os.path.join(PORTRAIT_DIR, 'portrait_' + slot)
    tileset.save(base + '_tileset.png')
    mouth.save(base + '_mouth.png')
    chibi.save(base + '_chibi.png')
    with open(base + '_palette.agbpal', 'wb') as f:
        f.write(pal_bytes)
    return chibi


# ── drawing a sprite the way the engine does (for readers that are not the build) ─────────────

VANILLA_WAIT_DIR = os.path.join(REPO, 'fireemblem8u', 'graphics', 'unit_icon', 'wait')
FACTION_PALETTE_DIR = os.path.join(REPO, 'fireemblem8u', 'graphics', 'unit_icon', 'palette')
FACTIONS = {'player': 'player', 'enemy': 'enemy', 'green': 'npc'}


def _agbpal(path):
    raw = open(path, 'rb').read()[:32]
    out = []
    for i in range(0, 32, 2):
        c = raw[i] | raw[i + 1] << 8
        out += [(c & 31) * 255 // 31, (c >> 5 & 31) * 255 // 31, (c >> 10 & 31) * 255 // 31]
    return out


@functools.lru_cache(maxsize=None)
def _faction_palette(faction):
    return _agbpal(os.path.join(FACTION_PALETTE_DIR, 'unit_icon_pal_%s.agbpal'
                                % FACTIONS[faction]))


@functools.lru_cache(maxsize=None)
def _cast_palette(campaign):
    return (Image.open(os.path.join(_asset_dir(campaign), 'cast_palette.png')).getpalette()
            or [])[:48]


def idle_frame(campaign, sprite, faction):
    """The first idle frame of `sprite` as the game draws it for a unit of `faction`
    ('player' | 'enemy' | 'green'): the 'cast' bank whatever the faction, else the sheet's
    role indices through the faction ramp, remapped onto the donor's layout first for 'remap'
    -- the same remap_sms_palette call the build makes. Index 0 is transparent."""
    sheet = sprite.sheet
    if sprite.palette == 'remap':
        donor_png = os.path.join(VANILLA_WAIT_DIR, 'unit_icon_wait_%s_sheet.png' % sprite.donor)
        out = os.path.join(tempfile.mkdtemp(prefix='manchego_art_'), 'remapped.png')
        map_sprite_tool.remap_sms_palette(sheet, donor_png, out)
        sheet = out
    im = Image.open(sheet)
    w, h = sprite.frame or map_sprite_tool.donor_sms_geometry(sprite.donor)[1:]
    frame = im.crop((0, 0, min(w, im.width), h))
    pal = _cast_palette(campaign) if sprite.palette == 'cast' else _faction_palette(faction)
    frame.putpalette(pal + (frame.getpalette() or [])[len(pal):])
    frame.info['transparency'] = 0
    return frame


def class_sprite(class_enum, faction):
    """A vanilla class's stock idle frame, through its SMSId's wait row (vanilla decomp at HEAD,
    so it needs no build), or None for a class with no row."""
    import re
    from inject.decomp import vanilla_decomp_text
    block = re.search(r'\[%s - 1\]\s*=\s*\{(.*?)\n\s*\},' % re.escape(class_enum),
                      vanilla_decomp_text('src/data_classes.c'), re.S)
    sms = re.search(r'\.SMSId\s*=\s*(0x[0-9a-fA-F]+|\d+)', block.group(1)) if block else None
    if not sms:
        return None
    row = re.search(r'unit_icon_wait_(\w+)_sheet\}\s*,\s*//\s*%d\s*$' % int(sms.group(1), 0),
                    vanilla_decomp_text('src/unit_icon_wait_data.c'), re.M)
    if not row:
        return None
    name = row.group(1)
    return idle_frame(None, Sprite(name, 'class', class_enum, (), os.path.join(
        VANILLA_WAIT_DIR, 'unit_icon_wait_%s_sheet.png' % name), None, name, None, 'faction'),
        faction)
