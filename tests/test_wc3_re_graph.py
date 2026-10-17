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

    def test_auto_seeds_match_authored_implementation_code_and_readable_class_name(self):
        curated = {"functions": [{"id": "cold-arrows", "label": "Cold Arrows attack hooks",
                                  "record_kind": "function_group", "addresses": [
                                      {"kind": "function_va", "rva": "0x0085ce10"},
                                      {"kind": "vtable_va", "rva": "0x00fa0dfc"}]}]}
        payload = {"editions": {"tft": {"ability": {"code": "AHca"},
                                         "aliases": ["ANfa", "ACcw"]}}}
        seeds = graph._candidate_seeds(curated, "ANfa", "CAbilityColdArrows", payload)
        self.assertEqual([seed["rva"] for seed in seeds], ["0x0085ce10"])

    def test_class_string_references_discover_without_curated_function_entries(self):
        refs = {
            "Apxf": ("CAbilityPhoenixFire", 0x01110001),
            "AOsw": ("CAbilityWard", 0x01110002),
            "ANfl": ("CAbilityForkedLightning", 0x01110003),
        }
        for rawcode, (class_name, target) in refs.items():
            with self.subTest(rawcode=rawcode):
                functions = {"0x00000100": {}, "0x00000200": {}}
                rows = [
                    ({"function_rva": "0x00000100", "site_rva": "0x00000108",
                      "target_va": f"0x{target:08x}"}, 1),
                    ({"function_rva": "0x00000200", "site_rva": "0x00000208",
                      "target_va": "0x01119999"}, 2),
                ]
                result = graph._class_string_reference_seeds(
                    class_name, {target: "rtti_name"}, rows, functions, self.scan)
                self.assertEqual([row["rva"] for row in result], ["0x00000100"])
                reason = result[0]["basis"][0]
                self.assertEqual(reason["evidence_classification"],
                                 "verified_static_reference_candidate")
                self.assertEqual(reason["receiver_identity"],
                                 "not established by a string reference")

    def test_multiple_class_string_references_are_retained_as_candidates(self):
        target = 0x01112345
        functions = {"0x00000100": {}, "0x00000200": {}}
        rows = [({"function_rva": addr, "site_rva": addr,
                  "target_va": f"0x{target:08x}"}, index)
                for index, addr in enumerate(functions, 1)]
        result = graph._class_string_reference_seeds(
            "CAbilityForkedLightning", {target: "rtti_name"}, rows, functions, self.scan)
        self.assertEqual([row["rva"] for row in result], sorted(functions))
        self.assertTrue(all(row["basis"][0]["confidence"] == "medium_static_candidate"
                            for row in result))

    def test_unresolved_class_string_reference_produces_no_seed(self):
        self.assertEqual(graph._class_string_reference_seeds(
            "CAbilityForkedLightning", {}, [], {}, self.scan), [])

    def test_class_string_search_rejects_mismatched_executable(self):
        executable = self.root / "wrong.exe"
        executable.write_bytes(b"wrong build")
        with self.assertRaisesRegex(graph.GraphError, "SHA-256 mismatch"):
            graph._class_string_target_vas(executable, "CAbilityForkedLightning", SHA)

    def test_registration_offsets_require_matching_build_and_translate_file_offsets(self):
        # A minimal PE with a raw-backed .text section whose RVA differs from its file offset.
        image = bytearray(0x500)
        image[0x3c:0x40] = (0x80).to_bytes(4, "little")
        image[0x86:0x88] = (1).to_bytes(2, "little")
        image[0x94:0x96] = (0xe0).to_bytes(2, "little")
        image[0x80:0x84] = b"PE\0\0"
        image[0x80 + 24 + 28:0x80 + 24 + 32] = (0x400000).to_bytes(4, "little")
        sh = 0x80 + 24 + 0xe0
        image[sh + 8:sh + 24] = (0x200).to_bytes(4, "little") + (0x1000).to_bytes(4, "little") + (0x200).to_bytes(4, "little") + (0x200).to_bytes(4, "little")
        executable = self.root / "fixture.exe"
        executable.write_bytes(image)
        digest = graph.hashlib.sha256(image).hexdigest()
        self.assertEqual(graph._file_offset_to_rva(executable, "0x00000220", digest), "0x00001020")
        self.assertEqual(graph._registration_seeds(executable,
            {"binary_sha256": "0" * 64}, "CAbilityForkedLightning", "ANfl", "ANfl",
            digest, {}, []), [])

    def test_registration_callback_requires_unique_containing_function(self):
        executable = self.root / "fixture.exe"
        executable.write_bytes(b"not a PE")
        # A stale registration must be discarded before parsing or trusting offsets.
        self.assertEqual(graph._registration_seeds(executable,
            {"binary_sha256": "0" * 64, "factory_file_offset": "0x20"},
            "CAbilityForkedLightning", "ANfl", "ANfl", SHA, {}, []), [])

    def test_class_linked_vtable_slots_are_candidates_not_graph_edges(self):
        # A class registration factory's exact static table reference scopes
        # slot candidates but must not imply runtime dispatch.
        factory, method = "0x00001000", "0x00002000"
        self._make(functions=[factory, method], datarefs=[{
            "function_rva": factory, "site_rva": "0x00001008",
            "target_va": "0x00403000", "target_rva": "0x00003000",
            "reference_type": "DATA"}])
        table_dir = self.root / "detail-vtable"
        write_export(table_dir, "detail", functions=[fn(factory)], vtables=[{
            "seed_rva": "0x00003000", "status": "pointer_table_candidate_only",
            "slots": [{"offset": "0x00000004", "target_rva": method,
                       "function_entry_confirmed": True}]}])
        out = graph.build_graph(rawcode="Apxf", scan=self.scan, inventory=INVENTORY,
                                lookup=self.lookup, detail=[table_dir], seed_rvas=[factory],
                                auto_seeds=False, max_depth=0, max_nodes=10)
        self.assertEqual([node["rva"] for node in out["nodes"]], [factory, method])
        self.assertEqual(out["nodes"][1]["depth"], 1)
        self.assertIn(method, out["vtable_method_candidates"])
        self.assertEqual(out["vtable_method_candidates"][method][0]["slot_offset"],
                         "0x00000004")
        self.assertEqual(out["vtable_method_candidates"][method][0]["confidence"],
                         "candidate_vtable_method")

    @unittest.skipUnless((ROOT / "data/Warcraft III/Warcraft III.exe").is_file(),
                         "local pinned Retail executable unavailable")
    def test_pinned_registration_callbacks_normalize_from_file_offsets(self):
        executable = ROOT / "data/Warcraft III/Warcraft III.exe"
        registration = {
            "binary_sha256": SHA,
            "factory_file_offset": "0x00877840",
            "destroy_file_offset": "0x008778b0",
            "pool_cleanup_file_offset": "0x008778e0",
        }
        functions = {"0x00878440": {}, "0x008784b0": {}, "0x008784e0": {}}
        rows = graph._registration_seeds(executable, registration,
            "CAbilityForkedLightning", "ANfl", "ANfl", SHA, functions, [])
        self.assertEqual([row["rva"] for row in rows], sorted(functions))
        self.assertEqual([row["basis"][0]["registration_role"] for row in rows],
                         ["factory", "destroy", "pool_cleanup"])
        self.assertTrue(all(row["basis"][0]["receiver_identity"].endswith(
            "runtime receiver not established") for row in rows))

    def test_auto_seed_normalizes_code_address_to_unique_containing_function(self):
        inventory = self.root / "inventory-containing.json"
        curated = json.loads(INVENTORY.read_text())
        curated["functions"] = [{"id": "forked", "label": "CAbilityForkedLightning constructor",
                                 "record_kind": "function_group", "status": "partially_resolved",
                                 "confidence": "high", "source": {"document": "fixture"},
                                 "addresses": [{"kind": "function_va", "rva": "0x00000108",
                                               "va": "0x00400108"}],
                                 "object_offsets": [], "evidence_summary": "fixture",
                                 "related_addresses": [], "related_addresses_semantics": "fixture"}]
        curated["verified_relationships"] = []
        curated["entry_count"] = 1
        curated["relationship_count"] = 0
        curated["verified_relationship_count"] = 0
        inventory.write_text(json.dumps(curated))
        self._make(functions=["0x00000100"])
        # Adjust scan metadata to model an instruction address inside the function.
        rows = [json.loads(line) for line in (self.scan / "functions.jsonl").read_text().splitlines()]
        rows[0]["body_min_va"] = "0x00400100"
        rows[0]["body_max_va"] = "0x00400120"
        (self.scan / "functions.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n")
        # Reuse a valid lookup identity but with a matching class hint.
        payload = lookup()
        payload["editions"]["tft"]["retail_class_reference"] = {
            "status": "offline_reference_hint", "class": "CAbilityForkedLightning"}
        result = graph.build_graph(rawcode="Apxf", scan=self.scan, inventory=inventory,
                                   lookup_data=payload, max_depth=0, max_nodes=10)
        seed = result["seeds"][0]
        self.assertEqual(seed["rva"], "0x00000100")
        self.assertEqual(seed["basis"][0]["address_normalization"]["inventory_rva"],
                         "0x00000108")

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
