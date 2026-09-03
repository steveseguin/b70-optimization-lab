#!/usr/bin/env python3
"""Create the A65 in-server GDN trace packet from frozen A64.

A64 served and reproduced the jitter but wrote no trace: the base launcher
unsets inherited VLLM_* variables, so only the Q38_-prefixed file path
survived and the trace kept its 4000-position default. Overlay commit
`c027fe2d...` reads every trace setting through a Q38_REPEATABILITY_TRACE_*
alias as well. A65 is A64 with that head and the five settings exported under
the alias names. Attempt 65 / port 19737; names carry `q38trace`.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A65_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-2304-ple-only-a64-gdntrace-w13n32.sh": "f19f0fbe922ccd07ed6b8476011e5ca824e2dc6c2b21dba06ff7b6dddcda64d6",
    "run-tp4-mtp0-2304-ple-only-a64-gdntrace-w13n32-client.sh": "b37bb78be5421852f74275584e3ed51bb724a4b558e95cd30100ee066f671b59",
    "supervise-tp4-mtp0-2304-ple-only-a64-gdntrace-w13n32.sh": "ec43ee9f62fa6cdf4c99ebbfc09673448c58780907b91bcabab103a4d5126c11",
    "run-q38-a64-host-controlled.sh": "cde506cf6a8e67dcca50c5da7398d9d25e08e4ea915f81785b9a2d1f12457610",
}
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
A64_HEAD = "69f905f1fb062cce782bbcb4850f3856924dc24b"
A65_HEAD = "c027fe2d12a8002996c5448654ef9d87fb26cdeb"
A64_RUN_DIR = "${RUN_PARENT}/qwen38-flash-next-fp8-tp4-ep4-gdntrace-mtp0-2304-ple-only-r1-attempt64"
A65_RUN_DIR = "${RUN_PARENT}/qwen38-flash-next-fp8-tp4-ep4-q38trace-mtp0-2304-ple-only-r1-attempt65"

OLD_TRACE_LINES = f"""export Q38_REPEATABILITY_TRACE_FILE={A64_RUN_DIR}/gdn-trace-rank{{rank}}.json
export VLLM_XPU_QWEN4_EXP_REPEATABILITY_TRACE_RANK=all
export VLLM_XPU_QWEN4_EXP_REPEATABILITY_TRACE_MIN_POSITION=0
export VLLM_XPU_QWEN4_EXP_REPEATABILITY_TRACE_EXACT_POSITIONS=0:7
export VLLM_XPU_QWEN4_EXP_REPEATABILITY_TRACE_COUNT=3
export VLLM_XPU_QWEN4_EXP_REPEATABILITY_TRACE_GDN_LAYERS=0,1,2
"""
NEW_TRACE_LINES = f"""export Q38_REPEATABILITY_TRACE_FILE={A65_RUN_DIR}/gdn-trace-rank{{rank}}.json
export Q38_REPEATABILITY_TRACE_RANK=all
export Q38_REPEATABILITY_TRACE_MIN_POSITION=0
export Q38_REPEATABILITY_TRACE_EXACT_POSITIONS=0:7
export Q38_REPEATABILITY_TRACE_COUNT=3
export Q38_REPEATABILITY_TRACE_GDN_LAYERS=0,1,2
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
        segment = segment.replace("attempt64", "attempt65")
        segment = segment.replace("19736", "19737")
        segment = segment.replace("ATTEMPT=64", "ATTEMPT=65")
        segment = segment.replace("a64", "a65")
        segment = segment.replace("A64", "A65")
        return segment.replace("gdntrace", "q38trace")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert "19736" not in out and "gdntrace" not in out
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
    assert re.fullmatch(r"[0-9a-f]{40}", A65_HEAD)
    launcher = source("launch-tp4-mtp0-2304-ple-only-a64-gdntrace-w13n32.sh")
    match = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert match
    launcher = replace_once(
        launcher, "expected_derived=" + match.group(1), "expected_derived=" + "0" * 64
    )
    launcher = replace_n(launcher, A64_HEAD, A65_HEAD, 2)
    launcher = replace_once(launcher, OLD_TRACE_LINES, NEW_TRACE_LINES)
    launcher = successor(launcher)

    env = os.environ.copy()
    env["Q38_A65_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a65-base.sh").unlink(missing_ok=True)
    assert f'expected_vllm_head="{A65_HEAD}"' in derived and A64_HEAD not in derived
    assert "moe-m1-w13-n32" in derived and "  --enforce-eager\n" in derived
    assert "oneccl-4ceafd1-b70-public" not in derived
    assert "q38-ple2k-a65" in derived and "VLLM_XPU_QWEN4_EXP_REPEATABILITY" not in derived
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )
    client = successor(
        source("run-tp4-mtp0-2304-ple-only-a64-gdntrace-w13n32-client.sh")
    )
    supervisor = successor(
        source("supervise-tp4-mtp0-2304-ple-only-a64-gdntrace-w13n32.sh")
    )
    supervisor = replace_once(
        supervisor,
        "expected_wrapper=f19f0fbe922ccd07ed6b8476011e5ca824e2dc6c2b21dba06ff7b6dddcda64d6",
        "expected_wrapper=" + digest(launcher),
    )
    supervisor = replace_once(
        supervisor,
        "expected_client=b37bb78be5421852f74275584e3ed51bb724a4b558e95cd30100ee066f671b59",
        "expected_client=" + digest(client),
    )
    host = successor(source("run-q38-a64-host-controlled.sh"))
    host = replace_once(
        host,
        "expected_supervisor=ec43ee9f62fa6cdf4c99ebbfc09673448c58780907b91bcabab103a4d5126c11",
        "expected_supervisor=" + digest(supervisor),
    )
    emit("launch-tp4-mtp0-2304-ple-only-a65-q38trace-w13n32.sh", launcher)
    emit("run-tp4-mtp0-2304-ple-only-a65-q38trace-w13n32-client.sh", client)
    emit("supervise-tp4-mtp0-2304-ple-only-a65-q38trace-w13n32.sh", supervisor)
    emit("run-q38-a65-host-controlled.sh", host)
    for name in (
        "launch-tp4-mtp0-2304-ple-only-a65-q38trace-w13n32.sh",
        "run-tp4-mtp0-2304-ple-only-a65-q38trace-w13n32-client.sh",
        "supervise-tp4-mtp0-2304-ple-only-a65-q38trace-w13n32.sh",
        "run-q38-a65-host-controlled.sh",
    ):
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
