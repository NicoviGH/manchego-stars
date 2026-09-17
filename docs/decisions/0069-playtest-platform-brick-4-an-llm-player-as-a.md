---
id: 69
title: "Playtest platform brick 4 = an LLM-player as a SOAK/BALANCE tool, built policy-and-transport-first (#63)."
date: "2026-06-20"
section: "Combat System"
issues: [63]
---

# Playtest platform brick 4 = an LLM-player as a SOAK/BALANCE tool, built policy-and-transport-first (#63).

The final #49 spine brick swaps the greedy clear-bot's rule-based `pickTarget` for an LLM *policy* over the
same I/O layer. Its job is dynamic balance signal — when a competent player loses units or barely clears a
chapter, that's the same signal `difficulty.py` models statically, now observed live; its credibility bar is
beating vanilla FE8 (so the signal isn't overfit to our maps). Locked architecture (brainstormed w/ Nicolas):
- **Transport = sidecar file-handshake.** mGBA's embedded Lua can't make network calls, so the harness
  serializes the board to a request file and blocks; an external `tools/playtest/llm_player.py` (Anthropic SDK,
  ordinary testable Python) decides and writes the response. Mirrors the platform doctrine — *pure core, driver
  owns I/O* — with the LLM **policy** in the Python sidecar. (Rejected: in-emulator socket = fragile.)
- **Granularity = per-turn commander.** The LLM gets the whole board once per player phase and emits an ordered
  list of unit orders; the harness executes them with existing primitives. ~6–8× fewer calls than per-unit and
  better play (tactics are interdependent: gang-up, bait, stay out of boss range).
- **Model = Sonnet default, `PT_MODEL` knob.** A weak player fires *false* balance alarms, defeating the soak,
  so default to one that plays well; a cheap Haiku soak is one flag away. No tiered/escalation plumbing (YAGNI).
- **Determinism + cost = one artifact, the board-hash-keyed transcript.** Each decision is keyed by
  `hash(serialize_board) + seed + chapter + turn`: replay hit → cached orders (free, deterministic); miss in
  replay → hard fail; miss in local soak → call the LLM, append. This single mechanism satisfies the platform's
  "replays identically on CI `lua` and mGBA" rule **and** makes re-soaks cost nothing.
- **M1 (this commit) = the three PURE cores only, no LLM calls** (TDD, `tools/test_llm_player.py` in `make
  test`, no emulator): `serialize_board` (deterministic compact JSON — units normalized by id so unit-array
  iteration order can't change the bytes/key), `validate_orders` (illegal orders → a `rejected` list with
  reasons so a bad LLM turn is dropped, never soft-locks — the harness runs the survivors), and `Transcript`
  record/replay keyed by `transcript_key`. Swap point stays the pure `clearbot.lua pickTarget`. M2 wires the
  sidecar handshake + `llmDrive` scenario (replay-only on the prologue), M3 the live policy, M4 the soak report
  into the difficulty curve, M5 the vanilla-FE8 validation milestone (needs a save-state checkpoint).
_Decided: 2026-06-20 (CLAUDE; pipeline track. Epic #63; M1 cores TDD'd green, 20 asserts in make test)_
