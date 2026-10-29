#!/usr/bin/env python3
"""Strategy as data (#510 step 6): each Strategy section, the twin's and ours, curated into
claims the parity model checks.

A Strategy section is the best record we have of how a chapter is actually PLAYED: the
twin's is the Fire Emblem Wiki's (vendored under `tools/wiki/vendor/twins/`), ours is the
chapter YAML's `strategy:`. Each claim cites the line it comes from, verbatim (wiki markup
stripped), and a claim whose citation is not in its section raises -- a claim nobody can
point at is the model's opinion, not the strategy's.

Kinds (each side's claims are read against that side's OWN party and force):

  terrain     `tile` (a TERRAIN_ name) and `vs` ('all', 'boss', or an enemy): the party
              holds that tile against those enemies. REPORTED: how many of the tile that
              side's map has, and what a foot unit gains on it. Not a model input: fed in,
              ch01's forts alone took its threat from x1.10 to x0.48, a side's cover set by
              whichever wiki text happened to mention a tile (Nicolas, 2026-10-21, on #510).
  carry       `unit` (one or a list) and `vs`: the strategy's answer to that enemy. CHECK:
              the named unit is the fielded party's fastest killer of it.
  answer      `unit` and `vs`: that enemy is the unit's best matchup. CHECK: of the enemy
              types on the map, bosses aside unless named, the unit kills `vs` fastest.
  wall        `unit` and `vs`: who should stand in front of that enemy. CHECK: the named
              unit survives it longest of the fielded party.
  threat      `vs`: the enemy the strategy says to fear. CHECK: it is the force's heaviest
              enemy type by summed threat, convertibles left out (they need not be fought).
  reinforcements  no fields: the strategy warns of the waves. REPORTED: how many bodies
              arrive after turn 1, and how many of them are in the side's heaviest
              engagement (#510 step 7), the one its threat is read from.
  recruit     `unit`, optional `by` (one or a list): talk that unit over, by `by` when the
              strategy names who (Neimi talks to Colm), else by anyone the game lets. PLAYED by
              the step-9 bot, first, before the rest of the map; not a parity read.
  keys        no fields: the strategy points at the enemies carrying keys. PLAYED: the bot
              strikes the enemies the game says hold a key first, and a unit holding one opens
              the door that cuts it off from its goal.
  heal        `vs`: heal between attacks on that enemy. PLAYED: the bot's style gates count the
              heal a healer can still give this phase before the enemy phase.
  avoid       `unit` and `vs`: keep that unit out of those enemies' reach (the flier off the
              archer). PLAYED: the unit never ends a move where one of them can strike it.
  priority    `vs`: an enemy to kill before the rest (the enemy thief). PLAYED: the bot ranks
              it above every other target.
  kits        `topic` (one of KIT_TOPICS): what the party picks up. REPORTED: modelled since
              #510 step 8 (ADR 0365): the verdict reads the happy path, every pickup taken,
              and `make difficulty CH=` prints the guaranteed path beside it.
  unmodelled  `topic` (one of TOPICS): play the model does not read. The topic fixes the
              #510 step that will (7: reach and time), or `out`: left out by decision
              (ADR 0365: healing, the arena, keys and steals, none of which changes what a
              unit fights with). Recorded so the curation is complete.

Topics are ONE shared taxonomy (TOPICS, KIT_TOPICS) for ours, the twin's and the step-9 bot,
so the same play carries the same tag on both sides: a line is tagged by what it MEANS, never
by a word it happens to use ("the undead race to desecrate them" and "save the western
Village" are both `site-race`). A topic outside the taxonomy raises; a new tag is added here,
with its meaning, before any claim uses it.

`vs` names an enemy by class (`fighter`, `armor-knight`), by our unit id or the twin's
character (`goblin-chief`, `breguet`), or `boss`; a list means any of them. Checks are FINDINGS printed beside the
verdict, never a gate, and no claim feeds the model (Nicolas, 2026-10-21, on #510).
"""
import functools
import os
import re

import yaml

import campaign_chapters
import difficulty as dif
import map_donor

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TWIN_CLAIMS = os.path.join(REPO, 'tools/wiki/twin_strategy.yaml')
TWIN_PAGES = os.path.join(REPO, 'tools/wiki/vendor/twins')

