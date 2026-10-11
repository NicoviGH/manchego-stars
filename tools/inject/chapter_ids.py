"""The chapters' PUBLIC constants: every CHNN_/PROLOGUE_ id another module reads.

A chapter's message ids, pids, slots and YAML names are read well outside the chapter --
`messages` registers every `*_MSG`, `cast` binds boss pids to portraits, ch05 re-reads ch03's
and ch04's texts -- and chapters read each other's in both directions. Kept in one leaf, like
`hosts.py`'s host slots, so no chapter module has to import another. A constant only its own
chapter reads stays in `inject/chapters/`.
"""
from inject.class_ids import ChapterClassIds
from inject.message_alloc import appended_message_id



# PROLOGUE_CHAPTER_INDEX / PROLOGUE_HOST_INDEX / PROLOGUE_EVENT_GROUP: inject/hosts.py.
# Cold-open guests ride vanilla character slots that are NOT in PORTRAIT_MAP, so their
# names/portraits are free placeholders until custom art (see [[feedback_nicolas_not_an_artist]]).
# Sephek rides the vanilla prologue boss slot (ONEILL) so he inherits its CA_BOSS
# attribute -> DefeatBoss fires on his death with no extra flagging. Guards stay
# generics (0x80/0x82) like vanilla. These are display-name/lord-quote slots only;
# class/level/stats come from the UnitDefinition below, not the slot's character data.
PROLOGUE_HLIN_SLOT = 'NATASHA'      # frail must-survive lead (our "lord")
PROLOGUE_SCRAMSAX_SLOT = 'KYLE'     # strong veteran (our "Jeigan")
PROLOGUE_SEPHEK_SLOT = 'ONEILL'     # boss (recurring villain; escapes in the ending)

# Cold-open guests can also wear a custom overworld sprite via the same SMS/MU machinery as
# the cast (inject_map_sprites) -- but their sheets are drawn to FE8's STANDARD player
# map-sprite palette (unit_icon_pal_player), so they render through the normal blue faction
# bank and take NO bespoke cast palette (unlike the cast's purple-bank override). Guests
# have no pcs/npcs YAML, so each sprite's metadata lives here:
#   (uid, slot, class_enum, donor_base)
# donor_base names the vanilla class whose SMS frame geometry the IDLE sheet matches, read
# from the decomp (Pirate = 16x16 axe infantry, matching Hlin's 3-frame 16x16 idle); like
# braulo's base it is a geometry token only, decoupled from the unit's actual class.
PROLOGUE_GUEST_SPRITES = [
    ('hlin-trollbane', PROLOGUE_HLIN_SLOT, 'CLASS_FIGHTER', 'Pirate'),
]

# CH01_HOST_INDEX / CH01_EVENT_GROUP: inject/hosts.py.
# The goal WINDOW + status-objective strings are message ids, and hosted chapters used to inherit
# them from whatever donor slot `_retarget_host_chapter` copied -- which silently shared them
# between chapters (#207). Every hosted chapter now DECLARES its pair, so `assert_message_ids_unique`
# can bind on them. ch01/ch02/ch03 keep the ids their donors already gave them (measured by running
# the injector -- HEAD and the working tree both lie about post-injection goal ids); only ch04 had
# to move, because its donor IS ch02's host slot.
CH01_GOAL_WINDOW_MSG = 0x19F     # vanilla slot 1's seize window ("Seize camp" is ours)
CH01_GOAL_STATUS_MSG = 0x1A3
CH01_BOSS_SLOT = 'BREGUET'   # vanilla Ch1's boss slot: CA_BOSS + hand-authored
# Scenic BG the lord-select menu plays over (NOT the battle map). A standalone "choose
# your leader" screen. Darkling Woods -- "the most Icewind Dale of the options" (Nicolas,
# 2026-06-16). Swap freely to any backgrounds.h enum.
CH01_LORDSEL_BG = 'BG_DARKLING_WOODS'

# ── Ch2 "Cold Welcome" (#22): hosted on chapter slot 3 (ch01's MNC2(0x3) target) ──
# Party PERSISTS from ch01 (no cast re-LOAD); the prep flow fields 5 of the saved roster
# (cap = UnitDef_Event_Ch3Ally entry count) and force-deploys the ch01-chosen lord
# (flag-driven, IsCharacterForceDeployed_ -- no per-chapter wiring). DefeatAll: the slot-3
# host goal is swapped to vanilla slot-4's defeat_all template and the vanilla Ch3
# Seize(14,1) is dropped, so CountRedUnits() drives the rout win; CauseGameOverIfLordDies
# already sits in EventListScr_Ch3_Misc.
# CH02_HOST_INDEX / CH02_EVENT_GROUP: inject/hosts.py.
CH02_GOAL_WINDOW_MSG = 0x19E     # vanilla slot 4's defeat_all window
CH02_GOAL_STATUS_MSG = 0x1A6
CH02_BOSS_SLOT = 'BAZBA'      # vanilla Ch3's boss slot -- Halvar mirror (custom bust #19 later)
CH02_MINIBOSS_SLOT = 'BONE'   # vanilla Ch2's named mid-tier, idle on slot 3 -- Grukk (bust later)
CH02_OPENING_BG = 'BG_NORMAL_VILLAGE'      # Bryn Shander west gate (vanilla village BG)
# The three GREEN chwinga (protect layer): each rides a distinct minor vanilla NPC slot so
# its survival is individually trackable via CHECK_ALIVE at the ending scene. Slots are
# collision-free (absent from our ch00-08); their map sprite + portrait + name-text
# (Mote/Rime/Glimmer) are the art checkpoint (#38/#39) -- placeholder vanilla faces meanwhile.
# (yaml_id, vanilla character slot). The charm-gift each survivor delivers is NOT stored here --
# it is read from the chapter YAML's green_allies[].gift (single source of truth; the ch02<->ch03
# reward swap lives in the YAML, so a hardcoded copy here silently drifted once -- #23).
# All three keep an identity (face + name): Glimmerfrost is the inhabitant of the (1,12)
# village rather than a unit on the field, so she needs a bust and a name for her visit
# scene but never enters the green table. Who DEPLOYS is read from the chapter YAML's
# green_allies, so moving a chwinga between the field and a village is a YAML edit.
CH02_CHWINGA = (
    ('chwinga-mote',    'DARA'),
    ('chwinga-rime',    'KLIMT'),
    ('chwinga-glimmer', 'MANSEL'),
)

