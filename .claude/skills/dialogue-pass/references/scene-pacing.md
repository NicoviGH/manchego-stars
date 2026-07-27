# Scene pacing — vanilla FE8 measured, and where ours sit

Measured 2026-07-23 with **`python3 tools/vanilla_scene.py <ch> [SceneFragment]`**, which pairs
a decomp eventscript's `TEXTSHOW` ids with the decoded bodies in `texts/texts.txt` and prints
the scene as boxed dialogue with a box count. Re-run it for the chapter you're writing —
that's `SKILL.md` §Inputs #4 made concrete.

`lore/narration.md` holds decomp-measured budgets for **cards / crawls / tours**. It has never
covered **chapter cutscenes** — this file does.

> Caveat: speaker attribution in the tool is approximate (it tracks the last `[LoadFace]`, and
> FE8 alternates portraits faster than that). Box counts and content are reliable; the name in
> front of a line is a hint, not gospel.

## The shape: vanilla front-loads, then keeps interruptions tight

**Opening scenes (`*_BeginningScene`), in boxes:**

| vanilla | Ch1 | Ch2 | Ch3 | Ch4 | Ch5 | Ch6 |
|---|---|---|---|---|---|---|
| boxes | 1 | 33 | 55 | 45 | **71** | 98 |

(Ch1 is ~0 because its story sits in the prologue/world-map, not the map scene.) Ch5's ending
scene is **74**. So a mid-game chapter spends roughly **45–100 boxes** on its opening and
about as many on its ending.

**But mid-battle beats are SHORT** — Ch5's in-map scenes run **3–7 boxes**:

- **3 boxes** — the bandit squad announcing it's joining the fight (`089F22A4`):
  > "Look at this. Now's our chance!" / "C'mon, lads!" / "Let's join the fight and steal our
  > way through this pathetic town!"
- **4 boxes** — the shop/armory tutorial · **7 boxes** — the Talk-recruit + crit tutorial
- **32 boxes** — one larger mid-battle story scene (`089F2270`)

**The rule to write to:** put story in the opening/ending cutscenes; a mid-battle escalation
is a *punch*, not a scene. An enemy announcing a turn of the battle gets ~3 boxes.

## Where our chapters sit (script lines in the chapter YAML)

| ours | ch00 | ch01 | ch02 | ch03 | ch04 | ch05 |
|---|---|---|---|---|---|---|
| opening | 10 | 29 | 10 | 14 | 8 | **7** (4 pre-map + 3 on-map) |
| ending | 6 | 22 | 11 | 7 | 3 | *unwritten* |

**We run at roughly 10–25% of the vanilla twin's cutscene length, and ch05 is our leanest yet.**
That is a real, quantified gap — not necessarily wrong (our register is terser and our cast
smaller than Eirika's), but it should be a *decision*, not an accident. ch01 at 29 lines shows
we go bigger when a chapter earns it, and ch05 is our first real boss.

**What this does NOT change:** our mid-battle beats are already right-sized. The ch05 eruption
drafts (~4–9 boxes) sit correctly against vanilla's 3-box escalation — if anything they can be
tighter. The gap is entirely in the opening/ending cutscenes.

## Tutorial-parity note found while measuring

Vanilla Ch5 spends a 7-box tutorial on **Talk-recruit + critical hits**, tied to Joshua:

> "Sometimes, you can talk to an enemy and convince him to join you… However, Joshua is a red
> unit. Unlike green units you've seen before, he will attack until he's spoken to. Moreover,
> Joshua is a myrmidon, who specializes in **critical hits**… you will suffer 3 times the
> normal damage."

Our **Sahnar is the same killing-edge crit-Myrmidon threat**, and `criticals` sits in
`onboarding-catalog.yaml` **unclaimed by any chapter's `introduces:` ledger**. So crit may never
be introduced in our chapter order before the chapter where a crit duelist first threatens the
player. Run the §Tutorial-parity check on ch05 and settle it with Nicolas (in-voice line vs a
box) before locking the recruit beat.
