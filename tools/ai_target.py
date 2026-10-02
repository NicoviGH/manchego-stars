#!/usr/bin/env python3
"""Which of our units FE8's enemy AI attacks -- a port of `AiComputeCombatScore`.

The enemy AI picks its target by scoring every (position, target, weapon) it can reach and
taking the best (fireemblem8u/src/cp_battle.c:572-780). The score is built on a SIMULATED
battle in which every strike connects and none crits (`BattleRoll2RN`/`BattleRoll1RN` return
their `simResult` under `BATTLE_CONFIG_SIMULATE`, bmbattle.c:253-265), so it is deterministic.

Components, weighted by the unit's combat-weight table (`ai_config` bits 3-7, cp_decide.c:99;
`gAiCombatScoreCoefficientTable`, cp_data.c):

    + damage dealt      50 on a kill, else coeff x (Atk - Def) x displayed hit / 100, cap 40
    + opponent low HP   coeff x (20 - target's HP after the battle), floored at 0
    + friend zone       POSITIONAL -- allies near the attack tile; not modelled (0)
    + target class      coeff x classRankBonuses[rank], cap 20 -- every class reads rank 9
                        (FE8's rank lists are empty), one past the array; see `_class_term`
    + turn number       coeff x turn (turn 1 here)
    - damage taken      -10 when the target cannot strike back, else
                        coeff x (its Atk - our Def) x its displayed hit / 100, cap 40
    - danger            POSITIONAL -- the danger map under the attack tile; not modelled (0)
    - own low HP        coeff x (20 - attacker's HP after the battle), floored at 0

    score = sum x 40, or -- when the sum is 0 or below -- the damage-dealt term alone.

Positions are not modelled: every target is assumed reachable, at whichever distance in the
attacker's range scores best (a 1-2 range unit picks the distance its target cannot answer).
What this answers is the half of the decision that stats decide: WHO the AI prefers.
"""
import functools
import re

import fe_combat as fc
import inject.decomp

CP_DATA = 'src/cp_data.c'
COEFF_FIELDS = ('coeffDamageDealt', 'coeffLowHpOpponent', 'coeffFriendZone',
                'coeffClassRankBonus', 'coeffTurnNumber', 'coeffDamageTaken', 'coeffDanger',
                'coeffLowHpSelf')
CLASS_RANKS = 9                 # sizeof classRankBonuses (cp_data.h)
CLASS_RANK = 9                  # AiGetClassRank: every gAiClassRankLists entry is empty


@functools.lru_cache(maxsize=None)
def coefficient_tables():
    """`gAiCombatScoreCoefficientTable` as a list of {field: int, 'bonuses': [9 ints]}, read
    from the decomp so a table is never transcribed by hand."""
    text = inject.decomp.vanilla_decomp_text(CP_DATA)
    s, e = inject.decomp._find_brace_block(text, 'gAiCombatScoreCoefficientTable[]',
                                           '<%s>' % CP_DATA)
    body = text[s + 1:e - 1]
    tables = []
    for m in re.finditer(r'\[(\d+)\]\s*=\s*\{(.*?)\.classRankBonuses\s*=\s*\{(.*?)\}', body,
                         re.S):
        index, fields, bonuses = int(m.group(1)), m.group(2), m.group(3)
        if index != len(tables):
            raise ValueError('%s: table [%d] out of order' % (CP_DATA, index))
        row = {f: int(re.search(r'\.%s\s*=\s*(\d+)' % f, fields).group(1))
               if re.search(r'\.%s\s*=' % f, fields) else 0 for f in COEFF_FIELDS}
        row['bonuses'] = [0] * CLASS_RANKS
        for k, v in re.findall(r'\[(\d+)\]\s*=\s*(\d+)', bonuses):
            row['bonuses'][int(k)] = int(v)
        tables.append(row)
    if not tables:
        raise ValueError('%s: no gAiCombatScoreCoefficientTable entries parsed' % CP_DATA)
    return tables


@functools.lru_cache(maxsize=None)
def _class_term(table_id):
    """`AiGetTargetClassCombatScoreComponent`. Rank 9 indexes one byte past the 9-entry
    `classRankBonuses`, which is the NEXT table's first byte (`coeffDamageDealt`; the struct is
    17 packed u8s). The term is the same for every target, so it never changes who is picked;
    it only decides whether the sum clears zero, and that is why it is read faithfully."""
    tables = coefficient_tables()
    nxt = tables[table_id + 1]['coeffDamageDealt'] if table_id + 1 < len(tables) else 0
    return min(20, tables[table_id]['coeffClassRankBonus'] * nxt)


def combat_weight_table(ai):
    """The combat-weight table id from a unit's 4 AI bytes (`ai_config` low byte, bits 3-7)."""
    return (ai[2] >> 3) & 0x1F


def _reaches(weapon, distance):
    return weapon is not None and weapon.rng[0] <= distance <= weapon.rng[1]


def _left(hp_a, hp_d, dmg_ad, dmg_da, counters, a_doubles, d_doubles):
    """HP left on (attacker, target) after the simulated battle: every strike lands, no crit,
    in FE8's order -- attacker, counter, then whoever doubles follows up."""
    hp = [hp_a, hp_d]
    order = [(1, dmg_ad)]
    if counters:
        order.append((0, dmg_da))
    if a_doubles:
        order.append((1, dmg_ad))
    elif counters and d_doubles:
        order.append((0, dmg_da))
    for struck, dmg in order:
        hp[struck] = max(0, hp[struck] - dmg)
        if hp[struck] == 0:
            break
    return hp[0], hp[1]


def combat_score(atk, dfn, table_id=0, turn=1):
    """`AiComputeCombatScore` for `atk` attacking `dfn`, at the best distance in `atk`'s range.
    Returns 0 for a weaponless attacker."""
    if atk.weapon is None:
        return 0
    c = coefficient_tables()[table_id]
    dmg_ad, dmg_da = fc.damage(atk, dfn), fc.damage(dfn, atk)
    a_doubles, d_doubles = fc.doubles(atk, dfn), fc.doubles(dfn, atk)
    dealt_hit = min(40, c['coeffDamageDealt'] * (dmg_ad * fc.hit_chance(atk, dfn) // 100))
    taken_hit = (min(40, c['coeffDamageTaken'] * (dmg_da * fc.hit_chance(dfn, atk) // 100))
                 if dfn.weapon is not None else None)
    constant = _class_term(table_id) + c['coeffTurnNumber'] * turn
    best = None
    for distance in range(atk.weapon.rng[0], atk.weapon.rng[1] + 1):
        counters = _reaches(dfn.weapon, distance)
        a_hp, d_hp = _left(atk.hp, dfn.hp, dmg_ad, dmg_da, counters, a_doubles, d_doubles)
        dealt = 50 if d_hp == 0 else dealt_hit
        taken = taken_hit if counters else -10
        total = (dealt
                 + max(0, c['coeffLowHpOpponent'] * (20 - d_hp))
                 + constant
                 - taken
                 - max(0, c['coeffLowHpSelf'] * (20 - a_hp)))
        score = total * 40 if total > 0 else dealt
        best = score if best is None else max(best, score)
    return best


def pick_target(atk, party, table_id=0, turn=1):
    """The party member the AI attacks: the first highest `combat_score` (the AI keeps a
    candidate only on a strictly better score). None for an empty party."""
    best, chosen = None, None
    for unit in party:
        s = combat_score(atk, unit, table_id, turn)
        if best is None or s > best:
            best, chosen = s, unit
    return chosen
