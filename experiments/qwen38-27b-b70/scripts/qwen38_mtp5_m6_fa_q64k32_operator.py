#!/usr/bin/env python3
"""Qwen3.8 MTP5/M6 Q64xK32 FlashAttention operator qualifier.

This campaign deliberately reuses the frozen exact-shape CPU oracle, mutation
inventory, XPU graph checks, and ABBA statistics from the prior qualifier.  It
adds fail-closed immutable failure packets so a candidate correctness failure
retains its stderr marker and mapped-library evidence before the process exits.
"""

from __future__ import annotations

import argparse
import copy
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import statistics
import sys
import time
from typing import Any


BASE_QUALIFIER = Path(__file__).with_name("qwen38_mtp5_m6_fa_operator.py")
BASE_QUALIFIER_SHA256 = (
    "0dd7b945ef35a11ff4d0a1ec085e604920524b996d539e089d89b4a019a5de1f"
)


def _sha256_file_local(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


if _sha256_file_local(BASE_QUALIFIER) != BASE_QUALIFIER_SHA256:
    raise RuntimeError("frozen base FlashAttention qualifier SHA mismatch")
_BASE_SPEC = importlib.util.spec_from_file_location(
    "qwen38_mtp5_m6_fa_operator_q64k32_base", BASE_QUALIFIER
)
if _BASE_SPEC is None or _BASE_SPEC.loader is None:
    raise RuntimeError("cannot load frozen base FlashAttention qualifier")
BASE = importlib.util.module_from_spec(_BASE_SPEC)
_BASE_SPEC.loader.exec_module(BASE)


SCHEMA_RUN = "qwen38-mtp5-m6-fa-q64k32-operator-run-v1"
SCHEMA_FAILURE = "qwen38-mtp5-m6-fa-q64k32-operator-failure-v1"
SCHEMA_COMPARE = "qwen38-mtp5-m6-fa-q64k32-operator-compare-v1"
SCHEMA_STAGE = "qwen38-mtp5-m6-fa-q64k32-r3-stage-v1"
POLICY_ENV = "VLLM_XPU_FA2_M6_HEAD256_Q64K32_POLICY"
POLICY_MARKER = "VLLM_XPU_FA2_M6_HEAD256_Q64K32_POLICY engaged"
POLICY_IDENTITY_KEY = "m6_head256_q64k32_policy"

# These source/build inputs are immutable prerequisites for candidate stages.
CANDIDATE_PATCH = Path(
    "/home/steve/llm-optimizations/experiments/qwen38-27b-b70/patches/"
    "vllm-xpu-kernels-qwen38-m6-head256-q64k32-chunk-prefill-r2-20260821.patch"
)
CANDIDATE_PATCH_SHA256 = (
    "9386432015f5c9cd330dd7cfb785a16f259cce8563f44da9f812dcceb342138a"
)
BUILD_HELPER = Path(
    "/home/steve/llm-optimizations/experiments/qwen38-27b-b70/scripts/"
    "build-qwen38-m6-head256-q64k32-attn-override-r3-20260821.sh"
)
BUILD_HELPER_SHA256 = "1e86bed65c4f757aa01eee540119a48e4e505526f8f66eb0ebe7099160318af9"
BUILD_INPUTS_BASENAME = "qwen38-m6-head256-q64k32-r3-build-inputs.sha256"
GRAPH_MANIFEST_BASENAME = "qwen38-m6-head256-q64k32-r3-candidate.graph.sha256"

# Configure the separately loaded base module process-locally.  All reused
# validators resolve these globals at call time.
BASE.SCHEMA_RUN = SCHEMA_RUN
BASE.SCHEMA_COMPARE = SCHEMA_COMPARE
BASE.SCHEMA_STAGE = SCHEMA_STAGE
BASE.POLICY_ENV = POLICY_ENV
BASE.POLICY_MARKER = POLICY_MARKER
BASE.CANDIDATE_PATCH = CANDIDATE_PATCH
BASE.CANDIDATE_PATCH_SHA256 = CANDIDATE_PATCH_SHA256
BASE.BUILD_HELPER = BUILD_HELPER
BASE.BUILD_HELPER_SHA256 = BUILD_HELPER_SHA256
BASE.BUILD_INPUTS_BASENAME = BUILD_INPUTS_BASENAME
BASE.GRAPH_MANIFEST_BASENAME = GRAPH_MANIFEST_BASENAME

ContractError = BASE.ContractError
CONTROL_STAGE = BASE.CONTROL_STAGE
CONTROL_HASHES = BASE.CONTROL_HASHES
RELATIVE_FILES = BASE.RELATIVE_FILES
KV_LENGTHS = BASE.KV_LENGTHS
ROWS = BASE.ROWS
Q_HEADS = BASE.Q_HEADS
KV_HEADS = BASE.KV_HEADS
HEAD_DIM = BASE.HEAD_DIM
BLOCK_SIZE = BASE.BLOCK_SIZE
MIN_SAMPLES = BASE.MIN_SAMPLES
MIN_LAUNCHES_PER_SAMPLE = BASE.MIN_LAUNCHES_PER_SAMPLE
MIN_STABILITY_REPLAYS = BASE.MIN_STABILITY_REPLAYS
EXPECTED_PHYSICAL_GPUS = BASE.EXPECTED_PHYSICAL_GPUS
EXPECTED_DEVICE_NAME = BASE.EXPECTED_DEVICE_NAME
MIN_SAVING_US_PER_CALL = BASE.MIN_SAVING_US_PER_CALL
MIN_SAVING_MS_PER_16 = BASE.MIN_SAVING_MS_PER_16
MAX_KV128_REGRESSION_US_PER_CALL = BASE.MAX_KV128_REGRESSION_US_PER_CALL

load_json = BASE.load_json
require_exact_keys = BASE.require_exact_keys
require_int = BASE.require_int
require_finite = BASE.require_finite
sha256_file = BASE.sha256_file
write_json_atomic = BASE.write_json_atomic
parse_sha256_manifest = BASE.parse_sha256_manifest
validate_candidate_manifest = BASE.validate_candidate_manifest
control_identity = BASE.control_identity
stage_identity = BASE.stage_identity
mapped_paths = BASE.mapped_paths


class RecordedArmFailure(ContractError):
    """An arm failed after its immutable failure evidence was published."""


def _operator_identity(expected_policy: str) -> dict[str, Any]:
    return {
        "dtype": "float16",
        "rows": ROWS,
        "mtp_depth": ROWS - 1,
        "q_heads_tp2_local": Q_HEADS,
        "kv_heads_tp2_local": KV_HEADS,
        "head_dim": HEAD_DIM,
        "block_size": BLOCK_SIZE,
        "kv_lengths": list(KV_LENGTHS),
        "causal": True,
        "paged_kv": True,
        "is_mix_batch": True,
        "vllm_xpu_fa2_force_chunk_decode": "1",
        POLICY_IDENTITY_KEY: expected_policy,
    }


def _process_identity(started_ns: int) -> dict[str, Any]:
    process_stat = Path("/proc/self/stat").read_text(encoding="utf-8").split()
    return {
        "pid": os.getpid(),
        "start_ticks": require_int(int(process_stat[21]), "process start ticks"),
        "boot_id": Path("/proc/sys/kernel/random/boot_id")
        .read_text(encoding="utf-8")
        .strip(),
        "started_time_ns": started_ns,
        "finished_time_ns": time.time_ns(),
    }


def _runtime_identity(
    torch: Any,
    driver_path: Path,
    driver_sha: str,
    repo_head: str,
    args: argparse.Namespace,
    pythonpath: list[str],
    ld_library_path: list[str],
) -> dict[str, Any]:
    return {
        "script_path": str(Path(__file__).resolve()),
        "script_sha256": sha256_file(Path(__file__).resolve()),
        "base_qualifier_path": str(BASE_QUALIFIER.resolve(strict=True)),
        "base_qualifier_sha256": BASE_QUALIFIER_SHA256,
        "campaign_driver_path": str(driver_path),
        "campaign_driver_sha256": driver_sha,
        "lab_repo_head": repo_head,
        "python": sys.version,
        "python_dont_write_bytecode": True,
        "torch_version": torch.__version__,
        "xpu_device_count": torch.xpu.device_count(),
        "hostname": socket.gethostname(),
        "physical_gpu": args.physical_gpu,
        "logical_device": "xpu:0",
        "ze_affinity_mask": os.environ["ZE_AFFINITY_MASK"],
        "device_name": torch.xpu.get_device_name(0),
        "device_properties": BASE._device_properties(torch, 0),
        "pythonpath_first": pythonpath[0],
        "ld_library_path_first": ld_library_path[0],
    }


def _timing_contract(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "clock": "torch.xpu.Event device elapsed time",
        "samples_per_shape_mode": args.samples,
        "launches_per_sample": args.launches_per_sample,
        "stability_replays_per_shape_mode": args.stability_replays,
        "gated_mode": "xpu_graph_replay",
    }


def _engagement_evidence(stderr_bytes: bytes, role: str) -> dict[str, Any]:
    expected_lines = [] if role == "control" else [POLICY_MARKER]
    decode_error: str | None = None
    try:
        stderr_text = stderr_bytes.decode("utf-8")
        stderr_lines = stderr_text.splitlines()
        marker_lines = [line for line in stderr_lines if POLICY_ENV in line]
    except UnicodeError as error:
        decode_error = f"stderr is not strict UTF-8: {error}"
        stderr_lines = []
        marker_lines = []
    return {
        "policy_env": POLICY_ENV,
        "policy_value": "0" if role == "control" else "1",
        "expected_marker_lines": expected_lines,
        "observed_marker_lines": marker_lines,
        "marker_gate_passed": decode_error is None and marker_lines == expected_lines,
        "stderr_decode_error": decode_error,
        "stderr_line_count": len(stderr_lines),
    }


def _mapping_evidence(identity: dict[str, Any]) -> dict[str, Any]:
    required = {
        name: Path(identity["files"][name]["path"])
        for name in ("extension", "device_library", "stock_library")
    }
    matched: dict[str, dict[str, str] | None] = {name: None for name in required}
    same_basename_paths: dict[str, list[str]] = {name: [] for name in required}
    error_text: str | None = None
    try:
        mappings = mapped_paths({path.name for path in required.values()})
        for name, path in required.items():
            same_basename_paths[name] = sorted(
                str(item) for item in mappings if item.name == path.name
            )
            if path in mappings:
                matched[name] = {
                    "path": str(path),
                    "sha256": identity["files"][name]["sha256"],
                }
    except Exception as error:  # preserve a receipt even for procfs/I/O failures
        error_text = str(error)
    passed = error_text is None and all(value is not None for value in matched.values())
    return {
        "required": {
            name: {
                "path": str(path),
                "sha256": identity["files"][name]["sha256"],
            }
            for name, path in required.items()
        },
        "matched": matched,
        "same_basename_paths": same_basename_paths,
        "mapping_gate_passed": passed,
        "mapping_error": error_text,
    }


_ASSERT_CLOSE_PATTERN = re.compile(
    r"(?P<where>KV (?P<kv>\d+) (?:(?:\S+) )?(?P<mode>eager|graph)"
    r"(?: (?P<replay>\d+))?) differs from "
    r"CPU oracle:.*?Mismatched elements: (?P<mismatch>\d+) / "
    r"(?P<elements>\d+) \((?P<percent>[^)]+)\).*?"
    r"Greatest absolute difference: (?P<absolute>[-+0-9.eE]+) at index "
    r"\((?P<absolute_index>[^)]+)\) \(up to (?P<atol>[-+0-9.eE]+) "
    r"allowed\).*?Greatest relative difference: "
    r"(?P<relative>[-+0-9.eE]+) at index \((?P<relative_index>[^)]+)\) "
    r"\(up to (?P<rtol>[-+0-9.eE]+) allowed\)",
    re.DOTALL,
)

_CORRECTNESS_FAILURE_PATTERNS = (
    ("poison-not-overwritten", re.compile(r"^KV \d+ .+ left poisoned NaNs$")),
    (
        "caller-output-not-honored",
        re.compile(
            r"^KV \d+ (?:eager call ignored static out|"
            r"graph capture ignored static out|"
            r"post-mutation eager call ignored out|"
            r"mutation .+ ignored eager out)$"
        ),
    ),
    ("bit-instability", re.compile(r"^KV \d+ .+ is not bit-stable$")),
    (
        "eager-graph-bit-mismatch",
        re.compile(
            r"^KV \d+ (?:eager and graph outputs differ bitwise|"
            r"mutation .+ eager/graph mismatch)$"
        ),
    ),
    ("mutation-output-inert", re.compile(r"^KV \d+ mutation .+ was output-inert$")),
)


def _index_list(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",")]


