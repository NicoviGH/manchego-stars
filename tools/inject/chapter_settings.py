"""Chapter settings passes: fog (#365) and difficulty modes (#303), total over every host.
"""
import json
import sys

from inject.hosting import _load_chapter_yaml, chapter_yaml_for
from inject.paths import CHAPTER_SETTINGS_JSON


DIFFICULTY_MODES = ('tutorial', 'normal', 'difficult')
# mode -> the chapter_settings field the engine reads for it. "easy" is FE8's own name for
# the TUTORIAL slot: difficulty menu option 0 sets controller=0/HARD=0, which is both the
# `-easyModeLevelMalus` branch (eventscr.c:2328) and the only state CHECK_TUTORIAL fires in.
DIFFICULTY_FIELDS = {'tutorial': 'easyModeLevelMalus',
                     'normal': 'normalModeLevelMalus',
                     'difficult': 'difficultModeLevelBonus'}
DIFFICULTY_MAX = 15          # each field is a 4-bit bitfield (chapterdata.h:47-49)


def chapter_difficulty_shifts(chap):
    """A chapter's DECLARED difficulty triple, validated, in mode->shift shape (#303).

    FE8 authors one enemy table per chapter and derives all three modes from it by
    re-projecting stats at unit-load time, so these three numbers are the entire
    difference between the modes. They are declared in the chapter YAML because the
    alternative is inheritance: a hosted chapter that names none keeps whatever its
    squatted host slot shipped, tuned for a different chapter. ch04 is the case that
    paid for this rule -- it hosts on slot 5 (`I05`, normal malus 0) while its parity
    twin FE8 Ch4 carries 2, which put its Normal at x1.30, outside the parity band."""
    block = chap.get('difficulty')
    if not isinstance(block, dict):
        sys.exit('ERROR: chapter %s declares no `difficulty:` block -- a chapter that '
                 'names none INHERITS its host slot\'s numbers, which are tuned for a '
                 'different chapter (#303)' % chap.get('id', '?'))
    out = {}
    for mode in DIFFICULTY_MODES:
        if mode not in block:
            sys.exit('ERROR: chapter %s `difficulty:` is missing `%s` -- all three of %s '
                     'must be declared together' % (chap.get('id', '?'), mode,
                                                    ', '.join(DIFFICULTY_MODES)))
        value = block[mode]
        if not isinstance(value, int) or isinstance(value, bool) \
                or not 0 <= value <= DIFFICULTY_MAX:
            sys.exit('ERROR: chapter %s `difficulty.%s` is %r -- must be an integer 0..%d '
                     '(the engine field is 4 bits wide, so %d silently truncates to 0)'
                     % (chap.get('id', '?'), mode, value, DIFFICULTY_MAX,
                        DIFFICULTY_MAX + 1))
        out[mode] = value
    return out


# `initialFogLevel` is a u8 (chapterdata.h:36), not a bitfield like the difficulty maluses,
# so the only hard bound is the byte. Vanilla itself uses exactly two values across all 79
# slots -- 0 on 74 of them and 3 on five (slots 7, 19, 32, 61, 62) -- so a level is a vision
# RADIUS in tiles and a small number. 256 is the trap worth naming: it truncates to 0, which
# reads as "no fog" and looks like somebody meant it.
FOG_LEVEL_MAX = 255
FOG_NONE = 'none'            # the declared spelling of zero, so `fog:` is never blank


