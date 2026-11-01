"""Results compared without the order of their compounds' entries (PROTOCOL.md, "Case files").

Some registries' contents come from maps vanilla makes with `Map.copyOf` over keys hashed by
identity, such as a timeline's tracks or a dimension type's and a biome's attributes, so the
order their entries go into a compound, and so the order a `HashMap` gives those that share a
bucket, changes from one run of vanilla to the next. A case that says `"unordered": true` has
each compound in its blobs sorted by key before it's hashed, for vanilla and Calcite alike.
"""

import struct


class _Reader:
    def __init__(self, data):
        self.data = data
        self.at = 0

    def take(self, n):
        if self.at + n > len(self.data):
            raise ValueError(f"the blob ends at {len(self.data)}, inside a value at {self.at}")
        v = self.data[self.at:self.at + n]
        self.at += n
        return v

    def u8(self):
        return self.take(1)[0]

    def i32(self):
        return struct.unpack(">i", self.take(4))[0]

    def u16(self):
        return struct.unpack(">H", self.take(2))[0]


# The sizes of the tags of fixed size: byte, short, int, long, float and double.
_FIXED = {1: 1, 2: 2, 3: 4, 4: 8, 5: 4, 6: 8}
# The element sizes of the arrays: bytes, ints and longs.
_ARRAY = {7: 1, 11: 4, 12: 8}


def _payload(r, kind):
    """The payload of a tag of type `kind`, with each compound in it sorted by key."""
    if kind in _FIXED:
        return r.take(_FIXED[kind])
    if kind in _ARRAY:
        n = r.i32()
        return struct.pack(">i", n) + r.take(max(n, 0) * _ARRAY[kind])
    if kind == 8:
        n = r.u16()
        return struct.pack(">H", n) + r.take(n)
    if kind == 9:
        element = r.u8()
        n = r.i32()
        return bytes([element]) + struct.pack(">i", n) + b"".join(_payload(r, element) for _ in range(max(n, 0)))
    if kind == 10:
        entries = []
        while True:
            t = r.u8()
            if t == 0:
                break
            n = r.u16()
            name = r.take(n)
            entries.append((name, bytes([t]) + struct.pack(">H", n) + name + _payload(r, t)))
        entries.sort(key=lambda e: e[0])
        return b"".join(e[1] for e in entries) + b"\x00"
    if kind == 0:
        return b""
    raise ValueError(f"tag type {kind} at {r.at}")


def sorted_contents(blob):
    """A `registries` contents blob with every compound in each entry's contents sorted by key: an
    `int` count, then each entry's ID as an `int` length and its UTF-8, its tag's type and its
    payload."""
    r = _Reader(blob)
    count = r.i32()
    out = bytearray(struct.pack(">i", count))
    for _ in range(count):
        n = r.i32()
        out += struct.pack(">i", n) + r.take(n)
        kind = r.u8()
        out.append(kind)
        out += _payload(r, kind)
    if r.at != len(blob):
        raise ValueError(f"{len(blob) - r.at} bytes after the last entry")
    return bytes(out)
