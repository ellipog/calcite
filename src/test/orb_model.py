"""An independent model of vanilla's ExperienceOrb and of Block.popExperience, written from the
decompiled Java, for test/experience_orb.calx and test/drops.calx: an orb made with seed 148,
falling onto stone and bouncing; one made with seed 149 following a player; and the level's
random as breaking blocks that drop experience draws from it.

    py -I src/test/orb_model.py
"""
import math
import struct


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def bits(x):
    return struct.unpack("<q", struct.pack("<d", x))[0]


def float_bits(x):
    return struct.unpack("<I", struct.pack("<f", x))[0]


def signed(v, n=64):
    v &= (1 << n) - 1
    return v - (1 << n) if v >= 1 << (n - 1) else v


class JavaRandom:
    """java.util.Random, which LegacyRandomSource is."""

    def __init__(self, seed):
        self.seed = (seed ^ 0x5DEECE66D) & ((1 << 48) - 1)

    def next(self, n):
        self.seed = (self.seed * 0x5DEECE66D + 0xB) & ((1 << 48) - 1)
        return signed(self.seed >> (48 - n), 32)

    def next_int(self, bound):
        r = self.next(31)
        m = bound - 1
        if bound & m == 0:
            return signed((bound * r) >> 31, 32)
        u = r
        while True:
            r = u % bound
            if signed(u - r + m, 32) >= 0:
                return r
            u = self.next(31)

    def next_long(self):
        return signed((self.next(32) << 32) + self.next(32))

    def next_float(self):
        return (self.next(24) & 0xFFFFFF) / float(1 << 24)

    def next_double(self):
        hi = self.next(26) & ((1 << 26) - 1)
        lo = self.next(27) & ((1 << 27) - 1)
        return ((hi << 27) + lo) * (1.0 / (1 << 53))


GRAVITY = 0.03
HALF = 0.25
HEIGHT = 0.5


class Orb:
    """`new ExperienceOrb(level, pos, Vec3.ZERO, value)`: Entity's random and UUID, then its spin,
    then its motion."""

    def __init__(self, seed, x, y, z):
        r = JavaRandom(seed)
        self.most = signed((r.next_long() & -61441) | 16384)
        self.least = signed((r.next_long() & 4611686018427387903) | (-(1 << 63)))
        self.y_rot = f32(r.next_float() * 360.0)
        self.vx = (r.next_double() * 0.2 - 0.1) * 2.0
        self.vy = r.next_double() * 0.2 * 2.0
        self.vz = (r.next_double() * 0.2 - 0.1) * 2.0
        self.x, self.y, self.z = x, y, z
        self.on_ground = False
        self.following = False

    def floor_meets(self, minx, miny, minz, maxx, maxy, maxz):
        """How many stone blocks of the y 0 row and below meet the box, as BlockCollisions finds them."""
        if not (miny < 1.0 and maxy > -64.0):
            return 0
        n = 0
        for bx in range(math.floor(minx - 1e-7), math.floor(maxx + 1e-7) + 1):
            for bz in range(math.floor(minz - 1e-7), math.floor(maxz + 1e-7) + 1):
                if minx < bx + 1 and maxx > bx and minz < bz + 1 and maxz > bz:
                    n += 1
        return n

    def collide_y(self, dy):
        """`collide` against the floor, the only thing there is: only a fall can be stopped, by the
        top of the stone at y 1."""
        if dy >= 0.0:
            return dy
        miny = self.y
        swept = (self.x - HALF, miny + dy, self.z - HALF, self.x + HALF, miny + HEIGHT, self.z + HALF)
        if self.floor_meets(*swept) == 0:
            return dy
        if abs(dy) < 1e-7:
            return 0.0
        gap = 1.0 - miny
        if gap <= 1e-7 and gap > dy:
            return gap
        return dy

    def move(self, dx, dy, dz):
        """`Entity.move`, then `restituteMovementAfterCollisions` on stone, whose bounciness is none."""
        my = self.collide_y(dy)
        mx, mz = dx, dz
        asked = dx * dx + dy * dy + dz * dz
        length = mx * mx + my * my + mz * mz
        if length > 1e-7 or asked - length < 1e-7:
            self.x, self.y, self.z = self.x + mx, self.y + my, self.z + mz
        vertical = dy != my
        below = vertical and dy < 0.0
        self.on_ground = below
        if abs(dy) > 0.0 and vertical:
            # restitution 0: (gravityCompensation - y) * effectiveDrag * restitution
            self.vy = (0.0 - self.vy) * 1.0 * 0.0
        # the block speed factor of stone is 1
        self.vx, self.vy, self.vz = self.vx * 1.0, self.vy * 1.0, self.vz * 1.0
        return below

    def tick(self, player=None):
        """`ExperienceOrb.tick` on the stone floor, nothing in its box, no fluid, no other orb."""
        colliding = self.floor_meets(self.x - HALF, self.y, self.z - HALF, self.x + HALF, self.y + HEIGHT, self.z + HALF) > 0
        if not colliding:
            self.vy = self.vy + -GRAVITY
        if player is not None:
            px, py, pz, eyes = player
            d = (px - self.x) ** 2 + (py - self.y) ** 2 + (pz - self.z) ** 2
            if self.following and d > 64.0:
                self.following = False
            if not self.following and d < 64.0:
                self.following = True
            if self.following:
                ex, ey, ez = px - self.x, py + f32(eyes) / 2.0 - self.y, pz - self.z
                length = ex * ex + ey * ey + ez * ez
                power = 1.0 - math.sqrt(length) / 8.0
                dist = math.sqrt(ex * ex + ey * ey + ez * ez)
                if dist < f32(1.0e-5):
                    nx = ny = nz = 0.0
                else:
                    nx, ny, nz = ex / dist, ey / dist, ez / dist
                pull = power * power * 0.1
                self.vx, self.vy, self.vz = self.vx + nx * pull, self.vy + ny * pull, self.vz + nz * pull
        fall_speed = self.vy
        below = self.move(self.vx, self.vy, self.vz)
        friction = f32(0.98)
        if self.on_ground:
            friction = f32(friction * f32(0.6))
        self.vx, self.vy, self.vz = self.vx * friction, self.vy * friction, self.vz * friction
        if below and fall_speed < -GRAVITY:
            self.vy = -fall_speed * 0.4

    def state(self):
        return [bits(self.x), bits(self.y), bits(self.z), bits(self.vx), bits(self.vy), bits(self.vz), 1 if self.on_ground else 0]


