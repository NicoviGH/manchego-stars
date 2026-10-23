---
id: 363
title: "A chapter not written yet gets no difficulty reading"
date: "2026-10-22"
section: "Combat System"
issues: [510]
---

# A chapter not written yet gets no difficulty reading

Nicolas, 2026-10-22: a `status: planned` chapter does not exist yet. Period. Its draft YAML is
never read as a force.

Nicolas, 2026-10-23, edited in place: "lets run the future chapters as we build them." The
first version of this record gave a planned chapter its twin's numbers as a target. It no
longer gets any: a chapter is read as it is built. The curve lists a planned row as not read,
`make difficulty CH=chNN` says it is not written yet, and neither its draft nor its twin is
opened for it. (A parity run that walked FE8 Ch8 for ch08's target was what prompted this.)

History: the curve printed a planned row's twin numbers as its target (ADR 0087, now
superseded). The per-chapter report (`make difficulty CH=chNN`) read instead the draft's
roster and levels and printed them under a "seed, not authoritative" banner. That read broke
once the board and the combat read shared one force walk (#525). ch08's draft has an unarmed
entry with no position and no donor, and the walk asked it for AI.

**Now** a planned chapter has no reading at all: `_report_unwritten` and the curve's planned
row print that it is not written, and `unwritten_projection`, `planned_target` and
`vanilla_projection` are retired.

**A written chapter places every body it fields.** `danger_map.bodies` raises on a body with
no position, rather than leaving it off the map while the parity read still fights it. The
board and the force then could not stay the same list, and step 7's engagements index one
into the other.
