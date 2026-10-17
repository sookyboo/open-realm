"""Offline tests for the rawcode-driven Retail RE lookup foundation."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from wc3_re import lookup
import wc3_ability_re as cli


def fake_row(rawcode="AOsw", code="AOwd", edition="TFT"):
    return {
        "schema_version": 1, "edition": edition, "rawcode": rawcode,
        "found": True, "archives": ["War3.mpq", "War3x.mpq"],
        "ability": {"id": rawcode, "code": code, "uber_alias": None,
                    "comments": "Serpent Ward", "race": "orc", "levels": 3,
                    "hero": True, "item": False, "version": 1,
                    "class_hint": "CAbilityWard", "parent_hint": "AAsm"},
        "ranks": [
            {"level": 1, "target_mask": "", "cost": 30, "cooldown": 6.5,
             "range": 500, "duration": 40, "hero_duration": 40, "area": 0, "cast": 0,
             "data": {"A": {"type": "number", "value": 0}}, "unit_id": "osp1",
             "buff_ids": ["Bwd1"], "effect_id": None},
        ],
        "strings": {"Name": "Serpent Ward", "Ubertip": "Summons a ward"},
        "aliases": ["AImo"], "buffs": [{"id": "Bwd1", "target_art": "Models\\ward.mdx"}],
    }


class ClassReferenceTests(unittest.TestCase):
    def test_real_reference_maps_serpent_ward_and_phoenix_fire(self):
        classes = lookup.class_reference()
        self.assertEqual(classes["AOwd"]["name"], "CAbilityWard")
        self.assertEqual(classes["Apxf"]["name"], "CAbilityPhoenixFire")
        self.assertNotIn("AOsw", classes)  # alias is resolved via authored `code`, not guessed

    def test_tft_class_rows_preserve_source_identity_and_callback_registration(self):
        classes = lookup.class_reference()
        self.assertEqual(classes["ANfl"]["registration"]["binary_sha256"],
                         lookup.load_inventory_identity()["sha256"])
        self.assertEqual(classes["ANfl"]["registration"]["factory_file_offset"], "0x00877840")
        self.assertEqual(classes["AOwd"]["registration"]["destroy_file_offset"], "0x00833d40")

    def test_rawcode_is_case_sensitive_and_safe(self):
        self.assertEqual(lookup.check_rawcode("Apxf"), "Apxf")
        for invalid in ("Apx", "Apxff", "ab-c", "\\x00ABC", "\u00e9bcD"):
            with self.subTest(invalid=invalid), self.assertRaises(lookup.LookupError):
                lookup.check_rawcode(invalid)

    def test_real_patch1_inventory_is_validated(self):
        identity = lookup.load_inventory_identity()
        self.assertEqual(identity["preferred_image_base"], "0x00400000")
        self.assertEqual(len(identity["sha256"]), 64)

    def test_executable_hash_mismatch_fails_closed(self):
        identity = lookup.load_inventory_identity()
        with tempfile.TemporaryDirectory() as temp:
            game = Path(temp) / "Warcraft III.exe"
            game.write_bytes(b"not retail")
            with self.assertRaisesRegex(lookup.LookupError, "SHA-256 differs"):
                lookup.check_executable(game, identity)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.audit = self.folder / "ability_audit"
        self.audit.touch()
        self.data = self.folder / "data"
        self.data.mkdir()

    def call(self, row, returncode=0, edition="tft", rawcode="AOsw"):
        completed = subprocess.CompletedProcess([], returncode, json.dumps(row), "")
        with mock.patch.object(lookup.subprocess, "run", return_value=completed) as invoked:
            result = lookup.audit_one(rawcode, edition, audit=self.audit, data_dir=self.data)
            invoked.assert_called_once_with(
                [str(self.audit), "-data", str(self.data), "-" + edition, "-json", "-raw", rawcode],
                capture_output=True, text=True, check=False)
        return result

    def test_direct_structured_data_not_text_scraping(self):
        row = self.call(fake_row())
        self.assertEqual(row["ability"]["code"], "AOwd")
        self.assertEqual(row["ranks"][0]["unit_id"], "osp1")
        self.assertEqual(row["buffs"][0]["target_art"], "Models\\ward.mdx")

    def test_roc_archive_provenance_excludes_tft_overlays(self):
        row = fake_row(edition="ROC")
        row["archives"] = ["War3Local.mpq", "War3xLocal.mpq", "War3x.mpq",
                           "FrozenThrone.mpq", "Deprecated.mpq", "War3.mpq"]
        result = self.call(row, edition="roc")
        self.assertEqual(result["archives"],
                         ["War3Local.mpq", "Deprecated.mpq", "War3.mpq"])

    def test_tft_archive_classification_uses_supported_filename_only(self):
        cases = {
            "data/Warcraft III/War3.mpq": False,
            "data/Warcraft III/War3Local.mpq": False,
            "data/Warcraft III/War3x.mpq": True,
            "data/Warcraft III/War3xLocal.mpq": True,
            "data/Warcraft III/Frozen Throne.mpq": True,
            "data/Warcraft III/FROZEN THRONE LOCAL.MPQ": True,
            "/tmp/war3x-backup/War3.mpq": False,
            "/tmp/Frozen-work/Deprecated.mpq": False,
            "CustomWar3x.mpq": False,
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(lookup._is_tft_archive(path), expected)

    def test_roc_archive_provenance_ignores_parent_directory_substrings(self):
        row = fake_row(edition="ROC")
        row["archives"] = ["/tmp/war3x-backup/War3.mpq",
                            "/tmp/Frozen-work/Deprecated.mpq",
                            "/tmp/War3xLocal.mpq"]
        result = self.call(row, edition="roc")
        self.assertEqual(result["archives"], row["archives"][:2])

    def test_rank_localized_strings_split_quoted_audit_csv_without_mutating_source(self):
        row = fake_row()
        source = 'Summons a ward, now","Summons rank two","Summons rank three'
        row["strings"]["Ubertip"] = source
        normalized = self.call(row)
        self.assertEqual(normalized["strings"]["Ubertip"], source)
        self.assertEqual([item["values"]["Ubertip"] for item in normalized["strings_by_rank"]],
                         ["Summons a ward, now", "Summons rank two", "Summons rank three"])

    def test_malformed_rank_localized_string_count_fails_closed(self):
        row = fake_row()
        row["strings"]["Ubertip"] = 'First rank","Second rank'
        with mock.patch.object(lookup.subprocess, "run", return_value=
                               subprocess.CompletedProcess([], 0, json.dumps(row), "")):
            with self.assertRaisesRegex(lookup.LookupError, "localized strings for 3 ability ranks"):
                lookup.audit_one("AOsw", "tft", audit=self.audit, data_dir=self.data)

    def test_missing_ability_is_valid_audit_result(self):
        row = {"schema_version": 1, "edition": "ROC", "rawcode": "AOsw",
               "found": False, "archives": ["War3.mpq"]}
        self.assertFalse(self.call(row, returncode=1, edition="roc")["found"])

    def test_mismatched_audit_output_is_rejected(self):
        with self.assertRaisesRegex(lookup.LookupError, "identity mismatch"):
            self.call(fake_row(rawcode="ANch"))

    def test_malformed_json_rejected(self):
        with mock.patch.object(lookup.subprocess, "run", return_value=
                               subprocess.CompletedProcess([], 0, "not json", "bad report")):
            with self.assertRaisesRegex(lookup.LookupError, "did not return valid JSON"):
                lookup.audit_one("AOsw", "tft", audit=self.audit, data_dir=self.data)

    def test_nonzero_when_found_is_rejected(self):
        with self.assertRaisesRegex(lookup.LookupError, "despite reporting a found row"):
            self.call(fake_row(), returncode=1)

    def test_missing_binary_reports_actionable_error(self):
        with self.assertRaisesRegex(lookup.LookupError, "make ability_audit"):
            lookup.audit_one("Apxf", "tft", audit=self.folder / "missing", data_dir=self.data)

    def test_resolve_preserves_edition_and_class_lead(self):
        tft = fake_row()
        roc = {"schema_version": 1, "edition": "ROC", "rawcode": "AOsw",
               "found": False, "archives": ["War3.mpq"]}
        with mock.patch.object(lookup, "audit_one", side_effect=[roc, tft]):
            result = lookup.resolve("AOsw", ["roc", "tft"], audit=self.audit, data_dir=self.data)
        self.assertFalse(result["editions"]["roc"]["found"])
        hint = result["editions"]["tft"]["retail_class_reference"]
        self.assertEqual(hint["implementation_code"], "AOwd")
        self.assertEqual(hint["class"], "CAbilityWard")
        self.assertEqual(hint["status"], "offline_reference_hint")
        self.assertFalse(result["executable_check"]["checked"])

    def test_unknown_rawcode_not_claimed(self):
        missing = {"schema_version": 1, "edition": "TFT", "rawcode": "Axxx",
                   "found": False, "archives": ["War3.mpq"]}
        with mock.patch.object(lookup, "audit_one", return_value=missing):
            with self.assertRaisesRegex(lookup.LookupError, "absent"):
                lookup.resolve("Axxx", ["tft"], audit=self.audit, data_dir=self.data)

    def test_cli_seed_writes_only_supported_material(self):
        data = {"schema_version": 1, "rawcode": "Apxf", "editions": {"tft": fake_row(rawcode="Apxf", code="Apxf")}}
        directory = self.folder / "out"
        with mock.patch.object(cli, "resolve", return_value=data):
            result = cli.main(["reconstruct", "Apxf", "--output-dir", str(directory)])
        self.assertEqual(result, 0)
        manifest = json.loads((directory / "manifest.json").read_text())
        self.assertEqual(manifest["status"], "seed_only")
        self.assertIn("ghidra_code_export", manifest["pending_stages"])
        self.assertEqual(json.loads((directory / "lookup.json").read_text())["rawcode"], "Apxf")
        with mock.patch.object(cli, "resolve", return_value=data):
            self.assertEqual(cli.main(["reconstruct", "Apxf", "--output-dir", str(directory)]), 1)

    def test_index_is_labelled_as_reference_only(self):
        output = self.folder / "class-index.json"
        self.assertEqual(cli.main(["index", "--output", str(output)]), 0)
        data = json.loads(output.read_text())
        self.assertEqual(data["kind"], "tft_class_reference_only")
        self.assertEqual(data["classes"]["AOwd"]["name"], "CAbilityWard")

    def test_verify_is_reserved(self):
        self.assertEqual(cli.main(["verify", "Apxf"]), 3)


if __name__ == "__main__":
    unittest.main()
