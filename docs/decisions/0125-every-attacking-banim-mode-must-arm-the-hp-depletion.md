---
id: 125
title: "Every ATTACKING banim mode must ARM the HP depletion — the unit it starves is the OPPONENT (#24)"
date: "2026-07-31"
section: "Art & Audio"
issues: [24]
---

# Every ATTACKING banim mode must ARM the HP depletion — the unit it starves is the OPPONENT (#24)

C01 `banim_code_wait_hp_deplete` (`0x85000001`) "freezes if no HP depletion is occurring/has occurred" —
the decomp states the hazard on the macro itself (`include/banim_code.inc`). The non-obvious half is **who
hangs**: every vanilla dodge/stand mode waits *bare* on C01 and relies on the **attacker's** script having
armed a depletion, with `prepare_hp_deplete` (C04, melee) or `call_spell_anim` (C05, projectile/spell).
So an attacking mode must arm one **even when nothing connects, and even when it never waits itself** —
a miss is exactly the case an author skips. Every vanilla donor we clone obeys this: `banim_pirm_ax1` and
`banim_armm_sp1` keep C04 in `attack_miss` and drop only `hit_normal`; `banim_arcm_ar1` / `banim_sham_mg1`
make `attack_miss` their *attack* body, arrow and all.

Four of our generated/imported paths broke it, and all four soft-lock — the whole proc tree wedges with
`GAMECTRL` at `lock=1`, `ekrBattleInRoundIdle` spinning on `(gBanimDoneFlag[0] + gBanimDoneFlag[1]) == 2`:
- **Faked MELEE `attack_miss`** emitted the wait with no C04. *This is what froze ch04 turn 4:* Braulo's
  counter missed Lupin, both anims stuck on C01, `gBanimDoneFlag = [0, 0]`.
- **Faked MELEE `attack_range`/`_critical`** ran the DEFENDER "stand" body (waits, arms nothing) on the
  assumption "a melee unit can't strike at range". False for us — `CLASS_PIRATE` ships a **Hand Axe** and
  `CLASS_ARMOR_KNIGHT`/`PEGASUS` a **Javelin**. Now the vanilla Armor Knight's thrown shape (C05).
- **Faked RANGED/MAGIC `attack_miss`** held a still frame and armed nothing; now the attack body, per the
  archer/shaman donors.
- **IMPORTED `Pinky.txt` mode 12** — the *community source* omitted C04. Her miss ended early while the
  Mauthe Doog's dodge blocked forever: `gBanimDoneFlag = [0, 1]`, the asymmetric signature of "the
  attacker finished, the defender is still waiting for a depletion nobody armed".

Guarded, not just fixed: `feditor_to_banim.validate_hp_deplete_arming` runs at `emit_motion_s` (the one
choke point every import crosses) and **fails the build** on any mode that opens with C03 and arms nothing,
so a community script's hole can never again surface as one unlucky combat mid-playtest. Auditing all 11
vendored/imported scripts found Pinky's the only offender. `TestHpDepleteArming` pins both halves of the
contract on both generators (attackers arm; dodge/stand deliberately do NOT).

**Method note (this is how a banim freeze gets diagnosed).** Read it as DATA, never pixels
([[feedback_verify_via_data_not_pixels]]): the proc pool carries its own diagnosis — `proc_lockCnt`
(the wait semaphore), `proc_scrCur` (which PROC_* command it sits on) and `proc_name` — and
`gBanimDoneFlag` + `gAnims[n].currentRoundType` name the stuck **side** and **round** outright. The
harness's `freezeReport` (smoke driver, fires on any SOFTLOCK verdict) prints all of it, so one run turns
"the game froze" into "the right side is playing MISS_CLOSE and never signals done". The inherited lead
said "Revenant vs Wolfram / check `battleTileSet 0x15`"; the actual pair was Lupin vs Braulo and the
tileset was irrelevant — [[feedback_inherited_leads_are_hypotheses]] again.
_Decided: 2026-07-31 (ch04 turn-4 soft-lock, #24)_
