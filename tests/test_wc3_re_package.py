"""Patch 6: complete offline reports from immutable, synthetic prior-stage exports."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from wc3_re import package as pkg
from wc3_re import graph as graph_io
from wc3_re import presentation as presentation_io
import wc3_ability_re as cli

SHA = "3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed"
RVA = "0x0080d820"
OTHER = "0x0080ecd0"


def lookup():
    return {"schema_version": 1, "rawcode": "Apxf",
            "executable_identity": {"sha256": SHA},
            "editions": {"roc": {"found": False}, "tft": {
                "found": True, "archives": ["War3.mpq", "War3x.mpq"],
                "ranks": [{"level": 1}], "retail_class_reference": {
                    "implementation_code": "Apxf", "class": "CAbilityPhoenixFire",
                    "status": "offline_reference_hint"}}}}


def graph():
    return {"schema_version": 1, "rawcode": "Apxf", "status": "static_candidate_graph",
            "executable_sha256": SHA, "class_reference_hint": "CAbilityPhoenixFire",
            "class_reference_is_native_verified": False,
            "input_exports": {"scan": "cached/scan", "detail": ["cached/detail"]},
            "nodes": [{"rva": RVA, "name": "PhoenixHandler", "decompile_status": "complete", "depth": 0, "incoming_static_function_count": 0},
                      {"rva": OTHER, "name": "PhoenixAcquire", "decompile_status": "not_exported", "depth": 1, "incoming_static_function_count": 1}],
            "edges": [{"from": RVA, "to": OTHER, "kind": "direct_call", "traversable": True,
                       "evidence": [{"origin": "ghidra_scan", "site_rva": "0x0080d830"},
                                    {"origin": "research_inventory", "index": 1, "context": "verified call"}]}],
            "gaps": [{"kind": "decompilation_missing_or_failed", "rva": OTHER},
                     {"kind": "indirect_or_unmapped_call", "rva": RVA, "count": 1}],
            "decompiled": {RVA: {"status": "complete", "c": "void FUN_0080d820(void) {}",
                                 "source": "cached/detail/decompiled.jsonl:1"}},
            "data_references": {RVA: [{"site_rva": "0x0080d831", "interpretation": "not_proven_field"}]},
            "memory_access_candidates": {RVA: [{"opcode": "STORE"}]},
            "branch_candidates": {RVA: [{"opcode": "CBRANCH"}]},
            "unbound_vtable_candidates": [{"status": "pointer_table_candidate_only"}],
            "claims": {"runtime_reachability_proven": False,
                       "semantic_state_fields_proven": False,
                       "animation_or_effect_timing_proven": False}}


def presentation():
    return {"schema_version": 1, "rawcode": "Apxf",
            "state": "authored_presentation_and_static_model_metadata_only",
            "runtime_effect_timing_verified": False,
            "editions": {"roc": {"found": False}, "tft": {
                "found": True, "archives": ["War3.mpq", "War3x.mpq"],
                "rank_links": [{"level": 1, "buff_ids": ["Bpxf"]}],
                "references": [{"source": "Buff:Bpxf", "field": "TargetArt", "rank": 1,
                                "asset": "Abilities\\Fire.mdx", "value": "Abilities/Fire.mdx", "kind": "model",
                                "evidence": "authored_data_only"}],
                "models": [{"path": "Abilities\\Fire.mdx", "status": "static_model_metadata",
                            "sequences": [{"name": "Stand"}]}],
                "sounds": [{"alias": "Fire", "status": "unresolved_sound_alias"}],
                "gaps": ["Runtime choice/timing, attachment spawning and effect lifetime require native evidence."]}}}


class OfflinePackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_merged_summary_preserves_graph_and_presentation_evidence(self):
        doc = pkg.build_package(lookup(), graph=graph(), presentation=presentation())
        self.assertEqual(doc["executable_sha256"], SHA)
        self.assertEqual(doc["coverage"]["metrics"]["function_nodes"], 2)
        self.assertEqual(doc["coverage"]["metrics"]["decompiled_complete"], 1)
        self.assertEqual(doc["coverage"]["metrics"]["authored_presentation_references"], 1)
        self.assertEqual(len(doc["dependencies"]["call_relationships"][0]["evidence"]), 2)
        self.assertEqual(doc["dependencies"]["memory_access_candidates"][RVA][0]["opcode"], "STORE")
        self.assertEqual(doc["dependencies"]["presentation"]["tft"]["rank_links"][0]["buff_ids"], ["Bpxf"])
        self.assertEqual(doc["code"][RVA]["c"], "void FUN_0080d820(void) {}")

    def test_offline_gaps_and_no_fabricated_code(self):
        doc = pkg.build_package(lookup(), graph=graph(), presentation=presentation())
        kinds = {row["kind"] for row in doc["questions"]}
        self.assertIn("indirect_or_unmapped_call", kinds)
        self.assertIn("class_binding_unverified", kinds)
        self.assertIn("sound_alias_unresolved", kinds)
        self.assertIn("effects_animation_timing_unproven", kinds)
        self.assertEqual(doc["coverage"]["dimensions"]["full_retail_parity"], "not_established")
        self.assertNotIn(OTHER, doc["code"])

    def test_lookup_only_has_honest_coverage_and_actionable_gaps(self):
        doc = pkg.build_package(lookup())
        self.assertEqual(doc["coverage"]["dimensions"]["native_pseudocode"], "not_available")
        self.assertEqual(doc["coverage"]["dimensions"]["presentation_assets"], "not_supplied")
        self.assertIn("no_execution_graph", [row["kind"] for row in doc["questions"]])
        self.assertIn("no_presentation_report", [row["kind"] for row in doc["questions"]])
        out = self.root / "lookup-only"
        pkg.write_package(doc, out)
        self.assertIn("No successful", (out / "native" / "decompiled.c").read_text())

    def test_wrong_rawcode_in_graph_or_presentation_fails_closed(self):
        bad = graph()
        bad["rawcode"] = "AOsw"
        with self.assertRaisesRegex(pkg.PackageError, "graph rawcode"):
            pkg.build_package(lookup(), graph=bad)
        bad = presentation()
        bad["rawcode"] = "AOsw"
        with self.assertRaisesRegex(pkg.PackageError, "presentation rawcode"):
            pkg.build_package(lookup(), presentation=bad)

    def test_wrong_executable_hash_is_rejected(self):
        bad = graph()
        bad["executable_sha256"] = "0" * 64
        with self.assertRaisesRegex(pkg.PackageError, "hash"):
            pkg.build_package(lookup(), graph=bad)
        bad = lookup()
        bad["executable_identity"]["sha256"] = "nonsha"
        with self.assertRaisesRegex(pkg.PackageError, "malformed"):
            pkg.build_package(bad)

    def test_presentation_edition_and_presence_mismatch_fails_closed(self):
        bad = presentation()
        del bad["editions"]["roc"]
        with self.assertRaisesRegex(pkg.PackageError, "editions"):
            pkg.build_package(lookup(), presentation=bad)
        bad = presentation()
        bad["editions"]["tft"]["found"] = False
        with self.assertRaisesRegex(pkg.PackageError, "disagree"):
            pkg.build_package(lookup(), presentation=bad)

    def test_unsupported_runtime_claims_cannot_be_laundered_into_static_report(self):
        bad = graph()
        bad["claims"]["runtime_reachability_proven"] = True
        with self.assertRaisesRegex(pkg.PackageError, "unexpectedly asserts"):
            pkg.build_package(lookup(), graph=bad)
        bad = presentation()
        bad["runtime_effect_timing_verified"] = True
        with self.assertRaisesRegex(pkg.PackageError, "unsupported runtime"):
            pkg.build_package(lookup(), presentation=bad)

    def test_duplicate_function_and_bad_edge_rejected(self):
        bad = graph()
        bad["nodes"].append(copy.deepcopy(bad["nodes"][0]))
        with self.assertRaisesRegex(pkg.PackageError, "duplicate"):
            pkg.build_package(lookup(), graph=bad)
        bad = graph()
        bad["edges"][0]["from"] = "0x12345678"
        with self.assertRaisesRegex(pkg.PackageError, "edge"):
            pkg.build_package(lookup(), graph=bad)

    def test_success_and_failure_pseudocode_written_with_traceable_source(self):
        doc = pkg.build_package(lookup(), graph=graph(), presentation=presentation())
        path = self.root / "complete"
        pkg.write_package(doc, path)
        text = (path / "native" / "decompiled.c").read_text()
        self.assertIn("NOT original Blizzard source", text)
        self.assertIn("Function RVA " + RVA, text)
        self.assertIn("cached/detail/decompiled.jsonl:1", text)
        self.assertNotIn("Function RVA " + OTHER, text)
        self.assertIn("not a", (path / "report.md").read_text().lower())
        with self.assertRaisesRegex(pkg.PackageError, "existing"):
            pkg.write_package(doc, path)

    def test_determinism_and_provenance_change_tracking(self):
        first = pkg.build_package(lookup(), graph=graph(), presentation=presentation())
        second = pkg.build_package(lookup(), graph=graph(), presentation=presentation())
        self.assertEqual(first, second)
        one = self.root / "one"
        two = self.root / "two"
        pkg.write_package(first, one)
        pkg.write_package(second, two)
        for name in ("report.md", "coverage.json", "questions.json", "native/decompiled.c"):
            self.assertEqual((one / name).read_bytes(), (two / name).read_bytes())
        altered = presentation()
        altered["editions"]["tft"]["references"].append({"field": "MissileArt"})
        changed = pkg.build_package(lookup(), graph=graph(), presentation=altered)
        self.assertNotEqual(changed["provenance"]["input_digests"]["presentation"],
                            first["provenance"]["input_digests"]["presentation"])

    def test_cached_graph_roundtrip_and_cli_without_tools(self):
        look = self.root / "lookup.json"
        look.write_text(json.dumps(lookup()))
        gpath = self.root / "graph"
        graph_io.write_graph(graph(), gpath)
        ppath = self.root / "presentation"
        presentation_io.write_presentation(presentation(), ppath)
        result = self.root / "report"
        rc = cli.main(["ability-package", "--lookup", str(look), "--graph", str(gpath),
                       "--presentation", str(ppath), "--output", str(result)])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads((result / "coverage.json").read_text())["metrics"]["decompiled_complete"], 1)
        self.assertEqual(json.loads((result / "questions.json").read_text())["rawcode"], "Apxf")
        self.assertFalse((result / "native" / "ability.c").exists())
        self.assertEqual(cli.main(["ability-package", "--lookup", str(look), "--graph", str(gpath),
                                   "--output", str(result)]), 1)

    def test_missing_or_malformed_graph_sidecar_does_not_create_report(self):
        look = self.root / "lookup.json"
        look.write_text(json.dumps(lookup()))
        gpath = self.root / "graph"
        graph_io.write_graph(graph(), gpath)
        (gpath / "native-code.json").unlink()
        output = self.root / "invalid"
        self.assertEqual(cli.main(["ability-package", "--lookup", str(look), "--graph", str(gpath),
                                   "--output", str(output)]), 1)
        self.assertFalse(output.exists())

    def test_reconstruct_integration_generates_offline_bundle(self):
        with mock.patch.object(cli, "resolve", return_value=lookup()):
            result = self.root / "reconstructed"
            self.assertEqual(cli.main(["reconstruct", "Apxf", "--no-asset-inspection",
                                       "--output-dir", str(result)]), 0)
        manifest = json.loads((result / "manifest.json").read_text())
        self.assertIn("offline_report_generation", manifest["completed_stages"])
        self.assertEqual(manifest["status"], "seed_only")
        self.assertEqual(manifest["sources"]["offline_report"], "offline/report.md")
        self.assertTrue((result / "offline" / "report.md").exists())


if __name__ == "__main__":
    unittest.main()
