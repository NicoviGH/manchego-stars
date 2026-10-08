"""Campaign-owned event scripts: define an `MS_*` EventListScr in a host chapter's eventscript
header, give it an extern, and prove it survived the injector's block rewrites.

Shared by every hosted chapter (ch05 first, ch06's boarding pass next) -- the script twin of
`inject.units.declare_unit_table`.
"""
import os
import sys

from inject import decomp as _decomp
from inject.paths import EVENTCALL_H
from inject.units import _assert_ms_symbol


def declare_event_script(path, symbol, body, comment):
    """DEFINE a campaign-owned EventListScr in `path` (a chN-eventscript.h), and return its symbol.

    The script twin of declare_unit_table, for the same reason and with the same payoff. A host
    slot frees only the scripts its stripped cutscenes stop referencing -- slot 6 leaves five, and
    ch05 needs three reinforcement waves plus one per village, which is more than it has. Naming
    our own removes the budget entirely, and `MS_Ch05Village2` says what it runs where
    `EventScr_089F2AE4` says nothing at all.
    """
    with open(path, encoding='utf-8') as f:
        script = f.read()
    if ('EventListScr %s[]' % symbol) in script:
        sys.exit('ERROR: event script %s is already defined this build -- two injectors are '
                 'claiming one symbol name' % symbol)
    _assert_ms_symbol(symbol)
    # The campaign's OWN scenes are defined here, not written through `_replace_brace_block`,
    # so the #337 cutscene-actor check has to run on this path too -- it is the path ch05's
    # talks and villages take, and the one ch06's Messie scene will (#337).
    for validate in _decomp.scene_validators():
        validate(body, symbol)
    with open(path, 'a', encoding='utf-8') as f:
        f.write('\n/* %s */\nCONST_DATA EventListScr %s[] = %s;\n' % (comment, symbol, body))
    with open(EVENTCALL_H, encoding='utf-8') as f:
        header = f.read()
    with open(EVENTCALL_H, 'w', encoding='utf-8') as f:
        f.write(event_script_extern(header, symbol, comment))
    return symbol


def assert_event_scripts_defined(path, symbols):
    """Fail the BUILD if a declared event script is missing from `path`.

    `declare_event_script` APPENDS, while the injectors' block-replacements rewrite the same file
    wholesale from a copy read earlier -- so declaring before the bulk write silently discards
    every appended script. The Location list still names them and the externs still exist, so the
    only symptom is a link error pointing at the reference rather than at the loss. Cheap to
    assert, and it pins the ordering against a future reshuffle of the injector.
    """
    with open(path, encoding='utf-8') as f:
        script = f.read()
    missing = [s for s in symbols if ('EventListScr %s[]' % s) not in script]
    if missing:
        sys.exit('ERROR: %s declared but not defined in %s -- declare_event_script APPENDS, so it '
                 'must run AFTER the block-replacement pass rewrites the file, never before'
                 % (', '.join(missing), os.path.basename(path)))


# Anchored on the first EventListScr extern, like the UnitDefinition block above it.
_SCRIPT_EXTERN_ANCHOR = 'extern CONST_DATA EventListScr EventScr_9EEA58[];'


def event_script_extern(header, symbol, comment):
    """Pure: `header` (eventcall.h) with an extern for event script `symbol`. Idempotent.

    The Location list that names these lives in a DIFFERENT file from their definitions, so
    without the declaration agbcc sees an implicit int and the build dies a long way from here.
    """
    _assert_ms_symbol(symbol)
    decl = 'extern CONST_DATA EventListScr %s[];' % symbol
    if decl in header:
        return header
    if _SCRIPT_EXTERN_ANCHOR not in header:
        sys.exit('ERROR: eventcall.h has no EventListScr extern block to extend (looked for %r)'
                 % _SCRIPT_EXTERN_ANCHOR)
    return header.replace(_SCRIPT_EXTERN_ANCHOR,
                          '%s\n%s /* %s */' % (_SCRIPT_EXTERN_ANCHOR, decl, comment), 1)
