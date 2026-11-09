"""Compares two servers' sessions packet by packet (P4.8): what the protocol bot was sent by
vanilla and by Calcite, as the vanilla adapter's SessionDump read it with vanilla's codecs.

A session is cut into the bot's steps, and each step's packets are lined up by kind, as `diff`
lines up text, a block event or a sound by where it is too (`PLACED`), so a run of a piston's
sounds and events, the same kinds over and over, lines up event by event. Two lined-up packets
match when their values are the same tree and, unless
vanilla doesn't fix the order (`UNORDERED`), the same bytes. Four things are taken out of the
line first, since when or in what order they come depends on timing rather than on the server:

- **Clock packets.** `set_time` and keep-alives come every so many ticks or milliseconds. Each
  side's are compared by their values with the times taken out, once a step.
- **Chunks.** Vanilla sends the chunks that are ready, nearest first, and they get ready on
  worker threads, so how many go in a batch and in what order changes from run to run. A step's
  chunks are compared as a set, by position, where its first batch began.
- **Block changes.** Vanilla broadcasts the chunks whose blocks changed in a tick from a
  `ReferenceOpenHashSet` of their holders, by identity, so in another order between chunks each
  run, and a light update comes as its light thread gets to the change. A step's
  `block_update`, `section_blocks_update` and `light_update` packets are compared as a multiset,
  those left over paired by where they are, to show what differs (D341), with the
  `block_entity_data` each block change brings, which comes as its tick does (D350).
- **What isn't a packet.** The bot's mark that the server closed the connection is lined up
  like a packet, as `<closed>`.
- **Entities.** What an entity other than the bot is sent comes on its own clock, from the tick
  it came in, as its tracker runs every so many ticks, so a step that ends a second after the bot
  last heard anything else ends between two of them where the clock has it. Each entity's
  packets, `ENTITY`, are lined up across the session instead, by its ID (CAL-148): what it is,
  `STATE`, its coming, its data, its going and its pickup, in the order it was sent them; and
  apart from those, its moves, in theirs. Two entities that came in different ticks, which is as
  the bot's packets fell between the server's ticks, meet, merge or are picked up a tick or two
  apart on each server, so where an entity's state comes among its moves, and how many moves it's
  sent before it goes, isn't the server's to fix: one side's moves may go on past the other's by
  as many as `MORE_MOVES`.

Fields vanilla draws afresh each run (`DRAWN`) are left out of both sides' values. And the sky's
light under the world is read as vanilla's light leaves it either way (CAL-122): the section below
the world's bottom is all 0, but whether its layer is kept as 2048 bytes of 0, `repeatFirstLayer`
of the bottom section's, or empty, `new DataLayer()`, is down to whether its chunk's sections were
set up before a neighbour's set up its own, which goes by which of the chunks being read vanilla's
workers finish first, and changes from run to run. A chunk sends such a layer as one of 0 in
`skyYMask`, so each side's is read as empty, in `emptySkyYMask`, as the other would have it.

Each packet that differs is keyed `session:SCENARIO/STEP/KIND`, which a file in
rig/differences/ can cover. The steps of login and configuration, and the status scenario, are
the suites G4.2 and P4.2 need, and fail on any difference no file covers.
"""

import difflib
import json
import re
from dataclasses import dataclass, field

import differences as registry

CLOCK = {"play/set_time", "play/keep_alive", "configuration/keep_alive"}
# What's lined up by entity rather than by step (CAL-148), and the fields each names the entity in.
ENTITY = {"play/add_entity", "play/set_entity_data", "play/set_entity_motion", "play/move_entity_pos",
          "play/move_entity_pos_rot", "play/move_entity_rot", "play/entity_position_sync",
          "play/remove_entities", "play/take_item_entity"}