# ch02's two Targos huts (2026-08-30). Vanilla Ch2 wires THREE Village() and our retile kept
# two of its four village-terrain tiles, so the map drew huts backing nothing. They are the
# raid's DECOY: pillage targets terrain, so villages are what pull six pillaging bandits off
# the protected greens while the player crosses to reach them.
#   id                  event script          msg     mug                       backdrop
CH02_VILLAGE_SLOTS = {
    'targos-hut-south': ('EventScr_089F15A0', 0xAC0, '[FID_VillagerWoman]', CH02_OPENING_BG),
    'targos-hut-east':  ('EventScr_089F1658', 0xAC1, '[FID_VillagerMan3]', CH02_OPENING_BG),
}
# The chwinga wear Sclorbo's chwinga map sprite (he is one), recoloured by the green NPC
# faction palette -- identical green triplets (Nicolas 2026-06-24). Build-time derived from
# this cast sprite; see _inject_ch02_chwinga_sprites.
CH02_CHWINGA_SPRITE_SRC = 'sclorbo'
# Their PORTRAITS are the same move: Sclorbo's bust with the icy-blue glow ramp hue-shifted
# to spirit-green (Nicolas-approved 2026-06-24), build-derived from his portrait (no committed
# asset). Each chwinga's vanilla portrait slot is collision-free (absent from our ch00-08):
# Dara reuses FE8's Saleh-grandmother face (Dara IS Saleh's grandmother), Klimt/Mansel their own.
CH02_CHWINGA_PORTRAIT_SLOT = {'DARA': 'Saleh_Grandma', 'KLIMT': 'Klimt', 'MANSEL': 'Mansel'}
# The turn-1 scene's messages, one per beat. The first two are the fliers-vs-bows debut
# (RBG warns flier Pinky, Pinky answers); the last three are Halvar's raid bark -- vanilla
# Ch2's own MSG_957, verbatim, pairing the warning with the announcement exactly as vanilla's
# opening does. 0xAC2-0xAC4 come from ch02's block.
CH02_TURN1_MSGS = (0x98f, 0x991, 0xAC2, 0xAC3, 0xAC4)


# ── Ch3 "The Termalaine Mine" (#23): hosted on chapter slot 4 (repaint of vanilla Ch3
#    "Bandits of Borgo", so the roster/positions mirror vanilla Ch3 1:1). Uses the vanilla
#    "Ch4" decomp symbol set (host index N -> ChN symbols, cf. ch02 on slot 3 = Ch3 symbols).
# CH03_HOST_INDEX / CH03_EVENT_GROUP: inject/hosts.py.
CH03_GOAL_WINDOW_MSG = 0x19D     # vanilla slot 6's defeat_boss window
CH03_GOAL_STATUS_MSG = 0x1A7
CH03_CHAPTER_YAML = 'ch03-the-termalaine-mine.yaml'
CH03_BOSS_PID = '0xb7'          # grell rides a raw charIndex (NOT the vanilla ch4 boss ENTOUMBED_CH4=0x49):
# The grell's flagged death quote (gDefeatTalkList) sets EVFLAG_DEFEAT_BOSS -> the Misc DefeatBoss AFEV.
# Body rides a dead vanilla Ch4 message id: 0x9A3 is the Ch4 opening cutscene's first line (Seth/Eirika at
# Serafew), referenced ONLY inside EventScr_Ch4_BeginningScene -- which inject_ch03 replaces -> dead in our build.
CH03_BOSS_DEATH_MSG = 0x9A3
CH03_TREX_TALK_MSG = 0x9A5
CH03_OPENING_CARD_MSG = 0x9A6
# A crier/RBG · B Wolfram (town) -> BG swaps to the mine · C KOBOLDS-ONLY sign (#58 box, empty cave)
# · D Pinky scouts out (fades away) · E Pinky returns ("it looked at me")
CH03_OPENING_MSGS = (0x9A7, 0x9A8, 0x9A9, 0x9B2, 0x9B3)
CH03_ENDING_CARD_MSG = 0x9AA
CH03_ENDING_MSGS = (0x9AB, 0x9AC, 0x9AD)    # A RBG bounty · B Trex negotiates his warren in · C Meesmickle button
CH03_TREX_ENTRANCE_MSG = 0x9AE              # light turn-1 on-map beat (Pinky telegraph + RBG "little dragon")
# Midmap RBG-execution beat (#23 item 1): the Icewind Brute is a mid-map MINIBOSS whose DEFEAT
# fires a flagged death cutscene (RBG guns down the beaten Brute) -- the mirror of the grell's
# DefeatBoss WIN, keyed to a tmp flag + a Misc AFEV instead of the win flag. It rides ON-MAP (no
# BG), like Trex's entrance. Reuses the dead Ch4 death-scene 0x9AF..0x9B1 message block.
CH03_BRUTE_MINIBOSS_PID = '0xb6'   # the Icewind Brute -- a clean raw charIndex sibling of the grell's
# 7 beats (RESTAGED 2026-07-11): A Pinky reaches out (faced) · A2 the Brute lunges at Pinky (FACELESS
# action box) · A3 the Brute's snarl (faced mug) · B RBG "Say cheese" (faced) · B2 the shot/kill (FACELESS
# action box) · B3 Pinky+RBG (faced two-hander) · C Wolfram (faced). The two faceless narration boxes ride
# the opaque auto-centered box (_beat_is_faceless -> SOLOTEXTBOXSTART). 0x9B2/0x9B3 are the opening's
# Pinky-scout beats; the midmap borrows 0x9B4..0x9B7 from the dead Ch4 block.
CH03_MIDMAP_MSGS = (0x9AF, 0x9B0, 0x9B1, 0x9B4, 0x9B5, 0x9B6, 0x9B7)
CH04_LUPIN_TALK_MSG = 0x9BA                    # dead Ch5 text slot -> stub parley line (Stage 4 finalizes)
CH04_REVEAL_MSGS = (0x9BB, 0x9BC)               # Lupin command + Marty parley-flag (stubs)

