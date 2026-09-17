---
id: 277
title: "A rescue-fuse FORECAST is the reusable question, and it is not a danger grid"
date: "2026-09-05"
section: "Operational Gotchas (durable)"
issues: [26, 367]
---

# A rescue-fuse FORECAST is the reusable question, and it is not a danger grid

#367 asked whether the difficulty model has a spatial element that was designed and never
wired. The answer for a full per-tile danger grid is: not built, and deliberately out of
scope here -- that is a different, much larger tool. What chapters actually need, repeatedly,
is narrower: *for a protected tile (a rescue boat, a defend objective, a fragile NPC), which
enemies can get a firing position on it, on what turn, for how much damage per phase, and
therefore when does it die?* `tools/rescue_forecast.py` answers exactly that, reusing (never
reinventing) three things that already existed on three different desks:

- `map_placement_preview.foot_reach` -- the contested (turn-1-body-blocked) Dijkstra
  `reached_on_contested:` already uses.
- `difficulty`'s stat resolution (`_entry_combatants`, `_class_base`, `on_terrain`) --
  the SAME donor-derived numbers the parity gate grades a chapter's force on.
- `fe_combat.damage_per_round` -- the decomp's own combat math, never a second model.

**The five pieces.** (1) `firing_cells(terrain, target, weapon_range)`: every cell at
Manhattan distance 1..range that a foot unit can stand on -- FE8 has no line of sight, so
this is pure distance, not a walk (`decisions.md` -> "What terrain cannot do is stop a
ranged weapon"). (2) `arrival_to_cells`: the turn an enemy first stands on ANY of those
cells, walking the CONTESTED map -- `None` (never engages) is a first-class result, not an
error. (3) damage/phase is `fe_combat.damage_per_round` with the target resolved on its
real terrain. (4) `sink_band`: HP / damage-per-phase is a MEAN, not a fact (`decisions.md`
-> "A rescue clock is a HIT RATE"), so the sink turn is reported as a band -- modeled as the
first-passage time of a random walk with the phase's own mean and variance (the Wald /
inverse-Gaussian approximation: `E[phases] = hp/mu`, `Var[phases] = hp*sigma2/mu**3`), a
heuristic width stated as exactly that in the docstring, not a claimed percentile. (5)
`concurrent_attacker_cap`: when several enemies can reach one target, how many can attack
it in the SAME phase is a bipartite MATCHING between attackers and the firing cells each
one's own range reaches, not a single number split between them.

**Validated against ch06's own measured numbers, not synthetic stand-ins.** boat-east's
javelin-range firing cells are exactly `(15,12) (17,10) (17,13) (17,14)`, one melee cell
`(17,13)`; boat-west's are `(2,17) (4,18) (4,19)`, one melee cell `(4,18)` -- both match
their declared `door`. `merfolk-thrower` (soldier L7, javelin) computes to 2.76 dmg/phase
against the hull's real fighting stats (19 HP / 6 Def in FOREST cover / +20 avoid) and
**cannot reach any east firing cell on the contested snapshot -- its own allies cork all
four.** `ice-crab` (bael L1, venin claw) computes to 2.82 dmg/phase, reaches its door on
turn 2, forecast sink band ~turn 6-12 (expected 9) against a declared 8 -- inside the band.

**The finding this reproduces, in one number: ch06's declared "sinks the hull on turn 7"
(east) describes a unit that never arrives.** That prose lives in `difficulty_note:`, not a
schema field -- nothing was asserting it, so nothing broke when it stopped being true. This
is the SAME shape as the already-confirmed #26 bug (`decisions.md` -> "AI_B is the APPROACH
and AI_A is the ACTION"): the tooling that measures a chapter's clock did not exist, so the
design note was never checked against the map it now sits on.

**The guard is ADVISORY, not a gate, on purpose.** `check.check_rescue_fuse_forecast` prints
(never appends to `fail`) when a declared `rescue_pursuers:` id cannot reach a firing cell
for any of its chapter's `rescue_boats`, and would check a declared numeric fuse against the
forecast band if a chapter ever adopts an (currently unused, forward-looking) `declared_fuse:`
field. Flipping the reachability half to a hard gate is a follow-up left for Nicolas once
ch06's east pursuer is resettled (move the pursuer, or re-declare which hull is its clock) --
this PR does not touch ch06's YAML to make the guard pass, because the finding is real and
the fix is a design call, not a bug in the tool. `chapter_status.loose_ends` surfaces the
identical finding for `make chapter CH=ch06`, sharing `check._fuse_forecast_findings` so the
two never drift into two different opinions about the same chapter.

