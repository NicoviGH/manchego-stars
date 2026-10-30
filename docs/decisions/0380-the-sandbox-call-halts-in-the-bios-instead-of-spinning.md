---
id: 380
title: "A sandbox call returns into the BIOS's Halt, not a spinning branch-to-self loop"
date: "2026-10-30"
section: "Combat System"
issues: [510]
---

# A sandbox call returns into the BIOS's Halt, not a spinning branch-to-self loop

#510 step 9, Nicolas's sweep of the bot code (2026-10-29: "nice and lean and efficient"). This
amends how ADR 0369's sandbox waits for a call to return. Which game function runs, and what is
read afterwards, does not change.

**Why.** A sandbox call takes at least one whole frame, because the harness only looks between
frames. The function itself is short. Until now the CPU spent the rest of that frame in a Thumb
`b .`, and mGBA emulates a spinning CPU instruction by instruction. The live game instead sits in
the BIOS's VBlankIntrWait, and mGBA skips a halted CPU from event to event. Measured on Manchego
Stars ch01: a sandbox frame cost 0.47 ms, or 1.05 ms with the roll breakpoints held (mGBA
single-steps while any breakpoint is set). A live frame cost about 0.13 ms. The sandbox was 5.0
of the run's 13.4 CPU s.

**What.** In a call that is loaded back, the return loop marks a RAM word, clears REG_IE and calls
the BIOS's Halt (`swi 2`). A RAM write to HALTCNT is ignored unless the CPU is running BIOS code
(mGBA `io.c`, as on hardware), which is why it is a SWI. The halted CPU's pc is in the BIOS, so
"returned" means the marker is set (`test_sight.lua`'s fake CPU runs the same store). Before each
call, the machine puts back two things:
- **The game's REG_IE.** A frame ends with the CPU halted, either in the game's VBlankIntrWait or
  in this loop. Only an enabled, pending interrupt wakes it: VBlank's IF, which is never
  acknowledged because IRQs stay masked in CPSR.
- **The SVC stack pointer, as the sandbox found it.** The next call abandons the BIOS's SWI frame
  without returning from it. Without the reset, the SVC stack crept down by one frame per call.
  About 46 calls into ch01's goal read, it reached the game's IRQ area and a call never returned.

The state load restores everything else (IE, SVC registers, the halted flag). A KEPT call (the shop,
`Sight.machine(cpu, true)`) keeps the old `b .`. Its SWI would overwrite the game's own SVC lr and
spsr, which a frame that ends inside VBlankIntrWait still needs, and no load puts them back.

**Measured, back to back against main (96cf9d1's code):**

| run | CPU s, main | CPU s, now | sandbox game time |
|---|---|---|---|
| Manchego Stars ch01, clean t9 | 13.56 | 9.63 | 5.06 s → 1.72 s |
| vanilla Ch4 attempt 1, clean t5 | 36.49 | 19.83 | 24.48 s → 9.45 s |

The two versions play identically. Both BOTRUN records match apart from `costs` and `frames`, and
ch01's run trace is byte-identical. `frames` counts sandbox frames, and it moved by 3 of 32,163
because some calls now finish at a frame edge.
