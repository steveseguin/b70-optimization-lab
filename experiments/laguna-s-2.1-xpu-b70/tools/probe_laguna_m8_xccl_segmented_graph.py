#!/usr/bin/env python3
"""Substrate-only M=8 XCCL/graph boundary gate; never a model benchmark.

This tool deliberately exercises the actual *model-forward* collective order
of vLLM commit 0964fe3d1: a graph prelude, one eager embedding BF16
``[8,3072]`` TP all-reduce, 96 eager BF16 ``[1,8,3072]`` TP all-gathers with
fixed-address graph work between them, then a graph tail.  It has no model,
tokenizer, endpoint, prompt, generation, cache, or network operation.

It is substrate evidence only.  Passing does not authorize a candidate or
prove that a real BreakableCUDAGraphCapture model trace has this topology.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time

WORLD_SIZE, GATHERS, ROWS, HIDDEN = 4, 96, 8, 3072
EXPECTED_EAGER, EXPECTED_GRAPHS = GATHERS + 1, GATHERS + 2
EXPECTED_NAME = "Intel(R) Arc(TM) Pro B70 Graphics"
EXPECTED_VLLM_SHA = "0964fe3d1b3508e39ee2455f70f1dbc7b13b0fd5"
SAFE_ENV = (
    "CCL_ATL_TRANSPORT",
    "ONEAPI_DEVICE_SELECTOR",
    "ZE_AFFINITY_MASK",
    "FI_TCP_IFACE",
    "CCL_KVS_IFACE",
    "CCL_TOPO_P2P_ACCESS",
    "LD_LIBRARY_PATH",
    "PYTHONDONTWRITEBYTECODE",
    "PYTHONNOUSERSITE",
    "TORCH_XCCL_ASYNC_ERROR_HANDLING",
    "VLLM_USE_BREAKABLE_CUDAGRAPH",
    "VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH",
)


def _sha256_path(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _raw_equal(torch, actual, expected) -> bool:
    return bool(torch.equal(actual.view(torch.uint8), expected.view(torch.uint8)))


def _digest(torch, tensor) -> str:
    return hashlib.sha256(
        tensor.contiguous().view(torch.uint8).cpu().numpy().tobytes()
    ).hexdigest()


def _owner_partitioned_embedding(rank: int, sample: int, torch):
    """One and only one rank owns every vocab-embedding output element.

    This mirrors the semantic reduction property of a vocab-parallel embedding:
    each shard contributes either its owned value or zero.  The values are
    small integers, exactly representable in BF16, so an XCCL tree cannot
    manufacture an order-dependent rounding discrepancy in this substrate test.
    """
    indices = torch.arange(ROWS * HIDDEN, dtype=torch.int32).reshape(ROWS, HIDDEN)
    owners = (indices + sample) % WORLD_SIZE
    values = ((indices * 13 + sample * 7) % 64) - 32
    return torch.where(owners == rank, values, torch.zeros_like(values)).to(
        torch.bfloat16
    )


def _nvme_ext4_child(value: str, create: bool) -> pathlib.Path:
    root = pathlib.Path(value).resolve()
    allowed = pathlib.Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs")
    if root == allowed or allowed not in root.parents:
        raise ValueError(f"output root must be a new child of {allowed}")
    if root.exists() and create:
        raise FileExistsError(f"output root already exists: {root}")
    mounts = []
    for line in pathlib.Path("/proc/self/mountinfo").read_text().splitlines():
        fields = line.split()
        dash = fields.index("-")
        mount = pathlib.Path(fields[4].replace("\\040", " ")).resolve()
        if mount == root or mount in root.parents:
            mounts.append((len(str(mount)), fields[dash + 1], fields[dash + 2]))
    if not mounts:
        raise RuntimeError("could not determine output backing mount")
    _, filesystem, source = max(mounts)
    if filesystem != "ext4" or not source.startswith("/dev/nvme"):
        raise RuntimeError(
            f"output must be internal NVMe/ext4, got {filesystem} {source}"
        )
    return root


def _command(argv: list[str], timeout: int = 20) -> str:
    completed = subprocess.run(
        argv,
        check=True,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    return completed.stdout


def _runtime_evidence(torch) -> dict:
    """Require four distinct physical B70s before initializing XCCL."""
    discovery = json.loads(_command(["xpu-smi", "discovery", "-j"]))
    devices = discovery.get("device_list")
    if not isinstance(devices, list) or len(devices) != WORLD_SIZE:
        raise RuntimeError("xpu-smi discovery did not expose exactly four devices")
    cards = []
    for device in devices:
        name = device.get("device_name")
        bdf, uuid = device.get("pci_bdf_address"), device.get("uuid")
        if (
            name != EXPECTED_NAME
            or not isinstance(bdf, str)
            or not isinstance(uuid, str)
        ):
            raise RuntimeError(f"invalid/non-B70 xpu-smi device: {device!r}")
        cards.append(
            {
                "device_id": device.get("device_id"),
                "device_name": name,
                "bdf": bdf,
                "uuid": uuid,
                "drm_device": device.get("drm_device"),
            }
        )
    if (
        len({x["bdf"] for x in cards}) != WORLD_SIZE
        or len({x["uuid"] for x in cards}) != WORLD_SIZE
    ):
        raise RuntimeError("B70 PCI BDF/UUID identities are not distinct")
    for card in cards:
        drm = card["drm_device"]
        if not isinstance(drm, str) or not pathlib.Path(drm).name.startswith("card"):
            raise RuntimeError(f"invalid B70 DRM identity: {drm!r}")
        sysfs = (
            pathlib.Path("/sys/class/drm") / pathlib.Path(drm).name / "device"
        ).resolve()
        vendor = (sysfs / "vendor").read_text().strip()
        product = (sysfs / "device").read_text().strip()
        if sysfs.name != card["bdf"] or vendor != "0x8086" or product != "0xe223":
            raise RuntimeError(f"B70 sysfs/PCI identity drift: {card!r}")
        card.update(
            {"sysfs_device": str(sysfs), "pci_vendor": vendor, "pci_product": product}
        )
    names = [torch.xpu.get_device_name(i) for i in range(torch.xpu.device_count())]
    if names != [EXPECTED_NAME] * WORLD_SIZE:
        raise RuntimeError(
            f"torch visible devices are not exactly four B70s: {names!r}"
        )
    return {
        "xpu_smi_devices": cards,
        "torch_xpu_names": names,
        "torch_version": torch.__version__,
        "torch_xpu_available": torch.xpu.is_available(),
        "xccl_library": getattr(torch._C, "_XCCL_VERSION", None),
    }


def _metadata(runtime_evidence: dict) -> dict:
    here = pathlib.Path(__file__).resolve()
    worktree = pathlib.Path("/home/steve/src/laguna-vllm-runtime-graph-20260724")
    vllm_sha = _command(["git", "-C", str(worktree), "rev-parse", "HEAD"]).strip()
    vllm_status = _command(
        ["git", "-C", str(worktree), "status", "--porcelain=v1"]
    ).strip()
    if vllm_sha != EXPECTED_VLLM_SHA or vllm_status:
        raise RuntimeError(
            "vLLM segmented source identity drifted: "
            f"sha={vllm_sha!r} dirty={bool(vllm_status)}"
        )
    return {
        "tool": str(here),
        "tool_sha256": _sha256_path(here),
        "vllm_worktree": str(worktree),
        "vllm_git_sha": vllm_sha,
        "argv": sys.argv,
        "safe_environment": {
            key: os.environ.get(key) for key in SAFE_ENV if key in os.environ
        },
        "python": sys.version,
        "pid": os.getpid(),
        "started_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "boot_id": pathlib.Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        "kernel_release": os.uname().release,
        "kernel_taint": pathlib.Path("/proc/sys/kernel/tainted").read_text().strip(),
        "runtime": runtime_evidence,
    }


def _failure(root: pathlib.Path, rank: int, error: BaseException) -> None:
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
    except OSError:
        pass


def _run(args: argparse.Namespace) -> None:
    import torch
    import torch.distributed as dist

    rank, local_rank = int(os.environ["RANK"]), int(os.environ["LOCAL_RANK"])
    if (
        int(os.environ["WORLD_SIZE"]) != WORLD_SIZE
        or int(os.environ["LOCAL_WORLD_SIZE"]) != WORLD_SIZE
        or rank != local_rank
    ):
        raise RuntimeError("requires one host, four ranks, and RANK == LOCAL_RANK")
    root = _nvme_ext4_child(args.output_root, create=rank == 0)
    if rank == 0:
        root.mkdir(parents=True, mode=0o755)
    initialized = False
    try:
        if torch.xpu.device_count() != WORLD_SIZE:
            raise RuntimeError("requires exactly four visible XPUs")
        torch.xpu.set_device(rank)
        runtime_evidence = _runtime_evidence(torch)
        evidence = _metadata(runtime_evidence)
        dist.init_process_group(
            "xccl",
            rank=rank,
            world_size=WORLD_SIZE,
            timeout=datetime.timedelta(seconds=args.timeout_seconds),
        )
        initialized = True
        _run_initialized(args, torch, dist, rank, root, evidence)
    except BaseException as error:
        _failure(root, rank, error)
        raise
    finally:
        if initialized:
            dist.destroy_process_group()


def _run_initialized(
    args, torch, dist, rank: int, root: pathlib.Path, evidence: dict
) -> None:
    # Every collective result and every graph-visible output has a permanent address.
    embed_stage = torch.empty((ROWS, HIDDEN), dtype=torch.bfloat16, device="xpu")
    embed_in = torch.empty((ROWS, HIDDEN), dtype=torch.bfloat16, device="xpu")
    embed_out = torch.empty_like(embed_in)
    embed_bridge = torch.empty_like(embed_in)
    local = [
        torch.empty((1, ROWS, HIDDEN), dtype=torch.bfloat16, device="xpu")
        for _ in range(GATHERS)
    ]
    gathered = [
        torch.empty((WORLD_SIZE, ROWS, HIDDEN), dtype=torch.bfloat16, device="xpu")
        for _ in range(GATHERS)
    ]
    sums = [
        torch.empty((ROWS, HIDDEN), dtype=torch.bfloat16, device="xpu")
        for _ in range(GATHERS)
    ]
    s01 = [torch.empty_like(embed_in) for _ in range(GATHERS)]
    s012 = [torch.empty_like(embed_in) for _ in range(GATHERS)]
    tail = torch.empty_like(embed_in)
    rank_bias = torch.full_like(embed_in, float(rank) - 1.5)
    persistent_tensors = (
        [embed_stage, embed_in, embed_out, embed_bridge]
        + local
        + gathered
        + sums
        + s01
        + s012
        + [tail, rank_bias]
    )
    pointer_signature = tuple(tensor.data_ptr() for tensor in persistent_tensors)
    if len(set(pointer_signature)) != len(pointer_signature):
        raise RuntimeError("persistent graph/collective buffers unexpectedly alias")
    pointer_signature_sha256 = hashlib.sha256(
        ",".join(map(str, pointer_signature)).encode()
    ).hexdigest()

    def graph_sum(i: int) -> None:
        torch.add(gathered[i][0], gathered[i][1], out=s01[i])
        torch.add(s01[i], gathered[i][2], out=s012[i])
        torch.add(s012[i], gathered[i][3], out=sums[i])
        if i + 1 < GATHERS:
            # This is the real dependency bridge: the graph consumes the prior
            # eager gather and produces the next eager gather's local input.
            # Division by four is an exact binary scale and keeps 96 hops bounded.
            local[i + 1].copy_(sums[i])
            local[i + 1].mul_(0.25)
            local[i + 1].add_(rank_bias)
        else:
            tail.copy_(sums[i])

    def stage(sample: int):
        host_embed = [
            _owner_partitioned_embedding(source_rank, sample, torch)
            for source_rank in range(WORLD_SIZE)
        ]
        embed_stage.copy_(host_embed[rank])
        expected_embed = torch.zeros_like(host_embed[0])
        for value in host_embed:
            expected_embed.add_(value)
        # Host-side expected recursion mirrors the fixed BF16 graph chain.
        expected = []
        for i in range(GATHERS):
            hosts = []
            for source_rank in range(WORLD_SIZE):
                source_bias = torch.full_like(expected_embed, float(source_rank) - 1.5)
                if i == 0:
                    source_local = expected_embed.clone().add_(source_bias)
                else:
                    prior_sum = expected[-1][1]
                    source_local = prior_sum.clone().mul_(0.25).add_(source_bias)
                hosts.append(source_local.reshape(1, ROWS, HIDDEN))
            gathered_expected = torch.cat(hosts, 0)
            summed = gathered_expected[0].clone()
            for source_rank in range(1, WORLD_SIZE):
                summed.add_(gathered_expected[source_rank])
            expected.append((gathered_expected, summed))
        return expected_embed.to("xpu"), [
            (gathered_expected.to("xpu"), summed.to("xpu"))
            for gathered_expected, summed in expected
        ]

    # Warmup fixes the eager operation sequence before capture; it is intentionally
    # not measured and has no model inputs.
    dist.barrier()
    stage(0)
    embed_in.copy_(embed_stage)
    dist.all_reduce(embed_in)
    embed_out.copy_(embed_in)
    embed_bridge.copy_(embed_out)
    local[0].copy_(embed_bridge)
    local[0].add_(rank_bias)
    for i in range(GATHERS):
        dist.all_gather_into_tensor(gathered[i], local[i])
        graph_sum(i)
    torch.xpu.synchronize()
    dist.barrier()
    prelude, bridge, graphs = (
        torch.xpu.XPUGraph(),
        torch.xpu.XPUGraph(),
        [],
    )
    capture_started = time.monotonic()
    with torch.xpu.graph(prelude):
        embed_in.copy_(embed_stage)
    with torch.xpu.graph(bridge):
        embed_bridge.copy_(embed_out)
        local[0].copy_(embed_bridge)
        local[0].add_(rank_bias)
    for i in range(GATHERS):
        graph = torch.xpu.XPUGraph()
        with torch.xpu.graph(graph):
            graph_sum(i)
        graphs.append(graph)
    capture_seconds = time.monotonic() - capture_started
    if len(graphs) + 2 != EXPECTED_GRAPHS:
        raise RuntimeError("graph topology count drift")
    dist.barrier()
    comparisons = changed_in = changed_out = 0
    prior_in = prior_out = None
    started = time.monotonic()
    for epoch in range(args.epochs):
        for replay in range(args.replays_per_epoch):
            sample = epoch * args.replays_per_epoch + replay + 1
            if tuple(tensor.data_ptr() for tensor in persistent_tensors) != (
                pointer_signature
            ):
                raise RuntimeError("persistent tensor address drift before replay")
            expected_embed, expected = stage(sample)
            dist.barrier()
            prelude.replay()
            embed_out.copy_(embed_in)
            dist.all_reduce(embed_out)
            bridge.replay()
            if not _raw_equal(torch, embed_out, expected_embed):
                raise RuntimeError(
                    f"raw embedding all-reduce mismatch rank={rank} sample={sample}"
                )
            comparisons += 1
            for i, (expected_gather, expected_sum) in enumerate(expected):
                dist.all_gather_into_tensor(gathered[i], local[i])
                graphs[i].replay()
                if not _raw_equal(torch, gathered[i], expected_gather):
                    raise RuntimeError(
                        f"raw gather mismatch rank={rank} sample={sample} slot={i}"
                    )
                if not _raw_equal(torch, sums[i], expected_sum):
                    raise RuntimeError(
                        f"raw graph sum mismatch rank={rank} sample={sample} slot={i}"
                    )
                comparisons += 2
            torch.xpu.synchronize()
            if not _raw_equal(torch, tail, expected[-1][1]):
                raise RuntimeError(
                    f"raw graph tail mismatch rank={rank} sample={sample}"
                )
            comparisons += 1
            inp, out = _digest(torch, embed_in), _digest(torch, tail)
            if prior_in is not None:
                changed_in += int(inp != prior_in)
                changed_out += int(out != prior_out)
            prior_in, prior_out = inp, out
    total = args.epochs * args.replays_per_epoch
    if (
        comparisons != total * (GATHERS * 2 + 2)
        or changed_in != total - 1
        or changed_out != total - 1
    ):
        raise RuntimeError("comparison/freshness evidence drift")
    result = {
        "status": "pass",
        "scope": "substrate_only_not_a_model_or_candidate",
        "rank": rank,
        "protocol": {
            "eager_order": ["embedding_all_reduce_bf16_[8,3072]"]
            + ["all_gather_bf16_[1,8,3072]"] * GATHERS,
            "eager_collectives": EXPECTED_EAGER,
            "graph_segments": EXPECTED_GRAPHS,
            "no_collective_captured": True,
            "changing_inputs": True,
        },
        "epochs": args.epochs,
        "replays_per_epoch": args.replays_per_epoch,
        "raw_comparisons": comparisons,
        "changed_input_transitions": changed_in,
        "changed_output_transitions": changed_out,
        "capture_seconds": capture_seconds,
        "validation_seconds": time.monotonic() - started,
        "final_input_sha256": prior_in,
        "final_tail_sha256": prior_out,
        "persistent_tensor_count": len(pointer_signature),
        "pointer_signature_sha256": pointer_signature_sha256,
        **evidence,
    }
    path = root / f"rank{rank}.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    path.chmod(0o444)
    dist.barrier()
    if rank == 0:
        ranks = [
            json.loads((root / f"rank{i}.json").read_text()) for i in range(WORLD_SIZE)
        ]
        aggregate = {
            "format": "laguna-m8-xccl-segmented-substrate-gate-v2",
            "status": "pass",
            "scope": "substrate_only_not_model_trace_not_candidate_authorization",
            "ranks": ranks,
        }
        (root / "aggregate.json").write_text(
            json.dumps(aggregate, indent=2, sort_keys=True) + "\n"
        )
        (root / "aggregate.json").chmod(0o444)
        root.chmod(0o555)
    dist.barrier()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root")
    parser.add_argument("--epochs", type=int, default=32)
    parser.add_argument("--replays-per-epoch", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="CPU-only topology and source-identity check; never imports torch",
    )
    args = parser.parse_args()
    if args.self_check:
        if (WORLD_SIZE, GATHERS, ROWS, HIDDEN) != (4, 96, 8, 3072):
            raise RuntimeError("fixed topology constants drifted")
        if (EXPECTED_EAGER, EXPECTED_GRAPHS) != (97, 98):
            raise RuntimeError("expected eager/graph topology drifted")
        worktree = pathlib.Path("/home/steve/src/laguna-vllm-runtime-graph-20260724")
        vllm_sha = _command(["git", "-C", str(worktree), "rev-parse", "HEAD"]).strip()
        if vllm_sha != EXPECTED_VLLM_SHA:
            raise RuntimeError(f"vLLM source identity drifted: {vllm_sha}")
        print(
            json.dumps(
                {
                    "status": "pass",
                    "scope": "cpu_only_substrate_tool_self_check",
                    "tool_sha256": _sha256_path(pathlib.Path(__file__).resolve()),
                    "eager_collectives": EXPECTED_EAGER,
                    "graph_segments": EXPECTED_GRAPHS,
                },
                sort_keys=True,
            )
        )
        return
    if not args.output_root:
        parser.error("--output-root is required unless --self-check is used")
    if args.epochs < 1 or args.replays_per_epoch < 2 or args.timeout_seconds < 30:
        parser.error("epochs>=1, replays>=2, timeout>=30 required")
    _run(args)


if __name__ == "__main__":
    main()
