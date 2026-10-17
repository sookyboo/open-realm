"""Coordinate bounded Frida/JASS captures in one already-running Retail process.

Session setup is offline. Live mode attaches to a separately launched, verified
Retail Wine process and uses Frida only for read-only tracing. Nothing launches
Warcraft, loads another map, changes game state, or performs a JHCR update.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Any
from threading import Lock

from wc3_re.frida import TraceError, _agent_source, summarize_trace


class SessionError(TraceError):
    """An incompatible or unproven session/capture boundary."""


_SAFE = re.compile(r"[A-Za-z0-9_.-]{1,80}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_STAGES = {"ready_for_review", "failed", "inconclusive", "timeout", "error"}
_PRELOAD = re.compile(r'Preload\s*\(\s*"((?:\\.|[^"\\])*)"\s*\)')


def digest(path: Path) -> str:
    hashed = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hashed.update(chunk)
    return hashed.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SessionError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise SessionError(f"expected a JSON object: {path}")
    return value


def save_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise SessionError(f"refusing to overwrite {path}")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _matching_file(path: Any, sha: Any, label: str) -> Path:
    if not isinstance(path, str) or not path or not isinstance(sha, str) or not _SHA.fullmatch(sha):
        raise SessionError(f"{label}: missing path or pinned SHA-256")
    candidate = Path(path).expanduser().resolve()
    if not candidate.is_file() or digest(candidate) != sha:
        raise SessionError(f"{label}: missing/modified file: {candidate}")
    return candidate


def _launch_ready(record: dict[str, Any], launch: dict[str, Any], plan: dict[str, Any]) -> None:
    exe = _matching_file(record.get("retail_executable"), record.get("retail_executable_sha256"), "Retail executable")
    _matching_file(record.get("prepared_map"), record.get("prepared_map_sha256"), "prepared map")
    if record["retail_executable_sha256"] != plan["executable_sha256"]:
        raise SessionError("probe executable hash disagrees with trace plan")
    if not launch.get("probe_id") or launch["probe_id"] != record.get("id"):
        raise SessionError("prepared launch belongs to a different probe")
    if (launch.get("role") != "prepared" or
            launch.get("map_sha256") != record.get("prepared_map_sha256") or
            launch.get("retail_executable_sha256") != record.get("retail_executable_sha256") or
            launch.get("control_screen_confirmed") is not True):
        raise SessionError("prepared launch lacks confirmed control/map/executable identity")
    command = launch.get("command")
    if (not isinstance(command, list) or not all(isinstance(c, str) for c in command) or
            not all(flag in command for flag in ("-loadfile", "-window", "-graphicsapi", "OpenGL2"))):
        raise SessionError("launch command lacks required Retail flags")
    win_map = launch.get("windows_map_path")
    if not isinstance(win_map, str) or not win_map or command[command.index("-loadfile") + 1:][:1] != [win_map]:
        raise SessionError("prepared launch -loadfile path is missing or mismatched")
    if Path(exe).name.casefold() not in " ".join(command).casefold():
        raise SessionError("launch command does not identify the pinned executable")
    if not isinstance(launch.get("launched_at_ns"), int) or launch["launched_at_ns"] < 1:
        raise SessionError("launch missing precise timestamp")
    jhcr = record.get("jhcr")
    if jhcr is not None:
        if not isinstance(jhcr, dict) or not isinstance(jhcr.get("state"), str) or not Path(jhcr["state"]).is_file():
            raise SessionError("JHCR state is missing: cannot claim compatible hot-reload session")
        if (not isinstance(jhcr.get("baseline_script"), str) or
                not Path(jhcr["baseline_script"]).is_file()):
            raise SessionError("JHCR baseline script is missing")


def _validate_plan(plan_dir: Path) -> dict[str, Any]:
    plan = load_json(plan_dir / "trace-plan.json")
    if plan.get("kind") != "read_only_frida_function_entry_plan":
        raise SessionError("expected a Patch 7 Frida trace plan")
    sha = plan.get("executable_sha256")
    if not isinstance(sha, str) or not _SHA.fullmatch(sha):
        raise SessionError("plan lacks exact executable hash")
    agent = plan_dir / "agent.js"
    if not agent.is_file() or agent.read_text(encoding="utf-8") != _agent_source(plan):
        raise SessionError("generated agent differs from immutable trace plan")
    return plan


def _validate_cases(raw: dict[str, Any], *, max_seconds: int) -> list[dict[str, Any]]:
    cases = raw.get("cases")
    if not isinstance(cases, list) or not cases:
        raise SessionError("cases file needs a nonempty cases array")
    if len(cases) > 64:
        raise SessionError("one session is limited to 64 cases")
    seen: set[str] = set()
    files: set[Path] = set()
    result = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise SessionError(f"case {index} is not an object")
        run_id = case.get("run_id")
        if not isinstance(run_id, str) or not _SAFE.fullmatch(run_id) or run_id in seen:
            raise SessionError(f"case {index}: invalid or duplicate run_id")
        seen.add(run_id)
        file_value = case.get("result_file")
        if not isinstance(file_value, str) or not file_value or not Path(file_value).is_absolute():
            raise SessionError(f"case {run_id}: result_file must be an absolute path")
        file_path = Path(file_value).resolve()
        if file_path in files:
            raise SessionError(f"case {run_id}: reused JASS result filename")
        files.add(file_path)
        timeout = case.get("timeout_seconds", max_seconds)
        if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= max_seconds:
            raise SessionError(f"case {run_id}: timeout_seconds must be 1..{max_seconds}")
        required = case.get("required_markers", [])
        inconclusive = case.get("inconclusive_markers", [])
        if any(not isinstance(v, list) or any(not isinstance(x, str) or not x for x in v)
               for v in (required, inconclusive)):
            raise SessionError(f"case {run_id}: invalid marker arrays")
        acceptance_semantics = case.get("acceptance_semantics")
        expected_acceptance = case.get("expected_order_accepted")
        if acceptance_semantics is not None and acceptance_semantics not in ("issue_order_return", "passive_setup"):
            raise SessionError(f"case {run_id}: invalid acceptance_semantics")
        if acceptance_semantics == "issue_order_return" and "expected_order_accepted" not in case:
            raise SessionError(f"case {run_id}: order-return semantics requires expected_order_accepted")
        if "expected_order_accepted" in case:
            if acceptance_semantics != "issue_order_return" or not isinstance(expected_acceptance, bool):
                raise SessionError(f"case {run_id}: expected_order_accepted requires issue_order_return semantics and a boolean")
            expected_marker = f"accepted={'true' if expected_acceptance else 'false'}"
            opposite_marker = f"accepted={'false' if expected_acceptance else 'true'}"
            if expected_marker not in required or opposite_marker not in inconclusive:
                raise SessionError(f"case {run_id}: acceptance markers disagree with expected_order_accepted")
        if acceptance_semantics == "passive_setup" and expected_acceptance is not None:
            raise SessionError(f"case {run_id}: passive setup cannot declare an order result")
        required_functions = case.get("required_function_rvas", [])
        if (not isinstance(required_functions, list) or
                any(not isinstance(rva, str) or not re.fullmatch(r"0x[0-9a-fA-F]{8}", rva)
                    for rva in required_functions) or
                len(set(rva.lower() for rva in required_functions)) != len(required_functions)):
            raise SessionError(f"case {run_id}: required_function_rvas must be unique eight-digit RVAs")
        result.append({"run_id": run_id, "result_file": str(file_path),
                       "timeout_seconds": timeout,
                       "required_markers": required, "inconclusive_markers": inconclusive,
                       **({"acceptance_semantics": acceptance_semantics} if acceptance_semantics else {}),
                       **({"expected_order_accepted": expected_acceptance} if expected_acceptance is not None else {}),
                       **({"required_function_rvas": required_functions} if required_functions else {})})
    return result


def create(*, plan_dir: Path, probe_dir: Path, cases_file: Path, output_dir: Path) -> dict[str, Any]:
    """Validate exact artifacts and create an immutable session manifest, offline."""
    if output_dir.exists():
        raise SessionError(f"session output path already exists: {output_dir}")
    plan = _validate_plan(plan_dir)
    probe = load_json(probe_dir / "probe.json")
    launch = load_json(probe_dir / "launch.json")
    _launch_ready(probe, launch, plan)
    cases = _validate_cases(load_json(cases_file), max_seconds=plan["limits"]["seconds"])
    selected_rvas = {row["rva"].lower() for row in plan["selected_hooks"]}
    for case in cases:
        missing = sorted(set(rva.lower() for rva in case.get("required_function_rvas", [])) - selected_rvas)
        if missing:
            raise SessionError(f"{case['run_id']}: required function RVAs are absent from trace plan: " + ", ".join(missing))
    # Preserve originals without turning session creation into a process launch.
    payload = {"schema_version": 1, "kind": "retail_ability_live_session",
               "rawcode": plan["rawcode"], "executable_sha256": plan["executable_sha256"],
               "plan_dir": str(plan_dir.resolve()), "plan_sha256": digest(plan_dir / "trace-plan.json"),
               "agent_sha256": digest(plan_dir / "agent.js"),
               "probe_dir": str(probe_dir.resolve()), "probe_sha256": digest(probe_dir / "probe.json"),
               "launch_sha256": digest(probe_dir / "launch.json"),
               "launch_time_ns": launch["launched_at_ns"],
               "prepared_map_sha256": probe["prepared_map_sha256"],
               "jhcr_prepared": isinstance(probe.get("jhcr"), dict),
               "cases": cases,
               "evidence_boundary": "JASS marker readiness and native calls are not gameplay parity proofs"}
    output_dir.mkdir(parents=True)
    save_json(output_dir / "session.json", payload)
    return payload


def inspect_session(directory: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    saved = load_json(directory / "session.json")
    if saved.get("schema_version") != 1 or saved.get("kind") != "retail_ability_live_session":
        raise SessionError("unsupported session manifest")
    plan_dir = Path(saved["plan_dir"])
    probe_dir = Path(saved["probe_dir"])
    for path, key in ((plan_dir / "trace-plan.json", "plan_sha256"),
                      (plan_dir / "agent.js", "agent_sha256"),
                      (probe_dir / "probe.json", "probe_sha256"),
                      (probe_dir / "launch.json", "launch_sha256")):
        _matching_file(str(path), saved[key], key)
    plan = _validate_plan(plan_dir)
    probe, launch = load_json(probe_dir / "probe.json"), load_json(probe_dir / "launch.json")
    _launch_ready(probe, launch, plan)
    if (saved["rawcode"] != plan["rawcode"] or saved["executable_sha256"] != plan["executable_sha256"] or
            saved["launch_time_ns"] != launch["launched_at_ns"] or
            saved["prepared_map_sha256"] != probe["prepared_map_sha256"] or
            saved["jhcr_prepared"] != isinstance(probe.get("jhcr"), dict)):
        raise SessionError("session provenance differs from live probe/plan")
    if _validate_cases({"cases": saved["cases"]}, max_seconds=plan["limits"]["seconds"]) != saved["cases"]:
        raise SessionError("invalid session case serialization")
    selected_rvas = {row["rva"].lower() for row in plan["selected_hooks"]}
    if any(set(rva.lower() for rva in case.get("required_function_rvas", [])) - selected_rvas
           for case in saved["cases"]):
        raise SessionError("session requires function RVAs absent from its immutable trace plan")
    return saved, plan, launch


def _host_process(launch: dict[str, Any], proc_root: Path = Path("/proc")) -> int:
    """Accept only a unique Linux Wine host whose command matches prepared launch."""
    expected_map = launch["windows_map_path"].casefold()
    expected_prefix = launch.get("wine_prefix")
    matches = []
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            args = [x.decode("utf-8", errors="replace") for x in
                    (entry / "cmdline").read_bytes().split(b"\0") if x]
            env = dict(x.split(b"=", 1) for x in (entry / "environ").read_bytes().split(b"\0") if b"=" in x)
        except (PermissionError, FileNotFoundError, ProcessLookupError, OSError):
            continue
        if not args or not any("warcraft iii.exe" in x.casefold() for x in args[:2]):
            continue
        if "-loadfile" not in args or args.index("-loadfile") + 1 >= len(args):
            continue
        if args[args.index("-loadfile") + 1].casefold() != expected_map:
            continue
        actual_prefix = env.get(b"WINEPREFIX")
        # If the record has an explicit prefix, it must agree with the live host.
        if expected_prefix and (actual_prefix is None or
                                os.path.realpath(os.fsdecode(actual_prefix)) != os.path.realpath(expected_prefix)):
            continue
        matches.append(int(entry.name))
    if len(matches) != 1:
        raise SessionError(f"expected one matching active Wine Retail process, found {len(matches)}")
    return matches[0]


def _same_prefix_server(proc_root: Path, *, host_pid: int, remote: str) -> bool:
    """Check the local Wine Frida server belongs to the same Wine prefix.

    Wine's Windows PID can differ from Linux's host PID. Never treat a merely
    unique remote process as sufficient to bridge those namespaces.
    """
    if not remote.startswith(("127.0.0.1:", "localhost:")):
        return False
    try:
        game_env = dict(x.split(b"=", 1) for x in
                        (proc_root / str(host_pid) / "environ").read_bytes().split(b"\0") if b"=" in x)
    except OSError:
        return False

    def prefix(env: dict[bytes, bytes]) -> str:
        explicit = env.get(b"WINEPREFIX")
        if explicit:
            return os.path.realpath(os.fsdecode(explicit))
        return os.path.realpath(os.path.join(os.fsdecode(env.get(b"HOME", b"")), ".wine"))

    expected = prefix(game_env)
    servers = 0
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            args = [x.decode(errors="replace") for x in
                    (entry / "cmdline").read_bytes().split(b"\0") if x]
            if not args or not any("frida-server.exe" in x.casefold() for x in args[:2]):
                continue
            env = dict(x.split(b"=", 1) for x in
                       (entry / "environ").read_bytes().split(b"\0") if b"=" in x)
        except OSError:
            continue
        if prefix(env) == expected:
            servers += 1
    return servers == 1


def select_frida_process(device: Any, host_pid: int, *, proc_root: Path = Path("/proc"),
                         remote: str = "127.0.0.1:27043") -> tuple[int, str]:
    """Require a unique Retail target and independently grounded process identity."""
    matches = [p for p in device.enumerate_processes()
               if p.name.casefold() == "warcraft iii.exe"]
    if len(matches) != 1:
        raise SessionError("expected exactly one named Warcraft III.exe process on the Frida server")
    frida_pid = matches[0].pid
    if frida_pid == host_pid:
        return frida_pid, "matching_host_and_frida_pid"
    if not _same_prefix_server(proc_root, host_pid=host_pid, remote=remote):
        raise SessionError("different Wine/Frida PIDs without a uniquely verified local same-prefix Frida server")
    return frida_pid, "unique_game_and_same_prefix_server_distinct_pid"


def _disarmed_agent(plan_dir: Path) -> tuple[str, str]:
    """Use the immutable generated agent, but prevent events before first case."""
    source = (plan_dir / "agent.js").read_text(encoding="utf-8")
    needle = "let armed = true;"
    if source.count(needle) != 1:
        raise SessionError("unsupported generated agent: missing one initial arm declaration")
    adapted = source.replace(needle, "let armed = false;", 1)
    return adapted, hashlib.sha256(adapted.encode("utf-8")).hexdigest()


def _fresh_capture(path: Path, baseline: tuple[int, str] | None,
                   start_ns: int, case: dict[str, Any]) -> tuple[str | None, bytes | None]:
    if not path.is_file():
        return None, None
    stat = path.stat()
    if stat.st_size == 0 or stat.st_mtime_ns <= start_ns:
        return None, None
    current = digest(path)
    if baseline is not None and current == baseline[1] and stat.st_mtime_ns == baseline[0]:
        return None, None
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    messages = [re.sub(r'\\(["\\])', r'\1', item) for item in _PRELOAD.findall(text)]
    run_id = case["run_id"]
    start_marker, done_marker = f"SESSION_START run_id={run_id}", f"SESSION_DONE run_id={run_id}"
    starts = [i for i, item in enumerate(messages) if item.startswith("SESSION_START ")]
    dones = [i for i, item in enumerate(messages) if item.startswith("SESSION_DONE ")]
    if not dones:
        # PreloadGen output may still be in progress; keep polling for completion.
        return None, None
    if not starts:
        return "inconclusive", raw
    if (starts != [messages.index(start_marker)] if start_marker in messages else True) or \
            (dones != [messages.index(done_marker)] if done_marker in messages else True):
        return "inconclusive", raw
    if messages.index(start_marker) >= messages.index(done_marker):
        return "inconclusive", raw
    if any(item not in (start_marker, done_marker) and
           (item.startswith("SESSION_START ") or item.startswith("SESSION_DONE ")) for item in messages):
        return "inconclusive", raw
    segment = messages[messages.index(start_marker) + 1:messages.index(done_marker)]
    if segment.count("setup_failed=false") != 1 or "setup_failed=true" in segment:
        return "inconclusive", raw
    acceptance = [item for item in segment if item in ("accepted=true", "accepted=false")]
    if len(acceptance) != 1:
        return "inconclusive", raw
    if "buffer_overflow=true" in segment or "observation_truncated=true" in segment:
        return "inconclusive", raw
    if case.get("acceptance_semantics") == "issue_order_return" and "expected_order_accepted" in case:
        observed = acceptance[0] == "accepted=true"
        if observed != case["expected_order_accepted"]:
            return "failed", raw
    for marker in case["required_markers"]:
        if marker not in segment:
            return "inconclusive", raw
    if any(marker in segment for marker in case["inconclusive_markers"]):
        return "inconclusive", raw
    if acceptance[0] == "accepted=false" and "expected_order_accepted" not in case:
        # Legacy manifests did not declare whether rejection was expected.
        return "inconclusive", raw
    if case.get("acceptance_semantics") == "passive_setup" and acceptance[0] != "accepted=true":
        return "inconclusive", raw
    return "ready_for_review", raw


def _get_device(remote: str) -> Any:
    try:
        import frida  # optional, only needed by the live command
    except ImportError as error:
        raise SessionError("install the matching Frida Python client for live capture") from error
    # Remote Wine frida-server; do not spawn or launch processes.
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", remote):
        raise SessionError("invalid Frida server endpoint")
    get_manager = getattr(frida, "get_device_manager", None)
    if not callable(get_manager):
        raise SessionError(
            "the selected Python cannot import the Frida client API (the tools/frida "
            "directory may be shadowing an uninstalled client); rerun this command "
            "with the matching Frida Python environment")
    return get_manager().add_remote_device(remote)


def _capture_case(script_session: Any, *, plan_dir: Path, plan: dict[str, Any],
                  case: dict[str, Any], outdir: Path, poll_seconds: float,
                  identity: dict[str, Any] | None = None) -> dict[str, Any]:
    """Load a fresh bounded agent for one case, recording immutable provenance."""
    outdir.mkdir()
    trace_path = outdir / "trace.jsonl"
    run_id = case["run_id"]
    result_file = Path(case["result_file"])
    before = (result_file.stat().st_mtime_ns, digest(result_file)) if result_file.is_file() else None
    modified_js, actual_sha = _disarmed_agent(plan_dir)
    expected_sha = digest(plan_dir / "agent.js")
    start_ns = time.time_ns()
    status = "timeout"
    jass_status = "missing"
    raw = None
    errors: list[str] = []
    script = script_session.create_script(modified_js)
    with trace_path.open("x", encoding="utf-8") as log:
        write_lock = Lock()
        def line(record: dict[str, Any]) -> None:
            with write_lock:
                log.write(json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n")
                log.flush()

        line({"event": "trace-metadata", "retail_sha256": plan["executable_sha256"],
              "agent_sha256": expected_sha, "session_agent_sha256": actual_sha,
              "session_agent_initially_disarmed": True,
              "agent_required_retail_sha256": plan["executable_sha256"],
              "run_id": run_id, "session_identity": identity or {}})

        def on_message(message: dict[str, Any], data: bytes | None) -> None:
            if message.get("type") == "send":
                line({"event": "frida-message", "payload": message.get("payload"), "run_id": run_id})
            else:
                reason = str(message.get("description") or message)
                errors.append(reason)
                line({"event": "frida-error", "reason": reason, "run_id": run_id})

        script.on("message", on_message)
        try:
            script.load()
            rpc = script.exports_sync
            if rpc.status().get("armed"):
                raise SessionError("Frida agent was armed before case initialization")
            if rpc.setrunid(run_id) is not True:
                raise SessionError("cannot set Frida run ID")
            # Capture the freshness threshold immediately before arming.
            start_ns = time.time_ns()
            if rpc.arm() is not True:
                raise SessionError("cannot arm bounded Frida agent")
            print(f"  Armed {run_id}; activate its already-prepared JASS scenario in Retail.", flush=True)
            deadline = time.monotonic() + case["timeout_seconds"]
            while time.monotonic() < deadline:
                if errors:
                    status = "error"
                    break
                found, candidate = _fresh_capture(result_file, before, start_ns, case)
                if found:
                    status, jass_status, raw = found, found, candidate
                    break
                current = rpc.status()
                if current.get("stopped"):
                    status = "inconclusive"
                    break
                time.sleep(min(poll_seconds, max(0.0, deadline - time.monotonic())))
        except Exception as error:
            errors.append(str(error))
            status = "error"
        finally:
            try:
                script.exports_sync.disarm()
            except Exception as error:
                errors.append(f"disarm: {error}")
                status = "error"
            try:
                script.unload()
            except Exception as error:
                errors.append(f"unload: {error}")
                status = "error"
            line({"event": "trace-end", "run_id": run_id, "errors": errors,
                  "result_status": status, "agent_sha256": actual_sha})
    if raw is not None:
        (outdir / "result.txt").write_bytes(raw)
    review = summarize_trace(plan_dir, trace_path)
    # Fail closed if the native agent truncated or the case did not finish.
    unexpected_runs = sorted(set(review["event_counts_by_run_id"]) - {run_id})
    if unexpected_runs:
        errors.append("native events from different run IDs: " + ", ".join(unexpected_runs))
        status = "error"
    if status == "ready_for_review" and review["status"] != "bounded_native_trace":
        status = "inconclusive"
    function_calls = review.get("function_calls_by_run_id", {}).get(run_id, {})
    missing_functions = [rva.lower() for rva in case.get("required_function_rvas", [])
                         if not function_calls.get(rva.lower())]
    if status == "ready_for_review" and missing_functions:
        status = "inconclusive"
    messages = [re.sub(r'\\(["\\])', r'\1', item) for item in _PRELOAD.findall(
        raw.decode("utf-8", errors="replace") if raw is not None else "")]
    accepted_values = [item for item in messages if item in ("accepted=true", "accepted=false")]
    observed_order_accepted = (accepted_values[0] == "accepted=true" if len(accepted_values) == 1 else None)
    outcome = ("expected_order_mismatch" if status == "failed" else
               "expected_order_outcome_observed" if status == "ready_for_review" and
               "expected_order_accepted" in case else
               "capture_ready" if status == "ready_for_review" else "incomplete")
    report = {"schema_version": 1, "run_id": run_id, "status": status,
              "jass_result_fresh": raw is not None,
              "jass_result_status": jass_status,
              "native_trace_status": review["status"], "native_counts_by_run_id": review["event_counts_by_run_id"],
              "native_function_calls_by_run_id": review.get("function_calls_by_run_id", {}),
              "missing_required_function_rvas": missing_functions,
              "acceptance_semantics": case.get("acceptance_semantics"),
              "expected_order_accepted": case.get("expected_order_accepted"),
              "observed_order_accepted": observed_order_accepted,
              "case_outcome": outcome,
              "trace_sha256": digest(trace_path),
              "jass_result_sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None,
              "host_errors": errors, "note": "Capture readiness is not gameplay parity proof"}
    save_json(outdir / "review.json", report)
    return report


def run(directory: Path, *, remote: str = "127.0.0.1:27043", poll_seconds: float = 0.1,
        proc_root: Path = Path("/proc"), device: Any | None = None) -> dict[str, Any]:
    """Reuse one already-loaded Retail process for all pending cases."""
    if not 0 < poll_seconds <= 5:
        raise SessionError("poll_seconds must be within (0, 5]")
    saved, plan, launch = inspect_session(directory)
    if (directory / "run-summary.json").exists():
        raise SessionError("session already has a run summary; create a new session instead")
    plan_dir = Path(saved["plan_dir"])
    with (directory / "run.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise SessionError("session runner already active") from error
        host_pid = _host_process(launch, proc_root)
        endpoint = device if device is not None else _get_device(remote)
        target_pid, mapping = select_frida_process(endpoint, host_pid, proc_root=proc_root, remote=remote)
        # Attach once; each case reloads its bounded script to reset event budgets.
        attached = endpoint.attach(target_pid)
        summaries = []
        try:
            for case in saved["cases"]:
                outdir = directory / case["run_id"]
                if outdir.exists():
                    raise SessionError(f"case already has an output directory (no overwrite): {outdir}")
                summaries.append(_capture_case(attached, plan_dir=plan_dir, plan=plan,
                                               case=case, outdir=outdir, poll_seconds=poll_seconds,
                                               identity={"host_pid": host_pid, "frida_pid": target_pid,
                                                         "process_identity_mapping": mapping,
                                                         "prepared_map_sha256": saved["prepared_map_sha256"],
                                                         "probe_sha256": saved["probe_sha256"],
                                                         "launch_sha256": saved["launch_sha256"]}))
                print(f"  {case['run_id']}: {summaries[-1]['status']}", flush=True)
                if summaries[-1]["status"] in ("error", "timeout", "inconclusive", "failed"):
                    break  # no false successful run progression
        finally:
            attached.detach()
    result = {"schema_version": 1, "rawcode": saved["rawcode"], "host_pid": host_pid,
              "frida_pid": target_pid, "process_identity_mapping": mapping,
              "session_cases_completed": len(summaries),
              "cases": summaries, "status": ("failed" if any(row["status"] == "failed" for row in summaries) else
              "ready_for_review" if len(summaries) == len(saved["cases"]) and
              all(row["status"] == "ready_for_review" for row in summaries) else "inconclusive"),
              "note": "Capture readiness is not semantic correctness"}
    save_json(directory / "run-summary.json", result)
    return result
