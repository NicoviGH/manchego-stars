---
id: 291
title: "A guard that SKIPS declares who covers it, and the declaration is checked"
date: "2026-09-17"
section: "Working Conventions (Definition of Done)"
issues: [379]
---

# A guard that SKIPS declares who covers it, and the declaration is checked

Four guards in `tools/check.py` cannot run on the CI job that runs `tools/check.py`. The
`checks` job installs pyyaml, checks out no submodule, and these four import `build_campaign`,
`difficulty`, `map_placement_preview` or `chapter_status`. Each printed a sentence and returned:

```
check_documented_tileset: skipping (No module named 'PIL'; the `tests` job's `make test` covers it)
```

The sentence was true when it was written. **Nothing held it there**, and a sentence is not a
gate: fixture-ify or delete the test it refers to and the guard covers nothing on either job,
while `check.py` keeps printing the reassurance. This repo has already shipped that exact shape
— `check_tile_changes_outlive_the_retarget` ran only through its own test file's subprocess,
which no-ops when `fireemblem8u/src` is absent, i.e. precisely on the lightweight job it existed
to protect.

## The claim is a table, and the tie is the call

`SKIP_COVERAGE` maps guard → (test file, test name), `_skip_covered_elsewhere` is the only thing
that prints the claim, and `check_skip_claims_name_a_live_test` holds all of it: the file exists,
`run_tests.py` collects it, the test is defined, and **its body calls the guard**.

That last condition is the one that matters. Existence alone would survive the failure being
guarded against — a test can keep its name, keep passing, and stop exercising the gate. Requiring
the call means renaming it, deleting it, repointing it or fixture-ifying it **fails the build**
rather than the coverage. The gate's own tests prove it fails on each of those, because a gate
that only ever passes is the thing being fixed here, not something to reproduce.

The printed message now names the covering test, so a reader of a CI log can go and read the
coverage instead of being told it exists.

## The skip PATH had the same bug in four copies

`except ImportError` was too narrow. `map_placement_preview` opens the decomp's `terrains.h` at
**module scope**, so with no submodule the import raises `FileNotFoundError` — #373's review
caught exactly this in another guard, where it would have reddened every PR on the one job it
was written to protect. All four guards carried those same three lines and **no test exercised
any of them**: they only ever ran on a machine where the import succeeds.

`SKIP_IMPORT_ERRORS = (ImportError, OSError)` now, and the skip paths are driven with the module
genuinely unimportable — a `meta_path` finder whose `find_spec` raises. Two details that decide
whether that test is worth anything:

- it asserts **what was printed**, not just that `fail` is empty. `fail == []` passes just as
  happily when the import succeeded and the guard ran clean, which would prove nothing;
- it uses `find_spec`, not the legacy `find_module`/`load_module` pair, which is gone in 3.12 and
  would have made the test rot silently.

Verified by regression: restoring the narrow `(ImportError,)` clause fails two of them.

## Why machine-check the claim rather than stop skipping

#379 offered both, and "stop skipping" — read from source the way `map_donor` and
`check_map_sidecar_routes_agree` do — is strictly better **where it is affordable**. It is not
uniformly affordable: `check_rescue_targets` needs real terrain, and rewriting the other three
to parse what they currently import is a real change to what each gate reads, with its own risk.

The declaration covers all four at once, costs nothing per guard, and makes the failure mode
loud. Converting individual guards to stdlib-only stays worth doing and is now strictly an
optimisation — when one converts, its entry simply leaves the table.