KINDS = {
    'terrain': {'tile', 'vs'},
    'carry': {'unit', 'vs'},
    'answer': {'unit', 'vs'},
    'wall': {'unit', 'vs'},
    'threat': {'vs'},
    'reinforcements': set(),
    'kits': {'topic'},
    'unmodelled': {'topic'},
    'recruit': {'unit'},
    'keys': set(),
    'heal': {'vs'},
    'avoid': {'unit', 'vs'},
    'priority': {'vs'},
}
# The kinds only the step-9 bot reads (#510): the parity model prints nothing for them.
PLAYED_ONLY = {'recruit', 'keys', 'heal', 'avoid', 'priority'}
# topic -> (the #510 step that reads it, what the play is). Step 7 = reach and time; 'out' =
# left out by decision (ADR 0365).
TOPICS = {
    'recruit': (7, 'talk an enemy or green unit over, or keep a recruit alive until talked to'),
    'talk': (7, 'a conversation between party members (not a recruit)'),
    'arrival': (7, 'allies who join mid-map, and where'),
    'escort': (7, 'keep allied, green or NPC units alive'),
    'site-race': (7, 'reach a village, niche or treasure before the enemy destroys or loots it'),
    'tempo': (7, 'move fast because the board worsens with time (eggs hatch, waves build)'),
    'objective': (7, 'a win condition other than rout (defeat the boss, survive, seize)'),
    'baiting': (7, 'draw an enemy out of position, or let it strike first on a chosen tile'),
    'hold': (7, 'stay put and let the enemy come, a chokepoint blocked or a line held'),
    'range': (7, "fight from outside an enemy's reach, or keep a unit out of one enemy's"),
    'rescue': (7, 'Rescue, Canto or a flier to carry a unit in or out'),
    'deploy-order': (7, 'the enemy AI picks staff targets by unit-list order'),
    'fog': (7, 'fog of war: torches, vision'),
    'siege': (7, 'use a map siege weapon (a ballista)'),
    'enemy-cover': (7, 'enemies hold evasive terrain'),
    'healing': ('out', 'staves, Vulneraries, Restore, Physic'),
    'steal': ('out', 'steal an item'),
    'arena': ('out', 'the arena'),
    'keys': ('out', 'door and chest keys'),
    'trade': ('out', 'move items between units'),
    'durability': ('out', 'weapon uses'),
}
KIT_TOPICS = {'villages', 'chests', 'drops', 'shop'}


def step_of(claim):
    """The #510 step an unmodelled claim waits on (7) or 'out', from its topic."""
    return TOPICS[claim['topic']][0]


def plain(text):
    """Wiki text as it reads: `[[a|b]]` -> b, `[[a]]` -> a, `{{title|X}}` -> X, `''` dropped,
    whitespace collapsed. Citations are compared in this form."""
    text = re.sub(r'\[\[(?:[^\]|]*\|)?([^\]]*)\]\]', r'\1', str(text or ''))
    text = re.sub(r'\{\{[^}|]*\|([^}]*)\}\}', r'\1', text)
    text = re.sub(r'\{\{[^}]*\}\}', '', text)
    text = re.sub(r"'{2,}", '', text)
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    text = re.sub(r'<!--.*', '', text, flags=re.S)      # a comment left open to the end
    return ' '.join(text.split())


@functools.lru_cache(maxsize=None)
def twin_section(page):
    """The twin page's ==Strategy== section, raw wikitext."""
    with open(os.path.join(TWIN_PAGES, page + '.wiki'), encoding='utf-8') as f:
        text = f.read()
    m = re.search(r'^==\s*Strategy\s*==\s*$(.*?)(?=^==[^=]|\Z)', text, re.M | re.S)
    if not m:
        raise ValueError('%s has no ==Strategy== section' % page)
    return m.group(1)


def validate(claims, section, where):
    """Raise on a claim of an unknown kind, a missing field, a bad step, or a citation that
    is not in `section`. Returns `claims`."""
    body = plain(section)
    for c in claims:
        kind = c.get('kind')
        if kind not in KINDS:
            raise ValueError('%s: unknown claim kind %r' % (where, kind))
        missing = KINDS[kind] - set(c)
        if missing:
            raise ValueError('%s: %s claim lacks %s' % (where, kind, ', '.join(sorted(missing))))
        if 'step' in c:
            raise ValueError('%s: a claim carries no step: its topic fixes it (TOPICS)' % where)
        if kind == 'unmodelled' and c['topic'] not in TOPICS:
            raise ValueError('%s: topic %r is not in the taxonomy (TOPICS)' % (where, c['topic']))
        if kind == 'kits' and c['topic'] not in KIT_TOPICS:
            raise ValueError('%s: kits topic %r is not one of %s'
                             % (where, c['topic'], sorted(KIT_TOPICS)))
        cite = plain(c.get('cite'))
        if not cite or cite not in body:
            raise ValueError('%s: %s claim cites a line its Strategy section does not have: %r'
                             % (where, kind, c.get('cite')))
    return claims


