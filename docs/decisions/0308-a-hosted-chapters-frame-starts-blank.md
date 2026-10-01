---
id: 308
title: "A hosted chapter's frame starts blank; keeping a donor field is declared"
date: "2026-10-01"
section: "Operational Gotchas (durable)"
issues: [412, 302]
---

# A hosted chapter's frame starts blank; keeping a donor field is declared

A hosted chapter squats a vanilla slot. Its two structs, the `ROMChapterData` row in
`chapter_settings.json` and the `ChapterEventGroup`, used to start as the donor's: any field an
injector did not touch kept vanilla's value. Six shipped bugs had that cause (goal text ids #207,
battle grounds #289, difficulty #303, `.traps` #306, fog #365, and ch02's misc list, which the
#313 census found). The censuses caught the class after the fact. Inheritance was still the
default.

Now `tools/inject/chapter_frame.py` writes both structs from blank:

- **`write_settings_row(chapter, host_index, writes)`** applies the chapter's writes and rules on
  every other field when it runs. A field is written by the chapter, owned by a total pass (fog,
  difficulty, battle grounds), or inherited with a reason in `chapter_data.DECLARED_INHERITED`.
  It refuses a field with none of these, a write to a field another pass owns, and a write to a
  field that still declares a reason to inherit. It does this before anything is written.
  `_retarget_host_chapter` and `inject_prologue` are its two callers.
- **`write_event_group(chapter, info, group, lists, roster, scenes)`** fills the lists the chapter
  names, by struct field. **Every other list is written empty**, never left as the donor's. It
  reads list symbols from the group itself, so no chapter keeps a table of vanilla list names
  (ch05's and ch06's `CHNN_EVENT_LISTS` are gone). It points both difficulties at `roster` and
  the two scene fields at `scenes`. `traps` belongs to `apply_chapter_traps`. The six skirmish
  rosters and `extraTrapsInHard` are inherited with reasons in `event_group.DECLARED_INHERITED`.

Four things follow:

- **The censuses are listings.** `event_group.census` and `chapter_data.census` read the
  declarations, not the bytes, so `make chapter` lists the ruling with no build (the struct's
  field list comes from the vanilla submodule).
- **A writer frames only its own chapter.** Both writers check the slot, group and eventinfo
  header they are handed against `inject/hosts.py`. Framing a copy-pasted neighbour's group
  would otherwise pass every guard while the chapter's real group kept the donor's lists.
- **The build's post-pass guards check two things.** `assert_framed` checks that every injected
  chapter came through both writers. The census guards check that every field the frame left
  inherited still reads as the donor's, pointer and target. A pass that writes an inherited
  field behind the frame's back fails there.
- **The per-chapter inheritances went away.** ch02's misc list and ch06's character list are now
  written: ch02's is the lord rule, and ch06's is empty. The prologue writes its own group id
  and goal block. Only its `prepScreenNumber` is still inherited, because it has no prep screen.
  The goal template's parameters (`windowDataType`, `destPos*`, `protectCharacterIndex`,
  `windowEndTurnNumber`) moved from "inherited" to "written": the frame copies them from the
  goal donor slot.

**Scope.** The frame covers the part every chapter shares, which is also the part whose
default used to be wrong. Rosters, scenes and texts stay in each chapter's own injector. #302's
"collapse `inject_chNN` into a shared driver" is narrowed to this frame. Folding scenes and rosters
into a driver is not planned work: no named change would get cheaper from it, and #302 rules
out re-authoring shipped chapters.

Done-when evidence: `injection_fingerprint` IDENTICAL for the default build (975 files), for
`--test-chapter` (970, where the prologue does not run) and for `--ch06-boot` (967). The boot and
ch05 flags reach scenes only, not the frame.
