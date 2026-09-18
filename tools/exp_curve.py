#!/usr/bin/env python3
"""The campaign's EXP economy, and the party-level band derived from it (#367 proposal 3).

`difficulty.py` answers *is this chapter's force at parity with its vanilla twin*. It says
nothing about what the party BRINGS to that force, because `player_combatant` resolves the
cast at base level on purpose -- the parity ratio compares two forces against a fixed
yardstick and a projected party level would break that cancellation rather than improve it.

So every ABSOLUTE question -- *can this unit survive that trip, is this fuse long enough for
a real party, is this objective a coin flip* -- has had no floor to stand on. During #26 a
ch06-era flier was assessed off her LEVEL 1 stat line and a chapter's design nearly turned
on it.

This is that floor, and it is DERIVED rather than asserted: FE8's own exp formulas
(`fireemblem8u/src/bmbattle.c`, transcribed below and cited per function) run over the real
per-chapter rosters -- ours and each chapter's vanilla twin -- and the party's level curve
falls out of the enemy force it eats.

    python3 tools/exp_curve.py                 # the per-chapter table
    python3 tools/exp_curve.py --write         # regenerate the block in the pacing doc

WHAT IT MODELS, AND WHAT IT DOES NOT. Every body on a chapter's roster dies once, to one
member of the deployed party, and the chapter's exp is then split evenly across the deploy
cap. That is why the answer is a BAND and not a point: an even split understates the units
that lead and overstates the tail. Not modelled, on either side: chip damage that does not
kill (which pays round exp and is left out of both sides), staff and arena exp, and the exp
a player farms by choosing to. All of those ADD, so the curve here is a floor.

Stat GROWTH is deliberately not modelled (#367): growths are random, and a level is the
planning quantity -- a projected stat line would be a precision the dice do not support.
"""
import argparse
import dataclasses
import functools
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_campaign as bc
import difficulty as d

REPO = bc.REPO
PACING_DOC = os.path.join(REPO, 'docs', 'fe8-pacing-reference.md')

# The generated block's fence in docs/fe8-pacing-reference.md. Everything between these two
# lines is rewritten by --write; everything outside is hand-written prose and is never
# touched.
BEGIN = '<!-- BEGIN GENERATED: party-level band (python3 tools/exp_curve.py --write) -->'
END = '<!-- END GENERATED: party-level band -->'

# One level is 100 exp (bmunit.c UNIT_EXP_DISABLED / the level-up threshold in
# BattleApplyExpGains: `if (unit->exp >= 100)`).
EXP_PER_LEVEL = 100


# ---------------------------------------------------------------------------------------
# ClassData reads. Vanilla data, so HEAD text through build_campaign.vanilla_decomp_text --
# never the working tree, which the build mutates.
# ---------------------------------------------------------------------------------------

def _classes_text():
    return bc.vanilla_decomp_text('src/data_classes.c')


@functools.lru_cache(maxsize=None)
def _class_block(class_enum):
    text = _classes_text()
    s, e = bc._find_brace_block(text, '[%s - 1]' % class_enum, bc.CLASSES_C)
    return text[s:e]


@functools.lru_cache(maxsize=None)
def class_relative_power(class_enum):
    """`.classRelativePower` -- vanilla's own price list for a class, and the term that does
    the work in every formula below. It divides round exp (a Soldier's crp 2 pays half again
    what a Fighter's crp 3 does) and multiplies power level."""
    m = re.search(r'\.classRelativePower\s*=\s*(\d+)', _class_block(class_enum))
    if not m:
        raise ValueError('%s has no .classRelativePower in data_classes.c' % class_enum)
    return int(m.group(1))


@functools.lru_cache(maxsize=None)
def class_attributes(class_enum):
    """The `CA_*` flags on a class, as a frozenset. Empty for a class with no `.attributes`
    line at all (CLASS_PIRATE, CLASS_SOLDIER) -- absent means zero, not inherited."""
    m = re.search(r'\.attributes\s*=\s*([^;]*?),\n', _class_block(class_enum))
    if not m:
        return frozenset()
    return frozenset(t.strip() for t in m.group(1).split('|') if t.strip())


@functools.lru_cache(maxsize=None)
def class_promotion(class_enum):
    """`.promotion`. On an UNPROMOTED class this is what it promotes into; on a PROMOTED one
    the decomp stores the class it came FROM (Paladin -> Cavalier), which is exactly what
    GetUnitPowerLevel reads. `None` when the field is absent or 0."""
    m = re.search(r'\.promotion\s*=\s*(\w+)', _class_block(class_enum))
    if not m or m.group(1) == '0':
        return None
    return m.group(1)


