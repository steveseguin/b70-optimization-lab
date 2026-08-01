#!/usr/bin/env python3
"""Changing-input TP4 probe for Laguna's M12 inline-gather composition."""

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
LAYERS = 48
ROWS = 12
HIDDEN = 3072


def _validate_output_root(value: str, *, require_absent: bool) -> pathlib.Path:
    root = pathlib.Path(value).resolve()
    allowed = pathlib.Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs")
    if root == allowed or allowed not in root.parents:
        raise ValueError(f"output root must be a child of {allowed}")
    if require_absent and root.exists():
        raise FileExistsError(f"output root already exists: {root}")
    mounts: list[tuple[int, str, str]] = []
    for line in pathlib.Path("/proc/self/mountinfo").read_text().splitlines():
        fields = line.split()
        separator = fields.index("-")
        mount_point = pathlib.Path(fields[4].replace("\\040", " ")).resolve()
        if mount_point == root or mount_point in root.parents:
            mounts.append(
                (len(str(mount_point)), fields[separator + 1], fields[separator + 2])
            )
    if not mounts:
        raise RuntimeError(f"no backing mount found for {root}")
    _, filesystem, source = max(mounts)
    if filesystem != "ext4" or not source.startswith("/dev/nvme"):
        raise RuntimeError(
            f"output root is not internal NVMe/ext4: {filesystem} {source}"
        )
    return root


def _host_root(torch, sample: int):
    indices = torch.arange(ROWS * HIDDEN, dtype=torch.int32)
    values = ((indices * 17 + sample * 1009) % 4096) - 2048
    return (
        values.to(torch.float32)
        .mul_(0.0009765625)
        .to(torch.bfloat16)
        .reshape(ROWS, HIDDEN)
    )


def _digest(torch, tensor) -> str:
    raw = tensor.contiguous().view(torch.uint8).cpu().numpy().tobytes()
    return hashlib.sha256(raw).hexdigest()


class _Arm:
    def __init__(self, torch, device, rank: int) -> None:
        self.torch = torch
        self.rank = rank
        self.root = torch.empty((ROWS, HIDDEN), dtype=torch.bfloat16, device=device)
        self.inputs = [self.root] + [torch.empty_like(self.root) for _ in range(LAYERS)]
        self.local_1 = [
            torch.empty((1, ROWS, HIDDEN), dtype=torch.bfloat16, device=device)
            for _ in range(LAYERS)
        ]
        self.local_2 = [torch.empty_like(self.local_1[0]) for _ in range(LAYERS)]
        self.gather_1 = [
            torch.empty((WORLD_SIZE, ROWS, HIDDEN), dtype=torch.bfloat16, device=device)
            for _ in range(LAYERS)
        ]
        self.gather_2 = [torch.empty_like(self.gather_1[0]) for _ in range(LAYERS)]
        self.sum_1 = [torch.empty_like(self.root) for _ in range(LAYERS)]
        self.sum_2 = [torch.empty_like(self.root) for _ in range(LAYERS)]
        self.scratch_1a = [torch.empty_like(self.root) for _ in range(LAYERS)]
        self.scratch_1b = [torch.empty_like(self.root) for _ in range(LAYERS)]
        self.scratch_2a = [torch.empty_like(self.root) for _ in range(LAYERS)]
        self.scratch_2b = [torch.empty_like(self.root) for _ in range(LAYERS)]
        self.layer_out = [torch.empty_like(self.root) for _ in range(LAYERS)]
        self.rank_bias = (rank - 1.5) * 0.0009765625

    def segment(self, dist, layer: int) -> None:
        torch = self.torch
        torch.mul(self.inputs[layer], 0.25, out=self.local_1[layer][0])
        self.local_1[layer][0].add_(self.rank_bias)
        dist.all_gather_into_tensor(self.gather_1[layer], self.local_1[layer])
        torch.add(
            self.gather_1[layer][0],
            self.gather_1[layer][1],
            out=self.scratch_1a[layer],
        )
        torch.add(
            self.scratch_1a[layer],
            self.gather_1[layer][2],
            out=self.scratch_1b[layer],
        )
        torch.add(
            self.scratch_1b[layer],
            self.gather_1[layer][3],
            out=self.sum_1[layer],
        )

        torch.mul(self.sum_1[layer], 0.25, out=self.local_2[layer][0])
        self.local_2[layer][0].add_(-self.rank_bias)
        dist.all_gather_into_tensor(self.gather_2[layer], self.local_2[layer])
        torch.add(
            self.gather_2[layer][0],
            self.gather_2[layer][1],
            out=self.scratch_2a[layer],
        )
        torch.add(
            self.scratch_2a[layer],
            self.gather_2[layer][2],
            out=self.scratch_2b[layer],
        )
        torch.add(
            self.scratch_2b[layer],
            self.gather_2[layer][3],
            out=self.sum_2[layer],
        )
        self.layer_out[layer].copy_(self.sum_2[layer])

    def eager_boundary(self, layer: int) -> None:
        # A fixed-output eager consumer/producer between captured segments.
        self.inputs[layer + 1].copy_(self.layer_out[layer])
        self.inputs[layer + 1].add_((layer % 7 - 3) * 0.000244140625)


