"""Checks Calcite's worldgen with Terralith and Terratonic against vanilla's (CAL-92): both servers
generate the same sample of chunks from the same seed and packs, and the chunks they save are
compared: each section's blocks and biomes, the heightmaps, the block entities, the block and fluid
ticks, the blocks marked for post-processing, and the structures' starts and references.

    py -I rig/runner/terragen.py [--reuse | --calcite] [--areas N] [--no-packs] [--orders]
                                 [--part-way]

It runs in build/rig/terragen/, with Mojang's EULA accepted in its scratch folder only (CAL-42).
The packs are bench/terralith.py's, fetched and checked against their SHA-512s there, and the
seed is C2ME's, as the benchmark's is.

1. `vanilla/`: vanilla's server freezes its ticks first, so no block or fluid tick a feature
   leaves runs, force-loads the middle 8 by 8 chunks of each sample area, 12 by 12, waits until
   each is loaded, saves and stops. A chunk loaded so ticks, and vanilla post-processes it as it
   starts to, so what's compared is the ring of chunks 2 out from those, at the area's edge,
   which a force-loaded chunk needs full and which never tick: as a pregenerated chunk is.
2. `calcite/`: Calcite's server pregenerates each area, and stops. With --part-way, it
   pregenerates the middle 10 by 10 of each first and stops, so the ring is saved lit around them,
   at `minecraft:light`, its mobs still to spawn; then it starts again and pregenerates the whole,
   carrying on from what it saved (CAL-161).
3. Each chunk of the rings is read from both worlds' region files and compared, its blocks and
   biomes decoded, so a palette's order doesn't count, and its ticks, blocks to update and block
   entities by position, so their order doesn't either.

The mobs each area's chunks spawned as they generated, `spawnMobsForChunkGeneration`, are
compared too, from each world's entity files, each as it's saved but for what's drawn from a
random of its own, its UUID and a chicken's egg time, and with its attributes sorted, which
vanilla saves in the order of a hash map keyed by identity (CAL-161): the same in a ring chunk
whose heightmaps are, so its surface is, unless vanilla's has a type Calcite doesn't make yet,
which ends a chunk's spawning in Calcite.

Light and the times a chunk keeps aren't compared. Where features from neighbouring
chunks meet, what's left depends on the order the chunks were decorated in, which vanilla doesn't
fix and Calcite fixes as its own (D29, D214): ore and stone blobs over each other, dripstone and
sculk, trees, and the ticks, blocks to update and block entities that go with them (D288). So
what's compared is in two parts:

- what must be the same: each chunk's status, its biomes, its structures' references, its starts
  but for the flags pieces set as they're placed, and the block entities both have, as they're
  saved;
- what the order moves: the blocks, heightmaps, ticks and blocks to update, and which block
  entities there are, counted.

It writes both to build/rig/terragen/report.json, and exits with 1 if anything that must be the
same isn't. --orders has vanilla make the sample a second time, force-loading one chunk at a time
from the far corner, in vanilla2/, and counts what that moves too, for scale. --reuse compares the
last run's worlds again, and --calcite makes Calcite's again against the last run's vanilla ones.
--no-packs does it all without the packs, in build/rig/terragen/plain/.
"""

import argparse
import json
import shutil
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "bench"))
import nbt  # noqa: E402
from sessions import Server, adapter, find_calx, free_port, vanilla_argv  # noqa: E402
from terralith import PINS, SEED, fetch  # noqa: E402

CALCITE = HERE.parents[1]
ROOT = CALCITE / "build" / "rig" / "terragen"
# The packs each world has: the pins, or none with --no-packs.
PACKS = PINS
REGION = Path("world") / "dimensions" / "minecraft" / "overworld" / "region"
ENTITIES = Path("world") / "dimensions" / "minecraft" / "overworld" / "entities"
# Each area's side in chunks, and how far in from its edge the chunks force-loaded start.
SIDE = 12
INSET = 2
# The sample's areas, by the block at their low corner: the spawn's, the benchmark's measured
# area's, and two far from both, in each quarter's direction.
AREAS = [(0, 0), (1000000, 1000000), (-20000, 35000), (300000, -500000), (-123456, -654321), (777777, 4096)]


