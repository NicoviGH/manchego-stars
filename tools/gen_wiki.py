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
import glob
import html
import os
import re
import sys

import yaml

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import difficulty                                      # noqa: E402
import scene_preview                                   # noqa: E402
import inject.decomp                                   # noqa: E402

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
    uri = None
    if os.path.exists(path):
        uri = 'data:image/png;base64,' + base64.b64encode(open(path, 'rb').read()).decode()
    _PORTRAITS[uid] = uri
    return uri


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


def recruits_of(chap):
    pc = chap.get('post_chapter') or {}
    ids = []
    for k in ('units_available_to_recruit', 'units_recruited_in_chapter'):
        for r in pc.get(k) or []:
            rid = r.get('id') if isinstance(r, dict) else r
            if rid and rid not in ids:
                ids.append(rid)
    return ids


def bosses_of(chap):
    return [e for e in enemy_list(chap) if e.get('is_boss')]


def item_rows(chap):
    """(item display, enum, how obtained) for every delivery vehicle the YAML declares."""
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
    for site in (chap.get('economy') or {}).get('reward_sites') or []:
        if site.get('gift'):
            n, en = our_item(site['gift'])
            rows.append((n, en, 'Reward site'))
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


# ── HTML pieces, in the wiki's own markup ──────────────────────────────────────

def infobox(title, rows):
    body = ''.join('<tr><th>%s</th><td><p>%s</p></td></tr>' % (esc(k), v) for k, v in rows if v)
    return ('<table class="infobox"><tbody><tr><td><table style="width:100%%"><tbody>'
            '<tr><th>%s</th></tr></tbody></table></td></tr><tr><td><table style="width:100%%">'
            '<tbody>%s</tbody></table></td></tr></tbody></table>' % (esc(title), body))


def h2(text, anchor):
    return '<h2><span class="mw-headline" id="%s">%s</span></h2>' % (anchor, esc(text))


def h3(text, anchor):
    return '<h3><span class="mw-headline" id="%s">%s</span></h3>' % (anchor, esc(text))


def wikitable(headers, rows, cls='wikitable'):
    if not rows:
        return '<p><i>None.</i></p>'
    head = ''.join('<th>%s</th>' % esc(h) for h in headers)
    body = ''.join('<tr>%s</tr>' % ''.join('<td>%s</td>' % c for c in r) for r in rows)
    return ('<div class="scroll"><table class="%s" style="margin:auto"><tbody><tr>%s</tr>%s'
            '</tbody></table></div>' % (cls, head, body))


def unit_card(uid, unit, joins_how):
    fs = (unit or {}).get('fe_stats') or {}
    img = portrait(uid)
    face = ('<img src="%s" width="96" height="80" alt="%s" style="image-rendering:pixelated">'
            % (img, esc(uid)) if img else '<i>no bust yet</i>')
    inv = '<br>'.join(esc(our_item(i)[0]) for i in (unit or {}).get('inventory') or []) or '—'
    name = (unit or {}).get('name') or uid
    return ('<td><table style="border-radius:14px;border:2px solid var(--color2);background:'
            'var(--color3);padding:4px;text-align:center;margin:auto;max-width:350px"><tbody>'
            '<tr><th style="border-radius:14px;border:1px solid var(--color2);padding:2px;'
            'font-size:larger">%s</th></tr><tr><td style="padding:2px;height:50px">%s</td></tr>'
            '<tr><td><table class="chapter-table" style="width:100%%;padding:2px;border:none;'
            'background:none;border-radius:0"><tbody><tr><td colspan="2"><b>%s</b></td></tr>'
            '<tr><td style="width:35%%"><b>Level</b><br>%s</td><td rowspan="2"><b>Inventory'
            '</b><br>%s</td></tr><tr><td><b>HP</b><br>%s</td></tr><tr><td colspan="2"><b>Joins'
            '</b><br>%s</td></tr></tbody></table></td></tr></tbody></table></td>'
            % (esc(name), face, esc(fs.get('class', '?')), esc(fs.get('level', '?')), inv,
               esc(fs.get('HP', '?')), esc(joins_how)))


