"""Watches chunks reach a real client (CAL-99): a relay between the client and a server that reads
the frames each way, as an offline server sends them, and times what comes.

    py -I rig/runner/chunkwatch.py --listen PORT --server HOST:PORT [--mbit N] [--ms N] [--out FILE]

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
  the client had every chunk then.

With --mbit, what the server sends goes to the client at that many megabits a second at most,
and with --ms, each way N milliseconds late, as a home link would, so the times are those of a
player at the other end of one. Times are from the relay's clock, as it hands the bytes on.
"""

import argparse
import json
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

    def __init__(self, ids):
        self.ids = ids
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

    def phase(self, kind, t):
        self.phases.append({"kind": kind, "at": t, "chunks": 0, "chunk_bytes": 0, "bytes": 0,
                            "batches": [], "answers": [], "last_chunk": None, "last_batch": None,
                            "forgotten": 0})

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
            elif name == "chunk_batch_finished":
                n, _ = varint(rest, 0)
                p["batches"].append((t, n))
                if n:
                    p["last_batch"] = len(self.batches)
                self.batches.append(t)
            elif name == "forget_level_chunk":
                p["forgotten"] += 1
        elif name == "chunk_batch_received" and len(rest) >= 4:
            rate = struct.unpack(">f", rest[:4])[0]
            p["answers"].append((t, rate))
            self.answers.append(t)

    def report(self):
        out = []
        for p in self.phases:
            last = p["last_chunk"]
            b = p["last_batch"]
            had = self.answers[b] if b is not None and b < len(self.answers) else None
            rates = [r for _, r in p["answers"]]
            out.append({
                "phase": p["kind"],
                "chunks": p["chunks"],
                "chunk_kib": round(p["chunk_bytes"] / 1024, 1),
                "bytes_a_chunk": round(p["chunk_bytes"] / p["chunks"]) if p["chunks"] else 0,
                "mib_sent": round(p["bytes"] / 1048576, 2),
                "batches": len(p["batches"]),
                "last_chunk_s": round(last - p["at"], 3) if last is not None else None,
                "client_had_all_s": round(had - p["at"], 3) if had is not None else None,
                "asked_a_tick": [round(min(rates), 1), round(max(rates), 1)] if rates else None,
                "forgotten": p["forgotten"],
            })
        return out


class Way(threading.Thread):
    """One way of a connection: reads from `src`, holds each read until it's due, by the link's
    latency and rate, then reads its frames and hands it on to `dst`."""

    def __init__(self, src, dst, watch, way, mbit, ms):
        super().__init__(daemon=True)
        self.src, self.dst, self.watch, self.way = src, dst, watch, way
        self.rate = mbit * 1e6 / 8 if mbit else None
        self.delay = ms / 1000
        self.buffer = b""
        self.free_at = 0.0

    def run(self):
        try:
            while True:
                data = self.src.recv(65536)
                if not data:
                    break
                due = time.monotonic() + self.delay
                if self.rate:
                    self.free_at = max(self.free_at, due) + len(data) / self.rate
                    due = self.free_at
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


class Relay:
    """Listens on `port` and relays each connection to `server`, watching each."""

    def __init__(self, port, server, mbit=None, ms=0):
        self.ids = packet_ids()
        self.server = server
        self.mbit, self.ms = mbit, ms
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
            watch = Watch(self.ids)
            self.watches.append(watch)
            Way(client, upstream, watch, "serverbound", None, self.ms).start()
            Way(upstream, client, watch, "clientbound", self.mbit, self.ms).start()

    def report(self):
        """Each connection that got to play, its phases."""
        return [w.report() for w in self.watches if w.phases]

    def close(self):
        self.listener.close()


def main():
    parser = argparse.ArgumentParser(description="Relays a client to a server and times the chunks it's sent.")
    parser.add_argument("--listen", type=int, required=True)
    parser.add_argument("--server", required=True, help="HOST:PORT")
    parser.add_argument("--mbit", type=float, help="the most the server's side sends, in megabits a second")
    parser.add_argument("--ms", type=float, default=0, help="milliseconds each way is late")
    parser.add_argument("--out", help="a file the report's written to as JSON, as it's stopped")
    args = parser.parse_args()
    host, port = args.server.rsplit(":", 1)
    relay = Relay(args.listen, (host, int(port)), args.mbit, args.ms)
    print(f"relaying 127.0.0.1:{args.listen} to {args.server}; Ctrl+C to stop and report")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    report = relay.report()
    print(json.dumps(report, indent=1))
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=1), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
