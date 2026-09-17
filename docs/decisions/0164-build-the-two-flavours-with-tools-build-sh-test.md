---
id: 164
title: "Build the two flavours with `tools/build.sh test|dist` — a plain `make` after `build_campaign --montage` silently clobbers the montage."
date: "2026-06-17"
section: "Story & Dialogue"
issues: []
---

# Build the two flavours with `tools/build.sh test|dist` — a plain `make` after `build_campaign --montage` silently clobbers the montage.

The `fireemblem8.gba` make target ALWAYS re-runs `build_campaign.py`, appending `--montage` only when `MONTAGE=1`. So the
intuitive "run `build_campaign.py --montage`, then `make`" sequence re-runs the generator WITHOUT the flag on that second
step and reverts the montage sources → a no-opener ROM byte-identical to the test build (this masqueraded as a "montage
won't compile / stale-objects" bug for a whole session; it was never a compile problem). The montage flavour MUST be one
command: `make MONTAGE=1`, wrapped as `tools/build.sh dist` (test = `tools/build.sh test`). A correct montage ROM's md5 is
NOT the no-opener `142971e3`. Sanity check after a build: `grep -c "skip intro monologue" fireemblem8u/src/gamecontrol.c`
= 0 for dist, 1 for test. Also: the decomp ships Linux `#!/bin/python3` shebangs that do not exist on macOS, and any
`git checkout` inside the `fireemblem8u` submodule reverts the fix — the next build then dies on `bad interpreter`,
minutes in, from a Makefile rule that looks unrelated. `setup-toolchain.sh` and `build.sh` both rewrite them, but the
DOCUMENTED build command is plain `make`, which bypassed both, so the failure kept recurring (three times in one session,
2026-08-05). **`build_campaign.normalise_decomp_shebangs` now re-applies it idempotently on EVERY build** — the hole is
closed at the one place every build passes through, rather than in wrappers a caller has to remember.
_Decided: 2026-06-17; root-caused + dist (with opener) GIF-verified end-to-end
(`run.sh recordopening`: title → New Game → lore crawl → Ten Towns tour → prologue map)._
