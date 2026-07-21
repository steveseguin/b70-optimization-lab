#!/usr/bin/env python3
"""Test whether a raw V1 list is retained by a surrounding XPU graph."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
sys.path.insert(0, str(ROOT / "tools"))

from option4_decoder import FixedAddressCommandGraph, compare_tensor_bits  # noqa: E402
from option4_decoder.native import load_native_replay  # noqa: E402
from phase1_m1_attention_graph_gate import Boundary  # noqa: E402
from phase1_m1_attention_replay import PacketCase  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("packet", type=Path)
    parser.add_argument("--native-build-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rank", type=int, default=0)
    parser.add_argument("--layer", type=int, default=42)
    parser.add_argument(
        "--capture-append-backend", choices=("raw-lz", "sycl"), default="raw-lz"
    )
    parser.add_argument(
        "--bucket", default="compressed-swa-full-anchor512"
    )
    args = parser.parse_args()
    if os.environ.get("ZE_AFFINITY_MASK") is None:
        raise RuntimeError("ZE_AFFINITY_MASK must select one free card")
    if os.environ.get("ZE_ENABLE_TRACING_LAYER") != "1":
        raise RuntimeError("ZE_ENABLE_TRACING_LAYER=1 is required")

    from vllm.platforms import current_platform

    current_platform.import_kernels()
    device = torch.device("xpu:0")
    torch.xpu.set_device(device)
    native = load_native_replay(args.native_build_dir)
    manifest = args.packet / "manifests" / (
        f"rank{args.rank}-layer{args.layer:02d}-{args.bucket}.json"
    )
    boundary = Boundary(PacketCase(args.packet, manifest, device))
    reference = Boundary(PacketCase(args.packet, manifest, device))
    handles: tuple[int, int] | None = None

    def inner_raw(_: int) -> None:
        assert handles is not None
        native.replay_raw_level_zero(*handles)

    inner = FixedAddressCommandGraph(
        boundary.launch, boundary.bindings(), native_replay=inner_raw
    )
    boundary.reset()
    inner.warm(3)
    inner_outputs = dict(inner.build())
    harvested = tuple(
        int(value)
        for value in native.harvest_raw_level_zero_handles(inner.graph_exec)
    )
    handles = harvested[:2]
    torch.xpu.synchronize()

    # This is the exact architectural question: a guarded op would make this
    # raw append while the surrounding PIECEWISE XPUGraph records.  If the raw
    # append bypasses queue recording, the outer executable is empty/stale.
    def nested_launch() -> dict[str, torch.Tensor]:
        assert handles is not None
        if args.capture_append_backend == "raw-lz":
            native.replay_raw_level_zero(*handles)
        else:
            native.replay_current_queue(inner.graph_exec)
        return {"local": inner_outputs["local"]}

    outer_error = None
    exact = False
    report = None
    outer_state = None
    try:
        outer = FixedAddressCommandGraph(
            nested_launch,
            boundary.bindings(),
            native_replay=native.replay_current_queue,
        )
        boundary.reset()
        outer.warm(2)
        outer_outputs = dict(outer.build())
        boundary.reset(7)
        reference.reset(7)
        expected = reference.launch()["local"]
        torch.xpu.synchronize()
        outer.replay()
        torch.xpu.synchronize()
        parity = compare_tensor_bits("local", outer_outputs["local"], expected)
        exact = parity.exact
        report = parity.to_dict()
        outer_state = outer.state.name
    except BaseException as exc:
        outer_error = f"{type(exc).__name__}: {exc}"

    result = {
        "schema": "option4-m1-attention-v1-nested-raw-probe",
        "passed": exact and outer_error is None,
        "pieced_surrounding_capture": True,
        "raw_append_recorded_by_outer_graph": exact,
        "capture_append_backend": args.capture_append_backend,
        "eager_break": not exact,
        "host_syncs_inside_candidate_op": 0,
        "outer_state": outer_state,
        "outer_error": outer_error,
        "parity": report,
        "inner_harvest_matching_appends": harvested[2],
        "layer": args.layer,
        "bucket": args.bucket,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
