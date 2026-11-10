# AGENTS.md — Manchego Stars

Manchego Stars is a GBA tactics ROM hack of *Fire Emblem: The Sacred Stones* (FE8), built from the `fireemblem8u` C decompilation. It turns a completed D&D 5e *Rime of the Frostmaiden* campaign into a playable tactics game: 8 player characters become FE units (FE8 classes, FE8 stats), and the campaign's narrative chapters become FE maps. **Combat is vanilla FE8 — FE hit/avoid/might/crit, FE stats, no conversion.** D&D is flavor; the d20 survives only as a cosmetic nat-20 animation on FE's own crits. Distribution is private — a pre-patched ROM sent to the campaign players.

This file is loaded into every session, so it holds operating rules and pointers only; the why
and the history live in `docs/decisions.md`.

## Source of Truth

The data is the doc — facts live in one place, indexes are generated (`decisions.md` §Documentation Model):

| For… | Look at… |
|---|---|
| Per-chapter facts | `campaigns/rime-of-the-frostmaiden/chapters/ch*.yaml` → generated `docs/CHAPTERS.md` |
| Unit class / promotion | `campaigns/.../{pcs,npcs}/*.yaml` → generated `docs/CLASSES.md` |
| Settled design decisions | `docs/decisions.md` |
| Generic 5e→FE engine conversion | `docs/rules-mapping.md` |
| A playtest-bot decision (planner, candidates, lookahead) | **ADR 0396**: a decision orders the game's outcomes, only the game forbids; the five tests every new rule passes |
| A unit's art / battle anim / platform | `inject_battle_anims` / `inject_battle_platforms` docstrings (how) + `decisions.md` Art & Audio (why) + the `custom_unit` issue template |
| Borrowable enemy reskin art | `docs/fe-repo-scouting.md` + per-unit `skin:` in chapter YAML + `campaign.yaml` `enemy_class_reskins` |
| Hosting a new chapter | `docs/adding-a-chapter.md` (runbook; shared-helper table, ADR 0340) |
| A playtest scenario's needs | Declared in the chapter YAML under `playtest:` (`tools/playtest/declared.py`, #314); everything a chapter does not own stays in `tools/playtest/matrix.yaml`. A name in both RAISES. |
| Prep screen / deploy cap | `decisions.md` → "How the deploy cap + prep screen are actually wired" + `inject_ch01`'s docstring. **Prep from ch01 on is standing protocol; the CAP is the parity. Never re-derive it from the decomp or from `hasPrepScreen` (dead FE7 field).** |
| FE8 cadence/reward grounding | `docs/fe8-pacing-reference.md` |
| How players play vanilla; playtesting research | `docs/research.md` (generated index of `docs/research/`) — evidence, never a decision |
| The back half (ch09–ch20) | `status: planned` chapter YAMLs via the wiki (`tools/gen_wiki.py`); `docs/roadmap.md` |
| Vision / roadmap | `docs/PRD.md` |
| Backlog | GitHub issues (milestones M0–M4); current state → `HANDOFF.md` |

## The decomp answers "what does vanilla do," never "what do WE do"

For our own conventions (prep, caps, objectives, economy, class mapping, art) **read
`docs/decisions.md` and cite the ADR**; vanilla's data knows nothing of what we diverged on. If
`decisions.md` is silent, ask — don't infer from the ROM.

## Session Start Checklist

1. `AGENTS.md` (this file)
2. **`git show main:HANDOFF.md`** — main's copy, never the working tree's (a branch carries a stale snapshot).
3. `docs/decisions.md` — the INDEX; open only the two or three records your task needs. Don't re-litigate.
4. The chapter or feature YAML/source being worked on
5. `git status` + `git log --oneline -10`

> **Playtest runs are the most expensive thing in this repo.**
> Never run the full `make matrix` gate locally; run only scenarios your change could affect;
> never run anything after a merge; on a failure spend **one instrumented run** covering your
> next three hypotheses, not one run per guess.

## Searching and context

- 86% of the files are the `fireemblem8u` submodule. Search our code with
  `rg <pat> -g '!fireemblem8u'`; search the decomp only on purpose, and say so. Never read a
  decomp source whole (`inject.decomp.vanilla_decomp_text` reads them at HEAD, memoised).
