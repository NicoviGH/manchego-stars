# Asset Pipeline — adding a custom unit (art · battle anim · platform)

How to give a character or enemy its full custom look — portrait, map sprite, **faked battle
animation**, and the snow/ice **battle platform** — and verify it in-engine fast. Codifies the
#65 exercise (RBG) so the remaining cast/enemies are streamlined and repeatable.

**The one principle that governs everything here: ADDITIVE, never global.** We clone into *free*
slots (a clone class, new `battle_terrain_table` rows, an appended `banim_data` row) so generic
units and enemies stay byte-vanilla. If you ever find yourself editing a shared/vanilla class,
anim, or terrain entry in place — stop; add a slot instead. Rationale: `decisions.md` (Art &
Audio; the additive clone-class call).

Everything is injected at build time by `tools/build_campaign.py` from sources committed under
`campaigns/<campaign>/`; decomp edits are restorable build artifacts (listed in
`PATCHED_DECOMP_FILES`), never committed (we never commit the `fireemblem8u` submodule).

---

## 0. Lane & worktree discipline

- **Content lane** (`../ms-content`, `inst/content`): `build_campaign.py`, `campaigns/**`, art
  tools, `CREDITS.md`, `docs/**`. Almost all of this playbook is content lane.
- **Pipeline lane** (`../ms-pipeline`, `inst/pipeline`): `tools/playtest/**` (the capture
  scenarios + `run.sh`), `difficulty.py`, `check.py`, CI.
- **The ROM builds in the worktree you run `make` in.** Develop+test capture scenarios in
  `ms-content` (where the campaign ROM builds), then **port the harness diff to `ms-pipeline`
  and commit there** — the lane check blocks committing pipeline files from content. (We did this
  for `recordrbg`/`recordrbgtest`.)

---

## 1. Portrait / bust + map sprite

Established pipeline — see the per-unit YAML `art:` block and these tools:

- **Generate** the source from reference art with **Gemini / "Nano Banana"** (`mcp__nanobanana`,
  or Nicolas prompt-runs it), then **fit + index** into an FE8 portrait via `tools/ref_to_bust.py`
  (e.g. `--crop L,T,R,B --flip-h --zoom 0.88`) and `tools/portrait_tool.py`.
- **Prompts live in the unit YAML** `art:` block (`must_keep`, `expression`, `palette_plan`,
  `composition`). Keep the literal "tells" that make the face read as the character.
- **Framing rules** (from the portrait walkthroughs, see memory + `decisions.md`): busts read like
  vanilla FE8 — **sharpen OFF**, big readable face, shoulders trail off the corners, **descale the
  whole bust to fit, never crop** a must-keep feature. Render crops and let Nicolas pick.
- **Map sprite**: a vanilla body base (FE-Repo, credited) reskinned via `tools/map_sprite_editor.py`
  with a per-CHARACTER `GetUnitSMSId` override (custom SMS id) so stock classes/enemies are
  untouched. Disclose AI-generated art in `CREDITS.md`.
- **FE name truncation**: any unit whose name >12 chars needs a short `fe_name:` in its YAML or the
  name buffer garbles.

---

## 2. Faked battle animation (1–3 static frames → full anim)

Non-vanilla units get a battle anim from **static frames** riding a donor class's timing/effects —
no hand-drawn motion. Generator: `tools/ref_to_battleframe.py`; injector:
`inject_battle_anims` in `build_campaign.py`.

### 2a. Make the frames (descale from hi-res, never re-shrink small art)
1. Get **high-res** source frames (e.g. `…/Battle Anims/<Unit>/`, 1920×1080 RGBA): a **Ready**,
   **Wind-up**, and **Peak/Action** pose.
