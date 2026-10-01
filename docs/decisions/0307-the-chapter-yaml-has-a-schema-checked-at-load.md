---
id: 307
title: "The chapter YAML has a schema, checked when the file is loaded"
date: "2026-10-01"
section: "Operational Gotchas (durable)"
issues: [411]
---

# The chapter YAML has a schema, checked when the file is loaded

Every reader of a chapter YAML does `chap.get('key')`. A typo'd key such as `enemy_unit:` or
`win_conditon:` therefore gave a chapter that silently had none. At best it showed up at
injection, and at worst in a watched playtest. `tools/chapter_schema.py` now lists every key
each object may hold and refuses the rest.

- **It checks keys and shape only.** Each mapping it describes may hold only the keys it names,
  and a value must be a mapping, a list or a leaf where the schema says so. The error names the
  path and the closest real key: `enemy_units[2].is_bos ... did you mean is_boss?`.
- **It leaves alone what other gates own.** A scene's `script:` belongs to `make scene`.
  Deployment's numbers belong to `check_chapter_deployment_schema`. Prose and a leaf's type
  belong to whoever reads them. The schema answers one question no reader can: does this key
  exist?
- **Every loader runs it.** The two cached loaders check as they parse.
  `campaign_chapters.load_all` covers `make chapter` and the reports, and
  `inject.hosting._load_chapter_yaml` covers the build. Every other reader that used to parse a
  chapter file itself now calls `chapter_schema.load(path)`: the arena, prologue, units and
  map-sprite passes, `difficulty`, `exp_curve`, `import_map_layout` and the onboarding index.
  `check_chapter_yaml_schema` runs the same check in `make check` and on the CI `checks` job
  (stdlib plus pyyaml), and its canary is a misspelt `win_condition`.
- **One unit shape covers every roster key.** `enemy_units`, `reinforcements`,
  `enemy_reinforcements`, `neutral_units`, `green_units`, `player_units` and
  `deployment.green_allies` all take the same fields. The readers treat them interchangeably
  (`raw_pids.PLACED_ROSTER_KEYS`), so a field that is legal on an enemy is legal in a wave.
- **A new key is one line in the schema.** The refusal says so. Planned seed chapters pass the
  same schema, and their keys are already listed.

Done-when evidence: all nine chapter YAMLs pass. Renaming ch05's `win_condition` makes
`make chapter CH=ch05` and the injector's loader both exit in 0.24s, naming the fix.
`injection_fingerprint` (default configuration) is IDENTICAL.
