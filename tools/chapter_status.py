#!/usr/bin/env python3
"""`make chapter chNN` -- what a chapter has DECLARED against what is actually built (#312).

Half of ch05's commits touched only `docs/` or `HANDOFF.md`, which is a human writing down
state the repo already knows. Everything here is derived at the moment you ask, from the one
place each fact lives, so there is nothing to keep up to date and nothing to forget.

This is `terraform plan` pointed at a chapter. It is a LIVE command and not a committed
report: it reads playtest verdicts and cache state, which change without anything being
edited. The scene books under `docs/scenes/` are the opposite case -- deterministic, so they
are generated, committed and diffed.
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign_chapters

REPO = campaign_chapters.REPO

load = campaign_chapters.load
load_all = campaign_chapters.load_all

SceneRow = collections.namedtuple('SceneRow', 'trigger slot declared boxes preview presses')
Room = collections.namedtuple('Room', 'claimed block used_in_block borrowed free')


def _preview_module():
    """`scene_preview`, or None where it cannot be imported.

    It reaches build_campaign, which imports Pillow at module scope -- so on the lightweight
    CI job that installs pyyaml and nothing else this is absent, and a status report is still
    worth printing without its preview column. Everything else here is stdlib + pyyaml.
    """
    try:
        import scene_preview
        return scene_preview
    except ImportError:
        return None


def _previews_by_event(chapter_short):
    """(trigger, slot) -> the preview key that renders it, for one chapter.

    The registry carries the authored event each scene renders, so this is a join and not a
    third copy of the mapping. A branched scene registers both arms against the SAME event;
    the locked arm is the one a status row names, so later keys do not displace it.
    """
    sp = _preview_module()
    if sp is None:
        return {}
    out = {}
    for key, entry in sp.registry().items():
        if key.split('/')[0] != chapter_short or entry.event is None:
            continue
        out.setdefault(tuple(entry.event), key)
    return out


def _build_campaign():
    """`build_campaign`, or None where Pillow is absent (see `_preview_module`)."""
    try:
        import build_campaign
        return build_campaign
    except ImportError:
        return None


def _boxes(script):
    """Authored boxes in a script -- stage directions are not boxes.

    Delegates to `build_campaign._script_box_count`, which is what the injectors count with:
    a second implementation would drift the moment a directive was added, and the whole point
    of this report is that it cannot drift.
    """
    if not script:
        return 0
    bc = _build_campaign()
    if bc is None:
        # No directive vocabulary, so every count would be an OVERCOUNT (20 where ch05's
        # scene 1 has 19). A wrong number in the same column as the right ones, with nothing
        # to mark it, is worse than an honest blank.
        return None
    return bc._script_box_count(script)


_scenes_cache = {}


def scenes(name, campaign=campaign_chapters.CAMPAIGN):
    """Every authored event in a chapter: declared, how many boxes, and whether it can be seen.

    An event with no `script:` is a SEED -- a named beat with nothing written yet, which is
    exactly the "declared but unbuilt" row a human used to keep in HANDOFF by hand. It is
    reported rather than skipped.

    Memoised: rendering a chapter's previews is the expensive part of this report, and the
    summary and the table both want the same rows.
    """
    chapter = load(name, campaign)
    key = (campaign_chapters.short_id(chapter), campaign)
    if key in _scenes_cache:
        return _scenes_cache[key]
    previews = _previews_by_event(campaign_chapters.short_id(chapter))
    sp = _preview_module()
    rows = []
    for event in chapter.get('events') or ():
        trigger, slot = event.get('trigger'), event.get('slot')
        script = event.get('script')
        preview_key = previews.get((trigger, slot)) or previews.get((trigger, None))
        presses = None
        if preview_key and sp is not None:
            presses = len(sp.preview(preview_key, campaign).boxes)
        rows.append(SceneRow(trigger, slot, bool(script), _boxes(script),
                             preview_key, presses))
    _scenes_cache[(campaign_chapters.short_id(chapter), campaign)] = rows
    return rows


def message_ids(name, campaign=campaign_chapters.CAMPAIGN):
    """What a chapter has spent of its host block, and what is left in it.

    `free` counts ids NOBODY claims, not ids this chapter has not taken: a neighbour may hold
    one out of this block (ch05's ending borrowed two of ch04's), and reporting those as free
    would invite exactly the collision `assert_message_ids_unique` exists to refuse.

    A chapter with no declared block reports `block=None` -- ch01 predates the
    registry, and "0 free" would read as full when the truth is that nobody wrote it down.
    That is a different answer from `block=UNKNOWN`, which means the registry could not be
    read at all: ch05's block is FULL, and rendering it as "not declared" would make the
    tightest chapter in the campaign look like the ones nobody has measured.
    """
    chapter = campaign_chapters.short_id(load(name, campaign))
    bc = _build_campaign()
    if bc is None:
        return Room(None, UNKNOWN, (), (), None)
    claimed = tuple(sorted(set(bc.HOSTED_CHAPTER_MESSAGE_IDS.get(chapter, ()))))
    ranges = bc.message_block_ranges(chapter)
    if not ranges:
        return Room(claimed, None, (), (), None)
    owner = {}
    for other, ids in bc.HOSTED_CHAPTER_MESSAGE_IDS.items():
        for mid in ids:
            owner[mid] = other
    # A chapter may hold SEVERAL ranges (#335 follow-up): ch05 spent its slot-6 block to
    # zero and draws the rest from the never-shipped pool, so headroom sums across all of
    # them -- reading only the first would still report it FULL.
    inside = lambda m: any(lo <= m <= hi for lo, hi in ranges)
    used = tuple(sorted(m for m in owner if inside(m)))
    borrowed = tuple(sorted(m for m in used if owner[m] != chapter))
    capacity = bc.message_block_capacity(chapter)
    return Room(claimed, ranges, used, borrowed, capacity - len(used))


ArtRow = collections.namedtuple('ArtRow', 'unit role portrait map_sprite battle_anim missing')

# What a named unit needs, and where that asset lives. Platforms are NOT here: a battle
# platform is a property of the CHAPTER's ground, not of a unit, so it is reported once at
# chapter level out of CHAPTER_BATTLE_TILESETS (which check.py already requires to be total).
_ART = (('portrait', 'portraits/%s.png'),
        ('map_sprite', 'map_sprites/%s.png'),
        ('battle_anim', 'battle_anims/%s'))


def named_units(chapter):
    """The units a chapter INTRODUCES, with the role that makes each one named.

    Bosses, minibosses and recruits -- the units that carry an identity and therefore need
    art of their own. The generic line classes are deliberately absent: they wear the
    chapter's `skin:` reskin, so asking whether `tomb-reaver` has a portrait would report a
    permanent, meaningless gap.
    """
    out = collections.OrderedDict()
    for unit in chapter.get('enemy_units') or ():
        if not isinstance(unit, dict) or not unit.get('id'):
            continue
        if unit.get('is_boss'):
            out.setdefault(unit['id'], 'boss')
        elif unit.get('is_miniboss'):
            out.setdefault(unit['id'], 'miniboss')
    post = chapter.get('post_chapter') or {}
    for unit in post.get('units_available_to_recruit') or ():
        if isinstance(unit, dict) and unit.get('id'):
            out.setdefault(unit['id'], 'recruit')
    for unit in post.get('caravan_npcs_added') or ():
        if isinstance(unit, dict) and unit.get('id'):
            out.setdefault(unit['id'], 'npc')
    return out


def art(name, campaign=campaign_chapters.CAMPAIGN):
    """Which art each named unit has, and what it is still missing."""
    chapter = load(name, campaign)
    root = os.path.join(REPO, 'campaigns', campaign)
    rows = []
    for unit, role in named_units(chapter).items():
        have = {}
        for piece, pattern in _ART:
            path = os.path.join(root, pattern % unit)
            have[piece] = os.path.isdir(path) if '%s.png' not in pattern else os.path.isfile(path)
        rows.append(ArtRow(unit, role, have['portrait'], have['map_sprite'],
                           have['battle_anim'],
                           sorted(p for p, ok in have.items() if not ok)))
    return rows


def _donor_label(row):
    """`(x, y)` for a coordinate donor, the richer spec's own text otherwise, `override`
    where the unit declares one. The donor is the ANSWER to "where did this AI come from",
    so it has to stay readable at a glance rather than truncate into noise."""
    if row.override:
        return 'override'
    donor = row.donor
    if isinstance(donor, (list, tuple)) and len(donor) == 2 and all(
            isinstance(v, int) for v in donor):
        return '(%d,%d)' % (donor[0], donor[1])
    if isinstance(donor, dict):
        at = donor.get('at')
        if isinstance(at, (list, tuple)) and len(at) == 2:
            return '(%d,%d)' % (at[0], at[1])
        return ','.join('%s=%s' % kv for kv in sorted(donor.items()))[:14]
    return '--' if donor is None else str(donor)[:14]


# The AI2 index selects a script from the decomp's own `gAi2ScriptTable`
# (`cp_data.c:1548`, 19 entries), which `cp_script.c:90` reads as
# `gpAi2Table[0][gActiveUnit->ai2]`. This mapping is that table, and the tests pin it so the
# two cannot drift. Cite the tracked `.c`: `cp_data.s` is a BUILD ARTIFACT and is not at HEAD.
#
# The first eight names were all this map had, so the other ELEVEN indices reported as bare
# `0x0A`-style numbers -- including one vanilla's own PROLOGUE fields (#344). Thirteen are now
# named. The remaining SIX (0x08, 0x09, 0x0A, 0x0B, 0x0D, 0x0F) are named after bare addresses
# in the decomp too, so they stay UNNAMED here rather than being guessed at: an invented name
# would be indistinguishable from a known one at the call site.
AI_BEHAVIOUR = {
    0x00: 'pursue',
    0x01: 'pursue-ignore-char',        # MoveToEnemy_IgnoreChar_Unused1
    0x02: 'pursue-ignore-char',        # MoveToEnemy_IgnoreChar_Unused2
    0x03: 'never-move',
    0x04: 'pillage',
    0x05: 'pillage-escape',
    0x06: 'pursue-twice',
    0x07: 'pursue-twice-ignore-char',  # MoveTwiceToEnemy_IgnoreChar_Unused1
    0x0C: 'escape',                    # gAiScript_Escape
    0x0E: 'attack-walls-snags',        # gAiScript_AttackWallsSnags
    0x10: 'guard-tile',
    0x11: 'pillage-after-1',
    0x12: 'charge-after-1',
}

# The ACTION half, `gAi1ScriptTable` (cp_data.c). This is the half that MOVES, and reading only
# AI_B is what let a chapter be designed against the word "never-move": `AI_B_03 NeverMove` is
# `AI_NOP_0E` -- it only suppresses crossing the map -- while `AI_A_00 ActionInRange` is
# `AI_ACTION(100)`, and acting includes stepping within the unit's own range to reach a target.
# Measured when this landed: 94 of 99 campaign enemies are ActionInRange, and 48 of the 51 units
# reported as "threat you walk into" will move (decisions.md -> "AI_B is the APPROACH and AI_A is
# the ACTION"). Same naming discipline as AI_BEHAVIOUR: the twelve entries the decomp gives only
# an address (0x09..0x14) stay UNNAMED rather than guessed at.
AI_ACTION = {
    0x00: 'engage',                   # ActionInRange
    0x01: 'engage-80',                # ActionInRange_80Perc
    0x02: 'engage-50',                # ActionInRange_50Perc
    0x03: 'hold',                     # ActionStanding -- vanilla Ch6's Novala, and a true statue
    0x04: 'hold-80',                  # ActionStanding_80Perc
    0x05: 'hold-50',                  # ActionStanding_50Perc
    0x06: 'inert',                    # DoNothing -- vanilla Ch6's three green villagers
    0x07: 'engage-except-char',       # ActionInRange_ExceptNatasha (ch05's escort rides this)
    0x08: 'engage-except-civilian',   # ActionInRange_ExceptCivilian
}
# Whether the ACTION reaches for a target. `engage*` walks within its own move range to attack;
# `hold*` strikes only what is already adjacent; `inert` does nothing at all.
AI_ACTION_MOVES = frozenset({'engage', 'engage-80', 'engage-50',
                             'engage-except-char', 'engage-except-civilian'})
AI_ACTION_HOLDS = frozenset({'hold', 'hold-80', 'hold-50', 'inert'})

# Which APPROACH families cross the map at you, and which hold ground. Note this is no longer the
# whole story on its own -- a holding APPROACH still moves if its ACTION engages, which is what
# `ai_shape` exists to express.
AI_COMES_TO_YOU = frozenset({'pursue', 'pursue-ignore-char', 'pursue-twice',
                             'pursue-twice-ignore-char', 'charge-after-1',
                             'pillage', 'pillage-after-1'})
AI_HOLDS_GROUND = frozenset({'never-move', 'guard-tile'})
# Known behaviours that are NEITHER: the unit moves, but not at the player. A thief that loots
# and leaves, a script that flees, one that chews on walls. Folding these into "unclassified"
# said "we do not know" about three scripts the decomp names outright -- and ai2=0x05 alone
# occurs 120x in the reference files the parity twins already read (#359 review). "Known but
# neither" and "unknown" are different facts and the report keeps them apart.
AI_OWN_ERRAND = frozenset({'pillage-escape', 'escape', 'attack-walls-snags'})


def ai_family(ai2):
    """The APPROACH family for an AI2 index, or None where the decomp does not name one."""
    return AI_BEHAVIOUR.get(ai2)


def ai_action(ai1):
    """The ACTION family for an AI1 index, or None where the decomp does not name one."""
    return AI_ACTION.get(ai1)


def ai_shape(ai):
    """The three-way shape a FULL 4-byte vector describes, or None if either half is unnamed.

        pursuer     -- the approach walks it across the map at you
        striker     -- it holds ground, but its ACTION steps out within its own move range
        statue      -- it holds ground and does not move at all, even to attack
        own-errand  -- it moves, but not at the player (loots, flees, chews on walls)

    Two buckets could not express the middle one, and the middle one is most of the campaign:
    `{engage, never-move}` is vanilla's commonest pairing. ch06's clock was designed as though
    it meant `statue`, and four merfolk walked to a boat the design had them nowhere near.

    Takes the vector, never a single byte: a stale `ai_shape(ai[1])` would classify a whole
    roster off half the information and look entirely correct, so an int RAISES.
    """
    if isinstance(ai, int) or not hasattr(ai, '__len__') or len(ai) < 2:
        raise TypeError('ai_shape takes the 4-byte AI vector, not one byte -- the ACTION half '
                        '(ai[0]) is what decides whether the unit moves (got %r)' % (ai,))
    action, approach = ai_action(ai[0]), ai_family(ai[1])
    if action is None or approach is None:
        return None
    if approach in AI_OWN_ERRAND:
        return 'own-errand'
    if approach in AI_COMES_TO_YOU:
        return 'pursuer'
    if approach in AI_HOLDS_GROUND:
        return 'striker' if action in AI_ACTION_MOVES else 'statue'
    return None


def behaviour_split(ais):
    """{pursuer, striker, statue, own_errand, unclassified, n} over a sequence of AI VECTORS.

    Reported rather than folded into threat. #344 set out to WEIGHT threat by behaviour and the
    measurement said not to: since #335 derives every unit's AI from its vanilla donor, our
    behavioural shape IS the twin's, so a weighting would scale both sides of the ratio
    identically and always report x1.00. What is worth having is the split in the open, where a
    future divergence shows -- which only works if the split describes the whole vector.
    """
    out = {'pursuer': 0, 'striker': 0, 'statue': 0, 'own_errand': 0, 'unclassified': 0, 'n': 0}
    for ai in ais:
        out['n'] += 1
        shape = ai_shape(ai)
        if shape is None:
            out['unclassified'] += 1
        else:
            out[shape.replace('-', '_')] += 1
    return out

# `override` is a FLAG, not the vector: both _donor_label and the report's override list
# test it for truth, and an ai_override whose vector ever stringified to something falsy
# would silently drop out of both while still being an override.
AiRow = collections.namedtuple('AiRow', 'unit donor override why ai')


def _difficulty_module():
    """`difficulty`, which owns donor resolution. Imported lazily for the same reason
    `_preview_module` is: this report must still run where its heavier deps are absent."""
    try:
        import difficulty
        return difficulty
    except ImportError:
        return None


def ai(name, campaign=campaign_chapters.CAMPAIGN, missing_ok=False):
    """Where each enemy's AI comes from: the vanilla donor it is borrowed from, or the
    declared override and its reason (#335 scope item 3).

    AI used to be authored per-unit by feel, and nothing showed it -- #48's threat and
    clear-load are computed from stats and weapons, so a chapter could measure x1.00 and
    still play like a different map. It is derived now, and this is where that is legible
    without remembering to go looking.

    Empty for a chapter with no curated twin: there is nothing to borrow from, which is a
    `parity_reference` gap rather than an AI one -- the same rule ai_donor_findings uses.
    """
    try:
        chapter = load(name, campaign)
    except Exception:
        if missing_ok:
            return []
        raise
    difficulty = _difficulty_module()
    if difficulty is None:
        return []
    ref = chapter.get('parity_reference')
    if difficulty.PARITY_REFERENCE_UDEFS.get(ref) is None:
        return []
    rows = []
    for key in difficulty.AI_ROSTER_KEYS:
        for enemy in chapter.get(key) or []:
            if not isinstance(enemy, dict):
                continue
            override = enemy.get('ai_override') or {}
            positions = enemy.get('positions') or []
            for index in range(max(1, len(positions))):
                try:
                    emitted = difficulty.enemy_ai_bytes(chapter, enemy, index)
                except ValueError as error:
                    # A donor that cannot be resolved is exactly what the parity gate fails
                    # on. Say so here rather than dropping the unit off the report.
                    rows.append(AiRow(enemy.get('id'), None, None, str(error), None))
                    break
                specs = difficulty._donor_specs(enemy)
                donor = specs[index] if specs and index < len(specs) else enemy.get('donor')
                rows.append(AiRow(enemy.get('id'), None if override else donor,
                                  bool(override), override.get('why'), emitted))
    return rows


ScenarioRow = collections.namedtuple(
    'ScenarioRow', 'scenario rom kind covers verdict stored')


def _matrix_module():
    """`tools/playtest/matrix.py`, or None when it cannot be imported."""
    try:
        sys.path.insert(0, os.path.join(REPO, 'tools', 'playtest'))
        import matrix
        return matrix
    except ImportError:
        return None


UNKNOWN = 'unknown'      # could not be read, which is NOT the same as "not declared"


def _hosted(name, campaign, field):
    """One field of a chapter's host-registry row, or None when it is not hosted.

    Matched on the chapter NUMBER as well as the short id, because the registry and the YAML
    do not agree on what the prologue is called: `inject/hosts.py` says `prologue`, the YAML
    says `ch00`. On the id alone the prologue reported as unhosted, with two loose ends that
    were not true.
    """
    try:
        sys.path.insert(0, os.path.join(REPO, 'tools'))
        from inject import hosts
    except ImportError:
        return None
    chapter = load(name, campaign)
    short = campaign_chapters.short_id(chapter)
    number = int(chapter['chapter_number'])
    for hosted in hosts.hosted_chapters():
        if hosted.name == short or hosted.number == number:
            return getattr(hosted, field)
    return None


def host_slot(name, campaign=campaign_chapters.CAMPAIGN):
    """The vanilla chapter slot this chapter is hosted on, from the host registry.

    Not derivable from the chapter number: FE8 inserts chapter 5X, so the slot and the
    number part company from ch04 on. `inject/hosts.py` is where that is declared.
    """
    return _hosted(name, campaign, 'host_index')


def event_group(name, campaign=campaign_chapters.CAMPAIGN):
    """The ChapterEventGroup this chapter's injector fills, from the host registry."""
    return _hosted(name, campaign, 'event_group')


def scenarios(name, campaign=campaign_chapters.CAMPAIGN, cache_dir=None):
    """Which playtest scenarios cover this chapter, and what each last said.

    "Covers" is the matrix's OWN notion, not a second one: a scenario covers a chapter if the
    slots it was last OBSERVED to visit include this chapter's host slot, falling back to the
    slot it boots at when the cache has never seen it run. `matrix.yaml`'s `host_chapter` is a
    boot hint rather than an upper bound -- `ch01win` boots at the prologue and plays into
    ch01 -- which is exactly why the observed set exists.

    The VERDICT is only ever a PASS. `store_cached_verdict` writes a slot on PASS and clears
    the scenario's slots on a FAIL, so an absent slot means "no stored PASS" and cannot be
    read as "never run" -- a failing scenario and an unrun one look identical from here, and
    saying otherwise is the blur this command must not make. Whether a stored PASS still
    applies to the tree as it stands is `matrix.py run --dry-run`'s question, deliberately
    not re-answered here.
    """
    matrix = _matrix_module()
    slot = host_slot(name, campaign)
    if matrix is None or slot is None:
        return []
    manifest = matrix.Manifest.load()
    short = campaign_chapters.short_id(load(name, campaign))
    # The chapter's own SUITE is a declaration and the cheapest truth available. The other
    # two are evidence: what a scenario was last observed to visit, and where it boots.
    # `host_chapter` alone is not enough -- matrix.py documents it as a boot HINT defaulting
    # to 1, so on a cold cache it misses every scenario that boots earlier and plays forward,
    # which is how ch02's nine scenarios reported as none.
    declared = set(manifest.suites.get(short) or ())
    rows = []
    for scenario_name in sorted(manifest.scenarios):
        try:
            scenario = manifest.resolve(scenario_name)
        except Exception:
            continue
        observed = matrix.load_observed_chapters(scenario_name, cache_dir)
        if scenario_name in declared:
            why = 'suite'
        elif observed and slot in observed:
            why = 'observed'
        elif not observed and scenario.host_chapter == slot:
            why = 'boot slot'
        else:
            continue
        verdict, stored = _last_verdict(matrix, scenario_name, cache_dir)
        rows.append(ScenarioRow(scenario_name, scenario.rom, scenario.kind, why,
                                verdict, stored))
    return rows


def _last_verdict(matrix, scenario, cache_dir=None):
    """The most recently STORED verdict for a scenario, with when it was stored.

    Read by scenario name rather than by fingerprint: a fingerprint names one exact build,
    and computing today's would mean doing the build this command exists to avoid. So this
    answers "what did it last say", and `--dry-run` answers "does that still count".
    """
    import glob
    import json
    directory = cache_dir or matrix.VERDICT_CACHE_DIR
    best = (None, None)
    for path in glob.glob(os.path.join(directory, '%s-*.json' % scenario)):
        try:
            with open(path) as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        if data.get('scenario') != scenario:
            continue
        when = data.get('stored')
        if best[1] is None or (when or 0) > best[1]:
            best = (data.get('verdict'), when)
    return best


def event_group_census(name, campaign=campaign_chapters.CAMPAIGN):
    """{field: WRITTEN/INHERITED/ABSENT} for this chapter, or None where it cannot be read.

    The SAME data the build guard rules on (#313) -- `make chapter` reports it and the build
    refuses it, off one census. Two censuses would be two answers, which is the drift this
    whole area is against.
    """
    try:
        sys.path.insert(0, os.path.join(REPO, 'tools'))
        from inject import event_group, hosts
    except ImportError:
        return None
    short = campaign_chapters.short_id(load(name, campaign))
    if not any(h.name == short for h in hosts.hosted_chapters()):
        return None
    # On an UNINJECTED decomp every field reads INHERITED -- true, and indistinguishable from
    # a real finding. Say cannot tell rather than report a census of nothing.
    if not event_group.injected():
        return None
    try:
        return event_group.census(short)
    except (KeyError, OSError):
        return None


def inherited_reasons(name, campaign=campaign_chapters.CAMPAIGN):
    """{field: declared reason} for what this chapter inherits, from the same registry."""
    verdicts = event_group_census(name, campaign) or {}
    from inject import event_group
    return dict((f, event_group.reason_for(campaign_chapters.short_id(load(name, campaign)), f)
                 or 'UNRULED')
                for f, v in verdicts.items() if v != 'WRITTEN')


def loose_ends(name, campaign=campaign_chapters.CAMPAIGN, cache_dir=None):
    """Anything declared but unbuilt, or built but undeclared. The hand-kept list, derived.

    Every line here is a fact one of the sections above already computed -- this is the
    summary a human used to write into HANDOFF, assembled from the same reads rather than
    from memory.
    """
    chapter = load(name, campaign)
    short = campaign_chapters.short_id(chapter)
    out = []

    rows = scenes(name, campaign)
    unwritten = [r for r in rows if not r.declared]
    if unwritten:
        out.append('%d of %d events have no script yet: %s'
                   % (len(unwritten), len(rows),
                      ', '.join(r.trigger or '?' for r in unwritten)))
    # Only claimable when the preview registry could actually be consulted: without it every
    # scene looks unpreviewable, and ch05's thirteen registered ones would be reported as gaps.
    unseeable = ([r for r in rows if r.declared and not r.preview]
                 if _preview_module() is not None else [])
    if unseeable:
        out.append('%d scripted event(s) cannot be previewed -- no `make scene` entry: %s'
                   % (len(unseeable), ', '.join(r.slot or r.trigger or '?' for r in unseeable)))

    room = message_ids(name, campaign)
    if room.block is UNKNOWN:
        pass                          # the registry could not be read; say nothing rather than guess
    elif room.block is None and room.claimed:
        out.append('claims %d message id(s) but declares no host block, so headroom is '
                   'unknown (see HOSTED_CHAPTER_MESSAGE_BLOCKS)' % len(room.claimed))
    elif room.block is not None and room.free == 0:
        out.append('the host block is full: %s, all %d spent -- the next scene costs a '
                   'redesign, not an id (extend it from the never-shipped pool; see '
                   'HOSTED_CHAPTER_MESSAGE_BLOCKS)'
                   % (' + '.join('0x%03X-0x%03X' % r for r in room.block),
                      len(room.used_in_block)))
    if room.borrowed:
        out.append('%d id(s) inside this block are held by another chapter: %s'
                   % (len(room.borrowed), ', '.join('0x%03X' % m for m in room.borrowed)))

    for row in art(name, campaign):
        if row.missing:
            out.append('%s (%s) has no %s' % (row.unit, row.role, ', '.join(row.missing)))

    if host_slot(name, campaign) is None:
        out.append('not hosted: no slot declared in inject/hosts.py, so nothing loads it')
    covering = scenarios(name, campaign, cache_dir)
    gated = [r for r in covering if r.kind == 'verdict']
    if not covering:
        out.append('no playtest scenario covers this chapter')
    elif gated and all(r.verdict is None for r in gated):
        # Counted over the VERDICT scenarios only -- `all()` over an empty set is vacuously
        # true, so a chapter covered solely by `record` scenarios used to be reported as
        # unproven with a count that included the very rows it had filtered out.
        out.append('%d verdict scenario(s) cover this chapter and none has a stored PASS'
                   % len(gated))

    status = str(chapter.get('status'))
    if status == 'planned' and host_slot(name, campaign) is not None:
        out.append('marked `status: planned` but hosted -- one of the two is stale')
    if status == 'active' and not any(r.declared for r in rows):
        out.append('marked `status: active` with no scripted event')
    return out


def _yes(flag):
    return 'yes' if flag else '--'


def _age(stored):
    if not stored:
        # NOT "never run": the cache only ever holds a PASS, so an absent slot covers both
        # "has not run" and "ran and failed", and this cannot tell them apart.
        return 'no stored PASS'
    import time
    days = (time.time() - stored) / 86400.0
    if days < 1:
        return '%dh ago' % max(1, int(days * 24))
    return '%dd ago' % int(days)


def report(name, campaign=campaign_chapters.CAMPAIGN, cache_dir=None):
    """The whole status of one chapter, as the page you read."""
    chapter = load(name, campaign)
    short = campaign_chapters.short_id(chapter)
    slot = host_slot(name, campaign)
    room = message_ids(name, campaign)
    out = []

    out.append('%s  %s' % (short, campaign_chapters.squish(chapter.get('title'))))
    out.append('  chapter   number %s, status %s, milestone %s'
               % (chapter.get('chapter_number'), chapter.get('status'),
                  chapter.get('milestone')))
    out.append('            host slot %s, event group %s'
               % (slot if slot is not None else 'NOT HOSTED',
                  event_group(name, campaign) or '--'))
    objective = chapter.get('objective') or {}
    modes = chapter.get('difficulty') or {}
    out.append('            objective %s, difficulty %s'
               % (objective.get('type', '--'),
                  ('/'.join('%s %s' % (m, modes[m]) for m in ('tutorial', 'normal', 'difficult')
                            if m in modes) or 'NOT DECLARED')))

    out.append('')
    out.append('  scenes    declared  boxes  presses  preview')
    for row in scenes(name, campaign):
        out.append('    %-22s %-8s %5s  %7s  %s'
                   % ((row.slot or row.trigger or '?')[:22], _yes(row.declared),
                      '?' if row.boxes is None else (row.boxes or '--'),
                      row.presses if row.presses is not None else '--',
                      row.preview or '--'))

    out.append('')
    if room.block is UNKNOWN:
        out.append('  message ids  cannot tell -- the id registry could not be read here')
    elif room.block is None:
        out.append('  message ids  %d claimed; no host block declared, headroom unknown'
                   % len(room.claimed))
    else:
        out.append('  message ids  %d claimed; block %s, %d spent, %s FREE'
                   % (len(room.claimed),
                      ' + '.join('0x%03X-0x%03X' % r for r in room.block),
                      len(room.used_in_block), room.free))
        if room.borrowed:
            out.append('               held by another chapter: %s'
                       % ', '.join('0x%03X' % m for m in room.borrowed))

    out.append('')
    out.append('  art       portrait  sprite  banim  unit')
    art_rows = art(name, campaign)
    for row in art_rows:
        out.append('    %-8s %-9s %-7s %-6s %s'
                   % (row.role, _yes(row.portrait), _yes(row.map_sprite),
                      _yes(row.battle_anim), row.unit))
    if not art_rows:
        out.append('    (no named units declared)')

    out.append('')
    ai_rows = ai(name, campaign)
    if ai_rows:
        out.append('  ai        action/approach          shape      borrowed from  unit')
        for row in ai_rows:
            if row.ai is None:
                out.append('    %-24s %-10s %-14s %s'
                           % ('UNGROUNDED', '--', '--', row.unit))
                continue
            # BOTH halves. The approach alone reads "never-move" for a unit that steps out to
            # strike, which is what ch06's clock was designed against (decisions.md -> "AI_B is
            # the APPROACH and AI_A is the ACTION").
            pair = '%s/%s' % (AI_ACTION.get(row.ai[0], '0x%02X' % row.ai[0]),
                              AI_BEHAVIOUR.get(row.ai[1], '0x%02X' % row.ai[1]))
            out.append('    %-24s %-10s %-14s %s'
                       % (pair, ai_shape(row.ai) or '?', _donor_label(row), row.unit))
        overrides = [r for r in ai_rows if r.override]
        for row in overrides:
            # First sentence only: the reason is authored in full in the chapter YAML, and this
            # report is a glance, not a second copy of it.
            why = ' '.join((row.why or '').split())
            if len(why) > 96:
                why = why[:95].rsplit(' ', 1)[0] + '...'
            out.append('    override  %s: %s' % (row.unit, why))
        # The behavioural split, beside the roster it describes (#344). Reported, never folded
        # into threat: AI is DERIVED from the donor, so our shape IS the twin's -- measured at
        # 0 points of difference on all six active chapters -- and a weighting would scale both
        # sides of the ratio and always say x1.00. What this catches is the day that stops
        # being true, which can only happen through an ai_override or a donor-less unit.
        split = behaviour_split([r.ai for r in ai_rows if r.ai is not None])
        if split['n']:
            # THREE, not two. A `striker` holds ground but steps out within its own move range,
            # and it is most of every roster -- collapsing it into "you walk into" is what let a
            # chapter be planned as though the line would stand still.
            line = ('    shape     %d come to you / %d hold and STRIKE / %d never move'
                    % (split['pursuer'], split['striker'], split['statue']))
            if split['own_errand']:
                # Moves, but not at the player -- loots and leaves, flees, chews on walls.
                line += ' / %d on its own errand' % split['own_errand']
            if split['unclassified']:
                # Named separately rather than folded into any of them: the decomp leaves six
                # AI2 scripts as bare addresses, and one is live in vanilla's own Prologue.
                line += ' / %d unclassified' % split['unclassified']
            out.append(line)
        out.append('    AI is BORROWED from each unit\'s vanilla donor, never authored --')
        out.append('    an override states its reason or the parity gate fails (#335).')

    out.append('')
    covering = scenarios(name, campaign, cache_dir)
    width = max([len(r.scenario) for r in covering] + [12])
    out.append('  scenarios %s kind      verdict  when' % 'name'.ljust(width))
    for row in covering:
        # Only a `kind: verdict` scenario has a verdict to store -- a `record` one produces
        # FRAMES, which is its whole output. "never run" beside twelve of those would read
        # as a chapter in trouble when nothing is wrong.
        when = _age(row.stored) if row.kind == 'verdict' else 'films, no verdict'
        out.append('    %s %-9s %-8s %s'
                   % (row.scenario.ljust(width), row.kind, row.verdict or '--', when))
    if not covering:
        out.append('    (none cover this chapter)')
    out.append('    a stored PASS says what it last said, not whether it still counts --')
    out.append('    `python3 tools/playtest/matrix.py run --dry-run` answers that, for free.')

    out.append('')
    out.append('  event group fields')
    verdicts = event_group_census(name, campaign)
    if verdicts is None:
        out.append('    cannot tell -- the decomp is not injected (run `make`), '
                   'or it could not be read')
    else:
        written = [f for f, v in verdicts.items() if v == 'WRITTEN']
        out.append('    %d WRITTEN, %d declared-inherited' % (len(written),
                                                              len(verdicts) - len(written)))
        for field, why in sorted(inherited_reasons(name, campaign).items()):
            out.append('    inherits %-30s %s' % (field, why))

    ends = loose_ends(name, campaign, cache_dir)
    out.append('')
    out.append('  loose ends')
    for end in ends:
        out.append('    - %s' % end)
    if not ends:
        out.append('    - none')
    return '\n'.join(out) + '\n'


def main():
    import argparse
    ap = argparse.ArgumentParser(
        description='What a chapter has DECLARED against what is actually built (#312). '
                    'Derived at the moment you ask -- no ROM build, no emulator.')
    ap.add_argument('chapter', nargs='?',
                    help='a chapter (ch05); omit for every chapter at a glance')
    ap.add_argument('--campaign', default=campaign_chapters.CAMPAIGN)
    args = ap.parse_args()
    if args.chapter:
        try:
            print(report(args.chapter, args.campaign), end='')
        except KeyError as exc:
            ap.error(str(exc).strip("'"))
        return 0
    for chapter in load_all(args.campaign):
        short = campaign_chapters.short_id(chapter)
        ends = loose_ends(short, args.campaign)
        rows = scenes(short, args.campaign)
        print('%-6s %-9s %2d/%-2d scenes written   %2d loose end%s'
              % (short, chapter.get('status'), sum(1 for r in rows if r.declared), len(rows),
                 len(ends), '' if len(ends) == 1 else 's'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
