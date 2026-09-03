#!/usr/bin/env python3
"""Create the A68 battery packet from frozen A67 with fresh attempt paths only.

A67 (full decode graph, public oneCCL twoshots, tuned M1 W13-N32 map,
VLLM_XPU_MKLDNN_DETERMINISTIC=1) is probed for logit exactness; A68 is the
byte-identical server at attempt 68 / port 19740 on which the frozen client
battery (recovery canary, quality suite with 16-repeat and exact 2K needle,
short rows, exact-2K rows) runs instead of the probe.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A68_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-2304-ple-only-a67-fullgraphdet-w13n32.sh": "1c41a023a84c65daee0b9a7a7e331eb8456bae26ef917b2db94d6f5a3fa4a661",
    "run-tp4-mtp0-2304-ple-only-a67-fullgraphdet-w13n32-client.sh": "0480fae03a05540cd2a416669f10600b72e6c11a498021c660476dd0d4f2c17f",
    "supervise-tp4-mtp0-2304-ple-only-a67-fullgraphdet-w13n32.sh": "eadbcc5e0c67dd9a9611c3fbd6263d45e1876bcc23a1cea21fca8c01108978c3",
    "run-q38-a67-host-controlled.sh": "e87a4c3a36c55e8012c02083dd00a79cb00b52d1fb549a6f1a2e59d7def0b286",
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
        segment = segment.replace("attempt67", "attempt68")
        segment = segment.replace("19739", "19740")
        segment = segment.replace("ATTEMPT=67", "ATTEMPT=68")
        segment = segment.replace("a67", "a68")
        return segment.replace("A67", "A68")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19739" not in out
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
    launcher = source("launch-tp4-mtp0-2304-ple-only-a67-fullgraphdet-w13n32.sh")
    match = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert match
    launcher = replace_once(
        launcher, "expected_derived=" + match.group(1), "expected_derived=" + "0" * 64
    )
    launcher = successor(launcher)
    env = os.environ.copy()
    env["Q38_A68_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a68-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a68" in derived and "q38-ple2k-a67" not in derived
    assert "oneccl-4ceafd1-b70-public" in derived and "  --enforce-eager\n" not in derived
    assert "export VLLM_XPU_MKLDNN_DETERMINISTIC=1\n" in derived
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )
    client = successor(
        source("run-tp4-mtp0-2304-ple-only-a67-fullgraphdet-w13n32-client.sh")
    )
    supervisor = successor(
        source("supervise-tp4-mtp0-2304-ple-only-a67-fullgraphdet-w13n32.sh")
    )
    supervisor = replace_once(
        supervisor,
        "expected_wrapper=1c41a023a84c65daee0b9a7a7e331eb8456bae26ef917b2db94d6f5a3fa4a661",
        "expected_wrapper=" + digest(launcher),
    )
    supervisor = replace_once(
        supervisor,
        "expected_client=0480fae03a05540cd2a416669f10600b72e6c11a498021c660476dd0d4f2c17f",
        "expected_client=" + digest(client),
    )
    host = successor(source("run-q38-a67-host-controlled.sh"))
    host = replace_once(
        host,
        "expected_supervisor=eadbcc5e0c67dd9a9611c3fbd6263d45e1876bcc23a1cea21fca8c01108978c3",
        "expected_supervisor=" + digest(supervisor),
    )
    emit("launch-tp4-mtp0-2304-ple-only-a68-fullgraphdet-w13n32.sh", launcher)
    emit("run-tp4-mtp0-2304-ple-only-a68-fullgraphdet-w13n32-client.sh", client)
    emit("supervise-tp4-mtp0-2304-ple-only-a68-fullgraphdet-w13n32.sh", supervisor)
    emit("run-q38-a68-host-controlled.sh", host)
    for name in (
        "launch-tp4-mtp0-2304-ple-only-a68-fullgraphdet-w13n32.sh",
        "run-tp4-mtp0-2304-ple-only-a68-fullgraphdet-w13n32-client.sh",
        "supervise-tp4-mtp0-2304-ple-only-a68-fullgraphdet-w13n32.sh",
        "run-q38-a68-host-controlled.sh",
    ):
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
