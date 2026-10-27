"""Draws the Calcite logo: the calcite block as the inventory shows it, and the wordmark.

    python assets/logo/logo.py

Needs Pillow, numpy and fontTools, texture/calcite.png and fonts/Unbounded[wght].ttf. Vanilla
material stays local, so texture/ isn't committed: take the textures banner.py and this script
name from assets/minecraft/textures/block/ in the 26.3 client jar.

Writes calcite-mark.svg and calcite-512.png, the block alone, and calcite-logo.svg and
calcite-logo-white.svg, the block with the wordmark.

The block is drawn the way the game draws a block in the inventory: an orthographic view turned
45 degrees about the vertical and tipped 30 degrees, with the top face lit fully, the left at 0.8
and the right at 0.6. Each texel is a parallelogram, so the SVG stays sharp at any size.

The wordmark is Unbounded Bold, lowercase, with an x-height of 64 on a baseline at 104,
converted to outlines, which the SIL Open Font License allows; fonts/OFL.txt is its text.
"""

import math
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
TEXTURE = HERE / "texture" / "calcite.png"
FONTS = HERE / "fonts"

INK, PAPER, NIGHT, SNOW = "#1E1F24", "#F7F3EC", "#0D1117", "#F0F6FC"
LIGHT = {"top": 1.0, "left": 0.8, "right": 0.6}

WORD = "calcite"
X_HEIGHT, BASELINE = 64, 104
BLOCK_HEIGHT = 2.1 * X_HEIGHT  # the block in the lockup, taller than the word's ascenders
BLOCK_GAP = 0.4 * X_HEIGHT


def f(n):
    s = f"{n:.3f}".rstrip("0").rstrip(".")
    return "0" if s == "-0" else s


def hexc(rgb):
    return "#%02X%02X%02X" % tuple(int(round(c)) for c in rgb)


# --- the block -----------------------------------------------------------------------------------

def project(x, y, z):
    """A point of the unit cube, x right, y up, z toward the viewer, onto the page, y down."""
    a, b = math.radians(45), math.radians(30)
    x, z = x * math.cos(a) - z * math.sin(a), x * math.sin(a) + z * math.cos(a)
    y, z = y * math.cos(b) - z * math.sin(b), y * math.sin(b) + z * math.cos(b)
    return x, -y


def faces():
    """Each visible face as (name, origin, u step, v step) on the page, for a cube of side 1
    centered on 0. u runs along the texture's columns, v down its rows."""
    c = lambda x, y, z: np.array(project(x - 0.5, y - 0.5, z - 0.5))
    return [
        ("top", c(0, 1, 0), c(1, 1, 0) - c(0, 1, 0), c(0, 1, 1) - c(0, 1, 0)),
        ("left", c(0, 1, 1), c(1, 1, 1) - c(0, 1, 1), c(0, 0, 1) - c(0, 1, 1)),
        ("right", c(1, 1, 1), c(1, 1, 0) - c(1, 1, 1), c(1, 0, 1) - c(1, 1, 1)),
    ]


def block(texture):
    """The block as [(polygon, rgb, kind)], the cube's side 1, centered on 0. Each face starts
    with a quad in its mean color, so antialiased seams between texels don't show what's behind;
    then runs of equal texels along a row are one parallelogram."""
    px = np.asarray(texture, float)
    n = px.shape[0]
    out = []
    for name, o, du, dv in faces():
        lit = px * LIGHT[name]
        out.append(([o, o + du, o + du + dv, o + dv], lit.reshape(-1, 3).mean(axis=0), "face"))
        for row in range(n):
            col = 0
            while col < n:
                end = col
                while end < n and (lit[row, end] == lit[row, col]).all():
                    end += 1
                a, b = o + du * col / n + dv * row / n, o + du * end / n + dv * row / n
                out.append(([a, b, b + dv / n, a + dv / n], lit[row, col], "texel"))
                col = end
    return out


def fit(quads, size, x0, cy):
    """Scales the block to `size` tall, its left edge at x0 and its middle at cy."""
    pts = np.array([p for quad, _, _ in quads for p in quad])
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    k = size / (hi[1] - lo[1])
    return [([(p - (lo[0], (lo[1] + hi[1]) / 2)) * k + (x0, cy) for p in quad], rgb, kind)
            for quad, rgb, kind in quads]


def block_width(size):
    pts = np.array([p for _, o, du, dv in faces() for p in (o, o + du, o + dv, o + du + dv)])
    return size * np.ptp(pts[:, 0]) / np.ptp(pts[:, 1])


# --- the wordmark --------------------------------------------------------------------------------

_fonts = {}


