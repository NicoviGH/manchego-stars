#!/usr/bin/env python3
"""Pinky bust touch-up (faithful to "Pinky Art.png", pixel-by-pixel like Rootis/Marty).

The smooth downscale frames Pinky well (both big ears, gem nose, swirl etchings), but a
few features can't survive the ~17x downscale + 16-colour quantization and need a hand
pass. This deterministic, colour-keyed pass fixes exactly these and nothing else:

  1. BLUE EYES. Pinky's ears (magenta) + ruby nose (red) are so saturated they consume
     the chroma-reservation slots, so BOTH irises (the big near eye and the small far
     eye tucked by the right ear) desaturate to a muddy blue-grey. We free two palette
     slots by merging the three near-identical dark greys (visually one colour), assign
     them two true blues, and repaint only the iris pixels inside scoped eye boxes
     (black pupils + white catchlights untouched), then despeckle the iris interiors.

  2. EARS/HANDS vs RUBY contrast (Nicolas's note). The ears, paws and ruby nose all
     quantized onto the SAME three red slots, so the ruby didn't pop. We lighten the two
     shared pink slots (so ears + hands read as a lighter pink) and, since the eye fix
     frees the old iris-shadow slot, repurpose it as a bright ruby red — then remap the
     gem's pixels to ruby + deep-red so the nose stays saturated and stands out.

16 colours preserved throughout (FE8 cap).

Reproduce:
  ref_to_bust.py "Pinky Art.png" pinky.png --crop 380,100,1675,1179   (smooth, default)
  python3 pinky_cleanup.py pinky.png
"""
import sys
import numpy as np
from PIL import Image

p = sys.argv[1] if len(sys.argv) > 1 else "pinky.png"
im = Image.open(p)
idx = np.asarray(im).copy()
pal = np.array(im.getpalette()[:48]).reshape(-1, 3).astype(int)
H, W = idx.shape


def slot(rgb):
    return int(np.sqrt(((pal[:16] - np.array(rgb)) ** 2).sum(1)).argmin())


def nb4(y, x):
    return [idx[y + dy, x + dx] for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))
            if 0 <= y + dy < H and 0 <= x + dx < W]


# Eye boxes (row0,row1,col0,col1) and the gem box, located from the index maps.
EYES = [(33, 49, 47, 62),    # big near eye
        (37, 45, 78, 85)]    # small far eye (tucked against the right ear)
GEM = (43, 58, 73, 89)       # faceted ruby nose

# ── 1. Free two palette slots for the blues ──────────────────────────────────
# 6/7/8 are (65,66,66)/(60,61,61)/(60,60,60): three near-identical dark greys read as
# one colour. Merge the two extras into the survivor, freeing their slots.
KEEP = slot((63, 63, 63))
dups = [i for i in range(16)
        if i != KEEP and np.sqrt(((pal[i] - pal[KEEP]) ** 2).sum()) < 9]
assert len(dups) >= 2, f"need 2 free slots, found {dups}"
BLUE_LIT, BLUE_DARK = dups[:2]
for d in (BLUE_LIT, BLUE_DARK):
    idx[idx == d] = KEEP                          # invisible: colours within 9 RGB
pal[BLUE_LIT] = (40, 130, 205)                    # lit iris  (ref blue ~26,126,204)
pal[BLUE_DARK] = (20, 80, 150)                    # iris shadow

# ── 2. Repaint both irises ───────────────────────────────────────────────────
# The iris is the desaturated blue-grey (83,95,101) + its shadow (53,63,68). Recolour
# all of it inside the eye box; the eyelid/brow/cheek share that blue-grey and so pick
# up a few stray vivid-blue flecks, which §2b then removes by connectivity.
IRIS = slot((83, 95, 101))                        # desaturated blue-grey iris fill
IRIS_SH = slot((53, 63, 68))                      # iris shadow (also the slot we'll
                                                  #   repurpose for ruby once freed)


def nb8(g, y, x):
    return [g[y + dy, x + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)
            if (dy or dx) and 0 <= y + dy < H and 0 <= x + dx < W]


for Y0, Y1, X0, X1 in EYES:
    box = idx[Y0:Y1, X0:X1]
    box[box == IRIS] = BLUE_LIT
    box[box == IRIS_SH] = BLUE_DARK
    idx[Y0:Y1, X0:X1] = box

# ── 2b. Trim stray blue around the eyes ──────────────────────────────────────
# The iris sits INSIDE the dark eye ring; the stray eyelid/brow/cheek flecks sit outside
# it, as separate little blue blobs. Cleanup snaps a blue pixel back to its dominant
# non-blue neighbour (the cheek). MAIN eye -> keep only the largest connected blue blob
# (the iris), drop the rest. FAR eye (tiny, crowded against the ear) -> drop its 5
# leftmost blue pixels, which read as loose specks rather than eye.
BLUE = {BLUE_LIT, BLUE_DARK}


def snap_nonblue(y, x):
    nb = [v for v in nb8(idx, y, x) if v not in BLUE]
    if nb:
        idx[y, x] = max(set(nb), key=nb.count)


def blue_components(box):
    Y0, Y1, X0, X1 = box
    seen, comps = set(), []
    for y in range(Y0, Y1):
        for x in range(X0, X1):
            if idx[y, x] in BLUE and (y, x) not in seen:
                stack, comp = [(y, x)], []
                seen.add((y, x))
                while stack:
                    cy, cx = stack.pop()
                    comp.append((cy, cx))
                    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        ny, nx = cy + dy, cx + dx
                        if Y0 <= ny < Y1 and X0 <= nx < X1 and \
                                idx[ny, nx] in BLUE and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
                comps.append(comp)
    return comps


