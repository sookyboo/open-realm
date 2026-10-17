"""Exact-build, read-only Ghidra exporter launcher and artifact validator.

Static references are not runtime reachability evidence. Vtable scans are
pointer-table *candidates*, never proof of a receiver's dynamic type.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
from typing import Any

from wc3_re.inventory import validate_inventory
from wc3_re.lookup import INVENTORY, LookupError, check_executable, load_inventory_identity

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/ghidra/Wc3AbilityExport.java"
RVA_PATTERN = re.compile(r"(?:0[xX])?[0-9a-fA-F]{1,8}\Z")
PROJECT_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_.-]*\Z")
KINDS = {"functions", "callsites", "datarefs", "vtables", "decompiled", "pcode"}


class GhidraError(LookupError):
    """Ghidra invocation or its exported evidence is invalid."""


def rva(value: str) -> int:
    if not isinstance(value, str) or RVA_PATTERN.fullmatch(value) is None:
        raise GhidraError(f"invalid RVA {value!r}: use a hex RVA such as 0x0080d820")
    number = int(value[2:] if value.lower().startswith("0x") else value, 16)
    if number > 0xFFFFFFFF - 0x00400000:
        raise GhidraError("RVA exceeds 32-bit address space")
    return number


def _inventory_seeds(path: Path) -> tuple[list[int], list[int]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise GhidraError(f"cannot load seed inventory {path}: {error}") from error
    report = validate_inventory(payload)
    if not report["valid"]:
        raise GhidraError("cannot seed from an invalid inventory")
    functions: set[int] = set()
    vtables: set[int] = set()
    for entry in payload["functions"]:
        for address in entry.get("addresses", []):
            kind = address.get("kind")
            # Only explicitly classified addresses from entry points; never
            # coerce related_addresses, constants or relationship endpoints.
            if kind == "function_va":
                functions.add(rva(address["rva"]))
            elif kind in ("vtable", "vtable_va"):
                vtables.add(rva(address["rva"]))
    return sorted(functions), sorted(vtables)


def _unique_hex(values: list[str]) -> list[int]:
    return sorted({rva(value) for value in values})


def make_command(*, headless: Path, project_dir: Path, project_name: str,
                 executable: Path, output: Path, identity: dict[str, Any],
                 mode: str, seed_rvas: list[int], vtable_rvas: list[int],
                 first_import: bool, timeout: int, vtable_slots: int) -> list[str]:
    if mode not in ("scan", "detail"):
        raise GhidraError("Ghidra export mode must be scan or detail")
    if not PROJECT_PATTERN.fullmatch(project_name):
        raise GhidraError("project name must be a safe single component")
    if timeout < 1 or timeout > 3600 or not 1 <= vtable_slots <= 512:
        raise GhidraError("decompile timeout must be 1–3600 and vtable slots 1–512")
    if mode == "detail" and not seed_rvas and not vtable_rvas:
        raise GhidraError("detail export needs --rva, --vtable-rva or --inventory-seeds")
    if not headless.is_file() or not SCRIPT.is_file():
        raise GhidraError("analyzeHeadless or Wc3AbilityExport.java not found")
    if not project_dir.is_dir():
        raise GhidraError(f"Ghidra project directory does not exist: {project_dir}")
    if first_import and (project_dir / (project_name + ".gpr")).exists():
        raise GhidraError("--import-first refuses an existing project: use -process mode")
    operation = ["-import", str(executable)] if first_import else ["-process", executable.name, "-noanalysis", "-readOnly"]
    return ([str(headless), str(project_dir), project_name, *operation,
             "-scriptPath", str(SCRIPT.parent), "-postScript", SCRIPT.name,
             str(output), str(identity["sha256"]), mode,
             ",".join(f"0x{item:08x}" for item in seed_rvas),
             ",".join(f"0x{item:08x}" for item in vtable_rvas),
             str(timeout), str(vtable_slots)])


def validate_export(output: Path, expected_sha256: str, expected_mode: str) -> dict[str, Any]:
    summary_path = output / "export-summary.json"
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise GhidraError(f"no valid completed Ghidra summary at {summary_path}: {error}") from error
    if (summary.get("schema_version") != 1 or summary.get("status") != "complete"
            or summary.get("mode") != expected_mode
            or str(summary.get("executable_sha256", "")).lower() != expected_sha256.lower()
            or summary.get("image_base") != "0x00400000"
            or summary.get("architecture") != "x86:LE:32"):
        raise GhidraError("Ghidra summary identity/mode/architecture mismatch")
    counts = summary.get("counts")
    if not isinstance(counts, dict):
        raise GhidraError("Ghidra summary missing counts")
    for kind in KINDS:
        n = counts.get(kind)
        if type(n) is not int or n < 0:
            raise GhidraError(f"invalid Ghidra count for {kind}")
        path = output / (kind + ".jsonl")
        try:
            with path.open("r", encoding="utf-8") as handle:
                actual = 0
                for index, line in enumerate(handle, start=1):
                    if not line.strip():
                        raise GhidraError(f"blank {kind} row {index}")
                    try:
                        record = json.loads(line)
                    except ValueError as error:
                        raise GhidraError(f"bad {kind} row {index}: {error}") from error
                    if not isinstance(record, dict):
                        raise GhidraError(f"nonobject {kind} row {index}")
                    actual += 1
        except OSError as error:
            raise GhidraError(f"missing Ghidra file {path}: {error}") from error
        if actual != n:
            raise GhidraError(f"{kind} count differs from completed summary: {actual} != {n}")
    if expected_mode == "scan" and counts["functions"] == 0:
        raise GhidraError("scan contains no functions: is the program analyzed?")
    return summary


def export(*, headless: Path, project_dir: Path, project_name: str,
           executable: Path, output: Path, inventory: Path = INVENTORY,
           mode: str = "scan", rvas: list[str] | None = None,
           vtables: list[str] | None = None, inventory_seeds: bool = False,
           first_import: bool = False, timeout: int = 60,
           vtable_slots: int = 128) -> dict[str, Any]:
    try:
        identity = load_inventory_identity(inventory)
        check_executable(executable, identity)  # mandatory for native analysis
    except LookupError as error:
        raise GhidraError(str(error)) from error
    if output.exists():
        raise GhidraError(f"refusing existing export directory: {output}")
    seed_rvas, vtable_rvas = _unique_hex(rvas or []), _unique_hex(vtables or [])
    if inventory_seeds:
        seeds, tables = _inventory_seeds(inventory)
        seed_rvas = sorted(set(seed_rvas) | set(seeds))
        vtable_rvas = sorted(set(vtable_rvas) | set(tables))
    if mode == "scan" and (seed_rvas or vtable_rvas):
        raise GhidraError("scan exports all function metadata; use detail for explicit RVAs")
    command = make_command(headless=headless.resolve(), project_dir=project_dir.resolve(),
                           project_name=project_name, executable=executable.resolve(),
                           output=output.resolve(), identity=identity, mode=mode,
                           seed_rvas=seed_rvas, vtable_rvas=vtable_rvas,
                           first_import=first_import, timeout=timeout, vtable_slots=vtable_slots)
    output.mkdir(parents=True)
    (output / "invocation.json").write_text(json.dumps({
        "schema_version": 1, "mode": mode, "binary_sha256": identity["sha256"],
        "command": command, "requested_rvas": [f"0x{x:08x}" for x in seed_rvas],
        "requested_vtable_rvas": [f"0x{x:08x}" for x in vtable_rvas],
        "note": "Ghidra static export, not a gameplay/dispatch observation.",
    }, indent=2) + "\n", encoding="utf-8")
    try:
        with (output / "ghidra.log").open("wb") as log:
            finished = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                      check=False)
    except OSError as error:
        raise GhidraError(f"cannot start Ghidra: {error}; inspect {output}") from error
    if finished.returncode != 0:
        raise GhidraError(f"analyzeHeadless returned {finished.returncode}; inspect {output / 'ghidra.log'}")
    return validate_export(output, str(identity["sha256"]), mode)
