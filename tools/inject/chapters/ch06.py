"""Chapter 6 (#26): its injector and everything only it reads.
"""
import heapq
import os
import re
import sys

from inject.cast import _classed_cast, CLASS_LOADOUT, ENEMY_BASE_SLOT, GUEST_PORTRAIT_MAP
from inject.chapter_ids import (CH06_BOAT_PIDS, CH06_BOAT_TALK_FLAGS, CH06_BOAT_TALK_MSGS,
                                CH06_BOAT_TALK_SCRIPTS, CH06_CHAPTER_YAML, CH06_GOAL_STATUS_MSG,
                                CH06_GOAL_WINDOW_MSG, CH06_OPENING_CARD_MSG, CH06_OPENING_MSGS,
                                CH06_OPENING_QUIP_MSG)
from inject.decomp import _replace_brace_block, REPO
from inject.chapter_frame import write_event_group
from inject.event_scripts import assert_event_scripts_defined, declare_event_script
from inject.class_ids import ChapterClassIds
from inject.hosting import _load_chapter_yaml, _retarget_host_chapter
from inject.hosts import CH06_EVENT_GROUP, CH06_HOST_INDEX
from inject.maps import _register_chapter_map, _register_tileset, TILESET_STEMS
from inject.terrain import _class_terrain_move_costs, _map_terrain_grid
from inject.paths import (
    CH05_EVENTSCRIPT_H, CH06_EVENTINFO_H, CH06_EVENTSCRIPT_H, CP_DATA_C, TEXTS_TXT)
from inject.recruit import talk_recruit_char_entries, talk_recruiters
from inject.scenes import (_emit_scene_beats, _make_fid, _prepend_defeat_quote, _split_event_beats,
                           _write_chapter_title_card, flag_defeat_quote, split_on_stage_cut)
from inject.text import (
    _script_to_message, dev_placeholder_scene, goal_window_body, name_message_body, set_message_body,
    vanilla_name_text_id)
from inject.units import (
    _ally_unit_entry, _deploy_cap_entries, _enemy_unit_entry, _items_with_drop_last,
    chapter_label_constant, declare_unit_table, enemy_ai_initialiser, safe_ai_clients)
from inject.villages import authored_boxes, save_all_bonus_script, village_script


CH06_BEGINNING_SCRIPT = 'EventScr_Ch7_BeginningScene'
CH06_ENDING_SCRIPT = 'EventScr_Ch7_EndingScene'
# The Hard-only reinforcement wave. Vanilla Ch6 keeps three extra Cavaliers in their own
# UnitDefinition array and loads them from a TURN-4 PLAYER-PHASE event through
# `EventScr_LoadReinforceHardMode`, which is Difficult-only (it returns early on tutorial and
# on not-hard, events_script_utils.c). We field the same three on the same clock through the
# same shared script -- so "Hard only" is FE8's own predicate and not a dial of ours.
CH06_HARD_WAVE_TURN = 4
CH06_HARD_WAVE_SCRIPT = 'EventScr_089F2CFC'      # slot 7's own turn-1 Murray bark; unreachable
                                                 # once the Turn list below is stripped (verified
                                                 # free by grep, the ch03/ch04/ch05 idiom)
CH06_PREP_SCRIPT = 'EventScr_08591FD8'           # the shared CLEAN/PREP/CLEAN script (cf. ch05)

# Our OWN roster tables (declare_unit_table). Named for the chapter whose units are in them.
CH06_ALLY_TABLE = 'MS_Ch06DeployCap'             # the never-LOADed PREP cap template
CH06_BOOT_SEED_TABLE = 'MS_Ch06BootSeed'         # --ch06-boot only: an armed party from a cold start
CH06_LINE_TABLE = 'MS_Ch06Line'                  # the 24-strong merfolk line (#360's placement)
CH06_HARD_WAVE_TABLE = 'MS_Ch06Wave4Hard'        # vanilla Ch6's Difficult-only cavalry trio
CH06_BOAT_TABLE = 'MS_Ch06Boats'                 # the two marooned boats, GREEN and killable

CH06_LAYOUT = ('Ch06MaerMonsterMap', 'ch06-maer-monster')   # (asset label, maps/ stem)
CH06_TILESET = 'snowy-bern-ice'                  # stem 'SnowIce' (TILESET_STEMS); ch06 is its
                                                 # first and only user, so it self-registers --
                                                 # the Cave/inject_ch03 idiom. _register_chapter_map
                                                 # sys.exits by asset label without this.
CH06_GOAL_DONOR = 17                             # a CLEAN untouched vanilla defeat_boss template.

# Nerra rides a real vanilla CHARACTER slot rather than a raw pid (ENEMY_BASE_SLOT): her
# chapter's parity_reference IS FE8 Ch6, so the boss the bar measures against and the slot she
# deploys on are the same character and she inherits his real line (#284/#334). Her defeat
# quote is FLAGGED and SILENT -- .msg = 0 -- because the merfolk do not speak, which is the
# contrast Messie's scene is built on; SetPidDefeatedFlag still raises EVFLAG_DEFEAT_BOSS, and
# that flag is what fires the win (CA_BOSS alone fires nothing). Same idiom as ch03's grell.
CH06_BOSS_PID = ENEMY_BASE_SLOT['nerra']
CH06_GENERIC_PID = '0x80'                        # autolevelled trash -- vanilla Ch7's own generic,

