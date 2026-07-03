# Vendored community portraits

Original FE-Repo mug sheets used as guest-portrait bases, vendored per the
project's asset pattern (pull the single file, never submodule the repo).
Source: [Klokinator/FE-Repo](https://github.com/Klokinator/FE-Repo) — pulled from
`Portrait Repository/` (the Generic, per-game, and OC subfolders).

| File | Used for | Author(s) | License tag |
|---|---|---|---|
| `Pirate Lady (Version 3) {Cygnus} [F2E].png` | Hlin Trollbane (ch00 guest) — silver-haired age recolor | Cygnus | F2E (free to edit) |
| `Hero {LaurentLacroix, UltraFenix, monk-han}.png` | Scramsax (ch00 guest) — used as-is | LaurentLacroix, UltraFenix, monk-han | none in filename — recheck before distribution |
| `Generic Villager {Cynon} [F2E].png` | Hruna (ch01 guest) — periwinkle→olive-wool coat recolor | Cynon | F2E (free to edit) |
| `Sonya (Witch, FE8 colours) {JeyTheCount} [F2E].png` | Vellynne Harpell (ch02 quest-giver) — magenta→snow-white hair recolor | JeyTheCount | F2E (free to edit) |
| `Hipster Wolf Head With Glasses {TotalityDesigns}.png` | Lupin (ch04 recruit) — bust ref. NOT FE-Repo: Redbubble listing supplied by Nicolas (2026-07-03); `../lupin.png` regenerates via `ref_to_bust.py` + `../lupin_darken.py` (render block in `npcs/lupin.yaml`) | TotalityDesigns | found image — private non-commercial use; recheck before distribution |

`../guest_vendor_busts.py` (ch00/ch01 guests) and `../vellynne.py` regenerate the
shipped busts from these sheets (96×80 crop, palette fixes, index-0 transparent).
Credit lines mirrored in the root `CREDITS.md`.
