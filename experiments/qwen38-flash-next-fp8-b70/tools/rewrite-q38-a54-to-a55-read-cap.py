#!/usr/bin/env python3
"""Create A55 from A54 with fresh paths and an 8-GiB local-read cap."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A55_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-2304-ple-only-a54-fullgraph-twoshots.sh": "9c89ff47eb8a46efa0b3fcec50114f8f46743e489536ec344731bce5b83e22a1",
    "run-tp4-mtp0-2304-ple-only-a54-fullgraph-twoshots-client.sh": "959a5c7b1ac9c8b28e59a90dada2bd11a81e1f9b87dc42bd55ba463bb054a82c",
    "supervise-tp4-mtp0-2304-ple-only-a54-fullgraph-twoshots.sh": "54db6272267468f51cb7d6eb41a2915b674ed9e0d2ff347c091d0e0b99d77a86",
    "run-q38-a54-host-controlled.sh": "82d676349b0b4fdf90ad7874afe8ae1e01ec3f6b8b9f4c46d39bf35a5d5d2be3",
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
        for marker in ("a54", "19726")
    )
    return text


def successor(text: str) -> str:
    text = text.replace("attempt54", "attempt55")
    text = text.replace("19726", "19727")
    text = text.replace("ATTEMPT=54", "ATTEMPT=55")
    text = text.replace("a54", "a55")
    return text.replace("A54", "A55")


def emit(name: str, text: str) -> None:
    path = ROOT / name
    if VALIDATE_ONLY:
        assert path.read_text(encoding="utf-8") == text, f"generated drift: {name}"
        return
    assert not path.exists(), f"refusing to overwrite {path}"
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def main() -> None:
    launcher = source("launch-tp4-mtp0-2304-ple-only-a54-fullgraph-twoshots.sh")
    old_derived = (
        "expected_derived="
        "7b4d1c9b2b07aad4c43fea7b03a9cb881559775bb4aeb1010b1a9f5b5ac2729e"
    )
    assert launcher.count(old_derived) == 1
    assert launcher.count("<= 8388608") == 1
    launcher = launcher.replace(old_derived, "expected_derived=" + "0" * 64)
    launcher = successor(launcher).replace("<= 8388608", "<= 16777216")
    env = os.environ.copy()
    env["Q38_A55_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a55-base.sh").unlink(missing_ok=True)
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )

    client = successor(
        source("run-tp4-mtp0-2304-ple-only-a54-fullgraph-twoshots-client.sh")
    )
    supervisor = successor(
        source("supervise-tp4-mtp0-2304-ple-only-a54-fullgraph-twoshots.sh")
    )
    assert supervisor.count("max_nvme_sectors_read_delta=8388608") == 1
    supervisor = supervisor.replace(
        "max_nvme_sectors_read_delta=8388608",
        "max_nvme_sectors_read_delta=16777216",
    )
    supervisor = supervisor.replace(
        "expected_wrapper=9c89ff47eb8a46efa0b3fcec50114f8f46743e489536ec344731bce5b83e22a1",
        "expected_wrapper=" + digest(launcher),
    ).replace(
        "expected_client=959a5c7b1ac9c8b28e59a90dada2bd11a81e1f9b87dc42bd55ba463bb054a82c",
        "expected_client=" + digest(client),
    )

    host = successor(source("run-q38-a54-host-controlled.sh"))
    host = host.replace(
        "expected_supervisor=54db6272267468f51cb7d6eb41a2915b674ed9e0d2ff347c091d0e0b99d77a86",
        "expected_supervisor=" + digest(supervisor),
    )

    emit("launch-tp4-mtp0-2304-ple-only-a55-fullgraph-twoshots.sh", launcher)
    emit("run-tp4-mtp0-2304-ple-only-a55-fullgraph-twoshots-client.sh", client)
    emit("supervise-tp4-mtp0-2304-ple-only-a55-fullgraph-twoshots.sh", supervisor)
    emit("run-q38-a55-host-controlled.sh", host)


if __name__ == "__main__":
    main()
