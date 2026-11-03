"""Watches chunks reach a real client (CAL-99): a relay between the client and a server that reads
the frames each way, as an offline server sends them, and times what comes.

    py -I rig/runner/chunkwatch.py --listen PORT --server HOST:PORT [--mbit N] [--ms N] [--out FILE] [--dump FILE]

realclient.py runs it in its own process with --watch. The client connects to the relay, the
relay to the server, and every byte goes through as it came. On the way it reads each frame: the
handshake, login, configuration and play, with the compression the server turns on, so it works
with any server, Calcite or vanilla, in offline mode. An online server's frames are encrypted, so
they're passed through unread.

From the frames it times, for the join and for each respawn packet after it, each a phase:

- the chunks the client was sent, `level_chunk_with_light`, and their bytes as framed;
- each `chunk_batch_finished`, and each `chunk_batch_received` the client answers it with, which
  it sends once it has the batch, with the chunks a tick it asks for; it answers each batch once,
  in order, so the nth answer is the nth batch's;
- when the last chunk of the phase was sent, and when the client answered the batch it was in:
  the client had every chunk then; and when it had half of them, 90% and 95%, which leave out
  the last few that took longer to make;
- with --mbit, how long what the server sent waited for the link behind what it sent before,
  which anything it sent then, such as another player's move, waited too.

With --mbit, what the server sends goes to the client at that many megabits a second at most,
and with --ms, each way N milliseconds late, as a home link would, so the times are those of a
player at the other end of one. The bytes go in pieces of 4 KB, one after another at the rate,
each late by the latency however many are on the way, so a batch takes the client as long to
come as it would on such a link. Times are from the relay's clock, as it hands the bytes on.

With --dump, each `level_chunk_with_light` the client's sent is written to the file as it was
before it was compressed, its packet ID and all, after its length as 4 bytes little-endian, so
compressors can be compared on the chunks a real client was sent.

With --view N, it also follows the player: where the client says it is, from its moves and the
server's teleports, and which chunks it has, each it was sent until the server has it forget it.
Four times a second, as the player moves, it counts the chunks of the circle of N chunks about
the player's that the client has, and how far the nearest it doesn't is. A phase's report then
says how much of its view the client had while it moved, and how fast it went, so a flight shows
whether the chunks kept up (CAL-94). realclient.py starts a phase of its own, `flight`, as the
player starts to fly forward, and `after` as they stop.
"""

import argparse
import json
import math
import queue
import re
import socket
import struct
import sys
import threading
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
CALCITE = HERE.parents[1]


def packet_ids():
    """Each state's packet names in ID order, each way, read from src/protocol/ids.calx, which
    oracle/datagen writes from vanilla's packets.json."""
    text = (CALCITE / "src" / "protocol" / "ids.calx").read_text(encoding="utf-8")
    ids = {}
    for state in ("Handshake", "Status", "Login", "Configuration", "Play"):
        at = text.index(f"State.{state} => {{")
        lists = re.findall(r"return \[(.*?)\]", text[at:], re.S)[:2]
        server, client = ([s.strip().strip('"') for s in body.split(",") if s.strip()] for body in lists)
        ids[state] = {"serverbound": server, "clientbound": client}
    return ids


def varint(data, at):
    value = shift = 0
    while True:
        if at >= len(data):
            return None, at
        b = data[at]
        at += 1
        value |= (b & 0x7F) << shift
        if not b & 0x80:
            break
        shift += 7
        if shift > 35:
            raise ValueError("a varint too long")
    if value >= 1 << 31:
        value -= 1 << 32
    return value, at


