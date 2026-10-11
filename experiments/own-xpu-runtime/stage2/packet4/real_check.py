#!/usr/bin/env python3
"""Compare real layer0 to the oracle, or compute its packet1b-derived reference."""
import hashlib
import json
from pathlib import Path
import struct
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
ORACLE=ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle'
def compare(run,inputs,output,oracle=None,binary=None):
    ids=json.loads((inputs/'input.json').read_text())['tokens']
    fixture=oracle/'layer-00.bf16' if oracle else None
    if fixture and fixture.exists():
        assert json.loads((oracle.parent/'input.json').read_text())['tokens']==ids
        expected=fixture.read_bytes();authority=str(fixture.relative_to(ROOT))
    else:
        # Execute the packet1b-derived GGUF reference in this CPU process.
        # No server, subprocess model, device API or whole bank materialization.
        sys.path.insert(0,str(ORACLE))
        import oracle as reference
        import torch
        import time
        torch.set_num_threads(2);torch.set_num_interop_threads(1)
        store=reference.Store()
        try:
            model=reference.Model(store,lambda row:None,time.monotonic()+1800,'sigmoid')
            with torch.inference_mode():
                emb=torch.cat([store.rows('token_embd.weight',i,1) for i in ids]).to(torch.bfloat16)
                streams=emb[:,None,:].repeat(1,4,1)
                streams=reference.ref.layer(streams,lambda x:model.attention(0,x),lambda x:model.mlp(0,x),model.hc('blk.0.hc_attn_'),model.hc('blk.0.hc_ffn_'))
                expected=streams[-1:].contiguous().view(torch.uint8).numpy().tobytes()
            authority='in-process packet1b-derived reference_gguf + oracle.Model, real layer0 only'
        finally:store.close()
    actual=(run/'step1/layer-00.bf16').read_bytes()
    assert len(actual)==len(expected)==20480
    output.mkdir(parents=True,exist_ok=True)
    (output/'actual-layer-00.bf16').write_bytes(actual);(output/'oracle-layer-00.bf16').write_bytes(expected)
    a=struct.unpack('<10240H',actual);b=struct.unpack('<10240H',expected)
    mismatch=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
    receipt=dict(schema='own-runtime.iq3.packet4.real-layer.v1',passed=not mismatch,prompt='incident-retrospective',prompt_tokens=len(ids),layer=0,shape=[1,4,2560],dtype='BF16 little-endian',actual_sha256=hashlib.sha256(actual).hexdigest(),oracle_sha256=hashlib.sha256(expected).hexdigest(),different_bf16_values=len(mismatch),first_difference=mismatch[0] if mismatch else None,authority=authority,tolerance=None,device_executed=False,run=json.loads((run/'receipt.json').read_text()),input_sha256=hashlib.sha256((inputs/'tokens.txt').read_bytes()).hexdigest())
    if binary:receipt['binary_sha256']=hashlib.sha256(binary.read_bytes()).hexdigest()
    (output/'comparison.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt
