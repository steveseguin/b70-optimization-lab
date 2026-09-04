#!/usr/bin/env python3
"""Create the A129 packet from frozen A81: graph MTP1 with GDN verifier rows through the decode kernel (VLLM_XPU_GDN_SERIAL_SPEC_DECODE).

A81 is the plain graph MTP1 packet (no exact-recurrent mode). A129 adds the
exact-2K divergence from token 7 to token 12 and left the 4K continuation
unchanged; the dense GEMMs were shown M-invariant offline and the MoE
already resolves M=2 to the M=1 config, leaving the 12 full-attention
layers' two-row FlashAttention path as the prime suspect (the 27B FP8 lane
needed serial spec attention, R38, for the same reason). A87 is the A85
packet at attempt 87 / port 19759 on overlay head d3a61403 (2169dbfe plus
the XPU serial verifier-row attention behind
VLLM_XPU_FA_SERIAL_SPEC_DECODE) with that flag exported to the server.
Nothing else changes.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A129_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp1-4352-ple-only-a81-fullgraphdet-w13n32.sh": "c1cd610a7bb93f45afd4a364892f2446fd55d7c6736374f097565290270dd936",
    "run-tp4-mtp1-4352-ple-only-a81-fullgraphdet-w13n32-client.sh": "ac19fe01e1fe83972cc217386608c612a8009047bd01d3194e52675a2121674d",
    "supervise-tp4-mtp1-4352-ple-only-a81-fullgraphdet-w13n32.sh": "f42a8a5e4808e7c61826355f82e31433cb43d4f057d0d5a4d900256dc337c77c",
    "run-q38-a81-host-controlled.sh": "b6c392ac01bdbaf323960b8dd33297315d1667b7f85ad4f2782123ba665e49a1",
}
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
        segment = segment.replace("attempt81", "attempt129")
        segment = segment.replace("19753", "19800")
        segment = segment.replace("ATTEMPT=81", "ATTEMPT=129")
        segment = segment.replace("a81", "a129")
        return segment.replace("A81", "A129")

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


OLD_HEAD = "2169dbfe38c2954edc5ae50e94f68d45be071b79"
NEW_HEAD = "5915cb0e88b03d709d743020d74c821c5b5b3ecf"


def replace_n(text: str, old: str, new: str, n: int) -> str:
    assert text.count(old) == n, f"anchor count {text.count(old)} != {n}: {old[:90]!r}"
    return text.replace(old, new)


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
    launcher = replace_n(launcher, OLD_HEAD, NEW_HEAD, 2)
    launcher = replace_once(launcher, "export KV_CACHE_MEMORY_BYTES=376569856\n", "export KV_CACHE_MEMORY_BYTES=376569856\nexport Q38_STEP_TIMING_LOG=10\n")
    launcher = replace_once(launcher, '  print "export VLLM_XPU_MKLDNN_DETERMINISTIC=1"\n', '  print "export VLLM_XPU_MKLDNN_DETERMINISTIC=1"\n  print "export VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1"\n  print "export VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=2"\n')
    env = os.environ.copy()
    env["Q38_A129_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a129-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a129" in derived and "q38-ple2k-a81" not in derived
    assert '[[ "${mtp}" == "1" ]] || {' in derived and "export MTP=1 MTP_EXACT=0 " in launcher
    assert "export VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1\n" in derived
    assert "export VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=2\n" in derived
    assert "export VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=2\n" not in derived
    assert f'expected_vllm_head="{NEW_HEAD}"' in derived and OLD_HEAD not in derived
    launcher = launcher.replace("expected_derived=" + "0" * 64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp1-4352-ple-only-a81-fullgraphdet-w13n32-client.sh"))
    supervisor = successor(source("supervise-tp4-mtp1-4352-ple-only-a81-fullgraphdet-w13n32.sh"))
    supervisor = replace_once(supervisor, "expected_wrapper=c1cd610a7bb93f45afd4a364892f2446fd55d7c6736374f097565290270dd936", "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=ac19fe01e1fe83972cc217386608c612a8009047bd01d3194e52675a2121674d", "expected_client=" + digest(client))
    host = successor(source("run-q38-a81-host-controlled.sh"))
    host = replace_once(host, "expected_supervisor=f42a8a5e4808e7c61826355f82e31433cb43d4f057d0d5a4d900256dc337c77c", "expected_supervisor=" + digest(supervisor))
    names = (
        "launch-tp4-mtp1-4352-ple-only-a129-fullgraphdet-w13n32.sh",
        "run-tp4-mtp1-4352-ple-only-a129-fullgraphdet-w13n32-client.sh",
        "supervise-tp4-mtp1-4352-ple-only-a129-fullgraphdet-w13n32.sh",
        "run-q38-a129-host-controlled.sh",
    )
    for name, text in zip(names, (launcher, client, supervisor, host)):
        emit(name, text)
    for name in names:
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
