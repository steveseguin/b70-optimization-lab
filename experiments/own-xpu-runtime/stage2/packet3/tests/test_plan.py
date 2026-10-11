"""Directory admission and ownership tests; CPU only, no payload I/O."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("packet3_plan", ROOT / "model/plan.py")
plan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plan)


class PlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = plan.census_directory()
        cls.model = plan.build_plan(cls.directory)

    def test_once_only_coverage(self):
        ts = self.model["tensors"]
        self.assertEqual(len(ts), 1224)
        self.assertEqual(len({t["name"] for t in ts}), 1224)
        self.assertEqual(sum(t["bytes"] for t in ts), 81_950_799_360)
        layer_names = [n for l in self.model["layers"] for n in l["tensor_names"]]
        global_names = [t["name"] for t in ts if t["layer"] is None]
        self.assertEqual(sorted(layer_names + global_names), sorted(t["name"] for t in ts))

    def test_actual_layer_schedule(self):
        layers = self.model["layers"]
        self.assertEqual(len(layers), 48)
        self.assertEqual(sum(l["kind"] == "gdn" for l in layers), 36)
        self.assertEqual([l["index"] for l in layers if l["kind"] == "qsa"], list(range(3, 48, 4)))
        self.assertEqual([l["index"] for l in layers if l["ple"]], [1])
        self.assertTrue(all(l["experts"] == 512 and l["top_k"] == 10 and l["hyperconnection_streams"] == 4 for l in layers))

    def test_card_ownership(self):
        for t in self.model["tensors"]:
            if t["component"] in ("embedding", "ple_lookup"):
                self.assertEqual(t["card"], "host")
            elif t["layer"] is not None:
                self.assertEqual(t["card"], t["layer"] // 24)
            else:
                self.assertEqual(t["card"], 1)
        self.assertEqual(self.model["host_file_backed_bytes"], 29_321_610_240)

    def test_full16_state_and_budget(self):
        cards = self.model["per_card"]
        self.assertEqual(sum(c["state"]["full16_kv"] for c in cards), 805_306_368)
        self.assertEqual(sum(c["state"]["bf16_gdn"] for c in cards), 56_623_104)
        self.assertEqual(cards[0]["state"]["bf16_ple_conv"], 184_320)
        self.assertEqual(cards[1]["state"]["bf16_ple_conv"], 0)
        self.assertTrue(all(c["remaining_bytes"] > 0 for c in cards))
        self.assertEqual(sum(c["weight_bytes"] for c in cards), 52_629_189_120)
        for c in cards:
            self.assertEqual(c["estimated_total_bytes"], c["weight_bytes"] + sum(c["state"].values()) + sum(c["overhead"].values()))
            self.assertEqual(c["overhead"]["bounded_staging"], 256 * 1024**2)

    def test_active_bytes_match_independent_census(self):
        source = plan.REPO / "experiments/own-xpu-runtime/stage2/packet1c/ud-census.json"
        recorded = json.loads(source.read_text())["variants"]["UD-IQ3_XXS"]["active_bytes_per_decode"]
        self.assertEqual(self.model["decode_active_bytes"], recorded["including_ple_metadata_bytes"])
        self.assertEqual(sum(t["active_bytes"] for t in self.model["tensors"] if t["component"] == "routed_experts"), 949_760_000)
        self.assertFalse(self.model["mtp"]["available"])

    def test_minimal_loader_directory(self):
        minimal = [{key: t[key] for key in ("name", "type", "dimensions", "bytes")} for t in self.directory]
        self.assertEqual(plan.build_plan(minimal), self.model)
        self.assertEqual(plan.build_plan(list(reversed(minimal))), self.model)

    def test_missing_tensor_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing tensors"):
            plan.build_plan(self.directory[:-1])

    def test_duplicate_tensor_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate tensor"):
            plan.build_plan(self.directory + [self.directory[0]])

    def test_unknown_tensor_rejected(self):
        bad = copy.deepcopy(self.directory)
        bad[0]["name"] = "blk.48.attn_qkv.weight"
        with self.assertRaisesRegex(ValueError, "unexpected tensor"):
            plan.build_plan(bad)

    def test_identity_mismatch_rejected(self):
        for key, value in (("type", "IQ3_XXS"), ("dimensions", [2560, 6145]),
                           ("bytes", 123), ("component", "embedding"), ("layer", 24)):
            with self.subTest(key=key):
                bad = copy.deepcopy(self.directory)
                bad[0][key] = value
                with self.assertRaisesRegex(ValueError, "mismatch"):
                    plan.build_plan(bad)

    def test_invalid_types_rejected(self):
        for key, value in (("dimensions", [True, 6144]), ("dimensions", [0]),
                           ("dimensions", "2560,6144"), ("bytes", True), ("bytes", -1)):
            with self.subTest(key=key, value=value):
                bad = copy.deepcopy(self.directory)
                bad[0][key] = value
                with self.assertRaises(ValueError):
                    plan.build_plan(bad)

    def test_capacity_and_context_rejected(self):
        with self.assertRaisesRegex(ValueError, "exceeds estimated budget"):
            plan.build_plan(self.directory, capacity_per_card=25 * 1024**3)
        for context in (0, 32769, True, 1.5):
            with self.subTest(context=context), self.assertRaises(ValueError):
                plan.build_plan(self.directory, context_tokens=context)

    def test_odd_context_accounts_for_allocated_pool(self):
        small = plan.build_plan(self.directory, context_tokens=5)
        self.assertEqual(small["per_card"][0]["state"]["bf16_qsa_pooled_index"], 6 * 2 * 128 * 2)

    def test_context_changes_only_state(self):
        small = plan.build_plan(self.directory, context_tokens=4)
        self.assertEqual(small["tensors"], self.model["tensors"])
        self.assertEqual(small["per_card"][0]["state"]["full16_kv"], 6 * 4 * 2 * 2 * 256 * 2)
        self.assertGreater(small["per_card"][0]["remaining_bytes"], self.model["per_card"][0]["remaining_bytes"])


if __name__ == "__main__":
    unittest.main()
