#!/usr/bin/env python3
"""Create the A80 diagnostic packet from frozen A79: MTP1 on the deterministic full-decode-graph line.

A79 is the deterministic graph identity (overlay 2169dbfe, mkldnn
deterministic, public oneCCL twoshots, tuned M1 W13-N32 map, PLE-only UVA,
4352 tokens) loading the local NVMe model copy. A80 is that server with the
publisher's MTP head active at one speculative token and the full decode
graph capturing sizes [1, 2] (the two-row verification step must be captured,
as the 27B FP8 lane showed): the derived base's MTP freeze moves from 0 to 1,
the export line sets MTP=1, and the KV budget becomes the 4352-token MTP1
headroom value 376569856 (32 blocks, the 2026-08-27 MTP1 4352 arm). The
frozen client is renamed for hash pinning only; the arm is driven by the
lane's standard tools against the deterministic line's pinned MTP0 hashes,
so exactness (MTP1 == MTP0 outputs) is the gate. Attempt 80 / port 19752.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A80_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp0-4352-ple-only-a79-fullgraphdet-w13n32.sh": "f5353bd7df7b5ad45eae39e4eb3f7a84d2091b0b203228267ab7ceefe0b557ec",
    "run-tp4-mtp0-4352-ple-only-a79-fullgraphdet-w13n32-client.sh": "c4fc22827de7a521880492c3ef975c905e12704da8e4d4168778b4409aface56",
    "supervise-tp4-mtp0-4352-ple-only-a79-fullgraphdet-w13n32.sh": "19d1fce81d255fbcd6acb85c428a43c39d2e42b966c6d9d706248fda9fa6df0e",
    "run-q38-a79-host-controlled.sh": "8836b0eda78b2fff5c28e55787f0e294a88621e55e82e82cc7be485cc3f0922c",
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
        segment = segment.replace("tp4-mtp0-4352-ple-only-a79", "tp4-mtp1-4352-ple-only-a80")
        segment = segment.replace("attempt79", "attempt80")
        segment = segment.replace("19751", "19752")
        segment = segment.replace("ATTEMPT=79", "ATTEMPT=80")
        segment = segment.replace("a79", "a80")
        segment = segment.replace("A79", "A80")
        segment = segment.replace("fullgraphdet-mtp0-4352-ple-only", "fullgraphdet-mtp1-4352-ple-only")
        return segment.replace("q38-mtp0-ple-only", "q38-mtp1-ple-only")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19751" not in out and "attempt79" not in out
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


MTP_RULE = (
    '$0 == "[[ \\"${mtp}\\" == \\"0\\" ]] || {" {\n'
    '  print "[[ \\"${mtp}\\" == \\"1\\" ]] || {"\n'
    "  next\n"
    "}\n"
)


def main() -> None:
    launcher = source("launch-tp4-mtp0-4352-ple-only-a79-fullgraphdet-w13n32.sh")
    match = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert match
    launcher = replace_once(
        launcher, "expected_derived=" + match.group(1), "expected_derived=" + "0" * 64
    )
    launcher = successor(launcher)
    # MTP1: lift the base's MTP freeze to exactly 1, export MTP=1, headroom KV.
    launcher = replace_once(launcher, '$0 == "export XPU_GRAPH=0" {\n', MTP_RULE + '$0 == "export XPU_GRAPH=0" {\n')
    launcher = replace_once(
        launcher,
        "export MTP=0 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=80 PORT=19752\n",
        "export MTP=1 MTP_EXACT=0 MAX_MODEL_LEN=4352 ATTEMPT=80 PORT=19752\n",
    )
    launcher = replace_once(launcher, "export KV_CACHE_MEMORY_BYTES=134217728\n", "export KV_CACHE_MEMORY_BYTES=376569856\n")
    launcher = replace_once(
        launcher,
        """grep -Fxq '[[ "${max_model_len}" == "4352" ]] || {' "$derived"\n""",
        """grep -Fxq '[[ "${max_model_len}" == "4352" ]] || {' "$derived"\ngrep -Fxq '[[ "${mtp}" == "1" ]] || {' "$derived"\n! grep -Fq '[[ "${mtp}" == "0" ]] || {' "$derived"\n""",
    )
    # Full decode graph capturing sizes 1 and 2.
    launcher = replace_once(launcher, "cudagraph_capture_sizes'\\'': [1],\"", "cudagraph_capture_sizes'\\'': [1, 2],\"")
    launcher = replace_once(launcher, "max_cudagraph_capture_size'\\'': 1, '\\''compile_sizes'\\'': [],\"", "max_cudagraph_capture_size'\\'': 2, '\\''compile_sizes'\\'': [],\"")
    launcher = replace_once(launcher, "cudagraph_capture_sizes == [1]\"", "cudagraph_capture_sizes == [1, 2]\"")
    launcher = replace_once(launcher, "max_cudagraph_capture_size == 1\"", "max_cudagraph_capture_size == 2\"")
    launcher = replace_n(
        launcher,
        '\\"cudagraph_capture_sizes\\":[1],\\"max_cudagraph_capture_size\\":1,',
        '\\"cudagraph_capture_sizes\\":[1,2],\\"max_cudagraph_capture_size\\":2,',
        2,
    )

    env = os.environ.copy()
    env["Q38_A80_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(
        ["bash"], input=launcher, text=True, capture_output=True, check=True, env=env
    ).stdout
    Path("/tmp/q38-ple2k-a80-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a80" in derived and "q38-ple2k-a79" not in derived
    assert "oneccl-4ceafd1-b70-public" in derived and "  --enforce-eager\n" not in derived
    assert "export VLLM_XPU_MKLDNN_DETERMINISTIC=1\n" in derived
    assert 'expected_vllm_head="2169dbfe38c2954edc5ae50e94f68d45be071b79"' in derived
    assert '[[ "${mtp}" == "1" ]] || {' in derived and '[[ "${mtp}" == "0" ]] || {' not in derived
    assert '"cudagraph_capture_sizes":[1,2],"max_cudagraph_capture_size":2' in derived
    assert "'cudagraph_capture_sizes': [1, 2]," in derived
    assert "assert config.compilation_config.max_cudagraph_capture_size == 2" in derived
    assert "args+=(--speculative-config \"${speculative_config_json}\")" in derived
    launcher = launcher.replace(
        "expected_derived=" + "0" * 64, "expected_derived=" + digest(derived)
    )
    # Diagnostic arm: the frozen client is renamed for hash pinning only.
    client = successor(source("run-tp4-mtp0-4352-ple-only-a79-fullgraphdet-w13n32-client.sh"))
    supervisor = successor(source("supervise-tp4-mtp0-4352-ple-only-a79-fullgraphdet-w13n32.sh"))
    supervisor = replace_once(supervisor, ".identity.mtp == 0 and", ".identity.mtp == 1 and")
    supervisor = replace_once(supervisor, ".identity.cudagraph_capture_sizes == [1] and", ".identity.cudagraph_capture_sizes == [1,2] and")
    supervisor = replace_once(supervisor, ".identity.kv_cache_memory_bytes == 134217728 and", ".identity.kv_cache_memory_bytes == 376569856 and")
    supervisor = replace_once(
        supervisor,
        "expected_wrapper=f5353bd7df7b5ad45eae39e4eb3f7a84d2091b0b203228267ab7ceefe0b557ec",
        "expected_wrapper=" + digest(launcher),
    )
    supervisor = replace_once(
        supervisor,
        "expected_client=c4fc22827de7a521880492c3ef975c905e12704da8e4d4168778b4409aface56",
        "expected_client=" + digest(client),
    )
    host = successor(source("run-q38-a79-host-controlled.sh"))
    host = replace_once(
        host,
        "expected_supervisor=19d1fce81d255fbcd6acb85c428a43c39d2e42b966c6d9d706248fda9fa6df0e",
        "expected_supervisor=" + digest(supervisor),
    )
    names = (
        "launch-tp4-mtp1-4352-ple-only-a80-fullgraphdet-w13n32.sh",
        "run-tp4-mtp1-4352-ple-only-a80-fullgraphdet-w13n32-client.sh",
        "supervise-tp4-mtp1-4352-ple-only-a80-fullgraphdet-w13n32.sh",
        "run-q38-a80-host-controlled.sh",
    )
    for name, text in zip(names, (launcher, client, supervisor, host)):
        emit(name, text)
    for name in names:
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
