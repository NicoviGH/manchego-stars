"""The ChapterEventGroup census: every field WRITTEN, or DECLARED-INHERITED with a reason.

A hosted chapter adopts a vanilla host slot, and every field we do not write keeps the donor's
value. Silently. That failure class has landed five times -- goal text ids (#207), battle
grounds (#289), difficulty numbers (#303), `.traps` (#306, which would have shipped vanilla
Ch7's two ballistae on ch06) -- and each was found one at a time, by something else going
wrong. In IaC terms it is `terraform import`: adopt a pre-existing resource and every unlisted
attribute keeps whatever it had. The answer is never a better runbook; it is to enumerate the
attribute set and require every attribute to be accounted for.

Kept STDLIB-ONLY, like `hosts.py` and `decomp.py` beside it, so `tools/check.py` can lint it in
CI's lightweight job (which installs pyyaml and nothing else).
"""
import os
import re
import subprocess

_TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(_TOOLS)
DECOMP = os.path.join(REPO, 'fireemblem8u')

CHAPTERDATA_H = os.path.join(DECOMP, 'include', 'chapterdata.h')
EVENTS_INFO_S = os.path.join(DECOMP, 'src', 'events_info.s')

_FIELD = re.compile(r'^\s*/\*\s*[0-9A-Fa-f]+\s*\*/\s*const\s+void\s*\*\s*(\w+)\s*;',
                    re.M)


def fields(path=CHAPTERDATA_H, source=None):
    """Every ChapterEventGroup field, IN STRUCT ORDER, read from the decomp header.

    Order is identity here, not presentation: the group is emitted as twenty bare `.word`s,
    so a field is known only by its position. Read from the source rather than transcribed,
    because a transcription cannot notice a field being added upstream -- and a field the
    census does not know about is exactly the silent inheritance this exists to stop.
    """
    if source is None:
        with open(path, encoding='utf-8') as fh:
            source = fh.read()
    start = source.index('struct ChapterEventGroup')
    body = source[start:source.index('};', start)]
    return [m.group(1) for m in _FIELD.finditer(body)]


WRITTEN = 'WRITTEN'
INHERITED = 'INHERITED'
ABSENT = 'ABSENT'

EVENTS_DIR = os.path.join(DECOMP, 'src', 'events')

_INIT = re.compile(r'\.(\w+)\s*=\s*([^,}]+?)\s*[,}]')


def header_for(symbol, events_dir=EVENTS_DIR):
    """The `src/events/*.h` that DEFINES a ChapterEventGroup symbol.

    Searched rather than derived from the symbol name: our chapters sit on shifted slots and
    the symbols do not follow one pattern (ch04's group is `Ch5EventData`, ch05's is
    `Ch6Events`), so a naming rule would quietly resolve to the wrong donor.
    """
    needle = 'struct ChapterEventGroup %s ' % symbol
    for name in sorted(os.listdir(events_dir)):
        if not name.endswith('.h'):
            continue
        path = os.path.join(events_dir, name)
        with open(path, encoding='utf-8') as fh:
            if needle in fh.read():
                return os.path.join('src', 'events', name)
    raise KeyError('no src/events/*.h defines struct ChapterEventGroup %s' % symbol)


def initializer(symbol, source):
    """{field: value} for a ChapterEventGroup, read from its designated initializer.

    The group is written `.field = Value,` -- keyed by NAME, so unlike the compiled `.word`
    list this cannot be misread by position. A field missing from the initializer is reported
    ABSENT rather than skipped: C zero-fills it, which is a real and different answer from
    both "we wrote it" and "we kept the donor's".

    Raises when the symbol is absent, because an empty read would classify every field as
    inherited and pass the census in silence -- the exact outcome this guard exists to stop.
    """
    marker = 'struct ChapterEventGroup %s ' % symbol
    at = source.find(marker)
    if at < 0:
        raise KeyError('%s is not defined in this source' % symbol)
    body = source[source.index('{', at) + 1:source.index('};', at)]
    return dict((m.group(1), m.group(2).strip()) for m in _INIT.finditer(body + '}'))


