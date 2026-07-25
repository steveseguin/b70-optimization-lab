#!/usr/bin/env python3
"""CPU-only tests for the TP4 context-KV runtime analyzer contract."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

import analyze_laguna_dflash_context_kv_runtime_gate as gate
import run_laguna_dflash_context_kv_runtime_arm as arm


def trace_tensor(
    rank: int,
    shape: list[int],
    *,
    dtype: str,
    pointer: int,
) -> dict:
    elements = 1
    for dimension in shape:
        elements *= dimension
    itemsize = 2 if dtype == "torch.bfloat16" else 8
    stride = []
    running = 1
    for dimension in reversed(shape):
        stride.append(running)
        running *= dimension
    return {
        "data_ptr": pointer,
        "device": f"xpu:{rank}",
        "dtype": dtype,
        "nbytes": elements * itemsize,
        "sha256": hashlib.sha256(f"{rank}:{shape}:{dtype}".encode()).hexdigest(),
        "shape": shape,
        "storage_offset": 0,
        "stride": list(reversed(stride)),
    }


def write_lifecycle_trace(treatment: str, arm_root: Path) -> None:
    trace = arm_root / "dflash-lifecycle"
    trace.mkdir(parents=True, mode=0o700)
    for rank in range(4):
        workspace = [
            {
                key: value
                for key, value in trace_tensor(
                    rank,
                    shape,
                    dtype="torch.bfloat16",
                    pointer=10000 + rank * 100 + offset,
                ).items()
                if key
                in {
                    "data_ptr",
                    "device",
                    "dtype",
                    "shape",
                    "storage_offset",
                    "stride",
                }
            }
            for offset, shape in enumerate(
                (
                    [6, 1, 3072],
                    [6, 1, 1536],
                    [2, 6, 1, 6, 128],
                    [6, 1, 6, 128],
                )
            )
        ]
        for index in range(2):
            projection = (
                {
                    "branch": "workspace",
                    "capturing": False,
                    "workspace_reused": bool(index),
                    "workspace_signatures": workspace,
                }
                if treatment == "candidate"
                else {
                    "branch": "incumbent",
                    "capturing": False,
                    "workspace_reused": None,
                    "workspace_signatures": None,
                }
            )
            event = {
                "schema": "laguna-dflash-context-kv-runtime-trace-v1",
                "rank": rank,
                "event_index": index,
                "selector_enabled": treatment == "candidate",
                "num_ctx": 1,
                "context_states": trace_tensor(
                    rank,
                    [1, 3072],
                    dtype="torch.bfloat16",
                    pointer=20000 + rank,
                ),
                "context_positions": trace_tensor(
                    rank,
                    [1],
                    dtype="torch.int64",
                    pointer=30000 + rank,
                ),
                "slot_mapping_signatures": [
                    trace_tensor(
                        rank,
                        [1],
                        dtype="torch.int64",
                        pointer=40000 + rank,
                    )
                ],
                "expected_cache_update_count": 6,
                "projection": projection,
                "precompute_returned": True,
            }
            path = trace / f"rank{rank}-event{index:05d}.json"
            path.write_text(json.dumps(event) + "\n", encoding="utf-8")


def valid_driver(treatment: str, root: Path) -> dict:
    selector = 1 if treatment == "candidate" else 0
    prompt_ids = [1, 2, 3]
    token_ids = list(range(arm.MAX_TOKENS))
    text = "frozen output"
    rpc = arm.RPC_DIRS[treatment]
    evidence = root / treatment / "evidence"
    trace = root / treatment / "dflash-lifecycle"
    trace.mkdir(parents=True, mode=0o700)
    (trace / "witness.json").write_text("{}\n", encoding="utf-8")
    lifecycle_manifest = arm.file_manifest(trace)
    return {
        "schema": arm.SCHEMA,
        "treatment": treatment,
        "selector": selector,
        "offline_only": True,
        "nonbenchmark": True,
        "single_chat_call": True,
        "worker_identity_calls": 1,
        "warmup_calls": 0,
        "retry_count": 0,
        "prompt_id": arm.PROMPT_ID,
        "prompt_sha256": hashlib.sha256(arm.PROMPT.encode()).hexdigest(),
        "prompt_token_ids": prompt_ids,
        "prompt_token_ids_sha256": arm.digest_json(prompt_ids),
        "max_tokens": arm.MAX_TOKENS,
        "seed": arm.SEED,
        "ignore_eos": True,
        "chat_template_kwargs": {"enable_thinking": False},
        "model": str(arm.TARGET_MODEL),
        "draft_model": str(arm.DRAFT_MODEL),
        "target_revision": arm.TARGET_REVISION,
        "draft_revision": arm.DRAFT_REVISION,
        "model_manifest_sha256": arm.MODEL_MANIFEST_SHA256,
        "engine_config": gate.expected_engine_config(),
        "compilation_config": gate.expected_compilation_config(),
        "speculative_config": gate.expected_speculative_config(),
        "environment": arm.frozen_environment(treatment, evidence, trace, rpc),
        "runtime": {
            "vllm_commit": arm.VLLM_COMMIT,
            "vllm_root": (
                "/home/steve/src/"
                "laguna-vllm-dflash-persistent-metadata-20260725"
            ),
            "vllm_module": (
                "/home/steve/src/laguna-vllm-dflash-persistent-metadata-"
                "20260725/vllm/__init__.py"
            ),
        },
        "num_cached_tokens": 0,
        "finish_reason": "length",
        "token_ids": token_ids,
        "token_ids_sha256": arm.digest_json(token_ids),
        "text": text,
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "usage": {
            "prompt_tokens": len(prompt_ids),
            "completion_tokens": arm.MAX_TOKENS,
            "cached_tokens": 0,
        },
        "evidence_dir": str(evidence),
        "evidence_canonical_sha256": "a" * 64,
        "evidence_file_sha256": "b" * 64,
        "lifecycle_trace_dir": str(trace),
        "lifecycle_trace_manifest": lifecycle_manifest,
        "lifecycle_trace_manifest_sha256": arm.digest_json(lifecycle_manifest),
        "rpc_dir": str(rpc),
        "worker_identities": [
            {
                "global_rank": rank,
                "global_world_size": 4,
                "distributed_backend": "xccl",
                "tp_rank": rank,
                "tp_world_size": 4,
                "xpu_device": rank,
                "xpu_device_name": "Intel(R) Arc(TM) Pro B70 Graphics",
                "model_class": "LagunaForCausalLM",
            }
            for rank in range(4)
        ],
    }


def test_valid_driver_accepts_both_treatments(tmp_path: Path) -> None:
    for treatment in ("control", "candidate"):
        driver = valid_driver(treatment, tmp_path)
        assert (
            gate.validate_driver(treatment, tmp_path / treatment, driver) is driver
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("selector", 7),
        ("num_cached_tokens", 1),
        ("warmup_calls", 1),
        ("retry_count", 1),
        ("finish_reason", "stop"),
        ("text_sha256", "0" * 64),
        ("token_ids_sha256", "0" * 64),
    ],
)
def test_driver_tamper_fails(
    tmp_path: Path, field: str, value: object
) -> None:
    driver = valid_driver("candidate", tmp_path)
    driver[field] = value
    with pytest.raises(ValueError):
        gate.validate_driver("candidate", tmp_path / "candidate", driver)


def test_unrelated_environment_tamper_fails(tmp_path: Path) -> None:
    driver = valid_driver("candidate", tmp_path)
    driver["environment"]["CCL_TOPO_P2P_ACCESS"] = "0"
    with pytest.raises(ValueError):
        gate.validate_driver("candidate", tmp_path / "candidate", driver)


def test_missing_environment_fails(tmp_path: Path) -> None:
    driver = valid_driver("control", tmp_path)
    del driver["environment"]["VLLM_XPU_EXACT_SPEC_ATTN"]
    with pytest.raises(ValueError):
        gate.validate_driver("control", tmp_path / "control", driver)


def test_timing_field_fails(tmp_path: Path) -> None:
    driver = valid_driver("control", tmp_path)
    driver["usage"]["elapsed_s"] = 1.0
    with pytest.raises(ValueError, match="usage drift|timing"):
        gate.validate_driver("control", tmp_path / "control", driver)


def test_normalization_allows_only_frozen_treatment_delta(tmp_path: Path) -> None:
    control = valid_driver("control", tmp_path)
    candidate = valid_driver("candidate", tmp_path)
    assert gate.normalize_treatment(control) == gate.normalize_treatment(candidate)
    candidate["engine_config"]["gpu_memory_utilization"] = 0.89
    assert gate.normalize_treatment(control) != gate.normalize_treatment(candidate)


def test_recursive_timing_rejection() -> None:
    with pytest.raises(ValueError, match="tok_s"):
        gate.reject_timing_fields({"nested": [{"tok_s": 99.0}]})


def test_teacher_prefix_is_frozen() -> None:
    tokens, identity = gate.teacher_prefix()
    assert len(tokens) == arm.MAX_TOKENS
    assert identity["sha256"] == gate.TEACHER_SHA256
    assert identity["prefix_sha256"] == arm.digest_json(tokens)


def test_tooling_has_no_model_timing_or_submission_path() -> None:
    tool_root = Path(__file__).resolve().parent
    driver_source = (tool_root / arm.__file__).read_text(encoding="utf-8")
    runner_source = (
        tool_root / "run_laguna_dflash_context_kv_runtime_gate.sh"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "perf_counter",
        "monotonic(",
        "bench-openai-realistic-suite",
        "submit_localmaxxing",
        "curl ",
    ):
        assert forbidden not in driver_source
        assert forbidden not in runner_source


def test_environment_allowlist_is_complete(tmp_path: Path) -> None:
    environment = arm.frozen_environment(
        "candidate",
        tmp_path / "evidence",
        tmp_path / "trace",
        tmp_path / "rpc",
    )
    assert set(environment) == set(arm.RECORDED_ENVIRONMENT)
    assert environment["VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE"] == "1"
    assert environment["PYTHONPATH"].split(":") == [
        (
            "/home/steve/llm-optimizations/"
            "experiments/laguna-s-2.1-xpu-b70/tools"
        ),
        "/home/steve/src/laguna-vllm-dflash-persistent-metadata-20260725",
        "/home/steve/src/deepseek-v4-xpu-kernels-record-4772f727",
    ]
    control = copy.deepcopy(environment)
    control["VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE"] = "0"
    assert control == arm.frozen_environment(
        "control",
        tmp_path / "evidence",
        tmp_path / "trace",
        tmp_path / "rpc",
    )


def test_output_accounting_accepts_equal_terminal_overrun() -> None:
    output = [10, 11, 12, 13]
    drivers = {
        treatment: {"token_ids": output}
        for treatment in ("control", "candidate")
    }
    evidence = {
        treatment: {
            "rank_events": {
                str(rank): [
                    {"emitted_ids": [11, 12]},
                    {"emitted_ids": [13, 99]},
                ]
                for rank in range(4)
            }
        }
        for treatment in ("control", "candidate")
    }
    assert gate.validate_output_accounting(drivers, evidence) == {
        treatment: {
            str(rank): {"ids": [99], "source_event_index": 1}
            for rank in range(4)
        }
        for treatment in ("control", "candidate")
    }


def test_output_accounting_rejects_public_prefix_drift() -> None:
    output = [10, 11, 12]
    drivers = {
        treatment: {"token_ids": output}
        for treatment in ("control", "candidate")
    }
    evidence = {
        treatment: {
            "rank_events": {
                str(rank): [{"emitted_ids": [11, 12]}]
                for rank in range(4)
            }
        }
        for treatment in ("control", "candidate")
    }
    evidence["candidate"]["rank_events"]["2"][0]["emitted_ids"] = [11, 13]
    with pytest.raises(ValueError, match="not an exact prefix"):
        gate.validate_output_accounting(drivers, evidence)


def test_output_accounting_rejects_terminal_overrun_drift() -> None:
    output = [10, 11, 12]
    drivers = {
        treatment: {"token_ids": output}
        for treatment in ("control", "candidate")
    }
    evidence = {
        treatment: {
            "rank_events": {
                str(rank): [{"emitted_ids": [11, 12, 99]}]
                for rank in range(4)
            }
        }
        for treatment in ("control", "candidate")
    }
    evidence["candidate"]["rank_events"]["3"][0]["emitted_ids"][-1] = 98
    with pytest.raises(ValueError, match="overrun"):
        gate.validate_output_accounting(drivers, evidence)


def test_output_accounting_rejects_tail_spanning_multiple_events() -> None:
    output = [10, 11, 12]
    drivers = {
        treatment: {"token_ids": output}
        for treatment in ("control", "candidate")
    }
    evidence = {
        treatment: {
            "rank_events": {
                str(rank): [
                    {"emitted_ids": [11, 12]},
                    {"emitted_ids": [90]},
                    {"emitted_ids": [91]},
                ]
                for rank in range(4)
            }
        }
        for treatment in ("control", "candidate")
    }
    with pytest.raises(ValueError, match="not confined to the final"):
        gate.validate_output_accounting(drivers, evidence)


def test_output_accounting_rejects_overrun_beyond_dflash_depth() -> None:
    output = [10, 11, 12]
    drivers = {
        treatment: {"token_ids": output}
        for treatment in ("control", "candidate")
    }
    evidence = {
        treatment: {
            "rank_events": {
                str(rank): [
                    {"emitted_ids": [11]},
                    {"emitted_ids": [12, 90, 91, 92, 93, 94, 95, 96, 97]},
                ]
                for rank in range(4)
            }
        }
        for treatment in ("control", "candidate")
    }
    with pytest.raises(ValueError, match="seven-token speculative depth"):
        gate.validate_output_accounting(drivers, evidence)


@pytest.mark.parametrize("treatment", ["control", "candidate"])
def test_lifecycle_trace_accepts_bounded_real_precompute(
    tmp_path: Path,
    treatment: str,
) -> None:
    arm_root = tmp_path / treatment
    write_lifecycle_trace(treatment, arm_root)

    result = gate.validate_lifecycle_trace(treatment, arm_root)

    assert result["counts"] == {rank: 2 for rank in range(4)}
    assert result["returned_precompute_calls"] == {
        rank: 2 for rank in range(4)
    }
    expected_reuse = 1 if treatment == "candidate" else 0
    assert result["reused_precompute_calls"] == {
        rank: expected_reuse for rank in range(4)
    }


def test_lifecycle_trace_rejects_unreturned_precompute(tmp_path: Path) -> None:
    arm_root = tmp_path / "candidate"
    write_lifecycle_trace("candidate", arm_root)
    path = arm_root / "dflash-lifecycle/rank2-event00001.json"
    event = json.loads(path.read_text(encoding="utf-8"))
    event["precompute_returned"] = False
    path.write_text(json.dumps(event) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="malformed lifecycle"):
        gate.validate_lifecycle_trace("candidate", arm_root)


def test_lifecycle_trace_rejects_partial_mapping(tmp_path: Path) -> None:
    arm_root = tmp_path / "candidate"
    write_lifecycle_trace("candidate", arm_root)
    path = arm_root / "dflash-lifecycle/rank1-event00000.json"
    event = json.loads(path.read_text(encoding="utf-8"))
    event["expected_cache_update_count"] = 5
    path.write_text(json.dumps(event) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="expected cache-update"):
        gate.validate_lifecycle_trace("candidate", arm_root)
