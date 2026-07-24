#!/usr/bin/env python3
"""Probe direct XPU-graph capture of Laguna's fixed M8 TP4 gather pattern."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import sys
import time

WORLD_SIZE = 4
LAYERS = 97
ROWS = 8
HIDDEN = 3072


def _host_source(torch, rank: int, sample: int, layer: int):
    indices = torch.arange(ROWS * HIDDEN, dtype=torch.int32)
    values = ((indices * 17 + rank * 1009 + sample * 313 + layer * 47) % 8192) - 4096
    return (
        values.to(torch.float32)
        .mul_(0.03125)
        .to(torch.bfloat16)
        .reshape(1, ROWS, HIDDEN)
    )


def _raw_equal(torch, actual, expected) -> bool:
    return bool(torch.equal(actual.view(torch.uint8), expected.view(torch.uint8)))


def _digest(torch, tensor) -> str:
    raw = tensor.contiguous().view(torch.uint8).cpu().numpy().tobytes()
    return hashlib.sha256(raw).hexdigest()


def _validate_output_root(value: str, *, require_absent: bool = True) -> pathlib.Path:
    root = pathlib.Path(value).resolve()
    allowed = pathlib.Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs")
    if root == allowed or allowed not in root.parents:
        raise ValueError(f"output root must be a child of {allowed}")
    if require_absent and root.exists():
        raise FileExistsError(f"output root already exists: {root}")
    mount_candidates = []
    for line in pathlib.Path("/proc/self/mountinfo").read_text().splitlines():
        fields = line.split()
        separator = fields.index("-")
        mount_point = pathlib.Path(fields[4].replace("\\040", " ")).resolve()
        if mount_point == root or mount_point in root.parents:
            mount_candidates.append(
                (len(str(mount_point)), fields[separator + 1], fields[separator + 2])
            )
    if not mount_candidates:
        raise RuntimeError(f"no backing mount found for {root}")
    _, filesystem, source = max(mount_candidates)
    if filesystem != "ext4" or not source.startswith("/dev/nvme"):
        raise RuntimeError(
            f"output root is not backed by internal NVMe/ext4: {filesystem} {source}"
        )
    return root


def _run(args: argparse.Namespace) -> None:
    import torch
    import torch.distributed as dist

    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    local_world_size = int(os.environ["LOCAL_WORLD_SIZE"])
    if world_size != WORLD_SIZE or local_world_size != WORLD_SIZE or rank != local_rank:
        raise RuntimeError(
            "probe requires one host with RANK==LOCAL_RANK and world size 4"
        )

    output_root = _validate_output_root(
        args.output_root,
        require_absent=rank == 0,
    )
    if rank == 0:
        output_root.mkdir(parents=True, mode=0o755)
    if torch.xpu.device_count() != WORLD_SIZE:
        raise RuntimeError(
            f"expected exactly {WORLD_SIZE} visible XPUs, "
            f"got {torch.xpu.device_count()}"
        )
    torch.xpu.set_device(local_rank)

    initialized = False
    try:
        dist.init_process_group(
            "xccl",
            rank=rank,
            world_size=world_size,
            timeout=datetime.timedelta(seconds=120),
        )
        initialized = True
        _run_initialized(args, torch, dist, rank, output_root)
    except BaseException as error:
        try:
            output_root.mkdir(parents=True, exist_ok=True)
            failure_path = output_root / f"rank{rank}-failure.json"
            failure_path.write_text(
                json.dumps(
                    {
                        "status": "fail",
                        "rank": rank,
                        "error_type": type(error).__name__,
                        "error": str(error),
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            failure_path.chmod(0o444)
        except OSError as marker_error:
            print(
                f"could not write rank {rank} failure marker: {marker_error}",
                file=sys.stderr,
                flush=True,
            )
        raise
    finally:
        if initialized:
            dist.destroy_process_group()


def _run_initialized(args, torch, dist, rank: int, output_root: pathlib.Path) -> None:
    dist.barrier()

    sources = [
        torch.empty((1, ROWS, HIDDEN), dtype=torch.bfloat16, device="xpu")
        for _ in range(LAYERS)
    ]
    gathered = [
        torch.empty(
            (WORLD_SIZE, ROWS, HIDDEN),
            dtype=torch.bfloat16,
            device="xpu",
        )
        for _ in range(LAYERS)
    ]
    sums = [
        torch.empty((ROWS, HIDDEN), dtype=torch.bfloat16, device="xpu")
        for _ in range(LAYERS)
    ]
    scratch_01 = [torch.empty_like(sums[0]) for _ in range(LAYERS)]
    scratch_012 = [torch.empty_like(sums[0]) for _ in range(LAYERS)]
    final_source = torch.empty((ROWS, HIDDEN), dtype=torch.bfloat16, device="xpu")
    final_reduction = torch.empty_like(final_source)

    def collective_cycle() -> None:
        for layer in range(LAYERS):
            dist.all_gather_into_tensor(gathered[layer], sources[layer])
            torch.add(
                gathered[layer][0],
                gathered[layer][1],
                out=scratch_01[layer],
            )
            torch.add(
                scratch_01[layer],
                gathered[layer][2],
                out=scratch_012[layer],
            )
            torch.add(
                scratch_012[layer],
                gathered[layer][3],
                out=sums[layer],
            )
        final_reduction.copy_(final_source)
        dist.all_reduce(final_reduction)

    def stage_and_expected(sample: int):
        expected_gathered = []
        expected_sums = []
        for layer in range(LAYERS):
            host_rows = [
                _host_source(torch, source_rank, sample, layer)
                for source_rank in range(WORLD_SIZE)
            ]
            sources[layer].copy_(host_rows[rank])
            expected_gather = torch.cat(host_rows, dim=0).to("xpu")
            expected_sum = expected_gather[0].clone()
            for source_rank in range(1, WORLD_SIZE):
                expected_sum.add_(expected_gather[source_rank])
            expected_gathered.append(expected_gather)
            expected_sums.append(expected_sum)
        final_host_rows = [
            (
                (
                    torch.arange(ROWS * HIDDEN, dtype=torch.int32)
                    + source_rank * 11
                    + sample * 7
                )
                % 32
                - 16
            )
            .to(torch.bfloat16)
            .reshape(ROWS, HIDDEN)
            for source_rank in range(WORLD_SIZE)
        ]
        final_source.copy_(final_host_rows[rank])
        expected_final = final_host_rows[0].to("xpu")
        for source_rank in range(1, WORLD_SIZE):
            expected_final.add_(final_host_rows[source_rank].to("xpu"))
        return expected_gathered, expected_sums, expected_final

    stage_and_expected(0)
    collective_cycle()
    torch.xpu.synchronize()
    dist.barrier()

    graph = torch.xpu.XPUGraph()
    dist.barrier()
    capture_started = time.monotonic()
    with torch.xpu.graph(graph):
        collective_cycle()
    dist.barrier()
    capture_seconds = time.monotonic() - capture_started

    comparisons = 0
    prior_source_digest = None
    prior_output_digest = None
    changed_sources = 0
    changed_outputs = 0
    replay_started = time.monotonic()
    for epoch in range(args.epochs):
        for replay in range(args.replays_per_epoch):
            sample = epoch * args.replays_per_epoch + replay + 1
            expected_gathered, expected_sums, expected_final = stage_and_expected(
                sample
            )
            dist.barrier()
            graph.replay()
            torch.xpu.synchronize()

            for layer in range(LAYERS):
                if not _raw_equal(torch, gathered[layer], expected_gathered[layer]):
                    raise RuntimeError(
                        f"raw gathered mismatch rank={rank} sample={sample} "
                        f"layer={layer}"
                    )
                if not _raw_equal(torch, sums[layer], expected_sums[layer]):
                    raise RuntimeError(
                        f"raw fixed-rank sum mismatch rank={rank} sample={sample} "
                        f"layer={layer}"
                    )
                comparisons += 2
            if not _raw_equal(torch, final_reduction, expected_final):
                raise RuntimeError(
                    f"raw final all-reduce mismatch rank={rank} sample={sample}"
                )
            comparisons += 1

            source_digest = _digest(torch, sources[0])
            output_digest = _digest(torch, final_reduction)
            if prior_source_digest is not None:
                changed_sources += int(source_digest != prior_source_digest)
                changed_outputs += int(output_digest != prior_output_digest)
            prior_source_digest = source_digest
            prior_output_digest = output_digest

    replay_seconds = time.monotonic() - replay_started
    total_replays = args.epochs * args.replays_per_epoch
    if changed_sources != total_replays - 1:
        raise RuntimeError("source freshness check failed")
    if changed_outputs != total_replays - 1:
        raise RuntimeError("output freshness check failed")

    result = {
        "status": "pass",
        "rank": rank,
        "world_size": WORLD_SIZE,
        "layers_per_cycle": LAYERS,
        "all_gathers_per_cycle": LAYERS,
        "all_reduces_per_cycle": 1,
        "fixed_rank_bf16_adds_per_cycle": LAYERS * 3,
        "epochs": args.epochs,
        "replays_per_epoch": args.replays_per_epoch,
        "total_replays": total_replays,
        "raw_comparisons": comparisons,
        "changed_source_transitions": changed_sources,
        "changed_output_transitions": changed_outputs,
        "capture_seconds": capture_seconds,
        "replay_validation_seconds": replay_seconds,
        "final_source_sha256": prior_source_digest,
        "final_output_sha256": prior_output_digest,
        "torch_version": torch.__version__,
        "device_name": torch.xpu.get_device_name(rank),
    }
    rank_path = output_root / f"rank{rank}.json"
    rank_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    rank_path.chmod(0o444)
    dist.barrier()

    if rank == 0:
        ranks = [
            json.loads((output_root / f"rank{item}.json").read_text())
            for item in range(WORLD_SIZE)
        ]
        aggregate = {
            "format": "laguna-m8-xccl-direct-graph-probe-v1",
            "status": (
                "pass" if all(item["status"] == "pass" for item in ranks) else "fail"
            ),
            "protocol": {
                "layers_per_cycle": LAYERS,
                "shape_per_rank": [1, ROWS, HIDDEN],
                "dtype": "bfloat16",
                "epochs": args.epochs,
                "replays_per_epoch": args.replays_per_epoch,
                "raw_boundaries": [
                    "gathered",
                    "fixed_rank_sum",
                    "final_all_reduce",
                ],
                "fresh_inputs_each_replay": True,
            },
            "ranks": ranks,
        }
        aggregate_path = output_root / "aggregate.json"
        aggregate_path.write_text(
            json.dumps(aggregate, indent=2, sort_keys=True) + "\n"
        )
        aggregate_path.chmod(0o444)
        output_root.chmod(0o555)

    dist.barrier()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--epochs", type=int, default=32)
    parser.add_argument("--replays-per-epoch", type=int, default=4)
    args = parser.parse_args()
    if args.epochs < 1 or args.replays_per_epoch < 2:
        parser.error("epochs must be >=1 and replays-per-epoch must be >=2")
    _run(args)


if __name__ == "__main__":
    main()
