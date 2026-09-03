#!/usr/bin/env python3
"""Create the A78 packet from frozen A73 with fresh attempt paths only.

A73 is the deterministic graph line's frozen client at 4352 served tokens
(exact-2K and exact-4K rows pinned to the line's own two-server hashes).
A78 is the byte-identical packet at attempt 78 / port 19750, an
independently started server on which the same frozen client runs, so the
4352-token record is a pair (the A70/A71 pattern).
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A78_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-4352-ple-only-a73-fullgraphdet-w13n32.sh": "867584a89d5baa111b8e4227e53dd64db96db08d02bfe08a381119f7438c1b66",
    "run-tp4-mtp0-4352-ple-only-a73-fullgraphdet-w13n32-client.sh": "24ac1167974c33f6e4e3f768960f0d44cf8c426bf3b1fcb2a5497a5075c087ad",
    "supervise-tp4-mtp0-4352-ple-only-a73-fullgraphdet-w13n32.sh": "3e5bce3023f2d1c2a1be008cfaf35134ab85252e6d3d841e120e05e594f62e8b",
    "run-q38-a73-host-controlled.sh": "add9c0a09dea7a053585c757a04937013895603031abe9d5c62c635829d27926",
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
        segment = segment.replace("attempt73", "attempt78")
        segment = segment.replace("19745", "19750")
        segment = segment.replace("ATTEMPT=73", "ATTEMPT=78")
        segment = segment.replace("a73", "a78")
        return segment.replace("A73", "A78")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19745" not in out and "attempt73" not in out
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
    launcher = source("launch-tp4-mtp0-4352-ple-only-a73-fullgraphdet-w13n32.sh")
    match = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert match
    launcher = replace_once(
        launcher, "expected_derived=" + match.group(1), "expected_derived=" + "0" * 64
    )
    launcher = successor(launcher)
    env = os.environ.copy()
    env["Q38_A78_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a78-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a78" in derived and "q38-ple2k-a73" not in derived
    assert "export VLLM_XPU_MKLDNN_DETERMINISTIC=1\n" in derived
    assert "oneccl-4ceafd1-b70-public" in derived and "  --enforce-eager\n" not in derived
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )
    client = successor(
        source("run-tp4-mtp0-4352-ple-only-a73-fullgraphdet-w13n32-client.sh")
    )
    supervisor = successor(
        source("supervise-tp4-mtp0-4352-ple-only-a73-fullgraphdet-w13n32.sh")
    )
    supervisor = replace_once(
        supervisor,
        "expected_wrapper=867584a89d5baa111b8e4227e53dd64db96db08d02bfe08a381119f7438c1b66",
        "expected_wrapper=" + digest(launcher),
    )
    supervisor = replace_once(
        supervisor,
        "expected_client=24ac1167974c33f6e4e3f768960f0d44cf8c426bf3b1fcb2a5497a5075c087ad",
        "expected_client=" + digest(client),
    )
    host = successor(source("run-q38-a73-host-controlled.sh"))
    host = replace_once(
        host,
        "expected_supervisor=3e5bce3023f2d1c2a1be008cfaf35134ab85252e6d3d841e120e05e594f62e8b",
        "expected_supervisor=" + digest(supervisor),
    )
    emit("launch-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh", launcher)
    emit("run-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32-client.sh", client)
    emit("supervise-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh", supervisor)
    emit("run-q38-a78-host-controlled.sh", host)
    for name in (
        "launch-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh",
        "run-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32-client.sh",
        "supervise-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh",
        "run-q38-a78-host-controlled.sh",
    ):
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