def chapter_fog_level(chap):
    """A chapter's DECLARED fog level, validated, as the u8 the engine reads (#365).

    Declared in the chapter YAML for the same reason the difficulty triple is: the
    alternative is inheritance. A hosted chapter keeps whatever `initialFogLevel` its
    squatted host slot shipped, and vanilla carries fog on five slots -- one of them slot 7,
    which hosts ch06. ch06 is a route puzzle across concentric water with seven crossings and a snag,
    so three-tile vision would have hidden the entire design while failing nothing.

    ch04 is why this reads from the YAML rather than only guarding inheritance: it WANTS
    fog, and got it from a literal `3` inside its injector, which means "ch04 is a fogged
    chapter" was written down nowhere a reader of ch04 would think to look."""
    if not isinstance(chap, dict):
        sys.exit('ERROR: a chapter YAML parsed as %r, not a mapping -- an empty or '
                 'comment-only chapter file reaches every declaration reader this way, so '
                 'it is refused here rather than crashing on the first `.get`' % type(chap))
    if 'fog' not in chap:
        sys.exit('ERROR: chapter %s declares no `fog:` -- a chapter that names none '
                 'INHERITS its host slot\'s initialFogLevel, which belongs to a different '
                 'chapter. Declare `fog: none` for no fog, or a vision radius in tiles '
                 '(vanilla\'s fogged chapters all use 3) (#365)' % chap.get('id', '?'))
    value = chap['fog']
    if value == FOG_NONE:
        return 0
    if isinstance(value, bool) or not isinstance(value, int) \
            or not 1 <= value <= FOG_LEVEL_MAX:
        sys.exit('ERROR: chapter %s declares `fog: %r` -- must be `%s` or a vision radius '
                 '1..%d. The engine field is a u8, so %d truncates to 0 and reads as no fog '
                 'at all' % (chap.get('id', '?'), value, FOG_NONE, FOG_LEVEL_MAX,
                             FOG_LEVEL_MAX + 1))
    return value


def apply_chapter_fog(campaign, verbose=False):
    """Write every hosted chapter's DECLARED fog level into its own host slot (#365).

    The fifth and last `chapter_settings` field a hosted chapter could inherit unexamined.
    The other four each got a total pass after something went wrong once: goal text ids
    (#207), battle grounds (`CHAPTER_BATTLE_TILESETS`), difficulty (#303) and `.traps`
    (#302). This is the same shape and deliberately TOTAL -- every hosted chapter is
    mentioned, so "nobody wrote a line for this chapter" stops being reachable."""
    from inject.hosts import hosted_chapters
    with open(CHAPTER_SETTINGS_JSON, encoding='utf-8') as f:
        settings = json.load(f)
    applied = []
    for chapter in hosted_chapters():
        chap = _load_chapter_yaml(campaign, chapter_yaml_for(chapter.name))
        level = chapter_fog_level(chap)
        settings['chapters'][chapter.host_index]['initialFogLevel'] = level
        applied.append((chapter.name, level))
    with open(CHAPTER_SETTINGS_JSON, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)
    if verbose:
        print('  fog: %s' % ', '.join('%s=%d' % (n, l) for n, l in applied))
    return applied


def apply_chapter_difficulty(campaign, verbose=False):
    """Write every hosted chapter's DECLARED difficulty triple into its own host slot.

    A pass over the registry rather than a line inside `_retarget_host_chapter`, for one
    reason: the prologue does not retarget at all (it runs on the slot it was given), so
    writing these where the retarget happens would silently miss a chapter -- the exact
    shape of #241. Mirrors `CHAPTER_BATTLE_TILESETS`, which solved this same problem for
    the battle grounds: one pass that has to MENTION every hosted chapter."""
    from inject.hosts import hosted_chapters
    with open(CHAPTER_SETTINGS_JSON, encoding='utf-8') as f:
        settings = json.load(f)
    applied = []
    for chapter in hosted_chapters():
        chap = _load_chapter_yaml(campaign, chapter_yaml_for(chapter.name))
        shifts = chapter_difficulty_shifts(chap)
        slot = settings['chapters'][chapter.host_index]
        for mode, field in DIFFICULTY_FIELDS.items():
            slot[field] = shifts[mode]
        applied.append((chapter.name, shifts))
    with open(CHAPTER_SETTINGS_JSON, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)
    if verbose:
        print('  difficulty (tutorial/normal/difficult): %s' % ', '.join(
            '%s %d/%d/%d' % (n, s['tutorial'], s['normal'], s['difficult'])
            for n, s in applied))
    return applied
