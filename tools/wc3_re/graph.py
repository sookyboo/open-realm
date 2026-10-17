"""Conservative, bounded ability graph assembled from exact-build static evidence.

A graph edge means there is a documented *possible* control-flow relationship,
not that a particular cast reached it.  Unclassified calls, unbound vtables,
related-address mentions and decompiler STOREs are never promoted to gameplay
facts.  This module performs no executable analysis or live instrumentation.
"""

from __future__ import annotations

from collections import defaultdict, deque
import json
from pathlib import Path
import re
from typing import Any

from wc3_re.ghidra import rva as parse_rva, validate_export
from wc3_re.inventory import validate_inventory
from wc3_re.lookup import LookupError, check_rawcode

MAX_NODES = 500
MAX_EDGES = 5000
MAX_DEPTH = 12
FOLLOW_RESEARCH = frozenset({"direct_call", "callback_dispatch"})
EXPLICIT_UNRESOLVED = frozenset({"call", "related_call_path", "virtual_dispatch"})


class GraphError(LookupError):
    """Invalid input, unsafe identification, or incomplete native evidence."""


def _hex(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise GraphError(f"{field}: expected an RVA string")
    return f"0x{parse_rva(value):08x}"


def _rows(directory: Path, kind: str):
    with (directory / (kind + ".jsonl")).open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            obj = json.loads(line)
            if not isinstance(obj, dict):
                raise GraphError(f"{directory / (kind + '.jsonl')}:{number}: expected object")
            yield obj, number


def _load_inventory(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise GraphError(f"cannot read inventory {path}: {error}") from error
    result = validate_inventory(data)
    if not result["valid"]:
        raise GraphError("inventory failed validation: " + ", ".join(
            issue["code"] for issue in result["issues"] if issue["severity"] == "error"))
    return data


def _class_from_lookup(path: Path | None, rawcode: str, sha: str,
                       payload: dict[str, Any] | None = None) -> tuple[str | None, dict[str, Any] | None, dict[str, Any] | None]:
    if path is None and payload is None:
        return None, None, None
    if payload is None:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise GraphError(f"cannot read lookup JSON {path}: {error}") from error
    else:
        doc = payload
    if not isinstance(doc, dict) or doc.get("schema_version") != 1 or doc.get("rawcode") != rawcode:
        raise GraphError("lookup.json rawcode/schema mismatch")
    if not isinstance(doc.get("executable_identity"), dict) or str(doc["executable_identity"].get("sha256", "")).lower() != sha.lower():
        raise GraphError("lookup.json executable identity differs from inventory")
    classes = set()
    if not isinstance(doc.get("editions"), dict):
        raise GraphError("lookup.json editions must be an object")
    for edition, data in doc["editions"].items():
        if not isinstance(data, dict):
            raise GraphError(f"lookup.json invalid edition {edition}")
        if data.get("found"):
            hint = data.get("retail_class_reference", {})
            if not isinstance(hint, dict):
                raise GraphError(f"lookup.json malformed class hint for {edition}")
            # Only class-reference hints, never a verified native factory mapping.
            if hint.get("status") == "offline_reference_hint" and hint.get("class"):
                classes.add(str(hint["class"]))
    if len(classes) > 1:
        raise GraphError("lookup.json contains conflicting class hints; use explicit seeds")
    return next(iter(classes), None), {"file": str(path) if path else None,
                                     "identity": "authored_data_only"}, doc


def _candidate_seeds(inventory: dict[str, Any], rawcode: str, class_hint: str | None,
                     lookup_doc: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    result = []
    terms = {rawcode}
    if class_hint:
        terms.add(class_hint)
        simple = class_hint.removeprefix("CAbility")
        terms.add(re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", simple))
    if lookup_doc:
        for edition in lookup_doc.get("editions", {}).values():
            ability = edition.get("ability", {}) if isinstance(edition, dict) else {}
            code = ability.get("code")
            if isinstance(code, str):
                terms.add(code)
            aliases = edition.get("aliases", []) if isinstance(edition, dict) else []
            terms.update(alias for alias in aliases if isinstance(alias, str))
    patterns = [re.compile(r"(?<![A-Za-z0-9_])" + re.escape(term) + r"(?![A-Za-z0-9_])", re.IGNORECASE)
                for term in terms if term]
    for entry in inventory["functions"]:
        # Only the curated label is eligible for auto-seeding. Context/related
        # addresses merely mention code and must not seed arbitrary functions.
        if entry.get("record_kind") == "vtable_record" or not any(
                pattern.search(entry.get("label", "")) for pattern in patterns):
            continue
        for address in entry["addresses"]:
            if address.get("kind") == "function_va":
                result.append({"rva": _hex(address["rva"], "inventory seed"),
                               "basis": "curated_label_match_only", "record_id": entry["id"],
                               "label": entry["label"], "confidence": "candidate_not_runtime_verified"})
    return result


def build_graph(*, rawcode: str, scan: Path, inventory: Path,
                detail: list[Path] | None = None, lookup: Path | None = None,
                lookup_data: dict[str, Any] | None = None,
                seed_rvas: list[str] | None = None, auto_seeds: bool = True,
                max_depth: int = 4, max_nodes: int = 120,
                max_edges: int = 1000) -> dict[str, Any]:
    """Build a deterministic graph; inputs are immutable validated exports.

    Only direct instruction references and cited direct/callback research edges
    are traversed.  Virtual relationships, computed calls and vtable candidates
    are retained, but never followed without a confirmed receiver binding.
    """
    check_rawcode(rawcode)
    if not 0 <= max_depth <= MAX_DEPTH or not 1 <= max_nodes <= MAX_NODES or not 1 <= max_edges <= MAX_EDGES:
        raise GraphError("invalid traversal bounds (depth 0–12, nodes 1–500, edges 1–5000)")
    inv = _load_inventory(inventory)
    sha = inv["executable"]["sha256"]
    validate_export(scan, sha, "scan")
    details = detail or []
    for directory in details:
        validate_export(directory, sha, "detail")
    hint, lookup_evidence, lookup_doc = _class_from_lookup(lookup, rawcode, sha, lookup_data)

    functions: dict[str, dict[str, Any]] = {}
    for f, number in _rows(scan, "functions"):
        entry = _hex(f.get("entry_rva"), "function.entry_rva")
        if entry in functions:
            raise GraphError(f"duplicate scan function entry {entry}")
        functions[entry] = {"rva": entry, "name": f.get("name"),
                            "signature": f.get("signature"), "namespace": f.get("namespace"),
                            "thunk_target_rva": f.get("thunk_target_rva"),
                            "source": f"{scan}/functions.jsonl:{number}"}
    function_ranges = []
    image_base = parse_rva("0x00400000")
    scan_function_rows = {}
    for function, number in _rows(scan, "functions"):
        scan_function_rows[_hex(function.get("entry_rva"), "function.entry_rva")] = function
    for entry, row in functions.items():
        try:
            function = scan_function_rows[entry]
            entry_va = parse_rva(entry) + image_base
            low_va = parse_rva(function.get("body_min_va") or function.get("entry_va") or f"0x{entry_va:08x}")
            high_va = parse_rva(function.get("body_max_va") or function.get("entry_va") or f"0x{entry_va:08x}")
            function_ranges.append((low_va - image_base, high_va - image_base, entry))
        except (OSError, ValueError, StopIteration):
            continue

    # Keep each independent research statement, even if it repeats an edge.
    inv_entry_by_rva: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in inv["functions"]:
        for addr in item["addresses"]:
            if addr.get("kind") == "function_va":
                inv_entry_by_rva[_hex(addr["rva"], "inventory address")].append(
                    {"record_id": item["id"], "label": item["label"],
                     "status": item["status"], "confidence": item["confidence"],
                     "source": item["source"]})

    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    indegree: dict[str, set[str]] = defaultdict(set)
    research_incoming: dict[str, set[str]] = defaultdict(set)
    unresolved_calls: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row, number in _rows(scan, "callsites"):
        caller = _hex(row.get("caller_rva"), "callsite.caller_rva")
        site = _hex(row.get("site_rva"), "callsite.site_rva")
        if caller not in functions:
            raise GraphError(f"callsite {site} caller {caller} missing from scan functions")
        classification = row.get("classification")
        evidence = {"origin": "ghidra_scan", "classification": classification,
                    "site_rva": site, "source": f"{scan}/callsites.jsonl:{number}"}
        if classification == "static_call_reference":
            target = row.get("target_function_entry_rva")
            if target is None:
                unresolved_calls[caller].append({**evidence, "reason": "unmapped_static_target",
                                                  "target_rva": row.get("target_rva")})
                continue
            target = _hex(target, "callsite.target_function_entry_rva")
            if target not in functions:
                unresolved_calls[caller].append({**evidence, "reason": "callee_missing_from_function_scan",
                                                  "target_rva": target})
                continue
            outgoing[caller].append({"from": caller, "to": target, "kind": "direct_call",
                                     "traversable": True, "evidence": evidence})
            indegree[target].add(caller)
        else:
            unresolved_calls[caller].append({**evidence,
                                              "reason": "unresolved_indirect_dispatch" if classification in
                                              ("unresolved_indirect_call", "computed_call_reference")
                                              else "unsupported_callsite_classification",
                                              "target_rva": row.get("target_rva")})

    # Ghidra-identified thunk targets are static forwarding leads, not a
    # verified dynamic class or a gameplay call observation.
    for entry, fn in functions.items():
        target = fn.get("thunk_target_rva")
        if target is not None:
            target = _hex(target, "thunk_target_rva")
            if target in functions:
                outgoing[entry].append({
                    "from": entry, "to": target, "kind": "thunk_forward",
                    "traversable": True, "evidence": {"origin": "ghidra_thunk",
                    "source": fn["source"], "classification": "static_thunk_target"}})
                indegree[target].add(entry)
            else:
                unresolved_calls[entry].append({"reason": "thunk_target_absent_from_scan",
                                                "target_rva": target, "source": fn["source"]})

    datarefs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row, number in _rows(scan, "datarefs"):
        function_rva = _hex(row.get("function_rva"), "dataref.function_rva")
        if function_rva not in functions:
            raise GraphError(f"data reference owner {function_rva} missing from scan functions")
        datarefs[function_rva].append({
            "site_rva": row.get("site_rva"), "target_rva": row.get("target_rva"),
            "target_va": row.get("target_va"),
            "reference_type": row.get("reference_type"),
            "source": f"{scan}/datarefs.jsonl:{number}",
            "interpretation": "static_data_reference_not_proven_field_or_art"})

    for index, rel in enumerate(inv["verified_relationships"]):
        source = _hex(rel["from"]["rva"], "relationship.from")
        target = _hex(rel["to"]["rva"], "relationship.to")
        kind = rel["kind"]
        record = {"from": source, "to": target, "kind": kind,
                  "traversable": kind in FOLLOW_RESEARCH and source in functions and target in functions,
                  "evidence": {"origin": "research_inventory", "index": index,
                               "confidence": rel["confidence"], "context": rel["context"],
                               "source": rel["source"]}}
        if kind not in FOLLOW_RESEARCH and kind not in EXPLICIT_UNRESOLVED:
            raise GraphError(f"unhandled relationship kind {kind}")
        if source in functions:
            outgoing[source].append(record)
        if record["traversable"]:
            research_incoming[target].add(source)

    seed_origins: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for seed in seed_rvas or []:
        seed_origins[_hex(seed, "--seed-rva")].append({"basis": "explicit_user_seed",
                                                         "confidence": "caller_supplied_not_verified"})
    if auto_seeds:
        for suggestion in _candidate_seeds(inv, rawcode, hint, lookup_doc):
            original = suggestion["rva"]
            if original not in functions:
                value = parse_rva(original)
                containing = sorted((entry for low, high, entry in function_ranges
                                     if low <= value <= high),
                                    key=lambda entry: parse_rva(entry))
                if len(containing) == 1:
                    suggestion = {**suggestion, "rva": containing[0],
                                  "address_normalization": {
                                      "inventory_rva": original,
                                      "scan_function_entry_rva": containing[0],
                                      "basis": "unique_ghidra_function_body_containment"}}
            seed_origins[suggestion["rva"]].append(suggestion)
    if not seed_origins:
        raise GraphError("no seeds: provide --seed-rva or a matching curated class label and --lookup")
    if len(seed_origins) > max_nodes:
        raise GraphError(f"{len(seed_origins)} seeds exceed --max-nodes={max_nodes}; "
                         "raise the bound or use --no-auto-seeds and explicit --seed-rva")
    missing_seeds = sorted(r for r in seed_origins if r not in functions)
    if missing_seeds:
        raise GraphError("seed function(s) absent from Ghidra scan: " + ", ".join(missing_seeds))

    depth: dict[str, int] = {}
    queue = deque()
    for seed in sorted(seed_origins):
        depth[seed] = 0
        queue.append(seed)
    edges: list[dict[str, Any]] = []
    omitted = {"depth_limit": 0, "node_limit": 0, "edge_limit": 0, "unresolved_target": 0}
    unresolved_relationship_targets: list[dict[str, Any]] = []
    # Group only identical *logical* edges, never their independent evidence.
    key_to_edge: dict[tuple[str, str, str], dict[str, Any]] = {}
    while queue:
        parent = queue.popleft()
        for item in sorted(outgoing[parent], key=lambda row: (row["to"], row["kind"],
                                                            str(row["evidence"].get("site_rva", "")),
                                                            str(row["evidence"].get("index", "")))):
            target = item["to"]
            if target not in functions:
                omitted["unresolved_target"] += 1
                if len(unresolved_relationship_targets) < max_edges:
                    unresolved_relationship_targets.append({
                        "from": parent, "to": target, "kind": item["kind"],
                        "evidence": item["evidence"],
                        "reason": "target_not_in_analyzed_function_scan"})
                continue
            can_follow = item["traversable"]
            if can_follow and target not in depth:
                if depth[parent] >= max_depth:
                    omitted["depth_limit"] += 1
                    # Keep edge to already covered targets but do not expand frontier.
                    continue
                if len(depth) >= max_nodes:
                    omitted["node_limit"] += 1
                    continue
                depth[target] = depth[parent] + 1
                queue.append(target)
            if target not in depth:
                # Nontraversable edges are still kept as unresolved candidate
                # destinations, but not treated as reached/executed nodes.
                if not can_follow:
                    key = (parent, target, item["kind"])
                    if key not in key_to_edge:
                        if len(edges) >= max_edges:
                            omitted["edge_limit"] += 1
                            continue
                        record = {"from": parent, "to": target, "kind": item["kind"],
                                  "traversable": False, "target_in_graph": False, "evidence": []}
                        key_to_edge[key] = record
                        edges.append(record)
                    key_to_edge[key]["evidence"].append(item["evidence"])
                continue
            key = (parent, target, item["kind"])
            if key not in key_to_edge:
                if len(edges) >= max_edges:
                    omitted["edge_limit"] += 1
                    continue
                record = {"from": parent, "to": target, "kind": item["kind"],
                          "traversable": can_follow, "target_in_graph": True, "evidence": []}
                key_to_edge[key] = record
                edges.append(record)
            key_to_edge[key]["evidence"].append(item["evidence"])

    code: dict[str, dict[str, Any]] = {}
    pcode_store: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pcode_branches: dict[str, list[dict[str, Any]]] = defaultdict(list)
    indirect_pcode: dict[str, list[dict[str, Any]]] = defaultdict(list)
    vtables: list[dict[str, Any]] = []
    for directory in details:
        for row, number in _rows(directory, "decompiled"):
            entry = _hex(row.get("function_rva"), "decompiled.function_rva")
            if entry in depth:
                value = {"status": row.get("status"), "c": row.get("c"),
                         "error": row.get("error"), "source": f"{directory}/decompiled.jsonl:{number}"}
                if entry in code and code[entry] != value:
                    # Same function may be decompiled multiple times; do not
                    # silently select one potentially conflicting export.
                    if code[entry].get("c") != value.get("c") or code[entry]["status"] != value["status"]:
                        raise GraphError(f"conflicting decompilation exports for {entry}")
                code.setdefault(entry, value)
        for row, number in _rows(directory, "pcode"):
            entry = _hex(row.get("function_rva"), "pcode.function_rva")
            if entry not in depth:
                continue
            if row.get("opcode") in ("STORE", "LOAD"):
                pcode_store[entry].append({"site_rva": row.get("site_rva"),
                                           "opcode": row["opcode"], "inputs": row.get("inputs"),
                                           "output": row.get("output"),
                                           "source": f"{directory}/pcode.jsonl:{number}",
                                           "interpretation": "untyped_memory_access_not_proven_field"})
            if row.get("opcode") in ("CBRANCH", "BRANCHIND"):
                pcode_branches[entry].append({"site_rva": row.get("site_rva"),
                                              "opcode": row["opcode"],
                                              "inputs": row.get("inputs"),
                                              "source": f"{directory}/pcode.jsonl:{number}",
                                              "interpretation": "unresolved_branch_semantics"})
            if row.get("opcode") == "CALLIND":
                indirect_pcode[entry].append({"site_rva": row.get("site_rva"),
                                              "source": f"{directory}/pcode.jsonl:{number}",
                                              "reason": "unresolved_indirect_dispatch"})
        for row, number in _rows(directory, "vtables"):
            vtables.append({"source": f"{directory}/vtables.jsonl:{number}",
                            "seed_rva": row.get("seed_rva"),
                            "status": "pointer_table_candidate_only",
                            "slots": row.get("slots", []),
                            "note": "Unbound pointer table; no receiver or class implied."})

    nodes = []
    gaps = []
    for addr in sorted(depth, key=lambda k: (depth[k], k)):
        fn = functions[addr]
        details_available = addr in code and code[addr]["status"] == "complete"
        node = {**fn, "depth": depth[addr], "seed_reasons": seed_origins.get(addr, []),
                "inventory_records": inv_entry_by_rva.get(addr, []),
                "incoming_static_function_count": len(indegree.get(addr, set())),
                "incoming_research_relationship_count": len(research_incoming.get(addr, set())),
                "shared_helper_candidate": len(indegree.get(addr, set())) >= 5,
                "decompile_status": code[addr]["status"] if addr in code else "not_exported",
                "unresolved_calls": unresolved_calls.get(addr, []) + indirect_pcode.get(addr, []),
                "data_reference_count": len(datarefs.get(addr, [])),
                "untyped_memory_access_count": len(pcode_store.get(addr, [])),
                "uninterpreted_branch_count": len(pcode_branches.get(addr, []))}
        nodes.append(node)
        if not details_available:
            gaps.append({"kind": "decompilation_missing_or_failed", "rva": addr})
        if pcode_branches.get(addr):
            gaps.append({"kind": "branch_semantics_unresolved", "rva": addr,
                         "count": len(pcode_branches[addr])})
        if node["unresolved_calls"]:
            gaps.append({"kind": "indirect_or_unmapped_call", "rva": addr,
                         "count": len(node["unresolved_calls"])})
    if any(item["kind"] in EXPLICIT_UNRESOLVED for item in edges):
        gaps.append({"kind": "candidate_dispatch_or_nonimmediate_path",
                     "count": sum(item["kind"] in EXPLICIT_UNRESOLVED for item in edges)})
    if any(omitted.values()):
        gaps.append({"kind": "bounded_traversal", "reasons": omitted})
    return {
        "schema_version": 1, "rawcode": rawcode, "status": "static_candidate_graph",
        "executable_sha256": sha, "class_reference_hint": hint,
        "class_reference_is_native_verified": False,
        "lookup_evidence": lookup_evidence,
        "input_exports": {"scan": str(scan), "detail": [str(p) for p in details]},
        "seeds": [{"rva": key, "basis": seed_origins[key]} for key in sorted(seed_origins)],
        "limits": {"max_depth": max_depth, "max_nodes": max_nodes, "max_edges": max_edges},
        "nodes": nodes, "edges": edges,
        "decompiled": code, "data_references": {addr: datarefs[addr] for addr in depth if datarefs.get(addr)},
        "memory_access_candidates": dict(pcode_store),
        "branch_candidates": dict(pcode_branches),
        "unbound_vtable_candidates": vtables,
        "gaps": gaps, "omitted": omitted,
        "unresolved_relationship_targets": unresolved_relationship_targets,
        "claims": {"runtime_reachability_proven": False, "semantic_state_fields_proven": False,
                   "animation_or_effect_timing_proven": False},
    }


def write_graph(graph: dict[str, Any], directory: Path) -> None:
    """Write a complete graph package to a new path, never overwriting evidence."""
    if directory.exists():
        raise GraphError(f"refusing existing graph directory: {directory}")
    directory.mkdir(parents=True)
    structure = {key: value for key, value in graph.items()
                 if key not in {"decompiled", "data_references", "memory_access_candidates", "branch_candidates"}}
    (directory / "execution-graph.json").write_text(
        json.dumps(structure, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (directory / "data-references.json").write_text(
        json.dumps(graph["data_references"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (directory / "native-code.json").write_text(
        json.dumps(graph["decompiled"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (directory / "memory-access-candidates.json").write_text(
        json.dumps(graph["memory_access_candidates"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (directory / "branch-candidates.json").write_text(
        json.dumps(graph["branch_candidates"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [f"# Static ability graph: `{graph['rawcode']}`", "",
             f"Retail SHA-256: `{graph['executable_sha256']}`", "",
             f"Class reference (unverified): `{graph['class_reference_hint'] or 'none'}`", "",
             f"Functions reached structurally: **{len(graph['nodes'])}**. "
             f"Candidate edges: **{len(graph['edges'])}**. "
             f"Gaps: **{len(graph['gaps'])}**.", "",
             "## Functions", "",
             "| RVA | Depth | Name | Static callers | Decompiled |", "|---|---:|---|---:|---|"]
    for node in graph["nodes"]:
        name = str(node.get("name") or "(unnamed)").replace("|", "\\|")
        lines.append(f"| `{node['rva']}` | {node['depth']} | {name} | "
                     f"{node['incoming_static_function_count']} | {node['decompile_status']} |")
    lines += ["", "## Unresolved questions", ""]
    for gap in graph["gaps"]:
        lines.append(f"- `{gap['kind']}`: `{gap.get('rva', 'graph')}` "
                     f"({gap.get('count', gap.get('reasons', 'needs review'))})")
    lines += ["", "## Evidence boundaries", "",
              "- Curated class/name matches are seed suggestions, not proven factory registration.",
              "- Direct calls are static links; they do not establish that a cast takes that path.",
              "- Research callback edges are preserved with their sources; virtual edges remain unbound.",
              "- Scan data references are static mentions, not confirmed object fields or presentation assets.",
              "- P-code LOAD/STORE entries are untyped memory accesses, not verified state fields.",
              "- P-code CBRANCH/BRANCHIND entries are undecoded branch candidates, not settled conditions.",
              "- Related address mentions and nonimmediate paths do not create direct call edges.", ""]
    (directory / "review.md").write_text("\n".join(lines), encoding="utf-8")
