"""The injection steps, in the order they run, each declaring what it writes and needs (#409).

`build_campaign.main()` used to run these as ~60 statements whose order was load-bearing, and
three mechanisms recovered the facts from outside: `check.py` regexed main()'s text for
hand-pinned MUST-precede pairs, a second regex kept boot-flag readers behind the cached steps,
and `build_scopes` parsed a chapter out of each function's name. Each step now says those
things itself, and the runner holds it to them:

  * `writes` -- decomp globs (relative to the build tree). A path the injection wrote that no
    step that ran declares fails the build (`check_footprint`); under INJECT_STRICT=1 (CI, the
    fingerprint gate) each step's writes are OBSERVED as it runs and a stray one fails the
    build naming the step and the path.
  * `needs` / `provides` -- named facts, each with its why in FACTS. Every provider of a fact
    must be listed before every step that needs it, or the build fails before writing
    anything. File-level reads cannot carry this: ch01 copies slot 1's goal block while it
    is still vanilla and ch04 copies ch02's AFTER ch02 hosted it -- two reads of one file
    that want opposite states.
  * `flags` -- the boot flags a step reads. A step (and its `when`) is handed a view of the
    arguments that holds `campaign` and its declared flags and raises on anything else, so the
    declaration is checked, not trusted.
  * `cached` -- restored across ROM configurations by the step cache (#309), which is sound
    only while nothing configuration-dependent has run. So every cached step must be listed
    before every step that reads a flag.
  * `scope` -- the playtest matrix's attribution for the step's writes (#255).

The listed order IS the execution order. It is validated rather than sorted: a sort would be
free to move appends (message ids, SMS ids) and so the ROM.
"""
import fnmatch
import inspect
import os
import sys

from inject.arena import inject_arena_attendant_portraits, inject_arena_presentation
from inject.backgrounds import inject_backgrounds
from inject.battle_anims import inject_battle_anims
from inject.boot import _configure_boot, TEST_CHAPTER_INDEX
from inject.chapter_settings import apply_chapter_difficulty, apply_chapter_fog
from inject.chapters.ch01 import inject_ch01, inject_northlook_bitey
from inject.chapters.ch02 import inject_ch02, inject_ch02_chwinga_faces
from inject.chapters.ch03 import inject_ch03
from inject.chapters.ch04 import chain_ch03_to_ch04, inject_ch04
from inject.chapters.ch05 import chain_ch04_to_ch05, inject_ch05, inject_ch05_visit_faces
from inject.chapters.ch06 import chain_ch05_to_ch06, inject_ch06
from inject.chapters.prologue import inject_prologue
from inject.crit_flourish import inject_crit_flourish
from inject.death_quotes import inject_pc_death_quotes
from inject.decomp import DECOMP
from inject.engine_patches import apply_engine_patches, patched_files
from inject.hosts import (
    CH01_HOST_INDEX, CH03_HOST_INDEX, CH04_HOST_INDEX, CH05_HOST_INDEX, CH06_HOST_INDEX,
    PROLOGUE_HOST_INDEX)
from inject.item_icons import inject_item_icon_pal2, inject_item_icons
from inject.map_sprites import inject_map_sprites
from inject.maps import inject_winter_tileset
from inject.messages import (
    assert_literals_are_claimed, assert_message_blocks_disjoint, assert_message_ids_unique,
    assert_named_raw_pids_are_exclusive, live_ids_in_declared_blocks)
from inject.names import inject_item_names, inject_names
from inject.platforms import inject_battle_platforms
from inject.portraits import inject_portraits, patch_portrait_geometry
from inject.raw_pids import patch_raw_pid_portraits
from inject.reskins import inject_enemy_class_battle_anims, inject_enemy_class_reskins
from inject.sms import sms_alloc_report, sms_alloc_reset
from inject.stats import patch_character_data
from inject.test_chapter import inject_test_chapter
from inject.text import reserve_appended_messages
from inject.title import inject_title_screen, inject_title_theme
from inject.traps import apply_chapter_traps
from inject.warm import PATCHED_DECOMP_FILES, restore_vanilla_sources


