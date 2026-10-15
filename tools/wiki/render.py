"""Expanded wikitext -> HTML, the MediaWiki parser's way for the markup the templates emit:
tables ({| |- | || ! !! |+ |}), headings, lists, paragraphs, bold/italic, internal links, files.

Links and files go through callbacks, because what a link points at and what a file IS are the
generator's answers (our pages, our art), not the wiki's.
"""
import html
import re


class Links:
    """Default resolvers: a link is a wiki page, a file is unknown."""

    def page(self, target, text):
        return '<a href="https://fireemblemwiki.org/wiki/%s" title="%s">%s</a>' % (
            html.escape(target.replace(' ', '_'), quote=True), html.escape(target, quote=True),
            text)

    def file(self, name, opts):
        img = '<img alt="%s" data-file="%s">' % (html.escape(opts.get('alt', ''), quote=True),
                                                  html.escape(name, quote=True))
        if opts.get('link', None) == '':
            return img
        return '<a href="#">%s</a>' % img


# ── inline ────────────────────────────────────────────────────────────────────────────────

FILE_NS = ('File:', 'Image:')


def _split_link(inner):
    """[[a|b|c]] -> ['a', 'b', 'c'], ignoring pipes inside nested [[ ]]."""
    parts, depth, cur, i = [], 0, [], 0
    while i < len(inner):
        if inner.startswith('[[', i):
            depth += 1
            cur.append('[[')
            i += 2
        elif inner.startswith(']]', i) and depth:
            depth -= 1
            cur.append(']]')
            i += 2
        elif inner[i] == '|' and depth == 0:
            parts.append(''.join(cur))
            cur = []
            i += 1
        else:
            cur.append(inner[i])
            i += 1
    parts.append(''.join(cur))
    return parts


def links(text, res):
    out, i = [], 0
    while True:
        j = text.find('[[', i)
        if j < 0:
            out.append(text[i:])
            break
        # find the matching ]]
        depth, k = 0, j
        while k < len(text):
            if text.startswith('[[', k):
                depth += 1
                k += 2
            elif text.startswith(']]', k):
                depth -= 1
                k += 2
                if depth == 0:
                    break
            else:
                k += 1
        if depth:
            out.append(text[i:])
            break
        out.append(text[i:j])
        parts = _split_link(text[j + 2:k - 2])
        target = parts[0].strip()
        if not target or re.search(r'[{}<>\[\]|]', target):   # not a valid title: literal
            out.append(text[j:k])
            i = k
            continue
        if target.startswith(FILE_NS):
            opts, caption = {}, None
            for p in parts[1:]:
                p = p.strip()
                m = re.match(r'(link|alt|class)=(.*)$', p, re.S)
                if m:
                    opts[m.group(1)] = m.group(2)
                elif re.fullmatch(r'\d*x?\d+px', p) or p in ('left', 'right', 'center', 'thumb',
                                                               'thumbnail', 'frame',
                                                               'frameless', 'none'):
                    opts.setdefault('size', p)
                else:
                    caption = p
            thumb = any(p.strip() in ('thumb', 'thumbnail', 'frame') for p in parts[1:])
            if caption and 'alt' not in opts:
                opts['alt'] = caption
            name = target.split(':', 1)[1].strip()
            if thumb:          # a thumbnail shows its caption under the image
                out.append('<figure typeof="mw:File/Thumb">%s<figcaption>%s</figcaption>'
                           '</figure>' % (res.file(name, opts), inline(caption or '', res)))
            else:
                out.append(res.file(name, opts))
        elif target.startswith('Category:'):
            pass
        elif target.startswith(':'):
            out.append(res.page(target[1:], inline(parts[-1] if len(parts) > 1 else target[1:], res)))
        else:
            text_ = parts[1] if len(parts) > 1 else target
            trail = re.match(r'[a-z]+', text[k:])          # MediaWiki's link trail
            if trail:
                text_ += trail.group(0)
                k += trail.end()
            out.append(res.page(target, inline(text_, res)))
        i = k
    return ''.join(out)


def quotes(line):
    """MediaWiki's doQuotes, simplified to balanced ''' and '' runs on one line."""
    tokens = re.split(r"('{2,5})", line)
    out, bold, ital = [], False, False
    for t in tokens:
        if re.fullmatch(r"'{2,5}", t):
            n = len(t)
            if n == 4:
                out.append("'")
                n = 3
            if n == 2:
                out.append('</i>' if ital else '<i>')
                ital = not ital
            elif n == 3:
                out.append('</b>' if bold else '<b>')
                bold = not bold
            else:
                if ital and bold:
                    out.append('</b></i>')
                elif ital:
                    out.append('</i><b>')
                elif bold:
                    out.append('</b><i>')
                else:
                    out.append('<i><b>')
                bold, ital = not bold, not ital
        else:
            out.append(t)
    if bold:
        out.append('</b>')
    if ital:
        out.append('</i>')
    return ''.join(out)


