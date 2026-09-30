"""Scene actors (#398): every reachable scene LOADs the characters it stages.

Importing this module registers `assert_scene_loads_its_actors` as a scene validator.
"""
import collections
import functools
import os
import re
import sys

from inject import decomp as _decomp
from inject import event_group
from inject.cast import PORTRAIT_MAP
from inject.decomp import DECOMP, vanilla_decomp_text
from inject.hosts import hosted_chapters
from inject.paths import EVENTS_UDEFS_C


# Every event command that resolves a character id through `GetUnitStructFromEventParameter`,
# with the ARGUMENT INDEX the pid sits at (EAstdlib.h:101-124). The index matters: `MOVE` is
# `MOVE(speed, pid, x, y)`, so reading argument 0 reads a SPEED -- vanilla's speeds are 0x10
# and 0x0, every one parses as a character id, and doing that flags 378 sites campaign-wide.
#
# The two severities are different failures and the decomp is explicit about which is which:
#
#   HANGS. The handler returns EVC_ERROR, and `EventEngine_Main` (event.c:106-112) `break`s
#   on EVC_ERROR WITHOUT advancing `pEventCurrent` -- so the engine re-runs the same command
#   forever. CUMO_CHAR (eventscr.c:3765) and the TARGET of MOVEONTO/MOVE_NEXTTO
#   (eventscr.c:2995) both do this.
#
#   NO-OPS SILENTLY. The MOVER of any move command returns EVC_ADVANCE_CONTINUE when NULL
#   (eventscr.c:2960), so the script advances and the walk simply never happens. Not a hang --
#   a scene that plays wrong, with the actor missing from a beat written around them.
#
# Both are worth refusing; only one wedges the cartridge, and saying "soft-lock" about the
# silent one would be an overstatement that the next reader would have to re-derive.
_HANGS, _NOOPS = 'hangs', 'plays without them'
_STAGING_COMMANDS = (
    ('CUMO_CHAR', 0, _HANGS),
    ('CAMERA2_CAHR', 0, _HANGS),
    ('MOVEONTO', 2, _HANGS),          # the TARGET; its mover is arg 1 and only no-ops
    ('MOVE_NEXTTO', 2, _HANGS),
    ('MOVE', 1, _NOOPS),
    ('MOVE_CLOSEST', 1, _NOOPS),
    ('MOVEONTO', 1, _NOOPS),
    ('MOVE_NEXTTO', 1, _NOOPS),
    ('MOVE_1STEP', 1, _NOOPS),
    ('MOVE_1STEP_CLOSEST', 1, _NOOPS),
    ('MOVE_DEFINED', 0, _NOOPS),
    ('MOVE_DEFINED_CLOSEST', 0, _NOOPS),
)
# LOAD3/LOAD4 exist and vanilla uses LOAD3 nine times; matching only LOAD[12] would accuse a
# scene that correctly loads its actor.
_LOAD_COMMAND = re.compile(r'\bLOAD[1-4]\(\s*[^,]+,\s*(\w+)\s*\)')


@functools.lru_cache(maxsize=None)
def _character_enum():
    """{CHARACTER_FOO: value} from the decomp's own header."""
    return {m.group(1): int(m.group(2), 0) for m in re.finditer(
        r'(CHARACTER_\w+|CHAR_EVT_\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)',
        vanilla_decomp_text('include/constants/characters.h'))}


def character_pid(token):
    """`CHARACTER_EIRIKA` or `0xce` -> int, or None if it is neither."""
    token = str(token).strip()
    enum = _character_enum()
    if token in enum:
        return enum[token]
    try:
        return int(token, 0)
    except ValueError:
        return None


