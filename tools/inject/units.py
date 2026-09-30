"""Unit tables: the ally/enemy REDA entries, declared `MS_*` unit tables, and AI setup.
"""
import glob
import os
import re
import sys

from yaml_loader import yaml_load
from inject.decomp import REPO, vanilla_decomp_text
from inject.paths import EVENTCALL_H, EVENTS_UDEFS_C


# Enemy AI byte vectors, mirrored from vanilla Ch1's own unit definitions
# (git HEAD src/events/ch1-eventudefs.h) per the YAML's ai_pattern labels.
def enemy_ai_initialiser(chap, enemy, index=0):
    """The `.ai = {...}` initialiser for one of our enemies -- its vanilla DONOR's bytes.

    #335. A chapter picks a vanilla twin so its difficulty is grounded rather than guessed,
    and we already derive that twin's classes, levels, inventories and drops from its
    `UnitDefinition` structs. The `.ai` field of those same structs was the one we never
    read: it got authored by feel through per-chapter label tables, and because #48 computes
    threat from stats and weapons, five chapters shipped a force that measured at parity and
    behaved nothing like its twin. There is no label vocabulary here on purpose -- the labels
    WERE the translation layer the drift lived in.

    `difficulty` is imported locally because it imports us; the decomp-reading layer is the
    lower one, and inverting that at module scope would cycle."""
    import difficulty
    return '{%s}' % ', '.join('0x%X' % b
                             for b in difficulty.enemy_ai_bytes(chap, enemy, index))


def _ally_unit_entry(leader, slot, class_enum, level, x, y, items, comment,
                     allegiance='BLUE', autolevel=False, ai=None, char=None):
    """One non-RED UnitDefinition row (events_udefs.c) for a chapter join/deploy/
    green-ally table. leader=None omits the leaderCharIndex field; autolevel/ai
    toggle their optional lines (GREEN allies use all three). `char` overrides the
    charIndex with a raw pid (a generic green pack shares one pid); default derives it
    from the named cast `slot`."""
    charref = char if char is not None else 'CHARACTER_%s' % slot.upper()
    fields = ['.charIndex = %s,%s' % (charref, comment),
              '.classIndex = %s,' % class_enum]
    if leader:
        fields.append('.leaderCharIndex = %s,' % leader)
    if autolevel:
        fields.append('.autolevel = 1,')
    fields += ['.allegiance = FACTION_ID_%s,' % allegiance,
               '.level = %d,' % level,
               '.xPosition = %d,' % x,
               '.yPosition = %d,' % y,
               '.redaCount = 0,',
               '.items = { %s },' % items]
    if ai:
        fields.append('.ai = %s,' % ai)
    return '    {\n' + ''.join('        %s\n' % f for f in fields) + '    },'


def _deploy_cap_entries(chap, cast, leader, label):
    """The ally deploy "cap template" rows from the chapter's `deployment:` block
    (#107 schema): never LOADed -- the prep flow reads the table's entry count as
    the field cap and its coords as the deploy tiles. classIndex rides
    deploy_class_for (today == the plain vanilla class; custom anims need no clone
    class since the per-character _u25 path, #65 M-B)."""
    dep = chap.get('deployment') or {}
    slots, limit = dep.get('deploy_slots'), dep.get('deploy_limit')
    if not slots:
        sys.exit('ERROR: %s has no deployment.deploy_slots -- a hosted chapter '
                 'needs its deploy tiles authored (they land with the map paint)'
                 % label)
    if len(slots) != limit:
        sys.exit('ERROR: %s deployment.deploy_slots (%d) != deploy_limit (%s)'
                 % (label, len(slots), limit))
    if len(cast) < limit:
        sys.exit('ERROR: %d classed cast < %s deploy_limit %d'
                 % (len(cast), label, limit))
    return [_ally_unit_entry(leader, slot, dce, lv, x, y, '0',
                             ' /* deploy slot %d (cap template, never LOADed) */' % i)
            for i, ((uid, slot, ce, dce, lv), (x, y))
            in enumerate(zip(cast[:limit], slots))]