- Context is the budget: cost is `size × remaining calls` (`decisions/` → "Context is the
  budget…"). `/handoff` at task boundaries, `/clear` on switches, don't idle a session past the
  cache's hour, prefer `sed -n`/`grep` to whole-file reads, redirect big output to a file.

## Key File Locations

| What | Where |
|---|---|
| Source assets (base ROM, anims, books) | `references/` — gitignored link to `~/Projects/manchego-stars-assets` (copyrighted, never committed) |
| Base ROM | `references/Fire Emblem - The Sacred Stones (USA, Australia).gba` |
| Reference PDFs | `references/References/` (frostmaiden-resources.md also in `docs/`) |
| *Rime of the Frostmaiden*, searchable | `references/References/rime-of-the-frostmaiden-ocr.txt` — OCR of the scanned PDF, one `===== PDF page N (printed p.N-1) =====` header per page; grep it |
| PC sheets / portraits | `data/pc-sheets/*.json`, `data/pc-sheets/portraits.json` |
| FE8 decomp | `fireemblem8u/` (submodule, stays vanilla) |
| Engine changes | `engine/patches/` (applied by `tools/inject/engine_patches.py`) |
| Campaign data | `campaigns/rime-of-the-frostmaiden/` |

## Build

```sh
make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba -j$(nproc)
```

Base-ROM check: `cd fireemblem8u && ./scripts/quickstart.sh --rom "../references/Fire Emblem - The Sacred Stones (USA, Australia).gba"`.
**`make` must be green at the end of every session. Never commit a broken build.**

## Coding Conventions

- Decomp C style, GCC 2.95.1 / `agbcc`: no C99 (no VLAs, no `//` in new C files, no designated
  initializers), no `stdint.h` types (use `u8`…`s32`), match `fireemblem8u/src/` naming.
- New engine behavior ships as a patch in `engine/patches/` (`git apply`; `engine_patches.py` says
  how to edit one), never a hand-edit to the decomp. The injector writes `build/fireemblem8u` (#408).
- Before changing a signature or a parameter's meaning: `tools/callsites.py`, then diff the output.
- Comments say **why**. When a change retires a mechanism or term, register its phrases in
  `tools/check.py` `DEAD_CONCEPTS` in the same commit ("Comments are testimony").

## Engine / Content Boundary Rule

> **If it references a character name, chapter number, or plot event, it goes in YAML, not C.**

Engine code (`engine/`, `fireemblem8u/src/`) is campaign-agnostic; campaign data is injected by
`tools/build_campaign.py`. `check.py check_engine_campaign_agnostic` rejects a campaign character
id in engine sources; chapter numbers and plot events are a review call.

## Coordination: feature-flow (one feature, one branch, one PR)

- Task = GitHub issue → `feat/<n>-slug` branch cut from `origin/main` → PR → CI + `/code-review`
  → squash-merge → delete the branch.
- Agent teams only for a named reason (ADR 0393).
- **Merge only on CI for the PR's HEAD commit**: wait on
  `gh run list --branch <b> --json headSha,status` until both workflows for the head sha
  complete (`gh pr checks --watch` can return before runs register).
- **Review is `/code-review`; the author never reviews.** `superpowers:requesting-code-review`
  only for a stack (one fresh reviewer per PR, down the stack) or context the diff can't carry.
  For mechanical changes proven unchanged by a machine gate, review the hand-written surface only.
- **Say the review level every time: `/code-review <PR> medium`** (a bare run reuses the last
  level). Never change `effortLevel` in `~/.claude/settings.json` for a review — it is global.
- **A stack lands with `--merge`**, and every child is retargeted to `main`
  (`gh pr edit <child> --base main`) BEFORE the parent's branch is deleted.
- **One checkout, one writer** (ADR 0390): no worktree without Nicolas's say-so, never two ROM
  builds in one tree.
- Keep the gitignored `.agents/`, `map-review/`, `review/` folders; stage paths explicitly.
  `.agents/skills` links to `.claude/skills` for Codex, which works here between Claude sessions
  and leaves a HANDOFF entry (changes, branch/PR, verification, next step).
- Pre-commit runs `tools/check.py` and only the unit tests a staged path reaches (ADR 0394);
  `make check`, `make test` and CI run them all.
- The engine/content invariant and the patch series (applies whole or fails) are hard gates;
  desk ownership (`check_lane_ownership`) is advisory.
- Never commit the `fireemblem8u` submodule pointer.

## Standing rules (Nicolas)

Where each came from: #588, comment 6752993507. Each is a correction he made: apply it, don't
re-ask.

- **Name the game Manchego Stars** (vs vanilla) in prose: chat, issues, commits, docs, comments.
  `ours` is only the code's game id, in backticks (`check.py check_prose_names_manchego_stars`).
- **Findings and an issue's status live on the GitHub issue**; HANDOFF only points at them. On
  hold is the `on-hold` label plus ONE comment saying why and what reopens it.
- **No design docs.** A design or plan is ONE comment on its issue, edited in place; the body
  links to it, nothing copies it, and the PR records the settled call as an ADR. This overrides
  the brainstorming skill's spec file.
- **Never make tests, the parity read or CI slower** without fixing the cost in the same PR;
  report before/after timings, base and branch timed back to back with `uptime` and CPU time.
- **No loose threads.** Before a handoff, prove every "unproven" or "assumed" claim (decomp
  citation, probe, test) or turn it into a guard that fails loudly; a docstring caveat is not
  enough.
- **Run the proof a change needs without asking.** The run-cost rule forbids pointless runs, not
  proof; never ask for a run budget, nor for the obvious application of a standing rule.
- **#510's north star is a trustworthy difficulty model.** Recommend and act; test each call by
  whether it makes the bot's reading more trustworthy; say so before a rabbit hole if you
  disagree.
- **No tidy design rules.** Don't turn a pattern from a few drafts into a principle; test it
  against vanilla's own units first, and frame design by the role a unit fills.
- **The planned chapters after ch07 are drafts.** Cite their `joins_roles`, twins and chapter
  count as "the current draft says", never as constraints.
- **No table record past Revel's End (ch08).** The book and vanilla FE8 are both inspiration and
  the best story wins: "the book doesn't have it" rules nothing out; say which parts are
  invented.

## Design placement test

Push each line to the desk that owns it; talk over interfaces; judge a boundary by the *named*
future changes it makes cheap (`decisions.md` → "A CHAPTER costs local slots").
**A change that reaches into another desk's cabinet or scatters one decision across desks is
rejected in review.**

## Definition of Done

Every change (`decisions.md` → Working Conventions):
- ships its doc + YAML updates in the same commit;
- says `Closes #N` when it completes tracked work;
- builds `make` green, and passes `python3 tools/verify_text.py` after any text change;
- records a new non-obvious decision in `docs/decisions.md` (dated).

Don't restate a fact that lives elsewhere — link to it.

## Tools

Each tool's docstring is its manual; this table only says when to reach for it.

| Tool | Use it to… |
|---|---|
| `tools/build_campaign.py` | inject campaign content into the decomp before `make` |
| `tools/verify_text.py` | decode the built ROM's message text (regression gate, no mGBA) |
| `make scene SCENE=chNN[/<n>]` | preview a scene's wrapping and staging from YAML, no build (#311); `docs/scenes/` is the diffed book. Authoring loop only — a scene still gets one real run. |
| `make chapter [CH=chNN]` | get oriented on a chapter: declared vs built, scenes, art, enemy AI donors, scenario verdicts (#312). Prefer it to HANDOFF prose. |
| `tools/playtest/run.sh <scenario>` | run ONE in-emulator scenario (rows from `matrix.yaml`) |
| `tools/playtest/inspect_state.py` | `render` a playtest log, or `diff` two runs to the first divergence |
| `tools/playtest/montecarlo.py` | the difficulty instrument (#510 step 9): `suite` (the frozen suite; a bot change's promotion), `starts`/`pilot`/`cell`/`report` (a chapter's Manchego Stars-vs-vanilla verdict), `attempts`, `story`/`audit`/`replay` (one run's trace, a failure's witness). Why: ADRs 0384 (SC-003's budget), 0385, 0388, 0392, 0395 |
| `make matrix [SUITE=…]` | the regression matrix, with a verdict cache (`--dry-run` is free). While working: the smallest covering set (`--scenarios a,b,c`). Before a merge: `SUITE=gate`. Before a build for the group: `SUITE=all`. |
| `make verdict-diff [BASE=ref]` | every chapter's parity verdict, base vs this tree (ADR 0353; CI comments when a cell moves) |
| `tools/gen_wiki.py` | the chapter wiki (#486, ADR 0347; CI deploys main's) |
| `tools/portrait_tool.py`, `tools/ref_to_bust.py` | bust art pipeline |
| `tools/build_mgba_headless.sh` | one-time headless mGBA build so `kind: verdict` scenarios run windowless (`PT_HEADED=1` forces a window) |
| `tools/setup-toolchain.sh` | one-time macOS toolchain setup |
