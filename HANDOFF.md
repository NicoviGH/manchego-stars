# Handoff: PICK UP HERE → Ch1 difficulty. Analysis is done; it needs Nicolas to pick the lever family (lord-anchor vs party-bump vs guest vs deploy), then model/implement. (#44 closed as a phantom — not a bug.)

**Date:** 2026-06-18 (session 13)
**Session focus:** Closed out the rescue #44 investigation (it was a phantom) and cleaned docs/memory
to convention. The one live work item is **Ch1 difficulty** — quantified and ready for a fresh
instance to drive with Nicolas. `make` green (only Lua playtest tooling changed this session).

## 🎯 PICK UP HERE — Ch1 difficulty (decision pending)
`tools/balance_report.py` settles the diagnosis: **the enemies aren't the problem — the party is.**
Our line goblins are **lv1** (class base); vanilla Ch1's were **lv2-3** + the same lv4 boss, so our
enemy field is marginally *easier*. The whole gap is the lordless cast:
- **Durability:** vanilla's *frailest* fielded unit (Eirika, 2.8 enemy-hits-to-down) ≈ our
  *sturdiest*. Half our cast drops in **<2 hits** open ground (~2.6 w/ forest). **Seth takes 17.5.**
- **Carry gap:** Eirika **ORKOs the boss** (effective Rapier ×3); our best (Braulo) needs ~2.8
  rounds of boss exposure (boss hits him for 11 — real risk).
- **Output gap:** **Seth alone = 48% of vanilla's 4-unit DPR.** Our best 4 = 44% of vanilla;
  our best 6 = 55% → **more bodies can't replace the missing carry.**

**DECISION NEEDED FROM NICOLAS — nothing chosen.** Options (lean-generous, no enemy nerfs):
- **"Lord-mode" — the player-chosen lord becomes the party's anchor (his idea, UNDECIDED).** Restores
  vanilla's "one anchor carries it" + gives lord-select weight + a campaign-long anchor. Sub-dial =
  how strong: Braulo-2.8 (today) → **Jagen-lite ≈ Gilliam 5.9** (leanable, still a fight) →
  Seth-17.5 (solos). Constraints: MVP is unpromoted ⇒ a level-boosted *in-class* anchor (flavour
  follows the picked class), NOT a promoted Paladin; campaign-wide; a pure level bump won't fix class
  holes (e.g. Wolfram Spd-15% doubling), so it needs a survivability floor. Alt framing he floated:
  level the *fielded party* to ≈ vanilla's 4 (caveat: vanilla output is Seth-concentrated, so a flat
  ensemble bump can't match it — someone still has to anchor).
- **Per-unit anchor tweak** — e.g. Wolfram +3 Spd → survivability 1.8→3.9 (stops the fighter double).
- **Guest veteran (a Jagen)** fielded in Ch1, like the prologue's Scramsax.
- **deploy_limit 4 → 5/6** (output 44%→50–55%) — he wants to discuss; **undecided**.
- **Forest-cover routing** (free, +20 avo → squishies 1.9→2.6) — secondary.
- **Generous campaign EXP** — long-game lever; barely moves Ch1 durability (def growths 5–15%).
- **AVOID:** nerfing the (already-gentle) enemies; blanket party-leveling (doesn't fix durability).

**How to continue:**
1. Re-engage Nicolas on the lever family — collaborative: bring the trade-offs, let him drive
   ([[feedback_fe-level-design]], [[feedback_collaborative_map_design]]). He may want to weigh the
   *concept* before any numbers.
2. If he wants to decide on numbers: extend `tools/balance_report.py` to model the chosen lever(s)
   across 2–3 tiers (e.g. lord-mode over the 7 lord candidates), then implement in the chapter YAML.
3. Record the chosen approach + rationale in `docs/decisions.md` (don't leave it only in chat).
- Run the current analysis: `python3 tools/balance_report.py`.

## Already resolved (no action)
- **#44 "rescued cast sprite renders BLACK" — closed, not-a-bug.** It's Meesmickle (a black cat by
  design); the session-12 `mu.c:856 facing==STANDING → PutMuSMS` root cause is dead code (facing is
  never STANDING), so the "decided fix" was a no-op. Cast verified rendering correctly across the
  rescue lift, rescue menu, and trade menu. mu.c untouched. Full record: **closed issue #44**.
- **Playtest tooling shipped:** `recordtrade` scenario (trade-screen capture) + action-menu /
  target-select shots in `recordrescue` (`harness.lua`, `run.sh`; on main).

## Builds
`tools/build.sh test` (lean) · `tools/build.sh dist` (with #43 montage; stamps `dist/`). NEVER a
bare `make` for a shippable ROM — it strips the montage.

## Gotchas (operational)
- Background `run.sh` calls need an explicit `cd`/absolute path (shell cwd resets between tool calls).
- `record*` defaults to 60fps+videoSync; `PT_FPS=240 tools/playtest/run.sh <scen>` for fast
  static/menu captures. Built ROM at `fireemblem8u/fireemblem8.gba`. Nicolas can't see inline
  renders — save to `map-review/` and `open`.
- **Never commit the `fireemblem8u` submodule pointer** (build artifact); stage repo files explicitly.
- Story text → `make` regenerates bodies; gate with `python3 tools/verify_text.py` after text changes.

## Standing rules
Combat = pure vanilla FE; field parity with vanilla ch N is doctrine. Custom art where it matters,
**show before committing**; bring 2-3 options, let Nicolas drive. **Project knowledge lives in the
repo** (decisions.md / YAML / lore / issues), NOT private memory. Auto-push to main once green; never
commit the `fireemblem8u` submodule pointer.
