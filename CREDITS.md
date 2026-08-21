# Credits

Manchego Stars is a private, non-commercial ROM hack of *Fire Emblem: The Sacred Stones*
shared with the campaign's players. This file tracks everyone whose work we build on.

> **TODO (before distribution):** align this to the proper community crediting format.
> GBAFE assets have conventions (FEUniverse credit threads, each asset's bundled
> `CREDITS.txt`, the F2E/F2U distinction) and we should copy each adopted asset's exact
> credit line. Also disclose **AI-generated art** (the PC portraits — see below) per current
> norms. For now this is a running list so nothing goes uncredited.

## Engine / base
- **Fire Emblem: The Sacred Stones** © Nintendo / Intelligent Systems — the base game (private hack; not redistributed as a commercial product).
- **`fireemblem8u`** — the FE8 decompilation by the **FireEmblemUniverse** decomp team. We build the ROM from it.
- Toolchain: `agbcc`, `gbagfx`, and the other decomp tools bundled in `fireemblem8u/tools/`.

## Community assets (F2E = free-to-edit; we reskin/recolour these)
Source: **[Klokinator/FE-Repo](https://github.com/Klokinator/FE-Repo)** (community asset repository). Per-asset authors:

| Asset | Used for | Author | License |
|---|---|---|---|
| `Cowboy (M) Gun` map sprite (stand + walk) | prof-rbg gunslinger map-sprite base (candidate) | **MeatofJustice** | F2E |
| `Flintlocker` gunner battle animation | prof-rbg battle-anim base (candidate; superseded — RBG's shipped anim (#65) uses descaled custom poses) | **ObsidianDaddy** | F2E |
| `Tiger (U)` map sprite (stand + walk) | meesmickle aristocat map-sprite base (candidate; sandbox copy not kept in-tree — re-vendor from FE-Repo when picked up) | **RandomWizard, Squaresoft** | F2E |
| `[Wolf-Variant] [F] Kitsune` battle animation | meesmickle battle-anim base (parked at `campaigns/.../battle_anims/_parked/`; alternative to the #65 descaled-pose path) | **ZoramineFae, Clendo** | F2E |
| `Pirate Lady (Version 3)` portrait | Hlin Trollbane ch00 guest portrait (silver-haired age recolor; vendored at `campaigns/.../portraits/vendor/`) | **Cygnus** | F2E |
| `Hero` portrait | Scramsax ch00 guest portrait (used as-is; vendored at `campaigns/.../portraits/vendor/`) | **LaurentLacroix, UltraFenix, monk-han** | no tag in filename — recheck before distribution |
| `Bandit Pegasus Knight` portrait | Izobai ch01 goblin boss portrait (green-goblin skin reskin; dresses the Breguet slot) | **AlexYTXG** | no tag in filename — recheck before distribution |
| `Generic Villager` portrait | Hruna ch01 Foaming Mugs quest-giver (periwinkle→olive-wool coat recolor; vendored at `campaigns/.../portraits/vendor/`) | **Cynon** | F2E |
| `Sonya (Witch, FE8 colours)` portrait | Vellynne Harpell ch02 quest-giver (recurring Arcane Brotherhood necromancer; magenta→snow-white hair recolor via `portraits/vellynne.py`, dresses the Ismaire slot) | **JeyTheCount** | F2E |
| `Aversa` portrait | Ravisin ch05 boss (silver→auburn hair and warm→frost-pale skin palette edit via `portraits/ravisin.py`; original brown markings and pixel geometry retained; dresses the Riev slot) | **Garytop** | F2E |
| `Skeleton (Armour, version 1)` portrait | Ch05 undead Arena Master (used as-is; build-dressed onto the otherwise-unused Glen face slot; source pinned to FE-Repo commit `3abc62d4f0a12d300911b51788719f950c5f45b9`) | **Generic Pretsel** | F2E |
| `Fire Imp (U)` map sprite (stand + walk) | ch01 goblin grunt map-sprite (soldier/fighter reskin classes; renders as a red imp under the enemy palette) | **Alexsplode** | F2E |
| `Brigand (U) Lizard Wildling` map sprite (stand + walk) | ch3 Termalaine kobold grunts (Brigand reskin, red reptile under the enemy palette) **and** Trex the recruit (recoloured onto the cast palette + gold eyes, via `tools/map_sprite_swapper.py`) | **Tarantino500** | F2U/F2E |
| `Berserker (M) Lizardzerker Axe` map sprite (stand + walk) | ch3 blade-kobold / Kobold Skirmisher (Mercenary reskin on a NEW appended class `0x80`, tall crested red reptile — distinct from the squat Wildling grunts) | **Seliost1** | F2U/F2E |
| `Chocobo Rider (F) Lance` map sprite (stand + walk) | Baxby the axe-beak map-sprite base (rider + lance stripped, recolored to a snowy tundra axe-beak; hand-reskinned by Nicolas in `tools/map_sprite_editor.py`) | **SkidMarc25** | no tag in filename — recheck before distribution |
| `[Custom DM] Awakening Dark Mage [F]` battle animation | Ravisin, ch05's frost-druid boss — a STAND-IN chosen to match her Aversa bust (the FE-Repo has no Aversa anim; vendored at `campaigns/.../battle_anims/ravisin/` and bound per-CHARACTER via `_u25`, #25; ships on a HAND-EDITED palette — black robe over near-white skin, matching her bust's "frost-pale skin, black feather mantle", with the anim's own auburn hair untouched. Five of fifteen entries move, via `palette_edit:` → `tools/banim_palette.py`; the author's enemy palette was rejected on sight because it recolours her hair) | still by **BatimatheBat**, animation by **Leo_Link** | F2U/F2E |
| `Druid Hoodless (F)` map sprite (stand + walk) | Ravisin's overworld sprite (#25) — vendored whole, converted onto the cast palette by `map_sprite_tool.recolour`, then index-swapped by Nicolas to match her battle anim (black robe / near-white skin / auburn hair). Chosen HOODLESS to agree with her bust and anim, against `CLASS_DRUID`'s stock hooded man; bound on her RAW pid via `SCRIPTED_NEUTRAL_SPRITES` | **Ultra-Fenix, Velvet Kitsune** | no tag in filename — recheck before distribution |
| `{Cynon} Battle Platforms` — Snowdrift, Snow Uneven Ground (Light), Ice Flat, Snow Dirt Path | battle-anim ground platforms for the snow chapters (vendored at `campaigns/.../platforms/`, injected into `battle_terrain_table` + the terrain→ground remap by `inject_battle_platforms`, #65); Snowdrift twilight-cooled, Snow Dirt Path as-is on TERRAIN_ROAD | **Cynon** | F2E (pack title: "All F2E") |
| `Assorted CGs {Zeldacrafter}` — Snowy Village | Targos ch02-ending event background (frozen Ten-Towns street at nightfall; cropped to 240×160 + FE8-banked by `tools/bg_to_fe8.py`, injected as a new `gConvoBackgroundData` slot by `inject_backgrounds`, #22) | **Zeldacrafter** | F2E (folder tag `{Zeldacrafter}`; source is a Tales of Berseria scene — recheck before distribution) |
| `Fenriel's BG` — Winter BG 06, Winter BG 04 | Bryn Shander's ch01-ending event background (walled snowbound town at dusk, #21) and Bremen's, reserved for ch07 (alpine lakeside town, #27). Both already 240×160; FE8-banked by `tools/bg_to_fe8.py` (8-bank refit) and injected as new `gConvoBackgroundData` slots by `inject_backgrounds` | **Fenriel** | folder tag `{Fenriel}`; both are photo-derived (real Alpine towns) — recheck before distribution, as with the Targos CG |
| `FE9-10 CG Rips` — Castle Interior 3 Winter Day | ch05's opening event background (`BG_MS_ELVEN_TOMB`): the snowed-in elven stonework behind the three scenes that play before the party arrives (#25). The FIRST vendored BG needing no refit — the rip already ships mode-P at 16 colours, so `tools/bg_to_fe8.py`'s greedy pack reproduces it EXACTLY (0 of 38400 pixels differ from the 5-bit source picture). The rip is LETTERBOXED — a 240-wide picture inside a 256-wide canvas — so `trim_uniform_border` strips the flat mat and the picture lands 1:1 with no scaling and no crop of real art at all. Injected as a new `gConvoBackgroundData` slot by `inject_backgrounds` | **uncredited rip** (folder `FE9-10 CG Rips`) | no per-file tag — a Tellius (FE9/10) CG rip, so **recheck before distribution**, as with the Targos and Fenriel CGs |
| `FE9-10 CG Rips` — Forest Outskirts 4 winter Day | ch05 scene 4's event background (`BG_MS_FOREST_OUTSKIRTS_WINTER`): the snowbound ridge the party crests before the map loads (#25) — the opening's second backdrop, cut to when the party physically arrives, as vanilla Ch5 cuts `BG_SERAFEW_VILLAGE`→`BG_TOWN` at the same beat. Same rip family as `BG_MS_ELVEN_TOMB` and needs no refit either: mode-P at 16 colours in, 0 of 38400 pixels different from the 5-bit source picture out — same letterbox mat as the tomb, stripped by `trim_uniform_border`, so it lands 1:1. Packs onto 3 banks, inside the six the fade procs apply. Injected as a new `gConvoBackgroundData` slot by `inject_backgrounds` | **uncredited rip** (folder `FE9-10 CG Rips`) | no per-file tag — a Tellius (FE9/10) CG rip, so **recheck before distribution**, as with the Targos and Fenriel CGs |
| `Skeleton (Assassin)` portrait | Sahnar the spectral-skeleton blademaster — bust (hooded skeletal assassin; red hood recolored to the cast slate cloak; vendored at `campaigns/.../portraits/vendor/`) | **Glaceo** | F2E |
| `Bonewalker (U) Specter` map sprite (stand + walk) | Sahnar map sprite base (cast-palette slate recolor, spectral glow dropped) | **Alexsplode** | F2E |
| `[Skeleton-Custom] Specter` battle animation (sword) | Sahnar battle anim — VENDORED + WIRED (#25); the full 12-mode FE-native script imported verbatim by `feditor_to_banim` (101 frames), in its **native palette** (deliberately not recolored to her cloak). Assets at `campaigns/.../battle_anims/sahnar/` | **Alexsplode** | F2E |
| `Cantor` portrait | ch05 reliquary-north resident — the tomb's cantor, who sang here when the place was an amphitheatre (dresses the `Man_Unused` slot; derived at build time by `inject_ch05_visit_faces`) | **Eden, L95** | F2E |
| `Skeleton (Mage, version 1)` portrait | ch05 reliquary-west resident — the tomb's archivist (dresses `Villager_Young_Man`) | **L95, BladerDj** | F2E |
| `Skeleton` portrait | ch05 reliquary-east resident — the tomb's quartermaster (dresses `Villager_Man_1`) | **L95** | F2E |
| `Skeleton (Full Smile)` portrait | ch05 reliquary-south resident — the cheerful one (dresses `Villager_Man_2`; orange pauldrons recolored verdigris to separate him from the east resident, who is the same body with a different jaw) | **L95, Nokitrix** | F2E |

| `[Custom Halb] Skeleberdier` battle animation (lance, axe, handaxe) | ch05's `risen-spear` and `tomb-reaver` — VENDORED + WIRED (#25). **One import dresses two classes**: the lance guard and all eight axe reavers, because this anim ships Lance, Axe (Swing/Stab) and Handaxe together. That closes what `docs/fe-repo-scouting.md` had recorded as a hard gap ("no undead axe anim"), which had ch05's biggest enemy block planned as a palette-swap of a LIVING Fighter. Imported verbatim by `feditor_to_banim` in its native bone-and-steel palette. Assets at `engine/battle_anims/_vendored/skeleberdier/` | **TheBlindArcher** (base); **Spud**, **MeatofJustice** (improvements); **UltraFenix** (reskin, commissioned by d_h); **tatata** (axe + handaxe modes) | F2U/F2E |
| `[Skeleton-Base] Bonewalker (one arm, sword)` battle animation | ch05's `crypt-blade` — VENDORED + WIRED (#25), in its native palette. Paired with the matching One Arm map sprite so the field and the close-up are the same body. Deliberately NOT the Specter, which is Sahnar's, so the named recruit does not read as one of the line | **IS** (vanilla skeleton); **Alexsplode** (one-arm edit) | F2U/F2E |
| `[Skeleton-Reskin] Wight Sniper` battle animation (bow) | ch05's `bone-archer` — VENDORED + WIRED (#25), in its native palette. Ships no unarmed mode, so the bow anim takes the unarmed weapon-type as well; without that an archer holding nothing falls back to the vanilla LIVING archer | **DATonDemand** | F2U/F2E |
| `Bonewalker (U)` map sprites — Lance, Axe, One Arm, Wight Bow (stand + walk) | ch05's four risen tomb-guard classes on the map (#25). Normalised to one palette index per distinct colour before vendoring: the Axe walk sheet spent 20 indices on 14 colours and the One Arm pair shipped RGBA, both of which the build's guards reject. Remapped onto each base class's SMS palette at build time, so the enemy faction palette colours them | **Epicer** (Lance); **Snerdels** (Axe); **IS** (One Arm, Wight Bow) | F2U/F2E |
(Each FE-Repo asset folder ships a `CREDITS.txt` — copy its exact line here when we lock the asset.)

## Pokémon-sourced assets (adopted sprite art)
Some cast sprites adopt Pokémon art, reskinned onto our cast palette; private non-commercial use,
same footing as the FE8 base game itself. Recheck before any wider distribution.

**Basil the goodberry shrub — Oddish (#43):**

| Asset | Used for | Origin | Source |
|---|---|---|---|
| PMD *Explorers of Sky* Oddish animation sheets (Idle/Walk/Charge/Shoot + Shadow) | Basil map sprites (`map_sprites/basil{,_mu}.png`, recoloured onto the cast palette) + battle-anim frames (`battle_anims/basil/`, 1.5x hqx) | © **Nintendo / Creatures / GAME FREAK / Spike Chunsoft** (official game rips, credited `CHUNSOFT` in the repo) | [PMDCollab/SpriteCollab](https://github.com/PMDCollab/SpriteCollab) `sprite/0043` |
| Oddish FireRed/LeafGreen battle sprite | Basil portrait (`portraits/basil.png`, hq2x + 16-colour fit; source vendored at `data/portraits/basil.png`) | © **Nintendo / Creatures / GAME FREAK** | [PokeAPI/sprites](https://github.com/PokeAPI/sprites) `generation-iii/firered-leafgreen/43.png` |

(The PMD SpriteCollab fan-made emotion portraits were evaluated but NOT shipped — the shipped
portrait derives from the official FRLG sprite only.)

**Lupin the direwolf — Lycanroc (#745):**

| Asset | Used for | Origin | Source |
|---|---|---|---|
| "Rockruff & Lycanroc Overworlds" sprite sheet (Midday form, 4-direction walk) | Lupin map sprites (`map_sprites/lupin{,_mu}.png`, recoloured to the cast grey ramp + hand-drawn glasses) **and ch04's parleyed wolf pack** (`map_sprites/lycanroc-pack{,_mu}.png` — the same Midday frames without glasses, indexed to FE8's standard SMS roles so the green NPC palette colours them) | fan art by **princess-phoenix**, derived from © **Nintendo / Creatures / GAME FREAK** designs | [princess-phoenix, DeviantArt](https://www.deviantart.com/princess-phoenix/art/Rockruff-and-Lycanroc-Overworlds-722268380) — **CC-BY 3.0** ("feel free to use these in any of your pokemon projects!") |

(Lupin's *portrait* is separate — the TotalityDesigns hipster-wolf ref, credited above under community/AI art.
His *battle anim* is separate again — Gemini-generated poses, disclosed below. PMD SpriteCollab's
Lycanroc `sprite/0745` was evaluated and RULED OUT for it: real and complete, but dungeon-sprite
art (72x80 frames holding a ~37x28 chibi), so it reads as a different game beside our FE8-scale
anims.)

**The White Moose — Wyrdeer (#899):**

| Asset | Used for | Origin | Source |
|---|---|---|---|
| "Wyrdeer - full sprite" sheet (mainline layout: front/back battle sprites, icons, palette ramps, 4-direction × 4-frame overworld walk at 32×32) | The White Moose **map sprite** (`map_sprites/white-moose{,_mu}.png`, indexed to the cast palette + canon blood staining) and **portrait** (`portraits/white-moose.png`, full-creature bust from the 96×96 front cell). Used in ch04 (scripted neutral quarry) and ch05 (miniboss). | fan art by **Anarlaurendil**, derived from © **Nintendo / Creatures / GAME FREAK** designs | [Anarlaurendil, DeviantArt](https://www.deviantart.com/anarlaurendil/art/Wyrdeer-full-sprite-889409543) — **CC BY-SA 3.0**; original vendored at `campaigns/.../portraits/vendor/` |

(Chosen over an FE-Repo reskin because the repo has **no elk/deer/stag art at all** — only wolves/hounds and
horse-bodied centaurs — and a repainted hound would read as one of ch04's own wolves. See
`docs/fe-repo-scouting.md`. The blood staining follows the book plate, *Rime of the Frostmaiden* p.81.
Battle anim still owed for ch05 (#25); PMD SpriteCollab has Wyrdeer `sprite/0899` — **CC BY-NC 4.0** —
whose `RearUp`/`Attack`/`Charge` supply the three poses `inject_battle_anims` needs.)

### Map tilesets (used as-is; the shared snow tileset for the MVP)
| Asset | Used for | Authors | Source | License |
|---|---|---|---|---|
| **Snowy Bern / Snowy Peaks** tileset (graphics + palette + tile config) | the campaign's shared winter tileset (Prologue town → Ch8 ice canyon) | **ZoramineFae** (assembled the insertable version), **Vennobennu** ("Snowy Peaks Revised" updates), **FEAW** (2015 original), **Sme** (original Discord source) | [FEUniverse t/7204](https://feuniverse.us/t/snowy-bern-snowy-peaks-tileset/7204) | F2U (community free-to-use with credit) |
| **Snowy Fields** (Fields + Customs, Snow palette; graphics + palette + tile config) | intact on-hand winter alternative (`maps/tilesets/snowy-fields/`) for chapters whose full-map visual language fits Fields better than Snowy Bern; not currently selected by a chapter | **N426** (Snow variant); bundled source-family credits also name **Dark, MaxTheMagelord, WAve, RandomWizard, Beast, Zarg**; base GBAFE Fields art © **Nintendo / Intelligent Systems** | [N426's resource thread](https://feuniverse.us/t/n426s-mediocre-sprite-works-and-general-bad-ideas/6943) and [Klokinator/FE-Repo](https://github.com/Klokinator/FE-Repo) → `Tilesets/Fields/FE7 Fields + Customs - Tileset` (bundled `CREDITS.txt` vendored alongside) | FE-Repo F2U default; recheck creator terms before distribution |
| **FE8 Fields Remaster / Super Fields** — native Snag family only | two brown Snag variants cherry-picked into Snowy Bern metatiles 8/35 for Ch4 (#24); the complete green-grass tileset is not retained | **WAve, RandomWizard, Beast**; base GBAFE Fields art © **Nintendo / Intelligent Systems** | [Klokinator/FE-Repo](https://github.com/Klokinator/FE-Repo) → `Tilesets/Fields/FE8 - Fields - Remaster - Super Fields - Tileset` | FE-Repo F2U default; recheck creator terms before distribution |
| **Village - Port or Town** tileset, **Winter Nighttime** palette (graphics + palette + tile config) | Ch5 "The Elven Tomb" — vanilla FE8 Ch5's geometry retiled as a snowbound elven tomb (`maps/tilesets/port-or-town-winter/`, #25) | **Cynon**, **WaVe**, **Atlas** (Winter Nighttime palette); base GBAFE Village art © **Nintendo / Intelligent Systems** | [Klokinator/FE-Repo](https://github.com/Klokinator/FE-Repo) → `Tilesets/Towns & Villages/Village - Port or Town {Cynon, WaVe, Atlas}` (bundled `CREDITS.txt` vendored alongside) | FE-Repo F2U default; recheck creator terms before distribution |
| **Cynon's Mineshaft** tileset, Gray palette (graphics + palette + tile config) | Ch3 "The Termalaine Mine" cave interior (`maps/tilesets/cave-interior/`, #40/#23) | **Cynon**; additional credits **GoudaGrabber** (rolling stock, north stairway), **Atlas** (one of the palettes); adapts tiles from FE6/7/8, FF4/6, PMD, RPG Maker 2000/2003, Pokémon G/S/C, Treasure of the Rudras, Thomas the Tank Engine (CD32) | [Klokinator/FE-Repo](https://github.com/Klokinator/FE-Repo) → `Tilesets/Caves/Cynon's Mineshaft - Tileset` (bundled `CREDITS.txt` vendored alongside) | F2E; author explicitly endorses cross-engine conversion |
| **FF5 Caves** tileset — navy dungeon-chest (closed/open) | the chest cherry-picked into `cave-interior` metatiles **17** (closed, terrain `0x21`) / **29** (open, `0x20`) on palette bank 5 for Ch3 (#40); full tileset vendored on-hand at `maps/tilesets/ff5-caves/` for future chapters | **WAve** | [Klokinator/FE-Repo](https://github.com/Klokinator/FE-Repo) → `Tilesets/Caves/FF5 - Caves - Tileset` (bundled `CREDITS.txt` vendored alongside) | FE-Repo; explicit license not in bundled CREDITS — recheck before distribution |
| **Lava Cave (Remaster)** tileset (graphics + palette + tile config) | on-hand cave/volcanic tileset for future chapters (`maps/tilesets/lava-cave/`) — not yet used | **HyperGammaSpaces** | [Klokinator/FE-Repo](https://github.com/Klokinator/FE-Repo) → `Tilesets/Caves/Lava Cave - Remaster - Tileset` (bundled `CREDITS.txt` vendored alongside) | FE-Repo; explicit license not in bundled CREDITS — recheck before distribution |

## Purchased assets
| Asset | Used for | Author | Source / License |
|---|---|---|---|
| **Icewind Dale: Ten-Towns Hand Drawn Maps and NPC Builder** (2021) — the ten-towns hand-drawn map (weathered + clean variants) + NPC builder tables | tour drawn-map B (`events/tour-map-b-towns.*`, icy duotone + re-lettering via `tools/gen_drawnmap.py`); NPC builder informs story/NPC work | **Joel Kleine** (@midlifedices) | purchased: [DriveThru product 353776](https://www.drivethrucomics.com/en/product/353776/icewind-dale-ten-towns-hand-drawn-maps-and-npc-builder); published under the DMs Guild Community Content Agreement |

## Campaign source material (Wizards of the Coast)
- ***Icewind Dale: Rime of the Frostmaiden*** © Wizards of the Coast — the campaign this hack adapts (privately, for its own players). Book art reused in-ROM: the ch1 opener aurora-township painting (lore-crawl mural), the regional Icewind Dale map (basis/reference for the world-tour backdrops), and the **axe-beak illustration** (the reference for Baxby's portrait — see AI-generated art below).

## AI-generated art (disclose)
- **PC/cast portraits** are AI-generated (Google **Gemini / "Nano Banana"**) from reference art, then hand-fitted and indexed into FE8 portraits via our bust pipeline (`tools/ref_to_bust.py`, `tools/portrait_tool.py`). To be disclosed as AI-assisted per community norms.
- **Baxby the axe-beak portrait** — the reference is the **axe-beak illustration from *Rime of the Frostmaiden*** (© Wizards of the Coast), modified with Google **Gemini** (prompt-run by Nicolas), then fitted/indexed via the bust pipeline (`tools/ref_to_bust.py --crop 780,18,1920,940 --flip-h --zoom 0.88`). Disclose as both AI-assisted and WotC-derived.
- **Lupin the direwolf portrait** — the reference is **"Hipster Wolf Head With Glasses"** by **TotalityDesigns** (Redbubble listing; found image supplied by Nicolas, 2026-07-03 — private non-commercial use, recheck before any wider distribution; original vendored at `campaigns/.../portraits/vendor/`), fitted/indexed via the bust pipeline (`tools/ref_to_bust.py --crop " -206,0,1033,1032" --zoom 1.0` + the `portraits/lupin_darken.py` ink-deepening pass). Not AI-generated.
- **Lupin the direwolf BATTLE ANIM** (`campaigns/.../battle_anims/lupin/`) — four hi-res poses (idle /
  windup / lunge / hit) generated with Google **Gemini** (prompt-run by Nicolas, 2026-08-02), matched to
  his existing portrait and map sprite; split + de-shadowed by `tools/split_pose_sheet.py`, downscaled and
  arranged into the pounce by `tools/poses_to_feditor.py`. **His spectacles are hand-painted by Nicolas at
  FE8 scale** (`tools/banim_paint.py`) — they are ~4x3 px after the shrink and no generated pass carries
  them. Disclose as AI-assisted.
- **Tour drawn-map A** (`events/tour-map-a-dale.*`) is a Gemini repaint of the book's regional Icewind Dale map (Magvel-style restyle, prompt-run by Nicolas), then converted/re-lettered by `tools/gen_drawnmap.py`.

## Our work
- Campaign design, YAML/data, build tooling (`tools/`), and custom pixel edits — Nicolas + Claude.
