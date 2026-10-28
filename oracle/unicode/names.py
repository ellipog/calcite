"""Writes src/java/names.calx, the character names Java's Character.codePointOf reads, from JDK 25.

    py -I oracle/unicode/names.py            # run Names.java on JDK 25 and write the module
    py -I oracle/unicode/names.py --check    # fail if what's committed is out of date

Vanilla's SNBT reads `\\N{SNOWMAN}` as the character Java's `Character.codePointOf` names, which
takes back exactly the names `Character.getName` gives. Names.java prints those for every code
point, by calling the JDK's public API only, and this turns them into a module: the names of
their own, sorted and front-coded, and the runs of code points Java names by their block and
number instead, such as `CJK UNIFIED IDEOGRAPHS 4E00`. The names are Unicode's, under the
Unicode License V3, whose notice the module keeps.
"""

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORACLE = HERE.parent
CALCITE = ORACLE.parent
MODULE = CALCITE / "src" / "java" / "names.calx"
sys.path.insert(0, str(ORACLE))
from jdk import find_java_home, java  # noqa: E402

NOTICE = """UNICODE LICENSE V3

COPYRIGHT AND PERMISSION NOTICE

Copyright © 1991-2024 Unicode, Inc.

NOTICE TO USER: Carefully read the following legal agreement. BY
DOWNLOADING, INSTALLING, COPYING OR OTHERWISE USING DATA FILES, AND/OR
SOFTWARE, YOU UNEQUIVOCALLY ACCEPT, AND AGREE TO BE BOUND BY, ALL OF THE
TERMS AND CONDITIONS OF THIS AGREEMENT. IF YOU DO NOT AGREE, DO NOT
DOWNLOAD, INSTALL, COPY, DISTRIBUTE OR USE THE DATA FILES OR SOFTWARE.

Permission is hereby granted, free of charge, to any person obtaining a
copy of data files and any associated documentation (the "Data Files") or
software and any associated documentation (the "Software") to deal in the
Data Files or Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, and/or sell
copies of the Data Files or Software, and to permit persons to whom the
Data Files or Software are furnished to do so, provided that either (a)
this copyright and permission notice appear with all copies of the Data
Files or Software, or (b) this copyright and permission notice appear in
associated Documentation.

THE DATA FILES AND SOFTWARE ARE PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT OF
THIRD PARTY RIGHTS.

IN NO EVENT SHALL THE COPYRIGHT HOLDER OR HOLDERS INCLUDED IN THIS NOTICE
BE LIABLE FOR ANY CLAIM, OR ANY SPECIAL INDIRECT OR CONSEQUENTIAL DAMAGES,
OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION,
ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THE DATA
FILES OR SOFTWARE.

Except as contained in this notice, the name of a copyright holder shall
not be used in advertising or otherwise to promote the sale, use or other
dealings in these Data Files or Software without prior written
authorization of the copyright holder."""

# The first character of a line says how much of the line before's name it shares: `0` for
# none, and one more for each character.
SHARED_BASE = 0x30


def dump(home):
    """Every (code point, name) Character.getName gives, in code point order."""
    out = subprocess.run([str(java(home)), str(HERE / "Names.java")], capture_output=True, check=True).stdout
    pairs = []
    for line in out.decode("utf-8").splitlines():
        hexcp, name = line.split(";", 1)
        pairs.append((int(hexcp, 16), name))
    return pairs


def module(pairs):
    """The text of src/java/names.calx."""
    named = []
    blocks = []  # [name, first, last]
    for cp, name in pairs:
        suffix = " " + format(cp, "X")
        if name.endswith(suffix):
            block = name[: -len(suffix)]
            if blocks and blocks[-1][0] == block and blocks[-1][2] == cp - 1:
                blocks[-1][2] = cp
            else:
                blocks.append([block, cp, cp])
        else:
            named.append((name, cp))
    named.sort()
    for name, _ in named:
        if '"#' in name or "#{" in name or ";" in name or name != name.strip():
            sys.exit(f"a name the table can't hold: {name!r}")
    lines = []
    previous = ""
    for name, cp in named:
        shared = 0
        while shared < min(len(name), len(previous)) and name[shared] == previous[shared]:
            shared += 1
        if SHARED_BASE + shared >= 0x7B:
            sys.exit(f"{name} shares too much with the name before it")
        lines.append(f"{chr(SHARED_BASE + shared)}{name[shared:]};{cp:X}")
        previous = name
    out = []
    out.append("/// The names Java's `Character.getName` gives code points, which `Character.codePointOf`")
    out.append("/// takes back, from JDK 25, which has Unicode 16.0's. Written by oracle/unicode/names.py")
    out.append("/// from what the JDK's public API gives: don't edit it.")
    out.append("///")
    out.append("/// The names are the Unicode Character Database's, under this notice:")
    out.append("///")
    for line in NOTICE.split("\n"):
        out.append("/// " + line if line else "///")
    out.append("module java.names")
    out.append("")
    out.append("/// A run of code points with no name of their own, which Java names by their block and")
    out.append("/// their number in uppercase hex, as `CJK UNIFIED IDEOGRAPHS 4E00`.")
    out.append("pub struct Block {")
    out.append("    pub name: String")
    out.append("    pub first: u32")
    out.append("    pub last: u32")
    out.append("}")
    out.append("")
    out.append(f"/// The {len(blocks)} runs, in code point order.")
    out.append("pub fn blocks() -> List<Block> {")
    out.append("    return [")
    for name, first, last in blocks:
        out.append(f'        Block {{ name: "{name}", first: 0x{first:X}, last: 0x{last:X} }},')
    out.append("    ]")
    out.append("}")
    out.append("")
    out.append(f"/// The {len(named)} names of their own, sorted, a line each: a character saying how many of")
    out.append(f"/// the line before's first characters the name shares, `0` for none and one more for each,")
    out.append("/// then the rest of the name, then `;` and the code point in uppercase hex.")
    out.append("pub fn named() -> String {")
    out.append('    return #"')
    for line in lines:
        out.append(line)
    out.append('"#')
    out.append("}")
    return "\n".join(out) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the committed module is out of date")
    parser.add_argument("--java-home", help="the JDK 25 to ask")
    args = parser.parse_args()
    text = module(dump(find_java_home(args.java_home)))
    old = MODULE.read_text(encoding="utf-8") if MODULE.exists() else None
    if old == text:
        return 0
    if args.check:
        print(f"{MODULE.relative_to(CALCITE).as_posix()} is out of date: run oracle/unicode/names.py", file=sys.stderr)
        return 1
    MODULE.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {MODULE.relative_to(CALCITE).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
