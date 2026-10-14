"""The Fire Emblem Wiki's chapter-page markup, cut from the rendered page and kept verbatim.

Every fragment here was copied out of fireemblemwiki.org/wiki/Distant_Blade as MediaWiki
renders it (2026-10-14); only the data is a parameter. Keep it that way: a change of LOOK is
a change here, copied from a fresh render, never re-invented (Nicolas, #487).
"""
import html

WIKI = 'https://fireemblemwiki.org/wiki/'
CELL = 'border-radius: 5px'


def esc(s):
    return html.escape(str(s if s is not None else ''), quote=True)


def fe(page, text=None):
    """A link to the Fire Emblem Wiki's own article on an FE term (class, item, stat)."""
    if not page:
        return esc(text or '')
    return ('<a href="%s%s" title="%s" target="_blank" rel="noopener">%s</a>'
            % (WIKI, esc(str(page).replace(' ', '_')), esc(page), esc(text or page)))


def fe_html(page, inner):
    """A wiki link around markup (an icon), as the wiki wraps its rank and affinity icons."""
    return ('<a href="%s%s" title="%s" target="_blank" rel="noopener">%s</a>'
            % (WIKI, esc(str(page).replace(' ', '_')), esc(page), inner))


def ours(anchor, text):
    return '<a href="#%s" title="%s">%s</a>' % (esc(anchor), esc(text), esc(text))


def file_img(src, w, h, alt=''):
    if not src:
        return ''
    return ('<span class="mw-default-size" typeof="mw:File"><img alt="%s" src="%s" width="%d" '
            'height="%d" class="mw-file-element" /></span>' % (esc(alt), src, w, h))


def h(level, text, anchor):
    return '<h%d><span class="mw-headline" id="%s">%s</span></h%d>' % (level, esc(anchor),
                                                                       esc(text), level)


def main_article(anchor, title):
    return ('<dl><dd><i>Main article: </i><a href="#%s" title="%s"><i><wbr />%s<wbr /></i></a>'
            '</dd></dl>' % (esc(anchor), esc(title), esc(title)))


def note(text):
    return '<dl><dd><i>%s</i></dd></dl>' % text


STAT_RANGE_NOTE = ('Stats with two figures separated by a ~ are presented as a range, '
                   'representing stats that vary due to random growths. The figures to the left '
                   'and right of the ~ are the stat\'s minimum and maximum possible values '
                   'respectively.')


# ── infobox, lead, contents ─────────────────────────────────────────────────────

def infobox(title, image, rows):
    body = ''.join('<tr><th>%s\n</th><td><p>%s\n</p></td></tr>' % (esc(k), v) for k, v in rows if v)
    return ('<table class="infobox"><tbody><tr><td><table style="width:100%%"><tbody><tr><th>%s\n'
            '</th></tr><tr><th><p>%s<br /><span style="font-size: 77%%"></span></p></th></tr>'
            '</tbody></table></td></tr><tr><td><table style="width:100%%"><tbody>%s</tbody>'
            '</table></td></tr></tbody></table>' % (esc(title), image, body))


def toc(entries, prefix):
    """entries: [(level, text, anchor)] -> the wiki's numbered Contents box."""
    out, counters, depth = [], [0, 0, 0], 0
    for n, (level, text, anchor) in enumerate(entries, 1):
        while depth < level:
            out.append('<ul>')
            depth += 1
        while depth > level:
            out.append('</li></ul>')
            depth -= 1
        if out and not out[-1].endswith('<ul>'):
            out.append('</li>')
        counters[level - 1] += 1
        for i in range(level, 3):
            counters[i] = 0
        num = '.'.join(str(c) for c in counters[:level])
        out.append('<li class="toclevel-%d tocsection-%d"><a href="#%s"><span class="tocnumber">'
                   '%s</span> <span class="toctext">%s</span></a>' % (level, n, esc(anchor), num,
                                                                     esc(text)))
    while depth > 0:
        out.append('</li></ul>')
        depth -= 1
    return ('<div id="toc-%s" class="toc" role="navigation"><input type="checkbox" role="button" '
            'id="toctogglecheckbox-%s" class="toctogglecheckbox" style="display:none" />'
            '<div class="toctitle" lang="en" dir="ltr"><h2>Contents</h2><span class="toctogglespan">'
            '<label class="toctogglelabel" for="toctogglecheckbox-%s"></label></span></div>%s</div>'
            % (prefix, prefix, prefix, ''.join(out)))


