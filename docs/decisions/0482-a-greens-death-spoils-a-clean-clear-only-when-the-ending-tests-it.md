---
id: 482
title: "A green's death spoils a clean clear only when the chapter's ending tests that green"
date: "2026-11-27"
section: "Combat System"
issues: [788, 764, 510]
---

# A green's death spoils a clean clear only when the chapter's ending tests that green

**Decided (Nicolas, 2026-11-27, #788).** A clean clear is every recruit, no blue death and no
reward missed. A green unit's death spoils it only if that green gates a reward. Green deaths stay
reported as a metric (`rec.greens`). This amends ADR 0376's decision 1, which counted every green's
death as a loss.

**Why.** R5's sizing (#764 comment 7224984293): vanilla Ch19 starts with ten allied greens (Mansel
and nine generic 0xCD Knights) that charge enemies on their own phase. The best of 15 tries lost 6
of 10, so Ch19 could never be clean, though none of them gates anything. A player does not reset
the chapter for them.

**What "gates a reward" reads.** The greens the chapter's ending scene tests for life: every
`CHECK_ALIVE` (`EvtCheckUnitNotDead`, CHECKSTATE 0x33 sub 2) that `sight.walkScript` reaches in
`ChapterEventGroup +4C endingSceneEvents`, CALLs followed (`sight.aliveChecks`,
`sight.endingChecks`, read once at the chapter's start through `api.gated`). It is read from the
ROM, never a table, so Manchego Stars' own endings are covered by the same read.
- A green's death spoils the clear when the green is an escort (its death ends the game) or is on
  that list (`botrun.spoilingDeaths`). Every death stays in `rec.deaths`; `rec.clear.lost` holds
  the spoiling ones.
- Branches are not evaluated, so a green the ending tests for dialogue alone also counts. Vanilla
  has no such case: every ending test of a non-player unit guards a `GIVEITEMTO`.
- A harness with no `api.gated` keeps ADR 0376's rule (every green counts), never a silent pass.
- An owed recruit is still judged by `recruits_missing`, whatever its side.

**Proof on the vanilla ROM** (a probe running `sight.aliveChecks` over the base ROM's bytes, the
group from `gChapterDataAssetTable[gChapterDataTable[ch].mapEventDataId]`, the tables
GetChapterEventDataPointer reads at 0x088B363C and 0x088B0890): the non-player units tested are
index 7 (Ch6) F9 FA FB (Orion's Bolt, `EventScr_Ch6_EndingScene`), index 17 and 30 (Ch17) Syrene
and F4-F7 (item 0x55, `EventScr_089F79D4`), index 24 (Ch10b) 89 8A 8B
(`EventScr_Ch10b_EndingScene`). These match the decomp's `CHECK_ALIVE` lines. No ending tests 0xCD,
so Ch19's greens gate nothing. Unit tests: `test_sight.lua` (aliveChecks), `test_botrun.lua`
(`test_a_green_death_spoils_the_clear_only_when_the_ending_tests_it`), each failing without the change.

**Not changed.** The planner: ADR 0384 already pays an allied green's survival only as a tie-break,
and an escort's death as a forfeit.
