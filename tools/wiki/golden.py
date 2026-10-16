"""The Fire Emblem Wiki's render, reduced to what a page LOOKS like (#493): its tags, their classes
and inline styles, and its words, in order. Comparing these between our render and the wiki's
own ignores what does not show (hrefs, image URLs, srcset, whitespace) and catches everything
that does, so a test can hold an exemplar page to the wiki without pinning incidental markup.
"""
import difflib
import re
from html.parser import HTMLParser

KEEP = {'table', 'tr', 'th', 'td', 'caption', 'div', 'h2', 'h3', 'h4', 'ul', 'ol', 'li', 'dl',
        'dd', 'dt', 'b', 'i', 'img', 'a', 'span', 'br', 'small', 'p'}
SKIP_CLASSES = ('toc', 'mw-editsection', 'mw-headline-number')


def norm_style(v):
    v = v or ''
    v = re.sub(r'\s+', ' ', v.strip().rstrip(';'))
    v = re.sub(r'\s*;\s*', '; ', v)
    v = re.sub(r'\s*:\s*', ': ', v)
    return v


class Tok(HTMLParser):
    def __init__(self, style=True):
        super().__init__(convert_charrefs=True)
        self.toks, self.skip, self.stack, self.style = [], 0, [], style

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get('class') or ''
        if self.skip or any(c in cls.split() for c in SKIP_CLASSES) or tag == 'style':
            if tag not in ('br', 'img'):
                self.skip += 1
                self.stack.append(('skip', tag))
            return
        if tag in ('br', 'img'):
            if tag in KEEP:
                self.toks.append('<%s>' % tag)
            return
        if tag == 'span' and (a.get('typeof') == 'mw:File' or cls in ('mw-headline', 'mw-default-size') or not cls):
            self.stack.append(('drop', tag))
            return
        if tag == 'a':
            self.stack.append(('keep', tag))
            self.toks.append('<a>')
            return
        if tag in KEEP:
            cls = ' '.join(sorted(c for c in cls.split() if c not in ('mw-collapsible',)))
            st = norm_style(a.get('style')) if self.style else ''
            self.toks.append('<%s%s%s>' % (tag, ' .' + cls if cls else '',
                                            ' {' + st + '}' if st else ''))
            self.stack.append(('keep', tag))
        else:
            self.stack.append(('drop', tag))

    def handle_startendtag(self, tag, attrs):
        # `<br/>` is one element: the default handler adds an end tag, which unwinds the stack
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        while self.stack:
            kind, t = self.stack.pop()
            if kind == 'skip':
                self.skip -= 1
            elif kind == 'keep' and not self.skip:
                self.toks.append('</%s>' % t)
            if t == tag:
                break

    def handle_data(self, data):
        if self.skip:
            return
        d = re.sub(r'[\s​]+', ' ', data).strip()
        if d:
            for w in d.split(' '):
                self.toks.append(w)


def tokens(html_text, style=True, drop_p=True):
    t = Tok(style)
    t.feed(html_text)
    toks = t.toks
    if drop_p:
        toks = [x for x in toks if x not in ('<p>', '</p>')]
    if toks[:1] == ['<div .mw-content-ltr mw-parser-output>'] and toks[-1:] == ['</div>']:
        toks = toks[1:-1]                    # MediaWiki's page wrapper, not page content
    return toks



def ratio(ours, theirs):
    """How much of the wiki's page our render reproduces, 0..1, over token sequences."""
    return difflib.SequenceMatcher(None, ours, theirs, autojunk=False).ratio()


def diff(ours, theirs, limit=20, ctx=3):
    """The first `limit` differences, as readable lines (what a failing test prints)."""
    out = []
    sm = difflib.SequenceMatcher(None, ours, theirs, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'equal':
            continue
        out.append('%s after %r:\n  ours: %s\n  wiki: %s' % (
            op, ' '.join(ours[max(0, i1 - ctx):i1]), ' '.join(ours[i1:i2])[:300],
            ' '.join(theirs[j1:j2])[:300]))
        if len(out) >= limit:
            break
    return out
