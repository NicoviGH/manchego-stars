#!/usr/bin/env python3
"""Build the campaign wiki: one page per chapter, laid out like the Fire Emblem Wiki's chapter
pages, generated from our YAML and the vanilla decomp so it cannot drift from either.

    python3 tools/gen_wiki.py            # writes build/wiki/index.html

Nothing on a page is typed by hand. Each section names its source:
  * OUR chapter       -- campaigns/<c>/chapters/ch*.yaml (active or `status: planned`)
  * the vanilla TWIN  -- the decomp at HEAD (units, recruits, drops, chests, gifts, shops),
                         read through difficulty.py's readers, never the working tree
  * the twin's play   -- the Fire Emblem Wiki's own Strategy section, read from the local
                         mirror in References/fe8-wiki/ and labelled as theirs
The stylesheets in tools/wiki/assets/ are the wiki's own (Timeless skin + site styles), so the
page reads like the reference it borrows from; the branding is ours.
"""
import base64
import collections
import functools
import glob
import html
import io
import os
import re
import sys

import yaml

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import difficulty                                      # noqa: E402
import scene_preview                                   # noqa: E402
import unit_load                                       # noqa: E402
import inject.cast                                     # noqa: E402
import inject.chapter_settings                         # noqa: E402
import inject.decomp                                   # noqa: E402
import inject.raw_pids                                 # noqa: E402
import inject.sms                                      # noqa: E402
import inject.stats                                    # noqa: E402
import inject.unit_art as unit_art                     # noqa: E402
import inject.villages                                 # noqa: E402
from wiki import pages as wp, site as wsite             # noqa: E402
import portrait_tool                                   # noqa: E402
from inject.class_ids import class_display_name        # noqa: E402
from wiki import art                                   # noqa: E402
from wiki import markup as mk                          # noqa: E402

ROOT = os.path.dirname(TOOLS)
CAMPAIGN = 'rime-of-the-frostmaiden'
CAMP = os.path.join(ROOT, 'campaigns', CAMPAIGN)
ASSETS = os.path.join(TOOLS, 'wiki', 'assets')
WIKI_MIRROR = os.path.join(ROOT, 'references', 'References', 'fe8-wiki')
OUT = os.path.join(ROOT, 'build', 'wiki', 'index.html')

# Vanilla FE8 by chapter NUMBER on Eirika's route (the curve twin, #459), plus the decomp stem
# its events live under (decomp suffix `a` is Eirika's route; the guide's letters are swapped),
# and the wiki mirror's page for it. Ephraim's maps appear as map DONORS, so they are listed too.
VANILLA = {
    'FE8 Prologue': ('prologue', 'The Fall of Renais', 'The_Fall_of_Renais'),
    'FE8 Ch1': ('ch1', 'Escape!', 'Escape'),
    'FE8 Ch2': ('ch2', 'The Protected', 'The_Protected'),
    'FE8 Ch3': ('ch3', 'The Bandits of Borgo', 'The_Bandits_of_Borgo'),
    'FE8 Ch4': ('ch4', 'Ancient Horrors', 'Ancient_Horrors'),
    'FE8 Ch5': ('ch5', "The Empire's Reach", 'The_Empires_Reach'),
    'FE8 Ch5x': ('ch5x', 'Unbroken Heart', 'Unbroken_Heart'),
    'FE8 Ch6': ('ch6', 'Victims of War', 'Victims_of_War'),
    'FE8 Ch7': ('ch7', 'Waterside Renvall', 'Waterside_Renvall'),
    'FE8 Ch8': ('ch8', "It's a Trap!", 'Its_a_Trap'),
    'FE8 Ch9': ('ch9a', 'Distant Blade', 'Distant_Blade'),
    'FE8 Ch10': ('ch10a', 'Revolt at Carcino', 'Revolt_at_Carcino'),
    'FE8 Ch11': ('ch11a', 'Creeping Darkness', 'Creeping_Darkness'),
    'FE8 Ch12': ('ch12a', 'Village of Silence', 'Village_of_Silence'),
    'FE8 Ch13': ('ch13a', 'Hamill Canyon', 'Hamill_Canyon'),
    'FE8 Ch14': ('ch14a', 'Queen of White Dunes', 'Queen_of_White_Dunes'),
    'FE8 Ch15': ('ch15a', 'Scorched Sand', 'Scorched_Sand'),
    'FE8 Ch16': ('ch16a', 'Ruled by Madness', 'Ruled_by_Madness'),
    'FE8 Ch17': ('ch17a', 'River of Regrets', 'River_of_Regrets'),
    'FE8 Ch18': ('ch18a', 'Two Faces of Evil', 'Two_Faces_of_Evil'),
    'FE8 Ch19': ('ch19a', 'Last Hope', 'Last_Hope'),
    'FE8 Ch20': ('ch20a', 'Darkling Woods', 'Darkling_Woods'),
    'FE8 Final': ('ch21a', 'Sacred Stone', 'Sacred_Stone_part_1'),
    'FE8 Ch9 Ephraim': ('ch9b', 'Fort Rigwald', 'Fort_Rigwald'),
    'FE8 Ch10 Ephraim': ('ch10b', 'Turning Traitor', 'Turning_Traitor'),
    'FE8 Ch11 Ephraim': ('ch11b', 'Phantom Ship', 'Phantom_Ship'),
    'FE8 Ch12 Ephraim': ('ch12b', 'Landing at Taizel', 'Landing_at_Taizel'),
    'FE8 Ch13 Ephraim': ('ch13b', "Fluorspar's Oath", 'Fluorspars_Oath'),
    'FE8 Ch14 Ephraim': ('ch14b', 'Father and Son', 'Father_and_Son'),
}


def esc(s):
    return html.escape(str(s if s is not None else ''), quote=True)


def para(text):
    """A YAML prose block as paragraphs (folded scalars keep blank-line breaks)."""
    if not text:
        return ''
    if isinstance(text, (list, tuple)):
        return ''.join('<p>%s</p>' % esc(t) for t in text)
    return ''.join('<p>%s</p>' % esc(p.strip()) for p in str(text).split('\n\n') if p.strip())


def twin_key(ref):
    """Normalise a YAML reference ("FE8 Ch13 — Hamill Canyon", "FE8 Ch13 Ephraim — ...") to a
    VANILLA key, or None."""
    if not ref:
        return None
    ref = str(ref)
    m = re.match(r'\s*FE8\s+(Prologue|Final|Ch\s*\d+x?)(a|b)?(\s+Ephraim)?', ref)
    if not m:
        return None
    base = 'FE8 ' + m.group(1).replace(' ', '')
    eph = m.group(3) or (m.group(2) == 'b')
    key = base + (' Ephraim' if eph else '')
    return key if key in VANILLA else (base if base in VANILLA else None)


def twin_label(ref):
    k = twin_key(ref)
    if not k:
        return esc(ref) if ref else '—'
    return '%s <i>%s</i>' % (esc(k.replace('FE8 ', 'FE8 ')), esc(VANILLA[k][1]))


# ── vanilla, from the decomp ───────────────────────────────────────────────────

_ITEM_NAMES = None


def _vanilla_item_names():
    """ITEM_ enum -> its in-game name, from data_items.c's nameTextId and texts.txt at HEAD."""
    global _ITEM_NAMES
    if _ITEM_NAMES is None:
        items = inject.decomp.vanilla_decomp_text('src/data_items.c')
        texts = inject.decomp.vanilla_decomp_text('texts/texts.txt')
        msgs = {int(m.group(1), 16): m.group(2) for m in
                re.finditer(r'^## MSG_([0-9A-Fa-f]+)\n(.*?)\[X\]', texts, re.M)}
        _ITEM_NAMES = {}
        for m in re.finditer(r'\[(ITEM_\w+)\]\s*=\s*\{(.*?)\n\s*\},', items, re.S):
            n = re.search(r'\.nameTextId\s*=\s*(0x[0-9a-fA-F]+|\d+)', m.group(2))
            if n and int(n.group(1), 0) in msgs:
                _ITEM_NAMES[m.group(1)] = re.sub(r'\[[^\]]*\]', '', msgs[int(n.group(1), 0)]).strip()
    return _ITEM_NAMES


def item_name(enum):
    """ITEM_AXE_IRON -> Iron Axe: the game's own name, else a readable spelling of the enum."""
    if not enum:
        return ''
    real = _vanilla_item_names().get(str(enum))
    if real:
        return real
    e = str(enum).replace('ITEM_', '')
    parts = e.split('_')
    kinds = {'SWORD', 'LANCE', 'AXE', 'BOW', 'ANIMA', 'LIGHT', 'DARK', 'STAFF', 'MONSTER'}
    if len(parts) > 1 and parts[0] in kinds:
        parts = parts[1:] + ([parts[0]] if parts[0] in ('SWORD', 'LANCE', 'AXE', 'BOW') else [])
    return ' '.join(p.capitalize() for p in parts)


def pretty_enum(e, prefix):
    return ' '.join(w.capitalize() for w in str(e).replace(prefix, '').split('_'))


_PLAIN = None


def _is_plain_item(enum):
    """True for a vanilla ITYPE_ITEM (rings, gems, boosters, potions): what a thief steals."""
    global _PLAIN
    if _PLAIN is None:
        text = inject.decomp.vanilla_decomp_text('src/data_items.c')
        _PLAIN = {m.group(1) for m in re.finditer(r'\[(ITEM_\w+)\]\s*=\s*\{(.*?)\n\s*\},', text, re.S)
                  if '.weaponType = ITYPE_ITEM' in m.group(2)}
    return enum in _PLAIN


@functools.lru_cache(maxsize=None)
def vanilla_payload(key):
    """Everything the twin hands out and fields, from its own event scripts at HEAD."""
    stem = VANILLA[key][0]
    out = {'stem': stem, 'chests': [], 'gifts': [], 'drops': [], 'steals': [], 'shops': [],
           'recruits': [],
           'grants': [], 'enemies': [], 'n_villages': 0, 'error': None}
    try:
        info = inject.decomp.vanilla_decomp_text('src/events/%s-eventinfo.h' % stem)
        script = inject.decomp.vanilla_decomp_text('src/events/%s-eventscript.h' % stem)
    except Exception as ex:                            # stem without events in this decomp
        out['error'] = 'no event files for %s (%s)' % (stem, ex.__class__.__name__)
        return out
    out['chests'] = re.findall(r'Chest\((ITEM_\w+)', info)
    out['gold_chests'] = re.findall(r'ChestMoney\(\s*(\d+)', info)
    out['gifts'] = list(difficulty._gift_items(script))
    out['n_villages'] = len(re.findall(r'Village\(', info))
    shoptext = inject.decomp.vanilla_decomp_text('src/events_shoplist.c')
    out['shops'] = [(sym, difficulty._shoplist_items(shoptext, sym))
                    for sym in re.findall(r'(?:Armory|Vendor|SecretShop)\(\s*(\w+)', info)]
    for u in difficulty._chapter_udefs(stem):
        if u['allegiance'] == 'FACTION_ID_RED' and u['items']:   # itemless = cutscene load
            out['enemies'].append(u)
            dropped = u['items'][-1] if u.get('itemDrop') else None
            if dropped:
                out['drops'].append(dropped)
            for i, it in enumerate(u['items']):          # a held non-weapon is the thief's prize
                if it != dropped and it not in ('ITEM_DOORKEY', 'ITEM_CHESTKEY') \
                        and _is_plain_item(it):
                    out['steals'].append(it)
    out['recruits'] = vanilla_joins().get(stem, [])
    try:
        out['grants'] = difficulty._named_item_grants(stem)
    except Exception:
        pass
    return out


EIRIKA_ORDER = ('prologue', 'ch1', 'ch2', 'ch3', 'ch4', 'ch5', 'ch5x', 'ch6', 'ch7', 'ch8',
                'ch9a', 'ch10a', 'ch11a', 'ch12a', 'ch13a', 'ch14a', 'ch15a', 'ch16a', 'ch17a',
                'ch18a', 'ch19a', 'ch20a', 'ch21a')
_JOINS = None


def vanilla_joins():
    """stem -> [(CHARACTER_, CLASS_, level, how)] for each character's FIRST armed appearance
    on Eirika's route: blue on the field, or green/red with a talk event that recruits them.
    Every later chapter re-loads the standing party; only the first load is a join. Ephraim's
    own stems are read on their own (their first appearance on that route)."""
    global _JOINS
    if _JOINS is None:
        _JOINS = {}
        for order in (EIRIKA_ORDER, ('ch9b', 'ch10b', 'ch11b', 'ch12b', 'ch13b', 'ch14b')):
            seen = set() if order is EIRIKA_ORDER else set(_seen_by('ch8'))
            for stem in order:
                try:
                    talk = difficulty._talk_recruits(stem)
                    loads = list(difficulty._chapter_udefs(stem))
                except Exception:
                    continue
                rows = []
                for u in loads:
                    char = u.get('charIndex')
                    if not char or char in seen or not u['items']:
                        continue
                    try:
                        if difficulty._character_number(char) not in difficulty.PLAYABLE_PIDS:
                            continue
                    except Exception:
                        continue
                    if u['allegiance'] == 'FACTION_ID_BLUE' or char in talk:
                        seen.add(char)
                        rows.append((char, u['classIndex'], u['level'],
                                     'talk' if char in talk else 'joins'))
                _JOINS[stem] = rows
                if order is EIRIKA_ORDER:
                    _SEEN[stem] = set(seen)
    return _JOINS


