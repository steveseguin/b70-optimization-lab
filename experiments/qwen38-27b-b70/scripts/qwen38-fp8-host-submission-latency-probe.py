#!/usr/bin/env python3
"""Host submission-latency probe (cross-host comparison). One card:
(1) tiny-kernel launch rate: 2000 back-to-back 1-element adds, us per launch;
(2) sync latency: launch + synchronize, us; (3) a decode-shaped W8A16 GEMM
(M=2, K=5120, N=7168) wall per call. Run inside the R139 image on each host
and compare; a ~2x gap here explains a ~2x c1 gap."""
import time, json, sys, torch
import vllm_xpu_kernels._xpu_C  # noqa
dev=torch.device("xpu:0"); x=torch.ones(1,device=dev); y=torch.ones(1,device=dev)
def t(fn,n,sync_each=False):
    for _ in range(100): fn()
    torch.xpu.synchronize(); t0=time.perf_counter()
    for _ in range(n):
        fn()
        if sync_each: torch.xpu.synchronize()
    torch.xpu.synchronize(); return (time.perf_counter()-t0)/n*1e6
r={"device":torch.xpu.get_device_name(0),"torch":torch.__version__}
r["launch_us_async"]=t(lambda: torch.add(x,y,out=x),2000)
r["launch_plus_sync_us"]=t(lambda: torch.add(x,y,out=x),500,True)
a=torch.randn(2,5120,dtype=torch.float16,device=dev); w=(torch.randn(7168,5120,device=dev)*0.02).to(torch.float8_e4m3fn); s=torch.ones(7168//128,5120//128,dtype=torch.float32,device=dev)
try:
    r["w8a16_m2_qkv_us"]=t(lambda: torch.ops._xpu_C.fp8_gemm_w8a16(a,w.t(),s.t(),None),500)
except Exception as e: r["w8a16_m2_qkv_us"]=f"err {e}"[:80]
h=torch.randn(2,5120,dtype=torch.float16,device=dev); wt=torch.ones(5120,device=dev)
from vllm import ir
r["ir_rms_norm_m2_us"]=t(lambda: ir.ops.rms_norm(h,wt,1e-6),500)
print(json.dumps(r,indent=1))
if len(sys.argv)>1: open(sys.argv[1],"w").write(json.dumps(r,indent=1))