# The rescue boats deploy as `fleet`: vanilla's own ship, which ships a 32x32 map sprite (SMSId
# 0x41) and a 19 HP / 5 Def hull, which a boat's `personal:` line may raise (the west hull is 28).
CH06_CLASS_IDS = ChapterClassIds('ch06')
CH06_ITEM_IDS = {'iron-lance': 'ITEM_LANCE_IRON', 'javelin': 'ITEM_LANCE_JAVELIN',
                 'iron-sword': 'ITEM_SWORD_IRON', 'iron-blade': 'ITEM_BLADE_IRON',
                 'steel-lance': 'ITEM_LANCE_STEEL',
                 'halberd': 'ITEM_AXE_HALBERD', 'horseslayer': 'ITEM_LANCE_HORSESLAYER',
                 'iron-bow': 'ITEM_BOW_IRON', 'flux': 'ITEM_DARK_FLUX',
                 'thunder': 'ITEM_ANIMA_THUNDER', 'mend': 'ITEM_STAFF_MEND',
                 'elixir': 'ITEM_ELIXIR',
                 # the two `fe_base:` redirects -- the YAML's flavour names for the Venin Lance
                 # (vanilla's Venin Axe, re-classed with its Fighter) and the Bael's Venin Claw
                 'venin-lance': 'ITEM_LANCE_VENIN', 'venin-claw': 'ITEM_MONSTER_VENINCLW',
                 # the boats' rewards, owed to the boarding pass: the east hull's Antitoxin and
                 # the save-them-both Orion's Bolt vanilla Ch6 grants in its ending
                 'antitoxin': 'ITEM_ANTITOXIN', 'orions-bolt': 'ITEM_ORIONSBOLT'}


#  AI_A_08's do-not-attack list, and the ch06 hulls it is repointed at. Vanilla declares it
#  `u8 gUnknown_085A8B3C[] = { CHARACTER_CITIZEN, 0, 0, 0 }` and NOTHING in FE8 uses AI_A_08 --
#  swept over events_udefs.c at decomp HEAD, `.ai = {0x8,` appears zero times -- so the index and
#  its list are both free for us to spend.
BOAT_SAFE_AI_INDEX = 0x8            # gAi1ScriptTable[AI_A_08] = gAiScript_ActionInRange_ExceptCivilian
BOAT_SAFE_AI_LIST = 'gUnknown_085A8B3C'


def repoint_boat_safe_ai_list(char_ids, why, owner):
    """Point AI_A_08's do-not-attack list at OUR rescue targets instead of vanilla's Citizen.

    ch06's map puts a killable hull inside the merfolk line, which vanilla Ch6 never does: over
    Ch6Map, with each class's own cost table, ZERO of its seventeen strikers can reach a
    villager in one turn. Ours reach a boat on enemy phase 1, four of them, and a hull tuned as
    a one-pursuer fuse sinks on turn 4 instead of 7. Vanilla buys that protection with TERRAIN
    -- a mountain ring no Armour or Cavalier can cross -- and our frozen lake has no analogue,
    so we buy it with the AI byte vanilla itself provides for exactly this job.

    `AI_A_08` is `gAiScript_ActionInRange_ExceptCivilian`: the standard offensive action run
    through `AiIsUnitEnemyAndNotInScrList`, which calls `AiIsInShortList(script->unk_08, ...)`
    against each candidate's `pCharacterData->number`. `unk_08` is the list below. Copying the
    byte alone does NOT protect our hulls, because the list holds a literal character id and
    ours are raw pids of our own -- the same trap `repoint_escort_safe_ai_list` documents for
    AI_A_07, and this is that function's twin.

    THE LIST IS WIDENED, and that is not cosmetic. `AiIsInShortList` takes a `const u16*` and
    stops on a zero entry, so vanilla's four BYTES are the two-entry u16 short list
    `{ CHARACTER_CITIZEN, TERMINATOR }` -- it holds ONE id, not four. Writing both hull pids
    into the byte slots would produce the single garbage id 0xBCBB and protect neither. Two ids
    need six bytes: `{ id, 0, id, 0, 0, 0 }` reads as `{ id, id, TERMINATOR }`.

    SAFE BECAUSE THE LIST HAS NO CLIENTS AT ALL. Unlike AI_A_07 (vanilla Ch5's Joshua), AI_A_08
    is referenced by no vanilla UnitDefinition in the ROM, so repointing its list changes the
    behaviour of nothing that vanilla ships.
    """
    assert_boat_safe_ai_is_single_chapter(owner)
    with open(CP_DATA_C, encoding='utf-8') as f:
        source = f.read()
    body = ', '.join('%s, 0' % c for c in char_ids) + ', 0, 0'
    pattern = (r'(u8 CONST_DATA %s\[\] = \{ )CHARACTER_CITIZEN, 0, 0, 0( \};)'
               % BOAT_SAFE_AI_LIST)
    source, count = re.subn(pattern, r'\g<1>%s\g<2>' % body, source, count=1)
    if count != 1:
        sys.exit('ERROR: %s is not vanilla\'s { CHARACTER_CITIZEN, 0, 0, 0 } in %s -- AI_A_08\'s '
                 'do-not-attack list moved or was already patched, so %s would go unprotected'
                 % (BOAT_SAFE_AI_LIST, CP_DATA_C, why))
    with open(CP_DATA_C, 'w', encoding='utf-8') as f:
        f.write(source)