def _first_mismatch(torch, control: _Arm, candidate: _Arm):
    fields = (
        ("local_1", control.local_1, candidate.local_1),
        ("gather_1", control.gather_1, candidate.gather_1),
        ("sum_1", control.sum_1, candidate.sum_1),
        ("local_2", control.local_2, candidate.local_2),
        ("gather_2", control.gather_2, candidate.gather_2),
        ("sum_2", control.sum_2, candidate.sum_2),
        ("layer_out", control.layer_out, candidate.layer_out),
    )
    comparisons = 0
    for layer in range(LAYERS):
        for stage, expected, actual in fields:
            comparisons += 1
            if not torch.equal(
                expected[layer].view(torch.uint8), actual[layer].view(torch.uint8)
            ):
                return comparisons, {"layer": layer, "stage": stage}
        comparisons += 1
        if not torch.equal(
            control.inputs[layer + 1].view(torch.uint8),
            candidate.inputs[layer + 1].view(torch.uint8),
        ):
            return comparisons, {"layer": layer, "stage": "eager_boundary"}
    return comparisons, None


def _run_initialized(args, torch, dist, rank: int, root: pathlib.Path) -> None:
    device = torch.device("xpu", rank)
    control = _Arm(torch, device, rank)
    candidate = _Arm(torch, device, rank)

    # Capture and immediately materialize each segment before the next eager
    # boundary establishes the following segment's fixed input address.
    candidate.root.copy_(_host_root(torch, 0).to(device))
    graphs = []
    dist.barrier()
    capture_started = time.monotonic()
    for layer in range(LAYERS):
        graph = torch.xpu.XPUGraph()
        with torch.xpu.graph(graph):
            candidate.segment(dist, layer)
        graph.replay()
        candidate.eager_boundary(layer)
        torch.xpu.synchronize()
        dist.barrier()
        graphs.append(graph)
    capture_seconds = time.monotonic() - capture_started

    total_comparisons = 0
    prior_digest = None
    changed_outputs = 0
    sample_digests: list[str] = []
    replay_started = time.monotonic()
    for sample in range(1, args.samples + 1):
        host_root = _host_root(torch, sample)

        control.root.copy_(host_root.to(device))
        for layer in range(LAYERS):
            control.segment(dist, layer)
            control.eager_boundary(layer)
        torch.xpu.synchronize()
        dist.barrier()

        candidate.root.copy_(host_root.to(device))
        for layer, graph in enumerate(graphs):
            graph.replay()
            candidate.eager_boundary(layer)
        torch.xpu.synchronize()
        dist.barrier()

        comparisons, mismatch = _first_mismatch(torch, control, candidate)
        total_comparisons += comparisons
        if mismatch is not None:
            raise RuntimeError(
                "raw composition mismatch "
                f"rank={rank} sample={sample} layer={mismatch['layer']} "
                f"stage={mismatch['stage']}"
            )
        digest = _digest(torch, candidate.inputs[-1])
        sample_digests.append(digest)
        if prior_digest is not None:
            changed_outputs += int(digest != prior_digest)
        prior_digest = digest

    replay_seconds = time.monotonic() - replay_started
    if changed_outputs != args.samples - 1:
        raise RuntimeError(
            f"final-output freshness failed: {changed_outputs}/{args.samples - 1}"
        )

    result = {
        "status": "pass",
        "rank": rank,
        "world_size": WORLD_SIZE,
        "layers": LAYERS,
        "rows": ROWS,
        "hidden": HIDDEN,
        "all_gathers_per_cycle": LAYERS * 2,
        "graph_segments": LAYERS,
        "eager_boundaries": LAYERS,
        "samples": args.samples,
        "raw_comparisons": total_comparisons,
        "changed_output_transitions": changed_outputs,
        "sample_final_sha256": sample_digests,
        "capture_seconds": capture_seconds,
        "replay_validation_seconds": replay_seconds,
        "torch_version": torch.__version__,
        "device_name": torch.xpu.get_device_name(rank),
        "probe_sha256": hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
        "runtime_environment": {
            name: os.environ.get(name)
            for name in (
                "ONEAPI_DEVICE_SELECTOR",
                "ZE_AFFINITY_MASK",
                "CCL_ATL_TRANSPORT",
                "CCL_TOPO_P2P_ACCESS",
                "CCL_KVS_IFACE",
                "FI_TCP_IFACE",
            )
        },
    }
    path = root / f"rank{rank}.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    path.chmod(0o444)
    dist.barrier()

    if rank == 0:
        ranks = [json.loads((root / f"rank{i}.json").read_text()) for i in range(4)]
        aggregate = {
            "format": "laguna-m12-inline-gather-composition-v1",
            "status": "pass" if all(r["status"] == "pass" for r in ranks) else "fail",
            "protocol": {
                "shape_per_rank": [1, ROWS, HIDDEN],
                "dtype": "bfloat16",
                "captured_producer_before_gather": True,
                "two_gathers_per_layer": True,
                "eager_fixed_output_boundary_between_layers": True,
                "fresh_root_each_replay": True,
                "final_all_reduce": False,
            },
            "ranks": ranks,
        }
        path = root / "aggregate.json"
        path.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n")
        path.chmod(0o444)
        root.chmod(0o555)
    dist.barrier()


