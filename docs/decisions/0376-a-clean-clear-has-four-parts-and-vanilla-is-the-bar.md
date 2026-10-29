---
id: 376
title: "A clean clear has four parts, a vanilla chapter without one is a bot fault, and the bot clears all of vanilla's Eirika route before any Manchego Stars verdict counts"
date: "2026-10-29"
section: "Combat System"
issues: [510]
---

# A clean clear has four parts, a vanilla chapter without one is a bot fault, and the bot clears all of vanilla's Eirika route before any Manchego Stars verdict counts

Decisions 1-4 of the #510 step 9 long-term design (#510 comment 6485197805, accepted by Nicolas
2026-10-29). Part A built 1 and 2 (#510 comment 6485521139); 3 is built in part C.

**1. A clean clear has four parts, each read from the game at the chapter's end, never from the
bot's intentions:** the chapter is won; no unit is lost, blue or green (vanilla Ch6 gives
Eirika an Orion's Bolt only if its three green villagers live, `EventScr_Ch6_EndingScene`); every
recruit the chapter owes joins; every village and chest the map offers is taken.
- **Owed recruits.** Both games alike, read from the game at the chapter's start (amended
  2026-10-29, audit finding 7): the target of each talk the game would run now
  (`sight.lua` `M.talks`: `SearchAvailableEvent` walks the chapter's `characterBasedEvents`, a
  breakpoint on `EvCheck03_CHAR`/`EvCheck04_CHARASM` reads each talk entry it is handed, and
  `CheckForCharacterEvents` keeps the available ones). A character already in the party at the
  chapter's start, dead or alive, deployed or not, is not owed; so a talk between two party
  members (ch15b's conversations) owes nothing, and a target who joins in the chapter's own
  events is owed and joined. Before: a regex over the decomp's `CHAR`/`CUSA`/`CALL` for vanilla
  (`difficulty._talk_recruits`, still the kit model's) and the YAML's on-map Talk recruits for
  Manchego Stars. Proved equal [ROM]: vanilla Ch2 owes Ross and Garcia, Ch5 Joshua, Manchego
  Stars ch03 Trex, ch01 no one (one walk and 73 checks for Ch2).
- **Joined = seen blue and NOT dead.** Vanilla's endings mark an unrecruited Talk recruit blue
  AND dead: `EventScr_StrictLoadUniqueAlly` CUSAs it (or SPAWN_ALLYs it when it was killed, since
  `UnitKill` clears a red unit's character pointer), then `SET_HP` from slot 1 = 0, which sets
  `US_DEAD` (`eventscr.c`). Seen in the ROM: the scout's Ch6 start holds Joshua blue with state
  0x04010005 (DEAD, HIDDEN, REMU's bits), and the game's prep list leaves him out. A dead blue
  entry is therefore no join (found the hard way: 6567cdc counted it, 0f7c010 fixed it). Manchego
  Stars' endings call no such loader, so an unrecruited recruit there simply never turns blue;
  both games are read alike.
- **Rewards.** The game's own list (`sight.explorable()`: each village and chest whose command
  the game offers; a tile only an event opens later is not on it). Taken = visited or opened by
  us, or a chest whose thief fell to one of ours and whose item then reached one of ours (the
  thief carries `US_DROP_ITEM`, `popup.c`; the drop goes to its killer, `bmmind.c`). A razed
  village is lost at once.
- The BOTRUN record carries `clear` (each part, with what spoiled it) and `clean`; a run with
  no owed list (a single-chapter `bot` run) leaves `clean` null, never true. `all_alive` is
  retired.

**2. On vanilla, a chapter with no clean clear is a bot fault, never "infeasible".** Strong players
clear vanilla FE8 with no losses (Nicolas: "if the bot never finds a solution it's the bots fault
not the level. Especially playing vanilla"). `campaign.lua` stops with `bot_fault`, the chapter
line carrying every failed attempt's `clear` and trace. Manchego Stars keeps `infeasible`.

**3. A retry knows what earlier attempts saw, and only that.** Attempt k at a chapter start reads
the play logs of attempts 1 to k-1 at the same start, each fact filtered by the game's vision
test (`sight.visible`) at the moment it was logged ("A player trying again would have seen the
map and stuff"). Built in part C.

**4. No Manchego Stars verdict counts until the bot clears ALL of vanilla's Eirika route clean**,
the whole route, not chapter by chapter as twins are reached ("Might as well do the whole
route"). This tightens ADR 0374's "the bot is proven on vanilla before ours is judged".

**First evidence (2026-10-29, retail ROM):** vanilla Ch2 cleared clean at attempt 1 (Ross and
Garcia talked over). Vanilla Ch5 has 3 styles and none cleared clean (deaths, the village at 5,1
unreached, Joshua killed), so the campaign stops there as a bot fault. Ch5x is entered from Ch5's
ending (`MNC2(0x5)`), not from Ch4's (`MNCH(0x6)`), so no clean Ch5x start exists until Ch5 is
cleared clean.

**Latent, not live:** vanilla's `StrictLoadUniqueAlly` calls still sit in unhosted slots
(ch10a / ch12b on `CHARACTER_MARISA`, ch14a / ch14b on `CHARACTER_RENNAC`), which Sahnar and Trex
wear. Hosting a chapter in one of those slots must replace that ending, or it marks our unit dead.
