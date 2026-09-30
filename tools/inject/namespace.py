"""The injector's constants, wherever they live -- the runtime twin of `inject.source`.

Three registries DISCOVER ids from the names of the injector's constants rather than keep a
second list: `messages.injector_message_ids` (every `*_MSG`/`*_MSGS`), `messages.raw_pid_claims`
(every `CHNN_*PID`/`*PIDS`) and `hosting.chapter_yaml_for` (`CHNN_CHAPTER_YAML`). Each used to
scan `globals()`, which was the whole injector while it was one file. Split across modules,
`globals()` is one module's -- and a scan that sees less does not fail, it finds fewer ids and
reports nothing wrong (ADR 0296's vacuous pass, by code movement; `inject.source` is the same
fix for the guards that read SOURCE).

So the scan is over every module of the injector at once. A name two modules bind to
DIFFERENT values raises: an import binds the same object, so a difference is two definitions,
and which one a registry saw would depend on module order.

A TEST that stubs one of these has the same problem from the other side: while the injector
was one module, `bc.REPO = tmp` reached every function; split, `from inject.decomp import
REPO` gives each importer its own binding, and patching one of them leaves the code under
test reading the real path -- a stub that silently stubs nothing. `stubbed` rebinds a name
in every module that holds it.
"""
import contextlib
import importlib
import pkgutil
import re

import inject


def injector_modules():
    """Every module under `tools/inject/`, imported, in name order.

    Not `build_campaign`: it holds the CLI and nothing a registry reads, and it runs as
    `__main__`, so importing it by name would load a second copy of the orchestrator."""
    names = sorted(info.name for info in pkgutil.walk_packages(inject.__path__, 'inject.'))
    return [importlib.import_module(name) for name in names]


def injector_constants(pattern):
    """{name: value} for every module-level name matching `pattern`, across the injector."""
    match = re.compile(pattern).search
    found, where = {}, {}
    for module in injector_modules():
        for name, value in vars(module).items():
            if not match(name):
                continue
            if name in found and found[name] is not value and found[name] != value:
                raise ValueError('%s is bound to different values in %s and %s -- two '
                                 'definitions, and a registry would see whichever sorted first'
                                 % (name, where[name], module.__name__))
            found.setdefault(name, value)
            where.setdefault(name, module.__name__)
    return found


@contextlib.contextmanager
def stubbed(name, value):
    """Rebind `name` to `value` in every injector module that binds it, then restore it.

    What `bc.NAME = value` did while the injector was one namespace. Raises KeyError when no
    module binds the name, so a stub of a renamed or deleted name fails instead of passing."""
    real = injector_constants('^%s$' % re.escape(name)).get(name)
    holders = [m for m in injector_modules() if name in vars(m) and vars(m)[name] is real]
    if not holders:
        raise KeyError('no injector module binds %s' % name)
    for module in holders:
        setattr(module, name, value)
    try:
        yield value
    finally:
        for module in holders:
            setattr(module, name, real)
