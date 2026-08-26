#!/usr/bin/env python3
"""Read-only validator for the official-FP8 TP1 eager fit/depth R2 result."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CAMPAIGN = "qwen38-official-fp8-tp1-fit-depth-20260826-r2"
ROOT = Path("/mnt/fast-ai/bench-results") / CAMPAIGN
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-fp8-tp1-fit-depth-r2-result.json"
DEPTHS = [2048, 4096, 8192]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def need(value, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def validate(root: Path, result_path: Path) -> dict:
    result = load(result_path)
    need(result["campaign_id"] == CAMPAIGN, "campaign identity changed")
    need(result["status"] == "passed-bounded-fit-depth", "result is not passed")
    for binding in result["tracked_inputs"].values():
        path = REPO / binding["path"]
        need(path.is_file() and digest(path) == binding["sha256"], f"tracked input changed: {path}")

    expected = result["raw_artifacts"]["sha256"]
    actual = sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())
    need(len(expected) == result["raw_artifacts"]["file_count"] == 20, "raw file count changed")
    need(actual == sorted(expected), "raw inventory changed")
    for relative, sha256 in expected.items():
        need(digest(root / relative) == sha256, f"raw hash changed: {relative}")

    verification = load(root / "model-verification.json")
    need(verification["status"] == "verified", "model verification failed")
    need(verification["files_verified"] == 66, "weight count changed")
    need(verification["bytes_verified_each_read_path"] == 30866866928, "verified byte count changed")
    need(verification["direct_mode"] == "strict O_DIRECT; no fallback", "direct verification weakened")
    need(verification["paths_coherent"], "model read paths diverged")

    cells = []
    for depth in DEPTHS:
        raw = load(root / f"fit-8k/depth-{depth}.json")
        need(raw == load(root / f"fit-8k/depth-{depth}.stdout.json"), f"stdout mirror changed: {depth}")
        need(raw["gate"]["passed"] and all(raw["gate"]["checks"].values()), f"depth gate failed: {depth}")
        usage = raw["response"]["usage"]
        need(usage["prompt_tokens"] == depth, f"prompt depth changed: {depth}")
        need(usage["completion_tokens"] == 128, f"completion length changed: {depth}")
        need(usage["prompt_tokens_details"]["cached_tokens"] == 0, f"cache reuse appeared: {depth}")
        cells.append({
            "x": depth,
            "decode_tok_s": raw["metric_window"]["conventional_99_interval_tok_s"],
            "ttft_ms": raw["metric_window"]["time_to_first_token_s"] * 1000,
            "cached_tokens": 0,
            "completion_tokens": 128,
            "output_token_ids_sha256": raw["response"]["output_token_ids_sha256"],
            "raw_sha256": digest(root / f"fit-8k/depth-{depth}.json"),
        })
    need(cells == result["cells"], "compact cells differ from raw receipts")

    arm = load(root / "fit-8k/arm-result.json")
    need(arm["status"] == "completed-awaiting-terminal", "arm status changed")
    need(arm["first_supported_depth"] == 8192 and arm["context_capacity_tokens"] == 8448, "fit boundary changed")
    terminal = load(root / "terminal-receipt.json")
    need(terminal["status"] == "completed-valid-bounded-fit-depth", "terminal status changed")
    need(terminal["authority"]["official_fp8_tp1_grade_c_cells"] == 3, "terminal cell authority changed")
    need(not terminal["authority"]["headline_or_protected_replacement"], "terminal widened headline authority")
    need(not terminal["authority"]["localmaxxing_submission"], "terminal widened submission authority")
    need(result["authority"]["protected_decode_values_unchanged"] == [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144], "protected values changed")
    return {"status": "pass", "raw_files_verified": 20, "cells_verified": 3, "first_supported_depth": 8192, "site_cells_authorized": 3}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--result", type=Path, default=RESULT)
    args = parser.parse_args()
    try:
        report = validate(args.root, args.result)
    except (KeyError, OSError, TypeError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
