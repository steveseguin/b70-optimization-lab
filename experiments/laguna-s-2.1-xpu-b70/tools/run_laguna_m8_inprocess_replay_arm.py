#!/usr/bin/env python3
"""One fresh q1/eager/graph arm for Laguna replay telemetry."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import time
from pathlib import Path
from typing import Any

TARGET = Path("/mnt/fast-ai/llm-models/laguna-s-2.1/int4")
DRAFT = Path("/mnt/fast-ai/llm-models/laguna-s-2.1/dflash-int4")
TARGET_REVISION = "4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb"
DRAFT_REVISION = "5e07c246915c86dc6920fead03d019989224f2ba"
VLLM_ROOT = Path("/home/steve/src/laguna-vllm-runtime-graph-20260724")
VLLM_COMMIT = "8cf58ed0f3679245053b6f298b4bf1ccd13906ed"
KERNEL_ROOT = Path("/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc")
KERNEL_COMMIT = "4772f727590c51b72add79350b913d098cf67872"
KERNELS = {
    "_C.abi3.so": "126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2",
    "_xpu_C.abi3.so": "f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8",
    "_moe_C.abi3.so": "6a6794249421aceb51f14980a3e2c0b0a9d7b492abf2f8d25b129b86f099bc5b",
    "libgrouped_gemm_xe_2.so": (
        "fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96"
    ),
}
PROMPT = (
    "Implement a Python function stable_partition(items, predicate) that returns "
    "the matching and non-matching items in their original relative order. "
    "Include type hints, a concise docstring, and four asserts covering an empty "
    "input, all true, all false, and mixed values. Return code only."
)
MAX_TOKENS = 128


def die(message: str) -> None:
    raise SystemExit(f"Laguna in-process replay arm: {message}")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_identity(root: Path, expected_commit: str, label: str) -> str:
    commit = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    status = subprocess.check_output(
        [
            "git",
            "-C",
            str(root),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        text=True,
    )
    if commit != expected_commit or status:
        die(f"{label} source identity drift: commit={commit} dirty={bool(status)}")
    return commit


def write_exclusive(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
        0o600,
    )
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                die("short arm-record write")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=("q1", "eager", "graph"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--profile-root", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    graph = args.arm == "graph"
    for path in (args.out, TARGET, DRAFT):
        resolved = path.resolve(strict=False)
        if (
            str(resolved).startswith("/media/")
            or "CorsairExternal" in str(resolved)
            or not resolved.is_relative_to(Path("/mnt/fast-ai"))
        ):
            die(f"non-NVMe path: {resolved}")
    if args.out.exists() or not TARGET.is_dir() or not DRAFT.is_dir():
        die("fresh output and both local model roots are required")
    if graph:
        if args.profile_root is None:
            die("graph arm requires a profile root")
        metadata = args.profile_root.lstat()
        if (
            args.profile_root.is_symlink()
            or not stat.S_ISDIR(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o700
            or any(args.profile_root.iterdir())
        ):
            die("graph profile root must be a fresh owner-private directory")
    elif args.profile_root is not None:
        die("only the graph arm may receive a profile root")

    import vllm
    import vllm_xpu_kernels

    vllm_root = Path(vllm.__file__).resolve().parents[1]
    if vllm_root != VLLM_ROOT:
        die(f"vLLM import origin drift: {vllm_root}")
    vllm_commit = git_identity(vllm_root, VLLM_COMMIT, "vLLM")
    kernel_commit = git_identity(KERNEL_ROOT, KERNEL_COMMIT, "kernel")
    kernel_package = Path(vllm_xpu_kernels.__file__).resolve().parent
    if kernel_package != (KERNEL_ROOT / "vllm_xpu_kernels").resolve():
        die(f"kernel package origin drift: {kernel_package}")
    kernel_identity = {}
    for name, expected in KERNELS.items():
        path = kernel_package / name
        actual = sha(path)
        if actual != expected:
            die(f"kernel binary drift: {path}")
        kernel_identity[name] = {"path": str(path), "sha256": actual}

    required = {
        "CCL_ATL_TRANSPORT": "ofi",
        "CCL_KVS_IFACE": "eno1",
        "CCL_TOPO_P2P_ACCESS": "1",
        "FI_TCP_IFACE": "eno1",
        "LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS": "7",
        "ONEAPI_DEVICE_SELECTOR": "level_zero:0,1,2,3",
        "TORCH_XCCL_ASYNC_ERROR_HANDLING": "1",
        "VLLM_DISABLE_SHARED_EXPERTS_STREAM": "0",
        "VLLM_KV_CACHE_LAYOUT": "NHD",
        "VLLM_SHARED_EXPERTS_STREAM_TOKEN_THRESHOLD": "256",
        "VLLM_TRACE_FUNCTION": "0",
        "VLLM_USE_AOT_COMPILE": "0",
        "VLLM_USE_BREAKABLE_CUDAGRAPH": "1" if graph else "0",
        "VLLM_XPU_ENABLE_XPU_GRAPH": "1" if graph else "0",
        "VLLM_XPU_EXACT_SPEC_ATTN": "1",
        "VLLM_XPU_EXPERT_MAP_ROUND_ROBIN": "0",
        "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE": "1",
        "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH": "0",
        "VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH": "1" if graph else "0",
        "VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM": "0",
        "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK": "0",
        "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2": "1",
        "VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION": "0",
        "VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE": "0",
        "VLLM_XPU_LAGUNA_M8_GATHER_SHARDED": "0",
        "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE": "1",
        "VLLM_XPU_LAGUNA_M8_REMOTE_ZERO": "0",
        "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE": "1",
        "VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM": "0",
        "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE": "1",
        "VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM": "0",
        "VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM": "0",
        "VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM": "0",
        "VLLM_XPU_LAGUNA_M8_W1_N_TILE": "64",
        "VLLM_XPU_LAGUNA_PARITY_PROBE": "0",
        "VLLM_XPU_V4_M1_BIASED_TOPK": "0",
        "VLLM_XPU_V4_M1_ROUTER_NORM": "0",
        "XPU_GRAPH": "1" if graph else "0",
        "ZE_AFFINITY_MASK": "0,1,2,3",
    }
    if graph:
        required.update(
            {
                "VLLM_XPU_LAGUNA_REPLAY_PROFILE_ROOT": str(args.profile_root),
                "VLLM_XPU_LAGUNA_REPLAY_PROFILE_SAMPLES": "31",
            }
        )
    for name, expected in required.items():
        if os.environ.get(name) != expected:
            die(f"{name}={os.environ.get(name)!r}, expected {expected!r}")
    forbidden = {
        "VLLM_XPU_LAGUNA_REPLAY_TRACE_SESSION",
        "VLLM_XPU_LAGUNA_REPLAY_TRACE_UNITRACE",
        "VLLM_XPU_LAGUNA_REPLAY_TRACE_UNITRACE_SHA256",
    }
    if forbidden.intersection(os.environ) or any(
        name.startswith("VLLM_XPU_LAGUNA_M8_EVIDENCE") for name in os.environ
    ):
        die("PTI/raw evidence variables are forbidden")
    if not graph and {
        "VLLM_XPU_LAGUNA_REPLAY_PROFILE_ROOT",
        "VLLM_XPU_LAGUNA_REPLAY_PROFILE_SAMPLES",
    }.intersection(os.environ):
        die("replay-profile variables are graph-only")

    from vllm import LLM, SamplingParams

    compilation_config = (
        {
            "mode": "NONE",
            "cudagraph_mode": "PIECEWISE",
            "cudagraph_capture_sizes": [8],
            "max_cudagraph_capture_size": 8,
        }
        if graph
        else None
    )
    kwargs: dict[str, Any] = {
        "model": str(TARGET),
        "revision": TARGET_REVISION,
        "tokenizer": str(TARGET),
        "tokenizer_revision": TARGET_REVISION,
        "trust_remote_code": True,
        "dtype": "bfloat16",
        "tensor_parallel_size": 4,
        "data_parallel_size": 1,
        "pipeline_parallel_size": 1,
        "distributed_executor_backend": "mp",
        "enable_expert_parallel": True,
        "all2all_backend": "allgather_reducescatter",
        "max_model_len": 8192,
        "max_num_batched_tokens": 8192,
        "max_num_seqs": 1,
        "block_size": 64,
        "kv_cache_dtype": "bfloat16",
        "gpu_memory_utilization": 0.90,
        "enable_prefix_caching": False,
        "async_scheduling": False,
        "generation_config": "vllm",
        "enforce_eager": not graph,
    }
    if args.arm != "q1":
        kwargs["speculative_config"] = {
            "method": "dflash",
            "model": str(DRAFT),
            "revision": DRAFT_REVISION,
            "num_speculative_tokens": 7,
            "draft_sample_method": "greedy",
            "rejection_sample_method": "standard",
        }
    if compilation_config is not None:
        kwargs["compilation_config"] = compilation_config

    llm = LLM(**kwargs)
    params = SamplingParams(
        temperature=0.0,
        top_p=1.0,
        max_tokens=MAX_TOKENS,
        seed=1,
        ignore_eos=True,
    )
    started_ns = time.monotonic_ns()
    generated = llm.generate([PROMPT], params, use_tqdm=False)
    wall_ns = time.monotonic_ns() - started_ns
    if len(generated) != 1 or len(generated[0].outputs) != 1:
        die("unexpected generation shape")
    output = generated[0].outputs[0]
    token_ids = list(output.token_ids)
    cached = getattr(generated[0], "num_cached_tokens", None)
    if cached != 0 or len(token_ids) != MAX_TOKENS:
        die(f"expected 128 uncached tokens, got tokens={len(token_ids)} cached={cached}")
    profile_rank_files = None
    if graph:
        assert args.profile_root is not None
        expected_names = {f"rank{rank}.json" for rank in range(4)}
        observed_names = {path.name for path in args.profile_root.iterdir()}
        if observed_names != expected_names:
            die(
                "graph generation did not close all four replay profiles: "
                f"{sorted(observed_names)}"
            )
        profile_rank_files = {}
        for rank in range(4):
            path = args.profile_root / f"rank{rank}.json"
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                die(f"cannot read rank{rank} replay profile: {exc}")
            if (
                not isinstance(payload, dict)
                or payload.get("status") != "complete"
                or payload.get("rank") != rank
                or payload.get("samples") != 31
                or not isinstance(payload.get("records"), list)
                or len(payload["records"]) != 31
            ):
                die(f"rank{rank} replay profile is incomplete")
            profile_rank_files[str(rank)] = {
                "path": str(path),
                "sha256": sha(path),
            }
    record = {
        "schema": "laguna-m8-inprocess-replay-arm-v1",
        "status": "complete",
        "diagnostic_only": True,
        "single_generate_call": True,
        "fresh_process": True,
        "arm": args.arm,
        "model": str(TARGET),
        "draft_model": str(DRAFT) if args.arm != "q1" else None,
        "vllm_root": str(vllm_root),
        "vllm_commit": vllm_commit,
        "kernel_root": str(KERNEL_ROOT),
        "kernel_commit": kernel_commit,
        "kernel_identity": kernel_identity,
        "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
        "prompt_tokens": len(generated[0].prompt_token_ids),
        "completion_tokens": len(token_ids),
        "cached_tokens": cached,
        "generation_wall_ns": wall_ns,
        "token_ids": token_ids,
        "token_ids_sha256": hashlib.sha256(
            json.dumps(token_ids, separators=(",", ":")).encode()
        ).hexdigest(),
        "text_sha256": hashlib.sha256(output.text.encode()).hexdigest(),
        "finish_reason": output.finish_reason,
        "profile_root": str(args.profile_root) if graph else None,
        "profile_samples": 31 if graph else None,
        "profile_rank_files": profile_rank_files,
        "compilation_config": compilation_config,
        "environment": {name: os.environ[name] for name in sorted(required)},
    }
    write_exclusive(args.out, record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
