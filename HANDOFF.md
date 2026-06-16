# Handoff: **Ch1 slice (#21) — IZOBAI BOSS PORTRAIT SHIPPED (commit 5459864, pushed). NEXT = execute the documented goblin-grunt-classes plan (issue #21 comment), then Goodberry rename, dialogue LAST.**

**Date:** 2026-06-16
**Session focus:** Goblin art for ch01 (#21, next-step #1 from last handoff). Decided the
map-sprite approach with Nicolas, built + shipped a custom **Izobai** boss portrait, and —
when reskinning the grunt classes turned out to be a campaign-wide trap — designed and
**documented a non-destructive plan** for the grunt map sprites, to be executed fresh.

**Live checklist = GitHub issue #21 (Ch1 slice). The goblin-grunt-classes execution plan
is a comment on #21:** https://github.com/NicoviGH/manchego-stars/issues/21#issuecomment-4719413468

---

## What shipped this session (commit 5459864, pushed to main)
- **Izobai boss portrait** — the Foaming Mugs goblin boss is **book canon** (a female
  Karkolohk warlord; DM notes had only "a group of goblins", unnamed — Izobai is the
  published-book name we adopted). Custom bust = **AlexYTXG's "Bandit Pegasus Knight"**
  FE-Repo mug, **recoloured to green goblin skin** (luminance-preserving ramp; red
  hair/headband/red outfit kept). Nicolas iterated: dropped a tusk+pointy-ear edit,
  chose "slightly greener than the first recolour".
- Wiring: `campaigns/.../portraits/izobai.png` (96×80, 16-colour, **0px clipped** in the
  FE8 dead-zone), `GUEST_PORTRAIT_MAP['izobai'] = 'Breguet'` in build_campaign (the
  chief's death-quote FID is FID_Breguet → that slot now shows Izobai), chief **renamed
  "Goblin Chief" → "Izobai"** in ch01 yaml. CREDITS.md rows added (Bandit Peg + goblin
  spearman).
- Verified: `make` green, `verify_text` 3404/0 runaway, **ch01win PASS** (march → Izobai
  falls → Seize → chapter 3).

## Map-sprite decisions (locked with Nicolas)
- **Grunts** (lance "Goblin Spear"/soldier, axe "Goblin Raider"/fighter): reuse the
  **one** goblin map sprite in the whole FE-Repo — **"Battle of Wesnoth (M) Goblin
  Spearman" {BoW, Norikins}** (Map Sprites/Monsters – Dragons & Special). Vendored to
  `map-review/goblin-art/goblin-spearman-{stand,walk}.png`. Sprite/weapon mismatch (spear
  art, axe combat) is fine — same as Wolfram (axe art, lance combat). Weapons stay mixed
  3-lance/3-axe (triangle lesson); NOT reclassed to all-spears.
- **Chief**: stays the **vanilla Knight** (armor-knight) map sprite — same class as
  Wolfram, so it's correct and needs no custom sprite.
- **Grunts render reddish/maroon** under the enemy faction palette (green would need a
  dedicated palette-bank engine detour — Nicolas chose to skip that).

## NEXT SESSION (in order)
1. **Execute the goblin-grunt-classes plan** (full detail = the #21 comment above).
   TL;DR: the grunts are generic **pid 0x80** → per-character sprite override impossible →
   must be class-level; but reskinning the shared `CLASS_SOLDIER`/`CLASS_FIGHTER` is
   campaign-wide (Nicolas flagged: would force every future soldier/fighter to be a goblin).
   So **clone soldier+fighter into 2 unused class slots** (GOBLIN_SOLDIER/GOBLIN_FIGHTER,
   identical stats, only the map SMS changed), assign the ch01 grunts to them via campaign
   data, keep vanilla classes human. Reversible + reusable. Mechanism stays
   campaign-agnostic in C (engine/content boundary). Verify with a **map-sprite playtest
   screenshot** (new — past shots flashed by mid-transition).
2. **Goodberry rename** (Vulnerary→Goodberry party-wide) — within this slice.
3. **Dialogue pass LAST**: Northlook opening, lord-select prompt/confirm, house hints
   0x93B/0x93C (note: 0x93C + the chief death quote still read **masculine "his/chief"** —
   update for **Izobai/female** in the dialogue pass), road sign 0x955, ending 0x954,
   chief quote 0x961; then `record` GIFs → Nicolas sign-off.
4. Carried: #29 world map; Scramsax Hero mug [F2E] license recheck; **AlexYTXG Bandit-Peg
   + BoW goblin-spearman license recheck before distribution** (no [F2E] tag on the
   bandit-peg filename); ch02+ YAML `ea_file:` schema cleanup.

## Tried / learned this session
- **FE-Repo goblin inventory is thin**: exactly ONE goblin **map sprite** (the BoW
  Spearman) and **ZERO goblin portraits** (Portrait Repository has no goblin/monster mug;
  closest is a "Moloch Sorcerer"). So the boss face had to be a **reskin of a human mug**,
  not a vendored goblin — pulled candidates from `Portrait Repository/Generic Characters
  (Villagers, Goons, and Loons)` and recoloured.
- **Skin-recolour gotchas** (all in `map-review/goblin-art/` scratch):
  (a) the warm-hue skin heuristic also catches tan **scarves** (Female Fighter v3) and
  the **bright face highlight is a near-white "cream"** the heuristic skips — include the
  cream index explicitly or the face stays pale; (b) **RGBA-key bug**: mapping keyed by
  3-tuples never matches `getpixel` 4-tuples → silent no-op (showed the original tan skin);
  key by `(r,g,b,255)`; (c) green ramp needs **g≫r** or it reads khaki/yellow.
- **Izobai is canon-female** ("a bossy goblin named Izobai", Karkolohk, escapes swearing
  revenge → recurring-villain hook). Nicolas wants her female; the green-goblin bust is.
- Map-sprite architecture (for the plan): `gClassData[]` indexed by `classId-1`
  (`bmunit.c:206`); `ClassData.SMSId`@off6 → WAIT/idle table; MOVE/walk table indexed by
  `classId-1` directly (`mu.c:1139`). Cast's per-character injection (cast palette bank
  0xB) is the WRONG tool for enemies (we want faction palette). Class enum maxes 0x7F →
  repurpose unused slots, don't extend the array.

## Current state
- ✅ Ch1 engine fully machine-verified (entry/preps/cap, lord-select force-deploy + game
  over, win-by-Seize). `make` green, `verify_text` 3404/0, playtests PASS (ch00
  win/gameover/retreat, ch01 default-lord, ch01lord, ch01win).
- ✅ **Izobai boss portrait shipped + pushed** (5459864). Nicolas approved the bust look.
- ⚠️ **Grunt map sprites NOT yet done** — plan documented on #21, ready to execute fresh.
- ⚠️ Dialogue still placeholder; gendered chief text needs the Izobai/female pass.
- ⚠️ ch01 ending MNC2(0x3) lands on vanilla Ch3 until ch02 is wired.

## Blockers
- None. (Goblin-class work is documented and ready; it's an engine/tooling task, not a blocker.)

## Key files
- `tools/build_campaign.py` — `GUEST_PORTRAIT_MAP` (izobai→Breguet), `inject_portraits`,
  `inject_ch01` (`CH01_CLASS_IDS`, `enemy_entry`, chief name/quote staging ~L2643–2905);
  for the plan: `_inject_idle_sprites`/`_inject_mu_sprites` (~L1773+, the cast path to
  branch from — but NOT reuse the cast-palette bank for enemies).
- `campaigns/rime-of-the-frostmaiden/portraits/izobai.png` — the shipped bust.
- `campaigns/.../chapters/ch01-the-iron-trail.yaml` — chief = "Izobai", goblin roster.
- `map-review/goblin-art/` — review renders (approved sheet, dead-zone preview, the
  goblin-spearman stand/walk to vendor, recolour scratch). **PNG → `open`.**
- `fireemblem8u/src/data_classes.c` + `include/bmunit.h` (ClassData/SMSId) +
  `src/unit_icon_move_data.c` (move table) — the goblin-class plan touches these.
- `tools/playtest/harness.lua` — `ch01win`/`ch01lord`; will need a map-sprite shot for
  goblin-grunt verification.

## Gotchas (carried)
- **rodata is discarded by the decomp ldscript**: injected `static const` tables / `""`
  literals → link error. Use `CONST_DATA` (.data) + vanilla dummy string pointers.
- Story text: YAML `script:` → build generates bodies; `make` overwrites manual decomp
  edits. Gate: `python3 tools/verify_text.py`.
- Odd-length NAME strings: pad with `[.]` (terminator parity).
- gDefeatTalkList: chapter-keyed entries at the HEAD; never after `{.pid=-1}`.
- Vanilla facts: `git -C fireemblem8u show HEAD:<file>` — the working tree holds OUR
  injected artifacts. **Never commit the `fireemblem8u` submodule pointer.**
- Bash cwd drifts; the built ROM lands at `fireemblem8u/fireemblem8.gba` (NOT repo root).
- Synthetic macOS keypresses don't reach mGBA; in-emulator Lua is the path. Playtest
  screenshots can land mid-transition (the death-quote frame was missed) — linger/extra A.
- PNG → `open` (Preview); GIF → `open -a Safari`.
- Pinky is male ("he"). Izobai is female ("she").
- Frostmaiden book (`references/References/icewind-dale-...pdf`, 324pp, **image-only, no
  text layer** — use `pdftoppm`) PDF page = printed + 1; DM notes
  `.../References/DungeonMasterNotesIcewindDale.pdf` (has a text layer).

## Memory
[[manchego-stars-project]] · [[feedback_custom_art_lever]] · [[feedback_nicolas_not_an_artist]] ·
[[project_manchego_stars_portrait_pipeline]] · [[feedback_show_before_committing_art]] ·
[[reference_fe_repo]] · [[feedback_vendor_community_assets]] · [[manchego-stars-automated-playtests]] ·
[[feedback_answer_before_picker]] · [[project_manchego_stars_cast_notes]] (Pinky=he; Izobai=she)

## Standing rules
Combat = pure vanilla FE; field parity with vanilla ch N is doctrine (cap = parity; chosen
lord force-deployed). Custom art on EVERY sprite part, follow concept faithfully, one
artwork at a time, **show before committing**. Story/dialogue = collaborative (variants →
Nicolas picks). Auto-push to main once green; never commit the `fireemblem8u` submodule
pointer. Playtests machine-run for logic, Nicolas for feel.
