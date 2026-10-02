"""Raw-pid bodies: units with no character slot of their own, and their base levels.

Also the roster readers every level/difficulty tool shares (`chapter_roster_entries`,
`placed_entries`), which is where a raw-pid boss's level comes from.
"""
import re
import sys

from inject.cast import ENEMY_BASE_SLOT, RAW_PID_PORTRAITS
from inject.chapter_ids import (
    CH03_BOSS_PID, CH03_BRUTE_MINIBOSS_PID, CH03_CHAPTER_YAML, CH05_BOSS_PID, CH05_CHAPTER_YAML,
    CH05_MOOSE_PID, CH06_BOAT_PIDS, CH06_CHAPTER_YAML)
from inject.decomp import _find_brace_block
from inject.hosting import _load_chapter_yaml, chapter_yaml_for
from inject.hosts import hosted_chapters
from inject.paths import CHARACTERS_C
from inject.stats import _set_field, BASE_FIELDS
from inject.text import raw_pid_name_text_id


def _bind_raw_pid_identity(block, marker, name_text_id, portrait_id):
    """Point one gCharacterData gap row at a donor's name, and optionally at its bust.

    `portrait_id` None = a NAME-ONLY donor: the row keeps its generic miniPortrait and gains no
    `.portraitId`, which is what a monster donor like Morva has to offer. Writing one anyway
    would paint some other character's face onto the creature.
    """
    block = _set_field(block, 'nameTextId', '0x%X' % name_text_id, CHARACTERS_C, marker)
    if portrait_id is None:
        return block
    if re.search(r'\.portraitId\s*=', block):
        return _set_field(block, 'portraitId', '0x%X' % portrait_id, CHARACTERS_C, marker)
    pat = re.compile(r'(?m)^(\s*\.defaultClass\s*=\s*[^,\n]+,\s*\n)')
    block, count = pat.subn(
        lambda m: m.group(1) + '        .portraitId = 0x%X,\n' % portrait_id, block, count=1)
    if count != 1:
        sys.exit('ERROR: .defaultClass insertion point not found in %s entry %s'
                 % (CHARACTERS_C, marker))
    return block


def raw_pid_portrait_data(text, campaign):
    """Bind named raw-pid enemies to their authored identity and personal stat line.

    Raw 0xB0-range CharacterData gaps carry only a generic miniPortrait and omit portraitId,
    while their nameTextId points at the generic "Monster" message. Repoint the name to the
    donor slot's own message, and -- for a donor that HAS a bust -- insert the full portrait id.
    Named bosses also need their YAML `personal` bases written here: FE8 adds those
    CharacterData values to the deployed class bases, exactly as vanilla Ch5 does for Saar.

    A donor may be NAME-ONLY (`portrait_id` None). The white moose's is: it rides Morva, FE8's
    own named Great Dragon, which is a monster character with a miniPortrait and no portraitId
    at all -- the right donor shape for a monster, and the reason the moose gains a name without
    gaining a bust.

    The two bindings are INDEPENDENT (#284). A raw-pid boss can need a stat line and no identity
    at all -- ch03's grell keeps the generic monster name plate on purpose -- so the personal
    pass walks its own table rather than riding along inside the portrait loop. Coupling them
    would have made a `personal:` block silently do nothing for any pid without a bust.
    """
    for pid, (_unit_id, slot, portrait_id, _name) in sorted(RAW_PID_PORTRAITS.items()):
        marker = '[%s - 1]' % pid.lower()
        start, end = _find_brace_block(text, marker, CHARACTERS_C)
        block = _bind_raw_pid_identity(block=text[start:end], marker=marker,
                                       name_text_id=raw_pid_name_text_id(slot),
                                       portrait_id=portrait_id)
        text = text[:start] + block + text[end:]

    for pid, (chapter_yaml, unit_id) in sorted(RAW_PID_PERSONAL_SOURCES.items()):
        marker = '[%s - 1]' % pid.lower()
        start, end = _find_brace_block(text, marker, CHARACTERS_C)
        block = text[start:end]
        chapter = _load_chapter_yaml(campaign, chapter_yaml)
        unit = next((entry for entry in personal_bearers(chapter)
                     if entry.get('id') == unit_id), None)
        if unit is None or 'personal' not in unit:
            sys.exit('ERROR: raw pid %s personal source %s/%s is missing'
                     % (pid, chapter_yaml, unit_id))
        for field in BASE_FIELDS:
            block = _set_field(block, field, int(unit['personal'].get(field, 0)),
                               CHARACTERS_C, marker)
        text = text[:start] + block + text[end:]

    # baseLevel LAST and on its own table: a raw-pid boss needs this whether or not it has a
    # `personal:` line (the moose and the kobold brute have none), and without it the
    # difficulty malus resets the unit and rebuilds it from growths. See RAW_PID_LEVEL_SOURCES.
    for pid, level in sorted(raw_pid_base_levels(campaign).items()):
        marker = '[%s - 1]' % pid.lower()
        start, end = _find_brace_block(text, marker, CHARACTERS_C)
        block = _set_field(text[start:end], 'baseLevel', level, CHARACTERS_C, marker)
        text = text[:start] + block + text[end:]
    return text


