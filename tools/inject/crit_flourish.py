"""The critical-hit flourish (#11).
"""
import os
import struct
import sys

from inject import engine_patches
from inject.decomp import DECOMP, REPO
from inject.paths import DATA_BANIM_S


def _gba_lz77_stored(data):
    """A GBA LZ77 container in stored (literal-only) form: header 0x10|size<<8,
    then a 0x00 flag byte + 8 literal bytes per block. Always valid input for
    LZ77UnCompWram; the ~12% size tax on these tiny efx assets beats vendoring
    a real compressor."""
    out = bytearray(struct.pack('<I', 0x10 | (len(data) << 8)))
    for i in range(0, len(data), 8):
        chunk = data[i:i + 8]
        out.append(0)
        out += chunk + b'\0' * (8 - len(chunk))
    return bytes(out)


def _crit_flourish_bins(png_path):
    """battle_anims/d20-crit.png (RGBA, tile-multiple dims, <=15 opaque colors) ->
    (img_lz, pal_raw, tsa_lz) for the banim SpellFx BG1 layer: a 4bpp tile sheet
    (tile 0 = blank), a 16-color palette (index 0 = the transparent slot), and a
    30x20 TSA of raw tile indices (EfxTmCpyBG adds the palette/charblock bits)
    centering the art on the upper screen."""
    from PIL import Image
    im = Image.open(png_path).convert('RGBA')
    if im.width % 8 or im.height % 8 or im.width > 240 or im.height > 160:
        sys.exit('ERROR: %s must be 8px-multiple dims within the 240x160 screen'
                 % png_path)
    tw, th = im.width // 8, im.height // 8
    # SpellFx_RegisterBgGfx decompresses into gSpellAnimBgfx (0x1D00 B = 232
    # tiles, banim-ekrbattle.c) -- overflow corrupts adjacent banim overlay state
    if tw * th + 1 > 232:
        sys.exit('ERROR: %s is %d tiles + 1 blank; the SpellFx gfx buffer holds '
                 '232 (gSpellAnimBgfx, 0x1D00 B)' % (png_path, tw * th))
    px = im.load()
    colors = []

    def cidx(p):
        if p[3] < 128:
            return 0
        if p[:3] not in colors:
            colors.append(p[:3])
            if len(colors) > 15:
                sys.exit('ERROR: %s exceeds 15 opaque colors; the 4bpp sheet '
                         'caps there (index 0 is the transparent slot)' % png_path)
        return colors.index(p[:3]) + 1

    tiles = [bytes(32)]                       # tile 0 = blank (the empty screen)
    tsa = [[0] * 30 for _ in range(20)]
    ox, oy = (30 - tw) // 2, 3                # centered, upper third
    for ty in range(th):
        for tx in range(tw):
            data = bytearray()
            for row in range(8):
                for b in range(4):
                    left = cidx(px[tx * 8 + b * 2, ty * 8 + row])
                    right = cidx(px[tx * 8 + b * 2 + 1, ty * 8 + row])
                    data.append(left | (right << 4))
            tiles.append(bytes(data))
            tsa[oy + ty][ox + tx] = len(tiles) - 1
    pal = bytearray(2)                        # index 0 stays black/transparent
    for r, g, b in colors:
        pal += struct.pack('<H', (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10))
    pal += b'\0' * (32 - len(pal))
    img = b''.join(tiles)
    tsa_bytes = b''.join(struct.pack('<H', t) for row in tsa for t in row)
    return _gba_lz77_stored(img), bytes(pal), _gba_lz77_stored(tsa_bytes)


def inject_crit_flourish(campaign, verbose=True):
    """The cosmetic nat-20 crit flourish (#11): the ENGINE half is a campaign-
    agnostic patch (engine/patches/optional/crit-d20-flourish.patch -- a d20 pops on the
    SpellFx layer when the vanilla crit flash tears down); the ART comes from the
    campaign (battle_anims/d20-crit.png). No asset -> neither half applies and
    combat stays pure vanilla."""
    src = os.path.join(REPO, 'campaigns', campaign, 'battle_anims', 'd20-crit.png')
    if not os.path.isfile(src):
        if verbose:
            print('  no battle_anims/d20-crit.png -- flourish skipped (vanilla crits)')
        return
    img, pal, tsa = _crit_flourish_bins(src)
    for stem, data in (('msd20crit_img', img), ('msd20crit_pal', pal),
                       ('msd20crit_tsa', tsa)):
        with open(os.path.join(DECOMP, 'graphics', 'banim', stem + '.bin'), 'wb') as f:
            f.write(data)
    with open(DATA_BANIM_S, encoding='utf-8') as f:
        already = '.global Img_MsD20Crit' in f.read()
    if already:
        # idempotent like the patch: a second run in one process must not append
        # duplicate labels (assembler: symbol already defined)
        engine_patches.apply_optional('crit-d20-flourish')
        return
    with open(DATA_BANIM_S, 'a', encoding='utf-8') as f:
        f.write('\n'.join([
            '', '/* Manchego Stars #11: nat-20 crit flourish (campaign asset) */']
            + sum(([  '\t.align 2, 0', '\t.global %s' % label, '%s:' % label,
                      '\t.incbin "graphics/banim/%s.bin"' % stem]
                   for label, stem in (('Img_MsD20Crit', 'msd20crit_img'),
                                       ('Pal_MsD20Crit', 'msd20crit_pal'),
                                       ('Tsa_MsD20Crit', 'msd20crit_tsa'))), []))
            + '\n')
    engine_patches.apply_optional('crit-d20-flourish')
    if verbose:
        print('  d20 flourish armed: %d B gfx + %d B tsa on the crit-flash teardown'
              % (len(img), len(tsa)))
