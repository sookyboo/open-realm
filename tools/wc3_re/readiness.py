"""Patch 12: offline evidence-chain readiness and synthetic end-to-end smoke tests.

No Wine, Retail, game data, Frida, Ghidra, or proprietary archives are used.
Synthetic fixtures are wiring tests; they are NEVER evidence of game behavior.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
from pathlib import Path
from typing import Any

from wc3_re import differential, frida, package, spec
from wc3_re.graph import write_graph
from wc3_re.presentation import write_presentation
from wc3_re.session import inspect_session


class ReadinessError(ValueError):
    """Invalid artifact, broken provenance chain, or unsupported smoke fixture."""


FIXTURES = Path(__file__).resolve().parents[2] / "tests/fixtures/wc3_ability_re"
EXPECTED = ("Apxf", "AOsw")


def _load(path: Path) -> dict[str, Any]:
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ReadinessError(f"cannot load {path}: {exc}") from exc
    if not isinstance(result, dict):
        raise ReadinessError(f"expected JSON object: {path}")
    return result


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tool_preflight(*, sha: str, executable: Path | None = None,
                   ghidra_headless: Path | None = None, audit: Path | None = None,
                   mpqtool: Path | None = None, mdxtool: Path | None = None,
                   data_dir: Path | None = None) -> dict[str, Any]:
    """Presence/hash preflight only: does not execute external tools or attach to Retail."""
    checks: dict[str, str] = {}
    for label, path in (("ghidra_headless", ghidra_headless), ("ability_audit", audit),
                        ("mpqtool", mpqtool), ("mdxtool", mdxtool)):
        checks[label] = "not_configured" if path is None else "present" if path.is_file() else "missing"
    checks["data_dir"] = ("not_configured" if data_dir is None else
                          "present" if data_dir.is_dir() else "missing")
    for binary in ("wine", "winepath"):
        checks[binary] = "present" if shutil.which(binary) else "missing"
    checks["frida_python"] = "present" if importlib.util.find_spec("frida") else "missing"
    checks["x11_display_env"] = "present" if os.environ.get("DISPLAY") else "missing"
    if executable is None:
        checks["retail_executable"] = "not_configured"
    elif not executable.is_file():
        checks["retail_executable"] = "missing"
    elif _hash(executable) != sha:
        raise ReadinessError("local Retail executable SHA-256 differs from pinned evidence")
    else:
        checks["retail_executable"] = "sha256_verified"
    return {"scope": "file_presence_and_hash_only_no_execution_or_runtime_attachment",
            "checks": checks, "fully_configured": all(value in ("present", "sha256_verified")
                                                 for value in checks.values())}


def inspect(root: Path, *, trace: Path | None = None, analysis: Path | None = None,
            output_spec: Path | None = None, session: Path | None = None,
            review: Path | None = None, tool_paths: dict[str, Path | None] | None = None) -> dict[str, Any]:
    """Check immutable provenance across existing artifacts; never create missing ones."""
    root = root.resolve()
    # spec.build enforces digests for lookup, graph, presentation and offline package.
    try:
        report = spec.build(root, analysis=analysis, review=review)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ReadinessError(f"offline evidence integrity failed: {exc}") from exc
    rawcode, sha = report["rawcode"], report["executable_sha256"]
    checks: dict[str, dict[str, Any]] = {}

    def add(name: str, status: str, detail: str) -> None:
        checks[name] = {"status": status, "detail": detail}

    add("offline", "validated", "lookup, provenance, package and supplied cached inputs agree")
    graph_path = root / "graph"
    graph = None
    if graph_path.is_dir():
        graph = package.read_graph(graph_path)
        if graph.get("rawcode") != rawcode or graph.get("executable_sha256") != sha:
            raise ReadinessError("execution graph identity differs from reconstruction")
        add("graph", "validated", "static candidate graph only; no receiver/reachability proof")
    else:
        add("graph", "not_supplied", "Ghidra scan/detail and ability-graph still needed")
    if (root / "presentation").is_dir():
        add("presentation", "validated", "authored/static dependencies only, not playback")
    else:
        add("presentation", "not_supplied", "resolve edition-specific assets when available")
    if trace is not None:
        try:
            plan = _load(trace / "trace-plan.json")
            if graph is None:
                raise ReadinessError("trace plan cannot be checked without graph")
            if plan.get("rawcode") != rawcode or plan.get("executable_sha256") != sha:
                raise ReadinessError("trace plan rawcode/executable differs from reconstruction")
            if plan.get("graph_sha256") != frida._digest(graph):
                raise ReadinessError("trace plan was generated from another/changed graph")
            if not (trace / "agent.js").is_file() or (trace / "agent.js").read_text(encoding="utf-8") != frida._agent_source(plan):
                raise ReadinessError("generated Frida agent no longer matches plan")
            add("trace", "validated", "offline plan integrity only; no trace execution claimed")
        except (OSError, ValueError, KeyError) as exc:
            raise ReadinessError(f"trace provenance failed: {exc}") from exc
    else:
        add("trace", "not_supplied", "optional until dynamic receiver questions require a run")
    if analysis is not None:
        add("analysis", "validated", "comparison evidence linked; open questions remain open")
    else:
        add("analysis", "not_supplied", "static-first follow-up planner has not been provided")
    if output_spec is not None:
        ev = _load(output_spec / "spec-evidence.json")
        if (ev.get("rawcode") != rawcode or ev.get("executable_sha256") != sha or
                ev.get("source_hashes") != report["provenance"] or
                ev.get("guardrails") != report["guardrails"] or
                ev.get("claims") != report["reviewed"]["claims"] or
                ev.get("open_questions") != report["open_questions"]):
            raise ReadinessError("generated specification does not match current reviewed evidence")
        if not (output_spec / "reference/ability.c").is_file() or "#if 0" not in (output_spec / "reference/ability.c").read_text(encoding="utf-8"):
            raise ReadinessError("reference C is missing its nonrunnable guard")
        add("specification", "validated", "review-linked guarded draft, not full Retail parity")
    else:
        add("specification", "not_supplied", "generate via ability-spec after static reconstruction")
    if session is not None:
        try:
            saved, plan, _launch = inspect_session(session)
            if saved["rawcode"] != rawcode or plan["executable_sha256"] != sha:
                raise ReadinessError("prepared session belongs to another ability/executable")
            if trace is not None and Path(saved["plan_dir"]).resolve() != trace.resolve():
                raise ReadinessError("session and supplied trace plan differ")
            add("session", "validated", "archived control/prepared-map identity only; game not checked")
        except (OSError, ValueError, KeyError) as exc:
            raise ReadinessError(f"session preflight failed: {exc}") from exc
    else:
        add("session", "not_supplied", "live integration requires a running, correctly prepared Retail map")
    tools = tool_preflight(sha=sha, **tool_paths) if tool_paths is not None else None
    return {"schema_version": 1, "kind": "wc3_ability_offline_readiness",
            "rawcode": rawcode, "executable_sha256": sha,
            "status": "offline_provenance_valid_not_retail_parity",
            "checks": checks, "tool_prerequisites": tools, "open_questions": len(report["open_questions"]),
            "evidence_boundary": {"native_execution_verified": False,
                                  "runtime_effect_timing_verified": False,
                                  "ability_logic_equivalent": False,
                                  "live_integration_tested": False},
            "next_action": "Resolve prioritized static questions; use targeted Retail probes only for remaining ambiguities"}


def write_readiness(result: dict[str, Any], output: Path) -> None:
    if output.exists():
        raise ReadinessError(f"refusing to overwrite readiness report: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def smoke(*, output: Path, fixtures: Path = FIXTURES) -> dict[str, Any]:
    """Exercise graph→package→Frida plan→static differential→spec using synthetic data."""
    if output.exists():
        raise ReadinessError(f"refusing existing smoke directory: {output}")
    sources: list[tuple[str, Path, dict[str, Any]]] = []
    # Validate every fixture BEFORE creating an output directory.
    for rawcode in EXPECTED:
        path = fixtures / (rawcode + ".json")
        data = _load(path)
        if (data.get("schema_version") != 1 or data.get("fixture_kind") != "synthetic_test_data_only"
                or data.get("rawcode") != rawcode
                or not all(isinstance(data.get(key), dict) for key in
                           ("lookup", "graph", "presentation", "expected"))):
            raise ReadinessError(f"invalid synthetic {rawcode} smoke fixture")
        if any(data[key].get("rawcode") != rawcode for key in ("lookup", "graph", "presentation")):
            raise ReadinessError(f"fixture rawcode mismatch: {rawcode}")
        sources.append((rawcode, path, data))
    output.mkdir(parents=True)
    cases = []
    try:
        for rawcode, path, data in sources:
            home = output / rawcode
            home.mkdir()
            (home / "lookup.json").write_text(json.dumps(data["lookup"], sort_keys=True, indent=2) + "\n", encoding="utf-8")
            write_graph(data["graph"], home / "graph")
            write_presentation(data["presentation"], home / "presentation")
            package.write_package(package.build_package(data["lookup"], graph=data["graph"],
                                                       presentation=data["presentation"]), home / "offline")
            frida.write_trace(frida.plan(package.read_graph(home / "graph"),
                                         capture_id="synthetic-" + rawcode), home / "trace")
            differential.write(differential.analyze(offline=home / "offline"), home / "analysis")
            spec.write(spec.build(home, analysis=home / "analysis"), home / "spec")
            result = inspect(home, trace=home / "trace", analysis=home / "analysis",
                             output_spec=home / "spec")
            if (result["checks"]["graph"]["status"] != "validated" or
                    result["checks"]["specification"]["status"] != "validated" or
                    result["open_questions"] == 0 or
                    _load(home / "spec/spec-evidence.json")["claims"] or
                    _load(home / "analysis/analysis.json")["comparisons"]):
                raise ReadinessError(f"smoke assertions failed for {rawcode}")
            if (data["lookup"]["editions"]["tft"]["retail_class_reference"]["implementation_code"]
                    != data["expected"]["implementation_code"] or
                    data["expected"]["entry_rva"] not in
                    [n["rva"] for n in package.read_graph(home / "graph")["nodes"]]):
                raise ReadinessError(f"fixture expected identity missing for {rawcode}")
            write_readiness(result, home / "readiness.json")
            cases.append({"rawcode": rawcode, "fixture_sha256": _hash(path),
                          "status": "synthetic_offline_pipeline_passed", "open_questions": result["open_questions"]})
    except Exception:
        # Keep partial output for investigation, but do not produce an overall success marker.
        raise
    summary = {"schema_version": 1, "kind": "synthetic_wc3_ability_re_smoke",
               "status": "synthetic_offline_pipeline_passed", "cases": cases,
               "retail_executed": False, "ghidra_executed": False, "warcraft_assets_used": False,
               "verification_scope": "tool wiring and provenance checks only; no Retail gameplay, graphics or audio evidence"}
    (output / "smoke-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary
