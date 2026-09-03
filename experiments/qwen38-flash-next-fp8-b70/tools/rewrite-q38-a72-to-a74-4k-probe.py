#!/usr/bin/env python3
"""Create the A72 receipt-repair packet from frozen A67 with fresh attempt paths only.

A67 (full decode graph, public oneCCL twoshots, tuned M1 W13-N32 map,
VLLM_XPU_MKLDNN_DETERMINISTIC=1) is probed for logit exactness; A72 is the
A71 server at attempt 72 / port 19744 on the overlay head that repairs the
graph-dispatch stats receipt (2169dbfe38c2954edc5ae50e94f68d45be071b79), with the W13-N32 verifier's
new hash pinned on which the frozen client
battery (recovery canary, quality suite with 16-repeat and exact 2K needle,
short rows, exact-2K rows) runs instead of the probe. One guard changes: the
bounded root-NVMe read cap (launcher pre-check and supervisor per-second
guard) rises from 16,777,216 to 134,217,728 sectors, because A66/A67 showed
mapped runtime pages being re-faulted at about 3.4 GiB per minute under the
server's host-memory pressure with zero AER events; the AER guard (at most 64
corrected events) is unchanged.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A74_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-2304-ple-only-a72-fullgraphdet-w13n32.sh": "d4a363c6f88e5241bd12d586bafe99609b0cb5834f6e6a5b20d5b8675ca4d6f9",
    "run-tp4-mtp0-2304-ple-only-a72-fullgraphdet-w13n32-client.sh": "676c38eccf953828c21798a8b8b2f900a78962b5a1f217bd488c5a7b4fd23ca6",
    "supervise-tp4-mtp0-2304-ple-only-a72-fullgraphdet-w13n32.sh": "085c7687720ba0b6b386ce5be29a5acec1a93a751d7c9bad54d75256fd068414",
    "run-q38-a72-host-controlled.sh": "343f572afab939fc0fce7fa0d2608dc436a424d958608b599dee0e660bf6ca56",
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
        segment = segment.replace("attempt72", "attempt74")
        segment = segment.replace("19744", "19746")
        segment = segment.replace("ATTEMPT=72", "ATTEMPT=74")
        segment = segment.replace("a72", "a74")
        segment = segment.replace("A72", "A74")
        return segment.replace("mtp0-2304-ple-only", "mtp0-4352-ple-only")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert "19744" not in out and "attempt72" not in out
    return out


def replace_once(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, f"anchor count != 1: {old[:90]!r}"
    return text.replace(old, new)


def replace_n(text: str, old: str, new: str, n: int) -> str:
    assert text.count(old) == n, f"anchor count {text.count(old)} != {n}: {old[:90]!r}"
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
    launcher = source("launch-tp4-mtp0-2304-ple-only-a72-fullgraphdet-w13n32.sh")
    match = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert match
    launcher = replace_once(
        launcher, "expected_derived=" + match.group(1), "expected_derived=" + "0" * 64
    )
    # 4352-token capacity: the awk rule that freezes the derived base, its
    # message, the static assertion on the derived text, and the export. The
    # 128 MiB cache stays (A9/A10 served 4352 tokens with it: 4,747 cache
    # tokens); the bounded-read cap literal 134217728 is untouched.
    launcher = replace_once(
        launcher,
        '  print "[[ \\"${max_model_len}\\" == \\"2304\\" ]] || {"\n',
        '  print "[[ \\"${max_model_len}\\" == \\"4352\\" ]] || {"\n',
    )
    launcher = replace_once(
        launcher,
        "FAIL: PLE-only base is frozen to MAX_MODEL_LEN=2304",
        "FAIL: PLE-only base is frozen to MAX_MODEL_LEN=4352",
    )
    launcher = replace_once(
        launcher,
        """grep -Fxq '[[ "${max_model_len}" == "2304" ]] || {' "$derived"\n""",
        """grep -Fxq '[[ "${max_model_len}" == "4352" ]] || {' "$derived"\n""",
    )
    launcher = replace_once(launcher, "MAX_MODEL_LEN=2304 ATTEMPT=72", "MAX_MODEL_LEN=4352 ATTEMPT=72")
    launcher = successor(launcher)

    env = os.environ.copy()
    env["Q38_A74_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a74-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a74" in derived and "q38-ple2k-a72" not in derived
    assert "oneccl-4ceafd1-b70-public" in derived and "  --enforce-eager\n" not in derived
    assert "export VLLM_XPU_MKLDNN_DETERMINISTIC=1\n" in derived
    assert 'expected_vllm_head="2169dbfe38c2954edc5ae50e94f68d45be071b79"' in derived
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )
    # The frozen client is renamed for hash pinning only; this diagnostic
    # attempt runs the logprob probe, not the client.
    client = successor(source("run-tp4-mtp0-2304-ple-only-a72-fullgraphdet-w13n32-client.sh"))
    client = replace_n(client, "--max-model-len 2304", "--max-model-len 4352", 1)
    client = replace_n(client, "max_model_len=2304", "max_model_len=4352", 1)
    client = replace_once(client, ".max_model_len == 2304)", ".max_model_len == 4352)")
    client = replace_once(client, '"max_model_len": 2304,', '"max_model_len": 4352,')
    supervisor = successor(source("supervise-tp4-mtp0-2304-ple-only-a72-fullgraphdet-w13n32.sh"))
    supervisor = replace_once(supervisor, '*"--max-model-len 2304"*', '*"--max-model-len 4352"*')
    supervisor = replace_once(supervisor, ".identity.max_model_len == 2304 and", ".identity.max_model_len == 4352 and")
    supervisor = replace_once(
        supervisor,
        "expected_wrapper=d4a363c6f88e5241bd12d586bafe99609b0cb5834f6e6a5b20d5b8675ca4d6f9",
        "expected_wrapper=" + digest(launcher),
    )
    supervisor = replace_once(
        supervisor,
        "expected_client=676c38eccf953828c21798a8b8b2f900a78962b5a1f217bd488c5a7b4fd23ca6",
        "expected_client=" + digest(client),
    )
    host = successor(source("run-q38-a72-host-controlled.sh"))
    host = replace_once(
        host,
        "expected_supervisor=085c7687720ba0b6b386ce5be29a5acec1a93a751d7c9bad54d75256fd068414",
        "expected_supervisor=" + digest(supervisor),
    )
    emit("launch-tp4-mtp0-4352-ple-only-a74-fullgraphdet-w13n32.sh", launcher)
    emit("run-tp4-mtp0-4352-ple-only-a74-fullgraphdet-w13n32-client.sh", client)
    emit("supervise-tp4-mtp0-4352-ple-only-a74-fullgraphdet-w13n32.sh", supervisor)
    emit("run-q38-a74-host-controlled.sh", host)
    for name in (
        "launch-tp4-mtp0-4352-ple-only-a74-fullgraphdet-w13n32.sh",
        "run-tp4-mtp0-4352-ple-only-a74-fullgraphdet-w13n32-client.sh",
        "supervise-tp4-mtp0-4352-ple-only-a74-fullgraphdet-w13n32.sh",
        "run-q38-a74-host-controlled.sh",
    ):
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