def chunks_of(area):
    """The chunks compared: the area's edge, 2 out from those force-loaded."""
    x0, z0 = area
    edge = (0, SIDE - 1)
    return [((x0 >> 4) + dx, (z0 >> 4) + dz) for dz in range(SIDE) for dx in range(SIDE) if dx in edge or dz in edge]


def area_of(area):
    """Every chunk of the area, whose mobs are compared."""
    x0, z0 = area
    return [((x0 >> 4) + dx, (z0 >> 4) + dz) for dz in range(SIDE) for dx in range(SIDE)]


def forced_of(area):
    x0, z0 = area
    inner = range(INSET, SIDE - INSET)
    return [((x0 >> 4) + dx, (z0 >> 4) + dz) for dz in inner for dx in inner]


def prepare(folder, port, eula):
    if folder.exists():
        shutil.rmtree(folder)
    (folder / "world" / "datapacks").mkdir(parents=True)
    for pin in PACKS:
        shutil.copyfile(CALCITE / "build" / "bench" / "packs" / pin["file"], folder / "world" / "datapacks" / pin["file"])
    (folder / "server.properties").write_text(
        f"online-mode=false\nserver-ip=127.0.0.1\nserver-port={port}\nlevel-seed={SEED}\n"
        "view-distance=2\nsimulation-distance=2\nspawn-protection=0\n", encoding="utf-8")
    if eula:
        # Elliot accepted Mojang's EULA for the rig's own scratch servers (CAL-42).
        (folder / "eula.txt").write_text("eula=true\n", encoding="utf-8")


def vanilla(areas, name="vanilla", one_by_one=False):
    folder = ROOT / name
    prepare(folder, free_port(), True)
    began = time.monotonic()
    server = Server(vanilla_argv(adapter()), folder, "vanilla")
    try:
        at = server.wait_for("Done (", timeout=600)
        server.type("tick freeze")
        at = server.wait_for("The game is frozen", at)
        for x0, z0 in areas:
            if one_by_one:
                continue
            bx, bz = ((x0 >> 4) + INSET) * 16, ((z0 >> 4) + INSET) * 16
            span = (SIDE - 2 * INSET) * 16 - 1
            server.type(f"forceload add {bx} {bz} {bx + span} {bz + span}")
            at = server.wait_for("to be force loaded", at)
        for area in areas:
            for cx, cz in (list(reversed(forced_of(area))) if one_by_one else forced_of(area)):
                if one_by_one:
                    server.type(f"forceload add {cx * 16} {cz * 16}")
                    at = server.wait_for("force loaded", at)
                end = time.monotonic() + 600
                while True:
                    server.type(f"execute if loaded {cx * 16} 0 {cz * 16}")
                    at = server.wait_for("Test ", at, timeout=60)
                    if "Test passed" in server.lines[at - 1]:
                        break
                    if time.monotonic() > end:
                        sys.exit(f"terragen: vanilla never loaded chunk {cx}, {cz}")
                    time.sleep(0.25)
        server.type("save-all flush")
        at = server.wait_for("Saved the game", at, timeout=600)
    finally:
        server.stop()
    print(f"  vanilla made {len(areas)} areas in {name}/ in {time.monotonic() - began:.1f} s", flush=True)


def calcite(areas, calx, part_way=False):
    out = CALCITE / "build" / "rig" / "terragen" / "calcite.exe"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([calx, "build", "--release", "src/calcite.calx", "-o", str(out)], cwd=CALCITE, check=True)
    folder = ROOT / "calcite"
    prepare(folder, free_port(), False)
    (folder / "calcite.properties").write_text("console-dashboard=off\nrecord-inputs=false\n", encoding="utf-8")
    began = time.monotonic()
    half = SIDE * 8
    # The square of each area's chunks, its middle first where it's made part-way.
    for radius in ([half - 16, half] if part_way else [half]):
        server = Server([str(out)], folder, "calcite")
        try:
            at = server.wait_for("Done (", timeout=600)
            for x0, z0 in areas:
                server.type(f"pregen center {(x0 >> 4) * 16 + half} {(z0 >> 4) * 16 + half}")
                server.type(f"pregen radius {radius}")
                server.type("pregen start")
                at = server.wait_for(" done: ", at, timeout=3600)
        finally:
            server.stop()
    print(f"  Calcite made its chunks in {time.monotonic() - began:.1f} s", flush=True)


