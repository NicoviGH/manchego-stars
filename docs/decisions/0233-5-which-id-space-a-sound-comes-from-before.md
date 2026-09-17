---
id: 233
title: "5. Which ID SPACE a sound comes from, before which sound."
date: "2026-08-10"
section: "Operational Gotchas (durable)"
issues: []
---

# 5. Which ID SPACE a sound comes from, before which sound.

FE8 has ~340 sound effects and names about sixty of them, so a cry has to be chosen by number.
There are two numberings and they do not agree. `banim_code_sound_*` (banim_code.inc) encodes
`0x850000XX` for BATTLE ANIMATIONS, and XX is not a song id; `SOUN`/`EvtPlaySong` takes a song
id, whose only definition is the ORDER of `sound/song_table.s`. Reading the first as the second
put `se_sys_hp2` (an HP-bar tick), `se_sys_bikkuri_mark1` (the "!" popup) and `dummy_song` in
front of Nicolas as monster roars — four auditions, each a ROM build and a watched run, before
the mismatch surfaced. He described one as *"the silliest little animal noise"*, which was
exactly right: it was a menu blip.

`tools/sfx_preview.py` renders any sound to WAV straight from the decomp -- song table ->
song `.s` -> voicegroup -> `direct_sound_samples/*.bin`, resampled by the interval between the
note the sequence plays and the sample's base key. No ROM, no emulator; `--html` writes a page
with play buttons. Picking ch05's bellow went from a build-and-watch per candidate to one page
and one listen. Noise/square-channel effects (ch05's own rumble is one) have no sample to export
and are reported as skipped rather than approximated.

**6. Nothing in the gate listens.** ch05's bellow shipped through four films with
`MUSCMID(SONG_SILENT)` where a DUCK was meant. That command fades the silent song IN -- it
replaces the BGM permanently -- so the chapter would have run from turn 1 to the boss in silence.
Every scenario passed, `verify_text` passed, every film looked right. It surfaced because Nicolas
asked whether the music comes back. The pair is `MUSI`/`MUNO` (`EvtSetVolumeDown` /
`EvtUnsetVolumeDown`), which ch05's reliquary visits already used. Audio is un-gated by
construction; `PT_SOUND=1` at least makes a run audible on purpose.

The wider rule this instantiates: *the fast-boot idea is not ch05's*. `TESTCH` and `--lord-boot`
are the same move for the test chapter and the lord-select screen. Any feature whose screen is
hard to reach should get one first — save-states do not substitute (they are invalid across code
changes) and `PT_FPS=240` is only a fallback.

_Decided: 2026-08-10 (Nicolas)._

**A green scenario whose inputs are byte-identical does not re-run. That is a build-system
problem, not a policy one.** `make` does not recompile clean objects and `bazel` does not re-run
cached tests; our matrix re-ran everything because the invalidation logic was never written, so
the only two options on the menu were "run all 17" and "a human picks by judgment" — and the
human picking is what kept failing. The scenario COUNT should keep growing (17 → 30 as chapters
land; capping it means deleting proof). What must stop growing is the number that EXECUTE.

**The soundness rule, which is the entire licence to skip.** A verdict is a pure function of the
ROM it boots, the scenario's own Lua, the harness helpers it transitively reaches, its
`matrix.yaml` entry, and the driver around it (`controller.lua`, the dofile'd modules, `run.sh`).
If all of those are byte-identical a PASS cannot become a FAIL. **A FAIL is never cached** — a
flaky red must always re-run; only green is skippable. Anything that cannot be pinned (no decomp
HEAD, a scenario `harness.lua` does not define) returns no key at all, and no key means no cache:
unknown is conservative, never optimistic.

**Do NOT hash `harness.lua` as a whole file.** It is one Lua chunk and nearly every task edits it,
so a whole-file hash invalidates all 17 scenarios on every commit and the cache never hits — the
feature becomes theatre. The granularity is the scenario's transitive helper CLOSURE, which
`check.py`'s blind-press gate already needed and which now lives in `matrix.py`
(`harness_functions`/`reaches`) with the rest of the code that reads harness.lua.

**What makes the closure sound is `harness_shared`, and this is the part that is easy to get
wrong.** Chunking by top-level function charges each chunk to the function that OPENS it, so
top-level data declared between two helpers — `TUNE`, `CALLBACK_NAMES`, the constants — is
glommed onto whichever helper happens to precede it. That data feeds every observation, so a key
built from a closure alone would miss an edit to it and serve a stale PASS. So the file is
PARTITIONED instead: each chunk is a function body (closure-attributable) plus a residue after
its column-0 terminator (shared by everyone), and a chunk with no terminator — a one-line
`local function yield() … end` — is unattributable, which means shared, never dropped. Verified
against the real 8,124-line harness: editing another scenario or rewording a comment holds the
key still; editing the scenario's own body, a helper it reaches, `TUNE`, `CALLBACK_NAMES`,
`controller.lua`, or its manifest entry all move it.

**Five more things belong in the key, and code review found every one of them.** Each is a
way for two genuinely different runs to collide: the ambient `PT_*` knobs `run.sh` passes into
the wrapper (`PT_SEED=7 … fuzz_ch01` would otherwise be served the seed-1 PASS — kept in sync
with `run.sh` by a test, because a hand-kept list rots and rotting *here* means a stale green);
a checkpoint-backed scenario's `ckpt_X` builder, which `run.sh` invokes directly so nothing in
Lua reaches it; a helper passed as a VALUE rather than called, which escapes a call-graph that
only follows `name(` (the closure now follows MENTIONS — median 58 → 66 of 237 functions, and
over-reaching only ever costs a re-run); `record`/`diagnostic` scenarios, which must never be
skipped because they exist to REFILL `/tmp/playtest-<name>` that `make_gif.py` then reads; and
the generated `symbols.lua`/`procscr.lua`, which are excluded because `run.sh` rewrites them
*after* the fingerprint is taken — hashing them cost two re-runs per engine change before the
cache converged, and their content is already implied by the ELF and by `gen_symbols.py`.

**The ROM cache had to cache the ELF too, and finding that is why the verdict cache's key is
trustworthy at all.** The key assumes identical ROM inputs imply identical symbols. That was
false: `restore_cached_rom` copied `fireemblem8.gba` and the build stamp but not
`fireemblem8.elf`, while `gen_symbols.py` reads the ELF to emit the tables the harness
dofiles — and the boot flags MOVE symbols (a ch05boot ELF and a canonical ELF disagree on 58
of the names the harness reads: `gUnitLookup`, `gItemData`, `Menu_OnIdle`, …). The gate spans
four ROM configurations, so a warm run restored three of them against the previous config's
symbol table and read the wrong memory — a live bug since the ROM cache landed, and one that
presents as unexplained flakiness rather than as anything pointing at the cache. The slot is
now `.gba` + `.elf` + `.json`, restored all-or-nothing, because half a slot is worse than
none. 44 MB per configuration, against a debugging session that finds nothing.

**A fresh RED always evicts a stored green.** Same key, different verdict, means the stored
green is now a lie, and leaving it makes the next run report a scenario green while it is red
right now. `run.sh` evicts too, because a scenario run DIRECTLY — which is how debugging
happens — never passes through the matrix. `MX_NO_CACHE=1` still evicts on a failure: bypassing
the cache must not become a way to fail a scenario and leave the lie in place.

**A cached green must never read as a fresh one**, so the table carries a `source` column
(`ran`/`cached`), the summary says `N ran, M cached`, and the run's log and screenshots are kept
beside the verdict — `/tmp/playtest-<name>` will have been overwritten by whatever ran last, and
a cached green nobody can look at is a green nobody can audit. `--no-verdict-cache` / `MX_NO_CACHE=1`
opts out. A group with nothing left to run is never BUILT, which is where the biggest saving is: a
doc-only or harness-only change costs no `make` and no emulator at all.

**Phase 2: the build attributes its own writes, and a ch05 edit stops re-running the
prologue.** Measured on the real gate, for a one-line ch05 enemy-level change: **6 run, 14
cached of 20**. The same edit under phase 1 alone re-ran all twenty, because
`rom_input_hash` cannot tell a ch05 edit from any other. `tools/build_scopes.py` watches the
decomp while `build_campaign.py` runs and records, per injection step, the files that step
actually wrote plus a digest of their contents; `matrix.py` keys each scenario on just the
scopes it depends on.

**Derived, never declared.** A step's scope is read off its own function name
(`inject_ch05` → `chapter:ch05`), and its file list is what the filesystem says it wrote —
not a table anybody maintains. Hand-kept impact maps rot silently and let real regressions
through, which is the exact failure this feature exists to prevent.

Three rules make it sound, and all three are the conservative direction:

- **A file written by more than one step belongs to EVERY step that wrote it.** This is the
  subtle killer. Nine shared tables (`chapter_settings.json`, `data_8B363C.s`,
  `src/events_udefs.c`, …) are written by both the global passes and ch05. Blaming the last
  writer would charge them to ch05 alone, and a portrait edit would then move only ch05's
  digest while every global scenario was served a stale PASS.
- **Unattributable means `global`.** Writes between steps, writes outside the walked roots
  (reconciled from git's own view of the decomp at the end), and any step whose name does
  not identify exactly one chapter — `chain_ch04_to_ch05` names two — all land in `global`,
  which every scenario depends on.
- **A scenario's chapter dependency comes from where it ACTUALLY WENT, not from a field.**
  The first cut read `matrix.yaml`'s `host_chapter` as the last chapter played. It is not —
  it is the harness's `PT_HOST_CHAPTER` hint and defaults to `1`, so `ch01win` boots at the
  prologue, plays into ch01, and declares `host_chapter: 1`. Reading it as an upper bound
  let ch01's map change without re-running the scenario that plays it: a stale PASS, caught
  in review. Every controller observation carries `world.chapter`, so a scenario's own log
  records its traversal; `matrix.py` stores that beside the verdict and scopes the next key
  to exactly those chapters. Cold (nothing observed yet) it depends on every chapter from
  its boot point FORWARD and converges after one pass. **Why trusting the observation is
  safe:** for a change to send a scenario somewhere new, that change must be in a scope it
  already depends on — a chapter it visits, or `global`, where the chapter-CHAINING steps
  live because their names name two chapters — so it re-runs and re-observes first. Slot
  numbers come from `tools/inject/hosts.py`, the file that ENROLS a chapter, so adding ch06
  is one line there and nothing in the matrix.

- **The scoped key still pins the ROM inputs no scope can see.** Everything else reaches the
  ROM as a file some injector WRITES, which the manifest observes — but the decomp's own
  sources are COMPILED (we patch only a handful), so a submodule bump touching an engine
  file no injector writes rebuilds the ROM and moves not one scope digest. `engine/` and the
  `Makefile` are the same shape. Those stay in the key as a narrow `engine_input_hash`;
  campaign data, which is what actually changes, stays scope-attributed.

**The manifest only exists AFTER the build**, which changes the shape of a run: a
configuration whose ROM inputs moved cannot be keyed on scopes until it is built, so
`execute()` asks the cache again *after* each build. Building can now REMOVE work rather
than merely precede it. Phase 1's "a fully cached group is never built" path still applies
whenever `rom_input_hash` hits, which is what keeps a doc-only change free. For the same
reason `--dry-run` says so out loud when a configuration changed: its listing is the coarse
answer, and most of those scenarios turn out cached once the build reports what it wrote.
The manifest travels in the ROM cache slot alongside the ELF, and for the same reason.

**Measured, and then re-measured properly — the first number was wrong.** An early pass
reported a ch05 enemy-level edit at 6 run / 14 cached. That measurement applied ONE ROM
configuration's manifest to every scenario; each configuration has its own, and they must be
built in the matrix's own alternating order. Driven through the real build by the
invalidation probe (`probe_invalidation.py`), the honest figure is **18 run, 2 cached** — chapter isolation
is far weaker than that first number claimed, because five whole-campaign tables are
rewritten by every chapter injector (see the line-level attribution note below). Recorded
with the error intact because a wrong measurement in an ADR is worse than no measurement,
and because the mistake — comparing keys instead of running the thing — is the reusable
lesson.

**Verified deterministic**: two consecutive identical builds produce byte-identical
manifests across all seven scopes. That matters because the attribution detects writes by
mtime, and a path set that churned would move a digest with no content behind it. A
config SWITCH does change which files get rewritten — that is real, and it is why the
measurement above compares two builds of the same configuration.

**What phase 2 does NOT buy.** Attribution is per FILE, so an edit to a chapter early in
the shared tables still moves the later chapters' digests: a ch02 enemy level moves ch02,
ch03, ch04 and ch05 (12 run, 8 cached) because every later chapter injector rewrites a
shared table that now carries ch02's bytes. The direction #255 asked for — a LATE chapter
edit not re-running everything before it — is the one that works, and it is the common case
while the campaign is built forward. Sub-file attribution would fix the rest and is a much
bigger lift with much more to get wrong; do not reach for it without a measurement saying
it pays.
_Decided: 2026-08-12 (#255 phase 2)._
