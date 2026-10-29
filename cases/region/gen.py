"""Writes cases/region/generated.json: region files written, read, cleared and opened again as
vanilla's RegionFile does them, chunks big enough for files of their own, every compression, broken
streams, and files whose headers point where no chunk can be.

    py -I cases/region/gen.py

Deterministic: noise comes from the runner's SplitMix64 generator, seeded here, and text from a
fixed rule, so rerunning it gives the same file.

A chunk's bytes come from the case, compressed already: its compression's byte, then the stream,
which both adapters write as they are, so the files compare byte for byte. The streams are made
here. zlib and gzip come from Python's zlib, the library Java's Deflater wraps. lz4 is framed as
lz4-java's LZ4BlockOutputStream frames it, in blocks compressed by a greedy LZ4 compressor here, or
stored. Chunks of a megabyte are stored zlib blocks around the runner's generated noise, so the
case file holds only their framing.
"""

import base64
import struct
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
from cases import splitmix64, write_file  # noqa: E402

SEED = 20261029
GZIP, DEFLATE, STORED, LZ4, CUSTOM = 1, 2, 3, 4, 127
SECTOR = 4096


def b64(data):
    return base64.b64encode(bytes(data)).decode()


def text(n, salt=0):
    """Bytes that compress well: words from a short list, picked by a fixed rule."""
    words = [b"stone ", b"dirt ", b"grass_block ", b"oak_log ", b"water ", b"air ", b"bedrock "]
    out = bytearray()
    i = salt
    while len(out) < n:
        out += words[(i * 7 + i // 3) % len(words)]
        i += 1
    return bytes(out[:n])


class Noise:
    """Incompressible bytes, as the runner's `f64_bits` generator expands them, with their parts."""

    def __init__(self, seed):
        self.seed = seed

    def make(self, n):
        """`n` bytes: whole 8-byte draws from the next seed, then zeros for the rest."""
        self.seed += 1
        rand = splitmix64(self.seed)
        data = b"".join(struct.pack(">Q", next(rand)) for _ in range(n // 8)) + bytes(n % 8)
        parts = [{"gen": "f64_bits", "seed": str(self.seed), "count": n // 8}]
        if n % 8:
            parts.append({"hex": ["00" * (n % 8)]})
        return data, parts


def stored_chunk(noise, n):
    """A chunk stored as it is: compression 3 and `n` bytes of noise."""
    data, parts = noise.make(n)
    return data, [{"hex": ["03"]}] + parts


def zlib_noise_chunk(noise, length):
    """A zlib chunk, compression 2, of exactly `length` bytes with its compression's byte: noise
    in stored deflate blocks, which every inflater reads."""
    body = length - 1 - 2 - 4
    blocks = -(-body // (65535 + 5))
    data_len = body - 5 * blocks
    q, r = divmod(data_len, blocks)
    sizes = [q + 1] * r + [q] * (blocks - r)
    assert max(sizes) <= 65535
    parts = [{"hex": ["02 7801"]}]
    data = bytearray()
    for k, n in enumerate(sizes):
        chunk, chunk_parts = noise.make(n)
        final = 1 if k == blocks - 1 else 0
        parts.append({"hex": [struct.pack("<BHH", final, n, n ^ 0xFFFF).hex()]})
        parts += chunk_parts
        data += chunk
    parts.append({"hex": [struct.pack(">I", zlib.adler32(data)).hex()]})
    return bytes(data), parts


def gzip(data, level=6):
    """gzip as Java's GZIPOutputStream writes it: no name, no time, OS 255."""
    c = zlib.compressobj(level, zlib.DEFLATED, -15)
    raw = c.compress(data) + c.flush()
    return b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\xff" + raw + struct.pack("<II", zlib.crc32(data), len(data))


# XXH32, as lz4-java's checksums use it.
P1, P2, P3, P4, P5 = 2654435761, 2246822519, 3266489917, 668265263, 374761393
M32 = 0xFFFFFFFF


def rotl(x, r):
    return ((x << r) | (x >> (32 - r))) & M32


def xxh32(data, seed):
    n = len(data)
    i = 0
    if n >= 16:
        v = [(seed + P1 + P2) & M32, (seed + P2) & M32, seed & M32, (seed - P1) & M32]
        while i + 16 <= n:
            for k in range(4):
                lane = struct.unpack_from("<I", data, i + 4 * k)[0]
                v[k] = (rotl((v[k] + lane * P2) & M32, 13) * P1) & M32
            i += 16
        h = (rotl(v[0], 1) + rotl(v[1], 7) + rotl(v[2], 12) + rotl(v[3], 18)) & M32
    else:
        h = (seed + P5) & M32
    h = (h + n) & M32
    while i + 4 <= n:
        h = (h + struct.unpack_from("<I", data, i)[0] * P3) & M32
        h = (rotl(h, 17) * P4) & M32
        i += 4
    while i < n:
        h = (h + data[i] * P5) & M32
        h = (rotl(h, 11) * P1) & M32
        i += 1
    h ^= h >> 15
    h = (h * P2) & M32
    h ^= h >> 13
    h = (h * P3) & M32
    h ^= h >> 16
    return h


def lz4_block(src):
    """One LZ4 block, greedy, with the format's rules for its end: the last match starts 12 or
    more bytes before it, and the last 5 bytes are literals."""
    n = len(src)
    out = bytearray()
    seen = {}
    anchor = i = 0

    def length(v):
        while v >= 255:
            out.append(255)
            v -= 255
        out.append(v)

    def sequence(literals, offset=None, match=0):
        lit = len(literals)
        token = (min(lit, 15) << 4) | (min(match - 4, 15) if offset else 0)
        out.append(token)
        if lit >= 15:
            length(lit - 15)
        out.extend(literals)
        if offset:
            out.extend(struct.pack("<H", offset))
            if match - 4 >= 15:
                length(match - 4 - 15)

    while i + 12 < n:
        key = src[i:i + 4]
        j = seen.get(key)
        seen[key] = i
        if j is not None and i - j <= 65535:
            m = 4
            while i + m < n - 5 and src[j + m] == src[i + m]:
                m += 1
            sequence(src[anchor:i], i - j, m)
            i += m
            anchor = i
        else:
            i += 1
    sequence(src[anchor:])
    return bytes(out)


def lz4(data, block=65536, store=False):
    """An LZ4Block stream, as LZ4BlockOutputStream writes one: blocks that don't get smaller are
    stored, and an empty block ends it."""
    level = block.bit_length() - 1 - 10
    out = bytearray()
    for k in range(0, len(data), block):
        part = data[k:k + block]
        packed = lz4_block(part)
        method, body = (0x10, part) if store or len(packed) >= len(part) else (0x20, packed)
        out += b"LZ4Block" + bytes([method | level])
        out += struct.pack("<iiI", len(body), len(part), xxh32(part, 0x9747B28C) & 0xFFFFFFF) + body
    out += b"LZ4Block" + bytes([0x10 | level]) + struct.pack("<iii", 0, 0, 0)
    return bytes(out)


def lz4_noise(noise, n):
    """An LZ4Block stream of `n` bytes of noise, its blocks stored, as parts: the noise from the
    runner's generator, the blocks' headers here."""
    parts = []
    for k in range(0, n, 65536):
        size = min(65536, n - k)
        data, data_parts = noise.make(size)
        head = b"LZ4Block" + bytes([0x10 | 6]) + struct.pack("<iiI", size, size, xxh32(data, 0x9747B28C) & 0xFFFFFFF)
        parts.append({"hex": [head.hex()]})
        parts += data_parts
    parts.append({"hex": [(b"LZ4Block" + bytes([0x16]) + bytes(12)).hex()]})
    return parts


def utf(text_bytes):
    return struct.pack(">H", len(text_bytes)) + text_bytes


def case(name, ops, blobs):
    return {"id": name, "input": {"ops": ops}, "blobs": blobs}


def layout(noise):
    """Chunks written into the first free sectors that fit, grown past the end, moved into what
    others left, cleared, and read again after the file is opened again."""
    blobs = [
        stored_chunk(noise, 3000)[1],
        stored_chunk(noise, 10000)[1],
        b64(bytes([DEFLATE]) + zlib.compress(text(20000), 6)),
        stored_chunk(noise, 14000)[1],
        stored_chunk(noise, 5000)[1],
        stored_chunk(noise, 100)[1],
        # Exactly a sector, with its 4 bytes of length.
        stored_chunk(noise, SECTOR - 5)[1],
    ]
    ops = [
        ["open"],
        ["write", 0, 0, 0], ["write", 1, 0, 1], ["write", 31, 31, 2],
        ["has", 0, 0], ["has", 5, 5],
        ["read", 0, 0], ["read", 1, 0], ["read", 31, 31],
        ["write", 1, 0, 3], ["write", 0, 0, 4], ["clear", 31, 31], ["clear", 9, 9],
        ["read", 31, 31], ["has", 31, 31],
        ["close"],
        ["open"],
        ["read", 1, 0], ["read", 0, 0],
        ["write", 2, 0, 5], ["write", 31, 0, 0], ["write", 7, 7, 6], ["write", 7, 7, 6],
        ["read", 7, 7],
        ["close"],
    ]
    return case("layout", ops, blobs)


def external(noise):
    """A chunk of 256 sectors or more goes in its own file, replaced when it's written again and
    removed when it fits again. One of 255 stays in the region file."""
    big = zlib_noise_chunk(noise, 256 * SECTOR - 4 + 1000)[1]
    bigger = zlib_noise_chunk(noise, 300 * SECTOR)[1]
    # With their 4 bytes of length, 255 sectors exactly, and a byte more.
    exactly = zlib_noise_chunk(noise, 255 * SECTOR - 4)[1]
    edge = zlib_noise_chunk(noise, 255 * SECTOR - 3)[1]
    blobs = [big, b64(bytes([DEFLATE]) + zlib.compress(text(3000), 6)), bigger, exactly, edge]
    ops = [
        ["open"],
        ["write", 3, 4, 0], ["read", 3, 4], ["close"],
        ["open"], ["read", 3, 4], ["has", 3, 4],
        ["write", 3, 4, 2], ["read", 3, 4], ["close"],
        ["open"], ["write", 3, 4, 1], ["read", 3, 4], ["close"],
        ["open"], ["write", 5, 5, 3], ["read", 5, 5], ["write", 6, 6, 4], ["read", 6, 6],
        ["clear", 6, 6], ["read", 6, 6], ["close"],
    ]
    return case("external", ops, blobs)


def compressions(noise):
    """Each compression vanilla reads, made as Java makes it, and edges of each format."""
    words = text(150000, 3)
    small = text(5000, 1)
    two_members = gzip(small[:2000]) + gzip(small[2000:])
    streams = [
        bytes([GZIP]) + gzip(small),
        bytes([GZIP]) + gzip(small, 1),
        bytes([GZIP]) + gzip(b""),
        bytes([GZIP]) + two_members,
        bytes([DEFLATE]) + zlib.compress(small, 1),
        bytes([DEFLATE]) + zlib.compress(small, 6),
        bytes([DEFLATE]) + zlib.compress(words, 9),
        bytes([DEFLATE]) + zlib.compress(b"", 6),
        # What follows a zlib stream's end isn't read.
        bytes([DEFLATE]) + zlib.compress(small, 6) + b"after the end",
        bytes([STORED]),
        bytes([STORED]) + small,
        bytes([LZ4]) + lz4(small),
        bytes([LZ4]) + lz4(words[:70000]),
        bytes([LZ4]) + lz4(small, store=True),
        bytes([LZ4]) + lz4(b""),
        # Blocks of 1 KiB, as a stream from another block size, and what follows its end.
        bytes([LZ4]) + lz4(words[:5000], block=1024) + b"after",
    ]
    blobs = [b64(s) for s in streams]
    # Noise in two blocks that are stored, as LZ4BlockOutputStream stores what doesn't shrink.
    blobs.append([{"hex": ["04"]}] + lz4_noise(noise, 70000))
    ops = [["open"]]
    for i in range(len(blobs)):
        ops.append(["write", i, 0, i])
    for i in range(len(blobs)):
        ops.append(["read", i, 0])
    ops.append(["close"])
    return case("compressions", ops, blobs)


def broken(noise):
    """Streams vanilla's readers refuse, chunks of custom and unknown compressions, and chunks
    that say their bytes are in a file of their own."""
    small = text(5000, 2)
    z = zlib.compress(small, 6)
    g = gzip(small)
    l4 = lz4(small)
    bad_adler = bytearray(z)
    bad_adler[-1] ^= 1
    bad_crc = bytearray(g)
    bad_crc[-5] ^= 1
    bad_check = bytearray(l4)
    bad_check[17] ^= 1
    streams = [
        bytes([DEFLATE]) + z[:len(z) // 2],
        bytes([DEFLATE]) + bytes(bad_adler),
        bytes([DEFLATE]) + b"\x78\x00" + z[2:],
        # A zlib header that asks for a preset dictionary.
        bytes([DEFLATE]) + b"\x78\xbb\x00\x00\x00\x01" + z[2:],
        bytes([DEFLATE]) + b"\x78\x9c\xff\xff\xff",
        bytes([GZIP]) + b"\x1f\x8c" + g[2:],
        bytes([GZIP]) + g[:len(g) // 2],
        bytes([GZIP]) + bytes(bad_crc),
        bytes([GZIP]) + g[:5],
        bytes([LZ4]) + l4[:len(l4) // 2],
        bytes([LZ4]) + bytes(bad_check),
        bytes([LZ4]) + b"LZ4Blocc" + l4[8:],
        bytes([LZ4]) + l4[:-21],
        bytes([CUSTOM]) + utf(b"minecraft:zstd") + b"data",
        bytes([CUSTOM]) + utf(b"zstd"),
        bytes([CUSTOM]) + utf(b"Bad Name"),
        bytes([CUSTOM]) + utf(b"a:b:c"),
        bytes([CUSTOM]) + utf(b":path"),
        bytes([CUSTOM]) + utf(b""),
        bytes([CUSTOM]) + utf(b"\xc0\x80"),
        bytes([CUSTOM]) + utf(b"\xff\xfe"),
        bytes([CUSTOM]) + b"\x00",
        bytes([CUSTOM]) + b"\x00\x0aabc",
        bytes([0]) + small,
        bytes([5]) + small,
        bytes([126]) + small,
        # External, with bytes inside too, and with no file of its own yet.
        bytes([DEFLATE | 128]) + z,
        bytes([5 | 128]),
        bytes([DEFLATE | 128]),
        bytes([CUSTOM | 128]),
    ]
    blobs = [b64(s) for s in streams]
    ext = len(streams) - 4
    blobs.append(b64(z))
    blobs.append(b64(utf(b"minecraft:zstd")))
    ops = [["open"]]
    for i in range(len(streams)):
        ops.append(["write", i, 1, i])
    for i in range(len(streams)):
        ops.append(["read", i, 1])
    # Their files come after the writes, which remove a chunk's file when it fits inside.
    ops += [
        ["put_external", ext, 1, len(streams)],
        ["put_external", ext + 1, 1, len(streams)],
        ["put_external", ext + 2, 1, len(streams)],
        ["put_external", ext + 3, 1, len(streams) + 1],
        ["read", ext, 1], ["read", ext + 1, 1], ["read", ext + 2, 1], ["read", ext + 3, 1],
        ["close"],
    ]
    return case("broken", ops, blobs)


def header(offsets, size):
    """A region file of `size` bytes, its offsets as given by chunk index, its times all 1."""
    out = bytearray(max(size, 0))
    for i, (sector, count) in offsets.items():
        struct.pack_into(">I", out, i * 4, (sector << 8) | count)
        if 4096 + i * 4 + 4 <= len(out):
            struct.pack_into(">I", out, 4096 + i * 4, 1)
    return out


def damaged(noise):
    """Headers whose places can't be right, which vanilla drops as it opens them, and chunks whose
    own headers are wrong, which it logs as it reads them."""
    small = text(3000, 5)
    z = bytes([DEFLATE]) + zlib.compress(small, 6)
    # 0 and 1 overlap the header, 2 has no sectors and 3 is past the end, so all four are dropped.
    # 4 is a good chunk. 5 is allocated, with no stream. 6 says it's longer than its sector, and 7
    # that its length is negative. 8 is in a sector nothing was written to. 10 is at 7 and 8, and
    # 9 and 11 at 8, which the file ends 3 bytes into.
    f = header({0: (1, 1), 1: (0, 1), 2: (5, 0), 3: (9, 1), 4: (2, 1), 5: (3, 1), 6: (4, 1),
                7: (5, 2), 8: (6, 1), 9: (8, 1), 10: (7, 2), 11: (8, 1)}, 8 * SECTOR + 3)
    struct.pack_into(">I", f, 2 * SECTOR, len(z))
    f[2 * SECTOR + 4:2 * SECTOR + 4 + len(z)] = z
    struct.pack_into(">IB", f, 4 * SECTOR, 5000, DEFLATE)
    struct.pack_into(">iB", f, 5 * SECTOR, -5, DEFLATE)
    struct.pack_into(">IB", f, 7 * SECTOR, 4, STORED)
    f[7 * SECTOR + 5:7 * SECTOR + 8] = b"abc"
    # A chunk at sector 3 of a file 3 sectors long: in bounds, as vanilla checks, with no bytes.
    at_end = header({0: (2, 1), 1: (3, 1)}, 3 * SECTOR)
    struct.pack_into(">I", at_end, 2 * SECTOR, len(z))
    at_end[2 * SECTOR + 4:2 * SECTOR + 4 + len(z)] = z
    blobs = [
        b64(f),
        b64(header({0: (2, 1), 1: (0, 0)}, 8)),
        b64(header({0: (2, 1)}, 5000)),
        b64(b""),
        stored_chunk(noise, 6000)[1],
        b64(at_end),
    ]
    ops = [
        ["put", 0], ["open"],
        *[["has", i, 0] for i in range(12)],
        *[["read", i, 0] for i in range(12)],
        # Each write goes in the first free sectors, among those of the chunks dropped and moved,
        # and the last over 9's and 11's, which 10's move freed.
        ["write", 4, 0, 4], ["write", 10, 0, 4], ["write", 20, 0, 4],
        ["read", 9, 0], ["read", 20, 0],
        ["close"],
        ["put", 1], ["open"], ["has", 0, 0], ["close"],
        ["put", 2], ["open"], ["has", 0, 0], ["write", 0, 0, 4], ["close"],
        ["put", 3], ["open"], ["read", 0, 0], ["close"],
        ["put", 3], ["open"], ["write", 1, 1, 4], ["close"],
        ["put", 5], ["open"], ["read", 0, 0], ["read", 1, 0], ["write", 2, 2, 4], ["read", 1, 0], ["close"],
    ]
    return case("damaged", ops, blobs)


def main():
    noise = Noise(SEED)
    cases = [layout(noise), external(noise), compressions(noise), broken(noise), damaged(noise)]
    write_file(HERE / "generated.json", "region", f"cases/region/gen.py, seed {SEED}", cases)


if __name__ == "__main__":
    main()
