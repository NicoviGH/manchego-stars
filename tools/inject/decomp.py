"""Shared decomp source-access layer: paths + brace-patch primitives.

Imported by every injector module (tools/inject/*, tools/build_campaign.py). Keep it
dependency-free so it never creates an import cycle. See docs/decisions.md -> Engine/content file seam.
"""

import functools
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# The submodule: vanilla FE8, and nothing writes to it (#408). Read vanilla from its HEAD.
SUBMODULE = os.path.join(REPO, 'fireemblem8u')
# The tree the injector writes and `make` compiles: a git worktree of the submodule at the
# same commit (tools/build_tree.py makes it), so `git status`/`checkout HEAD --` work in it
# exactly as they did in the submodule, and the submodule's own working tree stays clean.
DECOMP = os.path.join(REPO, 'build', 'fireemblem8u')

# Decomp source files patched by hooks that BOTH tracks touch (content injects
# lord quotes / map sprites into these; engine patch 0005 adds lord select to them).
BATTLEQUOTES_C = os.path.join(DECOMP, 'src', 'data_battlequotes.c')
BMUNIT_C = os.path.join(DECOMP, 'src', 'bmunit.c')
LORDSEL_FLAG_BASE = 0xF0
# Engine patch 0015's apply-once flag: beside 0006's 0xFA, past the ten 0xF0 candidates.
FOUNDING_EXP_FLAG = 0xFB


# Vanilla FE8 weapon key -> ITEM_ enum (constants/items.h). The single source mapping a
# campaign weapon (a plain vanilla id, or a flavor name's fe_base) to the decomp item.
# Shared because BOTH sides need it: content (build_campaign) emits enemy/guest loadouts from
# it; pipeline (difficulty) inverts it to resolve vanilla enemies. Lives here so neither side
# has to open the other's file to extend it (the seam: docs/decisions.md).
WEAPON_ITEM_ENUM = {
    'iron-sword': 'ITEM_SWORD_IRON', 'steel-sword': 'ITEM_SWORD_STEEL',
    'rapier': 'ITEM_SWORD_RAPIER', 'iron-lance': 'ITEM_LANCE_IRON',
    'silver-lance': 'ITEM_LANCE_SILVER', 'javelin': 'ITEM_LANCE_JAVELIN',
    'killing-edge': 'ITEM_SWORD_KILLER',
    'iron-axe': 'ITEM_AXE_IRON', 'steel-axe': 'ITEM_AXE_STEEL',
    'hand-axe': 'ITEM_AXE_HANDAXE',
    'iron-bow': 'ITEM_BOW_IRON', 'fire': 'ITEM_ANIMA_FIRE', 'flux': 'ITEM_DARK_FLUX',
}


def fe_item_enum(inv_entry):
    """The vanilla ITEM_ enum for a YAML inventory entry -- its fe_base (flavor name over a
    vanilla weapon) if present, else its id (a plain vanilla weapon)."""
    return WEAPON_ITEM_ENUM[inv_entry.get('fe_base') or inv_entry['id']]


def _find_brace_block(text, marker, path):
    """Return (start, end) covering the `{...}` (brace-balanced) after `marker`."""
    at = text.find(marker)
    if at < 0:
        sys.exit('ERROR: %r not found in %s' % (marker, path))
    brace = text.find('{', at)
    depth = 0
    i = brace
    while i < len(text):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return brace, i + 1
        i += 1
    sys.exit('ERROR: unbalanced braces for %r in %s' % (marker, path))


# Validators run on every EVENT SCENE body written through `_replace_brace_block`, which is
# the one place any injector writes one. Registered from outside (inject/scene_actors.py appends
# the #337 cutscene-actor check at import) so this module keeps importing nothing of its own --
# a scene check needs the campaign's cast, and this layer must stay dependency-free or every
# extraction of #389 gets an import cycle back (ADR 0287).
#
# A hook rather than a call per injector, for the reason `apply_chapter_fog` is a total pass:
# 79 call sites through here means "somebody forgets to call the guard on the new scene" is a
# question of when, not whether.
SCENE_VALIDATORS = []

# The modules that REGISTER one, loaded by name on first use -- not imported here, which would
# pull the cast (and Pillow) into this layer. Importing build_campaign used to register the
# #337 check as a side effect; once the injector split (#389), a caller that imported only a
# chapter module wrote its scenes with no check at all. Loading on use makes "every scene is
# checked" independent of who imported what.
SCENE_VALIDATOR_MODULES = ('inject.scene_actors',)


