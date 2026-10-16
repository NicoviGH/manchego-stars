"""Our pages as the Fire Emblem Wiki writes its own: wikitext calling its templates (#493).

Each function takes plain data (no YAML, no decomp) and returns the wikitext of one page, laid out
section for section like the vendored exemplar of that page type (`tools/wiki/vendor/pages/`):
the same headings in the same order, the same templates with the same parameters. A section the
exemplar has and we have no data for is left out, as the wiki leaves out an empty one. The data
is `gen_wiki`'s to gather; the layout is the wiki's, and lives here.
"""

STAT_RANGE_NOTE = (":''Stats with two figures separated by a ~ are presented as a range, "
                   "representing stats that vary due to random growths. The figures to the left "
                   "and right of the ~ are the stat's minimum and maximum possible values "
                   "respectively.''")
GAME = '08'          # the game number the templates key their art and pixel-art styling on


def _params(name, pairs, multiline=True):
    """{{name|k=v|...}}, one parameter per line as the wiki's own source writes them."""
    sep = '\n|' if multiline else '|'
    body = sep.join('%s=%s' % (k, v) for k, v in pairs if v is not None)
    return '{{%s%s%s%s}}' % (name, sep if body else '', body, '\n' if multiline and body else '')


def item(name, link=None, image=None, drop=False):
    """{{Item|8|name}}: icon + link, as an inventory or reward line names an item."""
    extra = ''.join('|%s=%s' % kv for kv in (('link', link), ('image', image)) if kv[1])
    return '{{Item|8|%s%s%s}}' % (name, extra, '|type=drop' if drop else '')


def hover(text, tip):
    return '{{h|%s|%s}}' % (text, tip)


def unit_cell(u, last=False):
    """One {{ChapUnitCellGBA}} row: an enemy, NPC or reinforcement."""
    return _params('ChapUnitCellGBA', [
        ('name', u['name']), ('class', u['class']), ('classarticle', u.get('class_article')),
        ('version', u.get('version')), ('type', u.get('type')),
        ('lv', u['lv']), ('#', u['n']),
        ('hp', u['hp']), ('str', u['str']), ('skill', u['skl']), ('spd', u['spd']),
        ('lck', u['lck']), ('def', u['def']), ('res', u['res']), ('con', u['con']),
        ('mov', u['mov']), ('inventory', ' • '.join(u['inventory']) or None),
        ('notes', u.get('notes')), ('last', 'yes' if last else None)])


def unit_table(kind, rows):
    """{{ChapUnitHdr}} + rows + {{ChapUnitFtr}}: one Enemy/NPC table."""
    cells = [unit_cell(r, last=(i == len(rows) - 1)) for i, r in enumerate(rows)]
    return '\n'.join(['{{ChapUnitHdr|type=%s|platform=gba}}' % kind] + cells + ['{{ChapUnitFtr}}'])


def tabs(labels, contents, default=None, width='100%'):
    pairs = [('width', width)] if width else []
    pairs += [('tab%d' % (i + 1), l) for i, l in enumerate(labels)]
    if default:
        pairs.append(('default', default))
    pairs += [('content%d' % (i + 1), c) for i, c in enumerate(contents)]
    return _params('Tab', pairs)


def boss_stats(b):
    """{{BossStats GBA}}: one boss on one difficulty."""
    return _params('BossStats GBA', [
        ('portrait', b.get('portrait')), ('sprite', b.get('sprite')), ('class', b['class']),
        ('classlink', b.get('class_article')), ('lv', b['lv']), ('affin', b.get('affinity')),
        ('HP', b['hp']), ('str', b.get('str')), ('mag', b.get('mag')), ('skill', b['skl']),
        ('spd', b['spd']), ('luck', b['lck']), ('def', b['def']), ('res', b['res']),
        ('con', b['con']), ('move', b['mov']), ('aid', b['aid']),
        ('inventory', '<br>'.join(b['inventory']) or None),
        ('sw', b['ranks'].get('sw')), ('la', b['ranks'].get('la')), ('ax', b['ranks'].get('ax')),
        ('bo', b['ranks'].get('bo')), ('an', b['ranks'].get('an')), ('li', b['ranks'].get('li')),
        ('da', b['ranks'].get('da')), ('st', b['ranks'].get('st'))])


