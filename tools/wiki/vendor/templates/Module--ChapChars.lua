local p = {}

function p.returning(frame)
	-- Naming the input
	local in_args = frame:getParent().args
	
	-- Determines whether or not to use "small"
	local size = ""; num = 0; pixels = "x80"
	local game = tostring(in_args["game#"])
	if game:find("%c", -1) ~= nil then -- if game ends with a control character
		game = game:sub(1, -2)
	end
	
	if tonumber(game) ~= nil then -- if the game is set as a number
		num = tonumber(game)
	end
	if num > 0 then -- if num was set, or game is set to "wa"
		game = "fe" .. game
	end
	
	local saga = ""
	if game:sub(1, 3) == "trs" or game:sub(1, 2) == "vs" then -- if the set game starts with "trs" or "vs"
		saga = "Saga:"
	end
	
	if num == 18 then
		size = "Medium "
	elseif num > 5 or game:sub(1, 3) == "trs" or game == "fewa2" then -- games that use small portraits; 1–5 and Warriors are false, 6–16 and TRS are true
		size = "Small "
	end
	
	if num == 17 then
		pixels = "100"
	end
	
	-- Begins construction of output
	local args = {}; images = {}; links = {}; alts = {}
	local hdr = "[[File:" .. size .. "portrait " -- Start of an image link
	local link = " " .. game .. ".png|link=" -- Middle portion of an image link
	local ftr = "|" .. pixels .. "px]]" -- End of link
	local output = hdr -- starts output with header value
	local i = 0
	
	-- loops through the input and turns it into a list of images and one of links
	for k, v in pairs(in_args) do
		if k:sub(1,6) == "return" then -- if first six characters are "return"
			i = tonumber(k:match("%d+"))
			
			if v:find("%c", -1) ~= nil then -- if an input ends with a control character
				v = v:sub(1, -2) -- removes last character
			end
			
			if tostring(k):sub(-7) == "article" then -- checks if last seven characters are "article"
				links[i] = v
			elseif tostring(k):sub(-3) == "alt" then
				alts[i] = v
			else
				images[i] = mw.ustring.lower(v)
				if links[i] == nil then -- checks if the corresponding link already exists
					links[i] = saga .. v
				end
				if alts[i] == nil then
					alts[i] = v:sub(1, 1):upper() .. v:sub(2)
				end
			end
		end
	end
	
	if images[1] == nil then -- true if images[1] is empty, which should only happen if return1 is not set
		return "None" -- ends the program
	end
	
	-- Turns the previous two lists into one list of partial links
	for k in pairs(images) do
		args[k] = images[k] .. link .. links[k] .. "|" .. alts[k] .. " &#8203;" -- creates the middle portion of the link
	end
	
	-- takes list created above and turns it into useable wikitext
	output = output .. table.concat(args, ftr .. hdr)
	
	-- returns completed image set
	return output .. ftr
end

function p.newunits(frame)
	-- Naming input to be more convinient
	local in_args = frame:getParent().args
	
	local units = {} -- variabe that will contain every "newunit#" field
	
	-- Checks input for newunit fields
	for k, v in pairs(in_args) do
		if tostring(k):find("newunit%d+") ~= nil then
			units[tonumber(k:sub(8))] = v
		end
	end
	
	if #units == 0 then -- if there are no new units
		return "|\nNone"
	end
	
	local rowbreak = 3
	
	if in_args[rowbreak] ~= nil then -- if rowbreak is set in the page
		rowbreak = in_args[rowbreak]
	elseif #units == 4 then -- if there are four new units
		rowbreak = 2
	end
	--[[rowbreak determines were new rows are made: breaks after the third unit,
		except when there are four units where it breaks after the second.]]
	
	local output = ""
	
	for k, v in ipairs(units) do -- assembles output
		output = output .. "|\n" .. v .. "\n"
		if k % rowbreak == 0 then -- adds new rows
			output = output .. "|-\n"
		end
	end
	
	return output
end

