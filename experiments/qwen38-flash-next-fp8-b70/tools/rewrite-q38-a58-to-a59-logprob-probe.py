#!/usr/bin/env python3
"""Create the A59 server packet from frozen A58 with fresh attempt paths only.

A59 is the byte-identical A56/A57/A58 server (tuned M1 W13-N32 map, twoshots,
full decode graph, external checkpoint, host guards) at attempt 59 / port
19731 for the logprob-resolution determinism probe
(`probe-q38-a59-logprob-determinism.py`). No inference selector changes.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A59_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-2304-ple-only-a58-fullgraph-w13n32.sh": "33e88a824d6bb18ace01f250ad952f29bb4741d731ab3cc537c75e5b36269a82",
    "run-tp4-mtp0-2304-ple-only-a58-fullgraph-w13n32-client.sh": "30735b72cadc3b9bc88aca76e11da5c532f0767f9f9a6053770976846069a6ce",
    "supervise-tp4-mtp0-2304-ple-only-a58-fullgraph-w13n32.sh": "cfef443421466b38176e51c14e6285c3e7a67f545739aed1efdc0c1c5b7c7dfe",
    "run-q38-a58-host-controlled.sh": "ff616929211e1d96b495ee1a53d6473b38d1b2e1ba92e5a3a3f45422dbcdd9f4",
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
        segment = segment.replace("attempt58", "attempt59")
        segment = segment.replace("19730", "19731")
        segment = segment.replace("ATTEMPT=58", "ATTEMPT=59")
        segment = segment.replace("a58", "a59")
        return segment.replace("A58", "A59")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19730" not in out
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
    launcher = source("launch-tp4-mtp0-2304-ple-only-a58-fullgraph-w13n32.sh")
    old_derived = "expected_derived=20cf26a3f3238112831384548cec839c4fb9af23b03a8168b4ba7c869cc1d61e"
    launcher = replace_once(launcher, old_derived, "expected_derived=" + "0" * 64)
    launcher = successor(launcher)
    env = os.environ.copy()
    env["Q38_A59_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a59-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a59" in derived and "q38-ple2k-a58" not in derived
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )
    client = successor(
        source("run-tp4-mtp0-2304-ple-only-a58-fullgraph-w13n32-client.sh")
    )
    supervisor = successor(
        source("supervise-tp4-mtp0-2304-ple-only-a58-fullgraph-w13n32.sh")
    )
    supervisor = replace_once(
        supervisor,
        "expected_wrapper=33e88a824d6bb18ace01f250ad952f29bb4741d731ab3cc537c75e5b36269a82",
        "expected_wrapper=" + digest(launcher),
    )
    supervisor = replace_once(
        supervisor,
        "expected_client=30735b72cadc3b9bc88aca76e11da5c532f0767f9f9a6053770976846069a6ce",
        "expected_client=" + digest(client),
    )
    host = successor(source("run-q38-a58-host-controlled.sh"))
    host = replace_once(
        host,
        "expected_supervisor=cfef443421466b38176e51c14e6285c3e7a67f545739aed1efdc0c1c5b7c7dfe",
        "expected_supervisor=" + digest(supervisor),
    )
    emit("launch-tp4-mtp0-2304-ple-only-a59-fullgraph-w13n32.sh", launcher)
    emit("run-tp4-mtp0-2304-ple-only-a59-fullgraph-w13n32-client.sh", client)
    emit("supervise-tp4-mtp0-2304-ple-only-a59-fullgraph-w13n32.sh", supervisor)
    emit("run-q38-a59-host-controlled.sh", host)
    for name in (
        "launch-tp4-mtp0-2304-ple-only-a59-fullgraph-w13n32.sh",
        "run-tp4-mtp0-2304-ple-only-a59-fullgraph-w13n32-client.sh",
        "supervise-tp4-mtp0-2304-ple-only-a59-fullgraph-w13n32.sh",
        "run-q38-a59-host-controlled.sh",
    ):
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
