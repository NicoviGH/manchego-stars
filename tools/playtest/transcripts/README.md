# Playtest LLM-player transcripts (#63)

Recorded per-turn decisions for the LLM-player sidecar, keyed by
`hash(serialize_board) + seed + chapter + turn` (see `tools/playtest/llm_player.py`).

- **Recording** (local, needs a model): run the sidecar with `--record` while
  `tools/playtest/run.sh llm` plays — cache misses call the configured model
  (`PT_PROVIDER` / `PT_MODEL` / `PT_BASE_URL`; `PT_PROVIDER=openai` against a local
  Ollama serve is the free path) and append here.
- **Replaying** (default, zero cost, deterministic): the sidecar serves recorded
  decisions only; a miss is a hard FAIL. Commit a transcript once a recorded run is
  worth replaying — it is the fixture that makes the `llm` scenario reproducible.

The board hash keys on the serialized board, so a transcript survives only as long as
the chapter's starting state does — a rebalanced enemy or moved deploy slot invalidates
the affected turns (by design: replaying stale orders against a changed board would be
noise, not signal).
