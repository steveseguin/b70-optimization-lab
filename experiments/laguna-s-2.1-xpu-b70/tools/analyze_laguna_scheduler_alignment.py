#!/usr/bin/env python3
"""Classify the frozen Laguna scheduler-budget A/B pair."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path
from typing import Any


EXPECTED_LONG_CASE_IDS = (
    "laguna-lc-01024-early",
    "laguna-lc-08192-early",
    "laguna-lc-08192-middle",
    "laguna-lc-08192-late",
    "laguna-lc-16384-middle",
    "laguna-lc-24576-middle",
    "laguna-lc-32640-early",
    "laguna-lc-32640-middle",
    "laguna-lc-32640-late",
)
EXPECTED_CASE_IDS = (
    *EXPECTED_LONG_CASE_IDS[:7],
    "sentinel-after-laguna-lc-32640-early",
    EXPECTED_LONG_CASE_IDS[7],
    "sentinel-after-laguna-lc-32640-middle",
    EXPECTED_LONG_CASE_IDS[8],
    "sentinel-after-laguna-lc-32640-late",
)
EXPECTED_CASES_CSV = ",".join(EXPECTED_LONG_CASE_IDS)
VLLM_COMMIT = "4ddb915284d4442885f72bed48311fd04640977c"
KERNEL_COMMIT = "99886d783372e621941228250091dc8ebdc1595d"
TARGET_REVISION = "4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb"
DRAFT_REVISION = "5e07c246915c86dc6920fead03d019989224f2ba"
MODEL_MANIFEST_SHA256 = (
    "45aa105ef4eceaf05cad33012e0752369f77cbbd76f2213ccfe0ce130fa6c0ac"
)
SUITE_SHA256 = "58123ef43144fd9eea7cd54610042c6fa43256f2ec66d36371d1d238a45ba977"
COMMON_IDENTITY = {
    "vllm_commit": VLLM_COMMIT,
    "kernel_commit": KERNEL_COMMIT,
    "expected_vllm_commit": VLLM_COMMIT,
    "expected_kernel_commit": KERNEL_COMMIT,
    "target_revision": TARGET_REVISION,
    "draft_revision": DRAFT_REVISION,
    "model_manifest_sha256": MODEL_MANIFEST_SHA256,
    "target_root": "/mnt/fast-ai/llm-models/laguna-s-2.1/int4",
    "draft_root": "/mnt/fast-ai/llm-models/laguna-s-2.1/dflash-int4",
    "target_config_sha256": "9f139560db8fd723a75ee4adc24a9fece4101df0e8e7f1cce6549f7eba5b14e6",
    "draft_config_sha256": "6f2aac901675ce9c9a12454d0432df7609dac0bc46614ca14725ea5e86f20926",
    "max_model_len": "32768",
    "enable_chunked_prefill": "true",
    "max_num_seqs": "1",
    "block_size": "64",
    "kv_cache_dtype": "bfloat16",
    "gpu_memory_utilization": "0.80",
    "prefix_caching": "false",
    "async_scheduling": "false",
    "selected_case_ids": EXPECTED_CASES_CSV,
    "exact_prefill_chunks": "1",
    "candidate_profile": "q12",
    "candidate_m": "12",
    "candidate_spec": "11",
    "memory_guard_min_available_kb": "8388608",
    "memory_guard_min_swap_free_kb": "4194304",
    "memory_guard_min_swap_total_kb": "25165816",
    "memory_guard_low_swap_min_available_kb": "16777216",
    "required_swap_layout": "laguna-longctx-24g",
    "require_oracle": "1",
    "candidate_target_topology": "146/145",
    "candidate_draft_topology": "14/13",
    "scored_measurement": "false",
    "suite_sha256": SUITE_SHA256,
    "runtime_lock_sha256": "64b0f04d29aabcabd65c0f71ff6a4c0923208228abd0559f2308e63fb3334829",
}
EXPECTED_SERVICE_ENV = {
    "VLLM_KV_CACHE_LAYOUT": "NHD",
    "VLLM_XPU_EXACT_SPEC_ATTN": "1",
    "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE": "1",
    "VLLM_XPU_LAGUNA_EXACT_MAX_M": "12",
    "VLLM_XPU_LAGUNA_EXACT_PREFILL_CHUNKS": "1",
    "LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS": "11",
    "LAGUNA_M": "12",
    "LAGUNA_SPEC": "11",
    "VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH": "1",
    "VLLM_USE_BREAKABLE_CUDAGRAPH": "1",
    "XPU_GRAPH": "1",
    "VLLM_XPU_ENABLE_XPU_GRAPH": "1",
    "VLLM_XPU_LAGUNA_M12_SHARED_ELEMENTWISE": "1",
    "VLLM_XPU_LAGUNA_DFLASH_SEGMENTED_GRAPH": "1",
    "VLLM_XPU_LAGUNA_DFLASH_INLINE_ATTENTION_GRAPHS": "1",
    "VLLM_XPU_LAGUNA_DECODE_GRF128": "1",
    "VLLM_XPU_LAGUNA_DECODE_TRANSPOSED_SCALES": "1",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_kv(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def median(rows: list[dict[str, Any]], field: str) -> float:
    if not rows:
        raise ValueError(f"no rows for median field {field}")
    values = []
    for row in rows:
        value: Any = row
        for part in field.split("."):
            value = value[part]
        value = float(value)
        if value <= 0:
            raise ValueError(f"non-positive metric {field}: {value}")
        values.append(value)
    return statistics.median(values)


def rank_topology_count(
    log: str,
    rank: int,
    verb: str,
    graphs: int,
    eager: int,
) -> int:
    return sum(
        f"(Worker_TP{rank}_EP{rank} " in line
        and verb in line
        and "audited breakable cudagraph for BatchDescriptor(num_tokens=12," in line
        and f"BreakableCUDAGraphCapture(graphs={graphs}, eager_breaks={eager})" in line
        for line in log.splitlines()
    )


def xpu_process_capture_clean(path: Path) -> bool:
    payload = json.loads(path.read_text())
    rows = payload["device_util_by_proc_list"]
    if not isinstance(rows, list) or len(rows) != 4:
        return False
    process_ids = {row.get("process_id") for row in rows}
    return (
        {row.get("device_id") for row in rows} == {0, 1, 2, 3}
        and all(row.get("process_name") == "xpu-smi" for row in rows)
        and len(process_ids) == 1
        and all(
            isinstance(process_id, int) and process_id > 0 for process_id in process_ids
        )
    )


def log_line_has_all(log: str, marker: str, fragments: tuple[str, ...]) -> bool:
    return any(
        marker in line and all(fragment in line for fragment in fragments)
        for line in log.splitlines()
    )


def run_checks(
    run_dir: Path,
    arm: str,
    expected_oracle: Path,
) -> tuple[dict[str, Any], list[str]]:
    failures = []
    bench_path = run_dir / "bench.json"
    bench = json.loads(bench_path.read_text())
    identity = read_kv(run_dir / "identity.txt")
    cleanup = read_kv(run_dir / "cleanup-status.txt")
    service_env = read_kv(run_dir / "service-environment.txt")
    runtime = json.loads((run_dir / "runtime-verification.json").read_text())
    server_log = (run_dir / "server.log").read_text(errors="replace")

    expected_budget = {
        "A": ("8192", "auto", "8182"),
        "B": ("8202", "8192", "8192"),
    }[arm]
    expected_oracle = expected_oracle.resolve()
    bench_oracle = Path(bench["run_identity"]["oracle"]).resolve()
    checks = {
        "bench_status": bench.get("status") == "PASS_ORACLE_EXACT",
        "run_status": (run_dir / "run-status.txt").read_text().strip() == "PASS",
        "cleanup": cleanup.get("original_status") == "0"
        and cleanup.get("stop_status") == "0"
        and cleanup.get("device_error_status") == "0",
        "device_error_scan_empty": not (run_dir / "device-error-scan.log")
        .read_text()
        .strip(),
        "common_identity": all(
            identity.get(key) == value for key, value in COMMON_IDENTITY.items()
        ),
        "suite_path": identity.get("suite", "").endswith(
            "/experiments/laguna-s-2.1-xpu-b70/long-context-suite-v1.json"
        ),
        "suite_sha256": bench["run_identity"].get("suite_sha256") == SUITE_SHA256,
        "runtime_verification": runtime.get("status") == "PASS"
        and runtime.get("vllm_origin", "").startswith(
            "/home/steve/src/laguna-vllm-exact-prefill-chunks-20260802/"
        )
        and runtime.get("kernel_package")
        == "/home/steve/src/laguna-xpu-kernels-shared-elementwise-m12-20260731/vllm_xpu_kernels",
        "service_environment": all(
            service_env.get(key) == value for key, value in EXPECTED_SERVICE_ENV.items()
        ),
        "swap_total": int(identity.get("host_swap_total_kb", "0")) == 25165816,
        "budget_identity": (
            identity.get("max_num_batched_tokens"),
            identity.get("max_num_scheduled_tokens"),
            identity.get("expected_effective_scheduled_tokens"),
        )
        == expected_budget,
        "oracle_path": bench_oracle == expected_oracle
        and Path(identity.get("oracle", "")).resolve() == expected_oracle,
        "oracle_sha256": bench["run_identity"].get("oracle_sha256")
        == sha256(expected_oracle),
        "engine_identity": all(
            fragment in server_log
            for fragment in (
                "model='/mnt/fast-ai/llm-models/laguna-s-2.1/int4'",
                "model='/mnt/fast-ai/llm-models/laguna-s-2.1/dflash-int4', num_spec_tokens=11",
                f"revision={TARGET_REVISION}",
                "dtype=torch.bfloat16",
                "max_seq_len=32768",
                "tensor_parallel_size=4",
                "pipeline_parallel_size=1",
                "data_parallel_size=1",
                "kv_cache_dtype=bfloat16",
                "enable_prefix_caching=False",
                "enable_chunked_prefill=True",
                "cudagraph_capture_sizes': [12]",
                "max_cudagraph_capture_size': 12",
            )
        ),
        "xpu_process_captures": xpu_process_capture_clean(
            run_dir / "xpu-processes-before.json"
        )
        and xpu_process_capture_clean(run_dir / "xpu-processes-after.json"),
        "target_topology_per_rank": all(
            rank_topology_count(server_log, rank, verb, 146, 145) == 1
            for rank in range(4)
            for verb in ("Captured", "Replayed")
        ),
        "draft_topology_per_rank": all(
            rank_topology_count(server_log, rank, verb, 14, 13) == 1
            for rank in range(4)
            for verb in ("Captured", "Replayed")
        ),
        "topology_total": server_log.count("BreakableCUDAGraphCapture(graphs=") == 16,
    }
    if arm == "A":
        checks["runtime_budget_log"] = (
            server_log.count("max_num_scheduled_tokens is set to 8182 based on") >= 1
            and "Laguna long scheduler budget: batched=8192 scheduled=auto"
            in server_log
        )
    else:
        checks["runtime_budget_log"] = (
            "Laguna long scheduler budget: batched=8202 scheduled=8192" in server_log
            and log_line_has_all(
                server_log,
                "non-default args:",
                (
                    "'max_num_batched_tokens': 8202",
                    "'max_num_scheduled_tokens': 8192",
                ),
            )
        )

    rows = bench.get("rows", [])
    checks["case_order"] = (
        tuple(row.get("case_id") for row in rows) == EXPECTED_CASE_IDS
    )
    checks["row_gates"] = len(rows) == len(EXPECTED_CASE_IDS) and all(
        row.get("passed")
        and row.get("cached_tokens") == 0
        and row.get("oracle", {}).get("tested")
        and row.get("oracle", {}).get("prompt_hash_equal")
        and row.get("oracle", {}).get("token_ids_equal")
        and row.get("oracle", {}).get("text_hash_equal")
        for row in rows
    )
    failures.extend(f"{arm}:{name}" for name, passed in checks.items() if not passed)
    return {"checks": checks, "rows": rows, "identity": identity}, failures


def write_result(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {"status": result["status"], "failures": result.get("failures", [])},
            sort_keys=True,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-run", type=Path, required=True)
    parser.add_argument("--candidate-run", type=Path)
    parser.add_argument("--repeat-oracle", type=Path, required=True)
    parser.add_argument("--control-only", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.control_only == (args.candidate_run is not None):
        parser.error("use either --control-only or --candidate-run")

    try:
        control, failures = run_checks(args.control_run, "A", args.repeat_oracle)
        if args.control_only:
            result = {
                "schema": "laguna-scheduler-alignment-control-v1",
                "status": "PASS" if not failures else "FAIL",
                "control_run": str(args.control_run.resolve()),
                "control_checks": control["checks"],
                "failures": failures,
            }
            write_result(args.out, result)
            return 0 if not failures else 1

        candidate, candidate_failures = run_checks(
            args.candidate_run,
            "B",
            args.control_run / "bench.json",
        )
        failures.extend(candidate_failures)
        common_identity_equal = all(
            control["identity"].get(key) == candidate["identity"].get(key)
            for key in COMMON_IDENTITY
        )
        if not common_identity_equal:
            failures.append("common_identity_mismatch")
        control_rows = {row["case_id"]: row for row in control["rows"]}
        candidate_rows = {row["case_id"]: row for row in candidate["rows"]}

        equality_fields = (
            "prompt_token_ids_sha256",
            "output_token_ids_sha256",
            "text_sha256",
            "token_ids",
            "spec_decode",
        )
        matched_equality = {
            case_id: all(
                control_rows.get(case_id, {}).get(field)
                == candidate_rows.get(case_id, {}).get(field)
                for field in equality_fields
            )
            for case_id in EXPECTED_CASE_IDS
        }
        if not all(matched_equality.values()):
            failures.append("matched_output_or_counter_equality")

        def group(
            rows: dict[str, dict[str, Any]],
            tokens: int,
        ) -> list[dict[str, Any]]:
            return [
                row
                for row in rows.values()
                if row.get("row_kind") == "long"
                and row.get("target_prompt_tokens") == tokens
            ]

        performance: dict[str, Any] = {}
        for tokens in (8192, 16384, 24576, 32640):
            a_rows = group(control_rows, tokens)
            b_rows = group(candidate_rows, tokens)
            performance[str(tokens)] = {
                "count": len(a_rows),
                "prefill_ratio": median(b_rows, "prefill_tok_s_prometheus")
                / median(a_rows, "prefill_tok_s_prometheus"),
                "ttft_ratio": median(b_rows, "client_ttft_s")
                / median(a_rows, "client_ttft_s"),
                "decode_ratio": median(
                    b_rows, "timing.conventional_99_interval_first_100_tok_s"
                )
                / median(a_rows, "timing.conventional_99_interval_first_100_tok_s"),
            }

        sentinel_a = [
            row for row in control_rows.values() if row.get("row_kind") == "sentinel"
        ]
        sentinel_b = [
            row for row in candidate_rows.values() if row.get("row_kind") == "sentinel"
        ]
        performance["sentinel"] = {
            "count": len(sentinel_a),
            "decode_ratio": median(
                sentinel_b, "timing.conventional_99_interval_first_100_tok_s"
            )
            / median(sentinel_a, "timing.conventional_99_interval_first_100_tok_s"),
        }
        performance_checks = {
            "8k_count": performance["8192"]["count"] == 3,
            "8k_prefill": performance["8192"]["prefill_ratio"] >= 1.35,
            "8k_ttft": performance["8192"]["ttft_ratio"] <= 0.75,
            "16k_count": performance["16384"]["count"] == 1,
            "24k_count": performance["24576"]["count"] == 1,
            "32k_count": performance["32640"]["count"] == 3,
            "sentinel_count": performance["sentinel"]["count"] == 3,
            "16k_prefill": performance["16384"]["prefill_ratio"] >= 0.98,
            "24k_prefill": performance["24576"]["prefill_ratio"] >= 0.98,
            "32k_prefill": performance["32640"]["prefill_ratio"] >= 0.98,
            "16k_ttft": performance["16384"]["ttft_ratio"] <= 1.02,
            "24k_ttft": performance["24576"]["ttft_ratio"] <= 1.02,
            "32k_ttft": performance["32640"]["ttft_ratio"] <= 1.02,
            "32k_decode_median": performance["32640"]["decode_ratio"] >= 0.98,
            "32k_decode_rows": all(
                candidate_rows[case_id]["timing"][
                    "conventional_99_interval_first_100_tok_s"
                ]
                / control_rows[case_id]["timing"][
                    "conventional_99_interval_first_100_tok_s"
                ]
                >= 0.95
                for case_id in EXPECTED_CASE_IDS
                if case_id.startswith("laguna-lc-32640-")
            ),
            "sentinel_decode": performance["sentinel"]["decode_ratio"] >= 0.98,
        }
        failures.extend(
            f"performance:{name}"
            for name, passed in performance_checks.items()
            if not passed
        )

        result = {
            "schema": "laguna-scheduler-alignment-ab-v1",
            "status": "PASS" if not failures else "FAIL",
            "control_run": str(args.control_run.resolve()),
            "candidate_run": str(args.candidate_run.resolve()),
            "control_checks": control["checks"],
            "candidate_checks": candidate["checks"],
            "common_identity_equal": common_identity_equal,
            "matched_equality": matched_equality,
            "performance": performance,
            "performance_checks": performance_checks,
            "failures": failures,
        }
        write_result(args.out, result)
        return 0 if not failures else 1
    except Exception as error:
        result = {
            "schema": "laguna-scheduler-alignment-ab-v1",
            "status": "ERROR",
            "failures": [f"analyzer_exception:{type(error).__name__}:{error}"],
        }
        write_result(args.out, result)
        return 2


if __name__ == "__main__":
    sys.exit(main())
