#!/usr/bin/env python3
"""Create the A161 packet from frozen A78: byte-identical apart from attempt, port and state names (graph MTP0 step timing graph MTP0 step timing with the PLE n-gram table ON DEVICE (cpu_offload_gb=0, no UVA offload) instead of the 12 GiB per-rank UVA offload; xpu-smi bypassed; exactness checked against the authority)."""
from __future__ import annotations
import hashlib, os, re, subprocess, sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
import q38_freeze_mitigation as _fm
from pathlib import Path
ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A161_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {'launch-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh': '736b5b92a757e4fd22ba271f42eabba72bf0c889018578d80c9a9246d3cd6a37', 'run-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32-client.sh': '38e0388cce6a39f9348a4e76051f96b0d912f7a4cd60d0e42aa9022d9a79185d', 'supervise-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh': '8a2b632651fdb14340f7f3643a839c7de9739b65be154f178e6871979da35134', 'run-q38-a78-host-controlled.sh': '7444be0bf492b73f4fd3a5aed2c8e54b32600d51b9d3f7dc0c4e0d32b9fea910'}
OLD_HEAD = "2169dbfe38c2954edc5ae50e94f68d45be071b79"
NEW_HEAD = "dee67ee215d44a1b3e00bade2739827c320afcba"
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
def digest(data):
    if isinstance(data, str): data = data.encode()
    return hashlib.sha256(data).hexdigest()
def source(name):
    data = (ROOT / name).read_bytes(); assert digest(data) == SOURCES[name], name; return data.decode()
def successor(text):
    def rename(seg):
        seg = seg.replace("tp4-mtp0-4352-ple-only-a78", "tp4-mtp0-4352-ple-only-a161")
        seg = seg.replace("attempt78", "attempt161").replace("19750", "19831")
        seg = seg.replace("ATTEMPT=78", "ATTEMPT=161").replace("a78", "a161").replace("A78", "A161")
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

    def _awk(s):
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"').replace("'", "'\\''") + '"'
    RULES = "".join(
        "$0 == " + _awk(old) + " {\n  print " + _awk(new) + "\n  next\n}\n"
        for old, new in (
            ("    enable_prefix_caching=False, offload_backend='uva', cpu_offload_gb=12.25,", "    enable_prefix_caching=False, offload_backend='uva', cpu_offload_gb=0.0,"),
            ("assert config.offload_config.uva.cpu_offload_gb == 12.25", "assert config.offload_config.uva.cpu_offload_gb == 0.0"),
            ("offload_budget = int(12.25 * 1024**3)", "offload_budget = 0"),
            ("assert offload_bytes_per_rank < offload_budget", "assert offload_budget == 0"),
            ("assert offload_budget - offload_bytes_per_rank < 64 * 1024**2", "assert offload_bytes_per_rank == 12_800_061_440"),
            ("  printf 'cpu_offload_gb=12.25\\n'", "  printf 'cpu_offload_gb=0.0\\n'"),
            ("  --cpu-offload-gb 12.25", "  --cpu-offload-gb 0"),
            ('  verify_offload_receipt || fail "workers did not each report exact 12.22-GiB selective offload"', "  verify_offload_receipt || true"),
            ('verify_offload_receipt || fail "workers did not each report exact 12.22-GiB selective offload"', "verify_offload_receipt || true"),
        )
    )
    launcher = replace_once(launcher, _fm.LAUNCHER_ANCHOR, RULES + _fm.LAUNCHER_ANCHOR)
    launcher = _fm.patch_launcher(launcher)
    assert launcher.count('_selective_ple_only_uva') == 2, launcher.count('_selective_ple_only_uva')
    launcher = launcher.replace('_selective_ple_only_uva', '_ple_on_device')
    assert launcher.count('cpu_offload_gb=12.0,') == 1 and launcher.count('cpu_offload_gb=12.0\\n') == 1, (launcher.count('cpu_offload_gb=12.0,'), launcher.count('cpu_offload_gb=12.0\\n'))
    launcher = launcher.replace('cpu_offload_gb=12.0,', 'cpu_offload_gb=0.0,').replace('cpu_offload_gb=12.0\\n', 'cpu_offload_gb=0.0\\n')
    assert launcher.count("grep -Fxq 'offload_budget = int(12.0 * 1024**3)' ") == 1 and launcher.count("grep -Fxq '  --cpu-offload-gb 12.0' ") == 1
    launcher = launcher.replace("grep -Fxq 'offload_budget = int(12.0 * 1024**3)' ", "grep -Fxq 'offload_budget = 0' ").replace("grep -Fxq '  --cpu-offload-gb 12.0' ", "grep -Fxq '  --cpu-offload-gb 0' ")
    env = os.environ.copy(); env["Q38_A161_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a161-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a161" in derived
    _fm.check_derived(derived)
    assert "cpu_offload_gb=0.0," in derived and "--cpu-offload-gb 0\n" in derived and "_ple_on_device" in derived and "verify_offload_receipt || true" in derived
    assert "12.25" not in derived and "cpu_offload_gb=12.0" not in derived
    assert f'expected_vllm_head="{NEW_HEAD}"' in derived and OLD_HEAD not in derived
    assert "export Q38_STEP_TIMING_LOG=10\n" in launcher
    launcher = launcher.replace("expected_derived=" + "0"*64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32-client.sh"))
    supervisor = successor(source("supervise-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh"))
    supervisor = _fm.patch_supervisor(supervisor)
    supervisor = replace_once(supervisor, "expected_wrapper=" + SOURCES["launch-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh"], "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=" + SOURCES["run-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32-client.sh"], "expected_client=" + digest(client))
    host = successor(source("run-q38-a78-host-controlled.sh"))
    host = replace_once(host, "expected_supervisor=" + SOURCES["supervise-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh"], "expected_supervisor=" + digest(supervisor))
    out_names = ("launch-tp4-mtp0-4352-ple-only-a161-fullgraphdet-w13n32.sh", "run-tp4-mtp0-4352-ple-only-a161-fullgraphdet-w13n32-client.sh", "supervise-tp4-mtp0-4352-ple-only-a161-fullgraphdet-w13n32.sh", "run-q38-a161-host-controlled.sh")
    for name, text in zip(out_names, (launcher, client, supervisor, host)): emit(name, text)
    for name in out_names: print(digest((ROOT / name).read_bytes()), name)
if __name__ == "__main__":
    main()
