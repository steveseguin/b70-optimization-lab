import torch, json, sys
from vllm import ir
DEV=torch.device("xpu:0"); DT=torch.float16; H=5120
out={}
for seed in (3,11,20260902):
    torch.manual_seed(seed)
    big=torch.randn((2048,H),dtype=DT,device=DEV)*2; rbig=torch.randn((2048,H),dtype=DT,device=DEV); w=torch.randn(H,dtype=torch.float32,device=DEV)*0.1+1.0
    def plain(t): return ir.ops.rms_norm(t,w,1e-6).clone()
    def fused(t,rr): o,_=ir.ops.fused_add_rms_norm(t,rr,w,1e-6); return o.clone()
    sp=torch.cat([plain(big[i:i+1].clone()) for i in range(256)]); sf=torch.cat([fused(big[i:i+1].clone(),rbig[i:i+1].clone()) for i in range(256)])
    Ms=list(range(1,65))+[96,128,256]
    def first_fail(fn):
        return next((M for M in Ms if not fn(M)),None)
    r={}
    r["plain_clone_first_ne"]=first_fail(lambda M: torch.equal(plain(big[:M].clone()),sp[:M]))
    r["fused_clone_first_ne"]=first_fail(lambda M: torch.equal(fused(big[:M].clone(),rbig[:M].clone()),sf[:M]))
    r["plain_view2048_first_ne"]=first_fail(lambda M: torch.equal(plain(big[:M]),sp[:M]))
    r["fused_view2048_first_ne"]=first_fail(lambda M: torch.equal(fused(big[:M],rbig[:M].clone()),sf[:M]))
    v512=big[:512].clone(); rv512=rbig[:512].clone()
    r["plain_view512_first_ne"]=first_fail(lambda M: torch.equal(plain(v512[:M]),sp[:M]))
    # row-0 class map for clones (plain)
    classes={}
    for M in Ms:
        k=plain(big[:M].clone())[0].cpu().numpy().tobytes(); classes.setdefault(k,[]).append(M)
    r["plain_clone_row0_classes"]=[c if len(c)<6 else [c[0],'..',c[-1],len(c)] for c in sorted(classes.values(),key=lambda v:v[0])]
    classes={}
    for M in Ms:
        k=fused(big[:M].clone(),rbig[:M].clone())[0].cpu().numpy().tobytes(); classes.setdefault(k,[]).append(M)
    r["fused_clone_row0_classes"]=[c if len(c)<6 else [c[0],'..',c[-1],len(c)] for c in sorted(classes.values(),key=lambda v:v[0])]
    # within-class permutation & chunked-clone reproduction
    for C in (8,15):
        r[f"plain_chunk{C}_clone_all_M"]=all(torch.equal(torch.cat([plain(big[i:i+C].clone()) for i in range(0,M,C)]),sp[:M]) for M in Ms)
        r[f"fused_chunk{C}_clone_all_M"]=all(torch.equal(torch.cat([fused(big[i:i+C].clone(),rbig[i:i+C].clone()) for i in range(0,M,C)]),sf[:M]) for M in Ms)
    perm=torch.randperm(15,device=DEV); r["plain_perm15_clone"]=bool(torch.equal(plain(big[:15][perm].clone()),sp[:15][perm])); r["fused_perm15_clone"]=bool(torch.equal(fused(big[:15][perm].clone(),rbig[:15][perm].clone()),sf[:15][perm]))
    out[f"seed{seed}"]=r; print(seed,r,flush=True)
json.dump(out,open(sys.argv[1],"w"),indent=1)