# ── Stage 4: the authored scenes ────────────────────────────────────────────────
# MESSAGE IDS: ch04 is hosted on slot 5, so it OWNS vanilla Ch5's whole message block
# (0x9BA-0x9CC) -- every id below is a dead Ch5 slot, freed when inject_ch04 blanks the Ch5
# event lists. ch05's YAML labels its beats "vanilla 0x9BB" etc., but those are ANATOMY
# references mined from its FE8 twin, NOT ids it may claim: ch05 will host on its own slot and
# take that slot's block. `_assert_message_ids_unique` (below) enforces this at build time --
# see the #198 review note on issue #24.
CH04_OPENING_CARD_MSG = 0x9BD                   # "Lonelywood" location card
CH04_OPENING_MSGS = (0x9BE, 0x9BF)              # A Nimsy's cottage · B the forest-edge fog beat
CH04_MOOSE_MSG = 0x9C0                          # the moose breaks and bolts -- RBG "After it!"
CH04_ENDING_MSG = 0x9C1                         # chapter_end, parley path (Lupin reads the trail)
CH04_ENDING_NO_LUPIN_MSG = 0x9C2                # chapter_end, no-parley path (Pinky/Meesmickle)
CH04_OPENING_FOREST_BG = 'BG_MS_LONELYWOOD_FOG'  # the forest edge under fog (Pinky's beat) --
CH04_NIMSY_FID = '[FID_VillagerOldWoman]'       # vanilla generic (textdefs.txt 0x5F)
                                                #   EventScr_089F2304, a Ch5 reinforcement script
                                                #   whose Turn entry we drop) -> the neutral moose
CH04_MOOSE_PID = '0xce'                         # its own pid (DISA targets it, and it alone)
CH04_MOOSE_MOV_TABLE = 'TerrainTable_MovCost_AnimalT2Normal'   # the Gwyllgi's own cost row
                                                # Starts at x=9, NOT x=8: (8,2) is the village
                                                # doorstep (#205), and an AREA covering it fires the
                                                # sighting the moment a unit steps up to visit.
                                                # Vanilla's own AREA (0,9)-(14,14) touched neither
                                                # village. Guarded by a test over `villages:`.
# The Lonelywood villages (#205, #24). Vanilla Ch4 wires TWO -- `Village(0, EventScr_089F1BD8,
# 8, 2)`, the Iron Axe, and `Village(0, .., 1, 11)`, its Lute RECRUIT village -- and we keep both
# tiles and the script shape. WHICH village and WHAT it gives are read from the chapter YAML: a
# village's reward and its line are content, and putting them here is the mistake #208 exists to
# undo.
#
# The Marty->Lupin parley took the recruit village's JOB, so for the whole slice (1,11) stood on
# visitable terrain with no Location entry -- FE8 offers Visit off the location event, so the
# player saw a cottage they could not enter (#24). Vanilla's own text there is pure Lute recruit
# dialogue (9B2/9B3/9B4, zero lore), so there was nothing to copy and the line is ours.
#
# Each village needs its OWN script and message slot -- two doors sharing one script show the
# same line at both and run the give-item tail twice. Keyed by the YAML's village `id`, so a
# third village is one row here plus one `villages:` entry.
#
# BACKDROP: both doors play over CH04_OPENING_FOREST_BG, our winterized fogged forest -- the very
# art Pinky's opening beat B stands in. Vanilla's `BG_NORMAL_VILLAGE` is a TEMPERATE GREEN TOWN,
# and during a village visit the backdrop is the entire screen, so ch04 was showing summer in a
# snowbound fog chapter (Nicolas, 2026-08-05). It is the forest and not our snow-TOWN art
# (BG_MS_TARGOS_WINTER) because there is no town on this map: both cottages are cabins standing
# in the woods, and a visitor is outside one of them -- "if we're outside their cabin, just use
# the bg you put behind pinky in his fog scene".
CH04_VILLAGE_SLOTS = {
    #  id                 event script          msg     mug                  backdrop
    'lonelywood':     ('EventScr_089F231C', 0x9C3, CH04_NIMSY_FID, CH04_OPENING_FOREST_BG),
    # The cottage's logger wears FID_VillagerMan3 -- the mug vanilla itself puts on the snag
    # village (MSG_9B5). It is free for us because our axe village reassigned that door to Nimsy.
    'forest-cottage': ('EventScr_089F2170', 0x9C6, '[FID_VillagerMan3]', CH04_OPENING_FOREST_BG),
}
# `EventScr_089F231C` is a dead Ch5 script (verified free at HEAD). `EventScr_089F2170` is vanilla
# Ch5's OWN village script -- `Village(EVFLAG_TMP(8), .., 12, 10)` in ch5-eventinfo.h, its only
# reference, and inject_ch04 replaces that whole Location list: a village script for a village.
# 0x9C6 is the next free id in ch04's block (it hosts on slot 5, so it owns 0x9BA-0x9CC). ch05's
# YAML labels beats "vanilla 0x9C6" -- those are ANATOMY references mined from its twin, not ids
# it may claim; it will host on its own slot and take that block.
CH04_VILLAGE_SCRIPT, CH04_VILLAGE_MSG = CH04_VILLAGE_SLOTS['lonelywood'][:2]
CH04_COTTAGE_SCRIPT, CH04_COTTAGE_MSG = CH04_VILLAGE_SLOTS['forest-cottage'][:2]
# ch04's goal strings (#207). Its goal donor is ch02's HOST slot, which inject_ch02 has already
# rewritten by the time inject_ch04 runs -- so ch04 inherited ch02's window AND status ids and the
# two wrote over each other (last injector wins; they happened to agree, which is why nothing
# looked broken). These come out of ch04's own dead Ch5 block instead.
CH04_GOAL_WINDOW_MSG = 0x9C4                    # dead Ch5 text slot -> the on-map goal banner
CH04_GOAL_STATUS_MSG = 0x9C5                    # dead Ch5 text slot -> the Status-screen objective
                                                # vanilla symbol -- campaign-owned event scripts,
                                                # declared AFTER the block-replacement pass.
