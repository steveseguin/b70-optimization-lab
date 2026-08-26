#!/usr/bin/env python3
"""CPU-only tests for the whitespace-only R2 route-screen retry."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest


HERE = Path(__file__).resolve().parent
R2_RUNNER_PATH = HERE / "run-20260825-qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-r2.py"
R2_VALIDATOR_PATH = HERE / "validate-20260825-qwen36-mtpq8-f16-tp1-mtp-route-8k-sentinel-r2.py"
R1_TEST_PATH = HERE / "test_qwen36_mtpq8_f16_tp1_mtp_route_8k_sentinel_r1.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


R2 = load(R2_RUNNER_PATH, "qwen36_mtp_route_8k_r2_test_runner")
VALIDATOR = load(R2_VALIDATOR_PATH, "qwen36_mtp_route_8k_r2_test_validator")
R1_TEST = load(R1_TEST_PATH, "qwen36_mtp_route_8k_r1_fixture_for_r2")


def changed_paths(left, right, prefix="") -> set[str]:
    if type(left) is not type(right):
        return {prefix}
    if isinstance(left, dict):
        result: set[str] = set()
        for key in set(left) | set(right):
            path = f"{prefix}.{key}" if prefix else key
            if key not in left or key not in right:
                result.add(path)
            else:
                result |= changed_paths(left[key], right[key], path)
        return result
    if isinstance(left, list):
        if len(left) != len(right):
            return {prefix}
        result: set[str] = set()
        for index, (a, b) in enumerate(zip(left, right)):
            result |= changed_paths(a, b, f"{prefix}[{index}]")
        return result
    return set() if left == right else {prefix}


class Route8KSentinelR2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = R1_TEST.Route8KSentinelTests()
        self.fixture.setUp()
        self.root = self.fixture.root
        identity_path = self.root / "identity.json"
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        identity["campaign_id"] = R2.R2_CAMPAIGN_ID
        identity_path.write_text(json.dumps(identity), encoding="utf-8")

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def test_r1_packet_and_failure_receipt_are_pinned(self) -> None:
        overlay = R2.load_overlay()
        R2.verify_references(overlay)
        self.assertEqual(R2.sha256_file(R2.R1_RUNNER),
                         "dccff88098bea9dd51bb09a4985756ec25b6de8a2a98e4cc3f24dd46d85e2095")
        self.assertEqual(R2.sha256_file(R2.R1_TERMINAL),
                         "b4580ac1ed743a234d894e1eb4c78212229e67b8e511e9d39721d1b4cd3f9c60")

    def test_merged_manifest_only_changes_retry_lifecycle(self) -> None:
        base = R2.BASE.merged_manifest(json.loads(R2.R1_MANIFEST.read_text(encoding="utf-8")))
        merged = R2.merge_manifest(R2.load_overlay())
        self.assertEqual(changed_paths(base, merged), {
            "campaign_id", "purpose", "lifecycle.runner", "lifecycle.validator",
            "lifecycle.output_root", "lifecycle.exact_ack",
            "retry_overlay.schema", "retry_overlay.r2_terminal_receipt_sha256",
            "retry_overlay.r1_r2_rows_reused", "retry_overlay.r1_terminal_receipt_sha256",
            "retry_overlay.sole_execution_delta", "retry_overlay.r1_rows_reused",
        })
        for key in ("model", "runtime", "fixture", "clients", "selectors", "server_contract",
                    "route_contract", "frozen_interpretation"):
            self.assertEqual(base[key], merged[key], key)

    def test_only_ldd_pattern_is_semantically_relaxed(self) -> None:
        old = 'rf"^{re.escape(row[\'soname\'])}\\s+=>\\s+(\\S+)"'
        new = 'rf"^\\s*{re.escape(row[\'soname\'])}\\s+=>\\s+(\\S+)"'
        self.assertNotIn(old, R2.TRANSFORMED_SOURCE)
        self.assertIn(new, R2.TRANSFORMED_SOURCE)
        runtime = R2.merge_manifest(R2.load_overlay())["runtime"]
        sample = "\n".join(
            f"\t{row['soname']} => {row['path']} (0x00000000)"
            for row in runtime["effective_local_shared_libraries"]
        )
        for row in runtime["effective_local_shared_libraries"]:
            match = re.search(rf"^\s*{re.escape(row['soname'])}\s+=>\s+(\S+)", sample, re.M)
            self.assertIsNotNone(match)
            self.assertEqual(Path(match.group(1)).resolve(), Path(row["path"]).resolve())

    def test_r2_check_is_inert(self) -> None:
        result = subprocess.run(
            [sys.executable, "-B", str(R2_RUNNER_PATH), "--check"],
            check=True, text=True, capture_output=True,
        )
        plan = json.loads(result.stdout)
        self.assertEqual(plan["campaign_id"], R2.R2_CAMPAIGN_ID)
        self.assertEqual(plan["exact_ack"], f"RUN {R2.R2_CAMPAIGN_ID}")
        self.assertEqual((plan["gpu_actions"], plan["network_requests"], plan["output_writes"]), (0, 0, 0))
        self.assertEqual(plan["fresh_server_lifetimes"], 5)

    def test_r2_validator_accepts_fresh_synthetic_artifacts(self) -> None:
        result = VALIDATOR.validate(self.root, R2.OVERLAY)
        self.assertTrue(result["screen_gate"]["passed"])
        self.assertEqual(result["campaign_id"], R2.R2_CAMPAIGN_ID)
        self.assertEqual(result["authority"]["candidate_routes_eligible_for_separately_preregistered_curve"], [1, 2, 4])
        self.assertFalse(result["authority"]["headline_or_protected_replacement"])


if __name__ == "__main__":
    unittest.main()