@functools.lru_cache(maxsize=None)
def character_attributes(char_enum):
    """The `CA_*` flags on a CHARACTER slot (data_characters.c), where CA_BOSS actually
    lives -- a boss is a character, never a class. Empty for a generic or unknown slot."""
    if not char_enum or not str(char_enum).startswith('CHARACTER_'):
        return frozenset()
    text = bc.vanilla_decomp_text('src/data_characters.c')
    try:
        s, e = bc._find_brace_block(text, '[%s - 1]' % char_enum, bc.CHARACTERS_C)
    except SystemExit:
        return frozenset()
    m = re.search(r'\.attributes\s*=\s*([^;]*?),\n', text[s:e])
    if not m:
        return frozenset()
    return frozenset(t.strip() for t in m.group(1).split('|') if t.strip())


# ---------------------------------------------------------------------------------------
# The formulas, transcribed from fireemblem8u/src/bmbattle.c at HEAD.
# ---------------------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Fighter:
    """One body in the exp math: a class, a level, and whether the ROM marks it a boss.

    `boss` is the CA_BOSS bit as the BUILT ROM carries it, which is not the same question as
    "is it the chapter's objective". Our bosses that ride a vanilla CHARACTER slot inherit
    that slot's CA_BOSS; one on a raw pid has an all-zero CharacterData and carries none, so
    it pays 40 less exp than the vanilla boss it is measured against."""
    name: str
    class_enum: str
    level: int
    boss: bool = False

    @property
    def promoted(self):
        return 'CA_PROMOTED' in class_attributes(self.class_enum)

    @property
    def relative_power(self):
        return class_relative_power(self.class_enum)


def exp_level(fighter):
    """GetUnitExpLevel."""
    return fighter.level + (20 if fighter.promoted else 0)


def round_exp(actor, target):
    """GetUnitRoundExp -- what a single ROUND of combat pays, kill or no kill."""
    gap = exp_level(actor) - exp_level(target)
    bracket = 31 - gap
    if bracket < 0:
        bracket = 0
    return bracket // actor.relative_power


def power_level(fighter):
    """GetUnitPowerLevel."""
    result = fighter.level * fighter.relative_power
    promo = class_promotion(fighter.class_enum)
    if fighter.promoted and promo:
        result += 20 * class_relative_power(promo)
    return result


def class_kill_exp_bonus(target):
    """GetUnitClassKillExpBonus -- the premium on a body that is worth more than its level.

    CLASS_ENTOUMBED is named in the decomp by class number, beside the attribute tests, and
    is kept literal here for the same reason the decomp keeps it: it is the one class whose
    kill bonus is not derivable from its flags."""
    result = 0
    attrs = class_attributes(target.class_enum)
    if 'CA_THIEF' in attrs:
        result += 20
    if target.boss:
        result += 40
    if target.class_enum == 'CLASS_ENTOUMBED':
        result += 40
    return result


def kill_exp_bonus(actor, target):
    """GetUnitKillExpBonus on the COMMON route -- the only branch our campaign can reach.

    The function has two: `(gBmSt.gameStateBits & 0x40) || (gPlaySt.chapterModeIndex != 1)`
    takes the plain `target - actor` penalty, and the else -- chapterModeIndex == 1, the
    common route -- HALVES the actor's power when the target is the weaker of the two. That
    generosity is not an option we picked: `savemenu.c:537` starts every new game at mode 1,
    and only `ch8-eventscript.h` (the Eirika/Ephraim route split, which we have no world map
    to reach) ever writes another value. 0x40 is BM_FLAG_LINKARENA. So mode 1 is our whole
    campaign -- and it is also FE8's own Prologue-Ch8, which is every twin we measure
    against."""
    result = 20
    tp, ap = power_level(target), power_level(actor)
    if tp <= ap:
        result += tp - ap // 2
    else:
        result += tp - ap
    result += class_kill_exp_bonus(target)
    if result < 0:
        result = 0
    return result


def battle_exp_gain(actor, target):
    """GetBattleUnitExpGain for a KILLING round: round exp + kill bonus, clamped to 1..100.

    The no-damage path (a flat 1) and ModifyUnitSpecialExp's special cases (gorgon egg 50,
    Demon King 0, Phantom actor 0) are not modelled -- none of those classes appears in
    ch00-ch06 or in their twins, and `unmodelled_special_exp_bodies` fails loudly if one
    ever does."""
    result = round_exp(actor, target) + kill_exp_bonus(actor, target)
    return max(1, min(100, result))


