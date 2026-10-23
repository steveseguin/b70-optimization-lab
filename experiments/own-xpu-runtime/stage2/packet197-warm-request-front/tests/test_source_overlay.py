"""CPU source-integration/transport contract checks, explicitly not a C++ compilation gate."""
import ast,hashlib,importlib.util,json,re,sys,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1];ROOT=P.parents[3]
sys.path.insert(0,str(P))
import prepare_overlay as overlay
spec=importlib.util.spec_from_file_location('p197_transport',ROOT/'experiments/own-xpu-runtime/integration/request_front/client.py')
transport=importlib.util.module_from_spec(spec);spec.loader.exec_module(transport)

def section(text,start,end):return text[text.index(start):text.index(end,text.index(start))]
class SourceOverlay(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.original=(overlay.NATIVE/'main.cpp').read_text();cls.header=(overlay.NATIVE/'checkpoint.hpp').read_text()
  cls.main,cls.checkpoint=overlay.transform(cls.original,cls.header)
 def test_exact_reset_step_and_checkpoint_state_bodies(self):
  for start,end in [('static void p58_reset_request(', '\n#ifdef OWN_RT_HOST_ONLY'),('    auto step = [&]', '    int next=-1;')]:
   self.assertEqual(section(self.original,start,end),section(self.main,start,end))
  for start,end in [('static SavedCheckpoint checkpoint_save(', 'struct RestoredCheckpoint'),('static RestoredCheckpoint checkpoint_restore(', '// packet181: "prefill"')]:
   self.assertEqual(section(self.header,start,end),section(self.checkpoint,start,end))
 def test_request_options_start_from_immutable_baseline(self):
  body=section(self.main,'    for(size_t request_number=0;', '    auto step = [&]')
  self.assertLess(body.index('a=front_base;'),body.index('a.checkpoint_restore=a.front_checkpoints'))
  self.assertLess(body.index('checkpoint_precheck('),body.index('p58_reset_request(*e,output)'))
  self.assertIn('e->cache_quiesce();e->a.tokens=a.tokens;',body)
  self.assertNotIn('cache_capacity(',body)
  self.assertIn('e->request_token_index=0;e->last_site=nullptr;',body)
  self.assertIn('generated.clear();text.clear();',body)
 def test_loaded_owner_and_terminal_drain_are_outside_loop(self):
  self.assertLess(self.main.index('e->initialize();',self.main.index('int main(')),self.main.index('front->reader.next('))
  self.assertGreater(self.main.index('owner_shutdown_attempted=true;teardown = e->shutdown();'),self.main.index('} // bracket views; weights and owner stay resident'))
  self.assertIn('if(!owner_shutdown_attempted)',self.main)
  self.assertIn('if(error.empty()&&comparison&&owner_shutdown_complete)',self.main)
  self.assertNotIn('stopped = 0;',section(self.main,'    for(size_t request_number=0;', '} // bracket views;'))
 def test_new_checkpoint_contract_cannot_claim_parent_qualification(self):
  self.assertIn('CHECKPOINT_LABEL="experimental-warm-front"',self.checkpoint)
  self.assertIn('CHECKPOINT_CONTRACT="v1.2+p197"',self.checkpoint)
  self.assertIn('CHECKPOINT_PACKET="packet197-warm-request-front"',self.checkpoint)
  value=re.search(r'CHECKPOINT_QUALIFIED_BY=("(?:\\.|[^"\\])*")',self.checkpoint)[1]
  self.assertEqual(json.loads(ast.literal_eval(value))['device_gates'],[])
  self.assertIn('checkpoint_self_sha256()!=m.binary_sha',self.checkpoint)
 def test_literal_event_prefixes_match_transport(self):
  for event in ('ready','request-start','request-complete','stopped','fatal'):
   line=next(x for x in self.main.splitlines() if 'front->emit(' in x and '\\"'+event+'\\"' in x)
   literals=re.findall(r'"(?:\\.|[^"\\])*"',line)
   prefix=ast.literal_eval(literals[0]);self.assertTrue(prefix.startswith('{"event":"'+event+'"'),prefix)
  native=(P/'native/request_front.hpp').read_text()
  self.assertIn('frame_limit=262144',native)
  for invariant in ('count_==maximum_','ids_.insert(r.id).second','now>=deadline','now>=idle_deadline','if(stop)','POLLERR|POLLNVAL','partial request at EOF'):
   self.assertIn(invariant,native)
 def test_restore_metrics_are_explicit_only_in_front_mode(self):
  self.assertIn('front&&restoring?std::to_string(restored.position):"0"',self.main)
  self.assertIn('experimental-warm-owner-v1',self.main)
  self.assertIn('session_reuse',self.main)
  reset=section(self.main,'static void p58_reset_request(', '\n#ifdef OWN_RT_HOST_ONLY')
  self.assertIn(r'"cached_tokens\":0',reset)
 def test_parent_pins_and_generated_overlay_match(self):
  pins=json.loads((P/'parent-pins.json').read_text())
  for name,digest in pins['sources'].items():self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest,name)
  self.assertEqual((P/'build/native/main.cpp').read_text(),self.main)
  self.assertEqual((P/'build/native/checkpoint.hpp').read_text(),self.checkpoint)
 def test_context_guard_and_checkpoint_frame_contract(self):
  frame=transport.encode_request('r1',[1,2,3],4,context=32,vocab=10,restore='s1',save='s2')
  self.assertEqual(frame,b'RUN\tr1\t4\ts1\ts2\t1 2 3\n')
  for kw in (dict(request_id='../escape'),dict(request_id='a.lock'),dict(tokens=[True]),dict(tokens=[10]),dict(max_new=0),dict(max_new=513),dict(restore='s1',save='s1'),dict(context=6)):
   args=dict(request_id='r1',tokens=[1,2,3],max_new=4,context=32,vocab=10);args.update(kw)
   with self.subTest(case=kw),self.assertRaises(ValueError):transport.encode_request(**args)
if __name__=='__main__':unittest.main()