def assert_boat_safe_ai_is_single_chapter(owner):
    """Refuse the repoint if any chapter but `owner` has picked up AI_A_08.

    `assert_escort_safe_ai_has_one_client`'s twin, and it exists because AI_A_08's list is
    exactly as GLOBAL as AI_A_07's. Once repointed it names ch06's two hull pids, so ANY unit
    anywhere carrying `{0x8, ...}` inherits "will not attack those pids".

    The invariants differ, and the difference is the point. AI_A_07's is one UNIT, because
    vanilla ships one client and a second would inherit our escort's immunity by accident.
    AI_A_08's is one CHAPTER, because vanilla ships NO clients -- so the chapter that claims
    the list may spend it on as many of its own units as it likes (ch06 spends it on ten), and
    the hazard is a DIFFERENT chapter picking the byte up for its own reasons. That unit would
    silently refuse to attack pids its chapter has never heard of, and the next chapter to want
    this byte for its own rescue targets would repoint the list out from under ch06 with
    nothing anywhere to say so.
    """
    strays = [c for c in safe_ai_clients(BOAT_SAFE_AI_INDEX)
              if not c.startswith(owner + '.')]
    if strays:
        sys.exit('ERROR: AI_A_08 (%s) is claimed by %s, but %s also carry it. The '
                 'do-not-attack list is GLOBAL and now names %s\'s rescue targets, so those '
                 'units silently inherit an immunity to pids their own chapter never declared. '
                 'Give them a different ACTION byte, or move the list to a second index.'
                 % (BOAT_SAFE_AI_LIST, owner, ', '.join(strays), owner))


# ── The merfolk surface (#26) ─────────────────────────────────────────────────────────────
# In beat B the line breaks through the water and WALKS to its turn-1 tiles (Nicolas,
# 2026-10-09): each unit LOADs on a channel tile and a one-step REDA walks it to its YAML
# position, vanilla's own reinforcement entrance. The YAML tile stays the fighting tile, so the
# balance gate, the danger map and the boats' fuses are untouched -- and a skipped scene loads
# them silently, straight onto those tiles.
TERRAIN_RIVER = 0x10
SURFACE_MIN_WALK = 2      # tiles of movement cost: a one-step hop out of the water does not read


def surface_spawns(terrain, units, water=TERRAIN_RIVER, min_walk=SURFACE_MIN_WALK):
    """{key: spawn tile or None} -- the water tile each unit surfaces from.

    `units` is [(key, dest, costs)], in YAML order. A spawn is a `water` tile from which the
    unit's OWN class can walk to `dest` (the REDA path is GenerateBestMovementScript over the
    class cost row, and the tile it stands on is never charged); the nearest such tile at least
    `min_walk` away wins, the nearest of any distance otherwise. Spawns are never shared. A unit
    with no water tile that reaches its post gets None and simply appears where it stands.
    """
    height, width = len(terrain), len(terrain[0])
    taken = {dest for _key, dest, _costs in units}
    out = {}
    for key, dest, costs in units:
        # Reverse Dijkstra from the post: dist[t] = movement spent walking t -> dest, not
        # counting t itself. Water tiles are scored as start points and never walked through.
        dist, heap, scored = {dest: 0}, [(0, dest)], []
        while heap:
            d, (x, y) = heapq.heappop(heap)
            if d > dist.get((x, y), 1 << 30):
                continue
            step = costs[terrain[y][x]]       # walking OFF (x, y) means having entered it
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if not (0 <= nx < width and 0 <= ny < height):
                    continue
                nd = d + step
                if terrain[ny][nx] == water:
                    if (nx, ny) not in taken:
                        scored.append((nd, (nx, ny)))
                    continue
                if costs[terrain[ny][nx]] > 0 and nd < dist.get((nx, ny), 1 << 30):
                    dist[(nx, ny)] = nd
                    heapq.heappush(heap, (nd, (nx, ny)))
        scored = sorted(set(scored))
        far = [c for c in scored if c[0] >= min_walk]
        pick = (far or scored or [None])[0]
        out[key] = pick[1] if pick else None
        if pick:
            taken.add(pick[1])
    return out


def ch06_line_spawns(chap, maps_dir):
    """surface_spawns for ch06's turn-1 line, keyed (enemy id, body index)."""
    from map_placement_preview import class_movement   # local: it imports the injector stack
    _w, _h, terrain = _map_terrain_grid(maps_dir, CH06_LAYOUT[1])
    units = []
    for enemy in chap['enemy_units']:
        if enemy.get('arrives_turn') is not None:
            continue
        costs = _class_terrain_move_costs(class_movement(enemy['class'])[0])
        for index, pos in enumerate(enemy['positions']):
            units.append(((enemy['id'], index), tuple(pos), costs))
    return surface_spawns(terrain, units)


def ch06_reda_symbol(enemy_id, index):
    return 'MS_Ch06Surface_%s_%d' % (re.sub(r'[^A-Za-z0-9]', '_', enemy_id), index)


def ch06_enemy_rows(chap, arrives_turn=None, spawns=None):
    """One UnitDefinition row per authored position for a ch06 deployment wave.

    `arrives_turn=None` selects the turn-1 line; a number selects that reinforcement wave (ch06
    has exactly one, vanilla Ch6's Difficult-only turn-4 trio). The BOSS takes her own vanilla
    CHARACTER slot so her flagged defeat quote keys to her and nothing else; everything else
    shares the slot's autolevelled generic, exactly as vanilla Ch6 and Ch7 both do.

    Positions, levels, inventories and drops are the chapter YAML's (#360); the `.ai` bytes are
    the DONOR's, resolved through `enemy_ai_initialiser` rather than authored here -- ch06 is
    the chapter #335 was written for, whose first draft measured at parity while fielding
    thirteen pursuers against a twin that fields two.
    """
    rows = []
    for enemy in chap['enemy_units']:
        if enemy.get('arrives_turn') != arrives_turn:
            continue
        cls = CH06_CLASS_IDS.for_entry(enemy)
        items = [CH06_ITEM_IDS[item.get('fe_base') or item['id']]
                 for item in enemy.get('inventory', [])]
        drop = enemy.get('item_drop')
        pid = CH06_BOSS_PID if enemy.get('is_boss') else CH06_GENERIC_PID
        for index, (x, y) in enumerate(enemy['positions']):
            carried = list(items)
            # FE8 drops the LAST item, and the YAML names the drop rather than relying on
            # inventory order -- so it is appended, and only to the first body of a `count:`
            # group (vanilla gives exactly one Fighter the axe drop, not all three).
            dropper = bool(drop) and index == 0
            if dropper:
                carried = _items_with_drop_last(carried, CH06_ITEM_IDS[drop])
            # `spawns` (the turn-1 line only): LOAD on the water tile, walk to the post.
            spawn = (spawns or {}).get((enemy['id'], index))
            sx, sy = spawn if spawn else (x, y)
            rows.append(_enemy_unit_entry(
                pid, cls, int(enemy['level']), bool(enemy.get('autolevel')), sx, sy,
                ', '.join(carried) or '0', enemy_ai_initialiser(chap, enemy, index),
                ' /* %s -- %s */' % (enemy['id'], enemy['name']), itemdrop=dropper,
                reda=ch06_reda_symbol(enemy['id'], index) if spawn else None))
    return rows


