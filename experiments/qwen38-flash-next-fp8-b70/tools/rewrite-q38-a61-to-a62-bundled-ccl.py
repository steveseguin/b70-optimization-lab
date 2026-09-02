#!/usr/bin/env python3
"""Create the A62 packet from frozen A61 with fresh attempt paths only.

A61 (bundled oneCCL control) never served: launched one minute after A60's
page-fault teardown, its workers soft-locked in the kernel and the host was
rebooted. A62 is the byte-identical A61 server (eager, tuned M1 W13-N32 map,
bundled oneCCL, external checkpoint, PLE-only UVA placement, 2304 max model
length, host guards) at attempt 62 / port 19734 on a fresh boot with GuC
70.72.1, for the same logprob-determinism probe at depths 8/64/256/2048.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A62_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-2304-ple-only-a61-bundledccl-w13n32.sh": "a1e5c07b183b276bd3b5463c05451480c85358165450a1816503e04058108c1e",
    "run-tp4-mtp0-2304-ple-only-a61-bundledccl-w13n32-client.sh": "4f442ec8490ee4ce433dd2d3dcce773e75a2a7645054f98ade4892d63ebc317e",
    "supervise-tp4-mtp0-2304-ple-only-a61-bundledccl-w13n32.sh": "09d424c48d78b81b31167fba44953ab76a73235d76d500ebd5ac16bdf1b9f9ee",
    "run-q38-a61-host-controlled.sh": "fda928d5336cc74f29af98eb787f83d984ac6f515f194fc344ee97d1d0e451ba",
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
        segment = segment.replace("attempt61", "attempt62")
        segment = segment.replace("19733", "19734")
        segment = segment.replace("ATTEMPT=61", "ATTEMPT=62")
        segment = segment.replace("a61", "a62")
        return segment.replace("A61", "A62")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19733" not in out
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
    launcher = source("launch-tp4-mtp0-2304-ple-only-a61-bundledccl-w13n32.sh")
    match = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert match
    launcher = replace_once(
        launcher, "expected_derived=" + match.group(1), "expected_derived=" + "0" * 64
    )
    launcher = successor(launcher)
    env = os.environ.copy()
    env["Q38_A62_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a62-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a62" in derived and "q38-ple2k-a61" not in derived
    assert (
        "oneccl-4ceafd1-b70-public" not in derived and "  --enforce-eager\n" in derived
    )
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )
    client = successor(
        source("run-tp4-mtp0-2304-ple-only-a61-bundledccl-w13n32-client.sh")
    )
    supervisor = successor(
        source("supervise-tp4-mtp0-2304-ple-only-a61-bundledccl-w13n32.sh")
    )
    supervisor = replace_once(
        supervisor,
        "expected_wrapper=a1e5c07b183b276bd3b5463c05451480c85358165450a1816503e04058108c1e",
        "expected_wrapper=" + digest(launcher),
    )
    supervisor = replace_once(
        supervisor,
        "expected_client=4f442ec8490ee4ce433dd2d3dcce773e75a2a7645054f98ade4892d63ebc317e",
        "expected_client=" + digest(client),
    )
    host = successor(source("run-q38-a61-host-controlled.sh"))
    host = replace_once(
        host,
        "expected_supervisor=09d424c48d78b81b31167fba44953ab76a73235d76d500ebd5ac16bdf1b9f9ee",
        "expected_supervisor=" + digest(supervisor),
    )
    emit("launch-tp4-mtp0-2304-ple-only-a62-bundledccl-w13n32.sh", launcher)
    emit("run-tp4-mtp0-2304-ple-only-a62-bundledccl-w13n32-client.sh", client)
    emit("supervise-tp4-mtp0-2304-ple-only-a62-bundledccl-w13n32.sh", supervisor)
    emit("run-q38-a62-host-controlled.sh", host)
    for name in (
        "launch-tp4-mtp0-2304-ple-only-a62-bundledccl-w13n32.sh",
        "run-tp4-mtp0-2304-ple-only-a62-bundledccl-w13n32-client.sh",
        "supervise-tp4-mtp0-2304-ple-only-a62-bundledccl-w13n32.sh",
        "run-q38-a62-host-controlled.sh",
    ):
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
