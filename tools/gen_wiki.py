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
import inject.stats                                    # noqa: E402
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


def wiki_strategy(key):
    """The twin's Strategy section, from the local mirror of the Fire Emblem Wiki."""
    path = os.path.join(WIKI_MIRROR, 'strategy-digest.md')
    if not key or not os.path.exists(path):
        return ''
    page = VANILLA[key][2]
    text = open(path, encoding='utf-8').read()
    m = re.search(r'^## %s\n(.*?)(?=^## |\Z)' % re.escape(page), text, re.S | re.M)
    if not m:
        return ''
    body = m.group(1).strip()
    body = re.sub(r'\{\{[^}]*\}\}', '', body)
    body = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r'\1', body)
    body = re.sub(r"'''?|''", '', body)
    return para(body.replace('\n\n', '\n\n'))


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


_PORTRAITS = {}


def portrait(uid):
    """Our own bust as a data URI (the wiki shows the in-game face; so do we)."""
    if uid in _PORTRAITS:
        return _PORTRAITS[uid]
    path = os.path.join(CAMP, 'portraits', '%s.png' % uid)
    _PORTRAITS[uid] = png_uri(path, key_index0=True) if os.path.exists(path) else None
    return _PORTRAITS[uid]


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


_ENUM_BY_KEY = None


def _enum_lookup():
    """Normalised spelling -> ITEM_ enum, from vanilla constants/items.h. Our ids are kebab
    spellings of vanilla names (pure-water, iron-axe, booster-def); vanilla puts a weapon's
    kind first (ITEM_AXE_IRON), so both orders are indexed. Plain spellings win ties, which
    keeps `torch` on the Torch item rather than the Torch staff."""
    global _ENUM_BY_KEY
    if _ENUM_BY_KEY is None:
        _ENUM_BY_KEY = {}
        kinds = ('SWORD', 'LANCE', 'AXE', 'BOW', 'BLADE', 'ANIMA', 'LIGHT', 'DARK', 'STAFF')
        late = {}
        for enum, name in _vanilla_item_names().items():          # the game's own names
            late.setdefault(re.sub(r'[^a-z0-9]', '', name.lower()), enum)
        for enum in difficulty._item_id_to_enum().values():
            parts = enum.replace('ITEM_', '').split('_')
            _ENUM_BY_KEY.setdefault(''.join(parts).lower(), enum)
            if len(parts) > 1 and parts[0] in kinds:
                rest = parts[1:]
                late.setdefault((''.join(rest) + parts[0]).lower(), enum)
                late.setdefault(''.join(rest).lower(), enum)
        for k, v in late.items():
            _ENUM_BY_KEY.setdefault(k, v)
    return _ENUM_BY_KEY


def our_item(it):
    """A YAML item ref -> (display name, vanilla enum or None)."""
    if isinstance(it, str):
        it = {'id': it}
    iid = it.get('id', '')
    try:
        enum = inject.decomp.fe_item_enum(it)
    except Exception:
        enum = _enum_lookup().get(str(it.get('fe_base') or iid).replace('-', '').lower())
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
    """(item display, enum, how obtained) for every delivery vehicle the ROM wires. The
    `economy:` ledger is design bookkeeping no injector reads, so it is not one."""
    rows = []
    for v in chap.get('villages') or []:
        for r in v.get('visit_reward') or v.get('reward') or []:
            if r.get('id') == 'gold':
                rows.append(('%s gold' % r.get('amount'), None, 'Visit village'))
            elif r.get('id'):
                n, e = our_item(r)
                rows.append((n, e, 'Visit village%s' % (' (%s)' % v['id'] if v.get('id') else '')))
    for c in chap.get('chests') or []:
        for it in c.get('contents') or []:
            n, e = our_item(it)
            rows.append((n, e, 'Open chest at %s' % (c.get('position'),)))
    for e in enemy_list(chap):
        who = e.get('name') or e.get('class')
        drop = e.get('item_drop')
        if drop:
            n, en = our_item(drop)
            rows.append((n, en, 'Dropped by %s' % who))
        for it in e.get('inventory') or []:
            n, en = our_item(it)
            iid = it.get('id') if isinstance(it, dict) else it
            if iid != drop and en and en not in ('ITEM_DOORKEY', 'ITEM_CHESTKEY') \
                    and _is_plain_item(en):
                rows.append((n, en, 'Steal from %s' % who))
    for g in (chap.get('deployment') or {}).get('green_allies') or []:
        if g.get('gift'):
            n, en = our_item(g['gift'])
            rows.append((n, en, 'Gift from %s' % (g.get('name') or g.get('id'))))
    bonus = (chap.get('economy') or {}).get('save_all_bonus')
    if bonus:
        n, en = our_item(bonus)
        rows.append((n, en, 'Save-all bonus'))
    for site in (chap.get('post_chapter') or {}).get('reward_sites') or []:
        if site.get('gift'):
            n, en = our_item(site['gift'])
            rows.append((n, en, 'Scene gift'))
    for boat in chap.get('rescue_boats') or []:
        for r in (boat.get('talk') or {}).get('reward') or []:
            n, en = our_item(r)
            rows.append((n, en, 'Talk on a rescue boat'))
    return rows


