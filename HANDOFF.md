# Handoff: Ch6–Ch8 collaborative walkthrough DONE (Bremen arc + MVP finale), plus a repo-wide FE-strictness doc sweep. NEXT = Rootis/Sclorbo signature beats, or start building (toolchain install)

**Date:** 2026-06-01
**Session focus:** Collaborative chapter walkthrough of Ch6 → Ch7 → Ch8, grounded directly in the two source PDFs (DM notes + published Frostmaiden book, Bremen pp.27–29) and the FE8 decomp. Folded book canon into the YAML, recorded two recalled signature moments, and — triggered by a bug found in Ch8 — swept a non-vanilla "element = effectiveness" error out of the docs (then re-worded the fix natively after a band-aid catch). All committed + pushed to main (HEAD `35eafd0`; this session spans `a5a71d0`→`35eafd0`).

## What changed this session

- **Ch6 — The Maer Monster** (`a5a71d0`): named the canon NPCs from the book — captain **Grynsk Berylbore**, researcher **Tali** (half-elf, they/them), boats **Burly Ram** / **Pronged Goat**. Mapped the book's ice-floe hazard to **vanilla FE8 terrain** (no engine work): open water = `SEA` (why the knucklehead swarm is a flier class), drifting floes = destructible `SNAG`, ice walls = `GLACIER`, decks = `SHIP_FLAT`. Ch6 stays **Marty's** signature showcase.
- **Ch7 — Blood in Bremen** (`32ac89c`): **Dorbulgruf Shalescar** reframed as *senile AND greedy* (book: addled mind; notes: cantankerous) — the party kills a confused, dying miser; ambiguity left unresolved. Kept him a formidable Warrior boss. **Wolfram's SECONDARY signature** recorded: mid-battle he bites a chunk out of Dorbulgruf's steel axe (new `battle_quote` event; primary stays Ch3 ore-snacking). Militia grounded (6 guards = town militia, 2 Hall Knights = the book's "2 veterans"); map = Town Hall + Five-Tavern Center.
- **Ch8 — The Eastway Ambush** (`c3cdc71`): faithful to the DM notes already; **removed the non-vanilla `weakness: fire`** on the ice trolls. FE8 has NO fire effectiveness (verified in `src/data_items.c` — 8 class-keyed categories only). Reframed: trolls are monsters, party lacks monster-effective (sacred) weapons → *that's why the wall is unwinnable*.
- **FE-strictness doc sweep** (`c24a966`, reworded `35eafd0`): the Ch8 bug was systemic. Fixed PRD.md (goal, engine bullet, "reads like D&D" pillar, **DoD criterion #6** + stale DoD #8 Messie ch#), decisions.md (the effectiveness rule + the damage-type-labels line), and ch00 prologue (Sephek's cold/fire motif → flavor). **Rule now stated positively: effectiveness is keyed to enemy CLASS (armor/cavalry/flier/dragon/monster/sword); damage types are flavor labels.** NOTE the lesson: the first pass wrote the fix as negation band-aids ("there is NO fire effectiveness", "never element-keyed") — Nicolas caught it; rewritten natively per `feedback_clean_doc_rewrites`. Don't patch over deleted ideas; state the standing rule as if the wrong version never existed.

## Signature-moment tally (the running open thread)

- **Done:** Marty (Ch6 Messie Talk primary + Ch4 wolf parley secondary), Wolfram (Ch3 ore-snacking primary + Ch7 axe-bite secondary), Meesmickle (Ch9 Revel's End toe-bean orc summon — fits his Summoner promotion), Braulo (Ch8 shackle-break).
- **Still TBD:** **Rootis** and **Sclorbo** — not in the DM notes; need Nicolas's recall. (Candidate framings explored and rejected for Ch6: they'd only be cutscene/battle-quote, and neither earned one in Bremen.)

## Standing rules (how Nicolas wants this work done)

- **Stock vanilla FE8 classes/weapons only** (verbatim decomp data). **Element = flavor, NEVER a mechanic** — including effectiveness (reaffirmed hard this session).
- **Ground FE claims in `fireemblem8u/`**; **ground STORY in the two PDFs** (DM notes Ch1–7 only + the published book, image-only scan, PDF page = printed+1). Read them directly when planning story.
- **Clean native doc rewrites** (no STALE/reverted banners). **Auto-push to main.** **Collaborative, chapter-by-chapter** story work (FE8 parallel + our version). **Balance: defer to FE, lean generous.**
- **Doc source-of-truth model:** per-chapter/unit facts live ONLY in YAML; `docs/CHAPTERS.md` + `CLASSES.md` are GENERATED (never hand-edit; re-run `ruby tools/gen-chapter-index.rb` + `gen-class-index.rb`); hand docs hold only durable rationale + forward planning. **Lean repo**; backlog lives in **GitHub issues** (M0–M4).

## Current repo / doc state

- All 9 MVP chapters (ch00–ch08) authored in YAML and now walked through against the sources. Generators clean. Validate YAML: `ruby -ryaml -e 'YAML.load_file("<path>")'`.
- **Source of truth:** chapter facts = `campaigns/.../chapters/ch00…ch08-*.yaml`; unit class/promotion/signatures = `campaigns/.../{pcs,npcs}/*.yaml`. Backlog = GitHub issues.

## NEXT TASK (pick one)

1. **Resolve Rootis + Sclorbo signature moments** — ask Nicolas to recall their standout beats, then anchor them in the right chapters (manifest as cutscene/battle-quote/conditional-command — NOT custom skills).
2. **Start building** — the first real blocker is **"Install the build toolchain"** (devkitARM/agbcc/ColorzCore/libpng), which gates every ROM build/test. `tools/build-campaign.ts` / `build-events.ts` still unbuilt (GitHub issues exist).
3. **Ch9+ story** is blocked on the rest of the DM notes (they end at the Eastway capture → Revel's End). Meesmickle's Ch9 toe-bean beat is the one confirmed Act II anchor so far.

## Blockers / open

- **Rootis & Sclorbo signature moments** still TBD (need Nicolas's recall).
- **pepperjack/brie `fe_stats.class` = null** (FE-legal class TBD post-MVP).
- **Ch 9–20 plot** blocked on the rest of the DM notes.
- **Build toolchain not installed** + `tools/build-campaign.ts`/`build-events.ts` unbuilt.
- **Lingering lean candidates** (low priority): `pc-spell-lists.md` / `magic-items.md` → consume into YAML then delete; PRD §8/§9 could slim further.
- **Pre-existing band-aid in `decisions.md`** (offered, not yet done): the damage-type-labels entry (~L164) still carries a `(reverted 2026-05-28 — see Combat System §)` parenthetical — same band-aid pattern, but it predates this session and is part of the ADR-style `_Decided / supersedes_` log convention. Clean the reverted-banners out of the decision log if Nicolas wants.
