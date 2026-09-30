"""The title screen and its theme.
"""
import os
import sys

from yaml_loader import yaml_load
from inject.decomp import DECOMP, REPO


def inject_title_screen(campaign, verbose=True):
    """Replace the boot title screen's gold "FIRE EMBLEM" logo with "MANCHEGO
    STARS" in the same gold letterform style (gen_gold_title hand-built glyphs +
    the logo's own gradient/outline/shadow). Only the image source changes: the
    decomp's generic gbagfx rule rebuilds title_fire_emblem_logo.4bpp(.lz) from
    the .png, the palette is preserved, and gSprite_Title_FireEmblemLogo /
    data_titlescreen.s are untouched. Idempotent (rebuilds a fresh canvas)."""
    import gen_gold_title
    ts_dir = os.path.join(DECOMP, 'graphics', 'titlescreen')

    # 1. Logo graphic (256x64): "MANCHEGO STARS" gold in the top 32 rows; the two-line
    #    subtitle in the bottom 32 rows (the half the second sprite draws). title_logos
    #    is read as tiles (pixel edits don't map to sprite regions), but the logo graphic
    #    maps cleanly, so both texts live here.
    logo_png = os.path.join(ts_dir, 'title_fire_emblem_logo.png')
    gen_gold_title.compose_logo('MANCHEGO STARS',
                                ('RIME OF THE', 'FROSTMAIDEN')).save(logo_png)
    for stale in ('.4bpp', '.4bpp.lz'):
        p = logo_png[:-4] + stale
        if os.path.exists(p):
            os.remove(p)

    # 2. titlescreen.c: the vanilla second logo sprite (0x2080) draws the bottom 32 rows
    #    as a blended glow at Y=53 (oam0=1077), overlapping the logo. Repoint it to a
    #    plain draw at Y=80 so those rows (our subtitle) render BELOW the logo; and drop
    #    the "THE SACRED STONES" scroll banner. Idempotent.
    ts_c = os.path.join(DECOMP, 'src', 'titlescreen.c')
    with open(ts_c, encoding='utf-8') as f:
        src = f.read()
    src = src.replace(
        '    PutSpriteExt(2, 4, 1077, gSprite_Title_FireEmblemLogo, 0x2080);',
        '    PutSpriteExt(1, 4, 80, gSprite_Title_FireEmblemLogo, 0x2080); '
        '/* manchego: subtitle row, below the logo */')
    src = src.replace(
        '    PutSpriteExt(1, 16, 85, gSprite_Title_SacredStonesBanner, 0x31A0);',
        '    /* manchego: scroll banner dropped (subtitle is in the logo graphic) */')
    # Disable the title's idle timeout: after ~13.5s with no input Title_IDLE fires
    # GAME_ACTION_CLASS_REEL -> the attract/class-reel demo, which crashes (we removed the
    # op-anim path + the demo's class/chapter data no longer matches). Never time out --
    # the title just holds with its music until the player presses START.
    src = src.replace(
        '        if (proc->timer_idle == 815)',
        '        if (0) /* manchego: never time out to the attract demo (it crashes) */')
    with open(ts_c, 'w', encoding='utf-8') as f:
        f.write(src)

    # 3. Theme the backdrop: recolor the mountain/sky bg palette to icy blue and blank
    #    the two-dragon foreground (off-theme). Recolour SETS hue (idempotent -- rebuilds
    #    don't drift); blanking the dragon tiles makes BG0 fully transparent. We edit the
    #    COMMITTED JASC .pal source (the .gbapal is build-generated -- %.gbapal: %.pal --
    #    so it isn't present at inject time on a clean checkout) and drop the stale .gbapal
    #    so gbagfx regenerates it blue. Index 0 (the magenta placeholder) is left alone.
    import colorsys
    pal_path = os.path.join(ts_dir, 'title_main_background.pal')
    with open(pal_path, encoding='utf-8') as f:
        lines = f.read().splitlines()
    for i in range(4, len(lines)):           # lines 0-2 = header, line 3 = index 0
        parts = lines[i].split()
        if len(parts) != 3:
            continue
        r, g, b = (int(c) / 255 for c in parts)
        _, l, s = colorsys.rgb_to_hls(r, g, b)
        nr, ng, nb = colorsys.hls_to_rgb(0.57, l, max(s, 0.45))  # ~205deg icy blue
        lines[i] = '%d %d %d' % (round(nr * 255), round(ng * 255), round(nb * 255))
    with open(pal_path, 'w', encoding='utf-8', newline='') as f:
        f.write('\r\n'.join(lines) + '\r\n')   # gbagfx requires CRLF .pal line endings
    gbapal = pal_path[:-4] + '.gbapal'
    if os.path.exists(gbapal):
        os.remove(gbapal)

    dragon_png = os.path.join(ts_dir, 'title_dragon_foreground.png')
    from PIL import Image as _Image
    dr = _Image.open(dragon_png)
    blank = _Image.new('P', dr.size, 0)
    blank.putpalette(dr.getpalette())
    blank.save(dragon_png)
    for stale in ('.4bpp', '.4bpp.lz'):
        p = dragon_png[:-4] + stale
        if os.path.exists(p):
            os.remove(p)
    if verbose:
        print('  boot title -> "MANCHEGO STARS" + "RIME OF THE / FROSTMAIDEN"; '
              'bg recolored icy blue, dragons removed')