def patch_raw_pid_portraits(campaign, verbose=True):
    """Write raw_pid_portrait_data() to the decomp CharacterData table."""
    stranded = unregistered_raw_pid_bosses(campaign)
    if stranded:
        sys.exit('ERROR: raw-pid boss(es) %s declare no baseLevel -- a gCharacterData gap '
                 'reads baseLevel 1, so the difficulty malus RESETS the unit to class base '
                 'and rebuilds it from growths, silently discarding its authored line (and '
                 'for a promoted class, handing it +9 levels it never had). Add a '
                 'RAW_PID_LEVEL_SOURCES row.' % ', '.join(stranded))
    with open(CHARACTERS_C, encoding='utf-8') as f:
        text = f.read()
    text = raw_pid_portrait_data(text, campaign)
    with open(CHARACTERS_C, 'w', encoding='utf-8') as f:
        f.write(text)
    if verbose:
        print('  %d raw-pid identity binding(s) patched' % len(RAW_PID_PORTRAITS))
# The chapter YAML is the authority for named raw-pid boss bases. These values cannot flow
# through patch_character_data(), which only visits the regular CHARACTER_* portrait map.
RAW_PID_PERSONAL_SOURCES = {
    CH05_BOSS_PID: (CH05_CHAPTER_YAML, 'ravisin'),
    # ch03's grell (#284). Unlike Ravisin it has no entry in RAW_PID_PORTRAITS -- it keeps the
    # generic monster name plate -- which is exactly why the personal pass had to stop being a
    # passenger inside the portrait loop. Its gap's bases are all zeros in vanilla, so without
    # this row the boss really does fight as a naked Mogall and folds in 1.1 rounds.
    CH03_BOSS_PID: (CH03_CHAPTER_YAML, 'grell'),
    # ch06's west hull (#26). A rescue hull is a raw-pid unit like a boss, and its line is
    # what the clock is measured on: CLASS_FLEET's 19 HP + 9 = 28 restores vanilla Ch6's
    # foot slack (the chapter YAML says why).
    CH06_BOAT_PIDS['boat-west']: (CH06_CHAPTER_YAML, 'boat-west'),
}


def personal_bearers(chapter):
    """Every entry in a chapter that may carry a `personal:` line: its enemy roster, every
    key, and its rescue hulls."""
    return (list(chapter_roster_entries(chapter))
            + [b for b in chapter.get('rescue_boats') or () if isinstance(b, dict)])
# Named raw-pid creatures whose BATTLE ANIM binds to a gCharacterData gap instead of a
# vanilla CHARACTER_ slot. Row = unit id -> (chapter YAML that declares it, its raw pid).
# The chapter YAML is the authority, exactly as it is for RAW_PID_PERSONAL_SOURCES above:
# a raw-pid creature has no pcs/npcs file, and giving it one would define the unit twice and
# put a miniboss on the deployable cast roster.
# Raw-pid BOSSES must declare a baseLevel, or the difficulty malus wipes their stat line.
#
# `UnitAutolevelPenalty` (bmunit.c) only fires `if (level > pCharacterData->baseLevel)`, and
# EVERY vanilla named boss ships baseLevel >= the level it deploys at: Saar 8/8, Breguet 4/4,
# Bazba 6/6, Novala 10/7, Murray 12/9. That is not a coincidence -- it is how vanilla protects
# a hand-authored boss line, so the same stats reach the map in all three difficulty modes.
#
# Our bosses on vanilla CHARACTER_ slots (ENEMY_BASE_SLOT) inherit that for free. The ones on
# RAW pids sit in gCharacterData GAPS, where baseLevel reads 1 -- so the penalty always fired,
# reset them to class base and rebuilt them from class growths. Measured in-engine: Ravisin
# came out 40 maxHP on Normal against 35 on Difficult, an INVERSION, because the reset path
# re-runs full `UnitAutolevel` -- promoted branch included, +9 levels of growth
# (GetCurrentPromotedLevelBonus) -- while the Difficult path calls `UnitAutolevelCore` direct
# and never grants it. All four raw-pid bosses were affected; the two promoted ones loudest.
#
# Row = raw pid -> (chapter YAML that declares the unit, its unit id). The LEVEL is read from
# the chapter YAML rather than repeated here, so baseLevel cannot drift from the level the unit
# actually deploys at. Guarded by unregistered_raw_pid_bosses(): the failure is silent, because
# a CharacterData gap is all zeros and nothing complains.
RAW_PID_LEVEL_SOURCES = {
    CH03_BOSS_PID:           (CH03_CHAPTER_YAML, 'grell'),
    CH03_BRUTE_MINIBOSS_PID: (CH03_CHAPTER_YAML, 'kobold-steel'),
    CH05_BOSS_PID:           (CH05_CHAPTER_YAML, 'ravisin'),
    CH05_MOOSE_PID:          (CH05_CHAPTER_YAML, 'white-moose'),
}