def failure_error_metadata(
    error: Exception, current_kv_length: int | None
) -> dict[str, Any]:
    message = str(error)
    match = _ASSERT_CLOSE_PATTERN.search(message)
    metadata: dict[str, Any] = {
        "exception_type": type(error).__name__,
        "message": message,
        "phase": "operator-case" if current_kv_length is not None else "post-case-gate",
        "correctness_kind": None,
        "kv_length": current_kv_length,
        "mode": None,
        "replay_index": None,
        "mismatched_elements": None,
        "element_count": None,
        "mismatch_percent_displayed": None,
        "greatest_absolute_difference": None,
        "greatest_absolute_difference_index": None,
        "absolute_tolerance": None,
        "greatest_relative_difference": None,
        "greatest_relative_difference_index": None,
        "relative_tolerance": None,
    }
    if match is not None:
        metadata.update(
            {
                "phase": "checked-cpu-oracle-replay",
                "correctness_kind": "cpu-oracle-mismatch",
                "kv_length": int(match.group("kv")),
                "mode": match.group("mode"),
                "replay_index": (
                    None
                    if match.group("replay") is None
                    else int(match.group("replay"))
                ),
                "mismatched_elements": int(match.group("mismatch")),
                "element_count": int(match.group("elements")),
                "mismatch_percent_displayed": match.group("percent"),
                "greatest_absolute_difference": float(match.group("absolute")),
                "greatest_absolute_difference_index": _index_list(
                    match.group("absolute_index")
                ),
                "absolute_tolerance": float(match.group("atol")),
                "greatest_relative_difference": float(match.group("relative")),
                "greatest_relative_difference_index": _index_list(
                    match.group("relative_index")
                ),
                "relative_tolerance": float(match.group("rtol")),
            }
        )
    elif current_kv_length is not None:
        for correctness_kind, pattern in _CORRECTNESS_FAILURE_PATTERNS:
            if pattern.fullmatch(message):
                metadata["phase"] = "checked-operator-correctness"
                metadata["correctness_kind"] = correctness_kind
                break
    return metadata


