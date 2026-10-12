"""CPU MTP reference, official block-FP8/BF16 semantics, IQ3 shared bindings.

Derived from the lab packet2 reference; source review is in wiring-review.md.
CPU BLAS/transcendentals do not certify device reduction-bit parity.
"""
from pathlib import Path
import ctypes, hashlib, json, math, os, sys
import numpy as np
import torch
P=Path(__file__).resolve().parent; ROOT=P.parents[3]
LANE=ROOT/"experiments/qwen38-flash-next-ud-iq3xxs-b70"
sys.path.insert(0,str(LANE/"packet2-cpu-oracle"))
import reference_gguf as ref
import qsa_reference
from oracle import Store
sys.path.insert(0,str(LANE/"packet3-runtime-oracle"))
from linear import Library,Linear as IQLinear
BF=torch.bfloat16; FP8=torch.float8_e4m3fn
MODEL=Path("/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8")
def digest(b):return hashlib.sha256(b).hexdigest()
class SafeStore:
    def __init__(self):
        self.index=json.loads((MODEL/"model.safetensors.index.json").read_text())["weight_map"]
        self.headers={};self.receipt={};self.small={}
    def meta(self,name):
        file=self.index[name]
        if file not in self.headers:
            with (MODEL/file).open("rb") as f:
                n=int.from_bytes(f.read(8),"little");h=f.read(n)
            self.headers[file]=(8+n,json.loads(h),digest(h))
        base,h,hh=self.headers[file];return file,base,h[name],hh
    def read(self,name,start=0,rows=None):
        file,base,t,hh=self.meta(name);shape=t["shape"];width=math.prod(shape[1:])
        rows=shape[0] if rows is None else rows
        size={"BF16":2,"F8_E4M3":1,"F32":4}[t["dtype"]];rb=width*size
        assert 0<=start and start+rows<=shape[0]
        offset=base+t["data_offsets"][0]+start*rb
        with (MODEL/file).open("rb") as f:f.seek(offset);raw=f.read(rows*rb)
        assert len(raw)==rows*rb
        key=name if start==0 and rows==shape[0] else f"{name}[{start}:{start+rows}]"
        self.receipt[key]=dict(file=file,offset=offset,bytes=len(raw),sha256=digest(raw),header_sha256=hh,dtype=t["dtype"],shape=[rows,*shape[1:]])
        dtype={"BF16":BF,"F8_E4M3":FP8,"F32":torch.float32}[t["dtype"]]
        return torch.frombuffer(bytearray(raw),dtype=dtype).reshape(rows,*shape[1:])
    def weight(self,name):
        if name not in self.small:self.small[name]=self.read(name)
        return self.small[name]

def gemma(x,w):
    y=x.float()*torch.rsqrt(ref.tree(x.float().square()).unsqueeze(-1)/x.shape[-1]+1e-6)
    return (y*(1+w.float())).to(BF)
def hc_norm(x,w):
    y=x.float()*torch.rsqrt(ref.tree(x.float().square()).unsqueeze(-1)/x.shape[-1]+1e-6)
    return (y+y*w.float()).to(BF)
class Dense:
    def __init__(self,w):self.w=w
    def __call__(self,x):return (x.float()@self.w.float().T).to(BF)
def activation_quant(x):
    groups=x.float().reshape(*x.shape[:-1],-1,128)
    scales=groups.abs().amax(-1).clamp_min(1e-10)*(1.0/448)
    codes=(groups/scales[...,None]).clamp(-448,448).to(FP8).float()
    return codes,scales
