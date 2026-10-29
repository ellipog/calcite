"""Compares two servers' sessions packet by packet (P4.8): what the protocol bot was sent by
vanilla and by Calcite, as the vanilla adapter's SessionDump read it with vanilla's codecs.

A session is cut into the bot's steps, and each step's packets are lined up by kind, as `diff`
lines up text. Two lined-up packets match when their values are the same tree and, unless
vanilla doesn't fix the order (`UNORDERED`), the same bytes. Three things are taken out of the
line first, since when they come depends on timing rather than on the server:

- **Clock packets.** `set_time` and keep-alives come every so many ticks or milliseconds. Each
  side's are compared by their values with the times taken out, once a step.
- **Chunks.** Vanilla sends the chunks that are ready, nearest first, and they get ready on
  worker threads, so how many go in a batch and in what order changes from run to run. A step's
  chunks are compared as a set, by position, where its first batch began.
- **What isn't a packet.** The bot's mark that the server closed the connection is lined up
  like a packet, as `<closed>`.

Fields vanilla draws afresh each run (`DRAWN`) are left out of both sides' values.

Each packet that differs is keyed `session:SCENARIO/STEP/KIND`, which a file in
rig/differences/ can cover. The steps of login and configuration, and the status scenario, are
the suites G4.2 and P4.2 need, and fail on any difference no file covers.
"""

import difflib
import json
from dataclasses import dataclass, field

import differences as registry

CLOCK = {"play/set_time", "play/keep_alive", "configuration/keep_alive"}
# The fields of a clock packet that hold the time.
CLOCK_TIMES = {"gameTime", "totalTicks", "id"}
CHUNKS = {"play/chunk_batch_start", "play/chunk_batch_finished", "play/level_chunk_with_light"}
# Packets whose bytes vanilla itself doesn't fix: their values must match, but not their bytes.
# PacketCheck lists the first three. A chunk's heightmaps are a HashMap, from `Collectors.toMap`,
# keyed by an enum, which hashes by identity, so vanilla writes them in another order each run;
# the client reads them into an EnumMap.
UNORDERED = {"configuration/update_tags", "play/update_tags", "play/set_time", "play/level_chunk_with_light"}
# Fields vanilla draws afresh each run, which can't match: the session ID the server draws as it
# starts, which every login gets, and the time on a chat message without a signature, which is
# the server's clock as it reads the message.
DRAWN = {"login/login_finished": {"sessionId"}, "play/player_chat": {"timeStamp"}}
SUITES = {"status": "status", "login": "login", "configuration": "configuration"}


@dataclass
class Entry:
    kind: str
    value: object
    sha: str = ""
    error: str = ""

    def text(self):
        return json.dumps(self.value, sort_keys=True)


@dataclass
class Step:
    name: str
    entries: list = field(default_factory=list)
    clock: dict = field(default_factory=dict)
    chunks: dict = field(default_factory=dict)
    batches: int = 0
    batched: int = 0


def load(path):
    """A session's steps, from SessionDump's .jsonl."""
    steps = [Step("start")]
    for line in path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        step = steps[-1]
        if "mark" in r:
            mark = r["mark"]
            if mark.startswith("step "):
                steps.append(Step(mark[5:]))
            else:
                step.entries.append(Entry(f"<{mark}>", None))
            continue
        kind = f"{r['state']}/{r['kind']}"
        value = r.get("value")
        if kind in DRAWN:
            value = without(value, DRAWN[kind])
        if kind in CLOCK:
            step.clock.setdefault(kind, without_times(value))
            continue
        if kind in CHUNKS:
            if not step.chunks and not step.batches:
                step.entries.append(Entry("<chunks>", None))
            if kind == "play/chunk_batch_start":
                step.batches += 1
            elif kind == "play/chunk_batch_finished":
                step.batched += value.get("batchSize", 0)
            else:
                step.chunks[(value.get("x"), value.get("z"))] = Entry(kind, without(value, {"x", "z"}), r["sha256"], r.get("error", ""))
            continue
        step.entries.append(Entry(kind, value, r["sha256"], r.get("error", "")))
    return [s for s in steps if s.name != "start" or s.entries]


