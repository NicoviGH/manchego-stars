local languageTable = {
	["aa"] = { --Afar
		defaultScript = "Latn"
	},
	["ab"] = { --Abkhazian
		defaultScript = "Cyrl",
		suppressScript = true
	},
	["ae"] = { --Avestan
		defaultScript = "Avst"
	},
	["af"] = { --Afrikaans
		defaultScript = "Latn",
		suppressScript = true
	},
	["ain"] = { --Ainu (Japan)
		defaultScript = "Kana"
	},
	["ak"] = { --Akan
		--Macrolanguage
		defaultScript = "Latn"
	},
	["akk"] = { --Akkadian
		defaultScript = "Xsux"
	},
	["alq"] = { --Algonquin
		defaultScript = "Latn"
	},
	["am"] = { --Amharic
		defaultScript = "Ethi",
		suppressScript = true
	},
	["an"] = { --Aragonese
		defaultScript = "Latn"
	},
	["ang"] = { --Old English (ca. 450-1100)
		defaultScript = "Latn"
	},
	["ar"] = { --Arabic
		--Macrolanguage
		defaultScript = "Arab",
		suppressScript = true
	},
	["arb"] = { --Standard Arabic
		--Parent: ar
		defaultScript = "Arab"
	},
	["arc"] = { --Official Aramaic (700-300 BCE), Imperial Aramaic (700-300 BCE)
		defaultScript = "Armi",
	},
	["as"] = { --Assamese
		defaultScript = "Beng",
		suppressScript = true
	},
	["av"] = { --Avaric
		defaultScript = "Cyrl"
	},
	["ay"] = { --Aymara
		--Macrolanguage
		defaultScript = "Latn",
		suppressScript = true
	},
	--["az"] = { --Azerbaijani
		--Macrolanguage
		----wikipediaArticle = "Azerbaijani language",
		--defaultScript = "Latn"
	--},
	["azb"] = { --South Azerbaijani
		--Parent: az
		defaultScript = "Arab"
	},
	["azj"] = { --North Azerbaijani
		--Parent: az
		defaultScript = "Latn"
	},
	["ba"] = { --Bashkir
		defaultScript = "Cyrl"
	},
	["ban"] = { --Balinese
		defaultScript = "Latn"
	},
	["be"] = { --Belarusian
		defaultScript = "Cyrl",
		suppressScript = true
	},
	["bg"] = { --Bulgarian
		defaultScript = "Cyrl",
		suppressScript = true
	},
	["bho"] = { --Bhojpuri
		defaultScript = "Deva"
	},
	["bi"] = { --Bislama
		defaultScript = "Latn"
	},
	["bm"] = { --Bambara
		defaultScript = "Latn"
	},
	["bn"] = { --Bengali, Bangla
		defaultScript = "Beng",
		suppressScript = true
	},
	["bo"] = { --Tibetan
		defaultScript = "Tibt"
	},
	["br"] = { --Breton
		defaultScript = "Latn"
	},
	["bs"] = { --Bosnian
		--Parent: sh
		defaultScript = "Latn",
		suppressScript = true
	},
	["bua"] = { --Buriat
		--Macrolanguage
		defaultScript = "Cyrl",
		suppressScript = true
	},
	["ca"] = { --Catalan, Valencian
		defaultScript = "Latn",
		suppressScript = true
	},
	["ce"] = { --Chechen
		defaultScript = "Cyrl"
	},
	["ceb"] = { --Cebuano
		defaultScript = "Latn"
	},
	["ch"] = { --Chamorro
		defaultScript = "Latn",
		suppressScript = true
	},
	["ckb"] = { --Central Kurdish
		--Parent: ku
		defaultScript = "Arab"
	},
	["cls"] = { --Classical Sanskrit
		--Parent: sa
		defaultScript = "Deva"
	},
	["cmg"] = { --Classical Mongolian
		defaultScript = "Mong"
	},
	["cmn"] = { --Mandarin Chinese
		--Parent: zh
		defaultScript = "Hani"
	},
	["co"] = { --Corsican
		defaultScript = "Latn"
	},
	["cop"] = { --Coptic
		defaultScript = "Copt"
	},
	["cr"] = { --Cree
		--Macrolanguage
		defaultScript = "Cans"
	},
	["cs"] = { --Czech
		defaultScript = "Latn",
		suppressScript = true
	},
	["cu"] = { --Church Slavic, Church Slavonic, Old Bulgarian, Old Church Slavonic, Old Slavonic
		defaultScript = "Cyrl"
	},
	["cv"] = { --Chuvash
		defaultScript = "Cyrl"
	},
	["cy"] = { --Welsh
		defaultScript = "Latn",
		suppressScript = true
	},
	["da"] = { --Danish
		defaultScript = "Latn",
		suppressScript = true
	},
	["dak"] = { --Dakota
		defaultScript = "Latn"
	},
	["de"] = { --German
		defaultScript = "Latn",
		suppressScript = true
	},
	["dji"] = { --Djinang
		defaultScript = "Latn"
	},
	["djr"] = { --Djambarrpuyngu
		defaultScript = "Latn"
	},
	["dv"] = { --Dhivehi, Divehi, Maldivian
		defaultScript = "Thaa",
		suppressScript = true
	},
	["dz"] = { --Dzongkha
		defaultScript = "Tibt",
		suppressScript = true
	},
	["ee"] = { --Ewe
		defaultScript = "Latn"
	},
	["egy"] = { --Egyptian (Ancient)
		defaultScript = "Egyp"
	},
	["ekk"] = { --Standard Estonian
		--Parent: et
		defaultScript = "Latn"
	},
	["el"] = { --Modern Greek (1453-)
		defaultScript = "Grek",
		suppressScript = true
	},
	["en"] = { --English
		defaultScript = "Latn",
		suppressScript = true
	},
	["eo"] = { --Esperanto
		defaultScript = "Latn",
		suppressScript = true
	},
	["es"] = { --Spanish, Castilian
		defaultScript = "Latn",
		suppressScript = true
	},
	["et"] = { --Estonian
		--Macrolanguage
		defaultScript = "Latn",
		suppressScript = true
	},
	["eu"] = { --Basque
		defaultScript = "Latn",
		suppressScript = true
	},
	["fa"] = { --Persian
		--Macrolanguage
		defaultScript = "Arab",
		suppressScript = true
	},
	["fat"] = { --Fanti
		--Parent: ak
		defaultScript = "Latn"
	},
	["ff"] = { --Fulah
		--Macrolanguage
		defaultScript = "Latn"
	},
	["fi"] = { --Finnish
		defaultScript = "Latn",
		suppressScript = true
	},
	["fil"] = { --Filipino, Pilipino
		defaultScript = "Latn"
	},
	["fj"] = { --Fijian
		defaultScript = "Latn",
		suppressScript = true
	},
	["fo"] = { --Faroese
		defaultScript = "Latn",
		suppressScript = true
	},
	["fr"] = { --French
		defaultScript = "Latn",
		suppressScript = true
	},
	["frm"] = { --Middle French (ca. 1400-1600)
		defaultScript = "Latn"
	},
	["fro"] = { --Old French (842-ca. 1400)
		defaultScript = "Latn"
	},
	["fy"] = { --Western Frisian
		defaultScript = "Latn",
		suppressScript = true
	},
	["ga"] = { --Irish
		defaultScript = "Latn",
		suppressScript = true
	},
	["gd"] = { --Scottish Gaelic, Gaelic
		defaultScript = "Latn"
	},
	["gem"] = { --Germanic languages
		--Collection
		defaultScript = "Latn"
	},
	["gez"] = { --Geez
		defaultScript = "Ethi"
	},
	["gl"] = { --Galician
		defaultScript = "Latn",
		suppressScript = true
	},
	["gmh"] = { --Middle High German (ca. 1050-1500)
		defaultScript = "Latn"
	},
	["gn"] = { --Guarani
		--Macrolanguage
		defaultScript = "Latn",
		suppressScript = true
	},
	["goh"] = { --Old High German (ca. 750-1050)
		defaultScript = "Latn"
	},
	["got"] = { --Gothic
		defaultScript = "Goth"
	},
	["grc"] = { --Ancient Greek (to 1453)
		defaultScript = "Grek"
	},
	["gu"] = { --Gujarati
		defaultScript = "Gujr",
		suppressScript = true
	},
	["gv"] = { --Manx
		defaultScript = "Latn",
		suppressScript = true
	},
	["ha"] = { --Hausa
		defaultScript = "Latn"
	},
	["hbo"] = { --Ancient Hebrew
		defaultScript = "Hebr"
	},
	["he"] = { --Hebrew
		defaultScript = "Hebr",
		suppressScript = true
	},
	["hi"] = { --Hindi
		defaultScript = "Deva",
		suppressScript = true
	},
	["hit"] = { --Hittite
		defaultScript = "Hluw"
	},
	["ho"] = { --Hiri Motu
		defaultScript = "Latn"
	},
	["hr"] = { --Croatian
		--Parent: sh
		defaultScript = "Latn",
		suppressScript = true
	},
	["ht"] = { --Haitian, Haitian Creole
		defaultScript = "Latn",
		suppressScript = true
	},
	["hu"] = { --Hungarian
		defaultScript = "Latn",
		suppressScript = true
	},
	["hur"] = { --Halkomelem
		defaultScript = "Latn"
	},
	["hy"] = { --Armenian
		defaultScript = "Armn",
		suppressScript = true
	},
	["hz"] = { --Herero
		defaultScript = "Latn"
	},
	["ia"] = { --Interlingua (International Auxiliary Language Association)
		defaultScript = "Latn"
	},
	["id"] = { --Indonesian
		--Parent: ms
		defaultScript = "Latn",
		suppressScript = true
	},
	["ie"] = { --Interlingue, Occidental
		defaultScript = "Latn"
	},
	["ig"] = { --Igbo
		defaultScript = "Latn"
	},
	["ii"] = { --Sichuan Yi, Nuosu
		defaultScript = "Yiii"
	},
	["ik"] = { --Inupiaq
		--Macrolanguage
		defaultScript = "Latn"
	},
	["ine"] = { --Indo-European languages
		--Collection
		defaultScript = "Latn"
	},
	["io"] = { --Ido
		defaultScript = "Latn"
	},
	["iow"] = { --Iowa-Oto
		defaultScript = "Latn"
	},
	["is"] = { --Icelandic
		defaultScript = "Latn",
		suppressScript = true
	},
	["it"] = { --Italian
		defaultScript = "Latn",
		suppressScript = true
	},
	["iu"] = { --Inuktitut
		--Macrolanguage
		defaultScript = "Latn"
	},
	["ja"] = { --Japanese
		defaultScript = "Jpan",
		suppressScript = true
	},
	["jah"] = { --Jah Hut
		defaultScript = "Latn"
	},
	["jpa"] = { --Jewish Palestinian Aramaic
		defaultScript = "Hebr"
	},
	["jrb"] = { --Judeo-Arabic
		--Macrolanguage
		defaultScript = "Hebr"
	},
	["jv"] = { --Javanese
		defaultScript = "Latn"
	},
	["ka"] = { --Georgian
		defaultScript = "Geor",
		suppressScript = true
	},
	["kg"] = { --Kongo
		--Macrolanguage
		defaultScript = "Latn"
	},
	["khk"] = { --Halh Mongolian
		--Parent: mn
		defaultScript = "Cyrl"
	},
	["ki"] = { --Kikuyu, Gikuyu
		defaultScript = "Latn"
	},
	["kj"] = { --Kuanyama, Kwanyama
		defaultScript = "Latn"
	},
	["kk"] = { --Kazakh
		defaultScript = "Cyrl",
		suppressScript = true
	},
	["kl"] = { --Kalaallisut, Greenlandic
		defaultScript = "Latn",
		suppressScript = true
	},
	["kld"] = { --Gamilaraay
		defaultScript = "Latn"
	},
	["km"] = { --Khmer, Central Khmer
		defaultScript = "Khmr",
		suppressScript = true
	},
	["kmr"] = { --Northern Kurdish
		--Parent: ku
		defaultScript = "Latn"
	},
	["kn"] = { --Kannada
		defaultScript = "Knda",
		suppressScript = true
	},
	["ko"] = { --Korean
		defaultScript = "Kore",
		suppressScript = true
	},
	["kr"] = { --Kanuri
		--Macrolanguage
		defaultScript = "Latn"
	},
	["ks"] = { --Kashmiri
		defaultScript = "Aran"
	},
	--["ku"] = { --Kurdish
		--Macrolanguage
		----wikipediaArticle = "Kurdish language",
		--defaultScript = "Latn"
	--},
	["kv"] = { --Komi
		--Macrolanguage
		defaultScript = "Cyrl"
	},
	["kw"] = { --Cornish
		defaultScript = "Latn"
	},
	["ky"] = { --Kirghiz, Kyrgyz
		defaultScript = "Cyrl"
	},
	["la"] = { --Latin
		defaultScript = "Latn",
		suppressScript = true
	},
	["lb"] = { --Luxembourgish, Letzeburgesch
		defaultScript = "Latn",
		suppressScript = true
	},
	["lg"] = { --Ganda, Luganda
		defaultScript = "Latn"
	},
	["li"] = { --Limburgan, Limburger, Limburgish
		defaultScript = "Latn"
	},
	["lkt"] = { --Lakota
		defaultScript = "Latn"
	},
	["ln"] = { --Lingala
		defaultScript = "Latn"
	},
	["lo"] = { --Lao
		defaultScript = "Laoo",
		suppressScript = true
	},
	["lt"] = { --Lithuanian
		defaultScript = "Latn",
		suppressScript = true
	},
	["ltc"] = { --Late Middle Chinese
		defaultScript = "Hant"
	},
	["lu"] = { --Luba-Katanga
		defaultScript = "Latn"
	},
	["lv"] = { --Latvian
		--Macrolanguage
		defaultScript = "Latn",
		suppressScript = true
	},
	["lzh"] = { --Literary Chinese
		--Parent: zh
		defaultScript = "Hant"
	},
	["mag"] = { --Magahi
		defaultScript = "Deva"
	},
	["mai"] = { --Maithili
		defaultScript = "Deva"
	},
	["mg"] = { --Malagasy
		--Macrolanguage
		defaultScript = "Latn"
	},
	["mga"] = { --Middle Irish (900-1200)
		defaultScript = "Latn"
	},
	["mh"] = { --Marshallese
		defaultScript = "Latn",
		suppressScript = true
	},
	["mi"] = { --Maori
		defaultScript = "Latn"
	},
	["mk"] = { --Macedonian
		defaultScript = "Cyrl",
		suppressScript = true
	},
	["ml"] = { --Malayalam
		defaultScript = "Mlym",
		suppressScript = true
	},
	--["mn"] = { --Mongolian
		--Macrolanguage
		----wikipediaArticle = "Mongolian language",
		--defaultScript = "Cyrl"
	--},
	["mr"] = { --Marathi
		defaultScript = "Deva",
		suppressScript = true
	},
	["ms"] = { --Malay (macrolanguage)
		--Macrolanguage
		defaultScript = "Latn",
		suppressScript = true
	},
	["mt"] = { --Maltese
		defaultScript = "Latn",
		suppressScript = true
	},
	["mvf"] = { --Peripheral Mongolian
		--Parent: mn
		defaultScript = "Mong"
	},
	["my"] = { --Burmese
		defaultScript = "Mymr",
		suppressScript = true
	},
	["na"] = { --Nauru
		defaultScript = "Latn",
		suppressScript = true
	},
	["nap"] = { --Neapolitan
		defaultScript = "Latn"
	},
	["nb"] = { --Norwegian Bokmål
		--Parent: no
		defaultScript = "Latn",
		suppressScript = true
	},
	["nci"] = { --Classical Nahuatl
		defaultScript = "Latn"
	},
	["nd"] = { --North Ndebele
		defaultScript = "Latn",
		suppressScript = true
	},
	["nds"] = { --Low German, Low Saxon
		defaultScript = "Latn",
		suppressScript = true
	},
	["ne"] = { --Nepali (macrolanguage)
		--Macrolanguage
		defaultScript = "Deva",
		suppressScript = true
	},
	["new"] = { --Nepal Bhasa, Newar, Newari
		defaultScript = "Newa"
	},
	["ng"] = { --Ndonga
		defaultScript = "Latn"
	},
	["nl"] = { --Dutch, Flemish
		defaultScript = "Latn",
		suppressScript = true
	},
	["nn"] = { --Norwegian Nynorsk
		--Parent: no
		defaultScript = "Latn",
		suppressScript = true
	},
	["no"] = { --Norwegian
		--Macrolanguage
		defaultScript = "Latn",
		suppressScript = true
	},
	["non"] = { --Old Norse
		defaultScript = "Latn"
	},
	["npi"] = { --Nepali (individual language)
		--Parent: ne
		defaultScript = "Deva"
	},
	["nr"] = { --South Ndebele
		defaultScript = "Latn",
		suppressScript = true
	},
	["nv"] = { --Navajo, Navaho
		defaultScript = "Latn"
	},
	["ny"] = { --Nyanja, Chewa, Chichewa
		defaultScript = "Latn",
		suppressScript = true
	},
	["oar"] = { --Old Aramaic (up to 700 BCE), Ancient Aramaic (up to 700 BCE)
		defaultScript = "Phnx"
	},
	["obm"] = { --Moabite
		defaultScript = "Phnx"
	},
	["oc"] = { --Occitan (post 1500)
		defaultScript = "Latn"
	},
	["oj"] = { --Ojibwa
		--Macrolanguage
		defaultScript = "Latn"
	},
	["ojp"] = { --Old Japanese
		defaultScript = "Jpan"
	},
	["om"] = { --Oromo
		--Macrolanguage
		defaultScript = "Latn",
		suppressScript = true
	},
	["or"] = { --Oriya (macrolanguage), Odia (macrolanguage)
		--Macrolanguage
		defaultScript = "Orya",
		suppressScript = true
	},
	["orv"] = { --Old Russian
		defaultScript = "Cyrl"
	},
	["ory"] = { --Odia (individual language), Oriya (individual language)
		--Parent: or
		defaultScript = "Orya"
	},
	["os"] = { --Ossetian, Ossetic
		defaultScript = "Cyrl"
	},
	["osx"] = { --Old Saxon
		defaultScript = "Latn"
	},
	["pa"] = { --Panjabi, Punjabi
		defaultScript = "Guru",
		suppressScript = true
	},
	["pal"] = { --Pahlavi
		defaultScript = "Phli"
	},
	["peo"] = { --Old Persian (ca. 600-400 B.C.)
		defaultScript = "Xpeo"
	},
	["pes"] = { --Iranian Persian
		--Parent: fa
		defaultScript = "Arab"
	},
	["pgl"] = { --Primitive Irish
		defaultScript = "Ogam"
	},
	["phn"] = { --Phoenician
		defaultScript = "Phnx"
	},
	["pi"] = { --Pali
		defaultScript = "Latn"
	},
	["pl"] = { --Polish
		defaultScript = "Latn",
		suppressScript = true
	},
	["pnb"] = { --Western Panjabi
		--Parent: lah
		defaultScript = "Aran"
	},
	["prg"] = { --Prussian
		defaultScript = "Latn"
	},
	["prs"] = { --Dari, Afghan Persian
		--Parent: fa
		defaultScript = "Arab"
	},
	["ps"] = { --Pushto, Pashto
		--Macrolanguage
		defaultScript = "Arab",
		suppressScript = true
	},
	["pt"] = { --Portuguese
		defaultScript = "Latn",
		suppressScript = true
	},
	["qu"] = { --Quechua
		--Macrolanguage
		defaultScript = "Latn",
		suppressScript = true
	},
	["quc"] = { --K'iche', Quiché
		defaultScript = "Latn"
	},
	["quy"] = { --Ayacucho Quechua
		--Parent: qu
		defaultScript = "Latn"
	},
	["quz"] = { --Cusco Quechua
		--Parent: qu
		defaultScript = "Latn"
	},
	["qwc"] = { --Classical Quechua
		--Parent: qu
		defaultScript = "Latn"
	},
	["rm"] = { --Romansh
		defaultScript = "Latn",
		suppressScript = true
	},
	["rn"] = { --Rundi
		defaultScript = "Latn",
		suppressScript = true
	},
	["ro"] = { --Romanian, Moldavian, Moldovan
		defaultScript = "Latn",
		suppressScript = true
	},
	["ru"] = { --Russian
		defaultScript = "Cyrl",
		suppressScript = true
	},
	["rw"] = { --Kinyarwanda
		defaultScript = "Latn",
		suppressScript = true
	},
	["ryu"] = { --Central Okinawan
		defaultScript = "Jpan"
	},
	["sa"] = { --Sanskrit
		--Macrolanguage
		defaultScript = "Deva",
		suppressScript = true
	},
	["sc"] = { --Sardinian
		--Macrolanguage
		defaultScript = "Latn"
	},
	["sco"] = { --Scots
		defaultScript = "Latn"
	},
	["scp"] = { --Hyolmo, Helambu Sherpa
		defaultScript = "Deva"
	},
	["sd"] = { --Sindhi
		defaultScript = "Arab"
	},
	["sdh"] = { --Southern Kurdish
		--Parent: ku
		defaultScript = "Arab"
	},
	["se"] = { --Northern Sami
		defaultScript = "Latn",
		suppressScript = true
	},
	["sg"] = { --Sango
		defaultScript = "Latn",
		suppressScript = true
	},
	["sga"] = { --Old Irish (to 900)
		defaultScript = "Latn"
	},
	--["sh"] = { --Serbo-Croatian
		--Macrolanguage
		----wikipediaArticle = "Serbo-Croatian",
		--defaultScript = "Latn"
	--},
	["si"] = { --Sinhala, Sinhalese
		defaultScript = "Sinh",
		suppressScript = true
	},
	["sk"] = { --Slovak
		defaultScript = "Latn",
		suppressScript = true
	},
	["sl"] = { --Slovenian
		defaultScript = "Latn",
		suppressScript = true
	},
	["sla"] = { --Slavic languages
		--Collection
		defaultScript = "Latn"
	},
	["sm"] = { --Samoan
		defaultScript = "Latn",
		suppressScript = true
	},
	["sn"] = { --Shona
		defaultScript = "Latn"
	},
	["so"] = { --Somali
		defaultScript = "Latn",
		suppressScript = true
	},
	["sog"] = { --Sogdian
		defaultScript = "Sogd"
	},
	["sq"] = { --Albanian
		--Macrolanguage
		defaultScript = "Latn",
		suppressScript = true
	},
	["sr"] = { --Serbian
		defaultScript = "Cyrl"
	},
	["ss"] = { --Swati
		defaultScript = "Latn",
		suppressScript = true
	},
	["st"] = { --Southern Sotho
		defaultScript = "Latn",
		suppressScript = true
	},
	["su"] = { --Sundanese
		defaultScript = "Latn"
	},
	["sux"] = { --Sumerian
		defaultScript = "Xsux"
	},
	["sv"] = { --Swedish
		defaultScript = "Latn",
		suppressScript = true
	},
	["sw"] = { --Swahili (macrolanguage)
		--Macrolanguage
		defaultScript = "Latn",
		suppressScript = true
	},
	["syc"] = { --Classical Syriac
		defaultScript = "Syrc"
	},
	["ta"] = { --Tamil
		defaultScript = "Taml",
		suppressScript = true
	},
	["te"] = { --Telugu
		defaultScript = "Telu",
		suppressScript = true
	},
	["tg"] = { --Tajik
		defaultScript = "Cyrl"
	},
	["th"] = { --Thai
		defaultScript = "Thai",
		suppressScript = true
	},
	["ti"] = { --Tigrinya
		defaultScript = "Ethi",
		suppressScript = true
	},
	["tk"] = { --Turkmen
		defaultScript = "Latn"
	},
	["tl"] = { --Tagalog
		defaultScript = "Latn",
		suppressScript = true
	},
	["tmr"] = { --Jewish Babylonian Aramaic (ca. 200-1200 CE)
		defaultScript = "Hebr"
	},
	["tn"] = { --Tswana
		defaultScript = "Latn",
		suppressScript = true
	},
	["to"] = { --Tonga (Tonga Islands)
		defaultScript = "Latn",
		suppressScript = true
	},
	["toi"] = { --Tonga (Zambia)
		defaultScript = "Latn"
	},
	["tpn"] = { --Tupinambá
		defaultScript = "Latn"
	},
	["tr"] = { --Turkish
		defaultScript = "Latn",
		suppressScript = true
	},
	["ts"] = { --Tsonga
		defaultScript = "Latn",
		suppressScript = true
	},
	["tt"] = { --Tatar
		defaultScript = "Cyrl"
	},
	["tw"] = { --Twi
		--Parent: ak
		defaultScript = "Latn"
	},
	["ty"] = { --Tahitian
		defaultScript = "Latn"
	},
	["ug"] = { --Uighur, Uyghur
		defaultScript = "Arab"
	},
	["uga"] = { --Ugaritic
		defaultScript = "Ugar"
	},
	["uk"] = { --Ukrainian
		defaultScript = "Cyrl",
		suppressScript = true
	},
	["ur"] = { --Urdu
		defaultScript = "Aran"
	},
	--["uz"] = { --Uzbek
		--Macrolanguage
		----wikipediaArticle = "Uzbek language",
		--defaultScript = "Cyrl"
	--},
	["uzn"] = { --Northern Uzbek
		--Parent: uz
		defaultScript = "Cyrl"
	},
	["uzs"] = { --Southern Uzbek
		--Parent: uz
		defaultScript = "Arab"
	},
	["ve"] = { --Venda
		defaultScript = "Latn",
		suppressScript = true
	},
	["vi"] = { --Vietnamese
		defaultScript = "Latn",
		suppressScript = true
	},
	["vo"] = { --Volapük
		defaultScript = "Latn"
	},
	["vsn"] = { --Vedic Sanskrit
		--Parent: sa
		defaultScript = "Deva"
	},
	["wa"] = { --Walloon
		defaultScript = "Latn"
	},
	["wo"] = { --Wolof
		defaultScript = "Latn"
	},
	["xct"] = { --Classical Tibetan
		defaultScript = "Tibt"
	},
	["xh"] = { --Xhosa
		defaultScript = "Latn",
		suppressScript = true
	},
	["xmn"] = { --Manichaean Middle Persian
		defaultScript = "Mani"
	},
	["xna"] = { --Ancient North Arabian
		defaultScript = "Narb"
	},
	["xng"] = { --Middle Mongolian
		defaultScript = "Mong"
	},
	["xpr"] = { --Parthian
		defaultScript = "Prti"
	},
	["xpu"] = { --Punic
		defaultScript = "Phnx"
	},
	["xsa"] = { --Sabaean
		defaultScript = "Sarb"
	},
	["xsr"] = { --Sherpa
		defaultScript = "Tibt"
	},
	["xul"] = { --Ngunawal, Nunukul
		defaultScript = "Latn"
	},
	["yi"] = { --Yiddish
		--Macrolanguage
		defaultScript = "Hebr",
		suppressScript = true
	},
	["yo"] = { --Yoruba
		defaultScript = "Latn"
	},
	["yua"] = { --Yucateco, Yucatec Maya
		defaultScript = "Latn"
	},
	["yue"] = { --Yue Chinese, Cantonese
		--Parent: zh
		defaultScript = "Hani"
	},
	["za"] = { --Zhuang, Chuang
		--Macrolanguage
		defaultScript = "Latn"
	},
	["zh"] = { --Chinese
		--Macrolanguage
		defaultScript = "Hani"
	},
	["zsm"] = { --Standard Malay
		--Parent: ms
		defaultScript = "Latn"
	},
	["zu"] = { --Zulu
		defaultScript = "Latn"
	}
}

