local getArgs = require('Module:Arguments').getArgs
local p = {}


--[[
Get the game's platform code from its number.
]]
function p.convertPlatform(platInput)
	local g_platform = {
		["fe06"] = "gba",
		["fe07"] = "gba",
		["fe08"] = "gba",
		["fe09"] = "gcn",
		["fe10"] = "wii",
		["fe11"] = "ds",
		["fe12"] = "ds",
		["trs1"] = "ps1",
		["trs01"] = "ps1",
		["trs2"] = "ps2",
		["trs02"] = "ps2"
	}

	local game_no = ""
	if tonumber(platInput) then
		game_no = string.format("fe%02d",tonumber(platInput))
	else
		game_no = platInput
	end
	if( g_platform[game_no] == nil ) then
		return game_no
	else
		return g_platform[game_no]
	end
end

function p.PlatformGame(frame)
	local args = getArgs(frame)
	return p.convertPlatform(args[1])	
end

function p.main(frame)
	local args = getArgs(frame)
	local usesSagaNamespace = {
		["ps1"] = true,
		["ps2"] = true,
		["vs1"] = true,
		["vs2"] = true
	}
	local imageSizes = {
		["fe16"] = "|x20px",
		["fewa"] = "|x20px",
		["fewa2"] = "|x20px",
		["fe17"] = "|x24px",
		["fe18"] = "|x20px",
		["fesh"] = "|x32px",
		["tmsfe"] = "|x20px|class=center-icons"
	}
	local platform = p.convertPlatform(args[1])
	local itemName = args[2]
	local linkTarget = args["link"] or args[2]
	local noLink = args["nolink"]
	local noImage = args["noimage"]
	if usesSagaNamespace[platform] then linkTarget = "Saga:" .. linkTarget end
	local imageName = args["image"] or itemName
	local itemImage = ""
	if noLink then
		linkTarget = ""
	end
	if platform == "tmsfe" and not args["image"] then
		itemImage = frame:expandTemplate{ title = 'TMS icon', args = { itemName } } .. " "
	elseif platform ~= "fe01" and not noImage then
		itemImage = string.format("[[File:Is %s %s.png%s|alt=|link=%s]]&nbsp;", platform, mw.ustring.lower(imageName), imageSizes[platform] or "", linkTarget)
	end
	local link = ""
	local defaultLinkColor = {
		["drop"] = "var(--default-item-drop-color)", --#0f0 on dark mode, #1E8200 (Awakening's color) on light mode
		["forged"] = "#45d0f0"
	}
	local customLinkColor = {
		["drop"] = {
			["gcn"] = "#ff8080",
			["wii"] = "#ff8080"
		},
		["forged"] = {
			["gcn"] = "var(--default-item-drop-color)",
			["wii"] = "var(--default-item-drop-color)"
		}
	}
	local defaultTypeImage = {
		["drop"] = "[[File:SNESItemDrop.png|",
		["forged"] = "[[File:3DSForge.png|14px|class=drop-icon|"
	}
	local customTypeImage = {
		["drop"] = {
			["fe16"] = "[[File:Is fe16 drop.png|x12px|class=drop-icon|",
			["fewa2"] = "[[File:Is fewa2 drop.png|x12px|class=drop-icon|",
			["fe17"] = "[[File:Is fe17 drop.png|x12px|class=drop-icon light-mode-drop-shadow|"
		},
		["forged"] = {
		}
	}
	local imageSuffix = {
		["drop"] = "link=Inventory#Droppable items|This item is dropped upon this unit's defeat.]]",
		["forged"] = "link=Forge|This weapon is forged and has boosted stats.]]"
	}

	local type = args["type"]
	if not noLink then
		if type == "drop" or type == "forged" then
			link = string.format("%s%s",frame:expandTemplate{ title = 'Colored link', args = { customLinkColor[type][platform] or defaultLinkColor[type], linkTarget, itemName } }, string.format("%s%s", customTypeImage[type][platform] or defaultTypeImage[type], imageSuffix[type]))
		else
			link = string.format("[[%s|%s]]", linkTarget, itemName)
		end
	else
		if type == "drop" or type == "forged" then
			link = string.format("%s%s",frame:expandTemplate{ title = 'Color', args = { customLinkColor[type][platform] or defaultLinkColor[type], itemName } }, string.format("%s%s", customTypeImage[type][platform] or defaultTypeImage[type], imageSuffix[type]))
		else
			link = string.format("%s", itemName)
		end
	end
	local lockImage = ""
	if args["lock"] then
		lockImage = "[[File:WiiLock.png|14px|link=Inventory#Locked items|This item or skill is locked to this unit.]]"
	end
	return itemImage .. link .. lockImage
end

return p