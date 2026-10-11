"""CPU-only checks of partial_grade.py (grading a cut run's answers snapshot); no model or device calls."""
import json
from pathlib import Path
import tempfile
import unittest

import partial_grade as pg


def task(tmp: Path) -> Path:
    (tmp / "tests").mkdir(parents=True)
    probes = {"p1_1": {"type": "current", "distance": 3, "item": 10}, "p1_2": {"type": "who", "distance": 30, "item": 10},
              "p2_1": {"type": "rule", "distance": 120, "item": 20}, "p2_2": {"type": "old_value", "distance": 450, "item": 20},
              "p3_1": {"type": "current", "distance": 2, "item": 30}}
    expected = {"p1_1": 5, "p1_2": "the stable hand", "p2_1": "protected", "p2_2": -7, "p3_1": 9, "aaaa11": 4, "bbbb22": None}
    (tmp / "tests/spec.json").write_text(json.dumps({"kind": "sparse", "mode": "memory", "expected": expected,
                                                     "history": {"p2_2": [1, 2], "aaaa11": [3]}, "n_items": 40}))
    (tmp / "tests/reference.json").write_text(json.dumps({"probes": probes}))
    return tmp


class PartialGrade(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.task = task(Path(self.dir.name))

    def tearDown(self):
        self.dir.cleanup()

    def status(self, answers, final=False):
        g = pg.grade(self.task, answers, final)
        return g, {r["key"]: r["status"] for r in g["probes"]}

    def test_only_reached_probe_items_count(self):
        g, st = self.status({"p1_1": 5, "p2_1": "Protected"})
        self.assertEqual(g["probe_items_answered"], 2)
        self.assertEqual(st, {"p1_1": "correct", "p1_2": "blank", "p2_1": "correct", "p2_2": "blank"})
        self.assertEqual(g["last_item"], 20)

    def test_statuses_follow_the_task_grader(self):
        _, st = self.status({"p1_1": "5", "p1_2": "Stable hand.", "p2_1": 12, "p2_2": 2, "p3_1": ""})
        self.assertEqual(st, {"p1_1": "correct", "p1_2": "correct", "p2_1": "wrong", "p2_2": "stale", "p3_1": "blank"})

    def test_bins(self):
        g, _ = self.status({"p3_1": 9})
        self.assertEqual({r["key"]: r["bin"] for r in g["probes"]},
                         {"p1_1": "d1-4", "p1_2": "d25-99", "p2_1": "d100-399", "p2_2": "d400+", "p3_1": "d1-4"})

    def test_final_keys_only_on_request(self):
        g, _ = self.status({"aaaa11": 3, "bbbb22": None})
        self.assertNotIn("final", g)
        g, _ = self.status({"aaaa11": 3, "bbbb22": None}, final=True)
        self.assertEqual(g["final"], {"correct": 1, "blank": 0, "wrong": 0, "stale": 1, "n": 2})

    def test_empty_answers(self):
        g, st = self.status({})
        self.assertEqual((g["probe_items_answered"], st), (0, {}))


if __name__ == "__main__":
    unittest.main()
