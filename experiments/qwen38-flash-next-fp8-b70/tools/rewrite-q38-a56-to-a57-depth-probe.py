#!/usr/bin/env python3
"""Create the A57 server packet from frozen A56 with fresh attempt paths only.

A57 is a diagnostic: the identical A56 server (tuned M1 W13-N32 map, twoshots,
full decode graph, external checkpoint, host guards) is launched under the
frozen launcher/supervisor/host wrapper at attempt 57 / port 19729, and a
separate depth-determinism probe client (`probe-q38-a57-depth-determinism.sh`)
replaces the lossless battery. The frozen A57 client generated here is kept
only so the supervisor's hash pins resolve; the probe writes the stop file
itself and the supervisor's stop is therefore recorded as invalid (rc 70),
which is the expected end state of a diagnostic arm. No inference selector
changes relative to A56.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A57_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-2304-ple-only-a56-fullgraph-w13n32.sh": "dfd7d0671c70a45be5b270800c5d033a521876124b109086b027f0fbdd8bdce0",
    "run-tp4-mtp0-2304-ple-only-a56-fullgraph-w13n32-client.sh": "ed23aa1e34216445a64228f64025b679d18167dd240e75f301e6860297f037c5",
    "supervise-tp4-mtp0-2304-ple-only-a56-fullgraph-w13n32.sh": "f5f59dba379b36ec9f7e3252bf81fb04466d8aee6a7c23138b6fe04db64dc131",
    "run-q38-a56-host-controlled.sh": "85bdae253355a33f5e22b53264079601527cea0bb0adf6e7de3113691dfe1a1a",
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
        segment = segment.replace("attempt56", "attempt57")
        segment = segment.replace("19728", "19729")
        segment = segment.replace("ATTEMPT=56", "ATTEMPT=57")
        segment = segment.replace("a56", "a57")
        return segment.replace("A56", "A57")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19728" not in out
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
    launcher = source("launch-tp4-mtp0-2304-ple-only-a56-fullgraph-w13n32.sh")
    old_derived = "expected_derived=b6cae5abedbe8052fc776be7d0648e58c72a2d9e5da073e03b791e32d1462dd3"
    launcher = replace_once(launcher, old_derived, "expected_derived=" + "0" * 64)
    launcher = successor(launcher)
    env = os.environ.copy()
    env["Q38_A57_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a57-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a57" in derived and "q38-ple2k-a56" not in derived
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )

    client = successor(
        source("run-tp4-mtp0-2304-ple-only-a56-fullgraph-w13n32-client.sh")
    )

    supervisor = successor(
        source("supervise-tp4-mtp0-2304-ple-only-a56-fullgraph-w13n32.sh")
    )
    supervisor = replace_once(
        supervisor,
        "expected_wrapper=dfd7d0671c70a45be5b270800c5d033a521876124b109086b027f0fbdd8bdce0",
        "expected_wrapper=" + digest(launcher),
    )
    supervisor = replace_once(
        supervisor,
        "expected_client=ed23aa1e34216445a64228f64025b679d18167dd240e75f301e6860297f037c5",
        "expected_client=" + digest(client),
    )

    host = successor(source("run-q38-a56-host-controlled.sh"))
    host = replace_once(
        host,
        "expected_supervisor=f5f59dba379b36ec9f7e3252bf81fb04466d8aee6a7c23138b6fe04db64dc131",
        "expected_supervisor=" + digest(supervisor),
    )

    emit("launch-tp4-mtp0-2304-ple-only-a57-fullgraph-w13n32.sh", launcher)
    emit("run-tp4-mtp0-2304-ple-only-a57-fullgraph-w13n32-client.sh", client)
    emit("supervise-tp4-mtp0-2304-ple-only-a57-fullgraph-w13n32.sh", supervisor)
    emit("run-q38-a57-host-controlled.sh", host)
    for name in (
        "launch-tp4-mtp0-2304-ple-only-a57-fullgraph-w13n32.sh",
        "run-tp4-mtp0-2304-ple-only-a57-fullgraph-w13n32-client.sh",
        "supervise-tp4-mtp0-2304-ple-only-a57-fullgraph-w13n32.sh",
        "run-q38-a57-host-controlled.sh",
    ):
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
