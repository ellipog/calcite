"""Writes cases/allow_list/generated.json: allowed_symlinks.txt read as a server reads it as it
starts, by vanilla's LevelStorageSource.parseValidator, then asked about link targets.

    py -I cases/allow_list/gen.py

Every case is for one system, since Windows matches globs with \\ between names and regular
expressions without regard to case, and a target is a path as that system's Path writes it. So
each case here comes twice, for Windows and for Linux, with the paths written as each writes
them. Then random files of globs, regular expressions and prefixes, with random targets.
"""

import base64
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "rig" / "runner"))
from cases import splitmix64, write_file  # noqa: E402

BS = "\\"


def b64(data):
    return base64.b64encode(bytes(data)).decode()


def win(path):
    """A Linux path as Windows writes the same: under C: if it's absolute, with \\ between names."""
    if path.startswith("/"):
        path = "C:" + path
    return path.replace("/", BS)


def windows_path(path):
    """Whether Windows' Path takes `path`: none of `<>:"|?*` or controls, but a drive's colon,
    and no name ending in a space."""
    for i, c in enumerate(path):
        if c in '<>"|?*' or ord(c) < 32 or (c == ":" and i != 1):
            return False
    return all(not name.endswith(" ") for name in path.split(BS))


def case(name, text, paths, wpaths=None, wtext=None):
    """The case for each system. `text` is the file, bytes or a string, or None for no file;
    `wtext` and `wpaths` are Windows' if they aren't the same with paths as Windows writes them."""
    out = []
    for system in ("linux", "windows"):
        t = text if system == "linux" or wtext is None else wtext
        ps = paths if system == "linux" else (wpaths if wpaths is not None else [win(p) for p in paths])
        if system == "windows":
            ps = [p for p in ps if windows_path(p)]
        c = {"id": f"{system}-{name}", "system": system, "input": {"paths": ps}}
        if t is not None:
            c["blobs"] = [b64(t.encode() if isinstance(t, str) else t)]
        out.append(c)
    return out


# Targets most cases ask about.
SOME = ["/data/x", "/data/x/y", "/datax", "/other/x", "relative/x", "../up", "/DATA/X", "/"]


