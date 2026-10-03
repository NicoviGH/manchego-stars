---
id: 326
title: "A chapter may carry an accepted party residual"
date: "2026-10-03"
section: "Combat System"
issues: [430]
---

# A chapter may carry an accepted party residual

#430 step 6. Nicolas accepted ch01-ch02's clear-load as the cost of having no Seth-tier unit
(ADR 0042 stands). Vanilla's Seth downs those bosses in 0.6 rounds and our best carry takes 1.0,
so our party clears each force at x1.41 the twin's rounds. Threat sits in band, and each force
copies its twin (force clear-load x0.97 and x1.00). The headline still read OFF (x1.36, x1.41), so
neither chapter could lock.

**A chapter may declare `accepted_residual: {party_clear_load: <ceiling>, adr: <decision>}`.**
`accept_residual` then passes a harder clear-load only when three things hold:

- threat is in band (threat is never excused);
- the force half of clear-load, which authoring controls, is in band;
- the party half is at or under the ceiling.

A force that drifts, or a party that falls further behind, still fails the gate. The row and the
chapter report name the decision (`[accepted ADR 0042]`).

ch01 (party x1.4078) and ch02 (x1.4081) carry a ceiling of 1.41, the figure Nicolas accepted.
**With them, ch00-ch06 are all `balance_locked`, and #430 step 6 is done.**
