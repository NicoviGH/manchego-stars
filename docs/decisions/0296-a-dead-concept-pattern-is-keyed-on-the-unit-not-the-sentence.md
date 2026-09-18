---
id: 296
title: "A DEAD_CONCEPTS pattern is keyed on the UNIT, not on the sentence that happened to survive"
date: "2026-09-18"
section: "Working Conventions (Definition of Done)"
issues: [393, 298, 311]
---

# A DEAD_CONCEPTS pattern is keyed on the UNIT, not on the sentence that happened to survive

The 29/42-**CHARACTER** wrap was retired by #298 and registered in `DEAD_CONCEPTS` the same
day, which is the discipline this repo asks for. It was then swept three times:

| sweep | what it found | what it missed |
|---|---|---|
| #298 | the sentences in front of it | three docstrings |
| #311 | those three | eight in the chapter YAML — unscanned |
| #393 | those eight | **thirteen more**, in spellings no pattern matched |

Twenty-one sites, and the count kept growing because each sweep wrote its patterns from the
hits it could already see. `wraps at 29` does not match `29-char bubble`, `Text_BG wrap of 42`,
`~29-30 ch/line`, `the 29-wrap`, `29-column wrap` or `wraps at ~42` — and five of those were in
`build_campaign.py`, a file the scan has covered since the registry existed.

**So a pattern names the UNIT, not the phrasing.** The retired concept here is *a line width
priced in characters*; the durable pattern is a retired number adjacent to a character unit,
however it is punctuated, not any sentence a previous author wrote around it. A registry entry
that reads like a quotation is a registry entry that will be outlived by a paraphrase.

## Two guards the widening needed

**A palette depth is not a line width.** `col\w*` reaches "colours", and `128 colours` even
contains a `28`. A guard that cries wolf gets bypassed, so the number carries a
`(?<![\d.])` boundary and the unit alternation lost its bare `col`.

**Citing the record that RETIRED a concept is not restating it.** A retirement's title has to
contain the words it retired — *"We wrapped on-map talk at 29 CHARACTERS; the engine measures
PIXELS"* is the name of the decision that killed the character wrap — and four live citations
of it were flagged the moment the patterns got wide enough to see them. `DEAD_CONCEPT_CITATIONS`
exempts that **exact title phrase**, matched from `talk at 29 CHARACTERS` because a wrapped
comment breaks the line wherever it breaks. Deliberately NOT a general "the line mentions
`decisions.md`" escape: that would let any drift hide behind a citation. This is the same
judgement the registry already records for `_script_to_message` and `hasPrepScreen` — a guard
that rejects its own warning is worse than none — but as a mechanism rather than a carve-out.

## The sweep's real cost is the CONCLUSIONS, not the words

Four of #393's own rewrites swapped the unit and kept the sentence's conclusion. Measured
against `_wrap_fe_lines` at the live budget, every one was wrong: ch05's substitute (270px),
Sahnar's locked line (283px) and the no-Lupin prose (323px) all flow to **two** lines, which one
box holds — so those splits are PACING calls, and the "it cannot be one box" rationale was the
character rule talking. Only Nicolas's goodberry line (504px, three lines) is genuinely a
capacity split. The quoted wrapper breaks in those same comments were 29-column output too.

**A retired rule leaves its conclusions behind.** Deleting its vocabulary does not delete them,
and they read as current fact — which is the exact failure the registry was built for, one level
up. So a vocabulary sweep re-measures every claim it touches: if a comment says a line does not
fit, run the wrapper. `python3 -c "import build_campaign as bc, fe8_talk_font as f;
bc._wrap_fe_lines(line)"` is the whole cost, and a box holds two lines.