def _run(args) -> None:
    import torch
    import torch.distributed as dist

    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    local_world_size = int(os.environ["LOCAL_WORLD_SIZE"])
    if world_size != 4 or local_world_size != 4 or rank != local_rank:
        raise RuntimeError("probe requires one host with RANK==LOCAL_RANK and TP4")
    root = _validate_output_root(args.output_root, require_absent=rank == 0)
    if torch.xpu.device_count() != 4:
        raise RuntimeError(
            f"expected four visible XPUs, got {torch.xpu.device_count()}"
        )
    torch.xpu.set_device(local_rank)
    initialized = False
    try:
        dist.init_process_group(
            "xccl",
            rank=rank,
            world_size=world_size,
            timeout=datetime.timedelta(seconds=180),
        )
        initialized = True
        if rank == 0:
            root.mkdir(parents=True, mode=0o755)
        dist.barrier()
        _run_initialized(args, torch, dist, rank, root)
    except BaseException as error:
        try:
            root.mkdir(parents=True, exist_ok=True)
            path = root / f"rank{rank}-failure.json"
            path.write_text(
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
            path.chmod(0o444)
        except OSError as marker_error:
            print(f"failure marker error: {marker_error}", file=sys.stderr, flush=True)
        raise
    finally:
        if initialized:
            dist.destroy_process_group()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--samples", type=int, default=4)
    args = parser.parse_args()
    if not 2 <= args.samples <= 8:
        parser.error("samples must be between 2 and 8")
    _run(args)


if __name__ == "__main__":
    main()