# What a step can need, and why the order matters. A fact with no provider, or a provider
# listed after a step that needs it, fails the build.
FACTS = {
    'engine-patches': 'a step that edits or reads a file the engine patches changed, as they '
                      'left it (git apply needs the vanilla text under them)',
    'sms-pool': 'one SMS id pool for the whole build -- both sprite passes spend from it (#227)',
    'map-sprite-sms-ids': 'reskins consume the SMS ids map-sprite injection allocates',
    'reskin-classes': 'the reskinned clone classes: their battle anims bind .pBattleAnimDef on '
                      'them, and chapter rosters (goblin grunts, skeletons) ride them',
    'tileset-labels': 'chapter maps register against the winter tileset asset-table labels',
    'slot1-goal-copied': "inject_ch01 copies vanilla slot 1's Seize goal block, which "
                         'inject_prologue then overwrites',
    'ch02-goal': "ch04 borrows ch02's hosted DefeatAll/Rout goal block",
    'ch03-landing': "chain_ch03_to_ch04 rewrites the dev-placeholder landing inject_ch03 wrote",
    'ch03-hosted': 'chapter hosts are injected in campaign order',
    'ch04-hosted': 'chapter hosts are injected in campaign order, and a chain into ch04 points '
                   'at the slot inject_ch04 hosts',
    'ch04-landing': "chain_ch04_to_ch05 rewrites the dev-placeholder landing inject_ch04 wrote",
    'ch05-hosted': 'chapter hosts are injected in campaign order, and a chain into ch05 points '
                   'at the slot inject_ch05 hosts',
    'ch05-landing': "chain_ch05_to_ch06 rewrites the dev-placeholder landing inject_ch05 wrote",
    'appended-messages': 'a message id past vanilla\'s last exists only once its header is '
                         'reserved (inject/message_alloc.py)',
    'ch06-hosted': 'a chain into ch06 points at the slot inject_ch06 hosts',
}


def _host(slot, layout, *extra):
    """What hosting a chapter in vanilla slot `slot` writes: its title card, its map, its event
    files, and its rows in the shared chapter tables."""
    return ('graphics/chap_title/chap_title_%d.*' % slot,
            'graphics/map/layout/%s.*' % layout,
            'src/events/ch%d-*' % slot,
            'data/const_data_chapter_maps.s', 'data/data_8B363C.s',
            'src/data/chapter_settings.json', 'src/data_battlequotes.c', 'src/events_udefs.c',
            'texts/texts.txt') + extra


# A map's tileset, registered by the first chapter that uses it.
def _tileset(name):
    return ('graphics/map/MapPalette%s.gbapal' % name, 'graphics/map/ObjectType%s.4bpp' % name,
            'graphics/map/TileConfiguration%s.bin' % name)


PORTRAIT = ('graphics/portrait/portrait_*',)
UNIT_ICONS = ('graphics/unit_icon/move/*', 'graphics/unit_icon/wait/*',
              'data/const_data_unit_icon_move.s', 'data/const_data_unit_icon_wait.s',
              'include/unit_icon_pointer.h', 'src/unit_icon_move_data.c',
              'src/unit_icon_wait_data.c')
BANIMS = ('graphics/banim/*', 'data/banim/*', 'include/banim_pointer.h', 'include/ekrbattle.h',
          'linker_script_banim_ext.txt', 'src/banim_data.c', 'src/data_banimconf.c')


class Step(object):
    def __init__(self, fn, call=None, title=None, note=None, writes=(), needs=(), provides=(),
                 flags=(), scope='global', cached=False, when=None):
        self.fn = fn
        self.name = fn.__name__
        self.call = call
        self.title = title
        self.note = note
        self.writes = tuple(writes)
        self.needs = tuple(needs)
        self.provides = tuple(provides)
        self.flags = tuple(flags)
        self.scope = scope
        self.cached = cached
        self.when = when

    def invoke(self, view):
        if self.call is not None:
            return self.call(self.fn, view)
        if 'campaign' in inspect.signature(self.fn).parameters:
            return self.fn(view.campaign)
        return self.fn()

    def undeclared(self, wrote):
        """The paths in `wrote` (relative to the tree) that match none of this step's globs."""
        return sorted(p for p in wrote
                      if not any(fnmatch.fnmatchcase(p, g) for g in self.writes))


def _assert_declared_blocks_clear():
    # The third of the message-ownership family. It ran only from the tests, so `make check`
    # caught it but a plain `make` with an edited block table still produced a ROM -- and the
    # whole point of these is to fail the BUILD rather than let a collision ship.
    drawn_over = live_ids_in_declared_blocks()
    if drawn_over:
        sys.exit('ERROR: declared message block(s) drawn over ids the build already '
                 'spends: %s' % ', '.join(drawn_over))


def _boot(index, **kwargs):
    return lambda fn, a: fn(index, **kwargs)