class Regions:
    """A world's region files, read as they're asked for."""

    def __init__(self, folder):
        self.folder, self.files = folder, {}

    def chunk(self, cx, cz):
        key = (cx >> 5, cz >> 5)
        if key not in self.files:
            path = self.folder / f"r.{key[0]}.{key[1]}.mca"
            self.files[key] = path.read_bytes() if path.is_file() else b""
        data = self.files[key]
        i = ((cx & 31) + (cz & 31) * 32) * 4
        if len(data) < 8192:
            return None
        sector = int.from_bytes(data[i:i + 3], "big")
        if sector == 0:
            return None
        at = sector * 4096
        length = int.from_bytes(data[at:at + 4], "big")
        kind = data[at + 4]
        body = data[at + 5:at + 4 + length]
        if kind == 2:
            raw = zlib.decompress(body)
        elif kind == 1:
            import gzip
            raw = gzip.decompress(body)
        elif kind == 3:
            raw = body
        else:
            raise ValueError(f"chunk {cx}, {cz} is compressed as {kind}, which this doesn't read")
        r = nbt._Reader(raw)
        if r.take(">b") != nbt.COMPOUND:
            raise ValueError(f"chunk {cx}, {cz} isn't a compound")
        r.string()
        return r.payload(nbt.COMPOUND)


def unpack(longs, bits, count):
    """A paletted container's indices, packed as 26.3 packs them: no index across two longs."""
    per = 64 // bits
    mask = (1 << bits) - 1
    out = []
    for v in longs:
        v &= 0xFFFFFFFFFFFFFFFF
        for j in range(per):
            out.append((v >> (j * bits)) & mask)
            if len(out) == count:
                return out
    return out + [0] * (count - len(out))


def state_name(s):
    """A palette's block state as text. 26.3 saves one with no properties as its id alone, one
    with them as `id` and `properties`, and a list holding both kinds wraps each id alone in a
    compound with the empty key."""
    if isinstance(s, str):
        return s
    if set(s) == {""}:
        return state_name(s[""])
    props = s.get("properties") or {}
    return s["id"] + ("[" + ",".join(f"{k}={props[k]}" for k in sorted(props)) + "]" if props else "")


def sections(chunk):
    """Each section's blocks and biomes, by its Y, decoded."""
    out = {}
    for sec in chunk.get("sections", []):
        y = int(sec["Y"])
        blocks = biomes = None
        if "block_states" in sec:
            palette = [state_name(s) for s in sec["block_states"]["palette"]]
            data = sec["block_states"].get("data")
            if not data or len(palette) == 1:
                blocks = [palette[0]] * 4096
            else:
                blocks = [palette[i] for i in unpack(data, max(4, (len(palette) - 1).bit_length()), 4096)]
        if "biomes" in sec:
            palette = list(sec["biomes"]["palette"])
            data = sec["biomes"].get("data")
            if not data or len(palette) == 1:
                biomes = [palette[0]] * 64
            else:
                biomes = [palette[i] for i in unpack(data, (len(palette) - 1).bit_length(), 64)]
        out[y] = (blocks, biomes)
    return out