def raw_pid_base_levels(campaign):
    """Raw pid -> the baseLevel it must carry, read from the level it deploys at."""
    out = {}
    for pid, (chapter_yaml, unit_id) in RAW_PID_LEVEL_SOURCES.items():
        level = _entry_base_level_in(_load_chapter_yaml(campaign, chapter_yaml), unit_id)
        if level is None:
            sys.exit('ERROR: RAW_PID_LEVEL_SOURCES names %s/%s, which does not exist'
                     % (chapter_yaml, unit_id))
        out[pid] = level
    return out


# The keys a chapter YAML may hold enemy entries under. ONE definition, because every
# reader of "what units does this chapter field" must agree: the parity metric, the AI-donor
# guard, the personal-line routes and the raw-pid boss registry all key off it, and ch02
# spent four chapters with its `reinforcements:` wave counted by some of them and not others
# (decisions.md -> "A parity ratio does not say how much of the twin it COPIED").
ENEMY_ROSTER_KEYS = ('enemy_units', 'reinforcements', 'enemy_reinforcements')


# Every roster key that PLACES a body on the map, enemy or not. `ENEMY_ROSTER_KEYS` is the
# enemy half and is what the difficulty math grades; a recruit can be placed by either half,
# because `recruit_initial_faction` defaults to GREEN (a neutral bystander recruited in place,
# the Colm/Neimi pattern) and only opts into RED. A reader asking "what level does this unit
# deploy at" that sees one half is the #368 failure in a new key.
PLACED_ROSTER_KEYS = ENEMY_ROSTER_KEYS + ('neutral_units', 'green_allies')


def placed_entries(chap):
    """Every entry that places a body, across ALL roster keys (see PLACED_ROSTER_KEYS)."""
    return [ed for key in PLACED_ROSTER_KEYS for ed in (chap.get(key) or [])
            if isinstance(ed, dict)]


def chapter_roster_entries(chap):
    """Every enemy entry a chapter fields, across ALL of its roster keys.

    A reinforcement wave is part of the force. The vanilla twins' curated UnitDefinition
    arrays fold their own waves in unconditionally (vanilla Ch2's `UnitDef_088B4470`,
    vanilla Ch6's Hard-mode array), so a reader that takes only the opening board compares
    seven bodies against nine and scores the two missing ones as divergence.
    """
    return [ed for key in ENEMY_ROSTER_KEYS for ed in (chap.get(key) or [])
            if isinstance(ed, dict)]


def entry_is_turn1(key, enemy_def):
    """Is this entry's body standing on the board at TURN 1, before the player's first move?

    The KEY decides it, not `arrives_turn` alone: only `enemy_units` is the opening-board
    array, and even then only unconditionally -- an entry there may still declare its OWN
    `arrives_turn > 1` (ch06's Difficult-only crab-rider wave stays inside `enemy_units` for
    exactly this reason, so its own field is what excludes it). A `reinforcements:` or
    `enemy_reinforcements:` entry is never turn-1 regardless of what it carries, and that
    matters because those entries use a DIFFERENT field for their own timing --
    `trigger_turn`, not `arrives_turn` (ch02's `rear-raiders`). Two readers tested
    `arrives_turn` alone against every key and both read a `trigger_turn` wave as turn-1,
    which is backwards: a reinforcement key is the one shape definitely not on the opening
    board (`difficulty.chapter_enemy_groups`'s dynamics split, and
    `map_placement_preview.enemy_bodies`'s Dijkstra blockers, #367)."""
    return key == 'enemy_units' and entry_arrival_turn(enemy_def) <= 1


