"""Tests for Retail JASS probe preparation and result capture."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("wc3_retail_probe", ROOT / "tools/wc3_retail_probe.py")
PROBE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(PROBE)


class ScriptEditTest(unittest.TestCase):
    def test_scoped_edits_preserve_crlf_and_insert_at_line_boundaries(self):
        source = (
            "globals\r\nendglobals\r\n"
            "function ProbeStart takes nothing returns nothing\r\n"
            "endfunction\r\n"
            "function Init takes nothing returns nothing\r\n"
            "    call StartGameplay()\r\n"
            "endfunction\r\n"
        )
        result = PROBE.apply_edits(source, [
            {
                "function": "Init",
                "anchor": "function Init takes nothing returns nothing",
                "where": "before",
                "text": "function ProbeHelper takes nothing returns nothing\nendfunction",
            },
            {
                "function": "Init",
                "anchor": "call StartGameplay()",
                "where": "after",
                "text": "call ProbeStart()",
            },
        ], Path("."))
        self.assertIn(
            "function ProbeHelper takes nothing returns nothing\r\nendfunction\r\n"
            "function Init takes nothing returns nothing\r\n",
            result,
        )
        self.assertIn("    call StartGameplay()\r\ncall ProbeStart()\r\nendfunction", result)
        self.assertNotIn("\n", result.replace("\r\n", ""))

    def test_duplicate_or_missing_anchor_fails_closed(self):
        source = (
            "function Init takes nothing returns nothing\n"
            "    call StartGameplay()\n"
            "    call StartGameplay()\n"
            "endfunction\n"
        )
        edit = {
            "function": "Init",
            "anchor": "call StartGameplay()",
            "where": "after",
            "text": "call ProbeStart()",
        }
        with self.assertRaisesRegex(PROBE.ProbeError, "found 2"):
            PROBE.apply_edits(source, [edit], Path("."))
        edit["anchor"] = "call MissingAnchor()"
        with self.assertRaisesRegex(PROBE.ProbeError, "found 0"):
            PROBE.apply_edits(source, [edit], Path("."))

    def test_function_must_be_unique(self):
        source = "function Init takes nothing returns nothing\nendfunction\n"
        with self.assertRaisesRegex(PROBE.ProbeError, "expected one function declaration"):
            PROBE.apply_edits(source, [{
                "function": "Absent",
                "anchor": "endfunction",
                "where": "before",
                "text": "call ProbeStart()",
            }], Path("."))


class CaptureTest(unittest.TestCase):
    def write_probe(self, directory: Path, result: Path, prepared_at_ns: int,
                    baseline: dict[str, object]) -> None:
        record = {
            "id": "fixture-probe",
            "prepared_at_ns": prepared_at_ns,
            "result_file": str(result),
            "result_before_prepare": baseline,
        }
        (directory / "probe.json").write_text(json.dumps(record), encoding="utf-8")

    def test_capture_saves_fresh_preload_text_and_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "probe"
            directory.mkdir()
            result = Path(tmp) / "Preload\u0020Output.txt"
            result.write_text("stale output", encoding="utf-8")
            baseline = PROBE.snapshot_result(result)
            prepared_at = time.time_ns() - 2_000_000_000
            result.write_text(
                'function PreloadFiles takes nothing returns nothing\n'
                'call Preload( "PROBE owner=0 escaped=\\"yes\\"" )\n'
                'call PreloadEnd( 0.0 )\nendfunction\n',
                encoding="utf-8",
            )
            self.write_probe(directory, result, prepared_at, baseline)

            PROBE.capture(SimpleNamespace(probe_dir=directory, timeout=1.0, poll_interval=0.01))

            self.assertEqual((directory / "result.txt").read_bytes(), result.read_bytes())
            report = json.loads((directory / "capture.json").read_text(encoding="utf-8"))
            self.assertEqual(report["preload_values"], ['PROBE owner=0 escaped="yes"'])
            self.assertIn("Not inferred", report["interpretation"])

    def test_capture_rejects_stale_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "probe"
            directory.mkdir()
            result = Path(tmp) / "result.txt"
            result.write_text("old", encoding="utf-8")
            baseline = PROBE.snapshot_result(result)
            self.write_probe(directory, result, time.time_ns() + 1_000_000_000, baseline)
            with self.assertRaisesRegex(PROBE.ProbeError, "no fresh non-empty result"):
                PROBE.capture(SimpleNamespace(probe_dir=directory, timeout=0.02,
                                              poll_interval=0.005))


if __name__ == "__main__":
    unittest.main()
