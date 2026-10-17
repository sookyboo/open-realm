"""Patch 4 offline graph contracts: no Retail, MPQs, Wine or Ghidra needed."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from wc3_re import ghidra, graph
import wc3_ability_re as cli

INVENTORY = ROOT / "docs/games/warcraft-3/ability-function-investigation.json"
SHA = "3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed"
PHOENIX = ("0x0080d7d0", "0x0080d820", "0x0080ecd0", "0x0080f1e0")
AREA = "0x0028ea00"
HELPER = "0x00282180"


def write_export(folder: Path, mode: str, *, functions=(), calls=(), pcode=(),
                 decompiled=(), vtables=(), datarefs=(), sha=SHA):
    folder.mkdir()
    data = {"functions": list(functions), "callsites": list(calls), "pcode": list(pcode),
            "decompiled": list(decompiled), "vtables": list(vtables), "datarefs": list(datarefs)}
    for kind, items in data.items():
        with (folder / (kind + ".jsonl")).open("w") as fh:
            for row in items:
                fh.write(json.dumps(row) + "\n")
    (folder / "export-summary.json").write_text(json.dumps({
        "schema_version": 1, "status": "complete", "mode": mode,
        "executable_sha256": sha, "image_base": "0x00400000",
        "architecture": "x86:LE:32", "counts": {key: len(value) for key, value in data.items()},
    }))


def fn(addr):
    return {"entry_rva": addr, "name": f"FUN_{addr[2:]}", "signature": "void f(void)",
            "namespace": "Global", "thunk_target_rva": None}


def direct(caller, target, site="0x00800010", classification="static_call_reference"):
    return {"caller_rva": caller, "site_rva": site, "target_function_entry_rva": target,
            "target_rva": target, "classification": classification}


def lookup(rawcode="Apxf", name="CAbilityPhoenixFire", sha=SHA):
    return {"schema_version": 1, "rawcode": rawcode,
            "executable_identity": {"sha256": sha},
            "editions": {"tft": {"found": True, "retail_class_reference": {
                "class": name, "status": "offline_reference_hint"}}}}


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scan = self.root / "scan"
        self.detail = self.root / "detail"
        self.lookup = self.root / "lookup.json"
        self.lookup.write_text(json.dumps(lookup()))

    def _make(self, *, calls=(), detail=False, functions=None, pcode=(),
              vtables=(), decompiled=(), datarefs=()):
        funcs = functions or [*PHOENIX, AREA, HELPER]
        write_export(self.scan, "scan", functions=[fn(s) for s in funcs],
                     calls=calls, datarefs=datarefs)
        if detail:
            write_export(self.detail, "detail", functions=[fn(PHOENIX[2])],
                         pcode=pcode, vtables=vtables, decompiled=decompiled)

    def _graph(self, **params):
        values = dict(rawcode="Apxf", scan=self.scan, inventory=INVENTORY, lookup=self.lookup,
                      max_depth=4, max_nodes=100, max_edges=500)
        values.update(params)
        return graph.build_graph(**values)

    def test_auto_class_label_seeds_only_function_entries(self):
        self._make()
        result = self._graph()
        seeds = [item["rva"] for item in result["seeds"]]
        self.assertEqual(seeds, sorted(PHOENIX))
        self.assertTrue(all(item["basis"][0]["basis"] == "curated_label_match_only"
                            for item in result["seeds"]))
        self.assertEqual(result["class_reference_hint"], "CAbilityPhoenixFire")
        self.assertFalse(result["class_reference_is_native_verified"])

    def test_research_direct_and_callback_links_are_traversable_not_live(self):
        self._make()
        result = self._graph()
        self.assertIn(AREA, [n["rva"] for n in result["nodes"]])
        edge = next(x for x in result["edges"] if x["from"] == PHOENIX[2] and x["to"] == AREA)
        self.assertEqual(edge["kind"], "callback_dispatch")
        self.assertEqual(edge["evidence"][0]["origin"], "research_inventory")
        self.assertFalse(result["claims"]["runtime_reachability_proven"])

    def test_scan_callsite_is_independent_evidence_of_direct_call(self):
        self._make(calls=[direct(PHOENIX[2], HELPER)])
        result = self._graph()
        edge = next(x for x in result["edges"] if x["from"] == PHOENIX[2]
                    and x["to"] == HELPER and x["kind"] == "direct_call")
        self.assertEqual(edge["evidence"][0]["origin"], "ghidra_scan")
        self.assertIn(HELPER, [node["rva"] for node in result["nodes"]])

    def test_duplicate_inventory_evidence_survives_without_duplicate_logical_edges(self):
        inv = json.loads(INVENTORY.read_text())
        rel = next(r for r in inv["verified_relationships"] if r["from"]["rva"].lower() == PHOENIX[1]
                   and r["to"]["rva"].lower() == PHOENIX[2])
        duplicate = json.loads(json.dumps(rel))
        duplicate["context"] = "independent reviewed callsite evidence"
        inv["verified_relationships"].append(duplicate)
        inv["verified_relationship_count"] += 1
        file = self.root / "inventory.json"
        file.write_text(json.dumps(inv))
        self._make()
        result = self._graph(inventory=file)
        edges = [e for e in result["edges"] if e["from"] == PHOENIX[1]
                 and e["to"] == PHOENIX[2] and e["kind"] == "direct_call"]
        self.assertEqual(len(edges), 1)
        self.assertEqual(len(edges[0]["evidence"]), 2)
        self.assertEqual({v["context"] for v in edges[0]["evidence"]},
                         {rel["context"], "independent reviewed callsite evidence"})

    def test_nonimmediate_call_relationship_and_untyped_mentions_not_followed(self):
        inv = json.loads(INVENTORY.read_text())
        self._make()
        # Add a tempting invented 'related_call_path' from a Phoenix seed to a helper.
        orig = inv["verified_relationships"][0]
        test_rel = json.loads(json.dumps(orig))
        test_rel["from"] = {"va": "0x00c0d7d0", "rva": PHOENIX[0]}
        test_rel["to"] = {"va": "0x00682180", "rva": HELPER}
        test_rel["kind"] = "related_call_path"
        inv["verified_relationships"].append(test_rel)
        inv["verified_relationship_count"] += 1
        path = self.root / "modified.json"
        path.write_text(json.dumps(inv))
        result = self._graph(inventory=path, seed_rvas=[PHOENIX[0]], auto_seeds=False)
        self.assertEqual(len(result["nodes"]), 1)
        edge = next(e for e in result["edges"] if e["to"] == HELPER)
        self.assertFalse(edge["traversable"])
        self.assertFalse(edge["target_in_graph"])

    def test_unresolved_computed_call_never_turns_into_static_edge(self):
        self._make(calls=[direct(PHOENIX[0], AREA, classification="computed_call_reference")])
        result = self._graph(seed_rvas=[PHOENIX[0]], auto_seeds=False)
        self.assertEqual(len(result["nodes"]), 1)
        self.assertEqual(len(result["edges"]), 0)
        self.assertEqual(result["nodes"][0]["unresolved_calls"][0]["reason"],
                         "unresolved_indirect_dispatch")

    def test_detail_pcode_store_is_untyped_not_field_semantics(self):
        self._make(detail=True, pcode=[{"function_rva": PHOENIX[2], "opcode": "STORE",
                                      "site_rva": "0x0080ecd1", "inputs": ["ram", "ptr", "value"]},
                                     {"function_rva": PHOENIX[2], "opcode": "CBRANCH",
                                      "site_rva": "0x0080ecd4", "inputs": ["target", "test"]},
                                     {"function_rva": PHOENIX[2], "opcode": "CALLIND",
                                      "site_rva": "0x0080ecd2"}],
                   decompiled=[{"function_rva": PHOENIX[2], "status": "complete",
                                "c": "void a(void) { }"}],
                   vtables=[{"seed_rva": "0x00b00000", "slots": [
                       {"target_rva": PHOENIX[2]}]}])
        result = self._graph(detail=[self.detail])
        self.assertIn("STORE", [x["opcode"] for x in result["memory_access_candidates"][PHOENIX[2]]])
        self.assertFalse(result["claims"]["semantic_state_fields_proven"])
        self.assertEqual(result["branch_candidates"][PHOENIX[2]][0]["opcode"], "CBRANCH")
        self.assertEqual(result["unbound_vtable_candidates"][0]["status"],
                         "pointer_table_candidate_only")
        self.assertTrue(any(gap["kind"] == "indirect_or_unmapped_call"
                            for gap in result["gaps"]))
        self.assertEqual(result["decompiled"][PHOENIX[2]]["c"], "void a(void) { }")

    def test_static_datarefs_remain_untyped_evidence(self):
        self._make(datarefs=[{"function_rva": PHOENIX[0],
                              "site_rva": "0x0080d7da", "target_rva": "0x00a00000",
                              "target_va": "0x00e00000", "reference_type": "DATA"}])
        result = self._graph()
        self.assertEqual(result["data_references"][PHOENIX[0]][0]["target_rva"],
                         "0x00a00000")
        self.assertIn("not_proven_field", result["data_references"][PHOENIX[0]][0]["interpretation"])

    def test_limits_bound_walk_and_mark_truncation(self):
        self._make()
        result = self._graph(max_depth=0, seed_rvas=[PHOENIX[1]], auto_seeds=False)
        self.assertEqual(len(result["nodes"]), 1)
        self.assertTrue(result["omitted"]["depth_limit"])
        self.assertIn("bounded_traversal", [gap["kind"] for gap in result["gaps"]])
        result = self._graph(max_nodes=1, seed_rvas=[PHOENIX[1]], auto_seeds=False)
        self.assertEqual(len(result["nodes"]), 1)
        self.assertTrue(result["omitted"]["node_limit"])

    def test_wrong_build_and_incomplete_export_rejected(self):
        self._make()
        with (self.scan / "export-summary.json").open("w") as out:
            out.write('{"status":"not_complete"}')
        with self.assertRaises(ghidra.GhidraError):
            self._graph()
        (self.scan / "export-summary.json").unlink()

    def test_missing_seed_is_error_not_fabricated_function(self):
        self._make()
        with self.assertRaisesRegex(graph.GraphError, "absent from Ghidra scan"):
            self._graph(seed_rvas=["0x00899999"])

    def test_empty_seeds_rejected(self):
        self._make()
        with self.assertRaisesRegex(graph.GraphError, "no seeds"):
            self._graph(auto_seeds=False)

    def test_bad_lookup_rawcode_sha_and_multiple_classes_rejected(self):
        self._make()
        for value in (lookup(rawcode="AEsh"), lookup(sha="0" * 64),
                      {**lookup(), "editions": {"roc": {"found": True,
                          "retail_class_reference": {"status": "offline_reference_hint", "class": "Other"}},
                          "tft": lookup()["editions"]["tft"]}}):
            self.lookup.write_text(json.dumps(value))
            with self.assertRaises(graph.GraphError):
                self._graph()

    def test_result_files_are_immutable_and_do_not_invent_code(self):
        self._make()
        result = self._graph()
        directory = self.root / "result"
        graph.write_graph(result, directory)
        self.assertTrue((directory / "execution-graph.json").exists())
        self.assertTrue((directory / "native-code.json").exists())
        self.assertTrue((directory / "data-references.json").exists())
        self.assertTrue((directory / "review.md").exists())
        self.assertTrue((directory / "branch-candidates.json").exists())
        self.assertEqual(json.loads((directory / "native-code.json").read_text()), {})
        with self.assertRaisesRegex(graph.GraphError, "refusing existing"):
            graph.write_graph(result, directory)

    def test_cli_graph_command_parser(self):
        args = cli.build_parser().parse_args([
            "ability-graph", "Apxf", "--scan", str(self.scan), "--output", "result",
            "--seed-rva", PHOENIX[0]])
        self.assertEqual(args.rawcode, "Apxf")
        self.assertEqual(args.seed_rva, [PHOENIX[0]])
        self.assertEqual(args.run, cli.command_ability_graph)

    def test_reconstruct_can_use_authored_lookup_class_seed(self):
        self._make()
        resolved = lookup()
        with mock.patch.object(cli, "resolve", return_value=resolved):
            target = self.root / "output"
            args = cli.build_parser().parse_args([
                "reconstruct", "Apxf", "--ghidra-scan", str(self.scan),
                "--output-dir", str(target)])
            self.assertEqual(cli.command_reconstruct(args), 0)
        manifest = json.loads((target / "manifest.json").read_text())
        self.assertIn("static_execution_graph", manifest["completed_stages"])
        self.assertEqual(manifest["status"], "static_candidate_graph")
        self.assertTrue((target / "graph" / "review.md").exists())


if __name__ == "__main__":
    unittest.main()