ENTITY_IDS = ("entityId", "id", "itemId")
STATE = {"play/add_entity", "play/set_entity_data", "play/remove_entities", "play/take_item_entity"}
# How many more moves one side's entity may be sent before it goes, or the bot leaves: three of
# an item's tracker's runs, each its motion and where it is.
MORE_MOVES = 6
# The fields of a clock packet that hold the time.
CLOCK_TIMES = {"gameTime", "totalTicks", "id"}
CHUNKS = {"play/chunk_batch_start", "play/chunk_batch_finished", "play/level_chunk_with_light"}
CHANGES = {"play/block_update", "play/section_blocks_update", "play/light_update", "play/block_entity_data"}
# Packets whose bytes vanilla itself doesn't fix: their values must match, but not their bytes.
# PacketCheck lists the first three. A chunk's heightmaps are a HashMap, from `Collectors.toMap`,
# keyed by an enum, which hashes by identity, so vanilla writes them in another order each run;
# the client reads them into an EnumMap.
# An entity's attributes come from `AttributeMap`'s set of those that changed, or of them all,
# which go by the instances' identity hashes, so vanilla sends them in another order each run;
# they're compared by their attributes' names (D375).
# The recipes' property sets are a HashMap keyed by `ResourceKey`s, which hash by identity, each
# set `Set.copyOf` of item holders, which do too, so vanilla writes both in another order each run;
# the client reads them into a map and sets, and SessionDump sorts them. The stonecutter's recipes
# are a list, whose order the values keep (D385).
# The login's levels are `levelKeys()`, a LinkedHashMap's keys put in as `createLevels` goes
# through the dimensions registry's `entrySet`, a HashMap's by `ResourceKey`, which hashes by
# identity, so after the overworld the Nether and the End come in either order (CAL-147).
UNORDERED = {"configuration/update_tags", "play/update_tags", "play/set_time", "play/level_chunk_with_light", "play/update_attributes", "play/update_recipes", "play/login"}
SORTED = {"play/update_attributes": ("attributes", "attribute")}
# A living entity's effects' particles, `DATA_EFFECT_PARTICLES`, come from its `activeEffects`, a
# HashMap keyed by the effects' holders, which hash by identity, so vanilla sends two or more in
# another order each run; a list of them is compared sorted, and its bytes aren't (D513).
PARTICLE_TYPE = "#minecraft:particle_type/"
# A player's effects are their `activeEffects`, the same map, so vanilla tells them a run of them,
# as they join or as they're ticked, in another order each run; a run of `update_mob_effect` or
# `remove_mob_effect` packets is compared sorted (D514).
RUNS = {"play/update_mob_effect", "play/remove_mob_effect"}
# Fields vanilla draws afresh each run, which can't match: the session ID the server draws as it
# starts, which every login gets; the time on a chat message without a signature, which is the
# server's clock as it reads the message; and a sound's seed, which `Level.playSound` draws from
# `threadSafeRandom`, seeded afresh as the server starts (CAL-125).
DRAWN = {"login/login_finished": {"sessionId"}, "play/player_chat": {"timeStamp"}, "play/sound": {"seed"}}
SUITES = {"status": "status", "login": "login", "configuration": "configuration"}
# Packets lined up by where they are as well as by kind: a block's event and a sound, which
# pistons and clocks send over and over (CAL-125).
PLACED = {"play/block_event", "play/sound"}
# Packets with a chunk's light, whose sky layer under the world is read as empty where it's all 0
# (CAL-122), and how SessionDump writes a layer that's all 0.
LIT = {"play/level_chunk_with_light", "play/light_update"}
ZERO_LAYER = "2048 bytes, sha256 e5a00aa9991ac8a5"


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
    # Each entity's packets in the step, by its ID, but the bot's, in the order they came.
    entities: dict = field(default_factory=dict)
    clock: dict = field(default_factory=dict)
    chunks: dict = field(default_factory=dict)
    batches: int = 0
    batched: int = 0
    # The chunk packets sent, each, which a respawn sends again for the same places (D428).
    sent: int = 0
    changes: list = field(default_factory=list)


def entity_of(kind, value):
    """The entity a packet of `ENTITY` is for, or None."""
    if not isinstance(value, dict):
        return None
    if kind == "play/remove_entities":
        ids = value.get("entityIds")
        return ids[0] if isinstance(ids, list) and len(ids) == 1 else None
    for name in ENTITY_IDS:
        if isinstance(value.get(name), int):
            return value[name]
    return None


