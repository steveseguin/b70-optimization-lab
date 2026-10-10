"""Synthetic CPU fixtures. Real H/head/FFN geometry, small sequence/bank."""
import hashlib
import json
from pathlib import Path
import unittest
import torch
import reference as R

DIGESTS={}

def sample(shape,seed=7,scale=.02,dtype=R.BF16):
    g=torch.Generator(device='cpu').manual_seed(seed)
    return (torch.randn(shape,generator=g)*scale).to(dtype)


def linear(n,k,seed=7,fp8=False):
    # Full-shape, nonconstant synthetic views, bounded backing allocation.
    v=sample((1,k),seed,scale=.01)
    if fp8:
        return R.Linear((v.float()*32).to(R.FP8).expand(n,k),torch.full(((n+127)//128,(k+127)//128),1/32,dtype=R.BF16))
    return R.Linear(v.expand(n,k))


def hc(seed=7,inject=True):
    w={'norm':sample((4,2560),seed),'down':linear(320,10240,seed),'up':linear(10240,320,seed+1)}
    if inject:w['inject']=linear(4,10240,seed+2)
    return w


def expert(seed=7,fp8=True):
    return {'gate':linear(640,2560,seed,fp8),'up':linear(640,2560,seed+1,fp8),'down':linear(2560,640,seed+2,fp8)}


def gw():
    return {**{key:linear(n,k,i) for i,(key,n,k) in enumerate([('qkv',10240,2560),('z',6144,2560),('a',48,2560),('b',48,2560),('out',2560,6144)])},'conv':sample((10240,1,4)),'alog':sample((48,)),'dt':sample((48,)),'norm':torch.ones(128,dtype=R.BF16)}


def qw():
    return {**{key:linear(n,k,i+20) for i,(key,n,k) in enumerate([('q',12288,2560),('k',512,2560),('v',512,2560),('index',640,2560),('out',2560,6144)])},'qn':sample((256,)),'kn':sample((256,)),'iqn':sample((128,)),'ikn':sample((128,))}


def empty_qsa():
    return (torch.empty(0,2,256,dtype=R.BF16),torch.empty(0,2,256,dtype=R.BF16),torch.empty(0,128,dtype=R.BF16))


def digest(name,*xs):
    h=hashlib.sha256()
    for x in xs:h.update(x.contiguous().view(torch.uint8).numpy().tobytes())
    DIGESTS[name]=h.hexdigest()


class Arithmetic(unittest.TestCase):
    def test_norm_known(self):
        y=R.norm(torch.ones(2,2560,dtype=R.BF16),torch.ones(2560,dtype=R.BF16))
        self.assertTrue(torch.equal(y,torch.full_like(y,2)))
    def test_tree_cancellation_order(self):
        self.assertEqual(R.tree(torch.tensor([1e8,1.,-1e8,1.])).item(),0)
    def test_linear_known(self):
        y=R.Linear(torch.tensor([[1.,2.],[-1.,1.]],dtype=R.BF16))(torch.tensor([[2.,3.]],dtype=R.BF16))
        self.assertEqual(y.tolist(),[[8.,1.]])
    def test_fp8_scale_blocks(self):
        w=torch.ones(256,256).to(R.FP8); s=torch.tensor([[1,2],[3,4]],dtype=R.BF16)
        y=R.Linear(w,s)(torch.ones(1,256,dtype=R.BF16))
        self.assertEqual(y[0,0],384);self.assertEqual(y[0,128],896)
    def test_linear_reject_scales(self):
        with self.assertRaises(ValueError):R.Linear(torch.ones(128,128).to(R.FP8),torch.ones(1,2,dtype=R.BF16))
    def test_linear_reject_activation(self):
        with self.assertRaises(ValueError):linear(3,2)(torch.ones(1,2))
    def test_cpu_reject_meta(self):
        with self.assertRaises(ValueError):R.cpu(torch.empty(1,device='meta'))
    def test_conv_chronology(self):
        h=torch.tensor([[1,2,3]],dtype=R.BF16); x=torch.tensor([4],dtype=R.BF16)
        w=torch.tensor([[[1,2,4,8]]],dtype=R.BF16)
        y,new=R.conv(x,h,w)
        self.assertEqual(y.item(),49);self.assertEqual(new.tolist(),[[2,3,4]])
        self.assertEqual(h.tolist(),[[1,2,3]])
    def test_rope_zero_and_nonzero(self):
        x=sample((2,24,256));y=R.rope(x,torch.tensor([0,7]))
        self.assertTrue(torch.equal(x[0],y[0]));self.assertFalse(torch.equal(x[1],y[1]))
        self.assertTrue(torch.equal(x[...,64:],y[...,64:]))


class GDN(unittest.TestCase):
    def args(self):
        return [sample((2,16,128),1),sample((2,16,128),2),sample((2,48,128),3),sample((2,48),4),sample((2,48),5),sample((48,),6),sample((48,),7),sample((48,128,128),8)]
    def test_serial_bf16_boundary(self):
        a=self.args();y,s=R.recurrence(*a)
        y0,s0=R.recurrence(*[z[:1] for z in a[:5]],*a[5:])
        y1,s1=R.recurrence(*[z[1:] for z in a[:5]],*a[5:7],s0)
        self.assertTrue(torch.equal(y,torch.cat((y0,y1))))
        self.assertTrue(torch.equal(s,s1));self.assertEqual(s.dtype,R.BF16)
        digest('gdn_recurrence',y,s)
    def test_reject_fp32_state(self):
        a=self.args();a[-1]=a[-1].float()
        with self.assertRaises(ValueError):R.recurrence(*a)
    def test_zero_fixed_point(self):
        a=[torch.zeros_like(z) for z in self.args()];y,s=R.recurrence(*a)
        self.assertEqual(torch.count_nonzero(y),0);self.assertEqual(torch.count_nonzero(s),0)
    def test_full_layer_and_repeat(self):
        x=sample((2,2560));history=sample((10240,3));state=sample((48,128,128))
        w=gw();out=R.gdn(x,w,history,state);again=R.gdn(x,w,history,state)
        self.assertEqual(out[0].shape,(2,2560));self.assertTrue(torch.count_nonzero(out[0])>0)
        for a,b in zip(out,again):self.assertTrue(torch.equal(a,b))
        digest('gdn_layer',*out)


class QSA(unittest.TestCase):
    def test_compression_round_and_tail(self):
        x=torch.arange(7,dtype=R.BF16)[:,None].expand(7,128)
        self.assertTrue(torch.equal(R.compress(x),torch.full((1,128),1.5,dtype=R.BF16)))
    def test_selection_score_order(self):
        k=torch.zeros(3,128,dtype=R.BF16);k[:,0]=torch.tensor([1,3,2],dtype=R.BF16)
        q=torch.zeros(4,128,dtype=R.BF16);q[:,0]=1
        self.assertEqual(R.select(q,k,13,8).tolist(),[4,5,6,7,8,9,10,11,12,13,-1])
    def test_selection_ties_and_production_budget(self):
        ids=R.select(torch.zeros(4,128,dtype=R.BF16),torch.zeros(514,128,dtype=R.BF16),2058)
        self.assertEqual(ids.shape,(2051,));self.assertEqual(ids[:2048].tolist(),list(range(2048)))
        self.assertEqual(ids[-3:].tolist(),[2056,2057,2058])
    def test_selection_negative_scores_relu(self):
        q=-torch.ones(4,128,dtype=R.BF16);k=torch.ones(3,128,dtype=R.BF16)
        self.assertEqual(R.select(q,k,11,4)[:4].tolist(),[0,1,2,3])
    def test_selection_missing_state(self):
        with self.assertRaises(ValueError):R.select(torch.zeros(4,128),torch.empty(0,128),4)
    def test_layer_causality_chunk_repeat(self):
        x=sample((5,2560));w=qw()
        y,state=R.qsa(x,w,empty_qsa())
        first,st=R.qsa(x[:3],w,empty_qsa());last,st=R.qsa(x[3:],w,st)
        self.assertTrue(torch.equal(y,torch.cat((first,last))))
        for a,b in zip(state,st):self.assertTrue(torch.equal(a,b));self.assertEqual(a.dtype,R.BF16)
        again,_=R.qsa(x,w,empty_qsa());self.assertTrue(torch.equal(y,again))
        changed=x.clone();changed[-1]*=2;cy,_=R.qsa(changed,w,empty_qsa())
        self.assertTrue(torch.equal(y[:-1],cy[:-1]));self.assertFalse(torch.equal(y[-1],cy[-1]))
        digest('qsa_layer',y,*state)


class RoutingHC(unittest.TestCase):
    def test_512_top10_order_weight(self):
        logits=torch.full((1,512),-20,dtype=R.BF16)
        logits[0,-10:]=torch.arange(10,dtype=R.BF16)/16
        ids,p=R.route(logits)
        self.assertEqual(ids.tolist(),[list(range(511,501,-1))])
        expected=torch.softmax(logits.float()[0,ids[0]],0)
        self.assertTrue(torch.allclose(p[0],expected,atol=1e-7,rtol=0))
    def test_ties(self):
        ids,p=R.route(torch.zeros(2,512,dtype=R.BF16))
        self.assertEqual(ids[0].tolist(),list(range(10)))
        self.assertTrue(torch.allclose(p,torch.full_like(p,.1)))
    def test_invalid_router(self):
        for x in [torch.zeros(1,9),torch.full((1,512),float('nan')),torch.full((1,512),float('inf'))]:
            with self.assertRaises(ValueError):R.route(x)
    def test_moe_full_width_reduced_bank_repeat(self):
        x=sample((1,2560));router=linear(512,2560)
        bank={i:expert(i) for i in range(10)};shared=expert(77,False);sg=linear(1,2560)
        a=R.moe(x,router,bank.__getitem__,shared,sg);b=R.moe(x,router,bank.__getitem__,shared,sg)
        self.assertEqual(a[0].shape,(1,2560));self.assertTrue(torch.count_nonzero(a[0])>0)
        for y,z in zip(a,b):self.assertTrue(torch.equal(y,z))
        with self.assertRaises(KeyError):R.moe(x,router,{}.__getitem__,shared,sg)
        digest('moe',*a)
    def test_shared_expert_gate(self):
        x=torch.ones(1,2,dtype=R.BF16);one=R.Linear(torch.eye(2,dtype=R.BF16))
        w={'gate':one,'up':one,'down':one}
        router=R.Linear(torch.zeros(10,2,dtype=R.BF16))
        zero={k:R.Linear(torch.zeros(2,2,dtype=R.BF16)) for k in w}
        y,_,_=R.moe(x,router,lambda _:zero,w,R.Linear(torch.zeros(1,2,dtype=R.BF16)))
        self.assertTrue(torch.equal(y,(R.ffn(x,w).float()*.5).to(R.BF16)))
    def test_hc_zero_logits_mean_and_injection(self):
        x=torch.ones(1,4,2560,dtype=R.BF16)
        w=hc();w['down']=R.Linear(torch.zeros(320,10240,dtype=R.BF16))
        y,inj=R.hc_mix(x,w)
        n=torch.stack([R.norm(x[:,i],w['norm'][i]) for i in range(4)],1)
        expected=torch.zeros_like(y,dtype=R.F32)
        for i in range(4):expected+=n[:,i].float()*.5
        self.assertTrue(torch.equal(y,(expected/4).to(R.BF16)))
        result=R.hc_combine(x,torch.ones(1,2560,dtype=R.BF16),torch.zeros(1,4,dtype=R.BF16))
        self.assertTrue(torch.equal(result,torch.full_like(result,2)))
    def test_hc_repeat(self):
        x=sample((2,4,2560));w=hc();a=R.hc_mix(x,w);b=R.hc_mix(x,w)
        for y,z in zip(a,b):self.assertTrue(torch.equal(y,z))
        digest('hc',*a)


class PLEMTP(unittest.TestCase):
    def test_ple_hash_known(self):
        ids,h=R.ple_ids([3],[1,2],[1,2,4],[101]*16,[0]*16)
        self.assertEqual(ids.tolist(),[[7]*8+[3]*8]);self.assertEqual(h,[2,3])
    def test_ple_eos(self):
        a,_=R.ple_ids([3],[9,248044],[1,2,4],[101]*16,[0]*16)
        b,_=R.ple_ids([3],[248044,248044],[1,2,4],[101]*16,[0]*16)
        self.assertTrue(torch.equal(a,b))
    def test_ple_chunk_and_overflow(self):
        args=([2**62+1,17,29],[101]*16,list(range(16)))
        a,h=R.ple_ids([5,6,7],[1,2],*args)
        b,hb=R.ple_ids([5],[1,2],*args);c,hc_=R.ple_ids([6,7],hb,*args)
        self.assertTrue(torch.equal(a,torch.cat((b,c))));self.assertEqual(h,hc_)
    def test_ple_shard_edges_and_scale(self):
        ids=torch.tensor([[0,2500011,2500012,320001535]+[3]*12])
        calls=[]
        def reader(p,r):
            calls.append((p,r));return torch.ones(160).to(R.FP8)
        y=R.ple_lookup(1,ids,reader,torch.tensor([2],dtype=R.BF16))
        self.assertEqual(y.shape,(1,2560));self.assertEqual(calls[:4],[(0,0),(0,2500011),(1,0),(127,2500011)])
        self.assertTrue(torch.equal(y,torch.full_like(y,2)));digest('ple',y)
    def test_ple_wrong_layer_bounds(self):
        for layer,idx in [(2,0),(1,-1),(1,320001536)]:
            with self.assertRaises(ValueError):R.ple_lookup(layer,torch.full((1,16),idx),lambda *_:None,torch.ones(1,dtype=R.BF16))
    def test_mtp_full_block_repeat(self):
        aw=qw();ah,mh=hc(31),hc(32);router=linear(512,2560);bank={i:expert(i) for i in range(10)};sh=expert(43,False);sg=linear(1,2560)
        def block(s):
            return R.layer(s,lambda x:R.qsa(x,aw,empty_qsa())[0],lambda x:R.moe(x,router,bank.__getitem__,sh,sg)[0],ah,mh)
        w={'embed':linear(2560,2560,21),'hidden':linear(2560,2560,22),'enorm':sample((2560,)),'hnorm':sample((10240,)),'mixer':hc(23,False),'head':linear(7,2560)}
        e,s=sample((1,2560)),sample((1,4,2560))
        a=R.mtp(e,s,w,block);b=R.mtp(e,s,w,block)
        self.assertEqual(a[0].shape,(1,7));self.assertEqual(a[1].shape,(1,4,2560))
        for y,z in zip(a,b):self.assertTrue(torch.equal(y,z))
        c=R.mtp(sample((1,2560),seed=91),s,w,block);self.assertFalse(torch.equal(a[1],c[1]))
        digest('mtp',*a)
    def test_contract_shapes(self):
        d=json.loads((Path(__file__).parent.parent/'packet1/tensor-contract.json').read_text())
        ts={t['name']:t['shape'] for t in d['tensors']};p='model.language_model.layers.'
        expected={p+'0.linear_attn.in_proj_qkv.weight':[10240,2560],p+'3.self_attn.q_proj.weight':[12288,2560],p+'3.self_attn.indexer.index_qk_proj.weight':[640,2560],p+'0.mlp.gate.weight':[512,2560],p+'0.mlp.experts.0.gate_proj.weight':[640,2560],p+'0.attn_hyper_connection.input_mix_weight_down.weight':[320,10240],'mtp.fc_hidden.weight':[2560,2560]}
        for name,shape in expected.items():self.assertEqual(ts[name],shape)
        self.assertEqual(d['ple']['tensor_layer_index'],1)

class IntegrationPlanning(unittest.TestCase):
    def test_full_gdn_decoder_layer(self):
        x=sample((1,4,2560));w=gw();ah,mh=hc(40),hc(41)
        bank={i:expert(i) for i in range(10)}
        router=linear(512,2560);shared=expert(42,False);sg=linear(1,2560)
        def attn(v):return R.gdn(v,w,torch.zeros(10240,3,dtype=R.BF16),torch.zeros(48,128,128,dtype=R.BF16))[0]
        def mlp(v):return R.moe(v,router,bank.__getitem__,shared,sg)[0]
        a=R.layer(x,attn,mlp,ah,mh);b=R.layer(x,attn,mlp,ah,mh)
        self.assertTrue(torch.equal(a,b));self.assertFalse(torch.equal(a,x));self.assertEqual(a.shape,(1,4,2560))
        digest('gdn_decoder',a)
    def test_planning_reconstruction(self):
        import planning
        saved=json.loads((Path(__file__).parent/'planning-arithmetic.json').read_text())
        self.assertEqual(planning.calculate(),saved)
    def test_grid_bytes_independent(self):
        import planning
        rows=planning.calculate()['two_card']
        expected=[2359584000,1253376000,903168000,1013760000]
        self.assertEqual([v['target_expert_bytes'] for v in rows.values()],expected)
        for v in rows.values():
            caches=list(v['uniform_cache'].values())
            self.assertLess(caches[0]['assumed_hit'],caches[-1]['assumed_hit'])
            self.assertGreater(caches[0]['miss_bytes_per_token'],caches[-1]['miss_bytes_per_token'])
    def test_bf16_routing_ties_are_stable(self):
        logits=torch.arange(512,dtype=R.BF16)[None,:]/32
        ids,_=R.route(logits)
        self.assertEqual(ids[0,:5].tolist(),[511,510,507,508,509])
