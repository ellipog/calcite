"""Regenerates every table from Mojang's server jar in one command (P2.1, gate G2.1).

    py -I oracle/datagen/datagen.py [--version 26.3] [--java-home PATH]
    py -I oracle/datagen/datagen.py --check     regenerate into a scratch folder and compare (G2.2)

Fetches and verifies the jar (oracle/fetch.py), runs Mojang's data generator with JDK 25 into
generated/<version>/datagen/, deletes the generator's .cache/ folder (it holds timestamps and is
the only output that changes between runs), then converts the reports into
generated/<version>/tables/ (convert.py). generated/ is gitignored (D30).

--check leaves generated/<version>/ alone: it regenerates into build/datagen/check/ and reports any
file whose bytes differ, so a regeneration that isn't repeatable is caught.
"""

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORACLE = HERE.parent
ROOT = ORACLE.parent
WORK = ORACLE / "work"
sys.path.insert(0, str(ORACLE))
sys.path.insert(0, str(HERE))
import convert  # noqa: E402
import fetch  # noqa: E402
from jdk import find_java_home, java  # noqa: E402

# The rig's reference configuration (D60). The reports are data, but this keeps every vanilla run
# Calcite compares against on the same floating-point behavior.
JVM_FLAGS = ["-XX:+UnlockDiagnosticVMOptions", "-XX:-UseLibmIntrinsic"]


def generate(version, java_home, base):
    """Runs the data generator and the converter into base (generated/<version>/ or a scratch copy)."""
    jar = fetch.ensure(version)
    datagen = base / "datagen"
    if datagen.exists():
        shutil.rmtree(datagen)
    datagen.parent.mkdir(parents=True, exist_ok=True)
    log = ROOT / "build" / "datagen" / f"{version}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    with open(log, "wb") as out:
        # The bundler unpacks its libraries relative to the working directory, so run it in oracle/work/.
        run = subprocess.run(
            [str(java(java_home)), *JVM_FLAGS, "-DbundlerMainClass=net.minecraft.data.Main",
             "-jar", str(jar), "--all", "--output", str(datagen)],
            cwd=WORK, stdout=out, stderr=subprocess.STDOUT)
    if run.returncode != 0:
        sys.exit(f"datagen: the data generator failed with exit code {run.returncode}; see {log}")
    shutil.rmtree(datagen / ".cache", ignore_errors=True)
    print(f"datagen: generated {sum(1 for p in datagen.rglob('*') if p.is_file()):,} files "
          f"in {time.monotonic() - start:.1f}s (log: {log})")
    try:
        index = convert.convert(version, datagen / "reports", base / "tables")
    except convert.ConvertError as e:
        sys.exit(f"datagen: convert: {e}")
    print(f"datagen: wrote {len(index['tables'])} tables to {base / 'tables'}")


def files(folder):
    return {p.relative_to(folder).as_posix(): p for p in folder.rglob("*") if p.is_file()}


def compare(a, b):
    """Relative paths that are missing from one side or differ in bytes."""
    fa, fb = files(a), files(b)
    return sorted(set(fa) ^ set(fb)) + sorted(p for p in set(fa) & set(fb) if fa[p].read_bytes() != fb[p].read_bytes())


def main():
    parser = argparse.ArgumentParser(description="Regenerate every table from the server jar.")
    parser.add_argument("--version", default="26.3")
    parser.add_argument("--java-home")
    parser.add_argument("--check", action="store_true",
                        help="regenerate into a scratch folder and compare with generated/<version>/")
    args = parser.parse_args()
    java_home = find_java_home(args.java_home)
    base = ROOT / "generated" / args.version
    if not args.check:
        generate(args.version, java_home, base)
        return
    if not (base / "tables" / "index.json").is_file():
        sys.exit(f"datagen: nothing to compare against; run datagen.py first")
    scratch = ROOT / "build" / "datagen" / "check"
    generate(args.version, java_home, scratch)
    diffs = compare(base, scratch)
    if diffs:
        print(f"datagen: {len(diffs)} files differ between {base} and {scratch}:")
        for p in diffs[:50]:
            print(f"  {p}")
        sys.exit(1)
    count = len(files(base))
    shutil.rmtree(scratch)
    print(f"datagen: the regeneration matches generated/{args.version}/ byte for byte ({count:,} files)")


if __name__ == "__main__":
    main()
