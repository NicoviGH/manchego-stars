---
id: 70
title: "#63 M2 = the sidecar handshake ships PROVIDER-AGNOSTIC — a free local model is one env var away."
date: "2026-07-02"
section: "Combat System"
issues: [63]
---

# #63 M2 = the sidecar handshake ships PROVIDER-AGNOSTIC — a free local model is one env var away.

Nicolas (2026-07-02) was cost-shy about the LLM-player; the happy medium is supporting free local models
(Llama/Gemma via Ollama or llama.cpp) alongside Anthropic. Settled:
- **Two transports, no SDK dependency.** `llm_player.py` speaks the Anthropic Messages API *or* any
  OpenAI-compatible `/chat/completions` endpoint, both via stdlib `urllib` (~15 lines each; a new dependency
  for two POSTs is the bigger risk, and the sidecar must run anywhere a playtester has python3). Knobs:
  `PT_PROVIDER` (`anthropic` default per the epic's "a weak player fires FALSE balance alarms" — Sonnet;
  `openai` = OpenAI-compatible), `PT_MODEL`, `PT_BASE_URL` (openai default = local Ollama,
  `http://localhost:11434/v1`), `PT_API_KEY`/`ANTHROPIC_API_KEY` (the latter feeds ONLY the anthropic
  transport — resolving it for the openai provider would Bearer-leak the Anthropic secret to whatever host
  `PT_BASE_URL` names). **The free path is plumbing/smoke value; the paid path is balance-signal value** — a
  Gemma-grade commander proves the loop and soaks for crashes, but its losses are weak evidence about chapter
  difficulty. Both record into the same transcript format. Model output passes a non-finite gate (`NaN` /
  `1e999`→inf orders are culled) — a one-off model hiccup must not record a transcript entry the strict
  Lua-side JSON reader can never parse.
- **Handshake = numbered files, tmp+rename both directions.** Harness writes `req-<n>.json`
  `{seed, chapter, turn, faction, board}` into `PT_LLM_DIR` and polls (wall-clock deadline — at 240fps a
  frame budget would be 4× too impatient); sidecar answers `resp-<n>.json` `{orders, rejected}`, lowest
  unanswered request first, and drains pending requests before honoring its `stop` file — **which `run.sh`
  touches when the run ends**, so the sidecar saves its transcript and exits on its own (no Ctrl-C-dependent
  save). Every write on both sides is tmp+`rename` so a poller never reads a half-written file; `run.sh llm`
  clears stale handshake files (a leftover `resp-1.json` would satisfy the first poll instantly with last
  run's orders), the sidecar tolerates a request vanishing mid-step (that cleanup can race a sidecar started
  first) and warns at startup about pre-existing requests (usually a crashed prior run).
- **Validation lives sidecar-side; the harness re-checks only what can change.** Orders pass
  `validate_orders` against the request's own board before they ship — including: attack targets must be
  foes and staff targets allies (friendly-fire "attacks" would blind-A into the Trade/Item submenu); a unit
  the exporter gave no `range` (staff-only/weaponless) can target nothing; `seize` is gated on the board's
  objective (the export carries no goal tile). The Lua executor re-checks just the mid-phase deltas (target
  died to an earlier order → reject before input) and stops on failed menus without rescue input. Any
  live-policy failure (endpoint down) still answers the harness with an `{error}` response — a fast
  diagnosable FAIL, not a 90s timeout;
  a replay-mode transcript miss does the same and exits non-zero — CI/replay stays closed-world.
- **Exported unit ids: blue = charId (PCs are unique), red = 1000+slot** — generic enemies *share* a charId,
  so the slot disambiguates which brigand an attack order targets.
- **Lua JSON is a vendored ~200-line subset (`tools/playtest/json.lua`), not a library.** mGBA's Lua has no
  JSON; encode writes sorted keys (deterministic bytes, mirroring the serializer doctrine), decode rejects
  trailing garbage (a truncated file must not half-parse into plausible orders). Unit-tested without mGBA
  (`test_json.lua`, 45 asserts) + a cross-language round trip (Lua req → Python sidecar → Lua resp) verified.
- **M2 limitations (deliberate, → M3):** staff orders fail closed as unsupported. Attack command/weapon/target
  selection now runs through the state-driven controller below; choosing among multiple legal targets by
  policy remains an M3 concern. In-emulator prologue
  replay needs local mGBA (CI has none — the platform rule); the protocol itself is fully unit-tested.
_Decided: 2026-07-02 (CLAUDE; pipeline track. Epic #63 M2 + Nicolas's free-model direction; 23 new Python
asserts + 45 Lua asserts in make test)_
