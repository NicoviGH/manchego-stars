---
id: 294
title: "An inherited scene runs only if something still POINTS at it, and five of them no longer do"
date: "2026-09-18"
section: "Operational Gotchas (durable)"
issues: [398, 337]
---

# An inherited scene runs only if something still POINTS at it, and five of them no longer do

*"A scene LOADs the PLAYER CHARACTERS it stages"* (0292) landed a guard on the scenes this
build **writes**. It cannot see the ones it **inherits**, and those are not hypothetical: our
injectors edit a host slot's event-script *file* without rewriting every scene in it, so
untouched vanilla scenes sit in the files we write — and `git diff` reports that the **file**
changed, never that a given scene did.

Five of them stage a character that is one of ours:

| file | command | vanilla character | ours |
|---|---|---|---|
| `ch2-eventscript.h` | `CUMO_CHAR(CHARACTER_EIRIKA)` | Eirika | **braulo** |
| `ch3-eventscript.h` | `CUMO_CHAR` + `MOVE`, `CHARACTER_NEIMI` | Neimi | **pinky** |
| `ch4-eventscript.h` | `MOVE` + `CUMO_CHAR`, `CHARACTER_ARTUR`; `CUMO_CHAR(CHARACTER_EIRIKA)` | Artur, Eirika | **basil**, **braulo** |
| `ch6-eventscript.h` | `CUMO_CHAR(CHARACTER_EIRIKA)` | Eirika | **braulo** |
| `ch7-eventscript.h` | `CUMO_CHAR(CHARACTER_EIRIKA)` | Eirika | **braulo** |

Vanilla can stage Eirika without loading her because Eirika is always there. We have no such
character — the player picks their own lord and any PC can be dead or simply not deployed — so
if one of these still ran it would be the exact hang 0292 exists to prevent, in code nobody
here wrote.

## They do not run, and "does it run" is a question about POINTERS

A scene executes only if its chapter's `ChapterEventGroup` still reaches it. That is decidable
rather than arguable, so the audit is a graph walk from the twenty fields, and the answer for
all five is **unreachable**:

| site | reached in VANILLA from | in OUR build |
|---|---|---|
| `EventScr_089F16EC` (ch02) | `EventScr_Ch3_BeginningScene` | **no referrer anywhere** |
| `EventScr_089F1CC4` (ch03) | `EventScr_Ch4_BeginningScene` | **no referrer anywhere** |
| `EventScr_089F2AE4` (ch05) | `EventScr_Ch6_BeginningScene` | **no referrer anywhere** |
| `EventScr_089F2EBC` (ch06) | `EventScr_Ch7_BeginningScene` | **no referrer anywhere** |
| `EventScr_Ch2Tutorial22` (ch01) | the tutorial **list**, and `EventScr_Ch2Tutorial10` | referrer survives; **the list is `{ NULL }`** |

Four of the five share one cause, and it is worth naming because nobody designed it: each was
reached only through a `SVAL(EVT_SLOT_2, …)` in its host slot's **beginning scene**, and every
injector rewrites that scene whole. Deleting the pointer was a side effect of writing our own
opening — not a decision anyone made about these scenes.

The fifth is different and weaker. `EventScr_Ch2Tutorial22` still has a live referrer
(`EventScr_Ch2Tutorial10`), and both are dead only because the injector writes
`EventListScr_Ch2_Tutorial` to `{ NULL }`. Tutorial dispatch is entirely list-driven —
`EnqueueTutEvent` scans `tutorialEvents` for a matching pointer and leaves `tutorial_counter`
at 0 when it finds none, and `RunTutorialEvent` is a no-op while that counter is 0
(`eventinfo.c:1271-1305`) — so an empty list means no tutorial can fire at all. That is a
**data** fact, not a structural one.

## So the finding is not the five scenes; it is what was holding them dead

Nothing was. Every one of these is unreachable as a **by-product** of an unrelated edit, and
the next chapter to squat a slot gets no such accident — it inherits a fresh set of vanilla
scenes and a fresh set of pointers, and whether it happens to overwrite the right one is luck.
"Dead today" is exactly the kind of fact that becomes a live soft-lock later, quietly.

> **The rule does not change; the POPULATION does. A scene LOADs the PCs it stages, whether we
> authored it or adopted it — so the test runs over everything a chapter can REACH, not just
> over what we wrote.**

`build_campaign.assert_reachable_scenes_load_their_actors` runs in the build beside the
ChapterEventGroup census (0288/#313), and for the same reason: the census rules on the twenty
fields, this rules on everything those fields lead to. 149 reachable scripts across the seven
hosted chapters today, none of them staging an unloaded PC.

Two things it refuses to do:

- **It will not answer from a walk it could not complete.** A script whose body is unreadable
  ends its branch silently, and every scene behind it then reads "unreachable" for the one
  reason that proves nothing. Unresolved symbols fail the build instead. This is not
  theoretical — the first cut indexed only `src/events` and truncated at six shared helpers in
  `src/` (`EventScr_LoadReinforce` and friends), reporting a clean result it had not earned.
- **It is scoped to the PCs**, for the reason measured on #337: the same rule applied to every
  staged character flags 73 sites in untouched vanilla, which plainly works.

And it carries its own positive control. `script_bodies_from` parses a file's *vanilla* text
the same way it parses the injected one, so a test re-runs the whole walk over the donor and
asserts all five sites are flagged there. A gate whose clean run has never been shown capable
of a dirty one is not evidence (0272, *"A check that could not RUN is not a check that
passed"*) — and on vanilla this one reports ten sites, five of them these.

## The trap this generalises

Adopting a vanilla slot means adopting its scripts, and the census answers that for the twenty
fields the struct names. It cannot answer it for the arbitrary graph hanging off them, where
a leftover scene is invisible to `git diff`, invisible to the census, and invisible to the
per-write guard — visible only to the question *what still points at this?*
