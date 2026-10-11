#!/usr/bin/env python3
"""Streaming, CPU-only IQ3 arithmetic oracle. No device/runtime API calls."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import mmap
import os
from pathlib import Path
import resource
import signal
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OWN = ROOT/'experiments/own-xpu-runtime'
sys.path.insert(0,str(OWN/'stage1/packet1b'))
import torch
from loaders.headers import gguf_header, gguf_shards
from loaders.dequant import BY_NAME
from packed import decode
from tokenizer import Tokenizer
import reference_gguf as ref

BF16 = torch.bfloat16
STOP = False


def sha(b): return hashlib.sha256(b).hexdigest()
def dump(path, value):
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    temp.replace(path)


def tensor_hash(x): return sha(x.contiguous().view(torch.uint8).numpy().tobytes())


def signature(path):
    s = path.stat()
    return dict(bytes=s.st_size,ctime_ns=s.st_ctime_ns,device=s.st_dev,inode=s.st_ino,mtime_ns=s.st_mtime_ns)


class Store:
    """One read-only bounded mmap per row tile; close it immediately.

    File mappings therefore cannot build up 82 GB of process RSS. Unmapping
    leaves the shared host page cache alone (no madvise or cache drops).
    """
    def __init__(self):
        self.admission = json.loads((HERE.parent/'packet1/admission-receipt.json').read_text())
        assert self.admission['passed']
        self.paths, self.fds, parsed = {}, {}, []
        for f in self.admission['files']:
            p = Path(self.admission['model_dir'])/Path(f['path']).name
            assert signature(p) == f['after'], ('changed admitted file',str(p))
            fd = p.open('rb')
            self.paths[f['path']], self.fds[f['path']] = p,fd
            parsed.append(gguf_header(fd,p.stat().st_size))
        gguf_shards(parsed)
        self.meta = parsed[0]['metadata']
        self.tensors = {t['name']:t for t in json.loads((HERE.parent/'packet1/tensor-census.json').read_text())['tensors']}
        for p,f in zip(parsed,self.admission['files']):
            for n,t in p['tensors'].items():
                for field in ('shape','type','bytes','file_offsets'):
                    assert t[field] == self.tensors[n][field]
                assert self.tensors[n]['shard'] == f['path']
        self.read_bytes = 0

    def raw(self, t, row, rows):
        width = t['shape'][-1]
        block,size = BY_NAME[t['type']]
        rb = width//block*size
        assert 0 <= row and row+rows <= math.prod(t['shape'])//width
        start = t['file_offsets'][0]+row*rb
        aligned = start//mmap.ALLOCATIONGRANULARITY*mmap.ALLOCATIONGRANULARITY
        length = rows*rb
        with mmap.mmap(self.fds[t['shard']].fileno(),start-aligned+length,
                       access=mmap.ACCESS_READ,offset=aligned) as mm:
            raw = mm[start-aligned:start-aligned+length]
        self.read_bytes += length
        return raw

    def rows(self, name, row, rows):
        t = self.tensors[name]
        return torch.from_numpy(decode(t['type'],self.raw(t,row,rows)).reshape(rows,t['shape'][-1]))

    def small(self, name):
        t = self.tensors[name]
        assert math.prod(t['shape']) <= 10240*4
        return self.rows(name,0,math.prod(t['shape'])//t['shape'][-1]).reshape(t['shape'])

    def check(self):
        for f in self.admission['files']:
            assert signature(self.paths[f['path']]) == f['after']

    def close(self):
        self.check()
        for fd in self.fds.values(): fd.close()


class Linear:
    """Exact FP32 dequant -> fixed M1 BLAS, 128 output rows -> BF16.

    K order is the stored GGUF column order. Input rows are always evaluated
    individually, so prefill batching never changes the dot-product dispatch.
    The FP32 CPU BLAS build/thread/ISA identity is part of the receipt.
    """
    def __init__(self, store, name, expert=None):
        self.store,self.name = store,name
        shape = store.tensors[name]['shape']
        self.n = shape[-2] if len(shape)>1 else 1
        self.base = 0 if expert is None else expert*self.n
        assert (len(shape)==3) == (expert is not None)

    def __call__(self, x):
        ref.cpu(x)
        assert x.dtype == BF16
        out = []
        xf = x.float()
        for start in range(0,self.n,128):
            w = self.store.rows(self.name,self.base+start,min(128,self.n-start))
            out.append(torch.cat([(row @ w.T).to(BF16) for row in xf.split(1)],0))
        return torch.cat(out,-1)


def unperm(x, width):
    """Stored [3,16,D] value-head order back to reference [16,3,D]."""
    return x.reshape(*x.shape[:-1],3,16,width).transpose(-3,-2).flatten(-3)


def perm(x, width):
    return x.reshape(*x.shape[:-1],16,3,width).transpose(-3,-2).flatten(-3)


class Model:
    def __init__(self, store, progress, deadline, output_gate):
        self.s,self.progress,self.deadline = store,progress,deadline
        self.output_gate = output_gate
        self.gdn,self.qsa = {},{}
        self.history = [248044,248044]
        self.ple_history = torch.zeros((10240,9),dtype=BF16)
        self.position = 0

    def guard(self):
        if STOP or time.monotonic() >= self.deadline: raise InterruptedError('wall limit or stop signal')
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024 >= 38_000_000_000:
            raise MemoryError('38 GB RSS guard')

    def linear(self, name, expert=None): return Linear(self.s,name,expert)
    def small(self, name): return self.s.small(name)

    def hc(self, prefix, inject=True):
        w = {k:self.linear(prefix+k+'.weight') for k in ('down','up')}
        w['norm'] = self.small(prefix+'norm.weight').reshape(4,2560)
        if inject: w['inject'] = self.linear(prefix+'inject.weight')
        return w

    def ple(self, streams, tokens):
        m = self.s.meta
        ids,self.history = ref.ple_ids(tokens,self.history,
            m['qwen4exp.ple.layer_multipliers'],m['qwen4exp.ple.head_vocab_sizes'],
            m['qwen4exp.ple.head_offsets'],m['qwen4exp.ple.eos_token_id'])
        # GGUF PLE is already scaled/requantized; no official FP8 scale added.
        emb = torch.stack([torch.cat([self.s.rows('per_layer_token_embd.weight',int(i),1)[0]
                                    for i in row]) for row in ids]).to(BF16)
        prefix = 'blk.1.ple_'
        key = self.linear(prefix+'key.weight')(emb).reshape(-1,4,2560)
        value = self.linear(prefix+'value.weight')(emb)
        def grouped(x, name):
            w = self.small(prefix+'norm_'+name+'.weight').reshape(4,2560)
            return torch.stack([ref.norm(x[:,i],w[i]) for i in range(4)],1)
        key,query = grouped(key,'key'),grouped(streams,'query')
        # Frozen extension of packet1b U6: explicit BF16 eager boundaries.
        product = (key.float()*query.float()).to(BF16)
        dot = ref.tree(product).to(BF16)
        gate = (dot.float()/math.sqrt(2560)).to(BF16)
        root = gate.abs().clamp_min(1e-6).float().sqrt().to(BF16)
        gate = torch.sigmoid((gate.sign().float()*root.float()).to(BF16).float()).to(BF16)
        gated = (gate.float()[:,:,None]*value.float()[:,None,:]).to(BF16)
        normalized = grouped(gated,'conv').flatten(1)
        weight = self.small(prefix+'conv1d.weight')[:,None,:]
        convrows = []
        for row in normalized:
            # dilation 3, chronological taps t-9,t-6,t-3,t; reuse conv math.
            y,_ = ref.conv(row,self.ple_history[:,::3],weight)
            convrows.append(y)
            self.ple_history = torch.cat((self.ple_history[:,1:],row[:,None]),1)
        branch = (gated.flatten(1).float()+torch.stack(convrows).float()).to(BF16)
        return (streams.float()+branch.reshape_as(streams).float()).to(BF16)

    def attention(self, layer, x):
        p = f'blk.{layer}.'
        if layer%4 != 3:
            def qkv(x):
                q,k,v = self.linear(p+'attn_qkv.weight')(x).split([2048,2048,6144],-1)
                return torch.cat((q,k,unperm(v,128)),-1)
            conv = self.small(p+'ssm_conv1d.weight')
            conv = torch.cat((conv[:4096],unperm(conv[4096:].T,128).T),0)[:,None,:]
            w = dict(qkv=qkv,z=lambda x:unperm(self.linear(p+'attn_gate.weight')(x),128),
                a=lambda x:unperm(self.linear(p+'ssm_alpha.weight')(x),1),
                b=lambda x:unperm(self.linear(p+'ssm_beta.weight')(x),1),
                alog=unperm(self.small(p+'ssm_a'),1),dt=unperm(self.small(p+'ssm_dt.bias'),1),
                conv=conv,norm=self.small(p+'ssm_norm.weight'),
                out=lambda x:self.linear(p+'ssm_out.weight')(perm(x,128)))
            history,state = self.gdn.get(layer,(torch.zeros((10240,3),dtype=BF16),torch.zeros((48,128,128),dtype=BF16)))
            y,history,state = ref.gdn(x,w,history,state,self.output_gate)
            self.gdn[layer] = history,state
            return y
        w = {k:self.linear(p+n+'.weight') for k,n in dict(q='attn_q',k='attn_k',v='attn_v',out='attn_output').items()}
        w.update({k:self.small(p+n+'.weight') for k,n in dict(qn='attn_q_norm',kn='attn_k_norm',iqn='indexer.q_norm',ikn='indexer.k_norm').items()})
        w['index'] = lambda x:torch.cat((self.linear(p+'indexer.q_proj.weight')(x),self.linear(p+'indexer.k_proj.weight')(x)),-1)
        past = self.qsa.get(layer,(torch.zeros((0,2,256),dtype=BF16),torch.zeros((0,2,256),dtype=BF16),torch.zeros((0,128),dtype=BF16)))
        y,self.qsa[layer] = ref.qsa(x,w,past)
        return y

    def mlp(self, layer, x):
        p = f'blk.{layer}.'
        def expert(e):
            self.guard()
            return {k:self.linear(p+'ffn_'+k+'_exps.weight',e) for k in ('gate','up','down')}
        shared = {k:self.linear(p+'ffn_'+k+'_shexp.weight') for k in ('gate','up','down')}
        # ref.moe calls only the selected ten, in routing order. No expert cache.
        return ref.moe(x,self.linear(p+'ffn_gate_inp.weight'),expert,shared,
                       self.linear(p+'ffn_gate_inp_shexp.weight'))[0]

    def forward(self, tokens, fixture=None):
        started = time.monotonic()
        emb = torch.cat([self.s.rows('token_embd.weight',i,1) for i in tokens]).to(BF16)
        streams = emb[:,None,:].repeat(1,4,1)
        for layer in range(48):
            self.guard()
            if layer == 1: streams = self.ple(streams,tokens)
            streams = ref.layer(streams,lambda x:self.attention(layer,x),lambda x:self.mlp(layer,x),
                                self.hc(f'blk.{layer}.hc_attn_'),self.hc(f'blk.{layer}.hc_ffn_'))
            if not torch.isfinite(streams).all(): raise ValueError(f'nonfinite layer {layer}')
            if fixture is not None:
                # End of final prompt position, which predicts generated step 1.
                hidden = streams[-1:].contiguous()
                raw = hidden.view(torch.uint8).numpy().tobytes()
                (fixture/f'layer-{layer:02}.bf16').write_bytes(raw)
                with (fixture/'layers.jsonl').open('a') as f:
                    f.write(json.dumps(dict(layer=layer,shape=list(hidden.shape),dtype='BF16 little-endian',sha256=sha(raw)))+'\n')
            self.progress(dict(phase='layer',layer=layer,positions=[self.position,self.position+len(tokens)],seconds=time.monotonic()-started))
        self.position += len(tokens)
        sample,_ = ref.hc_mix(streams[-1:],self.hc('output_hc_',False))
        logits = self.linear('output.weight')(sample)[0].float()
        if not torch.isfinite(logits).all(): raise ValueError('nonfinite logits')
        ids = torch.argsort(logits,descending=True,stable=True)[:5]
        return dict(token_id=int(ids[0]),top5_ids=ids.tolist(),top5_logits=logits[ids].tolist(),
                    logits_fp32_sha256=tensor_hash(logits),seconds=time.monotonic()-started)


def run(args):
    assert os.getpriority(os.PRIO_PROCESS,0) == 19
    assert os.environ.get('OMP_NUM_THREADS') == '8'
    torch.set_num_threads(8)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    assert sys.byteorder == 'little'
    # Bound address space too; maps are tiles, never whole model shards.
    resource.setrlimit(resource.RLIMIT_AS,(38_000_000_000,38_000_000_000))
    args.out.mkdir(parents=True,exist_ok=False)
    started = time.monotonic()
    deadline = started+args.hours*3600
    store = Store()
    tok = Tokenizer(store.meta)
    sources = list(HERE.glob('*.py'))+list((OWN/'stage1/packet1b/loaders').glob('*.py'))+list((OWN/'stage1/packet1b/loaders').glob('*grid*.json'))+[
        OWN/'stage2/packet1b/reference.py',OWN/'stage2/packet1/metadata/config.json',
        HERE/'prompts/prompts.json',HERE/'research-sources.json',HERE/'arithmetic-decision.json',
        HERE.parent/'packet1/admission-receipt.json',HERE.parent/'packet1/tensor-census.json',
        HERE.parent/'baseline-llamacpp/prepare-prompts.py',HERE.parent/'baseline-llamacpp/prompt-receipt.json',
        ROOT/'repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json']
    receipt = dict(schema='iq3-cpu-oracle.v1',started_utc=datetime.now(timezone.utc).isoformat(),
        git_head=os.popen('git rev-parse HEAD').read().strip(),host=os.uname().nodename,
        python=sys.version,torch=torch.__version__,numpy=__import__('numpy').__version__,
        torch_config=torch.__config__.show(),torch_cpu_capability=torch.backends.cpu.get_cpu_capability(),
        nice=19,threads=8,interop_threads=1,max_wall_seconds=args.hours*3600,
        gdn_output_gate=args.gdn_output_gate,
        sources={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sources},
        inputs=store.admission,tokenizer=dict(pre='qwen35',vocab=sha(json.dumps(store.meta['tokenizer.ggml.tokens'],ensure_ascii=False,separators=(',',':')).encode()),
        merges=sha(json.dumps(store.meta['tokenizer.ggml.merges'],ensure_ascii=False,separators=(',',':')).encode())),
        template=sha(store.meta['tokenizer.chat_template'].encode()),status='running',prompts=[])
    dump(args.out/'receipt.json',receipt)
    manifest = json.loads((HERE/'prompts/prompts.json').read_text())
    baseline = json.loads((HERE.parent/'baseline-llamacpp/prompt-receipt.json').read_text())
    requested = json.loads((ROOT/'repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json').read_text())
    assert [(p['id'],sha(p['prompt'].encode())) for p in requested['prompts']] == [(p['id'],p['raw_sha256']) for p in baseline['prompts']]
    assert manifest['template_sha256'] == baseline['template_sha256'] == receipt['template']
    try:
        for index,p in enumerate(manifest['prompts'][:args.prompts]):
            if time.monotonic() >= deadline: break
            prompt_started = time.monotonic()
            directory = args.out/p['id']; directory.mkdir()
            fixture = directory/'step1'; fixture.mkdir()
            text = (HERE/'prompts'/f"{p['id']}.txt").read_text()
            assert sha(text.encode()) == p['rendered_sha256'] == baseline['prompts'][index]['rendered_sha256']
            ids = tok.encode(text)
            assert tok.decode(ids) == text
            dump(directory/'input.json',dict(id=p['id'],tokens=ids,rendered_sha256=sha(text.encode()),prompt_tokens=len(ids)))
            result = dict(id=p['id'],prompt_tokens=len(ids),tokens=[],steps=[],status='prefill')
            receipt['prompts'].append(result)
            def progress(row):
                row['elapsed_seconds'] = time.monotonic()-started
                with (directory/'progress.jsonl').open('a') as f: f.write(json.dumps(row)+'\n')
                print(p['id'],json.dumps(row),flush=True)
            model = Model(store,progress,deadline,args.gdn_output_gate)
            step = model.forward(ids,fixture)
            result['prefill_seconds'] = step['seconds']
            while len(result['tokens']) < args.tokens:
                result['tokens'].append(step['token_id'])
                result['steps'].append(step)
                result['text'] = tok.decode(result['tokens'])
                result['seconds'] = time.monotonic()-prompt_started
                result['status'] = 'decode'
                dump(directory/'result.json',result)
                dump(args.out/'receipt.json',receipt)
                with (directory/'tokens.jsonl').open('a') as f:
                    f.write(json.dumps(dict(step=len(result['tokens']),**step))+'\n')
                if step['token_id'] in {store.meta['tokenizer.ggml.eos_token_id'],store.meta['tokenizer.ggml.bos_token_id']}:
                    result['status'] = 'eos'; break
                if len(result['tokens']) == 8:
                    result['pilot_decode_seconds_per_token'] = sum(s['seconds'] for s in result['steps'][1:])/7
                    if result['pilot_decode_seconds_per_token'] >= 600:
                        result['status'] = 'pilot-too-slow'; break
                if len(result['tokens']) == args.tokens:
                    result['status'] = 'token-cap'; break
                model.guard()
                step = model.forward([step['token_id']])
            decode_times = [s['seconds'] for s in result['steps'][1:]]
            result['decode_seconds_per_token'] = sum(decode_times)/len(decode_times) if decode_times else None
            result['seconds'] = time.monotonic()-prompt_started
            dump(directory/'result.json',result)
            dump(args.out/'receipt.json',receipt)
            del model
            if result['status'] == 'pilot-too-slow': break
        receipt['status'] = 'completed' if len(receipt['prompts']) == args.prompts else 'wall-limit'
    except InterruptedError as exc:
        receipt['status'] = 'wall-limit-or-stop'
        receipt['stop_reason'] = str(exc)
    except BaseException as exc:
        receipt['status'] = 'failed'
        receipt['error'] = repr(exc)
        raise
    finally:
        receipt['elapsed_seconds'] = time.monotonic()-started
        receipt['max_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        receipt['model_bytes_read'] = store.read_bytes
        receipt['completed_utc'] = datetime.now(timezone.utc).isoformat()
        store.close()
        dump(args.out/'receipt.json',receipt)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--hours',type=float,default=4)
    ap.add_argument('--prompts',type=int,default=12)
    ap.add_argument('--tokens',type=int,default=64)
    ap.add_argument('--gdn-output-gate',choices=['silu','sigmoid'],required=True,
                    help='Pending owner choice: packet1b SiLU or published-config sigmoid')
    args = ap.parse_args()
    assert 0 < args.hours <= 4 and 1 <= args.prompts <= 12 and 1 <= args.tokens <= 64
    def stop(signum, frame):
        global STOP
        STOP = True
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    with torch.inference_mode(): run(args)
