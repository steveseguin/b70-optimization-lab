#!/usr/bin/env python3
"""Fail-closed post-run gates for sealed Qwen3.8 TP2 validation arms."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any


PAD_MARKER = "VLLM_XPU_ONEDNN_INT4_DETERMINISM_PAD reached"
OUTER_DIRECT_RE = re.compile(
    r"Directly load the compiled graph\(s\) for compile range "
    r"\((\d+),\s*(\d+)\) from the cache, took [0-9]+(?:\.[0-9]+)? s"
)
CACHE_DIR_RE = re.compile(
    r"Using cache directory: (?P<path>.+?) for vLLM's torch\.compile\s*$"
)
AOT_DIRECT_RE = re.compile(
    r"Directly load AOT compilation from path (?P<path>.+?)\s*$"
)
RANK_RES = (
    re.compile(r"\[rank(?P<rank>\d+)\]"),
    re.compile(r"\(Worker_TP(?P<rank>\d+)\b"),
)
ACTOR_RE = re.compile(r"\((?P<actor>Worker_TP\d+|EngineCore) pid=\d+\)")
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
NEGATIVE_MARKERS = (
    "Cache the graph of compile range",
    "Compiling a graph for compile range",
    "saved AOT compiled function to",
    "unable to save AOT compiled function to",
)
NEGATIVE_GRAPH_STORE_RE = re.compile(
    r"Store the .* graph for compile range", re.IGNORECASE
)
RUNTIME_MARKERS = {
    "engine_tp2": "tensor_parallel_size=2",
    "engine_mtp5": "num_spec_tokens=5",
    "engine_fp16": "dtype=torch.float16",
    "engine_int4": "quantization=inc",
    "engine_seed0": "seed=0",
    "engine_no_prefix_cache": "enable_prefix_caching=False",
    "async_scheduling": "Asynchronous scheduling is enabled.",
    "target_int8_head": (
        "Prepared experimental XPU INT8 lm_head: "
        "prefix=language_model.lm_head scope=all"
    ),
    "draft_int4_head": "Prepared experimental XPU INT4 draft lm_head:",
}


class InputError(ValueError):
    """The gate input is missing or structurally invalid."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise InputError(f"missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"malformed JSON file {path}: {exc}") from exc


