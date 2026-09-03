#!/usr/bin/env python3
"""Create the A91 packet from frozen A85 with fresh attempt paths only (logprob probe of the exact-recurrent MTP1 line).

A81 (MTP1 in the full decode graph) and A83 (eager MTP1) both produced the
same exact-2K continuation, different from the MTP0 line's, so the
speculative verification path itself differs numerically from single-row
decode at depth. A84 is the A81 server at attempt 84 / port 19756 on which
the A59 logprob probe runs (depths 8, 256, 2048; eight first-step repeats
and three 128-token repeats each) so the top-5 logprobs can be compared
offline against the MTP0 line's A76/A77 probes: where the first difference
appears and how large it is. The frozen client is renamed only.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A91_REWRITE_VALIDATE_ONLY") == "1"
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
        segment = segment.replace("attempt85", "attempt91")
        segment = segment.replace("19757", "19763")
        segment = segment.replace("ATTEMPT=85", "ATTEMPT=91")
        segment = segment.replace("a85", "a91")
        return segment.replace("A85", "A91")

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
    env = os.environ.copy()
    env["Q38_A91_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a91-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a91" in derived and "q38-ple2k-a85" not in derived
    assert "export VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1" in derived
    assert '[[ "${mtp}" == "1" ]] || {' in derived
    assert '"cudagraph_capture_sizes":[1,2],"max_cudagraph_capture_size":2' in derived
    launcher = launcher.replace("expected_derived=" + "0" * 64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp1-4352-ple-only-a85-fullgraphdet-w13n32-client.sh"))
    supervisor = successor(source("supervise-tp4-mtp1-4352-ple-only-a85-fullgraphdet-w13n32.sh"))
    supervisor = replace_once(supervisor, "expected_wrapper=b2d2002d3a71b5fc609cabd0ad668ffab6868acd54d0c35273dca7d023f72588", "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=9f16a9307d35f19fa358b337396afae8860c8b7c12e5d8b2579fb9f3ee33d797", "expected_client=" + digest(client))
    host = successor(source("run-q38-a85-host-controlled.sh"))
    host = replace_once(host, "expected_supervisor=1acacd640e0aaad6f0282db70efcef2587c6ea9c7f7eca9baf27e4a61f8741c2", "expected_supervisor=" + digest(supervisor))
    names = (
        "launch-tp4-mtp1-4352-ple-only-a91-fullgraphdet-w13n32.sh",
        "run-tp4-mtp1-4352-ple-only-a91-fullgraphdet-w13n32-client.sh",
        "supervise-tp4-mtp1-4352-ple-only-a91-fullgraphdet-w13n32.sh",
        "run-q38-a91-host-controlled.sh",
    )
    for name, text in zip(names, (launcher, client, supervisor, host)):
        emit(name, text)
    for name in names:
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
