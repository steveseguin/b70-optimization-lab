#!/usr/bin/env python3
"""Validate compact Q8_0-weight/Q8_0-KV evidence and estimator calibration."""

from __future__ import annotations
import hashlib, json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q8weights-q8kv-tp1-target-http-depth-quality-r1-result.json"
CALIBRATION = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q8weights-q8kv-tp1-estimator-calibration-r1.json"
ESTIMATE = REPO / "data/qwen38-q8weights-q8kv-tp1-context-estimate-v1.json"
ROOT = Path("/mnt/fast-ai/bench-results/qwen38-q8weights-q8kv-tp1-target-http-depth-quality-20260826-r1")
DEPTHS = (0, 2048, 4096, 8192, 16384, 24576, 32768)
TERMINAL_SHA = "a48968624a9b167e2e997031b8dfadc4af91d89dd0e838e76351cd0c96cf3f4e"

def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()

def main() -> int:
    result = load(RESULT)
    calibration = load(CALIBRATION)
    estimate = load(ESTIMATE)
    terminal = load(ROOT / "terminal-receipt.json")
    identity = load(ROOT / "identity.json")
    quality = load(ROOT / "target-mtp0/quality.json")
    cleanup = load(ROOT / "target-mtp0/cleanup.json")
    arm = load(ROOT / "target-mtp0/arm-result.json")
    assert sha(ROOT / "terminal-receipt.json") == TERMINAL_SHA == result["raw_artifacts"]["sha256"]["terminal-receipt.json"]
    assert result["status"] == "passed" and terminal["status"] == "completed-valid-target-only-q8weights-q8kv-depth-quality"
    assert result["identity"]["git_head"] == result["identity"]["origin_main"] == identity["git_head"] == identity["origin_main"]
    assert result["identity"]["model"]["sha256"] == identity["model"]["sha256"]
    assert result["identity"]["runtime"]["binary_sha256"] == identity["runtime"]["binary_sha256"]
    assert set(result["validation"]["checks"]) == set(terminal["checks"]) and len(terminal["checks"]) == 16 and all(terminal["checks"].values())
    assert cleanup == {"forced_kill":False,"port_closed":True,"render_node_idle":True,"server_survivor":False} and arm["cleanup"] == cleanup and arm["error"] is None
    for compact, cell, depth in zip(result["serving_curve"]["cells"], terminal["cells"], DEPTHS, strict=True):
        raw_path = ROOT / f"target-mtp0/depth-{depth}/exact-depth.json"
        raw = load(raw_path)
        assert compact == cell and compact["active_context_tokens"] == depth
        assert compact["serving_decode_tok_s_99_interval"] == raw["metric_window"]["conventional_99_interval_tok_s"]
        assert compact["output_token_ids_sha256"] == raw["response"]["output_token_ids_sha256"]
        assert compact["cached_tokens"] == raw["response"]["usage"]["prompt_tokens_details"]["cached_tokens"] == 0
        assert raw["response"]["usage"]["completion_tokens"] == 128
        assert sha(raw_path) == result["raw_artifacts"]["sha256"][f"target-mtp0/depth-{depth}/exact-depth.json"]
    expected_exact = {item["name"]:item["sha256"] for item in quality["exact_cases"]}
    assert result["quality"]["exact_cases"]["output_sha256"] == expected_exact
    assert quality["pass_all"] and all(item["pass"] and item["usage"]["prompt_tokens_details"]["cached_tokens"] == 0 for item in quality["exact_cases"])
    assert result["quality"]["repeat_stability"]["output_sha256"] == quality["repeat_case"]["unique_hashes"][0] and quality["repeat_case"]["pass"]
    assert result["quality"]["long_context_needle"]["output_sha256"] == quality["long_context_case"]["sha256"] and quality["long_context_case"]["pass"]
    assert sum(1 for path in ROOT.rglob("*") if path.is_file()) == result["raw_artifacts"]["file_count"] == 24
    for relative, expected in result["raw_artifacts"]["sha256"].items():
        assert sha(ROOT / relative) == expected
    assert sha(ESTIMATE) == calibration["frozen_estimate"]["sha256"]
    assert sha(RESULT) == calibration["actual_result"]["sha256"]
    assert len(calibration["points"]) == 7 and calibration["summary"]["band_hits"] == 0 and calibration["summary"]["band_misses"] == 7
    for index, row in enumerate(calibration["points"]):
        estimated = estimate["points"][index]["decode_tok_s"]
        actual = terminal["cells"][index]["serving_decode_tok_s_99_interval"]
        assert row["active_context_tokens"] == DEPTHS[index]
        assert row["estimate"] == estimated["estimate"] and row["lower"] == estimated["lower"] and row["upper"] == estimated["upper"]
        assert row["actual"] == actual and row["band_hit"] is False and actual < row["lower"]
        assert abs(row["overprediction_percent_of_actual"] - ((row["estimate"] - actual) / actual * 100)) < 1e-12
    assert result["authority"] == terminal["authority"]
    print("PASS: Q8_0-weight/Q8_0-KV compact result and negative estimator calibration match retained evidence")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
