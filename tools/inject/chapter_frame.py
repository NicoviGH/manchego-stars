"""The chapter FRAME: a hosted chapter's settings row and event group, written from blank (#412).

A hosted chapter squats a vanilla slot, and the slot's two structs -- its `ROMChapterData` row
in chapter_settings.json and its `ChapterEventGroup` -- used to start as the DONOR's: every field
an injector did not touch kept vanilla's value. Six shipped bugs had that one cause (goal text
ids #207, battle grounds #289, difficulty #303, `.traps` #306, fog #365, the ch02 misc list the
census found), and the censuses (#313, #396) only caught the class after the fact.

Here the frame starts BLANK. These two writers rule on every field when they run, and a field
with no writer and no declared reason stops the build before anything is written:

  * WRITTEN by the chapter -- the `writes` / `lists` / `roster` / `scenes` it passes;
  * owned by another PASS -- fog, difficulty, battle grounds, traps, each a total pass over
    every hosted chapter (`chapter_data.OWNED_BY_PASS`, `event_group.OWNED_BY_PASS`);
  * INHERITED, with the reason the donor's value is right (`DECLARED_INHERITED` beside each).

An event list the chapter does not fill is written EMPTY, never left as the donor's. The
censuses now LIST this ruling; the build's post-pass guards check that every injected chapter
went through here and that each inherited field still reads as vanilla's.

What stays the chapter's own code: rosters, scenes and texts. The frame is the part every
chapter shares, and the part whose default used to be wrong.
"""
import json
import re
import sys

from . import chapter_data, event_group
from .decomp import _replace_brace_block
from .paths import CHAPTER_SETTINGS_JSON

# chapter -> the structs this build framed for it. The post-pass guards read it: a chapter that
# never came through here would keep every donor field, which is the default this module ends.
FRAMED = {'settings': set(), 'event_group': set()}


# --- the settings row (ROMChapterData) ---------------------------------------------------

def _assign(row, dotted, value):
    """Set one leaf of a nested settings row in place, so the row keeps its key order (the
    json is rewritten whole, and its bytes are part of the build's output)."""
    *path, leaf = dotted.split('.')
    for key in path:
        row = row[key]
    if leaf not in row:
        raise KeyError(dotted)
    row[leaf] = value


def frame_settings_row(chapter, row, writes):
    """Pure: `row` with every field ruled on -- `writes` applied, the rest kept only where a
    pass owns it or a reason declares it inherited. Exits naming every field nobody rules on.

    `row` is the tree's current row, so a pass that already ran (battle grounds) keeps what it
    wrote, and a pass still to come (fog, difficulty) overwrites what is there."""
    fields = chapter_data.fields()
    problems = ['%s writes `%s`, which is not a ROMChapterData field' % (chapter, f)
                for f in sorted(set(writes) - set(fields))]
    for field in fields:
        owner = chapter_data.owner_for(chapter, field)
        reason = chapter_data.reason_for(chapter, field)
        if field in writes:
            if owner in chapter_data.FRAME_WRITERS:
                continue
            if reason:
                problems.append('%s writes `%s` and still declares a reason to inherit it -- '
                                'the declaration is stale' % (chapter, field))
            elif owner:
                problems.append('%s writes `%s`, which `%s` owns -- one field, two writers'
                                % (chapter, field, owner))
            else:
                problems.append('%s writes `%s`, which no frame claims -- add it to '
                                'chapter_data.OWNED_BY_PASS so the census lists it'
                                % (chapter, field))
        elif owner in chapter_data.FRAME_WRITERS:
            problems.append('%s does not write `%s`, which its frame owns' % (chapter, field))
        elif not owner and not reason:
            problems.append('%s neither writes `%s` nor declares why the donor slot\'s value is '
                            'right (chapter_data.DECLARED_INHERITED)' % (chapter, field))
    if problems:
        sys.exit('ERROR: chapter settings frame (#412):\n  - ' + '\n  - '.join(problems))
    for field, value in writes.items():
        _assign(row, field, value)
    return row


def write_settings_row(chapter, host_index, writes):
    """Frame slot `host_index`'s chapter_settings.json row for `chapter`; returns the row."""
    with open(CHAPTER_SETTINGS_JSON, encoding='utf-8') as f:
        settings = json.load(f)
    row = frame_settings_row(chapter, settings['chapters'][host_index], writes)
    with open(CHAPTER_SETTINGS_JSON, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)
    FRAMED['settings'].add(chapter)
    return row


# --- the event group (ChapterEventGroup) -------------------------------------------------

LISTS, ROSTERS, SCENES = event_group.LISTS, event_group.ROSTERS, event_group.SCENES


