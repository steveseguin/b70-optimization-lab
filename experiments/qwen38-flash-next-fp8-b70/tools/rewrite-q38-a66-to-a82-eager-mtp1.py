#!/usr/bin/env python3
"""Create the A82 diagnostic packet from frozen A66: eager MTP1 on the deterministic line at 4352 tokens.

A81 (MTP1 inside the full decode graph, capture sizes [1, 2]) reproduced
the MTP0 line's short output exactly at 38.5-44.0 tok/s but diverged from
the MTP0 exact-2K continuation at token 7 (a near-tie flip) and decoded at
about half the MTP0 rate there. A82 separates the graph from the
speculative path: the eager deterministic identity (A66: mkldnn
deterministic, public oneCCL twoshots, tuned M1 W13-N32 map, PLE-only UVA,
`--enforce-eager`) served at 4352 tokens from the NVMe model copy with MTP1
and the 32-block MTP1 KV budget. Same driver and pinned MTP0 hashes.
Attempt 82 / port 19754.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A82_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-2304-ple-only-a66-mkldnndet-w13n32.sh": "a3d1818796b96fcf13e8a55ae24ddd5b666d1431221c5f1a5db5638aca009cb1",
    "run-tp4-mtp0-2304-ple-only-a66-mkldnndet-w13n32-client.sh": "c403b49f8784eb89bdd141419fc94106b1258a4a64152c10162a30f456a9dd37",
    "supervise-tp4-mtp0-2304-ple-only-a66-mkldnndet-w13n32.sh": "bd1f08e6d7f88101e88ffa391fa6f6c0aede09c1575b9f7359ee5a135928f05b",
    "run-q38-a66-host-controlled.sh": "5387416c3cef4f1b193fe3397b0282abfd72ebfe029ed09c16e5df617db43e70",
}
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
USB_MODEL = "/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8"
NVME_MODEL = "/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8"


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
        segment = segment.replace("tp4-mtp0-2304-ple-only-a66", "tp4-mtp1-4352-ple-only-a82")
        segment = segment.replace("mkldnndet-mtp0-2304-ple-only", "mkldnndet-mtp1-4352-ple-only")
        segment = segment.replace("q38-mtp0-ple-only", "q38-mtp1-ple-only")
        segment = segment.replace("attempt66", "attempt82")
        segment = segment.replace("19738", "19754")
        segment = segment.replace("ATTEMPT=66", "ATTEMPT=82")
        segment = segment.replace("a66", "a82")
        return segment.replace("A66", "A82")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19738" not in out and "attempt66" not in out
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


MTP_RULE = (
    '$0 == "[[ \\"${mtp}\\" == \\"0\\" ]] || {" {\n'
    '  print "[[ \\"${mtp}\\" == \\"1\\" ]] || {"\n'
    "  next\n"
    "}\n"
)
CAMPAIGN_RULE = '$0 == "campaign=\\"qwen38-flash-next-fp8-tp4-ep4-eager-mtp${mtp}${exact_suffix}-${max_model_len}-r1\\"" {\n'


def main() -> None:
    launcher = source("launch-tp4-mtp0-2304-ple-only-a66-mkldnndet-w13n32.sh")
    match = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert match
    launcher = replace_once(launcher, "expected_derived=" + match.group(1), "expected_derived=" + "0" * 64)
    launcher = successor(launcher)
    # 4352 capacity (A74 pattern).
    launcher = replace_once(launcher, '  print "[[ \\"${max_model_len}\\" == \\"2304\\" ]] || {"\n', '  print "[[ \\"${max_model_len}\\" == \\"4352\\" ]] || {"\n')
    launcher = replace_once(launcher, "FAIL: PLE-only base is frozen to MAX_MODEL_LEN=2304", "FAIL: PLE-only base is frozen to MAX_MODEL_LEN=4352")
    launcher = replace_once(launcher, """grep -Fxq '[[ "${max_model_len}" == "2304" ]] || {' "$derived"\n""", """grep -Fxq '[[ "${max_model_len}" == "4352" ]] || {' "$derived"\ngrep -Fxq '[[ "${mtp}" == "1" ]] || {' "$derived"\n! grep -Fq '[[ "${mtp}" == "0" ]] || {' "$derived"\n""")
    # MTP1 (A80 pattern) and its KV budget.
    launcher = replace_once(launcher, CAMPAIGN_RULE, MTP_RULE + CAMPAIGN_RULE)
    launcher = replace_once(launcher, "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=2304 ATTEMPT=82 PORT=19754\n", "export MTP=1 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=82 PORT=19754\n")
    launcher = replace_once(launcher, "export KV_CACHE_MEMORY_BYTES=134217728\n", "export KV_CACHE_MEMORY_BYTES=376569856\n")
    # NVMe model copy and the 256 GiB bounded-read cap (A79 pattern).
    launcher = replace_once(launcher, "export MODEL_PATH=" + USB_MODEL + "\n", "export MODEL_PATH=" + NVME_MODEL + "\n")
    launcher = replace_once(launcher, "     nvme_sectors_read - expected_nvme_sectors_read <= 16777216 )) || {\n", "     nvme_sectors_read - expected_nvme_sectors_read <= 536870912 )) || {\n")

    env = os.environ.copy()
    env["Q38_A82_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a82-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a82" in derived and "q38-ple2k-a66" not in derived
    assert "  --enforce-eager\n" in derived and "VLLM_XPU_ENABLE_XPU_GRAPH=1" not in derived
    assert "export VLLM_XPU_MKLDNN_DETERMINISTIC=1\n" in derived
    assert '[[ "${mtp}" == "1" ]] || {' in derived and '[[ "${mtp}" == "0" ]] || {' not in derived
    assert '[[ "${max_model_len}" == "4352" ]] || {' in derived
    assert derived.count(USB_MODEL) == derived.count("${MODEL_PATH:-" + USB_MODEL + "}") == 1
    launcher = launcher.replace("expected_derived=" + "0" * 64, "expected_derived=" + digest(derived))

    client = successor(source("run-tp4-mtp0-2304-ple-only-a66-mkldnndet-w13n32-client.sh"))
    supervisor = successor(source("supervise-tp4-mtp0-2304-ple-only-a66-mkldnndet-w13n32.sh"))
    supervisor = replace_once(supervisor, "max_nvme_sectors_read_delta=16777216\n", "max_nvme_sectors_read_delta=536870912\n")
    supervisor = replace_once(supervisor, "  (( mem_available_kib >= 16000000 )) || return 1\n", "  (( mem_available_kib >= 12000000 )) || return 1\n")
    supervisor = replace_once(supervisor, '*"vllm serve ' + USB_MODEL + '"*', '*"vllm serve ' + NVME_MODEL + '"*')
    supervisor = replace_once(supervisor, '*"--max-model-len 2304"*', '*"--max-model-len 4352"*')
    supervisor = replace_once(supervisor, ".identity.mtp == 0 and", ".identity.mtp == 1 and")
    supervisor = replace_once(supervisor, ".identity.max_model_len == 2304 and", ".identity.max_model_len == 4352 and")
    supervisor = replace_once(supervisor, ".identity.kv_cache_memory_bytes == 134217728 and", ".identity.kv_cache_memory_bytes == 376569856 and")
    assert USB_MODEL not in supervisor
    supervisor = replace_once(supervisor, "expected_wrapper=a3d1818796b96fcf13e8a55ae24ddd5b666d1431221c5f1a5db5638aca009cb1", "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=c403b49f8784eb89bdd141419fc94106b1258a4a64152c10162a30f456a9dd37", "expected_client=" + digest(client))
    host = successor(source("run-q38-a66-host-controlled.sh"))
    host = replace_once(host, "expected_supervisor=bd1f08e6d7f88101e88ffa391fa6f6c0aede09c1575b9f7359ee5a135928f05b", "expected_supervisor=" + digest(supervisor))
    names = (
        "launch-tp4-mtp1-4352-ple-only-a82-mkldnndet-w13n32.sh",
        "run-tp4-mtp1-4352-ple-only-a82-mkldnndet-w13n32-client.sh",
        "supervise-tp4-mtp1-4352-ple-only-a82-mkldnndet-w13n32.sh",
        "run-q38-a82-host-controlled.sh",
    )
    for name, text in zip(names, (launcher, client, supervisor, host)):
        emit(name, text)
    for name in names:
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
