"""Validate and normalize an exact-build Retail function inventory.

Only standard-library dependencies are needed. Validation checks structure and
internally consistent VA/RVA pairs; it does NOT prove that an RVA points to
executable code or that a claimed call occurred. Such claims require binary
and source review. No relationship is inferred from `related_addresses`.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any

DEFAULT_INVENTORY = (
    Path(__file__).resolve().parents[2]
    / "docs/games/warcraft-3/ability-function-investigation.json"
)
SCHEMA_FILE = Path(__file__).with_name("schema.json")
ADDRESS_KINDS = frozenset({
    "function_va", "vtable_va", "vtable", "global_va", "untyped_va", "constant"
})
RELATIONSHIP_KINDS = frozenset({
    "direct_call", "virtual_dispatch", "callback_dispatch", "related_call_path", "call"
})
CONFIDENCE = frozenset({"low", "medium", "high"})
STATUSES = frozenset({"observed", "partially_resolved", "candidate"})
RECORD_KINDS = frozenset({"function", "function_group", "vtable_record"})
HEX_RE = re.compile(r"0x[0-9a-fA-F]{1,8}\Z")
SHA_RE = re.compile(r"[0-9a-fA-F]{64}\Z")


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    location: str
    message: str


class InventoryError(ValueError):
    """The input cannot be validated or safely normalized."""


def _hex(value: Any, location: str, issues: list[Issue]) -> int | None:
    if not isinstance(value, str) or HEX_RE.fullmatch(value) is None:
        issues.append(Issue("error", "invalid_hex", location, "expected a 32-bit 0x-prefixed hex string"))
        return None
    return int(value, 16)


def _check_address(address: Any, location: str, base: int | None,
                   issues: list[Issue], counters: Counter[str]) -> None:
    if not isinstance(address, dict):
        issues.append(Issue("error", "invalid_address", location, "expected an address object"))
        return
    kind = address.get("kind")
    if kind is None:
        counters["untyped_addresses"] += 1
    elif not isinstance(kind, str) or kind not in ADDRESS_KINDS:
        issues.append(Issue("error", "invalid_address_kind", location, f"unrecognized address kind: {kind!r}"))
    if kind == "constant":
        if "va" in address or "rva" in address or "value" not in address:
            issues.append(Issue("error", "constant_as_address", location,
                                "a constant has `value`, but must not have VA/RVA"))
        if "value" in address:
            _hex(address["value"], location + ".value", issues)
        counters["constants"] += 1
        return
    if "value" in address:
        issues.append(Issue("error", "address_as_constant", location,
                            "only kind=constant may contain `value`"))
    va = _hex(address.get("va"), location + ".va", issues)
    rva = _hex(address.get("rva"), location + ".rva", issues)
    if va is not None and rva is not None and base is not None and va - base != rva:
        issues.append(Issue("error", "va_rva_mismatch", location,
                            f"VA {va:#010x} - image base {base:#010x} != RVA {rva:#010x}"))
    counters["addresses"] += 1


def _source(source: Any, location: str, issues: list[Issue]) -> None:
    if not isinstance(source, dict) or not isinstance(source.get("document"), str) or not source["document"].strip():
        issues.append(Issue("error", "invalid_source", location,
                            "source must include a nonempty document reference"))


def validate_inventory(data: Any) -> dict[str, Any]:
    """Return a deterministic report without rewriting or dropping evidence."""
    issues: list[Issue] = []
    counters: Counter[str] = Counter()
    if not isinstance(data, dict):
        return {"valid": False, "statistics": {},
                "issues": [asdict(Issue("error", "invalid_root", "$", "expected JSON object"))]}
    if data.get("schema_version") != 1:
        issues.append(Issue("error", "unsupported_schema", "$.schema_version", "expected schema version 1"))
    exe = data.get("executable")
    if not isinstance(exe, dict):
        issues.append(Issue("error", "missing_executable", "$.executable", "expected executable identity"))
        exe = {}
    sha = exe.get("sha256")
    if not isinstance(sha, str) or SHA_RE.fullmatch(sha) is None:
        issues.append(Issue("error", "invalid_sha256", "$.executable.sha256", "expected 64 hexadecimal digits"))
    for field in ("architecture", "module"):
        if not isinstance(exe.get(field), str) or not exe[field]:
            issues.append(Issue("error", "missing_executable_field", "$.executable." + field,
                                "required nonempty string"))
    base = _hex(exe.get("preferred_image_base"), "$.executable.preferred_image_base", issues)
    records = data.get("functions")
    relationships = data.get("verified_relationships")
    if not isinstance(records, list):
        issues.append(Issue("error", "invalid_records", "$.functions", "expected array"))
        records = []
    if not isinstance(relationships, list):
        issues.append(Issue("error", "invalid_relationships", "$.verified_relationships", "expected array"))
        relationships = []
    declared = data.get("relationship_kinds")
    if not isinstance(declared, dict):
        issues.append(Issue("error", "invalid_relationship_kinds", "$.relationship_kinds", "expected map of descriptions"))
        declared = {}
    seen_ids: set[str] = set()
    for i, record in enumerate(records):
        loc = f"$.functions[{i}]"
        if not isinstance(record, dict):
            issues.append(Issue("error", "invalid_record", loc, "expected object"))
            continue
        identifier = record.get("id")
        if not isinstance(identifier, str) or not identifier:
            issues.append(Issue("error", "invalid_id", loc + ".id", "expected nonempty ID"))
        elif identifier in seen_ids:
            issues.append(Issue("error", "duplicate_id", loc + ".id", f"duplicate {identifier!r}"))
        else:
            seen_ids.add(identifier)
        if not isinstance(record.get("label"), str) or not record["label"]:
            issues.append(Issue("error", "invalid_label", loc + ".label", "expected label"))
        for field, allowed in (("status", STATUSES), ("confidence", CONFIDENCE),
                               ("record_kind", RECORD_KINDS)):
            if not isinstance(record.get(field), str) or record[field] not in allowed:
                issues.append(Issue("error", "invalid_" + field, loc + "." + field,
                                    f"expected one of {', '.join(sorted(allowed))}"))
        addresses = record.get("addresses")
        if not isinstance(addresses, list) or not addresses:
            issues.append(Issue("error", "invalid_addresses", loc + ".addresses", "expected nonempty array"))
        else:
            for j, addr in enumerate(addresses):
                _check_address(addr, f"{loc}.addresses[{j}]", base, issues, counters)
                if isinstance(addr, dict) and addr.get("kind") == "constant":
                    issues.append(Issue("error", "constant_as_function_entry",
                                        f"{loc}.addresses[{j}]",
                                        "function/vtable entries must be module addresses"))
        related = record.get("related_addresses")
        if not isinstance(related, list):
            issues.append(Issue("error", "invalid_related_addresses", loc + ".related_addresses", "expected array"))
        else:
            for j, addr in enumerate(related):
                _check_address(addr, f"{loc}.related_addresses[{j}]", base, issues, counters)
        offsets = record.get("object_offsets", [])
        if not isinstance(offsets, list):
            issues.append(Issue("error", "invalid_offsets", loc + ".object_offsets", "expected array"))
        else:
            # Historical notes mix bare offsets and prose describing multiple
            # fields. Keep the prose as evidence; do not guess an offset from it.
            for j, offset in enumerate(offsets):
                if not isinstance(offset, str) or not offset.strip():
                    issues.append(Issue("error", "invalid_offset_note",
                                        f"{loc}.object_offsets[{j}]",
                                        "expected nonempty offset or offset description"))
        _source(record.get("source"), loc + ".source", issues)
        counters["record_" + str(record.get("record_kind"))] += 1
    edge_groups: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for i, relationship in enumerate(relationships):
        loc = f"$.verified_relationships[{i}]"
        if not isinstance(relationship, dict):
            issues.append(Issue("error", "invalid_relationship", loc, "expected object"))
            continue
        kind = relationship.get("kind")
        if not isinstance(kind, str) or kind not in RELATIONSHIP_KINDS or kind not in declared:
            issues.append(Issue("error", "invalid_relationship_kind", loc + ".kind",
                                f"{kind!r} is not a supported, declared relationship kind"))
        if kind == "call":
            counters["unclassified_call_edges"] += 1
        if kind == "related_call_path":
            counters["nonimmediate_paths"] += 1
        if not isinstance(relationship.get("confidence"), str) or relationship["confidence"] not in CONFIDENCE:
            issues.append(Issue("error", "invalid_confidence", loc + ".confidence", "invalid confidence"))
        if not isinstance(relationship.get("context"), str) or not relationship["context"].strip():
            issues.append(Issue("error", "invalid_context", loc + ".context", "required nonempty context"))
        _source(relationship.get("source"), loc + ".source", issues)
        for endpoint in ("from", "to"):
            address = relationship.get(endpoint)
            _check_address(address, loc + "." + endpoint, base, issues, counters)
            if isinstance(address, dict) and address.get("kind") == "constant":
                issues.append(Issue("error", "constant_as_graph_endpoint",
                                    loc + "." + endpoint,
                                    "a call/path relationship must connect module addresses"))
        source = relationship.get("from")
        target = relationship.get("to")
        if isinstance(source, dict) and isinstance(target, dict) and isinstance(kind, str):
            # Equivalent hex strings may have different leading zeros/case.
            def key(address: dict[str, Any]) -> str:
                value = address.get("rva")
                if isinstance(value, str) and HEX_RE.fullmatch(value):
                    return f"{int(value, 16):08x}"
                return str(value)
            edge_groups[(key(source), key(target), kind)].append(i)
    for name, count in (("entry_count", len(records)),
                        ("verified_relationship_count", len(relationships))):
        if data.get(name) != count:
            issues.append(Issue("error", "stale_count", "$." + name,
                                f"stored {data.get(name)!r}, actual {count}"))
    duplicate_groups = [indices for indices in edge_groups.values() if len(indices) > 1]
    counters["repeated_edge_groups"] = len(duplicate_groups)
    counters["repeated_edge_extra_records"] = sum(len(group) - 1 for group in duplicate_groups)
    counters["functions"] = len(records)
    counters["relationships"] = len(relationships)
    if counters["untyped_addresses"]:
        issues.append(Issue("warning", "legacy_untyped_addresses", "$",
                            f"{counters['untyped_addresses']} address references have no kind; "
                            "normalization labels them untyped_va without guessing"))
    if counters["unclassified_call_edges"]:
        issues.append(Issue("warning", "unclassified_call_edges", "$.verified_relationships",
                            f"{counters['unclassified_call_edges']} `call` edges have no proven dispatch modality"))
    if duplicate_groups:
        issues.append(Issue("info", "repeated_edge_evidence", "$.verified_relationships",
                            f"{len(duplicate_groups)} logical edges have multiple evidence records; they are preserved"))
    return {
        "valid": not any(issue.severity == "error" for issue in issues),
        "statistics": dict(sorted(counters.items())),
        "issues": [asdict(issue) for issue in issues],
    }


def normalize_inventory(data: dict[str, Any]) -> dict[str, Any]:
    """Create a canonical *copy*, retaining all source text and edge records.

    Untyped historical addresses become `untyped_va` rather than inferred code.
    A relationship still has its original kind (especially `call` and
    `related_call_path`); duplicate edges retain their distinct evidence.
    """
    result = validate_inventory(data)
    if not result["valid"]:
        raise InventoryError("cannot normalize an invalid inventory; run validate first")
    output = deepcopy(data)

    def canonical(address: dict[str, Any]) -> None:
        address.setdefault("kind", "untyped_va")
        if address["kind"] == "constant":
            address["value"] = f"0x{int(address['value'], 16):08x}"
        else:
            for field in ("va", "rva"):
                address[field] = f"0x{int(address[field], 16):08x}"

    for record in output["functions"]:
        for address in record["addresses"] + record["related_addresses"]:
            canonical(address)
    for edge in output["verified_relationships"]:
        canonical(edge["from"])
        canonical(edge["to"])
    output["entry_count"] = len(output["functions"])
    output["verified_relationship_count"] = len(output["verified_relationships"])
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", nargs="?", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--strict", action="store_true", help="also fail on warnings (legacy data will warn)")
    parser.add_argument("--normalized-output", type=Path, help="write a validated, typed copy; never overwrite input")
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.inventory.read_text(encoding="utf-8"))
        report = validate_inventory(data)
        if args.normalized_output is not None:
            if args.normalized_output.resolve() == args.inventory.resolve():
                raise InventoryError("refusing to overwrite source evidence inventory")
            normalized = normalize_inventory(data)
            args.normalized_output.parent.mkdir(parents=True, exist_ok=True)
            args.normalized_output.write_text(json.dumps(normalized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, InventoryError) as exc:
        print(f"inventory error: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        stats = report["statistics"]
        print(f"Inventory: {args.inventory} | records={stats.get('functions', 0)} "
              f"relationships={stats.get('relationships', 0)} "
              f"repeated-edge-groups={stats.get('repeated_edge_groups', 0)}")
        for item in report["issues"]:
            print(f"{item['severity']}: {item['code']} at {item['location']}: {item['message']}")
        print("VALID" if report["valid"] else "INVALID")
    has_warning = any(i["severity"] == "warning" for i in report["issues"])
    return 0 if report["valid"] and (not args.strict or not has_warning) else 1


if __name__ == "__main__":
    raise SystemExit(main())
