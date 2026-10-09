#!/usr/bin/env python3
"""The chapter YAML's schema: every key a chapter may write, checked when the file is loaded.

A typo'd key was found at injection or in a watched playtest, and mostly not at all: every reader
does `chap.get('key')`, so `enemy_unit: [...]` or `win_conditon:` is a chapter that silently has
none. This names the keys each object may hold and refuses the rest, from the first second.

What it checks: the KEYS of every mapping the schema describes, and whether a value is a mapping,
a list or a leaf where the schema says so. What it leaves alone: prose and the subtrees other
gates own. A scene's `script:` is the scene preview's (`make scene`), deployment's numbers are
`check_chapter_deployment_schema`'s, and a leaf's TYPE is the reader's -- this answers "does this
key exist", which no reader can.

Stdlib only, operating on parsed documents, so the CI `checks` job runs it beside `campaign_chapters`.
"""
import os
import sys

# A spec is one of:
#   ANY          -- anything at all (prose, or a subtree another gate owns)
#   {key: spec}  -- a mapping that may hold exactly these keys
#   [spec]       -- a list whose items each match spec
#   Keyed(spec)  -- a mapping with free keys (unit ids, class names), each value matching spec
ANY = object()


class Keyed(object):
    def __init__(self, spec):
        self.spec = spec


ART = {'portrait': ANY, 'source': ANY, 'hand_pass': ANY, 'palette': ANY, 'vendored': ANY,
       'map_sprite': {'mu': ANY, 'wait': ANY},
       'render': {'bg_thresh': ANY, 'crop': ANY, 'hand_pass': ANY, 'ref': ANY, 'zoom': ANY}}
REWARD = [{'id': ANY, 'amount': ANY}]

# One shape for every unit a chapter places, whatever roster key holds it: the readers treat
# them interchangeably (`raw_pids.PLACED_ROSTER_KEYS`, `check.ROSTER_KEYS`, map_placement_preview,
# difficulty), so a field legal on an enemy is legal on a reinforcement, a guest or an ally.
UNIT = {
    'id': ANY, 'name': ANY, 'fe_name': ANY, 'class': ANY, 'deploy_class': ANY, 'level': ANY,
    'levels': ANY, 'autolevel': ANY, 'count': ANY, 'composition': ANY,
    'position': ANY, 'positions': ANY, 'boss_tile': ANY, 'camera_at': ANY,
    'is_boss': ANY, 'is_miniboss': ANY, 'hard_mode_only': ANY, 'required': ANY, 'is_npc': ANY,
    'convertible': ANY, 'inventory': ANY, 'inventory_by_class': Keyed(ANY), 'weapon': ANY,
    'item_drop': ANY, 'gift': ANY, 'damage_type': ANY, 'personal': ANY, 'donor': ANY, 'twin': ANY,
    'ai_pattern': ANY, 'ai_override': {'ai': ANY, 'why': ANY}, 'behavior': ANY,
    'arrives': {'turn': ANY}, 'arrives_turn': ANY, 'spawn_edge': ANY, 'spawn_turn': ANY,
    'trigger_turn': ANY, 'charge_from': ANY, 'charge_route': ANY, 'walks_to': ANY,
    'flee_route': ANY, 'flees_to': ANY,
    'death_quote': ANY, 'defeat_quote': ANY, 'taunt': ANY, 'flavor': ANY, 'flavor_traits': ANY,
    'fe_mechanic': ANY, 'note': ANY,
    'parley': {'by': ANY, 'recruits_npc': ANY, 'result': ANY},
    'skin': {'fallback': ANY, 'look': ANY, 'source': ANY},
    'art': ART,
    'map_sprite': {'base': ANY, 'credit': ANY, 'palette': ANY, 'recipe': ANY, 'source': ANY},
    'battle_anim': {'abbr': ANY, 'clone_from': ANY, 'frames': ANY,
                    'import': {'frames_dir': ANY, 'palette_edit': ANY, 'txt': ANY,
                               'vendored': ANY}},
}

# A scene's fallback cut: its `script:` is the scene preview's to read.
SCENE_VARIANT = {'boxes': ANY, 'reason': ANY, 'replaces': ANY, 'script': ANY}

