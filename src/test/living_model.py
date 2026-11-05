"""An independent model of vanilla's LivingEntity and ArmorStand moving, written from the decompiled
Java, for test/living.calx: an armor stand falling onto stone, sliding on ice, sliding down a
ladder, falling into water and into lava; and a living entity walking and jumping on stone. Each
prints the ticks the test checks, with the sounds played and the dust thrown up.

    py -I src/test/living_model.py
"""
import math
import struct


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def bits(x):
    return struct.unpack("<q", struct.pack("<d", x))[0]


def float_bits(x):
    return struct.unpack("<i", struct.pack("<f", x))[0]


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

    def next_long(self):
        return signed((self.next(32) << 32) + self.next(32))

    def next_float(self):
        return (self.next(24) & 0xFFFFFF) / float(1 << 24)

    def next_double(self):
        hi = self.next(26) & ((1 << 26) - 1)
        lo = self.next(27) & ((1 << 27) - 1)
        return ((hi << 27) + lo) * (1.0 / (1 << 53))


SIN_SCALE = 10430.378350470453


def table(i):
    return f32(math.sin(i / SIN_SCALE))


def mth_sin(v):
    return table(int(v * SIN_SCALE) & 65535)


def mth_cos(v):
    return table(int(v * SIN_SCALE + 16384.0) & 65535)


def cmf(friction, modifier):
    """computeModifiedFriction."""
    v = f32(1.0 - f32(f32(1.0 - friction) * modifier))
    return min(max(v, 0.0), 1.0)


# The blocks the cases use: whether they're whole cubes, their friction, their sound type's step
# and fall sounds, the fluid in them and whether they're climbable.
SOLID = {"stone", "ice"}
FRICTION = {"ice": f32(0.98)}
SOUNDS = {"stone": "block.stone", "ice": "block.glass", "ladder": "block.ladder", "water": None, "lava": None}
FLUID = {"water": "water", "lava": "lava"}
CLIMBABLE = {"ladder"}
OWN_HEIGHT = f32(8 / 9.0)


class World:
    def __init__(self, floor_block="stone", fluid=None, ladder=False):
        self.floor_block = floor_block
        self.fluid = fluid
        self.ladder = ladder

    def block(self, x, y, z):
        if y < 0:
            return "stone"
        if y == 0:
            return self.floor_block
        if self.fluid and 1 <= y <= 3:
            return self.fluid
        if self.ladder and x == 0 and z == 0 and 1 <= y <= 10:
            return "ladder"
        return "air"


