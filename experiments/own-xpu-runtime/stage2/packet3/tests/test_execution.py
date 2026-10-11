"""Independent CPU oracle and immutable launch-plan checks. No device imports."""
import json
import os
from pathlib import Path
import subprocess
import unittest
import numpy as np
import reference

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"


def execute(*args):
    return subprocess.check_output([str(BUILD / "step"), *args], text=True)


class ExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = json.loads(execute("record", str(BUILD / "directory.txt")))
        cls.tiny = json.loads(execute())

    def test_tiny_independent_numpy_all_buffers(self):
        expected = reference.run(False)
        self.assertEqual(set(self.tiny), set(expected))
        for name, data in expected.items():
            with self.subTest(buffer=name):
                np.testing.assert_array_equal(np.asarray(self.tiny[name], dtype=np.uint32), data.ravel().view(np.uint32))

    def test_real_layer_independent_numpy_all_buffers(self):
        actual = json.loads(execute("real"))
        expected = reference.run(True)
        self.assertEqual(set(actual), set(expected))
        for name, data in expected.items():
            with self.subTest(buffer=name):
                np.testing.assert_array_equal(np.asarray(actual[name], dtype=np.uint32), data.ravel().view(np.uint32))

    def test_fresh_process_repeats(self):
        self.assertEqual(self.tiny, json.loads(execute()))
        self.assertEqual(execute("real"), execute("real"))

    def test_weight_bytes_exact_census(self):
        self.assertEqual(self.record["weight_bytes"], 4_951_240_940)
        launches = self.record["launches"]
        self.assertEqual(sum(l["weight_bytes"] for l in launches if l["op"] == "routed_gemv"), 949_760_000)
        names = [n for l in launches for n in l["weights"]]
        self.assertEqual(len(names), 1224)
        self.assertEqual(len(set(names)), 1224)

    def test_launch_count_and_order(self):
        ls = self.record["launches"]
        self.assertEqual(self.record["launch_count"], 1873)
        self.assertEqual(sum(l["op"] == "gdn" for l in ls), 36)
        self.assertEqual(sum(l["op"] == "qsa_attention" for l in ls), 12)
        self.assertEqual(sum(l["op"] == "routed_gemv" for l in ls), 144)
        self.assertEqual(sum(l["op"] == "check_status" for l in ls), 144)
        self.assertEqual([l["op"] for l in ls[-4:]], ["argmax", "handoff_result", "commit", "commit"])
        for i in range(48):
            prefix = f"blk.{i}."
            layer = [l for l in ls if l["label"].startswith(prefix)]
            ops = [l["op"] for l in layer]
            self.assertLess(ops.index("route"), ops.index("expert_gather"))
            self.assertLess(ops.index("expert_gather"), ops.index("routed_gemv"))
            self.assertEqual(ops[-1], "hc_combine")
            self.assertTrue(all(l["card"] == i // 24 for l in layer))

    def test_record_contains_shapes_extents_and_no_payload(self):
        for l in self.record["launches"]:
            self.assertTrue(l["shape"])
            self.assertTrue(all(d > 0 for d in l["shape"]))
            self.assertGreaterEqual(l["weight_bytes"], 0)
            self.assertGreater(l["write_bytes"], 0)
        self.assertEqual(sum(l["op"] == "handoff" for l in self.record["launches"]), 1)

    def test_integer_abi_and_cross_card_ownership(self):
        buffers = {b["name"]: b for b in self.record["buffers"]}
        self.assertEqual(buffers["token"]["scalar"], 2)  # I32
        self.assertEqual(buffers["blk.0.routes"]["scalar"], 3)  # U32 triples
        self.assertEqual(buffers["blk.1.ple.ids"]["element_bytes"], 8)
        self.assertEqual(buffers["ple_metadata"]["element_bytes"], 8)
        self.assertEqual(buffers["streams"]["card"], -1)  # distinct rank allocations
        self.assertEqual(buffers["blk.24.gdn.state"]["card"], 1)
        transfers = [l for l in self.record["launches"] if l["source_card"] != -1]
        self.assertEqual([(l["source_card"], l["card"]) for l in transfers], [(0, 1), (1, 0)])
        self.assertTrue(all(l["parameter"] == 0 for l in self.record["launches"] if l["op"] == "norm"))
        self.assertTrue(all(l["parameter"] == -1 for l in self.record["launches"] if l["op"] == "gdn"))

    def test_malformed_cpp_directory_rejected(self):
        original = (BUILD / "directory.txt").read_text()
        first = original.splitlines()[0]
        fields = first.split()
        mutations = [original + first + "\n", original.replace(first, first.replace(fields[1], "UNKNOWN"), 1),
                     original.replace(first, first.replace(fields[3], "1"), 1),
                     "\n".join(original.splitlines()[1:]) + "\n"]
        for i, text in enumerate(mutations):
            path = BUILD / f"invalid-{i}.txt"
            path.write_text(text)
            result = subprocess.run([str(BUILD / "step"), "record", str(path)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)

    def test_cpp_adversarial_checks(self):
        text = subprocess.check_output([str(BUILD / "host-tests")], text=True)
        self.assertIn("passed 18", text)


if __name__ == "__main__":
    unittest.main()
