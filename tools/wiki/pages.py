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
