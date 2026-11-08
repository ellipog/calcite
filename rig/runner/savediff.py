"""What two servers saved of the same chunks, compared (CAL-145): each block's state, each block
entity, the block and fluid ticks waiting, the heightmaps and the light, as vanilla's
`SerializableChunkData` writes them, read back from the worlds' region files.

    py -I rig/runner/savediff.py VANILLA_WORLD CALCITE_WORLD [X0 Z0 X1 Z1]

A section's palette and the bits it packs its states in depend on the order its blocks were set
in, so states are compared block by block, not as bytes; a block entity is compared by its
position, as a compound, and the ticks as sets, since each server keeps them in its own order.
What each saves of when it saved, `LastUpdate`, and how long players were near, `InhabitedTime`,
aren't compared: the bot's steps land on different game times on the two servers.

The entity chunks, in `entities/`, are compared too (CAL-148): each chunk's entities in the order
it saved them, by their UUIDs, and each entity's tags, but those that tell when the server
stopped, `ENTITY_TIMING`: an item's or an ageable mob's age, and its motion, which a still item
gathers as it falls 0.04 a tick between the moves it makes every 4 ticks; and a chicken's ticks
until it lays, which count down a tick at a time (CAL-156). A living entity's attributes are
compared in any order, `UNORDERED`, as vanilla's order changes from run to run.

So are the POI chunks, in `poi/` (CAL-160): which chunks each saved, each chunk's sections in the
order it saved them, and each section's `Valid` and its records, in order, each record's place,
type and tickets free.
"""

import struct
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nbt  # noqa: E402

# The chunk keys that are compared, each on its own: what isn't here, and isn't left out below, is
# compared as it is.
LEFT_OUT = {"LastUpdate", "InhabitedTime", "xPos", "zPos", "yPos", "DataVersion"}
# An entity's tags that tell when the server stopped (CAL-148).
ENTITY_TIMING = {"Age", "Motion", "EggLayTime"}
# An entity's lists in an order no server keeps (CAL-156): a living entity's attributes, which
# vanilla saves as its `AttributeMap`'s hash map of holders gives them, by identity hashes that
# differ from run to run; compared as sets.
UNORDERED = {"attributes"}


