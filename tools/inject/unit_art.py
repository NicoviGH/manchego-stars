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
import colorsys
import functools
import os
import re
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


def reskin_sprite(campaign, rk):
    """The Sprite one `enemy_class_reskins` entry dresses its class slot with. The donor is the
    BASE class's VANILLA wait sheet: the sheet is remapped onto that role layout so the enemy
    faction ramp colours it, and a vanilla read needs no build tree."""
    donor = vanilla_wait_donor(rk['base'])
    if donor is None:
        raise SystemExit('ERROR: enemy_class_reskins %s: base %s has no vanilla wait row'
                         % (rk['id'], rk['base']))
    frame = (tuple(int(v) for v in str(rk['frame']).lower().split('x'))
             if rk.get('frame') else None)
    return Sprite(rk['sprite'], 'reskin', rk['slot'], (rk['slot'],),
                  os.path.join(_asset_dir(campaign), rk['sprite'] + '.png'),
                  _walk(campaign, rk['sprite']), donor, frame, 'remap')


def reskin_sprites(campaign):
    """{(chapter, token): Sprite} for every enemy class reskin that dresses a chapter."""
    from inject.reskins import enemy_class_reskins
    out = {}
    for rk in enemy_class_reskins(campaign):
        sprite = reskin_sprite(campaign, rk)
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


def _hls(rgb):
    return colorsys.rgb_to_hls(*(c / 255 for c in rgb))


def _glow_band(rgb):
    """The chwinga's glow: Sclorbo's cyan ramp (hue 175-205, saturated), not his greys/robe."""
    h, _l, s = _hls(rgb)
    return 175 <= h * 360 <= 205 and s >= 0.35


def _interp(points, x):
    points = sorted(points)
    if x <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return points[-1][1]


def glow_to_green(rgb, pairs=None):
    """One glow colour -> spirit-green, by the transform the authored pairs define
    (CH02_CHWINGA_GLOW_RECOLOR): the target hue and saturation, interpolated by lightness, and
    the authored lightness shift. Exact on the authored sources, and it extends to any shade a
    re-render adds -- RGB keys did not: #488's matte re-render moved every glow colour, matched
    none of them, and the chwinga shipped Sclorbo's blue bust with nothing failing."""
    pairs = pairs or CH02_CHWINGA_GLOW_RECOLOR
    pts = [(_hls(src), _hls(dst)) for src, dst in pairs.items()]
    l = _hls(rgb)[1]
    h = _interp([(a[1], b[0]) for a, b in pts], l)
    s = _interp([(a[1], b[2]) for a, b in pts], l)
    dl = _interp([(a[1], b[1] - a[1]) for a, b in pts], l)
    out = colorsys.hls_to_rgb(h, min(max(l + dl, 0.0), 1.0), s)
    return tuple(int(round(c * 255)) for c in out)


def chwinga_bust(campaign):
    """Sclorbo's bust with the glow ramp shifted to spirit-green (the map sprite's swap). A bust
    with no glow left to shift is an error: the recolour silently doing nothing is the bug."""
    im = Image.open(os.path.join(_bust_dir(campaign), CH02_CHWINGA_SPRITE_SRC + '.png')).convert('P')
    pal = list(im.getpalette()[:48])
    shifted = 0
    for i in range(1, 16):                                # index 0 is the transparent key
        rgb = tuple(pal[i * 3:i * 3 + 3])
        if _glow_band(rgb):
            pal[i * 3:i * 3 + 3] = list(CH02_CHWINGA_GLOW_RECOLOR.get(rgb) or glow_to_green(rgb))
            shifted += 1
    if not shifted:
        raise SystemExit('ERROR: %s.png has no glow colours to shift for the ch02 chwinga '
                         '(inject.unit_art.chwinga_bust)' % CH02_CHWINGA_SPRITE_SRC)
    out = im.copy()
    out.putpalette(pal)
    return out


def _cast_busts(campaign):
    bust_dir = _bust_dir(campaign)
    return [Bust(uid, 'cast', slot, _file_bust(os.path.join(bust_dir, uid + '.png')))
            for uid, slot in PORTRAIT_MAP.items()]


