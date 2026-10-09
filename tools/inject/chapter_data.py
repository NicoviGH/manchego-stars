"""The ROMChapterData ruling: every `chapter_settings.json` field is WRITTEN, owned by a pass,
or DECLARED-INHERITED (#396).

A hosted chapter SQUATS a vanilla slot, so every field it did not write it used to keep -- tuned
for a different chapter. That shipped five times, each found one at a time by something else
going wrong:

    goal window / status text ids   #207   shared across vanilla slots, inherited
    battle grounds                  #289   chapters left standing on vanilla grass
    the difficulty triple           #303   ch04's Normal sat outside the parity band
    `.traps`                        #302   nearly shipped ch06 vanilla Ch7's ballistae
    `initialFogLevel`               #365   ch06 hosts on slot 7, a fogged vanilla slot
    `bgm`                           #26    every chapter played the NEXT vanilla chapter's music

The row is now FRAMED from blank (`chapter_frame.write_settings_row`, #412), and the tables
below are what the frame reads -- the same shape `event_group.py` gives `ChapterEventGroup`. The
census lists them; the build checks the bytes only for what they leave inherited.

WHAT A FIELD IS HERE. `chapter_settings.json` is the decomp's serialized `struct
ROMChapterData` (`include/chapterdata.h`), and it groups some of the struct's arrays into
nested objects (`map`, `bgm`, `goal`, `rank`, `divination`). The census walks to the LEAVES:
`map.obj1Id` is a thing a pass writes or inherits, `map` is not.

Stdlib only.
"""
import json
import os
import subprocess

from .decomp import DECOMP, git_env, REPO, SUBMODULE
SETTINGS = 'src/data/chapter_settings.json'

WRITTEN, INHERITED, ABSENT, UNRULED = 'WRITTEN', 'INHERITED', 'ABSENT', 'UNRULED'


def _read(path):
    with open(os.path.join(DECOMP, path), encoding='utf-8') as fh:
        return json.load(fh)


def _read_head(path):
    """The COMMITTED settings, never the working tree's -- the working tree is what the build
    mutates, and the census's whole question is what we changed away from vanilla."""
    out = subprocess.run(['git', '-C', SUBMODULE, 'show', 'HEAD:' + path],
                         capture_output=True, text=True, env=git_env())
    if out.returncode != 0:
        raise RuntimeError('cannot read HEAD:%s from the decomp: %s' % (path, out.stderr))
    return json.loads(out.stdout)


def leaves(entry, prefix=''):
    """{dotted path: value} for one chapter entry, nested groups walked to their leaves."""
    out = {}
    for key, value in entry.items():
        path = prefix + key
        if isinstance(value, dict):
            out.update(leaves(value, path + '.'))
        else:
            out[path] = value
    return out


_FIELDS = None


def fields(entry=None):
    """Every field of a chapter entry, in file order, read from the decomp at HEAD.

    Read rather than listed, so a field the decomp gains upstream tomorrow arrives here
    undeclared and fails the build -- which is the guard, not a side effect of it. Memoised:
    the frame asks once per hosted chapter, and each read is a `git show`."""
    global _FIELDS
    if entry is not None:
        return list(leaves(entry))
    if _FIELDS is None:
        _FIELDS = list(leaves(_read_head(SETTINGS)['chapters'][1]))
    return list(_FIELDS)


def classify(names, ours, vanilla):
    """{field: WRITTEN/INHERITED/ABSENT} for one chapter's entry against its own slot at HEAD.

    A field we write to the value the donor already carried reads INHERITED, because that is
    what the bytes say and the census reports bytes. `event_group` has the same wrinkle and
    answers it the same way: the chapter declares the coincidence (ch06's difficulty triple
    matches vanilla Ch7's), which is a fact worth writing down rather than a hole."""
    out = {}
    for name in names:
        if name not in ours:
            out[name] = ABSENT
        elif ours[name] == vanilla.get(name):
            out[name] = INHERITED
        else:
            out[name] = WRITTEN
    return out


