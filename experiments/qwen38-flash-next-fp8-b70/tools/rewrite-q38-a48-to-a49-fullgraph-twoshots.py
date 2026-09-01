#!/usr/bin/env python3
"""Create the path-only A49 successor and explicitly forward AER baselines."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A49_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-2304-ple-only-a48-fullgraph-twoshots.sh":
        "7f4366a6358c3a3aed6a1326b68e700519cfc591fcfce2b0ffd3d922118b2eb1",
    "run-tp4-mtp0-2304-ple-only-a48-fullgraph-twoshots-client.sh":
        "95a308a36a89414b661080df9945a621db7c9b6ba76e07b73a642d5d597e2a9a",
    "supervise-tp4-mtp0-2304-ple-only-a48-fullgraph-twoshots.sh":
        "e0e8a407c8ccbdd2e05146fe76bd7791a37f533ca572a4007266e258e8a0db11",
    "run-q38-a48-host-controlled.sh":
        "1ce70894278f81b6c3c32b21a9696f6098b21970af4649304ab0a3a11e1430b8",
}


def digest(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def source(name: str) -> str:
    path = ROOT / name
    data = path.read_bytes()
    assert digest(data) == SOURCES[name], f"source drift: {name}"
    text = data.decode()
    assert not any("a48" in value or "a49" in value for value in re.findall(r"[0-9a-f]{64}", text))
    return text


def successor(text: str) -> str:
    text = text.replace("attempt48", "attempt49")
    text = text.replace("19720", "19721")
    text = text.replace("ATTEMPT=48", "ATTEMPT=49")
    text = text.replace("a48", "a49")
    text = text.replace("A48", "A49")
    return text


def emit(name: str, text: str) -> None:
    path = ROOT / name
    if VALIDATE_ONLY:
        assert path.read_text(encoding="utf-8") == text, f"generated drift: {name}"
        return
    assert not path.exists(), f"refusing to overwrite {path}"
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def main() -> None:
    launcher = successor(source("launch-tp4-mtp0-2304-ple-only-a48-fullgraph-twoshots.sh"))
    launcher = launcher.replace(
        "expected_derived=a3bf49c3aad05f0245bc6ec1c0df19544860a7a2595d256a124af9a752bd108b",
        "expected_derived=" + "0" * 64,
    )
    env = os.environ.copy()
    env["Q38_A49_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    launcher = launcher.replace("expected_derived=" + "0" * 64, "expected_derived=" + digest(derived))

    client = successor(source("run-tp4-mtp0-2304-ple-only-a48-fullgraph-twoshots-client.sh"))
    client = client.replace("verify-q38-a49-fullgraph-runtime.py", "verify-q38-a48-fullgraph-runtime.py")

    supervisor = successor(source("supervise-tp4-mtp0-2304-ple-only-a48-fullgraph-twoshots.sh"))
    supervisor = supervisor.replace(
        "expected_wrapper=7f4366a6358c3a3aed6a1326b68e700519cfc591fcfce2b0ffd3d922118b2eb1",
        "expected_wrapper=" + digest(launcher),
    ).replace(
        "expected_client=95a308a36a89414b661080df9945a621db7c9b6ba76e07b73a642d5d597e2a9a",
        "expected_client=" + digest(client),
    )
    supervisor = supervisor.replace(
        "  HOME=/home/steve USER=steve LOGNAME=steve LANG=C.UTF-8 \\\n"
        "  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \\\n",
        "  HOME=/home/steve USER=steve LOGNAME=steve LANG=C.UTF-8 \\\n"
        "  Q38_A49_NVME_AER_BASELINE=\"$expected_nvme_aer_cor\" \\\n"
        "  Q38_A49_ROOT_AER_BASELINE=\"$expected_root_aer_cor\" \\\n"
        "  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \\\n",
        1,
    )

    host = successor(source("run-q38-a48-host-controlled.sh"))
    host = host.replace(
        "expected_supervisor=e0e8a407c8ccbdd2e05146fe76bd7791a37f533ca572a4007266e258e8a0db11",
        "expected_supervisor=" + digest(supervisor),
    )

    emit("launch-tp4-mtp0-2304-ple-only-a49-fullgraph-twoshots.sh", launcher)
    emit("run-tp4-mtp0-2304-ple-only-a49-fullgraph-twoshots-client.sh", client)
    emit("supervise-tp4-mtp0-2304-ple-only-a49-fullgraph-twoshots.sh", supervisor)
    emit("run-q38-a49-host-controlled.sh", host)


if __name__ == "__main__":
    main()
