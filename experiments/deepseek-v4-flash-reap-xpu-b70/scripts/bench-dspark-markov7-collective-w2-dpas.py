#!/usr/bin/env python3
"""Four-B70 captured gate for DPAS W2 in incumbent DSpark Markov.

This is a no-model-load component gate.  It retains the promoted replicated-W1,
sharded-W2, full-bias-all-gather transaction and changes only each stage's W2
projection from ``torch.mm(..., out=local_bias)`` to the exact BF16 DPAS op.
The synthetic base logits are controlled changed inputs; W1 activations and all
four W2 shards come from the real DSpark checkpoint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import time

import torch
import torch.distributed as dist
from safetensors import safe_open
import vllm_xpu_kernels._xpu_C as xpu_extension

from vllm.v1.worker.gpu.spec_decode.dspark.speculator import (
    _dspark_local_markov_embed_out_kernel,
)


WORLD = 4
STEPS = 7
VOCAB = 129280
MARKOV_RANK = 256
PARTITION = VOCAB // WORLD
W1_NAME = "mtp.2.markov_head.markov_w1.weight"
W2_NAME = "mtp.2.markov_head.markov_w2.weight"
ANCHORS = (17, PARTITION + 23, 2 * PARTITION + 31, VOCAB - 19, 97, 4421, 127999)
ROUTES = (
    "anchor_rank0_a",
    "anchor_rank1",
    "anchor_rank2",
    "anchor_rank3",
    "anchor_rank0_b",
    "anchor_rank0_c",
    "anchor_rank3_b",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tensor_sha256(tensor: torch.Tensor) -> str:
    cpu = tensor.detach().contiguous().cpu()
    return hashlib.sha256(cpu.view(torch.uint8).numpy().tobytes()).hexdigest()


def summarize(values: list[float]) -> dict[str, float]:
    return {
        "min_us": min(values),
        "median_us": statistics.median(values),
        "mean_us": statistics.fmean(values),
        "max_us": max(values),
    }


def load_target_ids(corpus: Path) -> tuple[torch.Tensor, dict[str, str]]:
    manifest_path = corpus / "rank0/verifier_logits_m8/000.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = manifest["tensors"]["top1_token_ids"]
    tensor = torch.load(corpus / entry["blob"], map_location="cpu", weights_only=True)
    if tuple(tensor.shape) != (STEPS + 1,) or tensor.dtype != torch.int64:
        raise RuntimeError(f"unexpected target token oracle {tensor.shape} {tensor.dtype}")
    return tensor.contiguous(), {
        "manifest": str(manifest_path),
        "blob": str(corpus / entry["blob"]),
        "blob_sha256": entry["blob_sha256"],
        "raw_sha256": entry["raw_sha256"],
    }


def changed_base_logits(route_index: int) -> torch.Tensor:
    generator = torch.Generator(device="cpu").manual_seed(0xB70D5A7 + route_index)
    base = torch.randn(
        (STEPS, VOCAB), generator=generator, dtype=torch.bfloat16
    ) * (1.5 + 0.125 * route_index)
    # Deterministic peaks make every changed route sensitive to a different
    # vocabulary partition without manufacturing the W2 output itself.
    for step in range(STEPS):
        peak = (ANCHORS[route_index] + (step + 1) * 7919) % VOCAB
        base[step, peak] = torch.tensor(18.0 + step, dtype=torch.bfloat16)
    return base.contiguous()


def mismatch_count(lhs: torch.Tensor, rhs: torch.Tensor) -> int:
    return int(torch.count_nonzero(lhs != rhs).item())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--target-corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--warmups", type=int, default=20)
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--replays-per-sample", type=int, default=100)
    parser.add_argument("--required-save-ms", type=float, default=0.15)
    args = parser.parse_args()

    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    if world_size != WORLD:
        raise SystemExit(f"requires four ranks, got {world_size}")
    if args.samples <= 0 or args.replays_per_sample <= 0 or args.warmups < 0:
        raise SystemExit("invalid timing counts")

    torch.xpu.set_device(local_rank)
    device = torch.device(f"xpu:{local_rank}")
    dist.init_process_group("xccl", device_id=device)

    with safe_open(args.weights, framework="pt", device="cpu") as handle:
        w1_cpu = handle.get_tensor(W1_NAME).contiguous()
        w2_cpu = handle.get_tensor(W2_NAME).contiguous()
    if (
        tuple(w1_cpu.shape) != (VOCAB, MARKOV_RANK)
        or tuple(w2_cpu.shape) != (VOCAB, MARKOV_RANK)
        or w1_cpu.dtype != torch.bfloat16
        or w2_cpu.dtype != torch.bfloat16
    ):
        raise RuntimeError(
            f"unexpected real Markov weights w1={w1_cpu.shape}/{w1_cpu.dtype} "
            f"w2={w2_cpu.shape}/{w2_cpu.dtype}"
        )
    full_w1 = w1_cpu.to(device)
    local_w2 = w2_cpu.narrow(0, rank * PARTITION, PARTITION).to(device)
    packed_local_w2 = local_w2.t().contiguous()
    if tuple(packed_local_w2.shape) != (MARKOV_RANK, PARTITION):
        raise RuntimeError(f"unexpected packed W2 {tuple(packed_local_w2.shape)}")
    del w1_cpu, w2_cpu, local_w2

    target_ids_cpu, target_identity = load_target_ids(args.target_corpus)
    target_ids = target_ids_cpu.to(device)
    cu_num_logits = torch.tensor([0, STEPS + 1], dtype=torch.int32, device=device)

    def make_state() -> dict[str, torch.Tensor]:
        return {
            "anchor": torch.empty((1,), dtype=torch.int64, device=device),
            "base": torch.empty((STEPS, VOCAB), dtype=torch.bfloat16, device=device),
            "embed": torch.empty(
                (1, MARKOV_RANK), dtype=torch.bfloat16, device=device
            ),
            "local_bias": torch.empty(
                (STEPS, PARTITION), dtype=torch.bfloat16, device=device
            ),
            "gathered_bias": torch.empty(
                (STEPS, WORLD, PARTITION), dtype=torch.bfloat16, device=device
            ),
            "logits": torch.empty(
                (STEPS, VOCAB), dtype=torch.bfloat16, device=device
            ),
            "prev": torch.empty((1,), dtype=torch.int64, device=device),
            "tokens": torch.empty((STEPS,), dtype=torch.int64, device=device),
        }

    control_state = make_state()
    candidate_state = make_state()

    def pre_collective(
        state: dict[str, torch.Tensor], use_dpas: bool, step: int
    ) -> None:
        token = state["anchor"] if step == 0 else state["prev"]
        _dspark_local_markov_embed_out_kernel[(1,)](
            token,
            full_w1,
            state["embed"],
            0,
            VOCAB,
            markov_rank=MARKOV_RANK,
            BLOCK_SIZE=256,
        )
        local_out = state["local_bias"].narrow(0, step, 1)
        if use_dpas:
            torch.ops._xpu_C.deepseek_markov_m1_bf16_dpas_out(
                local_out, state["embed"], packed_local_w2, 2
            )
        else:
            torch.mm(state["embed"], packed_local_w2, out=local_out)

    def post_collective(state: dict[str, torch.Tensor], step: int) -> None:
        gathered_out = state["gathered_bias"].select(0, step)
        logits_out = state["logits"].narrow(0, step, 1)
        torch.add(
            state["base"].narrow(0, step, 1),
            gathered_out.view(1, VOCAB),
            out=logits_out,
        )
        torch.argmax(logits_out, dim=-1, out=state["prev"])
        state["tokens"].narrow(0, step, 1).copy_(state["prev"])

    def eager_cycle(state: dict[str, torch.Tensor], use_dpas: bool) -> None:
        for step in range(STEPS):
            pre_collective(state, use_dpas, step)
            dist.all_gather_into_tensor(
                state["gathered_bias"].select(0, step),
                state["local_bias"].narrow(0, step, 1),
            )
            post_collective(state, step)

    def graph_cycle(
        state: dict[str, torch.Tensor],
        pre_graphs: list[torch.xpu.XPUGraph],
        post_graphs: list[torch.xpu.XPUGraph],
    ) -> None:
        for step in range(STEPS):
            pre_graphs[step].replay()
            dist.all_gather_into_tensor(
                state["gathered_bias"].select(0, step),
                state["local_bias"].narrow(0, step, 1),
            )
            post_graphs[step].replay()

    def snapshot(state: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
        return {
            name: state[name].detach().cpu().clone()
            for name in ("local_bias", "gathered_bias", "logits", "tokens")
        }

    def acceptance(tokens: torch.Tensor) -> tuple[list[int], int, int]:
        draft = torch.zeros((STEPS + 1,), dtype=torch.int32, device=device)
        draft[1:].copy_(tokens.to(device=device, dtype=torch.int32))
        sampled, num_sampled, num_rejected = (
            torch.ops._xpu_C.greedy_rejection_from_target_tokens(
                target_ids, draft, cu_num_logits, STEPS
            )
        )
        torch.xpu.synchronize()
        count = int(num_sampled.item())
        return (
            sampled[0, :count].cpu().tolist(),
            count,
            int(num_rejected.item()),
        )

    # Compile/JIT both arithmetic choices before graph capture.
    warm_base = changed_base_logits(0).to(device)
    for state in (control_state, candidate_state):
        state["anchor"].fill_(ANCHORS[0])
        state["base"].copy_(warm_base)
    eager_cycle(control_state, False)
    eager_cycle(candidate_state, True)
    torch.xpu.synchronize()

    # Mirror the incumbent breakable PIECEWISE transaction.  W2 remains inside
    # the pre-collective fixed-address graph segment; the already-existing
    # seven full-bias all-gathers stay explicit.  No event or host barrier is
    # introduced inside the component.
    control_pre: list[torch.xpu.XPUGraph] = []
    control_post: list[torch.xpu.XPUGraph] = []
    candidate_pre: list[torch.xpu.XPUGraph] = []
    candidate_post: list[torch.xpu.XPUGraph] = []
    dist.barrier()
    for step in range(STEPS):
        control_pre_graph = torch.xpu.XPUGraph()
        with torch.xpu.graph(control_pre_graph):
            pre_collective(control_state, False, step)
        control_pre.append(control_pre_graph)
        control_post_graph = torch.xpu.XPUGraph()
        with torch.xpu.graph(control_post_graph):
            post_collective(control_state, step)
        control_post.append(control_post_graph)
        candidate_pre_graph = torch.xpu.XPUGraph()
        with torch.xpu.graph(candidate_pre_graph):
            pre_collective(candidate_state, True, step)
        candidate_pre.append(candidate_pre_graph)
        candidate_post_graph = torch.xpu.XPUGraph()
        with torch.xpu.graph(candidate_post_graph):
            post_collective(candidate_state, step)
        candidate_post.append(candidate_post_graph)
    torch.xpu.synchronize()

    def time_component(call) -> float:
        dist.barrier()
        torch.xpu.synchronize()
        started = time.perf_counter_ns()
        for _ in range(args.replays_per_sample):
            call()
        torch.xpu.synchronize()
        return (time.perf_counter_ns() - started) / 1000.0 / args.replays_per_sample

    route_results: list[dict[str, object]] = []
    exact_count = 0
    for route_index, (route_name, anchor) in enumerate(
        zip(ROUTES, ANCHORS, strict=True)
    ):
        base_cpu = changed_base_logits(route_index)
        for state in (control_state, candidate_state):
            state["anchor"].fill_(anchor)
            state["base"].copy_(base_cpu.to(device))
        torch.xpu.synchronize()

        eager_cycle(control_state, False)
        torch.xpu.synchronize()
        eager_reference = snapshot(control_state)
        eager_acceptance = acceptance(eager_reference["tokens"])
        graph_cycle(control_state, control_pre, control_post)
        torch.xpu.synchronize()
        control_a = snapshot(control_state)
        control_accept_a = acceptance(control_a["tokens"])
        graph_cycle(candidate_state, candidate_pre, candidate_post)
        torch.xpu.synchronize()
        candidate_b = snapshot(candidate_state)
        candidate_accept_b = acceptance(candidate_b["tokens"])
        graph_cycle(control_state, control_pre, control_post)
        torch.xpu.synchronize()
        control_a2 = snapshot(control_state)
        control_accept_a2 = acceptance(control_a2["tokens"])

        fields = ("local_bias", "gathered_bias", "logits", "tokens")
        eager_mismatches = {
            name: mismatch_count(eager_reference[name], control_a[name])
            for name in fields
        }
        candidate_mismatches = {
            name: mismatch_count(control_a[name], candidate_b[name]) for name in fields
        }
        control_replay_mismatches = {
            name: mismatch_count(control_a[name], control_a2[name])
            for name in fields
        }
        route_exact = (
            not any(eager_mismatches.values())
            and not any(candidate_mismatches.values())
            and not any(control_replay_mismatches.values())
            and eager_acceptance
            == control_accept_a
            == candidate_accept_b
            == control_accept_a2
        )
        exact_count += int(route_exact)

        for _ in range(args.warmups):
            graph_cycle(control_state, control_pre, control_post)
            graph_cycle(candidate_state, candidate_pre, candidate_post)
        torch.xpu.synchronize()
        control_a_us: list[float] = []
        candidate_b_us: list[float] = []
        control_a2_us: list[float] = []
        for _ in range(args.samples):
            control_a_us.append(
                time_component(
                    lambda: graph_cycle(control_state, control_pre, control_post)
                )
            )
            candidate_b_us.append(
                time_component(
                    lambda: graph_cycle(candidate_state, candidate_pre, candidate_post)
                )
            )
            control_a2_us.append(
                time_component(
                    lambda: graph_cycle(control_state, control_pre, control_post)
                )
            )
        conservative_control_us = min(
            statistics.median(control_a_us), statistics.median(control_a2_us)
        )
        candidate_us = statistics.median(candidate_b_us)
        tokens = eager_reference["tokens"].tolist()
        route_results.append(
            {
                "route": route_name,
                "anchor": anchor,
                "anchor_owner": anchor // PARTITION,
                "base_logits_sha256": tensor_sha256(base_cpu),
                "exact": route_exact,
                "eager_control_mismatches": eager_mismatches,
                "candidate_mismatches": candidate_mismatches,
                "control_replay_mismatches": control_replay_mismatches,
                "seven_token_ids": tokens,
                "token_owners": [token // PARTITION for token in tokens],
                "acceptance": {
                    "eager_control": eager_acceptance,
                    "control_a": control_accept_a,
                    "candidate_b": candidate_accept_b,
                    "control_a2": control_accept_a2,
                    "target_token_ids": target_ids_cpu.tolist(),
                    "scope": "fixed real target-token component oracle; not endpoint acceptance",
                },
                "output_sha256": {
                    name: tensor_sha256(candidate_b[name]) for name in fields
                },
                "timing": {
                    "control_a": summarize(control_a_us),
                    "candidate_b": summarize(candidate_b_us),
                    "control_a2": summarize(control_a2_us),
                    "conservative_control_median_us": conservative_control_us,
                    "candidate_median_us": candidate_us,
                    "saved_ms_per_cycle": (
                        conservative_control_us - candidate_us
                    )
                    / 1000.0,
                },
            }
        )

    extension_path = Path(xpu_extension.__file__).resolve()
    local_result = {
        "rank": rank,
        "physical_card": local_rank,
        "device_name": torch.xpu.get_device_name(device),
        "aba_exact": exact_count,
        "aba_total": len(ROUTES),
        "routes": route_results,
        "worst_route": min(
            route_results, key=lambda row: row["timing"]["saved_ms_per_cycle"]
        )["route"],
        "worst_route_saved_ms_per_cycle": min(
            row["timing"]["saved_ms_per_cycle"] for row in route_results
        ),
        "xpu_extension": str(extension_path),
        "xpu_extension_sha256": sha256(extension_path),
    }
    gathered: list[dict[str, object] | None] = [None] * WORLD
    dist.all_gather_object(gathered, local_result)

    if rank == 0:
        ranks = [row for row in gathered if row is not None]
        exact = all(row["aba_exact"] == row["aba_total"] for row in ranks)
        global_floor = min(row["worst_route_saved_ms_per_cycle"] for row in ranks)
        result = {
            "schema_version": 1,
            "classification": "deepseek_v4_dspark_markov7_collective_w2_dpas_gate",
            "scope": "complete breakable-captured seven-stage component; not endpoint throughput",
            "passed": exact and global_floor >= args.required_save_ms,
            "exact": exact,
            "required_save_ms_per_cycle": args.required_save_ms,
            "slowest_card_worst_route_saved_ms_per_cycle": global_floor,
            "world_size": WORLD,
            "steps": STEPS,
            "warmups": args.warmups,
            "samples": args.samples,
            "replays_per_sample": args.replays_per_sample,
            "weights": str(args.weights),
            "weights_sha256": sha256(args.weights),
            "target_oracle": target_identity,
            "base_logits": "deterministic changed BF16 component inputs; not captured DSpark logits",
            "candidate": "deepseek_markov_m1_bf16_dpas_out tiles_per_item=2",
            "control": "torch.mm out=local_bias",
            "transport": "incumbent explicit full BF16 bias all_gather; no added graph break/event/host barrier",
            "ranks": ranks,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
    # The JSON gate is authoritative. Avoid a final rank-wide fail-code
    # broadcast/barrier: long graph batches can leave oneCCL teardown skewed,
    # and the old epilogue stranded otherwise-complete workers after output.
    dist.destroy_process_group()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
