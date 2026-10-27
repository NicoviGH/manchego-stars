"""The team caps the campaign bot fields under (#510 step 9 PR E): FE8 class -> group, and the
most units of a group a player fields.

A TABLE, never a read of class attributes (Nicolas, 2026-10-27: a table is always correct;
inference leaves room for interpretation). Every player unit is a stock vanilla class -- our
player reskins (Lupin's direwolf, Baxby's axebeak) are `class: cavalier` with per-character
art -- so the vanilla class names cover both games. The #543 lord classes join this table BY
NAME, each in the group of the role it fills. A player class missing from it raises in
bot.lua (Bot.team) and fails test_team_groups, so it can never fall into a default group.

The maxima are the research's (docs/research 0007, 0013): what players field, never a rule
of the game. A group the research names no limit for (magic, lords, trainees) has none.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import inject.class_ids  # noqa: E402

GROUPS = {
    'flier': ('CLASS_PEGASUS_KNIGHT', 'CLASS_FALCON_KNIGHT', 'CLASS_WYVERN_RIDER',
              'CLASS_WYVERN_RIDER_F', 'CLASS_WYVERN_KNIGHT', 'CLASS_WYVERN_KNIGHT_F',
              'CLASS_WYVERN_LORD', 'CLASS_WYVERN_LORD_F'),
    'healer': ('CLASS_PRIEST', 'CLASS_CLERIC', 'CLASS_TROUBADOUR', 'CLASS_BISHOP',
               'CLASS_BISHOP_F', 'CLASS_VALKYRIE'),
    'mounted': ('CLASS_CAVALIER', 'CLASS_CAVALIER_F', 'CLASS_PALADIN', 'CLASS_PALADIN_F',
                'CLASS_GREAT_KNIGHT', 'CLASS_GREAT_KNIGHT_F'),
    'armour': ('CLASS_ARMOR_KNIGHT', 'CLASS_ARMOR_KNIGHT_F', 'CLASS_GENERAL', 'CLASS_GENERAL_F'),
    'archer': ('CLASS_ARCHER', 'CLASS_ARCHER_F', 'CLASS_SNIPER', 'CLASS_SNIPER_F', 'CLASS_RANGER',
               'CLASS_RANGER_F'),
    'axe': ('CLASS_FIGHTER', 'CLASS_PIRATE', 'CLASS_BRIGAND', 'CLASS_WARRIOR', 'CLASS_BERSERKER',
            'CLASS_HERO', 'CLASS_HERO_F'),
    'thief': ('CLASS_THIEF', 'CLASS_ROGUE', 'CLASS_ASSASSIN', 'CLASS_ASSASSIN_F'),
    'sword': ('CLASS_MYRMIDON', 'CLASS_MYRMIDON_F', 'CLASS_MERCENARY', 'CLASS_MERCENARY_F',
              'CLASS_SWORDMASTER', 'CLASS_SWORDMASTER_F'),
    'dancer': ('CLASS_DANCER', 'CLASS_BARD'),
    'magic': ('CLASS_MAGE', 'CLASS_MAGE_F', 'CLASS_SHAMAN', 'CLASS_SHAMAN_F', 'CLASS_MONK',
              'CLASS_SAGE', 'CLASS_SAGE_F', 'CLASS_DRUID', 'CLASS_DRUID_F', 'CLASS_SUMMONER',
              'CLASS_SUMMONER_F', 'CLASS_MAGE_KNIGHT', 'CLASS_MAGE_KNIGHT_F',
              'CLASS_MANAKETE_MYRRH'),
    'lord': ('CLASS_EIRIKA_LORD', 'CLASS_EPHRAIM_LORD', 'CLASS_EIRIKA_MASTER_LORD',
             'CLASS_EPHRAIM_MASTER_LORD'),
    'trainee': ('CLASS_RECRUIT', 'CLASS_RECRUIT_T1', 'CLASS_RECRUIT_T2', 'CLASS_JOURNEYMAN',
                'CLASS_JOURNEYMAN_T1', 'CLASS_JOURNEYMAN_T2', 'CLASS_PUPIL', 'CLASS_PUPIL_T1',
                'CLASS_PUPIL_T2'),
}

# Hero sits with axes (Gerik's and Garcia's hand axes, 0007); Assassin with thieves (Colm's line).
MAXIMA = {'flier': 2, 'healer': 2, 'mounted': 3, 'armour': 1, 'archer': 1, 'axe': 2,
          'thief': 1, 'sword': 2, 'dancer': 1}


def class_group():
    """CLASS_X -> its group. A class in two groups raises."""
    out = {}
    for group, classes in GROUPS.items():
        for c in classes:
            if c in out:
                raise ValueError('%s is in both %s and %s' % (c, out[c], group))
            out[c] = group
    return out


def env():
    """What PT_CAMPAIGN carries for Bot.team: {'groups': {class id (str): group}, 'maxima'}.
    Ids are the decomp's numbers, so a name the decomp does not have raises."""
    values = inject.class_ids.vanilla_class_values()
    return {'groups': {str(values[c]): g for c, g in class_group().items()},
            'maxima': dict(MAXIMA)}