def without(value, names):
    if isinstance(value, dict):
        return {k: without(v, names) for k, v in value.items() if k not in names}
    if isinstance(value, list):
        return [without(v, names) for v in value]
    return value


def without_times(value):
    return without(value, CLOCK_TIMES)


def paths(a, b, at="", out=None, limit=12):
    """Where two trees differ, as paths, up to `limit` of them."""
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in list(a) + [k for k in b if k not in a]:
            if k == "@":
                if a.get("@") != b.get("@"):
                    out.append(f"{at or '.'}: {a.get('@')} vs {b.get('@')}")
                continue
            if k not in b:
                out.append(f"{at}.{k}: only vanilla has it")
            elif k not in a:
                out.append(f"{at}.{k}: only Calcite has it")
            else:
                paths(a[k], b[k], f"{at}.{k}", out, limit)
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{at}: {len(a)} items vs {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            paths(x, y, f"{at}[{i}]", out, limit)
            if len(out) >= limit:
                break
        return out
    if a != b:
        out.append(f"{at or '.'}: {short(a)} vs {short(b)}")
    return out


def short(v, n=120):
    s = json.dumps(v)
    return s if len(s) <= n else s[:n] + "..."


@dataclass
class Finding:
    key: str
    suite: str
    what: str
    detail: list = field(default_factory=list)
    covered_by: str = ""
    config: str = ""


def suite_of(scenario, step):
    if scenario == "status":
        return "status"
    return SUITES.get(step, "play")


def compare_entries(a, b):
    """What's wrong with Calcite's packet `b` where vanilla sent `a`, or None."""
    if a.error or b.error:
        if a.error and b.error:
            return None if a.error == b.error else [f"vanilla's: {a.error}", f"Calcite's: {b.error}"]
        return [f"Calcite's: {b.error}"] if b.error else [f"vanilla's: {a.error}"]
    if a.text() != b.text():
        return paths(a.value, b.value)
    if a.sha != b.sha and a.kind not in UNORDERED and a.kind not in DRAWN:
        return ["the same values in other bytes, such as a map in another order"]
    return None


def compare_step(scenario, va, ca, findings, counts):
    suite = suite_of(scenario, va.name)
    tally = counts.setdefault(suite, {"match": 0, "differ": 0})

    def found(kind, what, detail=()):
        findings.append(Finding(f"session:{scenario}/{va.name}/{kind.split('/', 1)[-1]}", suite, what, list(detail)))
        tally["differ"] += 1

    a, b = va.entries, ca.entries
    m = difflib.SequenceMatcher(a=[e.kind for e in a], b=[e.kind for e in b], autojunk=False)
    for op, i1, i2, j1, j2 in m.get_opcodes():
        if op == "equal":
            for x, y in zip(a[i1:i2], b[j1:j2]):
                if x.kind == "<chunks>":
                    compare_chunks(va, ca, found, tally)
                    continue
                problem = compare_entries(x, y)
                if problem:
                    found(x.kind, "differs", problem)
                else:
                    tally["match"] += 1
            continue
        for x in a[i1:i2]:
            found(x.kind, "only vanilla sends it" if not x.kind.startswith("<") else f"only vanilla's session has {x.kind}")
        for y in b[j1:j2]:
            found(y.kind, "only Calcite sends it" if not y.kind.startswith("<") else f"only Calcite's session has {y.kind}")
    for kind in sorted(set(va.clock) | set(ca.clock)):
        if kind not in ca.clock:
            found(kind, "only vanilla sends it")
        elif kind not in va.clock:
            found(kind, "only Calcite sends it")
        elif json.dumps(va.clock[kind], sort_keys=True) != json.dumps(ca.clock[kind], sort_keys=True):
            found(kind, "differs, with the times taken out", paths(va.clock[kind], ca.clock[kind]))
        else:
            tally["match"] += 1


def compare_chunks(va, ca, found, tally):
    if va.batched != len(va.chunks) or ca.batched != len(ca.chunks):
        found("play/chunk_batch_finished", "a batch's size isn't the chunks it held",
              [f"vanilla {va.batched} for {len(va.chunks)}, Calcite {ca.batched} for {len(ca.chunks)}"])
    only_v = sorted(set(va.chunks) - set(ca.chunks))
    only_c = sorted(set(ca.chunks) - set(va.chunks))
    if only_v or only_c:
        found("play/level_chunk_with_light", "other chunks", [f"only vanilla's: {only_v[:12]}", f"only Calcite's: {only_c[:12]}"])
    bad = 0
    for pos in sorted(set(va.chunks) & set(ca.chunks)):
        problem = compare_entries(va.chunks[pos], ca.chunks[pos])
        if problem:
            bad += 1
            if bad == 1:
                found("play/level_chunk_with_light", f"chunk {pos} differs", problem)
    if bad > 1:
        found("play/level_chunk_with_light", f"{bad - 1} more chunks differ")
    if not bad and not only_v and not only_c:
        tally["match"] += len(va.chunks)


@dataclass
class Report:
    findings: list
    counts: dict
    passed: bool


def compare(vanilla_steps, calcite_steps, scenario, findings, counts):
    by_name = {s.name: s for s in calcite_steps}
    for va in vanilla_steps:
        ca = by_name.get(va.name)
        if ca is None:
            findings.append(Finding(f"session:{scenario}/{va.name}/<step>", suite_of(scenario, va.name), "Calcite's session never got to this step"))
            counts.setdefault(suite_of(scenario, va.name), {"match": 0, "differ": 0})["differ"] += 1
            continue
        compare_step(scenario, va, ca, findings, counts)
    names = {s.name for s in vanilla_steps}
    for ca in calcite_steps:
        if ca.name not in names:
            findings.append(Finding(f"session:{scenario}/{ca.name}/<step>", suite_of(scenario, ca.name), "only Calcite's session gets to this step"))
            counts.setdefault(suite_of(scenario, ca.name), {"match": 0, "differ": 0})["differ"] += 1


def run(sessions, configs, scenarios, differences_dir, show=3, out=print, complete=False):
    """Compares the sessions of each configuration and scenario, and prints the suites. With
    `complete`, every scenario ran, so a difference with session cases that covered nothing is
    noted, as the scoreboard notes one whose cases pass."""
    known = registry.load(differences_dir)
    findings, counts = [], {}
    for config in configs:
        for scenario in scenarios:
            v = load(sessions / config / "vanilla" / f"{scenario}.jsonl")
            c = load(sessions / config / "calcite" / f"{scenario}.jsonl")
            before = len(findings)
            compare(v, c, scenario, findings, counts)
            for f in findings[before:]:
                f.config = config
    for f in findings:
        for d in known:
            if d.covers(f.key):
                f.covered_by = d.id
                break
    passed = True
    for suite in ("status", "login", "configuration", "play"):
        if suite not in counts:
            continue
        mine = [f for f in findings if f.suite == suite]
        open_ = [f for f in mine if not f.covered_by]
        gate = suite != "play"
        if gate and open_:
            passed = False
        state = ("PASS" if not open_ else "FAIL") if gate else ("match" if not open_ else "differs")
        out(f"{suite:14} {state:7} {counts[suite]['match']} match, {len(mine) - len(open_)} deliberate, {len(open_)} differ")
        for f in mine:
            note = f" (deliberate: {f.covered_by})" if f.covered_by else ""
            out(f"  [{f.config}] {f.key}: {f.what}{note}")
            for line in (f.detail if show == 0 else f.detail[:show]):
                out(f"      {line}")
    if complete:
        used = {f.covered_by for f in findings}
        for d in known:
            if any(c.startswith("session:") for c in d.cases) and d.id not in used:
                out(f"note: {d.id} covers no session that differs, so it may be out of date")
    out("the login, configuration and status suites " + ("pass" if passed else "fail"))
    return Report(findings, counts, passed)