comps = blue_components(EYES[0])                  # main eye: keep largest blob only
if comps:
    keep = max(comps, key=len)
    for comp in comps:
        if comp is not keep:
            for y, x in comp:
                snap_nonblue(y, x)

Y0, Y1, X0, X1 = EYES[1]                           # far eye: drop 5 leftmost blue
far_blue = sorted((x, y) for y in range(Y0, Y1) for x in range(X0, X1)
                  if idx[y, x] in BLUE)
for x, y in far_blue[:5]:
    snap_nonblue(y, x)

# ── 3. Iris despeckle ────────────────────────────────────────────────────────
# Grey/mauve flecks embedded INSIDE the blue iris (+ a stray mauve pixel in the pupil)
# snap to the local blue/pupil majority. Catchlight whites anchor the enclosure test but
# are never a snap target (highlights don't grow); the >=3-enclosed gate spares the
# eyelid/fur rim.
PUP_A, PUP_B, DK = slot((20, 17, 24)), slot((34, 23, 27)), slot((51, 53, 53))
WHITE = slot((203, 208, 209))
INTRUDER = {slot((163, 165, 164)), slot((136, 137, 138)), slot((136, 116, 127)), IRIS}
SNAP = {BLUE_LIT, BLUE_DARK, PUP_A, PUP_B, DK}
CORE = SNAP | {WHITE}
src = idx.copy()
for Y0, Y1, X0, X1 in EYES:
    for y in range(Y0, Y1):
        for x in range(X0, X1):
            if src[y, x] not in INTRUDER:
                continue
            nb = nb4(y, x)
            if sum(v in CORE for v in nb) < 3:
                continue
            targets = [v for v in nb if v in SNAP]
            if targets:
                idx[y, x] = max(set(targets), key=targets.count)

# ── 3b. Eye-halo cleanup ─────────────────────────────────────────────────────
# The downscale rings each eye with a faint mauve (purple-ish) anti-alias halo on the
# grey cheek — the low-contrast flecks Nicolas flagged (too close to grey for the >70
# despeckle gate). Scoped to a thin band around each eye box: a mauve pixel enclosed by
# grey snaps to its dominant grey neighbour (tie -> lighter), so the cheek reads clean
# without disturbing the swirl etchings or real face shading.
MAUVE = slot((136, 116, 127))
GREY = {slot((163, 165, 164)), slot((136, 137, 138))}
PAD = 5
src = idx.copy()
for Y0, Y1, X0, X1 in EYES:
    for y in range(max(0, Y0 - PAD), min(H, Y1 + PAD)):
        for x in range(max(0, X0 - PAD), min(W, X1 + PAD)):
            if Y0 <= y < Y1 and X0 <= x < X1:      # skip the eye interior itself
                continue
            if src[y, x] != MAUVE:
                continue
            nb = nb4(y, x)
            greys = [v for v in nb if v in GREY]
            if len(greys) >= 3:
                idx[y, x] = min(greys, key=lambda g: -pal[g].sum())  # tie -> lighter

# ── 4. Lighten ears/hands, keep the ruby saturated so it pops ─────────────────
PINK_LT = slot((175, 77, 135))       # shared light pink (ears, paws, gem highlights)
PINK_MD = slot((145, 31, 75))        # shared mid magenta
RED_DEEP = slot((124, 10, 42))       # shared deep red (kept saturated for the gem)
RUBY = IRIS_SH                        # the iris-shadow slot is now free -> reuse it

# stray iris-shadow pixels outside the gem (none expected) -> grey, so RUBY is gem-only
gy0, gy1, gx0, gx1 = GEM
mask = idx == RUBY
mask[gy0:gy1, gx0:gx1] = False
idx[mask] = KEEP

pal[PINK_LT] = (206, 132, 178)       # lighter pink  (was 175,77,135)
pal[PINK_MD] = (182, 84, 128)        # lighter mid   (was 145,31,75)
pal[RUBY] = (185, 40, 58)            # bright ruby red (ref lit facet ~171,33,56)

gem = idx[gy0:gy1, gx0:gx1]
gem[gem == PINK_LT] = RUBY           # gem highlights -> bright ruby
gem[gem == PINK_MD] = RUBY           # gem mid facets -> bright ruby
idx[gy0:gy1, gx0:gx1] = gem          # (deep-red facets stay RED_DEEP)

# ── 5. Gated cheek despeckle ─────────────────────────────────────────────────
# Lone mauve/pink flecks left around the eyes by the downscale's anti-alias halo: a
# pixel matching none of its 4 neighbours, whose neighbours agree (>=3) AND which is a
# strong colour outlier (RGB dist > 70), is noise -> snap to that majority. The eye and
# gem boxes are EXCLUDED so this never eats a catchlight or a gem facet (the >70 gate is
# the same load-bearing guard as in rootis_cleanup.py).
def in_box(y, x, b):
    return b[0] <= y < b[1] and b[2] <= x < b[3]


protected = EYES + [GEM]
src = idx.copy()
for y in range(H):
    for x in range(W):
        if src[y, x] == 0 or any(in_box(y, x, b) for b in protected):
            continue
        nb = nb4(y, x)
        if len(nb) < 3 or src[y, x] in nb:
            continue
        top = max(set(nb), key=nb.count)
        if nb.count(top) >= 3 and np.sqrt(((pal[src[y, x]] - pal[top]) ** 2).sum()) > 70:
            idx[y, x] = top

out = Image.fromarray(idx)
out.putpalette(pal.flatten().tolist())
out.save(p)
n_used = len(set(idx.flatten().tolist()))
print(f"{p}: eyes+ruby touched up ({n_used} colours; "
      f"blue={BLUE_LIT}/{BLUE_DARK} ruby={RUBY})")
