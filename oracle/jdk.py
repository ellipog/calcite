"""Finds a JDK of the version the game targets, for the vanilla adapter and the data generator."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

REQUIRED_JAVA = 25
EXE = ".exe" if os.name == "nt" else ""


def find_java_home(explicit=None, required=REQUIRED_JAVA):
    """The first JDK of the required major version: explicit, CALCITE_JAVA_HOME, JAVA_HOME, javac
    on PATH, then common install locations, newest first."""
    candidates = [explicit, os.environ.get("CALCITE_JAVA_HOME"), os.environ.get("JAVA_HOME")]
    javac = shutil.which("javac")
    if javac:
        candidates.append(str(Path(javac).resolve().parent.parent))
    for pattern in (f"~/tools/jdk-{required}*", f"C:/Program Files/Eclipse Adoptium/jdk-{required}*",
                    f"C:/Program Files/Java/jdk-{required}*", f"/usr/lib/jvm/*{required}*", f"/opt/jdk-{required}*"):
        base = Path(pattern.split("*")[0]).expanduser()
        if base.parent.is_dir():
            candidates += [str(p) for p in sorted(base.parent.glob(base.name + "*"), reverse=True)]
    for home in candidates:
        if not home:
            continue
        java = Path(home) / "bin" / f"java{EXE}"
        if not java.is_file():
            continue
        out = subprocess.run([str(java), "-version"], capture_output=True, text=True).stderr
        # The first line reads like: openjdk version "25.0.5" 2025-10-21 LTS
        try:
            major = int(out.split('"')[1].split(".")[0])
        except (IndexError, ValueError):
            continue
        if major == required:
            return Path(home)
    sys.exit(f"no JDK {required} found. Pass --java-home or set CALCITE_JAVA_HOME.")


def java(home):
    return home / "bin" / f"java{EXE}"
