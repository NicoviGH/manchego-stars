---
id: 281
title: "Three routes to one sidecar, and the fix is that they must AGREE"
date: "2026-09-16"
section: "Operational Gotchas (durable)"
issues: [373]
---

# Three routes to one sidecar, and the fix is that they must AGREE

"Which sidecar JSON belongs to this chapter" is answered in three places, by three different
routes. The gate derives it from the chapter YAML's `map.file` (`check._chapter_sidecar`). The
build gets its stem from the `CHxx_LAYOUT` constants and never reads `map.file` at all. The
preview takes `basename(map.file)` against `map_placement_preview`'s own campaign root. They agree
for all seven hosted chapters today, and nothing made them.

**Drift there is worse than a crash.** `check_documented_tileset` would either skip in silence —
looking for a sidecar at a path that does not exist — or assert that the YAML agrees with a
sidecar the cartridge never loads. That is the "documentation nothing reads" failure #371 closed
for the tileset FIELD, reappearing one level up in how the file is LOCATED.

**The guard checks that they agree; it does not pick a winner.** The instinct is to make one
authoritative, and #371's own history is the argument against it: the first attempt at that bug
promoted the YAML and would have shipped a preview of a tileset the game never loads. It produced
right answers for a wrong reason, which is only visible if something compares the two. If they
cannot drift silently, neither has to win.

**Every route is DERIVED from source, and that is not a stylistic choice.** The CI `checks` job
is the only job that runs `tools/check.py`, and it installs pyyaml and nothing else with no
submodule checked out — so `import build_campaign` (Pillow at module scope) and `import
map_placement_preview` (which opens the decomp's `terrains.h` at module scope) both fail there.
The first version of this guard imported the preview for one path constant and caught only
`ImportError`; the real failure is `FileNotFoundError`, so it would have turned every PR red while
never once running the new gate. `check_hosted_chapters_declared` states the same rule from the
same scar. So the registrations, the `CHxx_LAYOUT` stems and the preview's own maps root are all
read out of source text, the way `_injection_call_sequence` and `map_donor` already read
`build_campaign` — and a hand-kept table in `check.py` would have been a fourth place to disagree
about the same fact anyway. Matched per injector body rather than across the file, so a
registration cannot be attributed to whatever `def` happened to precede it, and on the LAYOUT
argument rather than the caller's local variable name, because renaming a local is a refactor and
must not empty a gate.

**One silence is kept, and the rest are refused — with the HOSTED list as the floor.** A chapter
whose map is painted but not yet hosted is a legitimate skip: ch06 lived in exactly that state
from #331 until #364, and a guard that reds the build through a normal authoring window gets
bypassed. But that benign skip is also the shape every blind spot degrades into, and review found
two live ones doing exactly that — a registration pattern keyed on the caller's local variable
name (rename it and all seven chapters read as "not hosted yet", zero violations over zero
chapters) and a chapter id that stops lining up (rename ch06's `id:` and its registration drops
out reporting the same false note). So `inject.hosts.hosted_chapters()` — stdlib-only, already
trusted by `check_hosted_chapters_declared` — is the floor: **a hosted chapter owes all three
routes**, so anything that would empty this gate becomes loud instead of quiet. A pattern that
matches nothing at all, an injector whose name cannot be attributed to a chapter, a `CHxx_LAYOUT`
the build does not define, a preview root that cannot be read, and a hosted chapter that lost its
`map:` block are each reported by name. Problems are carried as structured `(kind, text)` pairs
rather than sniffed back out of their own prose, so rewording a message cannot turn a failure into
a pass. The covered set stays assertable on top of all that, because a guard that quietly compares
nothing must not pass for one that compares everything.

Verified with an output diff over `terrain_grid` for all nine chapters: identical, ch03–ch06
included, and ch07/ch08 still report `MapNotCompiled` by name. Nothing about tileset resolution
moved — this change only makes a standing agreement enforceable.
