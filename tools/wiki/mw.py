"""A MediaWiki subset: expand the Fire Emblem Wiki's own templates, then render wikitext to HTML.

The wiki's pages are its templates called with data (#493): each template's parameters are the
data contract, and the template's source is the layout. So the generator writes WIKITEXT that
calls the vendored templates, and this module does what MediaWiki does with it -- the
preprocessor (templates, parameters, parser functions, the Lua modules those templates invoke,
ported) and the parser (tables, headings, links, files, lists, bold/italic) -- for exactly the
surface the vendored templates use. Anything outside it raises rather than rendering wrong.
"""
import os
import re

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vendor', 'templates')

# ── preprocessor: parse ───────────────────────────────────────────────────────────────────


class Tpl:
    """{{name|arg|...}}: `parts` are node lists, parts[0] the name."""
    __slots__ = ('parts',)

    def __init__(self, parts):
        self.parts = parts


class Param:
    """{{{name|default}}}"""
    __slots__ = ('parts',)

    def __init__(self, parts):
        self.parts = parts


def _strip_comments(text):
    return re.sub(r'<!--.*?-->', '', text, flags=re.S)


def parse(text):
    """Wikitext -> a node list (str | Tpl | Param), the way MediaWiki's preprocessor brackets
    it: the longest run of braces wins as {{{ when it can close as }}}, else {{."""
    nodes, i = _parse(_strip_comments(text), 0, None)
    return nodes


def _parse(s, i, closer):
    """Parse from i until `closer` ('}}' or '}}}') at depth 0 or end. Returns (parts-or-nodes,
    end). Inside a template/param, top-level '|' splits parts; [[...]] shields its pipes."""
    parts, cur, buf = [], [], []
    link_depth = 0

    def flush():
        if buf:
            cur.append(''.join(buf))
            buf.clear()

    n = len(s)
    while i < n:
        if closer and link_depth == 0 and s.startswith(closer, i):
            flush()
            parts.append(cur)
            return parts, i + len(closer)
        c = s[i]
        if c == '{' and s.startswith('{{', i):
            run = len(s[i:]) - len(s[i:].lstrip('{'))
            # MediaWiki: {{{{x}}}} etc. Take a param when 3+ braces open and it closes as }}}.
            if run >= 3:
                sub, j = _parse(s, i + 3, '}}}')
                if j is not None and s[j - 3:j] == '}}}':
                    flush()
                    cur.append(Param(sub))
                    i = j
                    continue
            sub, j = _parse(s, i + 2, '}}')
            if j is not None and s[j - 2:j] == '}}':
                flush()
                cur.append(Tpl(sub))
                i = j
                continue
            buf.append(c)
            i += 1
            continue
        if closer:
            if s.startswith('[[', i):
                link_depth += 1
                buf.append('[[')
                i += 2
                continue
            if s.startswith(']]', i) and link_depth:
                link_depth -= 1
                buf.append(']]')
                i += 2
                continue
            if c == '|' and link_depth == 0:
                flush()
                parts.append(cur)
                cur = []
                i += 1
                continue
        buf.append(c)
        i += 1
    flush()
    if closer:
        return None, None            # unclosed: caller treats the braces as text
    return cur, i


# ── preprocessor: expand ──────────────────────────────────────────────────────────────────


class Frame:
    def __init__(self, args, parent, title):
        self.args = args          # name -> (node list, parent frame) ; expanded lazily
        self.parent = parent
        self.title = title
        self._cache = {}

    def arg(self, name):
        if name not in self.args:
            return None
        if name not in self._cache:
            nodes, frame, named = self.args[name]
            v = frame.expand(nodes)
            self._cache[name] = v.strip() if named else v
        return self._cache[name]

    def expand(self, nodes):
        return self.wiki.expand(nodes, self)


