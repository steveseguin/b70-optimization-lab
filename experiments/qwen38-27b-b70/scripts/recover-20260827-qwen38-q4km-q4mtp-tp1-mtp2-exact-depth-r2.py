#!/usr/bin/env python3
"""Create-only, report-only recovery for the sealed Q4 MTP2 R2 depth run."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
PREREG = REPO / "experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q4km-q4mtp-tp1-mtp2-exact-depth-r2-report-recovery-prereg.json"
ORACLE = REPO / "experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q4km-tp1-mtp0-exact-depth-token-oracle.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def metric(text: str, name: str) -> float | None:
    for line in text.splitlines():
        if line.startswith(name + " "):
            return float(line.split()[-1])
    return None


def compose(root: Path) -> dict:
    prereg = load(PREREG)
    if prereg.get("state") != "preregistered-report-only-not-run":
        raise ValueError("recovery preregistration state changed")
    for name, expected in prereg["sealed_inputs"].items():
        path = root / name
        if not path.is_file() or sha(path) != expected:
            raise ValueError(f"sealed input mismatch: {name}")
    oracle = {row["active_context_tokens"]: row for row in load(ORACLE)["points"]}
    points = []
    for depth in (2048, 4096, 8192, 16384, 24576, 32768):
        row = load(root / f"depth-{depth}.json")
        exact = row["response"]["output_token_ids_sha256"] == oracle[depth]["output_token_ids_sha256"]
        checks = row.get("gate", {}).get("checks", {})
        if row.get("status") != "passed" or not checks or not all(checks.values()):
            raise ValueError(f"depth receipt gate failed: {depth}")
        decode = row["metric_window"]["conventional_99_interval_tok_s"]
        ttft = row["metric_window"]["time_to_first_token_s"] * 1000
        if not math.isfinite(decode) or not math.isfinite(ttft):
            raise ValueError(f"non-finite metric: {depth}")
        points.append({
            "active_context_tokens": depth,
            "decode_tok_s": decode,
            "ttft_ms": ttft,
            "target_oracle_exact": exact,
            "state": "lab-measured-grade-d" if exact else "quarantined-output-divergence",
            "output_token_ids_sha256": row["response"]["output_token_ids_sha256"],
        })
    canaries = load(root / "canaries.json")
    if canaries.get("pass_all") is not True:
        raise ValueError("objective canaries failed")
    metrics = (root / "metrics-after.txt").read_text(encoding="utf-8")
    drafted = metric(metrics, "llamacpp:spec_decode_num_draft_tokens_total")
    accepted = metric(metrics, "llamacpp:spec_decode_num_accepted_tokens_total")
    if drafted is None or accepted is None or drafted <= 0 or accepted <= 0:
        raise ValueError("draft counters missing or nonpositive")
    exact_depths = [row["active_context_tokens"] for row in points if row["target_oracle_exact"]]
    divergent_depths = [row["active_context_tokens"] for row in points if not row["target_oracle_exact"]]
    if exact_depths != [4096, 8192, 16384, 24576, 32768] or divergent_depths != [2048]:
        raise ValueError("observed exact/divergent boundary changed")
    return {
        "schema": "neural.download.qwen38-q4km-q4mtp-tp1-mtp2-exact-depth-result.v1",
        "campaign_id": "qwen38-q4km-q4mtp-tp1-mtp2-exact-depth-20260827-r2",
        "status": "failed-partial-2k-quarantined",
        "classification": "Grade D partial exact-context/TTFT coverage",
        "points": points,
        "exact_depths": exact_depths,
        "quarantined_depths": divergent_depths,
        "canaries_passed": True,
        "draft_counters": {"drafted": drafted, "accepted": accepted, "acceptance_rate": accepted / drafted},
        "report_recovery": {"gpu_actions": 0, "http_requests": 0, "sealed_inputs_verified": len(prereg["sealed_inputs"]), "source_failure_preserved": "terminal-receipt.json"},
        "publication_boundary": "Only exact 4K-32K cells may be published as Grade D partial coverage. The 2K cell is quarantined. Synthetic repeated-token shape fixture; no interpolation, extrapolation, natural-prose headline, or whole-profile pass."
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = compose(args.root)
    if args.output is None:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
