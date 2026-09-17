---
id: 138
title: "Item reflavor = global name + icon swap per item id; the cast's per-unit `name:` fields are documentation only (#21, 2026-06-16)."
date: "2026-06-16"
section: "Art & Audio"
issues: [21]
---

# Item reflavor = global name + icon swap per item id; the cast's per-unit `name:` fields are documentation only (#21, 2026-06-16).

FE8 stores **one** name message and **one** 16×16 icon per item id (`gItemData[].nameTextId` / `.iconId`), so a reflavored
consumable necessarily reads the same for the whole party — the per-unit inventory `name:` fields in the cast YAML (which
historically varied: "Healing Potion" / "Blood Vial" / "Goodberry") cannot differ in-engine and are kept purely as
documentation/flavor. The reflavored Vulnerary is unified party-wide as **"Goodberry"** (Marty's druidic ration; Meesmickle's
blood-draught flavor survives only as a YAML comment). Two campaign-agnostic, data-driven mechanisms inject this:
`build_campaign.inject_item_names` (campaign.yaml `item_names: {ITEM_ENUM: name}` → rewrites the item's `nameTextId` message,
terminator-parity padded) and `build_campaign.inject_item_icons` (campaign.yaml `item_icons: {ITEM_ENUM: asset}` → overwrites
the item's tracked `.png` source under `graphics/item_icon/`, which gbagfx compiles to the `.4bpp`). Both resolve the item's
id/iconId from `data_items.c` and the icon's source file from `data_item_icon.s`'s incbin order — never hardcoded. The icon is
authored from FE8's **shared item-icon palette** (one fixed 16-colour bank for all item icons) via `tools/item_icon_tool.py`
(`blueberry_grid`, design "L2": blue body, dark five-point calyx button, green branch rooted in the button's centre, single
left leaf — iterated with Nicolas). Authoring in the shared palette means the icon
needs no recolour; a vendored fruit icon would have had to be re-indexed to that palette anyway, so generated-via-tooling was
simpler than sourcing from the FE-Repo.
_Decided: 2026-06-16; shipped for the Goodberry (#21), `make` green + `verify_text` 3404/0 + `ch01win` PASS + in-ROM icon render._

**Palette off-by-one (2026-06-06, found on the first in-game cast test).** The cast bank loads one slot high: a
rainbow-palette test (each index a distinct hue) showed every sprite index `k` rendering cast colour `k-1`
(snowman-white→yellow, meesmickle's red cape→cyan, etc.). `gMapSpriteOverride`/`gCastMapPalette` data and the 4bpp
indices were all verified byte-correct, so the shift is in the engine's OBJ-bank load, not the injection.
**Fix:** `build_campaign._read_cast_palette` pre-rotates the 16-colour block up by one (`out[1:] + out[:1]`) so each
colour lands on its intended index. Don't "correct" `gCastMapPalette` to match `cast_palette.png` order — it is
intentionally rotated.

**Map sprites are IDLE-ONLY for now (movement auto-derive deferred).** The finished cast idle (`<id>.png`) is folded
onto the real cast id and injected; the stale per-class `<id>_mu.png` walk sheets were removed, so a *moving* unit
currently falls back to its stock class sprite (standing shows the custom sprite). The 32×32 action/side sheets explored
in the editor are exploratory and not injected. **Geometry base is a token:** for non-decomp FE-Repo donors the YAML
`art.map_sprite.base` is set to any decomp class of matching frame size (16×16 or 32×32) purely to read the SMS size;
the real art donor is named in a comment + `CREDITS.md`.

**Two sheets per character, grouped as one deliverable** (battle anims #39 are a separate track):
- **Idle** = the small **wait** sheet (16×16 frame strip), `unit_icon_wait_table[SMSId]`, swapped via the `GetUnitSMSId`
  per-character override above. *(Proven in mGBA, Braulo placeholder.)*
- **Hover/selected + walking** = the larger per-class **MU** sheet (`gMuInfoTable` = `unit_icon_move_table[classId-1]`;
  a **32×480 strip = 15 frames of 32×32**). Override the same way: `MuProc` carries `->unit`, so patch `GetMuImg` to
  return a per-character custom sheet (reusing the class's motion script, so only the graphics change) before falling
  back to the class sheet. Both in-chapter MU draws route through `GetMuImg`, so one hook covers hover + walk.
The MU sheet is the bigger art lift (a 15-frame walk cycle), but it stays in the map-sprite group, not battle anims.
One gotcha: `StartMu`/`StartMuExt` decompress the sheet *before* setting `proc->unit`, so the override reloads the
graphics after `proc->unit` is set (else it falls back to the class sheet).
_Decided 2026-06-04; both override paths (idle + MU) built and proven in mGBA with Braulo placeholders (idle = Dancer, hover/walk = Mogall). Colour mechanism revised 2026-06-05 to the dedicated-bank approach (bank 0xB) after confirming the bank is free in single-player play — supersedes the earlier "modify the shared player palette" plan, which carried a rollout mis-tint gotcha._

**Map-sprite ART process: reskin a vanilla FE base, NOT downscale generated art.**
The portrait pipeline (Gemini bust → downscale → indexed) does **not** transfer to map sprites: at 16×16 / 32×32,
downscaling detailed or AI-generated art yields irregular colours + mush (researched; AI tools make high-res
"pixel-*styled*" images that always need pixel-by-pixel cleanup). The FE-community standard is to **edit an existing
map-sprite base** (FEU Map Sprite Repository, Klokinator FE-Repo) — it bakes in the chibi proportions and, crucially,
the **already-animated walk cycle** (you re-skin the motion instead of animating 15 frames from scratch). At 16px a
heavily-reskinned base *is* effectively custom. **Process (decided 2026-06-04):** (1) pick the vanilla base of the
class closest to each character's build; (2) **programmatic recolour first** — remap the base to the shared cast
palette + light edits, render in mGBA, Nicolas judges; (3) **fallback = hand-edit in LibreSprite** (free Aseprite fork)
where the recolour isn't good enough (Nicolas will do the pixel pass). Idle (3f) first, then the walk MU
(15f). I handle palette-enforce / sheet-assembly / injection; the creative pixel judgement is the split point.
_Decided 2026-06-04 (Nicolas: recolour-first, hands-on fallback, free tool). See FEU "Map Sprite Insertion Mania" thread._