class Wiki:
    """Templates from `template_dir` (vendored action=raw sources), modules ported below."""

    def __init__(self, template_dir=TEMPLATES, pagename='', extra_templates=None):
        self.dir = template_dir
        self.pagename = pagename
        self.extra = extra_templates or {}
        self._src = {}

    # template sources
    def _file_for(self, title):
        fn = title.replace('/', '__').replace(':', '--').replace(' ', '_') + '.wiki'
        return os.path.join(self.dir, fn)

    def template_source(self, name):
        title = normalize_title(name, 'Template')
        if title in self.extra:
            return self.extra[title]
        if title in self._src:
            return self._src[title]
        path = self._file_for(title)
        if not os.path.isfile(path):
            raise KeyError('template not vendored: %s' % title)
        text = open(path, encoding='utf-8').read()
        m = re.match(r'\s*#redirect\s*\[\[([^\]|]+)', text, re.I)
        if m:
            text = self.template_source(m.group(1).split(':', 1)[-1])
        else:
            text = transclusion_text(text)
        self._src[title] = text
        return text

    def frame(self, args=None, title=''):
        f = Frame(args or {}, None, title)
        f.wiki = self
        return f

    def expand_text(self, text, args=None):
        return self.expand(parse(text), self.frame(args))

    def expand(self, nodes, frame):
        out = []
        for node in nodes:
            if isinstance(node, str):
                out.append(node)
            elif isinstance(node, Param):
                name = frame.expand(node.parts[0]).strip()
                v = frame.arg(name)
                if v is None:
                    if len(node.parts) > 1:
                        v = frame.expand(node.parts[1])
                    else:
                        v = '{{{%s}}}' % name
                out.append(v)
            else:
                out.append(self.call(node, frame))
        return ''.join(out)

    def call(self, node, frame):
        head = frame.expand(node.parts[0])
        # parser functions / magic words with a colon: {{#if:x|..}}, {{lc:x}}
        m = re.match(r'\s*(#?[A-Za-z]+)\s*:(.*)$', head, re.S)
        if m and (m.group(1).startswith('#') or m.group(1).lower() in MAGIC_FUNCS):
            fname = m.group(1).lower()
            first = m.group(2)
            rest = node.parts[1:]
            return self.parser_function(fname, first, rest, frame)
        name = head.strip()
        if name in MAGIC_WORDS:
            return MAGIC_WORDS[name](self)
        args, pos = {}, 0
        for part in node.parts[1:]:
            eq = _top_level_eq(part)
            if eq is not None:
                key = frame.expand(part[:eq[0]] + [eq[1]]).strip()
                args[key] = ([eq[2]] + part[eq[0] + 1:], frame, True)
            else:
                pos += 1
                args[str(pos)] = (part, frame, False)
        src = self.template_source(name)
        child = Frame(args, frame, name)
        child.wiki = self
        return self.expand(parse(src), child)

    # parser functions
    def parser_function(self, fname, first, rest, frame):
        def arg(i):
            return frame.expand(rest[i]) if i < len(rest) else ''
        if fname == '#if':
            return (arg(0) if first.strip() else arg(1)).strip()
        if fname == '#ifeq':
            a, b = first.strip(), arg(0).strip()
            return (arg(1) if _eq(a, b) else arg(2)).strip()
        if fname == '#ifexpr':
            return (arg(0) if expr(first) else arg(1)).strip()
        if fname == '#switch':
            value = first.strip()
            fall, default = False, None
            for part in rest:
                eq = _top_level_eq(part)
                if eq is None:                 # a bare case falls through to the next value
                    if _eq(frame.expand(part).strip(), value):
                        fall = True
                    continue
                key = frame.expand(part[:eq[0]] + [eq[1]]).strip()
                val_nodes = [eq[2]] + part[eq[0] + 1:]
                if fall or _eq(key, value):
                    return frame.expand(val_nodes).strip()
                if key == '#default':
                    default = val_nodes
            if default is not None:
                return frame.expand(default).strip()
            if rest and _top_level_eq(rest[-1]) is None:   # a trailing bare value: default
                return frame.expand(rest[-1]).strip()
            return ''
        if fname in ('defaultsort', 'displaytitle'):      # page metadata, renders nothing
            return ''
        if fname == 'lc':
            return first.lower()
        if fname == 'uc':
            return first.upper()
        if fname == 'ucfirst':
            return first[:1].upper() + first[1:]
        if fname == 'lcfirst':
            return first[:1].lower() + first[1:]
        if fname == '#tag':
            tag = first.strip()
            content = arg(0)
            attrs = ''.join(' %s="%s"' % tuple(x.strip() for x in frame.expand(p).split('=', 1))
                            for p in rest[1:])
            return '<%s%s>%s</%s>' % (tag, attrs, content, tag)
        if fname == '#invoke':
            module = first.strip()
            fn = arg(0).strip()
            margs = {}
            pos = 0
            for part in rest[1:]:
                eq = _top_level_eq(part)
                if eq is not None:
                    k = frame.expand(part[:eq[0]] + [eq[1]]).strip()
                    margs[k] = frame.expand([eq[2]] + part[eq[0] + 1:]).strip()
                else:
                    pos += 1
                    margs[str(pos)] = frame.expand(part)
            # Module:Arguments' getArgs: the #invoke's own args, falling back to the calling
            # template's, trimmed, with blanks dropped (Template:Lang passes none of its own).
            merged = {k: v for k, v in _parent_args(frame).items() if v and v.strip()}
            merged.update({k: v for k, v in margs.items() if v and v.strip()})
            margs = merged
            impl = MODULES.get((module[:1].upper() + module[1:], fn))
            if impl is None:
                raise KeyError('module not ported: %s.%s' % (module, fn))
            out = impl(self, margs, frame)
            # Module output is wikitext and is preprocessed again (frame:preprocess semantics
            # differ, but ChapChars emits {{Color2}} that MediaWiki DOES expand because the
            # module result is inserted before the template's own expansion completes).
            return self.expand(parse(out), frame)
        raise KeyError('parser function not supported: %s' % fname)


