#!/usr/bin/env python3
"""Create the A147 packet from frozen A78: byte-identical apart from attempt, port and state names (graph MTP0 step timing graph MTP0 step timing with --moe-backend auto (which selects the platform XPU FP8 MoE backend, grouped GEMM) instead of the explicit Triton backend, screening for exactness and step time)."""
from __future__ import annotations
import hashlib, os, re, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A147_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {'launch-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh': '736b5b92a757e4fd22ba271f42eabba72bf0c889018578d80c9a9246d3cd6a37', 'run-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32-client.sh': '38e0388cce6a39f9348a4e76051f96b0d912f7a4cd60d0e42aa9022d9a79185d', 'supervise-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh': '8a2b632651fdb14340f7f3643a839c7de9739b65be154f178e6871979da35134', 'run-q38-a78-host-controlled.sh': '7444be0bf492b73f4fd3a5aed2c8e54b32600d51b9d3f7dc0c4e0d32b9fea910'}
OLD_HEAD = "2169dbfe38c2954edc5ae50e94f68d45be071b79"
NEW_HEAD = "f8c7c0ee00ee8ac736b70d0e0657736a9f3d2e6c"
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
def digest(data):
    if isinstance(data, str): data = data.encode()
    return hashlib.sha256(data).hexdigest()
def source(name):
    data = (ROOT / name).read_bytes(); assert digest(data) == SOURCES[name], name; return data.decode()
def successor(text):
    def rename(seg):
        seg = seg.replace("tp4-mtp0-4352-ple-only-a78", "tp4-mtp0-4352-ple-only-a147")
        seg = seg.replace("attempt78", "attempt147").replace("19750", "19818")
        seg = seg.replace("ATTEMPT=78", "ATTEMPT=147").replace("a78", "a147").replace("A78", "A147")
        return seg
    parts=[]; last=0
    for m in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last:m.start()])); parts.append(m.group(0)); last=m.end()
    parts.append(rename(text[last:])); out="".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19750" not in out and "attempt78" not in out
    return out
def replace_n(t, a, b, n):
    assert t.count(a) == n, (t.count(a), n, a[:80]); return t.replace(a, b)
def replace_once(t, a, b):
    assert t.count(a) == 1, (t.count(a), a[:80]); return t.replace(a, b)
def emit(name, text):
    p = ROOT / name
    if VALIDATE_ONLY:
        assert p.read_text() == text, name; return
    assert not p.exists(), p; p.write_text(text); p.chmod(0o755)
def main():
    launcher = source("launch-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh")
    m = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M); assert m
    launcher = replace_once(launcher, "expected_derived=" + m.group(1), "expected_derived=" + "0"*64)
    launcher = successor(launcher)
    launcher = replace_n(launcher, OLD_HEAD, NEW_HEAD, 2)
    launcher = replace_once(launcher, "export KV_CACHE_MEMORY_BYTES=134217728\n", "export KV_CACHE_MEMORY_BYTES=134217728\nexport Q38_STEP_TIMING_LOG=10\n")
    launcher = replace_once(launcher, '  gsub(/moe_backend=triton eager=1/, "moe_backend=triton eager=0 graph=FULL_DECODE_ONLY")\n',
        '  gsub(/moe_backend=triton eager=1/, "moe_backend=auto eager=0 graph=FULL_DECODE_ONLY")\n'
        '  gsub(/moe_backend=.triton./, "moe_backend=\\047auto\\047")\n'
        '  gsub(/moe_backend == .triton./, "moe_backend == \\047auto\\047")\n'
        '  gsub(/--moe-backend triton/, "--moe-backend auto")\n')
    assert launcher.count("tp4_ep4_triton_fullgraphdet_mtp") >= 3
    launcher = launcher.replace("tp4_ep4_triton_fullgraphdet_mtp", "tp4_ep4_xpumoe_fullgraphdet_mtp")
    env = os.environ.copy(); env["Q38_A147_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a147-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a147" in derived
    assert "moe_backend='auto'" in derived and "--moe-backend auto" in derived and "moe_backend == 'auto'" in derived
    assert "moe_backend=auto eager=0" in derived and "tp4_ep4_xpumoe_fullgraphdet_mtp" in derived
    assert "moe_backend=triton" not in derived and "'triton'" not in derived and "--moe-backend triton" not in derived, [l for l in derived.splitlines() if "triton" in l][:8]
    assert f'expected_vllm_head="{NEW_HEAD}"' in derived and OLD_HEAD not in derived
    "export Q38_STEP_TIMING_LOG=10\n" in derived
    launcher = launcher.replace("expected_derived=" + "0"*64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32-client.sh"))
    supervisor = successor(source("supervise-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh"))
    supervisor = replace_once(supervisor, "expected_wrapper=" + SOURCES["launch-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh"], "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=" + SOURCES["run-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32-client.sh"], "expected_client=" + digest(client))
    host = successor(source("run-q38-a78-host-controlled.sh"))
    host = replace_once(host, "expected_supervisor=" + SOURCES["supervise-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh"], "expected_supervisor=" + digest(supervisor))
    out_names = ("launch-tp4-mtp0-4352-ple-only-a147-fullgraphdet-w13n32.sh", "run-tp4-mtp0-4352-ple-only-a147-fullgraphdet-w13n32-client.sh", "supervise-tp4-mtp0-4352-ple-only-a147-fullgraphdet-w13n32.sh", "run-q38-a147-host-controlled.sh")
    for name, text in zip(out_names, (launcher, client, supervisor, host)): emit(name, text)
    for name in out_names: print(digest((ROOT / name).read_bytes()), name)
if __name__ == "__main__":
    main()
