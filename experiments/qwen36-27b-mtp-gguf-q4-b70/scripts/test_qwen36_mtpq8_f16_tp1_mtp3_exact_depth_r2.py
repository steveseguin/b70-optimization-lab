from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest


HERE = Path(__file__).resolve().parent
R2_RUNNER_PATH = HERE / "run-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r2.py"
R2_VALIDATOR_PATH = HERE / "validate-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r2.py"
R1_TEST_PATH = HERE / "test_qwen36_mtpq8_f16_tp1_mtp3_exact_depth_r1.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


R2 = load(R2_RUNNER_PATH, "qwen36_mtp3_r2_test_runner")
VALIDATOR = load(R2_VALIDATOR_PATH, "qwen36_mtp3_r2_test_validator")
R1_TEST = load(R1_TEST_PATH, "qwen36_mtp3_r1_fixture_for_r2")


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


class MTP3R2RetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = R1_TEST.MTP3ExactDepthTests()
        self.fixture.setUp()
        self.root = self.fixture.root
        identity_path = self.root / "identity.json"
        identity = json.loads(identity_path.read_text())
        identity["campaign_id"] = R2.R2_CAMPAIGN_ID
        identity_path.write_text(json.dumps(identity))

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def test_r1_files_are_byte_identical_and_failure_is_pinned(self) -> None:
        overlay = R2.load_overlay()
        R2.verify_references(overlay)
        self.assertEqual(R2.sha256_file(R2.R1_RUNNER), "e28d915fc261868fea041b6a1edad1f818de01ab01b6b5b3765f1e961b399322")
        self.assertEqual(R2.sha256_file(R2.R1_TERMINAL), "c368d3c965fda512b740477c1acb2463a98c26a86722faddffc5e6642a9cebb7")

    def test_merged_execution_identity_only_changes_retry_lifecycle(self) -> None:
        base = json.loads(R2.R1_MANIFEST.read_text())
        merged = R2.merge_manifest(R2.load_overlay())
        self.assertEqual(changed_paths(base, merged), {
            "campaign_id", "purpose", "lifecycle.runner", "lifecycle.validator",
            "lifecycle.output_root", "lifecycle.exact_ack", "retry_overlay",
        })
        self.assertEqual(base["model"], merged["model"])
        self.assertEqual(base["runtime"], merged["runtime"])
        self.assertEqual(base["arms"], merged["arms"])
        self.assertEqual(base["server_contract"], merged["server_contract"])

    def test_tab_indented_real_ldd_rows_match_transformed_parser(self) -> None:
        runtime = R2.merge_manifest(R2.load_overlay())["runtime"]
        sample = "\n".join(
            f"\t{row['soname']} => {Path(runtime['binary']).parent / row['soname']} (0x00000000)"
            for row in runtime["effective_local_shared_libraries"]
        ) + "\n"
        for row in runtime["effective_local_shared_libraries"]:
            match = re.search(rf"^\s*{re.escape(row['soname'])}\s+=>\s+(\S+)", sample, re.M)
            self.assertIsNotNone(match)
            assert match is not None
            self.assertEqual(Path(match.group(1)).resolve(), Path(row["path"]).resolve())
        self.assertIn('rf"^\\s*{re.escape(row[\'soname\'])}\\s+=>\\s+(\\S+)"', R2.TRANSFORMED_SOURCE)
        self.assertNotIn('rf"^{re.escape(row[\'soname\'])}\\s+=>\\s+(\\S+)"', R2.TRANSFORMED_SOURCE)

    def test_r2_static_check_is_inert(self) -> None:
        result = subprocess.run([sys.executable, "-B", str(R2_RUNNER_PATH), "--check"], check=True, text=True, capture_output=True)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["campaign_id"], R2.R2_CAMPAIGN_ID)
        self.assertEqual(plan["exact_ack"], f"RUN {R2.R2_CAMPAIGN_ID}")
        self.assertEqual((plan["gpu_actions"], plan["network_requests"], plan["output_writes"]), (0, 0, 0))

    def test_r2_validator_accepts_fresh_synthetic_artifacts(self) -> None:
        result = VALIDATOR.validate(self.root, R2.OVERLAY)
        self.assertTrue(result["gate"]["passed"])
        self.assertEqual(result["campaign_id"], R2.R2_CAMPAIGN_ID)
        self.assertEqual(result["authority"]["matrix_cells_if_reviewed"], 7)


if __name__ == "__main__":
    unittest.main()
