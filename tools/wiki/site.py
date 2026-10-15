"""Our pages through the wiki's templates (#493): where a link goes, what a file is, one render.

Every page is wikitext that calls the Fire Emblem Wiki's own templates (`tools/wiki/vendor/`)
with our data, rendered by `mw` + `render`. Two answers are ours rather than the wiki's, and both
live here:

- **A link.** `[[Page]]` opens our page when we publish one under that title, and the Fire
  Emblem Wiki's article otherwise -- a vanilla class, item or stat keeps its real article
  (Nicolas, 2026-10-14: "class and item are vanilla, so just link to the real wiki").
- **A file.** The templates name art the wiki's way (`Ma gba <class> <version> enemy.gif`,
  `Small portrait <name> fe08.png`, `Is gba <item>.png`); `Files` maps each name the generator
  registered to the image the build dresses.
"""
import html
import re

from wiki import mw, render

FE_WIKI = 'https://fireemblemwiki.org/wiki/'


class Files:
    """name -> (data URI, width, height), for the names the generator hands the templates.
    The name is lower-cased and spaces folded, as MediaWiki matches file names."""

    def __init__(self):
        self.by_name = {}

    @staticmethod
    def key(name):
        name = re.sub(r'[\s_]+', ' ', name.strip())
        return name[:1].upper() + name[1:].lower()

    def add(self, name, uri, width, height):
        self.by_name[self.key(name)] = (uri, width, height)
        return name

    def get(self, name):
        return self.by_name.get(self.key(name))


class Site(render.Links):
    """Resolves links to our pages ({title: page id}) or the Fire Emblem Wiki, files to `files`."""

    def __init__(self, pages, files):
        self.pages = {self._norm(t): pid for t, pid in pages.items()}
        self.files = files
        self.missing_files = set()

    @staticmethod
    def _norm(title):
        title = re.sub(r'[\s_]+', ' ', title.strip())
        return title[:1].upper() + title[1:]

    def page(self, target, text):
        page, _, anchor = target.partition('#')
        pid = self.pages.get(self._norm(page)) if page else None
        if pid:
            href = '#' + pid + ('-' + anchor.replace(' ', '_') if anchor else '')
            return '<a href="%s" title="%s">%s</a>' % (html.escape(href, quote=True),
                                                     html.escape(page, quote=True), text)
        if ':' in page and page.split(':', 1)[0].lower() == 'wikipedia':
            url = 'https://en.wikipedia.org/wiki/' + page.split(':', 1)[1].strip()
        else:
            url = FE_WIKI + page.strip()
        return ('<a href="%s" title="%s" target="_blank" rel="noopener">%s</a>'
                % (html.escape(url.replace(' ', '_'), quote=True), html.escape(page, quote=True),
                   text))

    def file(self, name, opts):
        got = self.files.get(name)
        alt = html.escape(opts.get('alt', ''), quote=True)
        if got is None:
            self.missing_files.add(name)
            return '<span class="ms-missing-file" title="%s"></span>' % html.escape(name, True)
        uri, w, h = got
        size = opts.get('size', '')
        m = re.fullmatch(r'(\d*)x?(\d*)px', size)
        if m and (m.group(1) or m.group(2)):
            # A box to fit in, never upscaled: MediaWiki shows a 32px minimug asked for at
            # x80px at 32px (Template:ChapChars' portraits).
            want_w = int(m.group(1)) if m.group(1) else None
            want_h = int(m.group(2)) if m.group(2) else None
            scale = min(want_w / w if want_w and w else 1, want_h / h if want_h and h else 1, 1)
            w, h = max(round(w * scale), 1), max(round(h * scale), 1)
        img = ('<img alt="%s" src="%s" width="%d" height="%d" class="mw-file-element" '
               'decoding="async">' % (alt, uri, w, h))
        link = opts.get('link')
        if link == '':
            return img
        if link:
            return self.page(link, img)
        return img


def render_page(title, wikitext, site):
    """One page: expand the wikitext through the vendored templates, then render it."""
    return render.render(mw.Wiki(pagename=title).expand_text(wikitext), site)
