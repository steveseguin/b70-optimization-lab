import unittest
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


if __name__ == "__main__":
    unittest.main()
