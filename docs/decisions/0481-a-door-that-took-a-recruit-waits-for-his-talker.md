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

- `Timeline.releases` keeps the tile each recruit an act brought arrived on (`gone[charId] =
  { x, y }`, the latest attempt's, as the front is), not only that he left.
- `Bot` `releasesOf`: for each such recruit still owed here (`stake.gone`), his talkers
  (recruitsOf's `recruitTalkers`, on the field or the arrival memory names). Each talker's gap
  is `strikeGap` with a Talk's reach (1) to his arrival tile, on the map the door's change leaves.
  `talkReady` means every recruit has a talker at gap 0 or less (or none can Talk him).
  `full = ready >= need and talkReady`.
- The measure is his arrival tile, not the front. A talker who reaches the Fighters is still a
  turn behind him. The first build used the front, read `talkReady` true on the door's turn, and
  replayed R5 move for move (`t766a14`, 16/21/18 turns, Rennac lost each time).
- `sendStagers` works per recruit. For each recruit with no ready talker and none already
  sent, it sends his nearest talker that is free, or whose first job is his own Talk
  (`talk>` + his id), to the door, met beside it. That Talk's goal is past the door, so the door
  is its way there. It never takes a unit another job holds, nor a ready talker of another
  recruit.
- **A talker counts as on its way only while it is short of the door** (its march to the door
  is more than a step). A talker that stands beside the door and still cannot reach him has come
  as far as staging brings it. Waiting on it would hold the door for good.
- **No lord and no barred unit is sent** (the strikers' bars). With no talker sent, the door is
  not held for him: it is opened with what the army has, as ADR 0478 opens a door the army
  cannot fully strike.
- Strikers' and talkers' gaps are read in one `sight.changed` pass per door. The recruit scan
  that finds the stake also names each recruit's ids and talkers.
- No door, chapter or unit is named. The rule reads memory of an act that released a recruit
  who then left.

## Proof

- **Unit tests** (`test_bot.lua`, the release case): a talker 9 from the door and one that
  reaches the front but not the recruit both read not ready. In both cases the door waits and the
  talker is sent. A talker one move away reads ready, and the door opens. With two recruits, the
  unready one's talker is sent and the other's ready talker is not taken. A talker at the door
  that cannot reach a far recruit stages the release. A lord talker is not sent, and the door
  opens. The 5 talker checks
  fail on main, and the front-versus-arrival case fails under the front measure.
- **Replay `t766b14`** (Ch14 s4002, which had no clean try in R5's three):
  - Attempt 1 has no memory: Rennac lost, as before.
  - Attempt 2: the door waited while `talkReady` was false. He was talked over, then he and
    L'Arachel were lost over the cap.
  - Attempt 3: **won clean, 21 turns, 0 deaths.**
