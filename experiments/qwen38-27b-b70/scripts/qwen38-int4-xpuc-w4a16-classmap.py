# R217 census: row-class map of _xpu_C.int4_gemm_w4a16. For each M, is row 0 bit-identical to row 0 of the same input
# padded (zeros) to 16 / 64 / 512 rows, and to the M=1 call? Also: with a fixed pad class P, does row 0 depend on the
# CONTENT of the other rows (random vs zeros)? Answers whether "pad every call to P" gives full batch invariance.
import json,sys,hashlib,torch
from safetensors.torch import load_file
import vllm_xpu_kernels._xpu_C  # noqa
MODEL="/model"; dev=torch.device("xpu:0"); torch.manual_seed(0); idx=json.load(open(f"{MODEL}/model.safetensors.index.json"))["weight_map"]
h=lambda t: hashlib.sha256(t.contiguous().cpu().numpy().tobytes()).hexdigest()[:12]
MS=[1,2,4,5,8,9,10,12,16,17,24,32,33,48,64,65,96,128,129,192,256,257,384,512,513,768,1024]
res={}
for name in ("model.language_model.layers.1.mlp.down_proj","model.language_model.layers.1.mlp.gate_proj","model.language_model.layers.3.self_attn.q_proj","model.language_model.layers.1.linear_attn.out_proj"):
    sh=load_file(f"{MODEL}/{idx[name+'.qweight']}"); qw=sh[name+".qweight"].to(dev); sc=sh[name+".scales"].to(dev); K=qw.shape[0]*8; N=qw.shape[1]
    w_q=qw.t().contiguous(); w_s=sc.contiguous(); w_zp=torch.Tensor([8]).to(torch.int8).to(dev)
    f=lambda x: torch.ops._xpu_C.int4_gemm_w4a16(x, w_q.t(), None, w_s, w_zp, 128, None)
    x=torch.randn(1024,K,device=dev,dtype=torch.float16)*0.5
    def padded(M,P):
        xp=torch.zeros(P,K,device=dev,dtype=torch.float16); xp[:M]=x[:M]; return f(xp)
    with torch.no_grad():
        ref={P:h(padded(1,P)[0]) for P in (1,16,64,512)}
        # content dependence: row0 with rows 1..P-1 random vs zeros, for P in 16, 64, 512
        content={P: h(f(x[:P].contiguous())[0])==ref[P] for P in (16,64,512)}
        rows={}
        for M in MS:
            r0=h(f(x[:M].contiguous())[0])
            rows[M]={"eq_m1":r0==ref[1],"eq_pad16":r0==ref[16],"eq_pad64":r0==ref[64],"eq_pad512":r0==ref[512]}
    classes={}
    for M,v in rows.items():
        key=tuple(k for k,b in v.items() if b) or ("own",); classes.setdefault(key,[]).append(M)
    res[name]={"K":K,"N":N,"row0_independent_of_other_rows_content_at_P":content,"classes":{" & ".join(k):v for k,v in classes.items()}}
    print(name.split(".")[-1], "content-independent@P:", content, "| classes:", res[name]["classes"], flush=True)
json.dump(res,open(sys.argv[1],"w"),indent=1)
