import json,sys,time,torch
from safetensors.torch import load_file
from auto_round_kernel.qlinear import QuantLinearGPTQ
MODEL="/model"; dev=torch.device("xpu:0"); torch.manual_seed(0); idx=json.load(open(f"{MODEL}/model.safetensors.index.json"))["weight_map"]
res={}
for name in ("model.language_model.layers.1.mlp.down_proj","model.language_model.layers.1.mlp.gate_proj","model.language_model.layers.3.self_attn.q_proj","model.language_model.layers.1.linear_attn.out_proj"):
    sh=load_file(f"{MODEL}/{idx[name+'.qweight']}"); qw=sh[name+".qweight"]; K=qw.shape[0]*8; N=qw.shape[1]
    lin=QuantLinearGPTQ(4,128,True,K,N,False,weight_dtype=torch.float16); lin.qweight=qw.to(dev); lin.qzeros=sh[name+".qzeros"].to(dev); lin.scales=sh[name+".scales"].to(dev); lin.bias=None
    for m in ("post_init","prepare","repack"):
        if hasattr(lin,m): getattr(lin,m)(); break
    lin=lin.to(dev); x=torch.randn(32,K,device=dev,dtype=torch.float16)*0.5; e={}
    with torch.no_grad():
        for M in (1,2,3,4,5,6,7,8,12,16,24,32):
            xm=x[:M].contiguous()
            for _ in range(5): lin(xm)
            torch.xpu.synchronize(); t=time.perf_counter()
            for _ in range(30): lin(xm)
            torch.xpu.synchronize(); e[M]=round((time.perf_counter()-t)/30*1e6,1)
    res[name]=e; print(name.split(".")[-1], e, flush=True)
json.dump(res,open(sys.argv[1],"w"),indent=1)