def load(path):
    """A session's steps, from SessionDump's .jsonl."""
    steps = [Step("start")]
    me = None
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
        if kind in SORTED and isinstance(value, dict):
            field_name, key = SORTED[kind]
            value = dict(value, **{field_name: sorted(value.get(field_name, []), key=lambda e: str(e.get(key)))})
        if kind == "play/set_entity_data":
            value, moved = particles_sorted(value)
            if moved:
                r["sha256"] = ""
        if kind in LIT:
            value = under_world_empty(value)
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
                step.sent += 1
                step.chunks[(value.get("x"), value.get("z"))] = Entry(kind, without(value, {"x", "z"}), r["sha256"], r.get("error", ""))
            continue
        if kind in CHANGES:
            step.changes.append(Entry(kind, value, r["sha256"], r.get("error", "")))
            continue
        if kind == "play/login" and isinstance(value, dict):
            me = value.get("playerId")
        if kind in ENTITY:
            who = entity_of(kind, value)
            if who is not None and who != me:
                step.entities.setdefault(who, []).append(Entry(kind, value, r["sha256"], r.get("error", "")))
                continue
        step.entries.append(Entry(kind, value, r["sha256"], r.get("error", "")))
    for s in steps:
        s.entries = runs_sorted(s.entries)
    return [s for s in steps if s.name != "start" or s.entries or s.changes or s.entities]


def runs_sorted(entries):
    """`entries` with each run of two or more of a kind in RUNS sorted."""
    out = []
    i = 0
    while i < len(entries):
        j = i
        while entries[i].kind in RUNS and j < len(entries) and entries[j].kind == entries[i].kind:
            j += 1
        if j - i > 1:
            out.extend(sorted(entries[i:j], key=lambda e: e.text()))
            i = j
        else:
            out.append(entries[i])
            i += 1
    return out


def particles_sorted(value):
    """A `set_entity_data`'s `value` with each of its lists of two or more particles sorted, and
    whether it had one."""
    if not isinstance(value, dict) or not isinstance(value.get("packedItems"), list):
        return value, False
    items = []
    moved = False
    for item in value["packedItems"]:
        v = item.get("value") if isinstance(item, dict) else None
        if isinstance(v, list) and len(v) > 1 and all(isinstance(p, dict) and str(p.get("type", "")).startswith(PARTICLE_TYPE) for p in v):
            item = dict(item, value=sorted(v, key=lambda p: json.dumps(p, sort_keys=True)))
            moved = True
        items.append(item)
    return dict(value, packedItems=items), moved


def without(value, names):
    if isinstance(value, dict):
        return {k: without(v, names) for k, v in value.items() if k not in names}
    if isinstance(value, list):
        return [without(v, names) for v in value]
    return value


def without_times(value):
    return without(value, CLOCK_TIMES)


def mask(text):
    """The sections a light mask, as SessionDump writes a `BitSet`, `{0, 1, 2}`, holds."""
    inner = text.strip()[1:-1].strip()
    return [int(s) for s in inner.split(",")] if inner else []


def mask_text(bits):
    return "{" + ", ".join(str(b) for b in sorted(bits)) + "}"


def under_world_empty(value):
    """The packet's light with its sky layer under the world, section 0, read as empty where it's
    all 0, as vanilla's light makes it one way or the other from run to run (CAL-122)."""
    if not isinstance(value, dict):
        return value
    light = value.get("lightData")
    if not isinstance(light, dict) or not isinstance(light.get("skyYMask"), str):
        return value
    sky = mask(light["skyYMask"])
    updates = light.get("skyUpdates")
    if not sky or sky[0] != 0 or not isinstance(updates, list) or not updates or updates[0] != ZERO_LAYER:
        return value
    empty = mask(light.get("emptySkyYMask", "{}"))
    light = dict(light, skyYMask=mask_text(sky[1:]), emptySkyYMask=mask_text(set(empty) | {0}), skyUpdates=updates[1:])
    return dict(value, lightData=light)


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
    m = difflib.SequenceMatcher(a=[line_key(e) for e in a], b=[line_key(e) for e in b], autojunk=False)
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
    if va.changes or ca.changes:
        compare_changes(va, ca, found, tally)
    for kind in sorted(set(va.clock) | set(ca.clock)):
        if kind not in ca.clock:
            found(kind, "only vanilla sends it")
        elif kind not in va.clock:
            found(kind, "only Calcite sends it")
        elif json.dumps(va.clock[kind], sort_keys=True) != json.dumps(ca.clock[kind], sort_keys=True):
            found(kind, "differs, with the times taken out", paths(va.clock[kind], ca.clock[kind]))
        else:
            tally["match"] += 1


