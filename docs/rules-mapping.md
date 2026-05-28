# Rules Mapping — D&D 5e → Fire Emblem 8 (Engine-Level)

> **Scope: ENGINE, not content.** This document defines how *generic* D&D 5e mechanics
> convert to FE8-native mechanics. It is campaign-agnostic — it does not reference any
> character, chapter, or plot event. Any campaign (this one or a future one) inherits
> these rules. Character-specific application lives in `campaigns/<name>/pcs/*.yaml`.
>
> **Design spine (see decisions.md + memory):** FE8 is the spine; D&D is flavor overlaid
> on top. When a D&D mechanic has no clean FE analogue, the default is to **drop it or
> convert it to an FE-native form** — never to bolt a foreign system onto FE8's combat.
> FE8 is praised for tight, readable, well-tuned tactics; preserving that beats fidelity
> to 5e.
>
> **Eventual machine-readable home:** the conversions here are the spec that
> `tools/build-campaign.ts` + `data/srd-snapshot.json` + `data/homebrew/` implement.
> This markdown is the human-readable source of truth for that logic.

---

## Conversion Philosophy

Three tiers for any 5e mechanic:

1. **KEEP** — has a clean FE analogue or was already ratified in `decisions.md` (d20 attack rolls, damage types, doubling, summons). Port directly.
2. **CONVERT** — no direct analogue, but the *intent* maps onto an FE-native pattern. Reshape it (bonus actions → fold into the action; cantrips → finite high-use tomes).
3. **DROP** — purely a tabletop bookkeeping artifact or a system that would bloat FE combat (skill checks, concentration tracking, the short-rest/long-rest economy as literal rests). Remove; capture intent elsewhere if it matters.

---

## A. Combat Resolution

| 5e mechanic | Tier | FE8 conversion |
|---|---|---|
| **Attack roll** `1d20 + AbilityMod + ProfBonus ≥ AC` | KEEP | Replaces FE hit%/avoid entirely (decisions.md). Triangle bonus folds in as a flat to-hit modifier. Nat 1 = auto-miss, nat 20 = auto-hit + crit. |
| **Armor Class (AC)** | KEEP (as to-hit target) | AC is the number the attacker's d20 must beat. It is **separate** from damage reduction (below). A unit has one AC for being *hit*. |
| **Damage** `WeaponDice + AbilityMod` | CONVERT | FE armor-subtraction model: `Damage = roll(WeaponDice) + AbilityMod − DR`, then resistance/vulnerability multiplier. Never import 5e flat HP-vs-damage; always subtract DR (decisions.md). |
| **Damage Reduction (DR)** | CONVERT | FE's `DEF` (vs physical) and `RES` (vs magic) ARE the DR. AC handles to-hit; DEF/RES handle damage taken. This split is the key FE-ification: a 5e creature has only AC; an FE unit has AC **and** DEF/RES. |
| **Critical hit** (nat 20) | KEEP | Roll weapon dice twice (decisions.md), not FE's ×3. Improved Critical = crit on 19+. |
| **Advantage / Disadvantage** | KEEP | Roll 2d20 take higher/lower. Stored as an `advantage_state` on the attack. Cheap, no UI bloat. |
| **Doubling** (attack speed) | KEEP (FE-native) | `AS_attacker − AS_defender ≥ 4 → two attacks` (decisions.md). Pure FE8; D&D has no equivalent and we don't add one. |
| **Saving throws** `DC = 8 + Prof + Mod` vs `d20 + SaveMod` | KEEP (bounded) | Only fires for spells/staves/special effects — **never** on basic attacks. No nat-1/20 auto on saves. Success = half/no effect per effect def. Audit budget: a turn should rarely require >1 save roll to keep pace FE-fast. |
| **Hit points** | CONVERT | NEVER import 5e HP (200+). FE caps ~60–80 via growth tables. The 5e `hp_max` in a sheet is *source data only*; the in-engine value is `fe_stats.HP` + growths. |

---

## B. Action Economy — the biggest FE-ification

5e gives each turn: **1 action + 1 bonus action + 1 reaction + movement + free object interaction.** FE8 gives: **move + 1 action** (Attack / Staff / Item / Talk / special command / Wait), plus an automatic **counterattack** on the enemy phase. This is the largest structural gap and the easiest place to accidentally break FE.