_SCENES = None


def script_of(slug, chap):
    """The chapter's script, the way the wiki's Script page reads: every scene the scene
    previewer knows (wired or drafted), box by box with speakers and drawn widths; else the
    YAML's own event beats, which is where a chapter keeps its scenes before they are drafted."""
    global _SCENES
    if _SCENES is None:
        _SCENES = {}
        try:
            for key in scene_preview.registry():
                _SCENES.setdefault(key.split('/')[0], []).append(
                    scene_preview.format_scene(scene_preview.preview(key)))
        except Exception:
            pass
        try:
            for key, scene in scene_preview.drafts().items():
                _SCENES.setdefault(key.split('/')[0], []).append(scene_preview.format_scene(scene))
        except Exception:
            pass
    scenes = _SCENES.get(slug)
    if scenes:
        return ''.join('<pre class="ms-script">%s</pre>' % esc(t.rstrip()) for t in scenes)
    beats = [(e.get('trigger', ''), e.get('description', '')) for e in chap.get('events') or []
             if isinstance(e, dict) and e.get('description')]
    return wikitable(['When', 'Beat'], [(esc(t), para(d)) for t, d in beats]) if beats else ''


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


def item_cell(it):
    """A YAML item ref as the wiki writes an inventory entry: icon, then the linked name.
    The link goes to the vanilla item's article; the name is the one the ROM shows."""
    name, enum = our_item(it)
    return item_html(enum, name)


def item_html(enum, fallback=''):
    shown = rom_item_name(enum, fallback)
    custom = (campaign_yaml().get('item_icons') or {}).get(enum)
    icon = art.item_icon(enum, os.path.join(CAMP, 'item_icons', custom + '.png') if custom else None)
    return '%s&#160;%s' % (mk.file_img(icon, 16, 16), mk.fe(item_name(enum) or shown, shown))


def class_html(token, italic=False):
    """A class cell: the game's name for it, linked to the wiki's class article."""
    name = class_display_name(token)
    return mk.fe(name)


def class_enum_of(token):
    return difficulty._enemy_class_enum(token)


def _reskin_sprite(chap, token):
    """Our own map sprite for a class a reskin dresses in this chapter, or None."""
    for rk in campaign_yaml().get('enemy_class_reskins') or []:
        if token in ((rk.get('dresses') or {}).get(chap['_slug']) or []):
            path = os.path.join(CAMP, 'map_sprites', '%s.png' % rk.get('sprite'))
            return art.sheet_sprite(path, rk.get('frame', '16x16'))
    return None


def sprite_html(chap, token, faction='enemy'):
    got = _reskin_sprite(chap, token) if faction == 'enemy' else None
    if not got:
        try:
            got = art.map_sprite(class_enum_of(token), faction)
        except Exception:
            got = None
    return mk.file_img(got[0], got[1], got[2]) if got else ''


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


def ai_text(chap, ed):
    try:
        import chapter_status
        shape = chapter_status.ai_shape(difficulty.enemy_ai_bytes(chap, ed, 0))
    except Exception:
        shape = None
    return esc(AI_TEXT[shape]) if shape in AI_TEXT else mk.NO_AI


