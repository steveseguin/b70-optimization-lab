#!/usr/bin/env python3
"""Create A52 by lowering only A51's live memory floor."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A52_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-2304-ple-only-a51-fullgraph-twoshots.sh":
        "1513d8e952b85d4ce6a4ef19f9c5cbefeab56d620ebe34f8ae4a4cffdd520a2f",
    "run-tp4-mtp0-2304-ple-only-a51-fullgraph-twoshots-client.sh":
        "673f396e14176f229efd856b1a0c7c8b527912bd7bb0345bd57036a4db5d66ff",
    "supervise-tp4-mtp0-2304-ple-only-a51-fullgraph-twoshots.sh":
        "0928175d9716caf1537fe8dbf11b1e323abd6cd0496d329b732722ef47caeea1",
    "run-q38-a51-host-controlled.sh":
        "32233dec06891fb3ff7b4db42769ed240886959cb875f5ff5453e4960bca428b",
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
        "a51" in value or "a52" in value
        for value in re.findall(r"[0-9a-f]{64}", text)
    )
    return text


def successor(text: str) -> str:
    text = text.replace("attempt51", "attempt52")
    text = text.replace("19723", "19724")
    text = text.replace("ATTEMPT=51", "ATTEMPT=52")
    text = text.replace("a51", "a52")
    return text.replace("A51", "A52")


def emit(name: str, text: str) -> None:
    path = ROOT / name
    if VALIDATE_ONLY:
        assert path.read_text(encoding="utf-8") == text, f"generated drift: {name}"
        return
    assert not path.exists(), f"refusing to overwrite {path}"
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def main() -> None:
    launcher = successor(
        source("launch-tp4-mtp0-2304-ple-only-a51-fullgraph-twoshots.sh")
    )
    launcher = launcher.replace(
        "expected_derived=c2469e79014a3827391605f168a562495ad39976188954340803ef2cf31a3442",
        "expected_derived=" + "0" * 64,
    )
    env = os.environ.copy()
    env["Q38_A52_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )

    client = successor(
        source("run-tp4-mtp0-2304-ple-only-a51-fullgraph-twoshots-client.sh")
    )

    supervisor = successor(
        source("supervise-tp4-mtp0-2304-ple-only-a51-fullgraph-twoshots.sh")
    )
    assert supervisor.count("(( mem_available_kib >= 32000000 )) || return 1") == 1
    supervisor = supervisor.replace(
        "(( mem_available_kib >= 32000000 )) || return 1",
        "(( mem_available_kib >= 28000000 )) || return 1",
    )
    supervisor = supervisor.replace(
        "expected_wrapper=1513d8e952b85d4ce6a4ef19f9c5cbefeab56d620ebe34f8ae4a4cffdd520a2f",
        "expected_wrapper=" + digest(launcher),
    ).replace(
        "expected_client=673f396e14176f229efd856b1a0c7c8b527912bd7bb0345bd57036a4db5d66ff",
        "expected_client=" + digest(client),
    )

    host = successor(source("run-q38-a51-host-controlled.sh"))
    host = host.replace(
        "expected_supervisor=0928175d9716caf1537fe8dbf11b1e323abd6cd0496d329b732722ef47caeea1",
        "expected_supervisor=" + digest(supervisor),
    )

    emit("launch-tp4-mtp0-2304-ple-only-a52-fullgraph-twoshots.sh", launcher)
    emit("run-tp4-mtp0-2304-ple-only-a52-fullgraph-twoshots-client.sh", client)
    emit("supervise-tp4-mtp0-2304-ple-only-a52-fullgraph-twoshots.sh", supervisor)
    emit("run-q38-a52-host-controlled.sh", host)


if __name__ == "__main__":
    main()
