---
id: 227
title: "An FEditor `L` is an authoring bracket, not an instruction"
date: "2026-08-08"
section: "Operational Gotchas (durable)"
issues: [25]
---

# An FEditor `L` is an authoring bracket, not an instruction

Sahnar's Specter is the first vendored anim using FEditor's loop syntax — a bare `L` (`LOOPSTART {`)
closed by a `C01` (`LOOPEND }`) — and it crashed `parse_feditor` on `int("L")`. There is no loop
opcode in `banim_code.inc` to emit: vanilla encodes the same shape (frames after
`banim_code_call_spell_anim`, then the wait) as a **flat run**, see `banim_bgl_mg1_motion.s`. So the
`L` is dropped and its paired `C01` does the waiting. It surfaced only because the Specter's two
RANGED modes use it — modes a sword Myrmidon never plays, which is exactly the kind of thing that
would otherwise have sat unparsed until some later unit needed those modes.
