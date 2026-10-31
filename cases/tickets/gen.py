"""Writes cases/tickets/generated.json: random operations on a dimension's chunk tickets, and
saved `chunk_tickets` read, both those vanilla writes and broken ones.

    py -I cases/tickets/gen.py

Deterministic: everything comes from SplitMix64 seeded with SEED, so rerunning it gives the same
file.

The `random` cases add and take out tickets of every type at a pool of chunks, few or many, so
the table grows, shrinks and has keys taken out of it as stale tickets run out, which is where
vanilla's loop goes out of the table's order. The `stale` cases add mostly tickets that run out,
then purge them, many at a time, with some chunks' holders busy. The `saved` cases read
`chunk_tickets` as vanilla saves it, then activate and run the tickets, and the `broken` cases
read files with each field wrong in each way.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
from cases import splitmix64, write_file  # noqa: E402

SEED = 20261031
TYPES = ["player_spawn", "spawn_search", "dragon", "player_loading", "player_simulation", "forced", "portal",
         "ender_pearl", "unknown"]
TIMED = ["player_spawn", "spawn_search", "portal", "ender_pearl", "unknown"]


def signed64(x):
    return x - (1 << 64) if x >= 1 << 63 else x


def pack(x, z):
    return signed64((x & 0xFFFFFFFF) | ((z & 0xFFFFFFFF) << 32))


class Rng:
    def __init__(self, seed):
        self.r = splitmix64(seed)

    def next(self):
        return next(self.r)

    def below(self, n):
        return self.next() % n

    def chance(self, p):
        return self.below(1 << 20) < int(p * (1 << 20))

    def pick(self, items):
        return items[self.below(len(items))]


def pool(rng, size):
    """`size` chunks: near the origin, in a far corner, or spread over the world."""
    style = rng.below(3)
    out = []
    while len(out) < size:
        if style == 0:
            x, z = rng.below(21) - 10, rng.below(21) - 10
        elif style == 1:
            x, z = 1874999 - rng.below(30), -1874999 + rng.below(30)
        else:
            x, z = rng.below(3749999) - 1874999, rng.below(3749999) - 1874999
        if (x, z) not in out:
            out.append((x, z))
    return out


def level(rng):
    roll = rng.below(100)
    if roll < 80:
        return 22 + rng.below(23)
    if roll < 90:
        return 45 + rng.below(6)
    # Never below 0: the codec won't save one, and vanilla never makes one.
    return rng.below(22)


def ops_for(rng, chunks, count, timed_bias):
    ops = []
    for _ in range(count):
        x, z = rng.pick(chunks)
        c = str(pack(x, z))
        kind = rng.pick(TIMED) if rng.chance(timed_bias) else rng.pick(TYPES)
        roll = rng.below(1000)
        if roll < 380:
            ops.append(["add", c, kind, level(rng)])
        elif roll < 530:
            ops.append(["remove", c, kind, level(rng)])
        elif roll < 570:
            ops.append(["add_radius", kind, x, z, rng.below(12) - 1])
        elif roll < 590:
            ops.append(["remove_radius", kind, x, z, rng.below(12) - 1])
        elif roll < 640:
            ops.append(["forced", x, z, rng.chance(0.6)])
        elif roll < 655:
            ops.append(["replace_level", level(rng), kind])
        elif roll < 840:
            busy = [str(pack(*p)) for p in chunks if rng.chance(0.25)]
            ops.append(["purge", busy])
        elif roll < 880:
            ops.append(["level", c, rng.chance(0.5)])
        elif roll < 900:
            ops.append(["debug", c, rng.chance(0.5)])
        elif roll < 960:
            ops.append(["dump"])
        elif roll < 975:
            ops.append(["save"])
        else:
            ops.append(["deactivate"])
            if rng.chance(0.5):
                ops.append(["dump"])
            ops.append(["save"])
            ops.append(["activate"])
    ops.append(["dump"])
    ops.append(["save"])
    return ops


def snbt_ticket(x, z, kind, lvl, left):
    fields = [f"chunk_pos:[I;{x},{z}]", f"type:\"minecraft:{kind}\"", f"level:{lvl}"]
    if left != 0:
        fields.append(f"ticks_left:{left}L")
    return "{" + ",".join(fields) + "}"


def saved(rng, chunks, n):
    tickets = []
    for _ in range(n):
        x, z = rng.pick(chunks)
        kind = rng.pick(["forced", "portal"] if rng.chance(0.8) else TYPES)
        left = rng.below(301) if kind == "portal" else 0
        if rng.chance(0.05):
            left = rng.pick([-1, -5, 1 << 40, -(1 << 63)])
        tickets.append(snbt_ticket(x, z, kind, level(rng), left))
    return "{data:{tickets:[" + ",".join(tickets) + "]},DataVersion:5023}"


# Saved files broken in each way: `data` and `tickets` that aren't what they should be, and each
# field of a ticket missing or of each wrong kind, beside tickets that can be read.
GOOD = "{chunk_pos:[I;1,2],type:\"minecraft:portal\",level:30,ticks_left:7L}"
BROKEN = [
    "{DataVersion:5023}",
    "{data:5,DataVersion:5023}",
    "{data:[1,2],DataVersion:5023}",
    "{data:{},DataVersion:5023}",
    "{data:{tickets:5}}",
    "{data:{tickets:\"x\"}}",
    "{data:{tickets:{a:1}}}",
    "{data:{tickets:[]}}",
    "{data:{tickets:[I;1,2]}}",
    "{data:{tickets:[B;1b]}}",
    "{data:{tickets:[L;1L,2L]}}",
    "{data:{tickets:[1,2," + GOOD + "]}}",
    "{data:{tickets:[\"a\"," + GOOD + "]}}",
    "{data:{tickets:[{}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2]}]}}",
    "{data:{tickets:[{type:\"minecraft:forced\",level:31}]}}",
    "{data:{tickets:[{chunk_pos:[I;1],type:\"minecraft:forced\",level:31}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2,3],type:\"minecraft:forced\",level:31}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2,3],type:\"minecraft:nope\",level:31}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2,3,4],type:\"minecraft:forced\"}]}}",
    "{data:{tickets:[{chunk_pos:[1,2],type:\"minecraft:forced\",level:31}]}}",
    "{data:{tickets:[{chunk_pos:[1b,2s],type:\"minecraft:forced\",level:31}]}}",
    "{data:{tickets:[{chunk_pos:[L;1L,2L],type:\"minecraft:forced\",level:31}]}}",
    "{data:{tickets:[{chunk_pos:[B;1b,2b],type:\"minecraft:forced\",level:31}]}}",
    "{data:{tickets:[{chunk_pos:[\"a\",2],type:\"minecraft:forced\",level:31}]}}",
    "{data:{tickets:[{chunk_pos:\"1,2\",type:\"minecraft:forced\",level:31}]}}",
    "{data:{tickets:[{chunk_pos:{x:1,z:2},type:\"minecraft:forced\",level:31}]}}",
    "{data:{tickets:[{chunk_pos:7,type:\"minecraft:forced\",level:31}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2],type:\"forced\",level:31}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2],type:\"minecraft:nope\",level:31}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2],type:\"Bad:Name\",level:31}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2],type:\"a b\",level:31}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2],type:5,level:31}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2],type:\"minecraft:forced\"}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2],type:\"minecraft:forced\",level:-1}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2],type:\"minecraft:forced\",level:31b}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2],type:\"minecraft:forced\",level:31L}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2],type:\"minecraft:forced\",level:4294967327L}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2],type:\"minecraft:forced\",level:31.9d}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2],type:\"minecraft:forced\",level:-0.5f}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2],type:\"minecraft:forced\",level:\"31\"}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2],type:\"minecraft:forced\",level:[31]}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2],type:\"minecraft:portal\",level:30,ticks_left:5}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2],type:\"minecraft:portal\",level:30,ticks_left:5.7d}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2],type:\"minecraft:portal\",level:30,ticks_left:1e30d}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2],type:\"minecraft:portal\",level:30,ticks_left:\"5\"}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2],type:\"minecraft:portal\",level:30,ticks_left:0L}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2],type:\"minecraft:portal\",level:30,ticks_left:-3L}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2],type:\"minecraft:nope\",level:-1,ticks_left:\"x\"}]}}",
    "{data:{tickets:[{chunk_pos:[I;1,2,3],type:5,level:\"x\"}]}}",
    "{data:{tickets:[{chunk_pos:[I;1],type:5,level:\"x\"}]}}",
    "{data:{tickets:[{type:5},{chunk_pos:[I;1,2,3],type:\"minecraft:forced\",level:31},5," + GOOD + ",{level:-2}]}}",
    "{data:{tickets:[" + GOOD + "," + GOOD + ",{chunk_pos:[I;1,2],type:\"minecraft:portal\",level:30}]},DataVersion:4000}",
    "{data:{tickets:[{chunk_pos:[I;1,2],type:\"minecraft:portal\",level:30,extra:1b}],other:5}}",
]


def main():
    rng = Rng(SEED)
    cases = []
    for i in range(120):
        chunks = pool(rng, rng.pick([2, 4, 8, 16, 40, 90]))
        cases.append({"id": f"random-{i}", "input": {"ops": ops_for(rng, chunks, 40 + rng.below(160), 0.2)}})
    for i in range(60):
        chunks = pool(rng, rng.pick([6, 12, 30, 70]))
        ops = []
        for _ in range(len(chunks) * 2):
            x, z = rng.pick(chunks)
            ops.append(["add", str(pack(x, z)), rng.pick(TIMED + ["forced", "player_loading"]), level(rng)])
        ops.append(["dump"])
        for _ in range(8 + rng.below(30)):
            busy = [str(pack(*p)) for p in chunks if rng.chance(0.15)]
            ops.append(["purge", busy])
            if rng.chance(0.3):
                ops.append(["dump"])
        ops += ops_for(rng, chunks, 20 + rng.below(40), 0.7)
        cases.append({"id": f"stale-{i}", "input": {"ops": ops}})
    for i in range(40):
        chunks = pool(rng, rng.pick([3, 10, 25, 60]))
        ops = [["load", saved(rng, chunks, rng.below(len(chunks) * 3 + 1))], ["dump"], ["activate"], ["dump"]]
        ops += ops_for(rng, chunks, 10 + rng.below(60), 0.3)
        cases.append({"id": f"saved-{i}", "input": {"ops": ops}})
    for i, snbt in enumerate(BROKEN):
        cases.append({"id": f"broken-{i}", "input": {"ops": [["load", snbt], ["dump"], ["activate"], ["dump"], ["save"]]}})
    write_file(HERE / "generated.json", "tickets", f"cases/tickets/gen.py, seed {SEED}", cases)


if __name__ == "__main__":
    main()