CH05_SAHNAR_TALK_MSG = 0x9E8     # the TALK-RECRUIT scene, the chapter's payoff. MOVED off
                                 # vanilla 0x9CC and into ch05's OWN host block (2026-08-13,
                                 # dialogue-pass), which is what the placeholder note there always
                                 # said to do. 0x9CC held vanilla's Natasha->Joshua recruit -- the
                                 # exact scene ours is the twin of, so it read as a legitimate
                                 # placeholder on paper and as a BUG on screen: Basil wears the
                                 # Artur slot and Sahnar the Marisa slot, while 0x9CC loads
                                 # Natasha's and Joshua's faces and speaks their words. What the
                                 # player actually saw was Hlin Trollbane's bust (dressed onto the
                                 # Natasha slot) talking to vanilla Joshua. First free id in the
                                 # block; 0x9E9..0x9F3 remain for the opening and endings.
# ...and the no-Lupin arm's id. 0x9D1 is vanilla Ch5's TUTORIAL text (EventScr_089F231C),
# reachable only from EventListScr_Ch5_Tutorial -- which inject_ch04 zeroes along with the other
# three unused lists. Exactly the sweep that freed 0x9D2 for the moose quip and 0x9CD..0x9D0 for
# the reliquary visits, and verified against HEAD rather than assumed.
CH05_SAHNAR_TALK_NO_LUPIN_MSG = 0x9D1

# The four reliquary visits. Each rides OUR OWN script (declare_event_script) but shows VANILLA
# Ch5's own village line, by pointing at the message id that already holds it -- we never WRITE
# 0x9CD..0x9D0, so the ROM keeps vanilla's text verbatim and the id stays unclaimed
# (HOSTED_CHAPTER_MESSAGE_IDS). ch05's authored dialogue skips this range exactly (it runs
# 0x9BE..0x9CC then jumps to 0x9D5), so nothing collides.
#
# WRITTEN 2026-08-08 (dialogue-pass): the four bodies are ours now, at these same ids, and the
# ids are CLAIMED in HOSTED_CHAPTER_MESSAGE_IDS. Writing outside ch05's own host block is
# deliberate and safe, which is worth stating because the registry's whole point is that it
# usually is NOT: 0x9CD..0x9D0 are vanilla Ch5's village lines, and the only scripts that ever
# displayed them are `EventScr_089F2170` (which inject_ch04 REPLACES for its forest cottage) and
# `EventScr_089F21BC`/`21F8`/`2234` (left in ch5-eventscript.h but unreferenced once inject_ch04
# rewrites Ch5's Location list -- dead code, never run). Verified against HEAD, not assumed.
# The alternative -- spending four of ch05's own 16-id block -- was rejected because the
# remaining cutscene pass (#25) needs that block and HANDOFF already prices it as tight.
CH05_VILLAGE_SLOTS = {
    #  id                  event script          msg     mug
    'reliquary-east':  ('MS_Ch05VisitEast',  0x9CD, '[FID_VillagerMan1]'),
    'reliquary-south': ('MS_Ch05VisitSouth', 0x9CE, '[FID_VillagerMan2]'),
    'reliquary-west':  ('MS_Ch05VisitWest',  0x9CF, '[FID_VillagerYoungMan]'),
    'reliquary-north': ('MS_Ch05VisitNorth', 0x9D0, '[FID_ManUnused]'),
}
                                    # four-way (stone chamber / house / interior brown /
                                    # black temple): the map draws these sites as BUILDINGS,
                                    # so the interior should read as somewhere you stepped
                                    # INTO. BG_HOUSE's lit hearth and cooking pot are a
                                    # kitchen; the black temple is draped in green vines,
                                    # wrong for two years of unbroken winter.