def chapter(c):
    """A chapter page, laid out as `The Bandits of Borgo` / `The Protected` are."""
    out = [_params('Chapter Infobox', [
        ('image', c.get('image')), ('location', c.get('location')),
        ('new units', ', '.join('[[%s]]' % t for t in c.get('new_units', [])) or None),
        ('boss', ', '.join('[[%s]]' % t for t in c.get('bosses', [])) or None),
        ('previous', '[[%s]]' % c['previous'] if c.get('previous') else None),
        ('next', '[[%s]]' % c['next'] if c.get('next') else None)])]
    out.append("'''%s''' is %s." % (c['title'], c['lead']))
    if c.get('plot') or c.get('script_title'):
        out.append('==Plot==')
        if c.get('script_title'):
            out.append('{{main|%s}}' % c['script_title'])
        if c.get('plot'):
            out.append(c['plot'])

    out.append('==Chapter data==')
    out.append(_params('ChapData', [
        ('victory', c['victory']), ('defeat', c['defeat']), ('ally', c['ally']),
        ('other', c.get('other')), ('enemy', c['enemy']), ('map', c.get('map')),
        ('col', c.get('cols')), ('row', c.get('rows'))]))

    if c.get('new_unit_cards') or c.get('available') or c.get('forced'):
        pairs = [('game#', GAME)]
        for i, u in enumerate(c.get('new_unit_cards', []), 1):
            pairs.append(('newunit%d' % i, _params('NewUnit', [
                ('name', u['name']), ('namearticle', u.get('page')),
                ('portrait', u.get('portrait')), ('class', u['class']),
                ('classarticle', u.get('class_article')), ('HP', u['hp']), ('lv', u['lv']),
                ('inventory', '<br>'.join(u['inventory'])),
                ('recruitment method', u['how'])])))
        for group, units in (('forced', c.get('forced', [])), ('return', c.get('available', []))):
            for i, u in enumerate(units, 1):
                pairs += [('%s%d' % (group, i), u['image_key']),
                          ('%s%darticle' % (group, i), u['page']),
                          ('%s%dalt' % (group, i), u['name'])]
        out.append('===Character data===')
        out.append(_params('ChapChars', pairs))

    if c.get('items'):
        pairs = [('platform', 'gba')]
        for i, (name, how, extra) in enumerate(c['items'], 1):
            last = i == len(c['items'])
            key = 'last' if last else str(i)
            pairs += [('item' + key, name), ('obtain' + key, how)]
            pairs += [('item%s%s' % (key, k), v) for k, v in (extra or {}).items()]
        out.append('===Item data===')
        out.append(_params('ChapItems', pairs))

    if c.get('shops'):
        pairs = []
        for i, (label, stock) in enumerate(c['shops'], 1):
            pairs.append(('shop%d' % i, label))
            pairs.append(('stock%d' % i, '\n' + '\n'.join(
                '{{ChapShopCell|fe08|%s|%s}}' % (name, price) for name, price in stock)))
        out.append('===Shop data===')
        out.append(_params('ChapShop', pairs))

    if c.get('enemy_tabs'):
        out.append('===Enemy data===')
        out.append(STAT_RANGE_NOTE)
        labels = [l for l, _ in c['enemy_tabs']]
        contents = [unit_table('Enemy', rows) for _, rows in c['enemy_tabs']]
        out.append(tabs(labels, contents, c.get('enemy_default')) if len(labels) > 1
                   else contents[0])
    if c.get('npcs'):
        out.append('===NPC data===')
        out.append(unit_table('NPC', c['npcs']))
    if c.get('reinforcements'):
        out.append('====Reinforcements====')
        out.append('\n'.join('*Turn %s\n%s' % (turn, '\n'.join('**' + line for line in lines))
                              for turn, lines in c['reinforcements']))   # one list: no blank lines

    if c.get('bosses_data'):
        out.append('===Boss data===')
        out.append(STAT_RANGE_NOTE)
        for b in c['bosses_data']:
            out.append('{{main|%s}}' % b['page'])
            if len(b['modes']) > 1:
                out.append(tabs([l for l, _ in b['modes']],
                                [boss_stats(s) for _, s in b['modes']], width=None))
            else:
                out.append(boss_stats(b['modes'][0][1]))

    if c.get('strategy'):
        out.append('==Strategy==')
        out.append('{{strategy}}')
        out.append(c['strategy'])

    out.append(_params('ChapterNav', [
        ('prechapter', c.get('previous')), ('nextchapter', c.get('next'))]))
    if c.get('navbox'):
        out.append(c['navbox'])
    return '\n\n'.join(out) + '\n'


# A Script page's sections, in the order `The Bandits of Borgo/Script` and its siblings use.
SCRIPT_SECTIONS = ('Introduction', 'Opening', 'In battle', 'Talk conversations', 'Villages',
                   'Battle quotes', 'Ending')


