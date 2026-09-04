#!/usr/bin/env python3
"""R199: aggregate a vLLM torch-profiler trace (Chrome JSON, possibly .gz) into device-kernel time by kernel family and
by rank, over the profiled window. Prints the top kernels, the family split (GEMM / GDN / attention / allreduce /
norm-elementwise / other), and the per-step estimate (kernel time / number of decode steps = completion tokens)."""
import gzip, json, sys, glob, re, collections, os
root = sys.argv[1]; steps = int(sys.argv[2]) if len(sys.argv) > 2 else 0
files = sorted(glob.glob(os.path.join(root, "profile", "*.json*")))
if not files: print("no trace files"); sys.exit(1)
fam = [("allreduce", re.compile(r"allreduce|all_reduce|ccl|xccl|oneccl", re.I)), ("gemm", re.compile(r"gemm|matmul|mm_|xetla|dnnl|onednn|brgemm|conv", re.I)),
       ("gdn", re.compile(r"gdn|gated_delta|chunk_|recurrent|fused_recurrent|causal_conv|conv1d", re.I)), ("attention", re.compile(r"attn|attention|flash|paged|kv_cache|reshape_and_cache", re.I)),
       ("norm_elementwise", re.compile(r"norm|rms|triton_|elementwise|silu|gelu|rotary|rope|copy|fill|cat|index", re.I))]
for f in files:
    op = gzip.open if f.endswith(".gz") else open
    with op(f, "rt") as fh: d = json.load(fh)
    ev = d["traceEvents"] if isinstance(d, dict) else d
    kern = [e for e in ev if e.get("ph") == "X" and e.get("cat", "").lower() in ("kernel", "gpu_memcpy", "gpu_memset", "xpu_runtime", "sycl_kernel") or (e.get("ph") == "X" and "pid" in e and str(e.get("args", {}).get("stream", "")) and e.get("cat", "") == "kernel")]
    if not kern:
        cats = collections.Counter(e.get("cat", "") for e in ev if e.get("ph") == "X"); print(os.path.basename(f), "no kernel events; cats:", cats.most_common(8)); continue
    byname = collections.Counter(); byfam = collections.Counter(); total = 0.0
    for e in kern:
        dur = float(e.get("dur", 0)); n = e.get("name", "?"); total += dur; byname[n] += dur
        for name, rx in fam:
            if rx.search(n): byfam[name] += dur; break
        else: byfam["other"] += dur
    print(f"== {os.path.basename(f)}: {len(kern)} kernel events, {total/1000:.1f} ms device time" + (f", {total/1000/steps:.2f} ms/step over {steps} steps" if steps else ""))
    for k, v in byfam.most_common(): print(f"   {k:16s} {v/1000:8.1f} ms  {100*v/total:5.1f}%")
    print("   top kernels:")
    for n, v in byname.most_common(12): print(f"     {v/1000:8.1f} ms  {100*v/total:5.1f}%  {n[:110]}")
