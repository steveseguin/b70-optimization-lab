#!/usr/bin/env python3
"""Create the A63 old-overlay-head control packet from frozen A62.

A62 (eager, bundled oneCCL, tuned M1 map) reproduced the first-step jitter
even for an 8-token prompt, so neither the graph nor the collective library
is the source. The last provably bit-exact server (2026-08-28) ran the vLLM
overlay at `1372c62d975c554f4b465c8299bc5f3295301ceb`; every arm since runs
`cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9`, 18 commits later. A63 keeps
A62's server identity except that it drops the launcher's head override (so
the eager base's native pin `1372c62d...` applies and the overlay checkout
must be at that commit) and drops the tuned MoE map (the per-phase resolver
and its nested `W1_CONFIG` key do not exist at the old head). Attempt 63 /
port 19735; names carry `oldhead`. Staged kernels, model, placement, chunked
prefill, host guards, and the probe are unchanged.

Before launch: `git -C /home/steve/src/vllm-current-main checkout
1372c62d975c554f4b465c8299bc5f3295301ceb` (detached, clean). After the arm:
`git -C /home/steve/src/vllm-current-main checkout cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9`.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A63_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-2304-ple-only-a62-bundledccl-w13n32.sh": "15ec4b27670bcb77cab05f0c2d70780f0c4d558cacf36b2d2dacbf209196a623",
    "run-tp4-mtp0-2304-ple-only-a62-bundledccl-w13n32-client.sh": "25fe95624afe4dfc1029fcb69239195b5105d6e0a168b3ec6a34fee5a2461260",
    "supervise-tp4-mtp0-2304-ple-only-a62-bundledccl-w13n32.sh": "377dd77e822007af1573e37af29704b5c1c97de1040ddf2099537dd480e28a2e",
    "run-q38-a62-host-controlled.sh": "890ca8610493b418d493441d68d0ed851e7da1ab001d51c976c28f82f97c5073",
}
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
OLD_HEAD = "1372c62d975c554f4b465c8299bc5f3295301ceb"
NEW_HEAD = "cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9"

HEAD_RULE = f"""$0 == "expected_vllm_head=\\"{OLD_HEAD}\\"" {{
  print "expected_vllm_head=\\"{NEW_HEAD}\\""
  next
}}
"""
FOLDER_EXPORT = '  print "export VLLM_TUNED_CONFIG_FOLDER=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32"\n'
FOLDER_PRINTS = """  print "  printf '\\''tuned_config_folder=moe-m1-w13-n32\\\\n'\\''"
  print "  printf '\\''tuned_config_map_sha256=a8f1f8982e3e1af80ff31b9e0a00afaacf1af1b3c401585109b4d60d3c8267be\\\\n'\\''"
"""
FOLDER_ASSERTIONS = """[[ "$(grep -Fxc 'export VLLM_TUNED_CONFIG_FOLDER=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/configs/moe-m1-w13-n32' "$derived")" == 1 ]]
[[ "$(grep -Fxc "  printf 'tuned_config_folder=moe-m1-w13-n32\\\\n'" "$derived")" == 1 ]]
[[ "$(grep -Fxc "  printf 'tuned_config_map_sha256=a8f1f8982e3e1af80ff31b9e0a00afaacf1af1b3c401585109b4d60d3c8267be\\\\n'" "$derived")" == 1 ]]
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
        segment = segment.replace("attempt62", "attempt63")
        segment = segment.replace("19734", "19735")
        segment = segment.replace("ATTEMPT=62", "ATTEMPT=63")
        segment = segment.replace("a62", "a63")
        segment = segment.replace("A62", "A63")
        return segment.replace("bundledccl", "oldhead")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert "19734" not in out and "bundledccl" not in out
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
    launcher = source("launch-tp4-mtp0-2304-ple-only-a62-bundledccl-w13n32.sh")
    match = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert match
    launcher = replace_once(
        launcher, "expected_derived=" + match.group(1), "expected_derived=" + "0" * 64
    )
    # Static tuned-map identity block (four lines after the campaign name).
    start = launcher.index("tuned_config_folder=/home/steve/")
    end = launcher.index("\n", launcher.index("W13-N32 shape", start)) + 1
    block = launcher[start:end]
    assert block.count("\n") == 4, block
    launcher = launcher[:start] + launcher[end:]
    launcher = replace_once(launcher, HEAD_RULE, "")
    launcher = replace_once(launcher, FOLDER_EXPORT, "")
    launcher = replace_once(launcher, FOLDER_PRINTS, "")
    launcher = replace_once(launcher, FOLDER_ASSERTIONS, "")
    launcher = replace_once(
        launcher,
        f"""grep -Fxq 'expected_vllm_head="{NEW_HEAD}"' "$derived"\n""",
        f"""grep -Fxq 'expected_vllm_head="{OLD_HEAD}"' "$derived"\n"""
        """! grep -Fq 'VLLM_TUNED_CONFIG_FOLDER' "$derived"\n""",
    )
    launcher = successor(launcher)

    env = os.environ.copy()
    env["Q38_A63_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a63-base.sh").unlink(missing_ok=True)
    assert f'expected_vllm_head="{OLD_HEAD}"' in derived and NEW_HEAD not in derived
    assert "VLLM_TUNED_CONFIG_FOLDER" not in derived and "moe-m1-w13-n32" not in derived
    assert (
        "oneccl-4ceafd1-b70-public" not in derived and "  --enforce-eager\n" in derived
    )
    assert "q38-ple2k-a63" in derived
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )
    client = successor(
        source("run-tp4-mtp0-2304-ple-only-a62-bundledccl-w13n32-client.sh")
    )
    supervisor = successor(
        source("supervise-tp4-mtp0-2304-ple-only-a62-bundledccl-w13n32.sh")
    )
    supervisor = replace_once(
        supervisor,
        "expected_wrapper=15ec4b27670bcb77cab05f0c2d70780f0c4d558cacf36b2d2dacbf209196a623",
        "expected_wrapper=" + digest(launcher),
    )
    supervisor = replace_once(
        supervisor,
        "expected_client=25fe95624afe4dfc1029fcb69239195b5105d6e0a168b3ec6a34fee5a2461260",
        "expected_client=" + digest(client),
    )
    host = successor(source("run-q38-a62-host-controlled.sh"))
    host = replace_once(
        host,
        "expected_supervisor=377dd77e822007af1573e37af29704b5c1c97de1040ddf2099537dd480e28a2e",
        "expected_supervisor=" + digest(supervisor),
    )
    emit("launch-tp4-mtp0-2304-ple-only-a63-oldhead-w13n32.sh", launcher)
    emit("run-tp4-mtp0-2304-ple-only-a63-oldhead-w13n32-client.sh", client)
    emit("supervise-tp4-mtp0-2304-ple-only-a63-oldhead-w13n32.sh", supervisor)
    emit("run-q38-a63-host-controlled.sh", host)
    for name in (
        "launch-tp4-mtp0-2304-ple-only-a63-oldhead-w13n32.sh",
        "run-tp4-mtp0-2304-ple-only-a63-oldhead-w13n32-client.sh",
        "supervise-tp4-mtp0-2304-ple-only-a63-oldhead-w13n32.sh",
        "run-q38-a63-host-controlled.sh",
    ):
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
