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
      windup,peak}.png`; add the `battle_anim:` YAML block with a **free** `clone_into` class slot.
      ⚠️ confirm `AnimConf .index == anim_id + 1` (else purple dragon).
- [ ] **Stats** — wire `STAT_DONOR` / `BASE_DONOR` / `GROWTH_DONOR` (+ `PORTRAIT_MAP`) in `build_campaign.py`.
- [ ] **Platform** (only if a new ground look) — vendor from FE-Repo `{Cynon}` (F2E, **credit in
      `CREDITS.md`**), confirm 256×32 indexed; add to `BATTLE_PLATFORMS` + the right terrain mapping;
      set the chapter's `battleTileSet` (0 = Snowdrift / 0x15 = Uneven).
- [ ] **Build + verify** — `make TESTCH=1` then `run.sh recordrbg`; confirm the unit deploys as its
      clone class number and fires on the right ground (unforced).
- [ ] **Deliver** — GIF (never MP4) to `docs/demo/`, push → Nicolas reviews on GitHub. **Render → show
      → wait for OK → then commit** the art as canonical.
- [ ] **Record** — credit vendored assets in `CREDITS.md`; log any new non-obvious decision as a dated
      ADR in `docs/decisions.md` (same commit); `make` green + `verify_text` clean.
