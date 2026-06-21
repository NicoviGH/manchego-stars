#!/bin/bash
# SessionStart hook: inject the issue-reconciliation reflex into every session.
#
# WHY: the Definition of Done's only issue-closing lever is a manual `Closes #N`
# in a commit (docs/decisions.md -> Working Conventions), and GitHub issue state
# lives outside the repo, so check.py / make can never catch "work shipped but
# issue still open" -- the gap that left #20 (Prologue) open for eleven days
# after it was done. This hook makes reconciliation a standing session-open step.
#
# The reminder below is the real backstop -- it works everywhere, including
# Claude Code on the web where `gh` is absent. When `gh` IS available (local),
# tools/issue_reconcile.py appends the concrete shipped-but-open candidates.
#
# Synchronous, idempotent, non-interactive: it only prints context, never
# mutates the repo. Stdout becomes session context.
set -euo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"

cat <<'EOF'
[issue-reconciliation] Before starting new work this session, reconcile open
tracking issues against shipped state so done work doesn't sit open (the #20
Prologue gap). For each open chapter/feature issue, check: is its YAML
status/dialogue locked, did its host/inject or feature actually land, and did
any commit say `Closes #N`? If it's shipped but open, close it (or say why it
stays open). Closing tracked work in the same commit via `Closes #N` is the
Definition of Done (docs/decisions.md -> Working Conventions).
EOF

# Best-effort concrete candidates -- silent when clean or when gh is absent.
if [ -f "$ROOT/tools/issue_reconcile.py" ]; then
  python3 "$ROOT/tools/issue_reconcile.py" --session-start 2>/dev/null || true
fi
