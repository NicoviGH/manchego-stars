# Handoff — Content track 🔒 (instance A)

Live state for the **content instance**. The parallel-work model is the ADR in
`docs/decisions.md` (§Delivery model → Parallel work model / Engine-content file seam) and the
work tracker is #50; the backlog is **GitHub issues** (#49 ① Content track), not this file.
Don't clobber the pipeline track's `HANDOFF-pipeline.md`.

## Start here (fresh instance — do this first)
You are the **Content-track** instance for Manchego Stars (trunk-based, your own worktree).
1. Bootstrap an isolated build env: `tools/worktree-setup.sh ../ms-content` (creates the worktree
   on branch `inst/content` + symlinks the toolchain). `cd ../ms-content`.
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

## Last session (2026-06-19)
**Ch2 dialogue pass started + voice-reference infra built.** Studied FE8's own script cadence
(`fireemblem8u/texts/texts.txt`, incl. our shipped prologue/ch01) and the Frostmaiden canon
voices (book + web). Added two repo references and locked the first Ch2 scene:
- `lore/frostmaiden-voices.md` — canon-NPC voice reference (Arcane Brotherhood, Professor Skant,
  Auril, frost druids) + the FE8-cadence sourcing note (the two registers every line must satisfy).
- `lore/vellynne-harpell.md` — full §Voice bible (register **B**: icy-formal, no contractions).
- `ch02-cold-welcome.yaml` → **`ch02-opening` LOCKED**: Vellynne's west-gate cameo + stolen-orb
  hook (Skant/Lantomir seeded, unnamed). Vellynne/RBG/Braulo three-hander + Meesmickle button.

## Next (priority order)
1. **Finish the Ch2 "Cold Welcome" dialogue (#22)** — use the `dialogue-pass` skill (variants →
   Nicolas picks; he owns voice). `ch02-opening` is done; two beats remain:
   - **`ch02-rear-ambush`** (turn 3) — short combat bark as wolves hit the back line.
   - **`ch02-targos-inn`** (chapter end) — the big multi-beat scene (frozen-sacrifice discovery,
     frost-druid glimpse = Ch4 seed, inn room/camp split, Wolfram armors the sled, Maer Monster +
     Lonelywood rumors). **Needs Nicolas's beat intent before drafting.**
   Then **ch02 host wiring** (it's not built yet — MNC2 drops to vanilla Ch3) + Vellynne cutscene
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