@functools.lru_cache(maxsize=None)
def _twin_file():
    with open(TWIN_CLAIMS, encoding='utf-8') as f:
        return yaml.safe_load(f)


def twin_claims(parity_ref):
    """The twin's claims, validated against its vendored Strategy section; [] if uncurated."""
    entry = _twin_file().get(parity_ref)
    if not entry:
        return []
    return validate(entry['claims'], twin_section(entry['page']), parity_ref)


def our_claims(chap):
    """The chapter's `strategy_claims`, validated against its own `strategy:`."""
    return validate(chap.get('strategy_claims') or [], chap.get('strategy') or '',
                    chap.get('id') or chap.get('chapter_number'))


# ── Who is who: labels for each body of a force ─────────────────────────────────

def _norm(token):
    return str(token).lower().replace('class_', '').replace('character_', '').replace('_', '-')


def our_labels(chap, mode=None):
    """(name, type, labels) per body of `chap`'s force, in `difficulty.chapter_units` order. The type
    is the body's name (our ids are authored per unit type); the labels add its class,
    'boss' for a boss and 'convertible' for a convertible."""
    shifts = dif.inject.chapter_settings.chapter_difficulty_shifts(chap) if mode else None
    out = []
    for ed, u in dif.chapter_units(chap, mode=mode, shifts=shifts):
        cls = ed.get('class') or u.name[len(ed.get('id', '')) + 1:]
        labels = {_norm(ed.get('id', '')), _norm(u.name), _norm(cls)}
        labels |= {'boss'} if ed.get('is_boss') else set()
        labels |= {'convertible'} if ed.get('convertible') else set()
        out.append((u.name, _norm(u.name), frozenset(labels)))
    return out


def twin_labels(parity_ref, mode=None):
    """(name, type, labels) per body of the twin's force, in `vanilla_enemy_bodies` order. The type
    is the character for a named unit, else the class; the labels hold both, 'boss' for a
    CA_BOSS character and 'convertible'."""
    import exp_curve                        # exp_curve imports difficulty
    stem = dif.PARITY_REFERENCE_STEM.get(parity_ref)
    conv = dif._vanilla_convertible_chars(stem) if stem else set()
    out = []
    for _a, _i, d, c in dif.vanilla_loaded_units(parity_ref, mode):
        char = d['charIndex']
        labels = {_norm(d['classIndex'])}
        if char.startswith('CHARACTER_'):
            labels.add(_norm(char))
            if 'CA_BOSS' in exp_curve.character_attributes(char):
                labels.add('boss')
        if char in conv:
            labels.add('convertible')
        named = char.startswith('CHARACTER_')
        out.append((c.name, _norm(char) if named else _norm(d['classIndex']),
                    frozenset(labels)))
    return out


def matches(labels, vs):
    """Does a body with `labels` answer to `vs` (a name, 'all', or a list of names)?"""
    if isinstance(vs, list):
        return any(matches(labels, v) for v in vs)
    return vs == 'all' or _norm(vs) in labels


# ── Terrain: reported ───────────────────────────────────────────────────────────

def _terrain_counts(cells):
    ids = dif._terrain_tables()[0]
    out = {}
    for t in cells:
        out[ids.get(t)] = out.get(ids.get(t), 0) + 1
    return out


@functools.lru_cache(maxsize=None)
def twin_tiles(parity_ref):
    """{TERRAIN_ name: tiles} on the twin's map."""
    return _terrain_counts(t for row in dif.vanilla_terrain(parity_ref) for t in row)


@functools.lru_cache(maxsize=None)
def our_tiles(maps, stem):
    """{TERRAIN_ name: tiles} on one of our painted maps."""
    return _terrain_counts(map_donor.our_terrain(stem, maps)[2])


