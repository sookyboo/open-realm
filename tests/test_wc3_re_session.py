"""Offline session coordination contracts; no Retail, Wine or Frida installation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from wc3_re import frida, session
import wc3_ability_re as cli

SHA = "3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed"


def graph():
    return {"schema_version": 1, "rawcode": "Apxf", "status": "static_candidate_graph",
            "executable_sha256": SHA,
            "claims": {"runtime_reachability_proven": False},
            "seeds": [{"rva": "0x0080d820"}],
            "nodes": [{"rva": "0x0080d820", "name": "PhoenixFire", "depth": 0, "unresolved_calls": []}],
            "edges": []}


class FakeScript:
    def __init__(self, owner, source):
        self.owner = owner
        self.source = source
        self.message = None
        self.armed = False
        self.stopped = False
        self.run_id = None
        self.sent_result = False
        self.exports_sync = self

    def on(self, name, handler):
        assert name == "message"
        self.message = handler

    def load(self):
        self.message({"type": "send", "payload": {"source": "wc3_ability_re_frida",
                      "kind": "start", "capture_id": "capture", "rawcode": "Apxf"}}, None)

    def setrunid(self, name):
        self.run_id = name
        return True

    def arm(self):
        self.armed = True
        return True

    def status(self):
        if self.armed and not self.sent_result:
            self.sent_result = True
            self.owner.cases_seen.append(self.run_id)
            if not self.owner.skip_result:
                # Guarantee a fresh mtime after the arm snapshot on timestamp-precise filesystems.
                time.sleep(0.004)
                self.owner.results[self.run_id].write_text(
                    f'call Preload("SESSION_START run_id={self.run_id}")\n'
                    'call Preload("setup_failed=false")\n'
                    'call Preload("accepted=true")\n'
                    f'call Preload("SESSION_DONE run_id={self.run_id}")\n', encoding='utf-8')
            event = {"source": "wc3_ability_re_frida", "function_rva": "0x0080d820",
                     "run_id": self.run_id, "capture_id": "capture", "rawcode": "Apxf",
                     "thread_id": 1, "invocation_id": 1}
            self.message({"type": "send", "payload": {**event, "kind": "enter"}}, None)
            self.message({"type": "send", "payload": {**event, "kind": "leave",
                          "return_value_raw": "0x0"}}, None)
        return {"armed": self.armed, "stopped": self.stopped}

    def disarm(self):
        self.armed = False
        return {"emitted": 1}

    def unload(self):
        self.owner.scripts_unloaded += 1


class FakeAttached:
    def __init__(self, owner):
        self.owner = owner

    def create_script(self, js):
        self.owner.agent_sources.append(js)
        return FakeScript(self.owner, js)

    def detach(self):
        self.owner.detached += 1


class FakeDevice:
    def __init__(self, pid, results):
        self.pid = pid
        self.results = results
        self.attached = 0
        self.detached = 0
        self.scripts_unloaded = 0
        self.agent_sources = []
        self.cases_seen = []
        self.skip_result = False

    def enumerate_processes(self):
        return [SimpleNamespace(pid=self.pid, name="Warcraft III.exe")]

    def attach(self, pid):
        assert pid == self.pid
        self.attached += 1
        return FakeAttached(self)


class SessionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.plan_dir = self.root / "plan"
        self.probe_dir = self.root / "probe"
        self.probe_dir.mkdir()
        self.plan = frida.plan(graph(), capture_id="capture", seconds=5)
        frida.write_trace(self.plan, self.plan_dir)
        game = self.root / "Warcraft III.exe"
        game.write_bytes(b"safe offline fixture")
        game_sha = session.digest(game)
        # Fixture identities use a matching synthetic SHA throughout.
        self.plan["executable_sha256"] = game_sha
        frida_agent = frida._agent_source(self.plan)
        (self.plan_dir / "trace-plan.json").write_text(json.dumps(self.plan))
        (self.plan_dir / "agent.js").write_text(frida_agent)
        map_file = self.root / "probe.w3x"
        map_file.write_bytes(b"prepared map fixture")
        map_sha = session.digest(map_file)
        jhcr = self.root / "state.bin"
        jhcr.write_bytes(b"state")
        baseline = self.root / "baseline.j"
        baseline.write_text("function Probe takes nothing returns nothing\nendfunction")
        probe = {"id": "phoenix", "retail_executable": str(game),
                 "retail_executable_sha256": game_sha,
                 "prepared_map": str(map_file), "prepared_map_sha256": map_sha,
                 "jhcr": {"state": str(jhcr), "baseline_script": str(baseline)}}
        (self.probe_dir / "probe.json").write_text(json.dumps(probe))
        launch = {"probe_id": "phoenix", "role": "prepared", "map_sha256": map_sha,
                  "retail_executable_sha256": game_sha, "control_screen_confirmed": True,
                  "windows_map_path": "Z:\\probe.w3x", "launched_at_ns": time.time_ns(),
                  "wine_prefix": str(self.root / 'wine'),
                  "command": ["wine", str(game), "-window", "-graphicsapi", "OpenGL2",
                              "-loadfile", "Z:\\probe.w3x"]}
        (self.probe_dir / "launch.json").write_text(json.dumps(launch))
        self.results = {f"case-{i}": self.root / f"case-{i}.txt" for i in (1, 2)}
        self.cases_file = self.root / 'cases.json'
        self.cases = [{"run_id": run_id, "result_file": str(result),
                       "required_markers": ["accepted=true"], "timeout_seconds": 1}
                      for run_id, result in self.results.items()]
        self.cases_file.write_text(json.dumps({"cases": self.cases}))
        self.output = self.root / 'session'

    def create(self):
        return session.create(plan_dir=self.plan_dir, probe_dir=self.probe_dir,
                              cases_file=self.cases_file, output_dir=self.output)

    def test_session_creation_and_provenance(self):
        result = self.create()
        self.assertTrue(result["jhcr_prepared"])
        self.assertEqual(len(result["cases"]), 2)
        saved, plan, launch = session.inspect_session(self.output)
        self.assertEqual(saved["executable_sha256"], self.plan["executable_sha256"])
        self.assertEqual(plan["capture_id"], "capture")
        with self.assertRaisesRegex(session.SessionError, "already exists"):
            self.create()
        self.assertEqual(cli.main(["ability-session-check", "--session", str(self.output)]), 0)

    def test_mismatched_exe_and_map_refused(self):
        self.create()
        (self.root / "Warcraft III.exe").write_text("modified")
        with self.assertRaisesRegex(session.SessionError, "Retail executable"):
            session.inspect_session(self.output)

    def test_prepared_launch_and_jhcr_guards(self):
        record = session.load_json(self.probe_dir / "launch.json")
        record["control_screen_confirmed"] = False
        (self.probe_dir / "launch.json").write_text(json.dumps(record))
        with self.assertRaisesRegex(session.SessionError, "control/map"):
            self.create()

    def test_case_validation_unique_ids_files_and_timeout(self):
        invalid = [{**self.cases[0]}, {**self.cases[0], "run_id": "case-2"}]
        with self.assertRaisesRegex(session.SessionError, "reused JASS"):
            session._validate_cases({"cases": invalid}, max_seconds=5)
        invalid[1]["result_file"] = str(self.root / "new.txt")
        invalid[1]["timeout_seconds"] = 10
        with self.assertRaisesRegex(session.SessionError, "timeout_seconds"):
            session._validate_cases({"cases": invalid}, max_seconds=5)
        invalid[1]["timeout_seconds"] = 1
        invalid[1]["run_id"] = "../unsafe"
        with self.assertRaisesRegex(session.SessionError, "run_id"):
            session._validate_cases({"cases": invalid}, max_seconds=5)

    def test_result_requires_fresh_scoped_start_done(self):
        case = {**self.cases[0], "inconclusive_markers": []}
        file = self.results["case-1"]
        file.write_text('call Preload("SESSION_START run_id=case-10")\ncall Preload("SESSION_DONE run_id=case-10")\ncall Preload("accepted=true")')
        t0 = time.time_ns() - 1000000
        self.assertEqual(session._fresh_capture(file, None, t0, case)[0], "inconclusive")
        file.write_text('call Preload("SESSION_START run_id=case-1")\ncall Preload("setup_failed=false")\ncall Preload("accepted=true")\ncall Preload("SESSION_DONE run_id=case-1")')
        self.assertEqual(session._fresh_capture(file, None, t0, case)[0], 'ready_for_review')
        self.assertEqual(session._fresh_capture(file, None, time.time_ns() + 5000000, case)[0], None)
        file.write_text('call Preload("SESSION_DONE run_id=case-1")')
        self.assertEqual(session._fresh_capture(file, None, t0, case)[0], "inconclusive")

    def test_live_two_cases_one_attachment_no_restarts(self):
        self.create()
        fake = FakeDevice(9876, self.results)
        with mock.patch.object(session, "_host_process", return_value=9876):
            result = session.run(self.output, device=fake, poll_seconds=0.01)
        self.assertEqual(result["status"], "ready_for_review")
        self.assertEqual(fake.attached, 1)
        self.assertEqual(fake.detached, 1)
        self.assertEqual(fake.scripts_unloaded, 2)
        self.assertEqual(fake.cases_seen, ["case-1", "case-2"])
        self.assertTrue(all("let armed = false;" in js for js in fake.agent_sources))
        for run in ("case-1", "case-2"):
            self.assertTrue((self.output / run / "trace.jsonl").is_file())
            self.assertTrue((self.output / run / "result.txt").is_file())
        with mock.patch.object(session, "_host_process", return_value=9876), self.assertRaisesRegex(
                session.SessionError, "already has a run summary"):
            session.run(self.output, device=fake, poll_seconds=0.01)

    def test_timeout_stops_second_case_and_not_a_gameplay_pass(self):
        self.create()
        fake = FakeDevice(9876, self.results)
        fake.skip_result = True
        with mock.patch.object(session, "_host_process", return_value=9876):
            result = session.run(self.output, device=fake, poll_seconds=0.01)
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["cases"][0]["status"], "timeout")
        self.assertEqual(fake.scripts_unloaded, 1)
        self.assertFalse((self.output / "case-2").exists())

    def test_frida_process_must_match_host(self):
        with self.assertRaisesRegex(session.SessionError, "same-prefix Frida server"):
            session.select_frida_process(FakeDevice(8, {}), 7, proc_root=self.root)
        self.assertEqual(session.select_frida_process(FakeDevice(7, {}), 7)[1],
                         "matching_host_and_frida_pid")

    def test_live_attach_reports_missing_frida_api_clearly(self):
        with mock.patch.dict(sys.modules, {"frida": SimpleNamespace()}):
            with self.assertRaisesRegex(session.SessionError, "matching Frida Python environment"):
                session._get_device("127.0.0.1:27043")

    def test_host_process_requires_exact_map_and_wine_prefix(self):
        proc = self.root / "proc"
        for pid, suffix in (("100", "Z:\\probe.w3x"),
                            ("101", "Z:\\another.w3x")):
            location = proc / pid
            location.mkdir(parents=True)
            (location / "cmdline").write_bytes(
                ("Warcraft III.exe\0-window\0-graphicsapi\0OpenGL2\0-loadfile\0" +
                 suffix + "\0").encode())
            (location / "environ").write_bytes(
                ("HOME=" + str(self.root) + "\0WINEPREFIX=" +
                 str(self.root / "wine") + "\0").encode())
        launch = session.load_json(self.probe_dir / "launch.json")
        self.assertEqual(session._host_process(launch, proc), 100)
        (proc / "100" / "environ").write_bytes(b"WINEPREFIX=/wrong\0")
        with self.assertRaisesRegex(session.SessionError, "expected one"):
            session._host_process(launch, proc)

    def test_wine_pid_mapping_requires_same_prefix_local_server(self):
        proc = self.root / "proc"
        game = proc / "9876"
        server = proc / "9877"
        game.mkdir(parents=True)
        server.mkdir(parents=True)
        prefix = str(self.root / "wine")
        (game / "environ").write_bytes(("WINEPREFIX=" + prefix + "\0").encode())
        (server / "environ").write_bytes(("WINEPREFIX=" + prefix + "\0").encode())
        (server / "cmdline").write_bytes(b"frida-server.exe\0--listen=127.0.0.1:27043\0")
        result = session.select_frida_process(FakeDevice(555, {}), 9876, proc_root=proc)
        self.assertEqual(result, (555, "unique_game_and_same_prefix_server_distinct_pid"))
        (server / "environ").write_bytes(b"WINEPREFIX=/another\0")
        with self.assertRaisesRegex(session.SessionError, "same-prefix"):
            session.select_frida_process(FakeDevice(555, {}), 9876, proc_root=proc)
        with self.assertRaisesRegex(session.SessionError, "same-prefix"):
            session.select_frida_process(FakeDevice(555, {}), 9876, proc_root=proc,
                                         remote="192.0.2.3:27043")

    def test_inconclusive_capture_markers_preserved(self):
        case = {**self.cases[0], "inconclusive_markers": ["accepted=false"]}
        file = self.results["case-1"]
        file.write_text('call Preload("SESSION_START run_id=case-1")\ncall Preload("setup_failed=false")\ncall Preload("accepted=false")\ncall Preload("SESSION_DONE run_id=case-1")')
        self.assertEqual(session._fresh_capture(file, None, time.time_ns() - 1_000_000,
                                                case)[0], "inconclusive")

    def test_expected_rejection_is_complete_and_unexpected_rejection_fails(self):
        case = {"run_id": "case-1", "result_file": str(self.results["case-1"]),
                "timeout_seconds": 1, "acceptance_semantics": "issue_order_return",
                "expected_order_accepted": False,
                "required_markers": ["setup_failed=false", "accepted=false"],
                "inconclusive_markers": ["setup_failed=true", "accepted=true", "buffer_overflow=true"]}
        file = self.results["case-1"]
        prefix = 'call Preload("SESSION_START run_id=case-1")\ncall Preload("setup_failed=false")\n'
        suffix = '\ncall Preload("SESSION_DONE run_id=case-1")'
        file.write_text(prefix + 'call Preload("accepted=false")' + suffix)
        self.assertEqual(session._fresh_capture(file, None, time.time_ns() - 1_000_000, case)[0],
                         "ready_for_review")
        file.write_text(prefix + 'call Preload("accepted=true")' + suffix)
        self.assertEqual(session._fresh_capture(file, None, time.time_ns() - 1_000_000, case)[0], "failed")

    def test_acceptance_contract_requires_consistent_semantics_and_markers(self):
        invalid = {"cases": [{"run_id": "case-1", "result_file": str(self.root / "x.txt"),
                              "timeout_seconds": 1, "acceptance_semantics": "issue_order_return",
                              "expected_order_accepted": False,
                              "required_markers": ["accepted=true"],
                              "inconclusive_markers": ["accepted=false"]}]}
        with self.assertRaisesRegex(session.SessionError, "markers disagree"):
            session._validate_cases(invalid, max_seconds=5)

    def test_mutated_plan_agent_and_launch_refused(self):
        self.create()
        (self.plan_dir / "agent.js").write_text("malicious edit")
        with self.assertRaisesRegex(session.SessionError, "modified"):
            session.inspect_session(self.output)

    def test_cli_commands_parse(self):
        self.assertEqual(cli.main(["ability-session-create", "--plan", str(self.plan_dir),
                                   "--probe-dir", str(self.probe_dir), "--cases", str(self.cases_file),
                                   "--output", str(self.output)]), 0)


if __name__ == '__main__':
    unittest.main()
