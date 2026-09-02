#!/usr/bin/env python3
"""Create the A61 bundled-oneCCL control packet from frozen A60.

A60 (no graph) reproduced the A59 first-step jitter, so the graph is not the
source. A61 keeps A60's identity (eager, tuned M1 W13-N32 map, external
checkpoint, PLE-only UVA placement, 2304 max model length, chunked prefill,
Torch trace, host guards) and removes only the public oneCCL selection: the
`LD_PRELOAD` of `oneccl-4ceafd1-b70-public`, `CCL_KERNEL_PATH`,
`CCL_SYCL_ALLREDUCE_LL_THRESHOLD`, and `CCL_SYCL_ALLREDUCE_LL=twoshots`, plus
their identity receipts and hash checks. The server then uses the venv's
bundled oneCCL exactly as the deterministic 2026-08-28 eager line did.
Attempt 61 / port 19733; names carry `bundledccl`.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A61_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-2304-ple-only-a60-nograph-w13n32.sh": "4b3e95b7d27e07042b87c442dbdbd89b2d6d8bc6a20d6611f6c89f685db86867",
    "run-tp4-mtp0-2304-ple-only-a60-nograph-w13n32-client.sh": "5970b93dcb22f5d0d6d7e89369f0068e5829e05e7af9443f13cef9d7800d8dc5",
    "supervise-tp4-mtp0-2304-ple-only-a60-nograph-w13n32.sh": "c6eae5e4fc687ba1ed722e2b60c8948f89f0a5a5a7ec3de68ae65d3da39c598a",
    "run-q38-a60-host-controlled.sh": "7434e6f740a3c388e90ffb88cdcc9c8f68cddccf1ef802b68e746a831874c6f9",
}
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")

CCL_EXPORTS = """  print "export CCL_KERNEL_PATH=/home/steve/.venvs/vllm-xpu/lib/ccl/kernels"
  print "export CCL_SYCL_ALLREDUCE_LL_THRESHOLD=4096"
  print "export CCL_SYCL_ALLREDUCE_LL=twoshots"
  print "export LD_PRELOAD=/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public/lib/libccl.so.1.0"
"""
CCL_PRINTS = """  print "  printf '\\''libccl_sha256=43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700\\\\n'\\''"
  print "  printf '\\''ccl_kernel_sha256=0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9\\\\n'\\''"
  print "  printf '\\''ccl_sycl_allreduce_ll=twoshots\\\\n'\\''"
"""
CCL_SHA_CHECKS = """  print "echo 43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700  /mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public/lib/libccl.so.1.0 | sha256sum -c -"
  print "echo 0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9  /home/steve/.venvs/vllm-xpu/lib/ccl/kernels/kernels.spv | sha256sum -c -"
