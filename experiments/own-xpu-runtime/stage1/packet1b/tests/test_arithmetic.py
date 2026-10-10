import json
from pathlib import Path
import unittest
import torch
from reference.math import *

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT.parent/'packet1/tensor-contract.json').read_text())
RECORDS = {t['name']:t for t in CONTRACT['tensors']}


def tensor(name, value=0.001):
    """Nonzero expanded synthetic constant, with real contract shape/dtype.

    No weight payload is read. Expanded storage bounds test memory while all
    production-sized arithmetic executes through the ordinary Linear path.
    """
    t = RECORDS[name]
    dtype = {'BF16':BF16,'F8_E4M3':FP8}[t['dtype']]
    return torch.tensor(value,dtype=dtype,device='cpu').expand(t['shape'])


def linear(name):
    t = RECORDS[name]
    return Linear(tensor(name,0.125 if t['dtype']=='F8_E4M3' else 0.0001),
                  tensor(t['format']['scale_tensor'],0.015625) if t['dtype']=='F8_E4M3' else None)


def layer_weights(prefix, kind):
    a = prefix+('.linear_attn.' if kind=='gdn' else '.self_attn.')
    if kind=='gdn':
        attn = {key:linear(a+name+'.weight') for key,name in
                [('qkv','in_proj_qkv'),('z','in_proj_z'),('a','in_proj_a'),('b','in_proj_b'),('out','out_proj')]}
        attn.update(conv=tensor(a+'conv1d.weight',0.25),norm=tensor(a+'norm.weight',1),
                    A_log=tensor(a+'A_log',0),dt_bias=tensor(a+'dt_bias',0))
    else:
        attn = {key:linear(a+name+'_proj.weight') for key,name in [('q','q'),('k','k'),('v','v'),('out','o')]}
        attn.update(q_norm=tensor(a+'q_norm.weight',0),k_norm=tensor(a+'k_norm.weight',0))
    return {'attention':attn,'input_norm':tensor(prefix+'.input_layernorm.weight',0),
            'post_norm':tensor(prefix+'.post_attention_layernorm.weight',0),
            'ffn':{k:linear(prefix+'.mlp.'+k+'_proj.weight') for k in ('gate','up','down')}}


def bits_equal(a,b):
    return torch.equal(a.contiguous().view(torch.uint8),b.contiguous().view(torch.uint8))


