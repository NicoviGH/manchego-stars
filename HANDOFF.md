# Handoff — Manchego Stars · live state

The **single** live-state doc (one trunk, feature-flow — no per-lane handoffs). **What shipped** →
`git log --oneline -20` + closed issues, not here. **Backlog** → GitHub issues. **Decisions** →
`docs/decisions.md`. **Operating instructions** → `CLAUDE.md`. Run `/handoff` to refresh this file in place.

## Workflow — feature-flow
Issue → short-lived `feat/<slug>` branch off `main` → an ephemeral worktree → PR → CI + `/code-review`
→ squash-merge → drop the branch + worktree. No fixed lanes; a feature may span engine + content
(`decisions.md` → Coordination model). Hard invariants: no character/chapter/plot in `.c`/`.s`
(`check.py check_engine_campaign_agnostic`); never commit the `fireemblem8u` submodule pointer.

## Current release
**v0.1.0** friend release — Ch1 playable. Builds:
- `tools/build.sh dist` — **the friend build** (with the #43 opening montage), stamped into `dist/`.
- `tools/build.sh test` — lean dev build (straight-to-map boot).
- `make TESTCH=1` — Ch1 **sandbox** (whole cast + foes pre-deployed, New Game boots onto the map) for playtest.

Versioning `v0.<chapters-playable>.<patch>` (`VERSION` file). **Never a bare `make` for a shippable
ROM** (the wrapper applies the decomp shebang fix; a bare `make` dies on the gfx tools on macOS).
ADR: `decisions.md` §Distribution.

## Tools (quick ref)
- `make difficulty CH=chNN` · `make difficulty-gate` (enforcing parity curve) · `make test` · `make check` (drift).
- `tools/playtest/run.sh recordanim` — capture **any** cast member's battle anim on a `make TESTCH=1` ROM
  (`PT_CHAR=<id>`: braulo marty meesmickle wolfram prof-rbg rootis sclorbo pinky; a staff user FAILs
  cleanly). `tools/playtest/make_gif.py recordanim <id> --open` → review GIF. `recordrbg` = RBG on the
  real campaign (checkpoint). Other scenarios: `win|gameover|ch01win|clear|fuzz`.
- **Delivery to friends:** commit a **GIF** (never MP4 — a committed `.mp4` is a binary download, not
  inline on GitHub) to `docs/demo/` + push.

## Now / Next

### Content — Ch2 "Cold Welcome" (#22): art complete; title card + load-test remain
- **(a) Dialogue reground** — ✅ DONE, merged in #70 (`37f327c`): opening chwinga-adoption beat
  (Sclorbo's kin + Marty's Chagaccino), turn-1 RBG→Pinky archer tutorial (fliers-vs-bows debut),
  de-sledded rear bark + ending card. Host wired (3 opening beats + turn-1 tutorial scene reusing the
  dead `Ch3_Turn2Player` slot + turn-3 bark). Msg-id reuse vetted clean (0x98d/0x98f free; 0x991's only
  live ref is Bazba's talk in the emptied Character list).
- **(b) Chwinga + Vellynne art** (#38/#39/#19): **DONE** — chwinga map sprites (#74 `45d62fb`),
  portraits + Mote/Rime/Glimmer names (#75 `fb8f3ac`), Vellynne bust (#19 `3efdd29`). The whole chwinga
  look = Sclorbo's sprite & bust reused with the icy-blue glow recoloured spirit-green (he IS a chwinga),
  build-derived from his assets (no committed copies). Vellynne = FE-Repo Sonya (Witch) mug with a
  magenta→snow-white hair recolor (`portraits/vellynne.py`, dresses the Ismaire slot; credit JeyTheCount).
  ADRs in decisions.md Art & Audio. STILL OPEN (lighter): the **title card** ("Cold Welcome" —
  `gen_chapter_title` atlas missing C/W/d/m glyphs).
- **(c) mGBA load-test** ch01→ch02→win→chains (chwinga LOAD, archer threatens pegasi, survivors deliver
  charms). Fast via `make TESTCH=1` (wire a ch02 sandbox) or the `recordrbg`/checkpoint path.
- Per-unit art/anim follows the **convention homes** — `inject_battle_anims` / `inject_battle_platforms`
  docstrings (how) + `decisions.md` Art & Audio (why) + the **`custom_unit` issue template** (per-unit
  checklist); open one issue per remaining cast/enemy.
- Supporting: Vellynne portrait #19 · ch02 title card · enemy YAML #18 · NPC stubs #17 · world-map #29 ·
  overworld sprites #38 · onboarding-parity #64.

### Pipeline — playtest / parity
- **LLM-player #63 — M2 next** (M1 landed): sidecar + `llmDrive` handshake, **replay-only** from a recorded
  transcript on a built ROM (deterministic, zero LLM cost). Then M3 live policy (`PT_MODEL`, per `claude-api`
  skill) → M4 soak→curve → M5 vanilla-FE8 validation. Swap point: `clearbot.lua pickTarget`.
- **Land `balance_locked: true` on ch00/ch01/ch02** — the per-chapter parity gate (#48b) is enforcing but
  inert until a chapter opts in; those three read OK on the curve.
- #53 tail (FE8 Ch13 ref → our ch08): ~11 standard weapons to model; informational (ch08 is scripted-defeat,
  never CI-gated) — do only if idle. Other mechanics leaves: d20 crit #11, spell-economy #9, iconic matchups #8.

## Gotchas (cross-cutting)
- **Additive, never global** (content art): clone classes / new terrain slots / appended `banim` rows;
  never edit a shared vanilla class/anim/terrain in place. `decisions.md` Art & Audio + the `inject_*` docstrings.
- **Engine hooks live in `tools/inject/engine_hooks.py`** (guarded by `check_engine_guards_present`); engine
  stat changes to the chosen lord go in `EndPrepScreen`, not a phase-start seam.
- **New decomp patch target → add it to `PATCHED_DECOMP_FILES`**, or the build is non-idempotent.
- **Vanilla decomp reads go through `build_campaign.vanilla_decomp_text()` (HEAD)**, never the worktree —
  it also strips inherited git env (`GIT_DIR` overrode `-C` discovery → exit 128 under the pre-commit hook
  in a worktree; don't reach for `--no-verify`).
- **`make`-green can't prove apply timing** — `tools/playtest/` is the dynamic arbiter. Scenarios need a built
  ROM + `lua` (`brew install lua`); regenerate `symbols.lua` (auto by `run.sh`) after a rebuild.
- **CI unit tests run in the `build` job, not the lightweight `checks` job** (they need the submodule +
  numpy/PIL); a new test needing a new lib → add it to the `build` job's deps.
- **Distribution is the private pre-patched `.gba`** — the decomp build is non-matching vs retail (~67% of
  bytes differ), so no small public patch exists. `tools/make_bps.py` is correct but intentionally unwired.
- **Save layout must stay stable for testers** (#59): `check_save_layout_stable` reds on a `BWL_ARRAY_NUM`/
  `WIN_ARRAY_NUM`/`SAVEMAGIC` drift → that drop needs a per-release starter `.sav`.
- **Don't reuse a playtest checkpoint across an injection/build change** — only across pure graphics-byte
  swaps; a stale save-state shows the map/menu, never the battle.
- **Writing any dialogue → invoke `dialogue-pass` first** (voice grounding: per-NPC `lore/*.md` §Voice +
  `frostmaiden-voices.md`; story sources: the DM-notes PDF + the Frostmaiden book via `pdftoppm`). Story
  bodies are `make`-regenerated; gate text changes with `python3 tools/verify_text.py`.
- **`msg-id` vetting is treacherous** — `data_battlequotes.c` stores ids 4-digit zero-padded (`0x0935`);
  vet in the `0x0XXX` form, not naïve hex-grep. Long unit names overflow FE8's buffer → add a short
  `fe_name` (≤12). Reward placement follows `parity_reference`, not chapter number.
- **Chapter hosting** (model on `inject_ch01`/`inject_ch02`): each chapter rides the *next* vanilla slot
  (ch01→2, ch02→3), chained via `MNC2(<next slot>)`; new snow chapters set `battleTileSet` `0` (open) or
  `0x15` (rough).
- **Vanilla-only (monster/exotic) weapons belong in `difficulty.py`**, not the content-owned `WEAPON_ITEM_ENUM`.
- **Curation gotcha (#48):** filter `events_udefs.c` arrays to RED units that **carry weapons** (excludes
  cutscene arrays + unreferenced skirmish data).