def plain(value):
    """An NBT value as JSON can hold it, for the report."""
    if isinstance(value, dict):
        return {k: plain(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [plain(v) for v in value]
    return value


# The fields a structure piece sets as it's placed, the first time a chunk it's in is decorated
# or as it places a chest, a spawner or a mob, which the order of decoration decides.
PLACED_FLAGS = {"hps", "Witch", "Cat", "placedMainChest", "placedHiddenChest", "placedTrap1", "placedTrap2",
                "hasPlacedChest0", "hasPlacedChest1", "hasPlacedChest2", "hasPlacedChest3", "HPos", "Chest", "Mob"}


def unplaced(start):
    """A start without the flags its pieces set as they're placed, nor the height of a shipwreck
    that's adjusted it, `height_adjusted`, which `ShipwreckPiece.postProcess` works out from the
    heights around it the first time it's placed, so the order decides it too."""
    out = plain(start)
    for piece in out.get("Children", []):
        for flag in PLACED_FLAGS:
            piece.pop(flag, None)
        if piece.get("height_adjusted"):
            piece.pop("TPY", None)
            bb = piece.get("BB")
            if isinstance(bb, list) and len(bb) == 6:
                piece["BB"] = [bb[0], bb[2], bb[3], bb[5]]
    return out


def compare(cx, cz, v, c):
    """What differs between vanilla's chunk and Calcite's: lines of what must be the same, and of
    what the order of decoration moves, with the blocks that differ."""
    if v is None:
        return ["vanilla didn't save it"], [], 0
    if c is None:
        return ["Calcite didn't save it"], [], 0
    diffs, moved = [], []
    if v.get("Status") != c.get("Status"):
        diffs.append(f"status: vanilla {v.get('Status')}, Calcite {c.get('Status')}")
    vs, cs = sections(v), sections(c)
    blocks_off, biomes_off, first = 0, 0, None
    for y in sorted(set(vs) | set(cs)):
        vb, vbi = vs.get(y, (None, None))
        cb, cbi = cs.get(y, (None, None))
        if vb is None and cb is None:
            pass
        else:
            vb = vb or ["minecraft:air"] * 4096
            cb = cb or ["minecraft:air"] * 4096
            for i in range(4096):
                if vb[i] != cb[i]:
                    blocks_off += 1
                    if first is None:
                        x, z, by = i & 15, (i >> 4) & 15, i >> 8
                        first = f"({cx * 16 + x}, {y * 16 + by}, {cz * 16 + z}): vanilla {vb[i]}, Calcite {cb[i]}"
        if vbi is not None and cbi is not None and vbi != cbi:
            biomes_off += sum(1 for a, b in zip(vbi, cbi) if a != b)
    if blocks_off:
        moved.append(f"blocks: {blocks_off} differ, the first at {first}")
    if biomes_off:
        diffs.append(f"biomes: {biomes_off} quarts differ")
    vh, ch = v.get("Heightmaps", {}), c.get("Heightmaps", {})
    for name in sorted(set(vh) & set(ch)):
        if list(vh[name]) != list(ch[name]):
            moved.append(f"heightmap {name} differs")
    for name in sorted(set(vh) ^ set(ch)):
        diffs.append(f"heightmap {name} only in {'vanilla' if name in vh else 'Calcite'}")
    vbe = {(int(b["x"]), int(b["y"]), int(b["z"])): b for b in v.get("block_entities", [])}
    cbe = {(int(b["x"]), int(b["y"]), int(b["z"])): b for b in c.get("block_entities", [])}
    for pos in sorted(set(vbe) | set(cbe)):
        if pos not in cbe:
            moved.append(f"block entity at {pos}: only vanilla's, {vbe[pos].get('id')}")
        elif pos not in vbe:
            moved.append(f"block entity at {pos}: only Calcite's, {cbe[pos].get('id')}")
        elif plain(vbe[pos]) != plain(cbe[pos]):
            diffs.append(f"block entity at {pos} differs: vanilla {json.dumps(plain(vbe[pos]))[:300]}, "
                         f"Calcite {json.dumps(plain(cbe[pos]))[:300]}")
    for kind in ("block_ticks", "fluid_ticks"):
        vt, ct = ticks(v.get(kind, [])), ticks(c.get(kind, []))
        if vt != ct:
            only_v, only_c = sorted(set(vt) - set(ct)), sorted(set(ct) - set(vt))
            moved.append(f"{kind}: {len(vt)} in vanilla's, {len(ct)} in Calcite's; only vanilla's {only_v[:3]}, only Calcite's {only_c[:3]}")
    vp, cp = marks(v), marks(c)
    if vp != cp:
        moved.append(f"PostProcessing: {sum(len(x) for x in vp)} marks in vanilla's, {sum(len(x) for x in cp)} in Calcite's, "
                     f"first differing in section {next(i for i in range(max(len(vp), len(cp))) if (vp[i:i + 1] or [[]]) != (cp[i:i + 1] or [[]]))}")
    vst, cst = v.get("structures", {}), c.get("structures", {})
    if sorted(vst) != sorted(cst):
        diffs.append(f"structures: vanilla's has {sorted(vst)}, Calcite's {sorted(cst)}")
    vref = {k: sorted(x) for k, x in vst.get("References", {}).items()}
    cref = {k: sorted(x) for k, x in cst.get("References", {}).items()}
    if vref != cref:
        diffs.append(f"structure references: vanilla {vref}, Calcite {cref}")
    vstart, cstart = vst.get("starts", {}), cst.get("starts", {})
    if sorted(vstart) != sorted(cstart):
        diffs.append(f"structure starts: vanilla {sorted(vstart)}, Calcite {sorted(cstart)}")
    else:
        for k in sorted(vstart):
            if unplaced(vstart[k]) != unplaced(cstart[k]):
                diffs.append(f"structure start {k} differs: vanilla {json.dumps(unplaced(vstart[k]))[:400]}, "
                             f"Calcite {json.dumps(unplaced(cstart[k]))[:400]}")
            elif plain(vstart[k]) != plain(cstart[k]):
                moved.append(f"structure start {k}: its pieces' placed flags or heights differ")
    return diffs, moved, blocks_off


# What an entity draws from a random of its own as it's made, which depends on its ID, and so on
# the order vanilla's threads made the chunks in.
OWN_RANDOM = ("UUID", "EggLayTime")


def mobs(chunk):
    """An entity chunk's entities as they're saved, but for `OWN_RANDOM`, with their attributes
    sorted, and sorted by type and place, so no order counts."""
    out = []
    for e in (chunk or {}).get("Entities", []):
        tag = plain(e)
        for key in OWN_RANDOM:
            tag.pop(key, None)
        if isinstance(tag.get("attributes"), list):
            tag["attributes"] = sorted(tag["attributes"], key=lambda a: str(a.get("id")))
        out.append(tag)
    return sorted(out, key=lambda t: (str(t.get("id", "")), [float(p) for p in t.get("Pos", [])]))


def short(tags):
    """Entities as their types and places, for the report."""
    return [f"{t.get('id')} at {[round(float(p), 3) for p in t.get('Pos', [])]}" for t in tags]


def compare_mobs(vm, cm):
    """What differs between vanilla's mobs in a chunk and Calcite's, or None."""
    if vm == cm:
        return None
    if [t.get("id") for t in vm] != [t.get("id") for t in cm] or [t.get("Pos") for t in vm] != [t.get("Pos") for t in cm]:
        return f"vanilla's {short(vm)[:6]}, Calcite's {short(cm)[:6]}"
    for a, b in zip(vm, cm):
        if a != b:
            keys = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
            said = "; ".join(f"{k}: vanilla {json.dumps(a.get(k))[:160]}, Calcite {json.dumps(b.get(k))[:160]}" for k in keys[:4])
            return f"{a.get('id')} at {short([a])[0]}: {said}"
    return None


def mob_tally(areas, v, c, moved):
    """The mobs of each area's chunks, vanilla's against Calcite's: how many chunks have any in
    each, how many are the same, and those that differ, in a ring chunk whose surface the order
    doesn't move, `moved` the rest, where vanilla has no type Calcite doesn't make, which must be
    the same, and the rest."""
    out = {"vanilla_chunks": 0, "calcite_chunks": 0, "vanilla_mobs": 0, "calcite_mobs": 0, "same": 0, "wrong": [], "other": []}
    made = set()
    found = {}
    for area in areas:
        for cx, cz in area_of(area):
            vm, cm = mobs(v.chunk(cx, cz)), mobs(c.chunk(cx, cz))
            found[(cx, cz)] = (vm, cm)
            made |= {t.get("id") for t in cm}
    ring = {tuple(xz) for area in areas for xz in chunks_of(area)}
    for (cx, cz), (vm, cm) in found.items():
        out["vanilla_chunks"] += 1 if vm else 0
        out["calcite_chunks"] += 1 if cm else 0
        out["vanilla_mobs"] += len(vm)
        out["calcite_mobs"] += len(cm)
        diff = compare_mobs(vm, cm)
        if diff is None:
            out["same"] += 1 if vm else 0
            continue
        unmade = sorted({str(t.get("id")) for t in vm} - made)
        row = {"chunk": [cx, cz], "difference": diff}
        if unmade:
            row["unmade"] = unmade
        if (cx, cz) in ring and (cx, cz) not in moved and not unmade:
            out["wrong"].append(row)
        else:
            out["other"].append(row)
    return out


def ticks(tags):
    """A chunk's ticks, as a sorted list, so their order doesn't count."""
    return sorted((str(t.get("i")), int(t["x"]), int(t["y"]), int(t["z"]), int(t.get("t", 0)), int(t.get("p", 0))) for t in tags)


def marks(chunk):
    """Each section's blocks marked for post-processing, sorted, with no empty sections at the end."""
    out = [sorted(int(o) for o in section) for section in chunk.get("PostProcessing", [])]
    while out and not out[-1]:
        out.pop()
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reuse", action="store_true", help="compare the last run's worlds again")
    parser.add_argument("--calcite", action="store_true", help="make Calcite's worlds again, against the last run's vanilla ones")
    parser.add_argument("--areas", type=int, default=len(AREAS), help="how many of the sample's areas")
    parser.add_argument("--no-packs", action="store_true", help="vanilla's worldgen alone, in build/rig/terragen/plain/")
    parser.add_argument("--orders", action="store_true", help="have vanilla make the sample again in another order, for scale")
    parser.add_argument("--part-way", action="store_true", help="have Calcite make each area's middle first, stop and carry on")
    args = parser.parse_args()
    if args.no_packs:
        global ROOT, PACKS
        ROOT, PACKS = ROOT / "plain", []
    areas = AREAS[:args.areas]
    if args.calcite:
        calcite(areas, find_calx(), args.part_way)
    elif not args.reuse:
        fetch()
        vanilla(areas)
        if args.orders:
            vanilla(areas, "vanilla2", True)
        calcite(areas, find_calx(), args.part_way)
    v = Regions(ROOT / "vanilla" / REGION)
    report = {"calcite": tally(areas, v, Regions(ROOT / "calcite" / REGION))}
    if (ROOT / "vanilla2" / REGION).is_dir() and (args.orders or args.reuse):
        report["vanilla2"] = tally(areas, v, Regions(ROOT / "vanilla2" / REGION))
    moved = {tuple(r["chunk"]) for r in report["calcite"]["moved"] if any(d.startswith("heightmap") for d in r["differences"])}
    report["mobs"] = mob_tally(areas, Regions(ROOT / "vanilla" / ENTITIES), Regions(ROOT / "calcite" / ENTITIES), moved)
    (ROOT / "report.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    total = sum(len(chunks_of(a)) for a in areas)
    for name, t in report.items():
        if name == "mobs":
            continue
        who = "Calcite" if name == "calcite" else "vanilla in another order"
        print(f"terragen: {who}: {total - len(t['wrong'])} of {total} chunks have what must be vanilla's; "
              f"{t['same']} are vanilla's whole; the order moves {t['blocks']} blocks in {t['moved_chunks']} chunks", flush=True)
    wrong = report["calcite"]["wrong"]
    for r in wrong[:20]:
        print(f"  chunk {r['chunk'][0]}, {r['chunk'][1]}:")
        for d in r["differences"][:6]:
            print(f"    {d}")
    m = report["mobs"]
    print(f"terragen: mobs: {m['vanilla_mobs']} in {m['vanilla_chunks']} of vanilla's chunks, {m['calcite_mobs']} in "
          f"{m['calcite_chunks']} of Calcite's; {m['same']} chunks the same; {len(m['wrong'])} differ that must not, "
          f"{len(m['other'])} where the blocks differ or vanilla has a type Calcite doesn't make", flush=True)
    for r in m["wrong"][:12] + m["other"][:8]:
        print(f"  chunk {r['chunk'][0]}, {r['chunk'][1]}{' (unmade ' + ', '.join(r['unmade']) + ')' if 'unmade' in r else ''}: {r['difference']}")
    print(f"terragen: what differs is in {ROOT / 'report.json'}")
    if wrong or m["wrong"]:
        sys.exit(1)


def tally(areas, v, other):
    """What differs between vanilla's chunks and `other`'s: the chunks with what must be the same
    and isn't, those the order moves, how many blocks it moves, and how many are the same whole."""
    out = {"wrong": [], "moved": [], "blocks": 0, "moved_chunks": 0, "same": 0}
    for area in areas:
        for cx, cz in chunks_of(area):
            diffs, moved, blocks = compare(cx, cz, v.chunk(cx, cz), other.chunk(cx, cz))
            if diffs:
                out["wrong"].append({"chunk": [cx, cz], "differences": diffs})
            if moved:
                out["moved"].append({"chunk": [cx, cz], "differences": moved})
                out["moved_chunks"] += 1
            if not diffs and not moved:
                out["same"] += 1
            out["blocks"] += blocks
    return out


if __name__ == "__main__":
    main()