def scene_staged_pids(body, severity=None):
    """{pid: severity} for every character a scene body stages.

    A pid staged by two commands keeps the WORSE outcome: being told a beat plays without the
    actor is no help when another line in the same scene hangs on them."""
    out = {}
    for name, index, outcome in _STAGING_COMMANDS:
        if severity is not None and outcome != severity:
            continue
        # `\b` plus the literal `(` keeps MOVE from matching MOVE_DEFINED: the longer name
        # has no `(` right after `MOVE`.
        for m in re.finditer(r'\b%s\(([^)]*)\)' % name, body):
            args = [a.strip() for a in m.group(1).split(',')]
            if len(args) <= index:
                continue
            pid = character_pid(args[index])
            if pid is None:
                continue
            if out.get(pid) != _HANGS:
                out[pid] = outcome
    return out


@functools.lru_cache(maxsize=None)
def player_character_pids():
    """{pid: unit_id} for the cast the player can LOSE.

    A PC rides its `PORTRAIT_MAP` slot, so its on-map pid is `CHARACTER_<slot>`. This set is
    the whole scope of the guard: everything else a scene stages is on the map because the
    chapter put it there (a boss, a generic, a scripted neutral), while a PC is there only if
    the player still has them and chose to deploy them."""
    out = {}
    for unit_id, slot in PORTRAIT_MAP.items():
        pid = character_pid('CHARACTER_%s' % str(slot).upper())
        if pid is not None:
            out[pid] = unit_id
    return out


def scene_loaded_pids(body):
    """Every character pid the scene itself LOADs onto the map."""
    loaded = set()
    for m in _LOAD_COMMAND.finditer(body):
        loaded |= _unit_def_pids(m.group(1))
    return loaded


def assert_scene_loads_its_actors(body, scene, loaded_pids=None):
    """A scene must LOAD every PLAYER CHARACTER it stages (#337).

    The permadeath policy (`decisions.md` -> "Permadeath is a combat rule, not a narrative
    one") puts all eight PCs in every cutscene alive or dead. That is only safe while a scene
    LOADs the actors it stages: `LoadUnit` has no death check, so loading a DEAD character
    works, but `GetUnitStructFromEventParameter` returns NULL for an ABSENT one.

    What happens then depends on the command, and the two outcomes are not the same bug.
    `CUMO_CHAR` and the TARGET of `MOVEONTO`/`MOVE_NEXTTO` return EVC_ERROR, which
    `EventEngine_Main` handles by breaking WITHOUT advancing the script pointer -- the same
    command re-runs forever and the chapter HANGS. A move command's own mover returns
    EVC_ADVANCE_CONTINUE instead, so the script advances and the walk silently never happens:
    the scene plays, wrong, around an actor who is not there.

    SCOPED TO THE PCs, measured rather than assumed. "Every staged character must be LOADed"
    flags 73 sites in untouched VANILLA, which plainly works: vanilla stages Eirika without
    loading her because Eirika is always there. We have no always-present character -- the
    player picks their own lord, and any PC can be dead or unpicked at PREP -- so vanilla's
    guarantee is the one thing that does not transfer. Everything else is guaranteed by
    construction; ch05 stages Ravisin the same way and she has held the arena since turn 1."""
    loaded = set(loaded_pids or ()) | scene_loaded_pids(body)
    pcs = player_character_pids()
    missing = {pid: outcome for pid, outcome in scene_staged_pids(body).items()
               if pid in pcs and pid not in loaded}
    if not missing:
        return
    lines = ['  %s -- the chapter %s' % (pcs[pid], outcome)
             for pid, outcome in sorted(missing.items(), key=lambda kv: pcs[kv[0]])]
    sys.exit(
        'ERROR: %s stages player characters it never LOADs:\n%s\n'
        '  A PC is on the map only if the player still has them AND deployed them, so the '
        'unit lookup returns NULL the first time someone reaches this beat having lost them.\n'
        '  Add a LOAD naming a UnitDefinition that carries them, or stage the beat with '
        'CUMO_AT (a tile) rather than a character (#337).' % (scene, '\n'.join(lines)))


