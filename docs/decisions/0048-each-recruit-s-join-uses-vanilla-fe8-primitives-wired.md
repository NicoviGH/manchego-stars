---
id: 48
title: "Each recruit's JOIN uses vanilla FE8 primitives, wired per its own method — do NOT generalize:"
date: "2026-07-08"
section: "Combat System"
issues: [23]
---

# Each recruit's JOIN uses vanilla FE8 primitives, wired per its own method — do NOT generalize:

- **Baxby (ch01)** — an **off-map CUTSCENE recruit**: won over in the **ch01-ending cutscene** (Marty
  wins him over) with no on-map unit. The availability filter puts him on the ch02+ prep roster, but the
  filter only **sizes the deploy cap template** (which is never LOADed) — so it alone does NOT put him in
  the saved party. He therefore gets an explicit **between-chapter join-LOAD**: `inject_ch02` LOADs him
  (a free vanilla-Ch3 UnitDef symbol, blue, on a walkable tile) in the beginning scene **before the PREP
  CALL**, so Pick Units lists him and he persists forward like any deployed unit. This is the general rule
  for any off-map recruit — `build_campaign.offmap_join_recruits(N)` returns the recruits newly available
  at chapter N whose `recruit.via` is **not** an on-map talk (`story`/`talk`); each gets a join-LOAD its
  first chapter on the roster (empirically verified: `run.sh ch02baxby` — Baxby at `blue[8]=0x10`,
  deployable and fighting on the ch02 map). His YAML `via: market` / `cost_gp: 200` is **cutscene flavor,
  not a purchase mechanic** (there is no buy-a-unit UI; §Recruit budget: the cast is recruited by story,
  Pick Units deploys). Rides the vanilla **Forde** slot (donor Franz/Cavalier); his hand-painted axe-beak
  map sprite injects on the standard 32x32 cast pattern (`base: Gargoyle` geometry token + synth MU, like
  braulo/wolfram/meesmickle).
- **Trex (ch03)** — a **Colm-style on-map TALK recruit**: placed GREEN, joins via `CUSA` when talked to
  (the vanilla `EventScr_Ch3_Talk_NeimiColm → CUSA(COLM)` pattern; `CHAR(flag, script, talker, target)`).
  Rides **Rennac** (donor Colm/Thief). He is the army's ONLY thief, so recruitment must be **non-missable**
  and telegraphed **Joshua-style** (a hint line + FE8's auto Talk prompt). Talker = any core party member
  (below). WIRED (#23 item 2, 2026-07-09): `inject_ch03` emits the `CHAR`-per-candidate list + the shared
  `CUSA(CHARACTER_RENNAC)` script; the hint line rides the Cutscenes item. The availability filter gives
  him ch04+ prep, and the `CUSA` join makes him persist naturally (no off-map join-LOAD).
- **Lupin/Sahnar/Basil (ch04/ch05)** — wired per their YAML method when those slices land (not now).
**A generic "recruit engine" that auto-registers a unit from its YAML was explicitly rejected** (Nicolas,
2026-07-08): unit identity (slot/donor/portrait) is genuinely per-unit — vanilla has per-character tables
too — and each recruit's join method differs, so a one-size engine is over-engineering. The reusable
pieces are the availability filter + the vanilla `CUSA`/`CHAR` primitives, nothing more.
**Talker for Trex = ANY core party member** (RESOLVED — the only thief must be non-missable, and a static
`CHAR` can't name the *chosen* lord). Implemented (`build_campaign.talk_recruiters`) as one
`CHAR(flag, script, <candidate>, CHARACTER_RENNAC)` per field candidate — the ch03 blue roster
(`cast_available_at(3)`) — all pointing at ONE shared recruit script (`talk_recruit_char_entries` +
`talk_recruit_script`): completing any one talk runs `CUSA(CHARACTER_RENNAC)` (green→blue) and the shared
flag disables the rest. FE8's own multi-recruiter idiom (cf. vanilla ch14a Rennac's two `CHAR` entries).
Verified in-engine: `PT_HOST_CHAPTER=4 run.sh ch03talk` — park a candidate adjacent to green Trex, drive
Talk → Trex leaves the green array and lands in blue (`blue[09]=0x1C`).

**Entrance + recruit are DECOUPLED from the RBG-execution beat** (the vanilla Colm shape). Colm's on-map
appearance is a LIGHT turn-1 green-NPC beat (one line); ALL his substance rides the Talk
(`EventScr_Ch3_Talk_NeimiColm`) — there is no second cutscene that re-introduces him. We now match that:
the ch03 RBG-execution beat is RBG's alone (+ Wolfram), and Trex's disavowal/boast/deal MOVED to the talk.
**Why (the bug this fixes):** a freely-timed talk recruit and a fixed Brute-defeat cutscene fire in either
order, so bolting Trex's introduction onto the execution beat let a player who talked to green Trex first
recruit him *before* the cutscene "introduced" him — his line even thanked RBG for an execution that hadn't
happened. The talk line is reframed to "the wild ones — the ones your bounty names" so it is accurate from
turn 1 with zero kills (the bounty, not a kill count, is the town-trust thread). The light entrance beat
(Pinky's telegraph + RBG's "little dragon") rides the #23 Cutscenes item with the other scripted beats.
_Decided: 2026-07-08 (recruit model; Baxby + Trex the first two consumers) + 2026-07-09 (Nicolas + CLAUDE;
#23 item 2 — talker=any-core-member RESOLVED, Colm-style decouple, talk-recruit wired + verified in-engine)._

**Reward/item budget: a chapter's loot mirrors its `parity_reference` vanilla chapter — same as its enemies.**
Just as `deploy_limit` and the enemy roster track the parity-reference chapter (§Field parity), so does
the REWARD footprint — by **channel** (village / chest / shop / boss-drop) and **tier** (consumable →
gem/gold → basic weapon → stat-booster → promotion item → Silver → Sacred/legendary). The
decomp-pinned curve is `fe8-pacing-reference.md §3`. **Hard caps read off that curve:** no
**stat-boosters** and no **promotion items** until a chapter whose `parity_reference` is ≥ **FE8 Ch5**;
no **Silver** weapon until ≥ **Ch8**; no **Master Seal / Secret Shop / Sacred weapon** until ≥ **Ch14a**.
Placement follows the **parity_reference, not our chapter number** — our 8-chapter MVP maps to
*non-consecutive* FE8 chapters (e.g. ch08 → FE8 Ch13), so a chapter's reward tier is its reference's,
not "chapter N's." This is the item analogue of the recruit budget; per-chapter loot is authored in the
chapter YAML (the data is the doc). Consistent with the promotion seam (Ch8→9): our MVP chapters
(parity ≤ Ch13) sit below the Master-Seal threshold (Ch15a), so promotions stay deferred to Revel's End.
