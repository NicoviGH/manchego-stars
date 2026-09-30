"""Item icons: the campaign's icon art and the second icon palette bank.
"""
import os
import re
import shutil
import struct
import sys

from yaml_loader import yaml_load
from inject.arena import _bgr555
from inject.decomp import DECOMP, REPO
from inject.paths import CONST_MAPS_S, ITEMS_C


def item_icon_id(item_enum):
    """gItemData[item].iconId, scanned from data_items.c."""
    marker = '[%s] = {' % item_enum
    with open(ITEMS_C, encoding='utf-8') as f:
        lines = f.read().splitlines()
    for i, line in enumerate(lines):
        if marker in line:
            for probe in lines[i:i + 12]:
                m = re.search(r'\.iconId\s*=\s*(0x[0-9a-fA-F]+|\d+)', probe)
                if m:
                    return int(m.group(1), 0)
    sys.exit('ERROR: could not find iconId for %s in %s' % (item_enum, ITEMS_C))


def item_icon_png_path(icon_id):
    """The graphics/item_icon/*.png build-source file an iconId resolves to. Item icons
    are 16x16 4bpp tiles concatenated in data/data_item_icon.s in iconId order
    (item_icon_tiles); the Nth .incbin (0-based) is iconId N, and the decomp builds each
    .4bpp from a same-named .png (`%.4bpp: %.png`). Read it, never hardcode the name."""
    s = os.path.join(DECOMP, 'data', 'data_item_icon.s')
    incbins = re.findall(r'\.incbin\s+"(graphics/item_icon/[^"]+)\.4bpp"',
                         open(s, encoding='utf-8').read())
    if icon_id >= len(incbins):
        sys.exit('ERROR: iconId %#x past %d item icons in %s' % (icon_id, len(incbins), s))
    return incbins[icon_id] + '.png'


def inject_item_icons(campaign, verbose=True):
    """Swap a vanilla item's 16x16 icon for a campaign asset from campaign.yaml
    `item_icons:` (ITEM enum -> item_icons/<name>.png). Overwrites the item's tracked
    .png source (gbagfx makes the .4bpp at build). FE8 keeps one icon per item id, so
    every copy shows the new art (cf. inject_item_names for the name)."""
    cfg = os.path.join(REPO, 'campaigns', campaign, 'campaign.yaml')
    with open(cfg, encoding='utf-8') as f:
        icons = (yaml_load(f) or {}).get('item_icons') or {}
    if not icons:
        if verbose:
            print('  (no item_icons declared)')
        return
    from PIL import Image
    for item_enum, asset in icons.items():
        src = os.path.join(REPO, 'campaigns', campaign, 'item_icons', asset + '.png')
        if not os.path.isfile(src):
            sys.exit('ERROR: item_icon asset not found: %s' % src)
        im = Image.open(src)
        if im.mode != 'P' or im.size != (16, 16):
            sys.exit('ERROR: %s must be a 16x16 indexed (mode P) PNG; got %s %s'
                     % (src, im.mode, im.size))
        rel = item_icon_png_path(item_icon_id(item_enum))
        shutil.copyfile(src, os.path.join(DECOMP, rel))
        if verbose:
            print('  %-18s -> %s' % (item_enum, rel))


def _item_icon_pal2_bytes(colors):
    """16 '#rrggbb' colors -> a 32-byte BGR555 blob (one 16-colour item-icon palette bank)."""
    if len(colors) != 16:
        sys.exit('ERROR: item_icon_pal2.palette must have exactly 16 colors (got %d)' % len(colors))
    return b''.join(struct.pack('<H', _bgr555(c)) for c in colors)


def _append_item_icon_pal2(raw, colors):
    """Append the custom icon palette after FE8's two vanilla banks, without altering either."""
    if len(raw) < 64:
        sys.exit('ERROR: item_icon_palette.agbpal has %d bytes; expected two vanilla banks' % len(raw))
    out = bytearray(raw)
    if len(out) < 96:
        out.extend(b'\x00' * (96 - len(out)))
    out[64:96] = _item_icon_pal2_bytes(colors)
    return out


def _pal2_icon_ids(campaign):
    """The iconIds (gItemData.iconId) of the campaign's item_icon_pal2.icons, sorted."""
    cfg = os.path.join(REPO, 'campaigns', campaign, 'campaign.yaml')
    with open(cfg, encoding='utf-8') as f:
        pal2 = (yaml_load(f) or {}).get('item_icon_pal2') or {}
    return sorted(item_icon_id(e) for e in (pal2.get('icons') or []))


def _ms_pal2_iconids_asm(ids):
    """gMSPal2IconIds[] -- iconIds the DrawIcon hook routes from BG bank 4 to reserved bank 15.
    The 0xFFFF terminator is outside the valid icon-id range."""
    lines = ['', '/* Manchego Stars item icons that draw from custom palette 2 (#23). */',
             '\t.align 2, 0', '\t.global gMSPal2IconIds', 'gMSPal2IconIds:']
    lines += ['\t.hword %d' % i for i in ids]
    lines.append('\t.hword 0xFFFF')
    return '\n'.join(lines)


def inject_item_icon_pal2(campaign, verbose=True):
    """Wire custom-coloured item icons (#23) through an additive third source palette.

    The two vanilla banks stay byte-for-byte intact. This appends item_icon_pal2.palette and emits
    gMSPal2IconIds[]; the generic DrawIcon hook routes those standard item icons from BG bank 4 to
    the dedicated custom bank 15. No-op when no item_icon_pal2 is declared.
    """
    cfg = os.path.join(REPO, 'campaigns', campaign, 'campaign.yaml')
    with open(cfg, encoding='utf-8') as f:
        pal2 = (yaml_load(f) or {}).get('item_icon_pal2') or {}
    if not pal2:
        if verbose:
            print('  (no item_icon_pal2 declared)')
        return
    palpath = os.path.join(DECOMP, 'graphics', 'item_icon', 'item_icon_palette.agbpal')
    with open(palpath, 'rb') as f:
        raw = bytearray(f.read())
    with open(palpath, 'wb') as f:
        f.write(_append_item_icon_pal2(raw, pal2['palette']))
    ids = _pal2_icon_ids(campaign)
    with open(CONST_MAPS_S, 'a', encoding='utf-8') as f:
        f.write(_ms_pal2_iconids_asm(ids) + '\n')
    if verbose:
        print('  custom palette appended; gMSPal2IconIds = %s' % ids)
