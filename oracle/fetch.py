"""Fetches Mojang's server jar for a game version and checks it against a pinned SHA-1 (D30, P2.4),
and pins the stretch of the client jar that holds the vanilla data, which Calcite reads (D140).

    py -I oracle/fetch.py [--version 26.3]           download if missing, then verify
    py -I oracle/fetch.py [--version 26.3] --check   verify only, never download
    py -I oracle/fetch.py [--version 26.3] --jar P   install a local jar instead, if it matches the pin
    py -I oracle/fetch.py --version X --pin          look X up in Mojang's manifest and pin it

The jar goes to oracle/jars/server-<version>.jar, which is gitignored: nothing from Mojang is ever
committed. What is committed is oracle/versions.json, the jar's URL, size and SHA-1 per version,
so every checkout builds against the same bytes and a jar that's already there is checked offline.
Pinning reads Mojang's version manifest, then the version's metadata, checking the SHA-1 the
manifest gives for it. It pins the client jar too, which it downloads to
oracle/jars/client-<version>.jar, and the stretch of it Calcite reads: from the first file it
needs, data/ and the two language files, to the end of the last, with that stretch's SHA-256.

The vanilla adapter's build and the data generator step both call ensure(); so will Calcite's build.
"""

import argparse
import hashlib
import json
import os
import struct
import sys
import urllib.request
import zipfile
from pathlib import Path

MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
ORACLE = Path(__file__).resolve().parent
JARS = ORACLE / "jars"
VERSIONS = ORACLE / "versions.json"