ARRIVAL_TURN_FIELDS = ('arrives_turn', 'trigger_turn', 'spawn_turn')


def entry_arrival_turn(enemy_def):
    """The turn this entry's bodies reach the board: 1 unless it declares otherwise.

    Our chapters spell it four ways -- `arrives_turn` (ch04-ch06), `trigger_turn` (ch02's
    `reinforcements:` wave), `spawn_turn` (ch01's goblins, which its injector loads on turn
    3) and `arrives: {turn: N}` (ch08's seed) -- and a reader that knew only the first put
    ch01's wave on the opening board in every metric that asked (#440 review)."""
    for field in ARRIVAL_TURN_FIELDS:
        if enemy_def.get(field):
            return int(enemy_def[field])
    arrives = enemy_def.get('arrives')
    if isinstance(arrives, dict) and arrives.get('turn'):
        return int(arrives['turn'])
    return 1


def entry_body_levels(enemy_def):
    """The level of each BODY one enemy entry places, in order.

    `levels:` is a PER-BODY list and it is what the ROM contains -- the emitters zip it with
    `positions` to write one UnitDefinition per pair, so an entry carrying it declares an L2
    and an L3 rather than two copies of one level. Everything else is `count` (or, failing
    that, `positions`) bodies at the entry's `level`.

    Every field that states the body count states the SAME fact, so they must agree: a stale
    `count:` beside a `positions:` list models a force the ROM never emits, and since #367
    the parity metric compares body-for-body against the vanilla twin on it.
    """
    uid = enemy_def.get('id', enemy_def.get('name', 'enemy'))
    levels = enemy_def.get('levels')
    bag = (enemy_def.get('composition') or []) if 'class' not in enemy_def else None
    stated = [(f, n) for f, n in
              (('composition', len(bag) if bag else None),
               ('count', int(enemy_def['count']) if 'count' in enemy_def else None),
               ('positions', len(enemy_def['positions'])
                if enemy_def.get('positions') else None),
               ('levels', len(levels) if levels is not None else None))
              if n is not None]
    for field, n in stated:
        if n != stated[0][1]:
            raise ValueError('%r declares %s %d but %s %d -- they are the same fact and '
                             'they disagree' % (uid, stated[0][0], stated[0][1], field, n))
    count = stated[0][1] if stated else 1
    if count < 1:
        raise ValueError('%r places no body (%s %d)'
                         % (uid, stated[0][0] if stated else 'count', count))
    if levels is None:
        return [int(enemy_def.get('level', 1))] * count
    return [int(lv) for lv in levels]


def _entry_base_level_in(chap, unit_id):
    """The baseLevel the named unit deploys at, found across every roster key.

    Reads a DECLARED body level, so a boss authored `levels: [9]` writes baseLevel 9 rather
    than falling through to 1 -- which would make the ROM apply a difficulty malus while
    difficulty's `_our_base_level` models the same boss as immune to it."""
    unit = next((e for e in chapter_roster_entries(chap) if e.get('id') == unit_id), None)
    return None if unit is None else max(entry_body_levels(unit))


def unregistered_raw_pid_bosses(campaign):
    """Boss/miniboss ids that ride a RAW pid but declare no baseLevel (sorted).

    A boss is raw-pid when it has no ENEMY_BASE_SLOT row -- that table is exactly "our enemy
    id -> the vanilla CHARACTER_ slot it deploys on", and a raw-pid boss has no entry by
    construction. The prologue's zeroed guests are excluded: they DO ride vanilla slots (only
    their base STATS are zeroed), so their baseLevel is the slot's and the penalty is already
    governed by vanilla's own number."""
    return sorted(uid for chapter in hosted_chapters()
                  for uid in _unregistered_raw_pid_boss_entries(
                      _load_chapter_yaml(campaign, chapter_yaml_for(chapter.name))))


def _unregistered_raw_pid_boss_entries(chap):
    """The same question for ONE loaded chapter, over every roster key.

    difficulty's `_our_base_level` models a boss as malus-immune WHEREVER it is declared,
    and this registry is what makes that true, so the guard has to look wherever it is
    declared too."""
    registered = {unit_id for _yaml, unit_id in RAW_PID_LEVEL_SOURCES.values()}
    prologue_guests = {'sephek-kaltro'}
    return [enemy.get('id') for enemy in chapter_roster_entries(chap)
            if (enemy.get('is_boss') or enemy.get('is_miniboss'))
            and enemy.get('id') not in ENEMY_BASE_SLOT
            and enemy.get('id') not in registered
            and enemy.get('id') not in prologue_guests]
