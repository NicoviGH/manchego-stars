---
id: 271
title: "AI_B is the APPROACH and AI_A is the ACTION, and the moving half is AI_A"
date: "2026-09-04"
section: "Operational Gotchas (durable)"
issues: [26]
---

# AI_B is the APPROACH and AI_A is the ACTION, and the moving half is AI_A

`ch06clock`'s first headed run found three enemies our tooling labels **never-move** standing around
a boat they had walked to. They are not mislabelled data — they are a label that reports half a
vector.

From `cp_data.c`, a unit's AI is two scripts, not one:

- `gAi2ScriptTable[AI_B_03] = AiScr_AiB_NeverMove` is `AI_NOP_0E`. It is the **approach** script and
  it does nothing: all it suppresses is walking across the map at you.
- `gAi1ScriptTable[AI_A_00] = gAiScript_ActionInRange` is `AI_ACTION(100)`. It is the **action**
  script, and acting includes moving within the unit's own range to reach a target. The statue is
  `AI_A_03 ActionStanding`.

So `{0x00, 0x03}` — vanilla's most common pairing — means *"hold the line, but step out and hit
anything you can reach."* Measured across the campaign: **94 of 99 enemies are `ActionInRange`,
and 48 of the 51 units reported as "threat you walk into" will move.** Four units in the whole
campaign are genuine statues.

**What this does NOT invalidate.** `enemy_ai_bytes` emits all four donor bytes and `ai_bytes`
resolves vanilla's symbolic macros (`GuardTileAI` -> `(0x3, 0x3)`, `DoNothing` -> `(0x6, 0x3)`),
raising rather than defaulting on an unknown token. ch06's boats carry a live non-zero AI_A into the
ROM, which is the proof the pipeline is whole. #335's derivation is sound and nothing needs
re-deriving; *"AI behaviour is MEASURED and REPORTED, not weighted into threat"* still holds, since
copied-wholesale bytes match the twin on both halves.

**What it invalidated** was the read-back, now fixed in the same change. `AI_BEHAVIOUR`,
`ai_family`, `behaviour_split` and `make chapter`'s behaviour column all keyed on `ai[1]` alone, so
the split's premise — *"a unit that never moves contributes nothing until the player enters its
range"* — was false for 48 of 51 units, and #344's kept deliverable was the part that misreported.
Note the shape of it: #344's own corollary was a coverage gap in this same table along the AI_B
axis. Same bug class, one dimension over.

The report now names both halves and derives a THREE-way shape from the pair, because two buckets
could not express the case that actually shipped:

- **pursuer** — the approach walks it across the map at you.
- **striker** — it holds ground, but its ACTION steps out within its own move range. `{engage,
  never-move}` is vanilla's commonest pairing and most of every roster; this is the bucket that did
  not exist.
- **statue** — it holds ground and does not move at all, even to attack. Four units campaign-wide.

`AI_ACTION` is pinned against `gAi1ScriptTable` by a test on the same discipline `AI_BEHAVIOUR`
follows: the twelve entries the decomp gives only an address (0x09–0x14) stay UNNAMED rather than
guessed at. `ai_shape` takes the vector and **raises on a bare int**, because a stale
`ai_shape(ai[1])` would classify a whole roster off half the information and look entirely correct
— which is precisely how this defect survived. `map_placement_preview`'s `is_boss` special case is
deleted: it was standing in for the AI_A half it could not see, and it was wrong in both directions.

**Why it surfaced on ch06 and not earlier.** It needs a killable unit parked inside a static's
reach. Vanilla Ch6's entire red force is `ActionInRange x26 / ActionStanding x1` — **no
`AI_A_08 ActionInRange_ExceptCivilian` anywhere** — so vanilla protects its villagers by PLACEMENT
alone, which is what *"Vanilla Ch6's urgency is TRAVEL TIME"* measured independently. Our pockets
moved a 19 HP hull into range of four statics. The bytes are faithful; the map is what changed.

The ch06 response is not settled here — it is on #26.
