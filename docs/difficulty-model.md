# Difficulty Model — Manchego Stars

The doctrine is **field parity with vanilla chapter N** (`docs/decisions.md` → "Field parity"):
our chapter N mirrors vanilla FE8 chapter N on both the **enemy** side (counts/levels/AI) and
the **deploy cap**. This document covers the **party** half of that parity — how our cast is
statted so it plays at vanilla power — plus the **difficulty engine** that measures it as we
build chapters out. Combat math is the decomp's own (`fireemblem8u/src/bmbattle.c`), wired up in
`tools/balance_report.py`.

## 1. Diagnosis (why Ch1 played harder than vanilla)

`tools/balance_report.py` settles it: **the enemies aren't the problem.** Our line goblins are
lv1 (class base); vanilla Ch1's were lv2–3 + the same lv4 boss — so our field is marginally
*easier*. The whole gap was the **party**:

- Our cast were authored as **"naked class" units** — `fe_stats` = the vanilla class base
  verbatim, so every personal base stat was **0**. No real FE character is built that way
  (Franz ≠ a generic Cavalier); ours were effectively generic enemies wearing our faces. Half
  the cast died in <2 hits, and low-Spd units (Wolfram, AS 0) were **doubled** by the line.
- Vanilla balances early chapters around **Seth** — a prepromote "Jagen" (~17.5 enemy-hits to
  down, ORKOs the boss, ~48% of the party's damage). We have no such anchor.

## 2. The model — three layers, all vanilla-faithful

### 2a. Donor personal lines (static foundation)
Each PC already has a **class-matched vanilla donor** (`build_campaign.py` → `STAT_DONOR`), and
the build *already* inherits that donor's **growths + weapon ranks**. We complete it by also
inheriting the donor's **personal base stats** — the exact vanilla mechanism that distinguishes
characters from generics. No custom classes; pure vanilla data; static (baked into
`gCharacterData` at build).

| PC | class | donor (bases / growths) |
|---|---|---|
| Braulo | Pirate | Garcia |
| Wolfram | Knight | Gilliam |
| Prof-RBG | Archer | Neimi |
| Rootis | Mage | Lute |
| Sclorbo | Priest | Moulder |
| Pinky | Pegasus Knight | Vanessa |
| Marty / Meesmickle | Shaman | **Ewan bases / Knoll growths** |

The shamans split bases vs growths because FE8's only Shaman (Knoll) joins at lv9 — his bases
are inflated for Ch1, so we re-base to Ewan (the lv2 trainee dark-mage) while keeping Knoll's
growth curve.

**Result (decomp-sourced, `tools/balance_report.py`):** the cast reaches **vanilla parity on
both axes** — durability brackets vanilla's non-Seth band (Eirika 2.8 → Gilliam 5.9), the
doubling cliff is gone, and team **kill-throughput is ~97% of vanilla's fielded four** (see §4
on why kill-rate, not raw DPR). The Res-0 armor boss is melted by our donor-line mages, the way
vanilla used Eirika's effective Rapier.

### 2b. Per-lord survivability floor (dynamic — "lord-mode")
The player-chosen lord (#42) is force-deployed, must reach the seize tile, and their death is
game-over — today that is pure liability (a must-protect unit with no compensating strength).
Lord-mode fixes the asymmetry: at chapter start the engine applies a **per-lord HP/Def top-up to
a survivability floor (~5.0 enemy-hits-to-down)**, keyed on the chosen-lord flag.

- Bounded and self-scaling: **+0 for tanky picks** (Wolfram, Braulo), **+7 HP / +4 Def for the
  glass shamans**. Every lord clears the same floor, so **no character is a trap.**
- A **floor**, not "+N levels" — leveling barely bulks a low-Def-growth mage, but a direct
  HP/Def top-up floors any class.
- **One-time** top-up: it is huge at lv1 and trivial by lv18, so the anchor **fades into the
  party as everyone levels** (organic Jagen falloff; the ensemble re-forms mid-game). See §3.

### 2c. Roster growth matches vanilla
Add recruits on vanilla's join cadence (toward ~16–18 fielded-pool units by endgame). Party
strength scales the **vanilla way — bodies and promotions, never stat inflation** — and this
closes the only structural gap the campaign projection found: our roster is *deeper* than vanilla
early (8 PCs from Ch1 vs ~5) and would otherwise be *thinner* late (watch deploy-cap vs
roster-size as chapters are written).

### What we do NOT do
Nerf the (already-gentle) enemies · a Seth-tier god-anchor (breaks the ensemble, is unreachable
unpromoted, and the cast are all *player characters* — all eight must matter) · blanket
party-leveling (Def growths are 5–15%, so levels barely move durability) · any Pow/stat inflation
(the cast is already at parity; more overshoots vanilla) · speculative dynamic cast-tuning (the
engine hook exists, but reserve it for a specific playtest-found problem). Deploy caps stay = vanilla.

## 3. Open dials
- **Anchor trajectory** — *one-time* floor (fades → Jagen falloff) **[current choice]** vs a
  floor *re-applied each chapter* (permanent backbone). Flip if playtest shows the lord must stay
  relevant late.
- **Second shaman** — keep Marty/Meesmickle on the same line and **differentiate at promotion**
  (Druid vs Summoner, already decided) **[current choice]** vs giving one a distinct base donor.

## 4. The difficulty engine (tooling)

Generalize `tools/balance_report.py` from a Ch1-specific script into a **per-chapter difficulty
analyzer**, run as each chapter is authored. It is **data-driven** (no per-chapter hardcoding):

- **Inputs:** the chapter's enemy roster (chapter YAML / decomp events), the deployable cast at
  that point (cast YAML + donor lines + the lord floor), and the deploy cap.
- **Combat model:** the decomp's own formulas (`bmbattle.c`) — the single source of combat truth.
- **Metrics (the shared vocabulary):**
  - **Durability** — enemy line-hits-to-down per unit (open / forest).
  - **Output** — **kills-per-round, capped at 1.0/unit.** This is breakpoint-aware (a 2-round →
    1-round kill is what matters) and ignores overkill. Raw summed DPR is *wrong* here: it credits
    a unit for 40 damage to a 20-HP goblin, which massively inflated Seth and made our cast look
    like 72% of vanilla when the honest figure is ~97%.
  - **Carry coverage** — fastest unit to delete the boss / key threats; flag any deployment with
    no answer.
  - **Permutation sweep** — lord × team deployments: distribution + extremes; flag traps
    (a fragile must-survive lord) and trivializations.
  - **Vanilla delta** — our chapter N party vs vanilla chapter N party on all of the above.
- **Honest limits (do not over-trust it):** it is a **static** offense/defense proxy over the
  enemy roster. It does **not** model positioning, weapon range, turn count, enemy AI,
  reinforcement timing, terrain, or healing. It *flags* imbalance and *tracks vanilla parity*;
  the **playtest harness** (`tools/playtest/`) is the dynamic arbiter for everything it can't see.
- **Usage (proposed):** `python3 tools/balance_report.py --chapter chNN` (and/or a
  `make difficulty CH=chNN` target), optionally an advisory CI check on chapter YAML changes.

## References
- `tools/balance_report.py` — combat model + the Ch1 analysis this generalizes.
- `tools/build_campaign.py` — `STAT_DONOR` / `PORTRAIT_MAP` (the donor map); base-inheritance lands here.
- `docs/decisions.md` — the settled decision (party-side parity) and "Field parity" (enemy side).
- `docs/fe8-pacing-reference.md` — vanilla cadence / deploy caps per chapter.
