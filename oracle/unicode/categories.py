"""Writes src/java/categories.calx, the Unicode categories Java's regular expressions ask about, from JDK 25.

    py -I oracle/unicode/categories.py            # run Categories.java on JDK 25 and write the module
    py -I oracle/unicode/categories.py --check    # fail if what's committed is out of date

Java's `\\b` and `\\B` take a non-spacing mark as a word character when a letter or digit comes
before it, past any other non-spacing marks. Categories.java prints the code points
`Character.getType` puts in NON_SPACING_MARK and the UTF-16 units `Character.isLetterOrDigit`
takes, as runs, by calling the JDK's public API only, and this turns them into a module of
sorted run tables. The categories are Unicode's, under the Unicode License V3, whose notice the
module keeps.
"""

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORACLE = HERE.parent
CALCITE = ORACLE.parent
MODULE = CALCITE / "src" / "java" / "categories.calx"
sys.path.insert(0, str(ORACLE))
sys.path.insert(0, str(HERE))
from jdk import find_java_home, java  # noqa: E402
from names import NOTICE  # noqa: E402


def dump(home):
    """The runs Categories.java prints, by kind: {"mn": [(first, last)], "ld": [...]}."""
    out = subprocess.run([str(java(home)), str(HERE / "Categories.java")], capture_output=True, check=True).stdout
    runs = {"mn": [], "ld": []}
    for line in out.decode("utf-8").splitlines():
        kind, span = line.split(" ", 1)
        first, last = span.split(";")
        runs[kind].append((int(first, 16), int(last, 16)))
    return runs


def table(name, kind, values):
    """A constant array of the values, eight to a line."""
    lines = [f"const {name}: [{kind}; {len(values)}] = ["]
    for i in range(0, len(values), 8):
        lines.append("    " + " ".join(f"0x{v:X}," for v in values[i : i + 8]))
    lines.append("]")
    return lines


def search(name, guard, runs):
    """A binary search for the run `c` would be in, the last whose first is at most `c`, in the
    tables named `name`, after `guard`, which rules out code points none of the runs hold."""
    return [
        f"    if {guard} {{",
        "        return false",
        "    }",
        "    var lo: usize = 0",
        f"    var hi: usize = {len(runs)}",
        "    while lo < hi {",
        "        let mid = lo + (hi - lo) / 2",
        f"        if {name}_FIRST[mid] <= c {{",
        "            lo = mid + 1",
        "        } else {",
        "            hi = mid",
        "        }",
        "    }",
        f"    return lo > 0 and c <= {name}_LAST[lo - 1]",
    ]


def module(runs):
    """The text of src/java/categories.calx."""
    marks = runs["mn"]
    letters = runs["ld"]
    out = []
    out.append("/// The Unicode categories Java's regular expressions ask about, as JDK 25 gives them, which")
    out.append("/// has Unicode 16.0's. Written by oracle/unicode/categories.py from what the JDK's public API")
    out.append("/// gives: don't edit it.")
    out.append("///")
    out.append("/// The categories are the Unicode Character Database's, under this notice:")
    out.append("///")
    for line in NOTICE.split("\n"):
        out.append("/// " + line if line else "///")
    out.append("module java.categories")
    out.append("")
    out.append("/// Whether Java's `Character.getType` puts the code point in `NON_SPACING_MARK`, Unicode's Mn.")
    out.append("pub fn is_non_spacing_mark(c: u32) -> bool {")
    out += search("MARK", f"c < 0x{marks[0][0]:X}", marks)
    out.append("}")
    out.append("")
    out.append("/// Whether Java's `Character.isLetterOrDigit` takes the UTF-16 unit: a letter, of any of")
    out.append("/// Unicode's L categories, or a decimal digit, Nd. A surrogate never is.")
    out.append("pub fn is_letter_or_digit(c: u32) -> bool {")
    out.append("    if c < 0x80 {")
    out.append("        return (c >= 0x30 and c <= 0x39) or ((c | 0x20) >= 0x61 and (c | 0x20) <= 0x7A)")
    out.append("    }")
    out += search("LETTER", "c > 0xFFFF", letters)
    out.append("}")
    out.append("")
    out.append(f"// The {len(marks)} runs of non-spacing marks: where each starts, and where it ends.")
    out += table("MARK_FIRST", "u32", [f for f, _ in marks])
    out += table("MARK_LAST", "u32", [l for _, l in marks])
    out.append("")
    out.append(f"// The {len(letters)} runs of units that are letters or digits.")
    out += table("LETTER_FIRST", "u32", [f for f, _ in letters])
    out += table("LETTER_LAST", "u32", [l for _, l in letters])
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
        print(f"{MODULE.relative_to(CALCITE).as_posix()} is out of date: run oracle/unicode/categories.py", file=sys.stderr)
        return 1
    MODULE.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {MODULE.relative_to(CALCITE).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
