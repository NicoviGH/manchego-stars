---
id: 166
title: "Sephek Kaltro arc — distinct from Ravisin; ch02 plants the breadcrumb; reckoning held for Act II."
date: "2026-07-05"
section: "Story & Dialogue"
issues: [125]
---

# Sephek Kaltro arc — distinct from Ravisin; ch02 plants the breadcrumb; reckoning held for Act II.

Sephek (ch00 prologue boss, escapes undead) and **Ravisin** (ch05 "The Elven Tomb" frost-druid boss,
the beast-awakener) are **separate villains and stay separate** — both serve Auril (canon: Sephek is a
frost-druid spirit in a drowned mariner's body, book p.23-24), but Ravisin's ch05 stays our clean first
boss kill and Sephek is never folded into it (that would spend his reserved drowned-mariner death-reveal
in her fight). The **ch02-targos-inn** ending plants his first breadcrumb: the frozen body is one of his
sacrifice-lottery executions; the town blames the druids' rumor, while **Rootis** privately recognizes
the dagger-of-ice M.O. from **Hlin's briefing** (the party didn't witness ch00 — that prologue deploys
Hlin + Scramsax only, so Rootis knows the method, not the man). No fight here. His **reckoning** is held
for **Act II**: the book reserved the Torrga Icevein caravan as his payoff venue, but ch00 already uses
that caravan as its setting, so his true death gets a fresh Act-II setting — **provisionally a secondary
boss on a multi-boss map** (vanilla precedent: FE8 Ch15 Caellach + Valter, the Final chapter's Demon King
+ Lyon; our own ch05 already runs Ravisin + the White Moose), firmed when the back-half DM notes arrive.
Don't spend his death-reveal imagery before then.
_Decided 2026-06-19 with Nicolas (interactive story + dialogue pass for ch02-targos-inn)._

---

**#125 msg-id collision (ch01 ending vs. the tutorial trade demo) — RESOLVED unreachable, no emulator
needed.** `CH01_ENDING_MSGS` (0x949-0x94C) are also `TEXTSHOW`n by vanilla's tutorial-mode trade demo
compiled into `src/bmtrade.c`, which nothing patches — flagged as a live risk needing an mGBA repro to
size (#122 comment-sweep). Traced instead: that demo only runs behind `CheckTradeTutorial()` ->
`CheckFlag(0x87)`, and flag `0x87` has **exactly one setter in the whole decomp** — `ENUT(0x87)` inside
`EventScr_Ch1Tut_TradeSelectGalliamEnd` (`events/ch1-tutorials.h`), part of vanilla's real Ch1 chapter
slot (`Ch1Events` in `data_8B363C.s`) — a **separate ROM asset from `PrologueEvents`**, the only slot our
chapter progression ever loads (New Game redirects to `PROLOGUE_HOST_INDEX`; `_redirect_new_game` in
`build_campaign.py`). Vanilla's real Ch1 never loads in our build (our "ch01" rides the Prologue slot
instead), so flag `0x87` can never be set, `CheckTradeTutorial()` always returns false, and the trade
demo — and this msg-id collision — is unreachable by construction. General lesson for the msg-id-vetting
gotcha (below): reachability isn't just "is this id referenced elsewhere" (the 0x993/0x994 lesson) — a
referencing event can ALSO be dead if its own trigger condition (a flag, in this case) can never be set
in our build's actual chapter-load graph. Static trace of the flag's setter(s) resolves it without mGBA.
_Decided: 2026-07-05 (CLAUDE; pipeline track. #125, closed not-planned — no code change, comment-only)._

---
