"""The host-slot registry: which vanilla chapter slot each of our chapters occupies,
and which ChapterEventGroup its injector fills.

Kept STDLIB-ONLY on purpose, like decomp.py next to it. `tools/check.py` lints this in
CI's lightweight `checks` job, which installs pyyaml and nothing else; the first version
of that lint imported build_campaign, which imports Pillow at module scope, so the job
would have failed every push with `build_campaign does not import: No module named 'PIL'`
-- a red check that names the wrong problem (#241). build_campaign re-exports everything
here, so the constants still read as `bc.CH04_HOST_INDEX` at their call sites.

Why a registry at all: retargeting a host slot's MAP ids alone is enough to make a chapter
LOOK right while it runs the host slot's roster and scripts. That is silent and total, and
it is how ch04 shipped once (docs/adding-a-chapter.md step 4).
"""
import ast
import collections
import os
import re
import sys

_TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_CAMPAIGN_PY = os.path.join(_TOOLS, 'build_campaign.py')

# --- the declarations themselves -------------------------------------------------------
# Declaring CHNN_HOST_INDEX + CHNN_EVENT_GROUP here is what ENROLS a chapter. There is no
# list to remember to update, and undeclared_injectors() below fails the build if an
# inject_chNN exists without them.

PROLOGUE_CHAPTER_INDEX = 0   # CHAPTER_L_PROLOGUE -- the vanilla slot we configure then clone
PROLOGUE_HOST_INDEX = 1      # CHAPTER_L_1 -- normal chapter slot we actually load (New Game
                             # redirects 0 -> 1). The prologue slot has special engine paths
                             # that break our stripped chapter; a normal slot does not.
PROLOGUE_EVENT_GROUP = 'Ch1Events'   # the group slot 1 already points at; the prologue is the
                                     # one chapter that does NOT retarget (inject_prologue
                                     # step 1: asset[7] garbles the HUD, asset[10] loads clean)

CH01_HOST_INDEX = 2          # CHAPTER_L_2 -- the prologue ending's MNC2(0x2) target
CH01_EVENT_GROUP = 'Ch2Events'   # the ChapterEventGroup this injector fills (see _retarget_host_chapter)

CH02_HOST_INDEX = 3          # CHAPTER_L_3 -- ch01's ending MNC2(0x3) target
CH02_EVENT_GROUP = 'Ch3Events'   # the ChapterEventGroup this injector fills (see _retarget_host_chapter)

CH03_HOST_INDEX = 4
CH03_EVENT_GROUP = 'Ch4Events'   # the ChapterEventGroup this injector fills (see _retarget_host_chapter)

CH04_HOST_INDEX = 5
# The ChapterEventGroup this injector fills. NOT derivable from the slot index: vanilla's
# slot index tracks the chapter number only up to 4, because FE8 inserts chapter 5X at
# slot 5. So slot 5 ships pointing at Ch5XEvents, and every ch04 event is written into the
# Ch5* symbols -- _retarget_host_chapter repoints the slot or the chapter runs 5X's roster
# and scripts underneath our map.
CH04_EVENT_GROUP = 'Ch5EventData'

CH05_HOST_INDEX = 6
# Slot 6 SHIPS pointing at Ch5EventData -- the very group ch04 fills on slot 5. Leaving it
# alone would not be "the slot already points somewhere sensible"; it would put two of our
# chapters on one event group, and the second one to load would run the first one's roster
# and scripts under its own map. From slot 6 on, vanilla's slot index leads the chapter
# number by one (slot 5 is the inserted Ch5X), so slot N ships chapter N-1's group and the
# retarget is mandatory for every chapter after this one too.
CH05_EVENT_GROUP = 'Ch6Events'

CH06_HOST_INDEX = 7
# Slot 7 SHIPS pointing at Ch6Events -- the group ch05 fills on slot 6. Same trap as ch05's,
# one slot along: leaving it would put ch05 and ch06 on ONE event group, and the second to
# load would run the first's roster and scripts under its own map. Derived, not guessed:
# gChapterDataAssetTable[36] is Ch6Events and [39] is Ch7EventData, and slot 8 is the slot
# that ships the latter. So our chapter N takes the group named for chapter N, and the slot
# it sits on keeps shipping chapter N-1's -- the pattern every chapter from ch04 follows.
CH06_EVENT_GROUP = 'Ch7EventData'

