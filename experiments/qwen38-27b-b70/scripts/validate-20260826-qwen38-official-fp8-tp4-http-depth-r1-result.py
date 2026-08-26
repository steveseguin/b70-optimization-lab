#!/usr/bin/env python3
"""Read-only validator for the official-FP8 TP4 exact-depth result."""

from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROOT = Path("/mnt/fast-ai/bench-results/qwen38-official-fp8-tp4-http-depth-20260826-r1-attempt1")
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-fp8-tp4-http-depth-r1-result.json"
DEPTHS = [2048, 4096, 8192, 16384, 24576, 32768]

def load(path): return json.loads(path.read_text(encoding="utf-8"))
def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""): h.update(chunk)
    return h.hexdigest()
def need(value, message):
    if not value: raise RuntimeError(message)

def validate(root, result_path):
    result = load(result_path)
    need(result["status"] == "passed-qualified-exact-depth", "compact result is not passed")
    for binding in result["tracked_inputs"].values():
        path = REPO / binding["path"]
        need(path.is_file() and digest(path) == binding["sha256"], f"tracked input changed: {path}")
    summary = load(root / "summary.json")
    need(digest(root / "summary.json") == result["raw_summary_sha256"], "raw summary changed")
    need(digest(root / "result-sha256sums.txt") == result["raw_result_manifest_sha256"], "raw result manifest changed")
    need(summary["classification"] == "qualified-exact-depth", "raw summary classification changed")
    cells = []
    for depth in DEPTHS:
        raw_path = root / f"depth-{depth}.json"
        raw = load(raw_path)
        need(raw == load(root / f"depth-{depth}.stdout.json"), f"stdout mirror changed: {depth}")
        need(raw["gate"]["passed"] and all(raw["gate"]["checks"].values()), f"depth gate failed: {depth}")
        usage = raw["response"]["usage"]
        need(usage["prompt_tokens"] == depth and usage["completion_tokens"] == 128, f"usage changed: {depth}")
        need(usage["prompt_tokens_details"]["cached_tokens"] == 0, f"cache reuse appeared: {depth}")
        cells.append({"x": depth, "decode_tok_s": raw["metric_window"]["conventional_99_interval_tok_s"], "ttft_ms": raw["metric_window"]["time_to_first_token_s"] * 1000, "effective_prompt_throughput_proxy_tok_s": depth / raw["metric_window"]["time_to_first_token_s"], "cached_tokens": 0, "output_token_ids_sha256": raw["response"]["output_token_ids_sha256"], "raw_sha256": digest(raw_path)})
    need(cells == result["points"], "compact points differ from raw receipts")
    need([point["active_context_tokens"] for point in summary["points"]] == DEPTHS, "raw summary depths changed")
    verification = load(root / "model-verification.json")
    need(verification["status"] == "verified" and verification["files_verified"] == 66, "model verification changed")
    need(verification["direct_mode"] == "strict O_DIRECT; no fallback" and verification["paths_coherent"], "model verification weakened")
    need((root / "cleanup-status.txt").read_text().strip() == "clean", "cleanup is not clean")
    need(result["authority"]["site_cells"] == 6 and not result["authority"]["headline_or_protected_replacement"], "authority widened")
    need(result["authority"]["protected_decode_values_unchanged"] == [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144], "protected values changed")
    return {"status":"pass", "cells_verified":6, "cleanup":"clean", "site_cells_authorized":6, "headline_replacement":False}

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--root", type=Path, default=ROOT); parser.add_argument("--result", type=Path, default=RESULT); args = parser.parse_args()
    try: report = validate(args.root, args.result)
    except (KeyError, OSError, TypeError, ValueError, RuntimeError, json.JSONDecodeError) as exc: parser.error(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True)); return 0
if __name__ == "__main__": raise SystemExit(main())
