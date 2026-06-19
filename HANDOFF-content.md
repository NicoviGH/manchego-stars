# Handoff — Content track 🔒 live state

Per-track live state for the **content lane** (Ch2+ slices, dialogue, art). Worktree doctrine,
ownership map, and trunk rules → `CLAUDE.md` §Tracks (read first; the lane guard is
`check.py check_lane_ownership`). Parallel-work + seam model → `docs/decisions.md` §Delivery model /
§Seam enforcement. Backlog → GitHub issues (#49 ① Content). **Shared builds/gotchas/rules → `HANDOFF.md`
+ `CLAUDE.md`; this file holds only my current state + content-lane-specific gotchas.** Don't touch
`HANDOFF-pipeline.md`.

## Now (2026-06-19) — `ch02-rear-ambush` bark LOCKED; targos-inn is next (needs Nicolas)
`ch02-rear-ambush` turn-3 bark locked (`76cd540`, #22): speaker **Wolfram** (Nicolas's pick — keeps the
decisive-command beat off Braulo twice in one chapter, and ties to the sled Wolfram forged in ch01 /
re-plates at the inn). Text in `ch02-cold-welcome.yaml` turn-3 event: *"Wolves at our backs — the sled." /
"Hold here. I've got the rear."* Text-only YAML, **unwired** (eventscript + on-map bubble deferred) →
ROM-neutral. ⚠ **Wiring flag:** line 1 is 31 chars, past the 29-char on-map bubble wrap → at insertion it
wraps / needs an `[LF]` split; verify the right-side bubble isn't pushed offscreen.
(Earlier same day, all shipped: the Ch2/Ch1 inn drift bug is fixed — Targos-inn is now Wolfram **re-plating
raid battle-damage**, not first-armoring; soft-penalty = chest + post-chapter gold forfeit.)

## Next (priority order)
1. **`ch02-targos-inn`** (chapter end) — the big multi-beat scene (frozen-sacrifice discovery, frost-druid
   glimpse = Ch4 seed, inn room/camp split, **Wolfram's re-plating payoff**, Maer Monster + Lonelywood
   rumors). **Needs Nicolas's beat intent before drafting.** Then **ch02 host wiring** (not built — MNC2
   drops to vanilla Ch3) + Vellynne cutscene portrait (#19) + in-game motion review.
2. Supporting content as Ch2 needs them: enemy YAML pass #18, NPC/recruit stubs #17, recruit schedule
   (#45 item 5), world-map unlock #29.
3. Art passes layer on already-playable slices: portraits #19, overworld sprites #38.

## Watch out (content-lane only)
- **Writing any dialogue → invoke the `dialogue-pass` skill first.** Voice grounding lives in the repo:
  per-NPC `lore/*.md` §Voice bibles + `lore/frostmaiden-voices.md` (canon cast) + the FE8 cadence corpus
  `fireemblem8u/texts/texts.txt`. Read sources BEFORE asking Nicolas; bring drafts, not questions.
- Long unit names overflow FE8's name buffer — add a short `fe_name` (≤12) to new units.
- Story bodies are `make`-regenerated; gate text changes with `python3 tools/verify_text.py`.
