# R212b: fine determinism map of _xpu_C.int4_gemm_w4a16 over M=1..1024 (every M to 64, then steps) on an idle GPU, plus idle timings.
import json,sys,time,hashlib,torch
from safetensors.torch import load_file
import vllm_xpu_kernels._xpu_C  # noqa
MODEL="/model"; dev=torch.device("xpu:0"); torch.manual_seed(0); idx=json.load(open(f"{MODEL}/model.safetensors.index.json"))["weight_map"]
h=lambda t: hashlib.sha256(t.contiguous().cpu().numpy().tobytes()).hexdigest()[:12]
MS=list(range(1,65))+[72,80,96,112,120,128,136,144,160,192,224,240,255,256,257,272,288,320,384,448,480,511,512,513,576,640,768,896,1000,1023,1024]
res={}
for name in ("model.language_model.layers.1.mlp.down_proj","model.language_model.layers.1.mlp.gate_proj","model.language_model.layers.3.self_attn.q_proj","model.language_model.layers.1.linear_attn.out_proj","model.language_model.layers.1.mlp.up_proj","model.language_model.layers.3.self_attn.o_proj"):
    sh=load_file(f"{MODEL}/{idx[name+'.qweight']}"); qw=sh[name+".qweight"].to(dev); sc=sh[name+".scales"].to(dev); K=qw.shape[0]*8; N=qw.shape[1]
    w_q=qw.t().contiguous(); w_s=sc.contiguous(); w_zp=torch.Tensor([8]).to(torch.int8).to(dev)
    f=lambda x: torch.ops._xpu_C.int4_gemm_w4a16(x, w_q.t(), None, w_s, w_zp, 128, None)
    x=torch.randn(1024,K,device=dev,dtype=torch.float16)*0.5; e={}; bad=[]; var=[]
    with torch.no_grad():
        ref1=f(x[:1].contiguous())
        for M in MS:
            xm=x[:M].contiguous(); hs={h(f(xm)) for _ in range(4)}; a=f(xm)
            r2r=len(hs)==1; inv=h(a[0])==h(ref1[0])
            if not r2r: bad.append(M)
            if not inv: var.append(M)
            if M in (1,2,4,5,8,16,32,64,128,256,512,1024):
                for _ in range(5): f(xm)
                torch.xpu.synchronize(); t=time.perf_counter()
                for _ in range(40): f(xm)
                torch.xpu.synchronize(); e[M]=round((time.perf_counter()-t)/40*1e6,1)
    res[name]={"K":K,"N":N,"nondeterministic_M":bad,"row0_differs_from_m1_M":var,"us":e}
    print(name.split(".")[-1],f"K={K} N={N}","nondet:",bad,"| first row-variant M:",var[:3],"...","| us:",e,flush=True)
json.dump(res,open(sys.argv[1],"w"),indent=1)
