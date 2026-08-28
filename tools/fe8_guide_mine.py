#!/usr/bin/env python3
"""Mine fireemblemwiki.org into a generated FE8 parity + playstyle reference.

WHY THIS EXISTS. `fireemblem8u/` answers "what does vanilla CONTAIN" -- rosters,
flags, drops. It cannot answer "how is the chapter meant to be WON", and that is
what a `parity_reference:` is really reaching for. When a session of the D&D
campaign has to become a chapter, the question is "which vanilla chapter is this
SHAPED like", and only a walkthrough answers it.

NOT a source of truth for OUR chapters -- that is
`campaigns/<id>/chapters/*.yaml`. This records VANILLA only.

WHY THIS SOURCE. fireemblemwod.com was the first attempt and is a dead end: its
`ENG_` pages 403 permanently, and a burst of requests earns a sustained IP block
that survived two hours of silence and was immune to cookies. fireemblemwiki.org
serves cleanly AND is richer -- structured Chapter/Enemy/Boss/Item data plus a
Strategy section, where the walkthrough had prose only. Fandom is not an option
(403s a non-browser client).

Two things that cost real time, recorded so nobody repeats them:
  * The wiki's difficulty tabs are `<div class="tab&#95;content">` -- the class
    attribute is HTML-ESCAPED in the source, so every `class="tab_content"`
    regex silently matches nothing. Byte-offset heuristics over `<table>` are
    NOT a substitute; match the divs with a depth counter.
  * Retrying FAST is what keeps a rate-block alive. One request, no retry, a
    real gap between them, and resume from cache.

USAGE
    python3 tools/fe8_guide_mine.py --fetch      # populate the cache (slow, resumable)
    python3 tools/fe8_guide_mine.py --render     # cache -> docs/fe8-guide.md
    python3 tools/fe8_guide_mine.py --strategy ch6

The HTML cache lives outside the repo in the gitignored `.fe8-guide-cache/`;
only the derived, attributed digest is committed.
"""

