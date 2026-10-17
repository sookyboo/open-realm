"""Patch 10: evidence-bounded offline comparison of ability/JASS/Frida captures.

This is an observation and follow-up planner, NOT automatic Retail parity
verification. It never launches Retail or changes existing research records.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

from wc3_re.frida import summarize_trace, TraceError
from wc3_re.session import inspect_session, SessionError


class DifferentialError(ValueError):
    """Reject malformed, mismatched, or untrusted investigation inputs."""


_ID = re.compile(r"[A-Za-z0-9_.-]{1,80}\Z")
_RVA = re.compile(r"0x[0-9a-fA-F]{8}\Z")
_PRELOAD = re.compile(r'Preload\s*\(\s*"((?:\\.|[^"\\])*)"\s*\)')
_METRICS = {"life_change", "mana_change", "speed_change", "distance_moved",
            "owner_end", "buff_level_end", "function_enter_count", "unit_count_end"}
_STATUSES = {"ready_for_review", "failed", "timeout", "inconclusive", "error"}


def _load(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise DifferentialError(f"cannot read {path}: {error}") from error
    if not isinstance(obj, dict):
        raise DifferentialError(f"expected JSON object: {path}")
    return obj


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def _rva(value: Any) -> bool:
    return isinstance(value, str) and bool(_RVA.fullmatch(value))


def _read_offline(directory: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    questions = _load(directory / "questions.json")
    provenance = _load(directory / "provenance.json")
    coverage = _load(directory / "coverage.json")
    if questions.get("schema_version") != 1 or not isinstance(questions.get("questions"), list):
        raise DifferentialError("offline questions.json is not a Patch 6 question inventory")
    rawcode = questions.get("rawcode")
    if not isinstance(rawcode, str) or re.fullmatch(r"[A-Za-z0-9]{4}", rawcode) is None:
        raise DifferentialError("offline package has no valid rawcode")
    if coverage.get("schema_version") != 1 or coverage.get("rawcode") != rawcode:
        raise DifferentialError("offline coverage/provenance schema mismatch")
    seen = set()
    for item in questions["questions"]:
        if (not isinstance(item, dict) or not isinstance(item.get("id"), str)
                or item["id"] in seen or not isinstance(item.get("kind"), str)
                or not isinstance(item.get("category"), str)
                or not isinstance(item.get("source"), str)
                or not isinstance(item.get("suggested_resolution"), str)
                or item.get("status") != "unresolved"):
            raise DifferentialError("malformed or duplicate offline question")
        seen.add(item["id"])
    return questions, provenance


def _read_lab(path: Path | None, rawcode: str) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    plan = _load(path / "lab-plan.json" if path.is_dir() else path)
    if plan.get("schema_version") != 1 or plan.get("rawcode") != rawcode:
        raise DifferentialError("laboratory plan rawcode/schema mismatch")
    cases = plan.get("cases")
    if not isinstance(cases, list):
        raise DifferentialError("laboratory plan has no cases")
    result = {}
    for row in cases:
        if not isinstance(row, dict) or not isinstance(row.get("run_id"), str) or not _ID.fullmatch(row["run_id"]):
            raise DifferentialError("invalid lab case ID")
        if row["run_id"] in result:
            raise DifferentialError("duplicate lab case ID")
        if (isinstance(row.get("ticks"), bool) or not isinstance(row.get("ticks"), int)
                or not 1 <= row["ticks"] <= 120 or not isinstance(row.get("targets"), list)):
            raise DifferentialError(f"invalid lab sample contract: {row['run_id']}")
        if row.get("kind") not in {"passive", "target", "point", "immediate", "area", "projectile", "buff"}:
            raise DifferentialError("invalid laboratory scenario kind")
        semantics = row.get("acceptance_semantics", "passive_setup" if row["kind"] == "passive" else "issue_order_return")
        if semantics not in ("passive_setup", "issue_order_return"):
            raise DifferentialError(f"invalid acceptance semantics: {row['run_id']}")
        expected = row.get("expected_order_accepted", True if semantics == "issue_order_return" else None)
        if semantics == "issue_order_return" and not isinstance(expected, bool):
            raise DifferentialError(f"invalid expected order outcome: {row['run_id']}")
        if semantics == "passive_setup" and expected is not None:
            raise DifferentialError(f"passive setup cannot declare an order outcome: {row['run_id']}")
        observation = row.get("unit_observation")
        if observation is not None:
            if (not isinstance(observation, dict) or not isinstance(observation.get("unit_ids"), list)
                    or not observation["unit_ids"]
                    or any(not isinstance(code, str) or not re.fullmatch(r"[A-Za-z0-9]{4}", code)
                           for code in observation["unit_ids"])
                    or len(set(observation["unit_ids"])) != len(observation["unit_ids"])
                    or isinstance(observation.get("max_units"), bool)
                    or not isinstance(observation.get("max_units"), int)
                    or not 1 <= observation["max_units"] <= 32):
                raise DifferentialError(f"invalid watched-unit contract: {row['run_id']}")
        result[row["run_id"]] = {**row, "acceptance_semantics": semantics,
                                  "expected_order_accepted": expected}
    return result


def _read_comparisons(path: Path | None, cases: dict[str, Any]) -> list[dict[str, Any]]:
    if path is None:
        return []
    doc = _load(path)
    if doc.get("schema_version") != 1 or not isinstance(doc.get("comparisons"), list):
        raise DifferentialError("comparison manifest requires schema_version=1 and comparisons")
    results = []
    seen = set()
    for item in doc["comparisons"]:
        if not isinstance(item, dict) or set(item) - {
                "id", "case", "control", "metric", "target_index", "buff_rawcode",
                "unit_rawcode", "function_rva", "relation", "tolerance"}:
            raise DifferentialError("unsupported comparison property")
        cid = item.get("id")
        if not isinstance(cid, str) or not _ID.fullmatch(cid) or cid in seen:
            raise DifferentialError("invalid or duplicate comparison ID")
        seen.add(cid)
        if (item.get("case") not in cases or item.get("control") not in cases
                or item["case"] == item["control"]):
            raise DifferentialError(f"{cid}: comparison requires distinct lab case and control")
        if item.get("metric") not in _METRICS or item.get("relation") not in ("same", "different"):
            raise DifferentialError(f"{cid}: unsupported metric or relation")
        tol = item.get("tolerance", 0)
        if isinstance(tol, bool) or not isinstance(tol, (int, float)) or not math.isfinite(tol) or tol < 0:
            raise DifferentialError(f"{cid}: tolerance must be finite and nonnegative")
        index = item.get("target_index", 0)
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise DifferentialError(f"{cid}: invalid target_index")
        if item["metric"] not in ("function_enter_count", "unit_count_end"):
            if index >= len(cases[item["case"]]["targets"]) or index >= len(cases[item["control"]]["targets"]):
                raise DifferentialError(f"{cid}: target_index not present in case and control")
        if item["metric"] == "buff_level_end":
            buff = item.get("buff_rawcode")
            if not isinstance(buff, str) or not re.fullmatch(r"[A-Za-z0-9]{4}", buff):
                raise DifferentialError(f"{cid}: buff comparison needs four-character buff_rawcode")
            if any(buff not in cases[name].get("buff_ids", []) for name in (item["case"], item["control"])):
                raise DifferentialError(f"{cid}: buff must have been observed in both cases")
        if item["metric"] == "function_enter_count" and not _rva(item.get("function_rva")):
            raise DifferentialError(f"{cid}: function_enter_count needs an RVA")
        if item["metric"] == "unit_count_end":
            unit_code = item.get("unit_rawcode")
            if not isinstance(unit_code, str) or not re.fullmatch(r"[A-Za-z0-9]{4}", unit_code):
                raise DifferentialError(f"{cid}: unit_count_end needs a four-character unit_rawcode")
            if any(unit_code not in row.get("unit_observation", {}).get("unit_ids", [])
                   for row in (cases[item["case"]], cases[item["control"]])):
                raise DifferentialError(f"{cid}: unit_rawcode must be observed in both cases")
        results.append({**item, "target_index": index, "tolerance": float(tol)})
    return results


def _decode(value: str) -> str:
    # Only unescape the two JASS escapes used by the existing capture format.
    return re.sub(r'\\(["\\])', r'\1', value)


def _fields(line: str) -> dict[str, str]:
    return dict(part.split("=", 1) for part in line.split()[1:] if "=" in part)


def _parse_result(path: Path, run_id: str, lab: dict[str, Any] | None, rawcode: str) -> dict[str, Any]:
    """Reject stale-looking, truncated, or internally contradictory JASS records."""
    content = path.read_text(encoding="utf-8", errors="replace")
    lines = [_decode(item) for item in _PRELOAD.findall(content)]
    start, done = f"SESSION_START run_id={run_id}", f"SESSION_DONE run_id={run_id}"
    if (lines.count(start) != 1 or lines.count(done) != 1
            or lines.index(start) >= lines.index(done)):
        return {"status": "inconclusive", "reason": "missing, duplicate or out-of-order start/done markers"}
    if any(line.startswith("SESSION_START ") and line != start or
           line.startswith("SESSION_DONE ") and line != done for line in lines):
        return {"status": "inconclusive", "reason": "foreign run markers"}
    segment = lines[lines.index(start) + 1:lines.index(done)]
    if (segment.count("setup_failed=false") != 1 or "setup_failed=true" in segment
            or "buffer_overflow=true" in segment or "observation_truncated=true" in segment):
        return {"status": "inconclusive", "reason": "invalid setup, order or buffer markers"}
    acceptance = [line for line in segment if line in ("accepted=true", "accepted=false")]
    if len(acceptance) != 1:
        return {"status": "inconclusive", "reason": "missing or duplicate accepted marker"}
    acceptance_semantics = (lab or {}).get("acceptance_semantics",
                               "passive_setup" if (lab or {}).get("kind") == "passive" else "issue_order_return")
    observed_acceptance = acceptance[0] == "accepted=true"
    expected_acceptance = (lab or {}).get("expected_order_accepted",
                                        True if acceptance_semantics == "issue_order_return" else None)
    if acceptance_semantics == "issue_order_return":
        if expected_acceptance is None:
            return {"status": "inconclusive", "reason": "order result has no declared expectation"}
        acceptance_result = {"semantics": "Issue*Order return value",
                             "observed": observed_acceptance,
                             "expected": expected_acceptance,
                             "matches_expectation": observed_acceptance == expected_acceptance}
        if observed_acceptance != expected_acceptance:
            return {"status": "expectation_mismatch", "reason": "observed order return differs from the declared expectation",
                    "order_acceptance": acceptance_result}
    elif acceptance_semantics == "passive_setup":
        if not observed_acceptance:
            return {"status": "inconclusive", "reason": "passive setup marker indicates failure"}
        acceptance_result = {"semantics": "passive ability setup", "observed": True,
                             "expected": True, "matches_expectation": True}
    else:
        return {"status": "inconclusive", "reason": "unknown acceptance semantics"}
    if lab is not None and f"ability={rawcode} mode=generated_lab" not in segment:
        return {"status": "inconclusive", "reason": "laboratory rawcode marker missing"}
    samples: dict[str, dict[int, dict[str, float | int]]] = defaultdict(dict)
    buffs: dict[str, dict[int, int]] = defaultdict(dict)
    spells = []
    unit_counts: dict[str, dict[int, int]] = defaultdict(dict)
    units: dict[str, dict[int, dict[int, dict[str, float | int]]]] = defaultdict(lambda: defaultdict(dict))
    for line in segment:
        if line.startswith("OBS "):
            fields = _fields(line)
            role = fields.get("role")
            try:
                tick = int(fields["tick"])
                t = float(fields["time"])
                if tick < 0 or not math.isfinite(t):
                    raise ValueError()
                key = "caster" if role == "caster" else f"target:{int(fields['index'])}"
                if role not in ("caster", "target") or tick in samples[key]:
                    raise ValueError()
                values: dict[str, float | int] = {"time": t}
                for field in ("life", "mana", "speed", "x", "y"):
                    if field in fields:
                        values[field] = float(fields[field])
                        if not math.isfinite(values[field]):
                            raise ValueError()
                if "owner" in fields:
                    values["owner"] = int(fields["owner"])
                samples[key][tick] = values
            except (ValueError, KeyError, TypeError):
                return {"status": "inconclusive", "reason": "malformed or duplicate observation"}
        elif line.startswith("BUFF "):
            fields = _fields(line)
            try:
                key = f"target:{int(fields['target'])}:{fields['rawcode']}"
                tick, level = int(fields["tick"]), int(fields["level"])
                if tick < 0 or level < 0 or tick in buffs[key]:
                    raise ValueError()
                buffs[key][tick] = level
            except (ValueError, KeyError, TypeError):
                return {"status": "inconclusive", "reason": "malformed or duplicate buff observation"}
        elif line.startswith("SPELL "):
            spells.append(_fields(line))
        elif line.startswith("UNIT_COUNT "):
            fields = _fields(line)
            try:
                raw = fields["rawcode"]
                tick, count = int(fields["tick"]), int(fields["count"])
                if (not re.fullmatch(r"[A-Za-z0-9]{4}", raw) or tick < 0 or count < 0
                        or tick in unit_counts[raw]):
                    raise ValueError()
                unit_counts[raw][tick] = count
            except (ValueError, KeyError, TypeError):
                return {"status": "inconclusive", "reason": "malformed or duplicate unit count"}
        elif line.startswith("UNIT "):
            fields = _fields(line)
            try:
                raw = fields["rawcode"]
                tick, index, owner = int(fields["tick"]), int(fields["index"]), int(fields["owner"])
                values = {key: float(fields[key]) for key in ("x", "y")}
                if (not re.fullmatch(r"[A-Za-z0-9]{4}", raw) or tick < 0 or index < 0 or owner < 0
                        or any(not math.isfinite(value) for value in values.values())
                        or index in units[raw][tick]):
                    raise ValueError()
                units[raw][tick][index] = {"owner": owner, **values}
            except (ValueError, KeyError, TypeError):
                return {"status": "inconclusive", "reason": "malformed or duplicate unit observation"}
        elif line.startswith("UNIT_SCAN_TRUNCATED "):
            return {"status": "inconclusive", "reason": "watched-unit enumeration was truncated"}
    if lab is not None and "ticks" in lab:
        max_tick = lab["ticks"]
        keys = ["caster", *(f"target:{i}" for i in range(len(lab["targets"])))]
        if set(samples) != set(keys) or any(set(samples.get(key, {})) != set(range(max_tick + 1)) for key in keys):
            return {"status": "inconclusive", "reason": "missing or extra lab observation ticks"}
        expected_buffs = {f"target:{i}:{buff}" for i in range(len(lab["targets"])) for buff in lab.get("buff_ids", [])}
        if set(buffs) != expected_buffs or any(set(buffs.get(f"target:{i}:{buff}", {})) != set(range(max_tick + 1))
               for i in range(len(lab["targets"])) for buff in lab.get("buff_ids", [])):
            return {"status": "inconclusive", "reason": "missing or extra buff ticks"}
        watch = lab.get("unit_observation")
        expected_unit_codes = set(watch["unit_ids"]) if watch else set()
        if set(unit_counts) != expected_unit_codes:
            return {"status": "inconclusive", "reason": "missing or extra watched-unit counts"}
        if watch:
            for raw in expected_unit_codes:
                if set(unit_counts[raw]) != set(range(max_tick + 1)):
                    return {"status": "inconclusive", "reason": "missing watched-unit count ticks"}
                if set(units[raw]) - set(range(max_tick + 1)):
                    return {"status": "inconclusive", "reason": "extra watched-unit observation ticks"}
                for tick, count in unit_counts[raw].items():
                    rows = units[raw].get(tick, {})
                    if len(rows) != count or set(rows) != set(range(count)):
                        return {"status": "inconclusive", "reason": "watched-unit count does not match identity rows"}
        interval = lab.get("sample_interval_seconds")
        if isinstance(interval, (int, float)) and interval > 0:
            if any(abs(row["time"] - tick * interval) > 0.002
                   for rows in samples.values() for tick, row in rows.items()):
                return {"status": "inconclusive", "reason": "observation time disagrees with nominal timer"}
    return {"status": "sampled", "samples": samples, "buffs": buffs,
            "order_acceptance": acceptance_result,
            "unit_counts": unit_counts, "units": units,
            "spells": spells, "preload_lines": len(lines),
            "limitation": "Issue*Order return, observed native validation, and observed summoned units are separate evidence"}


def _metric(capture: dict[str, Any], item: dict[str, Any]) -> float | int | None:
    m = item["metric"]
    if m == "function_enter_count":
        row = capture["native_counts"].get(item["function_rva"].lower())
        return row.get("enter") if row else None
    if m == "unit_count_end":
        case = capture["lab"]
        return capture["jass"]["unit_counts"].get(item["unit_rawcode"], {}).get(case["ticks"])
    i = item["target_index"]
    if m == "buff_level_end":
        case = capture["lab"]
        return capture["jass"]["buffs"].get(f"target:{i}:{item['buff_rawcode']}", {}).get(case["ticks"])
    ticks = capture["lab"]["ticks"]
    rows = capture["jass"]["samples"].get(f"target:{i}", {})
    first, last = rows.get(0), rows.get(ticks)
    if first is None or last is None:
        return None
    if m == "owner_end":
        return last.get("owner")
    if m == "distance_moved":
        if not all(k in first and k in last for k in ("x", "y")):
            return None
        return math.hypot(last["x"] - first["x"], last["y"] - first["y"])
    field = {"life_change": "life", "mana_change": "mana", "speed_change": "speed"}.get(m)
    if field is None or field not in first or field not in last:
        return None
    return last[field] - first[field]


def _load_sessions(paths: list[Path], rawcode: str, sha: str | None,
                   lab: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cases: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    unique_paths = set()
    for path in paths:
        directory = path.resolve()
        if directory in unique_paths:
            raise DifferentialError("duplicate session directory")
        unique_paths.add(directory)
        try:
            saved, plan, _launch = inspect_session(directory)
        except (SessionError, OSError, KeyError, TypeError, ValueError) as error:
            raise DifferentialError(f"invalid session {directory}: {error}") from error
        if saved["rawcode"] != rawcode or plan["rawcode"] != rawcode:
            raise DifferentialError("session and offline package ability rawcodes differ")
        if sha and plan["executable_sha256"] != sha:
            raise DifferentialError("session and offline package Retail executable hashes differ")
        run_summary = _load(directory / "run-summary.json") if (directory / "run-summary.json").exists() else None
        if run_summary and (run_summary.get("rawcode") != rawcode or not isinstance(run_summary.get("cases"), list)):
            raise DifferentialError("session run-summary identity mismatch")
        if run_summary and any(not isinstance(row, dict) for row in run_summary["cases"]):
            raise DifferentialError("malformed run-summary case")
        reports = {row.get("run_id"): row for row in run_summary["cases"]} if run_summary else {}
        if run_summary and len(reports) != len(run_summary["cases"]):
            raise DifferentialError("duplicate or malformed run-summary cases")
        if set(reports) - {row["run_id"] for row in saved["cases"]}:
            raise DifferentialError("run-summary contains a case absent from immutable session manifest")
        session_id = f"session-{len(sources) + 1:03d}"
        sources.append({"session_id": session_id, "directory": str(directory),
                        "session_manifest_sha256": _sha(directory / "session.json"),
                        "run_summary_sha256": _sha(directory / "run-summary.json") if run_summary else None,
                        "executable_sha256": plan["executable_sha256"],
                        "prepared_map_sha256": saved["prepared_map_sha256"]})
        for row in saved["cases"]:
            run_id = row["run_id"]
            output = directory / run_id
            evidence = {"session_id": session_id, "run_id": run_id,
                        "status": "inconclusive", "reason": "case not captured",
                        "lab": lab.get(run_id), "native_counts": {}, "jass": {},
                        "trace_status": "not_captured"}
            if lab and run_id not in lab:
                raise DifferentialError(f"{run_id}: session case absent from supplied lab plan")
            if lab and str(Path(row["result_file"]).resolve()) != str(Path(lab[run_id]["result_file"]).resolve()):
                raise DifferentialError(f"{run_id}: JASS result path differs from lab plan")
            if (run_id not in reports or not (output / "review.json").is_file()
                    or not (output / "trace.jsonl").is_file() or not (output / "result.txt").is_file()):
                cases.append(evidence)
                continue
            review = _load(output / "review.json")
            if review.get("run_id") != run_id or review.get("status") not in _STATUSES:
                raise DifferentialError("case review identity or status invalid")
            if review["status"] != reports[run_id].get("status"):
                raise DifferentialError("case status differs from run-summary")
            try:
                native = summarize_trace(Path(saved["plan_dir"]), output / "trace.jsonl")
            except (OSError, TraceError, ValueError) as error:
                evidence["reason"] = f"invalid native trace: {error}"
                cases.append(evidence)
                continue
            if (native["rawcode"] != rawcode or native["executable_sha256"] != plan["executable_sha256"]
                    or review.get("native_trace_status") != native["status"]
                    or review.get("native_counts_by_run_id") != native["event_counts_by_run_id"]):
                raise DifferentialError("case Frida trace and review disagree")
            if ("native_function_calls_by_run_id" in review and
                    review["native_function_calls_by_run_id"] !=
                    native.get("function_calls_by_run_id", {}).get(run_id, {})):
                raise DifferentialError("case Frida return values and review disagree")
            case_contract = lab.get(run_id)
            if case_contract is None and row.get("acceptance_semantics"):
                case_contract = {"acceptance_semantics": row["acceptance_semantics"],
                                 "expected_order_accepted": row.get("expected_order_accepted")}
            if review.get("jass_result_sha256") and review["jass_result_sha256"] != _sha(output / "result.txt"):
                raise DifferentialError(f"{run_id}: JASS capture changed after session review")
            if review.get("trace_sha256") and review["trace_sha256"] != _sha(output / "trace.jsonl"):
                raise DifferentialError(f"{run_id}: native trace changed after session review")
            observations = _parse_result(output / "result.txt", run_id, case_contract, rawcode)
            evidence.update({"trace_status": native["status"], "jass": observations,
                             "native_counts": native["function_entry_counts"],
                             "native_function_calls": native.get("function_calls_by_run_id", {}).get(run_id, {}),
                             "trace_sha256": _sha(output / "trace.jsonl"),
                             "jass_sha256": _sha(output / "result.txt"),
                             "native_events_by_run_id": native["event_counts_by_run_id"]})
            foreign = set(native["event_counts_by_run_id"]) - {run_id}
            if observations["status"] == "expectation_mismatch":
                evidence.update({"status": "expectation_mismatch", "reason": observations["reason"]})
            elif review["status"] == "failed":
                evidence.update({"status": "failed", "reason": "session classified expected-outcome mismatch"})
            elif (review["status"] == "ready_for_review" and
                    native["status"] == "bounded_native_trace" and
                    observations["status"] == "sampled" and not foreign and
                    review.get("jass_result_fresh") is True):
                evidence.update({"status": "usable_observation", "reason": None})
            else:
                evidence["reason"] = observations.get("reason") or "incomplete, stale or unbounded evidence"
            cases.append(evidence)
    return cases, sources


def _compare(comparisons: list[dict[str, Any]], captures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_session: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for capture in captures:
        by_session[capture["session_id"]][capture["run_id"]] = capture
    outcome = []
    for item in comparisons:
        pairs = []
        missing = []
        for session_id, recorded in by_session.items():
            if item["case"] not in recorded and item["control"] not in recorded:
                continue
            if item["case"] not in recorded or item["control"] not in recorded:
                missing.append(session_id)
                continue
            a, b = recorded[item["case"]], recorded[item["control"]]
            if a["status"] != "usable_observation" or b["status"] != "usable_observation":
                missing.append(session_id)
                continue
            x, y = _metric(a, item), _metric(b, item)
            if x is None or y is None:
                missing.append(session_id)
                continue
            delta = abs(x - y)
            met = delta <= item["tolerance"] if item["relation"] == "same" else delta > item["tolerance"]
            pairs.append({"session_id": session_id, "case_value": x, "control_value": y,
                          "absolute_difference": delta, "matches_relation": met})
        status = ("inconclusive" if not pairs or missing else
                  "observed_consistent" if all(p["matches_relation"] for p in pairs) else
                  "observed_not_matching")
        outcome.append({"id": item["id"], "case": item["case"], "control": item["control"],
                        "metric": item["metric"], "relation": item["relation"],
                        "tolerance": item["tolerance"], "status": status,
                        "paired_observations": pairs, "incomplete_sessions": missing,
                        "claim_boundary": "sampled difference only; no proof of causation, native ownership or full Retail parity"})
    return outcome


def _rank_questions(questions: list[dict[str, Any]], captures: list[dict[str, Any]],
                    comparisons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Static work before additional live probes; deterministic and deduplicated."""
    native_hits = any(any(row.get("enter", 0) for row in cap.get("native_counts", {}).values())
                      for cap in captures if cap["status"] == "usable_observation")
    has_incomplete = any(cap["status"] != "usable_observation" for cap in captures)
    pending = []
    seen = set()
    for q in questions:
        kind, category = q["kind"], q["category"]
        if "decompilation" in kind or "missing_relationship" in kind or "no_execution_graph" == kind:
            strategy, priority = "ghidra_detail", 1
        elif "class_binding" in kind or "virtual" in kind or "dispatch" in kind or "indirect" in kind:
            strategy, priority = "static_dispatch_then_frida_if_needed", 2
        elif category == "presentation":
            strategy, priority = "static_asset_or_native_presentation_review", 3
        else:
            strategy, priority = "static_code_and_data_review", 2
        # Preserve unique question evidence but group identical work by kind/source.
        group = (strategy, kind, q.get("source", ""))
        if group in seen:
            for prior in pending:
                if prior["group_key"] == list(group):
                    prior["question_ids"].append(q["id"])
                    break
            continue
        seen.add(group)
        pending.append({"priority": priority, "strategy": strategy,
                        "group_key": list(group), "question_ids": [q["id"]],
                        "next_step": q.get("suggested_resolution", "Inspect existing evidence"),
                        "needs_retail_run": False,
                        "reason": "Reuse static exports first; runtime experiment only for remaining measurable ambiguity"})
    if has_incomplete:
        pending.append({"priority": 4, "strategy": "repair_incomplete_existing_capture",
                        "group_key": ["replay_failed_capture"], "question_ids": [],
                        "next_step": "Inspect setup markers, truncated trace, runtime budget and JASS completion before replaying any case",
                        "needs_retail_run": "only_after_failure_review",
                        "reason": "Failed or partial captures are not negative gameplay evidence"})
    if native_hits:
        pending.append({"priority": 3, "strategy": "interpret_reachable_native_calls",
                        "group_key": ["review_dynamic_receivers"], "question_ids": [],
                        "next_step": "Map observed functions to their owning object/caller and authored fields in Ghidra",
                        "needs_retail_run": False,
                        "reason": "A function hit does not establish receiver or gameplay semantics"})
    for cmp in comparisons:
        if cmp["status"] == "observed_not_matching":
            pending.append({"priority": 3, "strategy": "review_differential_counterexample",
                            "group_key": ["comparison", cmp["id"]], "question_ids": [],
                            "next_step": f"Review case/control confounds and native branches for {cmp['id']} before changing its hypothesis",
                            "needs_retail_run": False,
                            "reason": "Unexpected observation should be inspected before scheduling another game run"})
    return sorted(pending, key=lambda item: (item["priority"], item["strategy"], item["group_key"]))


