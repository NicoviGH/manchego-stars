# Handoff — Content track 🔒 (instance A)

Live state for the **content instance**. The parallel-work model is the ADR in
`docs/decisions.md` (§Delivery model → Parallel work model / Engine-content file seam) and the
work tracker is #50; the backlog is **GitHub issues** (#49 ① Content track), not this file.
Don't clobber the pipeline track's `HANDOFF-pipeline.md`.

## Launch this instance (paste as the kickoff prompt)
> You are the **Content-track** instance for Manchego Stars (trunk-based, your own worktree).
> 1. Bootstrap an isolated build env: `tools/worktree-setup.sh ../ms-content` (creates the
>    worktree on branch `inst/content` + symlinks the toolchain). `cd ../ms-content`.
> 2. Read `CLAUDE.md`, this file, and `docs/decisions.md`, then continue from **Next** below.
> 3. Trunk-based: small commits, `git pull --rebase origin main` often, push when green, no
>    long-lived branches, never commit the `fireemblem8u` submodule pointer.

## You own (edit freely)
- `campaigns/rime-of-the-frostmaiden/**` — chapter YAMLs, pcs/npcs/enemies YAML, dialogue
- `tools/build_campaign.py` — the `inject_*` content functions + the 6 sprite/palette hooks
- `tools/portrait_tool.py`, `tools/map_sprite_tool.py`, `tools/ref_to_bust.py` (art pipeline)
- `docs/` story/chapter/art docs

## Hands off (pipeline track owns — coordinate via an issue if you need a change)
- `tools/inject/engine_hooks.py`, `tools/inject/decomp.py` (shared — propose changes, don't fork)
- `tools/difficulty.py`, `tools/fe_combat.py`, `tools/check.py`, `tools/playtest/**`, CI

## Next (priority order)
1. **Ch2 slice — "Cold Welcome" (#22)** — the next vertical slice (map + events + enemies +
   cast-at-parity + draft dialogue), ch00/ch01 component breakdown reused. Sequential, needs
   Nicolas for design intent. Hosted on the next chapter slot (ch01 ends with the handoff MNCx).
2. Supporting content as Ch2 needs them: enemy YAML pass #18, NPC/recruit stubs #17, recruit
   schedule (#45 item 5), world-map unlock #29.
3. Art passes layer on already-playable slices: portraits #19, overworld sprites #38.

## Watch out
- Combat = pure vanilla FE; field parity with vanilla ch N is doctrine.
- Long unit names overflow FE8's name buffer — add a short `fe_name` (≤12) to new units.
- Story bodies are `make`-regenerated; gate text changes with `python3 tools/verify_text.py`.
- Build a shippable ROM only via `tools/build.sh test|dist`, never a bare `make`.