def _items_with_drop_last(items, drop_enum):
    """`items` with `drop_enum` present exactly ONCE and LAST -- FE8 drops the last item.

    A chapter YAML may name the dropped item in `inventory:` as well as in `item_drop:`, and both
    readings are right: the unit really is carrying it. Appending unconditionally then emits a
    SECOND copy. ch06 is the first chapter whose data spells it both ways and it shipped three
    such units -- {AXE_IRON, AXE_HALBERD, AXE_HALBERD} against a donor carrying two items -- while
    `make difficulty` read PARITY, because the parity model prices the YAML rather than the rows
    the injector emits. Re-ordering rather than merely de-duplicating, because "last" is the part
    the engine actually reads: an inventory that lists the drop first would otherwise drop the
    wrong item.
    """
    return [item for item in items if item != drop_enum] + [drop_enum]


def _enemy_unit_entry(char, class_enum, level, autolevel, x, y, items, ai, comment,
                      itemdrop=False):
    """One enemy UnitDefinition row; autolevel/itemdrop toggle their optional fields."""
    return ('    {\n'
            '        .charIndex = %s,%s\n'
            '        .classIndex = %s,\n'
            '%s'
            '        .allegiance = FACTION_ID_RED,\n'
            '        .level = %d,\n'
            '        .xPosition = %d,\n'
            '        .yPosition = %d,\n'
            '        .redaCount = 0,\n'
            '%s'
            '        .items = { %s },\n'
            '        .ai = %s,\n'
            '    },' % (char, comment, class_enum,
                       '        .autolevel = 1,\n' if autolevel else '',
                       level, x, y,
                       '        .itemDrop = 1,\n' if itemdrop else '',
                       items, ai))



# Every campaign-owned UnitDefinition table carries this prefix. It is the whole point of
# declare_unit_table: a symbol's NAME should say whose data is in it.
MS_TABLE_PREFIX = 'MS_'


def declare_unit_table(symbol, rows, comment):
    """DEFINE a campaign-owned UnitDefinition table, and return its symbol.

    Our chapter rosters used to be written by block-overwriting a vanilla table that the
    host slot's stripped cutscenes had left unreferenced -- ch04's moose still rides a
    symbol our own source comments as "dead Ch5 unit table". That worked, but it has two
    real costs, and the second one is what retires it:

      1. The symbol's NAME LIES. `UnitDef_088B61A8` holds ch05's sixteen tomb-guardians;
         nothing about the name says so, and the vanilla chapter it is named for is not
         even the vanilla chapter ch05 is a retile of. Reading the injector meant holding
         two unrelated numbering offsets in your head -- ours (chapter N hosts on slot
         N+1, because the prologue occupies a real slot) and FE8's own (it inserted Ch5X
         at slot 5, so from slot 6 on the slot index and the symbol name disagree in the
         BASE GAME: slot 6 ships Ch5EventData, slot 7 ships Ch6Events).
      2. It rations us to whatever the host slot happens to leave unreferenced. Slot 5
         freed seven tables; slot 6 frees three, and ch05 needs seven. Squatting would
         have meant reaching into Ch6's world-map ENCOUNTER rosters -- borrowing storage
         from a system we simply hope never runs.

    Defining our own symbol costs one appended table plus one extern, removes the ration
    entirely, and leaves the vanilla table untouched and honestly named. Both files are in
    PATCHED_DECOMP_FILES, so they are restored from HEAD each build and these appends never
    accumulate across builds.

    The host slot's EVENT-LIST symbols (EventListScr_ChN_*, the ChapterEventGroup) are NOT
    covered by this and cannot be: chapter_settings.json points at them structurally. Those
    stay vanilla-named, named once in a per-chapter constant block, and nowhere else.
    """
    with open(EVENTS_UDEFS_C, encoding='utf-8') as f:
        udefs = f.read()
    # The decomp files are restored from HEAD each build, so a symbol already present means
    # two injectors picked the same name in ONE run -- a collision that would otherwise
    # surface as a duplicate-definition link error a long way from its cause.
    if ('struct UnitDefinition %s[]' % symbol) in udefs:
        sys.exit('ERROR: unit table %s is already defined this build -- two injectors are '
                 'claiming one symbol name' % symbol)
    with open(EVENTS_UDEFS_C, 'w', encoding='utf-8') as f:
        f.write(unit_table_definition(udefs, symbol, rows, comment))
    with open(EVENTCALL_H, encoding='utf-8') as f:
        header = f.read()
    with open(EVENTCALL_H, 'w', encoding='utf-8') as f:
        f.write(unit_table_extern(header, symbol, comment))
    return symbol


