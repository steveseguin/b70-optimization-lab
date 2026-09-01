#!/usr/bin/env python3
"""Create A50 from A49 with the identical checkpoint read from USB storage."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A50_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-2304-ple-only-a49-fullgraph-twoshots.sh":
        "e9b8884bf1c338daeac991c739826f66860b73316b16bf21793ca4c4fd6da67c",
    "run-tp4-mtp0-2304-ple-only-a49-fullgraph-twoshots-client.sh":
        "626ae56cc9a8fc4965604bea29f16ea817ca7b6ccea68c97164154ea3338dc36",
    "supervise-tp4-mtp0-2304-ple-only-a49-fullgraph-twoshots.sh":
        "d314ee9e1d4f227e4858fef8315fec9cf886e28eda81a5bbda797ea5f5f36e15",
    "run-q38-a49-host-controlled.sh":
        "4b407d90a6e2a457a6ccbce6bd3a902c5437458461689a0fa64c4aea9f6ad311",
}
LOCAL_MODEL = "/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8"
EXTERNAL_MODEL = "/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8"


def digest(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def source(name: str) -> str:
    data = (ROOT / name).read_bytes()
    assert digest(data) == SOURCES[name], f"source drift: {name}"
    text = data.decode()
    assert not any("a49" in value or "a50" in value for value in re.findall(r"[0-9a-f]{64}", text))
    return text


def successor(text: str) -> str:
    text = text.replace("attempt49", "attempt50")
    text = text.replace("19721", "19722")
    text = text.replace("ATTEMPT=49", "ATTEMPT=50")
    text = text.replace("a49", "a50")
    text = text.replace("A49", "A50")
    return text.replace(LOCAL_MODEL, EXTERNAL_MODEL)


def emit(name: str, text: str) -> None:
    path = ROOT / name
    if VALIDATE_ONLY:
        assert path.read_text(encoding="utf-8") == text, f"generated drift: {name}"
        return
    assert not path.exists(), f"refusing to overwrite {path}"
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def main() -> None:
    launcher = successor(source("launch-tp4-mtp0-2304-ple-only-a49-fullgraph-twoshots.sh"))
    launcher = launcher.replace(
        "expected_derived=9fd3e3b0de618207ec7adfbdc9db5800467b33c8176ae2b8e5a074b812ae36ce",
        "expected_derived=" + "0" * 64,
    )
    env = os.environ.copy()
    env["Q38_A50_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    launcher = launcher.replace("expected_derived=" + "0" * 64, "expected_derived=" + digest(derived))

    client = successor(source("run-tp4-mtp0-2304-ple-only-a49-fullgraph-twoshots-client.sh"))
    client = client.replace("verify-q38-a50-fullgraph-runtime.py", "verify-q38-a48-fullgraph-runtime.py")

    supervisor = successor(source("supervise-tp4-mtp0-2304-ple-only-a49-fullgraph-twoshots.sh"))
    supervisor = supervisor.replace(
        "expected_wrapper=e9b8884bf1c338daeac991c739826f66860b73316b16bf21793ca4c4fd6da67c",
        "expected_wrapper=" + digest(launcher),
    ).replace(
        "expected_client=626ae56cc9a8fc4965604bea29f16ea817ca7b6ccea68c97164154ea3338dc36",
        "expected_client=" + digest(client),
    )

    host = successor(source("run-q38-a49-host-controlled.sh"))
    host = host.replace(
        "expected_supervisor=d314ee9e1d4f227e4858fef8315fec9cf886e28eda81a5bbda797ea5f5f36e15",
        "expected_supervisor=" + digest(supervisor),
    )

    emit("launch-tp4-mtp0-2304-ple-only-a50-fullgraph-twoshots.sh", launcher)
    emit("run-tp4-mtp0-2304-ple-only-a50-fullgraph-twoshots-client.sh", client)
    emit("supervise-tp4-mtp0-2304-ple-only-a50-fullgraph-twoshots.sh", supervisor)
    emit("run-q38-a50-host-controlled.sh", host)


if __name__ == "__main__":
    main()
