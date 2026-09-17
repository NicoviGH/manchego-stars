---
id: 255
title: "Three traps the reader had to be taught, each of which renders a plausible wrong scene:"
date: "2026-08-23"
section: "Operational Gotchas (durable)"
issues: []
---

# Three traps the reader had to be taught, each of which renders a plausible wrong scene:

1. **`[A][LF]` is the page break, not a line.** Read naively, that trailing `[LF]` opens the
   next box with a blank first line, and every long turn in the campaign previews with a
   phantom blank. The first throwaway spike did exactly this.
2. **A faceless speaker emits NO `[OpenX]`,** on purpose — opening one anchors the window to an
   absent portrait's mouth. So the last podium the reader saw still belongs to the PREVIOUS
   speaker, and carrying it forward captions the campaign's narration with whoever spoke before
   it.
3. **A face tag names the vanilla SLOT, not the character.** Unmapped, ch05's opening previews
   as a conversation between "Artur" and "Marisa".

**The golden master is a generated doc, not a new framework.** `docs/scenes/ch05.md` holds every
registered scene, `--write` regenerates it, and `tools/test_scene_preview.py` regenerates it in
memory and diffs — which is precisely the shape `check_generated_indexes_fresh` already uses for
`docs/CHAPTERS.md`. Approve once, diff forever (Feathers/Falco); box rendering is deterministic,
so a scene verified once stays verified for free. Proved rather than asserted: moving the talk
budget by **one pixel** fails the gate on 34 lines and flags Sephek's 203px line as over. It is
also fenced markdown, so the chapter's dialogue is readable on a phone on GitHub.

**Coverage is ch05 only, and that is the decision.** ch01–ch04 render their scenes INLINE inside
their injectors, so covering them means extracting those call sites into pure builders — real
surgery on a 13,901-line file whose only honest gate would be the very output diff this tool
provides. The constraint #302 named is authoring cost GOING FORWARD; ch06 gets the preview
either way. The extraction is a separate change with its own diff gate, if it is ever worth it.

**The boundary: preview replaces the AUTHORING loop, never the proof.** A scene still gets one
real run before it ships. The point is one run instead of one run per iteration.

_Decided: 2026-08-23. Proof: 19 unit tests; a 1px budget change moves 34 golden lines; the
committed book matches what the YAML renders today._

---
