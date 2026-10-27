"""Case files (rig/PROTOCOL.md, "Case files"): loading them and expanding their blobs."""

import base64
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path

CASE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
MASK64 = (1 << 64) - 1


class CaseFileError(Exception):
    pass


@dataclass(frozen=True)
class Case:
    probe: str
    probe_version: int
    id: str
    input: dict
    blobs: tuple
    source: Path

    @property
    def key(self):
        return f"{self.probe}:{self.id}"


def splitmix64(seed):
    """Steele, Lea and Flood's SplitMix64. The case generators' only source of randomness."""
    state = seed & MASK64
    while True:
        state = (state + 0x9E3779B97F4A7C15) & MASK64
        z = state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
        yield z ^ (z >> 31)


def _float(text):
    """A decimal or hex-float literal: "1.5", "-0", "inf", "nan", "0x1p-1074"."""
    if not isinstance(text, str):
        raise CaseFileError(f"float literal {text!r} must be a string")
    t = text.strip().lower()
    if t.lstrip("+-").startswith("0x"):
        return float.fromhex(t)
    return float(t)


def _generate(spec):
    gen = spec.get("gen")
    try:
        seed = int(spec["seed"])
        count = int(spec["count"])
    except (KeyError, ValueError) as e:
        raise CaseFileError(f"generator {spec!r} needs a decimal `seed` and a `count`") from e
    rand = splitmix64(seed)
    out = bytearray()
    if gen == "f64_bits":
        for _ in range(count):
            out += struct.pack(">Q", next(rand))
    elif gen == "f32_bits":
        for _ in range(count):
            out += struct.pack(">I", next(rand) >> 32)
    elif gen in ("f64_range", "f32_range"):
        # `ranges` makes tuples: each of the `count` records has one value from each range in turn.
        ranges = spec.get("ranges") or [[spec["min"], spec["max"]]]
        bounds = [(_float(lo), _float(hi)) for lo, hi in ranges]
        fmt = ">d" if gen == "f64_range" else ">f"
        for _ in range(count):
            for lo, hi in bounds:
                # 53 random bits scaled into [0, 1), exactly, then into [min, max) in f64.
                u = (next(rand) >> 11) * 2.0**-53
                out += struct.pack(fmt, lo + (hi - lo) * u)
    elif gen == "i32_range":
        lo, hi = int(spec["min"]), int(spec["max"])
        if not (-(1 << 31) <= lo <= hi < (1 << 31)):
            raise CaseFileError(f"generator {spec!r}: bad i32 range")
        for _ in range(count):
            out += struct.pack(">i", lo + next(rand) % (hi - lo + 1))
    else:
        raise CaseFileError(f"unknown generator `{gen}`")
    return bytes(out)


def _part(part):
    if isinstance(part, str):
        return base64.b64decode(part, validate=True)
    if not isinstance(part, dict):
        raise CaseFileError(f"blob part {part!r} must be base64 or an object")
    if "gen" in part:
        return _generate(part)
    if len(part) != 1:
        raise CaseFileError(f"blob part {part!r} must have exactly one key")
    (kind, values), = part.items()
    if not isinstance(values, list):
        raise CaseFileError(f"blob part `{kind}` must be a list")
    if kind == "f64":
        return b"".join(struct.pack(">d", _float(v)) for v in values)
    if kind == "f32":
        return b"".join(struct.pack(">f", _float(v)) for v in values)
    if kind == "f64_bits":
        return b"".join(struct.pack(">Q", int(v, 16)) for v in values)
    if kind == "f32_bits":
        return b"".join(struct.pack(">I", int(v, 16)) for v in values)
    if kind == "i32":
        return b"".join(struct.pack(">i", int(v)) for v in values)
    if kind == "i64":
        return b"".join(struct.pack(">q", int(v)) for v in values)
    if kind == "hex":
        return b"".join(bytes.fromhex(v) for v in values)
    raise CaseFileError(f"unknown blob part `{kind}`")


def expand_blob(blob):
    """A blob is one part or a list of parts, concatenated."""
    parts = blob if isinstance(blob, list) else [blob]
    return b"".join(_part(p) for p in parts)


def write_file(path, probe, generated_by, cases, probe_version=1):
    """Writes a generated case file, one case per line so its diffs stay readable."""
    lines = [json.dumps(c, ensure_ascii=False, separators=(",", ":")) for c in cases]
    text = (
        "{\n"
        f"  \"probe\": {json.dumps(probe)},\n"
        f"  \"probe_version\": {probe_version},\n"
        f"  \"generated_by\": {json.dumps(generated_by)},\n"
        "  \"cases\": [\n    " + ",\n    ".join(lines) + "\n  ]\n}\n"
    )
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {len(cases)} cases to {path}")


def load_file(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CaseFileError(f"{path}: {e}") from e
    probe = data.get("probe")
    version = data.get("probe_version")
    if not isinstance(probe, str) or not isinstance(version, int):
        raise CaseFileError(f"{path}: needs `probe` and an integer `probe_version`")
    cases = []
    for i, raw in enumerate(data.get("cases", [])):
        cid = raw.get("id")
        if not isinstance(cid, str) or not CASE_ID.match(cid):
            raise CaseFileError(f"{path}: case {i} has a bad id {cid!r}")
        try:
            blobs = tuple(expand_blob(b) for b in raw.get("blobs", []))
        except (CaseFileError, ValueError, KeyError, struct.error) as e:
            raise CaseFileError(f"{path}: case `{cid}`: {e}") from e
        cases.append(Case(probe, version, cid, raw.get("input", {}), blobs, Path(path)))
    return probe, cases


def load_all(cases_dir, probes=None):
    """Every case under cases/, by probe, in file then case order."""
    result = {}
    for probe_dir in sorted(p for p in Path(cases_dir).iterdir() if p.is_dir()):
        if probes and probe_dir.name not in probes:
            continue
        seen = {}
        for path in sorted(probe_dir.glob("*.json")):
            probe, cases = load_file(path)
            if probe != probe_dir.name:
                raise CaseFileError(f"{path}: says probe `{probe}` but is in cases/{probe_dir.name}/")
            for case in cases:
                if case.id in seen:
                    raise CaseFileError(f"{path}: case `{case.id}` is also in {seen[case.id]}")
                seen[case.id] = path.name
            result.setdefault(probe, []).extend(cases)
    if probes:
        missing = set(probes) - set(result)
        if missing:
            raise CaseFileError(f"no cases for {', '.join(sorted(missing))}")
    return result
