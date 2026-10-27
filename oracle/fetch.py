"""Fetches Mojang's server jar for a game version and checks it against a pinned SHA-1 (D30, P2.4).

    py -I oracle/fetch.py [--version 26.3]           download if missing, then verify
    py -I oracle/fetch.py [--version 26.3] --check   verify only, never download
    py -I oracle/fetch.py --version X --pin          look X up in Mojang's manifest and pin it

The jar goes to oracle/jars/server-<version>.jar, which is gitignored: nothing from Mojang is ever
committed. What is committed is oracle/versions.json, the jar's URL, size and SHA-1 per version,
so every checkout builds against the same bytes and a jar that's already there is checked offline.
Pinning reads Mojang's version manifest, then the version's metadata, checking the SHA-1 the
manifest gives for it.

The vanilla adapter's build and the data generator step both call ensure(); so will Calcite's build.
"""

import argparse
import hashlib
import json
import os
import sys
import urllib.request
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


def lookup(version):
    """The server jar's {sha1, size, url} from Mojang's manifest, with the metadata's SHA-1 checked."""
    manifest = json.loads(get(MANIFEST))
    entry = next((v for v in manifest["versions"] if v["id"] == version), None)
    if entry is None:
        sys.exit(f"fetch: Mojang's manifest has no version {version}")
    meta = get(entry["url"])
    if hashlib.sha1(meta).hexdigest() != entry["sha1"]:
        sys.exit(f"fetch: {version}'s metadata doesn't match the manifest's SHA-1")
    server = json.loads(meta).get("downloads", {}).get("server")
    if server is None:
        sys.exit(f"fetch: version {version} has no server download")
    return {"sha1": server["sha1"], "size": server["size"], "url": server["url"]}


def pin(version):
    all_pins = pins()
    all_pins[version] = lookup(version)
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


def main():
    parser = argparse.ArgumentParser(description="Fetch and verify Mojang's server jar.")
    parser.add_argument("--version", default="26.3")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="only verify the jar that's there")
    mode.add_argument("--pin", action="store_true", help="pin the version from Mojang's manifest")
    args = parser.parse_args()
    if args.pin:
        pin(args.version)
        return
    jar = ensure(args.version, download=not args.check)
    print(f"fetch: {jar} matches the pinned SHA-1 {pins()[args.version]['sha1']}")


if __name__ == "__main__":
    main()
