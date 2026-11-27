---
id: 481
title: "A door that took a recruit waits for his talker"
date: "2026-11-27"
section: "Combat System"
issues: [766, 764, 768, 510]
---

# A door that took a recruit waits for his talker

**Decided (#764, Nicolas 2026-11-26: "iterate without me in the loop until you solve it").**
This extends ADR 0478's staging from strikers to the recruit's talker.

**Why.** R5 (#768, 2026-11-27) ran with ADR 0478. Vanilla Ch14 still missed Rennac (0x1C) in 14
of 15 tries. On the door's turn the strikers stood ready in every attempt where memory knew the
door. L'Arachel (25), his only talker, was 10-16 tiles from him the turn after it opened, against
7 in the one recruit. He opens the chests at (22,5) and (22,3) and leaves within two turns. The
door released him while his talker was out of reach.

## The rule

- `Timeline.releases` keeps where each recruit an act brought first stood (`gone[charId] =
  { x, y }`, his arrival tile), not only that he left.
- `Bot` `releasesOf`: for each such recruit still owed here (`stake.gone`), his talkers
  (recruitsOf's `recruitTalkers`, on the field or the arrival memory names). Each talker's gap
  is `strikeGap` with a Talk's reach (1) to his arrival tile, on the map the door's change leaves.
  `talkReady` means every recruit has a talker at gap 0 or less (or none can Talk him).
  `full = ready >= need and talkReady`.
- The measure is his arrival tile, not the front. A talker who reaches the Fighters is still a
  turn behind him. The first build used the front, read `talkReady` true on the door's turn, and
  replayed R5 move for move (`t766a14`, 16/21/18 turns, Rennac lost each time).
- `sendStagers`: when no talker is ready, it sends the nearest one that is free or holds a Talk
  goal (kind `recruit`) to the door, met beside it. That Talk's goal tile is past the door, so the
  door is its way there. The bars are the strikers' own: no lord, nothing the stuck record bars.
  A talker on its way keeps the release unstaged, as a striker does.
- No door, chapter or unit is named. The rule reads memory of an act that released a recruit
  who then left.

## Proof

- **Unit tests** (`test_bot.lua`, the release case): a talker 9 from the door and one that
  reaches the front but not the recruit both read not ready. In both cases the door waits and the
  talker is sent. A talker one move away reads ready, and the door opens. The 5 talker checks
  fail on main, and the front-versus-arrival case fails under the front measure.
- **Replay `t766b14`** (Ch14 s4002, which had no clean try in R5's three):
  - Attempt 1 has no memory: Rennac lost, as before.
  - Attempt 2: the door waited while `talkReady` was false. He was talked over, then he and
    L'Arachel were lost over the cap.
  - Attempt 3: **won clean, 21 turns, 0 deaths.**
