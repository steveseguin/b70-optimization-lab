#!/usr/bin/env python3
"""One-shot, exactness-only adapter for the Laguna shared gate/up M=8 screen.

This module deliberately has no import-time torch/vLLM side effects.  It is
not a benchmark: it contains no performance instrumentation, counter, service,
generation, network, or removable-media path.  Its first durable operation is a strict
identity checkpoint.  If tensor work begins, the result root is terminal.

The companion fixture/authorization contract is intentionally maintained in
``gate_laguna_shared_gate_up_mm_stage0.py``.  This adapter runs only from a clean,
auth-only child commit whose packet freezes every tool, source, argument, and
environment byte.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import gate_laguna_shared_gate_up_mm_stage0 as stage0


MAIN_REPO = Path("/home/steve/llm-optimizations")
VLLM_REPO = Path("/home/steve/src/deepseek-v4-vllm-xpu-dspark")
KERNEL_REPO = Path("/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc")
MODEL_CONFIG = Path("/mnt/fast-ai/llm-models/laguna-s-2.1/int4/config.json")
EXPECTED_VLLM_COMMIT = "503f7784cf9d1704109b1e4650427fb4f417d604"
EXPECTED_KERNEL_COMMIT = "c59aaadbbfd350c2b5f4ad663e247c2811ae3181"
EXPECTED_BINARY_PATHS = {
    "_C.abi3.so": KERNEL_REPO / "vllm_xpu_kernels/_C.abi3.so",
    "_xpu_C.abi3.so": KERNEL_REPO / "vllm_xpu_kernels/_xpu_C.abi3.so",
    "_moe_C.abi3.so": KERNEL_REPO / "vllm_xpu_kernels/_moe_C.abi3.so",
    "libgrouped_gemm_xe_2.so": KERNEL_REPO / "vllm_xpu_kernels/libgrouped_gemm_xe_2.so",
}
RUNTIME_ADAPTER_STATE = "READY_STAGE0_EXECUTION"
PRE_TENSOR_CHECKPOINT = "pre-tensor-identity-checkpoint.json"
TENSOR_STARTED_CHECKPOINT = "tensor-work-started-checkpoint.json"
RUNTIME_CARD0_CHECKPOINT = "runtime-card0-binding-checkpoint.json"
RUNTIME_RELATIVE_DIRECTORIES = (
    "runtime/home",
    "runtime/tmp",
    "runtime/cache/huggingface",
    "runtime/cache/numba",
    "runtime/cache/pycache",
    "runtime/cache/sycl",
    "runtime/cache/torchinductor",
    "runtime/cache/transformers",
    "runtime/cache/triton",
    "runtime/cache/vllm",
    "runtime/cache/xdg",
    "runtime/cache/xdg-config",
    "runtime/cache/xdg-data",
    "runtime/cache/xdg-state",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _runtime_file_identity(record: dict[str, str]) -> dict[str, str]:
    path = Path(record["path"])
    require(path.is_file(), f"runtime identity file is absent: {path}")
    observed = {
        "path": str(path),
        "resolved_path": str(path.resolve(strict=True)),
        "sha256": sha256_file(path),
    }
    require(observed == record, f"runtime file identity drift: {path}")
    return observed


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def clean_git_identity(repo: Path) -> dict[str, Any]:
    require(repo.is_dir() and not repo.is_symlink(), f"invalid repository: {repo}")
    status = _git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    require(not status, f"repository is not clean: {repo}")
    return {
        "path": str(repo),
        "commit": _git(repo, "rev-parse", "HEAD"),
        "clean": True,
        "status_porcelain": [],
        "status_sha256": hashlib.sha256(b"").hexdigest(),
    }


def _read_text(path: Path) -> str:
    require(
        path.is_file() and not path.is_symlink(),
        f"required regular file missing: {path}",
    )
    return path.read_text().strip()


def _sysfs_card0_identity(expected: dict[str, Any]) -> dict[str, str]:
    """Validate the physical card through immutable local DRM/sysfs mapping.

    No vendor utility or torch device discovery is used here.  The UUID is
    already frozen in the authorization packet; sysfs proves card/BDF binding.
    """
    drm = Path(expected["drm_device"])
    require(drm == Path("/dev/dri/card3"), "stage zero is physical card 0 only")
    sys_device_link = Path("/sys/class/drm/card3/device")
    # DRM class entries are symlinks by design.  Only the fully resolved
    # PCI-device target is security-relevant here.
    require(sys_device_link.exists(), "card3 sysfs identity unavailable")
    sys_device = sys_device_link.resolve(strict=True)
    require(
        sys_device.is_dir()
        and str(sys_device).startswith("/sys/devices/")
        and sys_device.name.startswith("0000:"),
        "card3 sysfs target is not a PCI device",
    )
    bdf = sys_device.name
    require(bdf == expected["pci_bdf_address"], "card3 BDF differs from packet")
    vendor = _read_text(sys_device / "vendor")
    device = _read_text(sys_device / "device")
    require(vendor == "0x8086" and device.startswith("0x"), "card3 is not Intel")
    return {
        "drm_device": str(drm),
        "pci_bdf_address": bdf,
        "vendor": vendor,
        "device": device,
    }


def _require_nvme(path: Path) -> None:
    completed = subprocess.run(
        ["findmnt", "--noheadings", "--output", "SOURCE,FSTYPE", "--target", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    rows = [line.split() for line in completed.stdout.splitlines()]
    require(
        completed.returncode == 0 and [stage0.NVME_SOURCE, stage0.NVME_FSTYPE] in rows,
        "path is not the required internal NVMe/ext4 filesystem",
    )


def _reject_usb_path(path: Path) -> None:
    resolved = path.resolve(strict=False)
    require(
        not str(resolved).startswith(("/media/", "/mnt/usb", "/run/media/")),
        f"removable-media path rejected: {resolved}",
    )


def _strict_packet_runtime_contract(
    packet: dict[str, Any],
    fixture: dict[str, Any],
    argv: list[str],
    *,
    authorization_path: Path,
    fixture_path: Path,
    result_path: Path,
) -> dict[str, Any]:
    """Perform every pre-tensor validation using only stdlib/local files."""
    stage0.validate_fixture_manifest(fixture)
    stage0.validate_authorization(packet, fixture)
    expected_runtime = packet["runtime"]["observed_identity"]
    require(
        sys.executable == expected_runtime["python_executable"]
        and sys.version == expected_runtime["python_version"],
        "Python runtime identity drift",
    )
    runtime_files = {
        name: _runtime_file_identity(record)
        for name, record in expected_runtime["files"].items()
    }
    require(
        packet["source"]["vllm_commit"] == EXPECTED_VLLM_COMMIT,
        "wrong frozen vLLM source commit",
    )
    require(
        packet["source"]["kernel_commit"] == EXPECTED_KERNEL_COMMIT,
        "wrong frozen kernel commit",
    )
    tool = packet["tools"]["runtime_adapter"]
    require(
        tool["state"] == RUNTIME_ADAPTER_STATE,
        "runtime adapter is not explicitly released by a new authorization schema",
    )
    require(
        tool["path"] == stage0.TOOL_PATHS["runtime_adapter"],
        "runtime adapter path drift",
    )
    adapter_path = MAIN_REPO / tool["path"]
    require(sha256_file(adapter_path) == tool["sha256"], "runtime adapter hash drift")
    for name, record in packet["tools"].items():
        path = MAIN_REPO / record["path"]
        require(sha256_file(path) == record["sha256"], f"tool hash drift: {name}")
    for source_path, expected_hash in packet["source"]["files"].items():
        require(
            sha256_file(VLLM_REPO / source_path) == expected_hash,
            f"vLLM source hash drift: {source_path}",
        )
    main = clean_git_identity(MAIN_REPO)
    vllm = clean_git_identity(VLLM_REPO)
    kernels = clean_git_identity(KERNEL_REPO)
    tools_commit = packet["source"]["main_commit"]
    authorization_head = main["commit"]
    require(
        _git(MAIN_REPO, "rev-parse", f"{authorization_head}^") == tools_commit,
        "authorization HEAD is not the single child of the frozen tools commit",
    )
    changed_paths = _git(
        MAIN_REPO,
        "diff-tree",
        "--no-commit-id",
        "--name-only",
        "-r",
        authorization_head,
    ).splitlines()
    packet_repo_path = packet["authorization_tracking"]["packet_repo_path"]
    require(
        changed_paths == [packet_repo_path],
        "authorization commit changed more than the frozen packet",
    )
    tracked_packet = subprocess.run(
        [
            "git",
            "-C",
            str(MAIN_REPO),
            "show",
            f"{authorization_head}:{packet_repo_path}",
        ],
        check=True,
        capture_output=True,
    ).stdout
    require(
        tracked_packet == authorization_path.read_bytes(),
        "executed authorization bytes differ from the auth-only commit",
    )
    require(vllm["commit"] == EXPECTED_VLLM_COMMIT, "vLLM checkout drift")
    require(kernels["commit"] == EXPECTED_KERNEL_COMMIT, "kernel checkout drift")
    for name, binary in EXPECTED_BINARY_PATHS.items():
        require(
            sha256_file(binary) == packet["binaries"][name],
            f"native binary drift: {name}",
        )
    require(
        MODEL_CONFIG == Path(packet["model"]["config_path"]), "model config path drift"
    )
    _reject_usb_path(MODEL_CONFIG)
    _require_nvme(MODEL_CONFIG)
    require(
        sha256_file(MODEL_CONFIG) == packet["model"]["config_sha256"],
        "model config hash drift",
    )
    require(
        _read_text(Path("/proc/sys/kernel/random/boot_id")) == packet["boot_id"],
        "boot identity drift",
    )
    environment = packet["environment"]
    required_env = stage0.expected_environment(packet["storage"]["output_root"])
    require(
        environment == required_env,
        "environment packet is not the frozen stage-zero record stack",
    )
    require(
        dict(os.environ) == required_env,
        "process environment is not exactly the frozen env-i stage-zero map",
    )
    require(
        packet["argv"] == argv,
        "argv differs from frozen authorization packet",
    )
    require(
        Path(packet["packet_path"]) == authorization_path, "authorization path drift"
    )
    require(
        authorization_path.is_file()
        and not authorization_path.is_symlink()
        and (
            str(authorization_path).startswith(str(MAIN_REPO) + "/")
            or str(authorization_path).startswith(
                str(stage0.ARTIFACT_ROOT_LITERAL) + "/"
            )
        ),
        "authorization must be a frozen repo or internal-NVMe regular file",
    )
    stage0.require_nvme_artifact_path(
        fixture_path,
        suffix=".json",
        must_exist=True,
    )
    require(
        sha256_file(fixture_path) == packet["fixture"]["file_sha256"],
        "fixture file hash drift",
    )
    _reject_usb_path(authorization_path)
    _reject_usb_path(fixture_path)
    result = result_path
    output_root = Path(packet["storage"]["output_root"])
    require(
        result == output_root / "stage0-result.json",
        "result path differs from packet root",
    )
    stage0.require_nvme_artifact_path(output_root)
    stage0.require_nvme_artifact_path(result, suffix=".json")
    require(not output_root.exists(), "stage-zero root already exists and is terminal")
    require(
        not _is_within(authorization_path, output_root)
        and not _is_within(fixture_path, output_root),
        "authorization/fixture must be frozen outside the fresh run root",
    )
    _require_nvme(output_root.parent)
    _reject_usb_path(output_root)
    sysfs = _sysfs_card0_identity(packet["device"])
    return {
        "main_authorization_head": main,
        "frozen_tooling_commit": tools_commit,
        "authorization_commit_shape": {
            "parent": tools_commit,
            "changed_paths": changed_paths,
            "packet_bytes_sha256": hashlib.sha256(tracked_packet).hexdigest(),
        },
        "vllm": vllm,
        "kernels": kernels,
        "runtime_files": runtime_files,
        "sysfs_card0": sysfs,
    }


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _exclusive_json(path: Path, value: dict[str, Any]) -> None:
    """Create, fsync, and never overwrite a packet/result/checkpoint."""
    stage0.exclusive_json(path, value)
    parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def _create_runtime_directories(output_root: Path) -> None:
    """Create post-ownership cache/tmp roots without following symlinks."""
    require(
        output_root.is_dir() and not output_root.is_symlink(),
        "adapter does not own a regular output root",
    )
    root_fd = os.open(
        output_root,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    try:
        for relative in RUNTIME_RELATIVE_DIRECTORIES:
            directory_fd = os.dup(root_fd)
            try:
                for part in Path(relative).parts:
                    try:
                        os.mkdir(part, 0o700, dir_fd=directory_fd)
                        os.fsync(directory_fd)
                    except FileExistsError:
                        pass
                    next_fd = os.open(
                        part,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=directory_fd,
                    )
                    os.close(directory_fd)
                    directory_fd = next_fd
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        os.fsync(root_fd)
    finally:
        os.close(root_fd)


def _pre_tensor_payload(
    packet: dict[str, Any], fixture: dict[str, Any], observed: dict[str, Any]
) -> dict[str, Any]:
    return {
        "format": "laguna-shared-gate-up-m8-stage0-pre-tensor-checkpoint-v1",
        "status": "identity_validated_no_tensor_work",
        "tensor_work_started": False,
        "authorization_packet": {
            "path": packet["packet_path"],
            "sha256": stage0.packet_digest(packet),
        },
        "fixture_manifest_sha256": fixture["manifest_sha256"],
        "observed_pre_tensor_identity": observed,
        "downstream": {action: False for action in stage0.RESULT_ACTIONS},
    }


def _base_result(
    packet: dict[str, Any],
    fixture: dict[str, Any],
    *,
    started: str,
    pre_tensor_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    observed = {
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
    return {
        "format": stage0.RESULT_FORMAT,
        "status": "stage0_pre_tensor_failure",
        "passed": False,
        "terminal": False,
        "error": None,
        "started_utc": started,
        "completed_utc": started,
        "tensor_work_started": False,
        "execution_phase": "pre_tensor_identity_checkpoint",
        "last_durable_checkpoint": "pre_tensor_identity_checkpoint",
        "authorization_packet": {
            "path": packet["packet_path"],
            "sha256": stage0.packet_digest(packet),
        },
        "fixture_manifest_sha256": fixture["manifest_sha256"],
        "observed_identity": observed,
        "pre_tensor_identity": copy.deepcopy(pre_tensor_identity),
        "runtime_card0_binding": None,
        "constructor_scope_proof": None,
        "dispatch_proof": None,
        "epochs": [],
        "downstream": {action: False for action in stage0.RESULT_ACTIONS},
        "post_stage0_authorization": {action: False for action in stage0.PRE_ACTIONS},
    }


def _tensor_started_payload(result: dict[str, Any]) -> dict[str, Any]:
    """A separate O_EXCL marker makes post-tensor crashes terminal on disk."""
    return {
        "format": "laguna-shared-gate-up-m8-stage0-tensor-work-started-v1",
        "status": "tensor_work_started_terminal_if_interrupted",
        "tensor_work_started": True,
        "authorization_packet": result["authorization_packet"],
        "fixture_manifest_sha256": result["fixture_manifest_sha256"],
        "downstream": result["downstream"],
    }


def _runtime_card0_binding(
    torch: Any,
    packet: dict[str, Any],
    observed: dict[str, Any],
) -> dict[str, Any]:
    """Bind the post-marker XPU runtime to the frozen physical card zero."""
    require(
        os.environ.get("ONEAPI_DEVICE_SELECTOR") == "level_zero:0"
        and os.environ.get("ZE_AFFINITY_MASK") == "0",
        "runtime selectors do not bind physical card zero",
    )
    count = torch.xpu.device_count()
    require(count == 1, f"affinity must expose exactly one XPU, found {count}")
    current = torch.xpu.current_device()
    require(current == 0, f"current logical XPU is {current}, not zero")
    name = torch.xpu.get_device_name(0)
    require(
        name == stage0.EXPECTED_DEVICE_NAME,
        f"visible XPU is not the expected B70: {name!r}",
    )
    probe = torch.empty((), device="xpu")
    tensor_device = str(probe.device)
    require(tensor_device == "xpu:0", f"probe tensor landed on {tensor_device}")
    packet_device = copy.deepcopy(packet["device"])
    require(packet_device == stage0.EXPECTED_CARD0, "packet card-zero identity drift")
    sysfs = copy.deepcopy(observed["sysfs_card0"])
    require(
        sysfs.get("drm_device") == packet_device["drm_device"]
        and sysfs.get("pci_bdf_address") == packet_device["pci_bdf_address"]
        and sysfs.get("vendor") == "0x8086"
        and sysfs.get("device") == "0xe223",
        "runtime selectors are not bound to the frozen sysfs card",
    )
    observed_runtime = {
        "python_version": sys.version,
        "python_executable": sys.executable,
        "torch_version": str(torch.__version__),
        "files": {
            name: _runtime_file_identity(record)
            for name, record in packet["runtime"]["observed_identity"]["files"].items()
        },
    }
    require(
        Path(torch.__file__).resolve(strict=True)
        == Path(observed_runtime["files"]["torch_init"]["resolved_path"])
        and Path(torch.version.__file__).resolve(strict=True)
        == Path(observed_runtime["files"]["torch_version"]["resolved_path"])
        and observed_runtime == packet["runtime"]["observed_identity"],
        "imported Python/Torch/Level-Zero identity drift",
    )
    return {
        "oneapi_device_selector": "level_zero:0",
        "ze_affinity_mask": "0",
        "logical_device_id": 0,
        "current_device": current,
        "visible_device_count": count,
        "name": name,
        "tensor_device": tensor_device,
        "packet_device": packet_device,
        "sysfs_card0": sysfs,
        "runtime_identity": observed_runtime,
    }


def _record_tensor(tensor: Any, label: str, shape: tuple[int, ...]) -> dict[str, Any]:
    import torch

    require(
        tuple(tensor.shape) == shape and tensor.dtype == torch.bfloat16,
        f"tensor metadata drift: {label}",
    )
    value = tensor.detach().contiguous()
    raw = value.view(torch.uint16).cpu().numpy().tobytes()
    record = stage0.tensor_record(label, shape, raw, include_raw=True)
    require(record["finite"], f"nonfinite tensor: {label}")
    return record


def _input_hashes(tensors: dict[str, Any]) -> dict[str, str]:
    records = {
        name: _record_tensor(value, name, tuple(value.shape))["canonical_sha256"]
        for name, value in tensors.items()
    }
    return records


def _cpu_bf16(raw: bytes, shape: tuple[int, ...], torch: Any) -> Any:
    words = torch.frombuffer(bytearray(raw), dtype=torch.uint16).clone()
    return words.view(torch.bfloat16).reshape(shape).contiguous()


def _load_epoch(epoch: dict[str, Any], torch: Any) -> dict[str, Any]:
    tensors: dict[str, Any] = {}
    for record in epoch["tensors"]:
        label = record["label"]
        expected = stage0.fixture_bytes(
            epoch["epoch"], record["field_id"], tuple(record["shape"])
        )
        require(
            stage0.tensor_record(label, tuple(record["shape"]), expected)
            == {
                key: record[key]
                for key in (
                    "label",
                    "shape",
                    "dtype",
                    "byte_order",
                    "raw_bf16_le_sha256",
                    "canonical_sha256",
                    "finite",
                )
            },
            "fixture regeneration hash drift",
        )
        tensors[label] = _cpu_bf16(expected, tuple(record["shape"]), torch)
    return tensors


def _raw_equal(left: Any, right: Any, torch: Any) -> bool:
    return bool(
        torch.equal(left, right)
        and _record_tensor(left, "temporary.left", tuple(left.shape))[
            "raw_bf16_le_sha256"
        ]
        == _record_tensor(right, "temporary.right", tuple(right.shape))[
            "raw_bf16_le_sha256"
        ]
    )


def _verifier_forward_context(forward_context: Any, enabled: bool) -> Any:
    context = forward_context.ForwardContext(
        no_compile_layers={},
        attn_metadata={},
        slot_mapping={},
        additional_kwargs={"xpu_exact_spec_verifier": enabled},
    )
    return forward_context.override_forward_context(context)


def _forward(layer: Any, rows: Any) -> Any:
    output, bias = layer(rows)
    require(bias is None, "shared projection unexpectedly returned bias")
    return output


def _literal_bmm(rows: Any, weight: Any, torch: Any) -> Any:
    """The frozen independent-M=1 control, with no candidate marker path."""
    return torch.bmm(
        rows.unsqueeze(1),
        weight.t().unsqueeze(0).expand(rows.shape[0], -1, -1),
    ).squeeze(1)


def _pair_forward(gate: Any, up: Any, rows: Any) -> tuple[Any, Any]:
    """Keep the two checkpoint-selected projections separate and ordered."""
    return _forward(gate, rows), _forward(up, rows)


def _mutate_attr(target: Any, attribute: str, value: Any) -> Callable[[], None]:
    """Set one temporary validation attribute and return its exact restore."""
    old = getattr(target, attribute)
    setattr(target, attribute, value)
    return lambda: setattr(target, attribute, old)


def _dispatch_case(
    name: str,
    layer: Any,
    projection: str,
    rows: Any,
    *,
    output_width: int,
    verifier: bool,
    expect_mm: int,
    expect_bmm: int,
    expect_raise: bool,
    expected_exception: dict[str, str] | None,
    torch: Any,
    forward_context: Any,
) -> dict[str, Any]:
    """Run one named projection probe and emit the frozen call descriptor."""
    old_mm, old_bmm = torch.mm, torch.bmm
    old_apply = layer.quant_method.apply
    counts = {"mm": 0, "bmm": 0, "fallback": 0}
    caught_exception: dict[str, str] | None = None
    actual = None
    try:
        def counted_mm(left: Any, right: Any, *args: Any, **kwargs: Any) -> Any:
            require(
                right.data_ptr() == layer.weight.data_ptr(),
                "native MM escaped the named checkpoint projection",
            )
            counts["mm"] += 1
            return old_mm(left, right, *args, **kwargs)

        def counted_bmm(*args: Any, **kwargs: Any) -> Any:
            counts["bmm"] += 1
            return old_bmm(*args, **kwargs)

        def counted_fallback(*args: Any, **kwargs: Any) -> Any:
            counts["fallback"] += 1
            raise RuntimeError("named projection reached quant-method fallback")

        torch.mm, torch.bmm = counted_mm, counted_bmm
        layer.quant_method.apply = counted_fallback
        with _verifier_forward_context(forward_context, verifier):
            try:
                actual = _forward(layer, rows)
            except RuntimeError as error:
                caught_exception = {"type": type(error).__name__, "message": str(error)}
    finally:
        torch.mm, torch.bmm = old_mm, old_bmm
        layer.quant_method.apply = old_apply
    raised = caught_exception is not None
    require(raised is expect_raise, f"dispatch rejection drift: {name}")
    require(counts == {"mm": expect_mm, "bmm": expect_bmm, "fallback": 0}, f"dispatch count drift: {name}")
    expected = _literal_bmm(rows, layer.weight, torch) if actual is not None else None
    call = {
        "projection": projection,
        "marker_enabled": getattr(layer, "xpu_laguna_m8_shared_gate_up_mm", None)
        is True,
        "input_width": rows.shape[1],
        "mm_calls": counts["mm"],
        "bmm_calls": counts["bmm"],
        "fallback_calls": counts["fallback"],
        "actual_output": None
        if actual is None
        else _record_tensor(
            actual,
            f"stage0.dispatch.{name}.{projection}.actual",
            (rows.shape[0], output_width),
        ),
        "expected_output": None
        if expected is None
        else _record_tensor(
            expected,
            f"stage0.dispatch.{name}.{projection}.expected",
            (rows.shape[0], output_width),
        ),
    }
    if raised:
        require(
            expected_exception is not None and caught_exception == expected_exception,
            f"dispatch rejection evidence drift: {name}",
        )
        return {
            "rows": rows.shape[0], "verifier_rows": verifier,
            "raised": True, "exception": copy.deepcopy(expected_exception), "calls": [call],
        }
    require(
        _raw_equal(actual, expected, torch),
        f"dispatch raw output mismatch: {name}",
    )
    return {
        "rows": rows.shape[0], "verifier_rows": verifier,
        "raised": False, "exception": None, "calls": [call],
    }


def _marked_pair_dispatch_case(
    mlp: Any, rows: Any, *, torch: Any, forward_context: Any
) -> dict[str, Any]:
    """Run the real LagunaMLP forward and capture its marked pair in order."""
    gate, up = mlp.gate_proj, mlp.up_proj
    old_mm, old_bmm = torch.mm, torch.bmm
    old_gate_forward, old_up_forward = gate.forward, up.forward
    old_gate_apply, old_up_apply = gate.quant_method.apply, up.quant_method.apply
    counts = {role: {"mm": 0, "bmm": 0, "fallback": 0} for role in ("gate_proj", "up_proj")}
    actual: dict[str, Any] = {}
    order: list[str] = []
    active: str | None = None
    pointers = {gate.weight.data_ptr(): "gate_proj", up.weight.data_ptr(): "up_proj"}
    try:
        def counted_mm(left: Any, right: Any, *args: Any, **kwargs: Any) -> Any:
            role = pointers.get(right.data_ptr())
            if role is None:
                return old_mm(left, right, *args, **kwargs)
            require(role == active, "marked pair native-MM order drift")
            counts[role]["mm"] += 1
            return old_mm(left, right, *args, **kwargs)

        def counted_bmm(*args: Any, **kwargs: Any) -> Any:
            if active is not None:
                counts[active]["bmm"] += 1
            return old_bmm(*args, **kwargs)

        def wrapped(role: str, original: Callable[..., Any]) -> Callable[..., Any]:
            def forward(*args: Any, **kwargs: Any) -> Any:
                nonlocal active
                require(active is None, "LagunaMLP projection nesting drift")
                active = role
                order.append(role)
                try:
                    value = original(*args, **kwargs)
                    actual[role] = value[0]
                    return value
                finally:
                    active = None

            return forward

        def fallback(*_args: Any, **_kwargs: Any) -> Any:
            require(active is not None, "pair fallback escaped the projection")
            counts[active]["fallback"] += 1
            raise RuntimeError("marked pair reached quant-method fallback")

        torch.mm, torch.bmm = counted_mm, counted_bmm
        gate.quant_method.apply, up.quant_method.apply = fallback, fallback
        gate.forward, up.forward = wrapped("gate_proj", old_gate_forward), wrapped("up_proj", old_up_forward)
        with _verifier_forward_context(forward_context, True):
            mlp(rows)
    finally:
        torch.mm, torch.bmm = old_mm, old_bmm
        gate.forward, up.forward = old_gate_forward, old_up_forward
        gate.quant_method.apply, up.quant_method.apply = old_gate_apply, old_up_apply
    require(order == ["gate_proj", "up_proj"], "actual LagunaMLP forward order drift")
    calls = []
    for projection, layer in (("gate_proj", gate), ("up_proj", up)):
        expected = _literal_bmm(rows, layer.weight, torch)
        require(_raw_equal(actual[projection], expected, torch), f"marked pair raw mismatch: {projection}")
        require(counts[projection] == {"mm": 1, "bmm": 0, "fallback": 0}, f"marked pair primitive drift: {projection}")
        calls.append(
            {
                "projection": projection,
                "marker_enabled": True,
                "input_width": rows.shape[1],
                "mm_calls": 1,
                "bmm_calls": 0,
                "fallback_calls": 0,
                "actual_output": _record_tensor(actual[projection], f"stage0.dispatch.marked_pair_m8.{projection}.actual", (stage0.ROWS, stage0.PROJECTION)),
                "expected_output": _record_tensor(expected, f"stage0.dispatch.marked_pair_m8.{projection}.expected", (stage0.ROWS, stage0.PROJECTION)),
            }
        )
    return {"rows": stage0.ROWS, "verifier_rows": True, "raised": False, "exception": None, "calls": calls}


def _dispatch_proof_frozen(
    mlp: Any,
    dense_mlp: Any,
    draft_mlp: Any,
    incumbent_layers: dict[str, Any],
    fixture: dict[str, Any],
    torch: Any,
    forward_context: Any,
) -> dict[str, Any]:
    """Emit precisely the analyzer's named, real-path dispatch inventory."""
    from vllm import envs

    require(
        not envs._is_envs_cache_enabled(),
        "vLLM environment cache is enabled; dynamic rejection probes are stale",
    )
    first = _load_epoch(fixture["epochs"][0], torch)
    rows = first["hidden_input"].to("xpu")
    with torch.no_grad():
        mlp.gate_proj.weight.copy_(first["gate_weight"].to("xpu"))
        mlp.up_proj.weight.copy_(first["up_weight"].to("xpu"))
        mlp.down_proj.weight.copy_(first["down_weight"].to("xpu"))
        for layer in incumbent_layers.values():
            layer.weight.copy_(first["gate_weight"].to("xpu"))
    gate, up, down = mlp.gate_proj, mlp.up_proj, mlp.down_proj
    require(
        all(
            getattr(layer, "xpu_laguna_m8_shared_gate_up_mm", None) is True
            for layer in (gate, up)
        ),
        "actual constructor did not mark the gate/up pair",
    )
    require(
        all(
            not hasattr(layer, "xpu_laguna_m8_shared_gate_up_mm")
            for layer in (
                down,
                dense_mlp.gate_proj,
                draft_mlp.gate_proj,
                *incumbent_layers.values(),
            )
        ),
        "pair marker escaped its checkpoint-selected scope",
    )
    proof: dict[str, Any] = {
        "scope": "actual_checkpoint_selected_LagunaMLP.forward",
        "marker_scope": {
            "marked": [gate.prefix, up.prefix],
            "unmarked": [
                "model.layers.1.mlp.shared_expert.down_proj",
                "dense_mlp",
                "draft",
                "routed_mlp",
            ],
        },
        "marked_pair_m8": _marked_pair_dispatch_case(
            mlp, rows, torch=torch, forward_context=forward_context
        ),
    }

    def incumbent(
        name: str,
        layer: Any,
        projection: str,
        input_rows: Any,
        *,
        verifier: bool,
        output_width: int = stage0.PROJECTION,
    ) -> None:
        proof[name] = _dispatch_case(
            name,
            layer,
            projection,
            input_rows,
            output_width=output_width,
            verifier=verifier,
            expect_mm=0,
            expect_bmm=1,
            expect_raise=False,
            expected_exception=None,
            torch=torch,
            forward_context=forward_context,
        )

    def bindings_unmarked(layer: Any) -> Callable[[], None]:
        marker = layer.xpu_laguna_m8_shared_gate_up_mm
        scope = layer._xpu_laguna_m8_shared_gate_up_scope
        layer.xpu_laguna_m8_shared_gate_up_mm = False
        layer._xpu_laguna_m8_shared_gate_up_scope = None

        def restore() -> None:
            layer.xpu_laguna_m8_shared_gate_up_mm = marker
            layer._xpu_laguna_m8_shared_gate_up_scope = scope

        return restore

    for name, layer, projection in (
        ("unmarked_gate_m8", gate, "gate_proj"),
        ("unmarked_up_m8", up, "up_proj"),
    ):
        restore = bindings_unmarked(layer)
        try:
            incumbent(name, layer, projection, rows, verifier=True)
        finally:
            restore()
    incumbent("prefill_marked_gate", gate, "gate_proj", rows, verifier=False)
    incumbent("prefill_marked_up", up, "up_proj", rows, verifier=False)
    for name in ("dense", "draft", "routed"):
        incumbent(f"{name}_m8", incumbent_layers[name], name, rows, verifier=True)
    incumbent(
        "shared_down_m8",
        down,
        "shared_down",
        rows[:, : stage0.PROJECTION].contiguous(),
        verifier=True,
        output_width=stage0.HIDDEN,
    )
    for projection, layer in (("gate_proj", gate), ("up_proj", up)):
        for count in range(1, stage0.ROWS):
            incumbent(
                f"{projection}_m{count}",
                layer,
                projection,
                rows[:count],
                verifier=True,
            )

    def reject(
        name: str,
        layer: Any,
        projection: str,
        mutate: Callable[[], Callable[[], None]],
        *,
        case_rows: Any = rows,
    ) -> None:
        restore = mutate()
        try:
            proof[name] = _dispatch_case(
                name,
                layer,
                projection,
                case_rows,
                output_width=stage0.PROJECTION,
                verifier=True,
                expect_mm=0,
                expect_bmm=0,
                expect_raise=True,
                expected_exception=stage0.DISPATCH_REJECTION_EXCEPTIONS[name],
                torch=torch,
                forward_context=forward_context,
            )
        finally:
            restore()

    def set_environment(name: str, value: str | None) -> Callable[[], None]:
        old = os.environ.get(name)
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
        return lambda: os.environ.__setitem__(name, old) if old is not None else os.environ.pop(name, None)

    def weight_layout(layer: Any) -> Callable[[], None]:
        old = layer.weight
        bad = old.t().contiguous().t()
        require(not bad.is_contiguous(), "failed to make a noncontiguous weight")
        layer.weight = torch.nn.Parameter(bad, requires_grad=False)
        return lambda: setattr(layer, "weight", old)

    def role_scope(layer: Any, role: str) -> Callable[[], None]:
        old = layer._xpu_laguna_m8_shared_gate_up_scope
        layer._xpu_laguna_m8_shared_gate_up_scope = (old[0], old[1], role)
        return lambda: setattr(layer, "_xpu_laguna_m8_shared_gate_up_scope", old)

    noncontiguous_rows = rows.t().contiguous().t()
    require(not noncontiguous_rows.is_contiguous(), "failed to make noncontiguous rows")
    reject("bad_gate_rows_layout", gate, "gate_proj", lambda: lambda: None, case_rows=noncontiguous_rows)
    reject("bad_up_rows_layout", up, "up_proj", lambda: lambda: None, case_rows=noncontiguous_rows)
    reject("bad_gate_weight_layout", gate, "gate_proj", lambda: weight_layout(gate))
    reject("bad_up_weight_layout", up, "up_proj", lambda: weight_layout(up))
    reject("missing_gate_marker", gate, "gate_proj", lambda: _mutate_attr(gate, "xpu_laguna_m8_shared_gate_up_mm", False))
    reject("missing_up_marker", up, "up_proj", lambda: _mutate_attr(up, "xpu_laguna_m8_shared_gate_up_mm", False))
    reject("missing_gate_scope", gate, "gate_proj", lambda: _mutate_attr(gate, "_xpu_laguna_m8_shared_gate_up_scope", None))
    reject("missing_up_scope", up, "up_proj", lambda: _mutate_attr(up, "_xpu_laguna_m8_shared_gate_up_scope", None))
    reject("mismatched_gate_role_scope", gate, "gate_proj", lambda: role_scope(gate, "up_proj"))
    reject("mismatched_up_role_scope", up, "up_proj", lambda: role_scope(up, "gate_proj"))
    reject("up_exact_rows_corruption", gate, "gate_proj", lambda: _mutate_attr(up, "xpu_exact_spec_rows", False))
    reject("up_weight_layout_corruption", gate, "gate_proj", lambda: weight_layout(up))
    reject("up_bias_corruption", gate, "gate_proj", lambda: _mutate_attr(up, "bias", torch.nn.Parameter(torch.zeros(stage0.PROJECTION, device="xpu"))))
    for name, environment, value in (
        ("selector_pair_nonliteral", "VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM", "2"),
        ("selector_gate_overlap", "VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM", "1"),
        ("selector_down_overlap", "VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM", "1"),
        ("selector_gate_unset", "VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM", None),
        ("selector_down_unset", "VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM", None),
        ("record_stack_exact_attn_drift", "VLLM_XPU_EXACT_SPEC_ATTN", "0"),
        ("record_stack_batched_moe_drift", "VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE", "0"),
        ("record_stack_shared_elementwise_drift", "VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE", "0"),
        ("record_stack_qknorm_rope_drift", "VLLM_XPU_LAGUNA_M8_QKNORM_ROPE", "0"),
        ("record_stack_bf16_attn_mm_drift", "VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM", "1"),
        ("record_stack_bf16_router_topk_drift", "VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK", "1"),
        ("record_stack_fused_transaction_drift", "VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION", "1"),
        ("record_stack_remote_zero_drift", "VLLM_XPU_LAGUNA_M8_REMOTE_ZERO", "1"),
        ("record_stack_shared_expert_stream_drift", "VLLM_XPU_LAGUNA_M8_SHARED_EXPERT_STREAM", "1"),
        ("record_stack_graph_aot_drift", "XPU_GRAPH", "1"),
        ("record_stack_route_interleave_drift", "VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE", "0"),
        ("record_stack_w1_n64_drift", "VLLM_XPU_LAGUNA_M8_W1_N_TILE", "128"),
    ):
        reject(name, gate, "gate_proj", lambda environment=environment, value=value: set_environment(environment, value))
    return proof


