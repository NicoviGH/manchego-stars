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
4. **Vanilla pacing benchmark** for the slot being written — run
   **`python3 tools/vanilla_scene.py <ch> [SceneFragment]`** to print the twin's scenes as
   boxed dialogue with box counts (decomp `src/events/*-eventscript.h` + `texts/texts.txt`).
   **A chapter's messages live in TWO places and TWO channels — check both, or you will
   conclude vanilla lacks a beat it has:**
   - `*-eventscript.h` carries the scenes, in **two channels**: `TEXTSHOW` (on-map, units
     staged by `LOAD1`, the bubble's budget is **203px**) and `Text_BG(BG_*, id)` (a still
     backdrop, auto-centred helpbox, **192px**). The channel sets the width you hand-box to, and vanilla uses
     the backdrop for scenes that happen ELSEWHERE (Ch5's Grado command scenes) — so it also
     tells you where a scene is set. `vanilla_scene.py` prints id + channel per message
     (regression-guarded by `tools/test_vanilla_scene.py`; it once matched `TEXTSHOW` only
     and hid Ch5's two backdrop scenes, under-reporting an 11-message opening as 8).
   - `data_battlequotes.c` carries the **boss taunt, boss death quote, and any
     chapter-specific unit death quote** — these are NOT in the eventscript at all. Ch5's
     `0x9C6`/`0x9C7`/`0x9C8` live here, and `0x9C6` is the ESCORT's death quote, which is
     easy to mistake for a scene id. Grep both files before claiming an id is unused.
   - **If a mined beat looks absent, suspect the miner before concluding vanilla lacks it.**
   Measured budgets + where our chapters sit: **`references/scene-pacing.md`**. Headline:
   vanilla spends **45–100 boxes** on an opening/ending cutscene but keeps a **mid-battle
   escalation to ~3 boxes** — story goes in the bookend scenes, in-map beats are a punch.
   **Writing a VILLAIN? Read `references/fe8-register.md` first** — the FE8 script's own
   villain habits distilled from that corpus (direct address + insult-names, relish, dark
   irony, theatrical announcement, `...` pacing) with verbatim calibration quotes and an
   archetype table to check a new villain against so ours don't converge. Ground the voice
   in what the game shipped; don't invent a register.
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

0. **MANDATORY FIRST — mine the corpus, then write. Never draft from instinct.**
   Read **`references/natural-speech.md`** and do its Step 0: find the vanilla scene that
   already solves this scene's problem (`python3 tools/vanilla_scene.py <ch> [Fragment]`), and
   for a two-hander find the *relationship* twin among FE8's ~217 two-character scenes — the
   supports. ch05's 9BB burned a dozen drafts writing from instinct; two Ewan/Saleh supports
   fixed it in one pass. Skipping this step is what produces stilted dialogue, every time.
1. Bring **2–3 variant lines** per beat. Label what each variant trades off
   (e.g. "menace vs. brevity"). Nicolas picks or mixes; he owns voice.
2. **Draft BOXED, never as prose** (2026-07-23 learning — prose-length lines read as
   wordy and hide the real A-press pacing). Write every line as GBA boxes from the first
   pass: **2 lines per box**, measured in PIXELS not characters (#298 — 203px talk bubble,
   192px helpbox, 143px battle bubble; `tools/fe8_talk_font.py` owns the three budgets and
   `make scene` renders the real wrap), `...` holds, `--` interrupts — and show it *boxed*
   to Nicolas, not as paragraphs. Stay inside the budget: boss taunt ≤ 4 lines / 1 screen;
   opening exchange ≤ ~8 boxes; ending beat ≤ ~10 lines; narration card 2–5 lines ≤ ~25
   words; quote msgs 1–2 lines. Cut before adding.
3. Check every line against the speaker's banned list and calibration samples.
4. Lock a beat before moving to the next; record locked text in the chapter YAML
   (or issue #43 for montage slots that lack wiring). **Then update the chapter's GitHub
   tracker in the same breath** — the issue comment that lists which beats are written and
   what's next, plus the PR description if it has drifted. Do not wait to be asked: a stale
   tracker is how the handoff gets heavy and how Nicolas loses sight of what's in flight.

## Craft check (run on every draft AND every review pass)

Compliance isn't quality — a line can pass every budget and banned list and still be
flat. Judge the writing itself, and grade honestly: "functional" is a finding, not a
pass.

**Hard rule — NO CONTRASTING CLICHÉS (2026-07-23, Nicolas).** Never build a line on the
"not [X], but [Y]" / "not just [X], rather [Y]" formula, a false dichotomy, or a then/now
antithesis; never define something by first saying what it is *not*. **State what IS,
directly.** Offenders that got cut from ch05: *"That's not life. It's fever."* · *"I don't
kill. I cleanse."* · *"You grew things once… now nothing grows."* · *"They feed me. You never
did."* This is a TIC, not a style — once it's in your ear every character starts sounding
identical, and it was the single biggest cause of flat ch05 dialogue. **But do not
over-correct into flat declaratives either:** a scene of same-temperature statements reads as
monotone (a calm-Ravisin pass was rejected as "where did all the interesting go"). Vary
rhythm and heat; let lines surprise.

**Epigram disease (2026-07-23 — the single most common failure).** If every line is a polished
artifact that lands one beat and hands off, the scene reads as poetry, not talk. **Vanilla is
redundant and inefficient and that is why it sounds human** — characters apologise twice, say
the same thing four ways, interrupt themselves. Turns are LOPSIDED (two words answered by
forty), the eager character RUNS ON, and feelings are stated PLAINLY rather than buried in
subtext. Full diagnosis + the corpus-mining method: **`references/natural-speech.md`**.

**The master test (2026-07-23 learning — this is what fixed "dry"): people talking, not
mood-narration.** A line that *describes the atmosphere* ("she wakes the sad things,"
"nothing walks back out") is dead, however evocative. Every box is a PERSON — reacting,
joking, needling, asking — never the scene narrating itself. The dread rides in on a
concrete, in-character line (Basil *cheerfully*: "She sings to the dead ones. …I grow her
berries."), not portentous grimdark. If a line could be a stage direction, cut it. Then the
finer checks, in order of weight:

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
  (dedupe identical frames, ~83ms/frame, 2x nearest-neighbor), commit them in
  `docs/demo/` on the feature branch, and show the GitHub PR. Static screenshots
  mislead -- they catch the typewriter mid-stroke. Once the feature is accepted,
  remove the review artifact before merge unless a live document links to it.
- Message-encoding gotchas (the hard-won ones, full trace in
  `tools/build_campaign.py` `_script_to_message`): a line's budget is PIXELS —
  203px on-map, NOT the helpbox's 192px — so character counts are not the measure; every non-terminal [A] must be [LF]-followed
  (the width measure doesn't stop at [A], and right-side bubbles have no
  position clamp -- merged turns = offscreen bubble); a boss "steps out" via a
  message SPLIT + LOAD1 between, never a lazy right-face load mid-message.
