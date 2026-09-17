---
id: 58
title: "Per-chapter parity beyond Ch1 = enemy-pressure vs a `parity_reference` vanilla chapter."
date: "2026-06-19"
section: "Combat System"
issues: []
---

# Per-chapter parity beyond Ch1 = enemy-pressure vs a `parity_reference` vanilla chapter.

Our cast is fixed all game and already at vanilla parity (above), so a chapter's difficulty is set by its
enemies + deploy cap. The difficulty engine measures **enemy pressure** — threat/slot (Σ enemy
damage-per-round vs a fixed yardstick unit ÷ deploy cap) and clear-load/slot (Σ enemy bulk ÷ deploy cap) —
for our chapter and for the vanilla chapter named in a new per-chapter YAML field `parity_reference:
"FE8 ChN"` (the cadence-bar source of truth; vanilla enemies auto-extracted from the decomp). Parity =
within a band. The engine also still reports our actual cast vs our enemies (throughput / durability /
carry) as the absolute "can our roster clear it" check. **First cut analyzes at base level**; leveled stat
projection is a deferred fast-follow (needs the recruit schedule, #45 item 5). Execution + full design: #48.
_Decided: 2026-06-19 (Nicolas)_

**Implementation: the vanilla force comes from a curated array registry, not a per-chapter header.**
The decomp only decompiled enemy `UnitDefinition` arrays to C for the Prologue + Ch1 (`*-eventudefs.h`);
Ch2+ live in the monolithic `events_udefs.c` with address-named arrays interleaved with green/skirmish/
cutscene units that a region-scan would wrongly pull in. So `tools/difficulty.py` resolves a
`parity_reference` through a small **registry** (`PARITY_REFERENCE_UDEFS`: ref → file + the exact fightable
red array names) — the single human-curated point of "which vanilla arrays ARE this chapter's enemies".
Both sides project every enemy (generics AND named bosses) off **class base autoleveled to its level** — a
boss's personal line is the dynamic playtest's concern, not this static proxy — so ours and vanilla resolve
on identical footing and the yardstick/deploy-cap cancel in the ratio. Validation: our Ch1, mirrored 1:1 off
FE8 Ch1, reads at parity (threat ×0.89, clear-load ×0.97, both inside ±25%). Registry curation method for the
events_udefs.c chapters: the arrays a chapter's `chN-eventscript.h` references **whose RED units carry
weapons** — which excludes the interleaved skirmish/tower data (unreferenced) and the cutscene/preview arrays
(endgame villains placed with empty `.items`). Curated + fully modeled: Prologue, Ch1, **Ch2 (9), Ch3 (10),
Ch4 (23), Ch5 (23), Ch6 (25)**. **FE8 Ch13** (our ch08 — a scripted-defeat objective, informational only, not
a CI-gated chapter) is the lone deferred reference. `make difficulty CH=chNN` gains the pressure line;
`make difficulty` (no CH) prints the campaign curve.
_Implemented: 2026-06-19 (CLAUDE; pipeline track, TDD)_

**The parity curve is surfaced in CI, and the hard gate enforces per-chapter via an opt-in `balance_locked` flag (#48 (b)).**
CI's `build` job runs `make difficulty-gate` (`difficulty.py --curve --check`) on every build (after the
submodule checkout it needs to read the decomp HEAD), so balance spikes/sags and parity regressions are
visible on every PR **and** a regression on a finished chapter hard-fails the build. The gate is **per-chapter
opt-in**: because we author chapters as we go (the campaign isn't done until it's basically done), an
all-chapters gate would redden CI for every unwritten chapter. Instead a chapter is enforced only once content
marks it balance-final with **`balance_locked: true`** in its chapter YAML. `curve_gate_failures(rows)` fails a
**locked** chapter that is off-parity (`verdict != OK`), unreliably measured (a dropped boss — an unreliable OK
is not a pass), or has no curated `parity_reference` at all (you can't lock a chapter the metric can't measure —
a config mistake, surfaced loudly). **Unlocked** chapters (unwritten or mid-authoring) stay informational and
never gate, so an in-progress chapter never reddens CI; with zero locks the gate passes (enforces nothing),
which is why `--check` can ship before any chapter is locked. The lock is set in the **content** lane
(`campaigns/**`); the gate logic that reads it is **pipeline** (`difficulty.py`). Workflow: author a chapter's
enemy inventory → confirm it reads OK on the curve → add `balance_locked: true` → CI now defends it.
Decision: explicit flag over auto-detecting an authored force, because a parity gate's job is to lock in
*finished* work — auto-detect can't tell "balanced" from "halfway through placing enemies" and would fire
mid-authoring (Nicolas, 2026-06-21).
_Implemented: 2026-06-19 (informative curve); per-chapter gate enforcing 2026-06-21 (CLAUDE; pipeline track, TDD)_

**Monster/exotic enemy weapons stay out of the content-owned weapon map; venin is a base-might proxy (#53).**
FE8 Ch4 "Ancient Horrors" (all-monster) and Ch6 "Victims of War" needed weapons our cast never carries: the
monster claws (`fetid/rotten/venin-claw`), Evil Eye, and extended standards (`thunder`, `halberd`, `venin-axe`,
`iron-blade`, `horseslayer`). Their stats live in `fe_combat.W`, but the decomp-item→weapon mapping for them is
a **difficulty-local** `VANILLA_ONLY_ITEM_TO_WEAPON` merged into `ITEM_TO_WEAPON` — deliberately **not** in
`inject/decomp.py`'s content-facing `WEAPON_ITEM_ENUM` (that map drives the build's authored YAML loadouts and
is content-owned across the seam; our cast authors none of these). Modeling calls: **venin/poison weapons**
(which drain HP over turns in vanilla, not on-hit) are modeled at their **base might** as a low static-DPR
proxy — low threat, but the unit still resolves and counts as modeled rather than being dropped. **Monster
claws** are plain physical might (off-triangle, vs Def); **halberd/horseslayer** keep their effective-vs-cav
triple. **Staff-only healers** (a Priest/Troubadour carrying no weapon) are still dropped by design — that is a
weaponless drop, not an unmodeled-weapon drop, so an all-modeled reference can legitimately resolve fewer
units than it has armed-RED entries (Ch6: 27 armed → 25 modeled). _Implemented: 2026-06-19 (CLAUDE; pipeline track, TDD)_

**A fielded healer/support unit is modeled as weaponless (0 throughput, still a body for durability); `_weapon_for` honors the YAML `unlock` flag (#62).**
The difficulty engine couldn't fairly model a staff-only unit (our Sclorbo, vanilla's Moulder): `_weapon_for`
either crashed (`attack_speed` → `NoneType.wt`) or mis-roled a base healer as an attacker by crediting a tome
its base class can't wield. Two changes: (1) **`fe_combat` is now None-weapon-safe** — a `Combatant(weapon=None)`
has attack speed = Spd (no weight to bear), deals 0 damage / 0 throughput as an attacker, but is a valid
*defender* (enemies still resolve hit/damage against it, so its durability is computed). (2) **`_weapon_for`
skips inventory items whose `unlock` precondition isn't met** for the modeled (base-class) state — the YAML's
own `unlock: promotion` flag (e.g. `sclorbo.yaml`'s Light tomes) is the data-driven gate, cleaner than
inferring class weapon-ranks. So a base Priest resolves to **weaponless support = 0 throughput**, mirroring
vanilla Moulder, instead of an inflated 0.84 kills/round. **Healing itself stays unmodeled** (the static proxy
disclaims it; both our and vanilla fields run a healer, so `durability(min)` understatement is largely a
canceling artifact) — modeling heal-per-turn was scoped out as optional. _Implemented: 2026-06-20 (CLAUDE; pipeline track, TDD)_

**The vanilla PLAYER deploy field is derived from the decomp per chapter, not hand-maintained (#61).**
The party-side parity delta (our cast vs vanilla's deploy on the same enemy set) was keyed off a hand-curated
`VANILLA_FIELDS` dict that only held Ch1, so every other chapter printed "delta skipped." It now derives from
the decomp (HEAD) the same way the enemy force does: `PARITY_REFERENCE_ALLY_UDEFS` maps a chapter's
`parity_reference` to the reference chapter's blue force-deploy + reinforcement `UnitDefinition` arrays
(e.g. `UnitDef_Event_Ch1Ally`/`…AllyReinforce`, `UnitDef_Event_Ch2Ally`). Each named ally resolves to
**class base + its personal line** (the same donor-base inheritance our cast uses, via the unit's `.charIndex`)
— allies are **not** autoleveled (CharacterData stores their join-level display stats), and the weapon is the
**first attacking item** (symmetry with how `player_combatant` models our cast; a staff-only ally → weaponless
support per #62). `VANILLA_FIELDS` is deleted. The Ch1 delta is materially unchanged (throughput 3.74 → 3.69,
durability/carry identical) — the small shift is *more* faithful (Seth/Franz now use their equipped first weapon
from HEAD, not a hand-picked strongest), and Gilliam's hand-typo Con 13 is corrected to 14. _Implemented: 2026-06-20 (CLAUDE; pipeline track, TDD)_
