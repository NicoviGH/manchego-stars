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
