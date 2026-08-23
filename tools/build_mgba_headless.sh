#!/usr/bin/env bash
# Build mGBA's HEADLESS frontend, with Lua, into tools/emulator/ (#308).
#
# Why this exists rather than a download: nobody ships a macOS binary that has BOTH.
#   * mGBA's own macOS nightly DMG contains only mGBA.app -- the Qt GUI frontend, whose
#     --help has no headless option at all.
#   * pokeemerald-expansion vendors a prebuilt tools/mgba/mgba-rom-test-mac. It advertises
#     `--script` in its option parser but has NO Lua compiled in (their tests are C in the
#     ROM, so they never needed it) -- a three-line hello.lua fails to load.
# So we build it. BUILD_HEADLESS defaults to OFF upstream; USE_LUA defaults to ON.
#
# What it buys: a `kind: verdict` scenario asserts on MEMORY and needs no pixels, so it can
# run with no window and stop costing Nicolas's attention. See #302 for the measurement --
# 49% of ch05's commits were the session churn that one-watched-run-per-scene produced.
#
# Screenshots do NOT work under it: no video renderer is attached, so emu:screenshot()
# null-derefs inside PNGWritePixels (mCore_screenshot -> PNGWritePixels -> KERN_INVALID_
# ADDRESS at 0x0). That is a C segfault, uncatchable by the pcall in harness.lua's shot(),
# which is why the harness SKIPS the call when PLAYTEST_HEADLESS=1 rather than guarding it.
# `record` and `diagnostic` scenarios stay headed on purpose -- their output is the picture.
#
# One-time, roughly 10 minutes. The binary lands in tools/emulator/, which is gitignored,
# alongside the mGBA-dev.app nightly that run.sh fetches for headed runs.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
DEST="$REPO/tools/emulator"
SRC="${MGBA_SRC:-/tmp/mgba-src}"

command -v brew >/dev/null || { echo "Homebrew required" >&2; exit 2; }
echo "==> deps (cmake, libzip, lua)"
brew list --versions cmake  >/dev/null 2>&1 || brew install cmake
brew list --versions libzip >/dev/null 2>&1 || brew install libzip
brew list --versions lua    >/dev/null 2>&1 || brew install lua

if [ ! -d "$SRC" ]; then
    echo "==> cloning mGBA into $SRC"
    git clone --depth 1 https://github.com/mgba-emu/mgba.git "$SRC"
fi

echo "==> configuring"
# Qt and SDL off: we want no GUI frontend at all, and skipping them drops the Qt dependency
# entirely. Confirm the summary reads `Headless: ON` and `Lua: <version>` -- if Lua is
# missing the binary still builds and still advertises --script, and then fails to load
# every script at runtime. That is exactly how the vendored pokeemerald binary behaves.
cmake -S "$SRC" -B "$SRC/build" \
    -DBUILD_HEADLESS=ON -DBUILD_QT=OFF -DBUILD_SDL=OFF -DUSE_LUA=ON \
    -DCMAKE_BUILD_TYPE=Release | tail -20

echo "==> building"
cmake --build "$SRC/build" -j"$(sysctl -n hw.ncpu)" >/dev/null

echo "==> installing into $DEST"
mkdir -p "$DEST"
cp "$SRC/build/mgba-headless" "$DEST/mgba-headless"
# It links @rpath/libmgba.0.11.dylib, so the dylib travels with it and the loader is
# pointed at its own directory. Without this the binary runs only from the build tree.
cp "$SRC"/build/libmgba.*.dylib "$DEST/" 2>/dev/null || true
install_name_tool -add_rpath "@loader_path" "$DEST/mgba-headless" 2>/dev/null || true

echo "==> verifying Lua is really in there"
probe=$(mktemp /tmp/mgba-probe-XXXX.lua)
out=$(mktemp /tmp/mgba-probe-XXXX.txt)
printf 'local f=io.open("%s","w") f:write("ok") f:close()\n' "$out" > "$probe"
: > "$out"
"$DEST/mgba-headless" --script "$probe" "$REPO/fireemblem8u/baserom.gba" >/dev/null 2>&1 || true
if [ "$(cat "$out")" = "ok" ]; then
    echo "mgba-headless installed and running Lua: $DEST/mgba-headless"
else
    echo "ERROR: built, but Lua scripts do not load -- check the configure summary above" >&2
    exit 1
fi
rm -f "$probe" "$out"
