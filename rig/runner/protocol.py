"""The rig protocol (rig/PROTOCOL.md): frames, the adapter process, and result hashes."""

import hashlib
import json
import struct
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path

PROTOCOL = 1
MAX_HEADER = 64 << 20


class ProtocolError(Exception):
    """The adapter broke the protocol: a bad frame, a wrong id, or it exited."""


@dataclass
class Result:
    status: str
    output: dict
    blobs: list = field(default_factory=list)
    message: str | None = None

    def digest(self):
        return result_hash(self.output, self.blobs)


def canonical_json(value):
    """Keys sorted, no whitespace, non-ASCII as itself (PROTOCOL.md, "Results and hashes")."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def result_hash(output, blobs):
    h = hashlib.sha256()
    h.update(canonical_json(output).encode("utf-8"))
    for blob in blobs:
        h.update(struct.pack(">Q", len(blob)))
        h.update(blob)
    return h.hexdigest()


def write_frame(stream, header, blobs=()):
    header = dict(header, blobs=[len(b) for b in blobs])
    data = json.dumps(header, ensure_ascii=False, allow_nan=False).encode("utf-8")
    stream.write(struct.pack(">I", len(data)))
    stream.write(data)
    for blob in blobs:
        stream.write(blob)
    stream.flush()


def _read_exact(stream, n):
    data = stream.read(n)
    if len(data) != n:
        raise ProtocolError(f"adapter closed its output after {len(data)} of {n} bytes")
    return data


def read_frame(stream):
    (length,) = struct.unpack(">I", _read_exact(stream, 4))
    if length > MAX_HEADER:
        raise ProtocolError(f"header length {length} is out of range")
    header = json.loads(_read_exact(stream, length).decode("utf-8"))
    if not isinstance(header, dict):
        raise ProtocolError("header isn't a JSON object")
    blobs = [_read_exact(stream, n) for n in header.get("blobs", [])]
    return header, blobs


class Adapter:
    """A running adapter process. Use as a context manager, or call close()."""

    def __init__(self, argv, cwd=None, log_path=None):
        self.log_path = Path(log_path) if log_path else None
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log = open(self.log_path, "wb")
        else:
            self._log = subprocess.DEVNULL
        self.proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._log)
        self._next_id = 0
        self._lock = threading.Lock()
        reply = self._request({"type": "hello", "protocol": PROTOCOL}, (), expect="hello")[0]
        if reply.get("protocol") != PROTOCOL:
            raise ProtocolError(f"adapter speaks protocol {reply.get('protocol')}, not {PROTOCOL}")
        self.name = reply.get("adapter", "?")
        self.game_version = reply.get("game_version", "?")
        self.probes = dict(reply.get("probes", {}))
        self.about = dict(reply.get("about", {}))

    @classmethod
    def from_file(cls, path, log_path=None):
        """Starts the adapter described by an adapter.json, as the vanilla build writes."""
        spec = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(spec["argv"], cwd=spec.get("cwd"), log_path=log_path)

    def _request(self, header, blobs, expect):
        with self._lock:
            try:
                write_frame(self.proc.stdin, header, blobs)
                reply, reply_blobs = read_frame(self.proc.stdout)
            except (BrokenPipeError, OSError) as e:
                raise ProtocolError(f"adapter exited ({self.proc.poll()}): {e}") from e
        if reply.get("type") != expect:
            raise ProtocolError(f"expected `{expect}`, got `{reply.get('type')}`: {reply.get('message', '')}")
        return reply, reply_blobs

    def run(self, probe, case_id, input, blobs=()):
        if probe not in self.probes:
            return Result("unimplemented", {}, [], f"adapter has no probe `{probe}`")
        self._next_id += 1
        rid = self._next_id
        header = {"type": "run", "id": rid, "probe": probe, "case": case_id, "input": input}
        reply, reply_blobs = self._request(header, blobs, expect="result")
        if reply.get("id") != rid:
            raise ProtocolError(f"result for id {reply.get('id')}, expected {rid}")
        return Result(reply.get("status", "error"), reply.get("output", {}), reply_blobs, reply.get("message"))

    def close(self):
        if self.proc.poll() is None:
            try:
                self._request({"type": "bye"}, (), expect="bye")
            except ProtocolError:
                pass
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=30)
            except (OSError, subprocess.TimeoutExpired):
                self.proc.kill()
        if self._log is not subprocess.DEVNULL:
            self._log.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
