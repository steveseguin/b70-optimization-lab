#!/usr/bin/env python3
"""Create the A84 packet from frozen A81 with fresh attempt paths only (logprob probe arm).

A81 (MTP1 in the full decode graph) and A83 (eager MTP1) both produced the
same exact-2K continuation, different from the MTP0 line's, so the
speculative verification path itself differs numerically from single-row
decode at depth. A84 is the A81 server at attempt 84 / port 19756 on which
the A59 logprob probe runs (depths 8, 256, 2048; eight first-step repeats
and three 128-token repeats each) so the top-5 logprobs can be compared
offline against the MTP0 line's A76/A77 probes: where the first difference
appears and how large it is. The frozen client is renamed only.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A84_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp1-4352-ple-only-a81-fullgraphdet-w13n32.sh": "c1cd610a7bb93f45afd4a364892f2446fd55d7c6736374f097565290270dd936",
    "run-tp4-mtp1-4352-ple-only-a81-fullgraphdet-w13n32-client.sh": "ac19fe01e1fe83972cc217386608c612a8009047bd01d3194e52675a2121674d",
    "supervise-tp4-mtp1-4352-ple-only-a81-fullgraphdet-w13n32.sh": "f42a8a5e4808e7c61826355f82e31433cb43d4f057d0d5a4d900256dc337c77c",
    "run-q38-a81-host-controlled.sh": "b6c392ac01bdbaf323960b8dd33297315d1667b7f85ad4f2782123ba665e49a1",
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
        segment = segment.replace("attempt81", "attempt84")
        segment = segment.replace("19753", "19756")
        segment = segment.replace("ATTEMPT=81", "ATTEMPT=84")
        segment = segment.replace("a81", "a84")
        return segment.replace("A81", "A84")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19753" not in out and "attempt81" not in out
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
    launcher = source("launch-tp4-mtp1-4352-ple-only-a81-fullgraphdet-w13n32.sh")
    match = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert match
    launcher = replace_once(launcher, "expected_derived=" + match.group(1), "expected_derived=" + "0" * 64)
    launcher = successor(launcher)
    env = os.environ.copy()
    env["Q38_A84_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a84-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a84" in derived and "q38-ple2k-a81" not in derived
    assert '[[ "${mtp}" == "1" ]] || {' in derived
    assert '"cudagraph_capture_sizes":[1,2],"max_cudagraph_capture_size":2' in derived
    launcher = launcher.replace("expected_derived=" + "0" * 64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp1-4352-ple-only-a81-fullgraphdet-w13n32-client.sh"))
    supervisor = successor(source("supervise-tp4-mtp1-4352-ple-only-a81-fullgraphdet-w13n32.sh"))
    supervisor = replace_once(supervisor, "expected_wrapper=c1cd610a7bb93f45afd4a364892f2446fd55d7c6736374f097565290270dd936", "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=ac19fe01e1fe83972cc217386608c612a8009047bd01d3194e52675a2121674d", "expected_client=" + digest(client))
    host = successor(source("run-q38-a81-host-controlled.sh"))
    host = replace_once(host, "expected_supervisor=f42a8a5e4808e7c61826355f82e31433cb43d4f057d0d5a4d900256dc337c77c", "expected_supervisor=" + digest(supervisor))
    names = (
        "launch-tp4-mtp1-4352-ple-only-a84-fullgraphdet-w13n32.sh",
        "run-tp4-mtp1-4352-ple-only-a84-fullgraphdet-w13n32-client.sh",
        "supervise-tp4-mtp1-4352-ple-only-a84-fullgraphdet-w13n32.sh",
        "run-q38-a84-host-controlled.sh",
    )
    for name, text in zip(names, (launcher, client, supervisor, host)):
        emit(name, text)
    for name in names:
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
