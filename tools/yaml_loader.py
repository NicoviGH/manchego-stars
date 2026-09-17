#!/usr/bin/env python3
"""One YAML reader, through libyaml's C scanner where it is built in.

PyYAML's pure-Python scanner walks a document one character at a time through a chain of
Python calls. That made YAML parsing ~22s of a 51s injection (6M `reader.forward` calls)
for a few hundred KB of campaign data, and the injector grew a private `_yaml_load` to fix
it. Being private is exactly why the lesson did not travel: `difficulty.py` reached past it
to `bc.yaml.safe_load` -- the raw module, the slow scanner -- and paid 25s of
`test_difficulty.py`'s 151s across 400 loads (#380).

So the loader lives here, in ONE place, and every reader imports it. libyaml produces
identical documents to the Python scanner; where it is not built in we fall back, so this
is a speed decision and never a parse-semantics one.

Stdlib + pyyaml only, so the lightweight CI `checks` job (no Pillow, no submodule) can
import it alongside `campaign_chapters`.
"""
import yaml

# CSafeLoader exists only when PyYAML was built against libyaml.
LOADER = getattr(yaml, 'CSafeLoader', yaml.SafeLoader)

#: True when the C scanner is actually in use -- worth asserting in a perf test, and worth
#: printing when someone wonders why a build is slow on a fresh machine.
USING_LIBYAML = LOADER is not yaml.SafeLoader


def yaml_load(stream):
    """`yaml.safe_load`, through libyaml's C scanner when it is available."""
    return yaml.load(stream, Loader=LOADER)
