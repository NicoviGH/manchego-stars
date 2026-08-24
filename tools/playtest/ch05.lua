-- ch05.lua -- ch05's chapter-scoped playtest facts, in ITS OWN chunk (#314).
--
-- WHY THIS FILE EXISTS. Lua caps locals at 200 per chunk and `harness.lua` is one chunk at
-- that ceiling. Of its 198 top-level locals, 32 are chapter- or cast-scoped -- ~6-7 per
-- chapter over the five built -- so a shared budget runs out during ch06, not at ch18. The
-- old escape hatch ("declare it inside the scenario that needs it") kept the harness
-- compiling by converting the ceiling into DUPLICATION instead: 94 constant declarations
-- inside scenario bodies, 24 names re-typed across two or three scenarios. Basil's pid was
-- typed in three places, Ravisin's in two.
--
-- So a chapter's facts live in a chapter chunk with its own fresh 200. `LUA_CHUNKS` is
-- globbed, so `check_lua_chunks_load` covers this file the day it exists.
--
-- HOW TO USE IT. `dofile` it INSIDE the scenario that needs it -- function-scoped, so it
-- still costs harness.lua no top-level slot:
--
--     scenarios.ch05crest = function()
--         local CH05 = dofile(PLAYTEST_DIR .. "/ch05.lua")
--         ... CH05.PID.RAVISIN ...
--
-- WHAT BELONGS HERE: facts about ch05 that more than one scenario reads -- cast pids, the
-- reliquary table, message ids a branch turns on. What does NOT: engine constants (terrain
-- ids, item ids that are FE8's rather than ours) and anything a single scenario uses once.
-- ch06 starts here by default rather than by exception.
return {
    -- Cast, by the vanilla character slot each unit occupies.
    PID = {
        BASIL   = 0x13,     -- CHARACTER_ARTUR
        SAHNAR  = 0x16,     -- CHARACTER_MARISA
        RAVISIN = 0xb8,     -- the chapter boss
        MOOSE   = 0xb9,     -- the White Moose, ch04's payoff charging through scene 7
        LUPIN   = 0x1D,     -- CHARACTER_DUESSEL, the slot ch05 gives the wolf
    },

    -- The four reliquary doors: where they are, what each hands over, and the event id its
    -- Village macro sets. The tiles are the chapter YAML's `villages:` block
    -- (`check_declared_cases` proves a declared case cannot drift from it); the flags are
    -- CH05_VILLAGE_FLAGS in build_campaign, and they are what the save-all payout counts.
    RELIQUARIES = {
        { name = "north", x = 5,  y = 1,  item = 0x70, flag = 12 },   -- Torch
        { name = "west",  x = 5,  y = 6,  item = 0x5D, flag = 11 },   -- Secret Book
        { name = "east",  x = 12, y = 10, item = 0x0E, flag = 9  },   -- Armorslayer
        { name = "south", x = 12, y = 19, item = 0x60, flag = 10 },   -- Dracoshield
    },

    -- The save-all reward, paid only when all four flags above are set.
    REWARD = { GUIDING_RING = 0x68 },

    -- Message ids a BRANCH turns on. Box count cannot witness which arm played -- the Talk
    -- recruit's two arms are both 21 A-presses -- so a scenario asserts the id via
    -- INSPECT.activeMsg() instead (decisions.md -> "box count is no longer a witness").
    MSG = {
        RECRUIT_NO_LUPIN = 0x9D1,   -- the fallback arm: the wolf is absent, benched or dead
        ENDING_FULL      = 0x9C9,   -- Basil alive + Sahnar recruited
    },
}
