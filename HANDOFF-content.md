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

## Last session (2026-06-19, pm) — all pushed to main, green
**Ch2/Ch1 inn drift bug FIXED + a worktree commit-hook blocker fixed + the worktree workflow rule
codified.** Three commits on `main` (`421fe98..35debda`):
- **`cc3207c` fix(ch02) (#22)** — the drift bug is resolved. The Targos-inn beat no longer claims
  Wolfram *first-armors* the sled (it's already armored at the end of Ch1 — `ch01` ending beats C–D,
  his forge-night, RBG names the *Rolling Cheddar*). Rewrote all three spots in
  `ch02-cold-welcome.yaml`: `soft_penalty_on_sled_loss` (now just chest + gold forfeit), the
  `chapter_end` inn event description (Wolfram **re-plates the raid's battle-damage**, plays only if
  the sled survived), and `design_notes`. Flavor-only fields → ROM-neutral; `make check` clean.
- **`dcbb247` fix(build)** — `vanilla_decomp_text` now strips inherited git env. `git -C fireemblem8u
  show HEAD:…` was exiting 128 under the **pre-commit hook in a worktree** (git sets `GIT_DIR` for
  hooks, which overrides `-C` discovery → resolves against the superproject). This had been blocking
  *every* commit from `../ms-content` / `../ms-pipeline`. Reproduced + verified the fix under a
  simulated hook env.
- **`35debda` docs** — Nicolas's rule: **"work the content/pipeline track" always means cd into that
  track's worktree first, never `main`.** Rewrote the CLAUDE.md routing (dropped the old "sequential
  work needs none of this" carve-out), aligned both HANDOFF kickoffs, recorded it in `decisions.md`.

**Not done (Nicolas's call, teed up below):** the `ch02-rear-ambush` speaker pick and the
`ch02-targos-inn` beat intent — both surfaced with drafts/options, neither locked.

## Next (priority order)
1. **Lock `ch02-rear-ambush`** (turn-3 combat bark; #22) — **decision pending: speaker is Wolfram
   vs Braulo** (asked Nicolas at end of last session; not yet answered). Drafted + voice-grounded,
   budget = 1–2 lines / 1 screen, ends on the order. On his pick → run `dialogue-pass` to finalize
   voice, then commit the lock into `ch02-cold-welcome.yaml`'s rear-ambush event.
   - **Wolfram** (leanest, matches FE8's terse reinforcement barks): "Wolves at our backs — the sled." / "Hold here. I've got the rear."
   - **Braulo** (decisive settle-it leader beat): "More of them, behind the sled." / "Turn and hold the line. That's the work now."
2. **`ch02-targos-inn`** (chapter end) — the big multi-beat scene (frozen-sacrifice discovery,
   frost-druid glimpse = Ch4 seed, inn room/camp split, **Wolfram's re-plating payoff per the fix
   above**, Maer Monster + Lonelywood rumors). **Needs Nicolas's beat intent before drafting.**
   Then **ch02 host wiring** (not built yet — MNC2 drops to vanilla Ch3) + Vellynne cutscene
   portrait (#19) + in-game motion review.
3. Supporting content as Ch2 needs them: enemy YAML pass #18, NPC/recruit stubs #17, recruit
   schedule (#45 item 5), world-map unlock #29.
4. Art passes layer on already-playable slices: portraits #19, overworld sprites #38.

## Watch out
- **Writing any dialogue → invoke the `dialogue-pass` skill first.** Voice grounding lives in the
  repo: per-NPC `lore/*.md` §Voice bibles + `lore/frostmaiden-voices.md` (canon cast) + the FE8
  cadence corpus `fireemblem8u/texts/texts.txt`. Read sources BEFORE asking Nicolas; bring drafts,
  not questions.
- Combat = pure vanilla FE; field parity with vanilla ch N is doctrine.
- Long unit names overflow FE8's name buffer — add a short `fe_name` (≤12) to new units.
- Story bodies are `make`-regenerated; gate text changes with `python3 tools/verify_text.py`.
- Build a shippable ROM only via `tools/build.sh test|dist`, never a bare `make`.
