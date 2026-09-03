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
VALIDATE_ONLY = os.environ.get("Q38_A72_REWRITE_VALIDATE_ONLY") == "1"
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
        segment = segment.replace("attempt67", "attempt72")
        segment = segment.replace("19739", "19744")
        segment = segment.replace("ATTEMPT=67", "ATTEMPT=72")
        segment = segment.replace("a67", "a72")
        return segment.replace("A67", "A72")

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
    launcher = source("launch-tp4-mtp0-2304-ple-only-a67-fullgraphdet-w13n32.sh")
    match = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert match
    launcher = replace_once(
        launcher, "expected_derived=" + match.group(1), "expected_derived=" + "0" * 64
    )
    launcher = replace_once(
        launcher,
        "     nvme_sectors_read - expected_nvme_sectors_read <= 16777216 )) || {\n",
        "     nvme_sectors_read - expected_nvme_sectors_read <= 134217728 )) || {\n",
    )
    # A72 moves the overlay head from A67's 805cde59 (deterministic flag) to
    # the V2-runner CUDAGraphStat receipt commit; two launcher literals.
    launcher = replace_n(
        launcher,
        "805cde592dfe198a82deaba52894ebfc0e4a4352",
        "2169dbfe38c2954edc5ae50e94f68d45be071b79",
        2,
    )
    launcher = successor(launcher)
    env = os.environ.copy()
    env["Q38_A72_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a72-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a72" in derived and "q38-ple2k-a67" not in derived
    assert "oneccl-4ceafd1-b70-public" in derived and "  --enforce-eager\n" not in derived
    assert "export VLLM_XPU_MKLDNN_DETERMINISTIC=1\n" in derived
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )
    client = successor(
        source("run-tp4-mtp0-2304-ple-only-a67-fullgraphdet-w13n32-client.sh")
    )
    # A68 failed closed at admission: the A59->A67 rename of the `fullgraph`
    # token also renamed the pinned helper file. Restore the real file name;
    # its pinned SHA-256 is unchanged because the helper itself never moved.
    client = replace_once(
        client,
        "tools/verify-q38-a48-fullgraphdet-runtime.py",
        "tools/verify-q38-a48-fullgraph-runtime.py",
    )
    assert "verify-q38-a48-fullgraphdet-runtime.py" not in client
    # A70 passed every protected gate and produced one exact-2K output hash
    # on both rows (afffd211...) that differs from the 2026-08-27 native-line
    # record (5fd297f7...) at a near-tie token. A71 pins the deterministic
    # candidate so a fresh server must reproduce it byte for byte; the
    # native-line record is untouched elsewhere.
    client = replace_once(
        client,
        "assert depth_hashes == ['5fd297f79da317b0741140cccb52fb710f89dfd1444effe9068b806b0300e57e'] * 2\n",
        "assert depth_hashes == ['afffd2110812762164862b6388f054bb56696ee57b07eadce411a702c40bc714'] * 2\n",
    )
    # A69 failed closed at the W13-N32 resolver receipt: the verifier pinned
    # the overlay head cbc3cb58 while the server runs 805cde59 (three
    # diagnostic commits that leave the hashed MoE sources untouched). The
    # verifier now accepts both heads; pin its new hash, move the client's
    # own head receipts to 805cde59, and require the flag's identity receipt.
    client = replace_once(
        client,
        "a464b0f6a46e9149b33e5ccca772bf21385532693e78b691ca010a7833be2e6f",
        "4f4942289f3853f0dec60b9fcd14c644ca300abaaa9d9fa2ea56135f4d9f9c52",
    )
    client = replace_n(
        client,
        "cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9",
        "2169dbfe38c2954edc5ae50e94f68d45be071b79",
        3,
    )
    client = replace_once(
        client,
        "  'tuned_config_folder=moe-m1-w13-n32' 'tuned_config_map_sha256=a8f1f8982e3e1af80ff31b9e0a00afaacf1af1b3c401585109b4d60d3c8267be'; do\n",
        "  'tuned_config_folder=moe-m1-w13-n32' 'tuned_config_map_sha256=a8f1f8982e3e1af80ff31b9e0a00afaacf1af1b3c401585109b4d60d3c8267be' \\\n  'mkldnn_deterministic=1'; do\n",
    )
    supervisor = successor(
        source("supervise-tp4-mtp0-2304-ple-only-a67-fullgraphdet-w13n32.sh")
    )
    supervisor = replace_once(
        supervisor,
        "max_nvme_sectors_read_delta=16777216\n",
        "max_nvme_sectors_read_delta=134217728\n",
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
    emit("launch-tp4-mtp0-2304-ple-only-a72-fullgraphdet-w13n32.sh", launcher)
    emit("run-tp4-mtp0-2304-ple-only-a72-fullgraphdet-w13n32-client.sh", client)
    emit("supervise-tp4-mtp0-2304-ple-only-a72-fullgraphdet-w13n32.sh", supervisor)
    emit("run-q38-a72-host-controlled.sh", host)
    for name in (
        "launch-tp4-mtp0-2304-ple-only-a72-fullgraphdet-w13n32.sh",
        "run-tp4-mtp0-2304-ple-only-a72-fullgraphdet-w13n32-client.sh",
        "supervise-tp4-mtp0-2304-ple-only-a72-fullgraphdet-w13n32.sh",
        "run-q38-a72-host-controlled.sh",
    ):
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