def chunks(world, dimension="minecraft/overworld", folder="region"):
    """Each chunk the world's region files of `dimension` hold, by its position, as a compound:
    its blocks', or, with `folder` "entities", its entities', or with "poi", its points of
    interest."""
    out = {}
    for region in sorted((Path(world) / "dimensions" / dimension / folder).glob("r.*.*.mca")):
        data = region.read_bytes()
        if len(data) < 8192:
            continue
        rx, rz = (int(p) for p in region.name.split(".")[1:3])
        for i in range(1024):
            sector = int.from_bytes(data[i * 4:i * 4 + 3], "big")
            if sector == 0:
                continue
            at = sector * 4096
            length, kind = struct.unpack_from(">iB", data, at)
            if kind != 2:
                raise ValueError(f"{region.name} keeps chunk {i} compressed as {kind}, not zlib")
            r = nbt._Reader(zlib.decompress(bytes(data[at + 5:at + 4 + length])))
            r.take(">b")
            r.string()
            out[(rx * 32 + i % 32, rz * 32 + i // 32)] = r.payload(nbt.COMPOUND)
    return out


def state_name(entry):
    """A palette entry as `name[key=value,...]`, its properties in their names' order. 26.3 writes
    a state with no properties as its name alone, which a list of compounds holds as `{"": name}`,
    as `NbtOps` keeps a list of tags of more than one type, and one with them as `id` and
    `properties`."""
    if isinstance(entry, str):
        return entry
    if "" in entry:
        return entry[""]
    name = entry.get("id", entry.get("Name"))
    props = entry.get("properties", entry.get("Properties", {}))
    if not props:
        return name
    return name + "[" + ",".join(f"{k}={props[k]}" for k in sorted(props)) + "]"


def _indices(data, palette_len, size, least=4):
    """A paletted container's `size` entries, each its palette entry's index, as
    `SimpleBitStorage` packs them: as few bits as the palette needs, at least `least`, none
    across two longs."""
    bits = max(least, (palette_len - 1).bit_length())
    per = 64 // bits
    mask = (1 << bits) - 1
    out = []
    for i in range(size):
        word = data[i // per] & 0xFFFFFFFFFFFFFFFF
        out.append((word >> ((i % per) * bits)) & mask)
    return out


def section_states(section):
    """A section's 4096 states, as names, by `y * 256 + z * 16 + x`."""
    container = section.get("block_states", {"palette": [{"Name": "minecraft:air"}]})
    palette = container.get("palette", [])
    data = container.get("data")
    names = [state_name(p) for p in palette]
    if not data:
        return [names[0]] * 4096
    return [names[i] for i in _indices(data, len(palette), 4096)]


def block_entities(chunk):
    """A chunk's block entities by position, each without its position."""
    out = {}
    for be in chunk.get("block_entities", []):
        out[(be["x"], be["y"], be["z"])] = {k: v for k, v in be.items() if k not in ("x", "y", "z")}
    return out


def ticks(chunk, key):
    """A chunk's ticks of `key`, each as a hashable tuple, as a set."""
    return {tuple(sorted((k, str(v)) for k, v in t.items())) for t in chunk.get(key, [])}


def light(chunk, bottom):
    """A chunk's light by section and layer. The sky layer of 2048 bytes of 0 of the section
    below the world, `bottom`, is left out, as none: vanilla's light gives it to the first chunk
    it sets up in a batch, `repeatFirstLayer`, and none to the rest, by which of its workers
    finishes first (rig/README.md, "The sky under the world")."""
    out = {}
    for s in chunk.get("sections", []):
        for layer in ("BlockLight", "SkyLight"):
            if layer not in s:
                continue
            values = list(s[layer])
            if layer == "SkyLight" and s["Y"] == bottom and not any(values):
                continue
            out[(s["Y"], layer)] = values
    return out


def compare(vanilla_world, calcite_world, area, show=20):
    """The differences between the chunks in `area`, `(x0, z0, x1, z1)` inclusive, as each world
    saved them, as lines: none if they're the same."""
    v, c = chunks(vanilla_world), chunks(calcite_world)
    lines = []
    x0, z0, x1, z1 = area
    for cx in range(x0, x1 + 1):
        for cz in range(z0, z1 + 1):
            a, b = v.get((cx, cz)), c.get((cx, cz))
            if a is None or b is None:
                if a is not None or b is not None:
                    lines.append(f"chunk {cx}, {cz}: only {'vanilla' if a is not None else 'Calcite'} saved it")
                continue
            lines += [f"chunk {cx}, {cz}: {d}" for d in chunk_differences(cx, cz, a, b, show)]
    return lines + entity_differences(vanilla_world, calcite_world, area) + poi_differences(vanilla_world, calcite_world, area)


def uuid_of(entity):
    """An entity's UUID, its four ints, as a tuple."""
    return tuple(entity.get("UUID", ()))


def entity_differences(vanilla_world, calcite_world, area):
    """The differences between the entity chunks in `area` as each world saved them (CAL-148)."""
    v, c = chunks(vanilla_world, folder="entities"), chunks(calcite_world, folder="entities")
    lines = []
    x0, z0, x1, z1 = area
    for cx in range(x0, x1 + 1):
        for cz in range(z0, z1 + 1):
            a = v.get((cx, cz), {}).get("Entities", [])
            b = c.get((cx, cz), {}).get("Entities", [])
            if [uuid_of(e) for e in a] != [uuid_of(e) for e in b]:
                lines.append(f"entities {cx}, {cz}: {len(a)} of vanilla's, {[e.get('id') for e in a]}, vs {len(b)} of Calcite's, {[e.get('id') for e in b]}")
                continue
            for ea, eb in zip(a, b):
                keys = (set(ea) | set(eb)) - ENTITY_TIMING
                for key in sorted(keys):
                    if key in UNORDERED:
                        if sorted(map(repr, ea.get(key, []))) != sorted(map(repr, eb.get(key, []))):
                            lines.append(f"entities {cx}, {cz}: {ea.get('id')} {key}: {ea.get(key)!r:.200} vs {eb.get(key)!r:.200}")
                        continue
                    if ea.get(key) != eb.get(key):
                        lines.append(f"entities {cx}, {cz}: {ea.get('id')} {key}: {ea.get(key)!r:.200} vs {eb.get(key)!r:.200}")
                if list(ea) != list(eb):
                    lines.append(f"entities {cx}, {cz}: {ea.get('id')}'s tags in another order: {list(ea)} vs {list(eb)}")
    return lines


def poi_differences(vanilla_world, calcite_world, area):
    """The differences between the POI chunks in `area` as each world saved them (CAL-160)."""
    v, c = chunks(vanilla_world, folder="poi"), chunks(calcite_world, folder="poi")
    lines = []
    x0, z0, x1, z1 = area
    for cx in range(x0, x1 + 1):
        for cz in range(z0, z1 + 1):
            a, b = v.get((cx, cz)), c.get((cx, cz))
            if a is None or b is None:
                if a is not None or b is not None:
                    lines.append(f"poi {cx}, {cz}: only {'vanilla' if a is not None else 'Calcite'} saved it")
                continue
            sa, sb = a.get("Sections", {}), b.get("Sections", {})
            if list(sa) != list(sb):
                lines.append(f"poi {cx}, {cz}: sections {list(sa)} vs {list(sb)}")
                continue
            for y in sa:
                if sa[y] != sb[y]:
                    lines.append(f"poi {cx}, {cz}: section {y}: {sa[y]!r:.300} vs {sb[y]!r:.300}")
                elif list(sa[y]) != list(sb[y]):
                    lines.append(f"poi {cx}, {cz}: section {y}'s tags in another order: {list(sa[y])} vs {list(sb[y])}")
    return lines


def chunk_differences(cx, cz, a, b, show):
    out = []
    sa = {s["Y"]: s for s in a.get("sections", [])}
    sb = {s["Y"]: s for s in b.get("sections", [])}
    blocks = 0
    for y in sorted(set(sa) | set(sb)):
        na = section_states(sa.get(y, {}))
        nb = section_states(sb.get(y, {}))
        for i in range(4096):
            if na[i] != nb[i]:
                blocks += 1
                if blocks <= show:
                    x, yy, z = cx * 16 + i % 16, y * 16 + i // 256, cz * 16 + (i // 16) % 16
                    out.append(f"block {x}, {yy}, {z}: {na[i]} vs {nb[i]}")
    if blocks > show:
        out.append(f"{blocks - show} more blocks differ")
    ea, eb = block_entities(a), block_entities(b)
    for pos in sorted(set(ea) | set(eb)):
        if ea.get(pos) != eb.get(pos):
            out.append(f"block entity {pos[0]}, {pos[1]}, {pos[2]}: {ea.get(pos)!r:.300} vs {eb.get(pos)!r:.300}")
    for key in ("block_ticks", "fluid_ticks"):
        ta, tb = ticks(a, key), ticks(b, key)
        if ta != tb:
            out.append(f"{key}: {len(ta - tb)} only vanilla's, {len(tb - ta)} only Calcite's")
    for key in sorted((set(a) | set(b)) - LEFT_OUT - {"sections", "block_entities", "block_ticks", "fluid_ticks"}):
        if a.get(key) != b.get(key):
            out.append(f"{key}: {a.get(key)!r:.200} vs {b.get(key)!r:.200}")
    bottom = min(list(sa) + list(sb), default=None)
    la, lb = light(a, bottom), light(b, bottom)
    lit = [k for k in sorted(set(la) | set(lb)) if la.get(k) != lb.get(k)]
    if lit:
        out.append(f"light differs in {len(lit)} layers, the first section {lit[0][0]}'s {lit[0][1]}")
    return out


def main():
    args = sys.argv[1:]
    if len(args) not in (2, 6):
        sys.exit(__doc__)
    area = tuple(int(a) for a in args[2:]) if len(args) == 6 else (-1, -1, 0, 0)
    lines = compare(args[0], args[1], area)
    for line in lines:
        print(line)
    print("the same" if not lines else f"{len(lines)} differences")


if __name__ == "__main__":
    main()