**Same code path, two latent bugs fixed alongside it (map_placement_preview.py, not
rescue_forecast.py's own code).** `units_reaching` iterated `chapter['enemy_units']` only,
though its docstring claimed reinforcements were included -- true only because ch06 happens
to keep its Difficult-only wave inside `enemy_units`. It now reads
`build_campaign.chapter_roster_entries`, every roster key. `enemy_bodies` never read past
`enemy_units:` at all, so a `reinforcements:`/`enemy_reinforcements:` entry's body was
invisible to the contested Dijkstra's blockers regardless of timing -- and a naive fix that
widened the loop without ALSO fixing the timing test would have flipped the bug rather than
closed it, since those keys carry `trigger_turn`, not `arrives_turn` (ch02's `rear-raiders`
wave): testing `arrives_turn` alone reads an absent field as falsy, i.e. turn-1. The one
correct predicate -- "is this entry's body on the board at turn 1" -- was already living
correctly, but only, inside `difficulty.chapter_enemy_groups`; it is now
`build_campaign.entry_is_turn1(key, enemy_def)`, and both readers share it.

**Output diff, over all nine chapters (ch00..ch08), because a previous PR on this exact area
got burned diffing only seven of them (`decisions.md` -> "only ch02's numbers move").**
`enemy_bodies`, `units_reaching` (with each chapter's own `rescue_boats` as targets, `[]`
where none are declared) and `difficulty.chapter_enemy_groups`'s counts/names: byte-identical
before and after, on every chapter. This is a real, checked result, not an assumption --
ch02 is the only chapter using a `reinforcements:` key today, and its wave was invisible to
`enemy_bodies` both before (never read) and after (correctly excluded as not-turn-1); no
chapter besides ch06 declares `rescue_boats`, so `units_reaching`'s target list is `[]`
everywhere else and its output cannot move. The FIX has zero live-chapter impact today and
is still worth shipping: it closes two latent traps for the day a chapter fields a
reinforcement-key pursuer against a rescue target, which #367's own forecast model now makes
newly possible to author correctly. `chapter_status.report()` moves on exactly one chapter
(ch06) and by exactly one line -- the new advisory loose-end -- everywhere else
byte-identical.

**Review found two more crash paths the roster-widening opened, both fixed before merge.**
`/code-review high`, four independent angles, three of which converged on the same defect
from different directions: `_fuse_forecast_findings`'s declared-fuse loop compared
`r.sink_low <= declared <= r.sink_high` over every row that reaches its target, but
`pursuer_forecast` returns exactly `arrival_turn` set with every sink field `None` when the
attacker reaches a firing cell yet deals zero true damage there (`sink_band`'s own `None`
case) -- unreached today because no chapter has adopted `declared_fuse:` yet, but a raw
`TypeError` the day one does, inside the function whose own docstring and dedicated test
promise it never fails the build. Fixed by requiring `sink_low is not None` too. Second: the
now-widened `units_reaching` calls `difficulty.enemy_ai_bytes` on every roster key, which
RAISES on an entry with neither `donor:` nor `ai_override:` -- a normal mid-draft state --
and `check_rescue_targets` called it with no guard, inside a `main()` that runs every check
with zero exception isolation between them. One ungrounded `reinforcements:` entry on a
future rescue chapter would have crashed the ENTIRE `check.py`, every other gate along with
it. Fixed with the same try/except-and-skip idiom the function already used two lines above
for an unbuilt map. Both reproduced with a failing test before the fix -- the second via a
`check._chapters` monkeypatch, the first such precedent in that test file.

**The review's other half was reuse, and "it's only latent" was the wrong bar.** The same
pass flagged five places where this work had grown its own copy of something that already
existed. The first instinct was to leave them — all latent, none touching a gate or a live
chapter's numbers. That reasoning does not survive contact with where the code actually
lives: these are not pre-existing debt the PR walked past, they are code the PR itself wrote,
or the third instance of a bug in a file whose other two instances it already claims to have
fixed. A change that says "same code path, two latent bugs fixed alongside it" and leaves the
third copy of that same bug in that same file has not fixed the pattern, it has fixed two
thirds of it.

- **`placed_units` was that third copy.** `enemy_units` alone, plus a `late` flag testing
  `arrives_turn` alone — which reads a `trigger_turn` wave as turn-1, exactly backwards. Now
  iterates `ENEMY_ROSTER_KEYS` and asks `entry_is_turn1`, OR'd with `hard_mode_only` (a MODE
  gate, a different axis `entry_is_turn1` deliberately does not model).
- **`target_combatant` bypassed `difficulty._one_enemy`**, the path every other enemy
  resolves through, so it skipped autolevel, `CLASS_TAGS` (which `fe_combat` reads to resolve
  effective weapons) and any personal line. A no-op while ch06's boats are level-1
  no-personal `CLASS_FLEET`; silently wrong the day a `rescue_boats:` entry declares
  otherwise.
- **`firing_cells` was a second copy of the Manhattan-range check `units_reaching` already
  ran inline.** It is a terrain/range primitive, the same family as `foot_reach`, so it moved
  to `map_placement_preview`; `units_reaching` calls it and `rescue_forecast` aliases it.
- **`reached_on` and `arrival_to_cells` were mirror-image glue** over the same two
  primitives — Dijkstra, then points-to-turn — differing only in which end was plural.
  `arrival_turn_to` takes both ends as lists and serves either direction.
- **`chapter_status` grew a third `try: import X except ImportError: None`.** Extracted
  `_try_import`; the three wrappers stay separately named because tests monkeypatch them
  individually.

**One flagged "duplicate" was refused, and the reason is the general rule.**
`_boat_terrain_name` was called a duplicate of `difficulty.vanilla_terrain_at`. It is not:
`vanilla_terrain_at` resolves a tile on a VANILLA DONOR layout by name, `_boat_terrain_name`
reads OUR OWN compiled grid already in hand. Those differ by construction — see *"ch06
departs from its donor's terrain in 21 declared cells"* above, and both boat tiles are among
those 21 (`TILE_2E`/`VILLAGE_REGULAR` → `FOREST` by `terrain_divergence`). Unifying them
would swap the hull's cover for the donor's terrain and move every sink band. **A shared
shape is not a shared question**, and a dedup that changes an answer is a regression wearing
a cleanup's clothes.

Verified by output diff across all nine chapters over `placed_units`, `reached_on` (contested
and uncontested), `units_reaching` and the whole `chapter_forecast`: the only change anywhere
is ch02's `placed_units` gaining its two `rear-raiders` bodies, correctly marked late — which
is simultaneously the proof that the four refactors are behaviour-preserving and that the
fifth was a real bug.
