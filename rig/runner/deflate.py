"""Deflate, zlib and gzip streams that come out the same on every machine, for the case generators.

Python's zlib module compresses with the zlib Python was built with: zlib-ng on Windows from
Python 3.14, classic zlib elsewhere, and the two write different bytes for the same input. A case
file has to come out the same wherever its generator runs, since the runner's tests rerun every
generator and compare, so generators compress with this instead.

`deflate` writes one block with deflate's fixed Huffman codes: greedy LZ77 matches from level 2
up, only literals at level 1, and stored blocks at level 0. Every inflater reads these, Java's
included. Checksums still come from zlib's `crc32` and `adler32`, which are the same everywhere.
"""

import bisect
import struct
import zlib

LENGTH_BASE = (3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115,
               131, 163, 195, 227, 258)
LENGTH_EXTRA = (0,) * 8 + (1,) * 4 + (2,) * 4 + (3,) * 4 + (4,) * 4 + (5,) * 4 + (0,)
DISTANCE_BASE = (1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537,
                 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577)
DISTANCE_EXTRA = (0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13)
WINDOW = 32768
LONGEST = 258
STORED_MAX = 65535
# Java's GZIPOutputStream's header: no name, no time, no flags, OS 255.
GZIP_HEADER = b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\xff"


class Bits:
    """Bits written from the lowest of each byte up, as deflate packs them."""

    def __init__(self):
        self.out = bytearray()
        self.word = 0
        self.count = 0

    def put(self, value, n):
        self.word |= value << self.count
        self.count += n
        while self.count >= 8:
            self.out.append(self.word & 0xFF)
            self.word >>= 8
            self.count -= 8

    def code(self, value, n):
        """A Huffman code, which deflate writes from its highest bit."""
        self.put(int(format(value, f"0{n}b")[::-1], 2), n)

    def done(self):
        if self.count:
            self.out.append(self.word & 0xFF)
        return bytes(self.out)


def _symbol(bits, symbol):
    """A literal, length or end symbol in the fixed codes."""
    if symbol < 144:
        bits.code(0x30 + symbol, 8)
    elif symbol < 256:
        bits.code(0x190 + symbol - 144, 9)
    elif symbol < 280:
        bits.code(symbol - 256, 7)
    else:
        bits.code(0xC0 + symbol - 280, 8)


def _match(bits, length, distance):
    i = bisect.bisect_right(LENGTH_BASE, length) - 1
    _symbol(bits, 257 + i)
    bits.put(length - LENGTH_BASE[i], LENGTH_EXTRA[i])
    j = bisect.bisect_right(DISTANCE_BASE, distance) - 1
    bits.code(j, 5)
    bits.put(distance - DISTANCE_BASE[j], DISTANCE_EXTRA[j])


def _fixed(data, matches):
    bits = Bits()
    bits.put(1, 1)  # the last block
    bits.put(1, 2)  # with the fixed codes
    # Where each three bytes were last seen.
    last = {}
    i, n = 0, len(data)
    while i < n:
        length = distance = 0
        if matches and i + 3 <= n:
            key = data[i:i + 3]
            j = last.get(key)
            last[key] = i
            if j is not None and i - j <= WINDOW:
                length, distance = 3, i - j
                most = min(LONGEST, n - i)
                while length < most and data[j + length] == data[i + length]:
                    length += 1
        if length:
            _match(bits, length, distance)
            for k in range(i + 1, min(i + length, n - 2)):
                last[data[k:k + 3]] = k
            i += length
        else:
            _symbol(bits, data[i])
            i += 1
    _symbol(bits, 256)
    return bits.done()


def _stored(data):
    if not data:
        return struct.pack("<BHH", 1, 0, 0xFFFF)
    out = bytearray()
    for k in range(0, len(data), STORED_MAX):
        piece = data[k:k + STORED_MAX]
        last = 1 if k + STORED_MAX >= len(data) else 0
        out += struct.pack("<BHH", last, len(piece), len(piece) ^ 0xFFFF) + piece
    return bytes(out)


def deflate(data, level=6):
    """`data` as a raw deflate stream: stored at level 0, literals at 1, matches from 2 up (-1 is
    6, as zlib's default)."""
    data = bytes(data)
    if level == 0:
        return _stored(data)
    return _fixed(data, level != 1)


def zlib_stream(data, level=6):
    """`data` as a zlib stream, its header's level as zlib marks it for `level`."""
    data = bytes(data)
    level = 6 if level == -1 else level
    mark = 0 if level <= 1 else 1 if level <= 5 else 2 if level == 6 else 3
    flags = mark << 6
    flags += (31 - (0x78 << 8 | flags) % 31) % 31
    return bytes([0x78, flags]) + deflate(data, level) + struct.pack(">I", zlib.adler32(data))


def gzip_stream(data, level=6, header=GZIP_HEADER):
    """`data` as one gzip member, as Java's GZIPOutputStream writes it unless given another
    header."""
    data = bytes(data)
    return header + deflate(data, level) + struct.pack("<II", zlib.crc32(data), len(data) & 0xFFFFFFFF)
