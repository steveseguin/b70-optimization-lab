#!/usr/bin/env python3
"""Build the frozen Qwen3.8 Q8_0-weights/Q8_0-KV TP1 estimate snapshot."""

from __future__ import annotations

import argparse
from decimal import Decimal, getcontext
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ENGINE_ID = "qwen38-q8weights-q8kv-context-estimator"
ENGINE_VERSION = "1.0.0"
SNAPSHOT_ID = "qwen38-q8weights-q8kv-tp1-context-estimate-v1"
DEPTHS = [0, 2048, 4096, 8192, 16384, 24576, 32768]
DONOR_RUNTIME_COMMIT = "9fee29e9435f865ec0b811a783a6471a136d9317"
DONOR_BINARY_SHA256 = "ff2441d012488e3cf7fc537a3e7c1a05fea9159043f3f3a0b257f6647e7c6964"
UNCERTAINTY_EXPANSION = Decimal("0.05")
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "data/qwen38-q8weights-q8kv-tp1-context-estimate-v1.json"

SOURCE_HASHES = {
    "experiments/qwen38-27b-b70/data/qwen38-q8weights-f16-tp1-local-20260825-r2/result.json":
        "43a911b11dfe135180361d8ce24870bc6898d60416ef5ca17b09a1b530e795c2",
    "experiments/qwen38-27b-b70/data/qwen38-q8weights-f16-tp1-local-20260825-r2/command.txt":
        "6f80d02e551b651587f7a812e8018f24d006213c44ed7d78605ec12ecadf7b9c",
    "experiments/qwen38-27b-b70/data/qwen38-q8weights-f16-tp1-local-20260825-r2/environment.txt":
        "a442ebbfd36720142322f0b35c539de6882bc4e76e8718a1fcc6098e703eaf62",
    "experiments/qwen38-27b-b70/data/qwen38-q8weights-f16-tp1-local-20260825-r2/sha256sums.txt":
        "a7d5579a5a1a3b1c92bd28524099a4d256dedc26955250032c295008bb4ffa02",
    "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q5ks-f16kv-tp1-target-http-depth-quality-r1-result.json":
        "ee8cb67112e753832a62cdcb5d5449f5def065da0fbf83cbc8122cd7a193eda4",
    "experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q5ks-q8kv-tp1-target-http-depth-quality-r1-result.json":
        "2653041587bb80a1ea2c08d177114911d9cf60a2d379baa782a416396a7f0cd3",
    "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q4kxl-f16kv-tp1-target-http-depth-quality-r1-result.json":
        "9b824989b7f0856da27871f794c28e0362251ee82709840e75a80746426996af",
    "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q4kxl-q8kv-tp1-target-http-depth-quality-r1-result.json":
        "00aa8a92c0a7b3f7faccb03db3c3847b63e96979278487e4435d5ae1a5104ec2",
    "repro/qwen38-27b-q8-tp1-b70/model-direct.json":
        "189104e9d795fca60fa437da69f07b7bac5705effc819a00fbd08e26ef5d7888",
}

getcontext().prec = 50


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_decimal_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle, parse_float=Decimal)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def decimal_number(value: Decimal, places: int = 6) -> float:
    quantum = Decimal(1).scaleb(-places)
    return float(value.quantize(quantum))


def serving_points(value: dict[str, Any], label: str) -> dict[int, Decimal]:
    require(value.get("status") == "passed", f"{label} did not pass")
    identity = value.get("identity") or {}
    runtime = identity.get("runtime") or {}
    require(runtime.get("source_commit") == DONOR_RUNTIME_COMMIT, f"{label} runtime commit changed")
    require(runtime.get("binary_sha256") == DONOR_BINARY_SHA256, f"{label} binary changed")
    cells = (value.get("serving_curve") or {}).get("cells") or []
    points = {
        cell["active_context_tokens"]: cell["serving_decode_tok_s_99_interval"]
        for cell in cells
    }
    require(sorted(points) == DEPTHS, f"{label} depth axis incomplete")
    require(all(cell.get("cached_tokens") == 0 for cell in cells), f"{label} is not cache zero")
    return points


