#!/usr/bin/env python3
"""Prepare and capture bounded Warcraft III Retail JASS probes.

A JSON manifest names a source campaign map, exact JASS line anchors, injected
JASS fragments, and the expected PreloadGen result path. Preparation preserves
the source and verifies the repacked script byte-for-byte. Capture accepts only
a result file refreshed after preparation; it does not interpret observations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PRELOAD_RE = re.compile(r'Preload\s*\(\s*"((?:\\.|[^"\\])*)"\s*\)', re.S)


class ProbeError(RuntimeError):
    """A preparation or capture input failed validation."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(args, cwd=cwd, check=False, capture_output=True)
    if result.returncode:
        detail = result.stderr.decode(errors="replace").strip()
        if not detail:
            detail = result.stdout.decode(errors="replace").strip()
        raise ProbeError(f"command failed ({result.returncode}): {' '.join(args)}\n{detail}")
    return result


def mpq_bytes(mpqtool: Path, archive: Path, command: str, member: str | None = None) -> bytes:
    args = [str(mpqtool), "-mpq", str(archive), command]
    if member:
        args.append(member)
    return run(args).stdout


def resolve_manifest_path(value: str, base: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def read_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProbeError(f"cannot read manifest {path}: {error}") from error
    if not isinstance(manifest, dict):
        raise ProbeError("manifest root must be a JSON object")

    source = manifest.get("source")
    if not isinstance(source, dict):
        raise ProbeError("manifest must contain a source object")
    if not source.get("archive") or not source.get("member"):
        raise ProbeError("source must contain archive and member")
    map_member = PurePosixPath(str(source["member"]).replace("\\", "/"))
    if map_member.is_absolute() or ".." in map_member.parts:
        raise ProbeError(f"unsafe source map member: {map_member}")
    if map_member.suffix.lower() not in (".w3m", ".w3x"):
        raise ProbeError(f"source member must be a .w3m or .w3x map: {map_member}")
    source["member"] = map_member.as_posix()

    script_member = PurePosixPath(str(manifest.get("script_member", "war3map.j")))
    if script_member.is_absolute() or ".." in script_member.parts or len(script_member.parts) != 1:
        raise ProbeError("script_member must be a root archive member such as war3map.j")
    manifest["script_member"] = script_member.as_posix()

    probe_id = str(manifest.get("id", "")).strip()
    if not probe_id or not re.fullmatch(r"[A-Za-z0-9_.-]+", probe_id):
        raise ProbeError("manifest id is required and may contain only letters, digits, '.', '_' and '-'")
    edits = manifest.get("edits")
    if not isinstance(edits, list) or not edits:
        raise ProbeError("manifest must contain a non-empty edits array")
    for index, edit in enumerate(edits):
        if not isinstance(edit, dict):
            raise ProbeError(f"edit {index} must be an object")
        if not all(edit.get(key) for key in ("function", "anchor", "where")):
            raise ProbeError(f"edit {index} requires function, anchor and where")
        if not all(isinstance(edit[key], str) for key in ("function", "anchor", "where")):
            raise ProbeError(f"edit {index} function, anchor and where must be strings")
        if edit["where"] not in ("before", "after"):
            raise ProbeError(f"edit {index} where must be 'before' or 'after'")
        if bool(edit.get("text")) == bool(edit.get("file")):
            raise ProbeError(f"edit {index} must provide exactly one of text or file")
        if "\n" in edit["anchor"] or "\r" in edit["anchor"]:
            raise ProbeError(f"edit {index} anchor must be one line")
    if not manifest.get("result_file"):
        raise ProbeError("manifest result_file is required for fresh-result capture")
    if not isinstance(manifest["result_file"], str):
        raise ProbeError("result_file must be a string path")
    if "metadata" in manifest and not isinstance(manifest["metadata"], dict):
        raise ProbeError("metadata must be a JSON object")
    return manifest


def edit_text(edit: dict[str, Any], base: Path) -> str:
    if "text" in edit:
        fragment = str(edit["text"])
    else:
        fragment_path = resolve_manifest_path(str(edit["file"]), base)
        try:
            fragment = fragment_path.read_text(encoding="utf-8")
        except OSError as error:
            raise ProbeError(f"cannot read JASS fragment {fragment_path}: {error}") from error
    fragment = fragment.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if not fragment.strip():
        raise ProbeError("JASS edit fragment is empty")
    return fragment


def function_range(script: str, name: str) -> tuple[int, int]:
    header = re.compile(rf"(?m)^function\s+{re.escape(name)}\s+takes\b[^\r\n]*(?:\r?\n|$)")
    matches = list(header.finditer(script))
    if len(matches) != 1:
        raise ProbeError(f"expected one function declaration for {name}, found {len(matches)}")
    start = matches[0].start()
    end_match = re.search(r"(?m)^endfunction[ \t]*(?:\r?$)", script[matches[0].end():])
    if end_match is None:
        raise ProbeError(f"function {name} has no endfunction")
    return start, matches[0].end() + end_match.end()


def line_offsets(text: str) -> list[tuple[int, int, str]]:
    rows = []
    offset = 0
    for line in text.splitlines(keepends=True):
        rows.append((offset, offset + len(line), line))
        offset += len(line)
    if offset < len(text):
        rows.append((offset, len(text), text[offset:]))
    return rows


def apply_edits(script: str, edits: list[dict[str, Any]], base: Path) -> str:
    newline = "\r\n" if "\r\n" in script else "\n"
    insertions: list[tuple[int, str, str]] = []
    for index, edit in enumerate(edits):
        start, end = function_range(script, str(edit["function"]))
        function_text = script[start:end]
        anchor = str(edit["anchor"]).strip()
        found: list[tuple[int, int, str]] = []
        for line_start, line_end, line in line_offsets(function_text):
            if line.rstrip("\r\n").strip() == anchor:
                found.append((start + line_start, start + line_end, line))
        if len(found) != 1:
            raise ProbeError(
                f"edit {index}: expected one line matching anchor {anchor!r} inside "
                f"{edit['function']}, found {len(found)}")
        line_start, line_end, _ = found[0]
        fragment = edit_text(edit, base).replace("\n", newline)
        if edit["where"] == "before":
            insertions.append((line_start, fragment + newline, f"edit {index} before {anchor!r}"))
        else:
            line = found[0][2]
            prefix = "" if line.endswith(("\n", "\r")) else newline
            insertions.append((line_end, prefix + fragment + newline,
                               f"edit {index} after {anchor!r}"))

    positions = [position for position, _, _ in insertions]
    if len(positions) != len(set(positions)):
        raise ProbeError("multiple edits resolve to the same insertion point")
    for position, addition, _description in sorted(insertions, reverse=True):
        script = script[:position] + addition + script[position:]
    return script


def snapshot_result(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    if not path.is_file():
        raise ProbeError(f"result_file is not a regular file: {path}")
    stat = path.stat()
    return {"exists": True, "mtime_ns": stat.st_mtime_ns,
            "size": stat.st_size, "sha256": sha256_file(path)}


def map_root_members(mpqtool: Path, archive: Path) -> list[str]:
    listing = mpq_bytes(mpqtool, archive, "ls").decode("utf-8", errors="replace")
    return sorted(line.strip().replace("\\", "/").rstrip("/")
                  for line in listing.splitlines() if line.strip())


def prepare(args: argparse.Namespace) -> None:
    manifest_path = args.manifest.expanduser().resolve()
    manifest = read_manifest(manifest_path)
    base = manifest_path.parent
    archive = resolve_manifest_path(str(manifest["source"]["archive"]), base)
    if not archive.is_file():
        raise ProbeError(f"source archive not found: {archive}")
    executable_path: Path | None = None
    if manifest.get("retail_executable"):
        executable_path = resolve_manifest_path(str(manifest["retail_executable"]), base)
        if not executable_path.is_file():
            raise ProbeError(f"Retail executable not found: {executable_path}")
    if not args.mpqtool.is_file():
        raise ProbeError(f"mpqtool not found: {args.mpqtool}")
    smpq = shutil.which(args.smpq)
    if not smpq:
        raise ProbeError(f"smpq not found on PATH: {args.smpq}")

    output_dir = args.output_dir.expanduser().resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ProbeError(f"output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    prepared_at_ns = time.time_ns()
    result_file = resolve_manifest_path(str(manifest["result_file"]), base)
    result_before = snapshot_result(result_file)
    archive_before = sha256_file(archive)

    control_dir = output_dir / "control"
    stage_dir = output_dir / "stage"
    control_dir.mkdir(exist_ok=True)
    stage_dir.mkdir(exist_ok=True)
    map_path = control_dir / PurePosixPath(str(manifest["source"]["member"])).name
    script_path = stage_dir / str(manifest["script_member"])
    output_name = str(manifest.get("output_name") or map_path.name)
    if Path(output_name).name != output_name or output_name in (".", ".."):
        raise ProbeError("output_name must be a filename without directory components")
    output_map = output_dir / output_name
    if output_map.suffix.lower() not in (".w3m", ".w3x"):
        raise ProbeError("output_name must end in .w3m or .w3x")
    manifest_copy = output_dir / "manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest_copy.write_bytes(manifest_bytes)

    try:
        map_bytes = mpq_bytes(args.mpqtool, archive, "cat", str(manifest["source"]["member"]))
        map_path.write_bytes(map_bytes)
        source_script = mpq_bytes(args.mpqtool, map_path, "cat", str(manifest["script_member"]))
        control_members = map_root_members(args.mpqtool, map_path)
        exact_before = [name for name in control_members
                        if name.casefold() == str(manifest["script_member"]).casefold()]
        if len(exact_before) != 1:
            raise ProbeError(
                f"control map must contain exactly one root {manifest['script_member']} member; "
                f"found {len(exact_before)}")
        # Preserve any legacy non-UTF-8 comment bytes while editing ASCII anchors.
        script_text = source_script.decode("utf-8", errors="surrogateescape")
        edited_text = apply_edits(script_text, manifest["edits"], base)
        edited_bytes = edited_text.encode("utf-8", errors="surrogateescape")
        script_path.write_bytes(edited_bytes)
        shutil.copyfile(map_path, output_map)
        run([smpq, "-a", "-f", str(output_map), str(script_path.name)], cwd=stage_dir)

        member_names = map_root_members(args.mpqtool, output_map)
        if member_names != control_members:
            added = sorted(set(member_names) - set(control_members))
            removed = sorted(set(control_members) - set(member_names))
            raise ProbeError(f"map member list changed during repack; added={added}, removed={removed}")
        exact_scripts = [name for name in member_names
                         if name.casefold() == str(manifest["script_member"]).casefold()]
        if len(exact_scripts) != 1:
            raise ProbeError(
                f"expected exactly one root {manifest['script_member']} member, "
                f"found {len(exact_scripts)}")
        embedded_script = mpq_bytes(args.mpqtool, output_map, "cat", str(manifest["script_member"]))
        if embedded_script != edited_bytes:
            raise ProbeError("embedded JASS differs from the staged edited script")
        if sha256_file(archive) != archive_before:
            raise ProbeError("source archive changed during preparation")
    except (OSError, ProbeError) as error:
        raise ProbeError(f"preparation failed: {error}; inspect {output_dir}") from error

    record = {
        "id": manifest["id"],
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "prepared_at_ns": prepared_at_ns,
        "manifest": str(manifest_path),
        "manifest_copy": str(manifest_copy),
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "source_archive": str(archive),
        "source_archive_sha256": archive_before,
        "retail_executable": str(executable_path) if executable_path else None,
        "retail_executable_sha256": sha256_file(executable_path) if executable_path else None,
        "source_map_member": str(manifest["source"]["member"]),
        "control_map": str(map_path),
        "control_map_sha256": sha256_bytes(map_bytes),
        "root_members": control_members,
        "script_member": str(manifest["script_member"]),
        "source_script_sha256": sha256_bytes(source_script),
        "edited_script": str(script_path),
        "edited_script_sha256": sha256_bytes(edited_bytes),
        "prepared_map": str(output_map),
        "prepared_map_sha256": sha256_file(output_map),
        "result_file": str(result_file),
        "result_before_prepare": result_before,
        "metadata": manifest.get("metadata", {}),
        "notes": manifest.get("notes", ""),
    }
    (output_dir / "probe.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared map: {output_map}")
    print(f"Verified one {manifest['script_member']} member and byte-matched it to: {script_path}")
    print(f"After the Retail run, capture the fresh result with: "
          f"python3 {Path(__file__).resolve()} capture {output_dir}")


def decode_jass_string(value: str) -> str:
    return re.sub(r'\\(["\\])', r"\1", value)


def capture(args: argparse.Namespace) -> None:
    output_dir = args.probe_dir.expanduser().resolve()
    record_path = output_dir / "probe.json"
    if not record_path.is_file():
        raise ProbeError(f"prepared probe record not found: {record_path}")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    result_path = Path(record["result_file"])
    baseline = record["result_before_prepare"]
    capture_txt = output_dir / "result.txt"
    capture_json = output_dir / "capture.json"
    if capture_txt.exists() or capture_json.exists():
        raise ProbeError(f"capture output already exists in {output_dir}")

    deadline = time.monotonic() + args.timeout
    fresh_snapshot: dict[str, Any] | None = None
    while time.monotonic() <= deadline:
        if result_path.is_file():
            current = snapshot_result(result_path)
            newer = current["mtime_ns"] > record["prepared_at_ns"]
            changed = (not baseline.get("exists")
                       or current["mtime_ns"] != baseline.get("mtime_ns")
                       or current["sha256"] != baseline.get("sha256"))
            if newer and changed and current["size"] > 0:
                fresh_snapshot = current
                break
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(args.poll_interval, remaining))
    if fresh_snapshot is None:
        raise ProbeError(
            f"no fresh non-empty result at {result_path} within {args.timeout:g}s; "
            "the probe may not have run or PreloadGen may not have completed")

    raw = result_path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    values = [decode_jass_string(match) for match in PRELOAD_RE.findall(text)]
    capture_txt.write_bytes(raw)
    report = {
        "probe_id": record["id"],
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "result_file": str(result_path),
        "result_mtime_ns": fresh_snapshot["mtime_ns"],
        "result_sha256": fresh_snapshot["sha256"],
        "raw_copy": str(capture_txt),
        "preload_values": values,
        "interpretation": "Not inferred by this tool; review the raw output and probe contract.",
    }
    capture_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Captured fresh result: {capture_txt}")
    print(f"Parsed {len(values)} Preload value(s); review {capture_json}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare", help="extract, instrument and validate a copied map")
    prepare_parser.add_argument("manifest", type=Path, help="probe JSON manifest")
    prepare_parser.add_argument("output_dir", type=Path, help="new or empty output directory")
    prepare_parser.add_argument("--mpqtool", type=Path, default=ROOT / "build/bin/mpqtool")
    prepare_parser.add_argument("--smpq", default="smpq", help="StormLib smpq executable")
    prepare_parser.set_defaults(func=prepare)

    capture_parser = commands.add_parser("capture", help="wait for and save a fresh PreloadGen result")
    capture_parser.add_argument("probe_dir", type=Path, help="directory created by prepare")
    capture_parser.add_argument("--timeout", type=float, default=180.0)
    capture_parser.add_argument("--poll-interval", type=float, default=1.0)
    capture_parser.set_defaults(func=capture)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if getattr(args, "timeout", 1.0) <= 0 or getattr(args, "poll_interval", 0.1) <= 0:
        print("error: timeout and poll-interval must be positive", file=sys.stderr)
        return 2
    try:
        args.func(args)
    except (OSError, ProbeError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
