"""Independent checks of denominators, causality, alignment and FP8 boundaries."""
import unittest
from analyze import wilson,stats,lookups
class Protocol(unittest.TestCase):
    def test_wilson_known(self):
        lo,hi=wilson(50,100);self.assertAlmostEqual(lo,0.4038315304);self.assertAlmostEqual(hi,0.5961684696)
        self.assertAlmostEqual(wilson(0,64)[1],0.0566240598)
    def test_recent_successor_and_no_future(self):
        t=[10,20,30,10,40,10]
        self.assertEqual(lookups(t,5),dict(unigram=40,bigram=40,repeat_current=10))
        self.assertEqual(lookups(t+[99,10,77],5),lookups(t,5))
        self.assertEqual(lookups([1,2,3,4,1,2],5)["bigram"],3)
    def test_misses_do_not_cross_prompts(self):
        rows=[dict(prompt="a",generated_index=i,hit=False) for i in range(64)]
        rows += [dict(prompt="b",generated_index=i,hit=False) for i in range(64)]
        s=stats(rows);self.assertEqual(s["longest_miss_run"],64)
        self.assertEqual(sum(d["count"] for d in s["deciles"]),128)
    def test_shift(self):
        n=87
        for index in range(64):
            p=n-1+index;j=p-1
            self.assertEqual(j-(n-2),index)
            self.assertEqual((p+1)-n,index) # token x_(p+1) is generated[index]
class Numeric(unittest.TestCase):
    def test_fp8_and_norm(self):
        import torch
        torch.set_num_threads(1)
        from draft_reference import activation_quant,gemma,BF
        x=torch.full((1,128),448,dtype=BF);q,s=activation_quant(x)
        self.assertTrue(torch.equal(q,torch.full((1,1,128),448.)))
        self.assertEqual(s.item(),1.)
        x=torch.ones((1,8),dtype=BF)
        self.assertTrue(torch.equal(gemma(x,torch.zeros(8,dtype=BF)),x))
    def test_cache_and_weight_boundaries(self):
        import torch
        torch.set_num_threads(1)
        from draft_reference import ExpertLinear,BF
        class Tiny:
            def read(self,name):
                if name.endswith("weight_scale_inv"):return torch.full((1,1),0.5,dtype=BF)
                return torch.full((128,128),2,dtype=torch.float8_e4m3fn)
        x=torch.ones((1,128),dtype=BF)
        fp=ExpertLinear(Tiny(),"test",False)
        self.assertTrue(torch.equal(fp(x),torch.full((1,128),128,dtype=BF)))
        eq=ExpertLinear(Tiny(),"test",True)
        self.assertEqual(eq.code.dtype,torch.int8);self.assertEqual(eq.scale.shape,(128,8))
        self.assertTrue(torch.equal(eq(x),fp(x)))
if __name__=="__main__":unittest.main()