# The four residents' BUSTS. The sites are a TOMB, so the speakers are the tomb's own risen dead
# (Nicolas, 2026-08-08) and every one needs a face FE8 does not ship -- there is no undead mug in
# the base ROM (checked the whole FID table; the closest is a plain villager).
#
# SLOT CHOICE: each rides a vanilla portrait slot that is collision-free -- absent from our
# ch00-08 and dressed by nothing else in the injector. Villager_Man_3/4, Old_Man, Old_Woman,
# Young_Boy and Woman are all SPOKEN FOR (ch02's fisher, ch03's crier, ch04's Nimsy and logger,
# a prologue guest), so the free ones are Man_1, Man_2, Young_Man and the literally-unused
# Man_Unused. Overwriting a slot's graphics is GLOBAL, so "free" has to mean free everywhere.
#
# DERIVED AT BUILD TIME from the vendored FE-Repo mug, the chwinga pattern -- no committed
# derived asset, so the vendored PNG stays the single source. The two skeletons in orange
# pauldrons are the SAME BODY with a different jaw, so the south one is recoloured verdigris or
# the player meets the same man twice; only the two true oranges move, because the third tone in
# that ramp is also the SKULL's shadow (y 10..72, vs the pauldrons' y>=52) and recolouring it
# turns his teeth green.
CH05_VISIT_ORANGE_TO_VERDIGRIS = {(192, 96, 48): (86, 138, 116), (136, 80, 56): (52, 92, 80)}
CH05_VISIT_FACES = {
    #  id                 vendored FE-Repo mug                                    slot            recolor
    'reliquary-north': ('Cantor {Eden, L95} [F2E].png',                     'Man_Unused',        None),
    'reliquary-west':  ('Skeleton (Mage, version 1) {L95, BladerDj} [F2E].png',
                                                                            'Villager_Young_Man', None),
    'reliquary-east':  ('Skeleton {L95} [F2E].png',                         'Villager_Man_1',    None),
    'reliquary-south': ('Skeleton (Full Smile) {L95, Nokitrix} [F2E].png',   'Villager_Man_2',
                        CH05_VISIT_ORANGE_TO_VERDIGRIS),
}
CH05_CHAPTER_YAML = 'ch05-the-elven-tomb.yaml'
                                                 # NOT slot 6: that is ch05's own host slot, so
                                                 # donating from it would copy a goal the chapter
                                                 # is in the middle of replacing.
# ch05's goal strings come from its HOST SLOT's dead block (vanilla Ch6 = 0x9E4..0x9F5), not
# from vanilla Ch5's -- ch04 hosts on slot 5 and already owns that block (#207).
CH05_ERUPTION_MSG = 0x9E4                     # turn-2 Ravisin warning; first free Ch6-host id
CH05_RAVISIN_DEATH_MSG = 0x9E5                # locked Ravisin death quote; next Ch6-host id
CH05_ARENA_FOUND_MSG = 0x9E6                  # vanilla 0x9D5 anatomy, in ch05's host block
CH05_ARENA_RULES_MSG = 0x9E7                  # vanilla 0x9D6 anatomy, in ch05's host block
CH05_RAVISIN_TAUNT_MSG = 0x9F2                # first-engagement boss taunt (gBattleTalkList)
CH05_GOAL_WINDOW_MSG = 0x9F4
CH05_GOAL_STATUS_MSG = 0x9F5
# The three scenes, in PLAYER order, keyed by the YAML `slot:` label they carry. That label is an
# ANATOMY CITATION naming the vanilla scene we mine, never an id we write (ch04 hosts on slot 5
# and writes 0x9BB/0x9BC/0x9BD for real) -- the id beside it is the destination, and the two being
# separate fields is what lets them differ. Ids are the next three free in ch05's own Ch6 host
# block, allocated in #25's table.
CH05_OPENING_SLOTS = (
    #  YAML `slot:`      id     boxes  what
    ('vanilla 0x9BB', 0x9E9, 19, 'Basil and Sahnar talk through the stone'),
    ('vanilla 0x9BC', 0x9EA, 16, 'Sephek gives Ravisin her orders'),
    ('vanilla 0x9BD', 0x9EB, 7,  'Ravisin appraises the blade; Basil asks after her'),
)
CH05_ARRIVAL_SLOT = ('vanilla 0x9BE', 0x9EC, 7,
                     'the party crests the ridge; Wolfram finds the arena')
# The no-Lupin arm. ONE extra id, not four: `variant_beat` splices the substitute box and the
# WHOLE variant scene goes to a second message, which `branch_on_check_alive` picks at runtime
# (ch04's ending already does exactly this). Splitting the scene around the differing box would
# cost four ids -- duplicating text is free, ids are what is scarce.
CH05_ARRIVAL_NO_LUPIN_MSG = 0x9ED
# ── Scene 5 (#25): Basil trundles up, cracks the tourist joke, and JOINS ─────────────────────
# The opening's FIRST on-map beat, so it wraps at the talk bubble's budget
# -- and the one scene whose PLACEMENT does not inherit from the twin. Vanilla plays its 0x9C2
# BEFORE the prep CALL, but it can: it LOAD1s its speaking party onto the street first. Ours is
# placed BY prep (the ally table is never LOADed on a prep chapter -- decisions.md "How the deploy
# cap + prep screen are actually wired"), so before the CALL the field holds the risen line,
# Ravisin, and a green shrub with nobody to be talking to. The beat therefore plays AFTER prep, in
# vanilla's own after-prep shape (FADU(16) -> CUMO -> STAL -> CURE -> TEXTSTART, which is exactly
# what its 0x9C3/0x9C4 do) -- and it lands adjacent to the CUSA that was already there, so the ask
# and the flip are one beat rather than two across a screen.
CH05_BASIL_JOIN_SLOT = ('vanilla 0x9C2', 0x9EE, 3,
                        'Basil trundles up, cracks the tourist joke, joins')
