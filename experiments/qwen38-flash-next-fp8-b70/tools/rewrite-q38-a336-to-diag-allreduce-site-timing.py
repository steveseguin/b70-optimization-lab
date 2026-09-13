#!/usr/bin/env python3
"""Derive a timing-diagnostic MTP0 packet from the frozen promoted A336 packet (W13-N64, graph,
placement): identical apart from attempt, port and state names, the overlay head (the diagnostic
head on the promoted line) and a block of Q38_* exports in the launcher.

usage: rewrite-q38-a336-to-diag-allreduce-site-timing.py <attempt> <port> <new_head> <extra_env...>
       Q38_REWRITE_VALIDATE_ONLY=1 ... re-checks an emitted packet byte for byte.
"""
from __future__ import annotations
import hashlib, os, re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
attempt, port, NEW_HEAD, *extra_env = sys.argv[1:]
assert re.fullmatch(r"[0-9a-f]{40}", NEW_HEAD)
VALIDATE_ONLY = os.environ.get("Q38_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {
    'launch-tp4-mtp0-4352-ple-only-a336-fullgraphdet-w13n64.sh': 'cb48ec0507f78d618ee60d2dbb61a29ce027041fefd5b2cd292cf3458eba9240',
    'run-tp4-mtp0-4352-ple-only-a336-fullgraphdet-w13n64-client.sh': 'e681c5eaf4dbbfc4de37b1c848581ae9a01d8d1f900bd6eefdbdc9377844139a',
    'supervise-tp4-mtp0-4352-ple-only-a336-fullgraphdet-w13n64.sh': '7a923ecc2eea552ef7858897043d327e3a6380d89a76d793ed3d0aedd5ea76c8',
    'run-q38-a336-host-controlled.sh': '5c82156670f79f9368c613895d4bb022cd998b9a18999c4a03f9d9fcdc901543',
}
OLD_HEAD = "2a372e860e273273357cb7437ac7de1694304f9f"
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
def digest(data):
    if isinstance(data, str): data = data.encode()
    return hashlib.sha256(data).hexdigest()
def source(name):
    data = (ROOT / name).read_bytes(); assert digest(data) == SOURCES[name], name; return data.decode()
def successor(text):
    def rename(seg):
        seg = seg.replace("tp4-mtp0-4352-ple-only-a336", f"tp4-mtp0-4352-ple-only-a{attempt}")
        seg = seg.replace("attempt336", f"attempt{attempt}").replace("19949", port)
        seg = seg.replace("ATTEMPT=336", f"ATTEMPT={attempt}").replace("a336", f"a{attempt}").replace("A336", f"A{attempt}")
        return seg
    parts, last = [], 0
    for m in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last:m.start()])); parts.append(m.group(0)); last = m.end()
    parts.append(rename(text[last:])); out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    stripped = HASH_TOKEN.sub("", out)
    assert "19949" not in stripped and "attempt336" not in stripped and "a336" not in stripped
    return out
def replace_n(t, a, b, n):
    assert t.count(a) == n, (t.count(a), n, a[:90]); return t.replace(a, b)
def emit(name, text):
    p = ROOT / name
    if VALIDATE_ONLY:
        assert p.read_text() == text, name; return
    assert not p.exists(), p; p.write_text(text); p.chmod(0o755)
