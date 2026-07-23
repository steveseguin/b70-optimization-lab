#!/usr/bin/env python3
"""Analyze the preregistered Laguna BF16 router-topK crossover."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any


METRIC = "tok_s_1_100_after_ttft"
PROMPT_COUNT = 13
MIN_ROW_WINS = 9
MIN_CYCLE_SAVING_MS = 0.15
MAX_ACCEPTANCE_RATE_DELTA = 0.001
RECORD_FLOOR_TOK_S = 33.438926675602126
CANONICAL_MODEL = "laguna-s-2.1-int4"
CANONICAL_SEED = 1
CANONICAL_MAX_TOKENS = 512
CANONICAL_SUITE_ID = "laguna-s-2.1-realistic-cold-v1"
CANONICAL_SUITE_VERSION = 1
CANONICAL_SUITE_REL = "experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json"
REPO_ROOT = Path("/home/steve/llm-optimizations")
RUNNER_PATH = REPO_ROOT / (
    "experiments/laguna-s-2.1-xpu-b70/tools/run_router_topk_crossover_leg.sh"
)
RUNNER_SHA256 = "c1a58a0bec4869190183a32061b1f2c24f96e79a6ee69900bf2310a19b6087d2"
XPU_SMI_VERSION_SHA256 = (
    "d14b356677a57006a19e1e5b4aa45cada8fc0c553cd214ac76ad420ef5bdb4ab"
)
VLLM_COMMIT = "689ee3643f320e4a10c621ddd829620bc2f5b3b3"
KERNEL_COMMIT = "af6811818ef797aa86aef51bda15ae9c49040f7b"
TARGET_REVISION = "4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb"
DRAFT_REVISION = "5e07c246915c86dc6920fead03d019989224f2ba"
TARGET_MODEL_PATH = (
    "/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/int4"
)
DRAFT_MODEL_PATH = (
    "/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/dflash-int4"
)
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
    "target_lfs_sha256_files": "15",
    "draft_lfs_sha256_files": "1",
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
    "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE": "0",
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
    ): "bd337e35e8c5735f7e7ab2e4ff97835931c86a6daa51241329c3997a6b61f5b4",
    (
        "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/"
        "vllm_xpu_kernels/_xpu_C.abi3.so"
    ): "625af4bbe792effde9f2f54c319f807a5c49b9756be313f9307d90da9ff5149e",
    (
        "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/"
        "vllm_xpu_kernels/_moe_C.abi3.so"
    ): "0057b266d567731a9f9f592cefd9103bbf027ebb83c876d26c17ffb09994a3a0",
    (
        "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/"
        "vllm_xpu_kernels/libgrouped_gemm_xe_2.so"
    ): "78a7218de45ee46b3734dc977c0d6115607ff7536706c0be2d4728b4ca2c40be",
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


def resolved(value: str | Path) -> str:
    return str(Path(value).resolve())


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

    expected_keys = {
        **IDENTITY_FIXED_KEYS,
        "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK": (
            "0" if expected_treatment == "control" else "1"
        ),
        "treatment": expected_treatment,
    }
    xpu_smi_version_path = str(path.parent / "xpu-smi-version.txt")
    expected_checksums = {
        **IDENTITY_FIXED_CHECKSUMS,
        xpu_smi_version_path: XPU_SMI_VERSION_SHA256,
    }
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
        "all_fixed_key_values_match": all(key_value_matches.values()),
        "no_duplicate_checksum_paths": all(
            len(values) == 1 for values in checksum_occurrences.values()
        ),
        "all_required_checksums_present_once": all(
            len(checksum_occurrences.get(resolved(checksum_path), [])) == 1
            for checksum_path in expected_checksums
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
    checks = {
        "report_all_exact": exactness.get("all_exact") is True,
        "teacher_path_is_canonical": (
            resolved(exactness.get("teacher", "")) == resolved(TEACHER_PATH)
        ),
        "candidate_path_matches_leg": resolved(candidate.get("candidate", ""))
        == resolved(bench_path),
        **comparison_checks(comparison),
    }
    return {
        "path": str(exactness_path.resolve()),
        "sha256": sha256(exactness_path),
        "teacher": resolved(exactness.get("teacher", "")),
        "candidate": resolved(candidate.get("candidate", "")),
        "checks": checks,
        "passed": all(checks.values()),
        "exact_count": comparison.get("exact_count"),
        "total": comparison.get("total"),
        "long_then_next": comparison.get("long_then_next") or {},
        "rollover": comparison.get("rollover") or {},
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

    freshness = freshness_summary(bench)
    benchmark_identity = benchmark_identity_summary(bench)
    identity = identity_summary(identity_path, expected_treatment)
    exactness = per_leg_exactness(exactness_path, bench_path)
    metrics = metrics_summary(directory)
    quality_checks = {
        "freshness": freshness["passed"],
        "benchmark_run_identity": benchmark_identity["passed"],
        "record_stack_identity": identity["passed"],
        "teacher_exactness": exactness["passed"],
        "clean_pre_suite_metrics": metrics["clean_before_pass"],
        "primary_metric_count_13": primary.get("count") == PROMPT_COUNT,
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
        "headline_tok_s": float(primary["median"]),
        "mean_tok_s": float(primary["mean"]),
        "p10_tok_s": float(primary["p10"]),
        "bench_summary": summary_metrics,
        "metrics": metrics,
        "completion_tokens": sum(int(row["completion_tokens"]) for row in rows),
        "row_metrics": [
            {
                "prompt_id": row["prompt_id"],
                "prompt_sha256": row["prompt_sha256"],
                "prompt_tokens": int(row["prompt_tokens"]),
                "completion_tokens": int(row["completion_tokens"]),
                "cached_tokens": row["cached_tokens"],
                "tok_s": float(row[METRIC]),
            }
            for row in rows
        ],
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
    checks = {
        "all_exact": report.get("all_exact") is True,
        "teacher_path_matches": resolved(report.get("teacher", ""))
        == resolved(expected_teacher),
        "candidate_count_matches": len(candidates) == len(expected_candidates),
        "candidate_paths_match": (
            len(set(actual_candidates)) == len(actual_candidates)
            and set(actual_candidates)
            == {resolved(value) for value in expected_candidates}
        ),
        "every_comparison_exact_13": (
            len(comparison_passes) == len(expected_candidates)
            and all(comparison_passes)
        ),
    }
    return {
        "path": str(path.resolve()),
        "sha256": sha256(path),
        "teacher": resolved(report.get("teacher", "")),
        "candidates": actual_candidates,
        "checks": checks,
        "passed": all(checks.values()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze A1/B1 phase-one evidence or the complete A1/B1/B2/A2 "
            "Laguna router-topK crossover."
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
    return args


def main() -> int:
    args = parse_args()
    full_mode = args.b2 is not None and args.a2 is not None
    runs = {
        "A1": run_summary("A1-control", args.a1, "control"),
        "B1": run_summary("B1-candidate", args.b1, "candidate"),
    }
    if full_mode:
        runs["B2"] = run_summary("B2-candidate", args.b2, "candidate")
        runs["A2"] = run_summary("A2-control", args.a2, "control")

    pairs = {"B1_vs_A1": paired(runs["A1"], runs["B1"])}
    if full_mode:
        pairs["B2_vs_A2"] = paired(runs["A2"], runs["B2"])

    teacher_paths = {run["exactness"]["teacher"] for run in runs.values()}
    phase1_gates = {
        "a1_quality_and_honesty": runs["A1"]["quality_and_honesty_pass"],
        "b1_quality_and_honesty": runs["B1"]["quality_and_honesty_pass"],
        "a1_b1_same_canonical_teacher": (
            runs["A1"]["exactness"]["teacher"] == runs["B1"]["exactness"]["teacher"]
        ),
        **pairs["B1_vs_A1"]["gates"],
    }
    phase1_pass = all(phase1_gates.values())

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
            "combined_and_cross_leg_exactness": bool(
                combined_exactness and combined_exactness["passed"]
            ),
            **{
                f"b2_vs_a2_{name}": value
                for name, value in pairs["B2_vs_A2"]["gates"].items()
            },
            "candidate_lower_start_beats_control_lower_start": (
                candidate_lower > control_lower
            ),
        }
        full_abba_causal_pass = all(full_gates.values())
        strict_preregistered_record_pass = (
            full_abba_causal_pass and candidate_lower > RECORD_FLOOR_TOK_S
        )

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

    result = {
        "experiment": "laguna-m8-bf16-router-topk-crossover",
        "analysis_mode": "full_abba" if full_mode else "phase1_a1_b1",
        "order": [run["label"] for run in runs.values()],
        "thresholds": {
            "prompt_count": PROMPT_COUNT,
            "minimum_candidate_row_wins": MIN_ROW_WINS,
            "minimum_aggregate_cycle_saving_ms": MIN_CYCLE_SAVING_MS,
            "maximum_absolute_acceptance_rate_delta": (MAX_ACCEPTANCE_RATE_DELTA),
            "record_floor_tok_s_strictly_greater_than": RECORD_FLOOR_TOK_S,
            "speculation_vector_identity_required": False,
        },
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
            "xpu_smi_version_sha256": XPU_SMI_VERSION_SHA256,
            "vllm_commit": VLLM_COMMIT,
            "kernel_commit": KERNEL_COMMIT,
            "target_revision": TARGET_REVISION,
            "draft_revision": DRAFT_REVISION,
            "target_manifest_files": 27,
            "draft_manifest_files": 5,
            "target_lfs_sha256_files": 15,
            "draft_lfs_sha256_files": 1,
            "ambient_sensitive_environment": "empty_before_runner",
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
        "pairs": pairs,
        "phase1_gates": phase1_gates,
        "phase1_pass": phase1_pass,
        "combined_exactness": combined_exactness,
        "full_abba_gates": full_gates,
        "full_abba_causal_pass": full_abba_causal_pass,
        "candidate_lower_start_tok_s": candidate_lower,
        "control_lower_start_tok_s": control_lower,
        "candidate_lower_delta_from_record_tok_s": (
            None if candidate_lower is None else candidate_lower - RECORD_FLOOR_TOK_S
        ),
        "strict_preregistered_record_pass": strict_preregistered_record_pass,
        "disposition": disposition,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    markdown = [
        "# Laguna BF16 router-topK crossover result",
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
            "Teacher exact | Long-next | Rollover | Clean pre-metrics | Overall |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
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
            f"{run['quality_and_honesty_pass']} |"
        )
    markdown.extend(["", "## Accepted-token position histograms", ""])
    for key, run in runs.items():
        histogram = run["metrics"]["speculation"]["accepted_by_position"]
        markdown.append(f"- {key}: `{histogram}`")
    markdown.extend(
        [
            "",
            "## Gates",
            "",
            f"- Phase-one pass: `{phase1_pass}`",
            f"- Full ABBA causal pass: `{full_abba_causal_pass}`",
            f"- Strict record pass: `{strict_preregistered_record_pass}`",
            f"- Record floor: `>{RECORD_FLOOR_TOK_S:.15f} tok/s`",
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
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.write_text("\n".join(markdown), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
