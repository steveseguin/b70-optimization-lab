#!/usr/bin/env python3
"""Seal the host-only prerequisites for Laguna M8 gather-sharded Phase A/B.

This program is deliberately unable to prepare a native bundle or start an
accelerator workload.  It only reopens immutable evidence, asks the existing
bundle freezer to perform its *separate* host-only validation in a child
process, and writes one canonical certificate with O_EXCL/O_NOFOLLOW.

The command is intentionally not given defaults.  Its canonical input is the
reviewable declaration of every future Phase-A/Phase-B tool and test that
were committed before a packet can be authored.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable, Mapping

FORMAT = "laguna-m8-gather-sharded-stage0-completion-v1"
INPUT_FORMAT = "laguna-m8-gather-sharded-stage0-completion-input-v1"
ROOT_PREFIX = Path("/mnt/fast-ai")
REPOSITORY_ROOT = Path(__file__).parents[3]
TRACKED_DATA_ROOT = REPOSITORY_ROOT / "data"
SOURCE_PACKET_FORMAT = "laguna-s-2.1-m8-gather-sharded-source-build-ir-v1"
SOURCE_PACKET_STATUS = "source_build_ir_pass_stage0_incomplete"
OPERATIONAL_FORMAT = "laguna-m8-gather-sharded-operational-preflight-v2"
FIXTURE_FORMAT = "laguna-m8-gather-sharded-fixtures-v1"
BUNDLE_FORMAT = "laguna-m8-gather-sharded-native-bundle-v1"
BUNDLE_PREPARED_FORMAT = "laguna-m8-gather-sharded-native-bundle-prepared-v1"
FREEZER = Path(__file__).with_name("freeze_laguna_m8_gather_sharded_binary_bundle.py")
BUNDLE_ROOT = Path(
    "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/binaries/"
    "gather-sharded-phase-ab-7e6a740-20260724T1104Z"
)
BUNDLE_MANIFEST_NAME = "manifest.json"
BUNDLE_PREPARED_NAME = "bundle-prepared.json"
BUNDLE_EXPECTED = {
    "shared-_C.abi3.so": {
        "role": "approved_record_shared_ops",
        "source": "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/vllm_xpu_kernels/_C.abi3.so",
        "sha256": "126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2",
    },
    "shared-_xpu_C.abi3.so": {
        "role": "approved_record_rank_sum",
        "source": "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/vllm_xpu_kernels/_xpu_C.abi3.so",
        "sha256": "f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8",
    },
    "candidate-_moe_C.abi3.so": {
        "role": "standalone_sharded_gather_control_and_candidate",
        "source": "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/binaries/gather-sharded-7e6a740-20260724/_moe_C.abi3.so",
        "sha256": "3a16e85f7b6f324246f89e03d8aa89c37f0d6097c59d0a323ab2822dccd6d99f",
    },
    "libgdn_attn_kernels_xe_2.so": {
        "role": "required_xpu_module_dependency",
        "source": "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/vllm_xpu_kernels/libgdn_attn_kernels_xe_2.so",
        "sha256": "cdcf9539ac1715ef1dd9a81df422dd5bc1f3a58eff93e1bc5bde05959b5d34bb",
    },
    "libgrouped_gemm_xe_2.so": {
        "role": "required_xpu_module_dependency",
        "source": "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/vllm_xpu_kernels/libgrouped_gemm_xe_2.so",
        "sha256": "fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96",
    },
    "libgrouped_gemm_xe_default.so": {
        "role": "required_xpu_module_dependency",
        "source": "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/vllm_xpu_kernels/libgrouped_gemm_xe_default.so",
        "sha256": "982fb0b7fc96c877aaefa33f3342936af9403ed3960106dececf08697d98d53c",
    },
    "libmhc_kernels_xe_2.so": {
        "role": "required_xpu_module_dependency",
        "source": "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/vllm_xpu_kernels/libmhc_kernels_xe_2.so",
        "sha256": "f689c3d200731167394c387d267df90311fd5ec21eff9dededb619e871ce1a4f",
    },
    "libmqa_logits_kernels_xe_2.so": {
        "role": "required_xpu_module_dependency",
        "source": "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/vllm_xpu_kernels/libmqa_logits_kernels_xe_2.so",
        "sha256": "58cca1a0507914762b36874d719557715f3a8ae045106bc0aed42bd16e5b6aeb",
    },
}
BUNDLE_FILENAMES = frozenset(BUNDLE_EXPECTED)
SOURCE_PACKET_PATH = REPOSITORY_ROOT / "data/laguna-s-2.1-m8-gather-sharded-source-build-ir-20260724.json"
SOURCE_PACKET_SHA256 = "ef17daab068353e4ef8fbbbbda513a67811beda4fa81ae0a3f8b5d028a487c36"
DEVICE_IR_REPORT_SHA256 = "e6fefcaacc3253718c8a21ee6eae2544131fee613099ebf91cac9ddbdebd0505"
CANDIDATE_BINARY_SHA256 = "3a16e85f7b6f324246f89e03d8aa89c37f0d6097c59d0a323ab2822dccd6d99f"
FIXTURE_ROOT = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/evidence/m8-gather-sharded-fixtures-30b043b2b-20260724T1050Z")
FIXTURE_MANIFEST_SHA256 = "b1bef1cfeb72502074c0408ab73fa8bdf6f30732862410360658284b74161bd0"
FIXTURE_ANALYSIS_SHA256 = "04a897553820581f22f6d7ff62d72b08b6494f233caf6398308c667eeab6c8d4"
OPERATIONAL_REPORT_PATH = Path("/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/m8-gather-sharded-operational-preflight-20260724T104851Z/report.json")
OPERATIONAL_REPORT_SHA256 = "1c08e4e22fb24931258124f7dee3b31e5d117d715fae239c024e69ffb28b3649"
REQUIRED_TOOL_ROLES = frozenset(
    {
        "source_ir_inspector",
        "fixture_preparer",
        "operational_preflight",
        "native_bundle_freezer",
        "packet_freezer",
        "stage0_completion_generator",
        "phase_a_runner",
        "phase_a_runtime",
        "phase_a_coordinator",
        "phase_a_analyzer",
        "phase_b_runner",
        "phase_b_profile_fixture",
        "phase_b_counter_parser",
        "phase_b_analyzer",
    }
)
ROLE_PATHS = {
    "source_ir_inspector": (
        "experiments/laguna-s-2.1-xpu-b70/tools/inspect_laguna_m8_gather_sharded_spirv.py",
        "experiments/laguna-s-2.1-xpu-b70/tools/test_inspect_laguna_m8_gather_sharded_spirv.py",
    ),
    "fixture_preparer": (
        "experiments/laguna-s-2.1-xpu-b70/tools/prepare_laguna_m8_gather_sharded_fixtures.py",
        "experiments/laguna-s-2.1-xpu-b70/tools/test_prepare_laguna_m8_gather_sharded_fixtures.py",
    ),
    "operational_preflight": (
        "experiments/laguna-s-2.1-xpu-b70/tools/preflight_laguna_m8_gather_sharded_operational.py",
        "experiments/laguna-s-2.1-xpu-b70/tools/test_preflight_laguna_m8_gather_sharded_operational.py",
    ),
    "native_bundle_freezer": (
        "experiments/laguna-s-2.1-xpu-b70/tools/freeze_laguna_m8_gather_sharded_binary_bundle.py",
        "experiments/laguna-s-2.1-xpu-b70/tools/test_freeze_laguna_m8_gather_sharded_binary_bundle.py",
    ),
    "packet_freezer": (
        "experiments/laguna-s-2.1-xpu-b70/tools/freeze_laguna_m8_gather_sharded_packets.py",
        "experiments/laguna-s-2.1-xpu-b70/tools/test_freeze_laguna_m8_gather_sharded_packets.py",
    ),
    "stage0_completion_generator": (
        "experiments/laguna-s-2.1-xpu-b70/tools/freeze_laguna_m8_gather_sharded_stage0_completion.py",
        "experiments/laguna-s-2.1-xpu-b70/tools/test_freeze_laguna_m8_gather_sharded_stage0_completion.py",
    ),
    "phase_a_runner": (
        "experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_m8_gather_sharded_phase_a.py",
        "experiments/laguna-s-2.1-xpu-b70/tools/test_laguna_m8_gather_sharded_phase_a.py",
    ),
    "phase_a_runtime": (
        "experiments/laguna-s-2.1-xpu-b70/tools/laguna_m8_gather_sharded_phase_a_runtime.py",
        "experiments/laguna-s-2.1-xpu-b70/tools/test_laguna_m8_gather_sharded_phase_a.py",
    ),
    "phase_a_coordinator": (
        "experiments/laguna-s-2.1-xpu-b70/tools/orchestrate_laguna_m8_gather_sharded_phase_a.py",
        "experiments/laguna-s-2.1-xpu-b70/tools/test_laguna_m8_gather_sharded_phase_a.py",
    ),
    "phase_a_analyzer": (
        "experiments/laguna-s-2.1-xpu-b70/tools/analyze_laguna_m8_gather_sharded_phase_a.py",
        "experiments/laguna-s-2.1-xpu-b70/tools/test_laguna_m8_gather_sharded_phase_a.py",
    ),
    "phase_b_runner": (
        "experiments/laguna-s-2.1-xpu-b70/tools/run_laguna_m8_gather_sharded_phase_b.py",
        "experiments/laguna-s-2.1-xpu-b70/tools/test_laguna_m8_gather_sharded_phase_b.py",
    ),
    "phase_b_profile_fixture": (
        "experiments/laguna-s-2.1-xpu-b70/tools/profile_laguna_m8_gather_sharded_phase_b_fixture.py",
        "experiments/laguna-s-2.1-xpu-b70/tools/test_laguna_m8_gather_sharded_phase_b.py",
    ),
    "phase_b_counter_parser": (
        "experiments/laguna-s-2.1-xpu-b70/tools/laguna_m8_gather_sharded_counter_parser.py",
        "experiments/laguna-s-2.1-xpu-b70/tools/test_laguna_m8_gather_sharded_phase_b.py",
    ),
    "phase_b_analyzer": (
        "experiments/laguna-s-2.1-xpu-b70/tools/analyze_laguna_m8_gather_sharded_phase_b.py",
        "experiments/laguna-s-2.1-xpu-b70/tools/test_laguna_m8_gather_sharded_phase_b.py",
    ),
}
TENSOR_NAMES = frozenset(
    {
        "route_rows",
        "weights",
        "scale_add_input",
        "four_rank_tail",
        "residual_input",
        "norm_weight",
    }
)
FIXTURE_MEMBER_NAMES = frozenset(
    {
        "manifest.json",
        "analysis.json",
        "canonical_route_map.int32.le.bin",
        "route_rows.uint16.le.bin",
        "weights.uint32.le.bin",
        "scale_add_input.uint16.le.bin",
        "four_rank_tail.uint16.le.bin",
        "residual_input.uint16.le.bin",
        "norm_weight.uint16.le.bin",
    }
)
RECORD_VLLM = "8936aac144929190c1e53f8b8624ca397ce16f5b"
RECORD_KERNELS = "b6076ce1249ffee0e30bee528f4cd15c3bffb234"
CANDIDATE_KERNELS = "7e6a74026a2a4370abcb7973d28bbc9d1ddd1be6"
ACTIONS_NOT_PERFORMED = [
    "Torch import",
    "native-library import",
    "XPU enumeration",
    "XPU allocation",
    "XPU primitive",
    "unitrace",
    "model load",
    "generation",
    "network",
]
AUDIT_FORMAT = "laguna-m8-gather-sharded-independent-audit-v1"
AUDIT_STATUS = "pass_all_blockers_resolved"
AUDIT_REVIEWER_AUTHORITY = "independent_read_only_reviewer"
AUDIT_REQUIRED_KEYS = frozenset(
    {
        "format",
        "status",
        "read_only",
        "audit_id",
        "reviewer_id",
        "reviewer_authority",
        "scopes",
        "reviewed_source_packet",
        "reviewed_tool_hashes",
        "blocker_resolution",
        "open_findings",
    }
)
REQUIRED_AUDIT_SCOPES = frozenset(
    {
        "bundle_and_storage_closure",
        "declaration_and_evidence_reconciliation",
        "filesystem_descriptor_and_namespace_safety",
        "git_and_python_subprocess_identity",
        "source_schema_and_transitive_tool_closure",
        "test_corruption_and_fail_closed_coverage",
    }
)
REQUIRED_AUDIT_BLOCKER_KEYS = frozenset(
    {
        "bundle_child_fields_reopened_and_rehashed",
        "bundle_root_identity_and_storage_independently_attested",
        "declaration_rebuilt_field_for_field",
        "git_commit_is_canonical_reachable_and_bound_paths_clean",
        "git_environment_binary_timeout_and_output_hardened",
        "independent_audits_are_distinct_immutable_and_complete",
        "input_and_audit_paths_are_internal_nvme_only",
        "invocation_action_claims_are_scoped_and_enforceable",
        "local_helper_closure_is_transitive_and_deterministic",
        "output_parent_fd_is_retained_and_namespace_stable",
        "python_child_identity_environment_timeout_and_output_hardened",
        "regular_file_reads_have_stable_same_fd_metadata",
        "source_packet_schema_is_exact_and_complete",
    }
)
TOOLS_DIRECTORY = REPOSITORY_ROOT / "experiments/laguna-s-2.1-xpu-b70/tools"
GIT = Path("/usr/bin/git")
GIT_SHA256 = "2a8c18fbf43da9f692d75474c72bea9dfd796c260b0f3dfe456376abc3bbd668"
PYTHON_EXECUTABLE = Path(
    "/home/steve/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12"
)
PYTHON_EXECUTABLE_SHA256 = "202c17d1671602a4ef1d43e9b2fdbef0769443f37bf5e51f6b603e0b2c27d9d8"
SUBPROCESS_ENVIRONMENT = {
    "HOME": "/nonexistent",
    "LANG": "C",
    "LC_ALL": "C",
    "PATH": "/usr/bin:/bin",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONHASHSEED": "0",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def is_commit(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )


STABLE_STAT_FIELDS = (
    "st_dev",
    "st_ino",
    "st_mode",
    "st_nlink",
    "st_uid",
    "st_gid",
    "st_size",
    "st_mtime_ns",
    "st_ctime_ns",
)


def _same_metadata(before: os.stat_result, after: os.stat_result) -> bool:
    return all(
        getattr(before, field) == getattr(after, field)
        for field in STABLE_STAT_FIELDS
    )


def _regular_bytes_fd(
    descriptor: int,
    label: str,
    *,
    maximum: int = 16 * 1024 * 1024,
    expected_mode: int | None = None,
) -> bytes:
    """Read one already-open regular file, retaining its identity throughout."""
    before = os.fstat(descriptor)
    require(stat.S_ISREG(before.st_mode), f"not a regular file: {label}")
    require(before.st_size <= maximum, f"file exceeds bound: {label}")
    if expected_mode is not None:
        require(
            stat.S_IMODE(before.st_mode) == expected_mode,
            f"unsafe file mode: {label}",
        )
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    remaining = before.st_size
    while remaining:
        chunk = os.read(descriptor, min(1024 * 1024, remaining))
        require(chunk, f"short read: {label}")
        chunks.append(chunk)
        remaining -= len(chunk)
    require(not os.read(descriptor, 1), f"file changed while read: {label}")
    after = os.fstat(descriptor)
    require(
        _same_metadata(before, after),
        f"same-FD metadata changed while read: {label}",
    )
    return b"".join(chunks)


def _regular_bytes(path: Path, *, maximum: int = 16 * 1024 * 1024) -> bytes:
    require(path.is_absolute(), f"path must be absolute: {path}")
    descriptor = os.open(
        path,
        os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        return _regular_bytes_fd(descriptor, str(path), maximum=maximum)
    finally:
        os.close(descriptor)


def _canonical_object(path: Path, *, maximum: int = 16 * 1024 * 1024) -> tuple[dict[str, Any], bytes]:
    raw = _regular_bytes(path, maximum=maximum)
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"invalid JSON: {path}") from error
    require(isinstance(value, dict) and raw == canonical(value), f"noncanonical JSON: {path}")
    return value, raw


def _canonical_object_fd(
    descriptor: int,
    label: str,
    *,
    maximum: int = 16 * 1024 * 1024,
    expected_mode: int | None = None,
) -> tuple[dict[str, Any], bytes]:
    raw = _regular_bytes_fd(
        descriptor,
        label,
        maximum=maximum,
        expected_mode=expected_mode,
    )
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"invalid JSON: {label}") from error
    require(
        isinstance(value, dict) and raw == canonical(value),
        f"noncanonical JSON: {label}",
    )
    return value, raw


def _regular_bytes_at(
    directory_fd: int,
    name: str,
    *,
    expected_mode: int,
    maximum: int,
) -> bytes:
    descriptor = os.open(
        name,
        os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=directory_fd,
    )
    try:
        before = os.fstat(descriptor)
        require(
            stat.S_ISREG(before.st_mode)
            and stat.S_IMODE(before.st_mode) == expected_mode
            and before.st_size <= maximum,
            f"unsafe bundle member metadata: {name}",
        )
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            block = os.read(descriptor, min(1024 * 1024, remaining))
            require(block, f"short bundle member read: {name}")
            chunks.append(block)
            remaining -= len(block)
        require(not os.read(descriptor, 1), f"bundle member grew while read: {name}")
        after = os.fstat(descriptor)
        require(
            _same_metadata(before, after),
            f"same-FD bundle member metadata changed: {name}",
        )
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _canonical_object_at(
    directory_fd: int,
    name: str,
) -> tuple[dict[str, Any], bytes]:
    raw = _regular_bytes_at(
        directory_fd,
        name,
        expected_mode=0o444,
        maximum=1024 * 1024,
    )
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"invalid bundle metadata JSON: {name}") from error
    require(
        isinstance(value, dict) and raw == canonical(value),
        f"noncanonical bundle metadata: {name}",
    )
    return value, raw


def _absolute_from_input(value: object, label: str) -> Path:
    require(isinstance(value, str), f"{label} must be a path string")
    path = Path(value)
    require(path.is_absolute() and not path.is_symlink(), f"unsafe {label}")
    return path


def _path_record(path: Path, digest: str) -> dict[str, str]:
    raw = _regular_bytes(path)
    require(sha256_bytes(raw) == digest, f"digest drift: {path}")
    return {"path": str(path), "sha256": digest}


def _validate_internal_storage(storage: object, label: str) -> dict[str, str]:
    require(
        isinstance(storage, dict)
        and set(storage)
        == {"filesystem", "source", "major_minor", "mount_point", "sysfs_device"}
        and storage.get("filesystem") == "ext4"
        and storage.get("source") == "/dev/nvme0n1p2"
        and storage.get("major_minor") == "259:2"
        and isinstance(storage.get("mount_point"), str)
        and isinstance(storage.get("sysfs_device"), str)
        and any(
            part.startswith("nvme")
            for part in Path(storage["sysfs_device"]).parts
        ),
        f"{label} is not on the frozen internal NVMe",
    )
    return dict(storage)


def _unescape_mount_field(value: str) -> str:
    for encoded, decoded in (
        ("\\040", " "),
        ("\\011", "\t"),
        ("\\012", "\n"),
        ("\\134", "\\"),
    ):
        value = value.replace(encoded, decoded)
    return value


def _attest_internal_nvme(target: Path) -> dict[str, str]:
    """Locally attest storage without importing any mutable helper module."""
    resolved_target = target.resolve(strict=True)
    descriptor = os.open(
        "/proc/self/mountinfo",
        os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        blocks: list[bytes] = []
        total = 0
        while True:
            block = os.read(descriptor, 64 * 1024)
            if not block:
                break
            total += len(block)
            require(total <= 4 * 1024 * 1024, "mountinfo exceeds bound")
            blocks.append(block)
    finally:
        os.close(descriptor)
    try:
        lines = b"".join(blocks).decode("utf-8", errors="strict").splitlines()
    except UnicodeDecodeError as error:
        raise RuntimeError("mountinfo is not UTF-8") from error
    candidates: list[dict[str, str]] = []
    for line in lines:
        fields = line.split()
        try:
            separator = fields.index("-")
            major_minor = fields[2]
            mount_point = _unescape_mount_field(fields[4])
            filesystem = fields[separator + 1]
            source = _unescape_mount_field(fields[separator + 2])
        except (IndexError, ValueError):
            raise RuntimeError("malformed mountinfo row") from None
        mounted = Path(mount_point)
        if resolved_target == mounted or resolved_target.is_relative_to(mounted):
            candidates.append(
                {
                    "mount_point": mount_point,
                    "filesystem": filesystem,
                    "source": source,
                    "major_minor": major_minor,
                }
            )
    require(candidates, "no backing mount found for retained evidence")
    record = max(candidates, key=lambda item: len(Path(item["mount_point"]).parts))
    try:
        sysfs_device = (Path("/sys/dev/block") / record["major_minor"]).resolve(
            strict=True
        )
    except OSError as error:
        raise RuntimeError("block-device sysfs identity unavailable") from error
    return _validate_internal_storage(
        {**record, "sysfs_device": str(sysfs_device)}, "retained evidence"
    )


def _approved_parent(path: Path, label: str) -> Path:
    require(path.is_absolute() and not path.is_symlink(), f"unsafe {label}")
    resolved_parent = path.parent.resolve(strict=True)
    require(path.parent == resolved_parent, f"{label} has an intermediate symlink")
    artifact_prefix = ROOT_PREFIX.resolve(strict=True)
    tracked_prefix = TRACKED_DATA_ROOT.resolve(strict=True)
    require(
        resolved_parent.is_relative_to(artifact_prefix)
        or resolved_parent.is_relative_to(tracked_prefix),
        f"{label} is outside approved internal-NVMe roots",
    )
    return resolved_parent


def _require_nvme_output(
    path: Path,
    storage_attestor: Callable[[Path], Mapping[str, str]],
) -> dict[str, str]:
    resolved_parent = _approved_parent(path, "certificate output")
    return _validate_internal_storage(
        dict(storage_attestor(resolved_parent)),
        "certificate output",
    )


def _require_internal_evidence(
    path: Path,
    label: str,
    storage_attestor: Callable[[Path], Mapping[str, str]],
) -> dict[str, str]:
    """Compatibility probe for tests; production readers retain the FD below."""
    descriptor, storage = _open_internal_evidence(path, label, storage_attestor)
    try:
        return storage
    finally:
        os.close(descriptor)


def _visible_identity_matches(path: Path, descriptor: int, label: str) -> None:
    visible = os.stat(path, follow_symlinks=False)
    opened = os.fstat(descriptor)
    require(
        (visible.st_dev, visible.st_ino) == (opened.st_dev, opened.st_ino),
        f"{label} namespace changed while retained",
    )


def _open_internal_evidence(
    path: Path,
    label: str,
    storage_attestor: Callable[[Path], Mapping[str, str]],
    *,
    expected_mode: int = 0o444,
) -> tuple[int, dict[str, str]]:
    """Open, attestate, and retain a regular internal-NVMe evidence file.

    The returned descriptor is the authority.  Callers must consume it before
    closing it; a later pathname lookup is not accepted as evidence.
    """
    resolved_parent = _approved_parent(path, label)
    descriptor = os.open(
        path,
        os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        opened = os.fstat(descriptor)
        require(
            stat.S_ISREG(opened.st_mode)
            and stat.S_IMODE(opened.st_mode) == expected_mode,
            f"{label} is not an exact {expected_mode:04o} regular file",
        )
        require(
            path.parent.resolve(strict=True) == resolved_parent,
            f"{label} path identity drift",
        )
        _visible_identity_matches(path, descriptor, label)
        storage = _validate_internal_storage(
            dict(storage_attestor(Path("/proc/self/fd") / str(descriptor))),
            label,
        )
        require(
            _same_metadata(opened, os.fstat(descriptor)),
            f"{label} metadata changed during FD attestation",
        )
        _visible_identity_matches(path, descriptor, label)
        return descriptor, storage
    except BaseException:
        os.close(descriptor)
        raise


def _open_internal_directory(
    path: Path,
    label: str,
    storage_attestor: Callable[[Path], Mapping[str, str]],
) -> tuple[int, dict[str, str]]:
    """Open and FD-attest an approved internal-NVMe directory."""
    _approved_parent(path, label)
    descriptor = os.open(
        path,
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_CLOEXEC
        | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        opened = os.fstat(descriptor)
        require(stat.S_ISDIR(opened.st_mode), f"{label} is not a directory")
        _visible_identity_matches(path, descriptor, label)
        storage = _validate_internal_storage(
            dict(storage_attestor(Path("/proc/self/fd") / str(descriptor))),
            label,
        )
        require(
            _same_metadata(opened, os.fstat(descriptor)),
            f"{label} metadata changed during FD attestation",
        )
        _visible_identity_matches(path, descriptor, label)
        return descriptor, storage
    except BaseException:
        os.close(descriptor)
        raise


def _visible_member_identity_matches(
    directory_fd: int,
    name: str,
    descriptor: int,
    label: str,
) -> None:
    visible = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    opened = os.fstat(descriptor)
    require(
        (visible.st_dev, visible.st_ino) == (opened.st_dev, opened.st_ino),
        f"{label} namespace changed while retained",
    )


def _anchored_live_committed_bytes(
    path: Path,
    relative: str,
    digest: str,
    commit: str,
    committed_blob_reader: Callable[[str, str], bytes],
    label: str,
) -> bytes:
    """Compare live and committed bytes while retaining the live inode."""
    descriptor = os.open(
        path,
        os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        raw = _regular_bytes_fd(descriptor, str(path))
        require(sha256_bytes(raw) == digest, f"live {label} digest drift: {relative}")
        require(
            sha256_bytes(committed_blob_reader(commit, relative)) == digest,
            f"committed {label} digest drift: {relative}",
        )
        _visible_identity_matches(path, descriptor, f"live {label}")
        return raw
    finally:
        os.close(descriptor)


class _RetainedBuildEvidence:
    """All mutable-namespace evidence retained across one complete build."""

    def __init__(
        self,
        declaration: Mapping[str, Any],
        input_path: Path,
        storage_attestor: Callable[[Path], Mapping[str, str]],
        preopened_input: tuple[
            int, os.stat_result, Mapping[str, str], Mapping[str, Any], bytes
        ]
        | None = None,
    ) -> None:
        self._files: dict[str, tuple[Path, int, os.stat_result]] = {}
        self.fixture_members: dict[str, tuple[int, os.stat_result]] = {}
        self.fixture_root_fd: int | None = None
        self.fixture_root_initial: os.stat_result | None = None
        self.fixture_root = FIXTURE_ROOT
        try:
            if preopened_input is None:
                self.input, self.input_raw, self.input_storage = self._open_json(
                    input_path, "stage0 completion input", storage_attestor
                )
            else:
                (
                    descriptor,
                    initial,
                    supplied_storage,
                    supplied_input,
                    supplied_raw,
                ) = preopened_input
                self._files["stage0 completion input"] = (
                    input_path,
                    descriptor,
                    initial,
                )
                self.input = dict(supplied_input)
                self.input_raw = supplied_raw
                self.input_storage = _validate_internal_storage(
                    dict(supplied_storage), "stage0 completion input"
                )
            require(
                self.input == dict(declaration),
                "retained stage0 completion input bytes drift",
            )
            source_record = declaration.get("source_packet")
            require(
                isinstance(source_record, dict)
                and source_record.get("path") == str(SOURCE_PACKET_PATH)
                and source_record.get("sha256") == SOURCE_PACKET_SHA256,
                "source packet identity substitution",
            )
            self.source, self.source_raw, self.source_storage = self._open_json(
                SOURCE_PACKET_PATH, "source packet", storage_attestor
            )
            operational_record = declaration.get("operational_preflight")
            require(
                isinstance(operational_record, dict)
                and operational_record.get("report") == str(OPERATIONAL_REPORT_PATH)
                and operational_record.get("sha256") == OPERATIONAL_REPORT_SHA256,
                "operational report identity substitution",
            )
            (
                self.operational,
                self.operational_raw,
                self.operational_storage,
            ) = self._open_json(
                OPERATIONAL_REPORT_PATH, "operational report", storage_attestor
            )
            fixture_record = declaration.get("fixture")
            require(
                isinstance(fixture_record, dict)
                and fixture_record.get("root") == str(FIXTURE_ROOT)
                and fixture_record.get("manifest")
                == str(FIXTURE_ROOT / "manifest.json")
                and fixture_record.get("analysis")
                == str(FIXTURE_ROOT / "analysis.json"),
                "fixture identity substitution",
            )
            self.fixture_root_fd, self.fixture_storage = _open_internal_directory(
                FIXTURE_ROOT, "fixture root", storage_attestor
            )
            self.fixture_root_initial = os.fstat(self.fixture_root_fd)
            require(
                set(os.listdir(self.fixture_root_fd)) == FIXTURE_MEMBER_NAMES,
                "fixture root inventory drift",
            )
            for name in sorted(FIXTURE_MEMBER_NAMES):
                descriptor = os.open(
                    name,
                    os.O_RDONLY
                    | os.O_CLOEXEC
                    | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=self.fixture_root_fd,
                )
                metadata = os.fstat(descriptor)
                require(
                    stat.S_ISREG(metadata.st_mode)
                    and stat.S_IMODE(metadata.st_mode) == 0o444
                    and metadata.st_dev == self.fixture_root_initial.st_dev,
                    f"fixture member is not an exact 0444 regular file: {name}",
                )
                _visible_member_identity_matches(
                    self.fixture_root_fd,
                    name,
                    descriptor,
                    f"fixture member {name}",
                )
                self.fixture_members[name] = (descriptor, metadata)
            self.manifest, self.manifest_raw = _canonical_object_fd(
                self.fixture_members["manifest.json"][0],
                str(FIXTURE_ROOT / "manifest.json"),
                expected_mode=0o444,
            )
            self.analysis, self.analysis_raw = _canonical_object_fd(
                self.fixture_members["analysis.json"][0],
                str(FIXTURE_ROOT / "analysis.json"),
                expected_mode=0o444,
            )
        except BaseException:
            self.close()
            raise

    def _open_json(
        self,
        path: Path,
        label: str,
        storage_attestor: Callable[[Path], Mapping[str, str]],
    ) -> tuple[dict[str, Any], bytes, dict[str, str]]:
        descriptor, storage = _open_internal_evidence(
            path, label, storage_attestor, expected_mode=0o444
        )
        initial = os.fstat(descriptor)
        self._files[label] = (path, descriptor, initial)
        value, raw = _canonical_object_fd(
            descriptor, str(path), expected_mode=0o444
        )
        return value, raw, storage

    def reconcile(self) -> None:
        for label, (path, descriptor, initial) in self._files.items():
            require(
                _same_metadata(initial, os.fstat(descriptor)),
                f"{label} metadata changed during complete build",
            )
            _visible_identity_matches(path, descriptor, label)
        require(
            self.fixture_root_fd is not None
            and self.fixture_root_initial is not None
            and _same_metadata(
                self.fixture_root_initial, os.fstat(self.fixture_root_fd)
            )
            and set(os.listdir(self.fixture_root_fd)) == FIXTURE_MEMBER_NAMES,
            "fixture root changed during complete build",
        )
        _visible_identity_matches(
            FIXTURE_ROOT, self.fixture_root_fd, "fixture root"
        )
        for name, (descriptor, initial) in self.fixture_members.items():
            require(
                _same_metadata(initial, os.fstat(descriptor)),
                f"fixture member metadata changed during complete build: {name}",
            )
            _visible_member_identity_matches(
                self.fixture_root_fd,
                name,
                descriptor,
                f"fixture member {name}",
            )

    def close(self) -> None:
        for descriptor, _initial in self.fixture_members.values():
            try:
                os.close(descriptor)
            except OSError:
                pass
        self.fixture_members.clear()
        if self.fixture_root_fd is not None:
            try:
                os.close(self.fixture_root_fd)
            except OSError:
                pass
            self.fixture_root_fd = None
        for _path, descriptor, _initial in self._files.values():
            try:
                os.close(descriptor)
            except OSError:
                pass
        self._files.clear()


def _parent_identity(descriptor: int) -> dict[str, int]:
    metadata = os.fstat(descriptor)
    require(stat.S_ISDIR(metadata.st_mode), "certificate parent is not a directory")
    return {"device": metadata.st_dev, "inode": metadata.st_ino}


def _open_output_parent(
    path: Path,
    storage_attestor: Callable[[Path], Mapping[str, str]],
) -> tuple[int, dict[str, str], dict[str, int]]:
    """Retain the approved parent descriptor from attestation through fsync."""
    parent = _approved_parent(path, "certificate output")
    descriptor = os.open(
        parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        identity = _parent_identity(descriptor)
        require(
            path.parent.resolve(strict=True) == parent,
            "certificate lexical parent changed before creation",
        )
        path_metadata = os.stat(parent, follow_symlinks=False)
        require(
            (path_metadata.st_dev, path_metadata.st_ino)
            == (identity["device"], identity["inode"]),
            "certificate parent identity changed before creation",
        )
        storage = _validate_internal_storage(
            dict(storage_attestor(Path("/proc/self/fd") / str(descriptor))),
            "certificate output",
        )
        lexical_after_attestation = os.stat(parent, follow_symlinks=False)
        require(
            _parent_identity(descriptor) == identity
            and path.parent.resolve(strict=True) == parent,
            "certificate parent identity changed during attestation",
        )
        require(
            (lexical_after_attestation.st_dev, lexical_after_attestation.st_ino)
            == (identity["device"], identity["inode"]),
            "certificate parent identity changed during attestation",
        )
        return descriptor, storage, identity
    except BaseException:
        os.close(descriptor)
        raise


def _write_exclusive(
    path: Path,
    payload: bytes,
    *,
    parent_fd: int,
    parent_identity: Mapping[str, int],
) -> None:
    """Write through the retained parent FD and reject namespace substitution."""
    require(path.name and path.parent != path, "unsafe certificate output name")
    require(_parent_identity(parent_fd) == dict(parent_identity), "certificate parent descriptor drift")
    descriptor = os.open(
        path.name,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_CLOEXEC
        | getattr(os, "O_NOFOLLOW", 0),
        0o400,
        dir_fd=parent_fd,
    )
    certificate_identity: tuple[int, int] | None = None
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            require(written > 0, "short certificate write")
            view = view[written:]
        os.fchmod(descriptor, 0o444)
        os.fsync(descriptor)
        metadata = os.fstat(descriptor)
        require(
            stat.S_ISREG(metadata.st_mode) and stat.S_IMODE(metadata.st_mode) == 0o444,
            "certificate metadata drift while writing",
        )
        certificate_identity = (metadata.st_dev, metadata.st_ino)
    finally:
        os.close(descriptor)
    require(_parent_identity(parent_fd) == dict(parent_identity), "certificate parent descriptor changed")
    require(
        path.parent.resolve(strict=True) == path.parent,
        "certificate lexical parent changed after creation",
    )
    path_parent = os.stat(path.parent, follow_symlinks=False)
    require(
        (path_parent.st_dev, path_parent.st_ino)
        == (parent_identity["device"], parent_identity["inode"]),
        "certificate parent identity changed after creation",
    )
    visible = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
    require(
        certificate_identity == (visible.st_dev, visible.st_ino)
        and stat.S_ISREG(visible.st_mode)
        and stat.S_IMODE(visible.st_mode) == 0o444,
        "certificate visible inode drift",
    )
    os.fsync(parent_fd)


def _require_frozen_certificate(path: Path) -> None:
    metadata = os.stat(path, follow_symlinks=False)
    require(
        stat.S_ISREG(metadata.st_mode) and stat.S_IMODE(metadata.st_mode) == 0o444,
        "stage0 completion certificate is not a frozen regular file",
    )


def _open_pinned_executable(path: Path, digest: str, label: str) -> int:
    """Return an executable FD whose bytes and visible inode are pinned."""
    require(
        path.is_absolute() and path.resolve(strict=True) == path,
        f"{label} executable identity drift",
    )
    descriptor = os.open(
        path,
        os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        metadata = os.fstat(descriptor)
        require(
            stat.S_ISREG(metadata.st_mode) and metadata.st_mode & 0o111,
            f"{label} executable mode drift",
        )
        require(
            sha256_bytes(
                _regular_bytes_fd(descriptor, str(path), maximum=64 * 1024 * 1024)
            )
            == digest,
            f"{label} executable identity drift",
        )
        _visible_identity_matches(path, descriptor, f"{label} executable")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _assert_pinned_executable(path: Path, digest: str, label: str) -> None:
    """Host-only probe retained for tests; execution uses the returned FD path."""
    descriptor = _open_pinned_executable(path, digest, label)
    os.close(descriptor)


def _run_pinned_executable(
    path: Path,
    digest: str,
    label: str,
    arguments: list[str],
    *,
    text: bool,
    timeout: int,
    cwd: Path,
    environment: Mapping[str, str],
    extra_fds: tuple[int, ...] = (),
) -> subprocess.CompletedProcess[Any]:
    """Exec the verified inode, never a pathname reopened after verification."""
    descriptor = _open_pinned_executable(path, digest, label)
    try:
        execution_path = f"/proc/self/fd/{descriptor}"
        return subprocess.run(
            [execution_path, *arguments],
            check=False,
            capture_output=True,
            text=text,
            cwd=str(cwd),
            env=dict(environment),
            timeout=timeout,
            pass_fds=(descriptor, *extra_fds),
        )
    finally:
        os.close(descriptor)


def _git_command(arguments: list[str], *, text: bool) -> subprocess.CompletedProcess[Any]:
    try:
        return _run_pinned_executable(
            GIT,
            GIT_SHA256,
            "Git",
            [
                "--no-optional-locks", "--literal-pathspecs", "-c",
                f"safe.directory={REPOSITORY_ROOT}", "-C",
                str(REPOSITORY_ROOT), *arguments,
            ],
            text=text,
            timeout=10,
            cwd=REPOSITORY_ROOT,
            environment=SUBPROCESS_ENVIRONMENT,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("pinned Git command timed out") from error


def _committed_blob(commit: str, path: str) -> bytes:
    result = _git_command(["show", f"{commit}:{path}"], text=False)
    require(
        result.returncode == 0 and result.stderr == b"",
        f"tool is not present at declared commit: {path}",
    )
    return result.stdout


def _verify_reachable_clean_commit(commit: str, paths: set[str]) -> None:
    """Require a real ancestor commit and clean, committed declared paths.

    This intentionally does *not* inspect unrelated untracked sibling tools:
    the declaration can only certify the exact paths it binds.
    """
    resolved = _git_command(
        ["rev-parse", "--verify", f"{commit}^{{commit}}"],
        text=True,
    )
    require(
        resolved.returncode == 0
        and resolved.stdout == commit + "\n"
        and resolved.stderr == "",
        "tools commit is not a canonical commit",
    )
    ancestry = _git_command(
        ["merge-base", "--is-ancestor", commit, "HEAD"],
        text=False,
    )
    require(
        ancestry.returncode == 0
        and ancestry.stdout == b""
        and ancestry.stderr == b"",
        "tools commit is not reachable from HEAD",
    )
    status = _git_command(
        ["status", "--porcelain=v1", "--", *sorted(paths)],
        text=True,
    )
    require(
        status.returncode == 0 and status.stdout == "" and status.stderr == "",
        "declared tool path is not clean and precommitted",
    )


def _local_helper_closure(
    paths: set[str],
    *,
    committed_blob_reader: Callable[[str, str], bytes],
    commit: str,
) -> list[dict[str, str]]:
    """Hash the deterministic transitive local-Python closure of bound tools."""
    pending = sorted(paths)
    seen: set[str] = set()
    closure: list[dict[str, str]] = []
    while pending:
        relative = pending.pop(0)
        if relative in seen:
            continue
        seen.add(relative)
        absolute = REPOSITORY_ROOT / relative
        descriptor = os.open(
            absolute,
            os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            raw = _regular_bytes_fd(descriptor, str(absolute))
            require(
                sha256_bytes(committed_blob_reader(commit, relative))
                == sha256_bytes(raw),
                f"committed helper digest drift: {relative}",
            )
            _visible_identity_matches(absolute, descriptor, "local helper")
        finally:
            os.close(descriptor)
        closure.append({"path": relative, "sha256": sha256_bytes(raw)})
        try:
            tree = ast.parse(raw, filename=relative)
        except SyntaxError as error:
            raise RuntimeError(f"bound helper does not parse: {relative}") from error
        for node in ast.walk(tree):
            candidates: list[str] = []
            if isinstance(node, ast.Import):
                candidates = [alias.name.split(".", 1)[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                candidates = [node.module.split(".", 1)[0]]
            for module in sorted(set(candidates)):
                local = TOOLS_DIRECTORY / f"{module}.py"
                if local.is_file():
                    candidate = str(local.relative_to(REPOSITORY_ROOT))
                    if candidate not in seen and candidate not in pending:
                        pending.append(candidate)
        pending.sort()
    return sorted(closure, key=lambda item: item["path"])


def _verify_tool_bindings(
    declaration: object,
    *,
    committed_blob_reader: Callable[[str, str], bytes],
    commit_verifier: Callable[[str, set[str]], None] = _verify_reachable_clean_commit,
) -> dict[str, Any]:
    require(isinstance(declaration, dict), "tools declaration must be an object")
    require(set(declaration) == {"commit", "bindings"}, "tools declaration schema drift")
    commit = declaration["commit"]
    bindings = declaration["bindings"]
    require(is_commit(commit), "tools commit is malformed")
    require(isinstance(bindings, list) and len(bindings) == len(REQUIRED_TOOL_ROLES), "wrong tool binding count")
    declared_paths: set[str] = set()
    result: dict[str, Any] = {"commit": commit, "bindings": []}
    observed: set[str] = set()
    for binding in bindings:
        require(isinstance(binding, dict), "tool binding must be an object")
        require(set(binding) == {"role", "path", "sha256", "test_path", "test_sha256"}, "tool binding schema drift")
        role, path, digest, test_path, test_digest = (
            binding["role"],
            binding["path"],
            binding["sha256"],
            binding["test_path"],
            binding["test_sha256"],
        )
        require(isinstance(role, str) and role in REQUIRED_TOOL_ROLES and role not in observed, "tool role drift")
        require(
            all(isinstance(item, str) and not item.startswith("/") and ".." not in Path(item).parts for item in (path, test_path)),
            "tool path must be a repository-relative regular path",
        )
        require(is_sha256(digest) and is_sha256(test_digest), "tool digest malformed")
        require((path, test_path) == ROLE_PATHS[role], "tool role path substitution")
        declared_paths.update({path, test_path})
        repo = REPOSITORY_ROOT
        live_path, live_test = repo / path, repo / test_path
        _anchored_live_committed_bytes(
            live_path, path, digest, commit, committed_blob_reader, "tool"
        )
        _anchored_live_committed_bytes(
            live_test, test_path, test_digest, commit, committed_blob_reader, "test"
        )
        observed.add(role)
        result["bindings"].append(dict(binding))
    require(observed == REQUIRED_TOOL_ROLES, "required Phase-A/B bindings are incomplete")
    commit_verifier(commit, declared_paths)
    result["bindings"].sort(key=lambda item: item["role"])
    result["local_helper_closure"] = _local_helper_closure(
        declared_paths,
        committed_blob_reader=committed_blob_reader,
        commit=commit,
    )
    result["git_validation"] = {
        "path": str(GIT),
        "sha256": GIT_SHA256,
        "repository": str(REPOSITORY_ROOT),
        "safe_directory": str(REPOSITORY_ROOT),
        "environment": dict(SUBPROCESS_ENVIRONMENT),
        "timeout_seconds": 10,
        "optional_locks": False,
        "literal_pathspecs": True,
    }
    return result


def _tool_hashes(tools: Mapping[str, Any]) -> dict[str, str]:
    bindings = tools.get("bindings")
    closure = tools.get("local_helper_closure")
    require(isinstance(bindings, list) and isinstance(closure, list), "tool closure missing")
    hashes: dict[str, str] = {}
    for item in bindings:
        require(isinstance(item, dict), "tool binding malformed in closure")
        for path_key, digest_key in (("path", "sha256"), ("test_path", "test_sha256")):
            path, digest = item.get(path_key), item.get(digest_key)
            require(isinstance(path, str) and is_sha256(digest), "tool binding hash malformed")
            require(path not in hashes or hashes[path] == digest, "tool path digest conflict")
            hashes[path] = digest
    for item in closure:
        require(isinstance(item, dict) and set(item) == {"path", "sha256"}, "helper closure schema drift")
        path, digest = item["path"], item["sha256"]
        require(isinstance(path, str) and is_sha256(digest), "helper closure digest malformed")
        require(path not in hashes or hashes[path] == digest, "helper closure digest conflict")
        hashes[path] = digest
    return dict(sorted(hashes.items()))


def _verify_independent_audits(
    declaration: object,
    *,
    source_packet: Mapping[str, Any],
    tools: Mapping[str, Any],
    storage_attestor: Callable[[Path], Mapping[str, str]],
) -> list[dict[str, Any]]:
    # These immutable records bind distinct declared reviewer identities and
    # scopes.  Filesystem evidence cannot establish a human/agent trust
    # boundary beyond that convention, so no stronger provenance is claimed.
    require(isinstance(declaration, list) and len(declaration) >= 2, "at least two independent audit records are required")
    expected_source = {"path": source_packet["path"], "sha256": source_packet["sha256"]}
    expected_hashes = _tool_hashes(tools)
    observed_ids: set[str] = set()
    observed_reviewers: set[str] = set()
    observed_paths: set[str] = set()
    result: list[dict[str, Any]] = []
    for record in declaration:
        require(isinstance(record, dict) and set(record) == {"path", "sha256"}, "audit declaration schema drift")
        path = _absolute_from_input(record["path"], "independent audit")
        digest = record["sha256"]
        require(is_sha256(digest) and path not in observed_paths, "audit path or digest malformed")
        descriptor, storage = _open_internal_evidence(
            path, "independent audit", storage_attestor
        )
        try:
            audit, raw = _canonical_object_fd(
                descriptor,
                str(path),
                expected_mode=0o444,
            )
            _visible_identity_matches(path, descriptor, "independent audit")
        finally:
            os.close(descriptor)
        require(sha256_bytes(raw) == digest, "independent audit digest drift")
        require(set(audit) == AUDIT_REQUIRED_KEYS, "independent audit schema drift")
        require(audit.get("format") == AUDIT_FORMAT and audit.get("status") == AUDIT_STATUS and audit.get("read_only") is True, "independent audit did not pass read-only review")
        audit_id = audit.get("audit_id")
        reviewer_id = audit.get("reviewer_id")
        reviewer_authority = audit.get("reviewer_authority")
        require(isinstance(audit_id, str) and audit_id and audit_id not in observed_ids, "independent audit identity is not distinct")
        require(
            isinstance(reviewer_id, str)
            and reviewer_id
            and reviewer_id not in observed_reviewers
            and reviewer_authority == AUDIT_REVIEWER_AUTHORITY,
            "independent audit reviewer is not distinct",
        )
        require(
            isinstance(audit.get("scopes"), list)
            and audit["scopes"] == sorted(REQUIRED_AUDIT_SCOPES),
            "independent audit scope is incomplete",
        )
        require(audit.get("reviewed_source_packet") == expected_source, "independent audit source identity drift")
        require(audit.get("reviewed_tool_hashes") == expected_hashes, "independent audit tool identity drift")
        resolution = audit.get("blocker_resolution")
        require(
            isinstance(resolution, dict)
            and set(resolution) == REQUIRED_AUDIT_BLOCKER_KEYS
            and all(value is True for value in resolution.values())
            and audit.get("open_findings") == [],
            "independent audit leaves unresolved blockers",
        )
        observed_ids.add(audit_id)
        observed_reviewers.add(reviewer_id)
        observed_paths.add(path)
        result.append({"path": str(path), "sha256": digest, "storage": storage})
    return sorted(result, key=lambda item: item["path"])


def _verify_source_packet_object(
    record: object,
    packet: Mapping[str, Any],
    raw: bytes,
    storage: Mapping[str, str],
) -> dict[str, Any]:
    require(isinstance(record, dict) and set(record) == {"path", "sha256"}, "source packet declaration drift")
    path = _absolute_from_input(record["path"], "source packet")
    digest = record["sha256"]
    require(is_sha256(digest), "source packet digest malformed")
    require(
        path == SOURCE_PACKET_PATH and digest == SOURCE_PACKET_SHA256,
        "source packet identity substitution",
    )
    require(sha256_bytes(raw) == digest, "source packet digest drift")
    require(
        set(packet)
        == {
            "format", "status", "date", "record", "preregistration", "checkpoint",
            "candidate", "identity_correction", "cpu_validation", "build", "device_ir",
            "false_actions", "next_required",
        },
        "source packet top-level schema drift",
    )
    require(packet.get("format") == SOURCE_PACKET_FORMAT, "source packet format drift")
    require(packet.get("status") == SOURCE_PACKET_STATUS, "source packet status drift")
    source = packet.get("candidate")
    proof = packet.get("device_ir")
    validation = packet.get("cpu_validation")
    record_identity = packet.get("record")
    build = packet.get("build")
    require(isinstance(source, dict) and isinstance(proof, dict) and isinstance(validation, dict) and isinstance(record_identity, dict) and isinstance(build, dict), "source packet proof missing")
    require(
        set(source)
        == {"xpu_kernels_commit", "parent", "direct_child_of_record", "selector", "geometry", "source_sha256"}
        and source.get("selector") == "VLLM_XPU_LAGUNA_M8_GATHER_SHARDED=1"
        and source.get("geometry")
        == {
            "tokens": 8, "topk": 10, "hidden": 3072, "shards_per_token": 6,
            "work_items_per_shard": 64, "elements_per_work_item": 8,
            "columns_per_shard": 512, "workgroups_per_launch": 48,
            "simd32_subgroups_per_launch": 96,
        },
        "candidate source schema drift",
    )
    require(source.get("xpu_kernels_commit") == CANDIDATE_KERNELS and source.get("parent") == RECORD_KERNELS and source.get("direct_child_of_record") is True, "candidate source identity drift")
    require(record_identity.get("vllm_commit") == RECORD_VLLM and record_identity.get("xpu_kernels_commit") == RECORD_KERNELS, "record source identity drift")
    require(isinstance(source.get("source_sha256"), dict) and source["source_sha256"], "candidate source diff proof missing")
    require(all(is_sha256(value) for value in source["source_sha256"].values()), "candidate source digest malformed")
    binary = build.get("binary")
    require(
        isinstance(binary, dict)
        and binary.get("name") == "_moe_C.abi3.so"
        and binary.get("sha256") == CANDIDATE_BINARY_SHA256
        and binary.get("imported") is False
        and isinstance(build.get("evidence_sha256"), dict)
        and build["evidence_sha256"]
        and all(is_sha256(value) for value in build["evidence_sha256"].values()),
        "source build proof failed",
    )
    require(
        proof.get("report_sha256") == DEVICE_IR_REPORT_SHA256
        and proof.get("report_passed") is True
        and proof.get("fused_multiply_add_present") is False,
        "device IR proof failed",
    )
    require(
        isinstance(validation.get("static_tests"), dict)
        and isinstance(validation.get("oracle_tests"), dict)
        and validation.get("ruff") == "pass"
        and validation.get("python_ast") == "pass"
        and validation.get("diff_check") == "pass"
        and validation.get("independent_source_audits") == 2,
        "static source validation failed",
    )
    return {
        "path": str(path),
        "sha256": digest,
        "storage": dict(storage),
        "status": packet["status"],
        "record": dict(record_identity),
        "candidate": {
            "xpu_kernels_commit": source["xpu_kernels_commit"],
            "parent": source["parent"],
            "direct_child_of_record": source["direct_child_of_record"],
            "source_sha256": dict(sorted(source["source_sha256"].items())),
        },
        "build": {
            "artifact_root": build.get("artifact_root"),
            "compiler": build.get("compiler"),
            "binary": {
                "name": binary["name"],
                "sha256": binary["sha256"],
                "imported": binary["imported"],
            },
            "evidence_sha256": dict(sorted(build["evidence_sha256"].items())),
        },
        "device_ir": {
            "report_sha256": proof.get("report_sha256"),
            "report_passed": proof["report_passed"],
            "matching_execution_modes": proof.get("matching_execution_modes"),
            "fused_multiply_add_present": proof["fused_multiply_add_present"],
        },
        "cpu_validation": {
            "ruff": validation["ruff"],
            "python_ast": validation["python_ast"],
            "diff_check": validation["diff_check"],
            "independent_source_audits": validation.get("independent_source_audits"),
        },
    }


def _verify_source_packet(
    record: object,
    *,
    storage_attestor: Callable[[Path], Mapping[str, str]] = _attest_internal_nvme,
) -> dict[str, Any]:
    require(
        isinstance(record, dict) and set(record) == {"path", "sha256"},
        "source packet declaration drift",
    )
    path = _absolute_from_input(record["path"], "source packet")
    require(
        path == SOURCE_PACKET_PATH and record["sha256"] == SOURCE_PACKET_SHA256,
        "source packet identity substitution",
    )
    descriptor, storage = _open_internal_evidence(
        path, "source packet", storage_attestor
    )
    initial = os.fstat(descriptor)
    try:
        packet, raw = _canonical_object_fd(descriptor, str(path))
        result = _verify_source_packet_object(record, packet, raw, storage)
        require(
            _same_metadata(initial, os.fstat(descriptor)),
            "source packet metadata changed during validation",
        )
        _visible_identity_matches(path, descriptor, "source packet")
        return result
    finally:
        os.close(descriptor)


def _verify_fixture_objects(
    record: object,
    *,
    manifest: Mapping[str, Any],
    manifest_raw: bytes,
    analysis: Mapping[str, Any],
    analysis_raw: bytes,
    reanalyzed: Mapping[str, Any],
    storage: Mapping[str, str],
) -> dict[str, Any]:
    require(isinstance(record, dict) and set(record) == {"root", "manifest", "analysis", "analysis_sha256"}, "fixture declaration drift")
    root = _absolute_from_input(record["root"], "fixture root")
    manifest_path = _absolute_from_input(record["manifest"], "fixture manifest")
    analysis_path = _absolute_from_input(record["analysis"], "fixture analysis")
    require(manifest_path.parent == root and analysis_path.parent == root, "fixture root identity drift")
    require(is_sha256(record["analysis_sha256"]), "fixture analysis digest malformed")
    require(
        root == FIXTURE_ROOT
        and manifest_path == FIXTURE_ROOT / "manifest.json"
        and analysis_path == FIXTURE_ROOT / "analysis.json"
        and record["analysis_sha256"] == FIXTURE_ANALYSIS_SHA256,
        "fixture identity substitution",
    )
    require(sha256_bytes(analysis_raw) == record["analysis_sha256"], "fixture analysis digest drift")
    require(sha256_bytes(manifest_raw) == FIXTURE_MANIFEST_SHA256, "fixture manifest identity substitution")
    require(analysis == reanalyzed, "fixture analysis is not an independent current reanalysis")
    require(analysis.get("status") == "passed", "fixture reanalysis did not pass")
    require(analysis.get("manifest_sha256") == sha256_bytes(manifest_raw), "fixture manifest binding drift")
    require(
        manifest.get("format") == FIXTURE_FORMAT
        and manifest.get("production") is True
        and manifest.get("pre_timing_epochs") == 256
        and manifest.get("post_timing_epochs") == 32
        and manifest.get("geometry") == {"tokens": 8, "topk": 10, "hidden": 3072, "ranks": 4},
        "fixture production schema drift",
    )
    tensors = manifest.get("tensors")
    analyzed_tensors = analysis.get("tensors")
    require(isinstance(tensors, dict) and isinstance(analyzed_tensors, dict) and set(tensors) == TENSOR_NAMES == set(analyzed_tensors), "fixture tensor inventory drift")
    epochs = manifest.get("epochs")
    require(type(epochs) is int and epochs == 288, "fixture epoch count drift")
    for name in sorted(TENSOR_NAMES):
        expected, observed = tensors[name], analyzed_tensors[name]
        require(isinstance(expected, dict) and isinstance(observed, dict), "fixture tensor record malformed")
        require(expected.get("sha256") == observed.get("sha256"), f"fixture whole digest drift: {name}")
        require(expected.get("epoch_sha256") == observed.get("epoch_sha256"), f"fixture epoch digest drift: {name}")
        require(isinstance(expected.get("epoch_sha256"), list) and len(expected["epoch_sha256"]) == epochs and all(is_sha256(value) for value in expected["epoch_sha256"]), f"fixture per-epoch proof drift: {name}")
    route_map = manifest.get("canonical_route_map")
    require(
        isinstance(route_map, dict)
        and route_map == {
            "file": "canonical_route_map.int32.le.bin",
            "dtype": "<i4",
            "shape": [8, 10],
            "sha256": route_map.get("sha256"),
            "definition": "arange(80).reshape(8,10)",
        }
        and is_sha256(route_map.get("sha256")),
        "fixture route map proof missing",
    )
    expected_tensor_schema = {
        "route_rows": ("route_rows.uint16.le.bin", "<u2", [288, 80, 3072]),
        "weights": ("weights.uint32.le.bin", "<u4", [288, 8, 10]),
        "scale_add_input": ("scale_add_input.uint16.le.bin", "<u2", [288, 8, 3072]),
        "four_rank_tail": ("four_rank_tail.uint16.le.bin", "<u2", [288, 3, 8, 3072]),
        "residual_input": ("residual_input.uint16.le.bin", "<u2", [288, 8, 3072]),
        "norm_weight": ("norm_weight.uint16.le.bin", "<u2", [288, 3072]),
    }
    require(
        all(
            (tensors[name].get("file"), tensors[name].get("dtype"), tensors[name].get("shape")) == spec
            for name, spec in expected_tensor_schema.items()
        ),
        "fixture tensor dtype or shape drift",
    )
    required_coverage = {
        "all_65536",
        "all_fp32_edge_classes",
        "all_1024_local_zero_masks",
        "all_slots_independently_active",
        "all_local",
        "all_remote_zero",
        "zero_rows_literal_uint16_zero",
        "local_rows_match_formula",
        "canonical_route_map",
        "ordered_cancellation_witness",
        "bf16_midpoint_witness",
    }
    coverage = analysis.get("coverage")
    require(
        isinstance(coverage, dict)
        and all(coverage.get(name) is True for name in required_coverage)
        and coverage.get("uint16_patterns_present") == 65536
        and analysis.get("hashes_match_manifest") is True
        and analysis.get("deterministic_bytes_match") is True,
        "fixture coverage proof drift",
    )
    return {
        "root": str(root),
        "storage": dict(storage),
        "manifest": {"path": str(manifest_path), "sha256": sha256_bytes(manifest_raw)},
        "analysis": {"path": str(analysis_path), "sha256": record["analysis_sha256"]},
        "canonical_route_map": dict(route_map),
        "tensors": {
            name: {
                "file": tensors[name]["file"],
                "dtype": tensors[name]["dtype"],
                "shape": tensors[name]["shape"],
                "sha256": tensors[name]["sha256"],
                "epoch_sha256": tensors[name]["epoch_sha256"],
            }
            for name in sorted(TENSOR_NAMES)
        },
        "independent_reanalysis": {
            "status": analysis["status"],
            "coverage": analysis.get("coverage"),
            "deterministic_bytes_match": analysis.get("deterministic_bytes_match"),
            "hashes_match_manifest": analysis.get("hashes_match_manifest"),
        },
    }


def _verify_fixture(
    record: object,
    *,
    fixture_analyzer: Callable[[Path], Mapping[str, Any]],
    storage_attestor: Callable[[Path], Mapping[str, str]] = _attest_internal_nvme,
) -> dict[str, Any]:
    require(
        isinstance(record, dict)
        and set(record) == {"root", "manifest", "analysis", "analysis_sha256"},
        "fixture declaration drift",
    )
    root = _absolute_from_input(record["root"], "fixture root")
    require(root == FIXTURE_ROOT, "fixture identity substitution")
    root_fd, storage = _open_internal_directory(
        root, "fixture root", storage_attestor
    )
    root_initial = os.fstat(root_fd)
    members: dict[str, int] = {}
    member_initial: dict[str, os.stat_result] = {}
    try:
        require(
            set(os.listdir(root_fd)) == FIXTURE_MEMBER_NAMES,
            "fixture root inventory drift",
        )
        for name in sorted(FIXTURE_MEMBER_NAMES):
            descriptor = os.open(
                name,
                os.O_RDONLY
                | os.O_CLOEXEC
                | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=root_fd,
            )
            members[name] = descriptor
            member_initial[name] = os.fstat(descriptor)
            require(
                stat.S_ISREG(member_initial[name].st_mode)
                and stat.S_IMODE(member_initial[name].st_mode) == 0o444
                and member_initial[name].st_dev == root_initial.st_dev,
                f"fixture member is not an exact 0444 regular file: {name}",
            )
            _visible_member_identity_matches(
                root_fd, name, descriptor, f"fixture member {name}"
            )
        manifest, manifest_raw = _canonical_object_fd(
            members["manifest.json"], str(root / "manifest.json")
        )
        analysis, analysis_raw = _canonical_object_fd(
            members["analysis.json"], str(root / "analysis.json")
        )
        # The existing independent analyzer canonicalizes its root pathname.
        # Therefore this verifier takes the alternative exact-inventory route:
        # root and every member inode stay open and stable across reanalysis,
        # with the visible namespace reconciled before success.
        reanalyzed = dict(fixture_analyzer(root))
        result = _verify_fixture_objects(
            record,
            manifest=manifest,
            manifest_raw=manifest_raw,
            analysis=analysis,
            analysis_raw=analysis_raw,
            reanalyzed=reanalyzed,
            storage=storage,
        )
        require(
            _same_metadata(root_initial, os.fstat(root_fd))
            and set(os.listdir(root_fd)) == FIXTURE_MEMBER_NAMES,
            "fixture root changed during validation",
        )
        _visible_identity_matches(root, root_fd, "fixture root")
        for name, descriptor in members.items():
            require(
                _same_metadata(member_initial[name], os.fstat(descriptor)),
                f"fixture member metadata changed during validation: {name}",
            )
            _visible_member_identity_matches(
                root_fd, name, descriptor, f"fixture member {name}"
            )
        return result
    finally:
        for descriptor in members.values():
            os.close(descriptor)
        os.close(root_fd)


def _verify_operational_object(
    record: object,
    report: Mapping[str, Any],
    raw: bytes,
    live_storage: Mapping[str, str],
) -> dict[str, Any]:
    require(isinstance(record, dict) and set(record) == {"report", "sha256"}, "operational declaration drift")
    path = _absolute_from_input(record["report"], "operational report")
    digest = record["sha256"]
    require(is_sha256(digest), "operational report digest malformed")
    require(
        path == OPERATIONAL_REPORT_PATH and digest == OPERATIONAL_REPORT_SHA256,
        "operational report identity substitution",
    )
    require(sha256_bytes(raw) == digest, "operational report digest drift")
    require(report.get("format") == OPERATIONAL_FORMAT and report.get("status") == "passed", "operational preflight did not pass")
    output = report.get("output")
    require(isinstance(output, dict) and isinstance(output.get("storage"), dict), "operational storage proof missing")
    storage = output["storage"]
    require(storage.get("filesystem") == "ext4" and storage.get("source") == "/dev/nvme0n1p2" and storage.get("major_minor") == "259:2", "operational preflight storage drift")
    require(
        _validate_internal_storage(storage, "operational recorded storage")
        == live_storage,
        "operational recorded storage differs from live FD attestation",
    )
    return {"report": str(path), "sha256": digest, "status": report["status"], "format": report["format"], "storage": dict(live_storage)}


def _verify_operational(
    record: object,
    *,
    storage_attestor: Callable[[Path], Mapping[str, str]] = _attest_internal_nvme,
) -> dict[str, Any]:
    require(
        isinstance(record, dict)
        and set(record) == {"report", "sha256"}
        and record.get("report") == str(OPERATIONAL_REPORT_PATH)
        and record.get("sha256") == OPERATIONAL_REPORT_SHA256,
        "operational report identity substitution",
    )
    path = _absolute_from_input(
        record.get("report") if isinstance(record, dict) else None,
        "operational report",
    )
    descriptor, live_storage = _open_internal_evidence(
        path, "operational report", storage_attestor
    )
    initial = os.fstat(descriptor)
    try:
        report, raw = _canonical_object_fd(
            descriptor, str(path), expected_mode=0o444
        )
        result = _verify_operational_object(record, report, raw, live_storage)
        require(
            _same_metadata(initial, os.fstat(descriptor)),
            "operational report metadata changed during validation",
        )
        _visible_identity_matches(path, descriptor, "operational report")
        return result
    finally:
        os.close(descriptor)


VALIDATOR_BOOTSTRAP = (
    "import runpy,sys;"
    "closure,script=sys.argv[1:3];"
    "sys.path.insert(0,closure);"
    "sys.argv=[script,'--validate-existing'];"
    "runpy.run_path(script,run_name='__main__')"
)
FIXTURE_ANALYZER_BOOTSTRAP = (
    "import json,pathlib,runpy,sys;"
    "script,root=sys.argv[1:3];"
    "namespace=runpy.run_path(script,run_name='sealed_fixture_analyzer');"
    "result=namespace['analyze_existing'](pathlib.Path(root));"
    "print(json.dumps(result,sort_keys=True,separators=(',',':')))"
)


def _sealed_staging_fd(name: str, payload: bytes) -> int:
    """Return a read-only inherited FD with no writable pathname."""
    if hasattr(os, "memfd_create"):
        writable = os.memfd_create(name, getattr(os, "MFD_CLOEXEC", 0))
    else:
        # This inode is unlinked before any content is written.  The child is
        # passed only a read-only duplicate, never its transient pathname.
        writable, transient = tempfile.mkstemp(prefix=f".{name}.")
        os.unlink(transient)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(writable, view)
            require(written > 0, "short sealed staging write")
            view = view[written:]
        os.fsync(writable)
        readonly = os.open(
            f"/proc/self/fd/{writable}", os.O_RDONLY | os.O_CLOEXEC
        )
    finally:
        os.close(writable)
    try:
        require(
            sha256_bytes(_regular_bytes_fd(readonly, f"sealed staging {name}"))
            == sha256_bytes(payload),
            "sealed staging digest drift",
        )
        return readonly
    except BaseException:
        os.close(readonly)
        raise


def _validated_staged_validator_closure(
    tools: Mapping[str, Any],
) -> tuple[int, int, list[dict[str, str]], str]:
    """Freeze the verified local helper closure into read-only anonymous FDs."""
    closure = tools.get("local_helper_closure")
    require(isinstance(closure, list) and closure, "validated helper closure is missing")
    records: dict[str, str] = {}
    tools_relative = TOOLS_DIRECTORY.relative_to(REPOSITORY_ROOT)
    for record in closure:
        require(
            isinstance(record, dict) and set(record) == {"path", "sha256"},
            "validated helper closure schema drift",
        )
        relative, digest = record["path"], record["sha256"]
        require(
            isinstance(relative, str)
            and is_sha256(digest)
            and Path(relative).parent == tools_relative
            and Path(relative).suffix == ".py"
            and relative not in records,
            "validated helper closure member drift",
        )
        records[relative] = digest
    freezer_relative = str(FREEZER.relative_to(REPOSITORY_ROOT))
    operational_relative = str(
        (TOOLS_DIRECTORY / "preflight_laguna_m8_gather_sharded_operational.py").relative_to(
            REPOSITORY_ROOT
        )
    )
    require(
        freezer_relative in records and operational_relative in records,
        "validator helper closure is incomplete",
    )
    # The complete closure remains bound in ``tools``.  This child imports only
    # the freezer and its one direct local helper, so staging unrelated A/B
    # code would create a needless race without strengthening this invocation.
    staged_records = {
        freezer_relative: records[freezer_relative],
        operational_relative: records[operational_relative],
    }
    source: dict[str, bytes] = {}
    for relative, digest in sorted(staged_records.items()):
        path = REPOSITORY_ROOT / relative
        descriptor = os.open(
            path,
            os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            source[relative] = _regular_bytes_fd(descriptor, str(path))
            require(
                sha256_bytes(source[relative]) == digest,
                f"validated helper changed before staging: {relative}",
            )
            _visible_identity_matches(path, descriptor, "validated helper")
        finally:
            os.close(descriptor)
    archive_stream = io.BytesIO()
    with zipfile.ZipFile(
        archive_stream, "w", compression=zipfile.ZIP_STORED, strict_timestamps=True
    ) as archive:
        for relative in sorted(source):
            member = Path(relative).name
            info = zipfile.ZipInfo(member, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o100444 << 16
            archive.writestr(info, source[relative])
    closure_payload = archive_stream.getvalue()
    return (
        _sealed_staging_fd("laguna-stage0-helper-closure", closure_payload),
        _sealed_staging_fd("laguna-stage0-bundle-freezer", source[freezer_relative]),
        [
            {"path": relative, "sha256": staged_records[relative]}
            for relative in sorted(staged_records)
        ],
        sha256_bytes(closure_payload),
    )


def _analyze_fixture_subprocess(
    tools: Mapping[str, Any],
    root: Path,
) -> dict[str, Any]:
    relative = ROLE_PATHS["fixture_preparer"][0]
    closure = tools.get("local_helper_closure")
    require(isinstance(closure, list), "validated helper closure is missing")
    records = {
        item["path"]: item["sha256"]
        for item in closure
        if isinstance(item, dict)
        and set(item) == {"path", "sha256"}
        and isinstance(item.get("path"), str)
        and is_sha256(item.get("sha256"))
    }
    require(relative in records, "fixture analyzer is absent from bound closure")
    path = REPOSITORY_ROOT / relative
    descriptor = os.open(
        path,
        os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        source = _regular_bytes_fd(descriptor, str(path))
        require(
            sha256_bytes(source) == records[relative],
            "fixture analyzer changed before staging",
        )
        _visible_identity_matches(path, descriptor, "fixture analyzer")
    finally:
        os.close(descriptor)
    script_fd = _sealed_staging_fd("laguna-stage0-fixture-analyzer", source)
    try:
        result = _run_pinned_executable(
            PYTHON_EXECUTABLE,
            PYTHON_EXECUTABLE_SHA256,
            "fixture-analyzer Python",
            [
                "-I",
                "-S",
                "-c",
                FIXTURE_ANALYZER_BOOTSTRAP,
                f"/proc/self/fd/{script_fd}",
                str(root),
            ],
            text=True,
            timeout=120,
            cwd=Path("/"),
            environment=SUBPROCESS_ENVIRONMENT,
            extra_fds=(script_fd,),
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("fixture analyzer subprocess timed out") from error
    finally:
        os.close(script_fd)
    require(
        result.returncode == 0 and result.stderr == "",
        "fixture analyzer subprocess failed",
    )
    try:
        value = json.loads(result.stdout)
    except (TypeError, ValueError) as error:
        raise RuntimeError("fixture analyzer did not emit JSON") from error
    require(
        isinstance(value, dict)
        and result.stdout
        == json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        "fixture analyzer output is noncanonical",
    )
    return value


def _validate_bundle_subprocess(
    *,
    tools: Mapping[str, Any],
    storage_attestor: Callable[[Path], Mapping[str, str]] = _attest_internal_nvme,
) -> dict[str, Any]:
    # Check the pinned interpreter before even materializing the trusted
    # anonymous closure; `_run_pinned_executable` opens and pins it again for
    # the actual exec, so this early diagnostic is not the execution authority.
    _assert_pinned_executable(
        PYTHON_EXECUTABLE, PYTHON_EXECUTABLE_SHA256, "bundle-validator Python"
    )
    closure_fd, freezer_fd, closure_records, closure_sha256 = (
        _validated_staged_validator_closure(tools)
    )
    try:
        result = _run_pinned_executable(
            PYTHON_EXECUTABLE,
            PYTHON_EXECUTABLE_SHA256,
            "bundle-validator Python",
            [
                "-I",
                "-S",
                "-c",
                VALIDATOR_BOOTSTRAP,
                f"/proc/self/fd/{closure_fd}",
                f"/proc/self/fd/{freezer_fd}",
            ],
            text=True,
            timeout=30,
            cwd=Path("/"),
            environment=SUBPROCESS_ENVIRONMENT,
            extra_fds=(closure_fd, freezer_fd),
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("native-bundle validation subprocess timed out") from error
    finally:
        os.close(freezer_fd)
        os.close(closure_fd)
    require(
        result.returncode == 0 and result.stderr == "",
        "separate native-bundle validation subprocess failed",
    )
    try:
        value = json.loads(result.stdout)
    except (TypeError, ValueError) as error:
        raise RuntimeError("native-bundle validator did not emit JSON") from error
    require(isinstance(value, dict) and result.stdout == json.dumps(value, sort_keys=True) + "\n", "native-bundle validation output is noncanonical")
    required = {"root", "manifest", "manifest_sha256", "prepared", "prepared_sha256", "library_sha256", "status", "validation_protocol", "storage"}
    require(set(value) == required, "native-bundle validation schema drift")
    require(value.get("status") == "validated_host_only_not_imported", "native bundle is not separately validated")
    require(value.get("validation_protocol") == "separate_successful_validate_existing_invocation_required", "native bundle validation protocol drift")
    expected_libraries = {
        name: record["sha256"] for name, record in sorted(BUNDLE_EXPECTED.items())
    }
    require(value.get("library_sha256") == expected_libraries, "native bundle library proof drift")
    root = Path(value["root"])
    require(
        root == BUNDLE_ROOT
        and root.is_absolute()
        and not root.is_symlink()
        and root.resolve(strict=True) == root
        and value.get("manifest") == str(root / BUNDLE_MANIFEST_NAME)
        and value.get("prepared") == str(root / BUNDLE_PREPARED_NAME),
        "native bundle root identity substitution",
    )
    storage = value.get("storage")
    require(isinstance(storage, dict), "native bundle storage malformed")
    _validate_internal_storage(storage, "native bundle child storage")
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        root_stat = os.fstat(root_fd)
        require(stat.S_ISDIR(root_stat.st_mode) and stat.S_IMODE(root_stat.st_mode) == 0o555, "native bundle root mode drift")
        visible_root = os.stat(root, follow_symlinks=False)
        require((visible_root.st_dev, visible_root.st_ino) == (root_stat.st_dev, root_stat.st_ino), "native bundle root inode drift")
        independently_attested_storage = _validate_internal_storage(
            dict(storage_attestor(Path("/proc/self/fd") / str(root_fd))),
            "independently attested native bundle storage",
        )
        require(
            independently_attested_storage == storage,
            "native bundle child storage differs from independent attestation",
        )
        visible_after_attestation = os.stat(root, follow_symlinks=False)
        require(
            (visible_after_attestation.st_dev, visible_after_attestation.st_ino)
            == (root_stat.st_dev, root_stat.st_ino),
            "native bundle root changed during storage attestation",
        )
        expected_names = BUNDLE_FILENAMES | {BUNDLE_MANIFEST_NAME, BUNDLE_PREPARED_NAME}
        require(set(os.listdir(root_fd)) == expected_names, "native bundle inventory drift")
        libraries: dict[str, dict[str, Any]] = {}
        for name in sorted(BUNDLE_FILENAMES):
            library_raw = _regular_bytes_at(
                root_fd,
                name,
                expected_mode=0o444,
                maximum=256 * 1024 * 1024,
            )
            digest, size = sha256_bytes(library_raw), len(library_raw)
            expected = BUNDLE_EXPECTED[name]
            require(digest == expected["sha256"] == expected_libraries[name], f"native bundle library digest drift: {name}")
            libraries[name] = {
                "role": expected["role"], "source": expected["source"],
                "path": str(root / name), "sha256": digest, "bytes": size, "mode": 0o444,
            }
        manifest, manifest_raw = _canonical_object_at(
            root_fd,
            BUNDLE_MANIFEST_NAME,
        )
        prepared, prepared_raw = _canonical_object_at(
            root_fd,
            BUNDLE_PREPARED_NAME,
        )
        manifest_sha256 = sha256_bytes(manifest_raw)
        prepared_sha256 = sha256_bytes(prepared_raw)
        expected_manifest_libraries = {
            name: {key: libraries[name][key] for key in ("role", "source", "path", "sha256", "bytes")}
            for name in sorted(libraries)
        }
        require(
            manifest
            == {
                "format": BUNDLE_FORMAT,
                "status": "prepared_host_only_not_imported",
                "root": str(root),
                "storage": storage,
                "candidate_kernel_commit": CANDIDATE_KERNELS,
                "approved_record_kernel_commit": RECORD_KERNELS,
                "approved_record_vllm_commit": RECORD_VLLM,
                "libraries": expected_manifest_libraries,
                "actions_not_performed": [
                    "Torch import", "native-library import", "XPU enumeration",
                    "XPU allocation", "XPU primitive", "model load", "generation",
                ],
            },
            "native bundle manifest closure drift",
        )
        require(
            prepared
            == {
                "format": BUNDLE_PREPARED_FORMAT,
                "status": "prepared_requires_separate_validation",
                "root": str(root),
                "manifest_sha256": manifest_sha256,
                "library_sha256": expected_libraries,
            },
            "native bundle prepared closure drift",
        )
        require(
            _same_metadata(root_stat, os.fstat(root_fd)),
            "native bundle root metadata changed during validation",
        )
    finally:
        os.close(root_fd)
    require(value.get("manifest_sha256") == manifest_sha256 and value.get("prepared_sha256") == prepared_sha256, "native bundle child result digest drift")
    return {
        **value,
        "libraries": libraries,
        "validator_process": {
            "python": {
                "path": str(PYTHON_EXECUTABLE),
                "sha256": PYTHON_EXECUTABLE_SHA256,
            },
            "argv": [
                "/proc/self/fd/<retained-pinned-python>",
                "-I",
                "-S",
                "-c",
                f"sha256:{sha256_bytes(VALIDATOR_BOOTSTRAP.encode('utf-8'))}",
                "/proc/self/fd/<sealed-helper-closure>",
                "/proc/self/fd/<sealed-bundle-freezer>",
            ],
            "script_argv": [
                "/proc/self/fd/<sealed-bundle-freezer>",
                "--validate-existing",
            ],
            "cwd": "/",
            "environment": dict(SUBPROCESS_ENVIRONMENT),
            "timeout_seconds": 30,
            "stdout_sha256": sha256_bytes(result.stdout.encode("utf-8")),
            "stderr": "",
            "helper_closure": closure_records,
            "helper_closure_archive_sha256": closure_sha256,
            "execution": "retained-o-nofollow-fd-plus-read-only-anonymous-staging",
        },
    }


def build_certificate(
    declaration: Mapping[str, Any],
    output: Path,
    *,
    input_path: Path,
    fixture_analyzer: Callable[[Path], Mapping[str, Any]] | None = None,
    bundle_validator: Callable[[], dict[str, Any]] = _validate_bundle_subprocess,
    storage_attestor: Callable[[Path], Mapping[str, str]] = _attest_internal_nvme,
    committed_blob_reader: Callable[[str, str], bytes] = _committed_blob,
    commit_verifier: Callable[[str, set[str]], None] = _verify_reachable_clean_commit,
    output_storage: Mapping[str, str] | None = None,
    output_parent_identity: Mapping[str, int] | None = None,
    input_evidence: tuple[bytes, Mapping[str, str]] | None = None,
    retained_evidence: _RetainedBuildEvidence | None = None,
) -> dict[str, Any]:
    """Create one certificate; this function does no accelerator-facing work."""
    require(isinstance(declaration, Mapping), "certificate declaration must be an object")
    require(set(declaration) == {"format", "source_packet", "fixture", "operational_preflight", "tools", "independent_audits"}, "certificate declaration schema drift")
    require(declaration.get("format") == INPUT_FORMAT, "certificate declaration format drift")
    require(input_evidence is None, "legacy detached input evidence is forbidden")
    owns_evidence = retained_evidence is None
    evidence = retained_evidence or _RetainedBuildEvidence(
        declaration, input_path, storage_attestor
    )
    input_raw = evidence.input_raw
    input_storage = evidence.input_storage
    require(input_raw == canonical(dict(declaration)), "certificate declaration bytes drift")
    storage = dict(output_storage) if output_storage is not None else _require_nvme_output(output, storage_attestor)
    parent_identity = dict(output_parent_identity) if output_parent_identity is not None else None
    if parent_identity is None:
        parent_stat = os.stat(output.parent, follow_symlinks=False)
        parent_identity = {"device": parent_stat.st_dev, "inode": parent_stat.st_ino}
    require(set(parent_identity) == {"device", "inode"} and all(type(value) is int and value >= 0 for value in parent_identity.values()), "certificate output parent identity malformed")
    tools = _verify_tool_bindings(declaration["tools"], committed_blob_reader=committed_blob_reader, commit_verifier=commit_verifier)
    source_packet = _verify_source_packet_object(
        declaration["source_packet"],
        evidence.source,
        evidence.source_raw,
        evidence.source_storage,
    )
    reanalyzed = (
        dict(fixture_analyzer(FIXTURE_ROOT))
        if fixture_analyzer is not None
        else _analyze_fixture_subprocess(tools, FIXTURE_ROOT)
    )
    fixture = _verify_fixture_objects(
        declaration["fixture"],
        manifest=evidence.manifest,
        manifest_raw=evidence.manifest_raw,
        analysis=evidence.analysis,
        analysis_raw=evidence.analysis_raw,
        reanalyzed=reanalyzed,
        storage=evidence.fixture_storage,
    )
    operational_preflight = _verify_operational_object(
        declaration["operational_preflight"],
        evidence.operational,
        evidence.operational_raw,
        evidence.operational_storage,
    )
    audits = _verify_independent_audits(
        declaration["independent_audits"],
        source_packet=source_packet,
        tools=tools,
        storage_attestor=storage_attestor,
    )
    # Test doubles remain zero-argument, while the production validator is
    # given the just-verified closure it must stage into descriptor-backed code.
    bundle = (
        bundle_validator(tools=tools)
        if bundle_validator is _validate_bundle_subprocess
        else bundle_validator()
    )
    result = {
        "format": FORMAT,
        "status": "stage0_host_only_complete_pending_packet_commit",
        "input": {
            "path": str(input_path),
            "sha256": sha256_bytes(input_raw),
            "storage": input_storage,
        },
        "declaration": dict(declaration),
        "output": {"path": str(output), "storage": storage, "parent_identity": parent_identity},
        "source_packet": source_packet,
        "fixture": fixture,
        "operational_preflight": operational_preflight,
        "tools": tools,
        "independent_audits": audits,
        "native_bundle": bundle,
        "actions_not_performed_by_this_certificate_invocation": ACTIONS_NOT_PERFORMED,
    }
    evidence.reconcile()
    if owns_evidence:
        evidence.close()
    return result


def freeze_certificate(
    input_path: Path,
    output: Path,
    **kwargs: Any,
) -> dict[str, Any]:
    """Read one canonical declaration and atomically create its certificate."""
    require(
        "input_evidence" not in kwargs,
        "freeze cannot accept caller-supplied retained input evidence",
    )
    storage_attestor = kwargs.get("storage_attestor", _attest_internal_nvme)
    input_fd, input_storage = _open_internal_evidence(
        input_path, "stage0 completion input", storage_attestor
    )
    input_initial = os.fstat(input_fd)
    declaration, input_raw = _canonical_object_fd(
        input_fd, str(input_path), expected_mode=0o444
    )
    evidence = _RetainedBuildEvidence(
        declaration,
        input_path,
        storage_attestor,
        preopened_input=(
            input_fd,
            input_initial,
            input_storage,
            declaration,
            input_raw,
        ),
    )
    parent_fd, storage, identity = _open_output_parent(output, storage_attestor)
    try:
        certificate = build_certificate(
            declaration, output, input_path=input_path,
            output_storage=storage, output_parent_identity=identity,
            retained_evidence=evidence, **kwargs,
        )
        evidence.reconcile()
        _write_exclusive(output, canonical(certificate), parent_fd=parent_fd, parent_identity=identity)
        evidence.reconcile()
        return certificate
    finally:
        os.close(parent_fd)
        evidence.close()


def validate_certificate(
    certificate_path: Path,
    input_path: Path,
    **kwargs: Any,
) -> dict[str, Any]:
    """Rebuild evidence and require byte-for-byte certificate equality."""
    storage_attestor = kwargs.get(
        "storage_attestor", _attest_internal_nvme
    )
    certificate_fd, certificate_storage = _open_internal_evidence(
        certificate_path, "stage0 completion certificate", storage_attestor
    )
    input_fd, input_storage = _open_internal_evidence(
        input_path, "stage0 completion input", storage_attestor
    )
    certificate_initial = os.fstat(certificate_fd)
    input_initial = os.fstat(input_fd)
    try:
        certificate, raw = _canonical_object_fd(
            certificate_fd, str(certificate_path), expected_mode=0o444
        )
        declaration, input_raw = _canonical_object_fd(input_fd, str(input_path))
        retained_input_fd = input_fd
        input_fd = -1
        evidence = _RetainedBuildEvidence(
            declaration,
            input_path,
            storage_attestor,
            preopened_input=(
                retained_input_fd,
                input_initial,
                input_storage,
                declaration,
                input_raw,
            ),
        )
        expected = build_certificate(
            declaration,
            certificate_path,
            input_path=input_path,
            output_storage=certificate_storage,
            retained_evidence=evidence,
            **kwargs,
        )
        require(certificate == expected and raw == canonical(expected), "stage0 completion certificate drift")
        require(
            _same_metadata(certificate_initial, os.fstat(certificate_fd)),
            "stage0 completion certificate metadata changed during validation",
        )
        require(
            _same_metadata(input_initial, os.fstat(evidence._files["stage0 completion input"][1])),
            "stage0 completion input metadata changed during validation",
        )
        _visible_identity_matches(
            certificate_path, certificate_fd, "stage0 completion certificate"
        )
        evidence.reconcile()
        return certificate
    finally:
        if input_fd >= 0:
            os.close(input_fd)
        if "evidence" in locals():
            evidence.close()
        os.close(certificate_fd)


def _validate_certificate_only_retained(
    certificate_path: Path,
    *,
    certificate: Mapping[str, Any],
    raw: bytes,
    certificate_storage: Mapping[str, str],
    declaration: Mapping[str, Any],
    input_raw: bytes,
    input_storage: Mapping[str, str],
    retained_evidence: _RetainedBuildEvidence,
    fixture_analyzer: Callable[[Path], Mapping[str, Any]] | None = None,
    bundle_validator: Callable[[], dict[str, Any]] = _validate_bundle_subprocess,
    storage_attestor: Callable[[Path], Mapping[str, str]] = _attest_internal_nvme,
    committed_blob_reader: Callable[[str, str], bytes] = _committed_blob,
    commit_verifier: Callable[[str, set[str]], None] = _verify_reachable_clean_commit,
) -> dict[str, Any]:
    """Independently validate a sealed certificate without its input declaration.

    Packet validation deliberately needs this entry point: including the
    declaration in a Phase-A/B packet would create an unnecessary second
    authority.  Every certificate section carries its own path/hash closure,
    so the host-only checks can be rebuilt directly from the certificate.
    """
    required = {
        "format",
        "status",
        "input",
        "declaration",
        "output",
        "source_packet",
        "fixture",
        "operational_preflight",
        "tools",
        "native_bundle",
        "independent_audits",
        "actions_not_performed_by_this_certificate_invocation",
    }
    require(set(certificate) == required, "stage0 completion certificate schema drift")
    require(certificate.get("format") == FORMAT, "stage0 completion certificate format drift")
    require(certificate.get("status") == "stage0_host_only_complete_pending_packet_commit", "stage0 completion certificate status drift")
    input_record = certificate.get("input")
    require(
        isinstance(input_record, dict)
        and set(input_record) == {"path", "sha256", "storage"}
        and isinstance(input_record.get("path"), str)
        and is_sha256(input_record.get("sha256")),
        "stage0 completion input binding malformed",
    )
    input_path = _absolute_from_input(input_record["path"], "certificate input")
    require(
        input_record.get("storage") == dict(input_storage),
        "stage0 completion input storage drift",
    )
    require(
        sha256_bytes(input_raw) == input_record["sha256"]
        and declaration.get("format") == INPUT_FORMAT,
        "stage0 completion input closure drift",
    )
    output = certificate.get("output")
    require(isinstance(output, dict) and set(output) == {"path", "storage", "parent_identity"}, "certificate output schema drift")
    require(output.get("path") == str(certificate_path), "certificate output path drift")
    require(output.get("storage") == dict(certificate_storage), "certificate output storage drift")
    parent_stat = os.stat(certificate_path.parent, follow_symlinks=False)
    require(output.get("parent_identity") == {"device": parent_stat.st_dev, "inode": parent_stat.st_ino}, "certificate output parent identity drift")
    require(certificate.get("actions_not_performed_by_this_certificate_invocation") == ACTIONS_NOT_PERFORMED, "certificate actions-not-performed drift")
    expected = build_certificate(
        declaration,
        certificate_path,
        input_path=input_path,
        fixture_analyzer=fixture_analyzer,
        bundle_validator=bundle_validator,
        storage_attestor=storage_attestor,
        committed_blob_reader=committed_blob_reader,
        commit_verifier=commit_verifier,
        output_storage=output["storage"],
        output_parent_identity=output["parent_identity"],
        retained_evidence=retained_evidence,
    )
    require(certificate.get("declaration") == declaration and certificate == expected, "certificate declaration reconciliation drift")
    require(raw == canonical(certificate), "certificate canonical bytes drift")
    return certificate


def validate_certificate_only(
    certificate_path: Path,
    *,
    fixture_analyzer: Callable[[Path], Mapping[str, Any]] | None = None,
    bundle_validator: Callable[[], dict[str, Any]] = _validate_bundle_subprocess,
    storage_attestor: Callable[[Path], Mapping[str, str]] = _attest_internal_nvme,
    committed_blob_reader: Callable[[str, str], bytes] = _committed_blob,
    commit_verifier: Callable[[str, set[str]], None] = _verify_reachable_clean_commit,
) -> dict[str, Any]:
    """Validate while retaining certificate and input inodes until success."""
    certificate_fd, certificate_storage = _open_internal_evidence(
        certificate_path, "stage0 completion certificate", storage_attestor
    )
    certificate_initial = os.fstat(certificate_fd)
    input_fd: int | None = None
    try:
        certificate, raw = _canonical_object_fd(
            certificate_fd, str(certificate_path), expected_mode=0o444
        )
        input_record = certificate.get("input")
        require(
            isinstance(input_record, dict)
            and isinstance(input_record.get("path"), str),
            "stage0 completion input binding malformed",
        )
        input_path = _absolute_from_input(input_record["path"], "certificate input")
        input_fd, input_storage = _open_internal_evidence(
            input_path, "stage0 completion input", storage_attestor
        )
        input_initial = os.fstat(input_fd)
        declaration, input_raw = _canonical_object_fd(input_fd, str(input_path))
        retained_input_fd = input_fd
        input_fd = None
        evidence = _RetainedBuildEvidence(
            declaration,
            input_path,
            storage_attestor,
            preopened_input=(
                retained_input_fd,
                input_initial,
                input_storage,
                declaration,
                input_raw,
            ),
        )
        result = _validate_certificate_only_retained(
            certificate_path,
            certificate=certificate,
            raw=raw,
            certificate_storage=certificate_storage,
            declaration=declaration,
            input_raw=input_raw,
            input_storage=input_storage,
            retained_evidence=evidence,
            fixture_analyzer=fixture_analyzer,
            bundle_validator=bundle_validator,
            storage_attestor=storage_attestor,
            committed_blob_reader=committed_blob_reader,
            commit_verifier=commit_verifier,
        )
        require(
            _same_metadata(certificate_initial, os.fstat(certificate_fd)),
            "stage0 completion certificate metadata changed during validation",
        )
        require(
            _same_metadata(
                input_initial,
                os.fstat(evidence._files["stage0 completion input"][1]),
            ),
            "stage0 completion input metadata changed during validation",
        )
        _visible_identity_matches(
            certificate_path, certificate_fd, "stage0 completion certificate"
        )
        evidence.reconcile()
        return result
    finally:
        if input_fd is not None:
            os.close(input_fd)
        if "evidence" in locals():
            evidence.close()
        os.close(certificate_fd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validate-existing", action="store_true")
    args = parser.parse_args()
    if args.validate_existing:
        certificate = validate_certificate(args.output, args.input)
    else:
        certificate = freeze_certificate(args.input, args.output)
    print(json.dumps(certificate, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