def main():
    launcher = source("launch-tp4-mtp0-4352-ple-only-a336-fullgraphdet-w13n64.sh")
    m = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M); assert m
    launcher = replace_n(launcher, "expected_derived=" + m.group(1), "expected_derived=" + "0" * 64, 1)
    launcher = successor(launcher)
    launcher = replace_n(launcher, OLD_HEAD, NEW_HEAD, 2)
    OPTS = ("MAXLEN:", "KVBYTES:", "PLACEMENT:", "USERS:")
    exports = "".join(f"export {kv}\n" for kv in extra_env if not kv.startswith(OPTS))
    # USERS:<n> serves n sequences: max_num_seqs, decode graph capture sizes [1,2,4,...,n], and the
    # row-wise all-reduce / HC-norm selectors at n rows (batch invariance for the multi-user identity gate).
    us = [kv2.split(":", 1)[1] for kv2 in extra_env if kv2.startswith("USERS:")]
    if us:
        n = int(us[0]); sizes = [1]
        while sizes[-1] < n: sizes.append(sizes[-1] * 2)
        assert sizes[-1] == n, "USERS must be a power of two"
        py_list = ", ".join(str(x) for x in sizes); js_list = ",".join(str(x) for x in sizes)
        # these two literals live in the frozen base: rewrite them with exact-line awk rules
        anchor0 = '$0 == "export VLLM_XPU_GRAPH=0" { next }\n'
        rules = (f'$0 == "    max_num_seqs=1, max_num_batched_tokens=64," {{ print "    max_num_seqs={n}, max_num_batched_tokens=64,"; next }}\n'
                 f'$0 == "  --max-num-seqs 1" {{ print "  --max-num-seqs {n}"; next }}\n')
        launcher = replace_n(launcher, anchor0, rules + anchor0, 1)
        if "grep -Fxq '  --max-num-seqs 1' \"$derived\"" in launcher:
            launcher = launcher.replace("grep -Fxq '  --max-num-seqs 1' \"$derived\"", f"grep -Fxq '  --max-num-seqs {n}' \"$derived\"")
        launcher = replace_n(launcher, "'\\''cudagraph_capture_sizes'\\'': [1],", f"'\\''cudagraph_capture_sizes'\\'': [{py_list}],", 1)
        launcher = replace_n(launcher, "'\\''max_cudagraph_capture_size'\\'': 1, ", f"'\\''max_cudagraph_capture_size'\\'': {n}, ", 1)
        launcher = replace_n(launcher, "assert config.compilation_config.cudagraph_capture_sizes == [1]", f"assert config.compilation_config.cudagraph_capture_sizes == [{py_list}]", 1)
        launcher = replace_n(launcher, "assert config.compilation_config.max_cudagraph_capture_size == 1", f"assert config.compilation_config.max_cudagraph_capture_size == {n}", 1)
        launcher = replace_n(launcher, '\\"cudagraph_capture_sizes\\":[1],\\"max_cudagraph_capture_size\\":1', f'\\"cudagraph_capture_sizes\\":[{js_list}],\\"max_cudagraph_capture_size\\":{n}', 2)
        anchor_q = '  print "export VLLM_XPU_QSA_FUSED_INDEXER=1"\n'
        launcher = replace_n(launcher, anchor_q, anchor_q + f'  print "export VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS={n}"\n  print "export VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS={n}"\n', 1)
    # PLACEMENT:<path> swaps the expert host-placement file (bit-exact by construction; only VRAM moves).
    pl = [kv2.split(":", 1)[1] for kv2 in extra_env if kv2.startswith("PLACEMENT:")]
    if pl:
        launcher = replace_n(launcher, "export Q38_EXPERT_HOST_PLACEMENT=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/data/20260906-q38-expert-host-placement-3p5gib-per-rank.json\n", f"export Q38_EXPERT_HOST_PLACEMENT={pl[0]}\n", 1)
    # MAXLEN:<n> and KVBYTES:<n> override the served context and KV budget (long-context arms).
    lc = {k: v for k, v in (kv2.split(":", 1) for kv2 in extra_env if kv2.startswith(("MAXLEN:", "KVBYTES:", "PLACEMENT:", "USERS:")))}
    if "MAXLEN" in lc:
        launcher = replace_n(launcher, " MAX_MODEL_LEN=4352 ", f" MAX_MODEL_LEN={lc['MAXLEN']} ", 1)
        # the derived script's frozen-context check and message, printed by the launcher's awk rules
        launcher = replace_n(launcher, 'print "[[ \\"${max_model_len}\\" == \\"4352\\" ]] || {"', 'print "[[ \\"${max_model_len}\\" == \\"' + lc["MAXLEN"] + '\\" ]] || {"', 1)
        launcher = replace_n(launcher, "frozen to MAX_MODEL_LEN=4352", "frozen to MAX_MODEL_LEN=" + lc["MAXLEN"], 1)
        # the launcher's campaign literal (used for the derived script's --ack and the run/cache dirs) follows the served context
        launcher = replace_n(launcher, 'campaign=qwen38-flash-next-fp8-tp4-ep4-fullgraphdet-mtp0-4352-ple-only-r1\n', 'campaign=qwen38-flash-next-fp8-tp4-ep4-fullgraphdet-mtp0-' + lc["MAXLEN"] + '-ple-only-r1\n', 1)
        # the launcher's own derived-source assertion of the frozen-context check line
        launcher = replace_n(launcher, "grep -Fxq '[[ \"${max_model_len}\" == \"4352\" ]] || {' \"$derived\"", "grep -Fxq '[[ \"${max_model_len}\" == \"" + lc["MAXLEN"] + "\" ]] || {' \"$derived\"", 1)
    if "KVBYTES" in lc:
        launcher = replace_n(launcher, "export KV_CACHE_MEMORY_BYTES=134217728\n", f"export KV_CACHE_MEMORY_BYTES={lc['KVBYTES']}\n", 1)
        kv_anchor_value = lc["KVBYTES"]
    else:
        kv_anchor_value = "134217728"
    launcher = replace_n(launcher, f"export KV_CACHE_MEMORY_BYTES={kv_anchor_value}\n", f"export KV_CACHE_MEMORY_BYTES={kv_anchor_value}\n" + exports, 1)
    env = os.environ.copy(); env[f"Q38_A{attempt}_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path(f"/tmp/q38-ple2k-a{attempt}-base.sh").unlink(missing_ok=True)
    assert f"q38-ple2k-a{attempt}" in derived
    assert f'expected_vllm_head="{NEW_HEAD}"' in derived and (NEW_HEAD == OLD_HEAD or OLD_HEAD not in derived)
    launcher = launcher.replace("expected_derived=" + "0" * 64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp0-4352-ple-only-a336-fullgraphdet-w13n64-client.sh"))
    if "MAXLEN" in lc:
        client = client.replace("-4352-ple-only-r1", "-" + lc["MAXLEN"] + "-ple-only-r1")
    client = client.replace(OLD_HEAD, NEW_HEAD)
    supervisor = successor(source("supervise-tp4-mtp0-4352-ple-only-a336-fullgraphdet-w13n64.sh"))
    if "MAXLEN" in lc:
        supervisor = supervisor.replace("-4352-ple-only-r1", "-" + lc["MAXLEN"] + "-ple-only-r1")
    supervisor = replace_n(supervisor, "expected_wrapper=" + SOURCES["launch-tp4-mtp0-4352-ple-only-a336-fullgraphdet-w13n64.sh"], "expected_wrapper=" + digest(launcher), 1)
    supervisor = replace_n(supervisor, "expected_client=" + SOURCES["run-tp4-mtp0-4352-ple-only-a336-fullgraphdet-w13n64-client.sh"], "expected_client=" + digest(client), 1)
    host = successor(source("run-q38-a336-host-controlled.sh"))
    if "MAXLEN" in lc:
        host = host.replace("-4352-ple-only-r1", "-" + lc["MAXLEN"] + "-ple-only-r1")
    host = replace_n(host, "expected_supervisor=" + SOURCES["supervise-tp4-mtp0-4352-ple-only-a336-fullgraphdet-w13n64.sh"], "expected_supervisor=" + digest(supervisor), 1)
    out_names = (
        f"launch-tp4-mtp0-4352-ple-only-a{attempt}-fullgraphdet-w13n64.sh",
        f"run-tp4-mtp0-4352-ple-only-a{attempt}-fullgraphdet-w13n64-client.sh",
        f"supervise-tp4-mtp0-4352-ple-only-a{attempt}-fullgraphdet-w13n64.sh",
        f"run-q38-a{attempt}-host-controlled.sh",
    )
    for name, text in zip(out_names, (launcher, client, supervisor, host)): emit(name, text)
    for name in out_names: print(digest((ROOT / name).read_bytes()), name)
if __name__ == "__main__":
    main()
