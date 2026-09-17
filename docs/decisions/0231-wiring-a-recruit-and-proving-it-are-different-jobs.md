---
id: 231
title: "Wiring a recruit and PROVING it are different jobs, and the passing scenario proved nothing."
date: "2026-08-08"
section: "Operational Gotchas (durable)"
issues: [25]
---

# Wiring a recruit and PROVING it are different jobs, and the passing scenario proved nothing.

`ch05village` was green across every version of ch05's opening, including ones where Basil never
joined: it leaves Preparations with START and walks a *different* unit to a door, so a green shrub
nobody can command is invisible to it. The recruit chain needed its own gate, and `ch05recruit` is
it — three assertions in the order the player meets them: Basil is BLUE and commandable at turn 1
(the opening CUSA landed, the step with no other witness), Sahnar rises RED on turn 2, and Basil's
Talk flips her BLUE. It also gates the RECRUITER, not just the recruit: if the CHAR list named the
wrong talker the command menu simply has no Talk, and the chapter looks fine until a player tries.
**Its first run failed for the wrong reason, which is the lesson.** It reported "the CUSA did not
fire" when the CUSA was fine — the scene shows vanilla's 32-box `0x9CC` and my advance-dialogue
loop capped at 3600 frames, expiring 18 boxes in. *A loop cap must never be what decides failure.*
The fix is both halves: a budget with real headroom, **and** a verdict that tells "still running"
from "finished and still red", because reporting one as the other is how a wiring bug gets
invented and then hunted.
_Decided: 2026-08-08 (#25; the scenario caught its own author first)._

**DISPLAYING a vanilla message id you do not own is fine; displaying one another chapter WRITES
is not (#25 review).** ch05's scene labels read `slot: "vanilla 0x9C2"`, and those labels name the
chapter we **mine** (vanilla Ch5) — not the block we may write into. ch04 hosts on slot 5 and owns
`0x9BA..0x9C6` outright, so `0x9C2` in the built ROM is ch04's own no-parley ending. Pointing
Basil's join beat at it would have played Pinky and Marty discussing supper, in ch04's voice, with
ch04's faces — a green build, a passing `ch05recruit` (it reads factions, not text), and the wrong
scene on screen. The reliquary pattern is still correct and still in use: `0x9CC` and `0x9CD..0x9D0`
are written by NO hosted chapter, so the ROM holds vanilla's prose and borrowing it is exactly the
placeholder ADR. The two cases are indistinguishable at the call site — both are an int in a
constant — so `assert_message_id_unclaimed` now checks it instead of asking anyone to remember.
The join beat ships SILENT until the dialogue pass gives it an id from ch05's own block
(vanilla Ch6, `0x9E4..0x9F5`); a silent beat also keeps the script in vanilla's safe shape, since
one that continues with VISIBLE content after the prep prologue needs its own `FADU(16)` first.
_Decided: 2026-08-08 (found by `/code-review high` on PR #252, not by the build or the gate)._

---
