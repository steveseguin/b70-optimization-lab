#!/usr/bin/env python3
"""Bind the A31 M1-only endpoint to the current default-off source chain."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys


INPUT_SHA256 = "c02056aa5a963dbb6f0916664899cad80a5e2fac050f31c60a713390e0e7a6cd"
OUTPUT_SHA256 = "6fe2ffb28e60706bd7ad814fe0cb57752b8b4f0df27ad50d033880f77a424e0c"
SEALED_KERNEL_HEAD = "ad25aa9f69a2171612b9c6b83dfa82c69559f9e4"
WORKSPACE_CHAIN = (
    "359466a262489bdf4e1774e3572202dc82a00718",
    "a6ee94fd8fadb97dc033921f1019ef18f14d5dd0",
    "042c6e877b667f03087091ce3ab58b80903afc20",
    "eeee7d671abfa964626baa18da2174bb92cac80a",
    "e421889999bc1e5a5f11044d14548b9afdba644d",
)
WORKSPACE_HEAD = WORKSPACE_CHAIN[-1]

OLD_CHECK = (
    '[[ "$(git -C "${kernels_src}" rev-parse HEAD)" == '
    '"${expected_kernels_head}" ]] || fail "kernel overlay head changed"'
)
SERVE = 'setsid "${vllm_bin}" serve "${args[@]}" >"${server_log}" 2>&1 &'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def workspace_checks() -> str:
    checks = [
        f'[[ "$(git -C "${{kernels_src}}" rev-parse HEAD)" == "{WORKSPACE_HEAD}" ]] '
        '|| fail "kernel workspace head changed"'
    ]
    for distance, expected in enumerate(reversed(WORKSPACE_CHAIN[:-1]), start=1):
        checks.append(
            f'[[ "$(git -C "${{kernels_src}}" rev-parse HEAD~{distance})" == '
            f'"{expected}" ]] || fail "kernel workspace descendant chain changed"'
        )
    checks.append(
        '[[ "$(git -C "${kernels_src}" rev-parse HEAD~5)" == '
        '"${expected_kernels_head}" ]] || fail "kernel workspace sealed parent changed"'
    )
    return "\n".join(checks)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: rewrite-a31-current-source-contract.py PATH")
    path = Path(sys.argv[1])
    original = path.read_bytes()
    actual_input = digest(original)
    if actual_input != INPUT_SHA256:
        raise SystemExit(
            f"FAIL: A31 generated input is {actual_input}, expected {INPUT_SHA256}"
        )
    source = original.decode("utf-8")
    if source.count(OLD_CHECK) != 1 or source.count(SERVE) != 1:
        raise SystemExit("FAIL: A31 generated source anchors are not unique")

    source = source.replace(OLD_CHECK, workspace_checks())
    pre_serve = "\n".join(
        (
            f'[[ "$(git -C "${{kernels_src}}" rev-parse HEAD)" == "{WORKSPACE_HEAD}" ]] '
            '|| fail "kernel workspace changed immediately before launch"',
            '[[ -z "$(git -C "${kernels_src}" status --porcelain '
            '--untracked-files=no)" ]] || fail "kernel workspace became dirty '
            'immediately before launch"',
            '[[ -z "${VLLM_XPU_QWEN4_EXP_HC_GROUPED_UP+x}" ]] || fail '
            '"grouped-HC selector must remain unset"',
        )
    )
    source = source.replace(SERVE, f"{pre_serve}\n{SERVE}")
    transformed = source.encode("utf-8")
    actual_output = digest(transformed)
    if actual_output != OUTPUT_SHA256:
        raise SystemExit(
            f"FAIL: A31 generated output is {actual_output}, expected {OUTPUT_SHA256}"
        )
    temporary = path.with_name(f"{path.name}.workspace.{os.getpid()}")
    temporary.write_bytes(transformed)
    os.chmod(temporary, 0o700)
    os.replace(temporary, path)


if __name__ == "__main__":
    main()
