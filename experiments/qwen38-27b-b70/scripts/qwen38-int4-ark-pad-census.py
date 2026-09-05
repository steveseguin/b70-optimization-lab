#!/usr/bin/env python3
"""R210b: does padding rows to a fixed class make ARK woqgemm row-invariant and deterministic, and what does it cost?
For each layer: (1) M=1024 run-to-run; (2) row0 of x[:1] padded to 16 vs x[:6] padded to 16 vs x[:16]: identical?;
(3) prefill band: x[:60] padded to 512 run-to-run x12 and vs x[:512] row0; (4) timing M=1 vs M=16 (padded) and M=60 vs 512."""
import json, sys, os, time, torch
from safetensors.torch import load_file
from auto_round_kernel.qlinear import QuantLinearGPTQ
MODEL="/model"; OUT=sys.argv[1]; dev=torch.device("xpu:0"); torch.manual_seed(0)
idx=json.load(open(f"{MODEL}/model.safetensors.index.json"))["weight_map"]
def load(name):
    sh=load_file(f"{MODEL}/{idx[name+'.qweight']}"); return sh[name+".qweight"],sh[name+".qzeros"],sh[name+".scales"]
def build(name):
    qw,qz,sc=load(name); K=qw.shape[0]*8; N=qw.shape[1]; lin=QuantLinearGPTQ(4,128,True,K,N,False,weight_dtype=torch.float16)
    lin.qweight=qw.to(dev); lin.qzeros=qz.to(dev); lin.scales=sc.to(dev); lin.bias=None
    for m in ("post_init","prepare","repack"):
        if hasattr(lin,m): getattr(lin,m)(); break
    return lin.to(dev),K,N
def pad(x,M): return torch.cat([x, torch.zeros(M-x.shape[0], x.shape[1], device=x.device, dtype=x.dtype)]) if x.shape[0]<M else x
def timeit(lin,x,n=30):
    with torch.no_grad():
        for _ in range(5): lin(x)
        torch.xpu.synchronize(); t=time.perf_counter()
        for _ in range(n): lin(x)
        torch.xpu.synchronize(); return (time.perf_counter()-t)/n*1e6
res={}
for name in ("model.language_model.layers.1.mlp.down_proj","model.language_model.layers.1.mlp.gate_proj","model.language_model.layers.3.self_attn.q_proj","model.language_model.layers.1.linear_attn.out_proj"):
    lin,K,N=build(name); x=(torch.randn(1024,K,device=dev,dtype=torch.float16)*0.5); e={"K":K,"N":N}
    with torch.no_grad():
        o=[lin(x).clone() for _ in range(6)]; e["m1024_run_to_run_identical"]=all(torch.equal(o[0],y) for y in o[1:])
        a=lin(pad(x[:1],16))[0]; b=lin(pad(x[:6],16))[0]; c=lin(x[:16])[0]; d=lin(x[:1])[0]
        e["pad16_row0_invariant_m1_m6_m16"]=bool(torch.equal(a,b) and torch.equal(b,c)); e["pad16_row0_equals_unpadded_m1"]=bool(torch.equal(a,d))
        p=[lin(pad(x[:60],512)).clone() for _ in range(12)]; e["pad512_from60_run_to_run_identical"]=all(torch.equal(p[0],y) for y in p[1:])
        e["pad512_row0_equals_m512_row0"]=bool(torch.equal(p[0][0], lin(x[:512])[0]))
        p2=[lin(pad(x[:60],256)).clone() for _ in range(12)]; e["pad256_from60_run_to_run_identical"]=all(torch.equal(p2[0],y) for y in p2[1:])
        e["us_m1"]=round(timeit(lin,x[:1]),1); e["us_m16"]=round(timeit(lin,x[:16]),1); e["us_m8"]=round(timeit(lin,x[:8]),1); e["us_m60"]=round(timeit(lin,x[:60]),1); e["us_m512"]=round(timeit(lin,x[:512]),1); e["us_m1024"]=round(timeit(lin,x[:1024],10),1)
    res[name]=e; print(name.split(".")[-2]+"."+name.split(".")[-1], json.dumps(e), flush=True)
json.dump(res,open(OUT,"w"),indent=1)
