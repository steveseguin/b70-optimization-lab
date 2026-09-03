#!/usr/bin/env python3
"""Create the A75 packet from frozen A74 with fresh attempt paths only.

A74 never served: its host wrapper stopped at the free-root-NVMe floor
(220 GB) after the 27B image builds. A75 is the byte-identical A74 server
(deterministic graph identity at 4352 capacity) at attempt 75 / port 19747
after freeing the docker build cache, for the same 4K-prefill probe.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A75_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-4352-ple-only-a74-fullgraphdet-w13n32.sh": "ebc433d5700070abf60c5b919385600ff1c83f8d52c2aebcd6041da19bdbf509",
    "run-tp4-mtp0-4352-ple-only-a74-fullgraphdet-w13n32-client.sh": "c8011a2781ecd88eb9d9514446e0b16ff160b5d090422d2e7762ea2d729920ae",
    "supervise-tp4-mtp0-4352-ple-only-a74-fullgraphdet-w13n32.sh": "d7e1c9cbef9b3112ee16bc8809a97d5d015cb08cf4802bcecba80d9cbe15e547",
    "run-q38-a74-host-controlled.sh": "e11d1234aa1b4df170ea75ed3d7a91cd16fc026809cb4a7c8f9b78e576ef9fa9",
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
        segment = segment.replace("attempt74", "attempt75")
        segment = segment.replace("19746", "19747")
        segment = segment.replace("ATTEMPT=74", "ATTEMPT=75")
        segment = segment.replace("a74", "a75")
        return segment.replace("A74", "A75")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19746" not in out
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
    launcher = source("launch-tp4-mtp0-4352-ple-only-a74-fullgraphdet-w13n32.sh")
    match = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert match
    launcher = replace_once(
        launcher, "expected_derived=" + match.group(1), "expected_derived=" + "0" * 64
    )
    launcher = successor(launcher)
    env = os.environ.copy()
    env["Q38_A75_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a75-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a75" in derived and "q38-ple2k-a74" not in derived
    assert "oneccl-4ceafd1-b70-public" in derived and "  --enforce-eager\n" not in derived
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )
    client = successor(
        source("run-tp4-mtp0-4352-ple-only-a74-fullgraphdet-w13n32-client.sh")
    )
    supervisor = successor(
        source("supervise-tp4-mtp0-4352-ple-only-a74-fullgraphdet-w13n32.sh")
    )
    supervisor = replace_once(
        supervisor,
        "expected_wrapper=ebc433d5700070abf60c5b919385600ff1c83f8d52c2aebcd6041da19bdbf509",
        "expected_wrapper=" + digest(launcher),
    )
    supervisor = replace_once(
        supervisor,
        "expected_client=c8011a2781ecd88eb9d9514446e0b16ff160b5d090422d2e7762ea2d729920ae",
        "expected_client=" + digest(client),
    )
    host = successor(source("run-q38-a74-host-controlled.sh"))
    host = replace_once(
        host,
        "expected_supervisor=d7e1c9cbef9b3112ee16bc8809a97d5d015cb08cf4802bcecba80d9cbe15e547",
        "expected_supervisor=" + digest(supervisor),
    )
    emit("launch-tp4-mtp0-4352-ple-only-a75-fullgraphdet-w13n32.sh", launcher)
    emit("run-tp4-mtp0-4352-ple-only-a75-fullgraphdet-w13n32-client.sh", client)
    emit("supervise-tp4-mtp0-4352-ple-only-a75-fullgraphdet-w13n32.sh", supervisor)
    emit("run-q38-a75-host-controlled.sh", host)
    for name in (
        "launch-tp4-mtp0-4352-ple-only-a75-fullgraphdet-w13n32.sh",
        "run-tp4-mtp0-4352-ple-only-a75-fullgraphdet-w13n32-client.sh",
        "supervise-tp4-mtp0-4352-ple-only-a75-fullgraphdet-w13n32.sh",
        "run-q38-a75-host-controlled.sh",
    ):
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