def classify(field_names, ours, vanilla, rewritten=None):
    """field -> WRITTEN / INHERITED / ABSENT, ours against the donor's.

    A field is WRITTEN when we changed the POINTER **or** rewrote what it points AT, and
    `rewritten` supplies the second half. That distinction is the whole guard: our injectors
    mostly keep the donor's symbol and replace its contents -- `EventListScr_Ch6_Turn` is
    still called that and holds none of vanilla's events -- so comparing initializer tokens
    alone calls twenty fields per chapter INHERITED when almost none of them are. What leaks
    the donor's DATA is a field whose TARGET is still vanilla's.

    Every field in the struct gets a verdict, including ones neither side initialises: a
    field the census does not rule on is the silent inheritance this exists to prevent.
    """
    rewritten = rewritten or set()
    out = {}
    for name in field_names:
        mine, theirs = ours.get(name), vanilla.get(name)
        if mine is None:
            out[name] = ABSENT
        elif mine != theirs or mine in rewritten:
            out[name] = WRITTEN
        else:
            out[name] = INHERITED
    return out


_DEFN = r'(?:^|\n)[^\n]*\b%s\s*(?:\[\s*\]\s*)?='


def _definition(symbol, source):
    """The text of `symbol`'s definition in `source`, or None when it is not defined there."""
    match = re.search(_DEFN % re.escape(symbol), source)
    if match is None:
        return None
    tail = source[match.end():]
    end = tail.find('};')
    return tail[:end if end >= 0 else 4096]


_ANY_DEFN = re.compile(r'(?:^|\n)[^\n]*?\b(\w+)\s*(?:\[\s*\]\s*)?=', re.M)

_INDEX = None


def _symbol_index(search_dirs=None):
    """symbol -> the decomp-relative file that defines it, built by ONE pass over the sources.

    Indexed rather than searched per symbol: the census resolves ~20 symbols for each of six
    hosted chapters, and re-scanning a few hundred files for each of those turned a guard
    that runs inside every build into a ten-second one.
    """
    global _INDEX
    if _INDEX is not None:
        return _INDEX
    index = {}
    for rel_dir in (search_dirs or (os.path.join('src', 'events'), 'src')):
        base = os.path.join(DECOMP, rel_dir)
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            if not (name.endswith('.h') or name.endswith('.c')):
                continue
            rel = os.path.join(rel_dir, name)
            try:
                with open(os.path.join(DECOMP, rel), encoding='utf-8', errors='replace') as fh:
                    text = fh.read()
            except OSError:
                continue
            for m in _ANY_DEFN.finditer(text):
                index.setdefault(m.group(1), rel)
    _INDEX = index
    return index


def _defining_file(symbol, search_dirs=None):
    """The decomp-relative path that DEFINES a symbol, or None.

    A symbol we cannot locate is reported as unresolved rather than assumed unchanged --
    assuming would turn "I could not check" into "it is fine", which is the failure class
    this guard is about.
    """
    return _symbol_index(search_dirs).get(symbol)


def rewritten_symbols(tokens):
    """Which of `tokens` name data this build REWROTE, against the same symbol at HEAD.

    Compared per SYMBOL rather than per file: a chapter's event header holds several of the
    group's targets, so "the file changed" would mark every one of them written the moment
    any single one was.
    """
    out = set()
    cache = {}
    for token in set(tokens):
        rel = _defining_file(token)
        if rel is None:
            continue
        if rel not in cache:
            with open(os.path.join(DECOMP, rel), encoding='utf-8', errors='replace') as fh:
                mine = fh.read()
            try:
                theirs = vanilla_header(rel)
            except KeyError:
                theirs = None
            cache[rel] = (mine, theirs)
        mine, theirs = cache[rel]
        if theirs is None:
            continue
        if _definition(token, mine) != _definition(token, theirs):
            out.add(token)
    return out


def vanilla_header(relpath):
    """The COMMITTED text of a decomp source file.

    Our injectors patch these headers in the working tree, so the donor's values only exist
    at HEAD. The git env is stripped for the same reason `vanilla_decomp_text` strips it: an
    inherited GIT_DIR (set inside a commit hook) overrides `-C` discovery and resolves against
    the superproject instead of the submodule.
    """
    env = dict((k, v) for k, v in os.environ.items()
               if k not in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_PREFIX',
                            'GIT_COMMON_DIR', 'GIT_OBJECT_DIRECTORY', 'GIT_NAMESPACE',
                            'GIT_ALTERNATE_OBJECT_DIRECTORIES'))
    out = subprocess.run(['git', '-C', DECOMP, 'show', 'HEAD:%s' % relpath],
                         capture_output=True, text=True, env=env)
    if out.returncode != 0:
        raise KeyError('cannot read %s at HEAD: %s' % (relpath, out.stderr.strip()))
    return out.stdout


