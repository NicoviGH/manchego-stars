-- json.lua -- minimal pure-Lua JSON encode/decode for the sidecar handshake (#63 M2).
--
-- The harness exports the board as `req-<n>.json` and reads the sidecar's orders back
-- from `resp-<n>.json`; mGBA's embedded Lua ships no JSON library, so this is the pure
-- core for both directions, unit-tested without mGBA (test_json.lua). Deliberately a
-- SUBSET matching what the two ends of the protocol actually emit (Python `json.dumps`
-- output on the way in): objects, arrays, strings with standard escapes (incl. \uXXXX
-- basic-plane), numbers, true/false/null. Not a general validator -- decode returns
-- (nil, "reason") on anything it can't parse rather than guessing.
--
-- Conventions:
--   * encode() writes object keys SORTED, so the same table always produces the same
--     bytes (mirrors the sidecar's `sort_keys` serializer -- determinism doctrine).
--   * A table encodes as an array iff t[1] ~= nil, else as an object; the empty table
--     encodes as [] (the protocol has empty reach LISTS but no empty objects).
--   * decode() maps JSON null to Lua nil (the protocol never puts null inside arrays,
--     where nil would truncate the sequence).

local M = {}

-- ---------------------------------------------------------------- encode
local ESCAPES = {
    ['"'] = '\\"', ['\\'] = '\\\\', ['\b'] = '\\b', ['\f'] = '\\f',
    ['\n'] = '\\n', ['\r'] = '\\r', ['\t'] = '\\t',
}

local function encodeString(s)
    return '"' .. s:gsub('[%z\1-\31"\\]', function(c)
        return ESCAPES[c] or string.format('\\u%04x', c:byte())
    end) .. '"'
end

local function encodeNumber(n)
    if n ~= n or n == math.huge or n == -math.huge then
        error("json.encode: cannot encode nan/inf")
    end
    if math.type(n) == "integer" then return string.format("%d", n) end
    return string.format("%.14g", n)
end

local encodeValue

local function encodeTable(t)
    if t[1] ~= nil then                         -- array
        local parts = {}
        for i = 1, #t do parts[i] = encodeValue(t[i]) end
        return "[" .. table.concat(parts, ",") .. "]"
    end
    local keys = {}
    for k in pairs(t) do
        if type(k) ~= "string" then
            error("json.encode: object keys must be strings, got " .. type(k))
        end
        keys[#keys + 1] = k
    end
    if #keys == 0 then return "[]" end          -- empty table = empty array (see header)
    table.sort(keys)
    local parts = {}
    for i, k in ipairs(keys) do
        parts[i] = encodeString(k) .. ":" .. encodeValue(t[k])
    end
    return "{" .. table.concat(parts, ",") .. "}"
end

encodeValue = function(v)
    local ty = type(v)
    if v == nil then return "null"
    elseif ty == "boolean" then return v and "true" or "false"
    elseif ty == "number" then return encodeNumber(v)
    elseif ty == "string" then return encodeString(v)
    elseif ty == "table" then return encodeTable(v)
    end
    error("json.encode: cannot encode a " .. ty)
end

function M.encode(v) return encodeValue(v) end

-- ---------------------------------------------------------------- decode
-- Recursive descent over a position index. Each parser returns (value, nextPos) or
-- raises via error(msg, 0); M.decode wraps that into the (nil, reason) convention.

local function skipSpace(s, i)
    local _, j = s:find("^[ \t\r\n]*", i)
    return j + 1
end

local UNESCAPES = {
    ['"'] = '"', ['\\'] = '\\', ['/'] = '/', b = '\b', f = '\f',
    n = '\n', r = '\r', t = '\t',
}

local function parseString(s, i)               -- i sits on the opening quote
    local out, j = {}, i + 1
    while true do
        local c = s:sub(j, j)
        if c == "" then error("unterminated string at " .. i, 0) end
        if c == '"' then return table.concat(out), j + 1 end
        if c == "\\" then
            local e = s:sub(j + 1, j + 1)
            if e == "u" then
                local hex = s:sub(j + 2, j + 5)
                if not hex:match("^%x%x%x%x$") then
                    error("bad \\u escape at " .. j, 0)
                end
                out[#out + 1] = utf8.char(tonumber(hex, 16))
                j = j + 6
            elseif UNESCAPES[e] then
                out[#out + 1] = UNESCAPES[e]
                j = j + 2
            else
                error("bad escape '\\" .. e .. "' at " .. j, 0)
            end
        else
            out[#out + 1] = c
            j = j + 1
        end
    end
end

local function parseNumber(s, i)
    local numstr = s:match("^-?%d+%.?%d*[eE]?[+-]?%d*", i)
    local n = numstr and tonumber(numstr)
    if not n then error("bad number at " .. i, 0) end
    return n, i + #numstr
end

local parseValue

local function parseArray(s, i)                -- i sits on '['
    local out, j = {}, skipSpace(s, i + 1)
    if s:sub(j, j) == "]" then return out, j + 1 end
    while true do
        local v
        v, j = parseValue(s, j)
        out[#out + 1] = v
        j = skipSpace(s, j)
        local c = s:sub(j, j)
        if c == "]" then return out, j + 1 end
        if c ~= "," then error("expected ',' or ']' at " .. j, 0) end
        j = skipSpace(s, j + 1)
    end
end

local function parseObject(s, i)               -- i sits on '{'
    local out, j = {}, skipSpace(s, i + 1)
    if s:sub(j, j) == "}" then return out, j + 1 end
    while true do
        if s:sub(j, j) ~= '"' then error("expected object key at " .. j, 0) end
        local k, v
        k, j = parseString(s, j)
        j = skipSpace(s, j)
        if s:sub(j, j) ~= ":" then error("expected ':' at " .. j, 0) end
        v, j = parseValue(s, skipSpace(s, j + 1))
        out[k] = v
        j = skipSpace(s, j)
        local c = s:sub(j, j)
        if c == "}" then return out, j + 1 end
        if c ~= "," then error("expected ',' or '}' at " .. j, 0) end
        j = skipSpace(s, j + 1)
    end
end

parseValue = function(s, i)
    local c = s:sub(i, i)
    if c == "{" then return parseObject(s, i) end
    if c == "[" then return parseArray(s, i) end
    if c == '"' then return parseString(s, i) end
    if c == "t" and s:sub(i, i + 3) == "true" then return true, i + 4 end
    if c == "f" and s:sub(i, i + 4) == "false" then return false, i + 5 end
    if c == "n" and s:sub(i, i + 3) == "null" then return nil, i + 4 end
    if c == "-" or c:match("%d") then return parseNumber(s, i) end
    error("unexpected character '" .. c .. "' at " .. i, 0)
end

-- decode(s) -> value | (nil, reason). Trailing garbage after the value is an error
-- (a truncated/corrupt handshake file must not half-parse into plausible orders).
function M.decode(s)
    if type(s) ~= "string" then return nil, "not a string" end
    local ok, v, j = pcall(parseValue, s, skipSpace(s, 1))
    if not ok then return nil, v end
    if skipSpace(s, j) <= #s then return nil, "trailing garbage at " .. j end
    return v
end

return M
