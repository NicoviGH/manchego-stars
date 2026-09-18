"""The ROMChapterData census: every `chapter_settings.json` field is WRITTEN or
DECLARED-INHERITED, and anything nobody has ruled on fails the build (#396).

A hosted chapter SQUATS a vanilla slot, so every field it does not write it keeps -- tuned
for a different chapter. That has shipped five times, each found one at a time by something
else going wrong:

    goal window / status text ids   #207   shared across vanilla slots, inherited
    battle grounds                  #289   chapters left standing on vanilla grass
    the difficulty triple           #303   ch04's Normal sat outside the parity band
    `.traps`                        #302   nearly shipped ch06 vanilla Ch7's ballistae
    `initialFogLevel`               #365   ch06 hosts on slot 7, a fogged vanilla slot

Five incidents say nothing about the sixth. This is the same answer `event_group.py` gives
for `ChapterEventGroup` (#313), in the same shape and for the same reason -- and like that
one it runs LAST in the injection sequence, because the census reads what every injector
above it actually wrote.

WHAT A FIELD IS HERE. `chapter_settings.json` is the decomp's serialized `struct
ROMChapterData` (`include/chapterdata.h`), and it groups some of the struct's arrays into
nested objects (`map`, `bgm`, `goal`, `rank`, `divination`). The census walks to the LEAVES:
`map.obj1Id` is a thing a pass writes or inherits, `map` is not.

Stdlib only.
"""
import json
import os
import subprocess

from .decomp import git_env

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DECOMP = os.path.join(REPO, 'fireemblem8u')
SETTINGS = 'src/data/chapter_settings.json'

WRITTEN, INHERITED, ABSENT = 'WRITTEN', 'INHERITED', 'ABSENT'


def _read(path):
    with open(os.path.join(DECOMP, path), encoding='utf-8') as fh:
        return json.load(fh)


