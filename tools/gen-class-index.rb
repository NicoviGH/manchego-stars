#!/usr/bin/env ruby
# frozen_string_literal: true

# tools/gen-class-index.rb
#
# Generates docs/CLASSES.md (the unit roster + class/promotion index) from the
# per-unit YAML in campaigns/rime-of-the-frostmaiden/{pcs,npcs}/*.yaml.
#
# The unit YAML is the single source of truth for FE class + promotion; this index
# is DERIVED. Do not hand-edit docs/CLASSES.md — edit the YAML and regenerate:
#
#     ruby tools/gen-class-index.rb
#
# The *rationale* (why each PC maps to its FE class, the promotion seam) lives in
# docs/decisions.md, not here. Ruby stdlib YAML only (ruby 2.6+).

require "yaml"

ROOT = File.expand_path("..", __dir__)
PCS  = File.join(ROOT, "campaigns/rime-of-the-frostmaiden/pcs")
NPCS = File.join(ROOT, "campaigns/rime-of-the-frostmaiden/npcs")
OUT  = File.join(ROOT, "docs/CLASSES.md")

def squish(str)
  str.to_s.gsub(/\s+/, " ").strip
end

# "**Default** / Other / Other" from promotion.branch + promotion.default.
def promotion_cell(promo)
  return "—" unless promo
  branch = Array(promo["branch"])
  return "—" if branch.empty?
  default = promo["default"]
  ordered = ([default] + branch).compact.uniq
  ordered.map.with_index { |c, i| i.zero? && default ? "**#{c}**" : c }.join(" / ")
end

def fe_base(unit)
  cls = unit.dig("fe_stats", "class")
  cls.nil? || cls.to_s.strip.empty? ? "TBD (post-MVP)" : cls
end

def dnd_source(unit)
  d = unit["dnd"]
  return "—" unless d
  src = squish(d["class"])
  race = squish(d["race"])
  race.empty? ? src : "#{src} — #{race}"
end

def load_dir(dir)
  Dir.glob(File.join(dir, "*.yaml")).sort.map { |f| YAML.load_file(f) }
end

pcs  = load_dir(PCS).sort_by { |u| u["id"].to_s }
npcs = load_dir(NPCS).sort_by { |u| u["id"].to_s }
abort "No PC YAML found in #{PCS}" if pcs.empty?

lines = []
lines << "# Manchego Stars — Unit Roster & Class Index"
lines << ""
lines << "<!-- GENERATED FILE — do not edit by hand."
lines << "     Source:     campaigns/rime-of-the-frostmaiden/{pcs,npcs}/*.yaml"
lines << "     Regenerate: ruby tools/gen-class-index.rb"
lines << "     Class/promotion facts live in the unit YAML; this table is derived from it. -->"
lines << ""
lines << "Every unit is a **stock vanilla FE8 class** (bases/growths/caps verbatim from"
lines << "`fireemblem8u/src/data_classes.c`); D&D is flavor only. The *rationale* for each"
lines << "mapping and the promotion seam live in `docs/decisions.md` — this is just the"
lines << "roster derived from the unit YAML."
lines << ""
lines << "## Player characters"
lines << ""
lines << "| PC | D&D source | FE base | Promotion (player picks; **default** bold) |"
lines << "|---|---|---|---|"
pcs.each do |u|
  lines << "| #{squish(u['name'])} | #{dnd_source(u)} | #{fe_base(u)} | #{promotion_cell(u['promotion'])} |"
end
lines << ""
lines << "## Recruits & NPCs"
lines << ""
lines << "| Unit | FE base | Promotion | Joins via |"
lines << "|---|---|---|---|"
npcs.each do |u|
  joins = squish(u["recruited_via"])
  joins = "—" if joins.empty?
  lines << "| #{squish(u['name'])} | #{fe_base(u)} | #{promotion_cell(u['promotion'])} | #{joins} |"
end
lines << ""
lines << "> **Note.** `pepperjack`/`brie` carry `fe_stats.class: null` — their FE-legal"
lines << "> class is a deliberate post-MVP TBD. Other recruits referenced in the chapters"
lines << "> (Baxby, Trex, Sahnar, Lupin, Basil) do not yet have unit YAML; see the chapter"
lines << "> files and `docs/CHAPTERS.md` for where they join."
lines << ""

File.write(OUT, lines.join("\n"))
warn "Wrote #{OUT} (#{pcs.length} PCs, #{npcs.length} NPCs)."