def _dispatch_proof(
    mlp: Any,
    dense_mlp: Any,
    draft_mlp: Any,
    incumbent_layers: dict[str, Any],
    fixture: dict[str, Any],
    torch: Any,
    forward_context: Any,
) -> dict[str, Any]:
    """Exercise the frozen pair-v1 dispatch proof."""
    return _dispatch_proof_frozen(
        mlp,
        dense_mlp,
        draft_mlp,
        incumbent_layers,
        fixture,
        torch,
        forward_context,
    )

def _construct_real_mlp(
    torch: Any,
) -> tuple[Any, Any, Any, dict[str, Any], Any, Any, dict[str, Any]]:
    """Build the real LagunaMLP with the private committed constructor token."""
    from vllm.model_executor import parameter as parameter_module
    from vllm.model_executor.layers.quantization.compressed_tensors.compressed_tensors import (
        CompressedTensorsConfig,
    )
    from vllm.model_executor.models import laguna
    from vllm.model_executor.layers import linear
    from vllm import forward_context

    config = json.loads(MODEL_CONFIG.read_text())
    quant = config.get("quantization_config")
    require(isinstance(quant, dict), "checkpoint has no compressed-tensors metadata")
    ignores = quant.get("ignore")
    require(
        isinstance(ignores, list)
        and r"re:.*\.mlp\.shared_expert\.gate_proj$" in ignores,
        "checkpoint does not select unquantized shared gate",
    )
    require(
        r"re:.*\.mlp\.shared_expert\.up_proj$" in ignores,
        "checkpoint does not select unquantized shared up",
    )
    transforms = quant.get("transform_config", {}).get("config_groups", {})
    locations = [
        application.get("location")
        for group in transforms.values()
        if isinstance(group, dict)
        for application in group.get("apply", [])
        if isinstance(application, dict)
    ]
    require(
        locations and set(locations) <= {"weight_input", "weight_output"},
        "checkpoint asks for online transform",
    )
    quant_config = CompressedTensorsConfig.from_config(copy.deepcopy(quant))
    old_rank = parameter_module.get_tensor_model_parallel_rank
    old_size = parameter_module.get_tensor_model_parallel_world_size
    old_linear_rank = linear.get_tensor_model_parallel_rank
    old_linear_size = linear.get_tensor_model_parallel_world_size
    old_dtype = torch.get_default_dtype()
    try:
        parameter_module.get_tensor_model_parallel_rank = lambda: 0
        parameter_module.get_tensor_model_parallel_world_size = lambda: 4
        linear.get_tensor_model_parallel_rank = lambda: 0
        linear.get_tensor_model_parallel_world_size = lambda: 4
        torch.set_default_dtype(torch.bfloat16)
        mlp = laguna.LagunaMLP(
            hidden_size=stage0.HIDDEN,
            intermediate_size=1024,
            hidden_act="silu",
            quant_config=quant_config,
            reduce_results=False,
            exact_spec_target=True,
            use_m8_shared_elementwise=True,
            use_m8_shared_down_mm=False,
            use_m8_shared_gate_mm=False,
            use_m8_shared_gate_up_mm=True,
            _m8_shared_gate_up_scope=(
                laguna._LAGUNA_M8_SHARED_GATE_UP_CONSTRUCTOR_SCOPE
            ),
            prefix="model.layers.1.mlp.shared_expert",
        ).to("xpu")
        dense_mlp = laguna.LagunaMLP(
            hidden_size=stage0.HIDDEN,
            intermediate_size=1024,
            hidden_act="silu",
            quant_config=None,
            reduce_results=False,
            exact_spec_target=True,
            prefix="model.layers.1.mlp",
        ).to("xpu")
        draft_mlp = laguna.LagunaMLP(
            hidden_size=stage0.HIDDEN,
            intermediate_size=1024,
            hidden_act="silu",
            quant_config=None,
            reduce_results=False,
            exact_spec_target=False,
            prefix="draft.layers.1.mlp.shared_expert",
        ).to("xpu")
        incumbent_layers = {}
        routed_mlp = laguna.LagunaMLP(
            hidden_size=stage0.HIDDEN,
            intermediate_size=1024,
            hidden_act="silu",
            quant_config=None,
            reduce_results=False,
            exact_spec_target=True,
            prefix="model.layers.1.mlp.experts.0",
        ).to("xpu")
        # These are actual unquantized LagunaMLP representatives for the
        # named incumbent scopes.  The checkpoint target remains only `mlp`.
        for name, layer in (
            ("dense", dense_mlp.gate_proj),
            ("draft", draft_mlp.gate_proj),
            ("routed", routed_mlp.gate_proj),
        ):
            layer.xpu_exact_spec_rows = True
            incumbent_layers[name] = layer
    finally:
        torch.set_default_dtype(old_dtype)
        parameter_module.get_tensor_model_parallel_rank = old_rank
        parameter_module.get_tensor_model_parallel_world_size = old_size
        linear.get_tensor_model_parallel_rank = old_linear_rank
        linear.get_tensor_model_parallel_world_size = old_linear_size
    require(
        all(
            isinstance(layer.quant_method, linear.UnquantizedLinearMethod)
            for layer in (mlp.gate_proj, mlp.up_proj, mlp.down_proj)
        ),
        "checkpoint did not select unquantized shared projections",
    )
    require(
        all(
            projection.gather_output is False and projection.bias is None
            for projection in (mlp.gate_proj, mlp.up_proj)
        ),
        "actual shared gate/up has gather/bias drift",
    )
    require(
        all(
            tuple(projection.weight.shape) == (stage0.PROJECTION, stage0.HIDDEN)
            and projection.weight.dtype == torch.bfloat16
            for projection in (mlp.gate_proj, mlp.up_proj)
        ),
        "actual local gate/up weight geometry or dtype drift",
    )
    require(
        linear._xpu_laguna_m8_shared_gate_up_pair_scope_valid(
            mlp.gate_proj,
            mlp.gate_proj.prefix,
            "gate_proj",
            mlp.gate_proj._xpu_laguna_m8_shared_gate_up_scope,
        )
        and linear._xpu_laguna_m8_shared_gate_up_pair_scope_valid(
            mlp.up_proj,
            mlp.up_proj.prefix,
            "up_proj",
            mlp.up_proj._xpu_laguna_m8_shared_gate_up_scope,
        ),
        "actual constructor did not bind the canonical gate/up pair",
    )
    require(
        all(
            not hasattr(projection, "xpu_laguna_m8_shared_gate_up_mm")
            for projection in (
                dense_mlp.gate_proj,
                dense_mlp.up_proj,
                draft_mlp.gate_proj,
                draft_mlp.up_proj,
                mlp.down_proj,
            )
        ),
        "dense, draft, or shared down received the gate/up marker",
    )
    runtime_transforms = [
        type(module).__name__
        for module in mlp.modules()
        if type(module).__name__ == "HadamardTransform"
    ]
    require(not runtime_transforms, "checkpoint selected an online Hadamard transform")
    scope_proof = {
        "constructor": "LagunaMLP_with_committed_LagunaMoE_scope_token",
        "marked_prefixes": [mlp.gate_proj.prefix, mlp.up_proj.prefix],
        "marked_roles": ["gate_proj", "up_proj"],
        "shared_pair_scope": True,
        "forward_order": ["gate_proj", "up_proj", "down_proj"],
        "unmarked": {
            "shared_down": not hasattr(mlp.down_proj, "xpu_laguna_m8_shared_gate_up_mm"),
            "dense": not hasattr(dense_mlp.gate_proj, "xpu_laguna_m8_shared_gate_up_mm"),
            "draft": not hasattr(draft_mlp.gate_proj, "xpu_laguna_m8_shared_gate_up_mm"),
            "routed": True,
        },
        "quant_method": type(mlp.gate_proj.quant_method).__name__,
        "shared_elementwise_enabled": mlp.use_m8_shared_elementwise is True,
        "verifier_gating": (
            "vllm.forward_context.additional_kwargs.xpu_exact_spec_verifier"
        ),
        "runtime_hadamard_modules": runtime_transforms,
    }
    return (
        mlp,
        dense_mlp,
        draft_mlp,
        incumbent_layers,
        laguna,
        forward_context,
        scope_proof,
    )


