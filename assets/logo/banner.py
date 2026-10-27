"""Makes the README banners: the Calcite logo in the hollow of an amethyst geode, cut in half.

    python assets/logo/banner.py

Needs logo.py next to this file, and what it needs, and the block textures in texture/.
Writes calcite-banner.png. It's dark, a cave, and has its own background, so one banner
serves light and dark themes.

Calcite's home in the game is the geode: smooth basalt outside, then calcite, then amethyst
lining a hollow, with clusters growing in from the walls. The banner is a slice through one,
on a grid of blocks 32 pixels square, 2 pixels a texel. The hollow is an ellipse around the
logo, and each shell is that many blocks out from it, with smooth noise added so the walls
wander the way a real geode's do. Clusters keep clear of the logo. The hollow is night,
glowing faintly purple near its walls.
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import logo

HERE = logo.HERE
TEX = HERE / "texture"

WIDTH, HEIGHT = 1600, 480
TEXEL = 2
BLOCK = 16 * TEXEL
LOGO_WIDTH = 600
CORNER = 20
HOLLOW = (640, 128)          # the hollow's half width and half height, in pixels
SHELLS = [(1, "amethyst"), (3, "calcite"), (4, "basalt")]  # outer edges, in blocks from the hollow
WANDER = 0.7                 # how far the walls wander, in blocks
SEED = 26

# (hollow, glow, word)
THEMES = {
    "calcite-banner.png": ((13, 17, 23), (140, 90, 200), (240, 246, 252)),
}

BUDS = ["amethyst_cluster", "large_amethyst_bud", "medium_amethyst_bud", "small_amethyst_bud"]


def texture(name):
    return np.asarray(Image.open(TEX / f"{name}.png").convert("RGBA"), float)


def wander(h, w, rnd):
    """Smooth noise on the block grid, from -1 to 1."""
    coarse = rnd.uniform(-1, 1, (h // 3 + 3, w // 3 + 3))
    img = Image.fromarray(((coarse + 1) * 127.5).astype(np.uint8)).resize((w + 6, h + 6), Image.BICUBIC)
    return np.asarray(img, float)[3:3 + h, 3:3 + w] / 127.5 - 1


def layers(rnd):
    """Each block's layer: 0 for the hollow, then 1 amethyst, 2 calcite, 3 basalt, 4 stone."""
    h, w = HEIGHT // BLOCK, WIDTH // BLOCK
    ys, xs = np.mgrid[0:h, 0:w]
    cx, cy = (xs + 0.5) * BLOCK - WIDTH / 2, (ys + 0.5) * BLOCK - HEIGHT / 2
    # Distance from each block's center to the hollow's ellipse, signed, in blocks.
    t = np.linspace(0, 2 * np.pi, 4000, endpoint=False)
    ex, ey = HOLLOW[0] * np.cos(t), HOLLOW[1] * np.sin(t)
    dist = np.hypot(cx[..., None] - ex, cy[..., None] - ey).min(axis=-1)
    inside = (cx / HOLLOW[0]) ** 2 + (cy / HOLLOW[1]) ** 2 < 1
    d = np.where(inside, -dist, dist) / BLOCK + WANDER * wander(h, w, rnd)
    out = np.full((h, w), len(SHELLS) + 1)
    for i, (edge, _) in reversed(list(enumerate(SHELLS))):
        out[d < edge] = i + 1
    out[d < 0] = 0
    return out