_AUTONUMBER = [0]


def external(text):
    """[url text] -> a link; a bare [url] -> an auto-numbered [n], counted across the page."""
    def link(m):
        url, label = m.group(1), m.group(2)
        if label is None or not label.strip():
            _AUTONUMBER[0] += 1
            return ('<a rel="nofollow" class="external autonumber" href="%s">[%d]</a>'
                    % (html.escape(url, quote=True), _AUTONUMBER[0]))
        return ('<a rel="nofollow" class="external text" href="%s">%s</a>'
                % (html.escape(url, quote=True), label))
    return re.sub(r'\[((?:https?:)?//[^\s\]]+)(?:\s+([^\]]*))?\]', link, text)


def inline(text, res):
    return quotes(external(links(text, res)))


# ── block ─────────────────────────────────────────────────────────────────────────────────

def _cell_split(content, sep):
    """Split a cell line on `sep` ('||' or '!!') outside [[ ]]."""
    parts, depth, cur, i = [], 0, [], 0
    while i < len(content):
        if content.startswith('[[', i):
            depth += 1
        elif content.startswith(']]', i) and depth:
            depth -= 1
        if depth == 0 and content.startswith(sep, i):
            parts.append(''.join(cur))
            cur = []
            i += len(sep)
            continue
        cur.append(content[i])
        i += 1
    parts.append(''.join(cur))
    return parts


def _attrs_and_body(cell):
    """'style="x" | body' -> (' style="x"', 'body'): the first lone '|' outside [[ ]] and
    tags splits attributes from content."""
    depth, i = 0, 0
    while i < len(cell):
        if cell.startswith('[[', i):
            depth += 1
            i += 2
            continue
        if cell.startswith(']]', i) and depth:
            depth -= 1
            i += 2
            continue
        if cell[i] == '|' and depth == 0 and not cell.startswith('||', i):
            attrs = cell[:i]
            if '<' in attrs or '[' in attrs:
                break
            return ' ' + attrs.strip() if attrs.strip() else '', cell[i + 1:]
        i += 1
    return '', cell


def _css_unescape(m):
    # Sanitizer::checkCss decodes CSS escapes: the templates write `\#a83028` in #switch values.
    return 'style="%s"' % re.sub(r'\\(?![0-9a-fA-F])(.)', r'\1', m.group(1))


def render(text, res=None):
    res = res or Links()
    _AUTONUMBER[0] = 0
    # A tag's attributes may span lines (Tab/Content's style); the sanitizer joins them.
    text = re.sub(r'<[a-zA-Z][^<>]*>', lambda m: re.sub(r'\s*\n\s*', ' ', m.group(0)), text)
    text = re.sub(r'__[A-Z]+__', '', text)                 # behaviour switches
    text = re.sub(r'<br\s*/>', '<br>', text)              # the sanitizer's spelling
    text = _refs(text, res)
    text = re.sub(r'<gallery>(.*?)</gallery>', lambda m: _gallery(m.group(1), res), text,
                  flags=re.S)
    lines = text.split('\n')
    out = []
    _blocks(lines, 0, len(lines), out, res)
    return _drop_stray_end_tags(re.sub(r'style="([^"]*)"', _css_unescape, '\n'.join(out)))


VOID = {'br', 'img', 'hr', 'wbr', 'meta', 'input', 'col', 'area', 'source'}


def _drop_stray_end_tags(text):
    """MediaWiki's balancer (Remex) drops an end tag that closes nothing open: {{EU}} emits a
    `</span>` with no `<span>`, and kept, it would close the infobox's table around it."""
    out, stack, pos = [], [], 0
    for m in re.finditer(r'<(/?)([a-zA-Z][a-zA-Z0-9]*)\b[^>]*?(/?)>', text):
        closing, tag, selfclose = m.group(1), m.group(2).lower(), m.group(3)
        out.append(text[pos:m.start()])
        pos = m.end()
        if tag in VOID or selfclose:
            out.append(m.group(0))
        elif not closing:
            stack.append(tag)
            out.append(m.group(0))
        elif tag in stack:
            while stack and stack[-1] != tag:      # implicitly close what it encloses
                stack.pop()
            stack.pop()
            out.append(m.group(0))
        # else: a stray end tag -- dropped
    out.append(text[pos:])
    return ''.join(out)


