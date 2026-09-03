#!/usr/bin/env python3
"""Create the A77 packet from frozen A76 with fresh attempt paths only.

A76 was logit-exact through 4096-token prefill. A77 is the byte-identical
server at attempt 77 / port 19749, an independently started repeat of the
same probe so the 4K candidate hash is reproduced across two servers.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A77_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-4352-ple-only-a76-fullgraphdet-w13n32.sh": "0f58c646f6573f724d5b691cd228586dba70ce9ae72144d40df0463b458435fd",
    "run-tp4-mtp0-4352-ple-only-a76-fullgraphdet-w13n32-client.sh": "081d4cdcc729156f5a7a08578cf658fa70f91036bdbcb3ab5e3ef2e3da5f7d9f",
    "supervise-tp4-mtp0-4352-ple-only-a76-fullgraphdet-w13n32.sh": "ec4dc77f53595915a222f3dbb7701a5831dbc1b587487a8d132d3490410b25b0",
    "run-q38-a76-host-controlled.sh": "cfc4dc36f5f61c3545e05ee79bfba7c02551c6033d95007d4c95d5679e4329fe",
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
        segment = segment.replace("attempt76", "attempt77")
        segment = segment.replace("19748", "19749")
        segment = segment.replace("ATTEMPT=76", "ATTEMPT=77")
        segment = segment.replace("a76", "a77")
        return segment.replace("A76", "A77")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19748" not in out
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
    launcher = source("launch-tp4-mtp0-4352-ple-only-a76-fullgraphdet-w13n32.sh")
    match = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert match
    launcher = replace_once(
        launcher, "expected_derived=" + match.group(1), "expected_derived=" + "0" * 64
    )
    launcher = successor(launcher)
    env = os.environ.copy()
    env["Q38_A77_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a77-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a77" in derived and "q38-ple2k-a76" not in derived
    assert "oneccl-4ceafd1-b70-public" in derived and "  --enforce-eager\n" not in derived
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )
    client = successor(
        source("run-tp4-mtp0-4352-ple-only-a76-fullgraphdet-w13n32-client.sh")
    )
    supervisor = successor(
        source("supervise-tp4-mtp0-4352-ple-only-a76-fullgraphdet-w13n32.sh")
    )
    supervisor = replace_once(
        supervisor,
        "expected_wrapper=0f58c646f6573f724d5b691cd228586dba70ce9ae72144d40df0463b458435fd",
        "expected_wrapper=" + digest(launcher),
    )
    supervisor = replace_once(
        supervisor,
        "expected_client=081d4cdcc729156f5a7a08578cf658fa70f91036bdbcb3ab5e3ef2e3da5f7d9f",
        "expected_client=" + digest(client),
    )
    host = successor(source("run-q38-a76-host-controlled.sh"))
    host = replace_once(
        host,
        "expected_supervisor=ec4dc77f53595915a222f3dbb7701a5831dbc1b587487a8d132d3490410b25b0",
        "expected_supervisor=" + digest(supervisor),
    )
    emit("launch-tp4-mtp0-4352-ple-only-a77-fullgraphdet-w13n32.sh", launcher)
    emit("run-tp4-mtp0-4352-ple-only-a77-fullgraphdet-w13n32-client.sh", client)
    emit("supervise-tp4-mtp0-4352-ple-only-a77-fullgraphdet-w13n32.sh", supervisor)
    emit("run-q38-a77-host-controlled.sh", host)
    for name in (
        "launch-tp4-mtp0-4352-ple-only-a77-fullgraphdet-w13n32.sh",
        "run-tp4-mtp0-4352-ple-only-a77-fullgraphdet-w13n32-client.sh",
        "supervise-tp4-mtp0-4352-ple-only-a77-fullgraphdet-w13n32.sh",
        "run-q38-a77-host-controlled.sh",
    ):
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
