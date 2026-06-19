"""Build-time injection layer split out of build_campaign.py.

decomp.py  -- shared decomp source paths + brace-patch primitives (pipeline + content)
engine_hooks.py -- the campaign-agnostic engine C-source hooks (pipeline-owned)

See docs/decisions.md -> Engine/content file seam (#50).
"""
