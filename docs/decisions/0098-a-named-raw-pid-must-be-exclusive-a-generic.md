---
id: 98
title: "A NAMED raw pid must be exclusive; a GENERIC one need not be"
date: "2026-09-04"
section: "Distribution & Scope"
issues: [26, 364]
---

# A NAMED raw pid must be exclusive; a GENERIC one need not be

Our chapters put units on unnamed `gCharacterData` gaps in the 0xB0 range, and two chapters may
share one of those pids quite legally: ch03's grell and ch04's mogall both ride `0xb7`, because a
`gDefeatTalkList` entry is keyed by **chapter** as well as pid, so each chapter's quote finds its
own unit. ch05 and ch06 likewise both spend `0x80` on autolevelled trash.

Giving a pid a NAME breaks that symmetry, and the reason is structural: `RAW_PID_PORTRAITS` writes
`nameTextId` into `gCharacterData[pid - 1]`, which is **one global row per pid with no chapter
dimension at all**. So a named pid is a campaign-wide claim while a generic one is a per-chapter
one, and the two look identical at the call site — an entry in a dict of hex strings.

ch06's two rescue boats took `0xb4`/`0xb5`, which `CH04_PACK_PIDS` already owned. Two of ch04's
five Mauthe Doogs would have read **"Fishing Boat"** on the unit window. Nothing would have caught
it: `assert_pack_pids_addressable` checks that ch04's pack is addressable *within ch04*, and the
0xB0-range occupancy lived as prose in three separate comments, none of which was complete — the
one that mattered enumerated `0xB6..0xB9` and did not know about ch04's five.

**The prose was the bug, so prose is not the fix.** `assert_named_raw_pids_are_exclusive`
DISCOVERS every raw pid the module claims — string, tuple and dict constants alike, matched on
`CHNN_*PID`/`PIDS` — and fails the build when a named pid is claimed by two chapters, while
deliberately permitting a shared generic one. **0xB0..0xBA is FULL**; the next unnamed gaps are
`0xbb`/`0xbc`/`0xbd` (`nameTextId` 0x255, the generic monster plate).

_Decided: 2026-09-04 (Claude, hosting ch06) — found by `/code-review` on #364._