def load_identity(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError as exc:
        raise InputError(f"missing identity file: {path}") from exc
    identity: dict[str, str] = {}
    for lineno, line in enumerate(lines, 1):
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise InputError(f"malformed identity line {path}:{lineno}")
        key, value = line.split("=", 1)
        if not key or key in identity:
            raise InputError(f"duplicate/empty identity key {path}:{lineno}")
        identity[key] = value
    return identity


def clean_line(line: str) -> str:
    return ANSI_RE.sub("", line).rstrip()


def actor_from_line(line: str) -> str:
    match = ACTOR_RE.search(line)
    if match:
        return match.group("actor")
    ranks = ranks_from_line(line)
    if len(ranks) == 1:
        return f"rank{next(iter(ranks))}"
    return "unranked"


def ranks_from_line(line: str) -> set[int]:
    ranks: set[int] = set()
    for pattern in RANK_RES:
        ranks.update(int(match.group("rank")) for match in pattern.finditer(line))
    return ranks


def normalized_path(value: str) -> str:
    return str(Path(value).expanduser().resolve(strict=False))


def require_identity_int(identity: dict[str, str], key: str) -> int:
    value = identity.get(key)
    if value is None:
        raise InputError(f"identity is missing {key}")
    try:
        return int(value)
    except ValueError as exc:
        raise InputError(f"identity {key} is not an integer: {value!r}") from exc


def require_sha256(value: str, label: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise InputError(f"{label} is not a lowercase SHA-256: {value!r}")
    return value


def canonical_csv(values: list[str], label: str) -> str:
    if not values or any(not value or "," in value for value in values):
        raise InputError(f"{label} must contain nonempty comma-free values")
    if len(values) != len(set(values)):
        raise InputError(f"{label} contains duplicates")
    return ",".join(values)


def validate_expectations(args: argparse.Namespace, tp: int) -> None:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.expected_namespace):
        raise InputError("expected namespace must be one safe path component")
    roles = canonical_csv(args.expected_outer_role, "expected outer roles")
    if roles != "backbone,eagle_head":
        raise InputError("sealed Qwen3.8 TP2 requires backbone,eagle_head roles")
    keys = canonical_csv(args.expected_aot_key, "expected AOT keys")
    for key in args.expected_aot_key:
        require_sha256(key, "expected AOT key")
    if args.expected_outer_loads != len(args.expected_outer_role):
        raise InputError("outer-load count must equal the number of outer roles")
    if args.expected_aot_loads != tp * len(args.expected_aot_key):
        raise InputError("AOT-load count must equal TP times the number of AOT keys")
    if args.expected_pad_markers != tp:
        raise InputError("pad-marker count must equal tensor parallel size")
    require_sha256(args.expected_suite_sha256, "expected suite SHA-256")
    require_sha256(
        args.expected_quality_baseline_sha256,
        "expected quality-baseline SHA-256",
    )
    require_sha256(args.expected_model_manifest_sha256, "expected model-manifest SHA-256")
    require_sha256(args.expected_verify_script_sha256, "expected verifier SHA-256")
    require_sha256(args.expected_cache_manifest_sha256, "expected cache-manifest SHA-256")
    require_sha256(args.expected_graph_manifest_sha256, "expected graph-manifest SHA-256")
    for label, value in (
        ("expected native extension SHA-256", args.expected_native_sha256),
        ("expected core extension SHA-256", args.expected_core_sha256),
        ("expected MoE extension SHA-256", args.expected_moe_sha256),
        ("expected FA extension SHA-256", args.expected_fa_sha256),
    ):
        require_sha256(value, label)


def validate_bench_against_suite(bench_path: Path, suite_path: Path) -> dict[str, Any]:
    bench = load_bench_rows(bench_path)
    suite = load_json(suite_path)
    prompts = suite.get("prompts") if isinstance(suite, dict) else None
    suite_id = suite.get("suite_id") if isinstance(suite, dict) else None
    if not isinstance(prompts, list) or len(prompts) != 25:
        raise InputError("sealed validation suite must contain exactly 25 prompts")
    if not isinstance(suite_id, str) or not suite_id:
        raise InputError("sealed validation suite is missing suite_id")
    if bench["suite_id"] != suite_id or len(bench["rows"]) != len(prompts):
        raise InputError("benchmark suite identity/count does not match validation suite")
    for position, (prompt, row) in enumerate(zip(prompts, bench["rows"])):
        if not isinstance(prompt, dict):
            raise InputError(f"suite prompt {position} is not an object")
        prompt_id = prompt.get("id")
        prompt_text = prompt.get("prompt")
        if not isinstance(prompt_id, str) or not isinstance(prompt_text, str):
            raise InputError(f"suite prompt {position} has invalid id/text")
        expected_key = (
            position,
            prompt_id,
            hashlib.sha256(prompt_text.encode()).hexdigest(),
        )
        if row["key"] != expected_key:
            raise InputError(f"benchmark row {position} does not match suite prompt identity")
    return bench


def parse_server_log(
    path: Path,
    *,
    cache_dir: Path,
    tensor_parallel_size: int,
    expected_outer_roles: list[str],
    expected_aot_keys: list[str],
) -> dict[str, Any]:
    try:
        lines = [clean_line(line) for line in path.read_text(errors="replace").splitlines()]
    except FileNotFoundError as exc:
        raise InputError(f"missing server log: {path}") from exc

    pending_cache_dirs: dict[str, deque[str]] = defaultdict(deque)
    cache_dirs: list[dict[str, str]] = []
    outer_loads: list[dict[str, Any]] = []
    aot_loads: list[dict[str, Any]] = []
    pad_lines: list[dict[str, Any]] = []
    negative_lines: list[dict[str, Any]] = []
    runtime_markers: dict[str, list[dict[str, Any]]] = {
        key: [] for key in RUNTIME_MARKERS
    }

    for lineno, line in enumerate(lines, 1):
        actor = actor_from_line(line)
        cache_match = CACHE_DIR_RE.search(line)
        if cache_match:
            cache_path = normalized_path(cache_match.group("path"))
            pending_cache_dirs[actor].append(cache_path)
            cache_dirs.append({"line": lineno, "actor": actor, "path": cache_path})

        outer_match = OUTER_DIRECT_RE.search(line)
        if outer_match:
            paired_path = (
                pending_cache_dirs[actor].popleft()
                if pending_cache_dirs[actor]
                else None
            )
            outer_loads.append(
                {
                    "line": lineno,
                    "actor": actor,
                    "range": [int(outer_match.group(1)), int(outer_match.group(2))],
                    "cache_dir": paired_path,
                }
            )

        aot_match = AOT_DIRECT_RE.search(line)
        if aot_match:
            aot_path = normalized_path(aot_match.group("path"))
            path_rank_match = re.search(r"/rank_(\d+)_0/model$", aot_path)
            line_ranks = ranks_from_line(line)
            aot_loads.append(
                {
                    "line": lineno,
                    "actor": actor,
                    "path": aot_path,
                    "line_ranks": sorted(line_ranks),
                    "path_rank": int(path_rank_match.group(1)) if path_rank_match else None,
                }
            )

        if PAD_MARKER in line:
            pad_lines.append(
                {"line": lineno, "actor": actor, "ranks": sorted(ranks_from_line(line))}
            )

        if any(marker in line for marker in NEGATIVE_MARKERS) or NEGATIVE_GRAPH_STORE_RE.search(line):
            negative_lines.append({"line": lineno, "text": line})
        for key, marker in RUNTIME_MARKERS.items():
            if marker in line:
                runtime_markers[key].append(
                    {
                        "line": lineno,
                        "actor": actor,
                        "ranks": sorted(ranks_from_line(line)),
                    }
                )

    cache_dir_resolved = Path(normalized_path(str(cache_dir)))
    expected_cache_dirs = [
        normalized_path(str(cache_dir_resolved / "rank_0_0" / role))
        for role in expected_outer_roles
    ]
    aot_root = cache_dir_resolved.parent / "torch_aot_compile"
    expected_aot_paths = [
        normalized_path(str(aot_root / key / f"rank_{rank}_0" / "model"))
        for key in expected_aot_keys
        for rank in range(tensor_parallel_size)
    ]
    return {
        "cache_dirs": cache_dirs,
        "actual_cache_dir_paths": [item["path"] for item in cache_dirs],
        "expected_cache_dir_paths": expected_cache_dirs,
        "outer_loads": outer_loads,
        "aot_loads": aot_loads,
        "actual_aot_paths": [item["path"] for item in aot_loads],
        "expected_aot_paths": expected_aot_paths,
        "pad_lines": pad_lines,
        "negative_lines": negative_lines,
        "runtime_markers": runtime_markers,
    }


def compare_manifests(input_path: Path, output_path: Path) -> dict[str, Any]:
    input_bytes = input_path.read_bytes() if input_path.exists() else None
    output_bytes = output_path.read_bytes() if output_path.exists() else None
    if input_bytes is None:
        raise InputError(f"missing input cache manifest: {input_path}")
    if output_bytes is None:
        raise InputError(f"missing output cache manifest: {output_path}")
    input_json = load_json(input_path)
    output_json = load_json(output_path)
    fields = ("tree_sha256", "entry_count", "file_count", "total_file_bytes")
    return {
        "input_sha256": hashlib.sha256(input_bytes).hexdigest(),
        "output_sha256": hashlib.sha256(output_bytes).hexdigest(),
        "byte_identical": input_bytes == output_bytes,
        "identity_fields_equal": all(input_json.get(k) == output_json.get(k) for k in fields),
        "input_identity": {key: input_json.get(key) for key in fields},
        "output_identity": {key: output_json.get(key) for key in fields},
    }


def check_arm(args: argparse.Namespace) -> tuple[dict[str, Any], bool]:
    arm_root = Path(args.arm_root).resolve()
    identity = load_identity(arm_root / "run" / "identity.env")
    tp = require_identity_int(identity, "tensor_parallel_size")
    if tp <= 0:
        raise InputError("tensor_parallel_size must be positive")
    validate_expectations(args, tp)
    try:
        compilation_config = json.loads(identity.get("compilation_config", ""))
    except json.JSONDecodeError as exc:
        raise InputError(f"identity compilation_config is malformed: {exc}") from exc
    if not isinstance(compilation_config, dict) or not compilation_config.get("cache_dir"):
        raise InputError("identity compilation_config must contain explicit cache_dir")

    cache_root = Path(identity.get("vllm_cache_root", "")).resolve()
    expected_cache_root = Path(args.expected_cache_root).resolve()
    expected_cache_dir = cache_root / "torch_compile_cache" / args.expected_namespace
    actual_cache_dir = Path(compilation_config["cache_dir"]).resolve()
    log = parse_server_log(
        arm_root / "run" / "server.stdout.log",
        cache_dir=expected_cache_dir,
        tensor_parallel_size=tp,
        expected_outer_roles=args.expected_outer_role,
        expected_aot_keys=args.expected_aot_key,
    )
    manifests = compare_manifests(
        arm_root / "compile-cache-input-manifest.json",
        arm_root / "compile-cache-output-manifest.json",
    )
    supervision_path = arm_root / "run" / "supervision.log"
    try:
        supervision_lines = [
            line.rstrip()
            for line in supervision_path.read_text(errors="replace").splitlines()
            if line.strip()
        ]
    except FileNotFoundError as exc:
        raise InputError(f"missing supervision log: {supervision_path}") from exc

    errors: list[str] = []
    expected_identity = {
        "validation_mode": "spec-native-partition-exact-native",
        "gpu_index": "2,3",
        "tensor_parallel_size": "2",
        "model_dir": normalized_path(args.expected_model_dir),
        "model_manifest_sha256": args.expected_model_manifest_sha256,
        "verify_model_script_sha256": args.expected_verify_script_sha256,
        "model_verification_policy": "direct-and-ordinary-fail-closed",
        "model_verify_status": "verified",
        "enable_mtp": "1",
        "num_speculative_tokens": "5",
        "enable_xpu_graph": "1",
        "xpu_graph": "1",
        "vllm_xpu_enable_xpu_graph": "1",
        "vllm_xpu_force_graph_with_comm": "1",
        "vllm_xpu_graph_noop_comm_capture": "1",
        "max_model_len": "2048",
        "max_num_batched_tokens": "1024",
        "max_num_seqs": "1",
        "gpu_memory_utilization": "0.95",
        "pythonhashseed": "0",
        "draft_lm_head_int4": "1",
        "draft_lm_head_int4_group_size": "128",
        "draft_lm_head_int4_scale_dtype": "bf16",
        "draft_lm_head_int4_fallback_margin": "0",
        "gdn_native_spec_decode": "1",
        "gdn_native_spec_recurrent_serial_exact": "",
        "gdn_native_fallback": "0",
        "gdn_replayssm_spec": "0",
        "gdn_spec_persistent_scratch": "1",
        "gdn_capture_native_spec": "1",
        "ddtree_capture_gdn_core": "0",
        "ddtree_full_graph": "0",
        "onednn_int4_completion_barrier": "1",
        "onednn_int4_input_dependency": "1",
        "onednn_int4_input_dependency_scope": "all_target",
        "onednn_int4_determinism_pad": "1",
        "onednn_int8_completion_barrier": "1",
        "onednn_int8_input_dependency": "1",
        "fa2_force_chunk_decode": "1",
        "lm_head_int8": "1",
        "lm_head_int8_scope": "all",
        "lm_head_int8_scale_dtype": "bf16",
        "deterministic_greedy_margin": "0",
        "run_smoke": "1",
        "run_bench": "1",
        "bench_max_tokens": "512",
        "bench_metric_tokens": "100",
        "vllm_extra_args": "--dtype float16",
        "xpu_compile_allgather_custom_op": "1",
        "ccl_atl_transport": "ofi",
        "ccl_topo_p2p_access": "1",
        "ccl_ze_ipc_exchange": "pidfd",
        "oneccl_candidate_path": (
            "/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public/lib/libccl.so.1.0"
        ),
        "oneccl_candidate_sha256": (
            "43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700"
        ),
        "oneccl_kernels_sha256": (
            "0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9"
        ),
        "oneccl_source_top_commit": "b52f40c07f0b140e6aba87548c80720a350a9827",
        "oneccl_libccl_commit": "4ceafd15c03ce46f11eeaf91781a92afebd3cecf",
        "expected_onednn_int4_determinism_pad_markers": str(
            args.expected_pad_markers
        ),
        "expected_compile_cache_direct_loads": str(args.expected_outer_loads),
        "expected_aot_direct_loads": str(args.expected_aot_loads),
        "expected_compile_cache_namespace": args.expected_namespace,
        "expected_compile_cache_outer_roles": canonical_csv(
            args.expected_outer_role, "expected outer roles"
        ),
        "expected_aot_cache_keys": canonical_csv(
            args.expected_aot_key, "expected AOT keys"
        ),
        "expected_suite_sha256": args.expected_suite_sha256,
        "expected_quality_baseline_sha256": args.expected_quality_baseline_sha256,
    }
    for key, expected in expected_identity.items():
        actual = identity.get(key)
        if key == "model_dir" and actual:
            actual = normalized_path(actual)
        if actual != expected:
            errors.append(f"identity {key}={actual!r}, expected {expected!r}")
    oneccl_path = Path(identity.get("oneccl_candidate_path", ""))
    oneccl_kernel_path = oneccl_path.parent / "ccl" / "kernels" / "kernels.spv"
    if (
        not oneccl_path.is_file()
        or sha256_file(oneccl_path) != expected_identity["oneccl_candidate_sha256"]
        or not oneccl_kernel_path.is_file()
        or sha256_file(oneccl_kernel_path) != expected_identity["oneccl_kernels_sha256"]
    ):
        errors.append("oneCCL runtime bytes do not match the sealed identity")
    if identity.get("run_quality") != ("1" if args.require_quality_pass else "0"):
        errors.append("identity run_quality does not match the arm gate mode")
    for path_key, hash_key, expected_hash in (
        ("model_manifest", "model_manifest_sha256", args.expected_model_manifest_sha256),
        ("verify_model_script", "verify_model_script_sha256", args.expected_verify_script_sha256),
    ):
        path = Path(identity.get(path_key, ""))
        actual_hash = sha256_file(path) if path.is_file() else None
        if actual_hash != expected_hash or identity.get(hash_key) != actual_hash:
            errors.append(f"{path_key} bytes do not match the sealed identity")
    model_verify_path = Path(identity.get("model_verify_json", ""))
    model_verify_sha = (
        sha256_file(model_verify_path) if model_verify_path.is_file() else None
    )
    if model_verify_sha != identity.get("model_verify_json_sha256"):
        errors.append("model verification JSON is missing or changed")
    else:
        model_verify = load_json(model_verify_path)
        verified_files = (
            model_verify.get("files") if isinstance(model_verify, dict) else None
        )
        coherent = (
            isinstance(model_verify, dict)
            and model_verify.get("status") == "verified"
            and isinstance(verified_files, list)
            and len(verified_files) == 19
            and all(
                isinstance(item, dict)
                and item.get("ok") is True
                and item.get("direct_ok") is True
                and item.get("ordinary_ok") is True
                and item.get("paths_coherent") is True
                for item in verified_files
            )
        )
        if not coherent:
            errors.append("model verification JSON does not prove 19 coherent dual-view files")
    if identity.get("tp2_sealed_gates_required") != "1":
        errors.append("identity does not record tp2_sealed_gates_required=1")
    if identity.get("compile_cache_unchanged_required") != "1":
        errors.append("identity does not require unchanged compile cache")
    if identity.get("no_compile_cache_writes_required") != "1":
        errors.append("identity does not forbid compile-cache writes")
    for key in (
        "run_arm_script_sha256",
        "sealed_gate_checker_sha256",
        "campaign_driver_sha256",
        "validation_input_env_sha256",
    ):
        if not re.fullmatch(r"[0-9a-f]{64}", identity.get(key, "")):
            errors.append(f"identity is missing a valid {key}")
    snapshot_checks = {
        "run_arm_script_sha256": arm_root / "run" / "run-arm.sh.snapshot",
        "sealed_gate_checker_sha256": arm_root
        / "run"
        / "check-tp2-sealed-gates.py.snapshot",
        "campaign_driver_sha256": arm_root
        / "run"
        / "campaign-driver.sh.snapshot",
        "validation_input_env_sha256": arm_root / "run" / "validation-input.env",
        "common_runner_sha256": arm_root / "run" / "run-vllm-candidate.sh.snapshot",
        "serve_vllm_sha256": arm_root / "run" / "serve-vllm.sh.snapshot",
    }
    candidate_entrypoint = Path(identity.get("candidate_entrypoint", "missing"))
    if candidate_entrypoint.name != "run-tp2-fullgraph-transaction-candidate.sh":
        errors.append("candidate_entrypoint is not the top-level fullgraph transaction wrapper")
    snapshot_checks["candidate_entrypoint_sha256"] = (
        arm_root / "run" / (candidate_entrypoint.name + ".snapshot")
    )
    for identity_key, snapshot_path in snapshot_checks.items():
        actual_snapshot_sha = (
            sha256_file(snapshot_path) if snapshot_path.is_file() else None
        )
        if actual_snapshot_sha != identity.get(identity_key):
            errors.append(
                f"{identity_key} does not match immutable snapshot {snapshot_path}"
            )
    for prefix in ("parity_peer_bench", "target_token_bench"):
        source_value = identity.get(prefix, "")
        snapshot_value = identity.get(f"{prefix}_snapshot", "")
        if not source_value and not snapshot_value:
            continue
        source_path = Path(source_value)
        snapshot_path = Path(snapshot_value)
        source_sha = sha256_file(source_path) if source_path.is_file() else None
        snapshot_sha = sha256_file(snapshot_path) if snapshot_path.is_file() else None
        if source_sha != identity.get(f"{prefix}_sha256"):
            errors.append(f"live {prefix} changed or is missing after launch")
        if snapshot_sha != identity.get(f"{prefix}_snapshot_sha256"):
            errors.append(f"{prefix} snapshot does not match recorded identity")
        if source_sha != snapshot_sha:
            errors.append(f"{prefix} source and immutable snapshot differ")
        expected_sha = identity.get(f"expected_{prefix}_sha256", "")
        if expected_sha != source_sha:
            errors.append(f"{prefix} does not match its preregistered SHA")
    repo_head_path = arm_root / "run" / "llm-optimizations.git-head"
    repo_head = repo_head_path.read_text().strip() if repo_head_path.is_file() else None
    if repo_head != args.expected_repo_head:
        errors.append(
            f"repository HEAD mismatch: actual={repo_head} expected={args.expected_repo_head}"
        )
    repo_patch_path = arm_root / "run" / "llm-optimizations.working.patch"
    if (
        not repo_patch_path.is_file()
        or sha256_file(repo_patch_path) != hashlib.sha256(b"").hexdigest()
    ):
        errors.append("llm-optimizations tracked working patch is not empty")
    source_heads = {
        "vllm": "44fc8fde09fc311d3099dab10366b672d9142ea4",
        "vllm-xpu-kernels": "2dd55f380df753a10a88fcd9e96192561066e713",
    }
    for name, expected_head in source_heads.items():
        head_path = arm_root / "run" / f"{name}.git-head"
        patch_path = arm_root / "run" / f"{name}.working.patch"
        actual_head = head_path.read_text().strip() if head_path.is_file() else None
        patch_sha = sha256_file(patch_path) if patch_path.is_file() else None
        if actual_head != expected_head:
            errors.append(f"{name} source HEAD is not the sealed identity")
        if patch_sha != hashlib.sha256(b"").hexdigest():
            errors.append(f"{name} tracked working patch is not empty")
    if identity.get("require_xpu_modules_under_stage") != "1":
        errors.append("identity does not require strict staged XPU module resolution")
    stage_value = identity.get("xpu_kernels_src", "")
    if not stage_value:
        errors.append("identity is missing xpu_kernels_src")
        stage_path = None
    else:
        stage_path = Path(stage_value).resolve()
    staged_identity_paths: dict[str, str | None] = {}
    staged_files = {
        "xpu_native_extension_path": (
            "xpu_native_extension_sha256",
            args.expected_native_sha256,
        ),
        "xpu_core_extension_path": (
            "xpu_core_extension_sha256",
            args.expected_core_sha256,
        ),
        "xpu_moe_extension_path": (
            "xpu_moe_extension_sha256",
            args.expected_moe_sha256,
        ),
        "xpu_fa_extension_path": (
            "xpu_fa_extension_sha256",
            args.expected_fa_sha256,
        ),
    }
    for key in ("xpu_python_package_path", *staged_files):
        value = identity.get(key)
        staged_identity_paths[key] = value
        if not value:
            errors.append(f"identity is missing {key}")
            continue
        resolved = Path(value).resolve()
        if stage_path is None or not resolved.is_relative_to(stage_path):
            errors.append(f"identity {key} escapes staged XPU package: {resolved}")
        if key in staged_files:
            hash_key, expected_hash = staged_files[key]
            actual_hash = sha256_file(resolved) if resolved.is_file() else None
            recorded_hash = identity.get(hash_key)
            if actual_hash != expected_hash:
                errors.append(
                    f"staged file {key} SHA mismatch: actual={actual_hash} "
                    f"expected={expected_hash}"
                )
            if recorded_hash != actual_hash:
                errors.append(f"identity {hash_key} does not match staged file bytes")
    if actual_cache_dir != expected_cache_dir:
        errors.append(
            f"explicit cache_dir mismatch: actual={actual_cache_dir} expected={expected_cache_dir}"
        )
    if cache_root != expected_cache_root:
        errors.append(
            f"cache root mismatch: actual={cache_root} expected={expected_cache_root}"
        )
    expected_config = {
        "cache_dir": str(expected_cache_dir),
        "use_inductor_graph_partition": True,
        "pass_config": {"fuse_rope_kvcache_cat_mla": False},
        "cudagraph_mode": "PIECEWISE",
        "cudagraph_capture_sizes": [6],
        "max_cudagraph_capture_size": 6,
    }
    if compilation_config != expected_config:
        errors.append("compilation_config is not the exact sealed MTP5/capture-6 config")
    if Counter(log["actual_cache_dir_paths"]) != Counter(log["expected_cache_dir_paths"]):
        errors.append("Using-cache-directory paths do not match the expected outer roles")
    if len(log["outer_loads"]) != args.expected_outer_loads:
        errors.append(
            f"outer direct-load count {len(log['outer_loads'])} != {args.expected_outer_loads}"
        )
    for item in log["outer_loads"]:
        if item["range"] != [1, 1024]:
            errors.append(f"unexpected outer compile range at log line {item['line']}")
        if item["cache_dir"] is None:
            errors.append(f"outer direct load has no same-actor cache directory at line {item['line']}")
    if Counter(item["cache_dir"] for item in log["outer_loads"]) != Counter(
        log["expected_cache_dir_paths"]
    ):
        errors.append("outer direct loads are not paired to the expected cache roles")
    if len(log["aot_loads"]) != args.expected_aot_loads:
        errors.append(
            f"AOT direct-load count {len(log['aot_loads'])} != {args.expected_aot_loads}"
        )
    if Counter(log["actual_aot_paths"]) != Counter(log["expected_aot_paths"]):
        errors.append("AOT direct-load paths do not match the expected key/rank Cartesian set")
    for item in log["aot_loads"]:
        if tp > 1 and len(item["line_ranks"]) != 1:
            errors.append(f"AOT direct load lacks one actor rank at log line {item['line']}")
        elif item["line_ranks"] and item["path_rank"] not in item["line_ranks"]:
            errors.append(f"AOT actor/path rank mismatch at log line {item['line']}")
    if log["negative_lines"]:
        errors.append("graph/AOT compile or save marker was present")
    for key in (
        "engine_tp2",
        "engine_mtp5",
        "engine_fp16",
        "engine_int4",
        "engine_seed0",
        "engine_no_prefix_cache",
        "async_scheduling",
    ):
        if not log["runtime_markers"][key]:
            errors.append(f"required runtime marker is absent: {key}")
    for key in ("target_int8_head", "draft_int4_head"):
        ranks = [
            item["ranks"][0]
            for item in log["runtime_markers"][key]
            if len(item["ranks"]) == 1
        ]
        if Counter(ranks) != Counter(range(tp)):
            errors.append(f"{key} preparation does not cover each TP rank exactly once")

    if identity.get("onednn_int4_determinism_pad") != "1":
        errors.append("identity does not record onednn_int4_determinism_pad=1")
    if len(log["pad_lines"]) != args.expected_pad_markers:
        errors.append(
            f"pad-marker count {len(log['pad_lines'])} != {args.expected_pad_markers}"
        )
    pad_rank_sets = [set(item["ranks"]) for item in log["pad_lines"]]
    if any(len(ranks) != 1 for ranks in pad_rank_sets):
        errors.append("each pad marker must carry exactly one rank")
    actual_pad_ranks = [next(iter(ranks)) for ranks in pad_rank_sets if len(ranks) == 1]
    if Counter(actual_pad_ranks) != Counter(range(tp)):
        errors.append(f"pad-marker ranks {actual_pad_ranks} do not cover each TP rank exactly once")

    if not manifests["byte_identical"] or not manifests["identity_fields_equal"]:
        errors.append("compile-cache input/output manifests differ")
    if identity.get("compile_cache_input_manifest_sha256") != manifests["input_sha256"]:
        errors.append("identity compile-cache manifest SHA does not match copied input")
    if manifests["input_sha256"] != args.expected_cache_manifest_sha256:
        errors.append("copied input cache manifest does not match expected campaign SHA")
    if any("stop_group ERROR" in line for line in supervision_lines):
        errors.append("server supervision reported a stop_group error")
    if not supervision_lines or "stop_group complete: group empty" not in supervision_lines[-1]:
        errors.append("server supervision did not finish with an empty process group")

    suite_path = arm_root / "validation-suite.json"
    suite_sha256 = sha256_file(suite_path) if suite_path.is_file() else None
    if suite_sha256 != args.expected_suite_sha256:
        errors.append(
            f"validation suite SHA mismatch: actual={suite_sha256} expected={args.expected_suite_sha256}"
        )
    if identity.get("validation_suite_sha256") != suite_sha256:
        errors.append("identity validation-suite SHA does not match the arm artifact")
    try:
        bench = validate_bench_against_suite(arm_root / "data" / "bench.json", suite_path)
    except InputError as exc:
        bench = None
        errors.append(str(exc))

    graph_manifest_path = Path(identity.get("graph_stage_manifest", ""))
    graph_manifest_sha256 = (
        sha256_file(graph_manifest_path) if graph_manifest_path.is_file() else None
    )
    if not graph_manifest_sha256:
        errors.append("identity graph-stage manifest is missing or unreadable")
    if identity.get("graph_stage_manifest_sha256") != graph_manifest_sha256:
        errors.append("identity graph-stage manifest SHA does not match its file")
    if graph_manifest_sha256 != args.expected_graph_manifest_sha256:
        errors.append("graph-stage manifest does not match expected campaign SHA")

    quality: dict[str, Any] | None = None
    baseline_path = Path(identity.get("quality_baseline_json", ""))
    quality_baseline_sha256 = (
        sha256_file(baseline_path) if baseline_path.is_file() else None
    )
    if quality_baseline_sha256 != args.expected_quality_baseline_sha256:
        errors.append(
            "quality baseline SHA mismatch: "
            f"actual={quality_baseline_sha256} "
            f"expected={args.expected_quality_baseline_sha256}"
        )
    if identity.get("quality_baseline_json_sha256") != quality_baseline_sha256:
        errors.append("identity quality-baseline SHA does not match its file")
    if args.require_quality_pass:
        summary = load_json(arm_root / "run" / "summary.json")
        quality = {
            "quality_rc": summary.get("status", {}).get("quality_rc"),
            "quality_skipped": summary.get("status", {}).get("quality_skipped"),
            "pass_all": summary.get("quality_summary", {}).get("pass_all"),
            "baseline_match_all": summary.get("quality_summary", {}).get(
                "baseline_match_all"
            ),
        }
        if quality != {
            "quality_rc": 0,
            "quality_skipped": False,
            "pass_all": True,
            "baseline_match_all": True,
        }:
            errors.append(f"quality gate did not pass: {quality}")

    result = {
        "schema": "qwen38-tp2-sealed-arm-gates-v1",
        "status": "passed" if not errors else "failed",
        "arm_root": str(arm_root),
        "identity": {
            "repository_head": repo_head,
            "tensor_parallel_size": tp,
            "vllm_cache_root": str(cache_root),
            "expected_namespace": args.expected_namespace,
            "explicit_cache_dir": str(actual_cache_dir),
            "onednn_int4_determinism_pad": identity.get(
                "onednn_int4_determinism_pad"
            ),
            "stage": str(stage_path) if stage_path else None,
            "staged_paths": staged_identity_paths,
            "xpu_native_extension_sha256": identity.get(
                "xpu_native_extension_sha256"
            ),
            "xpu_fa_extension_sha256": identity.get("xpu_fa_extension_sha256"),
        },
        "pad": {
            "expected_markers": args.expected_pad_markers,
            "actual_markers": len(log["pad_lines"]),
            "actual_ranks": actual_pad_ranks,
            "lines": log["pad_lines"],
        },
        "cache_loads": {
            "expected_outer_roles": args.expected_outer_role,
            "expected_outer_loads": args.expected_outer_loads,
            "actual_outer_loads": len(log["outer_loads"]),
            "outer": log["outer_loads"],
            "expected_aot_keys": args.expected_aot_key,
            "expected_aot_loads": args.expected_aot_loads,
            "actual_aot_loads": len(log["aot_loads"]),
            "aot": log["aot_loads"],
            "negative_lines": log["negative_lines"],
            "runtime_markers": log["runtime_markers"],
        },
        "cache_manifests": manifests,
        "supervision": {
            "path": str(supervision_path),
            "final_line": supervision_lines[-1] if supervision_lines else None,
        },
        "suite": {"path": str(suite_path), "sha256": suite_sha256},
        "benchmark": bench,
        "graph_stage_manifest": {
            "path": str(graph_manifest_path),
            "sha256": graph_manifest_sha256,
        },
        "quality": quality,
        "quality_baseline_sha256": quality_baseline_sha256,
        "errors": errors,
    }
    return result, not errors


def load_bench_rows(path: Path) -> dict[str, Any]:
    data = load_json(path)
    fresh = data.get("fresh_response_validity")
    if not isinstance(fresh, dict) or fresh.get("valid") is not True:
        raise InputError(f"benchmark does not pass fresh-response validity: {path}")
    required_fresh = {
        "cached_tokens_all_zero": True,
        "each_prompt_run_once": True,
        "prompts_are_unique": True,
        "response_reuse": False,
        "history_acceleration": False,
        "ngram_history_acceleration": False,
        "context_checkpoints_or_prefix_reuse": False,
        "return_token_ids_requested": True,
        "primary_metric_tokens": 100,
    }
    for key, expected in required_fresh.items():
        if fresh.get(key) != expected:
            raise InputError(
                f"benchmark fresh-response field {key}={fresh.get(key)!r}, "
                f"expected {expected!r}: {path}"
            )
    realistic_gate = data.get("realistic_final_gate")
    if not isinstance(realistic_gate, dict) or realistic_gate.get("passed") is not True:
        raise InputError(f"benchmark realistic_final_gate did not pass: {path}")
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        raise InputError(f"benchmark rows are empty or invalid: {path}")
    parsed_rows: list[dict[str, Any]] = []
    seen: set[tuple[int, str, str]] = set()
    for position, row in enumerate(rows):
        if not isinstance(row, dict):
            raise InputError(f"benchmark row {position} is not an object: {path}")
        key = (row.get("prompt_index"), row.get("prompt_id"), row.get("prompt_sha256"))
        if (
            not isinstance(key[0], int)
            or key[0] != position
            or not isinstance(key[1], str)
            or not key[1]
            or not isinstance(key[2], str)
            or len(key[2]) != 64
        ):
            raise InputError(f"benchmark row identity is invalid at position {position}: {path}")
        if key in seen:
            raise InputError(f"duplicate benchmark row identity {key}: {path}")
        seen.add(key)
        token_ids = row.get("token_ids")
        if (
            not isinstance(token_ids, list)
            or not token_ids
            or any(not isinstance(token, int) or isinstance(token, bool) for token in token_ids)
        ):
            raise InputError(f"invalid token_ids for row {key}: {path}")
        parsed_rows.append({"key": key, "token_ids": token_ids})
    suite_id = fresh.get("suite_id")
    if not isinstance(suite_id, str) or not suite_id:
        raise InputError(f"benchmark suite_id is missing: {path}")
    if fresh.get("prompt_count") != len(parsed_rows):
        raise InputError(f"benchmark prompt_count does not match rows: {path}")
    cached_tokens = fresh.get("cached_tokens")
    if cached_tokens != [0] * len(parsed_rows):
        raise InputError(f"benchmark cached-token vector is not all-zero/exact: {path}")
    return {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "suite_id": suite_id,
        "rows": parsed_rows,
    }


def first_difference(left: list[int], right: list[int]) -> dict[str, Any] | None:
    for index, (left_token, right_token) in enumerate(zip(left, right)):
        if left_token != right_token:
            return {
                "index": index,
                "left_token": left_token,
                "right_token": right_token,
                "left_length": len(left),
                "right_length": len(right),
            }
    if len(left) != len(right):
        index = min(len(left), len(right))
        return {
            "index": index,
            "left_token": left[index] if index < len(left) else None,
            "right_token": right[index] if index < len(right) else None,
            "left_length": len(left),
            "right_length": len(right),
        }
    return None


def compare_streams(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_keys = [row["key"] for row in left["rows"]]
    right_keys = [row["key"] for row in right["rows"]]
    if left["suite_id"] != right["suite_id"] or left_keys != right_keys:
        raise InputError(
            f"benchmark suite/order mismatch: {left['path']} vs {right['path']}"
        )
    differences: list[dict[str, Any]] = []
    for left_row, right_row in zip(left["rows"], right["rows"]):
        difference = first_difference(left_row["token_ids"], right_row["token_ids"])
        if difference is not None:
            differences.append(
                {
                    "prompt_index": left_row["key"][0],
                    "prompt_id": left_row["key"][1],
                    "prompt_sha256": left_row["key"][2],
                    "first_difference": difference,
                }
            )
    return {
        "left": {k: left[k] for k in ("path", "sha256", "suite_id")},
        "right": {k: right[k] for k in ("path", "sha256", "suite_id")},
        "prompt_count": len(left["rows"]),
        "exact_count": len(left["rows"]) - len(differences),
        "all_exact": not differences,
        "differences": differences,
    }


def check_parity(args: argparse.Namespace) -> tuple[dict[str, Any], bool]:
    candidate = load_bench_rows(Path(args.candidate))
    peer = load_bench_rows(Path(args.peer))
    if peer["sha256"] != args.expected_peer_sha256:
        raise InputError("peer benchmark SHA does not match the prelaunch snapshot")
    candidate_peer = compare_streams(candidate, peer)
    errors: list[str] = []
    if not candidate_peer["all_exact"]:
        errors.append("candidate/peer token arrays are not exact for every prompt")
    candidate_reference = None
    peer_reference = None
    if args.reference:
        reference = load_bench_rows(Path(args.reference))
        if reference["sha256"] != args.expected_reference_sha256:
            raise InputError(
                "reference benchmark SHA does not match the prelaunch snapshot"
            )
        candidate_reference = compare_streams(candidate, reference)
        peer_reference = compare_streams(peer, reference)
        if args.require_reference_exact and (
            not candidate_reference["all_exact"] or not peer_reference["all_exact"]
        ):
            errors.append("candidate and peer do not both exactly match the reference")
    result = {
        "schema": "qwen38-token-array-parity-v1",
        "status": "passed" if not errors else "failed",
        "candidate_peer": candidate_peer,
        "candidate_reference": candidate_reference,
        "peer_reference": peer_reference,
        "reference_exact_required": args.require_reference_exact,
        "errors": errors,
    }
    return result, not errors


def write_result(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    arm = subparsers.add_parser("arm", help="check one completed sealed-cache arm")
    arm.add_argument("--arm-root", required=True)
    arm.add_argument("--expected-namespace", required=True)
    arm.add_argument("--expected-outer-role", action="append", required=True)
    arm.add_argument("--expected-outer-loads", type=int, required=True)
    arm.add_argument("--expected-aot-key", action="append", required=True)
    arm.add_argument("--expected-aot-loads", type=int, required=True)
    arm.add_argument("--expected-pad-markers", type=int, required=True)
    arm.add_argument("--expected-suite-sha256", required=True)
    arm.add_argument("--expected-model-dir", required=True)
    arm.add_argument("--expected-model-manifest-sha256", required=True)
    arm.add_argument("--expected-verify-script-sha256", required=True)
    arm.add_argument("--expected-cache-root", required=True)
    arm.add_argument("--expected-cache-manifest-sha256", required=True)
    arm.add_argument("--expected-graph-manifest-sha256", required=True)
    arm.add_argument("--expected-native-sha256", required=True)
    arm.add_argument("--expected-core-sha256", required=True)
    arm.add_argument("--expected-moe-sha256", required=True)
    arm.add_argument("--expected-fa-sha256", required=True)
    arm.add_argument("--expected-repo-head", required=True)
    arm.add_argument("--require-quality-pass", action="store_true")
    arm.add_argument("--expected-quality-baseline-sha256", required=True)
    arm.add_argument("--output", required=True)

    parity = subparsers.add_parser("parity", help="compare complete benchmark token arrays")
    parity.add_argument("--candidate", required=True)
    parity.add_argument("--peer", required=True)
    parity.add_argument("--expected-peer-sha256", required=True)
    parity.add_argument("--reference")
    parity.add_argument("--expected-reference-sha256")
    parity.add_argument("--require-reference-exact", action="store_true")
    parity.add_argument("--output", required=True)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    output = Path(args.output)
    try:
        if args.command == "arm":
            result, passed = check_arm(args)
        else:
            if args.require_reference_exact and not args.reference:
                raise InputError("--require-reference-exact requires --reference")
            if args.reference and not args.expected_reference_sha256:
                raise InputError("--reference requires --expected-reference-sha256")
            if args.expected_reference_sha256 and not args.reference:
                raise InputError("--expected-reference-sha256 requires --reference")
            require_sha256(args.expected_peer_sha256, "expected peer SHA-256")
            if args.expected_reference_sha256:
                require_sha256(
                    args.expected_reference_sha256,
                    "expected reference SHA-256",
                )
            result, passed = check_parity(args)
    except (InputError, OSError) as exc:
        result = {
            "schema": "qwen38-sealed-gate-input-error-v1",
            "status": "input-error",
            "error": str(exc),
        }
        write_result(output, result)
        print(str(exc), file=sys.stderr)
        return 2
    write_result(output, result)
    if not passed:
        for error in result.get("errors", []):
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
