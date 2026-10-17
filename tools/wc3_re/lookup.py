"""Resolve one WC3 rawcode from authored data with separately labelled class leads.

No Retail function or runtime behavior is inferred from reference class tables.
`ability_audit -json` is the only authoritative source of decoded SLK row data.
"""

from __future__ import annotations

import hashlib
import json
import csv
import io
from pathlib import Path
import re
import subprocess
from typing import Any

from wc3_re.inventory import validate_inventory

ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "docs/games/warcraft-3/ability-function-investigation.json"
CLASS_REFERENCE = ROOT / "games/warcraft-3/tft-ability-classes.txt"
DEFAULT_AUDIT = ROOT / "build/bin/ability_audit"
DEFAULT_DATA = ROOT / "data/Warcraft III"
RAWCODE_RE = re.compile(r"[A-Za-z0-9]{4}\Z")
CLASS_RE = re.compile(
    r'^\{\s*"([^"]{4})",\s*"([^"]+)"\s*\}\s*,?\s*/\*\s*parent="([^"]*)"'
    r'(?:\s+call=([0-9A-Fa-f]{8})\s+create=([0-9A-Fa-f]{8})'
    r'\s+destroy=([0-9A-Fa-f]{8})\s+pool=([0-9A-Fa-f]{8})'
    r'\s+rtti=([0-9A-Fa-f]{8})\s+desc_va=([0-9A-Fa-f]{8})'
    r'\s+table=([0-9A-Fa-f]{8})\s+init=([0-9A-Fa-f]{8}))?')
CLASS_SHA_RE = re.compile(r"^\s*\*\s*SHA-256:\s*([0-9a-f]{64})", re.IGNORECASE | re.MULTILINE)


class LookupError(RuntimeError):
    """Unusable local input, unknown rawcode, or invalid tool output."""


def check_rawcode(rawcode: str) -> str:
    if not RAWCODE_RE.fullmatch(rawcode):
        raise LookupError("rawcode must be exactly four ASCII letters or digits")
    return rawcode


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_inventory_identity(path: Path = INVENTORY) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise LookupError(f"cannot load inventory {path}: {error}") from error
    report = validate_inventory(data)
    if not report["valid"]:
        reasons = [issue["code"] for issue in report["issues"] if issue["severity"] == "error"]
        raise LookupError("inventory failed validation: " + ", ".join(reasons))
    return dict(data["executable"])


def class_reference(path: Path = CLASS_REFERENCE) -> dict[str, dict[str, Any]]:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as error:
        raise LookupError(f"cannot read class reference {path}: {error}") from error
    classes: dict[str, dict[str, Any]] = {}
    source_sha_match = CLASS_SHA_RE.search(content)
    source_sha256 = source_sha_match.group(1).lower() if source_sha_match else None
    for line in content.splitlines():
        match = CLASS_RE.match(line)
        if match:
            code, name, parent, *offsets = match.groups()
            if code in classes:
                raise LookupError(f"duplicate implementation code in class reference: {code}")
            row: dict[str, Any] = {"name": name, "parent_code": parent}
            if offsets[0] is not None:
                keys = ("registration_call_file_offset", "factory_file_offset",
                        "destroy_file_offset", "pool_cleanup_file_offset",
                        "rtti_file_offset", "descriptor_va", "vtable_file_offset",
                        "initializer_file_offset")
                row["registration"] = {
                    "binary_sha256": source_sha256,
                    "offsets_are": "file_offsets_except_descriptor_va",
                    **{key: f"0x{value.lower()}" for key, value in zip(keys, offsets)},
                }
            classes[code] = row
    if not classes:
        raise LookupError(f"no class rows found in {path}")
    return classes


def check_executable(path: Path | None, identity: dict[str, Any]) -> dict[str, Any]:
    if path is None:
        return {"checked": False, "expected_sha256": identity["sha256"],
                "note": "Executable not checked; no live addresses or runtime claims are verified."}
    if not path.is_file():
        raise LookupError(f"Retail executable not found: {path}")
    actual = sha256(path)
    if actual.lower() != str(identity["sha256"]).lower():
        raise LookupError(f"Retail executable SHA-256 differs from pinned inventory: {actual} != {identity['sha256']}")
    return {"checked": True, "path": str(path.resolve()), "sha256": actual}


def _check_ability_payload(doc: Any, rawcode: str, edition: str) -> dict[str, Any]:
    if not isinstance(doc, dict) or doc.get("schema_version") != 1:
        raise LookupError("ability_audit returned unsupported JSON schema")
    if doc.get("rawcode") != rawcode or doc.get("edition") != edition.upper():
        raise LookupError(f"ability_audit output identity mismatch for {rawcode}/{edition}")
    if (not isinstance(doc.get("found"), bool) or not isinstance(doc.get("archives"), list)
            or any(not isinstance(path, str) for path in doc["archives"])):
        raise LookupError("ability_audit returned incomplete found/archives fields")
    # ability_audit's data reader selects the requested edition correctly, but
    # its `archives` JSON field reports all discovered archives. Do not let the
    # presentation stage consume TFT overlays during a ROC lookup.
    if edition == "roc":
        doc["archives"] = [path for path in doc["archives"]
                           if not _is_tft_archive(path)]
    if doc["found"]:
        ability = doc.get("ability")
        if not isinstance(ability, dict) or ability.get("id") != rawcode:
            raise LookupError("ability_audit returned another ability row")
        for code in ("code", "uber_alias"):
            if ability.get(code) is not None:
                check_rawcode(ability[code])
        if not isinstance(doc.get("ranks"), list) or not doc["ranks"]:
            raise LookupError("ability_audit returned no level data")
        if type(ability.get("levels")) is not int or ability["levels"] < 0:
            raise LookupError("ability_audit returned invalid authored level count")
        if not isinstance(doc.get("aliases"), list) or not isinstance(doc.get("buffs"), list):
            raise LookupError("ability_audit returned incomplete alias/buff data")
        strings = doc.get("strings")
        if strings is not None:
            if not isinstance(strings, dict) or any(
                    value is not None and not isinstance(value, str) for value in strings.values()):
                raise LookupError("ability_audit returned malformed localized string data")
            count = min(max(1, int(ability.get("levels", 1))), 4)
            by_rank = []
            for level in range(1, count + 1):
                values: dict[str, str | None] = {}
                for key, raw in strings.items():
                    values[key] = _rank_string(raw, level - 1, count) if raw is not None else None
                by_rank.append({"level": level, "values": values})
            doc["strings_by_rank"] = by_rank
    return doc


