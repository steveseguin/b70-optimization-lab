#!/usr/bin/env python3
"""Create the A364 certification packet from frozen A305 - the certified MTP1 frozen-client
record packet - with the GDN verifier rows run by the kernel extension's own exact serial mode
instead of vLLM's Python serial path.

A362 (diag driver, stage v2) held the lineage's exact-2K hash on every row with the two-row
verify step at 33.7 ms instead of 42.7, and the kernel-level probe
(probes/gdn-spec-round-state-equivalence.py) is bit-identical for the mode. A364 puts the same
server through the full frozen client: bench-short, the quality screen, the exact-2K and
exact-4K repeats, the recovery canary, and the official selection receipt.

What moves against A305, and nothing else:
- the loaded kernel stage: `runtime-gdn-roundstate-bbae3c5-b70` (served stage with `_xpu_C`
  rebuilt from kernel commit bbae3c5 on e421889, which carries ad25aa9's generalisation of the
  exact replay to the MTP row count; the served build hard-gates it to four rows), with its own
  loadable manifest and stage build head;
- the derived server exports: VLLM_XPU_GDN_SERIAL_SPEC_DECODE=0 and the extension's
  VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1 / VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1
  (plus the completion barrier when BARRIER is set);
- the client's live-server selector check and identity receipts for the above.
The vLLM overlay head 6d872457, the tuned map, the verifier and every other pin stay."""
from __future__ import annotations
import hashlib, os, re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A364_REWRITE_VALIDATE_ONLY") == "1"
BARRIER = os.environ.get("Q38_A364_BARRIER", "1") == "1"
SOURCES = {
    'launch-tp4-mtp1-4352-ple-only-a305-fullgraphdet-w13n32.sh': '40abf013e0bed5c8f240bddb4e49df09cef53459fa901ecfddf25846a1d670c3',
    'run-tp4-mtp1-4352-ple-only-a305-fullgraphdet-w13n32-client.sh': '28c5b11cbc75ae39092282e7c6535208391ea68b521f2c02ebe4e0fd72f54ed2',
    'supervise-tp4-mtp1-4352-ple-only-a305-fullgraphdet-w13n32.sh': '0f25f30c1eb401af60630bc48057d00dfd3ff5c40fce00d5f085e339bc677e7b',
    'run-q38-a305-host-controlled.sh': '3406b140c26a0929a4f23242462e85cf9e1539043c5c830d723e3d627e3b0373',
}
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
OLD_STAGE = "/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70"
NEW_STAGE = "/mnt/usb-models/qwen38-build/runtime-gdn-roundstate-bbae3c5-b70"
OLD_MANIFEST = "runtime-stage-padding-guard-loadable.sha256"
NEW_MANIFEST = "runtime-stage-gdn-roundstate-v2-loadable.sha256"
OLD_STAGE_HEAD = "2f829747503c77d4814834dffd0840fb1dd9f75a"
NEW_STAGE_HEAD = "bbae3c59e226c1b0c2a2dca6c51b4465cf36fd26"
OLD_SELECTOR = "VLLM_XPU_GDN_SERIAL_SPEC_DECODE=1"
NEW_SELECTORS = ["VLLM_XPU_GDN_SERIAL_SPEC_DECODE=0", "VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1",
                 "VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1"] + (["VLLM_XPU_GDN_NATIVE_SPEC_COMPLETION_BARRIER=1"] if BARRIER else [])

def digest(data):
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()

def source(name):
    data = (ROOT / name).read_bytes()
    assert digest(data) == SOURCES[name], name
    return data.decode()

def successor(text):
    def rename(seg):
        seg = seg.replace("tp4-mtp1-4352-ple-only-a305", "tp4-mtp1-4352-ple-only-a364")
        seg = seg.replace("attempt305", "attempt364").replace("19974", "19977")
        seg = seg.replace("ATTEMPT=305", "ATTEMPT=364").replace("a305", "a364").replace("A305", "A364")
        return seg
    parts, last = [], 0
    for m in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last:m.start()]))
        parts.append(m.group(0))
        last = m.end()
    parts.append(rename(text[last:]))
    out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    assert "19974" not in out and "attempt305" not in out and "a305" not in out
    return out

def replace_n(t, a, b, n):
    assert t.count(a) == n, (t.count(a), a[:90])
    return t.replace(a, b)

def emit(name, text):
    p = ROOT / name
    if VALIDATE_ONLY:
        assert p.read_text() == text, name
        return
    assert not p.exists(), p
    p.write_text(text)
    p.chmod(0o755)

