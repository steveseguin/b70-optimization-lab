#!/usr/bin/env python3
"""Fail-closed Qwen3.8 TP2 native-SYCL GDN prefill stability oracle.

This is a raw-op diagnostic, not a server benchmark.  It invokes the staged
``_xpu_C::gdn_attention`` operator directly at the three production prompt
lengths associated with the remaining full-25 token families.  Every call is
preceded by device-side restoration of the same complete projected-input and
conv/SSM-cache fixtures.  Outputs and the selected state row are snapshotted
before the next restore, either across explicit call boundaries or in bounded
queued batches.

Run physical GPUs 2 and 3 in separate, affinity-isolated processes, then use
the ``compare`` subcommand to require cross-device bit identity.  The script
never loads model weights or starts vLLM.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import re
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path("/home/steve/llm-optimizations")
SCRIPT_PATH = Path(__file__).resolve()
STAGE = Path("/home/steve/staged-xpu-commitfix-graphfa-composite-20260820")
STAGE_PACKAGE = STAGE / "vllm_xpu_kernels"
STAGE_MANIFEST = (
    REPO
    / "repro/qwen38-27b-autoround-int4-b70/manifests/"
    "staged-xpu-commitfix-graphfa-composite-20260820.graph.sha256"
)
MODEL_CONFIG = Path(
    "/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan/config.json"
)
MODEL_MANIFEST = (
    REPO / "repro/qwen38-27b-autoround-int4-b70/manifests/model.json"
)
KERNEL_REPO = Path("/home/steve/src/vllm-xpu-kernels")
GDN_SOURCE = KERNEL_REPO / "csrc/xpu/gdn_attn/gdn_attn_interface.cpp"
REFERENCE_IDENTITY = Path(
    "/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/"
    "qwen38-detpad-composite4dd-marginfree-mtp5-25-spec-a2-20260820/"
    "run/identity.env"
)

EXPECTED = {
    "stage_manifest_sha256":
        "47861e8391b6b25dd9c3eb25e25c5939753aa470858b667d5bdf181344db18da",
    "native_extension_sha256":
        "4dd336013d155aab004fb1c916118957cb9349b491938da65769f2d8af18ffb0",
    "gdn_library_sha256":
        "c194e28dd902136df545b9c0bd3929d41968c31e84f5b3b2f5ae1dba9dbaeab7",
    "model_config_sha256":
        "9a1c29a807e34529bec03cba92b4dc00ba61e37a703b029b08a3142b6dc08cd1",
    "model_manifest_sha256":
        "731d851b39d37f3d58c5a74ad6a7cd3ade1c9e8543ef1612a5d55131ff8331b8",
    "kernel_git_head": "2dd55f380df753a10a88fcd9e96192561066e713",
    "gdn_source_sha256":
        "6ac157e3ef5539a3157504ffcc991c35ab8b78ee34c194639918df0583548a88",
    "reference_identity_sha256":
        "9b1d08bc768b222ecc29daf3fc33f7b20747f14e6947d3b8ba51935c3b0f1ea8",
    "python_prefix": "/home/steve/.venvs/vllm-xpu",
}

TOKEN_CASES = (
    (6, "selection--sql-debugging", 83),
    (11, "holdout--factual-protocol", 61),
    (24, "holdout--long-rollover-repository-audit", 849),
)
TP_SIZE = 2
NUM_K_HEADS = 16
NUM_V_HEADS = 48
HEAD_K_DIM = 128
HEAD_V_DIM = 128
CONV_WIDTH = 4
LOCAL_K_HEADS = NUM_K_HEADS // TP_SIZE
LOCAL_V_HEADS = NUM_V_HEADS // TP_SIZE
QKVZ_COLS = LOCAL_K_HEADS * (
    2 * HEAD_K_DIM + 2 * (NUM_V_HEADS // NUM_K_HEADS) * HEAD_V_DIM
)
BA_COLS = 2 * LOCAL_V_HEADS
CONV_COLS = LOCAL_K_HEADS * (
    2 * HEAD_K_DIM + (NUM_V_HEADS // NUM_K_HEADS) * HEAD_V_DIM
)
CACHE_ROWS = 8
CONV_CACHE_COLUMNS = 8
ACTIVE_CONV_COLUMNS = CONV_WIDTH - 1
ROW_PATTERN = (1, 1, 2, 4, 7)
OUTPUT_SENTINELS = (31744.0, -31744.0)
EXECUTION_MODES = ("isolated", "queued")
QUEUED_BATCH_CALLS = 16
BASE_SEED = 20260820
SCHEMA_VERSION = 1
MANIFEST_RE = re.compile(r"^([0-9a-f]{64})  (.+)$")
PREREG_CONTRACTS = {
    "qualification": {
        9000: (20, (6, 11, 24), ("isolated", "queued")),
    },
    "main": {
        0: (256, (6, 11, 24), ("isolated", "queued")),
        1: (256, (24, 11, 6), ("queued", "isolated")),
        2: (256, (11, 24, 6), ("isolated", "queued")),
        3: (256, (6, 24, 11), ("queued", "isolated")),
    },
}


class ContractError(RuntimeError):
    """A fail-closed identity, shape, or artifact contract violation."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_file_sha(path: Path, expected: str, label: str) -> str:
    if not path.is_file():
        raise ContractError(f"{label} is missing: {path}")
    actual = sha256_file(path)
    if actual != expected:
        raise ContractError(
            f"{label} SHA-256 mismatch: expected {expected}, got {actual}"
        )
    return actual


def parse_stage_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text().splitlines(), 1):
        match = MANIFEST_RE.fullmatch(raw_line)
        if not match:
            raise ContractError(
                f"malformed stage manifest line {line_number}: {raw_line!r}"
            )
        expected_sha, relative_text = match.groups()
        relative = Path(relative_text)
        if relative.is_absolute() or ".." in relative.parts:
            raise ContractError(f"unsafe stage-manifest path: {relative_text!r}")
        normalized = relative.as_posix()
        if normalized in entries:
            raise ContractError(f"duplicate stage-manifest path: {normalized}")
        entries[normalized] = expected_sha
    if not entries:
        raise ContractError("stage manifest is empty")
    return entries


def verify_complete_stage() -> dict[str, Any]:
    manifest_sha = require_file_sha(
        STAGE_MANIFEST,
        EXPECTED["stage_manifest_sha256"],
        "complete composite-stage manifest",
    )
    if not STAGE.is_dir():
        raise ContractError(f"composite stage is missing: {STAGE}")
    entries = parse_stage_manifest(STAGE_MANIFEST)
    actual_files = {
        path.relative_to(STAGE).as_posix()
        for path in STAGE.rglob("*")
        if path.is_file()
    }
    expected_files = set(entries)
    if actual_files != expected_files:
        missing = sorted(expected_files - actual_files)
        extra = sorted(actual_files - expected_files)
        raise ContractError(
            f"composite stage file set mismatch: missing={missing}, extra={extra}"
        )
    for relative, expected_sha in entries.items():
        candidate = STAGE / relative
        if candidate.is_symlink() or not candidate.is_file():
            raise ContractError(f"stage entry is not a regular file: {candidate}")
        actual_sha = sha256_file(candidate)
        if actual_sha != expected_sha:
            raise ContractError(
                f"stage entry SHA-256 mismatch for {relative}: "
                f"expected {expected_sha}, got {actual_sha}"
            )
    native_path = STAGE_PACKAGE / "_xpu_C.abi3.so"
    native_sha = require_file_sha(
        native_path, EXPECTED["native_extension_sha256"], "native extension"
    )
    gdn_library = STAGE_PACKAGE / "libgdn_attn_kernels_xe_2.so"
    gdn_library_sha = require_file_sha(
        gdn_library, EXPECTED["gdn_library_sha256"], "native GDN library"
    )
    return {
        "stage": str(STAGE),
        "manifest": str(STAGE_MANIFEST),
        "manifest_sha256": manifest_sha,
        "entry_count": len(entries),
        "native_extension": str(native_path),
        "native_extension_sha256": native_sha,
        "gdn_library": str(gdn_library),
        "gdn_library_sha256": gdn_library_sha,
    }