def inject_title_theme(campaign, verbose=True):
    """Recolor the chapter-title banner palettes from campaign.yaml `title_theme`.

    The banner's look is PALETTE data, not image data: chapter_title.c
    sub_80895B4 applies gPal_08A07AD8 / gPal_08A07C58 (data/data_A01CC4.s,
    incbin'd straight from baserom). gPal_08A07C58 is six tint pairs
    (normal+dim) of 16 colors; the GREEN pair (sub-pals 0+1) is what the
    Status screen draws the title card with (config 0x80) -- letters ride
    indices 1-6 and the banner plaque's leaf ramp indices 8-15. The in-map
    chapter intro uses the gray pair (config 8 -> +0xA0), left untouched.
    gPal_08A07AD8 (9 colors) is the bonus-claim screen's green ramp.

    We replace the six vanilla letter greens 1:1 with the YAML colors and
    hue-map every other green-dominant color (plaque leaves, dim variant)
    into the same family, then repoint the .s incbins at generated .bin
    files (data_A01CC4.s is in PATCHED_DECOMP_FILES, so each build starts
    from the vanilla incbins).
    """
    import colorsys
    import struct

    cfg_path = os.path.join(REPO, 'campaigns', campaign, 'campaign.yaml')
    with open(cfg_path, encoding='utf-8') as f:
        theme = (yaml_load(f) or {}).get('title_theme')
    if not theme:
        return
    letters = [tuple(int(h.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))
               for h in theme['letter_colors']]
    if len(letters) != 6:
        sys.exit('ERROR: title_theme.letter_colors must list 6 colors (light->dark)')
    vanilla_letters = [(240, 248, 248), (200, 232, 200), (160, 200, 160),
                       (112, 152, 112), (64, 112, 64), (16, 56, 16)]
    exact = dict(zip(vanilla_letters, letters))
    # family hue/extra saturation from the mid letter color
    target_h, _, target_s = colorsys.rgb_to_hls(*[v / 255 for v in letters[2]])

    def recolor(rgb):
        if rgb in exact:
            return exact[rgb]
        h, l, s = colorsys.rgb_to_hls(*[v / 255 for v in rgb])
        if not (0.19 <= h <= 0.47 and s > 0.08):  # not green family
            return rgb
        r, g, b = colorsys.hls_to_rgb(target_h, l, max(s, min(target_s, 0.6)))
        return tuple(round(v * 255) for v in (r, g, b))

    def gba(rgb):
        r, g, b = rgb
        return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)

    with open(os.path.join(DECOMP, 'baserom.gba'), 'rb') as f:
        rom = f.read()

    def transform(offset, count, recolor_through):
        out = []
        for i in range(count):
            v = struct.unpack_from('<H', rom, offset + i * 2)[0]
            rgb = ((v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3)
            out.append(gba(recolor(rgb) if i < recolor_through else rgb))
        return struct.pack('<%dH' % count, *out)

    pals = [  # (asm file, label, baserom offset, color count, recolor first N)
        # title letter palettes (chapter_title.c sub_80895B4)
        ('data/data_A01CC4.s', 'gPal_08A07AD8', 0xA07AD8, 9, 9),
        # sub_80895B4's config&1 table actually continues past the 9-color
        # label: the save-slot select (SaveMenuInitSlotPalette) reads pair 0's
        # normal row tail + the +0x10 dim row straight through these two
        # follower incbins -- without them the unselected slot banners stay
        # vanilla green (Nicolas, 2026-06-10 tour review). B0A's first 7 are
        # also the hard-save blink ramp; the rest is the per-difficulty pairs,
        # left vanilla.
        ('data/data_A01CC4.s', 'gUnknown_08A07AEA', 0xA07AEA, 0x10, 0x10),
        ('data/data_A01CC4.s', 'gUnknown_08A07B0A', 0xA07B0A, 0x70, 7),
        ('data/data_A01CC4.s', 'gPal_08A07C58', 0xA07C58, 0xC0, 32),
        # Status-screen banner PLAQUE sprites (uichapterstatus.c, OBJ rows 8-9;
        # pal 0 = the leaf-green ramp, pal 1 = blue-gray and passes through)
        ('data/data_A21658.s', 'Pal_PlayStatusSprites', 0xA2E1B8, 0x20, 0x20),
    ]
    for asm_rel, label, offset, count, n in pals:
        bin_rel = 'data/campaign_%s.bin' % label.lower()
        with open(os.path.join(DECOMP, bin_rel), 'wb') as f:
            f.write(transform(offset, count, n))
        asm_path = os.path.join(DECOMP, asm_rel)
        with open(asm_path, encoding='utf-8') as f:
            asm = f.read()
        old = '%s:  @ 0x0%X\n\t.incbin "baserom.gba", 0x%X, 0x%X' \
              % (label, 0x8000000 + offset, offset, count * 2)
        new = '%s:  @ 0x0%X (recolored: campaign title_theme)\n\t.incbin "%s"' \
              % (label, 0x8000000 + offset, bin_rel)
        if old not in asm:
            sys.exit('ERROR: incbin for %s not found in %s' % (label, asm_path))
        with open(asm_path, 'w', encoding='utf-8') as f:
            f.write(asm.replace(old, new))
    if verbose:
        print('  title banner palettes -> %s family (letters 1:1, greens hue-mapped)'
              % theme['letter_colors'][2])
