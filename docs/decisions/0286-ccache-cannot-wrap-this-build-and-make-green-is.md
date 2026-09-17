---
id: 286
title: "ccache cannot wrap this build, and `make green` is already near its floor"
date: "2026-09-17"
section: "Operational Gotchas (durable)"
issues: [382]
---

# ccache cannot wrap this build, and `make green` is already near its floor

After #380/#382 cut the test suite from 292.6s to 27.7s and the pre-commit hook from 6-10
minutes to ~45s, `make green` became CI's critical path at **129s**. The obvious next move was
ccache. It does not work here, and this record exists so nobody spends the afternoon finding
that out again.

## Why ccache cannot be used

The decomp compiles C through a **pipeline**, with the compiler reading standard input:

```make
$(CPP) $(CPPFLAGS) $< | iconv -f UTF-8 -t CP932 | $(CC1) $(CC1FLAGS) -o $*.s
```

ccache works by intercepting a compiler invoked with a source-file argument: it hashes that
file plus the flags and replays a cached object. It has no way to hash a stdin stream, and no
way to know what `-o $*.s` corresponds to. Making it work would mean **rewriting the upstream
decomp's compile rule**, which is not ours to fork — and `agbcc` is GCC 2.95.1 reading CP932,
so the rule is that shape for real reasons.

## Why the obvious alternative is worse

Caching `fireemblem8u/build/` across CI runs fails for a different reason: a fresh `git
checkout` stamps every source with the checkout time, so cached objects always look stale and
`make` rebuilds them anyway. Fixing that means restoring mtimes from git history, and **a
mistake there yields a stale ROM that passes the gate** — strictly worse than a slow gate.

## Where the 129s actually goes

Measured, rather than assumed:

| | |
|---|---|
| injection (`build_campaign.py`), cold | **41.7s** |
| injection, with a warm `.injectcache` | 37.9s |
| the rest (preprocess + agbcc + assemble + link) | **~87s** |

So caching `.injectcache` in CI — which looked promising, since it is gitignored and therefore
empty on every run — is worth about **4 seconds of 129**. Not worth a cache key.

The injector already solves this problem its own way: it **rewinds 306 unchanged files so
`make` skips them**, which is the same benefit ccache would have provided, applied where it can
actually be applied.

## The conclusion

`make green` stays at ~129s, and CI's wall clock stays at ~3 minutes. The remaining cost is
real compilation of ~1,956 sources, of which injection genuinely changes about 112. **There is
no cheap, safe way to skip the rest**, and the expensive unsafe way trades a 60-90s saving for
the possibility of shipping a ROM built from stale objects.