def line_key(entry):
    """What a packet's lined up by: its kind, and, for one of `PLACED`, where it is."""
    if entry.kind not in PLACED or not isinstance(entry.value, dict):
        return entry.kind
    v = entry.value
    at = v.get("pos") or {k: v.get(k) for k in ("x", "y", "z")}
    return f"{entry.kind} {json.dumps(without(at, {'@'}), sort_keys=True)}"


def where(entry):
    """Where a block change is: a block's position, a section's, or a light update's chunk."""
    v = entry.value if isinstance(entry.value, dict) else {}
    at = v.get("pos") or v.get("sectionPos") or {k: v.get(k) for k in ("x", "z")}
    return entry.kind, json.dumps(without(at, {"@"}), sort_keys=True)


def compare_changes(va, ca, found, tally):
    """A step's block changes as a multiset: each of vanilla's matched with one of Calcite's with
    the same value, then those left paired by where they are, in the order each side sent them,
    and the rest each side's own."""
    left_v = []
    by_value = {}
    for e in ca.changes:
        by_value.setdefault((e.kind, e.text()), []).append(e)
    for x in va.changes:
        same = by_value.get((x.kind, x.text()))
        if not same:
            left_v.append(x)
            continue
        y = same.pop(0)
        problem = compare_entries(x, y)
        if problem:
            found(x.kind, "differs", problem)
        else:
            tally["match"] += 1
    remaining = {id(e) for es in by_value.values() for e in es}
    left_c = [e for e in ca.changes if id(e) in remaining]
    by_place = {}
    for y in left_c:
        by_place.setdefault(where(y), []).append(y)
    only_v = []
    for x in left_v:
        there = by_place.get(where(x))
        if there:
            found(x.kind, "differs", compare_entries(x, there.pop(0)) or ["the same values"])
        else:
            only_v.append(x)
    only_c = [y for ys in by_place.values() for y in ys]
    for side, xs in (("vanilla", only_v), ("Calcite", only_c)):
        by_kind = {}
        for x in xs:
            by_kind.setdefault(x.kind, []).append(x)
        for kind, ys in sorted(by_kind.items()):
            what = f"only {side} sends it" if len(ys) == 1 else f"only {side} sends {len(ys)} of them"
            found(kind, what, [f"at {where(y)[1]}" for y in ys[:3]])
            tally["differ"] += len(ys) - 1


def compare_chunks(va, ca, found, tally):
    if va.batched != va.sent or ca.batched != ca.sent or va.sent != ca.sent:
        found("play/chunk_batch_finished", "a batch's size isn't the chunks it held",
              [f"vanilla {va.batched} for {va.sent}, Calcite {ca.batched} for {ca.sent}"])
    only_v = sorted(set(va.chunks) - set(ca.chunks))
    only_c = sorted(set(ca.chunks) - set(va.chunks))
    if only_v or only_c:
        found("play/level_chunk_with_light", "other chunks", [f"only vanilla's: {only_v[:12]}", f"only Calcite's: {only_c[:12]}"])
    bad = {}
    for pos in sorted(set(va.chunks) & set(ca.chunks)):
        problem = compare_entries(va.chunks[pos], ca.chunks[pos])
        if problem:
            bad[pos] = problem
    if bad:
        first = next(iter(bad))
        found("play/level_chunk_with_light", f"chunk {first} differs", bad[first])
    if len(bad) > 1:
        # The others, by what differs in them, so a few kinds of difference over many chunks
        # read as a few lines.
        kinds = {}
        for pos in list(bad)[1:]:
            kinds.setdefault(fields(bad[pos]), []).append(pos)
        found("play/level_chunk_with_light", f"{len(bad) - 1} more chunks differ",
              [f"{', '.join(k)}: {' '.join(f'({x},{z})' for x, z in ps)}" for k, ps in sorted(kinds.items(), key=lambda kv: -len(kv[1]))])
    tally["match"] += len(set(va.chunks) & set(ca.chunks)) - len(bad)


