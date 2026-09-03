import torch, json, sys, time, inspect
from vllm import ir
from vllm.third_party.flash_linear_attention.ops.layernorm_guard import rmsnorm_fn
print("rmsnorm_fn sig:", inspect.signature(rmsnorm_fn))
DEV=torch.device("xpu:0"); DT=torch.float16
def census(name, fn, M_list, H, seeds=(3,11,20260902)):
    res={}
    for seed in seeds:
        torch.manual_seed(seed)
        x=torch.randn((512,H),dtype=DT,device=DEV)*2; r=torch.randn((512,H),dtype=DT,device=DEV)
        single=torch.cat([fn(x[i:i+1].clone(),r[i:i+1].clone()) for i in range(256)])
        ff=next((M for M in M_list if not torch.equal(fn(x[:M].clone(),r[:M].clone()),single[:M])),None)
        perm=torch.randperm(256,device=DEV); pe=bool(torch.equal(fn(x[:256][perm].clone(),r[:256][perm].clone()),single[perm]))
        rep=bool(torch.equal(fn(x[:256].clone(),r[:256].clone()),fn(x[:256].clone(),r[:256].clone())))
        res[f"seed{seed}"]={"first_M_ne_single":ff,"perm256_equal":pe,"repeat":rep}
    print(name,res,flush=True); return res
H=5120; torch.manual_seed(0); w=torch.randn(H,dtype=torch.float32,device=DEV)*0.1+1.0; wh=w.to(DT)
Ms=list(range(1,65))+[96,128,256]
out={}
out["triton_plain_5120_fp16w"]=census("triton plain", lambda x,r: rmsnorm_fn(x, wh, None, z=None, eps=1e-6), Ms, H)
out["triton_addnorm_5120"]=census("triton add+norm", lambda x,r: rmsnorm_fn(x+r, wh, None, z=None, eps=1e-6), Ms, H)
out["ir_plain_5120_for_reference"]=census("ir plain (known bad)", lambda x,r: ir.ops.rms_norm(x,w,1e-6), Ms, H)
wq=torch.randn(256,dtype=DT,device=DEV)*0.1+1.0
out["triton_head_256"]=census("triton head 256", lambda x,r: rmsnorm_fn(x, wq, None, z=None, eps=1e-6), Ms, 256)
# timing
torch.manual_seed(1); x=torch.randn((128,H),dtype=DT,device=DEV); r=torch.randn((128,H),dtype=DT,device=DEV)
def t(fn,n=300):
    for _ in range(30): fn()
    torch.xpu.synchronize(); t0=time.perf_counter()
    for _ in range(n): fn()
    torch.xpu.synchronize(); return (time.perf_counter()-t0)/n*1e6
tim={}
for M in (1,2,16,64,128):
    tim[f"M{M}_ir_fused"]=t(lambda: ir.ops.fused_add_rms_norm(x[:M].clone(),r[:M].clone(),w,1e-6))
    tim[f"M{M}_triton_add_norm"]=t(lambda: rmsnorm_fn(x[:M]+r[:M], wh, None, z=None, eps=1e-6))
    tim[f"M{M}_ir_plain"]=t(lambda: ir.ops.rms_norm(x[:M],w,1e-6))
    tim[f"M{M}_triton_plain"]=t(lambda: rmsnorm_fn(x[:M], wh, None, z=None, eps=1e-6))
print({k:round(v,1) for k,v in tim.items()})
json.dump({"census":out,"timing_us":tim},open(sys.argv[1],"w"),indent=1)
