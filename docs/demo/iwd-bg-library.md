# Icewind Dale / winter event-BG library (FE-Repo candidates)

Vendorable cutscene backgrounds (`BACG` / `gConvoBackgroundData[]`) for the frozen-north chapters.
All sourced from **`Klokinator/FE-Repo`** under `BGs, Interface Elements/Background CGs/`. Pull a file
the usual way (never clone the repo): `gh api "repos/Klokinator/FE-Repo/contents/<url-encoded path>"`
→ `download_url` → `curl`. Contact sheet: `iwd-bg-shortlist.png`.

**FE8 import caveats:** event BGs are **240×160, 4bpp (16-color sub-palettes)**. The Fenrier/Fenreir
sets are already native 240×160; the others are 256×160 community exports and need a 16px center-crop.
These are detailed modern CGs — expect a **palette-reduction pass** to FE8's 16-color limit, which will
shift their look. Add to a NEW `gConvoBackgroundData[]` slot (**additive, never edit a vanilla entry**)
and **credit the author in `CREDITS.md`**.

| Theme | FE-Repo path (under `Background CGs/`) | Credit | Res | Local file |
|---|---|---|---|---|
| Snowy tundra / frozen forest + fence | `Fenriel's BG/Winter BG 01.png` | Fenrier | 240×160 | `winter-fenrier-01.png` |
| Aurora ice path | `Fenriel's BG/Winter BG 03.png` | Fenrier | 240×160 | `winter-fenrier-03.png` |
| Snowy town street (night) | `Fenriel's BG/Winter BG 05.png` | Fenrier | 240×160 | `winter-fenrier-05.png` |
| Winter scenes (alternates) | `Fenriel's BG/Winter BG 0{2,4,6}.png` | Fenrier | 240×160 | `winter-fenrier-0{2,4,6}.png` |
| Frozen town (day) | `Assorted CGs {Zeldacrafter}/Snowy Village (Tales of Berseria).png` | Zeldacrafter (Berseria rip) | 256×160 | `snowtown-zeldacrafter.png` |
| Snowy ruins / abandoned keep | `Assorted CGs {Zeldacrafter}/Snowy ruins.png` | Zeldacrafter | 256×160 | `snowruins-zeldacrafter.png` |
| Frozen keep / ice fortress | `WAve's BGs {WAve} [F2E]/Blue Castle.png` | WAve **[F2E]** | 256×160 | `frozenkeep-wave-bluecastle.png` |
| Mountains / Spine of the World | `WAve's BGs {WAve} [F2E]/Mountains 01.png` | WAve **[F2E]** | 256×160 | `tundra-mountains-wave-01.png` |
| Aurora / night sky | `Night BGs {Fenreir}/Night clouds.png` | Fenreir | 240×160 | `aurora-fenreir-clouds.png` |
| Frozen lake / sea at night (Maer Dualdon) | `Night BGs {Fenreir}/Night sea.png` | Fenreir | 240×160 | `frozenlake-fenreir-nightsea.png` |
| Mountain pass (night) | `FE7 BG's/Mountain Night.png` | FE7 rip | 256×160 | `tundra-fe7-mountain-night.png` |
| Frozen port / harbor (Easthaven) | `FE7 BG's/Port.png` | FE7 rip | 256×160 | `frozenport-fe7.png` |

**Licensing:** only WAve's pack is explicitly tagged `[F2E]`. Fenrier / Fenreir / Zeldacrafter follow
the repo's default F2E-with-credit convention but carry no per-file note; the Zeldacrafter (Tales of
Berseria) and FE7 entries are game rips — treat those as **recolor/reference bases**, not clean-credit
originals.
