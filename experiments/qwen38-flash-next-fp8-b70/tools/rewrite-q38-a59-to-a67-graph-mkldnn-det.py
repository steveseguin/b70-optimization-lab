#!/usr/bin/env python3
"""Create the A67 full-decode-graph deterministic-oneDNN probe packet from frozen A59.

A66 (eager, bundled oneCCL, tuned M1 W13-N32 map) became logit-exact once
every XPU worker set ``torch.backends.mkldnn.deterministic=True``. The
promotable identity is the A56/A59 full-decode-graph line with the public
oneCCL preload (twoshots), so A67 keeps the frozen A59 server exactly and
changes two things: the overlay head moves to ``805cde59...`` (adds
``VLLM_XPU_MKLDNN_DETERMINISTIC``) and the derived script exports that flag
next to the tuned-folder export with an ``mkldnn_deterministic=1`` receipt
and static assertions. Attempt 67 / port 19739; names carry
``fullgraphdet``. The logprob probe (depths 8/64/256/2048) runs against it.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A67_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-2304-ple-only-a59-fullgraph-w13n32.sh": "8e4ebce78bf5c0ca17667583930779d5267fea467ac0c293ebcebc1221ba297a",
    "run-tp4-mtp0-2304-ple-only-a59-fullgraph-w13n32-client.sh": "4204d28d8d46c3c4ca57be65f228ad8bfaf472b6cd45483e80bcf12804f9ebd8",
    "supervise-tp4-mtp0-2304-ple-only-a59-fullgraph-w13n32.sh": "770d9fc44f2bb7cf3afd4b7ee582e77c76ebca5fd194a574c56cc073eac0a554",
    "run-q38-a59-host-controlled.sh": "a3599e924eb3a3a3cd89df8104747f139c5aa3cf05a380223fce0f34a5d6675c",
}
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
A59_HEAD = "cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9"
A67_HEAD = "805cde592dfe198a82deaba52894ebfc0e4a4352"

FOLDER_EXPORT = '  print "export VLLM_TUNED_CONFIG_FOLDER=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32"\n'
FLAG_EXPORT = FOLDER_EXPORT + '  print "export VLLM_XPU_MKLDNN_DETERMINISTIC=1"\n'
FOLDER_PRINT = """  print "  printf '\\''tuned_config_folder=moe-m1-w13-n32\\\\n'\\''"
"""
FLAG_PRINT = FOLDER_PRINT + """  print "  printf '\\''mkldnn_deterministic=1\\\\n'\\''"
"""
FOLDER_ASSERT = """[[ "$(grep -Fxc "  printf 'tuned_config_folder=moe-m1-w13-n32\\\\n'" "$derived")" == 1 ]]
"""
FLAG_ASSERT = FOLDER_ASSERT + """[[ "$(grep -Fxc 'export VLLM_XPU_MKLDNN_DETERMINISTIC=1' "$derived")" == 1 ]]
[[ "$(grep -Fxc "  printf 'mkldnn_deterministic=1\\\\n'" "$derived")" == 1 ]]
"""


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
        segment = segment.replace("attempt59", "attempt67")
        segment = segment.replace("19731", "19739")
        segment = segment.replace("ATTEMPT=59", "ATTEMPT=67")
        segment = segment.replace("a59", "a67")
        segment = segment.replace("A59", "A67")
        return segment.replace("fullgraph", "fullgraphdet")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert "19731" not in out and "attempt59" not in out
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
    launcher = source("launch-tp4-mtp0-2304-ple-only-a59-fullgraph-w13n32.sh")
    match = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert match
    launcher = replace_once(
        launcher, "expected_derived=" + match.group(1), "expected_derived=" + "0" * 64
    )
    launcher = replace_n(launcher, A59_HEAD, A67_HEAD, 2)
    launcher = replace_once(launcher, FOLDER_EXPORT, FLAG_EXPORT)
    launcher = replace_once(launcher, FOLDER_PRINT, FLAG_PRINT)
    launcher = replace_once(launcher, FOLDER_ASSERT, FLAG_ASSERT)
    launcher = successor(launcher)

    env = os.environ.copy()
    env["Q38_A67_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a67-base.sh").unlink(missing_ok=True)
    assert f'expected_vllm_head="{A67_HEAD}"' in derived and A59_HEAD not in derived
    assert "moe-m1-w13-n32" in derived and "  --enforce-eager\n" not in derived
    assert "oneccl-4ceafd1-b70-public" in derived
    assert "export VLLM_XPU_MKLDNN_DETERMINISTIC=1\n" in derived
    assert "  printf 'mkldnn_deterministic=1\\n'\n" in derived
    assert "q38-ple2k-a67" in derived
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )
    client = successor(source("run-tp4-mtp0-2304-ple-only-a59-fullgraph-w13n32-client.sh"))
    supervisor = successor(source("supervise-tp4-mtp0-2304-ple-only-a59-fullgraph-w13n32.sh"))
    supervisor = replace_once(
        supervisor,
        "expected_wrapper=8e4ebce78bf5c0ca17667583930779d5267fea467ac0c293ebcebc1221ba297a",
        "expected_wrapper=" + digest(launcher),
    )
    supervisor = replace_once(
        supervisor,
        "expected_client=4204d28d8d46c3c4ca57be65f228ad8bfaf472b6cd45483e80bcf12804f9ebd8",
        "expected_client=" + digest(client),
    )
    host = successor(source("run-q38-a59-host-controlled.sh"))
    host = replace_once(
        host,
        "expected_supervisor=770d9fc44f2bb7cf3afd4b7ee582e77c76ebca5fd194a574c56cc073eac0a554",
        "expected_supervisor=" + digest(supervisor),
    )
    emit("launch-tp4-mtp0-2304-ple-only-a67-fullgraphdet-w13n32.sh", launcher)
    emit("run-tp4-mtp0-2304-ple-only-a67-fullgraphdet-w13n32-client.sh", client)
    emit("supervise-tp4-mtp0-2304-ple-only-a67-fullgraphdet-w13n32.sh", supervisor)
    emit("run-q38-a67-host-controlled.sh", host)
    for name in (
        "launch-tp4-mtp0-2304-ple-only-a67-fullgraphdet-w13n32.sh",
        "run-tp4-mtp0-2304-ple-only-a67-fullgraphdet-w13n32-client.sh",
        "supervise-tp4-mtp0-2304-ple-only-a67-fullgraphdet-w13n32.sh",
        "run-q38-a67-host-controlled.sh",
    ):
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
