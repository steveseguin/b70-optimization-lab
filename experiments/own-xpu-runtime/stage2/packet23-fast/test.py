#!/usr/bin/env python3
"""CPU integration tests; never launches the device target."""
import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np
import jsonschema
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(HERE.parent/'packet3/tests'))
import reference
from reference import Reference
# Independent NumPy evaluation of SG32's eight-consecutive-products order.
# All synthetic shapes select that order; production dispatch is tested separately.
def linear(x,name,rows,expert=0):
    x=np.asarray(x,dtype=np.float32)
    w=reference.weight(name,min(rows,4),x.shape[-1],expert)
    lanes=np.zeros((*x.shape[:-1],len(w),32),dtype=np.float32)
    for base in range(0,x.shape[-1],256):
        for j in range(8):
            columns=np.arange(base+j,min(base+256,x.shape[-1]),8)
            lanes[..., :len(columns)]+=x[...,None,columns]*w[:,columns]
    y=reference.bf(reference.tree(lanes))
    return y[...,np.arange(rows)%len(w)]
reference.linear=linear
# Independent graph/reductions, shared elementary arithmetic identity v2.
mathlib=ctypes.CDLL(str(HERE/'build/host/libmath_bridge.so'))
for name in ('exp','log','sqrt'):
 fn=getattr(mathlib,'v2_'+name);fn.argtypes=[ctypes.c_float];fn.restype=ctypes.c_float
 def unary(x,fn=fn):
  a=np.asarray(x,dtype=np.float32)
  return np.fromiter((fn(float(v)) for v in a.flat),dtype=np.float32,count=a.size).reshape(a.shape)
 setattr(reference,name,unary)
