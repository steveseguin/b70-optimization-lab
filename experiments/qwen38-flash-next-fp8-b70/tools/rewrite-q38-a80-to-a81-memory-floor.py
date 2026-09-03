#!/usr/bin/env python3
"""Create the A81 packet from frozen A80 with a 12 GB supervisor memory floor.

A80 (MTP1, capture sizes [1, 2], 376569856 KV bytes on the deterministic
full-decode-graph line, NVMe model copy) came up healthy, captured its
graphs, and was stopped by the supervisor's per-second host-memory guard on
the battery's first request: MemAvailable fell to 15,990,872 KiB against the
16,000,000 KiB floor. The MTP0 line bottoms at about 20.5 GB on the same
host (A79), so the MTP head and its buffers cost about 4.5 GB of host
memory. A81 is the byte-identical packet at attempt 81 / port 19753 with the
supervisor floor at 12,000,000 KiB; swap is off for the whole run, the
launch pre-check still requires 120,000,000 KiB free before start, and the
PSI, AER and bounded-read guards are unchanged.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A81_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp1-4352-ple-only-a80-fullgraphdet-w13n32.sh": "234daed6c2802a8d2cef9bee6b88dbcb0d77a41483e789d8824369fab795626d",
    "run-tp4-mtp1-4352-ple-only-a80-fullgraphdet-w13n32-client.sh": "35fbfd759c4f1043b96d1ea990776f7c187db1ac074609891b50a1e72bf7e1cd",
    "supervise-tp4-mtp1-4352-ple-only-a80-fullgraphdet-w13n32.sh": "9f5434682e7519033c94d214c40e13f09e32eee467fa001bf6f4271de219ae50",
    "run-q38-a80-host-controlled.sh": "e05d865d0cda565259f31e3a31738e7b7825a52fedbd4004ced4085c558a8748",
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
        segment = segment.replace("attempt80", "attempt81")
        segment = segment.replace("19752", "19753")
        segment = segment.replace("ATTEMPT=80", "ATTEMPT=81")
        segment = segment.replace("a80", "a81")
        return segment.replace("A80", "A81")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19752" not in out and "attempt80" not in out
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
    launcher = source("launch-tp4-mtp1-4352-ple-only-a80-fullgraphdet-w13n32.sh")
    match = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert match
    launcher = replace_once(launcher, "expected_derived=" + match.group(1), "expected_derived=" + "0" * 64)
    launcher = successor(launcher)
    env = os.environ.copy()
    env["Q38_A81_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a81-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a81" in derived and "q38-ple2k-a80" not in derived
    assert '[[ "${mtp}" == "1" ]] || {' in derived
    assert '"cudagraph_capture_sizes":[1,2],"max_cudagraph_capture_size":2' in derived
    launcher = launcher.replace("expected_derived=" + "0" * 64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp1-4352-ple-only-a80-fullgraphdet-w13n32-client.sh"))
    supervisor = successor(source("supervise-tp4-mtp1-4352-ple-only-a80-fullgraphdet-w13n32.sh"))
    supervisor = replace_once(supervisor, "  (( mem_available_kib >= 16000000 )) || return 1\n", "  (( mem_available_kib >= 12000000 )) || return 1\n")
    supervisor = replace_once(supervisor, "expected_wrapper=234daed6c2802a8d2cef9bee6b88dbcb0d77a41483e789d8824369fab795626d", "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=35fbfd759c4f1043b96d1ea990776f7c187db1ac074609891b50a1e72bf7e1cd", "expected_client=" + digest(client))
    host = successor(source("run-q38-a80-host-controlled.sh"))
    host = replace_once(host, "expected_supervisor=9f5434682e7519033c94d214c40e13f09e32eee467fa001bf6f4271de219ae50", "expected_supervisor=" + digest(supervisor))
    names = (
        "launch-tp4-mtp1-4352-ple-only-a81-fullgraphdet-w13n32.sh",
        "run-tp4-mtp1-4352-ple-only-a81-fullgraphdet-w13n32-client.sh",
        "supervise-tp4-mtp1-4352-ple-only-a81-fullgraphdet-w13n32.sh",
        "run-q38-a81-host-controlled.sh",
    )
    for name, text in zip(names, (launcher, client, supervisor, host)):
        emit(name, text)
    for name in names:
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
