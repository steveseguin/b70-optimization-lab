#!/usr/bin/env python3
"""Bind the A31 M1-only endpoint to the current default-off source chain."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys


INPUT_SHA256 = "c02056aa5a963dbb6f0916664899cad80a5e2fac050f31c60a713390e0e7a6cd"
OUTPUT_SHA256 = "07863a1e5981f1efbf79e414ef19dbb47c8aba693e404766a99efd021198be56"
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
INNER_LOCKS = """exec 7>/tmp/b70-benchmark.lock
flock -n 7 || fail "host-wide benchmark lock is held"
for gpu in 0 1 2 3; do
  eval "exec $((8 + gpu))>/tmp/b70-gpu${gpu}.lock"
  flock -n "$((8 + gpu))" || fail "GPU ${gpu} lock is held"
done"""
SUPERVISOR_LOCK_ASSERTION = """supervisor_pid=${Q38_A31_SUPERVISOR_PID:-}
[[ "$supervisor_pid" =~ ^[1-9][0-9]*$ ]] || fail "A31 supervisor identity is absent"
expected_supervisor_locks=(/tmp/b70-benchmark.lock /tmp/b70-gpu0.lock /tmp/b70-gpu1.lock /tmp/b70-gpu2.lock /tmp/b70-gpu3.lock)
for lock_index in 0 1 2 3 4; do
  [[ "$(readlink -f "/proc/${supervisor_pid}/fd/$((7 + lock_index))")" == "${expected_supervisor_locks[$lock_index]}" ]] || fail "A31 supervisor lock set changed"
done"""


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
    if (
        source.count(OLD_CHECK) != 1
        or source.count(SERVE) != 1
        or source.count(INNER_LOCKS) != 1
    ):
        raise SystemExit("FAIL: A31 generated source anchors are not unique")

    source = source.replace(OLD_CHECK, workspace_checks())
    source = source.replace(INNER_LOCKS, SUPERVISOR_LOCK_ASSERTION)
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
