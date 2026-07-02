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
| `Chocobo Rider (F) Lance` map sprite (stand + walk) | Baxby the axe-beak map-sprite base (rider + lance stripped, recolored to a snowy tundra axe-beak; hand-reskinned by Nicolas in `tools/map_sprite_editor.py`) | **SkidMarc25** | no tag in filename — recheck before distribution |
| `{Cynon} Battle Platforms` — Snowdrift, Snow Uneven Ground (Light), Ice Flat | battle-anim ground platforms for the snow chapters (vendored at `campaigns/.../platforms/`, injected into `battle_terrain_table` + the terrain→ground remap by `inject_battle_platforms`, #65); Snowdrift twilight-cooled | **Cynon** | F2E (pack title: "All F2E") |
| `Assorted CGs {Zeldacrafter}` — Snowy Village | Targos ch02-ending event background (frozen Ten-Towns street at nightfall; cropped to 240×160 + FE8-banked by `tools/bg_to_fe8.py`, injected as a new `gConvoBackgroundData` slot by `inject_backgrounds`, #22) | **Zeldacrafter** | F2E (folder tag `{Zeldacrafter}`; source is a Tales of Berseria scene — recheck before distribution) |

(Each FE-Repo asset folder ships a `CREDITS.txt` — copy its exact line here when we lock the asset.)

### Map tilesets (used as-is; the shared snow tileset for the MVP)
| Asset | Used for | Authors | Source | License |
|---|---|---|---|---|
| **Snowy Bern / Snowy Peaks** tileset (graphics + palette + tile config) | the campaign's shared winter tileset (Prologue town → Ch8 ice canyon) | **ZoramineFae** (assembled the insertable version), **Vennobennu** ("Snowy Peaks Revised" updates), **FEAW** (2015 original), **Sme** (original Discord source) | [FEUniverse t/7204](https://feuniverse.us/t/snowy-bern-snowy-peaks-tileset/7204) | F2U (community free-to-use with credit) |

## Purchased assets
| Asset | Used for | Author | Source / License |
|---|---|---|---|
| **Icewind Dale: Ten-Towns Hand Drawn Maps and NPC Builder** (2021) — the ten-towns hand-drawn map (weathered + clean variants) + NPC builder tables | tour drawn-map B (`events/tour-map-b-towns.*`, icy duotone + re-lettering via `tools/gen_drawnmap.py`); NPC builder informs story/NPC work | **Joel Kleine** (@midlifedices) | purchased: [DriveThru product 353776](https://www.drivethrucomics.com/en/product/353776/icewind-dale-ten-towns-hand-drawn-maps-and-npc-builder); published under the DMs Guild Community Content Agreement |

## Campaign source material (Wizards of the Coast)
- ***Icewind Dale: Rime of the Frostmaiden*** © Wizards of the Coast — the campaign this hack adapts (privately, for its own players). Book art reused in-ROM: the ch1 opener aurora-township painting (lore-crawl mural), the regional Icewind Dale map (basis/reference for the world-tour backdrops), and the **axe-beak illustration** (the reference for Baxby's portrait — see AI-generated art below).

## AI-generated art (disclose)
- **PC/cast portraits** are AI-generated (Google **Gemini / "Nano Banana"**) from reference art, then hand-fitted and indexed into FE8 portraits via our bust pipeline (`tools/ref_to_bust.py`, `tools/portrait_tool.py`). To be disclosed as AI-assisted per community norms.
- **Baxby the axe-beak portrait** — the reference is the **axe-beak illustration from *Rime of the Frostmaiden*** (© Wizards of the Coast), modified with Google **Gemini** (prompt-run by Nicolas), then fitted/indexed via the bust pipeline (`tools/ref_to_bust.py --crop 780,18,1920,940 --flip-h --zoom 0.88`). Disclose as both AI-assisted and WotC-derived.
- **Tour drawn-map A** (`events/tour-map-a-dale.*`) is a Gemini repaint of the book's regional Icewind Dale map (Magvel-style restyle, prompt-run by Nicolas), then converted/re-lettered by `tools/gen_drawnmap.py`.

## Our work
- Campaign design, YAML/data, build tooling (`tools/`), and custom pixel edits — Nicolas + Claude.
