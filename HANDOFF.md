# Handoff: #44 CLOSED (phantom — Meesmickle is a black cat by design; no render bug). Ch1 difficulty is the one live open item — QUANTIFIED, but the APPROACH is still Nicolas's design call (lord-anchor vs party-bump vs guest vs deploy — nothing chosen).

**Date:** 2026-06-18 (session 13)
**Where we are:** Chased #44 ("rescued cast sprite renders BLACK") to ground and found it's a
non-bug — closed it. No engine change shipped; mu.c untouched. The only carried-over open item is
the **Ch1 difficulty** approach, which needs a design decision from Nicolas (not an engineering task).

`make` green (untouched ROM — only Lua playtest tooling changed) · `recordrescue` + new
`recordtrade` PASS · drift clean.

## ✅ #44 "rescued cast sprite renders BLACK" — CLOSED, not-a-bug
There is **no render fault.** The "black sprite" is **Meesmickle** (GILLIAM slot): a deliberately
black cat with a red cape — his correct map sprite. A bystander Meesmickle near a rescue got misread
as a broken cast unit (greyed-out *acted* units are also just normal desaturation).

The session-12 root cause was **also wrong, and its "decided fix" was a no-op.** The blamed path —
`mu.c:856` `facing == MU_FACING_STANDING → PutMuSMS` — is **dead code**: `src/mu.o` builds from
`src/mu.c` (`.dep/src/mu.d`; `ASM_SUBDIR=asm`, so `mu.s` is dead reference), and `MU_FACING_STANDING`
(15) is **assigned nowhere** in any compiled `.c`. `proc->facing` is only ever `UNK11` or a
`SetMuFacing` arg, and no caller passes 15 → `PutMuSMS` never runs. Rerouting it changes a branch
that's never taken.

**Verified clean** (full custom art, correct palette): the rescue lift (Braulo carrying Marty),
the rescue action menu, the rescue target-select previews, and the **trade menu** (Braulo the orange
crab + Marty the mushroom-person). Captures in `map-review/rescue-44-*.png`. Full record: the
closed issue #44 + [[project_manchego_stars_cast_notes]] (Meesmickle = black cat by design).

## 🟡 Ch1 difficulty — QUANTIFIED; approach STILL OPEN (Nicolas's design call, nothing chosen)
`balance_report.py` settles the diagnosis: **the enemies are not the problem — the party is.** Our
line goblins are **lv1** (class base); vanilla Ch1's were **lv2-3** + the same lv4 boss, so our enemy
field is marginally *easier*. The gap is entirely the lordless cast:
- **Durability:** vanilla's *frailest* fielded unit (Eirika, 2.8 enemy-hits-to-down) ≈ our
  *sturdiest*. Half our cast drops in **<2 hits** open ground (~2.6 with forest). **Seth takes 17.5.**
- **Carry gap:** Eirika **ORKOs the boss** (effective Rapier ×3); our best (Braulo) needs ~2.8
  rounds of boss exposure (and the boss hits him for 11 — a real risk).
- **Output gap:** **Seth alone = 48% of vanilla's 4-unit DPR.** Our best 4 = 44% of vanilla;
  our best 6 = 55% → **more bodies can't replace the missing carry.**

**STATUS: still evaluating — NOTHING decided.** Options on the table (lean-generous, no enemy nerfs):
- **"Lord-mode" — the player-chosen lord becomes the party's anchor (Nicolas's idea, UNDECIDED).**
  Restores vanilla's "one anchor carries it" structure + gives lord-select weight + a campaign-long
  anchor (lord persists). Open sub-dial = how strong: Braulo-2.8 (today) → **Jagen-lite ≈ Gilliam
  5.9** (leanable, still a fight) → Seth-17.5 (solos). Constraints if pursued: MVP unpromoted ⇒
  level-boosted *in-class* anchor (flavour follows the picked class), NOT a promoted Paladin;
  campaign-wide; a pure level-boost won't fix class holes (e.g. Wolfram Spd-15% doubling) so it'd
  need a survivability floor. Alt framing he floated: instead level the fielded party to ≈ vanilla's
  4 (caveat: vanilla's output is Seth-concentrated, so a flat ensemble bump can't match it — *someone*
  still has to anchor).
- **Per-unit anchor tweak** — e.g. Wolfram +3 Spd → survivability 1.8→3.9 (stops the fighter double).
- **Guest veteran (a Jagen)** fielded in Ch1, like the prologue's Scramsax.
- **deploy_limit 4 → 5/6** (output 44%→50–55%) — Nicolas wants to discuss; **undecided**.
- **Forest-cover routing** (free, +20 avo → squishies 1.9→2.6) — secondary.
- **Generous campaign EXP** — long-game lever; barely moves Ch1 durability (def growths 5–15%).
- **AVOID:** nerfing the (already-gentle) enemies; blanket party-leveling (doesn't fix durability).

**Offered next step (NOT greenlit):** extend `tools/balance_report.py` to model "lord-mode" at 2–3
tiers across all 7 lord candidates, to pick the dial on numbers — *only if* Nicolas wants to decide on
numbers rather than keep weighing the concept (lord-anchor vs party-bump vs guest vs deploy).

## Next up
- **Ch1 difficulty decision** (Nicolas) — pick the lever family, then I model/implement.
- Otherwise back to the **ART path** (map sprites / battle anims) via the test-chapter loop
  ([[project_manchego_stars]] current focus).

## On-demand builds
`tools/build.sh test` (lean) · `tools/build.sh dist` (with #43 montage; stamps `dist/`). NEVER a
bare `make` for a shippable ROM — it strips the montage.

## Playtest tooling (this session)
- `tools/playtest/harness.lua` — new **`recordtrade`** scenario (captures the trade screen: both
  units' panels + items) and added action-menu / target-select `shot()`s to `recordrescue`.
- `tools/playtest/run.sh` — `recordtrade → ckpt_prep` (reuses the prep checkpoint).

## Gotchas (carried)
- Background `run.sh` calls need an explicit `cd`/absolute path (shell cwd resets between tool
  calls — a relative `tools/playtest/run.sh` silently no-ops from the wrong dir).
- `record*` defaults to 60fps+videoSync; `PT_FPS=240 tools/playtest/run.sh <scen>` for fast
  static/menu captures. Built ROM at `fireemblem8u/fireemblem8.gba`. Nicolas can't see inline
  renders — save to `map-review/` and `open`. Izobai female; Pinky male. **Meesmickle is a black cat
  by design** (don't mistake him for a render bug); greyed = normal acted desaturation.
- **Never commit the `fireemblem8u` submodule pointer** (build artifact); stage repo files explicitly.
- Story text → `make` regenerates bodies; gate with `verify_text` after any text change.

## Memory
[[project_manchego_stars]] · [[project_manchego_stars_campaign_structure]] · [[manchego_stars_automated_playtests]] ·
[[project_manchego_stars_cast_notes]] · [[manchego_stars_ch1_difficulty]] · [[feedback_use_decomp]] ·
[[feedback_fe-level-design]] · [[feedback_proactive-push]] · [[feedback_handoff_vs_memory]] · [[feedback_answer_before_picker]]

## Standing rules
Combat = pure vanilla FE; field parity with vanilla ch N is doctrine. Custom art where it matters,
**show before committing**; bring 2-3 options, let Nicolas drive. **Fast playtests for logic;
60fps recordings only for fade spot-checks.** Repo is the source of truth, NOT memory. Auto-push
to main once green; never commit the `fireemblem8u` submodule pointer.
