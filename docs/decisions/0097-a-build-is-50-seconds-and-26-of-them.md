---
id: 97
title: "A build is 50 seconds, and 26 of them were the same battle anims every time"
date: "2026-08-23"
section: "Distribution & Scope"
issues: [302, 309]
---

# A build is 50 seconds, and 26 of them were the same battle anims every time

#309 was written as *"switch ROM configurations by PATCHING the linked ELF, not by rebuilding"*,
borrowed from pokeemerald-expansion, on the premise that the gate's five builds were half of its
24m51s. The premise was inherited, so it was measured first (`decisions.md` → inherited leads are
hypotheses). On this Mac, `-j8`:

| | injector | `make -C fireemblem8u` | total |
|---|---|---|---|
| same-config rebuild | 35.8s | 23.9s | **59.7s** (ROM byte-identical) |
| config switch → `ch04boot` | 34.9s | 14.1s | **49.0s** |

A config switch recompiles ten `.c` files and relinks — it was already incremental. And
`cProfile` on the injector says where the rest goes: **`inject_enemy_class_battle_anims` 17.1s +
`inject_battle_anims` 8.5s = 26 of the ~35 injector seconds**, with every other step under 1.8s.
Neither can see a boot flag — both are called with `campaign` alone, and both run before the first
flag-dependent step — so all twelve `rom_configs` pay 26 seconds to produce byte-identical anim
data. **ELF patching aims at the 14s; the 26s was the number worth taking.**

**So a step whose inputs have not moved now restores what it wrote** (`tools/inject/step_cache.py`)
— the same bargain the ROM cache and the verdict cache already make one level up, with the STEP as
the unit. A config switch went **49.0s → 25.2s**, and a same-config rebuild 59.7s → 25.5s.

**What makes a restore sound, and what enforces it:**

- The key is everything the ROM is built from EXCEPT the boot flags, plus the decomp revision.
  That is exactly the claim being made — these steps cannot see a flag, so two configurations of
  the same source owe the same anim data. `build_scopes.fingerprint_paths` is now the ONE
  implementation of "have the inputs moved", shared with `matrix.rom_input_hash`: two caches
  answering that question differently would mean one of them is wrong.
- The key is the argument; the `pre`/`post` map is the CHECK on it, because a key that silently
  misses an input is the failure this repo cannot see — the ROM would be wrong and everything
  would still be green. Every file the step wrote must be sitting at the digest it had BEFORE the
  recorded run, or at the one that run left. **Both are needed**: `pre` is what makes "not yet
  applied" distinguishable from "already applied" for a step that APPENDS (banim tables are
  additive donor-prime, #65), and `post` is the state a real tree is actually in, because nothing
  wipes the decomp between builds. A `pre`-only rule looked right and would have hit exactly never
  — a test caught it, not a build.
- Two of the seven source files those steps write (`src/data_characters.c`, `src/data_classes.c`)
  are also written by EARLIER steps. Restoring is equivalent only because those earlier steps are
  themselves config-invariant, which is a property of main()'s ORDER — so
  `check.py check_cached_steps_are_config_invariant` holds it, reading the flag list out of
  main()'s own `_requested_flags` table so adding a flag cannot quietly widen the gap.
- Which paths to hash is DERIVED (what the step wrote last time), never declared. `roots` is a
  cost hint for the first entry only; a write outside it records an `unknown` pre-state, which
  forces a miss and fixes itself.
- `NO_INJECT_CACHE=1` resolves to a cache that always runs the step, so the call site has one
  shape and no branch.

**Proved by output, not by tests passing**: canonical built with the cache cold is
`a44afcc2…`, byte-identical to the ROM built before any of this existed; `ch04boot` built with 639
files restored instead of computed is `5fa10577…`, byte-identical to the `ch04boot` ROM built the
old way half an hour earlier. Two configurations, two matching ROMs.

⚠️ **A wrapped step drops out of `check_injection_order` unless the parser is told.** `_scopes.run`
had already taught this once and the docstring said so; `_anims.run` broke it again the same day it
was added, and the unit tests were green — `test_repo_main_satisfies_all_constraints` was the one
that caught it. The parser now sees through any `_x.run(step, ...)` wrapper.

**Phase 2 (post-link ELF patching) is DECIDED AND NOT BUILT** (2026-08-23, #309 closed). The boot
TARGET is genuinely patchable — a hardcoded immediate `_redirect_new_game` writes into
`StartBattleMap` — but each `--chNN-boot` also LOADs an armed party seed that must not execute on
the real chain, so patching means runtime-gating that seed first, and `testch` / `ch05lupinboot` /
`montage` / the ch05 debug boots inject DATA and can never be patched at all.

What settles it is not the ratio but the PRIZE: **per-chapter smoke coverage already exists** — the
`--all` sweep runs every chapter's `smoke_chNN` today. Patching would not buy the coverage, only
move it into the merge gate, for ~50s of a 408-second gate. Two events would reopen it: the `--all`
sweep growing slow enough that we stop running it before playtest builds, or a chapter regression
reaching the players that a gate-tier smoke would have caught.
