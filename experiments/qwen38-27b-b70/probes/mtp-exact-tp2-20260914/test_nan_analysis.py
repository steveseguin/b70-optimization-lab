from array import array
import hashlib
from itertools import combinations
import json
from pathlib import Path
import tempfile
import unittest

import nan_analysis as NA
import native


def tile(period, n):
    return (period * (n // NA.PERIOD + 1))[:n]


def rule_first_nan(first):
    """Synthetic: a NaN in the preferred operand wins, else the other NaN, else a finite surrogate."""
    def f(a, b):
        x, y = (a, b) if first == 0 else (b, a)
        if NA.is_nan(x):
            return x
        if NA.is_nan(y):
            return y
        return (a + b) & 0x7bff
    return f


def quieting(rule):
    return lambda a, b: (lambda r: r | 0x0200 if NA.is_nan(r) else r)(rule(a, b))


RULES = {"m0": rule_first_nan(0), "m1": rule_first_nan(1),
         "m2": quieting(rule_first_nan(0)), "m3": quieting(rule_first_nan(1))}


def positive_sign_rule(a, b):
    """Refutes all four synthetic modes: prefer a positive NaN, else rank-0."""
    if NA.is_nan(a) and NA.is_nan(b):
        return a if not a & 0x8000 else b
    return RULES["m0"](a, b)


def outputs_for(xccl_rule, shapes=NA.SHAPES, rules=RULES):
    period = {arm: array("H", (rule(a, b) for a, b in NA.PAIRS)) for arm, rule in dict(rules, xccl=xccl_rule).items()}
    return {r: {rows: {arm: tile(p, rows * NA.ELEMENTS_PER_ROW).tobytes() for arm, p in period.items()}
                for rows in shapes} for r in (0, 1)}


class NanAnalysisTests(unittest.TestCase):
    def test_fixture_covers_required_nan_classes_in_both_positions(self):
        self.assertEqual(NA.PERIOD, len(NA.BITS) ** 2)
        for rank in (0, 1):
            col = NA.column(rank, NA.PERIOD)
            self.assertEqual(list(col), [p[rank] for p in NA.PAIRS])
            nans = {b for b in col if NA.is_nan(b)}
            for sign in (0, 0x8000):
                signed = {b for b in nans if b & 0x8000 == sign}
                self.assertTrue(any(NA.is_quiet(b) for b in signed) and any(not NA.is_quiet(b) for b in signed))
                self.assertGreaterEqual(len({b & 0x03ff for b in signed}), 3)
        for bits in (0x7c00, 0xfc00, 0x0000, 0x8000, 0x3c00, 0xbc00, 0x7bff, 0x0001):
            self.assertIn(bits, NA.BITS)
        self.assertIn((0xfe02, 0x7e03), NA.PAIRS)
        self.assertIn((0x7e03, 0xfe02), NA.PAIRS)

    def test_mode_codes_match_native_abi(self):
        self.assertEqual(native.ADD_MODES, NA.MODE_CODES)

    def test_mismatch_count_collapse_equals_naive(self):
        n = 3 * NA.PERIOD + 17
        a = tile(array("H", (x for x, _ in NA.PAIRS)), n)
        b = array("H", a)
        for index in (0, 5, NA.PERIOD + 5, n - 1):
            b[index] ^= 1
        self.assertEqual(NA.mismatch_count(a.tobytes(), b.tobytes()), sum(x != y for x, y in zip(a, b)))
        self.assertEqual(NA.mismatch_count(a.tobytes(), a.tobytes()), 0)
        with self.assertRaises(ValueError):
            NA.mismatch_count(a.tobytes(), a.tobytes()[:-2])

    def test_selects_only_mode_matching_every_element_on_both_ranks(self):
        verdict = NA.evaluate(outputs_for(RULES["m1"]))
        self.assertEqual((verdict["status"], verdict["selected_mode"], verdict["matching_modes"]), ("selected", "m1", ["m1"]))
        self.assertTrue(all(v == 0 for r in verdict["mismatch_counts"]["m1"].values() for v in r.values()))
        self.assertGreater(verdict["mismatch_counts"]["m0"]["rank0"]["4096"], 0)
        json.dumps(verdict)

    def test_one_element_at_large_shape_on_one_rank_refutes_mode(self):
        outputs = outputs_for(RULES["m2"])
        # XCCL on BOTH ranks differs from m2 at one element; m2 stays equal to its own kernel.
        for r in (0, 1):
            raw = bytearray(outputs[r][4096]["xccl"])
            raw[2 * 3_000_001] ^= 1
            outputs[r][4096]["xccl"] = bytes(raw)
        verdict = NA.evaluate(outputs)
        self.assertIsNone(verdict["selected_mode"])
        self.assertEqual(verdict["status"], "no-single-formulation-matches")
        self.assertEqual(verdict["mismatch_counts"]["m2"]["rank1"]["4096"], 1)
        notes = verdict["distinguishing_table"]["position_dependent_refutations"]
        self.assertEqual([(x["mode"], x["rows"], x["element"]) for x in notes], [("m2", 4096, 3_000_001)])
        self.assertIn({"rank": 0, "rows": 4096, "arm": "xccl"}, verdict["position_dependent_outputs"])

    def test_no_single_formulation_gives_smallest_distinguishing_table(self):
        verdict = NA.evaluate(outputs_for(positive_sign_rule), shapes=(1, 2))
        self.assertEqual((verdict["status"], verdict["selected_mode"], verdict["matching_modes"]),
                         ("no-single-formulation-matches", None, []))
        rows = verdict["distinguishing_table"]["rows"]
        self.assertEqual(set().union(*(set(r["refutes"]) for r in rows)), set(NA.MODES))
        refute_sets = {frozenset(m for m in NA.MODES if any(row[f"{m}_rank{k}"] != row[f"xccl_rank{k}"] for k in (0, 1)))
                       for row in verdict["pair_table"]} - {frozenset()}
        minimum = next(size for size in range(1, 5) if any(set().union(*c) == set(NA.MODES) for c in combinations(refute_sets, size)))
        self.assertEqual(len(rows), minimum)
        for row in rows:
            self.assertTrue(all(k in row for k in ("rank0", "rank1", "xccl_rank0", "xccl_rank1", "m3_rank1")))

    def test_xccl_rank_disagreement_selects_nothing(self):
        outputs = outputs_for(RULES["m0"], shapes=(1, 2))
        outputs[1][2]["xccl"] = outputs_for(RULES["m1"], shapes=(2,))[1][2]["xccl"]
        verdict = NA.evaluate(outputs, shapes=(1, 2))
        self.assertEqual((verdict["status"], verdict["selected_mode"]), ("xccl-ranks-disagree", None))

    def test_multiple_matches_use_documented_preference(self):
        rules = dict(RULES, m2=RULES["m0"])
        verdict = NA.evaluate(outputs_for(RULES["m0"], shapes=(1,), rules=rules), shapes=(1,))
        self.assertEqual((verdict["selected_mode"], verdict["matching_modes"]), ("m0", ["m0", "m2"]))

    def test_missing_or_short_outputs_are_incomplete(self):
        outputs = outputs_for(RULES["m1"], shapes=(1, 2))
        del outputs[0][2]["m3"]
        outputs[1][1]["xccl"] = outputs[1][1]["xccl"][:-2]
        verdict = NA.evaluate(outputs, shapes=(1, 2))
        self.assertEqual((verdict["status"], verdict["selected_mode"]), ("incomplete", None))
        self.assertEqual(len(verdict["errors"]), 2)

    def test_class_mismatch_counts_only_non_nan_differences(self):
        a = array("H", [0x7e00, 0xfe02, 0x3c00, 0x7c00, 0x7e01])
        b = array("H", [0x7fff, 0x7e03, 0x3c00, 0x7c00, 0x3c00])
        self.assertEqual(NA.class_mismatch_count(a.tobytes(), b.tobytes()), 1)
        self.assertEqual(NA.mismatch_count(a.tobytes(), b.tobytes()), 3)
        c = array("H", b)
        c[2] = 0x3c01
        self.assertEqual(NA.class_mismatch_count(a.tobytes(), c.tobytes()), 2)

    def test_class_rule_selects_preferred_mode_when_xccl_nan_choice_moves(self):
        outputs = outputs_for(RULES["m1"])
        j = next(i for i, (a, b) in enumerate(NA.PAIRS)
                 if NA.is_nan(a) and NA.is_nan(b) and RULES["m0"](a, b) != RULES["m1"](a, b))
        element = j + NA.PERIOD * 100
        other = array("H", [RULES["m0"](*NA.PAIRS[j])]).tobytes()
        for r in (0, 1):
            raw = bytearray(outputs[r][4096]["xccl"])
            raw[2 * element:2 * element + 2] = other
            outputs[r][4096]["xccl"] = bytes(raw)
        self.assertEqual(NA.evaluate(outputs)["status"], "no-single-formulation-matches")
        verdict = NA.evaluate_class(outputs)
        self.assertEqual((verdict["status"], verdict["selected_mode"], verdict["rule"]), ("selected", "m0", "nan-class"))
        self.assertEqual(verdict["bit_exact_status"], "no-single-formulation-matches")
        json.dumps(verdict)

    def test_class_rule_still_refuses_non_nan_difference(self):
        outputs = outputs_for(RULES["m0"], shapes=(1,))
        j = NA.PAIRS.index((0x3c00, 0x3c00))
        for r in (0, 1):
            raw = bytearray(outputs[r][1]["xccl"])
            raw[2 * j] ^= 1
            outputs[r][1]["xccl"] = bytes(raw)
        verdict = NA.evaluate_class(outputs, shapes=(1,))
        self.assertEqual((verdict["status"], verdict["selected_mode"]), ("no-single-formulation-matches", None))

    def test_unknown_rule_refused(self):
        with self.assertRaises(ValueError):
            NA.analyze(Path("/nonexistent"), rule="loose")

    def write_run(self, directory, outputs, shapes, unchanged=True):
        for rank in (0, 1):
            receipt = {"status": "completed", "group_destroyed": True, "torch": "test", "library_sha256": "lib",
                       "add_mode_codes": NA.MODE_CODES, "shapes": {}}
            for rows in shapes:
                n = rows * NA.ELEMENTS_PER_ROW
                record = {"input_sha256": NA.sha(NA.column(rank, n).tobytes()),
                          "peer_input_sha256": NA.sha(NA.column(1 - rank, n).tobytes()),
                          "input_unchanged": {m: unchanged for m in NA.MODES}, "sha256": {}}
                for arm, raw in outputs[rank][rows].items():
                    (directory / f"rank{rank}-rows{rows}-{arm}.bin").write_bytes(raw)
                    record["sha256"][arm] = hashlib.sha256(raw).hexdigest()
                receipt["shapes"][str(rows)] = record
            (directory / f"rank{rank}-nan-semantics.json").write_text(json.dumps(receipt))

    def test_analyze_verifies_raw_hashes_inputs_and_lifetime(self):
        shapes = (1, 2)
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            self.write_run(d, outputs_for(RULES["m3"], shapes), shapes)
            self.assertEqual(NA.analyze(d, shapes)["selected_mode"], "m3")
            (d / "rank1-rows2-m3.bin").write_bytes(b"\0\0" * 10240)
            verdict = NA.analyze(d, shapes)
            self.assertEqual((verdict["status"], verdict["selected_mode"]), ("incomplete", None))
            self.assertIn("raw hash", verdict["errors"][0])
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            self.write_run(d, outputs_for(RULES["m3"], shapes), shapes, unchanged=False)
            self.assertEqual(NA.analyze(d, shapes)["status"], "incomplete")


if __name__ == "__main__":
    unittest.main()
