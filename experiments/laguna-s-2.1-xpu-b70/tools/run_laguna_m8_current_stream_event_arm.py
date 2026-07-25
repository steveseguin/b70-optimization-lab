#!/usr/bin/env python3
"""One fresh arm for the Laguna current-stream event diagnostic.

This is deliberately not a benchmark runner.  It performs exactly one
uncached 272-token generation in a fresh process.  The graph arm enables the
one-shot, rank-local XPU event diagnostic; q1 is the canonical teacher arm.
"""

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

from laguna_m8_current_stream_event_contract import expected_environment

TARGET = Path("/mnt/fast-ai/llm-models/laguna-s-2.1/int4")
DRAFT = Path("/mnt/fast-ai/llm-models/laguna-s-2.1/dflash-int4")
TARGET_REVISION = "4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb"
DRAFT_REVISION = "5e07c246915c86dc6920fead03d019989224f2ba"
VLLM_ROOT = Path("/home/steve/src/laguna-vllm-runtime-graph-20260724")
VLLM_COMMIT = "fcc2506f7da3a9fd142928af9275d25b9687342a"
KERNEL_ROOT = Path("/home/steve/src/deepseek-v4-xpu-kernels-record-4772f727")
KERNEL_COMMIT = "4772f727590c51b72add79350b913d098cf67872"
KERNELS = {
    "_C.abi3.so": "126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2",
    "_xpu_C.abi3.so": "f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8",
    "_moe_C.abi3.so": "6a6794249421aceb51f14980a3e2c0b0a9d7b492abf2f8d25b129b86f099bc5b",
    "_vllm_fa2_C.abi3.so": "e6faed930bbcd7a366cc55281b99e1a8d7016a8db40ab10015d78f72937c8e64",
    "libattn_kernels_xe_2.so": "680d486970eb58dc63f0b7ef41e028e2bb4b5a630a2987c96f8609d46a00e161",
    "libgdn_attn_kernels_xe_2.so": "cdcf9539ac1715ef1dd9a81df422dd5bc1f3a58eff93e1bc5bde05959b5d34bb",
    "libgrouped_gemm_xe_2.so": "fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96",
    "libgrouped_gemm_xe_default.so": "982fb0b7fc96c877aaefa33f3342936af9403ed3960106dececf08697d98d53c",
    "libmhc_kernels_xe_2.so": "f689c3d200731167394c387d267df90311fd5ec21eff9dededb619e871ce1a4f",
    "libmqa_logits_kernels_xe_2.so": "58cca1a0507914762b36874d719557715f3a8ae045106bc0aed42bd16e5b6aeb",
}
PROMPT = (
    "Implement a Python function stable_partition(items, predicate) that returns "
    "the matching and non-matching items in their original relative order. "
    "Include type hints, a concise docstring, and four asserts covering an empty "
    "input, all true, all false, and mixed values. Return code only."
)
MAX_TOKENS = 272
RANKS = tuple(range(4))


def die(message: str) -> None:
    raise SystemExit(f"Laguna current-stream event arm: {message}")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_identity(root: Path, expected: str, label: str) -> str:
    commit = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    status = subprocess.check_output(
        ["git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"],
        text=True,
    )
    if commit != expected or status:
        die(f"{label} source identity drift: commit={commit} dirty={bool(status)}")
    return commit