def by_hand():
    cases = []
    add = cases.extend
    # Reading the file.
    add(case("no-file", None, SOME))
    add(case("empty", "", SOME))
    add(case("only-comments", "# a comment\n#/data\n", SOME))
    add(case("blank-lines", "\n\n   \n\t\n" + chr(0x2028) + "\n" + chr(0x3000) + "\n/data\n", SOME))
    add(case("no-break-space-is-an-entry", chr(0xA0) + "\n/data\n", SOME + [chr(0xA0) + "x"], [win(p) for p in SOME] + [chr(0xA0) + "x"]))
    add(case("crlf", "# x\r\n/data/\r\n[prefix]/other\r\n", SOME))
    add(case("cr-only", "/data/\r/other", SOME))
    add(case("no-newline-at-end", "/other", SOME))
    add(case("byte-order-mark", "\ufeff/data", SOME))
    add(case("byte-order-mark-comment", "\ufeff# x\n/other", SOME))
    add(case("leading-space-is-a-prefix", " [prefix]/data", SOME + [" [prefix]/data/x"], [win(p) for p in SOME] + [" [prefix]C:" + BS + "data"]))
    add(case("comment-after-space", " # x\n/other", SOME + [" # x"], [win(p) for p in SOME] + [" # x"]))
    # Prefixes.
    add(case("prefix-plain", "/data/", SOME))
    add(case("prefix-typed", "[prefix]/data", SOME))
    add(case("prefix-empty-allows-all", "[prefix]", SOME))
    add(case("prefix-relative", "[prefix]..", SOME))
    add(case("prefix-forward-slash", "/data/", SOME, wtext="C:/data/"))
    add(case("prefix-case", "/DATA", SOME, wtext="C:" + BS + "DATA"))
    add(case("prefixes-several", "/nothing\n/other/\n[prefix]/data/x/", SOME))
    # Lines that aren't entries.
    for name, text in [("unterminated", "[prefix/data"), ("unterminated-empty", "["), ("type-case", "[Glob]/data/*"),
                       ("type-empty", "[]/data"), ("type-unknown", "[path]/data"), ("type-space", "[ glob]/data/*"),
                       ("bad-after-good", "/data\n[nope]x"), ("bad-before-good", "[nope]x\n/data"),
                       ("bad-after-bad-regex", "[regex](\n[nope]")]:
        add(case(name, text, SOME))
    add(case("bracket-in-contents", "[glob]]x", ["]x", "/data"], ["]x", "C:" + BS + "data"]))
    add(case("type-then-bracket", "[regex]][a]", ["]a", "]]a"]))
    # Bytes that aren't UTF-8.
    for name, data in [("not-utf8", b"/data\n\xff\n"), ("not-utf8-first", b"\xc3(\n/data"), ("overlong", b"/da\xc0\xafta"),
                       ("surrogate", b"/data\xed\xa0\x80"), ("cut-off", b"/data\xe2\x82"), ("past-unicode", b"/\xf4\x90\x80\x80")]:
        add(case(name, data, SOME))
    add(case("four-byte-utf8", "/data/" + chr(0x1F600), ["/data/" + chr(0x1F600) + "x", "/data/x"]))
    # Globs.
    add(case("glob-star", "[glob]/data/*", SOME, wtext="[glob]C:/data/*"))
    add(case("glob-star-star", "[glob]/data/**", SOME, wtext="[glob]C:/data/**"))
    add(case("glob-question", "[glob]/data/?", SOME + ["/data/" + chr(0xE9), "/data/" + chr(0x1F600)], wtext="[glob]C:/data/?"))
    add(case("glob-braces", "[glob]/{data,other}/*", SOME, wtext="[glob]C:/{data,other}/*"))
    add(case("glob-class", "[glob]/data/[!y]", SOME + ["/data/y", "/data/z"], wtext="[glob]C:/data/[!y]"))
    add(case("glob-range", "[glob]/data/[a-x]", SOME + ["/data/y"], wtext="[glob]C:/data/[a-x]"))
    add(case("glob-relative", "[glob]*/*", SOME))
    add(case("glob-backslash-escapes", "[glob]/data/" + BS + "*", SOME + ["/data/*"], wtext="[glob]C:" + BS + BS + "data" + BS + BS + "*", wpaths=[win(p) for p in SOME] + ["C:" + BS + "data" + BS + "x"]))
    add(case("glob-dots", "[glob]../*", SOME))
    add(case("glob-regex-characters", "[glob]/d(a)+t|a$/^*", ["/d(a)+t|a$/^x", "/data/x"]))
    add(case("glob-case", "[glob]/DATA/*", SOME, wtext="[glob]C:/DATA/*"))
    add(case("glob-unicode-case", "[glob]/" + chr(0xE4) + "/*", ["/" + chr(0xC4) + "/x", "/" + chr(0xE4) + "/x"], wtext="[glob]C:/" + chr(0xE4) + "/*"))
    for name, glob in [("glob-unclosed-brace", "/data/{a"), ("glob-nested-braces", "/{a,{b}}"), ("glob-unclosed-class", "/data/[a"),
                       ("glob-trailing-escape", "/data/" + BS), ("glob-separator-in-class", "/data/[/]"), ("glob-bad-range", "/data/[z-a]")]:
        add(case(name, "/data\n[glob]" + glob, SOME))
    add(case("glob-error-unused", "[glob]{", []))
    # Regular expressions.
    add(case("regex-dot-star", "[regex]/data/.*", SOME, wtext="[regex]C:" + BS + BS + "data" + BS + BS + ".*"))
    add(case("regex-whole", "[regex]/data", SOME + ["/data"]))
    add(case("regex-alternatives", "[regex]/(data|other)/x", SOME, wtext="[regex]C:" + BS + BS + "(data|other)" + BS + BS + "x"))
    add(case("regex-digits", "[regex]/data/" + BS + "d+", ["/data/1", "/data/12a", "/data/x"], wtext="[regex]C:" + BS + BS + "data" + BS + BS + BS + "d+"))
    add(case("regex-case", "[regex]/DATA/X", SOME, wtext="[regex]C:" + BS + BS + "DATA" + BS + BS + "X"))
    add(case("regex-inline-flag", "[regex](?i)/data/x", SOME, wtext="[regex](?-i)C:" + BS + BS + "data" + BS + BS + "x"))
    add(case("regex-unicode-case", "[regex]/" + chr(0xE4) + ".*", ["/" + chr(0xC4) + "x", "/" + chr(0xE4) + "x"], wtext="[regex]C:" + BS + BS + chr(0xE4) + ".*", wpaths=["C:" + BS + chr(0xC4) + "x", "C:" + BS + chr(0xE4) + "x"]))
    add(case("regex-sigma", "[regex]/" + chr(0x3C3), ["/" + chr(0x3A3), "/" + chr(0x3C2)], wtext="[regex]" + BS + BS + chr(0x3C3), wpaths=[BS + chr(0x3A3), BS + chr(0x3C2)]))
    add(case("regex-kelvin", "[regex]/k", ["/K", "/" + chr(0x212A)], wtext="[regex]" + BS + BS + "k", wpaths=[BS + "K", BS + chr(0x212A)]))
    add(case("regex-backref", "[regex]/(.+)/" + BS + "1", ["/ab/ab", "/ab/AB", "/ab/cd"], wtext="[regex]" + BS + BS + "(.+)" + BS + BS + BS + "1", wpaths=[BS + "ab" + BS + "ab", BS + "ab" + BS + "AB", BS + "ab" + BS + "cd"]))
    add(case("regex-lookahead", "[regex](?!/data).*", SOME))
    add(case("regex-quoted", "[regex]" + BS + "Q/data/.*" + BS + "E", SOME + ["/data/.*"], wtext="[regex]" + BS + "QC:" + BS + "data" + BS + ".*" + BS + "E", wpaths=[win(p) for p in SOME] + ["C:" + BS + "data" + BS + ".*"]))
    add(case("regex-empty", "[regex]", SOME))
    add(case("regex-comments-flag", "[regex](?x) / data / .* # anything", SOME, wtext="[regex](?x) C: " + BS + BS + " data " + BS + BS + " .* # anything"))
    for name, regex in [("regex-unclosed-group", "(/data"), ("regex-dangling", "*/data"), ("regex-unclosed-class", "[a"), ("regex-bad-escape", BS + "y"),
                        ("regex-bad-repetition", "a{2,1}"), ("regex-trailing-backslash", "/data" + BS), ("regex-unknown-group", BS + "k<n>")]:
        add(case(name, "/data\n[regex]" + regex, SOME))
    add(case("regex-error-after-good", "[regex]/data/.*\n[regex](", SOME))
    add(case("regex-error-unused", "[regex](", []))
    # Targets on Windows.
    W = ["C:" + BS + "data" + BS + "x", "c:" + BS + "data" + BS + "x", BS + BS + "server" + BS + "share" + BS + "x", "C:x", BS + "data" + BS + "x", "D:" + BS]
    cases.append({"id": "windows-roots", "system": "windows", "input": {"paths": W}, "blobs": [b64(("[glob]?:/data/*\n[regex]" + BS + BS + BS + BS + "server.*\n[prefix]C:").encode())]})
    cases.append({"id": "windows-glob-backslash-in-class", "system": "windows", "input": {"paths": W}, "blobs": [b64(("[glob]C:" + BS + BS + "data" + BS + BS + "[" + BS + BS + "]").encode())]})
    return cases


