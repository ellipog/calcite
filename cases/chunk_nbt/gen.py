"""Writes cases/chunk_nbt/generated.json: chunks' NBT, as SNBT, read and written back as vanilla's
SerializableChunkData reads and writes a chunk it loads from its region file and saves again.

    py -I cases/chunk_nbt/gen.py

Deterministic: sections' palettes and data come from the runner's SplitMix64 generator, seeded
here, so rerunning it gives the same file.

The cases cover each field the chunk keeps, written well and badly: the status, the position and
times, the sections' block states and biomes by name and properties, packed in every size a
palette comes in and in sizes the palette doesn't need, light, heightmaps, scheduled ticks,
post-processing, entities, block entities, structures, and the upgrade, blending and retrogen data
of chunks from older versions.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
from cases import splitmix64, write_file  # noqa: E402

SEED = 20261029
OVERWORLD = (-64, 24)
NETHER = (0, 16)

# States written as vanilla writes them: a default state as its block's name, any other as its
# block's name and its properties, every one, in name order.
STATES = [
    '"minecraft:air"', '"minecraft:stone"', '"minecraft:granite"', '"minecraft:dirt"',
    '"minecraft:grass_block"', '{id:"minecraft:grass_block",properties:{snowy:"true"}}',
    '"minecraft:oak_log"', '{id:"minecraft:oak_log",properties:{axis:"x"}}',
    '{id:"minecraft:oak_log",properties:{axis:"z"}}', '"minecraft:oak_leaves"',
    '{id:"minecraft:oak_leaves",properties:{distance:"1",persistent:"true",waterlogged:"false"}}',
    '"minecraft:water"', '{id:"minecraft:water",properties:{level:"8"}}', '"minecraft:lava"',
    '{id:"minecraft:wheat",properties:{age:"7"}}', '"minecraft:wheat"', '"minecraft:bedrock"',
    '"minecraft:deepslate"', '"minecraft:diamond_ore"', '"minecraft:cave_air"', '"minecraft:oak_planks"',
    '"minecraft:torch"', '{id:"minecraft:wall_torch",properties:{facing:"east"}}', '"minecraft:glass"',
    '{id:"minecraft:oak_slab",properties:{type:"top",waterlogged:"true"}}', '"minecraft:sand"',
    '"minecraft:gravel"', '"minecraft:cobblestone"', '{id:"minecraft:snow",properties:{layers:"4"}}',
    '{id:"minecraft:oak_stairs",properties:{facing:"west",half:"top",shape:"outer_left",waterlogged:"false"}}',
    '{id:"minecraft:redstone_wire",properties:{east:"side",north:"up",power:"15",south:"none",west:"none"}}',
    '{id:"minecraft:chest",properties:{facing:"south",type:"left",waterlogged:"false"}}', '"minecraft:short_grass"',
    '{id:"minecraft:kelp",properties:{age:"25"}}', '"minecraft:coal_ore"', '"minecraft:iron_ore"',
]
BIOMES = ['"minecraft:plains"', '"minecraft:forest"', '"minecraft:desert"', '"minecraft:ocean"',
          '"minecraft:river"', '"minecraft:taiga"', '"minecraft:swamp"', '"minecraft:jungle"',
          '"minecraft:savanna"', '"minecraft:badlands"', '"minecraft:dripstone_caves"',
          '"minecraft:lush_caves"', '"minecraft:deep_dark"', '"minecraft:beach"', '"minecraft:snowy_plains"',
          '"minecraft:mushroom_fields"', '"minecraft:cherry_grove"', '"minecraft:meadow"']


class Draws:
    def __init__(self, seed):
        self.rand = splitmix64(seed)

    def below(self, n):
        return next(self.rand) % n


def ceil_log2(n):
    return (n - 1).bit_length() if n > 1 else 0


def pack(values, bits):
    """Values of `bits` bits each in longs, as many whole ones in each as fit, from the low bits."""
    per = 64 // bits
    longs = []
    for start in range(0, len(values), per):
        v = 0
        for j, x in enumerate(values[start:start + per]):
            v |= x << (j * bits)
        if v >= 1 << 63:
            v -= 1 << 64
        longs.append(v)
    return longs


def longs(values):
    return "[L;" + ",".join(f"{v}L" for v in values) + "]"


def container(palette, data=None):
    out = "palette:[" + ",".join(palette) + "]"
    if data is not None:
        out += ",data:" + data
    return "{" + out + "}"


def block_bits(n):
    if n <= 1:
        return 0
    return max(4, ceil_log2(n)) if n <= 256 else ceil_log2(n)


def biome_bits(n):
    return ceil_log2(n)


def random_container(g, choices, n, size, bits_of, used=None):
    """A container of `size` values drawn from the first `n` of `choices`, or `used` of them."""
    palette = choices[:n]
    used = used or n
    values = [g.below(used) for _ in range(size)]
    bits = bits_of(n)
    if bits == 0:
        return container(palette)
    return container(palette, longs(pack(values, bits)))


def chunk(status='"minecraft:full"', x=0, z=0, sections=None, extra=""):
    out = f"DataVersion:5023,xPos:{x},yPos:-4,zPos:{z},LastUpdate:1234L,InhabitedTime:56L,Status:{status}"
    if sections is not None:
        out += ",sections:[" + ",".join(sections) + "]"
    if extra:
        out += "," + extra
    return "{" + out + "}"


def section(y, blocks=None, biomes=None, extra=""):
    parts = []
    if blocks is not None:
        parts.append("block_states:" + blocks)
    if biomes is not None:
        parts.append("biomes:" + biomes)
    if extra:
        parts.append(extra)
    parts.append(f"Y:{y}b")
    return "{" + ",".join(parts) + "}"


def case(name, snbt, height=OVERWORLD):
    return {"id": name, "input": {"min_y": height[0], "sections": height[1], "snbt": snbt}}


STONE = container(['"minecraft:stone"'])
PLAINS = container(['"minecraft:plains"'])


def basics():
    out = [
        case("no-status", "{xPos:1,zPos:2}"),
        case("empty-status", '{Status:""}'),
        case("status-not-string", "{Status:5}"),
        case("minimal", '{Status:"minecraft:full"}'),
        case("unknown-status", '{Status:"minecraft:nope"}'),
        case("bad-status-name", '{Status:"Not A Status"}'),
        case("short-status-name", '{Status:"features"}'),
        case("status-terrain", '{Status:"minecraft:terrain"}'),
        case("status-upper-case", '{Status:"minecraft:FULL"}'),
        case("status-other-namespace", '{Status:"calcite:full"}'),
        case("everything-empty", chunk()),
    ]
    for status in ["empty", "structure_starts", "structure_references", "biomes", "noise", "surface",
                   "carvers", "features", "initialize_light", "light", "spawn", "full"]:
        out.append(case(f"status-{status}", chunk(f'"minecraft:{status}"', extra='entities:[{id:"minecraft:pig"}]')))
    out += [
        case("position", chunk(x=-31, z=1000000)),
        case("position-not-int", '{Status:"minecraft:full",xPos:"3",zPos:2.5d}'),
        case("position-byte", '{Status:"minecraft:full",xPos:3b,zPos:-2s}'),
        case("position-long", '{Status:"minecraft:full",xPos:4294967297L,zPos:-1L}'),
        case("times-as-ints", '{Status:"minecraft:full",LastUpdate:5,InhabitedTime:7b}'),
        case("times-as-doubles", '{Status:"minecraft:full",LastUpdate:5.9d,InhabitedTime:-7.5f}'),
        case("times-negative-fractions", '{Status:"minecraft:full",LastUpdate:-7.5d,InhabitedTime:-7.5f,xPos:-1.5d,zPos:-0.5f}'),
        case("times-huge-doubles", '{Status:"minecraft:full",LastUpdate:1.0e30d,InhabitedTime:-1.0e30f,xPos:1.0e30d,zPos:-1.0e30f}'),
        case("times-as-strings", '{Status:"minecraft:full",LastUpdate:"5",InhabitedTime:[I;1]}'),
        case("data-version-old", '{DataVersion:100,Status:"minecraft:full"}'),
        case("y-pos-wrong", '{yPos:7,Status:"minecraft:full"}'),
        case("light-on", '{Status:"minecraft:full",isLightOn:1b}'),
        case("light-off", '{Status:"minecraft:full",isLightOn:0b}'),
        case("light-five", '{Status:"minecraft:full",isLightOn:5b}'),
        case("light-256", '{Status:"minecraft:full",isLightOn:256}'),
        case("light-half", '{Status:"minecraft:full",isLightOn:0.5d}'),
        case("light-minus-half", '{Status:"minecraft:full",isLightOn:-0.5d}'),
        case("light-int", '{Status:"minecraft:full",isLightOn:1}'),
        case("light-string", '{Status:"minecraft:full",isLightOn:"true"}'),
        case("unknown-keys", '{Status:"minecraft:full",foo:1,Level:{bar:2},CarvingMasks:{}}'),
    ]
    return out


def sections():
    s = lambda *a, **k: [section(*a, **k)]
    out = [
        case("one-stone-section", chunk(sections=s(0, STONE, PLAINS))),
        case("section-without-containers", chunk(sections=s(0))),
        case("section-blocks-only", chunk(sections=s(1, STONE))),
        case("section-biomes-only", chunk(sections=s(1, None, container(['"minecraft:desert"'])))),
        case("section-y-missing", chunk(sections=["{block_states:" + STONE + "}"])),
        case("section-y-int", chunk(sections=["{block_states:" + STONE + ",Y:3}"])),
        case("section-y-below", chunk(sections=s(-5, STONE, PLAINS))),
        case("section-y-above", chunk(sections=s(20, STONE, PLAINS))),
        case("section-y-top", chunk(sections=s(19, STONE, PLAINS))),
        case("section-y-bottom", chunk(sections=s(-4, STONE, PLAINS))),
        case("section-y-below-light", chunk(sections=s(-5, STONE, PLAINS, "SkyLight:[B;" + ",".join(["17b"] * 2048) + "]"))),
        case("section-y-far-below", chunk(sections=["{block_states:" + STONE + ",Y:-56b}"])),
        case("section-y-int-wraps", chunk(sections=["{block_states:" + STONE + ",Y:200}"])),
        case("section-y-int-wraps-in", chunk(sections=["{block_states:" + STONE + ",Y:258}"])),
        case("section-y-double", chunk(sections=["{block_states:" + STONE + ",Y:1.9d}", "{block_states:" + STONE + ",Y:-0.5f}"])),
        case("section-y-string", chunk(sections=["{block_states:" + STONE + ",Y:\"3\"}"])),
        case("sections-twice", chunk(sections=[section(0, STONE), section(0, container(['"minecraft:dirt"']))])),
        case("sections-out-of-order", chunk(sections=[section(5, STONE), section(-2, STONE), section(1, None, PLAINS)])),
        case("sections-not-list", chunk(extra="sections:{a:1}")),
        case("sections-of-ints", chunk(extra="sections:[1,2,3]")),
        case("sections-mixed", chunk(extra="sections:[[],{Y:1b,block_states:" + STONE + "}]")),
        case("nether-section-negative", chunk(sections=s(-1, STONE, PLAINS)), NETHER),
        case("nether-sections", chunk(sections=[section(y, STONE, PLAINS) for y in range(16)]), NETHER),
        case("one-section-world", chunk(sections=[section(1, STONE, PLAINS), section(2, STONE)]), (16, 1)),
        case("light-only", chunk(sections=s(3, None, None, "BlockLight:[B;" + ",".join(["1b"] * 2048) + "]"))),
        case("light-both", chunk(sections=s(3, STONE, PLAINS, "BlockLight:[B;" + ",".join(["-1b"] * 2048) + "],SkyLight:[B;" + ",".join([f"{i % 100}b" for i in range(2048)]) + "]"))),
        case("light-short", chunk(sections=s(3, STONE, PLAINS, "BlockLight:[B;1b,2b,3b]"))),
        case("light-long", chunk(sections=s(3, STONE, PLAINS, "SkyLight:[B;" + ",".join(["0b"] * 2049) + "]"))),
        case("light-empty", chunk(sections=s(3, STONE, PLAINS, "SkyLight:[B;]"))),
        case("light-not-bytes", chunk(sections=s(3, STONE, PLAINS, "SkyLight:[I;1,2],BlockLight:\"x\""))),
        case("light-list-of-bytes", chunk(sections=s(3, STONE, PLAINS, "SkyLight:[" + ",".join(["1b"] * 2048) + "]"))),
    ]
    return out


def palettes():
    one = lambda name, blocks, biomes=PLAINS: case(name, chunk(sections=[section(0, blocks, biomes)]))
    out = [
        case("bad-index-then-bad-section", chunk(sections=[section(0, container(['"minecraft:stone"', '"minecraft:dirt"'], longs(pack([0, 5] * 2048, 4))), PLAINS), section(1, container(['"minecraft:nope"']), PLAINS)])),
        case("bad-biome-index-then-bad-section", chunk(sections=[section(0, STONE, container(BIOMES[:3], longs(pack([3] * 64, 2)))), section(1, container(['"minecraft:nope"']), PLAINS), section(2, STONE, PLAINS, "BlockLight:[B;1b]")])),
        case("bad-light-after-logged-error", chunk(sections=[section(0, container(['"minecraft:nope"']), container(['"minecraft:nope"']), "BlockLight:[B;1b]")])),
        case("light-checked-outside-world", chunk(sections=[section(-10, STONE, PLAINS, "BlockLight:[B;1b]")])),
        one("palette-missing", "{}"),
        one("palette-missing-with-data", "{data:[L;1L]}"),
        one("palette-not-list", "{palette:5}"),
        one("palette-empty", "{palette:[]}"),
        one("palette-empty-with-data", "{palette:[],data:[L;0L]}"),
        one("palette-unknown-name", container(['"minecraft:nope"'])),
        one("palette-bad-name", container(['"Not A Block"'])),
        one("palette-no-namespace", container(['"stone"'])),
        one("palette-other-namespace", container(['"other:stone"'])),
        one("palette-int", container(["5"])),
        one("palette-list", container(["[]"])),
        one("palette-no-id", container(['{properties:{axis:"x"}}'])),
        one("palette-empty-compound", container(["{}"])),
        one("palette-unknown-id", container(['{id:"minecraft:nope"}'])),
        one("palette-bad-id", container(['{id:"Not A Block"}'])),
        one("palette-id-int", container(["{id:5}"])),
        one("palette-name-key", container(['{Name:"minecraft:oak_log",Properties:{axis:"x"}}'])),
        one("palette-default-written-out", container(['{id:"minecraft:oak_log",properties:{axis:"y"}}'])),
        one("palette-id-alone", container(['{id:"minecraft:oak_log"}'])),
        one("palette-id-alone-singleton", container(['{id:"minecraft:stone"}'])),
        one("palette-singleton-properties", container(['{id:"minecraft:stone",properties:{axis:"x"}}'])),
        one("palette-singleton-properties-int", container(['{id:"minecraft:stone",properties:5}'])),
        one("palette-bad-value", container(['{id:"minecraft:oak_log",properties:{axis:"w"}}'])),
        one("palette-unknown-property", container(['{id:"minecraft:oak_log",properties:{facing:"x"}}'])),
        one("palette-value-int", container(['{id:"minecraft:wheat",properties:{age:3}}'])),
        one("palette-value-byte-bool", container(['{id:"minecraft:grass_block",properties:{snowy:1b}}'])),
        one("palette-properties-int", container(['{id:"minecraft:oak_log",properties:5}'])),
        one("palette-properties-list", container(['{id:"minecraft:oak_log",properties:[]}'])),
        one("palette-some-properties", container(['{id:"minecraft:oak_stairs",properties:{half:"top",shape:"inner_left"}}'])),
        one("palette-some-bad-properties", container(['{id:"minecraft:oak_stairs",properties:{half:"middle",shape:"inner_left",facing:"up"}}'])),
        one("palette-extra-keys", container(['{id:"minecraft:oak_log",properties:{axis:"x"},foo:1}'])),
        one("palette-upper-case-value", container(['{id:"minecraft:oak_log",properties:{axis:"X"}}'])),
        one("palette-two-bad", container(['"minecraft:nope"', '"minecraft:stone"', "7"]), ),
        one("palette-three-bad", container(['"minecraft:nope"', "7", "{}", '"minecraft:dirt"'], longs(pack([0, 1, 2, 3] * 1024, 4)))),
        one("palette-names", container(['"Minecraft:stone"', '":stone"', '"minecraft:"', '"a:b:c"', '""', '"minecraft:stone "'], longs(pack([0, 1, 2, 3, 4, 5] * 682 + [0] * 4, 4)))),
        one("palette-int-array", "{palette:[I;1,2],data:" + longs(pack([0, 1] * 2048, 4)) + "}"),
        one("palette-mixed-list", container(['"minecraft:stone"', '{id:"minecraft:oak_log",properties:{axis:"x"}}', "5"], longs(pack([0, 1, 2] * 1365 + [0], 4)))),
        one("palette-property-order", container(['{id:"minecraft:oak_stairs",properties:{half:"top"}}', '{id:"minecraft:powered_rail",properties:{powered:"true"}}', '{id:"minecraft:piston_head",properties:{short:"true",facing:"up"}}'], longs(pack([0, 1, 2, 0] * 1024, 4)))),
        one("palette-all-bad-to-air", container(['"minecraft:nope"', '"minecraft:nada"'], longs(pack([0, 1] * 2048, 4)))),
        one("palette-index-past-end-many", container(['"minecraft:stone"', '"minecraft:dirt"'], longs(pack([0, 9, 1, 5, 3, 14, 7, 12] * 512, 4)))),
        one("palette-index-past-end-17", container(STATES[:17], longs(pack(list(range(17)) * 240 + [31, 20, 25, 18] * 4, 5)))),
        one("palette-index-past-end-global", container(STATES[:1] * 257, longs(pack([0, 300, 1, 511, 257] * 819 + [0], 9)))),
        one("biomes-index-past-end", STONE, container(BIOMES[:3], longs(pack([0, 1, 3, 2] * 16, 2)))),
        one("biomes-index-past-end-global", STONE, container(BIOMES[:9], longs(pack([0, 15, 1, 9] * 16, 4)))),
        one("biomes-empty-palette", STONE, "{palette:[]}"),
        one("blocks-bad-index-and-bad-biome", container(['"minecraft:stone"', '"minecraft:dirt"'], longs(pack([0, 1, 2, 3] * 1024, 4))), container(['"minecraft:nope"'])),
        one("blocks-empty-and-bad-biome", "{palette:[]}", container(['"minecraft:nope"'])),
        one("palette-same-state-twice", container(['"minecraft:oak_log"', '{id:"minecraft:oak_log",properties:{axis:"y"}}'], longs(pack([0, 1] * 2048, 4)))),
        one("palette-two-no-data", container(['"minecraft:stone"', '"minecraft:dirt"'])),
        one("palette-two-data-short", container(['"minecraft:stone"', '"minecraft:dirt"'], "[L;1L,2L]")),
        one("palette-two-data-long", container(['"minecraft:stone"', '"minecraft:dirt"'], longs([0] * 257))),
        one("palette-two-data-empty", container(['"minecraft:stone"', '"minecraft:dirt"'], "[L;]")),
        one("palette-two-data-ints", container(['"minecraft:stone"', '"minecraft:dirt"'], "[I;" + ",".join(["1"] * 256) + "]")),
        one("palette-two-data-list", container(['"minecraft:stone"', '"minecraft:dirt"'], "[" + ",".join(["1L"] * 256) + "]")),
        one("palette-two-data-string", container(['"minecraft:stone"', '"minecraft:dirt"'], '"x"')),
        one("palette-one-with-data", container(['"minecraft:stone"'], longs([7] * 256))),
        one("palette-one-with-short-data", container(['"minecraft:stone"'], "[L;7L]")),
        one("palette-index-past-end", container(['"minecraft:stone"', '"minecraft:dirt"'], longs(pack([0, 1, 2, 15] * 1024, 4)))),
        one("palette-bits-5-for-2", container(['"minecraft:stone"', '"minecraft:dirt"'], longs(pack([0, 1] * 2048, 5)))),
        one("palette-unused-entries", container(['"minecraft:stone"', '"minecraft:dirt"', '"minecraft:sand"'], longs(pack([2, 0] * 2048, 4)))),
        one("palette-all-one-value", container(['"minecraft:stone"', '"minecraft:dirt"'], longs(pack([1] * 4096, 4)))),
        one("biomes-missing-palette", STONE, "{}"),
        one("biomes-unknown", STONE, container(['"minecraft:nope"'])),
        one("biomes-bad-name", STONE, container(['"Nope Nope"'])),
        one("biomes-compound", STONE, container(['{id:"minecraft:plains"}'])),
        one("biomes-int", STONE, container(["3"])),
        one("biomes-two-no-data", STONE, container(['"minecraft:plains"', '"minecraft:desert"'])),
        one("biomes-two", STONE, container(['"minecraft:plains"', '"minecraft:desert"'], longs(pack([1, 0, 0, 1] * 16, 1)))),
        one("biomes-two-bits-4", STONE, container(['"minecraft:plains"', '"minecraft:desert"'], longs(pack([1, 0, 0, 1] * 16, 4)))),
        one("biomes-short-data", STONE, container(['"minecraft:plains"', '"minecraft:desert"'], "[L;]")),
        one("blocks-and-biomes-bad", container(['"minecraft:nope"']), container(['"minecraft:nope"'])),
        one("blocks-bad-and-short", container(['"minecraft:nope"', '"minecraft:stone"'], "[L;1L]")),
    ]
    g = Draws(SEED)
    for n in [2, 3, 4, 5, 8, 9, 15, 16, 17, 20, 31, 32, 33, 36]:
        n = min(n, len(STATES))
        out.append(one(f"blocks-{n}", random_container(g, STATES, n, 4096, block_bits)))
    out.append(one("blocks-36-using-3", random_container(g, STATES, 36, 4096, block_bits, 3)))
    out.append(one("blocks-17-using-16", random_container(g, STATES, 17, 4096, block_bits, 16)))
    out.append(one("blocks-5-using-1", random_container(g, STATES, 5, 4096, block_bits, 1)))
    for n in [2, 3, 4, 5, 8, 9, 13, 18]:
        out.append(one(f"biomes-{n}", STONE, random_container(g, BIOMES, n, 64, biome_bits)))
    out.append(one("biomes-9-using-2", STONE, random_container(g, BIOMES, 9, 64, biome_bits, 2)))
    out.append(one("biomes-4-using-1", STONE, random_container(g, BIOMES, 4, 64, biome_bits, 1)))
    # More than 256 states, which take the registry's IDs: every age of every crop and every
    # stair, spelled out.
    many = []
    for facing in ["north", "south", "west", "east"]:
        for half in ["top", "bottom"]:
            for shape in ["straight", "inner_left", "inner_right", "outer_left", "outer_right"]:
                for wl in ["true", "false"]:
                    for stair in ["oak_stairs", "stone_stairs", "spruce_stairs", "birch_stairs"]:
                        many.append(f'{{id:"minecraft:{stair}",properties:{{facing:"{facing}",half:"{half}",shape:"{shape}",waterlogged:"{wl}"}}}}')
    for n in [257, 300, 320]:
        out.append(one(f"blocks-global-{n}", random_container(g, many, n, 4096, block_bits)))
    out.append(one("blocks-global-300-using-200", random_container(g, many, 300, 4096, block_bits, 200)))
    out.append(one("blocks-global-300-using-2", random_container(g, many, 300, 4096, block_bits, 2)))
    return out


def ticks():
    tick = lambda i, x, y, z, t=1, p=0: f'{{i:"{i}",x:{x},y:{y},z:{z},t:{t},p:{p}}}'
    return [
        case("block-ticks", chunk(extra="block_ticks:[" + tick("minecraft:water", 1, 64, 2) + "," + tick("minecraft:stone", 15, -64, 15, 20, -3) + "]")),
        case("fluid-ticks", chunk(extra="fluid_ticks:[" + tick("minecraft:water", 1, 64, 2, 5, 3) + "," + tick("minecraft:flowing_lava", 0, 0, 0) + "]")),
        case("ticks-outside-chunk", chunk(x=2, z=-1, extra="block_ticks:[" + tick("minecraft:stone", 32, 0, -16) + "," + tick("minecraft:stone", 47, 0, -1) + "," + tick("minecraft:stone", 48, 0, -1) + "," + tick("minecraft:stone", 40, 0, -17) + "]")),
        case("ticks-unknown-block", chunk(extra="block_ticks:[" + tick("minecraft:nope", 1, 2, 3) + "," + tick("minecraft:stone", 1, 2, 3) + "]")),
        case("ticks-missing-field", chunk(extra='block_ticks:[{i:"minecraft:stone",x:1,y:2,t:1,p:0},{i:"minecraft:dirt",x:1,y:2,z:3,t:1,p:0}]')),
        case("ticks-no-priority", chunk(extra='block_ticks:[{i:"minecraft:stone",x:1,y:2,z:3,t:1}]')),
        case("ticks-priority-far", chunk(extra="block_ticks:[" + tick("minecraft:stone", 1, 2, 3, 1, 9) + "," + tick("minecraft:stone", 1, 2, 3, 1, -9) + "]")),
        case("ticks-same-twice", chunk(extra="block_ticks:[" + tick("minecraft:stone", 1, 2, 3) + "," + tick("minecraft:stone", 1, 2, 3, 7) + "]")),
        case("ticks-bad-types", chunk(extra='block_ticks:[{i:"minecraft:stone",x:1b,y:2s,z:3L,t:1.5d,p:0b}]')),
        case("ticks-not-list", chunk(extra='block_ticks:{i:"minecraft:stone"},fluid_ticks:5')),
        case("ticks-list-of-ints", chunk(extra="block_ticks:[1,2]")),
        case("ticks-fluid-as-block", chunk(extra="fluid_ticks:[" + tick("minecraft:stone", 1, 2, 3) + "]")),
        case("ticks-empty-compound", chunk(extra="block_ticks:[{}]")),
        case("ticks-all-bad", chunk(extra='block_ticks:[{i:5,x:"a",y:1,z:1,t:"b",p:"c"}]')),
        case("ticks-pos-missing", chunk(extra='block_ticks:[{i:"minecraft:stone",t:1,p:0}]')),
        case("ticks-x-and-t-missing", chunk(extra='block_ticks:[{i:"minecraft:nope",y:1,z:1,p:0}]')),
        case("ticks-three-bad", chunk(extra='block_ticks:[1,{},{i:"minecraft:nope",x:1,y:1,z:1,t:1,p:1}]')),
        case("ticks-number-kinds", chunk(extra='block_ticks:[{i:"minecraft:stone",x:1.9d,y:4294967297L,z:-0.5f,t:-1.5d,p:-1.5d},{i:"minecraft:stone",x:15.9f,y:-1.5d,z:2b,t:3s,p:2.9f}]')),
        case("ticks-huge", chunk(extra='block_ticks:[{i:"minecraft:stone",x:0,y:-1.0e30f,z:0,t:1.0e30d,p:-1.0e30d},{i:"minecraft:stone",x:0,y:1.0e30d,z:0,t:-9223372036854775808L,p:9223372036854775807L}]')),
        case("ticks-array-not-list", chunk(extra="block_ticks:[I;1,2]")),
        case("ticks-other-chunk-and-bad", chunk(extra='block_ticks:[{i:"minecraft:stone",x:100,y:1,z:1,t:1,p:0},{i:"minecraft:nope",x:1,y:1,z:1,t:1,p:0}]')),
        case("ticks-extra-keys", chunk(extra='block_ticks:[{i:"minecraft:stone",x:1,y:2,z:3,t:1,p:0,q:9}]')),
    ]


def others():
    return [
        case("heightmaps", chunk(extra="Heightmaps:{MOTION_BLOCKING:" + longs(range(37)) + ",WORLD_SURFACE:" + longs([5] * 37) + ",OCEAN_FLOOR_WG:[L;1L]}")),
        case("heightmaps-all", chunk(extra="Heightmaps:{" + ",".join(f"{k}:{longs([i] * 37)}" for i, k in enumerate(["WORLD_SURFACE_WG", "WORLD_SURFACE", "OCEAN_FLOOR_WG", "OCEAN_FLOOR", "MOTION_BLOCKING", "MOTION_BLOCKING_NO_LEAVES"])) + "}")),
        case("heightmaps-bad", chunk(extra='Heightmaps:{MOTION_BLOCKING:[I;1,2],WORLD_SURFACE:"x",LIGHT_BLOCKING:[L;1L],motion_blocking:[L;2L],OCEAN_FLOOR:[L;]}')),
        case("heightmaps-not-compound", chunk(extra="Heightmaps:[L;1L]")),
        case("post-processing", chunk(extra="PostProcessing:[[],[1s,2s,3s],[],[-1s],[]]")),
        case("post-processing-types", chunk(extra='PostProcessing:[[1b,2b],[1,2],[1L],["x"],[[1s]],[1.5d]]')),
        case("post-processing-not-lists", chunk(extra='PostProcessing:[1s,{a:1},"x",[5s]]')),
        case("post-processing-long", chunk(extra="PostProcessing:[" + ",".join(["[1s]"] * 30) + "]")),
        case("post-processing-int-array", chunk(extra="PostProcessing:[[I;1,2],[B;3b],[L;4L]]")),
        case("post-processing-negative-fractions", chunk(extra="PostProcessing:[[-1.5d,-0.5f,70000,1.0e30d]]")),
        case("post-processing-not-list", chunk(extra="PostProcessing:{a:[1s]}")),
        case("entities-full", chunk(extra='entities:[{id:"minecraft:pig",Pos:[1.0d,2.0d,3.0d]}]')),
        case("entities-proto", chunk('"minecraft:features"', extra='entities:[{id:"minecraft:pig"},5,{id:"minecraft:cow"}]')),
        case("entities-proto-not-list", chunk('"minecraft:features"', extra='entities:{id:"minecraft:pig"}')),
        case("block-entities", chunk(extra='block_entities:[{id:"minecraft:chest",x:1,y:2,z:3,Items:[]},{id:"minecraft:sign",x:0,y:0,z:0,keepPacked:1b}]')),
        case("block-entities-mixed", chunk(extra='block_entities:[{id:"minecraft:chest"},"x",[],{}]')),
        case("block-entities-not-list", chunk(extra='block_entities:{id:"minecraft:chest"}')),
        case("structures", chunk(extra='structures:{starts:{"minecraft:village_plains":{id:"INVALID"}},References:{"minecraft:mineshaft":[L;1L,2L]}}')),
        case("structures-not-compound", chunk(extra="structures:[1]")),
        case("structures-anything", chunk(extra="structures:{foo:1b,bar:{baz:[I;1]}}")),
        case("upgrade-data", chunk(extra="UpgradeData:{Indices:{\"0\":[I;1,2,3],\"5\":[I;4]},Sides:5b}")),
        case("upgrade-data-sides-only", chunk(extra="UpgradeData:{Sides:255}")),
        case("upgrade-data-sides-high", chunk(extra="UpgradeData:{Sides:256}")),
        case("upgrade-data-empty", chunk(extra="UpgradeData:{}")),
        case("upgrade-data-empty-index", chunk(extra="UpgradeData:{Indices:{\"0\":[I;]}}")),
        case("upgrade-data-index-past", chunk(extra="UpgradeData:{Indices:{\"24\":[I;1],\"23\":[I;2],\"-1\":[I;3],\"01\":[I;4]}}")),
        case("upgrade-data-ticks-only", chunk(extra='UpgradeData:{neighbor_block_ticks:[{i:"minecraft:stone",x:1,y:2,z:3,t:1,p:0}]}')),
        case("upgrade-data-ticks", chunk(extra='UpgradeData:{Sides:1b,neighbor_block_ticks:[{i:"minecraft:stone",x:100,y:2,z:3,t:1,p:0},{i:"minecraft:nope",x:1,y:2,z:3,t:1,p:0}],neighbor_fluid_ticks:[{i:"minecraft:water",x:1,y:2,z:3,t:1,p:5}]}')),
        case("upgrade-data-sides-double", chunk(extra="UpgradeData:{Sides:3.9d}")),
        case("upgrade-data-bad-ticks", chunk(extra='UpgradeData:{Sides:1b,neighbor_block_ticks:[{i:"minecraft:stone"}],neighbor_fluid_ticks:5}')),
        case("upgrade-data-some-bad-ticks", chunk(extra='UpgradeData:{Sides:1b,neighbor_block_ticks:[{i:"minecraft:nope",x:100,y:1,z:1,t:1,p:9},5,{i:"minecraft:stone",x:1,y:1,z:1,t:1,p:0}],neighbor_fluid_ticks:[{i:"minecraft:water",x:-1,y:1,z:1,t:1,p:0},{i:7,x:1,y:1,z:1,t:1,p:0}]}')),
        case("upgrade-data-not-compound", chunk(extra="UpgradeData:5")),
        case("upgrade-data-index-types", chunk(extra="UpgradeData:{Indices:{\"0\":[B;1b],\"1\":[L;1L],\"2\":[1,2]}}")),
        case("upgrade-data-nether", chunk(extra="UpgradeData:{Indices:{\"15\":[I;1],\"16\":[I;2]}}"), NETHER),
        case("blending-data", chunk(extra="blending_data:{min_section:-4,max_section:20}")),
        case("blending-data-heights", chunk(extra="blending_data:{min_section:-4,max_section:20,heights:[" + ",".join(f"{i}.5f" for i in range(16)) + "]}")),
        case("blending-data-heights-short", chunk(extra="blending_data:{min_section:-4,max_section:20,heights:[1.0f]}")),
        case("blending-data-heights-doubles", chunk(extra="blending_data:{min_section:0,max_section:1,heights:[" + ",".join(["1.0d"] * 16) + "]}")),
        case("blending-data-heights-bad", chunk(extra='blending_data:{min_section:0,max_section:1,heights:"x"}')),
        case("blending-data-missing", chunk(extra="blending_data:{min_section:-4}")),
        case("blending-data-not-compound", chunk(extra="blending_data:5")),
        case("blending-data-both-missing", chunk(extra="blending_data:{}")),
        case("blending-data-bad-types", chunk(extra='blending_data:{min_section:"a",max_section:1.5d}')),
        case("blending-data-heights-ints", chunk(extra="blending_data:{min_section:0,max_section:1,heights:[" + ",".join(str(i) for i in range(16)) + "]}")),
        case("blending-data-heights-mixed", chunk(extra='blending_data:{min_section:0,max_section:1,heights:[' + ",".join(["1.0f"] * 15) + ',"x"]}')),
        case("blending-data-heights-array", chunk(extra="blending_data:{min_section:0,max_section:1,heights:[I;" + ",".join(["2"] * 16) + "]}")),
        case("blending-data-short-and-missing", chunk(extra="blending_data:{min_section:0,heights:[1.0f]}")),
        case("blending-data-extra", chunk(extra="blending_data:{min_section:1,max_section:2,old_noise:1b}")),
        case("retrogen", chunk(extra='below_zero_retrogen:{target_status:"minecraft:spawn",missing_bedrock:[L;5L,-1L]}')),
        case("retrogen-no-bedrock", chunk(extra='below_zero_retrogen:{target_status:"minecraft:features"}')),
        case("retrogen-empty-bedrock", chunk(extra='below_zero_retrogen:{target_status:"minecraft:features",missing_bedrock:[L;0L]}')),
        case("retrogen-empty-status", chunk(extra='below_zero_retrogen:{target_status:"minecraft:empty"}')),
        case("retrogen-unknown-status", chunk(extra='below_zero_retrogen:{target_status:"minecraft:nope"}')),
        case("retrogen-no-status", chunk(extra="below_zero_retrogen:{}")),
        case("retrogen-bedrock-ints", chunk(extra='below_zero_retrogen:{target_status:"minecraft:full",missing_bedrock:[I;3]}')),
        case("retrogen-bedrock-list", chunk(extra='below_zero_retrogen:{target_status:"minecraft:full",missing_bedrock:[1.9d,-1.5d]}')),
        case("retrogen-bedrock-bad", chunk(extra='below_zero_retrogen:{target_status:"minecraft:full",missing_bedrock:[1,"x"]}')),
        case("retrogen-status-int", chunk(extra="below_zero_retrogen:{target_status:5}")),
        case("retrogen-bedrock-trailing-zero", chunk(extra='below_zero_retrogen:{target_status:"minecraft:full",missing_bedrock:[L;3L,0L]}')),
    ]


def whole():
    """Chunks with every section full, as a world's are."""
    g = Draws(SEED + 1)
    out = []
    for name, height, n_blocks, n_biomes in [("whole-overworld", OVERWORLD, 12, 3), ("whole-nether", NETHER, 6, 2)]:
        secs = []
        for y in range(height[0] // 16 - 1, height[0] // 16 + height[1] + 1):
            k = 1 + g.below(n_blocks)
            b = 1 + g.below(n_biomes)
            light = "SkyLight:[B;" + ",".join(f"{(g.below(256)) - 128}b" for _ in range(2048)) + "]"
            secs.append(section(y, random_container(g, STATES, k, 4096, block_bits), random_container(g, BIOMES, b, 64, biome_bits), light))
        extra = ("isLightOn:1b,Heightmaps:{MOTION_BLOCKING:" + longs([g.below(1 << 60) for _ in range(37)])
                 + ",WORLD_SURFACE:" + longs([g.below(1 << 60) for _ in range(37)]) + "},"
                 + 'block_entities:[{id:"minecraft:chest",x:1,y:2,z:3}],PostProcessing:[' + ",".join(["[]"] * height[1]) + "],"
                 + 'structures:{starts:{},References:{}},block_ticks:[],fluid_ticks:[{i:"minecraft:water",x:1,y:2,z:3,t:4,p:0}]')
        out.append(case(name, chunk(sections=secs, extra=extra), height))
    return out


def main():
    cases = basics() + sections() + palettes() + ticks() + others() + whole()
    write_file(HERE / "generated.json", "chunk_nbt", "cases/chunk_nbt/gen.py", cases)


if __name__ == "__main__":
    main()
