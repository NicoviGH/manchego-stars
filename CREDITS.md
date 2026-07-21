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
| `Fire Imp (U)` map sprite (stand + walk) | ch01 goblin grunt map-sprite (soldier/fighter reskin classes; renders as a red imp under the enemy palette) | **Alexsplode** | F2E |
| `Brigand (U) Lizard Wildling` map sprite (stand + walk) | ch3 Termalaine kobold grunts (Brigand reskin, red reptile under the enemy palette) **and** Trex the recruit (recoloured onto the cast palette + gold eyes, via `tools/map_sprite_swapper.py`) | **Tarantino500** | F2U/F2E |
| `Berserker (M) Lizardzerker Axe` map sprite (stand + walk) | ch3 blade-kobold / Kobold Skirmisher (Mercenary reskin on a NEW appended class `0x80`, tall crested red reptile — distinct from the squat Wildling grunts) | **Seliost1** | F2U/F2E |
| `Chocobo Rider (F) Lance` map sprite (stand + walk) | Baxby the axe-beak map-sprite base (rider + lance stripped, recolored to a snowy tundra axe-beak; hand-reskinned by Nicolas in `tools/map_sprite_editor.py`) | **SkidMarc25** | no tag in filename — recheck before distribution |
| `{Cynon} Battle Platforms` — Snowdrift, Snow Uneven Ground (Light), Ice Flat | battle-anim ground platforms for the snow chapters (vendored at `campaigns/.../platforms/`, injected into `battle_terrain_table` + the terrain→ground remap by `inject_battle_platforms`, #65); Snowdrift twilight-cooled | **Cynon** | F2E (pack title: "All F2E") |
| `Assorted CGs {Zeldacrafter}` — Snowy Village | Targos ch02-ending event background (frozen Ten-Towns street at nightfall; cropped to 240×160 + FE8-banked by `tools/bg_to_fe8.py`, injected as a new `gConvoBackgroundData` slot by `inject_backgrounds`, #22) | **Zeldacrafter** | F2E (folder tag `{Zeldacrafter}`; source is a Tales of Berseria scene — recheck before distribution) |
| `Skeleton (Assassin)` portrait | Sahnar the spectral-skeleton blademaster — bust (hooded skeletal assassin; red hood recolored to the cast slate cloak; vendored at `campaigns/.../portraits/vendor/`) | **Glaceo** | F2E |
| `Bonewalker (U) Specter` map sprite (stand + walk) | Sahnar map sprite base (cast-palette slate recolor, spectral glow dropped) | **Alexsplode** | F2E |
| `[Skeleton-Custom] Specter` battle animation (sword) | Sahnar battle anim — DECIDED, injection deferred (#39/#90); native palette, not yet vendored (source pointer in `npcs/sahnar.yaml`) | **Alexsplode** | F2E |

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
| "Rockruff & Lycanroc Overworlds" sprite sheet (Midday form, 4-direction walk) | Lupin map sprites (`map_sprites/lupin{,_mu}.png`, recoloured to the cast grey ramp + hand-drawn glasses) | fan art by **princess-phoenix**, derived from © **Nintendo / Creatures / GAME FREAK** designs | [princess-phoenix, DeviantArt](https://www.deviantart.com/princess-phoenix/art/Rockruff-and-Lycanroc-Overworlds-722268380) — **CC-BY 3.0** ("feel free to use these in any of your pokemon projects!") |

(Lupin's *portrait* is separate — the TotalityDesigns hipster-wolf ref, credited above under community/AI art.
Battle anim deferred; PMD SpriteCollab has Lycanroc `sprite/0745` in the same style for later.)

### Map tilesets (used as-is; the shared snow tileset for the MVP)
| Asset | Used for | Authors | Source | License |
|---|---|---|---|---|
| **Snowy Bern / Snowy Peaks** tileset (graphics + palette + tile config) | the campaign's shared winter tileset (Prologue town → Ch8 ice canyon) | **ZoramineFae** (assembled the insertable version), **Vennobennu** ("Snowy Peaks Revised" updates), **FEAW** (2015 original), **Sme** (original Discord source) | [FEUniverse t/7204](https://feuniverse.us/t/snowy-bern-snowy-peaks-tileset/7204) | F2U (community free-to-use with credit) |
| **Snowy Fields** (Fields + Customs, Snow palette; graphics + palette + tile config) | intact on-hand winter alternative (`maps/tilesets/snowy-fields/`) for chapters whose full-map visual language fits Fields better than Snowy Bern; not currently selected by a chapter | **N426** (Snow variant); bundled source-family credits also name **Dark, MaxTheMagelord, WAve, RandomWizard, Beast, Zarg**; base GBAFE Fields art © **Nintendo / Intelligent Systems** | [N426's resource thread](https://feuniverse.us/t/n426s-mediocre-sprite-works-and-general-bad-ideas/6943) and [Klokinator/FE-Repo](https://github.com/Klokinator/FE-Repo) → `Tilesets/Fields/FE7 Fields + Customs - Tileset` (bundled `CREDITS.txt` vendored alongside) | FE-Repo F2U default; recheck creator terms before distribution |
| **FE8 Fields Remaster / Super Fields** — native Snag family only | two brown Snag variants cherry-picked into Snowy Bern metatiles 8/35 for Ch4 (#24); the complete green-grass tileset is not retained | **WAve, RandomWizard, Beast**; base GBAFE Fields art © **Nintendo / Intelligent Systems** | [Klokinator/FE-Repo](https://github.com/Klokinator/FE-Repo) → `Tilesets/Fields/FE8 - Fields - Remaster - Super Fields - Tileset` | FE-Repo F2U default; recheck creator terms before distribution |
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
- **Tour drawn-map A** (`events/tour-map-a-dale.*`) is a Gemini repaint of the book's regional Icewind Dale map (Magvel-style restyle, prompt-run by Nicolas), then converted/re-lettered by `tools/gen_drawnmap.py`.

## Our work
- Campaign design, YAML/data, build tooling (`tools/`), and custom pixel edits — Nicolas + Claude.