def _guest_busts(campaign):
    bust_dir = _bust_dir(campaign)
    dressed = set(dressed_guest_slots(campaign))
    return [Bust(uid, 'guest', slot, _file_bust(os.path.join(bust_dir, uid + '.png')))
            for uid, slot in GUEST_PORTRAIT_MAP.items() if slot in dressed]


def _chwinga_busts(campaign):
    """One recoloured image, on each chwinga's portrait slot."""
    if not os.path.isfile(os.path.join(_bust_dir(campaign), CH02_CHWINGA_SPRITE_SRC + '.png')):
        return []
    image = functools.lru_cache(maxsize=None)(lambda: chwinga_bust(campaign))
    return [Bust(uid, 'chwinga', CH02_CHWINGA_PORTRAIT_SLOT[npc_slot], image)
            for uid, npc_slot in CH02_CHWINGA]


def _visit_busts(campaign):
    vendor = os.path.join(_bust_dir(campaign), 'vendor')
    out = []
    for vid, (mug, slot, recolor) in sorted(CH05_VISIT_FACES.items()):
        path = os.path.join(vendor, mug)
        if os.path.isfile(path):
            out.append(Bust(vid, 'visit', slot,
                            lambda path=path, recolor=recolor: _vendor_mug_to_bust(path, recolor)))
    return out


def _arena_busts(campaign):
    """One bust per attendant SLOT. Two hosts may share a slot only if they share the
    attendant: keeping the first chapter's art while GetArenaPresentationFace still emits a
    case for both hosts would put the wrong attendant on screen with a green build."""
    claimed, out = {}, []
    for host, override in sorted(arena_presentation_config(campaign)['chapters'].items()):
        slot, portrait = override['face_slot'], override['portrait_path']
        if slot in claimed:
            if claimed[slot] != portrait:
                raise SystemExit('ERROR: %s: Arena attendant face_slot %r is already dressed '
                                 'with a different portrait (%s) -- give this chapter its own '
                                 'slot' % (override['chapter_path'], slot, claimed[slot]))
            continue
        claimed[slot] = portrait
        out.append(Bust('arena-%s' % host, 'arena', slot,
                        lambda p=portrait: _vendor_mug_to_arena_bust(p)))
    return out


BUST_KINDS = {'cast': _cast_busts, 'guest': _guest_busts, 'chwinga': _chwinga_busts,
              'visit': _visit_busts, 'arena': _arena_busts}


def busts(campaign, kinds=None):
    """Every bust the build dresses, by kind: 'cast', 'guest', 'chwinga', 'visit', 'arena'.
    Conditioned on the asset existing, exactly as each pass was: a slot we do not dress keeps
    its vanilla face. Only the kinds asked for are built, so a cast reader neither parses the
    Arena config nor depends on it."""
    return [b for kind, make in BUST_KINDS.items() if kinds is None or kind in kinds
            for b in make(campaign)]


@functools.lru_cache(maxsize=None)
def _unit_busts(campaign):
    return {b.uid: b for b in busts(campaign, kinds=('cast', 'guest', 'chwinga'))}


def unit_bust(campaign, uid):
    """The bust a unit shows, as an image, or None: what the build dresses for it."""
    b = _unit_busts(campaign).get(uid)
    if b is None:
        return None
    if b.kind != 'chwinga' and not os.path.isfile(os.path.join(_bust_dir(campaign), uid + '.png')):
        return None
    return b.image()


@functools.lru_cache(maxsize=None)
def vanilla_slot_bust(slot):
    """The vanilla face a character slot shows when no bust dresses it (Halvar wears Bazba's).
    Read from the pristine submodule, or None for a faceless slot."""
    from inject.decomp import _find_brace_block, vanilla_decomp_text
    chars = vanilla_decomp_text('src/data_characters.c')
    s, e = _find_brace_block(chars, '[CHARACTER_%s - 1]' % slot.upper().replace('CHARACTER_', ''),
                             'src/data_characters.c')
    m = re.search(r'\.portraitId\s*=\s*(0x[0-9a-fA-F]+|\d+)', chars[s:e])
    if not m or int(m.group(1), 0) == 0:
        return None
    return portrait_bust(int(m.group(1), 0))