def scene_validators():
    """Every registered scene validator, with the modules that register them loaded first."""
    import importlib
    for name in SCENE_VALIDATOR_MODULES:
        importlib.import_module(name)
    return SCENE_VALIDATORS


def _replace_brace_block(text, marker, new_body, path):
    """Replace the `{...}` after `marker` with `new_body` (a `{...}` string)."""
    if marker.startswith('EventScr_'):
        for validate in scene_validators():
            validate(new_body, marker.split('[')[0])
    s, e = _find_brace_block(text, marker, path)
    return text[:s] + new_body + text[e:]


def git_env():
    """os.environ minus every inherited GIT_* that would override `git -C DECOMP` discovery.

    Git EXPORTS GIT_DIR/GIT_INDEX_FILE/... to a hook, and an explicit GIT_DIR beats `-C`. So
    inside a pre-commit hook every `git -C fireemblem8u show HEAD:...` resolves against the
    SUPERPROJECT and exits 128. `vanilla_decomp_text` learned this once and stripped the env
    inline; the lesson did not propagate, and `chapter_label_constants` -- the same call,
    without the strip -- made the hook unpassable from a worktree (12 test errors, #353).
    One helper, so the next `git -C DECOMP` cannot get it wrong; check.py pins every call site.
    """
    return {k: v for k, v in os.environ.items()
            if k not in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_PREFIX',
                         'GIT_COMMON_DIR', 'GIT_OBJECT_DIRECTORY', 'GIT_NAMESPACE',
                         'GIT_ALTERNATE_OBJECT_DIRECTORIES')}


# Bounded, not unbounded: today's readers touch ~9-22 files (~2-5 MB), but #365 proposes a
# ROMChapterData census, and a census is exactly the caller that walks a big slice of a
# 6,361-file decomp. 64 entries covers every real working set with room to spare and
# caps what a future sweep can pin in memory.
@functools.lru_cache(maxsize=64)
def vanilla_decomp_text(relpath):
    """Committed (HEAD) text of a decomp source file -- immune to the working-tree patching
    the build applies to PATCHED_DECOMP_FILES (e.g. data_characters.c portrait slots get
    overwritten, data_classes.c gets enemy-class clones). Anything that wants the *vanilla*
    value (donor stats, class bases, the difficulty engine) must read through here, not the
    mutable working tree. relpath is under fireemblem8u/, e.g. 'src/data_characters.c'.

    MEMOISED, because HEAD does not move inside a process and this is the hottest read in
    the repo: one `difficulty.curve_report` made 148 calls against 9 unique files -- 199 MB
    of subprocess I/O for 2.1 MB of content, `src/events_udefs.c` (1.78 MB) 114 times over.
    That was ~50s of `test_difficulty.py`'s 151s, and the reason a commit took 6-10 minutes
    with the CPU near idle (the pre-commit hook runs every test file). Returning the SAME
    str object also makes `difficulty.vanilla_redas`'s memo O(1) to key. A process that
    genuinely needs to re-read after HEAD moves calls `vanilla_decomp_text.cache_clear()`;
    nothing in-tree does, because nothing moves HEAD mid-run (#380)."""
    # Strip inherited git env so `git -C DECOMP` discovers the submodule's own gitdir.
    # Git sets GIT_DIR (etc.) when this runs inside a commit hook, and an explicit
    # GIT_DIR overrides the -C discovery -- so `show HEAD:...` resolves against the
    # superproject and fails (128). Bit us committing from a content/pipeline worktree,
    # whose submodule gitdir is separate from the superproject's.
    env = git_env()
    return subprocess.check_output(['git', '-C', SUBMODULE, 'show', 'HEAD:' + relpath],
                                   encoding='utf-8', env=env)


def _table_close_line(lines, decl):
    """(decl line index, closing `};` line index) for a C array `decl`."""
    di = next((i for i, ln in enumerate(lines) if decl in ln), None)
    if di is None:
        sys.exit('ERROR: %r not found' % decl)
    ci = next((i for i in range(di + 1, len(lines)) if lines[i].strip() == '};'), None)
    if ci is None:
        sys.exit('ERROR: close of %r not found' % decl)
    return di, ci
