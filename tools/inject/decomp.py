"""Shared decomp source-access layer: paths + brace-patch primitives.

Imported by BOTH tools/build_campaign.py (content) and
tools/inject/engine_hooks.py (pipeline). Keep it dependency-free so neither
side creates an import cycle. See docs/decisions.md -> Engine/content file seam.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DECOMP = os.path.join(REPO, 'fireemblem8u')

# Decomp source files patched by hooks that BOTH tracks touch (content injects
# lord quotes / map sprites into these; engine_hooks patches lord-select into them).
BATTLEQUOTES_C = os.path.join(DECOMP, 'src', 'data_battlequotes.c')
BMUNIT_C = os.path.join(DECOMP, 'src', 'bmunit.c')
LORDSEL_FLAG_BASE = 0xF0


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


def _replace_brace_block(text, marker, new_body, path):
    """Replace the `{...}` after `marker` with `new_body` (a `{...}` string)."""
    s, e = _find_brace_block(text, marker, path)
    return text[:s] + new_body + text[e:]