#
# `assert_scene_loads_its_actors` above hooks the two WRITERS, so it sees every scene this
# build authors and none that it inherits. Our injectors edit a host slot's event-script FILE
# without rewriting every scene in it, and `git diff` reports that the FILE changed, never
# that a given scene did -- so untouched vanilla scenes sit in the files we write.
#
# Five of them stage `CHARACTER_EIRIKA` or `CHARACTER_NEIMI`, which are braulo and pinky. That
# is the same soft-lock #337 exists to prevent, in code nobody here wrote.
#
# The rule does not change; the POPULATION does. A scene LOADs the PCs it stages, whether we
# authored it or adopted it -- so this applies the identical test to everything a chapter's
# ChapterEventGroup can actually reach (`event_group.reachable_scripts`), which is the set
# that can run. A vanilla scene nothing points at is dead weight, and the difference between
# the two is the entire audit.

SceneActorFinding = collections.namedtuple(
    'SceneActorFinding', 'chapter script file unit_id outcome loaded_by')


def reachable_scenes_staging_unloaded_pcs(roots_by_chapter=None, bodies=None,
                                          loaded_pids=None, hosted=None):
    """Every REACHABLE script that stages a player character it does not LOAD.

    `loaded_pids` maps a UnitDefinition symbol to the pids it carries, for tests that have no
    decomp to resolve against; left None, the real resolver is used.
    """
    bodies = event_group.script_bodies() if bodies is None else bodies
    if roots_by_chapter is None:
        rows = hosted if hosted is not None else hosted_chapters()
        roots_by_chapter = dict(
            (h.name, event_group.chapter_script_roots(h.name, rows)) for h in rows)
    pcs = player_character_pids()

    def loads(body):
        if loaded_pids is None:
            return scene_loaded_pids(body)
        out = set()
        for match in _LOAD_COMMAND.finditer(body):
            out |= set(loaded_pids.get(match.group(1), ()))
        return out

    found = []
    for chapter, roots in sorted(roots_by_chapter.items()):
        reached, _ = event_group.reachable_scripts(roots, bodies)
        # Who points AT each reachable script, within the same reachable set. Not part of the
        # verdict -- see below -- but the difference between an error a reader can act on and
        # one they have to re-derive.
        callers = collections.defaultdict(set)
        for symbol in reached:
            entry = bodies.get(symbol)
            if entry is None:
                continue
            for match in event_group.script_edges(entry[1]):
                if match != symbol and match in reached:
                    callers[match].add(symbol)
        for symbol in sorted(reached):
            entry = bodies.get(symbol)
            if entry is None:
                continue
            relpath, body = entry
            loaded = loads(body)
            for pid, outcome in sorted(scene_staged_pids(body).items()):
                if pid not in pcs or pid in loaded:
                    continue
                # THE VERDICT IS PER SCENE, exactly as it is for the scenes we write (#337).
                # A caller that LOADs the actor before calling does make the chain safe, and
                # vanilla relies on that in five of the twelve sites this flags on the donor
                # -- but "some caller loads it" is not the same claim as "every path does",
                # and a scene with two callers can be reached by the one that does not. So a
                # loading caller is REPORTED, never subtracted: it turns a build stop into a
                # one-line decision made with the evidence in front of you, instead of a
                # verdict this walk is not in a position to make.
                loaded_by = sorted(c for c in callers.get(symbol, ())
                                   if pid in loads(bodies[c][1]))
                found.append(SceneActorFinding(chapter, symbol, relpath, pcs[pid],
                                               outcome, tuple(loaded_by)))
    return found


