#!/usr/bin/env python3
"""CPU-only tests for the scheduler-alignment oracle and classifier."""

from __future__ import annotations

import json
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

import analyze_laguna_scheduler_alignment as alignment


TOOLS = Path(__file__).resolve().parent
ANALYZER = TOOLS / "analyze_laguna_scheduler_alignment.py"
BUILDER = TOOLS / "build_laguna_long_context_repeat_oracle.py"
CASE_IDS = (
    "laguna-lc-01024-early",
    "laguna-lc-08192-early",
    "laguna-lc-08192-middle",
    "laguna-lc-08192-late",
    "laguna-lc-16384-middle",
    "laguna-lc-24576-middle",
    "laguna-lc-32640-early",
    "sentinel-after-laguna-lc-32640-early",
    "laguna-lc-32640-middle",
    "sentinel-after-laguna-lc-32640-middle",
    "laguna-lc-32640-late",
    "sentinel-after-laguna-lc-32640-late",
)


def tokens_for(case_id: str) -> int:
    if case_id.startswith("sentinel-"):
        return 256
    return int(case_id.split("-")[2])


def row(case_id: str, arm: str) -> dict[str, object]:
    tokens = tokens_for(case_id)
    candidate = arm == "B"
    prefill = 140.0 if candidate and tokens == 8192 else 100.0
    ttft = 7.0 if candidate and tokens == 8192 else 10.0
    return {
        "case_id": case_id,
        "row_kind": "sentinel" if case_id.startswith("sentinel-") else "long",
        "target_prompt_tokens": tokens,
        "passed": True,
        "cached_tokens": 0,
        "oracle": {
            "tested": True,
            "prompt_hash_equal": True,
            "token_ids_equal": True,
            "text_hash_equal": True,
        },
        "checks": {
            "cache_zero": True,
            "completion_length_exact": True,
            "decode_metric_count_one": True,
            "finish_reason_length": True,
            "first_100_timed": True,
            "oracle_exact_if_requested": True,
            "prefill_metric_count_one": True,
            "prefill_metric_tokens_exact": True,
            "prefill_token_metric_count_one": True,
            "prompt_length_exact": True,
            "retrieval_pass": True,
            "returned_prompt_ids_exact": True,
            "stream_token_ids_exact": True,
        },
        "prompt_token_ids_sha256": f"prompt-{case_id}",
        "output_token_ids_sha256": f"output-{case_id}",
        "text_sha256": f"text-{case_id}",
        "token_ids": [1, 2, 3],
        "spec_decode": {"drafts": 10.0, "draft_tokens": 20.0, "accepted_tokens": 3.0},
        "prefill_tok_s_prometheus": prefill,
        "client_ttft_s": ttft,
        "timing": {"conventional_99_interval_first_100_tok_s": 100.0},
    }


def topology_log(arm: str) -> str:
    lines = []
    for verb in ("Captured", "Replayed"):
        for graphs, eager in ((146, 145), (14, 13)):
            for rank in range(4):
                lines.append(
                    f"(Worker_TP{rank}_EP{rank} pid=1) {verb} audited breakable cudagraph for BatchDescriptor(num_tokens=12, fake) BreakableCUDAGraphCapture(graphs={graphs}, eager_breaks={eager})"
                )
    lines.append(
        "model='/mnt/fast-ai/llm-models/laguna-s-2.1/int4' "
        "model='/mnt/fast-ai/llm-models/laguna-s-2.1/dflash-int4', num_spec_tokens=11 "
        f"revision={alignment.TARGET_REVISION} dtype=torch.bfloat16 max_seq_len=32768 "
        "tensor_parallel_size=4 pipeline_parallel_size=1 data_parallel_size=1 "
        "kv_cache_dtype=bfloat16 enable_prefix_caching=False enable_chunked_prefill=True "
        "cudagraph_capture_sizes': [12] max_cudagraph_capture_size': 12"
    )
    lines.append("TP rank 0, EP rank 0")
    if arm == "A":
        lines.extend(
            [
                "Laguna long scheduler budget: batched=8192 scheduled=auto",
                "max_num_scheduled_tokens is set to 8182 based on speculative settings",
            ]
        )
    else:
        lines.extend(
            [
                "Laguna long scheduler budget: batched=8202 scheduled=8192",
                "non-default args: {'max_num_batched_tokens': 8202, "
                "'max_num_scheduled_tokens': 8192}",
            ]
        )
    return "\n".join(lines) + "\n"


class SchedulerAlignmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.oracle = self.root / "oracle.json"
        self.oracle.write_text(json.dumps({"rows": []}))
        self.control = self.make_run("A")
        self.candidate = self.make_run("B")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def make_run(self, arm: str) -> Path:
        run = self.root / arm
        run.mkdir()
        batched, scheduled, effective = {
            "A": ("8192", "auto", "8182"),
            "B": ("8202", "8192", "8192"),
        }[arm]
        identity = dict(alignment.COMMON_IDENTITY)
        identity.update(
            {
                "host_swap_total_kb": "25165816",
                "max_num_batched_tokens": batched,
                "max_num_scheduled_tokens": scheduled,
                "expected_effective_scheduled_tokens": effective,
                "suite": "/repo/experiments/laguna-s-2.1-xpu-b70/long-context-suite-v1.json",
                "oracle": str(
                    self.oracle if arm == "A" else self.control / "bench.json"
                ),
            }
        )
        (run / "identity.txt").write_text(
            "".join(f"{key}={value}\n" for key, value in identity.items())
        )
        (run / "cleanup-status.txt").write_text(
            "original_status=0\nstop_status=0\ndevice_error_status=0\n"
        )
        (run / "run-status.txt").write_text("PASS\n")
        (run / "device-error-scan.log").write_text("")
        (run / "server.log").write_text(topology_log(arm))
        (run / "service-environment.txt").write_text(
            "".join(
                f"{key}={value}\n"
                for key, value in alignment.EXPECTED_SERVICE_ENV.items()
            )
        )
        (run / "runtime-verification.json").write_text(
            json.dumps(
                {
                    "status": "PASS",
                    "vllm_origin": "/home/steve/src/laguna-vllm-exact-prefill-chunks-20260802/vllm/__init__.py",
                    "kernel_package": "/home/steve/src/laguna-xpu-kernels-shared-elementwise-m12-20260731/vllm_xpu_kernels",
                }
            )
        )
        xpu_capture = {
            "device_util_by_proc_list": [
                {"device_id": rank, "process_id": 1234, "process_name": "xpu-smi"}
                for rank in range(4)
            ]
        }
        for name in ("xpu-processes-before.json", "xpu-processes-after.json"):
            (run / name).write_text(json.dumps(xpu_capture))
        oracle = self.oracle if arm == "A" else self.control / "bench.json"
        (run / "bench.json").write_text(
            json.dumps(
                {
                    "status": "PASS_ORACLE_EXACT",
                    "run_identity": {
                        "oracle": str(oracle),
                        "oracle_sha256": hashlib.sha256(
                            oracle.read_bytes()
                        ).hexdigest(),
                        "suite_sha256": alignment.SUITE_SHA256,
                    },
                    "rows": [row(case_id, arm) for case_id in CASE_IDS],
                }
            )
        )
        return run

    def analyze(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(ANALYZER),
                "--control-run",
                str(self.control),
                "--candidate-run",
                str(self.candidate),
                "--repeat-oracle",
                str(self.oracle),
                "--out",
                str(self.root / "summary.json"),
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_complete_pair_passes(self) -> None:
        completed = self.analyze()
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(
            json.loads((self.root / "summary.json").read_text())["status"], "PASS"
        )

    def test_counter_mismatch_fails(self) -> None:
        payload = json.loads((self.candidate / "bench.json").read_text())
        payload["rows"][1]["spec_decode"]["drafts"] = 11.0
        (self.candidate / "bench.json").write_text(json.dumps(payload))
        completed = self.analyze()
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("matched_output_or_counter_equality", completed.stdout)

    def test_8k_threshold_failure_is_classified(self) -> None:
        payload = json.loads((self.candidate / "bench.json").read_text())
        for candidate_row in payload["rows"]:
            if candidate_row["target_prompt_tokens"] == 8192:
                candidate_row["prefill_tok_s_prometheus"] = 120.0
        (self.candidate / "bench.json").write_text(json.dumps(payload))
        completed = self.analyze()
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("performance:8k_prefill", completed.stdout)

    def test_missing_metric_writes_structured_error(self) -> None:
        payload = json.loads((self.candidate / "bench.json").read_text())
        del payload["rows"][1]["prefill_tok_s_prometheus"]
        (self.candidate / "bench.json").write_text(json.dumps(payload))
        completed = self.analyze()
        self.assertEqual(completed.returncode, 2)
        summary = json.loads((self.root / "summary.json").read_text())
        self.assertEqual(summary["status"], "ERROR")

    def test_control_only_passes_before_candidate(self) -> None:
        completed = subprocess.run(
            [
                str(ANALYZER),
                "--control-run",
                str(self.control),
                "--repeat-oracle",
                str(self.oracle),
                "--control-only",
                "--out",
                str(self.root / "control-summary.json"),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_empty_xpu_capture_fails(self) -> None:
        (self.control / "xpu-processes-before.json").write_text(
            json.dumps({"device_util_by_proc_list": []})
        )
        completed = self.analyze()
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("A:xpu_process_captures", completed.stdout)

    def test_subset_xpu_capture_fails(self) -> None:
        capture = {
            "device_util_by_proc_list": [
                {"device_id": 0, "process_id": 1234, "process_name": "xpu-smi"},
                {"device_id": 1, "process_id": 1234, "process_name": "xpu-smi"},
                {"device_id": 2, "process_id": 1234, "process_name": "xpu-smi"},
            ]
        }
        (self.control / "xpu-processes-after.json").write_text(json.dumps(capture))
        completed = self.analyze()
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("A:xpu_process_captures", completed.stdout)

    def test_candidate_missing_vllm_budget_evidence_fails(self) -> None:
        server_log = (self.candidate / "server.log").read_text()
        server_log = server_log.replace("'max_num_scheduled_tokens': 8192", "")
        (self.candidate / "server.log").write_text(server_log)
        completed = self.analyze()
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("B:runtime_budget_log", completed.stdout)

    def test_oracle_builder_rejects_conflicting_duplicate(self) -> None:
        first = self.root / "first.json"
        second = self.root / "second.json"
        first.write_text(
            json.dumps(
                {
                    "status": "PASS",
                    "run_identity": {"created_at_utc": "2026-08-02T01:00:00+00:00"},
                    "rows": [row(CASE_IDS[0], "A")],
                }
            )
        )
        conflicting = row(CASE_IDS[0], "A")
        conflicting["token_ids"] = [9]
        second.write_text(
            json.dumps(
                {
                    "status": "PASS",
                    "run_identity": {"created_at_utc": "2026-08-02T02:00:00+00:00"},
                    "rows": [conflicting],
                }
            )
        )
        completed = subprocess.run(
            [
                str(BUILDER),
                "--case-source",
                f"{CASE_IDS[0]}={first},{second}",
                "--out",
                str(self.root / "oracle.json"),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("conflicting duplicate", completed.stderr)

    def test_oracle_builder_rejects_same_path_twice(self) -> None:
        source = self.root / "source.json"
        source.write_text(
            json.dumps(
                {
                    "status": "PASS",
                    "run_identity": {"created_at_utc": "2026-08-02T01:00:00+00:00"},
                    "rows": [row(CASE_IDS[0], "A")],
                }
            )
        )
        completed = subprocess.run(
            [
                str(BUILDER),
                "--case-source",
                f"{CASE_IDS[0]}={source},{source}",
                "--out",
                str(self.root / "oracle-same.json"),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("not independent", completed.stderr)

    def test_oracle_builder_rejects_copied_run_with_whitespace_change(self) -> None:
        payload = {
            "status": "PASS",
            "run_identity": {"created_at_utc": "2026-08-02T01:00:00+00:00"},
            "rows": [row(CASE_IDS[0], "A")],
        }
        first = self.root / "copy-first.json"
        second = self.root / "copy-second.json"
        first.write_text(json.dumps(payload))
        second.write_text(json.dumps(payload, indent=2))
        completed = subprocess.run(
            [
                str(BUILDER),
                "--case-source",
                f"{CASE_IDS[0]}={first},{second}",
                "--out",
                str(self.root / "oracle-copy.json"),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("not independent", completed.stderr)


if __name__ == "__main__":
    unittest.main()