def _scene(steps):
    """One scene as the wiki transcribes it: a speaker's turn per line, `<br>` between lines,
    narration in {{Quote}}, a stage direction in parentheses ("(Artur leaves)"). Consecutive
    boxes from one speaker are one turn, as they read.

    steps: [(kind, speaker, text)], kind 'say' | 'narrate' | 'stage'."""
    turns = []
    for kind, who, text in steps:
        if turns and kind == 'say' and turns[-1][:2] == (kind, who):
            turns[-1][2].append(text)
        else:
            turns.append((kind, who, [text]))
    lines = []
    for kind, who, t in turns:
        text = ' '.join(t)
        lines.append('{{Quote|%s}}' % text if kind == 'narrate' else
                     '(%s)' % text if kind == 'stage' else "'''%s:''' %s" % (who, text))
    return '\n'.join(l + ('<br>' if i + 1 < len(lines) and not l.startswith('{{')
                          and not lines[i + 1].startswith('{{') else '')
                     for i, l in enumerate(lines))


def script(c):
    """A chapter's Script subpage, laid out as `The Bandits of Borgo/Script` is.

    c['sections']: {section: [(subheading or None, [scene])]}, a scene being `_scene`'s steps,
    a (label, steps) variant of it (the wiki's "====Visit with Eirika===="), or a plain
    paragraph (a planned chapter's beat, not yet written)."""
    out = []
    for name in SCRIPT_SECTIONS:
        groups = c['sections'].get(name)
        if not groups:
            continue
        out.append('==%s==' % name)
        for sub, scenes in groups:
            if sub:
                out.append('===%s===' % sub)
            out.append('\n\n'.join(
                s if isinstance(s, str) else
                '====%s====\n%s' % (s[0], _scene(s[1])) if isinstance(s, tuple) else _scene(s)
                for s in scenes))
    script_link = lambda t: '%s/Script{{!}}%s' % (t, t) if t else None
    out.append(_params('ChapterNav', [
        ('name', c['title']), ('prechapter', script_link(c.get('previous'))),
        ('nextchapter', script_link(c.get('next')))]))
    if c.get('navbox'):
        out.append(c['navbox'])
    return '\n\n'.join(out) + '\n'


GAME_HEADING = "==''Manchego Stars''=="   # the exemplars' =={{FE8}}==: the game the section covers


def char_stats(s):
    """{{CharStats GBA}}: a playable unit's starting line, growths and how it joins."""
    pairs = [('portrait', s.get('portrait')), ('sprite', s.get('sprite')), ('class', s['class']),
             ('affin', s.get('affinity')), ('lv', s['lv']), ('HP', s['hp']),
             ('mag' if s.get('magic') else 'str', s['str']), ('skill', s['skl']),
             ('spd', s['spd']), ('luck', s['lck']), ('def', s['def']), ('res', s['res']),
             ('move', s['mov']), ('con', s['con']), ('aid', s['aid']),
             ('inventory', '<br>'.join(s['inventory']) or None)]
    pairs += [(k, v) for k, v in sorted(s['ranks'].items()) if v]
    g = s['growths']
    pairs += [('HP1', g['hp']), ('mag1' if s.get('magic') else 'str1', g['str']),
              ('skill1', g['skl']), ('spd1', g['spd']), ('luck1', g['lck']),
              ('def1', g['def']), ('res1', g['res']), ('recruit', s.get('recruit'))]
    return _params('CharStats GBA', pairs)


def promotion_gains(branches):
    """{{PromotionGains}}: one column per promotion; the last is unnumbered, as Colm's is."""
    pairs = []
    for i, b in enumerate(branches, 1):
        n = '' if i == len(branches) else str(i)
        pairs += [('class' + n, b['class'])] + [(k + n, b[k]) for k in (
            'hp', 'str', 'skill', 'spd', 'def', 'res', 'con', 'move', 'weaponlvl')]
    return _params('PromotionGains', pairs)