def assert_reachable_scenes_load_their_actors(roots_by_chapter=None, bodies=None,
                                              loaded_pids=None, hosted=None, verbose=False):
    """Guard: no scene a hosted chapter can REACH stages a PC it never LOADs (#398).

    Runs in the build after the injectors, like the census beside it, because the question is
    what our build points at -- at HEAD every one of these fields still points at the donor's
    scenes, and the guard would report the donor's bugs as ours.

    An unreadable script is raised, not skipped. The product of this guard is a NEGATIVE, and
    a symbol whose body could not be read ends its branch silently: everything behind it then
    reads unreachable for the one reason that proves nothing.
    """
    bodies = event_group.script_bodies() if bodies is None else bodies
    if roots_by_chapter is None:
        rows = hosted if hosted is not None else hosted_chapters()
        roots_by_chapter = dict(
            (h.name, event_group.chapter_script_roots(h.name, rows)) for h in rows)
    blind = {}
    for chapter, roots in sorted(roots_by_chapter.items()):
        _, unresolved = event_group.reachable_scripts(roots, bodies)
        if unresolved:
            blind[chapter] = sorted(unresolved)
    if blind:
        sys.exit('ERROR: the reachability walk could not read %d script(s), so "nothing '
                 'reaches that scene" is not an answer it can give (#398):\n  - %s'
                 % (sum(len(v) for v in blind.values()),
                    '\n  - '.join('%s: %s' % (c, ', '.join(s)) for c, s in blind.items())))
    found = reachable_scenes_staging_unloaded_pcs(roots_by_chapter, bodies, loaded_pids)
    if found:
        sys.exit(
            'ERROR: reachable scenes stage player characters they never LOAD (#398):\n  - %s\n'
            '  These run in OUR chapter. A PC is on the map only if the player still has them '
            'AND deployed them, so the unit lookup returns NULL the first time someone reaches '
            'the beat having lost them.\n'
            '  If the scene is vanilla\'s, the fix is usually to stop POINTING at it; if it is '
            'ours, LOAD the actor or stage the beat with CUMO_AT (a tile). Where a CALLER is '
            'named below it already LOADs that character, so the chain may well be safe -- '
            'check that EVERY path to the scene goes through it, then say so here.'
            % '\n  - '.join(
                '%s reaches %s (%s): %s -- the chapter %s%s'
                % (f.chapter, f.script, f.file, f.unit_id, f.outcome,
                   '; but caller(s) %s LOAD it' % ', '.join(f.loaded_by) if f.loaded_by else '')
                for f in found))
    if verbose:
        total = sum(len(event_group.reachable_scripts(r, bodies)[0])
                    for r in roots_by_chapter.values())
        print('  %d reachable script(s) across %d hosted chapter(s) stage no unloaded PC'
              % (total, len(roots_by_chapter)))
    return True


# Every file a UnitDefinition array can live in: vanilla's, and the per-chapter headers our
# own `declare_unit_table` writes. Searching only `events_udefs.c` silently returns an empty
# set for `UnitDef_Event_Ch1Ally` -- and an empty set reads as "the scene loaded nobody",
# which turns a correct LOAD into a false accusation.
def _udef_sources():
    import glob as _glob
    paths = [EVENTS_UDEFS_C] + sorted(
        _glob.glob(os.path.join(DECOMP, 'src', 'events', '*eventudefs.h')))
    return [t for t in (_live_decomp_text(p) for p in paths) if t] + \
        [vanilla_decomp_text('src/events_udefs.c')]


def _unit_def_pids(symbol):
    """The character pids a UnitDefinition array carries, ours or vanilla's."""
    import difficulty
    for text in _udef_sources():
        if (symbol + '[]') not in text:
            continue
        try:
            return {character_pid(e.get('charIndex'))
                    for e in difficulty.vanilla_unit_defs(text, symbol)} - {None}
        except BaseException:               # noqa: BLE001 -- an unparseable array is not
            continue                        # this guard's business to diagnose
    return set()


def _live_decomp_text(path):
    try:
        with open(path, encoding='utf-8') as fh:
            return fh.read()
    except OSError:
        return ''


# Registered on BOTH writers a scene body can go through. `_replace_brace_block` covers the
# scenes that overwrite a vanilla `EventScr_*`; `declare_event_script` covers the ones we
# DEFINE, which are the campaign's own `MS_*` scripts -- ch05's talks, villages and arena, and
# the ch06 Messie scene this guard was built for. Hooking only the first would have left the
# motivating case unchecked.
_decomp.SCENE_VALIDATORS.append(assert_scene_loads_its_actors)