"""
CCL_ASSERTIONS = """grep -Fxq 'export LD_PRELOAD=/mnt/fast-ai/runtime/oneccl-4ceafd1-b70-public/lib/libccl.so.1.0' "$derived"
grep -Fxq 'export CCL_SYCL_ALLREDUCE_LL_THRESHOLD=4096' "$derived"
[[ "$(grep -Fxc 'export CCL_SYCL_ALLREDUCE_LL=twoshots' "$derived")" == 1 ]]
[[ "$(grep -Fxc "  printf 'ccl_sycl_allreduce_ll=twoshots\\\\n'" "$derived")" == 1 ]]
"""
CCL_KERNEL_ASSERTION = """grep -Fxq 'export CCL_KERNEL_PATH=/home/steve/.venvs/vllm-xpu/lib/ccl/kernels' "$derived"
"""
NEW_ASSERTIONS = """! grep -Fq 'oneccl-4ceafd1-b70-public' "$derived"
! grep -Fq 'CCL_SYCL_ALLREDUCE_LL' "$derived"
! grep -Fq 'CCL_KERNEL_PATH' "$derived"
! grep -Fq 'LD_PRELOAD=' "$derived"
"""


def digest(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def source(name: str) -> str:
    data = (ROOT / name).read_bytes()
    assert digest(data) == SOURCES[name], f"source drift: {name}"
    return data.decode()


def successor(text: str) -> str:
    def rename(segment: str) -> str:
        segment = segment.replace("attempt60", "attempt61")
        segment = segment.replace("19732", "19733")
        segment = segment.replace("ATTEMPT=60", "ATTEMPT=61")
        segment = segment.replace("a60", "a61")
        segment = segment.replace("A60", "A61")
        return segment.replace("nograph", "bundledccl")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert "19732" not in out and "nograph" not in out
    return out


def replace_once(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, f"anchor count != 1: {old[:90]!r}"
    return text.replace(old, new)


def replace_n(text: str, old: str, new: str, n: int) -> str:
    assert text.count(old) == n, f"anchor count {text.count(old)} != {n}: {old[:90]!r}"
    return text.replace(old, new)


def emit(name: str, text: str) -> None:
    path = ROOT / name
    if VALIDATE_ONLY:
        assert path.read_text(encoding="utf-8") == text, f"generated drift: {name}"
        return
    assert not path.exists(), f"refusing to overwrite {path}"
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def main() -> None:
    launcher = source("launch-tp4-mtp0-2304-ple-only-a60-nograph-w13n32.sh")
    match = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert match
    launcher = replace_once(
        launcher, "expected_derived=" + match.group(1), "expected_derived=" + "0" * 64
    )
    launcher = replace_once(launcher, CCL_EXPORTS, "")
    launcher = replace_once(launcher, CCL_PRINTS, "")
    launcher = replace_n(launcher, CCL_SHA_CHECKS, "", 2)
    launcher = replace_once(launcher, CCL_ASSERTIONS, NEW_ASSERTIONS)
    launcher = replace_once(launcher, CCL_KERNEL_ASSERTION, "")
    launcher = replace_n(
        launcher,
        "diagnostics=nograph-public-oneccl-torch-trace",
        "diagnostics=nograph-bundled-oneccl-torch-trace",
        3,
    )
    launcher = successor(launcher)

    env = os.environ.copy()
    env["Q38_A61_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a61-base.sh").unlink(missing_ok=True)
    assert "oneccl-4ceafd1-b70-public" not in derived
    assert "CCL_SYCL_ALLREDUCE_LL" not in derived and "LD_PRELOAD=" not in derived
    assert "export CCL_TOPO_P2P_ACCESS=1\n" in derived
    assert "diagnostics=bundledccl-bundled-oneccl-torch-trace" in derived
    assert "  --enforce-eager\n" in derived and "q38-ple2k-a61" in derived
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )

    client = successor(
        source("run-tp4-mtp0-2304-ple-only-a60-nograph-w13n32-client.sh")
    )
    supervisor = successor(
        source("supervise-tp4-mtp0-2304-ple-only-a60-nograph-w13n32.sh")
    )
    supervisor = replace_once(
        supervisor,
        "expected_wrapper=4b3e95b7d27e07042b87c442dbdbd89b2d6d8bc6a20d6611f6c89f685db86867",
        "expected_wrapper=" + digest(launcher),
    )
    supervisor = replace_once(
        supervisor,
        "expected_client=5970b93dcb22f5d0d6d7e89369f0068e5829e05e7af9443f13cef9d7800d8dc5",
        "expected_client=" + digest(client),
    )
    host = successor(source("run-q38-a60-host-controlled.sh"))
    host = replace_once(
        host,
        "expected_supervisor=c6eae5e4fc687ba1ed722e2b60c8948f89f0a5a5a7ec3de68ae65d3da39c598a",
        "expected_supervisor=" + digest(supervisor),
    )
    emit("launch-tp4-mtp0-2304-ple-only-a61-bundledccl-w13n32.sh", launcher)
    emit("run-tp4-mtp0-2304-ple-only-a61-bundledccl-w13n32-client.sh", client)
    emit("supervise-tp4-mtp0-2304-ple-only-a61-bundledccl-w13n32.sh", supervisor)
    emit("run-q38-a61-host-controlled.sh", host)
    for name in (
        "launch-tp4-mtp0-2304-ple-only-a61-bundledccl-w13n32.sh",
        "run-tp4-mtp0-2304-ple-only-a61-bundledccl-w13n32-client.sh",
        "supervise-tp4-mtp0-2304-ple-only-a61-bundledccl-w13n32.sh",
        "run-q38-a61-host-controlled.sh",
    ):
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
