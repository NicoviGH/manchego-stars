---
id: 327
title: "A reskin says where it is worn, and the harness reads the injector's ids"
date: "2026-10-04"
section: "Engine & Tech Stack"
issues: [26, 347]
---

# A reskin says where it is worn, and the harness reads the injector's ids

**A chapter's enemy classes resolve through one helper.** `campaign.yaml` →
`enemy_class_reskins` → `dresses: {chNN: [token]}` says which chapter's tokens a reskin dresses.
`inject.class_ids.ChapterClassIds('chNN')[token]` returns that slot, or the vanilla class
(`armor-knight` → `CLASS_ARMOR_KNIGHT`, checked against vanilla `classes.h`). It replaces six
hand-kept `CHnn_CLASS_IDS` dicts that copied the YAML's slots, so a new reskin is one edit.

The key is (chapter, token), never `base`. Base is many-to-one: goblin-soldier and risen-spear
both clone `CLASS_SOLDIER`, and resolving by base shipped ch01's goblins as ch05's skeletons
(#347). A (chapter, token) that two reskins claim is a build error.

**An appended class id is declared, never allocated.** A save stores each unit's class id.
An id the build assigned on its own would stay unpinned until someone wrote it into the YAML,
and inserting a reskin above it would renumber it and swap classes in playtesters' saves. So
`slot_id` stays in `campaign.yaml`, and `inject.reskins.slot_id_violations` makes it cheap to get
right. A new slot without an id fails the build, and the error names the next free id. Ids that
collide, overlap vanilla's table (which ends at 0x7F), or leave a gap are refused. A gap would
cost dead padding rows in the positional move table.

**A vendored FE-Repo asset records its source, and `fe_repo_vendor.py verify` re-proves it.**
Measured over the tree on 2026-10-04: a battle anim is the mode folder's script plus its numbered
frames, byte for byte (402 of 402 files). A map sprite is the source pair re-encoded, which makes
it pixel-identical rather than byte-identical (8 of 8 pairs). The build re-maps every sheet onto
its base class's palette, so the picture is what has to match. A cast recolour is derived, keeps
its recipe in its unit YAML, and is not in the manifest.

**The playtest harness reads campaign ids from the build, never from literals.**
`gen_symbols.py` already regenerates `symbols.lua` after every `make`. It now also writes:

- `RESKIN_CLASS`: reskin id → the class id the build gave it, read off the build tree's
  `classes.h`.
- `CAMPAIGN`: cast pids (each cast member's `PORTRAIT_MAP` slot, never its stat donor), host
  slots, the lord-select candidate count and flag base, ch02's field chwinga and their YAML
  gifts, and the named pids for ch01-ch06. All of them come from the injector's own constants.

Before this, `harness.lua` and the chapter chunks held 22 top-level hand copies of those
values. Each copy could drift silently. Two had already gone wrong once: the slot-vs-donor
trap that `CAST`'s comments warned about three times, and the chwinga charm list, a hardcoded
copy of which Python had already deleted after #23. Each copy also cost a top-level local in
a chunk at Lua's 200-local ceiling. The harness went from 197 locals to 175.

What stays a Lua literal: engine facts about the GBA or the decomp (struct strides, state
bits), and chapter-chunk coordinates that `check_chapter_lua_facts` already proves against
the YAML.