def chars_block(cards):
    if not cards:
        return '<p><i>No new units.</i></p>'
    rows = ''.join('<tr>%s</tr>' % ''.join(cards[i:i + 3]) for i in range(0, len(cards), 3))
    return ('<table class="chap-chars round pixel-art width-80" style="margin:auto;border:2px '
            'solid var(--color2);background:var(--color3);text-align:center"><tbody><tr><th '
            'class="round" style="border:1px solid var(--color2);background:var(--color1);'
            'width:100%%;font-size:larger">Characters</th></tr><tr><td><table style="margin:'
            'auto;width:100%%"><tbody>%s</tbody></table></td></tr></tbody></table>' % rows)


# ── a chapter page ─────────────────────────────────────────────────────────────

def chapter_page(chap, prev, nxt, units, opens):
    slug = chap['_slug']
    title = chap.get('title', slug)
    num = chap.get('chapter_number')
    status = chap.get('status', 'active')
    curve = chap.get('parity_reference')
    donor = chap.get('fe8_base_map')
    ckey = twin_key(curve)
    dkey = twin_key(donor)
    obj = chap.get('objective') or {}
    obj_text = obj.get('description') or obj.get('type') if isinstance(obj, dict) else obj
    recs = recruits_of(chap)
    plan = chap.get('plan') or {}
    status_txt = ('Planned' if status == 'planned' else
                  'Locked' if chap.get('balance_locked') else 'Active')
    box = infobox(title, [
        ('Chapter', esc('Prologue' if chap.get('is_prologue') else 'Chapter %s' % num)),
        ('Status', esc(status_txt)),
        ('Curve twin', twin_label(curve)),
        ('Map donor', twin_label(donor)),
        ('Objective', esc(obj_text) if obj_text else esc(plan.get('objective', ''))),
        ('Location', esc(plan.get('location') or (chap.get('map') or {}).get('name', '')
                         if isinstance(chap.get('map'), dict) else plan.get('location', ''))),
        ('New units', ', '.join('<a href="#unit-%s">%s</a>' % (esc(r), esc((units.get(r) or {})
                                .get('name', r))) for r in recs)
         or esc(', '.join(plan.get('joins_roles') or []))),
        ('Boss(es)', esc(', '.join(b.get('name', '?') for b in bosses_of(chap))
                         or plan.get('boss', ''))),
        ('Previous chapter', '<a href="#%s">%s</a>' % (prev['_slug'], esc(prev.get('title')))
         if prev else ''),
        ('Next chapter', '<a href="#%s">%s</a>' % (nxt['_slug'], esc(nxt.get('title')))
         if nxt else ''),
    ])
    parts = [box]
    parts.append('<p><b>%s</b> is %s of <i>Manchego Stars</i>. Its curve twin is %s; its map '
                 'comes from %s.</p>' % (esc(title), 'the prologue' if chap.get('is_prologue')
                                         else 'chapter %s' % esc(num), twin_label(curve),
                                         twin_label(donor)))
    # Plot
    parts.append(h2('Plot', '%s-plot' % slug))
    parts.append(para(chap.get('narrative') or plan.get('story')))
    script = script_of(slug, chap)
    if script:
        parts.append('<details><summary>Script</summary>%s</details>' % script)
    if plan.get('sources'):
        parts.append('<p><small><b>Sources:</b> %s</small></p>' % esc('; '.join(plan['sources'])))
    # Chapter data
    parts.append(h2('Chapter data', '%s-data' % slug))
    rows = [('Objective', esc(obj_text or plan.get('objective', '—'))),
            ('Win', esc(chap.get('win_condition', ''))), ('Lose', esc(chap.get('lose_condition', ''))),
            ('Fog', esc(chap.get('fog', ''))), ('Cadence', esc(chap.get('cadence', ''))),
            ('Difficulty', esc(chap.get('difficulty_note', '')))]
    parts.append(wikitable(['Field', 'Value'], [r for r in rows if r[1]]))
    # Character data
    parts.append(h3('Character data', '%s-chars' % slug))
    cards = []
    for r in recs:
        u = units.get(r) or {}
        cards.append(unit_card(r, u, 'This chapter'))
    if not cards and plan.get('joins_roles'):
        parts.append(wikitable(['Vanilla role to fill', 'Who (recruit pass)'],
                               [(esc(x), '<i>open</i>') for x in plan['joins_roles']]))
    else:
        parts.append(chars_block(cards))
    # Item data
    parts.append(h3('Item data', '%s-items' % slug))
    ours = item_rows(chap)
    parts.append(wikitable(['Item', 'Obtain'], [(esc(n), esc(how)) for n, _, how in ours]))
    # Vanilla twin payload, checked against ours
    if ckey:
        v = vanilla_payload(ckey)
        parts.append(h3('Vanilla twin payload (%s)' % VANILLA[ckey][1], '%s-twin' % slug))
        if v['error']:
            parts.append('<p><i>%s</i></p>' % esc(v['error']))
        else:
            our_enums = {e for _, e, _ in ours if e}
            deviations = {d.get('item'): d.get('why', '') for d in chap.get('payload_deviations') or []}
            payload = ([(e, 'Chest') for e in v['chests']] + [(e, 'Gift / village / scene')
                       for e in v['gifts']] + [(e, 'Enemy drop') for e in v['drops']]
                       + [(e, 'Steal from an enemy') for e in v['steals']]
                       + [(e, 'Given to %s' % pretty_enum(c, 'CHARACTER_'))
                          for c, e in v['grants']])
            rows = []
            for e, how in payload:
                if e in our_enums:
                    mark = '<span style="color:var(--yes-checkmark-color)">delivered</span>'
                elif e in deviations:
                    mark = 'recorded deviation: %s' % esc(deviations[e])
                else:
                    mark = '<span style="color:var(--no-xmark-color)">not found in ours</span>'
                rows.append((esc(item_name(e)), esc(how), '<code>%s</code>' % esc(e), mark))
            for g in v.get('gold_chests') or []:
                rows.append(('%s gold' % esc(g), 'Chest', '', ''))
            parts.append(wikitable(['Item', 'Vanilla vehicle', 'Enum', 'Ours'], rows))
            rec = [(esc(pretty_enum(c, 'CHARACTER_')), esc(pretty_enum(k, 'CLASS_')), esc(l),
                    esc(how)) for c, k, l, how in v['recruits']]
            parts.append('<p><b>Vanilla recruits</b> (decomp loads):</p>')
            parts.append(wikitable(['Character', 'Class', 'Lv', 'How'], rec))
            if v['shops']:
                parts.append('<p><b>Vanilla shops</b>:</p>')
                parts.append(wikitable(['Shop', 'Stock'], [(esc(s.replace('ShopList_Event_', '')),
                             esc(', '.join(item_name(i) for i in items))) for s, items in v['shops']]))
            parts.append('<p><small>Read from <code>src/events/%s-event*.h</code> at HEAD. '
                         '"Not found in ours" compares vanilla enums with the items this '
                         'chapter\'s YAML resolves; a reflavoured item that keeps its enum '
                         'counts as delivered.</small></p>' % esc(v['stem']))
    if plan.get('payload_notes'):
        parts.append('<p><b>Where the twin\'s payload lands:</b></p>' + para(plan['payload_notes']))
    # Enemy data
    parts.append(h3('Enemy data', '%s-enemies' % slug))
    erows = []
    for e in enemy_list(chap):
        inv = ', '.join(our_item(i)[0] for i in e.get('inventory') or [])
        erows.append((esc(e.get('name') or e.get('id')), esc(e.get('class', '')),
                      esc(e.get('level', '')), esc(e.get('count', 1)), esc(inv),
                      esc(our_item(e['item_drop'])[0] if e.get('item_drop') else ''),
                      esc(e.get('arrives_turn', '') or ''),
                      'Boss' if e.get('is_boss') else ''))
    parts.append(wikitable(['Name', 'Class', 'Lv', '#', 'Items', 'Drops', 'Turn', ''], erows,
                           cls='wikitable chapter-table'))
    if ckey:
        v = vanilla_payload(ckey)
        vrows = {}
        for u in v['enemies']:
            k = (pretty_enum(u['classIndex'], 'CLASS_'), u['level'],
                 ', '.join(item_name(i) for i in u['items']))
            vrows[k] = vrows.get(k, 0) + 1
        parts.append('<details><summary>Vanilla twin\'s red units (%d loads, decomp)</summary>%s'
                     '</details>' % (len(v['enemies']), wikitable(['Class', 'Lv', 'Items', '#'],
                     [(esc(a), esc(b), esc(c), esc(n)) for (a, b, c), n in vrows.items()])))
    # Boss data
    bosses = bosses_of(chap)
    if bosses:
        parts.append(h3('Boss data', '%s-boss' % slug))
        brows = []
        for b in bosses:
            p = b.get('personal') or {}
            stats = ', '.join('%s %s' % (k.replace('base', ''), v) for k, v in p.items()
                              if k.startswith('base'))
            brows.append((esc(b.get('name')), esc(b.get('class')), esc(b.get('level')),
                          esc(stats or '—'), esc(b.get('death_quote', ''))))
        parts.append(wikitable(['Boss', 'Class', 'Lv', 'Personal stats', 'Death quote'], brows))
    # Lessons
    intro = chap.get('introduces') or plan.get('introduces')
    if intro:
        parts.append(h3('Introduces', '%s-intro' % slug))
        parts.append(wikitable(['Concept', 'How'], [(esc(i.get('concept') if isinstance(i, dict)
                     else i), esc((i.get('where') or i.get('coverage') or '') if isinstance(i, dict)
                     else '')) for i in intro]))
    # Strategy
    parts.append(h2('Strategy', '%s-strategy' % slug))
    parts.append(para(plan.get('how_it_plays') or chap.get('design_notes')))
    for key, label in ((dkey, 'map donor'), (ckey, 'curve twin')):
        if key and (label == 'curve twin' or key != ckey):
            s = wiki_strategy(key)
            if s:
                parts.append('<details><summary>Fire Emblem Wiki strategy for the %s, %s'
                             '</summary>%s</details>' % (label, esc(VANILLA[key][1]), s))
    # Open questions
    if opens.get(slug):
        parts.append(h2('Open questions', '%s-open' % slug))
        parts.append(wikitable(['Question', 'Claude\'s pick'], [(esc(q.get('q')), esc(q.get('pick', '')))
                     for q in opens[slug]]))
    parts.append('<p class="srcline"><small>Generated from <code>%s</code>.</small></p>'
                 % esc(chap['_file']))
    return '<section class="page" id="%s" data-title="%s">%s</section>' % (
        slug, esc(title), ''.join(parts))


