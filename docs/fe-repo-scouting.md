# FE-Repo asset scouting (enemy reskin art track)

A **research log**, not a source of truth. Authoritative reskin choices live where the build reads
them: per-unit `skin:` fields in the chapter YAMLs, and `enemy_class_reskins` in `campaign.yaml`
(wired by `inject_enemy_class_reskins` + `inject_enemy_class_battle_anims`). This file exists so the
FE-Repo doesn't get re-scanned from scratch every time a chapter needs an undead/beast skin.

Rationale for the whole approach — **"divorce skin from class"**: `docs/decisions.md` → the 2026-07-23
skin-divorce refinement (put our skins on the vanilla FE8 twin's classes → parity by construction;
the ch01 goblin-skinned Soldiers/Fighters are the precedent).

⚠️ **HOW to search this repo is a decided thing:** `docs/decisions.md` -> *"The FE-Repo is READ,
not grepped"*. Pull the git trees per top-level directory (the root recursive call truncates and
silently drops categories) and READ the category listings -- the assets that matter are named
`Squidsmith`, `IronShell-Tiny General` and `[Spider-Variant] Cavalier Rider`, and no keyword
sweep will ever find them.

**Taking an asset is one command** once it is chosen: `tools/fe_repo_vendor.py anim|sms`, which
records its source in the `fe-repo.yaml` beside it; `fe_repo_vendor.py verify` re-proves every
vendored asset against the FE-Repo. Its docstring says what a vendored anim and sheet ARE.

Source: **[Klokinator/FE-Repo](https://github.com/Klokinator/FE-Repo)** (the public GBAFE graphics
repo; FEUniverse mirror). Scanned 2026-07-23.

## How the repo is organized (the useful part)

- **`Battle Animations/`** and **`Map Sprites/`** use the **same folder structure**, organized **by class
  frame** — so a reskin's two halves (anim + SMS) sit in parallel folders, and undead skins live under
  the *weapon mode* they animate on, not under an "undead" category:
  - `Infantry - (Lnc) Soldiers, Halberdiers` · `Infantry - (Axe) Fighters and Warriors` ·
    `Infantry - (Axe) Brigs, Pirates, Zerkers` · `Infantry - (Bow) Archers and Hunters` ·
    `Infantry - (Swd) Mercenaries and Heroes` · `Infantry - (Swd) Myrms and Swordmasters` ·
    `Infantry - Knights, Generals, Armors`
  - `Magi - Dark-Type / Holy-Type / Nature-Type / Special`
  - `Monsters - Basic Types` · `Monsters - Dragons and Special`
  - `Mounted - Cavs, Paladins, Rangers` · `Mounted - Dismounted, Monsters, Misc` · `Mounted - Pegs,
    Wyverns, Griffons` · `Mounted - Valks, MKs, Magi`
- **`Portrait Repository/`** is organized **by game** (FE01–FE18 Mugs) + `Generic Characters` +
  `Spriting Community OCs`. No undead category — for a named undead boss, mine `FE08 Mugs` (the vanilla
  monster bosses) or `Generic Characters`.
- Licensing tags: `[U]` = free-to-use, `[F]` = free-to-edit; the repo states battle anims are generally
  free-to-edit. Fine for private distribution; keep the per-asset author credit line (our ADR convention).

## Availability by weapon mode (the load-bearing finding)

Undead **humanoid** anims cluster on **monster / sword / bow / magic** frames. **Armored** undead
are a real gap → use a **frost/pale palette-swap** of the vanilla frame (an ice-locked sentinel
reads better than a bone-knight anyway).

**Lance and axe are NOT a gap, and reading them as one cost ch05 its axe block for a month.** The
`Skeleberdier` covers *both* — it ships Lance, Axe (Stab), Axe (Swing) and Handaxe in one download
(the axe modes by tatata) — so a single vendored anim can dress a lance class and an axe class at
once. **Search a candidate's own mode folders before believing this table**: an anim filed under
one weapon category routinely carries several, and the category is where it *lives*, not what it
*does*. Skeleberdier is filed under Soldiers/Halberdiers; Wight Sniper, filed under skeletons,
ships a Lance beside its Bow.

