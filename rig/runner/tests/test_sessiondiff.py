"""Tests for the protocol suites' comparison, sessiondiff.py, on sessions written by hand as
SessionDump writes them. Standard library only. The rest of the runner is Calx and its tests are
test_runner.calx (CAL-253).

    py -I -m unittest discover -s rig/runner/tests -v
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNNER))

import sessiondiff  # noqa: E402


class Sessions(unittest.TestCase):
    """The protocol suites' comparison, on sessions written by hand as SessionDump writes them."""

    @staticmethod
    def packet(state, kind, value, sha="00"):
        return {"state": state, "size": 1, "sha256": sha, "kind": kind, "value": value}

    def compare(self, vanilla, calcite, differences_md=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for side, lines in (("vanilla", vanilla), ("calcite", calcite)):
                folder = root / "c" / side
                folder.mkdir(parents=True)
                (folder / "join.jsonl").write_text("".join(json.dumps(r) + "\n" for r in lines), encoding="utf-8")
            (root / "differences").mkdir()
            if differences_md:
                (root / "differences" / "x.md").write_text(differences_md, encoding="utf-8")
            printed = []
            report = sessiondiff.run(root, ["c"], ["join"], root / "differences", out=printed.append, complete=True)
            return report, printed

    def test_progress_ordered_by_the_clock(self):
        # After a reload, advancements obtained within a second may swap places; others may not.
        def progress(**firsts):
            return {k: {"criteria": {"c": f"2026-11-10 09:14:{s:02d} +0000"}, "done": True} for k, s in firsts.items()}
        vanilla = sessiondiff.first_obtained(progress(a=48, b=48, c=50))
        calcite = sessiondiff.first_obtained(progress(a=11, b=10, c=13))
        self.assertTrue(sessiondiff.ordered_by_the_clock(["a", "b", "c"], ["b", "a", "c"], vanilla, calcite))
        self.assertFalse(sessiondiff.ordered_by_the_clock(["a", "b", "c"], ["c", "a", "b"], vanilla, calcite))
        self.assertTrue(sessiondiff.ordered_by_the_clock(["a", "b", "c"], ["a", "b", "c"], vanilla, calcite))

    def test_same_sessions_pass(self):
        session = [
            {"mark": "step configuration"},
            self.packet("configuration", "custom_payload", {"brand": "vanilla"}),
            {"mark": "step join"},
            self.packet("play", "set_time", {"gameTime": 5}, "aa"),
            self.packet("play", "login", {"playerId": 1}),
        ]
        later = [dict(r) for r in session]
        later[3] = self.packet("play", "set_time", {"gameTime": 9}, "bb")
        report, _ = self.compare(session, later)
        self.assertTrue(report.passed)
        self.assertFalse(report.findings)

    def test_keep_alives_a_step_apart(self):
        # A keep-alive goes by the wall clock, so one a step before or after the other server's
        # is the same; two steps apart, it isn't.
        alive = self.packet("play", "keep_alive", {"id": 1})
        vanilla = [{"mark": "step join"}, alive, {"mark": "step a"}, {"mark": "step b"}, alive, {"mark": "step c"}, {"mark": "step d"}]
        calcite = [{"mark": "step join"}, {"mark": "step a"}, alive, {"mark": "step b"}, {"mark": "step c"}, {"mark": "step d"}, alive]
        report, _ = self.compare(vanilla, calcite)
        self.assertEqual(sorted((f.key, f.what) for f in report.findings), [
            ("session:join/b/keep_alive", "only vanilla sends it"), ("session:join/d/keep_alive", "only Calcite sends it")])

    def test_sky_under_the_world(self):
        # A chunk whose sky layer under the world is 2048 bytes of 0 matches one whose layer
        # there is empty, as vanilla's light makes it either way from run to run (CAL-122); a
        # layer there that isn't all 0 still differs.
        def chunk(x, sky, empty, updates):
            light = {"@": "ClientboundLightUpdatePacketData", "skyYMask": sky, "emptySkyYMask": empty, "skyUpdates": updates}
            return self.packet("play", "level_chunk_with_light", {"x": x, "z": 0, "lightData": light}, f"c{x}")

        zero, other = sessiondiff.ZERO_LAYER, "2048 bytes, sha256 1111111111111111"
        vanilla = [
            {"mark": "step join"},
            chunk(0, "{0, 1}", "{}", [zero, other]),
            chunk(1, "{1}", "{0}", [other]),
            chunk(2, "{0, 1}", "{}", [other, other]),
            self.packet("play", "chunk_batch_finished", {"batchSize": 3}),
        ]
        calcite = [
            {"mark": "step join"},
            chunk(0, "{1}", "{0}", [other]),
            chunk(1, "{0, 1}", "{}", [zero, other]),
            chunk(2, "{1}", "{0}", [other]),
            self.packet("play", "chunk_batch_finished", {"batchSize": 3}),
        ]
        report, _ = self.compare(vanilla, calcite)
        self.assertEqual([(f.key, f.what) for f in report.findings], [("session:join/join/level_chunk_with_light", "chunk (2, 0) differs")])

    def test_entities(self):
        # An item's packets are lined up by its ID across the steps (CAL-148): its moves may fall
        # in another step, its data among its moves elsewhere, and one side may send it a few
        # more moves before it goes; but a move that differs, or data only one side sends, is
        # found. The bot's own data stays in its step.
        def motion(x):
            return self.packet("play", "set_entity_motion", {"id": 2, "movement": {"x": x}}, f"m{x}")

        add = self.packet("play", "add_entity", {"id": 2, "uuid": "u"}, "a")
        data = self.packet("play", "set_entity_data", {"id": 2, "packedItems": [1]}, "d")
        mine = self.packet("play", "set_entity_data", {"id": 1, "packedItems": [0]}, "e")
        gone = self.packet("play", "remove_entities", {"entityIds": [2]}, "r")
        login = self.packet("play", "login", {"playerId": 1})
        vanilla = [{"mark": "step join"}, login, mine, add, motion(1), data, motion(2), {"mark": "step two"},
                   motion(3), gone]
        calcite = [{"mark": "step join"}, login, mine, add, motion(1), motion(2), {"mark": "step two"}, data,
                   motion(3), motion(4), motion(5), gone]
        report, _ = self.compare(vanilla, calcite)
        self.assertFalse(report.findings)
        wrong = [dict(r) for r in calcite]
        wrong[5] = motion(9)
        report, _ = self.compare(vanilla, wrong)
        self.assertEqual([f.key for f in report.findings], ["session:join/<entity>/set_entity_motion"])
        twice = calcite[:8] + [data] + calcite[8:]
        report, _ = self.compare(vanilla, twice)
        self.assertEqual([f.key for f in report.findings], ["session:join/<entity>/set_entity_data"])

    def test_differences_and_masks(self):
        vanilla = [
            {"mark": "step login"},
            self.packet("login", "login_finished", {"sessionId": "a", "profile": "Bot"}, "11"),
            {"mark": "step configuration"},
            self.packet("configuration", "custom_payload", {"brand": "vanilla"}),
            {"mark": "step join"},
            self.packet("play", "level_chunk_with_light", {"x": 0, "z": 0, "data": 1}, "c1"),
            self.packet("play", "level_chunk_with_light", {"x": 1, "z": 0, "data": 1}, "c2"),
            self.packet("play", "chunk_batch_finished", {"batchSize": 2}),
            self.packet("play", "commands", {"entries": 3}),
            self.packet("play", "player_info_update", {"entries": [{"profileId": "p", "latency": 0}]}, "l0"),
        ]
        calcite = [
            {"mark": "step login"},
            self.packet("login", "login_finished", {"sessionId": "b", "profile": "Bot"}, "22"),
            {"mark": "step configuration"},
            self.packet("configuration", "custom_payload", {"brand": "calcite"}),
            {"mark": "step join"},
            self.packet("play", "level_chunk_with_light", {"x": 1, "z": 0, "data": 1}, "c9"),
            self.packet("play", "level_chunk_with_light", {"x": 0, "z": 0, "data": 1}, "c8"),
            self.packet("play", "chunk_batch_finished", {"batchSize": 2}),
            self.packet("play", "player_info_update", {"entries": [{"profileId": "p", "latency": 1}]}, "l1"),
        ]
        report, _ = self.compare(vanilla, calcite)
        keys = sorted((f.key, f.what) for f in report.findings)
        # The session ID and a player's latency are drawn, and chunks are a set whose bytes vanilla
        # doesn't fix.
        self.assertEqual(keys, [("session:join/configuration/custom_payload", "differs"), ("session:join/join/commands", "only vanilla sends it")])
        self.assertFalse(report.passed)
        brand = "---\ntitle: Brand\nkind: identity\ncases:\n  - session:*/configuration/custom_payload\n---\n"
        report, printed = self.compare(vanilla, calcite, brand)
        self.assertTrue(report.passed)
        self.assertIn("  [c] session:join/configuration/custom_payload: differs (deliberate: x)", printed)

    def test_stale_difference_is_noted(self):
        session = [{"mark": "step configuration"}, self.packet("configuration", "custom_payload", {"brand": "x"})]
        stale = "---\ntitle: Brand\nkind: identity\ncases:\n  - session:*/configuration/custom_payload\n---\n"
        report, printed = self.compare(session, session, stale)
        self.assertTrue(report.passed)
        self.assertIn("note: x covers no session that differs, so it may be out of date", printed)

    def test_chunks_that_differ_are_grouped(self):
        def chunk(x, z, light, entities=()):
            value = {"x": x, "z": z, "chunkData": {"buffer": "b", "blockEntitiesData": list(entities)},
                     "lightData": {"skyUpdates": [light]}}
            return self.packet("play", "level_chunk_with_light", value)
        done = self.packet("play", "chunk_batch_finished", {"batchSize": 5})
        vanilla = [{"mark": "step join"}, chunk(0, 0, "a"), chunk(1, 0, "a", ["chest"]), chunk(2, 0, "a"), chunk(3, 0, "b"), chunk(4, 0, "a"), done]
        calcite = [{"mark": "step join"}, chunk(0, 0, "a"), chunk(1, 0, "a"), chunk(2, 0, "c"), chunk(3, 0, "c"), chunk(4, 0, "a"), done]
        report, printed = self.compare(vanilla, calcite)
        self.assertEqual([f.what for f in report.findings], ["chunk (1, 0) differs", "2 more chunks differ"])
        self.assertEqual(report.findings[1].detail, [".lightData.skyUpdates: (2,0) (3,0)"])
        # The two chunks that are the same still count.
        self.assertEqual(report.counts["play"]["match"], 2)

    def test_block_changes_in_any_order(self):
        def block(x, state):
            return self.packet("play", "block_update", {"pos": {"@": "BlockPos", "x": x, "y": 0, "z": 0}, "blockState": state})

        def section(x, changes):
            return self.packet("play", "section_blocks_update", {"sectionPos": {"@": "SectionPos", "x": x, "y": 0, "z": 0}, "positions": changes})
        light = self.packet("play", "light_update", {"x": 5, "z": 5, "lightData": "l"})
        vanilla = [{"mark": "step join"}, block(1, "stone"), section(2, [1, 2]), self.packet("play", "commands", {"entries": 3}),
                   block(3, "dirt"), block(4, "snow"), light]
        calcite = [{"mark": "step join"}, block(3, "dirt"), section(2, [1, 2]), self.packet("play", "commands", {"entries": 3}),
                   block(1, "stone"), block(4, "air"), block(6, "air")]
        report, _ = self.compare(vanilla, calcite)
        found = sorted((f.key, f.what, tuple(f.detail)) for f in report.findings)
        # Those in another order match; the one at x 4 differs; the light update and the block at 6
        # are each side's own.
        self.assertEqual(found, [
            ("session:join/join/block_update", "differs", (".blockState: \"snow\" vs \"air\"",)),
            ("session:join/join/block_update", "only Calcite sends it", ('at {"x": 6, "y": 0, "z": 0}',)),
            ("session:join/join/light_update", "only vanilla sends it", ('at {"x": 5, "z": 5}',)),
        ])
        self.assertEqual(report.counts["play"], {"match": 4, "differ": 3})

    def test_block_events_line_up_by_place(self):
        def event(x, b0):
            return self.packet("play", "block_event", {"pos": {"@": "BlockPos", "x": x, "y": 0, "z": 0}, "b0": b0, "b1": 5}, f"e{x}{b0}")

        def sound(x, seed):
            return self.packet("play", "sound", {"sound": "#minecraft:block.piston.extend", "x": x * 8 + 4, "y": 4, "z": 4, "pitch": 0.7, "seed": seed}, f"s{x}{seed}")
        # Calcite has lost the first piston's first pair: lined up by kind alone, every pair after
        # would be the other piston's. The seeds are drawn, so they don't count.
        vanilla = [{"mark": "step join"}, sound(1, 7), event(1, 0), sound(2, 8), event(2, 0), sound(1, 9), event(1, 1), sound(2, 3), event(2, 1)]
        calcite = [{"mark": "step join"}, sound(2, 1), event(2, 0), sound(1, 2), event(1, 1), sound(2, 4), event(2, 1)]
        report, _ = self.compare(vanilla, calcite)
        found = sorted((f.key, f.what) for f in report.findings)
        self.assertEqual(found, [("session:join/join/block_event", "only vanilla sends it"), ("session:join/join/sound", "only vanilla sends it")])
        self.assertEqual(report.counts["play"]["match"], 6)

    def test_scenarios_by_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for config, scenario in (("a", "join"), ("b", "status")):
                for side in ("vanilla", "calcite"):
                    folder = root / config / side
                    folder.mkdir(parents=True)
                    (folder / f"{scenario}.jsonl").write_text(json.dumps(self.packet("status", "status_response", {"v": 1})) + "\n", encoding="utf-8")
            (root / "differences").mkdir()
            report = sessiondiff.run(root, ["a", "b"], {"a": ["join"], "b": ["status"]}, root / "differences", out=lambda _: None)
            self.assertTrue(report.passed)
            self.assertEqual(report.counts["status"]["match"], 1)


if __name__ == "__main__":
    unittest.main()
