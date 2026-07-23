#!/usr/bin/env python3
"""Analyze the preregistered Laguna routed-W1 N64/N128 crossover."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import statistics
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


METRIC = "tok_s_1_100_after_ttft"
PROMPT_COUNT = 13
MIN_ROW_WINS = 9
MIN_CYCLE_SAVING_MS = 0.15
MAX_ACCEPTANCE_RATE_DELTA = 0.001
RECORD_FLOOR_TOK_S = 33.89498511171744
RECORD_ID = "cmrx6p5dv001bo4017hb7sixz"
CANONICAL_MODEL = "laguna-s-2.1-int4"
CANONICAL_SEED = 1
CANONICAL_MAX_TOKENS = 512
CANONICAL_SUITE_ID = "laguna-s-2.1-realistic-cold-v1"
CANONICAL_SUITE_VERSION = 1
CANONICAL_SUITE_REL = "experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json"
CAMPAIGN_ID = "w1-n128-endpoint-abba-8936aac-c59aaad-20260723T093923Z"
CAMPAIGN_ROOT = Path(
    "/media/steve/CorsairExternal/llm-optimization-artifacts/"
    f"laguna-s-2.1/runs/{CAMPAIGN_ID}"
)
CAMPAIGN_JOURNAL = CAMPAIGN_ROOT / ".campaign-journal.txt"
CAMPAIGN_GENESIS_SHA256 = "0" * 64
CAMPAIGN_LEGS = (
    ("A1", "01-A1-control", "control"),
    ("B1", "02-B1-candidate", "candidate"),
    ("B2", "03-B2-candidate", "candidate"),
    ("A2", "04-A2-control", "control"),
)
LEG_EVIDENCE_NAMES = (
    "identity.txt",
    "server.pid",
    "xpu-smi-version.txt",
    "prestart-xpu-ps.txt",
    "prestart-residual.txt",
    "server.log",
    "metrics-before-suite.prom",
    "bench.json",
    "bench.stdout",
    "metrics-after-suite.prom",
    "exactness-vs-q1.json",
    "exactness-vs-q1.stdout",
    "poststop-xpu-ps.txt",
    "poststop-residual.txt",
    "cleanup-status.txt",
)
REPO_ROOT = Path("/home/steve/llm-optimizations")
RUNNER_PATH = REPO_ROOT / (
    "experiments/laguna-s-2.1-xpu-b70/tools/run_w1_n128_crossover_leg.sh"
)
RUNNER_SHA256 = "ccf8da1924dfda527bcec40029cdba0b1718e474cbfde635f774603dde50c752"
ANALYZER_PATH = Path(__file__).resolve()
PREREGISTRATION_PATH = REPO_ROOT / (
    "experiments/laguna-s-2.1-xpu-b70/notes/"
    "2026-07-23-routed-w1-n128-endpoint-preregistration.md"
)
FORMAL_COMPONENT_PATH = Path(
    "/media/steve/CorsairExternal/llm-optimization-artifacts/"
    "laguna-s-2.1/runs/"
    "w1-n128-formal2-aggregate-c59aaad-8f2345e-20260723T053000-0400/"
    "summary.json"
)
COUNTER_COMPONENT_PATH = Path(
    "/media/steve/CorsairExternal/llm-optimization-artifacts/"
    "laguna-s-2.1/runs/"
    "w1-n128-counter-gate-c59aaad-00ceeac-20260723T054500-0400/"
    "summary.json"
)
PREREGISTRATION_SHA256 = (
    "43afaf5ac1005118c3692a35f42ea6b71f47c8dffec1b3e27650dfd4c7047cc6"
)
FORMAL_COMPONENT_SHA256 = (
    "bb48793e711cdb20889e888092344d35f0f3c7cb0e85bc120f63f51cff39b932"
)
COUNTER_COMPONENT_SHA256 = (
    "677b69fe353056a8a7a9afff7e7e952fe337a6d605c326beb80ae5e0103b6e76"
)
XPU_SMI_VERSION_SHA256 = (
    "d14b356677a57006a19e1e5b4aa45cada8fc0c553cd214ac76ad420ef5bdb4ab"
)
VLLM_COMMIT = "8936aac144929190c1e53f8b8624ca397ce16f5b"
KERNEL_COMMIT = "c59aaadbbfd350c2b5f4ad663e247c2811ae3181"
TARGET_REVISION = "4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb"
DRAFT_REVISION = "5e07c246915c86dc6920fead03d019989224f2ba"
TARGET_MODEL_PATH = (
    "/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/int4"
)
DRAFT_MODEL_PATH = (
    "/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/dflash-int4"
)
ONECCL_LIBRARY_PATH = "/home/steve/.venvs/deepseek-v4-xpu/lib/libccl.so"
LIBFABRIC_LIBRARY_PATH = "/home/steve/.venvs/deepseek-v4-xpu/lib/libfabric.so"
TEACHER_PATH = (
    "/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/"
    "runs/bulletproof-q1-canonical-cb616c6-6fc06b0-20260722T142908Z/"
    "bench.json"
)
IDENTITY_FIXED_KEYS = {
    "model": TARGET_MODEL_PATH,
    "model_revision": TARGET_REVISION,
    "draft_model": DRAFT_MODEL_PATH,
    "draft_revision": DRAFT_REVISION,
    "target_manifest_files": "27",
    "draft_manifest_files": "5",
    "target_manifest_bytes": "71922378071",
    "draft_manifest_bytes": "2229973769",
    "target_lfs_sha256_files": "15",
    "draft_lfs_sha256_files": "1",
    "target_lfs_bytes": "71907915776",
    "draft_lfs_bytes": "2229962896",
    "ambient_sensitive_environment": "empty_before_runner",
    "ONEAPI_DEVICE_SELECTOR": "level_zero:0,1,2,3",
    "ZE_AFFINITY_MASK": "0,1,2,3",
    "CCL_ATL_TRANSPORT": "ofi",
    "CCL_TOPO_P2P_ACCESS": "1",
    "VLLM_KV_CACHE_LAYOUT": "NHD",
    "VLLM_XPU_EXACT_SPEC_ATTN": "1",
    "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE": "1",
    "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2": "1",
    "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE": "1",
    "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK": "0",
    "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE": "1",
    "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE": "1",
    "VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM": "0",
    "VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION": "0",
    "VLLM_XPU_LAGUNA_M8_REMOTE_ZERO": "0",
    "VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM": "0",
    "VLLM_XPU_LAGUNA_PARITY_PROBE": "0",
    "VLLM_XPU_LAGUNA_PARITY_RETURN_STAGE": "<unset>",
    "VLLM_LAGUNA_TARGET_TRACE": "<unset>",
    "VLLM_DISABLE_SHARED_EXPERTS_STREAM": "0",
    "VLLM_SHARED_EXPERTS_STREAM_TOKEN_THRESHOLD": "256",
    "VLLM_XPU_EXPERT_MAP_ROUND_ROBIN": "0",
    "VLLM_XPU_V4_M1_BIASED_TOPK": "0",
    "VLLM_XPU_V4_M1_ROUTER_NORM": "0",
    "VLLM_TRACE_FUNCTION": "0",
    "TRITON_INTEL_DISABLE_IGC_OPT": "<unset>",
    "VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH": "0",
    "VLLM_USE_AOT_COMPILE": "0",
    "XPU_GRAPH": "0",
    "VLLM_XPU_ENABLE_XPU_GRAPH": "0",
    "LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS": "7",
    "LAGUNA_GPU_MEMORY_UTILIZATION": "0.90",
    "VLLM_EXTRA_ARGS": "",
    "mode": "dflash eager --no-async-scheduling kv=bfloat16 max_num_seqs=1",
    "prefix_caching": "disabled",
    "generation_warmup": "none",
    "benchmark": ("max_tokens=512 metric_tokens=100 seed=1 return_token_ids=true"),
    "suite": str(REPO_ROOT / CANONICAL_SUITE_REL),
    "teacher": TEACHER_PATH,
    "preregistration": str(PREREGISTRATION_PATH),
    "formal_component_gate": str(FORMAL_COMPONENT_PATH),
    "counter_component_gate": str(COUNTER_COMPONENT_PATH),
    "oneccl_library": ONECCL_LIBRARY_PATH,
    "libfabric_library": LIBFABRIC_LIBRARY_PATH,
    "torch": "2.12.0+xpu",
    "vllm": "0.1.dev1172+g4a6fd8747.xpu",
    "transformers": "5.13.1",
    "vllm-xpu-kernels": "0.1.11.dev53+g744a8b4",
    "triton-xpu": "3.7.1",
}
IDENTITY_FIXED_CHECKSUMS = {
    str(RUNNER_PATH): RUNNER_SHA256,
    str(
        REPO_ROOT / "experiments/laguna-s-2.1-xpu-b70/tools/serve_laguna.sh"
    ): "b27267affd51e242fbf24879e7adff69a1ca3e1829428d43501db67c9b65ccf4",
    str(
        REPO_ROOT / "experiments/laguna-s-2.1-xpu-b70/tools/compare_exact_runs.py"
    ): "87ad4d57907a15afba221be42ea00e3a1975308d421e0edc13881dafe38e3db3",
    str(REPO_ROOT / "scripts/bench-openai-realistic-suite.py"): (
        "40a483d9127a42c6e9f4a3651a429d39d25336d39eee0c782ba2c7712988aa2a"
    ),
    str(PREREGISTRATION_PATH): PREREGISTRATION_SHA256,
    str(FORMAL_COMPONENT_PATH): FORMAL_COMPONENT_SHA256,
    str(COUNTER_COMPONENT_PATH): COUNTER_COMPONENT_SHA256,
    ONECCL_LIBRARY_PATH: (
        "ace144a390a53720b2743844decf127661c942b56f3b414900b9d8c11461acc3"
    ),
    LIBFABRIC_LIBRARY_PATH: (
        "d849d56fd3f8f2581b4b0c17c1564f8145911a313c2c011d694aaf21e5e86b27"
    ),
    str(REPO_ROOT / CANONICAL_SUITE_REL): (
        "9fdaacfdc4de59407a73cbe0d8130fa0f6abe91fed782e399a58adbc035ea638"
    ),
    TEACHER_PATH: ("d41d3d5e2471ee98f783e58407e44217ade67f7472147eeeb82780efa89879d1"),
    f"{TARGET_MODEL_PATH}/config.json": (
        "9f139560db8fd723a75ee4adc24a9fece4101df0e8e7f1cce6549f7eba5b14e6"
    ),
    f"{DRAFT_MODEL_PATH}/config.json": (
        "6f2aac901675ce9c9a12454d0432df7609dac0bc46614ca14725ea5e86f20926"
    ),
    (
        f"{TARGET_MODEL_PATH}/.cache/huggingface/trees/{TARGET_REVISION}.json"
    ): "0128e1ddc4954ade6b4ab7677376e3f3a95aaa02ffede3efdd314f3d4d766643",
    (
        f"{DRAFT_MODEL_PATH}/.cache/huggingface/trees/{DRAFT_REVISION}.json"
    ): "452f28ec2d80bcc33dc89e3581996dd6c1b706243097ea4b342d7f4ee08b08be",
    f"{TARGET_MODEL_PATH}/chat_template.jinja": (
        "444819b8ad4612870827ac05b9147fe9e3344d3850cae8c2790898fc514099ff"
    ),
    f"{TARGET_MODEL_PATH}/generation_config.json": (
        "7d29550cada2f2ef1c0b73be71fa5c4531fd745b9d27c547929ed83b2dd2b272"
    ),
    f"{TARGET_MODEL_PATH}/model.safetensors.index.json": (
        "d6688684f088af44ba3f002d67df6355be1659a457c9a43168cf2f48740d3c88"
    ),
    f"{TARGET_MODEL_PATH}/special_tokens_map.json": (
        "70cd3459fde61761e9440751a590e89a108c09b1803cc7727f5ad1ed1ea6122b"
    ),
    f"{TARGET_MODEL_PATH}/tokenizer.json": (
        "809240f7a182cde859a4fc4ebc902e619a173d507e99304c1092aa04e7a6658e"
    ),
    f"{TARGET_MODEL_PATH}/tokenizer_config.json": (
        "8103b5dd4baf13b38ee927370fbfeab2b1378457efaa233d1c5f0410c40dc9f9"
    ),
    f"{TARGET_MODEL_PATH}/configuration_laguna.py": (
        "9446b4fca6f895bd0ed79d861f33447f8c231ba42b7c89cb4b4d25af3958c1fd"
    ),
    f"{TARGET_MODEL_PATH}/modeling_laguna.py": (
        "765fd328542d176ff6a62ac814327b11a824df29bdca001d341e9a7c2fe9d876"
    ),
    f"{DRAFT_MODEL_PATH}/config.py": (
        "7f908e8aea464132f6cb24e35f0adeee59ceed318f75ec4ee5f08bdff1aec07c"
    ),
    (
        "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/vllm_xpu_kernels/_C.abi3.so"
    ): "126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2",
    (
        "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/"
        "vllm_xpu_kernels/_xpu_C.abi3.so"
    ): "f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8",
    (
        "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/"
        "vllm_xpu_kernels/_moe_C.abi3.so"
    ): "0057b266d567731a9f9f592cefd9103bbf027ebb83c876d26c17ffb09994a3a0",
    (
        "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/"
        "vllm_xpu_kernels/libgrouped_gemm_xe_2.so"
    ): "fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96",
}
PROM_LINE = re.compile(
    r"^(?P<name>[^{\s]+)(?P<labels>\{[^}]*\})?\s+"
    r"(?P<value>[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)$"
)
POSITION_LABEL = re.compile(r'(?:^|,)position="(?P<position>\d+)"(?:,|})')
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
CHECKSUM_LINE = re.compile(r"^(?P<sha>[0-9a-f]{64})  (?P<path>/.*)$")
KEY_LINE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_-]*)=(?P<value>.*)$")
COMMIT_LINE = re.compile(r"^[0-9a-f]{40}$")


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def resolved(value: str | Path) -> str:
    return str(Path(value).resolve())


def parse_utc(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{label}: invalid UTC timestamp {value!r}") from error
    offset = parsed.utcoffset()
    if parsed.tzinfo is None or offset is None:
        raise ValueError(f"{label}: timestamp is not timezone-aware")
    if offset.total_seconds() != 0.0:
        raise ValueError(f"{label}: timestamp is not UTC")
    return parsed


def key_occurrences(path: Path) -> dict[str, list[str]]:
    occurrences: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = KEY_LINE.match(line)
        if match is not None:
            occurrences.setdefault(match.group("key"), []).append(match.group("value"))
    return occurrences


def strict_key_occurrences(path: Path) -> dict[str, list[str]]:
    occurrences: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = KEY_LINE.fullmatch(line)
        if match is None:
            raise ValueError(f"{path}: invalid key/value line {line!r}")
        occurrences.setdefault(match.group("key"), []).append(match.group("value"))
    return occurrences


def require_one_occurrence(
    occurrences: dict[str, list[str]],
    key: str,
    label: str,
) -> str:
    values = occurrences.get(key, [])
    if len(values) != 1:
        raise ValueError(f"{label}: expected one {key}, found {len(values)}")
    return values[0]


def idle_xpu_summary(path: Path) -> dict[str, Any]:
    lines = [
        line.split()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    header_ok = bool(lines) and lines[0] == [
        "PID",
        "Command",
        "DeviceID",
        "SHR",
        "MEM",
    ]
    rows = lines[1:] if lines else []
    row_shapes = all(len(row) == 5 for row in rows)
    probe_only = row_shapes and all(row[1] == "xpu-smi" for row in rows)
    devices = [row[2] for row in rows if len(row) == 5]
    checks = {
        "header": header_ok,
        "four_rows": len(rows) == 4,
        "five_columns_per_row": row_shapes,
        "probe_process_only": probe_only,
        "one_row_per_device": sorted(devices) == ["0", "1", "2", "3"],
    }
    return {
        "path": str(path.resolve()),
        "sha256": sha256(path),
        "checks": checks,
        "passed": all(checks.values()),
    }


def operational_summary(directory: Path) -> dict[str, Any]:
    identity_path = directory / "identity.txt"
    cleanup_path = directory / "cleanup-status.txt"
    server_pid_path = directory / "server.pid"
    prestart_path = directory / "prestart-xpu-ps.txt"
    poststop_path = directory / "poststop-xpu-ps.txt"
    prestart_residual = directory / "prestart-residual.txt"
    poststop_residual = directory / "poststop-residual.txt"
    server_log = directory / "server.log"
    bench_path = directory / "bench.json"
    bench_stdout = directory / "bench.stdout"
    exactness_path = directory / "exactness-vs-q1.json"
    exactness_stdout = directory / "exactness-vs-q1.stdout"
    required = (
        identity_path,
        cleanup_path,
        server_pid_path,
        prestart_path,
        poststop_path,
        prestart_residual,
        poststop_residual,
        server_log,
        bench_path,
        bench_stdout,
        exactness_path,
        exactness_stdout,
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise ValueError(f"{directory}: missing operational artifacts: {missing}")

    identity_keys = key_occurrences(identity_path)
    cleanup_keys = key_occurrences(cleanup_path)
    start_values = identity_keys.get("service_start_utc", [])
    cleanup_values = cleanup_keys.get("cleanup_completed_utc", [])
    start = (
        parse_utc(start_values[0], f"{identity_path}: service_start_utc")
        if len(start_values) == 1
        else None
    )
    cleanup = (
        parse_utc(cleanup_values[0], f"{cleanup_path}: cleanup_completed_utc")
        if len(cleanup_values) == 1
        else None
    )
    expected_cleanup = {
        "original_status": "0",
        "stop_status": "0",
        "poststop_proof_status": "0",
        "final_status": "0",
    }
    cleanup_status_matches = {
        key: cleanup_keys.get(key, []) == [expected]
        for key, expected in expected_cleanup.items()
    }
    expected_cleanup_keys = set(expected_cleanup) | {"cleanup_completed_utc"}
    pid_text = server_pid_path.read_text(encoding="utf-8").strip()
    pid = int(pid_text) if pid_text.isdecimal() else None
    prestart = idle_xpu_summary(prestart_path)
    poststop = idle_xpu_summary(poststop_path)
    server_lines = server_log.read_text(encoding="utf-8", errors="replace").splitlines()
    completion_request_lines = [
        line for line in server_lines if "POST /v1/chat/completions HTTP/1.1" in line
    ]
    mutation_request_lines = [
        line
        for line in server_lines
        if re.search(r'- "(?:POST|PUT|PATCH|DELETE) \S+ HTTP/\d(?:\.\d)?" ', line)
    ]
    successful_completion_lines = [
        line
        for line in completion_request_lines
        if '"POST /v1/chat/completions HTTP/1.1" 200 OK' in line
    ]
    checks = {
        "one_service_start_timestamp": len(start_values) == 1,
        "one_cleanup_timestamp": len(cleanup_values) == 1,
        "cleanup_not_before_start": (
            start is not None and cleanup is not None and cleanup >= start
        ),
        "cleanup_keys_exact": set(cleanup_keys) == expected_cleanup_keys,
        "cleanup_keys_not_duplicated": all(
            len(values) == 1 for values in cleanup_keys.values()
        ),
        "cleanup_status_all_zero": all(cleanup_status_matches.values()),
        "server_pid_valid": pid is not None and pid > 1,
        "prestart_four_devices_idle": prestart["passed"],
        "poststop_four_devices_idle": poststop["passed"],
        "prestart_residual_empty": prestart_residual.stat().st_size == 0,
        "poststop_residual_empty": poststop_residual.stat().st_size == 0,
        "exactly_13_completion_posts": (len(completion_request_lines) == PROMPT_COUNT),
        "all_completion_posts_succeeded": (
            len(successful_completion_lines)
            == len(completion_request_lines)
            == PROMPT_COUNT
        ),
        "no_other_mutating_http_requests": (
            mutation_request_lines == completion_request_lines
        ),
        "bench_stdout_matches_json": sha256(bench_stdout) == sha256(bench_path),
        "exactness_stdout_matches_json": (
            sha256(exactness_stdout) == sha256(exactness_path)
        ),
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "service_start_utc": None if start is None else start.isoformat(),
        "cleanup_completed_utc": None if cleanup is None else cleanup.isoformat(),
        "server_pid": pid,
        "completion_post_count": len(completion_request_lines),
        "successful_completion_post_count": len(successful_completion_lines),
        "mutating_http_request_count": len(mutation_request_lines),
        "cleanup_status_matches": cleanup_status_matches,
        "prestart_idle": prestart,
        "poststop_idle": poststop,
        "artifact_sha256": {path.name: sha256(path) for path in required},
    }


def benchmark_identity_summary(bench: dict[str, Any]) -> dict[str, Any]:
    identity_value = bench.get("run_identity")
    identity = identity_value if isinstance(identity_value, dict) else {}
    suite_value = identity.get("suite")
    suite = suite_value if isinstance(suite_value, dict) else {}
    request_extra_value = identity.get("request_extra")
    request_extra = request_extra_value if isinstance(request_extra_value, dict) else {}
    chat_template_value = request_extra.get("chat_template_kwargs")
    chat_template_kwargs = (
        chat_template_value if isinstance(chat_template_value, dict) else {}
    )
    freshness_value = bench.get("fresh_response_validity")
    freshness = freshness_value if isinstance(freshness_value, dict) else {}
    checks = {
        "run_identity_object": isinstance(identity_value, dict),
        "api_mode_chat": identity.get("api_mode") == "chat",
        "model_laguna_s_2_1_int4": identity.get("model") == CANONICAL_MODEL,
        "seed_1": (
            type(identity.get("seed")) is int and identity.get("seed") == CANONICAL_SEED
        ),
        "max_tokens_512": (
            type(identity.get("max_tokens")) is int
            and identity.get("max_tokens") == CANONICAL_MAX_TOKENS
        ),
        "prompt_count_13": (
            type(identity.get("prompt_count")) is int
            and identity.get("prompt_count") == PROMPT_COUNT
        ),
        "return_token_ids_true": identity.get("return_token_ids") is True,
        "enable_thinking_false": (chat_template_kwargs.get("enable_thinking") is False),
        "suite_id_canonical": suite.get("suite_id") == CANONICAL_SUITE_ID,
        "suite_version_1": (
            type(suite.get("version")) is int
            and suite.get("version") == CANONICAL_SUITE_VERSION
        ),
        "suite_path_canonical": identity.get("suite_path") == CANONICAL_SUITE_REL,
        "freshness_suite_id_canonical": (
            freshness.get("suite_id") == CANONICAL_SUITE_ID
        ),
        "freshness_suite_version_1": (
            type(freshness.get("suite_version")) is int
            and freshness.get("suite_version") == CANONICAL_SUITE_VERSION
        ),
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "run_identity": identity,
    }


def identity_summary(path: Path, expected_treatment: str) -> dict[str, Any]:
    if expected_treatment not in {"control", "candidate"}:
        raise ValueError(f"invalid expected treatment: {expected_treatment}")
    leg_matches = [
        (index, key, basename, treatment)
        for index, (key, basename, treatment) in enumerate(CAMPAIGN_LEGS, start=1)
        if path.parent.resolve() == (CAMPAIGN_ROOT / basename).resolve()
    ]
    if len(leg_matches) != 1:
        raise ValueError(f"{path}: not a frozen campaign leg directory")
    leg_index, leg_key, _basename, campaign_treatment = leg_matches[0]
    if campaign_treatment != expected_treatment:
        raise ValueError(f"{path}: treatment does not match frozen campaign leg")

    key_occurrences: dict[str, list[str]] = {}
    checksum_occurrences: dict[str, list[str]] = {}
    commits: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        key_match = KEY_LINE.match(line)
        if key_match is not None:
            key_occurrences.setdefault(key_match.group("key"), []).append(
                key_match.group("value")
            )
            continue
        checksum_match = CHECKSUM_LINE.match(line)
        if checksum_match is not None:
            checksum_occurrences.setdefault(
                resolved(checksum_match.group("path")), []
            ).append(checksum_match.group("sha"))
            continue
        if COMMIT_LINE.fullmatch(line):
            commits.append(line)

    campaign_entries = strict_key_occurrences(CAMPAIGN_JOURNAL)
    previous_chain_key = (
        None if leg_index == 1 else f"{CAMPAIGN_LEGS[leg_index - 2][0]}_chain_sha256"
    )
    previous_chain = (
        CAMPAIGN_GENESIS_SHA256
        if previous_chain_key is None
        else require_one_occurrence(
            campaign_entries,
            previous_chain_key,
            f"{CAMPAIGN_JOURNAL}: previous campaign chain",
        )
    )
    expected_keys = {
        **IDENTITY_FIXED_KEYS,
        "VLLM_XPU_LAGUNA_M8_W1_N_TILE": (
            "64" if expected_treatment == "control" else "128"
        ),
        "campaign_id": CAMPAIGN_ID,
        "campaign_root": str(CAMPAIGN_ROOT),
        "campaign_journal": str(CAMPAIGN_JOURNAL),
        "campaign_leg": leg_key,
        "campaign_leg_index": str(leg_index),
        "campaign_previous_chain_sha256": previous_chain,
        "treatment": expected_treatment,
    }
    xpu_smi_version_path = str(path.parent / "xpu-smi-version.txt")
    expected_checksums = {
        **IDENTITY_FIXED_CHECKSUMS,
        str(ANALYZER_PATH): sha256(ANALYZER_PATH),
        xpu_smi_version_path: XPU_SMI_VERSION_SHA256,
    }
    allowed_key_names = set(expected_keys) | {"service_start_utc"}
    start_values = key_occurrences.get("service_start_utc", [])
    valid_service_start = False
    if len(start_values) == 1:
        parse_utc(start_values[0], f"{path}: service_start_utc")
        valid_service_start = True
    key_value_matches = {
        key: len(key_occurrences.get(key, [])) == 1
        and key_occurrences[key][0] == expected
        for key, expected in expected_keys.items()
    }
    checksum_value_matches = {
        resolved(checksum_path): (
            len(checksum_occurrences.get(resolved(checksum_path), [])) == 1
            and checksum_occurrences[resolved(checksum_path)][0] == expected_sha
        )
        for checksum_path, expected_sha in expected_checksums.items()
    }
    checks = {
        "no_duplicate_key_lines": all(
            len(values) == 1 for values in key_occurrences.values()
        ),
        "all_required_key_lines_present_once": all(
            len(key_occurrences.get(key, [])) == 1 for key in expected_keys
        ),
        "no_unexpected_key_lines": set(key_occurrences) == allowed_key_names,
        "one_valid_service_start_utc": valid_service_start,
        "all_fixed_key_values_match": all(key_value_matches.values()),
        "no_duplicate_checksum_paths": all(
            len(values) == 1 for values in checksum_occurrences.values()
        ),
        "all_required_checksums_present_once": all(
            len(checksum_occurrences.get(resolved(checksum_path), [])) == 1
            for checksum_path in expected_checksums
        ),
        "no_unexpected_checksum_paths": (
            set(checksum_occurrences) == {resolved(path) for path in expected_checksums}
        ),
        "all_fixed_checksums_match": all(checksum_value_matches.values()),
        "runner_sha256_matches": checksum_value_matches[resolved(RUNNER_PATH)],
        "xpu_smi_version_sha256_matches": checksum_value_matches[
            resolved(xpu_smi_version_path)
        ],
        "three_source_commit_lines": len(commits) == 3,
        "vllm_commit_matches": len(commits) == 3 and commits[1] == VLLM_COMMIT,
        "kernel_commit_matches": len(commits) == 3 and commits[2] == KERNEL_COMMIT,
    }
    return {
        "path": str(path.resolve()),
        "sha256": sha256(path),
        "expected_treatment": expected_treatment,
        "checks": checks,
        "passed": all(checks.values()),
        "required_key_values": {
            key: values[0] if len(values) == 1 else values
            for key in expected_keys
            if (values := key_occurrences.get(key, []))
        },
        "key_value_matches": key_value_matches,
        "required_checksum_values": {
            resolved(checksum_path): values[0] if len(values) == 1 else values
            for checksum_path in expected_checksums
            if (values := checksum_occurrences.get(resolved(checksum_path), []))
        },
        "checksum_value_matches": checksum_value_matches,
        "duplicate_keys": {
            key: values for key, values in key_occurrences.items() if len(values) != 1
        },
        "duplicate_checksum_paths": {
            checksum_path: values
            for checksum_path, values in checksum_occurrences.items()
            if len(values) != 1
        },
        "source_commits": {
            "repository": commits[0] if len(commits) >= 1 else None,
            "vllm": commits[1] if len(commits) >= 2 else None,
            "kernels": commits[2] if len(commits) >= 3 else None,
        },
    }


def prom_samples(path: Path) -> list[tuple[str, str, float]]:
    samples: list[tuple[str, str, float]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        match = PROM_LINE.match(raw_line)
        if match:
            samples.append(
                (
                    match.group("name"),
                    match.group("labels") or "",
                    float(match.group("value")),
                )
            )
    return samples


def one_sample(samples: list[tuple[str, str, float]], name: str) -> float:
    values = [value for metric, _labels, value in samples if metric == name]
    if len(values) != 1:
        raise ValueError(f"expected one {name} sample, found {len(values)}")
    if not math.isfinite(values[0]):
        raise ValueError(f"{name}: non-finite metric value")
    return values[0]


def position_samples(
    samples: list[tuple[str, str, float]], name: str
) -> dict[int, float]:
    positions: dict[int, float] = {}
    for metric, labels, value in samples:
        if metric != name:
            continue
        match = POSITION_LABEL.search(labels)
        if match is None:
            raise ValueError(f"{name}: sample is missing a position label: {labels}")
        position = int(match.group("position"))
        if position in positions:
            raise ValueError(f"{name}: duplicate position {position}")
        if not math.isfinite(value):
            raise ValueError(f"{name}: non-finite value at position {position}")
        positions[position] = value
    if not positions:
        raise ValueError(f"found no {name} position samples")
    expected = list(range(max(positions) + 1))
    if sorted(positions) != expected:
        raise ValueError(
            f"{name}: positions must be contiguous from zero; found {sorted(positions)}"
        )
    return positions


def integer_delta(after: float, before: float, name: str) -> int:
    delta = after - before
    rounded = round(delta)
    if delta < 0.0 or not math.isclose(delta, rounded, abs_tol=1e-6):
        raise ValueError(f"{name}: invalid counter delta {delta}")
    return int(rounded)


def metrics_summary(directory: Path) -> dict[str, Any]:
    before_path = directory / "metrics-before-suite.prom"
    after_path = directory / "metrics-after-suite.prom"
    before = prom_samples(before_path)
    after = prom_samples(after_path)

    scalar_names = {
        "draft_cycles": "vllm:spec_decode_num_drafts_total",
        "draft_tokens": "vllm:spec_decode_num_draft_tokens_total",
        "accepted_tokens": "vllm:spec_decode_num_accepted_tokens_total",
        "decode_requests": "vllm:request_decode_time_seconds_count",
    }
    raw_before = {
        key: one_sample(before, metric) for key, metric in scalar_names.items()
    }
    raw_after = {key: one_sample(after, metric) for key, metric in scalar_names.items()}
    raw_before["decode_seconds"] = one_sample(
        before, "vllm:request_decode_time_seconds_sum"
    )
    raw_after["decode_seconds"] = one_sample(
        after, "vllm:request_decode_time_seconds_sum"
    )

    position_name = "vllm:spec_decode_num_accepted_tokens_per_pos_total"
    positions_before = position_samples(before, position_name)
    positions_after = position_samples(after, position_name)
    if positions_before.keys() != positions_after.keys():
        raise ValueError("accepted-position metric shape changed during the suite")

    deltas = {
        key: integer_delta(raw_after[key], raw_before[key], key) for key in scalar_names
    }
    decode_seconds = raw_after["decode_seconds"] - raw_before["decode_seconds"]
    if decode_seconds <= 0.0:
        raise ValueError(f"invalid request decode-time delta {decode_seconds}")
    accepted_by_position = [
        integer_delta(
            positions_after[position],
            positions_before[position],
            f"accepted_by_position[{position}]",
        )
        for position in sorted(positions_before)
    ]
    if deltas["draft_cycles"] <= 0 or deltas["draft_tokens"] <= 0:
        raise ValueError("speculation counters did not advance")
    if deltas["decode_requests"] != PROMPT_COUNT:
        raise ValueError(
            f"expected {PROMPT_COUNT} decode requests, "
            f"found {deltas['decode_requests']}"
        )

    clean_before_checks = {
        "draft_cycles_zero": raw_before["draft_cycles"] == 0.0,
        "draft_tokens_zero": raw_before["draft_tokens"] == 0.0,
        "accepted_tokens_zero": raw_before["accepted_tokens"] == 0.0,
        "accepted_by_position_zero": all(
            value == 0.0 for value in positions_before.values()
        ),
        "decode_requests_zero": raw_before["decode_requests"] == 0.0,
        "decode_seconds_zero": raw_before["decode_seconds"] == 0.0,
    }
    acceptance_rate = deltas["accepted_tokens"] / deltas["draft_tokens"]
    speculation_consistency_checks = {
        "seven_acceptance_positions": len(accepted_by_position) == 7,
        "accepted_positions_sum_to_total": (
            sum(accepted_by_position) == deltas["accepted_tokens"]
        ),
        "draft_tokens_equal_depth_times_cycles": (
            deltas["draft_tokens"] == 7 * deltas["draft_cycles"]
        ),
        "accepted_tokens_bounded": (
            0 <= deltas["accepted_tokens"] <= deltas["draft_tokens"]
        ),
        "accepted_positions_nonnegative": all(
            value >= 0 for value in accepted_by_position
        ),
    }
    if not all(speculation_consistency_checks.values()):
        raise ValueError(
            f"inconsistent speculation counters: {speculation_consistency_checks}"
        )
    return {
        "before_sha256": sha256(before_path),
        "after_sha256": sha256(after_path),
        "clean_before_checks": clean_before_checks,
        "clean_before_pass": all(clean_before_checks.values()),
        "raw_before": {
            **raw_before,
            "accepted_by_position": [
                positions_before[position] for position in sorted(positions_before)
            ],
        },
        "raw_after": {
            **raw_after,
            "accepted_by_position": [
                positions_after[position] for position in sorted(positions_after)
            ],
        },
        "request_decode_seconds": decode_seconds,
        "request_decode_count": deltas["decode_requests"],
        "aggregate_cycle_ms": 1000.0 * decode_seconds / deltas["draft_cycles"],
        "speculation_consistency_checks": speculation_consistency_checks,
        "speculation": {
            "draft_cycles": deltas["draft_cycles"],
            "draft_tokens": deltas["draft_tokens"],
            "accepted_tokens": deltas["accepted_tokens"],
            "accepted_by_position": accepted_by_position,
            "acceptance_rate": acceptance_rate,
        },
    }


def freshness_summary(bench: dict[str, Any]) -> dict[str, Any]:
    freshness = bench.get("fresh_response_validity", {})
    final_gate = bench.get("realistic_final_gate", {})
    rows = bench.get("rows", [])
    cached_vector = freshness.get("cached_tokens", [])
    final_gate_cached_vector = final_gate.get("cached_tokens", [])
    prompt_ids = [row.get("prompt_id") for row in rows]
    request_ids = [row.get("request_id") for row in rows]
    prompt_hashes = bench.get("prompt_sha256s", [])
    output_hashes = bench.get("output_sha256s", [])
    row_cached_tokens = [row.get("cached_tokens") for row in rows]
    row_prompt_hashes = [row.get("prompt_sha256") for row in rows]
    row_output_hashes = [row.get("sha256") for row in rows]
    checks = {
        "reported_fresh_response_valid": freshness.get("valid") is True,
        "reported_realistic_final_gate": final_gate.get("passed") is True,
        "prompt_count_13": freshness.get("prompt_count") == PROMPT_COUNT,
        "row_count_13": len(rows) == PROMPT_COUNT,
        "each_prompt_run_once": freshness.get("each_prompt_run_once") is True,
        "prompts_reported_unique": freshness.get("prompts_are_unique") is True,
        "prompt_ids_unique": len(set(prompt_ids)) == len(prompt_ids) == PROMPT_COUNT,
        "request_ids_unique": (
            len(set(request_ids)) == len(request_ids) == PROMPT_COUNT
        ),
        "prompt_hashes_unique": (
            len(set(prompt_hashes)) == len(prompt_hashes) == PROMPT_COUNT
        ),
        "output_hash_count_13": len(output_hashes) == PROMPT_COUNT,
        "prompt_hash_schema_valid": (
            len(prompt_hashes) == PROMPT_COUNT
            and all(
                isinstance(value, str) and SHA256_HEX.fullmatch(value)
                for value in prompt_hashes
            )
        ),
        "output_hash_schema_valid": (
            len(output_hashes) == PROMPT_COUNT
            and all(
                isinstance(value, str) and SHA256_HEX.fullmatch(value)
                for value in output_hashes
            )
        ),
        "top_level_prompt_hashes_match_rows": prompt_hashes == row_prompt_hashes,
        "top_level_output_hashes_match_rows": output_hashes == row_output_hashes,
        "cached_tokens_reported_zero": (
            freshness.get("cached_tokens_all_zero") is True
        ),
        "cached_vector_13_zero": (
            len(cached_vector) == PROMPT_COUNT
            and all(value == 0 for value in cached_vector)
        ),
        "row_cached_tokens_zero": (
            len(rows) == PROMPT_COUNT and all(value == 0 for value in row_cached_tokens)
        ),
        "freshness_cached_vector_matches_rows": cached_vector == row_cached_tokens,
        "no_context_checkpoint_or_prefix_reuse": (
            freshness.get("context_checkpoints_or_prefix_reuse") is False
        ),
        "no_history_acceleration": (freshness.get("history_acceleration") is False),
        "no_ngram_history_acceleration": (
            freshness.get("ngram_history_acceleration") is False
        ),
        "no_response_reuse": freshness.get("response_reuse") is False,
        "token_ids_requested": freshness.get("return_token_ids_requested") is True,
        "final_gate_cached_tokens_zero": (
            final_gate.get("cached_tokens_all_zero") is True
        ),
        "final_gate_cached_vector_matches_rows": (
            final_gate_cached_vector == row_cached_tokens
        ),
        "final_gate_prompts_unique": final_gate.get("prompts_unique") is True,
        "final_gate_metric_window_present": (
            final_gate.get("metric_token_id_events_at_least_window") is True
            and final_gate.get("completion_tokens_at_least_metric_window") is True
        ),
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "classification": freshness.get("classification"),
        "suite_id": freshness.get("suite_id"),
        "suite_version": freshness.get("suite_version"),
        "cached_tokens": cached_vector,
        "prompt_sha256s": prompt_hashes,
        "output_sha256s": output_hashes,
    }


def direct_token_comparison(
    teacher_path: Path,
    candidate_path: Path,
) -> dict[str, Any]:
    teacher = load_json(teacher_path)
    candidate = load_json(candidate_path)
    teacher_rows_value = teacher.get("rows")
    candidate_rows_value = candidate.get("rows")
    teacher_rows = teacher_rows_value if isinstance(teacher_rows_value, list) else []
    candidate_rows = (
        candidate_rows_value if isinstance(candidate_rows_value, list) else []
    )
    audited_rows: list[dict[str, Any]] = []
    exact_count = 0
    for index, (teacher_row, candidate_row) in enumerate(
        zip(teacher_rows, candidate_rows, strict=False)
    ):
        teacher_row = teacher_row if isinstance(teacher_row, dict) else {}
        candidate_row = candidate_row if isinstance(candidate_row, dict) else {}
        identity_equal = all(
            teacher_row.get(key) == candidate_row.get(key)
            for key in ("prompt_index", "prompt_id", "prompt_sha256")
        )
        teacher_ids = teacher_row.get("token_ids")
        candidate_ids = candidate_row.get("token_ids")
        teacher_ids_valid = isinstance(teacher_ids, list) and all(
            type(token_id) is int for token_id in teacher_ids
        )
        candidate_ids_valid = isinstance(candidate_ids, list) and all(
            type(token_id) is int for token_id in candidate_ids
        )
        token_ids_equal = (
            teacher_ids_valid and candidate_ids_valid and candidate_ids == teacher_ids
        )
        cached_zero = candidate_row.get("cached_tokens") == 0
        row_exact = identity_equal and token_ids_equal and cached_zero
        exact_count += int(row_exact)
        audited_rows.append(
            {
                "index": index,
                "prompt_id": candidate_row.get("prompt_id"),
                "prompt_tokens": candidate_row.get("prompt_tokens"),
                "completion_tokens": candidate_row.get("completion_tokens"),
                "identity_equal": identity_equal,
                "teacher_token_ids_valid": teacher_ids_valid,
                "candidate_token_ids_valid": candidate_ids_valid,
                "teacher_token_count": (
                    len(teacher_ids) if isinstance(teacher_ids, list) else None
                ),
                "candidate_token_count": (
                    len(candidate_ids) if isinstance(candidate_ids, list) else None
                ),
                "token_ids_equal": token_ids_equal,
                "cached_zero": cached_zero,
                "exact": row_exact,
            }
        )

    long_then_next = {
        "long_prompt_id": (
            audited_rows[0]["prompt_id"] if len(audited_rows) >= 1 else None
        ),
        "long_completion_tokens": (
            audited_rows[0]["completion_tokens"] if len(audited_rows) >= 1 else None
        ),
        "long_exact": (audited_rows[0]["exact"] if len(audited_rows) >= 1 else False),
        "next_prompt_id": (
            audited_rows[1]["prompt_id"] if len(audited_rows) >= 2 else None
        ),
        "next_exact": (audited_rows[1]["exact"] if len(audited_rows) >= 2 else False),
    }
    long_then_next["passed"] = (
        len(audited_rows) >= 2
        and long_then_next["long_completion_tokens"] == CANONICAL_MAX_TOKENS
        and long_then_next["long_exact"] is True
        and long_then_next["next_exact"] is True
    )
    rollover_rows = [
        row
        for row in audited_rows
        if type(row["prompt_tokens"]) is int and row["prompt_tokens"] >= 863
    ]
    rollover = {
        "count": len(rollover_rows),
        "exact_count": sum(row["exact"] is True for row in rollover_rows),
        "rows": rollover_rows,
    }
    checks = {
        "teacher_rows_object_list": isinstance(teacher_rows_value, list),
        "candidate_rows_object_list": isinstance(candidate_rows_value, list),
        "teacher_row_count_13": len(teacher_rows) == PROMPT_COUNT,
        "candidate_row_count_13": len(candidate_rows) == PROMPT_COUNT,
        "all_row_objects": all(
            isinstance(row, dict) for row in teacher_rows + candidate_rows
        ),
        "all_prompt_identities_equal": (
            len(audited_rows) == PROMPT_COUNT
            and all(row["identity_equal"] for row in audited_rows)
        ),
        "all_token_arrays_valid": (
            len(audited_rows) == PROMPT_COUNT
            and all(
                row["teacher_token_ids_valid"] and row["candidate_token_ids_valid"]
                for row in audited_rows
            )
        ),
        "all_complete_token_arrays_equal": exact_count == PROMPT_COUNT,
        "candidate_cached_tokens_all_zero": (
            len(audited_rows) == PROMPT_COUNT
            and all(row["cached_zero"] for row in audited_rows)
        ),
        "long_then_next_directly_recomputed": long_then_next["passed"] is True,
        "exactly_one_rollover_row_directly_recomputed": rollover["count"] == 1,
        "rollover_row_directly_recomputed_exact": rollover["exact_count"] == 1,
    }
    return {
        "teacher_path": str(teacher_path.resolve()),
        "teacher_sha256": sha256(teacher_path),
        "candidate_path": str(candidate_path.resolve()),
        "candidate_sha256": sha256(candidate_path),
        "exact_count": exact_count,
        "total": len(candidate_rows),
        "rows": audited_rows,
        "long_then_next": long_then_next,
        "rollover": rollover,
        "checks": checks,
        "passed": all(checks.values()),
    }


def comparison_checks(comparison: dict[str, Any]) -> dict[str, bool]:
    rollover = comparison.get("rollover") or {}
    long_then_next = comparison.get("long_then_next") or {}
    return {
        "exact": comparison.get("exact") is True,
        "exact_count_13": comparison.get("exact_count") == PROMPT_COUNT,
        "total_13": comparison.get("total") == PROMPT_COUNT,
        "all_cached_zero": comparison.get("all_cached_zero") is True,
        "long_then_next": long_then_next.get("passed") is True,
        "rollover_count_1": rollover.get("count") == 1,
        "rollover_exact_count_1": rollover.get("exact_count") == 1,
    }


def per_leg_exactness(exactness_path: Path, bench_path: Path) -> dict[str, Any]:
    exactness = load_json(exactness_path)
    candidates = exactness.get("candidates", [])
    if len(candidates) != 1:
        raise ValueError(
            f"{exactness_path}: expected one candidate, found {len(candidates)}"
        )
    candidate = candidates[0]
    comparison = candidate.get("comparison", {})
    direct = direct_token_comparison(Path(TEACHER_PATH), bench_path)
    checks = {
        "report_all_exact": exactness.get("all_exact") is True,
        "teacher_path_is_canonical": (
            resolved(exactness.get("teacher", "")) == resolved(TEACHER_PATH)
        ),
        "candidate_path_matches_leg": resolved(candidate.get("candidate", ""))
        == resolved(bench_path),
        "canonical_teacher_sha256": (
            direct["teacher_sha256"] == IDENTITY_FIXED_CHECKSUMS[TEACHER_PATH]
        ),
        "direct_teacher_candidate_token_comparison": direct["passed"],
        "report_exact_count_matches_direct": (
            comparison.get("exact_count") == direct["exact_count"]
        ),
        "report_total_matches_direct": comparison.get("total") == direct["total"],
        "report_long_then_next_matches_direct": (
            (comparison.get("long_then_next") or {}).get("passed")
            == direct["long_then_next"]["passed"]
            and (comparison.get("long_then_next") or {}).get("long_completion_tokens")
            == direct["long_then_next"]["long_completion_tokens"]
        ),
        "report_rollover_matches_direct": (
            (comparison.get("rollover") or {}).get("count")
            == direct["rollover"]["count"]
            and (comparison.get("rollover") or {}).get("exact_count")
            == direct["rollover"]["exact_count"]
        ),
        **comparison_checks(comparison),
    }
    return {
        "path": str(exactness_path.resolve()),
        "sha256": sha256(exactness_path),
        "teacher": resolved(exactness.get("teacher", "")),
        "candidate": resolved(candidate.get("candidate", "")),
        "direct_token_comparison": direct,
        "checks": checks,
        "passed": all(checks.values()),
        "exact_count": comparison.get("exact_count"),
        "total": comparison.get("total"),
        "long_then_next": comparison.get("long_then_next") or {},
        "rollover": comparison.get("rollover") or {},
    }


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot compute percentile of an empty sequence")
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * pct
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def primary_metric_audit(
    bench_path: Path,
    rows: list[dict[str, Any]],
    stored_primary: dict[str, Any],
) -> dict[str, Any]:
    if len(rows) != PROMPT_COUNT:
        raise ValueError(f"{bench_path}: expected {PROMPT_COUNT} rows")
    values: list[float] = []
    audited_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        offsets = row.get("token_id_offsets_s")
        token_ids = row.get("token_ids")
        if not isinstance(offsets, list) or not isinstance(token_ids, list):
            raise ValueError(f"{bench_path}: row {index} lacks token arrays")
        if len(offsets) != len(token_ids) or len(offsets) < 100:
            raise ValueError(
                f"{bench_path}: row {index} has mismatched token arrays or "
                "fewer than 100 token events"
            )
        if not all(type(token_id) is int for token_id in token_ids):
            raise ValueError(f"{bench_path}: row {index} has invalid token IDs")
        if not all(type(value) in (int, float) for value in offsets):
            raise ValueError(f"{bench_path}: row {index} has nonnumeric offsets")
        numeric_offsets = [float(value) for value in offsets]
        if not all(math.isfinite(value) and value >= 0.0 for value in numeric_offsets):
            raise ValueError(f"{bench_path}: row {index} has invalid offsets")
        if any(
            right < left
            for left, right in zip(numeric_offsets, numeric_offsets[1:], strict=False)
        ):
            raise ValueError(f"{bench_path}: row {index} offsets are nonmonotonic")
        duration = numeric_offsets[99] - numeric_offsets[0]
        if not math.isfinite(duration) or duration <= 0.0:
            raise ValueError(f"{bench_path}: row {index} has invalid metric window")
        recomputed = 100.0 / duration
        stored = row.get(METRIC)
        if (
            not isinstance(stored, (int, float))
            or not math.isfinite(float(stored))
            or not math.isclose(float(stored), recomputed, rel_tol=1e-15, abs_tol=0.0)
        ):
            raise ValueError(
                f"{bench_path}: row {index} stored metric does not recompute"
            )
        usage = row.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        token_event_count = len(offsets)
        count_checks = {
            "at_least_100_token_events": token_event_count >= 100,
            "token_array_lengths_match": (len(token_ids) == token_event_count),
            "completion_tokens_match_events": (
                type(row.get("completion_tokens")) is int
                and row["completion_tokens"] == token_event_count
            ),
            "stream_token_id_count_matches_events": (
                type(row.get("stream_token_id_count")) is int
                and row["stream_token_id_count"] == token_event_count
            ),
            "usage_completion_tokens_match_events": (
                type(usage.get("completion_tokens")) is int
                and usage["completion_tokens"] == token_event_count
            ),
            "ttft_matches_first_token_offset": (
                type(row.get("ttft_s")) in (int, float)
                and math.isfinite(float(row["ttft_s"]))
                and math.isclose(
                    float(row["ttft_s"]),
                    numeric_offsets[0],
                    rel_tol=1e-15,
                    abs_tol=0.0,
                )
            ),
            "token_timing_source": (
                row.get("token_timing_source")
                == "openai_stream_token_ids_chunk_timestamp"
            ),
        }
        if not all(count_checks.values()):
            raise ValueError(
                f"{bench_path}: row {index} token accounting mismatch: {count_checks}"
            )
        values.append(recomputed)
        audited_rows.append(
            {
                "prompt_index": row.get("prompt_index"),
                "prompt_id": row.get("prompt_id"),
                "token_event_count": token_event_count,
                "metric_duration_s": duration,
                "recomputed_tok_s": recomputed,
                "stored_tok_s": float(stored),
                "token_count_checks": count_checks,
            }
        )

    recomputed_summary = {
        "count": len(values),
        "max": max(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "min": min(values),
        "p10": percentile(values, 0.10),
        "stdev": statistics.stdev(values),
    }
    summary_checks = {
        "count": stored_primary.get("count") == recomputed_summary["count"]
    }
    for key in ("max", "mean", "median", "min", "p10", "stdev"):
        stored = stored_primary.get(key)
        summary_checks[key] = (
            isinstance(stored, (int, float))
            and math.isfinite(float(stored))
            and math.isclose(
                float(stored),
                recomputed_summary[key],
                rel_tol=1e-15,
                abs_tol=0.0,
            )
        )
    if not all(summary_checks.values()):
        raise ValueError(
            f"{bench_path}: stored primary summary does not recompute: {summary_checks}"
        )
    return {
        "passed": True,
        "formula": "100 / (token_id_offsets_s[99] - token_id_offsets_s[0])",
        "rows": audited_rows,
        "values": values,
        "recomputed_summary": recomputed_summary,
        "stored_summary_checks": summary_checks,
    }


def run_summary(label: str, directory: Path, expected_treatment: str) -> dict[str, Any]:
    bench_path = directory / "bench.json"
    exactness_path = directory / "exactness-vs-q1.json"
    identity_path = directory / "identity.txt"
    bench = load_json(bench_path)
    rows = bench.get("rows", [])
    summary_metrics = bench.get("summary", {})
    primary = summary_metrics.get(METRIC, {})
    if primary.get("count") != PROMPT_COUNT:
        raise ValueError(
            f"{bench_path}: expected {PROMPT_COUNT} values for {METRIC}, "
            f"found {primary.get('count')}"
        )
    primary_audit = primary_metric_audit(bench_path, rows, primary)

    freshness = freshness_summary(bench)
    benchmark_identity = benchmark_identity_summary(bench)
    identity = identity_summary(identity_path, expected_treatment)
    exactness = per_leg_exactness(exactness_path, bench_path)
    metrics = metrics_summary(directory)
    operational = operational_summary(directory)
    recomputed_primary = primary_audit["recomputed_summary"]
    headline_tok_s = recomputed_primary["median"]
    mean_tok_s = recomputed_primary["mean"]
    p10_tok_s = recomputed_primary["p10"]
    if not all(
        math.isfinite(value) and value > 0.0
        for value in (headline_tok_s, mean_tok_s, p10_tok_s)
    ):
        raise ValueError(f"{bench_path}: non-finite or non-positive summary")
    row_metrics = [
        {
            "prompt_id": row["prompt_id"],
            "prompt_sha256": row["prompt_sha256"],
            "prompt_tokens": int(row["prompt_tokens"]),
            "completion_tokens": int(row["completion_tokens"]),
            "cached_tokens": row["cached_tokens"],
            "tok_s": recomputed_tok_s,
        }
        for row, recomputed_tok_s in zip(rows, primary_audit["values"], strict=True)
    ]
    if any(
        not math.isfinite(row["tok_s"]) or row["tok_s"] <= 0.0 for row in row_metrics
    ):
        raise ValueError(f"{bench_path}: non-finite or non-positive row metric")
    quality_checks = {
        "freshness": freshness["passed"],
        "benchmark_run_identity": benchmark_identity["passed"],
        "record_stack_identity": identity["passed"],
        "teacher_exactness": exactness["passed"],
        "clean_pre_suite_metrics": metrics["clean_before_pass"],
        "speculation_counter_consistency": all(
            metrics["speculation_consistency_checks"].values()
        ),
        "one_logged_decode_request_per_suite_row": (
            len(rows)
            == metrics["request_decode_count"]
            == operational["completion_post_count"]
            == operational["successful_completion_post_count"]
            == PROMPT_COUNT
        ),
        "primary_metric_count_13": primary.get("count") == PROMPT_COUNT,
        "primary_metric_recomputed_from_token_events": (primary_audit["passed"]),
        "operational_cleanup_and_idle": operational["passed"],
    }
    return {
        "label": label,
        "directory": str(directory.resolve()),
        "bench_path": str(bench_path.resolve()),
        "bench_sha256": sha256(bench_path),
        "quality_and_honesty_checks": quality_checks,
        "quality_and_honesty_pass": all(quality_checks.values()),
        "freshness": freshness,
        "benchmark_run_identity": benchmark_identity,
        "identity": identity,
        "exactness": exactness,
        "operational": operational,
        "primary_metric_audit": primary_audit,
        "headline_tok_s": headline_tok_s,
        "mean_tok_s": mean_tok_s,
        "p10_tok_s": p10_tok_s,
        "bench_summary": summary_metrics,
        "metrics": metrics,
        "completion_tokens": sum(int(row["completion_tokens"]) for row in rows),
        "row_metrics": row_metrics,
    }


def paired(control: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    control_rows = control["row_metrics"]
    candidate_rows = candidate["row_metrics"]
    control_identity = [
        (row["prompt_id"], row["prompt_sha256"]) for row in control_rows
    ]
    candidate_identity = [
        (row["prompt_id"], row["prompt_sha256"]) for row in candidate_rows
    ]
    if control_identity != candidate_identity:
        raise ValueError("prompt identity/order differs between paired legs")
    if len(control_rows) != PROMPT_COUNT:
        raise ValueError(
            f"expected {PROMPT_COUNT} paired prompt rows, found {len(control_rows)}"
        )

    rows = []
    for control_row, candidate_row in zip(control_rows, candidate_rows, strict=True):
        delta_tok_s = candidate_row["tok_s"] - control_row["tok_s"]
        delta_pct = 100.0 * delta_tok_s / control_row["tok_s"]
        rows.append(
            {
                "prompt_id": control_row["prompt_id"],
                "control_tok_s": control_row["tok_s"],
                "candidate_tok_s": candidate_row["tok_s"],
                "delta_tok_s": delta_tok_s,
                "delta_pct": delta_pct,
            }
        )

    control_metrics = control["metrics"]
    candidate_metrics = candidate["metrics"]
    control_spec = control_metrics["speculation"]
    candidate_spec = candidate_metrics["speculation"]
    cycle_saving_ms = (
        control_metrics["aggregate_cycle_ms"] - candidate_metrics["aggregate_cycle_ms"]
    )
    acceptance_rate_delta = (
        candidate_spec["acceptance_rate"] - control_spec["acceptance_rate"]
    )
    row_wins = sum(row["delta_tok_s"] > 0.0 for row in rows)
    median_delta_tok_s = statistics.median(row["delta_tok_s"] for row in rows)
    median_delta_pct = statistics.median(row["delta_pct"] for row in rows)
    gates = {
        "candidate_headline_faster": (
            candidate["headline_tok_s"] > control["headline_tok_s"]
        ),
        "candidate_wins_at_least_9_of_13_rows": row_wins >= MIN_ROW_WINS,
        "paired_median_positive": median_delta_pct > 0.0,
        "aggregate_cycle_saving_at_least_0_15_ms": (
            cycle_saving_ms >= MIN_CYCLE_SAVING_MS
        ),
        "acceptance_rate_delta_at_most_0_001": (
            abs(acceptance_rate_delta) <= MAX_ACCEPTANCE_RATE_DELTA
        ),
    }
    accepted_by_position_delta = [
        candidate_value - control_value
        for control_value, candidate_value in zip(
            control_spec["accepted_by_position"],
            candidate_spec["accepted_by_position"],
            strict=True,
        )
    ]
    return {
        "control": control["label"],
        "candidate": candidate["label"],
        "headline_delta_tok_s": (
            candidate["headline_tok_s"] - control["headline_tok_s"]
        ),
        "headline_delta_pct": 100.0
        * (candidate["headline_tok_s"] / control["headline_tok_s"] - 1.0),
        "aggregate_cycle_saving_ms": cycle_saving_ms,
        "aggregate_cycle_delta_pct": 100.0
        * (
            candidate_metrics["aggregate_cycle_ms"]
            / control_metrics["aggregate_cycle_ms"]
            - 1.0
        ),
        "candidate_row_wins": row_wins,
        "candidate_row_losses_or_ties": len(rows) - row_wins,
        "median_paired_delta_tok_s": median_delta_tok_s,
        "median_paired_delta_pct": median_delta_pct,
        "acceptance_rate_delta": acceptance_rate_delta,
        "acceptance_rate_delta_percentage_points": 100.0 * acceptance_rate_delta,
        "speculation_work_identical_informational": control_spec == candidate_spec,
        "speculation_delta": {
            "draft_cycles": (
                candidate_spec["draft_cycles"] - control_spec["draft_cycles"]
            ),
            "draft_tokens": (
                candidate_spec["draft_tokens"] - control_spec["draft_tokens"]
            ),
            "accepted_tokens": (
                candidate_spec["accepted_tokens"] - control_spec["accepted_tokens"]
            ),
            "accepted_by_position": accepted_by_position_delta,
        },
        "gates": gates,
        "pass": all(gates.values()),
        "rows": rows,
    }


def sequence_summary(runs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    expected_order = ["A1", "B1", "B2", "A2"] if len(runs) == 4 else ["A1", "B1"]
    actual_order = list(runs)
    directories = [run["directory"] for run in runs.values()]
    pids = [run["operational"]["server_pid"] for run in runs.values()]
    gaps: list[dict[str, Any]] = []
    for previous_key, next_key in zip(actual_order, actual_order[1:], strict=False):
        previous_cleanup = parse_utc(
            runs[previous_key]["operational"]["cleanup_completed_utc"],
            f"{previous_key}: cleanup_completed_utc",
        )
        next_start = parse_utc(
            runs[next_key]["operational"]["service_start_utc"],
            f"{next_key}: service_start_utc",
        )
        gap_seconds = (next_start - previous_cleanup).total_seconds()
        gaps.append(
            {
                "previous": previous_key,
                "next": next_key,
                "previous_cleanup_utc": previous_cleanup.isoformat(),
                "next_start_utc": next_start.isoformat(),
                "idle_gap_seconds": gap_seconds,
                "at_least_60_seconds": gap_seconds >= 60.0,
            }
        )
    checks = {
        "expected_leg_order": actual_order == expected_order,
        "distinct_run_directories": len(set(directories)) == len(directories),
        "distinct_service_pids": (
            all(pid is not None for pid in pids) and len(set(pids)) == len(pids)
        ),
        "every_leg_operationally_clean": all(
            run["operational"]["passed"] for run in runs.values()
        ),
        "every_adjacent_idle_gap_at_least_60_seconds": (
            len(gaps) == len(runs) - 1
            and all(gap["at_least_60_seconds"] for gap in gaps)
        ),
    }
    return {
        "expected_order": expected_order,
        "actual_order": actual_order,
        "directories": directories,
        "service_pids": pids,
        "adjacent_idle_gaps": gaps,
        "checks": checks,
        "passed": all(checks.values()),
    }


def campaign_ledger_summary(
    runs: dict[str, dict[str, Any]],
    full_mode: bool,
) -> dict[str, Any]:
    expected_leg_count = 4 if full_mode else 2
    expected_legs = CAMPAIGN_LEGS[:expected_leg_count]
    expected_run_keys = [key for key, _basename, _treatment in expected_legs]
    if list(runs) != expected_run_keys:
        raise ValueError(
            "run mapping does not follow the frozen campaign prefix: "
            f"{list(runs)} != {expected_run_keys}"
        )
    if not CAMPAIGN_ROOT.is_dir() or not CAMPAIGN_JOURNAL.is_file():
        raise ValueError("frozen campaign root or journal is missing")

    entries_by_key = strict_key_occurrences(CAMPAIGN_JOURNAL)
    duplicate_keys = {
        key: values for key, values in entries_by_key.items() if len(values) != 1
    }
    if duplicate_keys:
        raise ValueError(f"campaign journal has duplicate keys: {duplicate_keys}")
    entries = {key: values[0] for key, values in entries_by_key.items()}
    header = {
        "campaign_id": CAMPAIGN_ID,
        "campaign_root": str(CAMPAIGN_ROOT),
        "runner_sha256": RUNNER_SHA256,
        "frozen_sequence": "A1-control,B1-candidate,B2-candidate,A2-control",
        "genesis_chain_sha256": CAMPAIGN_GENESIS_SHA256,
    }
    expected_keys = set(header)
    header_checks = {
        key: entries.get(key) == expected for key, expected in header.items()
    }

    phase1_binding: dict[str, Any] | None = None
    phase1_sha256 = "-"
    if full_mode:
        phase1_path = CAMPAIGN_ROOT / "phase1-analysis.json"
        phase1_markdown = CAMPAIGN_ROOT / "phase1-analysis.md"
        phase1_stdout = CAMPAIGN_ROOT / "phase1-analysis.stdout"
        phase1_seal = CAMPAIGN_ROOT / "phase1-analysis.seal.json"
        phase_paths = (
            phase1_path,
            phase1_markdown,
            phase1_stdout,
            phase1_seal,
        )
        missing = [str(path) for path in phase_paths if not path.is_file()]
        if missing:
            raise ValueError(f"missing frozen phase-one artifacts: {missing}")
        phase1 = load_json(phase1_path)
        phase_seal = load_json(phase1_seal)
        phase1_sha256 = sha256(phase1_path)
        phase_entries = {
            "phase1_analysis_path": str(phase1_path),
            "phase1_analysis_sha256": phase1_sha256,
            "phase1_markdown_sha256": sha256(phase1_markdown),
            "phase1_stdout_sha256": sha256(phase1_stdout),
            "phase1_seal_sha256": sha256(phase1_seal),
            "phase1_analyzer_sha256": sha256(ANALYZER_PATH),
        }
        expected_keys.update(phase_entries)
        phase_entry_checks = {
            key: entries.get(key) == expected for key, expected in phase_entries.items()
        }
        phase_checks = {
            "stdout_matches_json": sha256(phase1_stdout) == phase1_sha256,
            "analysis_mode": phase1.get("analysis_mode") == "phase1_a1_b1",
            "phase1_pass": phase1.get("phase1_pass") is True,
            "failed_phase1_gates_empty": (
                phase1.get("failed_gates", {}).get("phase1") == []
            ),
            "order": phase1.get("order") == ["A1-control", "B1-candidate"],
            "runner_sha256": (
                phase1.get("frozen_run_identity", {}).get("runner_sha256")
                == RUNNER_SHA256
            ),
            "analyzer_sha256": (
                phase1.get("frozen_run_identity", {}).get("analyzer_sha256")
                == sha256(ANALYZER_PATH)
            ),
            "a1_bench_sha256": (
                phase1.get("runs", {}).get("A1", {}).get("bench_sha256")
                == runs["A1"]["bench_sha256"]
            ),
            "b1_bench_sha256": (
                phase1.get("runs", {}).get("B1", {}).get("bench_sha256")
                == runs["B1"]["bench_sha256"]
            ),
            "phase_pair_pass": (
                phase1.get("pairs", {}).get("B1_vs_A1", {}).get("pass") is True
            ),
            "phase_sequence_pass": (
                phase1.get("phase1_sequence", {}).get("passed") is True
            ),
            "phase_campaign_ledger_pass": (
                phase1.get("campaign_ledger", {}).get("passed") is True
            ),
            "phase_seal_valid": phase_seal.get("valid") is True,
            "phase_seal_mode": (phase_seal.get("analysis_mode") == "phase1_a1_b1"),
            "phase_seal_json": (
                phase_seal.get("analysis_json_sha256") == phase1_sha256
            ),
            "phase_seal_markdown": (
                phase_seal.get("analysis_markdown_sha256") == sha256(phase1_markdown)
            ),
            "phase_seal_stdout": (
                phase_seal.get("analysis_stdout_sha256") == sha256(phase1_stdout)
            ),
            "phase_seal_analyzer": (
                phase_seal.get("analyzer_sha256") == sha256(ANALYZER_PATH)
            ),
            "phase_seal_runner": (phase_seal.get("runner_sha256") == RUNNER_SHA256),
            "phase_seal_journal": (
                phase_seal.get("campaign_journal_sha256")
                == phase1.get("campaign_ledger", {}).get("journal_sha256")
            ),
            "phase_seal_chain": (
                phase_seal.get("campaign_final_chain_sha256")
                == phase1.get("campaign_ledger", {}).get("final_chain_sha256")
            ),
        }
        phase1_binding = {
            "path": str(phase1_path),
            "sha256": phase1_sha256,
            "entry_checks": phase_entry_checks,
            "checks": phase_checks,
            "passed": all(phase_entry_checks.values()) and all(phase_checks.values()),
        }

    previous_chain = CAMPAIGN_GENESIS_SHA256
    leg_summaries: dict[str, Any] = {}
    for key, basename, treatment in expected_legs:
        directory = (CAMPAIGN_ROOT / basename).resolve()
        prefix = f"{key}_"
        required_keys = {
            f"{prefix}attempt_started_utc",
            f"{prefix}run_dir",
            f"{prefix}treatment",
            f"{prefix}service_start_utc",
            f"{prefix}final_status",
            f"{prefix}cleanup_completed_utc",
            f"{prefix}evidence_manifest_path",
            f"{prefix}evidence_manifest_sha256",
            f"{prefix}previous_chain_sha256",
            f"{prefix}chain_sha256",
        }
        expected_keys.update(required_keys)
        missing_keys = sorted(required_keys - set(entries))
        if missing_keys:
            raise ValueError(
                f"{key}: campaign journal keys are missing: {missing_keys}"
            )
        attempt = parse_utc(
            entries[f"{prefix}attempt_started_utc"],
            f"{key}: attempt_started_utc",
        )
        service = parse_utc(
            entries[f"{prefix}service_start_utc"],
            f"{key}: service_start_utc",
        )
        cleanup = parse_utc(
            entries[f"{prefix}cleanup_completed_utc"],
            f"{key}: cleanup_completed_utc",
        )
        manifest = directory / "leg-evidence.sha256"
        manifest_entries: dict[str, str] = {}
        if not manifest.is_file():
            raise ValueError(f"{key}: leg evidence manifest is missing")
        for line in manifest.read_text(encoding="utf-8").splitlines():
            match = CHECKSUM_LINE.fullmatch(line)
            if match is None:
                raise ValueError(f"{manifest}: invalid checksum line {line!r}")
            manifest_path = resolved(match.group("path"))
            if manifest_path in manifest_entries:
                raise ValueError(f"{manifest}: duplicate path {manifest_path}")
            manifest_entries[manifest_path] = match.group("sha")
        expected_paths = {resolved(directory / name) for name in LEG_EVIDENCE_NAMES}
        expected_directory_entries = set(LEG_EVIDENCE_NAMES) | {"leg-evidence.sha256"}
        directory_entries = list(directory.iterdir())
        actual_directory_entries = {path.name for path in directory_entries}
        actual_hashes = {
            path: sha256(Path(path)) for path in expected_paths if Path(path).is_file()
        }
        manifest_sha256 = sha256(manifest)
        leg_phase1_sha256 = phase1_sha256 if key in {"B2", "A2"} else "-"
        chain_payload = "|".join(
            (
                previous_chain,
                key,
                str(directory),
                treatment,
                entries[f"{prefix}attempt_started_utc"],
                entries[f"{prefix}service_start_utc"],
                entries[f"{prefix}cleanup_completed_utc"],
                manifest_sha256,
                leg_phase1_sha256,
            )
        )
        computed_chain = hashlib.sha256(
            (chain_payload + "\n").encode("utf-8")
        ).hexdigest()
        run = runs[key]
        checks = {
            "run_directory": entries[f"{prefix}run_dir"] == str(directory),
            "treatment": entries[f"{prefix}treatment"] == treatment,
            "final_status_zero": entries[f"{prefix}final_status"] == "0",
            "attempt_not_after_service": attempt <= service,
            "service_not_after_cleanup": service <= cleanup,
            "service_matches_leg_identity": service
            == parse_utc(
                run["operational"]["service_start_utc"],
                f"{key}: operational service start",
            ),
            "cleanup_matches_leg_artifact": cleanup
            == parse_utc(
                run["operational"]["cleanup_completed_utc"],
                f"{key}: operational cleanup",
            ),
            "manifest_path": (
                entries[f"{prefix}evidence_manifest_path"] == str(manifest)
            ),
            "manifest_sha256": (
                entries[f"{prefix}evidence_manifest_sha256"] == manifest_sha256
            ),
            "manifest_path_set_exact": set(manifest_entries) == expected_paths,
            "manifest_files_all_present": set(actual_hashes) == expected_paths,
            "manifest_hashes_match_current_files": (manifest_entries == actual_hashes),
            "leg_directory_entry_set_exact": (
                actual_directory_entries == expected_directory_entries
            ),
            "leg_directory_contains_regular_files_only": all(
                path.is_file() and not path.is_symlink() for path in directory_entries
            ),
            "previous_chain": (
                entries[f"{prefix}previous_chain_sha256"] == previous_chain
            ),
            "chain_sha256": entries[f"{prefix}chain_sha256"] == computed_chain,
            "identity_previous_chain": (
                run["identity"]["required_key_values"].get(
                    "campaign_previous_chain_sha256"
                )
                == previous_chain
            ),
        }
        leg_summaries[key] = {
            "directory": str(directory),
            "manifest_path": str(manifest),
            "manifest_sha256": manifest_sha256,
            "previous_chain_sha256": previous_chain,
            "computed_chain_sha256": computed_chain,
            "recorded_chain_sha256": entries[f"{prefix}chain_sha256"],
            "checks": checks,
            "passed": all(checks.values()),
        }
        previous_chain = computed_chain

    journal_key_set_check = set(entries) == expected_keys
    expected_directories = {basename for _key, basename, _treatment in expected_legs}
    actual_directories = {
        path.name for path in CAMPAIGN_ROOT.iterdir() if path.is_dir()
    }
    checks = {
        "header": all(header_checks.values()),
        "journal_key_set_exact": journal_key_set_check,
        "campaign_directories_exact_no_omitted_intervening_or_rescue": (
            actual_directories == expected_directories
        ),
        "all_leg_manifests_and_chain_links_pass": all(
            leg["passed"] for leg in leg_summaries.values()
        ),
        "phase1_binding": (phase1_binding is None or phase1_binding["passed"]),
    }
    return {
        "campaign_id": CAMPAIGN_ID,
        "campaign_root": str(CAMPAIGN_ROOT),
        "journal_path": str(CAMPAIGN_JOURNAL),
        "journal_sha256": sha256(CAMPAIGN_JOURNAL),
        "expected_leg_count": expected_leg_count,
        "header_checks": header_checks,
        "journal_keys": sorted(entries),
        "expected_journal_keys": sorted(expected_keys),
        "actual_directories": sorted(actual_directories),
        "expected_directories": sorted(expected_directories),
        "phase1_binding": phase1_binding,
        "legs": leg_summaries,
        "final_chain_sha256": previous_chain,
        "checks": checks,
        "passed": all(checks.values()),
    }


def exactness_bundle(
    path: Path,
    expected_teacher: str,
    expected_candidates: list[str],
) -> dict[str, Any]:
    report = load_json(path)
    candidates = report.get("candidates", [])
    actual_candidates = [
        resolved(candidate.get("candidate", "")) for candidate in candidates
    ]
    comparison_passes = [
        all(comparison_checks(candidate.get("comparison", {})).values())
        for candidate in candidates
    ]
    direct_comparisons = [
        direct_token_comparison(Path(expected_teacher), Path(candidate_path))
        for candidate_path in expected_candidates
    ]
    checks = {
        "all_exact": report.get("all_exact") is True,
        "teacher_path_matches": resolved(report.get("teacher", ""))
        == resolved(expected_teacher),
        "candidate_count_matches": len(candidates) == len(expected_candidates),
        "candidate_paths_match": (
            len(set(actual_candidates)) == len(actual_candidates)
            and actual_candidates == [resolved(value) for value in expected_candidates]
        ),
        "every_comparison_exact_13": (
            len(comparison_passes) == len(expected_candidates)
            and all(comparison_passes)
        ),
        "every_token_array_directly_recomputed_exact": (
            len(direct_comparisons) == len(expected_candidates)
            and all(comparison["passed"] for comparison in direct_comparisons)
        ),
        "report_counts_match_direct_recomputation": (
            len(candidates) == len(direct_comparisons)
            and all(
                candidate.get("comparison", {}).get("exact_count")
                == direct["exact_count"]
                and candidate.get("comparison", {}).get("total") == direct["total"]
                for candidate, direct in zip(
                    candidates, direct_comparisons, strict=True
                )
            )
        ),
        "report_canaries_match_direct_recomputation": (
            len(candidates) == len(direct_comparisons)
            and all(
                (candidate.get("comparison", {}).get("long_then_next") or {}).get(
                    "passed"
                )
                == direct["long_then_next"]["passed"]
                and (candidate.get("comparison", {}).get("rollover") or {}).get("count")
                == direct["rollover"]["count"]
                and (candidate.get("comparison", {}).get("rollover") or {}).get(
                    "exact_count"
                )
                == direct["rollover"]["exact_count"]
                for candidate, direct in zip(
                    candidates, direct_comparisons, strict=True
                )
            )
        ),
    }
    return {
        "path": str(path.resolve()),
        "sha256": sha256(path),
        "teacher": resolved(report.get("teacher", "")),
        "candidates": actual_candidates,
        "direct_token_comparisons": direct_comparisons,
        "checks": checks,
        "passed": all(checks.values()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze A1/B1 phase-one evidence or the complete A1/B1/B2/A2 "
            "Laguna routed-W1 N64/N128 crossover."
        )
    )
    parser.add_argument("--a1", type=Path, required=True)
    parser.add_argument("--b1", type=Path, required=True)
    parser.add_argument("--b2", type=Path)
    parser.add_argument("--a2", type=Path)
    parser.add_argument("--all-vs-teacher", type=Path)
    parser.add_argument("--cross-leg", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    args = parser.parse_args()

    full_paths = (args.b2 is not None, args.a2 is not None)
    if any(full_paths) and not all(full_paths):
        parser.error("--b2 and --a2 must be supplied together")
    combined_paths = (
        args.all_vs_teacher is not None,
        args.cross_leg is not None,
    )
    if any(combined_paths) and not all(combined_paths):
        parser.error("--all-vs-teacher and --cross-leg must be supplied together")
    if all(full_paths) and not all(combined_paths):
        parser.error("full ABBA analysis requires --all-vs-teacher and --cross-leg")
    expected_leg_paths = {
        key.lower(): (CAMPAIGN_ROOT / basename).resolve()
        for key, basename, _treatment in CAMPAIGN_LEGS
    }
    for argument_name in ("a1", "b1"):
        if getattr(args, argument_name).resolve() != expected_leg_paths[argument_name]:
            parser.error(
                f"--{argument_name} must be the frozen campaign "
                f"{argument_name.upper()} directory"
            )
    if all(full_paths):
        for argument_name in ("b2", "a2"):
            if (
                getattr(args, argument_name).resolve()
                != expected_leg_paths[argument_name]
            ):
                parser.error(
                    f"--{argument_name} must be the frozen campaign "
                    f"{argument_name.upper()} directory"
                )
        if (
            args.all_vs_teacher.resolve()
            != (CAMPAIGN_ROOT / "all-vs-canonical-teacher.json").resolve()
        ):
            parser.error("--all-vs-teacher must use the frozen campaign path")
        if (
            args.cross_leg.resolve()
            != (CAMPAIGN_ROOT / "cross-leg-exactness.json").resolve()
        ):
            parser.error("--cross-leg must use the frozen campaign path")
        expected_out = (CAMPAIGN_ROOT / "full-analysis.json").resolve()
        expected_markdown = (CAMPAIGN_ROOT / "full-analysis.md").resolve()
    else:
        if any(combined_paths):
            parser.error("phase-one analysis does not accept combined exactness")
        expected_out = (CAMPAIGN_ROOT / "phase1-analysis.json").resolve()
        expected_markdown = (CAMPAIGN_ROOT / "phase1-analysis.md").resolve()
    if args.out.resolve() != expected_out:
        parser.error(f"--out must be the frozen campaign path {expected_out}")
    if args.markdown_out.resolve() != expected_markdown:
        parser.error(
            f"--markdown-out must be the frozen campaign path {expected_markdown}"
        )
    return args


def frozen_evidence_summary() -> dict[str, Any]:
    expected = {
        str(RUNNER_PATH): RUNNER_SHA256,
        str(PREREGISTRATION_PATH): PREREGISTRATION_SHA256,
        str(FORMAL_COMPONENT_PATH): FORMAL_COMPONENT_SHA256,
        str(COUNTER_COMPONENT_PATH): COUNTER_COMPONENT_SHA256,
    }
    actual = {path: sha256(Path(path)) for path in expected}
    if actual != expected:
        raise ValueError(
            "frozen runner/preregistration/component identity mismatch: "
            f"expected={expected}, actual={actual}"
        )
    formal = load_json(FORMAL_COMPONENT_PATH)
    counter = load_json(COUNTER_COMPONENT_PATH)
    formal_checks = {
        "passed": formal.get("passed") is True,
        "component_exactness_and_timing_pass": (
            formal.get("component_exactness_and_timing_pass") is True
        ),
        "mean_relative_improvement_gate": (
            isinstance(formal.get("mean_relative_improvement"), (int, float))
            and isinstance(
                formal.get("required_mean_relative_improvement"), (int, float)
            )
            and formal["mean_relative_improvement"]
            >= formal["required_mean_relative_improvement"]
        ),
    }
    counter_aggregate = counter.get("aggregate")
    aggregate = counter_aggregate if isinstance(counter_aggregate, dict) else {}
    counter_checks = {
        "passed": counter.get("passed") is True,
        "all_cards_passed": aggregate.get("all_cards_passed") is True,
        "all_full_path_traces_passed": (
            aggregate.get("all_full_path_traces_passed") is True
        ),
        "all_w2_names_and_counts_identical": (
            aggregate.get("all_w2_names_and_counts_identical") is True
        ),
        "all_gather_names_and_counts_identical": (
            aggregate.get("all_gather_names_and_counts_identical") is True
        ),
        "all_profiles_zero_spill_proxies": (
            aggregate.get("all_profiles_zero_spill_proxies") is True
        ),
    }
    if not all(formal_checks.values()) or not all(counter_checks.values()):
        raise ValueError("frozen component evidence no longer passes")
    return {
        "checksums": actual,
        "formal_component_checks": formal_checks,
        "counter_component_checks": counter_checks,
        "passed": True,
    }


def main() -> int:
    args = parse_args()
    full_mode = args.b2 is not None and args.a2 is not None
    seal_path = CAMPAIGN_ROOT / (
        "full-analysis.seal.json" if full_mode else "phase1-analysis.seal.json"
    )
    stdout_path = CAMPAIGN_ROOT / (
        "full-analysis.stdout" if full_mode else "phase1-analysis.stdout"
    )
    campaign_lock_handle = (CAMPAIGN_ROOT / ".campaign.lock").open("a+")
    try:
        fcntl.flock(
            campaign_lock_handle.fileno(),
            fcntl.LOCK_EX | fcntl.LOCK_NB,
        )
    except BlockingIOError as error:
        raise ValueError("a campaign runner or analyzer is already active") from error
    seal_path.unlink(missing_ok=True)
    frozen_evidence = frozen_evidence_summary()
    runs = {
        "A1": run_summary("A1-control", args.a1, "control"),
        "B1": run_summary("B1-candidate", args.b1, "candidate"),
    }
    if full_mode:
        runs["B2"] = run_summary("B2-candidate", args.b2, "candidate")
        runs["A2"] = run_summary("A2-control", args.a2, "control")

    campaign_ledger = campaign_ledger_summary(runs, full_mode)
    campaign_prefix_chain_pass = (
        campaign_ledger["passed"]
        if not full_mode
        else bool(
            campaign_ledger["phase1_binding"]
            and campaign_ledger["phase1_binding"]["passed"]
        )
    )
    phase1_sequence = sequence_summary({"A1": runs["A1"], "B1": runs["B1"]})
    full_sequence = sequence_summary(runs) if full_mode else None
    pairs = {"B1_vs_A1": paired(runs["A1"], runs["B1"])}
    if full_mode:
        pairs["B2_vs_A2"] = paired(runs["A2"], runs["B2"])

    teacher_paths = {run["exactness"]["teacher"] for run in runs.values()}
    repository_source_commits = {
        key: run["identity"]["source_commits"]["repository"]
        for key, run in runs.items()
    }
    phase1_repository_source_commit_match = (
        repository_source_commits["A1"] is not None
        and repository_source_commits["A1"] == repository_source_commits["B1"]
    )
    all_repository_source_commits_match = (
        all(value is not None for value in repository_source_commits.values())
        and len(set(repository_source_commits.values())) == 1
    )
    phase1_gates = {
        "a1_quality_and_honesty": runs["A1"]["quality_and_honesty_pass"],
        "b1_quality_and_honesty": runs["B1"]["quality_and_honesty_pass"],
        "a1_b1_same_canonical_teacher": (
            runs["A1"]["exactness"]["teacher"] == runs["B1"]["exactness"]["teacher"]
        ),
        "a1_b1_same_repository_source_commit": (phase1_repository_source_commit_match),
        "a1_b1_fresh_services_in_order_with_idle_gap": (phase1_sequence["passed"]),
        "frozen_campaign_prefix_hash_chain": campaign_prefix_chain_pass,
        **pairs["B1_vs_A1"]["gates"],
    }
    phase1_pass = all(phase1_gates.values())
    if full_mode and not phase1_pass:
        raise ValueError(
            "B2/A2 artifacts are impermissible because the frozen phase-1 "
            "A1/B1 gate did not pass"
        )

    combined_exactness: dict[str, Any] | None = None
    if args.all_vs_teacher is not None and args.cross_leg is not None:
        all_expected = [runs["A1"]["bench_path"], runs["B1"]["bench_path"]]
        cross_expected = [runs["B1"]["bench_path"]]
        if full_mode:
            all_expected.extend([runs["B2"]["bench_path"], runs["A2"]["bench_path"]])
            cross_expected.extend([runs["B2"]["bench_path"], runs["A2"]["bench_path"]])
        all_vs_teacher = exactness_bundle(
            args.all_vs_teacher,
            runs["A1"]["exactness"]["teacher"],
            all_expected,
        )
        cross_leg = exactness_bundle(
            args.cross_leg,
            runs["A1"]["bench_path"],
            cross_expected,
        )
        combined_exactness = {
            "all_vs_teacher": all_vs_teacher,
            "cross_leg": cross_leg,
            "passed": all_vs_teacher["passed"] and cross_leg["passed"],
            "required_as_gate": full_mode,
        }

    full_abba_causal_pass: bool | None = None
    strict_preregistered_record_pass: bool | None = None
    full_gates: dict[str, bool] | None = None
    record_gates: dict[str, bool] | None = None
    candidate_lower: float | None = None
    control_lower: float | None = None
    if full_mode:
        candidate_lower = min(
            runs["B1"]["headline_tok_s"], runs["B2"]["headline_tok_s"]
        )
        control_lower = min(runs["A1"]["headline_tok_s"], runs["A2"]["headline_tok_s"])
        full_gates = {
            "phase1_pass": phase1_pass,
            "b2_quality_and_honesty": runs["B2"]["quality_and_honesty_pass"],
            "a2_quality_and_honesty": runs["A2"]["quality_and_honesty_pass"],
            "all_legs_same_canonical_teacher": len(teacher_paths) == 1,
            "all_legs_same_repository_source_commit": (
                all_repository_source_commits_match
            ),
            "combined_and_cross_leg_exactness": bool(
                combined_exactness and combined_exactness["passed"]
            ),
            "fresh_services_in_abba_order_with_idle_gaps": bool(
                full_sequence and full_sequence["passed"]
            ),
            "frozen_four_leg_campaign_hash_chain": campaign_ledger["passed"],
            **{
                f"b2_vs_a2_{name}": value
                for name, value in pairs["B2_vs_A2"]["gates"].items()
            },
            "candidate_lower_start_beats_control_lower_start": (
                candidate_lower > control_lower
            ),
        }
        full_abba_causal_pass = all(full_gates.values())
        record_gates = {
            "full_abba_causal_pass": full_abba_causal_pass,
            "candidate_lower_start_strictly_beats_record_floor": (
                candidate_lower > RECORD_FLOOR_TOK_S
            ),
        }
        strict_preregistered_record_pass = all(record_gates.values())

    if full_mode:
        if strict_preregistered_record_pass:
            disposition = "record_candidate"
        elif full_abba_causal_pass:
            disposition = "exact_reproducible_candidate_below_record_floor"
        else:
            disposition = "negative_or_inconclusive_stop"
    else:
        disposition = (
            "phase1_pass_continue_to_full_abba" if phase1_pass else "phase1_failed_stop"
        )

    failed_phase1_gates = [name for name, passed in phase1_gates.items() if not passed]
    failed_full_gates = (
        []
        if full_gates is None
        else [name for name, passed in full_gates.items() if not passed]
    )
    failed_record_gates = (
        []
        if record_gates is None
        else [name for name, passed in record_gates.items() if not passed]
    )
    result = {
        "experiment": "laguna-m8-routed-w1-n128-crossover",
        "analysis_mode": "full_abba" if full_mode else "phase1_a1_b1",
        "order": [run["label"] for run in runs.values()],
        "eligible": strict_preregistered_record_pass is True,
        "failed_gates": {
            "phase1": failed_phase1_gates,
            "full_abba": failed_full_gates,
            "record": failed_record_gates,
        },
        "thresholds": {
            "prompt_count": PROMPT_COUNT,
            "minimum_candidate_row_wins": MIN_ROW_WINS,
            "minimum_aggregate_cycle_saving_ms": MIN_CYCLE_SAVING_MS,
            "maximum_absolute_acceptance_rate_delta": (MAX_ACCEPTANCE_RATE_DELTA),
            "record_floor_tok_s_strictly_greater_than": RECORD_FLOOR_TOK_S,
            "speculation_vector_identity_required": False,
        },
        "record_anchor": {
            "record_id": RECORD_ID,
            "tok_s": RECORD_FLOOR_TOK_S,
            "candidate_must_be_strictly_greater": True,
        },
        "frozen_component_and_preregistration_evidence": frozen_evidence,
        "frozen_run_identity": {
            "model": CANONICAL_MODEL,
            "seed": CANONICAL_SEED,
            "max_tokens": CANONICAL_MAX_TOKENS,
            "prompt_count": PROMPT_COUNT,
            "return_token_ids": True,
            "enable_thinking": False,
            "suite_id": CANONICAL_SUITE_ID,
            "suite_version": CANONICAL_SUITE_VERSION,
            "suite_path": CANONICAL_SUITE_REL,
            "runner_path": str(RUNNER_PATH),
            "runner_sha256": RUNNER_SHA256,
            "analyzer_path": str(ANALYZER_PATH),
            "analyzer_sha256": sha256(ANALYZER_PATH),
            "xpu_smi_version_sha256": XPU_SMI_VERSION_SHA256,
            "vllm_commit": VLLM_COMMIT,
            "kernel_commit": KERNEL_COMMIT,
            "target_revision": TARGET_REVISION,
            "draft_revision": DRAFT_REVISION,
            "target_manifest_files": 27,
            "draft_manifest_files": 5,
            "target_manifest_bytes": 71922378071,
            "draft_manifest_bytes": 2229973769,
            "target_lfs_sha256_files": 15,
            "draft_lfs_sha256_files": 1,
            "target_lfs_bytes": 71907915776,
            "draft_lfs_bytes": 2229962896,
            "ambient_sensitive_environment": "empty_before_runner",
            "campaign_id": CAMPAIGN_ID,
            "campaign_root": str(CAMPAIGN_ROOT),
            "campaign_journal": str(CAMPAIGN_JOURNAL),
            "campaign_genesis_sha256": CAMPAIGN_GENESIS_SHA256,
            "runtime_versions": {
                key: IDENTITY_FIXED_KEYS[key]
                for key in (
                    "torch",
                    "vllm",
                    "transformers",
                    "vllm-xpu-kernels",
                    "triton-xpu",
                )
            },
        },
        "runs": runs,
        "campaign_ledger": campaign_ledger,
        "phase1_sequence": phase1_sequence,
        "full_sequence": full_sequence,
        "repository_source_commits": repository_source_commits,
        "all_supplied_legs_same_repository_source_commit": (
            all_repository_source_commits_match
        ),
        "pairs": pairs,
        "phase1_gates": phase1_gates,
        "phase1_pass": phase1_pass,
        "combined_exactness": combined_exactness,
        "full_abba_gates": full_gates,
        "record_gates": record_gates,
        "full_abba_causal_pass": full_abba_causal_pass,
        "candidate_lower_start_tok_s": candidate_lower,
        "control_lower_start_tok_s": control_lower,
        "candidate_lower_delta_from_record_tok_s": (
            None if candidate_lower is None else candidate_lower - RECORD_FLOOR_TOK_S
        ),
        "strict_preregistered_record_pass": strict_preregistered_record_pass,
        "disposition": disposition,
    }

    markdown = [
        "# Laguna routed-W1 N64/N128 crossover result",
        "",
        f"- Analysis mode: `{result['analysis_mode']}`",
        f"- Disposition: `{disposition}`",
        "",
        "| Leg | Treatment | Headline tok/s | Mean | p10 | Cycle ms | "
        "Drafts | Accepted | Acceptance |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key, run in runs.items():
        metrics = run["metrics"]
        speculation = metrics["speculation"]
        markdown.append(
            f"| {key} | {run['label']} | {run['headline_tok_s']:.6f} | "
            f"{run['mean_tok_s']:.6f} | {run['p10_tok_s']:.6f} | "
            f"{metrics['aggregate_cycle_ms']:.6f} | "
            f"{speculation['draft_cycles']} | "
            f"{speculation['accepted_tokens']} | "
            f"{speculation['acceptance_rate']:.6%} |"
        )
    markdown.extend(
        [
            "",
            "| Pair | Headline delta | Row wins | Median paired delta | "
            "Cycle saving | Acceptance delta | Pair pass |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for name, pair in pairs.items():
        markdown.append(
            f"| {name} | {pair['headline_delta_pct']:+.4f}% | "
            f"{pair['candidate_row_wins']}/{PROMPT_COUNT} | "
            f"{pair['median_paired_delta_pct']:+.4f}% | "
            f"{pair['aggregate_cycle_saving_ms']:+.6f} ms | "
            f"{pair['acceptance_rate_delta_percentage_points']:+.6f} pp | "
            f"{pair['pass']} |"
        )
    markdown.extend(
        [
            "",
            "## Quality and freshness",
            "",
            "| Leg | Fresh/cache-zero | Bench identity | Stack identity | "
            "Teacher exact | Long-next | Rollover | Clean pre-metrics | "
            "Fresh service/idle | Overall |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for key, run in runs.items():
        exactness = run["exactness"]
        markdown.append(
            f"| {key} | {run['freshness']['passed']} | "
            f"{run['benchmark_run_identity']['passed']} | "
            f"{run['identity']['passed']} | "
            f"{exactness['exact_count']}/{exactness['total']} | "
            f"{exactness['long_then_next']['passed']} | "
            f"{exactness['rollover']['exact_count']}/"
            f"{exactness['rollover']['count']} | "
            f"{run['metrics']['clean_before_pass']} | "
            f"{run['operational']['passed']} | "
            f"{run['quality_and_honesty_pass']} |"
        )
    markdown.extend(["", "## Accepted-token position histograms", ""])
    for key, run in runs.items():
        histogram = run["metrics"]["speculation"]["accepted_by_position"]
        markdown.append(f"- {key}: `{histogram}`")
    markdown.extend(["", "## Fresh-service sequence", ""])
    active_sequence = full_sequence if full_sequence is not None else phase1_sequence
    for gap in active_sequence["adjacent_idle_gaps"]:
        markdown.append(
            f"- {gap['previous']} -> {gap['next']}: "
            f"{gap['idle_gap_seconds']:.0f} s idle"
        )
    markdown.extend(
        [
            "",
            "## Gates",
            "",
            f"- Phase-one pass: `{phase1_pass}`",
            f"- Full ABBA causal pass: `{full_abba_causal_pass}`",
            f"- Strict record pass: `{strict_preregistered_record_pass}`",
            f"- Eligible: `{result['eligible']}`",
            f"- Frozen campaign hash chain: `{campaign_ledger['passed']}`",
            (
                "- Final campaign chain SHA-256: "
                f"`{campaign_ledger['final_chain_sha256']}`"
            ),
            f"- Record anchor: `{RECORD_ID}`",
            f"- Record floor: `>{RECORD_FLOOR_TOK_S:.15f} tok/s`",
            (
                "- Repository source commit identical across supplied legs: "
                f"`{all_repository_source_commits_match}`"
            ),
            (
                "- Combined/cross-leg exactness: "
                f"`{None if combined_exactness is None else combined_exactness['passed']}`"
            ),
            (
                "- Speculation-vector identity is recorded but is not a gate; "
                "absolute acceptance-rate drift must be `<=0.001`."
            ),
            "",
        ]
    )
    final_campaign_ledger = campaign_ledger_summary(runs, full_mode)
    publication_checks = {
        "campaign_ledger_still_passes": final_campaign_ledger["passed"],
        "campaign_journal_unchanged_during_analysis": (
            final_campaign_ledger["journal_sha256"] == campaign_ledger["journal_sha256"]
        ),
        "campaign_chain_unchanged_during_analysis": (
            final_campaign_ledger["final_chain_sha256"]
            == campaign_ledger["final_chain_sha256"]
        ),
        "all_leg_benchmarks_unchanged_during_analysis": all(
            sha256(Path(run["bench_path"])) == run["bench_sha256"]
            for run in runs.values()
        ),
        "combined_exactness_reports_unchanged_during_analysis": (
            combined_exactness is None
            or (
                sha256(Path(combined_exactness["all_vs_teacher"]["path"]))
                == combined_exactness["all_vs_teacher"]["sha256"]
                and sha256(Path(combined_exactness["cross_leg"]["path"]))
                == combined_exactness["cross_leg"]["sha256"]
            )
        ),
    }
    if not all(publication_checks.values()):
        raise ValueError(
            f"evidence changed before atomic analysis publication: {publication_checks}"
        )
    result["campaign_ledger"] = final_campaign_ledger
    result["publication_evidence_checks"] = publication_checks
    result["publication_seal"] = {
        "required": True,
        "path": str(seal_path),
        "submission_requires_eligible_true": True,
    }
    json_text = json.dumps(result, indent=2) + "\n"
    markdown_text = "\n".join(markdown)
    atomic_write_text(args.out, json_text)
    atomic_write_text(args.markdown_out, markdown_text)
    print(json_text, end="")
    sys.stdout.flush()
    stdout_checks = {
        "stdout_path_exists": stdout_path.is_file(),
        "stdout_matches_analysis_json": (
            stdout_path.is_file() and sha256(stdout_path) == sha256(args.out)
        ),
    }
    if not all(stdout_checks.values()):
        raise ValueError(f"analysis stdout was not durably captured: {stdout_checks}")
    seal = {
        "valid": True,
        "analysis_mode": result["analysis_mode"],
        "eligible": result["eligible"],
        "phase1_pass": result["phase1_pass"],
        "full_abba_causal_pass": result["full_abba_causal_pass"],
        "strict_preregistered_record_pass": (
            result["strict_preregistered_record_pass"]
        ),
        "analysis_json_path": str(args.out.resolve()),
        "analysis_json_sha256": sha256(args.out),
        "analysis_markdown_path": str(args.markdown_out.resolve()),
        "analysis_markdown_sha256": sha256(args.markdown_out),
        "analysis_stdout_path": str(stdout_path.resolve()),
        "analysis_stdout_sha256": sha256(stdout_path),
        "analyzer_path": str(ANALYZER_PATH),
        "analyzer_sha256": sha256(ANALYZER_PATH),
        "runner_path": str(RUNNER_PATH),
        "runner_sha256": RUNNER_SHA256,
        "campaign_journal_path": str(CAMPAIGN_JOURNAL),
        "campaign_journal_sha256": final_campaign_ledger["journal_sha256"],
        "campaign_final_chain_sha256": (final_campaign_ledger["final_chain_sha256"]),
        "publication_evidence_checks": publication_checks,
        "stdout_checks": stdout_checks,
        "sealed_utc": datetime.now(timezone.utc).isoformat(),
    }
    atomic_write_text(seal_path, json.dumps(seal, indent=2) + "\n")
    fcntl.flock(campaign_lock_handle.fileno(), fcntl.LOCK_UN)
    campaign_lock_handle.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
