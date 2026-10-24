import importlib.util, math, os, struct, tempfile, unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('comparison',Path(__file__).with_name('compare.py'));C=importlib.util.module_from_spec(s);s.loader.exec_module(C)
class Tests(unittest.TestCase):
 def test_bf16(self):
  self.assertEqual(C.bf16(struct.pack('<4H',0,0x8000,0x3f80,0xc000)),[0.,-0.,1.,-2.]);self.assertLess(math.copysign(1,C.bf16(b'\x00\x80')[0]),0)
 def test_stable_normalization_ties(self):
  lp=-math.log(2+math.exp(-1));ref={'id':0,'logprob':lp,'top_logprobs':[{'id':0,'logprob':lp},{'id':1,'logprob':lp},{'id':2,'logprob':lp-1}]}
  r=C.compare([10000.,10000.,9999.],ref);self.assertEqual(r['native_argmax'],0);self.assertEqual(r['reference_top_rows'][1]['native_tie_rank_interval'],[1,2]);self.assertLess(r['retained_top_max_abs_logprob_delta'],1e-12)
 def test_difference_is_not_quality_failure(self):
  r=C.compare([0.,1.],{'id':0,'logprob':-.1,'top_logprobs':[{'id':0,'logprob':-.1},{'id':1,'logprob':-2.}]});self.assertFalse(r['argmax_agrees']);self.assertEqual(r['reference_top_rows'][0]['native_rank_tie_break_low_id'],2)
 def test_refusals(self):
  ref={'id':0,'logprob':0.,'top_logprobs':[{'id':0,'logprob':0.}]}
  with self.assertRaises(ValueError):C.compare([float('nan')],ref)
  with self.assertRaises(ValueError):C.compare([0.],dict(ref,top_logprobs=[{'id':0,'logprob':0.}]*2))
 def test_alignment(self):
  prompt=list(range(87));tokens=list(range(100,132));trace=[]
  for p,t in enumerate(prompt+tokens[:-1]):trace.extend([{'rank':1,'op':1,'position':p,'token':t},{'rank':0,'op':1,'position':p,'token':t,'rank_received':p*2},{'rank':0,'op':2,'rank_received':p*2+1}])
  result={'tokens':tokens,'rank_trace':trace};ref={'tokens':tokens,'tokens_evaluated':87,'completion_probabilities':[{'id':t} for t in tokens]}
  self.assertEqual(C.alignment(result,prompt,ref)['last_evaluated_position_zero_based'],117)
  trace[0]['token']+=1
  with self.assertRaises(ValueError):C.alignment(result,prompt,ref)
 def test_range_hash(self):
  with tempfile.TemporaryFile() as f:
   f.write(b'prefixDATAend');f.flush();row={'offset':6,'bytes':4,'sha256':C.digest(b'DATA')};self.assertEqual(C.read_range(f.fileno(),row),b'DATA');row['offset']=5
   with self.assertRaises(ValueError):C.read_range(f.fileno(),row)
 def test_actual_metadata_authority_only(self):
  a,r,c,s,l=C.authority();self.assertEqual(a['consumed_tokens'],118);self.assertEqual(len(r['top_logprobs']),32);self.assertEqual(c['payload_bytes'],125598668);self.assertEqual(set(s),C.FILES);self.assertIn('logits.bin',l)
if __name__=='__main__':unittest.main()
