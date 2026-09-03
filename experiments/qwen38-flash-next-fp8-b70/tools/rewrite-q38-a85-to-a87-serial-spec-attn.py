#!/usr/bin/env python3
"""Create the A87 packet from frozen A85: serial verifier-row flash attention on top of the exact recurrent path.

A85 (MTP1 in the graph with the serial-exact recurrent path) moved the
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
VALIDATE_ONLY = os.environ.get("Q38_A87_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp1-4352-ple-only-a85-fullgraphdet-w13n32.sh": "b2d2002d3a71b5fc609cabd0ad668ffab6868acd54d0c35273dca7d023f72588",
    "run-tp4-mtp1-4352-ple-only-a85-fullgraphdet-w13n32-client.sh": "9f16a9307d35f19fa358b337396afae8860c8b7c12e5d8b2579fb9f3ee33d797",
    "supervise-tp4-mtp1-4352-ple-only-a85-fullgraphdet-w13n32.sh": "1acacd640e0aaad6f0282db70efcef2587c6ea9c7f7eca9baf27e4a61f8741c2",
    "run-q38-a85-host-controlled.sh": "37ae3fd4a8a4b1c90f15d025145ec5fa975600d3eab1ebf7b1ebf731b3065cd0",
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
        segment = segment.replace("attempt85", "attempt87")
        segment = segment.replace("19757", "19759")
        segment = segment.replace("ATTEMPT=85", "ATTEMPT=87")
        segment = segment.replace("a85", "a87")
        return segment.replace("A85", "A87")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19757" not in out and "attempt85" not in out
    return out


OLD_HEAD = "2169dbfe38c2954edc5ae50e94f68d45be071b79"
NEW_HEAD = "d3a61403dc28e3a9fce923848b578be886ffe142"


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
    launcher = source("launch-tp4-mtp1-4352-ple-only-a85-fullgraphdet-w13n32.sh")
    match = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert match
    launcher = replace_once(launcher, "expected_derived=" + match.group(1), "expected_derived=" + "0" * 64)
    launcher = successor(launcher)
    launcher = replace_n(launcher, OLD_HEAD, NEW_HEAD, 2)
    launcher = replace_once(launcher, '  print "export VLLM_XPU_MKLDNN_DETERMINISTIC=1"\n', '  print "export VLLM_XPU_MKLDNN_DETERMINISTIC=1"\n  print "export VLLM_XPU_FA_SERIAL_SPEC_DECODE=1"\n')
    env = os.environ.copy()
    env["Q38_A87_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a87-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a87" in derived and "q38-ple2k-a85" not in derived
    assert '[[ "${mtp}" == "1" ]] || {' in derived and '[[ "${mtp_exact}" == "1" ]] || {' in derived
    assert "export VLLM_XPU_FA_SERIAL_SPEC_DECODE=1\n" in derived
    assert "export VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1" in derived
    assert f'expected_vllm_head="{NEW_HEAD}"' in derived and OLD_HEAD not in derived
    launcher = launcher.replace("expected_derived=" + "0" * 64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp1-4352-ple-only-a85-fullgraphdet-w13n32-client.sh"))
    supervisor = successor(source("supervise-tp4-mtp1-4352-ple-only-a85-fullgraphdet-w13n32.sh"))
    supervisor = replace_once(supervisor, "expected_wrapper=b2d2002d3a71b5fc609cabd0ad668ffab6868acd54d0c35273dca7d023f72588", "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=9f16a9307d35f19fa358b337396afae8860c8b7c12e5d8b2579fb9f3ee33d797", "expected_client=" + digest(client))
    host = successor(source("run-q38-a85-host-controlled.sh"))
    host = replace_once(host, "expected_supervisor=1acacd640e0aaad6f0282db70efcef2587c6ea9c7f7eca9baf27e4a61f8741c2", "expected_supervisor=" + digest(supervisor))
    names = (
        "launch-tp4-mtp1-4352-ple-only-a87-fullgraphdet-w13n32.sh",
        "run-tp4-mtp1-4352-ple-only-a87-fullgraphdet-w13n32-client.sh",
        "supervise-tp4-mtp1-4352-ple-only-a87-fullgraphdet-w13n32.sh",
        "run-q38-a87-host-controlled.sh",
    )
    for name, text in zip(names, (launcher, client, supervisor, host)):
        emit(name, text)
    for name in names:
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