def census(chapter, hosted=None):
    """{field: WRITTEN/INHERITED/ABSENT} for one hosted chapter's ChapterEventGroup."""
    from . import hosts
    rows = hosted if hosted is not None else hosts.hosted_chapters()
    row = next((h for h in rows if h.name == chapter), None)
    if row is None:
        raise KeyError('%s is not a hosted chapter' % chapter)
    relpath = header_for(row.event_group)
    with open(os.path.join(DECOMP, relpath), encoding='utf-8') as fh:
        ours = initializer(row.event_group, fh.read())
    vanilla = initializer(row.event_group, vanilla_header(relpath))
    return classify(fields(), ours, vanilla, rewritten_symbols(ours.values()))


# --- the ruling ------------------------------------------------------------------------
#
# Every field a hosted chapter INHERITS needs a reason here, and a field with no reason fails
# the build. That is the whole guard: this failure class has landed five times -- goal text
# ids (#207), battle grounds (#289), difficulty numbers (#303), `.traps` (#306) -- and every
# instance was found one at a time, by something else going wrong.
#
# These reasons hold for every hosted chapter, because the inherited SET is the same eleven
# fields on ch01-ch05. A chapter needing its own ruling gets an entry in
# DECLARED_INHERITED_BY_CHAPTER, which is consulted first.
DECLARED_INHERITED = {
    # Vanilla ships these four lists EMPTY -- the bodies are a bare `END_MAIN`. There is no
    # donor behaviour to leak, so inheriting them is inheriting nothing. Checked, not assumed:
    # the census compares the TARGET, so if vanilla ever filled one of these the field would
    # still read INHERITED and this reason would be wrong -- which is why the reason names
    # the emptiness rather than the field.
    'specialEventsWhenUnitSelected': 'vanilla ships this list empty (END_MAIN): nothing to leak',
    'specialEventsWhenDestSelected': 'vanilla ships this list empty (END_MAIN): nothing to leak',
    'specialEventsAfterUnitMoved':   'vanilla ships this list empty (END_MAIN): nothing to leak',
    'tutorialEvents':                'vanilla ships this list empty (END_MAIN): nothing to leak',
    # Same shape, different table: TrapData_Event_ChNHard is TRAP_NONE on every slot we host.
    # ch05's NORMAL traps ARE written (#306 declared the tomb depression open ground), and the
    # hard-mode table needs no declaration of its own while it is already empty.
    'extraTrapsInHard': 'vanilla ships this table as TRAP_NONE on every slot we host',

    # THE SIX SKIRMISH ROSTERS. Nicolas, 2026-08-23: *"Vanilla has those optional skirmishes
    # so we also should. We can wire them when we get to the world map body of work."* So
    # these are KEPT deliberately, pending #29, and NOT nulled -- nulling would have foreclosed
    # a feature we want, and `GetChapterSkirmishLeaderClasses` (worldmap_timemons.c)
    # dereferences all three enemy rosters unconditionally for any chapter on a spawn node.
    #
    # What #29 inherits from this: our own rosters replace vanilla's here, and the engine
    # already ships the predicate for "does this chapter offer a skirmish" -- `sub_8083424`,
    # which checks all six for NULL. Nothing in FE8 calls it (verified: no caller in any
    # .c/.h/.s/.inc and no literal-address reference), so it is an entry point waiting for
    # one rather than a safety net that is already running.
    'playerUnitsChoice1InEncounter': 'skirmishes are IN scope; rosters authored with the world map (#29)',
    'playerUnitsChoice2InEncounter': 'skirmishes are IN scope; rosters authored with the world map (#29)',
    'playerUnitsChoice3InEncounter': 'skirmishes are IN scope; rosters authored with the world map (#29)',
    'enemyUnitsChoice1InEncounter':  'skirmishes are IN scope; rosters authored with the world map (#29)',
    'enemyUnitsChoice2InEncounter':  'skirmishes are IN scope; rosters authored with the world map (#29)',
    'enemyUnitsChoice3InEncounter':  'skirmishes are IN scope; rosters authored with the world map (#29)',
}