def census(chapter):
    """{field: WRITTEN/INHERITED/UNRULED} for one hosted chapter: the frame's ruling, listed.

    Read from the declarations, not the tree: the row is framed from blank
    (`chapter_frame.write_settings_row`, #412), so what a field holds is decided here before
    anything is written. UNRULED never survives a build -- the frame exits on it."""
    out = {}
    for field in fields():
        if owner_for(chapter, field):
            out[field] = WRITTEN
        else:
            out[field] = INHERITED if reason_for(chapter, field) else UNRULED
    return out


# --- who WRITES what ---------------------------------------------------------------------
#
# A field a pass owns is WRITTEN even when the value it writes happens to equal the donor's.
# The bytes cannot tell those apart -- ch06's declared difficulty triple IS vanilla Ch7's --
# and a census that reported those as inherited would demand a declaration per coincidence,
# which routine tuning would then invalidate. #396 asks for this directly: "the census has to
# count those as written, or it will demand passes that already exist."
#
# The value of an entry here is the pass that owns the field. `tools/test_chapter_data_census`
# checks each one against the injector's SOURCE, so a pass that stops writing its field --
# or gets renamed -- fails rather than leaving a claim nobody rechecks.
OWNED_BY_PASS = dict(
    [('map.' + f, '_retarget_host_chapter') for f in
     ('obj1Id', 'obj2Id', 'paletteId', 'tileConfigId', 'mainLayerId', 'objAnimId',
      'paletteAnimId', 'changeLayerId')] +
    [('mapEventDataId', '_retarget_host_chapter'),
     ('prepScreenNumber', '_retarget_host_chapter'),
     ('fadeToBlack', '_retarget_host_chapter'),
     # The two the chapter OWNS (#207), and the goal template's own parameters, copied from a
     # vanilla slot whose objective TYPE the chapter names (`GOAL_TEMPLATE`).
     ('goal.windowTextId', '_retarget_host_chapter'),
     ('goal.statusObjectiveTextId', '_retarget_host_chapter')] +
    [('goal.' + f, '_retarget_host_chapter') for f in
     ('windowDataType', 'destPosX', 'destPosY', 'protectCharacterIndex', 'windowEndTurnNumber')] +
    [# The TOTAL passes: each mentions every hosted chapter, which is what makes
     # "nobody wrote a line for this chapter" unreachable.
     ('initialFogLevel', 'apply_chapter_fog'),
     ('easyModeLevelMalus', 'apply_chapter_difficulty'),
     ('normalModeLevelMalus', 'apply_chapter_difficulty'),
     ('difficultModeLevelBonus', 'apply_chapter_difficulty'),
     ('battleTileSet', 'inject_battle_platforms')] +
    # The fourth total pass: a chapter plays its vanilla TWIN's music, the whole block copied
    # (ADR 0336). Inherited, it was the host slot's -- the NEXT vanilla chapter's.
    [('bgm.' + f, 'apply_chapter_music') for f in
     ('bluePhase', 'redPhase', 'greenPhase', 'blueGreenPhaseAlt', 'redPhaseAlt',
      'bluePhaseInHectorStory', 'redPhaseInHectorStory', 'greenPhaseInHectorStory',
      'prologueInLynStory', 'prologue', 'prologueInHectorStory')])

# The prologue is the exception: it does NOT retarget its host slot (inject/hosts.py) -- it runs
# on the slot it was given and frames the row itself. It writes the map, the goal, the fade and
# its own event group id, and keeps the slot's `prepScreenNumber` (declared below).
PROLOGUE = 'prologue'
PROLOGUE_WRITES = tuple(['map.' + f for f in
                         ('obj1Id', 'obj2Id', 'paletteId', 'tileConfigId', 'mainLayerId',
                          'objAnimId', 'paletteAnimId', 'changeLayerId')] +
                        ['goal.' + f for f in
                         ('windowTextId', 'statusObjectiveTextId', 'windowDataType', 'destPosX',
                          'destPosY', 'protectCharacterIndex', 'windowEndTurnNumber')] +
                        ['mapEventDataId', 'fadeToBlack'])

