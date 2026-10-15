"""The item and weapon-rank icons a Fire Emblem Wiki chapter page carries, as data URIs (the
artifact viewer loads nothing from outside the page).

An item's icon is the PNG the build compiles for its iconId (inject.item_icons): the injected
tree's file when there is one, so a campaign icon (the Goodberry) shows as the ROM shows it,
else the vanilla decomp's. Busts, minimugs and map sprites are inject.unit_art's, not this
module's: one answer per unit, shared with the build (#491).
"""
import base64
import functools
import io
import os

from PIL import Image

import inject.decomp
import inject.item_icons

VANILLA_ICONS = os.path.join(inject.decomp.SUBMODULE, 'graphics', 'item_icon')


def uri(img):
    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()


def _keyed(img):
    """An indexed icon with palette index 0 drawn transparent, as the GBA does."""
    img = img.copy()
    img.info['transparency'] = 0
    return img


@functools.lru_cache(maxsize=None)
def item_icon(enum):
    """The 16x16 icon the ROM shows for an ITEM_ enum, or None."""
    try:
        rel = inject.item_icons.item_icon_png_path(inject.item_icons.item_icon_id(enum))
    except (Exception, SystemExit):
        return None
    for root in (inject.decomp.DECOMP, inject.decomp.SUBMODULE):
        path = os.path.join(root, rel)
        if os.path.exists(path):
            return uri(_keyed(Image.open(path)))
    return None


@functools.lru_cache(maxsize=None)
def named_icon(stem):
    """An item_icon sheet by name (affinities, weapon-type ranks): 'affinity_ice'."""
    path = os.path.join(VANILLA_ICONS, 'item_icon_%s.png' % stem)
    return uri(_keyed(Image.open(path))) if os.path.exists(path) else None