import argparse
import collections
import html
import json
import os
import re
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://fireemblemwiki.org/wiki/"
CACHE = os.path.join(REPO, ".fe8-guide-cache", "wiki")
OUT = os.path.join(REPO, "docs", "fe8-guide.md")
GLOSSES = os.path.join(REPO, "docs", "fe8-guide-glosses.json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# (slug, wiki page title, display label). Neither the titles nor the NUMBERS are
# guesses. Titles are the chapter-title strings the decomp ships (MSG_0160..MSG_017B
# in fireemblem8u/tools/textencode/msg_list.txt). The numbers come from
# include/constants/chapters.h, which is the only thing that settles them: the
# message-list ORDER does not match the chapter numbering, and reading numbers off
# it puts Landing at Taizel at Ch11 (it is Ch12) and drops Creeping Darkness and
# Phantom Ship, the two Ch11s, entirely.
CHAPTERS = [
    ("prologue", "The Fall of Renais",   "Prologue"),
    ("ch1",      "Escape!",              "Chapter 1"),
    ("ch2",      "The Protected",        "Chapter 2"),
    ("ch3",      "The Bandits of Borgo", "Chapter 3"),
    ("ch4",      "Ancient Horrors",      "Chapter 4"),
    ("ch5",      "The Empire's Reach",   "Chapter 5"),
    ("ch5x",     "Unbroken Heart",       "Chapter 5x"),
    ("ch6",      "Victims of War",       "Chapter 6"),
    ("ch7",      "Waterside Renvall",    "Chapter 7"),
    ("ch8",      "It's a Trap!",         "Chapter 8"),
    ("eirika9",  "Distant Blade",        "Chapter 9 (Eirika)"),
    ("eirika10", "Revolt at Carcino",    "Chapter 10 (Eirika)"),
    ("eirika11", "Creeping Darkness",    "Chapter 11 (Eirika)"),
    ("eirika12", "Village of Silence",   "Chapter 12 (Eirika)"),
    ("eirika13", "Hamill Canyon",        "Chapter 13 (Eirika)"),
    ("eirika14", "Queen of White Dunes", "Chapter 14 (Eirika)"),
    ("ephraim9",  "Fort Rigwald",        "Chapter 9 (Ephraim)"),
    ("ephraim10", "Turning Traitor",     "Chapter 10 (Ephraim)"),
    ("ephraim11", "Phantom Ship",        "Chapter 11 (Ephraim)"),
    ("ephraim12", "Landing at Taizel",   "Chapter 12 (Ephraim)"),
    ("ephraim13", "Fluorspar's Oath",    "Chapter 13 (Ephraim)"),
    ("ephraim14", "Father and Son",      "Chapter 14 (Ephraim)"),
    ("ch15", "Scorched Sand",     "Chapter 15"),
    ("ch16", "Ruled by Madness",  "Chapter 16"),
    ("ch17", "River of Regrets",  "Chapter 17"),
    ("ch18", "Two Faces of Evil", "Chapter 18"),
    ("ch19", "Last Hope",         "Chapter 19"),
    ("ch20", "Darkling Woods",    "Chapter 20"),
]

STAT_COLS = ["HP", "S/M", "Mag", "Skill", "Spd", "Lck", "Prf", "Wlv", "Def"]


# ---------------------------------------------------------------- fetching ---

def fetch(slug, title, delay=4.0):
    """One page, resuming from cache. This host is well behaved; the delay is
    courtesy, not evasion."""
    dest = os.path.join(CACHE, slug + ".html")
    if os.path.exists(dest) and os.path.getsize(dest) > 20000:
        return "cached"
    url = BASE + title.replace(" ", "_").replace("'", "%27")
    try:
        p = subprocess.run(["curl", "-sS", "--compressed", "-A", UA,
                            "-w", "%{http_code}", "-o", dest, url],
                           capture_output=True, text=True, timeout=60)
        code = (p.stdout or "").strip()[-3:]
    except subprocess.TimeoutExpired:
        # a partial body left behind can be big enough to pass the size check and
        # then be trusted forever, so drop it here rather than let the loop die
        if os.path.exists(dest):
            os.remove(dest)
        time.sleep(delay)
        return "TIMEOUT"
    size = os.path.getsize(dest) if os.path.exists(dest) else 0
    ok = code == "200" and size > 20000
    if not ok and os.path.exists(dest):
        os.remove(dest)
    time.sleep(delay)
    return "%d bytes" % size if ok else "HTTP %s" % code


def fetch_all(delay=4.0):
    os.makedirs(CACHE, exist_ok=True)
    bad = 0
    for slug, title, _ in CHAPTERS:
        r = fetch(slug, title, delay)
        failed = r.startswith(("HTTP", "TIMEOUT"))
        bad += failed
        print(f"  {'FAIL' if failed else 'ok  '} {slug:12s} {title:24s} {r}", flush=True)
    print(f"\n{len(CHAPTERS)-bad} cached, {bad} failed. Re-run to retry only the failures.")
    return bad


# ----------------------------------------------------------------- parsing ---

def _text(fragment):
    t = html.unescape(re.sub(r"<[^>]+>", " ", fragment))
    return re.sub(r"\s+", " ", t).strip()


def _section(page, sect, nxt):
    i = page.find(f'id="{sect}"')
    j = page.find(f'id="{nxt}"')
    return page[i:j if j > i else len(page)] if i >= 0 else ""


def _section_until(page, sect, followers):
    """Slice from `sect` to whichever of `followers` appears first after it."""
    i = page.find(f'id="{sect}"')
    if i < 0:
        return ""
    ends = [page.find(f'id="{f}"', i) for f in followers]
    ends = [e for e in ends if e > i]
    return page[i:min(ends)] if ends else page[i:]


def _tab_panes(chunk):
    """Pair the tab LABELS with their content divs.

    The class attribute is escaped as `tab&#95;content` in the served HTML, and
    the panes nest further divs, so this walks depth rather than regexing a
    closing tag.
    """
    m = re.search(r'<div class="tab&#95;main"', chunk)
    if not m:
        return []
    g = m.start()
    labels = [_text(l) for l in re.findall(
        r'<span class="tab&#95;tab[^"]*">(.*?)</span>', chunk[g:g + 1500], re.S)]
    panes = []
    for pm in re.finditer(r'<div class="tab&#95;content"', chunk[g:]):
        p = g + pm.start()
        depth, k = 0, p
        while True:
            nxt = re.search(r"<div\b|</div>", chunk[k:])
            if not nxt:
                break
            k += nxt.end()
            depth += 1 if nxt.group(0).startswith("<div") else -1
            if depth == 0:
                panes.append(chunk[p:k])
                break
    return list(zip(labels, panes))


def _rows(pane):
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", pane, re.S):
        cells = [_text(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        if len(cells) >= 6 and re.fullmatch(r"\d{1,2}", cells[3]) and \
           re.fullmatch(r"\d{1,2}", cells[4]):
            out.append({"name": cells[1], "klass": cells[2],
                        "level": int(cells[3]), "count": int(cells[4])})
    return out


def parse(path):
    page = open(path, encoding="utf-8", errors="replace").read()
    page = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", page, flags=re.S | re.I)
    d = {}

    cd = _text(_section(page, "Chapter_data", "Character_data"))
    m = re.search(r"Victory:\s*(.+?)\s+(?:Player|Defeat:)", cd)
    d["objective"] = m.group(1).strip() if m else ""
    m = re.search(r"Defeat:\s*(.+?)\s+\d", cd)
    d["lose"] = m.group(1).strip() if m else ""
    m = re.search(r"(\d+)[–-](\d+)(\+\d+)?", cd)
    d["deploy"] = (m.group(0) if m else "")

    d["tiers"] = {}
    for label, pane in _tab_panes(_section(page, "Enemy_data", "Boss_data")):
        rows = _rows(pane)
        if rows:
            d["tiers"][label] = rows

    # `_section` runs to end-of-page when the named next-section is absent, so an
    # `or` chain never reaches its fallback -- it just dumps the page tail. Cut at
    # whichever known follower appears FIRST instead.
    d["strategy"] = _text(_section_until(page, "Strategy",
                                         ("Trivia", "Etymology", "Gallery",
                                          "Navigation", "References")))

    return d


def playable_tiers(tiers):
    """Every scraped tier except the Japanese columns, in page order.

    Tier labels are NOT a fixed set. Observed on the wiki: plain `Normal`, a
    COMBINED `Easy/Normal` (prologue, Ch1, Ch4), and ROUTE-SPLIT `Eirika Normal` /
    `Ephraim Normal` (Ch15, Ch16, which are route-shared chapters). Hardcoding
    ("Easy","Normal","Difficult") silently rendered NOTHING for the route-split
    chapters while the index still counted them -- so match by substring, and
    never drop a tier just because its label is unfamiliar.
    """
    return [(k, v) for k, v in tiers.items() if "(Japan)" not in k]


def tier_like(tiers, want):
    """The tier whose label mentions `want` (so `Easy/Normal` answers to both).
    Returns (label, rows) or (None, None)."""
    for k, v in playable_tiers(tiers):
        if want.lower() in k.lower():
            return k, v
    return None, None


def summarize(tier_rows):
    total = sum(r["count"] for r in tier_rows)
    avg = sum(r["level"] * r["count"] for r in tier_rows) / total if total else 0
    by = collections.Counter()
    for r in tier_rows:
        by[r["klass"]] += r["count"]
    return total, avg, by


# --------------------------------------------------------------- rendering ---

def render(records, glosses):
    L = ["# FE8 chapter guide — parity and playstyle reference\n",
         "**Generated** by `tools/fe8_guide_mine.py`. Do not hand-edit; re-run the tool.\n",
         "Source: **Fire Emblem Wiki** (<https://fireemblemwiki.org>), the independent wiki. "
         "Credited in `CREDITS.md`.\n",
         "**Vanilla FE8 only.** This is the *how is it played* half of parity — the decomp already "
         "answers *what it contains*. Facts about OUR chapters live in "
         "`campaigns/<id>/chapters/*.yaml`; never source a claim about our design from here.\n",
         "Enemy counts are **Normal** unless noted. In FE8 the difficulty dial is a *level shift* "
         "(`chapter_settings`: easyMalus/normalMalus/difficultBonus), not a different force — so a "
         "tier that adds or removes UNITS is a real design signal and is called out.\n",
         "**Shape / Pressure / Teaches** digest each chapter's Strategy section into design "
         "vocabulary, from `docs/fe8-guide-glosses.json`. The index below is the donor-selection "
         "view.\n", "---\n", "## Donor-selection index\n",
         "| Chapter | Objective | Enemies (N) | Shape | Pressure comes from |", "|---|---|---|---|---|"]

    for slug, label, d in records:
        g = glosses.get(slug) or {}
        if isinstance(g, str):
            g = {"playstyle": g}
        lab, rows = tier_like(d["tiers"], "Normal")
        if rows:
            tot = summarize(rows)[0]
            # say WHICH tier when it is not a plain "Normal" -- a route-split or
            # combined label under a column headed Normal is a silent lie.
            cell = f"{tot}" if lab == "Normal" else f"{tot} <sub>({lab})</sub>"
        else:
            cell = "—"
        anchor = re.sub(r"[^a-z0-9 -]", "", label.lower()).replace(" ", "-")
        L.append(f"| [{label}](#{anchor}) | {d['objective'] or '—'} | {cell} "
                 f"| {g.get('shape','—')} | {g.get('pressure','—')} |")
    L.append("\n---\n")

    for slug, label, d in records:
        g = glosses.get(slug) or {}
        if isinstance(g, str):
            g = {"playstyle": g}
        L.append(f"## {label}\n")
        L.append(f"- **Objective**: {d['objective'] or '—'}"
                 + (f"  ·  **Lose**: {d['lose']}" if d.get("lose") else ""))
        if d.get("deploy"):
            L.append(f"- **Deploy**: {d['deploy']}")
        for tier, rows in playable_tiers(d["tiers"]):
            tot, avg, by = summarize(rows)
            mix = ", ".join(f"{v}× {k}" for k, v in by.most_common(6))
            L.append(f"- **{tier}**: {tot} enemies · avg L{avg:.1f} — {mix}")
        nl, n = tier_like(d["tiers"], "Normal")
        hl, h = tier_like(d["tiers"], "Difficult")
        if n and h and nl != hl:
            a, b = summarize(n)[2], summarize(h)[2]
            # union of BOTH key sets: a class REMOVED on Difficult is a delta too,
            # and iterating only the Difficult counter would never show it.
            delta = {k: b.get(k, 0) - a.get(k, 0) for k in set(a) | set(b)
                     if b.get(k, 0) != a.get(k, 0)}
            if delta:
                L.append(f"- **Delta {nl} → {hl}**: {delta} — a UNIT change, not a level shift")
        for key, name in (("shape", "Shape"), ("pressure", "Pressure"), ("teaches", "Teaches")):
            if g.get(key):
                L.append(f"- **{name}**: {g[key]}")
        L.append(f"- **Playstyle**: {g['playstyle']}" if g.get("playstyle") else
                 f"- **Playstyle**: *not yet digested — "
                 f"`tools/fe8_guide_mine.py --strategy {slug}`*")
        L.append("")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--strategy", metavar="SLUG")
    ap.add_argument("--delay", type=float, default=4.0)
    ap.add_argument("--render-anyway", action="store_true",
                    help="render even if the fetch had failures (writes a partial digest)")
    ap.add_argument("--cache", default=CACHE)
    a = ap.parse_args()
    globals()["CACHE"] = a.cache

    if a.strategy:
        p = os.path.join(a.cache, a.strategy + ".html")
        if not os.path.exists(p):
            sys.exit(f"not cached: {a.strategy} (run --fetch)")
        print(parse(p)["strategy"] or "(no Strategy section)")
        return

    if not (a.fetch or a.render):
        a.fetch = a.render = True
    failures = 0
    if a.fetch:
        failures = fetch_all(a.delay)
    if a.render and failures and not a.render_anyway:
        sys.exit(f"ERROR: {failures} page(s) failed to fetch — refusing to overwrite the "
                 f"committed digest from a partial cache. Re-run --fetch (it resumes), "
                 f"or pass --render-anyway if a partial digest is what you want.")
    if a.render:
        records, missing = [], []
        for slug, title, label in CHAPTERS:
            p = os.path.join(a.cache, slug + ".html")
            if os.path.exists(p) and os.path.getsize(p) > 20000:
                records.append((slug, label, parse(p)))
            else:
                missing.append(slug)
        if not records:
            sys.exit("ERROR: cache empty — run with --fetch first (%s)" % a.cache)
        glosses = json.load(open(GLOSSES, encoding="utf-8")) if os.path.exists(GLOSSES) else {}
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        open(OUT, "w", encoding="utf-8").write(render(records, glosses))
        print(f"wrote {OUT} — {len(records)}/{len(CHAPTERS)} chapters")
        if missing:
            print("  MISSING (re-run --fetch): " + ", ".join(missing))


if __name__ == "__main__":
    main()
