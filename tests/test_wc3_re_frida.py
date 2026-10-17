"""Offline-only contracts for generated, bounded native ability instrumentation."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from wc3_re import frida
from wc3_re.graph import write_graph
import wc3_ability_re as cli

SHA = "3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed"
A = "0x0080d820"
B = "0x0080ecd0"
C = "0x0028ea00"


def sample_graph() -> dict:
    return {
        "schema_version": 1, "rawcode": "Apxf", "status": "static_candidate_graph",
        "class_reference_hint": "CAbilityPhoenixFire",
        "executable_sha256": SHA,
        "claims": {"runtime_reachability_proven": False},
        "seeds": [{"rva": A, "basis": [{"basis": "curated_label_match_only"}]}],
        "nodes": [
            {"rva": A, "name": "PhoenixEvent", "depth": 0, "unresolved_calls": []},
            {"rva": B, "name": "PhoenixAcquire", "depth": 1,
             "unresolved_calls": [{"reason": "unresolved_indirect_dispatch", "site_rva": "0x0080ecdd"}]},
            {"rva": C, "name": "SharedEnumerate", "depth": 2, "unresolved_calls": []},
        ],
        "edges": [
            {"from": A, "to": B, "kind": "direct_call", "traversable": True,
             "evidence": [{"origin": "ghidra_scan"}]},
            {"from": B, "to": C, "kind": "virtual_dispatch", "traversable": False,
             "evidence": [{"origin": "research_inventory", "context": "candidate"}]},
        ],
        "unbound_vtable_candidates": [{"seed_rva": "0x00b00000", "slots": [{"target_rva": C}]}],
    }


class TracePlanTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_candidate_selection_and_no_indirect_site_hooks(self):
        result = frida.plan(sample_graph(), max_hooks=2)
        self.assertEqual([hook["rva"] for hook in result["selected_hooks"]], [A, B])
        self.assertEqual(result["omitted_function_rvas"], [C])
        self.assertEqual(result["unresolved_sites"][0]["site_rva"], "0x0080ecdd")
        self.assertEqual(result["unresolved_sites"][0]["status"], "review_only_no_instruction_hook")
        self.assertEqual(result["candidate_relationships"][0]["kind"], "virtual_dispatch")
        self.assertFalse(result["evidence_boundary"]["receiver_identity_confirmed"])
        self.assertFalse(result["evidence_boundary"]["virtual_dispatch_bound"])

    def test_explicit_selection_priority_without_tracing_unvisited_targets(self):
        result = frida.plan(sample_graph(), max_hooks=1, include_rvas=[C])
        self.assertEqual([hook["rva"] for hook in result["selected_hooks"]], [C])
        with self.assertRaisesRegex(frida.TraceError, "analyzed graph"):
            frida.plan(sample_graph(), include_rvas=["0x00282180"])

    def test_return_address_filter_is_limited_to_selected_hook_and_generated_agent(self):
        result = frida.plan(sample_graph(), max_hooks=1, include_rvas=[A],
                            include_return_addresses={A: ["0x0080e123"]})
        self.assertEqual(result["selected_hooks"][0]["return_addresses"], ["0x0080e123"])
        agent = frida._agent_source(result)
        self.assertIn('"return_addresses": ["0x0080e123"]', agent)
        self.assertIn("return_addresses: hook.return_addresses", agent)
        self.assertIn("returnAddresses.indexOf(returnRva) !== -1", agent)
        with self.assertRaisesRegex(frida.TraceError, "not selected"):
            frida.plan(sample_graph(), max_hooks=1, include_rvas=[A],
                       include_return_addresses={B: ["0x0080e123"]})
        with self.assertRaisesRegex(frida.TraceError, "eight-digit"):
            frida.plan(sample_graph(), include_rvas=[A],
                       include_return_addresses={A: ["0x123"]})

    def test_invalid_inputs_fail_closed(self):
        for name, value in (("max_hooks", 0), ("max_hooks", 65), ("max_events", 0),
                            ("per_hook_events", 1201), ("seconds", 301),
                            ("stack_words", 9), ("capture_id", "x/y")):
            with self.subTest(name=name), self.assertRaises(frida.TraceError):
                frida.plan(sample_graph(), **{name: value})
        with self.assertRaisesRegex(frida.TraceError, "requested rawcode"):
            frida.plan(sample_graph(), rawcode="AOsw")
        broken = sample_graph()
        broken["executable_sha256"] = "not-a-hash"
        with self.assertRaisesRegex(frida.TraceError, "SHA-256"):
            frida.plan(broken)

    def test_invalid_graph_and_duplicate_nodes(self):
        broken = sample_graph()
        broken["nodes"].append(dict(broken["nodes"][0]))
        with self.assertRaisesRegex(frida.TraceError, "duplicate"):
            frida.plan(broken)
        broken = sample_graph()
        broken["nodes"][0]["rva"] = "0xBAD"
        with self.assertRaisesRegex(frida.TraceError, "RVA"):
            frida.plan(broken)
        broken = sample_graph()
        broken["claims"]["runtime_reachability_proven"] = True
        with self.assertRaisesRegex(frida.TraceError, "observed"):
            frida.plan(broken)

    def test_output_is_stable_immutable_and_has_no_abi_assumptions(self):
        result = frida.plan(sample_graph(), capture_id="phoenix-1", stack_words=2)
        path = self.root / "frida"
        frida.write_trace(result, path)
        self.assertEqual(json.loads((path / "trace-plan.json").read_text()), result)
        js = (path / "agent.js").read_text()
        self.assertTrue(js.startswith("// WC3_RETAIL_SHA256: " + SHA))
        for needle in ("Interceptor.attach", "rpc.exports", "stop('event_limit')",
                       "moduleInfo.base.add(rva)", "readPointer()", "return_address_rva"):
            self.assertIn(needle, js)
        self.assertNotIn("__WC3_RE_TRACE_CONFIGURATION__", js)
        self.assertNotIn("Memory.write", js)
        self.assertEqual(js, frida._agent_source(result))
        with self.assertRaisesRegex(frida.TraceError, "overwrite"):
            frida.write_trace(result, path)

    def test_controller_missing_and_tamper_refused(self):
        trace_plan = frida.plan(sample_graph())
        directory = self.root / "plan"
        frida.write_trace(trace_plan, directory)
        probe = self.root / "probe"
        probe.mkdir()
        (probe / "probe.json").write_text("{}")
        args = dict(plan_dir=directory, probe_dir=probe, seconds=60,
                    output=self.root / "trace.jsonl", controller=self.root / "missing.py")
        with self.assertRaisesRegex(frida.TraceError, "controller not found"):
            frida.run_controller(**args)
        with self.assertRaisesRegex(frida.TraceError, "duration"):
            frida.run_controller(**{**args, "seconds": 61})
        (directory / "agent.js").write_text("modified")
        with self.assertRaisesRegex(frida.TraceError, "differs"):
            frida.run_controller(**args)

    def test_controller_bridge_only_calls_existing_attach_tool(self):
        result = frida.plan(sample_graph())
        directory = self.root / "plan"
        frida.write_trace(result, directory)
        probe = self.root / "probe"
        probe.mkdir()
        (probe / "probe.json").write_text("{}")
        controller = self.root / "controller.py"
        controller.write_text("# fake")
        output = self.root / "events.jsonl"
        with mock.patch.object(frida.subprocess, "run") as runner:
            command = frida.run_controller(plan_dir=directory, probe_dir=probe,
                                           seconds=20, output=output, controller=controller)
        runner.assert_called_once_with(command, check=True)
        self.assertEqual(command[2], str(probe))
        self.assertIn(str(directory / "agent.js"), command)
        self.assertNotIn("--loadfile", command)

    def test_event_summarizer_does_not_claim_behavior(self):
        plan_dir = self.root / "plan"
        frida.write_trace(frida.plan(sample_graph(), capture_id="test-1"), plan_dir)
        events = [
            {"type": "send", "payload": {"source": "wc3_ability_re_frida", "kind": "start",
                                         "capture_id": "test-1", "rawcode": "Apxf"}},
            {"type": "send", "payload": {"source": "wc3_ability_re_frida", "kind": "enter",
                                         "function_rva": A, "capture_id": "test-1", "rawcode": "Apxf",
                                         "run_id": "case-1", "thread_id": 7, "invocation_id": 1}},
            {"source": "wc3_ability_re_frida", "kind": "leave",
             "function_rva": A, "capture_id": "test-1", "rawcode": "Apxf",
             "run_id": "case-1", "thread_id": 7, "invocation_id": 1,
             "return_value_raw": "0x41"},
            {"event": "trace-metadata", "retail_sha256": SHA,
             "agent_sha256": __import__("hashlib").sha256((plan_dir / "agent.js").read_bytes()).hexdigest(),
             "agent_required_retail_sha256": SHA},
            {"event": "trace-end", "errors": []},
            {"type": "logging", "message": "other"},
        ]
        path = self.root / "events.jsonl"
        path.write_text("\n".join(json.dumps(item) for item in events) + "\n")
        report = frida.summarize_trace(plan_dir, path)
        self.assertEqual(report["function_entry_counts"][A], {"enter": 1, "leave": 1})
        self.assertEqual(report["function_calls_by_run_id"]["case-1"][A][0]["return_value_raw"], "0x41")
        self.assertEqual(report["status"], "bounded_native_trace")
        self.assertIn("gameplay_effects", report["not_verified"])
        self.assertTrue(report["controller_identity_checked"])
        self.assertEqual(report["unclassified_controller_records"], 1)

    def test_missing_controller_end_or_overflow_is_not_success(self):
        plan_dir = self.root / "plan"
        frida.write_trace(frida.plan(sample_graph()), plan_dir)
        path = self.root / "incomplete.jsonl"
        path.write_text(json.dumps({"source": "wc3_ability_re_frida", "kind": "overflow",
                                    "reason": "event_limit", "capture_id": "offline-plan",
                                    "rawcode": "Apxf"}) + "\n")
        result = frida.summarize_trace(plan_dir, path)
        self.assertEqual(result["status"], "inconclusive_trace_setup")

    def test_unpaired_function_entry_marks_trace_partial(self):
        plan_dir = self.root / "plan"
        frida.write_trace(frida.plan(sample_graph(), capture_id="pairing"), plan_dir)
        agent_sha = __import__("hashlib").sha256((plan_dir / "agent.js").read_bytes()).hexdigest()
        records = [
            {"event": "trace-metadata", "retail_sha256": SHA, "agent_sha256": agent_sha,
             "agent_required_retail_sha256": SHA},
            {"source": "wc3_ability_re_frida", "kind": "start", "capture_id": "pairing", "rawcode": "Apxf"},
            {"source": "wc3_ability_re_frida", "kind": "enter", "capture_id": "pairing", "rawcode": "Apxf",
             "run_id": "case-1", "function_rva": A, "thread_id": 1, "invocation_id": 1},
            {"event": "trace-end", "errors": []},
        ]
        path = self.root / "unpaired.jsonl"
        path.write_text("\n".join(json.dumps(item) for item in records) + "\n")
        result = frida.summarize_trace(plan_dir, path)
        self.assertEqual(result["status"], "partial_native_trace")
        self.assertEqual(len(result["unpaired_function_calls"]), 1)
        self.assertTrue(result["truncated"])

    def test_mismatched_controller_identity_is_rejected(self):
        plan_dir = self.root / "plan"
        frida.write_trace(frida.plan(sample_graph()), plan_dir)
        path = self.root / "mismatched.jsonl"
        path.write_text(json.dumps({"event": "trace-metadata", "retail_sha256": "0" * 64,
                                    "agent_sha256": "0" * 64,
                                    "agent_required_retail_sha256": SHA}) + "\n")
        with self.assertRaisesRegex(frida.TraceError, "mismatched"):
            frida.summarize_trace(plan_dir, path)

    def test_event_mismatch_is_rejected(self):
        plan_dir = self.root / "plan"
        frida.write_trace(frida.plan(sample_graph()), plan_dir)
        path = self.root / "bad.jsonl"
        path.write_text(json.dumps({"source": "wc3_ability_re_frida", "kind": "enter",
                                    "capture_id": "offline-plan", "rawcode": "Apxf",
                                    "function_rva": "0x00012345"}) + "\n")
        with self.assertRaisesRegex(frida.TraceError, "mismatched"):
            frida.summarize_trace(plan_dir, path)

    def test_cli_generates_from_real_graph_directory(self):
        # Patch 4 writer expects the complete split output shape.
        obj = sample_graph()
        obj.update(decompiled={}, data_references={}, memory_access_candidates={},
                   branch_candidates={}, gaps=[], omitted={})
        for node in obj["nodes"]:
            node.update(incoming_static_function_count=0, decompile_status="not_exported")
        source = self.root / "graph"
        write_graph(obj, source)
        output = self.root / "result"
        self.assertEqual(cli.main(["ability-trace", "Apxf", "--graph", str(source),
                                   "--max-hooks", "2", "--output", str(output)]), 0)
        self.assertEqual(len(json.loads((output / "trace-plan.json").read_text())
                             ["selected_hooks"]), 2)
        self.assertEqual(cli.main(["ability-trace", "AOsw", "--graph", str(source),
                                   "--output", str(self.root / "bad")]), 1)

    def test_cli_accepts_bounded_return_address_filter(self):
        obj = sample_graph()
        obj.update(decompiled={}, data_references={}, memory_access_candidates={},
                   branch_candidates={}, gaps=[], omitted={})
        for node in obj["nodes"]:
            node.update(incoming_static_function_count=0, decompile_status="not_exported")
        source = self.root / "graph-filtered"
        write_graph(obj, source)
        output = self.root / "filtered"
        self.assertEqual(cli.main(["ability-trace", "Apxf", "--graph", str(source),
                                   "--max-hooks", "1", "--include-rva", A,
                                   "--include-return-address", A + "=0x0080e123",
                                   "--output", str(output)]), 0)
        plan = json.loads((output / "trace-plan.json").read_text())
        self.assertEqual(plan["selected_hooks"][0]["return_addresses"], ["0x0080e123"])


if __name__ == "__main__":
    unittest.main()
