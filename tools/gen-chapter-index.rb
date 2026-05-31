#!/usr/bin/env ruby
# frozen_string_literal: true

# tools/gen-chapter-index.rb
#
# Generates docs/CHAPTERS.md (the chapter overview table) from the per-chapter
# YAML in campaigns/rime-of-the-frostmaiden/chapters/ch*.yaml.
#
# The YAML is the single source of truth for per-chapter facts; this index is
# DERIVED. Do not hand-edit docs/CHAPTERS.md — edit the YAML and regenerate:
#
#     ruby tools/gen-chapter-index.rb
#
# Ruby's stdlib YAML (Psych) is used; no gems required (ruby 2.6+).

require "yaml"

ROOT      = File.expand_path("..", __dir__)
CHAPTERS  = File.join(ROOT, "campaigns/rime-of-the-frostmaiden/chapters")
OUT       = File.join(ROOT, "docs/CHAPTERS.md")

# cadence token (YAML) -> emoji + human label for the table + legend.
CADENCE = {
  "tutorial"          => ["🟦", "tutorial"],
  "full_party_intro"  => ["🟦", "full-party intro"],
  "breather_defend"   => ["🟦", "breather / defend"],
  "gimmick_multilevel" => ["🟨", "gimmick (multi-level)"],
  "monster_debut"     => ["🟨", "monster debut (fog)"],
  "first_boss"        => ["🟥", "first boss"],
  "marquee_setpiece"  => ["🎬", "marquee set-piece"],
  "big_battle_gray"   => ["🟥", "big battle (gray)"],
  "scripted_defeat"   => ["🎬", "scripted defeat"]
}.freeze

# objective.type token -> FE-canonical label.
OBJECTIVE = {
  "defeat_boss"         => "DefeatBoss",
  "defeat_all"          => "DefeatAll",
  "seize"               => "Seize",
  "survive"             => "Survive",
  "defeat_boss_or_talk" => "DefeatBoss / Talk"
}.freeze

def chapter_label(num)
  num.to_i.zero? ? "P" : num.to_s
end

# Resolve a chapter id (e.g. "ch05-the-elven-tomb" or "ch09-revels-end") to a
# short "Ch N" label, flagging targets that have no YAML yet (post-MVP).
def unlocks_label(target_id, known_numbers)
  return "—" if target_id.nil?
  m = target_id.match(/\Ach0*(\d+)/)
  return target_id unless m
  n = m[1].to_i
  known_numbers.include?(n) ? "Ch #{n}" : "Ch #{n} (post-MVP)"
end

def objective_label(obj)
  return "—" unless obj
  type = obj["type"]
  OBJECTIVE.fetch(type) { type.to_s.split("_").map(&:capitalize).join(" ") }
end

def squish(str)
  str.to_s.gsub(/\s+/, " ").strip
end

def recruits_label(post)
  return "—" unless post
  playable = Array(post["units_available_to_recruit"]).map { |u| u["id"] }
  npcs     = Array(post["caravan_npcs_added"]).map { |u| u["id"] }
  parts = []
  parts << playable.join(", ") unless playable.empty?
  parts << "+npc: #{npcs.join(', ')}" unless npcs.empty?
  parts.empty? ? "—" : parts.join(" ")
end

files = Dir.glob(File.join(CHAPTERS, "ch*.yaml")).sort
abort "No chapter YAML found in #{CHAPTERS}" if files.empty?

chapters = files.map { |f| YAML.load_file(f) }.sort_by { |c| c["chapter_number"].to_i }
known_numbers = chapters.map { |c| c["chapter_number"].to_i }

rows = chapters.map do |c|
  emoji, label = CADENCE.fetch(c["cadence"]) { ["", c["cadence"].to_s] }
  cadence_cell = [emoji, label].reject { |s| s.to_s.empty? }.join(" ")
  obj = c["objective"]
  objective_cell = squish("#{objective_label(obj)} — #{obj && obj['description']}")
  [
    chapter_label(c["chapter_number"]),
    squish(c["title"]),
    cadence_cell,
    objective_cell,
    recruits_label(c["post_chapter"]),
    unlocks_label(c.dig("post_chapter", "unlocks_chapter"), known_numbers)
  ]
end

# Build the legend from only the cadence tags actually present, grouped by emoji.
present = chapters.map { |c| c["cadence"] }.uniq
legend_by_emoji = present.each_with_object({}) do |tok, h|
  emoji, label = CADENCE.fetch(tok) { next }
  (h[emoji] ||= []) << label
end
legend = legend_by_emoji.map { |emoji, labels| "#{emoji} #{labels.uniq.join(' / ')}" }.join(" · ")

first_num = chapters.first["chapter_number"].to_i
last_num  = chapters.last["chapter_number"].to_i
span = first_num.zero? ? "Prologue–Ch #{last_num}" : "Ch #{first_num}–#{last_num}"

lines = []
lines << "# Manchego Stars — Chapter Index (MVP, #{span})"
lines << ""
lines << "<!-- GENERATED FILE — do not edit by hand."
lines << "     Source:     campaigns/rime-of-the-frostmaiden/chapters/ch*.yaml"
lines << "     Regenerate: ruby tools/gen-chapter-index.rb"
lines << "     Per-chapter facts live in the YAML; this table is derived from it. -->"
lines << ""
lines << "The per-chapter source of truth is the YAML in"
lines << "`campaigns/rime-of-the-frostmaiden/chapters/`. This table is generated from it."
lines << "Forward-looking design (the promotion seam, the Act II–V scaffold, the cadence"
lines << "rules) lives in `docs/decisions.md` and `docs/fe8-pacing-reference.md`."
lines << ""
lines << "**Cadence legend:** #{legend}"
lines << ""
lines << "| # | Title | Cadence | Objective | Recruits | Unlocks |"
lines << "|---|---|---|---|---|---|"
rows.each { |r| lines << "| #{r.join(' | ')} |" }
lines << ""

File.write(OUT, lines.join("\n"))
warn "Wrote #{OUT} (#{chapters.length} chapters)."
