# Handoff — Pipeline track ⚡ (instance B)

Live state for the **pipeline instance** (the CD machine — the part agents accelerate). The
parallel-work model is the ADR in `docs/decisions.md` (§Delivery model → Parallel work model /
Engine-content file seam); work tracker #50; backlog is **GitHub issues** (#49 ② Pipeline track),
not this file. Don't clobber the content track's `HANDOFF-content.md`.

## Launch this instance (paste as the kickoff prompt)
> You are the **Pipeline-track** instance for Manchego Stars (trunk-based, your own worktree).
> 1. Bootstrap an isolated build env: `tools/worktree-setup.sh ../ms-pipeline` (creates the
>    worktree on branch `inst/pipeline` + symlinks the toolchain). `cd ../ms-pipeline`.
> 2. Read `CLAUDE.md`, this file, and `docs/decisions.md`, then continue from **Next** below.
> 3. Trunk-based: small commits, `git pull --rebase origin main` often, push when green, no
>    long-lived branches, never commit the `fireemblem8u` submodule pointer.

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
1. **#48 — difficulty engine → all chapters**: next items (per-chapter enemy-pressure extractor +
   CI gate; confirm the ch08 "FE8 Ch13" informational flag once the extractor lands).
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
