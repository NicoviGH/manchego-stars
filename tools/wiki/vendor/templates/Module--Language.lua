local getArgs = require('Module:Arguments').getArgs
local p = {}
local languageTable = mw.loadData("Module:Language/Subtags").languageTable
local scriptTable = mw.loadData("Module:Language/Subtags").scriptTable

function p.lang(frame)
	local args = getArgs(frame)
	local language = args[1]
	local text = args[2] or ""
	local romanization = args[3]
	local isHoverLang = args["hl"]
	local script = ""
	local direction = ""
	local manualScript = ""
	local baseLanguage = ""
	if language:match("%u%l%l%l") then
		manualScript = language:match("%u%l%l%l")
		if scriptTable[manualScript] then
			baseLanguage = (string.gsub(baseLanguage,"-"..script,""))
			script = manualScript
			if scriptTable[script]["dir"] == "vertical-lr" or scriptTable[script]["dir"] == "vertical-rl" or scriptTable[script]["dir"] == "sideways-lr" then
				direction = ' style="writing-mode: ' .. scriptTable[script]["dir"] .. '"'
			elseif scriptTable[script]["dir"] == "rtl" then
				direction = ' dir="' .. scriptTable[script]["dir"] .. '"'
			end
		else
			baseLanguage = (string.gsub(baseLanguage,"-"..script,""))
			script = manualScript
			text = text .. "[[Category:Pages with invalid scripts in Lang template]]"
		end
	elseif languageTable[language] then
		baseLanguage = language
		if languageTable[language]["defaultScript"] then
			script = languageTable[language]["defaultScript"]
			if scriptTable[script] then
				if scriptTable[script]["dir"] then
					if scriptTable[script]["dir"] == "vertical-lr" or scriptTable[script]["dir"] == "vertical-rl" or scriptTable[script]["dir"] == "sideways-lr" then
						direction = ' style="writing-mode: ' .. scriptTable[script]["dir"] .. '"'
					elseif scriptTable[script]["dir"] == "rtl" then
						direction = ' dir="' .. scriptTable[script]["dir"] .. '"'
					end
				end
				if not languageTable[language]["suppressScript"] then
					language = language .. "-" .. script
				end
			end
		end
	end
	local hoverLangText = nil
	if isHoverLang and romanization then
		hoverLangText = ' class="explain tooltips" title="' .. romanization .. '"'
	end
	local romanizedText = nil
	if romanization and not isHoverLang then
		romanizedText = " ''<span lang=\"".. baseLanguage .. "-Latn" .. "\">" .. romanization .. "</span>''"
	end
	local output = string.format('<span%s lang="%s"%s>%s</span>%s',hoverLangText or "",language,direction,text,romanizedText or "")
	return output
end

return p