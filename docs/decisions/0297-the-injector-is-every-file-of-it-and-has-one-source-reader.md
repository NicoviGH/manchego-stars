---
id: 297
title: "The injector is every file of it, and it has ONE source reader"
date: "2026-09-30"
section: "Operational Gotchas (durable)"
issues: [389]
---

# The injector is every file of it, and it has ONE source reader

#389 moves code out of `build_campaign.py` into `tools/inject/`. Before the first move,
the census found **~60 sites that read the injector as TEXT** rather than importing it:
21 in `check.py` (the lean `checks` CI job has no Pillow, so it cannot import
build_campaign), 15 in `test_build_campaign.py`, the host-slot and message-literal scans
in `inject/hosts.py`, `map_donor`'s layout labels, and the shape tests around them. Every
one opened `tools/build_campaign.py` by path.

A reader of the old path does not FAIL when its target moves. It goes quiet: a `NotIn`
has nothing left to object to, discovery finds one chapter fewer, a literal scan finds
nothing and reports nothing wrong. That is ADR 0296's vacuous pass, arriving by code
movement instead of by a bad key -- and #389 is nothing but code movement.

## The rule

The injector is `build_campaign.py` plus every module under `tools/inject/`, and it is
read through `tools/inject/source.py` (stdlib-only, so CI can import it). Three views,
because the readers want three different things:

- `injector_source()` -- all files concatenated, for a pattern that names ONE thing
  (`RAW_PID_BATTLE_ANIMS = {`, `engine_hooks.X(`).
- `def_source(name)` -- one top-level definition, wherever it lives, for a reader that
  inspects one function's body. A name defined in two FILES raises: that is a move that
  left a copy behind, and letting whichever sorts first win would be a coin toss.
- `defs_source()` -- every top-level function and nothing between them, for a
  `^def X(.*?(?=^def |\Z)` walk. Over whole files that lookahead runs the last function of
  one module on into the next module's docstring and IMPORTS, and an import line names
  exactly the helpers these guards search for (`_retarget_host_chapter`,
  `_inject_tile_changes`).

`check_injector_source_has_one_reader` holds it: an `open()` or `os.path.join()` with
`build_campaign.py` as a literal argument fails, except in `INJECTOR_PATH_NAMERS`, where a
file that RUNS the injector says so -- and an excuse whose file stopped naming the path
fails too, so a stale one cannot excuse the next reader.

## What else it found

- **`ast.get_source_segment` re-splits the whole file on every call.** Over build_campaign's
  ~400 functions that was 126 seconds for one `defs_source()`. Splitting once per file
  and slicing lines is 7 ms.
- **The message-literal scan binds against the writer where it is DEFINED.** A call site
  in another file has no local `set_message_body` to bind a positional id against, and
  `callsites.scan` without a signature switches positional binding off -- the #341 shape.
  `MessageLiteral` now carries its `path`, so an error names the real file.
- **`test_hosts` swapped module objects under the suite.** It deleted `inject.hosts` from
  `sys.modules` and re-imported it, so any test module that imported `hosts` earlier was
  monkeypatching a copy nothing read any more. It surfaced only when `test_hosts` ran
  before `test_check_message_literals`; the parallel runner's file order hid it. The test
  now puts the same objects back.
- **The post-build `test_difficulty` + `test_map_tileset` failure is gone.** HANDOFF still
  prescribed a `git restore` for it; both tools read vanilla through HEAD
  (`_vanilla_decomp_text`), and the pair passes with both files injected (306 tests,
  measured 2026-09-30).
