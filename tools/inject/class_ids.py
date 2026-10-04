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
from inject.decomp import REPO, vanilla_decomp_text

DEFAULT_CAMPAIGN = 'rime-of-the-frostmaiden'


def vanilla_class_enum(token):
    """'armor-knight' -> 'CLASS_ARMOR_KNIGHT' (and 'pegasus_knight' -> 'CLASS_PEGASUS_KNIGHT')."""
    return 'CLASS_' + str(token).upper().replace('-', '_')


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
