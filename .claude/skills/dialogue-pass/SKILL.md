---
name: dialogue-pass
description: Co-write FE8 cutscene/quote dialogue for a Manchego Stars chapter with Nicolas — voice-bible-grounded, variant-based, vanilla-paced. Use when writing or revising any story text (cutscenes, battle quotes, narration cards, lore crawl, tour text).
---

# Dialogue Pass — collaborative chapter writing

Process distilled from the FE hack community ("every sentence spoken should have a
purpose"; GBA boxes show 2 lines — pace in A-presses), DM practice (voice flows from a
character document), and evaluated human-AI co-writing workflows (hierarchical: bible →
beats → lines, human curates every level). Decided 2026-06-09 (docs/decisions.md).

## Inputs (read FIRST, in order)

1. **Sources of truth:** the Frostmaiden book pages for the scene (PDF page = printed+1)
   and the DM-notes PDF — never invent what they already answer.
2. **Voice bibles:** `campaigns/rime-of-the-frostmaiden/lore/<speaker>.md` (§Voice:
   diction rules, calibration lines, banned list) and `lore/narration.md` for cards.
   If a speaker has no Voice section yet, write it (with Nicolas) before their lines.
3. **Beat outline:** the chapter YAML `events:` descriptions. If beats aren't settled,
   settle them with Nicolas before drafting any line.
4. **Vanilla pacing benchmark** for the slot being written (decomp,
   `fireemblem8u/src/events/*-eventscript.h` + `texts/texts.txt`).

## Drafting loop (per beat, WITH Nicolas — never solo)

1. Bring **2–3 variant lines** per beat. Label what each variant trades off
   (e.g. "menace vs. brevity"). Nicolas picks or mixes; he owns voice.
2. Stay inside the budget: boss taunt ≤ 4 lines / 1 screen; opening exchange ≤ ~8
   boxes; ending beat ≤ ~10 lines; narration card 2–5 lines ≤ ~25 words; quote msgs
   1–2 lines. Cut before adding.
3. Check every line against the speaker's banned list and calibration samples.
4. Lock a beat before moving to the next; record locked text in the chapter YAML
   (or issue #43 for montage slots that lack wiring).

## Craft check (run on every draft AND every review pass)

Compliance isn't quality — a line can pass every budget and banned list and still be
flat. Judge the writing itself, and grade honestly: "functional" is a finding, not a
pass. Checks, in order of weight:

1. **Cover-the-name test** — could only THIS speaker say it this way? A line any
   soldier/narrator could deliver is a flag, even if it breaks no rule.
2. **Job test** — every line advances, reveals, or lands. A box that only restates
   gets cut, not polished.
3. **Box button** — each A-press ends on a hook, a turn, or a punch; never on
   mid-thought filler. The scene's LAST line before gameplay should be quotable.
4. **Concrete over abstract** — trades, tools, weather. "A glassblower" beats
   "a victim"; "seems forthcoming" is the kind of limp abstraction to hunt.
5. **Device budget** — one rhetorical device (tricolon, anaphora, echo) per speaker
   per scene reads as voice; the same device twice reads as a tic. Spot repeats.
6. **Read-aloud test** — speech rhythm; contractions wherever the character allows.

Craft findings on LOCKED text don't silently reopen it: bring the flag + 2–3
alternative lines, Nicolas decides whether the lock reopens.

## Insertion & gates (after lines are locked)

- Text goes in `texts/texts.txt` via `set_message_body` in `tools/build_campaign.py`;
  msg ids read from the decomp, never hardcoded.
- Odd-length names/strings: pad with `[.]` so the `0x00` terminator stands alone
  (terminator-parity bug).
- `make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba` green, then
  `python3 tools/verify_text.py` (0 runaway).
- In-game eyeball of at least one scene with Nicolas (portraits + pacing read
  differently in-engine). Show before committing; wait for his OK.
