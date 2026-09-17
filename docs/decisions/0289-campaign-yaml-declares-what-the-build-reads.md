---
id: 289
title: "campaign.yaml declares what the BUILD reads, and it is scanned like any other doc"
date: "2026-09-17"
section: "Documentation Model"
issues: [30]
---

# campaign.yaml declares what the BUILD reads, and it is scanned like any other doc

#30 asked a small question — is `campaign.yaml` still accurate? — and the answer was no, in
three places at once. All three had survived for the same reason: **nothing read them, and
nothing scanned them.**

## A restatement nobody reads is the one that rots

`campaign.yaml` carried a `chapters:` block listing the campaign's chapters by name. By the
time anyone looked it was wrong in every way a list can be: it omitted the prologue, declared
`count: 7` for a nine-chapter campaign, and from ch04 on named every chapter one number too
low — the Elven Tomb filed as ch04 when it is ch05, on down to the Eastway Ambush at ch07 when
it is ch08.

The provenance is written in two other records: the old Ch 4 was **split** into White Moose +
Elven Tomb on 2026-05-31, and every chapter after it moved up one. ADR 0113 and ADR 0155 both
note their own renumbering that day. This block did not, because it is a copy, and a copy does
not get renumbered — it gets forgotten.

**A chapter's identity belongs to its own file.** `chapters/ch*.yaml` holds it,
`tools/campaign_chapters.py` is the single reader (#312), `docs/CHAPTERS.md` is generated from
that. The block is deleted and `check_campaign_declares_no_chapter_list` keeps it deleted.
Nothing broke while it was wrong, and that is the point: it could only ever mislead a reader,
which no build gate can catch.

## The file was outside the drift scan, so it kept teaching a retired tool

`campaign.yaml`'s first comment told the reader it was *"Read by tools/build-campaign.ts"* — a
tool retired when this repo moved to Python, and a name that has been **in the `DEAD_CONCEPTS`
registry** the whole time. Two more registered dead names sat in a `data_sources:` block
(`srd-snapshot`, `open5e-snapshot`) pointing at `data/srd/*.json`, a directory that does not
exist. The registry could not see any of it, because `DOC_GLOBS` covered markdown and code and
stopped there.

This is the same re-narrowing that let `.github/ISSUE_TEMPLATE/custom_unit.md` teach the retired
`clone_into` binding and the dialogue-pass skill teach the retired CHARACTER wrap. A campaign
declaration is doctrine a reader follows, so it is scanned like one: `campaigns/*/campaign.yaml`
is in `DOC_GLOBS`, which puts it under the dead-concept scan, the dangling-tool-reference scan
and the decision-pointer scan at once.

**The chapter YAML is deliberately NOT in yet** — it carries eight live hits of the retired
29/42-CHARACTER wrap vocabulary, and some of those lines are past-tense narration of the change
itself, which must not be swept blind. That is #393.

## A number this file states about the ENGINE can only disagree with the cartridge

`progression.promotion_threshold: 20` was simply false: FE8 gates promotion items at level 10
(`CanUnitUsePromotionItem` → `unit->level < 10`, `bmitemuse.c`). The field is gone rather than
corrected to 10, because the engine owns the number and restating it here recreates the same
failure one digit later.

What actually keeps the MVP unpromoted is **item availability, not level** — no Master Seal
exists before Ch 9, and ch05's Guiding Ring is deliberately unusable in the convoy (ADR 0155).
`level_cap_unpromoted`/`level_cap_promoted` stay at 20 because that IS the engine's own
`UNIT_LEVEL_MAX` (`bmunit.h`) and the fields say which.

## What stays, and why "unread" was not the test

`world_map:`, `permadeath:`, `starting_gold:` and `progression:` are also unread by the build,
and all of them stay. They are **dormant declarations with named futures** — the world map is
#29, the level band is #367 — and they are true. The test that mattered was never "does code
read it", it was **"is it still true, and does something else already own it"**. The
`chapters:` block failed both.