def _is_tft_archive(path: str) -> bool:
    """Classify known TFT archive *filenames*, never their parent directories."""
    name = Path(path.replace("\\", "/")).name.casefold()
    return name in {
        "war3x.mpq", "war3xlocal.mpq",
        "frozen.mpq", "frozenlocal.mpq",
        "frozenthrone.mpq", "frozenthronelocal.mpq",
        "frozen throne.mpq", "frozen throne local.mpq",
    }


def _rank_string(value: str, index: int, expected: int) -> str | None:
    """Split ability-audit's quote-stripped rank CSV without losing raw source."""
    # IniCache returns one quoted CSV list for localized rank strings; the C
    # JSON exporter strips only the outer quotes. Restore those for csv.reader.
    if '\",\"' not in value:
        return value if index == 0 else None
    try:
        parsed = next(csv.reader(io.StringIO('"' + value + '"'), strict=True))
    except (csv.Error, StopIteration) as error:
        raise LookupError(f"ability_audit returned malformed rank string data: {error}") from error
    if len(parsed) != expected:
        raise LookupError(f"ability_audit returned {len(parsed)} localized strings for {expected} ability ranks")
    return parsed[index]


def audit_one(rawcode: str, edition: str, *, audit: Path, data_dir: Path) -> dict[str, Any]:
    if not audit.is_file():
        raise LookupError(f"ability_audit not found at {audit}; build the existing tool with make ability_audit")
    if not data_dir.is_dir():
        raise LookupError(f"ability data directory not found: {data_dir}")
    command = [str(audit.resolve()), "-data", str(data_dir.resolve()), "-" + edition, "-json", "-raw", rawcode]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as error:
        raise LookupError(f"failed to run ability_audit: {error}") from error
    try:
        payload = json.loads(completed.stdout)
    except ValueError as error:
        raise LookupError(f"ability_audit did not return valid JSON ({edition}): {completed.stderr.strip()}") from error
    payload = _check_ability_payload(payload, rawcode, edition)
    if completed.returncode and payload["found"]:
        raise LookupError(f"ability_audit failed ({completed.returncode}) despite reporting a found row: {completed.stderr.strip()}")
    if not completed.returncode and not payload["found"]:
        raise LookupError("ability_audit returned success for missing ability")
    if completed.returncode not in (0, 1):
        raise LookupError(f"ability_audit failed ({completed.returncode}): {completed.stderr.strip()}")
    return payload


def resolve(rawcode: str, editions: list[str], *, audit: Path = DEFAULT_AUDIT,
            data_dir: Path = DEFAULT_DATA, inventory: Path = INVENTORY,
            classes_path: Path = CLASS_REFERENCE, executable: Path | None = None) -> dict[str, Any]:
    rawcode = check_rawcode(rawcode)
    if not editions or any(edition not in {"roc", "tft"} for edition in editions):
        raise LookupError("edition must be roc, tft, or both")
    identity = load_inventory_identity(inventory)
    checked_executable = check_executable(executable, identity)
    classes = class_reference(classes_path)
    results: dict[str, Any] = {}
    found = 0
    for edition in dict.fromkeys(editions):
        doc = audit_one(rawcode, edition, audit=audit, data_dir=data_dir)
        if doc["found"]:
            found += 1
            ability = doc["ability"]
            # AbilityData `code` is the implementation code; uber_alias is a
            # separate authored alias and must not silently replace it.
            code = ability.get("code") or rawcode
            entry = classes.get(code) if edition == "tft" else None
            doc["retail_class_reference"] = {
                "implementation_code": code,
                "class": entry["name"] if entry else None,
                "parent_code": entry["parent_code"] if entry else None,
                "registration": entry.get("registration") if entry else None,
                "source": str(classes_path),
                "status": "offline_reference_hint" if entry else "unresolved",
                "note": "Not verified factory registration or a runtime vtable.",
            }
        results[edition] = doc
    if not found:
        raise LookupError(f"rawcode {rawcode!r} absent from the selected edition(s)")
    return {
        "schema_version": 1, "rawcode": rawcode,
        "state": "authored_data_only",
        "executable_identity": identity, "executable_check": checked_executable,
        "source": {"audit": str(audit), "data_dir": str(data_dir)},
        "editions": results,
        "limitations": [
            "Authored data and saved class tables do not prove runtime behavior.",
            "The exact native factory, vtable and execution graph require Ghidra indexing (Patch 3).",
            "Presentation dependencies and actual timing are not yet reconstructed.",
        ],
    }
