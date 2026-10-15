#!/usr/bin/env python3
"""Vendor the Fire Emblem Wiki's own page sources, templates and renders (#493).

The wiki we generate is the Fire Emblem Wiki's layout filled with our data, and the layout IS the
wiki's templates. So we keep their source rather than copying rendered markup by eye: this
fetches one real FE8 page per page type (EXEMPLARS), every template and Lua module those pages
call, transitively, and the wiki's own render of each exemplar. `tools/wiki/mw.py` expands the
templates and `tools/test_wiki_engine.py` holds each exemplar's render against the wiki's,
so a template we render wrong fails a test instead of reaching Nicolas.

    python3 tools/wiki/vendor.py            # refresh everything under tools/wiki/vendor/

Re-run it when the wiki changes a template we use; the test diff shows what moved.
"""
import gzip
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from wiki import golden          # noqa: E402

VENDOR = os.path.join(HERE, 'vendor')
WIKI = 'https://fireemblemwiki.org/w/index.php?'
UA = {'User-Agent': 'Mozilla/5.0 (manchego-stars wiki vendoring)'}

# One real FE8 page per page type OUR wiki publishes (Nicolas, 2026-10-14), plus the navbox.
# Classes and items stay vanilla, so their links go to the real wiki and need no exemplar.
EXEMPLARS = (
    'Fire Emblem: The Sacred Stones',                         # the game article (home page)
    'The Bandits of Borgo',                                   # chapter
    'The Bandits of Borgo/Script',                            # chapter script
    'A New Journey',                                          # interlude chapter
    'Colm',                                                   # playable character
    'Dara',                                                   # non-playable character
    'Bazba',                                                  # boss
    'Imperial Three', 'Sacred Stone (object)',                # concepts (the lord-select page)
    'List of chapters in Fire Emblem: The Sacred Stones',
    'List of characters in Fire Emblem: The Sacred Stones',
    'Availability chart/The Sacred Stones',
)
NAVBOX = 'Template:Nav8'

MAGIC = {'PAGENAME', 'NAMESPACE', 'FULLPAGENAME', 'BASEPAGENAME', 'SUBPAGENAME', '!', '(!',
         '!)', '!-', '=', 'DEFAULTSORT', 'DISPLAYTITLE', 'lc', 'uc', 'ucfirst', 'lcfirst',
         'urlencode', 'SITENAME', 'CURRENTYEAR'}


def fetch(title, action):
    url = WIKI + urllib.parse.urlencode({'title': title, 'action': action})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                        timeout=30) as r:
                return r.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except OSError:
            time.sleep(2 * (attempt + 1))
    raise SystemExit('ERROR: could not fetch %s (%s)' % (title, action))


def file_name(title):
    """A title as a vendored file stem: '/' -> '__', ':' -> '--', ' ' -> '_'."""
    return title.replace('/', '__').replace(':', '--').replace(' ', '_')


def calls(text, lua):
    """Titles a page, template or module pulls in. A Lua module contributes only its real
    require/loadData/expandTemplate calls: braces inside Lua strings are not template calls."""
    names = set()
    if not lua:
        for m in re.finditer(r'\{\{\s*([^{}|#:\n][^{}|:\n]*?)\s*(?:\||\}\}|:)', text):
            n = m.group(1).strip()
            if n.startswith('{') or n in MAGIC or n.lower() in MAGIC:
                continue
            names.add('Template:' + n[0].upper() + n[1:].replace('_', ' '))
        for m in re.finditer(r'#invoke:\s*([^|}]+)', text):
            names.add('Module:' + m.group(1).strip())
    for m in re.finditer(r"(?:require|mw\.loadData)\(\s*['\"](Module:[^'\"]+)['\"]", text):
        names.add(m.group(1))
    for m in re.finditer(r"expandTemplate\{\s*title\s*=\s*['\"]([^'\"]+)['\"]", text):
        names.add('Template:' + m.group(1))
    return names


def crawl(queue, seen, missing):
    """Fetch every title in `queue` and everything it statically calls, transitively."""
    while queue:
        title = queue.pop(0)
        if title in seen:
            continue
        seen.add(title)
        text = fetch(title, 'raw')
        time.sleep(0.2)
        if text is None:
            missing.append(title)
            continue
        lua = title.startswith('Module:')
        is_page = title in EXEMPLARS
        sub = 'pages' if is_page else 'templates'
        with open(os.path.join(VENDOR, sub, file_name(title) + ('.lua' if lua else '.wiki')),
                  'w', encoding='utf-8') as f:
            f.write(text)
        redirect = re.match(r'\s*#redirect\s*\[\[([^\]|]+)', text, re.I)
        if redirect:
            queue.append(redirect.group(1).strip())
            continue
        body = text if is_page or lua else re.sub(r'<noinclude>.*?(</noinclude>|$)', '', text,
                                                   flags=re.S)
        queue += sorted(c for c in calls(body, lua) if c not in seen)
        if is_page:
            rendered = fetch(title, 'render')
            with gzip.open(os.path.join(VENDOR, 'golden', file_name(title) + '.json.gz'),
                           'wt', encoding='utf-8') as f:
                json.dump(golden.tokens(rendered), f)


def dynamic_templates(seen, missing):
    """Templates whose NAME is built at expansion time ({{{{{type}}}FEH}}) are invisible to the
    static crawl. Render each exemplar; fetch what the engine reports missing; repeat."""
    from wiki import mw
    while True:
        wanted = set()
        for title in EXEMPLARS:
            path = os.path.join(VENDOR, 'pages', file_name(title) + '.wiki')
            with open(path, encoding='utf-8') as f:
                text = f.read()
            try:
                mw.Wiki(pagename=title).expand_text(text)
            except KeyError as e:
                m = re.match(r"'template not vendored: (.*)'$", str(e))
                if m and m.group(1) not in seen:
                    wanted.add(m.group(1))
        if not wanted:
            return
        crawl(sorted(wanted), seen, missing)


def main():
    for sub in ('templates', 'pages', 'golden'):
        os.makedirs(os.path.join(VENDOR, sub), exist_ok=True)
    seen, missing = set(), []
    crawl(list(EXEMPLARS) + [NAVBOX], seen, missing)
    dynamic_templates(seen, missing)
    print('%d titles vendored, %d missing on the wiki (template calls inside unused '
          'branches)' % (len(seen) - len(missing), len(missing)))


if __name__ == '__main__':
    main()
