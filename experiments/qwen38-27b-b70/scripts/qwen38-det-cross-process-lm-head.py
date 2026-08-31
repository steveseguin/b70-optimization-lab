#!/usr/bin/env python3
"""Hash the actual Qwen3.8 LM-head M=1 output across fresh processes."""

import argparse
import hashlib
import json
from pathlib import Path

import torch
import torch.nn.functional as F
from safetensors import safe_open


SEED = 20260831
REPEATS = 16
WEIGHT_FILE = Path("/model/model-00007-of-00007.safetensors")
WEIGHT_KEY = "lm_head.weight"


def digest(value: torch.Tensor) -> str:
    return hashlib.sha256(value.cpu().contiguous().numpy().tobytes()).hexdigest()


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args(); torch.set_num_threads(1)
    with safe_open(WEIGHT_FILE,framework="pt",device="cpu") as handle:
        weight_cpu=handle.get_tensor(WEIGHT_KEY)
    checkpoint_dtype=str(weight_cpu.dtype); checkpoint_shape=list(weight_cpu.shape)
    weight=weight_cpu.to(device="xpu:0",dtype=torch.float16); del weight_cpu
    generator=torch.Generator(device="cpu"); generator.manual_seed(SEED)
    hidden=torch.randn(1,weight.shape[1],dtype=torch.float16,generator=generator).to("xpu:0")
    hashes=[]; top=[]
    for _ in range(REPEATS):
        logits=F.linear(hidden,weight); torch.xpu.synchronize()
        logits=logits.clone(); hashes.append(digest(logits))
        values,indices=torch.topk(logits.float(),k=2,dim=-1)
        top.append({"indices":indices.cpu().tolist()[0],"values":values.cpu().tolist()[0]})
    payload={"seed":SEED,"repeats":REPEATS,"checkpoint_dtype":checkpoint_dtype,
      "checkpoint_shape":checkpoint_shape,"runtime_dtype":str(weight.dtype),
      "unique_logit_hashes":sorted(set(hashes)),"top2":top,
      "top1_unique":sorted({row["indices"][0] for row in top})}
    args.out.write_text(json.dumps(payload,sort_keys=True)+"\n")


if __name__ == "__main__": main()
