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
| `Flintlocker` gunner battle animation | prof-rbg battle-anim base (candidate; #39, deferred) | **ObsidianDaddy** | F2E |
| `Tiger (U)` map sprite (stand + walk) | meesmickle aristocat map-sprite base (sandbox `meesmickle-tiger`) | **RandomWizard, Squaresoft** | F2E |
| `[Wolf-Variant] [F] Kitsune` battle animation | meesmickle battle-anim base (parked at `campaigns/.../battle_anims/_parked/`; #39, deferred) | **ZoramineFae, Clendo** | F2E |

(Each FE-Repo asset folder ships a `CREDITS.txt` — copy its exact line here when we lock the asset.)

## AI-generated art (disclose)
- **PC/cast portraits** are AI-generated (Google **Gemini / "Nano Banana"**) from reference art, then hand-fitted and indexed into FE8 portraits via our bust pipeline (`tools/ref_to_bust.py`, `tools/portrait_tool.py`). To be disclosed as AI-assisted per community norms.

## Our work
- Campaign design, YAML/data, build tooling (`tools/`), and custom pixel edits — Nicolas + Claude.
