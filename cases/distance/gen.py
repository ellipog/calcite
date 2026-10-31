"""Writes cases/distance/generated.json: players coming, going and walking about, tickets added
and taken out, and the view and simulation distances changing, on a dimension's distance
manager, with its dispatcher, its main thread and its chunks' entities ticking run in random
interleavings.

    py -I cases/distance/gen.py

Deterministic: everything comes from SplitMix64 seeded with SEED, so rerunning it gives the same
file.

Each case is a list of operations. Players join, leave and walk, a chunk or a jump at a time.
Tickets of every type come and go at levels that load a few hundred to a few thousand chunks.
The updates run, the dispatcher's jobs and the main thread's tasks run a few at a time or all at
once, the holders waited for tick their entities, a few or all at once or one by one, and the
dropped holders move out and unload. The cases ask whether players are near chunks and how many
chunks they spawn in, and dump the manager's state as they go, briefly, and in full at the end,
after rounds that let it settle.

The players stay within a few hundred chunks of 0, so no holder is out of vanilla's bounds, and
a player only leaves the chunk it's in, since vanilla fails on any other.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
from cases import splitmix64, write_file  # noqa: E402

SEED = 20261031
TYPES = ["player_spawn", "spawn_search", "dragon", "player_loading", "player_simulation", "forced",
         "portal", "ender_pearl", "unknown"]
BIG = 1 << 20


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


class Case:
    """A case's operations, with where its players are, so each leaves the chunk it's in."""

    def __init__(self, rng, span):
        self.rng = rng
        self.span = span
        self.ops = []
        self.players = {}
        self.next_id = 1
        self.tickets = []
        self.briefs = 0

    def chunk(self):
        rng = self.rng
        if self.players and rng.chance(0.7):
            x, z = rng.pick(sorted(self.players.values()))
            d = rng.pick([0, 1, 2, 4, 8, 14])
            return x + rng.below(2 * d + 1) - d, z + rng.below(2 * d + 1) - d
        return rng.below(2 * self.span + 1) - self.span, rng.below(2 * self.span + 1) - self.span

    def join(self, at=None):
        rng = self.rng
        # Sometimes a player that left comes back, as the adapter keeps it.
        gone = [i for i in range(1, self.next_id) if i not in self.players]
        if gone and rng.chance(0.3):
            player = rng.pick(gone)
        else:
            player = self.next_id
            self.next_id += 1
        x, z = at if at else self.chunk()
        self.players[player] = (x, z)
        self.ops.append(["player", player, x, z])

    def leave(self):
        player = self.rng.pick(sorted(self.players))
        x, z = self.players.pop(player)
        self.ops.append(["unplayer", player, x, z])

    def walk(self):
        rng = self.rng
        player = rng.pick(sorted(self.players))
        x, z = self.players[player]
        if rng.chance(0.85):
            dx, dz = rng.pick([(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1)])
        else:
            dx, dz = rng.below(41) - 20, rng.below(41) - 20
        nx = max(-self.span, min(self.span, x + dx))
        nz = max(-self.span, min(self.span, z + dz))
        self.ops.append(["unplayer", player, x, z])
        self.players[player] = (nx, nz)
        self.ops.append(["player", player, nx, nz])

    def ticket(self):
        rng = self.rng
        if self.tickets and rng.chance(0.45):
            t = rng.pick(self.tickets)
            if rng.chance(0.85):
                self.tickets.remove(t)
            self.ops.append(["unticket", *t])
            return
        r = rng.below(100)
        if r < 35:
            level = 31
        elif r < 50:
            level = 33
        elif r < 80:
            level = 32 + rng.below(13)
        elif r < 95:
            level = 22 + rng.below(9)
        else:
            level = 12 + rng.below(10)
        x, z = self.chunk()
        t = [rng.pick(TYPES), level, x, z]
        self.tickets.append(t)
        self.ops.append(["ticket", *t])

    def count(self):
        return self.rng.pick([1, 1, 1, 2, 3, 4, 6, 10, 40, BIG])

    def step(self, mix):
        """One operation, from `mix`'s weights."""
        rng = self.rng
        kinds, weights = zip(*mix)
        r = rng.below(sum(weights))
        for kind, w in zip(kinds, weights):
            if r < w:
                break
            r -= w
        if kind == "join":
            if len(self.players) < 4:
                self.join()
            else:
                self.walk()
        elif kind == "leave":
            if self.players:
                self.leave()
        elif kind == "walk":
            if self.players:
                self.walk()
        elif kind == "view":
            self.ops.append(["view", rng.pick([0, 1, 2, 2, 3, 3, 3, 4, 5, 6])])
        elif kind == "simulation":
            self.ops.append(["simulation", rng.pick([0, 2, 5, 8, 10, 12, 32])])
        elif kind == "ticket":
            self.ticket()
        elif kind == "update":
            self.ops.append(["update"])
        elif kind == "dispatch":
            self.ops.append(["dispatch", self.count()])
        elif kind == "main":
            self.ops.append(["main", self.count()])
        elif kind == "ready":
            if rng.chance(0.75):
                self.ops.append(["ready_first", self.count()])
            else:
                self.ops.append(["ready", *self.chunk()])
        elif kind == "drop":
            self.ops.append(["drop"])
        elif kind == "unload":
            self.ops.append(["unload", self.count()])
        elif kind == "promote":
            self.ops.append(["promote"])
        elif kind == "nearby":
            if rng.chance(0.8):
                self.ops.append(["nearby", *self.chunk()])
            else:
                self.ops.append(["spawn_count"])
        elif kind == "brief":
            if self.briefs < 6:
                self.briefs += 1
                self.ops.append(["brief"])

    def settle(self, rounds):
        """Rounds that run everything there is and have every chunk waited for tick its
        entities, enough for the chunks in view to get their tickets. Half the cases update
        twice a round, so the dispatcher waits on the holders before they're ready."""
        updates = [["update"]] * self.rng.pick([1, 2])
        for _ in range(rounds):
            self.ops += updates + [["dispatch", BIG], ["main", BIG]] * 4 + [["ready_first", BIG]]
        self.ops.append(["update"])

    def finish(self, view):
        n = max(1, len(self.players))
        self.settle(min(250, (2 * view + 1) ** 2 * n + 30))
        self.ops.append(["dump"])
        self.ops += [["drop"], ["unload", BIG], ["promote"], ["promote"], ["brief"]]