def _exact_scale_add(shared: Any, routed: Any, torch: Any) -> Any:
    """The frozen elementwise boundary: BF16 routed*2.5 then shared add."""
    require(
        hasattr(torch.ops, "_C") and hasattr(torch.ops._C, "laguna_m8_scale_add"),
        "exact shared scale/add extension is unavailable",
    )
    output = torch.empty_like(shared)
    torch.ops._C.laguna_m8_scale_add(output, shared, routed)
    return output


def _epoch_result(
    mlp: Any,
    laguna: Any,
    fixture_epoch: dict[str, Any],
    torch: Any,
    forward_context: Any,
) -> dict[str, Any]:
    host = _load_epoch(fixture_epoch, torch)
    fixture_before = _input_hashes(host)
    device = {name: value.to("xpu") for name, value in host.items()}
    after_host = _input_hashes(host)
    post_transfer = _input_hashes(device)
    require(
        fixture_before == after_host == post_transfer,
        "fixture input mutated during host/device transfer",
    )
    gate, up, down = mlp.gate_proj, mlp.up_proj, mlp.down_proj
    with torch.no_grad():
        gate.weight.copy_(device["gate_weight"])
        up.weight.copy_(device["up_weight"])
        down.weight.copy_(device["down_weight"])
    layer_weights_after_copy = {
        "gate_weight": _record_tensor(
            gate.weight,
            "gate_weight",
            (stage0.PROJECTION, stage0.HIDDEN),
        )["canonical_sha256"],
        "up_weight": _record_tensor(
            up.weight,
            "up_weight",
            (stage0.PROJECTION, stage0.HIDDEN),
        )["canonical_sha256"],
        "down_weight": _record_tensor(
            down.weight,
            "down_weight",
            (stage0.HIDDEN, stage0.PROJECTION),
        )["canonical_sha256"],
    }
    expected_weight_hashes = {
        name: _record_tensor(value, name, tuple(value.shape))["canonical_sha256"]
        for name, value in (
            ("gate_weight", device["gate_weight"]),
            ("up_weight", device["up_weight"]),
            ("down_weight", device["down_weight"]),
        )
    }
    require(layer_weights_after_copy == expected_weight_hashes, "weight copy drift")
    old_mm, old_bmm = torch.mm, torch.bmm
    candidate_trace: list[dict[str, Any]] = []
    try:
        with _verifier_forward_context(forward_context, True):
            control = _literal_bmm(device["hidden_input"], gate.weight, torch)
            up_control = _literal_bmm(device["hidden_input"], up.weight, torch)
            roles = {gate.weight.data_ptr(): "gate_proj", up.weight.data_ptr(): "up_proj"}

            def counted_mm(left: Any, right: Any, *args: Any, **kwargs: Any) -> Any:
                role = roles.get(right.data_ptr())
                require(role is not None, "candidate MM escaped the gate/up pair")
                candidate_trace.append({"role": role, "primitive": "mm"})
                return old_mm(left, right, *args, **kwargs)

            def forbidden_bmm(*_args: Any, **_kwargs: Any) -> Any:
                raise RuntimeError("candidate pair silently used incumbent BMM")

            torch.mm, torch.bmm = counted_mm, forbidden_bmm
            candidate, up_candidate = _pair_forward(gate, up, device["hidden_input"])
            candidate_repeat, up_candidate_repeat = _pair_forward(
                gate, up, device["hidden_input"]
            )
            require(
                candidate_trace == [
                    {"role": "gate_proj", "primitive": "mm"},
                    {"role": "up_proj", "primitive": "mm"},
                    {"role": "gate_proj", "primitive": "mm"},
                    {"role": "up_proj", "primitive": "mm"},
                ],
                "candidate pair dispatch/count order drift",
            )
            torch.mm, torch.bmm = old_mm, old_bmm
            silu_gate_control = torch.nn.functional.silu(control)
            silu_gate_candidate = torch.nn.functional.silu(candidate)
            silu_product_control = laguna._laguna_m8_shared_silu_mul(
                control, up_control, enabled=True
            )
            silu_product_candidate = laguna._laguna_m8_shared_silu_mul(
                candidate, up_candidate, enabled=True
            )
            down_control = _forward(down, silu_product_control)
            down_candidate = _forward(down, silu_product_candidate)
            add_control = _exact_scale_add(down_control, device["routed_input"], torch)
            add_candidate = _exact_scale_add(
                down_candidate, device["routed_input"], torch
            )
            reduction_control = add_control.clone()
            reduction_candidate = add_candidate.clone()
            for name in ("reduction_peer_0", "reduction_peer_1", "reduction_peer_2"):
                reduction_control.add_(device[name])
                reduction_candidate.add_(device[name])
    finally:
        torch.mm, torch.bmm = old_mm, old_bmm
    after_forward = _input_hashes(device)
    layer_weights_after_forward = {
        "gate_weight": _record_tensor(
            gate.weight,
            "gate_weight",
            (stage0.PROJECTION, stage0.HIDDEN),
        )["canonical_sha256"],
        "up_weight": _record_tensor(
            up.weight,
            "up_weight",
            (stage0.PROJECTION, stage0.HIDDEN),
        )["canonical_sha256"],
        "down_weight": _record_tensor(
            down.weight,
            "down_weight",
            (stage0.HIDDEN, stage0.PROJECTION),
        )["canonical_sha256"],
    }
    require(
        after_forward == fixture_before
        and layer_weights_after_forward == expected_weight_hashes,
        "input or shared-projection weight mutated during epoch",
    )
    outputs = {
        "gate_control": _record_tensor(control, "stage0.gate.control", (8, 256)),
        "gate_candidate": _record_tensor(candidate, "stage0.gate.candidate", (8, 256)),
        "gate_candidate_repeat": _record_tensor(
            candidate_repeat, "stage0.gate.candidate_repeat", (8, 256)
        ),
        "up_control": _record_tensor(up_control, "stage0.up.control", (8, 256)),
        "up_candidate": _record_tensor(up_candidate, "stage0.up.candidate", (8, 256)),
        "up_candidate_repeat": _record_tensor(
            up_candidate_repeat, "stage0.up.candidate_repeat", (8, 256)
        ),
        "gate_silu_control": _record_tensor(
            silu_gate_control, "stage0.gate.silu.control", (8, 256)
        ),
        "gate_silu_candidate": _record_tensor(
            silu_gate_candidate, "stage0.gate.silu.candidate", (8, 256)
        ),
        "silu_product_control": _record_tensor(
            silu_product_control, "stage0.bf16_multiply.control", (8, 256)
        ),
        "silu_product_candidate": _record_tensor(
            silu_product_candidate, "stage0.bf16_multiply.candidate", (8, 256)
        ),
        "down_control": _record_tensor(down_control, "stage0.down.control", (8, 3072)),
        "down_candidate": _record_tensor(
            down_candidate, "stage0.down.candidate", (8, 3072)
        ),
        "shared_routed_add_control": _record_tensor(
            add_control, "stage0.shared_routed_add.control", (8, 3072)
        ),
        "shared_routed_add_candidate": _record_tensor(
            add_candidate, "stage0.shared_routed_add.candidate", (8, 3072)
        ),
        "reduction_control": _record_tensor(
            reduction_control, "stage0.reduction.control", (8, 3072)
        ),
        "reduction_candidate": _record_tensor(
            reduction_candidate, "stage0.reduction.candidate", (8, 3072)
        ),
    }
    # The analyzer recomputes equality from preserved raw uint16 bytes.
    pairs = {
        "gate": (control, candidate),
        "gate_repeat": (candidate, candidate_repeat),
        "up": (up_control, up_candidate),
        "up_repeat": (up_candidate, up_candidate_repeat),
        "gate_silu": (silu_gate_control, silu_gate_candidate),
        "bf16_multiply": (silu_product_control, silu_product_candidate),
        "down": (down_control, down_candidate),
        "shared_routed_add": (add_control, add_candidate),
        "reduction": (reduction_control, reduction_candidate),
    }
    comparisons = {
        name: {
            "raw_uint16_equal": _raw_equal(left, right, torch),
            "torch_equal": bool(torch.equal(left, right)),
        }
        for name, (left, right) in pairs.items()
    }
    return {
        "epoch": fixture_epoch["epoch"],
        "fixture_epoch_sha256": fixture_epoch["epoch_sha256"],
        "input_copies": {
            "fixture_before": fixture_before,
            "after_host_copy": after_host,
            "post_transfer": post_transfer,
            "layer_weights_after_copy": layer_weights_after_copy,
            "after_forward": after_forward,
            "layer_weights_after_forward": layer_weights_after_forward,
        },
        "outputs": outputs,
        "comparisons": comparisons,
    }


