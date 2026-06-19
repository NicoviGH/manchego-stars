CAMPAIGN ?= rime-of-the-frostmaiden

# Phase 2: content pipeline. `make` first runs the campaign generator
# (tools/build_campaign.py), which injects our content into the fireemblem8u
# working tree, then builds the decomp ROM target directly.
#
# NOTE: we now intentionally diverge from vanilla, so we build the decomp's
# `fireemblem8.gba` target (NOT its default `compare` goal, which sha1-checks
# against the vanilla ROM). "make green" now means THE ROM BUILDS, not
# byte-identical-to-vanilla. Restore vanilla art with:
#   git -C fireemblem8u checkout graphics/portrait

NPROC := $(shell nproc 2>/dev/null || sysctl -n hw.ncpu)

# --- macOS toolchain shims (see tools/setup-toolchain.sh) ---------------------
# The decomp build assumes a Linux host. On macOS two adjustments keep a plain
# `make` green:
#   1. agbcc's host C++ tool (jsonproc) needs the SDK's libc++ headers — the
#      Command Line Tools' own c++/v1 is incomplete on recent Apple clang.
#   2. Several gfx scripts use `match`/`case`, which require python >= 3.10; the
#      system python3 is 3.9, so put Homebrew's python ahead on PATH for the
#      `#!/usr/bin/env python3` shebangs (normalised by tools/setup-toolchain.sh).
ifeq ($(shell uname),Darwin)
SDK_CXX := $(shell xcrun --show-sdk-path 2>/dev/null)/usr/include/c++/v1
export CPLUS_INCLUDE_PATH := $(SDK_CXX)$(if $(CPLUS_INCLUDE_PATH),:$(CPLUS_INCLUDE_PATH),)
BREW_PY := $(firstword $(wildcard /opt/homebrew/opt/python@3.1*/libexec/bin /usr/local/opt/python@3.1*/libexec/bin))
ifneq ($(BREW_PY),)
export PATH := $(BREW_PY):$(PATH)
endif
endif

.PHONY: all clean verify check test difficulty

all: fireemblem8.gba

# MONTAGE=1 wires the #43 opening montage (lore crawl on New Game) in place of
# the dev straight-to-map boot cut. Distribution builds (#37) must set it.
fireemblem8.gba:
	python3 tools/build_campaign.py --campaign $(CAMPAIGN) $(if $(MONTAGE),--montage)
	$(MAKE) -C fireemblem8u fireemblem8.gba -j$(NPROC)

# Drift guard: docs/tooling consistency. Same logic CI and the git pre-commit hook run.
check:
	@python3 tools/check.py

# Verify the built ROM's text decodes cleanly. (We diverge from vanilla on purpose,
# so there is no sha1 match to check.)
verify:
	@python3 tools/verify_text.py

# Run the Python unit tests (combat math + stat resolution + difficulty engine).
# Also run by `make check` / CI / the pre-commit hook.
test:
	@for t in tools/test_*.py; do echo "== $$t =="; python3 $$t || exit 1; done

# Static per-chapter difficulty / vanilla-parity report (no ROM build, no mGBA).
#   make difficulty CH=ch01     # one chapter's report
#   make difficulty             # campaign-wide enemy-pressure curve (all chapters)
difficulty:
ifeq ($(strip $(CH)),)
	@python3 tools/difficulty.py --campaign $(CAMPAIGN) --curve
else
	@python3 tools/difficulty.py --campaign $(CAMPAIGN) --chapter $(CH)
endif

clean:
	$(MAKE) -C fireemblem8u clean