| 5e concept | Tier | FE8 conversion |
|---|---|---|
| **Action** | KEEP | = the FE unit's single action (attack, cast, staff, item, command). |
| **Bonus action** | CONVERT | **Folds into the action.** A unit may NOT take a bonus-action ability *and* a main action in the same turn — it picks one. (This is the same lever applied to Sclorbo's Dance-vs-Cast.) The few "free" bonus actions that are pure flavor (e.g. a verbal taunt) become cosmetic, not a second action. |
| **Reaction** | CONVERT | FE has exactly one reaction: the counterattack. Map 5e reactions to one of: (a) the existing counterattack, (b) a **passive proc** that triggers automatically under a condition (no player input, capped uses/chapter), or (c) drop. No free-floating "use your reaction" prompts mid-enemy-phase. |
| **Free object interaction** | DROP | No analogue; irrelevant to FE. |
| **Movement split** (move-act-move) | CONVERT | FE is move-then-act (Canto units excepted). 5e's move/act/move flexibility collapses to FE's model. Mounted/Canto classes may move after acting per vanilla FE rules only. |

**Rule of thumb:** if a 5e ability says "as a bonus action" or "using your reaction," it must resolve to *the unit's one action*, *a passive auto-proc*, or *nothing*. It must never grant a second discretionary action in a turn.

---

## C. Spellcasting

| 5e mechanic | Tier | FE8 conversion |
|---|---|---|
| **Cantrips** (at-will, infinite) | CONVERT | FE has no infinite-use weapons except locked legendaries. A caster's **primary cantrip** = their equivalent of an FE unit's basic weapon: a locked personal tome with **generous finite uses** (suggest 40–50/chapter) that restocks free each chapter. **Secondary cantrips** = lower finite uses (15–25/chapter). This keeps "casters can always do something" without true-infinite spam. |
| **Spell slots** (by level, regain on long rest) | CONVERT | Tomes with **chapter-refresh charges** (long rest = chapter start, decisions.md). Slot count per level → tome use count. Cannot buy more slot-tomes; cantrip tomes restock free. Audit per-PC counts so totals feel FE (a handful of big spells/chapter, not a D&D nova). |
| **Spell level scaling** (upcasting) | CONVERT | Higher-level slot = stronger tier of the same tome (more dice/range), gated by chapter. No free-form upcast picker; the build pipeline emits the tier available at that chapter. |
| **Concentration** | DROP (mostly) | FE has no concentration tracking. Convert concentration buffs/debuffs to **fixed-duration timed effects** (N turns) or instant effects. Drop the "lose it if you take damage / cast another" bookkeeping. |
| **Ritual casting** | DROP | Out-of-combat utility; no FE combat analogue. |
| **Spell components (V/S/M)** | DROP | Flavor only. Exception: a "silenced" status can disable casting (maps to FE's Silence staff). |
| **Spell save vs spell attack** | KEEP | Save-based spells use §A saving throws; attack-roll spells use §A attack rolls. |
| **Spell range (feet)** | CONVERT | `tiles ≈ feet / 15`, then clamp to FE-sane ranges (melee 1, short 2–3, long 3–10). Tune per spell; don't let a 120ft cantrip become an 8-tile sniper unless intended. |

---

## D. Resources & Rests

| 5e mechanic | Tier | FE8 conversion |
|---|---|---|
| **Long rest** (full refill, ~1/day) | CONVERT | = **chapter start.** All slots/tomes/per-rest abilities refill between chapters. |
| **Short rest** (~per encounter) | CONVERT | No clean analogue. "X per short rest" abilities become **`uses_per_chapter`** (usually 1–2) or, if very minor, `uses_per_map`. Do not implement an in-map rest action. |
| **Class resource pools** (Sorcery Points, Ki, Rage uses, Bardic Inspiration, Pact slots, Channel Divinity, Superiority dice…) | CONVERT | Each becomes a **per-chapter use counter** or a **consumable item**, refilled at chapter start. Pick the FE form that reads cleanest: a counter in the unit panel, or an item in the inventory. |
| **Hit Dice** | DROP | Bookkeeping for short-rest healing; no FE analogue. |

---

## E. Stats & Character Math

| 5e stat | FE8 stat | Notes |
|---|---|---|
| **STR** | STR / POW | Physical attack + some weapon viability. |
| **DEX** | SKL + SPD (split) | Accuracy/crit (SKL) and doubling/avoid (SPD). One 5e stat → two FE stats; split per character concept. |
| **CON** | HP + DEF (partial) | Drives HP growth; minor DEF contribution. |
| **INT / WIS / CHA** | **MAG** (all fold here) | The single FE magic stat. Which 5e stat a class "really" uses is flavor metadata only (decisions.md). |
| **Proficiency bonus** | (folds into to-hit) | Part of the d20 attack/save formula; not a standalone FE stat. |
| **Ability modifier** | (folds into to-hit/damage) | Added per the §A formulas. |
| **Movement (speed ft)** | MOV | `MOV ≈ speed / 5`, then clamp to FE ranges (foot 4–6, mounted/flier 6–8). |
| **Skills / ability checks** | DROP | No Investigation/Persuasion rolls in FE combat. Capture as flavor in dialogue if it matters. |
| **Initiative** | DROP | FE uses fixed phase order (player → enemy → other), not rolled initiative. |

---

## F. Conditions & Status Effects

5e has ~15 conditions; FE8 has a small set (Sleep, Berserk/Confusion, Silence, Poison, Petrify, plus stat-debuff staves). Map down:

| 5e condition | FE8 form |
|---|---|
| Poisoned | Poison status (FE chip damage / stat penalty) |
| Stunned / Paralyzed / Incapacitated | Sleep status (skip turn, can't act/counter) — merge these |
| Frightened | Berserk-adjacent OR a to-hit/avoid debuff; pick one, don't stack |
| Charmed | "can't act against caster this turn" flag (treat caster as ally for that unit) |
| Restrained / Grappled | −MOV / rooted (can't move, can still act) |
| Prone | −avoid / −to-hit for a turn |
| Blinded | to-hit debuff |
| Deafened / Silenced | Silence status (no casting) |
| Petrified | Petrify (vanilla FE8 has this) |
| Exhaustion (6 levels) | DROP — too granular; pick a single −stat debuff if needed |
| Invisible | Untargetable flag (already used for terrain-hide abilities) |

Rule: never introduce a brand-new status UI for a 5e condition that maps onto an existing FE one. Merge aggressively.

---

## G. Damage Types, Resistance, Triangles

| 5e mechanic | Tier | FE8 conversion |
|---|---|---|
| **13 damage types** | KEEP | Per-class resistance/vuln/immunity bitmap (decisions.md, `engine/damage-types/`). |
| **Resistance (½) / Vulnerability (×2) / Immunity (0)** | KEEP | Applied as a multiplier *after* DR subtraction. |
| **Physical weapon triangle** | KEEP (reskinned) | Slashing > Bludgeoning > Piercing; vanilla +1 ATK / +15 hit (decisions.md). |
| **Magic triangle** | KEEP (reskinned) | Radiant > Necrotic > Elemental (decisions.md). |

---

## H. Summons & Extra Units

| 5e mechanic | Tier | FE8 conversion |
|---|---|---|
| **Summon spells / Find Familiar / Animate Dead** | KEEP (FE-native) | Spawn a temporary allied unit (FE8 Summoner phantoms are the template). Cap simultaneous summons; auto-remove at chapter end; gate by `uses_per_chapter`. |
| **Companion creatures / artificer constructs** | KEEP | Same as summons — temporary allied unit with its own stats, capped count. |
| **Wild Shape / polymorph / transform** | CONVERT | Manakete-style class transform only (vanilla FE8 Myrrh/Dragonstone path). Toggle costs a resource (per §D). No free-form polymorph into arbitrary statblocks. |

---

## I. What This Means for Class Design (generic)

When mapping ANY 5e class to FE (this campaign or future ones):

1. **Pick an FE chassis** (sprite + animations) from vanilla FE8 first; only go custom when no chassis fits.
2. **One FE base class → one FE promoted class.** Promotion happens at FE8 cadence (~Ch 9–11 of a 20-chapter game), NOT tied to a specific 5e level threshold beyond gating which features are *available*.
3. **Map the primary attack** to a finite-use weapon/tome (no infinite).
4. **Convert every "bonus action / reaction / per-short-rest" feature** per §B and §D before it reaches a YAML.
5. **Gate every level-N feature** to the chapter where that 5e level is reached on the campaign's level curve (see `class-progression-tables.md`).
6. **Collapse 5e stats to FE stats** per §E.
7. **Drop tabletop bookkeeping** (initiative, skill checks, hit dice, components, concentration tracking).

The per-class application of these rules lives in `class-progression-tables.md`; the per-character application lives in the campaign's PC YAMLs.

---

## Open Items (to confirm with playtesting / Nicolas)

- **Primary-cantrip use count** — proposed 40–50/chapter (effectively infinite within a map but FE-legal). Confirm the number feels right, or make signature cantrips truly unbreakable like a prf weapon.
- **Saving-throw frequency budget** — how many save rolls per turn is "still FE-fast"? Proposed: design so a typical turn needs ≤1.
- **Reaction procs** — confirm we want auto-procs (no player input) vs. dropping reactions entirely. Auto-procs preserve flavor but add enemy-phase animations.
- **DEX → SKL/SPD split ratio** — per-character judgment, or a fixed formula?
