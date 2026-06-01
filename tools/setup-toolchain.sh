#!/usr/bin/env bash
#
# setup-toolchain.sh — one-time build-toolchain setup for Manchego Stars on macOS.
#
# Idempotent: safe to re-run. Codifies the macOS-specific setup the upstream
# decomp quickstart.sh does not handle (Homebrew deps, a python >= 3.10 with
# numpy/pillow, agbcc, and a few Linux-only shebangs in the submodule scripts).
#
# After this completes, `make` from the repo root produces a byte-identical
# vanilla FE8 ROM (verify with `make verify`).
#
# Usage: tools/setup-toolchain.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DECOMP_DIR="${REPO_DIR}/fireemblem8u"
BASEROM_SRC="/Users/Yonick/Documents/Claude/Projects/Manchego Stars / Fire Emblem Game/Fire Emblem - The Sacred Stones (USA, Australia).gba"

say() { printf '\033[1;36m[setup]\033[0m %s\n' "$*"; }

if [[ "$(uname)" != "Darwin" ]]; then
  say "Non-macOS host: use the decomp's own scripts/quickstart.sh instead."
  exit 1
fi
command -v brew >/dev/null || { echo "Homebrew required: https://brew.sh"; exit 1; }

# 1. Homebrew deps. arm-none-eabi-gcc bundles the binutils assembler/linker;
#    coreutils provides `nproc`; libpng/pkg-config are for the gfx tools.
say "Installing Homebrew deps (arm-none-eabi-gcc, pkg-config, libpng, coreutils, python@3.12)"
brew install arm-none-eabi-gcc pkg-config libpng coreutils python@3.12

# 2. numpy + pillow for the python the build will actually invoke (>= 3.10,
#    because some gfx scripts use match/case). The Makefile puts python@3.1x's
#    libexec ahead on PATH, so install into that interpreter.
PY="$(ls -d /opt/homebrew/opt/python@3.1*/libexec/bin/python3 2>/dev/null | sort | tail -1)"
say "Installing numpy + pillow into ${PY}"
"${PY}" -m pip install --break-system-packages --upgrade numpy pillow

# 3. agbcc — the GBA C compiler. Built from source, installed into the decomp.
if [[ ! -x "${DECOMP_DIR}/tools/agbcc/bin/agbcc" ]]; then
  say "Building agbcc"
  mkdir -p "${DECOMP_DIR}/.deps"
  [[ -d "${DECOMP_DIR}/.deps/agbcc/.git" ]] || \
    git clone --depth 1 https://github.com/pret/agbcc.git "${DECOMP_DIR}/.deps/agbcc"
  ( cd "${DECOMP_DIR}/.deps/agbcc" && ./build.sh && ./install.sh "${DECOMP_DIR}" )
else
  say "agbcc already installed — skipping"
fi

# 4. Normalise Linux-only shebangs in the submodule's python scripts. Upstream
#    ships `#!/bin/python3`, which does not exist on macOS (and /bin is SIP-
#    protected, so it cannot be symlinked). Rewrite to the portable env form.
#    Idempotent; only touches files that still need it.
say "Normalising #!/bin/python3 shebangs in fireemblem8u/scripts"
while IFS= read -r f; do
  sed -i '' '1s|^#!/bin/python3|#!/usr/bin/env python3|' "$f"
done < <(grep -rl '^#!/bin/python3' "${DECOMP_DIR}/scripts" 2>/dev/null || true)

# 5. Base ROM. Never committed (see .gitignore); copied in from the source folder.
if [[ ! -f "${DECOMP_DIR}/baserom.gba" ]]; then
  if [[ -f "${BASEROM_SRC}" ]]; then
    say "Copying baserom.gba"
    cp "${BASEROM_SRC}" "${DECOMP_DIR}/baserom.gba"
  else
    say "WARNING: base ROM not found at the expected path; copy it to fireemblem8u/baserom.gba manually."
  fi
fi

say "Done. Build with:  make   (then  make verify  to confirm the checksum)"