def chapter_tiles(chap, campaign=campaign_chapters.CAMPAIGN):
    """{TERRAIN_ name: tiles} on the map `chap` declares, {} for a chapter with none."""
    path = (chap.get('map') or {}).get('file')
    if not path:
        return {}
    maps = os.path.dirname(os.path.join(REPO, 'campaigns', campaign, path))
    return our_tiles(maps, os.path.splitext(os.path.basename(path))[0])


def _terrain_line(claim, tiles):
    tile = dif._terrain_key(claim['tile'])
    vs = claim['vs']
    if not tiles.get(tile):
        return 'MISS terrain %s vs %s: the map has no %s' % (claim['tile'], vs, tile)
    avo, dfn, res = dif.terrain_cover(tile)
    return 'note terrain %s vs %s: %d on the map (+%d avo, +%d def, +%d res on foot)' % (
        claim['tile'], vs, tiles[tile], avo, dfn, res)


# ── The checks ──────────────────────────────────────────────────────────────────

def _units(claim):
    u = claim['unit']
    return [_norm(x) for x in (u if isinstance(u, list) else [u])]


def _reinforcement_line(side, arrivals):
    late = [k for k, turn in enumerate(arrivals or ()) if turn > 1]
    if not late:
        return 'note reinforcements: none arrive after turn 1 on this side\'s board'
    g = side.get('engagement')
    inside = sorted(set(late) & set(g.members)) if g else []
    where = ('' if g is None else ' (a %s on enemy phase %d)' % (g.kind, g.phase))
    return ('note reinforcements: %d bodies arrive after turn 1 (turns %s); %d of them in the '
            'heaviest engagement%s' % (len(late), ', '.join(str(t) for t in sorted(
                {arrivals[k] for k in late})), len(inside), where))


def _check(claim, bodies, per_enemy, labels, lines, tiles, side=None, arrivals=None):
    """One finding line for one modelled claim on one side, None for the rest. `bodies` is
    the side's force (mean lines), `per_enemy` its matchup row per body, `labels` its
    (type, labels) per body, `lines` {unit: median line} for its fielded team, `side` its
    `party_matchup` read and `arrivals` the turn each body arrives (None without a board)."""
    import fe_combat as fc
    kind, vs = claim['kind'], claim.get('vs')
    if kind == 'unmodelled' or kind in PLAYED_ONLY:
        return None
    if kind == 'kits':
        return ('note kits %s: modelled (#510 step 8) -- the verdict reads the happy path, '
                'the guaranteed path is printed beside it' % claim['topic'])
    if kind == 'terrain':
        return _terrain_line(claim, tiles)
    if kind == 'reinforcements':
        return _reinforcement_line(side or {}, arrivals)
    hit = [k for k, (_t, lab) in enumerate(labels) if matches(lab, vs)]
    if not hit:
        return 'MISS %s vs %s: no such enemy in the force' % (kind, vs)
    if kind == 'threat':
        load = {}
        for (_n, threat, _c, _w), (t, lab) in zip(per_enemy, labels):
            if 'convertible' not in lab:
                load[t] = load.get(t, 0.0) + threat
        named = [labels[k][0] for k in hit if labels[k][0] in load]
        if not named:
            return 'MISS threat %s: only convertibles carry it' % vs
        ranked = sorted(load, key=load.get, reverse=True)
        top = min(named, key=ranked.index)
        rank = ranked.index(top) + 1
        return ('%s threat %s: rank %d of %d enemy types by summed threat (%s %.1f; heaviest '
                '%s %.1f)' % ('OK  ' if rank == 1 else 'MISS', vs, rank, len(ranked), top,
                              load[top], ranked[0], load[ranked[0]]))
    names = _units(claim)
    by_norm = {_norm(m): line for m, line in lines.items()}
    present = [u for u in names if u in by_norm]
    if not present:
        return 'MISS %s %s vs %s: not fielded (team: %s)' % (
            kind, '/'.join(names), vs, ', '.join(lines))
    targets = [bodies[k] for k in hit]
    if kind == 'answer':
        # Any listed unit whose best matchup is `vs` holds the claim. The line, not the boss:
        # "train her on the Fighters" weighs them against the other generics, and a Rapier
        # triples on vanilla Ch1's armoured boss.
        reads = []
        for m in present:
            rounds = {}
            for b, (t, lab) in zip(bodies, labels):
                if 'boss' not in lab or matches(lab, vs):
                    rounds[t] = min(rounds.get(t, float('inf')),
                                    fc.rounds_to_kill(by_norm[m], b))
            target = min(fc.rounds_to_kill(by_norm[m], b) for b in targets)
            best = min(rounds, key=rounds.get)
            reads.append((target > rounds[best], m, target, best, rounds[best]))
        miss, m, target, best, top = min(reads)
        return '%s answer %s vs %s: %.1f rounds to kill (its best: %s %.1f)' % (
            'MISS' if miss else 'OK  ', m, vs, target, best, top)
    if kind == 'carry':
        score = {m: max(fc.rounds_to_kill(line, b) for b in targets)
                 for m, line in by_norm.items()}
        ranked = sorted(score, key=score.get)
        word = 'rounds to kill'
    else:                                   # wall: survives longest
        score = {m: dif.durability(line, targets) for m, line in by_norm.items()}
        ranked = sorted(score, key=score.get, reverse=True)
        word = 'rounds to fall'
    best = min(present, key=ranked.index)
    rank = ranked.index(best) + 1
    return '%s %s %s vs %s: rank %d of %d by %s (%s %.1f; best %s %.1f)' % (
        'OK  ' if rank == 1 else 'MISS', kind, '/'.join(names), vs, rank, len(ranked), word,
        best, score[best], ranked[0], score[ranked[0]])


