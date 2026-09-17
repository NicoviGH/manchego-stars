---
id: 196
title: "A reskin keeps its donor's CLASS NAME, and that is the intent"
date: "2026-08-21"
section: "Operational Gotchas (durable)"
issues: []
---

# A reskin keeps its donor's CLASS NAME, and that is the intent

ch05's skeletons read "Soldier"/"Fighter", ch01's goblins "Soldier", ch03's kobolds "Brigand". No
reskin in `campaign.yaml` carries a `name:`, and none needs one.

**RULED (Nicolas, 2026-08-21): "the skins saying the real class is the expected pattern, so just
leave it as is."** The reskin changes what a unit LOOKS like, not what it IS — an FE8 Soldier
dressed as a skeleton is still a Soldier, and the class name is the player's read on its stats,
weapon type and movement. Renaming it would hide the one piece of information the class name
exists to carry.

Closed as a question. Do not re-open it per chapter.
