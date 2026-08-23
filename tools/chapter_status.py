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
        return len(script)      # no directive vocabulary available; the honest upper bound
    return bc._script_box_count(script)


def scenes(name, campaign=campaign_chapters.CAMPAIGN):
    """Every authored event in a chapter: declared, how many boxes, and whether it can be seen.

    An event with no `script:` is a SEED -- a named beat with nothing written yet, which is
    exactly the "declared but unbuilt" row a human used to keep in HANDOFF by hand. It is
    reported rather than skipped.
    """
    chapter = load(name, campaign)
    previews = _previews_by_event(campaign_chapters.short_id(chapter))
    sp = _preview_module()
    rows = []
    for event in chapter.get('events') or ():
        trigger, slot = event.get('trigger'), event.get('slot')
        script = event.get('script')
        key = previews.get((trigger, slot)) or previews.get((trigger, None))
        presses = None
        if key and sp is not None:
            presses = len(sp.preview(key, campaign).boxes)
        rows.append(SceneRow(trigger, slot, bool(script), _boxes(script), key, presses))
    return rows


def message_ids(name, campaign=campaign_chapters.CAMPAIGN):
    """What a chapter has spent of its host block, and what is left in it.

    `free` counts ids NOBODY claims, not ids this chapter has not taken: a neighbour may hold
    one out of this block (ch05's ending borrowed two of ch04's), and reporting those as free
    would invite exactly the collision `assert_message_ids_unique` exists to refuse.

    A chapter with no declared block reports `block=None` -- ch01 and ch02 predate the
    registry, and "0 free" would read as full when the truth is that nobody wrote it down.
    """
    chapter = campaign_chapters.short_id(load(name, campaign))
    bc = _build_campaign()
    if bc is None:
        return Room((), None, (), (), None)
    claimed = tuple(sorted(set(bc.HOSTED_CHAPTER_MESSAGE_IDS.get(chapter, ()))))
    block = bc.HOSTED_CHAPTER_MESSAGE_BLOCKS.get(chapter)
    if block is None:
        return Room(claimed, None, (), (), None)
    lo, hi = block
    owner = {}
    for other, ids in bc.HOSTED_CHAPTER_MESSAGE_IDS.items():
        for mid in ids:
            owner[mid] = other
    used = tuple(sorted(m for m in owner if lo <= m <= hi))
    borrowed = tuple(sorted(m for m in used if owner[m] != chapter))
    return Room(claimed, (lo, hi), used, borrowed, (hi - lo + 1) - len(used))


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


def host_slot(name, campaign=campaign_chapters.CAMPAIGN):
    """The vanilla chapter slot this chapter is hosted on, from the host registry.

    Not derivable from the chapter number: FE8 inserts chapter 5X, so the slot and the
    number part company from ch04 on. `inject/hosts.py` is where that is declared.
    """
    try:
        sys.path.insert(0, os.path.join(REPO, 'tools'))
        from inject import hosts
    except ImportError:
        return None
    short = campaign_chapters.short_id(load(name, campaign))
    for hosted in hosts.hosted_chapters():
        if hosted.name == short:
            return hosted.host_index
    return None


def event_group(name, campaign=campaign_chapters.CAMPAIGN):
    """The ChapterEventGroup this chapter's injector fills, from the host registry."""
    try:
        sys.path.insert(0, os.path.join(REPO, 'tools'))
        from inject import hosts
    except ImportError:
        return None
    short = campaign_chapters.short_id(load(name, campaign))
    for hosted in hosts.hosted_chapters():
        if hosted.name == short:
            return hosted.event_group
    return None


def scenarios(name, campaign=campaign_chapters.CAMPAIGN, cache_dir=None):
    """Which playtest scenarios cover this chapter, and what each last said.

    "Covers" is the matrix's OWN notion, not a second one: a scenario covers a chapter if the
    slots it was last OBSERVED to visit include this chapter's host slot, falling back to the
    slot it boots at when the cache has never seen it run. `matrix.yaml`'s `host_chapter` is a
    boot hint rather than an upper bound -- `ch01win` boots at the prologue and plays into
    ch01 -- which is exactly why the observed set exists.

    A scenario that has never run reports `verdict=None`. An unrun scenario is not a failing
    one, and blurring the two would push someone into a playtest run to find out which -- the
    cost this command exists to save. Whether a stored PASS still applies to the tree as it
    stands is `matrix.py run --dry-run`'s question, and is deliberately not re-answered here.
    """
    matrix = _matrix_module()
    slot = host_slot(name, campaign)
    if matrix is None or slot is None:
        return []
    manifest = matrix.Manifest.load()
    rows = []
    for scenario_name in sorted(manifest.scenarios):
        try:
            scenario = manifest.resolve(scenario_name)
        except Exception:
            continue
        observed = matrix.load_observed_chapters(scenario_name, cache_dir)
        covers = slot in observed if observed else scenario.host_chapter == slot
        if not covers:
            continue
        verdict, stored = _last_verdict(matrix, scenario_name, cache_dir)
        rows.append(ScenarioRow(scenario_name, scenario.rom, scenario.kind,
                                'observed' if observed else 'boot slot', verdict, stored))
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


