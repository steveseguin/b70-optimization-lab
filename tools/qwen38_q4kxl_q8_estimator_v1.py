#!/usr/bin/env python3
"""Build the frozen Qwen3.8 UD-Q4_K_XL TP1 q8_0 KV estimate snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Any


ENGINE_ID = "qwen38-q4kxl-q8-context-estimator"
ENGINE_VERSION = "1.0.0"
SNAPSHOT_ID = "qwen38-q4kxl-tp1-q8-context-estimate-v1"
DEPTHS = [0, 2048, 4096, 8192, 16384, 24576, 32768]
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "data/qwen38-q4kxl-q8-tp1-context-estimate-v1.json"

SOURCE_HASHES = {
    "experiments/qwen38-27b-b70/data/2026-08-22-q4km-tp1-context-kv-sweep.json":
        "1c439bc6e46dc29ba37ed234ceb5a52758a68a10f570dc4d3efa0a03d33aa6ca",
    "experiments/qwen38-27b-b70/data/2026-08-22-qwen38-tp1-weight-ladder-sweep.json":
        "219331863fd0dee7f14f705890f373c1208b9a45d8f6d54e5e6ae2fde0ee4c26",
    "repro/qwen38-27b-256k-vision-mtp-b70/qwen38-27b-q5ks-flagship.sweep.json":
        "8f05570d712f6687bf359cfbda59d2cfb1bf31b3f573fc544f7b79f600accc09",
    "repro/qwen38-27b-256k-vision-mtp-b70/model-manifest.json":
        "7e7beaa9264400082c8ac50b6db9a50bc36ca44319d0bb6c921d923c38e285ee",
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


def estimate_metric(
    target_f16: Decimal,
    q4km_f16: Decimal,
    q4km_q8: Decimal,
    q5ks_f16: Decimal,
    q5ks_q8: Decimal,
) -> dict[str, Any]:
    q4km_ratio = q4km_q8 / q4km_f16
    q5ks_ratio = q5ks_q8 / q5ks_f16
    central_ratio = (q4km_ratio * q5ks_ratio).sqrt()
    low_ratio = min(q4km_ratio, q5ks_ratio)
    high_ratio = max(q4km_ratio, q5ks_ratio)
    central = target_f16 * central_ratio
    low = target_f16 * low_ratio
    high = target_f16 * high_ratio
    relative_half_width_pct = max(central - low, high - central) / central * 100
    return {
        "estimate": decimal_number(central),
        "lower": decimal_number(low),
        "upper": decimal_number(high),
        "donor_ratios": {
            "q4_k_m": decimal_number(q4km_ratio, 9),
            "ud_q5_k_s": decimal_number(q5ks_ratio, 9),
            "geometric_mean": decimal_number(central_ratio, 9),
        },
        "relative_half_width_pct": decimal_number(relative_half_width_pct, 4),
    }


def withheld_metric(
    q4km_f16: Decimal,
    q4km_q8: Decimal,
    q5ks_f16: Decimal,
    q5ks_q8: Decimal,
) -> dict[str, Any]:
    return {
        "state": "missing",
        "reason": "donor prefill ratios disagree and the donor builds are not identical; no defensible central estimate",
        "donor_ratios": {
            "q4_k_m": decimal_number(q4km_q8 / q4km_f16, 9),
            "ud_q5_k_s": decimal_number(q5ks_q8 / q5ks_f16, 9),
        },
    }


def build_snapshot() -> dict[str, Any]:
    for relative_path, expected_hash in SOURCE_HASHES.items():
        actual_hash = sha256(REPO_ROOT / relative_path)
        require(actual_hash == expected_hash, f"frozen source hash mismatch: {relative_path}")

    q4km_path = REPO_ROOT / next(path for path in SOURCE_HASHES if "q4km-tp1" in path)
    ladder_path = REPO_ROOT / next(path for path in SOURCE_HASHES if "weight-ladder" in path)
    q5ks_path = REPO_ROOT / next(path for path in SOURCE_HASHES if "q5ks-flagship.sweep" in path)
    manifest_path = REPO_ROOT / next(path for path in SOURCE_HASHES if path.endswith("model-manifest.json"))

    q4km = load_decimal_json(q4km_path)
    ladder = load_decimal_json(ladder_path)
    q5ks_raw = load_decimal_json(q5ks_path)
    manifest = load_decimal_json(manifest_path)

    require(q4km["depths"] == DEPTHS, "Q4_K_M depth axis changed")
    require(ladder["depths"] == DEPTHS, "weight-ladder depth axis changed")
    require(len(q5ks_raw) == len(DEPTHS) * 2, "UD-Q5_K_S q8 sweep row count changed")

    q4km_decode_f16 = q4km["decode_tg128_tok_s"]["kv_f16"]
    q4km_decode_q8 = q4km["decode_tg128_tok_s"]["kv_q8_0"]
    q4km_prefill_f16 = q4km["prefill_pp2048_tok_s"]["kv_f16"]
    q4km_prefill_q8 = q4km["prefill_pp2048_tok_s"]["kv_q8_0"]
    require(q4km_decode_f16 == ladder["variants"]["Q4_K_M"]["decode_tg128"],
            "Q4_K_M f16 decode anchors disagree")
    require(q4km_prefill_f16 == ladder["variants"]["Q4_K_M"]["prefill_pp2048"],
            "Q4_K_M f16 prefill anchors disagree")

    q5ks_decode_q8: dict[int, Decimal] = {}
    q5ks_prefill_q8: dict[int, Decimal] = {}
    for row in q5ks_raw:
        depth = row["n_depth"]
        require(depth in DEPTHS, f"unexpected UD-Q5_K_S depth: {depth}")
        require(row["type_k"] == "q8_0" and row["type_v"] == "q8_0",
                "UD-Q5_K_S donor is not q8_0 KV")
        if row["n_prompt"] == 0 and row["n_gen"] == 128:
            q5ks_decode_q8[depth] = row["avg_ts"]
        elif row["n_prompt"] == 2048 and row["n_gen"] == 0:
            q5ks_prefill_q8[depth] = row["avg_ts"]
        else:
            raise ValueError("unexpected UD-Q5_K_S benchmark shape")
    require(sorted(q5ks_decode_q8) == DEPTHS, "UD-Q5_K_S q8 decode axis incomplete")
    require(sorted(q5ks_prefill_q8) == DEPTHS, "UD-Q5_K_S q8 prefill axis incomplete")

    q5ks_f16 = ladder["variants"]["UD-Q5_K_S"]
    target_f16 = ladder["variants"]["UD-Q4_K_XL"]
    manifest_files = {entry["name"]: entry["sha256"] for entry in manifest["files"]}
    require(target_f16["sha256_16"] == manifest_files["Qwen3.8-27B-UD-Q4_K_XL.gguf"][:16],
            "target model identity mismatch")
    require(q5ks_f16["sha256_16"] == manifest_files["Qwen3.8-27B-UD-Q5_K_S.gguf"][:16],
            "UD-Q5_K_S donor model identity mismatch")

    points = []
    for index, depth in enumerate(DEPTHS):
        points.append({
            "active_context_tokens": depth,
            "target_f16_anchor": {
                "decode_tok_s": decimal_number(target_f16["decode_tg128"][index]),
                "prefill_tok_s": decimal_number(target_f16["prefill_pp2048"][index]),
            },
            "decode_tok_s": estimate_metric(
                target_f16["decode_tg128"][index],
                q4km_decode_f16[index],
                q4km_decode_q8[index],
                q5ks_f16["decode_tg128"][index],
                q5ks_decode_q8[depth],
            ),
            "prefill_tok_s": withheld_metric(
                q4km_prefill_f16[index],
                q4km_prefill_q8[index],
                q5ks_f16["prefill_pp2048"][index],
                q5ks_prefill_q8[depth],
            ),
        })

    script_path = Path(__file__).resolve()
    return {
        "format": "neural-download-estimate-snapshot-v1",
        "id": SNAPSHOT_ID,
        "snapshot_date": "2026-08-25",
        "state": "estimated",
        "classification": "estimated-not-measured",
        "grade": "D",
        "selectors": {
            "revision": "qwen3.8-27b",
            "artifact_id": "qwen38-27b-unsloth-ud-q4-k-xl-4ca7207",
            "quantization": "UD-Q4_K_XL",
            "runtime_family": "llama.cpp SYCL",
            "tp": 1,
            "mtp": 0,
            "graph": "off",
            "kv": "q8_0",
        },
        "target_identity": {
            "repository": manifest["repository"],
            "revision": manifest["revision"],
            "file": "Qwen3.8-27B-UD-Q4_K_XL.gguf",
            "sha256": manifest_files["Qwen3.8-27B-UD-Q4_K_XL.gguf"],
        },
        "workload": "llama-bench tg128 at exact active-depth points; raw-engine decode shape estimate",
        "method": {
            "central_formula": "target_f16 * sqrt((Q4_K_M_q8/Q4_K_M_f16) * (UD-Q5_K_S_q8/UD-Q5_K_S_f16))",
            "uncertainty_formula": "target_f16 * [min(donor ratios), max(donor ratios)]",
            "uncertainty_kind": "two-donor envelope; not a statistical confidence interval",
            "scope": "within Qwen3.8, TP1, MTP0, graph off, exact matching active-context point",
            "estimated_metrics": ["decode_tok_s"],
            "withheld_metrics": {
                "prefill_tok_s": "Q4_K_M and UD-Q5_K_S prefill penalties disagree materially and are runtime-build-confounded"
            },
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
        "limitations": [
            "No UD-Q4_K_XL q8_0 KV run is measured; every central value and band is an estimate.",
            "Only two donor quantizations define the envelope, so model-form uncertainty can be larger than the reported band.",
            "The UD-Q5_K_S q8 donor used llama.cpp build commit 9fee29e while the f16 weight ladder records a named build rather than a full commit identity.",
            "The snapshot estimates raw-engine decode only; prefill is deliberately withheld because the donor ratios disagree.",
            "The snapshot does not estimate quality, TTFT, VRAM, serving throughput, or record eligibility.",
            "Do not transfer these values across revisions, TP, MTP depth, graph mode, KV dtype, runtime, workload, or hardware.",
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
