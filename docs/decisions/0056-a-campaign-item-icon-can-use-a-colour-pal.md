---
id: 56
title: "A campaign item icon can use a colour pal 0 lacks, via an additive third item palette."
date: "2026-06-20"
section: "Combat System"
issues: []
---

# A campaign item icon can use a colour pal 0 lacks, via an additive third item palette.

FE8 item icons share a 16-colour pal 0, which has no pink and no globally-free colour index. The pink
Tourmaline (`ITEM_REDGEM` reskin, Nicolas) therefore cannot recolour pal 0. The earlier assumption that
the second source icon palette could be repainted was wrong: `LoadIconPalettes` places it in BG bank 5,
which regular map/UI text can also use. Repainting it made that text pink.

The corrected mechanism keeps both vanilla source banks byte-for-byte intact: (a) `inject_item_icons`
still swaps the Red Gem tiles; (b) `inject_item_icon_pal2` **appends** a third 16-colour source bank at
bytes 64–95 of `item_icon_palette.agbpal` and emits `gMSPal2IconIds[]`; (c) the generic
`_patch_draw_icon_pal2` hook leaves FE8's normal `ApplyPalettes(..., Dest, 2)` load alone. When an
opted-in icon is drawn with normal item-UI base bank 4, it copies source bank 2 into reserved BG bank 15
at draw time and replaces that icon's palette nibble with bank 15. The draw-time copy matters: earlier UI
initialisation can overwrite a loader-time copy. Other icon callers retain their vanilla base.

The palette-bank assertion in `run.sh ch03tourmaline` proves bank 5 remains vanilla (`0x7FDE` at index 1)
while bank 15 carries the custom palette (`0x7FFF`), and audits the active BG tilemaps so bank 15 is used
only by Tourmaline's four icon tiles. The accompanying screenshot proves the floor and text retain their
normal colours while Tourmaline is pink. More custom colours can share `item_icon_pal2`. The GBA has only
16 BG palette banks (0–15), so a further distinct palette is not an append-only live-memory change: it
requires a new BG-bank reservation and runtime collision audit in every relevant UI context. The cast
palette is an OBJ palette (bank 11), not a BG palette, so an item icon cannot point to it directly.
_Revised: 2026-07-14 (Nicolas — observed pink text; Codex — additive source bank, draw-time BG bank-15
route, and active-tilemap regression check; supersedes the 2026-07-11 pal-1 assumption)._

**Two healers, differentiated by donor (same move as the shamans).** The army's two staff users get
*distinct* vanilla donor lines to avoid stat-twins: **Sclorbo → Moulder** (the durable "war-priest":
HP70/Def25, balanced, accurate) and **Basil → Natasha** (the frail "mage-healer": HP50/Def15 but
Pow60/Res55/Lck60 — a glass, dodgy, magically-potent nuke-healer). The frail line sits
on Basil deliberately: **Sclorbo is a lord candidate** (#42) and the per-lord floor would have to work
harder on a frailer lord (he's already the weakest, staff-only lord pick), whereas **Basil is not a lord**
(joins Ch5, after the Ch1 lord-select), so frailty there carries no survivability-floor cost — and "fragile
but potent natural magic" suits an awakened shrub. Sclorbo is a **Priest → Bishop/Sage**; Basil is a
**Cleric → Bishop/Valkyrie** (see the next entry), so since 2026-08-08 the two differ by class as well
as by donor — but the donor is still what separates the stat lines, and it is the part that would matter
even if they shared a class.
_Decided: 2026-06-20 (Nicolas); Basil's class revised 2026-08-08._

**Basil is a Cleric, because Priest promotes into the wrong weapon type.** Basil was a Priest from
2026-06-20 until 2026-08-08, on the reasonable-looking grounds that she is the same class as Sclorbo
and differs only by donor. That was the wrong class, and the decomp says why: `ClassData.promotion`
for `CLASS_PRIEST` is **`CLASS_SAGE`** — an *anima* mage — while `CLASS_CLERIC`'s is **`CLASS_BISHOP_F`**,
which is *light*. Basil's own `battle_anim.spell_palette_tint` has always declared `[staff, light]`, so
Priest pointed her at the one promoted class whose weapon type contradicts her shipped art. Cleric's
branch (`gPromoJidLut`: Bishop_F / Valkyrie) is the one her kit already assumed.
Three things made this cheap enough to be worth doing, all verified rather than assumed:
**(1) the art does not move** — bust, map sprite and battle anim are all keyed to the *character* slot
(`GetUnitSMSId` override, a private `gUnitSpecificBanimConfigs` AnimConf), never to the class, and the
`clone_from: bishop` donor supplies the STAFF+LIGHT pair Bishop_F needs anyway;
**(2) the locked dialogue does not move** — not one locked Basil line in any chapter genders her, so the
whole ch05 corpus ported unchanged;
**(3) the slot does not move** — `gender:` in the unit YAML rewrites `.attributes` (`_set_gender`) on
whatever character slot the unit wears, so a female Cleric rides the male Artur slot fine, and promotion
is keyed by CLASS in `gPromoJidLut`, never by character.
Two bonuses that were not the reason but are real: Cleric's bases (HP16/Def0/Res6/**Con4** vs Priest's
18/1/5/**5**) lean the same way the Natasha donor does, and `CanUnitRescue` is `GetUnitAid(actor) >=
UNIT_CON(target)` (`bmunit.c:905`) — so Con 4 widens the set of party members who can ferry the ch05
escort, which is the chapter's whole set-piece. Growths are byte-identical between the two classes,
so nothing about her level-up curve changed. `gender: female` is mechanically inert on a foot unit:
both `CA_FEMALE` readers in the decomp (`GetUnitAid`, `koido.c`'s rescued-unit sprite) gate on
`CA_MOUNTEDAID` first. Basil is an awakened *plant*, which RotFM gives no gender, so nothing in canon
was overridden. Guarded by `test_basil_is_a_cleric_because_priest_promotes_into_the_wrong_weapon_type`
and `test_basil_bases_are_vanilla_cleric_class_data_verbatim`, both pinned against the decomp.
_Decided: 2026-08-08 (Nicolas, after an adversarial review that reversed CLAUDE's initial "not worth it")._