def fields(problem):
    """The fields a chunk's differences are in, two deep and without indices, as
    `.lightData.skyUpdates`."""
    out = set()
    for line in problem:
        at = line.split(": ", 1)[0] if line.startswith(".") else line
        out.add(".".join(re.sub(r"\[\d+\]", "", at).split(".")[:3]))
    return tuple(sorted(out))


@dataclass
class Report:
    findings: list
    counts: dict
    passed: bool


def streams(steps):
    """Each entity's packets across the session, by its ID, each with the place of its step."""
    out = {}
    for n, s in enumerate(steps):
        for who, es in s.entities.items():
            out.setdefault(who, []).extend((n, e) for e in es)
    return out


def compare_entities(vanilla_steps, calcite_steps, scenario, findings, counts):
    """Each entity's packets, in the order it was sent them, apart from the steps (CAL-148): a
    packet that differs, or one side's going on past the other's before the last steps."""
    tally = counts.setdefault("play", {"match": 0, "differ": 0})
    va, ca = streams(vanilla_steps), streams(calcite_steps)
    names_v = [s.name for s in vanilla_steps]
    names_c = [s.name for s in calcite_steps]

    def found(who, kind, what, detail=()):
        findings.append(Finding(f"session:{scenario}/<entity>/{kind.split('/', 1)[-1]}", "play", f"entity {who}: {what}", list(detail)))
        tally["differ"] += 1

    def line_up(who, a, b, more):
        m = difflib.SequenceMatcher(a=[e.kind for _, e in a], b=[e.kind for _, e in b], autojunk=False)
        ops = m.get_opcodes()
        for k, (op, i1, i2, j1, j2) in enumerate(ops):
            if op == "equal":
                for (_, x), (_, y) in zip(a[i1:i2], b[j1:j2]):
                    problem = compare_entries(x, y)
                    if problem:
                        found(who, x.kind, "differs", problem)
                    else:
                        tally["match"] += 1
                continue
            # One side's moves going on past the other's, a few of them, as it went later.
            if k == len(ops) - 1 and op in ("delete", "insert") and max(i2 - i1, j2 - j1) <= more:
                continue
            for n, x in a[i1:i2]:
                found(who, x.kind, f"only vanilla sends it, in {names_v[n]}")
            for n, y in b[j1:j2]:
                found(who, y.kind, f"only Calcite sends it, in {names_c[n]}")

    for who in sorted(set(va) | set(ca)):
        a, b = va.get(who, []), ca.get(who, [])
        line_up(who, [p for p in a if p[1].kind in STATE], [p for p in b if p[1].kind in STATE], 0)
        line_up(who, [p for p in a if p[1].kind not in STATE], [p for p in b if p[1].kind not in STATE], MORE_MOVES)


def compare(vanilla_steps, calcite_steps, scenario, findings, counts):
    compare_entities(vanilla_steps, calcite_steps, scenario, findings, counts)
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
    """Compares the sessions of each configuration and scenario, and prints the suites.
    `scenarios` is a list for every configuration, or a dict of each one's. With
    `complete`, every scenario ran, so a difference with session cases that covered nothing is
    noted, as the scoreboard notes one whose cases pass."""
    known = registry.load(differences_dir)
    findings, counts = [], {}
    for config in configs:
        for scenario in (scenarios.get(config, ()) if isinstance(scenarios, dict) else scenarios):
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
