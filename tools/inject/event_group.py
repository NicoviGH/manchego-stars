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


def _defining_file(symbol, search_dirs=None):
    """The decomp-relative path that DEFINES a symbol, or None.

    Searched over the event sources and the data tables the groups point into. A symbol we
    cannot locate is reported as unresolved rather than assumed unchanged -- assuming would
    turn "I could not check" into "it is fine", which is the failure this guard is about.
    """
    pattern = re.compile(_DEFN % re.escape(symbol))
    for rel_dir in (search_dirs or (os.path.join('src', 'events'), 'src')):
        base = os.path.join(DECOMP, rel_dir)
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            if not (name.endswith('.h') or name.endswith('.c')):
                continue
            path = os.path.join(base, name)
            try:
                with open(path, encoding='utf-8', errors='replace') as fh:
                    text = fh.read()
            except OSError:
                continue
            if pattern.search(text):
                return os.path.join(rel_dir, name)
    return None


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
