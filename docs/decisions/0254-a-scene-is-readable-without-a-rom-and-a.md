---
id: 254
title: "A scene is readable without a ROM, and a press count is read off the BODY"
date: "2026-08-23"
section: "Operational Gotchas (durable)"
issues: [311]
---

# A scene is readable without a ROM, and a press count is read off the BODY

ch05 authored dialogue at **one scene per session for fifteen sessions**, and #302's measurement
named the cause: verification was a watched GUI run, so the batch size was one scene. Half of
ch05's 102 commits were the session boundary that cadence produced. Yarn Spinner and ink exist
for exactly this — *"play through dialogue without importing into a game"* — and we had no scene
preview at all.

**`make scene SCENE=ch05/1` renders a scene from the chapter YAML: no build, no ROM, no
emulator, ~0.3s.** What makes it trustworthy is that it renders nothing itself. Each chapter
scene is already a pure `chap -> [(msg_id, body)]` builder (`ch05_opening_messages` and its
siblings), so the preview **calls the shipping builder and reads its output back**. A preview
with its own renderer is a preview that can disagree with the ROM, which is worse than none.
The only new logic is the body reader, and it is unit-tested against the traps below.

**The press count is read off the rendered body, and that corrected a claim this repo had
written down twice.** #311's own scope and the postscript above both said *presses == authored
boxes, the wrapper never invents a page break*. It does: `_script_to_message` pages a turn at
two lines, and each page is its own [A]. Measured across ch05's opening —

| scene | authored boxes | A-presses | turns wrapping past two lines |
|---|---|---|---|
| Basil and Sahnar | 19 | **23** | 4 |
| Sephek gives Ravisin her orders | 16 | **18** | 2 |
| Ravisin appraises the blade | 7 | 7 | 0 |

The generalisation came from ONE scene whose every box happened to fit in two lines at 203px
(the Talk recruit, still 16 and 17). **A press count is a fact about the wrap, not about the
script** — so it can only be read where the wrap has happened, which is the body.
