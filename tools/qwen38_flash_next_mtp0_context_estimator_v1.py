#!/usr/bin/env python3
"""Emit the frozen Grade-D TP4 eager MTP0 24K/32K estimate snapshot."""

from __future__ import annotations

import argparse
from decimal import Decimal, getcontext
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data/qwen38-flash-next-fp8-tp4-mtp0-context-estimate-v1.json"


def rounded(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.000001")))


def build_snapshot() -> dict[str, object]:
    getcontext().prec = 50
    d4 = Decimal("4.4560264746397324")
    d8 = Decimal("3.97972923995132")
    c4 = Decimal(4096)
    c8 = Decimal(8192)
    slope = (d8 / d4).ln() / (c8 / c4).ln()
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    points: list[dict[str, object]] = []
    for context in (24576, 32768):
        ratio = Decimal(context) / c8
        central = d8 * (slope * ratio.ln()).exp()
        points.append(
            {
                "active_context_tokens": context,
                "decode_tok_s": {
                    "estimate": rounded(central),
                    "lower": rounded(central * Decimal("0.50")),
                    "upper": rounded(central * Decimal("1.50")),
                    "uncertainty": {
                        "kind": "deterministic extrapolation band, not a statistical confidence interval",
                        "multipliers": [0.5, 1.5],
                    },
                },
                "evidence_grade": "D",
                "optimization_maturity": "unassessed",
            }
        )
    return {
        "format": "neural-download-estimate-snapshot-v1",
        "id": "qwen38-flash-next-fp8-tp4-mtp0-context-estimate-v1",
        "classification": "estimated-not-measured",
        "generated_at": "2026-08-28T18:00:00Z",
        "engine": {
            "id": "qwen38-flash-next-mtp0-context-estimator",
            "version": "1.0.0",
            "script": "tools/qwen38_flash_next_mtp0_context_estimator_v1.py",
            "sha256": script_sha,
            "arithmetic": "Python Decimal precision=50; log-linear extrapolation; output rounded to 6 decimals",
        },
        "method": {
            "formula": "D(c)=D8K*(c/8192)^s, where s=ln(D8K/D4K)/ln(2)",
            "anchors": [
                {
                    "measurement_id": "qwen38-flash-next-fp8-tp4-context4k-a1",
                    "active_context_tokens": 4096,
                    "decode_tok_s": rounded(d4),
                },
                {
                    "measurement_id": "qwen38-flash-next-fp8-tp4-context8k-a1",
                    "active_context_tokens": 8192,
                    "decode_tok_s": rounded(d8),
                },
            ],
            "slope": rounded(slope),
            "uncertainty": "50%-150% of the central extrapolation; deliberately wide because only two adjacent exact-depth anchors exist",
            "withheld": [
                "boot and fit",
                "quality and parity",
                "prefill and TTFT",
                "VRAM and cache capacity",
                "graph mode",
                "MTP depths above zero",
                "TP1 and TP2",
                "vision",
                "promotion and LocalMaxxing authority",
            ],
        },
        "grades": {
            "evidence": {
                "grade": "D",
                "label": "two-anchor extrapolation only",
            },
            "optimization_maturity": {
                "state": "unassessed",
                "label": "not booted or optimized at these depths",
            },
        },
        "points": points,
        "authority": {
            "estimated_cells": 2,
            "measured_cells": 0,
            "quality_cells": 0,
            "headline": False,
            "promotion": False,
            "localmaxxing_submission": False,
            "protected_value_replacement": False,
        },
        "limitations": [
            "Neither 24K nor 32K has boot, fit, request-completion, quality, or speed evidence.",
            "The central values extrapolate only the formal exact-depth MTP0 decode trend from 4K to 8K.",
            "The 16K diagnostic completion is excluded because its quarantined receipt grants no speed or curve credit.",
            "Do not transfer these estimates across TP, MTP, graph, modality, artifact, runtime, hardware, or workload.",
            "Estimated cells are not packet performance, promotion, record, or deployment evidence.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    desired = build_snapshot()
    if args.check:
        if not SNAPSHOT.exists():
            print(f"missing snapshot: {SNAPSHOT}", file=sys.stderr)
            return 1
        actual = json.loads(SNAPSHOT.read_text())
        if actual != desired:
            print(f"stale snapshot: {SNAPSHOT}", file=sys.stderr)
            return 1
        print(f"snapshot current: {SNAPSHOT.relative_to(ROOT)}")
        return 0
    print(json.dumps(desired, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
