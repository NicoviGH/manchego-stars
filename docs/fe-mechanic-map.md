# FE-Mechanic Map — `fe_mechanic` anchors → concrete FE8 references

> **Scope: the spec layer between content and engine.** Every PC ability in
> `campaigns/rime-of-the-frostmaiden/pcs/*.yaml` carries a human-readable `fe_mechanic`
> string (the vanilla-FE anchor that makes it play cleanly — "Nosferatu", "Sleep staff",
> "Summoner phantom", …). This document + the machine-readable
> [`campaigns/rime-of-the-frostmaiden/fe-mechanic-map.yaml`](../campaigns/rime-of-the-frostmaiden/fe-mechanic-map.yaml)
> turn those anchors into **concrete FE8 references**: real `ITEM_*` / `CA_*` enums from the
> decomp, or a named custom engine feature. `tools/build-campaign.ts` joins the map against the
> PC YAMLs to emit engine data.
>
> This is the next layer below [rules-mapping.md](rules-mapping.md): rules-mapping says *how a
> generic 5e mechanic becomes FE-native*; this map says *which exact FE8 item/ability/feature
> implements each PC's specific reskin.*

---

## Why a central map (vs. inline `fe_ref` on each ability)

The 93 `fe_mechanic` anchors are spread across 7 carefully-curated PC YAMLs. Keeping the FE8
reference in one indexed file (rather than a new `fe_ref:` field on all 93 abilities) means:

- One reviewable artifact; the curated PC YAMLs stay untouched.
- `build-campaign.ts` resolves with a single lookup, keyed by `<pc_id>.<ability_id>`.
- The custom-engine backlog (below) falls out of the map directly — it *is* the Phase 1 work list.

Trade-off: the map can drift from the YAMLs if an ability `id` is renamed. `build-campaign.ts`
**must validate** that every ability carrying an `fe_mechanic` has exactly one map entry, and
that no map key is orphaned. (If we later prefer locality, this map converts mechanically to
inline `fe_ref:` blocks — the schema is identical.)

---

## `fe_ref` schema

| field | when | meaning |
|---|---|---|
| `kind` | always | `item` \| `class_ability` \| `custom_engine` \| `none` |
| `fe8_item` | `kind: item` | a real `ITEM_*` enum (or `[list]`) from `fireemblem8u/include/constants/items.h` |
| `fe8_ability` | `kind: class_ability` | a real `CA_*` flag (or `[list]`) from `fireemblem8u/include/bmunit.h` |
| `module` | `kind: custom_engine` | the `engine/` dir that implements the feature |
| `feature` | `kind: custom_engine` | stable `snake_case` key for the feature (shared across PCs that need the same thing) |
| `base` | optional | the vanilla `ITEM_*`/`CA_*`/concept the custom feature **reuses or extends** — a head-start for the implementer |

The four kinds:

1. **`item`** — a vanilla FE8 item delivers the mechanic as-is. Cleanest possible mapping; just
   reuse the item. (e.g. Nosferatu drain → `ITEM_DARK_NOSFERATU`; Sleep → `ITEM_STAFF_SLEEP`.)
2. **`class_ability`** — a vanilla FE8 class-ability flag delivers it (e.g. Summoner phantom →
   `CA_SUMMON`; Dancer refresh → `CA_REFRESHER`).
3. **`custom_engine`** — no vanilla item/flag delivers the core mechanic; it needs new engine code.
   `base` points at the closest vanilla code to build on. These are the Phase 1 backlog.
4. **`none`** — no engine reference (dropped per rules-mapping, baked into stats, or narrative-only).

---

## FE8 ID legend (only the IDs this map uses)

**Tomes / staves (`constants/items.h`)**

