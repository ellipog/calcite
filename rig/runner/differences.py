"""The registry of deliberate differences (rig/differences/, P1.8)."""

import fnmatch
from dataclasses import dataclass
from pathlib import Path

KINDS = {"bug", "exploit", "identity", "performance", "platform"}


class DifferenceError(Exception):
    pass


@dataclass(frozen=True)
class Difference:
    id: str
    title: str
    kind: str
    cases: tuple
    path: Path

    def covers(self, key):
        """Whether this difference covers a case key, `probe:case-id`. Patterns are globs."""
        return any(fnmatch.fnmatchcase(key, pattern) for pattern in self.cases)


def _front_matter(text, path):
    """The YAML subset the registry uses: `key: value` lines and `- item` lists."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise DifferenceError(f"{path}: no front matter")
    fields, key = {}, None
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.lstrip().startswith("- "):
            if key is None or not isinstance(fields.get(key), list):
                raise DifferenceError(f"{path}: list item outside a list: {line!r}")
            fields[key].append(line.lstrip()[2:].strip().strip("\"'"))
            continue
        name, sep, value = line.partition(":")
        if not sep:
            raise DifferenceError(f"{path}: can't read {line!r}")
        key, value = name.strip(), value.strip()
        fields[key] = value.strip("\"'") if value else []
    raise DifferenceError(f"{path}: front matter isn't closed")


def load(directory):
    differences = []
    for path in sorted(Path(directory).glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        fields = _front_matter(path.read_text(encoding="utf-8"), path)
        for required in ("title", "kind", "cases"):
            if required not in fields:
                raise DifferenceError(f"{path}: missing `{required}`")
        if fields["kind"] not in KINDS:
            raise DifferenceError(f"{path}: kind must be one of {', '.join(sorted(KINDS))}")
        if not isinstance(fields["cases"], list) or not fields["cases"]:
            raise DifferenceError(f"{path}: `cases` must be a non-empty list")
        differences.append(Difference(path.stem, fields["title"], fields["kind"], tuple(fields["cases"]), path))
    return differences
