"""Checks Calcite's worldgen with Terralith and Terratonic against vanilla's (CAL-92): both servers
generate the same sample of chunks from the same seed and packs, and the chunks they save are
compared: each section's blocks and biomes, the heightmaps, the block entities and the structures'
references and starts.

    py -I rig/runner/terragen.py [--reuse] [--areas N] [--no-packs]

It runs in build/rig/terragen/, with Mojang's EULA accepted in its scratch folder only (CAL-42).
The packs are bench/terralith.py's, fetched and checked against their SHA-512s there, and the
seed is C2ME's, as the benchmark's is.

1. `vanilla/`: vanilla's server freezes its ticks first, so no block or fluid tick a feature
   leaves runs, force-loads each sample area, 8 by 8 chunks, waits until every chunk of each is
   loaded, saves and stops.
2. `calcite/`: Calcite's server pregenerates a square about each area, and stops.
3. Each chunk vanilla force-loaded, which it made to the end, is read from both worlds' region
   files and compared, its blocks and biomes decoded, so a palette's order doesn't count.

Light, entities and the times a chunk keeps aren't compared. It writes what differs to
build/rig/terragen/report.json, and exits with 1 if a chunk differs. --reuse compares the last
run's worlds again. --no-packs does it all without the packs, in build/rig/terragen/plain/, so a
difference can be told apart from one vanilla's own worldgen has.
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
SIDE = 8
# The sample's areas, by the block at their low corner: the spawn's, the benchmark's measured
# area's, and two far from both, in each quarter's direction.
AREAS = [(0, 0), (1000000, 1000000), (-20000, 35000), (300000, -500000), (-123456, -654321), (777777, 4096)]


def chunks_of(area):
    x0, z0 = area
    return [((x0 >> 4) + dx, (z0 >> 4) + dz) for dz in range(SIDE) for dx in range(SIDE)]


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


def vanilla(areas):
    folder = ROOT / "vanilla"
    prepare(folder, free_port(), True)
    began = time.monotonic()
    server = Server(vanilla_argv(adapter()), folder, "vanilla")
    try:
        at = server.wait_for("Done (", timeout=600)
        server.type("tick freeze")
        at = server.wait_for("The game is frozen", at)
        for x0, z0 in areas:
            x1, z1 = x0 + SIDE * 16 - 1, z0 + SIDE * 16 - 1
            server.type(f"forceload add {x0} {z0} {x1} {z1}")
            at = server.wait_for("to be force loaded", at)
        for area in areas:
            for cx, cz in chunks_of(area):
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
    print(f"  vanilla made {len(areas) * SIDE * SIDE} chunks in {time.monotonic() - began:.1f} s", flush=True)


def calcite(areas, calx):
    out = CALCITE / "build" / "rig" / "terragen" / "calcite.exe"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([calx, "build", "--release", "src/calcite.calx", "-o", str(out)], cwd=CALCITE, check=True)
    folder = ROOT / "calcite"
    prepare(folder, free_port(), False)
    (folder / "calcite.properties").write_text("console-dashboard=off\nrecord-inputs=false\n", encoding="utf-8")
    began = time.monotonic()
    server = Server([str(out)], folder, "calcite")
    try:
        at = server.wait_for("Done (", timeout=600)
        half = SIDE * 8
        for x0, z0 in areas:
            # A square about the area's middle reaching its edges: its chunks and those around.
            server.type(f"pregen center {x0 + half} {z0 + half}")
            server.type(f"pregen radius {half}")
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


def compare(cx, cz, v, c):
    """What differs between vanilla's chunk and Calcite's, as lines."""
    if v is None:
        return ["vanilla didn't save it"]
    if c is None:
        return ["Calcite didn't save it"]
    diffs = []
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
        diffs.append(f"blocks: {blocks_off} differ, the first at {first}")
    if biomes_off:
        diffs.append(f"biomes: {biomes_off} quarts differ")
    vh, ch = v.get("Heightmaps", {}), c.get("Heightmaps", {})
    for name in sorted(set(vh) & set(ch)):
        if list(vh[name]) != list(ch[name]):
            diffs.append(f"heightmap {name} differs")
    for name in sorted(set(vh) ^ set(ch)):
        diffs.append(f"heightmap {name} only in {'vanilla' if name in vh else 'Calcite'}")
    vbe = {(int(b["x"]), int(b["y"]), int(b["z"])): b for b in v.get("block_entities", [])}
    cbe = {(int(b["x"]), int(b["y"]), int(b["z"])): b for b in c.get("block_entities", [])}
    for pos in sorted(set(vbe) | set(cbe)):
        if pos not in cbe:
            diffs.append(f"block entity at {pos}: only vanilla's, {vbe[pos].get('id')}")
        elif pos not in vbe:
            diffs.append(f"block entity at {pos}: only Calcite's, {cbe[pos].get('id')}")
        elif plain(vbe[pos]) != plain(cbe[pos]):
            diffs.append(f"block entity at {pos} differs: vanilla {json.dumps(plain(vbe[pos]))[:300]}, "
                         f"Calcite {json.dumps(plain(cbe[pos]))[:300]}")
    vst, cst = v.get("structures", {}), c.get("structures", {})
    vref = {k: sorted(x) for k, x in vst.get("References", {}).items()}
    cref = {k: sorted(x) for k, x in cst.get("References", {}).items()}
    if vref != cref:
        diffs.append(f"structure references: vanilla {sorted(vref)}, Calcite {sorted(cref)}")
    vstart = {k: s.get("id") for k, s in vst.get("starts", {}).items()}
    cstart = {k: s.get("id") for k, s in cst.get("starts", {}).items()}
    if vstart != cstart:
        diffs.append(f"structure starts: vanilla {vstart}, Calcite {cstart}")
    return diffs


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reuse", action="store_true", help="compare the last run's worlds again")
    parser.add_argument("--areas", type=int, default=len(AREAS), help="how many of the sample's areas")
    parser.add_argument("--no-packs", action="store_true", help="vanilla's worldgen alone, in build/rig/terragen/plain/")
    args = parser.parse_args()
    if args.no_packs:
        global ROOT, PACKS
        ROOT, PACKS = ROOT / "plain", []
    areas = AREAS[:args.areas]
    if not args.reuse:
        fetch()
        vanilla(areas)
        calcite(areas, find_calx())
    v, c = Regions(ROOT / "vanilla" / REGION), Regions(ROOT / "calcite" / REGION)
    report, same = [], 0
    for area in areas:
        for cx, cz in chunks_of(area):
            diffs = compare(cx, cz, v.chunk(cx, cz), c.chunk(cx, cz))
            if diffs:
                report.append({"chunk": [cx, cz], "differences": diffs})
            else:
                same += 1
    total = len(areas) * SIDE * SIDE
    (ROOT / "report.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(f"terragen: {same} of {total} chunks are vanilla's", flush=True)
    for r in report[:20]:
        print(f"  chunk {r['chunk'][0]}, {r['chunk'][1]}:")
        for d in r["differences"][:6]:
            print(f"    {d}")
    if report:
        print(f"terragen: the rest is in {ROOT / 'report.json'}")
        sys.exit(1)


if __name__ == "__main__":
    main()
