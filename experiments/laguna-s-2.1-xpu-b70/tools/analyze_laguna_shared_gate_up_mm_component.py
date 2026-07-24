#!/usr/bin/env python3
"""Fail-closed offline analyzer for the four-card shared gate+up component.

This module is deliberately an evidence verifier, not a benchmark launcher.
It never imports torch, creates a campaign, opens a model, or authorizes a
counter, endpoint, service, payload, network action, or submission.  The
runner records raw BF16 and raw-nanosecond evidence; this verifier recomputes
the exactness and timing decisions from those bytes and integers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

import analyze_laguna_shared_gate_up_mm_stage0 as stage0_analyzer
import gate_laguna_shared_gate_up_mm_component as contract
import gate_laguna_shared_gate_up_mm_stage0 as stage0
import orchestrate_laguna_shared_gate_up_mm_component as coordinator


MAIN = Path("/home/steve/llm-optimizations")
VLLM = Path("/home/steve/src/deepseek-v4-vllm-xpu-dspark")
KERNEL = Path("/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc")
RESULT_NAME = "component-result.json"
AGGREGATE_NAME = "component-aggregate.json"
PRE_COUNT, POST_COUNT, LAYERS = 128, 32, 47
ROLES = ("gate", "up")
RING_NAMES = tuple(f"{role}_{arm}_output_slots" for role in ROLES for arm in ("control", "candidate"))


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return contract.canonical(value)


def sha(path: Path) -> str:
    return contract.sha(path)


def git(repo: Path, *args: str) -> str:
    return contract.git(repo, *args)


def _is_sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _read_canonical(path: Path, label: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"{label} is missing or a symlink: {path}")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"{label} is not JSON: {path}") from error
    require(isinstance(value, dict) and raw == canonical(value) + b"\n", f"{label} is not canonical JSON: {path}")
    return value


def _clean(repo: Path, commit: str) -> None:
    require(git(repo, "status", "--porcelain=v1", "--untracked-files=all") == "", f"dirty checkout: {repo}")
    require(git(repo, "rev-parse", "HEAD") == commit, f"source commit drift: {repo}")


def _packet_lineage(packet: dict[str, Any], authorization: Path) -> str:
    """Require a clean, packet-only authorization child of frozen tools."""
    require(authorization.read_bytes() == canonical(packet) + b"\n", "authorization bytes are noncanonical")
    tracking = packet["authorization_tracking"]
    require(tracking["repository"] == str(MAIN), "authorization repository drift")
    require(packet["source"]["main_tools_commit"] == tracking["tools_commit"], "tools/source commit split")
    require(git(MAIN, "status", "--porcelain=v1", "--untracked-files=all") == "", "main checkout is dirty")
    head = git(MAIN, "rev-parse", "HEAD")
    require(git(MAIN, "rev-parse", f"{head}^") == tracking["tools_commit"], "authorization is not tools child")
    changed = git(MAIN, "diff-tree", "--no-commit-id", "--name-only", "-r", head).splitlines()
    require(changed == [tracking["packet_repo_path"]], "authorization child is not packet-only")
    tracked = subprocess.run(["git", "-C", str(MAIN), "show", f"{head}:{tracking['packet_repo_path']}"], check=True, capture_output=True).stdout
    require(tracked == authorization.read_bytes(), "executed packet differs from Git object")
    return head


def _runtime_and_sources(packet: dict[str, Any]) -> None:
    _clean(VLLM, packet["source"]["vllm_commit"])
    _clean(KERNEL, packet["source"]["kernel_commit"])
    for name, record in packet["tools"].items():
        require(set(record) == {"path", "sha256", "state"} and _is_sha(record["sha256"]), f"tool schema drift: {name}")
        require(sha(MAIN / record["path"]) == record["sha256"], f"tool bytes drift: {name}")
    for relative, digest in packet["source"]["files"].items():
        require(_is_sha(digest) and sha(VLLM / relative) == digest, f"vLLM source bytes drift: {relative}")
    runtime = packet["runtime"]
    require(sys.executable == runtime["python_executable"] and sys.version == runtime["python_version"], "analyzer Python identity drift")
    for name, record in runtime["files"].items():
        path = Path(record["path"])
        require(path.is_file() and path.resolve(strict=True) == Path(record["resolved_path"]) and sha(path) == record["sha256"], f"runtime file drift: {name}")
    binaries = {
        "_C.abi3.so": KERNEL / "vllm_xpu_kernels/_C.abi3.so",
        "_xpu_C.abi3.so": KERNEL / "vllm_xpu_kernels/_xpu_C.abi3.so",
        "_moe_C.abi3.so": KERNEL / "vllm_xpu_kernels/_moe_C.abi3.so",
        "libgrouped_gemm_xe_2.so": KERNEL / "vllm_xpu_kernels/libgrouped_gemm_xe_2.so",
    }
    require(set(packet["binaries"]) == set(binaries), "binary inventory drift")
    for name, path in binaries.items():
        require(sha(path) == packet["binaries"][name], f"binary bytes drift: {name}")
    require(sha(Path(packet["model"]["config_path"])) == packet["model"]["config_sha256"], "model config drift")
    require(Path("/proc/sys/kernel/random/boot_id").read_text().strip() == packet["boot_id"], "boot identity drift")


def _stage0(packet: dict[str, Any]) -> dict[str, Any]:
    info = packet["stage0"]
    require(info["certificate"] == contract.SEALED_STAGE0 and info["required_status"] == "stage0_exactness_pass", "stage-zero certificate drift")
    result_path, fixture_path = Path(info["result_path"]), Path(info["fixture_path"])
    require(sha(result_path) == info["result_sha256"] == contract.SEALED_STAGE0["result_sha256"], "stage-zero result drift")
    require(sha(fixture_path) == info["fixture_sha256"] == contract.SEALED_STAGE0["fixture_sha256"], "stage-zero fixture drift")
    contract.validate_stage0_evidence(result_path, fixture_path)
    fixture = _read_canonical(fixture_path, "stage-zero fixture")
    stage0.validate_fixture_manifest(fixture)
    result = _read_canonical(result_path, "stage-zero result")
    require(result.get("status") == "stage0_exactness_pass" and result.get("passed") is True, "stage-zero is not an exact pass")
    return fixture


def _strict_tree(root: Path, expected: set[str]) -> None:
    require(root.is_dir() and not root.is_symlink(), "campaign root absent or symlinked")
    actual: set[str] = set()
    directories: set[str] = set()
    for base, dirs, files in os.walk(root, topdown=True, followlinks=False):
        base_path = Path(base)
        for name in dirs:
            child = base_path / name
            require(not child.is_symlink(), f"symlinked artifact directory: {child}")
            directories.add(str(child.relative_to(root)))
        for name in files:
            child = base_path / name
            require(child.is_file() and not child.is_symlink(), f"unsafe artifact: {child}")
            actual.add(str(child.relative_to(root)))
    require(actual == expected, f"artifact inventory drift: expected={sorted(expected)} actual={sorted(actual)}")
    expected_dirs = {str(parent) for item in expected for parent in Path(item).parents if str(parent) != "."}
    require(directories == expected_dirs, "artifact directory inventory drift")


def _checkpoint_paths(result: dict[str, Any]) -> list[str]:
    expected = [
        "pre-tensor-identity-checkpoint.json", "tensor-work-started-checkpoint.json",
        "runtime-card-binding-checkpoint.json", "constructor-scope-proof.json", "dispatch-proof.json",
        *[f"pre-epochs/epoch-{index:03d}.json" for index in range(PRE_COUNT)], "timing.json",
        *[f"post-epochs/epoch-{index:03d}.json" for index in range(POST_COUNT)],
    ]
    paths = result.get("checkpoints")
    require(paths == expected and len(paths) == 166, "checkpoint inventory/order drift")
    return expected


def _checkpoints(root: Path, result: dict[str, Any], digest: str, rank: int) -> None:
    paths = _checkpoint_paths(result)
    hashes = result.get("checkpoint_sha256")
    require(isinstance(hashes, dict) and set(hashes) == set(paths) and all(_is_sha(value) for value in hashes.values()), "checkpoint hash manifest drift")
    values = {relative: _read_canonical(root / relative, f"checkpoint {relative}") for relative in paths}
    for relative in paths:
        require(sha(root / relative) == hashes[relative], f"checkpoint hash drift: {relative}")
    require(values["tensor-work-started-checkpoint.json"] == {"format": "laguna-shared-gate-up-m8-component-tensor-start-v2", "packet_sha256": digest, "rank": rank, "tensor_work_started": True}, "tensor-start checkpoint drift")
    require(values["pre-tensor-identity-checkpoint.json"] == {"format": "laguna-shared-gate-up-m8-component-pre-tensor-v2", "packet_sha256": digest, "rank": rank, "tensor_work_started": False, "observed": result["observed"]}, "pre-tensor checkpoint/result split")
    require(values["runtime-card-binding-checkpoint.json"] == result["runtime_card_binding"], "runtime checkpoint/result split")
    require(values["constructor-scope-proof.json"] == result["constructor_scope_proof"], "scope checkpoint/result split")
    require(values["dispatch-proof.json"] == result["dispatch_proof"], "dispatch checkpoint/result split")
    require(values["timing.json"] == result["timing"], "timing checkpoint/result split")
    for phase, entries in (("pre", result["pre_exactness"]), ("post", result["post_exactness"])):
        for envelope in entries:
            entry = envelope.get("entry") if isinstance(envelope, dict) else None
            require(isinstance(entry, dict) and isinstance(entry.get("epoch"), int), f"{phase} epoch envelope drift")
            require(values[f"{phase}-epochs/epoch-{entry['epoch']:03d}.json"] == envelope, f"{phase} checkpoint/result split")


def _epoch(envelope: object, fixture_epoch: dict[str, Any], digest: str, rank: int) -> tuple[str, str]:
    require(isinstance(envelope, dict) and set(envelope) == {"packet_sha256", "rank", "entry"}, "epoch envelope schema drift")
    require(envelope["packet_sha256"] == digest and envelope["rank"] == rank and isinstance(envelope["entry"], dict), "epoch envelope binding drift")
    equal, output = stage0_analyzer._epoch(envelope["entry"], fixture_epoch)
    require(equal, f"raw BF16 mismatch at epoch {fixture_epoch['epoch']}")
    require(isinstance(output, tuple) and len(output) == 2 and all(_is_sha(value) for value in output), "pair output-hash evidence drift")
    return output


def _exactness(result: dict[str, Any], fixture: dict[str, Any], digest: str, rank: int) -> dict[str, str]:
    pre, post = result.get("pre_exactness"), result.get("post_exactness")
    require(isinstance(pre, list) and len(pre) == PRE_COUNT and isinstance(post, list) and len(post) == POST_COUNT, "pre/post exactness count drift")
    pre_output = [_epoch(item, fixture["epochs"][index], digest, rank) for index, item in enumerate(pre)]
    post_output = [_epoch(item, fixture["epochs"][index], digest, rank) for index, item in enumerate(post)]
    require(len(set(pre_output)) == PRE_COUNT and len(set(post_output)) == POST_COUNT, "exactness corpus lacks unique pair outputs")
    for index in range(POST_COUNT):
        require(canonical(post[index]) == canonical(pre[index]), f"post replay differs from pre epoch {index}")
    return {
        "pre_fixture": hashlib.sha256("".join(item["entry"]["fixture_epoch_sha256"] for item in pre).encode()).hexdigest(),
        "pre_output": hashlib.sha256("".join("".join(pair) for pair in pre_output).encode()).hexdigest(),
        "post_fixture": hashlib.sha256("".join(item["entry"]["fixture_epoch_sha256"] for item in post).encode()).hexdigest(),
        "post_output": hashlib.sha256("".join("".join(pair) for pair in post_output).encode()).hexdigest(),
    }


def _integer(value: object, label: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool) and value > 0, f"{label} is not a positive integer")
    return value


def _number(value: object, label: str) -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{label} is not numeric")
    value = float(value)
    require(math.isfinite(value), f"{label} is nonfinite")
    return value


def _metadata(value: object, *, label: str, shape: list[int], stride: list[int], raw: str | None = None) -> dict[str, Any]:
    keys = {"data_ptr", "shape", "stride", "dtype", "numel", "element_size"}
    if raw is not None:
        keys.add("raw_bf16_le_sha256")
    require(isinstance(value, dict) and set(value) == keys, f"{label} metadata schema drift")
    require(_integer(value["data_ptr"], label + " pointer") == value["data_ptr"] and value["shape"] == shape and value["stride"] == stride and value["dtype"] == "torch.bfloat16" and value["numel"] == math.prod(shape) and value["element_size"] == 2, f"{label} metadata drift")
    if raw is not None:
        require(value["raw_bf16_le_sha256"] == raw and _is_sha(raw), f"{label} raw hash drift")
    return value


def _fixture_tensor(epoch: dict[str, Any], label: str) -> dict[str, Any]:
    matching = [record for record in epoch["tensors"] if record["label"] == label]
    require(len(matching) == 1, f"fixture timing tensor missing: {label}")
    return matching[0]


def _timing_slot(value: object, fixture_epoch: dict[str, Any], index: int) -> tuple[dict[str, Any], ...]:
    expected = {"slot", "rows", "gate_weight", "up_weight", "rows_bmm", "gate_weight_t", "up_weight_t", "gate_expanded", "up_expanded", "gate_control", "up_control", "gate_candidate", "up_candidate"}
    require(isinstance(value, dict) and set(value) == expected and value["slot"] == index, f"timing slot schema/order drift: {index}")
    rows_fixture = _fixture_tensor(fixture_epoch, "hidden_input")
    gate_fixture = _fixture_tensor(fixture_epoch, "gate_weight")
    up_fixture = _fixture_tensor(fixture_epoch, "up_weight")
    rows_shape, weight_shape = rows_fixture["shape"], gate_fixture["shape"]
    require(rows_shape == [stage0.ROWS, stage0.HIDDEN] and weight_shape == [stage0.PROJECTION, stage0.HIDDEN] and up_fixture["shape"] == weight_shape, f"fixture geometry drift: {index}")
    rows = _metadata(value["rows"], label=f"rows {index}", shape=rows_shape, stride=[stage0.HIDDEN, 1], raw=rows_fixture["raw_bf16_le_sha256"])
    gate_weight = _metadata(value["gate_weight"], label=f"gate weight {index}", shape=weight_shape, stride=[stage0.HIDDEN, 1], raw=gate_fixture["raw_bf16_le_sha256"])
    up_weight = _metadata(value["up_weight"], label=f"up weight {index}", shape=weight_shape, stride=[stage0.HIDDEN, 1], raw=up_fixture["raw_bf16_le_sha256"])
    rows_bmm = _metadata(value["rows_bmm"], label=f"rows_bmm {index}", shape=[stage0.ROWS, 1, stage0.HIDDEN], stride=[stage0.HIDDEN, stage0.HIDDEN, 1])
    require(rows_bmm["data_ptr"] == rows["data_ptr"], f"timing rows view storage drift: {index}")
    for role, weight in (("gate", gate_weight), ("up", up_weight)):
        weight_t = _metadata(value[f"{role}_weight_t"], label=f"{role} weight_t {index}", shape=[stage0.HIDDEN, stage0.PROJECTION], stride=[1, stage0.HIDDEN])
        expanded = _metadata(
            value[f"{role}_expanded"],
            label=f"{role} expanded {index}",
            shape=[stage0.ROWS, stage0.HIDDEN, stage0.PROJECTION],
            stride=[0, 1, stage0.HIDDEN],
        )
        require(weight_t["data_ptr"] == weight["data_ptr"] and expanded["data_ptr"] == weight["data_ptr"], f"{role} timing view storage drift: {index}")
    outputs = []
    for role in ROLES:
        for arm in ("control", "candidate"):
            value_key = f"{role}_{arm}"
            item = value[value_key]
            raw = item.get("raw_bf16_le_sha256") if isinstance(item, dict) else None
            outputs.append(_metadata(item, label=f"{value_key} {index}", shape=[stage0.ROWS, stage0.PROJECTION] if arm == "candidate" else [stage0.ROWS, 1, stage0.PROJECTION], stride=[stage0.PROJECTION, 1] if arm == "candidate" else [stage0.PROJECTION, stage0.PROJECTION, 1], raw=raw))
    require(outputs[0]["raw_bf16_le_sha256"] == outputs[1]["raw_bf16_le_sha256"] and outputs[2]["raw_bf16_le_sha256"] == outputs[3]["raw_bf16_le_sha256"], f"timing role raw output mismatch: {index}")
    return (rows, gate_weight, up_weight, *outputs)


def _timing(timing: object, fixture: dict[str, Any], digest: str, rank: int) -> dict[str, float | int]:
    protocol = contract.PROTOCOL
    fixed = {
        "timing_label": "allocation_free_isolated_gate_up_GEMM_pair",
        "target_layers_per_cycle": LAYERS, "projections_per_layer": 2,
        "projection_calls_per_cycle": 94, "weight_bytes_each": 1572864,
        "distinct_inputs": LAYERS, "distinct_weights": 94,
        "preallocated_unique_inputs": True, "output_ring_slots_per_projection": LAYERS,
        "output_ring_count": 4, "distinct_preallocated_output_buffers": True,
        "warm_cycles_per_arm": protocol["warm_cycles_per_arm"],
        "blocks": protocol["abba_blocks"], "cycles_per_arm_per_block": protocol["cycles_per_arm_per_block"],
        "calls_per_arm": 6016, "eviction_bytes_once_per_arm": protocol["eviction_bytes_per_arm"],
        "synchronization": protocol["synchronization"], "arm_order": "A-B-B-A",
    }
    expected = set(fixed) | {"packet_sha256", "rank", "passed", "candidate_block_wins", "median_saving_ms_per_cycle", "buffer_proof", "preflight_proof", "blocks_detail"}
    require(isinstance(timing, dict) and set(timing) == expected, "timing schema drift")
    require(timing["packet_sha256"] == digest and timing["rank"] == rank, "timing packet/rank drift")
    for key, value in fixed.items():
        require(timing[key] == value, f"timing protocol drift: {key}")
    buffer = timing["buffer_proof"]
    buffer_keys = {"input_slots", "gate_weight_slots", "up_weight_slots", *RING_NAMES, "gate_control_layout", "up_control_layout", "gate_candidate_layout", "up_candidate_layout", "pre_timing_slots", "post_timing_slots", "nonalias"}
    require(isinstance(buffer, dict) and set(buffer) == buffer_keys, "timing buffer schema drift")
    for name in ("input_slots", "gate_weight_slots", "up_weight_slots", *RING_NAMES):
        slots = buffer[name]
        require(isinstance(slots, list) and len(slots) == LAYERS and len(set(slots)) == LAYERS and all(isinstance(item, int) and item > 0 for item in slots), f"timing ring drift: {name}")
    pre, post = buffer["pre_timing_slots"], buffer["post_timing_slots"]
    require(isinstance(pre, list) and isinstance(post, list) and len(pre) == len(post) == LAYERS, "timing slot count drift")
    live: list[int] = []
    for index, (before, after) in enumerate(zip(pre, post, strict=True)):
        before_meta = _timing_slot(before, fixture["epochs"][index], index)
        after_meta = _timing_slot(after, fixture["epochs"][index], index)
        for left, right in zip(before_meta, after_meta, strict=True):
            require(left == right, f"post-timing metadata/raw mutation: slot {index}")
        live.extend(item["data_ptr"] for item in before_meta)
    require(len(set(live)) == len(live) and buffer["nonalias"] is True, "timing storage aliases")
    require(len({item["rows"]["raw_bf16_le_sha256"] for item in pre}) == LAYERS, "timing inputs are not 47 distinct frozen raw tensors")
    require(len({item[f"{role}_weight"]["raw_bf16_le_sha256"] for item in pre for role in ROLES}) == 94, "timing weights are not 94 distinct frozen raw tensors")
    for role in ROLES:
        for arm in ("control", "candidate"):
            key = f"{role}_{arm}"
            layout = buffer[f"{key}_layout"]
            require(layout == {field: pre[0][key][field] for field in ("data_ptr", "shape", "stride", "dtype", "numel", "element_size")}, f"timing layout split: {key}")
    expected_rings = {
        "input_slots": sorted(item["rows"]["data_ptr"] for item in pre),
        "gate_weight_slots": sorted(item["gate_weight"]["data_ptr"] for item in pre),
        "up_weight_slots": sorted(item["up_weight"]["data_ptr"] for item in pre),
        **{f"{role}_{arm}_output_slots": sorted(item[f"{role}_{arm}"]["data_ptr"] for item in pre) for role in ROLES for arm in ("control", "candidate")},
    }
    for key, expected_slots in expected_rings.items():
        require(buffer[key] == expected_slots, f"timing ring/proof split: {key}")
    proofs = timing["preflight_proof"]
    require(isinstance(proofs, list) and len(proofs) == LAYERS, "timing preflight count drift")
    for index, proof in enumerate(proofs):
        expected_proof = {"slot": index, "input_metadata_unchanged": True, "weight_metadata_unchanged": True, "output_metadata_unchanged": True, "gate_literal_raw_uint16_equal": True, "up_literal_raw_uint16_equal": True, "gate_control_out_raw_uint16_equal": True, "up_control_out_raw_uint16_equal": True, "gate_candidate_out_raw_uint16_equal": True, "up_candidate_out_raw_uint16_equal": True, "gate_control_out_supplied_ptr": pre[index]["gate_control"]["data_ptr"], "gate_control_out_returned_ptr": pre[index]["gate_control"]["data_ptr"], "up_control_out_supplied_ptr": pre[index]["up_control"]["data_ptr"], "up_control_out_returned_ptr": pre[index]["up_control"]["data_ptr"], "gate_candidate_out_supplied_ptr": pre[index]["gate_candidate"]["data_ptr"], "gate_candidate_out_returned_ptr": pre[index]["gate_candidate"]["data_ptr"], "up_candidate_out_supplied_ptr": pre[index]["up_candidate"]["data_ptr"], "up_candidate_out_returned_ptr": pre[index]["up_candidate"]["data_ptr"]}
        require(proof == expected_proof, f"timing preflight proof drift: {index}")
    blocks = timing["blocks_detail"]
    require(isinstance(blocks, list) and len(blocks) == 31, "ABBA block count drift")
    savings: list[float] = []
    cycles = protocol["cycles_per_arm_per_block"]
    for index, block in enumerate(blocks):
        fields = {"block", "rotation", "slot_order", "A1_control_elapsed_ns", "A1_control_ms", "B1_candidate_elapsed_ns", "B1_candidate_ms", "B2_candidate_elapsed_ns", "B2_candidate_ms", "A2_control_elapsed_ns", "A2_control_ms", "paired_control_ms", "paired_candidate_ms", "saving_ms"}
        require(isinstance(block, dict) and set(block) == fields and block["block"] == index, "ABBA block schema/order drift")
        rotation = (index * 11) % LAYERS
        require(block["rotation"] == rotation and block["slot_order"] == [(rotation + slot) % LAYERS for slot in range(LAYERS)], f"ABBA rotation drift: {index}")
        ns = [_integer(block[key], f"block {index} {key}") for key in ("A1_control_elapsed_ns", "B1_candidate_elapsed_ns", "B2_candidate_elapsed_ns", "A2_control_elapsed_ns")]
        ms = [_number(block[key], f"block {index} {key}") for key in ("A1_control_ms", "B1_candidate_ms", "B2_candidate_ms", "A2_control_ms")]
        require(all(observed == raw / cycles / 1_000_000 for observed, raw in zip(ms, ns, strict=True)), f"ABBA raw-ns conversion drift: {index}")
        control = _number(block["paired_control_ms"], f"block {index} paired control")
        candidate = _number(block["paired_candidate_ms"], f"block {index} paired candidate")
        saving = _number(block["saving_ms"], f"block {index} saving")
        expected_control = (ns[0] + ns[3]) / 2.0 / cycles / 1_000_000
        expected_candidate = (ns[1] + ns[2]) / 2.0 / cycles / 1_000_000
        require(abs(control - expected_control) <= 1e-12 and abs(candidate - expected_candidate) <= 1e-12 and abs(saving - (control - candidate)) <= 1e-12, f"ABBA recomputation drift: {index}")
        savings.append(saving)
    wins, median = sum(value > 0.0 for value in savings), statistics.median(savings)
    require(timing["candidate_block_wins"] == wins and abs(_number(timing["median_saving_ms_per_cycle"], "reported median") - median) <= 1e-12, "timing aggregate drift")
    require(wins >= 28 and median >= 0.20 and timing["passed"] is True, "per-card timing threshold failed")
    return {"wins": wins, "median_saving_ms": median}


def validate_schema_for_cpu_tests(
    result: dict[str, Any], fixture: dict[str, Any], packet: dict[str, Any]
) -> dict[str, Any]:
    """Validate the evidence grammar without granting production acceptance."""
    contract.validate(packet)
    stage0.validate_fixture_manifest(fixture)
    rank = result.get("rank")
    require(
        isinstance(rank, int) and not isinstance(rank, bool) and rank in range(4),
        "rank drift",
    )
    required = {
        "format",
        "status",
        "passed",
        "rank",
        "physical",
        "packet_path",
        "packet_sha256",
        "observed",
        "tensor_work_started",
        "constructor_scope_proof",
        "dispatch_proof",
        "actual_forward_proof",
        "runtime_card_binding",
        "pre_exactness",
        "timing",
        "post_exactness",
        "checkpoints",
        "checkpoint_sha256",
        "failure",
        "downstream",
    }
    require(
        set(result) == required
        and result["format"]
        == "laguna-shared-gate-up-m8-four-card-component-result-v1",
        "component result schema/format drift",
    )
    digest = hashlib.sha256(canonical(packet) + b"\n").hexdigest()
    card = packet["cards"][rank]
    require(
        result["status"] == "component-card-pass"
        and result["passed"] is True
        and result["failure"] is None
        and result["rank"] == rank
        and result["physical"] == card["physical"]
        and result["packet_path"] == packet["packet_path"]
        and result["packet_sha256"] == digest
        and result["tensor_work_started"] is True
        and result["downstream"] == contract.FALSE_ACTIONS,
        "component result identity/status/action drift",
    )
    _checkpoint_paths(result)
    exact = _exactness(result, fixture, digest, rank)
    timing = _timing(result["timing"], fixture, digest, rank)
    return {"rank": rank, "exact": exact, "timing": timing}


def _binding(result: dict[str, Any], packet: dict[str, Any], rank: int, digest: str) -> dict[str, Any]:
    card = packet["cards"][rank]
    observed = result["observed"]
    expected_observed = {"argv", "environment", "main_identity", "vllm_identity", "kernel_identity", "runtime", "binaries", "model", "boot_id", "card_binding"}
    require(isinstance(observed, dict) and set(observed) == expected_observed and observed["argv"] == card["runner_argv"] and observed["environment"] == card["environment"], "observed argv/environment drift")
    for key, repo, commit in (("main_identity", MAIN, git(MAIN, "rev-parse", "HEAD")), ("vllm_identity", VLLM, packet["source"]["vllm_commit"]), ("kernel_identity", KERNEL, packet["source"]["kernel_commit"])):
        require(observed[key] == {"path": str(repo), "commit": commit, "clean": True, "status_porcelain": [], "status_sha256": hashlib.sha256(b"").hexdigest()}, f"observed source identity drift: {key}")
    require(observed["runtime"] == packet["runtime"] and observed["binaries"] == packet["binaries"] and observed["model"] == packet["model"] and observed["boot_id"] == packet["boot_id"], "observed runtime/model identity drift")
    physical = card["physical"]
    campaign_start_path = Path(packet["campaign_root"]) / "campaign-start-checkpoint.json"
    start = _read_canonical(campaign_start_path, "campaign start")
    require(start.get("packet_sha256") == digest and start.get("packet_path") == packet["packet_path"] and start.get("downstream") == contract.FALSE_ACTIONS, "campaign-start packet/downstream drift")
    coordinator.validate_device_preflight(start.get("device_preflight"), packet)
    preflight = start["device_preflight"]
    filtered = preflight["filtered"][rank]
    expected_card_binding = {
        "packet_sha256": digest,
        "rank": rank,
        "oneapi_device_selector": "level_zero:0",
        "ze_affinity_mask": str(rank),
        "logical_device_id": 0,
        "physical": physical,
        "sysfs": {"drm_device": physical["drm_device"], "pci_bdf_address": physical["pci_bdf_address"], "vendor": "0x8086", "device": "0xe223"},
        "sealed_device_preflight": {"campaign_start_path": str(campaign_start_path), "campaign_start_sha256": sha(campaign_start_path), "device_preflight_sha256": hashlib.sha256(canonical(preflight)).hexdigest(), "unfiltered_stdout_sha256": preflight["unfiltered"]["stdout_sha256"], "filtered_stdout_sha256": filtered["stdout_sha256"]},
    }
    require(observed["card_binding"] == expected_card_binding, "observed pre-tensor card binding drift")
    binding = result["runtime_card_binding"]
    require(
        isinstance(binding, dict)
        and set(binding) == {"format", "packet_sha256", "rank", "binding"}
        and binding["format"]
        == "laguna-shared-gate-up-m8-component-runtime-card-binding-v1"
        and binding["packet_sha256"] == digest
        and binding["rank"] == rank,
        "runtime binding wrapper drift",
    )
    physical_uuid_bytes = bytes.fromhex(physical["uuid"].replace("-", ""))
    torch_uuid_bytes = physical_uuid_bytes[::-1]
    expected_body = {
        **expected_card_binding,
        "visible_device_count": 1,
        "current_device": 0,
        "device_name": stage0.EXPECTED_DEVICE_NAME,
        "tensor_device": "xpu:0",
        "torch_version": packet["runtime"]["torch_version"],
        "runtime_uuid": physical["uuid"],
        "runtime_uuid_bytes_hex": physical_uuid_bytes.hex(),
        "torch_runtime_uuid": str(uuid.UUID(bytes=torch_uuid_bytes)),
        "torch_runtime_uuid_bytes_hex": torch_uuid_bytes.hex(),
        "runtime_uuid_mapping": (
            "xpu_smi_uuid_is_reverse_of_torch_level_zero_bytes"
        ),
    }
    body = binding["binding"]
    require(body == expected_body, "runtime card mapping/schema drift")
    return {
        "uuid": physical["uuid"],
        "runtime_uuid": body["runtime_uuid"],
        "torch_runtime_uuid_bytes_hex": body["torch_runtime_uuid_bytes_hex"],
        "bdf": physical["pci_bdf_address"],
        "boot_id": packet["boot_id"],
    }


def _card(packet: dict[str, Any], fixture: dict[str, Any], rank: int, path: Path) -> dict[str, Any]:
    result = _read_canonical(path, f"rank {rank} result")
    digest = sha(Path(packet["packet_path"]))
    expected = {"format", "status", "passed", "rank", "physical", "packet_path", "packet_sha256", "observed", "tensor_work_started", "constructor_scope_proof", "dispatch_proof", "actual_forward_proof", "runtime_card_binding", "pre_exactness", "timing", "post_exactness", "checkpoints", "checkpoint_sha256", "failure", "downstream"}
    require(set(result) == expected and result["format"] == "laguna-shared-gate-up-m8-four-card-component-result-v1", "component result schema/format drift")
    require(result["status"] == "component-card-pass" and result["passed"] is True and result["failure"] is None and result["downstream"] == contract.FALSE_ACTIONS, "result is not clean component pass")
    require(result["rank"] == rank and result["physical"] == packet["cards"][rank]["physical"] and result["packet_path"] == packet["packet_path"] and result["packet_sha256"] == digest and result["tensor_work_started"] is True, "result identity drift")
    _checkpoints(path.parent, result, digest, rank)
    binding = _binding(result, packet, rank, digest)
    scope = result["constructor_scope_proof"]
    dispatch = result["dispatch_proof"]
    require(isinstance(scope, dict) and scope.get("packet_sha256") == digest and scope.get("rank") == rank and set(scope) == {"packet_sha256", "rank", "scope"}, "scope envelope drift")
    require(isinstance(dispatch, dict) and dispatch.get("packet_sha256") == digest and dispatch.get("rank") == rank and set(dispatch) == {"packet_sha256", "rank", "proof"}, "dispatch envelope drift")
    stage0_analyzer.validate_constructor_scope(scope["scope"])
    stage0_analyzer.validate_dispatch_proof(dispatch["proof"])
    forward = result["actual_forward_proof"]
    require(
        forward
        == {
            "binding": result["runtime_card_binding"]["binding"],
            "scope": scope["scope"],
            "packet_sha256": digest,
            "rank": rank,
        },
        "actual ordered pair-forward proof drift",
    )
    exact = _exactness(result, fixture, digest, rank)
    timing = _timing(result["timing"], fixture, digest, rank)
    return {**binding, **exact, **timing}


def _cross_card(cards: list[dict[str, Any]]) -> None:
    for key in ("uuid", "runtime_uuid", "bdf"):
        require(len({card[key] for card in cards}) == 4, f"cross-card physical mapping collision: {key}")
    require(len({card["boot_id"] for card in cards}) == 1, "cards differ in boot identity")
    for key in ("pre_fixture", "pre_output", "post_fixture", "post_output"):
        require(len({card[key] for card in cards}) == 1, f"cross-card exactness digest drift: {key}")


def validate_production(packet: dict[str, Any], authorization: Path, results: list[Path], out: Path) -> tuple[str, list[dict[str, Any]]]:
    contract.validate(packet)
    require(authorization == Path(packet["packet_path"]), "authorization argv drift")
    head = _packet_lineage(packet, authorization)
    _runtime_and_sources(packet)
    fixture = _stage0(packet)
    require(results == [Path(card["result"]) for card in packet["cards"]], "card-result ordering drift")
    campaign = Path(packet["campaign_root"])
    require(out == campaign / AGGREGATE_NAME and not out.exists() and not out.is_symlink(), "aggregate path is not fresh/frozen")
    cards = [_card(packet, fixture, rank, path) for rank, path in enumerate(results)]
    _cross_card(cards)
    expected = {"campaign-start-checkpoint.json", *[f"rank-{rank}-terminal.json" for rank in range(4)]}
    for card in packet["cards"]:
        root = Path(card["output_root"]).relative_to(campaign)
        result = _read_canonical(Path(card["result"]), "result inventory")
        expected.add(str(root / RESULT_NAME))
        expected.update(str(root / item) for item in _checkpoint_paths(result))
    _strict_tree(campaign, expected)
    require(_packet_lineage(packet, authorization) == head, "authorization lineage changed during analysis")
    _runtime_and_sources(packet)
    require(_card(packet, _stage0(packet), 0, results[0]) == cards[0], "card zero changed during analysis")
    return head, cards


def _aggregate(packet: dict[str, Any], head: str, cards: list[dict[str, Any]], path: Path) -> dict[str, Any]:
    aggregate = _read_canonical(path, "component aggregate")
    expected = {
        "format": "laguna-shared-gate-up-m8-four-card-component-aggregate-v1",
        "status": "component_aggregate_pending_final_seal",
        "passed": True,
        "authorization_head": head,
        "packet_sha256": sha(Path(packet["packet_path"])),
        "cards": cards,
        "downstream": contract.FALSE_ACTIONS,
    }
    require(aggregate == expected, "aggregate schema/identity drift")
    return aggregate


def _terminal(packet: dict[str, Any], cards: list[dict[str, Any]]) -> dict[str, Any]:
    campaign = Path(packet["campaign_root"])
    terminal = _read_canonical(Path(packet["campaign_terminal_path"]), "campaign terminal")
    result_hashes = {str(card["rank"]): sha(Path(card["result"])) for card in packet["cards"]}
    expected = {
        "format": "laguna-shared-gate-up-m8-component-campaign-terminal-v1",
        "status": "component_aggregate_pending_final_seal",
        "failed_rank": None,
        "analyzer_invoked": True,
        "analyzer_argv": packet["analyzer_argv"],
        "analyzer_exit_code": 0,
        "packet_sha256": sha(Path(packet["packet_path"])),
        "aggregate_path": packet["aggregate_path"],
        "aggregate_sha256": sha(Path(packet["aggregate_path"])),
        "rank_result_sha256": result_hashes,
        "downstream": contract.FALSE_ACTIONS,
    }
    require(isinstance(terminal.get("completed_utc"), str) and terminal["completed_utc"].endswith("Z"), "campaign terminal timestamp drift")
    require({key: value for key, value in terminal.items() if key != "completed_utc"} == expected, "campaign terminal schema/identity drift")
    for rank, card in enumerate(packet["cards"]):
        path = campaign / f"rank-{rank}-terminal.json"
        leg = _read_canonical(path, f"rank {rank} terminal")
        require(isinstance(leg.get("completed_utc"), str) and leg["completed_utc"].endswith("Z"), f"rank {rank} terminal timestamp drift")
        expected_leg = {
            "format": "laguna-shared-gate-up-m8-component-leg-terminal-v1",
            "rank": rank,
            "argv": card["runner_argv"],
            "environment": card["environment"],
            "exit_code": 0,
            "result_path": card["result"],
            "result_present": True,
            "result_sha256": sha(Path(card["result"])),
            "status": "rank_zero_exit",
            "downstream": contract.FALSE_ACTIONS,
        }
        require({key: value for key, value in leg.items() if key != "completed_utc"} == expected_leg, f"rank {rank} terminal identity drift")
    return terminal


def _final_state(
    packet: dict[str, Any], authorization: Path, *, existing_final_manifest: bool = False
) -> tuple[str, list[dict[str, Any]], set[str]]:
    contract.validate(packet)
    head = _packet_lineage(packet, authorization)
    _runtime_and_sources(packet)
    fixture = _stage0(packet)
    cards = [_card(packet, fixture, rank, Path(card["result"])) for rank, card in enumerate(packet["cards"])]
    _cross_card(cards)
    _aggregate(packet, head, cards, Path(packet["aggregate_path"]))
    _terminal(packet, cards)
    campaign = Path(packet["campaign_root"])
    expected = {"campaign-start-checkpoint.json", "campaign-terminal.json", AGGREGATE_NAME, *[f"rank-{rank}-terminal.json" for rank in range(4)]}
    for card in packet["cards"]:
        root = Path(card["output_root"]).relative_to(campaign)
        result = _read_canonical(Path(card["result"]), "final result inventory")
        expected.add(str(root / RESULT_NAME))
        expected.update(str(root / item) for item in _checkpoint_paths(result))
    manifest = Path(packet["final_manifest_path"])
    _strict_tree(campaign, expected | ({manifest.name} if existing_final_manifest else set()))
    return head, cards, expected


def _final_manifest(packet: dict[str, Any], authorization: Path, head: str, expected: set[str]) -> dict[str, Any]:
    campaign = Path(packet["campaign_root"])
    hashes = {relative: sha(campaign / relative) for relative in sorted(expected)}
    return {
        "format": "laguna-shared-gate-up-m8-four-card-component-final-manifest-v1",
        "status": "component_final_seal_passed_counter_tooling_construction_authorized",
        "passed": True,
        "packet_path": packet["packet_path"],
        "packet_sha256": sha(authorization),
        "authorization_head": head,
        "aggregate_path": packet["aggregate_path"],
        "aggregate_sha256": sha(Path(packet["aggregate_path"])),
        "campaign_terminal_path": packet["campaign_terminal_path"],
        "campaign_terminal_sha256": sha(Path(packet["campaign_terminal_path"])),
        "finalizer_argv": packet["finalizer_argv"],
        "final_verifier_argv": packet["final_verifier_argv"],
        "pre_manifest_sha256": hashes,
        "downstream": {**contract.FALSE_ACTIONS, "counter_tooling_construction_authorized": True},
    }


def finalize_production(packet: dict[str, Any], authorization: Path, results: list[Path], aggregate: Path, terminal: Path, manifest: Path) -> dict[str, Any]:
    require(results == [Path(card["result"]) for card in packet["cards"]], "finalizer card result order drift")
    require(aggregate == Path(packet["aggregate_path"]) and terminal == Path(packet["campaign_terminal_path"]) and manifest == Path(packet["final_manifest_path"]), "finalizer path argv drift")
    require(not manifest.exists() and not manifest.is_symlink(), "final manifest path is not fresh")
    head, _cards, expected = _final_state(packet, authorization)
    candidate = _final_manifest(packet, authorization, head, expected)
    # Repeat every source/card/tree check before a non-replaceable final seal.
    repeat_head, repeat_cards, repeat_expected = _final_state(packet, authorization)
    require(repeat_head == head and repeat_expected == expected, "state changed during finalization")
    require(repeat_cards == _cards and _final_manifest(packet, authorization, repeat_head, repeat_expected) == candidate, "card/manifest race during finalization")
    return candidate


def verify_final_production(packet: dict[str, Any], authorization: Path, results: list[Path], aggregate: Path, terminal: Path, manifest: Path) -> None:
    require(results == [Path(card["result"]) for card in packet["cards"]], "final verifier card result order drift")
    require(aggregate == Path(packet["aggregate_path"]) and terminal == Path(packet["campaign_terminal_path"]) and manifest == Path(packet["final_manifest_path"]), "final verifier path argv drift")
    head, _cards, expected = _final_state(packet, authorization, existing_final_manifest=True)
    observed = _read_canonical(manifest, "component final manifest")
    expected_manifest = _final_manifest(packet, authorization, head, expected)
    require(observed == expected_manifest, "final manifest schema/identity drift")
    _strict_tree(Path(packet["campaign_root"]), expected | {manifest.name})


def _exclusive_json(path: Path, value: dict[str, Any]) -> None:
    contract._absolute_non_usb(path)
    require(
        path.name not in {"", ".", ".."} and "/" not in path.name,
        "unsafe aggregate filename",
    )
    require(
        path.parent.is_dir() and not path.parent.is_symlink(),
        "aggregate parent is unsafe",
    )
    payload = canonical(value) + b"\n"
    directory = os.open(
        path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    )
    try:
        fd = os.open(
            path.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o644,
            dir_fd=directory,
        )
        try:
            offset = 0
            while offset < len(payload):
                wrote = os.write(fd, payload[offset:])
                require(wrote > 0, "short aggregate write")
                offset += wrote
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(directory)
    finally:
        os.close(directory)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--card-result", action="append", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument("--verify-final", action="store_true")
    parser.add_argument("--aggregate", type=Path)
    parser.add_argument("--campaign-terminal", type=Path)
    parser.add_argument("--final-manifest", type=Path)
    args = parser.parse_args()
    require(not (args.finalize and args.verify_final), "analyzer modes are mutually exclusive")
    packet = _read_canonical(args.authorization, "authorization")
    require(dict(os.environ) == packet["coordinator_environment"], "analyzer environment differs from frozen packet")
    if args.finalize or args.verify_final:
        require(args.out is None and args.aggregate is not None and args.campaign_terminal is not None and args.final_manifest is not None, "final-seal arguments drift")
        expected = packet["finalizer_argv"] if args.finalize else packet["final_verifier_argv"]
        require(sys.argv == expected[1:], "final-seal argv differs from frozen packet")
        if args.finalize:
            manifest = finalize_production(packet, args.authorization, args.card_result, args.aggregate, args.campaign_terminal, args.final_manifest)
            _exclusive_json(args.final_manifest, manifest)
            print(json.dumps({"passed": True, "final_manifest": str(args.final_manifest)}, sort_keys=True))
        else:
            verify_final_production(packet, args.authorization, args.card_result, args.aggregate, args.campaign_terminal, args.final_manifest)
            print(json.dumps({"passed": True, "verified_final_manifest": str(args.final_manifest)}, sort_keys=True))
        return 0
    require(args.out is not None and args.aggregate is None and args.campaign_terminal is None and args.final_manifest is None, "initial analyzer arguments drift")
    require(sys.argv == packet["analyzer_argv"][1:], "analyzer argv differs from frozen packet")
    head, cards = validate_production(packet, args.authorization, args.card_result, args.out)
    aggregate = {"format": "laguna-shared-gate-up-m8-four-card-component-aggregate-v1", "status": "component_aggregate_pending_final_seal", "passed": True, "authorization_head": head, "packet_sha256": sha(args.authorization), "cards": cards, "downstream": contract.FALSE_ACTIONS}
    _exclusive_json(args.out, aggregate)
    print(json.dumps({"passed": True, "out": str(args.out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
