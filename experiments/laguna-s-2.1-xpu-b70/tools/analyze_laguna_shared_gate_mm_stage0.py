#!/usr/bin/env python3
"""Offline CPU-only verifier for frozen Laguna shared-gate stage-zero evidence."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import gate_laguna_shared_gate_mm_stage0 as stage0


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


OUTPUT_SPECS = {
    "gate_control": ("stage0.gate.control", (stage0.ROWS, stage0.PROJECTION)),
    "gate_candidate": ("stage0.gate.candidate", (stage0.ROWS, stage0.PROJECTION)),
    "gate_candidate_repeat": (
        "stage0.gate.candidate_repeat",
        (stage0.ROWS, stage0.PROJECTION),
    ),
    "up_control": ("stage0.up.control", (stage0.ROWS, stage0.PROJECTION)),
    "up_candidate": ("stage0.up.candidate", (stage0.ROWS, stage0.PROJECTION)),
    "silu_product_control": (
        "stage0.silu_product.control",
        (stage0.ROWS, stage0.PROJECTION),
    ),
    "silu_product_candidate": (
        "stage0.silu_product.candidate",
        (stage0.ROWS, stage0.PROJECTION),
    ),
    "down_control": ("stage0.down.control", (stage0.ROWS, stage0.HIDDEN)),
    "down_candidate": ("stage0.down.candidate", (stage0.ROWS, stage0.HIDDEN)),
    "shared_routed_add_control": (
        "stage0.shared_routed_add.control",
        (stage0.ROWS, stage0.HIDDEN),
    ),
    "shared_routed_add_candidate": (
        "stage0.shared_routed_add.candidate",
        (stage0.ROWS, stage0.HIDDEN),
    ),
    "reduction_control": ("stage0.reduction.control", (stage0.ROWS, stage0.HIDDEN)),
    "reduction_candidate": ("stage0.reduction.candidate", (stage0.ROWS, stage0.HIDDEN)),
}
PAIRINGS = {
    "gate": ("gate_control", "gate_candidate"),
    "repeat": ("gate_candidate", "gate_candidate_repeat"),
    "up": ("up_control", "up_candidate"),
    "silu_product": ("silu_product_control", "silu_product_candidate"),
    "down": ("down_control", "down_candidate"),
    "shared_routed_add": ("shared_routed_add_control", "shared_routed_add_candidate"),
    "reduction": ("reduction_control", "reduction_candidate"),
}


def _utc(value: object) -> datetime:
    require(isinstance(value, str) and value.endswith("Z"), "timestamp must be UTC Z")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise RuntimeError("invalid UTC timestamp") from error


def _raw(record: dict[str, Any], label: str, shape: tuple[int, ...]) -> bytes:
    keys = {
        "label",
        "shape",
        "dtype",
        "byte_order",
        "raw_bf16_le_base64",
        "raw_bf16_le_sha256",
        "canonical_sha256",
        "finite",
    }
    require(
        set(record) == keys
        and record["label"] == label
        and record["shape"] == list(shape)
        and record["dtype"] == stage0.DTYPE
        and record["byte_order"] == stage0.BYTE_ORDER,
        "output metadata drift",
    )
    try:
        raw = base64.b64decode(record["raw_bf16_le_base64"], validate=True)
    except Exception as error:
        raise RuntimeError("invalid output base64") from error
    require(len(raw) == stage0.tensor_byte_count(shape), "output raw length drift")
    finite = stage0.bf16_all_finite(raw)
    require(record["finite"] is finite and finite, "output finiteness drift")
    require(
        record["raw_bf16_le_sha256"] == stage0.sha256_bytes(raw)
        and record["canonical_sha256"]
        == stage0.canonical_tensor_sha256(label, shape, raw),
        "output hash drift",
    )
    return raw


def _dispatch_tensor(name: str, rows: int, record: dict[str, Any]) -> bytes:
    return _raw(record, f"stage0.dispatch.{name}", (rows, stage0.PROJECTION))


def _case(
    name: str,
    rows: int,
    *,
    mm: int,
    bmm: int,
    raised: bool,
    marker: bool,
    verifier: bool,
    proof: dict[str, Any],
) -> None:
    record = proof[name]
    keys = {
        "rows",
        "marker_enabled",
        "verifier_rows",
        "mm_calls",
        "bmm_calls",
        "fallback_calls",
        "raised",
        "exception",
        "actual_output",
        "expected_output",
    }
    require(
        set(record) == keys
        and record["rows"] == rows
        and record["marker_enabled"] is marker
        and record["verifier_rows"] is verifier
        and record["mm_calls"] == mm
        and record["bmm_calls"] == bmm
        and record["fallback_calls"] == 0
        and record["raised"] is raised,
        f"dispatch {name} count/scope drift",
    )
    if raised:
        require(
            record["exception"] == stage0.DISPATCH_REJECTION_EXCEPTIONS[name]
            and record["actual_output"] is None
            and record["expected_output"] is None,
            f"dispatch {name} accepted invalid call",
        )
    else:
        require(
            record["exception"] is None
            and _dispatch_tensor(name + ".actual", rows, record["actual_output"])
            == _dispatch_tensor(name + ".expected", rows, record["expected_output"]),
            f"dispatch {name} output mismatch",
        )


def validate_dispatch_proof(proof: dict[str, Any]) -> None:
    keys = {
        "scope",
        "marker_scope",
        "marked_m8",
        "unmarked_m8",
        "prefill_marked_gate",
        "m1",
        "m2",
        "m3",
        "m4",
        "m5",
        "m6",
        "m7",
        "bad_rows",
        "bad_weight_layout",
    }
    require(
        set(proof) == keys
        and proof["scope"] == "actual_checkpoint_selected_ColumnParallelLinear.forward",
        "dispatch proof scope drift",
    )
    require(
        proof["marker_scope"]
        == {
            "marked": ["model.layers.1.mlp.shared_expert.gate_proj"],
            "unmarked": [
                "model.layers.1.mlp.shared_expert.up_proj",
                "model.layers.1.mlp.shared_expert.down_proj",
                "dense_mlp",
                "draft",
            ],
        },
        "marker scope drift",
    )
    _case(
        "marked_m8",
        8,
        mm=1,
        bmm=0,
        raised=False,
        marker=True,
        verifier=True,
        proof=proof,
    )
    _case(
        "unmarked_m8",
        8,
        mm=0,
        bmm=1,
        raised=False,
        marker=False,
        verifier=True,
        proof=proof,
    )
    _case(
        "prefill_marked_gate",
        8,
        mm=0,
        bmm=1,
        raised=False,
        marker=True,
        verifier=False,
        proof=proof,
    )
    for rows in range(1, 8):
        _case(
            f"m{rows}",
            rows,
            mm=0,
            bmm=1,
            raised=False,
            marker=True,
            verifier=True,
            proof=proof,
        )
    _case(
        "bad_rows", 8, mm=0, bmm=0, raised=True, marker=True, verifier=True, proof=proof
    )
    _case(
        "bad_weight_layout",
        8,
        mm=0,
        bmm=0,
        raised=True,
        marker=True,
        verifier=True,
        proof=proof,
    )


def validate_constructor_scope(proof: dict[str, Any]) -> None:
    require(
        proof
        == {
            "constructor": "LagunaMLP_with_committed_LagunaMoE_scope_token",
            "marked_prefix": ("model.layers.1.mlp.shared_expert.gate_proj"),
            "marked_gate": True,
            "marked_scope_prefix": ("model.layers.1.mlp.shared_expert.gate_proj"),
            "unmarked": {
                "shared_up": True,
                "shared_down": True,
                "dense": True,
                "draft": True,
            },
            "quant_method": "UnquantizedLinearMethod",
            "shared_elementwise_enabled": True,
            "verifier_gating": (
                "vllm.forward_context.additional_kwargs.xpu_exact_spec_verifier"
            ),
            "runtime_hadamard_modules": [],
        },
        "constructor/marker scope proof drift",
    )


def validate_runtime_card0_binding(
    binding: dict[str, Any],
    packet: dict[str, Any],
    pre_tensor_identity: dict[str, Any],
) -> None:
    require(
        binding
        == {
            "oneapi_device_selector": "level_zero:0",
            "ze_affinity_mask": "0",
            "logical_device_id": 0,
            "current_device": 0,
            "visible_device_count": 1,
            "name": stage0.EXPECTED_DEVICE_NAME,
            "tensor_device": "xpu:0",
            "packet_device": packet["device"],
            "sysfs_card0": pre_tensor_identity["sysfs_card0"],
            "runtime_identity": packet["runtime"]["observed_identity"],
        },
        "runtime card-zero binding drift",
    )


def _validate_error(
    error: object,
    *,
    error_class: str,
    phase: str,
    proven: bool,
    proof: object,
    exception_required: bool,
) -> None:
    require(
        isinstance(error, dict)
        and set(error)
        == {
            "class",
            "phase",
            "exception_type",
            "message",
            "proven",
            "proof",
        }
        and error["class"] == error_class
        and error["phase"] == phase
        and isinstance(error["message"], str)
        and bool(error["message"])
        and error["proven"] is proven
        and error["proof"] == proof
        and (
            isinstance(error["exception_type"], str) and bool(error["exception_type"])
            if exception_required
            else error["exception_type"] is None
        ),
        f"{error_class} evidence drift",
    )


def _phase_epoch(phase: object) -> int | None:
    if not isinstance(phase, str):
        return None
    prefix, suffix = "epoch_", "_durable"
    if not (phase.startswith(prefix) and phase.endswith(suffix)):
        return None
    text = phase[len(prefix) : -len(suffix)]
    try:
        epoch = int(text)
    except ValueError:
        return None
    return epoch if phase == f"epoch_{epoch}_durable" else None


def _validate_phase_evidence(result: dict[str, Any]) -> None:
    phase = result["execution_phase"]
    binding = result["runtime_card0_binding"]
    constructor = result["constructor_scope_proof"]
    dispatch = result["dispatch_proof"]
    epochs = result["epochs"]
    epoch = _phase_epoch(phase)
    if phase == "pre_tensor_identity_checkpoint":
        expected = (False, None, None, None, 0)
    elif phase == "tensor_work_started":
        expected = (True, None, None, None, 0)
    elif phase == "runtime_card0_bound":
        expected = (True, True, None, None, 0)
    elif phase == "constructor_scope_durable":
        expected = (True, True, True, None, 0)
    elif phase == "dispatch_proof_durable":
        expected = (True, True, True, True, 0)
    elif epoch is not None and 0 <= epoch < stage0.EPOCHS:
        expected = (True, True, True, True, epoch + 1)
    elif phase == "all_128_epochs_durable":
        expected = (True, True, True, True, stage0.EPOCHS)
    else:
        raise RuntimeError("unknown execution phase")
    tensor_started, has_binding, has_constructor, has_dispatch, epoch_count = expected
    require(
        result["tensor_work_started"] is tensor_started
        and (binding is not None) is bool(has_binding)
        and (constructor is not None) is bool(has_constructor)
        and (dispatch is not None) is bool(has_dispatch)
        and isinstance(epochs, list)
        and len(epochs) == epoch_count,
        "execution phase/evidence boundary drift",
    )


def _epoch(entry: dict[str, Any], fixture_epoch: dict[str, Any]) -> tuple[bool, str]:
    keys = {"epoch", "fixture_epoch_sha256", "input_copies", "outputs", "comparisons"}
    require(
        set(entry) == keys
        and entry["epoch"] == fixture_epoch["epoch"]
        and entry["fixture_epoch_sha256"] == fixture_epoch["epoch_sha256"],
        "epoch identity/order drift",
    )
    inputs = {
        tensor["label"]: tensor["canonical_sha256"]
        for tensor in fixture_epoch["tensors"]
    }
    weights = {
        name: inputs[name] for name in ("gate_weight", "up_weight", "down_weight")
    }
    copies = entry["input_copies"]
    require(
        copies
        == {
            "fixture_before": inputs,
            "after_host_copy": inputs,
            "post_transfer": inputs,
            "layer_weights_after_copy": weights,
            "after_forward": inputs,
            "layer_weights_after_forward": weights,
        },
        "input copy/transfer/weight mutation drift",
    )
    outputs = entry["outputs"]
    require(set(outputs) == set(OUTPUT_SPECS), "output boundary set drift")
    raws = {
        name: _raw(outputs[name], label, shape)
        for name, (label, shape) in OUTPUT_SPECS.items()
    }
    comparisons = entry["comparisons"]
    require(set(comparisons) == set(PAIRINGS), "comparison boundary set drift")
    all_equal = True
    for name, (left, right) in PAIRINGS.items():
        claimed = comparisons[name]
        require(
            set(claimed) == {"raw_uint16_equal", "torch_equal"}
            and all(isinstance(value, bool) for value in claimed.values()),
            "comparison claim schema drift",
        )
        equal = raws[left] == raws[right]
        require(
            claimed["raw_uint16_equal"] is equal,
            f"raw comparison claim disagrees at {name}",
        )
        all_equal = all_equal and equal and claimed["torch_equal"]
    return all_equal, outputs["gate_candidate"]["canonical_sha256"]


def _expected_identity(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(packet[key])
        for key in (
            "tools",
            "source",
            "authorization_tracking",
            "runtime",
            "binaries",
            "model",
            "storage",
            "device",
            "boot_id",
            "protocol",
            "argv",
            "runner_argv",
            "environment",
        )
    }


def _validate_pre_tensor_identity(
    observed: dict[str, Any],
    packet: dict[str, Any],
) -> None:
    require(
        set(observed)
        == {
            "main_authorization_head",
            "frozen_tooling_commit",
            "authorization_commit_shape",
            "vllm",
            "kernels",
            "runtime_files",
            "sysfs_card0",
        },
        "pre-tensor observed identity fields drift",
    )
    main = observed["main_authorization_head"]
    require(
        set(main)
        == {
            "path",
            "commit",
            "clean",
            "status_porcelain",
            "status_sha256",
        }
        and main["path"] == "/home/steve/llm-optimizations"
        and stage0.is_commit(main["commit"])
        and main["commit"] != packet["source"]["main_commit"]
        and main["clean"] is True
        and main["status_porcelain"] == []
        and main["status_sha256"] == stage0.sha256_bytes(b""),
        "main authorization checkout identity drift",
    )
    require(
        observed["frozen_tooling_commit"] == packet["source"]["main_commit"],
        "frozen tooling commit observation drift",
    )
    shape = observed["authorization_commit_shape"]
    require(
        set(shape) == {"parent", "changed_paths", "packet_bytes_sha256"}
        and shape["parent"] == packet["source"]["main_commit"]
        and shape["changed_paths"]
        == [packet["authorization_tracking"]["packet_repo_path"]]
        and shape["packet_bytes_sha256"]
        == stage0.sha256_bytes(stage0.canonical_json_bytes(packet) + b"\n"),
        "authorization-only commit observation drift",
    )
    for name, expected_path, expected_commit in (
        (
            "vllm",
            "/home/steve/src/deepseek-v4-vllm-xpu-dspark",
            stage0.EXPECTED_VLLM_COMMIT,
        ),
        (
            "kernels",
            "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc",
            stage0.EXPECTED_KERNEL_COMMIT,
        ),
    ):
        identity = observed[name]
        require(
            set(identity)
            == {
                "path",
                "commit",
                "clean",
                "status_porcelain",
                "status_sha256",
            }
            and identity["path"] == expected_path
            and identity["commit"] == expected_commit
            and identity["clean"] is True
            and identity["status_porcelain"] == []
            and identity["status_sha256"] == stage0.sha256_bytes(b""),
            f"{name} observed identity drift",
        )
    require(
        observed["runtime_files"] == packet["runtime"]["observed_identity"]["files"],
        "pre-tensor Python/Torch/Level-Zero file identity drift",
    )
    sysfs = observed["sysfs_card0"]
    require(
        sysfs
        == {
            "drm_device": stage0.EXPECTED_CARD0["drm_device"],
            "pci_bdf_address": stage0.EXPECTED_CARD0["pci_bdf_address"],
            "vendor": "0x8086",
            "device": "0xe223",
        },
        "card-0 sysfs observation drift",
    )


def _base_result_check(
    result: dict[str, Any], fixture: dict[str, Any], packet: dict[str, Any]
) -> None:
    require(
        result["format"] == stage0.RESULT_FORMAT
        and result["fixture_manifest_sha256"] == fixture["manifest_sha256"],
        "result format/fixture drift",
    )
    require(
        _utc(result["completed_utc"]) >= _utc(result["started_utc"]),
        "result timestamps inverted",
    )
    authorization = result["authorization_packet"]
    require(
        authorization
        == {"path": packet["packet_path"], "sha256": stage0.packet_digest(packet)},
        "packet path/SHA drift",
    )
    require(
        result["observed_identity"] == _expected_identity(packet),
        "observed identity drift",
    )
    _validate_pre_tensor_identity(result["pre_tensor_identity"], packet)
    require(
        result["downstream"] == {action: False for action in stage0.RESULT_ACTIONS},
        "forbidden result action",
    )


def validate_schema_for_cpu_tests(
    result: dict[str, Any], fixture: dict[str, Any], packet: dict[str, Any]
) -> None:
    stage0.validate_fixture_manifest(fixture)
    stage0.validate_authorization(packet, fixture)
    required = {
        "format",
        "status",
        "passed",
        "terminal",
        "error",
        "started_utc",
        "completed_utc",
        "tensor_work_started",
        "execution_phase",
        "last_durable_checkpoint",
        "authorization_packet",
        "fixture_manifest_sha256",
        "observed_identity",
        "pre_tensor_identity",
        "runtime_card0_binding",
        "constructor_scope_proof",
        "dispatch_proof",
        "epochs",
        "downstream",
        "post_stage0_authorization",
    }
    require(set(result) == required, "result has missing/unrecognized fields")
    _base_result_check(result, fixture, packet)
    require(
        result["execution_phase"] == result["last_durable_checkpoint"],
        "execution phase differs from last durable checkpoint",
    )
    _validate_phase_evidence(result)
    status = result["status"]
    if status == "stage0_pre_tensor_failure":
        require(
            result["passed"] is False
            and result["terminal"] is False
            and result["tensor_work_started"] is False
            and result["execution_phase"] == "pre_tensor_identity_checkpoint"
            and result["last_durable_checkpoint"] == "pre_tensor_identity_checkpoint"
            and result["post_stage0_authorization"]
            == {action: False for action in stage0.PRE_ACTIONS},
            "pre-tensor failure contract drift",
        )
        _validate_error(
            result["error"],
            error_class="identity_or_tooling_failure",
            phase=result["execution_phase"],
            proven=False,
            proof=None,
            exception_required=True,
        )
        return
    binding = result["runtime_card0_binding"]
    if binding is not None:
        validate_runtime_card0_binding(
            binding,
            packet,
            result["pre_tensor_identity"],
        )
    constructor = result["constructor_scope_proof"]
    if constructor is not None:
        validate_constructor_scope(constructor)
    if result["dispatch_proof"] is not None:
        validate_dispatch_proof(result["dispatch_proof"])
    epochs = result["epochs"]
    equalities, gate_hashes = [], []
    for index, entry in enumerate(epochs):
        equal, gate_hash = _epoch(entry, fixture["epochs"][index])
        equalities.append(equal)
        gate_hashes.append(gate_hash)
    if status == "stage0_exactness_pass":
        require(
            result["passed"] is True
            and result["terminal"] is True
            and result["error"] is None
            and result["execution_phase"] == "all_128_epochs_durable"
            and result["last_durable_checkpoint"] == "all_128_epochs_durable"
            and all(equalities)
            and len(set(gate_hashes)) == stage0.EPOCHS
            and result["post_stage0_authorization"] == stage0.PASS_NEXT_ACTIONS,
            "stage0 pass contract drift",
        )
        return
    if status == "stage0_exactness_failed_stop":
        require(bool(epochs), "exactness failure has no durable epoch")
        mismatch_pairings = sorted(
            name
            for name, comparison in epochs[-1]["comparisons"].items()
            if not (comparison["raw_uint16_equal"] and comparison["torch_equal"])
        )
        proof = {
            "kind": "raw_exactness_mismatch",
            "epoch": len(epochs) - 1,
            "pairings": mismatch_pairings,
        }
        require(
            result["passed"] is False
            and result["terminal"] is True
            and len(epochs) >= 1
            and result["execution_phase"] == f"epoch_{len(epochs) - 1}_durable"
            and all(equalities[:-1])
            and not equalities[-1]
            and bool(mismatch_pairings)
            and result["post_stage0_authorization"]
            == {action: False for action in stage0.PRE_ACTIONS},
            "proven exactness failure contract drift",
        )
        _validate_error(
            result["error"],
            error_class="proven_exactness_failure",
            phase=result["execution_phase"],
            proven=True,
            proof=proof,
            exception_required=False,
        )
        return
    require(
        status == "stage0_runtime_infrastructure_failed_stop"
        and result["passed"] is False
        and result["terminal"] is True
        and result["execution_phase"] != "all_128_epochs_durable"
        and all(equalities)
        and result["post_stage0_authorization"]
        == {action: False for action in stage0.PRE_ACTIONS},
        "runtime/infrastructure failure contract drift",
    )
    _validate_error(
        result["error"],
        error_class="runtime_infrastructure_failure",
        phase=result["execution_phase"],
        proven=False,
        proof=None,
        exception_required=True,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _require_canonical_file(path: Path, value: dict[str, Any]) -> None:
    require(path.is_file() and not path.is_symlink(), f"evidence file absent: {path}")
    require(
        path.read_bytes() == stage0.canonical_json_bytes(value) + b"\n",
        f"evidence bytes are not canonical/frozen: {path}",
    )


def _validate_host_state(
    result: dict[str, Any],
    packet: dict[str, Any],
    authorization_path: Path,
) -> None:
    main_repo = Path("/home/steve/llm-optimizations")
    vllm_repo = Path("/home/steve/src/deepseek-v4-vllm-xpu-dspark")
    kernel_repo = Path("/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc")
    expected_runtime = packet["runtime"]["observed_identity"]
    require(
        sys.executable == expected_runtime["python_executable"]
        and sys.version == expected_runtime["python_version"],
        "analyzer Python identity drift",
    )
    for record in expected_runtime["files"].values():
        path = Path(record["path"])
        require(
            path.is_file()
            and str(path.resolve(strict=True)) == record["resolved_path"]
            and _sha256_file(path) == record["sha256"],
            f"runtime file drift during analysis: {path}",
        )
    for repo, expected_commit in (
        (vllm_repo, packet["source"]["vllm_commit"]),
        (kernel_repo, packet["source"]["kernel_commit"]),
    ):
        require(
            _git(repo, "status", "--porcelain=v1", "--untracked-files=all") == ""
            and _git(repo, "rev-parse", "HEAD") == expected_commit,
            f"source checkout drift during analysis: {repo}",
        )
    require(
        _git(main_repo, "status", "--porcelain=v1", "--untracked-files=all") == "",
        "main authorization checkout is not clean during analysis",
    )
    authorization_head = _git(main_repo, "rev-parse", "HEAD")
    require(
        authorization_head
        == result["pre_tensor_identity"]["main_authorization_head"]["commit"]
        and _git(main_repo, "rev-parse", f"{authorization_head}^")
        == packet["source"]["main_commit"],
        "authorization commit identity drift during analysis",
    )
    packet_repo_path = packet["authorization_tracking"]["packet_repo_path"]
    changed_paths = _git(
        main_repo,
        "diff-tree",
        "--no-commit-id",
        "--name-only",
        "-r",
        authorization_head,
    ).splitlines()
    require(
        changed_paths == [packet_repo_path],
        "authorization commit is not packet-only during analysis",
    )
    tracked_packet = subprocess.run(
        [
            "git",
            "-C",
            str(main_repo),
            "show",
            f"{authorization_head}:{packet_repo_path}",
        ],
        check=True,
        capture_output=True,
    ).stdout
    require(
        tracked_packet == authorization_path.read_bytes(),
        "analyzed packet differs from auth-only commit",
    )
    for record in packet["tools"].values():
        path = main_repo / record["path"]
        require(_sha256_file(path) == record["sha256"], f"tool drift: {path}")
    for relative, expected_hash in packet["source"]["files"].items():
        path = vllm_repo / relative
        require(_sha256_file(path) == expected_hash, f"source drift: {path}")
    binaries = {
        "_C.abi3.so": kernel_repo / "vllm_xpu_kernels/_C.abi3.so",
        "_xpu_C.abi3.so": kernel_repo / "vllm_xpu_kernels/_xpu_C.abi3.so",
        "_moe_C.abi3.so": kernel_repo / "vllm_xpu_kernels/_moe_C.abi3.so",
        "libgrouped_gemm_xe_2.so": (
            kernel_repo / "vllm_xpu_kernels/libgrouped_gemm_xe_2.so"
        ),
    }
    for name, path in binaries.items():
        require(_sha256_file(path) == packet["binaries"][name], f"binary drift: {name}")
    model_config = Path(packet["model"]["config_path"])
    require(
        _sha256_file(model_config) == packet["model"]["config_sha256"],
        "model config drift during analysis",
    )
    require(
        Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        == packet["boot_id"],
        "boot drift during analysis",
    )
    sysfs = Path("/sys/class/drm/card3/device").resolve(strict=True)
    require(
        sysfs.name == packet["device"]["pci_bdf_address"]
        and (sysfs / "vendor").read_text().strip() == "0x8086"
        and (sysfs / "device").read_text().strip() == "0xe223",
        "physical card-zero sysfs drift during analysis",
    )


def _validate_evidence_files(
    result: dict[str, Any],
    fixture: dict[str, Any],
    packet: dict[str, Any],
    *,
    fixture_path: Path,
    authorization_path: Path,
    result_path: Path,
) -> None:
    output_root = Path(packet["storage"]["output_root"])
    require(
        fixture_path == Path(packet["fixture"]["path"])
        and authorization_path == Path(packet["packet_path"])
        and result_path == Path(packet["storage"]["result_path"])
        and result_path == output_root / "stage0-result.json",
        "analysis paths differ from authorization packet",
    )
    stage0.require_nvme_artifact_path(output_root, must_exist=True)
    stage0.require_nvme_artifact_path(fixture_path, suffix=".json", must_exist=True)
    stage0.require_nvme_artifact_path(result_path, suffix=".json", must_exist=True)
    require(
        authorization_path.is_file()
        and not authorization_path.is_symlink()
        and authorization_path.resolve(strict=True).is_relative_to(
            Path("/home/steve/llm-optimizations").resolve(strict=True)
        ),
        "authorization evidence path drift",
    )
    _require_canonical_file(authorization_path, packet)
    _require_canonical_file(fixture_path, fixture)
    _require_canonical_file(result_path, result)
    require(
        _sha256_file(fixture_path) == packet["fixture"]["file_sha256"],
        "fixture evidence file SHA drift",
    )
    authorization = result["authorization_packet"]
    downstream = result["downstream"]
    pre_payload = {
        "format": "laguna-shared-gate-m8-stage0-pre-tensor-checkpoint-v1",
        "status": "identity_validated_no_tensor_work",
        "tensor_work_started": False,
        "authorization_packet": authorization,
        "fixture_manifest_sha256": fixture["manifest_sha256"],
        "observed_pre_tensor_identity": result["pre_tensor_identity"],
        "downstream": downstream,
    }
    tensor_payload = {
        "format": "laguna-shared-gate-m8-stage0-tensor-work-started-v1",
        "status": "tensor_work_started_terminal_if_interrupted",
        "tensor_work_started": True,
        "authorization_packet": authorization,
        "fixture_manifest_sha256": fixture["manifest_sha256"],
        "downstream": downstream,
    }
    checkpoint_values: dict[str, dict[str, Any] | None] = {
        "pre-tensor-identity-checkpoint.json": pre_payload,
        "tensor-work-started-checkpoint.json": (
            tensor_payload if result["tensor_work_started"] else None
        ),
        "runtime-card0-binding-checkpoint.json": (
            {
                "format": "laguna-shared-gate-m8-stage0-runtime-card0-binding-v1",
                "tensor_work_started": True,
                "authorization_packet": authorization,
                "runtime_card0_binding": result["runtime_card0_binding"],
                "downstream": downstream,
            }
            if result["runtime_card0_binding"] is not None
            else None
        ),
        "constructor-scope-proof.json": (
            {
                "format": "laguna-shared-gate-m8-stage0-constructor-scope-v1",
                "tensor_work_started": True,
                "authorization_packet": authorization,
                "proof": result["constructor_scope_proof"],
                "downstream": downstream,
            }
            if result["constructor_scope_proof"] is not None
            else None
        ),
        "dispatch-proof.json": (
            {
                "format": "laguna-shared-gate-m8-stage0-dispatch-proof-v1",
                "tensor_work_started": True,
                "authorization_packet": authorization,
                "proof": result["dispatch_proof"],
                "downstream": downstream,
            }
            if result["dispatch_proof"] is not None
            else None
        ),
    }
    expected_root_json = {"stage0-result.json"}
    for filename, value in checkpoint_values.items():
        path = output_root / filename
        if value is None:
            require(
                not path.exists() and not path.is_symlink(),
                f"future proof exists: {path}",
            )
        else:
            _require_canonical_file(path, value)
            expected_root_json.add(filename)
    actual_root_json = {
        path.name
        for path in output_root.iterdir()
        if path.name.endswith(".json") and (path.exists() or path.is_symlink())
    }
    require(
        actual_root_json == expected_root_json,
        "run root has missing/unrecognized JSON evidence",
    )
    epoch_root = output_root / "epochs"
    expected_epoch_files = {
        f"epoch-{entry['epoch']:03d}.json": entry for entry in result["epochs"]
    }
    if epoch_root.exists() or epoch_root.is_symlink():
        require(
            epoch_root.is_dir() and not epoch_root.is_symlink(),
            "epoch evidence root drift",
        )
        actual_epoch_names = {
            path.name
            for path in epoch_root.iterdir()
            if path.exists() or path.is_symlink()
        }
        require(
            actual_epoch_names == set(expected_epoch_files),
            "epoch evidence file set drift",
        )
        for filename, entry in expected_epoch_files.items():
            _require_canonical_file(epoch_root / filename, entry)
    else:
        require(not expected_epoch_files, "durable epochs are absent")


def validate(
    result: dict[str, Any],
    fixture: dict[str, Any],
    packet: dict[str, Any],
    *,
    fixture_path: Path,
    authorization_path: Path,
    result_path: Path,
) -> None:
    """Production validator: schema, durable files, and current host identity."""
    validate_schema_for_cpu_tests(result, fixture, packet)
    _validate_evidence_files(
        result,
        fixture,
        packet,
        fixture_path=fixture_path,
        authorization_path=authorization_path,
        result_path=result_path,
    )
    _validate_host_state(result, packet, authorization_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    fixture, packet, result = (
        json.loads(path.read_text())
        for path in (args.fixture, args.authorization, args.result)
    )
    validate(
        result,
        fixture,
        packet,
        fixture_path=args.fixture,
        authorization_path=args.authorization,
        result_path=args.result,
    )
    print("stage0-valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