# chapter -> {field: reason}, consulted before the shared table above.
DECLARED_INHERITED_BY_CHAPTER = {
    # FOUND BY THIS GUARD, on the day it was written -- a sixth instance of the failure class,
    # and the first that was not discovered by something else going wrong. Every other hosted
    # chapter writes its misc list; ch02 alone keeps the donor's. Checked rather than assumed:
    # vanilla Ch3's misc list is exactly `CauseGameOverIfLordDies` and nothing else, which IS
    # ch02's declared lose_condition (`all_player_units_defeated`, the FE8 lord rule), and its
    # `defeat_all` objective is FE8's default when no DefeatBoss/Seize is declared, so it wants
    # no misc entry of its own. The donor's value is correct here by coincidence of design, not
    # by intent -- which is the reason worth writing down.
    'ch02': {'miscBasedEvents': "vanilla Ch3's misc list is CauseGameOverIfLordDies alone, "
                                "which is ch02's declared lose_condition; its defeat_all "
                                "objective needs no misc entry"},
    # The prologue is the one chapter that does NOT retarget its host slot (inject/hosts.py):
    # it keeps Ch1Events and writes its scenes into the slot's own scripts, so almost the whole
    # group reads inherited by construction rather than by oversight.
    'prologue': dict((f, 'the prologue does not retarget its slot -- it keeps Ch1Events '
                         '(see inject/hosts.py)') for f in (
        'turnBasedEvents', 'characterBasedEvents', 'locationBasedEvents', 'miscBasedEvents',
        'traps', 'playerUnitsInNormal', 'playerUnitsInHard',
        'beginningSceneEvents', 'endingSceneEvents')),
}


def reason_for(chapter, field):
    """The declared reason a chapter may inherit a field, or None if nobody has ruled."""
    per = DECLARED_INHERITED_BY_CHAPTER.get(chapter) or {}
    return per.get(field) or DECLARED_INHERITED.get(field)


def assert_census_declared(censuses=None, declared=None, hosted=None):
    """Guard: every ChapterEventGroup field is WRITTEN or DECLARED-INHERITED, nothing else.

    Runs in the build, after the injectors, because the census reads what they actually wrote.
    A field nobody has ruled on -- including one that appears in the struct upstream tomorrow
    -- fails here rather than being discovered by shipping a bug.

    A declaration for a field we actually WRITE fails too. A reason nobody needs is a reason
    nobody rechecks, and left standing it is how a field keeps a stale justification after it
    stops being inherited.
    """
    import sys
    known = set(fields())
    if censuses is None:
        from . import hosts
        rows = hosted if hosted is not None else hosts.hosted_chapters()
        censuses = dict((h.name, census(h.name, rows)) for h in rows)
    problems = []
    for chapter, verdicts in sorted(censuses.items()):
        for field, verdict in sorted(verdicts.items()):
            reason = (declared.get(field) if declared is not None
                      else reason_for(chapter, field))
            if field not in known:
                problems.append('%s: %r is not a ChapterEventGroup field -- the census and '
                                'the struct disagree' % (chapter, field))
            elif verdict == INHERITED and not reason:
                problems.append('%s inherits `%s` and nobody has ruled on it. Either write '
                                'the field or declare why the donor\'s value is correct, in '
                                'event_group.DECLARED_INHERITED.' % (chapter, field))
            elif verdict == ABSENT and not reason:
                problems.append('%s leaves `%s` uninitialised, so C zero-fills it -- which is '
                                'a third answer nobody chose. Declare it or write it.'
                                % (chapter, field))
            elif verdict == WRITTEN and reason and declared is not None:
                problems.append('%s WRITES `%s` but still declares a reason to inherit it -- '
                                'the declaration is stale' % (chapter, field))
    if problems:
        sys.exit('ERROR: ChapterEventGroup census (#313):\n  - ' + '\n  - '.join(problems))
    return True
