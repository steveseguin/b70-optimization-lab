#!/usr/bin/env python3
"""Create the A58 server packet from frozen A57 with fresh attempt paths only.

A57's server (identical to A56: tuned M1 W13-N32 map, twoshots, full decode
graph, external checkpoint, host guards) froze the host at four-GPU worker
initialization on GuC 70.44.1. A58 is the byte-identical server at attempt
58 / port 19730 for the same depth-determinism probe, now on upstream GuC
70.72.1 loaded in place. No inference selector changes relative to A56/A57.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A58_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-2304-ple-only-a57-fullgraph-w13n32.sh": "c14b12c28032ee1cac35da1073c5c158c5d67e2b7aab0e4c726eb156e11aa679",
    "run-tp4-mtp0-2304-ple-only-a57-fullgraph-w13n32-client.sh": "aa99a5194ca5b58eee267359786a5c60dd7dd87e718a793bf37151d6461fd0de",
    "supervise-tp4-mtp0-2304-ple-only-a57-fullgraph-w13n32.sh": "7abd67acfca4c4969c5a0f70d5d1a267db08973c30a71d3a7ffe4d855619338f",
    "run-q38-a57-host-controlled.sh": "956aa7873327ec595058de9d6a829589ba7023cae6e1a48e83929e9536c4a2c3",
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
        segment = segment.replace("attempt57", "attempt58")
        segment = segment.replace("19729", "19730")
        segment = segment.replace("ATTEMPT=57", "ATTEMPT=58")
        segment = segment.replace("a57", "a58")
        return segment.replace("A57", "A58")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19729" not in out
    return out


def replace_once(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, f"anchor count != 1: {old[:80]!r}"
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
    launcher = source("launch-tp4-mtp0-2304-ple-only-a57-fullgraph-w13n32.sh")
    old_derived = "expected_derived=d07ed8276fd1b317b8ec157bf03140898d4777cd05551a972af7ebb7818e4491"
    launcher = replace_once(launcher, old_derived, "expected_derived=" + "0" * 64)
    launcher = successor(launcher)
    env = os.environ.copy()
    env["Q38_A58_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a58-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a58" in derived and "q38-ple2k-a57" not in derived
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )

    client = successor(
        source("run-tp4-mtp0-2304-ple-only-a57-fullgraph-w13n32-client.sh")
    )

    supervisor = successor(
        source("supervise-tp4-mtp0-2304-ple-only-a57-fullgraph-w13n32.sh")
    )
    supervisor = replace_once(
        supervisor,
        "expected_wrapper=c14b12c28032ee1cac35da1073c5c158c5d67e2b7aab0e4c726eb156e11aa679",
        "expected_wrapper=" + digest(launcher),
    )
    supervisor = replace_once(
        supervisor,
        "expected_client=aa99a5194ca5b58eee267359786a5c60dd7dd87e718a793bf37151d6461fd0de",
        "expected_client=" + digest(client),
    )

    host = successor(source("run-q38-a57-host-controlled.sh"))
    host = replace_once(
        host,
        "expected_supervisor=7abd67acfca4c4969c5a0f70d5d1a267db08973c30a71d3a7ffe4d855619338f",
        "expected_supervisor=" + digest(supervisor),
    )

    emit("launch-tp4-mtp0-2304-ple-only-a58-fullgraph-w13n32.sh", launcher)
    emit("run-tp4-mtp0-2304-ple-only-a58-fullgraph-w13n32-client.sh", client)
    emit("supervise-tp4-mtp0-2304-ple-only-a58-fullgraph-w13n32.sh", supervisor)
    emit("run-q38-a58-host-controlled.sh", host)
    for name in (
        "launch-tp4-mtp0-2304-ple-only-a58-fullgraph-w13n32.sh",
        "run-tp4-mtp0-2304-ple-only-a58-fullgraph-w13n32-client.sh",
        "supervise-tp4-mtp0-2304-ple-only-a58-fullgraph-w13n32.sh",
        "run-q38-a58-host-controlled.sh",
    ):
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
