#!/usr/bin/env python3
"""Gate a strided-batch compressor GEMM against exact independent M=1 GEMMs."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import torch
from safetensors import safe_open


def load_fused_weight(model: Path, layer: int) -> torch.Tensor:
    index = json.loads((model / "model.safetensors.index.json").read_text())
    keys = [
        f"layers.{layer}.attn.compressor.wkv.weight",
        f"layers.{layer}.attn.compressor.wgate.weight",
    ]
    tensors = []
    for key in keys:
        shard = model / index["weight_map"][key]
        with safe_open(shard, framework="pt", device="cpu") as handle:
            tensors.append(handle.get_tensor(key))
    return torch.cat(tensors, dim=0).contiguous()


def event_samples(fn, iterations: int, repeats: int) -> list[float]:
    samples = []
    for _ in range(repeats):
        start = torch.xpu.Event(enable_timing=True)
        end = torch.xpu.Event(enable_timing=True)
        start.record()
        for _ in range(iterations):
            fn()
        end.record()
        end.synchronize()
        samples.append(start.elapsed_time(end) * 1000.0 / iterations)
    return samples


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--width", type=int, default=2)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=9)
    parser.add_argument("--seed", type=int, default=419)
    args = parser.parse_args()
    if args.width not in (2, 4, 8):
        parser.error("--width must be 2, 4, or 8")

    torch.manual_seed(args.seed)
    torch.xpu.manual_seed_all(args.seed)
    device = torch.device("xpu:0")
    rows = []

    for layer in (2, 3):
        weight = load_fused_weight(args.model, layer).to(device)
        output_features, input_features = weight.shape
        hidden = torch.empty(
            (args.width, input_features), device=device, dtype=torch.bfloat16
        )

        def row_exact() -> torch.Tensor:
            return torch.cat(
                [
                    torch.mm(
                        hidden[row : row + 1],
                        weight.T,
                        out_dtype=torch.float32,
                    )
                    for row in range(args.width)
                ],
                dim=0,
            )

        def batched_exact() -> torch.Tensor:
            return torch.bmm(
                hidden[:, None, :],
                weight.T[None, :, :].expand(args.width, -1, -1),
                out_dtype=torch.float32,
            )[:, 0, :]

        def plain_m2() -> torch.Tensor:
            return torch.mm(hidden, weight.T, out_dtype=torch.float32)

        for _ in range(20):
            hidden.normal_()
            row_exact()
            batched_exact()
            plain_m2()
        torch.xpu.synchronize()

        graph = torch.xpu.XPUGraph()
        with torch.xpu.graph(graph):
            graph_output = batched_exact()
        graph.replay()
        torch.xpu.synchronize()

        epoch_rows = []
        for epoch in range(args.epochs):
            generator = torch.Generator(device=device).manual_seed(
                args.seed + layer * 1000 + epoch
            )
            scale = (0.0625, 0.25, 1.0, 4.0)[epoch % 4]
            hidden.copy_(
                torch.randn(
                    hidden.shape,
                    device=device,
                    dtype=hidden.dtype,
                    generator=generator,
                )
                * scale
            )
            expected = row_exact()
            eager_batched = batched_exact()
            eager_plain = plain_m2()
            graph.replay()
            torch.xpu.synchronize()
            graph_value = graph_output.clone()
            epoch_rows.append(
                {
                    "epoch": epoch,
                    "scale": scale,
                    "bmm_eager_exact": torch.equal(expected, eager_batched),
                    "bmm_graph_exact": torch.equal(expected, graph_value),
                    "plain_m2_exact": torch.equal(expected, eager_plain),
                    "bmm_graph_mismatches": int((expected != graph_value).sum().item()),
                    "plain_m2_mismatches": int((expected != eager_plain).sum().item()),
                    "bmm_graph_max_abs": float(
                        (expected - graph_value).abs().max().item()
                    ),
                    "plain_m2_max_abs": float(
                        (expected - eager_plain).abs().max().item()
                    ),
                }
            )
        graph.reset()
        torch.xpu.synchronize()

        hidden.normal_()
        row_samples = event_samples(row_exact, args.iterations, args.repeats)
        bmm_samples = event_samples(batched_exact, args.iterations, args.repeats)
        plain_samples = event_samples(plain_m2, args.iterations, args.repeats)
        row_median = statistics.median(row_samples)
        bmm_median = statistics.median(bmm_samples)
        rows.append(
            {
                "layer": layer,
                "compress_ratio": 4 if layer % 2 == 0 else 128,
                "shape": {
                    "m": args.width,
                    "n": output_features,
                    "k": input_features,
                },
                "epochs": args.epochs,
                "bmm_eager_exact_epochs": sum(
                    row["bmm_eager_exact"] for row in epoch_rows
                ),
                "bmm_graph_exact_epochs": sum(
                    row["bmm_graph_exact"] for row in epoch_rows
                ),
                "plain_m2_exact_epochs": sum(
                    row["plain_m2_exact"] for row in epoch_rows
                ),
                "timing": {
                    "independent_m1_plus_cat_median_us": row_median,
                    "bmm_median_us": bmm_median,
                    "plain_m2_median_us": statistics.median(plain_samples),
                    "bmm_saved_us": row_median - bmm_median,
                    "bmm_speedup": row_median / bmm_median,
                    "independent_m1_plus_cat_samples_us": row_samples,
                    "bmm_samples_us": bmm_samples,
                    "plain_m2_samples_us": plain_samples,
                },
                "epoch_rows": epoch_rows,
            }
        )

    c4_saved = rows[0]["timing"]["bmm_saved_us"]
    c128_saved = rows[1]["timing"]["bmm_saved_us"]
    projected_ms = (21 * c4_saved + 20 * c128_saved) / 1000.0
    passed = all(
        row["bmm_eager_exact_epochs"] == args.epochs
        and row["bmm_graph_exact_epochs"] == args.epochs
        for row in rows
    )
    result = {
        "schema_version": 1,
        "classification": f"deepseek_v4_compressor_m{args.width}_bmm_exact_gate",
        "device": torch.xpu.get_device_name(),
        "torch": torch.__version__,
        "model": str(args.model),
        "epochs_per_shape": args.epochs,
        "passed": passed,
        "projected_41_layer_savings_ms_per_cycle": projected_ms,
        "integration_gate_ms_per_cycle": 0.5,
        "clears_integration_gate": passed and projected_ms >= 0.5,
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "rows"},
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
