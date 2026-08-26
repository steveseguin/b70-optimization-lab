#!/usr/bin/env python3
"""Validate the compact Q4_K_M/F16-KV cache64 graph result against raw evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q4km-f16kv-tp1-sycl-graph-cache64-depth-quality-r1-result.json"
ROOT = Path("/mnt/fast-ai/bench-results/qwen38-q4km-f16kv-tp1-sycl-graph-cache64-depth-quality-20260826-r1")
DEPTHS = (0, 2048, 4096, 8192, 16384, 24576, 32768)
TERMINAL_SHA = "1eec5de2920ddd152a960b8f5ea522b6c63c848fc6f4fc9ee354386b44919eb4"


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
    terminal = load(ROOT / "terminal-receipt.json")
    identity = load(ROOT / "identity.json")
    quality = load(ROOT / "target-mtp0-graph-cache64/quality.json")
    cleanup = load(ROOT / "target-mtp0-graph-cache64/cleanup.json")
    arm = load(ROOT / "target-mtp0-graph-cache64/arm-result.json")
    graph = load(ROOT / "target-mtp0-graph-cache64/graph-evidence.json")

    assert sha(ROOT / "terminal-receipt.json") == TERMINAL_SHA == result["raw_artifacts"]["sha256"]["terminal-receipt.json"]
    assert result["status"] == "passed"
    assert terminal["status"] == result["validation"]["terminal_status"] == "completed-valid-q4km-f16kv-graph-cache64-depth-quality"
    assert len(terminal["checks"]) == result["validation"]["terminal_checks_total"] == 19
    assert sum(value is True for value in terminal["checks"].values()) == result["validation"]["terminal_checks_passed"] == 19
    assert result["authority"] == terminal["authority"]
    assert result["identity"]["git_head_and_origin_main_at_launch"] == identity["git_head"] == identity["origin_main"]
    assert result["identity"]["model"]["sha256"] == identity["model"]["sha256"]
    assert result["identity"]["runtime"]["binary_sha256"] == identity["runtime"]["binary_sha256"]
    assert result["identity"]["runtime"]["graph_backend_sha256"] == identity["runtime"]["graph_backend_sha256"]
    assert cleanup == {"forced_kill": False, "port_closed": True, "render_node_idle": True, "server_survivor": False}
    assert arm["cleanup"] == cleanup and arm["error"] is None

    for compact, terminal_cell, depth in zip(result["serving_curve"]["cells"], terminal["cells"], DEPTHS, strict=True):
        raw_path = ROOT / f"target-mtp0-graph-cache64/depth-{depth}/exact-depth.json"
        raw = load(raw_path)
        assert compact["active_context_tokens"] == terminal_cell["active_context_tokens"] == depth
        assert compact["serving_decode_tok_s_99_interval"] == terminal_cell["serving_decode_tok_s_99_interval"] == raw["metric_window"]["conventional_99_interval_tok_s"]
        assert compact["time_to_first_token_s"] == raw["metric_window"]["time_to_first_token_s"]
        assert compact["output_token_ids_sha256"] == terminal_cell["output_token_ids_sha256"] == raw["response"]["output_token_ids_sha256"]
        assert compact["text_sha256"] == raw["response"]["text_sha256"]
        assert compact["receipt_sha256"] == sha(raw_path)
        assert compact["cached_tokens"] == terminal_cell["cached_tokens"] == raw["response"]["usage"]["prompt_tokens_details"]["cached_tokens"] == 0
        assert compact["completion_tokens"] == raw["response"]["usage"]["completion_tokens"] == 128

    assert quality["pass_all"]
    assert len(quality["exact_cases"]) == result["quality"]["exact_cases"]["passed"] == 7
    assert all(item["pass"] and item["usage"]["prompt_tokens_details"]["cached_tokens"] == 0 for item in quality["exact_cases"])
    repeat = quality["repeat_case"]
    needle = quality["long_context_case"]
    assert repeat["pass"] and repeat["repeats"] == result["quality"]["repeat_stability"]["runs"] == 2
    assert repeat["unique_hashes"] == [result["quality"]["repeat_stability"]["output_sha256"]]
    assert needle["pass"] and needle["actual_prompt_tokens"] == result["quality"]["long_context_needle"]["actual_prompt_tokens_before_chat_template"] == 25200
    assert needle["usage"]["prompt_tokens"] == result["quality"]["long_context_needle"]["api_usage_prompt_tokens"] == 25212
    assert graph["direct_replay"] == result["graph_mechanism"]["direct_replay"] == 947
    assert graph["cache_limit"] == result["graph_mechanism"]["cache_limit"] == 64
    assert graph["direct_replay"] >= result["graph_mechanism"]["minimum_direct_replays"] == 896
    assert graph["requested"] == graph["cache_hit"] + graph["cache_miss"] == graph["replayed"] + graph["cache_full"]
    assert graph["recorded"] == graph["created"] == graph["cache_entries"]
    assert graph["replayed"] == graph["cache_hit"] + graph["created"]
    assert all(graph[key] == 0 for key in ("compatibility_rejected", "device_unsupported", "updated", "recreated"))

    assert sum(1 for path in ROOT.rglob("*") if path.is_file()) == result["raw_artifacts"]["file_count"] == 25
    for relative, expected in result["raw_artifacts"]["sha256"].items():
        assert sha(ROOT / relative) == expected
    print("PASS: compact Q4_K_M/F16-KV cache64 graph result matches all 25 raw artifacts and 19 terminal checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