class Living:
    def __init__(self, world, seed, x, y, z, width=0.5, height=1.975, eyes=1.7775):
        self.w = world
        self.random = JavaRandom(seed)
        self.random.next_long()
        self.random.next_long()
        self.yrot = f32(self.random.next_float() * f32(math.pi * 2))
        self.x, self.y, self.z = x, y, z
        self.vx = self.vy = self.vz = 0.0
        self.width, self.height, self.eyes = f32(width), f32(height), f32(eyes)
        self.gravity = 0.08
        self.on_ground = False
        self.hc = self.vc = self.below = False
        self.fall = 0.0
        self.first_tick = True
        self.in_water = False
        self.water = self.lava = 0.0
        self.water_eyes = False
        self.tick_count = 0
        self.move_dist = 0.0
        self.next_step = 1.0
        self.zza = 0.0
        self.speed = 0.0
        self.jumping = False
        self.no_jump_delay = 0
        self.sounds = []
        self.dust = []
        self.splash = 0

    def box(self):
        h = f32(self.width / 2.0)
        return [self.x - h, self.y, self.z - h, self.x + h, self.y + self.height, self.z + h]

    def in_lava(self):
        return not self.first_tick and self.lava > 0.0

    def play(self, name, volume, pitch):
        self.sounds.append((self.tick_count, "minecraft:" + name, float_bits(volume), float_bits(pitch)))

    def fluid_height(self, x, y, z, kind):
        above = self.w.block(x, y + 1, z)
        return 1.0 if FLUID.get(above) == kind else OWN_HEIGHT

    def update_fluids(self):
        """updateFluidInteraction: the fluids' heights over the box 0.001 in, its eyes, a splash."""
        b = self.box()
        d = [b[0] + 0.001, b[1] + 0.001, b[2] + 0.001, b[3] - 0.001, b[4] - 0.001, b[5] - 0.001]
        heights = {"water": 0.0, "lava": 0.0}
        eyes = False
        eye_x, eye_z = math.floor(self.x), math.floor(self.z)
        eye_y = self.y + self.eyes
        for x in range(math.floor(d[0]), math.ceil(d[3])):
            for y in range(math.floor(d[1]), math.ceil(d[4])):
                for z in range(math.floor(d[2]), math.ceil(d[5])):
                    kind = FLUID.get(self.w.block(x, y, z))
                    if kind is None:
                        continue
                    top = y + self.fluid_height(x, y, z, kind)
                    if top < d[1]:
                        continue
                    if x == eye_x and z == eye_z and eye_y >= y and eye_y <= top and kind == "water":
                        eyes = True
                    heights[kind] = max(top - b[1], heights[kind])
        self.water, self.lava = heights["water"], heights["lava"]
        self.water_eyes = eyes
        wet = self.water > 0.0
        if wet:
            self.fall = 0.0
            if not self.in_water and not self.first_tick:
                fast = f32(math.sqrt(self.vx * self.vx * f32(0.2) + self.vy * self.vy + self.vz * self.vz * f32(0.2)))
                volume = min(1.0, f32(fast * f32(0.2)))
                a = self.random.next_float()
                c = self.random.next_float()
                self.play("entity.generic.splash", volume, f32(1.0 + f32(f32(a - c) * f32(0.4))))
                n = math.ceil(f32(1.0 + f32(self.width * 20.0)))
                for _ in range(n * 5):
                    self.random.next_double()
                self.splash += 1
        self.in_water = wet

    def on_pos(self, offset):
        return (math.floor(self.x), math.floor(self.y - offset), math.floor(self.z))

    def climbable(self):
        return self.w.block(math.floor(self.x), math.floor(self.y), math.floor(self.z)) in CLIMBABLE

    def colliders(self, b):
        """Whether a whole block's shape meets the box: the floor only, in these cases."""
        return b[1] < 1.0 and b[4] > 0.0

    def move(self, dx, dy, dz):
        """Entity.move by dx, dy, dz, with a living entity's checkFallDamage and steps."""
        mx, my, mz = dx, dy, dz
        asked = dx * dx + dy * dy + dz * dz
        if asked != 0.0:
            b = self.box()
            swept = [b[0] + min(dx, 0), b[1] + min(dy, 0), b[2] + min(dz, 0), b[3] + max(dx, 0), b[4] + max(dy, 0), b[5] + max(dz, 0)]
            if self.colliders(swept):
                if dy != 0.0:
                    my = 0.0 if abs(dy) < 1.0e-7 else max(dy, 1.0 - b[1])
                z_first = abs(dx) < abs(dz)
                if z_first and dz != 0.0 and abs(dz) < 1.0e-7:
                    mz = 0.0
                if dx != 0.0 and abs(dx) < 1.0e-7:
                    mx = 0.0
                if not z_first and dz != 0.0 and abs(dz) < 1.0e-7:
                    mz = 0.0
        length = mx * mx + my * my + mz * mz
        if length > 1.0e-7 or asked - length < 1.0e-7:
            self.x, self.y, self.z = self.x + mx, self.y + my, self.z + mz
        x_hit = not abs(mx - dx) < f32(1.0e-5)
        z_hit = not abs(mz - dz) < f32(1.0e-5)
        self.hc = x_hit or z_hit
        self.vc = dy != my
        self.below = self.vc and dy < 0.0
        self.on_ground = self.below
        effect = self.on_pos(f32(0.2))
        effect_block = self.w.block(*effect)
        # LivingEntity.checkFallDamage.
        if not self.in_water:
            self.update_fluids()
        if self.on_ground and self.fall > 0.0:
            power = max(0, math.floor(self.fall + 1.0e-6 - 3.0))
            if power > 0 and effect_block != "air":
                scale = min(f32(0.2) + power / 15.0, 2.5)
                self.dust.append((self.tick_count, effect_block, bits(self.x), bits(self.y), bits(self.z), int(150.0 * scale)))
        if not self.in_water and my < 0.0:
            self.fall -= f32(my)
        if self.on_ground:
            if self.fall > 0.0:
                self.fall_on(effect_block, self.fall)
            self.fall = 0.0
        # restituteMovementAfterCollisions, nothing here bouncing.
        cy = self.vy
        if (abs(dy) > 0.0 and self.vc) or self.hc:
            if x_hit:
                self.vx = -self.vx * 0.0
            if z_hit:
                self.vz = -self.vz * 0.0
            if self.vc:
                self.vy = (0.0 - cy) * 1.0 * 0.0
        self.emit(mx, my, mz, effect, effect_block)
        # The block's speed factor, 1 for all of these.
        self.vx, self.vy, self.vz = self.vx * 1.0, self.vy * 1.0, self.vz * 1.0

    def fall_on(self, block, fell):
        damage = math.floor((fell + 1.0e-6 - 3.0) * 1.0 * 1.0)
        if damage > 0:
            self.play("entity.armor_stand.fall", 1.0, 1.0)
            below = self.w.block(math.floor(self.x), math.floor(self.y - f32(0.2)), math.floor(self.z))
            if below != "air":
                self.play(SOUNDS[below] + ".fall", f32(1.0 * f32(0.5)), f32(1.0 * f32(0.75)))

    def emit(self, mx, my, mz, effect, effect_block):
        gone = f32(math.sqrt(mx * mx + my * my + mz * mz) * f32(0.6))
        across = f32(math.sqrt(mx * mx + mz * mz) * f32(0.6))
        standing_pos = self.on_pos(f32(1.0e-5))
        standing = self.w.block(*standing_pos)
        climbing = standing in CLIMBABLE
        self.move_dist = f32(self.move_dist + (gone if climbing else across))
        if not self.move_dist > self.next_step or standing == "air":
            return
        stepped = self.step_on(effect_block, True)
        if standing_pos != effect:
            stepped = self.step_on(standing, False) or stepped
        if stepped:
            self.next_step = float(int(self.move_dist) + 1)
        elif self.in_water:
            self.next_step = float(int(self.move_dist) + 1)
            fast = f32(f32(math.sqrt(self.vx * self.vx * f32(0.2) + self.vy * self.vy + self.vz * self.vz * f32(0.2))) * f32(0.35))
            a = self.random.next_float()
            c = self.random.next_float()
            self.play("entity.generic.swim", min(1.0, fast), f32(1.0 + f32(f32(a - c) * f32(0.4))))

    def step_on(self, block, heard):
        if block == "air":
            return False
        if not (self.on_ground or block in CLIMBABLE):
            return False
        if heard:
            self.play(SOUNDS[block] + ".step", f32(1.0 * f32(0.15)), 1.0)
        return True

    def move_relative(self, speed):
        ix, iy, iz = 0.0, 0.0, f32(self.zza)
        length = ix * ix + iy * iy + iz * iz
        if length < 1.0e-7:
            ax = ay = az = 0.0
        else:
            if length > 1.0:
                d = math.sqrt(length)
                ix, iy, iz = ix / d, iy / d, iz / d
            mx, my, mz = ix * speed, iy * speed, iz * speed
            turn = f32(self.yrot * f32(math.pi / 180.0))
            s, c = mth_sin(turn), mth_cos(turn)
            ax, ay, az = mx * c - mz * s, my, mz * c + mx * s
        self.vx, self.vy, self.vz = self.vx + ax, self.vy + ay, self.vz + az

    def jump(self):
        lava = self.in_lava()
        height = self.lava if lava else self.water
        wet = self.in_water and height > 0.0
        threshold = 0.0 if self.eyes < 0.4 else 0.4
        if not wet or (self.on_ground and not height > threshold):
            if not lava or (self.on_ground and self.lava <= threshold):
                if (self.on_ground or (wet and height <= threshold)) and self.no_jump_delay == 0:
                    power = f32(f32(f32(0.41999998688697815) * 1.0) * 1.0)
                    if not power <= f32(1.0e-5):
                        self.vy = max(power, self.vy)
                    self.no_jump_delay = 10
            else:
                self.vy += f32(0.04)
        else:
            self.vy += f32(0.04)

    def travel(self):
        if self.in_water or self.in_lava():
            falling = self.vy <= 0.0
            g = self.gravity
            if self.in_water:
                slow = f32(0.8)
                self.move_relative(f32(0.02))
                self.move(self.vx, self.vy, self.vz)
                mx, my, mz = self.vx, self.vy, self.vz
                if self.hc and self.climbable():
                    my = 0.2
                mx, my, mz = mx * slow, my * f32(0.8), mz * slow
                self.vx, self.vy, self.vz = mx, self.fluid_falling(g, falling, my), mz
            else:
                self.move_relative(f32(0.02))
                self.move(self.vx, self.vy, self.vz)
                if self.lava <= (0.0 if self.eyes < 0.4 else 0.4):
                    self.vx, self.vy, self.vz = self.vx * 0.5, self.fluid_falling(g, falling, self.vy * f32(0.8)), self.vz * 0.5
                else:
                    self.vx, self.vy, self.vz = self.vx * 0.5, self.vy * 0.5, self.vz * 0.5
                self.vx, self.vy, self.vz = self.vx + 0.0, self.vy + -g / 4.0, self.vz + 0.0
            # jumpOutOfFluid: nothing across to be pushed against here.
            assert not self.hc
            return
        below = self.on_pos(f32(0.500001))
        friction = cmf(FRICTION.get(self.w.block(*below), f32(0.6)), 1.0) if self.on_ground else 1.0
        if self.on_ground:
            walk = f32(self.speed * f32(f32(0.21600002) / f32(f32(friction * friction) * friction))) if friction > 0.6 else self.speed
        else:
            walk = f32(0.02)
        self.move_relative(walk)
        if self.climbable():
            self.fall = 0.0
            most = f32(0.15)
            self.vx = min(max(self.vx, -most), most)
            self.vz = min(max(self.vz, -most), most)
            self.vy = max(self.vy, -most)
        self.move(self.vx, self.vy, self.vz)
        mx, my, mz = self.vx, self.vy, self.vz
        if (self.hc or self.jumping) and self.climbable():
            my = 0.2
        my -= self.gravity
        air = cmf(f32(0.91), 1.0)
        across = f32(friction * air)
        up = cmf(f32(0.98), 1.0)
        self.vx, self.vy, self.vz = mx * across, my * up, mz * across

    @staticmethod
    def fluid_falling(g, falling, y):
        if g == 0.0:
            return y
        if falling and abs(y - 0.005) >= 0.003 and abs(y - g / 16.0) < 0.003:
            return -0.003
        return y - g / 16.0

    def tick(self):
        """tickNonPassenger and ArmorStand's tick, with physics."""
        self.tick_count += 1
        # baseTick.
        self.update_fluids()
        if self.in_lava():
            self.fall *= 0.5
        self.first_tick = False
        # aiStep.
        if self.no_jump_delay > 0:
            self.no_jump_delay -= 1
        if abs(self.vx) < 0.003:
            self.vx = 0.0
        if abs(self.vz) < 0.003:
            self.vz = 0.0
        if abs(self.vy) < 0.003:
            self.vy = 0.0
        self.zza = f32(self.zza * f32(0.98))
        if self.jumping:
            self.jump()
        else:
            self.no_jump_delay = 0
        self.travel()

    def state(self):
        return [bits(self.x), bits(self.y), bits(self.z), bits(self.vx), bits(self.vy), bits(self.vz), 1 if self.on_ground else 0]