# ── tabs (the wiki's tab_main; site JS switches them, ours does too) ───────────

def tabs(labels, contents, selected=0, width='100%', boxed=False):
    if len(contents) == 1:
        return contents[0]
    spans = ' '.join('<span class="tab&#95;tab%s">%s</span>' % (' tabselected' if i == selected
                                                                else '', lab)
                     for i, lab in enumerate(labels))
    bodies = ''.join('<div class="tab&#95;content" style="%s">%s</div>'
                     % ('' if i == selected else 'display: none', c) for i, c in enumerate(contents))
    return ('<div class="tab&#95;main" style="margin: auto; width: %s; margin-top: 1em;">'
            '<div class="tabcontainer" style="padding-bottom: 2px; margin: 4px 4px 0; text-align: '
            'center;"><p>%s</p></div><div class="tabcontents" style="height: auto; margin: auto;">'
            '%s</div></div>' % (width, spans, bodies))


def boxed_tabs(title, labels, contents):
    """Shop data's framed variant of tab_main."""
    spans = ' '.join('<span class="tab&#95;tab%s">%s</span>' % (' tabselected' if i == 0 else '', l)
                     for i, l in enumerate(labels))
    bodies = ''.join('<div class="tab&#95;content" style="%s">%s</div>'
                     % ('' if i == 0 else 'display: none', c) for i, c in enumerate(contents))
    return ('<div class="round tab&#95;main" style="margin: auto; width: 70%%; border: 2px solid '
            'var(--color2); background: var(--color3);"><div class="round" style="border: 2px solid '
            'var(--color2); background: var(--color1); text-align: center; padding: 3px; font-size: '
            'larger; margin: 3px 3px 1em"><b>%s</b></div><div class="tabcontainer" style="padding-'
            'bottom: 2px; margin: 4px 4px 0; text-align: center;"><p>%s</p></div><div class="'
            'tabcontents" style="height: auto; margin: auto; padding: 4px; border-top: 2px solid '
            'var(--color2); text-align: center">%s</div></div>' % (esc(title), spans, bodies))


# ── Chapter data ────────────────────────────────────────────────────────────────

_HEAD = ('<table class="round" style="border: 1px solid var(--color2); background: var(--color1); '
         'width: 100%%; margin: auto; font-size: larger"><tbody><tr><th>%s\n</th></tr></tbody>'
         '</table>')


def chapter_data(victory, defeat, player, enemy, map_img, map_w, map_h):
    head = _HEAD
    return (
        '<table class="round width-40" style="margin: auto; border: 1px solid var(--color2); '
        'background: var(--color3); text-align: center"><tbody>'
        '<tr><td colspan="5">%s</td></tr>'
        '<tr><td style="width:47%%">%s</td><td colspan="4" style="width:53%%">%s</td></tr>'
        '<tr><td><b>Victory:</b> %s\n</td>'
        '<th class="roundtl" style="border: 1px solid var(--color2); background: #3850e0">Player\n</th>'
        '<th style="border: 1px solid var(--color2); background: #f8f840; color: #444; display: none">Partner\n</th>'
        '<th style="border: 1px solid var(--color2); background: #089000; display: none">Other\n</th>'
        '<th class="roundtr" style="border: 1px solid var(--color2); background: #a83028">Enemy\n</th>'
        '<th class="roundtr" style="border: 1px solid var(--color2); background: #f8f840; color: #444; display:none">Third\n</th></tr>'
        '<tr><td><b>Defeat:</b> %s\n</td>'
        '<td class="roundbl" style="border: 1px solid var(--color2); background: #3850e0">%s\n</td>'
        '<td style="border: 1px solid var(--color2); background: #f8f840; color: black; display: none"></td>'
        '<td style="border: 1px solid var(--color2); background: #089000; display: none"></td>'
        '<td class="roundbr" style="border: 1px solid var(--color2); background: #a83028">%s\n</td>'
        '<td class="roundbr" style="border: 1px solid var(--color2); background: #f8f840; color: black; display: none"></td></tr>'
        '<tr><td colspan="5"><table style="margin: auto; border: 1px solid var(--color2)"><tbody><tr>'
        '<td class="table-image-responsive-shrink">%s</td></tr></tbody></table></td></tr>'
        '<tr><td colspan="5"><b>Map dimensions:</b><br />%s columns by %s rows\n</td></tr>'
        '<tr><td colspan="5"></td></tr></tbody></table>'
        % (head % 'Chapter Data', head % 'Conditions', head % 'Unit Data', victory, defeat,
           player, enemy, map_img, map_w, map_h))


