"""Patch 11: source-linked, fail-closed Warcraft III ability implementation drafts.

A static call graph and sampled Retail differences do not imply semantic parity.
Only explicitly reviewed contracts supply implementation steps or executable-looking
C fragments; generated source is guarded from accidental compilation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from wc3_re.package import _digest, PackageError


class SpecError(ValueError):
    """Incompatible, malformed or misleading reconstruction specification evidence."""


_RVA = re.compile(r"0x[0-9a-fA-F]{8}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}\Z")
_DOMAINS = {"validation", "resources", "activation", "targeting", "impact",
            "periodic", "status", "lifecycle", "animation", "visuals", "audio"}
_STAGES = {"registration", "initialization", "validation", "resources",
           "cast_start", "activation", "launch", "travel", "impact", "periodic",
           "channel", "refresh", "expiry", "cancellation", "dispel", "death",
           "removal", "level_change", "enable", "disable"}
_COMPARISON = {"observed_consistent", "observed_not_matching", "inconclusive"}


def _load(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SpecError(f"cannot read {path}: {error}") from error
    if not isinstance(obj, dict):
        raise SpecError(f"expected JSON object: {path}")
    return obj


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as error:
        raise SpecError(f"missing source file {path}: {error}") from error
    return digest.hexdigest()


def _text(value: Any, label: str, *, limit: int = 8000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise SpecError(f"{label}: expected nonempty text of at most {limit} characters")
    return value


def _single_line(value: Any) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").replace("|", "\\|").replace("`", "'")


def _identity(rawcode: Any, sha: Any, label: str) -> None:
    if not isinstance(rawcode, str) or not re.fullmatch(r"[A-Za-z0-9]{4}", rawcode):
        raise SpecError(f"{label}: invalid rawcode")
    if sha is not None and (not isinstance(sha, str) or not _SHA.fullmatch(sha)):
        raise SpecError(f"{label}: invalid executable sha256")


def _source_inputs(root: Path) -> dict[str, Any]:
    lookup = _load(root / "lookup.json")
    offline = root / "offline"
    deps = _load(offline / "dependencies.json")
    coverage = _load(offline / "coverage.json")
    questions = _load(offline / "questions.json")
    provenance = _load(offline / "provenance.json")
    _identity(lookup.get("rawcode"), provenance.get("executable_sha256"), "offline provenance")
    rawcode = lookup["rawcode"]
    if lookup.get("schema_version") != 1 or not isinstance(lookup.get("editions"), dict):
        raise SpecError("lookup schema invalid")
    if coverage.get("schema_version") != 1 or coverage.get("rawcode") != rawcode:
        raise SpecError("coverage rawcode/schema mismatch")
    if questions.get("schema_version") != 1 or questions.get("rawcode") != rawcode or not isinstance(questions.get("questions"), list):
        raise SpecError("questions rawcode/schema mismatch")
    identity = lookup.get("executable_identity")
    if not isinstance(identity, dict):
        raise SpecError("lookup executable identity missing")
    sha = identity.get("sha256")
    if sha != provenance.get("executable_sha256"):
        raise SpecError("lookup and package executable hashes differ")
    digests = provenance.get("input_digests")
    if not isinstance(digests, dict) or digests.get("lookup") != _digest(lookup):
        raise SpecError("lookup was changed or package provenance is missing")
    for name in ("graph", "presentation"):
        if digests.get(name) is not None:
            if name == "graph":
                from wc3_re.package import read_graph
                imported = read_graph(root / "graph")
            else:
                from wc3_re.package import read_presentation
                imported = read_presentation(root / "presentation")
            if provenance["input_digests"][name] != _digest(imported):
                raise SpecError(f"{name} changed after building the offline report")
    funcs = deps.get("functions")
    if not isinstance(funcs, list) or not isinstance(deps.get("presentation"), dict):
        raise SpecError("offline dependencies missing functions/presentation")
    function_rvas = set()
    for item in funcs:
        if not isinstance(item, dict) or not isinstance(item.get("rva"), str) or not _RVA.fullmatch(item["rva"]):
            raise SpecError("invalid function entry in offline dependencies")
        function_rvas.add(item["rva"].lower())
    ids = set()
    for q in questions["questions"]:
        if not isinstance(q, dict) or not isinstance(q.get("id"), str) or q["id"] in ids or q.get("status") != "unresolved":
            raise SpecError("invalid/duplicate offline question")
        ids.add(q["id"])
    sources = {name: _hash_file(offline / name) for name in
               ("dependencies.json", "coverage.json", "questions.json", "provenance.json", "native/decompiled.c")}
    sources["lookup.json"] = _hash_file(root / "lookup.json")
    return {"rawcode": rawcode, "sha": sha, "lookup": lookup, "deps": deps,
            "coverage": coverage, "questions": questions["questions"],
            "function_rvas": function_rvas, "source_hashes": sources}


def _analysis(source: dict[str, Any], file: Path | None) -> dict[str, Any] | None:
    if file is None:
        return None
    obj = _load(file / "analysis.json" if file.is_dir() else file)
    if (obj.get("schema_version") != 1 or obj.get("kind") != "retail_ability_differential_review"
            or obj.get("status") != "observation_and_followup_plan_not_parity_proof"):
        raise SpecError("not a Patch 10 differential analysis")
    if obj.get("rawcode") != source["rawcode"] or obj.get("executable_sha256") != source["sha"]:
        raise SpecError("analysis rawcode or executable hash does not match offline source")
    inputs = obj.get("offline_inputs")
    if not isinstance(inputs, dict):
        raise SpecError("analysis source hashes missing")
    for name in ("questions.json", "provenance.json", "coverage.json"):
        if inputs.get(name) != source["source_hashes"][name]:
            raise SpecError("analysis does not refer to current offline source: " + name)
    if not isinstance(obj.get("comparisons"), list) or not isinstance(obj.get("capture_summaries"), list) or not isinstance(obj.get("question_actions"), list):
        raise SpecError("analysis is missing comparison or action evidence")
    seen = set()
    for item in obj["comparisons"]:
        if (not isinstance(item, dict) or not isinstance(item.get("id"), str)
                or item["id"] in seen or not isinstance(item.get("status"), str)
                or item["status"] not in _COMPARISON
                or not isinstance(item.get("paired_observations"), list)
                or not isinstance(item.get("incomplete_sessions"), list)):
            raise SpecError("invalid or duplicate comparison evidence")
        seen.add(item["id"])
        if item["status"] == "observed_consistent" and (not item["paired_observations"] or item["incomplete_sessions"]
                or any(not isinstance(p, dict) or p.get("matches_relation") is not True
                       for p in item["paired_observations"])):
            raise SpecError("comparison is labelled observed_consistent without complete matching pairs")
    return obj


def _review(source: dict[str, Any], analysis: dict[str, Any] | None,
            file: Path | None) -> dict[str, Any]:
    empty = {"schema_version": 1, "rawcode": source["rawcode"], "executable_sha256": source["sha"],
             "claims": [], "logic_steps": [], "state_transitions": [], "presentation_events": [],
             "acceptance_tests": [], "reference_c": []}
    if file is None:
        return empty
    obj = _load(file)
    if set(obj) - set(empty) or obj.get("schema_version") != 1 or obj.get("rawcode") != source["rawcode"] or obj.get("executable_sha256") != source["sha"]:
        raise SpecError("reviewed contract schema/rawcode/executable identity mismatch")
    for key in ("claims", "logic_steps", "state_transitions", "presentation_events", "acceptance_tests", "reference_c"):
        if not isinstance(obj.get(key), list):
            raise SpecError(f"review {key} must be a list (use [] when empty)")
    claims: dict[str, dict[str, Any]] = {}
    comparison_ids = {c["id"]: c for c in analysis["comparisons"]} if analysis else {}
    for item in obj["claims"]:
        if not isinstance(item, dict) or set(item) != {"id", "domain", "statement", "evidence"}:
            raise SpecError("review claim requires id/domain/statement/evidence only")
        cid = item["id"]
        if (not isinstance(cid, str) or not _ID.fullmatch(cid) or cid in claims
                or not isinstance(item["domain"], str) or item["domain"] not in _DOMAINS):
            raise SpecError("invalid/duplicate reviewed claim id or domain")
        _text(item["statement"], "reviewed claim")
        evs = item["evidence"]
        if not isinstance(evs, list) or not evs:
            raise SpecError("reviewed claims need explicit source evidence")
        for ev in evs:
            if not isinstance(ev, dict) or not isinstance(ev.get("type"), str):
                raise SpecError("invalid claim evidence")
            if ev["type"] == "native":
                if set(ev) != {"type", "rva"} or not isinstance(ev.get("rva"), str) or ev["rva"].lower() not in source["function_rvas"]:
                    raise SpecError("review references native RVA not present in offline graph")
            elif ev["type"] == "authored":
                if set(ev) != {"type", "edition", "rank", "field"}:
                    raise SpecError("authored source must name edition, rank and exact field")
                edition = (source["lookup"]["editions"].get(ev["edition"])
                           if isinstance(ev["edition"], str) else None)
                if not isinstance(edition, dict) or not edition.get("found") or not isinstance(ev["rank"], int) or isinstance(ev["rank"], bool):
                    raise SpecError("invalid authored source edition/rank")
                if not isinstance(ev["field"], str) or not any(isinstance(rank, dict) and rank.get("level") == ev["rank"] and ev["field"] in rank for rank in edition.get("ranks", [])):
                    raise SpecError("review references unexported authored rank field")
            elif ev["type"] == "comparison":
                if (set(ev) != {"type", "id"} or not isinstance(ev.get("id"), str)
                        or ev["id"] not in comparison_ids
                        or comparison_ids[ev["id"]]["status"] != "observed_consistent"):
                    raise SpecError("review references unverified/inconclusive comparison")
            else:
                raise SpecError(f"unsupported evidence type: {ev['type']}")
        claims[cid] = item
    for name, required in (
        ("logic_steps", {"id", "stage", "description", "claim_ids"}),
        ("state_transitions", {"id", "from", "event", "to", "actions", "claim_ids"}),
        ("presentation_events", {"id", "phase", "description", "asset", "claim_ids"}),
        ("acceptance_tests", {"id", "given", "when", "then", "claim_ids"}),
        ("reference_c", {"id", "code", "claim_ids"}),
    ):
        seen = set()
        for row in obj[name]:
            if not isinstance(row, dict) or set(row) != required:
                raise SpecError(f"{name}: invalid fields")
            ident = row["id"]
            if not isinstance(ident, str) or not _ID.fullmatch(ident) or ident in seen:
                raise SpecError(f"{name}: invalid/duplicate id")
            seen.add(ident)
            refs = row["claim_ids"]
            if (not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or ref not in claims for ref in refs)
                    or len(set(refs)) != len(refs)):
                raise SpecError(f"{name}: references missing or duplicate claim ids")
            if name == "logic_steps":
                if not isinstance(row["stage"], str) or row["stage"] not in _STAGES:
                    raise SpecError("invalid execution stage")
                _text(row["description"], "logic step")
            elif name == "state_transitions":
                for key in ("from", "event", "to", "actions"):
                    _text(row[key], "state transition " + key)
            elif name == "presentation_events":
                for key in ("phase", "description", "asset"):
                    _text(row[key], "presentation event " + key)
            elif name == "acceptance_tests":
                for key in ("given", "when", "then"):
                    _text(row[key], "acceptance test " + key)
            else:
                code = _text(row["code"], "reviewed C", limit=20000)
                if any(line.lstrip().startswith("#") for line in code.splitlines()):
                    raise SpecError("reviewed C snippets cannot contain preprocessor directives")
    return obj


def build(root: Path, *, analysis: Path | None = None, review: Path | None = None) -> dict[str, Any]:
    source = _source_inputs(root)
    analyzed = _analysis(source, analysis)
    reviewed = _review(source, analyzed, review)
    # The source comparison is observable evidence, never a completed semantic contract.
    return {"schema_version": 1, "rawcode": source["rawcode"], "executable_sha256": source["sha"],
            "status": "reviewed_draft_not_full_retail_parity",
            "lookup": source["lookup"], "dependencies": source["deps"],
            "coverage": source["coverage"], "open_questions": source["questions"],
            "analysis": analyzed, "reviewed": reviewed,
            "provenance": {"reconstruction_sources": source["source_hashes"],
                           "analysis_sha256": _hash_file(analysis / "analysis.json" if analysis.is_dir() else analysis) if analysis else None,
                           "review_sha256": _hash_file(review) if review else None},
            "guardrails": {"runtime_parity_proven": False,
                           "authored_art_is_runtime_playback": False,
                           "sampled_difference_is_native_formula": False,
                           "reference_c_can_compile": False}}


def _implementation(report: dict[str, Any]) -> str:
    r = report["reviewed"]
    lines = [f"# Implementation specification: `{report['rawcode']}`", "",
             "**Status: evidence-linked draft, NOT an exact Retail parity claim.**",
             "This specification separates authored data, structural native evidence,",
             "sampled observations and reviewed semantic contracts. No gameplay logic is inferred",
             "from a function name, an art reference or one measured difference.", "",
             f"Executable SHA-256: `{report['executable_sha256'] or 'not provided'}`", "",
             "## Ability data and native code", "",
             "`../lookup.json` contains the authoritative rank fields and source archives.",
             "`../offline/native/decompiled.c` contains raw Ghidra pseudocode, if exported.",
             "`../offline/dependencies.json` contains call edges, candidate memory fields and presentation sources.", "",
             "| Edition | Implementation code | Class hint | Ranks exported |",
             "|---|---|---|---:|"]
    for edition, item in sorted(report["lookup"]["editions"].items()):
        if not item.get("found"):
            lines.append(f"| {edition.upper()} | absent | — | 0 |")
        else:
            hint = item.get("retail_class_reference", {})
            lines.append(f"| {edition.upper()} | `{_single_line(hint.get('implementation_code', '?'))}` | "
                         f"{_single_line(hint.get('class') or 'unverified')} (hint) | {len(item.get('ranks', []))} |")
    lines += ["", "## Rank-specific authored fields (not runtime interpretation)", ""]
    for edition, item in sorted(report["lookup"]["editions"].items()):
        if not item.get("found"):
            continue
        for index, rank in enumerate(item.get("ranks", []), start=1):
            if not isinstance(rank, dict):
                raise SpecError("malformed lookup rank object")
            lines += [f"### {edition.upper()} rank {rank.get('level', index)}", "", "```json",
                      json.dumps(rank, indent=2, ensure_ascii=True, sort_keys=True), "```", ""]
    lines += ["## Explicit reviewed semantic claims", ""]
    if not r["claims"]:
        lines.append("No reviewed semantic claims supplied. Do not treat the static call graph as ability behavior.")
    for c in r["claims"]:
        ev = ", ".join(("native " + x["rva"] if x["type"] == "native" else
                        f"authored {x['edition']} rank {x['rank']} {x['field']}" if x["type"] == "authored" else
                        "sampled comparison " + x["id"]) for x in c["evidence"])
        lines.append(f"- **{c['id']}** ({c['domain']}): {_single_line(c['statement'])} — evidence: {ev}. "
                     "*Human-reviewed interpretation; evidence references are not automatic semantic proof.*")
    lines += ["", "## Ability execution", "", "| Stage | Reviewed step | Claim IDs |", "|---|---|---|"]
    for step in r["logic_steps"]:
        lines.append(f"| {step['stage']} | {_single_line(step['description'])} | {', '.join(step['claim_ids'])} |")
    if not r["logic_steps"]:
        lines.append("| — | No reviewed algorithm; inspect native code and unresolved questions. | — |")
    lines += ["", "## State transitions and cleanup", "", "| From | Event | To | Action | Evidence claims |",
              "|---|---|---|---|---|"]
    for row in r["state_transitions"]:
        lines.append(f"| {_single_line(row['from'])} | {_single_line(row['event'])} | {_single_line(row['to'])} | "
                     f"{_single_line(row['actions'])} | {', '.join(row['claim_ids'])} |")
    if not r["state_transitions"]:
        lines.append("| — | — | — | Unresolved; including cancellation, death, removal and expiry. | — |")
    lines += ["", "## Presentation and audio", "",
              "See `presentation-timeline.md` for authored asset dependencies and reviewed events.",
              "An asset reference or model sequence does not prove spawn, animation selection or lifetime.", "",
              "## Acceptance tests", "", "See `acceptance-tests.md` and `acceptance-tests.json`.", "",
              "## Outstanding questions", ""]
    for q in report["open_questions"]:
        lines.append(f"- `{q['id']}` {q['category']} / {q['kind']}: {_single_line(q.get('detail', ''))}. "
                     f"Next: {_single_line(q.get('suggested_resolution', 'review sources'))}.")
    if not report["open_questions"]:
        lines.append("No questions were recorded in the offline package. This does not establish full parity.")
    lines += ["", "## Implementation handoff", "",
              "Reference C fragments are reviewer-supplied and deliberately wrapped in `#if 0`.",
              "There is no generated game-module integration, no inferred Quake/OpenRealm API calls,",
              "and no compile-ready behavior until the full contract is independently reviewed.", ""]
    return "\n".join(lines) + "\n"


def _timeline(report: dict[str, Any]) -> str:
    lines = [f"# Presentation timeline: `{report['rawcode']}`", "",
             "**Runtime timing and animation playback are unverified unless reviewed native evidence explicitly establishes them.**", "",
             "## Authored presentation dependencies (not runtime events)", "",
             "| Edition | Source | Field | Asset/alias | Evidence |", "|---|---|---|---|---|"]
    count = 0
    for edition, item in sorted(report["dependencies"].get("presentation", {}).items()):
        if not item.get("found"):
            continue
        for ref in item.get("references", []):
            if not isinstance(ref, dict):
                raise SpecError("malformed authored art reference")
            lines.append(f"| {edition} | {_single_line(ref.get('source', '?'))} | "
                         f"{_single_line(ref.get('field', '?'))} | {_single_line(ref.get('asset') or ref.get('value') or '?')} | authored only |")
            count += 1
        for ref in item.get("sounds", []):
            if not isinstance(ref, dict):
                raise SpecError("malformed authored sound reference")
            lines.append(f"| {edition} | sound lookup | alias | {_single_line(ref.get('alias', '?'))} | "
                         f"{_single_line(ref.get('status', 'unknown'))} |")
            count += 1
    if not count:
        lines.append("| — | — | — | No authored references available | — |")
    lines += ["", "## Model metadata and authored animation sequences", ""]
    models_seen = 0
    for edition, item in sorted(report["dependencies"].get("presentation", {}).items()):
        if not item.get("found"):
            continue
        for model in item.get("models", []):
            if not isinstance(model, dict):
                raise SpecError("malformed model metadata")
            sequences = model.get("sequences")
            display = ", ".join(str(s.get("name", "?")) if isinstance(s, dict) else str(s)
                                for s in sequences) if isinstance(sequences, list) else "unknown"
            lines.append(f"- {edition.upper()} `{_single_line(model.get('path', '?'))}`: "
                         f"{_single_line(model.get('status', 'unknown'))}; "
                         f"authored sequences: {_single_line(display)} (not playback proof)")
            models_seen += 1
    if not models_seen:
        lines.append("No model metadata supplied.")
    lines += ["", "## Human-reviewed presentation events (not inferred from art presence)", "",
              "| Phase | Event | Asset | Claim IDs |", "|---|---|---|---|"]
    for event in report["reviewed"]["presentation_events"]:
        lines.append(f"| {_single_line(event['phase'])} | {_single_line(event['description'])} | "
                     f"{_single_line(event['asset'])} | {', '.join(event['claim_ids'])} |")
    if not report["reviewed"]["presentation_events"]:
        lines.append("| — | No reviewed runtime presentation events supplied. | — | — |")
    lines.extend(["", "Open questions: animation tags, model sequence/attachment selection, emitter",
                  "start and stop, projectile motion, sounds, update cadence and cleanup.", ""])
    return "\n".join(lines) + "\n"


def _acceptance(report: dict[str, Any]) -> str:
    lines = [f"# Acceptance scenarios: `{report['rawcode']}`", "",
             "**Draft test requirements:** these are not a claim that the implementation passes.", "",
             "| Test | Given | When | Expected | Reviewed claims |", "|---|---|---|---|---|"]
    for t in report["reviewed"]["acceptance_tests"]:
        lines.append(f"| {t['id']} | {_single_line(t['given'])} | {_single_line(t['when'])} | "
                     f"{_single_line(t['then'])} | {', '.join(t['claim_ids'])} |")
    if not report["reviewed"]["acceptance_tests"]:
        lines.append("| — | — | — | No reviewed numeric/semantic expected results supplied. | — |")
    if report["analysis"]:
        lines += ["", "## Existing sampled differentials (not specification assertions)", "",
                  "| Comparison | Status | Metric | Pairs |", "|---|---|---|---:|"]
        for row in report["analysis"]["comparisons"]:
            lines.append(f"| {row['id']} | {row['status']} | {_single_line(row.get('metric', '?'))} | "
                         f"{len(row['paired_observations'])} |")
    lines += ["", "Cover ordinary orders, invalid target/resource cases, lifecycle expiry/cancel/death,",
              "alias/rank data, and presentation cleanup when corresponding behaviors are established.", ""]
    return "\n".join(lines) + "\n"


def _reference(report: dict[str, Any]) -> tuple[str, str]:
    code = ["/* Reviewed reference fragments for Warcraft III ability " + report["rawcode"] + ".",
            " * Not Blizzard original source. Not compiled or integrated into OpenRealm.",
            " * Every snippet is supplied by a human-reviewed contract, not synthesized",
            " * from a decompiler name or an isolated Retail observation.",
            " */", "#if 0 /* REQUIRES MANUAL VALIDATION BEFORE REUSE */"]
    for frag in report["reviewed"]["reference_c"]:
        code += ["", "/* " + frag["id"] + " supported by reviewed claims: " + ", ".join(frag["claim_ids"]) + " */",
                 frag["code"]]
    if not report["reviewed"]["reference_c"]:
        code.extend(["", "/* No reviewed C implementation supplied. See ../implementation.md and native pseudocode. */"])
    code.extend(["#endif", ""])
    header = ["/* Reference notes only; no callable ability functions are declared.",
              " * See ability.c (#if 0) and ../implementation.md.",
              " * Do NOT add this as a game-module API or assume inferred object layouts.",
              " */", ""]
    return "\n".join(code), "\n".join(header)


def write(report: dict[str, Any], directory: Path) -> None:
    """Write new immutable output; caller completes all input checks first."""
    if directory.exists():
        raise SpecError(f"refusing to overwrite specification output: {directory}")
    directory.mkdir(parents=True)
    (directory / "reference").mkdir()
    code, header = _reference(report)
    sources = report["provenance"]
    outputs = {
        "implementation.md": _implementation(report),
        "presentation-timeline.md": _timeline(report),
        "acceptance-tests.md": _acceptance(report),
        "reference/ability.c": code,
        "reference/ability.h": header,
        "acceptance-tests.json": json.dumps({"schema_version": 1, "rawcode": report["rawcode"],
                                               "tests": report["reviewed"]["acceptance_tests"],
                                               "sampled_comparisons": report["analysis"]["comparisons"] if report["analysis"] else [],
                                               "sampled_comparisons_are_not_exact_contracts": True}, indent=2, sort_keys=True) + "\n",
        "spec-evidence.json": json.dumps({"schema_version": 1, "rawcode": report["rawcode"],
                                           "executable_sha256": report["executable_sha256"],
                                           "status": report["status"], "source_hashes": sources,
                                           "claims": report["reviewed"]["claims"],
                                           "open_questions": report["open_questions"],
                                           "guardrails": report["guardrails"]}, indent=2, sort_keys=True) + "\n",
    }
    for name, content in outputs.items():
        (directory / name).write_text(content, encoding="utf-8")
