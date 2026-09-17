---
id: 276
title: "What asking \"what is a body\" found: ch02 was never counting its own wave"
section: "Operational Gotchas (durable)"
issues: []
---

# What asking "what is a body" found: ch02 was never counting its own wave

Defining mirror% forced the question the ratio had never been asked, and the answer was that our
side and the twin's side were counting different forces.

`chapter_units` — THE our-side force builder — read only `enemy_units`. `vanilla_enemies` reads
every red `UnitDefinition` in the twin's curated arrays, **reinforcement waves included**. ch02
declares its rear-raider pair under the `reinforcements:` key, so its verdict compared **seven of
our bodies against nine of vanilla's**, and the two missing ones scored as divergence. That entry
also carries `levels: [2, 3]` and no `level:` — the per-body list `build_campaign` zips with
`positions` to emit the ROM — so both bodies were additionally modeled as **L1**.

ch06 had already hit this and worked around it privately: its Hard-only turn-4 wave is declared
inside `enemy_units` rather than under `reinforcements:`, and its own YAML comment says why —
*"#48's static bar folds that array in on the vanilla side unconditionally, so declaring ours is
what makes the two sides count the same force."* That is the general rule, and it was being
enforced one chapter at a time by hand.

Corrected, ch02 is not the campaign's easiest chapter by a wide margin. It is an exact
transcription:

| | shipped | corrected |
|---|---|---|
| threat/slot | 5.3 (**x0.81**) | 6.5 (**x1.00**) |
| clear-load/slot | 3.0 (**x0.79**) | 3.8 (**x1.00**) |
| mirror | 78% | **100%** |
| bodies ours vs twin | 7 vs 9 | 9 vs 9 |

The verdict was OK before and is OK now — it never flipped a gate, which is exactly why it
survived four chapters. `--mode difficult` moves identically (x0.81/x0.79 → x1.00/x1.00).

So there are **two** copy-x1.00 chapters, not one, and #367's "mirror% climbs as the donor
pipeline improves" reads differently: ch02 was already a transcription in 2026-08, and the
instrument was hiding it.

The fix is two functions and it is the general form, not a patch on ch02:

- `build_campaign.chapter_roster_entries` answers *"what is this chapter's force"* once, over
  `ENEMY_ROSTER_KEYS`. It lives on the desk that owns the chapter schema because four separate
  gates key off that answer — the parity metric, the AI-donor guard, the `personal:` injection
  routes (#284) and the raw-pid boss registry — and each had its own copy of the question. Two of
  those copies were holes: a boss under `reinforcements:` could carry a `personal:` block with no
  route into the ROM, and could ride a raw pid with no `RAW_PID_LEVEL_SOURCES` row, while
  `_our_base_level` modelled it as malus-immune anyway. `check.py` names the keys rather than
  importing them (its CI job runs on a bare interpreter), and a test fails if the two ever
  diverge.
- `_entry_combatants` is the single entry expander. It was three near-copies — one in
  `chapter_units`, one of its own, one inside `role_findings` — which is precisely how `levels:`
  came to be honored in one reader and defaulted to L1 in the others. Body count, per-body level
  and the `levels:`↔`count`/`positions`/`composition` guard all live in `_body_levels` now.

**A widened definition has to reach every reader or it makes the report contradict itself.** The
first attempt adopted the new roster in the verdict alone, and `--chapter ch02` then printed *"ours
(9 enemies)"* two lines above *"ours line 7 · reinf 0"*. Five readers were still on
`chap['enemy_units']`: the dynamics split, the unmodeled-boss warning (a gate hole — a staff-only
boss under `reinforcements:` raised no BOSS DROPPED), `load_field`'s cast tables, `role_findings`
(an arm of the parity gate, so a boss parked under `reinforcements:` could never be graded
per-unit), and `solo_contributors`.

One thing the shared expander must NOT unify: the parity metrics drop a unit with no modeled
weapon, and the cast tables must not — a chapter's healer is a body our units can kill and walk
past. That is the `drop_staff` flag, and the output diff is what caught it: ch06's throughput
moved 7.54 → 7.41 and three lords' worst matchups changed, because the menders had silently left
the field.

**A per-unit question is answered per unit TYPE, not per body.** This one was self-inflicted and
caught before it landed: consolidating on the shared expander made `role_findings` yield a row per
BODY, and ch08's `count: 4` ice-troll immediately read as *"4 units flagged is_boss (ice-troll,
ice-troll, ice-troll, ice-troll)"* with every warning repeated four times. (The old code was
correct here — it expanded per distinct TYPE — so this is a regression the consolidation
introduced, not a bug it found.) Whether a unit's threat is an outlier does not depend on how many
of it stand on the map, and `role` is a `--check` gate arm, so it would have redded CI on the first
locked chapter with a multi-copy boss entry. Hence `distinct`, which collapses bodies of one entry
unless `levels:` makes them genuinely different units — and a boss CENSUS that counts entries, since
`distinct` still splits one entry by level and every row carries that entry's id.

**And the output diff has to cover every chapter the tool reads, not the ones the change was
about.** The first diff ran ch00–ch06 and reported "only ch02 moves" — which was true of those
seven and false of ch08, a `status: planned` chapter the curve still grades. A planned chapter is
brainstorm seed, but the tool reads it, so it is part of the tool's output. Verified now over all
nine chapters, every `--lord-floor` table and all four curve reports (authored + three modes):
**only ch02's numbers move.**