def estimate_metric(
    target_f16: Decimal,
    q5ks_f16: Decimal,
    q5ks_q8: Decimal,
    q4kxl_f16: Decimal,
    q4kxl_q8: Decimal,
) -> dict[str, Any]:
    q5ks_ratio = q5ks_q8 / q5ks_f16
    q4kxl_ratio = q4kxl_q8 / q4kxl_f16
    central_ratio = (q5ks_ratio * q4kxl_ratio).sqrt()
    donor_low = min(q5ks_ratio, q4kxl_ratio)
    donor_high = max(q5ks_ratio, q4kxl_ratio)
    low_ratio = donor_low * (Decimal(1) - UNCERTAINTY_EXPANSION)
    high_ratio = donor_high * (Decimal(1) + UNCERTAINTY_EXPANSION)
    central = target_f16 * central_ratio
    low = target_f16 * low_ratio
    high = target_f16 * high_ratio
    return {
        "estimate": decimal_number(central),
        "lower": decimal_number(low),
        "upper": decimal_number(high),
        "donor_ratios": {
            "ud_q5_k_s": decimal_number(q5ks_ratio, 9),
            "ud_q4_k_xl": decimal_number(q4kxl_ratio, 9),
            "geometric_mean": decimal_number(central_ratio, 9),
        },
        "uncertainty": {
            "donor_ratio_low": decimal_number(donor_low, 9),
            "donor_ratio_high": decimal_number(donor_high, 9),
            "extra_multiplicative_expansion_each_side": decimal_number(UNCERTAINTY_EXPANSION, 4),
            "kind": "same-runtime two-donor envelope expanded by five percent; not a statistical confidence interval",
        },
    }


