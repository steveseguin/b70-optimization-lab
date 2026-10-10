"""Independent Flash-Next CPU mathematical reference, NOT certified arithmetic.

See README source keys S1-S6 and UNVERIFIED U1-U7. No runtime is imported.
All persistent floating state is BF16. Operations widen to FP32, and each
explicit .to(BF16) is a rounding boundary. No compilation/autocast/device APIs.
"""
from dataclasses import dataclass
import math
import torch

BF16, F32, FP8 = torch.bfloat16, torch.float32, torch.float8_e4m3fn


def cpu(*xs):
    if any(x.device.type != 'cpu' for x in xs):
        raise ValueError('CPU tensors only')


def tree(x):
    """Adjacent-pair FP32 tree, zero-pad odd widths. Device tree is U1."""
    cpu(x)
    x = x.float()
    if x.shape[-1] == 0:
        raise ValueError('empty reduction')
    while x.shape[-1] > 1:
        if x.shape[-1] % 2:
            x = torch.cat((x, torch.zeros_like(x[..., :1])), -1)
        x = x[..., ::2] + x[..., 1::2]
    return x.squeeze(-1)


def dot128(x, y):
    """32 key lanes, four ascending products per lane; then fixed CPU tree."""
    cpu(x, y)
    x, y = torch.broadcast_tensors(x.float(), y.float())
    if x.shape[-1] != 128:
        raise ValueError('GDN K128')
    z = (x*y).reshape(*x.shape[:-1], 32, 4)
    s = torch.zeros_like(z[..., 0])
    for i in range(4):
        s = s + z[..., i]
    return tree(s)


def norm(x, w, unit=True, out=BF16):
    cpu(x, w)
    if w.shape != x.shape[-1:]:
        raise ValueError('norm shape')
    v = tree(x.float().square()).unsqueeze(-1) / x.shape[-1]
    return (x.float()*torch.rsqrt(v+1e-6)*(w.float()+int(unit))).to(out)


def silu(x):
    cpu(x)
    return x.float()*torch.sigmoid(x.float())


