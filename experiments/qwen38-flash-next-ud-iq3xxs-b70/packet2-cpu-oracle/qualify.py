#!/usr/bin/env python3
"""CPU equivalence gates for packed evaluation, bindings and tokenizer."""
import json
import importlib.util
import os
from pathlib import Path
import time
import numpy as np
import torch
from oracle import HERE, OWN, ROOT, Store, Linear, Model, Tokenizer, ref, sha, dump, perm, unperm, tensor_hash
from packed import decode
from loaders.dequant import dequantize, BY_NAME


def main():
    assert os.getpriority(os.PRIO_PROCESS,0) == 19
    torch.set_num_threads(2); torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    start = time.monotonic()
    s = Store()
    samples = json.loads((HERE.parent/'packet1/sample-receipt.json').read_text())['content']['samples']
    checked = []
    for sample in samples:
        t = s.tensors[sample['name']]
        block,size = BY_NAME[t['type']]
        raw = s.raw(t,sample['row_index'],1)
        raw = raw[sample['column_start']//block*size:][:sample['raw_bytes']]
        out = decode(t['type'],raw)
        assert sha(raw) == sample['raw_sha256']
        assert sha(out.tobytes()) == sample['decoded_fp32_le_sha256'], sample['name']
        checked.append(dict(name=sample['name'],row=sample['row_index'],sha256=sha(out.tobytes())))
    rng = np.random.default_rng(9191)
    random_blocks = 0
    for kind in ('IQ2_S','IQ3_S','IQ4_NL','Q6_K','Q8_0'):
        block,size = BY_NAME[kind]
        b = rng.integers(0,256,(32,size),dtype=np.uint8)
        at = 208 if kind=='Q6_K' else 0
        # finite positive/negative/subnormal/zero binary16 scales
        scales = np.array([0,32768,1,32769,0x3c00,0xbc00,0x3555,0xb555]*4,dtype='<u2')
        b[:,at:at+2] = scales.view(np.uint8).reshape(-1,2)
        raw = b.tobytes()
        assert decode(kind,raw).tobytes() == dequantize(kind,raw,[32,block]).numpy().tobytes(),kind
        random_blocks += 32
    for width in (1,128):
        x = torch.arange(48*width).reshape(1,-1)
        assert torch.equal(unperm(perm(x,width),width),x)
    spec = importlib.util.spec_from_file_location('packet1b_reference',OWN/'stage2/packet1b/reference.py')
    original = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = original
    spec.loader.exec_module(original)
    torch.manual_seed(173)
    bf = torch.bfloat16
    x = torch.randn(2,128).to(bf)
    gamma = torch.randn(128).to(bf)
    assert torch.equal(original.norm(x,gamma),ref.norm(x,gamma.float()+1))
    q,k = torch.randn(2,16,128).to(bf),torch.randn(2,16,128).to(bf)
    v = torch.randn(2,48,128).to(bf)
    a,b = torch.randn(2,48).to(bf),torch.randn(2,48).to(bf)
    alog,dt = torch.randn(48).to(bf),torch.randn(48).to(bf)
    state = torch.randn(48,128,128).to(bf)
    expected = original.recurrence(q,k,v,a,b,alog,dt,state)
    actual = ref.recurrence(q,k,v,a,b,-alog.float().exp(),dt.float(),state)
    assert all(torch.equal(a,b) for a,b in zip(actual,expected))
    tokenizer = Tokenizer(s.meta)
    manifest = json.loads((HERE/'prompts/prompts.json').read_text())
    inputs = []
    # Independent well-tested BPE implementation, metadata from the same file.
    from tokenizers import Tokenizer as HFTokenizer, models, pre_tokenizers, decoders, AddedToken, Regex
    from tokenizer import PATTERN
    independent = HFTokenizer(models.BPE(vocab=tokenizer.vocab,merges=[tuple(x.split(' ')) for x in s.meta['tokenizer.ggml.merges']]))
    independent.pre_tokenizer = pre_tokenizers.Sequence([pre_tokenizers.Split(Regex(PATTERN),behavior='isolated'),pre_tokenizers.ByteLevel(add_prefix_space=False,use_regex=False)])
    independent.decoder = decoders.ByteLevel()
    independent.add_special_tokens([AddedToken(x,special=True,normalized=False) for x in tokenizer.special])
    for p in manifest['prompts']:
        text = (HERE/'prompts'/f"{p['id']}.txt").read_text()
        ids = tokenizer.encode(text)
        assert tokenizer.decode(ids) == text
        assert independent.encode(text).ids == ids,p['id']
        inputs.append(dict(id=p['id'],tokens=ids,count=len(ids),roundtrip=True,independent_tokenizers_match=True))
    # Real projection: frozen tile/M1 dispatch, batched and separate rows exact.
    x = torch.arange(2560).float().sin().to(torch.bfloat16)[None,:]
    linear = Linear(s,'blk.0.ffn_gate_inp.weight')
    y = linear(x)
    assert torch.equal(linear(x.repeat(2,1)),y.repeat(2,1))
    # Real PLE weights, synthetic streams: cross the dilation-three history
    # boundary and require row batching to preserve every bit of output/state.
    tokens = [248045,872,198,2610]
    streams = torch.arange(4*4*2560).float().sin().reshape(4,4,2560).to(bf)
    batch = Model(s,lambda _:None,time.monotonic()+120,'silu')
    serial = Model(s,lambda _:None,time.monotonic()+120,'silu')
    actual = batch.ple(streams,tokens)
    expected = torch.cat([serial.ple(streams[i:i+1],[t]) for i,t in enumerate(tokens)])
    assert torch.equal(actual,expected) and torch.isfinite(actual).all()
    assert torch.equal(batch.ple_history,serial.ple_history)
    assert batch.history == serial.history
    dump(HERE/'ple-binding-test.json',dict(scope='real PLE weights; synthetic streams; not a full-model fixture',
        passed=True,rows=4,input_tokens=tokens,input_sha256=tensor_hash(streams),
        output_sha256=tensor_hash(actual),history_sha256=tensor_hash(batch.ple_history),
        batch_serial_bit_exact=True,source_sha256=sha(Path(__file__).read_bytes())))
    s.close()
    receipt = dict(passed=True,elapsed_seconds=time.monotonic()-start,samples=checked,
        synthetic_blocks=random_blocks,inputs=inputs,projection_sha256=sha(y.view(torch.uint8).numpy().tobytes()),
        permute_roundtrip=True,norm_storage_adapter_exact=True,decay_storage_adapter_exact=True,
        tokenizers_version=__import__('tokenizers').__version__,
        sources={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in list(HERE.glob('*.py'))+list((OWN/'stage1/packet1b/loaders').glob('*.py'))},torch=torch.__version__)
    dump(HERE/'qualification.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('samples','inputs','sources')}))


if __name__ == '__main__': main()