# The two passes that FRAME a row (`chapter_frame.write_settings_row`): every field they own
# must come in their `writes`, and nothing they do not own may.
FRAME_WRITERS = ('_retarget_host_chapter', 'inject_prologue')


def owner_for(chapter, field):
    """The pass that WRITES this field for this chapter, or None if nobody does.

    Chapter-aware, because `_retarget_host_chapter` is not called by every injector. A census
    that answered this globally would mark a field written for a chapter whose injector never
    touches it -- which is the failure class this whole guard exists for, inside the guard.
    """
    if chapter == PROLOGUE:
        return 'inject_prologue' if field in PROLOGUE_WRITES else (
            None if OWNED_BY_PASS.get(field) == '_retarget_host_chapter'
            else OWNED_BY_PASS.get(field))
    return OWNED_BY_PASS.get(field)


# --- the ruling --------------------------------------------------------------------------
#
# Every field a hosted chapter INHERITS needs a reason here, and a field with no reason fails
# the build. Most of these are "inherited, and here is why that is safe" -- which is the
# census's value. It is the DECLARATION that is the work, not a pass per field.
#
# Each reason names the CONDITION that would make it wrong, because a reason that only says
# "unused" ages badly: the five incidents this guard exists for were all fields somebody had
# assumed were unused.
DECLARED_INHERITED = {
    # --- read by live engine code, and safe for a stated reason --------------------------
    'initialWeather':
        'the intro/`bmio` weather (bmio.c:1002). Every slot we host ships WEATHER_FINE, so '
        'there is no donor weather to leak. A chapter that WANTS weather writes it.',
    'initialPosX':
        'the chapter-intro camera centre (chapterintrofx.c:864, chapterintrofx_title.c:92). '
        'Inheriting the slot\'s tile is safe only while it lands inside OUR map -- which is a '
        'different chapter\'s geometry from the slot\'s -- so that is MEASURED, not assumed: '
        '`intro_camera_out_of_bounds()`.',
    'initialPosY': 'see initialPosX -- measured by `intro_camera_out_of_bounds()`',
    'mapCrackedWallHeath':
        'the HP of a destructible wall (bmtrick.c:197). Every hosted chapter declares its '
        'traps (#306) and none places a cracked wall, so nothing reads it. A chapter that '
        'places one writes this.',
    'victorySongEnemyThreshold':
        'how few enemies must remain for the victory theme (bm.c:1188). Every slot we host '
        'carries vanilla\'s own 1, so the inherited value IS the vanilla behaviour.',
    'gmapEventId':
        'indexes the WORLD MAP event tables (worldmap_main.c:1993). We ship no world map -- '
        '`_patch_battle_map_kind_fallback` routes every slot-2+ chapter to STORY -- so those '
        'tables are never entered. Revisit with #29.',
    'internalName':
        'a DEBUG string (bmdebug.c:954) and nothing else reads it; the label the player sees '
        'is `chapTitleTextId`.',
    'chapTitleId':
        'the title CARD graphic id. Each slot points at its own, and the chapter overwrites '
        'the ART at that id rather than repointing the field.',
    'chapTitleTextId':
        'the title STRING id. Same shape as chapTitleId: the chapter writes its own title '
        'into the slot\'s message id (`set_message_body(host["chapTitleTextId"], ...)`), so '
        'repointing the field would only move the problem.',
    'hasPrepScreen':
        'an FE7 leftover, FALSE for every FE8 chapter including ones that plainly have prep '
        '(chapterdata.h:37). Our prep comes from the deploy cap, never from this field -- '
        'AGENTS.md says so because reading it once produced a bogus "our prep is a '
        'divergence" claim.',
    'merchantPosX':
        'the world-map merchant tile, 255 (= none) on every slot we host. No world map (#29).',
    'merchantPosY': 'see merchantPosX',

    # --- FE7 leftovers the decomp itself marks dead ---------------------------------------
    #
    # Every one of these is commented "left over from FE7" in include/chapterdata.h. FE8 has
    # no Hector story, no divination tent and no tactics/exp/funds ranking, and nothing reads
    # them. Grouped in the source, listed leaf by leaf below, so a field the decomp gains
    # tomorrow is NOT quietly covered by a prefix.
}