_SEEN = {}


def _seen_by(stem):
    vanilla_joins() if not _SEEN else None
    return _SEEN.get(stem, set())


# ── ours, from the YAML ────────────────────────────────────────────────────────

def load_yaml(path):
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def chapters():
    out = []
    for path in sorted(glob.glob(os.path.join(CAMP, 'chapters', 'ch*.yaml'))):
        d = load_yaml(path)
        d['_file'] = os.path.relpath(path, ROOT)
        d['_slug'] = os.path.basename(path)[:4]
        out.append(d)
    out.sort(key=lambda d: (d.get('chapter_number') if isinstance(d.get('chapter_number'), int)
                            else 0, d['_slug']))
    return out


def units_index():
    idx = {}
    for kind in ('pcs', 'npcs'):
        for path in glob.glob(os.path.join(CAMP, kind, '*.yaml')):
            d = load_yaml(path)
            if d.get('id'):
                d['_kind'] = kind
                idx[d['id']] = d
    return idx


@functools.lru_cache(maxsize=None)
def _bust(uid):
    return unit_art.unit_bust(CAMPAIGN, uid) if uid else None


def portrait(uid):
    """The bust the build dresses for `uid` (inject.unit_art), as a data URI, or None."""
    bust = _bust(uid)
    return png_uri(bust, key_index0=True) if bust is not None else None


@functools.lru_cache(maxsize=None)
def minimug(uid):
    """The 32x32 minimug the build writes for `uid`: portrait_tool.generate's chibi."""
    bust = _bust(uid)
    if bust is None:
        return None
    return png_uri(portrait_tool.generate(bust, static_portrait=True)[2], key_index0=True)


def png_uri(path_or_image, key_index0=False):
    """A PNG as a data URI. FE8 busts are indexed and keep palette index 0 as the transparent
    colour (the green backdrop); the game never draws it, so neither do we."""
    from PIL import Image
    img = path_or_image if hasattr(path_or_image, 'save') else Image.open(path_or_image)
    if key_index0 and img.mode == 'P':
        img = img.copy()
        img.info['transparency'] = 0
    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()


# Vanilla layout per VANILLA key, for a planned chapter's donor map.
def vanilla_layout(key):
    m = re.match(r'FE8 (Prologue|Final|Ch(\d+)(x?))( Ephraim)?$', key or '')
    if not m:
        return None
    if m.group(1) == 'Prologue':
        return 'PrologueMap'
    if m.group(1) == 'Final':
        return 'FinalChapterMap1'
    n = int(m.group(2))
    if m.group(3):
        return 'Ch5XMap'
    if 9 <= n <= 14:
        if m.group(4):
            return 'Ch9EphMap' if n == 9 else 'Ch%dEphraimMap' % n
        return 'Ch%dEirikaMap' % n
    return 'Ch%dMap' % n


_MAPS = {}