def index_page(chs):
    rows = []
    for c in chs:
        st = 'Planned' if c.get('status') == 'planned' else ('Locked' if c.get('balance_locked')
                                                           else 'Active')
        rows.append(('<a href="#%s">%s</a>' % (c['_slug'], esc(c['_slug'])),
                     '<a href="#%s">%s</a>' % (c['_slug'], esc(c.get('title'))),
                     twin_label(c.get('parity_reference')), twin_label(c.get('fe8_base_map')),
                     esc(st)))
    return ('<section class="page" id="home" data-title="Chapters">'
            '<p><b>Manchego Stars Wiki</b> lists every chapter of the campaign, built and planned, '
            'with its vanilla twin. Each page is generated from the chapter\'s YAML and the FE8 '
            'decomp, so it is only as current as the last build.</p>%s</section>'
            % wikitable(['Ch', 'Title', 'Curve twin', 'Map donor', 'Status'], rows))


def roster_page(chs, units):
    rows = []
    for c in chs:
        for r in recruits_of(c):
            u = units.get(r) or {}
            img = portrait(r)
            face = '<img src="%s" width="48" height="40" alt="">' % img if img else ''
            rows.append(('<span id="unit-%s"></span>%s' % (esc(r), face), esc(u.get('name', r)),
                         esc((u.get('fe_stats') or {}).get('class', '?')),
                         '<a href="#%s">%s</a>' % (c['_slug'], esc(c['_slug']))))
        for role in (c.get('plan') or {}).get('joins_roles') or []:
            rows.append(('', '<i>open</i>', esc(role), '<a href="#%s">%s</a>'
                         % (c['_slug'], esc(c['_slug']))))
    pcs = [(('<img src="%s" width="48" height="40" alt="">' % portrait(k)) if portrait(k) else '',
            esc(u.get('name', k)), esc((u.get('fe_stats') or {}).get('class', '?')), 'ch01')
           for k, u in sorted(units.items()) if u['_kind'] == 'pcs']
    return ('<section class="page" id="roster" data-title="Roster">%s%s%s%s</section>'
            % (h2('Founding party', 'pcs'), wikitable(['', 'Name', 'Class', 'Joins'], pcs),
               h2('Recruits by chapter', 'recruits'), wikitable(['', 'Name', 'Class / role',
                                                                  'Joins'], rows)))


