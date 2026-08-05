import os, time, torch, torch.distributed as dist
try: import oneccl_bindings_for_pytorch  # noqa
except Exception: pass
LAYERS, M, HIDDEN, INTER, TOPK = 48, 12, 3072, 1024, 10
rank=int(os.environ.get("RANK","0")); world=int(os.environ.get("WORLD_SIZE","1"))
local=int(os.environ.get("LOCAL_RANK",str(rank)))
torch.xpu.set_device(local); dist.init_process_group(backend="xccl", rank=rank, world_size=world)
dev=f"xpu:{local}"; bf=torch.bfloat16
x=torch.randn(M,HIDDEN,dtype=bf,device=dev); qkv=torch.randn(HIDDEN,HIDDEN,dtype=bf,device=dev)
w13=torch.randn(HIDDEN,2*INTER,dtype=bf,device=dev); w2=torch.randn(INTER,HIDDEN,dtype=bf,device=dev)
disp=torch.randn(M*TOPK,HIDDEN,dtype=bf,device=dev)
gath=torch.empty(M*TOPK*world,HIDDEN,dtype=bf,device=dev); red=torch.empty_like(x)

def step(every):
    h=x
    for i in range(LAYERS):
        h=h@qkv; a=h@w13
        a=torch.nn.functional.silu(a[:,:INTER])*a[:,INTER:]; h=a@w2
        if every and (i % every)==0:
            dist.all_gather_into_tensor(gath,disp); dist.all_reduce(red)

for every,label in ((1,"every layer (96 calls)"),(2,"every 2 layers (48)"),(4,"every 4 layers (24)"),(8,"every 8 layers (12)"),(0,"none (0)")):
    for _ in range(5): step(every)
    torch.xpu.synchronize(); dist.barrier()
    t0=time.perf_counter()
    for _ in range(20): step(every)
    torch.xpu.synchronize()
    dt=(time.perf_counter()-t0)/20
    if rank==0:
        calls = 0 if every==0 else 2*((LAYERS+every-1)//every)
        print(f"  {label:26s} calls={calls:3d}  step={dt*1e3:7.2f} ms   ceiling@1.08tok={1.08/dt:6.1f}  @3.66tok={3.66/dt:7.1f}")
dist.destroy_process_group()