def get(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def file_sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pins():
    return json.loads(VERSIONS.read_text(encoding="utf-8")) if VERSIONS.is_file() else {}


def jar_path(version):
    return JARS / f"server-{version}.jar"


def client_path(version):
    return JARS / f"client-{version}.jar"


# The files Calcite reads from the vanilla data: the data pack and the server's language.
LANGUAGE = ("assets/minecraft/lang/en_us.json", "assets/minecraft/lang/deprecated.json")


def wanted(name):
    return name.startswith("data/") or name in LANGUAGE


def data_stretch(jar):
    """{offset, length, sha256} of the bytes of the jar from the first local header of a file
    Calcite reads to the end of the last one's data, data descriptor included."""
    raw = Path(jar).read_bytes()
    first, end = None, 0
    for info in zipfile.ZipFile(jar).infolist():
        if not wanted(info.filename):
            continue
        at = info.header_offset
        sig, _, flags, _, _, _, _, _, _, n, m = struct.unpack("<IHHHHHIIIHH", raw[at:at + 30])
        if sig != 0x04034B50:
            sys.exit(f"fetch: {info.filename} has no local header at {at}")
        stop = at + 30 + n + m + info.compress_size
        if flags & 8:
            stop += 16 if raw[stop:stop + 4] == b"PK\x07\x08" else 12
        first = at if first is None else min(first, at)
        end = max(end, stop)
    if first is None:
        sys.exit(f"fetch: {jar} holds none of the vanilla data")
    return {"offset": first, "length": end - first, "sha256": hashlib.sha256(raw[first:end]).hexdigest()}


def lookup(version):
    """The server jar's {sha1, size, url} from Mojang's manifest, with the metadata's SHA-1 checked."""
    manifest = json.loads(get(MANIFEST))
    entry = next((v for v in manifest["versions"] if v["id"] == version), None)
    if entry is None:
        sys.exit(f"fetch: Mojang's manifest has no version {version}")
    meta = get(entry["url"])
    if hashlib.sha1(meta).hexdigest() != entry["sha1"]:
        sys.exit(f"fetch: {version}'s metadata doesn't match the manifest's SHA-1")
    downloads = json.loads(meta).get("downloads", {})
    server, client = downloads.get("server"), downloads.get("client")
    if server is None or client is None:
        sys.exit(f"fetch: version {version} has no server or no client download")
    return {"sha1": server["sha1"], "size": server["size"], "url": server["url"],
            "client": {"sha1": client["sha1"], "size": client["size"], "url": client["url"]}}


def ensure_client(version, client):
    """The path of the version's client jar, checked against `client`'s SHA-1, downloading it if
    it isn't there."""
    jar = client_path(version)
    if jar.is_file() and file_sha1(jar) == client["sha1"]:
        return jar
    print(f"fetch: downloading {client['url']} ({client['size']:,} bytes)", file=sys.stderr)
    data = get(client["url"])
    if len(data) != client["size"] or hashlib.sha1(data).hexdigest() != client["sha1"]:
        sys.exit("fetch: the client download doesn't match its size and SHA-1")
    JARS.mkdir(parents=True, exist_ok=True)
    tmp = jar.with_suffix(".jar.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, jar)
    return jar


def pin(version):
    all_pins = pins()
    all_pins[version] = lookup(version)
    client = all_pins[version]["client"]
    client["data"] = data_stretch(ensure_client(version, client))
    VERSIONS.write_text(json.dumps(all_pins, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"fetch: pinned {version} to SHA-1 {all_pins[version]['sha1']} in {VERSIONS.name}")


def ensure(version, download=True):
    """Returns the path of the version's jar, verified against its pin, downloading it if needed."""
    want = pins().get(version)
    if want is None:
        sys.exit(f"fetch: {version} isn't pinned in {VERSIONS}. Run `py -I oracle/fetch.py --version {version} --pin`.")
    jar = jar_path(version)
    if jar.is_file():
        if file_sha1(jar) == want["sha1"]:
            return jar
        if not download:
            sys.exit(f"fetch: {jar} doesn't match the pinned SHA-1 {want['sha1']}")
        print(f"fetch: {jar} doesn't match the pinned SHA-1; downloading it again", file=sys.stderr)
    elif not download:
        sys.exit(f"fetch: {jar} is missing. Run `py -I oracle/fetch.py --version {version}`.")

    print(f"fetch: downloading {want['url']} ({want['size']:,} bytes)", file=sys.stderr)
    data = get(want["url"])
    if len(data) != want["size"] or hashlib.sha1(data).hexdigest() != want["sha1"]:
        sys.exit("fetch: the download doesn't match the pinned size and SHA-1")
    JARS.mkdir(parents=True, exist_ok=True)
    tmp = jar.with_suffix(".jar.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, jar)
    return jar


def install(version, source):
    """Copies a local jar into place, with no network, if it matches the version's pin."""
    want = pins().get(version)
    if want is None:
        sys.exit(f"fetch: {version} isn't pinned in {VERSIONS}")
    source = Path(source)
    if not source.is_file():
        sys.exit(f"fetch: {source} doesn't exist")
    if file_sha1(source) != want["sha1"]:
        sys.exit(f"fetch: {source} doesn't match the pinned SHA-1 {want['sha1']}; it's a different jar")
    JARS.mkdir(parents=True, exist_ok=True)
    jar = jar_path(version)
    tmp = jar.with_suffix(".jar.tmp")
    tmp.write_bytes(source.read_bytes())
    os.replace(tmp, jar)
    return jar


def main():
    parser = argparse.ArgumentParser(description="Fetch and verify Mojang's server jar.")
    parser.add_argument("--version", default="26.3")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="only verify the jar that's there")
    mode.add_argument("--pin", action="store_true", help="pin the version from Mojang's manifest")
    mode.add_argument("--jar", metavar="PATH", help="install a local jar instead of downloading one")
    args = parser.parse_args()
    if args.pin:
        pin(args.version)
        return
    jar = install(args.version, args.jar) if args.jar else ensure(args.version, download=not args.check)
    print(f"fetch: {jar} matches the pinned SHA-1 {pins()[args.version]['sha1']}")


if __name__ == "__main__":
    main()
