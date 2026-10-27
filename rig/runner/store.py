"""What the rig keeps: expected hashes and quarantine (committed), goldens (gitignored)."""

import base64
import json
from pathlib import Path


def _write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=False, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


class Store:
    def __init__(self, root, game_version):
        self.root = Path(root)
        self.version = game_version
        self.expected_dir = self.root / "expected" / game_version
        self.golden_dir = self.root / "golden" / game_version

    # Expected hashes: expected/<version>/<probe>.json

    def expected(self, probe):
        """{case id: hash} for a probe, or {} if it was never recorded."""
        path = self.expected_dir / f"{probe}.json"
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))["hashes"]

    def expected_meta(self, probe):
        path = self.expected_dir / f"{probe}.json"
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if k != "hashes"}

    def save_expected(self, probe, probe_version, about, hashes):
        _write_json(self.expected_dir / f"{probe}.json", {
            "probe": probe,
            "probe_version": probe_version,
            "game_version": self.version,
            "recorded_with": about,
            "hashes": dict(sorted(hashes.items())),
        })

    # Quarantine: expected/<version>/quarantine.json, {"probe:case": reason}

    def quarantine(self):
        path = self.expected_dir / "quarantine.json"
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))["cases"]

    def save_quarantine(self, cases):
        _write_json(self.expected_dir / "quarantine.json", {
            "about": "Cases where vanilla itself isn't repeatable, found by the self-check. They aren't scored.",
            "cases": dict(sorted(cases.items())),
        })

    # Goldens: golden/<version>/<probe>.jsonl, one full result per line

    def save_golden(self, probe, records):
        path = self.golden_dir / f"{probe}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            for case_id, result in records:
                f.write(json.dumps({
                    "id": case_id,
                    "status": result.status,
                    "hash": result.digest(),
                    "output": result.output,
                    "blobs": [base64.b64encode(b).decode("ascii") for b in result.blobs],
                }, ensure_ascii=False) + "\n")

    def golden(self, probe, case_id):
        path = self.golden_dir / f"{probe}.jsonl"
        if not path.is_file():
            return None
        with open(path, encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                if record["id"] == case_id:
                    record["blobs"] = [base64.b64decode(b) for b in record["blobs"]]
                    return record
        return None