def enemy_row(chap, ed, token, level, inv, n, shifts, mode):
    st = loaded(ed, token, level, shifts, mode)
    named = ed.get('is_boss') or ed.get('is_miniboss') or personal_of(ed)
    name = esc(ed.get('fe_name') or ed.get('name')) if named else esc(class_display_name(token))
    return {'sprite': sprite_html(chap, token), 'name': name, 'cls': class_html(token),
            'lv': level, 'n': n, 'stats': [unit_load.show(st[k]) for k in STAT_KEYS],
            'inventory': ' • '.join(item_cell(i) for i in inv if not
                                     (isinstance(i, dict) and i.get('is_key_item'))),
            'ai': ai_text(chap, ed)}


def enemy_section(chap, shifts):
    entries = enemy_list(chap)
    if not entries:
        return ''
    modes = MODE_LABELS if shifts else (('normal', 'Normal'),)
    contents = []
    for mode, _ in modes:
        start, reinf = [], []
        for ed in entries:
            for token, lv, inv, n in bodies(ed):
                (reinf if ed.get('arrives_turn') else start).append(
                    enemy_row(chap, ed, token, lv, inv, n, shifts, mode))
        blocks = [mk.enemy_block('Enemy Units', mk.enemy_rows(start))]
        if reinf:
            blocks.append(mk.enemy_block('Reinforcements', mk.enemy_rows(reinf)))
        contents.append(mk.enemy_tables(blocks))
    sel = [m for m, _ in modes].index('normal')
    return mk.note(mk.STAT_RANGE_NOTE) + '<hr />' + mk.tabs([l for _, l in modes], contents, sel)


def reinforcement_list(chap):
    waves = collections.OrderedDict()
    for ed in sorted((e for e in enemy_list(chap) if e.get('arrives_turn')),
                     key=lambda e: int(e['arrives_turn'])):
        for token, lv, inv, n in bodies(ed):
            weapon = next((our_item(i)[1] for i in inv), None)
            what = '%d %s' % (n, class_html(token)) if not ed.get('is_boss') else esc(ed.get('name'))
            if weapon:
                what += ' with %s' % mk.fe(item_name(weapon), rom_item_name(weapon))
            waves.setdefault(int(ed['arrives_turn']), []).append(what)
    if not waves:
        return ''
    return '<ul>%s</ul>' % ''.join('<li>Turn %d<ul>%s</ul></li>' % (t, ''.join(
        '<li>%s</li>' % w for w in ws)) for t, ws in waves.items())


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


def boss_section(chap, shifts):
    cards = []
    for ed in bosses_of(chap):
        token, lv = ed.get('class'), int(ed.get('level', 1))
        cls = class_enum_of(token)
        modes = MODE_LABELS if shifts else (('normal', 'Normal'),)
        loads = [loaded(ed, token, lv, shifts, m) for m, _ in modes]
        donor = inject.stats.BASE_DONOR.get(ed.get('id')) or inject.cast.ENEMY_BASE_SLOT.get(ed.get('id'))
        ranks = _ranks(cls, donor)
        rank_cells = [(mk.fe_html(p, mk.file_img(art.named_icon('inventory_category_' + k), 16, 16,
                                                  label)), _letter(ranks.get(_ITYPE[k])))
                      for k, p, label in _RANK_TYPES]
        face = portrait(ed['face']) if ed.get('face') else None
        attrs = unit_load._class_block(cls)
        inv = '<br />'.join(item_cell(i) for i in ed.get('inventory') or [])
        bodies_ = []
        for st in loads:
            con = st['Con'][0]
            aid = (con - 1 if 'CA_MOUNTEDAID' not in attrs else
                   (20 - con if 'CA_FEMALE' in attrs else 25 - con))
            stats = {'Max HP': unit_load.show(st['HP']), 'Luck': unit_load.show(st['Lck']),
                     'Strength': unit_load.show(st['Pow']), 'Defense': unit_load.show(st['Def']),
                     'Skill (stat)': unit_load.show(st['Skl']),
                     'Resistance': unit_load.show(st['Res']), 'Speed': unit_load.show(st['Spd']),
                     'Constitution': unit_load.show(st['Con']),
                     'Movement': unit_load.show(st['Mov']), 'Aid': aid}
            bodies_.append(mk.boss_card(
                mk.file_img(face, 96, 80, ed.get('name')) if face else '',
                sprite_html(chap, token), class_html(token), lv,
                _affinity(ed), stats, inv, rank_cells))
        uniq = list(dict.fromkeys(bodies_))
        labels = [l for _, l in modes]
        if len(uniq) == 1:
            body = mk.tabs(['All'], uniq)
        else:
            body = mk.tabs(labels, bodies_, [m for m, _ in modes].index('normal'), 'fit-content')
        cards.append(mk.note(mk.STAT_RANGE_NOTE) + body if not cards else body)
    return ''.join(cards)


