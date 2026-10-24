import copy,importlib.util,json,os,unittest
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('reference_longer_tests',P/'once.py');M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
def answer(request,n=512,stop='limit'):
 top=[dict(id=i,logprob=-float(i)) for i in range(32)];row=dict(id=0,logprob=0.,top_logprobs=top)
 return dict(tokens_evaluated=len(request['prompt']),timings=dict(prompt_n=len(request['prompt']),cache_n=0),truncated=False,tokens=[0]*n,tokens_predicted=n,stop=True,stop_type=stop,generation_settings=dict(temperature=0,samplers=['temperature'],n_predict=512,ignore_eos=False,n_probs=32,post_sampling_probs=False,repeat_penalty=1,presence_penalty=0,frequency_penalty=0,logit_bias=[],grammar='',lora=[],**{'speculative.types':'none'}),completion_probabilities=[copy.deepcopy(row) for _ in range(n)])
class Tests(unittest.TestCase):
 def setUp(self):self.request=json.loads((P/'requests.json').read_text())['cases'][0]['request']
 def test_all_fixed_original_cases(self):
  v=json.loads((P/'requests.json').read_text());m=json.loads(Path(v['manifest_path']).read_text());self.assertEqual(M.sha(v['manifest_path']),v['manifest_sha256'])
  for i,c in enumerate(v['cases']):
   self.assertEqual(c['index'],i);self.assertEqual(c['id'],m['prompts'][i]['prompt_id']);self.assertEqual(c['request']['prompt'],m['prompts'][i]['tokens']);self.assertEqual(c['request']['n_predict'],512);self.assertEqual(c['request']['temperature'],0)
  self.assertEqual(len(v['cases']),3)
 def test_cap_and_natural_eos(self):
  M.response_check(answer(self.request),self.request);M.response_check(answer(self.request,7,'eos'),self.request)
  with self.assertRaisesRegex(RuntimeError,'full cap'):M.response_check(answer(self.request,7),self.request)
 def test_effective_temperature_zero(self):
  x=answer(self.request,2,'eos');x['generation_settings']['temperature']=-1
  with self.assertRaisesRegex(RuntimeError,'greedy sampler'):M.response_check(x,self.request)
 def test_cached_input_and_wrong_argmax_refused(self):
  x=answer(self.request,2,'eos');x['timings']['cache_n']=1
  with self.assertRaisesRegex(RuntimeError,'uncached'):M.response_check(x,self.request)
  x=answer(self.request,2,'eos');x['completion_probabilities'][0]['top_logprobs'][1]['logprob']=1
  with self.assertRaisesRegex(RuntimeError,'argmax'):M.response_check(x,self.request)
 def test_home_preserved_and_dtypes_not_weakened(self):
  with patch.dict(os.environ,HOME='/home/steve'):self.assertEqual(M.clean_env()['HOME'],'/home/steve')
  M.dtype_log('K (bf16) V (bf16) R (f32) S (f32) P (f32)')
  with self.assertRaisesRegex(RuntimeError,'F32'):M.dtype_log('K (bf16) V (bf16) R (bf16) S (bf16) P (bf16)')
if __name__=='__main__':unittest.main()
