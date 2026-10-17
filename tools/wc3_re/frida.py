"""Generate and review bounded, read-only Frida probes from Patch 4 graphs.

A graph describes candidate code, not actual runtime dispatch. No ABI, vtable
receiver, state field, or gameplay outcome is inferred by this module.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any

from wc3_re.graph import GraphError
from wc3_re.package import read_graph
from wc3_re.lookup import check_rawcode


class TraceError(GraphError):
    """Invalid static input, unsafe trace request, or incomplete trace artifact."""


_SHA = re.compile(r"[0-9a-f]{64}\Z")
_RVA = re.compile(r"0x[0-9a-fA-F]{8}\Z")
_MAX_HOOKS = 64
_MAX_EVENTS = 10000
_MAX_SECONDS = 300
_MAX_WORDS = 8


def _rva(value: Any, context: str) -> str:
    if not isinstance(value, str) or not _RVA.fullmatch(value):
        raise TraceError(f"{context}: expected eight-digit hexadecimal function RVA")
    return f"0x{int(value, 16):08x}"


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode("utf-8")).hexdigest()


def plan(graph: dict[str, Any], *, rawcode: str | None = None,
         max_hooks: int = 24, max_events: int = 1200, per_hook_events: int = 120,
         seconds: int = 60, stack_words: int = 0,
         include_rvas: list[str] | None = None,
         include_return_addresses: dict[str, list[str]] | None = None,
         capture_id: str = "offline-plan") -> dict[str, Any]:
    """Choose safe function-entry hooks; indirect instruction sites are review-only."""
    if not isinstance(graph, dict) or graph.get("schema_version") != 1 or graph.get("status") != "static_candidate_graph":
        raise TraceError("expected a Patch 4 static_candidate_graph")
    actual_rawcode = check_rawcode(graph.get("rawcode", ""))
    if rawcode is not None and rawcode != actual_rawcode:
        raise TraceError("requested rawcode does not match execution graph")
    sha = graph.get("executable_sha256")
    if not isinstance(sha, str) or not _SHA.fullmatch(sha):
        raise TraceError("graph lacks lowercase exact-build executable SHA-256")
    if not (1 <= max_hooks <= _MAX_HOOKS and 1 <= max_events <= _MAX_EVENTS and
            1 <= per_hook_events <= max_events and 1 <= seconds <= _MAX_SECONDS and
            0 <= stack_words <= _MAX_WORDS):
        raise TraceError("invalid limits: hooks 1-64, events 1-10000, per-hook 1..events, "
                         "seconds 1-300, stack words 0-8")
    if not isinstance(capture_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", capture_id):
        raise TraceError("capture ID must be 1-80 safe ASCII characters")
    if graph.get("claims", {}).get("runtime_reachability_proven") is not False:
        raise TraceError("input graph must not assert observed runtime reachability")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise TraceError("graph has no nodes or edges")
    by_rva: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise TraceError("malformed function node")
        rva = _rva(node.get("rva"), "node.rva")
        if int(rva, 16) == 0 or rva in by_rva:
            raise TraceError(f"invalid/duplicate function RVA: {rva}")
        if not isinstance(node.get("unresolved_calls"), list):
            raise TraceError(f"node {rva} missing unresolved call list")
        if not isinstance(node.get("depth"), int) or node["depth"] < 0:
            raise TraceError(f"node {rva} missing depth")
        by_rva[rva] = node
    if not by_rva:
        raise TraceError("graph has no functions to trace")

    requested = [_rva(item, "--include-rva") for item in include_rvas or []]
    if len(set(requested)) != len(requested):
        raise TraceError("duplicate --include-rva entry")
    unknown = sorted(set(requested) - set(by_rva))
    if unknown:
        raise TraceError("explicit hooks must be analyzed graph functions: " + ", ".join(unknown))
    seeds = set()
    for item in graph.get("seeds", []):
        if not isinstance(item, dict) or not isinstance(item.get("rva"), str):
            raise TraceError("malformed seed")
        key = _rva(item["rva"], "seed.rva")
        if key not in by_rva:
            raise TraceError(f"seed {key} missing from graph")
        seeds.add(key)
    virtual_sources: set[str] = set()
    unresolved_edges: list[dict[str, Any]] = []
    for edge in edges:
        if not isinstance(edge, dict) or not isinstance(edge.get("evidence"), list):
            raise TraceError("graph edge lacks evidence")
        source = _rva(edge.get("from"), "edge.from")
        target = _rva(edge.get("to"), "edge.to")
        if source not in by_rva:
            raise TraceError(f"edge source absent from graph: {source}")
        if not edge.get("traversable"):
            virtual_sources.add(source)
            unresolved_edges.append({"from": source, "to_candidate": target,
                                     "kind": edge.get("kind"),
                                     "reason": "not_a_bound_runtime_dispatch",
                                     "evidence": edge["evidence"]})
    priority: list[tuple[tuple[int, int, str], str, list[str]]] = []
    for rva, node in by_rva.items():
        reasons = []
        if rva in seeds:
            reasons.append("graph_seed_candidate")
        if node["unresolved_calls"]:
            reasons.append("unresolved_call_in_function")
        if rva in virtual_sources:
            reasons.append("unbound_relationship_source")
        if rva in requested:
            reasons.append("explicit_graph_function_selection")
        if not reasons:
            reasons.append("static_dependency_survey")
        # Select explicit requests, seeds, ambiguity owners, then shallow nodes.
        rank = (0 if rva in requested else 1 if rva in seeds else
                2 if node["unresolved_calls"] or rva in virtual_sources else 3,
                node["depth"], rva)
        priority.append((rank, rva, reasons))
    priority.sort()
    if len(requested) > max_hooks:
        raise TraceError("explicit selections exceed max-hooks")
    selected = priority[:max_hooks]
    # Priority places explicitly requested functions at the front; hard cap is deliberate.
    hooks = [{"rva": rva, "name": str(by_rva[rva].get("name") or ""),
              "depth": by_rva[rva]["depth"], "reasons": reasons,
              "identity": "static_candidate_function_entry_only"}
             for _, rva, reasons in selected]
    missing_requested = sorted(set(requested) - {item["rva"] for item in hooks})
    if missing_requested:
        raise TraceError("explicit selections were truncated: " + ", ".join(missing_requested))
    return_address_filters: dict[str, list[str]] = {}
    for function_value, address_values in (include_return_addresses or {}).items():
        function_rva = _rva(function_value, "--include-return-address function")
        if function_rva not in {hook["rva"] for hook in hooks}:
            raise TraceError(f"return-address filter function is not selected: {function_rva}")
        if not isinstance(address_values, list) or not address_values:
            raise TraceError(f"return-address filter for {function_rva} must not be empty")
        addresses = [_rva(value, "--include-return-address") for value in address_values]
        if len(set(addresses)) != len(addresses):
            raise TraceError(f"duplicate return address for {function_rva}")
        return_address_filters[function_rva] = sorted(addresses)
    for hook in hooks:
        if hook["rva"] in return_address_filters:
            hook["return_addresses"] = return_address_filters[hook["rva"]]
    unresolved_sites = []
    for rva, node in sorted(by_rva.items()):
        for item in node["unresolved_calls"]:
            if not isinstance(item, dict):
                raise TraceError(f"invalid unresolved call in {rva}")
            site = item.get("site_rva")
            if site is not None:
                site = _rva(site, f"unresolved site of {rva}")
            unresolved_sites.append({"function_rva": rva, "site_rva": site,
                                     "reason": item.get("reason"),
                                     "status": "review_only_no_instruction_hook",
                                     "source": item.get("source")})
    # Store review-only vtables verbatim to avoid manufacturing class bindings.
    result = {"schema_version": 1, "kind": "read_only_frida_function_entry_plan",
              "rawcode": actual_rawcode, "executable_sha256": sha,
              "capture_id": capture_id,
              "limits": {"max_hooks": max_hooks, "max_events": max_events,
                         "per_hook_events": per_hook_events, "seconds": seconds,
                         "stack_words": stack_words},
              "selected_hooks": hooks,
              "omitted_function_rvas": [rva for _, rva, _ in priority[max_hooks:]],
              "unresolved_sites": unresolved_sites,
              "candidate_relationships": unresolved_edges,
              "unbound_vtable_candidates": graph.get("unbound_vtable_candidates", []),
              "graph_sha256": _digest(graph),
              "evidence_boundary": {"function_entries_are_candidates": True,
                                    "receiver_identity_confirmed": False,
                                    "calling_conventions_confirmed": False,
                                    "virtual_dispatch_bound": False,
                                    "state_write_semantics_known": False,
                                    "runtime_behavior_verified": False}}
    return result


def _agent_source(result: dict[str, Any]) -> str:
    template = (Path(__file__).parent / "frida_agent_template.js").read_text(encoding="utf-8")
    runtime = {"rawcode": result["rawcode"], "sha256": result["executable_sha256"],
               "capture_id": result["capture_id"], "limits": result["limits"],
               "hooks": [{"rva": entry["rva"], "name": entry["name"],
                          **({"return_addresses": entry["return_addresses"]}
                             if "return_addresses" in entry else {})}
                         for entry in result["selected_hooks"]]}
    # JSON.stringify safe; ASCII-only values escaped by json.dumps.
    js = json.dumps(runtime, sort_keys=True, ensure_ascii=True)
    return (f"// WC3_RETAIL_SHA256: {result['executable_sha256']}\n" +
            template.replace("__WC3_RE_TRACE_CONFIGURATION__", js))


def write_trace(result: dict[str, Any], directory: Path) -> None:
    """Write one immutable instrumentation plan and passive agent."""
    if directory.exists():
        raise TraceError(f"refusing to overwrite trace plan: {directory}")
    js = _agent_source(result)
    directory.mkdir(parents=True)
    (directory / "trace-plan.json").write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (directory / "agent.js").write_text(js, encoding="utf-8")
    (directory / "review.md").write_text(
        f"# Read-only ability trace: {result['rawcode']}\n\n"
        f"Executable SHA-256: `{result['executable_sha256']}`\n\n"
        f"Function-entry hooks: {len(result['selected_hooks'])}; omitted: "
        f"{len(result['omitted_function_rvas'])}.\n\n"
        "These are static *candidate* entry points. Capture reachability, registers, "
        "return sites and raw return values; do not infer arguments, receiver identity, "
        "gameplay semantics, or an ability-specific dispatch solely from a hit.\n\n"
        f"Unresolved indirect call sites: {len(result['unresolved_sites'])}; "
        "none is hooked or assigned a callee.\n\n"
        "The agent is initially armed for a bounded capture window and also exposes "
        "RPC `arm`, `disarm`, `status`, and `setrunid`. Use `disarm` between cases. "
        "Both event and time limits apply even if the host forgets to disarm.\n\n"
        "The surrounding Retail controller must verify the executable hash and "
        "map/process identity before attaching. The agent itself verifies x86 and "
        "that each address is in an executable module range.\n",
        encoding="utf-8")


def run_controller(*, plan_dir: Path, probe_dir: Path, seconds: int,
                   output: Path, controller: Path) -> list[str]:
    """Invoke the existing attach-only controller, if installed. No map/session lifecycle here."""
    plan_path = plan_dir / "trace-plan.json"
    agent_path = plan_dir / "agent.js"
    try:
        saved = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise TraceError(f"cannot read trace plan: {error}") from error
    if saved.get("kind") != "read_only_frida_function_entry_plan":
        raise TraceError("unrecognized Frida plan")
    expected_agent = _agent_source(saved)
    if not agent_path.is_file() or agent_path.read_text(encoding="utf-8") != expected_agent:
        raise TraceError("agent.js differs from the immutable trace plan")
    if not isinstance(seconds, int) or not 1 <= seconds <= saved["limits"]["seconds"]:
        raise TraceError("requested capture exceeds plan duration")
    if output.exists():
        raise TraceError(f"refusing existing trace output: {output}")
    if not controller.is_file():
        raise TraceError(f"attach-only Retail controller not found: {controller}; "
                         "restore tools/frida/trace_wc3_retail.py from the newer research branch "
                         "or use its documented command manually with agent.js")
    if not probe_dir.is_dir() or not (probe_dir / "probe.json").is_file():
        raise TraceError("prepared probe directory with probe.json is required")
    # Do not launch a new Retail process. Controller owns exact-build and map verification.
    command = ["python3", str(controller), str(probe_dir), "--agent", str(agent_path),
               "--seconds", str(seconds), "--output", str(output)]
    subprocess.run(command, check=True)
    return command


def summarize_trace(plan_dir: Path, trace_file: Path) -> dict[str, Any]:
    """Review attach-only controller JSONL without asserting gameplay behavior."""
    config = json.loads((plan_dir / "trace-plan.json").read_text(encoding="utf-8"))
    if config.get("kind") != "read_only_frida_function_entry_plan":
        raise TraceError("invalid saved trace plan")
    agent = plan_dir / "agent.js"
    if not agent.is_file() or agent.read_text(encoding="utf-8") != _agent_source(config):
        raise TraceError("trace agent differs from saved plan")
    agent_sha = hashlib.sha256(agent.read_bytes()).hexdigest()
    allowed = {hook["rva"] for hook in config["selected_hooks"]}
    totals: dict[str, dict[str, int]] = {r: {"enter": 0, "leave": 0} for r in sorted(allowed)}
    run_ids: dict[str, int] = {}
    pending_calls: dict[tuple[str, int, int, str], dict[str, Any]] = {}
    function_calls: dict[str, dict[str, list[dict[str, Any]]]] = {}
    observed: list[dict[str, Any]] = []
    unknown_records = 0
    invalid = []
    meta = []
    ends = []
    failures = []
    with trace_file.open(encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            try:
                record = json.loads(line)
            except ValueError:
                invalid.append(line_no)
                continue
            if not isinstance(record, dict):
                invalid.append(line_no)
                continue
            if record.get("event") == "trace-metadata":
                meta.append(record)
                if (record.get("retail_sha256") != config["executable_sha256"] or
                        record.get("agent_sha256") != agent_sha or
                        record.get("agent_required_retail_sha256") != config["executable_sha256"]):
                    invalid.append(line_no)
                continue
            if record.get("event") == "trace-end":
                ends.append(record)
                if record.get("errors"):
                    failures.append({"line": line_no, "reason": "controller_trace_errors"})
                continue
            if record.get("event") == "frida-error":
                failures.append({"line": line_no, "reason": "frida_error"})
                continue
            # The existing attach controller flattens Frida 'send' payloads,
            # while standalone captures may preserve the original envelope.
            payload = record.get("payload", record)
            if isinstance(payload, dict) and payload.get("type") == "send":
                payload = payload.get("payload", {})
            if not isinstance(payload, dict) or payload.get("source") != "wc3_ability_re_frida":
                unknown_records += 1
                continue
            if payload.get("capture_id") != config["capture_id"] or payload.get("rawcode") != config["rawcode"]:
                invalid.append(line_no)
                continue
            kind = payload.get("kind")
            if kind in ("enter", "leave"):
                rva = payload.get("function_rva")
                if rva not in allowed:
                    invalid.append(line_no)
                    continue
                totals[rva][kind] += 1
                run_id = payload.get("run_id")
                thread_id = payload.get("thread_id")
                invocation_id = payload.get("invocation_id")
                if (not isinstance(run_id, str) or isinstance(thread_id, bool) or
                        not isinstance(thread_id, int) or isinstance(invocation_id, bool) or
                        not isinstance(invocation_id, int)):
                    invalid.append(line_no)
                    continue
                run_ids[run_id] = run_ids.get(run_id, 0) + 1
                call_key = (run_id, thread_id, invocation_id, rva)
                if kind == "enter":
                    if call_key in pending_calls:
                        invalid.append(line_no)
                    else:
                        pending_calls[call_key] = {"return_address_rva": payload.get("return_address_rva")}
                else:
                    pending = pending_calls.pop(call_key, None)
                    value = payload.get("return_value_raw")
                    if pending is None or not isinstance(value, str) or not re.fullmatch(r"0x[0-9a-fA-F]+", value):
                        invalid.append(line_no)
                    else:
                        by_run = function_calls.setdefault(run_id, {})
                        by_function = by_run.setdefault(rva, [])
                        by_function.append({"thread_id": thread_id, "invocation_id": invocation_id,
                                            "return_value_raw": value.lower(),
                                            "return_address_rva": pending["return_address_rva"]})
            elif kind in ("start", "stop", "overflow", "install_error", "hook_limit"):
                observed.append({"line": line_no, "kind": kind,
                                 "function_rva": payload.get("function_rva"),
                                 "reason": payload.get("reason")})
                if kind == "install_error":
                    failures.append({"line": line_no, "reason": kind})
            else:
                unknown_records += 1
    if invalid:
        raise TraceError("trace has malformed or mismatched generated-agent records at lines: " +
                         ", ".join(map(str, invalid[:15])))
    if len(meta) > 1 or len(ends) > 1:
        raise TraceError("trace has duplicate controller metadata or end markers")
    valid_controller_envelope = len(meta) == 1 and len(ends) == 1
    start_seen = any(event["kind"] == "start" for event in observed)
    unpaired = [{"run_id": run_id, "thread_id": thread_id,
                 "invocation_id": invocation_id, "function_rva": rva}
                for run_id, thread_id, invocation_id, rva in sorted(pending_calls)]
    truncated = any(event["kind"] in ("overflow", "hook_limit") for event in observed) or bool(unpaired)
    status = ("inconclusive_trace_setup" if failures or not valid_controller_envelope or not start_seen
              else "partial_native_trace" if truncated else "bounded_native_trace")
    return {"schema_version": 1, "rawcode": config["rawcode"],
            "executable_sha256": config["executable_sha256"],
            "status": status,
            "controller_identity_checked": len(meta) == 1,
            "controller_finished": len(ends) == 1,
            "agent_start_observed": start_seen,
            "truncated": truncated, "errors": failures,
            "function_entry_counts": totals, "event_counts_by_run_id": run_ids,
            "function_calls_by_run_id": function_calls,
            "unpaired_function_calls": unpaired,
            "lifecycle_events": observed, "unclassified_controller_records": unknown_records,
            "not_verified": ["ability_receiver_identity", "calling_conventions",
                             "virtual_dispatch_binding", "gameplay_effects", "animation_timing"]}
