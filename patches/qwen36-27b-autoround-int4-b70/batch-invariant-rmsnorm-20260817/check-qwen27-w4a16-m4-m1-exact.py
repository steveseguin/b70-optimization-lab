#!/usr/bin/env python3
"""Check exact M4-versus-M1 invariance for Qwen27 TP2 stateless ops.

This is a direct XPU operator oracle, not an endpoint benchmark.  For every
INT4 projection shape used by one TP2 target step, the FP16 GDN BA projection,
and the INT8 target LM head, it creates one four-row activation and compares
the packed M4 result with four ordered M1 calls over the exact same rows.  All
comparisons and reductions stay on the XPU; the script performs one final host
transfer/synchronization after every case has been enqueued.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


GROUP_SIZE = 128
PACK_FACTOR = 8
DEFAULT_KERNEL_ROOT = Path("/home/steve/src/vllm-xpu-kernels")


@dataclass(frozen=True)
class Projection:
    name: str
    input_features: int
    output_features: int


PROJECTIONS = (
    Projection("gdn_qkvz", 5120, 8192),
    Projection("gdn_out", 3072, 5120),
    Projection("mlp_gateup", 5120, 17408),
    Projection("mlp_down", 8704, 5120),
    Projection("full_attention_qkvgate", 5120, 7168),
    Projection("full_attention_out", 3072, 5120),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_identity(root: Path) -> dict[str, str]:
    def run(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(root), *args], text=True
        ).strip()

    diff = subprocess.check_output(
        ["git", "-C", str(root), "diff", "--binary"]
    )
    return {
        "root": str(root),
        "head": run("rev-parse", "HEAD"),
        "working_diff_sha256": hashlib.sha256(diff).hexdigest(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--seed", type=int, default=20260817)
    parser.add_argument(
        "--kernel-root", type=Path, default=DEFAULT_KERNEL_ROOT
    )
    parser.add_argument("--output-json", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    kernel_root = args.kernel_root.expanduser().resolve()
    sys.path.insert(0, str(kernel_root))

    # The current runtime publishes oneDNN completion through this guarded
    # current-stream barrier.  The oracle tests arithmetic, not an intentionally
    # missing producer/consumer edge.
    os.environ.setdefault("VLLM_XPU_ONEDNN_INT4_COMPLETION_BARRIER", "1")
    os.environ.setdefault("VLLM_XPU_ONEDNN_INT8_COMPLETION_BARRIER", "1")

    import torch

    extension = importlib.import_module("vllm_xpu_kernels._xpu_C")
    if not torch.xpu.is_available():
        raise RuntimeError("torch.xpu is unavailable")
    device = torch.device(args.device)
    if device.type != "xpu":
        raise ValueError("--device must select an XPU device")
    device_index = 0 if device.index is None else device.index
    torch.xpu.set_device(device_index)

    generator = torch.Generator(device=device)
    generator.manual_seed(args.seed)
    zero_point = torch.tensor([8], dtype=torch.int8, device=device)

    pending: list[dict[str, Any]] = []
    retained: list[Any] = [zero_point]
    for projection in PROJECTIONS:
        k = projection.input_features
        n = projection.output_features
        backing = torch.randint(
            0,
            2**31 - 1,
            (n, k // PACK_FACTOR),
            dtype=torch.int32,
            device=device,
            generator=generator,
        ).contiguous()
        weight = backing.t()
        scales = (
            torch.rand(
                (k // GROUP_SIZE, n),
                dtype=torch.float16,
                device=device,
                generator=generator,
            )
            * 0.02
            + 0.001
        ).contiguous()
        activation = torch.randn(
            (4, k),
            dtype=torch.float16,
            device=device,
            generator=generator,
        ).contiguous()

        def gemm(x: Any) -> Any:
            return torch.ops._xpu_C.int4_gemm_w4a16(
                x,
                weight,
                None,
                scales,
                zero_point,
                GROUP_SIZE,
                None,
            )

        packed = gemm(activation)
        serial = torch.cat(
            [gemm(activation[row : row + 1]) for row in range(4)], dim=0
        )
        diff = (packed.float() - serial.float()).abs()
        mismatch = packed != serial
        row_mismatches = mismatch.reshape(4, -1).sum(dim=1, dtype=torch.int64)
        row_max_abs = diff.reshape(4, -1).amax(dim=1)
        packed_sums = packed.float().reshape(4, -1).sum(dim=1)
        serial_sums = serial.float().reshape(4, -1).sum(dim=1)

        pending.append(
            {
                "projection": projection,
                "operator": "_xpu_C.int4_gemm_w4a16",
                "row_mismatches": row_mismatches,
                "row_max_abs": row_max_abs,
                "packed_sums": packed_sums,
                "serial_sums": serial_sums,
                "weight_shape": list(weight.shape),
                "weight_stride": list(weight.stride()),
                "scale_shape": list(scales.shape),
            }
        )
        # Keep all producer inputs and outputs alive until the one final wait.
        retained.extend((backing, weight, scales, activation, packed, serial))

    def enqueue_comparison(
        projection: Projection,
        operator_name: str,
        activation: Any,
        weight: Any,
        scales: Any,
        operation: Any,
    ) -> None:
        packed = operation(activation)
        serial = torch.cat(
            [operation(activation[row : row + 1]) for row in range(4)], dim=0
        )
        diff = (packed.float() - serial.float()).abs()
        mismatch = packed != serial
        pending.append(
            {
                "projection": projection,
                "operator": operator_name,
                "row_mismatches": mismatch.reshape(4, -1).sum(
                    dim=1, dtype=torch.int64
                ),
                "row_max_abs": diff.reshape(4, -1).amax(dim=1),
                "packed_sums": packed.float().reshape(4, -1).sum(dim=1),
                "serial_sums": serial.float().reshape(4, -1).sum(dim=1),
                "weight_shape": list(weight.shape),
                "weight_stride": list(weight.stride()),
                "scale_shape": None if scales is None else list(scales.shape),
            }
        )
        retained.extend((activation, weight, scales, packed, serial))

    ba_projection = Projection("gdn_ba", 5120, 48)
    ba_activation = torch.randn(
        (4, ba_projection.input_features),
        dtype=torch.float16,
        device=device,
        generator=generator,
    ).contiguous()
    ba_weight = torch.randn(
        (ba_projection.output_features, ba_projection.input_features),
        dtype=torch.float16,
        device=device,
        generator=generator,
    ).contiguous()
    enqueue_comparison(
        ba_projection,
        "torch.nn.functional.linear_fp16",
        ba_activation,
        ba_weight,
        None,
        lambda x: torch.nn.functional.linear(x, ba_weight),
    )

    lm_projection = Projection("target_lm_head", 5120, 124160)
    lm_activation = torch.randn(
        (4, lm_projection.input_features),
        dtype=torch.float16,
        device=device,
        generator=generator,
    ).contiguous()
    lm_weight = torch.randint(
        -127,
        128,
        (lm_projection.input_features, lm_projection.output_features),
        dtype=torch.int8,
        device=device,
        generator=generator,
    ).contiguous()
    lm_scales = (
        torch.rand(
            (lm_projection.output_features,),
            dtype=torch.bfloat16,
            device=device,
            generator=generator,
        )
        * 0.02
        + 0.001
    ).contiguous()

    def lm_head(x: Any) -> Any:
        x_q, x_scale = torch.ops._xpu_C.per_token_quant_int8_xpu(x)
        return torch.ops._xpu_C.int8_gemm_w8a8(
            x_q,
            x_scale,
            lm_weight,
            lm_scales,
            torch.float16,
            None,
        )

    enqueue_comparison(
        lm_projection,
        "per_token_quant_int8_xpu+int8_gemm_w8a8",
        lm_activation,
        lm_weight,
        lm_scales,
        lm_head,
    )

    # This is the oracle's only device-to-host synchronization point.  Stacking
    # first makes one small transfer cover every projection and row.
    report_tensor = torch.stack(
        [
            torch.cat(
                (
                    case["row_mismatches"].to(torch.float64),
                    case["row_max_abs"].to(torch.float64),
                    case["packed_sums"].to(torch.float64),
                    case["serial_sums"].to(torch.float64),
                )
            )
            for case in pending
        ]
    ).cpu()

    results: list[dict[str, Any]] = []
    all_exact = True
    for case_index, case in enumerate(pending):
        values = report_tensor[case_index]
        row_mismatches = [int(value) for value in values[0:4].tolist()]
        row_max_abs = [float(value) for value in values[4:8].tolist()]
        packed_sums = [float(value) for value in values[8:12].tolist()]
        serial_sums = [float(value) for value in values[12:16].tolist()]
        exact = all(value == 0 for value in row_mismatches)
        all_exact = all_exact and exact
        results.append(
            {
                **asdict(case["projection"]),
                "operator": case["operator"],
                "m4_activation_shape": [4, case["projection"].input_features],
                "weight_shape": case["weight_shape"],
                "weight_stride": case["weight_stride"],
                "scale_shape": case["scale_shape"],
                "row_mismatch_counts": row_mismatches,
                "row_max_abs": row_max_abs,
                "packed_row_sums_fp32": packed_sums,
                "serial_row_sums_fp32": serial_sums,
                "bit_exact_all_rows": exact,
            }
        )

    extension_path = Path(extension.__file__).resolve()
    document = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "classification": "diagnostic_direct_operator_oracle",
        "result": "pass" if all_exact else "fail",
        "all_projections_bit_exact": all_exact,
        "comparison": "one packed M4 call versus four ordered M1 calls",
        "synchronization": "device-side comparisons; one final host transfer",
        "seed": args.seed,
        "device": str(device),
        "python": {
            "executable": sys.executable,
            "version": platform.python_version(),
        },
        "torch_version": str(torch.__version__),
        "kernel_source": git_identity(kernel_root),
        "extension": {
            "path": str(extension_path),
            "sha256": sha256_file(extension_path),
        },
        "environment": {
            "ONEAPI_DEVICE_SELECTOR": os.environ.get("ONEAPI_DEVICE_SELECTOR"),
            "ZE_AFFINITY_MASK": os.environ.get("ZE_AFFINITY_MASK"),
            "VLLM_XPU_ONEDNN_INT4_COMPLETION_BARRIER": os.environ.get(
                "VLLM_XPU_ONEDNN_INT4_COMPLETION_BARRIER"
            ),
            "VLLM_XPU_ONEDNN_INT8_COMPLETION_BARRIER": os.environ.get(
                "VLLM_XPU_ONEDNN_INT8_COMPLETION_BARRIER"
            ),
        },
        "results": results,
    }
    serialized = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if args.output_json is not None:
        output_path = args.output_json.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialized, encoding="utf-8")
    sys.stdout.write(serialized)
    return 0 if all_exact else 1


if __name__ == "__main__":
    raise SystemExit(main())