def _read_head(path):
    """The COMMITTED settings, never the working tree's -- the working tree is what the build
    mutates, and the census's whole question is what we changed away from vanilla."""
    out = subprocess.run(['git', '-C', DECOMP, 'show', 'HEAD:' + path],
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


def fields(entry=None):
    """Every field of a chapter entry, in file order, read from the decomp at HEAD.

    Read rather than listed, so a field the decomp gains upstream tomorrow arrives here
    undeclared and fails the build -- which is the guard, not a side effect of it."""
    if entry is None:
        entry = _read_head(SETTINGS)['chapters'][1]
    return list(leaves(entry))


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


def census(chapter, hosted=None):
    """{field: verdict} for one hosted chapter's ROMChapterData entry.

    Only meaningful on an INJECTED tree -- `event_group.injected(paths=(SETTINGS,))` answers
    that, and the build guard runs after every injector for exactly that reason.
    """
    from . import hosts
    rows = hosted if hosted is not None else hosts.hosted_chapters()
    row = next((h for h in rows if h.name == chapter), None)
    if row is None:
        raise KeyError('%s is not a hosted chapter' % chapter)
    ours = leaves(_read(SETTINGS)['chapters'][row.host_index])
    vanilla = leaves(_read_head(SETTINGS)['chapters'][row.host_index])
    return classify(fields(), ours, vanilla)


# --- who WRITES what ---------------------------------------------------------------------
#
# A field a pass owns is WRITTEN even when the value it writes happens to equal the donor's.
# The bytes cannot tell those apart -- ch06's declared difficulty triple IS vanilla Ch7's --
# and a census that reported those as inherited would demand a declaration per coincidence,
# which routine tuning would then invalidate. #396 asks for this directly: "the census has to
# count those as written, or it will demand passes that already exist."
#
# The value of an entry here is the pass that owns the field. `tools/test_chapter_data_census`
# checks each one against `build_campaign`'s SOURCE, so a pass that stops writing its field --
# or gets renamed -- fails rather than leaving a claim nobody rechecks.
OWNED_BY_PASS = dict(
    [('map.' + f, '_retarget_host_chapter') for f in
     ('obj1Id', 'obj2Id', 'paletteId', 'tileConfigId', 'mainLayerId', 'objAnimId',
      'paletteAnimId', 'changeLayerId')] +
    [('mapEventDataId', '_retarget_host_chapter'),
     ('prepScreenNumber', '_retarget_host_chapter'),
     ('fadeToBlack', '_retarget_host_chapter'),
     # The two the chapter OWNS (#207). The rest of the `goal` block is the donor template's
     # own parameters and is declared below, not claimed here.
     ('goal.windowTextId', '_retarget_host_chapter'),
     ('goal.statusObjectiveTextId', '_retarget_host_chapter'),
     # The three TOTAL passes: each mentions every hosted chapter, which is what makes
     # "nobody wrote a line for this chapter" unreachable.
     ('initialFogLevel', 'apply_chapter_fog'),
     ('easyModeLevelMalus', 'apply_chapter_difficulty'),
     ('normalModeLevelMalus', 'apply_chapter_difficulty'),
     ('difficultModeLevelBonus', 'apply_chapter_difficulty'),
     ('battleTileSet', 'inject_battle_platforms')])


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

    # --- the goal template's own parameters ----------------------------------------------
    #
    # `_retarget_host_chapter` copies the goal block wholesale from the vanilla slot whose
    # objective TYPE the chapter names, then overrides the two text ids the chapter owns
    # (#207). These three are the template's parameters, and they are inherited from a
    # vanilla goal of the same type ON PURPOSE -- that is what "copy the template" means.
    'goal.windowDataType':
        'the objective TYPE, and the retarget FAILS THE BUILD unless the template slot '
        'matches the type the chapter declared (`goal_err`). Checked, not inherited blindly.',
    'goal.destPosX':
        'the Seize marker the goal window draws (bmudisp.c:1029). Vanilla\'s OWN Seize '
        'chapters carry 255 here -- FE8 takes the seize tile from the event script\'s '
        'Seize(x,y), not from this field -- so 255 is the vanilla answer and not a gap.',
    'goal.destPosY': 'see goal.destPosX',
    'goal.protectCharacterIndex':
        'the unit a PROTECT objective watches (eventinfo.c:558), 0 = nobody on every slot we '
        'host. No hosted chapter declares a protect objective; one that does writes this.',
    'goal.windowEndTurnNumber':
        'the turn a SURVIVE objective counts to (player_interface.c:1616). No hosted chapter '
        'declares a survive objective; one that does writes this.',

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

# The eleven phase tracks. Inherited DELIBERATELY: `decisions.md` -> "Audio: vanilla FE8
# soundtrack for MVP", so a hosted chapter plays its host slot's own vanilla music, which is
# the soundtrack the campaign ships. The six `*InHectorStory` / prologue entries are FE7
# leftovers on top of that. A chapter that wants a different track writes this field; custom
# tracks are a post-ship stretch goal on that same record.
_BGM = ('a phase track, inherited on purpose: `decisions.md` -> "Audio: vanilla FE8 '
        'soundtrack for MVP", so the chapter plays its host slot\'s own vanilla music')
DECLARED_INHERITED.update(dict.fromkeys((
    'bgm.bluePhase', 'bgm.redPhase', 'bgm.greenPhase', 'bgm.blueGreenPhaseAlt',
    'bgm.redPhaseAlt',
), _BGM))
DECLARED_INHERITED.update(dict.fromkeys((
    'bgm.bluePhaseInHectorStory', 'bgm.redPhaseInHectorStory', 'bgm.greenPhaseInHectorStory',
    'bgm.prologueInLynStory', 'bgm.prologue', 'bgm.prologueInHectorStory',
), _FE7))


def reason_for(chapter, field):
    """The declared reason a chapter may inherit a field, or None if nobody has ruled.

    `chapter` is accepted for symmetry with `event_group.reason_for` and for the per-chapter
    table a future ruling will need; no field needs one today, and an empty table is a better
    statement of that than a parameter nobody passes."""
    per = DECLARED_INHERITED_BY_CHAPTER.get(chapter) or {}
    return per.get(field) or DECLARED_INHERITED.get(field)


# chapter -> {field: reason}, consulted before the shared table. Empty today: every hosted
# chapter inherits the same set, because they all squat slots of the same vanilla shape.
DECLARED_INHERITED_BY_CHAPTER = {}


def assert_census_declared(censuses=None, declared=None, hosted=None):
    """Guard: every ROMChapterData field is WRITTEN, owned by a pass, or DECLARED-INHERITED.

    Runs in the build after the injectors, because the census reads what they actually wrote.
    A field nobody has ruled on -- including one the decomp gains upstream tomorrow -- fails
    here rather than being discovered by shipping a bug, which is how the other five were
    found.

    A declaration for a field we actually WRITE fails too: a reason nobody needs is a reason
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
            owner = OWNED_BY_PASS.get(field)
            reason = (declared.get(field) if declared is not None
                      else reason_for(chapter, field))
            if field not in known:
                problems.append('%s: %r is not a ROMChapterData field -- the census and '
                                'chapter_settings.json disagree' % (chapter, field))
            elif owner and reason:
                # A reason to inherit a field a PASS writes is stale by construction, and
                # unlike the byte-level case this does not depend on the tree being injected
                # -- ownership is a property of the code, not of the values.
                problems.append('%s declares a reason to inherit `%s`, but `%s` writes it -- '
                                'the declaration is stale' % (chapter, field, owner))
            elif owner:
                continue          # a pass owns it, whatever the bytes happen to say
            elif verdict == INHERITED and not reason:
                problems.append('%s inherits `%s` and nobody has ruled on it. Either write '
                                'the field or declare why the donor slot\'s value is correct, '
                                'in chapter_data.DECLARED_INHERITED.' % (chapter, field))
            elif verdict == ABSENT and not reason:
                problems.append('%s carries no `%s` at all, so the generated struct takes '
                                'whatever json2c defaults it to -- a third answer nobody '
                                'chose. Declare it or write it.' % (chapter, field))
            elif verdict == WRITTEN and reason and declared is not None:
                problems.append('%s WRITES `%s` but still declares a reason to inherit it -- '
                                'the declaration is stale' % (chapter, field))
    if problems:
        sys.exit('ERROR: ROMChapterData census (#396):\n  - ' + '\n  - '.join(problems))
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
        rows = data.get('layout') or data.get('tiles')
        if isinstance(rows, list) and rows:
            return len(rows[0]), len(rows)
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
