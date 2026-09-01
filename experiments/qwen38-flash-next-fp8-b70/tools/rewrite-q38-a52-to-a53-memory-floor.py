#!/usr/bin/env python3
"""Create A53 by widening only A52's live memory headroom."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A53_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-2304-ple-only-a52-fullgraph-twoshots.sh":
        "05c8e37372870d66322c9d071eb9fd4c31a73e4b33035568baa8bda3f8807707",
    "run-tp4-mtp0-2304-ple-only-a52-fullgraph-twoshots-client.sh":
        "23341580a10daedc64ff9993f3be103103d5e90cb7353e877334ca38985529a4",
    "supervise-tp4-mtp0-2304-ple-only-a52-fullgraph-twoshots.sh":
        "f3bc6139446c04797f9235bf9e7d5b269aff25606f18ba1d3f7ba802a8c42d59",
    "run-q38-a52-host-controlled.sh":
        "33472abe3b64161f62c5aaffb6f419132e21ae051b8a1554224bc4c8405cfaf3",
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
        "a52" in value or "a53" in value
        for value in re.findall(r"[0-9a-f]{64}", text)
    )
    return text


def successor(text: str) -> str:
    text = text.replace("attempt52", "attempt53")
    text = text.replace("19724", "19725")
    text = text.replace("ATTEMPT=52", "ATTEMPT=53")
    text = text.replace("a52", "a53")
    return text.replace("A52", "A53")


def emit(name: str, text: str) -> None:
    path = ROOT / name
    if VALIDATE_ONLY:
        assert path.read_text(encoding="utf-8") == text, f"generated drift: {name}"
        return
    assert not path.exists(), f"refusing to overwrite {path}"
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def main() -> None:
    launcher = source("launch-tp4-mtp0-2304-ple-only-a52-fullgraph-twoshots.sh")
    assert launcher.count(
        "expected_derived=1dc280fb680dec39a4c11ec7fa77193e197249b3804ea1b9493116bfe1d281a2"
    ) == 1
    launcher = launcher.replace(
        "expected_derived=1dc280fb680dec39a4c11ec7fa77193e197249b3804ea1b9493116bfe1d281a2",
        "expected_derived=" + "0" * 64,
    )
    launcher = successor(launcher)
    env = os.environ.copy()
    env["Q38_A53_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a53-base.sh").unlink(missing_ok=True)
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )
    assert "expected_derived=" + digest(derived) in launcher

    client = successor(
        source("run-tp4-mtp0-2304-ple-only-a52-fullgraph-twoshots-client.sh")
    )

    supervisor = successor(
        source("supervise-tp4-mtp0-2304-ple-only-a52-fullgraph-twoshots.sh")
    )
    assert supervisor.count("(( mem_available_kib >= 28000000 )) || return 1") == 1
    supervisor = supervisor.replace(
        "(( mem_available_kib >= 28000000 )) || return 1",
        "(( mem_available_kib >= 16000000 )) || return 1",
    )
    supervisor = supervisor.replace(
        "expected_wrapper=05c8e37372870d66322c9d071eb9fd4c31a73e4b33035568baa8bda3f8807707",
        "expected_wrapper=" + digest(launcher),
    ).replace(
        "expected_client=23341580a10daedc64ff9993f3be103103d5e90cb7353e877334ca38985529a4",
        "expected_client=" + digest(client),
    )

    host = successor(source("run-q38-a52-host-controlled.sh"))
    host = host.replace(
        "expected_supervisor=f3bc6139446c04797f9235bf9e7d5b269aff25606f18ba1d3f7ba802a8c42d59",
        "expected_supervisor=" + digest(supervisor),
    )

    emit("launch-tp4-mtp0-2304-ple-only-a53-fullgraph-twoshots.sh", launcher)
    emit("run-tp4-mtp0-2304-ple-only-a53-fullgraph-twoshots-client.sh", client)
    emit("supervise-tp4-mtp0-2304-ple-only-a53-fullgraph-twoshots.sh", supervisor)
    emit("run-q38-a53-host-controlled.sh", host)


if __name__ == "__main__":
    main()
