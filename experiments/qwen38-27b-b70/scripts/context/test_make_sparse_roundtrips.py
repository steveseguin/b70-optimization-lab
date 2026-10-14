#!/usr/bin/env python3
"""Regression tests for --roundtrips in make_sparse_prose_tasks.py (the campaign-18 adversarial decoy).

A decoy is: a quiet SET to a new value, then a loss of k and an equal give-back far apart, with the
counter untouched between the three events, and the counter present in the final query. The reference
ledger must stay exact and the layout deterministic.

No live services or dependencies: the generator runs into a temporary directory.
"""
from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_sparse_prose_tasks as m

OPTS = {k: True for k in ("words", "pronouns", "corrections", "plans", "relative")}


def build(tmp, seed=0, roundtrips=4, n_batches=80):
    return m.build(Path(tmp), f"sparse-notes-b{n_batches}-s{seed}", 0, seed, 400, 3.0, 12, 40, "notes",
                   OPTS, 3.9, None, n_batches, surprise=4, probes_every=10, probes_k=3,
                   rules=True, class_rule=True, roundtrips=roundtrips)


def load(tmp, n_batches=80, seed=0):
    d = Path(tmp) / f"sparse-notes-b{n_batches}-s{seed}"
    spec = json.loads((d / "tests" / "spec.json").read_text())
    ref = json.loads((d / "tests" / "reference.json").read_text())
    meta = json.loads((d / "tests" / "metadata.json").read_text()) if (d / "tests" / "metadata.json").exists() else None
    return d, spec, ref, meta


class Roundtrips(unittest.TestCase):
    def test_structure_and_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(tmp)
            d, spec, ref, _ = load(tmp)
            trips = ref.get("roundtrips") or {}
            self.assertEqual(len(trips), 4, f"expected 4 placed decoys, got {trips}")
            protected = set((spec.get("rules") or {}).get("protected") or [])
            refs = ref["after_batch"]
            for nm, (b1, b3) in trips.items():
                self.assertLess(b1, b3)
                # the decoy counter is in the final query (unless the standing rule protects it)
                if nm not in protected:
                    self.assertIn(nm, spec["expected"], f"decoy {nm} missing from the final query")
                # ops touching nm between b1 and b3: exactly the three decoy events, in order
                ops = [(bi, o) for bi in range(b1, b3 + 1) for o in refs[bi - 1]["ops"] if o[0] == nm]
                self.assertEqual(len(ops), 3, f"{nm}: ops in window: {ops}")
                (i1, o1), (i2, o2), (i3, o3) = ops
                self.assertEqual((i1, o1[1]), (b1, "set"))
                self.assertEqual(o2[1], "add")
                self.assertEqual(o3[1], "add")
                self.assertEqual(o2[2], -o3[2], f"{nm}: pair not net-zero: {o2} vs {o3}")
                w = o1[2]
                self.assertEqual(o1[3], w)                    # state after the quiet set
                self.assertEqual(o2[3], w + o2[2])            # after the loss
                self.assertEqual(o3[3], w)                    # after the give-back: back to the set value
                self.assertEqual(refs[b3 - 1]["state"][nm], w)
                self.assertEqual(spec["expected"][nm], w if not (w < 0) else "overdrawn")

    def test_reserved_window_not_disturbed(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(tmp, roundtrips=8)
            _, _, ref, _ = load(tmp)
            refs = ref["after_batch"]
            for nm, (b1, b3) in (ref.get("roundtrips") or {}).items():
                n_ops = sum(1 for bi in range(b1, b3 + 1) for o in refs[bi - 1]["ops"] if o[0] == nm)
                self.assertEqual(n_ops, 3, f"{nm} disturbed inside its window")
            self.assertEqual(len(ref.get("roundtrips") or {}), 8)

    def test_deterministic(self):
        with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
            build(t1)
            build(t2)
            _, spec1, ref1, _ = load(t1)
            _, spec2, ref2, _ = load(t2)
            self.assertEqual(ref1["roundtrips"], ref2["roundtrips"])
            self.assertEqual(spec1["expected"], spec2["expected"])
            self.assertEqual(ref1["after_batch"], ref2["after_batch"])

    def test_off_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(tmp, roundtrips=0)
            _, _, ref, _ = load(tmp)
            self.assertEqual(ref.get("roundtrips"), {})


if __name__ == "__main__":
    unittest.main()