rope_table=np.frombuffer((HERE/'rope.bf16').read_bytes(),dtype='<u2').reshape(-1,32,2)
def rope(x,position,rotary):
 x=np.asarray(x,dtype=np.float32); row=rope_table[position,np.arange(rotary//2)*(64//rotary)].astype(np.uint32)
 c=(row[:,0]<<16).view(np.float32);z=(row[:,1]<<16).view(np.float32)
 a,b=x[...,:rotary//2],x[...,rotary//2:rotary]
 return np.concatenate((reference.bf(a*c-b*z),reference.bf(b*c+a*z),x[...,rotary:]),axis=-1)
reference.rope=rope

def run(binary,scratch,input_dir,nongemv="parallel"):
    os.environ["PACKET18_NONGEMV"]=nongemv
    assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
    dynamic=subprocess.check_output(['readelf','-d',str(binary)],text=True)
    assert not any(n in dynamic.lower() for n in ('libsycl','libze_loader','libur_loader','libopencl'))
    scratch.mkdir(parents=True,exist_ok=False)
    rows=[]
    memory_plans={}
    def launch(name,args,ok=True):
        out=scratch/name
        env=dict(os.environ)
        if 'DEPCHECK_REPORT' in env:env['DEPCHECK_REPORT']=str(out.with_suffix('.san.json'))
        p=subprocess.run([str(binary),'--timing',os.environ.get('PACKET23_TIMING','token'),'--fusion',os.environ.get('PACKET21_FUSION','on'),'--nongemv',nongemv,*map(str,args),'--output',str(out)],capture_output=True,text=True,timeout=240,env=env)
        assert (p.returncode==0)==ok,(p.stdout,p.stderr)
        rows.append(dict(name=name,returncode=p.returncode))
        if 'DEPCHECK_REPORT' in env:
            san=json.loads(Path(env['DEPCHECK_REPORT']).read_text());assert not san['violations']
            rows[-1]['sanitizer']=san
        return out
    for cards in (1,2):
        for generated in (1,3,8):
            token_file=scratch/'single-token.txt';token_file.write_text('2\n')
            extra=['--input',token_file] if generated==8 else []
            directory=launch(f'mini-{cards}-{generated}', ['--mini','--cards',cards,'--memory','resident' if cards==2 else 'layer-streaming','--card',0,'--tokens',generated,*extra])
            ref=Reference()
            for token in ((2,) if generated==8 else (2,5,3,7,1)):ref.step(token)
            tokens=[]
            for i in range(generated):
                token=int(ref.buffers['next_token'][0]);tokens.append(token)
                if token==15:break
                if i+1<generated:ref.step(token)
            actual=json.loads((directory/'buffers.json').read_text())
            expected={k:v.reshape(-1).view(np.uint32).tolist() for k,v in ref.buffers.items()}
            if os.environ.get("PACKET21_FUSION","on")=="on":
                for key in list(expected):
                    if key.endswith("expert_input"):
                        assert all(x==0 for x in actual[key]), "removed gather was written"
                        actual.pop(key);expected.pop(key)
            assert actual==expected,[k for k in expected if actual.get(k)!=expected[k]]
            receipt=json.loads((directory/'receipt.json').read_text())
            jsonschema.validate(receipt,json.loads((HERE/'receipt.schema.json').read_text()))
            assert receipt['passed'] and not receipt['device_executed'] and receipt['tokens']==tokens
            assert receipt['oracle_exact'] is None and receipt['max_read_bytes']<=4*1024*1024
            for teardown in receipt['teardown']:
                assert teardown['safe_to_exit'] and teardown['live_bytes']==0 and teardown['in_flight']==0
                seq=teardown['sequence'];assert seq.index('quiesce')<seq.index('drain')<seq.index('graphs-released')<seq.index('idle-marker-complete')<seq.index('events-released')<seq.index('queue-released')<seq.index('context-released')
            timings=[json.loads(line) for line in (directory/'sites.jsonl').read_text().splitlines()]
            assert sum(t['kernel_submissions'] for t in timings if t.get('label','').endswith('expsgate'))==2*(8 if generated==8 else generated+4)
            assert len(list(directory.glob('step*/layer-*.bf16')))==2*generated
            rows[-1].update(exact=True,buffers=len(expected),values=sum(map(len,expected.values())),tokens=tokens)
    repeat=launch('repeat',['--mini','--tokens','1'])
    assert (repeat/'buffers.json').read_bytes()==(scratch/'mini-1-1/buffers.json').read_bytes()
    launch('context-rejection',['--mini','--tokens',64],False)
    launch('bad-memory-mode',['--mini','--cards','2','--tokens','1'],False)
    launch('bad-cards',['--mini','--cards',3],False)
    launch('host-native-refusal',['--mini','--authorized-device-window'],False)
    # Existing-output refusal must preserve all evidence.
    before=(repeat/'receipt.json').read_bytes()
    p=subprocess.run([str(binary),'--mini','--output',str(repeat)],capture_output=True)
    assert p.returncode and (repeat/'receipt.json').read_bytes()==before
    common=['--model-dir',json.loads((input_dir/'input.json').read_text())['model_dir'],'--plan',input_dir/'plan.tsv','--identity',input_dir/'identity.tsv']
    census=json.loads((ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json').read_text())['tensors']
    for cards in (1,2):
        d=launch(f'real-plan-{cards}',[*common,'--record','--cards',cards,'--memory','resident' if cards==2 else 'layer-streaming','--card',0]);plan=json.loads((d/'plan.json').read_text())
        actual=plan['tensor_owners'];assert len(actual)==1224
        assert {x['name']:x['bytes'] for x in actual}=={x['name']:x['bytes'] for x in census}
        total=[sum(x['bytes'] for x in actual if x['card']==i) for i in range(cards)]
        assert sum(total)==52629189120
        if cards==2:assert total==[26165134080,26464055040]
        assert sum(x['bytes'] for x in actual if x['card']==-1)==29321610240
        assert all('variant' in x for x in actual if x['component'] in ('routed_experts','routers','shared_experts','target_head'))
        assert sum(x.get('variant')=='decode_const_sg32_v1' for x in actual if x['component']=='routed_experts')==144
        memory=plan['memory_plan'];memory_plans[str(cards)]=memory
        if cards==1:
            assert memory['streamed_peak_weight_bytes']==528476160
            assert memory['request_and_workspace_bytes_per_card'][0]+memory['streamed_peak_weight_bytes']<1024**3
        else:
            assert all(b+w<30*1024**3 for b,w in zip(memory['request_and_workspace_bytes_per_card'],memory['resident_weights_per_card']))
        rows[-1].update(tensors=len(actual),owned_weight_bytes=total,dispatch_sites=plan['dispatch_sites'])
    (HERE/'memory-plan.json').write_text(json.dumps(dict(schema='own-runtime.iq3.packet18.memory.v1',
        context=128,device_measured=False,plans=memory_plans),indent=2)+'\n')
    return dict(schema='own-runtime.iq3.packet18.cpu-tests.v1',passed=True,device_executed=False,tests=rows,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--nongemv',choices=['core','parallel'],default='parallel');p.add_argument('--binary',type=Path,required=True);p.add_argument('--scratch',type=Path,required=True);p.add_argument('--input',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args();r=run(a.binary,a.scratch,a.input,a.nongemv);a.receipt.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
