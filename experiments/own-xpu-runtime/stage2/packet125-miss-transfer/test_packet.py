"""CPU gates for replay, full receipt coverage and the non-lowering kill gate."""
import copy,json,resource,struct,unittest
from build_engine import P,sha,limits
import micro_gate as G
class Tests(unittest.TestCase):
 def fixture(self):
  rows=[dict(kind='device',copy_only_ordinal=1,copy_queues_available=1),dict(kind='allocation',pinned_bytes=6*1024**3,scrub_bytes=512*1024**2,aligned_mod64k=0,compact_mod64k=64)]
  raw=(P/'evidence/cases.bin').read_bytes()
  for i in range(384):
   token,layer,mask=struct.unpack_from('<III',raw,i*132);n=mask.bit_count();b=n*(2329600 if layer==2 else 1971200)
   for m in G.MODES:
    cp=m.startswith('bcs_');rows.append(dict(kind='sample',view=m,case=i,token=token,layer=layer,mask=mask,misses=n,miss_bytes=b,wall_ns=200 if m=='production' else 100,route_readback_ns=10 if cp else 0,serial_copy_wait_ns=0,copy_event_sum_ns=5,gate_ns=20,activation_ns=5,down_ns=20,delivered_bytes_checked=b if cp else 0,copy_events=n*(1 if m in ('bcs_aligned','bcs_contiguous') else 3) if cp else 0,all_bytes_exact=True,diagnostic_only=True))
  rows.append(dict(kind='summary',passed=True,drained=True,cases=384,samples=2688,model_loaded=False,diagnostic_only=True));return rows
 def test_inputs(self):
  from route_inputs import read_inputs
  read_inputs()
 def test_complete(self):self.assertEqual(len(G.analyze(self.fixture())['speed_qualified']),6)
 def test_missing(self):
  r=self.fixture();del r[5]
  with self.assertRaises(AssertionError):G.analyze(r)
 def test_duplicate(self):
  r=self.fixture();r.insert(-1,r[5])
  with self.assertRaises(AssertionError):G.analyze(r)
 def test_nan(self):
  r=self.fixture();r[5]['wall_ns']=float('nan')
  with self.assertRaises(AssertionError):G.analyze(r)
 def test_wrong_bytes(self):
  r=self.fixture();r[5]['delivered_bytes_checked']+=1
  with self.assertRaises(AssertionError):G.analyze(r)
 def test_mask(self):
  r=self.fixture();r[5]['mask']^=1
  with self.assertRaises(AssertionError):G.analyze(r)
 def test_threshold(self):
  r=self.fixture()
  for v in r:
   if v.get('view')=='bcs_aligned':v['wall_ns']=134
  self.assertNotIn('bcs_aligned',G.analyze(r)['speed_qualified'])
 def test_sparse_gate(self):
  r=self.fixture()
  for v in r:
   if v.get('view')=='bcs_aligned' and v['token']%64!=0:v['wall_ns']=201
  self.assertNotIn('bcs_aligned',G.analyze(r)['speed_qualified'])
 def test_reverse_order(self):
  with self.assertRaises(AssertionError):G.analyze(self.fixture(),owner=2)
 def test_iq3_extraction(self):
  parent=P.parent/'packet58j-onecard-port'
  s=(parent/'p28/submit.cpp').read_text();s=s[:s.index('void validate(')]+s[s.index('#ifndef OWN_RT_HOST_ONLY\nstruct Share'):s.index('#ifndef OWN_RT_HOST_ONLY\ntemplate<bool OutputPair>')]+ '\n}\n'
  for name in ('submit.hpp','dense.hpp','expert.hpp'):s=s.replace('#include "'+name+'"','#include "../packet58j-onecard-port/p28/'+name+'"')
  expected='// Exact production p28 Kernel/lanes/Share extraction; see build input pins.\n'+s
  self.assertEqual((P/'iq3_kernel.hpp').read_text(),expected)
 def test_no_resource_import_side_effect(self):
  import exec_limits
  baseline=exec_limits.snapshot();__import__('run_micro');self.assertEqual(exec_limits.snapshot(),baseline)
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,)*2);limits()
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
 (P/'evidence/cpu-tests.json').write_text(json.dumps(dict(passed=result.wasSuccessful(),tests=result.testsRun,device_executed=False,sources={n:sha(P/n) for n in ('test_packet.py','micro_gate.py','route_inputs.py','replay.cpp','prepare_routes.py')}),indent=2)+'\n')
 raise SystemExit(not result.wasSuccessful())