EVENT = {
    'type': ANY, 'trigger': ANY, 'turn': ANY, 'slot': ANY, 'status': ANY, 'description': ANY,
    'unit': ANY, 'target': ANY, 'tile': ANY, 'zone': ANY, 'recruits': ANY, 'ea_file': ANY,
    'script': ANY, 'flash_tiles': ANY, 'no_lupin_fallback': SCENE_VARIANT, 'no_sahnar_cut': SCENE_VARIANT,
}

# What a playtest case declares (tools/playtest/declared.py reads it).
PLAYTEST_CASE = {
    'name': ANY, 'kind': ANY, 'boot': ANY, 'checkpoint': ANY, 'deadline': ANY, 'headless': ANY,
    'lua': ANY, 'proves': ANY, 'given': ANY,
    'when': [{'visit': {'x': ANY, 'y': ANY, 'gains': ANY},
              'talk': {'x': ANY, 'y': ANY, 'gains': ANY}}],
    'then': [{'spoke': ANY}],
}

CHAPTER = {
    # identity and status
    'id': ANY, 'chapter_number': ANY, 'title': ANY, 'status': ANY, 'milestone': ANY,
    'is_prologue': ANY, 'is_mvp_finale': ANY, 'balance_locked': ANY, 'accepted_residual': ANY,
    # prose: the design record
    'narrative': ANY, 'design_notes': ANY, 'cadence': ANY, 'parity_reference': ANY,
    'difficulty_note': ANY, 'fe8_base_map': ANY, 'fe8_cadence_base': ANY,
    'forest_composition': ANY, 'win_condition': ANY, 'lose_condition': ANY,
    'signature_moments': [{'pc': ANY, 'trigger': ANY}],
    'introduces': [{'concept': ANY, 'coverage': ANY, 'status': ANY, 'where': ANY}],
    'messie': {'appears_in': ANY, 'art': ANY, 'art_note': ANY, 'name': ANY, 'pronouns': ANY, 'role': ANY,
               'surfaces': ANY},
    'soft_penalty_on_chwinga_loss': {'description': ANY},
    'charm_gifts': {'note': ANY},
    # the map
    'map': {'file': ANY, 'size': ANY, 'tileset': ANY, 'base_layout': ANY,
            'vanilla_layout': ANY, 'description': ANY, 'terrain_note': ANY,
            'placement_directives': ANY,
            'terrain_mechanic': {'boat_pockets': ANY, 'channels': ANY, 'crossings': ANY,
                                 'ice_walls': ANY, 'lake_ice': ANY, 'snow_drifts': ANY}},
    'terrain_divergence': [{'tile': ANY, 'from': ANY, 'to': ANY, 'why': ANY}],
    'fog': ANY,
    'traps': [{'type': ANY, 'x': ANY, 'y': ANY, 'item': ANY, 'count': ANY, 'turn': ANY}],
    'doors': [{'position': ANY}],
    'chests': [{'position': ANY, 'contents': [{'id': ANY, 'flavor': ANY}]}],
    'villages': [{'id': ANY, 'tile': ANY, 'note': ANY, 'visit_text': ANY,
                  'visit_reward': REWARD,
                  'inhabitant': {'id': ANY, 'name': ANY, 'fe_name': ANY}}],
    # the objective
    'objective': {'type': ANY, 'description': ANY, 'note': ANY, 'turns': ANY,
                  'seize_by': ANY, 'seize_tile': ANY,
                  'constraint': {'type': ANY, 'description': ANY, 'units': ANY,
                                 'fail_is_soft': ANY},
                  'secondary': [{'type': ANY, 'description': ANY}]},
    'difficulty': {'tutorial': ANY, 'normal': ANY, 'difficult': ANY},
    # the units
    'deployment': {'deploy_limit': ANY, 'deploy_slots': ANY, 'note': ANY, 'prep_screen': ANY,
                   'start_area': ANY, 'green_allies': [UNIT]},
    'player_units': [UNIT],
    'enemy_units': [UNIT],
    'reinforcements': [UNIT],
    'enemy_reinforcements': [UNIT],
    'neutral_units': [UNIT],
    'green_units': [UNIT],
    'npc_units': [{'id': ANY, 'count': ANY, 'behavior': ANY, 'must_not_be_killed': ANY,
                   'penalty_if_killed': {'gold': ANY, 'reputation': ANY}}],
    'rescue_boats': [{'id': ANY, 'fe_name': ANY, 'class': ANY, 'donor': ANY, 'faction': ANY,
                      'size': ANY, 'tile': ANY, 'door': ANY, 'attackable_sides': ANY,
                      'declared_fuse': ANY, 'personal': ANY,
                      'reached_on': Keyed(ANY), 'reached_on_contested': Keyed(ANY),
                      'talk': {'background': ANY, 'face': ANY, 'text': ANY,
                               'reward': REWARD}}],
    'rescue_pursuers': [{'id': ANY}],
    'cutscene_actors': ANY,
    'events': [EVENT],
    'arena_presentation': {'attendant': {'face_slot': ANY, 'portrait': ANY}},
    'available_shops': ANY,      # difficulty.py reads it here as well as under post_chapter
    'economy': {'elven_store': {'armory': ANY, 'vendor': ANY},
                'reward_sites': [{'gift': ANY}],
                'save_all_bonus': ANY, 'save_all_gate': ANY},
    'post_chapter': {'available_shops': ANY, 'ends_mvp': ANY, 'gold_reward': ANY,
                     'net_gold': ANY, 'hooks': ANY, 'unlocks_chapter': ANY,
                     'promotion_seam': {'note': ANY},
                     'caravan_npcs_added': [{'id': ANY, 'description': ANY}],
                     'units_available_to_recruit': [{'id': ANY, 'description': ANY,
                                                     'joins': ANY, 'via': ANY}],
                     'units_recruited_in_chapter': [{'id': ANY, 'where': ANY}]},
    'playtest': {'boot': ANY, 'cases': [PLAYTEST_CASE]},
}


