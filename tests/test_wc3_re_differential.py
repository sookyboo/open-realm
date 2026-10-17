"""Patch 10: offline-only differential analysis, provenance, and fail-closed tests."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from unittest import TestCase, mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from wc3_re import differential as diff
import wc3_ability_re as cli

SHA = "3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed"
RVA = "0x0080d820"


def put(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def probe_text(run_id, *, life=90, initial=100, speed=220, complete=True, extras=""):
    rows = [f"SESSION_START run_id={run_id}", "ability=Apxf mode=generated_lab",
            "setup_failed=false", "accepted=true"]
    for tick, health in ((0, initial), (1, life)):
        rows += [f"OBS role=caster tick={tick} time={tick * .25:.2f} life=100 mana=100 x=0 y=0 speed=300 order=0",
                 f"OBS role=target index=0 tick={tick} time={tick * .25:.2f} life={health} mana=10 x={tick * 10} y=0 speed={speed} owner=12"]
        rows.append(f"BUFF target=0 rawcode=Bpxf tick={tick} level={tick}")
    if extras:
        rows.append(extras)
    if complete:
        rows.append(f"SESSION_DONE run_id={run_id}")
    return "".join(f'call Preload("{row}")\n' for row in rows)


class DifferentialTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.offline = self.root / "offline"
        put(self.offline / "questions.json", {"schema_version": 1, "rawcode": "Apxf", "questions": [
            {"id": "Q0001", "category": "native_logic", "kind": "decompilation_missing_or_failed",
             "source": "graph.decompiled", "status": "unresolved", "suggested_resolution": "Decompile 0x01"},
            {"id": "Q0002", "category": "native_logic", "kind": "class_binding_unverified",
             "source": "graph.class_reference_hint", "status": "unresolved", "suggested_resolution": "Review factory"},
            {"id": "Q0003", "category": "presentation", "kind": "authored_presentation_gap",
             "source": "presentation.editions.tft.gaps", "status": "unresolved", "suggested_resolution": "Inspect model"}]})
        put(self.offline / "provenance.json", {"executable_sha256": SHA, "input_digests": {}})
        put(self.offline / "coverage.json", {"schema_version": 1, "rawcode": "Apxf", "metrics": {}})
        self.lab = self.root / "lab"
        self.case = {"kind": "passive", "ticks": 1, "sample_interval_seconds": 0.25,
                     "targets": [{"unit_id": "hfoo"}], "buff_ids": ["Bpxf"]}
        self.cases = {name: {**self.case, "run_id": name, "result_file": str(self.root / f"{name}.txt")}
                      for name in ("treated", "control")}
        put(self.lab / "lab-plan.json", {"schema_version": 1, "rawcode": "Apxf",
                                         "cases": list(self.cases.values())})
        self.spec = self.root / "comparisons.json"
        put(self.spec, {"schema_version": 1, "comparisons": [{
            "id": "life-impact", "case": "treated", "control": "control",
            "metric": "life_change", "relation": "different", "tolerance": 1.0},
            {"id": "speed-equal", "case": "treated", "control": "control",
             "metric": "speed_change", "relation": "same"},
            {"id": "hit-path", "case": "treated", "control": "control",
             "metric": "function_enter_count", "function_rva": RVA,
             "relation": "different"}]})

    def test_sample_parsing(self):
        path = self.root / "result.txt"
        path.write_text(probe_text("treated"))
        capture = diff._parse_result(path, "treated", self.case, "Apxf")
        self.assertEqual(capture["status"], "sampled")
        self.assertEqual(capture["samples"]["target:0"][1]["life"], 90)
        self.assertEqual(capture["buffs"]["target:0:Bpxf"][1], 1)

    def test_missing_marker_or_foreign_run_is_inconclusive(self):
        path = self.root / "result.txt"
        for string in (probe_text("treated", complete=False),
                       probe_text("treated", extras="SESSION_DONE run_id=foreign")):
            path.write_text(string)
            self.assertEqual(diff._parse_result(path, "treated", self.case, "Apxf")["status"], "inconclusive")

    def test_rejected_setup_and_overflow_not_negative_proofs(self):
        path = self.root / "result.txt"
        for fragment in ("setup_failed=true", "accepted=false", "buffer_overflow=true"):
            path.write_text(probe_text("treated", extras=fragment))
            self.assertEqual(diff._parse_result(path, "treated", self.case, "Apxf")["status"], "inconclusive")

    def test_gapped_tick_and_duplicate_samples_are_inconclusive(self):
        path = self.root / "result.txt"
        text = probe_text("treated")
        path.write_text(text.replace("tick=1", "tick=2"))
        self.assertEqual(diff._parse_result(path, "treated", self.case, "Apxf")["status"], "inconclusive")
        path.write_text(text.replace('call Preload("SESSION_DONE',
                                     'call Preload("OBS role=target index=0 tick=0 time=0 life=90")\ncall Preload("SESSION_DONE'))
        self.assertEqual(diff._parse_result(path, "treated", self.case, "Apxf")["status"], "inconclusive")

    def test_extra_target_and_buff_records_rejected(self):
        path = self.root / "result.txt"
        original = probe_text("treated")
        for extra in ('OBS role=target index=7 tick=1 time=0.25 life=2',
                      'BUFF target=7 rawcode=Bpxf tick=1 level=1'):
            path.write_text(original.replace('call Preload("SESSION_DONE',
                       f'call Preload("{extra}")\ncall Preload("SESSION_DONE'))
            self.assertEqual(diff._parse_result(path, "treated", self.case, "Apxf")["status"], "inconclusive")

    def test_cli_end_to_end_static_only(self):
        dest = self.root / "analysis_cli"
        self.assertEqual(cli.main(["ability-analyze", "--offline", str(self.offline),
                                   "--output", str(dest)]), 0)
        self.assertEqual(json.loads((dest / "analysis.json").read_text())["open_question_count"], 3)
        self.assertTrue((dest / "review.md").is_file())
        self.assertEqual(cli.main(["ability-analyze", "--offline", str(self.offline),
                                   "--output", str(dest)]), 1)

    def test_mismatched_rawcode_and_hash(self):
        put(self.lab / "lab-plan.json", {"schema_version": 1, "rawcode": "ANch", "cases": []})
        with self.assertRaisesRegex(diff.DifferentialError, "rawcode"):
            diff.analyze(offline=self.offline, lab=self.lab)
        put(self.lab / "lab-plan.json", {"schema_version": 1, "rawcode": "Apxf", "cases": list(self.cases.values())})
        put(self.offline / "provenance.json", {"executable_sha256": "bad"})
        with self.assertRaisesRegex(diff.DifferentialError, "hash"):
            diff.analyze(offline=self.offline, lab=self.lab)

    def test_bad_or_duplicate_comparisons_and_missing_controls(self):
        put(self.spec, {"schema_version": 1, "comparisons": [{"id": "a", "case": "treated", "control": "bad",
                                                                "metric": "life_change", "relation": "different"}]})
        with self.assertRaisesRegex(diff.DifferentialError, "distinct lab case"):
            diff.analyze(offline=self.offline, lab=self.lab, comparisons=self.spec)
        put(self.spec, {"schema_version": 1, "comparisons": [{"id": "a", "case": "treated", "control": "control",
             "metric": "life_change", "relation": "different", "tolerance": float("nan")}]})
        with self.assertRaisesRegex(diff.DifferentialError, "finite"):
            diff.analyze(offline=self.offline, lab=self.lab, comparisons=self.spec)

    def test_rank_static_questions_without_running_retail(self):
        output = diff.analyze(offline=self.offline, lab=self.lab)
        self.assertEqual(output["open_question_count"], 3)
        self.assertEqual([x["priority"] for x in output["question_actions"]], [1, 2, 3])
        self.assertTrue(all(x["needs_retail_run"] is False for x in output["question_actions"]))
        self.assertFalse(output["policy"]["questions_auto_resolved"])

    def _fixture_session(self, *, bad_native=False, invalid_case=None):
        session = self.root / "session"
        plan_dir = self.root / "trace-plan"
        put(plan_dir / "trace-plan.json", {"kind": "read_only_frida_function_entry_plan", "rawcode": "Apxf"})
        session.mkdir()
        manifest = {"rawcode": "Apxf", "plan_dir": str(plan_dir), "prepared_map_sha256": "abcd",
                    "cases": [{"run_id": name, "result_file": item["result_file"]} for name, item in self.cases.items()]}
        put(session / "session.json", manifest)
        statuses = []
        for run_id in self.cases:
            status = "timeout" if run_id == invalid_case else "ready_for_review"
            statuses.append({"run_id": run_id, "status": status})
            out = session / run_id
            out.mkdir()
            put(out / "review.json", {"run_id": run_id, "status": status, "native_trace_status":
                 "partial_native_trace" if bad_native else "bounded_native_trace",
                 "native_counts_by_run_id": {run_id: 1}, "jass_result_fresh": True})
            (out / "trace.jsonl").write_text("{}\n")
            (out / "result.txt").write_text(probe_text(run_id, life=90 if run_id == "treated" else 100))
        put(session / "run-summary.json", {"rawcode": "Apxf", "cases": statuses})
        return session, manifest

    def _native(self, plan_dir, trace_path):
        run_id = trace_path.parent.name
        return {"status": "bounded_native_trace", "rawcode": "Apxf", "executable_sha256": SHA,
                "function_entry_counts": {RVA: {"enter": 1 if run_id == "treated" else 0, "leave": 0}},
                "event_counts_by_run_id": {run_id: 1}}

    def test_actual_pipeline_with_mocks_at_live_provenance_boundary(self):
        session, saved = self._fixture_session()
        spec = diff._read_comparisons(self.spec, self.cases)
        fake_plan = {"rawcode": "Apxf", "executable_sha256": SHA}
        with mock.patch.object(diff, "inspect_session", return_value=(saved, fake_plan, {})), \
             mock.patch.object(diff, "summarize_trace", side_effect=self._native):
            output = diff.analyze(offline=self.offline, lab=self.lab, sessions=[session], comparisons=self.spec)
            comparison = {item["id"]: item for item in output["comparisons"]}
            self.assertEqual(comparison["life-impact"]["status"], "observed_consistent")
            self.assertEqual(comparison["speed-equal"]["status"], "observed_consistent")
            self.assertEqual(comparison["hit-path"]["status"], "observed_consistent")
            self.assertEqual(output["open_question_count"], 3)
            self.assertEqual(len(output["capture_summaries"]), 2)
            self.assertFalse(output["policy"]["retail_rerun_by_default"])
            diff.write(output, self.root / "out")
            self.assertIn("automatically closed: **0**", (self.root / "out/review.md").read_text())
            with self.assertRaisesRegex(diff.DifferentialError, "overwrite"):
                diff.write(output, self.root / "out")
        self.assertEqual(len(spec), 3)

    def test_incomplete_native_trace_blocks_differential(self):
        session, saved = self._fixture_session(bad_native=True)
        def partial(_plan, trace):
            obj = self._native(_plan, trace)
            obj["status"] = "partial_native_trace"
            return obj
        with mock.patch.object(diff, "inspect_session", return_value=(saved, {"rawcode": "Apxf", "executable_sha256": SHA}, {})), \
             mock.patch.object(diff, "summarize_trace", side_effect=partial):
            report = diff.analyze(offline=self.offline, lab=self.lab, sessions=[session], comparisons=self.spec)
        self.assertTrue(all(row["status"] == "inconclusive" for row in report["comparisons"]))
        self.assertTrue(all(row["status"] == "inconclusive" for row in report["capture_summaries"]))

    def test_missing_second_case_never_becomes_negative_result(self):
        session, saved = self._fixture_session(invalid_case="control")
        with mock.patch.object(diff, "inspect_session", return_value=(saved, {"rawcode": "Apxf", "executable_sha256": SHA}, {})), \
             mock.patch.object(diff, "summarize_trace", side_effect=self._native):
            report = diff.analyze(offline=self.offline, lab=self.lab, sessions=[session], comparisons=self.spec)
        self.assertEqual(report["comparisons"][0]["status"], "inconclusive")

    def test_cli_parser_with_new_command(self):
        args = cli.build_parser().parse_args(["ability-analyze", "--offline", str(self.offline),
                                               "--output", str(self.root / "output")])
        self.assertEqual(args.run, cli.command_ability_analyze)
        self.assertEqual(args.session, [])

    def test_bad_session_provenance_is_rejected(self):
        session, saved = self._fixture_session()
        with mock.patch.object(diff, "inspect_session", side_effect=diff.SessionError("map hash altered")):
            with self.assertRaisesRegex(diff.DifferentialError, "map hash altered"):
                diff.analyze(offline=self.offline, lab=self.lab, sessions=[session])

    def test_cross_session_pairs_never_mixed(self):
        captures = [
            {"session_id": "s1", "run_id": "treated", "status": "usable_observation", "lab": self.case,
             "jass": {"samples": {"target:0": {0: {"life": 100}, 1: {"life": 90}}}}, "native_counts": {}},
            {"session_id": "s2", "run_id": "control", "status": "usable_observation", "lab": self.case,
             "jass": {"samples": {"target:0": {0: {"life": 100}, 1: {"life": 100}}}}, "native_counts": {}}]
        comparisons = diff._read_comparisons(self.spec, self.cases)
        result = diff._compare(comparisons, captures)
        self.assertEqual(result[0]["status"], "inconclusive")
        self.assertEqual(result[0]["paired_observations"], [])


if __name__ == "__main__":
    import unittest
    unittest.main()