_FE7 = 'an FE7 leftover the decomp marks dead in chapterdata.h; FE8 never reads it'

DECLARED_INHERITED.update(dict.fromkeys((
    'chapTitleIdInHectorStory', 'chapTitleTextIdInHectorStory',
    'prepScreenNumberInHectorStory', 'merchantPosXInHectorStory',
    'merchantPosYInHectorStory',
    'divination.text.beginning', 'divination.text.EliwoodStory',
    'divination.text.HectorStory', 'divination.text.ending',
    'divination.portrait', 'divination.fee',
    # The FE7 rank tables: tactics turns, exp thresholds and funds gold, each doubled for a
    # Hector story FE8 does not have. FE8 ships no rank screen at all.
    'rank.tactics.A.EliwoodStory.Normal', 'rank.tactics.A.EliwoodStory.Hard',
    'rank.tactics.A.HectorStory.Normal', 'rank.tactics.A.HectorStory.Hard',
    'rank.tactics.B.EliwoodStory.Normal', 'rank.tactics.B.EliwoodStory.Hard',
    'rank.tactics.B.HectorStory.Normal', 'rank.tactics.B.HectorStory.Hard',
    'rank.tactics.C.EliwoodStory.Normal', 'rank.tactics.C.EliwoodStory.Hard',
    'rank.tactics.C.HectorStory.Normal', 'rank.tactics.C.HectorStory.Hard',
    'rank.tactics.D.EliwoodStory.Normal', 'rank.tactics.D.EliwoodStory.Hard',
    'rank.tactics.D.HectorStory.Normal', 'rank.tactics.D.HectorStory.Hard',
    'rank.exp.A.EliwoodStory.Normal', 'rank.exp.A.EliwoodStory.Hard',
    'rank.exp.A.HectorStory.Normal', 'rank.exp.A.HectorStory.Hard',
    'rank.exp.B.EliwoodStory.Normal', 'rank.exp.B.EliwoodStory.Hard',
    'rank.exp.B.HectorStory.Normal', 'rank.exp.B.HectorStory.Hard',
    'rank.exp.C.EliwoodStory.Normal', 'rank.exp.C.EliwoodStory.Hard',
    'rank.exp.C.HectorStory.Normal', 'rank.exp.C.HectorStory.Hard',
    'rank.exp.D.EliwoodStory.Normal', 'rank.exp.D.EliwoodStory.Hard',
    'rank.exp.D.HectorStory.Normal', 'rank.exp.D.HectorStory.Hard',
    'rank.funds.EliwoodStory.Normal', 'rank.funds.EliwoodStory.Hard',
    'rank.funds.HectorStory.Normal', 'rank.funds.HectorStory.Hard',
    'unk3D', 'unk5E', 'unk91', 'unk92', 'unk93',
), _FE7))

def reason_for(chapter, field):
    """The declared reason a chapter may inherit a field, or None if nobody has ruled."""
    per = DECLARED_INHERITED_BY_CHAPTER.get(chapter) or {}
    return per.get(field) or DECLARED_INHERITED.get(field)


