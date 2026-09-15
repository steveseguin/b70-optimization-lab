from array import array
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import analyze
from analyze import paired_latency


def timings(candidate=(90, 90, 90, 90, 90), scale=1):
    result = []
    for block in range(5):
        order = ["xccl", "candidate", "candidate", "xccl"] if block % 2 == 0 else ["candidate", "xccl", "xccl", "candidate"]
        result.extend({"block": block, "arm": arm, "ns_per_call": scale * (100 if arm == "xccl" else candidate[block])} for arm in order)
    return result


class AnalysisTests(unittest.TestCase):
    def test_slowest_rank_controls_gate(self):
        # Rank0 alone improves 10%, rank1 regresses 10%; cannot hide slow peer.
        result = paired_latency([timings(), timings((110,) * 5)])
        self.assertFalse(result["operator_speed_gate"])
        self.assertAlmostEqual(result["median_relative_improvement"], -.1)

    def test_one_negative_block_is_inconclusive(self):
        result = paired_latency([timings((90, 90, 110, 90, 90))] * 2)
        self.assertEqual(result["positive_blocks"], 4)
        self.assertFalse(result["operator_speed_gate"])

    def test_five_percent_threshold(self):
        self.assertTrue(paired_latency([timings((95,) * 5)] * 2)["operator_speed_gate"])
        self.assertFalse(paired_latency([timings((96,) * 5)] * 2)["operator_speed_gate"])

    def test_reordered_or_missing_samples_rejected(self):
        with self.assertRaises(ValueError):
            paired_latency([timings()[:-1], timings()])
        rows = timings()
        rows[0]["arm"] = "candidate"
        with self.assertRaises(ValueError):
            paired_latency([rows, timings()])


def write_screen(d, differ=None):
    """One-row synthetic screen; differ=(kind, bits) replaces candidate element 7 on both ranks."""
    n = 5120
    for rank in (0, 1):
        records = []
        for kind in analyze.KINDS:
            for repeat in (0, 1):
                ref = array("H", [0x3c00] * n)
                ref[7] = 0x7e03
                cand = array("H", ref)
                if differ and differ[0] == kind:
                    cand[7] = differ[1]
                stem = f"rank{rank}-rows1-{kind}-{repeat}"
                (d / f"{stem}.candidate.bin").write_bytes(cand.tobytes())
                (d / f"{stem}.xccl.bin").write_bytes(ref.tobytes())
                records.append({"rows": 1, "kind": kind, "repeat": repeat, "exact": True, "input_unchanged": True,
                                "candidate_sha256": hashlib.sha256(cand.tobytes()).hexdigest(),
                                "xccl_sha256": hashlib.sha256(ref.tobytes()).hexdigest()})
        (d / f"rank{rank}-quality.json").write_text(json.dumps(records))
        (d / f"rank{rank}-DONE.json").write_text("{}")
        (d / f"rank{rank}-rows1-timing.json").write_text(json.dumps(timings()))


class NanRuleAnalysisTests(unittest.TestCase):
    def test_nan_payload_difference_passes_only_under_nan_class(self):
        with tempfile.TemporaryDirectory() as d:
            write_screen(Path(d), ("nan_matrix", 0xfe02))
            strict = analyze.analyze(Path(d), "bit-exact", shapes=(1,))
            self.assertFalse(strict["quality_passed"])
            relaxed = analyze.analyze(Path(d), "nan-class", shapes=(1,))
            self.assertTrue(relaxed["quality_passed"])
            self.assertEqual(relaxed["shapes"][0]["bit_exact_cases"], 2 * (2 * len(analyze.KINDS) - 2))
            self.assertEqual(relaxed["nan_rule"], "nan-class")

    def test_real_number_difference_fails_under_both_rules(self):
        with tempfile.TemporaryDirectory() as d:
            write_screen(Path(d), ("varied", 0x3c01))
            for rule in analyze.RULES:
                self.assertFalse(analyze.analyze(Path(d), rule, shapes=(1,))["quality_passed"])

    def test_unknown_rule_refused(self):
        with self.assertRaises(ValueError):
            analyze.analyze(Path("/nonexistent"), "loose")


if __name__ == "__main__":
    unittest.main()