def tooltip(text, title):
    return ('<span class="explain tooltips" title="%s" style="color:inherit">%s</span>'
            % (esc(title), esc(text)))


# ── Character data ──────────────────────────────────────────────────────────────

def unit_card(name, face, class_html, hp, level, inventory, how):
    return ('<td><table style="border-radius: 14px; border: 2px solid var(--color2); background: '
            'var(--color3); padding: 4px; text-align: center; margin: auto; max-width: 350px"><tbody>'
            '<tr><th style="border-radius: 14px; border: 1px solid var(--color2); padding: 2px; '
            'font-size: larger">%s\n</th></tr><tr><td style="padding: 2px; width: 300px; height: '
            '50px">%s</td></tr><tr><td><table class="chapter-table" style="width: 100%%; padding: '
            '2px; border: none; background: none; border-radius: 0"><tbody>'
            '<tr><td style="%s" colspan="2"><b>%s</b>\n</td></tr>'
            '<tr><td style="width: 35%%; %s"><b>HP</b><br />%s\n</td><td style="%s" rowspan="2">'
            '<b>Inventory</b><br />%s\n</td></tr>'
            '<tr><td style="%s"><b>Level</b><br />%s\n</td></tr>'
            '<tr><td style="%s" colspan="2"><b>%s</b>\n</td></tr>'
            '</tbody></table></td></tr></tbody></table></td>'
            % (name, face, CELL, class_html, CELL, esc(hp), CELL, inventory, CELL, esc(level),
               CELL, how))


def _chars_subhead(text):
    return ('<tr><th><div class="round" style="margin: auto; border: 1px solid var(--color2); '
            'background: var(--color1); width: 66%%; padding: 3px">%s</div>\n</th></tr>' % esc(text))


def characters(new_cards, groups):
    """new_cards: unit_card cells; groups: [(heading, [minimug html])]."""
    rows = ['<tr><th class="round" style="border: 1px solid var(--color2); background: '
            'var(--color1); width: 100%; font-size: larger">Characters\n</th></tr>']
    if new_cards:
        grid = ''.join('<tr>%s</tr>' % ''.join(new_cards[i:i + 3])
                       for i in range(0, len(new_cards), 3))
        rows.append(_chars_subhead('New units'))
        rows.append('<tr><td><table style="margin: auto; width: 100%%"><tbody>%s</tbody></table>'
                    '</td></tr>' % grid)
    for heading, mugs in groups:
        if mugs:
            rows.append(_chars_subhead(heading))
            rows.append('<tr><td class="round" style="padding: 1em; border: 1px solid #b0b0b0">%s\n'
                        '</td></tr>' % '\n'.join(mugs))
    return ('<table class="chap-chars round pixel-art width-80" style="margin: auto; border: 2px '
            'solid var(--color2); background: var(--color3); text-align: center"><tbody>%s</tbody>'
            '</table>' % ''.join(rows))


# ── Item data ───────────────────────────────────────────────────────────────────

