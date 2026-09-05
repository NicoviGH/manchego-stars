-- ch06.lua -- ch06's chapter-scoped playtest facts, in ITS OWN chunk (#314).
--
-- Same reason ch05.lua exists: harness.lua is one chunk at Lua's 200-local ceiling, so a
-- chapter's facts live in a chapter chunk with its own fresh budget and are `dofile`d INSIDE
-- the scenario that needs them (function-scoped, costing harness.lua no top-level slot).
-- `LUA_CHUNKS` is globbed, so `check_lua_chunks_load` covers this file the day it exists.
--
-- WHAT BELONGS HERE: facts about ch06 that a scenario reads and the chapter YAML declares --
-- the two hulls, the two pursuers, and the ONE ground cell each hull can be swung at from.
-- `check_ch06_lua_matches_yaml` pins every coordinate and pid below against
-- `ch06-the-maer-monster.yaml`, so this file cannot drift into asserting a map we do not ship.
return {
    -- The two marooned boats: GREEN CLASS_FLEET units on raw pids of our own
    -- (CH06_BOAT_PIDS in build_campaign). `door` is the single ground cell adjacent to the
    -- hull -- the pocket's only entrance, and the whole subject of ch06clock.
    --
    -- `sinks_on` is the chapter YAML's DECLARED fuse. It is logged, never asserted: the fuse
    -- is a hit rate, not a turn number (see the scenario's header), so a single run is one
    -- sample of a distribution and an equality check on it would be a coin-flip verdict.
    BOATS = {
        { id = "boat-east", pid = 0xbb, x = 17, y = 12, doorX = 17, doorY = 13, sinks_on = 7 },
        { id = "boat-west", pid = 0xbc, x = 4,  y = 17, doorX = 4,  doorY = 18, sinks_on = 8 },
    },

    -- The two pursuers, by the tile each STARTS on. Every ch06 enemy is the same generic pid
    -- (CH06_GENERIC_PID 0x80), so a pursuer cannot be found by charId -- it is identified by
    -- its turn-1 position and then tracked by its index in gUnitArrayRed, which is stable.
    --
    -- They are deliberately different problems. The crab is range 1, so it must OCCUPY the
    -- door; the thrower is range 1-2, so the pocket never stops it and it has to be killed.
    PURSUERS = {
        { id = "merfolk-thrower", boat = "boat-east", x = 14, y = 9,  range = 2 },
        { id = "ice-crab",        boat = "boat-west", x = 7,  y = 20, range = 1 },
    },
}
