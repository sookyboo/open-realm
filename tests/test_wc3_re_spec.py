"""Patch 11: offline source-linked ability specification generator tests."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from wc3_re import package as pkg, spec
import wc3_ability_re as cli

SHA = "3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed"
RVA = "0x0080d820"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def source_lookup():
    return {"schema_version": 1, "rawcode": "Apxf",
            "executable_identity": {"sha256": SHA},
            "editions": {"tft": {"found": True, "ranks": [{"level": 1, "area": 600.0}],
                                 "retail_class_reference": {"implementation_code": "Apxf",
                                                            "class": "CAbilityPhoenixFire"}}}}


def source_graph():
    return {"schema_version": 1, "rawcode": "Apxf", "status": "static_candidate_graph",
            "executable_sha256": SHA, "class_reference_hint": "CAbilityPhoenixFire", "class_reference_is_native_verified": False,
            "nodes": [{"rva": RVA, "depth": 0, "incoming_static_function_count": 0, "decompile_status": "complete"}], "edges": [], "gaps": [],
            "data_references": {}, "memory_access_candidates": {}, "branch_candidates": {},
            "decompiled": {RVA: {"status": "complete", "c": "void FUN_0080d820(void) {}", "source": "ghidra"}},
            "claims": {"runtime_reachability_proven": False,
                       "semantic_state_fields_proven": False,
                       "animation_or_effect_timing_proven": False}}


def source_presentation():
    return {"schema_version": 1, "rawcode": "Apxf", "runtime_effect_timing_verified": False,
            "editions": {"tft": {"found": True, "rank_links": [], "models": [], "sounds": [],
                                 "references": [{"source": "Buff:Bpxf", "field": "TargetArt",
                                                 "asset": "Abilities/Fire.mdx", "value": "Abilities/Fire.mdx", "kind": "model"}], "gaps": []}}}


def reviewed():
    return {"schema_version": 1, "rawcode": "Apxf", "executable_sha256": SHA,
            "claims": [
                {"id": "radius", "domain": "targeting", "statement": "Uses the authored radius field during acquisition",
                 "evidence": [{"type": "authored", "edition": "tft", "rank": 1, "field": "area"},
                              {"type": "native", "rva": RVA}]},
            ],
            "logic_steps": [{"id": "step1", "stage": "periodic",
                             "description": "Read rank-specific radius before target enumeration",
                             "claim_ids": ["radius"]}],
            "state_transitions": [{"id": "state1", "from": "active", "event": "scan_timer",
                                   "to": "active", "actions": "enumerate candidates",
                                   "claim_ids": ["radius"]}],
            "presentation_events": [{"id": "art1", "phase": "unknown",
                                     "description": "Art path exists; actual playback requires tracing",
                                     "asset": "Abilities/Fire.mdx", "claim_ids": ["radius"]}],
            "acceptance_tests": [{"id": "test1", "given": "caster with rank 1",
                                  "when": "periodic scan triggers", "then": "radius data is read",
                                  "claim_ids": ["radius"]}],
            "reference_c": [{"id": "c1", "code": "/* reviewed excerpt */\nfloat example_radius = 600.0f;",
                             "claim_ids": ["radius"]}]}


class SpecTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.recon = self.root / "reconstruct"
        self.lookup = source_lookup()
        self.graph = source_graph()
        self.presentation = source_presentation()
        self.prepare()

    def prepare(self):
        self.recon.mkdir(parents=True, exist_ok=True)
        save(self.recon / "lookup.json", self.lookup)
        from wc3_re.graph import write_graph
        from wc3_re.presentation import write_presentation
        write_graph(self.graph, self.recon / "graph")
        write_presentation(self.presentation, self.recon / "presentation")
        pkg.write_package(pkg.build_package(self.lookup, graph=self.graph,
                                            presentation=self.presentation), self.recon / "offline")
        self.review = self.root / "review.json"
        save(self.review, reviewed())

    def write_analysis(self):
        analysis = {"schema_version": 1, "kind": "retail_ability_differential_review",
                    "rawcode": "Apxf", "executable_sha256": SHA,
                    "status": "observation_and_followup_plan_not_parity_proof",
                    "offline_inputs": {name: spec._hash_file(self.recon / "offline" / name)
                                       for name in ("questions.json", "provenance.json", "coverage.json")},
                    "comparisons": [{"id": "cmp1", "status": "observed_consistent",
                                     "metric": "life_change", "paired_observations": [{"matches_relation": True}],
                                     "incomplete_sessions": []}],
                    "capture_summaries": [], "question_actions": []}
        path = self.root / "analysis.json"
        save(path, analysis)
        return path

    def test_lookup_graph_art_review_and_source_provenance(self):
        report = spec.build(self.recon, review=self.review)
        self.assertEqual(report["rawcode"], "Apxf")
        self.assertEqual(report["reviewed"]["logic_steps"][0]["claim_ids"], ["radius"])
        self.assertEqual(report["status"], "reviewed_draft_not_full_retail_parity")
        self.assertEqual(report["guardrails"]["runtime_parity_proven"], False)
        self.assertTrue(report["provenance"]["review_sha256"])

    def test_cli_outputs_nonrunnable_c_and_specifications(self):
        out = self.root / "spec"
        self.assertEqual(cli.main(["ability-spec", "--reconstruction", str(self.recon),
                                   "--review", str(self.review), "--output", str(out)]), 0)
        c = (out / "reference/ability.c").read_text()
        self.assertIn("#if 0", c)
        self.assertIn("example_radius = 600.0f", c)
        self.assertIn("#endif", c)
        self.assertIn("periodic", (out / "implementation.md").read_text())
        self.assertIn("Abilities/Fire.mdx", (out / "presentation-timeline.md").read_text())
        self.assertIn("test1", (out / "acceptance-tests.md").read_text())
        self.assertEqual(json.loads((out / "acceptance-tests.json").read_text())["tests"][0]["id"], "test1")
        self.assertEqual(cli.main(["ability-spec", "--reconstruction", str(self.recon),
                                   "--output", str(out)]), 1)

    def test_without_review_is_honest_source_only_draft(self):
        report = spec.build(self.recon)
        self.assertEqual(report["reviewed"]["claims"], [])
        out = self.root / "no-review"
        spec.write(report, out)
        self.assertIn("No reviewed C implementation", (out / "reference/ability.c").read_text())
        self.assertIn("No reviewed runtime presentation", (out / "presentation-timeline.md").read_text())
        self.assertIn("No reviewed algorithm", (out / "implementation.md").read_text())
        self.assertGreater(len(report["open_questions"]), 0)

    def test_lookup_changed_after_package_is_rejected(self):
        edited = json.loads((self.recon / "lookup.json").read_text())
        edited["editions"]["tft"]["ranks"][0]["area"] = 900.0
        save(self.recon / "lookup.json", edited)
        with self.assertRaisesRegex(spec.SpecError, "changed"):
            spec.build(self.recon)

    def test_tampered_graph_and_presentation_is_rejected_when_cached_inputs_supplied(self):
        structure = self.recon / "graph/execution-graph.json"
        original = structure.read_text()
        structure.write_text(original.replace("static_candidate_graph", "modified_graph"))
        with self.assertRaisesRegex(spec.SpecError, "graph changed"):
            spec.build(self.recon)
        structure.write_text(original)
        assets = self.recon / "presentation/assets.json"
        obj = json.loads(assets.read_text())
        obj["editions"]["tft"]["gaps"].append("unreviewed change")
        save(assets, obj)
        with self.assertRaisesRegex(spec.SpecError, "presentation changed"):
            spec.build(self.recon)

    def test_review_rawcode_mismatch_fails(self):
        content = reviewed()
        content["rawcode"] = "AOsw"
        save(self.review, content)
        with self.assertRaisesRegex(spec.SpecError, "identity mismatch"):
            spec.build(self.recon, review=self.review)

    def test_unavailable_function_and_field_references_fail_closed(self):
        content = reviewed()
        content["claims"][0]["evidence"][1]["rva"] = "0x00ffffff"
        save(self.review, content)
        with self.assertRaisesRegex(spec.SpecError, "native RVA"):
            spec.build(self.recon, review=self.review)
        content = reviewed()
        content["claims"][0]["evidence"][0]["field"] = "missing"
        save(self.review, content)
        with self.assertRaisesRegex(spec.SpecError, "rank field"):
            spec.build(self.recon, review=self.review)

    def test_malformed_review_types_fail_with_spec_error(self):
        content = reviewed()
        content["claims"][0]["domain"] = ["targeting"]
        save(self.review, content)
        with self.assertRaisesRegex(spec.SpecError, "invalid/duplicate reviewed"):
            spec.build(self.recon, review=self.review)
        content = reviewed()
        content["claims"][0]["evidence"][0]["edition"] = ["tft"]
        save(self.review, content)
        with self.assertRaisesRegex(spec.SpecError, "authored source"):
            spec.build(self.recon, review=self.review)
        content = reviewed()
        content["logic_steps"][0]["stage"] = ["periodic"]
        save(self.review, content)
        with self.assertRaisesRegex(spec.SpecError, "execution stage"):
            spec.build(self.recon, review=self.review)

    def test_review_unknown_claim_and_invalid_stage_rejected(self):
        content = reviewed()
        content["logic_steps"][0]["claim_ids"] = ["not-reviewed"]
        save(self.review, content)
        with self.assertRaisesRegex(spec.SpecError, "claim ids"):
            spec.build(self.recon, review=self.review)
        content = reviewed()
        content["logic_steps"][0]["stage"] = "teleporting-unproven"
        save(self.review, content)
        with self.assertRaisesRegex(spec.SpecError, "execution stage"):
            spec.build(self.recon, review=self.review)

    def test_syntax_injection_into_reference_c_disallowed(self):
        content = reviewed()
        content["reference_c"][0]["code"] += "\n#endif\nint fake_behavior() { return 1; }"
        save(self.review, content)
        with self.assertRaisesRegex(spec.SpecError, "preprocessor directives"):
            spec.build(self.recon, review=self.review)

    def test_valid_analysis_only_observations_not_logic_or_spec(self):
        path = self.write_analysis()
        report = spec.build(self.recon, analysis=path)
        self.assertEqual(report["reviewed"]["claims"], [])
        out = self.root / "with-analysis"
        spec.write(report, out)
        doc = (out / "acceptance-tests.json").read_text()
        self.assertIn('"observed_consistent"', doc)
        self.assertTrue(json.loads(doc)["sampled_comparisons_are_not_exact_contracts"])

    def test_analysis_hash_or_build_mismatch_is_rejected(self):
        path = self.write_analysis()
        content = json.loads(path.read_text())
        content["offline_inputs"]["questions.json"] = "0" * 64
        save(path, content)
        with self.assertRaisesRegex(spec.SpecError, "current offline source"):
            spec.build(self.recon, analysis=path)
        content["offline_inputs"]["questions.json"] = spec._hash_file(self.recon / "offline/questions.json")
        content["executable_sha256"] = "a" * 64
        save(path, content)
        with self.assertRaisesRegex(spec.SpecError, "executable hash"):
            spec.build(self.recon, analysis=path)

    def test_inconclusive_comparison_cannot_underwrite_claim(self):
        path = self.write_analysis()
        data = json.loads(path.read_text())
        data["comparisons"][0]["status"] = "inconclusive"
        save(path, data)
        content = reviewed()
        content["claims"][0]["evidence"].append({"type": "comparison", "id": "cmp1"})
        save(self.review, content)
        with self.assertRaisesRegex(spec.SpecError, "inconclusive comparison"):
            spec.build(self.recon, analysis=path, review=self.review)

    def test_observed_comparison_can_be_cited_without_claiming_parity(self):
        path = self.write_analysis()
        content = reviewed()
        content["claims"][0]["evidence"].append({"type": "comparison", "id": "cmp1"})
        save(self.review, content)
        report = spec.build(self.recon, analysis=path, review=self.review)
        self.assertFalse(report["guardrails"]["runtime_parity_proven"])
        self.assertIn("sampled comparison cmp1", spec._implementation(report))

    def test_garbage_analysis_consistency_fails(self):
        path = self.write_analysis()
        data = json.loads(path.read_text())
        data["comparisons"][0]["paired_observations"] = []
        save(path, data)
        with self.assertRaisesRegex(spec.SpecError, "complete matching pairs"):
            spec.build(self.recon, analysis=path)


if __name__ == "__main__":
    unittest.main()
