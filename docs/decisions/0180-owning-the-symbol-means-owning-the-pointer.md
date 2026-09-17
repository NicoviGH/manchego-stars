---
id: 180
title: "Owning the symbol means owning the POINTER"
date: "2026-08-07"
section: "Operational Gotchas (durable)"
issues: [25]
---

# Owning the symbol means owning the POINTER

**Declaring a roster table does not wire it — the engine reads the roster through the
`ChapterEventGroup`.** `point_event_group_at` repoints `playerUnitsInNormal`/`InHard`, and
`assert_event_group_roster` fails the build if it was not done.

This shipped broken for one build and **had no symptom**: ch05 declared `MS_Ch05DeployCap`, nothing
pointed at it, so slot 6 kept deploying `UnitDef_Event_Ch6Ally` — vanilla Ch6's start tiles, on a map
whose geometry is vanilla Ch5's. The party appeared, PREP ran, the map drew, the load-test PASSed,
and four units stood **inside walls**. It is the ally-table twin of the host-slot/event-group
mis-target in `docs/adding-a-chapter.md` step 4, and it is invisible to every other gate.

ch03/ch04 could not hit it, because overwriting the table the group already points at cannot break
the link. Adopting campaign-owned symbols is what created the hazard, so it ships with its guard.

**Corollary — placement is verified from unit POSITIONS, never from a frame** (`INSPECT.units`, added
for this). A map sprite is drawn taller than its tile and offset upward, so a unit reads a row high,
and the camera row has to be recovered before any pixel can be assigned a coordinate at all. Nicolas
caught this one off a screenshot; confirming it took a memory dump.
