# Handoff — Content track 🔒 (instance A)

Live state for the **content instance**. The parallel-work model is the ADR in
`docs/decisions.md` (§Delivery model → Parallel work model / Engine-content file seam) and the
work tracker is #50; the backlog is **GitHub issues** (#49 ① Content track), not this file.
Don't clobber the pipeline track's `HANDOFF-pipeline.md`.

## Start here (fresh instance — do this first)
You are the **Content-track** instance for Manchego Stars (trunk-based, your own worktree).
1. **Work in the content worktree, never on `main`.** It already exists at `../ms-content` on branch
   `inst/content` — `cd ../ms-content` and confirm with `git rev-parse --abbrev-ref HEAD`. Only if it's
   missing, bootstrap it: `tools/worktree-setup.sh ../ms-content` (creates the worktree + symlinks the
   toolchain), then `cd ../ms-content`.
2. Read `CLAUDE.md` and `docs/decisions.md`, then continue from **Next** below.
3. Trunk-based: small commits, `git pull --rebase origin main` often, push when green, no
   long-lived branches, never commit the `fireemblem8u` submodule pointer.

## You own (edit freely)
- `campaigns/rime-of-the-frostmaiden/**` — chapter YAMLs, pcs/npcs/enemies YAML, dialogue
- `tools/build_campaign.py` — the `inject_*` content functions + the 6 sprite/palette hooks
- `tools/portrait_tool.py`, `tools/map_sprite_tool.py`, `tools/ref_to_bust.py` (art pipeline)
- `docs/` story/chapter/art docs

## Hands off (pipeline track owns — coordinate via an issue if you need a change)
- `tools/inject/engine_hooks.py`, `tools/inject/decomp.py` (shared — propose changes, don't fork)
- `tools/difficulty.py`, `tools/fe_combat.py`, `tools/check.py`, `tools/playtest/**`, CI

## Last session (2026-06-19, pm)
**Ch2 rear-ambush beat drafted (not locked) + a Ch2/Ch1 drift bug surfaced.** Ran the
`dialogue-pass` prep for `ch02-rear-ambush` (read the Wolfram/Braulo/RBG §Voice bibles + the FE8
reinforcement-bark cadence in `texts.txt` — model line is the terse `"We're surrounded."`). Brought
speaker+line variants; **nothing locked** (Nicolas paused on the inn question, below). No commits
this session.

**⚠ DRIFT BUG found — fix before the inn beat.** The Ch2 YAML still has **Wolfram armoring the
sled in the Targos inn cutscene**, but the sled is **already armored at the END of Ch1** (shipped
v0.1.0 canon: `ch01-the-iron-trail.yaml` ending beats C–D — Wolfram bites an ingot, asks Hruna for
the iron + a forge-night; RBG over-engineers & names it the *Rolling Cheddar*). So `ch02` contradicts
shipped Ch1 in **two** places:
- the `ch02-targos-inn` event description: *"Wolfram forges armored siding onto the sled from the
  ch01 iron ingots"* — he can't first-armor a sled that's already armored.
- `soft_penalty_on_sled_loss`: *"Wolfram's armoring beat is cut from the inn cutscene"* — that
  beat doesn't exist to cut.
These need a real replacement: a new inn payoff for Wolfram (e.g. he *repairs raid battle-damage* /
re-plates a gouged side, not first-time armoring) AND a real soft-penalty stake for losing the sled
(chest + post-chapter gold forfeit already stands; the "armoring cut" line must go).

## Next (priority order)
1. **Fix the Ch2 inn drift (above) FIRST** — it's a correctness bug in `ch02-cold-welcome.yaml`,
   not just prose. Rewrite the `ch02-targos-inn` event description + `soft_penalty_on_sled_loss`
   so neither claims a first-time armoring. Clean rewrite, no "changed on DATE" banners.
2. **Lock `ch02-rear-ambush`** (turn-3 combat bark; #22) — decision pending: **speaker is a
   toss-up between Wolfram and Braulo** (my earlier "Wolfram pre-echoes his armoring" pitch is
   DEAD — the armoring is a Ch1 beat). Drafted, budget = 1–2 lines / 1 screen, end on the order:
   - **Wolfram W3** (leanest, matches FE8): "Wolves at our backs — the sled." / "Hold here. I've got the rear."
   - **Braulo B1** (decisive settle-it): "More of them, behind the sled." / "Turn and hold the line. That's the work now."
3. **`ch02-targos-inn`** (chapter end) — the big multi-beat scene (frozen-sacrifice discovery,
   frost-druid glimpse = Ch4 seed, inn room/camp split, **Wolfram inn payoff per #1**, Maer Monster
   + Lonelywood rumors). **Needs Nicolas's beat intent before drafting.**
   Then **ch02 host wiring** (not built yet — MNC2 drops to vanilla Ch3) + Vellynne cutscene
   portrait (#19) + in-game motion review.
4. Supporting content as Ch2 needs them: enemy YAML pass #18, NPC/recruit stubs #17, recruit
   schedule (#45 item 5), world-map unlock #29.
5. Art passes layer on already-playable slices: portraits #19, overworld sprites #38.

## Watch out
- **Writing any dialogue → invoke the `dialogue-pass` skill first.** Voice grounding lives in the
  repo: per-NPC `lore/*.md` §Voice bibles + `lore/frostmaiden-voices.md` (canon cast) + the FE8
  cadence corpus `fireemblem8u/texts/texts.txt`. Read sources BEFORE asking Nicolas; bring drafts,
  not questions.
- Combat = pure vanilla FE; field parity with vanilla ch N is doctrine.
- Long unit names overflow FE8's name buffer — add a short `fe_name` (≤12) to new units.
- Story bodies are `make`-regenerated; gate text changes with `python3 tools/verify_text.py`.
- Build a shippable ROM only via `tools/build.sh test|dist`, never a bare `make`.
