#!/usr/bin/env python3
"""Reading the chapter YAML, once, for everything that derives from it.

`docs/CHAPTERS.md` and `make chapter chNN` answer different questions off the SAME facts, and
two readers is two chances to disagree about what a chapter says. This module is the reader;
the label vocabulary that turns a YAML token into prose lives here too, for the same reason.

Stdlib + pyyaml only, so the lightweight CI `checks` job can import it.
"""
import glob
import os
import re

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMPAIGN = 'rime-of-the-frostmaiden'


def chapters_dir(campaign=CAMPAIGN):
    return os.path.join(REPO, 'campaigns', campaign, 'chapters')


def paths(campaign=CAMPAIGN):
    return sorted(glob.glob(os.path.join(chapters_dir(campaign), 'ch*.yaml')))


def short_id(chapter):
    """`ch05-the-elven-tomb` -> `ch05`. The name every tool here takes on the command line."""
    return str(chapter['id']).split('-')[0]


_CACHE = {}


def load_all(campaign=CAMPAIGN):
    """Every chapter, in chapter-number order.

    Cached on each file's identity AND its mtime/size, the way `_load_chapter_yaml` is: a
    report asks for the same nine documents from half a dozen angles, and editing a chapter
    mid-session still has to be picked up.
    """
    key = tuple((p, os.stat(p).st_mtime_ns, os.stat(p).st_size) for p in paths(campaign))
    if key not in _CACHE:
        out = [yaml.safe_load(open(p, encoding='utf-8')) for p in paths(campaign)]
        out.sort(key=lambda c: int(c['chapter_number']))
        _CACHE.clear()             # one campaign at a time; never grow without bound
        _CACHE[key] = out
    return _CACHE[key]


def load(name, campaign=CAMPAIGN):
    """One chapter by short id (`ch05`), by full id, or by number."""
    want = str(name).strip()
    everything = load_all(campaign)
    for chapter in everything:
        if want in (short_id(chapter), str(chapter['id']), str(chapter['chapter_number'])):
            return chapter
    raise KeyError('no chapter %r -- have: %s'
                   % (name, ', '.join(short_id(c) for c in everything)))


def squish(s):
    return re.sub(r'\s+', ' ', str(s if s is not None else '')).strip()
