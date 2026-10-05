---
id: 328
title: "Our battle anims link past the 16MB image, in their own object"
date: "2026-10-04"
section: "Engine & Tech Stack"
issues: [26]
---

# Our battle anims link past the 16MB image, in their own object

**Every battle anim the build adds goes in `linker_script_banim_ext.txt`, which engine patch
0016 links as `data_banim_ext.o` at 0x09000000.** Vanilla's anim object keeps 0xC02000 and its
own script, untouched.

Vanilla's region runs 0xC02000-0xEE0000, with battle terrain fixed right behind it, and vanilla
fills it to 0xE47180. That left ~0.6MB for ours. ch06's merfolk overran it by 111KB, and the
link failed with "cannot move location counter backwards". The GBA bus addresses 32MB, so the
space past vanilla's 16MB image gives 16MB of headroom. The ROM grows from 16MB to ~17.3MB.

Why a second object, rather than moving vanilla's: moving `data_banim.o` would shift every
vanilla anim's address, and the baserom incbins are opaque bytes that may hold pointers into
them. With ours split out, `0xC02000-0xEE0000` in the built ROM is byte-identical to the base
ROM (measured 2026-10-04).

Two latent bugs surfaced with it, and both are fixed:

- **An anim object did not depend on its own script.** The rule listed the files a script
  names, so a script that dropped files left a stale object holding them. Both rules now
  depend on their script.
- **The anim step cache never watched a root-level file.** A hit restored every anim row but
  no linker script. It only worked because of the bug above. `step_cache.snapshot` now takes a
  file as a scope root, and `warm.BANIM_SCOPE_ROOTS` adds the script.

Proof the engine plays an anim from past 16MB: `recordch05platform` (full battle anims against
ch05's vendored skeletons, built through a cache hit) PASSES.
