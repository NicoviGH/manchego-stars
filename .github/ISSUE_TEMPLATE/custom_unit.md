---
name: "🎨 Custom unit (art · battle anim · platform)"
about: "Track a character or enemy's full custom look end-to-end, the repeatable way"
title: "[Unit] <name> — custom art/anim/platform"
labels: ["art"]
---

End-to-end checklist for giving a unit its custom look. **The "how" lives in code + decisions, not a
prose doc** — each step links its source of truth:
- Anim/clone-class how → the `inject_battle_anims` docstring (`tools/build_campaign.py`)
- Platform how → the `inject_battle_platforms` docstring (`tools/build_campaign.py`)
- Decisions/rationale (additive clone class, platform picks, scale) → `docs/decisions.md` (Art & Audio)
- Fast iteration → `make TESTCH=1` (boots into the Ch1 sandbox) + `inject_test_chapter` docstring;
  capture via `tools/playtest/run.sh recordrbg` (fresh checkpoint)
- **Principle that governs all of it: ADDITIVE, never global** — clone into free slots; never edit a
  shared vanilla class/anim/terrain in place.

## Checklist
- [ ] **Portrait + map sprite** — `art:` block in the unit YAML; generate (Gemini) → fit/index via
      `tools/ref_to_bust.py` / `tools/portrait_tool.py`; reskin a credited FE-Repo body via
      `tools/map_sprite_editor.py`. Add `fe_name` (≤12) if the name overflows the buffer.
- [ ] **Battle anim** — 3 hi-res poses → BOX-descale to `campaigns/.../battle_anims/<unit>/{ready,
      windup,peak}.png`; add the `battle_anim:` YAML block naming its `clone_from` donor class.
      (An FE-native community anim goes through `import:` instead — the `.txt` owns the cadence,
      so do NOT hand it one of ours.)
      ⚠️ confirm `AnimConf .index == anim_id + 1` (else purple dragon).
      ⚠️ repoint **every** slot the donor's AnimConf carries, including `ITYPE_ITEM` — that is the
      UNARMED entry, and a slot left vanilla draws the donor's human body the moment the unit's
      weapons break (#206, and again on #25's Myrmidon/Bishop rows).
- [ ] **Stats** — wire `STAT_DONOR` / `BASE_DONOR` / `GROWTH_DONOR` (+ `PORTRAIT_MAP`) in `build_campaign.py`.
- [ ] **Platform** (only if a new ground look) — vendor from FE-Repo `{Cynon}` (F2E, **credit in
      `CREDITS.md`**), confirm 256×32 indexed; add to `BATTLE_PLATFORMS` + the right terrain mapping;
      set the chapter's `battleTileSet` (0 = Snowdrift / 0x15 = Uneven).
- [ ] **Build + verify** — `make TESTCH=1`, then capture all THREE parts of the art in-engine:
      `PT_CHAR=<id> run.sh recordcast` (bust + map sprite, off the status screen) and
      `PT_CHAR=<id> run.sh recordanim` (the battle anim). Confirm the unit deploys as its PLAIN
      vanilla class (the anim rides a private per-character AnimConf) and fires on the right ground
      (unforced).
      ⚠️ **Film several rounds — `PT_ROUNDS=4` — not one.** FE8 resolves damage in DATA whatever the
      animation does, so a broken script still kills the foe, still shows correct frames and still
      reports PASS; a one-round capture never asks for the next input that reveals a soft-lock.
      That is exactly how Sahnar's Specter shipped a hang past a green capture (#25).
      If a round hangs, run a KNOWN-GOOD unit at the same `PT_ROUNDS` before blaming the anim —
      that control run is what separates "my capture is wrong" from "this asset is broken".
- [ ] **Deliver** — GIF (never MP4) to `docs/demo/`, push → Nicolas reviews on GitHub. **Render → show
      → wait for OK → then commit** the art as canonical.
- [ ] **Record** — credit vendored assets in `CREDITS.md`; log any new non-obvious decision as a dated
      ADR in `docs/decisions.md` (same commit); `make` green + `verify_text` clean.
