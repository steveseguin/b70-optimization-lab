import copy,importlib.util,json,unittest
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('independent_cpu_audit',P/'audit.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
def fixture(tokens=None,stop='limit'):
 tokens=tokens or [0]*512
 g=dict(temperature=0,samplers=['temperature'],seed=0,n_predict=512,ignore_eos=False,n_probs=32,post_sampling_probs=False,repeat_penalty=1,presence_penalty=0,frequency_penalty=0,dynatemp_range=0,mirostat=0,dry_multiplier=0,backend_sampling=False,logit_bias=[],grammar='',lora=[],**{'speculative.types':'none'})
 top=[dict(id=i,logprob=-float(i)) for i in range(32)]
 r=dict(tokens=tokens,tokens_evaluated=87,tokens_predicted=len(tokens),timings=dict(prompt_n=87,cache_n=0),truncated=False,stop=True,stop_type=stop,generation_settings=g,completion_probabilities=[dict(id=0,logprob=0.,top_logprobs=copy.deepcopy(top)) for _ in tokens],content='full text')
 return r,dict(prompt=list(range(87)))
class Tests(unittest.TestCase):
 def test_cap_and_omitted_probability_rows(self):
  r,q=fixture();v,m=A.check_response(r,q);self.assertEqual(v['generated_tokens'],512);self.assertEqual(m,1.)
  r,q=fixture([0,31,0],'eos');r['completion_probabilities']=r['completion_probabilities'][:2];v,m=A.check_response(r,q);self.assertEqual(v['omitted_probability_rows'],1);self.assertIn('prevent unique',v['probability_alignment'])
 def test_actual_live_evidence_schema_equal(self):
  s=importlib.util.spec_from_file_location('frozen_reference_once',P/'once.py');M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
  for tokens,stop in [([0]*512,'limit'),([0,31,0],'eos')]:
   r,q=fixture(tokens,stop)
   if stop=='eos':r['completion_probabilities']=r['completion_probabilities'][:2]
   v,_=A.check_response(r,q);self.assertEqual(v,M.response_check(r,q))
 def test_cache_argmax_order_refusals(self):
  for mutate in [lambda r:r['timings'].update(cache_n=1),lambda r:r['completion_probabilities'][0]['top_logprobs'][0].update(logprob=-2.),lambda r:r.update(tokens_predicted=511),lambda r:r['completion_probabilities'][0].update(id=33)]:
   r,q=fixture();mutate(r)
   with self.assertRaises(ValueError):A.check_response(r,q)
 def test_short_cap_failed_owner_refusals(self):
  r,q=fixture([0],'limit')
  with self.assertRaises(ValueError):A.check_response(r,q)
  t=dict(passed=False,first_error='fail',response_valid=False,completed_requests=0)
  with self.assertRaises(ValueError):A.closure(t,{'pid':1,'start_ticks':'0'})
 def test_actual_admitted_plan_metadata_only(self):
  self.assertEqual(A.digest(P/'plan.json'),A.PLAN_SHA);p=A.load(P/'plan.json');self.assertEqual(p['binary_sha256'],A.BINARY);self.assertEqual([len(c['request']['prompt']) for c in p['requests']],[87,90,77]);self.assertTrue(all(c['request']['n_predict']==512 for c in p['requests']))
if __name__=='__main__':unittest.main()