def _affinity(ed):
    aff = ed.get('affinity')
    if not aff:
        return ''
    return mk.fe_html('%s (affinity)' % str(aff).capitalize(),
                      mk.file_img(art.named_icon('affinity_%s' % aff), 16, 16, aff))


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


def unit_counts(chap):
    dep = chap.get('deployment') or {}
    player = dep.get('deploy_limit') or len(dep.get('deploy_slots') or []) or ''
    start = sum(n for ed in enemy_list(chap) if not ed.get('arrives_turn')
                for _t, _l, _i, n in bodies(ed))
    reinf = sum(n for ed in enemy_list(chap) if ed.get('arrives_turn')
                for _t, _l, _i, n in bodies(ed))
    enemy = '%d%s' % (start, mk.tooltip('+%d' % reinf, 'reinforcements') if reinf else '')
    return esc(player), enemy


def join_text(uid, unit, chap):
    if uid in (chap.get('_founding') or []):
        return 'Automatically at the start of the chapter'
    via = ((unit or {}).get('recruit') or {}).get('via')
    if via == 'talk':
        return 'Talk with any party member'
    if via == 'market':
        return 'Automatically after the chapter'
    return 'Automatically'


def available_before(chs, chap):
    out = []
    for c in chs:
        if c is chap:
            break
        out += [r for r in recruits_of(c) if r not in out]
    return out


def minimug_html(uid, units):
    img = art.minimug(os.path.join(CAMP, 'portraits', '%s.png' % uid))
    name = unit_name(uid, units)
    return '<a href="#unit-%s" title="%s">%s</a>' % (esc(uid), esc(name),
                                                    mk.file_img(img, 32, 32, name)) if img else ''


def item_rows_html(chap):
    rows = []
    for name, enum, how in item_rows(chap):
        how = esc(how).replace('Visit village', 'Visit %s' % mk.fe('Village', 'village'))
        rows.append((mk.file_img(art.item_icon(enum), 16, 16) if enum else '',
                     mk.fe(item_name(enum), rom_item_name(enum, name)) if enum else esc(name), how))
    return mk.items_table(rows) if rows else ''


def shop_html(chap):
    try:
        import importlib
        mod = importlib.import_module('inject.chapters.%s' % chap['_slug'])
    except Exception:
        return ''
    shops = getattr(mod, '%s_SHOPS' % chap['_slug'].upper(), None)
    if not shops:
        return ''
    text = inject.decomp.vanilla_decomp_text('src/data_items.c')
    labels, bodies_ = [], []
    for macro, sym, _x, _y in shops:
        rows = []
        for enum in difficulty._shoplist_items(
                inject.decomp.vanilla_decomp_text('src/events_shoplist.c'), sym):
            m = re.search(r'\[%s\]\s*=\s*\{(.*?)\n\s*\},' % re.escape(enum), text, re.S)
            uses = re.search(r'\.maxUses\s*=\s*(\d+)', m.group(1)) if m else None
            per = re.search(r'\.costPerUse\s*=\s*(\d+)', m.group(1)) if m else None
            cost = int(per.group(1)) * max(int(uses.group(1)) if uses else 1, 1) if per else ''
            rows.append((mk.file_img(art.item_icon(enum), 16, 16),
                         mk.fe(item_name(enum), rom_item_name(enum)), cost))
        labels.append(macro)
        bodies_.append(mk.shop_table(rows))
    return mk.boxed_tabs('Shop data', labels, bodies_)


def strategy_html(chap, ckey, dkey):
    out = []
    ours_ = chap.get('strategy')
    if ours_:
        out.append(para(ours_))
    for key, label in ((ckey, 'curve twin'), (dkey, 'map donor')):
        if key and (label == 'curve twin' or key != ckey):
            s = wiki_strategy(key)
            if s:
                out.append(mk.collapsible('Vanilla strategy for %s (%s), as the Fire Emblem Wiki '
                                          'writes it' % (VANILLA[key][1], label), s))
    return (mk.STRATEGY_DISCLAIMER + ''.join(out)) if out else ''


