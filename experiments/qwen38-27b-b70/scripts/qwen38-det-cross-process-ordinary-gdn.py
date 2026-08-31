#!/usr/bin/env python3
"""Cross-process Qwen3.8 ordinary native-GDN prefill/decode state screen."""

import argparse
import hashlib
import json
from pathlib import Path

import torch
import vllm_xpu_kernels._xpu_C  # noqa: F401


M_VALUES = (48, 49, 52, 53, 55, 56, 57, 59, 65, 71, 75, 78)
NK, NV, DK, DV, WIDTH, TP = 16, 48, 128, 128, 4, 1
LOCAL_K, LOCAL_V = NK // TP, NV // TP
QKVZ = LOCAL_K * (2 * DK + 2 * DV * NV // NK)
BA = 2 * LOCAL_V
CONV = LOCAL_K * (2 * DK + DV * NV // NK)
DECODE_STEPS = 32
SEED = 20260831


def cpu_randn(shape, dtype, seed):
    generator = torch.Generator(device="cpu"); generator.manual_seed(seed)
    return torch.randn(shape, dtype=dtype, generator=generator)


def update_digest(digest, *values):
    for value in values:
        digest.update(value.cpu().contiguous().numpy().tobytes())


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    torch.set_num_threads(1); device=torch.device("xpu:0"); f16=torch.float16
    conv_weights=cpu_randn((CONV,WIDTH),f16,SEED+1).to(device)
    conv_bias=cpu_randn((CONV,),f16,SEED+2).to(device)
    a_log=cpu_randn((LOCAL_V,),torch.float32,SEED+3).to(device)
    dt_bias=cpu_randn((LOCAL_V,),f16,SEED+4).to(device)
    state_index=torch.tensor([1],dtype=torch.int32,device=device)
    prefill_initial=torch.tensor([False],dtype=torch.bool,device=device)
    decode_initial=torch.tensor([True],dtype=torch.bool,device=device)
    decode_query=torch.tensor([0,1],dtype=torch.int32,device=device)
    rows=[]

    for m in M_VALUES:
        pre_qkvz=cpu_randn((m,QKVZ),f16,SEED+100+m).to(device)
        pre_ba=cpu_randn((m,BA),f16,SEED+200+m).to(device)
        dec_qkvz=cpu_randn((DECODE_STEPS,QKVZ),f16,SEED+300+m).to(device)
        dec_ba=cpu_randn((DECODE_STEPS,BA),f16,SEED+400+m).to(device)
        pre_query=torch.tensor([0,m],dtype=torch.int32,device=device)

        def chain():
            conv_state=torch.zeros((2,WIDTH-1,CONV),dtype=f16,device=device)
            ssm_state=torch.zeros((2,LOCAL_V,DV,DK),dtype=torch.float32,device=device)
            core=torch.empty((m,LOCAL_V,DV),dtype=f16,device=device)
            z=torch.empty_like(core)
            torch.ops._xpu_C.gdn_attention(core,z,pre_qkvz,pre_ba,NK,NV,DK,DV,
                conv_state,ssm_state,conv_weights,conv_bias,"silu",a_log,dt_bias,
                1,0,0,prefill_initial,pre_query,None,state_index,None,None,None,None,m,TP,True)
            torch.xpu.synchronize()
            pre_hash=hashlib.sha256(); update_digest(pre_hash,core,z,conv_state,ssm_state)
            dec_hash=hashlib.sha256()
            for step in range(DECODE_STEPS):
                dcore=torch.empty((1,LOCAL_V,DV),dtype=f16,device=device)
                dz=torch.empty_like(dcore)
                torch.ops._xpu_C.gdn_attention(dcore,dz,dec_qkvz[step:step+1],dec_ba[step:step+1],
                    NK,NV,DK,DV,conv_state,ssm_state,conv_weights,conv_bias,"silu",a_log,dt_bias,
                    0,1,0,decode_initial,decode_query,None,state_index,None,None,None,None,1,TP,True)
                torch.xpu.synchronize(); update_digest(dec_hash,dcore,dz)
            update_digest(dec_hash,conv_state,ssm_state)
            return pre_hash.hexdigest(),dec_hash.hexdigest()

        first=chain(); second=chain()
        rows.append({"m":m,"prefill_sha256":first[0],"decode_trajectory_sha256":first[1],
                     "within_process_prefill_exact":first[0]==second[0],
                     "within_process_decode_exact":first[1]==second[1]})
        del pre_qkvz,pre_ba,dec_qkvz,dec_ba
        torch.xpu.empty_cache()
    args.out.write_text(json.dumps({"seed":SEED,"decode_steps":DECODE_STEPS,"rows":rows},sort_keys=True)+"\n")


if __name__ == "__main__": main()