# Classes whose exp ModifyUnitSpecialExp overrides outright. If a roster ever fields one,
# this model is quietly wrong about it, so the simulation refuses to be quiet.
# Both egg classes: UNIT_IS_GORGON_EGG (bmunit.h) tests CLASS_GORGONEGG *and*
# CLASS_GORGONEGG2, and a guard that knows only the first still mis-prices half of them.
SPECIAL_EXP_CLASSES = ('CLASS_GORGONEGG', 'CLASS_GORGONEGG2', 'CLASS_DEMON_KING',
                       'CLASS_PHANTOM')


# ---------------------------------------------------------------------------------------
# The two rosters. Both sides must count the same KIND of thing -- every body the chapter
# fields, waves included -- which is the error #368 found in the parity metric.
# ---------------------------------------------------------------------------------------

def load_chapter(campaign, ch):
    with open(d.chapter_path(campaign, ch), encoding='utf-8') as f:
        return bc.yaml_load(f)


def _entry_boss(enemy_def):
    """Does this entry's body carry CA_BOSS in the BUILT ROM?

    Not the same question as `is_boss:`, which is our authoring flag for "the objective
    target". CA_BOSS lives on CharacterData, so a boss inherits it from the vanilla slot it
    deploys on (`ENEMY_CHARACTER_SLOT`) and a boss on a RAW pid -- whose CharacterData gap is
    all zeros -- carries none at all. The engine pays the +40 kill bonus off the ROM's
    answer, not off ours."""
    slot = bc.ENEMY_CHARACTER_SLOT.get(enemy_def.get('id'))
    return 'CA_BOSS' in character_attributes(slot)


def chapter_bodies(chap):
    """Every body our chapter fields, as Fighters. Staff-only units are KEPT: a healer
    contributes nothing to the threat math (which is why `difficulty` drops it) and a full
    kill's worth of exp to this one."""
    out = []
    for ed in bc.chapter_roster_entries(chap):
        name = ed.get('id', ed.get('name', 'enemy'))
        boss = _entry_boss(ed)
        levels = bc.entry_body_levels(ed)
        if 'composition' in ed and 'class' not in ed:
            classes = ed.get('composition') or []
        else:
            classes = [ed.get('class')] * len(levels)
        for cls, lv in zip(classes, levels):
            out.append(Fighter(name, d._enemy_class_enum(cls), int(lv), boss))
    return out


def vanilla_bodies(parity_ref):
    """Every RED body the twin fields, as Fighters. None when the reference is uncurated."""
    units = d.vanilla_red_units(parity_ref)
    if units is None:
        return None
    return [Fighter(u['charIndex'] or u['classIndex'], u['classIndex'], u['level'],
                    'CA_BOSS' in character_attributes(u['charIndex']))
            for u in units]


def party_classes(campaign):
    """(uid, class enum, first chapter number this unit can earn in) for the cast whose
    levels this band describes.

    `difficulty`'s own ROSTER, so there is one answer to "who is the party" in this repo,
    and `build_campaign.recruit_chapter_number` for when each joins -- the same answer
    `cast_available_at` sizes the deploy caps from. A recruit is on the field from the
    chapter AFTER the one that recruits it, and every recruit joins at level 1, so crediting
    one with the chapters before it joined hands it an exp history it never had."""
    out = []
    for uid in d.ROSTER:
        unit = dict(bc.load_unit(campaign, uid), id=uid)
        recruited = bc.recruit_chapter_number(campaign, unit)
        out.append((uid, bc.class_enum_for(unit),
                    0 if recruited is None else int(recruited) + 1))
    return out


def unmodelled_special_exp_bodies(campaign):
    """Bodies whose exp `ModifyUnitSpecialExp` overrides, which this model does not price.

    None exist in ch00-ch06 or their twins. When one does -- a gorgon egg, the Demon King --
    the model is quietly wrong about that chapter, and quiet is the failure mode this repo
    keeps paying for, so the simulation calls this and refuses to print instead."""
    found = []
    for chapter in bc.hosted_chapters():
        chap = bc._load_chapter_yaml(campaign, bc.chapter_yaml_for(chapter.name))
        sides = [(chap.get('id'), chapter_bodies(chap))]
        twin = vanilla_bodies(chap.get('parity_reference'))
        if twin is not None:
            sides.append((chap.get('parity_reference'), twin))
        for label, bodies in sides:
            found += ['%s: %s' % (label, b.class_enum) for b in bodies
                      if b.class_enum in SPECIAL_EXP_CLASSES]
    return sorted(set(found))


# ---------------------------------------------------------------------------------------
# The simulation.
# ---------------------------------------------------------------------------------------

# The band's edges. The centre is an even split of a chapter's exp across the deploy cap;
# the edges are the same chapters paying a unit that takes TWICE the average share and one
# that takes HALF. They are not the centre scaled: each edge runs its own career through
# every chapter, so FE8's own catch-up terms apply -- a unit that is already ahead earns
# less from the same body (round exp shrinks with the level gap, and the kill bonus
# subtracts the killer's power level). That TRIMS the spread rather than closing it: a 4x
# spread in share still ends as most of a 4x spread in exp, so the band is wide on purpose.
SHARE_LEAD, SHARE_TAIL = 2.0, 0.5

# Unpromoted units stop at 20. Promotion is not modelled (it is an ITEM the player spends
# when they choose to, and the seam is a design decision, not a curve) -- so a career that
# would pass the cap is held there and the row says the band is pinned rather than earned.
LEVEL_CAP = 20


class Career:
    """One unit's exp ledger across the campaign. Levels at 100 exp, as the engine does."""

    def __init__(self, name, class_enum, share=1.0, joins=0):
        self.name = name
        self.class_enum = class_enum
        self.share = share
        self.joins = joins          # first chapter_number this unit can earn in
        self.level = 1
        self.exp = 0

    @property
    def fighter(self):
        return Fighter(self.name, self.class_enum, self.level)

    def chapter_pot(self, bodies):
        """What this chapter pays THIS unit if it kills every body itself, at today's level.

        Resolved once per chapter rather than per kill: the unit's level moves during a
        chapter and modelling that would be a precision the rest of the model does not have
        (nothing here knows which body dies to whom, or in what order)."""
        me = self.fighter
        return sum(battle_exp_gain(me, body) for body in bodies)

    def fight(self, bodies, deploy_cap, chapter_number=None):
        if chapter_number is not None and chapter_number < self.joins:
            return 0
        gained = int(self.chapter_pot(bodies) * self.share / deploy_cap)
        self.exp += gained
        while self.exp >= EXP_PER_LEVEL and self.level < LEVEL_CAP:
            self.exp -= EXP_PER_LEVEL
            self.level += 1
        if self.level >= LEVEL_CAP:
            self.exp = 0
        return gained


def field_cap(chap):
    """How many player bodies this chapter fields -- the number its exp is split across.

    The `deployment:` cap where there is one, because that IS Pick Units: prep from ch01 on
    is standing protocol and the CAP is the parity (decisions.md -> the deploy cap / prep
    screen), so our cap and the twin's field are the same number by design and one split
    serves both sides. A fixed-roster chapter has no cap, and falling back to the whole
    roster would be wrong in the direction that matters: ch00 fields exactly Hlin and
    Scramsax, and splitting the prologue thirteen ways understates what its twin pays
    vanilla's two-unit field six-fold."""
    limit = (chap.get('deployment') or {}).get('deploy_limit')
    if limit is not None:
        return int(limit)
    return sum(len(bc.entry_body_levels(pu)) for pu in (chap.get('player_units') or []))


def _banks_exp(chap):
    """Does the PARTY fight this chapter -- i.e. does its exp reach the cast at all?

    Read off the deploy cap, because that is what Pick Units is: prep from ch01 on is
    standing protocol and the CAP is the parity (decisions.md -> the deploy cap / prep
    screen). A chapter with no cap is a FIXED-ROSTER chapter, and ours is ch00, whose two
    units are guests -- Hlin and Scramsax never join, so the prologue's exp is paid to
    nobody. Vanilla's prologue pays Eirika and Seth, who stay for the whole game, so the
    twin's curve banks a chapter ours does not. That asymmetry is real and it is the first
    thing the generated block says."""
    return (chap.get('deployment') or {}).get('deploy_limit') is not None


def _founding(careers):
    """Careers that have been on the field since the campaign began.

    The band's three columns are three SHARES of one career, so they are read over one
    population. Mixing a late recruit into the low edge pinned it at level 1 for every
    chapter after a recruitment, which stops being a statement about how much a unit is fed
    and becomes one about when it joined -- the recruit floor is its own column instead."""
    return [c for c in careers if c.joins == 0]