def point_event_group_at(info, group, field, symbol):
    """Pure: `info` (a chN-eventinfo.h) with ChapterEventGroup `group`.`field` -> `symbol`.

    Declaring our own roster table is only half the job: the ENGINE reads the roster through
    the ChapterEventGroup, so a table nobody points at is inert and the slot quietly keeps
    using the vanilla one. That is not a hypothetical -- it shipped for one build of ch05 and
    put the party on vanilla Ch6's start tiles, four of them inside walls, on a map whose
    geometry is vanilla Ch5's. Nothing failed: PREP ran, the map drew, the scenario PASSed,
    and only a unit-position dump showed it (INSPECT.units, added for exactly this).

    ch03/ch04 never hit it because they block-overwrote the very table the group already
    pointed at, so the link could not come undone. Owning the symbol means owning the pointer
    too, and this is the half that has no symptom.
    """
    pattern = re.compile(r'(\.%s\s*=\s*)([A-Za-z_]\w*)' % re.escape(field))
    body_start = info.index('struct ChapterEventGroup %s = {' % group)
    body_end = info.index('};', body_start)
    head, body, tail = info[:body_start], info[body_start:body_end], info[body_end:]
    body, n = pattern.subn(lambda m: m.group(1) + symbol, body)
    if n == 0:
        sys.exit('ERROR: ChapterEventGroup %s has no .%s field to repoint' % (group, field))
    return head + body + tail


def assert_event_group_roster(info_path, group, symbol):
    """Fail the BUILD if `group` does not deploy `symbol` on both difficulties.

    The bug this closes has no symptom: a chapter whose group still points at the vanilla
    ally table boots, runs PREP, draws the map, deploys a party and PASSes a load-test --
    just on another map's coordinates. It is the ally-table twin of the host-slot/event-group
    mis-target in docs/adding-a-chapter.md step 4, and it cost a build here.
    """
    with open(info_path, encoding='utf-8') as f:
        info = f.read()
    body = info[info.index('struct ChapterEventGroup %s = {' % group):]
    body = body[:body.index('};')]
    for field in ('playerUnitsInNormal', 'playerUnitsInHard'):
        match = re.search(r'\.%s\s*=\s*([A-Za-z_]\w*)' % field, body)
        if not match:
            sys.exit('ERROR: %s has no .%s' % (group, field))
        if match.group(1) != symbol:
            sys.exit('ERROR: %s.%s deploys %s, not %s -- the chapter would field its roster '
                     'on the HOST SLOT\'s tiles, which belong to a different map. Declaring '
                     'a roster table does not wire it; point_event_group_at does.'
                     % (group, field, match.group(1), symbol))


def unit_table_definition(udefs, symbol, rows, comment):
    """Pure: `udefs` with a campaign-owned UnitDefinition table appended.

    The rows are the same `_ally_unit_entry` / `_enemy_unit_entry` strings a squatted
    vanilla table took, so nothing about roster construction changes -- only where the
    result lands and what it is called.
    """
    _assert_ms_symbol(symbol)
    body = '{\n' + '\n'.join(rows) + '\n    { 0 },\n}'
    return udefs + ('\n/* %s */\nCONST_DATA struct UnitDefinition %s[] = %s;\n'
                    % (comment, symbol, body))


# agbcc needs a declaration before the event script that names the table. The vanilla tables
# declare theirs in eventcall.h, so ours sit with them rather than in a new header nothing
# else includes. Anchored on the FIRST UnitDefinition extern -- appending after a "last"
# extern found by scanning is what breaks when the block grows.
_UDEF_EXTERN_ANCHOR = 'extern CONST_DATA struct UnitDefinition UnitDef_Event_PrologueAlly[];'


