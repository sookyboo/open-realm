"""Patch 12: synthetic offline end-to-end smoke and evidence integrity tests.

Fixtures are NOT decompiled Retail behavior or proprietary assets.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from wc3_re import readiness, spec
import wc3_ability_re as cli


class HarnessReadinessTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        self.out = self.home / "smoke"
        self.summary = readiness.smoke(output=self.out)

    def recon(self, rawcode="Apxf"):
        return self.out / rawcode

    def test_both_abilities_execute_complete_synthetic_pipeline(self):
        self.assertEqual([item["rawcode"] for item in self.summary["cases"]], ["Apxf", "AOsw"])
        self.assertFalse(self.summary["retail_executed"])
        self.assertFalse(self.summary["ghidra_executed"])
        self.assertFalse(self.summary["warcraft_assets_used"])
        for rawcode in ("Apxf", "AOsw"):
            root = self.recon(rawcode)
            self.assertTrue((root / "offline/native/decompiled.c").is_file())
            self.assertTrue((root / "trace/agent.js").is_file())
            self.assertTrue((root / "analysis/analysis.json").is_file())
            self.assertTrue((root / "spec/implementation.md").is_file())
            self.assertEqual(json.loads((root / "spec/spec-evidence.json").read_text())["claims"], [])
            self.assertIn("#if 0", (root / "spec/reference/ability.c").read_text())
            self.assertGreater(json.loads((root / "readiness.json").read_text())["open_questions"], 0)

    def test_fixture_alias_and_native_candidates_are_distinct(self):
        ward = self.recon("AOsw")
        lookup = json.loads((ward / "lookup.json").read_text())
        self.assertEqual(lookup["editions"]["tft"]["retail_class_reference"]["implementation_code"], "AOwd")
        self.assertIn("synthetic", (ward / "offline/native/decompiled.c").read_text().lower())
        self.assertFalse(json.loads((ward / "spec/spec-evidence.json").read_text())["guardrails"]["runtime_parity_proven"])

    def test_full_readiness_validates_optional_stages(self):
        root = self.recon()
        report = readiness.inspect(root, trace=root / "trace", analysis=root / "analysis",
                                   output_spec=root / "spec")
        self.assertTrue(all(report["checks"][key]["status"] == "validated"
                            for key in ("graph", "offline", "trace", "analysis", "presentation", "specification")))
        self.assertEqual(report["checks"]["session"]["status"], "not_supplied")
        self.assertFalse(report["evidence_boundary"]["live_integration_tested"])

    def test_readiness_without_optional_inputs_is_not_runtime_proof(self):
        root = self.recon()
        report = readiness.inspect(root)
        self.assertEqual(report["checks"]["analysis"]["status"], "not_supplied")
        self.assertEqual(report["checks"]["trace"]["status"], "not_supplied")
        self.assertEqual(report["checks"]["specification"]["status"], "not_supplied")
        self.assertNotIn("verified", report["status"])

    def test_modified_lookup_fails_readiness(self):
        path = self.recon() / "lookup.json"
        doc = json.loads(path.read_text())
        doc["editions"]["tft"]["ranks"][0]["area"] = 1
        path.write_text(json.dumps(doc))
        with self.assertRaisesRegex(readiness.ReadinessError, "lookup.*changed"):
            readiness.inspect(self.recon())

    def test_modified_graph_fails_readiness(self):
        path = self.recon() / "graph/execution-graph.json"
        doc = json.loads(path.read_text())
        doc["edges"] = []
        path.write_text(json.dumps(doc))
        with self.assertRaisesRegex(readiness.ReadinessError, "graph changed"):
            readiness.inspect(self.recon())

    def test_modified_presentation_fails_readiness(self):
        path = self.recon() / "presentation/assets.json"
        doc = json.loads(path.read_text())
        doc["editions"]["tft"]["gaps"] = []
        path.write_text(json.dumps(doc))
        with self.assertRaisesRegex(readiness.ReadinessError, "presentation changed"):
            readiness.inspect(self.recon())

    def test_trace_plan_mutation_fails_readiness(self):
        path = self.recon() / "trace/trace-plan.json"
        doc = json.loads(path.read_text())
        doc["graph_sha256"] = "0" * 64
        path.write_text(json.dumps(doc))
        with self.assertRaisesRegex(readiness.ReadinessError, "graph"):
            readiness.inspect(self.recon(), trace=self.recon() / "trace")

    def test_frida_agent_mutation_fails_readiness(self):
        (self.recon() / "trace/agent.js").write_text("// broken")
        with self.assertRaisesRegex(readiness.ReadinessError, "agent"):
            readiness.inspect(self.recon(), trace=self.recon() / "trace")

    def test_analysis_rebased_on_other_offline_package_fails(self):
        with self.assertRaises((readiness.ReadinessError, spec.SpecError)):
            readiness.inspect(self.recon("AOsw"), analysis=self.recon("Apxf") / "analysis")

    def test_specification_cannot_be_relabelled_as_other_ability(self):
        with self.assertRaisesRegex(readiness.ReadinessError, "specification"):
            readiness.inspect(self.recon("AOsw"), output_spec=self.recon("Apxf") / "spec")

    def test_session_cross_ability_fails_preflight(self):
        root = self.recon()
        with mock.patch.object(readiness, "inspect_session", return_value=(
                {"rawcode": "AOsw", "plan_dir": str(root / "trace")},
                {"executable_sha256": json.loads((root / "lookup.json").read_text())["executable_identity"]["sha256"]}, {})):
            with self.assertRaisesRegex(readiness.ReadinessError, "another ability"):
                readiness.inspect(root, session=self.home / "not-really-a-session")

    def test_mocked_tool_preflight_is_presence_only(self):
        root = self.recon()
        sha = json.loads((root / "lookup.json").read_text())["executable_identity"]["sha256"]
        executable = self.home / "exe"
        executable.write_text("not real Retail")
        with self.assertRaisesRegex(readiness.ReadinessError, "SHA-256 differs"):
            readiness.tool_preflight(sha=sha, executable=executable)
        with mock.patch.object(readiness.shutil, "which", return_value="/usr/bin/fixture"), \
             mock.patch.object(readiness.importlib.util, "find_spec", return_value=object()), \
             mock.patch.dict(readiness.os.environ, {"DISPLAY": ":99"}):
            result = readiness.tool_preflight(sha=sha)
        self.assertEqual(result["checks"]["retail_executable"], "not_configured")
        self.assertFalse(result["fully_configured"])

    def test_smoke_refuses_overwrite_without_touching_old_evidence(self):
        before = (self.out / "smoke-summary.json").read_bytes()
        with self.assertRaisesRegex(readiness.ReadinessError, "existing smoke"):
            readiness.smoke(output=self.out)
        self.assertEqual((self.out / "smoke-summary.json").read_bytes(), before)

    def test_missing_fixture_fails_before_output_creation(self):
        fixture_dir = self.home / "partial"
        fixture_dir.mkdir()
        shutil.copy(readiness.FIXTURES / "Apxf.json", fixture_dir / "Apxf.json")
        new_output = self.home / "never_created"
        with self.assertRaisesRegex(readiness.ReadinessError, "cannot load"):
            readiness.smoke(output=new_output, fixtures=fixture_dir)
        self.assertFalse(new_output.exists())

    def test_bad_rawcode_fixture_fails_before_output_creation(self):
        fixture_dir = self.home / "bad"
        shutil.copytree(readiness.FIXTURES, fixture_dir)
        doc = json.loads((fixture_dir / "AOsw.json").read_text())
        doc["presentation"]["rawcode"] = "Apxf"
        (fixture_dir / "AOsw.json").write_text(json.dumps(doc))
        target = self.home / "not_created"
        with self.assertRaisesRegex(readiness.ReadinessError, "fixture rawcode mismatch"):
            readiness.smoke(output=target, fixtures=fixture_dir)
        self.assertFalse(target.exists())

    def test_immutable_report_output_and_cli(self):
        root = self.recon()
        target = self.home / "readiness.json"
        self.assertEqual(cli.main(["ability-readiness", "--reconstruction", str(root),
                                   "--trace", str(root / "trace"),
                                   "--analysis", str(root / "analysis"),
                                   "--specification", str(root / "spec"),
                                   "--output", str(target)]), 0)
        self.assertEqual(json.loads(target.read_text())["rawcode"], "Apxf")
        self.assertEqual(cli.main(["ability-readiness", "--reconstruction", str(root),
                                   "--output", str(target)]), 1)
        new_target = self.home / "cli-smoke"
        self.assertEqual(cli.main(["ability-smoke", "--output", str(new_target)]), 0)
        self.assertTrue((new_target / "AOsw/spec/spec-evidence.json").is_file())
        self.assertEqual(cli.main(["ability-smoke", "--output", str(new_target)]), 1)


if __name__ == "__main__":
    unittest.main()