def _publish_stderr(stderr_temporary: Path, stderr_output: Path) -> bytes:
    raw = stderr_temporary.read_bytes()
    os.chmod(stderr_temporary, 0o444)
    os.replace(stderr_temporary, stderr_output)
    directory_descriptor = os.open(stderr_output.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)
    return raw


def _failure_packet(
    *,
    args: argparse.Namespace,
    identity: dict[str, Any],
    runtime_identity: dict[str, Any],
    timing_contract: dict[str, Any],
    started_ns: int,
    completed_cases: list[dict[str, Any]],
    current_kv_length: int | None,
    error: Exception,
    engagement: dict[str, Any],
    mapping_evidence: dict[str, Any],
    stderr_output: Path,
    stderr_sha256: str,
    output: Path,
    failure_output: Path,
) -> dict[str, Any]:
    error_metadata = failure_error_metadata(error, current_kv_length)
    classification = failure_classification(
        args.role,
        error_metadata["correctness_kind"],
        engagement["marker_gate_passed"],
        mapping_evidence["mapping_gate_passed"],
    )
    engagement_record = dict(engagement)
    engagement_record.update(
        {
            "stderr_log_path": str(stderr_output.resolve(strict=True)),
            "stderr_log_sha256": stderr_sha256,
        }
    )
    return {
        "schema": SCHEMA_FAILURE,
        "passed": False,
        "classification": classification,
        "role": args.role,
        "arm_id": args.arm_id,
        "campaign_slot": args.campaign_slot,
        "process": _process_identity(started_ns),
        "operator_identity": _operator_identity("0" if args.role == "control" else "1"),
        "stage_identity": identity,
        "engagement": engagement_record,
        "mapping_evidence": mapping_evidence,
        "runtime_identity": runtime_identity,
        "timing_contract": timing_contract,
        "completed_cases": completed_cases,
        "failure": error_metadata,
        "output_contract": {
            "success_packet_path": str(output),
            "success_packet_persisted": False,
            "failure_packet_path": str(failure_output),
            "stderr_persisted": True,
        },
    }


def failure_classification(
    role: str,
    correctness_kind: str | None,
    marker_gate_passed: bool,
    mapping_gate_passed: bool,
) -> str:
    engagement_valid = marker_gate_passed is True and mapping_gate_passed is True
    if correctness_kind is not None and engagement_valid:
        return f"{role}-correctness-failure"
    if not engagement_valid:
        return "arm-failure-with-incomplete-or-invalid-engagement"
    return "arm-valid-engagement-unclassified-operator-or-runtime-failure"


