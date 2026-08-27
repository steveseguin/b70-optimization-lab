#!/usr/bin/env python3
"""Validate and aggregate the strict Qwen3.8 Q8 + Q4 MTP2 campaign."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
ROOT = REPO / "experiments/qwen38-27b-b70/data"
INPUTS = {
    "mtp0-control": (
        ROOT / "qwen38-q8-q4mtp-tp1-mtp0-control-20260827-r1",
        "4c6228c49bdfa0d97edd4ed50250daf894877cbc301320215eae98563fb040fa",
        "3d0d60240cca1937493ff525ffd58e4331148834fc0734e5ffb3433c94752cec",
    ),
    "mtp1-screen": (
        ROOT / "qwen38-q8-q4mtp-tp1-mtp1-20260827-r1",
        "ff0c68b5669fdfccc278dc85c6e4966601e5014193bae1108f75108a4077c764",
        "ab1c07cc2285c9ae8b81a4201b1caa599735985852034e5038c56e825ec54a43",
    ),
    "mtp2-r1": (
        ROOT / "qwen38-q8-q4mtp-tp1-mtp2-20260827-r1",
        "80c076bb4725526872ac18611af207da9b25818b65fe16b84c03b6a157e8d980",
        "4b4422dab297f4c9558f0a3523d8a835a087feb2113b989477b0051012adaa77",
    ),
    "mtp2-r2": (
        ROOT / "qwen38-q8-q4mtp-tp1-mtp2-20260827-r2",
        "38334ae826de22b2b00a5495c2bc1a99714563df13b4ac937ecf0bb6580dd19c",
        "3ebb4f6d461c8d034c05b8ca69cbf7298db8fafceb5917680dea3413d827ef20",
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs() -> dict[str, dict[str, Any]]:
    values: dict[str, dict[str, Any]] = {}
    for name, (root, performance_hash, qualification_hash) in INPUTS.items():
        performance_path = root / "performance.json"
        qualification_path = root / "qualification.json"
        if sha256(performance_path) != performance_hash:
            raise ValueError(f"{name} performance SHA mismatch")
        if sha256(qualification_path) != qualification_hash:
            raise ValueError(f"{name} qualification SHA mismatch")
        performance = json.loads(performance_path.read_text(encoding="utf-8"))
        qualification = json.loads(qualification_path.read_text(encoding="utf-8"))
        if qualification.get("status") != "passed":
            raise ValueError(f"{name} qualification did not pass")
        gate = performance.get("realistic_final_gate", {})
        if not (gate.get("passed") and gate.get("cached_tokens_all_zero")):
            raise ValueError(f"{name} realistic suite gate failed")
        if len(performance.get("rows", [])) != 12:
            raise ValueError(f"{name} does not contain twelve prompts")
        measured = performance["summary"]["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"]
        if measured != qualification["class_balanced_median_tok_s"]:
            raise ValueError(f"{name} metric mismatch")
        values[name] = {"performance": performance, "qualification": qualification}
    return values


def token_map(performance: dict[str, Any]) -> dict[str, list[int]]:
    return {row["prompt_id"]: row["token_ids"] for row in performance["rows"]}


def build_result(created_at_utc: str) -> dict[str, Any]:
    values = load_inputs()
    control_tokens = token_map(values["mtp0-control"]["performance"])
    for name in ("mtp1-screen", "mtp2-r1", "mtp2-r2"):
        if token_map(values[name]["performance"]) != control_tokens:
            raise ValueError(f"{name} complete token arrays differ from matched MTP0")
        qualification = values[name]["qualification"]
        if not (
            qualification["target_oracle_exact_prompts"] == 12
            and qualification["objective_canaries_passed"]
            and qualification["drafted_tokens"] > 0
            and qualification["accepted_tokens"] > 0
        ):
            raise ValueError(f"{name} speculative qualification is incomplete")

    control = values["mtp0-control"]["qualification"]["class_balanced_median_tok_s"]
    mtp1 = values["mtp1-screen"]["qualification"]["class_balanced_median_tok_s"]
    mtp2_attempts = [
        values[name]["qualification"]["class_balanced_median_tok_s"]
        for name in ("mtp2-r1", "mtp2-r2")
    ]
    mtp2 = statistics.median(mtp2_attempts)
    return {
        "schema": "neural.download.qwen38-q8-q4mtp-tp1-mtp2-strict-result.v1",
        "created_at_utc": created_at_utc,
        "status": "strict-package-headline-qualified",
        "profile": "Qwen3.8 27B Q8_0 target plus same-model Q4_0 external MTP draft, TP1, MTP depth 2, F16 target/draft KV, graph off, reasoning off, 1024-token configured context, raw native completions",
        "metric": {
            "name": "median of two fresh-server class-balanced medians, events 1-100 over 99 intervals after TTFT",
            "unit": "tok/s",
            "attempt_values": mtp2_attempts,
            "value": mtp2,
            "attempt_relative_range_percent": (max(mtp2_attempts) - min(mtp2_attempts)) / mtp2 * 100,
        },
        "matched_mtp0_control": {
            "value_tok_s": control,
            "mtp2_gain_percent": (mtp2 / control - 1) * 100,
            "complete_token_arrays_exact": "24/24 across both MTP2 servers",
        },
        "depth_screen": [
            {"mtp": 0, "tok_s": control, "samples": 1, "target_exact": True, "disposition": "matched promotion control"},
            {"mtp": 1, "tok_s": mtp1, "samples": 1, "target_exact": True, "disposition": "valid screen; slower than winner"},
            {"mtp": 2, "tok_s": mtp2, "samples": 2, "target_exact": True, "disposition": "winner; replicated on a fresh server"},
        ],
        "qualification": {
            "fresh_mtp2_servers": 2,
            "prompt_count_per_attempt": 12,
            "prompt_classes": 6,
            "max_tokens": 512,
            "metric_events": 100,
            "metric_intervals": 99,
            "cached_tokens_all_zero": True,
            "objective_canary_batteries_passed": "4/4 across matched control and two MTP2 servers",
            "complete_mtp2_token_arrays_exact_to_matched_mtp0": "24/24",
            "complete_mtp2_token_arrays_exact_between_fresh_servers": "12/12",
        },
        "draft_counters": {
            name: {
                "drafted_tokens": values[name]["qualification"]["drafted_tokens"],
                "accepted_tokens": values[name]["qualification"]["accepted_tokens"],
                "acceptance_rate": values[name]["qualification"]["acceptance_rate"],
            }
            for name in ("mtp1-screen", "mtp2-r1", "mtp2-r2")
        },
        "identities": {
            "target_sha256": "f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8",
            "draft_sha256": "50d9ce5a6da381bbcfb31061cf73df94a90e6faf8efeddee379a9cb8f1501c6e",
            "llama_server_sha256": "35f2d2327f05f42feb40f1a015ff46791e7277771ed97653f085be05a6f2c545",
            "libggml_sycl_sha256": "0e7789313ac5776b197da813d482f78e2f396620cc745af0f9c1bb2ec39bd154",
        },
        "inputs": {
            name: {
                "performance": str((root / "performance.json").relative_to(REPO)),
                "performance_sha256": performance_hash,
                "qualification": str((root / "qualification.json").relative_to(REPO)),
                "qualification_sha256": qualification_hash,
            }
            for name, (root, performance_hash, qualification_hash) in INPUTS.items()
        },
        "publication_authority": {
            "single_user_short_context_headline": True,
            "mtp_depth_profile": [0, 1, 2],
            "context_curve": False,
            "concurrency_curve": False,
            "localmaxxing_submission": False,
            "interpolation_or_extrapolation": False,
        },
        "scope": "One-B70 single-user short-context native HTTP decode only. No 32K, concurrency, TP2, Q8-draft, alternate-KV, chat-template, or another-runtime authority transfers from this result.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = build_result(dt.datetime.now(dt.UTC).isoformat())
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as stream:
            stream.write(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
