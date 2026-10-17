"""Offline synthetic tests for Patch 5 authored presentation resolution."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from wc3_re import presentation as p
import wc3_ability_re as cli


def lookup() -> dict:
    return {
        "schema_version": 1, "rawcode": "Apxf",
        "editions": {
            "roc": {"found": False},
            "tft": {
                "found": True, "archives": ["War3.mpq", "War3x.mpq"],
                "ability": {"id": "Apxf", "code": "Apxf"},
                "ranks": [{"level": 1, "unit_id": None, "effect_id": "Fx00",
                           "buff_ids": ["Bpxf"]}],
                "presentation": {"CasterArt": "Abilities/Spells/Fire/One.mdx,Abilities/Spells/Fire/One.mdl",
                                 "Art": "ReplaceableTextures/CommandButtons/BTNFire.blp",
                                 "Effectsound": "PhoenixFire"},
                "buffs": [{"id": "Bpxf", "target_art": "Abilities/Spells/Fire/Two.mdx"}],
                "effects": [{"id": "Fx00", "effect_art": "Abilities/Spells/Fire/Three.mdx"}],
            },
        },
    }


class PresentationTest(unittest.TestCase):
    def test_path_normalization_and_icon_classification(self):
        self.assertEqual(p.classify_art("Abilities/Fire.mdl", "TargetArt"),
                         ("model", "Abilities\\Fire.mdx"))
        self.assertEqual(p.classify_art("ReplaceableTextures/Icon.blp", "Art")[0],
                         "texture_or_icon")
        with self.assertRaises(p.PresentationError):
            p.classify_art("../secret.mdx", "TargetArt")
        with self.assertRaises(p.PresentationError):
            p.classify_art("C:\\escape.mdx", "TargetArt")

    def test_refs_editions_dedup_and_unverified_semantics(self):
        report = p.build_presentation(lookup(), mpqtool=Path("mpqtool"),
                                      mdxtool=Path("mdxtool"), inspect_assets=False)
        self.assertFalse(report["editions"]["roc"]["found"])
        data = report["editions"]["tft"]
        self.assertEqual(len(data["models"]), 3)
        self.assertTrue(all(model["status"] == "not_inspected" for model in data["models"]))
        self.assertEqual(len(data["sounds"]), 1)
        self.assertEqual(len([r for r in data["references"] if r["kind"] == "model"]), 4)
        self.assertEqual(data["rank_links"][0]["effect_id"], "Fx00")
        self.assertFalse(report["runtime_effect_timing_verified"])

    def test_sylk_sparse_cells_and_sound_row(self):
        rows = p.parse_sylk(b'ID;PWXL;N;E\nC;X1;Y1;K"SoundName"\n'
                            b'C;X2;Y1;K"FileNames"\nC;X3;Y1;K"Pitch"\n'
                            b'C;Y2;X1;K"PhoenixFire"\nC;X2;K"p1.wav,p2.wav"\n'
                            b'C;X3;K"1.2"\nE\n')
        self.assertEqual(rows[0]["FileNames"], "p1.wav,p2.wav")
        self.assertEqual(p._sound_match("PhoenixFire", rows, "War3.mpq")["status"],
                         "authored_sound_row")
        self.assertEqual(p._sound_match("Unknown", rows, None)["status"],
                         "unresolved_sound_alias")
        self.assertEqual(p.parse_sylk(b'ID;PWXL\nE\n'), [])

    def test_archive_overlay_and_mdxtool_json_contract(self):
        model = "Abilities\\Spells\\Fire\\One.mdx"
        calls = []
        def run(args, **kwargs):
            calls.append(args)
            if args[0] == "mpqtool" and args[2] == "War3x.mpq":
                return subprocess.CompletedProcess(args, 0, b"MDLX bytes", b"")
            if args[0] == "mdxtool":
                return subprocess.CompletedProcess(args, 0, json.dumps({
                    "schema_version": 1, "path": model, "sequences": [{"name": "Stand"}],
                    "textures": [], "chunks": {}, "event_objects_decoded": True,
                    "events": [],
                }).encode(), b"")
            return subprocess.CompletedProcess(args, 1, b"", b"missing")
        resolver = p.ArchiveResolver(["War3.mpq", "War3x.mpq"], Path("mpqtool"), Path("mdxtool"))
        with mock.patch.object(p.subprocess, "run", side_effect=run):
            result = resolver.inspect_model(model)
            self.assertEqual(result["status"], "static_model_metadata")
            self.assertEqual(result["archive"], "War3x.mpq")
            self.assertEqual(resolver.inspect_model(model), result)
        self.assertEqual(len(calls), 2)  # one MPQ cat, one MDX metadata export

    def test_invalid_model_json_rejected(self):
        resolver = p.ArchiveResolver(["War3.mpq"], Path("mpqtool"), Path("mdxtool"))
        def run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, b"{}" if args[0] == "mdxtool" else b"MDLX", b"")
        with mock.patch.object(p.subprocess, "run", side_effect=run):
            with self.assertRaisesRegex(p.PresentationError, "invalid metadata"):
                resolver.inspect_model("Abilities\\Fire.mdx")

    def test_event_dependencies_follow_spn_and_snd_without_runtime_claim(self):
        model = "Abilities\\Spells\\Fire\\One.mdx"
        child = "Abilities\\Spells\\Fire\\Spark.mdx"
        data = {
            "schema_version": 1, "path": model, "sequences": [], "textures": [],
            "chunks": {"EVTS": 180}, "event_objects_decoded": True,
            "events": [{"name": "SPN1Spark", "keys_ms": [200], "node_id": 2},
                       {"name": "SND1FireHit", "keys_ms": [350], "node_id": 3}],
        }
        child_data = {"schema_version": 1, "path": child, "sequences": [], "textures": [],
                      "chunks": {}, "event_objects_decoded": True, "events": []}
        files = {
            "Splats\\SpawnData.slk": (b'C;X1;Y1;K"Name"\nC;X2;Y1;K"Model"\n'
                                       b'C;X1;Y2;K"Spark"\nC;X2;K"Abilities/Spells/Fire/Spark.mdx"\n'),
            "UI\\SoundInfo\\AnimLookups.slk": (b'C;X1;Y1;K"Name"\nC;X2;Y1;K"SoundLabel"\n'
                                                  b'C;X1;Y2;K"FireHit"\nC;X2;K"FireBoom"\n'),
            "UI\\SoundInfo\\AbilitySounds.slk": b'ID;PWXL\n',
        }
        def run(args, **kwargs):
            if args[0] == "mpqtool":
                path = args[-1]
                return subprocess.CompletedProcess(args, 0, files.get(path, b"MDLX"), b"")
            if args[0] == "mdxtool":
                return subprocess.CompletedProcess(args, 0, json.dumps(
                    child_data if args[-2] == child else data).encode(), b"")
            return subprocess.CompletedProcess(args, 1, b"", b"err")
        item = lookup()
        item["editions"]["tft"]["presentation"] = {"CasterArt": model}
        item["editions"]["tft"]["buffs"] = []
        item["editions"]["tft"]["effects"] = []
        with mock.patch.object(p.subprocess, "run", side_effect=run):
            report = p.build_presentation(item, mpqtool=Path("mpqtool"), mdxtool=Path("mdxtool"))
        resolved = report["editions"]["tft"]
        self.assertEqual(len(resolved["models"]), 2)
        refs = resolved["models"][0]["event_dependencies"]
        self.assertEqual(refs[0]["child_model"], child)
        self.assertEqual(refs[1]["sound_alias"], "FireBoom")
        self.assertFalse(report["runtime_effect_timing_verified"])

    def test_missing_models_and_corrupt_event_metadata_handled(self):
        item = lookup()
        with mock.patch.object(p.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, b"", b"no archive")):
            result = p.build_presentation(item, mpqtool=Path("mpqtool"), mdxtool=Path("mdxtool"))
        self.assertIn("not_found_in_selected_archives", {m["status"] for m in result["editions"]["tft"]["models"]})
        self.assertTrue(any("not inspected" in gap.lower() for gap in result["editions"]["tft"]["gaps"]))

    def test_bad_lookup_and_model_limit_rejected(self):
        with self.assertRaisesRegex(p.PresentationError, "unsupported lookup"):
            p.build_presentation({}, mpqtool=Path("mpqtool"), mdxtool=Path("mdxtool"))
        with self.assertRaisesRegex(p.PresentationError, "max_models"):
            p.build_presentation(lookup(), mpqtool=Path("mpqtool"), mdxtool=Path("mdxtool"), max_models=0)

    def test_write_and_cli(self):
        report = p.build_presentation(lookup(), mpqtool=Path("mpqtool"),
                                      mdxtool=Path("mdxtool"), inspect_assets=False)
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "presentation"
            p.write_presentation(report, target)
            self.assertEqual(json.loads((target / "assets.json").read_text())["rawcode"], "Apxf")
            self.assertIn("not an observed runtime timeline", (target / "review.md").read_text())
            with self.assertRaises(p.PresentationError):
                p.write_presentation(report, target)
            look = Path(td) / "lookup.json"
            look.write_text(json.dumps(lookup()))
            out = Path(td) / "output"
            self.assertEqual(cli.main(["ability-presentation", "--lookup", str(look),
                                       "--output", str(out), "--no-asset-inspection"]), 0)
            self.assertTrue((out / "assets.json").is_file())

    def test_malformed_art_and_buff_fail_closed(self):
        item = lookup()
        item["editions"]["tft"]["presentation"]["CasterArt"] = "../bad.mdx"
        with self.assertRaisesRegex(p.PresentationError, "unsafe"):
            p.build_presentation(item, mpqtool=Path("mpqtool"), mdxtool=Path("mdxtool"), inspect_assets=False)
        item["editions"]["tft"]["presentation"] = {}
        item["editions"]["tft"]["buffs"] = ["Bpxf"]
        with self.assertRaisesRegex(p.PresentationError, "malformed buffs"):
            p.build_presentation(item, mpqtool=Path("mpqtool"), mdxtool=Path("mdxtool"), inspect_assets=False)


if __name__ == "__main__":
    unittest.main()
