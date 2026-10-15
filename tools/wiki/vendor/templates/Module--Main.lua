local p = {}

function p.main(frame)
	-- Name input for convenience
	local in_args = frame:getParent().args
	-- Start building output
	local args = {}
	local output = ""; i = ""
	
	-- Loop through input
	for k, v in pairs(in_args) do
		if type(k) == "number" then --if the field is a number
			if args[k] == nil then --if the sub-table has not been made
				args[k] = {}
			end
			
			-- changes any pipe magic words into pipe characters, and underscores to spaces
			v = v:gsub("{{!}}", "|"):gsub("_", " ")
			
			args[k][1] = v:match("^[^|]+") -- sets input as link before pipe
			
			if args[k][2] == nil then -- if display text has not been set
				--[[ sets display text as link text
				replaces # in display with § (except ones in character escape sequences &#)
				only displays characters after a pipe set in the link
				removes / at the start or end of a link]]
				args[k][2] = v:gsub("(?<!&) *# *", " § ", 1):match("[^\|]+$"):gsub("^/", ""):gsub("/$", "")
			end
		elseif type(k) == "string" and k:sub(1,1) == "l" then -- if field is "l#", the only other type that should be used
			i = tonumber(k:sub(2))
			
			if args[i] == nil then --if the sub-table has not been made
				args[i] = {}
			end
			
			args[i][2] = v
		end
	end
	
	for k, v in pairs(args) do -- assembles links
		args[k] = "[[" .. args[k][1] .. "|''<wbr>" .. args[k][2] .. "<wbr>'']]"
	end
	
	-- Turns the list from above into links, and appends to output
	if #args == 1 then
		output = output .. args[1]
	elseif #args == 2 then
		output = output .. table.concat(args, "'' and ''")
	else
		output = output .. mw.text.listToText(args, "'', ''", "'', and ''")
	end
	
	-- Return completed list of articles
	return output
end

return p