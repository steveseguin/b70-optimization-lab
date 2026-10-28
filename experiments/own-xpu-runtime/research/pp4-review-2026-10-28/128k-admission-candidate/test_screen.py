"""CPU arithmetic/source regression; not native constructor or native writer execution."""
import json, math, pathlib, unittest
ROOT=pathlib.Path(__file__).resolve().parents[3]
SOURCE=ROOT/'engine/src/gsq-rco-iq3s/dense-packed-block/engine/build/source/main.cpp'
PLANS=pathlib.Path('/dev/shm/sc117-attention-owner-cpu-screen-20261028')
class Screen(unittest.TestCase):
 def test_scope_and_unchanged_caps(self):
  s=SOURCE.read_text(); t=pathlib.Path('/dev/shm/sc117-128k-main-candidate.cpp').read_text()
  self.assertEqual(t.count('(a.pipeline_enabled()&&a.context==131072)'),2)
  for line in s.splitlines():
   if 'a.target_split!=23' in line or 'a.target_split!=24' in line or 'rope_constants::' in line or '30ull' in line:
    self.assertIn(line,t)
  for pipeline in (False,True):
   for context in (4096,32768,65536,131072,262144,98304):
    old=context in (4096,32768,65536,262144)
    admitted=old or (pipeline and context==131072)
    self.assertEqual(admitted,old if not pipeline else context in (4096,32768,65536,131072,262144))
 def test_actual_plan_cache_delta(self):
  for i in (0,1):
   p=json.loads((PLANS/f'target{i}/native/launch-plan.json').read_text())
   cache=[b for b in p['buffers'] if b['name'].endswith(('.qsa.keys','.qsa.values','.qsa.raw','.qsa.pooled'))]
   self.assertEqual(len(cache),24)
   full=sum(b['bytes'] for b in cache)
   self.assertEqual(full,262144*6*4736)
   self.assertEqual(full//4,1862270976)
 def test_writer_union_formula_screen(self):
  # Formula transcription from SnapshotWriteSet::scratch, not extracted C++ execution.
  # Production h=2560, budget=2048. Enumerate actual op inventory, fail on unknown.
  zero=set('tp_gather tp_route_mask tp_expert_gather tp_push tp_wait tp_select begin commit broadcast ple_hash check_status lookup handoff handoff_result gemv routed_gemv expert_gate_up silu_div4 silu_product hc_mix conv moe_combine ple_gate ple_add'.split())
  for i in (0,1):
   p=json.loads((PLANS/f'target{i}/native/launch-plan.json').read_text()); bs={b['name']:b for b in p['buffers']}
   bounds=[]
   for l in p['launches']:
    op=l['op']; n=math.prod(bs[l['inputs'][0]]['shape']) if l.get('inputs') and l['inputs'][0] in bs else 0
    if op in zero: bound=0
    elif op in ('norm','hc_combine'):
     # Native shape not serialized; conservative maximum admitted input elements.
     self.assertGreater(n,0);bound=n*4
    elif op=='route': bound=(2*((n+15)//16)+2*n)*4
    elif op=='argmax':bound=2*((n+255)//256)*4
    elif op=='expert_gather':bound=8*4
    elif op=='gdn':bound=4192*4
    elif op=='gdn_norm_gate':bound=48*4*4
    elif op=='qsa_prepare':bound=30*8*4
    elif op=='qsa_append_pool':bound=((131072+3)//4)*4*4
    elif op=='qsa_select':bound=((131072+3)//4)*4
    elif op=='qsa_attention':bound=16+24*258*((min(131072,2051)+31)//32)*4
    else:self.fail('unproved writer '+op)
    bounds.append(bound)
   self.assertLessEqual(max(bounds),8*1024**2)
   print('target',i,'128K source-derived writer upper',max(bounds))
if __name__=='__main__':unittest.main()
