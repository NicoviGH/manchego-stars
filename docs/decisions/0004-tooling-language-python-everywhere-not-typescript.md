---
id: 4
title: "Tooling language: Python everywhere. NOT TypeScript."
date: "2026-06-04"
section: "Engine & Tech Stack"
issues: []
---

# Tooling language: Python everywhere. NOT TypeScript.

The original plan named a Node/TypeScript toolchain (`build-campaign.ts`, `build-events.ts`, `pull-srd.ts`, `map-class.ts`). Reality: the injector is `tools/build_campaign.py`, with `tools/portrait_tool.py`, `tools/ref_to_bust.py`, `tools/verify_text.py`, and the index generators `tools/gen_chapter_index.py` / `tools/gen_class_index.py`. No Node, no `.ts`, and (since 2026-06-09) no Ruby — the index generators were ported to Python so `tools/check.py` can import them for the freshness gate and CI needs one runtime. The build interpreter is Homebrew `python@3.12` (numpy/pillow/pyyaml; see `tools/setup-toolchain.sh`).
_Decided: 2026-06-04 (supersedes the PRD's TS toolchain plan); 2026-06-09 (Ruby index generators ported to Python)_
