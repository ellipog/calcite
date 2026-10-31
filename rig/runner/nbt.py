"""Gzipped NBT files, as vanilla's `NbtIo.readCompressed` and `writeCompressed` have them, for the
rig to read and write a world's small files, such as level.dat and game_rules.dat.

Tags are Python values: a compound is a dict, a list a `List` of its element type, numbers are
`Byte`, `Short`, `Int`, `Long`, `Float` or `Double`, and arrays are `ByteArray`, `IntArray` or
`LongArray`, so a file written back has the types it was read with. A string is a `str`.
"""

import gzip
import struct

END, BYTE, SHORT, INT, LONG, FLOAT, DOUBLE, BYTE_ARRAY, STRING, LIST, COMPOUND, INT_ARRAY, LONG_ARRAY = range(13)


class Byte(int):
    pass


class Short(int):
    pass


class Int(int):
    pass


class Long(int):
    pass


class Float(float):
    pass


class Double(float):
    pass


class ByteArray(list):
    pass


class IntArray(list):
    pass


class LongArray(list):
    pass


class List(list):
    """A list tag, whose elements are all of the tag type `kind`."""

    def __init__(self, kind, items=()):
        super().__init__(items)
        self.kind = kind


NUMBERS = {BYTE: (Byte, ">b"), SHORT: (Short, ">h"), INT: (Int, ">i"), LONG: (Long, ">q"),
           FLOAT: (Float, ">f"), DOUBLE: (Double, ">d")}
ARRAYS = {BYTE_ARRAY: (ByteArray, ">b"), INT_ARRAY: (IntArray, ">i"), LONG_ARRAY: (LongArray, ">q")}


def kind_of(value):
    """The tag type of a value."""
    for kind, (cls, _) in list(NUMBERS.items()) + list(ARRAYS.items()):
        if type(value) is cls:
            return kind
    if isinstance(value, str):
        return STRING
    if isinstance(value, List):
        return LIST
    if isinstance(value, dict):
        return COMPOUND
    raise TypeError(f"{type(value).__name__} isn't a tag")


class _Reader:
    def __init__(self, data):
        self.data, self.at = data, 0

    def take(self, fmt):
        size = struct.calcsize(fmt)
        value = struct.unpack_from(fmt, self.data, self.at)[0]
        self.at += size
        return value

    def string(self):
        n = self.take(">H")
        s = self.data[self.at:self.at + n].decode("utf-8", errors="surrogatepass")
        self.at += n
        return s

    def payload(self, kind):
        if kind in NUMBERS:
            cls, fmt = NUMBERS[kind]
            return cls(self.take(fmt))
        if kind in ARRAYS:
            cls, fmt = ARRAYS[kind]
            return cls(self.take(fmt) for _ in range(self.take(">i")))
        if kind == STRING:
            return self.string()
        if kind == LIST:
            element = self.take(">b")
            return List(element, [self.payload(element) for _ in range(self.take(">i"))])
        if kind == COMPOUND:
            out = {}
            while (k := self.take(">b")) != END:
                name = self.string()
                out[name] = self.payload(k)
            return out
        raise ValueError(f"tag type {kind} isn't one")


def _write_string(out, s):
    b = s.encode("utf-8", errors="surrogatepass")
    out += struct.pack(">H", len(b)) + b


def _write(out, value):
    kind = kind_of(value)
    if kind in NUMBERS:
        out += struct.pack(NUMBERS[kind][1], value)
    elif kind in ARRAYS:
        out += struct.pack(">i", len(value))
        for v in value:
            out += struct.pack(ARRAYS[kind][1], v)
    elif kind == STRING:
        _write_string(out, value)
    elif kind == LIST:
        out += struct.pack(">bi", value.kind if value else (value.kind or END), len(value))
        for v in value:
            _write(out, v)
    else:
        for name, v in value.items():
            out += struct.pack(">b", kind_of(v))
            _write_string(out, name)
            _write(out, v)
        out += struct.pack(">b", END)


def read(path):
    """The root compound of a gzipped NBT file."""
    r = _Reader(gzip.decompress(path.read_bytes()))
    if r.take(">b") != COMPOUND:
        raise ValueError(f"{path} doesn't hold a compound")
    r.string()
    return r.payload(COMPOUND)


def write(path, root):
    """Writes `root`, a dict, as a gzipped NBT file with an empty root name."""
    out = bytearray(struct.pack(">bH", COMPOUND, 0))
    _write(out, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(bytes(out)))
