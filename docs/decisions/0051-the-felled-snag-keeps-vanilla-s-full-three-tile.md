---
id: 51
title: "The felled snag keeps vanilla's full three-tile silhouette, winterized in snowy-bern (#24)."
date: "2026-08-10"
section: "Combat System"
issues: [24]
---

# The felled snag keeps vanilla's full three-tile silhouette, winterized in snowy-bern (#24).

The masonry fallback above was mechanically safe and visually wrong: chopping a tree made a
stone bridge appear. Vanilla Ch4's change is a composed `7 / 4 / 11` picture -- wood fragments
on the near bank, the trunk over water, then fragments on the far bank -- so snowy-bern now
paints the same composition into its matching unused `7 / 36 / 11` slots. The grass pixels are
replaced with snowy-bern snow; the wood silhouette is lifted intact and recoloured with the
muted ramp from snowy-bern's upright snag 35. All three cells use Snowy Bern's existing lit
palette bank 4; the shared palette stays byte-for-byte untouched. That matters under fog:
tileset banks 5-9 are derived fog copies of lit banks 0-4, not spare authoring banks. The bank
fragments preserve snow tile 67's pixel pattern and the center keeps the vanilla trunk/water
silhouette, remapped only to colours already native to the snag palette.
`paint-metatile` is the reusable authoring seam: it splits a 16x16 indexed PNG into 8x8 tiles,
reuses byte-identical art, allocates only unreferenced tile ids, can claim an unused palette
bank in the lit 0-4 half, rejects the derived fog half, and preserves terrain unless explicitly
authored. Runtime still resolves each preferred
slot through `_snowy_metatile_for`, so `7 / 36 / 11` is accepted only while it carries
`PLAINS / BRIDGE_SNAG / PLAINS` **and each preferred slot is visibly painted, not merely
terrain-correct**. That preferred-path check has its own regression because bypassing the
ordinary search's blank-art guard can recreate the original solid-block failure. The enlarged
binary round-trip render is
`docs/demo/ch04-snowy-snag-bridge.png`; `ch04snag` remains the mechanism gate and an in-engine
frame remains the art gate.
_Decided: 2026-08-10 (Nicolas + Codex, #24; visual composition supplied by Nicolas)._

**ch04 Stage 2c — the reveal cutscene reuses the turn-2 TurnEvent script (load + stage as one).** Following vanilla Ch4's `EventScr_089F199C` shape, the turn-2 script that already `LOAD1`s the reveal wave *also* stages it in ONE script (`CAMERA2` to the NW fog → `LOAD1`/`ENUN` → `MUSC` → `CUMO_CHAR` Lupin → stub beats → `EVBIT_T`), rather than a separate cutscene script — that's how vanilla does a reinforcement-with-scene. On-map (no `BACG`); the beats are faced map bubbles (`_script_to_message`) on Lupin (Duessel) + Marty (Seth). Two beats plant the parley: Lupin commands the pack (shows intelligence) and Marty flags "talk to it" — the cutscene *is* the parley teaching (no separate tutorial). **Stub lines + `SONG_TENSION` placeholder; Stage 4 finalizes dialogue + music via the dialogue-pass skill.** Dead Ch5 slots `EventScr_089F22A4` (reused) + msgs `0x9BB`/`0x9BC`.
_Decided: 2026-07-21 (Nicolas + CLAUDE, ch04 slice #24, Stage 2c)._

**Parity-engine v1 gaps closed (#176 economy drops, #177 area-triggered reinforcements).** Two channels the
first cut of the extractors punted on, both read from HEAD like the rest: (1) **enemy drops** — a red unit
flagged `.itemDrop` drops its **last** inventory item on death (`US_DROP_ITEM`, the final slot per
`statscreen.c:726`); `vanilla_economy` now values it as a `drops` channel folded into `total_gold` (the Ch4/Ch5
lock twins carry none, so the lock is unchanged, but Ch2's Vulnerary / Ch3's keys / Ch13's crests now count).
(2) **area/zone-triggered reinforcements** — `_vanilla_reinforcement_turns` matched only the `TurnEventPlayer`
macro, so it missed Ch4 "Ancient Horrors"' waves: a turn-2 Bonewalker pack written as a raw
`TURN(…, FACTION_BLUE)` and a Revenant pack behind a temp-flag-gated `TURN` that an `AREA(…)` trigger arms on
zone-entry. It now also reads the raw-`TURN` expansion, treats any **flag-gated** turn event (and any `AREA`/
`AFEV` script that LOADs a force) as a reinforcement, and models zone-entry arrivals as `_ZONE_ENTRY_TURN`
(> 1, so they leave the turn-1 line) — Ch4 reads 16 line + 7 reinforcements, Ch5's 2/6/8 detection unchanged.
_Decided: 2026-07-16 (CLAUDE; TDD). Closes the v1 scope noted on #170/#171._
Worked example — **ch02 (parity FE8 Ch2):** gems + premium consumables only (vanilla Ch2's village
gifts) + a regular armory + one enemy consumable drop; **no boosters, no promos.** The three chwinga
"charms" are those gifts — **Elixir / Pure Water / Hand Axe** (the Hand Axe stands in for vanilla's
**Red Gem**, which is lent forward to ch03's gem mine; see the Ch3-deviations ADR below — net wealth
across ch02+ch03 is unchanged).
_Reconstructed: 2026-06-22 (CLAUDE, decomp event-data + `events_shoplist.c` scan) — upgrades
fe8-pacing §3 from era-buckets to a decomp-pinned curve (correcting the old "promos at Ch9–13": promos
+ boosters actually start Ch5, Master Seal/Secret Shop start ~Ch14a). Companion to the recruit budget._