def analyze(*, offline: Path, lab: Path | None = None, sessions: list[Path] | None = None,
            comparisons: Path | None = None) -> dict[str, Any]:
    questions, provenance = _read_offline(offline)
    rawcode = questions["rawcode"]
    sha = provenance.get("executable_sha256")
    if sha is not None and (not isinstance(sha, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", sha)):
        raise DifferentialError("offline provenance executable hash malformed")
    lab_cases = _read_lab(lab, rawcode)
    pair_specs = _read_comparisons(comparisons, lab_cases)
    captures, sources = _load_sessions(sessions or [], rawcode, sha, lab_cases)
    for cap in captures:
        if cap["lab"] is None and lab is not None:
            raise DifferentialError("capture lacks a matching lab scenario")
    observed = _compare(pair_specs, captures)
    todo = _rank_questions(questions["questions"], captures, observed)
    return {"schema_version": 1, "kind": "retail_ability_differential_review",
            "rawcode": rawcode, "executable_sha256": sha,
            "status": "observation_and_followup_plan_not_parity_proof",
            "offline_inputs": {name: _sha(offline / name) for name in
                               ("questions.json", "provenance.json", "coverage.json")},
            "lab_sha256": _sha(lab / "lab-plan.json" if lab and lab.is_dir() else lab) if lab else None,
            "comparisons_sha256": _sha(comparisons) if comparisons else None,
            "sessions": sources,
            "capture_summaries": [{key: value for key, value in cap.items()
                                  if key not in ("jass", "lab", "native_counts")}
                                  | {"native_entry_counts": {rva: x["enter"] for rva, x in cap["native_counts"].items()},
                                     "native_function_calls": cap.get("native_function_calls", {}),
                                     "order_acceptance": cap["jass"].get("order_acceptance"),
                                     "unit_counts": {raw: {str(tick): count for tick, count in ticks.items()}
                                                     for raw, ticks in cap["jass"].get("unit_counts", {}).items()},
                                     "unit_observations": {raw: {str(tick): [
                                         {"index": index, **row}
                                         for index, row in sorted(records.items())]
                                         for tick, records in ticks.items()}
                                         for raw, ticks in cap["jass"].get("units", {}).items()},
                                     "jass_sample_status": cap["jass"].get("status", "missing"),
                                     "jass_sample_reason": cap["jass"].get("reason")}
                                 for cap in captures],
            "comparisons": observed,
            "open_question_count": len(questions["questions"]),
            "question_actions": todo,
            "policy": {"static_first": True, "questions_auto_resolved": False,
                       "retail_rerun_by_default": False,
                       "native_entry_hit_is_not_receiver_proof": True,
                       "observation_is_not_causality_or_parity": True}}


def write(report: dict[str, Any], directory: Path) -> None:
    if directory.exists():
        raise DifferentialError(f"refusing to overwrite: {directory}")
    directory.mkdir(parents=True)
    (directory / "analysis.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    text = [f"# Ability differential review: {report['rawcode']}", "",
            "**Not Retail parity proof.** This report compares only complete, bounded observations.",
            "Authored data, static relationships and observations remain separately scoped.", "",
            f"Captured cases: {len(report['capture_summaries'])}; paired comparisons: {len(report['comparisons'])}.",
            f"Unresolved offline questions: {report['open_question_count']}; automatically closed: **0**.", "",
            "## Paired observations", ""]
    if not report["comparisons"]:
        text.append("No explicit case/control comparisons. Supply a comparison manifest to interpret sampled differences.")
    for row in report["comparisons"]:
        text.append(f"- `{row['id']}`: **{row['status']}** ({row['metric']}, {row['relation']}); "
                    f"{len(row['paired_observations'])} complete pair(s), {len(row['incomplete_sessions'])} incomplete session(s)")
    text.extend(["", "## Prioritized follow-ups (static-first)", ""])
    for row in report["question_actions"]:
        text.append(f"- P{row['priority']}: {row['strategy']} ({', '.join(row['question_ids']) or 'capture review'}): "
                    + str(row["next_step"]).replace("\n", " "))
    text.extend(["", "## Evidence rules", "",
                 "- Native function-entry counts are not ability receiver/virtual dispatch proofs.",
                 "- A JASS accepted order is not proof that an impact or status was applied.",
                 "- Sampled equality/difference does not establish a full formula or causation.",
                 "- Missing, rejected, overflowing or truncated captures are inconclusive, not negative results.",
                 "- Do not update the permanent function inventory or close questions automatically.", ""])
    (directory / "review.md").write_text("\n".join(text), encoding="utf-8")
