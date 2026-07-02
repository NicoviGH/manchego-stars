-- Tests for json.lua -- the sidecar-handshake JSON encode/decode core (no emulator).
-- Run: lua tools/playtest/test_json.lua
local here = (arg[0]:match("(.*/)")) or "./"
local J = dofile(here .. "json.lua")

local tests, fails = 0, 0
local function check(got, want, msg)
    tests = tests + 1
    if got ~= want then
        fails = fails + 1
        print(string.format("FAIL: %s\n  got  %s\n  want %s", msg, tostring(got), tostring(want)))
    end
end

-- ---- encode -----------------------------------------------------------------
check(J.encode(nil), "null", "encode nil")
check(J.encode(true), "true", "encode true")
check(J.encode(false), "false", "encode false")
check(J.encode(42), "42", "encode integer")
check(J.encode(-7), "-7", "encode negative integer")
check(J.encode(1.5), "1.5", "encode float")
check(J.encode("hi"), '"hi"', "encode plain string")
check(J.encode('a"b\\c\nd'), '"a\\"b\\\\c\\nd"', "encode escapes")
check(J.encode({}), "[]", "empty table encodes as empty array")
check(J.encode({ 1, 2, 3 }), "[1,2,3]", "encode array")
check(J.encode({ { 3, 4 }, { 5, 4 } }), "[[3,4],[5,4]]", "encode nested array (reach list)")

-- object keys come out SORTED, so identical tables give identical bytes
check(J.encode({ b = 1, a = 2 }), '{"a":2,"b":1}', "object keys are sorted")
check(J.encode({ move_to = { x = 5, y = 4 }, unit = 17 }),
    '{"move_to":{"x":5,"y":4},"unit":17}', "encode a nested order shape")

-- deterministic: two insertion orders, same bytes
do
    local a = { seed = 1, turn = 2, faction = "blue" }
    local b = { faction = "blue", seed = 1, turn = 2 }
    check(J.encode(a), J.encode(b), "encode is insertion-order independent")
end

-- non-encodable values fail loudly, not silently
check(pcall(J.encode, { f = print }), false, "encoding a function errors")
check(pcall(J.encode, { [1.5] = "x", x = 1 }), false, "non-string object key errors")
check(pcall(J.encode, 0 / 0), false, "encoding nan errors")

-- ---- decode -----------------------------------------------------------------
do
    local v = J.decode('{"orders":[{"unit":17,"move_to":{"x":5,"y":4},"action":"attack","target":104}]}')
    check(v ~= nil, true, "decode a response shape")
    check(v.orders[1].unit, 17, "decode order unit id")
    check(v.orders[1].move_to.x, 5, "decode nested move_to.x")
    check(v.orders[1].action, "attack", "decode action string")
    check(v.orders[1].target, 104, "decode target id")
end

check(J.decode("[]")[1], nil, "decode empty array")
check(#J.decode("[1,2,3]"), 3, "decode array length")
check(J.decode("-12"), -12, "decode negative number")
check(J.decode("2.5e2"), 250.0, "decode exponent float")
check(J.decode('"a\\nb"'), "a\nb", "decode newline escape")
check(J.decode('"\\u0041"'), "A", "decode unicode escape")
check(J.decode('  { "a" : [ 1 , 2 ] }  ').a[2], 2, "whitespace tolerated everywhere")
check(J.decode('{"a":null,"b":1}').a, nil, "null decodes to nil object value")
check(J.decode('{"a":null,"b":1}').b, 1, "sibling of a null survives")
check(J.decode('{"a":true,"b":false}').b, false, "decode booleans")

-- round trip: encode -> decode reproduces the structure
do
    local board = {
        map = { w = 15, h = 10 },
        units = {
            { id = 17, x = 3, y = 4, hp = 18, can_act = true, reach = { { 3, 4 }, { 4, 4 } } },
            { id = 1104, x = 6, y = 4, hp = 22, can_act = false, boss = true, reach = {} },
        },
    }
    local rt = J.decode(J.encode(board))
    check(rt.map.w, 15, "round trip map width")
    check(rt.units[1].reach[2][1], 4, "round trip nested reach pair")
    check(rt.units[2].boss, true, "round trip boolean")
    check(#rt.units[2].reach, 0, "round trip empty reach")
    check(J.encode(rt), J.encode(board), "re-encode is byte-identical")
end

-- corrupt input -> (nil, reason), never a half-parsed value
do
    local v, err = J.decode('{"orders":[{"unit":17')
    check(v, nil, "truncated JSON returns nil")
    check(err ~= nil, true, "truncated JSON returns a reason")
end
do
    local v, err = J.decode('{"a":1} trailing')
    check(v, nil, "trailing garbage returns nil")
    check(err and err:match("trailing") ~= nil, true, "trailing garbage names the reason")
end
check(J.decode("nope"), nil, "non-JSON text returns nil")
check(J.decode(nil), nil, "non-string input returns nil")
check(J.decode('{"a" 1}'), nil, "missing colon returns nil")
check(J.decode("[1,2,"), nil, "unclosed array returns nil")

if fails == 0 then
    print(string.format("ok -- %d assertions", tests))
    os.exit(0)
end
print(string.format("%d/%d FAILED", fails, tests))
os.exit(1)