BOOT = ('src/bmio.c', 'src/gamecontrol.c', 'src/events/prologue-wm.h')
BOOT_FLAGS = ('ch01_boot', 'ch03_boot', 'ch04_boot', 'ch05_boot', 'ch06_boot')
# The slot 1 sandbox, written over the prologue's event files.
TEST_CHAPTER = ('src/events/ch1-*',)
# The #43 opening montage: the lore crawl's subtitle cards, its mural and the drawn world maps.
MONTAGE = ('graphics/op_subtitle/*', 'graphics/world_map/MontageDrawnMap*',
           'data/data_opsubtitle.s', 'src/opsubtitle.c', 'src/worldmap_rm.c',
           'src/events/prologue-wm.h')


def _any_boot(a):
    return any(getattr(a, flag) for flag in BOOT_FLAGS)


def _canonical(a):
    """The New Game path a release ships: no fast-boot and no sandbox."""
    return not a.test_chapter and not _any_boot(a)


STEPS = [
    Step(inject_portraits, title='portraits:', writes=PORTRAIT),
    Step(inject_arena_attendant_portraits, writes=PORTRAIT),
    # A clean base each build (idempotent; vanilla donor reads).
    Step(restore_vanilla_sources, writes=PATCHED_DECOMP_FILES),
    # The campaign-agnostic engine changes (#410): engine/patches/, applied in one go.
    Step(apply_engine_patches, title='engine patches:', writes=patched_files(),
         provides=('engine-patches',)),
    Step(inject_arena_presentation, needs=('engine-patches',),
         writes=('src/banim-ekrarena.c', 'src/uiarena.c')),
    # Every allocated message id gets its header before anything writes one (#411).
    Step(reserve_appended_messages, title='appended messages (#411):',
         writes=('texts/texts.txt',), provides=('appended-messages',)),
    Step(inject_names, title='names:', needs=('appended-messages',),
         writes=('texts/texts.txt',)),
    Step(inject_item_names, title='item names:', writes=('texts/texts.txt',)),
    Step(inject_item_icons, title='item icons:', writes=('graphics/item_icon/*',)),
    Step(inject_item_icon_pal2,
         writes=('graphics/item_icon/*', 'data/const_data_chapter_maps.s')),
    Step(patch_character_data, title='characters:', writes=('src/data_characters.c',)),
    Step(patch_raw_pid_portraits, writes=('src/data_characters.c',)),
    Step(patch_portrait_geometry, title='portrait geometry:', writes=('src/portrait_data.c',)),
    Step(sms_alloc_reset, title='map sprites:', call=lambda fn, a: fn(a.campaign, verbose=True),
         provides=('sms-pool',)),
    Step(inject_map_sprites, needs=('sms-pool',), provides=('map-sprite-sms-ids',),
         writes=UNIT_ICONS + ('src/bmudisp.c', 'src/bmunit.c', 'src/mu.c',
                              'src/prep_unitselect.c', 'src/unitlistscreen.c')),
    Step(inject_enemy_class_reskins, title='enemy class reskins (#21):',
         needs=('sms-pool', 'map-sprite-sms-ids'), provides=('reskin-classes',),
         writes=UNIT_ICONS + ('include/constants/classes.h', 'src/data_classes.c')),
    Step(sms_alloc_report, needs=('map-sprite-sms-ids', 'reskin-classes')),
    # The two most expensive steps in the build (17.1s + 8.5s of a ~50s `make`, measured
    # 2026-08-23) and the two that NO boot flag reaches -- every ROM configuration pays them to
    # produce byte-identical data, and the matrix builds five for one gate. So they are cached
    # on their inputs (#309), which `validate` keeps sound by holding them ahead of every
    # flag reader.
    Step(inject_enemy_class_battle_anims, title='enemy class battle anims (#90):', cached=True,
         needs=('reskin-classes',), writes=BANIMS + ('src/data_classes.c',)),
    Step(inject_battle_anims, title='battle anims (#65):', cached=True,
         writes=BANIMS + ('src/data_banimconfunk.c', 'src/data_characters.c')),
    Step(inject_winter_tileset, title='winter tileset:', provides=('tileset-labels',),
         writes=_tileset('Snow') + ('graphics/map/layout/ChTestSnowMap.*',
                                    'data/const_data_chapter_maps.s', 'data/data_8B363C.s',
                                    'src/data/chapter_settings.json')),
    Step(inject_battle_platforms, title='battle platforms (#65):',
         writes=('graphics/banim/terrain/*', 'data/data_banim_terrain.s',
                 'include/banim_pointer.h', 'include/variables.h', 'src/banim-battleparse.c',
                 'src/banim_terrain_data.c', 'src/data_terrains.c',
                 'src/data/chapter_settings.json')),
    Step(inject_crit_flourish, title='crit flourish (#11):',
         writes=('graphics/banim/msd20crit_*', 'data/data_banim.s', 'src/banim-efxhit.c')),
    Step(inject_title_theme, title='title theme:',
         writes=('data/campaign_*.bin', 'data/data_A01CC4.s', 'data/data_A21658.s')),
    Step(inject_title_screen, title='title screen:',
         writes=('graphics/titlescreen/*', 'src/titlescreen.c')),
    # Vendored winter BGs -> new gConvoBackgroundData slots.
    Step(inject_backgrounds, title='event backgrounds (#22):',
         writes=('graphics/bg/*', 'data/data_bg.s', 'include/bg.h',
                 'include/constants/backgrounds.h', 'src/eventscr2.c')),
    # Ownership gate (#198 review): fail the build BEFORE any injector writes text if two
    # hosted chapters claim one message id -- a double-claim is otherwise silent, since
    # verify_text checks runaway text, not who owns a slot.
    Step(assert_message_ids_unique),
    Step(assert_named_raw_pids_are_exclusive),
    Step(assert_literals_are_claimed),
    Step(assert_message_blocks_disjoint),   # the setup that would make a collision inevitable
    Step(_assert_declared_blocks_clear),
    Step(inject_ch01, title='chapter 1 (#21):', scope='chapter:ch01',
         call=lambda fn, a: fn(a.campaign, boot=a.ch01_boot), flags=('ch01_boot',),
         needs=('reskin-classes', 'tileset-labels', 'appended-messages'),
         provides=('slot1-goal-copied',),
         writes=_host(2, 'Ch01IronTrailMap', 'include/eventcall.h')),
    # 'Ol Bitey over the tavern hearth (Beat 1 set dressing). Global: the fireplace is also
    # the backdrop of the dev placeholder scene the later chapters' endings play.
    Step(inject_northlook_bitey, writes=('graphics/bg/bg_Fireplace.png',)),
    # Hosts slot 3; ch01's ending MNC2(0x3) lands here.
    Step(inject_ch02, title='chapter 2 (#22):', scope='chapter:ch02',
         needs=('reskin-classes', 'tileset-labels'), provides=('ch02-goal',),
         writes=_host(3, 'Ch02ColdWelcomeMap')),
    # The green chwinga bust + Mote/Rime/Glimmer names.
    Step(inject_ch02_chwinga_faces, scope='chapter:ch02', writes=PORTRAIT + ('texts/texts.txt',)),
    Step(inject_ch03, title='chapter 3 (#23):', scope='chapter:ch03',
         call=lambda fn, a: fn(a.campaign, boot=a.ch03_boot), flags=('ch03_boot',),
         needs=('reskin-classes', 'tileset-labels'), provides=('ch03-hosted', 'ch03-landing'),
         writes=_host(4, 'Ch03TermalaineMineMap', *_tileset('Cave'))),
    Step(inject_ch04, title='chapter 4 (#24):', scope='chapter:ch04',
         call=lambda fn, a: fn(a.campaign, boot=a.ch04_boot), flags=('ch04_boot',),
         needs=('engine-patches', 'reskin-classes', 'tileset-labels', 'ch02-goal',
                'ch03-hosted'),
         provides=('ch04-hosted', 'ch04-landing'),
         writes=_host(5, 'Ch04LonelywoodForestMap', 'src/data_event_trigger.c')),
    Step(chain_ch03_to_ch04, needs=('ch03-landing', 'ch04-hosted'),
         writes=('src/events/ch4-eventscript.h',)),
    Step(inject_ch05, title='chapter 5 (#25):', scope='chapter:ch05',
         call=lambda fn, a: fn(a.campaign, boot=a.ch05_boot, lupin_proof=a.ch05_lupin,
                               moose_only=a.ch05_moose, ending_arm=a.ch05_ending),
         flags=('ch05_boot', 'ch05_lupin', 'ch05_moose', 'ch05_ending'),
         needs=('tileset-labels', 'ch04-hosted'),
         provides=('ch05-hosted', 'ch05-landing'),
         writes=_host(6, 'Ch05ElvenTombMap', 'include/eventcall.h', 'src/cp_data.c',
                      *_tileset('PortTown'))),
    # The four reliquary residents' skeleton busts.
    Step(inject_ch05_visit_faces, scope='chapter:ch05', writes=PORTRAIT),
    Step(chain_ch04_to_ch05, needs=('ch04-landing', 'ch05-hosted'),
         writes=('src/events/ch5-eventscript.h',)),
    Step(inject_ch06, title='chapter 6 (#26):', scope='chapter:ch06',
         call=lambda fn, a: fn(a.campaign, boot=a.ch06_boot), flags=('ch06_boot',),
         needs=('reskin-classes', 'tileset-labels', 'ch05-hosted'),
         provides=('ch06-hosted',),
         writes=_host(7, 'Ch06MaerMonsterMap', 'include/eventcall.h', 'src/cp_data.c',
                      *_tileset('SnowIce'))),
    Step(chain_ch05_to_ch06, needs=('ch05-landing', 'ch06-hosted'),
         writes=('src/events/ch6-eventscript.h',)),
    # New Game's target: exactly one of these runs.
    Step(_configure_boot, title='CH06 BOOT (playtest: New Game -> Maer Dualdon, party + merfolk '
                                '+ boats):',
         call=_boot(CH06_HOST_INDEX), flags=('ch06_boot',), when=lambda a: a.ch06_boot,
         writes=BOOT),
    Step(_configure_boot, title='CH05 BOOT (playtest: New Game -> the Elven Tomb, party + foes '
                                'deployed):',
         call=_boot(CH05_HOST_INDEX), flags=('ch05_boot',), when=lambda a: a.ch05_boot,
         writes=BOOT),
    Step(_configure_boot, title='CH04 BOOT (playtest: New Game -> White Moose forest, party + '
                                'foes deployed):',
         call=_boot(CH04_HOST_INDEX), flags=('ch04_boot',), when=lambda a: a.ch04_boot,
         writes=BOOT),
    Step(_configure_boot, title='CH03 BOOT (playtest: New Game -> Termalaine Mine, party + foes '
                                'deployed):',
         call=_boot(CH03_HOST_INDEX), flags=('ch03_boot',), when=lambda a: a.ch03_boot,
         writes=BOOT),
    # No seed table here on purpose: ch01's own opening LOADs the company and runs PREP, so a
    # cold start founds its party exactly as the canonical chapter does.
    Step(_configure_boot, title='CH01 BOOT (playtest: New Game -> the Iron Trail, party founded '
                                'by ch01):',
         call=_boot(CH01_HOST_INDEX), flags=('ch01_boot',), when=lambda a: a.ch01_boot,
         writes=BOOT),
    # The slot 1 sandbox, in place of the prologue; it never montages.
    Step(inject_test_chapter, title='TEST CHAPTER (playtest: New Game -> Ch1 sandbox, cast '
                                    'deployed):',
         call=lambda fn, a: fn(a.campaign, lord_boot=a.lord_boot, bench=a.bench),
         flags=BOOT_FLAGS + ('test_chapter', 'lord_boot', 'bench'),
         when=lambda a: a.test_chapter and not _any_boot(a),
         needs=('reskin-classes',), writes=TEST_CHAPTER),
    Step(_configure_boot, call=_boot(TEST_CHAPTER_INDEX), flags=BOOT_FLAGS + ('test_chapter',),
         when=lambda a: a.test_chapter and not _any_boot(a), writes=BOOT),
    Step(inject_prologue, title='prologue (New Game target):', scope='chapter:prologue',
         call=lambda fn, a: fn(a.campaign, montage=a.montage),
         flags=BOOT_FLAGS + ('test_chapter', 'montage'), when=_canonical,
         needs=('tileset-labels', 'slot1-goal-copied'),
         writes=_host(1, 'Ch00PrologueMap', 'src/data_characters.c', 'src/gamecontrol.c')
         + MONTAGE),
    Step(_configure_boot, call=lambda fn, a: fn(PROLOGUE_HOST_INDEX, montage=a.montage),
         flags=BOOT_FLAGS + ('test_chapter', 'montage'), when=_canonical, writes=BOOT),
    Step(inject_pc_death_quotes, title='death quotes (#6):',
         writes=('src/data_battlequotes.c', 'texts/texts.txt')),
    # LAST of the chapter passes: every hosted slot now exists, so this is where the registry
    # can insist each one DECLARED its numbers instead of keeping the donor's (#303). Fog is
    # the fifth and last chapter_settings field that could be inherited unexamined (#365): two
    # injectors wrote it inline and five chapters kept whatever their squatted slot shipped --
    # including ch06, whose host slot 7 is one of vanilla's five FOGGED slots. Total pass, so
    # "no injector wrote a line for this chapter" is unreachable.
    Step(apply_chapter_fog, title='fog (#365):', call=lambda fn, a: fn(a.campaign, verbose=True),
         writes=('src/data/chapter_settings.json',)),
    Step(apply_chapter_difficulty, title='difficulty modes (#303):',
         call=lambda fn, a: fn(a.campaign, verbose=True),
         writes=('src/data/chapter_settings.json',)),
    # Same pass, same reason: `.traps` is a ChapterEventGroup field our injectors fill but
    # never wrote, so a chapter kept its donor's. ch06 fills Ch7EventData, and vanilla Ch7
    # carries two ballistae -- writing the declaration makes that impossible (#302).
    Step(apply_chapter_traps, title='traps (#302):',
         call=lambda fn, a: fn(a.campaign, verbose=True), writes=('src/events_trapdata.c',)),
]


