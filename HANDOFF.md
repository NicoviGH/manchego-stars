# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-08-09 (Opus). **`main` carries only this handoff commit; no code landed on it.**
All of this session's work sits on **`feat/25-ch05-reliquary-visit-text` (7 commits, pushed)
behind open PR #253** — nothing is merged. The checkout is left on that branch.

`HANDOFF.md` lives on `main` and NOT on the branch — the pre-commit drift guard rejects a branch
copy, because merging one silently overwrites main's live state (it cost us ch04's on 2026-07-30).
Refresh it on `main` after #253 merges, never on the branch.

## In flight

**PR #253 — `feat/25-ch05-reliquary-visit-text`, OPEN, unreviewed, unmerged.** Six commits: the
four reliquary visit lines; their skeleton faces + backdrop; the `ch05reliquaries` scenario; the
portrait-geometry fix; `PT_RECORD_BOXES`; the matrix ROM cache. It is green (`make matrix` 17/17,
273 + 70 unit tests, `verify_text` 0 runaway) and reviewed by nobody. **No `/code-review ultra`
has run on it — that is user-triggered.**

## Next task

**Wire ch05's village-raid RACE — it is the next thing, and it BLOCKS a dialogue decision.**
Full write-up on **#25** (2026-08-09 comment), which is the source. The short version: the
chapter's declared structure — undead racing the party for the four reward-sites, plus the
`crest-of-cold-iron` save-all bonus — **is prose only.** No village-destruction wiring exists, no
save-all payout exists, and the YAML actively claims *"Wired at inject_ch05"*, which is false.

It gates writing: reliquary-south's box 6 warns about raiders the game cannot send. Wire the race
and the line is simply true as written; leave it unwired and the line must be rewritten to promise
less. **Nicolas was offered three replacements (A shouting outside / B Ravisin still out there /
C you're being followed) and has NOT chosen — do not rewrite it until the race question settles.**

Also owed and NOT started, all listed on #25: the Basil→Sahnar recruit text (`0x9CC`), the opening
(`0x9BA`–`0x9C4`), Ravisin's death quote, the arena tutorial, the no-Lupin branch, enemy reskins.

## Current state

- **Environment: Nicolas is on his Mac. ROM builds, `verify_text` and mGBA playtests are LIVE.**
- **Gate: `make matrix` 17/17** on the branch — `ch05reliquaries` is new and reads all four
  reliquary doors (gift identity + that each door actually SPOKE). `ch05village` stays; it covers
  the south door alone.
- **`make matrix SUITE=<chapter>` is ~11s cached; the full gate is ~6min.** Iterate on the chapter
  suite. The full matrix is the push gate, not the edit loop — see `decisions.md`.
- **The ch05 reliquary visits are DONE end to end** and confirmed in-engine: 27 boxes across four
  doors, four Eden/L95 skeleton busts on collision-free slots, `BG_INTERIOR_BROWN`.
- **ch05's opening and recruit still play VANILLA prose.** In-game this looks like a bug and is
  not one: `0x9CC` runs vanilla's Joshua/Natasha scene, and because Hlin Trollbane's bust is
  dressed onto the Natasha slot the player watches *Hlin* talk to *vanilla Joshua*.
- **Reopened for cosmetics:** **#24** (the ch04 snag falls into a stone bridge because
  snowy-bern's `BRIDGE_SNAG` metatile 36 is declared but never painted) and **#21** (Baxby's
  recruit plays over a green summer village). Both have decided fixes on the issues.
- **BG picks decided 2026-08-09:** Bryn Shander → FE-Repo `Fenriel's BG/Winter BG 06` (#21);
  Bremen → `Winter BG 04` (#27). Both already 240x160. Don't reuse `BG_MS_TARGOS_WINTER` a third
  time.
- **Cross-agent continuity:** Nicolas uses Codex only between Claude sessions. Codex must leave an
  explicit HANDOFF entry naming what it changed, the active branch/PR and commit state,
  verification actually run, and the exact next step. Ordinary short-lived feature branches in this
  checkout, one at a time — **do not create worktrees unless Nicolas explicitly changes that.**

## Gotchas most likely to bite next (long form in `docs/decisions.md`)

**This session's headline: three data checks can all pass while the thing is visibly broken.**
Three of the four ch05 faces rendered corrupted — a block of skull smeared over the eye sockets.
The clip model said 0 dropped, the on-disk sheets decoded correctly, and an OAM probe proved every
object draws. All three were true and none could see it, because the corruption happened at DRAW
time from a different table (the slot's mouth/eye geometry). **Nicolas caught it by looking at the
screen.** Verify rendering by rendering.

**The runner-up, same shape: I invented a bug from a bad crop.** I "found" a missing pauldron by
cropping the frame at the wrong x — the face is drawn MIRRORED at screen x0–95 (`screen_x =
95 - bust_x`), not where I looked. Measure the placement before concluding the art is wrong.

**And: a question is not a work order.** "Is that normal?" got repair previews when it wanted the
untouched source diffed against ours. Check the reference, give a verdict, stop.

The standing ones:

- **Read decomp data through `git show HEAD:`, never the built tree** — our injections are build
  artifacts. Signature: `make check` failing `test_difficulty` + `test_map_tileset` together right
  after a ROM build. Fix, don't debug:
  `git -C fireemblem8u restore src/data/chapter_settings.json data/data_8B363C.s`.
- **A HANDOFF lead is a hypothesis.** This session's proof: the ch05 YAML asserted the save-all
  bonus was "Wired at inject_ch05". It is not wired at all.
- **Before building tooling, grep for it.** `SUITE=` already existed while the full 7-minute matrix
  was run four times over.
- **A scenario's verdict only covers what it READS.** `ch05village` passed for months proving
  nothing about three of the four doors.
- **Post-injection SMS ids and goal ids cannot be read from HEAD or the working tree** — run the
  injector and read the result.
- **A failing playtest may be the WRONG ROM.** Boot flags are per-chapter, and so is
  `PT_HOST_CHAPTER`. `run.sh` refuses this in 0s off `.build-config.json` — **do not reach for
  `MX_SKIP_ROM_CHECK=1`**. **Exception: `mapshot`/`mapfull` are chapter-GENERIC.**
- **`harness.lua` is one Lua chunk AT the 200-local ceiling** (2 slots free). Hang new helpers off
  an existing table (`INSPECT`, `TUNE`) or inside the scenario, never a new top-level `local`.