def items_table(rows):
    """rows: [(icon html, name html, obtain html)]."""
    body = []
    last = len(rows) - 1
    for i, (icon, name, how) in enumerate(rows):
        l = ' style="border-bottom-left-radius: 9px"' if i == last else ''
        r = ' style="border-bottom-right-radius: 9px"' if i == last else ''
        body.append('<tr><td%s>%s</td><td><b>%s</b>\n</td><td%s>%s\n</td></tr>' % (l, icon, name, r,
                                                                                   how))
    return ('<table class="chapter-table width-60"><tbody><tr><td style="border: none; background: '
            'none"><table class="chapter-table" style="border-radius: 11px; background: '
            'var(--color1); width: 100%%"><tbody><tr><th style="border: none; background: none">'
            'Items\n</th></tr></tbody></table></td></tr><tr><td style="border: none; background: '
            'none"><table style="width: 100%%" class="pixel-art"><tbody><tr><th style="border-top-'
            'left-radius: 9px; width: 5%%">\n</th><th style="width: 30%%">Name\n</th><th style="'
            'border-top-right-radius: 9px; width: 65%%">Obtainment Method\n</th></tr>%s</tbody>'
            '</table></td></tr></tbody></table>' % ''.join(body))


def shop_table(rows):
    """rows: [(icon html, name html, cost)]."""
    body = ''.join('<tr><td class="roundl" style="text-align: right">%s</td><td>%s\n</td>'
                   '<td class="roundr">%s\n</td></tr>' % (i, n, esc(c)) for i, n, c in rows)
    return ('<table class="wikitable" style="border-collapse: separate; margin: auto; border: none; '
            'background: none"><tbody><tr><th class="roundl" style="width: 5%%">\n</th><th style="'
            'width: 30%%">Name\n</th><th class="roundr" style="width: 15%%">Cost\n</th></tr>%s'
            '</tbody></table>' % body)


# ── Enemy data ──────────────────────────────────────────────────────────────────

_ENEMY_HEAD = (
    '<tr><th class="roundtl" style="width: 3%; min-width: 16px">\n</th>'
    '<th style="width: 8%">Name\n</th>'
    '<th style="width: 8%">' + fe('Class') + '\n</th>'
    '<th style="width: 2.5%">' + fe('Level', 'Lv') + '\n</th>'
    '<th style="width: 2.5%">#\n</th>'
    '<th style="width: 4%">' + fe('HP') + '\n</th>'
    '<th style="width: 4%">' + fe('Str', 'S') + '/' + fe('Mag', 'M') + '\n</th>'
    '<th style="width: 4%;">' + fe('Skill (stat)', 'Skill') + '\n</th>'
    '<th style="width: 4%">' + fe('Spd') + '\n</th>'
    '<th style="width: 4%;">' + fe('Lck') + '\n</th>'
    '<th style="width: 4%">' + fe('Def') + '\n</th>'
    '<th style="width: 4%;">' + fe('Res') + '\n</th>'
    '<th style="width: 4%;">' + fe('Con') + '\n</th>'
    '<th style="width: 3%">' + fe('Movement', 'Mov') + '\n</th>'
    '<th class="roundtr" style="width: 40%">Inventory\n</th></tr>')


def enemy_rows(units):
    """units: [dict(sprite, name, cls, lv, n, stats[9 strs], inventory, ai)]."""
    out = []
    for u in units:
        cells = ''.join('<td>%s\n</td>' % esc(v) for v in [u['lv'], u['n']] + u['stats'])
        out.append('<tr><td class="pixel-art" rowspan="2">%s</td><td rowspan="2">%s\n</td>'
                   '<td rowspan="2">%s\n</td>%s<td class="pixel-art">%s\n</td></tr>'
                   '<tr><td colspan="12">%s\n</td></tr>'
                   % (u['sprite'], u['name'], u['cls'], cells, u['inventory'], u['ai']))
    return ''.join(out)


def enemy_block(title, rows_html):
    return ('<tr><td style="border: none; background: none"><table class="chapter-table" style="'
            'background: #a83028; color: #fff; width: 99%%"><tbody><tr><th style="border: none; '
            'background: none">%s\n</th></tr></tbody></table></td></tr><tr><td style="border: none; '
            'background: none"><table style="width: 100%%"><tbody>%s%s</tbody></table></td></tr>'
            % (esc(title), _ENEMY_HEAD, rows_html))


