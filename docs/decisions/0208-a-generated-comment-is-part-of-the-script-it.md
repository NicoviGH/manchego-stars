---
id: 208
title: "A GENERATED COMMENT is part of the script it describes"
date: "2026-08-14"
section: "Operational Gotchas (durable)"
issues: [25]
---

# A GENERATED COMMENT is part of the script it describes

Four tests broke in one session because an emitted `/* ... */` mentioned the command it was
explaining — `TEXTCONT`, `CAMERA`, `FADI/FADU`, `MUSI/MUNO`. The tests grep the GENERATED event
script, and a comment lives in that script exactly as an instruction does.

**Describe the command; never name it, inside a string that gets emitted.** This is the sibling of
"Comments are testimony" (which is about comments going STALE): that one says a wrong comment
misleads a reader, this one says a comment can break a test without misleading anybody.

_Recorded: 2026-08-14 (migrated out of HANDOFF 2026-08-20)._