def loose_ends(name, campaign=campaign_chapters.CAMPAIGN):
    """Anything declared but unbuilt, or built but undeclared. The hand-kept list, derived.

    Every line here is a fact one of the sections above already computed -- this is the
    summary a human used to write into HANDOFF, assembled from the same reads rather than
    from memory.
    """
    chapter = load(name, campaign)
    short = campaign_chapters.short_id(chapter)
    out = []

    unwritten = [r for r in scenes(name, campaign) if not r.declared]
    if unwritten:
        out.append('%d of %d events have no script yet: %s'
                   % (len(unwritten), len(scenes(name, campaign)),
                      ', '.join(r.trigger or '?' for r in unwritten)))
    unseeable = [r for r in scenes(name, campaign) if r.declared and not r.preview]
    if unseeable:
        out.append('%d scripted event(s) cannot be previewed -- no `make scene` entry: %s'
                   % (len(unseeable), ', '.join(r.slot or r.trigger or '?' for r in unseeable)))

    room = message_ids(name, campaign)
    if room.block is None and room.claimed:
        out.append('claims %d message id(s) but declares no host block, so headroom is '
                   'unknown (see HOSTED_CHAPTER_MESSAGE_BLOCKS)' % len(room.claimed))
    elif room.block is not None and room.free == 0:
        out.append('the host block is full: 0x%03X-0x%03X, all %d spent -- the next scene '
                   'costs a redesign, not an id' % (room.block[0], room.block[1],
                                                    len(room.used_in_block)))
    if room.borrowed:
        out.append('%d id(s) inside this block are held by another chapter: %s'
                   % (len(room.borrowed), ', '.join('0x%03X' % m for m in room.borrowed)))

    for row in art(name, campaign):
        if row.missing:
            out.append('%s (%s) has no %s' % (row.unit, row.role, ', '.join(row.missing)))

    if host_slot(name, campaign) is None:
        out.append('not hosted: no slot declared in inject/hosts.py, so nothing loads it')
    covering = scenarios(name, campaign)
    if not covering:
        out.append('no playtest scenario covers this chapter')
    elif all(r.verdict is None for r in covering if r.kind == 'verdict'):
        out.append('%d scenario(s) cover this chapter and none has a stored verdict'
                   % len(covering))

    status = str(chapter.get('status'))
    if status == 'planned' and host_slot(name, campaign) is not None:
        out.append('marked `status: planned` but hosted -- one of the two is stale')
    if status == 'active' and not any(r.declared for r in scenes(name, campaign)):
        out.append('marked `status: active` with no scripted event')
    return out


def _yes(flag):
    return 'yes' if flag else '--'


def _age(stored):
    if not stored:
        return 'never run'
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
                      row.boxes or '--', row.presses if row.presses is not None else '--',
                      row.preview or '--'))

    out.append('')
    if room.block is None:
        out.append('  message ids  %d claimed; no host block declared, headroom unknown'
                   % len(room.claimed))
    else:
        out.append('  message ids  %d claimed; block 0x%03X-0x%03X, %d spent, %s FREE'
                   % (len(room.claimed), room.block[0], room.block[1],
                      len(room.used_in_block), room.free))
        if room.borrowed:
            out.append('               held by another chapter: %s'
                       % ', '.join('0x%03X' % m for m in room.borrowed))

    out.append('')
    out.append('  art       portrait  sprite  banim  unit')
    for row in art(name, campaign):
        out.append('    %-8s %-9s %-7s %-6s %s'
                   % (row.role, _yes(row.portrait), _yes(row.map_sprite),
                      _yes(row.battle_anim), row.unit))
    if not art(name, campaign):
        out.append('    (no named units declared)')

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
    out.append('  event group fields  WRITTEN vs INHERITED: pending #313, whose census guard')
    out.append('                      owns that data. Not faked here -- two censuses would')
    out.append('                      be two answers.')

    ends = loose_ends(name, campaign)
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