def ch06_boat_rows(chap):
    """The two marooned fishing boats: GREEN `CLASS_FLEET` units, one raw pid each.

    A UNIT and not painted scenery, which is the whole clock (#360): a boat can be KILLED, and
    a dead one stops offering its boarding Talk exactly as a burned village stops offering
    Visit -- so one mechanism covers the gift and the save-them-both payout, and vanilla Ch6's
    own CHECK_ALIVE gate carries over unchanged.

    Their AI is DERIVED like every enemy's: each boat's `donor:` is vanilla Ch6's boss tile, so
    both inherit `GuardTileAI` -- ActionStanding + NeverMove. That matters rather than being
    decorative. `CLASS_FLEET` has baseMov 3, so a boat with the zero-filled default AI
    (ActionInRange + MoveToEnemy) would *sail off its own outcrop* toward the party, taking the
    pocket, the door and the entire fuse with it.

    They carry nothing. `CLASS_FLEET`'s 19 HP and 5 Def, plus a boat's own `personal:` line
    (RAW_PID_PERSONAL_SOURCES), are the hull the sinking clock is tuned
    against, and its weapon rank is a bow it is never given.
    """
    rows = []
    for boat in chap['rescue_boats']:
        x, y = boat['tile']
        rows.append(_ally_unit_entry(
            None, None, CH06_CLASS_IDS.for_entry(boat), 1, x, y, '0',
            ' /* %s -- marooned crew; killable, and the chapter\'s clock */' % boat['id'],
            allegiance='GREEN', char=CH06_BOAT_PIDS[boat['id']],
            ai=enemy_ai_initialiser(chap, boat)))
    return rows


BOARDING_SPEAKER = 'crew'


def ch06_boarding_wiring(campaign, chap):
    """The boarding pass (#26), vanilla Ch6's village in a hull: the Character list's Talk
    entries, one scene per boat, and its message.

    FE8's Talk is a NAMED PAIR -- `CHAR(flag, script, pid_a, pid_b)`, compared for exact equality
    -- so "any party member may board" is one entry per (field PC x boat), every entry for a boat
    sharing that boat's flag: the first boarding sets it and the rest are skipped. The roster is
    generated (`talk_recruiters`), never hand-listed. A sunk hull is dead, so its Talk is gone,
    exactly as a burned village stops offering Visit.

    The scene is `village_script`: the crew's line over the boat backdrop, then the reward into
    the boarder's hands. Returns (character list body, [(symbol, body, comment)],
    [(message id, body)])."""
    boarders = talk_recruiters(campaign, chap['chapter_number'])
    entries, scripts, messages = '', [], []
    for boat in chap['rescue_boats']:
        bid, talk = boat['id'], boat['talk']
        flag, symbol, msg = (CH06_BOAT_TALK_FLAGS[bid], CH06_BOAT_TALK_SCRIPTS[bid],
                             CH06_BOAT_TALK_MSGS[bid])
        entries += talk_recruit_char_entries(boarders, CH06_BOAT_PIDS[bid], flag, symbol)
        reward = talk.get('reward') or []
        item = CH06_ITEM_IDS[reward[0]['id']] if reward else None
        scripts.append((symbol, village_script(msg, item, talk['background']),
                        'ch06 boarding the %s -- the crew\'s line (0x%X)%s'
                        % (bid, msg, ', then %s' % item if item else '')))
        boxes = authored_boxes(bid, talk.get('text'), 'talk.text')
        messages.append((msg, _script_to_message(
            [{BOARDING_SPEAKER: line} for _who, line in boxes],
            {BOARDING_SPEAKER: ('[OpenMidLeft]', '[%s]' % talk['face'])})))
    return '{\n' + entries + '    END_MAIN\n}', scripts, messages


# ── The opening (#26) ─────────────────────────────────────────────────────────────────────
# Beat A plays over backdrops before the map exists: the Bremen town CG under the location card
# (vanilla's Serafew-village establishing shot), then a cut to a plain stone hall for the
# dialogue. Beat B plays ON THE MAP after prep, on the party -- ch05 0x9C2's after-prep shape.
CH06_OPENING_TOWN_BG = 'BG_MS_BREMEN_WINTER'     # Fenriel's lakeside town, vendored for Bremen
CH06_OPENING_HALL_BG = 'BG_CASTLE_BRIGHT'        # vanilla's plainest stone hall
# Three seats. The Speaker holds mid-right alone; Braulo leads the party from mid-left; RBG and
# Pinky SHARE far-left, father and son trading the seat on Pinky's two lines. Pinky's first cut sat
# far-right, and on film it put him off the screen's edge behind Dorbulgruf (2026-10-09).
CH06_OPENING_HOME = {'braulo': '[OpenMidLeft]', 'prof-rbg': '[OpenFarLeft]',
                     'dorbulgruf': '[OpenMidRight]', 'pinky': '[OpenFarLeft]'}
