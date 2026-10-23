"""CPU metadata tests only; no Engine or model/native execution."""
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

P = Path(__file__).resolve().parents[1]
ROOT = P.parents[3]
BINARY = P / "build/binding-probe"
ENV = {"PATH": "/usr/bin:/bin", "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2"}


def read(path):
    return json.loads(path.read_text())


def invoke(*args, success=True):
    result = subprocess.run([str(BINARY), *map(str, args)], capture_output=True,
                            text=True, env=ENV, timeout=5, check=False)
    if success:
        if result.returncode:
            raise AssertionError(result.stderr)
        return json.loads(result.stdout)
    if result.returncode == 0:
        raise AssertionError("invalid contract input accepted")
    return result


def independent_ple(token, history, eos=248044):
    """Integer oracle from pinned host/device definition, independent Python widths."""
    a, b = history
    if b == eos:
        a = eos
    multipliers = [(1 << 63) - 19, (1 << 63) - 33, (1 << 63) - 57]
    ids = []
    for n in (2, 3):
        bits = (token * multipliers[0]) ^ (b * multipliers[1])
        if n == 3:
            bits ^= a * multipliers[2]
        bits &= (1 << 64) - 1
        signed = bits if bits < (1 << 63) else bits - (1 << 64)
        for j in range(8):
            i = (n - 2) * 8 + j
            ids.append(signed % (97 + 2 * i) + i * 1000)
    return ids


class AuthorityTests(unittest.TestCase):
    def test_exact_pinned_source_and_recorded_metadata(self):
        authority = read(P / "authority-inputs.json")
        for name, expected in authority["artifacts_sha256"].items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected)
        self.assertEqual(hashlib.sha256((P / "AUTHORITY.md").read_bytes()).hexdigest(),
                         authority["authority_note_sha256"])

    def test_recorded_pending_token_and_history_are_not_new_inference(self):
        fixture = read(P / "authority-inputs.json")["recorded_append"]
        state = read(ROOT / fixture["manifest"])["token_state"]
        tokens = list(map(int, (ROOT / fixture["input"]).read_text().split()))
        self.assertEqual(state["position"], 342)
        self.assertEqual(state["token_history"], [43164, 22843])
        self.assertEqual(state["next_token"], tokens[state["position"]])
        self.assertEqual(tokens[342:345], [37574, 248046, 198])
        self.assertEqual(len(tokens), 370)

    def test_compiled_metadata_probe_and_source_closure(self):
        receipt = read(P / "evidence/binding-cpu.json")
        self.assertIs(receipt["passed"], True)
        self.assertIs(receipt["native_executed"], False)
        self.assertIs(receipt["device_executed"], False)
        self.assertEqual(receipt["compile_returncode"], 0)
        self.assertEqual(hashlib.sha256(BINARY.read_bytes()).hexdigest(), receipt["binary_sha256"])
        for name, expected in receipt["source_sha256"].items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected)

    def test_actual_census_persistent_and_row_extents(self):
        census = read(ROOT / read(P / "authority-inputs.json")["recorded_census"])
        self.assertEqual(len(census), 1)
        live = {a["label"]: a["bytes"] for a in census[0]["allocations"] if a["live"]}
        persistent = {"token_history": 16, "blk.1.ple.history": 184320}
        for layer in range(48):
            base = f"blk.{layer}."
            if layer % 4 == 3:
                persistent.update({base + "qsa.keys": 4096 * 1024,
                                   base + "qsa.values": 4096 * 1024,
                                   base + "qsa.raw": 4096 * 256,
                                   base + "qsa.pooled": 1024 * 256})
            else:
                persistent.update({base + "gdn.history": 61440,
                                   base + "gdn.state": 1572864})
        self.assertEqual(len(persistent), 122)
        expected = dict(persistent, streams=20480, embedding=5120, token=4, position=4)
        expected.update({"blk.1.ple.ids": 128, "blk.1.ple.lookup": 5120,
                         "operator-scratch": 268435456})
        for name, size in expected.items():
            with self.subTest(name=name):
                self.assertEqual(live["card0:" + name], size)


class BindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not BINARY.is_file():
            raise AssertionError("Build the tiny p204 binding probe first")
        result = invoke("--self-test")
        if result["passed"] is not True:
            raise AssertionError("C++ binding checks failed")
        cls.checks = result["checks"]

    def require_checks(self, *names):
        for name in names:
            with self.subTest(name=name):
                self.assertIs(self.checks[name], True)

    def test_partial_alias_and_typed_extents(self):
        self.require_checks("partial_row_alias_refused", "row_shared_alias_refused",
                            "region_overflow_refused", "typed_alignment_refused")

    def test_persistent_state_and_row_lifetime(self):
        self.require_checks("short_state_refused", "missing_state_refused",
                            "row_streams_distinct", "persistent_inventory_122",
                            "duplicate_persistent_state_refused")

    def test_row_history_positions_and_final_prompt(self):
        self.require_checks("history_chain_refused", "position_gap_refused",
                            "final_prompt_row_refused", "capacity_crossing_refused",
                            "vocabulary_overflow_refused")

    def test_causal_order_routes_and_workspace_dependency(self):
        self.require_checks("row1_before_row0_refused", "concurrent_scratch_lease_refused",
                            "route_capture_before_consumer_refused", "missing_native_dependency_refused",
                            "terminal_before_dependency_refused")

    def test_no_partial_checkpoint_or_undrained_commit(self):
        self.require_checks("commit_before_layers_refused", "checkpoint_before_commit_refused",
                            "undrained_commit_refused", "cache_readers_live_refused")

    def test_fatal_error_and_exact_final_publication(self):
        self.require_checks("partial_failure_sticky", "device_error_poisons",
                            "commit_once_exact_history", "single_boundary_tail_commits")

    def test_integer_hash_wrap_and_recorded_append_histories(self):
        history = [43164, 22843]
        for token in (37574, 248046, 198):
            result = invoke("--history", token, *history, 248044)
            self.assertEqual(result["before"], history)
            self.assertEqual(result["ids"], independent_ple(token, history))
            history = [history[1], token]
            self.assertEqual(result["after"], history)

    def test_ple_eos_sentinel_does_not_rewrite_history(self):
        a = invoke("--history", 198, 37574, 248044, 248044)
        b = invoke("--history", 198, 248044, 248044, 248044)
        self.assertEqual(a["ids"], b["ids"])
        self.assertEqual(a["ids"], independent_ple(198, [37574, 248044]))
        self.assertEqual(a["before"], [37574, 248044])
        self.assertEqual(a["after"], [248044, 198])

    def test_im_end_is_not_ple_eos(self):
        a = invoke("--history", 198, 37574, 248046, 248044)
        b = invoke("--history", 198, 248044, 248046, 248044)
        self.assertEqual(a["ids"], independent_ple(198, [37574, 248046]))
        self.assertEqual(a["ids"][:8], b["ids"][:8])
        self.assertNotEqual(a["ids"][8:], b["ids"][8:])

    def test_planner_exact_nonfinal_cover_and_capacity_boundaries(self):
        for start, count in ((0, 1), (0, 2), (0, 66), (30, 35), (31, 35),
                             (32, 36), (342, 370), (4093, 4096)):
            with self.subTest(start=start, count=count):
                result = invoke("--plan", start, count, 4096, 2)
                positions = []
                for span in result["spans"]:
                    at, n = span["start"], span["count"]
                    self.assertIn(n, (1, 2))
                    self.assertFalse(span["final"])
                    self.assertEqual(at // 32, (at + n - 1) // 32)
                    positions.extend(range(at, at + n))
                self.assertEqual(positions, list(range(start, count - 1)))
                self.assertEqual(result["final_position"], count - 1)
        self.require_checks("context_extent_exact")

    def test_qsa_prefix_pool_and_launch_extent_are_separate(self):
        for position, context in ((0, 4096), (2, 4096), (3, 4096), (4, 4096),
                                  (30, 4096), (31, 4096), (32, 4096),
                                  (342, 4096), (2050, 4096), (4095, 4096), (34, 35)):
            with self.subTest(position=position, context=context):
                result = invoke("--qsa", position, context)
                visible = position + 1
                self.assertEqual(result, {"visible_tokens": visible,
                                          "completed_pools": visible // 4,
                                          "tail_tokens": visible % 4,
                                          "context_extent": min(context, ((visible + 31) // 32) * 32)})

    def test_qsa_future_ids_and_sentinel_suffix(self):
        self.require_checks("qsa_future_id_refused", "qsa_nonempty_after_sentinel_refused",
                            "qsa_full_capacity_no_sentinel_accepted")

    def test_cli_and_context_bounds_refuse_without_work(self):
        for args in (("--device",), ("--self-test", "extra"),
                     ("--plan", 0, 4097, 4096, 2), ("--plan", 0, 10, 4096, 4),
                     ("--plan", 10, 10, 4096, 2), ("--plan", -1, 10, 4096, 2),
                     ("--plan", 0, 0, 4096, 2), ("--history", -1, 0, 0, 248044),
                     ("--qsa", 4096, 4096), ("--qsa", 0, 0)):
            with self.subTest(args=args):
                invoke(*args, success=False)


if __name__ == "__main__":
    unittest.main()
