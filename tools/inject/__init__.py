"""The injector: every pass `build_campaign.main()` runs, and what they share (#389).

The shared layer -- decomp.py (decomp paths + brace-patch primitives), paths.py, hosts.py,
text.py, scenes.py, cast.py, units.py, maps.py, ... -- sits under the domain passes (one
module each: names, sms, battle_anims, ...), which sit under chapters/, one module per
hosted chapter. chapter_ids.py is the leaf holding every chapter id another module reads.
engine_patches.py -- applies the campaign-agnostic engine changes, engine/patches/ (#410)

Working in it (the why is in ADR 0300 and the ADR each line cites):

  * Where a name lives: `inject.source.def_source(name)`, or grep `^def name` / `^NAME =`.
    A chapter id another module reads lives in chapter_ids.py; one only its chapter reads
    stays in chapters/chNN.py.
  * A test stubs with `inject.namespace.stubbed('NAME', value)`, never
    `mock.patch.object(inject.X, ...)`: each importer holds its own binding. A registry
    discovers constants with `inject.namespace.injector_constants(pattern)`, never `globals()`.
  * Never name a local `inject` in a file that uses `inject.X`. A function-local
    `import inject.X` makes `inject` local to the whole function.
  * A new pass is a `Step` in steps.py declaring its `writes`, `needs`, `flags` and `scope`
    (ADR 0304). `INJECT_STRICT=1` names the step behind an undeclared write.
  * A hosted chapter's settings row and event group go through chapter_frame.py (ADR 0308).
  * A new message is a name in message_alloc.py `APPENDED_MESSAGES`, read with
    `appended_message_id` (ADR 0306). A new chapter YAML key goes into tools/chapter_schema.py
    first, or every loader refuses the file (ADR 0307).
  * `decomp.DECOMP` is the BUILD tree; `decomp.SUBMODULE` is vanilla (ADR 0302).
  * A refactor is gated by tools/injection_fingerprint.py on the ROM configurations
    tools/fingerprint_reach.py says the change reaches (ADR 0309), ~2.5 min each. A KILLED
    run leaves its stashed state as `*.fingerprint-bak`; move those back before the next run.

See docs/decisions.md -> Engine/content file seam (#50).
"""
