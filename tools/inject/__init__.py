"""The injector: every pass `build_campaign.main()` runs, and what they share (#389).

The shared layer -- decomp.py (decomp paths + brace-patch primitives), paths.py, hosts.py,
text.py, scenes.py, cast.py, units.py, maps.py, ... -- sits under the domain passes (one
module each: names, sms, battle_anims, ...), which sit under chapters/, one module per
hosted chapter. chapter_ids.py is the leaf holding every chapter id another module reads.
engine_patches.py -- applies the campaign-agnostic engine changes, engine/patches/ (#410)

See docs/decisions.md -> Engine/content file seam (#50).
"""