def run(name, e, ticks, checked, before=None):
    rows = []
    for t in range(1, ticks + 1):
        if before:
            before(e)
        e.tick()
        if t in checked:
            rows.append([t] + e.state())
    print(f"== {name}")
    for r in rows:
        print("        " + ", ".join(str(v) for v in r) + ",")
    print(f"   sounds: {e.sounds}")
    print(f"   dust: {e.dust}")
    print(f"   x {e.x} y {e.y} z {e.z} v {e.vx} {e.vy} {e.vz} ground {e.on_ground} fall {e.fall} splashes {e.splash}")


def main():
    e = Living(World(), 155, 0.5, 10.0, 0.5)
    print(f"== made: y rot bits {float_bits(e.yrot)}")
    run("falling", e, 40, {1, 5, 10, 13, 14, 15, 20, 40})

    e = Living(World("ice"), 156, 0.5, 1.0, 0.5)
    e.on_ground = True
    e.vx = 0.6
    run("ice", e, 60, {1, 2, 10, 30, 60})

    e = Living(World(ladder=True), 157, 0.5, 8.0, 0.5)
    run("ladder", e, 70, {1, 2, 5, 10, 30, 47, 48, 49, 50, 70})

    e = Living(World(fluid="water"), 158, 0.5, 6.0, 0.5)
    run("water", e, 80, {1, 5, 10, 15, 20, 40, 80})

    e = Living(World(fluid="lava"), 159, 0.5, 5.0, 0.5)
    run("lava", e, 60, {1, 5, 10, 20, 40, 60})

    e = Living(World(), 160, 0.5, 1.0, 0.5)
    e.yrot = 30.0
    e.on_ground = True
    e.speed = f32(0.1)
    e.jumping = True

    def forward(w):
        w.zza = 1.0

    run("walker", e, 40, {1, 2, 5, 10, 11, 12, 20, 40}, forward)


if __name__ == "__main__":
    main()