def font_letters(file, weight, tracking=0.0):
    """A font's glyphs as outlines at `weight`, scaled to the x-height, `tracking` added
    between letters as a share of the x-height. The returned function takes x and returns
    ([(path d, evenodd)], the advance's end)."""

    def draw(x):
        from fontTools.pens.svgPathPen import SVGPathPen
        from fontTools.pens.transformPen import TransformPen
        from fontTools.ttLib import TTFont
        from fontTools.varLib import instancer

        if (file, weight) not in _fonts:
            font = TTFont(FONTS / file)
            if "fvar" in font:
                font = instancer.instantiateVariableFont(font, {"wght": weight})
            _fonts[file, weight] = font
        font = _fonts[file, weight]
        s = X_HEIGHT / font["OS/2"].sxHeight
        glyphs, cmap, hmtx = font.getGlyphSet(), font.getBestCmap(), font["hmtx"]
        parts = []
        for ch in WORD:
            name = cmap[ord(ch)]
            pen = SVGPathPen(glyphs, ntos=f)
            glyphs[name].draw(TransformPen(pen, (s, 0, 0, -s, x, BASELINE)))
            parts.append((pen.getCommands(), False))
            x += hmtx[name][0] * s + tracking * X_HEIGHT
        return parts, x

    return draw


# Unbounded Bold, tracked in a little.
WORDMARK = font_letters("Unbounded[wght].ttf", 700, -0.02)


# --- paths ---------------------------------------------------------------------------------------

def path_polygons(d):
    """The polygons of a path's subpaths, curves flattened. Handles M L H V Q C Z."""
    tokens = re.findall(r"[MmLlHhVvQqCcZz]|-?(?:\d+\.?\d*|\.\d+)", d)
    polys, cur, x, y, cmd, i = [], [], 0.0, 0.0, None, 0

    def nums(n):
        nonlocal i
        i += n
        return [float(t) for t in tokens[i - n:i]]

    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i]
            i += 1
            if cmd in "Zz":
                if cur:
                    polys.append(cur)
                    x, y = cur[0]
                cur = []
                continue
        rel, op = cmd.islower(), cmd.upper()
        bx, by = (x, y) if rel else (0.0, 0.0)
        if op == "M":
            px, py = nums(2)
            x, y = bx + px, by + py
            if cur:
                polys.append(cur)
            cur = [(x, y)]
            cmd = "l" if rel else "L"
        elif op == "L":
            px, py = nums(2)
            x, y = bx + px, by + py
            cur.append((x, y))
        elif op == "H":
            x = (x if rel else 0) + nums(1)[0]
            cur.append((x, y))
        elif op == "V":
            y = (y if rel else 0) + nums(1)[0]
            cur.append((x, y))
        elif op in "QC":
            n = 2 if op == "Q" else 3
            ctrl = [(x, y)] + [(bx + a, by + b) for a, b in zip(*[iter(nums(2 * n))] * 2)]
            for k in range(1, 17):
                t, pts = k / 16, ctrl
                while len(pts) > 1:  # de Casteljau
                    pts = [(p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t) for p, q in zip(pts, pts[1:])]
                cur.append(pts[0])
            x, y = ctrl[-1]
    if cur:
        polys.append(cur)
    return polys


def word_bounds(parts):
    pts = np.array([p for d, _ in parts for poly in path_polygons(d) for p in poly])
    return pts.min(axis=0), pts.max(axis=0)


# --- output --------------------------------------------------------------------------------------

def quad_path(quad):
    return "M" + " L".join(f"{f(x)} {f(y)}" for x, y in quad) + " Z"


def block_elements(quads):
    """Each face's backdrop, then the texels, one path per color."""
    els, texels = [], {}
    for quad, rgb, kind in quads:
        if kind == "face":
            els.append(f'<path fill="{hexc(rgb)}" d="{quad_path(quad)}"/>')
        else:
            texels.setdefault(hexc(rgb), []).append(quad_path(quad))
    return els + [f'<path fill="{c}" d="{" ".join(ds)}"/>' for c, ds in texels.items()]


def write_svg(path, view, els, label="Calcite"):
    body = "\n".join("  " + e for e in els)
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}" role="img" aria-label="{label}">\n'
                    f"  <title>{label}</title>\n{body}\n</svg>\n")