def build_snapshot() -> dict[str, Any]:
    for relative_path, expected_hash in SOURCE_HASHES.items():
        require(sha256(REPO_ROOT / relative_path) == expected_hash, f"frozen source hash mismatch: {relative_path}")

    target_path = REPO_ROOT / next(path for path in SOURCE_HASHES if path.endswith("/result.json"))
    q5_f16_path = REPO_ROOT / next(path for path in SOURCE_HASHES if "q5ks-f16kv" in path)
    q5_q8_path = REPO_ROOT / next(path for path in SOURCE_HASHES if "q5ks-q8kv" in path)
    q4_f16_path = REPO_ROOT / next(path for path in SOURCE_HASHES if "q4kxl-f16kv" in path)
    q4_q8_path = REPO_ROOT / next(path for path in SOURCE_HASHES if "q4kxl-q8kv" in path)
    model_manifest_path = REPO_ROOT / next(path for path in SOURCE_HASHES if path.endswith("model-direct.json"))

    target = load_decimal_json(target_path)
    require(target.get("classification") == "complete-raw-engine", "Q8_0/F16 target anchor classification changed")
    target_rows = [
        row for row in target.get("rows", [])
        if row.get("n_gen") == 128 and row.get("n_prompt") == 0
    ]
    require([row.get("n_depth") for row in target_rows] == DEPTHS, "Q8_0/F16 target depth axis changed")
    require(all(row.get("type_k") == "f16" and row.get("type_v") == "f16" for row in target_rows),
            "Q8_0 target anchor is not F16 KV")
    require(all(row.get("build_commit") == "4302fb599" for row in target_rows),
            "Q8_0 target raw runtime changed")
    target_f16 = {row["n_depth"]: row["avg_ts"] for row in target_rows}

    q5_f16 = serving_points(load_decimal_json(q5_f16_path), "Q5_K_S/F16")
    q5_q8 = serving_points(load_decimal_json(q5_q8_path), "Q5_K_S/Q8")
    q4_f16 = serving_points(load_decimal_json(q4_f16_path), "Q4_K_XL/F16")
    q4_q8 = serving_points(load_decimal_json(q4_q8_path), "Q4_K_XL/Q8")

    model_manifest = load_decimal_json(model_manifest_path)
    files = model_manifest.get("lfs_files") or []
    require(len(files) == 1, "Q8_0 model manifest shape changed")
    model = files[0]
    require(model.get("sha256") == "f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8",
            "Q8_0 model identity changed")

    sha_receipt = (REPO_ROOT / "experiments/qwen38-27b-b70/data/qwen38-q8weights-f16-tp1-local-20260825-r2/sha256sums.txt").read_text(encoding="utf-8")
    require("f8fe61241c010d91dba839ff3d5505def9ba569ae98c0ca498efc01b5fb4e2f0" in sha_receipt,
            "Q8_0/F16 target llama-bench identity changed")
    require(model["sha256"] in sha_receipt, "Q8_0 target model receipt changed")

    points = []
    for depth in DEPTHS:
        points.append({
            "active_context_tokens": depth,
            "target_f16_anchor": {
                "decode_tok_s": decimal_number(target_f16[depth]),
                "runtime_commit_short": "4302fb599",
                "workload": "llama-bench tg128, five repetitions",
            },
            "decode_tok_s": estimate_metric(
                target_f16[depth], q5_f16[depth], q5_q8[depth], q4_f16[depth], q4_q8[depth]
            ),
            "evidence_grade": "D",
            "optimization_maturity": "unassessed",
        })

    script_path = Path(__file__).resolve()
    return {
        "format": "neural-download-estimate-snapshot-v1",
        "id": SNAPSHOT_ID,
        "snapshot_date": "2026-08-26",
        "state": "estimated",
        "classification": "estimated-not-measured",
        "grades": {
            "evidence": {
                "grade": "D",
                "label": "calibrated estimate only",
                "reason": "No Q8_0-weight/Q8_0-KV target run exists; values transfer matched KV penalties from two same-runtime sibling artifacts onto the measured Q8_0-weight/F16 anchor.",
            },
            "optimization_maturity": {
                "state": "unassessed",
                "label": "not optimized or benchmarked",
                "reason": "An estimated speed is not evidence that this tuple boots, passes quality, or has received optimization work.",
            },
        },
        "selectors": {
            "revision": "qwen3.8-27b",
            "artifact_id": "qwen38-27b-ggmlorg-q8-0-0669b98",
            "quantization": "Q8_0",
            "runtime_family": "llama.cpp SYCL",
            "tp": 1,
            "mtp": 0,
            "graph_mode": "off",
            "kv": "q8_0",
        },
        "target_identity": {
            "repository": model_manifest["repository"],
            "revision": model_manifest["revision"],
            "file": model["path"],
            "bytes": model["bytes"],
            "sha256": model["sha256"],
        },
        "workload": "estimated raw-engine llama-bench tg128 at seven exact active-depth points; not HTTP serving",
        "method": {
            "central_formula": "Q8weights_F16_raw * sqrt((Q5_Q8_HTTP/Q5_F16_HTTP) * (Q4XL_Q8_HTTP/Q4XL_F16_HTTP))",
            "uncertainty_formula": "Q8weights_F16_raw * [0.95 * min(donor ratios), 1.05 * max(donor ratios)]",
            "uncertainty_kind": "same-runtime two-donor envelope plus a conservative five-percent multiplicative expansion; not a statistical confidence interval",
            "same_runtime_donor_requirement": {
                "runtime_commit": DONOR_RUNTIME_COMMIT,
                "binary_sha256": DONOR_BINARY_SHA256,
                "workload": "HTTP exact-depth, 128 generated tokens, cache zero, conventional 99-interval decode",
            },
            "target_anchor_runtime": {
                "commit_short": "4302fb599",
                "binary_sha256": "f8fe61241c010d91dba839ff3d5505def9ba569ae98c0ca498efc01b5fb4e2f0",
                "workload": "llama-bench tg128, five repetitions",
            },
            "mismatch_disclosure": "The donor ratios are internally same-runtime and same-workload, but they are transferred onto a different sealed raw-engine target anchor; Grade D and the expanded band reflect that mismatch.",
            "estimated_metrics": ["decode_tok_s"],
            "withheld_metrics": ["quality", "HTTP serving decode", "prefill", "TTFT", "VRAM", "fit", "determinism"],
        },
        "engine": {
            "id": ENGINE_ID,
            "version": ENGINE_VERSION,
            "script": str(script_path.relative_to(REPO_ROOT)),
            "sha256": sha256(script_path),
            "arithmetic": "Python Decimal, precision=50, geometric mean, output rounded to 6 decimals",
        },
        "sources": [
            {"path": path, "sha256": digest}
            for path, digest in SOURCE_HASHES.items()
        ],
        "points": points,
        "authority": {
            "estimated_cells": 7,
            "measured_cells": 0,
            "quality_cells": 0,
            "promotion": False,
            "headline": False,
            "protected_value_replacement": False,
            "localmaxxing_submission": False,
        },
        "limitations": [
            "No Q8_0-weight/Q8_0-KV run is measured; every central value and interval is an estimate.",
            "The target F16 anchor is raw-engine build 4302fb599 while donor ratios are same-binary HTTP measurements on 9fee29e; workload and runtime transfer may exceed the displayed interval.",
            "Only two sibling artifacts define the ratio envelope; Q8_0-weight behavior may differ.",
            "Evidence grade D is distinct from optimization maturity, which is unassessed.",
            "No quality, boot, fit, determinism, HTTP serving, prefill, TTFT, VRAM, record, or promotion claim is authorized.",
            "Do not transfer these values across revisions, artifacts, TP, MTP, graph mode, KV dtype, runtime, workload, or hardware.",
        ],
    }


def rendered_snapshot() -> str:
    return json.dumps(build_snapshot(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--stdout", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = rendered_snapshot()
    if args.stdout:
        sys.stdout.write(rendered)
        return 0
    output = args.output.resolve()
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != rendered:
            print(f"estimate snapshot differs: {output}", file=sys.stderr)
            return 1
        print(f"estimate snapshot is deterministic: {output}")
        return 0
    output.write_text(rendered, encoding="utf-8")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
