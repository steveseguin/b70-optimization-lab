# R212 census: vllm-xpu-kernels _xpu_C.int4_gemm_w4a16 (the plain-GPTQ XPUwNa16 path) on the same four AutoRound layers as R210.
import json,sys,time,hashlib,torch
from safetensors.torch import load_file

import vllm_xpu_kernels._xpu_C  # noqa: registers torch.ops._xpu_C
MODEL="/model"; dev=torch.device("xpu:0"); torch.manual_seed(0); idx=json.load(open(f"{MODEL}/model.safetensors.index.json"))["weight_map"]
h=lambda t: hashlib.sha256(t.contiguous().cpu().numpy().tobytes()).hexdigest()[:12]
res={}
for name in ("model.language_model.layers.1.mlp.down_proj","model.language_model.layers.1.mlp.gate_proj","model.language_model.layers.3.self_attn.q_proj","model.language_model.layers.1.linear_attn.out_proj"):
    sh=load_file(f"{MODEL}/{idx[name+'.qweight']}"); qw=sh[name+".qweight"].to(dev); sc=sh[name+".scales"].to(dev); K=qw.shape[0]*8; N=qw.shape[1]
    # mimic XPUwNa16LinearKernel.process_weights_after_loading (gptq layout: qweight [K/8,N], scales [K/g,N] -> transpose qweight) and apply_weights (w_q.t())
    w_q=qw.t().contiguous(); w_s=sc.contiguous(); w_zp=torch.Tensor([8]).to(torch.int8).to(dev)
    f=lambda x: torch.ops._xpu_C.int4_gemm_w4a16(x, w_q.t(), None, w_s, w_zp, 128, None)
    x=torch.randn(1024,K,device=dev,dtype=torch.float16)*0.5; e={}
    with torch.no_grad():
        ref1=f(x[:1].contiguous())
        for M in (1,2,3,4,5,6,8,16,32,60,128,256,512,1024):
            xm=x[:M].contiguous(); a=f(xm); b=f(xm); c=f(xm)
            for _ in range(5): f(xm)
            torch.xpu.synchronize(); t=time.perf_counter()
            for _ in range(30): f(xm)
            torch.xpu.synchronize()
            e[M]={"run_to_run":h(a)==h(b)==h(c),"row0_eq_m1":h(a[0])==h(ref1[0]),"us":round((time.perf_counter()-t)/30*1e6,1)}
    res[name]=e; print(name.split(".")[-1], {m:(v["run_to_run"],v["row0_eq_m1"],v["us"]) for m,v in e.items()}, flush=True)
json.dump(res,open(sys.argv[1],"w"),indent=1)