def _top_level_eq(part):
    """(index, before, after) of the first '=' in a part's top-level TEXT nodes, or None."""
    for idx, node in enumerate(part):
        if isinstance(node, str) and '=' in node:
            k = node.index('=')
            return idx, node[:k], node[k + 1:]
        if not isinstance(node, str):
            continue
    return None


def _eq(a, b):
    try:
        return float(a) == float(b)
    except ValueError:
        return a == b


def expr(text):
    """#ifexpr's expression language, the subset in use: numbers, + - * /, comparisons,
    and/or/not, parentheses."""
    t = text.strip()
    if not t:
        return False
    tokens = re.findall(r'\d+(?:\.\d+)?|<=|>=|<>|!=|[-+*/()<>=]|and|or|not|mod', t)
    py = []
    for tok in tokens:
        py.append({'=': '==', '<>': '!=', 'mod': '%'}.get(tok, tok))
    return bool(eval(' '.join(py), {'__builtins__': {}}, {}))   # tokens are whitelisted


MAGIC_FUNCS = {'lc', 'uc', 'ucfirst', 'lcfirst', 'defaultsort', 'displaytitle'}
MAGIC_WORDS = {
    '!': lambda w: '|', '(!': lambda w: '{|', '!)': lambda w: '|}', '!-': lambda w: '|-',
    '=': lambda w: '=', 'PAGENAME': lambda w: w.pagename, 'NAMESPACE': lambda w: '',
    'FULLPAGENAME': lambda w: w.pagename, 'BASEPAGENAME': lambda w: w.pagename.split('/')[0],
    'SUBPAGENAME': lambda w: w.pagename.split('/')[-1],
}


def normalize_title(name, default_ns):
    name = name.strip().replace('_', ' ')
    if ':' in name and name.split(':', 1)[0] in ('Template', 'Module'):
        ns, rest = name.split(':', 1)
    else:
        ns, rest = default_ns, name
    rest = rest.strip()
    return '%s:%s' % (ns, rest[:1].upper() + rest[1:])


def transclusion_text(text):
    m = re.findall(r'<onlyinclude>(.*?)</onlyinclude>', text, re.S)
    if m:
        return ''.join(m)
    text = re.sub(r'<noinclude>.*?(</noinclude>|$)', '', text, flags=re.S)
    return text.replace('<includeonly>', '').replace('</includeonly>', '')


