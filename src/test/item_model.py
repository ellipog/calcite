"""An independent model of vanilla's ItemEntity, written from the decompiled Java, for
test/item_entity.calx: an item made with seed 148, then one falling onto stone and sliding."""
import math
import struct


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def bits(x):
    return struct.unpack("<q", struct.pack("<d", x))[0]


class JavaRandom:
    def __init__(self, seed):
        self.seed = (seed ^ 0x5DEECE66D) & ((1 << 48) - 1)

    def next(self, n):
        self.seed = (self.seed * 0x5DEECE66D + 0xB) & ((1 << 48) - 1)
        r = self.seed >> (48 - n)
        if r >= 1 << (n - 1):
            r -= 1 << n
        return r

    def next_long(self):
        v = (self.next(32) << 32) + self.next(32)
        v &= (1 << 64) - 1
        if v >= 1 << 63:
            v -= 1 << 64
        return v

    def next_float(self):
        return (self.next(24) & 0xFFFFFF) / float(1 << 24)

    def next_double(self):
        hi = self.next(26) & ((1 << 26) - 1)
        lo = self.next(27) & ((1 << 27) - 1)
        return ((hi << 27) + lo) * (1.0 / (1 << 53))


def signed(v):
    v &= (1 << 64) - 1
    return v - (1 << 64) if v >= 1 << 63 else v


r = JavaRandom(148)
most = signed((r.next_long() & -61441) | 16384)
least = signed((r.next_long() & 4611686018427387903) | (-(1 << 63)))
bob = f32(f32(r.next_float() * f32(math.pi)) * 2.0)
spin = f32(r.next_float() * 360.0)
vx0 = r.next_double() * 0.2 - 0.1
vz0 = r.next_double() * 0.2 - 0.1
print("made", most, least, struct.unpack("<I", struct.pack("<f", bob))[0], struct.unpack("<I", struct.pack("<f", spin))[0], bits(vx0), bits(vz0))

# Falling onto stone, whose tops are at y 1, and sliding: id 7, from 0.5, 2, 0.5 moving
# 0.05, 0.1, -0.03.
ID = 7
x, y, z = 0.5, 2.0, 0.5
vx, vy, vz = 0.05, 0.1, -0.03
on_ground = False
tick = 0
HALF = f32(0.25) / 2


def ground_shapes(minx, miny, minz, maxx, maxy, maxz):
    """How many stone blocks of the y 0 row BlockCollisions gives for the swept box."""
    if not (miny < 1.0 and maxy > 0.0):
        return 0
    n = 0
    for bx in range(math.floor(minx - 1e-7), math.floor(maxx + 1e-7) + 1):
        for bz in range(math.floor(minz - 1e-7), math.floor(maxz + 1e-7) + 1):
            if minx < bx + 1 and maxx > bx and minz < bz + 1 and maxz > bz:
                n += 1
    return n


def collide(dx, dy, dz):
    minx, miny, minz = x - HALF, y, z - HALF
    maxx, maxy, maxz = x + HALF, y + f32(0.25), z + HALF
    sx0, sx1 = (minx + dx, maxx) if dx < 0 else (minx, maxx + dx) if dx > 0 else (minx, maxx)
    sy0, sy1 = (miny + dy, maxy) if dy < 0 else (miny, maxy + dy) if dy > 0 else (miny, maxy)
    sz0, sz1 = (minz + dz, maxz) if dz < 0 else (minz, maxz + dz) if dz > 0 else (minz, maxz)
    n = ground_shapes(sx0, sy0, sz0, sx1, sy1, sz1)
    if n == 0:
        return dx, dy, dz
    rx = ry = rz = 0.0

    def along(axis, d):
        for _ in range(n):
            if abs(d) < 1e-7:
                return 0.0
            if axis == 1 and d < 0:
                low = miny + ry
                top = 1.0
                # the row is under the box across, so it counts if its top is below
                if top <= low + 1e-7:
                    gap = top - low
                    if gap <= 1e-7 and gap > d:
                        d = gap
        return d

    if dy != 0.0:
        ry = along(1, dy)
    order = [2, 0] if abs(dx) < abs(dz) else [0, 2]
    for a in order:
        if a == 0 and dx != 0.0:
            rx = along(0, dx)
        if a == 2 and dz != 0.0:
            rz = along(2, dz)
    return rx, ry, rz


trace = []
for _ in range(40):
    tick += 1
    vy = vy + -0.04
    if on_ground and not (vx * vx + vz * vz > f32(1.0e-5)) and (tick + ID) % 4 != 0:
        pass
    else:
        dx, dy, dz = vx, vy, vz
        asked = dx * dx + dy * dy + dz * dz
        mx, my, mz = collide(dx, dy, dz) if asked != 0.0 else (dx, dy, dz)
        length = mx * mx + my * my + mz * mz
        if length > 1e-7 or asked - length < 1e-7:
            x, y, z = x + mx, y + my, z + mz
        x_hit = not abs(mx - dx) < f32(1e-5)
        z_hit = not abs(mz - dz) < f32(1e-5)
        vertical = dy != my
        on_ground = vertical and dy < 0.0
        if (abs(dy) > 0.0 and vertical) or x_hit or z_hit:
            cx, cy, cz = vx, vy, vz
            bx, by, bz = cx, cy, cz
            if x_hit:
                bx = -cx * 0.0
            if z_hit:
                bz = -cz * 0.0
            if vertical:
                by = (0.0 - cy) * 1.0 * 0.0
            vx, vy, vz = bx, by, bz
        # speed factors are all 1
        vx, vy, vz = vx * 1.0, vy * 1.0, vz * 1.0
        air = f32(0.98)
        ground = air
        if on_ground:
            ground = f32(ground * f32(0.6))
        vx, vy, vz = vx * ground, vy * air, vz * ground
        if on_ground and vy < 0.0:
            vx, vy, vz = vx * 1.0, vy * -0.5, vz * 1.0
    trace.append((tick, x, y, z, vx, vy, vz, on_ground))

for t in (1, 3, 5, 10, 20, 40):
    tk, a, b, c, d, e, g, og = trace[t - 1]
    print("tick", tk, bits(a), bits(b), bits(c), bits(d), bits(e), bits(g), og)
