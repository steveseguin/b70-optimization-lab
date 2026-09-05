#!/usr/bin/env python3
"""R210: ARK W4A16 (auto_round_kernel woqgemm) determinism census on real AutoRound INT4 layers.
Run-to-run bit-identity (same inputs, N repeats) and row-invariance (row 0 at batch M vs M=1) per M-class."""
import json, struct, sys, os, torch
from safetensors.torch import load_file
from auto_round_kernel.qlinear import QuantLinearGPTQ
MODEL = "/model"; OUT = sys.argv[1] if len(sys.argv) > 1 else "/out/census.json"
REPEATS = int(os.environ.get("REPEATS", "12")); MS = [1, 2, 3, 4, 5, 8, 12, 16, 32, 48, 64, 128, 256, 512]
dev = torch.device("xpu:0"); torch.manual_seed(0)
def find_shard(name):
    idx = json.load(open(f"{MODEL}/model.safetensors.index.json"))["weight_map"]; return f"{MODEL}/{idx[name]}"
layers = [("model.language_model.layers.1.mlp.down_proj", 17408, 5120), ("model.language_model.layers.1.mlp.gate_proj", 5120, 17408),
          ("model.language_model.layers.3.self_attn.qkv_proj", 5120, None), ("model.language_model.layers.1.linear_attn.out_proj", None, 5120)]
res = {"kind": "ark-woqgemm-census", "repeats": REPEATS, "layers": {}}
for name, K, N in layers:
    try:
        sh = load_file(find_shard(name + ".qweight")); qw = sh[name + ".qweight"]; qz = sh[name + ".qzeros"]; sc = sh[name + ".scales"]
    except Exception as e:
        # try the merged names in the checkpoint
        try:
            alt = name.replace("qkv_proj", "q_proj"); sh = load_file(find_shard(alt + ".qweight")); qw = sh[alt + ".qweight"]; qz = sh[alt + ".qzeros"]; sc = sh[alt + ".scales"]; name = alt
        except Exception as e2:
            res["layers"][name] = {"error": repr(e2)}; print(name, "skip:", repr(e2)[:120], flush=True); continue
    K = qw.shape[0] * 8; N = qw.shape[1]
    lin = QuantLinearGPTQ(4, 128, True, K, N, False, weight_dtype=torch.float16)
    lin.qweight = qw.to(dev); lin.qzeros = qz.to(dev); lin.scales = sc.to(dev); lin.bias = None
    # the post-load repack: find the method ARK uses (post_init) and call it
    for m in ("post_init", "prepare", "repack"):
        if hasattr(lin, m): getattr(lin, m)(); break
    lin = lin.to(dev)
    entry = {"K": K, "N": N, "run_to_run": {}, "row_invariance_vs_m1": {}}
    x_full = (torch.randn(max(MS), K, device=dev, dtype=torch.float16) * 0.5)
    ref1 = None
    for M in MS:
        x = x_full[:M].contiguous(); outs = []
        with torch.no_grad():
            for _ in range(REPEATS):
                y = lin(x); torch.xpu.synchronize(); outs.append(y.clone())
        same = all(torch.equal(outs[0], o) for o in outs[1:])
        ndiff = 0 if same else max(int((outs[0] != o).sum()) for o in outs[1:])
        entry["run_to_run"][M] = {"bit_identical": same, "max_differing_elements": ndiff}
        if M == 1: ref1 = outs[0][0].clone()
        else: entry["row_invariance_vs_m1"][M] = bool(torch.equal(outs[0][0], ref1))
        print(f"{name.split('.')[-2]}.{name.split('.')[-1]} K={K} N={N} M={M:3d}: run-to-run {'identical' if same else 'DIFFERS('+str(ndiff)+' elems)'}; row0==M1 {entry['row_invariance_vs_m1'].get(M,'-')}", flush=True)
    res["layers"][name] = entry
json.dump(res, open(OUT, "w"), indent=1); print("census written", OUT)
