#!/usr/bin/env python3
"""One private, offline Laguna M8 recorder arm.

This is deliberately a *correctness-component* driver, not a benchmark.  It
makes exactly one offline ``LLM.generate`` call in a fresh process and records
the emitted token IDs.  The runtime recorder is responsible for the target
hidden-state, KV, and collective raw-byte evidence; this driver refuses to
claim parity from token IDs alone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any


SCHEMA = "laguna-m8-raw-evidence-v2"
RECORDER_MARKER = "LAGUNA_M8_RAW_EVIDENCE_V2"
PROMPT = (
    "Offline correctness diagnostic only. Return exactly three short Python "
    "identifiers, one per line, that would be suitable names for an interval "
    "merge helper. Do not explain them."
)
MAX_TOKENS = 32
MODEL_MANIFEST_SHA256 = (
    "45aa105ef4eceaf05cad33012e0752369f77cbbd76f2213ccfe0ce130fa6c0ac"
)
TARGET_MODEL = Path("/mnt/fast-ai/llm-models/laguna-s-2.1/int4")
DRAFT_MODEL = Path("/mnt/fast-ai/llm-models/laguna-s-2.1/dflash-int4")
TARGET_REVISION = "4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb"
DRAFT_REVISION = "5e07c246915c86dc6920fead03d019989224f2ba"
VLLM_COMMIT = "e25867aa698f82cbf2fb835e26807078674acebc"
RPC_ROOT = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/tmp")
RPC_DIRS = {
    "incumbent-eager": RPC_ROOT / "m8p6-a",
    "segmented-eager": RPC_ROOT / "m8p6-b",
    "segmented-graph": RPC_ROOT / "m8p6-c",
}
ZMQ_UUID_FILENAME_BYTES = 36
ZMQ_CONSERVATIVE_PATH_BYTES = 100
EXPECTED_ARMS = {
    "incumbent-eager",
    "segmented-eager",
    "segmented-graph",
}
ABSENT_ENVIRONMENT = (
    "TRITON_INTEL_DISABLE_IGC_OPT",
    "VLLM_LAGUNA_TARGET_TRACE",
    "VLLM_LAGUNA_TARGET_TRACE_DIR",
    "VLLM_LAGUNA_TARGET_TRACE_INPUTS",
    "VLLM_LAGUNA_TARGET_TRACE_LAYER",
    "VLLM_LAGUNA_TARGET_TRACE_POSITION",
    "VLLM_LAGUNA_TARGET_TRACE_RANK",
    "VLLM_XPU_LAGUNA_PARITY_RETURN_STAGE",
)


def die(message: str) -> None:
    raise SystemExit(f"laguna M8 offline arm: {message}")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def canonical_json_snapshot(value: Any) -> str:
    """Detach frozen driver evidence from config dictionaries vLLM may mutate."""
    return json.dumps(
        value,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def assert_nvme(path: Path) -> None:
    resolved = path.resolve(strict=False)
    if "/media/" in str(resolved) or "CorsairExternal" in str(resolved):
        die(f"external/USB path is forbidden: {resolved}")
    if not resolved.is_relative_to(Path("/mnt/fast-ai").resolve(strict=True)):
        die(f"path must stay below /mnt/fast-ai: {resolved}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=sorted(EXPECTED_ARMS), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--rpc-dir", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--draft-model", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--draft-revision", required=True)
    parser.add_argument("--expected-vllm-commit", required=True)
    return parser.parse_args()


def rpc_socket_path_bytes(path: Path) -> int:
    return len(os.fsencode(str(path))) + 1 + ZMQ_UUID_FILENAME_BYTES


def execution_config(arm: str) -> tuple[bool, dict[str, Any] | None]:
    graph = arm == "segmented-graph"
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
    return not graph, compilation_config


def require_rpc_dir(args: argparse.Namespace) -> None:
    expected = RPC_DIRS[args.arm]
    try:
        path_stat = args.rpc_dir.lstat()
        resolved = args.rpc_dir.resolve(strict=True)
        resolved_root = args.rpc_dir.parent.resolve(strict=True)
    except OSError as exc:
        die(f"cannot inspect RPC base: {exc}")
    if (
        args.rpc_dir != expected
        or resolved != args.rpc_dir
        or resolved_root != RPC_ROOT
        or args.rpc_dir.is_symlink()
        or not stat.S_ISDIR(path_stat.st_mode)
        or stat.S_IMODE(path_stat.st_mode) != 0o700
    ):
        die(f"RPC base differs from the frozen private-NVMe layout: {args.rpc_dir}")
    assert_nvme(args.rpc_dir)
    socket_bytes = rpc_socket_path_bytes(args.rpc_dir)
    if socket_bytes > ZMQ_CONSERVATIVE_PATH_BYTES:
        die(
            "RPC base leaves insufficient Unix-socket path headroom: "
            f"{socket_bytes} bytes"
        )
    if os.environ.get("VLLM_RPC_BASE_PATH") != str(args.rpc_dir):
        die("VLLM_RPC_BASE_PATH differs from the explicit arm RPC argument")


def require_environment(args: argparse.Namespace) -> None:
    required = {
        "HOME": "/mnt/fast-ai/",
        "TMPDIR": "/mnt/fast-ai/",
        "HF_HOME": "/mnt/fast-ai/",
        "VLLM_CACHE_ROOT": "/mnt/fast-ai/",
        "TORCHINDUCTOR_CACHE_DIR": "/mnt/fast-ai/",
        "TRITON_CACHE_DIR": "/mnt/fast-ai/",
        "CCL_ATL_TRANSPORT": "ofi",
        "CCL_KVS_IFACE": "eno1",
        "CCL_TOPO_P2P_ACCESS": "1",
        "FI_TCP_IFACE": "eno1",
        "HF_HUB_OFFLINE": "1",
        "ONEAPI_DEVICE_SELECTOR": "level_zero:0,1,2,3",
        "TRANSFORMERS_OFFLINE": "1",
        "TORCH_XCCL_ASYNC_ERROR_HANDLING": "1",
        "VLLM_DISABLE_SHARED_EXPERTS_STREAM": "0",
        "VLLM_KV_CACHE_LAYOUT": "NHD",
        "VLLM_NO_USAGE_STATS": "1",
        "VLLM_RPC_BASE_PATH": "/mnt/fast-ai/",
        "VLLM_SHARED_EXPERTS_STREAM_TOKEN_THRESHOLD": "256",
        "VLLM_TRACE_FUNCTION": "0",
        "VLLM_XPU_EXPERT_MAP_ROUND_ROBIN": "0",
        "VLLM_XPU_LAGUNA_M8_EVIDENCE": "1",
        "VLLM_XPU_LAGUNA_M8_EVIDENCE_ARM": args.arm,
        "VLLM_XPU_LAGUNA_M8_EVIDENCE_ROOT": "/mnt/fast-ai/",
        "LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS": "7",
        "VLLM_XPU_EXACT_SPEC_ATTN": "1",
        "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE": "1",
        "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2": "1",
        "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE": "1",
        "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE": "1",
        "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE": "1",
        "VLLM_XPU_LAGUNA_M8_W1_N_TILE": "64",
        "VLLM_XPU_LAGUNA_PARITY_PROBE": "0",
        "VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM": "0",
        "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK": "0",
        "VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION": "0",
        "VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE": "0",
        "VLLM_XPU_LAGUNA_M8_GATHER_SHARDED": "0",
        "VLLM_XPU_LAGUNA_M8_REMOTE_ZERO": "0",
        "VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM": "0",
        "VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM": "0",
        "VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM": "0",
        "VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM": "0",
        "VLLM_XPU_V4_M1_BIASED_TOPK": "0",
        "VLLM_XPU_V4_M1_ROUTER_NORM": "0",
        "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH": "0",
        "VLLM_USE_AOT_COMPILE": "0",
        "ZE_AFFINITY_MASK": "0,1,2,3",
    }
    for name, expected in required.items():
        actual = os.environ.get(name)
        if expected.endswith("/"):
            if actual is None or not actual.startswith(expected):
                die(f"{name} must be private NVMe state, found {actual!r}")
        elif actual != expected:
            die(f"{name}={actual!r}, expected {expected!r}")
    if os.environ["VLLM_XPU_LAGUNA_M8_EVIDENCE_ROOT"] != str(args.evidence_dir):
        die("evidence environment root differs from the arm argument")

    graph = args.arm == "segmented-graph"
    expected_flags = {
        "VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH": "1" if graph else "0",
        "VLLM_USE_BREAKABLE_CUDAGRAPH": "1" if graph else "0",
        "XPU_GRAPH": "1" if graph else "0",
        "VLLM_XPU_ENABLE_XPU_GRAPH": "1" if graph else "0",
    }
    for name, expected in expected_flags.items():
        if os.environ.get(name) != expected:
            die(f"{name} must be {expected!r} for {args.arm}")
    present_debug = [name for name in ABSENT_ENVIRONMENT if name in os.environ]
    if present_debug:
        die(f"record-sensitive debug variables must be absent: {present_debug}")


def runtime_identity(expected_commit: str) -> dict[str, str]:
    import vllm

    runtime_path = Path(vllm.__file__).resolve()
    root = runtime_path.parents[1]
    head = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    if head != expected_commit:
        die(f"vLLM commit {head!r} does not match frozen {expected_commit!r}")
    return {
        "vllm_module": str(runtime_path),
        "vllm_root": str(root),
        "vllm_commit": head,
    }


def aggregate_rank_local_evidence(args: argparse.Namespace) -> None:
    """Parse actual recorder directories; paths are intentionally not aggregated."""
    from analyze_laguna_m8_actual_offline_gate import aggregate_recorder_root

    try:
        aggregate = aggregate_recorder_root(args.arm, args.evidence_dir)
    except ValueError as exc:
        die(f"low-level recorder validation failed: {exc}")
    output = args.evidence_dir / "evidence.json"
    if output.exists():
        die("recorder pre-created aggregate evidence; refusing an unaudited overwrite")
    output.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n")


def main() -> int:
    args = parse_args()
    for path in (
        args.out,
        args.evidence_dir,
        args.rpc_dir,
        args.model,
        args.draft_model,
    ):
        assert_nvme(path)
    if args.out.exists():
        die(f"refusing to overwrite arm output: {args.out}")
    if (
        args.model.resolve(strict=False) != TARGET_MODEL
        or args.draft_model.resolve(strict=False) != DRAFT_MODEL
        or args.revision != TARGET_REVISION
        or args.draft_revision != DRAFT_REVISION
        or args.expected_vllm_commit != VLLM_COMMIT
        or args.out.parent.resolve(strict=True)
        != args.evidence_dir.parent.resolve(strict=True)
    ):
        die("model/revision/runtime/output identity differs from the frozen gate")
    if not args.model.is_dir() or not args.draft_model.is_dir():
        die("both model paths must already exist as local directories")
    require_rpc_dir(args)
    require_environment(args)

    # The recorder itself creates one private directory per eligible target
    # forward and rank under this pre-created arm-local root.
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    if stat.S_IMODE(args.evidence_dir.stat().st_mode) != 0o700:
        die("evidence root is not owner-private mode 0700")
    identity = runtime_identity(args.expected_vllm_commit)

    from vllm import LLM, SamplingParams

    enforce_eager, compilation_config = execution_config(args.arm)
    speculative_config = {
        "method": "dflash",
        "model": str(args.draft_model),
        "revision": args.draft_revision,
        "num_speculative_tokens": 7,
        "draft_sample_method": "greedy",
        "rejection_sample_method": "standard",
    }
    engine_config = {
        "all2all_backend": "allgather_reducescatter",
        "async_scheduling": False,
        "block_size": 64,
        "data_parallel_size": 1,
        "distributed_executor_backend": "mp",
        "dtype": "bfloat16",
        "enable_expert_parallel": True,
        "enable_prefix_caching": False,
        "enforce_eager": enforce_eager,
        "generation_config": "vllm",
        "gpu_memory_utilization": 0.90,
        "kv_cache_dtype": "bfloat16",
        "max_model_len": 8192,
        "max_num_batched_tokens": 8192,
        "max_num_seqs": 1,
        "model": str(args.model),
        "pipeline_parallel_size": 1,
        "revision": args.revision,
        "tensor_parallel_size": 4,
        "tokenizer": str(args.model),
        "tokenizer_revision": args.revision,
        "trust_remote_code": True,
    }
    frozen_configs_json = canonical_json_snapshot(
        {
            "compilation_config": compilation_config,
            "engine_config": engine_config,
            "speculative_config": speculative_config,
        }
    )
    runtime_configs = json.loads(frozen_configs_json)
    llm_kwargs: dict[str, Any] = {
        **runtime_configs["engine_config"],
        "speculative_config": runtime_configs["speculative_config"],
    }
    if runtime_configs["compilation_config"] is not None:
        llm_kwargs["compilation_config"] = runtime_configs["compilation_config"]
    llm = LLM(**llm_kwargs)
    params = SamplingParams(
        temperature=0.0,
        top_p=1.0,
        max_tokens=MAX_TOKENS,
        seed=1,
        ignore_eos=True,
    )
    # Exactly one user-visible generation per fresh process.  Do not add a
    # warm-up, retry, second prompt, HTTP request, or timing metric here.
    generated = llm.generate([PROMPT], params, use_tqdm=False)
    if len(generated) != 1 or len(generated[0].outputs) != 1:
        die("offline LLM.generate returned an unexpected output shape")
    output = generated[0].outputs[0]
    token_ids = list(output.token_ids)
    cached_tokens = getattr(generated[0], "num_cached_tokens", None)
    if cached_tokens != 0:
        die(f"num_cached_tokens must be exactly 0, got {cached_tokens!r}")
    prompt_token_ids = list(generated[0].prompt_token_ids)
    aggregate_rank_local_evidence(args)
    recorded_configs = json.loads(frozen_configs_json)
    record = {
        "schema": "laguna-m8-offline-arm-v6",
        "arm": args.arm,
        "absent_environment": list(ABSENT_ENVIRONMENT),
        "offline_only": True,
        "single_generate_call": True,
        "nonbenchmark": True,
        "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
        "max_tokens": MAX_TOKENS,
        "seed": 1,
        "ignore_eos": True,
        "model": str(args.model),
        "draft_model": str(args.draft_model),
        "model_manifest_sha256": MODEL_MANIFEST_SHA256,
        "target_revision": args.revision,
        "draft_revision": args.draft_revision,
        "generation_config": "vllm",
        "engine_config": recorded_configs["engine_config"],
        "compilation_config": recorded_configs["compilation_config"],
        "speculative_config": recorded_configs["speculative_config"],
        "environment": {
            name: os.environ[name]
            for name in (
                "CCL_ATL_TRANSPORT",
                "CCL_KVS_IFACE",
                "CCL_TOPO_P2P_ACCESS",
                "FI_TCP_IFACE",
                "HF_HUB_OFFLINE",
                "LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS",
                "ONEAPI_DEVICE_SELECTOR",
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
                "VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM",
                "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK",
                "VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH",
                "VLLM_XPU_LAGUNA_M8_EVIDENCE",
                "VLLM_XPU_LAGUNA_M8_EVIDENCE_ARM",
                "VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION",
                "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2",
                "VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE",
                "VLLM_XPU_LAGUNA_M8_GATHER_SHARDED",
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
        },
        "token_ids": token_ids,
        "num_cached_tokens": cached_tokens,
        "usage": {
            "prompt_tokens": len(prompt_token_ids),
            "completion_tokens": len(token_ids),
            "total_tokens": len(prompt_token_ids) + len(token_ids),
            "cached_tokens": cached_tokens,
        },
        "token_ids_sha256": sha256_json(token_ids),
        "finish_reason": output.finish_reason,
        "text_sha256": hashlib.sha256(output.text.encode("utf-8")).hexdigest(),
        "evidence_dir": str(args.evidence_dir),
        "rpc_dir": str(args.rpc_dir),
        "rpc_uuid_socket_path_bytes": rpc_socket_path_bytes(args.rpc_dir),
        "runtime": identity,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