class ExpertLinear:
    def __init__(self,store,name,expanded):
        self.w=store.read(name+".weight").float();self.sc=store.read(name+".weight_scale_inv").float()
        self.expanded=expanded
        if expanded:
            w=self.w*self.sc.repeat_interleave(128,0).repeat_interleave(128,1)
            groups=w.reshape(w.shape[0],-1,16)
            self.scale=groups.abs().amax(-1)/127
            self.scale=torch.where(self.scale==0,torch.ones_like(self.scale),self.scale)
            self.code=torch.round(groups/self.scale[...,None]).clamp(-127,127).to(torch.int8)
            self.w=(self.code.float()*self.scale[...,None]).reshape_as(w)
    def __call__(self,x,out=BF,prob=None):
        if self.expanded:y=x.float()@self.w.T
        else:
            q,sc=activation_quant(x);y=torch.zeros((*x.shape[:-1],self.w.shape[0]),dtype=torch.float32)
            for k in range(self.w.shape[1]//128):
                dot=q[...,k,:]@self.w[:,128*k:128*(k+1)].T
                y=y+(dot*sc[...,k,None])*self.sc[:,k].repeat_interleave(128)
        if prob is not None:y=y*prob
        return y.to(out)

class Draft:
    def __init__(self,s,expanded=False):
        self.s=s;self.expanded=expanded;self.prefix="mtp.layers.0."
        self.cache=(torch.empty((0,2,256),dtype=BF),torch.empty((0,2,256),dtype=BF),torch.empty((0,128),dtype=BF))
        self.position=0
        self.experts_seen=set()
    def dense(self,name):return Dense(self.s.weight(name+".weight"))
    def normw(self,name):return self.s.weight(name+".weight")
    def mix(self,streams,prefix,inject=True):
        w=self.normw(prefix+".hc_norm").reshape(4,2560)
        xn=hc_norm(streams,w);flat=xn.flatten(1)
        low=ref.silu(self.dense(prefix+".input_mix_weight_down")(flat).float()/4).to(BF)
        gate=self.dense(prefix+".input_mix_weight_up")(low).reshape_as(streams)
        acc=torch.zeros_like(streams[:,0],dtype=torch.float32)
        for i in range(4):acc=acc+torch.sigmoid(gate[:,i].float())*xn[:,i].float()
        inj=self.dense(prefix+".block_inject_weight")(flat) if inject else None
        return (acc/4).to(BF),inj
    def attention(self,x):
        p=self.prefix+"self_attn."
        w={k:self.dense(p+v) for k,v in {"q":"q_proj","k":"k_proj","v":"v_proj","out":"o_proj","index":"indexer.index_qk_proj"}.items()}
        # The packet2 QSA calls norm with gains. Supply FP32 1+w, avoiding
        # an extra BF16 rounding when converting official Gemma parameters.
        for k,v in {"qn":"q_norm","kn":"k_norm","iqn":"indexer.q_layernorm","ikn":"indexer.k_layernorm"}.items():w[k]=1+self.normw(p+v).float()
        y,self.cache=qsa_reference.qsa(x,w,self.cache)
        return y
    def mlp(self,x):
        p=self.prefix+"mlp."
        logits=self.dense(p+"gate")(x);ids,prob=ref.route(logits)
        # vLLM weighted down accumulators round to BF16 before moe_sum.
        outputs=[]
        for slot,e in enumerate(ids[0].tolist()):
            self.experts_seen.add(e);ep=p+f"experts.{e}."
            gate=ExpertLinear(self.s,ep+"gate_proj",self.expanded)(x)
            up=ExpertLinear(self.s,ep+"up_proj",self.expanded)(x)
            h=(ref.silu(gate)*up.float()).to(BF)
            outputs.append(ExpertLinear(self.s,ep+"down_proj",self.expanded)(h,prob=prob[0,slot]))
        acc=torch.zeros_like(outputs[0],dtype=torch.float32)
        for y in outputs:acc=acc+y.float()
        routed=acc.to(BF)
        sh={k:self.dense(p+"shared_expert."+k+"_proj") for k in ("gate","up","down")}
        shared=(ref.ffn(x,sh).float()*torch.sigmoid(self.dense(p+"shared_expert_gate")(x)).float()).to(BF)
        return (routed.float()+shared.float()).to(BF)
    def __call__(self,streams,embedding,position):
        assert position==self.position==len(self.cache[0]);self.position+=1
        e=self.dense("mtp.fc_embedding")(gemma(embedding,self.normw("mtp.pre_fc_norm_embedding")))
        h=gemma(streams.flatten(1),self.normw("mtp.pre_fc_norm_hidden")).reshape_as(streams)
        h=self.dense("mtp.fc_hidden")(h)
        merged=(h.float()+e.float()[:,None,:]).to(BF)
        x,inj=self.mix(merged,self.prefix+"attn_hyper_connection")
        multi=ref.hc_combine(merged,self.attention(x),inj)
        x,inj=self.mix(multi,self.prefix+"mlp_hyper_connection")
        multi=ref.hc_combine(multi,self.mlp(x),inj)
        sample,_=self.mix(multi,"mtp.hyper_connection_mixer",False)
        return sample

class RecordedStore(Store):
    def __init__(self):
        super().__init__();self.read_receipt={}
    def raw(self,t,row,rows):
        raw=super().raw(t,row,rows);key=f"{t['name']}[{row}:{row+rows}]"
        if key not in self.read_receipt:
            self.read_receipt[key]=dict(shard=t['shard'],rows=[row,row+rows],bytes=len(raw),sha256=digest(raw))
        return raw

class Bindings:
    def __init__(self,s):
        self.iq=RecordedStore();self.s=s
        self.head=IQLinear(Library(P/"build/matmul.so"),self.iq,"output.weight")
        self.coarse=None
    def embedding(self,token,official=False):
        if official:return self.s.read("model.language_model.embed_tokens.weight",token,1)
        return self.iq.rows("token_embd.weight",token,1).to(BF)
    def logits(self,x,official=False):
        if not official:return self.head(x)[0].float()
        n=self.s.meta("lm_head.weight")[2]["shape"][0]
        out=[]
        for start in range(0,n,1024):
            w=self.s.read("lm_head.weight",start,min(1024,n-start))
            out.append((x.float()@w.float().T).to(BF)[0].float())
        return torch.cat(out)
    def prepare_coarse(self):
        # Preregistered cheap first pass: 64 evenly spaced input columns,
        # all vocabulary rows. It never uses target logits or future tokens.
        n=self.iq.tensors["output.weight"]["shape"][0]
        self.coarse=torch.empty((n,64),dtype=torch.float32)
        for start in range(0,n,128):
            count=min(128,n-start)
            self.coarse[start:start+count]=self.iq.rows("output.weight",start,count)[:,::40]
    def shortlists(self,x,logits):
        scores=self.coarse@x[0,::40].float()
        order=torch.argsort(scores,descending=True,stable=True)
        result={}
        for k in (4096,16384,65536):
            ids=order[:k];chosen=ids[torch.argmax(logits[ids])]
            top=torch.topk(logits[ids],2).values
            result[str(k)]=dict(draft_token=int(chosen),draft_margin=float(top[0]-top[1]))
        return result
