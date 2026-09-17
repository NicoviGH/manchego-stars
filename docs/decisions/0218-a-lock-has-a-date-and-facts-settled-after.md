---
id: 218
title: "A LOCK has a DATE, and facts settled after it still apply"
date: "2026-08-19"
section: "Operational Gotchas (durable)"
issues: [25, 293]
---

# A LOCK has a DATE, and facts settled after it still apply

ch05's scene 17 called Basil **"he"** twice. Her text was locked 2026-07-30; her `gender: female`
was settled 2026-08-08. Nobody contradicted anybody — **the lock simply predated the decision**,
and "locked" was read as "checked", which it never was.

So a locked scene is frozen against *re-litigation*, not against *facts*. Before wiring one, diff
its lock date against anything settled since about the characters it names — pronouns, class,
who is recruitable, who is even alive. Correcting a scene to match a later-settled fact is not
reopening the dialogue pass and does not need a fresh one; it is the same kind of change as
updating a stale constant. Preserve box count and rhythm, note the correction and its date in the
scene's own `description:`, and move on.

The exposure grows with the gap: ch05's endings were locked in July and are being wired in
August, and they are the LAST scenes anyone will read before they ship.