def character(c):
    """A character page, laid out as `Colm` (playable), `Dara` (NPC) and `Bazba` (boss) are."""
    out = [_params('Character Infobox', [
        ('name', c['name']), ('image', c.get('image')), ('caption', c.get('caption')),
        ('help_text', c.get('help_text')), ('gender', c.get('gender')),
        ('race', c.get('race')), ('startingclass', c.get('startingclass')),
        ('appearances', "''Manchego Stars''")])]
    if c.get('quote'):
        out.append('{{Quote|%s|%s}}' % c['quote'])
    out.append("'''%s''' is %s." % (c['name'], c['lead']))
    sections = [('===Role===', c.get('role'))]
    if c.get('char_stats'):
        sections.append(('===Starting stats and growth rates===', char_stats(c['char_stats'])))
    if c.get('promotions'):
        sections.append(('===Promotion stat gains===', promotion_gains(c['promotions'])))
    if c.get('boss_modes'):
        modes = c['boss_modes']
        body = boss_stats(modes[0][1]) if len(modes) == 1 else tabs(
            [l for l, _ in modes], [boss_stats(s) for _, s in modes], width=None)
        sections.append(('===Stats===', '{{also|%s}}\n%s\n%s' % (
            c['chapter'], STAT_RANGE_NOTE, body)))
    sections = [(h, b) for h, b in sections if b]
    if sections:
        out.append(GAME_HEADING)
        out += ['%s\n%s' % hb for hb in sections]
    if c.get('personality'):
        out.append('==Personality==\n' + c['personality'])
    quotes = [('===Battle quote%s===' % ('s' if len(c.get('battle_quotes') or []) > 1 else ''),
               '\n'.join('{{Quote|%s|%s}}' % q for q in c.get('battle_quotes') or [])),
              ('===Death quote===', '{{Quote|%s|%s}}' % c['death_quote']
               if c.get('death_quote') else None)]
    quotes = [(h, b) for h, b in quotes if b]
    if quotes:
        out.append('==Quotes==')
        out += ['%s\n%s' % hb for hb in quotes]
    if c.get('help_text'):
        out.append('==Flavor text==\n{{DescriptionHdr}}\n%s\n{{DescriptionFtr}}' % _params(
            'DescriptionCell', [('game', "''Manchego Stars''"), ('english', c['help_text'])]))
    if c.get('trivia'):
        out.append('==Trivia==\n' + '\n'.join('*' + t for t in c['trivia']))
    if c.get('gallery'):
        out.append('==Gallery==\n' + gallery(c['name'], c['gallery']))
    if c.get('navbox'):
        out.append(c['navbox'])
    return '\n\n'.join(out) + '\n'


_BORDER = 'style="border-left: 1px solid {{Color2}}%s"'


def gallery(name, g):
    """Colm's Gallery: a collapsed Sprite Gallery (portrait, then the map sprite of each class
    the unit can be), then the artwork in a <gallery>."""
    out = []
    if g.get('sprites'):
        cells = ['| %s | %s%s' % (_BORDER % '', '[[%s]] ' % cls, '[[File:%s]]' % f if f else '')
                 for cls, f in g['sprites']]
        out.append('\n'.join([
            '{| class="mw-collapsible mw-collapsed pixel-art width-75" style="margin: auto; '
            'border: 2px solid {{Color2}}; background: {{Color1}}; border-radius: 15px; '
            'text-align: center"',
            '! style="border: 1px solid {{Color2}}; background: {{Color1}}; border-radius: '
            '15px" | %sSprite Gallery' % ('[[File:%s]] ' % g['minimug'] if g.get('minimug') else ''),
            '|-', '|',
            '{| style="width: 100%; background: {{Color3}}; border-radius: 15px; border: 1px '
            'solid {{Color2}}; margin: auto; border-spacing: 0"',
            '| %s' % ('[[File:%s]]' % g['portrait'] if g.get('portrait') else '')] + cells +
            ['|}', '|}']))
    if g.get('artwork'):
        out.append('===Official artwork===\n<gallery>\n%s\n</gallery>' % '\n'.join(
            '%s|%s' % fc for fc in g['artwork']))
    return '\n\n'.join(out)


def character_list(c):
    """`List of characters in Fire Emblem: The Sacred Stones`: playable characters, then bosses,
    then the other named characters, each in the wiki's own list templates."""
    out = ["This page contains a list of characters appearing in ''Manchego Stars''."]
    out.append('==Playable characters==')
    out.append('\n'.join(['{{CharListHdr|class=pixel-art-3x}}'] + [
        '{{CharListCell|%s|%s|%s|%s|%s}}' % r for r in c['playable']] + [
        "{{CharListFtr|%d|''Manchego Stars''}}" % len(c['playable'])]))
    if c.get('bosses') or c.get('others'):
        out.append('==Non-playable characters==')
    if c.get('bosses'):
        out.append('===Bosses===')
        out.append('\n'.join(['{{BossListHdr|class=pixel-art-3x}}'] + [
            '{{BossListCell|%s|%s|%s|%s|%s}}' % r for r in c['bosses']] + ['{{BossListFtr}}']))
    if c.get('others'):
        out.append('===Other===')
        out.append('\n'.join(['{{NPCListHdr|class=pixel-art-3x}}'] + [
            '{{NPCListCell|%s|%s|%s}}' % r for r in c['others']] + ['{{NPCListFtr}}']))
    return '\n\n'.join(out) + '\n'