| ID | hex | used for |
|---|---|---|
| `ITEM_ANIMA_FIRE` | 0x38 | basic fire tome (Burning Hands, Scorching Ray base) |
| `ITEM_ANIMA_THUNDER` | 0x39 | thunder tome (Shocking Grasp, Thunderwave base) |
| `ITEM_ANIMA_ELFIRE` | 0x3A | mid fire tome (Immolation base) |
| `ITEM_ANIMA_BOLTING` | 0x3B | **thunder siege tome** — the siege-range chassis (Shatter, Call Lightning are this *exactly*; fire/cold "siege" tomes reuse its range) |
| `ITEM_ANIMA_FIMBULVETR` | 0x3C | top anima tome (cold-tier nuke base) |
| `ITEM_LIGHT_PURGE` | 0x42 | light siege tome (Meteor Swarm base) |
| `ITEM_DARK_FLUX` | 0x45 | basic dark tome (Chill Touch, Toll the Dead base) |
| `ITEM_DARK_NOSFERATU` | 0x47 | **drain** — damages + heals caster (Blight, Vampiric Touch) |
| `ITEM_DARK_FENRIR` | 0x49 | **dark siege nuke** (Abi-Dalzim's; Finger of Death base) |
| `ITEM_STAFF_HEAL` | 0x4B | single-target heal (Cure Wounds, Recharge self-heal) |
| `ITEM_STAFF_PHYSIC` | 0x4E | ranged heal (Mass Cure Wounds tier) |
| `ITEM_STAFF_RECOVER` | 0x4D | big heal (revive-suite tier) |
| `ITEM_STAFF_SILENCE` | 0x51 | disables casting (reference for silenced status) |
| `ITEM_STAFF_SLEEP` | 0x52 | **can't-act status** (Pacifying Spores, Hideous Laughter, Hypnotic Pattern base) |
| `ITEM_STAFF_BERSERK` | 0x53 | **lose-control status** (Confusion, Otto's Dance base) |
| `ITEM_STAFF_BARRIER` | 0x59 | +RES / anti-magic shield (Globe of Invulnerability base) |

**Other items**

| ID | hex | used for |
|---|---|---|
| `ITEM_SWORD_IRON` | 0x01 | plain melee sword (Luck E. Cheese — Wish is story-only) |
| `ITEM_SWORD_VENIN` | 0x08 | **poison status** anchor (Contagion base) |
| `ITEM_VULNERARY` | 0x6C | small consumable heal (Goodberry) |
| `ITEM_MINE` | 0x7A | **single-tile damage trap** — chassis for hazard tiles/zones |
| `ITEM_LIGHTRUNE` | 0x7B | **impassable barrier placement** — chassis for walls |
| `ITEM_HOPLON_SHIELD` | 0x7C | **negates enemy criticals** (Crit Immunity; Master of the Forge adamantine) |
| `ITEM_DIVINESTONE` | 0xAA | dragonstone (breath-cone flavor base) |
| `ITEM_MONSTER_SHARPCLAW` | 0x8B | claw weapon (Wolfram Feral Strike: Claws) |

**Class-ability flags (`bmunit.h`)**

| flag | bit | used for |
|---|---|---|
| `CA_SUMMON` | 1<<27 | Summoner phantom — temporary allied unit (Pepperjack/Brie, Animate Dead, Mordenkainen's Sword, summon-on-kill variants) |
| `CA_REFRESHER` | DANCE\|PLAY | Dance/refresh — grant an ally another turn (Sclorbo) |
| `CA_FLYER` | WYVERN\|PEGASUS | flier movement type (Fly = timed grant) |
| `CA_ASSASSIN` | 1<<25 | Lethality instakill (Power Word Kill threshold base) |
| `CA_CANTO` | 1<<1 | move-after-act (reference for Nimble Escape — currently unmapped, see §Unmapped) |
| `CA_CRITBONUS` | 1<<6 | +crit *rate* (NOT extra crit dice — Brutal Critical needs a custom multiplier) |

---

## Custom-engine backlog (the Phase 1 work list)

These are every `kind: custom_engine` feature, grouped by the module that owns it. The `feature`
key is shared — implement it once, every PC that references it gets it. **Bold = needed for MVP
(Ch 1–7)**; the rest are post-MVP gated.

### `engine/d20-combat` *(exists — scaffold)*
- **`extra_attack`** — brave-weapon-style second hit (base: brave weapon effect). *braulo.extra-attack (Ch5), braulo.frenzy (Ch3, gated on rage)*
- **`crit_extra_dice`** — extra weapon die on crit. *braulo.brutal-critical (Ch9)* — post-MVP
- **`extra_counter`** — second counterattack proc on melee hit (base: counterattack). *braulo.retaliation (Ch13)* — post-MVP
- **`reckless_toggle`** — toggle: +hit/+might, −avoid/−DEF while active (FE stat swing). *braulo.reckless-attack (Ch2)*
- **`dex_save_advantage`** — +avoid vs ranged/magic for a turn (or drop; no saves). *braulo.danger-sense (Ch2)*
- **`survive_at_1hp`** — drop to 1 HP instead of 0, escalating save. *braulo.relentless-rage (Ch11)* — post-MVP
- **`temp_hp_and_damage_aura`** — temp-HP buff + on-hit bonus damage while active. *marty.symbiotic-entity (Ch2)*
- **`damage_aura_on_approach`** — adjacent enemies auto-take chip. *marty.halo-of-spores (Ch2)*
- **`negate_incoming_crit`** — downgrade enemy crits to normal hits (base: ITEM_HOPLON_SHIELD). *marty.crit-immunity (Ch13)* — post-MVP
- **`mark_grants_advantage`** — marked foe gets −avoid (caster + summons hit it more). *marty.pheromone-spores (Ch1)*
- **`prf_tome_multibeam`** — locked personal tome, beam count scales (base: brave weapon effect; force type via damage-types). *meesmickle.eldritch-blast-tome (Ch1)*
- **`temp_hp_on_kill`** — gain temp HP on kill. *meesmickle.dark-ones-blessing (Ch1)*
- **`bonus_damage_finisher`** — add a big burst after a hit, 1/chapter. *meesmickle.hurl-through-hell (Ch13)* — post-MVP
- **`instakill_below_threshold`** — kill a target under an HP threshold (base: CA_ASSASSIN). *meesmickle.power-word-kill (Ch17)* — post-MVP
- **`bonus_damage_vs_wounded`** — extra damage to non-full-HP targets (base: ITEM_DARK_FLUX). *meesmickle.toll-the-dead (Ch1)*
- **`retaliate_fire_when_hit`** — auto fire damage to melee attacker (base: counterattack). *meesmickle.hellish-rebuke (Ch1)*
- **`cone_attack`** — fire/breath cone over a few adjacent tiles. *meesmickle.burning-hands (Ch1), wolfram.breath-weapon (Ch1, base: ITEM_DIVINESTONE)*
- **`siege_single_target`** — long-range single-target tome where no vanilla element-siege exists (base: ITEM_ANIMA_BOLTING for range). *meesmickle.fireball (Ch5), prof-rbg.fireball (Ch9), prof-rbg.ice-storm (Ch13), prof-rbg.cone-of-cold (Ch17), rootis.cone-of-cold (Ch9), wolfram.explosive-burst (Ch7)*
- **`reroll_self`** — 1/chapter: next attack auto-hits (FE has no roll to reroll). *meesmickle.dark-ones-own-luck (Ch6)*
- **`ally_save_bonus_proc`** — passive +avoid aura proc on a nearby ally. *prof-rbg.flash-of-genius (Ch7)*
- **`def_buff_reaction`** — +DEF/RES (or +avoid) reaction proc on self for one incoming hit. *prof-rbg.shield-spell (Ch3), wolfram.shield-spell (Ch5)*
- **`damage_and_shove`** — damage + push 1 tile (base: ITEM_ANIMA_THUNDER). *prof-rbg.thunderwave (Ch3)*
- **`multibolt_tome`** — N separate rolled hits, one cast (base: ITEM_ANIMA_FIRE + brave effect). *prof-rbg.scorching-ray (Ch5)*
- **`melee_tome_suppress_counter`** — melee tome; target loses its counter (base: ITEM_ANIMA_THUNDER). *prof-rbg.shocking-grasp (Ch1)*
- **`aoe_damage_and_prone`** — short-range burst + knockdown. *rootis.earth-tremor (Ch1)*
- **`siege_multi_blast`** — multi-point siege bombardment (base: ITEM_ANIMA_BOLTING, ITEM_LIGHT_PURGE). *rootis.meteor-swarm (Ch17)* — post-MVP
- **`grant_bonus_die`** — give an ally a die added to their next roll. *sclorbo.bardic-inspiration (Ch1)*
- **`enemy_roll_debuff_proc`** — auto-subtract a die from a nearby enemy's roll. *sclorbo.cutting-words (Ch3)*
- **`temp_hp_and_fear_immunity`** — ally buff: temp HP/turn + fear immunity. *sclorbo.heroism (Ch1)*
- **`auto_hit_multi_dart`** — auto-hitting multi-dart attack (reuses staff always-hit targeting). *sclorbo.magic-missile (Ch1)*
- **`bonus_damage_follow_up`** — melee hits add a small bonus bite. *wolfram.feral-strike-bite (Ch1)*

### `engine/status` *(PROPOSED NEW — status flags beyond the vanilla Sleep/Berserk/Silence/Poison staves)*
- `def_buff_timed` — timed +DEF/RES self-buff (FE-native; replaces the dropped pick-a-resistance). *meesmickle.fiendish-resilience (Ch9)* — post-MVP
- **`rage_self_buff`** — +might and +DEF (FE-native bulk; the 5e ×0.5-physical becomes +DEF, no multiplier), timed. *braulo.rage (Ch1)*
- **`status_immunity`** — immune to charm/fear (while raging). *braulo.mindless-rage (Ch6)*
- **`anti_heal_on_hit`** — target can't recover HP (base: ITEM_DARK_FLUX). *marty.chill-touch (Ch1)*
- **`blind`** — to-hit debuff for a turn. *marty.blindness-deafness (Ch3)*
- **`untargetable_self_timed`** — self untargetable for a turn. *marty.gaseous-form (Ch5)*
- **`untargetable_until_act`** — untargetable by ranged until move/act. *meesmickle.one-with-shadows (Ch2)*
- **`berserk_aoe`** — AoE lose-control (base: ITEM_STAFF_BERSERK). *marty.confusion (Ch7)*
- **`poison_strong`** — strong lingering poison + stat penalty (base: ITEM_SWORD_VENIN). *marty.contagion (Ch9)* — post-MVP
- **`charm_cant_act`** — target can't act against caster this turn. *meesmickle.suggestion (Ch3)*
- **`inflict_status_choice`** — choose poison/fear/sleep (base: ITEM_STAFF_SLEEP). *meesmickle.eyebite (Ch10)* — post-MVP
- **`sleep_aoe`** — AoE can't-act (base: ITEM_STAFF_SLEEP). *rootis.hypnotic-pattern (Ch5)*
- **`burn_dot`** — fire damage-over-time (base: ITEM_ANIMA_ELFIRE). *rootis.immolation (Ch9)* — post-MVP
- **`barrier_aoe`** — +RES shield on self + adjacent allies (base: ITEM_STAFF_BARRIER). *rootis.globe-of-invulnerability (Ch11)* — post-MVP
- **`slow_on_hit`** — target loses MOV/SPD on hit. *sclorbo.ray-of-frost (Ch1)*
- **`to_hit_debuff_on_hit`** — target attacks at −hit next turn. *sclorbo.vicious-mockery (Ch1)*
- **`forced_dance_cc`** — can't attack + shuffles uncontrollably (base: ITEM_STAFF_BERSERK). *sclorbo.ottos-irresistible-dance (Ch11)* — post-MVP
- **`revive_staff`** — raise a fallen ally; **no vanilla FE8 staff does this** (Heal/Physic/Recover tiers reuse vanilla; Revive/Raise Dead is the novel piece). *sclorbo.bard-healing-suite (Ch9+)* — post-MVP

### `engine/hazards` *(PROPOSED NEW — multi-tile / persistent / drifting terrain effects)*
- `hazard_zone_persistent` — 2×2 chip zone that stays (base: ITEM_MINE). *marty.spreading-spores (Ch9)* — post-MVP
- `hazard_zone_drifting` — chip zone that moves each turn (base: ITEM_MINE). *marty.cloudkill (Ch9), rootis.incendiary-cloud (Ch15)* — post-MVP
- `hazard_wall` — line of damage tiles (base: ITEM_MINE). *prof-rbg.wall-of-fire (Ch13)* — post-MVP
- `barrier_line_blocks_ranged` — impassable line that also stops ranged (base: ITEM_LIGHTRUNE). *prof-rbg.wind-wall (Ch9)* — post-MVP
- `barrier_impassable` — fully impassable barrier, movement + attacks (base: ITEM_LIGHTRUNE). *prof-rbg.wall-of-force (Ch17)* — post-MVP

### `engine/damage-types` *(exists — now a flavor label tag only)*
The ×0.5/×0/×2 resistance system was **dropped 2026-05-28** (no vanilla FE analogue). This module is
just a flavor damage-type label on weapons (for UI/descriptions). No custom resistance features:
- ~~`grant_resistance_choice`~~ → reflavored to **`def_buff_timed`** in `engine/status` (timed +DEF/RES self-buff). *meesmickle.fiendish-resilience (Ch9)* — post-MVP
- ~~`damage_resistance`~~ → **dropped to flavor** (`kind: none`). *wolfram.fire-resistance* is now narrative only; iconic vulnerabilities use vanilla FE weapon **effectiveness** instead.

### `engine/class-defs` *(exists — scaffold)*
- **`guard_stance`** — +DEF/RES, MOV 0, no counter until he emerges. *braulo.shell-defense (Ch1)*
- **`summon_on_kill`** — spawn a phantom from a slain enemy (base: CA_SUMMON). *marty.fungal-infestation (Ch6)*
- **`nuke_summon_on_kill`** — dark nuke; killed target rises as a thrall (base: ITEM_DARK_FENRIR + CA_SUMMON). *meesmickle.finger-of-death (Ch13)* — post-MVP
- **`grant_flier_movement_timed`** — temporary flier movement on self/ally (base: CA_FLYER). *rootis.fly (Ch5)*
- **`forge_command`** — prep-screen meta command: permanently buff an ally's gear; tiers add weapon upgrades / +DEF / adamantine crit-immunity (base: ITEM_HOPLON_SHIELD for adamantine; all FE-native — no damage-type resistance). *wolfram.forge (Ch1), wolfram.forge-expert (Ch7), wolfram.blade-forge (Ch11), wolfram.master-of-the-forge (Ch15)*

---

## Combat-resolution decision — RESOLVED 2026-05-28 (vanilla FE)

Combat *rules* are vanilla FE8 (hit%/avoid/might/crit); D&D is flavor; the d20 survives only as a
cosmetic crit flourish. **AC, saving throws, and advantage/disadvantage are dropped as mechanics**
(see `decisions.md` §Combat System). The `item` / `class_ability` / hazard / summon / status
mappings are **unaffected** — they were always vanilla-FE-native. The features and YAML fields that
assumed d20/AC/save/advantage **reflavor onto FE-native effects (hit/avoid/DEF/RES stat swings,
always-hit targeting) or drop**, per this table:

| feature / field | was (d20 assumption) | now (FE-native) |
|---|---|---|
| `reckless_toggle` *(braulo.reckless-attack)* | advantage on offense, enemies advantage vs self | toggle: **+hit/+might, −avoid/−DEF** while active (FE stat swing) |
| `dex_save_advantage` *(braulo.danger-sense)* | advantage on DEX saves vs visible AoE | **+avoid vs ranged/magic** for a turn, or drop (no saves) |
| `mark_grants_advantage` *(marty.pheromone-spores)* | marked foe → caster+summons get advantage | marked foe gets **−avoid** (everyone hits it more) |
| `auto_hit_multi_dart` *(sclorbo.magic-missile)* | auto-hit "skips the d20" | **always-hit multi-hit tome** — reuses staff always-hit targeting + brave multi-strike (fully FE-native; nothing to skip) |
| `reroll_self` *(meesmickle.dark-ones-own-luck)* | reroll a failed attack/save | 1/chapter: **next attack auto-hits** (or big +hit), no save half |
| `ally_save_bonus_proc` *(prof-rbg.flash-of-genius)* | auto +INT to ally's save/avoid | passive **+avoid aura** proc on nearby ally |
| `enemy_roll_debuff_proc` *(sclorbo.cutting-words)* | subtract a die from enemy's roll | auto **−hit/−avoid debuff** on a nearby enemy |
| `def_buff_reaction` *(prof-rbg/wolfram shield-spell; was `ac_buff_reaction`)* | +AC reaction for one hit | **+DEF/RES (or +avoid) reaction** proc for one incoming hit |
| `grant_bonus_die` *(sclorbo.bardic-inspiration)* | give ally a die for next roll | **+hit/+avoid/+might buff** to an ally (timed) |
| `guard_stance` *(braulo.shell-defense)* | +AC + save advantage, MOV 0, no counter | **+DEF/RES**, MOV 0, no counter until he emerges |
| all `save:` / `save_dc:` in PC YAMLs | DC vs d20 save | **flavor only** — status staves always-hit; offensive spells use FE magic combat |

These are now all `engine`-implementable as FE stat modifiers / always-hit effects — **no d20
substrate required**. The old `base: advantage_state` references have been removed from the backlog
and the `.yaml`; the FE-native forms in this table are authoritative.

---

## Unmapped abilities (follow-up pass)

Abilities **without** an `fe_mechanic` anchor are out of scope for this map but still need engine
references for `build-campaign.ts`. The ones with an obvious FE8 anchor (ready to map next):

- **rootis.dragon-wings** → Manakete/Dragonstone **class transform** (already decided; `engine/class-defs`)
- **prof-rbg.nimble-escape** → `CA_CANTO` (move-after-act)
- **prof-rbg.infuse-item** → `forge_command`-style prep-screen buff (shares Wolfram's feature)
- **sclorbo.natural-shelter** / **marty/rootis terrain hides** → `untargetable_self_timed`
- **meesmickle.unholy-body** → custom item-use flag (healing items deal poison)
- **rootis.crystallize / elemental-properties / snow-ski** → damage-type toggle, cold-heals, terrain-MOV passives

The rest (metamagic modifiers, capstones, pure-flavor racials) are either `none` or fold into the
features above. A second pass should give every `fe_mechanic`-less ability a `none`/feature tag so
the build can assert 100 % coverage.
