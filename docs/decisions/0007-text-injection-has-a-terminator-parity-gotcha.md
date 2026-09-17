---
id: 7
title: "Text injection has a terminator-parity gotcha (the reset's \"Huffman corruption\")."
date: "2026-06-04"
section: "Engine & Tech Stack"
issues: [46]
---

# Text injection has a terminator-parity gotcha (the reset's "Huffman corruption").

FE8 packs text two bytes per u16; `[X]` = the 0x00 string terminator. The packer (`textprocess.py`) pairs printable bytes two-at-a-time but emits each control byte (`[LF]`=0x01, `[X]`=0x00, the `[.]` pad=0x1F) as its own u16, which realigns the pairing — so each *run* of printables between control codes pairs independently. A run with an **odd** length makes its last char swallow the *following* byte; when that byte is the `[X]` terminator, the decoder runs past it into the next message (garbage + bleed-through). Vanilla pads odd names with `[.]` (`Franz[.][X]` vs `Seth[X]`); `build_campaign.py`'s `_term_pad` does the same — but the parity that matters is the **final run** (the printables after the last control code), **not** the whole message: a multi-line body whose earlier `[LF]` runs are odd can sum to an even total yet still have an odd final run that eats `[X]` (Pinky's pitch: 16+19+13 = 48 even, final run 13 odd → runaway). Note `verify_text.py` only flags *length* runaways (>~2133 vals), so a short bleed into the very next message passes its sweep — decode the specific ids (`verify_text.py 0xNNN`) and read the tail when authoring multi-line messages.
_Decided: 2026-06-04; refined 2026-06-25 (final-run parity — multi-line lord-select pitches, #46)_