class Watch:
    """What one connection's frames come to, each way, as phases."""

    def __init__(self, ids, dump=None, view=None):
        self.ids = ids
        self.dump = dump
        # With a view: the chunks the client has, where it last said it was, and each sample of
        # how much of the view about it it had: when, where, how many, and how far the nearest
        # it didn't have was, or None.
        self.view = view
        self.have = set()
        self.samples = []
        self.sampled = -1.0
        # Each chunk of the circle of `view` about the player's, by how far it is, nearest first.
        self.circle = sorted((math.hypot(dx, dz), dx, dz) for dx in range(-(view or 0), (view or 0) + 1)
                             for dz in range(-(view or 0), (view or 0) + 1) if dx * dx + dz * dz <= (view or 0) ** 2)
        self.lock = threading.Lock()
        self.state = {"serverbound": "Handshake", "clientbound": "Handshake"}
        self.threshold = -1
        self.encrypted = False
        self.start = time.monotonic()
        self.phases = []
        # Every batch finished, and every answer, in order: the client answers each batch once, in
        # the order they came, so the answer to the nth batch is the nth.
        self.batches = []
        self.answers = []
        # With --mbit, each piece the server sent: when, and how long it waited for the link.
        self.queued = []

    def phase(self, kind, t):
        self.phases.append({"kind": kind, "at": t, "chunks": 0, "chunk_bytes": 0, "bytes": 0,
                            "batches": [], "answers": [], "last_chunk": None, "last_batch": None,
                            "first_batch": len(self.batches), "forgotten": 0})

    def frame(self, way, frame, size, t):
        """A whole frame, without its length, `size` bytes on the wire with it, handed on at `t`."""
        if self.encrypted:
            return
        at = 0
        body = frame
        if self.threshold >= 0:
            data_length, at = varint(frame, 0)
            body = zlib.decompress(frame[at:]) if data_length else frame[at:]
        packet_id, at = varint(body, 0)
        names = self.ids[self.state[way]][way]
        name = names[packet_id] if 0 <= packet_id < len(names) else f"#{packet_id}"
        state = self.state[way]
        if self.phases and way == "clientbound":
            self.phases[-1]["bytes"] += size
            if self.dump and name == "level_chunk_with_light":
                self.dump.write(body)
        if state == "Handshake" and name == "intention":
            # The protocol version, the address, the port, then where it's going.
            _, at = varint(body, at)
            length, at = varint(body, at)
            at += length + 2
            intent, at = varint(body, at)
            nxt = {1: "Status", 2: "Login", 3: "Login"}.get(intent, "Login")
            self.state = {"serverbound": nxt, "clientbound": nxt}
        elif state == "Login" and name == "hello" and way == "clientbound":
            self.encrypted = True
        elif state == "Login" and name == "login_compression":
            self.threshold, _ = varint(body, at)
        elif state == "Login" and name == "login_finished":
            self.state["clientbound"] = "Configuration"
        elif state == "Login" and name == "login_acknowledged":
            self.state["serverbound"] = "Configuration"
        elif state == "Configuration" and name == "finish_configuration":
            self.state[way] = "Play"
        elif state == "Play":
            self.play(way, name, body[at:], size, t)

    def play(self, way, name, rest, size, t):
        if way == "clientbound" and name == "login":
            self.phase("join", t)
            return
        if way == "clientbound" and name == "respawn":
            # Another dimension: the client lets every chunk it had go.
            self.have.clear()
            self.phase("respawn", t)
            return
        if not self.phases:
            return
        p = self.phases[-1]
        if way == "clientbound":
            if name == "level_chunk_with_light":
                p["chunks"] += 1
                p["chunk_bytes"] += size
                p["last_chunk"] = t
                self.have.add(struct.unpack(">ii", rest[:8]))
            elif name == "chunk_batch_finished":
                n, _ = varint(rest, 0)
                p["batches"].append((t, n))
                if n:
                    p["last_batch"] = len(self.batches)
                self.batches.append(t)
            elif name == "forget_level_chunk":
                p["forgotten"] += 1
                # A chunk's position as one long, its x in the low half.
                packed = struct.unpack(">q", rest[:8])[0]
                x = packed & 0xFFFFFFFF
                self.have.discard((x - (1 << 32) if x >= 1 << 31 else x, packed >> 32))
            elif name == "player_position":
                # A teleport: its ID, then where to, which the server's are, not relative.
                _, at = varint(rest, 0)
                x, _, z = struct.unpack(">ddd", rest[at:at + 24])
                self.moved(x, z, t)
        elif name == "chunk_batch_received" and len(rest) >= 4:
            rate = struct.unpack(">f", rest[:4])[0]
            p["answers"].append((t, rate))
            self.answers.append(t)
        elif name in ("move_player_pos", "move_player_pos_rot"):
            x, _, z = struct.unpack(">ddd", rest[:24])
            self.moved(x, z, t)

    def moved(self, x, z, t):
        """The player is at `x`, `z`: four times a second, how much of the view about them the
        client has."""
        if not self.view or t - self.sampled < 0.25:
            return
        self.sampled = t
        cx, cz = math.floor(x) >> 4, math.floor(z) >> 4
        had = 0
        nearest = None
        for distance, dx, dz in self.circle:
            if (cx + dx, cz + dz) in self.have:
                had += 1
            elif nearest is None:
                nearest = distance
        self.samples.append((t, x, z, had, nearest))

    def report(self):
        out = []
        for i, p in enumerate(self.phases):
            end = self.phases[i + 1]["at"] if i + 1 < len(self.phases) else float("inf")
            waits = sorted(q for t, q in self.queued if p["at"] <= t < end)
            last = p["last_chunk"]
            b = p["last_batch"]
            had = self.answers[b] if b is not None and b < len(self.answers) else None
            rates = [r for _, r in p["answers"]]
            # When the client had each share of the phase's chunks: the answer to the batch that
            # took it that far.
            shares = {}
            for share in (50, 90, 95):
                got = 0
                for j, (_, n) in enumerate(p["batches"]):
                    got += n
                    if got * 100 >= share * p["chunks"]:
                        g = p["first_batch"] + j
                        if g < len(self.answers):
                            shares[share] = round(self.answers[g] - p["at"], 3)
                        break
            out.append({
                "phase": p["kind"],
                "chunks": p["chunks"],
                "chunk_kib": round(p["chunk_bytes"] / 1024, 1),
                "bytes_a_chunk": round(p["chunk_bytes"] / p["chunks"]) if p["chunks"] else 0,
                "mib_sent": round(p["bytes"] / 1048576, 2),
                "batches": len(p["batches"]),
                "last_chunk_s": round(last - p["at"], 3) if last is not None else None,
                "client_had_all_s": round(had - p["at"], 3) if had is not None else None,
                "client_had_half_s": shares.get(50),
                "client_had_90_s": shares.get(90),
                "client_had_95_s": shares.get(95),
                # How long what the server sent waited for the link, in milliseconds: the median,
                # the 95th percentile and the most.
                "link_wait_ms": [round(waits[len(waits) // 2] * 1000, 1), round(waits[len(waits) * 95 // 100] * 1000, 1),
                                 round(waits[-1] * 1000, 1)] if waits else None,
                "asked_a_tick": [round(min(rates), 1), round(max(rates), 1)] if rates else None,
                "forgotten": p["forgotten"],
                # Each batch's time and chunks, and each answer's time and the chunks a tick it
                # asked for, from the phase's start.
                "batch_times": [[round(t - p["at"], 3), n] for t, n in p["batches"]],
                "answer_times": [[round(t - p["at"], 3), round(r, 1)] for t, r in p["answers"]],
            })
            out[-1].update(self.view_report(p, end))
        return out

    def view_report(self, p, end):
        """With a view, how much of it the client had in the phase, as the player moved."""
        samples = [s for s in self.samples if p["at"] <= s[0] < end]
        if not self.view or len(samples) < 2:
            return {}
        size = len(self.circle)
        shares = [had / size * 100 for _, _, _, had, _ in samples]
        missing = sorted(n for *_, n in samples if n is not None)
        blocks = sum(math.hypot(b[1] - a[1], b[2] - a[2]) for a, b in zip(samples, samples[1:]))
        seconds = samples[-1][0] - samples[0][0]
        return {
            "view_chunks": size,
            "seconds": round(seconds, 1),
            "blocks_a_second": round(blocks / seconds, 1) if seconds else 0,
            "chunks_a_second": round(p["chunks"] / seconds, 1) if seconds else 0,
            # The share of the view the client had, in percent: the mean and the least, and
            # how many samples had all of it.
            "had_of_view": [round(sum(shares) / len(shares), 1), round(min(shares), 1)],
            "whole_view_samples": f"{len(samples) - len(missing)} of {len(samples)}",
            # How far the nearest chunk missing was, in chunks, where one was: the median and the
            # least.
            "nearest_missing": [round(missing[len(missing) // 2], 1), round(missing[0], 1)] if missing else None,
            # Each sample: when, from the phase's start, the share of the view, and the nearest
            # missing.
            "view_samples": [[round(t - p["at"], 2), round(had / size * 100, 1), n and round(n, 1)]
                             for t, _, _, had, n in samples],
        }


class Way(threading.Thread):
    """One way of a connection, as a link carries it: what's read from `src` is cut into pieces of
    at most PIECE bytes, each sent at the link's rate once the one before it is, then late by its
    latency. Another thread hands each on to `dst` once it's due, so reading never waits on the
    latency, and reads its frames as it does."""

    PIECE = 4096

    def __init__(self, src, dst, watch, way, mbit, ms):
        super().__init__(daemon=True)
        self.src, self.dst, self.watch, self.way = src, dst, watch, way
        self.rate = mbit * 1e6 / 8 if mbit else None
        self.delay = ms / 1000
        self.buffer = b""
        self.free_at = 0.0
        self.due = queue.Queue()

    def run(self):
        threading.Thread(target=self.hand_on, daemon=True).start()
        try:
            while True:
                data = self.src.recv(65536)
                if not data:
                    break
                now = time.monotonic()
                if not self.rate and not self.delay:
                    self.due.put((now, data))
                    continue
                for at in range(0, len(data), self.PIECE):
                    piece = data[at:at + self.PIECE]
                    sent = now
                    if self.rate:
                        start = max(self.free_at, now)
                        self.watch.queued.append((now, start - now))
                        self.free_at = start + len(piece) / self.rate
                        sent = self.free_at
                    self.due.put((sent + self.delay, piece))
        except OSError:
            pass
        self.due.put(None)

    def hand_on(self):
        try:
            while True:
                item = self.due.get()
                if item is None:
                    break
                due, data = item
                wait = due - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                # Read first, so compression the server turns on is on before the client answers.
                self.read(data, time.monotonic())
                self.dst.sendall(data)
        except OSError:
            pass
        finally:
            for s in (self.src, self.dst):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def read(self, data, t):
        self.buffer += data
        while True:
            length, at = varint(self.buffer, 0)
            if length is None or len(self.buffer) < at + length:
                return
            frame = self.buffer[at:at + length]
            self.buffer = self.buffer[at + length:]
            with self.watch.lock:
                try:
                    self.watch.frame(self.way, frame, at + length, t)
                except (ValueError, zlib.error, IndexError):
                    self.watch.encrypted = True


class Dump:
    """A file of chunk packets, each after its length, from every connection."""

    def __init__(self, path):
        self.file = open(path, "wb")
        self.lock = threading.Lock()
        self.count = 0

    def write(self, body):
        with self.lock:
            self.file.write(struct.pack("<I", len(body)) + body)
            self.count += 1

    def close(self):
        with self.lock:
            self.file.close()


class Relay:
    """Listens on `port` and relays each connection to `server`, watching each."""

    def __init__(self, port, server, mbit=None, ms=0, dump=None, view=None):
        self.ids = packet_ids()
        self.dump = Dump(dump) if dump else None
        self.server = server
        self.mbit, self.ms = mbit, ms
        self.view = view
        self.watches = []
        self.listener = socket.create_server(("127.0.0.1", port))
        threading.Thread(target=self.accept, daemon=True).start()

    def accept(self):
        while True:
            try:
                client, _ = self.listener.accept()
            except OSError:
                return
            upstream = socket.create_connection(self.server)
            for s in (client, upstream):
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            watch = Watch(self.ids, self.dump, self.view)
            self.watches.append(watch)
            Way(client, upstream, watch, "serverbound", None, self.ms).start()
            Way(upstream, client, watch, "clientbound", self.mbit, self.ms).start()

    def mark(self, kind):
        """Starts a phase named `kind` now on each connection that's playing."""
        t = time.monotonic()
        for w in self.watches:
            with w.lock:
                if w.phases:
                    w.phase(kind, t)

    def last_chunk(self):
        """When the last chunk any connection was sent was handed on, or None."""
        times = [p["last_chunk"] for w in self.watches for p in w.phases if p["last_chunk"] is not None]
        return max(times) if times else None

    def report(self):
        """Each connection that got to play, its phases."""
        return [w.report() for w in self.watches if w.phases]

    def close(self):
        self.listener.close()
        if self.dump:
            self.dump.close()


def main():
    parser = argparse.ArgumentParser(description="Relays a client to a server and times the chunks it's sent.")
    parser.add_argument("--listen", type=int, required=True)
    parser.add_argument("--server", required=True, help="HOST:PORT")
    parser.add_argument("--mbit", type=float, help="the most the server's side sends, in megabits a second")
    parser.add_argument("--ms", type=float, default=0, help="milliseconds each way is late")
    parser.add_argument("--out", help="a file the report's written to as JSON, as it's stopped")
    parser.add_argument("--dump", help="a file each chunk packet's written to, as it was before it was compressed")
    parser.add_argument("--view", type=int, help="follow the player, and how much of the view of this many chunks about them the client has")
    args = parser.parse_args()
    host, port = args.server.rsplit(":", 1)
    relay = Relay(args.listen, (host, int(port)), args.mbit, args.ms, args.dump, args.view)
    print(f"relaying 127.0.0.1:{args.listen} to {args.server}; Ctrl+C to stop and report")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    report = relay.report()
    relay.close()
    print(json.dumps(report, indent=1))
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=1), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