def git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(KERNEL_REPO), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def validate_model_contract() -> dict[str, Any]:
    config_sha = require_file_sha(
        MODEL_CONFIG, EXPECTED["model_config_sha256"], "model config"
    )
    manifest_sha = require_file_sha(
        MODEL_MANIFEST, EXPECTED["model_manifest_sha256"], "model manifest"
    )
    config = json.loads(MODEL_CONFIG.read_text())
    text_config = config.get("text_config")
    if not isinstance(text_config, dict):
        raise ContractError("model config has no text_config object")
    required = {
        "hidden_size": 5120,
        "num_hidden_layers": 64,
        "linear_num_key_heads": NUM_K_HEADS,
        "linear_num_value_heads": NUM_V_HEADS,
        "linear_key_head_dim": HEAD_K_DIM,
        "linear_value_head_dim": HEAD_V_DIM,
        "linear_conv_kernel_dim": CONV_WIDTH,
        "hidden_act": "silu",
        "mamba_ssm_dtype": "float32",
    }
    observed = {key: text_config.get(key) for key in required}
    if observed != required:
        raise ContractError(
            f"model shape contract mismatch: expected {required}, got {observed}"
        )
    return {
        "config": str(MODEL_CONFIG),
        "config_sha256": config_sha,
        "manifest": str(MODEL_MANIFEST),
        "manifest_sha256": manifest_sha,
        "shape_fields": observed,
        "runtime_dtype_override": "float16",
        "weights_loaded": False,
    }


def validate_source_contract() -> dict[str, Any]:
    head = git_output("rev-parse", "HEAD")
    if head != EXPECTED["kernel_git_head"]:
        raise ContractError(
            f"kernel source HEAD mismatch: expected {EXPECTED['kernel_git_head']}, "
            f"got {head}"
        )
    tracked_status = git_output("status", "--porcelain", "--untracked-files=no")
    if tracked_status:
        raise ContractError(f"kernel source has tracked changes: {tracked_status!r}")
    source_sha = require_file_sha(
        GDN_SOURCE, EXPECTED["gdn_source_sha256"], "native GDN source"
    )
    return {
        "repo": str(KERNEL_REPO),
        "git_head": head,
        "tracked_status": "clean",
        "gdn_source": str(GDN_SOURCE),
        "gdn_source_sha256": source_sha,
    }


def validate_process_contract(physical_gpu: int) -> dict[str, Any]:
    if Path(sys.prefix).resolve() != Path(EXPECTED["python_prefix"]).resolve():
        raise ContractError(
            f"wrong Python environment: expected prefix {EXPECTED['python_prefix']}, "
            f"got {sys.prefix}"
        )
    affinity = os.environ.get("ZE_AFFINITY_MASK")
    if affinity != str(physical_gpu):
        raise ContractError(
            f"ZE_AFFINITY_MASK must be exactly {physical_gpu!r}, got {affinity!r}"
        )
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise ContractError("PYTHONDONTWRITEBYTECODE must be exactly 1")
    ld_components = [
        component
        for component in os.environ.get("LD_LIBRARY_PATH", "").split(":")
        if component
    ]
    if not ld_components or ld_components[0] != str(STAGE_PACKAGE):
        raise ContractError(
            "the first nonempty LD_LIBRARY_PATH component must be the staged "
            f"package directory {STAGE_PACKAGE}; got {ld_components}"
        )
    reference_sha = require_file_sha(
        REFERENCE_IDENTITY,
        EXPECTED["reference_identity_sha256"],
        "A2 reference identity",
    )
    return {
        "hostname": socket.gethostname(),
        "python_executable": sys.executable,
        "python_prefix": sys.prefix,
        "physical_gpu": physical_gpu,
        "logical_device": "xpu:0",
        "ze_affinity_mask": affinity,
        "python_dont_write_bytecode": os.environ["PYTHONDONTWRITEBYTECODE"],
        "stage_library_path_first_nonempty": True,
        "reference_identity": str(REFERENCE_IDENTITY),
        "reference_identity_sha256": reference_sha,
    }


def shape_contract() -> dict[str, Any]:
    return {
        "tp_size": TP_SIZE,
        "num_k_heads_global": NUM_K_HEADS,
        "num_v_heads_global": NUM_V_HEADS,
        "num_k_heads_local": LOCAL_K_HEADS,
        "num_v_heads_local": LOCAL_V_HEADS,
        "head_k_dim": HEAD_K_DIM,
        "head_v_dim": HEAD_V_DIM,
        "conv_width": CONV_WIDTH,
        "qkvz_cols_local": QKVZ_COLS,
        "ba_cols_local": BA_COLS,
        "conv_cols_local": CONV_COLS,
        "activation_dtype": "float16",
        "conv_state_dtype": "float16",
        "ssm_state_dtype": "float32",
        "A_log_dtype": "float32",
        "dt_bias_dtype": "float16",
        "cache_rows": CACHE_ROWS,
        "conv_cache_columns": CONV_CACHE_COLUMNS,
        "active_conv_columns": [0, ACTIVE_CONV_COLUMNS],
        "reserved_conv_columns": [ACTIVE_CONV_COLUMNS, CONV_CACHE_COLUMNS],
        "row_pattern": list(ROW_PATTERN),
        "output_sentinels": list(OUTPUT_SENTINELS),
        "execution_modes": list(EXECUTION_MODES),
        "queued_batch_calls": QUEUED_BATCH_CALLS,
        "token_cases": [
            {"prompt_index": index, "label": label, "tokens": tokens}
            for index, label, tokens in TOKEN_CASES
        ],
        "base_seed": BASE_SEED,
        "reorder_input": True,
        "has_initial_state": False,
        "num_prefills": 1,
        "num_decodes": 0,
    }


def preflight(physical_gpu: int) -> dict[str, Any]:
    if physical_gpu not in (2, 3):
        raise ContractError("physical GPU must be 2 or 3")
    if QKVZ_COLS != 8192 or BA_COLS != 48 or CONV_COLS != 5120:
        raise ContractError("internal TP2-local shape derivation changed")
    return {
        "process": validate_process_contract(physical_gpu),
        "model": validate_model_contract(),
        "source": validate_source_contract(),
        "stage": verify_complete_stage(),
        "shape": shape_contract(),
        "script": str(SCRIPT_PATH),
        "script_sha256": sha256_file(SCRIPT_PATH),
    }