class Arithmetic(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(19)

    def test_fp8_bf16_scale_roundtrip(self):
        raw = torch.tensor([-2,-1,-0.5,0,0.5,1,2,4],dtype=FP8).repeat(64).reshape(2,256)
        scales = torch.tensor([[0.5,2]],dtype=BF16)
        out = fp8_dequant(raw,scales)
        expanded = scales.float().repeat_interleave(128,1)
        self.assertTrue(bits_equal((out.float()/expanded).to(FP8),raw))
        self.assertEqual(out.dtype,F16)

    def test_fp8_scale_rejects_fp32(self):
        with self.assertRaises(ValueError): fp8_dequant(torch.ones(2,2).to(FP8),torch.ones(1,1))

    def test_fp8_edge_tiles(self):
        w = torch.ones(129,129).to(FP8)
        sc = torch.tensor([[1,2],[3,4]],dtype=BF16)
        y = fp8_dequant(w,sc)
        self.assertEqual([y[0,0],y[0,-1],y[-1,0],y[-1,-1]],[1,2,3,4])

    def test_scale_wrong_shape(self):
        with self.assertRaises(ValueError): fp8_dequant(torch.ones(129,2).to(FP8),torch.ones(1,1,dtype=BF16))

    def test_w8a16_known_dot(self):
        w = torch.tensor([[1,2],[-1,4]],dtype=FP8)
        f = Linear(w,torch.tensor([[0.5]],dtype=BF16))
        y = f(torch.tensor([[2,3]],dtype=F16))
        self.assertTrue(torch.equal(y,torch.tensor([[4,5]],dtype=F16)))

    def test_linear_no_activation_quantization(self):
        f = Linear(torch.tensor([[1]],dtype=FP8),torch.ones(1,1,dtype=BF16))
        x = torch.tensor([[1.03125]],dtype=F16)
        self.assertTrue(bits_equal(f(x),x))

    def test_linear_bad_dtype(self):
        with self.assertRaises(ValueError): Linear(torch.ones(2,2))
        with self.assertRaises(ValueError): Linear(torch.ones(2,2,dtype=BF16))(torch.ones(1,2))

    def test_unit_offset_norm(self):
        x = torch.tensor([[3.,4.]],dtype=F16)
        w = torch.zeros(2,dtype=BF16)
        expected = (x.float()/torch.sqrt(torch.tensor(12.5+1e-6))).to(F16)
        self.assertTrue(bits_equal(rmsnorm(x,w),expected))
        self.assertTrue(torch.equal(rmsnorm(x,w,unit_offset=False),torch.zeros_like(x)))

    def test_residual_keeps_small_increment(self):
        r = residual_add(torch.tensor([0.25],dtype=F16),torch.tensor([2048.],dtype=F16))
        self.assertEqual(r.dtype,F32)
        self.assertEqual(r.item(),2048.25)

    def test_ffn_known_value(self):
        eye = Linear(torch.eye(2,dtype=BF16))
        x = torch.tensor([[1,-1]],dtype=F16)
        actual = ffn(x,eye,eye,eye)
        self.assertTrue(bits_equal(actual,(silu(x,F32)*x.float()).to(F16)))

    def test_conv_order_and_state(self):
        history = torch.tensor([[1,2,3]],dtype=F16)
        y, h = conv_step(torch.tensor([4],dtype=F16),history,torch.tensor([[[1,2,4,8]]],dtype=BF16))
        self.assertTrue(bits_equal(y,silu(torch.tensor([49.]))))
        self.assertTrue(torch.equal(h,torch.tensor([[2,3,4]],dtype=F16)))
        self.assertTrue(torch.equal(history,torch.tensor([[1,2,3]],dtype=F16)))

    def recurrent_args(self,t=2):
        return (torch.randn(t,16,128).half(),torch.randn(t,16,128).half(),
                torch.randn(t,48,128).half(),torch.randn(t,48).half(),torch.randn(t,48).half(),
                torch.zeros(48,dtype=BF16),torch.zeros(48,dtype=BF16),torch.randn(48,128,128)*0.01)

    def test_gdn_serial_state_matches_separate_calls(self):
        args = self.recurrent_args()
        y,s = gdn_recurrence(*args)
        y0,s0 = gdn_recurrence(*(v[:1] for v in args[:5]),*args[5:])
        y1,s1 = gdn_recurrence(*(v[1:] for v in args[:5]),*args[5:7],s0)
        self.assertTrue(bits_equal(y,torch.cat((y0,y1))))
        self.assertTrue(bits_equal(s,s1))

    def test_gdn_determinism_and_input_immutable(self):
        args = self.recurrent_args()
        saved = [x.clone() for x in args]
        first,second = gdn_recurrence(*args),gdn_recurrence(*args)
        self.assertTrue(all(bits_equal(a,b) for a,b in zip(first,second)))
        self.assertTrue(all(bits_equal(a,b) for a,b in zip(saved,args)))

    def test_gdn_zero_key_only_decays(self):
        args = list(self.recurrent_args(1))
        args[0].zero_(); args[1].zero_(); args[3].zero_(); args[4].zero_()
        y,s = gdn_recurrence(*args)
        self.assertTrue(torch.equal(y,torch.zeros_like(y)))
        self.assertTrue(bits_equal(s,args[-1]*0.5))

    def test_gdn_state_precision_rejected(self):
        args = list(self.recurrent_args())
        args[-1]=args[-1].half()
        with self.assertRaises(ValueError): gdn_recurrence(*args)

    def test_rope_zero_and_unrotated_tail(self):
        x = torch.randn(2,24,256).half()
        self.assertTrue(bits_equal(rope(x,torch.zeros(2,dtype=torch.int64)),x))
        self.assertTrue(bits_equal(rope(x,torch.tensor([17,39]))[...,64:],x[...,64:]))

    def test_rope_negative_position(self):
        with self.assertRaises(ValueError): rope(torch.zeros(1,24,256,dtype=F16),torch.tensor([-1]))

    def test_stable_ties(self):
        self.assertEqual(stable_argmax(torch.tensor([[1.,2.,2.]])).item(),1)
        self.assertEqual(stable_argmax(torch.tensor([[-0.,0.]])).item(),0)
        self.assertEqual(stable_argmax(torch.tensor([[float('inf'),float('inf')]])).item(),0)

    def test_argmax_nan_and_empty(self):
        for x in (torch.tensor([float('nan')]),torch.empty(0)):
            with self.assertRaises(ValueError): stable_argmax(x)

    def test_target_head(self):
        x = torch.tensor([[1.,2.]],dtype=F16)
        head = Linear(torch.tensor([[1,0],[0,1],[0,1]],dtype=BF16))
        y = target_head(x,torch.zeros_like(x,dtype=F32),torch.zeros(2,dtype=BF16),head)
        self.assertEqual(stable_argmax(y).item(),1)

    def test_full_vocabulary_tie(self):
        logits = torch.zeros(1,248320,dtype=F16)
        logits[0,248318:]=1
        self.assertEqual(stable_argmax(logits).item(),248318)

    def test_contract_gdn_layer_shape_repeat(self):
        w = layer_weights('model.language_model.layers.0','gdn')
        x = torch.linspace(-0.1,0.3,5120).half()[None,:]
        cache = (torch.zeros(10240,3,dtype=F16),torch.zeros(48,128,128))
        one = decoder_layer(x,None,w,'gdn',cache)
        two = decoder_layer(x,None,w,'gdn',cache)
        self.assertEqual(one[0].shape,(1,5120)); self.assertEqual(one[1].dtype,F32)
        self.assertEqual(one[2][0].shape,(10240,3)); self.assertEqual(one[2][1].dtype,F32)
        self.assertTrue(bits_equal(one[0],two[0])); self.assertTrue(bits_equal(one[1],two[1]))
        self.assertTrue(all(bits_equal(a,b) for a,b in zip(one[2],two[2])))
        self.assertGreater(torch.count_nonzero(one[0]).item(),0)

    def test_contract_attention_layer_shape_repeat_causality(self):
        w = layer_weights('model.language_model.layers.3','attention')
        x = torch.linspace(-0.1,0.3,5120).half().repeat(2,1)
        cache = (torch.zeros(0,4,256,dtype=F16),torch.zeros(0,4,256,dtype=F16))
        one = decoder_layer(x,None,w,'attention',cache,torch.tensor([0,1]))
        two = decoder_layer(x,None,w,'attention',cache,torch.tensor([0,1]))
        self.assertEqual(one[0].shape,(2,5120))
        self.assertEqual(one[2][0].shape,(2,4,256)); self.assertEqual(one[2][0].dtype,F16)
        self.assertTrue(bits_equal(one[0],two[0])); self.assertTrue(bits_equal(one[1],two[1]))
        self.assertTrue(all(bits_equal(a,b) for a,b in zip(one[2],two[2])))
        x[1]*=-2
        changed = decoder_layer(x,None,w,'attention',cache,torch.tensor([0,1]))
        self.assertTrue(bits_equal(one[0][0],changed[0][0]))
        self.assertFalse(bits_equal(one[0][1],changed[0][1]))

    def test_contract_mtp_forward(self):
        w = {'layer':layer_weights('mtp.layers.0','attention'),
             'embedding_norm':tensor('mtp.pre_fc_norm_embedding.weight',0),
             'hidden_norm':tensor('mtp.pre_fc_norm_hidden.weight',0),
             'norm':tensor('mtp.norm.weight',0),'fc':linear('mtp.fc.weight')}
        hidden = torch.linspace(-0.1,0.2,5120).half()[None,:]
        embedding = hidden.flip(-1)
        # Tiny vocabulary for head arithmetic; real MTP merge/block shapes.
        head = Linear(torch.tensor(0.0001,dtype=BF16).expand(7,5120))
        kv = (torch.empty(0,4,256,dtype=F16),torch.empty(0,4,256,dtype=F16))
        one = mtp_forward(hidden,embedding,w,torch.tensor([0]),kv,head)
        two = mtp_forward(hidden,embedding,w,torch.tensor([0]),kv,head)
        self.assertEqual(one[0].shape,(1,5120)); self.assertEqual(one[1].shape,(1,7))
        self.assertTrue(bits_equal(one[0],two[0])); self.assertTrue(bits_equal(one[1],two[1]))
        self.assertTrue(all(bits_equal(a,b) for a,b in zip(one[2],two[2])))

    def test_mtp_embedding_then_hidden_concat(self):
        from unittest.mock import patch
        import reference.math as module
        hidden=torch.tensor([[1.,3.]],dtype=F16)
        embedding=torch.tensor([[2.,-1.]],dtype=F16)
        captured=[]
        def merge(x):
            captured.append(x.clone())
            return x[:,:2]
        w={'embedding_norm':torch.zeros(2,dtype=BF16),'hidden_norm':torch.zeros(2,dtype=BF16),
           'norm':torch.zeros(2,dtype=BF16),'fc':merge,'layer':{}}
        with patch.object(module,'decoder_layer',side_effect=lambda x,*a:(x,torch.zeros_like(x,dtype=F32),())):
            mtp_forward(hidden,embedding,w,torch.tensor([0]),(),lambda x:x)
        self.assertTrue(bits_equal(captured[0],torch.cat((rmsnorm(embedding,w['embedding_norm']),rmsnorm(hidden,w['hidden_norm'])),-1)))

    def test_attention_rejects_compressed_kv(self):
        w=layer_weights('model.language_model.layers.3','attention')
        with self.assertRaises(ValueError):
            attention(torch.zeros(1,5120,dtype=F16),w,torch.tensor([0]),(torch.zeros(1,4,256,dtype=BF16),)*2)
