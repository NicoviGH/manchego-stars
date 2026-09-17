---
id: 241
title: "A battle anim binds to a CHARACTER, not to the cast"
date: "2026-08-15"
section: "Operational Gotchas (durable)"
issues: [25]
---

# A battle anim binds to a CHARACTER, not to the cast

The white moose is ch05's miniboss and the first unit to want a custom battle animation without
being a cast member. Every unit that had one before it rode a vanilla `CHARACTER_` slot, so
`inject_battle_anims` hardcoded its `_u25` binding as `[CHARACTER_<slot> - 1]` and read the slot
out of `PORTRAIT_MAP`. The moose has no such slot: it is the raw on-map pid `0xb9`, a
`gCharacterData` GAP, exactly like Ravisin at `0xb8`.

**The engine never cared.** `GetBattleAnimationId_WithUnique` reads
`unit->pCharacterData->_u25`, and that is the same field on a gap row as on a named one — the
gaps simply omit it, which defaults to `{0, 0}`, i.e. "no unique anim". The only thing standing
between the moose and a battle anim was the injector's marker STRING. So the fix is
`banim_u25_marker()`: a raw pid is addressed by `[0xb9 - 1]`, the identical designator
`raw_pid_portrait_data` has always written through, and a cast member still resolves to its
`CHARACTER_` enum. `RAW_PID_BATTLE_ANIMS` is the registry, and its unit declares `battle_anim:`
on the CHAPTER YAML that already owns its pid, class, AI and art — a `pcs/npcs` file would be a
second definition site and would put a miniboss on the deployable cast roster.

**The cadence is read off the donor's own script, never off a neighbouring row.** Nicolas chose
`clone_from: gwyllgi` for cadence, and the Gwyllgi's anim is `banim_cer_at1` (animId `0xB1`) —
internally "cer", for Cerberus. It is NOT `banim_mdg_at1` (`0xB0`), the Mauthe Doog's, which is
what Lupin's imported pounce reads; the two beasts are the unpromoted and promoted halves of one
line and vanilla gives each its own script. `cer_at1` runs growl (`mauthedoog_1`) → snap
(`mauthedoog_2`) → the shared contact hit → footfall away (`mauthedoog_3`), with **no screen
shake and no dirt kick**. The lance row's shake is the ARMOUR's weight; copying it onto a
quadruped would have been adapting a sibling row instead of reading the donor, which is the
exact mistake the sword row's comment was already written to prevent.

**The sandbox bench had a silent hole, and it is the same hole as #206.** `recordenemy` deploys
the TESTCH foes by CLASS, which is right for a class-level reskin and WRONG for a per-character
anim: a Gwyllgi deployed under the generic `0x80` monster charIndex plays the stock hound, so the
bench would have greenlit the opposite of what it was run for. The foe row now carries the
creature's OWN pid, and the scenario baits by pid rather than by class.

**The three-pose descale, for the next creature.** `--body 56` lands exactly the 88x64 the
injector's docstring names. `--noflip` because the master already faced left, like FE8's own
`cer_at1` sheet. No `--sharpen` (it grains a white flank) and no `--flat`: that palette is tuned
for warm hues and collapsed the blood-red antlers to tan — a chroma wash-out of the one accent
the creature is recognised by, which is the Arena palette lesson on a sprite.

_Decided: 2026-08-15 (Nicolas chose the donor; Claude wired it, #25)._