def lockup(texture, letters):
    """The block, then the word, its x-height centered on the block. Returns the block's quads,
    the word's parts and the bounds (x0, y0, x1, y1)."""
    mid = BASELINE - X_HEIGHT / 2
    quads = fit(block(texture), BLOCK_HEIGHT, 0, mid)
    probe, _ = letters(0)
    lo, hi = word_bounds(probe)
    word, _ = letters(block_width(BLOCK_HEIGHT) + BLOCK_GAP - lo[0])
    top = min(mid - BLOCK_HEIGHT / 2, lo[1])
    bottom = max(mid + BLOCK_HEIGHT / 2, hi[1])
    return quads, word, (0, top, block_width(BLOCK_HEIGHT) + BLOCK_GAP + hi[0] - lo[0], bottom)


def fill_mask(polys, width, height, evenodd):
    """Which pixel centers the polygons cover, by scanlines, with SVG's fill rules. Unlike
    PIL's polygon fill this handles a contour that crosses itself, as font outlines can."""
    edges = [(ax, ay, bx, by) for poly in polys for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1]) if ay != by]
    ax, ay, bx, by = np.array(edges).T
    low, high = np.minimum(ay, by), np.maximum(ay, by)
    direction = np.where(by > ay, 1, -1)
    centers = np.arange(width) + 0.5
    mask = np.zeros((height, width), dtype=bool)
    for row in range(max(0, int(low.min())), min(height, int(high.max()) + 1)):
        yc = row + 0.5
        hit = (low <= yc) & (yc < high)
        if not hit.any():
            continue
        cross = ax[hit] + (yc - ay[hit]) / (by[hit] - ay[hit]) * (bx[hit] - ax[hit])
        winding = np.zeros(width, dtype=int)
        for cx, d in zip(cross, direction[hit]):
            winding[centers > cx] += 1 if evenodd else d
        mask[row] = winding % 2 == 1 if evenodd else winding != 0
    return mask


def raster(items, w, h, k, ox, oy, ss=4):
    """Draws [(polygons, rgb, evenodd)] onto a transparent w x h RGBA image, page units scaled
    by k and moved by (ox, oy), antialiased by ss x ss supersampling. A lone convex polygon,
    a texel, goes straight to PIL; anything else is filled by fill_mask."""
    W, H = w * ss, h * ss
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    to_px = lambda poly: [((px * k + ox) * ss, (py * k + oy) * ss) for px, py in poly]
    for polys, rgb, evenodd in items:
        color = tuple(int(round(c)) for c in rgb) + (255,)
        if len(polys) == 1 and len(polys[0]) == 4:
            draw.polygon(to_px(polys[0]), fill=color)
            continue
        mask = fill_mask([to_px(poly) for poly in polys], W, H, evenodd)
        canvas.paste(Image.new("RGBA", (W, H), color), (0, 0), Image.fromarray(mask.astype(np.uint8) * 255))
    # Average premultiplied, so edges against transparency don't darken.
    px = np.asarray(canvas, float).reshape(h, ss, w, ss, 4)
    a = px[..., 3:4] / 255
    alpha = a.mean(axis=(1, 3))
    rgb = (px[..., :3] * a).mean(axis=(1, 3)) / np.maximum(alpha, 1e-6)
    return Image.fromarray(np.dstack([rgb, alpha * 255]).round().clip(0, 255).astype(np.uint8), "RGBA")


def lockup_image(texture, letters, width, word_rgb):
    """The lockup as an RGBA image `width` pixels wide."""
    quads, word, (x0, y0, x1, y1) = lockup(texture, letters)
    items = [([quad], rgb, False) for quad, rgb, _ in quads]
    items += [(path_polygons(d), word_rgb, eo) for d, eo in word]
    k = width / (x1 - x0)
    return raster(items, width, math.ceil((y1 - y0) * k), k, -x0 * k, -y0 * k)


def main():
    texture = Image.open(TEXTURE).convert("RGB")
    quads = fit(block(texture), 112, 64 - block_width(112) / 2, 64)
    write_svg(HERE / "calcite-mark.svg", "0 0 128 128", block_elements(quads))
    items = [([quad], rgb, False) for quad, rgb, _ in quads]
    raster(items, 512, 512, 4, 0, 0).save(HERE / "calcite-512.png", optimize=True)
    quads, word, (x0, y0, x1, y1) = lockup(texture, WORDMARK)
    view = f"{f(x0)} {f(y0)} {f(x1 - x0)} {f(y1 - y0)}"
    for suffix, fill in (("", INK), ("-white", SNOW)):
        els = block_elements(quads)
        els += [f'<path fill="{fill}"{" fill-rule=\"evenodd\"" if eo else ""} d="{d}"/>' for d, eo in word]
        write_svg(HERE / f"calcite-logo{suffix}.svg", view, els)
    print("wrote calcite-mark.svg, calcite-512.png, calcite-logo.svg, calcite-logo-white.svg")


if __name__ == "__main__":
    main()
