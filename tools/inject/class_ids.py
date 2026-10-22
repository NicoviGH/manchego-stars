"""Which class a chapter's enemy DEPLOYS as -- the one resolver every chapter roster reads.

A chapter YAML names a class by a vanilla token (`armor-knight`), and that token deploys as
its vanilla class (`CLASS_ARMOR_KNIGHT`) unless a campaign reskin claims it FOR THAT CHAPTER:
`campaign.yaml` -> `enemy_class_reskins` -> `dresses: {ch05: [soldier]}` sends every ch05
`soldier` to `CLASS_SOL_SKELEBERDIER`. An entry's `deploy_class` (ch03's `brigand-brute`) is
looked up before its `class`, so a sprite-only override never touches the parity engine.

The key is (chapter, token), never the reskin's `base`. Base is many-to-one by design --
goblin-soldier and risen-spear both clone CLASS_SOLDIER -- and resolving by base is what
shipped ch01's goblins as ch05's skeletons (#347). Each chapter used to restate its claimed
slots in a hand-kept `CHnn_CLASS_IDS` dict, which got the scoping right and drifted from
`campaign.yaml` the moment a reskin was added. Now the reskin says where it is worn, and a
(chapter, token) claimed twice is a build error.

Stdlib + yaml only: `difficulty.py` reads the vanilla rule from here.
"""
import functools
import os
import re

from yaml_loader import yaml_load
from inject.decomp import REPO, enum_values, vanilla_decomp_text

DEFAULT_CAMPAIGN = 'rime-of-the-frostmaiden'


def vanilla_class_enum(token):
    """'armor-knight' -> 'CLASS_ARMOR_KNIGHT' (and 'pegasus_knight' -> 'CLASS_PEGASUS_KNIGHT')."""
    return 'CLASS_' + str(token).upper().replace('-', '_')


# The in-game names title-casing a token gets wrong, from data_classes.c's nameTextId
# (test_class_ids pins every class against the decomp). FE8 truncates two to fit its box
# ("Pegasus Kn.", "Wyvern Kn."); the full names are the ones the Fire Emblem Wiki titles.
_CLASS_NAMES = {'armor-knight': 'Knight', 'falcon-knight': 'Falcoknight',
                'entoumbed': 'Entombed', 'mauthedoog': 'Mauthe Doog', 'gorgonegg': 'Gorgon Egg',
                'gorgonegg2': 'Gorgon Egg', 'eirika-lord': 'Lord', 'ephraim-lord': 'Lord',
                'eirika-master-lord': 'Great Lord', 'ephraim-master-lord': 'Great Lord',
                'manakete-myrrh': 'Manakete'}
_VARIANT = re.compile(r'-(f\d?|m\d|t\d|\d|bow)$')


def class_display_name(token):
    """A class token as FE8 names it: 'armor-knight' -> 'Knight', 'mage-f' -> 'Mage'.
    Decomp-free, so CI's checks job (no submodule) can run the class index with it."""
    if not token:
        return '?'
    t = str(token).lower().replace('_', '-')
    t = _CLASS_NAMES.get(t) or _CLASS_NAMES.get(_VARIANT.sub('', t)) or _VARIANT.sub('', t)
    return t if ' ' in t or t[:1].isupper() else ' '.join(w.capitalize() for w in t.split('-'))


@functools.lru_cache(maxsize=None)
def vanilla_class_values():
    """CLASS_X -> its id, for every vanilla class given a number (HEAD, as above). An alias
    (`CLASS_OBSTACLE = CLASS_EPHRAIM_LORD`) has no number of its own and is left out."""
    return enum_values(vanilla_decomp_text('include/constants/classes.h'), 'CLASS_')


@functools.lru_cache(maxsize=None)
def slayer_classes():
    """The classes `IsUnitEffectiveAgainst` (bmitem.c) makes x3 against the Monsters list. It
    switches on raw class ids (0x2B, 0x2C), named here through include/constants/classes.h."""
    fn = re.search(r's8 IsUnitEffectiveAgainst\(.*?\n\}',
                   vanilla_decomp_text('src/bmitem.c'), re.S).group(0)
    ids = {int(v, 16) for v in re.findall(r'case (0x[0-9A-Fa-f]+):', fn)}
    return frozenset(name for name, v in vanilla_class_values().items()
                     if v in ids)


@functools.lru_cache(maxsize=None)
def vanilla_class_enums():
    """Every enum name in vanilla FE8's class table (HEAD of the submodule, never the patched
    build tree, so a reskin's appended slot can never pass for a vanilla class)."""
    text = vanilla_decomp_text('include/constants/classes.h')
    return frozenset(re.findall(r'^\s*(CLASS_[A-Z0-9_]+)\s*=', text, re.MULTILINE))


@functools.lru_cache(maxsize=None)
def reskin_claims(campaign=DEFAULT_CAMPAIGN):
    """{(chapter, token): slot} over every reskin's `dresses:`. A pair claimed twice exits."""
    path = os.path.join(REPO, 'campaigns', campaign, 'campaign.yaml')
    with open(path, encoding='utf-8') as f:
        reskins = (yaml_load(f) or {}).get('enemy_class_reskins') or []
    claims, owner = {}, {}
    for rk in reskins:
        for chapter, tokens in (rk.get('dresses') or {}).items():
            for token in tokens:
                key = (chapter, token)
                if key in claims:
                    raise SystemExit('ERROR: %s %r is dressed by both %r and %r '
                                     '(campaign.yaml enemy_class_reskins)'
                                     % (chapter, token, owner[key], rk['id']))
                claims[key], owner[key] = rk['slot'], rk['id']
    return claims


class ChapterClassIds:
    """`CHnn_CLASS_IDS[token]` -> the class enum a chapter deploys that token as."""

    def __init__(self, chapter, campaign=DEFAULT_CAMPAIGN):
        self.chapter, self.campaign = chapter, campaign

    def __getitem__(self, token):
        slot = reskin_claims(self.campaign).get((self.chapter, token))
        if slot:
            return slot
        enum = vanilla_class_enum(token)
        if enum not in vanilla_class_enums():
            raise KeyError('%s: class %r is neither a vanilla class (%s) nor dressed by a '
                           'reskin for this chapter' % (self.chapter, token, enum))
        return enum

    def for_entry(self, entry):
        """The class an enemy entry deploys as: its `deploy_class`, else its `class`."""
        return self[entry.get('deploy_class') or entry['class']]
