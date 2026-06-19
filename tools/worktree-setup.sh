#!/usr/bin/env bash
# Bootstrap a git worktree as an isolated build environment for ONE parallel
# instance (e.g. the content track or the pipeline track). See
# docs/decisions.md §Parallel Work Model.
#
#   tools/worktree-setup.sh <path> [branch]
#
#     <path>    where to create the worktree (e.g. ../ms-content, ../ms-pipeline)
#     [branch]  branch to check out / create there (default: derived from <path>,
#               prefixed inst/). Two worktrees can't share one branch, and the
#               primary checkout holds `main`, so each instance lives on its own
#               short-lived branch and integrates to main frequently (trunk-based).
#
# WHY this script exists: the decomp build mutates the `fireemblem8u` submodule
# working tree, so two instances sharing one checkout would race and corrupt each
# other's build. A separate worktree gives each its OWN submodule working tree +
# index (git 2.x stores it under .git/worktrees/<wt>/modules/, verified isolated).
# But a fresh worktree's submodule is empty AND the build toolchain (agbcc + the
# small native binaries) is gitignored, so it doesn't come with the checkout.
# This script populates the submodule from the LOCAL object store (no re-clone)
# and SYMLINKS the toolchain from the primary checkout -- the compilers are static
# and only ever read during a build, so sharing them is safe and instant (no 9MB
# duplicated per worktree). Isolation is needed for the SOURCE/build tree, not the
# compiler.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

WT_PATH="${1:-}"
[ -n "$WT_PATH" ] || { echo "usage: tools/worktree-setup.sh <path> [branch]" >&2; exit 2; }

BRANCH="${2:-inst/$(basename "$WT_PATH")}"

# These toolchain artifacts are gitignored (built by setup-toolchain.sh) and so
# absent from a fresh submodule checkout. They are static native binaries -- safe
# to symlink and share across worktrees on the same machine.
TOOLCHAIN=(
    tools/agbcc
    tools/aif2pcm/aif2pcm
    tools/bin2c/bin2c
    tools/gbagfx/gbagfx
    tools/jsonproc/jsonproc
    tools/mid2agb/mid2agb
    tools/scaninc/scaninc
    tools/textencode/textencode
    baserom.gba
)

cd "$REPO"

# Sanity: the primary checkout must itself be toolchain-ready (run setup-toolchain.sh once).
if [ ! -x "fireemblem8u/tools/agbcc/bin/agbcc" ]; then
    echo "ERROR: primary checkout has no toolchain (fireemblem8u/tools/agbcc) -- run tools/setup-toolchain.sh first." >&2
    exit 1
fi

# The lane (content|pipeline) the seam guard enforces is derived from the branch name --
# inst/*content* -> content, inst/*pipeline* -> pipeline (tools/check.py _current_lane). A
# worktree off a name with neither is allowed but UN-laned: the guard will then block any
# lane-exclusive file there, so warn loudly.
case "$BRANCH" in
    *content*)  LANE=content ;;
    *pipeline*) LANE=pipeline ;;
    *)          LANE="" ;;
esac
if [ -z "$LANE" ]; then
    echo "WARNING: branch '$BRANCH' maps to no lane -- name it inst/...content/pipeline so the" >&2
    echo "         seam guard can identify this worktree (else lane-exclusive edits are blocked)." >&2
fi

echo ">> creating worktree '$WT_PATH' on branch '$BRANCH'  (lane: ${LANE:-NONE})"
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    git worktree add "$WT_PATH" "$BRANCH"
else
    git worktree add -b "$BRANCH" "$WT_PATH"
fi

# Make the seam guard active in the worktree. The lane is read from the branch name
# (tools/check.py _current_lane), so no per-worktree config is needed. core.hooksPath drives
# the pre-commit hook; it's inherited from the shared config, but set it if unset (relative
# -> resolves to this worktree's tools/hooks).
if [ -z "$(git config core.hooksPath || true)" ]; then
    git config core.hooksPath tools/hooks
    echo "   set core.hooksPath=tools/hooks (was unset) so the pre-commit seam guard runs"
fi

echo ">> initialising the fireemblem8u submodule in the worktree (from local objects)"
( cd "$WT_PATH" && git submodule update --init fireemblem8u )

echo ">> symlinking the build toolchain from the primary checkout (shared, read-only)"
M="$REPO/fireemblem8u"
W="$WT_PATH/fireemblem8u"
for t in "${TOOLCHAIN[@]}"; do
    if [ -e "$M/$t" ]; then
        mkdir -p "$(dirname "$W/$t")"
        ln -sfn "$M/$t" "$W/$t"
        echo "   linked $t"
    else
        echo "   skip (absent in primary): $t"
    fi
done

echo ">> done. Build there with:  ( cd $WT_PATH && tools/build.sh test )"
echo "   (build.sh re-applies the macOS shebang fix idempotently.)"
echo "   Remove when finished with:  git worktree remove $WT_PATH"