def _party(campaign, share=1.0):
    return [Career(uid, cls, share, joins) for uid, cls, joins in party_classes(campaign)]


def simulate(campaign='rime-of-the-frostmaiden'):
    """One row per HOSTED chapter, in chapter order, carrying the party level forward.

    Two parties are run: ours, fed our rosters, and a twin party fed each chapter's vanilla
    reference force. Both are OUR cast -- same classes, same `classRelativePower` -- so the
    only difference between the two curves is the enemy force, which is the comparison
    #367 asked for. The per-chapter `yield_ratio` is stricter still: both pots are measured
    against OUR party's state, so a ratio is never contaminated by the two curves having
    drifted apart."""
    special = unmodelled_special_exp_bodies(campaign)
    if special:
        raise ValueError('a roster fields a class ModifyUnitSpecialExp overrides, which this '
                         'model does not price: %s' % ', '.join(special))
    ours = _party(campaign)
    lead = _party(campaign, SHARE_LEAD)
    tail = _party(campaign, SHARE_TAIL)
    twin_party = _party(campaign)
    rows = []
    for chapter in bc.hosted_chapters():
        chap = bc._load_chapter_yaml(campaign, bc.chapter_yaml_for(chapter.name))
        bodies = chapter_bodies(chap)
        ref = chap.get('parity_reference')
        twin = vanilla_bodies(ref)
        cap = field_cap(chap)
        banks = _banks_exp(chap)
        number = int(chap.get('chapter_number'))
        # Both pots at OUR party's state, before anybody fights this chapter.
        pot = sum(c.chapter_pot(bodies) for c in ours) / len(ours)
        twin_pot = (sum(c.chapter_pot(twin) for c in ours) / len(ours)
                    if twin is not None else None)
        # The recruit floor, read at the START of the chapter: every recruit joins at level
        # 1, so the newest unit ON THE FIELD here is one this chapter has to be survivable
        # for. None until somebody has joined.
        newest = min([c.level for c in ours if c.joins and number >= c.joins] or [None])
        if banks:
            for career in ours + lead + tail:
                career.fight(bodies, cap, number)
        if twin is not None:
            # The twin party fights its own chapter whether or not ours banks this one
            # (see _banks_exp), and its members join on OUR recruitment schedule, so the
            # only difference between the two curves stays the enemy force.
            for career in twin_party:
                career.fight(twin, cap, number)
        rows.append({
            'id': chap.get('id'),
            'chapter_number': number,
            'reference': ref,
            'bodies': len(bodies),
            'twin_bodies': len(twin) if twin is not None else None,
            'field_cap': cap,
            'banks': banks,
            'pot': pot,
            'twin_pot': twin_pot,
            'yield_ratio': (pot / twin_pot) if twin_pot else None,
            'levels': {c.name: c.level for c in ours},
            'level_after': _mean_level(_founding(ours)),
            'level_after_exact': _mean_level_exact(_founding(ours)),
            'band_low': min(c.level for c in _founding(tail)),
            'band_high': max(c.level for c in _founding(lead)),
            'newest': newest,
            # Read over the FOUNDING careers, exactly as `level_after` is -- comparing a
            # mean over one population against a mean over another says nothing.
            'twin_level_after': (_mean_level(_founding(twin_party))
                                 if twin is not None else None),
        })
    return rows


def _mean_level_exact(careers):
    return sum(c.level + c.exp / EXP_PER_LEVEL for c in careers) / len(careers)


def _mean_level(careers):
    return int(_mean_level_exact(careers))


# ---------------------------------------------------------------------------------------
# The generated block in docs/fe8-pacing-reference.md.
# ---------------------------------------------------------------------------------------

