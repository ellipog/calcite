"""Calcite's rig adapter (P1.6), a stub until Calcite can run probes.

It speaks the rig protocol (rig/PROTOCOL.md) and implements only `ping`, so every other
probe scores as unimplemented. As Calcite's code lands, each probe moves here: this
process starts Calcite's probe binary and forwards requests to it.

Written from PROTOCOL.md alone, sharing no code with the runner, to keep the contract honest.
"""

import json
import struct
import sys

PROTOCOL = 1
PROBES = {"ping": 1}


def read_exact(stream, n):
    data = stream.read(n)
    if len(data) != n:
        return None
    return data


def read_frame(stream):
    head = read_exact(stream, 4)
    if head is None:
        return None
    (length,) = struct.unpack(">I", head)
    header = json.loads(read_exact(stream, length).decode("utf-8"))
    blobs = [read_exact(stream, n) for n in header.get("blobs", [])]
    return header, blobs


def write_frame(stream, header, blobs=()):
    header = dict(header, blobs=[len(b) for b in blobs])
    data = json.dumps(header, ensure_ascii=False).encode("utf-8")
    stream.write(struct.pack(">I", len(data)) + data + b"".join(blobs))
    stream.flush()


def run(header, blobs):
    probe = header.get("probe")
    reply = {"type": "result", "id": header.get("id"), "output": {}}
    if probe == "ping":
        reply.update(status="ok", output={"echo": header.get("input", {}).get("echo")})
        return reply, blobs
    reply.update(status="unimplemented", message=f"Calcite has no `{probe}` probe yet")
    return reply, []


def main():
    stdin, stdout = sys.stdin.buffer, sys.stdout.buffer
    while (frame := read_frame(stdin)) is not None:
        header, blobs = frame
        kind = header.get("type")
        if kind == "hello":
            write_frame(stdout, {"type": "hello", "protocol": PROTOCOL, "adapter": "calcite",
                                 "game_version": "26.3", "probes": PROBES,
                                 "about": {"stage": "stub"}})
        elif kind == "run":
            write_frame(stdout, *run(header, blobs))
        elif kind == "bye":
            write_frame(stdout, {"type": "bye"})
            return 0
        else:
            write_frame(stdout, {"type": "result", "id": header.get("id"), "status": "error",
                                 "output": {}, "message": f"unknown message type `{kind}`"})
    return 1


if __name__ == "__main__":
    sys.exit(main())
