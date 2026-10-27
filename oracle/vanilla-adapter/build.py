"""Build the vanilla adapter against a local server jar.

Usage: py -I build.py [--version 26.3] [--java-home PATH]

Fetches oracle/jars/server-<version>.jar if it's missing and checks it against
its pin (oracle/fetch.py), reads the bundler's library list from it, extracts
the inner server jar and its libraries into oracle/work/ (checking each
SHA-256 against the list), compiles the adapter with JDK 25, and writes
build/<platform>/adapter.json: the command line the rig's runner starts the
adapter with. Each platform builds into its own folder, so a Windows checkout
can also be built and run from WSL.

Nothing from the jar leaves oracle/work/ and build/, which are both gitignored.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORACLE = HERE.parent
WORK = ORACLE / "work"
PLATFORM = "windows" if os.name == "nt" else sys.platform
BUILD = HERE / "build" / PLATFORM

sys.path.insert(0, str(ORACLE))
import fetch  # noqa: E402
from jdk import EXE, REQUIRED_JAVA, find_java_home  # noqa: E402


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_list(bundle, name):
    """Parse a bundler list: one `sha256<TAB>id<TAB>path` entry per line."""
    entries = []
    for line in bundle.read(name).decode("utf-8").splitlines():
        if line.strip():
            digest, ident, path = line.split("\t")
            entries.append((digest, ident, path))
    return entries


def extract(bundle, member, dest, digest):
    """Extract one bundled file unless a copy with the right hash is there."""
    if dest.is_file() and sha256(dest) == digest:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    with bundle.open(member) as src, open(tmp, "wb") as out:
        shutil.copyfileobj(src, out)
    if sha256(tmp) != digest:
        tmp.unlink()
        sys.exit(f"build: {member} doesn't match the bundler's SHA-256")
    os.replace(tmp, dest)


def unpack(version):
    jar = fetch.ensure(version)
    with zipfile.ZipFile(jar) as bundle:
        classpath = []
        for digest, ident, path in read_list(bundle, "META-INF/versions.list"):
            dest = WORK / "versions" / path
            extract(bundle, f"META-INF/versions/{path}", dest, digest)
            classpath.append(dest)
        for digest, ident, path in read_list(bundle, "META-INF/libraries.list"):
            dest = WORK / "libraries" / path
            extract(bundle, f"META-INF/libraries/{path}", dest, digest)
            classpath.append(dest)
    return classpath


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", default="26.3")
    parser.add_argument("--java-home")
    args = parser.parse_args()

    classpath = unpack(args.version)
    java_home = find_java_home(args.java_home)
    exe = EXE

    classes = BUILD / "classes"
    if classes.exists():
        shutil.rmtree(classes)
    classes.mkdir(parents=True)
    sources = sorted(str(p) for p in (HERE / "src").rglob("*.java"))
    cp = os.pathsep.join(str(p) for p in classpath)
    # Lint everything but: annotations the libraries reference without shipping (classfile), the
    # deprecated vanilla methods probes call on purpose (deprecation), and serialVersionUID (serial).
    javac = subprocess.run(
        [str(java_home / "bin" / f"javac{exe}"), "--release", str(REQUIRED_JAVA),
         "-encoding", "UTF-8", "-Xlint:all,-processing,-classfile,-deprecation,-serial", "-Werror",
         "-cp", cp, "-d", str(classes), *sources],
    )
    if javac.returncode != 0:
        sys.exit("build: javac failed")

    adapter = {
        "adapter": "vanilla",
        "game_version": args.version,
        "argv": [
            str(java_home / "bin" / f"java{exe}"),
            # Logs go to stderr: stdout carries only frames.
            f"-Dlog4j2.configurationFile={HERE / 'log4j2.xml'}",
            "-Dfile.encoding=UTF-8",
            "-cp", os.pathsep.join([str(classes), cp]),
            "calcite.rig.vanilla.Main",
        ],
        # The game creates files relative to the working directory.
        "cwd": str(WORK),
        # JVM flags for each vanilla configuration the rig records (D60). `strict-math` is the
        # reference: with HotSpot's LIBM intrinsics off, Math gives StrictMath's results.
        "configs": {
            "strict-math": ["-XX:+UnlockDiagnosticVMOptions", "-XX:-UseLibmIntrinsic"],
            "intrinsics": [],
        },
        "default_config": "strict-math",
    }
    (BUILD / "adapter.json").write_text(json.dumps(adapter, indent=2) + "\n", encoding="utf-8")
    print(f"build: wrote {BUILD / 'adapter.json'}")


if __name__ == "__main__":
    main()
