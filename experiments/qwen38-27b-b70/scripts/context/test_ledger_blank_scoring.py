#!/usr/bin/env python3
"""Offline stdlib scoring regression tests for the sibling task generator.

Use --source-dir DIR or B70_CONTEXT_SOURCE_DIR=DIR to test another source snapshot.

No live services, model code, tokenizer setup, whole-filesystem scan, or dependencies.
The real generator writes task files into an isolated temporary directory. We execute
only the exact emitted grader prefix, before the unrelated container file scanner.
"""
from pathlib import Path
import argparse
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
options = argparse.ArgumentParser(add_help=False)
options.add_argument("--source-dir", default=os.environ.get("B70_CONTEXT_SOURCE_DIR"))
selection, test_args = options.parse_known_args()
sys.argv = sys.argv[:1] + test_args
SOURCE_DIR = (Path(selection.source_dir).resolve() if selection.source_dir
              else Path(__file__).resolve().parent)
GENERATOR = SOURCE_DIR / "make_kvstream_tasks.py"
BASE_LEDGER = SOURCE_DIR / "make_ledger_tasks.py"
SUMMARY = SOURCE_DIR / "summarize_results.py"

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

kv = load_module("make_kvstream_tasks", GENERATOR)
ledger = load_module("review_ledger", BASE_LEDGER)
summary = load_module("review_summary", SUMMARY)

def grade(spec, answers, source=None):
    code = (source or kv.GRADE_PY_V2).split("# ---- files created or changed after the image build")[0]
    def fake_open(path, *args, **kwargs):
        allowed = {"/tests/spec.json": spec, "/app/answers.json": answers}
        return io.StringIO(json.dumps(allowed[path]))
    scope = {"open": fake_open}
    exec(compile(code, "emitted grade.py scoring prefix", "exec"), scope)
    return {k: scope[k] for k in ("counts", "score", "status")}

def ledger_spec(expected):
    return {"kind": "ledger", "mode": "memory", "expected": expected, "history": {"live10": [3, 5]}}

class OfflineCount:
    kind = "review-only chars/2.5; fixed batch count, not measured model tokens"
    def __call__(self, text):
        return int(len(text) / 2.5)

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))

class ScoringRegression(unittest.TestCase):
    def test_deleted_blank_strings_are_admitted_losses(self):
        for blank in ("", " ", "\t\n"):
            with self.subTest(blank=repr(blank)):
                result = grade(ledger_spec({"gone10": None}), {"gone10": blank})
                self.assertEqual(result["status"]["gone10"], "blank")
                self.assertEqual(result["score"], 0)

    def test_legitimate_deleted_representations_remain_correct(self):
        for deleted in (None, "null", " NULL ", "none", "None", "deleted", " Deleted ", "del", "DEL"):
            with self.subTest(deleted=deleted):
                result = grade(ledger_spec({"gone10": None}), {"gone10": deleted})
                self.assertEqual(result["status"]["gone10"], "correct")
                self.assertEqual(result["score"], 1)

    def test_missing_answers_stay_blank(self):
        result = grade(ledger_spec({"gone10": None, "live10": 7}), {})
        self.assertEqual(result["counts"], {"correct": 0, "blank": 2, "wrong": 0, "stale": 0})

    def test_live_integer_and_stale_controls(self):
        for answer, status in [(7, "correct"), (7.0, "correct"), (" +7 ", "correct"),
                               ("", "blank"), (" \t", "blank"), (3, "stale"),
                               (True, "wrong"), (None, "wrong"), (7.2, "wrong"), ("DEL", "wrong")]:
            with self.subTest(answer=answer):
                result = grade(ledger_spec({"live10": 7}), {"live10": answer})
                self.assertEqual(result["status"]["live10"], status)

    def test_deleted_non_deletion_controls(self):
        for answer in (0, 7, False, {}, [], "missing", "0"):
            with self.subTest(answer=answer):
                result = grade(ledger_spec({"gone10": None}), {"gone10": answer})
                self.assertEqual(result["status"]["gone10"], "wrong")

    def test_kv_non_ledger_branch_unchanged(self):
        spec = {"kind": "kv", "mode": "memory", "expected": {"key": "alpha beta"}, "history": {"key": ["old value"]}}
        for answer, status in [("alpha beta", "correct"), (" alpha   beta ", "correct"),
                               ("", "blank"), ("\t", "blank"), (None, "blank"),
                               ("old value", "stale"), ("deleted", "wrong"), ("null", "wrong")]:
            with self.subTest(answer=answer):
                self.assertEqual(grade(spec, {"key": answer})["status"]["key"], status)

    def test_actual_generator_and_summary_path_seed_0_and_1(self):
        # Current default ledger batch/counter/query parameters, bounded to 20 batches.
        # The count fallback is explicit; these are fixtures, not reconstructed lab artifacts.
        with tempfile.TemporaryDirectory(prefix="b70-fixed-score-") as temp:
            root = Path(temp)
            for seed in (0, 1):
                with self.subTest(seed=seed):
                    name = f"ledger-memory-t120k-s{seed}"
                    ledger.build(root / "tasks", name, 120000, seed, 136, 24, 160, "memory", OfflineCount(), n_batches=20)
                    task = root / "tasks" / name
                    spec = json.loads((task / "tests/spec.json").read_text())
                    emitted = (task / "tests/grade.py").read_text()
                    self.assertEqual(emitted, kv.GRADE_PY_V2)
                    instruction = (task / "instruction.md").read_text()
                    self.assertIn('null if the counter is deleted', instruction)
                    self.assertIn('If you no longer know a value, map it to ""', instruction)
                    self.assertEqual(len(spec["expected"]), 24)
                    self.assertEqual(sum(v is None for v in spec["expected"].values()), 3)
                    self.assertEqual(grade(spec, spec["expected"], emitted)["score"], 1)
                    self.assertEqual(grade(spec, {}, emitted)["score"], 0)
                    result = grade(spec, dict.fromkeys(spec["expected"], ""), emitted)
                    trial = root / f"B32__{name}" / "trial"
                    dump(trial / "config.json", {"task": {"path": str(task)}})
                    dump(trial / "agent/trajectory.json", [{"role": "tool", "content": summary.SUBMIT}])
                    dump(trial / "result.json", {"task_name": name, "verifier_result": {"rewards": {"reward": result["score"]}}})
                    dump(trial / "verifier/details.json", {"counts": result["counts"], "per_key": result["status"], "score_raw": result["score"], "void": False})
                    row = summary.trial_row(trial)
                    self.assertEqual(row["ended_by"], "submit")
                    self.assertFalse(row["invalid"])
                    self.assertEqual(row["rule"], "ok")
                    self.assertEqual(row["mode"], "memory")
                    self.assertEqual(row["kind"], "ledger")
                    self.assertEqual(row["reward"], 0)
                    self.assertEqual(row["correct"], 0)
                    self.assertEqual(row["blank"], 24)

if __name__ == "__main__":
    print(f"Generator under test: {GENERATOR}", flush=True)
    unittest.main(verbosity=2)
