---
id: 292
title: "A scene LOADs the PLAYER CHARACTERS it stages, and only those need it"
date: "2026-09-17"
section: "Operational Gotchas (durable)"
issues: [337]
---

# A scene LOADs the PLAYER CHARACTERS it stages, and only those need it

*"Permadeath is a combat rule, not a narrative one"* puts all eight PCs in every cutscene
whether or not they are alive. That policy rests on one invariant, and nothing enforced it:

> **A cutscene LOADs its actors; it never assumes they are standing on the map.**

`LoadUnit` performs no death check, so loading a dead character is fine. `GetUnitFromCharId`
returns **NULL** for an *absent* one, and `CUMO_CHAR` / `MOVE` / `MOVE_DEFINED` all resolve
through it — so a beat naming a PC the scene never loaded is the same never-returns soft-lock
`assert_scripted_move_reachable` was written for. It fires the first time a player reaches that
beat having lost that character, and never before, which is why no playtest has found one.

## The scope is the PCs, and that was measured, not assumed

The obvious rule — *every* staged character must be LOADed by its scene — is wrong, and the
emitted scripts say so immediately: it flags **73 sites in untouched vanilla**, which plainly
works. Vanilla stages Eirika without loading her because **Eirika is always there**.

We have no such character. The player picks their own lord, and any PC can be dead or simply
not picked at PREP — so the guarantee vanilla leans on is exactly the one that does not
transfer. Everything else a scene stages is guaranteed by construction: ch05's
`CUMO_CHAR(0xb8)` is Ravisin, the boss, on the map from the chapter's own table since turn 1.
Flagging her would have been the gate crying wolf on the first real chapter it read.

A PC rides its `PORTRAIT_MAP` slot, so its on-map pid is `CHARACTER_<slot>` — braulo is
`CHARACTER_EIRIKA`, pinky is `CHARACTER_NEIMI`. That map is the whole scope.

## `MOVE`'s pid is its SECOND argument

`MOVE(speed, pid, x, y)` (`EAstdlib.h:117`). Reading the pid as the first argument is not a
small error: vanilla's speeds are `0x10` and `0x0`, **every one of them parses as a character
id**, and the first cut of this analysis reported 378 staging sites campaign-wide. Correctly
parsed and correctly scoped, the live tree has **none**.

## Where it runs, and why not in the injectors

The check is registered on `_replace_brace_block` — the single writer all 79 block writes go
through — and fires on any marker starting with `EventScr_`. A hook rather than a call per
injector for the reason `apply_chapter_fog` is a total pass: with that many call sites,
"somebody forgets to call the guard on the new scene" is a question of when, not whether.

The validator is registered from `build_campaign` rather than defined in `inject/decomp.py`,
because the check needs `PORTRAIT_MAP` and that layer stays dependency-free — otherwise every
extraction of #389 gets its import cycle back (ADR 0287).

## What it is worth today: nothing, which is the point

No scene currently stages a PC, so the guard finds nothing and the injected decomp is
byte-identical with it active (975 files). It was built **before** ch06's dialogue pass rather
than after, because ch06's Messie scene stages Marty and Braulo unconditionally, neither is
force-deployed, and the first player to arrive there having lost one would have found a
chapter that hangs.

⚠️ **What this does NOT cover, and it is a real question:** vanilla scenes we *inherit* rather
than write. A file our injector edits still contains vanilla scenes we never touched, and some
of them stage `CHARACTER_EIRIKA` — which is now **braulo**. Whether any of those still run in
our chapters is unanswered; the guard only sees what we write. That is **#398**.
