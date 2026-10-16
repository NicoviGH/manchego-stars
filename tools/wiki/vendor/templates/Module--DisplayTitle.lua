local getArgs = require('Module:Arguments').getArgs
local p = {}

function p.italic(frame)
	local args = getArgs(frame)
	local output = ""
	local title = mw.title.getCurrentTitle()
	local namespacePrefix = title.nsText
	if namespacePrefix ~= "" then
		namespacePrefix = namespacePrefix .. ":"
	end
	local pageName = title.text
	if args[1] then
		local iterator = 1
		local modifiedPageName = pageName
		while args[iterator] do
			modifiedPageName = (string.gsub(modifiedPageName, args[iterator], "<i>" .. args[iterator] .. "</i>"))
			iterator = iterator + 1
		end
		output = namespacePrefix .. modifiedPageName
	else
		output = namespacePrefix .. "''" .. pageName .. "''"
	end
	return output
end

return p