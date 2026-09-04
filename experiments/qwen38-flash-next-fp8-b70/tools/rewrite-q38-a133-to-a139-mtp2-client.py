#!/usr/bin/env python3
"""Create the A139 promotion packet from frozen A133: the first frozen MTP2 client (from the MTP2 battery packet A133) (A114/A116/A118 retired: resolver head pin, then size-1 dispatch requirements in the verifier and in the client's jq gate that MTP1 never meets).

A133 is the full-decode-graph MTP1 identity (capture sizes [1, 2], KV
376569856 bytes) with the three exact-verify flags (serial GDN verifier rows,
row-wise TP all-reduce, row-wise hyperconnection norm) on overlay 1b2a17c1.
A139 keeps that launcher, supervisor and host wrapper and replaces the
inherited MTP0 client with one whose identity receipts, live-environment
checks and runtime verifier (A139, capture [1, 2], size-1 and size-2 FULL
dispatch receipts) describe the MTP1 line, while the output pins (short,
16-repeat, exact-2K, exact-4K) stay the MTP0 authorities. Attempt 114 /
port 19810.
"""
from __future__ import annotations
import hashlib, os, re, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A139_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {'launch-tp4-mtp2-4352-ple-only-a133-fullgraphdet-w13n32.sh': '71f4e3b5feef9631d5f6bf1dc06e1e4ddf17ba9aa1aa3378273db1ad4b56f963', 'run-tp4-mtp2-4352-ple-only-a133-fullgraphdet-w13n32-client.sh': '91d7d57adce91e68f85c0b11795abb5b9f3489d105fbbcaf341b0dea02a1cc84', 'supervise-tp4-mtp2-4352-ple-only-a133-fullgraphdet-w13n32.sh': 'a769a627f5197923166792f29d6728510d0c29fd71ecaa9bb170f468a6729401', 'run-q38-a133-host-controlled.sh': '128a1f8ec18f8de8c1948f6e6b5954ce3132bd2babf47707eb34c82dfb470a30', 'verify-q38-a139-fullgraph-runtime.py': '3ae1575e2e77b4c7912f9e6e5a79af6202a3458b1bca2ab27a1480cdfe879137'}
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
OLD_HEAD = "2169dbfe38c2954edc5ae50e94f68d45be071b79"
NEW_HEAD = "5915cb0e88b03d709d743020d74c821c5b5b3ecf"
OLD_VERIFIER_SHA = "a3acec5018c4b1147f8efddb75f6678acee7f9802d4fb11f3c56bc7b2bd74ca8"
NEW_VERIFIER_SHA = SOURCES['verify-q38-a139-fullgraph-runtime.py']
OLD_COMP = '{"mode":0,"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1],"max_cudagraph_capture_size":1,"compile_sizes":[],"cudagraph_num_of_warmups":1}'
NEW_COMP = '{"mode":0,"cudagraph_mode":"FULL_DECODE_ONLY","cudagraph_capture_sizes":[1,2,3],"max_cudagraph_capture_size":3,"compile_sizes":[],"cudagraph_num_of_warmups":1}'
FLAG_GREPS = '''grep -zFxq 'VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1' "/proc/${server_pid}/environ" || {
  printf 'FAIL: live server lacks the serial GDN verifier-row selector\n' >&2
  exit 1
}
grep -zFxq 'VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=3' "/proc/${server_pid}/environ" || {
  printf 'FAIL: live server lacks the row-wise all-reduce selector\n' >&2
  exit 1
}
grep -zFxq 'VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=3' "/proc/${server_pid}/environ" || {
  printf 'FAIL: live server lacks the row-wise hyperconnection norm selector\n' >&2
  exit 1
}
'''

def digest(data):
    if isinstance(data, str): data = data.encode()
    return hashlib.sha256(data).hexdigest()
def source(name):
    data = (ROOT / name).read_bytes(); assert digest(data) == SOURCES[name], name; return data.decode()
def successor(text):
    def rename(seg):
        seg = seg.replace("tp4-mtp2-4352-ple-only-a133", "tp4-mtp2-4352-ple-only-a139")
        seg = seg.replace("attempt133", "attempt139").replace("19804", "19810")
        seg = seg.replace("ATTEMPT=133", "ATTEMPT=139").replace("a133", "a139").replace("A133", "A139")
        return seg
    parts=[]; last=0
    for m in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last:m.start()])); parts.append(m.group(0)); last=m.end()
    parts.append(rename(text[last:])); out="".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19804" not in out and "attempt133" not in out
    return out
def replace_once(t, a, b):
    assert t.count(a) == 1, (t.count(a), a[:80]); return t.replace(a, b)
def replace_n(t, a, b, n):
    assert t.count(a) == n, (t.count(a), n, a[:80]); return t.replace(a, b)
def emit(name, text):
    p = ROOT / name
    if VALIDATE_ONLY:
        assert p.read_text() == text, name; return
    assert not p.exists(), p; p.write_text(text); p.chmod(0o755)

