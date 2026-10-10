"""The campaign-agnostic engine changes: a patch series applied onto the build tree (#410).

`engine/patches/NNNN-*.patch` holds one change each, in `git format-patch` shape: the message
says what the change is for and the diff is plain C against the vanilla decomp. They are
applied in order with one `git apply`, which applies all of them or none and fails loudly
when one no longer matches -- the guard each Python string patch used to carry by hand.

They are exactly the commits a fork of the decomp would hold: `git am engine/patches/*.patch`
on a branch of the submodule reproduces them. The submodule itself stays vanilla (ADR 0302).

To change one: apply the series to a clean build tree up to it, edit the files, and write
`git diff` over its files back into the patch below its message (`git apply --check` on a
clean tree proves the series still applies). Engine code here must stay campaign-agnostic:
campaign data reaches it through tables the injector writes, never through the patch.
"""
import functools
import glob
import os
import re
import subprocess
import sys
import tempfile

from inject.decomp import DECOMP, git_env, REPO

PATCHES_DIR = os.path.join(REPO, 'engine', 'patches')
# Applied by the step that supplies what they link against, and only when it does: the crit
# flourish's patch names the d20 art's symbols, which a campaign without the art never defines.
OPTIONAL_DIR = os.path.join(PATCHES_DIR, 'optional')


def patches():
    """The series, in the order it applies."""
    return sorted(glob.glob(os.path.join(PATCHES_DIR, '[0-9][0-9][0-9][0-9]-*.patch')))


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def subject(path):
    m = re.search(r'^Subject: \[PATCH[^\]]*\] (.*)$', _read(path), re.M)
    return m.group(1) if m else os.path.basename(path)


def patched_files(paths=None):
    """Every decomp path the series changes, relative to the tree."""
    files = []
    for path in paths if paths is not None else patches():
        for rel in re.findall(r'^diff --git a/(\S+) b/', _read(path), re.M):
            if rel not in files:
                files.append(rel)
    return tuple(files)


def apply_optional(name):
    """Apply one optional patch (`engine/patches/optional/<name>.patch`), unless the tree
    already carries it."""
    path = os.path.join(OPTIONAL_DIR, name + '.patch')
    applied = subprocess.run(['git', '-C', DECOMP, 'apply', '--check', '-R', path],
                             env=git_env(), capture_output=True)
    if applied.returncode == 0:
        return
    run = subprocess.run(['git', '-C', DECOMP, 'apply', '--whitespace=nowarn', path],
                         env=git_env(), capture_output=True, text=True)
    if run.returncode:
        sys.exit('ERROR: engine patch %s does not apply to %s (#410):\n%s'
                 % (name, DECOMP, run.stderr.strip()))


def apply_sound_room_audition():
    """DEBUG build (SOUNDROOM=1): the Sound Room lists every song, so a chapter's music can be
    chosen by ear in plain mGBA on a fresh ROM (the harness buzzes under audio sync)."""
    apply_optional('sound-room-audition')
    print('  sound room: every song listed (audition build -- never ship this ROM)')


def apply_engine_patches(verbose=True):
    """Apply the series onto the (restored, vanilla) build tree."""
    series = patches()
    if not series:
        sys.exit('ERROR: no engine patches in %s' % PATCHES_DIR)
    run = subprocess.run(['git', '-C', DECOMP, 'apply', '--whitespace=nowarn'] + series,
                         env=git_env(), capture_output=True, text=True)
    if run.returncode:
        sys.exit('ERROR: the engine patches do not apply to %s -- a decomp bump moved the '
                 'code one of them edits, or a restore missed a file (#410):\n%s'
                 % (DECOMP, run.stderr.strip()))
    if verbose:
        for path in series:
            print('  ' + subject(path))
    return series


def patched_text(rel, optional=()):
    """`rel` as the series leaves it on vanilla -- for tests and readers that need the patched
    engine without a build tree. Applied in a scratch directory to the submodule's text."""
    return _patched(tuple(optional))[rel]


@functools.lru_cache(maxsize=None)
def _patched(optional):
    from inject.decomp import vanilla_decomp_text
    series = patches() + [os.path.join(OPTIONAL_DIR, name + '.patch') for name in optional]
    with tempfile.TemporaryDirectory() as tmp:
        files = patched_files(series)
        for rel in files:
            os.makedirs(os.path.dirname(os.path.join(tmp, rel)), exist_ok=True)
            with open(os.path.join(tmp, rel), 'w', encoding='utf-8') as fh:
                fh.write(vanilla_decomp_text(rel))
        subprocess.run(['git', 'apply', '--whitespace=nowarn'] + series, cwd=tmp,
                       env=git_env(), check=True, capture_output=True)
        out = {}
        for rel in files:
            with open(os.path.join(tmp, rel), encoding='utf-8') as fh:
                out[rel] = fh.read()
        return out


def vanilla_banim_count():
    """banim_data[] rows in vanilla = the id of the first custom (appended) banim. Patches 0008
    and 0009 carry it as a literal threshold; a decomp bump that moves it must move them."""
    from inject.decomp import vanilla_decomp_text
    return sum(1 for ln in vanilla_decomp_text('src/banim_data.c').splitlines()
               if ln.lstrip().startswith('{"'))
