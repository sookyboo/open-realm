#!/usr/bin/env python3
"""Run a bounded Frida agent against the prepared, live WC3 Retail launch.

The caller supplies a reviewed JavaScript agent. This controller validates the
probe launch identity and executable hash, attaches to the unique recorded
Retail process, and writes a new JSONL evidence file without overwriting data.
"""
import argparse
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import frida


EXPECTED_FRIDA = "17.19.0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("probe_dir", type=Path)
    parser.add_argument("--agent", type=Path, required=True, help="reviewed Frida JavaScript agent")
    parser.add_argument("--remote", default="127.0.0.1:27043")
    parser.add_argument("--pid", type=int, help="Frida/Windows PID; required if Retail is ambiguous")
    parser.add_argument("--seconds", type=float, default=60)
    parser.add_argument("--output", type=Path, required=True, help="new JSONL output path")
    args = parser.parse_args()

    run_dir = args.probe_dir.expanduser().resolve()
    launch_path = run_dir / "launch.json"
    try:
        launch = json.loads(launch_path.read_text(encoding="utf-8"))
        probe = json.loads((run_dir / "probe.json").read_text(encoding="utf-8"))
        agent_path = args.agent.expanduser().resolve()
        agent_source = agent_path.read_text(encoding="utf-8")
        exe = Path(launch["retail_executable"]).resolve()
    except (OSError, KeyError, json.JSONDecodeError) as error:
        parser.error(f"cannot load prepared Retail records/agent: {error}")
    output = args.output.expanduser().resolve()
    if output.exists():
        parser.error(f"refusing to overwrite trace output: {output}")
    if not (0 < args.seconds <= 300):
        parser.error("--seconds must be in (0, 300]")
    if frida.__version__ != EXPECTED_FRIDA:
        parser.error(f"expected Frida {EXPECTED_FRIDA}, found {frida.__version__}")
    if launch.get("role") != "prepared" or launch.get("probe_id") != probe.get("id"):
        parser.error("latest launch is not the prepared launch for this probe")
    if not launch.get("control_screen_confirmed"):
        parser.error("prepared launch lacks untouched-control screen confirmation")
    command = launch.get("command", [])
    if (str(exe) not in command or "-window" not in command
            or "-graphicsapi" not in command or "OpenGL2" not in command
            or "-loadfile" not in command
            or launch.get("windows_map_path") not in command):
        parser.error("launch record lacks the expected executable, map, or Retail flags")
    if launch.get("retail_executable_sha256") != sha256(exe):
        parser.error("Retail executable hash differs from the recorded launch")
    required_hash = re.search(r"(?m)^\s*//\s*WC3_RETAIL_SHA256:\s*([0-9a-f]{64})\s*$", agent_source)
    if required_hash and required_hash.group(1) != sha256(exe):
        parser.error("Frida agent declares a different supported Retail executable hash")
    map_path = Path(launch["map_path"]).resolve()
    if (launch.get("map_sha256") != probe.get("prepared_map_sha256")
            or sha256(map_path) != launch.get("map_sha256")):
        parser.error("prepared map hash/path does not match probe records")
    pid = int(launch["pid"])
    try:
        host_argv = [part.decode(errors="replace") for part in
                     Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0") if part]
    except OSError as error:
        parser.error(f"recorded Wine Retail host process is not running: {error}")
    if str(exe) not in host_argv or launch.get("windows_map_path") not in host_argv:
        parser.error("recorded Wine PID is not running the prepared executable/map")

    device = frida.get_device_manager().add_remote_device(args.remote)
    remote = device.query_system_parameters()
    if remote.get("platform") != "windows":
        parser.error(f"Frida endpoint is not the expected Windows Wine device: {remote}")
    candidates = [process for process in device.enumerate_processes()
                  if process.name.lower() == "warcraft iii.exe"]
    if args.pid is not None:
        candidates = [process for process in candidates if process.pid == args.pid]
    if len(candidates) != 1:
        parser.error(f"expected one Retail Frida process, found {[p.pid for p in candidates]}; use --pid")
    target = candidates[0]
    output.parent.mkdir(parents=True, exist_ok=True)
    errors = []
    with output.open("x", encoding="utf-8") as stream:
        def record(row):
            stream.write(json.dumps(row, sort_keys=True) + "\n")
            stream.flush()

        record({"event": "trace-metadata", "probe_id": probe["id"],
                "frida": frida.__version__, "remote": args.remote, "pid": target.pid,
                "seconds": args.seconds, "agent": str(agent_path),
                "agent_sha256": hashlib.sha256(agent_source.encode()).hexdigest(),
                "retail_executable": str(exe), "retail_sha256": sha256(exe),
                "agent_required_retail_sha256": required_hash.group(1) if required_hash else None,
                "map": str(map_path), "map_sha256": launch["map_sha256"],
                "started_at": datetime.now(timezone.utc).isoformat()})

        def on_message(message, _data):
            if message["type"] == "send":
                record(message["payload"])
            else:
                record({"event": "frida-error", "message": message})
                if message["type"] == "error":
                    errors.append(message.get("description", str(message)))

        session = device.attach(target.pid)
        try:
            script = session.create_script(agent_source)
            script.on("message", on_message)
            script.load()
            deadline = time.monotonic() + args.seconds
            while time.monotonic() < deadline and not errors:
                time.sleep(min(0.1, max(0, deadline - time.monotonic())))
        finally:
            session.detach()
            record({"event": "trace-end", "pid": target.pid,
                    "ended_at": datetime.now(timezone.utc).isoformat(), "errors": errors})
    if errors:
        raise RuntimeError("Frida agent failed: " + "; ".join(errors))
    print(f"Trace saved: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