def map_image(chap):
    """(data URI, caption) for the chapter's map: our compiled map when it exists, else the
    map donor's vanilla layout in vanilla's own art (what we will reskin). Rendered with the
    same metatile code the map tools use; the vanilla art comes from the build tree, so the
    decomp submodule is never written to."""
    slug = chap['_slug']
    if slug in _MAPS:
        return _MAPS[slug]
    out = (None, '')
    from PIL import Image
    mf = (chap.get('map') or {}).get('file') if isinstance(chap.get('map'), dict) else None
    stem = os.path.splitext(os.path.basename(mf))[0] if mf else None
    try:
        if stem and os.path.exists(os.path.join(CAMP, 'maps', stem + '.mar')):
            import map_placement_preview as mpp
            grid, _, ts = mpp.load_map(stem)
            img = Image.new('RGB', (len(grid[0]) * 16, len(grid) * 16))
            for y, row in enumerate(grid):
                for x, m in enumerate(row):
                    img.paste(ts.metatile_image(m), (x * 16, y * 16))
            out = (png_uri(img), 'Our map (%dx%d)' % (len(grid[0]), len(grid)))
        else:
            key = twin_key(chap.get('fe8_base_map'))
            layout = vanilla_layout(key)
            if layout:
                from map_tileset_tool import (Tileset, vanilla_layout_data,
                                              vanilla_layout_tileset_assets)
                sub, bld = inject.decomp.SUBMODULE, os.path.join(ROOT, 'build', 'fireemblem8u')
                obj, pal, cfg = vanilla_layout_tileset_assets(sub, layout)
                g = os.path.join(bld, 'graphics', 'map')
                ts = Tileset(os.path.join(g, obj + '.4bpp'), os.path.join(g, pal + '.gbapal'),
                             os.path.join(sub, 'graphics', 'map', cfg + '.bin'))
                w, h, cells, _ = vanilla_layout_data(sub, layout)
                img = Image.new('RGB', (w * 16, h * 16))
                for j, m in enumerate(cells):
                    img.paste(ts.metatile_image(m), ((j % w) * 16, (j // w) * 16))
                out = (png_uri(img), 'Donor map, vanilla art: %s (%dx%d)'
                       % (VANILLA[key][1], w, h))
    except Exception as ex:                            # a missing build tree, a new layout
        out = (None, 'map not rendered (%s)' % ex.__class__.__name__)
    _MAPS[slug] = out
    return out


def our_item(it):
    """A YAML item ref -> (display name, ITEM_ enum or None), through inject.decomp.ITEM_ENUM:
    the table the build reads."""
    if isinstance(it, str):
        it = {'id': it}
    iid = it.get('id', '')
    enum = inject.decomp.ITEM_ENUM.get(it.get('fe_base') or iid)
    name = it.get('name') or (item_name(enum) if enum else iid.replace('-', ' ').title())
    return name, enum


def enemy_list(chap):
    try:
        return list(difficulty.chapter_roster_entries(chap))
    except Exception:
        return list(chap.get('enemy_units') or [])


_NAMES = {}


def recruits_of(chap):
    """Unit ids that join here, in order. The PCs are the founding party: they join in the
    campaign's first playable (non-prologue) chapter, which `build` marks as `_founding`."""
    pc = chap.get('post_chapter') or {}
    ids = list(chap.get('_founding') or [])
    for k in ('units_available_to_recruit', 'units_recruited_in_chapter'):
        for r in pc.get(k) or []:
            rid = r.get('id') if isinstance(r, dict) else r
            if isinstance(r, dict) and r.get('name'):
                _NAMES.setdefault(rid, r['name'])
            if rid and rid not in ids:
                ids.append(rid)
    return ids


def unit_name(uid, units):
    return (units.get(uid) or {}).get('name') or _NAMES.get(uid) or uid.replace('-', ' ').title()


def bosses_of(chap):
    return [e for e in enemy_list(chap) if e.get('is_boss')]


def item_rows(chap):
    """(item display, enum or None, vehicle) for every delivery vehicle the ROM wires. A vehicle
    is (kind, detail): ('village', tile), ('chest', tile), ('drop' | 'steal', class token),
    ('gift', giver), ('save_all', None), ('scene', None), ('boat', None). Gold comes as
    ('N gold', None, vehicle). The `economy:` ledger is design bookkeeping no injector reads,
    so it is not one."""
    rows = []
    for v in chap.get('villages') or []:
        for r in v.get('visit_reward') or v.get('reward') or []:
            if r.get('id') == 'gold':
                rows.append(('%s gold' % r.get('amount'), None, ('village', v.get('tile'))))
            elif r.get('id'):
                n, e = our_item(r)
                rows.append((n, e, ('village', v.get('tile'))))
    for c in chap.get('chests') or []:
        for it in c.get('contents') or []:
            n, e = our_item(it)
            rows.append((n, e, ('chest', c.get('position'))))
    for e in enemy_list(chap):
        drop = e.get('item_drop')
        if drop:
            n, en = our_item(drop)
            rows.append((n, en, ('drop', e.get('class'))))
        for it in e.get('inventory') or []:
            n, en = our_item(it)
            iid = it.get('id') if isinstance(it, dict) else it
            if iid != drop and en and en not in ('ITEM_DOORKEY', 'ITEM_CHESTKEY') \
                    and _is_plain_item(en):
                rows.append((n, en, ('steal', e.get('class'))))
    for g in (chap.get('deployment') or {}).get('green_allies') or []:
        if g.get('gift'):
            n, en = our_item(g['gift'])
            rows.append((n, en, ('gift', g.get('fe_name') or g.get('name') or g.get('id'))))
    bonus = (chap.get('economy') or {}).get('save_all_bonus')
    if bonus:
        n, en = our_item(bonus)
        rows.append((n, en, ('save_all', None)))
    for site in (chap.get('post_chapter') or {}).get('reward_sites') or []:
        if site.get('gift'):
            n, en = our_item(site['gift'])
            rows.append((n, en, ('scene', None)))
    for boat in chap.get('rescue_boats') or []:
        for r in (boat.get('talk') or {}).get('reward') or []:
            n, en = our_item(r)
            rows.append((n, en, ('boat', None)))
    return rows


def _compass(tile, cols, rows):
    """A tile as the wiki places a site: 'northern', 'southwestern', 'central'."""
    x, y = tile
    ns = 'north' if y < rows / 3 else 'south' if y >= 2 * rows / 3 else ''
    ew = 'west' if x < cols / 3 else 'east' if x >= 2 * cols / 3 else ''
    return (ns + ew + 'ern') if (ns or ew) else 'central'


def obtain_phrases(rows_, cols, nrows):
    """How the wiki words each vehicle: 'Open northern left [[chest]]', 'Visit southern
    [[village]]', 'Steal from enemy [[Brigand]]'. Sites sharing a direction are told apart
    left/middle/right, as the wiki tells Borgo's three northern chests apart."""
    places = {}
    for _n, _e, (kind, detail) in rows_:
        if kind in ('chest', 'village') and detail and cols and nrows:
            places.setdefault((kind, _compass(detail, int(cols), int(nrows))), set()).add(
                tuple(detail))
    out = []
    for _n, _e, (kind, detail) in rows_:
        if kind in ('chest', 'village'):
            where = ''
            if detail and cols and nrows:
                where = _compass(detail, int(cols), int(nrows))
                same = sorted(places[(kind, where)])
                if len(same) > 1:
                    order = ['left', 'middle', 'right'] if len(same) == 3 else \
                        ['left', 'right'] if len(same) == 2 else [str(i + 1) for i in range(len(same))]
                    where += ' ' + order[same.index(tuple(detail))]
                where += ' '
            out.append('%s %s[[%s]]' % ('Open' if kind == 'chest' else 'Visit', where, kind))
        elif kind in ('drop', 'steal'):
            cls, _a = wiki_class(detail)
            out.append('%s enemy [[%s]]' % ('Dropped by' if kind == 'drop' else 'Steal from', cls))
        elif kind == 'gift':
            out.append('Given by %s at the end of the chapter if it survives' % detail)
        elif kind == 'save_all':
            out.append('Automatically at end of chapter if every village is saved')
        elif kind == 'scene':
            out.append('Automatically at end of chapter')
        else:
            out.append('Talk to a rescue boat')
    return out


_SCENES = None


def _scenes():
    """chapter -> [(trigger, event, title, steps)] for every scene the scene previewer knows: the
    wired ones as the ROM builds them, then the drafts, one entry per scripted EVENT (a draft
    split at its beat breaks is still one event). `event` is the YAML event a draft renders."""
    global _SCENES
    if _SCENES is None:
        _SCENES = {}
        reg = scene_preview.registry()
        for key, entry in reg.items():
            _SCENES.setdefault(key.split('/')[0], []).append(
                (entry.event.trigger if entry.event else None, None, entry.title,
                 [scene_preview.preview(key)]))
        drafts = collections.OrderedDict()
        for key, scene in scene_preview.drafts().items():
            stem = re.sub(r'-\d+$', '', key.split('/draft-')[1])
            drafts.setdefault((key.split('/')[0], stem), []).append(scene)
        seen = collections.Counter()
        for (chapter, stem), scenes in drafts.items():
            trigger = stem.split('.')[0]
            seen[chapter, trigger] += 1
            _SCENES.setdefault(chapter, []).append(
                (trigger, (chapter, trigger, seen[chapter, trigger]), None, scenes))
    return _SCENES


def _scripted_event(chap, ref):
    """The YAML event a draft renders: the nth scripted event on its trigger."""
    _chapter, trigger, n = ref
    evs = [e for e in chap.get('events') or []
           if isinstance(e, dict) and e.get('script') and e.get('trigger') == trigger]
    return evs[n - 1] if n <= len(evs) else {}


def script_section(trigger, kind=None):
    """Which section of the wiki's Script page a scene belongs in, from its trigger."""
    if kind == 'quote' or trigger in ('boss_battle', 'unit_engages_boss', 'boss_death'):
        return 'Battle quotes'
    if trigger == 'chapter_start':
        return 'Opening'
    if trigger == 'chapter_end':
        return 'Ending'
    if trigger == 'visit':
        return 'Villages'
    if kind == 'talk' or trigger is None or 'talk' in trigger:   # None: a boat boarded by Talk
        return 'Talk conversations'
    return 'In battle'


def _script_steps(scenes, units):
    """`wiki.pages._scene` steps for a run of scenes, as one transcript. A face that leaves
    for good while the scene goes on is a stage direction, as the wiki writes "(Artur leaves)".
    A face cleared to free a podium and back later is staging, and the faces cleared when a
    scene ends are not news either."""
    out = []
    for scene in scenes:
        steps = scene.steps
        for i, step in enumerate(steps):
            if step.kind == 'exit':
                rest = [s for s in steps[i + 1:] if s.kind == 'box']
                if step.speaker and rest and all(s.speaker != step.speaker for s in rest):
                    out.append(('stage', None, '%s leaves' % unit_name(step.speaker, units)))
                continue
            text = ' '.join(l.strip() for l in step.lines if l.strip())
            if step.kind == 'box' and text:
                out.append(('say', unit_name(step.speaker, units), text) if step.speaker
                           else ('narrate', None, text))
    return out


def _event_for(chap, trigger, ref):
    """The YAML event a scene renders: a draft's own, else the one event on its trigger."""
    if ref:
        return _scripted_event(chap, ref)
    evs = [e for e in chap.get('events') or []
           if isinstance(e, dict) and trigger and e.get('trigger') == trigger]
    return evs[0] if len(evs) == 1 else {}


def _when(chap, ev, units):
    """When a mid-battle scene fires, in the wiki's words ("Turn 2, player phase")."""
    if ev.get('turn'):
        return 'Turn %s, player phase' % ev['turn']
    if ev.get('unit'):
        named = {e.get('id'): e.get('name') for e in enemy_list(chap)}
        return 'Upon defeating %s' % (named.get(ev['unit']) or unit_name(ev['unit'], units))
    if ev.get('zone'):
        return 'When a unit reaches the %s' % ev['zone'].replace('_', ' ')
    return None


def script_sections(chap, units):
    """{section: [(subheading, [scene])]} for the chapter's Script page, or {} with no script.

    Subheadings are the wiki's: "Fighting X"/"Defeating X" for battle quotes, "X and Y" for a
    talk ("Anyone and X" when any unit can start it, as the wiki writes "Visit with anyone"),
    when it fires for a mid-battle scene, else what the scene is. A section holding one scene
    needs none, as the wiki's own Opening has none."""
    slug = chap['_slug']
    bosses = [b.get('name') for b in bosses_of(chap) if b.get('name')]
    talks = {unit_name(r, units): by and unit_name(by, units)
             for r, by in talk_joins(chap).items()}
    out = collections.OrderedDict()
    for trigger, ref, title, scenes in _scenes().get(slug, []):
        ev = _event_for(chap, trigger, ref)
        steps = _script_steps(scenes, units)
        if all(kind == 'stage' for kind, _w, _t in steps):
            continue
        speakers = list(collections.OrderedDict.fromkeys(
            w for kind, w, _t in steps if kind == 'say'))
        section = script_section(trigger, ev.get('type'))
        if section == 'Opening' and not out.get('Opening') and not speakers:
            section = 'Introduction'       # a narration card before anyone speaks
        if section == 'Battle quotes':
            who = bosses[0] if len(bosses) == 1 else speakers[0]
            sub = '%s %s' % ('Defeating' if trigger == 'boss_death' else 'Fighting', who)
        elif section == 'Talk conversations':
            # Who starts it, then who is talked to, as the wiki heads "Ross and Garcia". A
            # recruit talk names its wired talker, or "Anyone" when any party member can start
            # it; a talk only one side speaks in is likewise open to anyone (the rescue boats).
            joined = next((w for w in speakers if w in talks), None)
            if joined:
                pair = [talks[joined] or 'Anyone', joined]
            else:
                pair = speakers[:2] if len(speakers) > 1 else ['Anyone'] + speakers
            sub = ' and '.join(pair)
            if joined:
                steps += [('stage', None, '%s is recruited' % joined)]
        else:
            sub = (_when(chap, ev, units) if section == 'In battle' else None) or (
                title[:1].upper() + title[1:] if title
                else (trigger or '').replace('_', ' ').capitalize())
        groups = out.setdefault(section, [])
        base, extra = re.match(r'(.*?)(?: \((.*)\))?$', title or '').groups()
        prev = groups[-1] if groups else None
        if extra and prev and prev[2] == base:
            if extra.startswith('no '):    # the same scene when someone is missing: a variant
                who = extra[3:]
                if not isinstance(prev[1][0], tuple):
                    prev[1][0] = ('With %s' % who, prev[1][0])
                prev[1].append(('Without %s' % who, steps))
            else:                          # a follow-on message of the same scene
                prev[1][-1] = (prev[1][-1][0], prev[1][-1][1] + steps) if isinstance(
                    prev[1][-1], tuple) else prev[1][-1] + steps
            continue
        groups.append((sub, [steps], base))
    if not out:                            # not drafted yet: the YAML's own beats, in place
        for ev in chap.get('events') or []:
            if isinstance(ev, dict) and ev.get('description'):
                out.setdefault(script_section(ev.get('trigger'), ev.get('type')), []).append(
                    (None, [ev['description'].strip()], None))
    for section, groups in out.items():
        groups = [g[:2] for g in groups]
        if len(groups) == 1 and section not in ('Battle quotes', 'Talk conversations'):
            groups = [(None, groups[0][1])]
        out[section] = groups
    return out


def script_wikitext(chap, prev, nxt, units, navbox=''):
    sections = script_sections(chap, units)
    if not sections:
        return ''
    return wp.script({'title': chap.get('title', chap['_slug']), 'sections': sections,
                      'previous': prev.get('title') if prev else None,
                      'next': nxt.get('title') if nxt else None, 'navbox': navbox})


# ── what the ROM shows: names, icons, sprites ──────────────────────────────────

_CAMPAIGN_YAML = None


def campaign_yaml():
    global _CAMPAIGN_YAML
    if _CAMPAIGN_YAML is None:
        _CAMPAIGN_YAML = load_yaml(os.path.join(CAMP, 'campaign.yaml'))
    return _CAMPAIGN_YAML


def rom_item_name(enum, fallback=''):
    """What the game calls an item: FE8 keeps ONE name per item id, so a campaign rename
    (`item_names:`) or else vanilla's. Per-unit flavour names never reach the ROM."""
    if not enum:
        return fallback
    return (campaign_yaml().get('item_names') or {}).get(enum) or item_name(enum) or fallback


def item_html(enum, fallback=''):
    shown = rom_item_name(enum, fallback)
    icon = art.item_icon(enum)
    return '%s&#160;%s' % (mk.file_img(icon, 16, 16), mk.fe(item_name(enum) or shown, shown))


def class_html(token, italic=False):
    """A class cell: the game's name for it, linked to the wiki's class article."""
    name = class_display_name(token)
    return mk.fe(name)


def class_enum_of(token):
    return difficulty._enemy_class_enum(token)


# ── what the ROM loads, per difficulty mode ────────────────────────────────────

MODE_LABELS = (('tutorial', 'Easy'), ('normal', 'Normal'), ('difficult', 'Difficult'))
STAT_KEYS = ('HP', 'Pow', 'Skl', 'Spd', 'Lck', 'Def', 'Res', 'Con', 'Mov')


def chapter_shifts(chap):
    try:
        return inject.chapter_settings.chapter_difficulty_shifts(chap)
    except BaseException:                              # planned: no `difficulty:` block yet
        return None


def personal_of(ed):
    personal = ed.get('personal')
    if not personal:
        uid = ed.get('id')
        donor = inject.stats.BASE_DONOR.get(uid) or inject.cast.ENEMY_BASE_SLOT.get(uid)
        personal = difficulty.vanilla_personal_line(donor) if donor else None
    return personal


def loaded(ed, token, level, shifts, mode):
    return unit_load.load(class_enum_of(token), int(level), personal=personal_of(ed),
                          autolevel=bool(ed.get('autolevel')),
                          base_level=difficulty._our_base_level(dict(ed, level=level)),
                          shiftable=difficulty._our_takes_difficulty_shift(ed),
                          shifts=shifts, mode=mode)


def bodies(ed):
    """(class token, level, inventory refs, count) groups one entry places, the wiki's '#'."""
    if 'composition' in ed and 'class' not in ed:
        by = ed.get('inventory_by_class') or {}
        groups = collections.Counter(zip(ed.get('composition') or [],
                                         inject.raw_pids.entry_body_levels(ed)))
        return [(c, lv, by.get(c) or [], n) for (c, lv), n in groups.items()]
    groups = collections.Counter(inject.raw_pids.entry_body_levels(ed))
    return [(ed.get('class'), lv, ed.get('inventory') or [], n) for lv, n in groups.items()]


AI_TEXT = {'statue': 'Does not move.', 'striker': 'Attacks units within range.',
           'own-errand': 'Pursues its own errand (loots or escapes).'}


# ── boss cards ─────────────────────────────────────────────────────────────────

_RANK_TYPES = (('sword', 'Sword', 'Swords'), ('lance', 'Lance', 'Lances'), ('axe', 'Axe', 'Axes'),
               ('bow', 'Bow', 'Bows'), ('magic_anima', 'Anima', 'Anima magic'),
               ('magic_light', 'Light (magic)', 'Light magic'), ('magic_dark', 'Dark', 'Dark magic'),
               ('staff', 'Staff', 'Staves'))
_ITYPE = {'sword': 'ITYPE_SWORD', 'lance': 'ITYPE_LANCE', 'axe': 'ITYPE_AXE', 'bow': 'ITYPE_BOW',
          'magic_anima': 'ITYPE_ANIMA', 'magic_light': 'ITYPE_LIGHT', 'magic_dark': 'ITYPE_DARK',
          'staff': 'ITYPE_STAFF'}


@functools.lru_cache(maxsize=None)
def _rank_thresholds():
    """{rank letter: weapon exp}, from the decomp's own enum (include/bmitem.h)."""
    text = inject.decomp.vanilla_decomp_text('include/bmitem.h')
    return {k: int(v) for k, v in re.findall(r'\bWPN_EXP_([SABCDE])\s*=\s*(\d+)', text)}


def _ranks(class_enum, donor):
    """{ITYPE: wexp}: the class's baseRanks, a named character's own over them."""
    out = {}
    blocks = [unit_load._class_block(class_enum)]
    if donor:
        try:
            text = inject.decomp.vanilla_decomp_text('src/data_characters.c')
            s, e = inject.decomp._find_brace_block(text, '[%s - 1]' % donor, 'data_characters.c')
            blocks.append(text[s:e])
        except Exception:
            pass
    for b in blocks:
        m = re.search(r'\.baseRanks\s*=\s*\{(.*?)\}', b, re.S)
        for t, v in re.findall(r'\[(ITYPE_\w+)\]\s*=\s*(\w+)', m.group(1) if m else ''):
            letter = re.match(r'WPN_EXP_([SABCDE])$', v)
            out[t] = _rank_thresholds()[letter.group(1)] if letter else int(v, 0)
    return out


def _letter(wexp):
    best = [l for l, t in sorted(_rank_thresholds().items(), key=lambda kv: -kv[1])
            if wexp and wexp >= t]
    return best[0] if best else ''


# ── page pieces ────────────────────────────────────────────────────────────────

ORDINALS = ('zeroth', 'first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth',
            'ninth', 'tenth', 'eleventh', 'twelfth', 'thirteenth', 'fourteenth', 'fifteenth',
            'sixteenth', 'seventeenth', 'eighteenth', 'nineteenth', 'twentieth')

WIN_TEXT = {'all_enemies_defeated': 'Defeat all enemies', 'seize': 'Seize the gate',
            'none': 'Survive', 'survive': 'Survive'}
LOSE_TEXT = {'lord_defeated': 'The chosen lord dies', 'hlin_defeated': 'Hlin dies',
             'timer_expires_scripted_defeat': 'Scripted (the chapter cannot be won)'}


def victory_text(chap):
    w = str(chap.get('win_condition') or '')
    if w in WIN_TEXT:
        return esc(WIN_TEXT[w])
    if w.endswith('_defeated'):
        boss = bosses_of(chap)
        return 'Defeat %s' % esc(boss[0].get('name') if boss else w[:-9].replace('_', ' ').title())
    return esc(w.replace(' (planned)', ''))


def defeat_text(chap):
    l = str(chap.get('lose_condition') or '')
    return esc(LOSE_TEXT.get(l) or l)


def talk_joins(chap):
    """{unit id: who talks them in, None for any party member} for every unit this chapter
    recruits by Talk, from what the build WIRES (#493): a gated parley (the chapter's
    `parley: {by, recruits_npc}`, inject.recruit.parley_recruiters) or an on-map talk any party
    member can make (inject.recruit.on_map_talk_recruits)."""
    import inject.recruit
    out = {}
    for e in enemy_list(chap):
        parley = e.get('parley') or {}
        if parley.get('recruits_npc') and parley.get('by'):
            out[parley['recruits_npc']] = parley['by']
    try:
        talkers = inject.recruit.on_map_talk_recruits(CAMPAIGN, chap.get('chapter_number'))
    except (Exception, SystemExit):
        talkers = []
    for t in talkers:
        out.setdefault(t[0], None)
    return out


def join_text(uid, units, chap):
    """How the unit joins, in the wiki's words: by Talk (`talk_joins`), else an off-map join at
    chapter end. The unit file's `recruit.via` is not the answer: nearly every recruit says
    `story`, and reading it printed "Automatically" for Trex, who has to be talked to."""
    if uid in (chap.get('_founding') or []):
        return 'Automatically from turn 1'
    talks = talk_joins(chap)
    if uid in talks:
        return ('Enemy, talk to with [[%s]]' % unit_name(talks[uid], units) if talks[uid]
                else 'NPC, talk to with any party member')
    return 'Automatically at the end of the chapter'


def available_before(chs, chap):
    out = []
    for c in chs:
        if c is chap:
            break
        out += [r for r in recruits_of(c) if r not in out]
    return out


# ── wikitext pages through the Fire Emblem Wiki's templates (#493) ───────────────

def sprite_frame(chap, token, faction='enemy', uid=None):
    """The map sprite a unit wears in this chapter (PIL), trimmed as the wiki's sprites are."""
    sprite = unit_art.unit_sprite(CAMPAIGN, chap['_slug'], uid=uid, token=token)
    try:
        frame = (unit_art.idle_frame(CAMPAIGN, sprite, faction) if sprite
                 else unit_art.class_sprite(class_enum_of(token), faction))
    except Exception:
        frame = None
    return _trimmed(frame)


def _trimmed(frame):
    """A sprite frame cropped to its top row of ink, index 0 transparent, as the wiki's are."""
    if frame is None:
        return None
    box = frame.point(lambda i: 255 if i else 0).getbbox()
    if box:
        frame = frame.crop((0, box[1], frame.width, frame.height))
    frame.info['transparency'] = 0
    return frame


class WikiFiles(wsite.Files):
    """Registers each image under the name the templates build for it. The weapon-rank and
    affinity icons are the ROM's own; the wiki's UI glyphs (the drop marker) are vendored."""

    RANKS = {'Sword': 'sword', 'Lance': 'lance', 'Axe': 'axe', 'Bow': 'bow',
             'Anima': 'magic_anima', 'Light': 'magic_light', 'Dark': 'magic_dark',
             'Staff': 'staff'}
    AFFINITIES = ('anima', 'dark', 'fire', 'ice', 'light', 'thunder', 'wind')

    def __init__(self):
        super().__init__()
        for name, stem in self.RANKS.items():
            icon = art.named_icon('inventory_category_' + stem)
            if icon:
                self.add('GBARank%s.gif' % name, icon, 16, 16)
        for aff in self.AFFINITIES:
            icon = art.named_icon('affinity_' + aff)
            if icon:
                self.add('Is gba %saffin.png' % aff, icon, 16, 16)
        vendored = os.path.join(TOOLS, 'wiki', 'vendor', 'files')
        for fn in sorted(os.listdir(vendored)) if os.path.isdir(vendored) else ():
            from PIL import Image
            im = Image.open(os.path.join(vendored, fn))
            self.add(fn, png_uri(im), im.width, im.height)

    def portrait(self, uid):
        uri = portrait(uid)
        return self.add('Portrait %s ms.png' % uid, uri, 96, 80) if uri else None

    def minimug(self, uid):
        uri = minimug(uid)
        if uri:
            self.add('Small portrait %s fe08.png' % uid, uri, 32, 32)
        return uid

    def item(self, enum, shown):
        icon = art.item_icon(enum) if enum else None
        if icon:
            self.add('Is gba %s.png' % shown.lower(), icon, 16, 16)

    def sprite(self, name, frame):
        if frame is not None:
            self.add(name, png_uri(frame), frame.width, frame.height)


def wiki_item(it_or_enum, files, drop=False):
    """{{Item|8|...}} for a YAML item ref or an ITEM_ enum: the ROM's name, the vanilla article."""
    if isinstance(it_or_enum, str) and it_or_enum.startswith('ITEM_'):
        enum, fallback = it_or_enum, ''
    else:
        fallback, enum = our_item(it_or_enum)
    shown = rom_item_name(enum, fallback)
    files.item(enum, shown)
    article = item_name(enum) if enum else None
    return wp.item(shown, link=article if article and article != shown else None, drop=drop)


@functools.lru_cache(maxsize=None)
def _reskin_bases():
    import inject.reskins
    return {rk['id']: rk['base'] for rk in inject.reskins.enemy_class_reskins(CAMPAIGN)}


def wiki_class(token):
    """(the name the ROM shows, None): a reskin clones its base class whole, name included, so a
    goblin soldier's unit window says Soldier, and Soldier is the article it links to."""
    base = _reskin_bases().get(str(token).lower())
    if base:
        token = base[len('CLASS_'):].lower().replace('_', '-')
    return class_display_name(token), None


def wiki_unit_row(chap, ed, token, level, inv, n, shifts, mode, files, kind='Enemy'):
    st = loaded(ed, token, level, shifts, mode)
    # A named unit shows its name (bosses, personal lines, a named green ally); a generic shows
    # its class, as the ROM's unit window does.
    named = (ed.get('is_boss') or ed.get('is_miniboss') or personal_of(ed)
             or (kind == 'NPC' and (ed.get('fe_name') or ed.get('name'))))
    cls, article = wiki_class(token)
    version = 'ms-%s-%s' % (chap['_slug'], ed.get('id') or token)
    utype = 'npc' if kind == 'NPC' else 'enemy'
    files.sprite('Ma gba %s %s %s.gif' % (cls.lower(), version, utype),
                 sprite_frame(chap, token, 'green' if kind == 'NPC' else 'enemy', ed.get('id')))
    drop = ed.get('item_drop')
    items = [wiki_item(i, files) for i in inv
             if not (isinstance(i, dict) and i.get('is_key_item'))]
    if drop:                       # the ROM carries the drop as the last item (units.py)
        items.append(wiki_item(drop, files, drop=True))
    show = lambda k: unit_load.show(st[k])               # noqa: E731
    return {'name': (ed.get('fe_name') or ed.get('name')) if named else cls,
            'class': cls, 'class_article': article, 'version': version,
            'type': 'npc' if kind == 'NPC' else None, 'lv': level, 'n': n,
            'hp': show('HP'), 'str': show('Pow'), 'skl': show('Skl'), 'spd': show('Spd'),
            'lck': show('Lck'), 'def': show('Def'), 'res': show('Res'), 'con': show('Con'),
            'mov': show('Mov'), 'inventory': items, 'notes': AI_TEXT.get(_ai_shape(chap, ed))}


def wiki_recruit_npc_row(chap, g, units, files):
    """A cast member standing green until recruited (Trex): the line his slot loads with,
    his unit file's class, level and kit -- what the NPC table shows for vanilla's Colm."""
    uid = g['id']
    fs = (units.get(uid) or {}).get('fe_stats') or {}
    token = fs.get('class')
    cls, article = wiki_class(token)
    version = 'ms-%s-%s' % (chap['_slug'], uid)
    files.sprite('Ma gba %s %s npc.gif' % (cls.lower(), version),
                 sprite_frame(chap, token, 'green', uid))
    cls_enum, line = inject.stats.cast_loaded_line(CAMPAIGN, uid)
    mov = difficulty._class_base(cls_enum).get('baseMov', '')
    return {'name': unit_name(uid, units), 'class': cls, 'class_article': article,
            'version': version, 'type': 'npc', 'lv': fs.get('level', '?'), 'n': 1,
            'hp': line['baseHP'], 'str': line['basePow'], 'skl': line['baseSkl'],
            'spd': line['baseSpd'], 'lck': line['baseLck'], 'def': line['baseDef'],
            'res': line['baseRes'], 'con': line['baseCon'], 'mov': mov,
            'inventory': [wiki_item(e, files) for e in inject.cast.unit_items(CAMPAIGN, uid)],
            'notes': 'Talk to recruit'}


def _ai_shape(chap, ed):
    try:
        import chapter_status
        return chapter_status.ai_shape(difficulty.enemy_ai_bytes(chap, ed, 0))
    except Exception:
        return None


def chapter_wikitext(chap, prev, nxt, units, chs, files, navbox=''):
    slug = chap['_slug']
    title = chap.get('title', slug)
    num = chap.get('chapter_number')
    plan = chap.get('plan') or {}
    shifts = chapter_shifts(chap)
    modes = MODE_LABELS if shifts else (('normal', 'Normal'),)
    recs = recruits_of(chap)
    img, cap = map_image(chap)
    m = re.search(r'\((\d+)x(\d+)\)', cap or '')
    cols, rows = (m.groups() if m else (None, None))
    if img:
        files.add('MS map %s.png' % slug, img, int(cols or 0) * 16, int(rows or 0) * 16)
    c = {'title': title, 'location': chap.get('location'),
         'image': '[[File:MS map %s.png|200px]]' % slug if img else None,
         'map': '[[File:MS map %s.png]]' % slug if img else None, 'cols': cols, 'rows': rows,
         'new_units': [unit_name(r, units) for r in recs],
         'bosses': [b.get('name') for b in bosses_of(chap)] or
                   ([plan['boss']] if plan.get('boss') else []),
         'previous': prev.get('title') if prev else None,
         'next': nxt.get('title') if nxt else None,
         'lead': 'the %s of \'\'Manchego Stars\'\'' % (
             'prologue' if chap.get('is_prologue') else
             '%s chapter' % ORDINALS[num] if isinstance(num, int) and num < len(ORDINALS)
             else 'chapter %s' % num),
         'plot': chap.get('narrative') or plan.get('story'),
         'script_title': '%s/Script' % title if script_sections(chap, units) else None,
         'victory': victory_text(chap), 'defeat': defeat_text(chap), 'navbox': navbox}
    dep = chap.get('deployment') or {}
    c['ally'] = str(dep.get('deploy_limit') or len(dep.get('deploy_slots') or []) or '?')
    start = sum(n for ed in enemy_list(chap) if not ed.get('arrives_turn')
                for _t, _l, _i, n in bodies(ed))
    reinf = sum(n for ed in enemy_list(chap) if ed.get('arrives_turn')
                for _t, _l, _i, n in bodies(ed))
    c['enemy'] = '%d%s' % (start, wp.hover('+%d' % reinf, 'Reinforcements') if reinf else '')
    greens = list(dep.get('green_allies') or [])
    green_entries = [e for e in enemy_list(chap) if e.get('faction') == 'green']
    joiners = [g for g in greens if g['id'] in units]           # green until recruited
    if greens or green_entries:
        n_green = len(greens) + sum(n for e in green_entries for _t, _l, _i, n in bodies(e))
        c['other'] = str(n_green) + ''.join(
            wp.hover('\u22121', 'Upon %s being recruited' % unit_name(g['id'], units))
            for g in joiners)
        c['ally'] += ''.join(wp.hover('+1', 'Upon %s being recruited' % unit_name(g['id'], units))
                             for g in joiners)

    cards = []
    for pu in chap.get('player_units') or []:
        cls_enum = class_enum_of(pu.get('class'))
        hp = (difficulty._class_base(cls_enum).get('baseHP', 0)
              + inject.stats.guest_personal_line(pu, cls_enum).get('baseHP', 0))
        name, article = wiki_class(pu.get('class'))
        port = files.portrait(pu['id'])
        cards.append({'name': pu.get('name') or unit_name(pu['id'], units),
                      'portrait': '[[File:%s]]' % port if port else '', 'class': name,
                      'class_article': article, 'hp': hp, 'lv': pu.get('level', 1),
                      'inventory': [wiki_item(i, files) for i in pu.get('inventory') or []],
                      'how': 'Automatically from turn 1'})
    for r in recs:
        unit = units.get(r) or {}
        fs = unit.get('fe_stats') or {}
        try:
            hp = difficulty.player_combatant(CAMPAIGN, r).hp
            kit = [wiki_item(e, files) for e in inject.cast.unit_items(CAMPAIGN, r)]
        except (Exception, SystemExit):
            hp, kit = fs.get('HP', '?'), []
        name, article = wiki_class(fs.get('class'))
        port = files.portrait(r)
        cards.append({'name': unit_name(r, units), 'portrait': '[[File:%s]]' % port if port
                      else '', 'class': name, 'class_article': article, 'hp': hp,
                      'lv': fs.get('level', '?'), 'inventory': kit,
                      'how': join_text(r, units, chap)})
    c['new_unit_cards'] = cards
    c['available'] = [{'image_key': files.minimug(u), 'page': unit_name(u, units),
                       'name': unit_name(u, units)} for u in available_before(chs, chap)]

    c['items'] = []
    rows_ = item_rows(chap)
    for (name, enum, _v), how in zip(rows_, obtain_phrases(rows_, cols, rows)):
        if enum:
            shown = rom_item_name(enum, name)
            files.item(enum, shown)
            article = item_name(enum)
            c['items'].append((shown, how, {'article': article} if article != shown else None))
        elif name.endswith(' gold'):
            amount = int(name.split()[0])
            c['items'].append(('{:,}G'.format(amount), how,
                               {'image': 'gold', 'article': 'Gold'}))
        else:
            c['items'].append((name, how, None))

    shops = []
    data_items = inject.decomp.vanilla_decomp_text('src/data_items.c')
    shoplists = inject.decomp.vanilla_decomp_text('src/events_shoplist.c')
    for macro, sym, _x, _y in inject.villages.chapter_shops(chap):
        stock = []
        for enum in difficulty._shoplist_items(shoplists, sym):
            blk = re.search(r'\[%s\]\s*=\s*\{(.*?)\n\s*\},' % re.escape(enum), data_items, re.S)
            uses = re.search(r'\.maxUses\s*=\s*(\d+)', blk.group(1)) if blk else None
            per = re.search(r'\.costPerUse\s*=\s*(\d+)', blk.group(1)) if blk else None
            cost = int(per.group(1)) * max(int(uses.group(1)) if uses else 1, 1) if per else ''
            shown = rom_item_name(enum)
            files.item(enum, shown)
            stock.append((shown, cost))
        shops.append((macro, stock))
    c['shops'] = shops

    entries = enemy_list(chap)
    enemy_tabs, npcs = [], []
    for mode, label in modes:
        rows_ = [wiki_unit_row(chap, ed, t, lv, inv, n, shifts, mode, files)
                 for ed in entries if ed.get('faction') != 'green'
                 for t, lv, inv, n in bodies(ed)]
        if rows_:
            enemy_tabs.append((label, rows_))
    c['enemy_tabs'] = enemy_tabs
    c['enemy_default'] = str([m for m, _ in modes].index('normal') + 1) if len(modes) > 1 else None
    for g in greens:
        if g['id'] in units:
            npcs.append(wiki_recruit_npc_row(chap, g, units, files))
        else:
            for t, lv, inv, n in bodies(g):
                npcs.append(wiki_unit_row(chap, g, t, lv, inv, n, shifts, 'normal', files, 'NPC'))
    for ed in green_entries:
        for t, lv, inv, n in bodies(ed):
            npcs.append(wiki_unit_row(chap, ed, t, lv, inv, n, shifts, 'normal', files, 'NPC'))
    c['npcs'] = npcs

    waves = collections.OrderedDict()           # turn -> {(who, weapon): count}
    for ed in sorted((e for e in entries if e.get('arrives_turn')),
                     key=lambda e: int(e['arrives_turn'])):
        for token, lv, inv, n in bodies(ed):
            cls, _a = wiki_class(token)
            who = ed.get('name') if ed.get('is_boss') else cls
            weapon = next((our_item(i)[1] for i in inv), None)
            turn = waves.setdefault(int(ed['arrives_turn']), collections.OrderedDict())
            turn[(who, weapon, bool(ed.get('is_boss')))] = \
                turn.get((who, weapon, bool(ed.get('is_boss'))), 0) + n
    for turn, groups in waves.items():
        lines = []
        for (who, weapon, boss), n in groups.items():
            what = who if boss else '%d [[%s]]%s' % (n, who, 's' if n > 1 else '')
            if weapon:
                what += ' with %s' % wiki_item(weapon, files)
            lines.append(what)
        waves[turn] = lines
    c['reinforcements'] = list(waves.items())

    c['bosses_data'] = [{'page': ed.get('name'), 'modes': boss_modes(chap, ed, files, shifts, modes)}
                        for ed in bosses_of(chap)]

    c['strategy'] = chap.get('strategy')
    return wp.chapter(c)


RANK_PARAMS = (('sw', 'sword'), ('la', 'lance'), ('ax', 'axe'), ('bo', 'bow'),
               ('an', 'magic_anima'), ('li', 'magic_light'), ('da', 'magic_dark'), ('st', 'staff'))
MAGIC_ITYPES = ('ITYPE_ANIMA', 'ITYPE_LIGHT', 'ITYPE_DARK', 'ITYPE_STAFF')


def rank_params(ranks):
    """{template rank key: letter} from {ITYPE: wexp}, as the stats templates take them."""
    return {k: _letter(ranks.get(_ITYPE[t])) or None for k, t in RANK_PARAMS}


def aid_of(cls_enum, con):
    """FE8's GetUnitAid: con - 1 on foot; 25 - con mounted (20 - con for a female mount)."""
    attrs = unit_load._class_block(cls_enum)
    return (con - 1 if 'CA_MOUNTEDAID' not in attrs else
            (20 - con if 'CA_FEMALE' in attrs else 25 - con))


def boss_modes(chap, ed, files, shifts=None, modes=None):
    """[(difficulty label, {{BossStats GBA}} data)] for one boss as the ROM loads it, one per
    difficulty, folded to ('All', ...) when no difficulty moves it. The chapter page's Boss
    data and the boss's own page both read this."""
    if shifts is None:
        shifts = chapter_shifts(chap)
        modes = MODE_LABELS if shifts else (('normal', 'Normal'),)
    token, lv = ed.get('class'), int(ed.get('level', 1))
    cls_enum = class_enum_of(token)
    cls, article = wiki_class(token)
    donor = (inject.stats.BASE_DONOR.get(ed.get('id'))
             or inject.cast.ENEMY_BASE_SLOT.get(ed.get('id')))
    ranks = _ranks(cls_enum, donor)
    port = files.portrait(ed['face']) if ed.get('face') else None
    sprite_key = 'ms %s' % ed.get('id')
    files.sprite('Ma gba %s.gif' % sprite_key, sprite_frame(chap, token, uid=ed.get('id')))
    inv = [wiki_item(i, files) for i in ed.get('inventory') or []]
    magic = cls_enum and any(t in ranks for t in MAGIC_ITYPES)
    per_mode = []
    for mode, label in modes:
        st = loaded(ed, token, lv, shifts, mode)
        show = lambda k: unit_load.show(st[k])           # noqa: E731
        per_mode.append((label, {
            'portrait': '[[File:%s]]' % port if port else None, 'sprite': sprite_key,
            'class': cls, 'class_article': article, 'lv': lv,
            'affinity': str(ed['affinity']).capitalize() if ed.get('affinity') else None,
            'hp': show('HP'),
            'str': None if magic else show('Pow'), 'mag': show('Pow') if magic else None,
            'skl': show('Skl'), 'spd': show('Spd'), 'lck': show('Lck'), 'def': show('Def'),
            'res': show('Res'), 'con': show('Con'), 'mov': show('Mov'),
            'aid': aid_of(cls_enum, st['Con'][0]), 'inventory': inv,
            'ranks': rank_params(ranks)}))
    if len({repr(s) for _, s in per_mode}) == 1:
        per_mode = [('All', per_mode[0][1])]
    return per_mode


# ── character pages ────────────────────────────────────────────────────────────

def chapter_link(chap):
    """[[Title|Chapter&nbsp;N]], as the wiki names a chapter in running text."""
    num = chap.get('chapter_number')
    label = 'Prologue' if chap.get('is_prologue') else 'Chapter&nbsp;%s' % num
    return '[[%s|%s]]' % (chap.get('title', chap['_slug']), label)


def promotions(cls_enum):
    """{{PromotionGains}} columns for every class FE8 lets `cls_enum` promote into
    (gPromoJidLut, both branches): the promoted class's promotion bonuses, and the CON/MOV
    its base adds over the unpromoted one."""
    src = unit_load._class_block(cls_enum)
    out = []
    for target in inject.sms.promotion_branches().get(cls_enum) or []:
        b = unit_load._class_block(target)
        f = unit_load._field
        out.append({'class': '[[%s]]' % class_display_name(
                        target[len('CLASS_'):].lower().replace('_', '-')),
                    'hp': f(b, 'promotionHp'), 'str': f(b, 'promotionPow'),
                    'skill': f(b, 'promotionSkl'), 'spd': f(b, 'promotionSpd'),
                    'def': f(b, 'promotionDef'), 'res': f(b, 'promotionRes'),
                    'con': f(b, 'baseCon') - f(src, 'baseCon'),
                    'move': f(b, 'baseMov') - f(src, 'baseMov'),
                    'weaponlvl': _promotion_wexp(cls_enum, target)})
    return out


RANK_TEMPLATE = (('ITYPE_SWORD', 'SwordGBA'), ('ITYPE_LANCE', 'LanceGBA'),
                 ('ITYPE_AXE', 'AxeGBA'), ('ITYPE_BOW', 'BowGBA'), ('ITYPE_STAFF', 'StaffGBA'),
                 ('ITYPE_ANIMA', 'AnimaGBA'), ('ITYPE_LIGHT', 'LightGBA'),
                 ('ITYPE_DARK', 'DarkGBA'))


def _promotion_wexp(src, target):
    """The weapon experience promoting adds, as PromotionGains writes it ("{{SwordGBA}} +30",
    "--" for none): FE8's ApplyUnitPromotion takes the old class's base ranks off and puts the
    new class's on, so each type gains the difference."""
    old, new = _ranks(src, None), _ranks(target, None)
    gains = ['{{%s}} +%d' % (tpl, new.get(t, 0) - old.get(t, 0)) for t, tpl in RANK_TEMPLATE
             if new.get(t, 0) - old.get(t, 0) > 0]
    return ' '.join(gains) or '--'


def _quotes(chap, boss_name, units):
    """(battle quote, death quote) a boss says, from the chapter's own scenes; a chapter that
    keeps them on the boss's entry instead (`taunt:`, `death_quote:`) is read by `boss_page`."""
    got = {}
    for trigger, _ref, _title, scenes in _scenes().get(chap['_slug'], []):
        if trigger in ('boss_battle', 'boss_death'):
            lines = [t for k, w, t in _script_steps(scenes, units) if k == 'say' and w == boss_name]
            if lines:
                got.setdefault(trigger, ' '.join(lines))
    return got.get('boss_battle'), got.get('boss_death')


def _join_lines(uid, name, chap, units):
    """(CharStats `recruit`, Role sentence) for how `uid` joins in `chap`, from the build's
    wiring (`talk_joins`), worded as Colm's page words his: "Chapter 3, talk to with Neimi"."""
    if chap is None:
        return None, None
    where = chapter_link(chap)
    if uid in (chap.get('_founding') or []):
        return ('%s, automatically from turn 1' % where,
                '%s is one of the founding party, fielded from %s.' % (name, where))
    talks = talk_joins(chap)
    if uid in talks:
        by = '[[%s]]' % unit_name(talks[uid], units) if talks[uid] else 'any party member'
        side = 'an enemy' if talks[uid] else 'a green unit'
        return ('%s, talk to with %s' % (where, by),
                '%s appears in %s as %s, and joins when %s talks to %s.'
                % (name, where, side, by, name))
    return ('%s, automatically at the end of the chapter' % where,
            '%s joins at the end of %s.' % (name, where))


HD_ART = os.path.join(ROOT, 'references', 'References', 'PCs', 'HD Art')
SHEETS = os.path.join(ROOT, 'data', 'pc-sheets')
# A vanilla character whose wiki article is not their bare name.
WIKI_ARTICLE = {'Garcia': 'Garcia (The Sacred Stones)'}


def jpeg_uri(img, longest=640):
    """Artwork as a JPEG data URI, scaled so its longest side is `longest`: the HD sources
    are megabytes each and the published page has a size cap."""
    img = img.convert('RGB')
    img.thumbnail((longest, longest))
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode(), img.size


def hd_art(uid, units):
    """The unit's HD artwork in References/PCs/HD Art (`<Name>HD.<ext>`), as a PIL image."""
    if not os.path.isdir(HD_ART):
        return None
    keys = {uid.replace('-', ''), re.sub(r'\W', '', unit_name(uid, units).split()[0]).lower()}
    for fn in sorted(os.listdir(HD_ART)):
        stem = os.path.splitext(fn)[0].lower()
        if stem.endswith('hd') and stem[:-2] in keys:
            from PIL import Image
            return Image.open(os.path.join(HD_ART, fn))
    return None


def dnd_sheet(name):
    """The unit's D&D Beyond sheet (data/pc-sheets), matched by name, or None."""
    for path in glob.glob(os.path.join(SHEETS, '*.json')):
        import json
        with open(path, encoding='utf-8') as f:
            d = json.load(f)
        if isinstance(d, dict) and d.get('name') == name:
            return d
    return None


def _wiki_link(vanilla_name):
    art = WIKI_ARTICLE.get(vanilla_name)
    return '[[%s|%s]]' % (art, vanilla_name) if art else '[[%s]]' % vanilla_name


def cast_trivia(uid, name):
    """Trivia from the record: the D&D character the unit was, and the vanilla units whose
    data the slot carries (inject.stats' donors, by what each one supplies)."""
    out = []
    sheet = dnd_sheet(name)
    if sheet:
        race = sheet.get('race') or ''
        if sheet.get('race_homebrew') and sheet.get('race_base') not in (None, race):
            race = '%s (a homebrew %s)' % (race, sheet['race_base'])
        cls = sheet.get('class') or ''
        if sheet.get('subclass'):
            cls = '%s (%s)' % (cls, sheet['subclass'])
        out.append("In the original ''Rime of the Frostmaiden'' campaign, %s was a level %s "
                   "%s %s." % (name, sheet.get('level'), race, cls))
    roles = (('base stats', inject.stats.BASE_DONOR), ('growth rates', inject.stats.GROWTH_DONOR),
             ('weapon ranks', inject.stats.STAT_DONOR))
    by = collections.OrderedDict()
    for what, table in roles:
        if uid in table:
            by.setdefault(table[uid][len('CHARACTER_'):].capitalize(), []).append(what)
    if by:
        parts = ['%s are built on %s\'s' % (' and '.join(w), _wiki_link(d)) if 'base stats' in w
                 and len(w) == 1 else '%s are %s\'s' % (', '.join(w[:-1]) + (' and ' if len(w) > 1
                 else '') + w[-1], _wiki_link(d)) for d, w in by.items()]
        out.append("%s's %s." % (name, '; '.join(parts)))
    return out


LORE = os.path.join(CAMP, 'lore')


@functools.lru_cache(maxsize=None)
def lore_profiles():
    """{lore file stem: (name, Profile prose)} for every lore file with a `## Profile` -- the one
    section of a character's lore written to be read as-is (lore/README.md)."""
    out = {}
    for path in sorted(glob.glob(os.path.join(LORE, '*.md'))):
        with open(path, encoding='utf-8') as f:
            text = f.read()
        m = re.search(r'^## Profile\n(.*?)(?=^## |\Z)', text, re.S | re.M)
        if not m:
            continue
        name = re.match(r'# (.+?)(?: — |$)', text).group(1).strip()
        paras = [' '.join(p.split()) for p in m.group(1).strip().split('\n\n')]
        out[os.path.splitext(os.path.basename(path))[0]] = (name, '\n\n'.join(paras))
    return out


def lore_for(uid, name):
    """The lore stem that is `uid`'s: its own id, else its name ("Izobai" -> izobai)."""
    profiles = lore_profiles()
    for key in (uid, re.sub(r'[^a-z0-9]+', '-', (name or '').lower()).strip('-'),
                (name or '').split()[0].lower() if name else None):
        if key in profiles:
            return key
    return None


def first_appearance(name, chs, units):
    """The first chapter whose scenes give `name` a line, or None. A script may name a speaker
    by first name alone ("Hlin")."""
    names = {name, name.split()[0]}
    for c in chs:
        for _t, _r, _title, scenes in _scenes().get(c['_slug'], []):
            if any(k == 'say' and w in names for k, w, _x in _script_steps(scenes, units)):
                return c
    return None


def face_key(stem, name):
    """The portrait key a lore character's face is registered under: its stem, else its first
    name (the guest faces are keyed `duvessa`, `vellynne`)."""
    faces = dict(inject.cast.PORTRAIT_MAP, **inject.cast.GUEST_PORTRAIT_MAP)
    first = name.split()[0].lower()
    return stem if stem in faces else first if first in faces else stem


def cast_page(uid, units, chs, files):
    """A cast member's page, as `Colm`'s: the line, growths, ranks and kit the slot loads with
    (inject.stats, the injector's own answers), how the build wires the join, its death quote."""
    import inject.text
    unit = units.get(uid) or {}
    name = unit_name(uid, units)
    cls_enum, line = inject.stats.cast_loaded_line(CAMPAIGN, uid)
    fs = unit.get('fe_stats') or {}
    cls, _article = wiki_class(fs.get('class'))
    joins = next((c for c in chs if uid in recruits_of(c)), None)
    port = files.portrait(uid)
    sprite = 'ms %s' % uid
    if joins:
        files.sprite('Ma gba %s playable.gif' % sprite,
                     sprite_frame(joins, fs.get('class'), 'player', uid))
    g = inject.stats.cast_growths(uid)
    ranks = _ranks(cls_enum, inject.stats.STAT_DONOR.get(uid))
    recruit, role = _join_lines(uid, name, joins, units)
    help_text = inject.text.slot_help_text(inject.cast.PORTRAIT_MAP[uid])
    race = (unit.get('dnd') or {}).get('race')
    art = hd_art(uid, units)
    artwork = None
    if art is not None:
        uri, (w, h) = jpeg_uri(art)
        artwork = files.add('MS art %s.jpg' % uid, uri, w, h)
    sprites = [(cls, 'Ma gba %s playable.gif' % sprite if joins else None)]
    for target in inject.sms.promotion_branches().get(cls_enum) or []:
        name_t = class_display_name(target[len('CLASS_'):].lower().replace('_', '-'))
        key = 'Ma gba ms %s playable.gif' % name_t.lower()
        files.sprite(key, _trimmed(unit_art.class_sprite(target, 'player')))
        sprites.append((name_t, key))
    image = ('[[File:%s|200px]]' % artwork if artwork else
             '[[File:%s|class=pixel-art]]' % port if port else None)
    return wp.character({
        'name': name, 'image': image,
        'caption': ("Artwork of %s." % name if artwork else
                    "%s's portrait from ''Manchego Stars''." % name if port else None),
        'trivia': cast_trivia(uid, name),
        'personality': (lore_profiles().get(lore_for(uid, name)) or (None, None))[1],
        'gallery': {'portrait': port, 'minimug': files.minimug(uid) and
                    'Small portrait %s fe08.png' % uid, 'sprites': sprites,
                    'artwork': [(artwork, 'Artwork of %s.' % name)] if artwork else []},
        'help_text': help_text, 'gender': str(unit.get('gender', '')).capitalize() or None,
        'race': race, 'startingclass': '[[%s]]' % cls,
        'lead': 'a playable [[%s]] in \'\'Manchego Stars\'\'%s' % (
            cls.lower(), '. %s first appears in %s' % (name, chapter_link(joins)) if joins
            else ''),
        'role': role,
        'char_stats': {
            'portrait': '[[File:%s]]' % port if port else None, 'sprite': sprite,
            'class': cls, 'affinity': inject.stats.CAST_AFFINITY[len('UNIT_AFFIN_'):].lower(),
            'lv': fs.get('level', 1), 'hp': line['baseHP'], 'str': line['basePow'],
            'skl': line['baseSkl'], 'spd': line['baseSpd'], 'lck': line['baseLck'],
            'def': line['baseDef'], 'res': line['baseRes'], 'con': line['baseCon'],
            'mov': difficulty._class_base(cls_enum).get('baseMov', ''),
            'aid': aid_of(cls_enum, line['baseCon']),
            'magic': any(t in ranks for t in MAGIC_ITYPES),
            'inventory': [wiki_item(e, files) for e in inject.cast.unit_items(CAMPAIGN, uid)],
            'ranks': rank_params(ranks),
            'growths': {'hp': g['growthHP'], 'str': g['growthPow'], 'skl': g['growthSkl'],
                        'spd': g['growthSpd'], 'lck': g['growthLck'], 'def': g['growthDef'],
                        'res': g['growthRes']},
            'recruit': recruit},
        'promotions': promotions(cls_enum),
        'death_quote': (unit['death_quote'], "%s's death quote in ''Manchego Stars''." % name)
                       if unit.get('death_quote') else None})


def boss_page(chap, ed, units, files):
    """A boss's page, as `Bazba`'s: the chapter it leads, its stats per difficulty (the
    chapter page's own Boss data), and its quotes from the chapter's scenes."""
    name = ed.get('name')
    cls, _article = wiki_class(ed.get('class'))
    port = files.portrait(ed['face']) if ed.get('face') else None
    battle, death = _quotes(chap, name, units)
    battle, death = battle or ed.get('taunt'), death or ed.get('death_quote')
    title = chap.get('title', chap['_slug'])
    return wp.character({
        'name': name, 'image': '[[File:%s|class=pixel-art]]' % port if port else None,
        'caption': "%s's portrait from ''Manchego Stars''." % name if port else None,
        'startingclass': '[[%s]]' % cls,
        'quote': (battle, name) if battle else None,
        'lead': 'a [[boss]] appearing in \'\'Manchego Stars\'\'',
        'role': '%s appears as the [[boss]] of %s.' % (name, chapter_link(chap)),
        'chapter': title, 'boss_modes': boss_modes(chap, ed, files),
        'personality': (lore_profiles().get(lore_for(ed.get('id'), name)) or (None, None))[1],
        'battle_quotes': [(battle, "%s, in %s." % (name, chapter_link(chap)))] if battle else [],
        'death_quote': (death, "%s's death quote." % name) if death else None})


def planned_page(uid, units, chs, files):
    """A recruit with a class but no slot yet (a planned chapter's joiner): what is decided
    -- its class and where it joins -- and nothing the build cannot answer yet."""
    unit = units.get(uid) or {}
    name = unit_name(uid, units)
    cls, _article = wiki_class((unit.get('fe_stats') or {}).get('class'))
    joins = next((c for c in chs if uid in recruits_of(c)), None)
    port = files.portrait(uid)
    role = '%s joins in %s.' % (name, chapter_link(joins)) if joins else None   # not wired yet
    return wp.character({
        'name': name, 'image': '[[File:%s|class=pixel-art]]' % port if port else None,
        'startingclass': '[[%s]]' % cls,
        'lead': 'a playable [[%s]] planned for \'\'Manchego Stars\'\'' % cls.lower(),
        'role': role})


def npc_page(stem, chs, units, files):
    """A named character who neither joins nor is fought, as `Dara`'s page: the lore's Profile."""
    name, profile = lore_profiles()[stem]
    port = files.portrait(face_key(stem, name))
    first = first_appearance(name, chs, units)
    return wp.character({
        'name': name, 'image': '[[File:%s|class=pixel-art]]' % port if port else None,
        'caption': "%s's portrait from ''Manchego Stars''." % name if port else None,
        'lead': 'a non-playable character in \'\'Manchego Stars\'\'',
        'role': '%s first appears in %s.' % (name, chapter_link(first)) if first else None,
        'personality': profile})


def npc_stems(chs, units):
    """Lore characters with a Profile that no cast or boss page already covers."""
    taken = {lore_for(uid, unit_name(uid, units)) for uid in units}
    for c in chs:
        for ed in bosses_of(c):
            taken.add(lore_for(ed.get('id'), ed.get('name')))
    return [k for k in lore_profiles() if k not in taken]


def list_wikitext(chs, units, files):
    """The character list, from the same units, bosses and lore the character pages read."""
    def port(key):
        name = files.portrait(key)
        return '[[File:%s|64x64px]]' % name if name else 'N/A'

    def cls_link(token):
        return '[[%s]]' % wiki_class(token)[0]

    playable = []
    for uid, _slot, _cls, _ in inject.cast.classed_cast(CAMPAIGN):
        name = unit_name(uid, units)
        joins = next((c for c in chs if uid in recruits_of(c)), None)
        first = first_appearance(name, chs, units) or joins
        if joins and first and chs.index(first) > chs.index(joins):
            first = joins
        playable.append((port(uid), name, cls_link((units[uid].get('fe_stats') or {}).get('class')),
                         chapter_link(first) if first else '', chapter_link(joins) if joins else ''))
    bosses = []
    for c in chs:
        if c.get('status') == 'planned':
            continue
        for ed in bosses_of(c):
            if not ed.get('name'):
                continue
            first = first_appearance(ed['name'], chs, units) or c
            if chs.index(first) > chs.index(c):
                first = c
            bosses.append((port(ed['face']) if ed.get('face') else 'N/A', ed['name'],
                           cls_link(ed.get('class')), chapter_link(first), chapter_link(c)))
    others = []
    for stem in npc_stems(chs, units):
        name, profile = lore_profiles()[stem]
        others.append((port(face_key(stem, name)), name, re.split(r'(?<=\.)\s', profile, 1)[0]))
    return wp.character_list({'playable': playable, 'bosses': bosses, 'others': others})


def character_pages(chs, units, files):
    """[(page id, title, wikitext)]: every classed cast member, every planned recruit (a class,
    no slot yet), every hosted boss, then every other named character the lore profiles. A unit
    with no class (a map ballista) is no character."""
    import inject.cast
    classed = [uid for uid, _slot, _cls, _ in inject.cast.classed_cast(CAMPAIGN)]
    out = [('unit-%s' % uid, unit_name(uid, units), cast_page(uid, units, chs, files))
           for uid in classed]
    out += [('unit-%s' % uid, unit_name(uid, units), planned_page(uid, units, chs, files))
            for uid, u in sorted(units.items())
            if uid not in classed and (u.get('fe_stats') or {}).get('class')]
    for c in chs:
        if c.get('status') == 'planned':
            continue
        for ed in bosses_of(c):
            if ed.get('name'):
                out.append(('boss-%s' % ed.get('id'), ed['name'], boss_page(c, ed, units, files)))
    out += [('npc-%s' % stem, lore_profiles()[stem][0], npc_page(stem, chs, units, files))
            for stem in npc_stems(chs, units)]
    return out


def design_page(chap, opens):
    """Ours, not the wiki's: the plan the cloned article has no section for (#487)."""
    slug, title = chap['_slug'], chap.get('title', chap['_slug'])
    plan = chap.get('plan') or {}
    ckey = twin_key(chap.get('parity_reference'))
    parts = [mk.infobox('%s/Design notes' % title, '', [
        ('Status', esc('Planned' if chap.get('status') == 'planned' else
                       'Locked' if chap.get('balance_locked') else 'Active')),
        ('Curve twin', twin_label(chap.get('parity_reference'))),
        ('Map donor', twin_label(chap.get('fe8_base_map'))),
        ('Source', '<code>%s</code>' % esc(chap['_file'])),
    ])]
    if opens.get(slug):
        parts.append(mk.h(2, 'Open questions', '%s-design-open' % slug))
        parts.append(wikitable(['Question', 'Claude\'s pick'],
                               [(esc(q.get('q')), esc(q.get('pick', ''))) for q in opens[slug]]))
    prose = plan.get('how_it_plays') or chap.get('design_notes')
    if prose:
        parts.append(mk.h(2, 'How it plays', '%s-design-plays' % slug) + para(prose))
    if plan.get('joins_roles'):
        parts.append(mk.h(2, 'Recruit roles to fill', '%s-design-roles' % slug))
        parts.append(wikitable(['Vanilla role', 'Who (recruit pass)'],
                               [(esc(x), '<i>open</i>') for x in plan['joins_roles']]))
    if ckey:
        parts.append(mk.h(2, 'Vanilla twin payload (%s)' % VANILLA[ckey][1], '%s-design-twin' % slug))
        parts.append(twin_payload_html(chap, ckey))
    intro = chap.get('introduces') or plan.get('introduces')
    if intro:
        parts.append(mk.h(2, 'Introduces', '%s-design-intro' % slug))
        parts.append(wikitable(['Concept', 'How'], [(esc(i.get('concept') if isinstance(i, dict)
                     else i), esc((i.get('where') or i.get('coverage') or '') if isinstance(i, dict)
                     else '')) for i in intro]))
    if plan.get('sources'):
        parts.append('<p><small><b>Sources:</b> %s</small></p>' % esc('; '.join(plan['sources'])))
    return page('%s/design' % slug, '%s/Design notes' % title, ''.join(parts),
                tools=[(slug, 'Chapter')], category='Design notes')


def payload_verdicts(twin_items, ours_counts, deviations):
    """'delivered' / 'deviation' / 'missing' per twin item, COUNTED: a twin item handed out
    twice needs two of ours, so a set test would read the second copy as delivered."""
    left = collections.Counter(ours_counts)
    out = []
    for e in twin_items:
        if left[e] > 0:
            left[e] -= 1
            out.append('delivered')
        else:
            out.append('deviation' if e in deviations else 'missing')
    return out


def twin_payload_html(chap, ckey):
    v = vanilla_payload(ckey)
    if v['error']:
        return '<p><i>%s</i></p>' % esc(v['error'])
    ours_ = collections.Counter(e for _, e, _ in item_rows(chap) if e)
    deviations = {d.get('item'): d.get('why', '') for d in chap.get('payload_deviations') or []}
    payload = ([(e, 'Chest') for e in v['chests']] + [(e, 'Gift / village / scene')
               for e in v['gifts']] + [(e, 'Enemy drop') for e in v['drops']]
               + [(e, 'Steal from an enemy') for e in v['steals']]
               + [(e, 'Given to %s' % pretty_enum(c, 'CHARACTER_')) for c, e in v['grants']])
    rows = []
    for (e, how), verdict in zip(payload, payload_verdicts([e for e, _ in payload], ours_,
                                                          deviations)):
        mark = {'delivered': '<span style="color:var(--yes-checkmark-color)">delivered</span>',
                'missing': '<span style="color:var(--no-xmark-color)">not found in ours</span>'
                }.get(verdict) or 'recorded deviation: %s' % esc(deviations[e])
        rows.append((item_html(e), esc(how), '<code>%s</code>' % esc(e), mark))
    for g in v.get('gold_chests') or []:
        rows.append(('%s gold' % esc(g), 'Chest', '', ''))
    out = [wikitable(['Item', 'Vanilla vehicle', 'Enum', 'Ours'], rows)]
    rec = [(esc(pretty_enum(c, 'CHARACTER_')), class_html(k[len('CLASS_'):].lower()), esc(l),
            esc(how)) for c, k, l, how in v['recruits']]
    out.append('<p><b>Vanilla recruits</b> (decomp loads):</p>' + wikitable(
        ['Character', 'Class', 'Lv', 'How'], rec))
    if v['shops']:
        out.append('<p><b>Vanilla shops</b>:</p>' + wikitable(['Shop', 'Stock'], [(esc(
            s.replace('ShopList_Event_', '')), ', '.join(item_html(i) for i in items))
            for s, items in v['shops']]))
    vrows = collections.Counter((u['classIndex'][len('CLASS_'):].lower(), u['level'],
                                 tuple(u['items'])) for u in v['enemies'])
    out.append(mk.collapsible('Vanilla twin\'s red units (%d loads, decomp)' % len(v['enemies']),
                              wikitable(['Class', 'Lv', 'Items', '#'], [
                                  (class_html(c), esc(l), ' • '.join(item_html(i) for i in its),
                                   esc(n)) for (c, l, its), n in vrows.items()])))
    if (chap.get('plan') or {}).get('payload_notes'):
        out.append('<p><b>Where the twin\'s payload lands:</b></p>' +
                   para(chap['plan']['payload_notes']))
    out.append('<p><small>Read from <code>src/events/%s-event*.h</code> at HEAD. "Not found in '
               'ours" compares vanilla enums with the items this chapter\'s YAML resolves, '
               'counted: a twin item given twice needs two of ours.</small></p>' % esc(v['stem']))
    return ''.join(out)


def wikitable(headers, rows, cls='wikitable'):
    if not rows:
        return '<p><i>None.</i></p>'
    head = ''.join('<th>%s\n</th>' % esc(x) for x in headers)
    body = ''.join('<tr>%s</tr>' % ''.join('<td>%s\n</td>' % c for c in r) for r in rows)
    return '<table class="%s" style="margin: auto"><tbody><tr>%s</tr>%s</tbody></table>' % (
        cls, head, body)


def page(pid, title, body, tools=(), category=None):
    tools = [t for t in tools if t]
    return ('<section class="page" id="%s" data-title="%s" data-tools="%s" data-category="%s">'
            '<div class="mw-content-ltr mw-parser-output" lang="en" dir="ltr">%s</div></section>'
            % (esc(pid), esc(title), esc('|'.join('%s=%s' % t for t in tools)),
               esc(category or ''), body))


BASE_GAME = 'Fire Emblem: The Sacred Stones'


def home_page(chs, units):
    """The Fire Emblem Wiki's game page (its The Sacred Stones article), filled with ours:
    infobox, lead, Plot by act, Gameplay, Chapters, Characters. Acts and the gameplay notes
    come from campaign.yaml; everything else from the chapters and units."""
    camp = campaign_yaml()
    title = str(camp.get('title', 'Manchego Stars')).split(':')[0]
    built = [c for c in chs if c.get('status') != 'planned']
    pcs = [k for k, u in units.items() if u['_kind'] == 'pcs']
    recruits = [r for c in chs for r in recruits_of(c) if r not in pcs]
    box = mk.infobox(title, '', [
        ('Base game', '<i>%s</i>' % mk.fe(BASE_GAME)),
        ('Campaign', '<i>Rime of the Frostmaiden</i> (<i>Dungeons &amp; Dragons</i> 5th edition)'),
        ('Platform(s)', mk.fe('Game Boy Advance')),
        ('Built from', '<code>fireemblem8u</code> (the FE8 decompilation)'),
    ])
    lead = ('<p><i><b>%s</b></i> is a <i>%s</i> ROM hack for the %s, built from the game\'s '
            'decompilation. It turns a finished <i>Rime of the Frostmaiden</i> campaign into a '
            'tactics game: the %d player characters become units, and the campaign\'s story '
            'becomes %d chapters.\n</p>' % (esc(title), mk.fe(BASE_GAME, 'Fire Emblem: The Sacred '
            'Stones'), mk.fe('Game Boy Advance'), len(pcs), len(chs)))
    toc, parts = [], []
    acts = camp.get('acts') or {}
    plot = mk.main_article('chapters', 'List of chapters in %s' % title)
    toc.append((1, 'Plot', 'home-Plot'))
    for act in acts:
        members = [c for c in chs if str(c.get('act')) == str(act)]
        if not members:
            continue
        anchor = 'home-Act_%s' % act
        toc.append((2, 'Act %s' % act, anchor))
        body = para(acts[act]) + ''.join(
            para(c.get('narrative') or (c.get('plan') or {}).get('story')) for c in members)
        plot += mk.h(3, 'Act %s' % act, anchor) + body
    parts.append(mk.h(2, 'Plot', 'home-Plot') + plot)
    notes = camp.get('gameplay') or []
    if notes:
        toc.append((1, 'Gameplay', 'home-Gameplay'))
        body = ('<p>A turn-based strategy game on <i>%s</i>\'s own engine and rules. What plays '
                'differently:\n</p>' % mk.fe(BASE_GAME, 'The Sacred Stones'))
        for n in notes:
            anchor = 'home-%s' % re.sub(r'\W+', '_', n['title'])
            toc.append((2, n['title'], anchor))
            body += mk.h(3, n['title'], anchor) + para(n.get('text'))
        parts.append(mk.h(2, 'Gameplay', 'home-Gameplay') + body)
    toc.append((1, 'Chapters', 'home-Chapters'))
    parts.append(mk.h(2, 'Chapters', 'home-Chapters') + mk.main_article(
        'chapters', 'List of chapters in %s' % title) + '<p>A playthrough runs %d chapters, '
        'from the prologue to the finale; %d are built and %d are planned.\n</p>'
        % (len(chs), len(built), len(chs) - len(built)))
    toc.append((1, 'Characters', 'home-Characters'))
    parts.append(mk.h(2, 'Characters', 'home-Characters') + mk.main_article(
        'roster', 'List of characters in %s' % title) + '<p><i>%s</i> features %d playable '
        'characters: the %d player characters of the campaign, who found the company, and %d '
        'recruits who join along the way.\n</p>' % (esc(title), len(pcs) + len(recruits),
                                                     len(pcs), len(recruits)))
    return page('home', title, box + lead + mk.toc(toc, 'home') + ''.join(parts))


def index_page(chs):
    rows = []
    for c in chs:
        st = 'Planned' if c.get('status') == 'planned' else ('Locked' if c.get('balance_locked')
                                                           else 'Active')
        rows.append((mk.ours(c['_slug'], c['_slug']), mk.ours(c['_slug'], c.get('title')),
                     twin_label(c.get('parity_reference')), twin_label(c.get('fe8_base_map')),
                     esc(st)))
    return page('chapters', 'List of chapters in Manchego Stars', '<p>Every chapter of the '
                'campaign, built and planned. Each page is generated from the chapter\'s YAML and '
                'the FE8 decomp, so it is only as current as the last build.</p>' + wikitable(
                    ['Ch', 'Title', 'Curve twin', 'Map donor', 'Status'], rows))


def decisions_page(chs, opens):
    rows = []
    for c in chs:
        for q in opens.get(c['_slug'], []):
            rows.append((mk.ours('%s/design' % c['_slug'], c['_slug']), esc(q.get('q')),
                         esc(q.get('pick', ''))))
    return page('decisions', 'Open decisions', '<p>Every open question any chapter carries, in '
                'chapter order. Each lives in its chapter\'s YAML under <code>open_questions</code>'
                '; settle it there and it leaves this list.</p>' + wikitable(
                    ['Ch', 'Question', 'Claude\'s pick'], rows))


def css():
    """The wiki's own stylesheets, minus what they fetch from the wiki's servers (skin icons,
    a webfont): the artifact viewer blocks every outside load, so those are dropped here and
    the page falls back to the system font and plain bullets."""
    text = '\n'.join(open(os.path.join(ASSETS, f), encoding='utf-8').read()
                     for f in ('skin.css', 'site.css'))
    text = re.sub(r'@font-face\s*\{[^}]*\}', '', text)
    text = re.sub(r'@import[^;]*;', '', text)
    return re.sub(r'url\((?!["\']?data:)[^)]*\)', 'none', text)


# Ours, not the wiki's: one file holds every page, so the router shows one at a time; and the
# site's wide-screen banner slot (15.25rem, an image from its servers) collapses to its own
# narrow-screen margin, since the artifact viewer cannot load the image.
PAGE_CSS = """
/* jquery.makeCollapsible.styles (MediaWiki core; not in the vendored skin) */
.mw-collapsible-toggle-default::before{content:'['}
.mw-collapsible-toggle-default::after{content:']'}
.mw-collapsible-toggle-default .mw-collapsible-text{cursor:pointer}
section.page[hidden]{display:none!important}
#mw-content-container{margin-top:3.5rem!important}
"""

JS = """
(function(){
 document.body.className='mediawiki ltr sitedir-ltr mw-hide-empty-elt ns-0 ns-subject skin-timeless action-view skin--responsive';
 var pages=[].slice.call(document.querySelectorAll('section.page'));
 function show(){var id=decodeURIComponent((location.hash||'#home').slice(1));
  var target=document.getElementById(id);var page=target&&target.closest?target.closest('section.page'):null;
  if(!page){page=document.getElementById('home');}
  pages.forEach(function(p){p.hidden=(p!==page);});
  document.querySelector('#firstHeading .mw-page-title-main').textContent=page.getAttribute('data-title');
  document.title=page.getAttribute('data-title')+' - Manchego Stars Wiki';
  var tools=page.getAttribute('data-tools'),ul=document.getElementById('ms-page-tools');ul.innerHTML='';
  (tools?tools.split('|'):[]).forEach(function(t){var kv=t.split('=');var li=document.createElement('li');
   li.className='mw-list-item';var a=document.createElement('a');a.href='#'+kv[0];a.textContent=kv[1];
   li.appendChild(a);ul.appendChild(li);});
  document.getElementById('page-tools').style.display=tools?'':'none';
  var cat=page.getAttribute('data-category');var cl=document.getElementById('ms-cat');
  cl.textContent=cat||'';document.getElementById('catlinks').style.display=cat?'':'none';
  if(target&&target!==page)target.scrollIntoView();else window.scrollTo(0,0);}
 window.addEventListener('hashchange',show);show();
 window.addEventListener('load',function(){setTimeout(show,0);});  // after the browser's own anchor jump
 document.addEventListener('click',function(e){
  var tab=e.target.closest&&e.target.closest('.tab_tab');
  if(tab){var main=tab.closest('.tab_main');var all=[].slice.call(main.querySelector('.tabcontainer').querySelectorAll('.tab_tab'));
   var i=all.indexOf(tab);all.forEach(function(t,j){t.classList.toggle('tabselected',j===i);});
   var bodies=[].filter.call(main.querySelector('.tabcontents').children,function(c){return c.classList.contains('tab_content');});
   bodies.forEach(function(b,j){b.style.display=j===i?'':'none';});return;}
  var tg=e.target.closest&&e.target.closest('.mw-collapsible-toggle');
  if(tg){e.preventDefault();setCollapsed(tg.closest('.mw-collapsible'),
                                          !tg.closest('.mw-collapsible').classList.contains('mw-collapsed'));}
 });
 // MediaWiki's jquery.makeCollapsible, for tables: a [Collapse]/[Expand] toggle in the first
 // row's last cell; collapsed, every row but the first is hidden.
 function rows(t){return [].slice.call(t.rows).slice(1);}
 function setCollapsed(t,c){t.classList.toggle('mw-collapsed',c);
  rows(t).forEach(function(r){if(r.closest('table')===t)r.style.display=c?'none':'';});
  var tg=t.querySelector('.mw-collapsible-toggle');tg.setAttribute('aria-expanded',c?'false':'true');
  tg.classList.toggle('mw-collapsible-toggle-expanded',!c);tg.classList.toggle('mw-collapsible-toggle-collapsed',c);
  tg.querySelector('.mw-collapsible-text').textContent=c?'Expand':'Collapse';}
 [].slice.call(document.querySelectorAll('table.mw-collapsible')).forEach(function(t){
  var first=t.rows[0];if(!first)return;var cells=first.cells;var cell=cells[cells.length-1];
  var tg=document.createElement('span');tg.className='mw-collapsible-toggle mw-collapsible-toggle-default';
  tg.setAttribute('role','button');tg.tabIndex=0;tg.innerHTML='<a class="mw-collapsible-text">Collapse</a>';
  cell.insertBefore(tg,cell.firstChild);t.classList.add('mw-made-collapsible');
  setCollapsed(t,t.classList.contains('mw-collapsed'));});
})();
"""


def chrome(pages_html, chs):
    """The Fire Emblem Wiki's Timeless page frame (header, both sidebars, footer) around our
    pages, nested exactly as the same render nests it; the wiki's own tools, notices and search
    are dropped, and our navigation sits in their portlets."""
    nav = ''.join('<li class="mw-list-item"><a href="#%s">%s</a></li>' % (esc(a), esc(t)) for a, t in
                  (('home', 'Main page'), ('chapters', 'List of chapters'), ('roster', 'Characters'),
                   ('decisions', 'Open decisions')))
    chap_nav = ''.join('<li class="mw-list-item"><a href="#%s">%s %s</a></li>'
                       % (esc(c['_slug']), esc(c['_slug']), esc(c.get('title'))) for c in chs)
    portlet = ('<div role="navigation" class="mw-portlet" id="%s"><h3 lang="en" dir="ltr">%s</h3>'
               '<div class="mw-portlet-body"><ul lang="en" dir="ltr"%s>%s</ul></div></div>')
    bar = ('<div class="color-bar"><div class="color-middle-container"><div class="color-middle">'
           '</div></div><div class="color-left"></div><div class="color-right"></div></div>')
    return (
        '<div id="mw-wrapper">'
        '<div id="mw-header-container" class="ts-container"><div id="mw-header" class="ts-inner">'
        '<div id="p-logo-text" class="mw-portlet" role="banner"><a id="p-banner" class="mw-wiki-'
        'title long" href="#home">Manchego Stars Wiki</a></div><div class="visualClear"></div></div>'
        + bar.replace('<div class="color-bar">', '<div id="mw-header-hack" class="color-bar">', 1)
        + '<div id="mw-header-nav-hack">' + bar + '</div></div>'
        '<div id="menus-cover"></div>'
        '<div id="mw-content-container" class="ts-container"><div id="mw-content-block" class="ts-'
        'inner"><div id="mw-content-wrapper"><div id="mw-content"><div id="content" class="mw-body" '
        'role="main"><div class="mw-indicators"></div><h1 id="firstHeading" class="firstHeading mw-'
        'first-heading"><span class="mw-page-title-main"></span></h1><div id="bodyContentOuter">'
        '<div id="siteSub">From Manchego Stars Wiki, generated from the campaign\'s YAML and the FE8 '
        'decomp.</div><div class="visualClear"></div><div id="bodyContent"><div id="contentSub"><div '
        'id="mw-content-subtitle"></div></div><div id="mw-content-text" class="mw-body-content">'
        + pages_html +
        '</div><div class="visualClear"></div></div></div></div></div>'
        '<div id="content-bottom-stuff"><div id="catlinks" class="catlinks"><div id="mw-normal-'
        'catlinks" class="mw-normal-catlinks">Categories: <ul><li id="ms-cat"></li></ul></div></div>'
        '</div></div>'
        '<div id="mw-site-navigation"><div id="site-navigation" class="sidebar-chunk"><h2><span>'
        'Navigation</span></h2><div class="sidebar-inner">'
        + portlet % ('p-navigation', 'Navigation', '', nav)
        + portlet % ('p-chapters', 'Chapters', '', chap_nav) + '</div></div></div>'
        '<div id="mw-related-navigation"><div id="page-tools" class="sidebar-chunk"><h2><span>Page '
        'tools</span></h2><div class="sidebar-inner">'
        + portlet % ('p-cactions', 'Page tools', ' id="ms-page-tools"', '') + '</div></div></div>'
        '<div class="visualClear"></div></div></div>'
        '<div id="mw-footer-container" class="mw-footer-container ts-container"><div id="mw-footer" '
        'class="mw-footer ts-inner" role="contentinfo" lang="en" dir="ltr"><div id="footer-list">'
        '<ul id="footer-info"><li>Built by <code>tools/gen_wiki.py</code>. Layout and stylesheets: '
        'the <a class="external" href="https://fireemblemwiki.org/" target="_blank" rel="noopener">'
        'Fire Emblem Wiki</a> (GNU FDL 1.3).</li></ul></div><div class="visualClear"></div></div>'
        '</div></div>')


def open_questions(chs):
    return {c['_slug']: list(c.get('open_questions') or []) for c in chs}


def build():
    chs = chapters()
    units = units_index()
    first = next((c for c in chs if not c.get('is_prologue')), None)
    if first is not None:
        first['_founding'] = sorted(k for k, u in units.items() if u['_kind'] == 'pcs')
    opens = open_questions(chs)
    files = WikiFiles()
    titles = {}                       # page title -> page id: what a [[link]] opens here
    for c in chs:
        titles[c.get('title', c['_slug'])] = c['_slug']
        titles['%s/Script' % c.get('title', c['_slug'])] = '%s/script' % c['_slug']
    titles['List of characters in Manchego Stars'] = 'roster'
    chars = character_pages(chs, units, files)
    for pid, title, _wt in chars:
        titles.setdefault(title, pid)
    wsite_ = wsite.Site(titles, files)
    roster_title = 'List of characters in Manchego Stars'
    pages = [home_page(chs, units), index_page(chs),
             page('roster', roster_title, wsite.render_page(
                 roster_title, list_wikitext(chs, units, files), wsite_)),
             decisions_page(chs, opens)]
    for i, c in enumerate(chs):
        title = c.get('title', c['_slug'])
        wt = chapter_wikitext(c, chs[i - 1] if i else None,
                              chs[i + 1] if i + 1 < len(chs) else None, units, chs, files)
        script = script_wikitext(c, chs[i - 1] if i else None,
                                 chs[i + 1] if i + 1 < len(chs) else None, units)
        pages.append(page(c['_slug'], title, wsite.render_page(title, wt, wsite_),
                          tools=[('%s/script' % c['_slug'], 'Script') if script else None,
                                 ('%s/design' % c['_slug'], 'Design notes')],
                          category='Planned chapters' if c.get('status') == 'planned'
                          else 'Chapters'))
        if script:
            pages.append(page('%s/script' % c['_slug'], '%s/Script' % title,
                              wsite.render_page('%s/Script' % title, script, wsite_),
                              tools=[(c['_slug'], 'Chapter')], category='Scripts'))
        pages.append(design_page(c, opens))
    for pid, title, wt in chars:
        pages.append(page(pid, title, wsite.render_page(title, wt, wsite_),
                          category='Characters'))
    if wsite_.missing_files:
        print('wiki: %d file(s) no template could find: %s' % (
            len(wsite_.missing_files), ', '.join(sorted(wsite_.missing_files)[:12])))
    n_open = sum(len(v) for v in opens.values())
    doc = ('<meta charset="utf-8"><title>Manchego Stars Wiki</title><style>%s\n%s</style>'
           '%s<script>%s</script>'
           % (css(), PAGE_CSS, chrome(''.join(pages), chs), JS))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(doc)
    return OUT, len(chs), n_open


def main():
    out, n, k = build()
    print('wrote %s (%d chapters, %d open questions, %d bytes)' % (
        os.path.relpath(out, ROOT), n, k, os.path.getsize(out)))


if __name__ == '__main__':
    main()