CH05_BASIL_JOIN_NO_LUPIN_MSG = 0x9EF
# ── Scene 6 (#25): Sahnar alone at the sarcophagus ───────────────────────────────────────────
# A PLAIN ON-MAP BUBBLE, inherited from the twin without an exception -- and it only became one
# on 2026-08-14, when Nicolas moved her summon into scene 3. While she was a turn-2 riser this
# scene had nothing on the field to anchor a bubble to and was priced as needing its own
# BACKDROP; with her standing at the arena from turn 1 it is vanilla's 0x9C3 exactly, down to
# the camera move. All six locked boxes survive untouched -- "...Someone has come." reads as
# well standing in the amphitheatre as lying under a lid.
#
# Vanilla's own after-prep shape for this beat, verbatim from EventScr_Ch5_BeginningScene:
#   FADU(16) -> CAMERA -> CUMO_AT(12, 6) -> STAL/CURE -> LOAD1(Joshua) -> ENUN
#   -> MOVE(Joshua, 9, 7) -> ENUN -> CUMO_CHAR -> STAL/CURE -> TEXTSTART/TEXTSHOW(0x9c3)
# The LOAD1 lands AFTER the camera is already on the tile, so the player watches the duelist
# arrive rather than finding her there -- and then she STEPS OFF IT, which is load-bearing rather
# than flourish. (12,6) is TERRAIN_ARENA_REGULAR and the arena tutorial's trigger is
# `AREA(..., 12, 6, 12, 6)`; a hostile standing there makes the arena unenterable for the whole
# chapter and silently kills the `arena-wager` debut (#264/#265). This wiring dropped the MOVE at
# first and did exactly that. Her walk-off tile is the YAML's `walks_to`, vanilla's own (9,7) --
# TERRAIN_ROAD, no defensive bonus, clear of the arena mouth.
#
# SEVEN boxes, not the six the scene was locked at, and no word of it changed: the channel
# swap is what costs the press. "No one ever came. I stopped counting somewhere in the middle."
# is 60 characters, which is three lines at 29 and a box holds two -- so the wrapper was
# choosing the A-press and landing it mid-clause. The YAML now authors the break at the full
# stop instead. Same lesson as the reliquary lines and scene 5's fallback: an authored A-press
# is pacing, and a wrapped one is an accident.
CH05_SAHNAR_ALONE_SLOT = ('vanilla 0x9C3', 0x9F0, 7, 'Sahnar alone in the sarcophagus')
# ── Scene 7 (#25): the LAST beat before the map -- Pinky asks, and the moose answers ─────────
# The twin is vanilla's 0x9C4, and we take its POSITION and not its content (chapter YAML,
# Nicolas 2026-07-29): Natasha steeling herself is cut, but the SLOT -- the final on-map beat
# before turn 1, a bubble over the field -- is inherited whole, down to vanilla's own
# `CAMERA/CUMO -> STAL/CURE -> TEXTSTART/TEXTSHOW` shape.
#
# TWO boxes and ONE id, and that pairing is the finding. The beat is a setup/punchline across a
# WORDLESS action -- Pinky asks, the moose bellows and breaks, Meesmickle answers sideways -- so
# something has to happen between the presses. Splitting it into two TEXTSHOWs would have cost a
# second hosted id (#25 has exactly one spare left). It does not: `stage_break:` renders
# vanilla's `[BreakTalk]`, the event script does its business at the pause and `TEXTCONT` resumes
# the same message. See SCRIPT_DIRECTIVES for what that pause does and does not buy.
CH05_MOOSE_CHARGE_SLOT = ('vanilla 0x9C4', 0x9F1, 2,
                          'Pinky asks why the moose is not running; it charges')
# ...and the punchline's own id, which is what the full-screen bellow COSTS. The two boxes shared
# 0x9F1 across a `[BreakTalk]` until the CG went in; a scene change tears the talk down, so the
# quip has to be a second message (filmed 2026-08-15: with a break, it never appeared at all).
# 0x9D2 was ch05's one spare, so the block is now EXACTLY spent -- the endings and the taunt fit
# and nothing is left over. Another beat names its message in inject/message_alloc.py (#411).
CH05_MOOSE_QUIP_MSG = 0x9D2
# Raw charIndexes. Pids need only be unique WITHIN a chapter -- gDefeatTalkList entries carry
# .chapter, so ch03's 0xb7 and ch04's 0xb7 coexist -- but the boss and the moose need their own
# so their flagged death entries key to them alone.
CH05_BOSS_PID = '0xb8'                           # Ravisin: flagged EVFLAG_DEFEAT_BOSS -> the WIN
CH05_MOOSE_PID = '0xb9'                          # the white moose: named, but NOT the win condition
# The moose's NAME, appended past vanilla's last message by the build (inject/message_alloc.py).
CH05_MOOSE_NAME_MSG = appended_message_id('ch05', 'moose-name')
                                      # vanilla's own move: its ending returns to the backdrop
                                      # the fight happened over rather than buying a new one.
