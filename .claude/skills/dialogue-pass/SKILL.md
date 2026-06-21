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
   For MINOR/incidental NPCs (house visits, villagers, shopkeepers): use
   `lore/npc-bench.md` — setting-true name bank, one voice texture + one quirk each,
   Dale occupations, four drop-in pre-gens, and real inter-town travel times for
   pacing claims. Minor NPCs never get a full bible.
3. **Beat outline:** the chapter YAML `events:` descriptions. If beats aren't settled,
   settle them with Nicolas before drafting any line.
4. **Vanilla pacing benchmark** for the slot being written (decomp,
   `fireemblem8u/src/events/*-eventscript.h` + `texts/texts.txt`).
5. **Onboarding catalog + coverage:** `docs/ONBOARDING.md` (generated) +
   `campaigns/.../onboarding-catalog.yaml` (what vanilla teaches, the channel, the decomp
   citation) and the prior chapters' `introduces:` ledger — for the tutorial-parity check below.

## Tutorial-parity check (run when settling a chapter's beats)

Combat is vanilla-strict, so this is about **timing**, not new mechanics: whenever a concept
first becomes relevant in *our* chapter order, our players must get the same heads-up a vanilla
player gets — vanilla weaves it into BOTH flag-gated tutorial boxes AND mandatory story dialogue
(a veteran who declines the tutorial still sees the dialogue half). Rewriting cutscenes can
silently strip it. So, before locking beats:

1. List the mechanics/unit-types this chapter introduces (new enemy class, flier, fog, monster,
   siege, thief, status, terrain gimmick…). For each, check the prior chapters' `introduces:`
   ledger: is this its **first** campaign appearance?
2. For each first, look it up in the catalog. If vanilla teaches it (and where/which channel),
   we owe an equivalent heads-up here — flag it to Nicolas: *"first monsters appear here; vanilla
   has a character call it out — we should too."* Pick the channel per the C-hybrid: a vanilla
   box for dry systemic lessons (triangle, terrain), in-voice dialogue for threats/narrative ones.
3. Record the decision as an `introduces:` entry on the chapter YAML (`concept`, `coverage`,
   `where`, `status`), then `python3 tools/gen_onboarding_index.py` (freshness +
   orphan/double-debut integrity are gated by `tools/test_onboarding.py`). A concept debuts once.

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
- In-game review with Nicolas as MOTION, not stills (decided 2026-06-10): run
  `tools/playtest/run.sh record`, assemble the captured frames into GIFs
  (dedupe identical frames, ~83ms/frame, 2x nearest-neighbor), drop them in
  `map-review/`, and `open -a Safari` them (Preview paginates GIFs). Static
  screenshots mislead -- they catch the typewriter mid-stroke. Show before
  committing; wait for his OK.
- Message-encoding gotchas (the hard-won ones, full trace in
  `tools/build_campaign.py` `_script_to_message`): on-map bubble lines wrap at
  29 chars, NOT Text_BG's ~42; every non-terminal [A] must be [LF]-followed
  (the width measure doesn't stop at [A], and right-side bubbles have no
  position clamp -- merged turns = offscreen bubble); a boss "steps out" via a
  message SPLIT + LOAD1 between, never a lazy right-face load mid-message.

## Close the loop (after the dialogue lands)

Locked dialogue is usually the LAST gating item on a chapter's tracking issue,
so finishing it often *completes* that issue -- the moment to close it, not
later. Skipping this is exactly how #20 (Prologue) sat open for eleven days
after its dialogue shipped in a Ch2-focused commit that never said `Closes #20`.

- Check the chapter's tracking issue (`#2x`): does this dialogue complete its
  remaining checklist? If yes, the commit that lands the text says **`Closes #N`**
  (Definition of Done, `docs/decisions.md` -> Working Conventions). If the
  chapter still needs hosting/placement, say `Refs #N` and leave it open.
- If the dialogue is incidental to a *different* chapter's commit (the #20
  failure mode), still tick/close the issue it actually finishes -- don't let
  the commit's headline subject decide which issue gets reconciled.
