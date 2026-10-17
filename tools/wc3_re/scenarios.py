"""Generate bounded, user-triggered JASS ability experiments for Patch 8 sessions.

No Retail/JASS process is launched. Outputs are intentionally map-agnostic JASS
fragments plus a compatible Patch 8 session case manifest. No ability behavior
is inferred from the requested scenario category.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import re
from typing import Any

from wc3_re.session import _validate_cases


class ScenarioError(ValueError):
    """An unsafe, ambiguous, or unsupported Retail scenario specification."""


FOURCC = re.compile(r"[A-Za-z0-9]{4}\Z")
RUN_ID = re.compile(r"[A-Za-z0-9_.-]{1,80}\Z")
SUPPORTED = {"passive", "target", "point", "immediate", "area", "projectile", "buff"}
MAX_CASES = 32
MAX_TARGETS = 8
MAX_TICKS = 120
MAX_LOG_LINES = 1400


def _fourcc(value: Any, name: str) -> str:
    if not isinstance(value, str) or not FOURCC.fullmatch(value):
        raise ScenarioError(f"{name} must be an ASCII alphanumeric four-character rawcode")
    return value


def _number(value: Any, name: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ScenarioError(f"{name} must be finite, between {low:g} and {high:g}")
    return float(value)


def _integer(value: Any, name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ScenarioError(f"{name} must be an integer from {low} to {high}")
    return value


def _unit(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ScenarioError(f"{name} must be an object")
    unexpected = set(value) - {"unit_id", "player", "x", "y", "facing", "life", "mana", "move_speed"}
    if unexpected:
        raise ScenarioError(f"{name}: unsupported unit fields: " + ", ".join(sorted(unexpected)))
    row = {"unit_id": _fourcc(value.get("unit_id"), f"{name}.unit_id"),
           "player": _integer(value.get("player"), f"{name}.player", 0, 15),
           "x": _number(value.get("x"), f"{name}.x", -32000, 32000),
           "y": _number(value.get("y"), f"{name}.y", -32000, 32000),
           "facing": _number(value.get("facing", 0), f"{name}.facing", -360, 360)}
    for key in ("life", "mana", "move_speed"):
        if key in value:
            # May be clamped by the engine; not a guarantee of final runtime state.
            row[key] = _number(value[key], f"{name}.{key}", 0, 100000)
    return row


def _map_config(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ScenarioError("map must be an object")
    required = ("archive", "member", "retail_executable", "hook_function", "hook_anchor")
    unexpected = set(value) - set(required) - {"hook_where", "edition"}
    if unexpected:
        raise ScenarioError("map: unsupported fields: " + ", ".join(sorted(unexpected)))
    if value.get("edition", "tft") not in ("roc", "tft"):
        raise ScenarioError("map.edition must be roc or tft")
    if any(not isinstance(value.get(k), str) or not value[k].strip() for k in required):
        raise ScenarioError("map needs archive, member, retail_executable, hook_function, hook_anchor")
    if not Path(value["archive"]).is_absolute() or not Path(value["retail_executable"]).is_absolute():
        raise ScenarioError("map.archive and map.retail_executable must be absolute paths")
    if not re.fullmatch(r"[A-Za-z_]\w*", value["hook_function"]):
        raise ScenarioError("map.hook_function must be a JASS function identifier")
    if '\n' in value["hook_anchor"] or '\r' in value["hook_anchor"]:
        raise ScenarioError("map.hook_anchor must be one whole JASS line")
    if value.get("hook_where", "after") not in ("before", "after"):
        raise ScenarioError("map.hook_where must be before or after")
    return {**{key: value[key] for key in required}, "hook_where": value.get("hook_where", "after"),
            "edition": value.get("edition", "tft")}


def validate(source: dict[str, Any]) -> dict[str, Any]:
    """Return a normalized, bounded scenario plan; fail closed on unknown directives."""
    if not isinstance(source, dict) or source.get("schema_version") != 1:
        raise ScenarioError("expected schema_version=1 scenario object")
    allowed_root = {"schema_version", "rawcode", "result_dir", "chat_player", "cases", "map"}
    if set(source) - allowed_root:
        raise ScenarioError("unsupported top-level keys: " + ", ".join(sorted(set(source) - allowed_root)))
    rawcode = _fourcc(source.get("rawcode"), "rawcode")
    dest = source.get("result_dir")
    if not isinstance(dest, str) or not Path(dest).is_absolute():
        raise ScenarioError("result_dir must be an absolute path to the active Wine CustomMapData directory")
    dest_path = Path(dest).expanduser().resolve()
    chat_player = _integer(source.get("chat_player", 0), "chat_player", 0, 15)
    cases = source.get("cases")
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        raise ScenarioError(f"cases must contain 1..{MAX_CASES} experiments")
    normalized = []
    seen: set[str] = set()
    for n, case in enumerate(cases):
        where = f"cases[{n}]"
        if not isinstance(case, dict):
            raise ScenarioError(f"{where} must be an object")
        allowed = {"run_id", "kind", "caster", "targets", "ability_level", "learn_mode", "hero_level",
                   "order", "expected_order_accepted", "point", "duration_seconds",
                   "sample_interval_seconds", "buff_ids", "timeout_seconds"}
        if set(case) - allowed:
            raise ScenarioError(f"{where}: unsupported keys " + ", ".join(sorted(set(case) - allowed)))
        run_id = case.get("run_id")
        if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id) or run_id in seen:
            raise ScenarioError(f"{where}.run_id must be unique and safe")
        seen.add(run_id)
        kind = case.get("kind")
        if kind not in SUPPORTED:
            raise ScenarioError(f"{where}.kind must be one of {sorted(SUPPORTED)}")
        caster = _unit(case.get("caster"), f"{where}.caster")
        targets = case.get("targets", [])
        if not isinstance(targets, list) or len(targets) > MAX_TARGETS:
            raise ScenarioError(f"{where}.targets must contain at most {MAX_TARGETS} units")
        targets = [_unit(unit, f"{where}.targets[{i}]") for i, unit in enumerate(targets)]
        if kind in ("target", "projectile", "buff") and not targets:
            raise ScenarioError(f"{where}: targeted scenario requires a target")
        order = case.get("order")
        expected_order_accepted = case.get("expected_order_accepted", True)
        if not isinstance(expected_order_accepted, bool):
            raise ScenarioError(f"{where}.expected_order_accepted must be a boolean")
        if kind == "passive":
            if order is not None:
                raise ScenarioError(f"{where}: passive scenarios must not issue an order")
            if "expected_order_accepted" in case:
                raise ScenarioError(f"{where}: expected_order_accepted only applies to ordered scenarios")
        elif not isinstance(order, str) or not re.fullmatch(r"[a-z][a-z0-9]{0,31}", order):
            raise ScenarioError(f"{where}: explicit lower-case order is required; cannot infer from rawcode")
        point = None
        if kind in ("point", "area"):
            if not isinstance(case.get("point"), dict):
                raise ScenarioError(f"{where}: point/area scenario requires point {{x,y}}")
            if set(case["point"]) != {"x", "y"}:
                raise ScenarioError(f"{where}.point must contain only x and y")
            point = {coord: _number(case["point"][coord], f"{where}.point.{coord}", -32000, 32000)
                     for coord in ("x", "y")}
        elif "point" in case:
            raise ScenarioError(f"{where}: point is only valid for point/area")
        level = _integer(case.get("ability_level", 1), f"{where}.ability_level", 1, 20)
        learn_mode = case.get("learn_mode", "unit_add")
        if learn_mode not in ("unit_add", "hero_skill"):
            raise ScenarioError(f"{where}: learn_mode must be unit_add or hero_skill")
        hero_level = None
        if learn_mode == "hero_skill":
            hero_level = _integer(case.get("hero_level"), f"{where}.hero_level", 1, 100)
        elif "hero_level" in case:
            raise ScenarioError(f"{where}: hero_level requires hero_skill learning")
        duration = _number(case.get("duration_seconds", 3.0), f"{where}.duration_seconds", 0.05, 60)
        interval = _number(case.get("sample_interval_seconds", 0.25), f"{where}.sample_interval_seconds", 0.05, 10)
        ticks = math.ceil((duration - 1e-9) / interval)
        if ticks > MAX_TICKS:
            raise ScenarioError(f"{where}: {ticks} ticks exceed max {MAX_TICKS}; increase interval")
        buffs = case.get("buff_ids", [])
        if not isinstance(buffs, list) or len(buffs) > 8:
            raise ScenarioError(f"{where}: buff_ids supports up to eight entries")
        buffs = [_fourcc(b, f"{where}.buff_ids") for b in buffs]
        if len(buffs) != len(set(buffs)):
            raise ScenarioError(f"{where}: duplicate buff identifiers")
        # Record one snapshot per unit at t=0 and each timer step; headroom for setup.
        if (ticks + 1) * (len(targets) + 1 + len(targets) * len(buffs)) + 16 > MAX_LOG_LINES:
            raise ScenarioError(f"{where}: observation buffer limit exceeded")
        timeout = _integer(case.get("timeout_seconds", min(60, math.ceil(duration) + 15)),
                           f"{where}.timeout_seconds", 1, 360)
        normalized.append({"run_id": run_id, "kind": kind, "caster": caster, "targets": targets,
                           "ability_level": level, "learn_mode": learn_mode, "hero_level": hero_level,
                           "order": order, "expected_order_accepted": expected_order_accepted,
                           "point": point, "duration_seconds": duration,
                           "sample_interval_seconds": interval, "ticks": ticks,
                           "buff_ids": buffs, "timeout_seconds": timeout,
                           "result_file": str(dest_path / (run_id + ".txt")),
                           "chat_command": "-re " + run_id})
    result = {"schema_version": 1, "rawcode": rawcode, "result_dir": str(dest_path),
              "chat_player": chat_player, "cases": normalized,
              "evidence_boundary": "authored scenarios only; order return and JASS samples do not establish exact native semantics"}
    if "map" in source:
        result["map"] = _map_config(source["map"])
    return result


def _real(x: float) -> str:
    return f"{x:.6f}"


def _spawn(unit: dict[str, Any], dest: str) -> list[str]:
    lines = [f"    set {dest} = CreateUnit(Player({unit['player']}), '{unit['unit_id']}', {_real(unit['x'])}, {_real(unit['y'])}, {_real(unit['facing'])})"]
    for field, state in (("life", "UNIT_STATE_LIFE"), ("mana", "UNIT_STATE_MANA")):
        if field in unit:
            lines.append(f"    call SetUnitState({dest}, {state}, {_real(unit[field])})")
    if "move_speed" in unit:
        lines.append(f"    call SetUnitMoveSpeed({dest}, {_real(unit['move_speed'])})")
    return lines


def _join(parts: list[str]) -> str:
    return "\n".join(parts) + "\n"


def _render_fragments(plan: dict[str, Any]) -> tuple[str, str]:
    globals_text = _join([
        "    timer RE_Timer = null", "    trigger RE_SpellTrigger = null", "    unit RE_Caster = null", "    unit array RE_Target",
        "    integer RE_TargetCount = 0", "    integer RE_LogCount = 0", "    string array RE_Log",
        "    boolean RE_Busy = false", "    boolean RE_Overflow = false",
        "    integer RE_SampleIndex = 0", "    integer RE_MaxSamples = 0",
        "    real RE_Interval = 0.0", "    real RE_Elapsed = 0.0",
        "    boolean RE_SetupOk = false", "    boolean RE_OrderAccepted = false",
        "    string RE_RunId = \"\"",
    ])
    lines = [
        "// Generated Warcraft III ability laboratory. Do not edit active timer callbacks with JHCR.",
        "function RE_LogLine takes string line returns nothing",
        f"    if RE_LogCount < {MAX_LOG_LINES} then",
        "        set RE_Log[RE_LogCount] = line",
        "        set RE_LogCount = RE_LogCount + 1",
        "    else",
        "        set RE_Overflow = true",
        "    endif",
        "endfunction",
        "",
        "function RE_Record takes nothing returns nothing",
        "    local integer i = 0",
        "    if RE_Caster != null then",
        '        call RE_LogLine("OBS role=caster tick=" + I2S(RE_SampleIndex) + " time=" + R2S(RE_Elapsed) + " life=" + R2S(GetUnitState(RE_Caster, UNIT_STATE_LIFE)) + " mana=" + R2S(GetUnitState(RE_Caster, UNIT_STATE_MANA)) + " x=" + R2S(GetUnitX(RE_Caster)) + " y=" + R2S(GetUnitY(RE_Caster)) + " speed=" + R2S(GetUnitMoveSpeed(RE_Caster)) + " order=" + I2S(GetUnitCurrentOrder(RE_Caster)))',
        "    endif",
        "    loop",
        "        exitwhen i >= RE_TargetCount",
        "        if RE_Target[i] != null then",
        '            call RE_LogLine("OBS role=target index=" + I2S(i) + " tick=" + I2S(RE_SampleIndex) + " time=" + R2S(RE_Elapsed) + " life=" + R2S(GetUnitState(RE_Target[i], UNIT_STATE_LIFE)) + " mana=" + R2S(GetUnitState(RE_Target[i], UNIT_STATE_MANA)) + " x=" + R2S(GetUnitX(RE_Target[i])) + " y=" + R2S(GetUnitY(RE_Target[i])) + " speed=" + R2S(GetUnitMoveSpeed(RE_Target[i])) + " owner=" + I2S(GetPlayerId(GetOwningPlayer(RE_Target[i]))))',
        "        endif",
        "        set i = i + 1",
        "    endloop",
    ]
    for case in plan["cases"]:
        if not case["buff_ids"] or not case["targets"]:
            continue
        lines += [f'    if RE_RunId == "{case["run_id"]}" then']
        for target_index, _ in enumerate(case["targets"]):
            for buff in case["buff_ids"]:
                lines += [f'        call RE_LogLine("BUFF target={target_index} rawcode={buff} tick=" + I2S(RE_SampleIndex) + " level=" + I2S(GetUnitAbilityLevel(RE_Target[{target_index}], \'{buff}\')))']
        lines += ["    endif"]
    lines += ["endfunction", "",
        "function RE_OnSpell takes nothing returns nothing",
        "    if not RE_Busy or GetTriggerUnit() != RE_Caster then",
        "        return",
        "    endif",
        "    if GetTriggerEventId() == EVENT_UNIT_SPELL_CAST then",
        '        call RE_LogLine("SPELL stage=cast rawcode_int=" + I2S(GetSpellAbilityId()) + " sample_tick=" + I2S(RE_SampleIndex))',
        "    elseif GetTriggerEventId() == EVENT_UNIT_SPELL_EFFECT then",
        '        call RE_LogLine("SPELL stage=effect rawcode_int=" + I2S(GetSpellAbilityId()) + " sample_tick=" + I2S(RE_SampleIndex))',
        "    elseif GetTriggerEventId() == EVENT_UNIT_SPELL_FINISH then",
        '        call RE_LogLine("SPELL stage=finish rawcode_int=" + I2S(GetSpellAbilityId()) + " sample_tick=" + I2S(RE_SampleIndex))',
        "    elseif GetTriggerEventId() == EVENT_UNIT_SPELL_ENDCAST then",
        '        call RE_LogLine("SPELL stage=endcast rawcode_int=" + I2S(GetSpellAbilityId()) + " sample_tick=" + I2S(RE_SampleIndex))',
        "    endif",
        "endfunction", "",
        "function RE_Reset takes nothing returns nothing",
        "    local integer i = 0",
        "    if RE_Timer != null then",
        "        call PauseTimer(RE_Timer)",
        "    endif",
        "    if RE_SpellTrigger != null then",
        "        call DestroyTrigger(RE_SpellTrigger)",
        "        set RE_SpellTrigger = null",
        "    endif",
        "    if RE_Caster != null then",
        "        call RemoveUnit(RE_Caster)",
        "        set RE_Caster = null",
        "    endif",
        "    loop",
        "        exitwhen i >= RE_TargetCount",
        "        if RE_Target[i] != null then",
        "            call RemoveUnit(RE_Target[i])",
        "            set RE_Target[i] = null",
        "        endif",
        "        set i = i + 1",
        "    endloop",
        "    set RE_TargetCount = 0",
        "    set RE_LogCount = 0",
        "    set RE_Overflow = false",
        "    set RE_SampleIndex = 0",
        "    set RE_Elapsed = 0.0",
        "    set RE_OrderAccepted = false",
        "    set RE_SetupOk = false",
        "endfunction",
        "",
    ]
    lines += [
        "function RE_Emit takes nothing returns nothing",
        "    local integer i = 0",
        "    call PreloadGenClear()",
        "    call PreloadGenStart()",
        '    call Preload("SESSION_START run_id=" + RE_RunId)',
        f'    call Preload("ability={plan["rawcode"]} mode=generated_lab")',
        "    if RE_SetupOk then",
        '        call Preload("setup_failed=false")',
        "    else",
        '        call Preload("setup_failed=true")',
        "    endif",
        "    if RE_OrderAccepted then",
        '        call Preload("accepted=true")',
        "    else",
        '        call Preload("accepted=false")',
        "    endif",
        "    if RE_Overflow then",
        '        call Preload("buffer_overflow=true")',
        "    endif",
        "    loop",
        "        exitwhen i >= RE_LogCount",
        "        call Preload(RE_Log[i])",
        "        set RE_Log[i] = null",
        "        set i = i + 1",
        "    endloop",
        '    call Preload("SESSION_DONE run_id=" + RE_RunId)',
        "    // Dynamic filename is deliberately avoided; each case calls a literal PreloadGenEnd.",
        "endfunction",
        "",
    ]
    # A case-specific finish branch keeps PreloadGenEnd literals available to the
    # existing strict map preparation validator; no dynamic filename guessing.
    lines += ["function RE_Finish takes nothing returns nothing", "    call RE_Emit()"]
    for index, case in enumerate(plan["cases"]):
        prefix = "if" if index == 0 else "elseif"
        lines += [f"    {prefix} RE_RunId == \"{case['run_id']}\" then",
                  f'        call PreloadGenEnd("{case["run_id"]}.txt")']
    lines += ["    endif", "    set RE_Busy = false", "endfunction", "",
              "function RE_Tick takes nothing returns nothing",
              "    set RE_SampleIndex = RE_SampleIndex + 1",
              "    set RE_Elapsed = I2R(RE_SampleIndex) * RE_Interval",
              "    call RE_Record()",
              "    if RE_SampleIndex >= RE_MaxSamples then",
              "        call PauseTimer(RE_Timer)",
              "        call RE_Finish()",
              "    endif",
              "endfunction", ""]

    for index, case in enumerate(plan["cases"]):
        lines += [f"function RE_Start_{index} takes nothing returns nothing",
                  "    if RE_Busy then", "        return", "    endif",
                  "    set RE_Busy = true", "    call RE_Reset()",
                  f'    set RE_RunId = "{case["run_id"]}"',
                  f'    set RE_MaxSamples = {case["ticks"]}',
                  f'    set RE_Interval = {_real(case["sample_interval_seconds"])}']
        lines += _spawn(case["caster"], "RE_Caster")
        for target_index, target in enumerate(case["targets"]):
            lines += _spawn(target, f"RE_Target[{target_index}]")
        lines += [f'    set RE_TargetCount = {len(case["targets"])}',
                  "    set RE_SetupOk = RE_Caster != null"]
        for target_index in range(len(case["targets"])):
            lines += [f"    set RE_SetupOk = RE_SetupOk and RE_Target[{target_index}] != null"]
        lines += ["    if not RE_SetupOk then", "        call RE_Finish()", "        return", "    endif"]
        if case["learn_mode"] == "hero_skill":
            lines += [f'    call SetHeroLevel(RE_Caster, {case["hero_level"]}, false)']
            lines += [f'    call SelectHeroSkill(RE_Caster, \'{plan["rawcode"]}\')' for _ in range(case["ability_level"])]
        else:
            lines += [f'    call UnitAddAbility(RE_Caster, \'{plan["rawcode"]}\')']
            if case["ability_level"] > 1:
                lines += [f'    call SetUnitAbilityLevel(RE_Caster, \'{plan["rawcode"]}\', {case["ability_level"]})']
        lines += [f'    set RE_SetupOk = RE_SetupOk and GetUnitAbilityLevel(RE_Caster, \'{plan["rawcode"]}\') == {case["ability_level"]}']
        lines += ["    if not RE_SetupOk then", "        call RE_Finish()", "        return", "    endif",
                  "    set RE_SpellTrigger = CreateTrigger()",
                  "    call TriggerRegisterUnitEvent(RE_SpellTrigger, RE_Caster, EVENT_UNIT_SPELL_CAST)",
                  "    call TriggerRegisterUnitEvent(RE_SpellTrigger, RE_Caster, EVENT_UNIT_SPELL_EFFECT)",
                  "    call TriggerRegisterUnitEvent(RE_SpellTrigger, RE_Caster, EVENT_UNIT_SPELL_FINISH)",
                  "    call TriggerRegisterUnitEvent(RE_SpellTrigger, RE_Caster, EVENT_UNIT_SPELL_ENDCAST)",
                  "    call TriggerAddAction(RE_SpellTrigger, function RE_OnSpell)",
                  "    // Baseline before issuing an order; later OBS rows are scheduled samples.",
                  "    call RE_Record()"]
        if case["kind"] == "passive":
            lines += ["    // Passive: accepted=true means initialized, NOT accepted a cast order.",
                      "    set RE_OrderAccepted = true"]
        elif case["kind"] in ("target", "projectile", "buff"):
            lines += [f'    set RE_OrderAccepted = IssueTargetOrder(RE_Caster, "{case["order"]}", RE_Target[0])']
        elif case["kind"] in ("point", "area"):
            lines += [f'    set RE_OrderAccepted = IssuePointOrder(RE_Caster, "{case["order"]}", {_real(case["point"]["x"])}, {_real(case["point"]["y"])})']
        else:
            lines += [f'    set RE_OrderAccepted = IssueImmediateOrder(RE_Caster, "{case["order"]}")']
        lines += ["    if not RE_OrderAccepted then",
                  "        call RE_Finish()", "        return", "    endif",
                  "    call TimerStart(RE_Timer, RE_Interval, true, function RE_Tick)",
                  "endfunction", ""]
    lines += ["function RE_Chat takes nothing returns nothing",
              "    local string msg = GetEventPlayerChatString()",
              "    if RE_Busy then", "        return", "    endif"]
    for index, case in enumerate(plan["cases"]):
        prefix = "if" if index == 0 else "elseif"
        lines += [f'    {prefix} msg == "{case["chat_command"]}" then',
                  f"        call RE_Start_{index}()"]
    lines += ["    endif", "endfunction", "",
              "function RE_Init takes nothing returns nothing",
              "    local trigger t = null", "    if RE_Timer != null then", "        return", "    endif",
              "    set RE_Timer = CreateTimer()", "    set t = CreateTrigger()",
              f'    call TriggerRegisterPlayerChatEvent(t, Player({plan["chat_player"]}), "-re ", false)',
              "    call TriggerAddAction(t, function RE_Chat)",
              "    set t = null", "endfunction"]
    return globals_text, _join(lines)


def build(source: dict[str, Any]) -> dict[str, Any]:
    plan = validate(source)
    case_manifest = {"cases": []}
    for row in plan["cases"]:
        acceptance = "accepted=" + ("true" if row["expected_order_accepted"] else "false")
        opposite = "accepted=" + ("false" if row["expected_order_accepted"] else "true")
        case_manifest["cases"].append({
            "run_id": row["run_id"], "result_file": row["result_file"],
            "timeout_seconds": row["timeout_seconds"],
            "required_markers": ["setup_failed=false", acceptance],
            "inconclusive_markers": ["setup_failed=true", opposite, "buffer_overflow=true"],
            "chat_command": row["chat_command"]})
    # Patch 8 rejects unknown case properties on write because it normalizes
    # its own manifests; chat_command goes into a separate operator guide.
    session_cases = {"cases": [{k: v for k, v in case.items() if k != "chat_command"}
                               for case in case_manifest["cases"]]}
    # Check compatibility with the current session contract, allowing a larger
    # requested timeout that will be checked against its chosen Frida plan later.
    _validate_cases(session_cases, max_seconds=360)
    globals_j, funcs_j = _render_fragments(plan)
    return {"plan": plan, "case_manifest": case_manifest, "session_cases": session_cases,
            "globals": globals_j, "functions": funcs_j}


def write(result: dict[str, Any], output: Path) -> None:
    if output.exists():
        raise ScenarioError(f"refusing to overwrite scenario directory: {output}")
    output.mkdir(parents=True)
    (output / "lab-globals.j").write_text(result["globals"], encoding="utf-8")
    (output / "lab-functions.j").write_text(result["functions"], encoding="utf-8")
    (output / "lab-session-cases.json").write_text(json.dumps(result["session_cases"], indent=2) + "\n", encoding="utf-8")
    (output / "lab-plan.json").write_text(json.dumps(result["plan"], indent=2) + "\n", encoding="utf-8")
    if "map" in result["plan"]:
        m = result["plan"]["map"]
        # These are intended for the newer optional Retail map-prep runner,
        # which is not bundled in every older reconstruction checkout.
        probe = {"id": "re-lab-" + result["plan"]["rawcode"],
                 "source": {"archive": m["archive"], "member": m["member"]},
                 "script_member": "war3map.j", "retail_executable": m["retail_executable"],
                 "result_file": result["plan"]["cases"][0]["result_file"],
                 "edits": [{"block": "globals", "anchor": "endglobals", "where": "before",
                            "file": "lab-globals.j"},
                           {"function": m["hook_function"],
                            "anchor": "function " + m["hook_function"] + " takes nothing returns nothing",
                            "where": "before", "file": "lab-functions.j"},
                           {"function": m["hook_function"], "anchor": m["hook_anchor"],
                            "where": m["hook_where"], "text": "call RE_Init()"}],
                 "metadata": {"mode": m["edition"].upper(), "ability_rawcodes": [result["plan"]["rawcode"]]}}
        (output / "lab-probe.json").write_text(json.dumps(probe, indent=2) + "\n", encoding="utf-8")
    rows = ["# Retail ability laboratory: " + result["plan"]["rawcode"], "",
            "Generated JASS and scenario metadata only. This is not a verified Retail execution.", "",
            "## Cases", "",
            "| Case | Chat command (while Frida is armed) | Target count | Samples |",
            "|---|---|---:|---:|"]
    for case in result["plan"]["cases"]:
        rows.append(f'| `{case["run_id"]}` | `{case["chat_command"]}` | {len(case["targets"])} | {case["ticks"]+1} |')
    rows += ["", "Run each chat command after the Patch 8 session runner arms the corresponding case.",
             "The scenario starts only after that command; no automatic keyboard input is sent.",
             "Compile/prepare a copied map with the generated JASS and confirm an untouched control map first.",
             "A prepared-map manifest (`lab-probe.json`) is included only when map anchors are supplied.",
             "The hooks must run after gameplay/cinematic restrictions have been restored.",
             "The first case's result file in the prep manifest is solely the strict filename preflight;",
             "each JASS case writes its own unique `PreloadGenEnd` filename.",
             "Place the output `result_dir` at the Wine CustomMapData path and clear stale files before running.",
             "Do not JHCR-reload the generated timer or scenario callbacks; use a prepared map.",
             "After cases complete, review `OBS`, optional `BUFF`, and cast/effect/end `SPELL` events.",
             "Timer sample time is nominal JASS timer time, not an exact native effect timestamp.",
             "Casting success is only the JASS `Issue*Order` return; passive accepted=true means setup only.",
             "Never treat successful capture markers as gameplay parity or buff absence proof.",
             "Spawned projectile/area effects may outlive removed units; use well-separated safe test areas.",
             "Native hook budgets and session timeouts must be large enough for the longest case.",
             "", "## Files", "", "- `lab-plan.json`: normalized scenario inputs",
             "- `lab-globals.j`: add inside an existing top-level globals block",
             "- `lab-functions.j`: insert before the selected map function",
             "- `lab-session-cases.json`: Patch 8 `--cases` input",
             "- `lab-probe.json`: optional map-preparation manifest", ""]
    (output / "README.md").write_text("\n".join(rows), encoding="utf-8")