# chapter -> {field: reason}, consulted before the shared table above.
DECLARED_INHERITED_BY_CHAPTER = {
    # The one field `_retarget_host_chapter` writes that `inject_prologue` does not: the
    # prologue has no prep screen, so it keeps its slot's number.
    PROLOGUE: {
        'prepScreenNumber':
            'the double-wide glyph index the PREP header reads. The prologue has no prep '
            'screen -- prep is standing protocol from ch01 on (AGENTS.md / decisions.md), and '
            'the prologue is a fixed two-guest tutorial -- so nothing reads vanilla\'s 2. A '
            'prologue that gains prep writes it.',
    },
}


def behind_the_frame(chapter, kept, ours, vanilla):
    """Pure: a problem for each field the frame left INHERITED that no longer holds the donor
    slot's value."""
    return ['%s declares `%s` inherited, but the build changed it -- something wrote it '
            'behind the frame' % (chapter, field)
            for field, verdict in sorted(classify(kept, ours, vanilla).items())
            if verdict != INHERITED]


def assert_census_declared(hosted=None):
    """Guard: every field the frame left INHERITED still holds the donor slot's value.

    Runs after every pass. The frame rules on each field before it writes, so what is left to
    check is the claim itself: a pass that writes an "inherited" field behind the frame's back
    makes its declared reason wrong, and only the bytes can say so."""
    import sys
    from . import hosts
    rows = hosted if hosted is not None else hosts.hosted_chapters()
    ours_all, head_all = _read(SETTINGS)['chapters'], _read_head(SETTINGS)['chapters']
    problems = []
    for row in rows:
        verdicts = census(row.name)
        problems += ['%s: `%s` is UNRULED' % (row.name, f)
                     for f, v in sorted(verdicts.items()) if v == UNRULED]
        kept = [f for f, v in verdicts.items() if v == INHERITED]
        problems += behind_the_frame(row.name, kept, leaves(ours_all[row.host_index]),
                                     leaves(head_all[row.host_index]))
    known = set(fields())
    problems += ['%r is ruled on but is not a ROMChapterData field' % f
                 for f in sorted(set(OWNED_BY_PASS) | set(DECLARED_INHERITED)) if f not in known]
    if problems:
        sys.exit('ERROR: ROMChapterData census (#396, #412):\n  - ' + '\n  - '.join(problems))
    return True


# --- the one inherited field whose safety is a property of OUR map -----------------------

def _map_size(chapter_name, campaign='rime-of-the-frostmaiden'):
    """(width, height) of a chapter's painted map, from the layout JSON the build compiles."""
    import glob
    stem = chapter_name if chapter_name != 'prologue' else 'ch00'
    pattern = os.path.join(REPO, 'campaigns', campaign, 'maps', stem + '*.json')
    for path in sorted(glob.glob(pattern)):
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
        if 'width' in data and 'height' in data:
            return int(data['width']), int(data['height'])
    return None


def intro_camera_out_of_bounds(cameras=None, sizes=None, campaign='rime-of-the-frostmaiden'):
    """[(chapter, (x, y), (w, h))] for every hosted chapter whose INHERITED intro camera tile
    falls outside its own map.

    This is what makes `initialPosX/Y`'s declaration a measurement. The field is the chapter
    intro's camera centre, and a hosted chapter inherits it from its host SLOT while its map
    comes from a DONOR -- a different vanilla chapter (ch06 hosts on slot 7 and paints FE8
    Ch13's geometry). Nothing else in the build compares those two, so a repaint that shrinks
    a map past the slot's tile would park the intro camera off the map with no symptom until
    somebody watched the intro.
    """
    if cameras is None:
        from . import hosts
        head = _read_head(SETTINGS)['chapters']
        cameras = dict((h.name, (head[h.host_index]['initialPosX'],
                                 head[h.host_index]['initialPosY']))
                       for h in hosts.hosted_chapters())
    out = []
    for name, (x, y) in sorted(cameras.items()):
        size = sizes.get(name) if sizes is not None else _map_size(name, campaign)
        if size is None:
            continue
        if not (0 <= x < size[0] and 0 <= y < size[1]):
            out.append((name, (x, y), size))
    return out
