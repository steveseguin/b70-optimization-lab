from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

import pytest

import analyze_laguna_m8_inprocess_replay as analyzer


def test_driver_analyzer_and_runner_completion_contract_agree() -> None:
    tools = Path(__file__).parent
    driver_tree = ast.parse(
        (tools / "run_laguna_m8_inprocess_replay_arm.py").read_text()
    )
    max_tokens = [
        node.value.value
        for node in driver_tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "MAX_TOKENS"
            for target in node.targets
        )
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, int)
    ]
    assert max_tokens == [analyzer.COMPLETION_TOKENS]
    runner = (tools / "run_laguna_m8_inprocess_replay.sh").read_text()
    assert f"completion_tokens_per_arm={analyzer.COMPLETION_TOKENS}" in runner


def test_runner_sets_every_driver_required_environment_key() -> None:
    tools = Path(__file__).parent
    driver_tree = ast.parse(
        (tools / "run_laguna_m8_inprocess_replay_arm.py").read_text()
    )
    required: set[str] = set()
    for node in ast.walk(driver_tree):
        dictionaries: list[ast.Dict] = []
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "required"
                for target in node.targets
            )
            and isinstance(node.value, ast.Dict)
        ):
            dictionaries.append(node.value)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "required"
            and node.func.attr == "update"
            and node.args
            and isinstance(node.args[0], ast.Dict)
        ):
            dictionaries.append(node.args[0])
        for dictionary in dictionaries:
            required.update(
                key.value
                for key in dictionary.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            )

    runner = (tools / "run_laguna_m8_inprocess_replay.sh").read_text()
    missing = [
        name
        for name in sorted(required)
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}=", runner) is None
    ]
    assert missing == []