def chapter_page(chap, prev, nxt, units, chs):
    slug = chap['_slug']
    title = chap.get('title', slug)
    num = chap.get('chapter_number')
    plan = chap.get('plan') or {}
    ckey, dkey = twin_key(chap.get('parity_reference')), twin_key(chap.get('fe8_base_map'))
    shifts = chapter_shifts(chap)
    recs = recruits_of(chap)
    img, _cap = map_image(chap)
    a = lambda part: '%s-%s' % (slug, part)              # noqa: E731
    sections, toc = [], []

    def add(level, text, anchor, body):
        if body:
            toc.append((level - 1, text, anchor))
            sections.append(mk.h(level, text, anchor) + body)

    # Plot
    script = script_of(slug, chap)
    plot = (mk.main_article('%s/script' % slug, '%s/Script' % title) if script else '') + \
        para(chap.get('narrative') or plan.get('story'))
    add(2, 'Plot', a('Plot'), plot)
    # Chapter data
    w = h = '?'
    m = re.search(r'\((\d+)x(\d+)\)', _cap or '')
    if m:
        w, h = m.groups()
    player, enemy = unit_counts(chap)
    data = mk.chapter_data(victory_text(chap), defeat_text(chap), player, enemy,
                           mk.file_img(img, int(w) * 16 if w != '?' else 0,
                                       int(h) * 16 if h != '?' else 0, title) if img else '',
                           w, h)
    toc.append((1, 'Chapter data', a('Chapter_data')))
    sections.append(mk.h(2, 'Chapter data', a('Chapter_data')) + data)
    cards = [mk.unit_card(mk.ours('unit-%s' % r, unit_name(r, units)),
                          mk.file_img(portrait(r), 96, 80, unit_name(r, units)),
                          class_html((units.get(r) or {}).get('fe_stats', {}).get('class')),
                          (units.get(r) or {}).get('fe_stats', {}).get('HP', '?'),
                          (units.get(r) or {}).get('fe_stats', {}).get('level', '?'),
                          '<br />'.join(item_cell(i) for i in (units.get(r) or {}).get('inventory')
                                        or []),
                          join_text(r, units.get(r), chap)) for r in recs]
    avail = [minimug_html(u, units) for u in available_before(chs, chap)]
    add(3, 'Character data', a('Character_data'),
        mk.characters(cards, [('Available characters', avail)]) if cards or avail else '')
    add(3, 'Item data', a('Item_data'), item_rows_html(chap))
    add(3, 'Shop data', a('Shop_data'), shop_html(chap))
    add(3, 'Enemy data', a('Enemy_data'), enemy_section(chap, shifts))
    add(4, 'Reinforcements', a('Reinforcements'), reinforcement_list(chap))
    add(3, 'Boss data', a('Boss_data'), boss_section(chap, shifts))
    add(2, 'Strategy', a('Strategy'), strategy_html(chap, ckey, dkey))
    box = mk.infobox(title, mk.file_img(img, 200, 0, title).replace(' height="0"', '') if img
                     else '', [
        ('Location', esc(chap.get('location', ''))),
        ('New units', ', '.join(mk.ours('unit-%s' % r, unit_name(r, units)) for r in recs)),
        ('Boss(es)', ', '.join(esc(b.get('name', '?')) for b in bosses_of(chap))
         or esc(plan.get('boss', ''))),
        ('Previous chapter(s)', mk.ours(prev['_slug'], prev.get('title')) if prev else ''),
        ('Next chapter(s)', mk.ours(nxt['_slug'], nxt.get('title')) if nxt else ''),
    ])
    lead = ('<p><b>%s</b> is the %s of <i>Manchego Stars</i>.\n</p>'
            % (esc(title), 'prologue' if chap.get('is_prologue') else
               '%s chapter' % ORDINALS[num] if isinstance(num, int) and num < len(ORDINALS)
               else 'chapter %s' % esc(num)))
    return page(slug, title, box + lead + mk.toc(toc, slug) + ''.join(sections),
                tools=[('%s/script' % slug, 'Script') if script else None,
                       ('%s/design' % slug, 'Design notes')],
                category='Planned chapters' if chap.get('status') == 'planned' else 'Chapters')