def _deny_followup_actions() -> dict[str, bool]:
    return {action: False for action in stage0.PRE_ACTIONS}


def _mark_runtime_infrastructure_failure(
    result: dict[str, Any], error: BaseException
) -> dict[str, Any]:
    result.update(
        {
            "status": "stage0_runtime_infrastructure_failed_stop",
            "passed": False,
            "terminal": True,
            "error": {
                "class": "runtime_infrastructure_failure",
                "phase": result["execution_phase"],
                "exception_type": type(error).__name__,
                "message": str(error) or repr(error),
                "proven": False,
                "proof": None,
            },
            "post_stage0_authorization": _deny_followup_actions(),
        }
    )
    return result


def _mark_proven_exactness_failure(
    result: dict[str, Any],
    *,
    epoch: int,
    pairings: list[str],
) -> dict[str, Any]:
    require(pairings, "exactness failure has no mismatched pairing")
    proof = {
        "kind": "raw_exactness_mismatch",
        "epoch": epoch,
        "pairings": sorted(pairings),
    }
    result.update(
        {
            "status": "stage0_exactness_failed_stop",
            "passed": False,
            "terminal": True,
            "error": {
                "class": "proven_exactness_failure",
                "phase": result["execution_phase"],
                "exception_type": None,
                "message": f"bitwise exactness mismatch at epoch {epoch}",
                "proven": True,
                "proof": proof,
            },
            "post_stage0_authorization": _deny_followup_actions(),
        }
    )
    return result


