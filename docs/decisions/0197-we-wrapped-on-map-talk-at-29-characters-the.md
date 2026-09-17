---
id: 197
title: "We wrapped on-map talk at 29 CHARACTERS; the engine measures PIXELS"
date: "2026-08-21"
section: "Operational Gotchas (durable)"
issues: []
---

# We wrapped on-map talk at 29 CHARACTERS; the engine measures PIXELS

`_wrap_fe_lines`' default was 29, and its docstring derived that from vanilla: *"MSG_910/911 top
out at 29 chars"*. Both halves are true and the conclusion does not follow — **`MSG_910` is simply
a narrow message**, and the rule generalised one short sample into a ceiling.

**The engine never counts characters.** `StartTalkExt` (scene.c:403) sets
`activeWidth = Div(GetStrTalkLen(str, 0) + 7, 8) + 2` — `GetStrTalkLen` accumulates
`glyph->width` **in pixels** (`fontgrp.c` → `GetStringTextLenASCII`), and the `/8 + 2` converts to
tiles plus the bubble border. The talk font is **variable-width**: measured out of `TextGlyphs_Talk`
in the built ROM, `i` is 2px, `.` is 2px, space is 4px, `a` and `m` are 6px, `W` is 8px. A
29-character line can be anywhere from ~60px to ~230px, so a character count is not a conservative
proxy — it is an unrelated quantity that happens to correlate.

Measured, in this exact channel (on-map `TEXTSHOW`, widest DRAWN line):

| | widest line | |
|---|---|---|
| `MSG_9CC` — vanilla's Natasha→Joshua Talk, the scene ch05's Talk is the twin of | **203px** (43 ch) | |
| `MSG_9C3` — vanilla, same channel | 182px (39 ch) | |
| `MSG_910` — the message the 29 rule was read off | 140px (29 ch) | the narrow sample |
| ch05's Talk recruit, ours | **132px** (29 ch) | **65% of vanilla's** |

**So there is no tradeoff to weigh, which was the question.** Vanilla ships 203px lines in the
same window, from the same podiums, and 203px + the 2-tile border is 219px against a 240px screen.
Wrapping at 29 characters buys nothing and costs A-presses: re-flowing ch05's authored dialogue at
vanilla's own budget saves **27 of 152 presses (18%)** without touching one word or one authored
break.

The budget is per-PODIUM in principle — the bubble anchors at `gTalkFaceHPosLut` and is clamped to
[0,30] tiles — but vanilla's 203px line sits on `[OpenMidRight]`, which is exactly where ours sit,
so the comparison is like-for-like rather than a hope.

**HOW THE ROLLOUT MUST BE GATED, learned the hard way.** Changing the wrapper means changing
every call site of a function whose parameter CHANGED UNITS, and a regex sweep over those sites
broke three things the 546 unit tests all passed through:

- it stripped `width=` from function DEFINITIONS as well as calls, so their bodies referenced an
  undefined name;
- it missed a POSITIONAL `29`, and ch05's moose scene silently re-wrapped to seven characters
  a line;
- it flattened two sites that are **not the talk window at all** — the lord-select CARD (a fixed
  20-column panel drawn by our own generated `LordSelect_DrawCard` through its own font) and
  ch03's faceless narration beats (the auto-centered `SOLOTEXTBOXSTART` box, `helpbox.c`).
  Those keep character widths and now pass `measure=len`, because the talk font's glyph widths
  do not describe either renderer and extending a measurement past what it measured is how the
  29 rule got made in the first place.

None of that was caught by tests. What caught all three was **rendering every message body under
the old code and the new and diffing them**: 3404 messages, and the invariants are that no body
loses a WORD and — for a widening — no body costs MORE A-presses. That diff is the gate for any
future wrap change; run it before the test suite, not after. Result here: 86 bodies re-wrapped,
0 words moved, 0 bodies more expensive, **60 fewer A-presses campaign-wide**.

_Answered: 2026-08-21 (Nicolas: "I really don't understand if there's a tradeoff which is why I
keep pointing to vanilla as reference. Do you really need my input for this?" — no, and this is
what the reference says)._
