"""CPU-only tamper coverage for the hash-frozen shared-gate stage-zero layer."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

import analyze_laguna_shared_gate_mm_stage0 as analyzer
import gate_laguna_shared_gate_mm_stage0 as stage0


def _hashes() -> dict[str, str]:
    names = [
        *stage0.TOOL_PATHS,
        *stage0.SOURCE_PATHS,
        "fixture_file",
        "main_commit",
    ]
    values = {name: hashlib.sha256(name.encode()).hexdigest() for name in names}
    values["main_commit"] = hashlib.sha1(b"main-commit").hexdigest()
    return values


def _packet(fixture: dict) -> dict:
    return stage0.authorization_template(
        fixture,
        hashes=_hashes(),
        output_root="/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/stage0-frozen-test",
    )


def _raw(shape: tuple[int, ...], epoch: int) -> bytes:
    raw = bytearray(stage0.tensor_byte_count(shape))
    raw[-2:] = (epoch + 1).to_bytes(2, "little")
    return bytes(raw)


def _output(name: str, epoch: int) -> dict:
    label, shape = analyzer.OUTPUT_SPECS[name]
    return stage0.tensor_record(label, shape, _raw(shape, epoch), include_raw=True)


def _dispatch_output(name: str, rows: int, epoch: int) -> dict:
    return stage0.tensor_record(
        f"stage0.dispatch.{name}",
        (rows, stage0.PROJECTION),
        _raw((rows, stage0.PROJECTION), epoch),
        include_raw=True,
    )


def _dispatch_case(
    name: str,
    rows: int,
    *,
    mm: int,
    bmm: int,
    raised: bool,
    marker: bool,
    verifier: bool,
) -> dict:
    actual = expected = None
    if not raised:
        actual = _dispatch_output(name + ".actual", rows, rows)
        expected = _dispatch_output(name + ".expected", rows, rows)
    exception = (
        copy.deepcopy(stage0.DISPATCH_REJECTION_EXCEPTIONS[name]) if raised else None
    )
    return {
        "rows": rows,
        "marker_enabled": marker,
        "verifier_rows": verifier,
        "mm_calls": mm,
        "bmm_calls": bmm,
        "fallback_calls": 0,
        "raised": raised,
        "exception": exception,
        "actual_output": actual,
        "expected_output": expected,
    }


def _dispatch() -> dict:
    proof = {
        "scope": "actual_checkpoint_selected_ColumnParallelLinear.forward",
        "marker_scope": {
            "marked": ["model.layers.1.mlp.shared_expert.gate_proj"],
            "unmarked": [
                "model.layers.1.mlp.shared_expert.up_proj",
                "model.layers.1.mlp.shared_expert.down_proj",
                "dense_mlp",
                "draft",
            ],
        },
    }
    proof["marked_m8"] = _dispatch_case(
        "marked_m8", 8, mm=1, bmm=0, raised=False, marker=True, verifier=True
    )
    proof["unmarked_m8"] = _dispatch_case(
        "unmarked_m8", 8, mm=0, bmm=1, raised=False, marker=False, verifier=True
    )
    proof["prefill_marked_gate"] = _dispatch_case(
        "prefill_marked_gate", 8, mm=0, bmm=1, raised=False, marker=True, verifier=False
    )
    for rows in range(1, 8):
        proof[f"m{rows}"] = _dispatch_case(
            f"m{rows}", rows, mm=0, bmm=1, raised=False, marker=True, verifier=True
        )
    proof["bad_rows"] = _dispatch_case(
        "bad_rows", 8, mm=0, bmm=0, raised=True, marker=True, verifier=True
    )
    proof["bad_weight_layout"] = _dispatch_case(
        "bad_weight_layout", 8, mm=0, bmm=0, raised=True, marker=True, verifier=True
    )
    return proof


def _epoch(fixture_epoch: dict) -> dict:
    inputs = {
        tensor["label"]: tensor["canonical_sha256"]
        for tensor in fixture_epoch["tensors"]
    }
    outputs = {
        name: _output(name, fixture_epoch["epoch"]) for name in analyzer.OUTPUT_SPECS
    }
    weights = {
        name: inputs[name] for name in ("gate_weight", "up_weight", "down_weight")
    }
    return {
        "epoch": fixture_epoch["epoch"],
        "fixture_epoch_sha256": fixture_epoch["epoch_sha256"],
        "input_copies": {
            "fixture_before": inputs,
            "after_host_copy": dict(inputs),
            "post_transfer": dict(inputs),
            "layer_weights_after_copy": weights,
            "after_forward": dict(inputs),
            "layer_weights_after_forward": dict(weights),
        },
        "outputs": outputs,
        "comparisons": {
            name: {"raw_uint16_equal": True, "torch_equal": True}
            for name in analyzer.PAIRINGS
        },
    }


def _result(fixture: dict, packet: dict) -> dict:
    pre_tensor_identity = {
        "main_authorization_head": {
            "path": "/home/steve/llm-optimizations",
            "commit": hashlib.sha1(b"authorization-commit").hexdigest(),
            "clean": True,
            "status_porcelain": [],
            "status_sha256": hashlib.sha256(b"").hexdigest(),
        },
        "frozen_tooling_commit": packet["source"]["main_commit"],
        "authorization_commit_shape": {
            "parent": packet["source"]["main_commit"],
            "changed_paths": [packet["authorization_tracking"]["packet_repo_path"]],
            "packet_bytes_sha256": stage0.sha256_bytes(
                stage0.canonical_json_bytes(packet) + b"\n"
            ),
        },
        "vllm": {
            "path": "/home/steve/src/deepseek-v4-vllm-xpu-dspark",
            "commit": stage0.EXPECTED_VLLM_COMMIT,
            "clean": True,
            "status_porcelain": [],
            "status_sha256": hashlib.sha256(b"").hexdigest(),
        },
        "kernels": {
            "path": "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc",
            "commit": stage0.EXPECTED_KERNEL_COMMIT,
            "clean": True,
            "status_porcelain": [],
            "status_sha256": hashlib.sha256(b"").hexdigest(),
        },
        "runtime_files": copy.deepcopy(packet["runtime"]["observed_identity"]["files"]),
        "sysfs_card0": {
            "drm_device": stage0.EXPECTED_CARD0["drm_device"],
            "pci_bdf_address": stage0.EXPECTED_CARD0["pci_bdf_address"],
            "vendor": "0x8086",
            "device": "0xe223",
        },
    }
    constructor_scope_proof = {
        "constructor": "LagunaMLP_with_committed_LagunaMoE_scope_token",
        "marked_prefix": "model.layers.1.mlp.shared_expert.gate_proj",
        "marked_gate": True,
        "marked_scope_prefix": "model.layers.1.mlp.shared_expert.gate_proj",
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
    }
    return {
        "format": stage0.RESULT_FORMAT,
        "status": "stage0_exactness_pass",
        "passed": True,
        "terminal": True,
        "error": None,
        "started_utc": "2026-07-23T12:00:00Z",
        "completed_utc": "2026-07-23T12:01:00Z",
        "tensor_work_started": True,
        "execution_phase": "all_128_epochs_durable",
        "last_durable_checkpoint": "all_128_epochs_durable",
        "authorization_packet": {
            "path": packet["packet_path"],
            "sha256": stage0.packet_digest(packet),
        },
        "fixture_manifest_sha256": fixture["manifest_sha256"],
        "observed_identity": {
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
        },
        "pre_tensor_identity": pre_tensor_identity,
        "runtime_card0_binding": {
            "oneapi_device_selector": "level_zero:0",
            "ze_affinity_mask": "0",
            "logical_device_id": 0,
            "current_device": 0,
            "visible_device_count": 1,
            "name": stage0.EXPECTED_DEVICE_NAME,
            "tensor_device": "xpu:0",
            "packet_device": copy.deepcopy(packet["device"]),
            "sysfs_card0": copy.deepcopy(pre_tensor_identity["sysfs_card0"]),
            "runtime_identity": copy.deepcopy(packet["runtime"]["observed_identity"]),
        },
        "constructor_scope_proof": constructor_scope_proof,
        "dispatch_proof": _dispatch(),
        "epochs": [_epoch(item) for item in fixture["epochs"]],
        "downstream": {action: False for action in stage0.RESULT_ACTIONS},
        "post_stage0_authorization": dict(stage0.PASS_NEXT_ACTIONS),
    }


@pytest.fixture(scope="module")
def evidence() -> tuple[dict, dict, dict]:
    fixture = stage0.frozen_fixture_manifest()
    packet = _packet(fixture)
    return fixture, packet, _result(fixture, packet)


def _reject(fixture: dict, packet: dict, result: dict) -> None:
    with pytest.raises(RuntimeError):
        analyzer.validate_schema_for_cpu_tests(result, fixture, packet)


def test_canonical_fixture_decodes_finite_bf16(
    evidence: tuple[dict, dict, dict],
) -> None:
    fixture, _, _ = evidence
    stage0.validate_fixture_manifest(fixture)
    assert fixture["case_counts"] == {
        "finite_random": 64,
        "signed_zero_subnormal": 16,
        "bounded_large_finite": 16,
        "cancellation_heavy": 16,
        "bf16_boundary_overlay": 16,
    }
    assert stage0.bf16_all_finite(
        stage0.fixture_bytes(127, 8, (stage0.ROWS, stage0.HIDDEN))
    )
    assert not stage0.bf16_all_finite(b"\x80\x7f")


def test_write_all_retries_short_writes_and_rejects_zero(monkeypatch) -> None:
    chunks: list[bytes] = []

    def short_write(_fd: int, pending: memoryview) -> int:
        size = min(3, len(pending))
        chunks.append(bytes(pending[:size]))
        return size

    monkeypatch.setattr(stage0.os, "write", short_write)
    stage0.write_all(17, b"abcdefgh")
    assert b"".join(chunks) == b"abcdefgh"
    monkeypatch.setattr(stage0.os, "write", lambda _fd, _pending: 0)
    with pytest.raises(RuntimeError, match="short write"):
        stage0.write_all(17, b"x")


def test_authorization_template_rejects_packet_outside_main_repo() -> None:
    fixture = stage0.frozen_fixture_manifest()
    with pytest.raises(RuntimeError, match="inside the main repo"):
        stage0.authorization_template(
            fixture,
            hashes=_hashes(),
            output_root=(
                "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/"
                "stage0-outside-packet-test"
            ),
            packet_path=(
                "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/"
                "authorizations/not-tracked.json"
            ),
        )


def test_full_pass_recomputes_raw_torch_finiteness_and_dispatch(
    evidence: tuple[dict, dict, dict],
) -> None:
    fixture, packet, result = evidence
    analyzer.validate_schema_for_cpu_tests(result, fixture, packet)


def test_production_validator_rejects_schema_only_synthetic_pass(
    evidence: tuple[dict, dict, dict],
    tmp_path: Path,
) -> None:
    fixture, packet, result = evidence
    with pytest.raises(RuntimeError, match="analysis paths"):
        analyzer.validate(
            result,
            fixture,
            packet,
            fixture_path=tmp_path / "fixture.json",
            authorization_path=tmp_path / "authorization.json",
            result_path=tmp_path / "result.json",
        )


def test_packet_rejects_every_identity_and_escalation_boundary(
    evidence: tuple[dict, dict, dict],
) -> None:
    fixture, packet, result = evidence
    targets = [
        (packet["preregistration"], "sha256", "0" * 64),
        (packet["tools"]["fixture_generator"], "path", "wrong.py"),
        (packet["tools"]["runtime_adapter"], "state", "READY"),
        (packet["fixture"], "epoch_count", 127),
        (packet["source"], "vllm_commit", "g" * 40),
        (packet["source"]["files"], stage0.SOURCE_PATHS[0], "0" * 64),
        (packet["runtime"], "eager", False),
        (packet["binaries"], "_C.abi3.so", "0" * 64),
        (packet["model"], "config_sha256", "0" * 64),
        (packet["device"], "uuid", "wrong"),
        (packet, "boot_id", "wrong"),
        (packet["environment"], "TP", "1"),
        (packet["storage"], "output_root", "/media/Corsair/bad"),
        (packet["pre_actions"], "timing_authorized", True),
    ]
    for target, key, replacement in targets:
        old = target[key]
        target[key] = replacement
        try:
            _reject(fixture, packet, result)
        finally:
            target[key] = old
    packet["argv"].append("--unexpected")
    try:
        _reject(fixture, packet, result)
    finally:
        packet["argv"].pop()
    packet["tools"]["cpu_tests"]["extra"] = True
    try:
        _reject(fixture, packet, result)
    finally:
        packet["tools"]["cpu_tests"].pop("extra")


def test_rejects_fixture_seed_case_order_hash_and_tensor_changes(
    evidence: tuple[dict, dict, dict],
) -> None:
    fixture, packet, result = evidence
    targets = [
        (fixture, "base_seed", 1),
        (fixture, "case_formula", "other"),
        (fixture["epochs"][4], "case", 0),
        (fixture["epochs"][2]["tensors"][0], "seed", 0),
        (fixture["epochs"][2]["tensors"][0], "finite", False),
        (fixture["epochs"][2]["tensors"][0], "canonical_sha256", "0" * 64),
        (fixture, "ordered_epoch_hashes_sha256", "0" * 64),
    ]
    for target, key, replacement in targets:
        old = target[key]
        target[key] = replacement
        try:
            _reject(fixture, packet, result)
        finally:
            target[key] = old
    fixture["epochs"].reverse()
    try:
        _reject(fixture, packet, result)
    finally:
        fixture["epochs"].reverse()
    removed = fixture["epochs"][0]["tensors"].pop()
    try:
        _reject(fixture, packet, result)
    finally:
        fixture["epochs"][0]["tensors"].append(removed)


def test_rejects_result_identity_time_failure_and_escalation_tamper(
    evidence: tuple[dict, dict, dict],
) -> None:
    fixture, packet, result = evidence
    targets = [
        (result, "started_utc", "not-a-time"),
        (result, "completed_utc", "2026-07-23T11:00:00Z"),
        (result["authorization_packet"], "sha256", "0" * 64),
        (result["observed_identity"]["runtime"], "eager", False),
        (result["downstream"], "timing_performed", True),
        (result["post_stage0_authorization"], "counter_authorized", True),
        (result, "terminal", False),
    ]
    for target, key, replacement in targets:
        old = target[key]
        target[key] = replacement
        try:
            _reject(fixture, packet, result)
        finally:
            target[key] = old
    result["extra_performance_ms"] = 1
    try:
        _reject(fixture, packet, result)
    finally:
        result.pop("extra_performance_ms")


def test_rejects_copy_raw_torch_nonfinite_replay_and_boundary_tamper(
    evidence: tuple[dict, dict, dict],
) -> None:
    fixture, packet, result = evidence
    targets = [
        (result["epochs"][1]["input_copies"]["post_transfer"], "gate_weight", "0" * 64),
        (result["epochs"][2]["comparisons"]["gate"], "torch_equal", False),
        (
            result["epochs"][3]["outputs"]["gate_candidate"],
            "raw_bf16_le_sha256",
            "0" * 64,
        ),
        (result["epochs"][4]["outputs"]["down_candidate"], "finite", False),
    ]
    for target, key, replacement in targets:
        old = target[key]
        target[key] = replacement
        try:
            _reject(fixture, packet, result)
        finally:
            target[key] = old
    output = result["epochs"][5]["outputs"]["gate_candidate"]
    old_raw = output["raw_bf16_le_base64"]
    output["raw_bf16_le_base64"] = "gH8="  # one BF16 infinity, also wrong length
    try:
        _reject(fixture, packet, result)
    finally:
        output["raw_bf16_le_base64"] = old_raw
    old = {
        name: result["epochs"][1]["outputs"][name]
        for name in ("gate_control", "gate_candidate", "gate_candidate_repeat")
    }
    for name in old:
        result["epochs"][1]["outputs"][name] = copy.deepcopy(
            result["epochs"][0]["outputs"][name]
        )
    try:
        _reject(fixture, packet, result)
    finally:
        result["epochs"][1]["outputs"].update(old)
    result["epochs"].reverse()
    try:
        _reject(fixture, packet, result)
    finally:
        result["epochs"].reverse()


@pytest.mark.parametrize(
    "case",
    [
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
    ],
)
def test_rejects_each_dispatch_case_and_scope_tamper(
    evidence: tuple[dict, dict, dict], case: str
) -> None:
    _, _, result = evidence
    proof = result["dispatch_proof"][case]
    old = proof["fallback_calls"]
    proof["fallback_calls"] = 1
    try:
        with pytest.raises(RuntimeError):
            analyzer.validate_dispatch_proof(result["dispatch_proof"])
    finally:
        proof["fallback_calls"] = old
    marked = result["dispatch_proof"]["marker_scope"]["marked"]
    marked.append("dense_mlp")
    try:
        with pytest.raises(RuntimeError):
            analyzer.validate_dispatch_proof(result["dispatch_proof"])
    finally:
        marked.pop()


@pytest.mark.parametrize("key", ["type", "message"])
def test_rejects_dispatch_exception_identity_tamper(
    evidence: tuple[dict, dict, dict], key: str
) -> None:
    _, _, result = evidence
    exception = result["dispatch_proof"]["bad_rows"]["exception"]
    old = exception[key]
    exception[key] = "wrong"
    try:
        with pytest.raises(RuntimeError):
            analyzer.validate_dispatch_proof(result["dispatch_proof"])
    finally:
        exception[key] = old


def test_runtime_failure_is_phase_bound_and_never_proven(
    evidence: tuple[dict, dict, dict],
) -> None:
    fixture, packet, passing = evidence
    runtime = copy.deepcopy(passing)
    runtime.update(
        {
            "status": "stage0_runtime_infrastructure_failed_stop",
            "passed": False,
            "error": {
                "class": "runtime_infrastructure_failure",
                "phase": "dispatch_proof_durable",
                "exception_type": "RuntimeError",
                "message": "driver stopped",
                "proven": False,
                "proof": None,
            },
            "execution_phase": "dispatch_proof_durable",
            "last_durable_checkpoint": "dispatch_proof_durable",
            "epochs": [],
            "post_stage0_authorization": {
                action: False for action in stage0.PRE_ACTIONS
            },
        }
    )
    analyzer.validate_schema_for_cpu_tests(runtime, fixture, packet)
    runtime["error"]["proven"] = True
    _reject(fixture, packet, runtime)
    runtime["error"]["proven"] = False
    runtime["runtime_card0_binding"] = None
    _reject(fixture, packet, runtime)


def test_tensor_started_runtime_failure_cannot_claim_later_evidence(
    evidence: tuple[dict, dict, dict],
) -> None:
    fixture, packet, passing = evidence
    runtime = copy.deepcopy(passing)
    runtime.update(
        {
            "status": "stage0_runtime_infrastructure_failed_stop",
            "passed": False,
            "error": {
                "class": "runtime_infrastructure_failure",
                "phase": "tensor_work_started",
                "exception_type": "ImportError",
                "message": "torch import failed",
                "proven": False,
                "proof": None,
            },
            "execution_phase": "tensor_work_started",
            "last_durable_checkpoint": "tensor_work_started",
            "runtime_card0_binding": None,
            "constructor_scope_proof": None,
            "dispatch_proof": None,
            "epochs": [],
            "post_stage0_authorization": {
                action: False for action in stage0.PRE_ACTIONS
            },
        }
    )
    analyzer.validate_schema_for_cpu_tests(runtime, fixture, packet)
    runtime["constructor_scope_proof"] = copy.deepcopy(
        passing["constructor_scope_proof"]
    )
    _reject(fixture, packet, runtime)


def test_pre_and_post_tensor_failure_contracts(
    evidence: tuple[dict, dict, dict],
) -> None:
    fixture, packet, result = evidence
    pre = copy.copy(result)
    pre.update(
        {
            "status": "stage0_pre_tensor_failure",
            "passed": False,
            "terminal": False,
            "error": {
                "class": "identity_or_tooling_failure",
                "phase": "pre_tensor_identity_checkpoint",
                "exception_type": "RuntimeError",
                "message": "fixture checksum failed",
                "proven": False,
                "proof": None,
            },
            "tensor_work_started": False,
            "execution_phase": "pre_tensor_identity_checkpoint",
            "last_durable_checkpoint": "pre_tensor_identity_checkpoint",
            "runtime_card0_binding": None,
            "constructor_scope_proof": None,
            "dispatch_proof": None,
            "epochs": [],
            "post_stage0_authorization": {
                action: False for action in stage0.PRE_ACTIONS
            },
        }
    )
    analyzer.validate_schema_for_cpu_tests(pre, fixture, packet)
    pre["terminal"] = True
    _reject(fixture, packet, pre)
    post = copy.copy(result)
    post.update(
        {
            "status": "stage0_exactness_failed_stop",
            "passed": False,
            "error": {
                "class": "proven_exactness_failure",
                "phase": "epoch_0_durable",
                "exception_type": None,
                "message": "bitwise exactness mismatch at epoch 0",
                "proven": True,
                "proof": {
                    "kind": "raw_exactness_mismatch",
                    "epoch": 0,
                    "pairings": ["gate"],
                },
            },
            "execution_phase": "epoch_0_durable",
            "last_durable_checkpoint": "epoch_0_durable",
            "epochs": [copy.deepcopy(result["epochs"][0])],
            "post_stage0_authorization": {
                action: False for action in stage0.PRE_ACTIONS
            },
        }
    )
    post["epochs"][0]["outputs"]["gate_candidate"]["raw_bf16_le_base64"] = post[
        "epochs"
    ][0]["outputs"]["gate_control"]["raw_bf16_le_base64"]
    # Replace a valid raw word and its hashes to create an independently visible mismatch.
    raw = bytearray(_raw((stage0.ROWS, stage0.PROJECTION), 77))
    post["epochs"][0]["outputs"]["gate_candidate"] = stage0.tensor_record(
        "stage0.gate.candidate",
        (stage0.ROWS, stage0.PROJECTION),
        bytes(raw),
        include_raw=True,
    )
    post["epochs"][0]["outputs"]["gate_candidate_repeat"] = stage0.tensor_record(
        "stage0.gate.candidate_repeat",
        (stage0.ROWS, stage0.PROJECTION),
        bytes(raw),
        include_raw=True,
    )
    post["epochs"][0]["comparisons"]["gate"] = {
        "raw_uint16_equal": False,
        "torch_equal": False,
    }
    analyzer.validate_schema_for_cpu_tests(post, fixture, packet)


def test_rejects_path_escape_and_symlink(tmp_path) -> None:
    with pytest.raises(RuntimeError):
        stage0.require_nvme_artifact_path(
            Path("/media/Corsair/nope.json"), suffix=".json"
        )
    escaped = stage0.ARTIFACT_ROOT_LITERAL / "stage0-symlink-test"
    if escaped.exists() or escaped.is_symlink():
        pytest.skip("shared artifact root already contains test name")
    escaped.symlink_to(tmp_path, target_is_directory=True)
    try:
        with pytest.raises(RuntimeError):
            stage0.require_nvme_artifact_path(escaped / "x.json", suffix=".json")
    finally:
        escaped.unlink()
