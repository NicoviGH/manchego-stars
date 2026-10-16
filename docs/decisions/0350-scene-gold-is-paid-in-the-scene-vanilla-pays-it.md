---
id: 350
title: "Scene gold is paid in a scene, with vanilla's own lines"
date: "2026-10-16"
section: "Economy"
issues: [495]
---

# Scene gold is paid in a scene, with vanilla's own lines

Vanilla FE8 has no clear bonus, but it does pay gold in scenes. Right after Ch1, Castle Frelia's
scene (chapter 0x38, the decomp's `lordsplit`) pays the leader 5,000, so Ch2 opens at 5,000
(measured on retail by `vanillagold`, 2026-10-15). Ch8's ending pays 10,000 the same way. Ours
paid neither, and ch02's Armory opened on an empty purse. The 2026-06-17 "net wash" call (the
job's 200 gold spent on Baxby) had read vanilla as paying nothing.

**The vehicle.** A chapter declares `economy.scene_gold: [{amount, scene, after_beat}]`.
`scene` is one of its cutscene triggers, and naming any other scene fails the build.
`after_beat` (1-based) pays once that beat's text closes. Without it, the scene's injector pays
where the scene ends. `inject.scenes.scene_gold_script` emits lordsplit's own sequence:
`CALL(EventScr_RemoveBGIfNeeded)` so the popup shows over the map, then
`SVAL(EVT_SLOT_3, n)` and `GIVEITEMTOMAIN(CHAR_EVT_PLAYER_LEADER)`. Mid-scene, it fades back up
onto the scene's backdrop. `difficulty.chapter_economy` and the wiki count it. A twin's gold
that we moved on purpose is recorded as `payload_deviations: - item: 10000 gold`.

**ch01** pays the 5,000 after Duvessa's beat, once she has handed over the Council's standing
commission. That is the town's purse, as Hayden's was the crown's, and it needs no new line. The
job's two hundred still goes on Baxby, as the scene says. `ch01gold` plays the real chain and
reads 5,000 on ch02's map. **ch07** pays vanilla Ch8's 10,000 (ADR 0339) before its placeholder
ending fades. Who hands it over is the dialogue pass's call. `post_chapter.net_gold` is retired.
