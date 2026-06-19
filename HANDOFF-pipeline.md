# Handoff — Pipeline track ⚡ (instance B)

Live state for the **pipeline instance** (the CD machine — the part agents accelerate). The
parallel-work model is the ADR in `docs/decisions.md` (§Delivery model → Parallel work model /
Engine-content file seam); work tracker #50; backlog is **GitHub issues** (#49 ② Pipeline track),
not this file. Don't clobber the content track's `HANDOFF-content.md`.

## Start here (fresh instance — do this first)
You are the **Pipeline-track** instance for Manchego Stars (trunk-based, your own worktree).
1. Bootstrap an isolated build env: `tools/worktree-setup.sh ../ms-pipeline` (creates the worktree
   on branch `inst/pipeline` + symlinks the toolchain). `cd ../ms-pipeline`.
2. Read `CLAUDE.md` and `docs/decisions.md`, then continue from **Next** below.
3. Trunk-based: small commits, `git pull --rebase origin main` often, push when green, no
   long-lived branches, never commit the `fireemblem8u` submodule pointer.

## You own (edit freely)
- `tools/inject/engine_hooks.py` — the 5 campaign-agnostic engine hooks
- `tools/inject/decomp.py` — shared decomp paths + brace-patch primitives (content imports these;
  changing a signature ripples into `build_campaign.py`, so keep them stable / coordinate)
- `tools/difficulty.py`, `tools/fe_combat.py`, `tools/check.py` (drift guard), `tools/playtest/**`
- `.github/workflows/**` (CI), `tools/build.sh`, `tools/worktree-setup.sh`

## Hands off (content track owns — coordinate via an issue if you need a change)
- `campaigns/**`, dialogue, and `tools/build_campaign.py`'s `inject_*` + sprite/palette hooks
- If you need a new engine hook wired, add it in `engine_hooks.py` and add the one orchestrator
  call in `build_campaign.py` (the only content-file line you touch) — then update the guard.

## Next (priority order)
1. **#48 — difficulty engine → all chapters**: engine landed + **registry now covers Prologue, Ch1,
   Ch2 (9), Ch3 (10), Ch5 (23)** (curation method documented at the `PARITY_REFERENCE_UDEFS` block:
   eventscript-referenced arrays with armed RED units; excludes skirmish + cutscene arrays). Also
   shipped this session: warn-on-dropped-boss guardrail (#51), prologue boss weapon driven from YAML
   (#52, byte-identical). Remaining fast-follows:
   (a) **#53** — model FE8 monster + extended weapons (claws/eyes, halberd, venin, horseslayer) to
       curate the last refs **FE8 Ch4 (ch04/ch05), Ch6 (ch07), Ch13 (ch08)**; Ch4 is all-monster so
       its whole force is unmodeled until then;
   (b) wire the **hard CI gate** (verdict OFF → fail) once Ch2+ enemies are authored, so it doesn't red
       the build today; (c) leveled stat projection (#45 item 5). Note: the gate stays informative until
       the **content track authors Ch2+ enemy inventories** (curve shows our side 0.0 / `!!boss dropped`).
2. **Playtest platform**: grow `tools/playtest/` from the floor/ch01win scenarios toward an I/O
   harness → stability fuzzer → LLM-player (#49 dependency spine: `3c → I/O harness → …`).
3. Mechanics/flavor leaves once specced: lord-select UX #46, d20 crit #11, spell-economy #9,
   iconic matchups #8. Injection pipeline #14 / maps #40 gate content, so prioritize them if Ch2+
   authoring is blocked.

## Watch out
- New decomp patch target → add it to `PATCHED_DECOMP_FILES` (build idempotency / `count==1` guard).
- Engine stat changes to the chosen lord go in `EndPrepScreen`, not a phase-start seam.
- `make`-green can't prove apply timing — `tools/playtest/` is the dynamic arbiter; run it.
- Vanilla decomp reads go through `build_campaign.vanilla_decomp_text()` (HEAD), never the worktree.
- A behavior-preserving refactor should yield a byte-identical ROM (md5) — use that as proof.
