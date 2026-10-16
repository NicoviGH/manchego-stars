local getArgs = require('Module:Arguments').getArgs
local p = {}

function p.main(frame)
	local icons = mw.loadData("Module:IconTMS/Data")
	local carnageTable = mw.loadData("Module:Carnage/Data")
	local args = getArgs(frame)
	local thing = args[1]
	local icon = nil
	if icons[thing] then
		icon = icons[thing]
	elseif carnageTable[thing] then
		if carnageTable[thing]["type"] then
			icon = carnageTable[thing]["type"]
		end
	end
	if not icon then return "[[Category:Pages calling undefined TMSFE icon]]" end
	if icon == "dummy" then return "[[Category:Pages calling TMSFE icon that needs filling]]" end
	
	output = "[[File:Is tmsfe " .. icon .. ".png|20px|class=center-icons|link=]]"
	return output
end

return p