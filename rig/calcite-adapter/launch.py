"""Builds Calcite's rig adapter with calx, then runs it (P3.8).

The adapter is Calcite's own code, in src/rig/adapter.calx. This script only builds it and
hands it the runner's standard input and output. A release build takes under half a second,
and calx reuses it when nothing changed, so it builds on every start and is never stale.

calx is found from the CALX environment variable, then PATH, then a calx checkout beside this
repository (../calx), as the workspace has it. CALCITE_DEBUG=1 builds without --release, so
the adapter checks that it frees everything it allocates.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

CALCITE = Path(__file__).resolve().parents[2]
EXE = ".exe" if os.name == "nt" else ""
PLATFORM = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")


def find_calx():
    if os.environ.get("CALX"):
        return os.environ["CALX"]
    if found := shutil.which("calx"):
        return found
    beside = CALCITE.parent / "calx" / "build" / "compiler" / PLATFORM / f"calx{EXE}"
    if beside.is_file():
        return str(beside)
    sys.exit("calcite-adapter: no calx. Set CALX, put calx on PATH, or build ../calx")


def main():
    debug = os.environ.get("CALCITE_DEBUG") == "1"
    binary = CALCITE / "build" / "rig" / PLATFORM / f"calcite-adapter{'-debug' if debug else ''}{EXE}"
    build = [find_calx(), "build", *([] if debug else ["--release"]), "src/rig/adapter.calx", "-o", str(binary)]
    # Standard output carries only frames, so the build's output goes to standard error.
    built = subprocess.run(build, cwd=CALCITE, stdout=sys.stderr, stdin=subprocess.DEVNULL)
    if built.returncode != 0:
        sys.exit(f"calcite-adapter: the build failed with status {built.returncode}")
    return subprocess.run([str(binary)]).returncode


if __name__ == "__main__":
    sys.exit(main())
