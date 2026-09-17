---
id: 19
title: "Playtest test-chapter build (`make TESTCH=1`)"
date: "2026-06-23"
section: "Documentation Model"
issues: []
---

# Playtest test-chapter build (`make TESTCH=1`)

`build_campaign.py --test-chapter` re-activates the dormant `inject_test_chapter`:
New Game boots **straight into a Ch1 sandbox** (vanilla Border Mulan map, hosted at
chapter slot 1 *in place of the prologue*) with the whole classed cast deployed and
the (reskinned) foes loaded, all cutscenes/objectives stripped. It skips the ~5-min
prologue grind for fast in-engine spot-checks (art, battle anims, balance). Mutually
exclusive with the prologue (both host slot 1); the real "Iron Trail" Ch1 at slot 2 is
untouched, and the default `make` (no `TESTCH`) still builds the full prologue→Ch1
campaign. Pairs with the playtest harness as the no-grind path into a fightable chapter.
_Decided: 2026-06-23_

---
