#!/usr/bin/env python3
"""Aggregate Option-4 Phase-1 packet, component, trace, and nesting evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet-manifest", type=Path, required=True)
    parser.add_argument("--component-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    helper_path = Path(__file__).with_name("summarize_unitrace.py")
    spec = importlib.util.spec_from_file_location("option4_unitrace", helper_path)
    assert spec is not None and spec.loader is not None
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)

    packet = json.loads(args.packet_manifest.read_text())
    gate = json.loads(
        (args.component_root / "raw-lz-gate-layer42-anchor512.json").read_text()
    )
    nested_raw = json.loads(
        (args.component_root / "nested-raw-probe.json").read_text()
    )
    nested_sycl = json.loads(
        (args.component_root / "nested-sycl-probe.json").read_text()
    )
    eager_oracles = [
        json.loads((args.component_root / name).read_text())
        for name in ("eager-anchor64.json", "eager-anchor512.json")
    ]
    per_layer_paths = sorted((args.component_root / "per-layer").glob("layer*.json"))
    per_layer = [json.loads(path.read_text()) for path in per_layer_paths]
    per_layer_index = [
        {
            "path": str(path.relative_to(args.component_root)),
            "layer": row["layer"],
            "bucket": row["bucket"],
            "passed": row["passed"],
            "raw_regular_list": row["graph"]["raw_regular_list"],
        }
        for path, row in zip(per_layer_paths, per_layer, strict=True)
    ]
    eager_trace = helper.summarize(args.component_root / "traces" / "eager")
    raw_trace = helper.summarize(args.component_root / "traces" / "raw")

    component_passed = (
        packet["passed"]
        and all(row["passed"] for row in eager_oracles)
        and len(per_layer) == 86
        and all(row["passed"] for row in per_layer)
        and gate["changed"]["exact"] == gate["changed"]["required"] == 40
        and gate["replay"]["passed"] == gate["replay"]["required"] == 70
        and gate["replay"]["epoch_28_present"]
        and gate["replay"]["epoch_58_present"]
        and raw_trace["effective_submission_boundaries"] == 1
        and raw_trace["host_sync_total"] == 0
    )
    result = {
        "schema": "option4-m1-attention-phase1-summary-v1",
        "capture": {
            "passed": packet["passed"],
            "coverage": packet["coverage"],
            "checksums": packet["checksums"],
            "jit": packet["jit"],
            "packet_manifest_sha256": packet["packet_manifest_sha256"],
        },
        "component": {
            "passed": component_passed,
            "eager_oracle_layers": [
                {
                    "bucket": row["bucket"],
                    "exact_layers": row["exact_layers"],
                    "layers": row["layers"],
                }
                for row in eager_oracles
            ],
            "raw_command_list_instances": len(per_layer),
            "raw_command_list_passed": sum(bool(row["passed"]) for row in per_layer),
            "layers": len({row["layer"] for row in per_layer}),
            "buckets": sorted({row["bucket"] for row in per_layer}),
            "per_layer_index_sha256": canonical_sha(per_layer_index),
            "changed_exact": gate["changed"]["exact"],
            "changed_required": gate["changed"]["required"],
            "replay_passed": gate["replay"]["passed"],
            "replay_required": gate["replay"]["required"],
            "epoch_28_present": gate["replay"]["epoch_28_present"],
            "epoch_58_present": gate["replay"]["epoch_58_present"],
            "eager_trace": eager_trace,
            "v1_trace": raw_trace,
            "submission_boundary_eager": eager_trace[
                "effective_submission_boundaries"
            ],
            "submission_boundary_v1": raw_trace["effective_submission_boundaries"],
            "v1_host_syncs": raw_trace["host_sync_total"],
            "native_shim_sha256": gate["runtime"]["native_shim_sha256"],
            "xpu_extension_sha256": gate["runtime"]["xpu_extension_sha256"],
        },
        "endpoint_admission": {
            "passed": nested_sycl["passed"],
            "piecewise_surrounding_capture": nested_sycl[
                "pieced_surrounding_capture"
            ],
            "capture_append_backend": nested_sycl["capture_append_backend"],
            "append_recorded": nested_sycl["raw_append_recorded_by_outer_graph"],
            "eager_break": nested_sycl["eager_break"],
            "host_syncs_inside_candidate_op": nested_sycl[
                "host_syncs_inside_candidate_op"
            ],
            "parity": nested_sycl["parity"],
            "blocker": None if nested_sycl["passed"] else nested_sycl["outer_error"],
            "preserved_raw_level_zero_negative": {
                "passed": nested_raw["passed"],
                "capture_append_backend": nested_raw.get(
                    "capture_append_backend", "raw-lz"
                ),
                "append_recorded": nested_raw[
                    "raw_append_recorded_by_outer_graph"
                ],
                "eager_break": nested_raw["eager_break"],
                "reason": (
                    "direct raw Level Zero append bypasses surrounding SYCL graph "
                    "recording"
                ),
            },
        },
        "four_card_endpoint_run": False,
        "phase2_go": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if component_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
