#!/usr/bin/env python3
"""Create the A79 packet from frozen A78: the same server loading the verified local-NVMe model copy.

A78 is the deterministic graph line's frozen client at 4352 served tokens.
A79 is the same packet at attempt 79 / port 19751 with two changes: the
server loads the model from the local NVMe copy
(/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8, verified against the
2026-08-27 receipt on 2026-09-03, 124 s) instead of the USB copy, and the
bounded root-NVMe read guard rises from 64 GiB to 256 GiB of sectors
(the model is 173 GB; the AER guard is unchanged). The frozen client and its
pinned hashes are unchanged, so any output difference fails the run. The
purpose is iteration speed: the USB load takes about 550 s per attempt.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A79_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh": "736b5b92a757e4fd22ba271f42eabba72bf0c889018578d80c9a9246d3cd6a37",
    "run-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32-client.sh": "38e0388cce6a39f9348a4e76051f96b0d912f7a4cd60d0e42aa9022d9a79185d",
    "supervise-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh": "8a2b632651fdb14340f7f3643a839c7de9739b65be154f178e6871979da35134",
    "run-q38-a78-host-controlled.sh": "7444be0bf492b73f4fd3a5aed2c8e54b32600d51b9d3f7dc0c4e0d32b9fea910",
}
USB_MODEL = "/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8"
NVME_MODEL = "/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8"
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
        segment = segment.replace("attempt78", "attempt79")
        segment = segment.replace("19750", "19751")
        segment = segment.replace("ATTEMPT=78", "ATTEMPT=79")
        segment = segment.replace("a78", "a79")
        return segment.replace("A78", "A79")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19750" not in out and "attempt78" not in out
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
    launcher = source("launch-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh")
    match = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert match
    launcher = replace_once(
        launcher, "expected_derived=" + match.group(1), "expected_derived=" + "0" * 64
    )
    launcher = successor(launcher)
    launcher = replace_once(launcher, "export MODEL_PATH=" + USB_MODEL + "\n", "export MODEL_PATH=" + NVME_MODEL + "\n")
    launcher = replace_once(
        launcher,
        "     nvme_sectors_read - expected_nvme_sectors_read <= 134217728 )) || {\n",
        "     nvme_sectors_read - expected_nvme_sectors_read <= 536870912 )) || {\n",
    )
    env = os.environ.copy()
    env["Q38_A79_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a79-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a79" in derived and "q38-ple2k-a78" not in derived
    # The base keeps the USB path only as the inert `${MODEL_PATH:-...}` default;
    # the launcher exports MODEL_PATH to the NVMe copy before deriving.
    assert derived.count(USB_MODEL) == derived.count("${MODEL_PATH:-" + USB_MODEL + "}") == 1
    assert "export VLLM_XPU_MKLDNN_DETERMINISTIC=1\n" in derived
    assert "oneccl-4ceafd1-b70-public" in derived and "  --enforce-eager\n" not in derived
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )
    client = successor(
        source("run-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32-client.sh")
    )
    client = replace_once(client, "tokenizer=" + USB_MODEL + "\n", "tokenizer=" + NVME_MODEL + "\n")
    client = replace_once(client, '*"vllm serve ' + USB_MODEL + '"*', '*"vllm serve ' + NVME_MODEL + '"*')
    assert USB_MODEL not in client
    supervisor = successor(
        source("supervise-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh")
    )
    supervisor = replace_once(supervisor, "max_nvme_sectors_read_delta=134217728\n", "max_nvme_sectors_read_delta=536870912\n")
    supervisor = replace_once(supervisor, '*"vllm serve ' + USB_MODEL + '"*', '*"vllm serve ' + NVME_MODEL + '"*')
    assert USB_MODEL not in supervisor
    supervisor = replace_once(
        supervisor,
        "expected_wrapper=736b5b92a757e4fd22ba271f42eabba72bf0c889018578d80c9a9246d3cd6a37",
        "expected_wrapper=" + digest(launcher),
    )
    supervisor = replace_once(
        supervisor,
        "expected_client=38e0388cce6a39f9348a4e76051f96b0d912f7a4cd60d0e42aa9022d9a79185d",
        "expected_client=" + digest(client),
    )
    host = successor(source("run-q38-a78-host-controlled.sh"))
    host = replace_once(
        host,
        "expected_supervisor=8a2b632651fdb14340f7f3643a839c7de9739b65be154f178e6871979da35134",
        "expected_supervisor=" + digest(supervisor),
    )
    emit("launch-tp4-mtp0-4352-ple-only-a79-fullgraphdet-w13n32.sh", launcher)
    emit("run-tp4-mtp0-4352-ple-only-a79-fullgraphdet-w13n32-client.sh", client)
    emit("supervise-tp4-mtp0-4352-ple-only-a79-fullgraphdet-w13n32.sh", supervisor)
    emit("run-q38-a79-host-controlled.sh", host)
    for name in (
        "launch-tp4-mtp0-4352-ple-only-a79-fullgraphdet-w13n32.sh",
        "run-tp4-mtp0-4352-ple-only-a79-fullgraphdet-w13n32-client.sh",
        "supervise-tp4-mtp0-4352-ple-only-a79-fullgraphdet-w13n32.sh",
        "run-q38-a79-host-controlled.sh",
    ):
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
