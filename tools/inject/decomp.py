"""Shared decomp source-access layer: paths + brace-patch primitives.

Imported by BOTH tools/build_campaign.py (content) and
tools/inject/engine_hooks.py (pipeline). Keep it dependency-free so neither
side creates an import cycle. See docs/decisions.md -> Engine/content file seam.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DECOMP = os.path.join(REPO, 'fireemblem8u')

# Decomp source files patched by hooks that BOTH tracks touch (content injects
# lord quotes / map sprites into these; engine_hooks patches lord-select into them).
BATTLEQUOTES_C = os.path.join(DECOMP, 'src', 'data_battlequotes.c')
BMUNIT_C = os.path.join(DECOMP, 'src', 'bmunit.c')
LORDSEL_FLAG_BASE = 0xF0


# Vanilla FE8 weapon key -> ITEM_ enum (constants/items.h). The single source mapping a
# campaign weapon (a plain vanilla id, or a flavor name's fe_base) to the decomp item.
# Shared because BOTH sides need it: content (build_campaign) emits enemy/guest loadouts from
# it; pipeline (difficulty) inverts it to resolve vanilla enemies. Lives here so neither side
# has to open the other's file to extend it (the seam: docs/decisions.md).
WEAPON_ITEM_ENUM = {
    'iron-sword': 'ITEM_SWORD_IRON', 'steel-sword': 'ITEM_SWORD_STEEL',
    'rapier': 'ITEM_SWORD_RAPIER', 'iron-lance': 'ITEM_LANCE_IRON',
    'silver-lance': 'ITEM_LANCE_SILVER', 'javelin': 'ITEM_LANCE_JAVELIN',
    'killing-edge': 'ITEM_SWORD_KILLER',
    'iron-axe': 'ITEM_AXE_IRON', 'steel-axe': 'ITEM_AXE_STEEL',
    'hand-axe': 'ITEM_AXE_HANDAXE',
    'iron-bow': 'ITEM_BOW_IRON', 'fire': 'ITEM_ANIMA_FIRE', 'flux': 'ITEM_DARK_FLUX',
}


def fe_item_enum(inv_entry):
    """The vanilla ITEM_ enum for a YAML inventory entry -- its fe_base (flavor name over a
    vanilla weapon) if present, else its id (a plain vanilla weapon)."""
    return WEAPON_ITEM_ENUM[inv_entry.get('fe_base') or inv_entry['id']]


def _find_brace_block(text, marker, path):
    """Return (start, end) covering the `{...}` (brace-balanced) after `marker`."""
    at = text.find(marker)
    if at < 0:
        sys.exit('ERROR: %r not found in %s' % (marker, path))
    brace = text.find('{', at)
    depth = 0
    i = brace
    while i < len(text):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return brace, i + 1
        i += 1
    sys.exit('ERROR: unbalanced braces for %r in %s' % (marker, path))


def _replace_brace_block(text, marker, new_body, path):
    """Replace the `{...}` after `marker` with `new_body` (a `{...}` string)."""
    s, e = _find_brace_block(text, marker, path)
    return text[:s] + new_body + text[e:]
