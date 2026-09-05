#!/usr/bin/env python3
"""Create the A179 packet from frozen A78: byte-identical apart from attempt, port and state names (graph MTP0 step timing at the promoted identity with VRAM headroom: UVA offload of embed_tokens plus routed experts matched by 'mlp.experts' and capped by the 13.4 GiB budget (the offloader sees layer params without their index, so the first ~2 layers' experts are offloaded; ~1.2-1.9 GiB/rank freed, bit-exact), Q38_MEM_NOTE=1 (Q38_DIAG_ROUTE=balanced: 10 experts spread 3/3/2/2 over the EP ranks, varying per replay), timing only)."""
from __future__ import annotations
import hashlib, os, re, subprocess, sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
import q38_freeze_mitigation as _fm
from pathlib import Path
ROOT = Path(__file__).resolve().parent
VALIDATE_ONLY = os.environ.get("Q38_A179_REWRITE_VALIDATE_ONLY") == "1"
SOURCES = {'launch-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh': '736b5b92a757e4fd22ba271f42eabba72bf0c889018578d80c9a9246d3cd6a37', 'run-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32-client.sh': '38e0388cce6a39f9348a4e76051f96b0d912f7a4cd60d0e42aa9022d9a79185d', 'supervise-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh': '8a2b632651fdb14340f7f3643a839c7de9739b65be154f178e6871979da35134', 'run-q38-a78-host-controlled.sh': '7444be0bf492b73f4fd3a5aed2c8e54b32600d51b9d3f7dc0c4e0d32b9fea910'}
OLD_HEAD = "2169dbfe38c2954edc5ae50e94f68d45be071b79"
NEW_HEAD = "08df70ea5a8e9f6c7112701c968aaf9a775ff0df"
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")
def digest(data):
    if isinstance(data, str): data = data.encode()
    return hashlib.sha256(data).hexdigest()
def source(name):
    data = (ROOT / name).read_bytes(); assert digest(data) == SOURCES[name], name; return data.decode()
def successor(text):
    def rename(seg):
        seg = seg.replace("tp4-mtp0-4352-ple-only-a78", "tp4-mtp0-4352-ple-only-a179")
        seg = seg.replace("attempt78", "attempt179").replace("19750", "19850")
        seg = seg.replace("ATTEMPT=78", "ATTEMPT=179").replace("a78", "a179").replace("A78", "A179")
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
PARAMS4_PY = "'ple_embedding.ngram_embedding.weight', 'embed_tokens.weight', 'mlp.experts'"
PARAMS4_CSV = "ple_embedding.ngram_embedding.weight,embed_tokens.weight,mlp.experts"
PARAMS4_SP = "ple_embedding.ngram_embedding.weight embed_tokens.weight mlp.experts"
SQ = "'\\''"  # how a single quote is spelled inside the launcher's single-quoted awk program
def q(t):
    return t.replace("'", SQ)
def patch_a179(l):
    l = replace_once(l, '  print substr($0, 1, RLENGTH) "' + q("'ple_embedding.ngram_embedding.weight',") + '"\n', '  print substr($0, 1, RLENGTH) "' + q(PARAMS4_PY) + '"\n')
    l = replace_once(l, '$0 == "embed_selector = ' + q("'embed_tokens.weight'") + '" { next }\n', '')
    l = replace_once(l, 'index($0, "assert f' + q("'.{embed_selector}.'") + '") == 1 { next }\n', '')
    l = replace_once(l, '$0 == "print(f' + q("'embed_bytes_per_rank={embed_bytes_per_rank}'") + ')" { next }\n', '')
    l = replace_once(l, '$0 == "embed_bytes_per_rank = 317_849_600" { next }\n', '$0 == "embed_bytes_per_rank = 317_849_600" {\n  print\n  print "experts_bytes_per_rank = 2 * (128 * 1280 * 2560 + 128 * 2560 * 640)"\n  next\n}\n')
    l = replace_once(l, '  print "offload_bytes_per_rank = ple_bytes_per_rank"\n', '  print "offload_bytes_per_rank = ple_bytes_per_rank + embed_bytes_per_rank + experts_bytes_per_rank"\n')
    l = l.replace('_selective_ple_only_uva', '_selective_ple_embed_experts_budget13p4_uva')
    l = replace_once(l, 'gsub(/12\\.25/, "12.0")', 'gsub(/12\\.25/, "13.4")')
    l = replace_once(l, 'gsub(/12\\.22/, "11.92")', 'gsub(/12\\.22/, "13.78")')
    l = replace_once(l, 'gsub(/exact_12\\.22/, "exact_11.92")', 'gsub(/exact_12\\.22/, "exact_13.78")')
    l = replace_once(l, 'gsub(/ple_embedding\\.ngram_embedding\\.weight,embed_tokens\\.weight/, "ple_embedding.ngram_embedding.weight")', 'gsub(/ple_embedding\\.ngram_embedding\\.weight,embed_tokens\\.weight/, "' + PARAMS4_CSV + '")')
    l = replace_once(l, 'gsub(/ple_embedding\\.ngram_embedding\\.weight embed_tokens\\.weight/, "ple_embedding.ngram_embedding.weight")', 'gsub(/ple_embedding\\.ngram_embedding\\.weight embed_tokens\\.weight/, "' + PARAMS4_SP + '")')
    l = replace_once(l, "grep -Fxq '    enable_prefix_caching=False, offload_backend=" + SQ + "uva" + SQ + ", cpu_offload_gb=12.0,' \"$derived\"\n", "grep -Fxq '    enable_prefix_caching=False, offload_backend=" + SQ + "uva" + SQ + ", cpu_offload_gb=13.4,' \"$derived\"\n")
    l = replace_once(l, 'grep -Fxq "        \'ple_embedding.ngram_embedding.weight\'," "$derived"\n', 'grep -Fxq "        ' + PARAMS4_PY + '" "$derived"\n')
    l = replace_once(l, 'grep -Fxq "    \'ple_embedding.ngram_embedding.weight\'," "$derived"\n', 'grep -Fxq "    ' + PARAMS4_PY + '" "$derived"\n')
    l = replace_once(l, "grep -Fxq 'offload_bytes_per_rank = ple_bytes_per_rank' \"$derived\"\n", "grep -Fxq 'offload_bytes_per_rank = ple_bytes_per_rank + embed_bytes_per_rank + experts_bytes_per_rank' \"$derived\"\ngrep -Fxq 'experts_bytes_per_rank = 2 * (128 * 1280 * 2560 + 128 * 2560 * 640)' \"$derived\"\n")
    l = replace_once(l, "grep -Fxq 'offload_budget = int(12.0 * 1024**3)' \"$derived\"\n", "grep -Fxq 'offload_budget = int(13.4 * 1024**3)' \"$derived\"\n")
    l = replace_once(l, "grep -Fxq '  --cpu-offload-gb 12.0' \"$derived\"\n", "grep -Fxq '  --cpu-offload-gb 13.4' \"$derived\"\n")
    l = replace_once(l, "grep -Fxq '  --cpu-offload-params ple_embedding.ngram_embedding.weight' \"$derived\"\n", "grep -Fxq '  --cpu-offload-params " + PARAMS4_SP + "' \"$derived\"\n")
    l = replace_once(l, "grep -Fxq '  printf " + SQ + "cpu_offload_gb=12.0\\n" + SQ + "' \"$derived\"\n", "grep -Fxq '  printf " + SQ + "cpu_offload_gb=13.4\\n" + SQ + "' \"$derived\"\n")
    l = replace_once(l, "grep -Fxq '  printf " + SQ + "cpu_offload_params=ple_embedding.ngram_embedding.weight\\n" + SQ + "' \"$derived\"\n", "grep -Fxq '  printf " + SQ + "cpu_offload_params=" + PARAMS4_CSV + "\\n" + SQ + "' \"$derived\"\n")
    l = replace_once(l, '! grep -Fq "\'embed_tokens.weight\'" "$derived"\n', 'grep -Fq "\'mlp.experts\'" "$derived"\n')
    return l