@functools.lru_cache(maxsize=None)
def portrait_bust(portrait_id, root=None):
    """Portrait `portrait_id` decoded to a 96x80 bust with the closed mouth laid on where
    portrait_data.c puts it, in its own palette, or None. `root` is a decomp tree (default the
    pristine submodule); pass the build tree to see the faces the build dressed."""
    from inject.decomp import vanilla_decomp_text
    root = root or os.path.join(REPO, 'fireemblem8u')
    path = os.path.join(root, 'src', 'portrait_data.c')
    if root == os.path.join(REPO, 'fireemblem8u') or not os.path.isfile(path):
        text, root = vanilla_decomp_text('src/portrait_data.c'), os.path.join(REPO, 'fireemblem8u')
    else:
        with open(path, encoding='utf-8') as f:
            text = f.read()
    row = re.search(r'(?m)^\s*\{([^}]*)\},\s*//\s*%d\b' % (portrait_id - 1), text)
    if not row:
        return None
    f = [x.strip() for x in row.group(1).split(',')]
    pdir = os.path.join(root, 'graphics', 'portrait')
    pal = os.path.join(pdir, f[2] + '.agbpal')
    if f[0] == '0' and f[4] != '0':
        # A monster's face is a class card (portrait_Mogall_card), not a bust tileset.
        card = Image.open(os.path.join(pdir, f[4] + '.png'))
        card.putpalette(_agbpal(pal))
        return card
    if f[0] == '0':
        return None
    xmouth, ymouth = int(f[7]), int(f[8])
    bust = portrait_tool.decode(Image.open(os.path.join(pdir, f[0] + '.png')))
    mouth = Image.open(os.path.join(pdir, f[3] + '.png')).crop(
        (0, 0, portrait_tool.MOUTH_W, portrait_tool.MOUTH_H))
    bust.paste(mouth, (xmouth * 8, ymouth * 8))
    bust.putpalette(_agbpal(pal))
    return bust


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
        with tempfile.TemporaryDirectory(prefix='manchego_art_') as tmp:
            out = os.path.join(tmp, 'remapped.png')
            map_sprite_tool.remap_sms_palette(sheet, donor_png, out)
            im = Image.open(out)
            im.load()
    else:
        im = Image.open(sheet)
    w, h = sprite.frame or map_sprite_tool.donor_sms_geometry(sprite.donor)[1:]
    frame = im.crop((0, 0, min(w, im.width), h))
    pal = _cast_palette(campaign) if sprite.palette == 'cast' else _faction_palette(faction)
    frame.putpalette(pal + (frame.getpalette() or [])[len(pal):])
    frame.info['transparency'] = 0
    return frame


@functools.lru_cache(maxsize=None)
def vanilla_wait_donor(class_enum):
    """The <Name> of the wait sheet a vanilla class's SMSId points at (vanilla decomp at HEAD,
    so it needs no build), or None for a class with no row."""
    from inject.decomp import vanilla_decomp_text
    block = re.search(r'\[%s - 1\]\s*=\s*\{(.*?)\n\s*\},' % re.escape(class_enum),
                      vanilla_decomp_text('src/data_classes.c'), re.S)
    sms = re.search(r'\.SMSId\s*=\s*(0x[0-9a-fA-F]+|\d+)', block.group(1)) if block else None
    if not sms:
        return None
    row = re.search(r'unit_icon_wait_(\w+)_sheet\}.*//\s*%d\s*$' % int(sms.group(1), 0),
                    vanilla_decomp_text('src/unit_icon_wait_data.c'), re.M)
    return row.group(1) if row else None


def class_sprite(class_enum, faction):
    """A vanilla class's stock idle frame, or None for a class with no wait row."""
    name = vanilla_wait_donor(class_enum)
    if name is None:
        return None
    return idle_frame(None, Sprite(name, 'class', class_enum, (), os.path.join(
        VANILLA_WAIT_DIR, 'unit_icon_wait_%s_sheet.png' % name), None, name, None, 'faction'),
        faction)