# Scene 16 in TWO copies -- Sahnar recruited or not -- and each is ONE continuous message.
#
# It was three `beat_break` beats first, with the berry exchange as the middle one so the event
# script could skip it. That played correctly and LOOKED WRONG, and only a film says so
# (Nicolas, 2026-08-19): every `Text()` is its own TEXTSTART..REMA, so the seams tore the faces
# down and rebuilt them, and Basil -- who speaks in all three -- faded out and reloaded into the
# seat she was already sitting in, twice. Held as one message the podium manager keeps her up
# from the first box to the last and rotates everyone else through mid-left, which is the scene:
# the party comes to HER.
#
# Whole copies rather than a prefix/arm/suffix split, and nothing is hand-duplicated -- each is
# generated from the one locked script by `variant_beat`, whose `replaces:` anchors assert the
# edit lands where the YAML says. Ids are not scarce; seams are expensive.
#
# THERE IS NO LUPIN AXIS, and that is a correction rather than a simplification. Both endings
# carried a `no_lupin_fallback` until 2026-08-19, on the grounds that Basil's "like she woke the
# wolves" named an optional recruit. It does not: recruitment decides whether Lupin JOINS, not
# whether the party ever met the pack, and ch04's turn-2 reveal puts the wolves in front of them
# on every path. The line is true in both worlds, so the branch could only ever be wrong
# (Nicolas). Three ids instead of six, and nothing has to be appended past MSG_D4B any more.
CH05_ENDING_MSGS = {                       # was Sahnar recruited? -> message id
    True:  0x9C9,                          # the full scene, as locked
    False: 0x9CA,                          # ...with the six berry boxes cut
}
# The Basil-died variant: ten boxes and ONE arm. Sahnar is deliberately silent over the body even
# when she was recruited (the YAML's "NOT NESTED" note), and there is no Lupin axis, so this
# scene has nothing left to branch on at all.
CH05_ENDING_LOST_MSG = 0x9F3               # the host block's last free id
                                                 # 6 and 7 are both ours now (ch03 and ch05 took
                                                 # them); 0 is the prologue's and read-only. There
                                                 # is no convention to follow here -- the donor is
                                                 # storage, and any clean slot of the right
                                                 # windowDataType does (Nicolas, 2026-09-03).
# ch06's message block is vanilla Ch7's own dead ids (HOSTED_CHAPTER_MESSAGE_BLOCKS), which
# fall dead the moment the event lists and the beginning scene below are rewritten. The goal
# pair takes the block's LAST two ids, as ch05's does. New scenes take no block id at all: they
# name their messages in inject/message_alloc.py (#411).
CH06_GOAL_WINDOW_MSG = 0x9FE
CH06_GOAL_STATUS_MSG = 0x9FF
                                                 # and vanilla Ch6's (both spend 0x80)
# The two marooned boats are UNITS, not painted scenery, so they can be KILLED -- which is the
# whole clock (#360). Each takes its OWN raw pid, for the same reason ch04's wolf pack needed one
# (#203): a shared pid is unaddressable, and each hull has to be independently CHECK_ALIVE-able
# for the save-them-both payout and independently Talk-able when the boarding pass lands.
#
# 0xB0..0xBA IS FULL, and a first draft of this line took 0xB4/0xB5 believing otherwise. The
# range's real occupancy is 0xb0/b1/b2/b4/b5 CH04_PACK_PIDS, 0xb3 ch04's Mauthe Doog, 0xb6 ch03's
# Brute, 0xb7 ch03's grell (which ch04's mogall shares -- legal, because a defeat quote is keyed
# by CHAPTER too), 0xb8 Ravisin, 0xb9 the moose, 0xba Sahnar's. Taking 0xB4/0xB5 would have
# renamed two of ch04's five wolves to "Fishing Boat": a name plate is written into
# `gCharacterData`, which is ONE GLOBAL TABLE with no chapter dimension, so a NAMED pid must be
# exclusive even though a generic one need not be (ch05 and ch06 both spend 0x80 for trash).
# 0xbb and 0xbc are the next unnamed gaps -- nameTextId 0x255, the generic monster plate, the
# same shape as every pid above. `assert_named_raw_pids_are_exclusive` now makes the mistake
# impossible rather than leaving the next chapter to re-read this comment.
CH06_CHAPTER_YAML = 'ch06-the-maer-monster.yaml'
CH06_BOAT_PIDS = {'boat-east': '0xbb', 'boat-west': '0xbc'}
# Their NAMES, appended past vanilla's last message by the build (inject/message_alloc.py).
CH06_BOAT_NAME_MSGS = {'boat-east': appended_message_id('ch06', 'boat-east-name'),
                       'boat-west': appended_message_id('ch06', 'boat-west-name')}
# The boarding pass (#26): any party member Talks a hull, one Talk entry per (PC x boat) and every
# entry for a boat sharing that boat's ONE flag, so the first boarding shuts the rest. Flags 9/10:
# slot 7's lists are all ours, and the Turn list's wave rides flag 0. The scenes are our own `MS_`
# scripts and their messages are appended (inject/message_alloc.py).
CH06_BOAT_TALK_FLAGS = {'boat-east': 'EVFLAG_TMP(9)', 'boat-west': 'EVFLAG_TMP(10)'}
# Which hull came home, set by the ending for ch07's docks opening to fork on (Grynsk, Tali,
# both or neither). PERMANENT flags (ids >= 101 ride the save across the chapter break), next to
# the 0xF0-0xFB block inject.decomp already holds; vanilla's highest permanent flag is 235.
CH06_BOAT_SURVIVED_FLAGS = {'boat-east': '0xFC', 'boat-west': '0xFD'}
CH06_BOAT_TALK_SCRIPTS = {'boat-east': 'MS_Ch06BoardEast', 'boat-west': 'MS_Ch06BoardWest'}
CH06_BOAT_TALK_MSGS = {'boat-east': appended_message_id('ch06', 'boat-east-talk'),
                       'boat-west': appended_message_id('ch06', 'boat-west-talk')}
