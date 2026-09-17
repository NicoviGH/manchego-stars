---
id: 73
title: "Recording a cutscene as a review GIF (the standard way to show Nicolas motion)."
date: "2026-06-17"
section: "Combat System"
issues: [21, 219, 220]
---

# Recording a cutscene as a review GIF (the standard way to show Nicolas motion).

The harness fast-forwards non-recorded lead-up, so an assert scenario's screenshots can land
on fades — to SEE a scene play, use a `record*` scenario: it drives the game to the
scene, then captures PNG motion frames `NN-<tag>.png` into `/tmp/playtest-<scenario>/`.
Existing: `recordending` (ch01 outro, tag `end`), `recordch01trail` (`trail`),
`recordlord` (`lord`), `recordch01`/`record`/`scenes` (`op`/`bt`). To record a NEW scene,
add `scenarios.record<name>` that drives to it then captures; for an OUTRO, reuse the win
drive (cf. `recordending`'s copy of `ch01win`) and swap the fast win-wait for
`pokeNormalConfig()` (restores readable typewriter speed after the battle's
`pokeFastConfig`) + `recordCutscene`. Its old numeric `pressEvery` option is now only a
compatibility switch: positive enables A **only while the controller observes FE8's dialogue-input
wait**, and zero disables it; there is no timing cadence or fallback input. A recorder with an
unfilmed `pre` step must return `false, reason` on failure and put configuration restoration in
`afterPre`, whose setup/cleanup lifecycle is guaranteed and plain-Lua tested. Then assemble + show:
`tools/playtest/make_gif.py <scenario> <tag> --name <basename> --open` (PIL; `--fps`
controls read pace — **~6 fps for text-heavy scenes Nicolas needs to read**, 12 for quick
motion; `--scale` nearest-upscales the 240×160 frame; the default output is `docs/demo/` on the
feature branch for GitHub review, and must be pruned before merge unless a live document retains it
as evidence — [[feedback_sharing_visual_drafts]]).
_Decided: 2026-06-17 (#21 ending review); updated 2026-08-03 for the #220 controller contract and #219 recorder cleanup._