2. Clean → a protected ~15-colour palette (`*_fam.png` masters). **Snap to a *protected* palette
   (don't median-cut)** or pink noses/inner-ears get dropped.
3. **BOX-downscale the hi-res master → the small frame** (e.g. 88×64), anchoring the **feet at a
   common baseline** so the frames share one anchor and the feet stay on the platform. Despeckle
   stray pixels surgically. **Quality rule: always descale from the hi-res master — never re-shrink
   an already-small frame** (non-integer re-shrink is what looked "less clean"; verified 2026-06).
   To resize a unit later, re-descale from the master at the new scale.
4. Commit the 3 frames to `campaigns/<c>/battle_anims/<unit>/{ready,windup,peak}.png`.

### 2b. The additive clone class (the critical part)
In the unit YAML, a `battle_anim:` block:
```yaml
battle_anim:
  clone_from: archer                   # donor: timing/effects/modes + the weapon-type slot
  clone_into: CLASS_BLST_KILLER_EMPTY  # a FREE class slot -> the unit's private clone (additive)
  abbr: rbg_ar1                         # banim asset stem (<=12 chars)
  frames: [<unit>/ready.png, <unit>/windup.png, <unit>/peak.png]   # 1-3, Ready->Windup->Peak
```
`inject_battle_anims` then:
- generates the banim assets (`ref_to_battleframe.build_battle_anim`) — sheet `.4bpp`, `.agbpal`,
  `motion.s` — and **appends** one `banim_data[]` row (self-sizing table; new `anim_id`);
- **clones the donor class** into `clone_into` and gives the clone its **own** `AnimConf`, so the
  donor class + its AnimConf stay byte-vanilla and **only this unit (deployed AS the clone class)
  shows the custom anim**. Generic/enemy archers keep the vanilla anim.
- **Off-by-one, do not forget:** `GetBattleAnimationId` returns `idx - 1`, so the clone's
  `AnimConf .index` must be **`anim_id + 1`**. (Getting this wrong renders a *purple dragon*.)

Stats/growths/ranks come from donor maps in `build_campaign.py`: `STAT_DONOR`, `BASE_DONOR`,
`GROWTH_DONOR` (e.g. RBG bases from a Ch1-appropriate vanilla unit; ranks kept on a donor with the
right weapon type). `PORTRAIT_MAP` ties the unit id to its vanilla character slot. `deploy_class_for(unit)`
returns the clone class everywhere the unit is placed (defaultClass, cast-join `classIndex`,
test-chapter roster) — that's what makes the unit deploy *as* the clone.

**Picking a free `clone_into` slot:** use an unused class enum (RBG used `CLASS_BLST_KILLER_EMPTY`
0x6C). One clone per anim'd unit. Verify in-engine the unit deploys as that class number
(`pClassData->number`).

---

## 3. Battle ground platform (snow / ice)

FE8's battle platform (the ground combatants stand on) is **terrain-driven**
(`gBanimFloorfx → battle_terrain_table[idx]`, chosen by `GetBanimTerrainGround(terrainId,
chapter.battleTileSet)`). Vanilla has **no snow ground** (`siroyuka1` is pale *stone*). We vendor
real snow/ice platforms and remap terrain→ground per tile. Injector: `inject_battle_platforms`.

### 3a. Source the asset (FE-Repo, F2E)
- Repo: **`Klokinator/FE-Repo`** → `BGs, Interface Elements/Battle Frames & Backgrounds/`
  → **`{Cynon} Battle Platforms (All F2E)`** (snow/ice: `Snowdrift`, `Snow Uneven Ground`
  Light/Medium/Night, `Ice Flat`, `Ice FE6 Magically Frozen Lake`, …). Backup pack: `{WAve}`.
- Pull a specific file without cloning the 2.3 GB repo (see memory *vendor community assets*):
  ```sh
  gh api "repos/Klokinator/FE-Repo/contents/<URL-encoded path>" \
    | python3 -c "import sys,json;[print(e['download_url']) for e in json.load(sys.stdin)]"
  curl -fsSL "<download_url>" -o <local.png>
  ```
- **Format check (must be a drop-in):** indexed mode **P, 256×32, ≤16 colours, dense indices 0–15**
  — identical to vanilla `battle_terrain_*_tileset.png`. (Cynon's are; no quantizing needed.)
- **Credit the author in `CREDITS.md`** (the Community-assets table; pack ships its own F2E tag).

### 3b. Pick per the narrative, grounded in the book
Read the chapter YAML for the setting + the **Frostmaiden book** for scenery (render pages with
`pdftoppm -r 200 -f P -l P "<book.pdf>" /tmp/p`; the book is image-only — read the rendered PNGs).
The dale is the **Everlasting Rime** — perpetual twilight, no sun — so use the **Medium/Night**
palette, *not* the bright "Light", unless chosen. Record the per-chapter pick in `decisions.md`.
(RBG exercise: Prologue = `Snowdrift` (twilight-cooled), Ch1 "Iron Trail" = `Snow Uneven Ground` Light.)

### 3c. Inject it (`inject_battle_platforms`)
1. Drop the source PNG in `campaigns/<c>/platforms/<stem>.png`; add it to the `BATTLE_PLATFORMS`
   list `(png stem, symbol stem, palette tint)` — tint `0.80` cools a bright platform to twilight,
   `1.0` = as-is.
2. The injector vendors it (PNG→`.4bpp.lz` via the Makefile `gbagfx` rule + a generated `.agbpal`),
   appends an **extern** (`banim_pointer.h`), an **`.incbin`** (`data_banim_terrain.s`), and a
   **`battle_terrain_table` row** (`banim_terrain_data.c`; table self-sizes via `sizeof`). New
   grounds get indices from `PLATFORM_BASE_INDEX` (currently 115+).
3. **Terrain→ground remap** (`data_terrains.c`): `_terrain_snow_ground()` categorises every
   `TERRAIN_*` → drift / rough / ice (`_PLAT_ICE`, `_PLAT_ROUGH`, else drift). `BanimTerrainGroundDefault`
   = snow-**open** (plains→Snowdrift) for `battleTileSet 0` chapters; a new
   `BanimTerrainGround_Tileset15` = snow-**rough** (open ground→Uneven), plus its `extern`
   (`variables.h`) + a `case 0x15` in `_GetBanimTerrainGround` (`banim-battleparse.c`).
4. **Per-chapter assignment** (`chapter_settings.json`): set a chapter's `battleTileSet` to `0`
   (open/Snowdrift) or `0x15` (rough/Uneven). Prologue (idx 1) keeps 0; Ch1 (idx 2) → 0x15.
5. Add every patched decomp file to `PATCHED_DECOMP_FILES` so each build starts clean.

**For a NEW chapter:** usually just set its `battleTileSet` to 0 or 0x15. Want a third look
(e.g. a frozen-lake chapter → `Ice Flat`)? Add the ground to `BATTLE_PLATFORMS`, add a
`BanimTerrainGround_Tileset16` mapping + `case 0x16`, point the chapter at it.

---

## 4. Fast in-engine iteration & verification

- **Playtest ROM, no prologue grind:** `make CAMPAIGN=<c> TESTCH=1 fireemblem8.gba` — New Game
  boots **straight into a Ch1 sandbox** with the whole cast deployed (each unit as its clone) +
  the reskinned foes (`inject_test_chapter`, re-activated via `--test-chapter`). Plain `make` is
  the full prologue→Ch1 campaign.
- **Capture RBG firing** (currently reliable path): build the ROM, then `tools/playtest/run.sh
  recordrbg` — it builds a **fresh** `rbgch01` checkpoint (the slow prologue+lord-select once at
  240fps) and replays just the shot. **Don't reuse a checkpoint across an *injection* change** —
  the platform/anim injection shifts ROM layout and a stale save-state's pointers corrupt
  (symptom: capture shows the map/menu, never the battle). Reuse is only safe across pure
  *graphics-byte* swaps.
- **Verify the platform UNFORCED:** sample a mid-battle frame (`*-rbg.png`, ~40 % in) and confirm
  the ground resolved to snow with no force hack. (To preview a *new* ground quickly you can still
  force `gBanimFloorfx = <index>` in `banim-ekrbattleintro.c` for a throwaway build, then revert.)
- **Deliver to Nicolas:** commit a **GIF** (never MP4) to `docs/demo/` and push → he views it
  inline on GitHub (web/mobile). A committed `.mp4` is a binary download, not inline. Build the GIF
  with `tools/playtest/make_gif.py <scenario> <tag>` (default GIF; `--mp4` is local-only); keep it
  ~50 frames + `quantize(128)` ≈ 200 KB. When he's at his computer, `open map-review/<still>.png`
  works too. (See memory *remote file delivery*.)

---

## 5. Per-unit checklist (repeat this for each character/enemy)

1. **Portrait + map sprite** — YAML `art:` block; generate (Gemini) → fit/index; reskin a credited
   FE-Repo body; add `fe_name` if the name >12 chars.
2. **Battle anim** — 3 hi-res poses → BOX-descale to frames → commit; YAML `battle_anim:` block
   with a **free** `clone_into` slot; confirm `AnimConf .index == anim_id + 1`.
3. **Stats** — wire `STAT_DONOR` / `BASE_DONOR` / `GROWTH_DONOR` (and `PORTRAIT_MAP`) for the unit.
4. **Platform** (if a new look) — vendor from FE-Repo (F2E, credit), confirm 256×32 indexed,
   add to `BATTLE_PLATFORMS` + the right terrain mapping + chapter `battleTileSet`.
5. **Build + verify** — `make TESTCH=1` then `run.sh recordrbg`; check the unit deploys as its
   clone class number and fires on the right ground.
6. **Deliver** — GIF to `docs/demo/`, push, get Nicolas's sign-off **before** committing the art
   as canonical (render → show → wait → commit).
7. **Record** — credit vendored assets in `CREDITS.md`; log any new non-obvious decision (ADR) in
   `decisions.md`, same commit; build green.

---

## 6. Known gaps / next-session tasks

- **`recordrbgtest` doesn't reach the battle anim** on the TESTCH sandbox — its `captureAttack`
  A-press sequence stalls on the attack-forecast/weapon-select menu (the sandbox's menu flow
  differs from the checkpoint path). Frames come out as the menu, and the scenario still returns
  PASS (captureAttack is unconditional). **Fix:** inspect `02-rbg-deploy.png` (the state
  `captureAttack` starts from) and the early `*-rbg.png` frames, then adjust the menu navigation
  (likely an extra confirm, or wait on the action menu before the first A). Until fixed, use
  `recordrbg` with a **fresh** checkpoint. (Pipeline lane.)
- When a unit's name/anim/platform count grows, re-confirm: clone slots are still free, the banim
  table still self-sizes, and `PLATFORM_BASE_INDEX` still matches the table tail.
