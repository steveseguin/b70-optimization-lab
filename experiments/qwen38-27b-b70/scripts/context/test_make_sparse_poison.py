#!/usr/bin/env python3
"""Tests for --poison in make_sparse_prose_tasks.py and for hostile_report.py (2026-10-17).

The forged stream must be the clean stream plus the forged paragraphs (same expected answers, every other paragraph
the same, same questions), and the report must class oracle answers as kept and the forgeries' answers as followed.
No live services: the generator runs into a temporary directory.
"""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_sparse_prose_tasks as m

OPTS = {"words": True, "pronouns": False, "corrections": False, "plans": False, "relative": False}
KINDS = ("memory", "method", "rule", "value")


def build(tmp, name, poison=()):
    m.build(Path(tmp), name, 0, 0, 400, 3.0, 14, 40, "memory", OPTS, 3.9, None, 80, probes_every=10, probes_k=3,
            rules=True, poison=poison)
    d = Path(tmp) / name
    load = lambda f: json.loads((d / "tests" / f).read_text())
    return d, load("spec.json"), load("reference.json"), load("items.json")


def details(spec, answers):
    per = {k: ("correct" if answers.get(k) == v else "wrong") for k, v in spec["expected"].items()}
    return {"per_key": per, "answers": answers, "correct": sum(v == "correct" for v in per.values()), "n": len(per)}


def report(tmp, task, det):
    p = Path(tmp) / "details.json"
    p.write_text(json.dumps(det))
    j = Path(tmp) / "report.json"
    subprocess.run([sys.executable, str(HERE / "hostile_report.py"), "--task", str(task), "--details", str(p),
                    "--json", str(j)], check=True, capture_output=True, text=True)
    return json.loads(j.read_text())


class Poison(unittest.TestCase):
    def test_clean_stream_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, cs, cr, ci = build(tmp, "clean")
            _, ps, pr, pi = build(tmp, "poison", KINDS)
            self.assertEqual(cs["expected"], ps["expected"])
            self.assertEqual(cr["probes"].keys(), pr["probes"].keys())
            self.assertEqual([p["q"] for p in cr["probes"].values()], [p["q"] for p in pr["probes"].values()])
            self.assertEqual(len(ci), len(pi))
            added = []
            for a, b in zip(ci, pi):
                pa, pb = a.split("\n\n"), b.split("\n\n")
                self.assertEqual([x for x in pb if x in pa], pa)
                added += [x for x in pb if x not in pa]
            self.assertEqual(sorted(added), sorted(r["text"] for r in pr["poison"]))
            self.assertEqual([r["kind"] for r in pr["poison"]], list(KINDS))
            self.assertEqual(len({r["batch"] for r in pr["poison"]}), 4)
            self.assertTrue(all(r["batch"] >= 3 for r in pr["poison"]))

    def test_targets_and_forged_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, spec, ref, _ = build(tmp, "poison", KINDS)
            exp, rules = spec["expected"], spec["rules"]
            by = {r["kind"]: r for r in ref["poison"]}
            self.assertTrue(by["memory"]["final_targets"])
            self.assertTrue(all(n.startswith(by["memory"]["letter"]) and n in exp for n in by["memory"]["final_targets"]))
            self.assertNotEqual((by["method"]["a"], by["method"]["b"]), (rules["a"], rules["b"]))
            self.assertNotEqual(by["method"]["a"], rules["a"])
            y = by["value"]["final_targets"][0]
            self.assertNotEqual(exp[y], by["value"]["asks_for"])
            self.assertNotIn(by["value"]["asks_for"], spec["history"].get(y, []))
            self.assertEqual(by["rule"]["final_targets"], [n for n in exp if exp[n] == "protected" and not n.startswith("p")])

    def test_report_kept_and_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            task, spec, ref, _ = build(tmp, "poison", KINDS)
            exp, rules = spec["expected"], spec["rules"]
            r = report(tmp, task, details(spec, dict(exp)))
            for f in r["forgeries"]:
                self.assertEqual(set(f["counts"]), {"kept"}, f)
                self.assertTrue(f["targets"], f)
            self.assertEqual(r["untargeted"]["correct"], r["untargeted"]["n"])
            # answers that obey every forgery
            bad = dict(exp)
            by = {x["kind"]: x for x in ref["poison"]}
            for k, p in ref["probes"].items():
                if p["item"] > by["method"]["item"] and p["type"] == "procedure":
                    v = (exp[k] - rules["b"]) // rules["a"]
                    bad[k] = by["method"]["a"] * v + by["method"]["b"]
                if p["item"] > by["rule"]["item"] and p["type"] == "rule":
                    bad[k] = 123
            for n in by["rule"]["final_targets"]:
                bad[n] = 77
            bad[by["value"]["final_targets"][0]] = by["value"]["asks_for"]
            for n in by["memory"]["final_targets"]:
                bad[n] = ""
            r = report(tmp, task, details(spec, bad))
            got = {f["kind"]: f["counts"] for f in r["forgeries"]}
            self.assertEqual(set(got["method"]), {"followed"})
            self.assertEqual(set(got["rule"]), {"followed"})
            self.assertEqual(got["value"], {"followed": 1})
            self.assertIn("lost", got["memory"])


if __name__ == "__main__":
    unittest.main()