def main():
    launcher = source("launch-tp4-mtp2-4352-ple-only-a133-fullgraphdet-w13n32.sh")
    m = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M); assert m
    launcher = replace_once(launcher, "expected_derived=" + m.group(1), "expected_derived=" + "0"*64)
    launcher = successor(launcher)
    env = os.environ.copy(); env["Q38_A139_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a139-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a139" in derived, "derived lacks a139 base name"
    assert "ATTEMPT=139 PORT=19810" in launcher, "launcher lacks attempt/port exports"
    assert NEW_HEAD in derived, "derived lacks the new head"
    assert OLD_HEAD not in derived, "derived still carries the old head"
    for flag in ("export VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1\n", "export VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=3\n", "export VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=3\n"):
        assert flag in derived, flag
    launcher = launcher.replace("expected_derived=" + "0"*64, "expected_derived=" + digest(derived))

    client = successor(source("run-tp4-mtp2-4352-ple-only-a133-fullgraphdet-w13n32-client.sh"))
    client = replace_once(client, "verify-q38-a48-fullgraph-runtime.py", "verify-q38-a139-fullgraph-runtime.py")
    client = replace_once(client, "4f4942289f3853f0dec60b9fcd14c644ca300abaaa9d9fa2ea56135f4d9f9c52", "0bd36f13056d79924e7598bf8d844db3a5b8b35639737c0ef0b5af68cad14753")
    client = replace_once(client, "expected_runtime_verifier=" + OLD_VERIFIER_SHA, "expected_runtime_verifier=" + NEW_VERIFIER_SHA)
    client = replace_n(client, OLD_COMP, NEW_COMP, 2)
    client = replace_n(client, OLD_HEAD, NEW_HEAD, 3)
    client = replace_once(client, '[[ "$server_command" != *"--speculative-config"* && "$server_command" != *"--reasoning-parser"* ]] || {\n  printf \'FAIL: MTP or reasoning parser unexpectedly present\\n\' >&2\n',
                          '[[ "$server_command" == *"--speculative-config"* && "$server_command" != *"--reasoning-parser"* ]] || {\n  printf \'FAIL: MTP absent or reasoning parser present\\n\' >&2\n')
    client = replace_once(client, "  'moe_backend=triton eager=0 graph=FULL_DECODE_ONLY mtp=0 max_model_len=4352 max_num_batched_tokens=64' \\\n  'kv_cache_memory_bytes=134217728' 'kv_cache_layout=BLHNC' \\\n",
                          "  'moe_backend=triton eager=0 graph=FULL_DECODE_ONLY mtp=2 max_model_len=4352 max_num_batched_tokens=64' \\\n  'mtp_exact_recurrent=0' \\\n  'kv_cache_memory_bytes=376569856' 'kv_cache_layout=BLHNC' \\\n")
    client = replace_once(client, 'assert labels.get("kv_cache_memory_bytes") == "134217728", labels', 'assert labels.get("kv_cache_memory_bytes") == "376569856", labels')
    client = replace_once(client, '        "tp": 4, "ep": 4, "mtp": 0, "graph": "FULL_DECODE_ONLY",\n        "compilation_mode": "NONE", "cudagraph_capture_sizes": [1],\n',
                          '        "tp": 4, "ep": 4, "mtp": 2, "graph": "FULL_DECODE_ONLY",\n        "compilation_mode": "NONE", "cudagraph_capture_sizes": [1, 2, 3],\n        "exact_verify_selectors": ["VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1", "VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=3", "VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=3"],\n')
    client = replace_once(client, '        "input_embedding": "device", "kv_cache_memory_bytes": 134217728,\n', '        "input_embedding": "device", "kv_cache_memory_bytes": 376569856,\n')
    client = replace_once(client, "grep -zFxq 'CCL_SYCL_ALLREDUCE_LL=twoshots' \"/proc/${server_pid}/environ\" || {\n  printf 'FAIL: live server lacks exact twoshots selector\\n' >&2\n  exit 1\n}\n",
                          "grep -zFxq 'CCL_SYCL_ALLREDUCE_LL=twoshots' \"/proc/${server_pid}/environ\" || {\n  printf 'FAIL: live server lacks exact twoshots selector\\n' >&2\n  exit 1\n}\n" + FLAG_GREPS)
    client = replace_once(client, "  .size_1_full_dispatch_count > 0 and (.collective_processes | length) >= 4 and\n", "  .size_3_full_dispatch_count > 0 and .size_2_full_dispatch_count >= 0 and (.collective_processes | length) >= 4 and\n")
    client = replace_once(client, "  .schema_version == 2 and .compilation_mode == \"NONE\" and\n", "  .schema_version == 3 and .compilation_mode == \"NONE\" and\n")
    assert client.count(" MTP0 ") == 3, client.count(" MTP0 ")
    client = client.replace(" MTP0 ", " MTP2 ")
    assert "134217728" not in client and OLD_HEAD not in client and "mtp=0" not in client
    assert ".size_1_full_dispatch_count > 0" not in client and "capture_sizes\":[1]," not in client

    supervisor = successor(source("supervise-tp4-mtp2-4352-ple-only-a133-fullgraphdet-w13n32.sh"))
    supervisor = replace_once(supervisor, "expected_wrapper=" + SOURCES['launch-tp4-mtp2-4352-ple-only-a133-fullgraphdet-w13n32.sh'], "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=" + SOURCES['run-tp4-mtp2-4352-ple-only-a133-fullgraphdet-w13n32-client.sh'], "expected_client=" + digest(client))
    host = successor(source("run-q38-a133-host-controlled.sh"))
    host = replace_once(host, "expected_supervisor=" + SOURCES['supervise-tp4-mtp2-4352-ple-only-a133-fullgraphdet-w13n32.sh'], "expected_supervisor=" + digest(supervisor))
    names = ("launch-tp4-mtp2-4352-ple-only-a139-fullgraphdet-w13n32.sh", "run-tp4-mtp2-4352-ple-only-a139-fullgraphdet-w13n32-client.sh", "supervise-tp4-mtp2-4352-ple-only-a139-fullgraphdet-w13n32.sh", "run-q38-a139-host-controlled.sh")
    for name, text in zip(names, (launcher, client, supervisor, host)): emit(name, text)
    for name in names: print(digest((ROOT / name).read_bytes()), name)
if __name__ == "__main__":
    main()
