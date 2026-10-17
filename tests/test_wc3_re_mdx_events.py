"""End-to-end regression for size-prefixed MDX EVTS event objects."""

from __future__ import annotations

import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MPQTOOL = ROOT / "build/bin/mpqtool"
MDXTOOL = ROOT / "build/bin/mdxtool"


def _chunk(tag: bytes, payload: bytes) -> bytes:
    return tag + struct.pack("<I", len(payload)) + payload


def _event(name: str, timestamp: int) -> bytes:
    node = (struct.pack("<I", 96) + name.encode("ascii").ljust(80, b"\0")
            + struct.pack("<III", 7, 0xFFFFFFFF, 0))
    return node + b"KEVT" + struct.pack("<III", 1, 0xFFFFFFFF, timestamp)


class MdxEventJsonTests(unittest.TestCase):
    def test_reads_multiple_size_prefixed_events_and_key_times(self):
        if not MPQTOOL.is_file() or not MDXTOOL.is_file():
            self.skipTest("build mpqtool and mdxtool first")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sample.mdx"
            archive = root / "sample.mpq"
            evt = _event("SPN1spark", 500) + _event("SND1impact", 1250)
            source.write_bytes(b"MDLX" + _chunk(b"EVTS", evt))
            subprocess.run([str(MPQTOOL), "-mpq", str(archive), "create"],
                           check=True, capture_output=True)
            subprocess.run([str(MPQTOOL), "-mpq", str(archive), "pack",
                            str(source), "Effects\\sample.mdx"],
                           check=True, capture_output=True)
            result = subprocess.run([str(MDXTOOL), "-mpq", str(archive), "-model",
                                     "Effects\\sample.mdx", "--info-json"],
                                    check=True, capture_output=True, text=True)
            metadata = json.loads(result.stdout)
            self.assertTrue(metadata["event_objects_decoded"])
            self.assertEqual([(event["name"], event["keys_ms"])
                              for event in metadata["events"]],
                             [("SPN1spark", [500]), ("SND1impact", [1250])])


if __name__ == "__main__":
    unittest.main()