# Beat B's five speakers: Meesmickle takes Wolfram's seat, the one used longest ago.
CH06_OPENING_ICE_SEATS = {'wolfram': '[OpenMidLeft]', 'pinky': '[OpenFarLeft]',
                          'braulo': '[OpenMidRight]', 'rootis': '[OpenFarRight]',
                          'meesmickle': '[OpenMidLeft]'}


def ch06_opening_beats(chap):
    """(location card, [hall, ice, quip]) off the locked chapter_start script.

    Beat B is cut in two at its one `stage_cut` (split_on_stage_cut refuses zero or two): the
    camera has to leave the party to show the merfolk surfacing, and a paused talk cannot survive
    a camera move under its bubble, so Meesmickle's answer is a message of its own.
    """
    card, beats = _split_event_beats(chap, 'chapter_start', 'ch06 opening', CH06_OPENING_MSGS)
    ice, _direction, quip = split_on_stage_cut(beats[1], 'ch06 opening beat B')
    return card, [beats[0], ice, quip]


def ch06_opening_head(hall_label):
    """The event-script head before LOMA: the town under its card, then the hall's dialogue.

    The second BACG needs its load mode re-armed (REMOVEPORTRAITS) -- the card and the fades
    leave `activeTextType` where a bare BACG is a no-op (the ch03/ch04 stale-BG fix).
    """
    return ('    REMOVEPORTRAITS\n'
            '    BACG(%s) /* Bremen from the lake: the establishing shot */\n'
            '    FADU(16)\n'
            '    BROWNBOXTEXT(0x%X, 8, 8) /* "Bremen" location card */\n'
            '    FADI(16)\n'
            '    REMOVEPORTRAITS /* re-arm BACG BG-load mode before the cut */\n'
            '    BACG(%s) /* CUT inside: the Speaker\'s hall */\n'
            '    FADU(16)\n' % (CH06_OPENING_TOWN_BG, CH06_OPENING_CARD_MSG, CH06_OPENING_HALL_BG)
            + '    Text(0x%X) /* A -- %s */\n' % (CH06_OPENING_MSGS[0], hall_label)
            + '    REMA\n'
              '    FADI(16) /* fade the hall out; LOMA builds the lake next */\n')


def ch06_opening_ice_block(camera_tile, lake_tile):
    """Beat B, AFTER the prep CALL: the map fades up on the party, then cuts to the lake.

    The camera is set before each message and never inside one: a camera move under an open
    bubble scrolls the map out from beneath it (ch05's moose note). So the shadows are talked
    about on the party, the talk ENDS, the camera pans to the middle of the lake, the line LOADs
    in shot, and Meesmickle answers over it. CUMO_AT takes a tile, never a unit -- any speaker
    here may be benched at prep.
    """
    x, y = camera_tile
    lx, ly = lake_tile
    return ('    FADU(16) /* the prep prologue left the screen black */\n'
            '    CAMERA(%d, %d) /* the SCROLL -- CUMO alone only draws a cursor */\n'
            '    CUMO_AT(%d, %d) /* on the party, standing on the ice */\n'
            '    STAL(60)\n'
            '    CURE\n'
            '    Text(0x%X) /* B -- on the ice: Wolfram reads the boats, the shadows multiply */\n'
            '    CAMERA(%d, %d) /* PAN to the middle of the lake, where the shadows were */\n'
            '    STAL(30)\n'
            '    LOAD1(0x1, %s) /* the merfolk break through the water */\n'
            '    ENUN\n'
            '    STAL(30)\n'
            '    Text(0x%X) /* ...and Meesmickle answers */\n'
            % (x, y, x, y, CH06_OPENING_MSGS[1], lx, ly, CH06_LINE_TABLE, CH06_OPENING_QUIP_MSG))


def ch06_lake_camera_tile(chap):
    """Where the camera pans for the merfolk: the boss's own tile, the centre shelf."""
    boss = next(e for e in chap['enemy_units'] if e.get('is_boss'))
    return tuple(boss['positions'][0])


def ch06_party_camera_tile(chap):
    """The first deploy slot: the lord's, and the lord is force-deployed, so it is never empty."""
    return tuple(chap['deployment']['deploy_slots'][0])