def parse_order(value: str) -> tuple[int, ...]:
    try:
        order = tuple(int(item) for item in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("order must be comma-separated integers") from exc
    expected = sorted(index for index, _, _ in TOKEN_CASES)
    if sorted(order) != expected or len(order) != len(expected):
        raise argparse.ArgumentTypeError(
            f"order must be a permutation of {','.join(map(str, expected))}"
        )
    return order


def parse_mode_order(value: str) -> tuple[str, ...]:
    order = tuple(item.strip() for item in value.split(","))
    if sorted(order) != sorted(EXECUTION_MODES) or len(order) != len(EXECUTION_MODES):
        raise argparse.ArgumentTypeError(
            f"mode order must be a permutation of {','.join(EXECUTION_MODES)}"
        )
    return order


def row_schedule(calls: int) -> tuple[int, ...]:
    return tuple(ROW_PATTERN[index % len(ROW_PATTERN)] for index in range(calls))


def cpu_tensor_digest(torch: Any, tensor: Any) -> dict[str, Any]:
    contiguous = tensor.detach().contiguous().view(torch.uint8)
    raw = contiguous.numpy().tobytes()
    return {
        "shape": list(tensor.shape),
        "dtype": str(tensor.dtype),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def xpu_tensor_digest(torch: Any, tensor: Any) -> dict[str, Any]:
    return cpu_tensor_digest(torch, tensor.detach().contiguous().cpu())


def make_cpu_inputs(torch: Any, tokens: int, seed: int) -> dict[str, Any]:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)

    def randn(shape: tuple[int, ...], *, scale: float = 1.0,
              dtype: Any = None) -> Any:
        value = torch.randn(shape, generator=generator, dtype=torch.float32) * scale
        return value.to(dtype=dtype or torch.float16)

    return {
        "qkvz": randn((tokens, QKVZ_COLS), scale=0.125),
        "ba": randn((tokens, BA_COLS), scale=0.125),
        "conv_weights": randn((CONV_COLS, CONV_WIDTH), scale=0.03125),
        "conv_state": randn(
            (CACHE_ROWS, CONV_CACHE_COLUMNS, CONV_COLS), scale=0.015625
        ),
        "ssm_state": randn(
            (CACHE_ROWS, LOCAL_V_HEADS, HEAD_V_DIM, HEAD_K_DIM),
            scale=0.015625,
            dtype=torch.float32,
        ),
        "A_log": randn((LOCAL_V_HEADS,), scale=0.03125, dtype=torch.float32),
        "dt_bias": randn((LOCAL_V_HEADS,), scale=0.03125),
    }


def compare_tensor(torch: Any, current: Any, reference: Any, *,
                   sentinel: float | None = None,
                   reference_digest: dict[str, Any] | None = None) -> dict[str, Any]:
    equal = bool(torch.equal(current, reference))
    bad_count = int(torch.ne(current, reference).sum().item())
    finite = bool(torch.isfinite(current).all().item())
    max_abs_diff: float | None
    if finite and bool(torch.isfinite(reference).all().item()):
        max_abs_diff = float(
            (current.float() - reference.float()).abs().max().item()
        )
    else:
        max_abs_diff = None
    sentinel_count = (
        int(torch.eq(current, sentinel).sum().item()) if sentinel is not None else None
    )
    current_digest = xpu_tensor_digest(torch, current)
    expected_digest = (
        reference_digest
        if reference_digest is not None
        else xpu_tensor_digest(torch, reference)
    )
    return {
        "equal_reference": equal,
        "finite": finite,
        "bad_count": bad_count,
        "max_abs_diff": max_abs_diff,
        "sentinel_count": sentinel_count,
        "digest": current_digest,
        "reference_digest": expected_digest,
    }


def tensor_comparison_pass(item: Any) -> bool:
    return (
        isinstance(item, dict)
        and item.get("equal_reference")
        is (item.get("digest") == item.get("reference_digest"))
        and item.get("equal_reference") is True
        and item.get("finite") is True
        and item.get("bad_count") == 0
        and item.get("max_abs_diff") == 0.0
    )


def run_case(torch: Any, *, prompt_index: int, label: str, tokens: int,
             seed: int, calls: int,
             mode: str) -> tuple[dict[str, Any], int, dict[str, Any] | None]:
    cpu_inputs = make_cpu_inputs(torch, tokens, seed)
    input_digests = {
        name: cpu_tensor_digest(torch, value)
        for name, value in cpu_inputs.items()
    }
    device = torch.device("xpu:0")
    source = {name: value.to(device) for name, value in cpu_inputs.items()}
    qkvz_work = torch.empty_like(source["qkvz"])
    ba_work = torch.empty_like(source["ba"])
    conv_work = torch.empty_like(source["conv_state"])
    ssm_work = torch.empty_like(source["ssm_state"])
    core_work = torch.empty(
        (tokens, LOCAL_V_HEADS, HEAD_V_DIM),
        dtype=torch.float16,
        device=device,
    )
    z_work = torch.empty_like(core_work)
    query_start = torch.tensor([0, tokens], dtype=torch.int32, device=device)
    has_initial_state = torch.zeros(1, dtype=torch.bool, device=device)
    metadata_digests = {
        "query_start": xpu_tensor_digest(torch, query_start),
        "has_initial_state": xpu_tensor_digest(torch, has_initial_state),
    }
    row_reference_digests = {}
    for row in sorted(set(ROW_PATTERN)):
        nonselected_rows = [
            candidate for candidate in range(CACHE_ROWS) if candidate != row
        ]
        row_reference_digests[row] = {
            "conv_reserved": cpu_tensor_digest(
                torch, cpu_inputs["conv_state"][row, ACTIVE_CONV_COLUMNS:]
            ),
            "conv_nonselected": cpu_tensor_digest(
                torch, cpu_inputs["conv_state"][nonselected_rows]
            ),
            "ssm_nonselected": cpu_tensor_digest(
                torch, cpu_inputs["ssm_state"][nonselected_rows]
            ),
            "state_index": cpu_tensor_digest(
                torch, torch.tensor([row], dtype=torch.int32)
            ),
        }

    native_calls = 0
    rows = row_schedule(calls)
    if mode not in EXECUTION_MODES:
        raise ContractError(f"unsupported execution mode: {mode}")
    batch_calls = 1 if mode == "isolated" else QUEUED_BATCH_CALLS
    reference: dict[str, Any] | None = None
    reference_digests: dict[str, dict[str, Any]] | None = None
    observations: list[dict[str, Any]] = []
    first_failure: dict[str, Any] | None = None
    for batch_start in range(0, calls, batch_calls):
        queued_snapshots: list[dict[str, Any]] = []
        batch_stop = min(calls, batch_start + batch_calls)
        for iteration in range(batch_start, batch_stop):
            row = rows[iteration]
            poison = OUTPUT_SENTINELS[iteration % len(OUTPUT_SENTINELS)]
            qkvz_work.copy_(source["qkvz"])
            ba_work.copy_(source["ba"])
            conv_work.copy_(source["conv_state"])
            ssm_work.copy_(source["ssm_state"])
            core_work.fill_(poison)
            z_work.fill_(poison)
            state_index = torch.tensor([row], dtype=torch.int32, device=device)
            if mode == "isolated":
                torch.xpu.synchronize()
            torch.ops._xpu_C.gdn_attention(
                core_work,
                z_work,
                qkvz_work,
                ba_work,
                NUM_K_HEADS,
                NUM_V_HEADS,
                HEAD_K_DIM,
                HEAD_V_DIM,
                conv_state=conv_work,
                ssm_state=ssm_work,
                conv_weights=source["conv_weights"],
                conv_bias=None,
                activation="silu",
                A_log=source["A_log"],
                dt_bias=source["dt_bias"],
                num_prefills=1,
                num_decodes=0,
                has_initial_state=has_initial_state,
                non_spec_query_start_loc=query_start,
                non_spec_state_indices_tensor=state_index,
                num_actual_tokens=tokens,
                tp_size=TP_SIZE,
                reorder_input=True,
            )
            native_calls += 1
            if mode == "isolated":
                torch.xpu.synchronize()
            nonselected_rows = [
                candidate for candidate in range(CACHE_ROWS) if candidate != row
            ]
            queued_snapshots.append({
                "iteration": iteration,
                "state_row": row,
                "nonselected_rows": nonselected_rows,
                "poison": poison,
                "core": core_work.clone(),
                "z": z_work.clone(),
                "qkvz": qkvz_work.clone(),
                "ba": ba_work.clone(),
                "conv_state": conv_work[row, :ACTIVE_CONV_COLUMNS].clone(),
                "conv_reserved": conv_work[row, ACTIVE_CONV_COLUMNS:].clone(),
                "conv_nonselected": conv_work[nonselected_rows].clone(),
                "ssm_state": ssm_work[row].clone(),
                "ssm_nonselected": ssm_work[nonselected_rows].clone(),
                "state_index": state_index.clone(),
            })
        torch.xpu.synchronize()
        for snapshot in queued_snapshots:
            for name in (
                "core", "z", "qkvz", "ba", "conv_state", "conv_reserved",
                "conv_nonselected", "ssm_state", "ssm_nonselected",
                "state_index",
            ):
                snapshot[name] = snapshot[name].cpu()
            if reference is None:
                reference = {
                    name: snapshot[name]
                    for name in ("core", "z", "conv_state", "ssm_state")
                }
                reference_digests = {
                    name: cpu_tensor_digest(torch, value)
                    for name, value in reference.items()
                }
            assert reference_digests is not None
            tensors = {
                "core": compare_tensor(
                    torch, snapshot["core"], reference["core"],
                    sentinel=snapshot["poison"],
                    reference_digest=reference_digests["core"],
                ),
                "z": compare_tensor(
                    torch, snapshot["z"], reference["z"],
                    sentinel=snapshot["poison"],
                    reference_digest=reference_digests["z"],
                ),
                "conv_state": compare_tensor(
                    torch, snapshot["conv_state"], reference["conv_state"],
                    reference_digest=reference_digests["conv_state"],
                ),
                "ssm_state": compare_tensor(
                    torch, snapshot["ssm_state"], reference["ssm_state"],
                    reference_digest=reference_digests["ssm_state"],
                ),
            }
            reserved = compare_tensor(
                torch,
                snapshot["conv_reserved"],
                cpu_inputs["conv_state"][
                    snapshot["state_row"], ACTIVE_CONV_COLUMNS:
                ],
                reference_digest=row_reference_digests[
                    snapshot["state_row"]
                ]["conv_reserved"],
            )
            working_inputs = {
                "qkvz": compare_tensor(
                    torch, snapshot["qkvz"], cpu_inputs["qkvz"],
                    reference_digest=input_digests["qkvz"],
                ),
                "ba": compare_tensor(
                    torch, snapshot["ba"], cpu_inputs["ba"],
                    reference_digest=input_digests["ba"],
                ),
            }
            nonselected_rows = snapshot["nonselected_rows"]
            nonselected_state_scope = {
                "conv_unchanged": compare_tensor(
                    torch,
                    snapshot["conv_nonselected"],
                    cpu_inputs["conv_state"][nonselected_rows],
                    reference_digest=row_reference_digests[
                        snapshot["state_row"]
                    ]["conv_nonselected"],
                ),
                "ssm_unchanged": compare_tensor(
                    torch,
                    snapshot["ssm_nonselected"],
                    cpu_inputs["ssm_state"][nonselected_rows],
                    reference_digest=row_reference_digests[
                        snapshot["state_row"]
                    ]["ssm_nonselected"],
                ),
            }
            expected_state_index = torch.tensor(
                [snapshot["state_row"]], dtype=torch.int32
            )
            state_index_check = compare_tensor(
                torch, snapshot["state_index"], expected_state_index,
                reference_digest=row_reference_digests[
                    snapshot["state_row"]
                ]["state_index"],
            )
            checks = {
                **{f"tensor.{name}": tensor_comparison_pass(item)
                   for name, item in tensors.items()},
                "reserved_conv_unchanged": tensor_comparison_pass(reserved),
                **{
                    f"working_input.{name}": tensor_comparison_pass(item)
                    for name, item in working_inputs.items()
                },
                **{
                    f"nonselected_state.{name}": tensor_comparison_pass(item)
                    for name, item in nonselected_state_scope.items()
                },
                "state_index_unchanged": tensor_comparison_pass(state_index_check),
            }
            failed_checks = [name for name, passed in checks.items() if not passed]
            observation_pass = not failed_checks
            observation = {
                "iteration": snapshot["iteration"],
                "state_row": snapshot["state_row"],
                "nonselected_rows": nonselected_rows,
                "output_poison": snapshot["poison"],
                "passed": observation_pass,
                "failed_checks": failed_checks,
                "tensors": tensors,
                "immutable_working_inputs": working_inputs,
                "reserved_conv_unchanged": reserved,
                "nonselected_state_scope": nonselected_state_scope,
                "state_index_unchanged": state_index_check,
            }
            observations.append(observation)
            if first_failure is None and not observation_pass:
                first_failure = {
                    "scope": "observation",
                    "mode": mode,
                    "prompt_index": prompt_index,
                    "tokens": tokens,
                    "batch_start": batch_start,
                    "batch_stop": batch_stop,
                    "iteration": snapshot["iteration"],
                    "state_row": snapshot["state_row"],
                    "failed_checks": failed_checks,
                    "native_calls_at_detection": native_calls,
                }
        if first_failure is not None:
            break

    if reference is None or reference_digests is None:
        raise ContractError("execution produced no reference observation")

    immutable_working_inputs = {
        "qkvz": compare_tensor(
            torch, qkvz_work, source["qkvz"],
            reference_digest=input_digests["qkvz"],
        ),
        "ba": compare_tensor(
            torch, ba_work, source["ba"], reference_digest=input_digests["ba"]
        ),
    }
    working_inputs_preserved = all(
        item["equal_reference"] and item["finite"]
        for item in immutable_working_inputs.values()
    )
    immutable_source_inputs = {}
    for name, tensor in source.items():
        observed_digest = xpu_tensor_digest(torch, tensor)
        expected_digest = input_digests[name]
        immutable_source_inputs[name] = {
            "equal_original": observed_digest == expected_digest,
            "finite": bool(torch.isfinite(tensor).all().item()),
            "expected": expected_digest,
            "observed": observed_digest,
        }
    metadata_after = {
        "query_start": xpu_tensor_digest(torch, query_start),
        "has_initial_state": xpu_tensor_digest(torch, has_initial_state),
    }
    metadata_preserved = metadata_after == metadata_digests
    sources_preserved = all(
        item["equal_original"] and item["finite"]
        for item in immutable_source_inputs.values()
    )
    final_row = rows[native_calls - 1]
    other_rows = [row for row in range(CACHE_ROWS) if row != final_row]
    state_side_effect_scope = {
        "final_selected_row": final_row,
        "nonselected_conv_unchanged": compare_tensor(
            torch, conv_work[other_rows], source["conv_state"][other_rows],
            reference_digest=row_reference_digests[final_row]["conv_nonselected"],
        ),
        "nonselected_ssm_unchanged": compare_tensor(
            torch, ssm_work[other_rows], source["ssm_state"][other_rows],
            reference_digest=row_reference_digests[final_row]["ssm_nonselected"],
        ),
    }
    scoped = all(
        tensor_comparison_pass(state_side_effect_scope[name])
        for name in ("nonselected_conv_unchanged", "nonselected_ssm_unchanged")
    )
    observations_passed = all(item["passed"] for item in observations)
    postflight_checks = {
        "observations": observations_passed,
        "immutable_working_inputs": working_inputs_preserved,
        "immutable_source_inputs": sources_preserved,
        "metadata": metadata_preserved,
        "state_side_effect_scope": scoped,
    }
    pass_all = (
        observations_passed
        and working_inputs_preserved
        and sources_preserved
        and metadata_preserved
        and scoped
    )
    if first_failure is None and not pass_all:
        first_failure = {
            "scope": "case_postflight",
            "mode": mode,
            "prompt_index": prompt_index,
            "tokens": tokens,
            "batch_start": ((native_calls - 1) // batch_calls) * batch_calls,
            "batch_stop": native_calls,
            "iteration": native_calls - 1,
            "state_row": final_row,
            "failed_checks": [
                name for name, passed in postflight_checks.items() if not passed
            ],
            "native_calls_at_detection": native_calls,
        }
    return ({
        "prompt_index": prompt_index,
        "label": label,
        "mode": mode,
        "tokens": tokens,
        "seed": seed,
        "calls": calls,
        "row_schedule": list(rows),
        "executed_row_schedule": list(rows[:native_calls]),
        "queued_batch_calls": batch_calls,
        "complete_cache_reset_each_call": True,
        "selected_state_rows_have_distinct_fixture_values": True,
        "finite_stale_output_poison_invariance": True,
        "alternating_finite_output_poison": list(OUTPUT_SENTINELS),
        "native_calls": native_calls,
        "input_digests": input_digests,
        "immutable_working_inputs": immutable_working_inputs,
        "immutable_source_inputs": immutable_source_inputs,
        "metadata_before": metadata_digests,
        "metadata_after": metadata_after,
        "metadata_preserved": metadata_preserved,
        "state_side_effect_scope": state_side_effect_scope,
        "reference_digests": reference_digests,
        "observations": observations,
        "first_failure": first_failure,
        "passed": pass_all,
    }, native_calls, first_failure)


def import_native_operator(torch: Any) -> tuple[Any, dict[str, Any]]:
    if any(name == "vllm_xpu_kernels" or name.startswith("vllm_xpu_kernels.")
           for name in sys.modules):
        raise ContractError("vllm_xpu_kernels was imported before identity checks")
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(STAGE))
    importlib.invalidate_caches()
    package = importlib.import_module("vllm_xpu_kernels")
    native = importlib.import_module("vllm_xpu_kernels._xpu_C")
    package_path = Path(package.__file__).resolve()
    native_path = Path(native.__file__).resolve()
    expected_package_path = (STAGE_PACKAGE / "__init__.py").resolve()
    expected_native_path = (STAGE_PACKAGE / "_xpu_C.abi3.so").resolve()
    if package_path != expected_package_path:
        raise ContractError(
            f"loaded package path mismatch: expected {expected_package_path}, "
            f"got {package_path}"
        )
    if native_path != expected_native_path:
        raise ContractError(
            f"loaded native path mismatch: expected {expected_native_path}, "
            f"got {native_path}"
        )
    if not hasattr(torch.ops._xpu_C, "gdn_attention"):
        raise ContractError("staged extension did not register _xpu_C::gdn_attention")
    operator = torch.ops._xpu_C.gdn_attention
    schema = str(operator.default._schema)
    if "_xpu_C::gdn_attention" not in schema:
        raise ContractError(f"unexpected native operator schema: {schema}")
    mapped_gdn = mapped_gdn_library()
    return operator, {
        "package_path": str(package_path),
        "native_module_path": str(native_path),
        "native_module_sha256": sha256_file(native_path),
        "operator": "_xpu_C::gdn_attention",
        "operator_schema": schema,
        "direct_raw_op_call": True,
        "mapped_gdn_library": mapped_gdn,
    }


def mapped_gdn_library() -> dict[str, str]:
    expected_path = (STAGE_PACKAGE / "libgdn_attn_kernels_xe_2.so").resolve()
    mapped_paths: set[Path] = set()
    for line in Path("/proc/self/maps").read_text().splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) == 6 and fields[5].startswith("/"):
            raw_path = fields[5].removesuffix(" (deleted)")
            candidate = Path(raw_path)
            if candidate.name == expected_path.name:
                if fields[5].endswith(" (deleted)"):
                    raise ContractError(f"mapped GDN library was deleted: {fields[5]}")
                mapped_paths.add(candidate.resolve())
    if mapped_paths != {expected_path}:
        raise ContractError(
            f"mapped GDN library mismatch: expected {[str(expected_path)]}, "
            f"got {sorted(map(str, mapped_paths))}"
        )
    mapped_sha = require_file_sha(
        expected_path, EXPECTED["gdn_library_sha256"], "mapped GDN library"
    )
    return {"path": str(expected_path), "sha256": mapped_sha}


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise ContractError(f"refusing to overwrite output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists():
        raise ContractError(f"temporary output already exists: {temporary}")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def execute_run(args: argparse.Namespace) -> int:
    temporary_output = args.json_out.with_name(args.json_out.name + ".tmp")
    if args.json_out.exists():
        raise ContractError(f"refusing to rerun over existing output: {args.json_out}")
    if temporary_output.exists():
        raise ContractError(
            f"refusing to run with existing temporary output: {temporary_output}"
        )
    if args.process_index == 9000:
        contract_name = "qualification"
        qualification_binding = None
        if args.qualification_json is not None:
            raise ContractError(
                "qualification run must not receive --qualification-json"
            )
    elif args.process_index in PREREG_CONTRACTS["main"]:
        contract_name = "main"
        if args.qualification_json is None:
            raise ContractError("main run requires --qualification-json")
        qualification_binding = validate_qualification_binding(
            args.qualification_json
        )
    else:
        raise ContractError(
            "process index must be qualification 9000 or main 0,1,2,3"
        )
    expected_calls, expected_order, expected_mode_order = PREREG_CONTRACTS[
        contract_name
    ][args.process_index]
    if (
        args.calls != expected_calls
        or args.order != expected_order
        or args.mode_order != expected_mode_order
    ):
        raise ContractError(
            f"run arguments do not match frozen {contract_name} process "
            f"{args.process_index} contract"
        )
    identity = preflight(args.physical_gpu)
    identity["qualification_binding"] = qualification_binding
    import torch

    if not torch.xpu.is_available():
        raise ContractError("torch.xpu is unavailable")
    device_count = int(torch.xpu.device_count())
    if device_count != 1:
        raise ContractError(
            f"affinity-isolated process must see exactly one XPU, got {device_count}"
        )
    torch.xpu.set_device(0)
    _, engagement = import_native_operator(torch)
    cases: list[dict[str, Any]] = []
    native_calls = 0
    first_failure: dict[str, Any] | None = None
    cases_by_index = {index: (label, tokens) for index, label, tokens in TOKEN_CASES}
    for mode in args.mode_order:
        for prompt_index in args.order:
            label, tokens = cases_by_index[prompt_index]
            case, calls, case_failure = run_case(
                torch,
                prompt_index=prompt_index,
                label=label,
                tokens=tokens,
                seed=BASE_SEED + prompt_index,
                calls=args.calls,
                mode=mode,
            )
            cases.append(case)
            native_calls += calls
            if case_failure is not None:
                first_failure = case_failure
                break
        if first_failure is not None:
            break
    expected_calls = len(EXECUTION_MODES) * len(TOKEN_CASES) * args.calls
    engagement.update({
        "native_call_count": native_calls,
        "planned_native_call_count": expected_calls,
        "engaged": native_calls > 0,
        "completed_planned_calls": native_calls == expected_calls,
    })
    postflight_stage = verify_complete_stage()
    postflight_mapped_gdn_library = mapped_gdn_library()
    if postflight_stage != identity["stage"]:
        raise ContractError("composite stage changed between preflight and postflight")
    if postflight_mapped_gdn_library != engagement["mapped_gdn_library"]:
        raise ContractError("mapped GDN library changed between import and postflight")
    if not engagement["engaged"]:
        raise ContractError("native GDN operator was never invoked")
    pass_all = (
        engagement["completed_planned_calls"]
        and all(case["passed"] for case in cases)
        and len(cases) == len(EXECUTION_MODES) * len(TOKEN_CASES)
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic": "qwen38-native-sycl-gdn-prefill-state-stability",
        "status": "pass" if pass_all else "fail",
        "valid": True,
        "scientific_classification": (
            "bounded-negative" if pass_all else "scientific-positive"
        ),
        "identity": identity,
        "execution": {
            "contract": contract_name,
            "process_index": args.process_index,
            "calls_per_length": args.calls,
            "prompt_order": list(args.order),
            "mode_order": list(args.mode_order),
            "fresh_process_required": True,
            "qualification_binding": qualification_binding,
        },
        "runtime": {
            "torch_version": torch.__version__,
            "torch_xpu_version": getattr(torch.version, "xpu", None),
            "visible_xpu_count": device_count,
            "device_properties": str(torch.xpu.get_device_properties(0)),
        },
        "engagement": engagement,
        "postflight_stage": postflight_stage,
        "postflight_mapped_gdn_library": postflight_mapped_gdn_library,
        "summary": {
            "pass_all": pass_all,
            "scientific_positive": not pass_all,
            "completed_full_schedule": native_calls == expected_calls,
            "planned_native_call_count": expected_calls,
            "case_count": len(cases),
            "passed_cases": sum(case["passed"] for case in cases),
            "native_call_count": native_calls,
            "first_failure": first_failure,
            "host_sync_policy": {
                "isolated": "before-and-after-each-native-call",
                "queued": f"once-per-{QUEUED_BATCH_CALLS}-call-batch",
            },
        },
        "cases": cases,
    }
    atomic_write_json(args.json_out, payload)
    print(json.dumps({
        "json": str(args.json_out),
        "status": payload["status"],
        "physical_gpu": args.physical_gpu,
        "process_index": args.process_index,
        "native_call_count": native_calls,
        "first_failure": first_failure,
    }, sort_keys=True))
    return 0 if pass_all else 1


def load_result(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ContractError(f"result does not exist: {path}")
    payload = json.loads(path.read_text())
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(f"unsupported result schema in {path}")
    if payload.get("valid") is not True or payload.get("status") not in {
        "pass", "fail"
    }:
        raise ContractError(f"invalid raw-op result envelope in {path}")
    return payload


def index_results(paths: list[Path], physical_gpu: int) -> dict[int, tuple[Path, dict[str, Any]]]:
    indexed: dict[int, tuple[Path, dict[str, Any]]] = {}
    for path in paths:
        payload = load_result(path)
        observed_gpu = payload["identity"]["process"]["physical_gpu"]
        if observed_gpu != physical_gpu:
            raise ContractError(
                f"{path} claims physical GPU {observed_gpu}, expected {physical_gpu}"
            )
        process_index = payload["execution"]["process_index"]
        if process_index in indexed:
            raise ContractError(
                f"duplicate physical GPU {physical_gpu} process index {process_index}"
            )
        indexed[process_index] = (path, payload)
    return indexed


def validate_passing_case_evidence(case: dict[str, Any], calls: int) -> None:
    prompt_index = case.get("prompt_index")
    mode = case.get("mode")
    context = f"prompt {prompt_index}, mode {mode}"
    observations = case.get("observations")
    reference_digests = case.get("reference_digests")
    if not isinstance(observations, list) or len(observations) != calls:
        raise ContractError(f"observation count mismatch for {context}")
    if not isinstance(reference_digests, dict) or set(reference_digests) != {
        "core", "z", "conv_state", "ssm_state"
    }:
        raise ContractError(f"reference-digest keys mismatch for {context}")
    rows = row_schedule(calls)
    for iteration, observation in enumerate(observations):
        expected_row = rows[iteration]
        expected_nonselected = [
            row for row in range(CACHE_ROWS) if row != expected_row
        ]
        if (
            observation.get("iteration") != iteration
            or observation.get("state_row") != expected_row
            or observation.get("nonselected_rows") != expected_nonselected
            or observation.get("output_poison")
            != OUTPUT_SENTINELS[iteration % len(OUTPUT_SENTINELS)]
        ):
            raise ContractError(
                f"observation coordinates mismatch for {context}, iteration {iteration}"
            )
        tensors = observation.get("tensors")
        working = observation.get("immutable_working_inputs")
        nonselected = observation.get("nonselected_state_scope")
        if not isinstance(tensors, dict) or set(tensors) != {
            "core", "z", "conv_state", "ssm_state"
        }:
            raise ContractError(f"tensor evidence keys mismatch for {context}")
        if any(
            not isinstance(item, dict)
            or item.get("reference_digest") != reference_digests[name]
            for name, item in tensors.items()
        ):
            raise ContractError(f"tensor reference binding mismatch for {context}")
        if not isinstance(working, dict) or set(working) != {"qkvz", "ba"}:
            raise ContractError(f"working-input evidence keys mismatch for {context}")
        if not isinstance(nonselected, dict) or set(nonselected) != {
            "conv_unchanged", "ssm_unchanged"
        }:
            raise ContractError(f"nonselected-state evidence keys mismatch for {context}")
        derived_checks = {
            **{
                f"tensor.{name}": tensor_comparison_pass(item)
                for name, item in tensors.items()
            },
            "reserved_conv_unchanged": tensor_comparison_pass(
                observation.get("reserved_conv_unchanged", {})
            ),
            **{
                f"working_input.{name}": tensor_comparison_pass(item)
                for name, item in working.items()
            },
            **{
                f"nonselected_state.{name}": tensor_comparison_pass(item)
                for name, item in nonselected.items()
            },
            "state_index_unchanged": tensor_comparison_pass(
                observation.get("state_index_unchanged", {})
            ),
        }
        failed_checks = [
            name for name, passed in derived_checks.items() if not passed
        ]
        derived_pass = not failed_checks
        if (
            observation.get("failed_checks") != failed_checks
            or observation.get("passed") is not derived_pass
            or not derived_pass
        ):
            raise ContractError(
                f"nested observation evidence failed for {context}, "
                f"iteration {iteration}: {failed_checks}"
            )

    final_working = case.get("immutable_working_inputs")
    if (
        not isinstance(final_working, dict)
        or set(final_working) != {"qkvz", "ba"}
        or not all(tensor_comparison_pass(item) for item in final_working.values())
    ):
        raise ContractError(f"final working-input evidence failed for {context}")
    input_digests = case.get("input_digests")
    source_inputs = case.get("immutable_source_inputs")
    if (
        not isinstance(input_digests, dict)
        or not isinstance(source_inputs, dict)
        or set(source_inputs) != set(input_digests)
        or set(input_digests)
        != {
            "qkvz", "ba", "conv_weights", "conv_state", "ssm_state",
            "A_log", "dt_bias",
        }
    ):
        raise ContractError(f"source-input evidence keys mismatch for {context}")
    if any(
        item.get("reference_digest") != input_digests[name]
        for name, item in final_working.items()
    ):
        raise ContractError(f"final working-input binding failed for {context}")
    for observation in observations:
        if any(
            item.get("reference_digest") != input_digests[name]
            for name, item in observation["immutable_working_inputs"].items()
        ):
            raise ContractError(f"per-call working-input binding failed for {context}")
    for name, item in source_inputs.items():
        if (
            not isinstance(item, dict)
            or item.get("equal_original")
            is not (item.get("expected") == item.get("observed"))
            or item.get("equal_original") is not True
            or item.get("finite") is not True
            or item.get("expected") != input_digests[name]
        ):
            raise ContractError(
                f"immutable source evidence failed for {context}, tensor {name}"
            )
    metadata_equal = case.get("metadata_before") == case.get("metadata_after")
    if (
        case.get("metadata_preserved") is not metadata_equal
        or not metadata_equal
    ):
        raise ContractError(f"metadata evidence failed for {context}")
    state_scope = case.get("state_side_effect_scope")
    if (
        not isinstance(state_scope, dict)
        or state_scope.get("final_selected_row") != rows[-1]
        or not tensor_comparison_pass(
            state_scope.get("nonselected_conv_unchanged", {})
        )
        or not tensor_comparison_pass(
            state_scope.get("nonselected_ssm_unchanged", {})
        )
    ):
        raise ContractError(f"final state-scope evidence failed for {context}")
    if (
        case.get("complete_cache_reset_each_call") is not True
        or case.get("selected_state_rows_have_distinct_fixture_values") is not True
        or case.get("finite_stale_output_poison_invariance") is not True
        or case.get("alternating_finite_output_poison") != list(OUTPUT_SENTINELS)
        or case.get("executed_row_schedule") != list(rows)
        or case.get("first_failure") is not None
        or case.get("passed") is not True
    ):
        raise ContractError(f"derived case pass contract failed for {context}")


def validate_preregistered_contract(
    contract_name: str,
    gpu2: dict[int, tuple[Path, dict[str, Any]]],
    gpu3: dict[int, tuple[Path, dict[str, Any]]],
    qualification_binding: dict[str, Any] | None,
) -> dict[str, Any]:
    expected = PREREG_CONTRACTS[contract_name]
    expected_indices = set(expected)
    current_script_sha = sha256_file(SCRIPT_PATH)
    current_shape = shape_contract()
    if set(gpu2) != expected_indices or set(gpu3) != expected_indices:
        raise ContractError(
            f"{contract_name} comparison requires process indices "
            f"{sorted(expected_indices)} on each GPU; got GPU2={sorted(gpu2)}, "
            f"GPU3={sorted(gpu3)}"
        )
    for process_index, (calls, prompt_order, mode_order) in expected.items():
        expected_execution = {
            "contract": contract_name,
            "process_index": process_index,
            "calls_per_length": calls,
            "prompt_order": list(prompt_order),
            "mode_order": list(mode_order),
            "fresh_process_required": True,
            "qualification_binding": qualification_binding,
        }
        for physical_gpu, indexed in ((2, gpu2), (3, gpu3)):
            payload = indexed[process_index][1]
            if payload.get("valid") is not True or payload.get("status") != "pass":
                raise ContractError(
                    f"{contract_name} input is not a valid pass for GPU "
                    f"{physical_gpu} process {process_index}"
                )
            identity = payload.get("identity", {})
            if (
                identity.get("script") != str(SCRIPT_PATH)
                or identity.get("script_sha256") != current_script_sha
            ):
                raise ContractError(
                    f"{contract_name} current-script binding mismatch for GPU "
                    f"{physical_gpu} process {process_index}"
                )
            if identity.get("shape") != current_shape:
                raise ContractError(
                    f"{contract_name} current shape contract mismatch for GPU "
                    f"{physical_gpu} process {process_index}"
                )
            if identity.get("qualification_binding") != qualification_binding:
                raise ContractError(
                    f"{contract_name} qualification binding mismatch for GPU "
                    f"{physical_gpu} process {process_index}"
                )
            observed = payload.get("execution")
            if observed != expected_execution:
                raise ContractError(
                    f"{contract_name} execution mismatch for GPU {physical_gpu} "
                    f"process {process_index}: expected {expected_execution}, "
                    f"got {observed}"
                )
            expected_cases = [
                (mode, prompt_index)
                for mode in mode_order
                for prompt_index in prompt_order
            ]
            observed_cases = [
                (case.get("mode"), case.get("prompt_index"))
                for case in payload.get("cases", [])
            ]
            if observed_cases != expected_cases:
                raise ContractError(
                    f"{contract_name} case order mismatch for GPU {physical_gpu} "
                    f"process {process_index}: expected {expected_cases}, "
                    f"got {observed_cases}"
                )
            expected_native_calls = (
                len(EXECUTION_MODES) * len(TOKEN_CASES) * calls
            )
            cases_by_index = {
                index: (label, tokens) for index, label, tokens in TOKEN_CASES
            }
            for case in payload["cases"]:
                expected_seed = BASE_SEED + case["prompt_index"]
                expected_label, expected_tokens = cases_by_index[case["prompt_index"]]
                expected_batch_calls = (
                    1 if case["mode"] == "isolated" else QUEUED_BATCH_CALLS
                )
                if (
                    case.get("calls") != calls
                    or case.get("native_calls") != calls
                    or case.get("seed") != expected_seed
                    or case.get("label") != expected_label
                    or case.get("tokens") != expected_tokens
                    or case.get("row_schedule") != list(row_schedule(calls))
                    or case.get("queued_batch_calls") != expected_batch_calls
                ):
                    raise ContractError(
                        f"{contract_name} case contract mismatch for GPU "
                        f"{physical_gpu} process {process_index}, prompt "
                        f"{case.get('prompt_index')}, mode {case.get('mode')}"
                    )
                validate_passing_case_evidence(case, calls)
            engagement = payload.get("engagement", {})
            if (
                engagement.get("engaged") is not True
                or engagement.get("completed_planned_calls") is not True
                or engagement.get("native_call_count")
                != expected_native_calls
                or engagement.get("planned_native_call_count")
                != expected_native_calls
            ):
                raise ContractError(
                    f"{contract_name} engagement mismatch for GPU "
                    f"{physical_gpu} process {process_index}"
                )
            expected_summary = {
                "pass_all": True,
                "scientific_positive": False,
                "completed_full_schedule": True,
                "planned_native_call_count": expected_native_calls,
                "case_count": len(EXECUTION_MODES) * len(TOKEN_CASES),
                "passed_cases": len(EXECUTION_MODES) * len(TOKEN_CASES),
                "native_call_count": expected_native_calls,
                "first_failure": None,
                "host_sync_policy": {
                    "isolated": "before-and-after-each-native-call",
                    "queued": f"once-per-{QUEUED_BATCH_CALLS}-call-batch",
                },
            }
            if payload.get("summary") != expected_summary:
                raise ContractError(
                    f"{contract_name} summary contract mismatch for GPU "
                    f"{physical_gpu} process {process_index}"
                )
            if payload.get("scientific_classification") != "bounded-negative":
                raise ContractError(
                    f"{contract_name} classification mismatch for GPU "
                    f"{physical_gpu} process {process_index}"
                )
            if payload.get("postflight_stage") != identity.get("stage"):
                raise ContractError(
                    f"{contract_name} pre/post stage mismatch for GPU "
                    f"{physical_gpu} process {process_index}"
                )
            if (
                payload.get("postflight_mapped_gdn_library")
                != engagement.get("mapped_gdn_library")
            ):
                raise ContractError(
                    f"{contract_name} import/postflight GDN mapping mismatch for "
                    f"GPU {physical_gpu} process {process_index}"
                )
    calls_per_process_pair = {
        process_index: 2 * len(EXECUTION_MODES) * len(TOKEN_CASES) * values[0]
        for process_index, values in expected.items()
    }
    return {
        "name": contract_name,
        "process_indices": sorted(expected_indices),
        "result_file_count": len(gpu2) + len(gpu3),
        "native_call_count": sum(calls_per_process_pair.values()),
        "calls_per_process_pair": calls_per_process_pair,
        "validated": True,
    }


def validate_qualification_binding(path: Path) -> dict[str, Any]:
    path = path.resolve()
    payload = load_result(path)
    if (
        payload.get("diagnostic")
        != "qwen38-native-sycl-gdn-prefill-cross-device-comparison"
        or payload.get("status") != "pass"
        or payload.get("valid") is not True
        or payload.get("qualification_binding") is not None
    ):
        raise ContractError("qualification comparison is not a valid pass")
    expected_binding = {
        "script": str(SCRIPT_PATH),
        "script_sha256": sha256_file(SCRIPT_PATH),
        "shape": shape_contract(),
    }
    if payload.get("identity_binding") != expected_binding:
        raise ContractError("qualification comparison has stale script/shape binding")
    expected_contract = {
        "name": "qualification",
        "process_indices": [9000],
        "result_file_count": 2,
        "native_call_count": 240,
        "calls_per_process_pair": {"9000": 240},
        "validated": True,
    }
    if payload.get("contract") != expected_contract:
        raise ContractError("qualification comparison contract is not exact")
    expected_summary = {
        "pass_all": True,
        "identity_equal": True,
        "all_individual_results_passed": True,
        "case_count": 6,
        "aggregate_case_count": 12,
        "all_cross_process_reference_digests_equal": True,
        "result_file_count": 2,
        "native_call_count": 240,
    }
    if payload.get("summary") != expected_summary:
        raise ContractError("qualification comparison summary is not exact")
    inputs = payload.get("inputs")
    if (
        not isinstance(inputs, list)
        or [(item.get("physical_gpu"), item.get("process_index")) for item in inputs]
        != [(2, 9000), (3, 9000)]
        or any(
            not isinstance(item.get("path"), str)
            or re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", "")) is None
            for item in inputs
        )
    ):
        raise ContractError("qualification comparison inputs are not exact")
    comparisons = payload.get("comparisons")
    aggregate = payload.get("aggregate_comparisons")
    if (
        not isinstance(comparisons, list)
        or len(comparisons) != 6
        or any(
            item.get("same_case") is not True
            or item.get("input_digests_equal") is not True
            or set(item.get("reference_tensor_digests_equal", {}))
            != {"core", "z", "conv_state", "ssm_state"}
            or not all(item["reference_tensor_digests_equal"].values())
            or item.get("passed") is not True
            for item in comparisons
        )
        or not isinstance(aggregate, list)
        or len(aggregate) != 12
        or any(
            item.get("same_cpu_fixture") is not True
            or set(item.get("reference_tensor_digests_equal", {}))
            != {"core", "z", "conv_state", "ssm_state"}
            or not all(item["reference_tensor_digests_equal"].values())
            or item.get("passed") is not True
            for item in aggregate
        )
    ):
        raise ContractError("qualification comparison evidence is not exact")
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "status": "pass",
        "script_sha256": expected_binding["script_sha256"],
        "shape": expected_binding["shape"],
    }


def execute_compare(args: argparse.Namespace) -> int:
    if args.contract == "main":
        if args.qualification_json is None:
            raise ContractError("main comparison requires --qualification-json")
        qualification_binding = validate_qualification_binding(
            args.qualification_json
        )
    else:
        if args.qualification_json is not None:
            raise ContractError(
                "qualification comparison must not receive --qualification-json"
            )
        qualification_binding = None
    gpu2 = index_results(args.gpu2_json, 2)
    gpu3 = index_results(args.gpu3_json, 3)
    contract = validate_preregistered_contract(
        args.contract, gpu2, gpu3, qualification_binding
    )
    identity_fields = ("model", "source", "stage", "shape", "script_sha256")
    first_index = contract["process_indices"][0]
    identity_reference = gpu2[first_index][1]["identity"]
    all_payloads = [item[1] for item in gpu2.values()] + [item[1] for item in gpu3.values()]
    identity_equal = all(
        payload["identity"][field] == identity_reference[field]
        for payload in all_payloads
        for field in identity_fields
    )
    comparisons: list[dict[str, Any]] = []
    for process_index in contract["process_indices"]:
        left = gpu2[process_index][1]
        right = gpu3[process_index][1]
        if left.get("execution") != right.get("execution"):
            raise ContractError(
                f"GPU 2/3 execution contracts differ for process {process_index}"
            )
        for left_case, right_case in zip(left["cases"], right["cases"], strict=True):
            same_case = (
                left_case["prompt_index"] == right_case["prompt_index"]
                and left_case["mode"] == right_case["mode"]
                and left_case["tokens"] == right_case["tokens"]
                and left_case["seed"] == right_case["seed"]
            )
            input_equal = left_case["input_digests"] == right_case["input_digests"]
            tensor_equal = {
                name: (
                    left_case["reference_digests"][name]
                    == right_case["reference_digests"][name]
                )
                for name in ("core", "z", "conv_state", "ssm_state")
            }
            case_pass = same_case and input_equal and all(tensor_equal.values())
            comparisons.append({
                "process_index": process_index,
                "prompt_index": left_case["prompt_index"],
                "mode": left_case["mode"],
                "tokens": left_case["tokens"],
                "same_case": same_case,
                "input_digests_equal": input_equal,
                "reference_tensor_digests_equal": tensor_equal,
                "passed": case_pass,
            })
    canonical_cases = {
        case["prompt_index"]: case
        for case in gpu2[first_index][1]["cases"]
        if case["mode"] == EXECUTION_MODES[0]
    }
    if set(canonical_cases) != {index for index, _, _ in TOKEN_CASES}:
        raise ContractError("canonical result lacks one isolated case per prompt")
    aggregate_comparisons: list[dict[str, Any]] = []
    for physical_gpu, indexed in ((2, gpu2), (3, gpu3)):
        for process_index, (_, observed_payload) in sorted(indexed.items()):
            for observed_case in observed_payload["cases"]:
                canonical = canonical_cases[observed_case["prompt_index"]]
                same_fixture = (
                    observed_case["tokens"] == canonical["tokens"]
                    and observed_case["seed"] == canonical["seed"]
                    and observed_case["input_digests"] == canonical["input_digests"]
                )
                tensor_equal = {
                    name: (
                        observed_case["reference_digests"][name]
                        == canonical["reference_digests"][name]
                    )
                    for name in ("core", "z", "conv_state", "ssm_state")
                }
                aggregate_comparisons.append({
                    "physical_gpu": physical_gpu,
                    "process_index": process_index,
                    "prompt_index": observed_case["prompt_index"],
                    "mode": observed_case["mode"],
                    "same_cpu_fixture": same_fixture,
                    "reference_tensor_digests_equal": tensor_equal,
                    "passed": same_fixture and all(tensor_equal.values()),
                })
    pass_all = (
        identity_equal
        and all(payload["summary"]["pass_all"] is True for payload in all_payloads)
        and all(
            len(payload["cases"]) == len(EXECUTION_MODES) * len(TOKEN_CASES)
            for payload in all_payloads
        )
        and all(item["passed"] for item in comparisons)
        and all(item["passed"] for item in aggregate_comparisons)
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic": "qwen38-native-sycl-gdn-prefill-cross-device-comparison",
        "status": "pass" if pass_all else "fail",
        "valid": True,
        "identity_binding": {
            "script": str(SCRIPT_PATH),
            "script_sha256": sha256_file(SCRIPT_PATH),
            "shape": shape_contract(),
        },
        "qualification_binding": qualification_binding,
        "contract": contract,
        "inputs": [
            {
                "physical_gpu": physical_gpu,
                "process_index": process_index,
                "path": str(path),
                "sha256": sha256_file(path),
            }
            for physical_gpu, indexed in ((2, gpu2), (3, gpu3))
            for process_index, (path, _) in sorted(indexed.items())
        ],
        "summary": {
            "pass_all": pass_all,
            "identity_equal": identity_equal,
            "all_individual_results_passed": all(
                payload["summary"]["pass_all"] is True for payload in all_payloads
            ),
            "case_count": len(comparisons),
            "aggregate_case_count": len(aggregate_comparisons),
            "all_cross_process_reference_digests_equal": all(
                item["passed"] for item in aggregate_comparisons
            ),
            "result_file_count": len(all_payloads),
            "native_call_count": contract["native_call_count"],
        },
        "comparisons": comparisons,
        "aggregate_comparisons": aggregate_comparisons,
    }
    atomic_write_json(args.json_out, payload)
    print(json.dumps({
        "json": str(args.json_out),
        "status": payload["status"],
    }, sort_keys=True))
    return 0 if pass_all else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight_parser = subparsers.add_parser(
        "preflight", help="validate identity and shape contract without importing torch"
    )
    preflight_parser.add_argument("--physical-gpu", type=int, choices=(2, 3), required=True)

    run_parser = subparsers.add_parser(
        "run", help="run one affinity-isolated physical-GPU raw-op oracle"
    )
    run_parser.add_argument("--physical-gpu", type=int, choices=(2, 3), required=True)
    run_parser.add_argument("--process-index", type=int, required=True)
    run_parser.add_argument("--calls", type=int, required=True)
    run_parser.add_argument("--order", type=parse_order, required=True)
    run_parser.add_argument("--mode-order", type=parse_mode_order, required=True)
    run_parser.add_argument("--qualification-json", type=Path)
    run_parser.add_argument("--json-out", type=Path, required=True)

    compare_parser = subparsers.add_parser(
        "compare", help="validate and compare a preregistered GPU2/GPU3 result set"
    )
    compare_parser.add_argument(
        "--contract", choices=tuple(PREREG_CONTRACTS), required=True
    )
    compare_parser.add_argument("--gpu2-json", type=Path, nargs="+", required=True)
    compare_parser.add_argument("--gpu3-json", type=Path, nargs="+", required=True)
    compare_parser.add_argument("--qualification-json", type=Path)
    compare_parser.add_argument("--json-out", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "preflight":
            identity = preflight(args.physical_gpu)
            print(json.dumps({
                "status": "pass",
                "physical_gpu": args.physical_gpu,
                "identity": identity,
            }, sort_keys=True))
            return 0
        if args.command == "run":
            return execute_run(args)
        if args.command == "compare":
            return execute_compare(args)
        raise AssertionError(f"unhandled command: {args.command}")
    except (
        ContractError,
        OSError,
        ValueError,
        KeyError,
        RuntimeError,
        subprocess.SubprocessError,
    ) as exc:
        artifact_written = False
        if (
            args.command == "run"
            and hasattr(args, "json_out")
            and not args.json_out.exists()
        ):
            qualification_request = None
            if args.qualification_json is not None:
                qualification_path = args.qualification_json.resolve()
                qualification_request = {
                    "path": str(qualification_path),
                    "sha256": (
                        sha256_file(qualification_path)
                        if qualification_path.is_file()
                        else None
                    ),
                }
            invalid_payload = {
                "schema_version": SCHEMA_VERSION,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "diagnostic": "qwen38-native-sycl-gdn-prefill-state-stability",
                "status": "invalid",
                "valid": False,
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
                "requested_execution": {
                    "physical_gpu": args.physical_gpu,
                    "process_index": args.process_index,
                    "calls_per_length": args.calls,
                    "prompt_order": list(args.order),
                    "mode_order": list(args.mode_order),
                    "qualification": qualification_request,
                },
                "script": str(SCRIPT_PATH),
                "script_sha256": sha256_file(SCRIPT_PATH),
            }
            try:
                atomic_write_json(args.json_out, invalid_payload)
                artifact_written = True
            except (ContractError, OSError):
                artifact_written = False
        print(json.dumps({
            "status": "invalid",
            "valid": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "artifact_written": artifact_written,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
