#!/usr/bin/env python3
"""Freeze the exact native libraries for the sharded-gather A/B campaigns.

This is a host-only copier.  It never imports Torch or a native extension.
Production paths and digests are intentionally constants so a later
authorization packet can bind one read-only internal-NVMe bundle.
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


def _copy_one(source: Path, destination: Path, expected_sha256: str) -> int:
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
            destination,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_CLOEXEC
            | getattr(os, "O_NOFOLLOW", 0),
            0o400,
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
        os.fsync(destination_fd)
        os.fchmod(destination_fd, 0o444)
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


def _write_manifest(root: Path, value: dict[str, Any]) -> str:
    payload = canonical(value)
    digest = hashlib.sha256(payload).hexdigest()
    descriptor = os.open(
        root / "manifest.json",
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_CLOEXEC
        | getattr(os, "O_NOFOLLOW", 0),
        0o400,
    )
    try:
        _write_all(descriptor, payload)
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o444)
    finally:
        os.close(descriptor)
    return digest


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
    os.mkdir(destination, 0o700)
    root_fd: int | None = None
    try:
        root_fd = os.open(
            destination,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
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
            size = _copy_one(source, destination / name, record["sha256"])
            frozen[name] = {
                "role": record["role"],
                "source": str(source),
                "path": str(destination / name),
                "sha256": record["sha256"],
                "bytes": size,
            }
        manifest = {
            "format": FORMAT,
            "status": "frozen_host_only_not_imported",
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
        manifest_sha256 = _write_manifest(destination, manifest)
        os.fsync(root_fd)
        os.fchmod(root_fd, 0o555)
    except BaseException:
        # Keep any partial fresh root as durable fail-closed evidence.  It must
        # never be repaired or reused as an authorization target.
        if root_fd is not None:
            os.fsync(root_fd)
        raise
    finally:
        if root_fd is not None:
            os.close(root_fd)
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    return {
        "root": str(destination),
        "manifest": str(destination / "manifest.json"),
        "manifest_sha256": manifest_sha256,
        "library_sha256": {
            name: record["sha256"] for name, record in frozen.items()
        },
        "status": "frozen_host_only_not_imported",
    }


def main() -> int:
    summary = freeze(
        DEFAULT_BUNDLE,
        EXPECTED,
        storage_attestor=operational.attest_internal_nvme,
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
