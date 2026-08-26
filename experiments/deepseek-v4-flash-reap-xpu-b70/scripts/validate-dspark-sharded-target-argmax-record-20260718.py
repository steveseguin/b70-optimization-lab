#!/usr/bin/env python3
"""Read-only validator for the 2026-07-18 DeepSeek 80.820 record receipt."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
RECEIPT = REPO / "experiments/deepseek-v4-flash-reap-xpu-b70/data/dspark-sharded-target-argmax-record-20260718-raw-receipt.json"
RESULT = REPO / "experiments/deepseek-v4-flash-reap-xpu-b70/data/dspark-sharded-target-argmax-record-20260718.json"
CLAIM = REPO / "claims/lab-deepseek-v4-flash-fp8fp4-dspark7-tp4.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def main() -> None:
    receipt = load(RECEIPT)
    result = load(RESULT)
    claim = load(CLAIM)
    root = Path(receipt["raw_root"])
    rows = receipt["files"]

    require(receipt["expected_file_count"] == len(rows) == 14, "receipt file count")
    require(len({row["path"] for row in rows}) == len(rows), "duplicate receipt path")
    require(root.is_dir(), f"raw root missing: {root}")
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    expected = {row["path"] for row in rows}
    require(actual == expected, f"raw inventory differs: missing={sorted(expected - actual)}, extra={sorted(actual - expected)}")

    for row in rows:
        path = root / row["path"]
        require(path.stat().st_size == row["bytes"], f"size differs: {row['path']}")
        require(sha256(path) == row["sha256"], f"SHA-256 differs: {row['path']}")

    measurement = receipt["measurement"]
    require(result["record_tok_s"] == measurement["strict_suite_high_tok_s"], "record high binding")
    require(result["strict_suite_medians_tok_s"] == measurement["strict_suite_medians_tok_s"], "suite medians binding")
    require(result["strict_suite_median_of_medians_tok_s"] == measurement["strict_suite_median_of_medians_tok_s"], "median-of-medians binding")
    require(result["realistic_requests_cached_zero"] == measurement["realistic_requests_cached_zero"] == 36, "cache-zero binding")
    require(result["exact_canary_passes"] == measurement["exact_canary_passes"] == 24, "exact-canary binding")
    require(result["localmaxxing_id"] == receipt["localmaxxing_id"] == "cmrquta9905w3lg013m5vxoqx", "LocalMaxxing binding")
    require(claim["claimed"]["date"] == claim["verification"]["date"] == "2026-07-18", "claim date")
    require(claim["claimed"]["tok_s"] == claim["verification"]["tok_s"] == 80.82, "historical claim preserved")
    require(claim["verification"]["evidence"] == receipt["bound_result"], "direct evidence link")

    print("PASS: DeepSeek 2026-07-18 raw receipt, result, claim, and LocalMaxxing identity are consistent")


if __name__ == "__main__":
    main()
