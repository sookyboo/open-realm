"""Offline Patch 9 scenario emitter and session manifest contracts."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from wc3_re import scenarios, session
import wc3_ability_re


def unit(x=0, y=0, *, player=0, unit_id="hfoo"):
    return {"unit_id": unit_id, "player": player, "x": x, "y": y}


def specification():
    return {"schema_version": 1, "rawcode": "Apxf", "result_dir": "/tmp/CustomMapData",
            "cases": [
                {"run_id": "phoenix-300", "kind": "passive", "caster": unit(),
                 "targets": [unit(300, player=12)], "duration_seconds": 3,
                 "sample_interval_seconds": 0.25, "buff_ids": ["Bpxf"]},
                {"run_id": "phoenix-650", "kind": "passive", "caster": unit(1200),
                 "targets": [unit(1850, player=12)], "duration_seconds": 3,
                 "sample_interval_seconds": 0.25},
            ]}


class ScenarioTests(unittest.TestCase):
    def test_batch_generates_isolated_ids_and_session_contract(self):
        report = scenarios.build(specification())
        plan = report["plan"]
        self.assertEqual(len(plan["cases"]), 2)
        self.assertIn('PreloadGenEnd("phoenix-300.txt")', report["functions"])
        self.assertIn('PreloadGenEnd("phoenix-650.txt")', report["functions"])
        self.assertIn('SESSION_START run_id=', report["functions"])
        self.assertIn('SESSION_DONE run_id=', report["functions"])
        self.assertIn('BUFF target=0 rawcode=Bpxf tick=', report["functions"])
        self.assertIn('SPELL stage=effect rawcode_int=', report["functions"])
        self.assertIn('EVENT_UNIT_SPELL_ENDCAST', report["functions"])
        self.assertIn('DestroyTrigger(RE_SpellTrigger)', report["functions"])
        self.assertIn('RE_Target[0] = CreateUnit(Player(12)', report["functions"])
        cases = report["session_cases"]["cases"]
        self.assertEqual([c["run_id"] for c in cases], ["phoenix-300", "phoenix-650"])
        self.assertEqual([c["timeout_seconds"] for c in cases], [60, 60])
        self.assertEqual([Path(c["result_file"]).name for c in cases], ["phoenix-300.txt", "phoenix-650.txt"])
        self.assertEqual(session._validate_cases(report["session_cases"], max_seconds=60), cases)
        self.assertNotIn("chat_command", cases[0])
        self.assertIn("setup_failed=true", cases[0]["inconclusive_markers"])
        self.assertIn("buffer_overflow=true", cases[0]["inconclusive_markers"])
        self.assertEqual(plan["cases"][0]["ticks"], 12)

    def test_target_point_area_immediate_projectile_buff_hero(self):
        source = specification()
        source["rawcode"] = "AOsw"
        cases = source["cases"] = []
        for kind in ("target", "point", "area", "immediate", "projectile", "buff"):
            entry = {"run_id": kind, "kind": kind, "order": "ward", "caster": unit(),
                     "targets": [unit(80, player=12)] if kind in ("target", "projectile", "buff") else []}
            if kind in ("area", "point"):
                entry["point"] = {"x": 99, "y": 120}
            cases.append(entry)
        cases[0]["learn_mode"] = "hero_skill"
        cases[0]["hero_level"] = 6
        cases[0]["ability_level"] = 3
        js = scenarios.build(source)["functions"]
        self.assertIn("IssueTargetOrder", js)
        first_case = js[js.index("function RE_Start_0"):js.index("function RE_Start_1")]
        self.assertLess(first_case.index("call RE_Record()"), first_case.index("IssueTargetOrder"))
        self.assertIn("IssuePointOrder", js)
        self.assertIn("IssueImmediateOrder", js)
        self.assertIn("call SetHeroLevel(RE_Caster, 6, false)", js)
        self.assertEqual(js.count("call SelectHeroSkill(RE_Caster, 'AOsw')"), 3)
        self.assertIn('GetUnitAbilityLevel(RE_Caster, \'AOsw\') == 3', js)
        self.assertEqual(js.count('function RE_Start_'), 6)
        # Stock JASS (without JassHelper forward references) requires emitter before tick callback.
        self.assertLess(js.index("function RE_Finish"), js.index("function RE_Tick"))
        self.assertLess(js.index("function RE_Tick"), js.index("function RE_Start_0"))
        self.assertLess(js.index("function RE_Chat"), js.index("function RE_Init"))

    def test_expected_rejected_order_is_a_required_outcome(self):
        source = specification()
        source["rawcode"] = "AOsw"
        source["cases"] = [{"run_id": "ward-rejected", "kind": "point", "order": "ward",
                            "expected_order_accepted": False, "caster": unit(),
                            "point": {"x": 100, "y": 200}}]
        report = scenarios.build(source)
        case = report["session_cases"]["cases"][0]
        self.assertEqual(case["required_markers"], ["setup_failed=false", "accepted=false"])
        self.assertEqual(case["inconclusive_markers"], ["setup_failed=true", "accepted=true",
                                                         "buffer_overflow=true", "observation_truncated=true"])

    def test_expected_order_acceptance_is_boolean_and_not_for_passives(self):
        source = specification()
        source["cases"][0]["expected_order_accepted"] = "false"
        with self.assertRaisesRegex(scenarios.ScenarioError, "must be a boolean"):
            scenarios.build(source)
        source = specification()
        source["cases"][0]["expected_order_accepted"] = False
        with self.assertRaisesRegex(scenarios.ScenarioError, "only applies to ordered"):
            scenarios.build(source)

    def test_watched_units_are_bounded_observed_and_cleaned_between_cases(self):
        source = specification()
        source["rawcode"] = "AOsw"
        source["cases"] = [
            {"run_id": "ward-good", "kind": "point", "order": "ward",
             "expected_order_accepted": True, "caster": unit(unit_id="Oshd"),
             "learn_mode": "hero_skill", "hero_level": 2, "point": {"x": 300, "y": 200},
             "unit_observation": {"unit_ids": ["osp1"], "x": 300, "y": 200,
                                  "radius": 512, "cleanup_before_next": True},
             "required_function_rvas": ["0x00834110"]},
            {"run_id": "ward-bad", "kind": "point", "order": "ward",
             "expected_order_accepted": False, "caster": unit(unit_id="Oshd"),
             "learn_mode": "hero_skill", "hero_level": 2, "point": {"x": -500, "y": 200},
             "unit_observation": {"unit_ids": ["osp1"], "x": -500, "y": 200,
                                  "radius": 512, "cleanup_before_next": True}},
        ]
        result = scenarios.build(source)
        j = result["functions"]
        self.assertIn("UNIT_COUNT rawcode=osp1 tick=", j)
        self.assertIn("GetOwningPlayer(observed)", j)
        self.assertIn("RE_ObservationTruncated", j)
        self.assertIn("call RemoveUnit(observed)", j)
        self.assertIn("required_function_rvas", json.dumps(result["session_cases"]))
        rejected = j[j.index("function RE_Start_1"):j.index("function RE_Chat")]
        self.assertIn("IssuePointOrder", rejected)
        self.assertIn("TimerStart(RE_Timer", rejected)
        self.assertNotIn("if not RE_OrderAccepted then", rejected)

    def test_watched_unit_limits_and_native_rvas_are_validated(self):
        source = specification()
        source["cases"][0]["unit_observation"] = {"unit_ids": ["osp1"], "x": 0, "y": 0,
                                                     "radius": 100, "max_units": 0}
        with self.assertRaisesRegex(scenarios.ScenarioError, "max_units"):
            scenarios.build(source)
        source = specification()
        source["cases"][0]["required_function_rvas"] = ["bad"]
        with self.assertRaisesRegex(scenarios.ScenarioError, "RVA"):
            scenarios.build(source)

    def test_invalid_rawcode_and_duplicate_case_ids(self):
        sample = specification()
        sample["rawcode"] = "Apxf\" + BAD()"
        with self.assertRaisesRegex(scenarios.ScenarioError, "rawcode"):
            scenarios.build(sample)
        sample = specification()
        sample["cases"][1]["run_id"] = "phoenix-300"
        with self.assertRaisesRegex(scenarios.ScenarioError, "duplicate|unique"):
            scenarios.build(sample)

    def test_orders_not_guessed_and_passive_rejects_order(self):
        sample = specification()
        sample["cases"][0]["kind"] = "target"
        with self.assertRaisesRegex(scenarios.ScenarioError, "explicit.*order"):
            scenarios.build(sample)
        sample = specification()
        sample["cases"][0]["order"] = "ward"
        with self.assertRaisesRegex(scenarios.ScenarioError, "passive.*order"):
            scenarios.build(sample)

    def test_unsafe_type_and_property_rejected(self):
        sample = specification()
        sample["cases"][0]["targets"][0]["player"] = True
        with self.assertRaisesRegex(scenarios.ScenarioError, "player"):
            scenarios.build(sample)
        sample = specification()
        sample["cases"][0]["mystery"] = "script"
        with self.assertRaisesRegex(scenarios.ScenarioError, "unsupported keys"):
            scenarios.build(sample)
        sample = specification()
        sample["result_dir"] = "relative/path"
        with self.assertRaisesRegex(scenarios.ScenarioError, "absolute"):
            scenarios.build(sample)
        sample = specification()
        sample["cases"][0]["sample_interval_seconds"] = 0
        with self.assertRaisesRegex(scenarios.ScenarioError, "finite"):
            scenarios.build(sample)

    def test_max_samples_and_buff_observation_budget(self):
        sample = specification()
        sample["cases"][0]["duration_seconds"] = 60
        sample["cases"][0]["sample_interval_seconds"] = 0.05
        with self.assertRaisesRegex(scenarios.ScenarioError, "ticks exceed"):
            scenarios.build(sample)
        sample = specification()
        sample["cases"][0]["duration_seconds"] = 6
        sample["cases"][0]["sample_interval_seconds"] = 0.05
        sample["cases"][0]["targets"] = [unit(i, player=12) for i in range(8)]
        sample["cases"][0]["buff_ids"] = ["B000", "B001", "B002", "B003", "B004"]
        with self.assertRaisesRegex(scenarios.ScenarioError, "buffer limit"):
            scenarios.build(sample)

    def test_map_preparation_manifest_matches_source_anchor_contract(self):
        source = specification()
        source["map"] = {"archive": "/data/War3xLocal.mpq", "member": "Maps/FrozenThrone/Campaign/OrcX01.w3x",
                         "retail_executable": "/data/Warcraft III.exe",
                         "hook_function": "Trig_Intro_Skipped_Actions",
                         "hook_anchor": "call ConditionalTriggerExecute( gg_trg_Gameplay )"}
        result = scenarios.build(source)
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "lab"
            scenarios.write(result, target)
            probe = json.loads((target / "lab-probe.json").read_text())
            self.assertEqual(probe["edits"][0]["block"], "globals")
            self.assertEqual(probe["edits"][1]["where"], "before")
            self.assertEqual(probe["edits"][2]["text"], "call RE_Init()")
            self.assertEqual(probe["result_file"], "/tmp/CustomMapData/phoenix-300.txt")
            self.assertTrue((target / "lab-functions.j").is_file())
            self.assertEqual(len(json.loads((target / "lab-session-cases.json").read_text())["cases"]), 2)
            with self.assertRaisesRegex(scenarios.ScenarioError, "refusing to overwrite"):
                scenarios.write(result, target)

    def test_no_map_probe_manifest_without_hook(self):
        report = scenarios.build(specification())
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / 'lab'
            scenarios.write(report, target)
            self.assertFalse((target / 'lab-probe.json').exists())

    def test_cli_rejects_rawcode_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / 'spec.json'
            source.write_text(json.dumps(specification()))
            with mock.patch('sys.stderr'):
                self.assertEqual(wc3_ability_re.main(['ability-scenarios', 'AOsw', '--spec', str(source),
                                                       '--output', str(Path(td) / 'x')]), 1)
            self.assertEqual(wc3_ability_re.main(['ability-scenarios', 'Apxf', '--spec', str(source),
                                                   '--output', str(Path(td) / 'lab')]), 0)

    def test_jass_function_balance_and_native_provenance(self):
        f = scenarios.build(specification())['functions']
        self.assertEqual(sum(line.startswith('function ') for line in f.splitlines()),
                         sum(line == 'endfunction' for line in f.splitlines()))
        self.assertIn('GetUnitCurrentOrder(RE_Caster)', f)
        self.assertNotIn('UnitDamageTarget(', f)  # no bypassing Retail's order pipeline
        self.assertNotIn('call ExecuteFunc(', f)
        self.assertIn('PreloadGenStart()', f)
        self.assertIn('PreloadGenClear()', f)


if __name__ == '__main__':
    unittest.main()