def script_page(chap):
    slug, title = chap['_slug'], chap.get('title', chap['_slug'])
    script = script_of(slug, chap)
    if not script:
        return ''
    return page('%s/script' % slug, '%s/Script' % title, script,
                tools=[(slug, 'Chapter')], category='Scripts')


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


def index_page(chs):
    rows = []
    for c in chs:
        st = 'Planned' if c.get('status') == 'planned' else ('Locked' if c.get('balance_locked')
                                                           else 'Active')
        rows.append((mk.ours(c['_slug'], c['_slug']), mk.ours(c['_slug'], c.get('title')),
                     twin_label(c.get('parity_reference')), twin_label(c.get('fe8_base_map')),
                     esc(st)))
    return page('home', 'Chapters', '<p><b>Manchego Stars Wiki</b> lists every chapter of the '
                'campaign, built and planned. Each page is generated from the chapter\'s YAML and '
                'the FE8 decomp, so it is only as current as the last build.</p>' + wikitable(
                    ['Ch', 'Title', 'Curve twin', 'Map donor', 'Status'], rows))


def roster_page(chs, units):
    rows = []
    for c in chs:
        for r in recruits_of(c):
            if r in (c.get('_founding') or []):
                continue
            u = units.get(r) or {}
            rows.append(('<span id="unit-%s"></span>%s' % (esc(r), mk.file_img(
                         art.minimug(os.path.join(CAMP, 'portraits', '%s.png' % r)), 32, 32)),
                         esc(unit_name(r, units)), class_html((u.get('fe_stats') or {}).get('class')),
                         mk.ours(c['_slug'], c['_slug'])))
        for role in (c.get('plan') or {}).get('joins_roles') or []:
            rows.append(('', '<i>open</i>', esc(role), mk.ours(c['_slug'], c['_slug'])))
    first = next((c for c in chs if c.get('_founding')), None)
    pcs = [('<span id="unit-%s"></span>%s' % (esc(k), mk.file_img(art.minimug(os.path.join(
            CAMP, 'portraits', '%s.png' % k)), 32, 32)), esc(u.get('name', k)),
            class_html((u.get('fe_stats') or {}).get('class')),
            mk.ours(first['_slug'], first['_slug']) if first else '')
           for k, u in sorted(units.items()) if u['_kind'] == 'pcs']
    return page('roster', 'Roster', mk.h(2, 'Founding party', 'pcs') +
                wikitable(['', 'Name', 'Class', 'Joins'], pcs) +
                mk.h(2, 'Recruits by chapter', 'recruits') +
                wikitable(['', 'Name', 'Class / role', 'Joins'], rows))


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
section.page[hidden]{display:none!important}
#mw-content-container{margin-top:3.5rem!important}
.ms-script{white-space:pre;overflow-x:auto;font-size:12px}
.mw-collapsible.mw-collapsed tr+tr{display:none}
.mw-collapsible th{cursor:pointer}
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
  var th=e.target.closest&&e.target.closest('.mw-collapsible th');
  if(th){th.closest('.mw-collapsible').classList.toggle('mw-collapsed');}
 });
})();
"""


def chrome(pages_html, chs):
    """The Fire Emblem Wiki's Timeless page frame (header, both sidebars, footer) around our
    pages, nested exactly as the same render nests it; the wiki's own tools, notices and search
    are dropped, and our navigation sits in their portlets."""
    nav = ''.join('<li class="mw-list-item"><a href="#%s">%s</a></li>' % (esc(a), esc(t)) for a, t in
                  (('home', 'Chapters'), ('roster', 'Roster'), ('decisions', 'Open decisions')))
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
        '</div><div class="visualClear"></div></div>'
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
    pages = [index_page(chs), roster_page(chs, units), decisions_page(chs, opens)]
    for i, c in enumerate(chs):
        pages.append(chapter_page(c, chs[i - 1] if i else None,
                                  chs[i + 1] if i + 1 < len(chs) else None, units, chs))
        pages.append(script_page(c))
        pages.append(design_page(c, opens))
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