def unit_table_extern(header, symbol, comment):
    """Pure: `header` (eventcall.h) with an extern for `symbol`. Idempotent."""
    _assert_ms_symbol(symbol)
    decl = 'extern CONST_DATA struct UnitDefinition %s[];' % symbol
    if decl in header:
        return header
    if _UDEF_EXTERN_ANCHOR not in header:
        sys.exit('ERROR: eventcall.h has no UnitDefinition extern block to extend '
                 '(looked for %r)' % _UDEF_EXTERN_ANCHOR)
    return header.replace(_UDEF_EXTERN_ANCHOR,
                          '%s\n%s /* %s */' % (_UDEF_EXTERN_ANCHOR, decl, comment), 1)


def chapter_label_constants(source=None):
    """{slot index: CHAPTER_L_* name} read from the decomp's own chapters.h.

    The name and the value DIVERGE, and quietly. FE8 inserted Ch5x at slot 5, so:

        CHAPTER_L_4  = 0x04     CHAPTER_L_5X = 0x05
        CHAPTER_L_5  = 0x06     CHAPTER_L_6  = 0x07

    Slot 6 is therefore CHAPTER_L_5, and every chapter we host from here on has a label
    whose digits are one less than its slot. For slots 1-4 the two coincide, which is why
    four injectors could hardcode 'CHAPTER_L_%d' % host_index and be right by accident.

    ch05 is the first chapter where guessing is WRONG, and the failure is silent: a
    gDefeatTalkList entry keyed to the wrong .chapter simply never matches, so the boss dies,
    no flag is set, DefeatBoss never fires, and the map cannot be won -- with nothing in the
    build or the logs to say why. Resolve by VALUE; never spell the name from a number.
    """
    if source is None:
        source = vanilla_decomp_text('include/constants/chapters.h')
    labels = {}
    for name, value in re.findall(r'(CHAPTER_L_\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)', source):
        labels.setdefault(int(value, 0), name)
    return labels


def chapter_label_constant(slot, source=None):
    """The CHAPTER_L_* constant naming chapter slot `slot` (see chapter_label_constants)."""
    labels = chapter_label_constants(source)
    if slot not in labels:
        sys.exit('ERROR: no CHAPTER_L_* constant has value 0x%02X -- chapters.h does not name '
                 'chapter slot %d' % (slot, slot))
    return labels[slot]


def _assert_ms_symbol(symbol):
    if not symbol.startswith(MS_TABLE_PREFIX):
        sys.exit('ERROR: campaign-owned unit table %r must start with %r -- the prefix is '
                 'what distinguishes our data from the vanilla tables we no longer squat on'
                 % (symbol, MS_TABLE_PREFIX))


def safe_ai_clients(ai_index, campaign='rime-of-the-frostmaiden'):
    """`['chNN.enemy-id', ...]` for every enemy whose EMITTED AI1 is `ai_index`.

    Reads what each chapter actually ships -- donor bytes or a declared override -- rather
    than a table of labels (#335). That is strictly wider than the label scan it replaced:
    it also catches a unit that inherits the byte from its vanilla DONOR, which no scan of
    our own vocabulary could ever see.

    One implementation for BOTH repointed do-not-attack lists. They have the same hazard --
    a global list whose safety rests on knowing every client -- and having only AI_A_07's
    swept is what let AI_A_08 be spent with no sweep at all."""
    import difficulty
    out = []
    for path in sorted(glob.glob(os.path.join(
            REPO, 'campaigns', campaign, 'chapters', 'ch*.yaml'))):
        with open(path, encoding='utf-8') as source:
            chap = yaml_load(source)
        stem = os.path.basename(path)[:4]
        for key in difficulty.AI_ROSTER_KEYS:
            for enemy in chap.get(key) or []:
                if not isinstance(enemy, dict):
                    continue
                for index in range(max(1, len(enemy.get('positions') or []))):
                    try:
                        ai = difficulty.enemy_ai_bytes(chap, enemy, index)
                    except ValueError:
                        continue        # ungrounded: ai_donor_findings reports it, not us
                    if ai[0] == ai_index:
                        out.append('%s.%s' % (stem, enemy.get('id')))
                        break
    return sorted(out)
