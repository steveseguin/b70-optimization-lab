#!/usr/bin/env python3
"""Independent packet1b fixtures. CPU torch only; never query device APIs."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import torch
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('p15_reference',HERE.parent.parent/'packet1b/reference.py')
ref=importlib.util.module_from_spec(spec);sys.modules[spec.name]=ref;spec.loader.exec_module(ref)
B,F=torch.bfloat16,torch.float32
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def raw(x):return x.contiguous().view(torch.uint8).numpy().tobytes()
def rnd(*s):return (torch.randint(-16,17,s).float()/32).to(B)
def zeros(*s):return torch.zeros(s,dtype=B)
def save(out,name,op,inputs,outputs,T=1,W=2560,H=4,E=0,flags=1,capacity=128,budget=2048,pos=0,active=1,error=0):
    outputs=dict(outputs);outputs.setdefault(15,torch.tensor([pos,active,error],dtype=torch.int32))
    buffers={**inputs,15:torch.tensor([pos,active,error],dtype=torch.int32)}
    for slot,value in outputs.items():
        if slot not in buffers:buffers[slot]=torch.full_like(value,0)
    if not active or error:outputs={slot:buffers[slot].clone() for slot in outputs}
    data=bytearray(struct.pack('<8i',op,T,W,H,E,flags,capacity,budget))
    for j in range(16):
        v=raw(buffers.get(j,torch.zeros(1,dtype=torch.int32)))
        data+=struct.pack('<2I',len(v),j in outputs)+v
        if j in outputs:
            b=raw(outputs[j]);assert len(b)==len(v);data+=b
    path=out/(name+'.fixture');path.write_bytes(data)
    return dict(name=path.name,op=op,M=T,output_bytes=sum(len(raw(v)) for v in outputs.values()),sha256=sha(path))
def generate(out):
    torch.set_num_threads(2);torch.set_num_interop_threads(1);torch.manual_seed(1511)
    out.mkdir(parents=True,exist_ok=False);cases=[]
    def add(*a,**kw):cases.append(save(out,*a,**kw))
    for T in (1,3,87):
        # Genuine full-shape recurrence: nonzero state, varied inputs; output/state BOTH checked.
        q,k,v,a,b=rnd(T,16,128),rnd(T,16,128),rnd(T,48,128),rnd(T,48),rnd(T,48)
        alog,dt,state=rnd(48),rnd(48),rnd(48,128,128)
        y,st=ref.recurrence(q,k,v,a,b,alog,dt,state);y_saved=y
        qkv=torch.cat((q.flatten(1),k.flatten(1),v.flatten(1)),-1)
        args={0:qkv,1:a,2:b,3:alog,4:dt,5:state}
        add(f'gdn-{T}',1,args,{6:y,7:st},T=T)
        if T==1:
            add('gdn-inactive',1,args,{6:y,7:st},active=0)
            add('gdn-sticky-error',1,args,{6:y,7:st},error=1)
        # Packed layout identity changes only mapping; A is already negative exponential.
        perm=torch.tensor([(h%16)*3+h//16 for h in range(48)])
        add(f'gdn-packed-{T}',1,{0:torch.cat((q.flatten(1),k.flatten(1),v[:,perm].flatten(1)),-1),1:a[:,perm],2:b[:,perm],3:-torch.exp(alog[perm].float()),4:dt[perm],5:state[perm]}, {6:y[:,perm],7:st[perm]},T=T,flags=2|4)
        for width in (17,10240):
            x,h,w=rnd(T,width),rnd(width,3),rnd(width,1,4);history=h.clone();ys=[]
            for row in x:
                z,history=ref.conv(row,history,w);ys.append(z)
            add(f'conv-{width}-{T}',0,{0:x,1:h,2:w},{3:torch.stack(ys),4:history},T=T,W=width,E=1)
        streams,w=rnd(T,4,2560),rnd(4,2560)
        normed=torch.stack([ref.norm(streams[:,h],w[h]) for h in range(4)],1)
        add(f'norm-{T}',2,{0:streams,1:w},{2:normed},T=T)
        branch,inj=rnd(T,2560),rnd(T,4)
        combined=ref.hc_combine(streams,branch,inj)
        normed2=torch.stack([ref.norm(combined[:,h],w[h]) for h in range(4)],1)
        add(f'combine-norm-{T}',5,{0:streams,1:branch,2:inj,3:w},{4:combined,5:normed2},T=T)
        gate=rnd(T,4,2560);acc=torch.zeros(T,2560)
        for h in range(4):acc=acc+torch.sigmoid(gate[:,h].float())*normed[:,h].float()
        add(f'mix-{T}',4,{0:normed,1:gate},{2:(acc/4).to(B)},T=T)
        x=rnd(T,320);add(f'hc-act-{T}',3,{0:x},{2:ref.silu(x.float()/4).to(B)},T=T,W=320)
        x,u=rnd(T,640),rnd(T,640);add(f'ffn-act-{T}',3,{0:x,1:u},{2:(ref.silu(x)*u.float()).to(B)},T=T,W=640,E=1)
        rng=torch.get_rng_state();rx,ru=rnd(T,10,640),rnd(T,10,640);torch.set_rng_state(rng);add(f'ffn-routed-act-{T}',3,{0:rx,1:ru},{2:(ref.silu(rx)*ru.float()).to(B)},T=T,W=6400,E=1)
        y,z,wg=rnd(T,48,128),rnd(T,48,128),rnd(128)
        add(f'gdn-gated-{T}',8,{0:y,1:z,2:wg},{3:(ref.norm(y,wg,unit=False,out=F)*torch.sigmoid(z.float())).to(B)},T=T,H=48,flags=0)
        logits=rnd(T,512);ids,prob=ref.route(logits);x=rnd(T,2560)
        routes=torch.stack((ids,torch.zeros_like(ids),torch.full_like(ids,640)),-1).int();down=routes.clone();down[:,:,2]=2560
        add(f'route-gather-{T}',6,{0:logits,1:x},{2:ids.int(),3:prob,4:x[:,None,:].expand(-1,10,-1).clone(),5:routes,6:down},T=T,W=512,E=10)
        expert,shared,sg=rnd(T,10,2560),rnd(T,2560),rnd(T);acc=torch.zeros(T,2560)
        for j in range(10):acc=acc+expert[:,j].float()*prob[:,j,None]
        combined=(acc.to(B).float()+(shared.float()*torch.sigmoid(sg.float())[:,None]).to(B).float()).to(B)
        add(f'moe-combine-{T}',7,{0:expert,1:prob,2:shared,3:sg},{4:combined},T=T,E=10)
        # Real GGUF scalar weights are F32. Never quantize them to BF16 on load.
        add(f'norm-stored-f32-{T}',2,{0:streams,1:w.float()+1},{2:normed},T=T,flags=8)
        add(f'gdn-runtime-f32-{T}',1,{0:torch.cat((q.flatten(1),k.flatten(1),v[:,perm].flatten(1)),-1),1:a[:,perm],2:b[:,perm],3:-torch.exp(alog[perm].float()),4:dt[perm].float(),5:state[perm]}, {6:y_saved[:,perm],7:st[perm]},T=T,flags=2|4|8)
        # QSA prepare, append/chronological pool, select and gated attention.
        pos=3;cap=128;positions=torch.arange(pos,pos+T)
        qgate,k,iq=rnd(T,24,512),rnd(T,2,256),rnd(T,4,128)
        qw,kw,iw=rnd(256),rnd(256),rnd(128)
        qout=ref.rope(ref.norm(qgate[:,:,:256],qw),positions)
        kout=ref.rope(ref.norm(k,kw),positions);iout=ref.rope(ref.norm(iq,iw),positions)
        add(f'qsa-prepare-{T}',9,{0:qgate,1:k,2:iq,3:qw,4:kw,5:iw},{6:qout,7:qgate[:,:,256:].clone(),8:kout,9:iout},T=T,pos=pos)
        oldk,oldv,oldraw=rnd(cap,2,256),rnd(cap,2,256),rnd(cap,128);values,rawkey=rnd(T,2,256),rnd(T,128);poolw=rnd(128)
        allk,allv,allraw=oldk.clone(),oldv.clone(),oldraw.clone();allk[pos:pos+T]=kout;allv[pos:pos+T]=values;allraw[pos:pos+T]=rawkey
        pooled=zeros((cap+3)//4,128);complete=ref.compress(allraw[:pos+T]);ck=ref.rope(ref.norm(complete[:,None,:],poolw),torch.arange(len(complete))*4)[:,0,:];pooled[:len(ck)]=ck
        add(f'qsa-pool-{T}',10,{0:kout,1:values,2:rawkey,3:poolw,4:oldk,5:oldv,6:oldraw,7:zeros((cap+3)//4,128)},{4:allk,5:allv,6:allraw,7:pooled},T=T,pos=pos)
        ids=torch.stack([ref.select(iout[r],ck,pos+r) for r in range(T)]).int()
        add(f'qsa-select-{T}',11,{0:iout,1:pooled},{2:ids},T=T,pos=pos)
        ys=[];score_full=torch.zeros(T,24,2051);prob_full=torch.zeros_like(score_full);score_full[:,:,:cap]=-torch.inf
        for r in range(T):
            ix=ids[r][ids[r]>=0].long();ks=allk[ix].repeat_interleave(12,1).float();vs=allv[ix].repeat_interleave(12,1).float()
            score=ref.tree(ks*qout[r].float())/16;ex=torch.exp(score-score.max(0).values);p=ex/ref.tree(ex.T)[None,:]
            score_full[r,:,:len(ix)]=score.T;prob_full[r,:,:len(ix)]=p.T
            y=ref.tree((p[:,:,None]*vs).permute(1,2,0)).to(B);ys.append((y.float()*torch.sigmoid(qgate[r,:,256:].float())).to(B))
        add(f'qsa-attention-{T}',12,{0:qout,1:qgate[:,:,256:].clone(),2:allk,3:allv,4:ids,6:torch.zeros(T,24,2051),7:torch.zeros(T,24,2051)}, {5:torch.stack(ys),6:score_full,7:prob_full},T=T,pos=pos)
    # Non-BF16 FP32 conv coefficients catch an accidental weight cast.
    x,h,w=rnd(3,17),rnd(17,3),rnd(17,1,4).float()+2**-13;history=h.clone();ys=[]
    for row in x:
        y,history=ref.conv(row,history,w);ys.append(y)
    add('conv-real-f32-weights',0,{0:x,1:h,2:w},{3:torch.stack(ys),4:history},T=3,W=17,E=1,flags=8)
    # Odd widths exercise zero-padding at every tree level, not just powers of two.
    for width in (1,3,17,255,2560):
        x,w=rnd(1,4,width),rnd(4,width)
        y=torch.stack([ref.norm(x[:,h],w[h]) for h in range(4)],1)
        add(f'norm-odd-{width}',2,{0:x,1:w},{2:y},W=width)
    # PLE dilation3 is outside packet1b.conv: independent literal tap/cast oracle.
    width,T=17,5;x,h,w=rnd(T,width),rnd(width,9),rnd(width,4);history=h.clone();ys=[]
    for row in x:
        acc=torch.zeros(width)
        for tap in range(4):acc=acc+(row if tap==3 else history[:,3*tap]).float()*w[:,tap].float()
        ys.append(ref.silu(acc.to(B)).to(B));history=torch.cat((history[:,1:],row[:,None]),-1)
    add('conv-dilation3',0,{0:x,1:h,2:w},{3:torch.stack(ys),4:history},T=T,W=width,E=3)
    # Stable all-equal router, and finite-input rejection (no output writes).
    logits=zeros(1,512);x=rnd(1,2560);ids,prob=ref.route(logits)
    routes=torch.stack((ids,torch.zeros_like(ids),torch.full_like(ids,640)),-1).int();down=routes.clone();down[:,:,2]=2560
    rout={2:ids.int(),3:prob,4:x[:,None,:].expand(-1,10,-1).clone(),5:routes,6:down}
    add('route-ties',6,{0:logits,1:x},rout,W=512,E=10)
    varied=(torch.arange(512,dtype=F)/32-8).to(B)[None,:];vi,vp=ref.route(varied)
    assert int(vi[0,0])==511 and torch.unique(vp).numel()>1
    vr=torch.stack((vi,torch.zeros_like(vi),torch.full_like(vi,640)),-1).int();vd=vr.clone();vd[:,:,2]=2560
    add('route-varied',6,{0:varied,1:x},{2:vi.int(),3:vp,4:x[:,None,:].expand(-1,10,-1).clone(),5:vr,6:vd},W=512,E=10)
    iq,keys=rnd(4,128),rnd(4,128);selected=ref.select(iq,keys,10,budget=4)
    add('select-pruned-tail',11,{0:iq[None,:],1:keys},{2:selected.int()[None,:]},capacity=16,budget=4,pos=10)
    logits[0,9]=float('nan')
    try:ref.route(logits);raise AssertionError('reference accepted NaN')
    except ValueError:pass
    empty={slot:torch.zeros_like(value) for slot,value in rout.items()}
    add('route-nan',6,{0:logits,1:x,**empty},{**empty,15:torch.tensor([0,1,1],dtype=torch.int32)},W=512,E=10)
    # Existing completed pools are preserved. Only group1 becomes complete at pos7.
    pos=7;cap=16;k,v,rawkey=rnd(1,2,256),rnd(1,2,256),rnd(1,128);kw=rnd(128)
    oldk,oldv,oldraw=rnd(cap,2,256),rnd(cap,2,256),rnd(cap,128)
    allk,allv,allraw=oldk.clone(),oldv.clone(),oldraw.clone();allk[pos]=k[0];allv[pos]=v[0];allraw[pos]=rawkey[0]
    prior=zeros(cap//4,128);oldpool=ref.compress(oldraw[:pos]);prior[:len(oldpool)]=ref.rope(ref.norm(oldpool[:,None,:],kw),torch.arange(len(oldpool))*4)[:,0,:]
    expected=prior.clone();newpool=ref.compress(allraw[:pos+1]);expected[:len(newpool)]=ref.rope(ref.norm(newpool[:,None,:],kw),torch.arange(len(newpool))*4)[:,0,:]
    args={0:k,1:v,2:rawkey,3:kw,4:oldk,5:oldv,6:oldraw,7:prior}
    outs={4:allk,5:allv,6:allraw,7:expected}
    add('pool-existing',10,args,outs,pos=pos,capacity=cap)
    add('pool-inactive',10,args,outs,pos=pos,capacity=cap,active=0)
    (out/'cases.txt').write_text(''.join(c['name']+'\n' for c in cases))
    m=dict(schema='own-runtime.packet15.fixtures.v1',device_executed=False,seed=1511,torch_version=torch.__version__,cpu_capability=torch.backends.cpu.get_cpu_capability(),reference_sha256=sha(HERE.parent.parent/'packet1b/reference.py'),cases=cases)
    (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');return m
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if os.getpriority(os.PRIO_PROCESS,0)!=19 or os.environ.get('OMP_NUM_THREADS')!='2':raise SystemExit('nice19 / OMP_NUM_THREADS=2 required')
    print(json.dumps(generate(a.output),indent=2))
