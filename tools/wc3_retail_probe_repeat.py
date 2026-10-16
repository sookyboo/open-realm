#!/usr/bin/env python3
"""Prepare and capture repeated runs of a Warcraft III Retail JASS probe.

Each iteration receives a private manifest/output directory and a unique
PreloadGen result filename. Retail map confirmation and scenario interaction
remain operator driven.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE_TOOL = ROOT / "tools/wc3_retail_probe.py"


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def confirm(prompt: str) -> None:
    try:
        answer = input(prompt + " [y/N] ").strip().lower()
    except EOFError as error:
        raise RuntimeError("interactive confirmation required; rerun in a terminal") from error
    if answer not in ("y", "yes"):
        raise RuntimeError("stopped at operator request")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="base probe manifest")
    parser.add_argument("output_root", type=Path, help="new or empty directory for all runs")
    parser.add_argument("--runs", type=int, default=2, help="number of iterations (default: 2)")
    parser.add_argument("--mpqtool", type=Path, default=ROOT / "build/bin/mpqtool")
    parser.add_argument("--smpq", default="smpq")
    parser.add_argument("--wine", default="wine")
    parser.add_argument("--winepath", default="winepath")
    parser.add_argument("--wine-prefix", type=Path)
    parser.add_argument("--display", help="X display forwarded to Retail launches")
    parser.add_argument("--xauthority", help="Xauthority file forwarded to Retail launches")
    parser.add_argument("--timeout", type=float, default=240.0)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")

    source_manifest = args.manifest.expanduser().resolve()
    output_root = args.output_root.expanduser().resolve()
    if not source_manifest.is_file():
        parser.error(f"manifest not found: {source_manifest}")
    if output_root.exists() and any(output_root.iterdir()):
        parser.error(f"output root must be new or empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    base = source_manifest.parent
    # Normalize manifest-relative paths before copying it into each run folder.
    for key in ("archive",):
        value = Path(manifest["source"][key]).expanduser()
        manifest["source"][key] = str((base / value).resolve() if not value.is_absolute() else value.resolve())
    if manifest.get("retail_executable"):
        value = Path(manifest["retail_executable"]).expanduser()
        manifest["retail_executable"] = str((base / value).resolve() if not value.is_absolute() else value.resolve())
    for edit in manifest["edits"]:
        if "file" in edit:
            value = Path(edit["file"]).expanduser()
            edit["file"] = str((base / value).resolve() if not value.is_absolute() else value.resolve())

    result_path = Path(manifest["result_file"]).expanduser()
    result_parent = result_path.parent
    result_stem = result_path.stem
    result_suffix = result_path.suffix or ".txt"
    output_name = Path(manifest.get("output_name", "probe.w3x"))
    output_stem, output_suffix = output_name.stem, output_name.suffix

    try:
        for index in range(1, args.runs + 1):
            run_id = f"run-{index:03d}"
            run_dir = output_root / run_id
            run_dir.mkdir()
            current = json.loads(json.dumps(manifest))
            current["id"] = f"{manifest['id']}-{run_id}"
            current["result_file"] = str(result_parent / f"{result_stem}-{index:03d}{result_suffix}")
            current["output_name"] = f"{output_stem}-{index:03d}{output_suffix}"
            for edit in current["edits"]:
                if "file" not in edit:
                    continue
                fragment = Path(edit["file"])
                content = fragment.read_text(encoding="utf-8")
                content = content.replace("@RESULT_FILE@", Path(current["result_file"]).name)
                copied_fragment = run_dir / fragment.name
                copied_fragment.write_text(content, encoding="utf-8")
                edit["file"] = str(copied_fragment)
            current_manifest = run_dir / "manifest.json"
            current_manifest.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")

            run([sys.executable, str(PROBE_TOOL), "prepare", str(current_manifest),
                 str(run_dir / "probe"), "--mpqtool", str(args.mpqtool), "--smpq", args.smpq])
            probe_dir = run_dir / "probe"
            run([sys.executable, str(PROBE_TOOL), "launch", str(probe_dir), "--control",
                 "--wine", args.wine, "--winepath", args.winepath,
                 *( ["--wine-prefix", str(args.wine_prefix)] if args.wine_prefix else []),
                 *( ["--display", args.display] if args.display else []),
                 *( ["--xauthority", args.xauthority] if args.xauthority else [])])
            confirm(f"{run_id}: confirm the untouched control reached its expected screen and exit Retail")
            run([sys.executable, str(PROBE_TOOL), "launch", str(probe_dir), "--control-confirmed",
                 "--wine", args.wine, "--winepath", args.winepath,
                 *( ["--wine-prefix", str(args.wine_prefix)] if args.wine_prefix else []),
                 *( ["--display", args.display] if args.display else []),
                 *( ["--xauthority", args.xauthority] if args.xauthority else [])])
            confirm(f"{run_id}: complete the documented prepared-map interaction and allow the probe to finish")
            run([sys.executable, str(PROBE_TOOL), "capture", str(probe_dir),
                 "--timeout", str(args.timeout)])
            print(f"Completed {run_id}; artifacts: {run_dir}", flush=True)
    except (OSError, subprocess.CalledProcessError, RuntimeError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
