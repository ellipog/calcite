"""The oracle rig's runner (P1.3).

    py -I rig/runner/rig.py list
    py -I rig/runner/rig.py record [--probe P ...]
    py -I rig/runner/rig.py check [--probe P ...] [--variants all|name,...] [--quarantine]
    py -I rig/runner/rig.py score [--adapter calcite|vanilla|PATH] [--probe P ...]
    py -I rig/runner/rig.py diff PROBE CASE [--adapter ...]

See rig/README.md.
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cases as cases_mod  # noqa: E402
import differences as differences_mod  # noqa: E402
from protocol import Adapter, ProtocolError, Result, canonical_json  # noqa: E402
from store import Store  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build" / "rig"
ADAPTERS = {
    "vanilla": ROOT / "oracle" / "vanilla-adapter" / "build" / "adapter.json",
    "calcite": ROOT / "rig" / "calcite-adapter" / "adapter.json",
}

# Self-check variants (P1.4): each changes something a result must not depend on.
VARIANTS = {
    "default": {"jvm": [], "about": "the adapter as built"},
    "shuffled": {"jvm": [], "shuffle": True, "about": "cases in a random order, so no case depends on the one before"},
    "twice": {"jvm": [], "twice": True, "about": "every case run twice in a row, comparing the second run"},
    "interpreter": {"jvm": ["-Xint"], "about": "no JIT at all"},
    "c1": {"jvm": ["-XX:TieredStopAtLevel=1"], "about": "only the C1 compiler"},
    "c2": {"jvm": ["-XX:-TieredCompilation", "-XX:CompileThreshold=50"], "about": "only C2, compiling early"},
    "serial-1cpu": {"jvm": ["-XX:+UseSerialGC", "-XX:ActiveProcessorCount=1"], "about": "serial GC on one CPU"},
    "parallel-8cpu": {"jvm": ["-XX:+UseParallelGC", "-XX:ActiveProcessorCount=8"], "about": "parallel GC on eight CPUs"},
}


def die(message):
    print(f"rig: {message}", file=sys.stderr)
    sys.exit(2)


class Session:
    """An adapter that's restarted if it crashes, so one bad case can't end a run."""

    MAX_RESTARTS = 3

    def __init__(self, name, jvm_args=(), log_name=None):
        spec_path = ADAPTERS.get(name, Path(name))
        if not spec_path.is_file():
            hint = " Run oracle/vanilla-adapter/build.py first." if name == "vanilla" else ""
            die(f"no adapter at {spec_path}.{hint}")
        self.spec = json.loads(spec_path.read_text(encoding="utf-8"))
        argv = [sys.executable if a == "{python}" else a for a in self.spec["argv"]]
        self.argv = argv[:1] + list(jvm_args) + argv[1:]
        self.cwd = self.spec.get("cwd") or str(spec_path.parent)
        self.log = OUT / "logs" / f"{log_name or Path(name).stem}.log"
        self.restarts = 0
        self.adapter = self._start()

    def _start(self):
        return Adapter(self.argv, cwd=self.cwd, log_path=self.log)

    @property
    def probes(self):
        return self.adapter.probes

    @property
    def about(self):
        return {"adapter": self.adapter.name, "game_version": self.adapter.game_version, **self.adapter.about}

    def run(self, case):
        version = self.adapter.probes.get(case.probe)
        if version is not None and version != case.probe_version:
            return Result("error", {}, [], f"adapter has {case.probe} v{version}, case is v{case.probe_version}")
        try:
            return self.adapter.run(case.probe, case.id, case.input, case.blobs)
        except ProtocolError as e:
            self.adapter.close()
            if self.restarts >= self.MAX_RESTARTS:
                raise
            self.restarts += 1
            self.adapter = self._start()
            return Result("error", {}, [], f"adapter crashed: {e} (log: {self.log})")

    def close(self):
        self.adapter.close()


def load_cases(probes):
    try:
        return cases_mod.load_all(ROOT / "cases", probes)
    except cases_mod.CaseFileError as e:
        die(str(e))


def load_differences():
    try:
        return differences_mod.load(ROOT / "rig" / "differences")
    except differences_mod.DifferenceError as e:
        die(str(e))


def cmd_list(args):
    store = Store(ROOT, args.version)
    by_probe = load_cases(args.probe)
    quarantine = store.quarantine()
    print(f"{'probe':<12} {'cases':>6} {'recorded':>9} {'quarantined':>12}")
    for probe, cases in by_probe.items():
        expected = store.expected(probe)
        recorded = sum(1 for c in cases if c.id in expected)
        q = sum(1 for c in cases if c.key in quarantine)
        print(f"{probe:<12} {len(cases):>6} {recorded:>9} {q:>12}")


def cmd_record(args):
    store = Store(ROOT, args.version)
    by_probe = load_cases(args.probe)
    quarantine = store.quarantine()
    session = Session("vanilla")
    if session.adapter.game_version != args.version:
        die(f"the vanilla adapter is {session.adapter.game_version}, not {args.version}")
    failed = False
    try:
        for probe, cases in by_probe.items():
            started = time.time()
            records, problems = [], []
            for case in cases:
                result = session.run(case)
                if result.status != "ok":
                    lines = (result.message or "").strip().splitlines()
                    problems.append(f"  {case.key}: {result.status}: {lines[0] if lines else ''}")
                records.append((case.id, result))
            if problems:
                failed = True
                print(f"{probe}: not recorded, {len(problems)} cases didn't run:")
                print("\n".join(problems[:20]))
                continue
            old = store.expected(probe)
            hashes = {cid: r.digest() for cid, r in records}
            changed = [cid for cid, h in hashes.items() if cid in old and old[cid] != h]
            added = sum(1 for cid in hashes if cid not in old)
            removed = sum(1 for cid in old if cid not in hashes)
            store.save_golden(probe, records)
            store.save_expected(probe, cases[0].probe_version, session.about, hashes)
            print(f"{probe}: recorded {len(hashes)} cases in {time.time() - started:.1f}s"
                  f" ({added} new, {len(changed)} changed, {removed} removed)")
            for cid in changed[:20]:
                note = " (quarantined)" if f"{probe}:{cid}" in quarantine else ""
                print(f"  changed: {probe}:{cid}{note}")
    finally:
        session.close()
    sys.exit(1 if failed else 0)


def _run_variant(name, by_probe, expected_by_probe, quarantine):
    """Runs every case under one variant, returning {case key: why it differs from expected}."""
    variant = VARIANTS[name]
    session = Session("vanilla", variant["jvm"], log_name=f"vanilla-{name}")
    mismatches = {}
    try:
        work = [c for cases in by_probe.values() for c in cases]
        if variant.get("shuffle"):
            random.Random(20261027).shuffle(work)
        for case in work:
            expected = expected_by_probe[case.probe].get(case.id)
            if expected is None or case.key in quarantine:
                continue
            result = session.run(case)
            if variant.get("twice") and result.status == "ok":
                first = result.digest()
                result = session.run(case)
                if result.status == "ok" and result.digest() != first:
                    mismatches[case.key] = "differs when run again in the same process"
                    continue
            if result.status != "ok":
                mismatches[case.key] = f"{result.status}: {(result.message or '').strip()[:200]}"
            elif result.digest() != expected:
                mismatches[case.key] = "hash differs from expected"
    finally:
        session.close()
    return mismatches


def cmd_check(args):
    """The self-check: vanilla against its own recorded hashes, under each variant."""
    store = Store(ROOT, args.version)
    by_probe = load_cases(args.probe)
    quarantine = store.quarantine()
    names = list(VARIANTS) if args.variants == "all" else args.variants.split(",")
    for name in names:
        if name not in VARIANTS:
            die(f"unknown variant `{name}`. Variants: {', '.join(VARIANTS)}")
    expected = {probe: store.expected(probe) for probe in by_probe}
    unrecorded = [c.key for cases in by_probe.values() for c in cases if c.id not in expected[c.probe]]
    if unrecorded:
        print(f"check: {len(unrecorded)} cases have no expected hash yet; run `record` first. First: {unrecorded[0]}")

    found = {}
    for name in names:
        started = time.time()
        mismatches = _run_variant(name, by_probe, expected, quarantine)
        print(f"{name:<14} {len(mismatches):>5} mismatches  {time.time() - started:6.1f}s  ({VARIANTS[name]['about']})")
        for key, why in mismatches.items():
            found.setdefault(key, []).append(f"{name}: {why}")

    if not found:
        print("check: vanilla is repeatable on every recorded case")
        return
    print(f"check: {len(found)} cases aren't repeatable:")
    for key, whys in sorted(found.items())[:40]:
        print(f"  {key}: {'; '.join(whys)}")
    if args.quarantine:
        quarantine.update({k: "; ".join(v) for k, v in found.items()})
        store.save_quarantine(quarantine)
        print(f"check: quarantined them in {store.expected_dir / 'quarantine.json'}")
    sys.exit(1)


OUTCOMES = ("pass", "fail", "difference", "unimplemented", "error", "quarantined", "unrecorded")


def cmd_score(args):
    store = Store(ROOT, args.version)
    by_probe = load_cases(args.probe)
    quarantine = store.quarantine()
    differences = load_differences()
    session = Session(args.adapter)
    outcomes, notes = {}, {}
    stale = []
    try:
        for probe, cases in by_probe.items():
            expected = store.expected(probe)
            for case in cases:
                if case.key in quarantine:
                    outcomes[case.key] = "quarantined"
                    continue
                if case.id not in expected:
                    outcomes[case.key] = "unrecorded"
                    continue
                result = session.run(case)
                covering = [d for d in differences if d.covers(case.key)]
                if result.status in ("unimplemented", "error"):
                    outcomes[case.key] = result.status
                    if result.status == "error":
                        notes[case.key] = (result.message or "").strip()[:300]
                elif result.digest() == expected[case.id]:
                    outcomes[case.key] = "pass"
                    stale.extend(f"{d.id} covers {case.key}, which passes" for d in covering)
                elif covering:
                    outcomes[case.key] = "difference"
                    notes[case.key] = ", ".join(d.id for d in covering)
                else:
                    outcomes[case.key] = "fail"
    finally:
        session.close()

    rows = []
    for probe, cases in by_probe.items():
        counts = {o: 0 for o in OUTCOMES}
        for case in cases:
            counts[outcomes[case.key]] += 1
        rows.append((probe, len(cases), counts))
    total = {o: sum(r[2][o] for r in rows) for o in OUTCOMES}

    header = f"| Probe | Cases | {' | '.join(o.capitalize() for o in OUTCOMES)} | Score |"
    print(f"Scoreboard: {session.adapter.name} against vanilla {args.version}\n")
    print(header)
    print("|" + "---|" * (len(OUTCOMES) + 3))
    for probe, n, counts in rows + [("**All**", sum(r[1] for r in rows), total)]:
        scored = n - counts["difference"] - counts["quarantined"] - counts["unrecorded"]
        score = f"{100 * counts['pass'] / scored:.1f}%" if scored else "-"
        print(f"| {probe} | {n} | {' | '.join(str(counts[o]) for o in OUTCOMES)} | {score} |")

    fails = [k for k, o in outcomes.items() if o in ("fail", "error")]
    if fails:
        print(f"\nFirst failures ({len(fails)} in all):")
        for key in fails[:20]:
            print(f"  {key}: {outcomes[key]}{': ' + notes[key].splitlines()[0] if notes.get(key) else ''}")
    for line in stale:
        print(f"note: {line}")

    OUT.mkdir(parents=True, exist_ok=True)
    report = OUT / f"scoreboard-{Path(args.adapter).stem}.json"
    report.write_text(json.dumps({
        "adapter": session.about,
        "game_version": args.version,
        "totals": total,
        "probes": {p: c for p, _, c in rows},
        "cases": outcomes,
        "notes": notes,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"\nFull report: {report}")


def _hexdump(data, start, width=16):
    chunk = data[start:start + width]
    return f"{start:08x}  {chunk.hex(' ')}"


def cmd_diff(args):
    store = Store(ROOT, args.version)
    by_probe = load_cases([args.probe])
    case = next((c for c in by_probe[args.probe] if c.id == args.case), None)
    if case is None:
        die(f"no case `{args.case}` in cases/{args.probe}/")
    golden = store.golden(args.probe, args.case)
    if golden is None:
        die(f"no golden for {case.key}; run `record` first")
    session = Session(args.adapter)
    try:
        result = session.run(case)
    finally:
        session.close()

    print(f"case:     {case.key} ({case.source.relative_to(ROOT)})")
    print(f"vanilla:  {golden['status']} {golden['hash']}")
    print(f"{session.adapter.name + ':':<9} {result.status} {result.digest() if result.status == 'ok' else ''}")
    if result.message:
        print(result.message.rstrip())
    if result.status != "ok":
        return
    if result.output != golden["output"]:
        print("\noutput differs:")
        print(f"  vanilla: {canonical_json(golden['output'])}")
        print(f"  {session.adapter.name}: {canonical_json(result.output)}")
    if len(result.blobs) != len(golden["blobs"]):
        print(f"\nblob count differs: vanilla {len(golden['blobs'])}, {session.adapter.name} {len(result.blobs)}")
    for i, (want, got) in enumerate(zip(golden["blobs"], result.blobs)):
        if want == got:
            continue
        at = next((j for j in range(min(len(want), len(got))) if want[j] != got[j]), min(len(want), len(got)))
        print(f"\nblob {i} differs at byte {at} (vanilla {len(want)} bytes, {session.adapter.name} {len(got)}):")
        row = at - at % 16
        print(f"  vanilla: {_hexdump(want, row)}")
        print(f"  {session.adapter.name}: {_hexdump(got, row)}")


def main():
    parser = argparse.ArgumentParser(prog="rig", description="The oracle rig's runner.")
    parser.add_argument("--version", default="26.3", help="game version (default 26.3)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="cases per probe, and how many are recorded")
    p.add_argument("--probe", action="append")
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("record", help="run vanilla, write goldens and expected hashes")
    p.add_argument("--probe", action="append")
    p.set_defaults(fn=cmd_record)

    p = sub.add_parser("check", help="self-check: vanilla against its own expected hashes")
    p.add_argument("--probe", action="append")
    p.add_argument("--variants", default="default", help=f"`all` or a comma list of: {', '.join(VARIANTS)}")
    p.add_argument("--quarantine", action="store_true", help="quarantine the cases that aren't repeatable")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("score", help="run an adapter against the expected hashes")
    p.add_argument("--adapter", default="calcite", help="calcite, vanilla, or a path to an adapter.json")
    p.add_argument("--probe", action="append")
    p.set_defaults(fn=cmd_score)

    p = sub.add_parser("diff", help="compare one case's result with vanilla's golden")
    p.add_argument("probe")
    p.add_argument("case")
    p.add_argument("--adapter", default="calcite")
    p.set_defaults(fn=cmd_diff)

    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
