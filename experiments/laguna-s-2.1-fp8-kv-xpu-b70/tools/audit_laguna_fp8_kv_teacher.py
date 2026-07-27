#!/usr/bin/env python3
"""Audit a completed FP8 q1 teacher, including the first reporting-gate miss."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

EXPECTED_SCALE_DIGEST = (
    "3e6df440976ab2ed5229e1a39179cbc99d573c615386f223eeabc9de5ea9ddc0"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_status(path: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    for line in path.read_text().splitlines():
        key, value = line.split("=", 1)
        result[key] = int(value)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite {args.out}")

    bench_path = args.run / "bench.json"
    log_path = args.run / "server.log"
    scale_path = args.run / "checkpoint-fp8-kv-scales.json"
    cleanup_path = args.run / "cleanup-status.txt"
    for path in (bench_path, log_path, scale_path, cleanup_path):
        if not path.is_file():
            raise SystemExit(f"missing evidence: {path}")

    bench = json.loads(bench_path.read_text())
    scale = json.loads(scale_path.read_text())
    cleanup = parse_status(cleanup_path)
    log = log_path.read_text(encoding="utf-8", errors="replace")
    rows = bench.get("rows", [])
    target_audits = log.count(
        "LAGUNA_FP8_KV_SCALE_AUDIT=PASS model=target layers=48"
    )
    draft_audits = log.count("LAGUNA_FP8_KV_SCALE_AUDIT=PASS model=draft")
    flash_markers = log.count("Using Flash Attention backend")
    fp8_engine_markers = log.count("kv_cache_dtype=fp8")
    runtime_errors = len(
        re.findall(r"RuntimeError|Traceback|device lost|\\bERROR\\b", log, re.I)
    )
    bench_valid = bool(
        bench.get("fresh_response_validity", {}).get("valid")
        and bench.get("fresh_response_validity", {}).get("cached_tokens_all_zero")
        and bench.get("realistic_final_gate", {}).get("passed")
        and bench.get("run_identity", {}).get("prompt_count") == 13
        and bench.get("run_identity", {}).get("max_tokens") == 512
        and len(rows) == 13
        and all(row.get("cached_tokens") == 0 for row in rows)
        and all((row.get("completion_tokens") or 0) >= 100 for row in rows)
    )
    corrected_gates_pass = bool(
        bench_valid
        and scale.get("digest") == EXPECTED_SCALE_DIGEST
        and scale.get("layers") == 48
        and scale.get("scale_tensors") == 96
        and scale.get("unit_scale_count") == 0
        and target_audits == 4
        and draft_audits == 0
        and flash_markers == 1
        and fp8_engine_markers >= 1
        and runtime_errors == 0
        and cleanup.get("worker_status") == 0
        and cleanup.get("idle_status") == 0
    )
    result = {
        "schema": "laguna-fp8-kv-teacher-audit-v1",
        "run": str(args.run.resolve()),
        "classification": (
            "admissible_fp8_q1_teacher_after_reporting_gate_correction"
            if corrected_gates_pass
            else "invalid"
        ),
        "corrected_gates_pass": corrected_gates_pass,
        "not_a_throughput_record": True,
        "original_harness_status": cleanup.get("original_status"),
        "original_failure": (
            "required four logger.info_once FlashAttention markers; observed one"
        ),
        "corrected_requirement": "exactly one FlashAttention selection marker",
        "bench_valid": bench_valid,
        "target_scale_audit_passes": target_audits,
        "draft_scale_audit_passes": draft_audits,
        "flash_attention_markers": flash_markers,
        "fp8_engine_markers": fp8_engine_markers,
        "runtime_errors": runtime_errors,
        "cleanup": cleanup,
        "prompt_count": len(rows),
        "cached_tokens_all_zero": all(
            row.get("cached_tokens") == 0 for row in rows
        ),
        "teacher_bench_sha256": sha256(bench_path),
        "server_log_sha256": sha256(log_path),
        "identity_sha256": sha256(args.run / "identity.txt"),
        "checkpoint_scale_audit_sha256": sha256(scale_path),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if corrected_gates_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