| need | borrowable? | asset(s) |
|---|---|---|
| sword skeleton | ✅ | `Monsters - Basic Types/[Skeleton-Base] Bonewalker`, `[Skeleton-Custom] Specter`, `Stalfos`, `Skull King` |
| bow skeleton | ✅ | `Monsters - Basic Types/[Skeleton-Reskin] Wight Sniper` |
| lance skeleton | ✅ | `Infantry - (Lnc) …/[Custom Halb] Skeleberdier`; also `[Skeleton-Reskin] Wight Sniper`, whose Lance mode sits beside its Bow |
| axe undead | ✅ | `[Custom Halb] Skeleberdier` → `3. Axe (Swing)` / `3. Axe (Stab)` / `4. Handaxe`, all by tatata. **Shipped in ch05** (#25) |
| armored undead | ❌ | palette-swap the vanilla Armor-Knight/General (frost "sentinel") |
| zombie | ✅ | `Monsters - Basic Types/[Zombie-Base] Revenant`, `Entombed +Ranged`, `[Zombie-Custom] Gore` |
| undead caster | ✅ | `Magi - Dark-Type/[T3 Dark Druid-Reskin] Skeleton Druid`, `[T3 Necromancer-*] …`, `[T2 Summoner-Reskin] Plague Doctor / Warlock` |
| beasts — **wolves/hounds only** | ✅✅ | `Monsters - Basic Types/[Wolf-Base] Gwyllgi` (+repals), `Hellhound`, `[Wolf-Reskin] Wolf`, `Winged Cerberus/Vampirehound`, `Wolfskin` |
| **elk / deer / stag / moose** | ❌ | **none — verified 2026-07-31** against the full directory listings of `Battle Animations/Monsters - Basic Types` and `Map Sprites/Monsters - Basic Types` (not the tree API, which truncates). Every quadruped there is a wolf/hound or a centaur (`Tarvos`/`Maelduin`, horse-bodied + humanoid torso). This row previously read "wolves/hounds/**elk**" and listed only wolves — that wording is what produced ch04/ch05's "Gwyllgi repal → elk" plan, i.e. a repainted HOUND for the campaign's title creature. Superseded: the White Moose adopts **Wyrdeer** (see `chapters/ch04-the-white-moose.yaml` → `art:`). |
| mounted undead / death-knight | ❌ | none; nearest = `Mounted - …/[Wolf-Variant] Wolf Knight` (mounted wolf) |
| sea monster / plesiosaur | ❌ | none (`Monsters - Dragons and Special` has only a `Mermaid`) |

## Per-chapter sourcing

### ch05 — The Elven Tomb (risen elven guardians, undead) — SHIPPED (#25)
Wired 2026-08-20 as `enemy_class_reskins` entries in `campaign.yaml`, map sprite **and** battle
anim for all four line classes. That file is the authority now; the `skin:` fields in
`chapters/ch05-the-elven-tomb.yaml` are the older intent notes and are read by no code.
- `risen-spear` (Soldier/lance) → **Skeleberdier** lance · sprite `Bonewalker (U) Lance {Epicer}`
- `tomb-reaver` (Fighter/axe) → **Skeleberdier** axe + handaxe · sprite `Bonewalker (U) Axe {Snerdels}`
  — *not* a palette-swap; this row read "no undead axe anim" until the mode folders were opened
- `crypt-blade` (Mercenary/sword) → **Bonewalker (one arm)** · sprite `Bonewalker (U) One Arm {IS}`,
  the same body as the anim. Deliberately NOT the Specter, which is Sahnar's, so the named recruit
  does not read as one of the line
- `bone-archer` (Archer/bow) → **Wight Sniper** · sprite `Bonewalker (U) Wight Bow {IS}`
- `frost-sentinel` (Armor-Knight) → frost palette-swap ("ice-locked elven sentinel") — the Def-anchor
- `sahnar` (Myrmidon) → **Specter** (already planned, #25 thread)
- `white-moose` (Gwyllgi) → **SUPERSEDED 2026-07-31.** Was "Gwyllgi repal"; the FE-Repo has no elk
  art (see the availability table above), and a repainted hound reads wrong beside ch04's actual
  wolf pack. Now **Wyrdeer**-sourced: map sprite + portrait from Anarlaurendil's DeviantArt sheet
  (CC BY-SA 3.0, shipped — `chapters/ch04-the-white-moose.yaml` → `art:`); the ch05 BATTLE ANIM is
  still owed and should come from **PMD SpriteCollab `sprite/0899`** (`RearUp`/`Attack`/`Charge`
  give the three `ready`/`windup`/`peak` poses `inject_battle_anims` wants — CC BY-NC 4.0)
- `ravisin` (Druid) → authored frost-druid art (alt if ever wanted: `Skeleton Druid`)
- Map sprites (SMS) for each: the parallel `Map Sprites/Monsters - Basic Types` (skeleton/zombie) or a palette-swap.

### ch04 — The White Moose (beasts) — logged on issue #24
The wolf/beast anims (Gwyllgi repals, Hellhounds, Wolf reskins, mounted Wolf-Knight) for ch04's pack +
Lupin. Cut from ch05; parked on **issue #24** so the `feat/24-ch04-map` branch finds them.

### ch08 — ice trolls (Easthaven ambush) — forward note
`[Berserker-Variant] Yetizerker` (frost berserker) fits the book's ice trolls if we want real frost-brute
art over a palette-swap.

### ch06 — the merfolk (Bremen) — logged on issue #26
Shipped: `[Monster-Custom] [F] Mermaid by Stephano` (its `(Bra)` modes; map sprite `Mermaid (F)
{N426}`), `[General-Variant] IronShell-Tiny General`, `[Monster-Custom] [U] Lamia by L95`, and the
`Shark Rider (M) {N426}` map sprite. Rejected: `[Spider-Variant] [M] Cavalier Rider` (a recolour only
makes an ice SPIDER, and a crab is Braulo's identity) and `Squidsmith` (Nicolas: "meh, kinda weird").
Messie needs no anim: he is a cutscene actor, and his map sprite is painted (#363).

**THE FE-REPO IS NOT THE WHOLE COMMUNITY.** N426's Shark Rider has a full battle anim (Trident, Axe,
Unarmed) that never reached the FE-Repo: it is in his FEUniverse thread
(https://feuniverse.us/t/6943/40, files on the Dropbox linked there), and ch06's cavalry ships it.
Before calling an asset missing, search FEUniverse too: it is Discourse, so
`https://feuniverse.us/search.json?q=<term>` answers in JSON and `/raw/<topic>/<post>` returns a
post's text. An artist's own thread is the place to look once the FE-Repo has their map sprite.

**Water-themed sweep, 2026-10-05** (every name in Battle Animations / Map Sprites / Portraits): anims
`Squidsmith` (axe, handaxe), `Snail Knight` (Cavalier: lance, magic), `Warrior Naga` (sword, magic;
reads as an armoured human), `Naga` (monster), `Tortoise` (unarmed), the Lamias; map sprites
`Kraken (U) Sea Monster {Xenith}`, `Fish (U)`, `Shark (U) {N426}`, `Shark Rider (F) {N426}`,
`Tortoise (U)`. **PMD SpriteCollab** has complete sets for ~40 water/ice Pokémon (Tentacruel, Gyarados,
Octillery, Cloyster, Golisopod...); ch06's Bael becomes Tentacruel from there.
