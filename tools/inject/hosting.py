"""A chapter's host slot and its YAML: loading, retargeting, recruit numbering.
"""
import copy
import json
import os
import sys

from yaml_loader import yaml_load
from inject.namespace import injector_constants
from inject.asset_table import _asm_table_word_index
from inject.decomp import REPO
from inject.paths import ASSET_TABLE_S, CHAPTER_SETTINGS_JSON


_CHAPTER_YAML_CACHE = {}


def _load_chapter_yaml(campaign, filename):
    """Parse a chapter YAML, reusing the parse when the file on disk has not changed.

    A build asks for the same handful of chapter files dozens of times (62 calls, ~9s of a
    51s injection) because every injector that needs one line of a chapter parses the whole
    document. The cache is keyed on the file's identity AND its mtime/size, so editing a
    chapter mid-build is still picked up. Callers get a deep copy: several injectors edit
    the dict they are handed, and a shared parse must not let one injector's edits leak
    into the next one's view of the chapter.
    """
    path = os.path.join(REPO, 'campaigns', campaign, 'chapters', filename)
    st = os.stat(path)
    key = (path, st.st_mtime_ns, st.st_size)
    if key not in _CHAPTER_YAML_CACHE:
        with open(path, encoding='utf-8') as f:
            _CHAPTER_YAML_CACHE[key] = yaml_load(f)
    return copy.deepcopy(_CHAPTER_YAML_CACHE[key])


def chapter_yaml_for(name):
    """A `hosted_chapters()` registry name -> its chapter YAML filename.

    Discovered from the injector's own constants (`inject.namespace`) rather than a second
    hand-kept table, the same way inject.hosts discovers host slots: a chapter that declares a host slot but no
    YAML fails here instead of being skipped by every pass built on the registry (#241)."""
    const = ('PROLOGUE_CHAPTER_YAML' if name == 'prologue'
             else '%s_CHAPTER_YAML' % name.upper())
    filename = injector_constants(r'^(PROLOGUE|CH\d+)_CHAPTER_YAML$').get(const)
    if filename is None:
        sys.exit('ERROR: hosted chapter %s has no %s -- declare it next to its '
                 '%s_HOST_INDEX' % (name, const, name.upper()))
    return filename


def _retarget_host_chapter(host_index, goal_slot, goal_type, goal_err, indices,
                           chapter_number, event_group, goal_text_ids):
    """Point host chapter slot `host_index` (chapter_settings.json) at a registered
    map (`indices` from _register_chapter_map) and copy vanilla slot `goal_slot`'s
    goal template (checked against windowDataType `goal_type`, else sys.exit(goal_err)).
    The prep-screen header reads "Chapter NN" from prepScreenNumber, not the slot
    index. It is a double-wide glyph index: vanilla slots carry exactly 2 * chapter
    number (slot1=2, slot2=4, ... both ch5 and ch5x = 10). Returns the host dict.

    `event_group` is the ChapterEventGroup SYMBOL the caller's injector fills, and it is
    mandatory because the slot's own mapEventDataId cannot be trusted to name it: FE8
    inserts chapter 5X at slot 5, so from there on the slot index stops tracking the
    chapter number (slot 5 -> Ch5XEvents, while ch04's events live in Ch5EventData).
    Retargeting only the map ids is enough to make the chapter LOOK right, so a wrong
    event group fails silently and totally -- the slot presents our map while running the
    host slot's roster and scripts. Repointing it here keeps map and events one decision.

    `goal_text_ids` = (windowTextId, statusObjectiveTextId) the chapter OWNS. They override the
    donor's, which are shared across vanilla slots and were being inherited (#207)."""
    obj_idx, pal_idx, cfg_idx, layout_idx = indices
    with open(CHAPTER_SETTINGS_JSON, encoding='utf-8') as f:
        settings = json.load(f)
    host = settings['chapters'][host_index]
    goal = settings['chapters'][goal_slot]['goal']
    if goal.get('windowDataType') != goal_type:
        sys.exit(goal_err)
    host['map'].update({'obj1Id': obj_idx, 'obj2Id': 0, 'paletteId': pal_idx,
                        'tileConfigId': cfg_idx, 'mainLayerId': layout_idx,
                        'objAnimId': 0, 'paletteAnimId': 0, 'changeLayerId': 0})
    host['mapEventDataId'] = _asm_table_word_index(
        ASSET_TABLE_S, 'gChapterDataAssetTable', event_group)
    host['goal'] = dict(goal)
    # The donor's goal carries the donor's TEXT ids, and vanilla points many slots at one string
    # -- so copying it wholesale makes two hosted chapters write over each other's objective
    # (#207). ch04's donor is even ch02's own host slot. The caller declares its pair and it wins
    # here, alongside the map and event ids, so all three stay ONE decision.
    host['goal']['windowTextId'], host['goal']['statusObjectiveTextId'] = goal_text_ids
    host['prepScreenNumber'] = chapter_number * 2
    # fadeToBlack=1: the chapter INTRO ends on BLACK instead of fading the battle map in
    # (ChapterIntro_LoopFadeToMap, chapterintrofx.c:916 -- fadeToBlack takes the SetDispEnable
    # black branch, else it blends the map in). Our openings are BG cutscenes (the BeginningScene
    # BACGs), so the vanilla map fade-in just FLASHES the map for a beat before the BACG. This is
    # the vanilla mechanism for cutscene-opening chapters (slots 2/3 already ship with it; slot 4
    # did not -> ch03's opening map flash). Set for every hosted chapter so none flash.
    host['fadeToBlack'] = 1
    with open(CHAPTER_SETTINGS_JSON, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)
    return host


def recruit_chapter_number(campaign, unit):
    """The chapter_number a cast member is RECRUITED in, or None for the founding party.
    Data-driven from the unit YAML `recruit.chapter` (a chapter id) -> that chapter's
    `chapter_number`. The reusable recruit infra keys prep-availability off this: a unit
    is on the field from the chapter AFTER it is recruited (see cast_available_at)."""
    rec = (unit.get('recruit') or {}).get('chapter')
    if not rec:
        return None
    return _load_chapter_yaml(campaign, rec + '.yaml')['chapter_number']