def entry_tiles(enemy_def):
    """The tiles one roster entry places its bodies on, in order: `positions:`, or a lone
    `position:` -- the shape every boss and single unit is written in (ch01's Izobai, ch02's
    captain). Reading `positions` alone dropped those bodies off every board (#430). The
    pairs come back as written, so a shape guard can still see a malformed one."""
    if enemy_def.get('positions'):
        return list(enemy_def['positions'])
    return [enemy_def['position']] if enemy_def.get('position') else []


def _kind(value):
    return ('a mapping' if isinstance(value, dict) else 'a list' if isinstance(value, list)
            else 'a %s' % type(value).__name__)


def violations(rel, doc, spec=CHAPTER, path=''):
    """Every place `doc` strays from `spec`, as '<file>: <path>: <what>' strings. Pure."""
    if spec is ANY or doc is None:
        return []
    out = []
    if isinstance(spec, Keyed):
        if not isinstance(doc, dict):
            return ['%s: %s must be a mapping, not %s' % (rel, path or '<root>', _kind(doc))]
        for key, value in doc.items():
            out += violations(rel, value, spec.spec, '%s.%s' % (path, key))
        return out
    if isinstance(spec, list):
        if not isinstance(doc, list):
            return ['%s: %s must be a list, not %s' % (rel, path or '<root>', _kind(doc))]
        for i, item in enumerate(doc):
            out += violations(rel, item, spec[0], '%s[%d]' % (path, i))
        return out
    if not isinstance(doc, dict):
        return ['%s: %s must be a mapping, not %s' % (rel, path or '<root>', _kind(doc))]
    for key, value in doc.items():
        where = '%s.%s' % (path, key) if path else str(key)
        if key not in spec:
            out.append('%s: %s is not a chapter key%s (tools/chapter_schema.py lists them; add '
                       'it there if it is new)' % (rel, where, _suggest(key, spec)))
            continue
        out += violations(rel, value, spec[key], where)
    return out


def _suggest(key, spec):
    import difflib
    close = difflib.get_close_matches(str(key), [str(k) for k in spec], n=1)
    return ' -- did you mean `%s`?' % close[0] if close else ''


def load(path):
    """Parse the chapter YAML at `path` and validate it. Every reader that parses a chapter
    file itself goes through here, so no path through the tooling skips the schema."""
    from yaml_loader import yaml_load
    with open(path, encoding='utf-8') as f:
        return validate(os.path.basename(path), yaml_load(f))


def validate(rel, doc):
    """Exit naming every violation, or return `doc` unchanged."""
    bad = violations(rel, doc)
    if bad:
        sys.exit('ERROR: chapter YAML does not match its schema:\n  ' + '\n  '.join(bad))
    return doc
