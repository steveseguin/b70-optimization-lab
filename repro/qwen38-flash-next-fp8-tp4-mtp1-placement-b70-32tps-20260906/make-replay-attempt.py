#!/usr/bin/env python3
"""Derive a replay packet a<N> from the frozen A226 packet (lossless MTP1, 31.929484 tok/s).

The four A226 scripts are pinned by frozen-a226-packet.sha256. The derived packet is
byte-identical apart from the attempt number, port, and state-file names; every
hash token (64/40 hex) is preserved and the packet's own internal hashes
(expected_derived, expected_wrapper, expected_client, expected_supervisor) are
recomputed exactly the way the lab's generators do. Usage:

  make-replay-attempt.py <attempt> <port>          # writes the four scripts
  make-replay-attempt.py <attempt> <port> --check  # verifies existing scripts

Refuses to overwrite an existing packet.
"""
from __future__ import annotations
import hashlib, os, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1] / "experiments/qwen38-flash-next-fp8-b70/tools"
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
SRC = {
    "launcher": "launch-tp4-mtp1-4352-ple-only-a226-fullgraphdet-w13n32.sh",
    "client": "run-tp4-mtp1-4352-ple-only-a226-fullgraphdet-w13n32-client.sh",
    "supervisor": "supervise-tp4-mtp1-4352-ple-only-a226-fullgraphdet-w13n32.sh",
    "host": "run-q38-a226-host-controlled.sh",
}
SRC_PORT = "19896"


def digest(data) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def pinned() -> dict[str, str]:
    pins = {}
    for line in (HERE / "frozen-a226-packet.sha256").read_text().splitlines():
        sha, name = line.split()
        pins[name] = sha
    return pins


def source(name: str, pins: dict[str, str]) -> str:
    data = (ROOT / name).read_bytes()
    if digest(data) != pins[name]:
        sys.exit(f"frozen A226 packet drifted: {name}")
    return data.decode()


def successor(text: str, attempt: int, port: str) -> str:
    def rename(seg: str) -> str:
        seg = seg.replace("tp4-mtp1-4352-ple-only-a226", f"tp4-mtp1-4352-ple-only-a{attempt}")
        seg = seg.replace("attempt226", f"attempt{attempt}").replace(SRC_PORT, port)
        seg = seg.replace("ATTEMPT=189", f"ATTEMPT={attempt}").replace("a226", f"a{attempt}").replace("A226", f"A{attempt}")
        return seg
    parts, last = [], 0
    for m in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last:m.start()]))
        parts.append(m.group(0))
        last = m.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert SRC_PORT not in out and "attempt226" not in out
    return out


def replace_once(t: str, a: str, b: str) -> str:
    assert t.count(a) == 1, (t.count(a), a[:80])
    return t.replace(a, b)


def main() -> int:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    attempt = int(sys.argv[1]); port = sys.argv[2]; check = "--check" in sys.argv[3:]
    assert attempt > 226 and port.isdigit() and port != SRC_PORT
    pins = pinned()
    launcher = source(SRC["launcher"], pins)
    m = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M); assert m
    launcher = replace_once(launcher, "expected_derived=" + m.group(1), "expected_derived=" + "0" * 64)
    launcher = successor(launcher, attempt, port)
    env = os.environ.copy(); env[f"Q38_A{attempt}_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path(f"/tmp/q38-ple2k-a{attempt}-base.sh").unlink(missing_ok=True)
    assert f"q38-ple2k-a{attempt}" in derived
    launcher = launcher.replace("expected_derived=" + "0" * 64, "expected_derived=" + digest(derived))
    client = successor(source(SRC["client"], pins), attempt, port)
    supervisor = successor(source(SRC["supervisor"], pins), attempt, port)
    supervisor = replace_once(supervisor, "expected_wrapper=" + pins[SRC["launcher"]], "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=" + pins[SRC["client"]], "expected_client=" + digest(client))
    host = successor(source(SRC["host"], pins), attempt, port)
    host = replace_once(host, "expected_supervisor=" + pins[SRC["supervisor"]], "expected_supervisor=" + digest(supervisor))
    outputs = {
        f"launch-tp4-mtp1-4352-ple-only-a{attempt}-fullgraphdet-w13n32.sh": launcher,
        f"run-tp4-mtp1-4352-ple-only-a{attempt}-fullgraphdet-w13n32-client.sh": client,
        f"supervise-tp4-mtp1-4352-ple-only-a{attempt}-fullgraphdet-w13n32.sh": supervisor,
        f"run-q38-a{attempt}-host-controlled.sh": host,
    }
    for name, text in outputs.items():
        p = ROOT / name
        if check:
            if not p.exists() or p.read_text() != text:
                sys.exit(f"packet a{attempt} differs from a fresh derivation: {name}")
            continue
        if p.exists():
            sys.exit(f"refusing to overwrite {p}")
        p.write_text(text); p.chmod(0o755)
    for name in outputs:
        print(digest((ROOT / name).read_bytes()), name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
