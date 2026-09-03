#!/usr/bin/env python3
"""Create the A66 deterministic-oneDNN endpoint control from frozen A65.

The BF16 deterministic census (A3/A4a, 2026-09-02) showed the K=10240
hyperconnection down-projections vary natively at M=1 and that
``torch.backends.mkldnn.deterministic=True`` made every dense family exact
within and across fresh processes at a multiplicity-weighted cost ratio of
0.986. A66 keeps the A65 server identity (eager, bundled oneCCL, tuned M1
W13-N32 map, external checkpoint, PLE-only UVA placement, 2304 max model
length, host guards) and changes two things: the overlay head moves to the
commit that adds ``VLLM_XPU_MKLDNN_DETERMINISTIC`` (read in the XPU worker's
``init_device``), which the launcher exports as ``1``; and the A65 trace
exports return to the A62 ``unset`` lines. Attempt 66 / port 19738; names
carry ``mkldnndet``.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A66_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-2304-ple-only-a65-q38trace-w13n32.sh": "202d0f17feb683f21be30de3a9bceeeac2be514f46bde309df672a80213368c1",
    "run-tp4-mtp0-2304-ple-only-a65-q38trace-w13n32-client.sh": "4620efedc7bdcd0790321d45ef6f99b21e000114854cff5b8dd20d0c90b6e3b4",
    "supervise-tp4-mtp0-2304-ple-only-a65-q38trace-w13n32.sh": "b39836d07ba325b47c028dd49a593b74d8fb95dbe95b3b3e52b68981358290dc",
    "run-q38-a65-host-controlled.sh": "cc411503e7aa52520e3bd9486da42ecc1b10f9040b79006e1e526bcefffc2fce",
}
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
A65_HEAD = "c027fe2d12a8002996c5448654ef9d87fb26cdeb"
A66_HEAD = "805cde592dfe198a82deaba52894ebfc0e4a4352"
A65_RUN_DIR = "${RUN_PARENT}/qwen38-flash-next-fp8-tp4-ep4-q38trace-mtp0-2304-ple-only-r1-attempt65"

A65_TRACE_LINES = f"""export Q38_REPEATABILITY_TRACE_FILE={A65_RUN_DIR}/gdn-trace-rank{{rank}}.json
export Q38_REPEATABILITY_TRACE_RANK=all
export Q38_REPEATABILITY_TRACE_MIN_POSITION=0
export Q38_REPEATABILITY_TRACE_EXACT_POSITIONS=0:7
export Q38_REPEATABILITY_TRACE_COUNT=3
export Q38_REPEATABILITY_TRACE_GDN_LAYERS=0,1,2
"""
A66_LINES = """unset Q38_REPEATABILITY_TRACE_FILE
unset VLLM_XPU_QWEN4_EXP_REPEATABILITY_TRACE_RANK
"""
# The derived script unsets every inherited VLLM_* variable, so the flag must
# be exported inside it (next to the tuned-folder export) and receipted.
FOLDER_EXPORT = '  print "export VLLM_TUNED_CONFIG_FOLDER=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32"\n'
FLAG_EXPORT = FOLDER_EXPORT + '  print "export VLLM_XPU_MKLDNN_DETERMINISTIC=1"\n'
FOLDER_PRINT = """  print "  printf '\\''tuned_config_folder=moe-m1-w13-n32\\\\n'\\''"
"""
FLAG_PRINT = FOLDER_PRINT + """  print "  printf '\\''mkldnn_deterministic=1\\\\n'\\''"
"""
FOLDER_ASSERT = """[[ "$(grep -Fxc "  printf 'tuned_config_folder=moe-m1-w13-n32\\\\n'" "$derived")" == 1 ]]
"""
FLAG_ASSERT = FOLDER_ASSERT + """[[ "$(grep -Fxc 'export VLLM_XPU_MKLDNN_DETERMINISTIC=1' "$derived")" == 1 ]]
[[ "$(grep -Fxc "  printf 'mkldnn_deterministic=1\\\\n'" "$derived")" == 1 ]]
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
        segment = segment.replace("attempt65", "attempt66")
        segment = segment.replace("19737", "19738")
        segment = segment.replace("ATTEMPT=65", "ATTEMPT=66")
        segment = segment.replace("a65", "a66")
        segment = segment.replace("A65", "A66")
        return segment.replace("q38trace", "mkldnndet")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert "19737" not in out and "q38trace" not in out
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
    assert re.fullmatch(r"[0-9a-f]{40}", A66_HEAD), "fill in A66_HEAD first"
    launcher = source("launch-tp4-mtp0-2304-ple-only-a65-q38trace-w13n32.sh")
    match = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert match
    launcher = replace_once(
        launcher, "expected_derived=" + match.group(1), "expected_derived=" + "0" * 64
    )
    launcher = replace_n(launcher, A65_HEAD, A66_HEAD, 2)
    launcher = replace_once(launcher, A65_TRACE_LINES, A66_LINES)
    launcher = replace_once(launcher, FOLDER_EXPORT, FLAG_EXPORT)
    launcher = replace_once(launcher, FOLDER_PRINT, FLAG_PRINT)
    launcher = replace_once(launcher, FOLDER_ASSERT, FLAG_ASSERT)
    launcher = successor(launcher)

    env = os.environ.copy()
    env["Q38_A66_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a66-base.sh").unlink(missing_ok=True)
    assert f'expected_vllm_head="{A66_HEAD}"' in derived and A65_HEAD not in derived
    assert "moe-m1-w13-n32" in derived and "  --enforce-eager\n" in derived
    assert "oneccl-4ceafd1-b70-public" not in derived
    assert "REPEATABILITY_TRACE" not in derived
    assert "export VLLM_XPU_MKLDNN_DETERMINISTIC=1\n" in derived
    assert "  printf 'mkldnn_deterministic=1\\n'\n" in derived
    assert "q38-ple2k-a66" in derived
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )
    client = successor(source("run-tp4-mtp0-2304-ple-only-a65-q38trace-w13n32-client.sh"))
    supervisor = successor(source("supervise-tp4-mtp0-2304-ple-only-a65-q38trace-w13n32.sh"))
    supervisor = replace_once(
        supervisor,
        "expected_wrapper=202d0f17feb683f21be30de3a9bceeeac2be514f46bde309df672a80213368c1",
        "expected_wrapper=" + digest(launcher),
    )
    supervisor = replace_once(
        supervisor,
        "expected_client=4620efedc7bdcd0790321d45ef6f99b21e000114854cff5b8dd20d0c90b6e3b4",
        "expected_client=" + digest(client),
    )
    host = successor(source("run-q38-a65-host-controlled.sh"))
    host = replace_once(
        host,
        "expected_supervisor=b39836d07ba325b47c028dd49a593b74d8fb95dbe95b3b3e52b68981358290dc",
        "expected_supervisor=" + digest(supervisor),
    )
    emit("launch-tp4-mtp0-2304-ple-only-a66-mkldnndet-w13n32.sh", launcher)
    emit("run-tp4-mtp0-2304-ple-only-a66-mkldnndet-w13n32-client.sh", client)
    emit("supervise-tp4-mtp0-2304-ple-only-a66-mkldnndet-w13n32.sh", supervisor)
    emit("run-q38-a66-host-controlled.sh", host)
    for name in (
        "launch-tp4-mtp0-2304-ple-only-a66-mkldnndet-w13n32.sh",
        "run-tp4-mtp0-2304-ple-only-a66-mkldnndet-w13n32-client.sh",
        "supervise-tp4-mtp0-2304-ple-only-a66-mkldnndet-w13n32.sh",
        "run-q38-a66-host-controlled.sh",
    ):
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