def enemy_tables(blocks):
    return '<table class="chapter-table width-95"><tbody>%s</tbody></table>' % ''.join(blocks)


NO_AI = '<span style="white-space: nowrap">--</span>'


# ── Boss data ───────────────────────────────────────────────────────────────────

def _pair(label_a, val_a, label_b, val_b):
    def one(label, val):
        if label is None:
            return ''
        return ('<th style="border-radius: 5px 0 0 5px">%s\n</th><td style="border-radius: 0 5px '
                '5px 0">%s\n</td>' % (label, esc(val)))
    return '<tr>%s%s</tr>' % (one(label_a, val_a), one(label_b, val_b))


def boss_card(face, sprite, class_html, level, affinity, stats, inventory, ranks):
    """stats: dict of the wiki's labels; ranks: [(icon html, letter)] x8 (swords..staves)."""
    grid = ''.join(_pair(fe(a), stats[a], fe(b), stats[b]) for a, b in
                   (('Max HP', 'Luck'), ('Strength', 'Defense'), ('Skill (stat)', 'Resistance'),
                    ('Speed', 'Constitution'), ('Movement', 'Aid')))
    grid = grid.replace('>Skill (stat)<', '>Skill<')
    rank_rows = ''
    for half in (ranks[:4], ranks[4:]):
        rank_rows += '<tr>%s</tr>' % ''.join(
            '<td style="border-radius: 5px 0 0 5px; min-width: 15px">%s</td><td style="'
            'border-radius: 0 5px 5px 0">%s\n</td>' % (icon, letter or NO_AI) for icon, letter in half)
    return (
        '<div class="stat-table-flex pixel-art"><div class="stat-table-flex-item"><table><tbody>'
        '<tr><td colspan="2" style="background: none; border: none">%s</td></tr>'
        '<tr><th colspan="2" style="border-width: 2px; border-radius: 5px">%s <i>%s</i>\n</th></tr>'
        '<tr><th style="border-width: 2px; border-radius: 5px 0 0 5px">%s\n</th><td style="'
        'border-radius: 0 5px 5px 0">%s\n</td></tr>'
        '<tr><th style="border-width: 2px; border-radius: 5px 0 0 5px">%s\n</th><td style="'
        'border-radius: 0 5px 5px 0; min-width: 13px">%s</td></tr></tbody></table></div>'
        '<div class="stat-grid"><div class="stat-table-inner-flex"><div class="stat-table-flex-item">'
        '<table style="border-spacing: 3px"><tbody><tr><th colspan="4" style="border-width: 2px; '
        'border-radius: 5px">Stats\n</th></tr>%s</tbody></table></div><div class="stat-table-flex-'
        'item"><table style="border-spacing: 3px"><tbody><tr><th style="border-width: 2px; border-'
        'radius: 5px">Inventory\n</th></tr><tr><td style="text-align: left; background: none; '
        'border: none">%s\n</td></tr><tr><td style="background: none; border: none"><table style="'
        'width: 100%%"><caption>Weapon Levels\n</caption><tbody>%s</tbody></table></td></tr>'
        '</tbody></table></div></div></div></div>'
        % (face, sprite, class_html, fe('Level'), esc(level), fe('Affinity'), affinity or NO_AI,
           grid, inventory, rank_rows))


# ── Strategy, Trivia ────────────────────────────────────────────────────────────

STRATEGY_DISCLAIMER = (
    '<div style="border-top:solid 2px #ddd; border-bottom:solid 2px #ddd"><table><tbody><tr><td>'
    '<b>This section details unofficial strategies that may help with completion of the chapter. '
    'This may not work for everybody.</b>\n</td></tr></tbody></table></div>')


def collapsible(title, body):
    """The wiki's mw-collapsible box (jquery.makeCollapsible), collapsed by default."""
    return ('<table class="wikitable mw-collapsible mw-collapsed" style="width: 100%%"><tbody><tr>'
            '<th>%s\n</th></tr><tr><td>%s\n</td></tr></tbody></table>' % (esc(title), body))