def decisions_page(chs, opens):
    rows = []
    for c in chs:
        for q in opens.get(c['_slug'], []):
            rows.append(('<a href="#%s">%s</a>' % (c['_slug'], esc(c['_slug'])), esc(q.get('q')),
                         esc(q.get('pick', ''))))
    return ('<section class="page" id="decisions" data-title="Open decisions">'
            '<p>Every open question any chapter carries, in chapter order. Each lives in its '
            'chapter\'s YAML under <code>open_questions</code>; settle it there and it leaves '
            'this list.</p>%s</section>' % wikitable(['Ch', 'Question', 'Claude\'s pick'], rows))


def css():
    return '\n'.join(open(os.path.join(ASSETS, f), encoding='utf-8').read()
                     for f in ('skin.css', 'site.css'))


PAGE_CSS = """
:root{color-scheme:dark;--page-bg:#11131f}
html,body{background:var(--page-bg)}
body{color:var(--text-color);margin:0}
#mw-wrapper{min-width:0}
.ms-shell{display:grid;grid-template-columns:13rem minmax(0,1fr);gap:1rem;max-width:80rem;
 margin:0 auto;padding-inline:16px;padding-block:1rem}
.ms-side{position:sticky;top:env(safe-area-inset-top,0px);align-self:start;max-height:100vh;
 overflow:auto;font-size:13px}
.ms-side a{display:block;padding:2px 4px}
.ms-side h3{margin:.8em 0 .2em;font-size:12px;letter-spacing:.06em;text-transform:uppercase}
.mw-body{min-width:0}
.scroll{overflow-x:auto;max-width:100%}
section.page{display:block}
section.page[hidden]{display:none!important}
details{margin:.6em 0}
summary{cursor:pointer;font-weight:bold}
.ms-script{white-space:pre;overflow-x:auto;font-size:12px;background:var(--color3);
 border:1px solid var(--color2);padding:.5em}
.ms-banner{font-size:1.4em;font-weight:bold;padding:.4em 16px}
@media (max-width:720px){.ms-shell{grid-template-columns:minmax(0,1fr)}
 .ms-side{position:static;max-height:none}.infobox{float:none;width:100%}}
"""

