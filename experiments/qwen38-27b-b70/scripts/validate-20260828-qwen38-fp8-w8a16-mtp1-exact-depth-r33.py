#!/usr/bin/env python3
"""Recompute the compact R33 MTP1 exact-depth result from tracked evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
RESULT = LANE / "data/2026-08-28-qwen38-fp8-w8a16-mtp1-exact-depth-r33-result.json"
RAW = LANE / "data/qwen38-fp8-w8a16-mtp1-exact-depth-20260828-r33"
TARGET = LANE / "data/qwen38-fp8-block-w8a16-tp2-http-depth-20260826-r2"
DEPTHS = (2048, 4096, 8192, 16384, 24576, 32768)


def load(path: Path):
    return json.loads(path.read_text())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def need(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    result = load(RESULT)
    need(result["status"] == "qualified-grade-c-exact-depth", "status changed")
    need(result["gates"]["public_32k_cell_eligible"] is True, "32K gate changed")
    need(result["gates"]["strict_natural_prompt_headline_eligible"] is False, "headline boundary changed")
    need(result["gates"]["localmaxxing_eligible"] is False, "submission boundary changed")
    need([point["active_context_tokens"] for point in result["points"]] == list(DEPTHS), "depth axis changed")

    for point in result["points"]:
        depth = point["active_context_tokens"]
        raw_path = RAW / f"exact-depth/depth-{depth}.json"
        raw = load(raw_path)
        target = load(TARGET / f"depth-{depth}.json")
        need(raw["status"] == "passed" and raw["gate"]["passed"], f"raw gate failed: {depth}")
        need(raw["gate"]["checks"]["cached_tokens_zero"], f"cache gate failed: {depth}")
        need(len(raw["response"]["token_ids"]) == 128, f"token count changed: {depth}")
        need(raw["response"]["token_ids"] == target["response"]["token_ids"], f"target parity failed: {depth}")
        need(raw["response"]["output_token_ids_sha256"] == point["output_token_ids_sha256"], f"output hash changed: {depth}")
        need(raw["metric_window"]["conventional_99_interval_tok_s"] == point["decode_tok_s"], f"decode changed: {depth}")
        need(raw["metric_window"]["time_to_first_token_s"] * 1000 == point["ttft_ms"], f"TTFT changed: {depth}")
        expected_proxy = depth / raw["metric_window"]["time_to_first_token_s"]
        need(expected_proxy == point["effective_prompt_throughput_proxy_tok_s"], f"prompt proxy changed: {depth}")
        need(sha256(raw_path) == point["raw_sha256"], f"raw receipt changed: {depth}")

    metrics = (RAW / "metrics.prom").read_text()
    need('vllm:spec_decode_num_draft_tokens_total{engine="0",model_name="qwen38-fp8"} 429.0' in metrics, "draft total changed")
    need('vllm:spec_decode_num_accepted_tokens_total{engine="0",model_name="qwen38-fp8"} 336.0' in metrics, "accepted total changed")
    log = (RAW / "server.log").read_text()
    need("VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT armed (r30)" in log, "RMS treatment marker missing")
    need("Triton kernel JIT compilation during inference: eagle_prepare_next_token_padded_kernel" in log, "2K JIT caveat missing")
    need("Application shutdown complete" in log, "clean shutdown marker missing")
    print("PASS: R33 has six cache-zero exact-depth points, all target-token exact")


if __name__ == "__main__":
    main()