# ── ported Lua modules (Module:ChapChars, Module:Item, Module:Main, Module:String) ─────────

def _parent_args(frame):
    """The CALLING template's args -- frame:getParent().args in Lua."""
    return {k: frame.arg(k) for k in frame.args}


def _game_bits(game):
    num = int(game) if game.isdigit() else 0
    if num > 0:
        game = 'fe' + game
    size = 'Medium ' if num == 18 else ('Small ' if num > 5 or game in ('trs01', 'fewa2') else '')
    pixels = '100' if num == 17 else 'x80'
    return game, size, pixels


def chapchars_newunits(wiki, args, frame):
    pa = _parent_args(frame)
    units = {int(k[7:]): v for k, v in pa.items() if re.fullmatch(r'newunit\d+', k)}
    if not units:
        return '|\nNone'
    rowbreak = 2 if len(units) == 4 else 3
    out = ''
    for k in sorted(units):
        out += '|\n' + units[k] + '\n'
        if k % rowbreak == 0:
            out += '|-\n'
    return out


def chapchars_oldunits(wiki, args, frame):
    pa = _parent_args(frame)
    game, size, pixels = _game_bits(pa.get('game#', '') or '')
    groups = {'return': {}, 'forced': {}, 'nodepl': {}}
    for k, v in pa.items():
        m = re.match(r'(return|forced|nodepl)(\d+)(article|alt)?$', k)
        if not m:
            continue
        slot = groups[m.group(1)].setdefault(int(m.group(2)), [None, None, None])
        if m.group(3) == 'article':
            slot[1] = v
        elif m.group(3) == 'alt':
            slot[2] = v
        else:
            slot[0] = v.lower()
            slot[1] = slot[1] or v
            slot[2] = slot[2] or v[:1].upper() + v[1:]
    hdr = '[[File:%sportrait ' % size
    link = ' %s.png|link=' % game
    ftr = '|%spx]]' % pixels

    def imgs(d):
        return ''.join('%s%s%s%s|%s &#8203;%s' % (hdr, d[k][0], link, d[k][1], d[k][2], ftr)
                       for k in sorted(d))
    cellh = ('! <div class="round" style="margin: auto; border: 1px solid {{Color2}}; '
             'background: {{Color1}}; width: 66%; padding: 3px">')
    cellc = '| class="round"style="padding: 1em; border: 1px solid #b0b0b0" | '
    out = ''
    if groups['forced']:
        out = cellh + 'Forcibly deployed characters</div>\n|-\n' + cellc + imgs(groups['forced']) + '\n|-\n'
    out += (cellh + 'Available characters</div>\n|-\n' + cellc
            + (imgs(groups['return']) if groups['return'] else 'None') + '\n|-\n')
    if groups['nodepl']:
        out += cellh + 'Undeployable characters</div>\n|-\n' + cellc + imgs(groups['nodepl'])
    return out


GBA = {'fe06', 'fe07', 'fe08'}


def item_main(wiki, args, frame):
    """Module:Item.main for the GBA games (args are the {{Item}} call's)."""
    pa = _parent_args(frame)
    plat_in = pa.get('1', '').strip()
    game = 'fe%02d' % int(plat_in) if plat_in.isdigit() else plat_in
    platform = 'gba' if game in GBA else game
    name = pa.get('2', '').strip()
    target = pa.get('link') or name
    image = pa.get('image') or name
    out = ''
    if not pa.get('noimage'):
        out = '[[File:Is %s %s.png|alt=|link=%s]]&nbsp;' % (platform, image.lower(),
                                                               '' if pa.get('nolink') else target)
    if pa.get('type') == 'drop':
        out += ('<span style="color:var(--default-item-drop-color)">[[%s|%s]]</span>'
                '[[File:SNESItemDrop.png|link=Inventory#Droppable items|This item is dropped '
                "upon this unit's defeat.]]" % (target, name))
    elif pa.get('nolink'):
        out += name
    else:
        out += '[[%s|%s]]' % (target, name)
    return out