def _environment(arm: str, profile_root: Path) -> dict[str, str]:
    graph = arm == "graph"
    optimized_dflash = arm != "q1"
    values = {
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
        "VLLM_XPU_LAGUNA_M8_CAPTURE_ATTENTION_GRAPHS": "0",
        "VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA": (
            "1" if graph else "0"
        ),
        "VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM": "0",
        "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK": "0",
        "VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION": "0",
        "VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2": ("1" if optimized_dflash else "0"),
        "VLLM_XPU_LAGUNA_M8_GATHER_FINALIZE": "0",
        "VLLM_XPU_LAGUNA_M8_GATHER_SHARDED": "0",
        "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE": "1" if optimized_dflash else "0",
        "VLLM_XPU_LAGUNA_M8_REMOTE_ZERO": "0",
        "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE": ("1" if optimized_dflash else "0"),
        "VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM": "0",
        "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE": ("1" if optimized_dflash else "0"),
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
        values.update(
            {
                "VLLM_XPU_LAGUNA_REPLAY_PROFILE_ROOT": str(profile_root),
                "VLLM_XPU_LAGUNA_REPLAY_PROFILE_SAMPLES": "31",
            }
        )
    return values


def _record(sample: int) -> dict:
    durations = {
        kind: [sample + 1] * count for kind, count in analyzer.SEGMENT_COUNTS.items()
    }
    segment_total = sum(sum(items) for items in durations.values())
    timings = {field: sample + 1 for field in analyzer.TIMING_FIELDS}
    timings.update(
        {
            "capture_replay_host_loop_ns": segment_total,
            "replay_host_total_ns": segment_total + 1,
            "post_replay_synchronize_ns": 1,
            "whole_replay_completion_ns": segment_total + 2,
        }
    )
    return {
        **timings,
        "sample": sample,
        "segment_host_call_ns": durations,
        "segment_host_call_total_ns": {
            kind: sum(items) for kind, items in durations.items()
        },
        "segment_ordered_host_call_ns": [
            [kind, value]
            for kind in ("graph", "collective", "attention", "eager")
            for value in durations[kind]
        ],
    }


def _profile(rank: int) -> dict:
    kinds = ["graph"] * 146 + ["collective"] * 97 + ["attention"] * 48
    return {
        "schema": "laguna-m8-breakable-replay-profile-v1",
        "status": "complete",
        "rank": rank,
        "samples": 31,
        "batch_descriptor": "BatchDescriptor(num_tokens=8)",
        "graphs": 146,
        "eager_breaks": 145,
        "boundary_categories": {"attention": 48, "collective": 97},
        "segment_kind_order_sha256": hashlib.sha256(
            ",".join(kinds).encode()
        ).hexdigest(),
        "records": [_record(sample) for sample in range(31)],
    }


def _arm(arm: str, profile_root: Path, rank_files: dict[str, dict]) -> dict:
    token_ids = list(range(analyzer.COMPLETION_TOKENS))
    kernel_identity = {
        name: {
            "path": str(
                Path(analyzer.EXPECTED_KERNEL_ROOT) / "vllm_xpu_kernels" / name
            ),
            "sha256": digest,
        }
        for name, digest in analyzer.EXPECTED_KERNELS.items()
    }
    return {
        "schema": "laguna-m8-inprocess-replay-arm-v4",
        "status": "complete",
        "diagnostic_only": True,
        "single_generate_call": True,
        "fresh_process": True,
        "arm": arm,
        "model": analyzer.EXPECTED_MODEL,
        "draft_model": None if arm == "q1" else analyzer.EXPECTED_DRAFT,
        "vllm_root": analyzer.EXPECTED_VLLM_ROOT,
        "vllm_commit": analyzer.EXPECTED_VLLM_COMMIT,
        "kernel_root": analyzer.EXPECTED_KERNEL_ROOT,
        "kernel_commit": analyzer.EXPECTED_KERNEL_COMMIT,
        "async_scheduling": arm == "q1",
        "kernel_identity": kernel_identity,
        "prompt_sha256": "a" * 64,
        "prompt_tokens": 31,
        "completion_tokens": analyzer.COMPLETION_TOKENS,
        "cached_tokens": 0,
        "generation_wall_ns": 1,
        "token_ids": token_ids,
        "token_ids_sha256": hashlib.sha256(
            json.dumps(token_ids, separators=(",", ":")).encode()
        ).hexdigest(),
        "text_sha256": "b" * 64,
        "finish_reason": "length",
        "profile_root": str(profile_root) if arm == "graph" else None,
        "profile_samples": 31 if arm == "graph" else None,
        "profile_rank_files": rank_files if arm == "graph" else None,
        "compilation_config": {
            "mode": "NONE",
            "cudagraph_mode": "PIECEWISE",
            "cudagraph_capture_sizes": [8],
            "max_cudagraph_capture_size": 8,
        }
        if arm == "graph"
        else None,
        "environment": _environment(arm, profile_root),
    }


def _write(path: Path, value: dict, mode: int = 0o600) -> None:
    path.write_text(json.dumps(value))
    path.chmod(mode)


@pytest.fixture
def fixture_root() -> Path:
    root = Path(
        tempfile.mkdtemp(prefix="laguna-inprocess-analyzer-", dir="/mnt/fast-ai")
    )
    root.chmod(0o700)
    profile_root = root / "graph" / "profile"
    profile_root.mkdir(parents=True, mode=0o700)
    for rank in analyzer.RANKS:
        _write(profile_root / f"rank{rank}.json", _profile(rank))
    rank_files = {
        str(rank): {
            "path": str(profile_root / f"rank{rank}.json"),
            "sha256": hashlib.sha256(
                (profile_root / f"rank{rank}.json").read_bytes()
            ).hexdigest(),
        }
        for rank in analyzer.RANKS
    }
    for arm in analyzer.ARM_NAMES:
        arm_root = root / arm
        arm_root.mkdir(exist_ok=True)
        _write(arm_root / "driver.json", _arm(arm, profile_root, rank_files))
    try:
        yield root
    finally:
        shutil.rmtree(root)


def _run(monkeypatch: pytest.MonkeyPatch, root: Path) -> int:
    output = root / "analysis.json"
    monkeypatch.setattr(
        analyzer,
        "parse_args",
        lambda: type("Args", (), {"run_dir": root, "out": output})(),
    )
    return analyzer.main()


def test_valid_four_rank_profiles_pass_and_reduce_max_rank(
    fixture_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _run(monkeypatch, fixture_root) == 0
    result = json.loads((fixture_root / "analysis.json").read_text())
    assert result["bitwise_exact_q1_eager_graph"] is True
    assert len(result["max_rank_samples"]) == 31


def test_rejects_q1_graph_token_mismatch(
    fixture_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = fixture_root / "graph" / "driver.json"
    payload = json.loads(path.read_text())
    payload["token_ids"][7] = 999
    payload["token_ids_sha256"] = hashlib.sha256(
        json.dumps(payload["token_ids"], separators=(",", ":")).encode()
    ).hexdigest()
    _write(path, payload)
    with pytest.raises(SystemExit, match="exact output mismatch"):
        _run(monkeypatch, fixture_root)


def test_rejects_noncanonical_q1_scheduler_identity(
    fixture_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = fixture_root / "q1" / "driver.json"
    payload = json.loads(path.read_text())
    payload["async_scheduling"] = False
    _write(path, payload)
    with pytest.raises(SystemExit, match="async_scheduling"):
        _run(monkeypatch, fixture_root)


def test_rejects_short_rank_profile(
    fixture_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = fixture_root / "graph" / "profile" / "rank3.json"
    payload = json.loads(path.read_text())
    payload["records"] = payload["records"][:-1]
    _write(path, payload)
    with pytest.raises(SystemExit, match="exactly 31 replay rows"):
        _run(monkeypatch, fixture_root)


def test_rejects_timing_containment_and_segment_order_drift(
    fixture_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = fixture_root / "graph" / "profile" / "rank1.json"
    payload = json.loads(path.read_text())
    payload["records"][0]["segment_ordered_host_call_ns"][0][1] += 1
    _write(path, payload)
    with pytest.raises(SystemExit, match="ordered duration drifted"):
        _run(monkeypatch, fixture_root)