def render(rows=None, campaign='rime-of-the-frostmaiden'):
    """The generated block, fences included. Everything it states is a column of `simulate`
    -- there is no prose here that the model cannot recompute."""
    rows = simulate(campaign) if rows is None else rows
    out = [BEGIN, '',
           '<!-- Derived from FE8\'s own exp formulas over the real rosters. Do not hand-edit:',
           '     the next regen silently discards it, and tools/test_exp_curve.py fails the',
           '     build while it is stale. -->', '',
           '| chapter | bar | field | exp ours/twin | benched | typical | fed | newest |',
           '|---|---|---|---|---|---|---|---|']
    for r in rows:
        ratio = ('%d / %d (x%.2f)' % (round(r['pot']), round(r['twin_pot']), r['yield_ratio'])
                 if r['yield_ratio'] else '%d / --' % round(r['pot']))
        out.append('| %s%s | %s | %d | %s | L%d | **L%d** | L%d | %s |'
                   % (r['id'].split('-')[0], '' if r['banks'] else ' †',
                      r['reference'] or '--', r['field_cap'], ratio,
                      r['band_low'], r['level_after'], r['band_high'],
                      ('L%d' % r['newest']) if r['newest'] is not None else '--'))
    last = rows[-1]
    nxt = 'ch%02d' % (last['chapter_number'] + 1)
    twin = ('L%d' % last['twin_level_after'] if last['twin_level_after'] is not None
            else '-- (%s is not a curated reference, so there is no twin curve)'
                 % (last['reference'] or 'its bar'))
    out += ['',
            '**Entering %s the party is L%d** -- L%d for a founding unit that rides the bench,'
            % (nxt, last['level_after'], last['band_low']),
            'L%d for one fed every kill, and **L1 for anyone recruited into it**, because every'
            % last['band_high'],
            'recruit joins at level 1 (`newest` is the lowest level actually on the field that',
            'chapter).', '',
            'The same cast fed each chapter\'s VANILLA twin instead of ours reaches **%s** over'
            % twin,
            'the same span: the party lands where FE8\'s party lands, which is what makes the',
            'absolute number usable.', '']
    unbanked = [r for r in rows if not r['banks']]
    if unbanked:
        out += ['† %s pays its exp to units the party never gets -- a fixed-roster chapter '
                'whose guests do' % ', '.join(r['id'].split('-')[0] for r in unbanked),
                'not join. Vanilla\'s prologue pays Eirika and Seth, who stay for the whole '
                'game, so the twin',
                'banks a chapter we do not. The two curves still converge, because FE8 pays a '
                'lower-level unit',
                'more for the same body.', '']
    out.append(END)
    return '\n'.join(out)


def rewrite(text, rows=None, campaign='rime-of-the-frostmaiden'):
    """`text` with the fenced block replaced. Raises when the fence is missing or malformed --
    a generator that appends its block when it cannot find the old one writes a second copy
    every run."""
    start, end = text.find(BEGIN), text.find(END)
    if start < 0 or end < 0 or end < start:
        raise ValueError('%s has no intact generated block (expected %r ... %r)'
                         % (os.path.relpath(PACING_DOC, REPO), BEGIN, END))
    return text[:start] + render(rows, campaign) + text[end + len(END):]


def print_table(rows):
    bar = '=' * 86
    print(bar)
    print('CAMPAIGN EXP CURVE -- the party level each chapter\'s force pays for')
    print('  exp is split across the field; the band is a unit taking %sx and %sx the '
          'average share' % (SHARE_TAIL, SHARE_LEAD))
    print(bar)
    print('  %-24s %-13s %6s %8s %8s   %s'
          % ('chapter', 'bar', 'field', 'exp', 'vs twin',
             'founding party after (low/typical/high) + newest'))
    for r in rows:
        print('  %-24s %-13s %6d %8d %8s   L%-2d L%-2d L%-3d %-8s%s'
              % (r['id'][:24], (r['reference'] or '--')[:13], r['field_cap'], round(r['pot']),
                 ('x%.2f' % r['yield_ratio']) if r['yield_ratio'] else '--',
                 r['band_low'], r['level_after'], r['band_high'],
                 ('newest L%d' % r['newest']) if r['newest'] is not None else '',
                 '' if r['banks'] else '   (fixed roster -- the party banks none of it)'))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--campaign', default='rime-of-the-frostmaiden')
    ap.add_argument('--write', action='store_true',
                    help='rewrite the generated party-level block in %s'
                         % os.path.relpath(PACING_DOC, REPO))
    args = ap.parse_args()
    rows = simulate(args.campaign)
    print_table(rows)
    if args.write:
        with open(PACING_DOC, encoding='utf-8') as f:
            have = f.read()
        want = rewrite(have, rows, args.campaign)
        if want != have:
            with open(PACING_DOC, 'w', encoding='utf-8') as f:
                f.write(want)
            print('\nwrote %s' % os.path.relpath(PACING_DOC, REPO))
        else:
            print('\n%s already current' % os.path.relpath(PACING_DOC, REPO))


if __name__ == '__main__':
    main()
