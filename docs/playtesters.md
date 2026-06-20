# Playing Manchego Stars — a guide for testers

Welcome, playtester! This is how to install the game on your phone and — the important part —
**keep your progress when a new build drops** so you never replay chapters you've already beaten.

If you hit a bug, a balance gripe, or a typo, please
[open the feedback form](https://github.com/NicoviGH/manchego-stars/issues/new?template=playtest_feedback.yml).

---

## 1. Get the game

You have two ways to install — pick whichever is easier for you.

**A. Pre-patched build (easiest — ask Nicolas for the link).** Download the ready-to-play `.gba`
from the private link Nicolas shares with you, and skip to step 2.

**B. Patch it yourself (public).** If you own a legal copy of *Fire Emblem: The Sacred Stones*
(USA), you can build the game from the public patch:
1. Grab `manchego-stars.bps` from the [latest release](https://github.com/NicoviGH/manchego-stars/releases/latest).
2. On your phone, open a browser patcher like **[rompatcher.me](https://www.marcrobledo.com/RomPatcher.js/)**.
3. Pick your FE8 `.gba` as the ROM, pick `manchego-stars.bps` as the patch, tap **Apply**, and
   save the patched `.gba`.

---

## 2. Load it in your emulator

### Android — Pizza Boy GBA
1. Put the patched `.gba` somewhere on your phone (e.g. a `ManchegoStars/` folder).
2. Open **Pizza Boy GBA**, browse to the `.gba`, and load it.

### iOS — Delta
1. Save the patched `.gba` to the **Files** app.
2. Open **Delta**, tap **+**, and pick the `.gba` to import it.

> **Always save in-game.** Use the game's own **Save** menu (between chapters / at suspend points).
> That is what writes the portable save file the next section relies on. **Do not** count on your
> emulator's *save-states* (the quick-save snapshots) to carry over — they are locked to one exact
> build and break on every new drop.

---

## 3. Keep your progress on a new build

Your in-game save lives in a battery save file (`.sav`). New builds of Manchego Stars are designed
to keep the same save layout, so **your old `.sav` stays valid on the new build** — you just have to
carry it across. (A build check guards this; if a drop ever *can't* preserve saves, Nicolas will tell
you and send a fresh starter save instead.)

### Android — Pizza Boy GBA
Pizza Boy attaches a save to a ROM **by filename**, so this is automatic if you keep names identical:
1. (Optional but smart) back up your current `.sav` first — copy it, or use Pizza Boy's save export.
2. Replace the old `.gba` with the new one **using the exact same filename, in the same folder**.
3. Load it — your `.sav` is still attached, and you're right where you left off.

### iOS — Delta
Delta keeps a save tied to each imported game, so move the save over explicitly:
1. **Export your save:** long-press the current game → **Manage Save File** → **Export Save File**,
   and save it to Files.
2. **Import the new build:** tap **+** and import the new patched `.gba`.
3. **Restore your save:** long-press the new game → **Manage Save File** → **Import Save File** →
   pick the save you exported in step 1.
4. Delete the old game entry so you don't get them confused.

---

## Why this works (for the curious)

A Fire Emblem save is accepted on any build whose save-block *layout* matches — the validity check is
a fixed magic number plus a checksum, not a per-build version stamp. Manchego Stars reskins the game
within FE8's existing chapter and character slots and never changes the save structures, so your `.sav`
keeps passing that check from one drop to the next. The repo's drift guard
(`tools/check.py check_save_layout_stable`) fails the build if that ever stops being true, which is the
signal for the one-time "fresh starter save" fallback.