local scriptTable = {
	["Adlm"] = {
		--Description: Adlam
		dir = "rtl"
	},
	["Afak"] = {
		--Description: Afaka
		dir = "ltr"
	},
	["Aghb"] = {
		--Description: Caucasian Albanian
		dir = "ltr"
	},
	["Ahom"] = {
		--Description: Ahom
		--Description: Tai Ahom
		dir = "ltr"
	},
	["Arab"] = {
		--Description: Arabic
		dir = "rtl"
	},
	["Aran"] = {
		--Description: Arabic (Nastaliq variant)
		dir = "rtl"
	},
	["Armi"] = {
		--Description: Imperial Aramaic
		dir = "rtl"
	},
	["Armn"] = {
		--Description: Armenian
		dir = "ltr"
	},
	["Avst"] = {
		--Description: Avestan
		dir = "rtl"
	},
	["Bali"] = {
		--Description: Balinese
		dir = "ltr"
	},
	["Bamu"] = {
		--Description: Bamum
		dir = "ltr"
	},
	["Bass"] = {
		--Description: Bassa Vah
		dir = "ltr"
	},
	["Batk"] = {
		--Description: Batak
		dir = "ltr"
	},
	["Beng"] = {
		--Description: Bengali
		--Description: Bangla
		dir = "ltr"
	},
	["Berf"] = {
		--Description: Beria Erfe
		dir = "ltr"
	},
	["Bhks"] = {
		--Description: Bhaiksuki
		dir = "ltr"
	},
	["Blis"] = {
		--Description: Blissymbols
		dir = "ltr"
	},
	["Bopo"] = {
		--Description: Bopomofo
		dir = "ltr"
	},
	["Brah"] = {
		--Description: Brahmi
		dir = "ltr"
	},
	["Brai"] = {
		--Description: Braille
		dir = "ltr"
	},
	["Bugi"] = {
		--Description: Buginese
		dir = "ltr"
	},
	["Buhd"] = {
		--Description: Buhid
		dir = "ltr"
	},
	["Cakm"] = {
		--Description: Chakma
		dir = "ltr"
	},
	["Cans"] = {
		--Description: Unified Canadian Aboriginal Syllabics
		dir = "ltr"
	},
	["Cari"] = {
		--Description: Carian
		dir = "ltr"
	},
	["Cham"] = {
		--Description: Cham
		dir = "ltr"
	},
	["Cher"] = {
		--Description: Cherokee
		dir = "ltr"
	},
	["Chis"] = {
		--Description: Chisoi
		dir = "ltr"
	},
	["Chrs"] = {
		--Description: Chorasmian
		dir = "rtl"
	},
	["Cirt"] = {
		--Description: Cirth
		dir = "ltr"
	},
	["Copt"] = {
		--Description: Coptic
		dir = "ltr"
	},
	["Cpmn"] = {
		--Description: Cypro-Minoan
		dir = "ltr"
	},
	["Cprt"] = {
		--Description: Cypriot syllabary
		dir = "rtl"
	},
	["Cyrl"] = {
		--Description: Cyrillic
		dir = "ltr"
	},
	["Cyrs"] = {
		--Description: Cyrillic (Old Church Slavonic variant)
		dir = "ltr"
	},
	["Deva"] = {
		--Description: Devanagari
		--Description: Nagari
		dir = "ltr"
	},
	["Diak"] = {
		--Description: Dives Akuru
		dir = "ltr"
	},
	["Dogr"] = {
		--Description: Dogra
		dir = "ltr"
	},
	["Dsrt"] = {
		--Description: Deseret
		--Description: Mormon
		dir = "ltr"
	},
	["Dupl"] = {
		--Description: Duployan shorthand
		--Description: Duployan stenography
		dir = "ltr"
	},
	["Egyd"] = {
		--Description: Egyptian demotic
		dir = "rtl"
	},
	["Egyh"] = {
		--Description: Egyptian hieratic
		dir = "rtl"
	},
	["Egyp"] = {
		--Description: Egyptian hieroglyphs
		dir = "ltr"
	},
	["Elba"] = {
		--Description: Elbasan
		dir = "ltr"
	},
	["Elym"] = {
		--Description: Elymaic
		dir = "rtl"
	},
	["Ethi"] = {
		--Description: Ethiopic
		--Description: Geʻez
		--Description: Ge'ez
		dir = "ltr"
	},
	["Gara"] = {
		--Description: Garay
		dir = "rtl"
	},
	["Geok"] = {
		--Description: Khutsuri (Asomtavruli and Nuskhuri)
		dir = "ltr"
	},
	["Geor"] = {
		--Description: Georgian (Mkhedruli and Mtavruli)
		dir = "ltr"
	},
	["Glag"] = {
		--Description: Glagolitic
		dir = "ltr"
	},
	["Gong"] = {
		--Description: Gunjala Gondi
		dir = "ltr"
	},
	["Gonm"] = {
		--Description: Masaram Gondi
		dir = "ltr"
	},
	["Goth"] = {
		--Description: Gothic
		dir = "ltr"
	},
	["Gran"] = {
		--Description: Grantha
		dir = "ltr"
	},
	["Grek"] = {
		--Description: Greek
		dir = "ltr"
	},
	["Gujr"] = {
		--Description: Gujarati
		dir = "ltr"
	},
	["Gukh"] = {
		--Description: Gurung Khema
		dir = "ltr"
	},
	["Guru"] = {
		--Description: Gurmukhi
		dir = "ltr"
	},
	["Hanb"] = {
		--Description: Han with Bopomofo (alias for Han + Bopomofo)
		dir = "ltr"
	},
	["Hang"] = {
		--Description: Hangul
		--Description: Hangŭl
		--Description: Hangeul
		dir = "ltr"
	},
	["Hani"] = {
		--Description: Han
		--Description: Hanzi
		--Description: Kanji
		--Description: Hanja
		dir = "ltr"
	},
	["Hano"] = {
		--Description: Hanunoo
		--Description: Hanunóo
		dir = "ltr"
	},
	["Hans"] = {
		--Description: Han (Simplified variant)
		dir = "ltr"
	},
	["Hant"] = {
		--Description: Han (Traditional variant)
		dir = "ltr"
	},
	["Hatr"] = {
		--Description: Hatran
		dir = "ltr"
	},
	["Hebr"] = {
		--Description: Hebrew
		dir = "rtl"
	},
	["Hira"] = {
		--Description: Hiragana
		dir = "ltr"
	},
	["Hluw"] = {
		--Description: Anatolian Hieroglyphs
		--Description: Luwian Hieroglyphs
		--Description: Hittite Hieroglyphs
		dir = "ltr"
	},
	["Hmng"] = {
		--Description: Pahawh Hmong
		dir = "ltr"
	},
	["Hmnp"] = {
		--Description: Nyiakeng Puachue Hmong
		dir = "ltr"
	},
	["Hntl"] = {
		--Description: Han (Traditional variant) with Latin (alias for Hant + Latn)
		dir = "ltr"
	},
	["Hrkt"] = {
		--Description: Japanese syllabaries (alias for Hiragana + Katakana)
		dir = "ltr"
	},
	["Hung"] = {
		--Description: Old Hungarian
		--Description: Hungarian Runic
		dir = "rtl"
	},
	["Inds"] = {
		--Description: Indus
		--Description: Harappan
		dir = "rtl"
	},
	["Ital"] = {
		--Description: Old Italic (Etruscan, Oscan, etc.)
		dir = "ltr"
	},
	["Jamo"] = {
		--Description: Jamo (alias for Jamo subset of Hangul)
		dir = "ltr"
	},
	["Java"] = {
		--Description: Javanese
		dir = "ltr"
	},
	["Jpan"] = {
		--Description: Japanese (alias for Han + Hiragana + Katakana)
		dir = "ltr"
	},
	["Jurc"] = {
		--Description: Jurchen
		dir = "ltr"
	},
	["Kali"] = {
		--Description: Kayah Li
		dir = "ltr"
	},
	["Kana"] = {
		--Description: Katakana
		dir = "ltr"
	},
	["Kawi"] = {
		--Description: Kawi
		dir = "ltr"
	},
	["Khar"] = {
		--Description: Kharoshthi
		dir = "rtl"
	},
	["Khmr"] = {
		--Description: Khmer
		dir = "ltr"
	},
	["Khoj"] = {
		--Description: Khojki
		dir = "ltr"
	},
	["Kitl"] = {
		--Description: Khitan large script
		dir = "vertical-rl"
	},
	["Kits"] = {
		--Description: Khitan small script
		dir = "vertical-rl"
	},
	["Knda"] = {
		--Description: Kannada
		dir = "ltr"
	},
	["Kore"] = {
		--Description: Korean (alias for Hangul + Han)
		dir = "ltr"
	},
	["Kpel"] = {
		--Description: Kpelle
		dir = "ltr"
	},
	["Krai"] = {
		--Description: Kirat Rai
		dir = "ltr"
	},
	["Kthi"] = {
		--Description: Kaithi
		dir = "ltr"
	},
	["Lana"] = {
		--Description: Tai Tham
		--Description: Lanna
		dir = "ltr"
	},
	["Laoo"] = {
		--Description: Lao
		dir = "ltr"
	},
	["Latf"] = {
		--Description: Latin (Fraktur variant)
		dir = "ltr"
	},
	["Latg"] = {
		--Description: Latin (Gaelic variant)
		dir = "ltr"
	},
	["Latn"] = {
		--Description: Latin
		dir = "ltr"
	},
	["Leke"] = {
		--Description: Leke
		dir = "ltr"
	},
	["Lepc"] = {
		--Description: Lepcha
		--Description: Róng
		dir = "ltr"
	},
	["Limb"] = {
		--Description: Limbu
		dir = "ltr"
	},
	["Lina"] = {
		--Description: Linear A
		dir = "ltr"
	},
	["Linb"] = {
		--Description: Linear B
		dir = "ltr"
	},
	["Lisu"] = {
		--Description: Lisu
		--Description: Fraser
		dir = "ltr"
	},
	["Loma"] = {
		--Description: Loma
		dir = "ltr"
	},
	["Lyci"] = {
		--Description: Lycian
		dir = "ltr"
	},
	["Lydi"] = {
		--Description: Lydian
		dir = "rtl"
	},
	["Mahj"] = {
		--Description: Mahajani
		dir = "ltr"
	},
	["Maka"] = {
		--Description: Makasar
		dir = "ltr"
	},
	["Mand"] = {
		--Description: Mandaic
		--Description: Mandaean
		dir = "rtl"
	},
	["Mani"] = {
		--Description: Manichaean
		dir = "rtl"
	},
	["Marc"] = {
		--Description: Marchen
		dir = "ltr"
	},
	["Maya"] = {
		--Description: Mayan hieroglyphs
		dir = "vertical-lr"
	},
	["Medf"] = {
		--Description: Medefaidrin
		--Description: Oberi Okaime
		--Description: Oberi Ɔkaimɛ
		dir = "ltr"
	},
	["Mend"] = {
		--Description: Mende Kikakui
		dir = "rtl"
	},
	["Merc"] = {
		--Description: Meroitic Cursive
		dir = "rtl"
	},
	["Mero"] = {
		--Description: Meroitic Hieroglyphs
		dir = "vertical-rl"
	},
	["Mlym"] = {
		--Description: Malayalam
		dir = "ltr"
	},
	["Modi"] = {
		--Description: Modi
		--Description: Moḍī
		dir = "ltr"
	},
	["Mong"] = {
		--Description: Mongolian
		dir = "vertical-lr"
	},
	["Moon"] = {
		--Description: Moon
		--Description: Moon code
		--Description: Moon script
		--Description: Moon type
		dir = "ltr"
	},
	["Mroo"] = {
		--Description: Mro
		--Description: Mru
		dir = "ltr"
	},
	["Mtei"] = {
		--Description: Meitei Mayek
		--Description: Meithei
		--Description: Meetei
		dir = "ltr"
	},
	["Mult"] = {
		--Description: Multani
		dir = "ltr"
	},
	["Mymr"] = {
		--Description: Myanmar
		--Description: Burmese
		dir = "ltr"
	},
	["Nagm"] = {
		--Description: Nag Mundari
		dir = "ltr"
	},
	["Nand"] = {
		--Description: Nandinagari
		dir = "ltr"
	},
	["Narb"] = {
		--Description: Old North Arabian
		--Description: Ancient North Arabian
		dir = "rtl"
	},
	["Nbat"] = {
		--Description: Nabataean
		dir = "rtl"
	},
	["Newa"] = {
		--Description: Newa
		--Description: Newar
		--Description: Newari
		--Description: Nepāla lipi
		dir = "ltr"
	},
	["Nkdb"] = {
		--Description: Naxi Dongba
		--Description: na²¹ɕi³³ to³³ba²¹
		--Description: Nakhi Tomba
		dir = "ltr"
	},
	["Nkgb"] = {
		--Description: Naxi Geba
		--Description: na²¹ɕi³³ gʌ²¹ba²¹
		--Description: 'Na-'Khi ²Ggŏ-¹baw
		--Description: Nakhi Geba
		dir = "ltr"
	},
	["Nkoo"] = {
		--Description: N’Ko
		--Description: N'Ko
		dir = "rtl"
	},
	["Nshu"] = {
		--Description: Nüshu
		dir = "vertical-rl"
	},
	["Ogam"] = {
		--Description: Ogham
		dir = "ltr"
	},
	["Olck"] = {
		--Description: Ol Chiki
		--Description: Ol Cemet'
		--Description: Ol
		--Description: Santali
		dir = "ltr"
	},
	["Onao"] = {
		--Description: Ol Onal
		dir = "ltr"
	},
	["Orkh"] = {
		--Description: Old Turkic
		--Description: Orkhon Runic
		dir = "rtl"
	},
	["Orya"] = {
		--Description: Oriya
		--Description: Odia
		dir = "ltr"
	},
	["Osge"] = {
		--Description: Osage
		dir = "ltr"
	},
	["Osma"] = {
		--Description: Osmanya
		dir = "ltr"
	},
	["Ougr"] = {
		--Description: Old Uyghur
		dir = "vertical-lr"
	},
	["Palm"] = {
		--Description: Palmyrene
		dir = "rtl"
	},
	["Pauc"] = {
		--Description: Pau Cin Hau
		dir = "ltr"
	},
	["Pcun"] = {
		--Description: Proto-Cuneiform
		dir = "ltr"
	},
	["Pelm"] = {
		--Description: Proto-Elamite
		dir = "ltr"
	},
	["Perm"] = {
		--Description: Old Permic
		dir = "ltr"
	},
	["Phag"] = {
		--Description: Phags-pa
		dir = "vertical-lr"
	},
	["Phli"] = {
		--Description: Inscriptional Pahlavi
		dir = "rtl"
	},
	["Phlp"] = {
		--Description: Psalter Pahlavi
		dir = "rtl"
	},
	["Phlv"] = {
		--Description: Book Pahlavi
		dir = "rtl"
	},
	["Phnx"] = {
		--Description: Phoenician
		dir = "rtl"
	},
	["Piqd"] = {
		--Description: Klingon (KLI pIqaD)
		dir = "ltr"
	},
	["Plrd"] = {
		--Description: Miao
		--Description: Pollard
		dir = "ltr"
	},
	["Prti"] = {
		--Description: Inscriptional Parthian
		dir = "rtl"
	},
	["Psin"] = {
		--Description: Proto-Sinaitic
		dir = "ltr" --Was inconsistent even within the same text, so just setting ltr by default
	},
	["Ranj"] = {
		--Description: Ranjana
		dir = "ltr"
	},
	["Rjng"] = {
		--Description: Rejang
		--Description: Redjang
		--Description: Kaganga
		dir = "ltr"
	},
	["Rohg"] = {
		--Description: Hanifi Rohingya
		dir = "rtl"
	},
	["Roro"] = {
		--Description: Rongorongo
		dir = "ltr"
	},
	["Runr"] = {
		--Description: Runic
		dir = "ltr"
	},
	["Samr"] = {
		--Description: Samaritan
		dir = "rtl"
	},
	["Sara"] = {
		--Description: Sarati
		dir = "ltr"
	},
	["Sarb"] = {
		--Description: Old South Arabian
		dir = "rtl"
	},
	["Saur"] = {
		--Description: Saurashtra
		dir = "ltr"
	},
	["Sgnw"] = {
		--Description: SignWriting
		dir = "ltr"
	},
	["Shaw"] = {
		--Description: Shavian
		--Description: Shaw
		dir = "ltr"
	},
	["Shrd"] = {
		--Description: Sharada
		--Description: Śāradā
		dir = "ltr"
	},
	["Shui"] = {
		--Description: Shuishu
		dir = "vertical-rl"
	},
	["Sidd"] = {
		--Description: Siddham
		--Description: Siddhaṃ
		--Description: Siddhamātṛkā
		dir = "ltr"
	},
	["Sidt"] = {
		--Description: Sidetic
		dir = "rtl"
	},
	["Sind"] = {
		--Description: Khudawadi
		--Description: Sindhi
		dir = "ltr"
	},
	["Sinh"] = {
		--Description: Sinhala
		dir = "ltr"
	},
	["Sogd"] = {
		--Description: Sogdian
		dir = "vertical-lr"
	},
	["Sogo"] = {
		--Description: Old Sogdian
		dir = "rtl"
	},
	["Sora"] = {
		--Description: Sora Sompeng
		dir = "ltr"
	},
	["Soyo"] = {
		--Description: Soyombo
		dir = "ltr"
	},
	["Sund"] = {
		--Description: Sundanese
		dir = "ltr"
	},
	["Sunu"] = {
		--Description: Sunuwar
		dir = "ltr"
	},
	["Sylo"] = {
		--Description: Syloti Nagri
		dir = "ltr"
	},
	["Syrc"] = {
		--Description: Syriac
		dir = "rtl"
	},
	["Syre"] = {
		--Description: Syriac (Estrangelo variant)
		dir = "rtl"
	},
	["Syrj"] = {
		--Description: Syriac (Western variant)
		dir = "rtl"
	},
	["Syrn"] = {
		--Description: Syriac (Eastern variant)
		dir = "rtl"
	},
	["Tagb"] = {
		--Description: Tagbanwa
		dir = "ltr"
	},
	["Takr"] = {
		--Description: Takri
		--Description: Ṭākrī
		--Description: Ṭāṅkrī
		dir = "ltr"
	},
	["Tale"] = {
		--Description: Tai Le
		dir = "ltr"
	},
	["Talu"] = {
		--Description: New Tai Lue
		dir = "ltr"
	},
	["Taml"] = {
		--Description: Tamil
		dir = "ltr"
	},
	["Tang"] = {
		--Description: Tangut
		dir = "vertical-rl"
	},
	["Tavt"] = {
		--Description: Tai Viet
		dir = "ltr"
	},
	["Tayo"] = {
		--Description: Tai Yo
		dir = "vertical-rl"
	},
	["Telu"] = {
		--Description: Telugu
		dir = "ltr"
	},
	["Teng"] = {
		--Description: Tengwar
		dir = "ltr"
	},
	["Tfng"] = {
		--Description: Tifinagh
		--Description: Berber
		dir = "ltr"
	},
	["Tglg"] = {
		--Description: Tagalog
		--Description: Baybayin
		--Description: Alibata
		dir = "ltr"
	},
	["Thaa"] = {
		--Description: Thaana
		dir = "rtl"
	},
	["Thai"] = {
		--Description: Thai
		dir = "ltr"
	},
	["Tibt"] = {
		--Description: Tibetan
		dir = "ltr"
	},
	["Tirh"] = {
		--Description: Tirhuta
		dir = "ltr"
	},
	["Tnsa"] = {
		--Description: Tangsa
		dir = "ltr"
	},
	["Todr"] = {
		--Description: Todhri
		dir = "ltr"
	},
	["Tols"] = {
		--Description: Tolong Siki
		dir = "ltr"
	},
	["Toto"] = {
		--Description: Toto
		dir = "ltr"
	},
	["Tutg"] = {
		--Description: Tulu-Tigalari
		dir = "ltr"
	},
	["Ugar"] = {
		--Description: Ugaritic
		dir = "ltr"
	},
	["Vaii"] = {
		--Description: Vai
		dir = "ltr"
	},
	["Visp"] = {
		--Description: Visible Speech
		dir = "ltr"
	},
	["Vith"] = {
		--Description: Vithkuqi
		dir = "ltr"
	},
	["Wara"] = {
		--Description: Warang Citi
		--Description: Varang Kshiti
		dir = "ltr"
	},
	["Wcho"] = {
		--Description: Wancho
		dir = "ltr"
	},
	["Wole"] = {
		--Description: Woleai
		dir = "ltr"
	},
	["Xpeo"] = {
		--Description: Old Persian
		dir = "ltr"
	},
	["Xsux"] = {
		--Description: Sumero-Akkadian cuneiform
		dir = "ltr"
	},
	["Yezi"] = {
		--Description: Yezidi
		dir = "rtl"
	},
	["Yiii"] = {
		--Description: Yi
		dir = "ltr"
	},
	["Zanb"] = {
		--Description: Zanabazar Square
		--Description: Zanabazarin Dörböljin Useg
		--Description: Xewtee Dörböljin Bicig
		--Description: Horizontal Square Script
		dir = "ltr"
	}
}

return {
	languageTable = languageTable,
	scriptTable = scriptTable
}