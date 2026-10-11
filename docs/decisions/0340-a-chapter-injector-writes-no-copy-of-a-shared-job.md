---
id: 340
title: "A chapter injector writes no copy of a shared job"
date: "2026-10-10"
section: "Operational Gotchas (durable)"
issues: [479, 302, 27]
---

# A chapter injector writes no copy of a shared job

Nicolas, 2026-10-10: ch07 writes no custom or copied code. It uses the shared helpers.

Each chapter from ch04 on was built by copying the last one, so the same jobs existed once per
chapter under a chapter prefix. `chain_chNN_to_chMM` was 96% identical across three copies, and
`chNN_enemy_rows` across three more. The copies had already drifted. ch04's enemy emitter
honoured per-body `levels:`, but ch05's and ch06's read `level` alone.

**Each job now has one shared helper, and the chapter passes its facts as parameters** (#479):

- **Chaining:** `inject.hosting.chain(src, dst)` makes the chain step. Each step keeps its
  `chain_<src>_to_<dst>` name, which the step facts and tests address.
- **Rosters:** `inject.units.enemy_rows(chap, class_ids, item_ids, pid_for, ...)`, for ch03
  to ch06. Each chapter's rule for which CHARACTER an entry rides is a small `chNN_enemy_pid`,
  and all four now honour per-body `levels:`. ch01 and ch02 still hand-build their rosters
  entry by entry (bespoke comments, `composition:` packs), so a `levels:` split there still
  needs those emitters touched.
- **Locations:** `inject.villages.chapter_location_events`.
- **Frame texts:** `inject.scenes.write_frame_texts` writes the title, both goal texts and the
  title card, for the prologue and ch01-ch06. `inject.text.write_nameplate` renames a borrowed
  boss slot.
- **Event-script shapes in `inject.scenes`:**
  - `backdrop`, at every plain REMOVEPORTRAITS/BACG/FADU site (ch05's moose bellow and the dev
    placeholder in `inject.text` keep their own shapes);
  - `debug_boot_script` and `ending_call`, for the late-beat boots;
  - `gather_cast`, for the closing-scene gather;
  - `record_alive_flags`, for a survivor flag a later chapter reads;
  - `branch_on_flag` and `branch_on_check_exists`, beside `branch_on_check_alive`;
  - `party_camera_tile`.

A chapter keeps a real difference by naming it. `ch06_messie_gather` validates Messie's island
and route, then calls `gather_cast`.

**The guard:** `check_no_chapter_copies_of_shared_jobs` fails on any `chNN_<job>` at the top of
`tools/inject/chapters/*.py` when a shared module defines a public `<job>`. It also fails on any
hand-written `chain_chNN_to_chMM`. On the old tree it named all three `chNN_location_events`
wrappers, both later enemy-row copies, ch05's camera tile and every chain.

**Proof it moved nothing:** the injection fingerprint (#389) over all 15 ROM configurations,
which is every one `fingerprint_reach.py` says the change reaches. Every injected file is
byte-identical except the event-script headers whose comments the shared helpers spell one way,
and those are identical once C comments are stripped.

**Not in scope:** one declarative `inject_chapter` driver. ADR 0308's scope call stands. The
frame is shared, and rosters, scenes and texts stay the chapter's own code.
