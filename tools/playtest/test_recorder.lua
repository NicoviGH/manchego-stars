-- Tests for recorder.lua -- setup/cleanup lifecycle without an emulator.
-- Run: lua tools/playtest/test_recorder.lua
local here = (arg[0]:match("(.*/)")) or "./"
local Recorder = dofile(here .. "recorder.lua")

local tests, fails = 0, 0
local function check(got, want, msg)
    tests = tests + 1
    if got ~= want then
        fails = fails + 1
        print(string.format("FAIL: %s\n  got  %s\n  want %s", msg, tostring(got), tostring(want)))
    end
end

local trace = {}
local ok, why = Recorder.runSetup(function()
    trace[#trace + 1] = "setup"
    return true
end, function() trace[#trace + 1] = "cleanup" end)
check(ok, true, "successful setup stays successful")
check(why, nil, "successful setup has no reason")
check(table.concat(trace, ","), "setup,cleanup", "cleanup follows successful setup")

trace = {}
ok, why = Recorder.runSetup(function()
    trace[#trace + 1] = "setup"
    -- Existing pre-steps predate the result contract and return nil on success.
end, function() trace[#trace + 1] = "cleanup" end)
check(ok, true, "legacy nil setup result is normalized to success")
check(why, nil, "legacy setup has no failure reason")
check(table.concat(trace, ","), "setup,cleanup", "cleanup follows a legacy setup")

trace = {}
ok, why = Recorder.runSetup(function()
    trace[#trace + 1] = "setup"
    return false, "could not reach the clearing"
end, function() trace[#trace + 1] = "cleanup" end)
check(ok, false, "failed setup stays failed")
check(why, "could not reach the clearing", "failed setup preserves its reason")
check(table.concat(trace, ","), "setup,cleanup", "cleanup follows failed setup")

trace = {}
ok, why = Recorder.runSetup(function()
    trace[#trace + 1] = "setup"
    error("setup exploded")
end, function() trace[#trace + 1] = "cleanup" end)
check(ok, false, "setup exception becomes an immediate failure")
check(tostring(why):match("setup exploded") ~= nil, true, "setup exception keeps its message")
check(table.concat(trace, ","), "setup,cleanup", "cleanup follows a setup exception")

if fails > 0 then
    print(string.format("%d/%d assertions failed", fails, tests))
    os.exit(1)
end
print(string.format("ok -- %d assertions", tests))
