"""Independent NumPy oracle for packet3 synthetic host orchestration.

No model payload, accelerator library or device entry point. Scalars use the
host C libm float functions also used by the C++ mock: this isolates reduction
and BF16 boundaries from platform transcendental-library differences. That is
an explicit host oracle contract, not a claim of device arithmetic parity.
"""
import argparse
import ctypes
import ctypes.util
import json
from pathlib import Path
import numpy as np

F = np.float32
_libm = ctypes.CDLL(ctypes.util.find_library('m'))
for _name in ('expf', 'logf', 'sqrtf', 'sinf', 'cosf', 'powf'):
    _fn = getattr(_libm, _name)
    _fn.argtypes = [ctypes.c_float] * (2 if _name == 'powf' else 1)
    _fn.restype = ctypes.c_float


def unary(name, x):
    a = np.asarray(x, dtype=np.float32)
    return np.fromiter((getattr(_libm, name)(float(v)) for v in a.flat), dtype=np.float32,
                       count=a.size).reshape(a.shape)


def exp(x): return unary('expf', x)
def log(x): return unary('logf', x)
def sqrt(x): return unary('sqrtf', x)
def sigmoid(x): return F(1) / (F(1) + exp(-np.asarray(x, dtype=np.float32)))
def silu(x): return np.asarray(x, dtype=np.float32) * sigmoid(x)


def bf(x):
    """BF16 RNE then widen exactly; NaNs remain quiet NaNs."""
    x = np.asarray(x, dtype=np.float32)
    u = x.view(np.uint32)
    rounded = (u + np.uint32(0x7fff) + ((u >> 16) & 1)) & np.uint32(0xffff0000)
    rounded = np.where((u & 0x7fffffff) > 0x7f800000, (u | np.uint32(0x00400000)) & np.uint32(0xffff0000), rounded)
    return rounded.astype(np.uint32).view(np.float32)


def tree(x):
    x = np.asarray(x, dtype=np.float32)
    if not x.shape[-1]: raise ValueError('empty reduction')
    while x.shape[-1] > 1:
        if x.shape[-1] % 2:
            x = np.concatenate((x, np.zeros_like(x[..., :1])), axis=-1)
        x = x[..., ::2] + x[..., 1::2]
    return x[..., 0]