# Messie, the boss-death cutscene's actor: 0xbd, the next unnamed 0x255 gap after the boats
# (0xbe is Fomortiis). He is NAMED, so the pid is his alone (assert_named_raw_pids_are_exclusive).
# The opening (#26): the location card, then one message per beat. Appended, never block ids.
CH06_OPENING_CARD_MSG = appended_message_id('ch06', 'opening-card')
CH06_OPENING_MSGS = (appended_message_id('ch06', 'opening-hall'),
                     appended_message_id('ch06', 'opening-ice'))
# ...and beat B's far side of its stage_cut: Meesmickle, over the merfolk surfacing.
CH06_OPENING_QUIP_MSG = appended_message_id('ch06', 'opening-ice-quip')
CH06_MESSIE_PID = '0xbd'
# His scene (#26): the boss_defeated script, one message.
CH06_MESSIE_MSG = appended_message_id('ch06', 'messie-ice')
CH06_NERRA_TAUNT_MSG = appended_message_id('ch06', 'nerra-taunt')       # first-engagement taunt
CH06_NERRA_RETREAT_MSG = appended_message_id('ch06', 'nerra-retreat')   # her defeat line
# ch05's four INFANTRY classes are dressed as skeletons (#25, campaign.yaml `dresses: {ch05:}`):
# every ch05 red unit wearing one is a risen tomb-guardian, so the repoint is wholesale rather
# than per-enemy. The three that stay vanilla are not oversights: the DRUID is Ravisin, who
# carries her own authored art; the GWYLLGI is the moose; and the MYRMIDON is Sahnar, whose
# Specter anim and map sprite landed with her recruit (#251) and who turns BLUE mid-chapter.
CH05_CLASS_IDS = ChapterClassIds('ch05')
CH05_ITEM_IDS = {'flux': 'ITEM_DARK_FLUX', 'rotten-claw': 'ITEM_MONSTER_ROTTENCLW',
                 # the GWYLLGI's own vanilla weapon (the moose deploys as one), kept
                 # under its vanilla NAME -- renaming the item would burn 'Hell Fang'
                 # for every future Gwyllgi in the campaign (Nicolas, 2026-08-15)
                 'hell-fang': 'ITEM_MONSTER_HELLFANG',
                 'fire-fang': 'ITEM_MONSTER_FIREFANG',
                 'iron-lance': 'ITEM_LANCE_IRON', 'iron-axe': 'ITEM_AXE_IRON',
                 'iron-sword': 'ITEM_SWORD_IRON', 'iron-bow': 'ITEM_BOW_IRON',
                 # FE8 calls the Killing Edge ITEM_SWORD_KILLER -- it is the sword vanilla
                 # Joshua carries on this very map, and Sahnar is his 1:1 (crit-threat duelist)
                 'killing-edge': 'ITEM_SWORD_KILLER',
                 # the four reliquary gifts (villages) -- vanilla Ch5's own reward tier, and
                 # the exact items `make difficulty CH=ch05` prices the economy against
                 'booster-def': 'ITEM_BOOSTER_DEF', 'booster-skl': 'ITEM_BOOSTER_SKL',
                 'armorslayer': 'ITEM_SWORD_ARMORSLAYER', 'torch': 'ITEM_TORCH',
                 # the save-all-four bonus -- vanilla Ch5's own, handed over at the ending
                 'guiding-ring': 'ITEM_GUIDINGRING',
                 # ch06's boats -- vanilla Ch6's own pair: the village gift, and the
                 # save-them-all prize its ENDING scene grants on CHECK_ALIVE
                 'antitoxin': 'ITEM_ANTITOXIN', 'orions-bolt': 'ITEM_ORIONSBOLT'}


# ── Message-id ownership across hosted chapters (#198 review, issue #24) ────────
# Each hosted chapter writes text into DEAD message slots belonging to the vanilla chapter it
# hosts ON -- ch03 sits on slot 4 and takes vanilla Ch4's block, ch04 sits on slot 5 and takes
# vanilla Ch5's. Two chapters claiming one id is a SILENT failure: `verify_text` decodes what
# it finds and checks for runaway text, not for who owns a slot, so the second writer simply
# overwrites the first and the build stays green.
#
# That is not hypothetical. ch05's YAML labels its beats `slot: "vanilla 0x9BB"` / `"0x9BC"`,
# which are ANATOMY references mined from its FE8 twin -- but the same field means a LITERAL id
# a few lines away (`"vanilla 0x9C6" # data_battlequotes.c, pid CHARACTER_NATASHA`), and ch04
# writes real text into 0x9BB/0x9BC right now. ch05's text insertion is still owed (#25), so
# this guard lands FIRST, deliberately.
# Ids the PROLOGUE and ch01 write as bare literals inside their injectors. They have no
# `*_MSG` constant to be found by name, and neither chapter declares a block -- so until they
# were registered here, both guard sources were blind to them. 0xC25 is the sharp one: it sits
# 0x33 above ch05's 0xBC5-0xBF2, so the obvious next move (extend ch05's pool upward) would
# have been accepted and would have overwritten Scramsax's defeat quote.
PROLOGUE_LITERAL_MSGS = (0x664, 0x90D, 0x90E, 0x914, 0x917, 0x918, 0x936, 0xC25)
CH01_LITERAL_MSGS = (0x93B, 0x93C, 0x955, 0x961)


# `--ch05-ending=<arm>`: the roster states the ending branches on, named. The Lupin dimension is
# NOT here -- `--ch05-lupin` already exists and composes with each of these, so the six films are
# three arms x two flags rather than six flags.
CH05_ENDING_ARMS = ('full', 'no-sahnar', 'basil-died')
