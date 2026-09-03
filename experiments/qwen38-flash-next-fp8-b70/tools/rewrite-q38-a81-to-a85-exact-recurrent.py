#!/usr/bin/env python3
"""Create the A85 packet from frozen A81: MTP1 in the full decode graph with the serial-exact recurrent path.

A81/A83/A84 showed the MTP1 verification path diverging from single-row
decode after the first generated token at every depth. The kernel source
carries an exact recurrent spec-decode path (VLLM_XPU_GDN_NATIVE_SPEC_
RECURRENT_SERIAL_EXACT with persistent scratch; generalized to the MTP1 row
count in kernel commit ad25aa9, an ancestor of the line's e421889 source
head) that was never exercised end to end (the 2026-08-27 attempt died on a
launcher path-length defect). A85 is the A81 packet at attempt 85 / port
19757 with MTP_EXACT=1: the base's exact freeze lifts to exactly 1, the
kernel stage becomes the sealed exact build
/mnt/usb-models/qwen38-build/runtime-mtp1-exact-ad25aa9-b70 (manifest
runtime-stage-mtp1-exact-loadable.sha256, stage build head ad25aa9), the
served model name carries the base's -mtp1-exact-recurrent suffix, and the
campaign name its -exact-recurrent- infix. Everything else is A81.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A85_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp1-4352-ple-only-a81-fullgraphdet-w13n32.sh": "c1cd610a7bb93f45afd4a364892f2446fd55d7c6736374f097565290270dd936",
    "run-tp4-mtp1-4352-ple-only-a81-fullgraphdet-w13n32-client.sh": "ac19fe01e1fe83972cc217386608c612a8009047bd01d3194e52675a2121674d",
    "supervise-tp4-mtp1-4352-ple-only-a81-fullgraphdet-w13n32.sh": "f42a8a5e4808e7c61826355f82e31433cb43d4f057d0d5a4d900256dc337c77c",
    "run-q38-a81-host-controlled.sh": "b6c392ac01bdbaf323960b8dd33297315d1667b7f85ad4f2782123ba665e49a1",
}
EXACT_RULE = (
    '$0 == "[[ \\"${mtp_exact}\\" == \\"0\\" ]] || {" {\n'
    '  print "[[ \\"${mtp_exact}\\" == \\"1\\" ]] || {"\n'
    "  next\n"
    "}\n"
)
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")


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
        segment = segment.replace("fullgraphdet-mtp1-4352-ple-only", "fullgraphdet-mtp1-exact-recurrent-4352-ple-only")
        segment = segment.replace("attempt81", "attempt85")
        segment = segment.replace("19753", "19757")
        segment = segment.replace("ATTEMPT=81", "ATTEMPT=85")
        segment = segment.replace("a81", "a85")
        return segment.replace("A81", "A85")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19753" not in out and "attempt81" not in out
    return out


def replace_once(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, f"anchor count != 1: {old[:90]!r}"
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
    launcher = source("launch-tp4-mtp1-4352-ple-only-a81-fullgraphdet-w13n32.sh")
    match = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert match
    launcher = replace_once(launcher, "expected_derived=" + match.group(1), "expected_derived=" + "0" * 64)
    launcher = successor(launcher)
    launcher = replace_once(launcher, '$0 == "export XPU_GRAPH=0" {\n', EXACT_RULE + '$0 == "export XPU_GRAPH=0" {\n')
    launcher = replace_once(launcher, "export MTP=1 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=85 PORT=19757\n", "export MTP=1 MTP_EXACT=1 MAX_MODEL_LEN=4352 ATTEMPT=85 PORT=19757\n")
    launcher = replace_once(launcher, "export KERNEL_STAGE=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70\n", "export KERNEL_STAGE=/mnt/usb-models/qwen38-build/runtime-mtp1-exact-ad25aa9-b70\n")
    launcher = replace_once(launcher, """grep -Fxq '[[ "${mtp}" == "1" ]] || {' "$derived"\n""", """grep -Fxq '[[ "${mtp}" == "1" ]] || {' "$derived"\ngrep -Fxq '[[ "${mtp_exact}" == "1" ]] || {' "$derived"\n""")
    env = os.environ.copy()
    env["Q38_A85_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a85-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a85" in derived and "q38-ple2k-a81" not in derived
    assert '[[ "${mtp}" == "1" ]] || {' in derived and '[[ "${mtp_exact}" == "1" ]] || {' in derived
    assert '[[ "${mtp_exact}" == "0" ]] || {' not in derived
    assert '"cudagraph_capture_sizes":[1,2],"max_cudagraph_capture_size":2' in derived
    assert "export VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1" in derived
    assert "runtime-stage-mtp1-exact-loadable.sha256" in derived
    assert 'served_model_name="qwen38-flash-next-fp8-tp4-mtp1-exact-recurrent"' in derived
    assert 'expected_stage_build_head="ad25aa9f69a2171612b9c6b83dfa82c69559f9e4"' in derived
    assert 'expected_kernels_head="e421889999bc1e5a5f11044d14548b9afdba644d"' in derived
    launcher = launcher.replace("expected_derived=" + "0" * 64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp1-4352-ple-only-a81-fullgraphdet-w13n32-client.sh"))
    supervisor = successor(source("supervise-tp4-mtp1-4352-ple-only-a81-fullgraphdet-w13n32.sh"))
    supervisor = replace_once(supervisor, '.identity.stage_build_head == "2f829747503c77d4814834dffd0840fb1dd9f75a" and', '.identity.stage_build_head == "ad25aa9f69a2171612b9c6b83dfa82c69559f9e4" and')
    supervisor = replace_once(supervisor, "expected_wrapper=c1cd610a7bb93f45afd4a364892f2446fd55d7c6736374f097565290270dd936", "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=ac19fe01e1fe83972cc217386608c612a8009047bd01d3194e52675a2121674d", "expected_client=" + digest(client))
    host = successor(source("run-q38-a81-host-controlled.sh"))
    host = replace_once(host, "expected_supervisor=f42a8a5e4808e7c61826355f82e31433cb43d4f057d0d5a4d900256dc337c77c", "expected_supervisor=" + digest(supervisor))
    names = (
        "launch-tp4-mtp1-4352-ple-only-a85-fullgraphdet-w13n32.sh",
        "run-tp4-mtp1-4352-ple-only-a85-fullgraphdet-w13n32-client.sh",
        "supervise-tp4-mtp1-4352-ple-only-a85-fullgraphdet-w13n32.sh",
        "run-q38-a85-host-controlled.sh",
    )
    for name, text in zip(names, (launcher, client, supervisor, host)):
        emit(name, text)
    for name in names:
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