@dataclass
class Linear:
    """BF16 matrix, or E4M3 with BF16 block128 scales; output BF16.

    FP8 dequant rounds BF16 before FP32 CPU dot. This mathematical surrogate
    does NOT reproduce certified Triton activation quantization/reduction (U2).
    Output tiles bound temporary storage even for expanded synthetic weights.
    """
    weight: torch.Tensor
    scales: torch.Tensor | None = None

    def __post_init__(self):
        cpu(self.weight)
        if self.weight.ndim != 2 or min(self.weight.shape) < 1:
            raise ValueError('matrix required')
        if self.scales is None:
            if self.weight.dtype != BF16:
                raise ValueError('BF16 weight required')
        else:
            cpu(self.scales)
            n, k = self.weight.shape
            if self.weight.dtype != FP8 or self.scales.dtype != BF16 or self.scales.shape != ((n+127)//128, (k+127)//128):
                raise ValueError('FP8 block scale shape/type')

    def __call__(self, x):
        cpu(x)
        if x.dtype != BF16 or x.shape[-1] != self.weight.shape[1]:
            raise ValueError('BF16 matching linear input')
        ys = []
        for start in range(0, self.weight.shape[0], 128):
            w = self.weight[start:start+128].float()
            if self.scales is not None:
                scale = self.scales[start//128].float().repeat_interleave(128)[:w.shape[1]]
                w = (w*scale).to(BF16).float()
            ys.append((x.float() @ w.T).to(BF16))
        return torch.cat(ys, -1)


def conv(x, history, w):
    cpu(x, history, w)
    if history.shape != (x.numel(), 3) or w.shape != (x.numel(), 1, 4):
        raise ValueError('width4 conv')
    window = torch.cat((history, x[:, None]), -1)
    acc = torch.zeros_like(x, dtype=F32)
    for tap in range(4):
        acc = acc + window[:, tap].float()*w[:, 0, tap].float()
    return silu(acc).to(BF16), window[:, 1:].clone()


def recurrence(q, k, v, a, b, alog, dt, state):
    """S1 serial dependency; output before BF16 state store on EVERY row.

    Normalize Q/K; Q/sqrt(K); decay state; prediction; beta correction;
    outer-product update; output dot; BF16 state commit. U1 covers FMA/tree.
    """
    cpu(q, k, v, a, b, alog, dt, state)
    t = q.shape[0]
    if q.shape != (t,16,128) or k.shape != q.shape or v.shape != (t,48,128) or a.shape != (t,48) or b.shape != a.shape or state.shape != (48,128,128) or alog.shape != (48,) or dt.shape != (48,):
        raise ValueError('Flash GDN shape')
    if any(z.dtype != BF16 for z in (q,k,v,a,b,alog,dt,state)):
        raise ValueError('Flash BF16 operands/state')
    s, ys = state.clone(), []
    for i in range(t):
        qr, kr = q[i].float(), k[i].float()
        qr = qr/torch.sqrt(dot128(qr,qr)[:,None]+1e-6)/math.sqrt(128)
        kr = kr/torch.sqrt(dot128(kr,kr)[:,None]+1e-6)
        qr, kr = qr.repeat_interleave(3,0), kr.repeat_interleave(3,0)
        gate = a[i].float()+dt.float()
        sp = gate.clone()
        mask = gate < 20
        sp[mask] = torch.log(1+torch.exp(gate[mask]))
        decay = torch.exp(-torch.exp(alog.float())*sp)
        decayed = s.float()*decay[:,None,None]
        delta = (v[i].float()-dot128(decayed,kr[:,None,:]))*torch.sigmoid(b[i].float())[:,None]
        updated = decayed+delta[:,:,None]*kr[:,None,:]
        ys.append(dot128(updated,qr[:,None,:]).to(BF16))
        s = updated.to(BF16)
    return torch.stack(ys), s


def gdn(x, w, history, state):
    qkv, z = w['qkv'](x), w['z'](x).reshape(-1,48,128)
    rows = []
    for row in qkv:
        y, history = conv(row,history,w['conv']); rows.append(y)
    q,k,v = torch.stack(rows).split([2048,2048,6144],-1)
    y,state = recurrence(q.reshape(-1,16,128),k.reshape(-1,16,128),v.reshape(-1,48,128),w['a'](x),w['b'](x),w['alog'],w['dt'],state)
    y = norm(y,w['norm'],unit=False,out=F32)*silu(z)
    return w['out'](y.to(BF16).flatten(1)),history,state


def rope(x, positions, rotary=64):
    """Text positions only; split-half rotate, BF16 trig tables (U3)."""
    cpu(x,positions)
    angle = positions.float()[:,None] * (1e7**(-torch.arange(0,rotary,2,dtype=F32)/rotary))[None,:]
    c,s = angle.cos().to(BF16).float()[:,None,:],angle.sin().to(BF16).float()[:,None,:]
    a,b = x[...,:rotary//2].float(),x[...,rotary//2:rotary].float()
    return torch.cat(((a*c-b*s).to(BF16),(b*c+a*s).to(BF16),x[...,rotary:]),-1)


def compress(raw):
    """S2: four chronological raw keys -> FP32 mean -> BF16; omit tail."""
    cpu(raw)
    if raw.ndim != 2 or raw.shape[1] != 128 or raw.dtype != BF16:
        raise ValueError('raw index keys [T,128] BF16')
    count = raw.shape[0]//4
    s = torch.zeros((count,128),dtype=F32)
    for i in range(4):
        s = s+raw[i:count*4:4].float()
    return (s/4).to(BF16)


def select(q, keys, position, budget=2048):
    """S2: head-order ReLU dot sum/sqrt128; stable descending blocks; tail.

    Return budget+3 slots, -1 padded. QSA compression is architecture-defined
    pooling, NOT reduced KV precision; actual attention K/V remain BF16.
    """
    cpu(q,keys)
    if q.shape != (4,128) or keys.shape[1:] != (128,) or budget < 4 or budget%4 or position < 0:
        raise ValueError('indexer geometry')
    n = (position+1)//4
    if len(keys)<n:
        raise ValueError('missing complete groups')
    scores = torch.zeros(n,dtype=F32)
    for h in range(4):
        scores = scores+tree(keys[:n].float()*q[h].float()).clamp_min(0)
    scores = scores/math.sqrt(128)
    blocks = torch.argsort(scores,descending=True,stable=True)[:budget//4]
    ids = [int(b)*4+j for b in blocks for j in range(4)]
    ids += list(range(n*4,position+1))
    out = torch.full((budget+3,),-1,dtype=torch.int64)
    out[:len(ids)] = torch.tensor(ids,dtype=torch.int64)
    return out


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
        y=(y.float()*torch.sigmoid(gate[0].float())).to(BF16)
        outputs.append(w['out'](y.reshape(1,6144)))
    return torch.cat(outputs), (keys,values,raw)


def route(logits, top=10):
    """S3 softmax then top10 renormalization. Tie order is CPU choice U4."""
    cpu(logits)
    if logits.ndim != 2 or logits.shape[1]<top or not torch.isfinite(logits).all():
        raise ValueError('finite routing logits and enough experts required')
    v=logits.float()
    e=torch.exp(v-v.max(-1,keepdim=True).values)
    p=e/tree(e)[:,None]
    ids=torch.argsort(p,descending=True,stable=True)[:,:top]
    p=p.gather(1,ids)
    return ids,p/tree(p)[:,None]


def ffn(x,w):
    return w['down']((silu(w['gate'](x))*w['up'](x).float()).to(BF16))


def moe(x,router,experts,shared,shared_gate):
    """Logical top10 order, weight after down, FP32 ordered sum -> BF16.

    Experts is an ID->weights callback; missing IDs fail, never prune/fallback.
    Add sigmoid-gated shared BF16 expert. Device quant/reduce parity U2/U4.
    """
    ids,prob=route(router(x))
    rows=[]
    for r in range(len(x)):
        acc=torch.zeros(x.shape[1],dtype=F32)
        for j,e in enumerate(ids[r]):
            y=ffn(x[r:r+1],experts(int(e)))[0]
            acc=acc+y.float()*prob[r,j]
        rows.append(acc.to(BF16))
    routed=torch.stack(rows)
    sh=(ffn(x,shared).float()*torch.sigmoid(shared_gate(x).float())).to(BF16)
    return (routed.float()+sh.float()).to(BF16),ids,prob


def hc_mix(streams,w):
    """S4: stream norm; down/4 -> SiLU -> up -> sigmoid, mean in stream order."""
    cpu(streams)
    if streams.shape[-2:] != (4,2560):
        raise ValueError('four HC streams H2560')
    xn=torch.stack([norm(streams[:,i],w['norm'][i]) for i in range(4)],1)
    flat=xn.flatten(1)
    low=silu(w['down'](flat).float()/4).to(BF16)
    gate=w['up'](low).reshape_as(streams)
    acc=torch.zeros_like(streams[:,0],dtype=F32)
    for i in range(4):
        acc=acc+torch.sigmoid(gate[:,i].float())*xn[:,i].float()
    inj=w['inject'](flat) if 'inject' in w else None
    return (acc/4).to(BF16),inj


def hc_combine(streams,branch,inj):
    cpu(streams,branch,inj)
    return (streams.float()+branch.float()[:,None,:]*(2*torch.sigmoid(inj.float()/4))[:,:,None]).to(BF16)


def ple_ids(tokens,history,multipliers,sizes,offsets,eos=248044):
    """S5 int64 multiply/XOR, positive remainder; EOS resets preceding history.

    Caller supplies authenticated checkpoint hash metadata later (U6); this
    packet uses synthetic values. History is oldest first, length two.
    """
    if len(history)!=2 or len(multipliers)!=3 or len(sizes)!=16 or len(offsets)!=16 or min(sizes)<=0:
        raise ValueError('PLE metadata geometry')
    def signed(v):
        v &= (1<<64)-1
        return v-(1<<64) if v >= 1<<63 else v
    past=list(history); rows=[]
    for token in tokens:
        old=past[-2:]
        if eos in old:
            last=len(old)-1-old[::-1].index(eos)
            old=[eos]*(last+1)+old[last+1:]
        order=[int(token),old[-1],old[-2]]
        hashes=[]
        for n in (2,3):
            mixed=0
            for j in range(n): mixed=signed(mixed ^ signed(order[j]*int(multipliers[j])))
            hashes.extend(mixed%int(sizes[h])+int(offsets[h]) for h in range((n-2)*8,(n-1)*8))
        rows.append(hashes); past.append(int(token))
    return torch.tensor(rows,dtype=torch.int64),past[-2:]


def ple_lookup(layer,ids,row_reader,scale):
    """Only layers.1: 16 FP8 rows -> BF16 -> scale -> BF16, flatten H2560.

    row_reader(partition,row) must return CPU E4M3[160]. No file I/O here.
    Partition geometry is the packet1 contract; unknown payloads never read.
    """
    cpu(ids,scale)
    if layer!=1 or ids.ndim!=2 or ids.shape[1]!=16 or (ids<0).any() or (ids>=320001536).any() or scale.numel()!=1 or scale.dtype!=BF16:
        raise ValueError('PLE layers.1 and physical row bounds')
    out=[]
    for row in ids:
        gathered=[]
        for idx in row:
            part,local=divmod(int(idx),2500012)
            v=row_reader(part,local); cpu(v)
            if v.shape!=(160,) or v.dtype!=FP8: raise ValueError('FP8 row required')
            gathered.append((v.to(BF16).float()*scale.float()).to(BF16))
        out.append(torch.cat(gathered))
    return torch.stack(out)


def layer(streams,attn,mlp,attn_hc,mlp_hc):
    """Materialized version of S4 delayed combine; no PLE in MTP layer."""
    x,inj=hc_mix(streams,attn_hc)
    streams=hc_combine(streams,attn(x),inj)
    x,inj=hc_mix(streams,mlp_hc)
    return hc_combine(streams,mlp(x),inj)


def mtp(embedding,streams,w,block):
    """S6: separate pre-norm/projections; broadcast add; QSA/MoE/HC block;
    final HC mixer and shared full head. No proposal acceptance implemented.
    """
    e=w['embed'](norm(embedding,w['enorm']))
    h=norm(streams.flatten(1),w['hnorm']).reshape_as(streams)
    h=w['hidden'](h)
    merged=(h.float()+e.float()[:,None,:]).to(BF16)
    multi=block(merged)
    sample,_=hc_mix(multi,w['mixer'])
    return w['head'](sample),multi
