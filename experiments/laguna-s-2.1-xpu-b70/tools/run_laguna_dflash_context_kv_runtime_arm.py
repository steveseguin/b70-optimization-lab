#!/usr/bin/env python3
"""One fresh, non-timing TP4 Laguna context-KV runtime arm."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any

from analyze_laguna_m8_actual_offline_gate import aggregate_recorder_root


SCHEMA = "laguna-dflash-context-kv-runtime-arm-v1"
EVIDENCE_ARM = "segmented-graph"
TARGET_MODEL = Path("/mnt/fast-ai/llm-models/laguna-s-2.1/int4")
DRAFT_MODEL = Path("/mnt/fast-ai/llm-models/laguna-s-2.1/dflash-int4")
TARGET_REVISION = "4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb"
DRAFT_REVISION = "5e07c246915c86dc6920fead03d019989224f2ba"
VLLM_COMMIT = "7c38a20229b7bcd0f149e3e9a6b6b5493c3bd85b"
MODEL_MANIFEST_SHA256 = (
    "45aa105ef4eceaf05cad33012e0752369f77cbbd76f2213ccfe0ce130fa6c0ac"
)
PROMPT_ID = "python-lru-cache"
PROMPT = (
    "Implement a production-quality Python LRUCache class with get and put in "
    "O(1), capacity validation, type hints, and a short unittest example. "
    "Explain the invariants briefly. Include enough implementation and review "
    "detail for a maintainer to use the answer directly."
)
MAX_TOKENS = 32
SEED = 1
RPC_DIRS = {
    "control": Path(
        "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/dckvr-a"
    ),
    "candidate": Path(
        "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp/dckvr-b"
    ),
}
RECORDED_ENVIRONMENT = (
    "CCL_ATL_TRANSPORT",
    "CCL_KVS_IFACE",
    "CCL_TOPO_P2P_ACCESS",
    "FI_TCP_IFACE",
    "HF_HUB_OFFLINE",
    "LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS",
    "ONEAPI_DEVICE_SELECTOR",
    "PYTHONPATH",
    "TRANSFORMERS_OFFLINE",
    "TORCH_XCCL_ASYNC_ERROR_HANDLING",
    "VLLM_DISABLE_SHARED_EXPERTS_STREAM",
    "VLLM_KV_CACHE_LAYOUT",
    "VLLM_NO_USAGE_STATS",
    "VLLM_RPC_BASE_PATH",
    "VLLM_SHARED_EXPERTS_STREAM_TOKEN_THRESHOLD",
    "VLLM_TRACE_FUNCTION",
    "VLLM_USE_AOT_COMPILE",
    "VLLM_USE_BREAKABLE_CUDAGRAPH",
    "VLLM_XPU_EXPERT_MAP_ROUND_ROBIN",
    "VLLM_XPU_ENABLE_XPU_GRAPH",
    "VLLM_XPU_EXACT_SPEC_ATTN",
    "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE",
    "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH",
    "VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE",
    "VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_RUNTIME_TRACE",
    "VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_RUNTIME_TRACE_ROOT",
    "VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM",
    "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK",
    "VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH",
    "VLLM_XPU_LAGUNA_M8_CAPTURE_ATTENTION_GRAPHS",
    "VLLM_XPU_LAGUNA_M8_EVIDENCE",
    "VLLM_XPU_LAGUNA_M8_EVIDENCE_ARM",
    "VLLM_XPU_LAGUNA_M8_EVIDENCE_ROOT",
    "VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION",
    "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2",
    "VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE",
    "VLLM_XPU_LAGUNA_M8_GATHER_SHARDED",
    "VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA",
    "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE",
    "VLLM_XPU_LAGUNA_M8_REMOTE_ZERO",
    "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE",
    "VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM",
    "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE",
    "VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM",
    "VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM",
    "VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM",
    "VLLM_XPU_LAGUNA_M8_W1_N_TILE",
    "VLLM_XPU_LAGUNA_PARITY_PROBE",
    "VLLM_XPU_V4_M1_BIASED_TOPK",
    "VLLM_XPU_V4_M1_ROUTER_NORM",
    "XPU_GRAPH",
    "ZE_AFFINITY_MASK",
)


def die(message: str) -> None:
    raise SystemExit(f"Laguna context-KV runtime arm: {message}")


def digest_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_manifest(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): sha256_file(path)
        for path in sorted(root.iterdir())
        if path.is_file() and not path.is_symlink()
    }


def write_exclusive(path: Path, value: dict[str, Any]) -> None:
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    descriptor = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_CLOEXEC
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                die("short exclusive output write")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def require_private_nvme_dir(path: Path, *, empty: bool) -> Path:
    try:
        metadata = path.lstat()
        resolved = path.resolve(strict=True)
        nvme = Path("/mnt/fast-ai").resolve(strict=True)
    except OSError as exc:
        die(f"cannot inspect private NVMe directory {path}: {exc}")
    if (
        resolved != path
        or path.is_symlink()
        or not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o700
        or not resolved.is_relative_to(nvme)
        or resolved == nvme
        or resolved.stat().st_dev != nvme.stat().st_dev
        or (empty and any(resolved.iterdir()))
    ):
        die(f"invalid private NVMe directory: {path}")
    return resolved


def frozen_environment(
    treatment: str, evidence_dir: Path, trace_dir: Path, rpc_dir: Path
) -> dict[str, str]:
    selector = "1" if treatment == "candidate" else "0"
    return {
        "CCL_ATL_TRANSPORT": "ofi",
        "CCL_KVS_IFACE": "eno1",
        "CCL_TOPO_P2P_ACCESS": "1",
        "FI_TCP_IFACE": "eno1",
        "HF_HUB_OFFLINE": "1",
        "LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS": "7",
        "ONEAPI_DEVICE_SELECTOR": "level_zero:0,1,2,3",
        "PYTHONPATH": (
            "/home/steve/llm-optimizations/"
            "experiments/laguna-s-2.1-xpu-b70/tools:"
            "/home/steve/src/laguna-vllm-dflash-persistent-metadata-20260725:"
            "/home/steve/src/deepseek-v4-xpu-kernels-record-4772f727"
        ),
        "TRANSFORMERS_OFFLINE": "1",
        "TORCH_XCCL_ASYNC_ERROR_HANDLING": "1",
        "VLLM_DISABLE_SHARED_EXPERTS_STREAM": "0",
        "VLLM_KV_CACHE_LAYOUT": "NHD",
        "VLLM_NO_USAGE_STATS": "1",
        "VLLM_RPC_BASE_PATH": str(rpc_dir),
        "VLLM_SHARED_EXPERTS_STREAM_TOKEN_THRESHOLD": "256",
        "VLLM_TRACE_FUNCTION": "0",
        "VLLM_USE_AOT_COMPILE": "0",
        "VLLM_USE_BREAKABLE_CUDAGRAPH": "1",
        "VLLM_XPU_EXPERT_MAP_ROUND_ROBIN": "0",
        "VLLM_XPU_ENABLE_XPU_GRAPH": "1",
        "VLLM_XPU_EXACT_SPEC_ATTN": "1",
        "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE": "1",
        "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH": "0",
        "VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE": selector,
        "VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_RUNTIME_TRACE": "1",
        "VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_RUNTIME_TRACE_ROOT": str(trace_dir),
        "VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM": "0",
        "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK": "0",
        "VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH": "1",
        "VLLM_XPU_LAGUNA_M8_CAPTURE_ATTENTION_GRAPHS": "0",
        "VLLM_XPU_LAGUNA_M8_EVIDENCE": "1",
        "VLLM_XPU_LAGUNA_M8_EVIDENCE_ARM": EVIDENCE_ARM,
        "VLLM_XPU_LAGUNA_M8_EVIDENCE_ROOT": str(evidence_dir),
        "VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION": "0",
        "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2": "1",
        "VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE": "0",
        "VLLM_XPU_LAGUNA_M8_GATHER_SHARDED": "0",
        "VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA": "1",
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
        "XPU_GRAPH": "1",
        "ZE_AFFINITY_MASK": "0,1,2,3",
    }


def required_environment(
    treatment: str, evidence_dir: Path, trace_dir: Path, rpc_dir: Path
) -> None:
    required = frozen_environment(treatment, evidence_dir, trace_dir, rpc_dir)
    drift = {
        name: (os.environ.get(name), expected)
        for name, expected in required.items()
        if os.environ.get(name) != expected
    }
    if drift:
        die(f"frozen environment drift: {drift}")
    if set(required) != set(RECORDED_ENVIRONMENT):
        die("recorded environment allowlist drift")


def runtime_identity() -> dict[str, str]:
    import vllm

    module = Path(vllm.__file__).resolve()
    root = module.parents[1]
    commit = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    if commit != VLLM_COMMIT:
        die(f"vLLM commit drift: {commit}")
    return {
        "vllm_module": str(module),
        "vllm_root": str(root),
        "vllm_commit": commit,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--treatment", choices=("control", "candidate"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--trace-dir", type=Path, required=True)
    parser.add_argument("--rpc-dir", type=Path, required=True)
    args = parser.parse_args()

    if (
        args.out.exists()
        or args.out.is_symlink()
        or args.evidence_dir.exists()
        or args.trace_dir.is_symlink()
    ):
        die("output or evidence path is not fresh")
    arm_root = require_private_nvme_dir(args.out.parent, empty=False)
    rpc_dir = require_private_nvme_dir(args.rpc_dir, empty=True)
    trace_dir = require_private_nvme_dir(args.trace_dir, empty=True)
    if (
        args.out.parent.resolve() != arm_root
        or args.out != arm_root / "driver.json"
        or args.evidence_dir != arm_root / "evidence"
        or trace_dir != arm_root / "dflash-lifecycle"
        or args.rpc_dir != RPC_DIRS[args.treatment]
    ):
        die("arm output/evidence/RPC identity drift")
    required_environment(
        args.treatment,
        args.evidence_dir,
        trace_dir,
        rpc_dir,
    )
    if not TARGET_MODEL.is_dir() or not DRAFT_MODEL.is_dir():
        die("local target or draft model is absent")
    identity = runtime_identity()

    args.evidence_dir.mkdir(mode=0o700)
    if stat.S_IMODE(args.evidence_dir.stat().st_mode) != 0o700:
        die("evidence directory mode drift")

    from vllm import LLM, SamplingParams

    compilation_config = {
        "mode": "NONE",
        "cudagraph_mode": "PIECEWISE",
        "cudagraph_capture_sizes": [8],
        "max_cudagraph_capture_size": 8,
    }
    speculative_config = {
        "method": "dflash",
        "model": str(DRAFT_MODEL),
        "revision": DRAFT_REVISION,
        "num_speculative_tokens": 7,
        "draft_sample_method": "greedy",
        "rejection_sample_method": "standard",
    }
    engine_config = {
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
        "enforce_eager": False,
    }
    llm = LLM(
        **engine_config,
        compilation_config=compilation_config,
        speculative_config=speculative_config,
    )
    worker_identities = sorted(
        llm.collective_rpc("get_laguna_tp4_runtime_identity"),
        key=lambda value: value["global_rank"],
    )
    request_phase_arm_ranks = sorted(
        llm.collective_rpc("arm_laguna_dflash_runtime_request_phase")
    )
    params = SamplingParams(
        temperature=0.0,
        top_p=1.0,
        max_tokens=MAX_TOKENS,
        seed=SEED,
        ignore_eos=True,
    )
    generated = llm.chat(
        [{"role": "user", "content": PROMPT}],
        sampling_params=params,
        use_tqdm=False,
        chat_template_kwargs={"enable_thinking": False},
    )
    if len(generated) != 1 or len(generated[0].outputs) != 1:
        die("single chat call returned an unexpected output shape")
    request = generated[0]
    output = request.outputs[0]
    token_ids = list(output.token_ids)
    prompt_token_ids = list(request.prompt_token_ids or [])
    cached_tokens = getattr(request, "num_cached_tokens", None)
    if cached_tokens != 0:
        die(f"num_cached_tokens must be zero, got {cached_tokens!r}")
    if len(token_ids) != MAX_TOKENS or output.finish_reason != "length":
        die("generation did not produce the frozen 32-token length result")

    aggregate = aggregate_recorder_root(EVIDENCE_ARM, args.evidence_dir)
    write_exclusive(args.evidence_dir / "evidence.json", aggregate)
    evidence_file = args.evidence_dir / "evidence.json"
    lifecycle_manifest = file_manifest(trace_dir)
    if not lifecycle_manifest:
        die("DFlash lifecycle trace is empty")
    record = {
        "schema": SCHEMA,
        "treatment": args.treatment,
        "selector": int(
            os.environ["VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE"]
        ),
        "offline_only": True,
        "nonbenchmark": True,
        "single_chat_call": True,
        "worker_identity_calls": 1,
        "request_phase_arm_calls": 1,
        "request_phase_arm_ranks": request_phase_arm_ranks,
        "warmup_calls": 0,
        "retry_count": 0,
        "prompt_id": PROMPT_ID,
        "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
        "prompt_token_ids": prompt_token_ids,
        "prompt_token_ids_sha256": digest_json(prompt_token_ids),
        "max_tokens": MAX_TOKENS,
        "seed": SEED,
        "ignore_eos": True,
        "chat_template_kwargs": {"enable_thinking": False},
        "model": str(TARGET_MODEL),
        "draft_model": str(DRAFT_MODEL),
        "target_revision": TARGET_REVISION,
        "draft_revision": DRAFT_REVISION,
        "model_manifest_sha256": MODEL_MANIFEST_SHA256,
        "engine_config": engine_config,
        "compilation_config": compilation_config,
        "speculative_config": speculative_config,
        "environment": {name: os.environ[name] for name in RECORDED_ENVIRONMENT},
        "runtime": identity,
        "worker_identities": worker_identities,
        "num_cached_tokens": cached_tokens,
        "finish_reason": output.finish_reason,
        "token_ids": token_ids,
        "token_ids_sha256": digest_json(token_ids),
        "text": output.text,
        "text_sha256": hashlib.sha256(output.text.encode()).hexdigest(),
        "usage": {
            "prompt_tokens": len(prompt_token_ids),
            "completion_tokens": len(token_ids),
            "cached_tokens": cached_tokens,
        },
        "evidence_dir": str(args.evidence_dir),
        "evidence_canonical_sha256": digest_json(aggregate),
        "evidence_file_sha256": sha256_file(evidence_file),
        "lifecycle_trace_dir": str(trace_dir),
        "lifecycle_trace_manifest": lifecycle_manifest,
        "lifecycle_trace_manifest_sha256": digest_json(lifecycle_manifest),
        "rpc_dir": str(rpc_dir),
    }
    write_exclusive(args.out, record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
