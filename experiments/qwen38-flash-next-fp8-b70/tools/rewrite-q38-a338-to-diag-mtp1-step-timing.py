#!/usr/bin/env python3
"""Derive a timing-diagnostic MTP0 packet from the frozen promoted A338 packet (W13-N64, graph,
placement): identical apart from attempt, port and state names, the overlay head (the diagnostic
head on the promoted line) and a block of Q38_* exports in the launcher.

usage: rewrite-q38-a338-to-diag-allreduce-site-timing.py <attempt> <port> <new_head> <extra_env...>
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
    'launch-tp4-mtp1-4352-ple-only-a338-fullgraphdet-w13n32.sh': '29cf042e8fd431269efdef4e85a753b27301c319f704c2a1419750e9dca938b5',
    'run-tp4-mtp1-4352-ple-only-a338-fullgraphdet-w13n32-client.sh': '1d75682819ec1e4072a412ea5cc72c1c75876abadb8c108d63c5d3ea83de805d',
    'supervise-tp4-mtp1-4352-ple-only-a338-fullgraphdet-w13n32.sh': '679e0784afd550fb356c85af777c98fa879ee2c6959ab2f31ddf66c96a599837',
    'run-q38-a338-host-controlled.sh': '169f27220b91995585bd856542f793a9850a5093a49c83b2ce752b4ad4e71098',
}
OLD_HEAD = "6d8724577dabbee5fa0bbc70c4d927c6174c8d8a"
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
def digest(data):
    if isinstance(data, str): data = data.encode()
    return hashlib.sha256(data).hexdigest()
def source(name):
    data = (ROOT / name).read_bytes(); assert digest(data) == SOURCES[name], name; return data.decode()
def successor(text):
    def rename(seg):
        seg = seg.replace("tp4-mtp1-4352-ple-only-a338", f"tp4-mtp1-4352-ple-only-a{attempt}")
        seg = seg.replace("attempt338", f"attempt{attempt}").replace("19951", port)
        seg = seg.replace("ATTEMPT=338", f"ATTEMPT={attempt}").replace("a338", f"a{attempt}").replace("A338", f"A{attempt}")
        return seg
    parts, last = [], 0
    for m in HASH_TOKEN.finditer(text):
        parts.append(rename(text[last:m.start()])); parts.append(m.group(0)); last = m.end()
    parts.append(rename(text[last:])); out = "".join(parts)
    assert sorted(HASH_TOKEN.findall(out)) == sorted(HASH_TOKEN.findall(text))
    stripped = HASH_TOKEN.sub("", out)
    assert "19951" not in stripped and "attempt338" not in stripped and "a338" not in stripped
    return out
def replace_n(t, a, b, n):
    assert t.count(a) == n, (t.count(a), n, a[:90]); return t.replace(a, b)
def emit(name, text):
    p = ROOT / name
    if VALIDATE_ONLY:
        assert p.read_text() == text, name; return
    assert not p.exists(), p; p.write_text(text); p.chmod(0o755)
def main():
    launcher = source("launch-tp4-mtp1-4352-ple-only-a338-fullgraphdet-w13n32.sh")
    m = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M); assert m
    launcher = replace_n(launcher, "expected_derived=" + m.group(1), "expected_derived=" + "0" * 64, 1)
    launcher = successor(launcher)
    launcher = replace_n(launcher, OLD_HEAD, NEW_HEAD, 2)
    # Plain entries become launcher exports (Q38_* survive into the engine). Entries prefixed
    # DERIVED: are printed into the derived server script next to the other VLLM_XPU_* exports,
    # because the derived launcher unsets every inherited VLLM_* variable.
    plain = [kv for kv in extra_env if not kv.startswith(("DERIVED:", "STAGE:", "MANIFEST:", "STAGE_BUILD_HEAD:", "MAXLEN:", "KVBYTES:", "PLACEMENT:"))]
    derived_kvs = [kv[len("DERIVED:"):] for kv in extra_env if kv.startswith("DERIVED:")]
    exports = "".join(f"export {kv}\n" for kv in plain)
    # PLACEMENT:<path> swaps the expert host-placement file (bit-exact by construction; only VRAM moves).
    pl = [kv2.split(":", 1)[1] for kv2 in extra_env if kv2.startswith("PLACEMENT:")]
    if pl:
        launcher = replace_n(launcher, "export Q38_EXPERT_HOST_PLACEMENT=/home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/data/20260906-q38-expert-host-placement-3p5gib-per-rank.json\n", f"export Q38_EXPERT_HOST_PLACEMENT={pl[0]}\n", 1)
    # MAXLEN:<n> and KVBYTES:<n> override the served context and KV budget (long-context arms).
    lc = {k: v for k, v in (kv2.split(":", 1) for kv2 in extra_env if kv2.startswith(("MAXLEN:", "KVBYTES:", "PLACEMENT:")))}
    if "MAXLEN" in lc:
        launcher = replace_n(launcher, " MAX_MODEL_LEN=4352 ", f" MAX_MODEL_LEN={lc['MAXLEN']} ", 1)
        # the derived script's frozen-context check and message, printed by the launcher's awk rules
        launcher = replace_n(launcher, 'print "[[ \\"${max_model_len}\\" == \\"4352\\" ]] || {"', 'print "[[ \\"${max_model_len}\\" == \\"' + lc["MAXLEN"] + '\\" ]] || {"', 1)
        launcher = replace_n(launcher, "frozen to MAX_MODEL_LEN=4352", "frozen to MAX_MODEL_LEN=" + lc["MAXLEN"], 1)
    if "KVBYTES" in lc:
        launcher = replace_n(launcher, "export KV_CACHE_MEMORY_BYTES=376569856\n", f"export KV_CACHE_MEMORY_BYTES={lc['KVBYTES']}\n", 1)
        kv_anchor_value = lc["KVBYTES"]
    else:
        kv_anchor_value = "376569856"
    launcher = replace_n(launcher, f"export KV_CACHE_MEMORY_BYTES={kv_anchor_value}\n", f"export KV_CACHE_MEMORY_BYTES={kv_anchor_value}\n" + exports, 1)
    # STAGE:<dir> MANIFEST:<file name under data/> STAGE_BUILD_HEAD:<sha> swap the loaded kernel
    # stage: the launcher's KERNEL_STAGE export, and gsub rules in the derived script for the
    # manifest file name and the recorded stage build head.
    opts = {k: v for k, v in (kv.split(":", 1) for kv in extra_env if kv.startswith(("STAGE:", "MANIFEST:", "STAGE_BUILD_HEAD:")))}
    if "STAGE" in opts:
        launcher = replace_n(launcher, "export KERNEL_STAGE=/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70\n", f"export KERNEL_STAGE={opts['STAGE']}\n", 1)
    rules = ""
    if "MANIFEST" in opts:
        rules += f'  gsub(/runtime-stage-padding-guard-loadable\\.sha256/, "{opts["MANIFEST"]}")\n'
    if "STAGE_BUILD_HEAD" in opts:
        # Exact-line rule (the served build head also appears in the padding receipt check).
        line_rule = ('$0 == "  expected_stage_build_head=\\"2f829747503c77d4814834dffd0840fb1dd9f75a\\"" '
                     '{ print "  expected_stage_build_head=\\"' + opts["STAGE_BUILD_HEAD"] + '\\""; next }\n')
        anchor0 = '$0 == "export VLLM_XPU_GRAPH=0" { next }\n'
        launcher = replace_n(launcher, anchor0, line_rule + anchor0, 1)
    if rules:
        anchor = '  gsub(/enforce_eager=True/, "enforce_eager=False")\n'
        launcher = replace_n(launcher, anchor, anchor + rules, 1)
    if derived_kvs:
        # after the last export of the block, so a DERIVED override of a printed selector wins
        anchor = '  print "export VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS=2"\n'
        launcher = replace_n(launcher, anchor, anchor + "".join(f'  print "export {kv}"\n' for kv in derived_kvs), 1)
    env = os.environ.copy(); env[f"Q38_A{attempt}_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path(f"/tmp/q38-ple2k-a{attempt}-base.sh").unlink(missing_ok=True)
    assert f"q38-ple2k-a{attempt}" in derived
    assert f'expected_vllm_head="{NEW_HEAD}"' in derived and (NEW_HEAD == OLD_HEAD or OLD_HEAD not in derived)
    if "MANIFEST" in opts:
        assert opts["MANIFEST"] in derived and "runtime-stage-padding-guard-loadable.sha256" not in derived
    if "STAGE_BUILD_HEAD" in opts:
        assert f'expected_stage_build_head="{opts["STAGE_BUILD_HEAD"]}"' in derived
    launcher = launcher.replace("expected_derived=" + "0" * 64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp1-4352-ple-only-a338-fullgraphdet-w13n32-client.sh"))
    if "MAXLEN" in lc:
        client = client.replace("-4352-ple-only-r1", "-" + lc["MAXLEN"] + "-ple-only-r1")
    client = client.replace(OLD_HEAD, NEW_HEAD)
    supervisor = successor(source("supervise-tp4-mtp1-4352-ple-only-a338-fullgraphdet-w13n32.sh"))
    if "MAXLEN" in lc:
        supervisor = supervisor.replace("-4352-ple-only-r1", "-" + lc["MAXLEN"] + "-ple-only-r1")
    supervisor = replace_n(supervisor, "expected_wrapper=" + SOURCES["launch-tp4-mtp1-4352-ple-only-a338-fullgraphdet-w13n32.sh"], "expected_wrapper=" + digest(launcher), 1)
    supervisor = replace_n(supervisor, "expected_client=" + SOURCES["run-tp4-mtp1-4352-ple-only-a338-fullgraphdet-w13n32-client.sh"], "expected_client=" + digest(client), 1)
    host = successor(source("run-q38-a338-host-controlled.sh"))
    if "MAXLEN" in lc:
        host = host.replace("-4352-ple-only-r1", "-" + lc["MAXLEN"] + "-ple-only-r1")
    host = replace_n(host, "expected_supervisor=" + SOURCES["supervise-tp4-mtp1-4352-ple-only-a338-fullgraphdet-w13n32.sh"], "expected_supervisor=" + digest(supervisor), 1)
    out_names = (
        f"launch-tp4-mtp1-4352-ple-only-a{attempt}-fullgraphdet-w13n32.sh",
        f"run-tp4-mtp1-4352-ple-only-a{attempt}-fullgraphdet-w13n32-client.sh",
        f"supervise-tp4-mtp1-4352-ple-only-a{attempt}-fullgraphdet-w13n32.sh",
        f"run-q38-a{attempt}-host-controlled.sh",
    )
    for name, text in zip(out_names, (launcher, client, supervisor, host)): emit(name, text)
    for name in out_names: print(digest((ROOT / name).read_bytes()), name)
if __name__ == "__main__":
    main()
