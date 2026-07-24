#!/usr/bin/env python3
"""One-generation Laguna M8 replay trace arm.

This is a diagnostic component run, not a throughput benchmark.  PTI starts
paused around process/model initialization.  After the LLM is fully
constructed, this driver resumes tracing, performs exactly one fresh
generation, pauses tracing, and records the uncached greedy output.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import stat
import subprocess
import time
from pathlib import Path
from typing import Any


TARGET_MODEL = Path("/mnt/fast-ai/llm-models/laguna-s-2.1/int4")
DRAFT_MODEL = Path("/mnt/fast-ai/llm-models/laguna-s-2.1/dflash-int4")
TARGET_REVISION = "4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb"
DRAFT_REVISION = "5e07c246915c86dc6920fead03d019989224f2ba"
VLLM_COMMIT = "b1cca41292296342fd9f0f7a5621e8d26d7a910d"
UNITRACE_SHA256 = "5aaca1f418a212a1d298cac27afb6c471bf1fcf47a1622e0c20d1a2cf43fc85a"
KERNEL_ROOT = Path("/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc")
KERNEL_BINARIES = {
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
    raise SystemExit(f"Laguna M8 replay trace arm: {message}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=("eager", "graph"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--unitrace", type=Path, required=True)
    parser.add_argument("--session", required=True)
    return parser.parse_args()


def require_identity(args: argparse.Namespace) -> dict[str, Any]:
    if not re.fullmatch(r"LagunaReplay[A-Za-z0-9]{32,48}", args.session):
        die("unitrace session is not a frozen high-entropy Laguna session")
    for path in (args.out, TARGET_MODEL, DRAFT_MODEL):
        resolved = path.resolve(strict=False)
        if str(resolved).startswith("/media/") or "CorsairExternal" in str(resolved):
            die(f"external/USB path is forbidden: {resolved}")
    if not args.out.resolve(strict=False).is_relative_to(Path("/mnt/fast-ai")):
        die("output must be on the internal NVMe")
    if args.out.exists():
        die("refusing to overwrite arm output")
    if not TARGET_MODEL.is_dir() or not DRAFT_MODEL.is_dir():
        die("internal-NVMe model roots are missing")
    descriptor = os.open(args.unitrace, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or sha256_file(Path(f"/proc/self/fd/{descriptor}")) != UNITRACE_SHA256
        ):
            die("unitrace identity drift")
    finally:
        os.close(descriptor)

    import vllm
    import vllm_xpu_kernels

    root = Path(vllm.__file__).resolve().parents[1]
    commit = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    if commit != VLLM_COMMIT:
        die(f"vLLM commit drift: {commit}")
    kernel_package = Path(vllm_xpu_kernels.__file__).resolve().parent
    expected_kernel_package = (KERNEL_ROOT / "vllm_xpu_kernels").resolve()
    if kernel_package != expected_kernel_package:
        die(f"XPU kernel package origin drift: {kernel_package}")
    kernel_files: dict[str, dict[str, str]] = {}
    for name, expected_sha in KERNEL_BINARIES.items():
        path = kernel_package / name
        actual_sha = sha256_file(path)
        if actual_sha != expected_sha:
            die(f"XPU kernel binary drift: {path}")
        kernel_files[name] = {"path": str(path), "sha256": actual_sha}
    return {
        "vllm_root": str(root),
        "vllm_commit": commit,
        "kernel_root": str(KERNEL_ROOT),
        "kernel_files": kernel_files,
        "unitrace": str(args.unitrace.resolve()),
        "unitrace_sha256": UNITRACE_SHA256,
    }


def control(unitrace: Path, action: str, session: str) -> dict[str, Any]:
    if action not in {"resume", "pause"}:
        die(f"invalid temporal-control action: {action}")
    descriptor = os.open(unitrace, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        before = os.fstat(descriptor)
        if sha256_file(Path(f"/proc/self/fd/{descriptor}")) != UNITRACE_SHA256:
            die("retained unitrace changed before temporal control")
        process = subprocess.run(
            [f"/proc/self/fd/{descriptor}", f"--{action}", session],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            pass_fds=(descriptor,),
            timeout=30,
            check=False,
        )
        after = os.fstat(descriptor)
        if (
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            or sha256_file(Path(f"/proc/self/fd/{descriptor}")) != UNITRACE_SHA256
        ):
            die("retained unitrace changed across temporal control")
    finally:
        os.close(descriptor)
    expected = f"[INFO] Session {session} is {action}d\n".encode()
    if process.returncode != 0 or process.stdout != b"" or process.stderr != expected:
        die(
            f"unitrace {action} acknowledgement drifted: "
            f"returncode={process.returncode}"
        )
    return {
        "action": action,
        "returncode": process.returncode,
        "stdout_sha256": hashlib.sha256(process.stdout).hexdigest(),
        "stderr_base64": base64.b64encode(process.stderr).decode(),
        "stderr_sha256": hashlib.sha256(process.stderr).hexdigest(),
    }


def main() -> int:
    args = parse_args()
    identity = require_identity(args)
    graph = args.arm == "graph"
    expected = {
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
        "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE": "1",
        "VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM": "0",
        "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE": "1",
        "VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM": "0",
        "VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM": "0",
        "VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM": "0",
        "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE": "1",
        "VLLM_XPU_LAGUNA_M8_REMOTE_ZERO": "0",
        "VLLM_XPU_LAGUNA_M8_W1_N_TILE": "64",
        "VLLM_XPU_LAGUNA_PARITY_PROBE": "0",
        "VLLM_XPU_LAGUNA_REPLAY_TRACE_SESSION": args.session,
        "VLLM_XPU_LAGUNA_REPLAY_TRACE_UNITRACE": str(args.unitrace),
        "VLLM_XPU_LAGUNA_REPLAY_TRACE_UNITRACE_SHA256": UNITRACE_SHA256,
        "VLLM_XPU_V4_M1_BIASED_TOPK": "0",
        "VLLM_XPU_V4_M1_ROUTER_NORM": "0",
        "XPU_GRAPH": "1" if graph else "0",
        "ZE_AFFINITY_MASK": "0,1,2,3",
    }
    for name, value in expected.items():
        if os.environ.get(name) != value:
            die(f"{name}={os.environ.get(name)!r}, expected {value!r}")
    if any(name.startswith("VLLM_XPU_LAGUNA_M8_EVIDENCE") for name in os.environ):
        die("raw evidence recorder must be absent from the timing trace")

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
        "model": str(TARGET_MODEL),
        "revision": TARGET_REVISION,
        "tokenizer": str(TARGET_MODEL),
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
        "speculative_config": {
            "method": "dflash",
            "model": str(DRAFT_MODEL),
            "revision": DRAFT_REVISION,
            "num_speculative_tokens": 7,
            "draft_sample_method": "greedy",
            "rejection_sample_method": "standard",
        },
    }
    if compilation_config is not None:
        kwargs["compilation_config"] = compilation_config

    # Model load and graph capture remain outside the traced interval.
    llm = LLM(**kwargs)
    params = SamplingParams(
        temperature=0.0,
        top_p=1.0,
        max_tokens=MAX_TOKENS,
        seed=1,
        ignore_eos=True,
    )
    resumed = (
        {
            "action": "runtime-first-replay",
            "contract": "all ranks paused before first replay; rank zero resumes",
        }
        if graph
        else control(args.unitrace, "resume", args.session)
    )
    started_ns = time.monotonic_ns()
    try:
        generated = llm.generate([PROMPT], params, use_tqdm=False)
    finally:
        finished_ns = time.monotonic_ns()
        paused = control(args.unitrace, "pause", args.session)
    if len(generated) != 1 or len(generated[0].outputs) != 1:
        die("offline generation returned an unexpected output shape")
    output = generated[0].outputs[0]
    token_ids = list(output.token_ids)
    cached_tokens = getattr(generated[0], "num_cached_tokens", None)
    if cached_tokens != 0 or len(token_ids) != MAX_TOKENS:
        die(
            f"expected {MAX_TOKENS} uncached output tokens, got "
            f"tokens={len(token_ids)} cached={cached_tokens!r}"
        )
    prompt_token_ids = list(generated[0].prompt_token_ids)
    record = {
        "schema": "laguna-m8-replay-trace-arm-v1",
        "status": "complete",
        "diagnostic_only": True,
        "not_benchmark_evidence": True,
        "single_generate_call": True,
        "fresh_process": True,
        "arm": args.arm,
        "session": args.session,
        "identity": identity,
        "model": str(TARGET_MODEL),
        "draft_model": str(DRAFT_MODEL),
        "target_revision": TARGET_REVISION,
        "draft_revision": DRAFT_REVISION,
        "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
        "max_tokens": MAX_TOKENS,
        "seed": 1,
        "cached_tokens": cached_tokens,
        "prompt_tokens": len(prompt_token_ids),
        "completion_tokens": len(token_ids),
        "generation_wall_ns": finished_ns - started_ns,
        "token_ids": token_ids,
        "token_ids_sha256": canonical_hash(token_ids),
        "text_sha256": hashlib.sha256(output.text.encode()).hexdigest(),
        "finish_reason": output.finish_reason,
        "compilation_config": compilation_config,
        "temporal_control": {"resume": resumed, "pause": paused},
        "environment": {name: os.environ[name] for name in sorted(expected)},
    }
    args.out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