# The weights of each kind of operation, by the kind of case.
STEADY = [("update", 30), ("dispatch", 25), ("main", 25), ("ready", 15), ("brief", 2), ("nearby", 3)]
WALK = STEADY + [("walk", 12), ("drop", 3), ("unload", 3), ("promote", 1)]
CROWD = WALK + [("join", 4), ("leave", 3), ("view", 3), ("simulation", 2)]
TICKETS = STEADY + [("ticket", 25), ("drop", 4), ("unload", 4), ("promote", 2)]
EVERYTHING = CROWD + [("ticket", 10)]


def case(rng, name, mix, views, joins, steps, span=40):
    c = Case(rng, span)
    view = rng.pick(views)
    if rng.chance(0.3):
        c.ops.append(["simulation", rng.pick([2, 5, 8, 12])])
    if rng.chance(0.5):
        c.ops.append(["view", view])
    for _ in range(joins):
        c.join()
    if not rng.chance(0.5):
        c.ops.append(["view", view])
    for _ in range(steps):
        c.step(mix)
    largest = max([view] + [op[1] for op in c.ops if op[0] == "view"])
    c.finish(largest)
    return {"id": name, "input": {"ops": c.ops}}


def main():
    rng = Rng(SEED)
    cases = []
    for i in range(20):
        cases.append(case(rng, f"join-{i}", STEADY, [0, 1, 2, 3, 4], 1, rng.pick([20, 60, 150])))
    for i in range(20):
        cases.append(case(rng, f"walk-{i}", WALK, [2, 3, 4], 1, rng.pick([60, 150, 300])))
    for i in range(16):
        cases.append(case(rng, f"crowd-{i}", CROWD, [1, 2, 3], 1 + rng.below(3), rng.pick([80, 200, 400]), span=12))
    for i in range(16):
        cases.append(case(rng, f"tickets-{i}", TICKETS, [2, 3], rng.below(2), rng.pick([40, 120, 250]), span=20))
    for i in range(30):
        cases.append(case(rng, f"random-{i}", EVERYTHING, [0, 2, 3, 4], rng.below(3), rng.pick([100, 250, 500]), span=16))
    write_file(HERE / "generated.json", "distance", f"cases/distance/gen.py, seed {SEED}", cases)


if __name__ == "__main__":
    main()
