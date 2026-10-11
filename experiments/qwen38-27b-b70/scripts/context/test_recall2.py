"""CPU-only checks of recall2.py (windowed archive search); no model or device calls."""
import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest


class Recall2(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        os.environ["RECALL_ARCHIVE"] = self.dir.name
        for n in range(1, 61):
            text = f"Day {n} was quiet. The clerk moved abcd12 to {n * 10}."
            if n % 7 == 0:
                text += f" The porter argued about the lamp by gate {n}."
            (Path(self.dir.name) / f"item-{n:03d}.txt").write_text(text + "\n\nSecond paragraph of item %d." % n)
        import importlib
        import recall2
        self.mod = importlib.reload(recall2)

    def tearDown(self):
        self.dir.cleanup()
        os.environ.pop("RECALL_ARCHIVE", None)

    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.mod.main(list(argv))
        return out.getvalue().strip().splitlines()

    def test_default_is_v1(self):
        lines = self.run_cli("abcd12")
        self.assertEqual(len(lines), 41)                     # 40 matches + the note
        self.assertTrue(lines[0].startswith("item 1: "))
        self.assertIn("60 matches", lines[-1])
        self.assertIn("showing the first 40", lines[-1])

    def test_last_before(self):
        lines = self.run_cli("abcd12", "--before", "41", "--last", "3")
        self.assertEqual([l.split(":")[0] for l in lines[:3]], ["item 39", "item 40", "item 41"])
        self.assertIn("41 matches in items 1-41", lines[3])
        self.assertIn("showing the last 3", lines[3])

    def test_window_without_truncation_has_no_note(self):
        lines = self.run_cli("abcd12", "--after", "58")
        self.assertEqual([l.split(":")[0] for l in lines], ["item 58", "item 59", "item 60"])

    def test_where(self):
        lines = self.run_cli("--where", "porter", "--before", "30")
        self.assertEqual(lines, ["4 matching sentences in 4 items in items 1-30: 7, 14, 21, 28"])
        self.assertEqual(self.run_cli("--where", "abcd12", "--after", "55"),
                         ["6 matching sentences in 6 items in items 55 onward: 55-60"])

    def test_item_and_missing(self):
        self.assertEqual(self.run_cli("--item", "7")[0], "ITEM 7 (archived)")
        self.assertIn("is not in the archive (archived: 1-60)", self.run_cli("--item", "99")[0])
        self.assertIn("no archived sentence matches", self.run_cli("zzzz99", "--before", "10")[0])

    def test_bad_regex_falls_back_to_plain_text(self):
        self.assertIn("no archived sentence matches", self.run_cli("gate (")[0])

    def test_ranges(self):
        self.assertEqual(self.mod.ranges([1, 2, 3, 7, 9, 10]), "1-3, 7, 9-10")


if __name__ == "__main__":
    unittest.main()