def _refs(text, res):
    """Cite, by position: each <ref> becomes a numbered marker, and each <references/> prints
    the refs gathered since the last one, then empties the list -- so a second <references/>
    with nothing new prints nothing (Imperial Three calls {{refbar}} twice). Numbers run on."""
    parts = re.split(r'(<references\s*/>)', text)
    out, notes, count = [], [], [0]

    named = {}

    def ref_name(attrs):
        m = re.search(r"""name\s*=\s*(?:"([^"]*)"|''([^']*)''|'([^']*)'|([^\s/>]+))""", attrs or '')
        return next((g for g in m.groups() if g is not None), None) if m else None

    def marker(n):
        return ('<sup id="cite_ref-%d" class="reference"><a href="#cite_note-%d">'
                '<span class="cite-bracket">[</span>%d<span class="cite-bracket">]</span>'
                '</a></sup>' % (n, n, n))

    uses = {}

    def cite(m):
        attrs, body = (m.group(1), None) if m.group(1) is not None else (m.group(2), m.group(3))
        name = ref_name(attrs)
        if name in named:                  # a named ref used again: its number, no new note
            uses[named[name]] += 1
            return marker(named[name])
        count[0] += 1
        n = count[0]
        uses[n] = 1
        if name:
            named[name] = n
        notes.append((n, body or ''))
        return marker(n)

    def backlink(n):
        if uses[n] == 1:
            return '<a href="#cite_ref-%d">\u2191</a>' % n
        return '\u2191 ' + ' '.join('<sup><a href="#cite_ref-%d_%d">%d.%d</a></sup>'
                                     % (n, k, n, k) for k in range(uses[n]))

    for part in parts:
        if re.fullmatch(r'<references\s*/>', part):
            if notes:
                items = ''.join('<li id="cite_note-%d"><span class="mw-cite-backlink">%s'
                                '</span> <span class="reference-text">%s</span></li>'
                                % (n, backlink(n), _ref_body(body, res))
                                for n, body in notes)
                out.append('<div class="mw-references-wrap"><ol class="references">%s</ol>'
                           '</div>' % items)
                notes.clear()
        else:
            out.append(re.sub(r'<ref(\s[^>]*?)/>|<ref(\s[^>]*)?>(.*?)</ref>', cite, part,
                              flags=re.S))
    return ''.join(out)


def _ref_body(body, res):
    """A ref's content is full wikitext: its first line runs on from the marker, and a later
    line can open a list (the manual citations' `;` lines become a definition list)."""
    lines = body.strip().split('\n')
    lines[0] = INLINE + lines[0]
    out = []
    _blocks(lines, 0, len(lines), out, res, in_cell=True)
    return '\n'.join(out)


def _gallery(body, res):
    """<gallery> (traditional mode): one box per `File|caption` line."""
    boxes = []
    for line in body.strip().split('\n'):
        if not line.strip():
            continue
        name, _, caption = line.strip().partition('|')
        name = name.split(':', 1)[1] if name.startswith(FILE_NS) else name
        shown = inline(caption, res)
        plain = html.unescape(re.sub(r'<[^>]+>', '', shown))
        img = res.file(name.strip(), {'alt': plain, 'size': '120px'})
        boxes.append('<li class="gallerybox" style="width: 155px"><div class="thumb" style='
                     '"width: 150px; height: 150px;">%s</div><div class="gallerytext">%s</div>'
                     '</li>' % (img, shown))
    return '<ul class="gallery mw-gallery-traditional">%s</ul>' % ''.join(boxes)


INLINE = '\x00'      # marks a cell's first line: it follows `|` on the same source line


TABLE_LINE = re.compile(r'^\s*(\{\||\|\}|\|-|\|\+|\||!)')


