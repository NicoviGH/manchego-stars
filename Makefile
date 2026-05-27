CAMPAIGN ?= rime-of-the-frostmaiden

# Phase 0: placeholder until build-campaign.ts is implemented (Phase 2)
# For now, delegates straight to the fireemblem8u decomp build to verify
# the base toolchain is working.

.PHONY: all clean verify

all: fireemblem8.gba

fireemblem8.gba:
	$(MAKE) -C fireemblem8u -j$(shell nproc 2>/dev/null || sysctl -n hw.ncpu)

verify:
	@cd fireemblem8u && sha1sum -c sha1.txt && echo "ROM OK"

clean:
	$(MAKE) -C fireemblem8u clean
