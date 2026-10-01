"""Name plates: the cast's names and the campaign's item names.
"""
import os
import re
import sys

from yaml_loader import yaml_load
from inject.cast import load_unit, PORTRAIT_MAP, RAW_PID_PORTRAITS
from inject.decomp import REPO
from inject.paths import ITEMS_C, TEXTS_TXT
from inject.text import (
    display_name, name_message_body, raw_pid_name_text_id, set_message_body, vanilla_name_text_id)


def inject_names(campaign, verbose=True):
    """Write each cast member's display name into its vanilla slot's name message."""
    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    for unit_id, slot in PORTRAIT_MAP.items():
        unit = load_unit(campaign, unit_id)
        unit.setdefault('id', unit_id)
        name = display_name(unit)
        text_id = vanilla_name_text_id(slot)
        set_message_body(lines, text_id, name_message_body(name))
        if verbose:
            print('  %-10s -> MSG_%03X (was %s): %s' % (unit_id, text_id, slot, name))
    for _pid, (unit_id, slot, _portrait_id, name) in sorted(RAW_PID_PORTRAITS.items()):
        text_id = raw_pid_name_text_id(slot)
        appended = isinstance(slot, int)   # an id the build allocated (inject/message_alloc.py)
        set_message_body(lines, text_id, name_message_body(name))
        if verbose:
            print('  %-10s -> MSG_%03X (%s): %s'
                  % (unit_id, text_id, 'appended' if appended else 'was %s' % slot, name))
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def item_name_text_id(item_enum):
    """nameTextId of a vanilla item, scanned from data_items.c. FE8 stores one name
    message per item id (gItemData[].nameTextId), so renaming it retitles every copy
    of that item in-game -- read the id from the decomp, never hardcode."""
    marker = '[%s] = {' % item_enum
    with open(ITEMS_C, encoding='utf-8') as f:
        lines = f.read().splitlines()
    for i, line in enumerate(lines):
        if marker in line:
            for probe in lines[i:i + 12]:
                m = re.search(r'\.nameTextId\s*=\s*(0x[0-9a-fA-F]+|\d+)', probe)
                if m:
                    return int(m.group(1), 0)
    sys.exit('ERROR: could not find nameTextId for %s in %s' % (item_enum, ITEMS_C))


def inject_item_names(campaign, verbose=True):
    """Rename vanilla items globally from campaign.yaml `item_names:` (ITEM enum ->
    display name). FE8 keeps a single name per item id, so a reflavored consumable
    reads the same for the whole party (cf. the cast's per-unit flavor names are
    documentation only -- the engine can't differ them)."""
    cfg = os.path.join(REPO, 'campaigns', campaign, 'campaign.yaml')
    with open(cfg, encoding='utf-8') as f:
        renames = (yaml_load(f) or {}).get('item_names') or {}
    if not renames:
        if verbose:
            print('  (no item_names declared)')
        return
    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    for item_enum, name in renames.items():
        text_id = item_name_text_id(item_enum)
        set_message_body(lines, text_id, name_message_body(str(name)))
        if verbose:
            print('  %-18s -> MSG_%03X: %s' % (item_enum, text_id, name))
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
