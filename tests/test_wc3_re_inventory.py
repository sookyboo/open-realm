"""Offline, standard-library-only inventory validation regression tests."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.wc3_re import inventory as inv  # noqa: E402


def fixture() -> dict:
    base = 0x400000

    def address(rva: int, kind: str | None = "function_va") -> dict:
        addr = {"va": f"0x{base + rva:08X}", "rva": f"0x{rva:08X}"}
        if kind is not None:
            addr["kind"] = kind
        return addr

    return {
        "schema_version": 1,
        "executable": {"sha256": "a" * 64, "module": "Warcraft III.exe",
                       "architecture": "PE32 x86", "preferred_image_base": "0x00400000"},
        "functions": [{"id": "fn_00001000", "label": "Example callback", "category": "targeting",
                       "record_kind": "function", "status": "observed", "confidence": "high",
                       "addresses": [address(0x1000)], "object_offsets": ["+0x120: callback slot"],
                       "related_addresses": [address(0x2000, None)],
                       "source": {"document": "docs/probe.md", "section": "Trace"},
                       "evidence_summary": "Preserve this text as evidence"}],
        "verified_relationships": [{"from": address(0x1000, None),
                                     "to": address(0x2000, None), "kind": "call",
                                     "context": "Call site reached; mode not classified",
                                     "confidence": "medium", "source": {"document": "docs/probe.md"}}],
        "relationship_kinds": {"call": "Dispatch classification not established"},
        "entry_count": 1,
        "verified_relationship_count": 1,
    }


class InventoryTest(unittest.TestCase):
    def test_legacy_data_loads_without_inventing_dispatch(self):
        data = fixture()
        result = inv.validate_inventory(data)
        self.assertTrue(result["valid"], result["issues"])
        self.assertEqual(result["statistics"]["untyped_addresses"], 3)
        self.assertEqual(result["statistics"]["unclassified_call_edges"], 1)
        normalized = inv.normalize_inventory(data)
        self.assertEqual(normalized["verified_relationships"][0]["kind"], "call")
        self.assertEqual(normalized["verified_relationships"][0]["from"]["kind"], "untyped_va")
        self.assertEqual(normalized["functions"][0]["related_addresses"][0]["kind"], "untyped_va")
        self.assertEqual(normalized["functions"][0]["evidence_summary"], "Preserve this text as evidence")
        self.assertNotIn("kind", data["verified_relationships"][0]["from"])
        self.assertEqual(inv.normalize_inventory(normalized), normalized)

    def test_detects_bad_va_rva_and_does_not_autofix(self):
        data = fixture()
        data["functions"][0]["addresses"][0]["rva"] = "0x00003000"
        report = inv.validate_inventory(data)
        self.assertFalse(report["valid"])
        self.assertIn("va_rva_mismatch", [e["code"] for e in report["issues"]])
        with self.assertRaises(inv.InventoryError):
            inv.normalize_inventory(data)

    def test_constant_is_not_code_and_must_not_carry_rva(self):
        data = fixture()
        data["functions"][0]["related_addresses"].append(
            {"kind": "constant", "value": "0x2B61676C"})
        self.assertTrue(inv.validate_inventory(data)["valid"])
        normalized = inv.normalize_inventory(data)
        self.assertEqual(normalized["functions"][0]["related_addresses"][-1],
                         {"kind": "constant", "value": "0x2b61676c"})
        bad = deepcopy(data)
        bad["functions"][0]["related_addresses"][-1]["rva"] = "0x2b21676c"
        self.assertIn("constant_as_address", [e["code"] for e in inv.validate_inventory(bad)["issues"]])

    def test_constant_is_never_a_graph_node(self):
        data = fixture()
        data["verified_relationships"][0]["to"] = {"kind": "constant", "value": "0x2b61676c"}
        self.assertIn("constant_as_graph_endpoint",
                      [e["code"] for e in inv.validate_inventory(data)["issues"]])
        data = fixture()
        data["functions"][0]["addresses"].append({"kind": "constant", "value": "0x2b61676c"})
        self.assertIn("constant_as_function_entry",
                      [e["code"] for e in inv.validate_inventory(data)["issues"]])

    def test_rejects_unknown_and_undeclared_relationships(self):
        data = fixture()
        del data["relationship_kinds"]["call"]
        self.assertIn("invalid_relationship_kind", [e["code"] for e in inv.validate_inventory(data)["issues"]])
        data["relationship_kinds"]["call"] = "unclassified"
        data["verified_relationships"][0]["kind"] = "suspicious_dispatch"
        data["relationship_kinds"]["suspicious_dispatch"] = "bad"
        self.assertIn("invalid_relationship_kind", [e["code"] for e in inv.validate_inventory(data)["issues"]])

    def test_distinct_evidence_records_for_same_edge_are_kept(self):
        data = fixture()
        twin = deepcopy(data["verified_relationships"][0])
        twin["context"] = "Independent second evidence report"
        twin["source"]["document"] = "docs/second.md"
        data["verified_relationships"].append(twin)
        data["verified_relationship_count"] = 2
        report = inv.validate_inventory(data)
        self.assertTrue(report["valid"])
        self.assertEqual(report["statistics"]["repeated_edge_groups"], 1)
        normalized = inv.normalize_inventory(data)
        self.assertEqual(len(normalized["verified_relationships"]), 2)
        self.assertNotEqual(normalized["verified_relationships"][0]["source"],
                            normalized["verified_relationships"][1]["source"])

    def test_mentioned_addresses_do_not_create_call_edges(self):
        data = fixture()
        data["verified_relationships"] = []
        data["verified_relationship_count"] = 0
        normalized = inv.normalize_inventory(data)
        self.assertEqual(normalized["verified_relationships"], [])
        self.assertEqual(len(normalized["functions"][0]["related_addresses"]), 1)

    def test_opaque_offset_descriptions_are_preserved(self):
        data = fixture()
        data["functions"][0]["object_offsets"].append(
            "+0x228/+0x22C/+0x230: three distinct candidate gates")
        self.assertTrue(inv.validate_inventory(data)["valid"])
        self.assertEqual(inv.normalize_inventory(data)["functions"][0]["object_offsets"],
                         data["functions"][0]["object_offsets"])

    def test_stale_counts_and_duplicate_record_ids_fail(self):
        data = fixture()
        data["entry_count"] = 2
        self.assertIn("stale_count", [e["code"] for e in inv.validate_inventory(data)["issues"]])
        data["entry_count"] = 1
        data["functions"].append(deepcopy(data["functions"][0]))
        data["entry_count"] = 2
        self.assertIn("duplicate_id", [e["code"] for e in inv.validate_inventory(data)["issues"]])

    def test_schema_enums_match_validator(self):
        schema = json.loads(inv.SCHEMA_FILE.read_text(encoding="utf-8"))
        definitions = schema["$defs"]
        self.assertEqual(set(definitions["address"]["properties"]["kind"]["enum"]),
                         inv.ADDRESS_KINDS)
        self.assertEqual(set(definitions["relationship"]["properties"]["kind"]["enum"]),
                         inv.RELATIONSHIP_KINDS)

    def test_malformed_enum_types_report_errors_not_exceptions(self):
        data = fixture()
        data["functions"][0]["status"] = ["observed"]
        data["functions"][0]["addresses"][0]["kind"] = {"bogus": "kind"}
        data["verified_relationships"][0]["kind"] = ["direct_call"]
        self.assertFalse(inv.validate_inventory(data)["valid"])

    def test_cli_json_report_and_normalized_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, output = root / "source.json", root / "normalized.json"
            source.write_text(json.dumps(fixture()), encoding="utf-8")
            with mock.patch("sys.stdout"):
                self.assertEqual(inv.main([str(source), "--format", "json",
                                           "--normalized-output", str(output)]), 0)
            self.assertTrue(output.is_file())
            self.assertEqual(inv.validate_inventory(json.loads(output.read_text()))["valid"], True)
            self.assertEqual(json.loads(source.read_text()), fixture())
            with mock.patch("sys.stderr"):
                self.assertEqual(inv.main([str(source), "--normalized-output", str(source)]), 2)
            with mock.patch("sys.stdout"):
                self.assertEqual(inv.main([str(source), "--strict"]), 1)

    def test_bundled_inventory_when_available(self):
        if not inv.DEFAULT_INVENTORY.is_file():
            self.skipTest("Retail investigation inventory not present in this checkout")
        data = json.loads(inv.DEFAULT_INVENTORY.read_text(encoding="utf-8"))
        report = inv.validate_inventory(data)
        self.assertTrue(report["valid"], report["issues"])
        normalized = inv.normalize_inventory(data)
        self.assertEqual(len(normalized["functions"]), len(data["functions"]))
        self.assertEqual(len(normalized["verified_relationships"]),
                         len(data["verified_relationships"]))
        self.assertEqual(data["functions"][0]["evidence_summary"],
                         normalized["functions"][0]["evidence_summary"])
        self.assertEqual(len({r["kind"] for r in normalized["verified_relationships"]}
                             - inv.RELATIONSHIP_KINDS), 0)


if __name__ == "__main__":
    unittest.main()
