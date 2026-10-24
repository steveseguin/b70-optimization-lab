import hashlib,importlib.util,json,struct,tempfile,unittest
from pathlib import Path
P=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('prefix_audit_tests',P/'audit.py');A=importlib.util.module_from_spec(sp);sp.loader.exec_module(A)
sha=lambda x:hashlib.sha256(x).hexdigest()
def fixture(path):
 data={'unselected.bin':b'other-state','logits.bin':struct.pack('<4H',0x3f80,0x4000,0,0),'position.bin':struct.pack('<I',157)}
 bundle=b'';lines=['GSQ_STATE_BUNDLE_V1'];buffers={}
 for n,b in data.items():lines.append(f'{n}\t{len(bundle)}\t{len(b)}\t{sha(b)}');buffers[n[:-4]]=sha(b);bundle+=b
 state=json.dumps({'buffers':buffers},separators=(',',':')).encode();index=('\n'.join(lines)+'\n').encode();seal=f'GSQ_STATE_SEAL_V1\n{len(bundle)}\n{sha(bundle)}\n{sha(index)}\n{sha(state)}\n'.encode()
 for n,b in {'state.bundle':bundle,'state-index.tsv':index,'state.json':state,'state-seal.txt':seal}.items():(path/n).write_bytes(b)
 return data,bundle
class Tests(unittest.TestCase):
 def test_one_stream_selected_and_whole_integrity(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);data,b=fixture(p);got=A.S.read_selected(p,{'logits.bin':8,'position.bin':4})
   self.assertEqual(got['captured'],{k:data[k] for k in ('logits.bin','position.bin')});self.assertEqual(got['whole_sha256'],sha(b));self.assertEqual(got['payload_bytes'],len(b));self.assertEqual(got['range_count'],3)
   changed=bytearray(b);changed[0]^=1;(p/'state.bundle').write_bytes(changed)
   with self.assertRaisesRegex(ValueError,'buffer bytes differ'):A.S.read_selected(p,{'logits.bin':8,'position.bin':4})
 def test_missing_or_wrong_extent_and_unsealed_file(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);fixture(p)
   for wanted in ({'absent.bin':4},{'logits.bin':4}):
    with self.assertRaises(ValueError):A.S.read_selected(p,wanted)
   (p/'partial').write_bytes(b'x')
   with self.assertRaisesRegex(ValueError,'incomplete/unexpected'):A.S.read_selected(p,{'position.bin':4})
 def test_tie_vs_strict_order_conclusion(self):
  v=[0.]*265;v[220]=v[264]=1.;r={'top_logprobs':[{'logprob':-.9},{'logprob':-1.0}]}
  self.assertTrue(A.rounding_question(v,r)['final_rounding_can_hide_reverse_strict_order']);v[220]=1.0078125
  self.assertFalse(A.rounding_question(v,r)['final_rounding_can_hide_reverse_strict_order'])
  v[220]=.5
  with self.assertRaises(ValueError):A.rounding_question(v,r)
 def test_probability_alignment_refuses_omissions(self):
  tokens=[1]*512;tokens[70]=264;probs=[dict(id=t,top_logprobs=[{}]*32) for t in tokens]
  ref=dict(prompt_tokens=[2]*87,tokens=tokens);response=dict(status=200,response=dict(tokens=tokens,tokens_evaluated=87,completion_probabilities=probs,generation_settings={'post_sampling_probs':False}))
  self.assertEqual(A.reference_row(response,ref)['id'],264);response['response']['completion_probabilities']=probs[1:]
  with self.assertRaisesRegex(ValueError,'probability positions'):A.reference_row(response,ref)
 def test_actual_small_plan_and_budget(self):
  p=P/'plan.json';self.assertEqual(sha(p.read_bytes()),A.PLAN_SHA);plan=json.loads(p.read_text());case=plan['suite']['cases'][0]
  self.assertEqual((len(case['prompt_tokens']),case['prompt_tokens'][-1],plan['max_new'],plan['startup_max_new']),(157,303,1,128))
  self.assertEqual(plan['adapter']['binary_sha256'],A.BINARY)
  b=dict(stage=3,acknowledged=['reset_00','last_dump','finish'],remaining_payload_bytes=0,metadata_reserve_bytes=128<<20,external_floor_bytes=2<<30);A.check_budget(b);b['stage']=2
  with self.assertRaises(ValueError):A.check_budget(b)
if __name__=='__main__':unittest.main()
