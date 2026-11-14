"""Checks what a chunk does as it starts to tick against vanilla (D329, CAL-91): its
post-processing, `LevelChunk.postProcessGeneration`, and its first ticks; and the chunks a save
left part-way, as their generation goes on (D333, D334, CAL-113).

    py -I rig/runner/ticking.py [--reuse] [--show N]

Both servers load the world the round trip has vanilla make and save (rig/runner/roundtrip.py),
whose chunks from -6 to 5 are full, and more to the north and east, where vanilla loaded the
spawn's. Those vanilla ticked it post-processed before it saved them. Those at the edge it didn't,
so they still have the blocks their generation marked, `PostProcessing`: aquifers' water and lava,
mushrooms, ice, glow lichen, leaves. Round the full chunks, the save has a ring with its features,
waiting for its light, then one with only its terrain, then one with only its biomes: among the
chunks from -8 to 7, at -7 and -8 on the west, 6 and 7 on the south, at the north-west corner, and
on the east south of 0. The rig's bot joins each server at the origin with a view of 10, as
`sessions.py` records a session, so the chunks from -8 to 7 are all sent, each server finishing
the part-way rings first, from where it saved them (D334).

Each chunk packet's blocks are decoded, so how a palette is written (D271) doesn't count, with the
blocks each `block_update` and `section_blocks_update` after it sets, as the client keeps them, so
what each block's ticks set after the chunk was sent counts (D337), and the blocks of the chunks
from -8 to 7 are compared. A block that differs in a way that waits on
something not in Calcite yet is counted under it, by the card it waits on; any other fails the
check.

It runs vanilla from the adapter (oracle/adapter.calx), with Mojang's EULA accepted in
the rig's scratch folder only (CAL-42), and needs the reports datagen writes to generated/26.3/
(oracle/datagen/README.md). --reuse compares the last recording again. Neither side's packets are
dumped to JSON, which for this many block updates runs to gigabytes.
"""

import argparse
import collections
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "bench"))
import sessions  # noqa: E402

CALCITE = HERE.parents[1]
REPORTS = CALCITE / "generated" / "26.3" / "datagen" / "reports"
CONFIG = "ticking"
sessions.CONFIGS[CONFIG] = sessions.Config({}, view=10, scenarios=("join",), world=sessions.SAVED_WORLD,
                                           spawn=(0, 100, 0), entities=False)
# The chunks compared: those the save has full, and the two rings it left part-way round them.
LOW, HIGH = -8, 7
# The Overworld's sections, from y -64.
SECTIONS, MIN_Y = 24, -64
# `ConnectionProtocol`'s number for play, as the bot records it (src/rig/session.calx).
PLAY = 4
# The blocks that fall, which come down as entities.
FALLING = {"sand", "red_sand", "gravel", "suspicious_sand", "suspicious_gravel", "anvil", "dragon_egg"}


def base(name):
    return name.split("[")[0]


# What waits on something not in Calcite yet, or comes of the levels' draws, which part from
# vanilla's here, with no tape to seed them again, each by vanilla's block and Calcite's. Since the
# blocks set after a chunk is sent count, some come of how long each server ran.
KNOWN = [
    ("precipitation's snow, laid where each server's own draws put it, and the grass under it (D340)",
     lambda v, c: {base(v), base(c)} == {"snow", "air"} or {v, c} == {"grass_block[snowy=true]", "grass_block[snowy=false]"}),
    ("random ticks, whose draws part from vanilla's while Calcite has few blocks' (CAL-106)",
     lambda v, c: {base(v), base(c)} == {"grass_block", "dirt"}),
    ("falling blocks, which come down as entities",
     lambda v, c: (v == "air" and base(c) in FALLING) or (base(v) in FALLING and base(c) not in FALLING)),
]


def varint(b, at):
    v = shift = 0
    while True:
        x = b[at]
        at += 1
        v |= (x & 0x7F) << shift
        shift += 7
        if not x & 0x80:
            return v, at


def container(b, at, entries, indirect_bits):
    """A paletted container's values, as 26.3 sends it: its bits, its palette unless it's single
    or global, then its longs, with no index across two."""
    bits = b[at]
    at += 1
    if bits == 0:
        v, at = varint(b, at)
        return [v] * entries, at
    palette = None
    if bits <= indirect_bits:
        n, at = varint(b, at)
        palette = []
        for _ in range(n):
            v, at = varint(b, at)
            palette.append(v)
    per = 64 // bits
    longs = (entries + per - 1) // per
    mask = (1 << bits) - 1
    out = []
    for k in range(longs):
        w = struct.unpack_from(">Q", b, at + 8 * k)[0]
        for j in range(per):
            if len(out) == entries:
                break
            out.append((w >> (j * bits)) & mask)
    at += 8 * longs
    return ([palette[i] for i in out] if palette is not None else out), at


def signed(v, bits):
    """`v`'s low `bits` bits as a signed number."""
    v &= (1 << bits) - 1
    return v - (1 << bits) if v >> (bits - 1) else v


def set_block(out, x, y, z, state):
    """The block at x, y, z set to `state` in the chunk it's in, if that was sent."""
    sections = out.get((x >> 4, z >> 4))
    s = (y - MIN_Y) >> 4
    if sections is not None and 0 <= s < SECTIONS:
        sections[s][((y & 15) << 8) | ((z & 15) << 4) | (x & 15)] = state


