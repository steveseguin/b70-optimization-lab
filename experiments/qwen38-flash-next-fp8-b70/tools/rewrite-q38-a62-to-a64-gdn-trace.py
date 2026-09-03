#!/usr/bin/env python3
"""Create the A64 in-server GDN trace packet from frozen A62.

A63 (old overlay head) reproduced the same first-step jitter, so the 18
overlay commits are excluded and the 2026-08-30 A24/A25 localization
(first cross-start difference at the layer-1 GatedDeltaNet attention output,
everything upstream exact) is the best pointer. A64 keeps A62's server
identity (eager, bundled oneCCL, tuned M1 W13-N32 map, external checkpoint,
PLE-only UVA placement, 2304 max model length, host guards) and changes two
things: the overlay head moves to the diagnostic commit that adds default-off
GDN-internal records to the report-only repeatability trace, and the launcher
exports that trace for all four ranks with an exact 8-token position window
and a capture count of three, so the three depth-8 probe prefills are traced
op by op on one server. Attempt 64 / port 19736; names carry `gdntrace`.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A64_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-2304-ple-only-a62-bundledccl-w13n32.sh": "15ec4b27670bcb77cab05f0c2d70780f0c4d558cacf36b2d2dacbf209196a623",
    "run-tp4-mtp0-2304-ple-only-a62-bundledccl-w13n32-client.sh": "25fe95624afe4dfc1029fcb69239195b5105d6e0a168b3ec6a34fee5a2461260",
    "supervise-tp4-mtp0-2304-ple-only-a62-bundledccl-w13n32.sh": "377dd77e822007af1573e37af29704b5c1c97de1040ddf2099537dd480e28a2e",
    "run-q38-a62-host-controlled.sh": "890ca8610493b418d493441d68d0ed851e7da1ab001d51c976c28f82f97c5073",
}
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
A62_HEAD = "cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9"
A64_HEAD = "69f905f1fb062cce782bbcb4850f3856924dc24b"
RUN_DIR = "${RUN_PARENT}/qwen38-flash-next-fp8-tp4-ep4-gdntrace-mtp0-2304-ple-only-r1-attempt64"

OLD_TRACE_LINES = """unset Q38_REPEATABILITY_TRACE_FILE
unset VLLM_XPU_QWEN4_EXP_REPEATABILITY_TRACE_RANK
"""
NEW_TRACE_LINES = f"""export Q38_REPEATABILITY_TRACE_FILE={RUN_DIR}/gdn-trace-rank{{rank}}.json
export VLLM_XPU_QWEN4_EXP_REPEATABILITY_TRACE_RANK=all
export VLLM_XPU_QWEN4_EXP_REPEATABILITY_TRACE_MIN_POSITION=0
export VLLM_XPU_QWEN4_EXP_REPEATABILITY_TRACE_EXACT_POSITIONS=0:7
export VLLM_XPU_QWEN4_EXP_REPEATABILITY_TRACE_COUNT=3
export VLLM_XPU_QWEN4_EXP_REPEATABILITY_TRACE_GDN_LAYERS=0,1,2
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
        segment = segment.replace("attempt62", "attempt64")
        segment = segment.replace("19734", "19736")
        segment = segment.replace("ATTEMPT=62", "ATTEMPT=64")
        segment = segment.replace("a62", "a64")
        segment = segment.replace("A62", "A64")
        return segment.replace("bundledccl", "gdntrace")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert "19734" not in out and "bundledccl" not in out
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
    assert re.fullmatch(r"[0-9a-f]{40}", A64_HEAD), "fill in A64_HEAD first"
    launcher = source("launch-tp4-mtp0-2304-ple-only-a62-bundledccl-w13n32.sh")
    match = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert match
    launcher = replace_once(
        launcher, "expected_derived=" + match.group(1), "expected_derived=" + "0" * 64
    )
    launcher = replace_n(launcher, A62_HEAD, A64_HEAD, 2)
    launcher = replace_once(launcher, OLD_TRACE_LINES, NEW_TRACE_LINES)
    launcher = successor(launcher)

    env = os.environ.copy()
    env["Q38_A64_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a64-base.sh").unlink(missing_ok=True)
    assert f'expected_vllm_head="{A64_HEAD}"' in derived and A62_HEAD not in derived
    assert "moe-m1-w13-n32" in derived and "  --enforce-eager\n" in derived
    assert "oneccl-4ceafd1-b70-public" not in derived
    assert "q38-ple2k-a64" in derived
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )
    client = successor(
        source("run-tp4-mtp0-2304-ple-only-a62-bundledccl-w13n32-client.sh")
    )
    supervisor = successor(
        source("supervise-tp4-mtp0-2304-ple-only-a62-bundledccl-w13n32.sh")
    )
    supervisor = replace_once(
        supervisor,
        "expected_wrapper=15ec4b27670bcb77cab05f0c2d70780f0c4d558cacf36b2d2dacbf209196a623",
        "expected_wrapper=" + digest(launcher),
    )
    supervisor = replace_once(
        supervisor,
        "expected_client=25fe95624afe4dfc1029fcb69239195b5105d6e0a168b3ec6a34fee5a2461260",
        "expected_client=" + digest(client),
    )
    host = successor(source("run-q38-a62-host-controlled.sh"))
    host = replace_once(
        host,
        "expected_supervisor=377dd77e822007af1573e37af29704b5c1c97de1040ddf2099537dd480e28a2e",
        "expected_supervisor=" + digest(supervisor),
    )
    emit("launch-tp4-mtp0-2304-ple-only-a64-gdntrace-w13n32.sh", launcher)
    emit("run-tp4-mtp0-2304-ple-only-a64-gdntrace-w13n32-client.sh", client)
    emit("supervise-tp4-mtp0-2304-ple-only-a64-gdntrace-w13n32.sh", supervisor)
    emit("run-q38-a64-host-controlled.sh", host)
    for name in (
        "launch-tp4-mtp0-2304-ple-only-a64-gdntrace-w13n32.sh",
        "run-tp4-mtp0-2304-ple-only-a64-gdntrace-w13n32-client.sh",
        "supervise-tp4-mtp0-2304-ple-only-a64-gdntrace-w13n32.sh",
        "run-q38-a64-host-controlled.sh",
    ):
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