# --- discovery -------------------------------------------------------------------------

HostedChapter = collections.namedtuple(
    'HostedChapter', 'name number host_index event_group')

_HOST_INDEX_RE = re.compile(r'^(CH(\d+))_HOST_INDEX$')
_INJECTOR_RE = re.compile(r'^inject_(prologue|ch(\d+))$')


def hosted_chapters(scope=None):
    """Every chapter this build hosts, DISCOVERED from the constants above.

    The prologue is enrolled like any other chapter even though its constants are not
    CHNN_-shaped. It was invisible to the first version of this function, which left slot 1
    out of the collision map -- so a later CH05_HOST_INDEX = 1 would have passed the guard
    and quietly overwritten the prologue's events (#241).

    Ordered by chapter NUMBER, not name: the prologue is 0 and must lead, and a name sort
    against a sorted() scan is a test that cannot fail.

    Raises ValueError rather than sys.exit: the lints and tests that consume this need to
    assert on the failure, not die inside it.
    """
    scope = globals() if scope is None else scope
    found, by_slot = [], {}

    def enrol(name, number, prefix, slot, group):
        if slot in by_slot:
            raise ValueError(
                'host slot %d is claimed by both %s and %s -- one chapter would overwrite '
                'the other\'s events' % (slot, by_slot[slot], name))
        by_slot[slot] = name
        found.append(HostedChapter(name, number, slot, group))

    enrol('prologue', 0, 'PROLOGUE', scope['PROLOGUE_HOST_INDEX'],
          scope['PROLOGUE_EVENT_GROUP'])
    for name in sorted(scope):
        match = _HOST_INDEX_RE.match(name)
        if not match:
            continue
        prefix, number = match.group(1), int(match.group(2))
        group = scope.get('%s_EVENT_GROUP' % prefix)
        if group is None:
            raise ValueError(
                '%s_HOST_INDEX is declared with no %s_EVENT_GROUP. A hosted slot must NAME '
                'the ChapterEventGroup its injector fills -- never assume the slot already '
                'points there. Retargeting the map ids alone still makes the chapter LOOK '
                'right while it runs the host slot\'s roster and scripts (see '
                'docs/adding-a-chapter.md step 4).' % (prefix, prefix))
        enrol(prefix.lower(), number, prefix, scope[name], group)
    return sorted(found, key=lambda c: c.number)


def injector_chapters(path=BUILD_CAMPAIGN_PY, source=None):
    """The chapters build_campaign actually has an injector for, read from its SOURCE.

    ast.parse rather than import, for the same reason this module is stdlib-only: the lint
    that consumes it runs in a CI job with no Pillow.
    """
    if source is None:
        with open(path, encoding='utf-8') as f:
            source = f.read()
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        match = _INJECTOR_RE.match(node.name)
        if match:
            found.append(('prologue', 0) if match.group(1) == 'prologue'
                         else (match.group(1), int(match.group(2))))
    return [name for name, _ in sorted(set(found), key=lambda pair: pair[1])]


def undeclared_injectors(path=BUILD_CAMPAIGN_PY, source=None, scope=None):
    """Injectors that exist but enrol nothing -- discovery's blind spot.

    Discovery covers a chapter that spells its constants right. `inject_ch05` with a typo'd
    or missing CH05_HOST_INDEX is simply not found, and every guard built on the registry
    passes with one chapter fewer and no complaint. That is the ch04 failure class #138 set
    out to close, so it is a gate, not a convention (#241).
    """
    enrolled = {c.name for c in hosted_chapters(scope)}
    return [name for name in injector_chapters(path, source) if name not in enrolled]


# --- bare-literal message ids (#346) ----------------------------------------------------

MessageLiteral = collections.namedtuple('MessageLiteral', 'msg_id chapter lineno')

