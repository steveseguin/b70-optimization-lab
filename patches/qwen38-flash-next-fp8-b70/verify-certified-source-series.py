#!/usr/bin/env python3
"""Verify the certified Qwen3.8 Flash-Next source patch sequences.

The verifier is offline and build-free. It clones the supplied repositories
into a temporary directory, applies only the declared production patches, and
asserts the exact resulting Git tree objects.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import tempfile
from pathlib import Path


PACKET_ROOT = Path(__file__).resolve().parent
VLLM_BASE = "76cfe1cd88d30d525eec8be5bff75f8b77471c88"
VLLM_TREE = "31ebb7785df4686df1ef03b0f4ef56b660022a06"
KERNEL_BASE = "0fd18a7c08a64d2645bf083cfa5576200b61b02c"
KERNEL_TREE = "d8c4318a0f0d71c3c36867253ad92b377906fec9"

VLLM_PATCHES = (
    "0001-Merge-02f2b4c15dd987d9436e125aab29604447c77405-into-.patch",
    "0002-support-PLE-Offload-for-Qwen3.8-Flash-Next.patch",
    "0003-Support-eager-PLE-offload-transport-on-XPU.patch",
    "0004-Enable-Qwen4Exp-model-dispatch-on-XPU.patch",
    "0005-Add-Qwen4Exp-XPU-hyperconnection-fallbacks.patch",
    "0006-Enable-Qwen4Exp-QSA-kernels-on-XPU.patch",
    "0007-Fix-PLE-target-device-selection-across-accelerators.patch",
    "0008-Restore-weight-skip-filters-for-Qwen4Exp.patch",
    "0009-Port-QSA-compressed-cache-to-tokens-per-state.patch",
    "0010-Avoid-copying-uninitialized-PLE-weights-during-offlo.patch",
    "0012-Allow-selective-UVA-offload-of-Qwen4Exp-embeddings.patch",
    "0014-Normalize-QSA-caches-from-logical-layout.patch",
    "0015-Support-legacy-XPU-GDN-ABI-for-target-decode.patch",
    "0016-Fail-closed-on-XPU-GDN-schema-mismatches.patch",
    "0017-Port-Qwen4Exp-MTP-tests-to-tokens-per-state-cache-AP.patch",
    "0018-Route-legacy-XPU-GDN-speculative-decode.patch",
)

KERNEL_PATCHES = (
    (
        "40683a39dbe9ef9db42f1432e243c52b98889531",
        "73d138249b8df4b02e2d59f14d1a86d3de241ef13ea275cb2794b0c96c2fb3cb",
        "0001-40683a39-restore-architecture-probe-bindings.patch",
    ),
    (
        "1b0e26a8e927e6d6316c06066381b306519b24a4",
        "80b6d67625c551a8e0ddb05de3e61558609dbdcf68db47c34350f1684106531a",
        "0002-1b0e26a8-restore-local-MoE-prologue-source.patch",
    ),
    (
        "7b7a6769cfddae1a4001fbffc6b5743fcbd8a980",
        "7122914a3eca012a1d1942bfe5b5f07f2958965f464d88d25b92c7bf62036e73",
        "0003-7b7a6769-include-fused-quant-implementations.patch",
    ),
    (
        "c694d2f28247cec0b4389c273b8012d96dbf89ac",
        "0bec3da2d6d1364d79a6b69b71f59fc67e5935249b679f980e7aea7562ca4f94",
        "0004-c694d2f2-link-core-memory-info-implementation.patch",
    ),
    (
        "49002d71134e614f905f02e37250ca86e9d97455",
        "3007c7ff02fda5fbaecb616fc800507ae1410ca33fa0c62da805c791d5b6d68e",
        "0005-49002d71-restore-registered-core-implementations.patch",
    ),
    (
        "7cf216774fb3c5eabf20d1f481d6548682604c37",
        "63a430a537aec3574c8a9ff3a238d19ea94920352df0f7114471852e2eb71689",
        "0006-7cf21677-link-core-host-registration-to-Level-Zero.patch",
    ),
    (
        "2f829747503c77d4814834dffd0840fb1dd9f75a",
        "c419d747dae949179281c072bb529d67a3939e077a4e9a78b859c56750100eeb",
        "0007-2f829747-ignore-padding-sentinels-during-alignment.patch",
    ),
)


class VerificationError(RuntimeError):
    pass


def run(*args: str, cwd: Path | None = None, capture: bool = False) -> str:
    completed = subprocess.run(
        args,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    if completed.returncode:
        details = (completed.stderr or completed.stdout or "").strip()
        raise VerificationError(
            f"command failed ({completed.returncode}): {' '.join(args)}"
            + (f"\n{details}" if details else "")
        )
    return completed.stdout.strip() if capture else ""


def require_source(path: Path, commit: str, label: str) -> Path:
    source = path.resolve(strict=True)
    if (
        run("git", "rev-parse", "--is-inside-work-tree", cwd=source, capture=True)
        != "true"
    ):
        raise VerificationError(f"{label} is not a Git worktree: {source}")
    run("git", "cat-file", "-e", f"{commit}^{{commit}}", cwd=source, capture=True)
    return source


def fresh_clone(source: Path, destination: Path, base: str) -> None:
    run(
        "git",
        "clone",
        "--quiet",
        "--shared",
        "--no-checkout",
        "--",
        str(source),
        str(destination),
    )
    run("git", "checkout", "--quiet", "--detach", base, cwd=destination)


def apply_and_assert(
    worktree: Path, patches: tuple[Path, ...], expected_tree: str
) -> str:
    for patch in patches:
        if not patch.is_file():
            raise VerificationError(f"missing patch: {patch}")
        run("git", "apply", "--check", "--index", str(patch), cwd=worktree)
        run("git", "apply", "--index", str(patch), cwd=worktree)
    run("git", "diff", "--cached", "--check", cwd=worktree)
    actual = run("git", "write-tree", cwd=worktree, capture=True)
    if actual != expected_tree:
        raise VerificationError(
            f"tree mismatch: expected {expected_tree}, got {actual}"
        )
    return actual


def verify_kernel_patch_bytes(patch_root: Path) -> tuple[Path, ...]:
    expected_names = [entry[2] for entry in KERNEL_PATCHES]
    actual_names = sorted(path.name for path in patch_root.glob("*.patch"))
    if actual_names != expected_names:
        raise VerificationError(
            f"kernel patch inventory mismatch: expected {expected_names}, got {actual_names}"
        )
    expected_manifest = [
        f"{expected_sha256}  {name}"
        for _commit, expected_sha256, name in KERNEL_PATCHES
    ]
    actual_manifest = (patch_root / "series.sha256").read_text().splitlines()
    if actual_manifest != expected_manifest:
        raise VerificationError("kernel series.sha256 order or contents mismatch")
    result: list[Path] = []
    for commit, expected_sha256, name in KERNEL_PATCHES:
        path = patch_root / name
        payload = path.read_bytes()
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if actual_sha256 != expected_sha256:
            raise VerificationError(
                f"SHA-256 mismatch for {name}: expected {expected_sha256}, got {actual_sha256}"
            )
        first_line = payload.splitlines()[0].decode("ascii")
        if first_line != f"From {commit} Mon Sep 17 00:00:00 2001":
            raise VerificationError(f"commit identity mismatch in {name}: {first_line}")
        result.append(path)
    return tuple(result)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vllm-source", type=Path, required=True)
    parser.add_argument("--kernel-source", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    vllm_source = require_source(args.vllm_source, VLLM_BASE, "vLLM source")
    kernel_source = require_source(args.kernel_source, KERNEL_BASE, "kernel source")
    vllm_patches = tuple(PACKET_ROOT / "vllm" / name for name in VLLM_PATCHES)
    kernel_patches = verify_kernel_patch_bytes(
        PACKET_ROOT / "vllm-xpu-kernels-certified-2f829747"
    )

    with tempfile.TemporaryDirectory(prefix="qwen38-source-verify-") as temporary:
        temporary_root = Path(temporary)
        vllm_worktree = temporary_root / "vllm"
        kernel_worktree = temporary_root / "vllm-xpu-kernels"
        fresh_clone(vllm_source, vllm_worktree, VLLM_BASE)
        fresh_clone(kernel_source, kernel_worktree, KERNEL_BASE)
        vllm_tree = apply_and_assert(vllm_worktree, vllm_patches, VLLM_TREE)
        kernel_tree = apply_and_assert(kernel_worktree, kernel_patches, KERNEL_TREE)

    print(f"PASS vLLM base={VLLM_BASE} tree={vllm_tree} patches={len(vllm_patches)}")
    print(
        f"PASS kernels base={KERNEL_BASE} tree={kernel_tree} patches={len(kernel_patches)}"
    )
    print("PASS certified source reconstruction; builds and GPU access not performed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, VerificationError) as error:
        raise SystemExit(f"FAIL: {error}") from error
