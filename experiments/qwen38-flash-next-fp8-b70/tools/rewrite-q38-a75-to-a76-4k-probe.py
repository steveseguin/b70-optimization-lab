#!/usr/bin/env python3
"""Create the A76 packet from frozen A75 with fresh attempt paths only.

A75 never served: the supervisor's host-pressure guard (memory PSI full
avg10 > 10.0) fired during the workers' 12 GiB PLE offload pinning, a
reclaim transient from a warmed page cache. A76 is the byte-identical A75
server at attempt 76 / port 19748, launched after dropping the page cache.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A76_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-4352-ple-only-a75-fullgraphdet-w13n32.sh": "1e8b5c3cb5b43b01b935e6c611e6f346ebba746053370f91af4bbf410337e850",
    "run-tp4-mtp0-4352-ple-only-a75-fullgraphdet-w13n32-client.sh": "06944f94a3865aaf1a2c03631cf24f0abaf4026cd1d54cb70a7f0babfa1466f5",
    "supervise-tp4-mtp0-4352-ple-only-a75-fullgraphdet-w13n32.sh": "b9a9b423aaa51d507617e57df859a373290178678234076341e5118b589edbea",
    "run-q38-a75-host-controlled.sh": "50b390d6234dba1591c1878cda11594113e40df2f088f8f5df646c74b58e1c91",
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
        segment = segment.replace("attempt75", "attempt76")
        segment = segment.replace("19747", "19748")
        segment = segment.replace("ATTEMPT=75", "ATTEMPT=76")
        segment = segment.replace("a75", "a76")
        return segment.replace("A75", "A76")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19747" not in out
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
    launcher = source("launch-tp4-mtp0-4352-ple-only-a75-fullgraphdet-w13n32.sh")
    match = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert match
    launcher = replace_once(
        launcher, "expected_derived=" + match.group(1), "expected_derived=" + "0" * 64
    )
    launcher = successor(launcher)
    env = os.environ.copy()
    env["Q38_A76_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a76-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a76" in derived and "q38-ple2k-a75" not in derived
    assert "oneccl-4ceafd1-b70-public" in derived and "  --enforce-eager\n" not in derived
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )
    client = successor(
        source("run-tp4-mtp0-4352-ple-only-a75-fullgraphdet-w13n32-client.sh")
    )
    supervisor = successor(
        source("supervise-tp4-mtp0-4352-ple-only-a75-fullgraphdet-w13n32.sh")
    )
    supervisor = replace_once(
        supervisor,
        "expected_wrapper=1e8b5c3cb5b43b01b935e6c611e6f346ebba746053370f91af4bbf410337e850",
        "expected_wrapper=" + digest(launcher),
    )
    supervisor = replace_once(
        supervisor,
        "expected_client=06944f94a3865aaf1a2c03631cf24f0abaf4026cd1d54cb70a7f0babfa1466f5",
        "expected_client=" + digest(client),
    )
    host = successor(source("run-q38-a75-host-controlled.sh"))
    host = replace_once(
        host,
        "expected_supervisor=b9a9b423aaa51d507617e57df859a373290178678234076341e5118b589edbea",
        "expected_supervisor=" + digest(supervisor),
    )
    emit("launch-tp4-mtp0-4352-ple-only-a76-fullgraphdet-w13n32.sh", launcher)
    emit("run-tp4-mtp0-4352-ple-only-a76-fullgraphdet-w13n32-client.sh", client)
    emit("supervise-tp4-mtp0-4352-ple-only-a76-fullgraphdet-w13n32.sh", supervisor)
    emit("run-q38-a76-host-controlled.sh", host)
    for name in (
        "launch-tp4-mtp0-4352-ple-only-a76-fullgraphdet-w13n32.sh",
        "run-tp4-mtp0-4352-ple-only-a76-fullgraphdet-w13n32-client.sh",
        "supervise-tp4-mtp0-4352-ple-only-a76-fullgraphdet-w13n32.sh",
        "run-q38-a76-host-controlled.sh",
    ):
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
