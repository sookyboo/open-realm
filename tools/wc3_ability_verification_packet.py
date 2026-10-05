#!/usr/bin/env python3
"""Build a Retail-data and native-analysis packet for WC3 ability verification.

Examples:
  python3 tools/wc3_ability_verification_packet.py Apxf AOeq \
    --output /tmp/wc3-ability-packet.md
  python3 tools/wc3_ability_verification_packet.py --rawcodes-file /tmp/rows.txt \
    --claims-file /tmp/claims.json --native-address Apxf=0x00C0ECD0,0x00C0F1E0

The tool captures ability_audit output and records the exact executable hash.
It does not infer behavior from names, data, or addresses; the generated
worksheet keeps those conclusions and any remaining runtime questions explicit.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "data/Warcraft III"
DEFAULT_EXE = DEFAULT_DATA / "Warcraft III.exe"
DEFAULT_AUDIT = ROOT / "build/bin/ability_audit"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_rawcodes(args: argparse.Namespace) -> list[str]:
    values = list(args.rawcodes)
    if args.rawcodes_file:
        for line_number, line in enumerate(args.rawcodes_file.read_text(encoding="utf-8").splitlines(), 1):
            line = line.split("#", 1)[0]
            values.extend(line.replace(",", " ").split())
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        rawcode = value.strip()
        if len(rawcode) != 4:
            raise ValueError(f"rawcode must contain exactly four characters: {value!r}")
        if rawcode not in seen:
            rows.append(rawcode)
            seen.add(rawcode)
    if not rows:
        raise ValueError("provide rawcodes as arguments or with --rawcodes-file")
    return rows


def load_claims(path: Path | None, rawcodes: list[str]) -> dict[str, list[str]]:
    if path is None:
        return {rawcode: [] for rawcode in rawcodes}
    value: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("claims JSON must be an object mapping rawcodes to arrays of strings")
    result: dict[str, list[str]] = {}
    for rawcode in rawcodes:
        claims = value.get(rawcode, [])
        if not isinstance(claims, list) or not all(isinstance(claim, str) for claim in claims):
            raise ValueError(f"claims for {rawcode} must be an array of strings")
        result[rawcode] = claims
    return result


def load_addresses(values: list[str], rawcodes: list[str]) -> dict[str, list[str]]:
    result = {rawcode: [] for rawcode in rawcodes}
    for value in values:
        if "=" not in value:
            raise ValueError(f"native address must be RAWCODE=ADDR[,ADDR...]: {value!r}")
        rawcode, address_list = value.split("=", 1)
        if rawcode not in result:
            raise ValueError(f"native address names rawcode not in this packet: {rawcode}")
        addresses = [item.strip() for item in address_list.split(",") if item.strip()]
        if not addresses:
            raise ValueError(f"no addresses supplied for {rawcode}")
        for address in addresses:
            try:
                int(address, 0)
            except ValueError as error:
                raise ValueError(f"invalid native address {address!r}") from error
        result[rawcode].extend(addresses)
    return result


def run_audit(audit: Path, data_dir: Path, rawcode: str, *, tooltip: bool) -> tuple[int, str, str]:
    # Supplying archives individually avoids recursively loading movie MPQs and
    # makes the exact data source/order visible in every captured audit.
    command = [str(audit)]
    for name in ("War3xLocal.mpq", "War3x.mpq", "War3Local.mpq", "War3.mpq", "Deprecated.mpq"):
        archive = data_dir / name
        if archive.is_file():
            command.extend(["-mpq", str(archive)])
    if tooltip:
        command.extend(["-tft", "-resolve-tooltip", rawcode])
    else:
        # No edition flag makes ability_audit print both ROC and TFT rows.
        command.extend(["-raw", rawcode])
    try:
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
    except OSError as error:
        return 127, "", str(error)
    return completed.returncode, completed.stdout.rstrip(), completed.stderr.rstrip()


def audit_supports_tooltip(audit: Path) -> bool:
    try:
        completed = subprocess.run([str(audit), "--help"], text=True,
                                   capture_output=True, check=False)
    except OSError:
        return False
    return "-resolve-tooltip" in completed.stderr or "-resolve-tooltip" in completed.stdout


def markdown_fence(text: str) -> str:
    # Audit output is plain text, but choose a longer fence if a row contains one.
    runs = re.findall(r"`+", text)
    longest = max((len(run) for run in runs), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}text\n{text}\n{fence}"


def render(args: argparse.Namespace, rawcodes: list[str], claims: dict[str, list[str]],
           addresses: dict[str, list[str]], executable_hash: str,
           data_hashes: list[tuple[str, int, str | None]], *, tooltip_supported: bool) -> tuple[str, bool]:
    lines = [
        "# Warcraft III ability verification packet",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"Retail executable: `{args.executable}`",
        f"Retail executable SHA-256: `{executable_hash}`",
        f"Ability data directory: `{args.data_dir}`",
        "",
        "Data archives used by this installation:",
        "",
    ]
    if data_hashes:
        for name, size, digest in data_hashes:
            suffix = f"; SHA-256 `{digest}`" if digest else "; hash omitted (use `--hash-data-archives` to compute it)"
            lines.append(f"- `{name}` — {size:,} bytes{suffix}")
    else:
        lines.append("- No standard `War3*.mpq` archives were found in the data directory.")
    lines.extend([
        "",
        "> Address evidence is valid only for the executable hash above. Object data and tooltip text establish authored values; they do not by themselves establish runtime behavior.",
        "> A class label printed by `ability_audit` may come from the checked-in registry. Confirm rawcode registration and the concrete vtable in the executable above before using it to select a hook.",
        "",
        "## Batch overview",
        "",
        "| Rawcode | Claims supplied | Data audit | Resolved TFT tooltip |",
        "|---|---:|---|---|",
    ])

    captures: dict[str, tuple[tuple[int, str, str], tuple[int, str, str]]] = {}
    complete = True
    for rawcode in rawcodes:
        raw = run_audit(args.audit, args.data_dir, rawcode, tooltip=False)
        tip = (run_audit(args.audit, args.data_dir, rawcode, tooltip=True) if tooltip_supported
               else (2, "", "ability_audit lacks -resolve-tooltip; rebuild it with `make build/bin/ability_audit`"))
        captures[rawcode] = raw, tip
        raw_status = "captured" if raw[0] == 0 else f"exit {raw[0]}"
        tooltip_open = "[UNRESOLVED:" in tip[1] or "[UNSUPPORTED:" in tip[1]
        tip_absent = tip[0] == 0 and "not found" in tip[1].lower()
        tip_status = ("no TFT row" if tip_absent else
                      ("unresolved placeholders" if tooltip_open else
                       ("captured" if tip[0] == 0 else f"exit {tip[0]}")))
        if raw[0] != 0 or tip[0] != 0:
            complete = False
        lines.append(f"| `{rawcode}` | {len(claims[rawcode])} | {raw_status} | {tip_status} |")

    for rawcode in rawcodes:
        raw, tip = captures[rawcode]
        lines.extend([
            "",
            f"## `{rawcode}`",
            "",
            "### Claims to settle",
            "",
        ])
        if claims[rawcode]:
            lines.extend(f"- [ ] {claim}" for claim in claims[rawcode])
        else:
            lines.append("- [ ] Add a narrow behavior claim before treating this row as verified.")
        lines.extend(["", "### ROC and TFT AbilityData audit", ""])
        if raw[1]:
            lines.append(markdown_fence(raw[1]))
        else:
            lines.append("No stdout was returned.")
        if raw[2]:
            lines.extend(["", "Audit diagnostics:", "", markdown_fence(raw[2])])
        lines.extend(["", "### TFT resolved tooltip", ""])
        if tip[1]:
            lines.append(markdown_fence(tip[1]))
        else:
            lines.append("No stdout was returned.")
        if tip[2]:
            lines.extend(["", "Tooltip diagnostics:", "", markdown_fence(tip[2])])
        lines.extend([
            "",
            "### Exact-build native trace worksheet",
            "",
            "- Implementation FOURCC and concrete class:",
            "- Registration / instance generator and constructor:",
            "- Ability vtable and relevant virtual slots:",
            "- Callback or order entry point:",
            "- Caller → helper → effect path:",
            "- Target predicates and branch outcomes:",
            "- Native field read → AbilityData/BuffData/UnitData field:",
            "- Resulting gameplay state/effect:",
            "- Inverse, expiry, interruption, and save/load path:",
            "- Frida needed? Name the unresolved dynamic question:",
            "- JASS/Retail run needed? Name the unresolved observable result:",
            "- Status: unreviewed / partial / verified / inconclusive",
            "",
        ])
        if addresses[rawcode]:
            headless = Path(args.ghidra_home) / "support/analyzeHeadless"
            command = [
                str(headless), args.ghidra_project, args.ghidra_project_name,
                "-process", Path(args.executable).name, "-noanalysis",
                "-scriptPath", str(ROOT / "tools/ghidra"),
                "-postScript", "Wc3DumpFunction.java", *addresses[rawcode],
            ]
            lines.extend([
                "Ghidra command for supplied addresses:",
                "",
                markdown_fence(shlex.join(command)),
                "",
            ])
        else:
            lines.extend([
                "Ghidra command template (add exact-build addresses after confirming them in r2):",
                "",
                markdown_fence(
                    f"{Path(args.ghidra_home) / 'support/analyzeHeadless'} "
                    f"{shlex.quote(args.ghidra_project)} {shlex.quote(args.ghidra_project_name)} "
                    f"-process {shlex.quote(Path(args.executable).name)} -noanalysis "
                    f"-scriptPath {shlex.quote(str(ROOT / 'tools/ghidra'))} "
                    "-postScript Wc3DumpFunction.java <confirmed-VA> [<confirmed-VA> ...]"
                ),
                "",
            ])
    return "\n".join(lines).rstrip() + "\n", complete


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("rawcodes", nargs="*", help="four-character AbilityData rawcodes")
    parser.add_argument("--rawcodes-file", type=Path, help="text file with rawcodes separated by whitespace or commas; # starts a comment")
    parser.add_argument("--claims-file", type=Path, help="JSON object mapping rawcodes to arrays of behavior claims")
    parser.add_argument("--native-address", action="append", default=[], metavar="RAW=ADDR[,ADDR...]",
                        help="confirmed preferred VA(s), repeat once per rawcode")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA, help="installed Warcraft III data directory")
    parser.add_argument("--executable", type=Path, default=DEFAULT_EXE, help="exact Retail executable being analyzed")
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT, help="built ability_audit executable")
    parser.add_argument("--output", type=Path, help="write Markdown here instead of stdout")
    parser.add_argument("--hash-data-archives", action="store_true",
                        help="also hash installed MPQs (reads up to several GB)")
    parser.add_argument("--ghidra-home", default="/opt/openrealm-tools/ghidra_12.1.4_PUBLIC",
                        help="Ghidra installation root, used for generated commands")
    parser.add_argument("--ghidra-project", default="/tmp/wc3-ghidra-ability",
                        help="cached Ghidra project directory")
    parser.add_argument("--ghidra-project-name", default="Wc3Retail1292",
                        help="cached Ghidra project name")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args.data_dir = args.data_dir.resolve()
    args.executable = args.executable.resolve()
    args.audit = args.audit.resolve()
    try:
        if not args.data_dir.is_dir():
            raise ValueError(f"data directory does not exist: {args.data_dir}")
        if not args.executable.is_file():
            raise ValueError(f"Retail executable does not exist: {args.executable}")
        if not args.audit.is_file():
            raise ValueError(f"ability_audit is missing: {args.audit}; build it with `make build/bin/ability_audit`")
        rawcodes = read_rawcodes(args)
        claims = load_claims(args.claims_file, rawcodes)
        addresses = load_addresses(args.native_address, rawcodes)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ability-packet: {error}", file=sys.stderr)
        return 2

    archives: list[tuple[str, int, str | None]] = []
    for name in ("War3.mpq", "War3x.mpq", "War3Local.mpq", "War3xLocal.mpq", "Deprecated.mpq"):
        archive = args.data_dir / name
        if archive.is_file():
            archives.append((name, archive.stat().st_size,
                             sha256_file(archive) if args.hash_data_archives else None))
    report, complete = render(args, rawcodes, claims, addresses, sha256_file(args.executable), archives,
                              tooltip_supported=audit_supports_tooltip(args.audit))
    if args.output:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(report, encoding="utf-8")
        except OSError as error:
            print(f"ability-packet: cannot write {args.output}: {error}", file=sys.stderr)
            return 2
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(report)
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
