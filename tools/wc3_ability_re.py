#!/usr/bin/env python3
"""Warcraft III Retail ability reconstruction harness (lookup foundation).

Patch 2 resolves authored ability rows and creates reconstruction seeds.
Patch 3 adds Ghidra exports; Patch 4 constructs bounded execution graphs.
Patch 5 resolves authored presentation dependencies and static MDX metadata.
Patch 6 assembles a cacheable, evidence-limited offline reconstruction package.
Patch 7 generates bounded, read-only native Frida trace plans.
Patch 8 coordinates bounded live Frida/JASS captures in a verified, existing Retail session.
Patch 9 generates reusable, bounded JASS laboratory scenarios and session manifests.
Patch 10 correlates archived case/control observations and ranks remaining static-first research.
Patch 11 produces evidence-linked implementation specs and guarded reviewed C references.
Patch 12 adds synthetic end-to-end offline smoke coverage and integrity/readiness checking.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
import sys

from wc3_re.ghidra import GhidraError, export as ghidra_export, validate_export
from wc3_re.graph import GraphError, build_graph, write_graph
from wc3_re.presentation import PresentationError, build_presentation, write_presentation
from wc3_re.package import (PackageError, build_package, read_graph,
                             read_presentation, write_package)
from wc3_re.frida import (TraceError, plan as make_trace_plan, write_trace,
                          run_controller, summarize_trace)
from wc3_re.session import SessionError, create as create_session, run as run_session, inspect_session
from wc3_re.scenarios import ScenarioError, build as build_scenarios, write as write_scenarios
from wc3_re.differential import DifferentialError, analyze as analyze_differentials, write as write_differentials
from wc3_re.spec import SpecError, build as build_spec, write as write_spec
from wc3_re.readiness import (ReadinessError, inspect as inspect_readiness,
                              write_readiness, smoke as smoke_readiness, FIXTURES)
from wc3_re.lookup import (CLASS_REFERENCE, DEFAULT_AUDIT, DEFAULT_DATA, INVENTORY,
                           LookupError, check_executable, check_rawcode, class_reference,
                           load_inventory_identity, resolve)

ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise LookupError(f"refusing to overwrite existing output: {path}")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def options(parser: argparse.ArgumentParser, *, data: bool = True) -> None:
    parser.add_argument("--inventory", type=Path, default=INVENTORY)
    parser.add_argument("--classes", type=Path, default=CLASS_REFERENCE)
    parser.add_argument("--executable", type=Path, help="optional exact-build Retail executable (verify SHA-256)")
    if data:
        parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
        parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)


def print_lookup(payload: dict) -> None:
    print(f"Rawcode: {payload['rawcode']}")
    print(f"Native executable: {payload['executable_identity']['module']} "
          f"({payload['executable_identity']['sha256']})")
    if not payload["executable_check"]["checked"]:
        print("Executable: not supplied/checked (data lookup only)")
    for edition, record in payload["editions"].items():
        print(f"\n{edition.upper()}: " + ("found" if record["found"] else "not found"))
        if not record["found"]:
            continue
        row = record["ability"]
        hint = record["retail_class_reference"]
        print(f"  implementation code: {hint['implementation_code']}")
        print(f"  class reference: {hint['class'] or 'unresolved'} (NOT runtime-verified)")
        print(f"  levels: {row['levels']} / exported ranks: {len(record['ranks'])}")
        print(f"  aliases: {', '.join(record['aliases']) or '(none)'}")
        print(f"  buff references: {', '.join(dict.fromkeys(b for rank in record['ranks'] for b in rank['buff_ids'])) or '(none)'}")
    print("\nState: authored data only; native code, execution and visual timelines pending.")


def _audit_supports_json(audit: Path) -> bool:
    if not audit.is_file():
        return False
    try:
        result = subprocess.run([str(audit.resolve()), "--help"], capture_output=True,
                                text=True, check=False)
    except OSError:
        return False
    return "-json" in result.stdout or "-json" in result.stderr


def command_doctor(args: argparse.Namespace) -> int:
    identity = load_inventory_identity(args.inventory)
    class_rows = class_reference(args.classes)
    check = check_executable(args.executable, identity)
    supports_json = _audit_supports_json(args.audit)
    report = {
        "inventory": "valid", "class_reference_entries": len(class_rows),
        "executable_check": check,
        "audit_present": args.audit.is_file(), "audit_json_supported": supports_json,
        "data_directory_present": args.data_dir.is_dir(),
        "ready_for_lookup": supports_json and args.data_dir.is_dir(),
        "exact_build_executable_checked": check["checked"],
        "native_trace_tools_checked": False,
    }
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for key, value in report.items():
            print(f"{key}: {value}")
    return 0 if report["ready_for_lookup"] else 1


def command_lookup(args: argparse.Namespace) -> int:
    editions = ["roc", "tft"] if args.edition == "both" else [args.edition]
    payload = resolve(args.rawcode, editions, audit=args.audit, data_dir=args.data_dir,
                      inventory=args.inventory, classes_path=args.classes, executable=args.executable)
    if args.output:
        write_json(args.output, payload)
    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print_lookup(payload)
        if args.output:
            print(f"Wrote: {args.output}")
    return 0


def command_index(args: argparse.Namespace) -> int:
    # This is the rawcode/class *reference* index, not a Ghidra function index.
    identity = load_inventory_identity(args.inventory)
    check_executable(args.executable, identity)
    classes = class_reference(args.classes)
    payload = {"schema_version": 1, "kind": "tft_class_reference_only",
               "retail_executable_identity": identity, "source": str(args.classes),
               "note": "Not Ghidra-verified factory, vtable or function evidence.",
               "classes": classes}
    write_json(args.output, payload)
    print(f"Wrote {len(classes)} reference rows: {args.output}")
    return 0


def command_reconstruct(args: argparse.Namespace) -> int:
    editions = ["roc", "tft"] if args.edition == "both" else [args.edition]
    payload = resolve(args.rawcode, editions, audit=args.audit, data_dir=args.data_dir,
                      inventory=args.inventory, classes_path=args.classes, executable=args.executable)
    outdir = args.output_dir or ROOT / "build-re/ability-re" / args.rawcode
    if outdir.exists():
        raise LookupError(f"refusing existing reconstruction directory: {outdir}")
    graph = None
    if args.ghidra_scan:
        graph = build_graph(rawcode=args.rawcode, scan=args.ghidra_scan,
                            inventory=args.inventory, detail=args.ghidra_detail,
                            # A freshly resolved class reference only hints at a class name.
                            # Persist the lookup first, then use it for graph seed selection.
                            seed_rvas=args.seed_rva, auto_seeds=not args.no_auto_seeds,
                            max_depth=args.max_depth, max_nodes=args.max_nodes,
                            max_edges=args.max_edges,
                            lookup_data=payload)
    elif args.ghidra_detail or args.seed_rva:
        raise LookupError("--ghidra-detail/--seed-rva require --ghidra-scan")
    presentation = build_presentation(
        payload, mpqtool=args.mpqtool, mdxtool=args.mdxtool,
        inspect_assets=not args.no_asset_inspection)
    package = build_package(payload, graph=graph, presentation=presentation)
    manifest = {
        "schema_version": 1, "rawcode": args.rawcode, "status": "static_candidate_graph" if graph else "seed_only",
        "sources": {"lookup": "lookup.json", "presentation": "presentation/assets.json",
                    "offline_report": "offline/report.md"},
        "completed_stages": ["inventory_validation", "authored_data_lookup", "offline_class_hint",
                             "static_presentation_dependency_resolution", "offline_report_generation"]
                            + (["static_execution_graph"] if graph else []),
        "pending_stages": ([] if graph else ["ghidra_code_export", "execution_graph"])
                          + ["presentation_runtime_semantics", "runtime_verification_if_needed",
                             "implementation_specification"],
        "warning": "Graph is structural static evidence, not a verified class binding or execution trace."
                   if graph else "Native code/graph not yet exported.",
    }
    outdir.mkdir(parents=True)
    write_json(outdir / "lookup.json", payload)
    write_presentation(presentation, outdir / "presentation")
    if graph:
        write_graph(graph, outdir / "graph")
    write_package(package, outdir / "offline")
    write_json(outdir / "manifest.json", manifest)
    print(f"Created reconstruction: {outdir}")
    print("Authored asset dependencies: presentation/assets.json (not a runtime effect timeline)")
    print("Offline reconstruction report: offline/report.md (no runtime parity claims)")
    if graph:
        print(f"Static graph: {len(graph['nodes'])} functions, {len(graph['edges'])} candidate edges, {len(graph['gaps'])} gaps")
    else:
        print("Native code/graph not exported: supply --ghidra-scan and optional --ghidra-detail.")
    return 0


def command_ability_package(args: argparse.Namespace) -> int:
    """Repackage previously exported static artifacts with no external tools."""
    lookup = json.loads(args.lookup.read_text(encoding="utf-8"))
    graph = read_graph(args.graph) if args.graph else None
    presentation = read_presentation(args.presentation) if args.presentation else None
    result = build_package(lookup, graph=graph, presentation=presentation)
    write_package(result, args.output)
    print(f"Offline ability report: {args.output / 'report.md'}")
    print("Static evidence only; Retail behavior and visual timings are not verified.")
    return 0


def command_ability_presentation(args: argparse.Namespace) -> int:
    try:
        payload = json.loads(args.lookup.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PresentationError(f"cannot load lookup JSON: {error}") from error
    report = build_presentation(payload, mpqtool=args.mpqtool, mdxtool=args.mdxtool,
                                inspect_assets=not args.no_asset_inspection,
                                max_models=args.max_models)
    write_presentation(report, args.output)
    print(f"Static presentation dependency report: {args.output}")
    return 0


def presentation_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mpqtool", type=Path, default=ROOT / "build/bin/mpqtool")
    parser.add_argument("--mdxtool", type=Path, default=ROOT / "build/bin/mdxtool")
    parser.add_argument("--no-asset-inspection", action="store_true",
                        help="collect references only, do not query MPQ/MDX files")


def command_ghidra_export(args: argparse.Namespace) -> int:
    result = ghidra_export(headless=args.headless, project_dir=args.project_dir,
                           project_name=args.project_name, executable=args.executable,
                           output=args.output, inventory=args.inventory,
                           mode=args.mode, rvas=args.rva, vtables=args.vtable_rva,
                           inventory_seeds=args.inventory_seeds,
                           first_import=args.import_first,
                           timeout=args.decompile_timeout, vtable_slots=args.vtable_slots)
    print(f"Ghidra {result['mode']} export: {args.output}")
    print(json.dumps(result['counts'], indent=2, sort_keys=True))
    print("Static code/reference export only: runtime virtual dispatch and class identity not proven.")
    return 0


def command_ghidra_check(args: argparse.Namespace) -> int:
    identity = load_inventory_identity(args.inventory)
    result = validate_export(args.directory, identity['sha256'], args.mode)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def command_ability_graph(args: argparse.Namespace) -> int:
    graph = build_graph(rawcode=args.rawcode, scan=args.scan, detail=args.detail,
                        inventory=args.inventory, lookup=args.lookup,
                        seed_rvas=args.seed_rva, auto_seeds=not args.no_auto_seeds,
                        max_depth=args.max_depth, max_nodes=args.max_nodes,
                        max_edges=args.max_edges)
    write_graph(graph, args.output)
    print(f"Static ability graph: {args.output}")
    print(f"{len(graph['nodes'])} functions, {len(graph['edges'])} structural edges, "
          f"{len(graph['gaps'])} review gaps")
    return 0


def graph_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--seed-rva", action="append", default=[],
                        help="confirmed/selected function start RVA; repeatable")
    parser.add_argument("--no-auto-seeds", action="store_true",
                        help="disable curated-label/class-hint suggestions")
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument("--max-nodes", type=int, default=120)
    parser.add_argument("--max-edges", type=int, default=1000)


def command_ability_trace(args: argparse.Namespace) -> int:
    graph = read_graph(args.graph)
    plan = make_trace_plan(graph, rawcode=args.rawcode, max_hooks=args.max_hooks,
                           max_events=args.max_events, per_hook_events=args.per_hook_events,
                           seconds=args.seconds, stack_words=args.stack_words,
                           include_rvas=args.include_rva, capture_id=args.capture_id)
    if args.executable:
        check_executable(args.executable, {"sha256": plan["executable_sha256"]})
    write_trace(plan, args.output)
    print(f"Generated {len(plan['selected_hooks'])} bounded candidate hooks: {args.output / 'agent.js'}")
    print("The plan is static evidence only; runtime arguments and dispatch remain unverified.")
    return 0


def command_ability_trace_run(args: argparse.Namespace) -> int:
    command = run_controller(plan_dir=args.plan, probe_dir=args.probe_dir,
                             seconds=args.seconds, output=args.output, controller=args.controller)
    print("Controller finished: " + " ".join(command))
    return 0


def command_ability_trace_review(args: argparse.Namespace) -> int:
    result = summarize_trace(args.plan, args.trace)
    if args.output:
        write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def command_ability_session_create(args: argparse.Namespace) -> int:
    created = create_session(plan_dir=args.plan, probe_dir=args.probe_dir,
                             cases_file=args.cases, output_dir=args.output)
    print(f"Prepared offline session: {args.output} ({len(created['cases'])} cases)")
    print("No game launched; a matching prepared map must already be running before session-run.")
    return 0


def command_ability_session_run(args: argparse.Namespace) -> int:
    result = run_session(args.session, remote=args.remote, poll_seconds=args.poll_seconds)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result['status'] == 'ready_for_review' else 2


def command_ability_session_check(args: argparse.Namespace) -> int:
    saved, plan, launch = inspect_session(args.session)
    print(json.dumps({"status": "offline_provenance_valid", "rawcode": saved['rawcode'],
                      "executable_sha256": plan['executable_sha256'],
                      "session_cases": len(saved['cases']),
                      "launch_time_ns": launch['launched_at_ns'],
                      "jhcr_prepared": saved['jhcr_prepared'],
                      "note": "Does not establish a live matching process or gameplay behavior"},
                     indent=2, sort_keys=True))
    return 0


def command_ability_scenarios(args: argparse.Namespace) -> int:
    try:
        source = json.loads(args.spec.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ScenarioError(f"cannot load scenario specification: {error}") from error
    if not isinstance(source, dict) or source.get("rawcode") != args.rawcode:
        raise ScenarioError("scenario rawcode does not match requested rawcode")
    result = build_scenarios(source)
    write_scenarios(result, args.output)
    print(f"Generated {len(result['plan']['cases'])} JASS scenarios for {args.rawcode}: {args.output}")
    print("Install on a verified copied map, then type each case chat command while Frida is armed.")
    print("Generated setup and order markers do not prove native behavior or parity.")
    return 0


def command_ability_analyze(args: argparse.Namespace) -> int:
    result = analyze_differentials(offline=args.offline, lab=args.lab,
                                   sessions=args.session, comparisons=args.comparisons)
    write_differentials(result, args.output)
    print(f"Analyzed {len(result['capture_summaries'])} captures, "
          f"{len(result['comparisons'])} comparisons; "
          f"{result['open_question_count']} questions remain open: {args.output}")
    return 0


def command_ability_spec(args: argparse.Namespace) -> int:
    result = build_spec(args.reconstruction, analysis=args.analysis, review=args.review)
    write_spec(result, args.output)
    print(f"Evidence-linked implementation draft: {args.output / 'implementation.md'}")
    print("Reference C is guarded; unresolved behavior and static/runtime evidence limits are preserved.")
    return 0


def command_ability_readiness(args: argparse.Namespace) -> int:
    result = inspect_readiness(args.reconstruction, trace=args.trace, analysis=args.analysis,
                               output_spec=args.specification, session=args.session,
                               review=args.review,
                               tool_paths={"executable": args.executable, "ghidra_headless": args.ghidra_headless,
                                           "audit": args.audit, "mpqtool": args.mpqtool,
                                           "mdxtool": args.mdxtool, "data_dir": args.data_dir}
                               if args.check_tools else None)
    if args.output:
        write_readiness(result, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def command_ability_smoke(args: argparse.Namespace) -> int:
    result = smoke_readiness(output=args.output, fixtures=args.fixtures)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def command_verify(_args: argparse.Namespace) -> int:
    print("verify is reserved for Patch 10+ semantic analysis; use ability-scenarios and ability-session-* now.",
          file=sys.stderr)
    return 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="inspect local inventory, classes and data readiness")
    options(doctor)
    doctor.add_argument("--format", choices=("text", "json"), default="text")
    doctor.set_defaults(run=command_doctor)
    lookup = commands.add_parser("lookup", help="resolve rawcode against actual ROC/TFT AbilityData")
    lookup.add_argument("rawcode", type=check_rawcode)
    lookup.add_argument("--edition", choices=("roc", "tft", "both"), default="tft")
    lookup.add_argument("--format", choices=("text", "json"), default="text")
    lookup.add_argument("--output", type=Path, help="save a JSON copy; existing files are not overwritten")
    options(lookup)
    lookup.set_defaults(run=command_lookup)
    index = commands.add_parser("index", help="export offline TFT class reference index (not Ghidra)")
    options(index, data=False)
    index.add_argument("--output", type=Path, default=ROOT / "build-re/ability-re/class-reference-index.json")
    index.set_defaults(run=command_index)
    reconstruct = commands.add_parser("reconstruct", help="create lookup or optional static execution-graph package")
    reconstruct.add_argument("rawcode", type=check_rawcode)
    reconstruct.add_argument("--edition", choices=("roc", "tft", "both"), default="tft")
    reconstruct.add_argument("--output-dir", type=Path)
    reconstruct.add_argument("--ghidra-scan", type=Path,
                             help="validated Patch 3 scan directory for an optional static graph")
    reconstruct.add_argument("--ghidra-detail", type=Path, action="append", default=[],
                             help="validated detail export for pseudocode/p-code (repeatable)")
    graph_options(reconstruct)
    presentation_options(reconstruct)
    options(reconstruct)
    reconstruct.set_defaults(run=command_reconstruct)
    package = commands.add_parser("ability-package", help="combine cached lookup, graph and presentation into an offline report")
    package.add_argument("--lookup", type=Path, required=True, help="Patch 2 lookup.json")
    package.add_argument("--graph", type=Path, help="Patch 4 graph directory (includes sidecars)")
    package.add_argument("--presentation", type=Path, help="Patch 5 presentation directory or assets.json")
    package.add_argument("--output", type=Path, required=True, help="new offline report directory")
    package.set_defaults(run=command_ability_package)
    presentation = commands.add_parser("ability-presentation", help="resolve authored art/audio and optional MDX metadata")
    presentation.add_argument("--lookup", type=Path, required=True, help="Patch 2 lookup.json")
    presentation.add_argument("--output", type=Path, required=True, help="new output directory")
    presentation.add_argument("--max-models", type=int, default=128)
    presentation_options(presentation)
    presentation.set_defaults(run=command_ability_presentation)
    ghidra = commands.add_parser("ghidra-export", help="export exact-build Ghidra native evidence")
    ghidra.add_argument("--headless", type=Path, required=True, help="path to Ghidra analyzeHeadless")
    ghidra.add_argument("--project-dir", type=Path, required=True, help="existing Ghidra project parent")
    ghidra.add_argument("--project-name", required=True, help="Ghidra project name")
    ghidra.add_argument("--executable", type=Path, required=True, help="SHA-256 checked Retail PE32")
    ghidra.add_argument("--inventory", type=Path, default=INVENTORY)
    ghidra.add_argument("--output", type=Path, required=True, help="new directory for immutable export")
    ghidra.add_argument("--mode", choices=("scan", "detail"), default="scan")
    ghidra.add_argument("--rva", action="append", default=[], help="function RVA in hex (detail mode)")
    ghidra.add_argument("--vtable-rva", action="append", default=[], help="candidate vtable RVA (detail mode)")
    ghidra.add_argument("--inventory-seeds", action="store_true", help="add explicitly typed inventory entry addresses")
    ghidra.add_argument("--import-first", action="store_true", help="create/analyze a fresh Ghidra project, not -readOnly")
    ghidra.add_argument("--decompile-timeout", type=int, default=60)
    ghidra.add_argument("--vtable-slots", type=int, default=128)
    ghidra.set_defaults(run=command_ghidra_export)
    check = commands.add_parser("ghidra-check", help="validate completed exported JSONL without Ghidra")
    check.add_argument("directory", type=Path)
    check.add_argument("--inventory", type=Path, default=INVENTORY)
    check.add_argument("--mode", choices=("scan", "detail"), required=True)
    check.set_defaults(run=command_ghidra_check)
    graph = commands.add_parser("ability-graph", help="generate bounded static graph from Ghidra and research evidence")
    graph.add_argument("rawcode", type=check_rawcode)
    graph.add_argument("--scan", type=Path, required=True, help="validated Ghidra scan export")
    graph.add_argument("--detail", type=Path, action="append", default=[], help="detail export(s) with decompilation")
    graph.add_argument("--lookup", type=Path, help="Patch 2 lookup.json for class-name seed hints")
    graph.add_argument("--inventory", type=Path, default=INVENTORY)
    graph.add_argument("--output", type=Path, required=True, help="new output directory (never overwrite)")
    graph_options(graph)
    graph.set_defaults(run=command_ability_graph)
    trace = commands.add_parser("ability-trace", help="generate bounded Frida agent from a saved static graph")
    trace.add_argument("rawcode", type=check_rawcode)
    trace.add_argument("--graph", type=Path, required=True, help="Patch 4 graph directory")
    trace.add_argument("--output", type=Path, required=True, help="new trace-plan directory")
    trace.add_argument("--executable", type=Path, help="optional exact-build executable SHA check")
    trace.add_argument("--max-hooks", type=int, default=24)
    trace.add_argument("--max-events", type=int, default=1200)
    trace.add_argument("--per-hook-events", type=int, default=120)
    trace.add_argument("--seconds", type=int, default=60)
    trace.add_argument("--stack-words", type=int, default=0,
                       help="optional raw x86 stack words, NOT inferred arguments")
    trace.add_argument("--include-rva", action="append", default=[],
                       help="select an existing graph function entry (repeatable)")
    trace.add_argument("--capture-id", default="offline-plan")
    trace.set_defaults(run=command_ability_trace)
    trace_run = commands.add_parser("ability-trace-run", help="attach with an installed Retail trace controller")
    trace_run.add_argument("--plan", type=Path, required=True, help="ability-trace directory")
    trace_run.add_argument("--probe-dir", type=Path, required=True, help="prepared-map evidence directory")
    trace_run.add_argument("--seconds", type=int, default=60)
    trace_run.add_argument("--output", type=Path, required=True, help="new trace JSONL file")
    trace_run.add_argument("--controller", type=Path, default=ROOT / "tools/frida/trace_wc3_retail.py")
    trace_run.set_defaults(run=command_ability_trace_run)
    trace_review = commands.add_parser("ability-trace-review", help="summarize saved native trace event counts")
    trace_review.add_argument("--plan", type=Path, required=True)
    trace_review.add_argument("--trace", type=Path, required=True)
    trace_review.add_argument("--output", type=Path)
    trace_review.set_defaults(run=command_ability_trace_review)
    sess_create = commands.add_parser("ability-session-create", help="offline: pin a prepared Retail/JHCR map, generated trace and JASS cases")
    sess_create.add_argument("--plan", type=Path, required=True, help="Patch 7 generated trace plan directory")
    sess_create.add_argument("--probe-dir", type=Path, required=True, help="confirmed prepared-map probe directory")
    sess_create.add_argument("--cases", type=Path, required=True, help="case manifest with distinct run IDs and JASS result files")
    sess_create.add_argument("--output", type=Path, required=True, help="new session directory (no overwrites)")
    sess_create.set_defaults(run=command_ability_session_create)
    sess_run = commands.add_parser("ability-session-run", help="live: attach once and run bounded Frida/JASS captures against existing Retail")
    sess_run.add_argument("--session", type=Path, required=True, help="directory made by ability-session-create")
    sess_run.add_argument("--remote", default="127.0.0.1:27043", help="Frida server endpoint")
    sess_run.add_argument("--poll-seconds", type=float, default=0.1)
    sess_run.set_defaults(run=command_ability_session_run)
    sess_check = commands.add_parser("ability-session-check", help="offline: verify immutable prepared-map session identity")
    sess_check.add_argument("--session", type=Path, required=True)
    sess_check.set_defaults(run=command_ability_session_check)
    scenarios = commands.add_parser("ability-scenarios", help="offline: generate bounded reusable Retail/JASS laboratory scenarios")
    scenarios.add_argument("rawcode", type=check_rawcode)
    scenarios.add_argument("--spec", required=True, type=Path, help="schema_version=1 lab scenario JSON")
    scenarios.add_argument("--output", required=True, type=Path, help="new immutable scenario output directory")
    scenarios.set_defaults(run=command_ability_scenarios)
    analyze = commands.add_parser("ability-analyze", help="offline: compare sampled Retail cases and rank static-first follow-ups")
    analyze.add_argument("--offline", type=Path, required=True, help="Patch 6 offline package directory")
    analyze.add_argument("--lab", type=Path, help="Patch 9 lab-plan.json file or its directory")
    analyze.add_argument("--session", type=Path, action="append", default=[],
                         help="Patch 8 archived session output directory (repeatable)")
    analyze.add_argument("--comparisons", type=Path,
                         help="optional explicit same-session case/control comparison manifest")
    analyze.add_argument("--output", type=Path, required=True, help="new analysis output directory")
    analyze.set_defaults(run=command_ability_analyze)
    verify = commands.add_parser("verify", help="reserved: semantic Retail verification (not yet implemented)")
    verify.add_argument("rawcode", type=check_rawcode)
    spec = commands.add_parser("ability-spec", help="generate evidence-linked, guarded reference C and implementation spec")
    spec.add_argument("--reconstruction", type=Path, required=True,
                      help="Patch 6 reconstruction root containing lookup.json and offline/")
    spec.add_argument("--analysis", type=Path, help="optional Patch 10 analysis.json or analysis directory")
    spec.add_argument("--review", type=Path, help="optional manually reviewed semantic contract JSON")
    spec.add_argument("--output", type=Path, required=True, help="new specification directory")
    spec.set_defaults(run=command_ability_spec)
    readiness = commands.add_parser("ability-readiness", help="offline: check source hashes and cross-stage reconstruction identity")
    readiness.add_argument("--reconstruction", type=Path, required=True)
    readiness.add_argument("--trace", type=Path, help="optional generated Frida trace-plan directory")
    readiness.add_argument("--analysis", type=Path, help="optional Patch 10 differential analysis directory")
    readiness.add_argument("--specification", type=Path, help="optional Patch 11 output directory")
    readiness.add_argument("--session", type=Path, help="optional prepared Retail session directory; no attach")
    readiness.add_argument("--review", type=Path, help="reviewed contract used to build --specification")
    readiness.add_argument("--check-tools", action="store_true", help="check tool presence (never launches/attaches)")
    readiness.add_argument("--executable", type=Path, help="optional pinned Retail executable for SHA check")
    readiness.add_argument("--ghidra-headless", type=Path, help="optional Ghidra analyzeHeadless path")
    readiness.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    readiness.add_argument("--mpqtool", type=Path, default=ROOT / "build/bin/mpqtool")
    readiness.add_argument("--mdxtool", type=Path, default=ROOT / "build/bin/mdxtool")
    readiness.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    readiness.add_argument("--output", type=Path, help="optional immutable JSON readiness report")
    readiness.set_defaults(run=command_ability_readiness)
    smoke = commands.add_parser("ability-smoke", help="offline synthetic integration checks for Apxf and AOsw")
    smoke.add_argument("--output", type=Path, required=True, help="new output directory")
    smoke.add_argument("--fixtures", type=Path, default=FIXTURES, help="test fixtures, not Retail data")
    smoke.set_defaults(run=command_ability_smoke)
    verify.set_defaults(run=command_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.run(args)
    except (LookupError, PresentationError, PackageError, SessionError, ScenarioError, DifferentialError, SpecError, ReadinessError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
