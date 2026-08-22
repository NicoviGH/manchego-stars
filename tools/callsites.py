#!/usr/bin/env python3
"""Every call site of a function, with arguments BOUND to parameter names (#300).

**The query grep cannot answer.** Text search sees a definition, a keyword argument and a
positional argument as the same string, so "where is this called, and with what" degrades into
"which lines mention this word". Six greps in one session (2026-08-21) answered questions they
could not answer and three shipped bugs the whole unit suite passed through -- most sharply
`_ch05_opening_body(..., fid, 29)`, where a width passed POSITIONALLY made every search for
`width=` walk past it and ch05's moose scene re-wrapped to seven characters a line.

An LSP answers this only obliquely: find-references hands back locations and you still infer
the binding by reading each one. This prints the binding.

    python3 tools/callsites.py tools/build_campaign.py _wrap_fe_lines
    python3 tools/callsites.py 'tools/*.py' _script_to_message _wrap_fe_lines

USE IT BEFORE any change to a function's SIGNATURE or to what a parameter MEANS -- the second is
the dangerous one, because the call sites still compile and the tests still pass. See
`check.py check_wrap_widths_are_pixels` for the guard that then keeps the change honest.
"""
import argparse
import ast
import dataclasses
import glob
import sys


class ParseError(Exception):
    """A file that will not parse, named so the caller knows which one."""


@dataclasses.dataclass
class Site:
    kind: str                 # 'def' or 'call'
    path: str
    lineno: int
    params: list              # def: its parameter names, in order
    bound: dict               # call: parameter name -> argument source text
    positional: set           # call: which of those were passed POSITIONALLY


def _params_of(node):
    a = node.args
    return [p.arg for p in list(getattr(a, 'posonlyargs', [])) + list(a.args)]


def signature(source, target, path='<source>'):
    """`target`'s parameter names as DEFINED in `source`, or [] if it is not defined there."""
    try:
        tree = ast.parse(source, path)
    except SyntaxError as exc:
        raise ParseError('%s: %s' % (path, exc))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == target:
            return _params_of(node)
    return []


def scan(source, target, path, params=None):
    """Every definition and call of `target` in `source`, in line order.

    `params` supplies the signature from ELSEWHERE, which is what makes cross-file analysis
    honest: a call in another module has no local definition to bind its positional arguments
    against, and guessing `arg0/arg1` there would miss exactly the positional-argument case
    that motivated this tool. Resolve it once with `signature()` against the defining file and
    pass it in."""
    try:
        tree = ast.parse(source, path)
    except SyntaxError as exc:
        raise ParseError('%s: %s' % (path, exc))

    # Bind positional arguments against the definition IN THIS FILE when there is one. A call
    # in another file still reports its keywords; its positionals fall back to arg0/arg1/...
    # rather than being silently attributed to the wrong parameter.
    if params is None:
        params = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == target:
                params = _params_of(node)

    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == target:
            out.append(Site('def', path, node.lineno, _params_of(node), {}, set()))
            continue
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # A module-qualified call (`bc._wrap_fe_lines`) is the same function reached another
        # way; the campaign's own tests reach it exactly like that, and missing them would
        # under-report where the code is actually exercised.
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, 'id', None)
        if name != target:
            continue
        bound, positional = {}, set()
        for i, arg in enumerate(node.args):
            if isinstance(arg, ast.Starred):
                key = '*args'
            else:
                key = params[i] if i < len(params) else 'arg%d' % i
            bound[key] = ast.unparse(arg)
            positional.add(key)
        for kw in node.keywords:
            bound[kw.arg or '**kwargs'] = ast.unparse(kw.value)
        out.append(Site('call', path, node.lineno, [], bound, positional))
    return sorted(out, key=lambda s: (s.lineno, s.kind))


def render(sites):
    lines = []
    for s in sites:
        if s.kind == 'def':
            lines.append('DEF   %s:%d  (%s)' % (s.path, s.lineno, ', '.join(s.params)))
            continue
        args = ['%s=%s%s' % (k, v, ' [POSITIONAL]' if k in s.positional else '')
                for k, v in s.bound.items()]
        lines.append('CALL  %s:%d  %s' % (s.path, s.lineno, ' | '.join(args) or '(no args)'))
    return '\n'.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('path', help='a file or a glob')
    ap.add_argument('targets', nargs='+', help='function name(s)')
    args = ap.parse_args(argv)

    paths = sorted(glob.glob(args.path)) or [args.path]
    found = 0
    for path in paths:
        try:
            source = open(path, encoding='utf-8').read()
        except OSError as exc:
            sys.exit('ERROR: %s' % exc)
        for target in args.targets:
            sites = scan(source, target, path)
            if sites:
                found += len([s for s in sites if s.kind == 'call'])
                print(render(sites))
    print('-- %d call site(s)' % found)
    return 0


if __name__ == '__main__':
    sys.exit(main())
