CAMPAIGN ?= rime-of-the-frostmaiden

# Phase 0: placeholder until build-campaign.ts is implemented (Phase 2)
# For now, delegates straight to the fireemblem8u decomp build to verify
# the base toolchain is working.

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

.PHONY: all clean verify

all: fireemblem8.gba

fireemblem8.gba:
	$(MAKE) -C fireemblem8u -j$(NPROC)

verify:
	@cd fireemblem8u && sha1sum -c checksum.sha1 && echo "ROM OK"

clean:
	$(MAKE) -C fireemblem8u clean