class FlagView(object):
    """The build's arguments as one step may read them: `campaign` and its declared flags."""

    def __init__(self, args, step):
        self._args = args
        self._step = step

    def __getattr__(self, name):
        if name == 'campaign' or name in self._step.flags:
            return getattr(self._args, name)
        raise AttributeError('%s reads --%s but does not declare it in its `flags` (#409)'
                             % (self._step.name, name.replace('_', '-')))


def validate(steps):
    """Every way the listed order can contradict the declarations, as messages."""
    problems = []
    position = {}
    for i, step in enumerate(steps):
        for fact in step.provides + step.needs:
            if fact not in FACTS:
                problems.append('%s names fact %r, which FACTS does not define' % (step.name, fact))
        for fact in step.provides:
            position.setdefault(fact, []).append(i)
    for i, step in enumerate(steps):
        for fact in step.needs:
            providers = position.get(fact)
            if not providers:
                problems.append('%s needs %r, which no step provides' % (step.name, fact))
            for j in providers or ():
                if j > i:
                    problems.append('%s must run before %s -- %s'
                                    % (steps[j].name, step.name, FACTS[fact]))
    flagged = [i for i, step in enumerate(steps) if step.flags]
    for i, step in enumerate(steps):
        if step.cached and flagged and flagged[0] < i:
            problems.append(
                'injection cache: %s is restored across ROM configurations, but %s reads a boot '
                'flag and runs FIRST -- a restored output would then depend on which '
                'configuration built it (#309)' % (step.name, steps[flagged[0]].name))
    return problems