# The one function that WRITES a message body. Every id the build spends passes through it.
MESSAGE_WRITER = 'set_message_body'

_literal_cache = {}


def _callsites():
    """`tools/callsites.py`, imported off _TOOLS rather than off whoever set sys.path.

    Stdlib-only, like everything else here -- it imports ast and dataclasses and nothing
    else -- so this keeps the promise the module docstring makes: the lean `checks` CI job
    can read this file without Pillow.
    """
    if _TOOLS not in sys.path:
        sys.path.insert(0, _TOOLS)
    import callsites
    return callsites


def literal_message_ids(path=BUILD_CAMPAIGN_PY, source=None):
    """Message ids written as a BARE LITERAL at a `set_message_body` call site, from SOURCE.

    `build_campaign.injector_message_ids` finds an id by the NAME of the constant holding
    it, so an id passed as hex AT the call site has no name to be found by. The prologue and
    ch01 write twelve of them, and they are visible to the guards today only because someone
    grepped for them once and hand-transcribed them into `PROLOGUE_LITERAL_MSGS` /
    `CH01_LITERAL_MSGS`. That makes the promise in that docstring -- "registering a new one
    is enough, there is no second list to remember" -- false for exactly this class: the next
    bare literal is invisible until a human notices it (#346). This is the mechanism.

    Read through `callsites`, not a regex: `msg_id` is passed POSITIONALLY at all 71 call
    sites, so `grep msg_id=` finds none of them, and binding "the second argument" by hand is
    the assumption `callsites` exists to remove. Same reason `check_wrap_widths_are_pixels`
    reads bindings rather than text.

    Each literal is attributed to the injector that WRITES it -- `inject_prologue` is ch00,
    `inject_chNN` is chNN, which are HOSTED_CHAPTER_MESSAGE_IDS' own keys -- so a literal
    carries an OWNER and not just a value. A literal outside every injector reports
    `chapter=None`; it is still an id the build spends, but nothing can say whose it is.

    Raises ValueError when `source` does not define the writer. An unresolvable signature
    switches positional binding off in `callsites.scan`, which would leave this returning ()
    for a file full of literals -- a scan that quietly stops scanning, which is the failure
    #341 shipped and decisions.md 2026-09-02 names.
    """
    if source is None and path in _literal_cache:
        return _literal_cache[path]
    cache_key = None
    if source is None:
        with open(path, encoding='utf-8') as f:
            source = f.read()
        cache_key = path

    callsites = _callsites()
    params = callsites.signature(source, MESSAGE_WRITER, path)
    if 'msg_id' not in params:
        raise ValueError(
            '%s does not define %s(.., msg_id, ..), so its call sites cannot be bound and '
            'every bare literal in it would read as absent' % (path, MESSAGE_WRITER))

    tree = ast.parse(source, path)
    # Injectors never nest, so a line span is enough to say which one owns a call. A call in
    # a module-level helper falls outside all of them and reports no chapter, which is the
    # truth: the helper is called with an id, it does not choose one.
    spans = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        match = _INJECTOR_RE.match(node.name)
        if match:
            spans.append((node.lineno, node.end_lineno or node.lineno,
                          'ch00' if match.group(2) is None else match.group(1)))

    found = []
    for site in callsites.scan(source, MESSAGE_WRITER, path, params=params):
        if site.kind != 'call':
            continue
        try:
            value = int(site.bound.get('msg_id'), 0)
        except (TypeError, ValueError):
            continue          # a named constant or an expression: discovery by NAME owns it
        chapter = next((c for lo, hi, c in spans if lo <= site.lineno <= hi), None)
        found.append(MessageLiteral(value, chapter, site.lineno))
    found = tuple(sorted(found, key=lambda lit: lit.lineno))
    if cache_key is not None:
        # ast.parse of a 14k-line module costs ~60ms; injector_message_ids is called from the
        # build AND from a dozen tests. Keyed by path and skipped for a caller-supplied
        # source, which is never the file on disk.
        _literal_cache[cache_key] = found
    return found
