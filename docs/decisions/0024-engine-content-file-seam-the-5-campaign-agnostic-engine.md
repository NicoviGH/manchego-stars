---
id: 24
title: "Engine/content file seam: the 5 campaign-agnostic engine hooks live in `tools/inject/`, not `build_campaign.py`."
date: "2026-06-19"
section: "Working Conventions (Definition of Done)"
issues: []
---

# Engine/content file seam: the 5 campaign-agnostic engine hooks live in `tools/inject/`, not `build_campaign.py`.

So the pipeline track never has to open the content track's file. `tools/inject/decomp.py` holds the
shared decomp-patch primitives (`_find_brace_block`, `_replace_brace_block`) + the decomp paths both
sides patch; `tools/inject/engine_hooks.py` holds the 5 hooks (player-start-cursor guard, terrain-name
guard, battle-map-kind fallback, lord-select, lord-floor) + their engine-only path/flag constants.
`build_campaign.py` imports from `decomp` and orchestrates `engine_hooks.*`. The 6 sprite/palette
injection hooks **stay** in `build_campaign.py` (content-owned): new chapters bring new cast art, so
that machinery belongs with content — which is why this is the *narrow* (5-hook) split, not all 11.
Done **preventatively** rather than "when it bites": the seam is already known (waiting for a merge
conflict teaches us nothing new) and a silently mis-resolved conflict could drop an engine hook — the
exact failure `check.py check_engine_guards_present` exists to catch. That guard is rewritten to assert,
per hook, that it is *defined* in `engine_hooks.py` AND *called* (`engine_hooks.<fn>(...)`) from
`build_campaign.py`; both arms verified to bite. The refactor is behavior-preserving — proven by a
byte-identical ROM (md5 unchanged) plus `lordfloor`/`ch01win` playtests. Work tracker #50.
_Decided: 2026-06-19_

**Coordination model: feature-flow over fixed lanes.** We first split work into two fixed lanes
(content = `campaigns/**` + `build_campaign.py` + art tools; pipeline = `difficulty.py`/`fe_combat.py`/
`check.py`/`playtest/**`/`build.sh`/CI) and **enforced** them with a file-glob ownership guard
(`check.py check_lane_ownership`, keyed off the `inst/<track>` branch; #55) because the seam was
honor-system and got crossed. The guard worked, but the lanes were the wrong *shape*: real features
routinely **span** the glob seam — the per-chapter parity gate (gate + `balance_locked`), adding a weapon
(combat-model map + `WEAPON_ITEM_ENUM`), lord-select UX (bounced engine→content over *file paths*), and
capturing a unit's battle anim (the `record*` scenario **and** the sandbox build it fires on). A fixed
partition doesn't *prevent* collisions on a spanning feature; it **saws the feature in half** so neither
lane can finish-and-verify it. We already patched around it once (the 2026-06-22 "content `record*` are
content spot-checks" carve-out — queued, never landed) and hit the same wall again with `recordrbgtest`
(capture = pipeline scenario, sandbox = content build → un-verifiable from either lane).

The root error was **conflating build-isolation with ownership**. Isolation (two ROM builds corrupt one
tree) is physical and is solved by *a* worktree — any worktree. Ownership (who may change what) is logical
and got welded onto the same `inst/<track>` worktree, forcing work to partition by file type. Unwelded:

- **Feature-flow.** A task = issue → short-lived `feat/<n>-slug` branch off `main` → an **ephemeral**
  worktree (isolation only) → a **PR** → CI + `/code-review` → squash-merge → drop the branch + worktree.
  Concurrency = N feature worktrees, not two fixed slots. A PR may span the old seam; that is the point.