def strict():
    """Check each step's writes as it runs (CI's build and the fingerprint gate). A walk of the
    whole tree around each of ~60 steps adds ~16s to a ~53s injection on the Mac, so an
    ordinary build checks the whole injection's writes once instead (`check_footprint`), and
    walks only around the chapter steps, for their scopes."""
    return os.environ.get('INJECT_STRICT') == '1'


def run(steps, args, scopes, anims):
    """Run `steps` in order; returns the steps that ran."""
    problems = validate(steps)
    if problems:
        sys.exit('ERROR: the injection steps contradict their declarations (#409):\n  '
                 + '\n  '.join(problems))
    ran = []
    for step in steps:
        view = FlagView(args, step)
        if step.when is not None and not step.when(view):
            continue
        if step.title:
            print(step.title)
        if step.cached:
            thunk = lambda: anims.run(lambda *_: step.invoke(view), name=step.name)  # noqa: E731
        else:
            thunk = lambda: step.invoke(view)  # noqa: E731
        if strict() or step.scope != 'global':
            undeclared = step.undeclared(scopes.watch(step.scope, thunk))
        else:
            thunk()
            undeclared = ()
        if step.note:
            print('  ' + step.note)
        if undeclared:
            sys.exit('ERROR: %s wrote %s, which its `writes` do not declare (#409). Declare '
                     'it in inject/steps.py, or stop writing it.'
                     % (step.name, ', '.join(undeclared)))
        ran.append(step)
    return ran


def check_footprint(ran, wrote):
    """The whole injection's half of the write check: every path it wrote (relative to the
    tree) must be declared by some step that ran."""
    undeclared = sorted(p for p in wrote if all(step.undeclared([p]) for step in ran))
    if undeclared:
        sys.exit('ERROR: the injection wrote %s, which no step declares in its `writes` '
                 '(#409). INJECT_STRICT=1 names the step.' % ', '.join(undeclared))