def findings(chap, matchup, mode=None, campaign=campaign_chapters.CAMPAIGN):
    """{'ours': ([claim], [line]), 'twin': (...)}: each side's validated claims, and every
    modelled one checked against that side's own read in `matchup`
    (`difficulty.chapter_matchup`)."""
    if chap.get('status') == 'planned':
        # ADR 0363: an unwritten chapter gets no reading, and the claims curated for the
        # vanilla baseline past Ch7 are bot data only.
        raise ValueError('%s is planned: no strategy reading (ADR 0363)' % chap.get('id'))
    ref = chap.get('parity_reference')
    our_force, van_force = matchup['forces']
    out = {}
    our_turns, van_turns = matchup['arrivals']
    for key, claims, side, force, labels, lines, tiles, turns in (
            ('ours', our_claims(chap), matchup['ours'], our_force, our_labels(chap, mode),
             matchup['lines'], chapter_tiles(chap, campaign), our_turns),
            ('twin', twin_claims(ref), matchup['vanilla'], van_force, twin_labels(ref, mode),
             matchup['lines_vanilla'], twin_tiles(ref), van_turns)):
        # Labels come from a second walk of the force; it must be the same bodies in the
        # same order, or every check reads another unit.
        if [n for n, _t, _lab in labels] != [b.name for b in force]:
            raise ValueError('%s: the labels do not walk the force body for body' % key)
        labels = [(t, lab) for _n, t, lab in labels]
        checked = (_check(c, force, side['per_enemy'], labels, lines, tiles, side, turns)
                   for c in claims)
        out[key] = (claims, [f for f in checked if f])
    return out


def unmodelled_lines(claims):
    """The report's lines for a side's unmodelled claims: what a later #510 step inherits,
    then what is out by decision."""
    out = {}
    for c in claims:
        if c['kind'] == 'unmodelled':
            out.setdefault(step_of(c), []).append(c['topic'])
    return (['    unmodelled, step %d: %s' % (s, ', '.join(out[s]))
             for s in sorted(k for k in out if k != 'out')]
            + (['    not modelled (ADR 0365): %s' % ', '.join(out['out'])] if 'out' in out else []))


def print_strategy(chap, campaign, mode=None):
    """The `make difficulty` section: each side's claims, checked, and what later steps
    inherit."""
    print('\n-- STRATEGY CLAIMS (#510 step 6: reported, never an input) ' + '-' * 10)
    matchup = dif.chapter_matchup(chap, campaign, mode=mode)
    if matchup is None:
        print('  (no party read for this chapter -- claims not checked)')
        return
    read = findings(chap, matchup, mode, campaign)
    for key, label in (('ours', 'ours'), ('twin', chap.get('parity_reference'))):
        claims, lines = read[key]
        print('  %s:' % label)
        for line in lines or ['(no modelled claims)']:
            print('    %s' % line)
        for line in unmodelled_lines(claims):
            print(line)
