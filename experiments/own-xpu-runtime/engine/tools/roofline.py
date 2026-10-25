#!/usr/bin/env python3
"""Per-site roofline for an OWNRT_DECODE_PROFILE=2 device profile.

roofline.py PROFILE.jsonl --layers 0-23 [--placement placement.tsv] [--peak 537] [--top 40] [--compare OLD.jsonl]

Matrix sites (gemv:/routed_gemv:<grid>:<role>) get their weight bytes from the placement table (routed experts at
10/512 of the tensor), the achieved GB/s and the time lost against the bandwidth peak. Non-matrix sites are listed
by busy time. Only non-speculative, non-cancelled steps are used. --compare prints the per-site delta to OLD.
"""
import argparse, collections, json, re
ROLE = {"gdn.qkv": "attn_qkv.weight", "gdn.z": "attn_gate.weight", "attention": "ssm_out.weight|attn_output.weight",
        "hc.a.low": "hc_attn_down.weight", "hc.a.gate": "hc_attn_up.weight", "hc.f.low": "hc_ffn_down.weight",
        "hc.f.gate": "hc_ffn_up.weight", "router": "ffn_gate_inp.weight", "shexpgate": "ffn_gate_shexp.weight",
        "shexpup": "ffn_up_shexp.weight", "shexpdown": "ffn_down_shexp.weight", "gdn.a": "ssm_alpha.weight|ssm_beta.weight",
        "qsa.qgate": "attn_q.weight", "qsa.k": "attn_k.weight", "qsa.v": "attn_v.weight",
        "qsa.iq": "indexer.q_proj.weight|indexer.k_proj.weight", "expsgate": "ffn_gate_exps.weight",
        "expsup": "ffn_up_exps.weight", "expsdown": "ffn_down_exps.weight"}
GT = {0: "F32", 8: "Q8_0", 12: "Q4_K", 13: "Q5_K", 14: "Q6_K", 18: "IQ3_XXS", 20: "IQ4_NL", 21: "IQ3_S", 22: "IQ2_S",
      23: "IQ4_XS", 30: "BF16", 42: "Q2_0"}
def load(path):
    rows = [json.loads(l) for l in open(path)]
    rows = [r for r in rows if not r.get("speculative") and not r.get("cancelled")]
    agg = collections.Counter()
    for r in rows:
        for k, v in r["sites"].items(): agg[k] += v["busy_us"] / len(rows)
    return agg, len(rows), sum(r["span_us"] for r in rows) / len(rows)
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("profile"); ap.add_argument("--layers", required=True)
    ap.add_argument("--placement", default="/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/loader/placement.tsv")
    ap.add_argument("--peak", type=float, default=537.0); ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--compare")
    a = ap.parse_args()
    lo, hi = map(int, a.layers.split("-"))
    by = collections.Counter()
    for line in open(a.placement):
        f = line.rstrip("\n").split("\t")
        if len(f) < 6: f = line.split()
        m = re.match(r"blk\.(\d+)\.(.*)", f[1])
        if not m or not lo <= int(m.group(1)) <= hi: continue
        for role, pat in ROLE.items():
            if re.fullmatch(pat, m.group(2)):
                nb = int(f[5]); by[(role, GT.get(int(f[3]), f[3]))] += nb * 10 / 512 if "exps" in m.group(2) else nb
    agg, n, span = load(a.profile)
    old = load(a.compare)[0] if a.compare else None
    total = sum(agg.values()); rows = []
    for key, us in agg.items():
        p = key.split(":"); b = by.get((p[2], p[1]), 0) if len(p) == 3 else 0
        rows.append((us, key, b))
    mb = sum(r[2] for r in rows) / 1e6; mat = sum(r[0] for r in rows if r[2])
    print(f"{n} steps, span {span:.0f} us, busy {total:.0f} us; matrix {mat:.0f} us for {mb:.1f} MB "
          f"(peak {mb / a.peak * 1e3:.0f} us), other {total - mat:.0f} us")
    for us, key, b in sorted(rows, reverse=True)[:a.top]:
        extra = f" {b / us / 1e3:6.0f} GB/s lost {us - b / a.peak / 1e3:6.0f}" if b and us else ""
        delta = f"  delta {us - old.get(key, 0):+7.0f}" if old is not None else ""
        print(f"  {key:34s} {us:7.0f} us{extra}{delta}")
main()