def _blocks(lines, i, end, out, res, in_cell=False):
    para = []
    list_stack = []

    def flush_para():
        if para:
            body = '\n'.join(inline(p, res) for p in para)
            if body.strip():
                if in_cell and not out_has_block[0]:
                    out.append(body)
                else:
                    out.append('<p>' + body + '\n</p>')
            para.clear()

    def close_lists(depth=0):
        while len(list_stack) > depth:
            tag, item = list_stack.pop()
            if item:
                out.append('</%s>' % item)
            out.append('</%s>' % tag)

    out_has_block = [False]
    while i < end:
        line = lines[i]
        if line.startswith(INLINE):
            line = line[1:]
            if line.strip():
                para.append(line)
            i += 1
            continue
        s = line.strip()
        if s.startswith('{|'):
            flush_para()
            close_lists()
            i = _table(lines, i, out, res)
            out_has_block[0] = True
            continue
        m = re.match(r'^(={1,6})\s*(.*?)\s*\1\s*$', line)
        if m:
            flush_para()
            close_lists()
            level = len(m.group(1))
            title = inline(m.group(2), res)
            anchor = re.sub(r'\s+', '_', re.sub(r'<[^>]+>', '', title))
            out.append('<h%d><span class="mw-headline" id="%s">%s</span></h%d>'
                       % (level, html.escape(anchor, quote=True), title, level))
            out_has_block[0] = True
            i += 1
            continue
        lm = re.match(r'^([*#:;]+)\s*(.*)$', line)
        if lm:
            flush_para()
            marks = lm.group(1)
            want = [{'*': 'ul', '#': 'ol', ':': 'dl', ';': 'dl'}[c] for c in marks]
            kinds = ['dd' if c == ':' else ('dt' if c == ';' else 'li') for c in marks]
            k = 0
            while k < len(list_stack) and k < len(want) and list_stack[k][0] == want[k]:
                k += 1
            close_lists(k)                    # leave the levels this line does not share
            if k == len(want):                # same list, next item: close the open one
                tag, open_item = list_stack[-1]
                if open_item:
                    out.append('</%s>' % open_item)
                list_stack[-1] = (tag, None)
            for d in range(len(list_stack), len(want)):
                out.append('<%s>' % want[d])
                list_stack.append((want[d], None))
                if d < len(want) - 1:         # an intermediate level gets an item to nest in
                    out.append('<%s>' % kinds[d])
                    list_stack[-1] = (want[d], kinds[d])
            item = kinds[-1]
            out.append('<%s>%s' % (item, inline(lm.group(2), res)))
            list_stack[-1] = (list_stack[-1][0], item)
            out_has_block[0] = True
            i += 1
            continue
        close_lists()
        if s == '' :
            flush_para()
            i += 1
            continue
        if s.startswith('----'):
            flush_para()
            out.append('<hr>')
            i += 1
            continue
        if re.match(r'^\s*<(div|/div|table|/table)\b', line):
            flush_para()
            out.append(inline(line, res))
            out_has_block[0] = True
            i += 1
            continue
        para.append(line)
        i += 1
    flush_para()
    close_lists()


def _table(lines, i, out, res):
    """Render the table opening at lines[i]; return the index past its |}."""
    first = lines[i].strip()
    out.append('<table%s>' % (' ' + first[2:].strip() if first[2:].strip() else ''))
    i += 1
    row_open = False
    cell = None             # (tag, attrs, [content lines])

    def close_cell():
        nonlocal cell
        if cell is None:
            return
        tag, attrs, body = cell
        inner = []
        _blocks(body, 0, len(body), inner, res, in_cell=True)
        out.append('<%s%s>%s\n</%s>' % (tag, attrs, '\n'.join(inner), tag))
        cell = None

    def open_row():
        nonlocal row_open
        if not row_open:
            out.append('<tr>')
            row_open = True

    def close_row():
        nonlocal row_open
        close_cell()
        if row_open:
            if out[-1].startswith('<tr'):        # MediaWiki drops a row with no cells
                out.pop()
            else:
                out.append('</tr>')
            row_open = False

    while i < len(lines):
        raw = lines[i]
        s = raw.strip()
        if s.startswith('{|'):
            # nested table belongs to the current cell's content
            if cell is None:
                open_row()
                cell = ('td', '', [])
            depth, j = 0, i
            while j < len(lines):
                t = lines[j].strip()
                if t.startswith('{|'):
                    depth += 1
                elif t.startswith('|}'):
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            cell[2].extend(lines[i:j + 1])
            i = j + 1
            continue
        if s.startswith('|}'):
            close_row()
            out.append('</table>')
            if s[2:].strip():
                out.append(inline(s[2:], res))
            return i + 1
        if s.startswith('|-'):
            close_row()
            open_row_attrs = s[2:].lstrip('-').strip()
            out.append('<tr%s>' % (' ' + open_row_attrs if open_row_attrs else ''))
            row_open = True
            i += 1
            continue
        if s.startswith('|+'):
            close_cell()
            attrs, body = _attrs_and_body(s[2:])
            out.append('<caption%s>%s</caption>' % (attrs, inline(body.strip(), res)))
            i += 1
            continue
        if s.startswith('|') or s.startswith('!'):
            close_cell()
            open_row()
            tag = 'th' if s[0] == '!' else 'td'
            content = s[1:]
            pieces = _cell_split(content, '||')
            if tag == 'th':
                pieces = [q for p in pieces for q in _cell_split(p, '!!')]
            for n, piece in enumerate(pieces):
                close_cell()
                attrs, body = _attrs_and_body(piece)
                cell = (tag, attrs, [INLINE + (body.strip() if n < len(pieces) - 1 else body.lstrip())])
            i += 1
            continue
        if cell is not None:
            cell[2].append(raw)
        elif s:
            # text between rows: MediaWiki moves it before the table; keep it in place
            out.append(inline(s, res))
        i += 1
    close_row()
    out.append('</table>')
    return i