def run_xpu(args: argparse.Namespace) -> dict[str, Any]:
    output = Path(args.output)
    temporary = Path(f"{output}.tmp")
    stderr_output = Path(f"{output}.stderr.log")
    stderr_temporary = Path(f"{stderr_output}.tmp")
    failure_output = Path(f"{output}.failure.json")
    failure_temporary = Path(f"{failure_output}.tmp")
    collision_paths = (
        output,
        temporary,
        stderr_output,
        stderr_temporary,
        failure_output,
        failure_temporary,
    )
    if any(path.exists() for path in collision_paths):
        raise ContractError(
            "refusing existing success/failure/stderr output or temporary path: "
            f"{output}"
        )

    started_ns = time.time_ns()
    identity = stage_identity(args)
    stage = Path(identity["stage"])
    if os.environ.get("VLLM_XPU_FA2_FORCE_CHUNK_DECODE") != "1":
        raise ContractError("VLLM_XPU_FA2_FORCE_CHUNK_DECODE must equal 1")
    expected_policy = "0" if args.role == "control" else "1"
    if os.environ.get(POLICY_ENV) != expected_policy:
        raise ContractError(
            f"{POLICY_ENV} must equal {expected_policy} for role {args.role}"
        )
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1" or not sys.dont_write_bytecode:
        raise ContractError(
            "PYTHONDONTWRITEBYTECODE=1 is required for sealed stage inventory"
        )
    pythonpath = os.environ.get("PYTHONPATH", "").split(os.pathsep)
    ld_library_path = os.environ.get("LD_LIBRARY_PATH", "").split(os.pathsep)
    if not pythonpath or Path(pythonpath[0]).resolve() != stage:
        raise ContractError("selected stage must be first in PYTHONPATH")
    if (
        not ld_library_path
        or Path(ld_library_path[0]).resolve() != stage / "vllm_xpu_kernels"
    ):
        raise ContractError("selected stage package must be first in LD_LIBRARY_PATH")
    if args.physical_gpu not in EXPECTED_PHYSICAL_GPUS:
        raise ContractError(
            f"physical GPU must be one of the preregistered {EXPECTED_PHYSICAL_GPUS}"
        )
    if os.environ.get("ZE_AFFINITY_MASK") != str(args.physical_gpu):
        raise ContractError("ZE_AFFINITY_MASK must select exactly the physical GPU")
    driver_text = os.environ.get("QWEN38_FA_Q64K32_CAMPAIGN_DRIVER")
    driver_sha = os.environ.get("QWEN38_FA_Q64K32_CAMPAIGN_DRIVER_SHA256")
    repo_head = os.environ.get("QWEN38_FA_Q64K32_LAB_REPO_HEAD")
    if not driver_text or not driver_sha or not repo_head:
        raise ContractError("campaign driver path/SHA and lab repo HEAD are required")
    driver_path = BASE._canonical_absolute(driver_text, "campaign driver")
    if sha256_file(driver_path) != driver_sha:
        raise ContractError("campaign driver SHA mismatch")

    import torch  # pylint: disable=import-outside-toplevel

    if not torch.xpu.is_available():
        raise ContractError("XPU is unavailable")
    if torch.xpu.device_count() != 1:
        raise ContractError(
            f"expected exactly one affinity-scoped XPU, got {torch.xpu.device_count()}"
        )
    if not hasattr(torch.xpu, "XPUGraph") or not hasattr(torch.xpu, "graph"):
        raise ContractError("this PyTorch build lacks XPU graph support")
    torch.xpu.set_device(0)
    interface = __import__(
        "vllm_xpu_kernels.flash_attn_interface", fromlist=["flash_attn_varlen_func"]
    )
    extension = __import__("vllm_xpu_kernels._vllm_fa2_C", fromlist=["*"])
    if not bool(getattr(interface, "FA2_AVAILABLE", False)):
        raise ContractError(
            f"staged FA extension unavailable: {interface.FA2_UNAVAILABLE_REASON}"
        )
    if Path(interface.__file__).resolve() != Path(
        identity["files"]["interface"]["path"]
    ):
        raise ContractError(
            "imported FlashAttention interface is outside selected stage"
        )
    if Path(extension.__file__).resolve() != Path(
        identity["files"]["extension"]["path"]
    ):
        raise ContractError("imported FA extension is outside selected stage")

    runtime_identity = _runtime_identity(
        torch, driver_path, driver_sha, repo_head, args, pythonpath, ld_library_path
    )
    timing_contract = _timing_contract(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    completed_cases: list[dict[str, Any]] = []
    current_kv_length: int | None = None
    case_error: Exception | None = None
    saved_stderr = os.dup(2)
    try:
        with stderr_temporary.open("xb") as stderr_stream:
            os.dup2(stderr_stream.fileno(), 2)
            try:
                for current_kv_length in KV_LENGTHS:
                    completed_cases.append(
                        BASE._run_case(
                            torch,
                            interface.flash_attn_varlen_func,
                            0,
                            current_kv_length,
                            args.samples,
                            args.launches_per_sample,
                            args.stability_replays,
                        )
                    )
                current_kv_length = None
            except Exception as error:  # evidence must survive a checked arm failure
                case_error = error
            finally:
                sys.stderr.flush()
                ctypes.CDLL(None).fflush(None)
                os.fsync(stderr_stream.fileno())
                os.dup2(saved_stderr, 2)
    finally:
        os.close(saved_stderr)

    stderr_bytes = _publish_stderr(stderr_temporary, stderr_output)
    stderr_sha256 = sha256_file(stderr_output)
    engagement = _engagement_evidence(stderr_bytes, args.role)
    mapping_evidence = _mapping_evidence(identity)
    gate_errors: list[str] = []
    if engagement["marker_gate_passed"] is not True:
        gate_errors.append(
            "policy marker mismatch: "
            f"actual={engagement['observed_marker_lines']} "
            f"expected={engagement['expected_marker_lines']}"
        )
    if mapping_evidence["mapping_gate_passed"] is not True:
        gate_errors.append(
            "mapped-library proof failed: "
            f"error={mapping_evidence['mapping_error']} "
            f"matched={mapping_evidence['matched']}"
        )

    if case_error is not None or gate_errors:
        failure_error: Exception = case_error or ContractError("; ".join(gate_errors))
        failure_packet = _failure_packet(
            args=args,
            identity=identity,
            runtime_identity=runtime_identity,
            timing_contract=timing_contract,
            started_ns=started_ns,
            completed_cases=completed_cases,
            current_kv_length=current_kv_length,
            error=failure_error,
            engagement=engagement,
            mapping_evidence=mapping_evidence,
            stderr_output=stderr_output,
            stderr_sha256=stderr_sha256,
            output=output,
            failure_output=failure_output,
        )
        write_json_atomic(failure_output, failure_temporary, failure_packet)
        raise RecordedArmFailure(
            f"{failure_error}; immutable failure packet={failure_output}"
        )

    mapped_libraries = {
        name: value
        for name, value in mapping_evidence["matched"].items()
        if value is not None
    }
    engagement_success = {
        "policy_env": POLICY_ENV,
        "policy_value": expected_policy,
        "expected_marker_count": 0 if args.role == "control" else 1,
        "marker_count": len(engagement["observed_marker_lines"]),
        "marker": None if args.role == "control" else POLICY_MARKER,
        "stderr_log_path": str(stderr_output.resolve(strict=True)),
        "stderr_log_sha256": stderr_sha256,
        "stderr_line_count": engagement["stderr_line_count"],
    }
    packet = {
        "schema": SCHEMA_RUN,
        "passed": True,
        "role": args.role,
        "arm_id": args.arm_id,
        "campaign_slot": args.campaign_slot,
        "process": _process_identity(started_ns),
        "operator_identity": _operator_identity(expected_policy),
        "stage_identity": identity,
        "mapped_libraries": mapped_libraries,
        "engagement": engagement_success,
        "runtime_identity": runtime_identity,
        "timing_contract": timing_contract,
        "cases": completed_cases,
    }
    write_json_atomic(output, temporary, packet)
    return packet


_RUNTIME_KEYS = (
    "script_path",
    "script_sha256",
    "base_qualifier_path",
    "base_qualifier_sha256",
    "campaign_driver_path",
    "campaign_driver_sha256",
    "lab_repo_head",
    "python",
    "python_dont_write_bytecode",
    "torch_version",
    "xpu_device_count",
    "hostname",
    "physical_gpu",
    "logical_device",
    "ze_affinity_mask",
    "device_name",
    "device_properties",
    "pythonpath_first",
    "ld_library_path_first",
)


def _translate_success_for_base(packet: dict[str, Any]) -> dict[str, Any]:
    translated = copy.deepcopy(packet)
    operator = translated["operator_identity"]
    operator["m6_head256_q8k64_policy"] = operator.pop(POLICY_IDENTITY_KEY)
    runtime = translated["runtime_identity"]
    runtime.pop("base_qualifier_path")
    runtime.pop("base_qualifier_sha256")
    return translated


def _validate_runtime_identity(runtime: Any, path: Path) -> None:
    if not isinstance(runtime, dict):
        raise ContractError(f"{path}: runtime identity must be an object")
    require_exact_keys(runtime, _RUNTIME_KEYS, f"{path}.runtime_identity")
    if runtime["script_path"] != str(Path(__file__).resolve()) or runtime[
        "script_sha256"
    ] != sha256_file(Path(__file__).resolve()):
        raise ContractError(f"{path}: Q64xK32 qualifier identity mismatch")
    if (
        runtime["base_qualifier_path"] != str(BASE_QUALIFIER.resolve(strict=True))
        or runtime["base_qualifier_sha256"] != BASE_QUALIFIER_SHA256
    ):
        raise ContractError(f"{path}: frozen base qualifier identity mismatch")
    if (
        runtime["python_dont_write_bytecode"] is not True
        or runtime["xpu_device_count"] != 1
        or runtime["physical_gpu"] not in EXPECTED_PHYSICAL_GPUS
        or runtime["logical_device"] != "xpu:0"
        or runtime["ze_affinity_mask"] != str(runtime["physical_gpu"])
        or runtime["device_name"] != EXPECTED_DEVICE_NAME
        or not isinstance(runtime["hostname"], str)
        or not runtime["hostname"]
        or not isinstance(runtime["python"], str)
        or not runtime["python"]
        or not isinstance(runtime["torch_version"], str)
        or not runtime["torch_version"]
        or not isinstance(runtime["device_properties"], dict)
    ):
        raise ContractError(f"{path}: failure runtime/device identity mismatch")
    for name in ("campaign_driver_sha256", "script_sha256"):
        _require_sha256(runtime[name], f"{path}.runtime_identity.{name}")
    if not re.fullmatch(r"[0-9a-f]{40}", runtime["lab_repo_head"]):
        raise ContractError(f"{path}: malformed lab repository HEAD")
    if not isinstance(runtime["campaign_driver_path"], str):
        raise ContractError(f"{path}: malformed failure campaign driver path")
    driver_path = Path(runtime["campaign_driver_path"])
    if (
        not driver_path.is_absolute()
        or driver_path.resolve(strict=True) != driver_path
        or sha256_file(driver_path) != runtime["campaign_driver_sha256"]
    ):
        raise ContractError(f"{path}: failure campaign driver identity changed")


def _require_sha256(value: Any, where: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ContractError(f"{where}: malformed SHA-256")
    return value


def _validate_completed_cases(
    completed: Any, timing: Any, path: Path
) -> list[dict[str, Any]]:
    if not isinstance(timing, dict):
        raise ContractError(f"{path}: failure timing contract must be an object")
    require_exact_keys(
        timing,
        (
            "clock",
            "samples_per_shape_mode",
            "launches_per_sample",
            "stability_replays_per_shape_mode",
            "gated_mode",
        ),
        f"{path}.timing_contract",
    )
    samples = require_int(timing["samples_per_shape_mode"], "failure samples")
    launches = require_int(timing["launches_per_sample"], "failure launches")
    stability = require_int(
        timing["stability_replays_per_shape_mode"], "failure stability"
    )
    if (
        timing["clock"] != "torch.xpu.Event device elapsed time"
        or timing["gated_mode"] != "xpu_graph_replay"
        or samples < MIN_SAMPLES
        or launches < MIN_LAUNCHES_PER_SAMPLE
        or stability < MIN_STABILITY_REPLAYS
    ):
        raise ContractError(f"{path}: failure timing contract is below minimum")
    if (
        not isinstance(completed, list)
        or len(completed) > len(KV_LENGTHS)
        or not all(isinstance(case, dict) for case in completed)
        or [case.get("kv_length") for case in completed]
        != list(KV_LENGTHS[: len(completed)])
    ):
        raise ContractError(f"{path}: completed-case prefix is malformed")
    case_keys = (
        "kv_length",
        "fixture_seed",
        "fixture_sha256",
        "oracle_sha256",
        "eager_output_sha256",
        "graph_output_sha256",
        "eager_bit_stable",
        "graph_bit_stable",
        "eager_graph_exact",
        "eager_static_out_honored",
        "graph_static_out_honored",
        "poison_checked_replays_per_mode",
        "eager_max_abs_diff",
        "graph_max_abs_diff",
        "mutations",
        "eager_samples_us_per_call",
        "graph_samples_us_per_call",
        "eager_median_us_per_call",
        "graph_median_us_per_call",
        "passed",
    )
    mutation_keys = (
        "name",
        "target",
        "scale",
        "seqused_k",
        "input_sha256",
        "oracle_sha256",
        "eager_output_sha256",
        "graph_output_sha256",
        "eager_max_abs_diff",
        "graph_max_abs_diff",
        "repetitions_per_mode",
        "output_changed_from_baseline",
        "eager_graph_exact",
        "restored_before_next",
        "passed",
    )
    for case in completed:
        kv = require_int(case.get("kv_length"), "completed KV")
        require_exact_keys(case, case_keys, f"{path}.completed.KV{kv}")
        if case["fixture_seed"] != 380000 + kv or any(
            case[name] is not True
            for name in (
                "eager_bit_stable",
                "graph_bit_stable",
                "eager_graph_exact",
                "eager_static_out_honored",
                "graph_static_out_honored",
                "passed",
            )
        ):
            raise ContractError(f"{path}: completed KV {kv} correctness mismatch")
        if case["eager_output_sha256"] != case["graph_output_sha256"]:
            raise ContractError(
                f"{path}: completed KV {kv} eager/graph digest mismatch"
            )
        if case["poison_checked_replays_per_mode"] != stability:
            raise ContractError(f"{path}: completed KV {kv} poison count mismatch")
        for name in (
            "fixture_sha256",
            "oracle_sha256",
            "eager_output_sha256",
            "graph_output_sha256",
        ):
            _require_sha256(case[name], f"{path}.completed.KV{kv}.{name}")
        eager = case["eager_samples_us_per_call"]
        graph = case["graph_samples_us_per_call"]
        if (
            not isinstance(eager, list)
            or len(eager) != samples
            or not isinstance(graph, list)
            or len(graph) != samples
        ):
            raise ContractError(f"{path}: completed KV {kv} sample count mismatch")
        eager_values = [
            require_finite(item, "completed eager sample") for item in eager
        ]
        graph_values = [
            require_finite(item, "completed graph sample") for item in graph
        ]
        if min(eager_values + graph_values) <= 0:
            raise ContractError(f"{path}: completed KV {kv} non-positive timing")
        if (
            require_finite(case["eager_median_us_per_call"], "completed eager median")
            != statistics.median(eager_values)
            or require_finite(
                case["graph_median_us_per_call"], "completed graph median"
            )
            != statistics.median(graph_values)
            or require_finite(case["eager_max_abs_diff"], "completed eager diff")
            > BASE.ATOL
            or require_finite(case["graph_max_abs_diff"], "completed graph diff")
            > BASE.ATOL
        ):
            raise ContractError(f"{path}: completed KV {kv} timing/diff mismatch")
        expected_mutations = (
            ("q_scale_0p875", "q", 0.875, kv),
            ("k_cache_scale_0p875", "k_cache", 0.875, kv),
            ("v_cache_scale_0p875", "v_cache", 0.875, kv),
            ("seqused_k_minus_64", "seqused_k", None, kv - BLOCK_SIZE),
        )
        mutations = case["mutations"]
        if not isinstance(mutations, list) or len(mutations) != 4:
            raise ContractError(f"{path}: completed KV {kv} mutation inventory")
        input_digests: set[str] = set()
        for mutation, expected in zip(mutations, expected_mutations):
            if not isinstance(mutation, dict):
                raise ContractError(f"{path}: completed KV {kv} mutation type")
            require_exact_keys(mutation, mutation_keys, f"{path}.completed.mutation")
            actual_scale = mutation["scale"]
            if expected[2] is not None:
                actual_scale = require_finite(actual_scale, "completed mutation scale")
            if (
                (
                    mutation["name"],
                    mutation["target"],
                    actual_scale,
                    mutation["seqused_k"],
                )
                != expected
                or mutation["repetitions_per_mode"]
                != BASE.MUTATION_REPETITIONS_PER_MODE
                or any(
                    mutation[name] is not True
                    for name in (
                        "output_changed_from_baseline",
                        "eager_graph_exact",
                        "restored_before_next",
                        "passed",
                    )
                )
                or mutation["eager_output_sha256"] != mutation["graph_output_sha256"]
                or mutation["eager_output_sha256"] == case["eager_output_sha256"]
                or require_finite(mutation["eager_max_abs_diff"], "mutation eager diff")
                > BASE.ATOL
                or require_finite(mutation["graph_max_abs_diff"], "mutation graph diff")
                > BASE.ATOL
            ):
                raise ContractError(f"{path}: completed KV {kv} mutation mismatch")
            for name in (
                "input_sha256",
                "oracle_sha256",
                "eager_output_sha256",
                "graph_output_sha256",
            ):
                _require_sha256(mutation[name], f"{path}.completed.mutation.{name}")
            input_digests.add(mutation["input_sha256"])
        if len(input_digests) != 4:
            raise ContractError(f"{path}: completed KV {kv} mutation digest collision")
    return completed


def _validate_run_packet(packet: Any, path: Path) -> dict[str, Any]:
    if not isinstance(packet, dict):
        raise ContractError(f"{path}: run packet must be an object")
    operator = packet.get("operator_identity")
    if not isinstance(operator, dict) or POLICY_IDENTITY_KEY not in operator:
        raise ContractError(f"{path}: missing Q64xK32 policy identity")
    if "m6_head256_q8k64_policy" in operator:
        raise ContractError(f"{path}: stale Q8xK64 policy identity")
    _validate_runtime_identity(packet.get("runtime_identity"), path)
    BASE._validate_run_packet(_translate_success_for_base(packet), path)
    return packet


def compare_packets(
    packets: list[dict[str, Any]], bootstrap_iterations: int
) -> dict[str, Any]:
    translated = [_translate_success_for_base(packet) for packet in packets]
    result = BASE.compare_packets(translated, bootstrap_iterations)
    result["classification"] = (
        "q64k32-candidate-qualified-for-endpoint-campaign"
        if result["passed"]
        else "q64k32-candidate-rejected-at-operator-gate"
    )
    return result


def compare_command(args: argparse.Namespace) -> dict[str, Any]:
    output = Path(args.output)
    temporary = Path(f"{output}.tmp")
    if output.exists() or temporary.exists():
        raise ContractError(f"refusing existing comparison output: {output}")
    loaded = [
        _validate_run_packet(load_json(Path(path)), Path(path)) for path in args.packets
    ]
    candidate_packets = [packet for packet in loaded if packet["role"] == "candidate"]
    manifest_references = {
        (
            packet["stage_identity"]["manifest_path"],
            packet["stage_identity"]["manifest_sha256"],
        )
        for packet in candidate_packets
    }
    if len(manifest_references) != 1:
        raise ContractError("candidate manifest identity differs across packets")
    manifest_path_text, manifest_sha = next(iter(manifest_references))
    manifest_path = Path(manifest_path_text)
    if not manifest_path.is_file() or sha256_file(manifest_path) != manifest_sha:
        raise ContractError(
            f"candidate stage manifest missing or changed: {manifest_path}"
        )
    identity = validate_candidate_manifest(manifest_path)
    for packet in candidate_packets:
        for key in (
            "stage",
            "hashes",
            "manifest_path",
            "manifest_sha256",
            "artifact_path",
            "artifact_sha256",
            "graph_manifest_path",
            "graph_manifest_sha256",
        ):
            if packet["stage_identity"][key] != identity[key]:
                raise ContractError(
                    f"candidate manifest revalidation differs for {key}: {manifest_path}"
                )
    for packet in loaded:
        stderr_path = Path(packet["engagement"]["stderr_log_path"])
        if (
            not stderr_path.is_file()
            or sha256_file(stderr_path) != packet["engagement"]["stderr_log_sha256"]
        ):
            raise ContractError(
                f"stderr engagement log missing or changed: {stderr_path}"
            )
        evidence = _engagement_evidence(stderr_path.read_bytes(), packet["role"])
        if (
            evidence["marker_gate_passed"] is not True
            or evidence["stderr_line_count"]
            != packet["engagement"]["stderr_line_count"]
        ):
            raise ContractError(f"stderr policy marker evidence changed: {stderr_path}")
    result = compare_packets(loaded, args.bootstrap_iterations)
    result["packet_paths"] = [
        str(Path(path).resolve(strict=True)) for path in args.packets
    ]
    result["packet_sha256"] = [sha256_file(Path(path)) for path in args.packets]
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(output, temporary, result)
    return result


_FAILURE_KEYS = (
    "schema",
    "passed",
    "classification",
    "role",
    "arm_id",
    "campaign_slot",
    "process",
    "operator_identity",
    "stage_identity",
    "engagement",
    "mapping_evidence",
    "runtime_identity",
    "timing_contract",
    "completed_cases",
    "failure",
    "output_contract",
)


def validate_failure_packet(packet: Any, path: Path) -> dict[str, Any]:
    if not isinstance(packet, dict):
        raise ContractError(f"{path}: failure packet must be an object")
    require_exact_keys(packet, _FAILURE_KEYS, str(path))
    if packet["schema"] != SCHEMA_FAILURE or packet["passed"] is not False:
        raise ContractError(f"{path}: failure schema/pass mismatch")
    if packet["role"] not in ("control", "candidate"):
        raise ContractError(f"{path}: invalid failure role")
    slot = require_int(packet["campaign_slot"], f"{path}.campaign_slot")
    if (
        slot not in (1, 2, 3, 4)
        or not isinstance(packet["arm_id"], str)
        or not packet["arm_id"]
    ):
        raise ContractError(f"{path}: invalid failure arm identity")
    if packet["operator_identity"] != _operator_identity(
        "0" if packet["role"] == "control" else "1"
    ):
        raise ContractError(f"{path}: failure operator identity mismatch")
    _validate_runtime_identity(packet["runtime_identity"], path)
    process = packet["process"]
    if not isinstance(process, dict):
        raise ContractError(f"{path}: process identity must be an object")
    require_exact_keys(
        process,
        (
            "pid",
            "start_ticks",
            "boot_id",
            "started_time_ns",
            "finished_time_ns",
        ),
        f"{path}.process",
    )
    for name in ("pid", "start_ticks", "started_time_ns", "finished_time_ns"):
        if require_int(process[name], f"{path}.process.{name}") <= 0:
            raise ContractError(f"{path}: negative process identity field {name}")
    if (
        not isinstance(process["boot_id"], str)
        or not process["boot_id"]
        or process["finished_time_ns"] < process["started_time_ns"]
    ):
        raise ContractError(f"{path}: malformed process identity")

    runtime = packet["runtime_identity"]
    expected_role = "control" if slot in (1, 4) else "candidate"
    expected_suffix = ("a1", "b1", "b2", "a2")[slot - 1]
    expected_arm = f"gpu{runtime['physical_gpu']}-{expected_suffix}"
    if packet["role"] != expected_role or packet["arm_id"] != expected_arm:
        raise ContractError(f"{path}: failure arm/slot/device ordering mismatch")

    stage = packet["stage_identity"]
    if not isinstance(stage, dict):
        raise ContractError(f"{path}: failure stage identity must be an object")
    require_exact_keys(
        stage,
        (
            "role",
            "stage",
            "hashes",
            "manifest_path",
            "manifest_sha256",
            "artifact_path",
            "artifact_sha256",
            "graph_manifest_path",
            "graph_manifest_sha256",
            "files",
        ),
        f"{path}.stage_identity",
    )
    if (
        stage["role"] != packet["role"]
        or not isinstance(stage["hashes"], dict)
        or set(stage["hashes"]) != set(RELATIVE_FILES)
    ):
        raise ContractError(f"{path}: failure stage identity mismatch")
    for name, digest in stage["hashes"].items():
        _require_sha256(digest, f"{path}.stage_identity.hashes.{name}")
    files = stage["files"]
    if not isinstance(files, dict) or set(files) != set(RELATIVE_FILES):
        raise ContractError(f"{path}: failure stage file inventory mismatch")
    for name, relative in RELATIVE_FILES.items():
        entry = files[name]
        require_exact_keys(
            entry, ("path", "relative_path", "sha256"), f"{path}.files.{name}"
        )
        if entry != {
            "path": str(Path(stage["stage"]) / relative),
            "relative_path": relative,
            "sha256": stage["hashes"][name],
        }:
            raise ContractError(f"{path}: failure stage file {name} mismatch")
    if packet["role"] == "control":
        if stage["stage"] != str(CONTROL_STAGE) or stage["hashes"] != CONTROL_HASHES:
            raise ContractError(f"{path}: failure control stage mismatch")
        if any(
            stage[name] is not None
            for name in (
                "manifest_path",
                "manifest_sha256",
                "artifact_path",
                "artifact_sha256",
                "graph_manifest_path",
                "graph_manifest_sha256",
            )
        ):
            raise ContractError(f"{path}: control failure has candidate provenance")
        current_stage = stage_identity(
            argparse.Namespace(
                role="control", stage=stage["stage"], stage_manifest=None
            )
        )
        if stage != current_stage:
            raise ContractError(f"{path}: failure control stage no longer revalidates")
    else:
        manifest_path = Path(stage["manifest_path"])
        if not manifest_path.is_file():
            raise ContractError(f"{path}: candidate failure manifest is unavailable")
        current_stage = stage_identity(
            argparse.Namespace(
                role="candidate", stage=None, stage_manifest=str(manifest_path)
            )
        )
        for name in (
            "stage",
            "hashes",
            "manifest_path",
            "manifest_sha256",
            "artifact_path",
            "artifact_sha256",
            "graph_manifest_path",
            "graph_manifest_sha256",
            "files",
        ):
            if stage[name] != current_stage[name]:
                raise ContractError(
                    f"{path}: candidate failure stage no longer revalidates: {name}"
                )
    if runtime["pythonpath_first"] != stage["stage"] or runtime[
        "ld_library_path_first"
    ] != str(Path(stage["stage"]) / "vllm_xpu_kernels"):
        raise ContractError(f"{path}: failure runtime did not select its stage")
    engagement = packet["engagement"]
    require_exact_keys(
        engagement,
        (
            "policy_env",
            "policy_value",
            "expected_marker_lines",
            "observed_marker_lines",
            "marker_gate_passed",
            "stderr_decode_error",
            "stderr_line_count",
            "stderr_log_path",
            "stderr_log_sha256",
        ),
        f"{path}.engagement",
    )
    stderr_path = Path(engagement["stderr_log_path"])
    if (
        not stderr_path.is_file()
        or sha256_file(stderr_path) != engagement["stderr_log_sha256"]
    ):
        raise ContractError(f"{path}: failure stderr missing or changed")
    if stderr_path.stat().st_mode & 0o222:
        raise ContractError(f"{path}: failure stderr is writable")
    recomputed_engagement = _engagement_evidence(
        stderr_path.read_bytes(), packet["role"]
    )
    for key, value in recomputed_engagement.items():
        if engagement[key] != value:
            raise ContractError(f"{path}: failure engagement does not recompute: {key}")
    mapping = packet["mapping_evidence"]
    require_exact_keys(
        mapping,
        (
            "required",
            "matched",
            "same_basename_paths",
            "mapping_gate_passed",
            "mapping_error",
        ),
        f"{path}.mapping_evidence",
    )
    required_mapping = {
        name: {
            "path": files[name]["path"],
            "sha256": files[name]["sha256"],
        }
        for name in ("extension", "device_library", "stock_library")
    }
    if mapping["required"] != required_mapping:
        raise ContractError(f"{path}: failure mapping requirement mismatch")
    if not isinstance(mapping["matched"], dict) or set(mapping["matched"]) != set(
        required_mapping
    ):
        raise ContractError(f"{path}: failure matched mapping inventory mismatch")
    if not isinstance(mapping["same_basename_paths"], dict) or set(
        mapping["same_basename_paths"]
    ) != set(required_mapping):
        raise ContractError(f"{path}: failure basename mapping inventory mismatch")
    if mapping["mapping_error"] is not None and (
        not isinstance(mapping["mapping_error"], str) or not mapping["mapping_error"]
    ):
        raise ContractError(f"{path}: malformed mapping error")
    for name in required_mapping:
        same_name = mapping["same_basename_paths"][name]
        if (
            not isinstance(same_name, list)
            or not all(isinstance(item, str) for item in same_name)
            or same_name != sorted(set(same_name))
        ):
            raise ContractError(f"{path}: malformed same-basename mapping {name}")
        expected_match = (
            required_mapping[name]
            if required_mapping[name]["path"] in same_name
            else None
        )
        if mapping["matched"][name] != expected_match:
            raise ContractError(f"{path}: false matched mapping corroboration {name}")
    derived_mapping_pass = (
        mapping["mapping_error"] is None and mapping["matched"] == required_mapping
    )
    if mapping["mapping_gate_passed"] is not derived_mapping_pass:
        raise ContractError(f"{path}: failure mapping gate does not rederive")
    failure = packet["failure"]
    require_exact_keys(
        failure,
        (
            "exception_type",
            "message",
            "phase",
            "correctness_kind",
            "kv_length",
            "mode",
            "replay_index",
            "mismatched_elements",
            "element_count",
            "mismatch_percent_displayed",
            "greatest_absolute_difference",
            "greatest_absolute_difference_index",
            "absolute_tolerance",
            "greatest_relative_difference",
            "greatest_relative_difference_index",
            "relative_tolerance",
        ),
        f"{path}.failure",
    )
    if not isinstance(failure["exception_type"], str) or not isinstance(
        failure["message"], str
    ):
        raise ContractError(f"{path}: malformed failure exception")
    parsed = failure_error_metadata(Exception(failure["message"]), failure["kv_length"])
    for name in (
        "phase",
        "correctness_kind",
        "kv_length",
        "mode",
        "replay_index",
        "mismatched_elements",
        "element_count",
        "mismatch_percent_displayed",
        "greatest_absolute_difference",
        "greatest_absolute_difference_index",
        "absolute_tolerance",
        "greatest_relative_difference",
        "greatest_relative_difference_index",
        "relative_tolerance",
    ):
        if failure[name] != parsed[name]:
            raise ContractError(f"{path}: failure error metadata does not rederive")
    if failure["correctness_kind"] is not None:
        kv = require_int(failure["kv_length"], f"{path}.failure.kv_length")
        if kv not in KV_LENGTHS or not failure["message"].startswith(f"KV {kv} "):
            raise ContractError(f"{path}: correctness failure KV is inconsistent")
    if failure["correctness_kind"] == "cpu-oracle-mismatch":
        replay = failure["replay_index"]
        if replay is not None:
            replay = require_int(replay, "failure replay")
        mismatch = require_int(failure["mismatched_elements"], "failure mismatch")
        elements = require_int(failure["element_count"], "failure elements")
        if (
            failure["mode"] not in ("eager", "graph")
            or (
                replay is not None
                and (
                    replay < 0
                    or replay
                    >= packet["timing_contract"]["stability_replays_per_shape_mode"]
                )
            )
            or (replay is None and " post-mutation " not in failure["message"])
            or mismatch <= 0
            or mismatch > elements
            or elements != ROWS * Q_HEADS * HEAD_DIM
            or failure["absolute_tolerance"] != BASE.ATOL
            or failure["relative_tolerance"] != BASE.RTOL
            or require_finite(
                failure["greatest_absolute_difference"], "failure absolute diff"
            )
            < 0
            or require_finite(
                failure["greatest_relative_difference"], "failure relative diff"
            )
            < 0
            or failure["greatest_absolute_difference_index"] is None
            or failure["greatest_relative_difference_index"] is None
            or len(failure["greatest_absolute_difference_index"]) != 3
            or len(failure["greatest_relative_difference_index"]) != 3
            or not all(
                isinstance(item, int) and not isinstance(item, bool) and item >= 0
                for item in failure["greatest_absolute_difference_index"]
                + failure["greatest_relative_difference_index"]
            )
        ):
            raise ContractError(f"{path}: CPU-oracle failure numerics are inconsistent")
        displayed = failure["mismatch_percent_displayed"]
        if (
            not isinstance(displayed, str)
            or not displayed.endswith("%")
            or round(float(displayed[:-1]), 1) != round(100.0 * mismatch / elements, 1)
        ):
            raise ContractError(f"{path}: mismatch percentage is inconsistent")
    _validate_completed_cases(
        packet["completed_cases"], packet["timing_contract"], path
    )
    output_contract = packet["output_contract"]
    require_exact_keys(
        output_contract,
        (
            "success_packet_path",
            "success_packet_persisted",
            "failure_packet_path",
            "stderr_persisted",
        ),
        f"{path}.output_contract",
    )
    if (
        output_contract["success_packet_persisted"] is not False
        or output_contract["stderr_persisted"] is not True
        or Path(output_contract["failure_packet_path"]).resolve() != path.resolve()
        or Path(output_contract["success_packet_path"]).exists()
        or Path(output_contract["failure_packet_path"])
        != Path(f"{output_contract['success_packet_path']}.failure.json")
        or Path(engagement["stderr_log_path"])
        != Path(f"{output_contract['success_packet_path']}.stderr.log")
    ):
        raise ContractError(f"{path}: failure output contract mismatch")
    expected_classification = failure_classification(
        packet["role"],
        failure["correctness_kind"],
        engagement["marker_gate_passed"],
        mapping["mapping_gate_passed"],
    )
    if packet["classification"] != expected_classification:
        raise ContractError(f"{path}: failure classification does not rederive")
    if path.stat().st_mode & 0o222:
        raise ContractError(f"{path}: failure packet is writable")
    return packet


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate-stage")
    validate.add_argument("--role", choices=("control", "candidate"), required=True)
    validate.add_argument("--stage")
    validate.add_argument("--stage-manifest")

    run = subparsers.add_parser("run")
    run.add_argument("--role", choices=("control", "candidate"), required=True)
    run.add_argument("--stage")
    run.add_argument("--stage-manifest")
    run.add_argument("--physical-gpu", type=int, required=True)
    run.add_argument("--arm-id", required=True)
    run.add_argument("--campaign-slot", type=int, choices=(1, 2, 3, 4), required=True)
    run.add_argument("--output", required=True)
    run.add_argument("--samples", type=int, default=40)
    run.add_argument("--launches-per-sample", type=int, default=100)
    run.add_argument("--stability-replays", type=int, default=32)

    validate_failure = subparsers.add_parser("validate-failure")
    validate_failure.add_argument("packet")

    compare = subparsers.add_parser("compare")
    compare.add_argument("--output", required=True)
    compare.add_argument("--bootstrap-iterations", type=int, default=10000)
    compare.add_argument("packets", nargs=8)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "validate-stage":
            identity = stage_identity(args)
            print(json.dumps(identity, indent=2, sort_keys=True))
            return 0
        if args.command == "validate-failure":
            packet_path = Path(args.packet)
            validate_failure_packet(load_json(packet_path), packet_path)
            print(json.dumps({"passed": True, "failure_packet": str(packet_path)}))
            return 0
        if args.command == "run":
            if args.samples < MIN_SAMPLES:
                parser.error(f"--samples must be >= {MIN_SAMPLES}")
            if args.launches_per_sample < MIN_LAUNCHES_PER_SAMPLE:
                parser.error(
                    f"--launches-per-sample must be >= {MIN_LAUNCHES_PER_SAMPLE}"
                )
            if args.stability_replays < MIN_STABILITY_REPLAYS:
                parser.error(f"--stability-replays must be >= {MIN_STABILITY_REPLAYS}")
            packet = run_xpu(args)
            print(
                json.dumps(
                    {"passed": True, "output": args.output, "arm": packet["arm_id"]}
                )
            )
            return 0
        result = compare_command(args)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["passed"] else 14
    except ContractError as error:
        print(f"error: {error}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
