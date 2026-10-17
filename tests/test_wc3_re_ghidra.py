"""Offline Ghidra adapter tests. No Ghidra, executable, MPQ or Wine required."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from wc3_re import ghidra
import wc3_ability_re as cli

SHA = "3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed"


def fixture_export(directory: Path, mode: str = "scan", counts: dict | None = None) -> None:
    actual = {kind: 0 for kind in ghidra.KINDS}
    actual["functions"] = 1
    if counts is not None:
        actual.update(counts)
    for kind, size in actual.items():
        with (directory / (kind + ".jsonl")).open("w") as output:
            for index in range(size):
                output.write(json.dumps({"rva": f"0x{index + 0x80d820:08x}", "kind": kind}) + "\n")
    (directory / "export-summary.json").write_text(json.dumps({
        "schema_version": 1, "status": "complete", "mode": mode,
        "executable_sha256": SHA, "image_base": "0x00400000",
        "architecture": "x86:LE:32", "counts": actual,
    }))


class AddressesAndSeeds(unittest.TestCase):
    def test_rva_is_hex_not_va_or_constant(self):
        self.assertEqual(ghidra.rva("0x0080d820"), 0x80D820)
        self.assertEqual(ghidra.rva("0080D820"), 0x80D820)
        for invalid in ("-100", "xyz", "0x000000001", "0xffffffff", "", "0x--123"):
            with self.subTest(invalid=invalid), self.assertRaises(ghidra.GhidraError):
                ghidra.rva(invalid)

    def test_inventory_seeds_only_explicitly_typed_entry_addresses(self):
        funcs, tables = ghidra._inventory_seeds(ghidra.INVENTORY)
        self.assertIn(0x0006B3C0, funcs)
        self.assertIn(0x00A9BC30, tables)
        self.assertNotIn(0x2B21676C, funcs)  # old constant-as-VA error
        self.assertTrue(all(number < 0xFC000000 for number in funcs + tables))
        self.assertEqual(len(funcs), len(set(funcs)))

    def test_normalizer_does_not_promote_legacy_address_or_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = json.loads(ghidra.INVENTORY.read_text())
            source["functions"][0]["related_addresses"].append({
                "va": "0x00C00000", "rva": "0x00800000"})
            path = Path(tmp) / "inventory.json"
            path.write_text(json.dumps(source))
            funcs, tables = ghidra._inventory_seeds(path)
            self.assertNotIn(0x00800000, funcs)
            self.assertNotIn(0x00800000, tables)


class ExportCommands(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.exe = self.root / "Warcraft III.exe"
        self.exe.write_bytes(b"dummy")
        self.headless = self.root / "analyzeHeadless"
        self.headless.write_text("dummy")

    def test_initial_import_and_incremental_process_are_distinct(self):
        common = dict(headless=self.headless, project_dir=self.root, project_name="WC3Retail",
                      executable=self.exe, output=self.root / "out", identity={"sha256": SHA},
                      mode="detail", seed_rvas=[0x80D820], vtable_rvas=[], timeout=60,
                      vtable_slots=128)
        first = ghidra.make_command(**common, first_import=True)
        self.assertIn("-import", first)
        self.assertNotIn("-noanalysis", first)
        self.assertIn("Wc3AbilityExport.java", first)
        self.assertIn("0x0080d820", first)
        reuse = ghidra.make_command(**common, first_import=False)
        self.assertIn("-process", reuse)
        self.assertIn("-readOnly", reuse)
        self.assertIn("-noanalysis", reuse)

    def test_detail_requires_seeds_and_scan_requires_none(self):
        opts = dict(headless=self.headless, project_dir=self.root, project_name="WC3Retail",
                    executable=self.exe, output=self.root / "out", identity={"sha256": SHA},
                    mode="detail", seed_rvas=[], vtable_rvas=[], first_import=False,
                    timeout=60, vtable_slots=128)
        with self.assertRaisesRegex(ghidra.GhidraError, "needs"):
            ghidra.make_command(**opts)
        opts["mode"] = "scan"
        opts["seed_rvas"] = [0x80D820]
        with mock.patch.object(ghidra, "check_executable", return_value={"checked": True}):
            with mock.patch.object(ghidra, "load_inventory_identity", return_value={"sha256": SHA}):
                with self.assertRaisesRegex(ghidra.GhidraError, "scan exports"):
                    ghidra.export(headless=self.headless, project_dir=self.root,
                                  project_name="WC3Retail", executable=self.exe,
                                  output=self.root / "out", mode="scan", rvas=["0x80d820"])

    def test_rejects_unverified_executable_before_launch(self):
        with self.assertRaisesRegex(ghidra.GhidraError, "SHA-256 differs"):
            ghidra.export(headless=self.headless, project_dir=self.root,
                          project_name="WC3Retail", executable=self.exe,
                          output=self.root / "out")
        self.assertFalse((self.root / "out").exists())

    def test_launch_records_provenance_and_validates_output(self):
        def fake_run(command, **kwargs):
            self.assertIn("-readOnly", command)
            self.assertIn("-noanalysis", command)
            fixture_export(self.root / "out")
            return subprocess.CompletedProcess(command, 0)
        with mock.patch.object(ghidra, "check_executable", return_value={"checked": True}):
            with mock.patch.object(ghidra.subprocess, "run", side_effect=fake_run):
                result = ghidra.export(headless=self.headless, project_dir=self.root,
                                       project_name="WC3Retail", executable=self.exe,
                                       output=self.root / "out")
        self.assertEqual(result["counts"]["functions"], 1)
        saved = json.loads((self.root / "out" / "invocation.json").read_text())
        self.assertEqual(saved["binary_sha256"], SHA)
        self.assertIn("-postScript", saved["command"])

    def test_no_completed_summary_on_failed_ghidra(self):
        with mock.patch.object(ghidra, "check_executable", return_value={"checked": True}):
            with mock.patch.object(ghidra.subprocess, "run", return_value=subprocess.CompletedProcess([], 7)):
                with self.assertRaisesRegex(ghidra.GhidraError, "returned 7"):
                    ghidra.export(headless=self.headless, project_dir=self.root,
                                  project_name="WC3Retail", executable=self.exe,
                                  output=self.root / "out")
        self.assertTrue((self.root / "out" / "invocation.json").exists())
        self.assertFalse((self.root / "out" / "export-summary.json").exists())

    def test_existing_project_not_overwritten_by_first_import(self):
        (self.root / "WC3Retail.gpr").touch()
        with self.assertRaisesRegex(ghidra.GhidraError, "existing project"):
            ghidra.make_command(headless=self.headless, project_dir=self.root,
                                project_name="WC3Retail", executable=self.exe,
                                output=self.root / "out", identity={"sha256": SHA},
                                mode="scan", seed_rvas=[], vtable_rvas=[],
                                first_import=True, timeout=60, vtable_slots=128)


class ExportValidation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        fixture_export(self.directory)

    def test_completed_scan_is_accepted(self):
        result = ghidra.validate_export(self.directory, SHA, "scan")
        self.assertEqual(result["status"], "complete")

    def test_binary_identity_and_mode_fails_closed(self):
        with self.assertRaisesRegex(ghidra.GhidraError, "mismatch"):
            ghidra.validate_export(self.directory, "a" * 64, "scan")
        with self.assertRaisesRegex(ghidra.GhidraError, "mismatch"):
            ghidra.validate_export(self.directory, SHA, "detail")

    def test_missing_jsonl_or_truncated_file_is_rejected(self):
        (self.directory / "functions.jsonl").unlink()
        with self.assertRaisesRegex(ghidra.GhidraError, "missing"):
            ghidra.validate_export(self.directory, SHA, "scan")
        (self.directory / "functions.jsonl").write_text('{"rva":"0x00000001"}\nBAD\n')
        with self.assertRaisesRegex(ghidra.GhidraError, "bad functions row"):
            ghidra.validate_export(self.directory, SHA, "scan")

    def test_counts_must_match(self):
        (self.directory / "functions.jsonl").write_text('')
        with self.assertRaisesRegex(ghidra.GhidraError, "count differs"):
            ghidra.validate_export(self.directory, SHA, "scan")

    def test_zero_function_scan_rejected(self):
        fixture_export(self.directory, counts={"functions": 0})
        with self.assertRaisesRegex(ghidra.GhidraError, "no functions"):
            ghidra.validate_export(self.directory, SHA, "scan")

    def test_cli_has_ghidra_command_without_claiming_full_reconstruction(self):
        parser = cli.build_parser()
        opts = parser.parse_args(["ghidra-export", "--headless", "/tmp/headless",
                                  "--project-dir", "/tmp", "--project-name", "WC3Retail",
                                  "--executable", "/tmp/Retail.exe", "--output", "/tmp/export",
                                  "--mode", "detail", "--rva", "0x0080d820"])
        self.assertEqual(opts.mode, "detail")
        self.assertEqual(opts.rva, ["0x0080d820"])
        self.assertEqual(parser.parse_args(["reconstruct", "Apxf"]).rawcode, "Apxf")


if __name__ == "__main__":
    unittest.main()
