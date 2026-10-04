"""Tests for Retail JASS probe preparation and result capture."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import time
import unittest
from unittest import mock
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

    def test_global_declarations_insert_inside_existing_block(self):
        source = (
            "globals\n"
            "    integer udg_existing = 0\n"
            "endglobals\n"
            "function Init takes nothing returns nothing\n"
            "endfunction\n"
        )
        result = PROBE.apply_edits(source, [{
            "block": "globals",
            "anchor": "integer udg_existing = 0",
            "where": "after",
            "text": "unit gg_probe_caster = null",
        }], Path("."))
        self.assertEqual(len(PROBE.re.findall(r"(?m)^globals$", result)), 1)
        self.assertIn("integer udg_existing = 0\nunit gg_probe_caster = null\nendglobals", result)

    def test_second_globals_block_is_rejected(self):
        source = (
            "globals\nendglobals\n"
            "function Init takes nothing returns nothing\n"
            "endfunction\n"
        )
        with self.assertRaisesRegex(PROBE.ProbeError, "never inject a second"):
            PROBE.apply_edits(source, [{
                "function": "Init",
                "anchor": "function Init takes nothing returns nothing",
                "where": "before",
                "text": "globals\n    integer gg_bad = 0\nendglobals",
            }], Path("."))

    def test_globals_block_after_functions_is_rejected(self):
        source = (
            "function Init takes nothing returns nothing\n"
            "endfunction\n"
            "globals\nendglobals\n"
        )
        with self.assertRaisesRegex(PROBE.ProbeError, "appears after a function"):
            PROBE.validate_jass_layout(source)

    def test_preload_result_filename_must_match_manifest(self):
        script = 'call PreloadGenEnd("expected.txt")\n'
        names = PROBE.validate_result_filename(script, Path("/tmp/expected.txt"))
        self.assertEqual(names, ["expected.txt"])
        with self.assertRaisesRegex(PROBE.ProbeError, "does not match"):
            PROBE.validate_result_filename(script, Path("/tmp/other.txt"))


class CaptureTest(unittest.TestCase):
    def write_probe(self, directory: Path, result: Path, prepared_at_ns: int,
                    baseline: dict[str, object]) -> None:
        record = {
            "id": "fixture-probe",
            "prepared_at_ns": prepared_at_ns,
            "result_file": str(result),
            "result_before_prepare": baseline,
            "capture_contract": {},
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
            self.assertIn("not a gameplay pass/fail judgment", report["interpretation"])
            self.assertEqual(report["status"], "unclassified")

    def test_capture_marks_rejected_order_inconclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "probe"
            directory.mkdir()
            result = Path(tmp) / "result.txt"
            prepared_at = time.time_ns() - 2_000_000_000
            result.write_text(
                'call Preload( "SERPENTWARD_CAST probe=ward-test accepted=false" )\n',
                encoding="utf-8",
            )
            self.write_probe(directory, result, prepared_at, {"exists": False})
            probe = json.loads((directory / "probe.json").read_text(encoding="utf-8"))
            probe["capture_contract"] = {
                "required_markers": ["probe=ward-test"],
                "inconclusive_markers": ["accepted=false"],
            }
            (directory / "probe.json").write_text(json.dumps(probe), encoding="utf-8")

            PROBE.capture(SimpleNamespace(probe_dir=directory, timeout=1.0, poll_interval=0.01))

            report = json.loads((directory / "capture.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "inconclusive")
            self.assertEqual(report["found_inconclusive_markers"], ["accepted=false"])
            self.assertTrue(any("failed setup or rejected action" in reason
                                for reason in report["status_reasons"]))

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

    def test_capture_requires_a_prepared_map_launch_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "probe"
            directory.mkdir()
            result = Path(tmp) / "result.txt"
            result.write_text('call Preload("PROBE ready=1")\n', encoding="utf-8")
            self.write_probe(directory, result, time.time_ns() - 1_000_000,
                             {"exists": False})
            record = json.loads((directory / "probe.json").read_text(encoding="utf-8"))
            record["retail_executable"] = "/unused/retail.exe"
            (directory / "probe.json").write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaisesRegex(PROBE.ProbeError, "no Retail launch record"):
                PROBE.capture(SimpleNamespace(probe_dir=directory, timeout=0.02,
                                              poll_interval=0.005))


class LaunchTest(unittest.TestCase):
    def test_launch_converts_prepared_map_and_records_required_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "probe"
            directory.mkdir()
            executable = Path(tmp) / "Warcraft III.exe"
            executable.write_bytes(b"retail executable fixture")
            control = directory / "control.w3x"
            prepared = directory / "prepared.w3x"
            control.write_bytes(b"control map")
            prepared.write_bytes(b"prepared map")
            record = {
                "id": "launch-fixture",
                "retail_executable": str(executable),
                "retail_executable_sha256": PROBE.sha256_file(executable),
                "control_map": str(control),
                "control_map_sha256": PROBE.sha256_file(control),
                "prepared_map": str(prepared),
                "prepared_map_sha256": PROBE.sha256_file(prepared),
            }
            (directory / "probe.json").write_text(json.dumps(record), encoding="utf-8")
            args = SimpleNamespace(probe_dir=directory, control=False, wine="wine-fixture",
                                   winepath="winepath-fixture", wine_prefix=None)
            with mock.patch.object(PROBE, "run", return_value=SimpleNamespace(
                    stdout=b"Z:\\tmp\\probe\\prepared.w3x\r\n")) as path_call, \
                 mock.patch.object(PROBE.subprocess, "Popen",
                                   return_value=SimpleNamespace(pid=4321)) as popen:
                PROBE.launch(args)

            path_call.assert_called_once()
            self.assertEqual(path_call.call_args.args[0],
                             ["winepath-fixture", "-w", str(prepared)])
            command = popen.call_args.args[0]
            self.assertEqual(command, ["wine-fixture", str(executable), "-window",
                                       "-graphicsapi", "OpenGL2", "-loadfile",
                                       "Z:\\tmp\\probe\\prepared.w3x"])
            launch_record = json.loads((directory / "launch.json").read_text(encoding="utf-8"))
            self.assertEqual(launch_record["role"], "prepared")
            self.assertEqual(launch_record["map_sha256"], record["prepared_map_sha256"])
            self.assertTrue(launch_record["manual_map_confirmation_required"])


if __name__ == "__main__":
    unittest.main()
