# Narration Register — Cards, Crawls & Tours

> Not a character: the voice of the lore crawl (#43), the world-map town tour (#43),
> and in-chapter location/narration cards. Benchmarked against vanilla FE8's decomp
> assets — keep these budgets or the pacing drifts.

## Vanilla benchmarks (decomp-measured)

| Slot | Vanilla form | Budget |
|---|---|---|
| Lore crawl | 7 subtitle cards (`graphics/op_subtitle/`) | 2–5 short lines/card, ~15–25 words |
| World-map tour | `WM_TEXT(0x8DB)`: 4 intro cards + 5 nation cards + closing | ~10 A-presses total; nation card = 2 lines |
| Location card | `BROWNBOXTEXT` ("Renais Castle") | a name, ≤1 line |

## Register rules

- Mythic but plain — vanilla's "In an age long past… evil flooded over the land." is
  the ceiling for poetry. One idea per card.
- Tour epithet formula: "<place>, <one defining clause>." (vanilla: "The kingdom of
  Frelia, ruled by Hayden, the venerable Sage King.")
- Source register: the book's Cold Open boxed text (printed p.22) is already written
  in this voice — adapt, don't invent.
- Content allocation (decided 2026-06-09, see decisions.md): crawl = cosmic (Auril,
  the Rime), tour = geographic (all ten towns, grouped by lake), chapter scenes =
  local plot only. No layer repeats another's facts.

## Tour structure (all ten towns, 4 cards)

1. Bryn Shander — the walled hub, de-facto capital (standalone card).
2. Maer Dualdon: Targos, Bremen, Termalaine, Lonelywood.
3. Lac Dinneshere: Easthaven, Caer-Dineval, Caer-Konig.
4. Redwaters: Good Mead, Dougan's Hole.

One fewer A-press than vanilla's five nations.