def patch_client(c):
    return replace_once(c, "'cpu_offload_gb=12.0' 'cpu_offload_params=ple_embedding.ngram_embedding.weight'", "'cpu_offload_gb=13.4' 'cpu_offload_params=" + PARAMS4_CSV + "'")

def main():
    launcher = source("launch-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh")
    m = re.search(r"^expected_derived=([0-9a-f]{64})$", launcher, re.M); assert m
    launcher = replace_once(launcher, "expected_derived=" + m.group(1), "expected_derived=" + "0"*64)
    launcher = successor(launcher)
    launcher = replace_n(launcher, OLD_HEAD, NEW_HEAD, 2)
    launcher = _fm.patch_launcher(launcher)
    launcher = replace_once(launcher, "export KV_CACHE_MEMORY_BYTES=134217728\n", "export KV_CACHE_MEMORY_BYTES=134217728\nexport Q38_STEP_TIMING_LOG=10\nexport Q38_MEM_NOTE=1\n")
    launcher = patch_a179(launcher)
    env = os.environ.copy(); env["Q38_A179_DERIVED_SOURCE_ONLY"] = "1"
    derived = subprocess.run(["bash"], input=launcher, text=True, capture_output=True, check=True, env=env).stdout
    Path("/tmp/q38-ple2k-a179-base.sh").unlink(missing_ok=True)
    assert "q38-ple2k-a179" in derived
    _fm.check_derived(derived)
    assert f'expected_vllm_head="{NEW_HEAD}"' in derived and OLD_HEAD not in derived
    assert "export Q38_MEM_NOTE=1\n" in launcher and "export Q38_STEP_TIMING_LOG=10\n" in launcher and "Q38_DIAG_ROUTE" not in launcher
    launcher = launcher.replace("expected_derived=" + "0"*64, "expected_derived=" + digest(derived))
    client = successor(source("run-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32-client.sh"))
    client = patch_client(client)
    supervisor = successor(source("supervise-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh"))
    supervisor = _fm.patch_supervisor(supervisor)
    supervisor = replace_once(supervisor, "expected_wrapper=" + SOURCES["launch-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh"], "expected_wrapper=" + digest(launcher))
    supervisor = replace_once(supervisor, "expected_client=" + SOURCES["run-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32-client.sh"], "expected_client=" + digest(client))
    host = successor(source("run-q38-a78-host-controlled.sh"))
    host = replace_once(host, "expected_supervisor=" + SOURCES["supervise-tp4-mtp0-4352-ple-only-a78-fullgraphdet-w13n32.sh"], "expected_supervisor=" + digest(supervisor))
    out_names = ("launch-tp4-mtp0-4352-ple-only-a179-fullgraphdet-w13n32.sh", "run-tp4-mtp0-4352-ple-only-a179-fullgraphdet-w13n32-client.sh", "supervise-tp4-mtp0-4352-ple-only-a179-fullgraphdet-w13n32.sh", "run-q38-a179-host-controlled.sh")
    for name, text in zip(out_names, (launcher, client, supervisor, host)): emit(name, text)
    for name in out_names: print(digest((ROOT / name).read_bytes()), name)
if __name__ == "__main__":
    main()
