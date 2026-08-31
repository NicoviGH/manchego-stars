@AGENTS.md

<!-- Every instruction that is not Claude-specific lives in AGENTS.md, which the line
     above imports in full. Two files describing how to work in this repo is exactly the
     drift this project guards against: AGENTS.md had silently fallen behind, still
     pointing the base ROM at Documents/Codex. Add project guidance THERE. Only things
     that are true of Claude Code specifically belong below. -->

## Claude Code

### Model Selection Guide

| Task | Model |
|---|---|
| Single C file edit (~200 LOC) | Sonnet (default) |
| Cross-cutting engine change (8+ files) | Opus with extended thinking |
| Generate dialogue, YAML, item descriptions | Haiku |
| ROM build smoke-test / mGBA memory reads | Script, no LLM |