def inject_ch06(campaign, boot=False, verbose=True):
    """Host Ch6 "The Maer Monster" (#26) on slot 7: the frozen mouth of Maer Dualdon retiled
    from Ch13 Ephraim, vanilla Ch6's own twenty-four re-dressed as merfolk on our placement,
    the two marooned boats as killable GREEN units, the real PREP deploy, and DefeatBoss(Nerra).

    THREE different vanilla chapters meet here and none of them substitutes for another --
    the DONOR is Ch13 Ephraim (geometry and the deploy tiles), the BAR is Ch6 (classes, levels,
    inventories, drops and every `.ai` byte, derived per unit), and the HOST is slot 7, which
    supplies storage and nothing else. The CH06_* constant block states that once.

    The boarding pass is wired (ch06_boarding_wiring): Grynsk's and Tali's scenes, the east
    hull's Antitoxin, and the save-both Orion's Bolt in the ending. The OPENING is wired: beat A
    in Bremen's hall over backdrops, then LOMA and prep, then beat B on the ice, which cuts to the
    lake where the merfolk line LOADs in shot (it is NOT on the map during prep). The ending plays the
    victory sting, the payout, and the dev-placeholder landing. Nerra's defeat quote is FLAGGED
    but SILENT by design: the merfolk do not speak, and Messie does.

    DEFERRED to follow-up passes: Messie's boss-death cutscene, the ending scene, and the
    title-card art. ch06's ending parks on the dev placeholder until ch07 hosts, exactly as
    ch05's did.
    """
    maps_dir = os.path.join(REPO, 'campaigns', campaign, 'maps')
    chap = _load_chapter_yaml(campaign, CH06_CHAPTER_YAML)
    op_card, op_beats = ch06_opening_beats(chap)

    # 1. Map: register the snowy-bern-ice tileset (ch06 is its only user, so it self-registers
    #    -- the Cave/inject_ch03 idiom) and the painted layout, then point slot 7 at them and
    #    borrow slot 17's clean defeat_boss goal banner.
    _register_tileset(campaign, CH06_TILESET, TILESET_STEMS[CH06_TILESET],
                      'Manchego Stars snowy-bern-ice tileset (#26)')
    indices = _register_chapter_map(maps_dir, CH06_LAYOUT,
                                    'Manchego Stars ch06 Maer Dualdon layout (#26)')
    obj_idx, pal_idx, cfg_idx, layout_idx = indices
    host = _retarget_host_chapter(
        CH06_HOST_INDEX, CH06_GOAL_DONOR, 'defeat_boss',
        'ERROR: slot %d goal is not the vanilla defeat_boss template (ch06 DefeatBoss donor)'
        % CH06_GOAL_DONOR, indices, chap['chapter_number'], CH06_EVENT_GROUP,
        (CH06_GOAL_WINDOW_MSG, CH06_GOAL_STATUS_MSG))

    # Fog is not written here any more either -- `apply_chapter_fog` writes ch06's declared
    # `fog: none` along with every other hosted chapter's (#365). This block is what the
    # generalisation was built from: slot 7 SHIPS `initialFogLevel: 3` (vanilla Ch7 is fogged),
    # and ch06's donor puts 40% of the map in concentric water with eight crossings, so the
    # route is the puzzle and one the player is meant to see and solve. Inheriting three-tile
    # vision would have hidden the entire design and failed nothing.

    # 2. Rosters. The cap template is NEVER LOADed -- PREP reads its entry count (the cap) and
    #    the YAML's deploy_slots tiles, then redeploys the player's picks (cf. ch03/ch04/ch05).
    cast, _ = _classed_cast(campaign, available_at=chap['chapter_number'])
    for uid, _slot, ce, _dce, _level in cast:
        if ce not in CLASS_LOADOUT:
            sys.exit('ERROR: no loadout for %s (ch06 field roster %s)' % (ce, uid))
    leader = 'CHARACTER_%s' % cast[0][1].upper()
    cap_rows = _deploy_cap_entries(chap, cast, leader, 'ch06')
    declare_unit_table(CH06_ALLY_TABLE, cap_rows,
                       'ch06 PREP deploy-cap template (never LOADed; the CAP is the parity)')
    # --ch06-boot only: the field roster armed from CLASS_LOADOUT on the deploy tiles, so PREP
    # has a party to pick from a COLD New Game. The real chain omits it -- the party persists.
    slots = chap['deployment']['deploy_slots']
    seed_rows = [_ally_unit_entry(leader, slot, dce, level, x, y,
                                  ', '.join(CLASS_LOADOUT[ce]),
                                  ' /* %s -- ch06 boot party seed (armed; PREP re-picks) */' % uid)
                 for (uid, slot, ce, dce, level), (x, y) in zip(cast, slots)]
    declare_unit_table(CH06_BOOT_SEED_TABLE, seed_rows,
                       'ch06 --ch06-boot armed party seed (cold-start PREP fodder)')

    # The line SURFACES in beat B: each unit LOADs on a channel tile and walks to its post.
    spawns = ch06_line_spawns(chap, maps_dir)
    line_rows = ch06_enemy_rows(chap, spawns=spawns)
    redas = [(ch06_reda_symbol(eid, i), x, y)
             for e in chap['enemy_units'] if e.get('arrives_turn') is None
             for i, (x, y) in enumerate(e['positions']) for eid in [e['id']]
             if spawns.get((eid, i))]
    declare_unit_table(CH06_LINE_TABLE, line_rows,
                       'ch06 turn-1 line: the merfolk of Maer Dualdon, on our placement (#360), '
                       'surfacing from the channels', redas=redas)
    wave_rows = ch06_enemy_rows(chap, arrives_turn=CH06_HARD_WAVE_TURN)
    if not wave_rows:
        sys.exit('ERROR: ch06 declares no enemies arriving on turn %d, but a wave table and a '
                 'TurnEventPlayer are wired for it' % CH06_HARD_WAVE_TURN)
    # The wave rides `EventScr_LoadReinforceHardMode`, so EVERY unit in it is Difficult-only
    # whether or not it says so. A row that arrived on turn 4 without `hard_mode_only` would
    # simply never appear on Normal, and the chapter YAML would be describing a force the ROM
    # does not field -- which is the failure #48's static bar cannot see, because it folds
    # vanilla's Hard array in on both sides.
    late = [e['id'] for e in chap['enemy_units']
            if e.get('arrives_turn') == CH06_HARD_WAVE_TURN and not e.get('hard_mode_only')]
    if late:
        sys.exit('ERROR: ch06 turn-%d arrivals %s are not `hard_mode_only:`, but the only '
                 'turn-%d load is the Difficult-mode one -- they would never appear'
                 % (CH06_HARD_WAVE_TURN, ', '.join(late), CH06_HARD_WAVE_TURN))
    declare_unit_table(CH06_HARD_WAVE_TABLE, wave_rows,
                       'ch06 Difficult-only turn-%d wave (vanilla Ch6\'s own reinforce array)'
                       % CH06_HARD_WAVE_TURN)

    # The two marooned boats: GREEN, killable, one pid each so the payout can ask about them
    # separately. LOADed by the beginning scene beside the line -- they are on the field from
    # turn 1, because the clock starts when the chapter does.
    boat_rows = ch06_boat_rows(chap)
    declare_unit_table(CH06_BOAT_TABLE, boat_rows,
                       'ch06 the Burly Ram and the Pronged Goat: green hulls in their pockets, '
                       'and the chapter\'s real difficulty (#26)')
    # ...and take the hulls off the MENU for every unit that is not their declared pursuer.
    # Four of the line's strikers reach a hull on enemy phase 1 -- vanilla Ch6's line reaches
    # its villagers NEVER -- so the chapter's overridden units carry AI_A_08 and this points
    # its do-not-attack list at the two boat pids. See repoint_boat_safe_ai_list.
    repoint_boat_safe_ai_list([CH06_BOAT_PIDS['boat-east'], CH06_BOAT_PIDS['boat-west']],
                              'ch06 the two marooned hulls', owner='ch06')

    # 3. Wire ours into the host slot's event group; every list not named here is written
    #    empty, INCLUDING Location. That is a real decision and not an oversight: vanilla Ch7's
    #    list is a Seize plus two Houses, and ch06 has no village terrain anywhere on the map
    #    (the two former village bodies are the boat pockets, and their doors were repainted to
    #    FOREST precisely so no dead Visit prompt survives -- see the YAML's
    #    `terrain_divergence`). The boarding Talks are CHARACTER events, not Location ones
    #    (ch06_boarding_wiring). The roster is OUR table: pointing at vanilla
    #    Ch7's would deploy the party on another map's coordinates, with PREP running, the map
    #    drawn, and a load test that PASSes.
    board_events, board_scripts, board_messages = ch06_boarding_wiring(campaign, chap)
    write_event_group('ch06', CH06_EVENTINFO_H, CH06_EVENT_GROUP, lists={
        'characterBasedEvents': board_events,
        'turnBasedEvents':
            '{\n    TurnEventPlayer(0, %s, %d) /* Difficult-only cavalry wave: %d */\n'
            '    END_MAIN\n}' % (CH06_HARD_WAVE_SCRIPT, CH06_HARD_WAVE_TURN, len(wave_rows)),
        # Misc = the win/lose machinery and nothing else. DefeatBoss is an AFEV on
        # EVFLAG_DEFEAT_BOSS, which Nerra's FLAGGED defeat quote sets on her death (step 5) --
        # CA_BOSS alone fires nothing.
        'miscBasedEvents': '{\n    DefeatBoss(%s)\n    CauseGameOverIfLordDies\n    END_MAIN\n}'
                           % CH06_ENDING_SCRIPT,
    }, roster=CH06_ALLY_TABLE, scenes=(CH06_BEGINNING_SCRIPT, CH06_ENDING_SCRIPT))

    # 4. The beginning scene, the Hard wave script and the ending. The beginning: beat A over
    #    backdrops, LOMA rebuilds the battle map fresh, both hulls LOAD, then CALL Preparations
    #    (which reads the never-LOADed cap template), then beat B on the ice, which cuts to
    #    the lake and LOADs the merfolk line in shot. No FADU before the prep CALL -- the shared prep
    #    prologue fades to black itself, so revealing the freshly LOMA'd map here only flashes
    #    it (the ch03/ch04/ch05 note, same reason).
    with open(CH06_EVENTSCRIPT_H, encoding='utf-8') as f:
        script = f.read()
    seed_load = ('    LOAD1(0x1, %s) /* --ch06-boot: found an armed party */\n'
                 '    ENUN\n' % CH06_BOOT_SEED_TABLE) if boot else ''
    beginning = ('{\n'
                 '    MUSC(SONG_TENSION)\n'
                 + ch06_opening_head('Bremen\'s hall: Dorbulgruf, the beast, the bounty') +
                 '    SVAL(EVT_SLOT_B, 0x0) /* map camera origin for the reload */\n'
                 '    LOMA(0x%X) /* RestartBattleMap -- build the ch06 map fresh */\n'
                 % CH06_HOST_INDEX
                 + '    LOAD1(0x1, %s) /* the two marooned boats, green in their pockets */\n'
                   '    ENUN\n' % CH06_BOAT_TABLE
                 + seed_load
                 + '    CALL(%s) /* preparations: pick %d; lord force-deployed */\n'
                 % (CH06_PREP_SCRIPT, chap['deployment']['deploy_limit'])
                 + ch06_opening_ice_block(ch06_party_camera_tile(chap), ch06_lake_camera_tile(chap))
                 + '    ENUT(8)\n    EVBIT_T(7)\n    ENDA\n}')
    script = _replace_brace_block(script, CH06_BEGINNING_SCRIPT + '[] =', beginning,
                                  CH06_EVENTSCRIPT_H)
    # The wave, through FE8's OWN Difficult-mode predicate: EventScr_LoadReinforceHardMode
    # reads the slot-2 table and returns early on tutorial and on not-hard. Vanilla Ch6 loads
    # its three extra Cavaliers with these exact two lines.
    script = _replace_brace_block(
        script, CH06_HARD_WAVE_SCRIPT + '[] =',
        '{\n    SVAL(EVT_SLOT_2, %s)\n'
        '    CALL(EventScr_LoadReinforceHardMode) /* Difficult only -- FE8\'s own predicate */\n'
        '    EVBIT_T(7)\n    ENDA\n}' % CH06_HARD_WAVE_TABLE, CH06_EVENTSCRIPT_H)
    # The ending: the victory sting, then the dev-placeholder landing. ch07 is not hosted, so
    # this parks exactly where ch05's did until ch06 hosted; the Messie scene and the ending
    # cutscene are the dialogue pass's, and neither is stubbed with placeholder prose here.
    # The save-both payout is vanilla Ch6's own: CHECK_ALIVE on every civilian, the Orion's Bolt
    # only on a clean sweep. Boarding is not required, only keeping both hulls afloat.
    hulls = {b['id']: CH06_BOAT_PIDS[b['id']] for b in chap['rescue_boats']}
    script = _replace_brace_block(
        script, CH06_ENDING_SCRIPT + '[] =',
        '{\n    MUSC(SONG_VICTORY)\n'
        + save_all_bonus_script(hulls, CH06_ITEM_IDS[chap['economy']['save_all_bonus']],
                                check='CHECK_ALIVE')
        + '    FADI(16) /* fade the lake out into the dev-placeholder landing */\n'
        + dev_placeholder_scene() + '    ENDA\n}', CH06_EVENTSCRIPT_H)
    with open(CH06_EVENTSCRIPT_H, 'w', encoding='utf-8') as f:
        f.write(script)
    # The boarding scenes APPEND, so they follow the bulk rewrite above (ch05's ordering rule).
    for symbol, body, comment in board_scripts:
        declare_event_script(CH06_EVENTSCRIPT_H, symbol, body, comment)
    assert_event_scripts_defined(CH06_EVENTSCRIPT_H, [s for s, _b, _c in board_scripts])

    # 5. Texts + the flagged defeat quote that IS the win trigger.
    with open(TEXTS_TXT, encoding='utf-8') as f:
        lines = f.read().split('\n')
    set_message_body(lines, host['chapTitleTextId'], name_message_body(chap['title']))
    boss = next(e for e in chap['enemy_units'] if e.get('is_boss'))
    set_message_body(lines, host['goal']['statusObjectiveTextId'],
                     name_message_body('Defeat ' + (boss.get('fe_name') or boss['name'])))
    set_message_body(lines, host['goal']['windowTextId'], goal_window_body('Defeat boss'))
    # Nerra rides CHARACTER_NOVALA, so his nameplate leaks onto her unit window and her death
    # unless it is rewritten -- the same rename ch01 and ch02 do for their borrowed boss slots.
    set_message_body(lines, vanilla_name_text_id(CH06_BOSS_PID.replace('CHARACTER_', '')),
                     name_message_body(boss.get('fe_name') or boss['name']))
    for msg_id, body in board_messages:
        set_message_body(lines, msg_id, body)
    # The opening's card and its two beats. The Speaker's face rides GUEST_PORTRAIT_MAP (Murray).
    set_message_body(lines, CH06_OPENING_CARD_MSG, name_message_body(op_card))
    _emit_scene_beats(lines, CH06_OPENING_MSGS + (CH06_OPENING_QUIP_MSG,), op_beats,
                      _make_fid({}, 'ch06 opening: unknown cutscene speaker',
                                fallback=GUEST_PORTRAIT_MAP),
                      CH06_OPENING_HOME,
                      overrides=[None, CH06_OPENING_ICE_SEATS, CH06_OPENING_ICE_SEATS])
    # The boats' name plates are NOT written here: they are RAW_PID_PORTRAITS rows, and
    # inject_names writes every one of those off that registry (appending the ones whose donor
    # is an id we own). Writing them again here would make this injector a second owner of the
    # same decision, and the two copies would drift.
    with open(TEXTS_TXT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    _write_chapter_title_card(host, 'Ch.6: ' + chap['title'])
    # SILENT and FLAGGED (msg = 0). DisplayDefeatTalkForPid only draws a box when .msg is
    # nonzero, while SetPidDefeatedFlag raises the flag either way (eventinfo.c) -- so the
    # merfolk elder dies without a line and the DefeatBoss AFEV still fires. That is the
    # design and not a deferral: the merfolk do not speak, which is what makes Messie's
    # answer land (Nicolas, 2026-08-29). Same idiom as ch03's grell.
    _prepend_defeat_quote(flag_defeat_quote(
        CH06_BOSS_PID, chapter_label_constant(CH06_HOST_INDEX), 'EVFLAG_DEFEAT_BOSS',
        'Nerra (ch06 boss): silent defeat -> DefeatBoss WIN flag'))

    if verbose:
        print('  ch06 map (obj1=%d pal=%d cfg=%d layout=%d) hosted on chapter %d; defeat_boss '
              'goal + DefeatBoss(Nerra) WIN wired, PREP deploy cap %d%s + %d line + t%d:%d '
              'hard-only + %d boat(s)'
              % (obj_idx, pal_idx, cfg_idx, layout_idx, CH06_HOST_INDEX, len(cap_rows),
                 ' (boot-seeded party)' if boot else '', len(line_rows),
                 CH06_HARD_WAVE_TURN, len(wave_rows), len(boat_rows)))


def chain_ch05_to_ch06():
    """Advance ch05's authored ending from the dev landing to the now-hosted ch06."""
    with open(CH05_EVENTSCRIPT_H, encoding='utf-8') as f:
        script = f.read()
    landing = dev_placeholder_scene()
    if script.count(landing) != 1:
        sys.exit('ERROR: expected exactly one ch05 dev-placeholder landing before ch06 chain')
    script = script.replace(
        landing,
        '    MNC2(0x%X) /* -> ch06 "The Maer Monster", hosted on slot %d */\n'
        % (CH06_HOST_INDEX, CH06_HOST_INDEX), 1)
    with open(CH05_EVENTSCRIPT_H, 'w', encoding='utf-8') as f:
        f.write(script)