# Pieces of random entries, as Linux paths, which Windows' cases write as Windows does.
GLOB_PIECES = ["/", "data", "x", "y", "*", "**", "?", "[a-x]", "[!y]", "{data,other}", "{x,y,}", ".", "..", "-", chr(0xE9), "X", "[xy]", "/data/", "D"]
REGEX_PIECES = ["/", "data", "x", "y", ".", ".*", ".+", "[a-z]", "[^/]*", "(?i)", "(data|other)", "x?", "\\d", "(?:/[^/]+)*", "X", chr(0xE9), "$", "^", "\\w+", "(?=/d)", "(?!/o)"]
PATH_PIECES = ["data", "other", "x", "y", "X", "DATA", ".", "..", chr(0xE9), chr(0xC9), "1", "xy", "a-b", "d"]


def pick(rand, items):
    return items[next(rand) % len(items)]


def random_cases(count, seed):
    rand = splitmix64(seed)
    cases = []
    for k in range(count):
        lines = []
        wlines = []
        for _ in range(1 + next(rand) % 3):
            kind = next(rand) % 3
            n = 1 + next(rand) % 5
            if kind == 0:
                g = "".join(pick(rand, GLOB_PIECES) for _ in range(n))
                lines.append("[glob]" + g)
                wlines.append("[glob]" + g)
            elif kind == 1:
                r = "".join(pick(rand, REGEX_PIECES) for _ in range(n))
                lines.append("[regex]" + r)
                # Windows writes \ between names, which a regular expression escapes.
                wlines.append("[regex]" + r.replace("/", BS + BS))
            else:
                p = "/" + "/".join(pick(rand, PATH_PIECES) for _ in range(n % 3))
                lines.append(p)
                wlines.append(win(p))
        paths = []
        for _ in range(6):
            names = [pick(rand, PATH_PIECES) for _ in range(1 + next(rand) % 3)]
            p = ("/" if next(rand) % 4 else "") + "/".join(names)
            paths.append(p)
        cases.extend(case(f"random-{k}", "\n".join(lines) + "\n", paths, wtext="\n".join(wlines) + "\n"))
    return cases


def main():
    cases = by_hand() + random_cases(300, 20261031)
    write_file(HERE / "generated.json", "allow_list", "cases/allow_list/gen.py", cases, probe_version=1)


if __name__ == "__main__":
    main()
