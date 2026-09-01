#!/usr/bin/env python3
"""Create A54 as an exact path-only successor to A53."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A54_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-2304-ple-only-a53-fullgraph-twoshots.sh":
        "21d8847459900f60f496ae596effecdcd90cb0bff263b1cdb3fbee263010ab88",
    "run-tp4-mtp0-2304-ple-only-a53-fullgraph-twoshots-client.sh":
        "5e1229459998d3aeea9d93268b5abc8bc783021446ecc0bad4a0daa07eab2005",
    "supervise-tp4-mtp0-2304-ple-only-a53-fullgraph-twoshots.sh":
        "59e00337ed0a9260261ca706e6f82147d8a659ca2f0072c8570932b7df080ad2",
    "run-q38-a53-host-controlled.sh":
        "82c3a4efa88b0c87f90d02dd323c851c7eb4618a10f35cd0cc1d380e4395091a",
}


def digest(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def source(name: str) -> str:
    data = (ROOT / name).read_bytes()
    assert digest(data) == SOURCES[name], f"source drift: {name}"
    text = data.decode()
    assert not any(
        marker in value
        for value in re.findall(r"[0-9a-f]{64}", text)
        for marker in ("a53", "a54", "19725", "19726")
    )
    return text


def successor(text: str) -> str:
    text = text.replace("attempt53", "attempt54")
    text = text.replace("19725", "19726")
    text = text.replace("ATTEMPT=53", "ATTEMPT=54")
    text = text.replace("a53", "a54")
    return text.replace("A53", "A54")


def emit(name: str, text: str) -> None:
    path = ROOT / name
    if VALIDATE_ONLY:
        assert path.read_text(encoding="utf-8") == text, f"generated drift: {name}"
        return
    assert not path.exists(), f"refusing to overwrite {path}"
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def main() -> None:
    launcher = source("launch-tp4-mtp0-2304-ple-only-a53-fullgraph-twoshots.sh")
    old_derived = (
        "expected_derived="
        "76d687f8febdfa7393192471b9c324a0a2858c250af9f777d11fb9beceb5766d"
    )
    assert launcher.count(old_derived) == 1
    launcher = launcher.replace(old_derived, "expected_derived=" + "0" * 64)
    launcher = successor(launcher)
    env = os.environ.copy()
    env["Q38_A54_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a54-base.sh").unlink(missing_ok=True)
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )

    client = successor(
        source("run-tp4-mtp0-2304-ple-only-a53-fullgraph-twoshots-client.sh")
    )
    supervisor = successor(
        source("supervise-tp4-mtp0-2304-ple-only-a53-fullgraph-twoshots.sh")
    )
    supervisor = supervisor.replace(
        "expected_wrapper=21d8847459900f60f496ae596effecdcd90cb0bff263b1cdb3fbee263010ab88",
        "expected_wrapper=" + digest(launcher),
    ).replace(
        "expected_client=5e1229459998d3aeea9d93268b5abc8bc783021446ecc0bad4a0daa07eab2005",
        "expected_client=" + digest(client),
    )

    host = successor(source("run-q38-a53-host-controlled.sh"))
    host = host.replace(
        "expected_supervisor=59e00337ed0a9260261ca706e6f82147d8a659ca2f0072c8570932b7df080ad2",
        "expected_supervisor=" + digest(supervisor),
    )

    emit("launch-tp4-mtp0-2304-ple-only-a54-fullgraph-twoshots.sh", launcher)
    emit("run-tp4-mtp0-2304-ple-only-a54-fullgraph-twoshots-client.sh", client)
    emit("supervise-tp4-mtp0-2304-ple-only-a54-fullgraph-twoshots.sh", supervisor)
    emit("run-q38-a54-host-controlled.sh", host)


if __name__ == "__main__":
    main()
