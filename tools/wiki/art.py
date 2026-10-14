"""The little pictures a Fire Emblem Wiki chapter page carries, drawn from the game's own art:
item icons, enemy map sprites, and the 32x32 minimug beside each available character.

Everything is a data URI, because the artifact viewer loads nothing from outside the page.
Vanilla art is read from the decomp submodule's graphics (never written); our busts come
from the campaign's portraits/.
"""
import base64
import functools
import io
import os
import re

from PIL import Image

import inject.decomp

GRAPHICS = os.path.join(inject.decomp.SUBMODULE, 'graphics')


def uri(img):
    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()


def _keyed(img):
    """An indexed sprite with palette index 0 drawn transparent, as the GBA does."""
    img = img.copy()
    img.info['transparency'] = 0
    return img


@functools.lru_cache(maxsize=None)
def _icon_files():
    """iconId -> item_icon PNG, in the order data_item_icon.s lays the tiles out."""
    text = inject.decomp.vanilla_decomp_text('data/data_item_icon.s')
    return re.findall(r'graphics/item_icon/(item_icon_\w+)\.4bpp', text)


@functools.lru_cache(maxsize=None)
def _item_icon_ids():
    text = inject.decomp.vanilla_decomp_text('src/data_items.c')
    out = {}
    for m in re.finditer(r'\[(ITEM_\w+)\]\s*=\s*\{(.*?)\n\s*\},', text, re.S):
        i = re.search(r'\.iconId\s*=\s*(0x[0-9a-fA-F]+|\d+)', m.group(2))
        if i:
            out[m.group(1)] = int(i.group(1), 0)
    return out


@functools.lru_cache(maxsize=None)
def item_icon(enum, custom=None):
    """The 16x16 inventory icon for an ITEM_ enum (or `custom`, a campaign icon PNG that
    replaces it in the ROM), or None."""
    if custom and os.path.exists(custom):
        return uri(_keyed(Image.open(custom)))
    icon = _item_icon_ids().get(enum)
    files = _icon_files()
    if icon is None or icon >= len(files):
        return None
    path = os.path.join(GRAPHICS, 'item_icon', files[icon] + '.png')
    return uri(_keyed(Image.open(path))) if os.path.exists(path) else None


@functools.lru_cache(maxsize=None)
def named_icon(stem):
    """An item_icon sheet by name (affinities, weapon-type ranks): 'affinity_ice'."""
    path = os.path.join(GRAPHICS, 'item_icon', 'item_icon_%s.png' % stem)
    return uri(_keyed(Image.open(path))) if os.path.exists(path) else None


@functools.lru_cache(maxsize=None)
def _wait_rows():
    """SMS id -> (size, sheet stem), from unit_icon_wait_data.c's `// N` rows."""
    text = inject.decomp.vanilla_decomp_text('src/unit_icon_wait_data.c')
    return {int(n): (size, sym) for size, sym, n in re.findall(
        r'\{\s*\d+\s*,\s*UNIT_ICON_SIZE_(\w+)\s*,\s*(unit_icon_wait_\w+)\s*\}\s*,\s*//\s*(\d+)',
        text)}


@functools.lru_cache(maxsize=None)
def _faction_palette(faction):
    raw = open(os.path.join(GRAPHICS, 'unit_icon', 'palette', 'unit_icon_pal_%s.agbpal'
                            % faction), 'rb').read()[:32]
    out = []
    for i in range(0, 32, 2):
        c = raw[i] | raw[i + 1] << 8
        out += [(c & 31) * 255 // 31, (c >> 5 & 31) * 255 // 31, (c >> 10 & 31) * 255 // 31]
    return out


@functools.lru_cache(maxsize=None)
def map_sprite(class_enum, faction='enemy'):
    """(data URI, width, height) of a vanilla class's standing map sprite in a faction's
    colours, or None."""
    try:
        block = re.search(r'\[%s - 1\]\s*=\s*\{(.*?)\n\s*\},' % re.escape(class_enum),
                          inject.decomp.vanilla_decomp_text('src/data_classes.c'), re.S).group(1)
        sms = int(re.search(r'\.SMSId\s*=\s*(0x[0-9a-fA-F]+|\d+)', block).group(1), 0)
        size, sym = _wait_rows()[sms]
    except (AttributeError, KeyError):
        return None
    return sheet_sprite(os.path.join(GRAPHICS, 'unit_icon', 'wait', sym + '.png'), size, faction)


@functools.lru_cache(maxsize=None)
def sheet_sprite(path, size='16x16', faction='enemy'):
    """The first wait frame of a sheet in a faction's colours, trimmed of empty rows above
    the figure the way the wiki's are. Our own sheets (map_sprites/) share the format."""
    if not os.path.exists(path):
        return None
    sheet = Image.open(path)
    w, h = (int(x) for x in size.lower().split('x'))
    frame = sheet.crop((0, 0, min(w, sheet.width), h))
    frame.putpalette(_faction_palette(faction) + frame.getpalette()[48:])
    box = frame.point(lambda i: 255 if i else 0).getbbox()
    if box:
        frame = frame.crop((0, box[1], frame.width, h))
    frame = _keyed(frame)
    return uri(frame), frame.width, frame.height


@functools.lru_cache(maxsize=None)
def minimug(path):
    """The 32x32 minimug FE8 builds from a 96x80 bust (portrait_tool's own crop)."""
    import portrait_tool
    if not os.path.exists(path):
        return None
    return uri(_keyed(portrait_tool._make_chibi(Image.open(path))))