def _run_tensor_work(
    packet: dict[str, Any],
    fixture: dict[str, Any],
    result: dict[str, Any],
    observed: dict[str, Any],
) -> dict[str, Any]:
    _exclusive_json(
        Path(packet["storage"]["output_root"]) / TENSOR_STARTED_CHECKPOINT,
        _tensor_started_payload(result),
    )
    result["tensor_work_started"] = True
    result["execution_phase"] = "tensor_work_started"
    result["last_durable_checkpoint"] = "tensor_work_started"
    _create_runtime_directories(Path(packet["storage"]["output_root"]))
    # This is intentionally the first torch/vLLM import in the entire file.
    import torch

    output_root = Path(packet["storage"]["output_root"])
    runtime_binding = _runtime_card0_binding(torch, packet, observed)
    _exclusive_json(
        output_root / RUNTIME_CARD0_CHECKPOINT,
        {
            "format": "laguna-shared-gate-up-m8-stage0-runtime-card0-binding-v1",
            "tensor_work_started": True,
            "authorization_packet": result["authorization_packet"],
            "runtime_card0_binding": runtime_binding,
            "downstream": result["downstream"],
        },
    )
    result["runtime_card0_binding"] = runtime_binding
    result["execution_phase"] = "runtime_card0_bound"
    result["last_durable_checkpoint"] = "runtime_card0_bound"
    mlp, dense_mlp, draft_mlp, incumbent_layers, laguna, forward_context, constructor_scope = (
        _construct_real_mlp(torch)
    )
    _exclusive_json(
        output_root / "constructor-scope-proof.json",
        {
            "format": "laguna-shared-gate-up-m8-stage0-constructor-scope-v1",
            "tensor_work_started": True,
            "authorization_packet": result["authorization_packet"],
            "proof": constructor_scope,
            "downstream": result["downstream"],
        },
    )
    result["constructor_scope_proof"] = constructor_scope
    result["execution_phase"] = "constructor_scope_durable"
    result["last_durable_checkpoint"] = "constructor_scope_durable"
    dispatch_proof = _dispatch_proof(
        mlp, dense_mlp, draft_mlp, incumbent_layers, fixture, torch, forward_context
    )
    _exclusive_json(
        output_root / "dispatch-proof.json",
        {
            "format": "laguna-shared-gate-up-m8-stage0-dispatch-proof-v1",
            "tensor_work_started": True,
            "authorization_packet": result["authorization_packet"],
            "proof": dispatch_proof,
            "downstream": result["downstream"],
        },
    )
    result["dispatch_proof"] = dispatch_proof
    result["execution_phase"] = "dispatch_proof_durable"
    result["last_durable_checkpoint"] = "dispatch_proof_durable"
    for fixture_epoch in fixture["epochs"]:
        entry = _epoch_result(mlp, laguna, fixture_epoch, torch, forward_context)
        _exclusive_json(
            output_root / "epochs" / f"epoch-{fixture_epoch['epoch']:03d}.json",
            entry,
        )
        result["epochs"].append(entry)
        result["execution_phase"] = f"epoch_{fixture_epoch['epoch']}_durable"
        result["last_durable_checkpoint"] = f"epoch_{fixture_epoch['epoch']}_durable"
        mismatches = [
            name
            for name, comparison in entry["comparisons"].items()
            if not (comparison["raw_uint16_equal"] and comparison["torch_equal"])
        ]
        if mismatches:
            return _mark_proven_exactness_failure(
                result,
                epoch=fixture_epoch["epoch"],
                pairings=mismatches,
            )
    result.update(
        {
            "status": "stage0_exactness_pass",
            "passed": True,
            "terminal": True,
            "error": None,
            "execution_phase": "all_128_epochs_durable",
            "last_durable_checkpoint": "all_128_epochs_durable",
            "post_stage0_authorization": dict(stage0.PASS_NEXT_ACTIONS),
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    argv = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--authorization",
        str(args.authorization),
        "--fixture",
        str(args.fixture),
        "--result",
        str(args.result),
    ]
    packet: dict[str, Any] | None = None
    fixture: dict[str, Any] | None = None
    observed: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    run_root_owned = False
    try:
        packet = json.loads(args.authorization.read_text())
        fixture = json.loads(args.fixture.read_text())
        observed = _strict_packet_runtime_contract(
            packet,
            fixture,
            argv,
            authorization_path=args.authorization,
            fixture_path=args.fixture,
            result_path=args.result,
        )
        output_root = Path(packet["storage"]["output_root"])
        _exclusive_json(
            output_root / PRE_TENSOR_CHECKPOINT,
            _pre_tensor_payload(packet, fixture, observed),
        )
        run_root_owned = True
        result = _base_result(
            packet,
            fixture,
            started=utc_now(),
            pre_tensor_identity=observed,
        )
        result = _run_tensor_work(packet, fixture, result, observed)
    except Exception as error:
        if packet is None or fixture is None:
            raise
        if result is None:
            if not run_root_owned:
                # In particular, never add a file to an already-existing
                # root after a preflight collision or identity failure.
                print(f"stage-zero pre-tensor rejection: {error}", file=sys.stderr)
                return 1
            # Identity/tooling failures never start tensor work and are retryable
            # only under a new frozen root, preserving this explicit result.
            output_root = Path(packet["storage"]["output_root"])
            result = _base_result(
                packet,
                fixture,
                started=utc_now(),
                pre_tensor_identity=observed,
            )
            result["error"] = {
                "class": "identity_or_tooling_failure",
                "phase": result["execution_phase"],
                "exception_type": type(error).__name__,
                "message": str(error),
                "proven": False,
                "proof": None,
            }
        else:
            result = _mark_runtime_infrastructure_failure(result, error)
        result["completed_utc"] = utc_now()
        _exclusive_json(
            Path(packet["storage"]["output_root"]) / "stage0-result.json", result
        )
        return 1
    require(result is not None and packet is not None, "internal result state missing")
    result["completed_utc"] = utc_now()
    _exclusive_json(
        Path(packet["storage"]["output_root"]) / "stage0-result.json", result
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
