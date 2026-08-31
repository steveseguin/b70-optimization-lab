#!/usr/bin/env python3
"""Separate A29's live kernel workspace from its sealed runtime identity."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys


INPUT_SHA256 = "8909a33733ceb9196527abc698cee73e5b1441ca5c59bb44964e71143b329b06"
OUTPUT_SHA256 = "37791a9b20d0ce0d10e89f3930f9d0e8b7d7f743e1074691b39ed22a40e6adbb"
WORKSPACE_HEAD = "359466a262489bdf4e1774e3572202dc82a00718"

OLD_CHECK = (
    '[[ "$(git -C "${kernels_src}" rev-parse HEAD)" == '
    '"${expected_kernels_head}" ]] || fail "kernel overlay head changed"'
)
NEW_CHECK = "\n".join(
    (
        f'[[ "$(git -C "${{kernels_src}}" rev-parse HEAD)" == "{WORKSPACE_HEAD}" ]] '
        '|| fail "kernel workspace head changed"',
        '[[ "$(git -C "${kernels_src}" rev-parse HEAD^)" == '
        '"${expected_kernels_head}" ]] || fail "kernel workspace is not the exact '
        'default-off child of the sealed runtime source"',
    )
)
SERVE = 'setsid "${vllm_bin}" serve "${args[@]}" >"${server_log}" 2>&1 &'
PRE_SERVE = "\n".join(
    (
        f'[[ "$(git -C "${{kernels_src}}" rev-parse HEAD)" == "{WORKSPACE_HEAD}" ]] '
        '|| fail "kernel workspace changed immediately before launch"',
        '[[ -z "$(git -C "${kernels_src}" status --porcelain '
        '--untracked-files=no)" ]] || fail "kernel workspace became dirty immediately '
        'before launch"',
    )
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: rewrite-a29-kernel-workspace-contract.py PATH")
    path = Path(sys.argv[1])
    original = path.read_bytes()
    actual_input = digest(original)
    if actual_input != INPUT_SHA256:
        raise SystemExit(
            f"FAIL: A29 generated input is {actual_input}, expected {INPUT_SHA256}"
        )
    source = original.decode("utf-8")
    if source.count(OLD_CHECK) != 1 or source.count(SERVE) != 1:
        raise SystemExit("FAIL: A29 generated source anchors are not unique")
    source = source.replace(OLD_CHECK, NEW_CHECK)
    source = source.replace(SERVE, f"{PRE_SERVE}\n{SERVE}")
    transformed = source.encode("utf-8")
    actual_output = digest(transformed)
    if actual_output != OUTPUT_SHA256:
        raise SystemExit(
            f"FAIL: A29 generated output is {actual_output}, expected {OUTPUT_SHA256}"
        )
    temporary = path.with_name(f"{path.name}.workspace.{os.getpid()}")
    temporary.write_bytes(transformed)
    os.chmod(temporary, 0o700)
    os.replace(temporary, path)


if __name__ == "__main__":
    main()