function p.oldunits(frame)
	-- Naming the input
	local in_args = frame:getParent().args
	
	local size = ""; num = 0; pixels = "x80"; transform = ""
	local game = tostring(in_args["game#"])
	
	if game:find("%c", -1) ~= nil then -- if game ends with a control character
		game = game:sub(1, -2) -- removes control character
	end
	
	if game == 'feh' or game == 'fesh' then
		return ''
	end
	
	if tonumber(game) ~= nil then -- if the game is set as a number
		num = tonumber(game) -- sets a number field for convinience
	end
	
	if num > 0 then -- if num was set, or game is set to "wa"
		game = "fe" .. game -- sets "game" to use the number for portraits
	end
	
	local saga = ""
	-- if the set game starts with "trs" or "vs"
	if game:sub(1, 3) == "trs" or game:sub(1, 2) == "vs" then 
		saga = "Saga:" -- link to Saga namespace
	end
	
	if game == "trs01" then -- if the game is TRS1
		-- sets transform css used for TRS1 portraits
		transform = " ps1-scale"
	end
	
	--[[games that use small portraits;
		1–5 and Warriors are false, 6–16 and TRS1 are true]]
	if num == 18 then
		size = "Medium "
	elseif num > 5 or game == "trs01" or game == "fewa2" then
		size = "Small "
	end
	
	--if game is Engage
	if num == 17 then
		pixels = "100" -- sets width of 100 px rather than height of 80
	end
	
	-- Begins construction of output
	-- arrays for required, available and undeployable characters
	local forceds = {}; returns = {}; nodeploys = {}
	
	-- look-up table for arrays
	local a_tab = {
		["return"] = returns,
		["forced"] = forceds,
		["nodepl"] = nodeploys
	}
	
	local hdr = "[[File:" .. size .. "portrait " -- Start of an image link
	local link = " " .. game .. ".png|link=" -- Middle portion of an image link
	local ftr = "|" .. pixels .. "px]]" -- End of link
	local output = '' -- empty start to output
	-- Common element for headers; text set later
	local cellh = "! <div class=\"round\" style=\"margin: auto; " ..
		"border: 1px solid {{Color2}}; background: {{Color1}}; width: 66%; " ..
		"padding: 3px\">"
	-- common element for cells
	local cellc = "| class=\"round" .. transform .. "\"" .. "style=\"padding: 1em; border: 1px solid #b0b0b0" .. "\" | "
		
	--[[ variables used for the loop:
		i is the number of the field (e.g. "return1" gives 1)
		j is the name of the field (e.g. "return1" gives "return")
		active is the active array (e.g. "return1" uses the returns array)]]
	local i = 0; j = ''; active = {}
	
	--[[loops through the input,
		sorts it into the required, available, and undeployable characters]]
	for k, v in pairs(in_args) do
		i = tonumber(k:match("%d+")) -- field number
		j = k:sub(1,6) -- field name
		
		if v:find("%c", -1) ~= nil then -- if an input ends with a control character
			v = v:sub(1, -2) -- removes last character
		end
		
		active = a_tab[j]
		
		if active ~= nil then
			if active[i] == nil then 
				active[i] = {} -- sets a sub-table if one does not already exist
			end
			
			-- checks if last seven characters are "article"
			if tostring(k):sub(-7) == "article" then
				active[i][2] = v -- sets a unique link for this image
			-- checks if last three characters are "alt"
			elseif tostring(k):sub(-3) == "alt" then
				active[i][3] = v -- sets unique alt text for this image
			else -- if the other two are false, the image set must be left
				active[i][1] = mw.ustring.lower(v) -- sets image
				
				-- checks if the corresponding link already exists
				if active[i][2] == nil then
					active[i][2] = saga .. v -- sets link to same value as image
				end
				
				-- checks if the corresponding alt already exists
				if active[i][3] == nil then
					-- sets atl to same value as image
					active[i][3] = v:sub(1, 1):upper() .. v:sub(2)
				end
			end
		end
		j = nil -- resets j so inapplicable fields don't slip through
	end
	
	-- sets up empty outputs for required, available, and undeployable units
	local outf = ''; outr = ''; outn = ''
	
	if forceds[1] ~= nil then -- if first required character doesn't exist
		for k in ipairs(forceds) do
			-- assembles required units part of output
			outf = outf .. hdr .. forceds[k][1] .. link .. forceds[k][2] ..
			"|" .. forceds[k][3] .. " &#8203;" .. ftr
		end
	end
	
	if returns[1] ~= nil then -- if first available character doesn't exist
		for k in ipairs(returns) do
			-- assembles available units part of output
			outr = outr .. hdr .. returns[k][1] .. link .. returns[k][2] ..
			"|" .. returns[k][3] .. " &#8203;" .. ftr
		end
	else
		outr = "None"
	end
	
	if nodeploys[1] ~= nil then -- if first undeployable character is nil
		for k in ipairs(nodeploys) do
			-- assembles undeployable units part of output
			outn = outn .. hdr .. nodeploys[k][1] .. link .. nodeploys[k][2] ..
			"|" .. nodeploys[k][3] .. " &#8203;" .. ftr
		end
	end
	
	if outf ~= '' then -- places required characters in output, if they exist
		output = cellh .. "Forcibly deployed characters</div>" .. "\n|-\n" ..
		cellc .. outf .. "\n|-\n"
	end
	
	-- places available characters in output
	output = output .. cellh .. "Available characters</div>" .. "\n|-\n" ..
		cellc .. outr .. "\n|-\n"
	
	-- places undeployable characters in output, if they exist
	if outn ~= '' then
		output = output .. cellh .. "Undeployable characters</div>" .. "\n|-\n" ..
		cellc .. outn
	end
	
	-- returns completed image set
	return output
end

return p