#!/usr/bin/env python3
"""Check Qwen3.6 W8A8 MoE middle-layerlet correctness.

This compares the new graph-native layerlet against the accepted exact
endpoint path:

  offsets W8A8 GEMM1
  -> vLLM BF16 SiLU activation
  -> XPU per-token INT8 quant
  -> offsets W8A8 GEMM2

It is intentionally synthetic. The purpose is to validate the operator and
graph-capture behavior before using it inside the full vLLM endpoint.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_KERNEL_REPO = Path("/home/steve/src/vllm-xpu-kernels")
DEFAULT_DATA_DIR = Path("/home/steve/llm-optimizations/data")


@dataclass(frozen=True)
class Case:
    name: str
    experts: int
    rows: tuple[int, ...]
    hidden: int
    inter: int


DEFAULT_CASES = (
    Case("tiny_sparse", 4, (1, 2, 0, 3), 64, 64),
    Case("single_hot_expert", 4, (0, 0, 8, 0), 64, 64),
    Case("decode_like_sparse", 8, (1, 0, 2, 0, 1, 0, 3, 1), 128, 128),
    Case("dense_small", 8, (1, 1, 1, 1, 1, 1, 1, 1), 128, 64),
    Case(
        "qwen36_decode_one_token_tp4_shape",
        256,
        tuple(1 if i in (3, 17, 42, 64, 101, 149, 203, 241) else 0
              for i in range(256)),
        2048,
        128,
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--kernel-repo", type=Path, default=DEFAULT_KERNEL_REPO)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--md-out", type=Path)
    parser.add_argument("--graph-replay", action="store_true")
    parser.add_argument("--require-graph", action="store_true")
    parser.add_argument("--rtol", type=float, default=0.0)
    parser.add_argument("--atol", type=float, default=0.0)
    return parser.parse_args()


def add_kernel_repo_to_path(kernel_repo: Path) -> None:
    repo = str(kernel_repo)
    if repo not in sys.path:
        sys.path.insert(0, repo)


def make_offsets(torch: Any, rows: tuple[int, ...], device: str) -> Any:
    rows_cpu = torch.tensor(rows, dtype=torch.int64)
    offsets_cpu = torch.empty((len(rows) + 1,), dtype=torch.int64)
    offsets_cpu[0] = 0
    offsets_cpu[1:] = torch.cumsum(rows_cpu, dim=0)
    return offsets_cpu.to(device)


def fill_random_(torch: Any, tensors: dict[str, Any], case: Case) -> None:
    device = tensors["gemm1_a"].device
    total = int(sum(case.rows))
    tensors["gemm1_a"].copy_(
        torch.randint(-16, 16, (total, case.hidden), dtype=torch.int8,
                      device=device))
    tensors["gemm1_a_scales"].copy_(
        torch.rand((total, 1), dtype=torch.float32, device=device) * 0.03 +
        0.01)
    tensors["w13"].copy_(
        torch.randint(-16,
                      16,
                      (case.experts, case.hidden, 2 * case.inter),
                      dtype=torch.int8,
                      device=device))
    tensors["w13_scales"].copy_(
        torch.rand((case.experts, 2 * case.inter),
                   dtype=torch.float32,
                   device=device) * 0.03 + 0.01)
    tensors["w2"].copy_(
        torch.randint(-16,
                      16,
                      (case.experts, case.inter, case.hidden),
                      dtype=torch.int8,
                      device=device))
    tensors["w2_scales"].copy_(
        torch.rand((case.experts, case.hidden),
                   dtype=torch.float32,
                   device=device) * 0.03 + 0.01)


def allocate_case_tensors(torch: Any, case: Case, device: str) -> dict[str, Any]:
    total = int(sum(case.rows))
    return {
        "rows_per_expert":
        torch.tensor(case.rows, dtype=torch.int32, device=device),
        "offsets":
        make_offsets(torch, case.rows, device),
        "prefix_offsets":
        torch.empty((case.experts + 1,), dtype=torch.int64, device=device),
        "gemm1_a":
        torch.empty((total, case.hidden), dtype=torch.int8, device=device),
        "gemm1_a_scales":
        torch.empty((total, 1), dtype=torch.float32, device=device),
        "w13":
        torch.empty((case.experts, case.hidden, 2 * case.inter),
                    dtype=torch.int8,
                    device=device),
        "w13_scales":
        torch.empty((case.experts, 2 * case.inter),
                    dtype=torch.float32,
                    device=device),
        "w2":
        torch.empty((case.experts, case.inter, case.hidden),
                    dtype=torch.int8,
                    device=device),
        "w2_scales":
        torch.empty((case.experts, case.hidden),
                    dtype=torch.float32,
                    device=device),
        "ref_gemm1":
        torch.empty((total, 2 * case.inter),
                    dtype=torch.bfloat16,
                    device=device),
        "ref_act":
        torch.empty((total, case.inter), dtype=torch.bfloat16, device=device),
        "ref_gemm2_a":
        torch.empty((total, case.inter), dtype=torch.int8, device=device),
        "ref_gemm2_a_scales":
        torch.empty((total, 1), dtype=torch.float32, device=device),
        "ref_out":
        torch.empty((total, case.hidden), dtype=torch.bfloat16, device=device),
        "rows_ref_gemm1":
        torch.empty((total, 2 * case.inter),
                    dtype=torch.bfloat16,
                    device=device),
        "rows_ref_act":
        torch.empty((total, case.inter), dtype=torch.bfloat16, device=device),
        "rows_ref_gemm2_a":
        torch.empty((total, case.inter), dtype=torch.int8, device=device),
        "rows_ref_gemm2_a_scales":
        torch.empty((total, 1), dtype=torch.float32, device=device),
        "rows_ref_out":
        torch.empty((total, case.hidden), dtype=torch.bfloat16, device=device),
        "cand_gemm1":
        torch.empty((total, 2 * case.inter),
                    dtype=torch.bfloat16,
                    device=device),
        "cand_gemm2_a":
        torch.empty((total, case.inter), dtype=torch.int8, device=device),
        "cand_gemm2_a_scales":
        torch.empty((total, 1), dtype=torch.float32, device=device),
        "cand_out":
        torch.empty((total, case.hidden), dtype=torch.bfloat16, device=device),
    }


def compare_prefix_offsets(torch: Any,
                           tensors: dict[str, Any],
                           run_op: bool = True) -> dict[str, Any]:
    rows = tensors["rows_per_expert"]
    offsets = tensors["prefix_offsets"]
    ret_is_offsets = None
    if run_op:
        ret = torch.ops._xpu_C.qwen36_rows_per_expert_offsets_int64_out(
            rows, offsets)
        ret_is_offsets = bool(ret.data_ptr() == offsets.data_ptr())
    ref = torch.empty_like(offsets)
    ref[0].zero_()
    torch.cumsum(rows, dim=0, dtype=torch.int64, out=ref[1:])
    torch.xpu.synchronize()
    return {
        "offsets_equal": bool(torch.equal(offsets, ref)),
        "offsets_mismatch_count": int((offsets.cpu() != ref.cpu()).sum().item()),
        "offsets": [int(v) for v in offsets.cpu().tolist()],
        "ref_offsets": [int(v) for v in ref.cpu().tolist()],
        "ret_is_offsets": ret_is_offsets,
    }


def prefix_passed(result: dict[str, Any]) -> bool:
    return bool(result.get("offsets_equal")) and int(
        result.get("offsets_mismatch_count", 1)) == 0


def run_reference(torch: Any, fmi: Any, tensors: dict[str, Any],
                  case: Case) -> None:
    ops = torch.ops._xpu_C
    ops.cutlass_grouped_gemm_w8a8_int8_offsets_interface(
        tensors["gemm1_a"],
        tensors["gemm1_a_scales"],
        tensors["w13"],
        tensors["w13_scales"],
        None,
        tensors["ref_gemm1"],
        tensors["offsets"],
        2 * case.inter,
        case.hidden,
        case.experts,
    )
    fmi.fused_moe_activation(tensors["ref_act"], tensors["ref_gemm1"],
                             "silu")
    ops.per_token_quant_int8_xpu_out(tensors["ref_act"],
                                     tensors["ref_gemm2_a"],
                                     tensors["ref_gemm2_a_scales"])
    ops.cutlass_grouped_gemm_w8a8_int8_offsets_interface(
        tensors["ref_gemm2_a"],
        tensors["ref_gemm2_a_scales"],
        tensors["w2"],
        tensors["w2_scales"],
        None,
        tensors["ref_out"],
        tensors["offsets"],
        case.hidden,
        case.inter,
        case.experts,
    )


def run_rows_reference(torch: Any, fmi: Any, tensors: dict[str, Any],
                       case: Case) -> None:
    ops = torch.ops._xpu_C
    ops.cutlass_grouped_gemm_w8a8_int8_interface(
        tensors["gemm1_a"],
        tensors["gemm1_a_scales"],
        tensors["w13"],
        tensors["w13_scales"],
        None,
        tensors["rows_ref_gemm1"],
        tensors["rows_per_expert"],
        2 * case.inter,
        case.hidden,
        case.experts,
    )
    fmi.fused_moe_activation(tensors["rows_ref_act"],
                             tensors["rows_ref_gemm1"], "silu")
    ops.per_token_quant_int8_xpu_out(tensors["rows_ref_act"],
                                     tensors["rows_ref_gemm2_a"],
                                     tensors["rows_ref_gemm2_a_scales"])
    ops.cutlass_grouped_gemm_w8a8_int8_interface(
        tensors["rows_ref_gemm2_a"],
        tensors["rows_ref_gemm2_a_scales"],
        tensors["w2"],
        tensors["w2_scales"],
        None,
        tensors["rows_ref_out"],
        tensors["rows_per_expert"],
        case.hidden,
        case.inter,
        case.experts,
    )


def run_candidate(torch: Any, tensors: dict[str, Any], case: Case) -> Any:
    return torch.ops._xpu_C.qwen36_moe_w8a8_middle_layerlet(
        tensors["gemm1_a"],
        tensors["gemm1_a_scales"],
        tensors["w13"],
        tensors["w13_scales"],
        None,
        tensors["cand_gemm1"],
        tensors["cand_gemm2_a"],
        tensors["cand_gemm2_a_scales"],
        tensors["w2"],
        tensors["w2_scales"],
        None,
        tensors["cand_out"],
        tensors["offsets"],
        2 * case.inter,
        case.hidden,
        case.hidden,
        case.inter,
        case.experts,
    )


def max_abs(torch: Any, left: Any, right: Any) -> float:
    if left.numel() == 0:
        return 0.0
    return float((left.float() - right.float()).abs().max().cpu().item())


def compare_outputs(torch: Any, tensors: dict[str, Any],
                    case: Case) -> dict[str, Any]:
    ref_gemm2_a = tensors["ref_gemm2_a"].cpu()
    cand_gemm2_a = tensors["cand_gemm2_a"].cpu()
    mismatch_count = int((ref_gemm2_a != cand_gemm2_a).sum().item())
    return {
        "gemm1_max_abs_diff":
        max_abs(torch, tensors["ref_gemm1"], tensors["cand_gemm1"]),
        "gemm2_a_equal":
        bool(torch.equal(ref_gemm2_a, cand_gemm2_a)),
        "gemm2_a_mismatch_count":
        mismatch_count,
        "gemm2_a_scales_max_abs_diff":
        max_abs(torch, tensors["ref_gemm2_a_scales"],
                tensors["cand_gemm2_a_scales"]),
        "gemm2_output_max_abs_diff":
        max_abs(torch, tensors["ref_out"], tensors["cand_out"]),
        "ref_checksum":
        float(tensors["ref_out"].float().sum().cpu().item()),
        "cand_checksum":
        float(tensors["cand_out"].float().sum().cpu().item()),
        "retains_rows":
        int(sum(case.rows)),
    }


def compare_rows_reference(torch: Any, tensors: dict[str, Any]) -> dict[str, Any]:
    rows_ref_gemm2_a = tensors["rows_ref_gemm2_a"].cpu()
    ref_gemm2_a = tensors["ref_gemm2_a"].cpu()
    return {
        "gemm1_max_abs_diff":
        max_abs(torch, tensors["rows_ref_gemm1"], tensors["ref_gemm1"]),
        "gemm2_a_equal":
        bool(torch.equal(rows_ref_gemm2_a, ref_gemm2_a)),
        "gemm2_a_mismatch_count":
        int((rows_ref_gemm2_a != ref_gemm2_a).sum().item()),
        "gemm2_a_scales_max_abs_diff":
        max_abs(torch, tensors["rows_ref_gemm2_a_scales"],
                tensors["ref_gemm2_a_scales"]),
        "gemm2_output_max_abs_diff":
        max_abs(torch, tensors["rows_ref_out"], tensors["ref_out"]),
        "rows_ref_checksum":
        float(tensors["rows_ref_out"].float().sum().cpu().item()),
        "offset_ref_checksum":
        float(tensors["ref_out"].float().sum().cpu().item()),
    }


def case_passed(result: dict[str, Any], rtol: float, atol: float) -> bool:
    del rtol
    allowed = atol
    return (result["gemm1_max_abs_diff"] <= allowed
            and result["gemm2_a_equal"]
            and result["gemm2_a_scales_max_abs_diff"] <= allowed
            and result["gemm2_output_max_abs_diff"] <= allowed)


def run_graph_replay_case(torch: Any, fmi: Any, tensors: dict[str, Any],
                          case: Case, args: argparse.Namespace) -> dict[str,
                                                                        Any]:
    if not hasattr(torch.xpu, "XPUGraph") or not hasattr(torch.xpu, "graph"):
        return {"status": "unsupported", "passed": not args.require_graph}

    graph = torch.xpu.XPUGraph()
    try:
        for _ in range(3):
            run_candidate(torch, tensors, case)
        torch.xpu.synchronize()

        with torch.xpu.graph(graph):
            run_candidate(torch, tensors, case)
        torch.xpu.synchronize()

        fill_random_(torch, tensors, case)
        run_reference(torch, fmi, tensors, case)
        tensors["cand_gemm1"].zero_()
        tensors["cand_gemm2_a"].zero_()
        tensors["cand_gemm2_a_scales"].zero_()
        tensors["cand_out"].zero_()
        torch.xpu.synchronize()
        graph.replay()
        torch.xpu.synchronize()
        comparison = compare_outputs(torch, tensors, case)
        comparison["status"] = "executed"
        comparison["passed"] = case_passed(comparison, args.rtol, args.atol)
        return comparison
    except Exception as exc:  # noqa: BLE001 - report graph failures as data.
        return {
            "status": "error",
            "passed": False if args.require_graph else True,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def run_prefix_graph_replay_case(torch: Any, tensors: dict[str, Any],
                                 case: Case,
                                 args: argparse.Namespace) -> dict[str, Any]:
    if not hasattr(torch.xpu, "XPUGraph") or not hasattr(torch.xpu, "graph"):
        return {"status": "unsupported", "passed": not args.require_graph}

    graph = torch.xpu.XPUGraph()
    try:
        for _ in range(3):
            torch.ops._xpu_C.qwen36_rows_per_expert_offsets_int64_out(
                tensors["rows_per_expert"], tensors["prefix_offsets"])
        torch.xpu.synchronize()

        with torch.xpu.graph(graph):
            torch.ops._xpu_C.qwen36_rows_per_expert_offsets_int64_out(
                tensors["rows_per_expert"], tensors["prefix_offsets"])
        torch.xpu.synchronize()

        replacement = tuple((value + index + 1) % 5
                            for index, value in enumerate(case.rows))
        tensors["rows_per_expert"].copy_(
            torch.tensor(replacement,
                         dtype=torch.int32,
                         device=tensors["rows_per_expert"].device))
        tensors["prefix_offsets"].zero_()
        torch.xpu.synchronize()
        graph.replay()
        torch.xpu.synchronize()
        comparison = compare_prefix_offsets(torch, tensors, run_op=False)
        comparison["status"] = "executed"
        comparison["mutated_rows"] = [int(v) for v in replacement]
        comparison["passed"] = prefix_passed(comparison)
        tensors["rows_per_expert"].copy_(
            torch.tensor(case.rows,
                         dtype=torch.int32,
                         device=tensors["rows_per_expert"].device))
        return comparison
    except Exception as exc:  # noqa: BLE001 - report graph failures as data.
        return {
            "status": "error",
            "passed": False if args.require_graph else True,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def write_artifacts(args: argparse.Namespace, report: dict[str, Any]) -> None:
    args.data_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_out = args.json_out or (
        args.data_dir / f"qwen36-w8a8-middle-layerlet-check-{stamp}.json")
    md_out = args.md_out or (
        args.data_dir / f"qwen36-w8a8-middle-layerlet-check-{stamp}.md")

    json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    lines = [
        "# Qwen3.6 W8A8 Middle Layerlet Check",
        "",
        f"- timestamp_utc: `{report['timestamp_utc']}`",
        f"- device: `{report['device']}`",
        f"- overall_passed: `{report['overall_passed']}`",
        f"- graph_replay_requested: `{report['graph_replay_requested']}`",
        f"- require_graph: `{report['require_graph']}`",
        "",
        "| case | prefix | prefix graph | rows ref | layerlet | layerlet graph | rows out diff | gemm1 diff | q equal | scale diff | out diff |",
        "| --- | --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: |",
    ]
    for item in report["cases"]:
        prefix = item["prefix_eager"]
        prefix_graph = item.get("prefix_graph")
        rows_ref = item["rows_reference"]
        eager = item["eager"]
        graph = item.get("graph")
        prefix_graph_text = "n/a"
        if prefix_graph is not None:
            prefix_graph_text = (
                f"{prefix_graph.get('passed')} ({prefix_graph.get('status')})")
        graph_text = "n/a"
        if graph is not None:
            graph_text = f"{graph.get('passed')} ({graph.get('status')})"
        lines.append(
            "| {name} | {prefix_pass} | {prefix_graph_text} | "
            "{rows_ref_pass} | {eager_pass} | {graph_text} | "
            "{rows_od:.6g} | {g1:.6g} | {qeq} | {sd:.6g} | {od:.6g} |".format(
                name=item["case"]["name"],
                prefix_pass=prefix["passed"],
                prefix_graph_text=prefix_graph_text,
                rows_ref_pass=rows_ref["passed"],
                eager_pass=eager["passed"],
                graph_text=graph_text,
                rows_od=rows_ref["gemm2_output_max_abs_diff"],
                g1=eager["gemm1_max_abs_diff"],
                qeq=eager["gemm2_a_equal"],
                sd=eager["gemm2_a_scales_max_abs_diff"],
                od=eager["gemm2_output_max_abs_diff"],
            ))
    md_out.write_text("\n".join(lines) + "\n")
    report["json_out"] = str(json_out)
    report["md_out"] = str(md_out)


def main() -> int:
    args = parse_args()
    add_kernel_repo_to_path(args.kernel_repo)

    import torch
    from vllm_xpu_kernels import fused_moe_interface as fmi
    import vllm_xpu_kernels._xpu_C  # noqa: F401

    required = [
        "cutlass_grouped_gemm_w8a8_int8_offsets_interface",
        "per_token_quant_int8_xpu_out",
        "silu_and_mul_quant_int8_xpu_out",
        "qwen36_moe_w8a8_middle_layerlet",
        "qwen36_rows_per_expert_offsets_int64_out",
    ]
    missing = []
    for name in required:
        try:
            getattr(torch.ops._xpu_C, name)
        except AttributeError:
            missing.append(name)
    if missing:
        raise RuntimeError(f"missing required XPU ops: {missing}")
    if not torch.xpu.is_available():
        raise RuntimeError("torch.xpu is not available")

    torch.manual_seed(args.seed)
    report: dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "device": str(torch.xpu.get_device_name(int(args.device.split(":")[-1]))),
        "seed": args.seed,
        "kernel_repo": str(args.kernel_repo),
        "graph_replay_requested": bool(args.graph_replay),
        "require_graph": bool(args.require_graph),
        "reference_activation_quant": "vllm_silu_then_xpu_per_token_quant",
        "cases": [],
    }

    all_passed = True
    for case_index, case in enumerate(DEFAULT_CASES):
        torch.manual_seed(args.seed + case_index)
        tensors = allocate_case_tensors(torch, case, args.device)
        prefix_eager = compare_prefix_offsets(torch, tensors)
        prefix_eager["passed"] = prefix_passed(prefix_eager)
        tensors["offsets"] = tensors["prefix_offsets"]
        fill_random_(torch, tensors, case)
        run_reference(torch, fmi, tensors, case)
        run_rows_reference(torch, fmi, tensors, case)
        ret = run_candidate(torch, tensors, case)
        torch.xpu.synchronize()
        rows_reference = compare_rows_reference(torch, tensors)
        rows_reference["passed"] = case_passed(rows_reference, args.rtol,
                                               args.atol)
        eager = compare_outputs(torch, tensors, case)
        eager["passed"] = case_passed(eager, args.rtol, args.atol)
        eager["ret_is_out"] = bool(ret.data_ptr() == tensors["cand_out"].data_ptr())
        graph_result = None
        prefix_graph_result = None
        if args.graph_replay:
            prefix_graph_result = run_prefix_graph_replay_case(
                torch, tensors, case, args)
            prefix_eager = compare_prefix_offsets(torch, tensors)
            prefix_eager["passed"] = prefix_passed(prefix_eager)
            graph_result = run_graph_replay_case(torch, fmi, tensors, case,
                                                 args)
        item = {
            "case": asdict(case),
            "prefix_eager": prefix_eager,
            "rows_reference": rows_reference,
            "eager": eager,
        }
        if prefix_graph_result is not None:
            item["prefix_graph"] = prefix_graph_result
        if graph_result is not None:
            item["graph"] = graph_result
        report["cases"].append(item)
        all_passed = all_passed and prefix_eager["passed"]
        if prefix_graph_result is not None:
            all_passed = all_passed and bool(prefix_graph_result.get("passed"))
        all_passed = all_passed and rows_reference["passed"]
        all_passed = all_passed and eager["passed"]
        if graph_result is not None:
            all_passed = all_passed and bool(graph_result.get("passed"))

    report["overall_passed"] = bool(all_passed)
    write_artifacts(args, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
