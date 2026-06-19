# Handoff — Content track 🔒 live state

Per-track live state for the **content lane** (Ch2+ slices, dialogue, art). Worktree doctrine,
ownership map, and trunk rules → `CLAUDE.md` §Tracks (read first; the lane guard is
`check.py check_lane_ownership`). Parallel-work + seam model → `docs/decisions.md` §Delivery model /
§Seam enforcement. Backlog → GitHub issues (#49 ① Content). **Shared builds/gotchas/rules → `HANDOFF.md`
+ `CLAUDE.md`; this file holds only my current state + content-lane-specific gotchas.** Don't touch
`HANDOFF-pipeline.md`.

## Now (2026-06-19) — ch02 dialogue fully LOCKED; host wiring is the next gate
All three ch02 cutscenes are now locked text in `ch02-cold-welcome.yaml` — opening, turn-3 rear-ambush
bark, and the **targos-inn ending** (`2e60003`, #22). The ending lands the **Sephek breadcrumb**: town
blames the druids' Auril rumor; **Rootis** IDs the dagger-of-ice kill from Hlin's briefing (no fight);
camp = one narration card; **RBG** calls the fork north onto the druids' trail (Messie bounty left for
ch06). **New canon** in `decisions.md` §Story (Sephek arc): distinct from Ravisin (ch05); his reckoning
is held for an **Act-II multi-boss slot** (ch00 already uses the Torrga caravan as its *setting*); stale
"Torrga = payoff venue" note fixed in `lore/sephek-kaltro.md`.
All ch02 cutscene text is **unwired** — eventscript + host wiring is next (MNC2 still drops to vanilla
Ch3). ⚠ Wiring flag still open: the rear-ambush bark line is 31 chars, past the 29-char on-map bubble
wrap → at insertion it wraps / needs an `[LF]` split; verify the right-side bubble isn't pushed offscreen.

## Next (priority order)
1. **ch02 host wiring** — host ch02 in the decomp + the eventscripts that consume the three locked
   cutscenes (opening / rear-ambush / targos-inn) via `build_campaign.py inject_*`, so MNC2 stops dropping
   to vanilla Ch3. Mind the rear-ambush bubble-width flag at insertion. Then Vellynne cutscene portrait
   (#19) + in-game motion review of all three scenes.
2. Supporting content as Ch2 needs them: enemy YAML pass #18, NPC/recruit stubs #17, recruit schedule
   (#45 item 5), world-map unlock #29.
3. Art passes layer on already-playable slices: portraits #19, overworld sprites #38.

## Watch out (content-lane only)
- **Writing any dialogue → invoke the `dialogue-pass` skill first.** Voice grounding lives in the repo:
  per-NPC `lore/*.md` §Voice bibles + `lore/frostmaiden-voices.md` (canon cast) + the FE8 cadence corpus
  `fireemblem8u/texts/texts.txt`. Read sources BEFORE asking Nicolas; bring drafts, not questions.
- Long unit names overflow FE8's name buffer — add a short `fe_name` (≤12) to new units.
- Story bodies are `make`-regenerated; gate text changes with `python3 tools/verify_text.py`.
