# Design Decisions — Manchego Stars

> These decisions are **settled**. Do not re-open them without a strong reason.
>
> **This file is GENERATED.** Each decision is one file under `docs/decisions/`;
> this is the index. Add or edit the ADR, then regenerate:
> `python3 tools/gen_decisions_index.py`. `tools/check.py` fails if it is stale.

288 decisions. Read this index, then open the two or three you need — the whole
set is ~197,000 tokens and no session has ever needed all of it at once.

**Contents:** [Engine & Tech Stack](#engine-tech-stack) · [Documentation Model](#documentation-model) · [Working Conventions (Definition of Done)](#working-conventions-definition-of-done) · [Combat System](#combat-system) · [Weapon & Magic Systems](#weapon-magic-systems) · [Economy](#economy) · [Distribution & Scope](#distribution-scope) · [Art & Audio](#art-audio) · [Class Mapping & Promotions](#class-mapping-promotions) · [Story & Dialogue](#story-dialogue) · [Operational Gotchas (durable)](#operational-gotchas-durable) · [Open Questions (not yet decided)](#open-questions-not-yet-decided)

---

## Engine & Tech Stack

| | decision | date | issues |
|---|---|---|---|
| `0001` | [Base game: FE8 Sacred Stones (US) decomp (fireemblem8u)](decisions/0001-base-game-fe8-sacred-stones-decomp.md) | May 2026 | — |
| `0002` | [Compiler: agbcc (GCC 2.95.1)](decisions/0002-compiler-agbcc.md) | May 2026 | — |
| `0003` | [Engine/content split: engine in C (reusable), campaign data in YAML (swappable)](decisions/0003-engine-content-split-engine-in-c-campaign-data-in.md) | May 2026 | — |
| `0004` | [Tooling language: Python everywhere. NOT TypeScript.](decisions/0004-tooling-language-python-everywhere-not-typescript.md) | 2026-06-04 | — |
| `0005` | [Content injection is decomp-native — edit the decomp's own source, NOT Event Assembler.](decisions/0005-content-injection-is-decomp-native-edit-the-decomp-s.md) | 2026-06-04 | — |
| `0006` | [Injection is idempotent: a byte-identical re-emit rewinds the file's mtime, so make skips it.](decisions/0006-injection-is-idempotent-a-byte-identical-re-emit-rewinds.md) | 2026-07-30 | #24 |
| `0007` | [Text injection has a terminator-parity gotcha (the reset's "Huffman corruption").](decisions/0007-text-injection-has-a-terminator-parity-gotcha.md) | 2026-06-04 | #46 |
| `0008` | [Card/name text from YAML must be ASCII-folded before FE8 encoding — name_message_body does it centrally.](decisions/0008-card-name-text-from-yaml-must-be-ascii-folded.md) | 2026-06-25 | — |
| `0009` | [Test-chapter spawn = vanilla Ch1 map stripped to a sandbox (not a hand-authored chapter).](decisions/0009-test-chapter-spawn-vanilla-ch1-map-stripped-to-a.md) | 2026-06-04 | — |
| `0010` | [Non-LORD-class lords need engine guards (the prologue "garbage-band" crash).](decisions/0010-non-lord-class-lords-need-engine-guards.md) | 2026-06-09 | — |
| `0011` | [Chapter injection rides shared module-level helpers, not per-chapter nested copies (#104/#105).](decisions/0011-chapter-injection-rides-shared-module-level-helpers-not-per.md) | 2026-07-02 | #104 #105 |
| `0012` | [Chapter deployment schema: ONE shape, gated (#107).](decisions/0012-chapter-deployment-schema-one-shape-gated.md) | 2026-07-02 | #107 |
| `0013` | [A retile inherits vanilla's terrain; the tileset's terrain table is ours to author (#25).](decisions/0013-a-retile-inherits-vanilla-s-terrain-the-tileset-s.md) | 2026-08-07 | #25 |
| `0014` | [A vanilla layout's tileset is resolved, never inferred from asset-table position (#25).](decisions/0014-a-vanilla-layout-s-tileset-is-resolved-never-inferred.md) | 2026-08-07 | #25 |
| `0015` | [A tileset's unused slots are declared by TERRAIN_NONE, not by a filler colour (#25).](decisions/0015-a-tileset-s-unused-slots-are-declared-by-terrainnone.md) | 2026-08-07 | #25 |
| `0016` | [Tileset vendoring is a one-command import; Ch3's cave tileset is cave-interior (#40).](decisions/0016-tileset-vendoring-is-a-one-command-import-ch3-s.md) | 2026-07-02 | #40 |

---

## Documentation Model

| | decision | date | issues |
|---|---|---|---|
| `0017` | [Three tiers; a per-chapter fact lives in exactly one place (the YAML)](decisions/0017-three-tiers-a-per-chapter-fact-lives-in-exactly.md) | 2026-05-31 | — |
| `0018` | [Chapter cadence taxonomy (the cadence: field)](decisions/0018-chapter-cadence-taxonomy.md) | 2026-05-31 | — |
| `0019` | [Playtest test-chapter build (make TESTCH=1)](decisions/0019-playtest-test-chapter-build.md) | 2026-06-23 | — |
| `0284` | [A decision is a FILE, and decisions.md is the index over them](decisions/0284-a-decision-is-a-file-and-decisions-md-is.md) | 2026-09-17 | #384 |

---

## Working Conventions (Definition of Done)

**Why this section exists:** the project drifted because the plan was written up front,
then implementation pivoted (Python not TS, decomp-native not Event Assembler, stock
classes not homebrew) and the canonical docs/issues were never reconciled. The same
fact lived in CLAUDE.md, PRD.md, README, rules-mapping, decisions.md, and GitHub, so
no update ever propagated. These conventions keep a single source of truth.

**Single source of truth — link, don't restate.** Each fact lives in exactly one place:
- *Settled decisions & rationale* → this file (`decisions.md`).
- *Per-chapter facts* → chapter YAML → generated `CHAPTERS.md`. *Unit facts* → unit YAML → `CLASSES.md`.
- *Work backlog* → GitHub issues (milestones M0–M4).

**HANDOFF.md is authored on `main` only (2026-07-30).** Gated by
`check.py check_handoff_only_on_main`; a branch may leave it untouched or sync it to main's
tip, but may not author its own. Refresh it on main *after* a merge, never on the branch.

*Why it needed a gate rather than a habit.* HANDOFF describes **global** live state, but it
is a tracked repo-root file — so every branch and worktree gets a private copy that quietly
stops describing the project and starts describing *the project as that branch last saw it*.
Merge the branch and the stale copy overwrites main's. With one short-lived branch at a time
this never surfaced: every HANDOFF commit before 2026-07-21 landed on main. Two long-lived
parallel branches (ch04 and ch05, nine days) made divergence certain, and the last merge won
regardless of which copy was newer. The ch05 merge put ch04 back to a "WIP checkpoint" four
committed stages out of date; it was only caught because `git pull` refused to clobber an
unrelated local edit.

This is the same root cause as *"feature-flow only works if each feature LANDS before the
next starts"* (below), showing up in a file instead of a rebase — and it had **already been
caught once**, on 2026-07-21, with the mitigation "keep the copies in sync". That is a
memory, not a control, and it failed nine days later. Hence a check: the guard passes the
two states that are actually safe (untouched — git's 3-way merge keeps main's version; or
byte-identical to main's tip, the ideal state for a worktree people read HANDOFF in) and
fails only a branch carrying live state it does not own. It reports *skipped* rather than
*violated* when it cannot see a base, because a guard that cries wolf gets bypassed.
- *Live state* → the single **`HANDOFF.md`** (one trunk, feature-flow — the per-track handoffs were retired 2026-06-24); `/handoff` refreshes it in place. Keep it lean: live Now/Next + gotchas + pointers, no per-session history (that's `git log` + closed issues). *Vision/pitch* → `PRD.md` (no specifics that live elsewhere).
- `CLAUDE.md` is lean **operating instructions + pointers**, not a fact store (a bloated CLAUDE.md gets ignored). If a fact belongs in two docs, one of them should link instead.

**Record decisions when made.** Any change that alters architecture, scope, tooling, or a
settled rule gets a dated entry here in the same session — ADR-style, while context is
fresh. Don't leave it in chat or agent memory only.

| | decision | date | issues |
|---|---|---|---|
| `0020` | [Definition of Done for a change:](decisions/0020-definition-of-done-for-a-change.md) | 2026-06-04 | — |
| `0021` | [Process: the superpowers workflow layers ON TOP of this knowledge architecture (not a replacement).](decisions/0021-process-the-superpowers-workflow-layers-on-top-of-this.md) | 2026-06-19 | — |
| `0022` | [Delivery model: chapters ship as vertical slices through a CD pipeline.](decisions/0022-delivery-model-chapters-ship-as-vertical-slices-through-a.md) | 2026-06-19 | — |
| `0023` | [Parallel work model: per-instance git worktrees for build isolation, not branch-per-track.](decisions/0023-parallel-work-model-per-instance-git-worktrees-for-build.md) | 2026-06-19 | — |
| `0024` | [Engine/content file seam: the 5 campaign-agnostic engine hooks live in tools/inject/, not build_campaign.py.](decisions/0024-engine-content-file-seam-the-5-campaign-agnostic-engine.md) | 2026-06-19 | — |
| `0025` | [/code-review is the review step, and the author never reviews their own PR](decisions/0025-code-review-is-the-review-step-and-the-author.md) | 2026-09-02 | — |
| `0026` | [Boot decision localized; bows need a min-range in playtest targeting (the first feature-flow feature).](decisions/0026-boot-decision-localized-bows-need-a-min-range-in.md) | 2026-06-24 | — |
| `0027` | [Ch2 load-test: automate the STRUCTURAL half in the harness; the PACING half stays human.](decisions/0027-ch2-load-test-automate-the-structural-half-in-the.md) | 2026-06-25 | — |
| `0028` | [Clear-bot pathing: BFS march + multi-range + stall watchdog landed; #60 still open on boss-breach.](decisions/0028-clear-bot-pathing-bfs-march-multi-range-stall-watchdog.md) | 2026-06-25 | #60 |
| `0029` | [(a) tools/check.py runs in CI's checks job, which installs pyyaml and nothing else.](decisions/0029-tools-check-py-runs-in-ci-s-checks-job.md) | 2026-08-06 | #237 #239 #240 #241 |
| `0285` | [Context is the budget, and the expensive thing is what enters it early](decisions/0285-context-is-the-budget-and-it-is-quadratic.md) | 2026-09-17 | #386 |
| `0288` | [Review the WRITTEN surface, and price effort per PR](decisions/0288-review-the-written-surface-not-the-generated-bulk.md) | 2026-09-17 | #391 |

---

## Combat System

> **2026-05-28 — Combat resolution reverted to vanilla FE.** The earlier "Hybrid
> d20/FE" decision (May 2026) is **superseded**. For playability the combat *rules*
> stay vanilla FE8 (hit%/avoid/might, FE crit, FE doubling); **D&D is flavor only**.
> The d20 survives at most as a **cosmetic flourish on a crit**, never as the
> resolution system. **AC, saving throws, and advantage/disadvantage are dropped**
> as mechanics (see below). Rationale (Nicolas): "the rules need to stay FE or the
> game won't play the same" — the FE-strictness spine. The four implementation
> sub-questions were ratified by Nicolas on 2026-05-28: d20 = cosmetic-crit-only,
> saves dropped, AC dropped, advantage dropped.

| | decision | date | issues |
|---|---|---|---|
| `0030` | [Combat resolution: vanilla FE8 hit / avoid / might](decisions/0030-combat-resolution-vanilla-fe8-hit-avoid-might.md) | 2026-05-28 | — |
| `0031` | [d20: cosmetic crit flourish only](decisions/0031-d20-cosmetic-crit-flourish-only.md) | 2026-05-28 | — |
| `0032` | [The d20 flourish SHIPS (#11): a gold nat-20 pops at the crit flash's teardown.](decisions/0032-the-d20-flourish-ships-a-gold-nat-20-pops.md) | 2026-07-02 | #11 |
| `0033` | [AC (Armor Class): dropped as a mechanic](decisions/0033-ac-dropped-as-a-mechanic.md) | 2026-05-28 | — |
| `0034` | [Saving throws: dropped → vanilla FE magic](decisions/0034-saving-throws-dropped-vanilla-fe-magic.md) | 2026-05-28 | — |
| `0035` | [Advantage / disadvantage: dropped](decisions/0035-advantage-disadvantage-dropped.md) | 2026-05-28 | — |
| `0036` | [Damage: vanilla FE armor-subtraction model (nothing layered under it)](decisions/0036-damage-vanilla-fe-armor-subtraction-model.md) | 2026-05-28 | — |
| `0037` | [Critical hits: vanilla FE (skill-based rate, ×3 damage)](decisions/0037-critical-hits-vanilla-fe.md) | 2026-05-28 | — |
| `0038` | [Doubling: vanilla FE (unchanged)](decisions/0038-doubling-vanilla-fe.md) | May 2026 | — |
| `0039` | [Damage-type resistance/vulnerability/immunity: DROPPED as a mechanic](decisions/0039-damage-type-resistance-vulnerability-immunity-dropped-as-a-mechanic.md) | 2026-05-28 | — |
| `0040` | [Hit-rate tuning: vanilla FE, no special floor needed](decisions/0040-hit-rate-tuning-vanilla-fe-no-special-floor-needed.md) | 2026-05-28 | — |
| `0041` | [Field parity: our chapter N fields what vanilla FE8 chapter N fields — both sides.](decisions/0041-field-parity-our-chapter-n-fields-what-vanilla-fe8.md) | 2026-06-10 | — |
| `0042` | [Party-side parity: donor personal lines + a per-lord survivability floor — never enemy or stat inflation.](decisions/0042-party-side-parity-donor-personal-lines-a-per-lord.md) | 2026-06-18 | — |
| `0043` | [Difficulty is checked in fidelity tiers, and the roster↔map loop is bidirectional — a chapter is not...](decisions/0043-difficulty-is-checked-in-fidelity-tiers-and-the-rostermap.md) | 2026-07-17 | — |
| `0044` | [Match the twin's CLASS MIX, not just its totals — the weapon triangle is invisible to the per-slot averages.](decisions/0044-match-the-twin-s-class-mix-not-just-its.md) | 2026-07-23 | — |
| `0045` | [A boss is class base PLUS a personal stat line — that, not the class, is why FE8 bosses are walls.](decisions/0045-a-boss-is-class-base-plus-a-personal-stat.md) | 2026-07-23 | — |
| `0046` | [Corollary — our undead reskins read GLASSY against the parity yardstick, so match clear-load with high-Spd beasts +...](decisions/0046-corollary-our-undead-reskins-read-glassy-against-the-parity.md) | 2026-07-22 | #25 |
| `0047` | [Refinement (2026-07-23) — the RIGHT fix for the glassy problem is a SKIN divorce, not a composition fight: put undead...](decisions/0047-refinement-the-right-fix-for-the-glassy-problem-is.md) | 2026-07-23 | #25 |
| `0048` | [Each recruit's JOIN uses vanilla FE8 primitives, wired per its own method — do NOT generalize:](decisions/0048-each-recruit-s-join-uses-vanilla-fe8-primitives-wired.md) | 2026-07-08 | #23 |
| `0049` | [ch04 and ch05 each map 1:1 to their numeric FE8 twin (map AND parity); theme is layered, not borrowed.](decisions/0049-ch04-and-ch05-each-map-1-1-to-their.md) | 2026-07-15 | #24 #25 |
| `0050` | [A map change picks its tiles by TERRAIN, and a declared terrain is not a painted tile. ch04's Iron Axe exists because...](decisions/0050-a-map-change-picks-its-tiles-by-terrain-and.md) | 2026-08-02 | #205 #214 |
| `0051` | [The felled snag keeps vanilla's full three-tile silhouette, winterized in snowy-bern (#24).](decisions/0051-the-felled-snag-keeps-vanilla-s-full-three-tile.md) | 2026-08-10 | #24 |
| `0052` | [Ch3 "The Termalaine Mine" — four sanctioned deviations from strict per-chapter parity.](decisions/0052-ch3-the-termalaine-mine-four-sanctioned-deviations-from-strict.md) | 2026-06-26 | — |
| `0053` | [Ch3 layout = vanilla Borgo geometry repainted, NOT a custom Gem-Mine blockout.](decisions/0053-ch3-layout-vanilla-borgo-geometry-repainted-not-a-custom.md) | 2026-07-04 | #23 |
| `0054` | [Ch3 chains off ch02's ending (MNC2(0x4)); the party persists, no armed seed.](decisions/0054-ch3-chains-off-ch02-s-ending-the-party-persists.md) | 2026-07-11 | #23 |
| `0055` | [Ch3 chests + doors ride ONE per-chapter MapChange array; a door opens to the tile below it.](decisions/0055-ch3-chests-doors-ride-one-per-chapter-mapchange-array.md) | 2026-07-11 | #23 |
| `0056` | [A campaign item icon can use a colour pal 0 lacks, via an additive third item palette.](decisions/0056-a-campaign-item-icon-can-use-a-colour-pal.md) | 2026-06-20 | — |
| `0057` | [Lord floor, runtime mechanism (#45 3b/3c): a build-baked table applied once at the first player phase.](decisions/0057-lord-floor-runtime-mechanism-a-build-baked-table-applied.md) | 2026-06-19 | #45 |
| `0058` | [Per-chapter parity beyond Ch1 = enemy-pressure vs a parity_reference vanilla chapter.](decisions/0058-per-chapter-parity-beyond-ch1-enemy-pressure-vs-a.md) | 2026-06-19 | — |
| `0059` | [How the deploy cap + prep screen are actually wired (the [decomp] mechanism).](decisions/0059-how-the-deploy-cap-prep-screen-are-actually-wired.md) | 2026-06-10 | — |
| `0060` | [No world map ⇒ GetBattleMapKind() falls back to STORY (engine hardening).](decisions/0060-no-world-map-getbattlemapkind-falls-back-to-story.md) | 2026-06-10 | — |
| `0061` | [Game over = the lord-analog only; story-required allies "retreat" instead.](decisions/0061-game-over-the-lord-analog-only-story-required-allies.md) | 2026-06-09 | — |
| `0062` | [Player-chosen lord (#42): route-split menu between the Northlook muster and preps.](decisions/0062-player-chosen-lord-route-split-menu-between-the-northlook.md) | 2026-06-10 | #42 |
| `0063` | [Lord-select UI (#46): the existing #42 menu COMPOSED with stock components, not a bespoke screen.](decisions/0063-lord-select-ui-the-existing-42-menu-composed-with.md) | 2026-06-24 | #42 #46 |
| `0064` | [Chapter outcomes ride gDefeatTalkList; entries go at the HEAD of the table.](decisions/0064-chapter-outcomes-ride-gdefeattalklist-entries-go-at-the-head.md) | 2026-06-09 | — |
| `0065` | [Automated playtests: mGBA Lua scripting drives deterministic win/lose checks.](decisions/0065-automated-playtests-mgba-lua-scripting-drives-deterministic-win-lose.md) | 2026-06-09 | — |
| `0066` | [Playtest platform first brick = a generic SMOKE LIVENESS net, not more hand-scripted scenarios (#49).](decisions/0066-playtest-platform-first-brick-a-generic-smoke-liveness-net.md) | 2026-06-19 | #49 |
| `0067` | [Playtest platform brick 2 = a greedy CLEAR-BOT that proves completability with real combat (#60).](decisions/0067-playtest-platform-brick-2-a-greedy-clear-bot-that.md) | 2026-06-19 | #60 |
| `0068` | [Playtest platform brick 3 = a SEEDED random-input fuzzer ("smart monkey") over the same I/O layer (#49).](decisions/0068-playtest-platform-brick-3-a-seeded-random-input-fuzzer.md) | 2026-06-19 | #49 |
| `0069` | [Playtest platform brick 4 = an LLM-player as a SOAK/BALANCE tool, built policy-and-transport-first (#63).](decisions/0069-playtest-platform-brick-4-an-llm-player-as-a.md) | 2026-06-20 | #63 |
| `0070` | [#63 M2 = the sidecar handshake ships PROVIDER-AGNOSTIC — a free local model is one env var away.](decisions/0070-63-m2-the-sidecar-handshake-ships-provider-agnostic-a.md) | 2026-07-02 | #63 |
| `0071` | [Playtest controller contract = observe, classify, enumerate, guard one input, verify, trace (#220).](decisions/0071-playtest-controller-contract-observe-classify-enumerate-guard-one-input.md) | 2026-08-03 | #63 #220 |
| `0072` | [What the contract costs, measured, so it is not re-litigated (Nicolas's standing question).](decisions/0072-what-the-contract-costs-measured-so-it-is-not.md) | 2026-08-06 | #220 #238 |
| `0073` | [Recording a cutscene as a review GIF (the standard way to show Nicolas motion).](decisions/0073-recording-a-cutscene-as-a-review-gif.md) | 2026-06-17 | #21 #219 #220 |
| `0074` | [One manifest owns "what a playtest scenario needs"; run.sh and the matrix runner both read it (#231).](decisions/0074-one-manifest-owns-what-a-playtest-scenario-needs-run.md) | 2026-08-05 | #222 #231 |
| `0075` | [Chapter title cards are IMAGES, recomposed from vanilla glyphs.](decisions/0075-chapter-title-cards-are-images-recomposed-from-vanilla-glyphs.md) | 2026-06-09 | — |
| `0076` | [A spawn-node story chapter needs the no-world-map title fallback, not just a recomposed card.](decisions/0076-a-spawn-node-story-chapter-needs-the-no-world.md) | 2026-07-11 | — |
| `0077` | [Every decomp file an engine hook patches must be registered in PATCHED_DECOMP_FILES.](decisions/0077-every-decomp-file-an-engine-hook-patches-must-be.md) | 2026-07-11 | — |
| `0078` | [Seize-map legibility: the seize tile must read as a seize point and the boss sits on it — a level-design checkpoint](decisions/0078-seize-map-legibility-the-seize-tile-must-read-as.md) | 2026-06-19 | #56 #57 |
| `0079` | [Title banner theme: "glacial blue", a pure PALETTE recolor (no pixel edits).](decisions/0079-title-banner-theme-glacial-blue-a-pure-palette-recolor.md) | 2026-06-09 | — |

---

## Weapon & Magic Systems

| | decision | date | issues |
|---|---|---|---|
| `0080` | [Weapon triangle: vanilla FE (Sword > Axe > Lance); damage-type names are flavor](decisions/0080-weapon-triangle-vanilla-fe-damage-type-names-are-flavor.md) | 2026-05-29 | — |
| `0081` | [Magic triangle: vanilla FE (Anima > Light > Dark)](decisions/0081-magic-triangle-vanilla-fe.md) | 2026-05-29 | — |
| `0082` | [Damage-type / elemental flavor: dropped as a game feature; deferred to battle-anim art](decisions/0082-damage-type-elemental-flavor-dropped-as-a-game-feature.md) | 2026-06-04 | — |
| `0083` | [Spell economy: finite-use tomes that deplete and are restocked with gold (decision B)](decisions/0083-spell-economy-finite-use-tomes-that-deplete-and-are.md) | 2026-05-29 | — |
| `0084` | [Decision B needs (almost) no code — vanilla FE8 IS the spell economy (#9 delta audit).](decisions/0084-decision-b-needs-no-code-vanilla-fe8-is-the.md) | 2026-07-02 | #9 |
| `0085` | [Iconic matchups are OUT — the vanilla principle covers item DATA, not just mechanisms (#8 reverted).](decisions/0085-iconic-matchups-are-out-the-vanilla-principle-covers-item.md) | 2026-07-02 | #8 |
| `0086` | [Comments are testimony, code is evidence — the comment-drift guard (post-mortem of the "zeroed growths" incident).](decisions/0086-comments-are-testimony-code-is-evidence-the-comment-drift.md) | 2026-07-02 | — |
| `0087` | [The difficulty curve projects planned chapters forward from their vanilla reference (#123).](decisions/0087-the-difficulty-curve-projects-planned-chapters-forward-from-their.md) | 2026-07-02 | #123 |
| `0088` | [MVP weapons = stock FE weapons (no custom Might); personal weapons are post-MVP](decisions/0088-mvp-weapons-stock-fe-weapons-personal-weapons-are-post.md) | 2026-05-30 | — |

---

## Economy

| | decision | date | issues |
|---|---|---|---|
| `0089` | [Gold Pieces (GP) replace FE gold (same mechanic, D&D label)](decisions/0089-gold-pieces-replace-fe-gold.md) | May 2026 | — |
| `0090` | [~~No arena~~ — SUPERSEDED 2026-07-29. The arena is KEPT, and it keeps its name.](decisions/0090-no-arena-superseded-2026-07-29-the-arena-is.md) | 2026-07-29 | — |
| `0091` | [Arena presentation: winter is campaign-wide; attendants remain chapter-owned.](decisions/0091-arena-presentation-winter-is-campaign-wide-attendants-remain-chapter.md) | 2026-08-11 | #265 |
| `0092` | [Gold availability follows vanilla FE8 — no per-chapter clear bonus](decisions/0092-gold-availability-follows-vanilla-fe8-no-per-chapter-clear.md) | 2026-06-17 | — |

---

## Distribution & Scope

| | decision | date | issues |
|---|---|---|---|
| `0093` | [A verdict scenario needs no pixels, so it runs HEADLESS](decisions/0093-a-verdict-scenario-needs-no-pixels-so-it-runs.md) | 2026-08-22 | #302 #308 |
| `0094` | [Headless flipped the parallel-dispatch default — 3.2x](decisions/0094-headless-flipped-the-parallel-dispatch-default-3-2x.md) | 2026-08-23 | #302 #310 |
| `0095` | [The gate is the spine plus the last two chapters; depth lives in the chapter suite](decisions/0095-the-gate-is-the-spine-plus-the-last-two.md) | 2026-08-23 | #302 |
| `0096` | [A blanket pkill is a serial-world habit, and parallel dispatch turned it into a saboteur](decisions/0096-a-blanket-pkill-is-a-serial-world-habit-and.md) | 2026-08-23 | #310 |
| `0097` | [A build is 50 seconds, and 26 of them were the same battle anims every time](decisions/0097-a-build-is-50-seconds-and-26-of-them.md) | 2026-08-23 | #302 #309 |
| `0098` | [A NAMED raw pid must be exclusive; a GENERIC one need not be](decisions/0098-a-named-raw-pid-must-be-exclusive-a-generic.md) | 2026-09-04 | #26 #364 |
| `0099` | [The parity model prices the YAML; only the EMITTED ROWS are the ROM](decisions/0099-the-parity-model-prices-the-yaml-only-the-emitted.md) | 2026-09-04 | #26 #364 |
| `0100` | [A load-test that reads the roster before PREP settles is a diagnostic that LIES](decisions/0100-a-load-test-that-reads-the-roster-before-prep.md) | 2026-09-04 | #26 |
| `0101` | [The asset table is addressed by a u8, so ch06 RECLAIMS a slot rather than appending](decisions/0101-the-asset-table-is-addressed-by-a-u8-so.md) | 2026-09-03 | #26 |
| `0102` | [A hosted chapter inherits its host slot's FOG, and nothing guards that](decisions/0102-a-hosted-chapter-inherits-its-host-slot-s-fog.md) | 2026-09-03 | #26 |
| `0103` | [A chapter declares its traps; .traps is the fourth inherited field](decisions/0103-a-chapter-declares-its-traps-traps-is-the-fourth.md) | 2026-08-22 | #302 |
| `0104` | [The arena tutorial is safety text, so it plays in every mode](decisions/0104-the-arena-tutorial-is-safety-text-so-it-plays.md) | 2026-08-22 | #303 |
| `0105` | [Ravisin was holding a bar that had moved](decisions/0105-ravisin-was-holding-a-bar-that-had-moved.md) | 2026-08-22 | #303 |
| `0106` | [The parity model must honour baseLevel, or it grades bosses the ROM never touches](decisions/0106-the-parity-model-must-honour-baselevel-or-it-grades.md) | 2026-08-22 | #303 |
| `0107` | [A raw-pid boss must declare baseLevel, or difficulty wipes its stat line](decisions/0107-a-raw-pid-boss-must-declare-baselevel-or-difficulty.md) | 2026-08-22 | #303 |
| `0108` | [Measured in-engine, before the fix (ch05, three runs):](decisions/0108-measured-in-engine-before-the-fix.md) | 2026-08-22 | #303 |
| `0109` | [Vanilla ships three difficulty modes, so we ship three](decisions/0109-vanilla-ships-three-difficulty-modes-so-we-ship-three.md) | 2026-08-22 | #303 |
| `0110` | [What the ruling makes wrong, and therefore what it commits us to:](decisions/0110-what-the-ruling-makes-wrong-and-therefore-what-it.md) | 2026-08-22 | #302 #303 |
| `0111` | [Distribution: private, pre-patched .gba shared with the 7 players (no public ROM or patch)](decisions/0111-distribution-private-pre-patched-gba-shared-with-the-7.md) | 2026-06-20 | #59 |
| `0112` | [Permadeath: player choice via FE8's Casual/Classic toggle](decisions/0112-permadeath-player-choice-via-fe8-s-casual-classic-toggle.md) | May 2026 | — |
| `0113` | [MVP scope: 8 chapters (Prologue–Ch 8), ending at the Eastway scripted defeat → Revel's End cliffhanger](decisions/0113-mvp-scope-8-chapters-ending-at-the-eastway-scripted.md) | 2026-05-31 | — |
| `0114` | [Unbuilt chapter boundaries land on a reusable dev placeholder, not a vanilla map](decisions/0114-unbuilt-chapter-boundaries-land-on-a-reusable-dev-placeholder.md) | 2026-06-17 | — |
| `0115` | [Release versioning: v0.<chapters-playable>.<patch>, staying 0.x until the full MVP ships as v1.0](decisions/0115-release-versioning-v0-chapters-playable-patch-staying-0-x.md) | 2026-06-19 | — |
| `0116` | [Playtest carryover: testers carry their own .sav across builds; a per-release starter save is the fallback](decisions/0116-playtest-carryover-testers-carry-their-own-sav-across-builds.md) | 2026-06-20 | #59 |

---

## Art & Audio

| | decision | date | issues |
|---|---|---|---|
| `0117` | [Battle-anim ground platforms: vendored snow/ice (FE-Repo, not stone)](decisions/0117-battle-anim-ground-platforms-vendored-snow-ice.md) | 2026-06-23 | — |
| `0118` | [Faked battle anims: per-CHARACTER (_u25), not per-class clones (#65 M-A → M-B)](decisions/0118-faked-battle-anims-per-character-not-per-class-clones.md) | 2026-06-26 | #65 |
| `0119` | [Faked anim fidelity pass: archer-palette cyan, melee lunge, record-capture (#65 M-B)](decisions/0119-faked-anim-fidelity-pass-archer-palette-cyan-melee-lunge.md) | 2026-06-26 | #65 |
| `0120` | [Faked battle-animation review loop: donor visuals, game-valid previews, and archive cost (#65)](decisions/0120-faked-battle-animation-review-loop-donor-visuals-game-valid.md) | 2026-07-14 | #65 #163 |
| `0121` | [Imported enemy battle anims: transcribe a REAL community animation, bind per-CLASS (#90)](decisions/0121-imported-enemy-battle-anims-transcribe-a-real-community-animation.md) | 2026-07-17 | #90 |
| `0122` | [Process cost worth remembering (see decisions Operational Gotchas + [[feedback_check_precedent_before_inventing]]):](decisions/0122-process-cost-worth-remembering.md) | 2026-07-18 | #190 |
| `0123` | [Three pipeline rules the same unit earned:](decisions/0123-three-pipeline-rules-the-same-unit-earned.md) | 2026-08-03 | #206 |
| `0124` | [Two process rules the same session earned, because both cost a rebuild:](decisions/0124-two-process-rules-the-same-session-earned-because-both.md) | 2026-08-02 | #206 |
| `0125` | [Every ATTACKING banim mode must ARM the HP depletion — the unit it starves is the OPPONENT (#24)](decisions/0125-every-attacking-banim-mode-must-arm-the-hp-depletion.md) | 2026-07-31 | #24 |
| `0126` | [Character-scoped spell colours are campaign data; the tint rides a dedicated overlay global (#165, #168)](decisions/0126-character-scoped-spell-colours-are-campaign-data-the-tint.md) | 2026-07-15 | #165 #168 |
| `0127` | [A caster clones from its OWN class; the spell tint is the flavour lever, not the donor (Rootis, #65)](decisions/0127-a-caster-clones-from-its-own-class-the-spell.md) | 2026-07-17 | #65 |
| `0128` | [Per-caster charge flash: pulse the actor's OWN palette, armed from an EXISTING banim command (#183)](decisions/0128-per-caster-charge-flash-pulse-the-actor-s-own.md) | 2026-07-18 | #183 |
| `0129` | [A HEALER (staff caster) rides ONE anim for heal + defense + post-promo attack — the last PC anim (Sclorbo, #191)](decisions/0129-a-healer-rides-one-anim-for-heal-defense-post.md) | 2026-07-19 | #191 |
| `0130` | [Event backgrounds (BACG): vendored winter CGs, injected as NEW gConvoBackgroundData slots](decisions/0130-event-backgrounds-vendored-winter-cgs-injected-as-new-gconvobackgrounddata.md) | 2026-06-25 | — |
| `0131` | [A dithered CG needs the banks FITTED to it, not tiles that already agree (bg_to_fe8.py)](decisions/0131-a-dithered-cg-needs-the-banks-fitted-to-it.md) | 2026-08-09 | — |
| `0132` | [Maps: hand-drawn in Tiled, NOT AI-generated](decisions/0132-maps-hand-drawn-in-tiled-not-ai-generated.md) | May 2026 | — |
| `0133` | [Audio: vanilla FE8 soundtrack for MVP](decisions/0133-audio-vanilla-fe8-soundtrack-for-mvp.md) | May 2026 | — |
| `0134` | [Art: CUSTOM indexed-palette pixel art for every PC/recruit sprite part — portrait, map sprite, AND battle animation.](decisions/0134-art-custom-indexed-palette-pixel-art-for-every-pc.md) | 2026-06-01 | — |
| `0135` | [Guest (campaign-NPC) portraits: vendor by default, custom when the character recurs; injection is optional-by-file.](decisions/0135-guest-portraits-vendor-by-default-custom-when-the-character.md) | 2026-06-09 | — |
| `0136` | [Green NPC chwinga: per-CHARACTER override of a derived cast sprite, tinted by the green faction palette (#38,...](decisions/0136-green-npc-chwinga-per-character-override-of-a-derived.md) | 2026-07-30 | #38 |
| `0137` | [A luminance recolour can collide two ROLES on one index — check the roles, not just the ramp (#24).](decisions/0137-a-luminance-recolour-can-collide-two-roles-on-one.md) | 2026-06-16 | #21 #24 |
| `0138` | [Item reflavor = global name + icon swap per item id; the cast's per-unit name: fields are documentation only (#21,...](decisions/0138-item-reflavor-global-name-icon-swap-per-item-id.md) | 2026-06-16 | #21 |
| `0139` | [Map-sprite EDITING surface + geometry/animation read from the decomp (2026-06-05).](decisions/0139-map-sprite-editing-surface-geometry-animation-read-from-the.md) | 2026-06-05 | — |
| `0140` | [Cutscene art: portrait-based dialogue only for MVP](decisions/0140-cutscene-art-portrait-based-dialogue-only-for-mvp.md) | May 2026 | — |
| `0141` | [Maps: one community winter tileset + Tiled layouts, inserted decomp-native](decisions/0141-maps-one-community-winter-tileset-tiled-layouts-inserted-decomp.md) | 2026-06-07 | — |
| `0142` | [Winter retiles preserve the vanilla artists' forest sequences as a strict generation AND import invariant.](decisions/0142-winter-retiles-preserve-the-vanilla-artists-forest-sequences-as.md) | 2026-07-20 | — |
| `0143` | [Tilesets stay coherent; Snowy Bern may borrow only Super Fields' complete Snag family.](decisions/0143-tilesets-stay-coherent-snowy-bern-may-borrow-only-super.md) | 2026-07-20 | #24 |
| `0144` | [Adopting non-FE sprite sources (Basil/Oddish)](decisions/0144-adopting-non-fe-sprite-sources.md) | 2026-07-16 | — |
| `0145` | [Adopting sprites, part 2 — Lupin (Lycanroc) + Sahnar (spectral skeleton)](decisions/0145-adopting-sprites-part-2-lupin-sahnar.md) | 2026-07-17 | — |

---

## Class Mapping & Promotions

| | decision | date | issues |
|---|---|---|---|
| `0146` | [A reskin is resolved by its SLOT, never by the class it clones](decisions/0146-a-reskin-is-resolved-by-its-slot-never-by.md) | 2026-09-02 | #347 |
| `0147` | [Growths + starting weapon ranks: copied from a class-matched vanilla "stat donor" unit](decisions/0147-growths-starting-weapon-ranks-copied-from-a-class-matched.md) | 2026-06-04 | — |
| `0148` | [Base classes](decisions/0148-base-classes.md) | 2026-05-30 | — |
| `0149` | [Pepperjack & Brie are vanilla FE8 map ballistae (siege the party mans), NOT roster recruits](decisions/0149-pepperjack-brie-are-vanilla-fe8-map-ballistae-not-roster.md) | 2026-06-20 | — |
| `0150` | [Promotions are FE8's vanilla BRANCHED choice (the player picks at the Master Seal)](decisions/0150-promotions-are-fe8-s-vanilla-branched-choice.md) | 2026-05-30 | — |
| `0151` | [Sclorbo: stock Priest → Bishop (staff healer; attack tomes at promotion)](decisions/0151-sclorbo-stock-priest-bishop.md) | 2026-05-29 | — |
| `0152` | [Rootis: stock Mage → Sage / Mage Knight](decisions/0152-rootis-stock-mage-sage-mage-knight.md) | 2026-05-29 | — |
| `0153` | [FE stat column folds 5e stats to FE stats](decisions/0153-fe-stat-column-folds-5e-stats-to-fe-stats.md) | 2026-05-27 | — |
| `0154` | [Wolfram & RBG are NOT casters](decisions/0154-wolfram-rbg-are-not-casters.md) | 2026-05-29 | — |
| `0155` | [The promotion seam (Ch 8 → 9): foreshadow in the MVP, pay off at Revel's End](decisions/0155-the-promotion-seam-foreshadow-in-the-mvp-pay-off.md) | 2026-05-31 | — |

---

## Story & Dialogue

| | decision | date | issues |
|---|---|---|---|
| `0156` | [Tutorial-parity is a standing guardrail, not a one-time map.](decisions/0156-tutorial-parity-is-a-standing-guardrail-not-a-one.md) | 2026-06-21 | — |
| `0157` | [Faceless narration/asides always ride an opaque SOLOTEXTBOXSTART box, never the translucent talk window (#58).](decisions/0157-faceless-narration-asides-always-ride-an-opaque-solotextboxstart-box.md) | 2026-06-20 | #58 |
| `0158` | [Dialogue is co-written via the dialogue-pass skill: voice bibles → beats → 2–3 variants per beat, Nicolas picks.](decisions/0158-dialogue-is-co-written-via-the-dialogue-pass-skill.md) | 2026-06-09 | — |
| `0159` | [MINE THE CORPUS BEFORE WRITING A LINE — this is now step 0 of the drafting loop, not advice.](decisions/0159-mine-the-corpus-before-writing-a-line-this-is.md) | 2026-07-23 | — |
| `0160` | [Villain voice is grounded in FE8's own script, and contrasting clichés are banned.](decisions/0160-villain-voice-is-grounded-in-fe8-s-own-script.md) | 2026-07-23 | — |
| `0161` | [Dialogue-pass craft learnings (2026-07-23, ch05 opening) — folded into the skill's Craft check.](decisions/0161-dialogue-pass-craft-learnings-folded-into-the-skill-s.md) | 2026-07-23 | — |
| `0162` | [New-game opening sequence: three exclusive content layers, written in story order.](decisions/0162-new-game-opening-sequence-three-exclusive-content-layers-written.md) | 2026-06-09 | — |
| `0163` | [Lore crawl rides vanilla's seven-slide proc untouched; slides are re-rendered PNGs, gated by MONTAGE=1.](decisions/0163-lore-crawl-rides-vanilla-s-seven-slide-proc-untouched.md) | 2026-06-10 | — |
| `0164` | [Build the two flavours with tools/build.sh test|dist — a plain make after build_campaign --montage silently clobbers...](decisions/0164-build-the-two-flavours-with-tools-build-sh-test.md) | 2026-06-17 | — |
| `0165` | [World-map tour rides vanilla's drawn-map slot with two Icewind Dale backdrops, selected by a free mask bit.](decisions/0165-world-map-tour-rides-vanilla-s-drawn-map-slot.md) | 2026-06-10 | #29 #43 |
| `0166` | [Sephek Kaltro arc — distinct from Ravisin; ch02 plants the breadcrumb; reckoning held for Act II.](decisions/0166-sephek-kaltro-arc-distinct-from-ravisin-ch02-plants-the.md) | 2026-07-05 | #125 |
| `0167` | [Marty's "spore covenant" is retired — a thread that reads well in a bible and never reached a beat](decisions/0167-marty-s-spore-covenant-is-retired-a-thread-that.md) | 2026-07-29 | — |
| `0168` | [Vanilla's "if the escort died" cutscene is the same scene's BACK HALF — so our branch is cheap](decisions/0168-vanilla-s-if-the-escort-died-cutscene-is-the.md) | 2026-07-30 | — |
| `0169` | [A recruit-gated scene block goes MID-scene, never on the button](decisions/0169-a-recruit-gated-scene-block-goes-mid-scene-never.md) | 2026-07-30 | — |

---

## Operational Gotchas (durable)

_Moved here from `HANDOFF.md` 2026-07-02 (audit): these are durable engineering constraints, not
session state. `HANDOFF.md` points here._

| | decision | date | issues |
|---|---|---|---|
| `0170` | [A guard that stops guarding fails silently, and green is what that looks like](decisions/0170-a-guard-that-stops-guarding-fails-silently-and-green.md) | 2026-09-02 | — |
| `0171` | [A duplicate top-level def disables the earlier one and says nothing](decisions/0171-a-duplicate-top-level-def-disables-the-earlier-one.md) | 2026-09-02 | — |
| `0172` | [AI behaviour is MEASURED and REPORTED, not weighted into threat](decisions/0172-ai-behaviour-is-measured-and-reported-not-weighted-into.md) | 2026-09-03 | #344 |
| `0173` | [A deadline that measures the MACHINE is not a deadline](decisions/0173-a-deadline-that-measures-the-machine-is-not-a.md) | 2026-09-02 | #345 |
| `0174` | [A message id written as a bare literal now registers itself](decisions/0174-a-message-id-written-as-a-bare-literal-now.md) | 2026-09-02 | #346 |
| `0175` | [A retile inherits vanilla's GIFT PLACEMENT, not just its terrain](decisions/0175-a-retile-inherits-vanilla-s-gift-placement-not-just.md) | 2026-08-07 | #25 |
| `0176` | [Generated art is CONVERTED by the injector, never left for make](decisions/0176-generated-art-is-converted-by-the-injector-never-left.md) | 2026-08-07 | #245 |
| `0177` | [Vanilla prose is a legitimate PLACEHOLDER; vanilla wiring is not](decisions/0177-vanilla-prose-is-a-legitimate-placeholder-vanilla-wiring-is.md) | 2026-08-07 | #25 |
| `0178` | [Campaign-owned EVENT SCRIPTS, same as tables](decisions/0178-campaign-owned-event-scripts-same-as-tables.md) | 2026-08-07 | #25 |
| `0179` | [Campaign rosters live in campaign-named symbols](decisions/0179-campaign-rosters-live-in-campaign-named-symbols.md) | 2026-08-07 | #25 |
| `0180` | [Owning the symbol means owning the POINTER](decisions/0180-owning-the-symbol-means-owning-the-pointer.md) | 2026-08-07 | #25 |
| `0181` | [A CHAPTER_L_ label is resolved by VALUE, never spelled from a number](decisions/0181-a-chapterl-label-is-resolved-by-value-never-spelled.md) | 2026-08-07 | #25 |
| `0182` | [A dead message id is proven by USE, not by an empty body](decisions/0182-a-dead-message-id-is-proven-by-use-not.md) | 2026-08-08 | #25 |
| `0183` | [A host block is not the whole id budget — sweep the neighbourhood](decisions/0183-a-host-block-is-not-the-whole-id-budget.md) | 2026-08-13 | #25 |
| `0184` | [A cutscene's CHANNEL is inherited from the twin, not chosen](decisions/0184-a-cutscene-s-channel-is-inherited-from-the-twin.md) | 2026-08-13 | #25 |
| `0185` | [Text_BG is not a spelling of BACG — it is a CALL with a fade cycle on both ends](decisions/0185-textbg-is-not-a-spelling-of-bacg-it-is.md) | 2026-08-13 | — |
| `0186` | [A reporting artifact outlived the note that named it: the ch05 endings](decisions/0186-a-reporting-artifact-outlived-the-note-that-named-it.md) | 2026-08-19 | #25 |
| `0187` | [CHECK_ALIVE answers for a unit in ANY faction — so a recruit needs its FLAG too](decisions/0187-checkalive-answers-for-a-unit-in-any-faction-so.md) | 2026-08-19 | #25 |
| `0188` | [A conditional block inside a scene is a WHOLE second copy, not a spliced beat](decisions/0188-a-conditional-block-inside-a-scene-is-a-whole.md) | 2026-08-19 | #25 |
| `0189` | [Neither ch05 ending branches on Lupin: an ENCOUNTER is not a RECRUIT](decisions/0189-neither-ch05-ending-branches-on-lupin-an-encounter-is.md) | 2026-08-19 | #25 |
| `0190` | [The test, for any future line: does the player necessarily ENCOUNTER the thing it names?](decisions/0190-the-test-for-any-future-line-does-the-player.md) | 2026-08-19 | — |
| `0191` | [A portrait SLOT name is not a face TAG, and the near-miss is silent](decisions/0191-a-portrait-slot-name-is-not-a-face-tag.md) | 2026-08-13 | #25 |
| `0192` | ["Did the player recruit them?" is CHECK_ALIVE, and it needs no flag](decisions/0192-did-the-player-recruit-them-is-checkalive-and-it.md) | 2026-08-13 | #25 |
| `0193` | [The --ch05-boot ROM can only ever play the NO-Lupin arm](decisions/0193-the-ch05-boot-rom-can-only-ever-play-the.md) | 2026-08-13 | #25 |
| `0194` | [A glued em-dash still has to FIT](decisions/0194-a-glued-em-dash-still-has-to-fit.md) | 2026-08-13 | #25 |
| `0195` | [The alive arm needed a LEVER, and the boot seed was a second reason it had none](decisions/0195-the-alive-arm-needed-a-lever-and-the-boot.md) | 2026-08-14 | #25 |
| `0196` | [A reskin keeps its donor's CLASS NAME, and that is the intent](decisions/0196-a-reskin-keeps-its-donor-s-class-name-and.md) | 2026-08-21 | — |
| `0197` | [We wrapped on-map talk at 29 CHARACTERS; the engine measures PIXELS](decisions/0197-we-wrapped-on-map-talk-at-29-characters-the.md) | 2026-08-21 | — |
| `0198` | [Two arms of one branch can be the same LENGTH — so box count is not a witness](decisions/0198-two-arms-of-one-branch-can-be-the-same.md) | 2026-08-21 | #25 |
| `0199` | [The last two CHECK_ALIVE states, proved](decisions/0199-the-last-two-checkalive-states-proved.md) | 2026-08-21 | #25 |
| `0200` | [A page break is AUTHORED, and vanilla is the reason](decisions/0200-a-page-break-is-authored-and-vanilla-is-the.md) | 2026-08-21 | #25 |
| `0201` | [A letterbox mat is not picture, and a CENTRE crop keeps half of it](decisions/0201-a-letterbox-mat-is-not-picture-and-a-centre.md) | 2026-08-14 | #25 |
| `0202` | [Inheriting a channel is not inheriting a POSITION: scene 5 plays after PREP](decisions/0202-inheriting-a-channel-is-not-inheriting-a-position-scene.md) | 2026-08-14 | #25 |
| `0203` | [A fallback line chosen as PROSE has not been boxed](decisions/0203-a-fallback-line-chosen-as-prose-has-not-been.md) | 2026-08-14 | #25 |
| `0204` | [A face that never speaks must be PRELOADED, and podium rungs overlap](decisions/0204-a-face-that-never-speaks-must-be-preloaded-and.md) | 2026-08-14 | #25 |
| `0205` | [A unit's LOAD tile is not its POST, and the difference cost us the arena](decisions/0205-a-unit-s-load-tile-is-not-its-post.md) | 2026-08-14 | #25 |
| `0206` | [AI parity can hide in a GLOBAL table, not in the unit's own bytes](decisions/0206-ai-parity-can-hide-in-a-global-table-not.md) | 2026-08-14 | #25 |
| `0207` | [A terrain byte is not a picture: pan to the thing before you shoot](decisions/0207-a-terrain-byte-is-not-a-picture-pan-to.md) | 2026-08-14 | #25 |
| `0208` | [A GENERATED COMMENT is part of the script it describes](decisions/0208-a-generated-comment-is-part-of-the-script-it.md) | 2026-08-14 | #25 |
| `0209` | [CI runs make test BEFORE it mocks baserom.gba (2026-07, #23)](decisions/0209-ci-runs-make-test-before-it-mocks-baserom-gba.md) | — | #23 |
| `0210` | [Prove a menu action by its SEMANTIC command, not by resemblance](decisions/0210-prove-a-menu-action-by-its-semantic-command-not.md) | 2026-08-11 | #25 |
| `0211` | [A CHAPTER costs local slots, so a chapter gets its own chunk](decisions/0211-a-chapter-costs-local-slots-so-a-chapter-gets.md) | 2026-08-24 | #314 |
| `0212` | [The headroom guard measured one file correctly BY ACCIDENT](decisions/0212-the-headroom-guard-measured-one-file-correctly-by-accident.md) | 2026-08-24 | #327 |
| `0213` | [A CHAPTER is not what was filling harness.lua](decisions/0213-a-chapter-is-not-what-was-filling-harness-lua.md) | 2026-08-24 | #327 |
| `0214` | [A scenario is DECLARED by the chapter it tests](decisions/0214-a-scenario-is-declared-by-the-chapter-it-tests.md) | 2026-08-24 | #314 |
| `0215` | [A scenario written against the old design will FAIL ON SUCCESS](decisions/0215-a-scenario-written-against-the-old-design-will-fail.md) | 2026-08-14 | #25 |
| `0216` | [A vendored anim's palette is a BY-EYE call, so it gets an editor, not a function](decisions/0216-a-vendored-anim-s-palette-is-a-by-eye.md) | 2026-08-17 | #25 |
| `0217` | [ch06 departs from its donor's terrain in 21 declared cells, and replaces forest composition wholesale](decisions/0217-ch06-departs-from-its-donor-s-terrain-in-21.md) | 2026-08-28 | #26 |
| `0218` | [A LOCK has a DATE, and facts settled after it still apply](decisions/0218-a-lock-has-a-date-and-facts-settled-after.md) | 2026-08-19 | #25 #293 |
| `0219` | [A battle anim carries FOUR palettes and the engine picks one; ours are four copies](decisions/0219-a-battle-anim-carries-four-palettes-and-the-engine.md) | 2026-08-20 | #25 |
| `0220` | [recordenemy baits by REACH OVERLAP, not by melee — an archer can be benched](decisions/0220-recordenemy-baits-by-reach-overlap-not-by-melee-an.md) | 2026-08-20 | #25 |
| `0221` | [mapfull was chapter-generic in name and ch03-shaped in fact](decisions/0221-mapfull-was-chapter-generic-in-name-and-ch03-shaped.md) | 2026-08-20 | #25 |
| `0222` | [The TESTCH bench is bounded by SMS VRAM, not by its tile row](decisions/0222-the-testch-bench-is-bounded-by-sms-vram-not.md) | 2026-08-19 | #25 |
| `0223` | [A community map sprite is keyed on GREEN, not on index 0](decisions/0223-a-community-map-sprite-is-keyed-on-green-not.md) | 2026-08-17 | #25 |
| `0224` | [Ravisin's map sprite rides SCRIPTED_NEUTRAL_SPRITES, boss or not](decisions/0224-ravisin-s-map-sprite-rides-scriptedneutralsprites-boss-or-not.md) | 2026-08-17 | #25 |
| `0225` | [An artifact is not its inputs — verify the FILE you are shipping](decisions/0225-an-artifact-is-not-its-inputs-verify-the-file.md) | 2026-08-14 | #25 |
| `0226` | [The "one output path" half bit again, sequentially rather than concurrently (2026-08-19, #25).](decisions/0226-the-one-output-path-half-bit-again-sequentially-rather.md) | 2026-08-19 | #25 |
| `0227` | [An FEditor L is an authoring bracket, not an instruction](decisions/0227-an-feditor-l-is-an-authoring-bracket-not-an.md) | 2026-08-08 | #25 |
| `0228` | [Arming the HP depletion is not LANDING it](decisions/0228-arming-the-hp-depletion-is-not-landing-it.md) | 2026-08-08 | #25 |
| `0229` | [A donor row is completed for the CLASS, not for the unit that lands it](decisions/0229-a-donor-row-is-completed-for-the-class-not.md) | 2026-08-08 | #25 |
| `0230` | [A green recruit's TILE is load-bearing, and getting it wrong has no symptom (#25).](decisions/0230-a-green-recruit-s-tile-is-load-bearing-and.md) | 2026-08-08 | #25 |
| `0231` | [Wiring a recruit and PROVING it are different jobs, and the passing scenario proved nothing.](decisions/0231-wiring-a-recruit-and-proving-it-are-different-jobs.md) | 2026-08-08 | #25 |
| `0232` | [The village-raid race is four vanilla parts, and ch05 shipped none of them (#25)](decisions/0232-the-village-raid-race-is-four-vanilla-parts-and.md) | 2026-08-09 | #25 |
| `0233` | [5. Which ID SPACE a sound comes from, before which sound.](decisions/0233-5-which-id-space-a-sound-comes-from-before.md) | 2026-08-10 | — |
| `0234` | [A cache can be right for the wrong reason, and only the artifact says which.](decisions/0234-a-cache-can-be-right-for-the-wrong-reason.md) | 2026-08-13 | #255 |
| `0235` | [WHEN a scope is hashed is the whole feature. Hashing at the end of the build undid it.](decisions/0235-when-a-scope-is-hashed-is-the-whole-feature.md) | 2026-08-13 | #255 |
| `0236` | [Reading a VANILLA tileset's art: the committed object sheet is an INVERTED grayscale PNG](decisions/0236-reading-a-vanilla-tileset-s-art-the-committed-object.md) | 2026-08-10 | #24 |
| `0237` | [A wash-out is a CHROMA failure, and our checks all measured luminance](decisions/0237-a-wash-out-is-a-chroma-failure-and-our.md) | 2026-08-12 | #265 |
| `0238` | [Composition needs the base ROM; config loading must not](decisions/0238-composition-needs-the-base-rom-config-loading-must-not.md) | 2026-08-12 | #265 |
| `0239` | [Reading a vanilla BG asset offline: tools/rom_bg_preview.py, and TSA is not always LZ77](decisions/0239-reading-a-vanilla-bg-asset-offline-tools-rombgpreview-py.md) | 2026-08-12 | #265 |
| `0240` | [The injector was slow in Python, not in work](decisions/0240-the-injector-was-slow-in-python-not-in-work.md) | 2026-08-13 | #274 |
| `0241` | [A battle anim binds to a CHARACTER, not to the cast](decisions/0241-a-battle-anim-binds-to-a-character-not-to.md) | 2026-08-15 | #25 |
| `0242` | [A name needs a STRING, not a character slot](decisions/0242-a-name-needs-a-string-not-a-character-slot.md) | 2026-08-15 | #25 |
| `0243` | [convertible prices a fight the player declines — name the chapter after it and they won't](decisions/0243-convertible-prices-a-fight-the-player-declines-name-the.md) | 2026-08-15 | #25 |
| `0244` | [One unit can BE the parity overage, and the band will hide it](decisions/0244-one-unit-can-be-the-parity-overage-and-the.md) | 2026-08-15 | #25 |
| `0245` | [The role check has to read the personal line; the aggregate cannot yet](decisions/0245-the-role-check-has-to-read-the-personal-line.md) | 2026-08-15 | #25 |
| `0246` | [A test below unittest.main() is not a test](decisions/0246-a-test-below-unittest-main-is-not-a-test.md) | 2026-08-15 | — |
| `0247` | [A skip guard must key on a symbol only WE write](decisions/0247-a-skip-guard-must-key-on-a-symbol-only.md) | 2026-08-16 | #25 |
| `0248` | [The rule: a guard that asks "has our injection happened?" must name something only WE emit.](decisions/0248-the-rule-a-guard-that-asks-has-our-injection.md) | 2026-08-16 | #286 |
| `0249` | [A boss on a vanilla SLOT already has its line — measure what deploys](decisions/0249-a-boss-on-a-vanilla-slot-already-has-its.md) | 2026-08-16 | #284 |
| `0250` | [Riding a slot is not enough — the slot has to survive the build, and one does not.](decisions/0250-riding-a-slot-is-not-enough-the-slot-has.md) | 2026-08-16 | #284 |
| `0251` | [A zero is a cliff, not a measurement — the aggregate reads the real article](decisions/0251-a-zero-is-a-cliff-not-a-measurement-the.md) | 2026-08-16 | #285 |
| `0252` | [One death quote per character](decisions/0252-one-death-quote-per-character.md) | 2026-08-16 | #25 |
| `0253` | [A ground array holds index + 1, and nobody was reading the ground](decisions/0253-a-ground-array-holds-index-1-and-nobody-was.md) | 2026-08-16 | #25 #65 |
| `0254` | [A scene is readable without a ROM, and a press count is read off the BODY](decisions/0254-a-scene-is-readable-without-a-rom-and-a.md) | 2026-08-23 | #311 |
| `0255` | [Three traps the reader had to be taught, each of which renders a plausible wrong scene:](decisions/0255-three-traps-the-reader-had-to-be-taught-each.md) | 2026-08-23 | — |
| `0256` | [A chapter's status is DERIVED, and HANDOFF stops carrying it](decisions/0256-a-chapter-s-status-is-derived-and-handoff-stops.md) | 2026-08-23 | #312 |
| `0257` | [Three things it found on the day it was built:](decisions/0257-three-things-it-found-on-the-day-it-was.md) | 2026-08-23 | — |
| `0258` | [Every ChapterEventGroup field is WRITTEN or DECLARED-INHERITED](decisions/0258-every-chaptereventgroup-field-is-written-or-declared-inherited.md) | 2026-08-23 | #313 |
| `0259` | [A base-map LABEL is prose — the donor is DERIVED](decisions/0259-a-base-map-label-is-prose-the-donor-is.md) | 2026-08-26 | #26 |
| `0260` | [Three ways the naive version of this lies, all handled in the tool and all worth knowing:](decisions/0260-three-ways-the-naive-version-of-this-lies-all.md) | 2026-08-26 | — |
| `0261` | [A map sprite is 32x32 or it is nothing](decisions/0261-a-map-sprite-is-32x32-or-it-is-nothing.md) | 2026-08-26 | #26 |
| `0262` | [The DONOR and the BAR are different chapters, and ch06 makes that explicit](decisions/0262-the-donor-and-the-bar-are-different-chapters-and.md) | 2026-08-28 | #26 |
| `0263` | [Messie is a cutscene, not a boss](decisions/0263-messie-is-a-cutscene-not-a-boss.md) | 2026-08-29 | — |
| `0264` | [The AI is in the UnitDefs, so it is DERIVED](decisions/0264-the-ai-is-in-the-unitdefs-so-it-is.md) | 2026-08-29 | — |
| `0265` | [A donor carries its AI, so there is nothing left to allowlist](decisions/0265-a-donor-carries-its-ai-so-there-is-nothing.md) | 2026-08-31 | #335 |
| `0266` | [Permadeath is a combat rule, not a narrative one](decisions/0266-permadeath-is-a-combat-rule-not-a-narrative-one.md) | 2026-08-29 | — |
| `0267` | [The FE-Repo is READ, not grepped](decisions/0267-the-fe-repo-is-read-not-grepped.md) | 2026-08-29 | — |
| `0268` | [ch06's boats sit in POCKETS, because a village is a body you cannot walk into and a door you visit it from](decisions/0268-ch06-s-boats-sit-in-pockets-because-a-village.md) | 2026-09-03 | #26 |
| `0269` | [Vanilla Ch6's urgency is TRAVEL TIME, not a fuse](decisions/0269-vanilla-ch6-s-urgency-is-travel-time-not-a.md) | 2026-09-03 | #26 |
| `0270` | [A rescue clock is a HIT RATE, so a scenario MEASURES it and never asserts it](decisions/0270-a-rescue-clock-is-a-hit-rate-so-a.md) | 2026-09-04 | #26 |
| `0271` | [AI_B is the APPROACH and AI_A is the ACTION, and the moving half is AI_A](decisions/0271-aib-is-the-approach-and-aia-is-the-action.md) | 2026-09-04 | #26 |
| `0272` | [A reach number measured on an EMPTY MAP is a claim about terrain, not about the chapter](decisions/0272-a-reach-number-measured-on-an-empty-map-is.md) | 2026-09-04 | #26 |
| `0273` | [Two do-not-attack lists are not one mechanism, and they have different invariants](decisions/0273-two-do-not-attack-lists-are-not-one-mechanism.md) | 2026-09-04 | #26 |
| `0274` | [A reachability gate that skips reinforcements is grading the opening board, not the chapter](decisions/0274-a-reachability-gate-that-skips-reinforcements-is-grading-the.md) | 2026-09-04 | #26 |
| `0275` | [A parity ratio does not say how much of the twin it COPIED, so mirror% says it](decisions/0275-a-parity-ratio-does-not-say-how-much-of.md) | 2026-09-04 | #367 |
| `0276` | [What asking "what is a body" found: ch02 was never counting its own wave](decisions/0276-what-asking-what-is-a-body-found-ch02-was.md) | — | — |
| `0277` | [A rescue-fuse FORECAST is the reusable question, and it is not a danger grid](decisions/0277-a-rescue-fuse-forecast-is-the-reusable-question-and.md) | 2026-09-05 | #26 #367 |
| `0278` | [A map's tileset has one home, and it is the one the BUILD reads](decisions/0278-a-map-s-tileset-has-one-home-and-it.md) | 2026-09-06 | #26 |
| `0279` | [A check that could not RUN is not a check that passed](decisions/0279-a-check-that-could-not-run-is-not-a.md) | 2026-09-15 | #372 |
| `0280` | [The tileset's one home had three more callers, and they were the ones writing TILES](decisions/0280-the-tileset-s-one-home-had-three-more-callers.md) | 2026-09-16 | #374 |
| `0281` | [Three routes to one sidecar, and the fix is that they must AGREE](decisions/0281-three-routes-to-one-sidecar-and-the-fix-is.md) | 2026-09-16 | #373 |
| `0282` | [A read that never changes is read ONCE, and ours was read 114 times](decisions/0282-a-read-that-never-changes-is-read-once-and.md) | 2026-09-17 | #380 |
| `0283` | [Work that does not depend on other work should not wait for it](decisions/0283-work-that-does-not-depend-on-other-work-should.md) | 2026-09-17 | #382 |
| `0286` | [ccache cannot wrap this build, and make green is already near its floor](decisions/0286-ccache-cannot-wrap-this-build-and-make-green-is.md) | 2026-09-17 | #382 |
| `0287` | [A banner is not a domain boundary, and the gate for moving code is its OUTPUT](decisions/0287-a-banner-is-not-a-domain-boundary.md) | 2026-09-17 | #389 |

---

## Open Questions (not yet decided)

See `docs/PRD.md §13` for the full list. Key unresolved items:
- Signature moments for Marty, Meesmickle, Rootis, Sclorbo (Nicolas to recall)
- Velynne Harpell's arc (check published adventure)
- Sephek Kaltro — did he appear in the campaign?
- Messie's specific Bremen function (shop? services? quest-giver?)
- Unit struct save budget for D&D fields (audit in Phase 1, issue #10)