def geode(hollow, glow, logo_box):
    rnd = np.random.default_rng(SEED)
    grid = layers(rnd)
    h, w = grid.shape
    tex = {name: texture(name) for name in
           ["amethyst_block", "budding_amethyst", "calcite", "smooth_basalt", "stone"] + BUDS}
    img = np.zeros((HEIGHT, WIDTH, 3))
    img[:] = hollow

    # The hollow's glow: light from the amethyst, falling off from the walls.
    walls = Image.fromarray(((grid > 0) * 255).astype(np.uint8)).resize((WIDTH, HEIGHT), Image.NEAREST)
    near = np.asarray(walls.filter(ImageFilter.GaussianBlur(36)), float)[..., None] / 255
    img = img + (np.array(glow, float) - img) * near * 0.55

    yy, xx = np.mgrid[0:h, 0:w]
    edge = np.hypot((xx + 0.5) / w - 0.5, (yy + 0.5) / h - 0.5) * 2  # 0 center, ~1.04 corners
    budding = np.zeros_like(grid, dtype=bool)
    for y in range(h):
        for x in range(w):
            layer = grid[y, x]
            if layer == 0:
                continue
            if layer == 1:
                budding[y, x] = rnd.random() < 0.3
                name = "budding_amethyst" if budding[y, x] else "amethyst_block"
            else:
                name = ["calcite", "smooth_basalt", "stone"][min(layer, 4) - 2]
            # Deeper is darker, and so are the banner's ends.
            light = [1.0, 1.0, 0.95, 0.8, 0.55][layer - 1] * (1 - 0.35 * max(0, edge[y, x] - 0.55))
            img[y * BLOCK:(y + 1) * BLOCK, x * BLOCK:(x + 1) * BLOCK] = \
                np.kron(tex[name][..., :3], np.ones((TEXEL, TEXEL, 1))) * light

    # Buds, on the amethyst's hollow side, growing inward, clear of the logo.
    lx0, ly0, lx1, ly1 = logo_box
    for y in range(h):
        for x in range(w):
            if grid[y, x] != 1 or rnd.random() > (0.85 if budding[y, x] else 0.2):
                continue
            for dy, dx, turn in ((-1, 0, 0), (1, 0, 2), (0, 1, 3), (0, -1, 1)):
                ny, nx = y + dy, x + dx
                if not (0 <= ny < h and 0 <= nx < w) or grid[ny, nx] != 0:
                    continue
                px, py = nx * BLOCK, ny * BLOCK
                if px + BLOCK > lx0 - 12 and px < lx1 + 12 and py + BLOCK > ly0 - 12 and py < ly1 + 12:
                    break
                sprite = np.rot90(tex[BUDS[rnd.integers(len(BUDS))]], turn)
                sprite = np.kron(sprite, np.ones((TEXEL, TEXEL, 1)))
                a = sprite[..., 3:4] / 255
                cell = img[py:py + BLOCK, px:px + BLOCK]
                img[py:py + BLOCK, px:px + BLOCK] = cell * (1 - a) + sprite[..., :3] * a
                break
    return img


def banner(hollow, glow, word):
    mark = logo.lockup_image(Image.open(logo.TEXTURE).convert("RGB"), logo.WORDMARK, LOGO_WIDTH, word)
    rgba = np.asarray(mark, float)
    lh, lw = rgba.shape[:2]
    oy, ox = (HEIGHT - lh) // 2, (WIDTH - lw) // 2
    img = geode(hollow, glow, (ox, oy, ox + lw, oy + lh))
    a = rgba[..., 3:4] / 255
    img[oy:oy + lh, ox:ox + lw] = img[oy:oy + lh, ox:ox + lw] * (1 - a) + rgba[..., :3] * a

    # Rounded corners, antialiased 4x.
    corners = Image.new("L", (WIDTH * 4, HEIGHT * 4), 0)
    ImageDraw.Draw(corners).rounded_rectangle((0, 0, WIDTH * 4 - 1, HEIGHT * 4 - 1), CORNER * 4, fill=255)
    out = Image.fromarray(img.round().clip(0, 255).astype(np.uint8)).convert("RGBA")
    out.putalpha(corners.resize((WIDTH, HEIGHT), Image.LANCZOS))
    return out


def main():
    for name, colors in THEMES.items():
        banner(*colors).save(HERE / name, optimize=True)
        print(f"wrote {name}")


if __name__ == "__main__":
    main()
