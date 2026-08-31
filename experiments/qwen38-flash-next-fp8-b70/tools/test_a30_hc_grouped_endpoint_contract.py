#!/usr/bin/env python3
"""Static and validation-only contract tests for the frozen A30 endpoint arm."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import unittest


TOOLS = Path(__file__).parent
LAUNCHER = TOOLS / "launch-tp4-mtp0-4352-ple-only-a30-hc-grouped-m1.sh"
CLIENT = TOOLS / "run-tp4-mtp0-4352-ple-only-a30-hc-grouped-m1-client.sh"
SUPERVISOR = TOOLS / "supervise-tp4-mtp0-4352-ple-only-a30-hc-grouped-m1.sh"
REWRITE = TOOLS / "rewrite-a30-hybrid-stage-contract.py"

EXPECTED_FILE_SHA256 = {
    LAUNCHER.name: "19ea4096d8de475ea40738b8d0c2bde006c6e660a653e93d010a56717aff094e",
    CLIENT.name: "71387d4df1f9c5fa2527cd301a8a8992a8ef370cae418eb83e5a44ca56814b07",
    SUPERVISOR.name: "c5a8490f801616844ecf0ef7517879e414e2577369cf70753e7884943d8b91b1",
    REWRITE.name: "b68ce87cdd3403e4a7ac246c6c9580e420a5492ab4c91e42b9ea15ef19d229d4",
}
EXPECTED_DERIVED_SHA256 = {
    "outer": "fe815b8419a60ba24bc9a2f21182fc3b780bb40e22885358c2eed53782f21e95",
    "inner": "8733a114124632c3fe47edaefac261f57e4999d1af211152f79a0ca8a29758f0",
    "client": "116ddf13fff1a556565b98484ebcb78724d30d56ad9a82d9fcebbf72dbcdd703",
    "supervisor": "4a498eceb1d6797598dd28b2a01efe554a45fd691553556f015f6370ff7666db",
}
STAGE = "/mnt/fast-ai/qwen38-build/runtime-serving-hcgrouped-eeee7d6-a2"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def generated(path: Path, selector: str) -> str:
    env = os.environ.copy()
    env[selector] = "1"
    return subprocess.run(
        [str(path)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout


def shell_syntax(source: str) -> None:
    subprocess.run(
        ["bash", "-n"],
        input=source,
        check=True,
        capture_output=True,
        text=True,
    )


class A30EndpointContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.outer = generated(LAUNCHER, "Q38_A30_SOURCE_ONLY")
        cls.inner = generated(LAUNCHER, "Q38_A30_INNER_SOURCE_ONLY")
        cls.client = generated(CLIENT, "Q38_A30_SOURCE_ONLY")
        cls.supervisor = generated(SUPERVISOR, "Q38_A30_SOURCE_ONLY")

    def test_frozen_files_and_generated_sources(self) -> None:
        for path in (LAUNCHER, CLIENT, SUPERVISOR, REWRITE):
            self.assertEqual(digest(path.read_bytes()), EXPECTED_FILE_SHA256[path.name])
        for name, source in (
            ("outer", self.outer),
            ("inner", self.inner),
            ("client", self.client),
            ("supervisor", self.supervisor),
        ):
            shell_syntax(source)
            self.assertEqual(digest(source.encode()), EXPECTED_DERIVED_SHA256[name])

    def test_identity_and_benchmark_shape_are_exact(self) -> None:
        self.assertIn("ATTEMPT=30 PORT=19702", self.outer)
        for source in (self.client, self.supervisor):
            self.assertIn("attempt30", source)
        for source in (self.outer, self.client, self.supervisor):
            self.assertIn("19702", source)
            self.assertNotIn("attempt29", source)
            self.assertNotIn("19701", source)
        self.assertIn(
            "MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=30 PORT=19702",
            self.outer,
        )
        self.assertIn("KV_CACHE_MEMORY_BYTES=134217728", self.outer)
        for token in (
            "--tensor-parallel-size 4",
            "--enable-expert-parallel",
            "--enforce-eager",
            "--max-num-seqs 1",
            "--max-num-batched-tokens 64",
            "--no-async-scheduling",
            "--cpu-offload-gb 12.0",
            "--cpu-offload-params ple_embedding.ngram_embedding.weight",
        ):
            self.assertIn(token, self.inner)
        self.assertIn("max_num_scheduled_tokens is None", self.inner)
        self.assertIn("cudagraph_mode.name == 'NONE'", self.inner)

    def test_only_qualified_treatments_are_enabled(self) -> None:
        flag = "export VLLM_XPU_QWEN4_EXP_HC_GROUPED_UP=1"
        self.assertEqual(self.inner.count(flag), 1)
        self.assertGreater(
            self.inner.index(flag),
            self.inner.index("unset VLLM_XPU_PLE_UVA_PREFETCH"),
        )
        self.assertIn(
            "assert envs.VLLM_XPU_QWEN4_EXP_HC_GROUPED_UP is True", self.inner
        )
        self.assertIn("len(grouped_schema.arguments) == 11", self.inner)
        self.assertIn("configs/moe-warps8-m1", self.inner)
        self.assertIn("requested_m == 1", self.client)
        self.assertIn("selected_batch_key == 1", self.client)
        self.assertIn("effective_config.num_warps == 8", self.client)
        self.assertIn("official_resolver_match == true", self.client)
        for forbidden in (
            "VLLM_XPU_PLE_UVA_PREFETCH=1",
            "VLLM_XPU_QWEN4_EXP_REPEATABILITY_TRACE_FILE=",
            "start_profile",
            "KINETO",
        ):
            self.assertNotIn(forbidden, self.inner + self.client)

    def test_hybrid_stage_and_source_provenance_are_closed(self) -> None:
        for source in (self.inner, self.client):
            self.assertIn(STAGE, source)
            self.assertIn("797769b34b6db5c934609b75dc04cc61ec66e5f9", source)
            self.assertIn("eeee7d671abfa964626baa18da2174bb92cac80a", source)
            self.assertIn("2f829747503c77d4814834dffd0840fb1dd9f75a", source)
            self.assertIn(
                "a4e83ec34d91b70a666dc170fcc3bda75562592c58fce198f29cfa4d25755d0d",
                source,
            )
            self.assertIn(
                "ca218488129510e0bc29175f96fd17f0572ecbc2e0f7913ce3c576d25b5b3591",
                source,
            )
        self.assertIn("runtime_stage_native_head", self.client)
        self.assertIn("runtime_stage_retained_base_head", self.client)
        self.assertIn("stage_native_head", self.supervisor)
        self.assertIn("stage_retained_base_head", self.supervisor)
        self.assertIn("kernel chain changed immediately before launch", self.inner)
        self.assertIn("HC grouped source changed immediately before launch", self.inner)
        self.assertNotIn("runtime-core-moe-negidguard-b70", self.inner + self.client)

    def test_full_quality_battery_and_protected_hashes_survive(self) -> None:
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
            "3b0b3192cd70de9c19caf7a6f6f69a4dda63cc4e66049c2cf9c15633103896b7",
            "cached_tokens",
        ):
            self.assertIn(token, self.client)
        self.assertIn("client-gates-passed.txt", self.supervisor)
        self.assertIn('.status == "passed"', self.supervisor)
        self.assertIn('.recovery_canary == "passed"', self.supervisor)
        self.assertIn(".exact_4k.repeats == 2", self.supervisor)
        self.assertIn(".identity.hc_grouped_up == true", self.supervisor)
        self.assertIn(
            "! grep -Fq 'nvme 0000:01:00.0:'",
            self.supervisor,
        )

    def test_validation_only_does_not_claim_boot_or_paths(self) -> None:
        marker = Path(f"/run/user/{os.getuid()}/q38-flash-next-full-load.boot-id")
        paths = (
            Path(
                "/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/"
                "qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1-attempt30"
            ),
            Path(
                "/mnt/usb-models/llm-runtime/qwen38-flash-next-fp8-b70/"
                "qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1-attempt30"
            ),
        )
        before_marker = marker.read_bytes() if marker.exists() else None
        before_paths = tuple(path.exists() for path in paths)
        env = os.environ.copy()
        env["Q38_A30_VALIDATE_ONLY"] = "1"
        subprocess.run(
            [str(LAUNCHER)],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        after_marker = marker.read_bytes() if marker.exists() else None
        self.assertEqual(after_marker, before_marker)
        self.assertEqual(tuple(path.exists() for path in paths), before_paths)


if __name__ == "__main__":
    unittest.main()
