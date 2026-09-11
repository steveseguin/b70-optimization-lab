# Run inside an R290/R291 image with VLLM_XPU_FP16_LINEAR_CLASSPAD=1 VLLM_TARGET_DEVICE=xpu on one card: the op on the TP1 shapes with bias, strided and 3-D inputs.
import torch, time, logging
logging.basicConfig(level=logging.INFO)
import vllm.model_executor.layers.utils as U
dev="xpu"; torch.manual_seed(2)
class L: pass
def check(N,K,label,bias=False,strided=False):
    W=(torch.randn(N,K,device=dev)*0.02).half(); b=(torch.randn(N,device=dev)*0.01).half() if bias else None
    big=torch.randn(600,K+64,device=dev).half()
    X=big[:, :K] if strided else big[:, :K].contiguous()
    f=lambda x: U.default_unquantized_gemm(L(), x, W, b)
    f(X[:1]); torch.xpu.synchronize()
    single=torch.cat([f(X[i:i+1]) for i in range(64)],0); torch.xpu.synchronize()
    bad=[]
    for M in [1,2,12,16,20,24,32,33,48,64,96,128,192,193,256,320,512,600]:
        o=f(X[:M]); torch.xpu.synchronize(); n=min(M,64)
        if not (torch.equal(o[:n],single[:n]) and torch.equal(o,f(X[:M]))): bad.append(M)
    # 3-D input as the model passes it ([M,1,K] or [1,M,K])
    o3=f(X[:24].unsqueeze(1)).reshape(24,-1); ok3=torch.equal(o3,single[:24])
    print(f"{label:34s} N={N:6d} K={K} bias={bias} strided={strided}: {'ALL OK' if not bad else 'FAIL at '+str(bad)}  3d_ok={ok3}")
for N,K,l in [(12288,2560,"per-layer B (TP1)"),(10240,2560,"per-layer A (TP1)"),(2560,4096,"out-proj-like (TP1)"),(248320,2560,"lm_head (TP1)")]:
    check(N,K,l); check(N,K,l,bias=True); check(N,K,l,strided=True)
