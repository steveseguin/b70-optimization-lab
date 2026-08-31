#!/usr/bin/env python3
"""Static source-contract tests for the frozen A29 endpoint arm."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import unittest


TOOLS = Path(__file__).parent


def generated(name: str) -> str:
    env = os.environ.copy()
    env["Q38_A29_SOURCE_ONLY"] = "1"
    return subprocess.run(
        [str(TOOLS / name)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout


class A29EndpointContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.wrapper = (
            TOOLS / "launch-tp4-mtp0-4352-ple-only-a29-moe-m1-warps8.sh"
        ).read_text()
        cls.rewrite = (TOOLS / "rewrite-a29-kernel-workspace-contract.py").read_text()
        cls.launch = generated("launch-tp4-mtp0-4352-ple-only-a29-moe-m1-warps8.sh")
        cls.client = generated("run-tp4-mtp0-4352-ple-only-a29-moe-m1-warps8-client.sh")
        cls.supervisor = generated(
            "supervise-tp4-mtp0-4352-ple-only-a29-moe-m1-warps8.sh"
        )

    def test_isolated_identity_and_sync_ple(self) -> None:
        self.assertIn("ATTEMPT=29 PORT=19701", self.launch)
        for source in (self.client, self.supervisor):
            self.assertIn("attempt29", source)
        for source in (self.launch, self.client, self.supervisor):
            self.assertIn("19701", source)
        self.assertIn("unset VLLM_XPU_PLE_UVA_PREFETCH", self.launch)
        self.assertNotIn("attempt27", self.launch)
        self.assertNotIn("19699", self.launch)

    def test_live_selection_receipt_is_not_file_load_only(self) -> None:
        self.assertIn("verify-moe-m1-selection.py", self.launch)
        self.assertIn("moe-m1-selection-receipt.json", self.client)
        self.assertIn(".requested_m == 1", self.client)
        self.assertIn(".selected_batch_key == 1", self.client)
        self.assertIn(".effective_config.num_warps == 8", self.client)
        self.assertIn(".official_resolver_match == true", self.client)

    def test_full_a27_battery_and_protected_hashes_survive(self) -> None:
        for token in (
            "--repeat-runs 16",
            "quality-current.json",
            "bench-short-r1.json",
            "bench-short-r2.json",
            "bench-short-r3.json",
            "exact-depth-4k-r1.json",
            "exact-depth-4k-r2.json",
            "5f40744644b98ddd58a0c202fe855af324c0b1c33e1a6275afd74c12488f89f0",
            "1d833e5f463366223a669aa15495840d1337b173e675a9ea04f00a5ae339d5cc",
            "cached_tokens",
        ):
            self.assertIn(token, self.client)
        self.assertIn("client-gates-passed.txt", self.supervisor)
        self.assertIn('.status == "passed"', self.supervisor)
        self.assertIn('.recovery_canary == "passed"', self.supervisor)
        self.assertIn(".exact_4k.repeats == 2", self.supervisor)

    def test_rejects_profiler_async_and_old_m4_folder(self) -> None:
        self.assertIn("old M4 tuned folder leaked", self.client)
        self.assertIn("trace selector unexpectedly present", self.client)
        self.assertIn("async UVA PLE selector unexpectedly present", self.client)
        self.assertNotIn("start_profile", self.client)
        self.assertNotIn("KINETO", self.launch.upper())

    def test_workspace_child_and_stage_are_checked_before_boot_claim(self) -> None:
        workspace_head = "359466a262489bdf4e1774e3572202dc82a00718"
        staged_head = "ad25aa9f69a2171612b9c6b83dfa82c69559f9e4"
        self.assertIn(workspace_head, self.wrapper)
        self.assertIn(staged_head, self.wrapper)
        self.assertIn("runtime-stage-padding-guard-loadable.sha256", self.wrapper)
        self.assertIn("default-off child patch changed before boot claim", self.wrapper)
        self.assertLess(
            self.wrapper.index("kernel workspace head changed before boot claim"),
            self.wrapper.index("source <(derive)"),
        )
        self.assertIn("q38-flash-next-full-load.boot-id", self.launch)

    def test_workspace_is_rechecked_immediately_before_serve(self) -> None:
        self.assertIn("rewrite-a29-kernel-workspace-contract.py", self.launch)
        self.assertIn(
            "kernel workspace changed immediately before launch", self.rewrite
        )
        self.assertIn("kernel workspace became dirty immediately", self.rewrite)
        self.assertIn("before launch", self.rewrite)


if __name__ == "__main__":
    unittest.main()