JS = """
(function(){
 var pages=[].slice.call(document.querySelectorAll('section.page'));
 function show(){var id=(location.hash||'#home').slice(1);
  var target=document.getElementById(id);var page=target&&target.closest?target.closest('section.page'):null;
  if(!page){page=document.getElementById('home');}
  pages.forEach(function(p){p.hidden=(p!==page);});
  var h=document.getElementById('ms-title');if(h)h.textContent=page.getAttribute('data-title');
  if(target&&target!==page)target.scrollIntoView();else window.scrollTo(0,0);}
 window.addEventListener('hashchange',show);show();
})();
"""


def open_questions(chs):
    return {c['_slug']: list(c.get('open_questions') or []) for c in chs}


def build():
    chs = chapters()
    units = units_index()
    opens = open_questions(chs)
    pages = [index_page(chs), roster_page(chs, units), decisions_page(chs, opens)]
    for i, c in enumerate(chs):
        pages.append(chapter_page(c, chs[i - 1] if i else None,
                                  chs[i + 1] if i + 1 < len(chs) else None, units, opens))
    nav = ''.join('<a href="#%s">%s %s</a>' % (c['_slug'], esc(c['_slug']), esc(c.get('title')))
                  for c in chs)
    side = ('<nav class="ms-side" aria-label="Wiki"><h3>Navigation</h3><a href="#home">Chapters'
            '</a><a href="#roster">Roster</a><a href="#decisions">Open decisions</a>'
            '<h3>Chapters</h3>%s</nav>' % nav)
    n_open = sum(len(v) for v in opens.values())
    doc = ('<title>Manchego Stars Wiki</title><style>%s\n%s</style>'
           '<div id="mw-wrapper" class="mediawiki skin-timeless"><div class="ms-banner">'
           'Manchego Stars Wiki</div><div class="ms-shell">%s<main id="content" class="mw-body">'
           '<h1 id="ms-title" class="firstHeading">Chapters</h1><div id="bodyContent">'
           '<div class="mw-parser-output">%s</div></div><p><small>%d chapters, %d open '
           'questions. Built by tools/gen_wiki.py.</small></p></main></div></div><script>%s'
           '</script>' % (css(), PAGE_CSS, side, ''.join(pages), len(chs), n_open, JS))
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
