#!/usr/bin/env python3
"""Tests for --retro / --retro-loud in make_sparse_prose_tasks.py (2026-10-17): audits that reverse an entry from far
back. The quiet and loud streams must share the ledger, questions and answers and differ only in the audit sentences;
each audit must name an entry that is its counter's only change in that item, at least 30 batches back; the counter
must be untouched by random changes from its opening on and be in the final query at the reversed value.
No live services: the generator runs into a temporary directory.
"""
from pathlib import Path
import json
import re
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_sparse_prose_tasks as m

OPTS = {"words": True, "pronouns": False, "corrections": False, "plans": False, "relative": False}


def build(tmp, name, loud=False, retro=6, seed=0):
    m.build(Path(tmp), name, 0, seed, 400, 3.0, 14, 40, "memory", OPTS, 3.9, None, 120, probes_every=10, probes_k=3,
            rules=True, retro=retro, retro_loud=loud)
    d = Path(tmp) / name
    load = lambda f: json.loads((d / "tests" / f).read_text())
    return load("spec.json"), load("reference.json"), load("items.json"), (d / "instruction.md").read_text()


class Retro(unittest.TestCase):
    def test_loud_and_quiet_differ_only_in_wording(self):
        with tempfile.TemporaryDirectory() as tmp:
            sq, rq, iq, nq = build(tmp, "quiet")
            sl, rl, il, nl = build(tmp, "loud", loud=True)
            self.assertEqual(sq["expected"], sl["expected"])
            self.assertEqual(rq["after_batch"], rl["after_batch"])
            self.assertEqual([p["q"] for p in rq["probes"].values()], [p["q"] for p in rl["probes"].values()])
            self.assertTrue(rq["retro"])
            self.assertEqual(rq["retro"], rl["retro"])
            audit_items = {r["item"] for r in rq["retro"]}
            for n, (a, b) in enumerate(zip(iq, il), 1):
                if n not in audit_items:
                    self.assertEqual(a, b, f"item {n} differs")
                else:
                    strip = lambda t: re.sub(r" by \d+ entered", " entered", t)
                    self.assertEqual(strip(b), a)
            self.assertIn("but not the amount", nq)
            self.assertIn("and the amount", nl)

    def test_audits(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec, ref, items, _ = build(tmp, "quiet", seed=1)
            refs, exp = ref["after_batch"], spec["expected"]
            self.assertGreaterEqual(len(ref["retro"]), 3)
            for r in ref["retro"]:
                nm, i, b = r["counter"], r["entry_batch"], r["batch"]
                self.assertGreaterEqual(b - i, 30)
                mine = [o for o in refs[i - 1]["ops"] if o[0] == nm]
                self.assertEqual(len(mine), 1)
                self.assertEqual((mine[0][1], mine[0][2]), ("add", r["amount"]))
                self.assertEqual(refs[b - 1]["state"][nm], r["after"])
                self.assertEqual(r["after"], r["before"] - r["amount"])
                self.assertIn(f"item {r['entry_item']} was a mistake", items[r["item"] - 1])
                self.assertEqual(ref["item_no"][str(i)], r["entry_item"])
                # untouched after the audit; in the final query at the audited value
                self.assertFalse([o for bb in range(b, len(refs)) for o in refs[bb]["ops"] if o[0] == nm])
                if nm not in (spec["rules"] or {}).get("protected", []):
                    self.assertEqual(exp[nm], r["after"])

    def test_off_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, ref, _, nq = build(tmp, "none", retro=0)
            self.assertNotIn("retro", ref)
            self.assertNotIn("An audit may reverse", nq)


if __name__ == "__main__":
    unittest.main()
