-- Pure setup/cleanup lifecycle for cutscene recorders.
-- Keeping this independent of mGBA makes failure cleanup executable in plain Lua tests.
local M = {}

function M.runSetup(setup, cleanup)
    local setupCalled, setupOk, setupWhy = pcall(setup)
    local cleanupCalled, cleanupError = pcall(cleanup or function() end)

    if not setupCalled then
        return false, "setup error: " .. tostring(setupOk)
    end
    if not cleanupCalled then
        return false, "cleanup error: " .. tostring(cleanupError)
    end
    if setupOk == false then return false, setupWhy end
    return true, setupWhy
end

return M