def dot_gdn(x, y):
    """Real K128: 32 lanes, four consecutive products then tree32.

    Mini D4 uses the adjacent tree over its four products.
    """
    p = np.asarray(x, dtype=np.float32) * np.asarray(y, dtype=np.float32)
    if p.shape[-1] not in (4, 128): raise ValueError('fixture GDN width')
    if p.shape[-1] == 4:
        return tree(p)
    lanes = np.zeros((*p.shape[:-1], 32), dtype=np.float32)
    for j in range(4):
        lanes[..., :p.shape[-1] // 4] += p[..., j::4]
    return tree(lanes)


def weight(name, rows, cols, expert=0):
    r = np.arange(rows, dtype=np.int64)[:, None]
    k = np.arange(cols, dtype=np.int64)[None, :]
    return (((k * 3 + (r % 4) * 5 + sum(name.encode()) + expert * 7) % 17) - 8).astype(np.float32) / F(512)


def control(name, n): return weight(name, 1, n)[0]


def linear(x, name, rows, expert=0):
    """Packet2 order: 32 strided lanes; adjacent tree32; BF16 store.

    The fixture repeats each four output rows. Evaluate each distinct row once;
    this changes no product or reduction, and makes real-shape CPU tests small.
    """
    x = np.asarray(x, dtype=np.float32)
    w = weight(name, min(rows, 4), x.shape[-1], expert)
    lane = np.zeros((*x.shape[:-1], len(w), 32), dtype=np.float32)
    for begin in range(0, x.shape[-1], 32):
        width = min(32, x.shape[-1] - begin)
        lane[..., :width] += x[..., None, begin:begin+width] * w[:, begin:begin+width]
    y = bf(tree(lane))
    return y[..., np.arange(rows) % len(w)]


def norm(x, name, unit=True, rounded=True):
    x = np.asarray(x, dtype=np.float32)
    var = tree(x * x)[..., None] / F(x.shape[-1])
    out = (x * (F(1) / sqrt(var + F(1e-6)))) * (control(name, x.shape[-1]) + F(unit))
    return bf(out) if rounded else out


def recurrence(q, k, v, a, b, alog, dt, state):
    q = q / sqrt(dot_gdn(q, q)[..., None] + F(1e-6)) / sqrt(F(q.shape[-1]))
    k = k / sqrt(dot_gdn(k, k)[..., None] + F(1e-6))
    repeat = len(v) // len(q)
    q, k = np.repeat(q, repeat, axis=0), np.repeat(k, repeat, axis=0)
    gate = a + dt
    sp = gate.copy()
    mask = gate < F(20)
    sp[mask] = log(F(1) + exp(gate[mask]))
    decay = exp(-exp(alog) * sp)
    decayed = state * decay[:, None, None]
    delta = (v - dot_gdn(decayed, k[:, None, :])) * sigmoid(b)[:, None]
    updated = decayed + delta[:, :, None] * k[:, None, :]
    return bf(dot_gdn(updated, q[:, None, :])), bf(updated)


def grouped_norm(x, name):
    x = np.asarray(x, dtype=np.float32)
    var = tree(x * x)[..., None] / F(x.shape[-1])
    w = control(name, x.size).reshape(x.shape)
    return bf(x * (F(1) / sqrt(var + F(1e-6))) * (w + F(1)))


def hc_combine(streams, branch, injection):
    return bf(streams + branch[None, :] * (F(2) * sigmoid(injection / F(4)))[:, None])


def rope(x, position, rotary):
    x = np.asarray(x, dtype=np.float32)
    freq = np.array([_libm.powf(F(1e7), F(-2 * j / rotary)) for j in range(rotary // 2)], dtype=np.float32)
    theta = F(position) * freq
    c, s = bf(unary('cosf', theta)), bf(unary('sinf', theta))
    a, b = x[..., :rotary // 2], x[..., rotary // 2:rotary]
    return np.concatenate((bf(a * c - b * s), bf(b * c + a * s), x[..., rotary:]), axis=-1)


class Reference:
    """Straightforward CPU graph with every materialized buffer retained."""
    def __init__(self, real=False):
        self.real = real
        self.h, self.low, self.experts, self.mid = (2560, 320, 512, 640) if real else (16, 4, 16, 8)
        self.kh, self.vh, self.d = (16, 48, 128) if real else (1, 3, 4)
        self.buffers = {'token': np.zeros(1, np.float32), 'position': np.zeros(1, np.float32),
                        'active': np.ones(1, np.float32), 'error': np.zeros(1, np.float32),
                        'next_token': np.zeros(1, np.float32)}
        self.buffers['token_history'] = np.full(2, 248044 if real else 15, np.float32)
        if not real:
            self.buffers['ple_metadata'] = np.asarray([3,5,7]+[17]*16+[17*i for i in range(16)],np.float32)
        self.position = 0
        self.past = [15, 15]

    def save(self, name, value):
        self.buffers[name] = np.asarray(value, np.float32).copy()
        return self.buffers[name]

    def lin(self, x, name, rows, dest, expert=0):
        return self.save(dest, linear(x, name, rows, expert))

    def hc(self, streams, prefix, tag, inject=True):
        n = self.save(tag+'.norm', grouped_norm(streams, prefix+'norm.weight'))
        lo = self.lin(n.reshape(-1), prefix+'down.weight', self.low, tag+'.low')
        act = self.save(tag+'.act', bf(silu(lo/F(4))))
        gate = self.lin(act, prefix+'up.weight', self.h*4, tag+'.gate').reshape(4, self.h)
        acc = np.zeros(self.h, np.float32)
        for i in range(4): acc = acc + sigmoid(gate[i])*n[i]
        mixed = self.save(tag+'.mix', bf(acc/F(4)))
        inj = self.lin(n.reshape(-1), prefix+'inject.weight', 4, tag+'.inject') if inject else None
        return mixed, inj

    def gdn(self, x, prefix):
        tag = prefix+'gdn.'
        ch=(2*self.kh+self.vh)*self.d
        qkv=self.lin(x,prefix+'attn_qkv.weight',ch,tag+'qkv')
        z=self.lin(x,prefix+'attn_gate.weight',self.vh*self.d,tag+'z').reshape(self.vh,self.d)
        a=self.lin(x,prefix+'ssm_alpha.weight',self.vh,tag+'a')
        b=self.lin(x,prefix+'ssm_beta.weight',self.vh,tag+'b')
        history=self.buffers.get(tag+'history',np.zeros((ch,3),np.float32))
        window=np.concatenate((history,qkv[:,None]),axis=1)
        w=weight(prefix+'ssm_conv1d.weight',ch,4)
        acc=np.zeros(ch,np.float32)
        for tap in range(4): acc=acc+window[:,tap]*w[:,tap]
        conv=self.save(tag+'conv',bf(silu(acc)))
        self.save(tag+'history',window[:,1:])
        q,k,v=np.split(conv,[self.kh*self.d,2*self.kh*self.d])
        state=self.buffers.get(tag+'state',np.zeros((self.vh,self.d,self.d),np.float32))
        y,state=recurrence(q.reshape(self.kh,self.d),k.reshape(self.kh,self.d),v.reshape(self.vh,self.d),a,b,
                           control(prefix+'ssm_a',self.vh),control(prefix+'ssm_dt.bias',self.vh),state)
        self.save(tag+'y',y);self.save(tag+'state',state)
        gated=self.save(tag+'gated',bf(norm(y,prefix+'ssm_norm.weight',False,False)*sigmoid(z)))
        return self.lin(gated.reshape(-1),prefix+'ssm_out.weight',self.h,prefix+'attention')

    def moe(self,x,prefix):
        router=self.lin(x,prefix+'ffn_gate_inp.weight',self.experts,prefix+'router')
        ee=exp(router-router.max());p=ee/tree(ee)
        ids=np.argsort(-p,kind='stable')[:10];p=p[ids];p=p/tree(p)
        self.save(prefix+'ids',ids);self.save(prefix+'prob',p)
        self.save(prefix+'routes',np.stack((ids,np.zeros(10),np.full(10,self.mid)),axis=1))
        self.save(prefix+'routes.down',np.stack((ids,np.zeros(10),np.full(10,self.h)),axis=1))
        self.save(prefix+'expert_input',np.tile(x,(10,1)))
        for name in ('expsgate.status','expsup.status','expsdown.status'):
            self.save(prefix+name,np.zeros(10,np.float32))
        results={}
        for suffix,eids in [('exps',ids),('shexp',[0])]:
            gs=[];us=[];acts=[];outs=[]
            for e in eids:
                gs.append(linear(x,prefix+'ffn_gate_'+suffix+'.weight',self.mid,int(e)))
                us.append(linear(x,prefix+'ffn_up_'+suffix+'.weight',self.mid,int(e)))
                acts.append(bf(silu(gs[-1])*us[-1]))
                outs.append(linear(acts[-1],prefix+'ffn_down_'+suffix+'.weight',self.h,int(e)))
            for dest,values in [('gate',gs),('up',us),('act',acts),('down',outs)]: self.save(prefix+suffix+dest,values)
            results[suffix]=np.asarray(outs)
        gate=self.lin(x,prefix+'ffn_gate_inp_shexp.weight',1,prefix+'shared_gate')
        acc=np.zeros(self.h,np.float32)
        for i in range(10):acc=acc+results['exps'][i]*p[i]
        out=bf(bf(acc)+bf(results['shexp'][0]*sigmoid(gate)))
        return self.save(prefix+'moe',out)

    def ple(self,streams,token,prefix):
        t=prefix+'ple.'
        old=self.past[:]
        if 15 in old:
            last=1-old[::-1].index(15);old=[15]*(last+1)+old[last+1:]
        order=[token,old[-1],old[-2]];ids=[]
        for n in (2,3):
            mixed=0
            for j in range(n):mixed^=order[j]*(3,5,7)[j]
            ids.extend(mixed%17+17*h for h in range((n-2)*8,(n-1)*8))
        self.past=[self.past[-1],token]
        self.save(t+'ids',ids);self.save('token_history',self.past)
        lookup=np.concatenate([bf(weight('per_layer_token_embd.weight',row+1,self.h//16)[row]) for row in ids])
        self.save(t+'lookup',lookup)
        key=self.lin(lookup,prefix+'ple_key.weight',4*self.h,t+'key').reshape(4,self.h)
        value=self.lin(lookup,prefix+'ple_value.weight',self.h,t+'value')
        key=self.save(t+'kn',grouped_norm(key,prefix+'ple_norm_key.weight'))
        query=self.save(t+'qn',grouped_norm(streams,prefix+'ple_norm_query.weight'))
        gate=bf(bf(tree(bf(key*query)))/sqrt(F(self.h)))
        gate=bf(sigmoid(bf(np.sign(gate)*bf(sqrt(np.maximum(np.abs(gate),F(1e-6)))))))
        gated=self.save(t+'gated',bf(gate[:,None]*value[None,:]))
        cn=self.save(t+'cn',grouped_norm(gated,prefix+'ple_norm_conv.weight')).reshape(-1)
        history=self.buffers.get(t+'history',np.zeros((4*self.h,9),np.float32))
        window=np.concatenate((history,cn[:,None]),axis=1)
        w=weight(prefix+'ple_conv1d.weight',4*self.h,4);acc=np.zeros(4*self.h,np.float32)
        for tap in range(4):acc=acc+window[:,tap*3]*w[:,tap]
        conv=self.save(t+'conv',bf(silu(bf(acc)))).reshape(4,self.h)
        self.save(t+'history',window[:,1:])
        return bf(streams+bf(gated+conv))

    def qsa(self,x,prefix):
        t=prefix+'qsa.';d=4;heads=4;pos=self.position
        qgate=self.lin(x,prefix+'attn_q.weight',32,t+'qgate').reshape(heads,8)
        k=self.lin(x,prefix+'attn_k.weight',4,t+'k').reshape(1,d)
        v=self.lin(x,prefix+'attn_v.weight',4,t+'v').reshape(1,d)
        iq=self.lin(x,prefix+'indexer.q_proj.weight',16,t+'iq').reshape(4,d)
        ik=self.lin(x,prefix+'indexer.k_proj.weight',4,t+'ik')
        q=self.save(t+'q',rope(norm(qgate[:,:d],prefix+'attn_q_norm.weight'),pos,2))
        gate=self.save(t+'gate',qgate[:,d:])
        kn=self.save(t+'kn',rope(norm(k,prefix+'attn_k_norm.weight'),pos,2))
        iqn=self.save(t+'iqn',rope(norm(iq,prefix+'indexer.q_norm.weight'),pos,2))
        keys=self.buffers.get(t+'keys',np.zeros((8,1,d),np.float32)).copy()
        values=self.buffers.get(t+'values',np.zeros((8,1,d),np.float32)).copy()
        raw=self.buffers.get(t+'raw',np.zeros((8,d),np.float32)).copy()
        keys[pos]=kn;values[pos]=v;raw[pos]=ik
        self.save(t+'keys',keys);self.save(t+'values',values);self.save(t+'raw',raw)
        pooled=np.zeros((2,d),np.float32)
        for block in range((pos+1)//4):
            total=np.zeros(d,np.float32)
            for j in range(4):total=total+raw[block*4+j]
            pooled[block]=rope(norm(bf(total/F(4)),prefix+'indexer.k_norm.weight'),block*4,2)
        self.save(t+'pooled',pooled)
        scores=np.zeros((pos+1)//4,np.float32)
        for h in range(4):scores=scores+np.maximum(tree(pooled[:len(scores)]*iqn[h]),F(0))
        scores=scores/sqrt(F(d));blocks=np.argsort(-scores,kind='stable')[:2]
        ids=[int(block)*4+j for block in blocks for j in range(4)];ids.extend(range(len(scores)*4,pos+1))
        padded=np.full(11,-1,np.float32);padded[:len(ids)]=ids;self.save(t+'ids',padded)
        ks,vs=np.repeat(keys[ids],4,axis=1),np.repeat(values[ids],4,axis=1)
        scores=tree(ks*q[None,:,:])/sqrt(F(d));ee=exp(scores-scores.max(axis=0,keepdims=True))
        prob=ee/tree(ee.T)[None,:]
        y=bf(tree((prob[:,:,None]*vs).transpose(1,2,0)))
        y=self.save(t+'y',bf(y*sigmoid(gate)))
        return self.lin(y.reshape(-1),prefix+'attn_output.weight',self.h,prefix+'attention')

    def step(self, token):
        self.save('token',[token]);self.save('error',[0])
        embedding=self.save('embedding',bf(weight('token_embd.weight',token+1,self.h)[token]))
        streams=np.tile(embedding,(4,1))
        for layer in range(1 if self.real else 2):
            prefix=f'blk.{layer}.'
            if layer==1:streams=self.ple(streams,token,prefix)
            x,inj=self.hc(streams,prefix+'hc_attn_',prefix+'hc.a')
            attn=self.gdn(x,prefix) if layer==0 else self.qsa(x,prefix)
            streams=hc_combine(streams,attn,inj)
            x,inj=self.hc(streams,prefix+'hc_ffn_',prefix+'hc.f')
            streams=hc_combine(streams,self.moe(x,prefix),inj)
        self.save('streams',streams)
        if not self.real:
            mixed,_=self.hc(streams,'output_hc_','final',False)
            logits=self.lin(mixed,'output.weight',16,'logits')
            self.save('next_token',[int(np.argmax(logits))])
        self.position+=1;self.save('position',[self.position])


def run(real=False):
    ref=Reference(real)
    for token in [2,5,3,7,1]:ref.step(token)
    return {name:value.reshape(-1) for name,value in ref.buffers.items()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--real',action='store_true')
    parser.add_argument('--compare',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    actual=run(args.real)
    encoded={k:v.view(np.uint32).tolist() for k,v in sorted(actual.items())}
    if args.output:args.output.write_text(json.dumps(encoded))
    if args.compare:
        expected=json.loads(args.compare.read_text())
        failures=[]
        for k in sorted(set(expected)|set(encoded)):
            if k not in expected or k not in encoded:failures.append((k,'missing'));continue
            a=np.array(encoded[k],np.uint32);b=np.array(expected[k],np.uint32)
            if a.shape!=b.shape:failures.append((k,('shape',a.shape,b.shape)));continue
            mismatch=np.flatnonzero(a!=b)
            if len(mismatch):
                i=int(mismatch[0]);failures.append((k,{'count':len(mismatch),'index':i,'numpy_bits':int(a[i]),'cpp_bits':int(b[i]),'numpy':float(a.view(np.float32)[i]),'cpp':float(b.view(np.float32)[i])}))
        if failures:
            print(json.dumps({'passed':False,'failures':failures},indent=2));raise SystemExit(1)
        print(json.dumps({'passed':True,'buffers':len(encoded),'values':sum(map(len,encoded.values())),'arithmetic':'FP32 bit-exact; BF16 RNE boundaries bit-exact','real':args.real}))
    else:print(json.dumps({'buffers':len(encoded),'values':sum(map(len,encoded.values())),'real':args.real}))


if __name__=='__main__':main()
