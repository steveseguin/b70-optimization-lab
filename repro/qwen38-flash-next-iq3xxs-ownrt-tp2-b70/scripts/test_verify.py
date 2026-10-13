"""CPU-only rejection tests; no runtime or systemd actions."""
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from verify import PACKET, verify_suite

class ReceiptChecks(unittest.TestCase):
    def test_sealed_suite(self):
        with contextlib.redirect_stdout(io.StringIO()):
            value = verify_suite(PACKET / "receipts-cards01-20261013-c4096/WS128")
        self.assertAlmostEqual(value, 37.85626413203107)

    def test_reject_changed_output(self):
        source = PACKET / "receipts-cards01-20261013-c4096/WS128"
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory)
            shutil.copyfile(source / "summary.json", dest / "summary.json")
            row = json.loads((dest / "summary.json").read_text())["rows"][0]
            receipt = json.loads((source / row["receipt"]).read_text())
            receipt["tokens"][0] += 1
            file = dest / row["receipt"]
            file.parent.mkdir(parents=True)
            file.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, "token mismatch"):
                verify_suite(dest)

    def test_reject_duplicate_or_missing_prompt(self):
        source = PACKET / "receipts-cards01-20261013-c4096/WS128"
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory)
            summary = json.loads((source / "summary.json").read_text())
            summary["rows"][-1] = summary["rows"][0]
            (dest / "summary.json").write_text(json.dumps(summary))
            with self.assertRaisesRegex(ValueError, "prompt coverage"):
                verify_suite(dest)

if __name__ == "__main__":
    unittest.main()
