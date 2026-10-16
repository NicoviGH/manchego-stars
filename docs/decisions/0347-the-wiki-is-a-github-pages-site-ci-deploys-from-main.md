---
id: 347
title: "The wiki is a GitHub Pages site CI deploys from main"
date: "2026-10-15"
section: "Documentation Model"
issues: [486, 493]
---

# The wiki is a GitHub Pages site CI deploys from main

Nicolas, 2026-10-15: "I'd love the wiki to just automatically update itself ... publishing
updates to the wiki is expensive and annoying." The wiki was a claude.ai artifact that someone
republished by hand after every change.

The `build` job now runs `tools/gen_wiki.py` after the ROM build on every run, so a broken
generator fails the PR. On `main` it uploads `build/wiki/` and the `deploy-wiki` job serves it
on GitHub Pages. It is generated in the `build` job because it renders donor maps from the
build tree's graphics. There is no publish step and no secret.

Everything it reads is in the repo. The three inputs that lived only in the local References
folder were vendored: the twin chapters' Fire Emblem Wiki pages (`tools/wiki/vendor/twins/`,
GFDL 1.3), the PCs' HD art at the 640px the page embeds (`portraits/hd/`), and the book's
illustrations (`lore/book-art/`). The repo and the site are public, the way ROM hacks are,
and `CREDITS.md` declares what we do not own (Nicolas: "we've been keeping track of credits
and can declare that we don't own X or Y IP"). Firebase Hosting, Santiago's Ant Game method,
does the same job but needs a service-account secret; Pages needs none.
_Decided: 2026-10-15 (Nicolas)_
