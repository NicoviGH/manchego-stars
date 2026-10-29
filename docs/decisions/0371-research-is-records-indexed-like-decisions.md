---
id: 371
title: "Research is kept as records under docs/research/, indexed like the decisions"
date: "2026-10-27"
section: "Documentation Model"
issues: [510]
---

# Research is kept as records under docs/research/, indexed like the decisions

Reference research (what guides, forums and papers say, each claim cited) goes in
`docs/research/`, one record per topic with the decisions' front matter (`id`, `title`, `date`,
`section`, `issues`) plus `tags`. `tools/gen_decisions_index.py` generates `docs/research.md`
from it the same way it generates `docs/decisions.md` (one generator, two collections), and
`tools/check.py` holds both fresh and well-formed.

Why (Nicolas, 2026-10-27): research that lands as one long document is grepped, and grepping a
long file puts the whole of it into a session's context. A title and tags in front matter are
searchable from the index alone, so a session opens only the record it needs -- the reason the
decisions were split (#384). Research is evidence, not a decision: a record never says what we
do, and a decision that rests on it cites the record.