def chunks(side, chunk_id, updates=None):
    """Each chunk the side was sent, by its position: its sections' block states, by ID, with
    the blocks set since, if `updates` gives the IDs of `block_update` and
    `section_blocks_update`, in the order they came."""
    b = (sessions.SESSIONS / CONFIG / side / "join.bin").read_bytes()
    block_id, section_id = updates or (None, None)
    out = {}
    at = 0
    while at < len(b):
        state = b[at]
        n = struct.unpack_from(">I", b, at + 1)[0]
        body = b[at + 5:at + 5 + n]
        at += 5 + n
        if state != PLAY:
            continue
        kind, p = varint(body, 0)
        if kind == block_id:
            # `BlockPos.asLong`: x in the top 26 bits, z in the next 26, y in the low 12.
            packed = struct.unpack_from(">q", body, p)[0]
            block, _ = varint(body, p + 8)
            set_block(out, signed(packed >> 38, 26), signed(packed, 12), signed(packed >> 12, 26), block)
            continue
        if kind == section_id:
            # `SectionPos.asLong`: x in the top 22 bits, z in the next 22, y in the low 20; then
            # each block as its state over its place in the section, x, z and y, 4 bits each.
            packed = struct.unpack_from(">q", body, p)[0]
            sx, sy, sz = signed(packed >> 42, 22), signed(packed, 20), signed(packed >> 20, 22)
            count, p = varint(body, p + 8)
            for _ in range(count):
                v, p = varint(body, p)
                local = v & 0xFFF
                set_block(out, sx * 16 + (local >> 8), sy * 16 + (local & 15), sz * 16 + ((local >> 4) & 15), v >> 12)
            continue
        if kind != chunk_id:
            continue
        cx, cz = struct.unpack_from(">ii", body, p)
        p += 8
        maps, p = varint(body, p)
        for _ in range(maps):
            _, p = varint(body, p)
            longs, p = varint(body, p)
            p += 8 * longs
        size, p = varint(body, p)
        data = body[p:p + size]
        q = 0
        states = []
        for _ in range(SECTIONS):
            q += 4
            s, q = container(data, q, 4096, 8)
            _, q = container(data, q, 64, 3)
            states.append(s)
        out[(cx, cz)] = states
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reuse", action="store_true", help="compare the last recording again")
    parser.add_argument("--show", type=int, default=10, help="the differences shown of each kind")
    args = parser.parse_args()
    names = {}
    for block, info in json.loads((REPORTS / "blocks.json").read_text(encoding="utf-8")).items():
        for s in info["states"]:
            p = s.get("properties") or {}
            names[s["id"]] = block.removeprefix("minecraft:") + ("[" + ",".join(f"{k}={p[k]}" for k in sorted(p)) + "]" if p else "")
    packets = json.loads((REPORTS / "packets.json").read_text(encoding="utf-8"))
    play = packets["play"]["clientbound"]
    chunk_id = play["minecraft:level_chunk_with_light"]["protocol_id"]
    updates = (play["minecraft:block_update"]["protocol_id"], play["minecraft:section_blocks_update"]["protocol_id"])
    if not args.reuse:
        server, bot = sessions.build_calcite(sessions.find_calx())
        sessions.record(CONFIG, "vanilla", sessions.vanilla_argv(sessions.adapter()), bot, ("join",))
        sessions.record(CONFIG, "calcite", [str(server)], bot, ("join",))
    v, c = chunks("vanilla", chunk_id, updates), chunks("calcite", chunk_id, updates)
    compared = [pos for pos in sorted(set(v) & set(c)) if LOW <= pos[0] <= HIGH and LOW <= pos[1] <= HIGH]
    if len(compared) != (HIGH - LOW + 1) ** 2:
        sys.exit(f"ticking: only {len(compared)} of the chunks from {LOW} to {HIGH} were sent to both")
    known = collections.Counter()
    unknown = collections.Counter()
    examples = {}
    for pos in compared:
        for s in range(SECTIONS):
            a, b = v[pos][s], c[pos][s]
            if a == b:
                continue
            for i in range(4096):
                if a[i] == b[i]:
                    continue
                va, ca = names.get(a[i], str(a[i])), names.get(b[i], str(b[i]))
                at = (pos[0] * 16 + (i & 15), MIN_Y + s * 16 + (i >> 8), pos[1] * 16 + ((i >> 4) & 15))
                why = next((w for w, test in KNOWN if test(va, ca)), None)
                if why:
                    known[why] += 1
                else:
                    unknown[(va, ca)] += 1
                    examples.setdefault((va, ca), at)
    print(f"ticking: {len(compared)} chunks from {LOW} to {HIGH}, sent to both and compared")
    for why, n in known.most_common():
        print(f"  {n:6} waiting on {why}")
    for (va, ca), n in unknown.most_common(args.show):
        print(f"  {n:6} differ: vanilla {va}, Calcite {ca}, at {examples[(va, ca)]}")
    if unknown:
        sys.exit(f"ticking: {sum(unknown.values())} blocks differ")
    print("ticking: PASS, every block the same but those waiting on what isn't in Calcite yet")


if __name__ == "__main__":
    main()