def _group_body(info, group):
    start = info.index('struct ChapterEventGroup %s = {' % group)
    return start, info.index('};', start)


def group_symbol(info, group, field):
    """The symbol `group`.`field` points at."""
    start, end = _group_body(info, group)
    match = re.search(r'\.%s\s*=\s*([A-Za-z_]\w*)' % re.escape(field), info[start:end])
    if not match:
        sys.exit('ERROR: ChapterEventGroup %s has no .%s' % (group, field))
    return match.group(1)


def point_event_group_at(info, group, field, symbol):
    """Pure: `info` (a chN-eventinfo.h) with ChapterEventGroup `group`.`field` -> `symbol`.

    Declaring our own roster table is only half the job: the ENGINE reads the roster through
    the ChapterEventGroup, so a table nobody points at is inert and the slot quietly keeps
    using the vanilla one. That shipped for one build of ch05 and put the party on vanilla
    Ch6's start tiles, four of them inside walls, on a map whose geometry is vanilla Ch5's.
    Nothing failed: PREP ran, the map drew, the scenario PASSed.
    """
    pattern = re.compile(r'(\.%s\s*=\s*)([A-Za-z_]\w*)' % re.escape(field))
    start, end = _group_body(info, group)
    body, n = pattern.subn(lambda m: m.group(1) + symbol, info[start:end])
    if n == 0:
        sys.exit('ERROR: ChapterEventGroup %s has no .%s field to repoint' % (group, field))
    return info[:start] + body + info[end:]


def blank_list(info, symbol):
    """The empty body for event list `symbol`, by its declared type: an `EventListScr *[]`
    (a tutorial's pointer array) ends on NULL, an `EventListScr[]` on END_MAIN. Writing
    END_MAIN into the pointer array is an int-from-pointer compile error."""
    match = re.search(r'EventListScr\s*(\*?)\s*%s\s*\[\s*\]' % re.escape(symbol), info)
    if not match:
        sys.exit('ERROR: no event list %s[] to blank' % symbol)
    return '{\n    NULL\n}' if match.group(1) else '{\n    END_MAIN\n}'


def frame_event_group(chapter, info, group, lists, roster, scenes, path='<info>'):
    """Pure: `info` with `group` framed for `chapter`.

    `lists` maps a list FIELD (`turnBasedEvents`, ...) to the body the chapter fills it with;
    every other list is written empty unless the chapter declares it inherited. `roster` is
    the table both difficulties deploy, `scenes` the (beginning, ending) scripts. The list
    SYMBOLS are read from the group itself, so no chapter names a vanilla list again."""
    known = event_group.fields()
    problems = ['%s fills `%s`, which is not an event list' % (chapter, f)
                for f in sorted(set(lists) - set(LISTS))]
    for field in known:
        owner = event_group.owner_for(field)
        reason = event_group.reason_for(chapter, field)
        if owner == event_group.FRAME_WRITER:
            if reason and (field in lists or field not in LISTS):
                problems.append('%s writes `%s` and still declares a reason to inherit it -- '
                                'the declaration is stale' % (chapter, field))
        elif not owner and not reason:
            problems.append('%s leaves `%s` to the donor and nobody has ruled on it '
                            '(event_group.DECLARED_INHERITED)' % (chapter, field))
    if problems:
        sys.exit('ERROR: event group frame (#412):\n  - ' + '\n  - '.join(problems))
    for field in LISTS:
        if field not in lists and event_group.reason_for(chapter, field):
            continue
        symbol = group_symbol(info, group, field)
        body = lists.get(field) or blank_list(info, symbol)
        info = _replace_brace_block(info, symbol + '[] =', body, path)
    for field in ROSTERS:
        info = point_event_group_at(info, group, field, roster)
    for field, symbol in zip(SCENES, scenes):
        info = point_event_group_at(info, group, field, symbol)
    return info


def write_event_group(chapter, info_path, group, lists, roster, scenes):
    """Frame `group` in `info_path` for `chapter` (see frame_event_group)."""
    with open(info_path, encoding='utf-8') as f:
        info = f.read()
    info = frame_event_group(chapter, info, group, lists, roster, scenes, info_path)
    with open(info_path, 'w', encoding='utf-8') as f:
        f.write(info)
    FRAMED['event_group'].add(chapter)


def assert_framed(hosted):
    """Guard: every chapter this build injected came through both frame writers."""
    missing = ['%s (%s)' % (h.name, struct) for h in hosted
               for struct in ('settings', 'event_group') if h.name not in FRAMED[struct]]
    if missing:
        sys.exit('ERROR: %s were never framed, so they keep every donor field (#412). Call '
                 'write_settings_row / write_event_group from the injector.'
                 % ', '.join(missing))
    return True