def main():
    launcher = source("launch-tp4-mtp1-4352-ple-only-a305-fullgraphdet-w13n32.sh")
    m = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M)
    assert m
    launcher = replace_n(launcher, "expected_derived=" + m.group(1), "expected_derived=" + "0" * 64, 1)
    launcher = successor(launcher)
    launcher = replace_n(launcher, f"export KERNEL_STAGE={OLD_STAGE}\n", f"export KERNEL_STAGE={NEW_STAGE}\n", 1)
    anchor0 = '$0 == "export VLLM_XPU_GRAPH=0" { next }\n'
    line_rule = (f'$0 == "  expected_stage_build_head=\\"{OLD_STAGE_HEAD}\\"" '
                 f'{{ print "  expected_stage_build_head=\\"{NEW_STAGE_HEAD}\\""; next }}\n')
    launcher = replace_n(launcher, anchor0, line_rule + anchor0, 1)
    anchor1 = '  gsub(/enforce_eager=True/, "enforce_eager=False")\n'
    launcher = replace_n(launcher, anchor1, anchor1 + f'  gsub(/{OLD_MANIFEST.replace(".", "\\.")}/, "{NEW_MANIFEST}")\n', 1)
    anchor2 = f'  print "export {OLD_SELECTOR}"\n'
    launcher = replace_n(launcher, anchor2, anchor2 + "".join(f'  print "export {kv}"\n' for kv in NEW_SELECTORS), 1)
    env = os.environ.copy()
    env["Q38_A364_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a364-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a364" in derived
    assert f'expected_stage_build_head="{NEW_STAGE_HEAD}"' in derived
    # the served build head legitimately remains in the padding-receipt check (that receipt was
    # produced on the served stage); the stage identity line is the one that must move
    assert derived.count(OLD_STAGE_HEAD) == 1 and "padding_receipt['source']['kernel_head'] == '" + OLD_STAGE_HEAD in derived
    assert NEW_MANIFEST in derived and OLD_MANIFEST not in derived
    for kv in NEW_SELECTORS:
        assert f"export {kv}\n" in derived, kv
    launcher = launcher.replace("expected_derived=" + "0" * 64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp1-4352-ple-only-a305-fullgraphdet-w13n32-client.sh"))
    client = client.replace(OLD_STAGE_HEAD, NEW_STAGE_HEAD)
    old_check = f"grep -zFxq '{OLD_SELECTOR}' \"/proc/${{server_pid}}/environ\" || {{\n  printf 'FAIL: live server lacks the serial GDN verifier-row selector\n' >&2\n  exit 1\n}}\n"
    new_check = "".join(
        f"grep -zFxq '{kv}' \"/proc/${{server_pid}}/environ\" || {{\n  printf 'FAIL: live server lacks the exact GDN verifier selector {kv}\\n' >&2\n  exit 1\n}}\n"
        for kv in NEW_SELECTORS)
    client = replace_n(client, old_check, new_check, 1)
    client = replace_n(client, f'"exact_verify_selectors": ["{OLD_SELECTOR}", ',
                       '"exact_verify_selectors": [' + "".join(f'"{kv}", ' for kv in NEW_SELECTORS), 1)
    assert OLD_SELECTOR not in client
    supervisor = successor(source("supervise-tp4-mtp1-4352-ple-only-a305-fullgraphdet-w13n32.sh"))
    supervisor = replace_n(supervisor, "expected_wrapper=" + SOURCES["launch-tp4-mtp1-4352-ple-only-a305-fullgraphdet-w13n32.sh"], "expected_wrapper=" + digest(launcher), 1)
    supervisor = replace_n(supervisor, "expected_client=" + SOURCES["run-tp4-mtp1-4352-ple-only-a305-fullgraphdet-w13n32-client.sh"], "expected_client=" + digest(client), 1)
    host = successor(source("run-q38-a305-host-controlled.sh"))
    host = replace_n(host, "expected_supervisor=" + SOURCES["supervise-tp4-mtp1-4352-ple-only-a305-fullgraphdet-w13n32.sh"], "expected_supervisor=" + digest(supervisor), 1)
    out_names = (
        "launch-tp4-mtp1-4352-ple-only-a364-fullgraphdet-w13n32.sh",
        "run-tp4-mtp1-4352-ple-only-a364-fullgraphdet-w13n32-client.sh",
        "supervise-tp4-mtp1-4352-ple-only-a364-fullgraphdet-w13n32.sh",
        "run-q38-a364-host-controlled.sh",
    )
    for name, text in zip(out_names, (launcher, client, supervisor, host)):
        emit(name, text)
    for name in out_names:
        print(digest((ROOT / name).read_bytes()), name)

if __name__ == "__main__":
    main()
