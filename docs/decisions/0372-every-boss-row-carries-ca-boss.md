---
id: 372
title: "Every chapter boss's row carries CA_BOSS, and its personal line is its whole line"
date: "2026-10-28"
section: "Combat System"
issues: [545]
---

# Every chapter boss's row carries CA_BOSS, and its personal line is its whole line

A boss on a raw character pid (ch03's grell on 0xBF, ch05's Ravisin on 0xB8) used to ride a row
with no `CA_BOSS`, because neither a cloned generic row nor an unused gap carries it. The chapter
still ended on the boss's death (its flagged death quote raises `EVFLAG_DEFEAT_BOSS`), but the
engine withheld everything it hangs on the bit: the +40 kill exp (`bmbattle.c`), the map's boss
marker (`bmudisp.c`), the chapter status screen's listing (`uichapterstatus.c`), the Silencer
rate (`bmbattle.c`) and the opening camera's pan (`bmcamadjust.c`).

**The build now stamps `CA_BOSS` onto every chapter boss's row**
(`inject.raw_pids.stamp_boss_attributes`, over `CHAPTER_ENEMY_PIDS`), raw pid or vanilla slot.
That is vanilla's own shape: every FE8 chapter boss is a character with `CA_BOSS`. A test fails
when any `is_boss` unit's row lacks it. The parity model reads the same answer
(`exp_curve.entry_carries_ca_boss`), so it no longer prices a raw-pid boss as a generic.

**What follows from it.** With `CA_BOSS`, `LoadUnit` sends an autolevelled red unit down
`UnitAutolevelRealistic`, which levels it from the row's `baseLevel`. Our bosses' `baseLevel` is
their deploy level (`RAW_PID_LEVEL_SOURCES`), so they grow zero levels, as vanilla's do (Bazba:
`baseLevel` 6, deployed at L6). **A boss's `personal:` line is therefore its WHOLE line at its
level**, never a line that autolevel grows on top of. The grell was the one boss this changed: it
had rolled 7 class-growth autolevels on top of its line. Those levels are folded into its
`personal:` at the model's rounded means (Nicolas chose this over accepting the drop, 2026-10-28),
so its line is unchanged (36 HP / Pow 10 / Def 8 at L8). Only the ±12% autolevel noise is gone.

**What it cost.** ch03 now pays the +40 boss bonus its twin's Bazba pays (pot 382 → 422 against
the twin's 415). No parity verdict changed. ch03's ratios moved by about 1%, from losing the noise.
Ravisin's kill was already at the 100-exp cap, so ch05's pot did not move.

**0xB8 is vanilla's generic Arch Mogall row**, and later vanilla chapters field Arch Mogalls on
it. The build already rewrote that row as Ravisin's name and line. A row the build rewrites is
ours (`assert_rewritten_raw_pids_are_exclusive`), so the bit is one more field of the same row.
