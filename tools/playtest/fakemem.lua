-- fakeMem() -> m: a table-backed, byte-true fake of the emulator's memory for the unit tests
-- (test_board.lua, test_sight.lua), so a halfword and the bytes inside it are one store, as in
-- the game. m.u8/s8/u16/u32 read, m.w8/w16/w32 write, all little-endian. The wider reads go
-- through m.u16, so a test may wrap it to count them.
return function()
    local bytes = {}
    local m = {}
    function m.u8(a) return bytes[a] or 0 end
    function m.s8(a) local v = m.u8(a); return v >= 0x80 and v - 0x100 or v end
    function m.u16(a) return m.u8(a) | (m.u8(a + 1) << 8) end
    function m.u32(a) return m.u16(a) | (m.u16(a + 2) << 16) end
    function m.w8(a, v) bytes[a] = v & 0xFF end
    function m.w16(a, v) m.w8(a, v); m.w8(a + 1, v >> 8) end
    function m.w32(a, v) m.w16(a, v); m.w16(a + 2, v >> 16) end
    return m
end
