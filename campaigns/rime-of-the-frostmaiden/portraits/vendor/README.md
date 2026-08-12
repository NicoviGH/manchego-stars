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
| `Aversa {Garytop} [F2E].png` | Ravisin (ch05 boss) — silver→auburn hair and warm→frost-pale skin palette edit; original brown markings retained | Garytop | F2E (free to edit) |
| `Skeleton (Armour, version 1) {Generic Pretsel} [F2E].png` | Ch05 Arena Master — used as-is; dresses the collision-free Glen face slot only when Ch05 opens the Arena | Generic Pretsel | F2E (free to edit) |
| `Hipster Wolf Head With Glasses {TotalityDesigns}.png` | Lupin (ch04 recruit) — bust ref. NOT FE-Repo: Redbubble listing supplied by Nicolas (2026-07-03); `../lupin.png` regenerates via `ref_to_bust.py` + `../lupin_darken.py` (render block in `npcs/lupin.yaml`) | TotalityDesigns | found image — private non-commercial use; recheck before distribution |

`../guest_vendor_busts.py` (ch00/ch01 guests), `../vellynne.py`, and `../ravisin.py` regenerate the
shipped busts from these sheets (96×80 crop, palette fixes, index-0 transparent).
Credit lines mirrored in the root `CREDITS.md`.

The Arena Master source is pinned to FE-Repo commit
[`3abc62d4f0a12d300911b51788719f950c5f45b9`](https://github.com/Klokinator/FE-Repo/blob/3abc62d4f0a12d300911b51788719f950c5f45b9/Portrait%20Repository/Generic%20Characters%20%28Villagers%2C%20Goons%2C%20and%20Loons%29/Skeleton%20%28Armour%2C%20version%201%29%20%7BGeneric%20Pretsel%7D%20%5BF2E%5D.png)
(`sha256 b5a1bbfb2e2c20fc6c77c689936784166277c1652faf37c7f6c91935cea6583f`).
