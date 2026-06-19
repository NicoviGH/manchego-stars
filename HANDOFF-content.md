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

## Last session (2026-06-19, pm) — pushed to main, green
**`ch02-rear-ambush` turn-3 bark LOCKED.** Commit `76cd540` feat(ch02) (#22). Speaker resolved —
**Wolfram** (Nicolas's pick over Braulo): keeps the decisive-command beat off Braulo twice in one
chapter (the opening cutscene already ends on his settle-it line) and ties the bark to the sled
Wolfram forged in ch01 / re-plates at the inn. Locked text in `ch02-cold-welcome.yaml`'s turn-3
event: *"Wolves at our backs — the sled." / "Hold here. I've got the rear."* — terse FE8
reinforcement-bark cadence, ends on the order; passed the `dialogue-pass` craft check. Text-only
YAML, **unwired** (eventscript + on-map bubble fit deferred, same posture as the locked opening
event) → ROM-neutral; `make check` clean. **One wiring flag recorded in the event description:**
line 1 is 31 chars, past the 29-char on-map bubble wrap → at insertion it wraps to the bubble's 2nd
line (or `[LF]` split); verify the right-side bubble isn't pushed offscreen by the width measure.

Prior session (same day, `421fe98..35debda`, all shipped): Ch2/Ch1 inn drift bug FIXED (`cc3207c` —
Targos-inn beat now has Wolfram **re-plating raid battle-damage**, not first-armoring; soft-penalty
is just chest + gold forfeit); worktree commit-hook blocker fixed (`dcbb247` — `vanilla_decomp_text`
strips inherited git env so `git -C fireemblem8u show` survives the pre-commit hook in a worktree);
worktree-always rule codified (`35debda`).

**Not done (Nicolas's call, teed up below):** the `ch02-targos-inn` beat intent — needs his beat
direction before drafting.

## Next (priority order)
1. **`ch02-targos-inn`** (chapter end) — the big multi-beat scene (frozen-sacrifice discovery,
   frost-druid glimpse = Ch4 seed, inn room/camp split, **Wolfram's re-plating payoff per the fix
   above**, Maer Monster + Lonelywood rumors). **Needs Nicolas's beat intent before drafting.**
   Then **ch02 host wiring** (not built yet — MNC2 drops to vanilla Ch3) + Vellynne cutscene
   portrait (#19) + in-game motion review.
2. Supporting content as Ch2 needs them: enemy YAML pass #18, NPC/recruit stubs #17, recruit
   schedule (#45 item 5), world-map unlock #29.
3. Art passes layer on already-playable slices: portraits #19, overworld sprites #38.

## Watch out
- **Writing any dialogue → invoke the `dialogue-pass` skill first.** Voice grounding lives in the
  repo: per-NPC `lore/*.md` §Voice bibles + `lore/frostmaiden-voices.md` (canon cast) + the FE8
  cadence corpus `fireemblem8u/texts/texts.txt`. Read sources BEFORE asking Nicolas; bring drafts,
  not questions.
- Combat = pure vanilla FE; field parity with vanilla ch N is doctrine.
- Long unit names overflow FE8's name buffer — add a short `fe_name` (≤12) to new units.
- Story bodies are `make`-regenerated; gate text changes with `python3 tools/verify_text.py`.
- Build a shippable ROM only via `tools/build.sh test|dist`, never a bare `make`.
