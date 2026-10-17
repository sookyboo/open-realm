"""Patch 6: deterministic, evidence-bounded *offline* ability reconstruction package.

Consumes Patch 2 lookup, Patch 4 graph, and Patch 5 presentation objects.
It neither executes Retail/Ghidra nor infers gameplay semantics from an art
reference, an unnamed p-code access, or an unbound virtual-call candidate.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from wc3_re.lookup import LookupError, check_rawcode


class PackageError(LookupError):
    """Incomplete, inconsistent, or unsafe reconstruction evidence."""


def _object(doc: Any, name: str) -> dict[str, Any]:
    if not isinstance(doc, dict) or doc.get("schema_version") != 1:
        raise PackageError(f"{name} must be a version 1 JSON object")
    return doc


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PackageError(f"cannot read {label} {path}: {error}") from error
    return _object(doc, label)


def read_graph(directory: Path) -> dict[str, Any]:
    """Restore the split output of write_graph, without losing any evidence."""
    if not directory.is_dir():
        raise PackageError(f"graph directory does not exist: {directory}")
    obj = _read_json(directory / "execution-graph.json", "execution graph")
    for name, key in (("native-code.json", "decompiled"),
                      ("data-references.json", "data_references"),
                      ("memory-access-candidates.json", "memory_access_candidates"),
                      ("branch-candidates.json", "branch_candidates")):
        raw = directory / name
        try:
            item = json.loads(raw.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise PackageError(f"cannot read graph sidecar {raw}: {error}") from error
        if not isinstance(item, dict):
            raise PackageError(f"graph sidecar must be an object: {raw}")
        obj[key] = item
    return obj


def read_presentation(path: Path) -> dict[str, Any]:
    return _read_json(path / "assets.json" if path.is_dir() else path, "presentation")


def _digest(payload: Any) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _safe_md(value: Any) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").replace("|", "\\|").replace("`", "'")


def _validate(lookup: dict[str, Any], graph: dict[str, Any] | None,
              presentation: dict[str, Any] | None) -> tuple[str, str | None]:
    _object(lookup, "lookup")
    rawcode = check_rawcode(lookup.get("rawcode", ""))
    editions = lookup.get("editions")
    if not isinstance(editions, dict) or not editions or any(
            key not in ("roc", "tft") or not isinstance(value, dict)
            for key, value in editions.items()):
        raise PackageError("lookup has invalid or empty editions")
    identity = lookup.get("executable_identity")
    sha = identity.get("sha256") if isinstance(identity, dict) else None
    if sha is not None and (not isinstance(sha, str) or len(sha) != 64
                            or any(c not in "0123456789abcdef" for c in sha.lower())):
        raise PackageError("lookup executable SHA-256 is malformed")
    if graph is not None:
        _object(graph, "execution graph")
        if graph.get("status") != "static_candidate_graph":
            raise PackageError("graph is not a static candidate graph")
        if graph.get("rawcode") != rawcode:
            raise PackageError("graph rawcode does not match lookup")
        if not sha or str(graph.get("executable_sha256", "")).lower() != sha.lower():
            raise PackageError("graph executable hash does not match lookup")
        if not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("edges"), list) or not isinstance(graph.get("gaps"), list):
            raise PackageError("graph lacks nodes, edges, or gaps")
        if not isinstance(graph.get("decompiled"), dict):
            raise PackageError("graph lacks decompiled code sidecar")
        claims = graph.get("claims")
        if not isinstance(claims, dict) or any(not isinstance(claims.get(name), bool) for name in
                ("runtime_reachability_proven", "semantic_state_fields_proven",
                 "animation_or_effect_timing_proven")):
            raise PackageError("graph is missing static-evidence claim boundaries")
        if any(claims[name] for name in
               ("runtime_reachability_proven", "semantic_state_fields_proven",
                "animation_or_effect_timing_proven")):
            raise PackageError("static graph unexpectedly asserts runtime/semantic proof")
        entries = [node.get("rva") for node in graph["nodes"] if isinstance(node, dict)]
        if len(entries) != len(graph["nodes"]) or any(not isinstance(rva, str) or re.fullmatch(r"0x[0-9a-fA-F]{8}", rva) is None for rva in entries) or len(entries) != len(set(entries)):
            raise PackageError("graph has invalid or duplicate function RVAs")
        for edge in graph["edges"]:
            if not isinstance(edge, dict) or edge.get("from") not in entries or not isinstance(edge.get("to"), str) or re.fullmatch(r"0x[0-9a-fA-F]{8}", edge["to"]) is None:
                raise PackageError("graph edge has invalid function reference")
            if not isinstance(edge.get("evidence"), list):
                raise PackageError("graph edge lacks evidence records")
        if any(rva not in entries or not isinstance(row, dict)
               for rva, row in graph["decompiled"].items()):
            raise PackageError("decompiled function does not belong to the graph")
    if presentation is not None:
        _object(presentation, "presentation")
        if presentation.get("rawcode") != rawcode:
            raise PackageError("presentation rawcode does not match lookup")
        if presentation.get("runtime_effect_timing_verified") is not False:
            raise PackageError("presentation has unsupported runtime timing evidence")
        presented_editions = presentation.get("editions")
        if not isinstance(presented_editions, dict) or presented_editions.keys() != editions.keys():
            raise PackageError("presentation editions do not match lookup")
        for edition, info in presented_editions.items():
            if not isinstance(info, dict) or info.get("found") is not editions[edition].get("found"):
                raise PackageError(f"presentation/lookup disagree on {edition} ability presence")
            if info["found"] and any(not isinstance(info.get(key), list)
                                      for key in ("references", "models", "sounds", "gaps", "rank_links")):
                raise PackageError(f"presentation has incomplete {edition} dependencies")
    return rawcode, sha


def build_package(lookup: dict[str, Any], *, graph: dict[str, Any] | None = None,
                  presentation: dict[str, Any] | None = None) -> dict[str, Any]:
    """Combine already generated evidence without performing further tool calls."""
    rawcode, sha = _validate(lookup, graph, presentation)
    names = sorted(node["rva"] for node in graph["nodes"]) if graph else []
    code = graph["decompiled"] if graph else {}
    complete = sorted(rva for rva in names if rva in code and code[rva].get("status") == "complete"
                      and isinstance(code[rva].get("c"), str) and code[rva]["c"].strip())
    deps: dict[str, Any] = {
        "functions": graph["nodes"] if graph else [],
        "call_relationships": graph["edges"] if graph else [],
        "data_references": graph.get("data_references", {}) if graph else {},
        "memory_access_candidates": graph.get("memory_access_candidates", {}) if graph else {},
        "branch_candidates": graph.get("branch_candidates", {}) if graph else {},
        "unbound_vtables": graph.get("unbound_vtable_candidates", []) if graph else [],
        "vtable_method_candidates": graph.get("vtable_method_candidates", {}) if graph else {},
        "presentation": {},
    }
    questions: list[dict[str, Any]] = []

    def add(category: str, kind: str, detail: str, source: str,
            next_step: str) -> None:
        questions.append({"id": f"Q{len(questions) + 1:04d}", "category": category,
                          "kind": kind, "detail": detail, "source": source,
                          "suggested_resolution": next_step, "status": "unresolved"})

    if graph is None:
        add("native_logic", "no_execution_graph", "No validated static function graph supplied.",
            "graph", "Generate a Ghidra scan/detail export and ability-graph before considering Retail.")
    else:
        for item in graph["gaps"]:
            if not isinstance(item, dict) or not isinstance(item.get("kind"), str):
                raise PackageError("malformed graph gap")
            kind = item["kind"]
            add("native_logic", kind,
                f"Function {item.get('rva', '(graph-wide)')}; count={item.get('count', 'unknown')}; "
                f"bounds={item.get('reasons', 'none')}",
                "graph.gaps", "Use cached static evidence or targeted Ghidra detail/dispatch review first.")
        if not graph["nodes"]:
            add("native_logic", "empty_function_graph", "No functions represented.",
                "graph.nodes", "Check rawcode-to-class seed bindings and Ghidra scan.")
        gap_rvas = {row.get("rva") for row in graph["gaps"]
                    if row.get("kind") == "decompilation_missing_or_failed"}
        for rva in sorted(set(names) - set(complete) - gap_rvas):
            add("native_logic", "decompilation_missing_or_failed",
                f"No complete decompiled body for function {rva}.", "graph.decompiled",
                "Generate a focused Ghidra detail export for this function.")
        if graph.get("unresolved_relationship_targets"):
            add("native_logic", "missing_relationship_targets",
                f"{len(graph['unresolved_relationship_targets'])} documented targets outside the analyzed scan.",
                "graph.unresolved_relationship_targets", "Inspect missing target functions in Ghidra.")
        if not graph.get("class_reference_is_native_verified", False):
            add("native_logic", "class_binding_unverified", "Offline class reference is not confirmed factory/vtable binding.",
                "graph.class_reference_hint", "Resolve registration/factory and receiver statically; trace if necessary.")
    if presentation is None:
        add("presentation", "no_presentation_report", "No authored art or sound dependencies supplied.",
            "presentation", "Run ability-presentation using the cached lookup.")
    else:
        for edition, item in sorted(presentation["editions"].items()):
            if not item["found"]:
                deps["presentation"][edition] = {"found": False}
                continue
            deps["presentation"][edition] = {"found": True, "rank_links": item["rank_links"],
                "references": item["references"], "models": item["models"], "sounds": item["sounds"]}
            for message in item["gaps"]:
                add("presentation", "authored_presentation_gap", str(message),
                    f"presentation.editions.{edition}.gaps", "Inspect native presentation selection; use a targeted trace only if static analysis cannot resolve it.")
            for model in item["models"]:
                if not isinstance(model, dict):
                    raise PackageError("presentation model is malformed")
                if model.get("status") != "static_model_metadata":
                    add("presentation", "model_not_resolved", str(model.get("path", "(unknown)")),
                        f"presentation.editions.{edition}.models", "Resolve missing/unsupported asset from selected edition archives.")
            for sound in item["sounds"]:
                if not isinstance(sound, dict):
                    raise PackageError("presentation sound is malformed")
                if sound.get("status") not in ("authored_sound_row",):
                    add("presentation", "sound_alias_unresolved", str(sound.get("alias", "(unknown)")),
                        f"presentation.editions.{edition}.sounds", "Inspect edition-specific sound lookup and fallback.")
    add("runtime_fidelity", "execution_not_observed", "Static calls and authored references do not prove a given cast takes these paths.",
        "static_evidence_boundary", "Use later runtime tracing only for material ambiguous branches after static review.")
    add("runtime_fidelity", "effects_animation_timing_unproven", "Model paths and sequence metadata do not establish animation or effect timing/lifetime.",
        "static_evidence_boundary", "Resolve native presentation dispatch and timer owners; run focused Retail comparison if necessary.")
    decoded = {edition: {"found": bool(row.get("found")),
                        "rank_count": len(row.get("ranks", [])) if row.get("found") else 0,
                        "implementation_code": row.get("retail_class_reference", {}).get("implementation_code") if row.get("found") else None,
                        "class_reference": row.get("retail_class_reference", {}).get("class") if row.get("found") else None}
               for edition, row in sorted(lookup["editions"].items())}
    present_count = sum(len(row.get("references", [])) for row in presentation["editions"].values()) if presentation else 0
    model_count = sum(len(row.get("models", [])) for row in presentation["editions"].values()) if presentation else 0
    coverage = {
        "schema_version": 1, "rawcode": rawcode,
        "metrics": {"authored_editions_found": sum(row["found"] for row in decoded.values()),
                    "authored_ranks_exported": sum(row["rank_count"] for row in decoded.values()),
                    "function_nodes": len(names), "decompiled_complete": len(complete),
                    "decompiled_missing_or_failed": len(names) - len(complete),
                    "authored_presentation_references": present_count,
                    "model_references_inspected_or_attempted": model_count,
                    "unresolved_questions": len(questions)},
        "dimensions": {
            "authored_data": "present" if any(row["found"] for row in decoded.values()) else "ability_absent_in_selected_editions",
            "native_execution_graph": "static_candidates_only" if graph else "not_supplied",
            "native_pseudocode": "all_selected_functions_decompiled" if names and len(complete) == len(names)
                                  else "partially_decompiled" if complete else "not_available",
            "presentation_assets": "authored_dependencies_only" if presentation else "not_supplied",
            "gameplay_semantics": "unverified", "runtime_effect_selection": "unverified",
            "animations_and_audio_timing": "unverified", "full_retail_parity": "not_established"},
        "note": "Counts measure extracted evidence, never percentages of Retail parity.",
    }
    return {
        "schema_version": 1, "rawcode": rawcode, "executable_sha256": sha,
        "state": "offline_static_reconstruction_not_verified_gameplay",
        "editions": decoded, "coverage": coverage, "dependencies": deps,
        "questions": questions, "code": {rva: code[rva] for rva in complete},
        "provenance": {"executable_sha256": sha,
                       "input_digests": {"lookup": _digest(lookup),
                                         "graph": _digest(graph) if graph is not None else None,
                                         "presentation": _digest(presentation) if presentation is not None else None},
                       "graph_sources": graph.get("input_exports") if graph else None,
                       "data_source": "Patch 2 authored lookup; edition archives are recorded in lookup.json",
                       "claim_scope": "static/offline only"},
    }


def _pseudocode(report: dict[str, Any]) -> str:
    lines = ["/*", " * Decompiled Warcraft III Retail C-like pseudocode (unmodified output from Ghidra).",
             " * NOT original Blizzard source, NOT guaranteed compilable, NOT an OpenRealm implementation.",
             " * Only complete exported bodies below; omitted bodies are listed in coverage.json.",
             " * A function's appearance does not prove execution during an ability cast.", " */", ""]
    for rva, item in sorted(report["code"].items()):
        source = str(item.get("source", "not recorded")).replace("*/", "* /").replace("\n", " ")
        lines.extend([f"/* Function RVA {rva}; export: {source} */", item["c"].rstrip(), ""])
    if not report["code"]:
        lines.append("/* No successful Ghidra detail decompilations supplied. */")
    return "\n".join(lines).rstrip() + "\n"


def _report_md(report: dict[str, Any]) -> str:
    counts = report["coverage"]["metrics"]
    lines = [f"# Offline Retail ability reconstruction: `{report['rawcode']}`", "",
             "**Evidence boundary:** static code and authored game data only. This is **not** an",
             "implementation-ready parity specification or verified runtime effect timeline.", "",
             f"Retail executable SHA-256: `{report['executable_sha256'] or 'not provided'}`", "",
             "## Available evidence", "",
             "| Dimension | Status |", "|---|---|", *(
                 f"| {_safe_md(key.replace('_', ' '))} | `{value}` |"
                 for key, value in report["coverage"]["dimensions"].items()), "",
             "## Authored ability rows", "",
             "| Edition | Found | Exported ranks | Implementation code | Class hint |",
             "|---|---|---:|---|---|"]
    for edition, record in report["editions"].items():
        lines.append(f"| {edition.upper()} | {record['found']} | {record['rank_count']} | "
                     f"`{_safe_md(record['implementation_code'] or '-')}` | "
                     f"`{_safe_md(record['class_reference'] or 'unresolved')}` (unverified) |")
    lines += ["", "## Static native code", "",
              f"Functions in graph: **{counts['function_nodes']}**; successful detail decompilations: "
              f"**{counts['decompiled_complete']}**. These do not establish runtime reachability.", "",
              "See `native/decompiled.c` and `dependencies.json` for actual code and source evidence.", "",
              "## Authored presentation", "",
              f"Authoring references: **{counts['authored_presentation_references']}**; "
              f"model entries: **{counts['model_references_inspected_or_attempted']}**.", "",
              "See `dependencies.json` for authored source fields, models and sound definitions.",
              "Model sequence metadata is not a proof that Retail selects or plays a sequence.", "",
              "## Questions to resolve", "",
              f"Open questions: **{counts['unresolved_questions']}**. "
              "See `questions.json` for categories, sources, and suggested next steps.", ""]
    for item in report["questions"]:
        lines.append(f"- **{item['id']}** ({item['category']}, `{item['kind']}`): {_safe_md(item['detail'])}")
    lines += ["", "## Evidence provenance and regeneration", "",
              "`provenance.json` contains canonical content digests for each input and native export paths.",
              "Re-run `ability-package` with cached `lookup.json`, `graph/`, and `presentation/` to",
              "generate a fresh offline report without Ghidra, MPQ inspection, Wine or Retail.", ""]
    return "\n".join(lines)


def write_package(report: dict[str, Any], directory: Path) -> None:
    """Create immutable package; validate before creating the directory."""
    if directory.exists():
        raise PackageError(f"refusing existing offline report directory: {directory}")
    directory.mkdir(parents=True)
    native = directory / "native"
    native.mkdir()
    payloads = {
        "coverage.json": report["coverage"],
        "dependencies.json": report["dependencies"],
        "questions.json": {"schema_version": 1, "rawcode": report["rawcode"],
                           "questions": report["questions"]},
        "provenance.json": report["provenance"],
    }
    for name, contents in payloads.items():
        (directory / name).write_text(json.dumps(contents, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (native / "decompiled.c").write_text(_pseudocode(report), encoding="utf-8")
    (directory / "report.md").write_text(_report_md(report), encoding="utf-8")
    (directory / "README.md").write_text(
        "# Offline reconstruction package\n\n"
        "- [Summary and open questions](report.md)\n"
        "- [Coverage](coverage.json) — evidence counts, not gameplay parity\n"
        "- [Dependencies](dependencies.json) — static graph and authored assets\n"
        "- [Gaps](questions.json) — explicit unresolved steps\n"
        "- [Ghidra C-like output](native/decompiled.c) — not original or compilable source\n"
        "- [Provenance](provenance.json) — input content digests and Retail identity\n",
        encoding="utf-8")