def main_main(wiki, args, frame):
    """Module:Main.main: each page as [[page|''<wbr>shown<wbr>'']], listed with and/commas."""
    pa = _parent_args(frame)
    pages = {}
    for k, v in pa.items():
        if k.isdigit():
            v = v.replace('{{!}}', '|').replace('_', ' ')
            target = v.split('|', 1)[0]
            shown = re.sub(r'(?<!&) *# *', ' \u00a7 ', v, count=1).split('|')[-1].strip('/')
            pages[int(k)] = [target, pages.get(int(k), [None, None])[1] or shown]
        elif k.startswith('l') and k[1:].isdigit():
            pages.setdefault(int(k[1:]), [None, None])[1] = v
    links = ["[[%s|''<wbr>%s<wbr>'']]" % (t, d) for _, (t, d) in sorted(pages.items())]
    if len(links) <= 2:
        return "'' and ''".join(links)
    return "'', ''".join(links[:-1]) + "'', and ''" + links[-1]


def string_replace(wiki, args, frame):
    src, pat, rep = args.get('1', ''), args.get('2', ''), args.get('3', '')
    return src.replace(pat, rep)


def language_lang(wiki, args, frame):
    """Module:Language.lang, the path {{hl}} takes for a language with no script suffix
    (ja): a hover span over the native text, titled with the romanization."""
    lang, text, rom = args.get('1', 'ja').strip(), args.get('2', ''), args.get('3', '')
    if args.get('hl'):
        return '<span class="explain tooltips" title="%s" lang="%s">%s</span>' % (rom, lang, text)
    return '<span lang="%s">%s</span>' % (lang, text)


def displaytitle_italic(wiki, args, frame):
    """Module:DisplayTitle.italic: the page name in italics, or just the named parts."""
    name = wiki.pagename
    parts = [args[str(i)] for i in range(1, 20) if args.get(str(i))]
    if not parts:
        return "''%s''" % name
    for part in parts:
        name = name.replace(part, '<i>%s</i>' % part, 1)
    return name


AFFINITY_GBA = {   # Module:Affinity's GBA table: bonus per support level unit, by affinity
    'fire': (1, 0, 5, 5, 5, 0), 'thunder': (0, 1, 0, 5, 5, 5), 'wind': (1, 0, 5, 0, 5, 5),
    'ice': (0, 1, 5, 5, 0, 5), 'dark': (0, 0, 5, 5, 5, 5), 'light': (1, 1, 5, 0, 5, 0),
    'anima': (1, 1, 0, 5, 0, 5)}


def affinity_main(wiki, args, frame):
    """Module:Affinity.main, GBA variant: one support-level row of combined bonuses."""
    variant = args.get('1', '').strip().upper()
    if variant != 'GBA':
        raise KeyError('Module:Affinity variant not ported: %s' % variant)
    a, b = args['2'].strip().lower(), args['3'].strip().lower()
    level = args['4'].strip().upper()
    mult = {'C': 0.5, 'B': 1, 'A': 1.5}[level]
    last_row = not args.get('ending') and level == 'A'
    out = '! class="roundbl" | ' + level if last_row else '! ' + level
    vals = [int((x + y) * mult) for x, y in zip(AFFINITY_GBA[a], AFFINITY_GBA[b])]
    for i, v in enumerate(vals):
        if i == len(vals) - 1 and last_row:
            out += '\n| class="roundbr" | %d' % v
        else:
            out += '\n| %d' % v
    return out


def string_rep(wiki, args, frame):
    return args.get('1', '') * int(args.get('2', '1').strip() or 1)


MODULES = {('Language', 'lang'): language_lang,
           ('DisplayTitle', 'italic'): displaytitle_italic,
           ('Affinity', 'main'): affinity_main,
           ('String', 'rep'): string_rep,
           ('ChapChars', 'newunits'): chapchars_newunits,
           ('ChapChars', 'oldunits'): chapchars_oldunits,
           ('Item', 'main'): item_main,
           ('Main', 'main'): main_main,
           ('String', 'replace'): string_replace}