o = Orb(148, 0.5, 2.0, 0.5)
print("made", o.most, o.least, float_bits(o.y_rot), bits(o.vx), bits(o.vy), bits(o.vz))
for t in range(1, 41):
    o.tick()
    if t in (1, 3, 5, 10, 20, 40):
        print("falling", t, *o.state())

p = Orb(149, 0.5, 1.0, 0.5)
for t in range(1, 21):
    p.tick((3.5, 1.0, 0.5, 1.62))
    if t in (1, 2, 5, 10, 20):
        print("following", t, *p.state())


def orb_values(amount):
    """`awardWithDirection`'s split, `getExperienceValue` of what's left each time."""
    out = []
    while amount > 0:
        v = 1
        for s in (2477, 1237, 617, 307, 149, 73, 37, 17, 7, 3):
            if amount >= s:
                v = s
                break
        amount -= v
        out.append(v)
    return out


# Blocks broken at 3, -60, 5 with the level's random seeded 0, in turn: each stack its loot
# gives popped, three nextDoubles each, `popResource`; then `spawnAfterBreak`'s sample of its xp
# range; then, with block_drops on, each orb's `nextInt(40)` as `tryMergeToExisting` draws it.
r = JavaRandom(0)
cases = [
    # block, stacks popped, the sample, block_drops, silk touch's set to 0
    ("diamond_ore", 1, lambda: r.next_int(5) + 3, True, False),
    ("sculk_catalyst", 0, lambda: 5, True, False),
    ("sculk_catalyst silk touch", 1, lambda: 5, True, True),
    ("spawner", 0, lambda: 15 + r.next_int(15) + r.next_int(15), True, False),
    ("redstone_ore", 1, lambda: r.next_int(5) + 1, True, False),
    ("diamond_ore, block_drops off", 1, lambda: r.next_int(5) + 3, False, False),
    ("sculk_catalyst again", 0, lambda: 5, True, False),
]
for name, stacks, sample, drops, silk in cases:
    line = [name + ":"]
    for _ in range(stacks):
        px = 3 + 0.5 + (r.next_double() * 0.5 + -0.25)
        py = -60 + 0.5 + (r.next_double() * 0.5 + -0.25) - 0.125
        pz = 5 + 0.5 + (r.next_double() * 0.5 + -0.25)
        if drops:
            line.append(f"item({bits(px)},{bits(py)},{bits(pz)})")
    amount = sample()
    if silk:
        amount = 0
    if amount > 0 and drops:
        for v in orb_values(amount):
            line.append(f"orb({v},{r.next_int(40)})")
    print("award", " ".join(line))
print("after", r.next_long())
