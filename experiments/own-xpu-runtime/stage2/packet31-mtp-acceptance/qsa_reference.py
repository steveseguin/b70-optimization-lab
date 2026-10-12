"""Lab packet2 QSA, corrected to official BF16 gate and RoPE formulas."""
import torch
from reference_gguf import cpu, norm, tree, compress, select, BF16, F32

def rope(x, positions, rotary=64):
    """Text positions only; split-half rotate, BF16 trig tables (U3)."""
    cpu(x,positions)
    angle = positions.float()[:,None] * (1/(1e7**(torch.arange(0,rotary,2,dtype=F32)/rotary)))[None,:]
    c,s = angle.cos().to(BF16).float()[:,None,:],angle.sin().to(BF16).float()[:,None,:]
    a,b = x[...,:rotary//2].float(),x[...,rotary//2:rotary].float()
    return torch.cat(((a*c-b*s).to(BF16),(b*c+a*s).to(BF16),x[...,rotary:]),-1)


def qsa(x,w,past):
    """Full-shaped single-request text QSA: serial rows, BF16 KV and raw keys.

    past=(K[T,2,256],V[T,2,256],raw[T,128]); never mutate caller state.
    CPU attention uses selected-order FP32 softmax/PV; split-K parity U3.
    """
    cpu(x,*past)
    keys,values,raw = [v.clone() for v in past]
    if keys.shape != (len(raw),2,256) or values.shape != keys.shape or raw.shape != (len(raw),128) or any(v.dtype != BF16 for v in past):
        raise ValueError('QSA cache shape/dtype')
    outputs=[]
    for row in x.split(1):
        pos=torch.tensor([len(raw)])
        q,gate=w['q'](row).reshape(1,24,512).split(256,-1)
        q=rope(norm(q,w['qn']),pos)
        k=rope(norm(w['k'](row).reshape(1,2,256),w['kn']),pos)
        v=w['v'](row).reshape(1,2,256)
        iq,ik=w['index'](row).split([512,128],-1)
        iq=rope(norm(iq.reshape(1,4,128),w['iqn']),pos)[0]
        raw=torch.cat((raw,ik),0)
        pooled=compress(raw)
        ck=rope(norm(pooled[:,None,:],w['ikn']),torch.arange(len(pooled))*4)[:,0,:]
        ids=select(iq,ck,int(pos[0])); ids=ids[ids>=0]
        keys=torch.cat((keys,k),0); values=torch.cat((values,v),0)
        ks=keys[ids].repeat_interleave(12,1).float()
        vs=values[ids].repeat_interleave(12,1).float()
        score=tree(ks*q[0].float())/16
        exp=torch.exp(score-score.max(0).values)
        prob=exp/tree(exp.T)[None,:]
        y=tree((prob[:,:,None]*vs).permute(1,2,0)).to(BF16)
        y=(y.float()*torch.sigmoid(gate[0]).float()).to(BF16)
        outputs.append(w['out'](y.reshape(1,6144)))
    return torch.cat(outputs), (keys,values,raw)