def write_exclusive(path: Path, value: dict[str, Any]) -> None:
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o600
    )
    try:
        offset = 0
        while offset < len(raw):
            written = os.write(descriptor, raw[offset:])
            if written <= 0:
                die("short arm-record write")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=("q1", "graph-event"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--event-root", type=Path)
    return parser.parse_args()


def _safe_event_root(root: Path) -> None:
    try:
        metadata = root.lstat()
        resolved = root.resolve(strict=True)
    except OSError as exc:
        die(f"event root is unavailable: {exc}")
    if (
        not root.is_absolute()
        or root.is_symlink()
        or not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o700
        or not resolved.is_relative_to(Path("/mnt/fast-ai"))
        or str(resolved).startswith("/media/")
        or "CorsairExternal" in str(resolved)
        or any(resolved.iterdir())
    ):
        die("event root must be fresh, owner-private, internal NVMe")


def main() -> int:
    args = parse_args()
    graph = args.arm == "graph-event"
    for path in (args.out, TARGET, DRAFT):
        resolved = path.resolve(strict=False)
        if (
            str(resolved).startswith("/media/")
            or "CorsairExternal" in str(resolved)
            or not resolved.is_relative_to(Path("/mnt/fast-ai"))
        ):
            die(f"non-NVMe path: {resolved}")
    if (
        args.out.exists()
        or args.out.is_symlink()
        or not TARGET.is_dir()
        or not DRAFT.is_dir()
    ):
        die("fresh output and both local model roots are required")
    if graph:
        if args.event_root is None:
            die("graph-event arm requires an event root")
        _safe_event_root(args.event_root)
    elif args.event_root is not None:
        die("q1 arm must not receive an event root")

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

    required = expected_environment(graph, args.event_root)
    for name, expected in required.items():
        if os.environ.get(name) != expected:
            die(f"{name}={os.environ.get(name)!r}, expected {expected!r}")
    forbidden = {
        "VLLM_XPU_LAGUNA_REPLAY_PROFILE_ROOT",
        "VLLM_XPU_LAGUNA_REPLAY_PROFILE_SAMPLES",
        "VLLM_XPU_LAGUNA_REPLAY_TRACE_SESSION",
        "VLLM_XPU_LAGUNA_REPLAY_TRACE_UNITRACE",
        "VLLM_XPU_LAGUNA_REPLAY_TRACE_UNITRACE_SHA256",
    }
    if forbidden.intersection(os.environ) or any(
        name.startswith("VLLM_XPU_LAGUNA_M8_EVIDENCE") for name in os.environ
    ):
        die("incompatible profiling/evidence variables are forbidden")
    if not graph and "VLLM_XPU_LAGUNA_REPLAY_EVENT_PROFILE_ROOT" in os.environ:
        die("event profile variable is graph-event-only")

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
        "async_scheduling": args.arm == "q1",
        "generation_config": "vllm",
        "enforce_eager": not graph,
    }
    if graph:
        kwargs["speculative_config"] = {
            "method": "dflash",
            "model": str(DRAFT),
            "revision": DRAFT_REVISION,
            "num_speculative_tokens": 7,
            "draft_sample_method": "greedy",
            "rejection_sample_method": "standard",
        }
        kwargs["compilation_config"] = compilation_config
    llm = LLM(**kwargs)
    params = SamplingParams(
        temperature=0.0, top_p=1.0, max_tokens=MAX_TOKENS, seed=1, ignore_eos=True
    )
    started_ns = time.monotonic_ns()
    generated = llm.generate([PROMPT], params, use_tqdm=False)
    wall_ns = time.monotonic_ns() - started_ns
    if len(generated) != 1 or len(generated[0].outputs) != 1:
        die("unexpected generation shape")
    output = generated[0].outputs[0]
    token_ids = list(output.token_ids)
    cached = getattr(generated[0], "num_cached_tokens", None)
    if cached != 0 or len(token_ids) != MAX_TOKENS or output.finish_reason != "length":
        die(
            f"expected {MAX_TOKENS} uncached length-limited tokens, got tokens={len(token_ids)} cached={cached} finish={output.finish_reason!r}"
        )
    profile_rank_files = None
    if graph:
        assert args.event_root is not None
        expected = {f"rank{rank}.json" for rank in RANKS}
        observed = {path.name for path in args.event_root.iterdir()}
        if observed != expected:
            die(
                f"graph generation did not close four event profiles: {sorted(observed)}"
            )
        profile_rank_files = {}
        for rank in RANKS:
            path = args.event_root / f"rank{rank}.json"
            metadata = path.lstat()
            if (
                path.is_symlink()
                or not stat.S_ISREG(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) != 0o600
            ):
                die(f"rank{rank} event profile is unsafe")
            payload = json.loads(path.read_text(encoding="utf-8"))
            if (
                not isinstance(payload, dict)
                or payload.get("schema") != "laguna-m8-current-stream-event-profile-v1"
                or payload.get("status") != "complete"
                or payload.get("rank") != rank
            ):
                die(f"rank{rank} event profile is incomplete")
            profile_rank_files[str(rank)] = {"path": str(path), "sha256": sha(path)}
    record = {
        "schema": "laguna-m8-current-stream-event-arm-v1",
        "status": "complete",
        "diagnostic_only": True,
        "not_benchmark_or_submission_evidence": True,
        "single_generate_call": True,
        "fresh_process": True,
        "arm": args.arm,
        "graph": graph,
        "model": str(TARGET),
        "draft_model": str(DRAFT) if graph else None,
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
        "event_root": str(args.event_root) if graph else None,
        "event_rank_files": profile_rank_files,
        "compilation_config": compilation_config,
        "async_scheduling": args.arm == "q1",
        "environment": {name: os.environ[name] for name in sorted(required)},
    }
    write_exclusive(args.out, record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
