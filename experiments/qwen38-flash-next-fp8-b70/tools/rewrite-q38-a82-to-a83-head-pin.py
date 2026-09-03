#!/usr/bin/env python3
"""Create the A83 packet from frozen A82 with the current overlay head pinned.

A82 (eager MTP1 on the deterministic line, derived from A66) failed its
launch pre-check with 'vLLM overlay head changed': A66 pinned overlay head
805cde59 (before the V2-runner receipt fix 2169dbfe that A72 and later use).
A83 is the same packet at attempt 83 / port 19755 with the launcher's two
head literals moved to 2169dbfe38c2954edc5ae50e94f68d45be071b79, the head
every deterministic-line server since A72 has run on; nothing else changes.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A83_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    "launch-tp4-mtp1-4352-ple-only-a82-mkldnndet-w13n32.sh": "17760673f0483ecd0cb649a2aa0139dfabdbffb1f3144f0716a04cfd334b510c",
    "run-tp4-mtp1-4352-ple-only-a82-mkldnndet-w13n32-client.sh": "95bdbb43298cfcc267a656752efc661cf8ac3f19c6be822d1858f24c38cb6f9c",
    "supervise-tp4-mtp1-4352-ple-only-a82-mkldnndet-w13n32.sh": "04a7a7a57f2195dea864928bf7006c9e802c7186a4546ffa693513f0f43ae430",
    "run-q38-a82-host-controlled.sh": "7dfe5813c17f2ae458c14fc0b42b47515910a3a7ef77855473225b8ed856ecc4",
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
        segment = segment.replace("attempt82", "attempt83")
        segment = segment.replace("19754", "19755")
        segment = segment.replace("ATTEMPT=82", "ATTEMPT=83")
        segment = segment.replace("a82", "a83")
        return segment.replace("A82", "A83")

    parts: list[str] = []
    last = 0
    for match in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19754" not in out and "attempt82" not in out
    return out


def replace_n(text: str, old: str, new: str, n: int) -> str:
    assert text.count(old) == n, f"anchor count {text.count(old)} != {n}: {old[:90]!r}"
    return text.replace(old, new)


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
    launcher = source("launch-tp4-mtp1-4352-ple-only-a82-mkldnndet-w13n32.sh")
    match = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert match
    launcher = replace_once(launcher, "expected_derived=" + match.group(1), "expected_derived=" + "0" * 64)
    launcher = successor(launcher)
    launcher = replace_n(launcher, "805cde592dfe198a82deaba52894ebfc0e4a4352", "2169dbfe38c2954edc5ae50e94f68d45be071b79", 2)
    env = os.environ.copy()
    env["Q38_A83_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a83-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a83" in derived and "q38-ple2k-a82" not in derived
    assert '[[ "${mtp}" == "1" ]] || {' in derived
    assert "  --enforce-eager\n" in derived
    assert 'expected_vllm_head="2169dbfe38c2954edc5ae50e94f68d45be071b79"' in derived and "805cde59" not in derived
    launcher = launcher.replace("expected_derived=" + "0" * 64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp1-4352-ple-only-a82-mkldnndet-w13n32-client.sh"))
    supervisor = successor(source("supervise-tp4-mtp1-4352-ple-only-a82-mkldnndet-w13n32.sh"))
    supervisor = replace_once(supervisor, "expected_wrapper=17760673f0483ecd0cb649a2aa0139dfabdbffb1f3144f0716a04cfd334b510c", "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=95bdbb43298cfcc267a656752efc661cf8ac3f19c6be822d1858f24c38cb6f9c", "expected_client=" + digest(client))
    host = successor(source("run-q38-a82-host-controlled.sh"))
    host = replace_once(host, "expected_supervisor=04a7a7a57f2195dea864928bf7006c9e802c7186a4546ffa693513f0f43ae430", "expected_supervisor=" + digest(supervisor))
    names = (
        "launch-tp4-mtp1-4352-ple-only-a83-mkldnndet-w13n32.sh",
        "run-tp4-mtp1-4352-ple-only-a83-mkldnndet-w13n32-client.sh",
        "supervise-tp4-mtp1-4352-ple-only-a83-mkldnndet-w13n32.sh",
        "run-q38-a83-host-controlled.sh",
    )
    for name, text in zip(names, (launcher, client, supervisor, host)):
        emit(name, text)
    for name in names:
        print(digest((ROOT / name).read_bytes()), name)


if __name__ == "__main__":
    main()
