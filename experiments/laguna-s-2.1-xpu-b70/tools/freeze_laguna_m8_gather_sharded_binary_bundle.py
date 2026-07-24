#!/usr/bin/env python3
"""Prepare and independently validate the sharded-gather native bundle.

This is a host-only copier.  It never imports Torch or a native extension.
Production paths and digests are intentionally constants so a later
authorization packet can bind one read-only internal-NVMe bundle.

Preparation and validation are deliberately separate invocations.  A prepare
invocation can fail after its final visible write but before a durability
operation reports success.  Such a root remains *prepared*, never authorized.
Only a later successful ``--validate-existing`` invocation, recorded before
the packet-only commit, makes the root eligible for packet binding.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any, Callable

import preflight_laguna_m8_gather_sharded_operational as operational


ARTIFACT_ROOT = Path(
    "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1"
)
BINARY_PARENT = ARTIFACT_ROOT / "binaries"
DEFAULT_BUNDLE = (
    BINARY_PARENT
    / "gather-sharded-phase-ab-7e6a740-20260724T1104Z"
)
FORMAT = "laguna-m8-gather-sharded-native-bundle-v1"
PREPARED_FORMAT = "laguna-m8-gather-sharded-native-bundle-prepared-v1"
MANIFEST_NAME = "manifest.json"
PREPARED_NAME = "bundle-prepared.json"
EXPECTED = {
    "shared-_C.abi3.so": {
        "role": "approved_record_shared_ops",
        "source": (
            "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/"
            "vllm_xpu_kernels/_C.abi3.so"
        ),
        "sha256": (
            "126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2"
        ),
    },
    "shared-_xpu_C.abi3.so": {
        "role": "approved_record_rank_sum",
        "source": (
            "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/"
            "vllm_xpu_kernels/_xpu_C.abi3.so"
        ),
        "sha256": (
            "f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8"
        ),
    },
    "candidate-_moe_C.abi3.so": {
        "role": "standalone_sharded_gather_control_and_candidate",
        "source": (
            "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/"
            "binaries/gather-sharded-7e6a740-20260724/_moe_C.abi3.so"
        ),
        "sha256": (
            "3a16e85f7b6f324246f89e03d8aa89c37f0d6097c59d0a323ab2822dccd6d99f"
        ),
    },
    "libgdn_attn_kernels_xe_2.so": {
        "role": "required_xpu_module_dependency",
        "source": (
            "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/"
            "vllm_xpu_kernels/libgdn_attn_kernels_xe_2.so"
        ),
        "sha256": (
            "cdcf9539ac1715ef1dd9a81df422dd5bc1f3a58eff93e1bc5bde05959b5d34bb"
        ),
    },
    "libgrouped_gemm_xe_2.so": {
        "role": "required_xpu_module_dependency",
        "source": (
            "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/"
            "vllm_xpu_kernels/libgrouped_gemm_xe_2.so"
        ),
        "sha256": (
            "fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96"
        ),
    },
    "libgrouped_gemm_xe_default.so": {
        "role": "required_xpu_module_dependency",
        "source": (
            "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/"
            "vllm_xpu_kernels/libgrouped_gemm_xe_default.so"
        ),
        "sha256": (
            "982fb0b7fc96c877aaefa33f3342936af9403ed3960106dececf08697d98d53c"
        ),
    },
    "libmhc_kernels_xe_2.so": {
        "role": "required_xpu_module_dependency",
        "source": (
            "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/"
            "vllm_xpu_kernels/libmhc_kernels_xe_2.so"
        ),
        "sha256": (
            "f689c3d200731167394c387d267df90311fd5ec21eff9dededb619e871ce1a4f"
        ),
    },
    "libmqa_logits_kernels_xe_2.so": {
        "role": "required_xpu_module_dependency",
        "source": (
            "/home/steve/src/deepseek-v4-xpu-kernels-mwidth-mhc/"
            "vllm_xpu_kernels/libmqa_logits_kernels_xe_2.so"
        ),
        "sha256": (
            "58cca1a0507914762b36874d719557715f3a8ae045106bc0aed42bd16e5b6aeb"
        ),
    },
}
BUNDLE_FILENAMES = frozenset(EXPECTED)


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        require(written > 0, "short bundle write")
        view = view[written:]


def _copy_one(
    source: Path,
    root_fd: int,
    destination_name: str,
    expected_sha256: str,
) -> int:
    require(_is_sha256(expected_sha256), "malformed expected library digest")
    require(source.is_absolute(), "library source must be absolute")
    source_fd = os.open(
        source,
        os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
    )
    destination_fd: int | None = None
    try:
        source_stat = os.fstat(source_fd)
        require(stat.S_ISREG(source_stat.st_mode), "library source is not regular")
        require(source_stat.st_size > 0, "library source is empty")
        destination_fd = os.open(
            destination_name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_CLOEXEC
            | getattr(os, "O_NOFOLLOW", 0),
            0o400,
            dir_fd=root_fd,
        )
        digest = hashlib.sha256()
        copied = 0
        while True:
            block = os.read(source_fd, 1024 * 1024)
            if not block:
                break
            digest.update(block)
            _write_all(destination_fd, block)
            copied += len(block)
        require(copied == source_stat.st_size, "library changed or copied short")
        require(
            digest.hexdigest() == expected_sha256,
            f"library source digest drift: {source}",
        )
        os.fchmod(destination_fd, 0o444)
        os.fsync(destination_fd)
        destination_stat = os.fstat(destination_fd)
        require(
            stat.S_ISREG(destination_stat.st_mode)
            and destination_stat.st_size == source_stat.st_size,
            "frozen library metadata drift",
        )
        return copied
    finally:
        if destination_fd is not None:
            os.close(destination_fd)
        os.close(source_fd)


def _write_read_only_at(
    root_fd: int,
    name: str,
    payload: bytes,
) -> str:
    digest = hashlib.sha256(payload).hexdigest()
    descriptor = os.open(
        name,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_CLOEXEC
        | getattr(os, "O_NOFOLLOW", 0),
        0o400,
        dir_fd=root_fd,
    )
    try:
        _write_all(descriptor, payload)
        os.fchmod(descriptor, 0o444)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return digest


def _hash_regular_at(
    root_fd: int,
    name: str,
    *,
    expected_mode: int,
) -> tuple[str, int]:
    descriptor = os.open(
        name,
        os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=root_fd,
    )
    try:
        metadata = os.fstat(descriptor)
        require(stat.S_ISREG(metadata.st_mode), f"bundle member is not regular: {name}")
        require(
            stat.S_IMODE(metadata.st_mode) == expected_mode,
            f"bundle member mode drift: {name}",
        )
        digest = hashlib.sha256()
        size = 0
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            digest.update(block)
            size += len(block)
        require(size == metadata.st_size, f"bundle member changed while read: {name}")
        return digest.hexdigest(), size
    finally:
        os.close(descriptor)


def _read_canonical_at(root_fd: int, name: str) -> tuple[dict[str, Any], bytes]:
    descriptor = os.open(
        name,
        os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=root_fd,
    )
    try:
        metadata = os.fstat(descriptor)
        require(
            stat.S_ISREG(metadata.st_mode)
            and stat.S_IMODE(metadata.st_mode) == 0o444
            and metadata.st_size <= 1024 * 1024,
            f"unsafe bundle metadata file: {name}",
        )
        raw = os.read(descriptor, metadata.st_size + 1)
        require(len(raw) == metadata.st_size, f"short bundle metadata read: {name}")
    finally:
        os.close(descriptor)
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"invalid bundle metadata JSON: {name}") from error
    require(
        isinstance(value, dict) and raw == canonical(value),
        f"noncanonical bundle metadata: {name}",
    )
    return value, raw


def _validate_storage(storage: dict[str, str]) -> None:
    require(
        isinstance(storage, dict)
        and storage.get("filesystem") == "ext4"
        and storage.get("source") == "/dev/nvme0n1p2"
        and storage.get("major_minor") == "259:2"
        and isinstance(storage.get("sysfs_device"), str)
        and any(
            part.startswith("nvme")
            for part in Path(storage["sysfs_device"]).parts
        ),
        "bundle storage is not the frozen internal NVMe",
    )


def validate_bundle(
    root: Path,
    entries: dict[str, dict[str, str]],
    *,
    storage_attestor: Callable[[Path], dict[str, str]],
) -> dict[str, Any]:
    """Reopen and fully validate one completed production bundle."""
    require(root.is_absolute() and not root.is_symlink(), "unsafe bundle root")
    resolved = root.resolve(strict=True)
    require(
        resolved == root
        and resolved.parent == BINARY_PARENT.resolve(strict=True),
        "bundle root identity drift",
    )
    storage = storage_attestor(resolved)
    _validate_storage(storage)
    root_fd = os.open(
        resolved,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        metadata = os.fstat(root_fd)
        require(
            stat.S_ISDIR(metadata.st_mode)
            and stat.S_IMODE(metadata.st_mode) == 0o555,
            "completed bundle root mode drift",
        )
        expected_names = BUNDLE_FILENAMES | {MANIFEST_NAME, PREPARED_NAME}
        require(set(os.listdir(root_fd)) == expected_names, "bundle inventory drift")
        observed: dict[str, dict[str, Any]] = {}
        for name in sorted(BUNDLE_FILENAMES):
            digest, size = _hash_regular_at(root_fd, name, expected_mode=0o444)
            require(
                digest == entries[name]["sha256"],
                f"completed bundle digest drift: {name}",
            )
            observed[name] = {"sha256": digest, "bytes": size}
        manifest, manifest_raw = _read_canonical_at(root_fd, MANIFEST_NAME)
        prepared, prepared_raw = _read_canonical_at(root_fd, PREPARED_NAME)
        manifest_sha256 = hashlib.sha256(manifest_raw).hexdigest()
        prepared_sha256 = hashlib.sha256(prepared_raw).hexdigest()
        expected_libraries = {
            name: {
                    "role": entries[name]["role"],
                    "source": entries[name]["source"],
                    "path": str(root / name),
                    "sha256": entries[name]["sha256"],
                    "bytes": observed[name]["bytes"],
                }
            for name in sorted(BUNDLE_FILENAMES)
        }
        require(
            manifest
            == {
                "format": FORMAT,
                "status": "prepared_host_only_not_imported",
                "root": str(root),
                "storage": storage,
                "candidate_kernel_commit": (
                    "7e6a74026a2a4370abcb7973d28bbc9d1ddd1be6"
                ),
                "approved_record_kernel_commit": (
                    "b6076ce1249ffee0e30bee528f4cd15c3bffb234"
                ),
                "approved_record_vllm_commit": (
                    "8936aac144929190c1e53f8b8624ca397ce16f5b"
                ),
                "libraries": expected_libraries,
                "actions_not_performed": [
                    "Torch import",
                    "native-library import",
                    "XPU enumeration",
                    "XPU allocation",
                    "XPU primitive",
                    "model load",
                    "generation",
                ],
            },
            "bundle manifest identity drift",
        )
        require(
            prepared
            == {
                "format": PREPARED_FORMAT,
                "status": "prepared_requires_separate_validation",
                "root": str(root),
                "manifest_sha256": manifest_sha256,
                "library_sha256": {
                    name: entries[name]["sha256"]
                    for name in sorted(BUNDLE_FILENAMES)
                },
            },
            "bundle prepared marker drift",
        )
        return {
            "root": str(root),
            "manifest": str(root / MANIFEST_NAME),
            "manifest_sha256": manifest_sha256,
            "prepared": str(root / PREPARED_NAME),
            "prepared_sha256": prepared_sha256,
            "library_sha256": {
                name: entries[name]["sha256"]
                for name in sorted(BUNDLE_FILENAMES)
            },
            "status": "validated_host_only_not_imported",
            "validation_protocol": (
                "separate_successful_validate_existing_invocation_required"
            ),
            "storage": storage,
        }
    finally:
        os.close(root_fd)


def freeze(
    destination: Path,
    entries: dict[str, dict[str, str]],
    *,
    storage_attestor: Callable[[Path], dict[str, str]],
) -> dict[str, Any]:
    """Create one fresh bundle and return its canonical manifest summary."""
    require(destination.is_absolute(), "bundle path must be absolute")
    parent = destination.parent.resolve(strict=True)
    require(
        parent == BINARY_PARENT.resolve(strict=True),
        "bundle must be an immediate child of the frozen binary parent",
    )
    require(not destination.exists() and not destination.is_symlink(), "bundle exists")
    require(set(entries) == BUNDLE_FILENAMES, "native bundle filename inventory drift")
    storage = storage_attestor(parent)
    _validate_storage(storage)
    parent_fd = os.open(
        parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    root_fd: int | None = None
    created = False
    try:
        parent_path_stat = os.stat(parent, follow_symlinks=False)
        parent_fd_stat = os.fstat(parent_fd)
        require(
            stat.S_ISDIR(parent_path_stat.st_mode)
            and (parent_path_stat.st_dev, parent_path_stat.st_ino)
            == (parent_fd_stat.st_dev, parent_fd_stat.st_ino),
            "bundle parent identity changed",
        )
        os.mkdir(destination.name, 0o700, dir_fd=parent_fd)
        created = True
        os.fsync(parent_fd)
        root_fd = os.open(
            destination.name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
        frozen: dict[str, dict[str, Any]] = {}
        for name in sorted(entries):
            record = entries[name]
            require(
                isinstance(record, dict)
                and set(record) == {"role", "source", "sha256"}
                and isinstance(record["role"], str)
                and record["role"],
                f"bundle source schema drift: {name}",
            )
            source = Path(record["source"])
            size = _copy_one(source, root_fd, name, record["sha256"])
            frozen[name] = {
                "role": record["role"],
                "source": str(source),
                "path": str(destination / name),
                "sha256": record["sha256"],
                "bytes": size,
            }
        manifest = {
            "format": FORMAT,
            "status": "prepared_host_only_not_imported",
            "root": str(destination),
            "storage": storage,
            "candidate_kernel_commit": (
                "7e6a74026a2a4370abcb7973d28bbc9d1ddd1be6"
            ),
            "approved_record_kernel_commit": (
                "b6076ce1249ffee0e30bee528f4cd15c3bffb234"
            ),
            "approved_record_vllm_commit": (
                "8936aac144929190c1e53f8b8624ca397ce16f5b"
            ),
            "libraries": frozen,
            "actions_not_performed": [
                "Torch import",
                "native-library import",
                "XPU enumeration",
                "XPU allocation",
                "XPU primitive",
                "model load",
                "generation",
            ],
        }
        manifest_sha256 = _write_read_only_at(
            root_fd,
            MANIFEST_NAME,
            canonical(manifest),
        )
        prepared = {
            "format": PREPARED_FORMAT,
            "status": "prepared_requires_separate_validation",
            "root": str(destination),
            "manifest_sha256": manifest_sha256,
            "library_sha256": {
                name: record["sha256"]
                for name, record in sorted(frozen.items())
            },
        }
        _write_read_only_at(root_fd, PREPARED_NAME, canonical(prepared))
        os.fsync(root_fd)
        os.fchmod(root_fd, 0o555)
        os.fsync(root_fd)
        os.fsync(parent_fd)
    except BaseException:
        # Keep any partial fresh root as durable fail-closed evidence.  It must
        # never be repaired or reused as an authorization target.
        if root_fd is not None:
            os.fsync(root_fd)
        if created:
            os.fsync(parent_fd)
        raise
    finally:
        if root_fd is not None:
            os.close(root_fd)
        os.close(parent_fd)
    return {
        "root": str(destination),
        "manifest": str(destination / MANIFEST_NAME),
        "manifest_sha256": manifest_sha256,
        "prepared": str(destination / PREPARED_NAME),
        "prepared_sha256": hashlib.sha256(canonical(prepared)).hexdigest(),
        "library_sha256": {
            name: entries[name]["sha256"] for name in sorted(BUNDLE_FILENAMES)
        },
        "status": "prepared_requires_separate_validation",
        "next_required": "run --validate-existing in a new process",
        "storage": storage,
    }


def main() -> int:
    validate_only = "--validate-existing" in sys.argv[1:]
    require(
        sys.argv[1:] in ([], ["--validate-existing"]),
        "only the fixed production prepare or --validate-existing is allowed",
    )
    if validate_only:
        summary = validate_bundle(
            DEFAULT_BUNDLE,
            EXPECTED,
            storage_attestor=operational.attest_internal_nvme,
        )
    else:
        summary = freeze(
            DEFAULT_BUNDLE,
            EXPECTED,
            storage_attestor=operational.attest_internal_nvme,
        )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
